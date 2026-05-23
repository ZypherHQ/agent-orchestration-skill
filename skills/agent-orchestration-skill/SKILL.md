---
name: agent-orchestration-skill
description: EXPLICIT ONLY. Use only when prompt contains `$agent-orchestration-skill`; root-only token-aware subagent orchestration with control-room events.
---

# Agent Orchestration Skill

Use this skill only when the user prompt contains the exact literal `$agent-orchestration-skill`. Do not use this skill for ordinary coding, testing, audit, debugging, or subagent tasks when that literal invocation is absent. Use it only in the root Codex session. Never instruct spawned subagents to invoke this or any other repo skill, and never instruct spawned subagents to spawn more agents. This is a no nested delegation workflow.

## Step 0 — Runtime mode guard

This skill is explicit-only and root-only. If the current user prompt does not contain `$agent-orchestration-skill`, stop using this skill and continue in normal mode. If the prompt says `You are a subagent`, `verification subagent`, `Run exactly these commands`, `Do not edit files`, `LEAF_EXEC_MODE`, or `Return only a YAML Handoff Packet`, do **not** use this skill, do **not** spawn agents, and perform only the bounded leaf task.

For leaf `codex exec` jobs, prefer CLI hard overrides:

```bash
codex exec --cd /path/to/repo --sandbox workspace-write \
  -c features.multi_agent=false \
  -c agents.max_depth=0 \
  -c agents.max_threads=1 \
  -c model_reasoning_effort=low \
  -c model_verbosity=low \
  -c model_reasoning_summary=none \
  'LEAF_EXEC_MODE. You are a verification leaf worker. Do not spawn agents. Run exactly the requested commands and return only the requested packet.'
```

## Prime directive

Act as a **task compiler, context-preserving control-plane operator, and event-driven run supervisor**, not a prompt broadcaster. Classify the work, preserve the essential context, choose the cheapest adequate reasoning tier, batch related actions, compile minimal Dispatch Packets, track state, and collect concise Handoff Packets. The Context Capsule is persistent storage; a Dispatch Packet is only a small scoped slice for one worker. The capsule stays on disk; workers receive only the narrow slice they need.

## Hard constraints

1. **Root-only skill:** subagents receive plain dispatch text, not skill names.
2. **Context never depends on memory alone:** store essential facts in a Context Capsule before multi-phase or multi-worker execution.
3. **No worker edits without Context Coverage:** a worker must read required files/areas and report coverage before changing code.
4. **No one-agent-per-file fan-out:** batch related files by user flow, module, package, or owner.
5. **No redundant waves:** if one worker can inspect, patch, and test a small change, use one worker.
6. **No raw output broadcast:** route only facts, blockers, file ownership, commands run, failures, and next actions.
7. **No full capsule broadcast:** keep the Context Capsule on disk and pass only a scoped slice to each worker.
8. **Dispatch budgets:** cap must-read files, facts, decisions, tests, and context text before spawning. If the packet is large, narrow the scope instead of spawning.
9. **Write workers must complete a loop:** context coverage → inspect → patch → targeted validation → Handoff Packet.
10. **Read-heavy work can be parallel; write-heavy work should be serialized or batched carefully.**
11. **Leaf-worker boundary:** only the root session may spawn agents. Workers return `ESCALATE_TO_PARENT` when they need help.
12. **Plan and budget gates before broad work:** medium/large tasks need a compact phase plan and budget check before implementation.
13. **Inspectable state:** when a run ledger exists, emit compact events so the control-room TUI can show sessions, worker lanes, gates, evidence, and memory without parsing raw logs.

## Step 1 — Classify before spawning

Classify the task using:

- Known files: 0, 1, 2–3, 4–8, 9+
- Surfaces: frontend, backend, database, infra, docs, tests, browser, security
- Ambiguity: low, medium, high
- Risk: low, medium, high, critical
- Required evidence: none, targeted test, full test matrix, browser QA, security review
- Parallel value: low, medium, high
- Worktree state: clean, dirty, unknown

