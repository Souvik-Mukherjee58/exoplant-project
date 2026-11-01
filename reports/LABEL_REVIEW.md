# JWST Ground-Truth Label Review & Verification Log

This document serves as the formal manual audit log for JWST transmission spectroscopy ground-truth labels in ExoSignal.
As required by the scientific protocol (see [README_LABELS.md](file:///a:/Claude%20Code/exosignal/backend/data/reference/README_LABELS.md)), every candidate exoplanet target must be audited against official STScI program execution records and NASA MAST archives before being marked `verified=True` and `observation_type="transmission"` in `backend/data/reference/jwst_transmission_targets.csv`.

---

## 1. Review Instructions

1. **Verify Observing Geometry & Mode**:
   - **Accept (`transmission`)**: Confirmed primary transit transmission spectroscopy (starlight filtering through the planetary terminator).
   - **Reject (`emission`)**: Secondary eclipse dayside thermal emission measurements (occultation behind the star).
   - **Reject (`phase_curve`)**: Full-orbit thermal phase curve observations.
   - **Reject (`transit_timing`)**: Exomoon searches or transit timing variation (TTV) measurements without transmission spectroscopy.
2. **Verify Space Telescope Science Institute (STScI) Program ID**:
   - Cross-reference official program listings at `https://www.stsci.edu/jwst/science-execution/program-information?id={PID}`.
   - Check that the host star name appears in the published STScI proposal target list.
3. **Record Human Review Decision**:
   - Fill in your name/ID in `checked_by`, the date in `date`, and the final decision (`APPROVED: transmission`, `REJECTED: emission`, `REJECTED: phase_curve`, or `REJECTED: invalid_id`).
   - For approved rows, update `backend/data/reference/jwst_transmission_targets.csv` to set `verified=True` and `observation_type=transmission`.
   - The ML training pipeline requires **at least 15 verified transmission labels** to train supervised ranking models.

---

## 2. Target Review Table

| planet | program_id | source_url | checked_by | date | decision |
|:---|:---:|:---|:---:|:---:|:---:|
| TRAPPIST-1 b | 1201 | https://www.stsci.edu/jwst/science-execution/program-information?id=1201 | | | [Pending Review] |
| TRAPPIST-1 c | 1201 | https://www.stsci.edu/jwst/science-execution/program-information?id=1201 | | | [Pending Review] |
| TRAPPIST-1 d | 2589 | https://www.stsci.edu/jwst/science-execution/program-information?id=2589 | | | [Pending Review] |
| TRAPPIST-1 e | 2589 | https://www.stsci.edu/jwst/science-execution/program-information?id=2589 | | | [Pending Review] |
| TRAPPIST-1 f | 2589 | https://www.stsci.edu/jwst/science-execution/program-information?id=2589 | | | [Pending Review] |
| TRAPPIST-1 g | 2589 | https://www.stsci.edu/jwst/science-execution/program-information?id=2589 | | | [Pending Review] |
| TRAPPIST-1 h | 2589 | https://www.stsci.edu/jwst/science-execution/program-information?id=2589 | | | [Pending Review] |
| LHS 1140 b | | | | | [ID failed verification - needs program lookup] |
| L 98-59 b | 2512 | https://www.stsci.edu/jwst/science-execution/program-information?id=2512 | | | [Pending Review] |
| L 98-59 c | 2512 | https://www.stsci.edu/jwst/science-execution/program-information?id=2512 | | | [Pending Review] |
| L 98-59 d | 2512 | https://www.stsci.edu/jwst/science-execution/program-information?id=2512 | | | [Pending Review] |
| GJ 1132 b | | | | | [ID failed verification - was PID 1995 (cosmology)] |
| GJ 1214 b | | | | | [ID failed verification - was PID 1803 (phase_curve)] |
| GJ 436 b | | | | | [ID failed verification - needs program lookup] |
| GJ 3470 b | | | | | [ID failed verification - needs program lookup] |
| LP 791-18 d | | | | | [ID failed verification - needs program lookup] |
| TOI-270 d | | | | | [ID failed verification - needs program lookup] |
| K2-18 b | 2722 | https://www.stsci.edu/jwst/science-execution/program-information?id=2722 | | | [Pending Review] |
| 55 Cnc e | 1952 | https://www.stsci.edu/jwst/science-execution/program-information?id=1952 | | | [Pending Review] |
| WASP-39 b | 1366 | https://www.stsci.edu/jwst/science-execution/program-information?id=1366 | | | [Pending Review] |
| WASP-96 b | 2734 | https://www.stsci.edu/jwst/science-execution/program-information?id=2734 | | | [Pending Review] |
| WASP-121 b | | | | | [ID failed verification - was PID 1729 (phase_curve)] |
| WASP-76 b | | | | | [ID failed verification - needs program lookup] |
| WASP-43 b | 1366 | https://www.stsci.edu/jwst/science-execution/program-information?id=1366 | | | [Pending Review] |
| WASP-18 b | | | | | [ID failed verification - needs program lookup] |
| WASP-80 b | | | | | [ID failed verification - was PID 2114 (supernovae)] |
| WASP-107 b | | | | | [ID failed verification - needs program lookup] |
| HD 209458 b | | | | | [ID failed verification - needs program lookup] |
| HD 189733 b | 1633 | https://www.stsci.edu/jwst/science-execution/program-information?id=1633 | | | [Pending Review] |
| HAT-P-18 b | | | | | [ID failed verification - needs program lookup] |
| HAT-P-26 b | | | | | [ID failed verification - was PID 1743 (Gl 486 b)] |
| HAT-P-32 b | | | | | [ID failed verification - needs program lookup] |
| TOI-700 d | | | | | [ID failed verification - transit timing / exomoon] |
| TOI-849 b | | | | | [ID failed verification - emission spectroscopy] |
| GJ 367 b | | | | | [ID failed verification - thermal phase curve] |
