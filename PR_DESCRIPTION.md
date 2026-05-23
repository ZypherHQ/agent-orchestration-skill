## Summary

  This PR hardens the agent orchestration package and upgrades the control-plane UX.

  Major changes:
  - Hardened orchestration gates and validators.
  - Added safer command execution for quality gates.
  - Added blocking enforcement for unresolved/rejected control gates and file ownership conflicts.
  - Improved structured handoff/context validation.
  - Added DAG cycle detection and fixed review dependencies.
  - Added safer locked/atomic orchestration state writes.
  - Upgraded TUI from snapshot-only behavior to realtime interactive mode.
  - Upgraded GUI to realtime SSE dashboard with JSON API, auth token support, and remote binding guard.
  - Fixed package/install behavior and CLI wrappers.
  - Added focused open-source docs under `docs/`.
  - Added GitHub Actions CI with ShellCheck, Python syntax sanity, npm tests, publish check, and pack dry-run.

  ## Notable Behavior Changes

  - `aoc tui` / `aoc` is now usable as a realtime TUI.
  - `aoc snapshot` remains available for deterministic CI/test output.
  - GUI supports:
    - `--auth-token`
    - `--allow-remote`
    - `--once`
    - realtime SSE updates
  - `aoc init --task ...` now generates a unique run id unless `--run-id` / `--run` is supplied.
  - `quality_gate.py` no longer runs shell strings by default; shell execution requires explicit `--shell`.

  ## Docs Added

  - `docs/README.md`
  - `docs/USAGE_EXAMPLES.md`
  - `docs/REPO_MAP.md`
  - `docs/SETUP_AND_BASELINE.md`
  - `docs/STATE_AND_CHANGELOG.md`
  - `docs/ISSUE_TRIAGE.md`
  - `docs/QUALITY_AUDIT.md`
  - `docs/PR_CANDIDATES.md`
  - `docs/SECURITY_MODEL.md`

  ## Validation

  Passed locally:
  - `npm test`
  - `npm run test:npm-cli`
  - `npm run publish:check`
  - `npm pack --dry-run --json`
  - ShellCheck on shell entrypoints
  - Python syntax sanity check
  - Browser GUI visual pass with agent-browser
  - GUI auth and SSE live-update check
  - TUI snapshot smoke
  - Mobile viewport GUI smoke

  ## Release Notes

  The package tarball in `dist/agentic-orchestration-control-0.1.0.tgz` was regenerated after cleanup. Python bytecode artifacts are excluded from npm packaging.
