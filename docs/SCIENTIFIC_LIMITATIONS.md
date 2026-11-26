# Scientific limitations and open prerequisites

What is measured, derived, assumed and unknown in ExoSignal. Last reviewed 2026-11-24.

## How to read the scores

| Quantity        | Is                                                                     | Is not                                            |
| :-------------- | :--------------------------------------------------------------------- | :------------------------------------------------ |
| Priority score  | 100 × sigmoid of a logistic regression trained on unverified labels    | A probability; a measure of habitability or life  |
| Heuristic score | A weighted sum of catalog-based components; not used for the ranking   | A measurement                                     |
| Anomaly score   | A statistical outlier score, often caused by unusual or uncertain data | Evidence of extraterrestrial life or intelligence |
| HZ status       | An orbital distance compared with a 1-D climate model                  | Evidence of water or habitability                 |

## Data classes

| Class   | Examples                                                                                                           |
| :------ | :----------------------------------------------------------------------------------------------------------------- |
| Archive | Radius, period, stellar parameters (NASA Exoplanet Archive composite table; a value can itself be an estimate)     |
| Derived | TSM, ESM, Earth Similarity Index, HZ status, transit depth proxy                                                   |
| Assumed | Mass fallback, K-to-J offset of 0.8 mag, median imputation, neutral defaults in the heuristic score                |
| Unknown | Mass provenance in artifact `v1_2026-10-29`; MAST and archive time systems; which planets JWST has really observed |

## Known defects of the served artifact

1. **Labels.** 32 positive labels, none human-verified; some are known to be wrong. All metrics are provisional.
2. **Mass fallback.** Above 1.23 Earth radii the code uses M = 2.69 R^0.93, attributed to Chen & Kipping (2017) but not
   their relation. It underestimates giant-planet masses, so their TSM is too large. A correction exists in
   unpublished work and must be merged together with a model rebuild.
3. **Scores of ineligible planets.** The artifact stores model outputs for planets that do not transit (Proxima Cen b:
   99.99). The API no longer serves them; the file still contains them.
4. **Habitable zone.** The polynomials hold for host stars of 2600–7200 K. 80 catalog planets orbit stars outside that range.
5. **Earth Similarity Index.** Uses equilibrium temperature and weights normalised to 1, unlike the published form.
6. **Registry entry.** `n_features: 10` should be 21, and its metrics are null. Fixed for the next build only.
7. **Catalog file.** `planets.parquet` was rebuilt on 2026-11-02 without updating its record; the record is corrected and the
   file reproduced column by column ([ARTIFACT_PROVENANCE.md](ARTIFACT_PROVENANCE.md)).

## Prerequisites before any JWST label can be approved (checkpoint H2 stays blocked)

|   # | Prerequisite                                                                                      | State       |
| --: | :------------------------------------------------------------------------------------------------ | :---------- |
|   1 | Derive and independently check the conversion between MAST times and archive transit times        | Open        |
|   2 | Confirm the meaning of the archive's time-system column for every reference                       | Open        |
|   3 | Derive a timing tolerance from that conversion (no margin is used until then)                     | Open        |
|   4 | Show that the bulk MAST query is complete (`scripts/check_mast_completeness.py`, live, owner-run) | Not run     |
|   5 | Per-host cache files, or an equivalent provenance record for the bulk file                        | Open        |
|   6 | Confirm archive column names and limit flags against a live query                                 | Not run     |
|   7 | Confirm the argument-of-periastron convention per reference (both are shown; none is assumed)     | Open        |
|   8 | Eclipse time prediction                                                                           | Deferred    |
|   9 | Proper motion in the position check                                                               | Open        |
|  10 | Human review of every row                                                                         | Not started |

Until 1–3 are done, every candidate row is `ambiguous`, and `scripts/review_labels.py` approves nothing: it needs a
`transit_in_window` row with known uncertainty, provenance hashes and a time system that the builder has validated.
The row must also equal the row computed again from the cached archive data. Training and the CI benchmark ignore a row
without its approval in the review log. An approval records a fingerprint of its archive data; `review_labels.py
--summary` reports approvals whose data have changed since. Training cannot check that, because the cache is never committed.
The cache and the log themselves are not signed.
Passing tests do not change this.
