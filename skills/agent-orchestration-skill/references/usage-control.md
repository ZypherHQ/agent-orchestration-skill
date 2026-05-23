# Usage Control

Usage control is local-first and split into two channels:

1. **Real/imported usage**: token and cost data imported from trusted local tooling such as `ccusage` JSON, Codex JSON events, or explicit wrapper metadata.
2. **Estimated orchestration pressure**: a deterministic proxy derived from Dispatch Packet size, Handoff Packet size, Context Capsule size, evidence size, and event volume.

Do not mix these concepts. Estimated pressure is not billing; it is a waste/risk signal.

## What to record

Record usage per run, phase, worker, model, and reasoning tier when available:

- input tokens
- output tokens
- reasoning output tokens
- cached input tokens
- cache creation tokens
- total tokens
- cost USD, if a trusted source provides it
- model
- reasoning level
- source: `ccusage`, `codex_exec_json`, `manual`, or `orchestration_estimate`

## Reports

Use session reports to inspect one orchestration run:

```bash
aoc usage --run-id latest
```

Use source reports to separate imported usage from local estimates:

```bash
aoc usage --group-by source
```

Use statusline for compact TUI/sidebar display:

```bash
aoc usage --run-id latest --statusline
```

## ccusage bridge

If `ccusage` is installed, import focused Codex session data:

```bash
aoc ccusage run --source codex --report session --run-id latest
```

Or import an exported JSON file:

```bash
ccusage codex session --json --offline > .orchestration/usage/ccusage-codex-session.json
aoc ccusage import --input .orchestration/usage/ccusage-codex-session.json --run-id latest
```

## Budget policy

Before adding workers, broad verification, high reasoning, or xhigh strategy, check usage pressure:

```bash
aoc budget 12000 --run-id latest
```

If the check fails, reduce context, merge batches, reuse prior handoffs, or stop at a gate for human approval.
