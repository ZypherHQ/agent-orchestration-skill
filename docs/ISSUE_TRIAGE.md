# Issue Triage

Use this page to reproduce and verify known or likely issues.

## Known Issues

| Issue | Severity | Status | Reproduce | Verify Fix |
| --- | --- | --- | --- | --- |
| Hidden legacy `.agents` or `.codex` payload blocks publish checks. | High | Fixed for empty sandbox-mounted directories; still enforced for hidden dirs with payload. | Run `npm run publish:check`. | Command passes for empty sandbox mounts and fails if hidden production payload exists. |
| Python bytecode artifacts can fail publish validation. | Medium | Known packaging hygiene risk. | Run `find . -name __pycache__ -o -name '*.pyc'` before publish checks. | `npm run validate:production` passes and no bytecode appears in `npm pack --dry-run`. |
| GUI server stays running without `--once`. | Low | Expected behavior, easy to mistake for a hang. | Run `npx --yes agentic-orchestration-control gui --repo . --run-id smoke`. | Use `--once` when a static HTML snapshot is wanted. |
| `logs.txt` may contain stale local output. | Low | Needs cleanup decision. | Open `logs.txt` and check whether it is release-worthy. | Remove from release process or replace with intentional sample evidence. |

## Triage Template

Copy this into a GitHub issue:

````markdown
## What happened

## Expected behavior

## Reproduction

```bash
npx --yes agentic-orchestration-control --help
npm run validate:production
```

## Environment

- OS:
- Node:
- npm:
- Python:
- Install method:

## Evidence

Paste the shortest useful output. Do not paste `.orchestration/` logs without checking for private task names or file paths.
````

## Severity Guide

| Severity | Use When |
| --- | --- |
| Critical | A release exposes secrets, executes unintended commands, or corrupts a target repo. |
| High | Install, activation gating, or validation is broken for normal users. |
| Medium | A core command works incorrectly but has a clear workaround. |
| Low | Docs, ergonomics, cleanup, or expected behavior needs clarification. |

## First Checks

Run:

```bash
npx --yes agentic-orchestration-control --help
npx --yes agentic-orchestration-control --version
npm test
npm run test:npm-cli
```

If the issue involves packaging, also run:

```bash
npm run publish:check
npm pack --dry-run
```

Current baseline note: `npm run publish:check` passed after publish validation was updated to tolerate empty sandbox-mounted `.agents` and `.codex` directories. Hidden directories with payload should still fail release validation.
