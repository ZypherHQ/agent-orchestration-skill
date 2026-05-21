#!/usr/bin/env python3
"""Classify verification or worker failure output and recommend retry/replan/escalation."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RULES = [
    ("transient_network", re.compile(r"(ECONNRESET|ETIMEDOUT|ENOTFOUND|network|timeout|rate.?limit|temporar)", re.I), "retry_same_worker_once"),
    ("missing_dependency", re.compile(r"(module not found|cannot find module|no such file or directory|command not found|missing dependency)", re.I), "inspect_setup_then_retry"),
    ("format_lint", re.compile(r"(cargo fmt|prettier|eslint|ruff|black|gofmt|format|lint)", re.I), "fix_targeted_or_run_formatter_if_allowed"),
    ("test_assertion", re.compile(r"(AssertionError|assertion failed|expected .* received|FAILED|FAILURES|panicked at)", re.I), "root_cause_before_retry"),
    ("compile_type", re.compile(r"(type error|TS\d{4}|mismatched types|borrow checker|compilation failed|cannot compile)", re.I), "implementation_fix_required"),
    ("permission_sandbox", re.compile(r"(permission denied|operation not permitted|sandbox|read-only file system)", re.I), "escalate_to_parent"),
    ("scope_conflict", re.compile(r"(uncommitted changes|merge conflict|would be overwritten|dirty worktree)", re.I), "preserve_worktree_and_escalate"),
]


def classify(text: str) -> dict:
    hits = []
    for name, rx, action in RULES:
        if rx.search(text):
            hits.append({"kind": name, "recommended_action": action})
    if not hits:
        hits.append({"kind": "unknown", "recommended_action": "summarize_evidence_and_replan_or_escalate"})
    # Conservative action priority.
    priority = ["preserve_worktree_and_escalate", "escalate_to_parent", "implementation_fix_required", "root_cause_before_retry", "inspect_setup_then_retry", "fix_targeted_or_run_formatter_if_allowed", "retry_same_worker_once"]
    action = next((p for p in priority if any(h["recommended_action"] == p for h in hits)), hits[0]["recommended_action"])
    return {"classification": hits, "primary_action": action}


def main() -> None:
    ap = argparse.ArgumentParser(description="Classify failure output")
    ap.add_argument("--file")
    ap.add_argument("--text")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    else:
        text = args.text or ""
    result = classify(text)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Primary action: {result['primary_action']}")
        for h in result["classification"]:
            print(f"- {h['kind']}: {h['recommended_action']}")


if __name__ == "__main__":
    main()
