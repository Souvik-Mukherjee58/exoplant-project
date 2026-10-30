# ADR 0001: Grouped Cross-Validation Over Temporal Split for Model Selection

- **Status**: Accepted
- **Date**: 2026-10-28
- **Deciders**: ML & Astronomical Engineering Team

---

## Context & Problem Statement

When evaluating machine learning ranking models on astronomical catalogs, two critical failure modes arise:

1. **Host-Level Feature Leakage**: Multi-planet systems (e.g., TRAPPIST-1 with 7 planets, L 98-59 with 4 planets) share identical host star features: distance to Earth, stellar radius, mass, metallicity, and infrared brightness ($J/K$ magnitudes). Under naive random train/test splits, sibling planets appear on both sides of the evaluation boundary, allowing models to trivially memorize host star identifiers and inflating Average Precision to unrealistic levels ($AP > 0.85$).
2. **Temporal Split Sample Starvation**: In historical forward-in-time temporal evaluation (train $\le 2017$, validation $2018-2021$, test $\ge 2022$), exoplanet discoveries after 2021 contain **exactly one confirmed JWST transmission target** ($n_{pos} = 1$, LP 791-18 d) among 938 candidates. A test set with $N=1$ positive target is statistically unviable for ranking evaluation: metrics like Average Precision and NDCG oscillate binary-wise (0 or 1), bootstrap confidence intervals span $[0.0, 1.0]$, and statistical significance testing is mathematically impossible.

---

## Decision

1. **Primary Protocol**: We adopt **5-Fold `StratifiedGroupKFold` across 5 random seeds (25 folds total)**, grouped strictly by host star (`hostname`).
   - Every multi-planet system is held out together: no host star or sibling planet ever crosses train and test folds.
   - Stratification balances the 32 positive targets proportionally across all folds ($~6.4$ positive targets per test fold).
   - Metrics are reported with 1,000-resample bootstrap 95% confidence intervals and per-fold paired difference tests against baseline metrics.
2. **Secondary Protocol**: Leave-One-Host-Out (LOHO) cross-validation across all 24 positive host stars, recording target rank within the complete 4,643-planet pool.
3. **Temporal Split Role**: The historical temporal split is retained strictly as a qualitative sanity check and is explicitly **never used for model selection or hyperparameter tuning**.

---

## Consequences

### Positive
- Completely eliminates astronomical feature leakage across multi-planet systems.
- Provides statistically sound, narrow 95% bootstrap confidence intervals for ranker comparison.
- Evaluates true generalized performance on newly discovered planetary systems around unseen stars.

### Negative / Trade-offs
- Group cross-validation is computationally more intensive than a single static split, requiring training and evaluating 25 separate fold models per candidate algorithm.

