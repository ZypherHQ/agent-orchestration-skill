#!/usr/bin/env python3
"""Validate a compact orchestration DAG before spawning workers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED = {"id", "agent", "objective", "depends_on", "acceptance", "validation", "context_policy"}


def dependency_cycles(phases: list[dict]) -> list[str]:
    graph: dict[str, list[str]] = {}
    for ph in phases:
        pid = str(ph.get("id", ""))
        if pid:
            graph[pid] = [str(dep) for dep in (ph.get("depends_on", []) or [])]

    cycles: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(pid: str) -> None:
        if pid in visited:
            return
        if pid in visiting:
            start = stack.index(pid) if pid in stack else 0
            cycles.append(" -> ".join(stack[start:] + [pid]))
            return
        visiting.add(pid)
        stack.append(pid)
        for dep in graph.get(pid, []):
            if dep in graph:
                visit(dep)
        stack.pop()
        visiting.remove(pid)
        visited.add(pid)

    for pid in graph:
        visit(pid)
    return cycles


def validate(plan: dict) -> list[str]:
    problems: list[str] = []
    phases = plan.get("phases")
    if not isinstance(phases, list) or not phases:
        return ["Plan has no phases"]
    if len(phases) > 7:
        problems.append(f"Plan has too many phases: {len(phases)} > 7")
    ids: set[str] = set()
    for i, ph in enumerate(phases, 1):
        missing = REQUIRED - set(ph)
        if missing:
            problems.append(f"Phase {i} missing fields: {', '.join(sorted(missing))}")
        pid = str(ph.get("id", ""))
        if not pid:
            problems.append(f"Phase {i} has empty id")
        if pid in ids:
            problems.append(f"Duplicate phase id: {pid}")
        ids.add(pid)
        obj = str(ph.get("objective", ""))
        if len(obj) < 20:
            problems.append(f"Phase {pid or i} objective too vague")
        for field in ["acceptance", "validation"]:
            val = ph.get(field)
            if not isinstance(val, list) or not val:
                problems.append(f"Phase {pid or i} has no {field} list")
        agent = str(ph.get("agent", ""))
        if not agent:
            problems.append(f"Phase {pid or i} has no agent")
    for ph in phases:
        pid = str(ph.get("id", ""))
        for dep in ph.get("depends_on", []) or []:
            if dep not in ids:
                problems.append(f"Phase {pid} depends on unknown phase {dep}")
            if dep == pid:
                problems.append(f"Phase {pid} depends on itself")
    for cycle in dependency_cycles([ph for ph in phases if isinstance(ph, dict)]):
        problems.append(f"Dependency cycle detected: {cycle}")
    kinds = {str(ph.get("kind", "")) for ph in phases}
    if "implementation" not in kinds and plan.get("size") not in {"audit", "research"}:
        problems.append("No implementation phase present for a non-read-only plan")
    if "verification" not in kinds and plan.get("size") not in {"audit", "research"}:
        problems.append("No verification phase present for a non-read-only plan")
    policy = str(plan.get("dispatch_policy", ""))
    if "must not invoke skills" not in policy.lower() or "must not" not in policy.lower():
        problems.append("Dispatch policy must explicitly prevent worker skill invocation/delegation")
    context_policy = str(plan.get("context_policy", ""))
    if "context capsule" not in context_policy.lower() or "context coverage" not in context_policy.lower():
        problems.append("Plan must include Context Capsule and Context Coverage policy")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Binary plan executable gate")
    ap.add_argument("plan_json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    problems = validate(plan)
    result = {"status": "REJECT" if problems else "OKAY", "problems": problems[:10], "phase_count": len(plan.get("phases", [])) if isinstance(plan.get("phases"), list) else 0}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["status"])
        for p in result["problems"]:
            print(f"- {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
