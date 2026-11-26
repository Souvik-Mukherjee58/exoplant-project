# ADR 0007: How a human approves protected changes in CI

- **Status**: Proposed, not adopted; superseded by the guard v3.3 proposal (see the revision below)
- **Date**: 2026-11-22
- **Decider**: Souvik Mukherjee (project owner)

## Context

This repository is built largely with AI coding agents, and agents fabricated data twice (program IDs,
a "MAST cache"). The change guard therefore fails on any change to protected paths (label CSVs,
review log, load-test results, the guard itself) unless a human approves it.

Locally, approval is an untracked `.guard-allow` file. That file is never committed, so CI cannot see it:
every legitimate human data commit (the label review at checkpoint H2) would fail CI permanently. A
permanently red CI teaches everyone to ignore it, which is worse than no CI. Separately, the push trigger
compared only `HEAD~1`, so in a push of several commits only the last one was checked.

The honest constraint: on a solo developer machine, an agent runs as the developer, with the same files,
git identity and signing keys. Nothing local can prove "a human did this".

## Decision

Put the human approval where the agent has no access: the GitHub UI.

- Agents work on branches. The owner opens a PR to `main`.
- If the PR changes protected paths, the owner reviews the diff and applies the label `human-approved`.
  The workflow then runs the guard with `--human-approved`: protected-path changes are listed as
  "HUMAN-APPROVED VIA PR LABEL" instead of failing. Data-integrity rules (e.g. a `verified=True` label
  without an APPROVED review row) still fail.
- `--human-approved` is ignored unless `GITHUB_ACTIONS=true`, so it cannot be used locally.
- Pushes compare with `github.event.before`, so every pushed commit is checked.
- Branch protection on `main` requires a PR and passing checks, so pushes to `main` come from merged,
  checked PRs.

## Consequences

- CI stays green for legitimate human data changes and stays red for unapproved ones.
- Security rests on the agent having no GitHub UI/API credentials. If an agent is ever given a GitHub
  token that can label PRs, this control is void; that must be recorded if it changes.
- Rejected alternatives: a commit-message trailer ("human-override: ...") is trivially written by an
  agent; committing `.guard-allow` makes it permanent and invisible in review; signed commits do not help
  when the agent can use the same key.

## Revision 2026-11-24

The text above is kept as written. This design was never applied. A pull request label does not show who reviewed which
commit, so the v3.3 proposal uses protected environments and checks the approver, the author and the exact head commit
instead. v3.3 is tested locally only; nothing has been tested on GitHub.
