"""Main FastAPI application for ExoSignal with production observability and decoupled lifecycle."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import v1
from app.config import APP_VERSION, resolve_artifacts_dir, settings
from app.ml.model_consistency import ExplanationsUnavailable
from app.observability import (
    UNEXPECTED_ERROR_MESSAGE,
    ETagCacheMiddleware,
    RateLimitingMiddleware,
    RequestTracingMiddleware,
    build_error_response,
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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Decoupled application lifecycle:
    Warm up vectorized DuckDB query engine, precomputed artifacts, and Linear SHAP explainer on startup;
    close connections cleanly on shutdown.
    """
    logger.info(f"ExoSignal starting (env={_env}, log_level={_log_level})")
    degraded: List[str] = []  # optional subsystems that failed; readiness does not depend on them

    try:
        engine = CatalogQueryEngine.get_instance()
        logger.info(f"DuckDB query engine initialized with artifact: {engine.active_version}")
    except Exception:
        logger.exception("Failed to initialize DuckDB query engine on startup (/ready will report 503)")

    try:
        from app.ml.explainability import SHAPExplainer

        explainer = SHAPExplainer.get_instance()
        logger.info(f"Linear SHAP explainer initialized with model: {explainer.model_path}")
    except ExplanationsUnavailable:
        # Logged with its details by the check; the catalog is still served, explanations answer 503.
        logger.error("Explanations are disabled: the model does not match the served catalog (/ready reports 503)")
    except Exception:  # noqa: BLE001 - logged with traceback; /metrics reports the explainer state
        logger.warning("Could not initialize Linear SHAP explainer on startup", exc_info=True)
        degraded.append("explanations unavailable")
    else:
        try:
            catalog = CatalogQueryEngine.get_instance().get_cursor().execute("SELECT * FROM planets").df()
            logger.info("Explanation features precomputed for %d planets", explainer.warm_feature_cache(catalog))
        except Exception:  # noqa: BLE001 - logged with traceback; explanations are then computed on first request
            logger.warning("Could not precompute explanation features on startup", exc_info=True)
            degraded.append("explanation features not precomputed")

    # The final line states what /ready will answer: it uses the same check.
    problem, _ = _readiness()
    if problem is not None:
        logger.error("ExoSignal started but is NOT READY: %s (/ready answers 503)", problem["error"])
    elif degraded:
        logger.warning("ExoSignal startup complete and ready, degraded: %s", "; ".join(degraded))
    else:
        logger.info("ExoSignal startup complete — all subsystems online")
    yield

    logger.info("ExoSignal shutting down")
    try:
        engine = CatalogQueryEngine.get_instance()
        engine.close()
    except Exception:  # noqa: BLE001 - logged with traceback; shutting down anyway
        logger.warning("Query engine did not close cleanly on shutdown", exc_info=True)


app = FastAPI(
    title="ExoSignal API",
    description="Exoplanet Follow-Up Target Prioritization Platform",
    version=APP_VERSION,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Consistent Error Response Exception Handlers
# ---------------------------------------------------------------------------


def _format_error_response(status_code: int, message: str, detail: Any, details_payload: Any = None) -> JSONResponse:
    """Build unified consistent JSON error response schema."""
    return build_error_response(status_code, message, detail, request_id_ctx.get(), details_payload)


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
        status_code=422,
        message="Request parameter validation failed",
        detail=exc.errors(),
        details_payload=exc.errors(),
    )


@app.exception_handler(ExplanationsUnavailable)
async def explanations_unavailable_handler(request: Request, exc: ExplanationsUnavailable) -> JSONResponse:
    """503 rather than an explanation of a model that did not score the served catalog."""
    return _format_error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        message="Explanations are unavailable: the explanation model does not match the served catalog",
        detail=list(exc.report.problems),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected 500 exceptions with consistent schema and secure logging."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return _format_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=UNEXPECTED_ERROR_MESSAGE,
        detail="Internal server error",
    )


# ---------------------------------------------------------------------------
# Middleware Pipeline
# Starlette runs the LAST added middleware first, so a request passes through
# CORS -> Tracing -> RateLimiting -> ETag/Cache -> Gzip -> routes.
# CORS is outermost so that a browser can also read 429 and 304 responses.
# ---------------------------------------------------------------------------

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(ETagCacheMiddleware)
app.add_middleware(
    RateLimitingMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
    trusted_proxy_hops=settings.TRUSTED_PROXY_HOPS,
)
app.add_middleware(RequestTracingMiddleware)


def validate_cors_origins(origins: list) -> list:
    """Fail fast on origin patterns Starlette does not support.

    allow_origins is matched literally, so "https://*.vercel.app" never matches and the deployed frontend
    would be blocked by the browser. Only "*" alone or exact origins are accepted.
    """
    bad = [o for o in origins if "*" in o and o != "*"]
    if bad:
        raise ValueError(
            f"Unsupported CORS_ORIGINS entries {bad}: wildcard subdomains are not matched. "
            """Set exact origins, e.g. CORS_ORIGINS='["https://your-app.vercel.app"]'."""
        )
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=validate_cors_origins(settings.CORS_ORIGINS),
    allow_credentials=False,  # public read-only API: no cookies are used
    allow_methods=["GET", "HEAD", "OPTIONS"],  # the API is read-only: it has no endpoint that changes data or the model
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Core System Endpoints
# ---------------------------------------------------------------------------


