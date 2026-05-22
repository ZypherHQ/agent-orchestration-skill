# Worktree Isolation

For L/XL or dirty-checkout work, prefer an isolated git worktree so implementation does not overwrite unrelated user changes.

## When to use

- Main checkout is dirty.
- Multi-file implementation is expected.
- High-risk change requires review before merge.
- Multiple independent write bundles may run sequentially or in separate sandboxes.

## When not to use

- Tiny XS/S patch in one known file.
- The task must operate on the current checkout state.
- Repo is not a git repository.

Use plan mode first:

```bash
python .agents/skills/agent-orchestration-skill/scripts/worktree_guard.py --root . --run-id <id>
```

Creation is explicit:

```bash
python .agents/skills/agent-orchestration-skill/scripts/worktree_guard.py --root . --run-id <id> --create
```
