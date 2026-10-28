# ExoSignal Model Evaluation Benchmark Report

## Operational Evaluation Summary
- **Evaluation Era**: Out-of-Time Test Set (Discovery Years >= 2022)
- **Train Set Size**: 2791 planets (Discovery Years <= 2017)
- **Validation Set Size**: 914 planets (2018 - 2021)
- **Test Set Size**: 938 planets (2022 - 2026)
- **Evaluation Positive Rate**: 0.11%
- **Primary Optimization Metric**: `precision@10`

### Metric Justification
> Observing time on flagship space observatories (JWST/HST) is strictly capacity-constrained. Precision@10 measures the fraction of top-10 proposed targets that yield viable spectroscopic data, directly minimizing wasted multimillion-dollar observing proposals.

## Leaderboard Comparison (7 Models)

| Model | Precision@5 | Precision@10 | Precision@20 | Recall@10 | Recall@25 | Recall@50 | NDCG@10 | MAP | PR-AUC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **TSM-Only Baseline** | 0.0000 | 0.0000 | 0.0500 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0588 | 0.5005 |
| **ESM-Only Baseline** | 0.0000 | 0.0000 | 0.0500 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0588 | 0.5005 |
| **Heuristic Composite (ExoSignal)** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0294 | 0.0147 |
| **Model A (LightGBM - All Features)** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0286 | 0.0139 |
| **Distance-Only Baseline** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0222 | 0.0111 |
| **Model B (LightGBM - Raw Features Only)** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0152 | 0.5053 |
| **Random Baseline** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0017 | 0.0008 |

## Scientific Ground Truth Formulation
Ground truth targets are determined by:
1. **NASA / STScI Approved JWST Atmospheric Transmission Spectroscopy Programs** (Cycles 1, 2, 3, and GTO accepted transmission spectroscopic follow-up targets).
2. Evaluated strictly on transmission-eligible planets to ensure physical observation feasibility.
