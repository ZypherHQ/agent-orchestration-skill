# Agentic Orchestration Control

<p align="center">
  <em>Root-only, token-aware Codex orchestration with leaf-worker guards, DAG planning, run ledger state, and deterministic verification utilities.</em>
</p>

<p align="center">
  <a href="https://github.com/ZypherHQ/agent-orchestration-skill">
    <img src="https://img.shields.io/badge/GitHub-ZypherHQ%2Fagent--orchestration--skill-111827?style=for-the-badge&labelColor=0f172a" alt="GitHub repository" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge&labelColor=0f172a" alt="MIT License" />
  </a>
  <img src="https://img.shields.io/badge/Skill-1-2563eb?style=for-the-badge&labelColor=0f172a" alt="One installable skill" />
  <img src="https://img.shields.io/badge/Utilities-16-f59e0b?style=for-the-badge&labelColor=0f172a" alt="Sixteen utility scripts" />
</p>

Portable **Agent Skill** for Codex root sessions that need disciplined orchestration instead of prompt fan-out. This repo packages a single root-only skill, reference policies, an OpenAI agent manifest, and deterministic helper scripts for classification, batching, planning, budget checks, dispatch compilation, handoff validation, verification, failure recovery, and worktree safety.

The design goal is simple: keep the parent session in control, keep leaf workers bounded, and keep token usage proportional to task size.

<p align="center"><sub><a href="#installing">Install</a> · <a href="#skill">Skill</a> · <a href="#what-it-enforces">Guardrails</a> · <a href="#workflow">Workflow</a> · <a href="#repo-layout">Repo Layout</a> · <a href="#scripts">Scripts</a> · <a href="#references">References</a> · <a href="#common-questions">FAQ</a> · <a href="#license">License</a></sub></p>

## Installing

