# Control Room TUI

`agentic-orchestration-control` opens a local terminal control room for orchestration runs.

The TUI is filesystem-first. It reads `.orchestration/` artifacts:

```text
.orchestration/index.json
.orchestration/events.jsonl
.orchestration/runs/<run_id>/state.json
.orchestration/runs/<run_id>/events.jsonl
.orchestration/runs/<run_id>/plan.json
.orchestration/runs/<run_id>/dispatches/
.orchestration/runs/<run_id>/handoffs/
.orchestration/runs/<run_id>/evidence/
.orchestration/runs/<run_id>/controls/
.orchestration/memory/index.json
```

Default UX:

- Sessions: choose one root orchestration run.
- Overview: task, status, classification, budget, last event.
- DAG: phase graph and dependencies.
- Workers: leaf-worker lanes, reasoning, scope, progress proxy, current status.
- Events: compact timeline.
- Memory: Context Capsule and indexed durable memory.
- Gates: STOP gate status and decisions.
- Stats: workers, handoffs, evidence, dispatch size, token-pressure proxy.

The TUI must not become a hidden orchestrator. It should observe state and write explicit control decisions only when the user chooses an action.

For non-interactive environments, use:

```bash
agentic-orchestration-control snapshot --repo .
```
