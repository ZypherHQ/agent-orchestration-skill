# Agent Orchestration Skill Gate

This repository includes an optional orchestration skill: `$agent-orchestration-skill`.

Use that skill only when the user prompt contains the exact literal invocation `$agent-orchestration-skill`. Do not invoke it implicitly for generic coding, testing, audit, debugging, or subagent-related tasks.

Normal mode: if the exact invocation is absent, work normally and do not create orchestration artifacts, run ledgers, context capsules, DAG plans, or skill-driven subagent workflows.

Leaf mode: if the prompt says `You are a subagent`, `verification subagent`, `worker`, `leaf worker`, `LEAF_EXEC_MODE`, `Run exactly these commands`, `Do not edit files`, or `Return only a YAML Handoff Packet`, do not invoke skills and do not spawn/request/recommend child agents. Execute only the bounded task and return only the requested packet.

Spawned workers are leaf workers: no skills, no nested subagents, no routing fields such as `target_agent` or `next_handoff`; return `ESCALATE_TO_PARENT` when blocked.
