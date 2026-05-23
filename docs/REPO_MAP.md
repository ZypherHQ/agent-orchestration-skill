# Repo Map

This repository packages an explicit-only Codex orchestration skill, subagent profiles, CLI wrappers, and validation tests.

## Top Level

| Path | Role |
| --- | --- |
| `README.md` | Public overview and quickstart. Keep it short and link deeper details here. |
| `VALIDATION.md` | Snapshot of validation commands and expected npm payload. |
| `AGENTS.md` | Runtime guard: use the orchestration skill only when explicitly invoked. |
| `package.json` | npm package metadata, command aliases, scripts, engine requirement, and publish allowlist. |
| `install.sh` | Installs the supported `skills/` and `subagents/` layout into a target repo. |
| `LICENSE` | MIT license. |
| `workflow-diagram.png` | README diagram asset. |
| `SKILL_PACK_MANIFEST.json` | Skill pack manifest used by packaging/distribution workflows. |
| `logs.txt` | Local log artifact. Do not treat it as product documentation. |

## CLI And Install Surface

| Path | Role |
| --- | --- |
| `bin/aoc.mjs` | npm/npx command router. Routes commands to bundled Python scripts. |
| `tools/fix-permissions.mjs` | Normalizes executable bits before tests and publish checks. |
| `dist/*.tgz` | Locally packed npm tarball artifacts. Regenerate before release validation. |

## Skill Payload

| Path | Role |
| --- | --- |
| `skills/agent-orchestration-skill/SKILL.md` | The explicit-only root orchestration workflow. |
| `skills/agent-orchestration-skill/bin/` | Skill-level command wrappers installed with the payload. |
| `skills/agent-orchestration-skill/scripts/` | Deterministic utilities for ledgers, context capsules, events, gates, usage, memory, TUI, GUI, validation, and bridges. |
| `skills/agent-orchestration-skill/references/` | Focused policy/reference pages used by the skill when more detail is needed. |
| `skills/agent-orchestration-skill/agents/openai.yaml` | Agent metadata/configuration used by the skill pack. |

## Subagent Profiles

| Path | Role |
| --- | --- |
| `subagents/config.toml` | Shared subagent defaults. |
| `subagents/*-low.toml` | Low-effort read-only scouts, routers, finalizers, and exact command runners. |
| `subagents/*-medium.toml` | Normal implementation, browser QA, verification, and regression review workers. |
| `subagents/*-high.toml` | Complex implementation and security review profiles. |
| `subagents/strategy-architect-xhigh.toml` | Rare read-only planning profile for large ambiguous work. |

All subagent profiles disable nested agent spawning. Workers are expected to be leaf workers.

## Tests

| Path | Role |
| --- | --- |
| `tests/aggressive_validation.py` | Main production validation suite for layout, install behavior, scripts, TUI/GUI, usage, budget, and publish readiness. |
| `tests/npm_cli_validation.mjs` | npm CLI smoke test for install, init, snapshot, GUI snapshot, usage, and budget commands. |

## Runtime State

The package creates runtime state in consuming repositories:

```text
.orchestration/
.orchestration/runs/<run_id>/
.orchestration/events.jsonl
.orchestration/usage/
.orchestration/memory/
```

Runtime state is local project data, not source code. Review it before sharing logs or publishing artifacts.

## Generated Or Local-Only Files

| Path | Role |
| --- | --- |
| `.orchestration/` | Created by local runs and installs. |
| `.orchestration-backup-*` | Created by installer when backing up legacy layouts. |
| `__pycache__/`, `*.pyc` | Python bytecode artifacts. These should not be included in publishable packages. |
| `node_modules/` | Local npm dependencies. |
