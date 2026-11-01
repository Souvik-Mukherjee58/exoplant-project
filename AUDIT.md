# ExoSignal End-to-End Technical & Engineering Audit

**Audit Role**: Strict SDE-1 / MLE-1 Hiring Manager (Funded Startup)  
**Date of Audit**: November 2, 2026  
**Repository**: `exosignal`  
**Audit Standard**: Strict Pass/Fail Checklist with File:Line Evidence — No Speculation, No Invented Metrics  

---

## 1. Executive Summary & Overall Hiring Assessment

- **Overall Engineering & Scientific Score**: **8.5 / 10** (Role: SDE-1 / MLE-1)
- **Hiring Verdict**: **Strong Hire (High Priority)**. The repository demonstrates exceptional technical maturity, mathematical depth, architectural clarity, and test rigor far exceeding typical SDE-1/MLE-1 candidates.
- **Top 3 High-Leverage Changes to Reach 10 / 10**:
  1. **Frontend Code-Splitting & Bundle Optimization**: The initial JavaScript bundle (`dist/assets/index-*.js`) is 981 kB minified (275 kB gzip), exceeding Vite's 500 kB budget. Lazily importing Three.js (`Planet3DVisualizer`) and Recharts via `React.lazy()` / `Suspense` will reduce the initial page bundle to under 200 kB.
  2. **Purge Residual Static UI Placeholders & Connect Radar to API**: Remove residual hardcoded latency strings (`"6.8ms P50 latency (170ms P50 under concurrent load)"` in `About.jsx:91`, `Home.jsx:1156,1215`, and `Methodology.jsx:138`), and bind the 5-axis spectroscopic radar chart in `Home.jsx:216-224` to dynamic planet parameters rather than static demo values.
  3. **Execute Live k6 Load Test & Add Latency Regression Guard**: Run `scripts/run_loadtest.sh` against a live staging container to populate `reports/LOADTEST.md` with empirical p50/p95/p99 numbers, and wire a latency budget assertion into the CI pipeline.

---

## 2. Pass / Fail Verification Checklist

| # | Audit Item | Status | Key Metric / Verification | File:Line Evidence |
|:---:|:---|:---:|:---|:---|
| **1** | **Clean Clone & Setup** | **PASS** | Repository is self-contained. Parquet/model binaries tracked via Git LFS. Container definition runs non-root. | `docker-compose.yml:1-55`, `.gitattributes:1-2`, `backend/Dockerfile:1-60` |
| **2** | **Backend Test Suite** | **PASS** | **188 passed** (0 failures, 1 Starlette deprecation warning) in 57.05s across 16 test modules. | `backend/tests/` |
| **3** | **Backend Linter & Formatter** | **PASS** | `ruff check .` passed with 0 errors; `ruff format --check` clean. | `backend/app/`, `backend/tests/` |
| **4** | **Backend Strict Typing** | **PASS** | `mypy app/ml app/scoring` passed with 0 issues in 9 source files. | `backend/app/ml/`, `backend/app/scoring/` |
| **5** | **Scripts Linter** | **PASS** | `ruff check scripts/` passed with 0 errors across all 7 utility scripts. | `scripts/` |
| **6** | **Frontend Unit & Component Tests** | **PASS** | **23 passed** across 7 test suites in 7.96s (Vitest + Testing Library). | `frontend/src/test/` |
| **7** | **Frontend Linter** | **PASS** | `npm run lint` (ESLint) passed with 0 errors and 0 warnings. | `frontend/src/` |
| **8** | **Frontend Production Build** | **PASS** | `vite build` completed successfully in 6.67s; HTML, CSS, and JS chunks emitted. | `frontend/dist/` |
| **9** | **README Table Freshness** | **PASS** | `python scripts/render_readme_results.py --check` passes cleanly. | `scripts/render_readme_results.py:1-125` |
| **10** | **Non-Transiting Filtering** | **PASS** | Exactly 0 non-transiting or transmission-ineligible planets have `priority_rank` or `ml_rank`. | `planets.parquet`, `backend/tests/test_ranking_unique.py:122-138` |
| **11** | **Strict Label Gating** | **PASS** | Only `verified == True` AND `observation_type == 'transmission'` rows used; pipeline halts if $< 15$. | `backend/app/ml/ground_truth.py:94-109`, `backend/app/pipeline.py:118-123` |
| **12** | **Out-of-Fold (OOF) Scoring** | **PASS** | Known targets strictly receive out-of-fold CV scores to eliminate optimistic evaluation bias. | `backend/app/services/query_engine.py:475-477`, `backend/tests/test_ranking_unique.py:107-120` |
| **13** | **Statistical Rigor & CIs** | **PASS** | All metrics report $n_{pos}$, 95% bootstrap CIs, paired differences, and nested CV outer-fold bounds. | `backend/artifacts/v1_2026-10-29/evaluation.json:3,18-21,84-89`, `reports/NESTED_CV.md:22-34` |
| **14** | **Deterministic Ranking** | **PASS** | `priority_rank` and `unobserved_rank` are strictly unique and contiguous (1..N) with multi-key tie-breakers. | `backend/tests/test_ranking_unique.py:26-78` |

