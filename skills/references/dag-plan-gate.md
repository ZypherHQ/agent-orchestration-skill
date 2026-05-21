# DAG Plan Gate

Use a dependency-aware DAG for M/L/XL tasks. Do not use a DAG for tiny single-file fixes.

## Requirements

- Max 7 phases. Larger work must be split into multiple runs or compressed by batching related files.
- Each phase needs objective, owner agent, dependencies, acceptance criteria, validation, and stop conditions.
- Read-only discovery may run in parallel; write phases with overlapping files must not run in parallel.
- Plan must pass the binary gate: `OKAY` or `REJECT` with actionable blockers.

## Gate criteria

A plan is executable when:

- referenced files/modules exist or the phase explicitly says discovery is required;
- every phase can start from its Dispatch Packet;
- acceptance criteria are observable;
- dependencies are valid and non-circular;
- verification exists for behavioral changes;
- worker leaf policy is explicit.

Use:

```bash
python .agents/skills/agentic-orchestration-control/scripts/dag_planner.py --task "..." --size M --surfaces frontend,backend > .orchestration/plan.json
python .agents/skills/agentic-orchestration-control/scripts/plan_gate.py .orchestration/plan.json
```