Use `scripts/orchestration_decider.py` when useful.

## Step 2 — Pick the minimum viable orchestration mode

| Mode | Criteria | Default behavior |
|---|---|---|
| XS | Known tiny task | Usually no subagent. If root edits are forbidden, exactly one `micro_implementer_medium` |
| S | 1–3 related files | One bundled `micro_implementer_medium` or `batch_implementer_medium`; optional exact `test_runner_low` only when useful |
| M | 3–8 files or unclear owner | Short DAG; `code_mapper_low` only if discovery is needed; one batched implementer; verifier |
| L | Multi-surface feature/fix | Ledger + DAG + bounded scout/research + 1–2 implementers + verification |
| XL | Very large or critical ambiguous work | Ledger + DAG + plan gate + optional `strategy_architect_xhigh`, then scoped high/medium workers |

Do not spawn agents just to satisfy a habit. Spawn only when the worker has a meaningful bundle of work or isolates noisy verification/browser output. A useful worker must perform at least two valuable actions, such as inspect + patch, patch + validate, browser reproduce + evidence, or mapping + ownership summary.

## Step 3 — Preserve context before dispatch

For every task with more than one phase or worker, create/update a Context Capsule. It is the root-owned source of truth for facts that must not be lost when a new subagent context opens. It is **not** prompt payload and must not be pasted wholesale into every worker prompt.

```bash
python skills/agent-orchestration-skill/scripts/context_capsule.py init \
  --task "<task>" \
  --goal "<goal>" \
  --must-read path/to/file_a \
  --must-read path/to/file_b \
  --acceptance "<observable acceptance criterion>" \
  --validation "<command or QA check>" \
  --out .orchestration/context_capsule.json
```

Keep the capsule compact. Store confirmed facts, rejected assumptions, decisions, ownership, required files/areas, forbidden files/areas, acceptance criteria, validation commands, blockers, and evidence references. Do not store raw logs, transcripts, broad summaries, or private reasoning.

When dispatching a worker, use a narrow slice:

```bash
python skills/agent-orchestration-skill/scripts/context_capsule.py slice \
  --file .orchestration/context_capsule.json \
  --focus "<worker objective/scope>" \
  --max-items 4
```

Use:

```bash
python skills/agent-orchestration-skill/scripts/context_capsule.py render --file .orchestration/context_capsule.json --focus "<worker objective/scope>" --max-chars 1200
```

Read `references/context-capsule.md` when needed.

## Step 4 — Create control-plane state when needed

For XS/S, avoid unnecessary artifacts unless useful. For medium/large tasks, initialize a run ledger:

```bash
python skills/agent-orchestration-skill/scripts/run_ledger.py init --task "<task>"
```

Use the ledger to record phases, dispatches, Handoff Packets, claimed files, evidence, failures, context capsule path, and final status. Before spawning any worker, check the ledger for duplicate active/completed work.

When a ledger exists, treat the run as event-driven. Emit compact state changes so the optional control-room TUI can show the orchestration without parsing raw logs:

```bash
python skills/agent-orchestration-skill/scripts/event_emit.py   --run-id <run_id>   --event worker_dispatched   --agent batch_implementer_medium   --reasoning medium   --summary "frontend cart implementation bundle dispatched"
```

Use events for run creation, classification, DAG/budget gates, worker dispatch, Context Coverage, commands, handoffs, failures, memory updates, and final status. Events are compact JSONL records; long logs belong in `evidence/` files.

## Step 5 — Build a DAG only when orchestration is justified

Do not use a DAG for tiny tasks. For medium/large tasks, create a compact dependency-aware DAG with at most 7 phases:

```bash
python skills/agent-orchestration-skill/scripts/dag_planner.py --task "<task>" --size M --surfaces frontend,backend > .orchestration/plan.json
python skills/agent-orchestration-skill/scripts/plan_gate.py .orchestration/plan.json
```

If the gate rejects the plan, fix the plan before spawning. The plan gate checks executability, dependencies, acceptance criteria, validation, context policy, and worker leaf policy.

