# Wisdom Notepads

Persistent notepads are for durable operational knowledge, not transcripts.

## Write only when useful next time

Good entries:

- a project-specific test command that revealed a real failure;
- a dependency contract that was easy to misread;
- a recurring failure mode and workaround;
- an architecture boundary that affected the fix;
- a verification gap that should be closed later.

Bad entries:

- generic summaries;
- raw logs;
- private reasoning;
- obvious facts already in code;
- one-off failures with no future impact.

Use:

```bash
python skills/agent-orchestration-skill/scripts/notepad.py --kind learnings --context "..." --insight "..." --impact "..."
```
