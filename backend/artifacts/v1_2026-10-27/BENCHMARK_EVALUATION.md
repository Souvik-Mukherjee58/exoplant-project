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

## Leaderboard Comparison

| Model | Precision@5 | Precision@10 | Recall@10 | NDCG@10 | MAP | PR-AUC |
| --- | --- | --- | --- | --- | --- | --- |
| **Random Baseline** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0017 | 0.0008 |
| **Distance-Only Baseline** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0222 | 0.0111 |
| **ESI Heuristic Ranker** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0556 | 0.0278 |
| **ExoSignal v1 Composite** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0294 | 0.0147 |
| **Supervised LightGBM LTR** | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0286 | 0.0139 |

## Scientific Ground Truth Formulation
Ground truth targets are determined by:
1. **Kempton et al. (2018)** Transmission Spectroscopy Metric (TSM) ($TSM \ge 10$ for rocky/temperate, $TSM \ge 80$ for sub-Neptunes).
2. **NASA / STScI Approved JWST Atmospheric Programs** (Cycles 1, 2, and 3 accepted spectroscopic follow-up targets).
