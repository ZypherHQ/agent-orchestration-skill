# Inspectable Memory Layer

Memory is file-based and inspectable. It is not a hidden transcript cache.

Layers:

1. Context Capsule: critical task context for the active orchestration.
2. Run Ledger: per-session operational state, dispatches, handoffs, evidence, events.
3. Durable Notepads / Wiki: reusable facts, decisions, known traps, verification notes.
4. Memory Index: searchable summary of capsule, handoffs, evidence, and notes.

Use the public CLI to create:

```text
.orchestration/memory/index.json
```

Use the public CLI to inspect why something was remembered:

```bash
aoc memory build --run-id latest
aoc memory search "query"
```

Rules:

- Store durable facts, decisions, evidence refs, and known repo patterns.
- Do not store long logs or private reasoning.
- Prefer Markdown for durable notes and JSON/JSONL for state.
- Every memory update should be explainable by source evidence.
