# State And Changelog

## Current State

The repository currently provides:

- An npm CLI router in `bin/aoc.mjs`.
- A production `skills/agent-orchestration-skill/` payload.
- Leaf-worker subagent profiles in `subagents/`.
- An installer that writes supported layouts under `skills/`, `subagents/`, and `.orchestration/`.
- Validation suites for packaging, install behavior, CLI smoke tests, TUI/GUI snapshots, usage, budget, and publish readiness.
- A `package.json` package allowlist that includes `docs/`.
- TUI and GUI control-room surfaces for live run inspection.

The skill is explicit-only. It should activate only when the prompt includes `$agent-orchestration-skill`.

## Runtime State

Installed or local runs write state under:

```text
.orchestration/
.orchestration/runs/<run_id>/
.orchestration/events.jsonl
.orchestration/usage/
.orchestration/memory/
```

This state may include task names, event summaries, file paths, handoff summaries, evidence references, and imported usage reports.

State writes use file locks and atomic replacement so concurrent tools do not partially write run ledgers or indexes.

## Recent Implementation Alignment

- `publish-check` now passes with empty sandbox-mounted `.agents` or `.codex` directories, while hidden directories with payload still fail.
- Core gates now use safe `quality_gate` argv defaults with explicit `--shell`.
- `control_gate` enforcement blocks waiting or rejected gates and active ownership conflicts.
- Handoff and context validation now report structured coverage problems instead of only loose text checks.
- DAG review handling now respects dependencies and detects cycles.
- The TUI live view supports auto-refresh, pause, manual refresh, refresh interval, tab selection, and run selection. Snapshot output remains deterministic, and index rebuilds require explicit `--rebuild-index`.
- The GUI provides a stdlib SSE dashboard, JSON API, `--allow-remote`, `--auth-token`, and `--once` snapshot mode. It does not depend on mock data or external assets.
- Package install creates `AGENTS.md` when absent, and installed wrappers support `publish-check`.

## Documentation Change Set

Added the focused `/docs` set:

- `docs/README.md`: docs index.
- `docs/USAGE_EXAMPLES.md`: realistic command workflows.
- `docs/REPO_MAP.md`: maintainable file/group map.
- `docs/SETUP_AND_BASELINE.md`: setup and validation baseline.
- `docs/STATE_AND_CHANGELOG.md`: current state and doc change summary.
- `docs/ISSUE_TRIAGE.md`: known issues and verification steps.
- `docs/QUALITY_AUDIT.md`: quality findings and expected checks.
- `docs/PR_CANDIDATES.md`: reviewable contributor PR slices.
- `docs/SECURITY_MODEL.md`: local state, GUI, and command execution risks.

Latest command-docs audit:

- Public user docs now prefer `npm install -g agentic-orchestration-control` plus `aoc ...` commands instead of source-tree router examples.
- GUI examples document both `/api/snapshot` JSON reads and the `/events` SSE stream for realtime inspection.
- Internal skill references still keep direct bundled Python commands where no public CLI route exists; `SKILL.md` labels those as low-level control-plane operations.

## Baseline Before This Change

Existing top-level docs already covered:

- Install from npm or local tarball.
- The explicit `$agent-orchestration-skill` trigger.
- Short CLI commands.
- TUI/GUI and optional Codex app-server bridge.
- Publish and validation commands.
- A compact top-level repo layout.

The new docs avoid replacing the README. They expand the operational details for users and contributors.

## Follow-Up Alignment

Before release, rerun:

```bash
npm run validate:production
```

Then update `VALIDATION.md` if command output or expected npm payload changes.
