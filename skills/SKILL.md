---
name: agentic-orchestration-control
description: ROOT ORCHESTRATOR ONLY. Explicit-use token-aware Codex workflow with leaf workers, DAG gating, state ledger, retry policy, and no nested delegation.
---

# Agentic Orchestration Control v3.0 — Control Plane + Token Efficiency

Use this skill only in the root Codex session. Never instruct spawned subagents to invoke this or any other repo skill, and never instruct a spawned subagent to spawn more agents.

## Step 0 — Runtime mode guard

This skill is root-only. Before using it, confirm the current session is not a leaf `codex exec` verification job. If the prompt says `You are a subagent`, `verification subagent`, `Run exactly these commands`, `Do not edit files`, or `Return only a YAML Handoff Packet`, do **not** use this skill, do **not** spawn agents, and perform only the bounded leaf task.

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

Read `references/exec-leaf-mode.md` when diagnosing subagents that try to spawn other agents.

## Prime directive

Act as a **task compiler and control-plane operator**, not a prompt broadcaster. Classify the work, choose the cheapest adequate reasoning tier, batch related actions, compile minimal Dispatch Packets, track state, and collect concise Handoff Packets.

## Hard constraints

1. **Root-only skill:** this skill is for the parent orchestrator. Subagents receive plain dispatch text, not skill names.
2. **No one-agent-per-file fan-out:** batch related files by user flow, module, package, or owner.
3. **No xhigh by default:** xhigh is reserved for hard ambiguity/high risk, not routine patches.
4. **No redundant waves:** if one worker can inspect, patch, and test a small change, use one worker.
5. **No raw output broadcast:** route only facts, blockers, file ownership, commands run, failures, and next actions.
6. **Write workers must complete a loop:** inspect → patch → targeted validation → Handoff Packet.
7. **Read-heavy work can be parallel; write-heavy work should be serialized or batched carefully.**
8. **Leaf-worker boundary:** only the root session may spawn agents. Spawned workers must not delegate; they return `ESCALATE_TO_PARENT` when they need another specialist.
9. **State before spawn:** for M/L/XL, create a run ledger and check it before spawning or respawning.
10. **Plan gate before broad work:** M/L/XL tasks need a dependency-aware plan and binary executable gate before implementation.

## Step 1 — Classify before spawning

Classify the task using these dimensions:

- Known files: 0, 1, 2–3, 4–8, 9+
- Surfaces: frontend, backend, database, infra, docs, tests, browser, security
- Ambiguity: low, medium, high
- Risk: low, medium, high, critical
- Required evidence: none, targeted test, full test matrix, browser QA, security review
- Parallel value: low, medium, high
- Worktree state: clean, dirty, unknown

Use `scripts/orchestration_decider.py` when useful.

## Step 2 — Pick the minimum viable orchestration mode

| Mode | Criteria | Agents |
|---|---|---|
| XS | Known one-file or tiny low-risk fix | `micro_implementer_low` only |
| S | 1–3 related files, low/medium ambiguity | `micro_implementer_low` or `batch_implementer_medium`; optional `test_runner_low` |
| M | 3–8 files or unclear owner/root cause | short DAG; `code_mapper_medium` then `batch_implementer_medium`; verifier |
| L | Multi-surface feature/fix, 8–20 files | DAG + state ledger + bounded mapper/research + 1–2 implementers + verification |
| XL | Ambiguous high-risk auth/payment/security/data/concurrency/prod incident | DAG + plan gate + `deep_debugger_xhigh` or high reviewers, then scoped implementers |

## Step 3 — Create control-plane state when needed

For XS/S, do not create unnecessary artifacts unless useful. For M/L/XL, initialize a run ledger:

```bash
python .agents/skills/agentic-orchestration-control/scripts/run_ledger.py init --task "<task>"
```

Use the ledger to record phases, dispatches, Handoff Packets, claimed files, evidence, failures, and final status. Before spawning any worker, check the ledger for duplicate active/completed work. Read `references/control-plane.md` and `references/session-lifecycle.md` when needed.

## Step 4 — Build a DAG only when orchestration is justified

Do not use a DAG for tiny tasks. For M/L/XL, create a compact dependency-aware DAG with at most 7 phases:

```bash
python .agents/skills/agentic-orchestration-control/scripts/dag_planner.py --task "<task>" --size M --surfaces frontend,backend > .orchestration/plan.json
python .agents/skills/agentic-orchestration-control/scripts/plan_gate.py .orchestration/plan.json
```

If the gate rejects the plan, fix the plan before spawning. The plan gate checks executability, dependencies, acceptance criteria, validation, and worker leaf policy. Read `references/dag-plan-gate.md` when needed.

## Step 5 — Enforce leaf-worker spawning boundary

Before every spawn, verify the selected custom agent has all three safeguards:

```text
[features].multi_agent = false
[agents].max_depth = 0
LEAF WORKER CONTRACT in developer_instructions
```

