# Thinking Router

Use the cheapest adequate reasoning effort.

## Low

Use for known files, straightforward edits, simple test updates, formatting-safe patches, narrow validation, and deterministic script execution.

## Medium

Use for normal coding tasks: multiple related files, moderate ambiguity, component state bugs, API integration, browser QA, or test design.

## High

Use for complex logic, security-sensitive review, data migrations, concurrency suspicion, hard regression audit, or multi-module reasoning.

## XHigh

Use only when the task needs deep root-cause reasoning and lower tiers are likely to waste more total tokens through failed attempts. Examples: auth bypass, payment correctness, data loss, race conditions, production incident, critical flaky behavior, multi-surface bug with unknown owner.

## Anti-patterns

- xhigh for a typo, simple CSS tweak, known one-file fix, or isolated import bug.
- high for mechanical changes that can be verified by tests.
- several low agents for a cohesive two-file patch; use one medium worker instead.