---

## 3. Clean Clone & Local Setup Audit

| Instruction / Command | Expected Behavior | Actual Behavior | Verdict | File:Line Evidence |
|:---|:---|:---|:---:|:---|
| `git clone <url>` | Clones repository | Clones tracking branch `main`. | **PASS** | Self-contained git repository. |
| Git LFS Assets | Downloads `planets.parquet` & `*.joblib` | Managed by Git LFS. If Git LFS is missing, files clone as pointer stubs. | **WARN** | `.gitattributes:1-2` tracks binaries. README should explicitly note `git lfs install`. |
| `cd backend && pip install -r requirements.txt` | Installs runtime dependencies | Installs FastAPI, DuckDB, scikit-learn, LightGBM, Pandas, NumPy. | **PASS** | `backend/requirements.txt:1-14`. |
| `cd backend && pytest` | Executes backend test suite | Runs 188 tests. Requires packages in `requirements-dev.txt` (`pytest-cov`, `astroquery`, `ruff`, `mypy`). | **WARN** | README line 121 omits `requirements-dev.txt`. Developer must install `requirements-dev.txt` to run full CI tests. |
| `cd frontend && npm install && npm run dev` | Starts Vite dev server | Vite starts cleanly on `http://localhost:3000`. | **PASS** | `frontend/package.json:1-40`. |
| `docker compose up --build` | Zero-config full-stack containerization | Backend and frontend containers define non-root execution, healthchecks, and reverse proxy. Docker daemon must be running. | **PASS** | `docker-compose.yml:1-55`, `backend/Dockerfile:1-60`, `frontend/Dockerfile:1-39`. |

---

## 4. Test, Lint, and Build Results

### Backend
- **Pytest**: 188 passed, 1 warning in 57.05s.
- **Ruff Linter**: All checks passed (0 errors, 0 warnings across `app/`, `tests/`, and `scripts/`).
- **Mypy Type Checking**: Success (0 issues in 9 source files across `app/ml` and `app/scoring`).

### Frontend
- **ESLint**: Clean pass (0 errors, 0 warnings across all `.js` and `.jsx` files).
- **Vitest**: 7 passed test suites, 23 passed tests in 7.96s.
- **Vite Build**: Built in 6.67s; emitted `dist/index.html` (1.10 kB), `dist/assets/index-*.css` (16.53 kB), and `dist/assets/index-*.js` (981.13 kB).

---

## 5. Claim Audit: Factual Claims in README, Docs, and UI

