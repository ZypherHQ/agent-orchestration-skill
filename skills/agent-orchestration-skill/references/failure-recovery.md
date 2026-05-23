# Failure Recovery

Failures should trigger diagnosis, not immediate fan-out.

## Policy

- Transient command/network failure: retry the same command or same worker once.
- Setup/dependency failure: inspect project setup once, then retry if the fix is in scope.
- Test assertion/compile failure: route back to the implementation owner with exact failure evidence.
- Permission/sandbox/conflict/dirty worktree: escalate to root/user; do not keep spawning.
- Same failure twice: replan or use a higher-reasoning debugger, not another equal worker.

## Retry caps

- XS/S: one retry maximum.
- M/L: two retries maximum across the same phase.
- XL/high-risk: one retry after explicit root-cause analysis; then replan.

Use:

```bash
python skills/agent-orchestration-skill/scripts/failure_classifier.py --file .orchestration/runs/<id>/evidence/failure.log
```
