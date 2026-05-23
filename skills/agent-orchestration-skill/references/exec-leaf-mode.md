# Exec Leaf Mode

`codex exec` starts a fresh Codex session. If you run a command such as:

```bash
codex exec --cd /repo --sandbox workspace-write 'You are a verification subagent ...'
```

that process is not automatically protected by a custom agent TOML. It may behave like a root session unless you add hard config overrides or unambiguous leaf-mode instructions.

## Why this matters

Project config may enable multi-agent tools globally so the root orchestrator can spawn workers. A manually launched `codex exec` verifier can inherit that global config. If older AGENTS.md text says every substantial task should spawn agents or includes routing fields such as `next_handoff`, the verifier may try to coordinate instead of simply running checks.

## Required launch pattern for verifier exec jobs

Use CLI overrides to disable collaboration tools for the exec process itself:

```bash
codex exec --cd /path/to/repo --sandbox workspace-write \
  -c features.multi_agent=false \
  -c agents.max_depth=0 \
  -c agents.max_threads=1 \
  -c model_reasoning_effort=low \
  -c model_verbosity=low \
  -c model_reasoning_summary=none \
  'LEAF_EXEC_MODE. You are a verification leaf worker. Do not spawn agents. Run exactly the requested commands and return only the requested packet.'
```

Use `medium` reasoning only when the verifier must diagnose failures, not when it is merely executing known commands.

## Leaf prompt template

```text
LEAF_EXEC_MODE.
You are a verification leaf worker for <repo>.
Follow the leaf-worker section of AGENTS.md.
Do not invoke skills.
Do not spawn, request, recommend, or plan child agents.
Do not edit files except normal build/test artifacts produced by the requested commands.
Run exactly these commands, in order:
1. <command>
2. <command>
Return only a YAML Handoff Packet with command, status, exit code, and concise evidence.
If blocked, return STATUS: ESCALATE_TO_PARENT with the blocker; do not delegate.
```

## Output rule

For leaf verification jobs, do not include routing fields such as `next_handoff` or `target_agent` unless the parent explicitly requested them. The parent already knows it is the target.
