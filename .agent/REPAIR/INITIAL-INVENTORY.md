# Initial inventory (2026-11-24, 22:52 IST)

Read-only check at the start of the full repair.

## Git

| Item                         | State                                                              |
| :--------------------------- | :----------------------------------------------------------------- |
| Branch, HEAD                 | `main`, `ce4fcff`                                                  |
| Remote                       | `Souvik-Mukherjee58/exoplant-project`, `main` at `2e93228`         |
| Divergence                   | Local `main` +1 (`ce4fcff` removes the stray file `0,`), remote +0 |
| Changed since the last audit | No, except spacing in two of this repair's own documents           |

The working copy of `PROGRESS.md` ticks Phase 1 and H0 without evidence. It must not be staged.

## Preservation

All original documents, recovered material and the Git directory were backed up before any change, and the copies were
verified by SHA-256. Details are kept privately.

## Protected files

Data (`backend/data/reference/`, `reports/*.csv`, `reports/LABEL_REVIEW.md`, `docs/assets/`), guard files and
`.agent/PLAN.md` were not changed by this repair.

## Baselines before this repair

Phase 2 tests 322 passed; full backend 538 passed, 1 warning; frontend 25 passed (Node 22); guard PASS.

## Problems found

|   # | Problem                                                                                                         | Where             |
| --: | :-------------------------------------------------------------------------------------------------------------- | :---------------- |
|   1 | README clone URL and badges name a repository that the public cannot read                                       | README            |
|   2 | README links a `LICENSE` that does not exist and a demo that is not deployed; the "walkthrough" GIF is 64 bytes | README            |
|   3 | `*.joblib` is declared as Git LFS but committed as ordinary files                                               | `.gitattributes`  |
|   4 | Two API requests always fail; several more API defects                                                          | backend           |
|   5 | Invented values, wrong distance units and unsupported claims in the interface                                   | frontend          |
|   6 | Scores stored and served for planets that the model must not rank                                               | API, artifact     |
|   7 | ADRs 0001–0005 "Accepted" without recorded evidence                                                             | `docs/adr`        |
|   8 | The mass relation on `main` is not the one it is attributed to                                                  | `ground_truth.py` |
|   9 | Known vulnerabilities in npm packages                                                                           | frontend          |
