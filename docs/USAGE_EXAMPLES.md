# Usage Examples

These examples use the short `aoc` command after installing the package into a repository:

```bash
npx --yes agentic-orchestration-control install .
```

If `aoc` is not on `PATH`, use the local shim:

```bash
./.orchestration/bin/aoc
```

## Open Before A Run Exists

Open the terminal control room:

```bash
aoc
```

Open the GUI:

```bash
aoc gui
```

Expected behavior before any AOC run exists: the UI renders an empty state and any discoverable imported Codex sessions. It should not require `aoc init`.

## Use The Explicit Skill

Prompt Codex with the literal skill name:

```text
Use $agent-orchestration-skill for this task.

Run in token-efficient control-plane mode.
Spawn only useful leaf workers.
Preserve context with a scoped Context Capsule.
```

Prompts without `$agent-orchestration-skill` should run in normal mode.

## Initialize A Run

Create an observable run with a generated unique run id:

```bash
aoc init "Fix checkout flow"
```

Machine-readable form:

```bash
aoc init "Fix checkout flow" --json
```

Expected result:

```text
.orchestration/runs/<generated_run_id>/state.json
```

## List And Select Sessions

List native AOC runs and imported Codex sessions:

```bash
aoc sessions
aoc sessions --json
```

Show the selected run:

```bash
aoc current
aoc current --json
```

Select a run:

```bash
aoc use <run_id>
```

## Import Codex Sessions

Import local Codex rollout logs:

```bash
aoc import
```

Use a fake or alternate Codex home:

```bash
AOC_CODEX_HOME=/tmp/fake-codex aoc import --json
```

The importer reads:

```text
sessions/YYYY/MM/DD/rollout-*.jsonl
```

Imported sessions appear in:

```bash
aoc sessions
aoc
aoc gui
```

## Render Snapshots

Print a non-interactive control-room snapshot:

```bash
aoc
```

Render one HTML GUI snapshot:

```bash
aoc gui --once > /tmp/aoc.html
```

## Check Usage And Budget

Show derived run usage:

```bash
aoc usage
```

Check an estimated-token budget:

```bash
aoc budget 12000
```

Expected output includes either `PASS` or `FAIL`.

## Search Local State

Search run state, events, handoffs, dispatches, evidence, memory notes, and imported Codex summaries:

```bash
aoc search "checkout"
aoc search "checkout" --json
```

## Work With Gates

Show current gate status:

```bash
aoc gates
```

Request a gate:

```bash
aoc gates request --gate-id browser-qa --reason "UI flow changed"
```

## Remote GUI Access

The GUI is local-only by default. Expose it remotely only with an auth token:

```bash
AOC_GUI_TOKEN=replace-me \
  aoc gui \
  --host 0.0.0.0 \
  --allow-remote \
  --auth-token "$AOC_GUI_TOKEN"
```

Fetch JSON from the local GUI API:

```bash
curl -H "Authorization: Bearer replace-me" http://127.0.0.1:8787/api/snapshot
```

## Validate Before Publish

Run the production validation matrix:

```bash
npm run validate:production
```

Expected checks:

```text
npm test
npm run test:npm-cli
npm run publish:check
npm pack --dry-run
```

## Smoke Test The Tarball

Pack and test the local package:

```bash
npm pack --pack-destination dist
tmp="$(mktemp -d)"
git init -q "$tmp/repo"
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz \
  agentic-orchestration-control install "$tmp/repo"
```

Then use the installed shim from that repo:

```bash
"$tmp/repo/.orchestration/bin/aoc" init "Fix checkout flow" --json
"$tmp/repo/.orchestration/bin/aoc" sessions --json
```
