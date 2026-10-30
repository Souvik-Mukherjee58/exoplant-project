# ExoSignal Scientific Ranking Evaluation Report

## Executive Summary
- **Eligible Candidates Pool**: 4643 transmission-eligible planets
- **Confirmed Positive Targets**: 32 planets across 24 host stars
- **Positive Pre-test Probability**: 0.69%
- **Primary Protocol**: 5-Fold StratifiedGroupKFold across 5 Random Seeds (25 Folds), grouped by host star (`hostname`)
- **Primary Ranking Metric**: Average Precision (AP) with 95% Bootstrap CI (1000 resamples)
- **Selected Production Model**: **Logistic Regression (Variant A - All Features)** (AP: 0.4597, Recall@50: 0.7459)

---

## 1. Primary Protocol Leaderboard (StratifiedGroupKFold, 25 Folds)
*Grouped by host star (`hostname`) to ensure multi-planet siblings (e.g. TRAPPIST-1, L 98-59) never cross folds. Metrics reported as mean ± std [95% bootstrap CI].*

| Model | AP (PR-AUC) | NDCG@25 | Precision@10 | Precision@25 | Recall@25 | Recall@50 | Recall@100 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression (Variant A - All Features)** | 0.4597 ± 0.2476 | 0.6017 ± 0.2491 | 0.3200 ± 0.2227 | 0.1776 ± 0.1137 | 0.6708 ± 0.2573 | 0.7459 ± 0.2428 | 0.8590 ± 0.2042 |
| **Logistic Regression (Variant B - Raw Features Only)** | 0.3700 ± 0.1794 | 0.5167 ± 0.2030 | 0.2920 ± 0.1958 | 0.1600 ± 0.1037 | 0.6212 ± 0.2671 | 0.7100 ± 0.2587 | 0.8299 ± 0.2188 |
| **Model A (LightGBM - All Features)** | 0.2673 ± 0.1986 | 0.3988 ± 0.2133 | 0.2240 ± 0.1656 | 0.1472 ± 0.1078 | 0.5564 ± 0.2569 | 0.7634 ± 0.2253 | 0.8467 ± 0.1864 |
| **Distance-Only Baseline** | 0.2555 ± 0.1811 | 0.3701 ± 0.1742 | 0.2480 ± 0.2193 | 0.1472 ± 0.1228 | 0.5484 ± 0.2438 | 0.6148 ± 0.2250 | 0.7095 ± 0.2188 |
| **TSM-Only Baseline** | 0.2247 ± 0.1355 | 0.3902 ± 0.1653 | 0.2240 ± 0.1176 | 0.1184 ± 0.0560 | 0.5439 ± 0.2278 | 0.5479 ± 0.2226 | 0.6622 ± 0.2212 |
| **Heuristic Composite (ExoSignal)** | 0.2011 ± 0.1828 | 0.3559 ± 0.2192 | 0.1640 ± 0.1852 | 0.1408 ± 0.1068 | 0.5386 ± 0.2348 | 0.5520 ± 0.2427 | 0.6327 ± 0.2220 |
| **ESM-Only Baseline** | 0.1955 ± 0.1730 | 0.3034 ± 0.2102 | 0.1600 ± 0.1265 | 0.0704 ± 0.0470 | 0.3480 ± 0.2676 | 0.4123 ± 0.2569 | 0.5848 ± 0.2437 |
| **Model B (LightGBM - Raw Features Only)** | 0.1912 ± 0.1109 | 0.3243 ± 0.1454 | 0.1520 ± 0.1100 | 0.1232 ± 0.0838 | 0.5254 ± 0.2592 | 0.6771 ± 0.2755 | 0.7833 ± 0.2381 |
| **Random Baseline** | 0.0104 ± 0.0074 | 0.0025 ± 0.0121 | 0.0000 ± 0.0000 | 0.0016 ± 0.0078 | 0.0057 ± 0.0280 | 0.0702 ± 0.1992 | 0.1084 ± 0.2061 |

---

## 2. Paired Statistical Comparison vs. TSM-Only Baseline (Kempton et al. 2018)
*Per-fold paired differences (Model − TSM) with 95% percentile bootstrap CI (1000 resamples). Stated as 'no significant difference' if the 95% CI spans zero.*

