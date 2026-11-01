# JWST Ground-Truth Label Verification Protocol

This document defines the formal ground-truth label verification protocol, column specifications, scientific criteria, and review workflow for the ExoSignal JWST spectroscopic follow-up reference catalog.

---

## 1. Ground-Truth Invariant & Scientific Scope

The core objective of ExoSignal is identifying which known exoplanets should be targeted for **atmospheric transmission spectroscopy** with the James Webb Space Telescope (JWST).

### Scientific Invariant
> **Only confirmed transiting exoplanets observed in verified atmospheric transmission spectroscopy modes under approved STScI programs qualify as ground-truth positives (`is_jwst_target = True`, `ground_truth_binary = 1`).**

Non-transiting planets, secondary eclipse thermal emission observations, full-orbit thermal phase curves, and pure transit timing/exomoon searches are strictly excluded from transmission training labels.

---

## 2. Reference Catalog Schema (`jwst_transmission_targets.csv`)

The reference dataset located at `backend/data/reference/jwst_transmission_targets.csv` contains the following audited columns:

| Column | Data Type | Default | Description |
|:---|:---:|:---:|:---|
| `planet_name` | String | - | Canonical IAU exoplanet name matching NASA Exoplanet Archive composite table (`pl_name`). |
| `program_id` | String / Int | `""` | Official STScI approved program ID. Cleared (`""`) if verification failed. Replacement IDs must not be invented without verification. |
| `cycle` | Integer | - | JWST observing cycle (e.g. `1`, `2`, `3`). |
| `mode` | String | - | Instrument and spectroscopic configuration (e.g. `NIRSpec/PRISM`, `NIRISS/SOSS`, `NIRCam`, `MIRI/LRS`). |
| `source_url` | String | `""` | Direct public STScI program URL (`https://www.stsci.edu/jwst/science-execution/program-information?id={PID}`). Cleared (`""`) if verification failed. |
| `observation_type` | String | `"unknown"` | Observational regime: `transmission`, `emission`, `phase_curve`, `transit_timing`, or `unknown`. Only `transmission` rows can be positive labels. |
| `verified` | Boolean | `False` | Must be `True` if and only if transiting geometry and transmission mode have been verified by a reviewer. |
| `needs_review` | Boolean | `True` | Flags rows requiring manual auditing, resolution of failed IDs, or verification against literature. |
| `notes` | String | `""` | Verification audit details, PIs, citations, or error status (e.g. `"ID failed verification"`). |

---

## 3. Label Extraction Rules in Code (`app/ml/ground_truth.py`)

In `backend/app/ml/ground_truth.py`, `get_verified_jwst_targets()` strictly enforces:

```python
# 1. Missing columns raise ValueError
if "verified" not in df.columns or "observation_type" not in df.columns:
    raise ValueError(
        "Reference catalog is missing required columns 'verified' and/or 'observation_type'. "
        "Please update backend/data/reference/jwst_transmission_targets.csv."
    )

# 2. Labels require both verified=True AND observation_type="transmission"
is_verified = df["verified"].apply(_parse_bool)
is_transmission = df["observation_type"].astype(str).str.strip().str.lower() == "transmission"
verified_mask = is_verified & is_transmission

# 3. Any unverified or non-transmission rows trigger a loud warning to stdout
unverified_df = df[~verified_mask]
if len(unverified_df) > 0:
    print_unverified_targets_warning(unverified_df)
```

---

## 4. Pipeline Minimum Label Threshold Invariant (`app/pipeline.py`)

Supervised learning-to-rank models (Logistic Regression Variant A and LightGBM) require sufficient positive instances for stratified cross-validation.
In `backend/app/pipeline.py`:

```python
n_pos = int(gt_df["ground_truth_binary"].sum()) if "ground_truth_binary" in gt_df.columns else 0
if n_pos < 15:
    raise RuntimeError(
        f"Pipeline stopped: Fewer than 15 verified labels exist (found {n_pos}). "
        "Please finish the label review in backend/data/reference/jwst_transmission_targets.csv "
        "(set verified=True and observation_type='transmission') before running the pipeline."
    )
```

The pipeline will **never silently train on an empty or tiny positive label set**.

---

## 5. Manual Review Process & Workflow

To review and verify targets:
1. Open [LABEL_REVIEW.md](file:///a:/Claude%20Code/exosignal/reports/LABEL_REVIEW.md) to inspect candidate targets.
2. For targets with `"ID failed verification"`, look up the host star in official STScI Cycle 1, 2, 3, or 4 approved programs lists.
3. Check the proposal abstract and observing template:
   - Must be **transiting exoplanet transmission spectroscopy** (primary eclipse).
   - If secondary eclipse thermal emission, mark `observation_type = emission, verified = False`.
   - If full-orbit thermal phase curve, mark `observation_type = phase_curve, verified = False`.
4. Record your review decision in `reports/LABEL_REVIEW.md` (`checked_by`, `date`, `decision`).
5. Update `backend/data/reference/jwst_transmission_targets.csv`:
   - Set `verified = True`
   - Set `observation_type = transmission`
   - Set `needs_review = False`
   - Add verified `program_id`, `source_url`, and citation in `notes`.
6. Run the test suite:
   ```bash
   cd backend && python -m pytest tests/test_labels_strict.py -v
   ```
