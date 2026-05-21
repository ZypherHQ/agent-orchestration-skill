# Evaluation Harness

The orchestration system itself needs tests.

## Smoke scenarios

1. Leaf exec verifier does not invoke skills and does not propose `target_agent`.
2. XS one-file fix recommends one low-effort worker.
3. S/M related-file task batches files instead of one agent per file.
4. High-risk auth/security task enables high/xhigh only after classification.
5. Multi-packet routing detects overlapping file ownership.
6. Plan gate rejects missing acceptance criteria or invalid dependencies.
7. Failure classifier escalates sandbox/dirty worktree problems instead of retrying forever.

## Commands

```bash
python .agents/skills/agentic-orchestration-control/scripts/token_budget_linter.py --root .
python .agents/skills/agentic-orchestration-control/scripts/orchestration_decider.py --task "fix one known file" --known-files 1 --risk low --ambiguity low
```
