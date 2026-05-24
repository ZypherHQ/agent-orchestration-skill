# Agentic Orchestration Control

<p align="center">
  <img src="workflow-diagram.png" alt="Agentic Orchestration Control workflow" width="100%" />
</p>

Agentic Orchestration Control is an explicit-only npm control room for Codex orchestration. It installs a Codex skill, leaf-worker profiles, local run ledgers, usage reports, Codex session import, and TUI/GUI views into a repository without using hidden `.skills`, `.agents`, or `.codex` package layouts.

## Start In 10 Seconds

Install the published package globally, then install AOC into the repository you are working in:

```bash
npm install -g agentic-orchestration-control
aoc install .
```

Open the control room:

```bash
aoc
aoc gui
```

Start an observable run:

```bash
aoc init "Fix checkout flow"
```

Use the skill only when you want the orchestration workflow:

```text
Use $agent-orchestration-skill for this task.
```

Prompts without the exact literal `$agent-orchestration-skill` should run in normal Codex mode.

## Short Commands

```bash
aoc
aoc gui
aoc init "Fix checkout flow"
aoc sessions
aoc import
aoc current
aoc use <run_id>
aoc search "checkout"
aoc usage
aoc budget 12000
aoc doctor
```

`aoc` resolves the repo from `--repo`, `AOC_REPO`, the nearest git root, or the current directory when it looks like a project. It resolves the run from `--run-id`, `AOC_RUN_ID`, `.orchestration/current-run`, `.orchestration/current.json`, or the latest `.orchestration/runs/*` state, including imported Codex sessions.

## Before A Run Exists

`aoc` and `aoc gui` should open even before `aoc init`. In an empty repo they show an empty state and any discoverable Codex sessions. Use `aoc import` to import local Codex rollout logs into `.orchestration/runs/` without creating a native AOC run first.

## AOC Runs vs Codex Sessions

An AOC run is a local orchestration ledger created by `aoc init "task"`. It stores state, events, dispatches, handoffs, evidence, gates, memory, and usage under `.orchestration/runs/<run_id>/`.

An imported Codex session comes from local Codex rollout JSONL files under `AOC_CODEX_HOME`, `CODEX_HOME`, `~/.codex`, or another configured Codex home. Imported sessions are normalized into `.orchestration/runs/codex-*/` with source metadata so the TUI, GUI, sessions list, usage, and search commands can display them beside native AOC runs.

## How The Skill Works

The installed `AGENTS.md` keeps the skill explicit-only. The root Codex thread remains the orchestrator, and spawned workers are leaf-only. The package provides subagent profiles and validators, but it does not make model calls by itself.

Installed layout:

```text
skills/agent-orchestration-skill/
subagents/
.orchestration/bin/aoc
AGENTS.md
```

## TUI And GUI

Use the terminal control room for quick status:

```bash
aoc
aoc sessions
aoc current
```

Use the local web GUI for a browser view:

```bash
aoc gui
aoc gui --once
```

The GUI binds to localhost by default. Remote binding requires explicit opt-in and auth:

```bash
AOC_GUI_TOKEN="change-me" aoc gui --host 0.0.0.0 --allow-remote --auth-token "$AOC_GUI_TOKEN"
```

## Usage And Budget

Usage reports separate imported or recorded real token data from local estimated orchestration pressure:

```bash
aoc usage
aoc budget 12000
```

Estimated pressure is not provider billing. Treat it as a local signal for prompt size, fan-out, and validation cost.

## Codex Session Import

Import local Codex sessions:

```bash
aoc import
```

Use a fake or alternate Codex home when testing:

```bash
AOC_CODEX_HOME=/tmp/fake-codex aoc import --json
```

List and inspect imported sessions:

```bash
aoc sessions
aoc use <run_id>
aoc search "checkout"
```

## Safety Model

- The skill activates only on the exact literal `$agent-orchestration-skill`.
- Runtime state stays in `.orchestration/`.
- Hidden `.skills`, `.agents`, and `.codex` package payloads are rejected.
- The GUI is localhost-only unless `--allow-remote` and an auth token are provided.
- Imported Codex sessions are local files; review `.orchestration/` before sharing or committing it.

## Troubleshooting

If `aoc` is not on `PATH`, use the installed repo shim:

```bash
./.orchestration/bin/aoc
```

If no sessions appear, run:

```bash
aoc import --json
aoc sessions --json
```

If the wrong repo or run is selected, be explicit:

```bash
aoc --repo .
aoc use <run_id>
```

## Development And Publishing

```bash
npm install
npm test
npm run test:npm-cli
npm run publish:check
npm pack --dry-run
npm run validate:production
```

More detail lives in [docs/README.md](docs/README.md) and the command reference in [docs/COMMANDS.md](docs/COMMANDS.md).

## License

MIT License. See [LICENSE](LICENSE).
