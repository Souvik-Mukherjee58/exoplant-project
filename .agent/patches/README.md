# Guard patches for the owner's human-override commit

The guard's own files (`scripts/guard_changes.py`, `.github/workflows/guard.yml`, ...) are protected, so an
AI agent cannot commit changes to them. These patches are applied and committed by the owner only.
Both are made against the working tree that contains the uncommitted "Section 0" repair.

| patch                                       | what it fixes                                                                                                                                                                                                                                                                                                                                                                                 |
| :------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0001-guard-row-level-label-approval.patch` | The label check used a DOTALL regex (`planet.*?APPROVED.*?date`) that matched across lines, so one approval anywhere below a pending planet validated it. Now one table line must hold planet, program_id, APPROVED, reviewer and ISO date (same rule as `scripts/check_data_integrity.py`).                                                                                                  |
| `0002-guard-ci-human-approved-label.patch`  | CI never sees `.guard-allow`, so every legitimate human data commit (e.g. checkpoint H2) would fail CI forever, and on push only `HEAD~1` was checked. Adds `--human-approved` (honoured only when `GITHUB_ACTIONS=true`), passed by the workflow when the PR has the owner's `human-approved` label; pushes compare with `github.event.before`. See `docs/adr/0007-human-approval-in-ci.md`. |

Apply (in the main working tree, after reviewing each diff):

```bash
git apply --check .agent/patches/0001-guard-row-level-label-approval.patch
git apply .agent/patches/0001-guard-row-level-label-approval.patch
git apply .agent/patches/0002-guard-ci-human-approved-label.patch
```

Then, on GitHub: create a label named `human-approved`, and enable branch protection on `main`
("Require a pull request before merging", "Require status checks to pass").
