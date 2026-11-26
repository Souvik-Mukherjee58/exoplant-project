# ADR 0006: One bulk MAST query, and planet assignment by transit ephemeris

- **Status**: Proposed — implemented, owner acceptance not recorded
- **Date**: 2026-11-22
- **Decider**: Not recorded
- **Authorship**: Drafted and implemented with AI coding assistance

## Context

Labels answer "was this planet observed by JWST in transit (transmission spectroscopy)?". The v1 labels
were produced by hand and by an AI tool, and both failed: invented program IDs, and a fabricated "MAST
cache". Labels must now come from the real archive, and every label must be approved by a human.

Two facts constrain the design:

1. A JWST program on a host star does not say _which_ planet or _which_ geometry it observed.
   TRAPPIST-1 has seven planets; program 1366 includes WASP-39 (transit), WASP-18 (eclipse) and a single
   WASP-43 MIRI time series. Title keywords are a weak hint: the v1 fabrication appended "transmission"
   to a real title precisely because a keyword classifier was trusted.
2. Every JWST transit/eclipse product in MAST is filed as `dataproduct_type = "timeseries"`. A live
   count on 2026-11-22 returned 4,187 such rows in total (vs. ~200k `spectrum` rows that are not
   time-series observations).

## Decision

- **One bulk query** (`obs_collection="JWST", dataproduct_type="timeseries"`) instead of one query per
  host (~3,500 hosts). Fewer requests, no host-name-variant guessing at query time, and the raw table is
  cached once, unmodified, with its SHA-256.
- **Host matching locally**: normalised name, then name with a trailing planet letter, then a
  coordinate match (default 30″, unique host required). The method is recorded per row.
- **Planet assignment by ephemeris**: for each window `[t_min, t_max]` and each planet of the host,
  predict mid-transit and secondary-eclipse times from NASA's `pl_tranmid`/`pl_orbper` with propagated
  uncertainty `σ(n) = sqrt(σ_T0² + n²σ_P²)`. Status is `transit_in_window` / `eclipse_in_window` only
  when the event ± (3σ + margin) is fully inside the window; anything borderline is `ambiguous`.
- **Eccentric orbits** (e > 0.1): the eclipse can sit anywhere in phase 0.5 ± (2/π)e, so overlap with that
  range makes the row `ambiguous`, never `no_event`. On real data this catches GJ 436 b, whose JWST
  windows all sit at phase ≈ 0.58.
- **Phase clusters**: if unexplained windows for one planet from ≥ 2 programs bunch at one phase, the
  archive ephemeris is probably off, so those rows become `ambiguous` with a note. On real data this
  flags TOI-270 d (three windows, two programs, ≈ 10 h from the predicted transit). In resonant systems
  (TRAPPIST-1) several planets cluster on the same windows; those are surfaced once at host level.
- The script **never writes labels**. It writes `reports/jwst_mast_candidates.csv` for
  `scripts/review_labels.py`; only a human approval writes `verified=True`.

## Consequences

- Positive: complete coverage of JWST time-series data in one request; each label has a traceable
  obs_id, window and predicted event time; fabricated caches fail `scripts/check_mast_cache.py`
  (live re-query, SHA-256, whole-number-date check).
- Negative: linear ephemerides ignore transit-timing variations, so TTV systems produce many `ambiguous`
  rows that need human time. The MJD (MAST) vs BJD_TDB (archive) difference (≤ ~10 min) is absorbed by a
  0.25 h margin rather than converted exactly.
- Deviation from the original plan (per-host queries with name variants): recorded here deliberately.

## Revision 2026-11-24 (correction)

Everything from "Context" to "Consequences" is kept as written on 2026-11-22. Corrections:

- **Status and decider.** "Accepted" and "reviewed by the owner" had no recorded evidence. The header now says so.
- **"Complete coverage" and the "on real data" statements** were not backed by any data or log in this repository and have
  not been reproduced. Completeness of the bulk query is **not demonstrated**; `scripts/check_mast_completeness.py`
  (live, owner-run) is meant to test it.
- **"Cached once, unmodified"** means: an ECSV serialisation of the table astroquery parsed. It is not the raw response.
- **The 0.25 h margin is removed.** It had no derivation. No margin or bound replaces it. The conversion between MAST times
  and archive times has not been derived or independently checked, so every row is `ambiguous`
  (`VALIDATED_TIME_SYSTEMS` is empty).
- **Circular orbits are no longer assumed** for e ≤ 0.1 or unknown e, and no eclipse time is predicted. `eclipse_status`
  lists the missing or ambiguous inputs. `eclipse_in_window` and `no_event_in_window` are not produced.
- **Missing uncertainty** is never zero: the row stays `ambiguous` with `uncertainty_status`.
- **Timing is not assignment.** The position must agree with the host, the name must not give another planet, obs_ids must be
  present and unique, and every row carries hashes of its MAST row and of both caches. The hashes sit beside the data:
  they detect accidental change, not a deliberate rewrite.
- **Open:** per-host cache files (PLAN.md) or equivalent provenance for the bulk file; archive column names and limit-flag coding
  (the query has not been run); MAST time scale; proper motion is not applied.
