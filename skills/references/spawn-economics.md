# Spawn Economics

Spawn only when delegation provides more value than cost.

## Cost model

Every subagent opens its own model/tool loop. Treat this as a fixed startup cost plus the cost of tools, files, logs, tests, context slice, and reasoning. A subagent should own a meaningful bundle of work.

## Useful-worker test

Before spawning, the root asks:

1. Can this be done directly without losing control or evidence?
2. Can one worker complete the loop alone?
3. Will this worker perform at least two valuable actions?
4. Does this worker own a coherent surface with no file conflict?
5. Is the Dispatch Packet small enough?

If the answer is no, do not spawn.

## Default caps

- XS: usually 0 workers, max 1 if root edits are forbidden.
- S: 1 worker, 2 only when verification/browser output is genuinely separate.
- M: 2–3 total agents, often serial rather than all parallel.
- L: 3–5 agents if domains are independent.
- XL: up to configured `max_threads`, but only for high-value read-heavy exploration, tests, or review.

## Spawn when

- It can run independent read-heavy work in parallel.
- It has a clearly different tool surface or expertise.
- It keeps noisy logs/tests/browser output out of the root context.
- It owns a complete implementation bundle.
- It provides independent verification or browser evidence.

## Do not spawn when

- The work is a known one-file fix and a single loop can do inspect+patch+test.
- The agent would only read one file and report back.
- The scout would read the same files the implementer must read anyway.
- File ownership overlaps with another active write agent.
- The only purpose is to satisfy a multiagent habit.
- The Dispatch Packet has become large because the scope is unclear.
