# Dispatch Packet Contract

Subagent prompts should be short, complete, and bounded.

## Required fields

```text
ROLE:
REASONING / MODEL INTENT:
OBJECTIVE:
SCOPE OWNERSHIP:
ALLOWED FILES / AREAS:
FORBIDDEN FILES / AREAS:
CONTEXT DIGEST:
TASK BUNDLE:
ACCEPTANCE CRITERIA:
VALIDATION REQUIRED:
STOP CONDITIONS:
SKILL POLICY: Do not invoke skills. Do not spawn subagents.
OUTPUT FORMAT: Handoff Packet only.
```

## Context diet

Include only:

- confirmed facts,
- relevant file paths/symbols,
- previous failures,
- exact acceptance criteria,
- commands to run.

Exclude:

- raw logs unless a short excerpt is necessary,
- unrelated agent findings,
- whole root plan,
- skill names,
- broad “audit everything” instructions for a scoped worker.
