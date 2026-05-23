# Validation Report

This package was validated as a production `skills/` + `subagents/` layout.

## Fixed issues

- Replaced all runtime/package paths from `.skills/` to `skills/`.
- Added self-install protection so `node bin/aoc.mjs install .` does not move `skills/agent-orchestration-skill` into `.orchestration-backup-*`.
- Added permission normalization before test/publish, then strict executable checks.
- Removed public demo commands and demo payloads from production package.
- Strengthened publish checks so npm payload must include the complete skill, subagents, tests, tools, and CLI router.
- Added forbidden-path checks for `.skills/`, `.agents/`, `.codex/`, and `demo_run.py`.
- Added install tests for both external repos and self-install into the package root.

## Commands validated

```bash
node tools/fix-permissions.mjs --quiet
npm test
npm run publish:check
npm pack --dry-run
npm pack --pack-destination dist
```

Tarball smoke test was run with:

```bash
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control install <repo>
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control init --repo <repo> --run-id smoke --task "smoke"
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control snapshot --repo <repo> --run-id smoke
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control gui --repo <repo> --run-id smoke --once --with-codex
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control usage --repo <repo> --run-id smoke
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control budget 12000 --repo <repo> --run-id smoke
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control codex doctor --repo <repo>
npx --yes --package ./dist/agentic-orchestration-control-0.1.0.tgz agentic-orchestration-control publish-check
```

## Expected npm payload

`npm pack --dry-run` must include:

```text
skills/agent-orchestration-skill/SKILL.md
skills/agent-orchestration-skill/scripts/*.py
skills/agent-orchestration-skill/bin/*
subagents/*.toml
bin/aoc.mjs
tools/fix-permissions.mjs
tests/aggressive_validation.py
tests/npm_cli_validation.mjs
README.md
LICENSE
install.sh
workflow-diagram.png
```

It must not include:

```text
.skills/
.agents/
.codex/
demo_run.py
__pycache__/
*.pyc
```
