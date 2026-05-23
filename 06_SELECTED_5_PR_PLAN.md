# 06_SELECTED_5_PR_PLAN.md

## Selected 5 PR Plan — agent-orchestration-skill

Priority ordering based on effort, impact, and risk ratio.

---

## PR 1: Fix Reference Filename Typo ⭐ (Highest Priority)

**Issue**: `evalation-harness.md` → `evaluation-harness.md`

### Why First
- Trivial one-liner fix (git mv)
- No risk, no review complexity
- Demonstrates contribution workflow
- Unblocks other reference documentation work

### Plan
```bash
cd /root/oss-pr-campaign/repos/agent-orchestration-skill
git mv skills/references/evalation-harness.md skills/references/evaluation-harness.md
git add -A
git commit -m "fix: rename evalation-harness.md to evaluation-harness.md"
git push origin main
```

### Validation
- `ls skills/references/` shows `evaluation-harness.md` (no evalation)
- README.md and SKILL.md still reference the file correctly (they don't hardcode the filename — they just mention "evaluation-harness.md" conceptually)

---

## PR 2: Add pytest Test Suite for Core Utilities

**Issue**: Zero test coverage on deterministic utility scripts

### Why Second
- Tests protect against regressions
- Scripts are deterministic → easy to test
- Evaluation harness explicitly calls for automated checks
- Foundation for CI/CD in PR 3

### Plan
Create `tests/` directory with:

```
tests/
├── __init__.py
├── test_orchestration_decider.py
├── test_batch_tasks.py
├── test_context_coverage_gate.py
├── test_failure_classifier.py
└── test_handoff_validate.py
```

### Test Strategy
- `test_orchestration_decider.py`: CLI arg parsing, output structure validation
- `test_batch_tasks.py`: File grouping logic with known inputs
- `test_context_coverage_gate.py`: Coverage validation with mock dispatch/handoff
- `test_failure_classifier.py`: Failure classification with sample logs
- `test_handoff_validate.py`: Handoff field validation

### Files to Create/Modify
- Create `tests/` directory
- Create 5 test files (~50 lines each)
- Create `tests/__init__.py`
- Add `pytest` dependency note (if needed, add to any future README updates)

### Validation
```bash
cd /root/oss-pr-campaign/repos/agent-orchestration-skill
python -m pytest tests/ -v
# Expected: all tests pass
```

---

## PR 3: Add GitHub Actions CI/CD

**Issue**: No automated validation on PRs/merges

### Why Third
- Completes the testing infrastructure (PR 2)
- Standard professional practice
- Catches issues before merge
- Low risk with standard actions

### Plan
Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install ruff
      - run: ruff check skills/scripts/ agents/ config.toml

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install mypy
      - run: mypy skills/scripts/ --ignore-missing-imports

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install pytest toml
      - run: python -m pytest tests/ -v

  validate-configs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install toml
      - run: python -c "import toml; [toml.load(f) for f in __import__('os').listdir('agents')]"
```

### Files to Create
- `.github/workflows/ci.yml`

### Validation
- GitHub Actions runs on PR
- All 4 jobs pass

---

## PR 4: Add CONTRIBUTING.md

**Issue**: No contribution guidance for community

### Why Fourth
- Low effort, high impact for community engagement
- Defines standards that CI/CD enforces
- Professional project standard
- Complements the well-documented SKILL.md

### Plan
Create `CONTRIBUTING.md`:

```markdown
# Contributing to Agent Orchestration Skill

## Quick Start

1. Fork and clone the repo
2. Install dependencies: `pip install -r requirements.txt` (if created)
3. Run tests: `python -m pytest tests/ -v`
4. Lint: `ruff check skills/scripts/`

## PR Standards

- All CI checks must pass
- New scripts must have tests
- TOML configs must remain valid
- No implicit skill activation

## What We Accept

- Test coverage for utility scripts
- Documentation improvements
- Type annotation additions
- Reference document expansions
- Developer experience improvements

## What We Avoid

- Changes to SKILL.md core contract without discussion
- Relaxing leaf-worker constraints
- Implicit activation patterns
```

### Files to Create
- `CONTRIBUTING.md`

### Validation
- File exists and is non-empty
- Markdown renders correctly

---

## PR 5: Add Makefile for Common Tasks

**Issue**: Developers manually run scripts with long CLI commands

### Why Fifth
- Improves DX with simple `make` targets
- Low effort, consistent with contributing ecosystem
- Complements CI/CD (lint/test targets)
- Reduces friction for new contributors

### Plan
Create `Makefile`:

```makefile
.PHONY: help test lint typecheck validate-configs clean

help:
	@echo "Available targets:"
	@echo "  test            - Run pytest test suite"
	@echo "  lint            - Run ruff linter on scripts and configs"
	@echo "  typecheck       - Run mypy type checker"
	@echo "  validate-configs - Validate all TOML files"
	@echo "  clean           - Remove __pycache__ and .pyc files"

test:
	python -m pytest tests/ -v

lint:
	ruff check skills/scripts/ agents/ config.toml

typecheck:
	mypy skills/scripts/ --ignore-missing-imports

validate-configs:
	python -c "import toml, os; [toml.load(f) for f in ['config.toml'] + ['agents/'+x for x in os.listdir('agents')])"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
```

### Dependencies
- `pip install ruff mypy pytest toml` (or single `pip install ruff mypy pytest toml`)

### Files to Create
- `Makefile`

### Validation
```bash
make help
make test
make lint
make validate-configs
```

---

## Execution Order

| PR | Description | Risk | Days |
|----|-------------|------|------|
| 1 | Fix `evalation-harness.md` typo | Very Low | 0.5 |
| 2 | Add pytest test suite | Low | 1-2 |
| 3 | Add GitHub Actions CI/CD | Low | 1 |
| 4 | Add CONTRIBUTING.md | Very Low | 0.5 |
| 5 | Add Makefile | Very Low | 0.5 |

**Total estimated time**: 3-4 days (sequential), can be parallelized after PR 1

---

## Out of Scope (For Now)

- Changes to SKILL.md core contract (requires deep discussion)
- Adding new agent profiles (existing 14 are well-designed)
- Expanding reference documents (low priority vs infrastructure)
- Type annotations (nice-to-have but deferrable)