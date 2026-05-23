# Control Plane

Use a small persistent control plane for non-trivial runs. The goal is not to create documentation bloat; it is to prevent duplicate spawning, lost handoffs, forgotten failures, and repeated verification.

## Files

```text
.orchestration/
  runs/<run_id>/state.json
  runs/<run_id>/dispatches/
  runs/<run_id>/handoffs/
  runs/<run_id>/evidence/
  notepads/learnings.md
  notepads/decisions.md
  notepads/issues.md
  notepads/verification.md
  notepads/problems.md
```

## Root rules

- Create a run ledger only for root orchestration mode, not for leaf verification jobs.
- Use the ledger before spawning to check whether an equivalent phase is already active or complete.
- Record agent name, phase, claimed files, commands, status, blocker, and evidence path.
- Do not broadcast the ledger to every worker. Workers receive short Dispatch Packets.
- Write notepad entries only for durable facts that will help future tasks. Do not store transcript summaries or noisy logs.

## Useful commands

```bash
python skills/agent-orchestration-skill/scripts/run_ledger.py init --task "..."
python skills/agent-orchestration-skill/scripts/run_ledger.py update --run-id <id> --kind dispatch --agent batch_implementer_medium --summary "..."
python skills/agent-orchestration-skill/scripts/run_ledger.py show --run-id <id>
```