The [`npx skills add`](https://github.com/vercel-labs/agent-skills) CLI scans the `skills/` directory in this repo.

```bash
npx skills add https://github.com/ZypherHQ/agent-orchestration-skill
```

Install only this skill by its `name:` field from frontmatter:

```bash
npx skills add https://github.com/ZypherHQ/agent-orchestration-skill --skill "agentic-orchestration-control"
```

You can also copy `skills/SKILL.md` into a repo or paste it directly into a Codex workflow when you want the orchestration policy without the installer.

## Skill

This repository exposes one installable skill:

| Skill file | Install name | Description |
| --- | --- | --- |
| `skills/SKILL.md` | `agentic-orchestration-control` | Root orchestrator only. Token-aware Codex workflow with leaf workers, DAG gating, state ledger, retry policy, and no nested delegation. |

The OpenAI-facing manifest at `skills/agents/openai.yaml` labels the skill as **Agentic Orchestration Control v3** and disables implicit invocation so it only runs when explicitly requested.

## What It Enforces

- Root session only. Spawned workers must not invoke this skill, invoke repo skills, or spawn child agents.
- No one-agent-per-file fan-out. Work is batched by surface, ownership, or user flow.
- No `xhigh` by default. Reasoning effort must match ambiguity and risk.
- No duplicate waves. Active or completed work should be resumed or reused before respawning.
- No raw-log broadcast. Workers return compact Handoff Packets with evidence and blockers only.
- No partial write workers. Implementation workers are expected to inspect, patch, validate, and hand off in one bounded loop.
- No blind retries. Failures are classified before retry, replan, or escalation.

## Workflow

1. Classify the task by file count, surfaces, ambiguity, risk, verification needs, and parallel value.
2. Pick the smallest orchestration mode that fits: `XS`, `S`, `M`, `L`, or `XL`.
3. For non-trivial work, initialize a run ledger under `.orchestration/runs/<run_id>/`.
4. For `M` and above, generate a compact dependency-aware DAG and reject it if the plan is not executable.
5. Compile short Dispatch Packets for bounded leaf workers instead of broadcasting the full root plan.
6. Run verification matched to scope, classify failures, and record durable learnings only when they will matter next time.

## Repo Layout

| Path | Purpose |
| --- | --- |
| `skills/SKILL.md` | Main root-only skill contract and operating instructions. |
| `skills/agents/openai.yaml` | Display metadata and explicit invocation policy for the skill. |
| `skills/references/` | Focused policy notes for specific orchestration concerns. |
| `skills/scripts/` | Deterministic helper scripts for planning, routing, gating, validation, and state. |

## Scripts

These utilities are deliberately model-free. They provide deterministic structure around the orchestration flow.

| Script | Purpose |
| --- | --- |
| `skills/scripts/orchestration_decider.py` | Recommends task size, reasoning effort, default agent set, and verification level from task metadata. |
| `skills/scripts/batch_tasks.py` | Groups files or tasks into fewer implementation batches by surface and ownership. |
| `skills/scripts/budget_governor.py` | Applies a simple point budget to catch obvious over-orchestration before spawning. |
| `skills/scripts/dag_planner.py` | Builds a compact phase DAG for `M/L/XL` work. |
| `skills/scripts/plan_gate.py` | Rejects plans that are vague, invalid, circular, or missing worker policy and verification. |
| `skills/scripts/dispatch_compiler.py` | Compiles short Dispatch Packets for subagents from explicit packet fields or JSON. |
| `skills/scripts/run_ledger.py` | Creates and updates the persistent run ledger under `.orchestration/runs/`. |
| `skills/scripts/handoff_validate.py` | Validates Handoff Packets for required fields, forbidden routing text, and excessive length. |
| `skills/scripts/handoff_router.py` | Merges multiple handoffs and detects overlapping file ownership. |
| `skills/scripts/failure_classifier.py` | Maps failure text to retry, fix, escalation, or replan actions. |
| `skills/scripts/test_matrix.py` | Detects common project lint, typecheck, test, build, and docker verification commands. |
| `skills/scripts/quality_gate.py` | Executes verification commands and writes JSON plus Markdown evidence reports. |
| `skills/scripts/worktree_guard.py` | Plans or creates isolated git worktrees for larger or dirty-checkout runs. |
| `skills/scripts/notepad.py` | Appends compact durable learnings, decisions, issues, or verification notes. |
| `skills/scripts/token_budget_linter.py` | Lints installed repo skills, worker agent configs, and stale orchestration patterns. |
| `skills/scripts/codex_leaf_exec.sh` | Launches `codex exec` in hard leaf-worker mode with multi-agent tools disabled. |

### Example commands

Classify a task:

```bash
python skills/scripts/orchestration_decider.py \
  --task "fix flaky checkout flow" \
  --known-files 5 \
  --surfaces frontend,backend,tests \
  --risk medium \
  --ambiguity medium
```

Create a ledger entry:

```bash
python skills/scripts/run_ledger.py init --task "fix flaky checkout flow"
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

Discover likely verification commands:

```bash
python skills/scripts/test_matrix.py --root .
```

Run a quality gate:

```bash
python skills/scripts/quality_gate.py "npm run test" "npm run build"
```

## References

The reference files are intentionally short and specialized. They exist so the root session can load only the policy needed for the current situation.

| Reference file | Focus |
| --- | --- |
| `skills/references/control-plane.md` | Run ledger structure, event tracking, and durable notes. |
| `skills/references/dag-plan-gate.md` | Compact DAG requirements and executable-plan gate rules. |
| `skills/references/dispatch-packet.md` | Required Dispatch Packet fields and context-diet rules. |
| `skills/references/evaluation-harness.md` | Smoke-test scenarios for the orchestration system itself. |
| `skills/references/exec-leaf-mode.md` | Hard leaf-mode launch pattern for `codex exec` verification jobs. |
| `skills/references/failure-recovery.md` | Retry caps and escalation policy for repeated failures. |
| `skills/references/leaf-worker-boundary.md` | Multi-layer containment policy for spawned workers. |
| `skills/references/session-lifecycle.md` | Resume-vs-respawn policy and duplicate-spawn checks. |
| `skills/references/skill-scope-policy.md` | Why workers must not activate repo skills or orchestration internals. |
| `skills/references/source-contract-proof.md` | Contract-first rule for local source and upstream docs. |
| `skills/references/spawn-economics.md` | Cost model and default agent caps by task size. |
| `skills/references/test-gate.md` | Verification expectations for `XS/S`, `M`, and `L/XL` work. |
| `skills/references/thinking-router.md` | Reasoning-effort selection rules and anti-patterns. |
| `skills/references/wisdom-notepads.md` | Rules for durable notes instead of transcript bloat. |
| `skills/references/worker-contract.md` | Expected loop and handoff structure for read/write workers. |
| `skills/references/worktree-isolation.md` | When to plan or create isolated git worktrees. |

## Common Questions

**What problem does this solve?**  
It gives a Codex root session a disciplined control plane so multi-step work does not collapse into recursive delegation, oversized prompts, duplicate agents, or weak verification.

**Can a spawned worker use this skill?**  
No. The entire design assumes the skill is root-only and workers receive only a bounded Dispatch Packet.

**Do the scripts call models?**  
No. The scripts are deterministic utilities for classification, planning, validation, state, and evidence handling.

**When should I create a ledger and DAG?**  
Usually for `M`, `L`, and `XL` tasks. Tiny `XS/S` work should stay lightweight unless there is a real need for persistent state.

**What is the safest way to run `codex exec` as a verifier?**  
Use `skills/scripts/codex_leaf_exec.sh`, which disables multi-agent tools and caps the exec process as a leaf worker.

**Does this repo include multiple installable skills?**  
No. It exposes one orchestration skill plus supporting references and tooling.

## License

[MIT License](LICENSE)
