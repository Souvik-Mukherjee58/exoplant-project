# Changelog

All notable changes to the ExoSignal platform are documented in this file.
Format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), adhering to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-10-30

### Added
- **Production Observability & Serving**:
  - Context-propagated structured JSON logging with `X-Request-ID` correlation.
  - Separate `/health` (system state liveness) and `/ready` (DuckDB index & in-memory artifact query) operational probes.
  - In-memory sliding-window client IP rate limiting (`RATE_LIMIT_PER_MINUTE`).
  - Automated `GZipMiddleware` compression for HTTP payloads $> 1\text{ KB}$.
  - Deterministic HTTP ETag generation based on active catalog version with `304 Not Modified` support.
  - Standardized unified API error envelope (`{"detail": ..., "error": {...}}`).
- **Zero Disk I/O Request Serving**:
  - Preloaded versioned manifests, PCA projections, evaluation statistics, and LTR metadata directly into memory at startup.
  - Automated test verifying zero filesystem read operations (`open`, `read_parquet`, `read_csv`) across all active request paths.
- **Container Hardening & Orchestration**:
  - Pinned base images (`python:3.11.11-slim`, `node:20.18-alpine`, `nginx:1.27.3-alpine`).
  - Unprivileged user execution (`exosignal` UID on backend; `nginx` with `cap_net_bind_service` on frontend).
  - Multi-stage Docker builds isolating development toolchains from runtime containers.
  - Native Docker Compose healthcheck probes on both frontend and backend.
  - Clean clone zero-config support with `.env.example` template and fallback environment defaults.
- **Benchmarking & Load Testing**:
  - Comprehensive k6 script (`loadtest/api.js`) targeting `/planets`, `/top-targets`, `/planets/{name}`, and `/explain/{name}`.
  - Empirical load test report template (`reports/LOADTEST.md`) with latency thresholds and execution steps.
- **Cloud Deployment Infrastructure**:
  - Deployment configuration manifests for Render (`render.yaml`), Fly.io (`fly.toml`), Vercel (`vercel.json`), and Netlify (`netlify.toml`).
  - End-to-end production deployment guide (`DEPLOY.md`).
- **Documentation & Architecture Decisions**:
  - Comprehensive Model Card (`docs/MODEL_CARD.md`).
  - Architecture Decision Records (`docs/adr/0001-0004` covering grouped CV, model selection, DuckDB analytical engine, and UI out-of-fold scoring).
  - Automated README benchmark results table generator (`scripts/render_readme_results.py`).

---

## [0.2.0] - 2026-10-28

### Added
- **Learning-to-Rank (LTR) Machine Learning Framework**:
  - 21 physically motivated astrophysical features spanning transit depth, scale height, insolation flux, bulk density, and infrared attenuation.
  - 25-fold `StratifiedGroupKFold` cross-validation grouped by host star to eliminate multi-planet sibling leakage.
  - 7-model comparative benchmark evaluation (Random, Distance, TSM, ESM, Heuristic, LightGBM, and Regularized Logistic Regression).
  - Selection of Regularized Logistic Regression (Variant A) yielding $+104.6\%$ Average Precision improvement over TSM baseline ($p < 0.001$).
- **In-Process DuckDB Analytical Engine**:
  - Sub-millisecond SQL queries over immutable columnar Parquet catalog storage (`artifacts/{version}/planets.parquet`).
  - Column pruning and predicate pushdown achieving $p_{50} \sim 3.6\text{ ms}$ query latency.
- **TreeSHAP Explainability Layer**:
  - Exact additive feature attributions satisfying $\sum \phi_i + \text{Base} = \text{Score}$ to machine precision.
  - Pairwise differential attribution ($\Delta \phi_i = \phi_i(A) - \phi_i(B)$) explaining ranking reversals between any two planets.
- **Model Registry & Provenance**:
  - Cryptographic SHA256 fingerprinting for model artifacts and catalogs.
  - Atomic zero-downtime model promotion and rollback CLI commands.
- **Frontend Scientific UI/UX**:
  - Interactive TreeSHAP waterfall charts in React.
  - Head-to-head differential comparison view between candidate exoplanets.
  - Canvas-based 3D exoplanet visualizer with realistic atmospheric rendering.
  - Quick Search navigation modal (`Cmd+K` / `Ctrl+K`).

---

## [0.1.0] - 2026-10-22

### Added
- Initial release of ExoSignal.
- Automated data ingestion from NASA Exoplanet Archive composite parameters table.
- Astronomical data cleaning, normalization, and outlier detection (Isolation Forest & Local Outlier Factor).
- Transit eligibility rules enforcing Kempton et al. (2018) criteria and Chen & Kipping mass-radius fallback relations.
- Heuristic composite scoring engine for exoplanet spectroscopic follow-up utility.
- FastAPI backend REST endpoints and Vite React web application.
- Comprehensive automated test suite with pytest and vitest.

