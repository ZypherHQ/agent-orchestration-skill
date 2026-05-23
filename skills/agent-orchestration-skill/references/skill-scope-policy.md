# Skill Scope Policy

The orchestration skill is root-only. The root can read this skill and references, then compile plain Dispatch Packets for workers.

Spawned subagents must not:

- invoke `$agent-orchestration-skill`;
- invoke other repo skills;
- read internal orchestration references;
- spawn child agents;
- broadcast raw logs.

Why: child skill activation repeats orchestration context, increases token usage, and can cause recursive planning or duplicate fan-out. A worker needs a bounded job and a Context Capsule digest, not the whole operating manual.

The installer removes stale phase skills from `skills` so child sessions see only one short root-only skill in the skill list.
