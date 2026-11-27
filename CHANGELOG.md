# Changelog

All notable changes to the ExoSignal platform are documented in this file.
Format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), adhering to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- `LICENSE`: MIT License, Copyright (c) 2026 Souvik Mukherjee.
- **API (additive):** `GET /api/v1/explain/{planet_name}` and `GET /api/v1/planets/{planet_name}/explain` (the same endpoint and response) return two new fields. Both are always present in the response and may be `null`; neither is required in the OpenAPI schema, and the existing fields are unchanged (`ml_priority_score` is still the production model's score, rounded to 0.1; only its schema description was reworded to say so).
  - `served_priority_score` (number or `null`): the score the catalog serves for this planet (its `priority_score`, rounded to 0.01). For planets labelled as JWST targets this is an out-of-fold score; for every other planet it is the production model's score. `null` when the catalog row has no score (no ranked planet today).
  - `explains_served_score` (boolean or `null`): `true` when the score this explanation breaks down (the production model's, unrounded) is within 0.01 points of the served score, `false` when it is not, and `null` when `served_priority_score` is `null`. With a model that passes the startup consistency check, `false` occurs only for planets labelled as JWST targets, whose out-of-fold score can differ from the production model's.
  - The comparison endpoint (`GET /api/v1/planets/compare-explain`) does not return these fields.
  - Compared with the published API (commit `665eec8`), these two fields and the removal of the promote and rollback endpoints (see Removed) are the only changes to the OpenAPI schema.

### Removed

- **Breaking (API):** `POST /api/v1/models/registry/promote/{version}` and `POST /api/v1/models/registry/rollback`, and the `ADMIN_TOKEN` setting that enabled them. The API runs several worker processes, and each loads the active artifact version when it starts, so a promotion over HTTP changed only the process that received it and the workers then served different versions. Both paths now answer `404`; `ADMIN_TOKEN` is ignored. A model now goes live only by deployment: `python -m app.pipeline build` (or `python -m app.pipeline registry rollback`) updates `artifacts/active_version.txt`, the change is reviewed and committed, and the API is redeployed or restarted, after which every worker serves the new version. `GET /api/v1/models/registry/active` reports the pointer (`active_version`), the version the answering process serves (`served_version`) and whether they agree (`serving_matches_pointer`).

### Fixed

- API: size-class filter bypassed other filters (500 for gas giants); 500 when observed targets were included; wildcard search; `split=val` returned the test report; cached registry responses; internal error text in responses; unbounded request IDs; meaningless scores served for non-transiting planets.
- Interface: the Explorer loads again (it asked for more rows than the API allows); distances were parsecs labelled as light-years; invented radar values for real planets removed; preset planet values now come from the API; unknown values are shown as unknown; labels are no longer called confirmed or verified.
- Label review: only rows with a validated time system, known uncertainty and provenance can be approved (none today); an earlier rejection blocks approval. A row must equal the row computed again from the cached archive data. Training and the CI benchmark use a verified row only with its approval in the review log.
- Artifact: the record of `planets.parquet` was out of date since 2026-11-02; corrected after reproducing the file (docs/ARTIFACT_PROVENANCE.md). Missing values no longer turn into 0.0 in a rebuild.
- Interface: planets are called "not labelled" instead of "unobserved"; promotional wording removed.
- Model registry: integrity check works on a clean clone; missing checksums no longer count as valid; host names are not recorded.
- MAST label builder: write-path, dry-run, identity, uncertainty and timing repairs (ADR 0006 revision). Not run against live archives.

### Corrections to earlier entries (kept below as written)

- 0.2.0 "sub-millisecond", "p50 ~3.6 ms", "zero-downtime": not measured or tested.
- 0.2.0 "TreeSHAP": the served model uses Linear SHAP.
- 0.2.0 "+104.6 % ... p < 0.001": computed on unverified labels and correlated folds.
- 0.3.0 "empirical load test": no load test has been run. `render.yaml` and the root `netlify.toml` no longer exist on `main`.
- 0.1.0 "Chen & Kipping": the implemented relation differs (see README).

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
