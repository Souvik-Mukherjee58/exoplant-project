"""Structured JSON logging and request observability middleware for ExoSignal.

Production-grade observability layer providing:
1. JSON-structured log output (machine-parseable by ELK, Datadog, CloudWatch).
2. Per-request correlation IDs (X-Request-ID header propagation via contextvars).
3. Request/response timing metrics with automatic slow-query alerting.
4. In-memory sliding-window rate limiting per client IP with Retry-After.
5. ETag and Cache-Control header injection for immutable artifact version caching (304 Not Modified).
"""

import contextvars
import hashlib
import json
import logging
import sys
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Context variable for request correlation ID across async task execution
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

HTTP_STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter for production log aggregation pipelines.

    Output format:
        {"timestamp": "...", "level": "INFO", "logger": "app.main", "message": "...", "request_id": "...", ...}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id from contextvar if not explicitly passed on record
        ctx_req_id = request_id_ctx.get()
        if ctx_req_id:
            log_entry["request_id"] = ctx_req_id

        # Include exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra fields attached to the record
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "client_ip", "user_agent"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, use JSON formatter; otherwise use human-readable format.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicate output
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if json_output:
        handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
        )

    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware that attaches correlation IDs and timing to every request.

    Features:
    - Propagates or generates X-Request-ID for distributed tracing.
    - Sets request_id context variable for unified structured log emission.
    - Logs request start and completion with execution latency.
    - Emits warnings for slow requests (> 500ms).
    - Attaches timing headers (X-Process-Time, X-Request-ID) to all responses.
    """

    SLOW_REQUEST_THRESHOLD_MS = 500.0

    async def dispatch(self, request: Request, call_next) -> Response:
        # Propagate or generate request ID
        request_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
        token = request_id_ctx.set(request_id)
        start_time = time.perf_counter()

        logger = logging.getLogger("exosignal.http")

        # Log request start
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "")[:100],
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Unhandled exception on {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "duration_ms": round(duration_ms, 2),
                    "status_code": 500,
                },
                exc_info=True,
            )
            request_id_ctx.reset(token)
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Attach response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        # Log completion
        log_level = logging.WARNING if duration_ms > self.SLOW_REQUEST_THRESHOLD_MS else logging.INFO
        logger.log(
            log_level,
            f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.1f}ms)"
            + (" [SLOW]" if duration_ms > self.SLOW_REQUEST_THRESHOLD_MS else ""),
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        request_id_ctx.reset(token)
        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Lightweight in-memory sliding-window rate limiting per client IP.

    Default: 120 requests/minute per IP (configurable via settings.RATE_LIMIT_PER_MINUTE).
    Exempts liveness/readiness probes (/health, /ready, /metrics) and API documentation.
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.limit = requests_per_minute
        self.window_seconds = 60.0
        self._history: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._exempt_paths = {"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        limit = getattr(request.app.state, "rate_limit_per_minute", None)
        if limit is None:
            limit = self.limit

        if path in self._exempt_paths or limit <= 0:
            return await call_next(request)

        # Extract client IP (respecting reverse-proxy X-Forwarded-For if available)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._history.get(client_ip, [])
            valid = [t for t in timestamps if t > cutoff]

            if len(valid) >= limit:
                self._history[client_ip] = valid
                req_id = request.headers.get("X-Request-ID") or request_id_ctx.get() or str(uuid.uuid4())[:8]
                return JSONResponse(
                    status_code=429,
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(now + 60)),
                        "X-Request-ID": req_id,
                    },
                    content={
                        "detail": f"Rate limit exceeded. Maximum {limit} requests per minute allowed.",
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit of {limit} requests per minute exceeded.",
                            "status_code": 429,
                            "request_id": req_id,
                            "details": {"limit_per_minute": limit, "retry_after_seconds": 60},
                        },
                    },
                )

            valid.append(now)
            self._history[client_ip] = valid
            remaining = max(0, limit - len(valid))

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class ETagCacheMiddleware(BaseHTTPMiddleware):
    """
    Attaches ETag and Cache-Control headers to read-only GET endpoints.

    Derives ETags deterministically from active artifact version and request query parameters.
    Returns 304 Not Modified when client's If-None-Match matches the current active artifact ETag.
    """

    def __init__(self, app):
        super().__init__(app)
        self._active_version_cache: Optional[str] = None

    def _get_active_version(self) -> str:
        if self._active_version_cache:
            return self._active_version_cache
        try:
            from app.services.query_engine import CatalogQueryEngine

            v = CatalogQueryEngine.get_instance().active_version
            if v:
                self._active_version_cache = v
                return v
        except Exception:
            pass
        return "v1"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only apply caching headers to read-only GET and HEAD requests
        if request.method not in ("GET", "HEAD"):
            return await call_next(request)

        path = request.url.path
        # Exclude dynamic monitoring probes and docs
        if path in ("/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        active_version = self._get_active_version()
        etag_seed = f"{active_version}:{path}:{request.url.query}"
        digest = hashlib.sha256(etag_seed.encode("utf-8")).hexdigest()[:16]
        etag = f'W/"{active_version}-{digest}"'

        # Conditional request check (If-None-Match)
        client_etag = request.headers.get("if-none-match")
        if client_etag and client_etag.strip() == etag:
            req_id = request.headers.get("X-Request-ID") or request_id_ctx.get() or ""
            headers = {
                "ETag": etag,
                "Cache-Control": "public, max-age=3600, must-revalidate",
            }
            if req_id:
                headers["X-Request-ID"] = req_id
            return Response(status_code=304, headers=headers)

        response = await call_next(request)

        # On successful response, inject ETag and Cache-Control
        if response.status_code == 200:
            response.headers["ETag"] = etag
            response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"

        return response
