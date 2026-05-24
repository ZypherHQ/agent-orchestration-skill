# AOC Command Reference

The checked-in command contract is `tools/aoc.commands.json`. The npm CLI reads
and validates it at startup so help text, installed shims, and command routing
do not drift.

The preferred command surface is short and repo-aware:

```bash
aoc
aoc gui
aoc init "Fix checkout flow"
aoc sessions
aoc import
aoc current
aoc use <run_id>
aoc search "query"
aoc usage
aoc budget 12000
aoc doctor
```

## Resolution Rules

Repo resolution order:

1. `--repo`
2. `AOC_REPO`
3. nearest git root from the current directory
4. current directory when it contains `.orchestration`, `package.json`, `skills`, or `.git`
5. a clear error

Run resolution order:

1. `--run-id`
2. `AOC_RUN_ID`
3. `.orchestration/current-run`
4. `.orchestration/current.json`
5. latest `.orchestration/runs/*` state, including imported Codex sessions
6. no run, with an empty dashboard and discoverable Codex sessions

## Commands

| Command | Purpose |
| --- | --- |
| `aoc` | Open the terminal control room. In non-interactive shells it prints a snapshot. |
| `aoc gui` | Open the local web GUI. Use `--once` for one HTML snapshot. |
| `aoc init "Fix checkout flow"` | Create a run ledger with a generated unique run id. |
| `aoc sessions` | List native AOC runs and imported Codex sessions. |
| `aoc import` | Discover and import Codex rollout JSONL sessions. |
| `aoc current` | Print the currently selected run. |
| `aoc use <run_id>` | Select the current run for later commands. |
| `aoc search "query"` | Search run state, events, handoffs, evidence, memory, and imported summaries. |
| `aoc usage` | Show run-scoped usage with derived pressure. |
| `aoc budget 12000` | Check usage against an estimated-token budget. |
| `aoc doctor` | Run local package and repo sanity checks. |

## Global Flags

| Flag | Meaning |
| --- | --- |
| `--repo <path>` | Use a specific repository. |
| `--run-id <id>` | Use a specific run or imported session. |
| `--json` | Print machine-readable output where supported. |
| `--quiet` | Suppress non-essential output where supported. |
| `--verbose` | Print extra diagnostics where supported. |
| `--no-open` | Do not open a browser for GUI commands. |

## Codex Session Import

`aoc import` discovers sessions from:

1. `--codex-home`
2. `AOC_CODEX_HOME`
3. `CODEX_HOME`
4. `~/.codex`
5. `/root/.codex` when readable

It reads rollout files under:

```text
sessions/YYYY/MM/DD/rollout-*.jsonl
```

Imported sessions are normalized into `.orchestration/runs/codex-*/`, keep source metadata, and appear in `aoc sessions`, `aoc`, `aoc gui`, and `aoc search`.
