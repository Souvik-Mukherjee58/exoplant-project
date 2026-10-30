# ADR 0004: Out-of-Fold (OOF) Scoring for Known Targets in the User Interface

- **Status**: Accepted
- **Date**: 2026-10-28
- **Deciders**: ML & Product Engineering Team

---

## Context & Problem Statement

ExoSignal displays both unobserved candidate targets for future JWST proposals and confirmed JWST targets from Cycle 1–3 programs (e.g., TRAPPIST-1 e, K2-18 b, WASP-121 b).

If a single global production model trained on the entire dataset scores these confirmed targets in the UI:
1. **Optimistic Train-Set Reporting Bias**: The model has already seen these 32 positive targets during training. Presenting in-sample ranks gives an exaggerated, dishonest impression of real-world discovery capability.
2. **Reviewer Distrust**: Astrobiologists and machine learning reviewers cannot determine whether high target scores stem from genuine physical inductive bias or in-sample label memorization.

---

## Decision

1. **Out-of-Fold Precomputation**: During the 25-fold grouped cross-validation build process, predictions for every known JWST target are recorded strictly from the fold models where their host star was **held out from training**.
2. **Columnar Schema Invariant**: Both `oof_priority_score` and `oof_ml_rank` are stored directly in `planets.parquet`.
3. **Dual UI Ranking Views**:
   - **Candidate Discovery View** (`GET /api/v1/top-targets`, `GET /api/v1/planets`): Focuses on *unobserved candidate targets* for future observing cycles, with `exclude_observed=true` by default.
   - **Model Validation View** (`GET /api/v1/validation/known-targets`): Displays confirmed JWST targets strictly using their **out-of-fold ranks and scores**.

---

## Consequences

### Positive
- Guarantees complete transparency and scientific honesty in UI metrics.
- Confirms that the model's high prioritization of targets like TRAPPIST-1 e (OOF Rank: 4) and LHS 1140 b (OOF Rank: 9) reflects true out-of-sample discovery ability on unseen host stars.
- Eliminates potential for misleading astronomical claims.

### Negative / Trade-offs
- Requires maintaining dual scoring columns (`priority_score` vs `oof_priority_score`) in the catalog schema and frontend types.

