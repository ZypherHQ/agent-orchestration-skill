# Context Coverage Gate

The Context Coverage Gate prevents workers from editing with incomplete context.

## Correct validation target

Validate against the worker's Dispatch Packet, not the entire Context Capsule.

The full capsule may contain context for several phases or workers. A worker should only prove coverage for the files/areas assigned to that worker.

```bash
python .agents/skills/agent-orchestration-skill/scripts/context_coverage_gate.py \
  --dispatch .orchestration/runs/<run_id>/dispatches/<worker>.md \
  --handoff .orchestration/runs/<run_id>/handoffs/<worker>.md
```

Use `--capsule --full-capsule` only if the worker was assigned every must-read item in the capsule.

## Required worker output

A write worker must return a handoff section like:

```yaml
context_coverage:
  required_files_read:
    - path: app/cart/page.tsx
      status: read
    - path: lib/cart/store.ts
      status: read
  missing_context: []
  safe_to_modify: true
```

If required context is unavailable:

```yaml
status: ESCALATE_TO_PARENT
context_coverage:
  required_files_read:
    - path: app/cart/page.tsx
      status: read
  missing_context:
    - lib/cart/store.ts
  safe_to_modify: false
parent_action: provide missing file/context or narrow scope
```

## Forbidden leakage

The validator rejects routing/delegation leakage such as:

- `target_agent`
- `next_handoff`
- `spawn_agent`
- `wait_agent`
- `resume_agent`
- `$agent-orchestration-skill`
