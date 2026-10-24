# ---- Stage 1: Build Stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: Production Runtime ----
FROM python:3.11-slim AS runtime

# libgomp required by LightGBM at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd -r exosignal && useradd -r -g exosignal -d /app -s /sbin/nologin exosignal

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/
COPY data/ ./data/
COPY artifacts/ ./artifacts/
COPY pytest.ini ./

# Ensure artifact pointer exists
RUN test -f artifacts/active_version.txt || echo "No active artifact version" >&2

# Set ownership
RUN chown -R exosignal:exosignal /app

USER exosignal

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EXOSIGNAL_ENV=production \
    CORS_ORIGINS='["*"]' \
    LOG_LEVEL=info \
    WORKERS=2

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Gunicorn with uvicorn workers for production concurrency
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
