# ExoSignal Model Evaluation Benchmark Report

## Operational Evaluation Summary
- **Evaluation Era**: Out-of-Time Test Set (Discovery Years >= 2022)
- **Train Set Size**: 3594 planets (Discovery Years <= 2017)
- **Validation Set Size**: 1300 planets (2018 - 2021)
- **Test Set Size**: 1557 planets (2022 - 2026)
- **Evaluation Positive Rate**: 24.15%
- **Primary Optimization Metric**: `precision@10`

### Metric Justification
> Observing time on flagship space observatories (JWST/HST) is strictly capacity-constrained. Precision@10 measures the fraction of top-10 proposed targets that yield viable spectroscopic data, directly minimizing wasted multimillion-dollar observing proposals.

## Leaderboard Comparison

| Model | Precision@5 | Precision@10 | Recall@10 | NDCG@10 | MAP | PR-AUC |
| --- | --- | --- | --- | --- | --- | --- |
| **Distance-Only Baseline** | 1.0000 | 1.0000 | 0.0266 | 0.4649 | 0.5907 | 0.5901 |
| **ExoSignal v1 Composite** | 1.0000 | 1.0000 | 0.0266 | 0.7434 | 0.4984 | 0.4975 |
| **Supervised LightGBM LTR** | 0.8000 | 0.9000 | 0.0239 | 0.3879 | 0.9825 | 0.9822 |
| **ESI Heuristic Ranker** | 0.0000 | 0.4000 | 0.0106 | 0.1985 | 0.3014 | 0.2995 |
| **Random Baseline** | 0.2000 | 0.2000 | 0.0053 | 0.1324 | 0.2345 | 0.2328 |

## Scientific Ground Truth Formulation
Ground truth targets are determined by:
1. **Kempton et al. (2018)** Transmission Spectroscopy Metric (TSM) ($TSM \ge 10$ for rocky/temperate, $TSM \ge 80$ for sub-Neptunes).
2. **NASA / STScI Approved JWST Atmospheric Programs** (Cycles 1, 2, and 3 accepted spectroscopic follow-up targets).
