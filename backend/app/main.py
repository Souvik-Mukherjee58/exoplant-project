"""Main FastAPI application for ExoSignal with production observability and decoupled lifecycle."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import v1
from app.config import settings
from app.observability import (
    HTTP_STATUS_TO_CODE,
    ETagCacheMiddleware,
    RateLimitingMiddleware,
    RequestTracingMiddleware,
    configure_logging,
    request_id_ctx,
)
from app.services.query_engine import CatalogQueryEngine

# Configure structured logging before anything else
_env = os.environ.get("EXOSIGNAL_ENV", settings.EXOSIGNAL_ENV)
_json_logs = os.environ.get("JSON_LOGS", "true").lower() in ("true", "1", "yes")
_log_level = os.environ.get("LOG_LEVEL", settings.LOG_LEVEL)
configure_logging(level=_log_level, json_output=_json_logs)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Decoupled application lifecycle:
    Warm up vectorized DuckDB query engine, precomputed artifacts, and TreeSHAP explainer on startup;
    close connections cleanly on shutdown.
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
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Consistent Error Response Exception Handlers
# ---------------------------------------------------------------------------


def _format_error_response(status_code: int, message: str, detail: Any, details_payload: Any = None) -> JSONResponse:
    """Build unified consistent JSON error response schema."""
    req_id = request_id_ctx.get()
    code = HTTP_STATUS_TO_CODE.get(status_code, "ERROR")
    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": req_id} if req_id else None,
        content={
            "detail": detail,
            "error": {
                "code": code,
                "message": message,
                "status_code": status_code,
                "request_id": req_id,
                "details": details_payload,
            },
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions with consistent error schema."""
    return _format_error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        detail=exc.detail,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle 422 request parameter validation errors with consistent schema."""
    return _format_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Request parameter validation failed",
        detail=exc.errors(),
        details_payload=exc.errors(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected 500 exceptions with consistent schema and secure logging."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return _format_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected server error occurred while processing the request",
        detail="Internal server error",
    )


# ---------------------------------------------------------------------------
# Middleware Pipeline
# Order: outer-to-inner -> Tracing -> RateLimiting -> ETag/Cache -> Gzip -> CORS
# ---------------------------------------------------------------------------

app.add_middleware(RequestTracingMiddleware)
app.add_middleware(RateLimitingMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)
app.add_middleware(ETagCacheMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

is_wildcard = "*" in settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Core System Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return {
        "message": "ExoSignal API",
        "version": "0.3.0",
        "description": "Exoplanet Follow-Up Target Prioritization Platform",
        "engine": "DuckDB Vectorized Analytical Engine",
        "environment": _env,
    }


@app.get("/health")
async def health():
    """Liveness probe: verifies process is alive and returns basic service status."""
    try:
        engine = CatalogQueryEngine.get_instance()
        count = engine.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0] if engine.conn else 0
        return {
            "status": "ok",
            "service": "exosignal",
            "version": "0.3.0",
            "query_engine": "DuckDB Vectorized Parquet Engine",
            "artifact_version": engine.active_version,
            "catalog_records": count,
            "environment": _env,
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e), "environment": _env}


@app.get("/ready")
async def ready():
    """
    Readiness probe: verifies that the artifact version is loaded into memory,
    DuckDB can execute queries, and the ML subsystems are ready to serve traffic.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        if engine.conn is None:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "error": "DuckDB connection is not initialized"},
            )

        count = engine.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0]
        if count <= 0:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "error": "Catalog contains zero records"},
            )

        return {
            "status": "ready",
            "artifact_version": engine.active_version,
            "duckdb": "ok",
            "catalog_records": count,
            "environment": _env,
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "error": str(e)},
        )


@app.get("/metrics")
async def metrics():
    """
    Lightweight operational metrics endpoint for monitoring dashboards.
    Returns subsystem health, artifact metadata, and model registry summary.
    """
    result = {"service": "exosignal", "version": "0.3.0", "environment": _env, "subsystems": {}}

    # DuckDB health
    try:
        engine = CatalogQueryEngine.get_instance()
        count = engine.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0] if engine.conn else 0
        result["subsystems"]["duckdb"] = {
            "status": "ok",
            "artifact_version": engine.active_version,
            "catalog_records": count,
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
            "n_features": len(explainer.feature_names),
        }
    except Exception as e:
        result["subsystems"]["shap_explainer"] = {"status": "unavailable", "error": str(e)}

    # Model registry
    try:
        registry_path = Path("artifacts/registry.json")
        if not registry_path.exists() and Path("backend/artifacts/registry.json").exists():
            registry_path = Path("backend/artifacts/registry.json")

        if registry_path.exists():
            with open(registry_path, "r", encoding="utf-8") as f:
                reg = json.load(f)
            result["subsystems"]["model_registry"] = {
                "status": "ok",
                "registered_versions": len(reg.get("versions", {})),
                "promotions": len(reg.get("promotion_history", [])),
            }
        else:
            result["subsystems"]["model_registry"] = {"status": "not_initialized"}
    except Exception as e:
        result["subsystems"]["model_registry"] = {"status": "error", "error": str(e)}

    return result


# Include API routers
app.include_router(v1.router, prefix="/api/v1", tags=["v1"])
