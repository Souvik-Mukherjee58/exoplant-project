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

ExoSignal was redesigned from the ground up as a production-grade ML systems project for exoplanet spectroscopic follow-up prioritization:

1. **Astronomical Ground Truth Benchmark**:
   - Formulates targets against published peer-reviewed metrics: **Transmission Spectroscopy Metric (TSM)** and **Emission Spectroscopy Metric (ESM)** (*Kempton et al., PASP 2018*), with Chen & Kipping (2017) mass-radius fallback relations.
   - Evaluates models on an out-of-time temporal holdout split (Discovery $\le 2017$ train, $2018-2021$ val, $\ge 2022$ test) against confirmed JWST Cycle 1–3 Guaranteed Time & General Observers programs.
   - Rigorous evaluation metrics: **NDCG@10**, **MAP**, **Precision@10**, and **PR-AUC**.

2. **Supervised Learning-to-Rank (LTR)**:
   - LightGBM GBDT ranking model trained over **21 physically motivated astrophysical features** (composite transmission SNR proxy, geometric transit depth, atmospheric scale height proxy, insolation flux, bulk density, host star infrared magnitude, and distance attenuation).
   - Achieves superior ranking utility over heuristics, with feature gains dominated by transmission spectroscopic SNR (82.5% gain) and planetary radius (6.5% gain).

3. **In-Process Analytical Query Engine (DuckDB & Parquet)**:
   - Zero-copy columnar queries over immutable versioned Parquet catalog storage (`artifacts/{version}/planets.parquet`).
   - Parameterized SQL execution with predicate pushdown and secondary B-Tree indexing, achieving **P50 query latencies of ~4.05ms** without database network hops.
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
   - Multi-stage, non-root Docker builds for backend (Python 3.11 slim) and frontend (Node 20 build + Nginx Alpine static serving).
   - Production Docker Compose orchestration with automated healthchecks, volume mounts, and Nginx reverse proxying.
   - Structured JSON logging with per-request correlation IDs (`X-Request-ID`), execution timing (`X-Process-Time`), and slow-request monitoring.
   - Production monitoring endpoints: `/health` (system state, active model version, catalog counts) and `/metrics` (DuckDB, SHAP, registry subsystem health).
   - 5-job GitHub Actions CI/CD pipeline featuring **ML benchmark regression gates** enforcing automated quality bars on NDCG@10, MAP, and Precision@10.

## Quick Start with Docker (Recommended)

Run the entire full-stack application (FastAPI backend + Vite/Nginx frontend + in-process DuckDB) with a single command:

```bash
docker compose up --build
```

- **Frontend Application**: `http://localhost:3000`
- **Backend API & Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`
- **Metrics**: `http://localhost:8000/metrics`

## Running Tests

ExoSignal includes a comprehensive **92-test automated suite** covering astrophysical accuracy, LTR ranking benchmarks, DuckDB analytical engine performance, TreeSHAP mathematical invariants, model registry lifecycle, structured logging, and container readiness:

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

# Run 5-model ranking benchmark leaderboard across train/val/test splits
python -m app.pipeline evaluate --split test

# Model Registry Operations
python -m app.pipeline registry list                       # List all registered versions & metrics
python -m app.pipeline registry validate                   # Validate SHA256 integrity of active artifacts
python -m app.pipeline registry compare --version-a v1_2026-10-23 --version-b v1_2026-10-22
python -m app.pipeline registry rollback --reason "Audit failure"
```

## License

This project is for research and educational purposes.