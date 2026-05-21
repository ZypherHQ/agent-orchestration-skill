# Worker Contract

## Write workers

A write worker must not stop after a trivial action. It must perform a complete bounded loop:

1. Inspect assigned files and nearby dependencies.
2. Identify the minimal safe change.
3. Modify only allowed files.
4. Add/update comments only where they clarify non-obvious code.
5. Run targeted validation when available.
6. Return a concise Handoff Packet.

## Read-only workers

A read-only worker must gather enough evidence to be useful:

- cite files/symbols/commands,
- distinguish confirmed facts from hypotheses,
- identify ownership and likely next action,
- avoid proposing broad rewrites without evidence.

## Handoff Packet

```text
STATUS: success | partial | blocked | failed
SUMMARY:
FILES TOUCHED / INSPECTED:
CHANGES MADE:
VALIDATION:
RISKS:
NEXT RECOMMENDED ACTION:
```