@app.get("/", response_model=None)
async def root() -> Dict[str, Any]:
    return {
        "message": "ExoSignal API",
        "version": APP_VERSION,
        "description": "Exoplanet Follow-Up Target Prioritization Platform",
        "engine": "DuckDB Vectorized Analytical Engine",
        "environment": _env,
    }


# Probes query DuckDB and read files: plain `def`, so FastAPI runs them in its thread pool, not on the event loop.
@app.get("/health", response_model=None)
@app.get("/api/v1/health", include_in_schema=False, response_model=None)  # reachable through the frontend's /api proxy
def health() -> Dict[str, Any]:
    """Liveness probe: verifies process is alive and returns basic service status."""
    try:
        engine = CatalogQueryEngine.get_instance()
        count = engine.count_records()
        return {
            "status": "ok",
            "service": "exosignal",
            "version": APP_VERSION,
            "query_engine": "DuckDB Vectorized Parquet Engine",
            "artifact_version": engine.active_version,
            "catalog_records": count,
            "environment": _env,
        }
    except Exception:
        logger.exception("Health probe failed")
        return {"status": "degraded", "error": "query engine unavailable", "environment": _env}


def _readiness() -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """What /ready reports: (problem, None) when not ready, else (None, facts). Also used for the startup log."""
    try:
        engine = CatalogQueryEngine.get_instance()
        if engine.conn is None:
            return {"error": "DuckDB connection is not initialized"}, {}

        count = engine.count_records()
        if count <= 0:
            return {"error": "Catalog contains zero records"}, {}

        # A deployment whose explanation model is not the catalog's model must not go live.
        from app.ml.explainability import SHAPExplainer

        try:
            SHAPExplainer.get_instance()
        except ExplanationsUnavailable as exc:
            return {
                "error": "explanation model does not match the served catalog",
                "problems": list(exc.report.problems),
            }, {}
        except Exception:  # noqa: BLE001 - logged with traceback; the catalog itself is ready (as before this check)
            logger.warning("Readiness: explainer unavailable", exc_info=True)

        return None, {"artifact_version": engine.active_version, "catalog_records": count}
    except Exception:
        logger.exception("Readiness probe failed")
        return {"error": "query engine unavailable"}, {}


@app.get("/ready", response_model=None)
def ready() -> Union[Dict[str, Any], JSONResponse]:
    """
    Readiness probe: verifies that the artifact version is loaded into memory,
    DuckDB can execute queries, and the ML subsystems are ready to serve traffic.
    """
    problem, facts = _readiness()
    if problem is not None:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "not_ready", **problem})
    return {
        "status": "ready",
        "artifact_version": facts["artifact_version"],
        "duckdb": "ok",
        "catalog_records": facts["catalog_records"],
        "environment": _env,
    }


@app.get("/metrics", response_model=None)
@app.get("/api/v1/metrics", include_in_schema=False, response_model=None)
def metrics() -> Dict[str, Any]:
    """
    Lightweight operational metrics endpoint for monitoring dashboards.
    Returns subsystem health, artifact metadata, and model registry summary.
    """
    subsystems: Dict[str, Dict[str, Any]] = {}
    result: Dict[str, Any] = {
        "service": "exosignal",
        "version": APP_VERSION,
        "environment": _env,
        "subsystems": subsystems,
    }

    # DuckDB health
    try:
        engine = CatalogQueryEngine.get_instance()
        count = engine.count_records()
        subsystems["duckdb"] = {
            "status": "ok",
            "artifact_version": engine.active_version,
            "catalog_records": count,
        }
    except Exception:
        logger.exception("Metrics: query engine unavailable")
        subsystems["duckdb"] = {"status": "error"}

    # SHAP explainer health
    try:
        from app.ml.explainability import SHAPExplainer

        explainer = SHAPExplainer.get_instance()
        subsystems["shap_explainer"] = {
            "status": "ok",
            "model_file": Path(str(explainer.model_path)).name,
            "n_features": len(explainer.feature_names),
            "model_check": explainer.consistency.as_dict() if explainer.consistency else None,
        }
    except ExplanationsUnavailable as exc:
        subsystems["shap_explainer"] = {"status": "model_mismatch", "model_check": exc.report.as_dict()}
    except Exception:
        logger.exception("Metrics: explainer unavailable")
        subsystems["shap_explainer"] = {"status": "unavailable"}

    # Model registry
    try:
        registry_path = resolve_artifacts_dir() / "registry.json"

        if registry_path.exists():
            with open(registry_path, "r", encoding="utf-8") as f:
                reg = json.load(f)
            subsystems["model_registry"] = {
                "status": "ok",
                "registered_versions": len(reg.get("versions", {})),
                "promotions": len(reg.get("promotion_history", [])),
            }
        else:
            subsystems["model_registry"] = {"status": "not_initialized"}
    except Exception:
        logger.exception("Metrics: model registry unreadable")
        subsystems["model_registry"] = {"status": "error"}

    return result


# Include API routers
app.include_router(v1.router, prefix="/api/v1", tags=["v1"])


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", getattr(settings, "PORT", 8000)))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
