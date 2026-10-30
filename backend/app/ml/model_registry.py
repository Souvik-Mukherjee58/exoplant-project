"""Model Registry for versioned ML artifact lifecycle management.

Tracks model lineage, training provenance, evaluation metrics, and deployment status
across immutable versioned artifact directories. Designed for interview-grade MLOps
demonstrations without requiring external infrastructure (MLflow, W&B, etc.).

Registry Structure:
    artifacts/
    ├── registry.json              # Central registry index
    ├── active_version.txt         # Pointer to production artifact
    ├── v1_2026-10-23/
    │   ├── planets.parquet
    │   ├── ltr_model.joblib
    │   ├── manifest.json
    │   └── registry_entry.json    # Per-version metadata
    └── v1_2026-10-24/
        └── ...
"""

import datetime
import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

REGISTRY_FILE = "registry.json"


class ModelRegistry:
    """
    Local-first model registry providing:
    1. Immutable artifact registration with SHA256 integrity checksums.
    2. Training provenance (hyperparameters, feature set, dataset fingerprint).
    3. Evaluation metric snapshots per version (NDCG@10, MAP, Precision@10).
    4. Promotion/rollback of active production version with audit trail.
    5. Lineage queries across all registered versions.
    """

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
        self.registry_path = self.artifacts_dir / REGISTRY_FILE
        self._registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load or initialize the central registry index."""
        if self.registry_path.exists():
            with open(self.registry_path, "r") as f:
                return cast(Dict[str, Any], json.load(f))
        return {
            "schema_version": "1.0",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "versions": {},
            "promotion_history": [],
        }

    def _save_registry(self) -> None:
        """Persist registry to disk atomically."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.registry_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(self._registry, f, indent=2, default=str)
        tmp_path.replace(self.registry_path)

    @staticmethod
    def _compute_checksum(filepath: Path) -> str:
        """Compute SHA256 checksum of a file."""
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    def register_version(
        self,
        version: str,
        model_path: str,
        parquet_path: str,
        training_config: Dict[str, Any],
        evaluation_metrics: Dict[str, Any],
        dataset_stats: Optional[Dict[str, Any]] = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Register a new artifact version with full provenance metadata.

        Args:
            version: Artifact version tag (e.g. 'v1_2026-10-23').
            model_path: Path to the serialized LTR model (.joblib).
            parquet_path: Path to the compiled Parquet catalog.
            training_config: Hyperparameters, feature list, split strategy.
            evaluation_metrics: Offline benchmark results (NDCG@10, MAP, etc.).
            dataset_stats: Optional dataset-level statistics.
            notes: Free-text annotation for this version.

        Returns:
            The registered entry dictionary.
        """
        model_file = Path(model_path)
        parquet_file = Path(parquet_path)

        entry = {
            "version": version,
            "registered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "registered",
            "artifacts": {
                "model": {
                    "path": str(model_file),
                    "sha256": self._compute_checksum(model_file) if model_file.exists() else None,
                    "size_bytes": model_file.stat().st_size if model_file.exists() else None,
                },
                "parquet": {
                    "path": str(parquet_file),
                    "sha256": self._compute_checksum(parquet_file) if parquet_file.exists() else None,
                    "size_bytes": parquet_file.stat().st_size if parquet_file.exists() else None,
                },
            },
            "training": training_config,
            "evaluation": evaluation_metrics,
            "dataset": dataset_stats or {},
            "environment": {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "hostname": platform.node(),
            },
            "notes": notes,
        }

        # Store in central registry
        self._registry["versions"][version] = entry

        # Also write per-version entry for self-contained artifact directories
        version_dir = self.artifacts_dir / version
        if version_dir.exists():
            entry_path = version_dir / "registry_entry.json"
            with open(entry_path, "w") as f:
                json.dump(entry, f, indent=2, default=str)

        self._save_registry()
        return entry

    def promote(self, version: str, reason: str = "") -> None:
        """
        Promote a registered version to active production status.

        Updates active_version.txt pointer and records audit trail entry.
        """
        if version not in self._registry["versions"]:
            raise ValueError(f"Version '{version}' is not registered in the model registry")

        # Read current active version for audit
        active_ptr = self.artifacts_dir / "active_version.txt"
        previous_version = active_ptr.read_text().strip() if active_ptr.exists() else None

        # Update pointer
        active_ptr.write_text(version)

        # Update status
        for v, entry in self._registry["versions"].items():
            if v == version:
                entry["status"] = "production"
            elif entry.get("status") == "production":
                entry["status"] = "archived"

        # Audit trail
        self._registry["promotion_history"].append(
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "from_version": previous_version,
                "to_version": version,
                "reason": reason,
            }
        )

        self._save_registry()

    def rollback(self, reason: str = "") -> Optional[str]:
        """
        Rollback to the previously active version.

        Returns the version rolled back to, or None if no history exists.
        """
        history = self._registry.get("promotion_history", [])
        if len(history) < 1:
            return None

        previous = history[-1].get("from_version")
        if previous and previous in self._registry["versions"]:
            self.promote(str(previous), reason=f"ROLLBACK: {reason}")
            return str(previous)
        return None

    def get_version(self, version: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific registered version."""
        return cast(Optional[Dict[str, Any]], self._registry["versions"].get(version))

    def get_active_version(self) -> Optional[str]:
        """Get the currently active (production) version tag."""
        active_ptr = self.artifacts_dir / "active_version.txt"
        if active_ptr.exists():
            return active_ptr.read_text().strip()
        return None

    def list_versions(self) -> List[Dict[str, Any]]:
        """List all registered versions with summary metadata."""
        versions = []
        for tag, entry in sorted(
            self._registry["versions"].items(), key=lambda x: x[1].get("registered_at", ""), reverse=True
        ):
            versions.append(
                {
                    "version": tag,
                    "status": entry.get("status", "unknown"),
                    "registered_at": entry.get("registered_at"),
                    "ndcg_at_10": entry.get("evaluation", {}).get("ndcg@10"),
                    "map": entry.get("evaluation", {}).get("map"),
                    "precision_at_10": entry.get("evaluation", {}).get("precision@10"),
                    "notes": entry.get("notes", ""),
                }
            )
        return versions

    def validate_integrity(self, version: str) -> Dict[str, Any]:
        """
        Validate artifact integrity by recomputing SHA256 checksums
        and comparing against registered values.
        """
        entry = self._registry["versions"].get(version)
        if not entry:
            return {"valid": False, "error": f"Version '{version}' not found in registry"}

        results: Dict[str, Any] = {"version": version, "checks": {}}
        all_valid = True

        for artifact_key in ["model", "parquet"]:
            artifact_info = entry.get("artifacts", {}).get(artifact_key, {})
            filepath = Path(artifact_info.get("path", ""))
            expected_sha = artifact_info.get("sha256")

            if not filepath.exists():
                results["checks"][artifact_key] = {"status": "MISSING", "path": str(filepath)}
                all_valid = False
            elif expected_sha:
                actual_sha = self._compute_checksum(filepath)
                matched = actual_sha == expected_sha
                results["checks"][artifact_key] = {
                    "status": "OK" if matched else "CORRUPTED",
                    "expected_sha256": expected_sha[:16] + "...",
                    "actual_sha256": actual_sha[:16] + "...",
                }
                if not matched:
                    all_valid = False
            else:
                results["checks"][artifact_key] = {"status": "NO_CHECKSUM"}

        results["valid"] = all_valid
        return results

    def compare_versions(self, version_a: str, version_b: str) -> Dict[str, Any]:
        """
        Compare evaluation metrics between two registered versions.
        Useful for promotion decisions and A/B analysis.
        """
        entry_a = self._registry["versions"].get(version_a)
        entry_b = self._registry["versions"].get(version_b)

        if not entry_a or not entry_b:
            missing = version_a if not entry_a else version_b
            return {"error": f"Version '{missing}' not found"}

        eval_a = entry_a.get("evaluation", {})
        eval_b = entry_b.get("evaluation", {})

        metrics = ["ndcg@10", "map", "precision@10", "pr_auc"]
        comparison = {}
        for m in metrics:
            val_a = eval_a.get(m)
            val_b = eval_b.get(m)
            if val_a is not None and val_b is not None:
                comparison[m] = {
                    version_a: round(val_a, 4),
                    version_b: round(val_b, 4),
                    "delta": round(val_a - val_b, 4),
                    "winner": version_a if val_a >= val_b else version_b,
                }

        return {"version_a": version_a, "version_b": version_b, "metric_comparison": comparison}
