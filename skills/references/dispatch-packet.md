# Dispatch Packet

A Dispatch Packet is a compact job contract for one leaf worker. It is not the whole transcript, the whole plan, or the whole Context Capsule.

## Core rule

The Context Capsule is persistent storage. The Dispatch Packet gets only a scoped slice.

Do not broadcast the full capsule to every worker. If a worker needs more than the slice, it must return `ESCALATE_TO_PARENT` with the missing context.

## Default dispatch caps

Use these caps unless the task genuinely requires a larger packet:

- `must_read`: max 8 items
- `allowed`: max 8 items
- `forbidden`: max 6 items
- `confirmed_facts`: max 5 items
- `rejected_assumptions`: max 3 items
- `decisions`: max 3 items
- `tasks`: max 8 items
- `acceptance_criteria`: max 5 items
- `validation`: max 4 checks
- capsule/context text: about 900 characters
- compiled packet: target below about 7000 characters

If the packet exceeds budget, narrow the scope before spawning. Do not solve the issue by sending more context.

## Required fields

```text
ROLE:
MODE / REASONING BUDGET:
OBJECTIVE:
SCOPE OWNERSHIP:
MUST READ BEFORE EDITING:
FILES / AREAS ALLOWED:
FILES / AREAS FORBIDDEN:
CONTEXT CAPSULE SLICE:
CONFIRMED FACTS:
REJECTED ASSUMPTIONS:
TASK BUNDLE:
ACCEPTANCE CRITERIA:
VALIDATION REQUIRED:
CONTEXT COVERAGE CHECK:
STOP CONDITIONS:
SKILL / DELEGATION POLICY:
OUTPUT:
```

## Rules

- Include only context needed for this worker.
- Required files/areas must be specific enough to verify coverage.
- Prefer 3–8 must-read files over broad directories.
- Put known dead ends in `REJECTED ASSUMPTIONS`.
- Put commands in `VALIDATION REQUIRED` instead of vague “test it”.
- Workers must return `ESCALATE_TO_PARENT` if required context is missing.
- Do not include raw logs, full diffs, transcripts, or previous handoffs unless they are tiny and directly relevant.

## Compiler

Use:

```bash
python .agents/skills/agent-orchestration-skill/scripts/dispatch_compiler.py \
  --capsule .orchestration/context_capsule.json \
  --focus "<worker scope>" \
  --objective "<bounded objective>" \
  --tasks "<task 1>;<task 2>" \
  --stats
```

The compiler slices capsule entries by worker focus and hard-caps section sizes.
