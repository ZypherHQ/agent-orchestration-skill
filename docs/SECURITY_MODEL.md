# Security Model

This package is a local orchestration control tool. It does not need network access for its core validation tests, but users may run it inside repositories that contain private code, paths, task names, and logs.

## Trust Boundaries

| Boundary | Risk | Control |
| --- | --- | --- |
| Target repo install | Installer writes `skills/`, `subagents/`, and `.orchestration/` into a target repo. | Run install only for repos you control. Review `.orchestration-backup-*` after migration. |
| Runtime state | `.orchestration/` can include task names, file paths, event summaries, handoffs, evidence references, and usage imports. | Treat `.orchestration/` as local project state. Review before sharing or committing. |
| Local GUI | The GUI renders run state in a browser. | It binds locally by default. Require explicit `--allow-remote` and an auth token for remote access. |
| Command execution | CLI routes to bundled Python scripts and installer shims. | Run commands from a trusted checkout or npm package. Inspect `bin/aoc.mjs` and `install.sh` for release-sensitive changes. |
| External bridges | Codex app-server/codexui and ccusage bridges can import external state. | Import only trusted files/endpoints. Keep imported usage separate from estimated orchestration pressure. |

## Local GUI

Render a static HTML snapshot when possible:

```bash
npx --yes agentic-orchestration-control gui \
  --repo . \
  --run-id smoke \
  --once > /tmp/aoc-smoke.html
```

Expose remote access only with an explicit token:

```bash
AOC_GUI_TOKEN="change-me" \
  npx --yes agentic-orchestration-control gui \
  --repo . \
  --run-id smoke \
  --host 0.0.0.0 \
  --allow-remote \
  --auth-token "$AOC_GUI_TOKEN"
```

> Note: Do not use a shared or committed token. Do not expose the GUI from a repo containing private task logs unless you intend to share that state.

## Runtime State Privacy

Before sharing diagnostics, inspect:

```bash
find .orchestration -maxdepth 3 -type f
```

Look for:

- Private repository paths.
- Task descriptions copied from prompts.
- Handoff summaries.
- Evidence files or logs.
- Imported usage reports.
- Codex app-server links or thread identifiers.

## Installer Behavior

The installer backs up legacy layouts:

```text
.skills/
.agents/skills/agent-orchestration-skill/
.codex/agents
```

Backups are written under:

```text
.orchestration-backup-<timestamp>/
```

Review backups before deleting them.

## Reporting Vulnerabilities

Open a private security report if available on the hosting platform. If not, open a minimal public issue that describes the affected surface without publishing secrets, tokens, private logs, or exploit payloads.