## Step 6 — Reasoning router

Use the cheapest adequate reasoning tier:

- `low`: scouts, file/symbol discovery, code-path mapping, docs contract checks, exact command execution, routing/finalization.
- `medium`: normal code writing, small-to-medium implementation bundles, browser QA, meaningful test design, verification matrices.
- `high`: complex implementation, non-trivial business logic, migrations, concurrency suspicion, security-sensitive review, hard regression audit.
- `xhigh`: very large ambiguous planning, architecture/feature structuring, critical design tradeoffs, or repeated high-effort failure with evidence.

Do not use `xhigh` for routine updates, isolated fixes, simple debugging, or single-file implementation. Prefer `strategy_architect_xhigh` as read-only planning; use `complex_implementer_high` for hard writes.

Use `scripts/budget_governor.py` before spawning:

```bash
python skills/agent-orchestration-skill/scripts/budget_governor.py --size M --agents code_mapper_low,batch_implementer_medium --reasoning medium --dispatch-chars <largest_packet_chars>
```

## Step 7 — Compile Dispatch Packets with required context

A Dispatch Packet must be short, targeted, and include only a scoped Context Capsule slice. Do not paste the whole plan, whole capsule, raw logs, or previous transcripts. Include:

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

Use `scripts/dispatch_compiler.py` when useful. It caps the capsule slice by default: 8 must-read items, 6 forbidden items, 5 facts, 3 rejected assumptions, 3 decisions, 5 acceptance criteria, 4 validation checks, and about 900 context characters. Workers must treat the packet as complete. If a required file/area is unavailable, they must return `ESCALATE_TO_PARENT` instead of guessing.

If the compiled packet is too large, do not spawn yet. Narrow the worker objective, reduce must-read files, or split by dependency phase. Never solve token pressure by broadcasting a larger packet.

## Step 8 — Batch tasks

Before spawning implementers, group work by ownership:

- Before any spawn, ask: can the root do this directly, or can the assigned worker do the full loop alone?
- Same user flow → one worker.
- Same package/module → one worker.
- Frontend + small API touch for the same feature → one `batch_implementer_medium`, not two agents.
- Independent read-only audits → parallel agents are okay.
- Independent write-heavy modules → separate workers only if file ownership does not overlap.
- Do not spawn a scout if the implementer must read the same files anyway; put those files in `MUST READ`.

Use `scripts/batch_tasks.py` when useful.

## Step 9 — Handoff validation and context coverage gate

Use `communication_router_low` only from the root session, and only when there are multiple Handoff Packets, conflicts, overlapping files, or many test results.

Validate leaf handoffs:

```bash
python skills/agent-orchestration-skill/scripts/handoff_validate.py <handoff-file>
```

For context-sensitive work, validate coverage against the worker Dispatch Packet. This avoids forcing one worker to cover the whole capsule:

```bash
python skills/agent-orchestration-skill/scripts/context_coverage_gate.py --dispatch <dispatch-file> --handoff <handoff-file>
```

Use `--capsule --full-capsule` only when a single worker was explicitly assigned every must-read item in the capsule.

Workers must not return `next_handoff`, `target_agent`, or child-agent plans unless explicitly requested by the user.

## Step 10 — Failure recovery

Do not respond to failure by blindly spawning another agent.

- Classify failure.
- Retry transient failures once.
- Send compile/test failures back to the same implementation owner with exact evidence.
- Escalate sandbox, permission, dirty-worktree, or scope conflicts to the root/user.
- Replan after repeated systematic failure.

Use:

```bash
python skills/agent-orchestration-skill/scripts/failure_classifier.py --file <failure-log>
```

## Step 11 — Verification gate

- XS/S: targeted tests or commands relevant to touched files.
- M: targeted tests + relevant lint/typecheck/build/integration gate.
- L/XL: full matrix, browser QA if UI flow changed, security/regression review if high-risk.

