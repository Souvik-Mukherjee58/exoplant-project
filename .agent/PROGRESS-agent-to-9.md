# Agent work on branch `agent/to-9` (2026-11-22)

Separate from `.agent/PROGRESS.md` so it does not conflict with the owner's uncommitted edits there.
Every phase ended with `python scripts/guard_changes.py --full` = `GUARD: PASS` on a clean worktree
(backend pytest, ruff, mypy, frontend eslint, vitest, build), committed through the pre-commit hook (no
`--no-verify`).

| phase                                    | commit                    | verified                                                                                                                                                                                                           |
| :--------------------------------------- | :------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2 MAST candidates + ephemeris assignment | 1dff28a                   | 41 new tests; dry run on live MAST (4,187 time-series rows) and NASA TAP (4,830 transiting planets); `check_mast_cache.py` live re-query of 3 proposals PASS. No candidates CSV committed (that is checkpoint H1). |
| 3 label review CLI                       | 78c622c                   | 12 tests; `--summary` on real-data candidates: 269 planet x program groups. Fixed cross-line approval match in `check_data_integrity.py`.                                                                          |
| guard proposals (owner applies)          | 52a732f..1027b9b, e37b442 | `.agent/patches/*.proposed.txt`, tested with the Section 0 guard tests (18 passed). ADR 0007.                                                                                                                      |
| 6 UI truth fixes                         | f85fcf6                   | 25 frontend tests; API returns percentile/TSM/size class on detail; mass provenance unknown is never shown as "Measured".                                                                                          |
| 7 deploy readiness                       | 955c2b5                   | CORS wildcard fail-fast, Fly config fixed, admin-gated promote/rollback, rate limiter hardening (8 tests); smoke test run against a local server: PASS, CORS negative case FAIL as expected. Not deployed.         |
| 8 prep load-test tooling                 | e37b442                   | 6 tests; capacity curve script + renderer; nothing measured yet.                                                                                                                                                   |
| 9 (partial) docs truth pass              | d22ae37                   | README PROVISIONAL banner; unmeasured ADR 0003 benchmark removed; ADR deciders corrected.                                                                                                                          |

Separate branch `agent/phase4-science` (6e43e00): correct Chen & Kipping (2017) masses and mass provenance.
Merge it together with the Phase 4 retrain: until the artifact is rebuilt,
`test_labelled_planets_scored_out_of_fold` fails by design (stale artifact).

Open, needs the owner: Section 0 override commit (restore PLAN.md raw text in the same commit), apply the
proposed guard files, H1-H6, and stating contributions for the resume.
