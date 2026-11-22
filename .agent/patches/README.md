# Proposed guard changes for the owner's human-override commit

The guard's own files (`scripts/guard_changes.py`, `.github/workflows/guard.yml`, ...) are protected, so an
AI agent cannot commit changes to them. The complete proposed files are stored here as `.txt` (so no
formatter or whitespace hook rewrites them). They are based on the working tree that contains the
uncommitted "Section 0" repair, and were tested with its `backend/tests/test_guard.py` (18 passed).

| file                            | what it changes                                                                                                                                                                                                                                                                                                                                                       |
| :------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `guard_changes.py.proposed.txt` | 1) The label check used a DOTALL regex (`planet.*?APPROVED.*?date`) that matched across lines, so one approval anywhere below a pending planet validated it. Now one table line must hold planet, program_id, APPROVED, reviewer and ISO date (same rule as `scripts/check_data_integrity.py`). 2) Adds `--human-approved`, honoured only when `GITHUB_ACTIONS=true`. |
| `.guard.toml.proposed.txt`      | Also protects `reports/k6_capacity.json` (from `scripts/run_capacity_curve.py`), like `reports/k6_summary.json`.                                                                                                                                                                                                                                                      |
| `guard.yml.proposed.txt`        | Passes `--human-approved` only for PRs labelled `human-approved` by the owner (and for pushes to `main`, which must come from merged PRs); pushes compare with `github.event.before` instead of `HEAD~1`. See `docs/adr/0007-human-approval-in-ci.md`.                                                                                                                |

Review, then copy (in the main working tree, after the Section 0 changes are present):

```bash
git diff --no-index scripts/guard_changes.py .agent/patches/guard_changes.py.proposed.txt
git diff --no-index .github/workflows/guard.yml .agent/patches/guard.yml.proposed.txt
cp .agent/patches/guard_changes.py.proposed.txt scripts/guard_changes.py
cp .agent/patches/guard.yml.proposed.txt .github/workflows/guard.yml
cp .agent/patches/.guard.toml.proposed.txt .guard.toml
```

Then, on GitHub: create a label named `human-approved`, and enable branch protection on `main`
("Require a pull request before merging", "Require status checks to pass").