Do not rely on `agents.max_depth = 1` alone. If a worker returns `ESCALATE_TO_PARENT`, the root decides whether to spawn another agent, resume the same worker, or continue serially.

## Step 6 — Thinking/reasoning router

- `low`: known file, straightforward code edit, targeted test, mechanical fix.
- `medium`: normal feature/fix, several related files, moderate debugging, browser QA.
- `high`: complex logic, edge cases, security review, migrations, broad regression audit.
- `xhigh`: only when root cause is unknown and risk is high/critical, or the task involves security/payment/auth/data/concurrency across multiple surfaces.

Do not use xhigh for a single-file fix unless that single file is security/payment/auth/data/concurrency critical or lower-effort attempts failed with evidence.

Use `scripts/budget_governor.py` to catch obvious over-orchestration before spawning:

```bash
python .agents/skills/agentic-orchestration-control/scripts/budget_governor.py --size M --agents code_mapper_medium,batch_implementer_medium,verification_engine_medium --reasoning medium
```

## Step 7 — Compile Dispatch Packets

Dispatch Packets must be short and targeted. Do not paste the whole plan. Include:

```text
ROLE:
MODE / REASONING BUDGET:
OBJECTIVE:
SCOPE OWNERSHIP:
FILES / AREAS ALLOWED:
FILES / AREAS FORBIDDEN:
CONTEXT DIGEST:
TASK BUNDLE:
ACCEPTANCE CRITERIA:
VALIDATION REQUIRED:
STOP CONDITIONS:
SKILL / DELEGATION POLICY: Do not invoke skills. Do not spawn, request, recommend, or plan child subagents. If more agents are needed, return ESCALATE_TO_PARENT to the root. Treat this packet as complete.
OUTPUT: concise Handoff Packet only.
```

Use `scripts/dispatch_compiler.py` when useful.

## Step 8 — Batch tasks

Before spawning implementers, group work by ownership:

- Same user flow → one worker.
- Same package/module → one worker.
- Frontend + small API touch for the same feature → one `batch_implementer_medium`, not two agents.
- Independent read-only audits → parallel agents are okay.
- Independent write-heavy modules → separate workers only if file ownership does not overlap.

Use `scripts/batch_tasks.py` when useful.

## Step 9 — Communication routing and handoff validation

Use `communication_router_low` only from the root session, and only when there are multiple Handoff Packets, conflicting claims, overlapping files, or many test results. For a one-worker XS/S task, the root can consume the Handoff Packet directly.

Validate leaf handoffs if they are suspicious, too long, or contain routing fields:

```bash
python .agents/skills/agentic-orchestration-control/scripts/handoff_validate.py <handoff-file>
```

Workers must not return `next_handoff`, `target_agent`, or any child-agent plan unless explicitly requested by the user.

## Step 10 — Failure recovery

Do not respond to failure by blindly spawning another agent.

- Classify failure.
- Retry transient failures once.
- Send compile/test failures back to the same implementation owner with exact evidence.
- Escalate sandbox, permission, dirty-worktree, or scope conflicts to the root/user.
- Replan after repeated systematic failure.

Use:

```bash
python .agents/skills/agentic-orchestration-control/scripts/failure_classifier.py --file <failure-log>
```

Read `references/failure-recovery.md` when needed.

## Step 11 — Verification gate

- XS/S: targeted tests or commands relevant to touched files.
- M: targeted tests + lint/typecheck/build where relevant.
- L/XL: full matrix, browser QA if UI flow changed, security/regression review if high-risk.

Use `scripts/test_matrix.py` and `scripts/quality_gate.py` for deterministic command discovery/execution.

## Step 12 — Worktree isolation when appropriate

For L/XL, dirty checkouts, or high-risk multi-file edits, consider isolated worktree planning before implementation:

```bash
python .agents/skills/agentic-orchestration-control/scripts/worktree_guard.py --root . --run-id <run_id>
```

Only create a worktree when it is clearly useful and safe. Read `references/worktree-isolation.md` when needed.

## Step 13 — Durable learning, not transcript bloat

At the end of meaningful runs, write a tiny notepad entry only if the insight will help future work:

```bash
python .agents/skills/agentic-orchestration-control/scripts/notepad.py --kind learnings --context "..." --insight "..." --impact "..."
```

Do not store raw logs, private reasoning, or generic summaries. Read `references/wisdom-notepads.md` when needed.

## Step 14 — Final output

Return a PR-ready summary:

- Classification and why the chosen agent count/reasoning was sufficient.
- Run ID if a ledger was created.
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
- `references/dispatch-packet.md`
- `references/worker-contract.md`
- `references/test-gate.md`
- `references/skill-scope-policy.md`
- `references/leaf-worker-boundary.md`
- `references/control-plane.md`
- `references/dag-plan-gate.md`
- `references/session-lifecycle.md`
- `references/failure-recovery.md`
- `references/worktree-isolation.md`
- `references/wisdom-notepads.md`
- `references/source-contract-proof.md`
- `references/evaluation-harness.md`
