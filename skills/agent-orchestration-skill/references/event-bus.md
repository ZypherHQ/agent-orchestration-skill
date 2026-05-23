# Event Bus

The control-room layer is event-driven. Do not force the TUI to infer state from verbose logs.

Write compact JSONL events to:

```text
.orchestration/events.jsonl
.orchestration/runs/<run_id>/events.jsonl
```

Use `scripts/event_emit.py` when a tool, gate, worker, command, or memory update changes the run state.

Important event names:

```text
run_created
task_classified
context_capsule_created
dag_created
plan_gate_passed
plan_gate_rejected
budget_gate_passed
budget_gate_rejected
dispatch_compiled
worker_dispatched
worker_started
context_coverage_passed
context_coverage_failed
command_started
command_finished
handoff_received
handoff_validated
handoff_rejected
quality_gate_completed
verification_failed
failure_classified
retry_scheduled
replan_requested
stop_gate_waiting
gate_approve
gate_reject
memory_index_built
run_completed
run_failed
```

Rules:

- Events must be short and structured.
- Do not store raw logs, transcripts, or private reasoning in events.
- Put long command output under `evidence/` and link it through metadata.
- Every user control action should write an event.
- Event payloads should explain state, not become another prompt transcript.
