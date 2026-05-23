# Agent Orchestration Skill

<p align="center">
  <em>Token-efficient subagent orchestration for coding agents: preserve context, avoid nested spawn, route reasoning deliberately, and verify every meaningful change.</em>
</p>

<p align="center">
  <a href="https://github.com/ZypherHQ/agent-orchestration-skill">
    <img src="https://img.shields.io/badge/GitHub-ZypherHQ%2Fagent--orchestration--skill-111827?style=for-the-badge&labelColor=0f172a" alt="GitHub repository" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge&labelColor=0f172a" alt="MIT License" />
  </a>
  <img src="https://img.shields.io/badge/Skill-Explicit%20Only-2563eb?style=for-the-badge&labelColor=0f172a" alt="Explicit only skill" />
  <img src="https://img.shields.io/badge/Subagents-Leaf%20Workers-f59e0b?style=for-the-badge&labelColor=0f172a" alt="Leaf worker subagents" />
</p>

<p align="center">
  <img src="./workflow-diagram.png" alt="Agent Orchestration Skill workflow diagram" width="100%" />
</p>

<p align="center">
  <sub>
    <a href="#why-this-exists">Why</a> ·
    <a href="#what-it-does">Features</a> ·
    <a href="#how-it-works">Workflow</a> ·
|    <a href="#install">Install</a> ·
    <a href="#quick-start">Quick Start</a> ·
    <a href="#usage">Usage</a> ·
    <a href="#repo-layout">Repo Layout</a> ·
    <a href="#utilities">Utilities</a> ·
    <a href="#faq">FAQ</a>
  </sub>
</p>

## Why this exists

Multi-agent coding can be powerful, but it often fails in predictable ways:

- too many subagents are spawned for work that only needs one focused pass;
- each subagent starts with a fresh context and misses important facts;
- workers try to delegate to other workers, causing nested spawn and token waste;
- large transcripts are copied into every agent instead of sending scoped context;
- reasoning effort is overused, especially for simple file discovery or small fixes;
- verification is weak, duplicated, or disconnected from the actual change.

**Agent Orchestration Skill** is a root-only control layer for coding agents. It helps the parent session decide whether orchestration is needed, which workers are useful, what context they receive, how much reasoning they should use, and how their output is validated.

It is **Codex-first**, but the operating model can be adapted to Claude Code, OpenCode, Cursor, and other agentic coding environments.

## What it does

- **Explicit-only activation** — the skill should run only when you invoke `$agent-orchestration-skill`.
- **Root-only orchestration** — the parent session coordinates; spawned workers execute bounded tasks.
- **Leaf-worker boundaries** — workers must not invoke skills, spawn child agents, or route tasks to other workers.
- **Context Capsule** — preserves task-critical context without turning the prompt into a transcript dump.
- **Scoped Dispatch Packets** — each worker receives only the relevant context slice for its assignment.
- **Context Coverage Gate** — workers must confirm required files/context before editing.
- **Token-aware spawning** — avoids one-agent-per-file fan-out and blocks unnecessary waves.
- **Reasoning router** — uses low, medium, high, or xhigh reasoning only where it makes sense.
- **Batched execution** — groups related work by surface, ownership, module, or user flow.
- **Run Ledger** — records phases, dispatches, handoffs, evidence, failures, and recovery decisions.
- **Dependency-aware planning** — builds compact DAG plans for larger tasks.
- **Plan Gate** — rejects vague, circular, or unverifiable execution plans.
- **Budget Governor** — checks orchestration cost before spawning workers.
- **Handoff Validator** — rejects noisy handoffs, nested delegation leakage, and missing evidence.
- **Failure Recovery** — classifies failures before retrying, replanning, or escalating.
- **Aggressive verification** — lint, typecheck, unit tests, integration tests, build checks, browser QA, and re-audit where relevant.
- **Durable Notepads** — stores useful learnings and decisions without saving noisy transcripts.
- **PR-ready reporting** — summarizes files changed, agents used, commands run, evidence, failures, and residual risks.

## How it works

