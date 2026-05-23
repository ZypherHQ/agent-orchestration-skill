# 05_PR_CANDIDATES.md

## PR Candidates — agent-orchestration-skill

Based on repository analysis, codebase quality audit, and triage findings.

---

### Candidate 1: Fix Reference Filename Typo

**File**: `skills/references/evalation-harness.md` → `evaluation-harness.md`

**Rationale**:
- `evalation` is missing the 'u' — should be `evaluation-harness.md`
- This breaks alphabetical ordering in directory listing
- Inconsistent with naming convention (all other references use full words)
- Easy, self-contained change with no risk

**Change**:
```bash
mv skills/references/evalation-harness.md skills/references/evaluation-harness.md
```

**Labels**: documentation, typo, good-first-issue

---

### Candidate 2: Add pytest Test Suite for Utility Scripts

**Files**: Create `tests/` directory with test files for core utilities

**Rationale**:
- 15 Python scripts are deterministic and testable
- Zero test coverage currently
- `evaluation-harness.md` explicitly lists checks that should be automated
- Tests would prevent regressions as the project grows

**Candidates for testing**:
- `orchestration_decider.py` — deterministic classification
- `batch_tasks.py` — file grouping logic
- `context_coverage_gate.py` — coverage validation
- `failure_classifier.py` — failure classification
- `handoff_validate.py` — handoff validation rules

**Change**: Add `tests/` directory with pytest tests

**Labels**: testing, infrastructure, enhancement

---

### Candidate 3: Add GitHub Actions CI/CD Workflow

**File**: `.github/workflows/ci.yml`

**Rationale**:
- Repository is new (2 days) with no CI visible
- Python project with multiple scripts needs automated linting/type-checking
- Tests (from Candidate 2) would integrate into CI
- Standard practice for any meaningful open source project

**Workflow should cover**:
- `ruff` or `flake8` linting on Python scripts
- `mypy` type checking
- `pytest` test execution
- Cron/merge validation

**Labels**: CI/CD, automation, infrastructure

---

### Candidate 4: Add Type Annotations to Core Scripts

**Files**: Prioritize `context_capsule.py`, `dispatch_compiler.py`, `dag_planner.py`, `budget_governor.py`

**Rationale**:
- None of the 15 Python scripts have type hints
- The project is well-designed architecturally but implementation lacks type safety
- Adding types would improve maintainability and catch errors early
- Most scripts are under 200 lines — feasible to type incrementally

**Change**: Add `from __future__ import annotations` and function-level type hints

**Labels**: enhancement, maintainability, python

---

### Candidate 5: Add Inline Comments to Agent TOML Profiles

**Files**: All 14 `agents/*.toml` files

**Rationale**:
- Agent profiles have fields that aren't self-explanatory (e.g., `tools`, `disabled_tools`, `env`)
- Current profiles have no comments explaining the purpose of each field
- Would help contributors understand agent configuration
- Low effort, high value for onboarding

**Example**:
```toml
[agent]
# reasoning_effort: low|medium|high|xhigh — controls思维链 depth
# Avoid using high/xhigh for simple verification tasks
reasoning_effort = "low"
```

**Labels**: documentation, enhancement, good-first-issue

---

### Candidate 6: Add Missing Reference Document Content

**File**: `skills/references/source-contract-proof.md`

**Rationale**:
- `source-contract-proof.md` is only 13 lines (615 bytes) — very thin
- Other references average 1000-2000 bytes
- The "dependency-backed behavior" guidance is valuable but incomplete
- Could expand with practical examples, anti-patterns, and Context7 usage

**Change**: Expand to ~50 lines with examples and more structured guidance

**Labels**: documentation, enhancement

---

### Candidate 7: Add CONTRIBUTING.md

**File**: `CONTRIBUTING.md`

**Rationale**:
- New repository with no community contribution guidance
- Would define PR standards, testing expectations, and review process
- Align with `evaluation-harness.md` requirements
- Standard practice for professional open source projects

**Labels**: community, documentation, enhancement

---

### Candidate 8: Add a Simple Makefile or Task Runner

**File**: `Makefile` or `tasks.py`

**Rationale**:
- Many scripts with similar patterns (lint, test, validate all TOMLs)
- A Makefile would simplify common operations
- Low effort, high convenience for developers

**Targets**:
- `make test` — run pytest
- `make lint` — run ruff/flake8
- `make validate-config` — validate all TOML files
- `make check-links` — validate markdown links

**Labels**: developer-experience, enhancement, automation

---

### Summary Table

| # | Candidate | Effort | Impact | Risk |
|---|-----------|--------|--------|------|
| 1 | Fix `evalation-harness.md` typo | Low | Low | Very Low |
| 2 | Add pytest test suite | Medium | High | Low |
| 3 | Add GitHub Actions CI/CD | Medium | High | Low |
| 4 | Add type annotations | Medium | Medium | Low |
| 5 | Comment agent TOML profiles | Low | Medium | Very Low |
| 6 | Expand `source-contract-proof.md` | Low | Low | Very Low |
| 7 | Add CONTRIBUTING.md | Low | Medium | Very Low |
| 8 | Add Makefile | Low | Medium | Very Low |