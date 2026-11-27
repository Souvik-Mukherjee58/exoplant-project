"""Configuration settings for ExoSignal."""

import json
from pathlib import Path
from typing import Any, List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The one version string of the API (FastAPI metadata, /, /health and /metrics).
APP_VERSION = "0.3.0"


class Settings(BaseSettings):
    """Central application configuration with environment variable support."""

    # Environment & Logging
    EXOSIGNAL_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = True

    # API
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000

    # CORS (can be a JSON array e.g. '["http://localhost"]' or comma-separated string)
    CORS_ORIGINS: List[str] = ["*"]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    # Number of reverse proxies in front of the app that append to X-Forwarded-For (Fly.io: 1).
    # 0 = ignore the header (safe default: a client can put anything in it).
    TRUSTED_PROXY_HOPS: int = 0

    # Base directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Data paths (can be overridden via ENV vars e.g. DATA_DIR, RAW_DATA_DIR, etc.)
    DATA_DIR: Path = Path("data")
    RAW_DATA_DIR: Path = Path("data/raw")
    PROCESSED_DATA_DIR: Path = Path("data/processed")
    REFERENCE_DATA_DIR: Path = Path("data/reference")

    # Specific file paths
    JWST_TARGETS_PATH: Path = Path("data/reference/jwst_transmission_targets.csv")
    PROCESSED_DATA_FILE: Path = Path("data/processed/processed_exoplanets.csv")

    # Artifacts paths
    ARTIFACT_VERSION: Optional[str] = None
    ARTIFACTS_DIR: Path = Path("artifacts")
    ACTIVE_VERSION_FILE: Path = Path("artifacts/active_version.txt")

    # ML Settings
    RANDOM_STATE: int = 42
    ANOMALY_CONTAMINATION: float = 0.1

    # API Settings
    API_TIMEOUT: int = 30  # Timeout for external API requests in seconds

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if item]
                except json.JSONDecodeError:
                    pass  # not JSON after all: read it as a comma-separated list below
            return [item.strip() for item in v_stripped.split(",") if item.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if item]
        return ["*"]

    def resolve_path(self, path: Path | str) -> Path:
        """Resolve a path against workspace directories cleanly without guesswork."""
        p = Path(path)
        if p.is_absolute() and p.exists():
            return p
        # Check current working directory first
        if p.exists():
            return p
        # Check relative to BASE_DIR (backend/)
        base_p = self.BASE_DIR / p
        if base_p.exists():
            return base_p
        # Check parent of BASE_DIR (workspace root)
        root_p = self.BASE_DIR.parent / p
        if root_p.exists():
            return root_p
        # Default to base_p or p
        return p if p.is_absolute() else base_p

    def get_jwst_targets_path(self) -> Path:
        """Return resolved path to the JWST transmission targets catalog."""
        return self.resolve_path(self.JWST_TARGETS_PATH)

    def get_artifacts_dir(self) -> Path:
        """The artifacts directory: ARTIFACTS_DIR if absolute, else relative to backend/ (never to the working directory)."""
        p = Path(self.ARTIFACTS_DIR)
        return p if p.is_absolute() else self.BASE_DIR / p

    def get_processed_data_path(self) -> Path:
        """Return resolved path to processed exoplanets CSV."""
        return self.resolve_path(self.PROCESSED_DATA_FILE)


settings: Settings = Settings()


def resolve_artifacts_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """An explicit artifacts directory (relative to the working directory, else to backend/), or the configured one."""
    if not artifacts_dir:
        return settings.get_artifacts_dir()
    p = Path(artifacts_dir)
    if not p.is_absolute() and not p.exists() and (settings.BASE_DIR / p).exists():
        return settings.BASE_DIR / p
    return p


__all__ = ["APP_VERSION", "Settings", "resolve_artifacts_dir", "settings"]