```text
User invokes $agent-orchestration-skill
        ↓
Root orchestrator classifies the task
        ↓
Decides: no worker, one worker, or controlled multi-worker plan
        ↓
Preserves context in a Context Capsule
        ↓
Compiles scoped Dispatch Packets
        ↓
Spawns only useful leaf workers
        ↓
Workers pass Context Coverage, execute, validate, and hand off
        ↓
Handoffs are validated and merged into the Run Ledger
        ↓
Failures are classified before retry/replan/escalation
        ↓
Verification, re-audit, and PR-ready report
```

The core rule is simple:

> Do not spawn more agents, pass more context, or use more reasoning than the task actually needs.

## Context without token bloat

The system separates **memory** from **prompt payload**.

| Layer | Purpose | Token behavior |
| --- | --- | --- |
| `Context Capsule` | Persistent task-critical context | Stored on disk; not broadcast in full. |
| `Dispatch Packet` | Worker-specific context slice | Short, scoped, and capped. |
| `Context Coverage Gate` | Proof the worker read required context | Prevents blind edits. |
| `Handoff Packet` | Structured worker result | Concise evidence, no raw logs. |
| `Run Ledger` | Operational state for the run | Tracks phases, evidence, failures, and decisions. |
| `Durable Notepads` | Reusable learnings | Saves only durable knowledge, not transcripts. |

This prevents the common failure mode where every subagent receives a huge transcript but still misses the one file or decision that matters.

## Reasoning policy

Reasoning effort is selected by task depth, not by habit.

| Reasoning | Use for | Avoid for |
| --- | --- | --- |
| `low` | scouting, file discovery, source checks, exact command execution | complex implementation or ambiguous debugging |
| `medium` | normal code writing, small/medium fixes, batch implementation, browser QA, deep verification | architecture-heavy planning |
| `high` | complex implementation, difficult business logic, security/data/concurrency-sensitive work | trivial patches and simple test runs |
| `xhigh` | large architecture, feature structuring, critical ambiguity, deep planning | default implementation, one-file fixes, basic scouting |

`xhigh` is intentionally rare. It is most useful for structuring difficult problems, not for routine edits.

## Install

**Prerequisites:** Node.js 18+ and npm. `npx` is included with npm.

Install the skill with the Agent Skills CLI:

```bash
npx skills add https://github.com/ZypherHQ/agent-orchestration-skill --skill "agent-orchestration-skill"
```

Or install all skills exposed by this repository:

```bash
npx skills add https://github.com/ZypherHQ/agent-orchestration-skill
```

This repository is designed to expose a single orchestration skill plus supporting references and deterministic utilities.

## Quick Start

This skill is designed for tasks that benefit from controlled multi-agent orchestration — not for every change. Use it when the work is complex enough to need multiple workers, scoped context, and verifiable handoffs.

### Classify your task first

Before invoking the skill, classify the task size:

```bash
python skills/scripts/orchestration_decider.py \
  --task "implement user authentication flow" \
  --known-files 12 \
  --surfaces frontend,backend,tests \
  --risk medium \
  --ambiguity low
```

The decider outputs a recommended task size (`XS`–`XL`), reasoning effort, and worker count. For `XS` and `S` tasks, you often don't need the skill at all.

### Run a medium task with orchestration

Once you have a task that warrants orchestration:

**1. Initialize a Context Capsule** to preserve task-critical context:

```bash
python skills/scripts/context_capsule.py init \
  --task "implement user authentication flow" \
  --out .orchestration/context_capsule.json
```

**2. Plan with a DAG** for tasks involving multiple surfaces:

```bash
python skills/scripts/dag_planner.py \
  --task "implement user authentication flow" \
  --size M \
  --surfaces frontend,backend,tests \
  --out .orchestration/plan.json
```

**3. Gate the plan** before spawning workers:

```bash
python skills/scripts/plan_gate.py .orchestration/plan.json
```

**4. Compile a Dispatch Packet** for each worker:

```bash
python skills/scripts/dispatch_compiler.py \
  --task "backend auth endpoints" \
  --must-read backend/auth.go backend/auth_test.go \
  --acceptance "POST /auth/login returns 200 with token" \
  --validation "go test ./backend/... -run Auth" \
  --capsule .orchestration/context_capsule.json
```

