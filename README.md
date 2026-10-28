# ExoSignal — Data-Driven Exoplanet Follow-Up Target Prioritization Platform

ExoSignal analyzes astronomical archive parameters and computes multi-criteria follow-up rankings to assist researchers in prioritizing exoplanets for atmospheric characterization and spectroscopic study.

## Scientific Disclaimer

> Target priority scores represent comparative observational utility for spectroscopic follow-up, based on physical characteristics, host star parameters, insolation flux, and observational accessibility. Scores do not represent a probability of extraterrestrial life or intelligence.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entrypoint
│   │   ├── config.py            # Application configuration
│   │   ├── api/
│   │   │   └── v1.py            # API routes (REST endpoints)
│   │   ├── services/
│   │   │   ├── data_ingestion.py# Data loading service
│   │   │   ├── data_cleaning.py # Normalization and validation
│   │   │   ├── data_processor.py# Pipeline orchestration & cache
│   │   │   └── feature_engineering.py # Derived physical features
│   │   ├── ml/
│   │   │   └── anomaly_detection.py   # Unsupervised outlier scoring
│   │   └── scoring/
│   │       └── priority_scorer.py     # Multi-criteria target scoring
│   ├── data/
│   │   ├── raw/                 # Ingested archive datasets
│   │   └── processed/           # Processed catalog and metadata
│   ├── tests/                   # Automated backend test suite
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx              # Application shell and routing
│   │   ├── App.css              # Theme tokens
│   │   ├── index.css            # Scientific design system & utilities
│   │   ├── main.jsx             # React entrypoint
│   │   ├── pages/               # View components (Analytics, Explorer, PlanetDetail, etc.)
│   │   ├── services/            # API client layer
│   │   ├── hooks/               # Custom data-fetching hooks
│   │   └── utils/               # Numerical and scientific formatters
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Quick Start

### Backend Service

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive API documentation is accessible at `http://localhost:8000/docs`.

### Frontend Application

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

## Machine Learning Systems Architecture

ExoSignal provides an end-to-end machine learning engineering framework for exoplanet spectroscopic follow-up prioritization:

1. **Astronomical Ground Truth Benchmark**:
   - Formulates targets against published peer-reviewed metrics: **Transmission Spectroscopy Metric (TSM)** and **Emission Spectroscopy Metric (ESM)** (*Kempton et al., PASP 2018*), with Chen & Kipping (2017) mass-radius fallback relations.
   - Restricts transmission spectroscopy ranking strictly to transiting planets with valid stellar and planetary measurements (`eligible_for_transmission = true`).
   - Evaluates models on an out-of-time temporal holdout split (Discovery $\le 2017$ train, $2018-2021$ val, $\ge 2022$ test) against confirmed JWST Cycle 1–3 Guaranteed Time & General Observers programs.
   - Comprehensive comparative evaluation across **7 benchmark rankers**:
     1. Random Baseline
     2. Distance-Only Ranker
     3. TSM-Only Baseline (Kempton et al. 2018)
     4. ESM-Only Baseline (Kempton et al. 2018)
     5. Heuristic Composite Scorer (ExoSignal)
     6. Model A (LightGBM Ranker with 21 physical + proxy features)
     7. Model B (LightGBM Ranker with 18 raw physical features, isolating proxy leakage)
   - Evaluation metrics: **Precision@5/10/20**, **Recall@10/25/50**, **NDCG@10**, **MAP**, and **PR-AUC**.

2. **Supervised Learning-to-Rank (LTR)**:
   - LightGBM ranking model trained over **21 physically motivated astrophysical features** (composite transmission SNR proxy, geometric transit depth, atmospheric scale height proxy, insolation flux, bulk density, host star infrared magnitude, and distance attenuation).
   - Generates unified, consistent ranking scores (`priority_score` and `priority_rank`), with `heuristic_habitability_score` provided as an auxiliary metric.

