#!/usr/bin/env python3
"""Token-aware orchestration classifier for Codex.

This script does not call models. It deterministically recommends agent count,
reasoning effort, and workflow shape from task metadata.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from typing import List

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
AMB_ORDER = {"low": 0, "medium": 1, "high": 2}
HIGH_RISK_SURFACES = {"auth", "payment", "payments", "security", "database", "data", "migration", "infra", "concurrency"}

@dataclass
class Recommendation:
    size: str
    max_agents: int
    default_agents: List[str]
    reasoning: str
    router_required: bool
    browser_qa: bool
    verification: str
    notes: List[str]


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"1", "true", "yes", "y", "on"}


def decide(task: str, known_files: int, surfaces: List[str], risk: str, ambiguity: str,
           requires_browser: bool, requires_docs: bool, failing_tests: int = 0) -> Recommendation:
    s = {x.strip().lower() for x in surfaces if x.strip()}
    risk_i = RISK_ORDER[risk]
    amb_i = AMB_ORDER[ambiguity]
    high_risk_surface = bool(s & HIGH_RISK_SURFACES)
    notes: List[str] = []

    # Size classification
    if known_files <= 1 and risk_i == 0 and amb_i == 0 and failing_tests <= 1 and not requires_docs:
        size = "XS"
        agents = ["micro_implementer_low"]
        reasoning = "low"
        verification = "targeted"
        max_agents = 1
    elif known_files <= 3 and risk_i <= 1 and amb_i <= 1:
        size = "S"
        agents = ["micro_implementer_low" if known_files <= 1 else "batch_implementer_medium"]
        reasoning = "low" if known_files <= 1 and amb_i == 0 else "medium"
        verification = "targeted+local-gate"
        max_agents = 1 if not requires_browser else 2
    elif known_files <= 8 and risk_i <= 2 and amb_i <= 2:
        size = "M"
        agents = []
        if amb_i >= 1 or known_files == 0:
            agents.append("code_mapper_medium")
        if requires_docs:
            agents.append("docs_researcher_medium")
        agents.append("batch_implementer_medium")
        if requires_browser:
            agents.append("browser_qa_medium")
        else:
            agents.append("verification_engine_medium")
        reasoning = "medium"
        verification = "targeted+lint/type/build-as-relevant"
        max_agents = min(4, len(agents))
    elif risk_i >= 3 or high_risk_surface or amb_i == 2 or known_files > 8:
        size = "XL" if risk_i >= 3 or (amb_i == 2 and high_risk_surface) or known_files > 20 else "L"
        agents = []
        if amb_i == 2 or known_files == 0:
            agents.append("deep_debugger_xhigh" if risk_i >= 2 or high_risk_surface else "code_mapper_medium")
        if requires_docs:
            agents.append("docs_researcher_medium")
        agents.append("complex_implementer_high" if size == "XL" or risk_i >= 2 else "batch_implementer_medium")
        agents.append("security_reviewer_high" if high_risk_surface or risk_i >= 2 else "regression_reviewer_medium")
        agents.append("browser_qa_medium" if requires_browser else "verification_engine_medium")
        reasoning = "xhigh" if "deep_debugger_xhigh" in agents else "high"
        verification = "full-matrix+specialized-review"
        max_agents = 4
    else:
        size = "M"
        agents = ["code_mapper_medium", "batch_implementer_medium", "verification_engine_medium"]
        reasoning = "medium"
        verification = "targeted+lint/type/build-as-relevant"
        max_agents = 3

    # Router only when multiple packets are expected.
    router_required = len(agents) > 2 or (len(agents) > 1 and any(a.endswith("reviewer_high") for a in agents))

    if known_files <= 1 and reasoning in {"high", "xhigh"} and not high_risk_surface:
        notes.append("Downgrade recommended: one-file non-critical work should not use high/xhigh.")
    if len(agents) == 1:
        notes.append("Single worker should perform inspect -> patch -> targeted validation -> handoff.")
    if len(agents) > max_agents:
        agents = agents[:max_agents]
        notes.append("Agent list trimmed to max_agents cap.")
    if requires_browser:
        notes.append("Browser QA required because UI/user flow behavior is in scope.")
    if requires_docs:
        notes.append("Docs research should be short and version-specific; do not research broadly.")

    return Recommendation(
        size=size,
        max_agents=max_agents,
        default_agents=agents,
        reasoning=reasoning,
        router_required=router_required,
        browser_qa=requires_browser,
        verification=verification,
        notes=notes,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Recommend token-efficient Codex orchestration.")
    ap.add_argument("--task", required=True, help="Task summary")
    ap.add_argument("--known-files", type=int, default=0, help="Known/likely files involved")
    ap.add_argument("--surfaces", default="", help="Comma-separated surfaces: frontend,backend,auth,payment,database,infra,tests,browser")
    ap.add_argument("--risk", choices=list(RISK_ORDER), default="medium")
    ap.add_argument("--ambiguity", choices=list(AMB_ORDER), default="medium")
    ap.add_argument("--requires-browser", default="false")
    ap.add_argument("--requires-docs", default="false")
    ap.add_argument("--failing-tests", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="Output compact JSON only")
    args = ap.parse_args()

    rec = decide(
        task=args.task,
        known_files=args.known_files,
        surfaces=args.surfaces.split(","),
        risk=args.risk,
        ambiguity=args.ambiguity,
        requires_browser=parse_bool(args.requires_browser),
        requires_docs=parse_bool(args.requires_docs),
        failing_tests=args.failing_tests,
    )
    data = asdict(rec)
    data["task"] = args.task
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"Task: {args.task}")
        print(f"Size: {rec.size}")
        print(f"Reasoning: {rec.reasoning}")
        print(f"Max agents: {rec.max_agents}")
        print(f"Agents: {', '.join(rec.default_agents)}")
        print(f"Router required: {rec.router_required}")
        print(f"Verification: {rec.verification}")
        for note in rec.notes:
            print(f"- {note}")

if __name__ == "__main__":
    main()
