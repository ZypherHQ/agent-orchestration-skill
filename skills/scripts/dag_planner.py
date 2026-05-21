#!/usr/bin/env python3
"""Generate a compact dependency-aware phase DAG for Codex orchestration.

The output is intentionally small: it is a plan skeleton for the root orchestrator,
not a long prompt to broadcast to workers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SURFACE_AGENT = {
    "docs": "docs_researcher_medium",
    "research": "docs_researcher_medium",
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
        "acceptance": ["Output satisfies the specific objective", "No unrelated scope expansion"],
        "validation": ["Provide concise evidence or blocker"],
    }


def build_plan(task: str, surfaces: list[str], size: str, risk: str, ambiguity: str, requires_browser: bool, requires_docs: bool) -> dict:
    phases: list[dict] = []
    high = risk in {"high", "critical"} or ambiguity == "high"

    # Planning/read-only phase only when it buys down uncertainty.
    if requires_docs:
        phases.append(phase("P1", "Research only the version-specific technical contracts needed for this task; cite source names in the handoff.", "docs_researcher_medium", kind="research"))
    if ambiguity in {"medium", "high"} or size in {"M", "L", "XL"}:
        deps = [phases[-1]["id"]] if phases else []
        phases.append(phase("P2" if phases else "P1", "Map relevant code paths, owners, tests, and likely blast radius without editing files.", "code_mapper_medium" if not high else "deep_debugger_xhigh", deps=deps, kind="audit", reasoning="xhigh" if high and ambiguity == "high" else "medium"))

    deps = [phases[-1]["id"]] if phases else []
    impl_agent = "micro_implementer_low" if size in {"XS", "S"} and len(surfaces) <= 1 and risk == "low" else "batch_implementer_medium"
    if size in {"L", "XL"} or risk in {"high", "critical"}:
        impl_agent = "complex_implementer_high"
    phases.append(phase(f"P{len(phases)+1}", "Implement the smallest complete scoped change bundle across related files; include targeted validation.", impl_agent, deps=deps, kind="implementation", reasoning="low" if impl_agent == "micro_implementer_low" else "medium" if impl_agent == "batch_implementer_medium" else "high"))

    deps = [phases[-1]["id"]]
    phases.append(phase(f"P{len(phases)+1}", "Run verification commands matched to touched surfaces; collect concise evidence and failures.", "verification_engine_medium" if size not in {"XS", "S"} else "test_runner_low", deps=deps, kind="verification", reasoning="low" if size in {"XS", "S"} else "medium"))

    if requires_browser:
        phases.append(phase(f"P{len(phases)+1}", "Validate changed UI/user flows with browser QA and capture concrete evidence.", "browser_qa_medium", deps=deps, kind="browser_qa"))

    if high:
        phases.append(phase(f"P{len(phases)+1}", "Review the final diff for security/regression risk; do not edit files.", "security_reviewer_high" if risk in {"high", "critical"} else "regression_reviewer_medium", deps=[phases[-1]["id"]], kind="review", reasoning="high"))

    # Hard cap at 7 phases; merge tail reviews if needed.
    if len(phases) > 7:
        keep = phases[:6]
        tail = phases[6:]
        keep.append(phase("P7", "Merged final verification/review for remaining evidence gates.", "verification_engine_medium", deps=list({d for t in tail for d in t.get("depends_on", [])}) or [keep[-1]["id"]], kind="verification"))
        phases = keep

    return {
        "task": task,
        "size": size,
        "risk": risk,
        "ambiguity": ambiguity,
        "surfaces": surfaces,
        "phase_count": len(phases),
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
    ap.add_argument("--out")
    args = ap.parse_args()
    plan = build_plan(args.task, split_csv(args.surfaces), args.size, args.risk, args.ambiguity, args.requires_browser, args.requires_docs)
    text = json.dumps(plan, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