Use `scripts/test_matrix.py` and `scripts/quality_gate.py` for deterministic command discovery/execution.

## Step 12 — Worktree isolation when appropriate

For large tasks, dirty checkouts, or high-risk multi-file edits, consider isolated worktree planning before implementation:

```bash
python skills/agent-orchestration-skill/scripts/worktree_guard.py --root . --run-id <run_id>
```

Only create a worktree when it is clearly useful and safe.

## Step 13 — Durable learning and inspectable control room

At the end of meaningful runs, write a tiny notepad entry only if the insight will help future work:

```bash
python skills/agent-orchestration-skill/scripts/notepad.py --kind learnings --context "..." --insight "..." --impact "..."
```

Build an inspectable memory index when the run produced decisions, handoffs, or evidence that should be searchable:

```bash
python skills/agent-orchestration-skill/scripts/memory_index.py build --run-id <run_id>
```

Open the local control-room TUI or GUI when the user asks to inspect orchestration state:

```bash
aoc
# or
npx agentic-orchestration-control

# GUI
aoc gui
# or
npx agentic-orchestration-control gui
```

Initialize a production run ledger when the user explicitly asks to start an observable orchestration session before work begins:

```bash
aoc init --run-id <run_id> --task "<task title>"
```

Optional Codex app-server/codexui visibility is safe and opt-in:

```bash
aoc codex doctor
aoc gui --with-codex --codex-url http://127.0.0.1:<port>
```

Keep `.orchestration/` as the source of truth for orchestration state. Treat Codex app-server/codexui as optional live-runtime context, not as a replacement for the run ledger, Context Capsule, Dispatch Packets, Handoffs, or evidence.

Do not store raw logs, private reasoning, or generic summaries. The memory layer should explain what was remembered and why, using source artifacts and evidence references.


## Step 14 — Usage control and cost visibility

Track usage separately from orchestration state. The control room should show both:

- **real/imported usage** when available from local tools such as `ccusage`;
- **estimated orchestration pressure** derived from Dispatch Packets, Handoff Packets, Context Capsule slices, evidence files, and event volume.

Never treat estimated pressure as provider billing. It is a local signal for token waste, prompt bloat, and fan-out risk. Real token usage must come from a trusted source such as a Codex log export, `codex exec --json` metadata, or imported `ccusage` JSON.

For a run-scoped usage report including the derived estimate:

```bash
aoc usage --run-id <run_id>
```

For optional `ccusage` integration when it is installed:

```bash
aoc ccusage run --run-id <run_id>
```

Use budget checks before approving more workers, broad test matrices, high reasoning, or xhigh strategy:

```bash
aoc budget 12000 --run-id <run_id>
```

If usage pressure is high, prefer narrowing the Dispatch Packet, merging worker batches, downgrading reasoning, reusing previous results, or stopping at a gate before spawning more workers.

## Step 15 — Final output

Return a PR-ready summary:

- Classification and why the chosen agent count/reasoning was sufficient.
- Run ID if a ledger was created.
- Context Capsule path if used.
- Agents used and why.
- Files changed.
- Tests/commands/browser checks run and results.
- Failures and recovery decisions.
- Known residual risks or skipped checks.
- Follow-up only when genuinely useful.

## Reference modules

Read these only when needed:

- `references/spawn-economics.md`
- `references/thinking-router.md`
- `references/context-capsule.md`
- `references/context-coverage-gate.md`
- `references/dispatch-packet.md`
- `references/worker-contract.md`
- `references/test-gate.md`
- `references/skill-scope-policy.md`
- `references/leaf-worker-boundary.md`
- `references/control-plane.md`
- `references/control-room.md`
- `references/event-bus.md`
- `references/stop-gates.md`
- `references/memory-layer.md`
- `references/dag-plan-gate.md`
- `references/session-lifecycle.md`
- `references/failure-recovery.md`
- `references/worktree-isolation.md`
- `references/wisdom-notepads.md`
- `references/source-contract-proof.md`
- `references/evaluation-harness.md`
- `references/usage-control.md`
