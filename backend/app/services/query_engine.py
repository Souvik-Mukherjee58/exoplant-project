"""In-process analytical query engine using DuckDB and Parquet.

Provides:
1. Zero-copy / in-process vectorized SQL execution over immutable Parquet artifacts.
2. Thread-safe concurrent read operations releasing Python's GIL.
3. Predicate pushdown for range queries, parametric filtering, and case-insensitive search.
4. Indexed in-memory analytical table (latency depends on the host; nothing is guaranteed).
5. Decoupled read-only serving architecture separating pipeline builds from API requests.
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, cast

import duckdb
import numpy as np

from app.config import resolve_artifacts_dir, settings
from app.ml.pca_projection import project_catalog

logger = logging.getLogger(__name__)

# Every catalog query selects these; an artifact without them cannot be served.
REQUIRED_COLUMNS = frozenset(
    {
        "planet_name",
        "target_priority_score",
        "ml_priority_score",
        "ml_rank",
        "rank_delta",
        "planet_radius",
        "planet_mass",
        "orbital_period",
        "equilibrium_temperature",
        "distance",
        "hz_status",
        "anomaly_score",
        "discovery_method",
    }
)


def _fetch_one(cursor: Any, sql: str) -> Tuple[Any, ...]:
    """Run a query that always returns exactly one row (an aggregate such as COUNT).

    No row means the engine is broken, not that there is no data, so it is an error rather than None.
    """
    row = cursor.execute(sql).fetchone()
    if row is None:
        raise RuntimeError(f"Query returned no row: {' '.join(sql.split())[:80]}")
    return cast(Tuple[Any, ...], row)


class CatalogQueryEngine:
    """
    Vectorized SQL query engine over the exoplanet Parquet catalog.

    Thread-safe singleton managing an in-process DuckDB analytical database.
    """

    _instance: Optional["CatalogQueryEngine"] = None
    _lock = threading.Lock()

    def __init__(self, artifacts_dir: Optional[str] = None):
        self.artifacts_dir = resolve_artifacts_dir(artifacts_dir)
        self.active_version: Optional[str] = None
        self.parquet_path: Optional[Path] = None
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        self.columns: FrozenSet[str] = frozenset()
        self.manifest: Dict[str, Any] = {}
        self.precomputed_pca: Dict[str, Any] = {}
        self.precomputed_stats: Dict[str, Any] = {}
        self.ltr_feature_importance: Dict[str, Any] = {}
        self.benchmark_report: Dict[str, Any] = {}
        self._init_engine()

    @classmethod
    def get_instance(cls, artifacts_dir: Optional[str] = None) -> "CatalogQueryEngine":
        """Thread-safe singleton accessor."""
        with cls._lock:
            if cls._instance is None or cls._instance.conn is None:
                cls._instance = cls(artifacts_dir=artifacts_dir)
            return cls._instance

    @classmethod
    def reload_instance(cls, artifacts_dir: Optional[str] = None) -> "CatalogQueryEngine":
        """Force reload of the query engine (e.g. after pipeline rebuild)."""
        with cls._lock:
            cls._instance = cls(artifacts_dir=artifacts_dir)
            return cls._instance

    def _resolve_parquet_path(self) -> Tuple[str, Path]:
        """Locate the active Parquet catalog artifact."""
        # 1. Check explicit environment variable or settings override first
        env_version = os.environ.get("ARTIFACT_VERSION") or getattr(settings, "ARTIFACT_VERSION", None)
        if env_version:
            env_version = str(env_version).strip()
            candidate = self.artifacts_dir / env_version / "planets.parquet"
            if candidate.exists():
                return env_version, candidate

        # 2. Check active_version.txt pointer
        active_ptr = self.artifacts_dir / "active_version.txt"
        if active_ptr.exists():
            version = active_ptr.read_text().strip()
            candidate = self.artifacts_dir / version / "planets.parquet"
            if candidate.exists():
                return version, candidate

        # Fallback to any versioned parquet
        parquet_candidates = list(self.artifacts_dir.glob("*/planets.parquet"))
        if parquet_candidates:
            # Sort by directory name
            latest = sorted(parquet_candidates, key=lambda p: p.parent.name, reverse=True)[0]
            return latest.parent.name, latest

        # Legacy processed fallback
        legacy_parquet = Path(settings.PROCESSED_DATA_DIR) / "planets.parquet"
        if legacy_parquet.exists():
            return "legacy", legacy_parquet

        raise FileNotFoundError(
            f"No Parquet catalog found in {self.artifacts_dir}. "
            "Please run 'python -m app.pipeline build' to compile catalog artifacts."
        )

    def _init_engine(self) -> None:
        """Initialize DuckDB in-memory database and create indexed catalog table."""
        self.active_version, self.parquet_path = self._resolve_parquet_path()
        logger.info(f"Initializing DuckDB Query Engine with artifact: {self.active_version} ({self.parquet_path})")

        # In-process thread-safe in-memory connection
        self.conn = duckdb.connect(database=":memory:")
        # Optimize DuckDB execution threads
        self.conn.execute("PRAGMA threads=4;")

        parquet_posix = self.parquet_path.as_posix()
        # Create in-memory table directly from Parquet
        self.conn.execute(f"CREATE TABLE planets AS SELECT * FROM read_parquet('{parquet_posix}');")

        # The artifact's schema is fixed per version: read it once and fail fast if a required column is missing.
        # Optional columns (absent from older artifacts) are looked up in self.columns by the queries.
        self.columns = frozenset(row[0] for row in self.conn.execute("DESCRIBE planets").fetchall())
        missing = sorted(REQUIRED_COLUMNS - self.columns)
        if missing:
            raise RuntimeError(f"Artifact {self.active_version} lacks required columns {missing}: rebuild it")

        # Secondary indexes for the common filters
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ml_priority ON planets(ml_priority_score);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_heuristic_priority ON planets(target_priority_score);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_hz_status ON planets(hz_status);")

        row_count = _fetch_one(self.conn, "SELECT COUNT(*) FROM planets")[0]
        logger.info(f"DuckDB Query Engine ready. Loaded {row_count} planets into memory.")

        # Preload artifact JSONs into memory once at startup
        self.manifest = self._load_json_artifact("manifest.json")
        self.precomputed_pca = self._load_json_artifact("precomputed_pca.json")
        self.precomputed_stats = self._load_json_artifact("precomputed_stats.json")
        self.ltr_feature_importance = self._load_json_artifact("ltr_feature_importance.json")
        self.benchmark_report = self._load_json_artifact("benchmark_report.json") or self._load_json_artifact(
            "evaluation.json"
        )

    def _load_json_artifact(self, filename: str) -> Dict[str, Any]:
        """Load a JSON artifact from active version directory or root artifacts dir."""
        import json

        if self.active_version:
            v_file = self.artifacts_dir / self.active_version / filename
            if v_file.exists():
                try:
                    with open(v_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (OSError, ValueError):  # unreadable or not JSON
                    logger.warning("Failed to load %s", v_file, exc_info=True)
        root_file = self.artifacts_dir / filename
        if root_file.exists():
            try:
                with open(root_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):  # unreadable or not JSON
                logger.warning("Failed to load %s", root_file, exc_info=True)
        return {}

    def get_precomputed_pca(self) -> Dict[str, Any]:
        """Return precomputed PCA projection from memory."""
        if not self.precomputed_pca:
            self.precomputed_pca = self._compute_pca_in_memory()
        return self.precomputed_pca

    def _compute_pca_in_memory(self) -> Dict[str, Any]:
        """The PCA projection, computed here only when the artifact has no precomputed_pca.json."""
        return project_catalog(self.get_cursor().execute("SELECT * FROM planets").df())

    def get_ltr_info(self) -> Dict[str, Any]:
        """Return LTR model metadata from in-memory manifest."""
        models_info = self.manifest.get("models", {})
        bench_info = self.manifest.get("benchmark", {})
        return {
            "artifact_version": self.active_version or "unknown",
            "model_name": models_info.get(
                "selected_production_model", models_info.get("ltr_model", "ltr_model.joblib")
            ),
            "algorithm": models_info.get(
                "production_algorithm",
                models_info.get("ltr_algorithm", "unknown (algorithm missing from manifest)"),
            ),
            "top_features": models_info.get("top_features", models_info.get("ltr_top_features", [])),
            "benchmark_leaderboard": bench_info.get("leaderboard", []),
        }

    def get_ltr_feature_importances(self) -> Dict[str, Any]:
        """Return ranked feature importances from in-memory preloaded artifact."""
        if self.ltr_feature_importance:
            return self.ltr_feature_importance
        return {"error": "LTR feature importance not available."}

    def get_benchmark_report(self, split: str = "test") -> Dict[str, Any]:
        """Return the preloaded benchmark report, and only for the split it was computed on."""
        if self.benchmark_report and self.benchmark_report.get("evaluation_split") == split:
            return self.benchmark_report
        return {"error": f"Evaluation benchmark report for split '{split}' not available."}

    def count_records(self) -> int:
        """Number of planets in the served catalog (one query, on a thread-local cursor)."""
        return int(_fetch_one(self.get_cursor(), "SELECT COUNT(*) FROM planets")[0])

    def get_cursor(self) -> duckdb.DuckDBPyConnection:
        """Get a thread-safe connection cursor for concurrent query execution."""
        if self.conn is None:
            raise RuntimeError("The query engine is closed")
        return self.conn.cursor()

    # ---------------------------------------------------------------------------
    # Analytical Query Operations
    # ---------------------------------------------------------------------------

    def query_planets(
        self,
        limit: int = 100,
        offset: int = 0,
        min_priority: float = 0.0,
        max_priority: float = 100.0,
        q: Optional[str] = None,
        hz_status: Optional[str] = None,
        sort_by: str = "heuristic",
        eligible_only: bool = False,
        exclude_observed: bool = False,
        size_class: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query exoplanets with predicate pushdown, parametric filters, and pagination.

        Uses parameterized SQL to guarantee SQL-injection safety.
        """
        cursor = self.get_cursor()
        table_cols = self.columns

        if sort_by == "heuristic":
            sort_order = "target_priority_score DESC"
            filter_col = (
                "heuristic_habitability_score"
                if "heuristic_habitability_score" in table_cols
                else "target_priority_score"
            )
        elif sort_by == "ml":
            sort_order = "ml_rank ASC NULLS LAST"  # ineligible planets have a score but no rank
            filter_col = "ml_priority_score"
        elif sort_by == "priority":
            filter_col = "priority_score" if "priority_score" in table_cols else "ml_priority_score"
            # Older artifacts lack the rank or even the score: sort by what the filter uses.
            sort_order = "priority_rank ASC NULLS LAST" if "priority_rank" in table_cols else f"{filter_col} DESC"
        else:
            sort_order = "target_priority_score DESC"
            filter_col = "target_priority_score"

        where_clauses: List[str] = []
        params: List[Any] = []
        if sort_by == "heuristic" or min_priority > 0.0 or max_priority < 100.0:
            where_clauses += [f"{filter_col} >= ?", f"{filter_col} <= ?"]
            params += [float(min_priority), float(max_priority)]
            if sort_by in ("priority", "ml") and "eligible_for_transmission" in table_cols:
                # A model score of an ineligible planet means nothing, so no score range can select it.
                where_clauses.append("eligible_for_transmission = true")

        if eligible_only:
            if "eligible_for_transmission" in table_cols:
                where_clauses.append("eligible_for_transmission = true")
            elif "is_transiting" in table_cols:
                where_clauses.append("is_transiting = true")

        if exclude_observed and ("already_observed_jwst" in table_cols or "is_jwst_target" in table_cols):
            obs_col = "already_observed_jwst" if "already_observed_jwst" in table_cols else "is_jwst_target"
            where_clauses.append(f"({obs_col} IS NULL OR {obs_col} = false)")

        if size_class and size_class.strip():
            sc = size_class.strip().lower()
            if "kempton_size_class" in table_cols:
                if "terrestrial" in sc or "rocky" in sc:
                    where_clauses.append("lower(kempton_size_class) = 'terrestrial'")
                elif "small" in sc:
                    where_clauses.append("lower(kempton_size_class) = 'small sub-neptune'")
                elif "large" in sc:
                    where_clauses.append("lower(kempton_size_class) = 'large sub-neptune'")
                elif "giant" in sc or "jovian" in sc:
                    where_clauses.append(  # parenthesised: a bare OR would bypass every other filter
                        "(lower(kempton_size_class) LIKE '%giant%' OR lower(kempton_size_class) LIKE '%jovian%')"
                    )
                else:
                    where_clauses.append("contains(lower(kempton_size_class), ?)")
                    params.append(sc)
            else:
                # Radius thresholds fallback
                if "terrestrial" in sc or "rocky" in sc:
                    where_clauses.append("planet_radius < 1.5")
                elif "small" in sc:
                    where_clauses.append("planet_radius >= 1.5 AND planet_radius < 2.75")
                elif "large" in sc:
                    where_clauses.append("planet_radius >= 2.75 AND planet_radius < 4.0")
                elif "giant" in sc or "jovian" in sc:
                    where_clauses.append("planet_radius >= 4.0")

        if q and q.strip():
            # contains() is a literal match: '%' and '_' in user input are not wildcards. A variant that is
            # empty after normalisation would match every row, so it is left out.
            clean_q = q.strip().lower()
            name_matches = ["contains(lower(planet_name), ?)"]
            params.append(clean_q)
            spaced = clean_q.replace("-", " ").strip()
            if spaced:
                name_matches.append("contains(replace(lower(planet_name), '-', ' '), ?)")
                params.append(spaced)
            compact = clean_q.replace("-", "").replace(" ", "")
            if compact:
                name_matches.append("contains(replace(replace(lower(planet_name), '-', ''), ' ', ''), ?)")
                params.append(compact)
            where_clauses.append("(" + " OR ".join(name_matches) + ")")

        if hz_status and hz_status.strip():
            where_clauses.append("lower(hz_status) = ?")
            params.append(hz_status.strip().lower())

        where_sql = " AND ".join(where_clauses) or "true"
        params.extend([int(limit), int(offset)])

        extra_selects = []
        for c in [
            "priority_score",
            "priority_rank",
            "heuristic_habitability_score",
            "is_transiting",
            "eligible_for_transmission",
            "exclusion_reason",
            "already_observed_jwst",
            "is_jwst_target",
            "tsm",
            "tsm_threshold",
            "kempton_size_class",
            "percentile_rank",
            "percentile_rank_string",
            "oof_ml_rank",
            "oof_priority_score",
            "unobserved_rank",
            "stellar_name",
            "semi_major_axis",
            "stellar_radius",
            "stellar_mass",
            "stellar_effective_temperature",
            "stellar_metallicity",
            "j_magnitude",
            "k_magnitude",
            "earth_similarity",
            "mass_source",
            "mass_is_estimated",
        ]:
            if c in table_cols:
                extra_selects.append(c)
        extra_sql = (",\n                " + ",\n                ".join(extra_selects)) if extra_selects else ""

        sql = f"""
            SELECT
                planet_name,
                target_priority_score,
                ml_priority_score,
                ml_rank,
                rank_delta,
                planet_radius,
                planet_mass,
                orbital_period,
                equilibrium_temperature,
                distance,
                hz_status,
                anomaly_score,
                discovery_method{extra_sql}
            FROM planets
            WHERE {where_sql}
            ORDER BY {sort_order}, planet_name ASC
            LIMIT ? OFFSET ?
        """

        df = cursor.execute(sql, params).df()
        return df.to_dict(orient="records")

    def get_planet_by_name(self, planet_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete details for a single planet using exact case-insensitive match.
        """
        if not planet_name or not planet_name.strip():
            return None

        cursor = self.get_cursor()
        clean = planet_name.strip()
        sql = """
            SELECT *
            FROM planets
            WHERE lower(trim(planet_name)) = lower(trim(?))
               OR replace(lower(trim(planet_name)), '-', ' ') = replace(lower(trim(?)), '-', ' ')
               OR replace(replace(lower(trim(planet_name)), '-', ''), ' ', '') = replace(replace(lower(trim(?)), '-', ''), ' ', '')
            LIMIT 1
        """
        df = cursor.execute(sql, [clean, clean, clean]).df()
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def get_top_targets(
        self, limit: int = 10, min_priority: float = 0.0, sort_by: str = "priority", exclude_observed: bool = True
    ) -> List[Dict[str, Any]]:
        """Retrieve highest-ranked targets above priority threshold (eligible unobserved planets only by default)."""
        return self.query_planets(
            limit=limit,
            offset=0,
            min_priority=min_priority,
            sort_by=sort_by,
            eligible_only=True,
            exclude_observed=exclude_observed,
        )

    def get_known_jwst_targets(self) -> List[Dict[str, Any]]:
        """Planets labelled as JWST targets in the artifact (unverified labels), by out-of-fold rank."""
        cursor = self.get_cursor()
        table_cols = self.columns

        obs_col = "already_observed_jwst" if "already_observed_jwst" in table_cols else "is_jwst_target"
        order_col = (
            "oof_ml_rank ASC NULLS LAST, priority_score DESC" if "oof_ml_rank" in table_cols else "priority_score DESC"
        )

        sql = f"""
            SELECT *
            FROM planets
            WHERE ({obs_col} = true)
            ORDER BY {order_col}, planet_name ASC
        """
        df = cursor.execute(sql).df()
        return df.to_dict(orient="records")

    def get_recommendations(
        self, limit: int = 25, offset: int = 0, exclude_observed: bool = True, size_class: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve candidate recommendations filtered by observation status and size class."""
        return self.query_planets(
            limit=limit,
            offset=offset,
            min_priority=0.0,
            sort_by="priority",
            eligible_only=True,
            exclude_observed=exclude_observed,
            size_class=size_class,
        )

    def get_analysis_stats(self) -> Dict[str, Any]:
        """
        Compute population-level statistical aggregates in a single vectorized SQL pass.
        """
        cursor = self.get_cursor()

        # Score distribution
        score_stats = _fetch_one(
            cursor,
            """
            SELECT
                COUNT(*) as total_planets,
                min(target_priority_score) as min_score,
                max(target_priority_score) as max_score,
                avg(target_priority_score) as mean_score,
                median(target_priority_score) as median_score,
                stddev_pop(target_priority_score) as std_score,
                min(anomaly_score) as min_anomaly,
                max(anomaly_score) as max_anomaly,
                avg(anomaly_score) as mean_anomaly,
                median(anomaly_score) as median_anomaly
            FROM planets
        """,
        )

        # Empirical histogram bins (0-20, 20-40, 40-60, 60-80, 80-100)
        hist_rows = cursor.execute("""
            SELECT
                CASE
                    WHEN target_priority_score < 20 THEN '0-20'
                    WHEN target_priority_score < 40 THEN '20-40'
                    WHEN target_priority_score < 60 THEN '40-60'
                    WHEN target_priority_score < 80 THEN '60-80'
                    ELSE '80-100'
                END as score_bin,
                COUNT(*) as count
            FROM planets
            GROUP BY 1
            ORDER BY 1
        """).fetchall()
        bin_map = {r[0]: r[1] for r in hist_rows}
        standard_bins = ["0-20", "20-40", "40-60", "60-80", "80-100"]
        priority_histogram = [{"range": b, "count": bin_map.get(b, 0)} for b in standard_bins]

        # Habitable zone breakdown
        hz_rows = cursor.execute("""
            SELECT hz_status, COUNT(*) as count
            FROM planets
            GROUP BY hz_status
            ORDER BY count DESC, hz_status
        """).fetchall()
        hz_distribution = {r[0]: r[1] for r in hz_rows if r[0] is not None}

        # Discovery method breakdown
        disc_rows = cursor.execute("""
            SELECT discovery_method, COUNT(*) as count
            FROM planets
            WHERE discovery_method IS NOT NULL
            GROUP BY discovery_method
            ORDER BY count DESC, discovery_method
        """).fetchall()
        discovery_distribution = {r[0]: r[1] for r in disc_rows}

        return {
            "total_planets": int(score_stats[0]),
            "score_distribution": {
                "min": round(float(score_stats[1]), 1),
                "max": round(float(score_stats[2]), 1),
                "mean": round(float(score_stats[3]), 1),
                "median": round(float(score_stats[4]), 1),
                "std": round(float(score_stats[5]), 1),
            },
            "priority_histogram": priority_histogram,
            "anomaly_distribution": {
                "min": round(float(score_stats[6]), 3),
                "max": round(float(score_stats[7]), 3),
                "mean": round(float(score_stats[8]), 3),
                "median": round(float(score_stats[9]), 3),
            },
            "hz_distribution": hz_distribution,
            "discovery_method_distribution": discovery_distribution,
        }

    def benchmark_latency(self, iterations: int = 100) -> Dict[str, Any]:
        """
        Time a fixed set of queries, one after another, in this process.

        This is neither an HTTP measurement nor a concurrency test; see reports/LOADTEST.md for those.
        """
        cursor = self.get_cursor()
        latencies_ms = []

        query_templates: List[Tuple[str, List[Any]]] = [
            ("SELECT * FROM planets WHERE ml_priority_score >= 80 LIMIT 20", []),
            ("SELECT * FROM planets WHERE lower(planet_name) LIKE '%toi%' LIMIT 20", []),
            ("SELECT * FROM planets WHERE hz_status = 'Inside HZ' ORDER BY ml_priority_score DESC LIMIT 20", []),
            ("SELECT avg(ml_priority_score), stddev(ml_priority_score) FROM planets GROUP BY hz_status", []),
            ("SELECT * FROM planets WHERE planet_radius BETWEEN 0.8 AND 1.8 LIMIT 50", []),
        ]

        for i in range(iterations):
            sql, params = query_templates[i % len(query_templates)]
            start = time.perf_counter()
            _ = cursor.execute(sql, params).fetchall()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies_ms.append(elapsed_ms)

        latencies_ms.sort()
        n = len(latencies_ms)
        return {
            "iterations": iterations,
            "engine": f"DuckDB {duckdb.__version__} (In-Memory Vectorized)",
            "catalog_records": _fetch_one(cursor, "SELECT COUNT(*) FROM planets")[0],
            "min_ms": round(float(latencies_ms[0]), 3),
            "max_ms": round(float(latencies_ms[-1]), 3),
            "mean_ms": round(float(np.mean(latencies_ms)), 3),
            "p50_ms": round(float(latencies_ms[int(n * 0.50)]), 3),
            "p95_ms": round(float(latencies_ms[int(n * 0.95)]), 3),
            "p99_ms": round(float(latencies_ms[int(n * 0.99)]), 3),
            "p95_below_10ms_in_this_run": bool(latencies_ms[int(n * 0.95)] < 10.0),
        }

    def close(self) -> None:
        """Close connection cleanly."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("DuckDB Query Engine closed.")
        with CatalogQueryEngine._lock:
            if CatalogQueryEngine._instance is self:
                CatalogQueryEngine._instance = None
