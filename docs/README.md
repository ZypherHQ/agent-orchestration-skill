# Documentation

Start here when you need more than the top-level quickstart.

## Use The Package

- [Setup and baseline](SETUP_AND_BASELINE.md): install prerequisites, run the first smoke test, and record the validation baseline.
- [Usage examples](USAGE_EXAMPLES.md): copy-pasteable workflows for install, run ledgers, TUI/GUI, usage, gates, memory, and publish checks.
- [Security model](SECURITY_MODEL.md): local state, logs, GUI exposure, and command execution risks.

## Understand The Repo

- [Repo map](REPO_MAP.md): what each file group owns and when to edit it.
- [State and changelog](STATE_AND_CHANGELOG.md): current repository state and recent documentation changes.
- [Quality audit](QUALITY_AUDIT.md): expected verification checks and current audit observations.

## Contribute

- [Issue triage](ISSUE_TRIAGE.md): known issues, severity, reproduction, and verification steps.
- [PR candidates](PR_CANDIDATES.md): small, reviewable contribution slices.

## Source Of Truth

Use the code and package metadata as the source of truth:

```bash
node bin/aoc.mjs --help
node bin/aoc.mjs version
npm run validate:production
```

The package is explicit-only: the orchestration skill activates only when a prompt contains the exact literal `$agent-orchestration-skill`.
