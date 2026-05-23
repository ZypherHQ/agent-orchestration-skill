# PR Candidates

Keep PRs small and reviewable. Each candidate below should include validation evidence.

## 1. Release Artifact Hygiene

Scope:

- Remove or intentionally relocate local artifacts such as `logs.txt`.
- Ensure bytecode artifacts are not present before publish validation.
- Confirm `dist/` artifacts are regenerated only when needed.

Validation:

```bash
find . -name __pycache__ -o -name '*.pyc'
npm run validate:production
```

## 2. CLI Help Examples

Scope:

- Review `node bin/aoc.mjs --help` for command accuracy.
- Add missing examples only where they map to implemented routes.
- Keep the help output short.

Validation:

```bash
node bin/aoc.mjs --help
npm run test:npm-cli
```

## 3. Setup Smoke Test Script

Scope:

- Add a dedicated script for the tarball smoke test described in `docs/USAGE_EXAMPLES.md`.
- Keep it deterministic and temporary-directory based.
- Do not require Codex runtime access.

Validation:

```bash
npm run validate:production
```

## 4. Security Review Pass

Scope:

- Audit GUI auth/token handling.
- Audit installer behavior around backups and shell shims.
- Audit `.orchestration/` files for private data risks.

Validation:

```bash
npm test
npm run publish:check
```

Add manual evidence for GUI local/remote behavior.

## 5. Reference Docs Consistency

Scope:

- Check `skills/agent-orchestration-skill/references/` against `SKILL.md`.
- Remove stale references or add missing links from the skill body.
- Keep reference pages focused on policy, not duplicate CLI reference.

Validation:

```bash
rg "references/" skills/agent-orchestration-skill/SKILL.md
npm test
```