**5. Run a quality gate** after workers complete:

```bash
python skills/scripts/quality_gate.py "go test ./..." "go build ./..."
```

### Small tasks — skip the skill

For `XS` and `S` tasks, direct coding is cheaper and cleaner:

```
Fix the typo in src/lib.rs.
Run cargo fmt --check.
```

The skill is explicit-only. It does not activate unless you invoke `$agent-orchestration-skill`.

## Usage

Invoke it explicitly when you want controlled orchestration:

```text
Use $agent-orchestration-skill for this task.

Run in token-efficient control-plane mode.
Preserve context with a Context Capsule.
Spawn only useful leaf workers.
Do not spawn one agent per file.
Use low for scouting, medium for normal coding/testing, high for complex implementation, and xhigh only for large architecture/planning.
```

For small tasks, do not invoke the skill. A normal direct coding run is usually cheaper and cleaner.

```text
Fix the typo in src/lib.rs.
Run cargo fmt --check.
```

## Workflow by task size

| Size | Typical behavior |
| --- | --- |
| `XS` | No subagents. Minimal direct workflow. No heavy ledger/DAG. |
| `S` | Zero or one worker if useful. Targeted validation only. |
| `M` | Small number of batched workers. Context Capsule + scoped dispatch. |
| `L` | Run Ledger, DAG plan, Plan Gate, Budget Governor, multiple bounded phases. |
| `XL` | Strategy planning, worktree isolation planning, strict budget checks, staged verification and re-audit. |

## Worker contract

Every spawned worker is a leaf worker.

Workers must:

- read the assigned Dispatch Packet;
- inspect required files before editing;
- pass Context Coverage before making changes;
- execute a complete bounded loop: inspect → patch → validate → handoff;
- return concise evidence and blockers;
- escalate to the parent when context is missing or scope is unsafe.

Workers must not:

- invoke `$agent-orchestration-skill`;
- invoke repo skills;
- spawn child agents;
- ask another worker to take over;
- emit `target_agent`, `next_handoff`, or nested routing instructions;
- broadcast raw logs as handoff content.

## Repo layout

| Path | Purpose |
| --- | --- |
| `skills/SKILL.md` | Root-only orchestration contract and operating instructions. |
| `skills/agents/openai.yaml` | Skill metadata and explicit invocation policy. |
| `skills/references/` | Focused policy references loaded only when needed. |
| `skills/scripts/` | Deterministic utilities for planning, context, budget, validation, testing, and state. |
| `workflow-diagram.png` | Visual overview shown at the top of this README. |

## Utilities

The scripts are model-free helpers that keep the orchestration flow structured and auditable.

| Script | Purpose |
| --- | --- |
| `orchestration_decider.py` | Recommends task size, reasoning effort, agent count, and verification level. |
| `context_capsule.py` | Creates, updates, renders, slices, and measures the persistent Context Capsule. |
| `dispatch_compiler.py` | Builds short scoped Dispatch Packets from explicit fields or JSON. |
| `context_coverage_gate.py` | Checks whether a worker covered required context before editing. |
| `batch_tasks.py` | Groups related files/tasks to avoid one-agent-per-file fan-out. |
| `budget_governor.py` | Flags over-orchestration before spawning workers. |
| `dag_planner.py` | Builds compact dependency-aware plans for larger tasks. |
| `plan_gate.py` | Rejects invalid, vague, circular, or unverifiable plans. |
| `run_ledger.py` | Creates and updates `.orchestration/runs/<run_id>/` state. |
| `handoff_validate.py` | Validates handoffs for required fields, coverage, evidence, and forbidden routing. |
| `handoff_router.py` | Merges handoffs and detects overlapping file ownership. |
| `failure_classifier.py` | Maps failures to retry, fix, replan, or escalation. |
| `test_matrix.py` | Detects common lint, typecheck, build, test, docker, and browser verification commands. |
| `quality_gate.py` | Runs verification commands and writes JSON/Markdown evidence. |
| `worktree_guard.py` | Plans or creates isolated git worktrees for large or dirty-checkout work. |
| `notepad.py` | Stores compact durable learnings, decisions, issues, and verification notes. |
| `token_budget_linter.py` | Detects stale always-on orchestration patterns and token-heavy config. |
| `codex_leaf_exec.sh` | Launches `codex exec` in hard leaf-worker mode with multi-agent tools disabled. |

