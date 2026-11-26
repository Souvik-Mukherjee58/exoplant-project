# Provenance of artifact `v1_2026-10-29`

## What is served

| File                                  | SHA-256 (first 12) | Origin                                                    |
| :------------------------------------ | :----------------- | :-------------------------------------------------------- |
| `data/raw/nasa_exoplanet_archive.csv` | `d9b6412dfb2b`     | NASA Exoplanet Archive snapshot, 6,451 planets            |
| `ltr_model.joblib`                    | `4f998d601ac6`     | Build of 2026-10-28                                       |
| `planets.parquet`                     | `8e3ec9cf07a5`     | Rebuilt in commit `1e3570d` (2026-11-02); Git LFS         |
| `planets.parquet`, before that        | `054e0aa50451`     | Commit `bb40aca` (2026-10-31); still available in Git LFS |

## The mismatch (2026-11-02 to 2026-11-25)

Commit `1e3570d` replaced `planets.parquet` but not `registry_entry.json` and `manifest.json`, so the integrity check reported a
mismatch. Comparison of the two files:

| Question                       | Result                                                                           |
| :----------------------------- | :------------------------------------------------------------------------------- |
| Planets, row order, columns    | Equal (6,451)                                                                    |
| Labels                         | Equal (32, not human-verified)                                                   |
| Columns without any difference | All input, feature, anomaly and heuristic columns                                |
| Different                      | Four score columns, their ranks and percentiles, and the percentile text         |
| Scores                         | The old values are the new ones rounded to 4 decimals, in every row              |
| Ranks                          | The rounding made ties among scores near 0; without it they are ordered by score |
| Cause in the same commit       | `ltr_model.py`: rounding removed, rank rule and percentile text changed          |

The file was therefore changed on purpose and the record was out of date. The record was corrected on 2026-11-25; its `revisions` field
says what changed. The file itself was not touched.

## Reproduction

`cd backend && python ../scripts/reproduce_artifact.py` (offline, writes nothing; also run by `tests/test_artifact_provenance.py`):

| Step                                                                                | Result                                                                                   |
| :---------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------- |
| Raw snapshot and code give every feature column                                     | Equal (1e-9)                                                                             |
| Committed model gives the final-model scores                                        | Equal                                                                                    |
| Host-grouped cross-validation gives the out-of-fold scores                          | Within 1.5e-4 of 100 points (solver noise); exactly equal on the features of the catalog |
| Scores give ranks and percentiles                                                   | Equal                                                                                    |
| Benchmark on this catalog (9 models, all metrics)                                   | Equal to `benchmark_report.json` to 4 decimals (run once, by hand)                       |
| Windows (Python 3.13, 3.11) and Linux (3.11, six OpenBLAS kernels), pinned packages | Same ranks everywhere                                                                    |

## What this does not show

- The labels are not human-verified, so all metrics stay provisional. A new build is refused until enough labels are approved.
- The byte sequence cannot be reproduced: the file was written by another Arrow version (26).
- The known defects listed in [SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md) are part of what is reproduced.

## A defect found on the way

With the pinned pandas 2.2.3 and NumPy 2.1.3, `np.nan_to_num(series)` overwrites the original column. A rebuild would have stored
0.0 for 11, 28, 299 and 379 missing values and changed 9 scores (of planets that are not ranked). The served file was built with other
versions and is not affected. The code no longer uses it on columns, and a test compares the missing values with the served file.
