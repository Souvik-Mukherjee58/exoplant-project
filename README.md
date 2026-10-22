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

## Running Tests

```bash
cd backend
python -m pytest
```

## System Overview & Engineering Highlights

- **Stateless REST API:** Built with FastAPI, providing deterministic responses, Pydantic validation schemas, and structured logging.
- **Fast Event Loop:** CPU-bound analytical data processing runs via FastAPI threadpools without blocking asynchronous I/O.
- **Interactive Scientific Visualizations:** Recharts integration for PCA feature-space projection, empirical score histograms, and habitable zone categorization.
- **Parametric Filtering & Exact Matching:** Server-side normalized exact-match lookups (`/api/v1/planets/{planet_name}`) and parameterized range queries.

## License

This project is for research and educational purposes.