# Contributing to ExoSignal

Thank you for contributing to ExoSignal. As a scientific exoplanet research and prioritization system, scientific integrity, label accuracy, and reproducible benchmarks are top priorities.

> [!IMPORTANT]
> **Strict Policy on Scientific Data & Benchmark Reports**:
> Files under `backend/data/reference/` and `reports/` require human review and verified astronomical provenance. AI tools and autonomous agents MUST NOT create, edit, fill in, or fabricate data in these directories under any circumstances. All changes require human verification via `.guard-allow`.

---

## Change Guard Architecture

ExoSignal enforces an automated **Change Guard** (`scripts/guard_changes.py`) to safeguard critical scientific data, benchmark outputs, and test suite rigor.

### Protected Paths
Changes to the following paths are strictly guarded and will trigger CI failure unless authorized by a human reviewer:
- `backend/data/reference/` — Archival truth rosters and Cycle target catalogs
- `reports/.mast_cache/` — Raw MAST API query responses (must never be committed)
- `reports/*.csv` — Machine-generated candidate rosters
- `reports/LABEL_REVIEW.md` — Human audit log and provenance decisions
- `reports/CYCLE4_SOURCE.md` — STScI Cycle 4 official source documentation
- `reports/k6_summary.json` — Empirical k6 load test results
- `docs/assets/**` — Verified visual media and screenshots
- Guard configuration & infrastructure files (`.guard.toml`, `.guard-allow`, `scripts/guard_changes.py`, `.github/workflows/guard.yml`, `.pre-commit-config.yaml`, `.agent/PLAN.md`)

### Human Review & `.guard-allow`
1. **No Autonomous AI Edits to Data**: AI agents and automated scripts must never create, edit, or fabricate data files in `backend/data/reference/` or `reports/`.
2. **Authorized Modifications via `.guard-allow`**:
   - To authorize intentional changes to protected paths during human review, create a `.guard-allow` file at the repository root listing the specific paths or glob patterns (one per line).
   - `.guard-allow` **cannot** bypass the guard's own configuration or script files.
   - Always delete `.guard-allow` after your changes are committed.

### Pre-Commit and CI Checks
- **Pre-commit hook**: Runs `python scripts/guard_changes.py --staged` on every commit.
- **Continuous Integration**: GitHub Actions runs `python scripts/guard_changes.py --full --base origin/main` on all pull requests and pushes to `main`.
- **Manual Full Verification**:
  ```bash
  python scripts/guard_changes.py --full
  ```
