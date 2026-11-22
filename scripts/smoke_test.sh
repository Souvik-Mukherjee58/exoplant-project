#!/usr/bin/env bash
# ==============================================================================
# ExoSignal post-deployment smoke test
#
#   bash scripts/smoke_test.sh <BACKEND_URL> [FRONTEND_URL]
#   bash scripts/smoke_test.sh https://exosignal-backend.fly.dev https://exosignal.vercel.app
#
# Fails (exit 1) if:
#   - any endpoint is not HTTP 200
#   - the live API's n_positives differs from the committed evaluation.json of the active artifact
#   - FRONTEND_URL is given and CORS does not allow it, or the frontend does not serve index.html
# ==============================================================================

set -euo pipefail

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ -z "${1:-${API_URL:-}}" ]; then
  echo "Usage: bash scripts/smoke_test.sh <BACKEND_URL> [FRONTEND_URL]"
  exit 2
fi

TARGET_URL="${1:-${API_URL}}"
TARGET_URL="${TARGET_URL%/}"
FRONTEND_URL="${2:-${FRONTEND_URL:-}}"
FRONTEND_URL="${FRONTEND_URL%/}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python}"

echo "Backend : ${TARGET_URL}"
if [ -n "${FRONTEND_URL}" ]; then echo "Frontend: ${FRONTEND_URL}"; fi

TMP_BODY=$(mktemp)
TMP_HDR=$(mktemp)
trap 'rm -f "${TMP_BODY}" "${TMP_HDR}"' EXIT
FAILED=0

check_endpoint() {
  local name="$1" path="$2" code
  code=$(curl -s -L -o "${TMP_BODY}" -w "%{http_code}" --max-time 30 "${TARGET_URL}${path}") || true
  if [ "${code}" = "200" ]; then
    printf "[PASS] %-28s %s\n" "${name}" "${path}"
  else
    printf "[FAIL] %-28s %s (HTTP %s) %s\n" "${name}" "${path}" "${code}" "$(head -c 160 "${TMP_BODY}" 2>/dev/null)"
    FAILED=$((FAILED + 1))
  fi
}

check_endpoint "Liveness" "/health"
check_endpoint "Readiness" "/ready"
check_endpoint "Top targets" "/api/v1/top-targets?limit=5"
check_endpoint "Planet detail" "/api/v1/planets/TRAPPIST-1%20e"
check_endpoint "Linear SHAP explain" "/api/v1/planets/TRAPPIST-1%20e/explain"
check_endpoint "Evaluation" "/api/v1/evaluation/benchmark"

# n_positives served live must equal the committed evaluation of the active artifact
LIVE_N=$("${PYTHON}" -c "import json,sys; print(json.load(open(sys.argv[1])).get('n_positives'))" "${TMP_BODY}" 2>/dev/null || echo "?")
VERSION=$(tr -d '[:space:]' < "${REPO_ROOT}/backend/artifacts/active_version.txt")
EVAL_JSON="${REPO_ROOT}/backend/artifacts/${VERSION}/evaluation.json"
FILE_N=$("${PYTHON}" -c "import json,sys; print(json.load(open(sys.argv[1])).get('n_positives'))" "${EVAL_JSON}" 2>/dev/null || echo "?")
if [ "${LIVE_N}" != "?" ] && [ "${LIVE_N}" = "${FILE_N}" ]; then
  echo "[PASS] n_positives live == ${VERSION}/evaluation.json (${LIVE_N})"
else
  echo "[FAIL] n_positives live=${LIVE_N} vs ${VERSION}/evaluation.json=${FILE_N}"
  FAILED=$((FAILED + 1))
fi

if [ -n "${FRONTEND_URL}" ]; then
  code=$(curl -s -o "${TMP_BODY}" -w "%{http_code}" --max-time 30 "${FRONTEND_URL}/") || true
  if [ "${code}" = "200" ] && grep -qi '<div id="root"' "${TMP_BODY}"; then
    echo "[PASS] Frontend serves index.html"
  else
    echo "[FAIL] Frontend ${FRONTEND_URL}/ (HTTP ${code})"
    FAILED=$((FAILED + 1))
  fi
  curl -s -D "${TMP_HDR}" -o /dev/null --max-time 30 -H "Origin: ${FRONTEND_URL}" \
    "${TARGET_URL}/api/v1/top-targets?limit=1" || true
  allow=$(grep -i '^access-control-allow-origin:' "${TMP_HDR}" | tr -d '\r' | cut -d' ' -f2- || true)
  if [ "${allow}" = "${FRONTEND_URL}" ] || [ "${allow}" = "*" ]; then
    echo "[PASS] CORS allows ${FRONTEND_URL} (${allow})"
  else
    echo "[FAIL] CORS: Access-Control-Allow-Origin='${allow}' for Origin ${FRONTEND_URL}"
    FAILED=$((FAILED + 1))
  fi
fi

if [ "${FAILED}" -eq 0 ]; then
  echo "SMOKE TEST: PASS"
  exit 0
fi
echo "SMOKE TEST: FAIL (${FAILED})"
exit 1
