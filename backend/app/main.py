"""Main FastAPI application for ExoSignal with production observability and decoupled lifecycle."""

import os
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from app.services.query_engine import CatalogQueryEngine
from app.observability import configure_logging, RequestTracingMiddleware

# Configure structured logging before anything else
_env = os.environ.get("EXOSIGNAL_ENV", "development")
_json_logs = _env == "production"
_log_level = os.environ.get("LOG_LEVEL", "INFO")
configure_logging(level=_log_level, json_output=_json_logs)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Decoupled application lifecycle:
    Warm up vectorized DuckDB query engine and TreeSHAP explainer on startup;
    close connections on shutdown.
    """
    logger.info(f"ExoSignal starting (env={_env}, log_level={_log_level})")

    try:
        engine = CatalogQueryEngine.get_instance()
        logger.info(f"DuckDB query engine initialized with artifact: {engine.active_version}")
    except Exception as e:
        logger.error(f"Failed to initialize DuckDB query engine on startup: {str(e)}")

    try:
        from app.ml.explainability import SHAPExplainer
        explainer = SHAPExplainer.get_instance()
        logger.info(f"TreeSHAP explainer initialized with model: {explainer.model_path}")
    except Exception as e:
        logger.warning(f"Could not initialize TreeSHAP explainer on startup: {str(e)}")

    logger.info("ExoSignal startup complete — all subsystems online")
    yield

    logger.info("ExoSignal shutting down")
    try:
        engine = CatalogQueryEngine.get_instance()
        engine.close()
    except Exception:
        pass


app = FastAPI(
    title="ExoSignal API",
    description="Exoplanet Follow-Up Target Prioritization Platform",
    version="0.3.0",
    lifespan=lifespan
)

# Request tracing middleware (must be added before CORS)
app.add_middleware(RequestTracingMiddleware)

# CORS: allow origins from config; when wildcard is used, credentials must be False
is_wildcard = "*" in settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "ExoSignal API",
        "version": "0.3.0",
        "description": "Exoplanet Follow-Up Target Prioritization Platform",
        "engine": "DuckDB Vectorized Analytical Engine",
        "environment": _env
    }


@app.get("/health")
async def health():
    try:
        engine = CatalogQueryEngine.get_instance()
        count = engine.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0]
        return {
            "status": "ok",
            "query_engine": "DuckDB Vectorized Parquet Engine",
            "artifact_version": engine.active_version,
            "catalog_records": count,
            "environment": _env
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e), "environment": _env}


@app.get("/metrics")
async def metrics():
    """
    Lightweight operational metrics endpoint for monitoring dashboards.
    Returns subsystem health, artifact metadata, and model registry summary.
    """
    import json
    from pathlib import Path

    result = {
        "service": "exosignal",
        "version": "0.3.0",
        "environment": _env,
        "subsystems": {}
    }

    # DuckDB health
    try:
        engine = CatalogQueryEngine.get_instance()
        count = engine.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0]
        result["subsystems"]["duckdb"] = {
            "status": "ok",
            "artifact_version": engine.active_version,
            "catalog_records": count
        }
    except Exception as e:
        result["subsystems"]["duckdb"] = {"status": "error", "error": str(e)}

    # SHAP explainer health
    try:
        from app.ml.explainability import SHAPExplainer
        explainer = SHAPExplainer.get_instance()
        result["subsystems"]["shap_explainer"] = {
            "status": "ok",
            "model_path": str(explainer.model_path),
            "n_features": len(explainer.feature_names)
        }
    except Exception as e:
        result["subsystems"]["shap_explainer"] = {"status": "unavailable", "error": str(e)}

    # Model registry
    try:
        registry_path = Path("artifacts/registry.json")
        if registry_path.exists():
            with open(registry_path, "r") as f:
                reg = json.load(f)
            result["subsystems"]["model_registry"] = {
                "status": "ok",
                "registered_versions": len(reg.get("versions", {})),
                "promotions": len(reg.get("promotion_history", []))
            }
        else:
            result["subsystems"]["model_registry"] = {"status": "not_initialized"}
    except Exception as e:
        result["subsystems"]["model_registry"] = {"status": "error", "error": str(e)}

    return result


# Include API routers
from .api import v1

app.include_router(v1.router, prefix="/api/v1", tags=["v1"])