3. **In-Process Analytical Query Engine (DuckDB & Parquet)**:
   - Zero-copy columnar queries over immutable versioned Parquet catalog storage (`artifacts/{version}/planets.parquet`).
   - Parameterized SQL execution with predicate pushdown and secondary indexing, achieving **empirical P50 query latencies of ~3.6ms (P95 < 8ms)** without external database network hops.
   - Measure empirical query performance directly via:
     ```bash
     python scripts/bench_query.py --iterations 200
     ```
   - Fully decoupled application lifecycle via FastAPI `lifespan` context manager.

4. **TreeSHAP Explainability Layer**:
   - Exact local feature attribution via **TreeSHAP** (*Lundberg et al., Nature Machine Intelligence 2020*), leveraging native C++ LightGBM execution (`pred_contrib=True`).
   - Enforces the additive conservation invariant: $\sum_{i=1}^{21} \phi_i + \text{Base Value} = \text{Predicted Margin}$ to machine floating point precision ($< 10^{-14}$).
   - **Pairwise Differential Attribution**: Computes $\Delta \phi_i = \phi_i(A) - \phi_i(B)$ explaining ranking reversals between any two candidate targets.
   - Interactive dual-direction waterfall charts in React displaying positive drivers, negative barriers, physical units, and ML rank shifts.

5. **Model Registry & Cryptographic Provenance**:
   - Local-first immutable model registry tracking artifact lineage, training hyperparameters, temporal splits, dataset fingerprints, and offline evaluation metrics.
   - Cryptographic SHA256 integrity validation to detect model tampering or silent disk corruption.
   - Atomic zero-downtime model promotion and one-click rollback with audit trail.
   - Built-in CLI and REST API endpoints (`/api/v1/models/registry/versions`, `/active`, `/validate/{version}`, `/compare`, `/promote/{version}`, `/rollback`).

6. **Production Hardening, Observability & Containerization**:
   - Multi-stage Docker builds for backend (Python 3.11 slim) and frontend (Node 20 build + Nginx Alpine static serving).
   - Docker Compose orchestration with automated healthchecks, volume mounts, and reverse proxying.
   - Structured JSON logging with per-request correlation IDs (`X-Request-ID`), execution timing (`X-Process-Time`), and slow-request monitoring.
   - Operational monitoring endpoints: `/health` (system state, active model version, catalog counts) and `/metrics` (DuckDB, SHAP, registry subsystem health).
   - 5-job GitHub Actions CI/CD pipeline featuring **ML benchmark regression gates** validating leaderboard structure across all 7 rankers.

## Quick Start with Docker (Recommended)

Run the full-stack application (FastAPI backend + Vite/Nginx frontend + in-process DuckDB) with a single command:

```bash
docker compose up --build
```

- **Frontend Application**: `http://localhost:3000`
- **Backend API & Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`
- **Metrics**: `http://localhost:8000/metrics`

## Running Tests

ExoSignal includes a comprehensive **95-test automated suite** covering transit eligibility constraints, honest ground truth definitions, one-score one-rank consistency, flexible search and SHAP retrieval, LTR ranking benchmarks, DuckDB analytical engine performance, TreeSHAP mathematical invariants, model registry lifecycle, structured logging, and container readiness:

```bash
cd backend
python -m pytest -v
```

## Running the Build Pipeline & Model Registry

To compile new immutable versioned artifacts from the raw catalog and manage model deployments:

```bash
cd backend
# Build, score, extract features, fit LTR model, run benchmarks, and auto-register
python -m app.pipeline build

# Inspect active artifact manifest and catalog statistics
python -m app.pipeline inspect

# Run 7-model ranking benchmark leaderboard across train/val/test splits
python -m app.pipeline evaluate --split test

# Model Registry Operations
python -m app.pipeline registry list                       # List all registered versions & metrics
python -m app.pipeline registry validate                   # Validate SHA256 integrity of active artifacts
python -m app.pipeline registry compare --version-a v1_2026-10-23 --version-b v1_2026-10-22
python -m app.pipeline registry rollback --reason "Audit failure"
```

## License

This project is for research and educational purposes.