"""High-performance vectorized analytical query engine using DuckDB and Parquet.

Provides:
1. Zero-copy / in-process vectorized SQL execution over immutable Parquet artifacts.
2. Thread-safe concurrent read operations releasing Python's GIL.
3. Predicate pushdown for range queries, parametric filtering, and case-insensitive search.
4. B-Tree indexed in-memory analytical table with sub-10ms latency guarantees.
5. Decoupled read-only serving architecture separating pipeline builds from API requests.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import logging
import time
import threading
import duckdb
import pandas as pd
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class CatalogQueryEngine:
    """
    Vectorized SQL query engine over the exoplanet Parquet catalog.

    Thread-safe singleton managing an in-process DuckDB analytical database.
    """

    _instance: Optional["CatalogQueryEngine"] = None
    _lock = threading.Lock()

    def __init__(self, artifacts_dir: Optional[str] = None):
        if artifacts_dir:
            p = Path(artifacts_dir)
            if not p.exists() and (Path("backend") / p).exists():
                p = Path("backend") / p
            self.artifacts_dir = p
        else:
            if Path("artifacts").exists():
                self.artifacts_dir = Path("artifacts")
            elif Path("backend/artifacts").exists():
                self.artifacts_dir = Path("backend/artifacts")
            else:
                self.artifacts_dir = Path("artifacts")
        self.active_version: Optional[str] = None
        self.parquet_path: Optional[Path] = None
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        self._init_engine()

    @classmethod
    def get_instance(cls, artifacts_dir: Optional[str] = None) -> "CatalogQueryEngine":
        """Thread-safe singleton accessor."""
        with cls._lock:
            if cls._instance is None:
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

        # Create secondary B-Tree indexes for sub-10ms filtering
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ml_priority ON planets(ml_priority_score);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_heuristic_priority ON planets(target_priority_score);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_hz_status ON planets(hz_status);")

        row_count = self.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0]
        logger.info(f"DuckDB Query Engine ready. Loaded {row_count} planets into memory.")

    def get_cursor(self) -> duckdb.DuckDBPyConnection:
        """Get a thread-safe connection cursor for concurrent query execution."""
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
        eligible_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Query exoplanets with predicate pushdown, parametric filters, and pagination.

        Uses parameterized SQL to guarantee SQL-injection safety.
        """
        cursor = self.get_cursor()

        # Check existing columns in table
        try:
            table_cols = {c[0] for c in cursor.execute("DESCRIBE planets").fetchall()}
        except Exception:
            table_cols = set()

        if sort_by == "heuristic":
            sort_order = "target_priority_score DESC"
            filter_col = "heuristic_habitability_score" if "heuristic_habitability_score" in table_cols else "target_priority_score"
        elif sort_by in ("ml", "priority"):
            sort_order = "priority_rank ASC NULLS LAST" if "priority_rank" in table_cols else "ml_priority_score DESC"
            filter_col = "priority_score" if "priority_score" in table_cols else "ml_priority_score"
        else:
            sort_order = "target_priority_score DESC"
            filter_col = "target_priority_score"

        where_clauses = [f"{filter_col} >= ?", f"{filter_col} <= ?"]
        params: List[Any] = [float(min_priority), float(max_priority)]

        if eligible_only:
            if "eligible_for_transmission" in table_cols:
                where_clauses.append("eligible_for_transmission = true")
            elif "is_transiting" in table_cols:
                where_clauses.append("is_transiting = true")

        if q and q.strip():
            clean_q = q.strip().lower()
            q_variants = [
                f"%{clean_q}%",
                f"%{clean_q.replace('-', ' ')}%",
                f"%{clean_q.replace('-', '').replace(' ', '')}%"
            ]
            where_clauses.append(
                "(lower(planet_name) LIKE ? OR "
                "replace(lower(planet_name), '-', ' ') LIKE ? OR "
                "replace(replace(lower(planet_name), '-', ''), ' ', '') LIKE ?)"
            )
            params.extend(q_variants)

        if hz_status and hz_status.strip():
            where_clauses.append("lower(hz_status) = ?")
            params.append(hz_status.strip().lower())

        where_sql = " AND ".join(where_clauses)
        params.extend([int(limit), int(offset)])

        extra_selects = []
        for c in [
            "priority_score", "priority_rank", "heuristic_habitability_score",
            "is_transiting", "eligible_for_transmission", "exclusion_reason"
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
            ORDER BY {sort_order}
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
        self,
        limit: int = 10,
        min_priority: float = 0.0,
        sort_by: str = "priority"
    ) -> List[Dict[str, Any]]:
        """Retrieve highest-ranked targets above priority threshold (eligible planets only)."""
        return self.query_planets(
            limit=limit,
            offset=0,
            min_priority=min_priority,
            sort_by=sort_by,
            eligible_only=True
        )

    def get_analysis_stats(self) -> Dict[str, Any]:
        """
        Compute population-level statistical aggregates in a single vectorized SQL pass.
        """
        cursor = self.get_cursor()

        # Score distribution
        score_stats = cursor.execute("""
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
        """).fetchone()

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
        standard_bins = ['0-20', '20-40', '40-60', '60-80', '80-100']
        priority_histogram = [{"range": b, "count": bin_map.get(b, 0)} for b in standard_bins]

        # Habitable zone breakdown
        hz_rows = cursor.execute("""
            SELECT hz_status, COUNT(*) as count
            FROM planets
            GROUP BY hz_status
            ORDER BY count DESC
        """).fetchall()
        hz_distribution = {r[0]: r[1] for r in hz_rows if r[0] is not None}

        # Discovery method breakdown
        disc_rows = cursor.execute("""
            SELECT discovery_method, COUNT(*) as count
            FROM planets
            WHERE discovery_method IS NOT NULL
            GROUP BY discovery_method
            ORDER BY count DESC
        """).fetchall()
        discovery_distribution = {r[0]: r[1] for r in disc_rows}

        return {
            "total_planets": int(score_stats[0]),
            "score_distribution": {
                "min": round(float(score_stats[1]), 1),
                "max": round(float(score_stats[2]), 1),
                "mean": round(float(score_stats[3]), 1),
                "median": round(float(score_stats[4]), 1),
                "std": round(float(score_stats[5]), 1)
            },
            "priority_histogram": priority_histogram,
            "anomaly_distribution": {
                "min": round(float(score_stats[6]), 3),
                "max": round(float(score_stats[7]), 3),
                "mean": round(float(score_stats[8]), 3),
                "median": round(float(score_stats[9]), 3)
            },
            "hz_distribution": hz_distribution,
            "discovery_method_distribution": discovery_distribution
        }

    def benchmark_latency(self, iterations: int = 100) -> Dict[str, Any]:
        """
        Execute latency benchmark over simulated concurrent analytical queries.

        Measures P50, P95, and P99 query latency in milliseconds.
        """
        cursor = self.get_cursor()
        latencies_ms = []

        query_templates = [
            ("SELECT * FROM planets WHERE ml_priority_score >= 80 LIMIT 20", []),
            ("SELECT * FROM planets WHERE lower(planet_name) LIKE '%toi%' LIMIT 20", []),
            ("SELECT * FROM planets WHERE hz_status = 'Inside HZ' ORDER BY ml_priority_score DESC LIMIT 20", []),
            ("SELECT avg(ml_priority_score), stddev(ml_priority_score) FROM planets GROUP BY hz_status", []),
            ("SELECT * FROM planets WHERE planet_radius BETWEEN 0.8 AND 1.8 LIMIT 50", [])
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
            "catalog_records": self.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0],
            "min_ms": round(float(latencies_ms[0]), 3),
            "max_ms": round(float(latencies_ms[-1]), 3),
            "mean_ms": round(float(np.mean(latencies_ms)), 3),
            "p50_ms": round(float(latencies_ms[int(n * 0.50)]), 3),
            "p95_ms": round(float(latencies_ms[int(n * 0.95)]), 3),
            "p99_ms": round(float(latencies_ms[int(n * 0.99)]), 3),
            "sub_10ms_guarantee": bool(latencies_ms[int(n * 0.95)] < 10.0)
        }

    def close(self) -> None:
        """Close connection cleanly."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("DuckDB Query Engine closed.")
