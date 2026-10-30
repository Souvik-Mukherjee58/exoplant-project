# ExoSignal Model Card: Spectroscopic Follow-Up Prioritization Ranker

Following the standardized model reporting framework (*Mitchell et al., FAT* 2019*).

---

## 1. Model Details

- **Model Identifier**: ExoSignal Production Ranker (Variant A)
- **Model Version**: `v1_2026-10-29`
- **Model Type**: Regularized Logistic Regression with Balanced Class Weighting ($L_2$, $C=1.0$) over standardized, log-transformed astrophysical features.
- **Explainability Engine**: Exact Linear/TreeSHAP attribution via native analytic formulation, satisfying additive conservation $\sum_{i=1}^{21} \phi_i + \text{Base} = \text{Score}$ to machine precision.
- **Maintainer**: Souvik Mukherjee (`Souvik-Mukherjee58`)
- **License**: MIT / Research & Educational Use

---

## 2. Intended Use

### Primary Intended Use
- Assisting astronomical researchers, observing teams, and Telescope Allocation Committees (TAC) in prioritizing known transiting exoplanets for atmospheric characterization via **transmission spectroscopy** with the James Webb Space Telescope (JWST) and future observatories (e.g., Ariel, HWO).
- Providing interpretable, physically motivated ranking scores and local feature attributions (TreeSHAP waterfalls) explaining why individual targets rank higher or lower.

### Target Users
- Exoplanet astronomers, observational astrophysicists, and instrument science teams.

---

## 3. Out-of-Scope & Prohibited Use Cases

> [!CAUTION]
> **Scientific & Astrobiological Disclaimer**
> ExoSignal scores represent **comparative observational utility for transmission spectroscopy** based on transit geometry, host star infrared brightness, and atmospheric scale height.
> 
> - **NOT an Extraterrestrial Life Detector**: High scores do **not** indicate evidence or probability of extraterrestrial life, biosignatures, or technological intelligence.
> - **NOT a Habitability Index**: While habitability status is tracked as an auxiliary physical parameter, hot gas giants (e.g., WASP-121 b, HD 209458 b) often achieve the highest observational SNR while being completely uninhabitable.
> - **NOT for Non-Transiting Targets**: Non-transiting planets discovered via radial velocity or direct imaging cannot undergo transmission spectroscopy and are strictly excluded.

---

## 4. Training Data & Preprocessing

- **Data Source**: NASA Exoplanet Archive (`ps` composite parameters table).
- **Ground Truth Reference**: Confirmed JWST Cycle 1–3 approved transmission spectroscopy programs (32 positive planets across 24 host stars; positive prevalence = 0.69%).
- **Eligibility Filter**: Restricted strictly to transiting planets with valid stellar and planetary measurements ($N = 4,643$ eligible out of 6,451 raw catalog entries).
- **Feature Space (21 Features)**:
  - *Planetary parameters*: $R_p$ (planet radius), $M_p$ (planet mass, Chen & Kipping fallback), $P$ (orbital period), $a$ (semi-major axis), $T_{eq}$ (equilibrium temperature).
  - *Stellar parameters*: $T_{eff}$ (effective temperature), $R_*$ (stellar radius), $M_*$ (stellar mass), $[Fe/H]$ (metallicity), $d$ (distance), $J$ and $K$ band infrared magnitudes.
  - *Astrophysical proxies*: Geometric transit depth proxy $(R_p/R_*)^2$, atmospheric scale height proxy $(T_{eq}/g)$, bulk density, insolation flux, infrared brightness, distance attenuation, and transmission SNR proxy.
- **Transformation**: Robust log-transformations on power-law physical quantities ($\log(d)$, $\log(R_p)$, $\log(T_{eq})$), median imputation on secondary missing values, and standard scaling.

---

## 5. Quantitative Evaluation & Metrics

Evaluated across **25 host-grouped folds** (`StratifiedGroupKFold`, 5 seeds $\times$ 5 folds) grouped by host star (`hostname`):

| Evaluation Metric | Baseline (TSM-Only) | ExoSignal Production Model | Improvement | 95% Bootstrap CI |
|:---|:---:|:---:|:---:|:---:|
| **Average Precision (AP / PR-AUC)** | 0.2247 | **0.4597** | **+0.2350** | [+0.1443, +0.3275] |
| **NDCG@25** | 0.3902 | **0.6017** | **+0.2115** | [+0.1117, +0.3125] |
| **Precision@10** | 0.2240 | **0.3200** | **+0.0960** | [+0.0160, +0.1840] |
| **Recall@50** | 0.5479 | **0.7459** | **+0.1980** | [+0.0940, +0.3020] |
| **LOHO Median Rank** | 341.0 | **41.5** (Top 0.89%) | **-299.5 ranks** | — |

---

## 6. Known Biases & Limitations

1. **Severe Target Imbalance ($n_{pos} = 32$)**: Only 32 confirmed JWST transmission spectroscopy targets exist across Cycles 1–3, representing $0.69\%$ positive class prevalence.
2. **Human Committee Selection Bias**: Positive ground truth labels reflect human Telescope Allocation Committee (TAC) proposal approvals rather than raw atmospheric signal ground truth.
3. **Observational Malmquist Bias**: Targets are heavily skewed toward nearby ($d < 100\text{ pc}$), infrared-bright host stars ($K < 10$) with large transit depths.
4. **Unlabeled Candidates $\neq$ Negative Targets**: Planets not yet approved for JWST time may possess exceptional spectroscopic utility that has not yet been proposed.

