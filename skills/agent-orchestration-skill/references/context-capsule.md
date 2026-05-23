# Context Capsule

A Context Capsule preserves essential context across agent boundaries. It is root-owned persistent state, not a prompt blob.

## Purpose

Use it to prevent the “new subagent context” problem without sending the whole transcript to every worker.

The capsule stores:

- required files/areas;
- forbidden files/areas;
- confirmed facts;
- rejected assumptions;
- decisions and constraints;
- ownership notes;
- acceptance criteria;
- validation commands;
- blockers;
- evidence references.

Do not store raw logs, long transcripts, broad summaries, private reasoning, or every file touched during exploration.

## Storage vs dispatch

```text
Context Capsule file
= root-owned source of truth
= may contain more than one worker needs

Dispatch Packet
= narrow slice for one worker
= must stay small
```

Never paste the full capsule into every worker prompt.

## When to create one

Create a capsule when there is more than one phase or worker, or when a task has context that must not be lost.

Avoid heavy capsule work for tiny tasks unless the user explicitly wants orchestration and context preservation.

## Rendering

Compact overview:

```bash
python skills/agent-orchestration-skill/scripts/context_capsule.py render \
  --file .orchestration/context_capsule.json \
  --max-chars 1600 \
  --max-items 8
```

Worker slice:

```bash
python skills/agent-orchestration-skill/scripts/context_capsule.py slice \
  --file .orchestration/context_capsule.json \
  --focus "cart subtotal frontend state" \
  --max-items 4
```

## Merge handoffs carefully

When merging a Handoff Packet, store only durable evidence and confirmed facts. Do not ingest the entire handoff as context.