| # | Public Claim | Claimed Value | Verified Artifact / Code Truth | Verdict | File:Line Evidence |
|:---:|:---|:---:|:---|:---:|:---|
| 1 | **Average Precision (AP)** | **0.4597** [0.3599, 0.5687] | 25-fold CV AP: `0.4597`, bootstrap 95% CI: `[0.3599, 0.5687]`. | **SUPPORTED** | `backend/artifacts/v1_2026-10-29/evaluation.json:16,18-21` |
| 2 | **AP Improvement vs TSM** | **+104.6%** ($+0.2350$) | Baseline AP: `0.2247`. Ratio: $(0.4597 - 0.2247)/0.2247 = +104.58\%$. Paired 95% CI: `[+0.1443, +0.3275]`, $p < 0.001$. | **SUPPORTED** | `backend/artifacts/v1_2026-10-29/evaluation.json:84-89` |
| 3 | **Recall@50** | **74.6%** ($74.59 \pm 24.28\%$) | Recovers $74.59\%$ of positive targets in top 50 ranks. | **SUPPORTED** | `backend/artifacts/v1_2026-10-29/evaluation.json:22` |
| 4 | **Leave-One-Host-Out Median Rank** | **41.5** | LOHO cross-validation yields median rank 41.5 across positive systems. | **SUPPORTED** | `backend/artifacts/v1_2026-10-29/evaluation.json:52` |
| 5 | **Catalog Population** | **6,451 raw / 4,643 eligible** | Composite archive rows: 6,451; transmission-eligible: 4,643. | **SUPPORTED** | `manifest.json:7,10`, `planets.parquet` |
| 6 | **Feature Space** | **21 features** | Exactly 21 standardized physical features engineered. | **SUPPORTED** | `backend/app/ml/ltr_model.py:27-51`, `ltr_feature_importance.json` |
| 7 | **Linear SHAP Conservation** | **Additive closed-form** | Exact analytic linear SHAP formulation guarantees zero residual attribution error ($< 10^{-14}$). | **SUPPORTED** | `backend/app/ml/explainability.py:90-115`, `backend/tests/test_production_readiness.py:252-254` |
| 8 | **Zero Leakage Protocol** | **StratifiedGroupKFold (25 folds)** | Multi-planet host stars never split across train/test folds. | **SUPPORTED** | `backend/app/ml/evaluation.py:158-195`, `docs/adr/0001-grouped-cv-over-temporal-split.md` |
| 9 | **UI Concurrent Load Latency Claim** | `"6.8ms P50 latency (170ms P50 under concurrent load per reports/LOADTEST.md)"` | UI text asserts this benchmark, but `reports/LOADTEST.md` currently holds placeholders pending user execution of `scripts/run_loadtest.sh`. | **UNSUPPORTED / RESIDUAL MOCK** | `frontend/src/pages/About.jsx:91-92`, `frontend/src/pages/Home.jsx:1156,1215`, `frontend/src/pages/Methodology.jsx:138-139` |
| 10 | **Use of Adjectives** | `"production"`, `"real-time"`, `"state-of-the-art"` | "Production" is strictly scoped to the active model registry artifact and environment variable. "Real-time" and "state-of-the-art" have 0 occurrences. | **SUPPORTED** | `frontend/src/`, `README.md`, `docs/` |

---

## 6. Number Audit: UI Statistics Tracing to API / Artifacts

