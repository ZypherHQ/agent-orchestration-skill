# Session Lifecycle: Resume, Do Not Respawn

Do not launch a fresh worker for the same phase when an existing worker already has the context or produced a partial result. Prefer continuation through the root if the platform supports it; otherwise, compile a new Dispatch Packet that includes only the missing evidence and previous blocker.

## States

- `initialized`
- `planned`
- `dispatching`
- `worker_active`
- `waiting_for_handoff`
- `blocked`
- `retrying`
- `verifying`
- `complete`
- `aborted`

## Duplicate-spawn check

Before spawning:

1. Check active agents in `.orchestration/runs/<run_id>/state.json`.
2. Check claimed files and phase IDs.
3. If an equivalent phase exists, resume or request a concise continuation instead of spawning a duplicate.
4. If the old worker is blocked, classify the blocker first; do not blindly create another agent.

## Completion ownership

The root owns final synthesis. Workers own only their Handoff Packet. A worker should not recommend another worker; it returns `ESCALATE_TO_PARENT` if blocked.
