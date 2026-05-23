# Quality Audit

This audit focuses on the repository as an open-source package.

## Current Findings

| Severity | Finding | Evidence | Expected Action |
| --- | --- | --- | --- |
| High | Publish readiness now distinguishes empty sandbox mounts from hidden payload. | `npm run publish:check` passed after allowing empty `.agents` and `.codex` directories. | Keep failing hidden directories that contain production payload. |
| Medium | Publish validation is strict about Python bytecode, but bytecode can appear after local Python runs. | `tests/aggressive_validation.py` checks for `__pycache__` and `*.pyc`. | Keep bytecode out of release artifacts; rerun validation after cleanup. |
| Low | `logs.txt` is present at the repository root. | Top-level file list includes `logs.txt`. | Decide whether it is intentional evidence or local noise before release. |
| Info | The README already covers the quickstart and top-level command surface. | `README.md` contains install, skill use, commands, and layout. | Keep detailed workflows in `/docs` instead of expanding README. |
| Info | Validation coverage is broad for a CLI package. | `tests/aggressive_validation.py` and `tests/npm_cli_validation.mjs`. | Preserve strict install, CLI, GUI snapshot, usage, and publish checks. |
| Info | Repository docs are included in the npm package allowlist. | `package.json` `files` includes `docs/`. | Keep docs short and release-relevant so the tarball does not carry stale operational notes. |

## Verification Expectations

Run these before merging runtime-affecting changes:

```bash
npm run fix:permissions
npm test
npm run test:npm-cli
npm run publish:check
npm pack --dry-run
```

Run this before publishing:

```bash
npm run validate:production
```

## Manual Checks

Inspect the CLI help:

```bash
npx --yes agentic-orchestration-control --help
```

Check the explicit-only trigger is still documented:

```bash
rg "\\$agent-orchestration-skill" README.md AGENTS.md skills/agent-orchestration-skill/SKILL.md docs
```

Check for generated artifacts:

```bash
find . -name __pycache__ -o -name '*.pyc'
```

Expected result before release:

```text
no output
```

## Review Criteria

- The skill remains explicit-only and root-only.
- Subagent profiles remain leaf-only and do not enable nested delegation.
- The installer preserves the supported `skills/` + `subagents/` layout.
- Legacy hidden layouts are backed up, not silently merged.
- Runtime state stays under `.orchestration/`.
- GUI remote exposure requires explicit opt-in and token usage.
- Publish checks reject hidden legacy payloads, demo payloads, bytecode, and incomplete package payloads.
- Empty sandbox-mounted hidden directories are tolerated only when they contain no payload.
