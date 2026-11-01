#!/usr/bin/env bash
# ==============================================================================
# ExoSignal Load Test Runner
#
# Usage:
#   ./scripts/run_loadtest.sh <base_url>
# Example:
#   ./scripts/run_loadtest.sh http://localhost:8000
#   ./scripts/run_loadtest.sh https://exosignal-backend.fly.dev
# ==============================================================================

set -euo pipefail

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: ./scripts/run_loadtest.sh <base_url>"
    echo "Example: ./scripts/run_loadtest.sh http://localhost:8000"
    exit 0
fi

BASE_URL="${1:-http://localhost:8000}"
# Strip trailing slash
BASE_URL="${BASE_URL%/}"

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${WORKSPACE_ROOT}"

mkdir -p reports

echo "================================================================================"
echo " ExoSignal API Load Testing Runner"
echo " Target Base URL: ${BASE_URL}"
echo " Stages         : Ramping to 50 then 200 Virtual Users (VUs)"
echo " Export Summary : reports/k6_summary.json"
echo "================================================================================"

# 1. Check if local native k6 is available
if command -v k6 >/dev/null 2>&1; then
    echo "[+] Running native k6 load test suite (loadtest/api.js)..."
    k6 run \
        -e BASE_URL="${BASE_URL}" \
        --summary-export reports/k6_summary.json \
        loadtest/api.js
    echo "[+] Load test complete. Summary exported to reports/k6_summary.json"
    echo "[+] Run 'python scripts/render_loadtest_report.py' to update reports/LOADTEST.md"
    exit 0
fi

# 2. Check if Docker is available to run grafana/k6
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "[+] Running k6 inside Docker container (grafana/k6)..."
    docker run --rm -i --net=host \
        -v "${WORKSPACE_ROOT}/loadtest:/loadtest" \
        -v "${WORKSPACE_ROOT}/reports:/reports" \
        grafana/k6 run \
        -e BASE_URL="${BASE_URL}" \
        --summary-export /reports/k6_summary.json \
        /loadtest/api.js
    echo "[+] Docker load test complete. Summary exported to reports/k6_summary.json"
    echo "[+] Run 'python scripts/render_loadtest_report.py' to update reports/LOADTEST.md"
    exit 0
fi

echo "[ERROR] Neither native 'k6' nor a running Docker daemon was detected." >&2
echo "To run the load test:" >&2
echo "  Option A: Install k6 natively: https://k6.io/docs/get-started/installation/" >&2
echo "  Option B: Start Docker Desktop and re-run this script." >&2
exit 1
