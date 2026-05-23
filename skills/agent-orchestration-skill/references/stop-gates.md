# STOP Gates

STOP gates are user-visible control points. They prevent silent escalation, blind retries, and unnecessary token spend.

Use `scripts/control_gate.py` to create or resolve gates.

Typical gates:

```text
plan_gate
budget_gate
before_high_reasoning
before_xhigh_strategy
before_browser_qa
before_destructive_command
before_touching_forbidden_files
before_more_workers
before_retry_after_failure
before_final_report
```

Gate actions:

```text
approve
reject
replan
pause
resume
downgrade
merge
```

Rules:

- A gate must contain a clear reason.
- A gate should offer concrete options.
- Every gate decision writes a control file and an event.
- The root orchestrator remains responsible for interpreting the decision.
- Workers must not create or approve gates; they return `ESCALATE_TO_PARENT`.
