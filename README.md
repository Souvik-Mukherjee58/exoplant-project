# ExoSignal — AI-Assisted Exoplanet Technosignature Target Prioritization System

ExoSignal uses publicly available astronomical data and machine learning to identify
and rank exoplanet systems that may be especially valuable targets for future
technosignature observations.

## Important Scientific Disclaimer

> The priority score does not represent the probability of extraterrestrial life or
> intelligence. It is a computational ranking intended to identify targets that may
> warrant further scientific investigation.

## Project Structure

```
exosignal/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py             # Configuration settings
│   │   ├── api/
│   │   │   └── v1.py             # API routes
│   │   ├── services/
│   │   │   ├── data_ingestion.py # Data loading service
│   │   │   ├── data_cleaning.py  # Data cleaning service
│   │   │   └── feature_engineering.py # Feature engineering
│   │   ├── ml/
│   │   │   └── anomaly_detection.py   # ML anomaly detection
│   │   ├── scoring/
│   │   │   └── priority_scorer.py     # Priority scoring
│   │   └── utils/
│   ├── data/
│   │   ├── raw/                 # Raw downloaded data
│   │   └── processed/           # Processed data
│   ├── tests/                   # Test files
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx             # Main App component
│   │   ├── App.css             # Styling
│   │   ├── main.jsx            # Entry point
│   │   ├── components/          # Reusable components
│   │   ├── pages/               # Page components
│   │   ├── services/            # API services
│   │   ├── hooks/              # Custom hooks
│   │   └── utils/              # Utilities
│   ├── index.html
│   └── package.json
└── README.md
```

## Quick Start

### Backend

```bash
cd exosignal/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd exosignal/frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

## Features

- Data ingestion from NASA Exoplanet Archive (CSV/API)
- Data cleaning and standardization
- Feature engineering (Earth similarity, HZ status, observational accessibility)
- ML-based anomaly detection (Isolation Forest + LOF)
- Scientifically interpretable priority scoring
- Interactive web dashboard
- Planet comparison and ranking

## Methodology

See the Methodology page in the dashboard for full details.

## Scientific Limitations

- Priority scores are computational rankings, not probability estimates
- Missing data is handled explicitly, not fabricated
- HZ estimates are approximate
- Anomaly scores detect unusual patterns, not extraterrestrial activity

## License

This project is for research and educational purposes only.