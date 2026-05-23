# Setup And Baseline

Use this guide to get from a clean checkout to a validated local package. If
you only want to use the published package, prefer the `npx --yes
agentic-orchestration-control ...` commands shown in `USAGE_EXAMPLES.md`.

## Prerequisites

Check Node and Python:

```bash
node --version
python3 --version
npm --version
```

Expected:

```text
node >= 18.17.0
python3 available
npm available
```

Check Git if you want to run install smoke tests against temporary repos:

```bash
git --version
```

## Install Dependencies

Install npm dependencies:

```bash
npm install
```

Expected result:

```text
node_modules/
```

> Note: The validation suite also calls Python scripts, but this repository does not define a Python virtualenv or Python package install step.

## Normalize Permissions

Set executable bits expected by tests and publish checks:

```bash
npm run fix:permissions
```

Expected output is quiet unless a file cannot be updated.

## Run The Main Baseline

Run the strict production test:

```bash
npm test
```

Expected output includes multiple `PASS` lines and ends without an exception.

## Run The Npm CLI Smoke Test

Validate the npm router behavior:

```bash
npm run test:npm-cli
```

Expected output:

```text
ALL NPM CLI VALIDATION CHECKS PASSED
```

## Run Publish Readiness

Check package metadata and payload rules:

```bash
npm run publish:check
```

Expected output includes:

```text
PASS
```

> Note: Empty sandbox-mounted `.agents` and `.codex` directories are allowed. Hidden directories with files still fail publish readiness.

## Run Full Production Validation

Run the prepublish matrix:

```bash
npm run validate:production
```

Expected steps:

```text
node tools/fix-permissions.mjs --quiet
npm test
npm run publish:check
npm pack --dry-run
```

## Pack Locally

Create a local tarball:

```bash
npm pack --pack-destination dist
```

Expected result:

```text
dist/agentic-orchestration-control-<version>.tgz
```

## First Run

Create a run ledger:

```bash
npx --yes agentic-orchestration-control init \
  --repo . \
  --run-id baseline \
  --task "baseline smoke"
```

Render a snapshot:

```bash
npx --yes agentic-orchestration-control snapshot --repo . --run-id baseline
```

Expected output includes:

```text
Agentic Orchestration Control
```

## Common Failures

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `node: command not found` | Node is not installed or not on `PATH`. | Install Node matching `package.json` `engines.node`. |
| `python3: command not found` | Python 3 is unavailable. | Install Python 3 and rerun the command. |
| Executable permission failures | Files lost executable bits after archive/copy. | Run `npm run fix:permissions`. |
| Publish check rejects `__pycache__` or `*.pyc` | Python bytecode exists in the package tree. | Remove bytecode artifacts before publish validation. |
| Install moves legacy layouts | Installer found `.skills/`, `.agents/`, or `.codex/agents`. | Check `.orchestration-backup-*` and confirm the new `skills/` layout. |
| GUI command appears to hang | `gui` starts a local server unless `--once` is used. | Use `npx --yes agentic-orchestration-control gui --once > /tmp/aoc.html` for a static snapshot. |
| GUI refuses remote bind | Remote exposure needs an explicit token. | Pass `--allow-remote` with `--auth-token` or `AOC_GUI_TOKEN`. |
| TUI index looks stale | Index rebuilds are explicit. | Rerun with `--rebuild-index` when you want to refresh `.orchestration/index.json`. |
