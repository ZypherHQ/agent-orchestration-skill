# Reasoning Router

Use the cheapest adequate reasoning effort. Reasoning is a scarce budget; spend it only where it improves correctness.

## Low

Use for scouts and deterministic operations:

- file/symbol discovery;
- code-path mapping without deep design;
- bounded docs/source contract checks;
- exact verification commands;
- handoff routing and final summaries.

Low agents must stay narrow. Do not spawn several low scouts when one implementer must read the same files anyway.

## Medium

Use for normal production work:

- one small implementation bundle;
- several related files in one module/user flow;
- ordinary debugging with a plausible owner;
- browser QA and verification matrices;
- test design where failure interpretation matters.

Medium is the default for normal writing and deep verification.

## High

Use for complex writes or reviews:

- non-trivial business logic;
- migrations or data-model changes;
- concurrency-sensitive code;
- security-sensitive review;
- broad regression review after risky changes.

High should be scoped by a clear Dispatch Packet and required files. It is not a substitute for missing context.

## XHigh

Use only for very large ambiguous planning or critical architecture/feature-structure decisions. Prefer read-only strategy first. Do not use it as the default debugger or implementer.

Use `strategy_architect_xhigh` when the root needs a plan, invariants, risk model, or architectural decomposition before workers implement.

## Anti-patterns

- xhigh for routine updates, simple debugging, isolated files, CSS, imports, or mechanical fixes.
- xhigh as an implementation worker for normal changes.
- high for changes that tests can mechanically verify.
- several low agents for a cohesive two-file patch; use one medium worker instead.
- a scout that reads the same files the implementer must read anyway; include those files in the Dispatch Packet instead.
