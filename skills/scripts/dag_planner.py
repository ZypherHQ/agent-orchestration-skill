#!/usr/bin/env python3
"""Generate a compact dependency-aware phase DAG for Codex orchestration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SURFACE_AGENT = {
    "docs": "docs_researcher_low",
    "research": "docs_researcher_low",
    "frontend": "batch_implementer_medium",
    "backend": "batch_implementer_medium",
    "database": "complex_implementer_high",
    "infra": "complex_implementer_high",
    "security": "security_reviewer_high",
    "tests": "verification_engine_medium",
    "browser": "browser_qa_medium",
}


def split_csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def phase(pid: str, objective: str, agent: str, deps: list[str] | None = None, kind: str = "work", reasoning: str = "medium") -> dict:
    return {
        "id": pid,
        "kind": kind,
        "agent": agent,
        "reasoning": reasoning,
        "depends_on": deps or [],
        "objective": objective,
        "context_policy": "Worker receives Context Capsule digest, reads must_read entries before editing, and reports context_coverage.",
        "acceptance": ["Output satisfies the specific objective", "No unrelated scope expansion"],
        "validation": ["Provide concise evidence or blocker"],
    }


def build_plan(task: str, surfaces: list[str], size: str, risk: str, ambiguity: str, requires_browser: bool, requires_docs: bool, needs_architecture: bool) -> dict:
    phases: list[dict] = []
    high_risk = risk in {"high", "critical"}
    very_large = size == "XL" or needs_architecture

    if requires_docs:
        phases.append(phase("P1", "Research only the technical contracts needed for this task; return concise source-backed constraints.", "docs_researcher_low", kind="research", reasoning="low"))

    if very_large and (ambiguity == "high" or needs_architecture):
        deps = [phases[-1]["id"]] if phases else []
        phases.append(phase(f"P{len(phases)+1}", "Create a compact architecture/execution strategy with invariants, risks, required context, and acceptance criteria. Do not edit files.", "strategy_architect_xhigh", deps=deps, kind="strategy", reasoning="xhigh"))
    elif ambiguity in {"medium", "high"} or size in {"M", "L", "XL"}:
        deps = [phases[-1]["id"]] if phases else []
        phases.append(phase(f"P{len(phases)+1}", "Map relevant code paths, owners, tests, and likely blast radius without editing files.", "code_mapper_low", deps=deps, kind="audit", reasoning="low"))

    deps = [phases[-1]["id"]] if phases else []
    if size in {"XS", "S"} and len(surfaces) <= 1 and risk == "low":
        impl_agent = "micro_implementer_medium"
        impl_reasoning = "medium"
    elif size in {"L", "XL"} or high_risk:
        impl_agent = "complex_implementer_high"
        impl_reasoning = "high"
    else:
        impl_agent = "batch_implementer_medium"
        impl_reasoning = "medium"
    phases.append(phase(f"P{len(phases)+1}", "Implement the smallest complete scoped change bundle across related files; include targeted validation.", impl_agent, deps=deps, kind="implementation", reasoning=impl_reasoning))

    deps = [phases[-1]["id"]]
    phases.append(phase(f"P{len(phases)+1}", "Run verification commands matched to touched surfaces; collect concise evidence and failures.", "verification_engine_medium" if size not in {"XS", "S"} else "test_runner_low", deps=deps, kind="verification", reasoning="medium" if size not in {"XS", "S"} else "low"))

    if requires_browser:
        phases.append(phase(f"P{len(phases)+1}", "Validate changed UI/user flows with browser QA and capture concrete evidence.", "browser_qa_medium", deps=deps, kind="browser_qa", reasoning="medium"))

    if high_risk:
        phases.append(phase(f"P{len(phases)+1}", "Review the final diff for security/regression risk; do not edit files.", "security_reviewer_high", deps=[phases[-1]["id"]], kind="review", reasoning="high"))
    elif size in {"L", "XL"}:
        phases.append(phase(f"P{len(phases)+1}", "Review the final diff for regressions and missing tests; do not edit files.", "regression_reviewer_medium", deps=[phases[-1]["id"]], kind="review", reasoning="medium"))

    if len(phases) > 7:
        keep = phases[:6]
        tail = phases[6:]
        keep.append(phase("P7", "Merged final verification/review for remaining evidence gates.", "verification_engine_medium", deps=list({d for t in tail for d in t.get("depends_on", [])}) or [keep[-1]["id"]], kind="verification", reasoning="medium"))
        phases = keep

    return {
        "task": task,
        "size": size,
        "risk": risk,
        "ambiguity": ambiguity,
        "surfaces": surfaces,
        "phase_count": len(phases),
        "context_policy": "Root maintains Context Capsule. Each dispatch includes must_read context. Write workers must pass Context Coverage before editing.",
        "phases": phases,
        "dispatch_policy": "Root compiles short Dispatch Packets per phase. Workers are leaf workers and must not invoke skills or spawn agents.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a compact orchestration DAG")
    ap.add_argument("--task", required=True)
    ap.add_argument("--surfaces", default="")
    ap.add_argument("--size", choices=["XS", "S", "M", "L", "XL"], default="M")
    ap.add_argument("--risk", choices=["low", "medium", "high", "critical"], default="medium")
    ap.add_argument("--ambiguity", choices=["low", "medium", "high"], default="medium")
    ap.add_argument("--requires-browser", action="store_true")
    ap.add_argument("--requires-docs", action="store_true")
    ap.add_argument("--needs-architecture", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    plan = build_plan(args.task, split_csv(args.surfaces), args.size, args.risk, args.ambiguity, args.requires_browser, args.requires_docs, args.needs_architecture)
    text = json.dumps(plan, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
