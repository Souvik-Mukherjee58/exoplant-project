# ExoSignal Autonomous Execution Progress

**Current phase**: Phase G (Automatic change guard)

---

## Phase Checklist

- [ ] **Phase G**: Automatic change guard (`scripts/guard_changes.py`, `.guard.toml`, tests, pre-commit, CI)
- [ ] **Phase 1**: Purge fabricated data (MAST cache purge, cycle 4 reset, `check_data_integrity.py`, CI)
- [ ] **HUMAN CHECKPOINT H0**: Create `.guard-allow` for Phase 1 purge, then remove after commit
- [ ] **Phase 2**: Real MAST script with planet assignment (`scripts/build_jwst_labels_from_mast.py`, TAP query ephemerides)
- [ ] **HUMAN CHECKPOINT H1**: Run live MAST query & cache verification, commit candidates CSV
- [ ] **Phase 3**: Label review CLI (`scripts/review_labels.py` interactive terminal reviewer)
- [ ] **HUMAN CHECKPOINT H2**: Run interactive label review for >= 15 verified transmission targets
- [ ] **Phase 4**: Retrain and regenerate every report (New artifact version, evaluation reports, nested CV)
- [ ] **HUMAN CHECKPOINT H3**: Cycle 4 target list from STScI GO programs and `CYCLE4_SOURCE.md`
- [ ] **Phase 5**: Cycle 4 forward test (`scripts/forward_test.py`, 10k permutations, `FORWARD_TEST.md`)
- [ ] **Phase 6**: UI fixes (10 strict UI invariant fixes, Lighthouse audit)
- [ ] **Phase 7**: Deploy readiness (Single backend Docker platform, clean env vars, smoke tests)
- [ ] **HUMAN CHECKPOINT H4**: Deploy to cloud (Fly.io + Vercel), execute live smoke tests
- [ ] **Phase 8 prep**: Load test scripts verification (`scripts/run_loadtest.sh`, `render_loadtest_report.py`)
- [ ] **HUMAN CHECKPOINT H5**: Run k6 load test on live deployment, analyze bottlenecks
- [ ] **HUMAN CHECKPOINT H6**: Record walkthrough GIF, screenshots, YouTube demo
- [ ] **Phase 9**: README + docs truth pass (Zero buzzwords, factual lessons learned, empty interview notes)
- [ ] **Phase 10**: Final audit (Clean clone end-to-end audit, pass/fail checklist, PLAN COMPLETE)

---

## Phase Log

### Section A: Setup
- **Status**: Completed
- **Commit**: a438cd1
- **Verified**: Saved verbatim prompt to `.agent/PLAN.md`, initialized `.agent/PROGRESS.md`.
- **Unresolved**: None
