# Agent Orchestration Skill — API Reference

This document describes the executable scripts in `skills/scripts/` that form the core orchestration primitives. All scripts are standalone Python 3 programs with no external runtime dependencies beyond the Python standard library.

---

## dispatch_compiler.py

**Purpose:** Compile a scoped, token-capped Dispatch Packet for a Codex leaf worker.

**Usage:**
```bash
python dispatch_compiler.py --from-json INPUT.json --capsule CAPSULE.json [options]
```

**Key options:**
- `--from-json PATH` — JSON file containing packet fields (`role`, `reasoning`, `objective`, `scope`, `focus`, `must_read`, `allowed`, `forbidden`, `context`, `confirmed`, `rejected`, `decisions`, `tasks`, `acceptance`, `validation`, `stop`, `output`)
- `--capsule PATH` — Context Capsule JSON to slice into the packet
- `--max-context-chars N` — Max context slice size (default 900)
- `--max-packet-chars N` — Max total packet size (default 7000)
- `--strict` — Fail if no `must_read` items are defined
- `--stats` — Print JSON stats to stderr (chars, limits, capsule source, over-budget status)
- `--allow-oversize` — Print packet even if it exceeds budget
- `--max-<field> N` — Per-field item caps (e.g., `--max-must-read 8`)

**Output:** Writes the Dispatch Packet as plain text to stdout.

**Example:**
```bash
python dispatch_compiler.py \
  --from-json packet.json \
  --capsule capsule.json \
  --max-context-chars 900 \
  --stats
```

---

## orchestration_decider.py

**Purpose:** Recommend minimal useful orchestration: agent count, reasoning effort, and spawn policy.

**Usage:**
```bash
python orchestration_decider.py --task "..." --known-files N [options]
```

**Key options:**
- `--task STRING` (required) — Natural language task description
- `--known-files N` — Estimated number of files to modify (default 0)
- `--surfaces STR` — Comma-separated surface tags (`auth`, `payment`, `frontend`, `docs`, …)
- `--risk low|medium|high|critical` — Risk level of the change (default medium)
- `--ambiguity low|medium|high` — Ambiguity / uncertainty of requirements (default medium)
- `--requires-browser true|false` — Task requires browser-based verification
- `--requires-docs true|false` — Task requires documentation lookup
- `--failing-tests N` — Number of failing tests (default 0)
- `--needs-architecture true|false` — Task requires architectural planning
- `--root-can-edit true|false` — Root context may edit files directly
- `--force-delegate true|false` — Force subagent even for trivial tasks
- `--json` — Output machine-readable JSON instead of human summary

**Output:** Prints size class (XS/S/M/L/XL), max agents, recommended agent types, reasoning level, spawn policy, and usage notes.

**Size classes:**
| Size | Description | Max agents |
|------|-------------|------------|
| XS | 1 file, trivial, low risk | 0–1 |
| S | ≤3 files, low-medium risk | 1 |
| M | ≤8 files, medium risk | 3 |
| L | ≤20 files, medium risk | 4 |
| XL | Large/refactor/architecture | 5 |

**Example:**
```bash
python orchestration_decider.py \
  --task "Add user authentication to checkout flow" \
  --known-files 5 \
  --surfaces "auth,payment,frontend" \
  --risk high \
  --ambiguity medium \
  --json
```

---

## handoff_router.py

**Purpose:** Merge multiple subagent Handoff Packets and detect file ownership conflicts.

**Usage:**
```bash
python handoff_router.py PACKET1.md [PACKET2.md ...] [options]
```

**Key options:**
- `packets` — One or more markdown/text files containing handoff packets
- `--json` — Output machine-readable JSON instead of human summary

**Output:**
- List of packets with extracted file references and summaries
- File ownership conflict report (files touched by more than one packet)
- Human-readable routing digest

**Example:**
```bash
python handoff_router.py worker1_handoff.md worker2_handoff.md worker3_handoff.md
```

---

## Additional Scripts

### context_capsule.py
Persists and retrieves the Context Capsule — a document recording confirmed facts, rejected assumptions, decisions, ownership, and acceptance criteria for the current task.

### failure_classifier.py
Classifies failure types (test failures, lint errors, type errors, runtime crashes) and recommends remediation strategies.

### budget_governor.py
Enforces token budget constraints across the orchestration session.

### dag_planner.py
Builds a directed acyclic graph of task dependencies for complex multi-agent workflows.

### run_ledger.py
Logs orchestration events for audit and replay.

### batch_tasks.py
Splits large task bundles into sized batches for parallel worker dispatch.

### context_coverage_gate.py
Validates that all required context items have been read before proceeding to modification.

### handoff_validate.py
Validates handoff packet structure and required fields.

### plan_gate.py
Enforces that a plan exists and meets quality criteria before branching to workers.

### quality_gate.py
Runs quality checks (lint, type, format) across the modified surface.

### test_matrix.py
Manages the test matrix for multi-configuration testing (OS, Python version, etc.).

### token_budget_linter.py
Lints token usage against the budget and flags overages.

### worktree_guard.py
Enforces worktree isolation so workers do not interfere with each other's files.

### notepad.py
Shared scratch space for inter-agent communication.

---

## File Formats

### Dispatch Packet (output of dispatch_compiler.py)
Plain text with sections: `ROLE`, `MODE / REASONING BUDGET`, `OBJECTIVE`, `SCOPE OWNERSHIP`, `MUST READ BEFORE EDITING`, `FILES / AREAS ALLOWED`, `FILES / AREAS FORBIDDEN`, `CONTEXT CAPSULE SLICE`, `CONFIRMED FACTS`, `REJECTED ASSUMPTIONS`, `DECISIONS / CONSTRAINTS`, `TASK BUNDLE`, `ACCEPTANCE CRITERIA`, `VALIDATION REQUIRED`, `CONTEXT COVERAGE CHECK`, `STOP CONDITIONS`, `SKILL / DELEGATION POLICY`, `OUTPUT`.

### Context Capsule (input to dispatch_compiler.py)
JSON object with keys: `task`, `parent_goal`, `must_read`, `useful_optional`, `forbidden`, `confirmed_facts`, `rejected_assumptions`, `decisions`, `ownership`, `acceptance_criteria`, `validation_commands`.

### Handoff Packet (input to handoff_router.py)
Plain text or markdown summarizing: `STATUS`, `SUMMARY`, `CONTEXT_COVERAGE`, `FILES_READ`, `FILES_CHANGED`, `CHANGES`, `VALIDATION`, `EVIDENCE`, `RISKS`, `PARENT_ACTION`.