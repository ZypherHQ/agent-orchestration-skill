# Worker Contract

## Write workers

A write worker must perform a complete bounded loop:

1. Read the Dispatch Packet.
2. Perform Context Coverage Check for every required file/area.
3. Inspect assigned files and nearby dependencies.
4. Identify the minimal safe change.
5. Modify only allowed files.
6. Add/update comments only where they clarify non-obvious code.
7. Run targeted validation when available.
8. Return a concise Handoff Packet.

## Read-only workers

A read-only worker must gather enough evidence to be useful:

- cite files/symbols/commands;
- distinguish confirmed facts from hypotheses;
- identify ownership and likely next parent action;
- avoid broad rewrites without evidence.

## Handoff Packet

```text
STATUS: success | partial | blocked | failed | ESCALATE_TO_PARENT
SUMMARY:
CONTEXT_COVERAGE:
FILES_READ:
FILES_CHANGED:
CHANGES_MADE:
VALIDATION:
EVIDENCE:
RISKS:
PARENT_ACTION:
```

Workers must not include `target_agent`, `next_handoff`, or child-agent plans unless the user explicitly requested those fields.
