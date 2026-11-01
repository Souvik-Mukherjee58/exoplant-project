#!/usr/bin/env bash
# ==============================================================================
# ExoSignal Post-Deployment Smoke Test Script
#
# Usage:
#   ./scripts/smoke_test.sh [BASE_URL]
# Example:
#   ./scripts/smoke_test.sh https://exosignal-backend.fly.dev
#   API_URL=https://exosignal-backend.fly.dev ./scripts/smoke_test.sh
# ==============================================================================

set -euo pipefail

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "Usage: ./scripts/smoke_test.sh [BASE_URL]"
  echo "Example: ./scripts/smoke_test.sh https://exosignal-backend.fly.dev"
  exit 0
fi

# Determine target URL (argument $1 takes priority, then $API_URL, then localhost default)
TARGET_URL="${1:-${API_URL:-http://localhost:8000}}"
# Strip trailing slash if present
TARGET_URL="${TARGET_URL%/}"

echo "=================================================================="
echo " Running ExoSignal Post-Deployment Smoke Tests"
echo " Target Base URL: ${TARGET_URL}"
echo "=================================================================="

# Temporary file for HTTP response inspection
TMP_BODY=$(mktemp)
trap 'rm -f "${TMP_BODY}"' EXIT

FAILED=0

check_endpoint() {
  local name="$1"
  local path="$2"
  local url="${TARGET_URL}${path}"

  printf "Testing %-35s ... " "${name} (${path})"

  local http_code
  http_code=$(curl -s -L -o "${TMP_BODY}" -w "%{http_code}" --max-time 15 "${url}" || echo "000")

  if [ "${http_code}" -eq 200 ]; then
    echo "[PASS] (HTTP 200)"
  else
    echo "[FAIL] (HTTP ${http_code})"
    echo "  URL: ${url}"
    echo "  Response body preview: $(head -c 200 "${TMP_BODY}" 2>/dev/null || true)"
    FAILED=$((FAILED + 1))
  fi
}

# 1. Liveness check
check_endpoint "Liveness Probe" "/health"

# 2. Readiness check (verifies DuckDB in-memory query & active artifact)
check_endpoint "Readiness Probe" "/ready"

# 3. Top targets endpoint
check_endpoint "Top Targets Endpoint" "/api/v1/top-targets?limit=5"

# 4. Target dossier detail lookup
check_endpoint "Planet Detail Dossier" "/api/v1/planets/TRAPPIST-1%20e"

# 5. Linear SHAP attribution explain endpoint
check_endpoint "Linear SHAP Explain" "/api/v1/explain/TRAPPIST-1%20e"

echo "=================================================================="
if [ "${FAILED}" -eq 0 ]; then
  echo " [SUCCESS] All 5 production smoke test checks PASSED."
  echo " Deployment is verified healthy and ready to serve traffic."
  echo "=================================================================="
  exit 0
else
  echo " [FAILURE] ${FAILED} check(s) failed."
  echo " Check server logs and network configuration."
  echo "=================================================================="
  exit 1
fi
