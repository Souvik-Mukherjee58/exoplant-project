"""Structured JSON logging and request observability middleware for ExoSignal.

Production-grade observability layer providing:
1. JSON-structured log output (machine-parseable by ELK, Datadog, CloudWatch).
2. Per-request correlation IDs (X-Request-ID header propagation).
3. Request/response timing metrics with automatic slow-query alerting.
4. Startup telemetry for infrastructure health verification.
"""

import logging
import json
import time
import uuid
import sys
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter for production log aggregation pipelines.

    Output format:
        {"timestamp": "...", "level": "INFO", "logger": "app.main", "message": "...", "extra": {...}}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra fields attached to the record
        for key in ("request_id", "method", "path", "status_code",
                     "duration_ms", "client_ip", "user_agent"):
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
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        ))

    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware that attaches correlation IDs and timing to every request.

    Features:
    - Propagates or generates X-Request-ID for distributed tracing.
    - Logs request start and completion with duration.
    - Emits warnings for slow requests (> 500ms).
    - Attaches timing header (X-Process-Time) to responses.
    """

    SLOW_REQUEST_THRESHOLD_MS = 500.0

    async def dispatch(self, request: Request, call_next) -> Response:
        # Propagate or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
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
                "user_agent": request.headers.get("user-agent", "")[:100]
            }
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Unhandled exception on {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "duration_ms": round(duration_ms, 2),
                    "status_code": 500
                },
                exc_info=True
            )
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
                "duration_ms": round(duration_ms, 2)
            }
        )

        return response
