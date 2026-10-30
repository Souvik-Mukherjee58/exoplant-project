# ADR 0002: Model Selection — Regularized Linear Ranking Over Complex GBDT

- **Status**: Accepted
- **Date**: 2026-10-28
- **Deciders**: ML & Astronomical Engineering Team

---

## Context & Problem Statement

We evaluated 7 candidate ranking architectures across the 25-fold grouped cross-validation protocol on the 4,643 transmission-eligible exoplanet candidate pool with 32 confirmed positive targets ($0.69\%$ positive class prevalence):
1. Random Baseline
2. Distance-Only Baseline
3. TSM-Only Baseline (*Kempton et al., PASP 2018*)
4. ESM-Only Baseline (*Kempton et al., PASP 2018*)
5. Heuristic Composite Scorer (ExoSignal)
6. Complex GBDT (LightGBM Ranker with 21 features)
7. Regularized Logistic Regression with Balanced Class Weighting (Variant A & B)

Unconstrained tree-based models (LightGBM) suffered from severe overfitting in this extreme high-class-imbalance regime ($n_{pos} = 32$):
- LightGBM Model A achieved an AP of only $0.2673 \pm 0.1986$ ($95\%$ CI $[-0.0396, +0.1291]$ vs. TSM baseline), failing to establish a statistically significant improvement over the standard astronomical baseline.
- Decision trees created non-monotonic step boundaries where minor physical parameter perturbations caused arbitrary rank swings.

---

## Decision

We select **Regularized Logistic Regression (Variant A - All Features, $L_2$, $C=1.0$, `class_weight='balanced'`)** as the active production ranking model (`ltr_model.joblib`).

### Key Validation Findings:
1. **Statistically Superior Performance**:
   - Primary Ranking AP: **$0.4597 \pm 0.2476$** (vs. TSM $0.2247$, Mean Diff $+0.2350$, $95\%$ bootstrap CI $[+0.1443, +0.3275]$, $p < 0.001$).
   - Recall@50: **$0.7459 \pm 0.2428$** (captures 74.6% of all confirmed targets within the top 50 ranked candidates).
   - LOHO Median Rank: **41.5** (Top $0.89\%$ of the catalog; LightGBM: 61.0, TSM: 341.0).
2. **Monotonic Astrophysical Inductive Bias**:
   - Linear coefficients guarantee monotonic sensitivity (e.g., nearer targets and brighter host stars strictly increase priority, without tree-splitting artifacts).
3. **Exact Mathematical Explainability**:
   - Supports exact closed-form SHAP feature attribution: $\phi_i = w_i (x_i - \mathbb{E}[x_i])$, guaranteeing that $\sum \phi_i + \text{Base Value} = \text{Predicted Margin}$ to machine floating-point precision ($< 10^{-14}$) with zero sampling variance.

---

## Consequences

### Positive
- Robust generalization on unseen planetary systems without tree overfitting.
- $+104.6\%$ improvement in Average Precision over the peer-reviewed TSM baseline.
- Instant, deterministic TreeSHAP attribution calculations ($< 0.1\text{ ms}$).

### Negative / Trade-offs
- Linear models cannot capture high-order nonlinear feature interactions without explicit feature engineering (mitigated by including composite physical interaction proxies such as transit depth and atmospheric scale height).

