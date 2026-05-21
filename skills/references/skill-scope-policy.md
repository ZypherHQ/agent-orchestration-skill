# Skill Scope Policy

The orchestration skill is root-only. The root can read this skill and its references, then compile plain Dispatch Packets for workers.

Spawned subagents must not:

- invoke `$agentic-orchestration-control`,
- invoke other repo skills,
- read internal orchestration references,
- spawn child agents,
- broadcast raw logs.

Why: child skill activation repeats orchestration context, increases token usage, and can cause recursive planning or duplicate fan-out. A worker needs a bounded job, not the whole operating manual.

The installer removes old v1.x phase skills from `.agents/skills` so child sessions see only one short root-only skill in the skill list.
