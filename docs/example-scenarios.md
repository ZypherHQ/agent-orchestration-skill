# Example Orchestration Scenarios

This document illustrates how the Agent Orchestration Skill is applied across different task sizes and complexity levels.

## Scenario 1: XS — Direct Fix

**Task:** Fix a typo in `src/utils.rs`.

```text
Fix the typo "recieve" → "receive" in src/utils.rs.
Run cargo fmt.
```

**Decision:** No orchestration. Direct coding run.

**Outcome:** Single edit, no context capsule, no dispatch packet, no worker spawned.

---

## Scenario 2: S — Single Targeted Worker

**Task:** Add missing error handling to `src/auth.rs`.

```text
Use $agent-orchestration-skill.

Task: Add error handling to auth token validation.
Known files: src/auth.rs
Surfaces: backend
Risk: low
Ambiguity: low
```

**Decision:** Task size S. One worker with `low` reasoning if scouting is needed, `medium` for implementation.

**Flow:**
1. Create Context Capsule with task goal.
2. Compile scoped Dispatch Packet pointing to `src/auth.rs` and required coverage.
3. Spawn one leaf worker with bounded instructions.
4. Worker passes Context Coverage, edits, validates.
5. Handoff validated, merged to Run Ledger.
6. Quality gate runs `cargo check`.

**Worker config:** `low` reasoning, single dispatch packet, targeted validation only.

---

## Scenario 3: M — Batched Workers by Surface

**Task:** Implement a new API endpoint across frontend, backend, and tests.

```text
Use $agent-orchestration-skill.

Task: Implement /users/:id/preferences endpoint.
Surfaces: frontend, backend, tests
Known files: 12
Risk: medium
Ambiguity: medium
```

**Decision:** Task size M. Three workers — one per surface — batched by ownership.

**Flow:**
1. Create Context Capsule.
2. Compile three scoped Dispatch Packets, one per surface:
   - `backend`: route handler + middleware
   - `frontend`: API client + types
   - `tests`: integration coverage
3. Spawn three leaf workers in parallel.
4. Each worker passes Context Coverage, executes, validates.
5. Handoffs validated, merged to Run Ledger.
6. Quality gate runs lint, typecheck, and integration tests.

**Worker config:** `medium` reasoning per worker, scoped dispatch, surface-level validation.

---

## Scenario 4: L — DAG Plan with Multiple Phases

**Task:** Refactor the checkout flow across 40 files.

```text
Use $agent-orchestration-skill.

Task: Refactor checkout flow to use new payment SDK.
Surfaces: frontend, backend, shared, tests
Known files: 40
Risk: high
Ambiguity: medium
```

**Decision:** Task size L. DAG plan, Budget Governor check, multiple bounded phases.

**Flow:**
1. Create Context Capsule with refactoring goal and payment SDK contract.
2. Run `dag_planner.py` to build dependency-aware plan.
3. Run `plan_gate.py` to reject vague or circular plans.
4. Run `budget_governor.py` to flag over-orchestration before spawning.
5. Phase 1: shared types + interface (one worker, `high` reasoning).
6. Phase 2: backend implementation (one worker, `high` reasoning).
7. Phase 3: frontend consumer + tests (one worker, `medium` reasoning).
8. Handoffs validated and merged per phase.
9. Full quality gate: lint → typecheck → unit tests → integration tests.

**Worker config:** `high` for architecture-heavy phases, `medium` for consumer phases. Strict dispatch scoping.

---

## Scenario 5: XL — Worktree Isolation with Staged Verification

**Task:** Large migration from REST to GraphQL across the entire codebase.

```text
Use $agent-orchestration-skill.

Task: Migrate all API endpoints from REST to GraphQL.
Surfaces: api, frontend, backend, tests, docs
Known files: 150+
Risk: xhigh
Ambiguity: high
```

**Decision:** Task size XL. Worktree isolation, strict budget checks, staged verification and re-audit.

**Flow:**
1. Create Context Capsule with GraphQL schema contract and migration strategy.
2. Run `dag_planner.py` with explicit phase boundaries.
3. Run `plan_gate.py` — require verifiable milestones per phase.
4. Run `worktree_guard.py` to create isolated worktrees for parallel surfaces.
5. Budget Governor enforces worker caps and phase limits.
6. Phased execution:
   - Phase 1: Schema + types (isolated worktree, `xhigh` reasoning).
   - Phase 2: Backend resolvers (isolated worktree, `high` reasoning).
   - Phase 3: Frontend consumers (isolated worktree, `medium` reasoning).
   - Phase 4: Tests + docs (isolated worktree, `medium` reasoning).
7. Each phase: Context Coverage → dispatch → execute → validate → handoff.
8. Re-audit pass after all phases complete.
9. Full verification: lint → typecheck → tests → build → browser QA.

**Worker config:** Strict dispatch scoping, worktree isolation per phase, re-audit gate before merge.

---

## Anti-Patterns Avoided

| Anti-pattern | What should happen instead |
|---|---|
| One agent per file | Batch by surface, module, or ownership |
| Full transcript broadcast | Context Capsule + scoped Dispatch Packets |
| Nested agent spawn | Root-only orchestration, leaf workers stay leaf |
| Blind edits | Context Coverage Gate confirmation before patching |
| `xhigh` for simple tasks | Route reasoning effort to match task depth |
| Weak verification | Aggressive lint, typecheck, test, build, and QA gates |
| No failure classification | `failure_classifier.py` maps failures before retry |

---

## Quick Reference

| Task size | Workers | Reasoning | Key tools |
|---|---|---|---|
| XS | 0 | — | Direct coding |
| S | 0–1 | low–medium | Context Capsule, Dispatch Packet |
| M | 1–3 | medium | + Handoff Validator, Quality Gate |
| L | 3–5 | medium–high | + DAG Planner, Plan Gate, Budget Governor, Run Ledger |
| XL | 5+ | high–xhigh | + Worktree Guard, Staged phases, Re-audit gate |
