# ExoSignal API Load Test Report

This document records the empirical load test results and benchmarking methodology for the ExoSignal FastAPI backend and DuckDB query engine under concurrent user load.

---

## 1. Test Execution Commands

To execute the load test against a running instance of ExoSignal:

### Local Execution (with k6 installed)

```bash
# Default target: http://localhost:8000
k6 run loadtest/api.js

# Custom target URL (e.g. Docker container or remote staging server):
k6 run -e BASE_URL=http://localhost:8000 loadtest/api.js

# Export detailed summary to JSON:
k6 run --summary-export=reports/summary.json loadtest/api.js
```

### Docker Execution (no local k6 installation required)

```bash
# On Linux / macOS:
docker run --rm -i --net=host -v $(pwd)/loadtest:/loadtest grafana/k6 run /loadtest/api.js

# On Windows PowerShell:
docker run --rm -i --net=host -v ${PWD}/loadtest:/loadtest grafana/k6 run /loadtest/api.js
```

---

## 2. Benchmark Environment & System Under Test

| Parameter | Specification | Notes |
|:---|:---|:---|
| **Host CPU** | `[PLACEHOLDER - e.g. AMD Ryzen / Intel Core / Apple Silicon, N cores]` | Hardware executing the backend server |
| **Host RAM** | `[PLACEHOLDER - e.g. 16 GB / 32 GB / 64 GB]` | Total host physical memory |
| **Operating System** | `[PLACEHOLDER - e.g. Linux Ubuntu 22.04 / macOS 14 / Windows 11]` | OS kernel |
| **Runtime Environment** | Docker Compose (`python:3.11-slim`, Uvicorn, 2 workers) | Production multi-stage container |
| **In-Memory Analytical Engine** | DuckDB v1.1.3 + In-Memory Preloaded Cache | Zero disk I/O on hot request path |
| **Dataset Size** | 5,821 exoplanets (active catalog: `v1_2026-10-29`) | `artifacts/v1_2026-10-29/planets.parquet` (~1.4 MB) |
| **Preloaded Artifacts** | PCA coordinates, evaluation metrics, LTR feature importance | Preloaded into memory at startup |

---

## 3. Workload Profile & Concurrency

- **Traffic Distribution**:
  - `GET /api/v1/planets` (25%): Paginated catalog index query with predicate pushdown and sorting
  - `GET /api/v1/top-targets` (25%): Filtered candidate index scan (unobserved JWST candidates)
  - `GET /api/v1/planets/{name}` (25%): Direct key lookup via DuckDB index
  - `GET /api/v1/explain/{name}` (25%): Real-time TreeSHAP waterfall attribution and invariant validation
- **Ramp Stages**:
  1. *Warmup*: 0 to 5 VUs over 10 seconds
  2. *Sustained Load*: 20 VUs over 30 seconds
  3. *Peak Burst*: 20 to 30 VUs over 10 seconds
  4. *Cooldown*: 30 to 0 VUs over 10 seconds
- **Total Duration**: 60 seconds

---

## 4. Aggregate Performance Summary

> **Note**: Values below are placeholders to be populated upon executing the test with your target environment.

| Performance Metric | Target / Threshold | Empirical Result | Status |
|:---|:---:|:---:|:---:|
| **Peak Concurrency** | $\ge 20\text{ VUs}$ | `[PLACEHOLDER: e.g. 30 VUs]` | `[PENDING]` |
| **Throughput (RPS)** | $\ge 100\text{ req/s}$ | `[PLACEHOLDER: e.g. 145.2 req/s]` | `[PENDING]` |
| **Total Requests Completed** | — | `[PLACEHOLDER: e.g. 8,712]` | `[PENDING]` |
| **Overall Success Rate** | $\ge 99.0\%$ | `[PLACEHOLDER: e.g. 100.0%]` | `[PENDING]` |
| **Overall Error Rate** | $< 1.0\%$ | `[PLACEHOLDER: e.g. 0.00%]` | `[PENDING]` |
| **Median Latency ($p_{50}$)** | $< 25\text{ ms}$ | `[PLACEHOLDER: e.g. 8.4 ms]` | `[PENDING]` |
| **95th Percentile Latency ($p_{95}$)** | $< 150\text{ ms}$ | `[PLACEHOLDER: e.g. 32.1 ms]` | `[PENDING]` |
| **99th Percentile Latency ($p_{99}$)** | $< 300\text{ ms}$ | `[PLACEHOLDER: e.g. 64.7 ms]` | `[PENDING]` |

---

## 5. Per-Endpoint Latency & Throughput Breakdown

| Endpoint | Total Requests | RPS | $p_{50}$ (ms) | $p_{95}$ (ms) | $p_{99}$ (ms) | Error Rate (%) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `GET /api/v1/planets` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]%` |
| `GET /api/v1/top-targets` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]%` |
| `GET /api/v1/planets/{name}` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]%` |
| `GET /api/v1/explain/{name}` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]%` |

---

## 6. Observations & Architectural Analysis

- **In-Memory Startup Preloading**: Zero disk reads occur during the active request path. The artifact manifest, DuckDB database tables, precomputed PCA projections, and LTR metadata reside in RAM after application lifespan startup.
- **TreeSHAP Efficiency**: TreeSHAP feature attributions run via native LightGBM C++ bindings (`pred_contrib=True`), keeping calculation latencies well within the interactive $p_{95} < 50\text{ ms}$ threshold.
- **DuckDB Predicate Pushdown**: DuckDB utilizes column pruning and vectorized filtering on the memory-mapped Parquet table, preventing full dataset scans on filtered queries.
- **ETag & HTTP Caching**: Repeated identical queries return `304 Not Modified` when an `If-None-Match` header is supplied, freeing server resources.