## Example commands

Classify a task:

```bash
python skills/scripts/orchestration_decider.py \
  --task "fix flaky checkout flow" \
  --known-files 5 \
  --surfaces frontend,backend,tests \
  --risk medium \
  --ambiguity medium
```

Create a Context Capsule:

```bash
python skills/scripts/context_capsule.py init \
  --task "fix flaky checkout flow" \
  --out .orchestration/context_capsule.json
```

Compile a scoped Dispatch Packet:

```bash
python skills/scripts/dispatch_compiler.py \
  --task "fix checkout retry state" \
  --must-read src/checkout.ts tests/checkout.spec.ts \
  --acceptance "retry state is reset after successful payment" \
  --validation "npm run test -- checkout" \
  --capsule .orchestration/context_capsule.json
```

Generate and gate a plan:

```bash
python skills/scripts/dag_planner.py \
  --task "fix flaky checkout flow" \
  --size M \
  --surfaces frontend,backend,tests \
  --out .orchestration/plan.json

python skills/scripts/plan_gate.py .orchestration/plan.json
```

Run a quality gate:

```bash
python skills/scripts/quality_gate.py "npm run test" "npm run build"
```

Run a Codex verifier as a hard leaf worker:

```bash
skills/scripts/codex_leaf_exec.sh . \
  "LEAF_EXEC_MODE. Run the requested verification commands only. Do not edit files except normal build artifacts. Return a concise YAML Handoff Packet."
```

## References

| Reference file | Focus |
| --- | --- |
| `control-plane.md` | Run ledger, event tracking, evidence, and durable notes. |
| `context-capsule.md` | Context preservation without full-context broadcast. |
| `context-coverage-gate.md` | Required file/context coverage before edits. |
| `dag-plan-gate.md` | Compact DAG requirements and executable-plan checks. |
| `dispatch-packet.md` | Scoped worker instructions and context-diet rules. |
| `exec-leaf-mode.md` | Hard leaf-mode pattern for `codex exec` verification jobs. |
| `failure-recovery.md` | Retry caps, replan, and escalation policy. |
| `leaf-worker-boundary.md` | Multi-layer containment for spawned workers. |
| `session-lifecycle.md` | Resume-vs-respawn policy and duplicate-spawn checks. |
| `skill-scope-policy.md` | Why workers must not activate repo skills. |
| `spawn-economics.md` | Cost model and default worker caps by task size. |
| `test-gate.md` | Verification expectations by task size and risk. |
| `thinking-router.md` | Reasoning-effort selection and anti-patterns. |
| `wisdom-notepads.md` | Durable notes instead of transcript bloat. |
| `worker-contract.md` | Expected worker loop and handoff structure. |
| `worktree-isolation.md` | When to plan or create isolated git worktrees. |

## FAQ

### Does the skill run automatically?

No. It is designed for explicit invocation only:

```text
Use $agent-orchestration-skill for this task.
```

### Does this replace normal coding runs?

No. It is for tasks that benefit from controlled orchestration. Small single-file changes are often better handled directly.

### Can a spawned worker use the skill?

No. The skill is root-only. Workers receive scoped Dispatch Packets and must remain leaf workers.

### Does the Context Capsule increase token usage?

Not when used correctly. The full capsule is stored on disk. Workers receive only a short relevant slice, plus required files and acceptance criteria.

### Do the scripts call models?

No. They are deterministic utilities for classification, planning, budget checks, validation, state, and evidence handling.

### Why not spawn one agent per file?

Because it usually wastes tokens and fragments ownership. This skill prefers batched work by surface, module, user flow, or implementation owner.

### When should I use `xhigh` reasoning?

Only for unusually large, ambiguous, or architecture-heavy problems. It should not be the default for implementation, testing, or file discovery.

## License

[MIT License](LICENSE)
