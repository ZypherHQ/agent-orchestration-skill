# Spawn Economics

Spawn only when delegation provides more value than cost.

## Cost model

Every subagent opens its own model/tool loop. Treat this as a fixed startup cost plus the cost of any tools, files, logs, tests, and reasoning it performs. A subagent should therefore own a meaningful bundle of work.

## Default caps

- XS/S: 1 worker.
- M: 2–3 total agents, often serial rather than all parallel.
- L: 3–5 agents if domains are independent.
- XL: up to configured `max_threads`, but only for high-value read-heavy exploration, tests, or review.

## Spawn decision

Spawn a subagent when at least one is true:

- It can run independent read-heavy work in parallel.
- It has a clearly different tool surface or expertise.
- It keeps noisy logs/tests/browser output out of the root context.
- It owns a complete implementation bundle.

Do not spawn when:

- The work is a known one-file fix and a single worker can do inspect+patch+test.
- The agent would only read one file and report back.
- File ownership overlaps with another active write agent.
- The only purpose is to satisfy a “multiagent always” habit rather than a real partition.
