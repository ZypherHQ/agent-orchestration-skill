# Usage Examples

These examples assume `npm` is available. Use `npx --yes agentic-orchestration-control`
from any repository where you want to install or inspect the control plane.

## Install Into A Repo

Install the skill pack into a repository:

```bash
npx --yes agentic-orchestration-control install /path/to/repo
```

Expected result:

```text
/path/to/repo/skills/agent-orchestration-skill/
/path/to/repo/subagents/
/path/to/repo/.orchestration/bin/aoc
/path/to/repo/AGENTS.md
```

> Note: Installing into a repo with legacy `.skills/`, `.agents/skills/agent-orchestration-skill`, or `.codex/agents` paths backs them up under `.orchestration-backup-*`.

## Use The Explicit Skill

Prompt Codex with the literal skill name:

```text
Use $agent-orchestration-skill for this task.

Run in token-efficient control-plane mode.
Spawn only useful leaf workers.
Preserve context with a scoped Context Capsule.
```

Prompts without `$agent-orchestration-skill` should run in normal mode.

## Initialize A Run Ledger

Create an observable run:

```bash
npx --yes agentic-orchestration-control init \
  --repo . \
  --run-id smoke \
  --task "smoke validation"
```

Expected result:

```text
.orchestration/runs/smoke/state.json
```

## Render A Snapshot

Print a non-interactive control-room snapshot:

```bash
npx --yes agentic-orchestration-control snapshot --repo . --run-id smoke
```

Expected output includes:

```text
Agentic Orchestration Control
```

Open the live TUI:

```bash
npx --yes agentic-orchestration-control tui --repo . --run-id smoke
```

Useful controls include pause, manual refresh, refresh interval, tab selection, and run selection. Use `--rebuild-index` only when you intentionally want to rebuild `.orchestration/index.json` before reading.

## Open The Local GUI

Render one HTML snapshot:

```bash
npx --yes agentic-orchestration-control gui \
  --repo . \
  --run-id smoke \
  --once > /tmp/aoc-smoke.html
```

Run the local server:

```bash
npx --yes agentic-orchestration-control gui --repo . --run-id smoke
```

> Note: The GUI is local-only by default. Use `--allow-remote` and an auth token only when you intentionally expose it beyond localhost.

Expose the GUI remotely only with an auth token:

```bash
AOC_GUI_TOKEN=replace-me \
  npx --yes agentic-orchestration-control gui \
  --repo . \
  --run-id smoke \
  --allow-remote \
  --auth-token "$AOC_GUI_TOKEN"
```

Fetch JSON from the local GUI API:

```bash
curl -H "Authorization: Bearer replace-me" http://127.0.0.1:8787/api/snapshot
```

Watch the realtime SSE stream from a shell:

```bash
curl -N -H "Authorization: Bearer replace-me" "http://127.0.0.1:8787/events?run=smoke"
```

## Check Usage And Budget

Show derived run usage:

```bash
npx --yes agentic-orchestration-control usage --repo . --run-id smoke
```

Check an estimated-token budget:

```bash
npx --yes agentic-orchestration-control budget 12000 --repo . --run-id smoke
```

Expected output includes either:

```text
PASS
```

or:

```text
FAIL
```

## Work With Gates

Show current gate status:

```bash
npx --yes agentic-orchestration-control gates --repo . --run-id smoke
```

Request a gate:

```bash
npx --yes agentic-orchestration-control gates request \
  --repo . \
  --run-id smoke \
  --gate-id browser-qa \
  --reason "UI flow changed"
```

## Build And Search Memory

Build the memory index:

```bash
npx --yes agentic-orchestration-control memory build --repo . --run-id smoke
```

Search it:

```bash
npx --yes agentic-orchestration-control memory search "handoff" --repo .
```

## Validate Before Publish

Run the production validation matrix:

```bash
npm run validate:production
```

Expected checks:

```text
npm test
npm run publish:check
npm pack --dry-run
```

> Note: Empty sandbox-mounted `.agents` or `.codex` directories are tolerated. Hidden directories with payload should still fail `publish-check`.

## Smoke Test The Tarball

Pack and test the local package:

```bash
npm pack --pack-destination dist
tmp="$(mktemp -d)"
git init -q "$tmp/repo"
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz \
  agentic-orchestration-control install "$tmp/repo"
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz \
  agentic-orchestration-control init --repo "$tmp/repo" --run-id smoke --task "smoke"
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz \
  agentic-orchestration-control snapshot --repo "$tmp/repo" --run-id smoke
```

Expected result:

```text
skills/agent-orchestration-skill/
subagents/
.orchestration/bin/aoc
AGENTS.md
```
