# 01_REPO_MAP.md

## What It Does

**Agent Orchestration Skill** is a root-only control layer for coding agents (Codex-first, adaptable to Claude Code, OpenCode, Cursor, etc.). It helps the parent session decide:
- Whether orchestration is needed
- Which workers are useful
- What context they receive
- How much reasoning they should use
- How their output is validated

The core principle: **Do not spawn more agents, pass more context, or use more reasoning than the task actually needs.**

## Tech Stack

- **Language**: Python
- **Primary use**: Codex agent orchestration (codex exec, codex code)
- **Config format**: TOML (config.toml, agent TOML profiles)
- **Agent profiles**: TOML-based profiles for different agent types
- **Skill interface**: YAML-based skill metadata

## Main Directories

```
agent-orchestration-skill/
├── README.md                    # Full documentation
├── LICENSE                      # MIT License
├── config.toml                  # Default Codex config (max_threads=4, max_depth=1, medium reasoning)
├── workflow-diagram.png         # Visual workflow overview
├── skills/
│   ├── SKILL.md               # Root orchestration contract (explicit-only, root-only)
│   ├── agents/
│   │   └── openai.yaml        # Skill metadata (explicit invocation policy)
│   ├── references/            # 16 policy reference documents
│   │   ├── control-plane.md
│   │   ├── context-capsule.md
│   │   ├── context-coverage-gate.md
│   │   ├── dag-plan-gate.md
│   │   ├── dispatch-packet.md
│   │   ├── exec-leaf-mode.md
│   │   ├── evaluation-harness.md
│   │   ├── failure-recovery.md
│   │   ├── leaf-worker-boundary.md
│   │   ├── session-lifecycle.md
│   │   ├── skill-scope-policy.md
│   │   ├── source-contract-proof.md
│   │   ├── spawn-economics.md
│   │   ├── test-gate.md
│   │   ├── thinking-router.md
│   │   ├── wisdom-notepads.md
│   │   └── worktree-isolation.md
│   └── scripts/               # 15 deterministic utility scripts
│       ├── batch_tasks.py
│       ├── budget_governor.py
│       ├── context_capsule.py
│       ├── context_coverage_gate.py
│       ├── dag_planner.py
│       ├── dispatch_compiler.py
│       ├── failure_classifier.py
│       ├── handoff_router.py
│       ├── handoff_validate.py
│       ├── notepad.py
│       ├── orchestration_decider.py
│       ├── plan_gate.py
│       ├── quality_gate.py
│       ├── run_ledger.py
│       ├── test_matrix.py
│       ├── token_budget_linter.py
│       └── worktree_guard.py
└── agents/                     # Agent profile TOMLs
    ├── communication-router-low.toml
    ├── security-reviewer-high.toml
    ├── test-runner-low.toml
    └── verification-engine-medium.toml
```

## Key Scripts (utilities)

| Script | Purpose |
|--------|---------|
| `orchestration_decider.py` | Recommends task size, reasoning effort, agent count, verification level |
| `context_capsule.py` | Creates, updates, renders, slices, measures the persistent Context Capsule |
| `dispatch_compiler.py` | Builds short scoped Dispatch Packets from explicit fields or JSON |
| `context_coverage_gate.py` | Checks whether a worker covered required context before editing |
| `batch_tasks.py` | Groups related files/tasks to avoid one-agent-per-file fan-out |
| `budget_governor.py` | Flags over-orchestration before spawning workers |
| `dag_planner.py` | Builds compact dependency-aware plans for larger tasks |
| `plan_gate.py` | Rejects invalid, vague, circular, or unverifiable plans |
| `run_ledger.py` | Creates and updates `.orchestration/runs/<run_id>/` state |
| `handoff_validate.py` | Validates handoffs for required fields, coverage, evidence, and forbidden routing |
| `handoff_router.py` | Merges handoffs and detects overlapping file ownership |
| `failure_classifier.py` | Maps failures to retry, fix, replan, or escalation |
| `test_matrix.py` | Detects common lint, typecheck, build, test, docker, and browser verification commands |
| `quality_gate.py` | Runs verification commands and writes JSON/Markdown evidence |
| `worktree_guard.py` | Plans or creates isolated git worktrees for large or dirty-checkout work |
| `notepad.py` | Stores compact durable learnings, decisions, issues, and verification notes |
| `token_budget_linter.py` | Detects stale always-on orchestration patterns and token-heavy config |
| `codex_leaf_exec.sh` | Launches `codex exec` in hard leaf-worker mode with multi-agent tools disabled |

## Agent Profiles

| Profile | Reasoning | Use Case |
|---------|-----------|----------|
| `test-runner-low` | low | Verifier for exact targeted commands on small scoped changes |
| `verification-engine-medium` | medium | Verification tasks |
| `communication-router-low` | low | Handoff routing and merging |
| `security-reviewer-high` | high | Security-sensitive review |

## Task Size Workflow

| Size | Behavior |
|------|----------|
| XS | No subagents. Minimal direct workflow. No heavy ledger/DAG |
| S | Zero or one worker if useful. Targeted validation only |
| M | Small number of batched workers. Context Capsule + scoped dispatch |
| L | Run Ledger, DAG plan, Plan Gate, Budget Governor, multiple bounded phases |
| XL | Strategy planning, worktree isolation planning, strict budget checks, staged verification and re-audit |

## Runtime & Commands

- **Invocation**: Explicit only — `Use $agent-orchestration-skill for this task`
- **CLI tools**: Python scripts (no model calls — deterministic utilities)
- **Run ledger**: `.orchestration/runs/<run_id>/`
- **Context Capsule**: `.orchestration/context_capsule.json`

## Risk-Sensitive Areas

- **Leaf-worker boundary enforcement**: Workers must not invoke skills, spawn child agents, or route to other workers
- **Context Coverage Gate**: Workers must confirm required files/context before editing
- **Budget Governor**: Checks orchestration cost before spawning workers
- **Spawn Economics**: Default caps by task size (XS: 0, S: 1, M: 2-3, L: 3-5, XL: up to max_threads)
- **Failure Recovery**: Classified before retry/replan/escalation

## Safe PR Areas

- Adding new reference documents following existing patterns
- Improving script utilities (deterministic, no model calls)
- Adding agent profile TOMLs with proper leaf-worker constraints
- Documentation improvements (README, inline comments)
- Test coverage for utility scripts

## Unsafe PR Areas (requires careful review)

- Changes to the core SKILL.md orchestration contract
- Modifications to the worker contract or leaf-worker boundaries
- Changes to the Context Capsule or Dispatch Packet structures
- Modifications to spawn economics or budget governor logic
- Any changes that relax leaf-worker constraints (multi-agent enabling)