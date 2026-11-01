# ADR 0005: Systematic Ground-Truth Label Verification and Non-Transmission Exclusion

- **Status**: Accepted
- **Date**: 2026-10-31
- **Deciders**: Astrophysical Machine Learning & Systems Architecture Team

---

## Context & Problem Statement

Supervised machine learning for exoplanet spectroscopic follow-up prioritizes targets for atmospheric transmission spectroscopy with the James Webb Space Telescope (JWST). The fidelity of this prioritization depends entirely on the accuracy and physical consistency of the ground-truth positive label set.

### 1. Why Hand-Curated Lists Failed
Initial versions of the reference catalog relied on hand-compiled lists of JWST exoplanet targets. Technical auditing revealed two critical failure modes in this approach:

1. **Human Transcription and Attribution Errors**:
   - **GJ 1132 b**: Listed with Program ID `1995`. When audited against Space Telescope Science Institute (STScI) records, Program 1995 was revealed to be an unrelated extragalactic cosmology study (*"Answering the Most Important Problem in Cosmology Today: Is the Tension in the Hubble Constant Real?"*, PI: Riess).
   - **WASP-80 b**: Listed with Program ID `2114`. STScI records show Program 2114 is a supernova investigation (*"MIR Spectroscopy of Type Ia Supernovae: The Key to Unlocking their Explosions and Element Production"*, PI: Johansson).
   - **HAT-P-26 b**: Listed with Program ID `1743`, which actually targets the terrestrial exoplanet Gl 486 b (*"Constraining the Atmosphere of the Terrestrial Exoplanet Gl486b"*, PI: Mansfield).
2. **Astrophysical Regime Conflation (Label Pollution)**:
   - Hand-curated lists treated *any* JWST exoplanet observation as a positive label.
   - JWST exoplanet characterization spans distinct observational techniques:
     - **Primary Transit (Transmission Spectroscopy)**: Measures starlight filtering through the planetary terminator annulus. Detectability scales with atmospheric scale height:
       $$\Delta \delta \propto \frac{2 R_p H}{R_*^2} = \frac{2 R_p k_B T_{eq}}{\mu g R_*^2}$$
     - **Secondary Eclipse (Thermal Emission)**: Measures dayside planetary thermal flux prior to and after occultation behind the host star (e.g. 55 Cnc e, WASP-18 b, TOI-849 b). Detectability scales with dayside thermal emission:
       $$\text{ESM} \propto \frac{B_\lambda(T_{day})}{B_\lambda(T_*)} \left(\frac{R_p}{R_*}\right)^2$$
     - **Full-Orbit Phase Curves**: Measures longitudinal day-night thermal contrast across full orbits (e.g. GJ 1214 b, WASP-121 b, WASP-43 b, GJ 367 b).
     - **Transit Timing Variations (TTV) / Exomoon Searches**: Pure timing measurements without atmospheric transmission spectra (e.g. TOI-700 d).
   - Conflating secondary eclipse emission and phase curves with transmission spectroscopy severely degraded learning-to-rank performance: rankers learned to penalize high-TSM temperate sub-Neptunes and reward ultra-short-period, tidally locked furnaces with high thermal flux.

---

## Decision

We replace unverified hand-curated lists with an automated verification harness coupled with mandatory human review:

1. **Automated STScI & MAST Scraping (`scripts/verify_jwst_reference.py` & `scripts/build_jwst_labels_from_mast.py`)**:
   - Queries STScI public program APIs and NASA Mikulski Archive for Space Telescopes (MAST).
   - Validates HTTP reachability, program title, and verifies whether the host star name appears in the published observation target list.
   - Scrapes instrument configuration (NIRSpec/PRISM, NIRISS/SOSS, NIRCam, MIRI/LRS).
2. **Explicit Catalog Schema with Audit Metadata**:
   - `backend/data/reference/jwst_transmission_targets.csv` enforces 9 columns:
     `planet_name,program_id,cycle,mode,source_url,observation_type,verified,needs_review,notes`
   - Default values are `verified = False` and `needs_review = True`.
   - Any row where host star confirmation fails or observation type is non-transmission (`phase_curve`, `emission`, `transit_timing`) has `program_id` and `source_url` cleared (`""`) and `notes = "ID failed verification"`. No replacement IDs may be invented without verification.
3. **Mandatory Human Domain Review (`reports/LABEL_REVIEW.md`)**:
   - Automated scripts cannot autonomously interpret scientific proposal nuances (e.g., whether an ERS program's multi-instrument allocation includes a transmission spectrum).
   - Reviewers inspect proposal abstracts and record findings in `reports/LABEL_REVIEW.md` (`planet, program_id, source_url, checked_by, date, decision`).
4. **Strict Runtime Code Invariants**:
   - In `backend/app/ml/ground_truth.py:get_verified_jwst_targets()`:
     - Missing `verified` or `observation_type` columns immediately raise `ValueError`.
     - Positive labels are strictly defined as:
       $$\text{verified} == \text{True} \quad \land \quad \text{observation\_type} == \text{"transmission"}$$
     - Any unverified row triggers a prominent loud warning to stdout.
   - In `backend/app/pipeline.py`:
     - If fewer than 15 verified transmission labels exist ($n_{\text{pos}} < 15$), the build pipeline halts with `RuntimeError` requiring completion of the review log.

---

## Consequences

### Positive
- **Zero Label Hallucination**: Eliminates phantom program IDs (such as cosmology and supernova proposals).
- **Physical Purity**: Ensures supervised ranking models optimize strictly for atmospheric transit detectability.
- **Fail-Safe Operation**: Prevents the ML pipeline from silently training on an empty or inadequately verified label set.
- **Full Traceability**: Every verified label traces directly to a specific STScI approved program URL and human audit log entry.

### Trade-offs & Mitigations
- In the initial unreviewed state, live reference targets default to `verified=False`, halting the pipeline until domain review is completed. Test fixtures (`fixture_jwst_reference.csv`) are isolated to test algorithmic execution without weakening live production auditing.