```
UI Component / Screen                      Tracing Source                     Integrity Status
─────────────────────────────────────────────────────────────────────────────────────────────
Home.jsx: Catalog Population               GET /api/v1/analysis (DuckDB)      PASS (Dynamic 6,451)
Home.jsx: Model Quality AP & Recall        GET /api/v1/models/benchmark       PASS (Dynamic 0.4597, 0.746)
Home.jsx: Feature Importance (|Coeff|)     GET /api/v1/models/feature-imp.    PASS (Dynamic signed bars)
Home.jsx: P50 Latency Card                 Text literal "< 10 ms"             WARN (Static text literal)
Home.jsx: Radar Chart Demonstration Data   Hardcoded demonstration values     WARN (Trappist: 94, etc.)
Home.jsx: Architecture Pipeline Subtitle   "6.8ms P50 / 170ms P50"            FAIL (Residual static text)
Home.jsx: Golden Benchmark Targets         GET /api/v1/validation/known-targ. PASS (Dynamic OOF Ranks)
Home.jsx: Unobserved Recommendations       GET /api/v1/top-targets            PASS (Dynamic unobserved)
TopTargets.jsx: Top 10 Candidates          GET /api/v1/top-targets            PASS (Dynamic percentile)
TopTargets.jsx: Known JWST Positives       GET /api/v1/validation/known-targ. PASS (Dynamic OOF scores)
PlanetDetail.jsx: Physical Parameters      GET /api/v1/planets/{name}         PASS (Dynamic DuckDB)
PlanetDetail.jsx: Linear SHAP Waterfall    GET /api/v1/explain/{name}         PASS (Dynamic log-odds)
Analytics.jsx: Parameter Distributions     GET /api/v1/analysis               PASS (Dynamic DuckDB)
ModelRegistry.jsx: Active Model Integrity  GET /api/v1/models/registry/active PASS (Dynamic SHA-256)
Methodology.jsx: Component Weights         GET /api/v1/methodology/weights    PASS (Dynamic 35/30/15/10/10)
About.jsx & Methodology.jsx: Engine Stack  "6.8ms P50 / 170ms P50"            FAIL (Residual static text)
```

---

## 7. Science & ML Rigor Audit

### 1. Are Non-Transiting Planets Ever Ranked?
- **Audit Query**: Executed DuckDB SQL query against `backend/artifacts/v1_2026-10-29/planets.parquet`:
  ```sql
  SELECT COUNT(planet_name) FROM 'planets.parquet' 
  WHERE (is_transiting = false OR eligible_for_transmission = false) 
    AND (priority_rank IS NOT NULL OR ml_rank IS NOT NULL);
  ```
- **Result**: Exactly **`0`**. All 1,808 non-transiting or ineligible planets have `priority_rank = NaN` and `ml_rank = NaN`.
- **Verdict**: **PASS** (`backend/tests/test_ranking_unique.py:122-138`).

### 2. Do Labels Use Only Verified Transmission Rows?
- **Code Enforcement**: `backend/app/ml/ground_truth.py:94-109` strictly requires `verified == True` and `observation_type.lower() == "transmission"`. Any missing column raises `ValueError`.
- **Halt Guard**: `backend/app/pipeline.py:118-123` halts execution with a `RuntimeError` if fewer than 15 verified labels exist.
- **Reference Table vs Fixture**: Live reference table (`backend/data/reference/jwst_transmission_targets.csv`) contains 35 candidate rows currently awaiting human review (`verified=False, needs_review=True`). Benchmark evaluations use 26 verified targets in `backend/tests/fixtures/fixture_jwst_reference.csv`.
- **Verdict**: **PASS** (`backend/tests/test_labels_strict.py:1-95`).

### 3. Are UI Scores for Known Targets Out-of-Fold (OOF)?
- **Evaluation Isolation**: `backend/app/services/query_engine.py:476` sorts known targets strictly by `oof_ml_rank ASC NULLS LAST`.
- **Score Integrity**: For all labelled planets, `priority_score` equals `oof_priority_score` within machine tolerance.
- **Verdict**: **PASS** (`backend/tests/test_ranking_unique.py:107-120`, `frontend/src/test/GoldenSection.test.jsx:1-60`).

### 4. Does the Evaluation Report Include $n_{positives}$ and 95% CIs?
- **Reporting**: `backend/artifacts/v1_2026-10-29/evaluation.json` explicitly logs `"n_positives": 32`, bootstrap confidence intervals (`"ap_ci95": [0.3599, 0.5687]`), paired difference intervals vs TSM (`[+0.1443, +0.3275]`), and nested cross-validation bounds (`reports/NESTED_CV.md`).
- **Caveats**: `EVALUATION.md:93-94` explicitly documents that bootstrap intervals across repeated folds are approximate and references the 5-fold host-grouped nested CV as the honest estimate.
- **Verdict**: **PASS** (`backend/tests/test_reports_consistency.py:1-190`).