| Model | Mean Diff (AP) | 95% Bootstrap CI (AP) | Conclusion vs TSM |
| :--- | :---: | :---: | :--- |
| **Logistic Regression (Variant A - All Features)** | +0.2350 | [+0.1443, +0.3275] | **statistically significant improvement** |
| **Logistic Regression (Variant B - Raw Features Only)** | +0.1453 | [+0.0684, +0.2231] | **statistically significant improvement** |
| **Model A (LightGBM - All Features)** | +0.0426 | [-0.0396, +0.1291] | **no significant difference** |
| **Distance-Only Baseline** | +0.0308 | [-0.0704, +0.1339] | **no significant difference** |
| **TSM-Only Baseline** | +0.0000 | [+0.0000, +0.0000] | **no significant difference** |
| **Heuristic Composite (ExoSignal)** | -0.0236 | [-0.1231, +0.0814] | **no significant difference** |
| **ESM-Only Baseline** | -0.0292 | [-0.1021, +0.0487] | **no significant difference** |
| **Model B (LightGBM - Raw Features Only)** | -0.0335 | [-0.0938, +0.0255] | **no significant difference** |
| **Random Baseline** | -0.2143 | [-0.2712, -0.1642] | **statistically significant underperformance** |

---

## 3. Secondary Protocol: Leave-One-Host-Out (LOHO) Cross-Validation
*Evaluates rank of held-out positive targets across all 24 positive host stars among all 4643 eligible candidate planets.*

| Model | Median Rank | Mean Rank | Top 1% (≤ 47) | Top 5% (≤ 233) | Top 10% (≤ 465) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression (Variant A - All Features)** | 41.5 | 209.2 | 56.2% | 81.2% | 84.4% |
| **Distance-Only Baseline** | 61.0 | 376.4 | 46.9% | 62.5% | 71.9% |
| **Model A (LightGBM - All Features)** | 61.0 | 147.6 | 43.8% | 81.2% | 90.6% |
| **Logistic Regression (Variant B - Raw Features Only)** | 62.0 | 234.5 | 43.8% | 75.0% | 84.4% |
| **Heuristic Composite (ExoSignal)** | 90.0 | 683.7 | 21.9% | 56.2% | 65.6% |
| **Model B (LightGBM - Raw Features Only)** | 102.5 | 278.3 | 15.6% | 65.6% | 78.1% |
| **TSM-Only Baseline** | 341.0 | 609.4 | 31.2% | 46.9% | 56.2% |
| **ESM-Only Baseline** | 574.0 | 1216.0 | 25.0% | 34.4% | 46.9% |
| **Random Baseline** | 2506.0 | 2278.6 | 0.0% | 6.2% | 12.5% |

---

## 4. Forward-in-Time Sanity Check (n_pos=1)
> [!NOTE]
> **Status**: `sanity_check_only`
> **Methodology Note**: Strictly a forward-in-time sanity check (n_pos=1 in test split, LP 791-18 d). Never used for model selection or statistical inference.

- **Train Split (Discovery ≤ 2017)**: 2791 planets
- **Validation Split (2018–2021)**: 914 planets
- **Test Split (≥ 2022)**: 938 planets (Contains 1 positive target: **LP 791-18 d**)

| Model | Test P@10 | Test NDCG@10 | Test MAP | Test PR-AUC |
| :--- | :---: | :---: | :---: | :---: |
| **Heuristic Composite (ExoSignal)** | 0.0000 | 0.0000 | 0.0294 | 0.0294 |
| **Distance-Only Baseline** | 0.0000 | 0.0000 | 0.0222 | 0.0222 |
| **Logistic Regression (Variant A - All Features)** | 0.0000 | 0.0000 | 0.0094 | 0.0094 |
| **Model A (LightGBM - All Features)** | 0.0000 | 0.0000 | 0.0020 | 0.0020 |
| **Random Baseline** | 0.0000 | 0.0000 | 0.0017 | 0.0017 |
| **TSM-Only Baseline** | 0.0000 | 0.0000 | 0.0014 | 0.0014 |
| **ESM-Only Baseline** | 0.0000 | 0.0000 | 0.0013 | 0.0013 |
| **Model B (LightGBM - Raw Features Only)** | 0.0000 | 0.0000 | 0.0011 | 0.0011 |

---

## 5. Limitations & Astrophysical Caveats
1. **Small Sample Size ($n = 32$)**: The total number of confirmed JWST atmospheric transmission spectroscopy targets approved through peer-reviewed Cycle 1–3 programs is currently limited to 32 exoplanets.
2. **Label = Human Selection**: Labels represent human telescope allocation committee (TAC) program approvals rather than physical observation ground truth.
3. **Target Selection Bias**: Known targets are heavily biased toward bright host stars (low infrared J/K magnitudes), nearby distances, and systems with precisely measured transit ephemerides.
