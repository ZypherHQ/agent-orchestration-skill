# 02_SETUP_AND_BASELINE.md

## Setup & Baseline — agent-orchestration-skill

### Repository Overview

- **Upstream**: https://github.com/ZypherHQ/agent-orchestration-skill
- **Language**: Python (17 scripts, 1 shell script)
- **License**: MIT
- **Created**: 2026-05-20
- **Last push**: 2026-05-22
- **Stars**: 60 | **Forks**: 1 (parent)

### What It Is

A Codex-first multi-agent orchestration skill providing token-efficient subagent orchestration for coding agents. Explicit-only activation, root-only orchestration, leaf-worker boundaries.

### Directory Structure

```
agent-orchestration-skill/
├── README.md                          # Full documentation
├── LICENSE                            # MIT
├── config.toml                        # Default Codex config
├── workflow-diagram.png               # Visual overview
├── agents/                            # 14 agent profile TOMLs
│   ├── batch-implementer-medium.toml
│   ├── browser-qa-medium.toml
│   ├── code-mapper-low.toml
│   ├── communication-router-low.toml
│   ├── complex-implementer-high.toml
│   ├── docs-researcher-low.toml
│   ├── micro-implementer-medium.toml
│   ├── pr-finalizer-low.toml
│   ├── regression-reviewer-medium.toml
│   ├── scope-scout-low.toml
│   ├── security-reviewer-high.toml
│   ├── strategy-architect-xhigh.toml
│   ├── test-runner-low.toml
│   └── verification-engine-medium.toml
└── skills/
    ├── SKILL.md                       # Root orchestration contract
    ├── agents/openai.yaml             # Skill metadata
    ├── references/                    # 16 policy reference docs
    │   ├── context-capsule.md
    │   ├── context-coverage-gate.md
    │   ├── control-plane.md
    │   ├── dag-plan-gate.md
    │   ├── dispatch-packet.md
    │   ├── evalation-harness.md       # NOTE: typo in filename
    │   ├── exec-leaf-mode.md
    │   ├── failure-recovery.md
    │   ├── leaf-worker-boundary.md
    │   ├── session-lifecycle.md
    │   ├── skill-scope-policy.md
    │   ├── source-contract-proof.md
    │   ├── spawn-economics.md
    │   ├── test-gate.md
    │   ├── thinking-router.md
    │   ├── wisdom-notepads.md
    │   ├── worker-contract.md
    │   └── worktree-isolation.md
    └── scripts/                       # 15 Python utilities + 1 shell
        ├── batch_tasks.py
        ├── budget_governor.py
        ├── codex_leaf_exec.sh
        ├── context_capsule.py
        ├── context_coverage_gate.py
        ├── dag_planner.py
        ├── dispatch_compiler.py
        ├── failure_classifier.py
        ├── handoff_router.py
        ├── handoff_validate.py
        ├── notepad.py
        ├── orchestration_decider.py
        ├── plan_gate.py
        ├── quality_gate.py
        ├── run_ledger.py
        ├── test_matrix.py
        ├── token_budget_linter.py
        └── worktree_guard.py
```

### Test/Validation Status

- **pytest**: 0 tests collected (no test suite present)
- **TOML validity**: All 14 agent profiles + config.toml are valid
- **No implicit test harness** — evaluation is manual per `evaluation-harness.md`

### Baseline Scripts (spot-checked)

| Script | Status | Notes |
|--------|--------|-------|
| `orchestration_decider.py` | ✅ Loads | Deterministic classification utility |
| `context_capsule.py` | ✅ Loads | Init/slice/render/measure operations |
| `dispatch_compiler.py` | ✅ Loads | Packet compilation with caps |
| `batch_tasks.py` | ✅ Loads | File grouping utility |
| `run_ledger.py` | ✅ Loads | Run state management |
| `handoff_validate.py` | ✅ Loads | Handoff validation |
| `plan_gate.py` | ✅ Loads | Plan rejection logic |

### Key Config Values (config.toml)

```toml
[features]
multi_agent = true

[agents]
max_threads = 4        # Lowered from Codex default to avoid fan-out
max_depth = 1          # Root -> child fallback only
job_max_runtime_seconds = 2400

# Reasoning defaults
model_reasoning_effort = "medium"
plan_mode_reasoning_effort = "high"
model_verbosity = "medium"
model_reasoning_summary = "concise"
```

### Observed Issues

1. **No test suite** — pytest collects 0 items. No unit tests for scripts.
2. **evaluation-harness.md has typo** — `evalation-harness.md` (missing 'u')
3. **No CI/CD** — no GitHub Actions workflow visible
4. **New repo** (2 days old) — limited history to draw patterns from

### Safe to Operate

- All TOML configs parse correctly
- All Python scripts import without error
- No TODO/FIXME/XXX/HACK markers found
- No broken external links detected