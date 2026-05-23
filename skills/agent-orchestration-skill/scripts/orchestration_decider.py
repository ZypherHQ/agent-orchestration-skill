#!/usr/bin/env python3
"""Recommend minimal useful orchestration, agent count, and reasoning effort."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
AMB_ORDER = {"low": 0, "medium": 1, "high": 2}
HIGH_RISK_SURFACES = {"auth", "payment", "payments", "security", "database", "data", "migration", "concurrency", "production"}
UI_SURFACES = {"frontend", "ui", "browser"}
DOC_SURFACES = {"docs", "research", "dependency"}


@dataclass
class Recommendation:
    size: str
    max_agents: int
    default_agents: list[str]
    reasoning: str
    context_capsule_required: bool
    router_required: bool
    browser_qa: bool
    verification: str
    spawn_policy: str
    notes: list[str]


def parse_bool(v: str | bool) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def dedupe_cap(agents: list[str], cap: int) -> list[str]:
    out: list[str] = []
    for a in agents:
        if a not in out:
            out.append(a)
    return out[:cap]


def decide(
    task: str,
    known_files: int,
    surfaces: list[str],
    risk: str,
    ambiguity: str,
    requires_browser: bool,
    requires_docs: bool,
    failing_tests: int,
    needs_architecture: bool = False,
    root_can_edit: bool = True,
    force_delegate: bool = False,
) -> Recommendation:
    sset = {s.strip().lower() for s in surfaces if s.strip()}
    risk_i = RISK_ORDER[risk]
    amb_i = AMB_ORDER[ambiguity]
    high_risk_surface = bool(sset & HIGH_RISK_SURFACES)
    task_l = task.lower()
    architecture_terms = ["architecture", "architect", "design", "structure", "structuring", "major feature", "new feature", "system design", "redesign", "refactor architecture"]
    if not needs_architecture and any(term in task_l for term in architecture_terms) and (amb_i >= 1 or risk_i >= 1 or len(sset) >= 2 or known_files == 0):
        needs_architecture = True
    requires_browser = requires_browser or bool(sset & UI_SURFACES)
    requires_docs = requires_docs or bool(sset & DOC_SURFACES)
    notes: list[str] = []

    if known_files <= 1 and risk_i == 0 and amb_i == 0 and failing_tests <= 1 and not needs_architecture and not requires_browser and not requires_docs:
        size = "XS"
        max_agents = 1 if (force_delegate or not root_can_edit) else 0
        agents = ["micro_implementer_medium"] if max_agents else []
        reasoning = "medium" if agents else "low"
        verification = "targeted"
        spawn_policy = "one_worker_due_to_root_edit_boundary" if agents else "no_subagent_preferred"
        notes.append("Do not create ledger, DAG, router, or Context Capsule unless the task expands.")
        if not agents:
            notes.append("Direct execution is cheaper than opening a fresh worker context for a tiny known-scope task.")
    elif known_files <= 3 and risk_i <= 1 and amb_i <= 1 and not needs_architecture:
        size = "S"
        max_agents = 1
        agents = ["batch_implementer_medium" if known_files > 1 else "micro_implementer_medium"]
        reasoning = "medium"
        verification = "targeted"
        spawn_policy = "single_bundled_worker"
        notes.append("One worker should inspect, patch, and run targeted validation. Do not spawn a separate scout unless owner is unknown.")
        if requires_browser:
            notes.append("Keep browser checks targeted; spawn browser_qa only if separate evidence is required.")
        if requires_docs:
            notes.append("Keep docs lookup bounded; spawn docs_researcher only if the implementation contract is unclear.")
    elif known_files <= 8 and risk_i <= 2 and not needs_architecture:
        size = "M"
        max_agents = 3
        agents: list[str] = []
        if amb_i >= 1 or known_files == 0:
            agents.append("code_mapper_low")
        if requires_docs and amb_i >= 1:
            agents.append("docs_researcher_low")
        agents.append("batch_implementer_medium")
        if failing_tests > 1 or risk_i >= 1 or requires_browser:
            agents.append("verification_engine_medium")
        if requires_browser and risk_i >= 1:
            agents.append("browser_qa_medium")
        reasoning = "medium"
        verification = "matrix" if failing_tests > 1 or risk_i >= 1 else "targeted+selected-matrix"
        spawn_policy = "small_wave_with_batched_write"
    elif known_files <= 20 and risk_i <= 2 and not needs_architecture:
        size = "L"
        max_agents = 4
        agents = []
        if amb_i >= 1 or known_files == 0:
            agents.append("code_mapper_low")
        if requires_docs:
            agents.append("docs_researcher_low")
        agents.append("complex_implementer_high" if high_risk_surface or amb_i == 2 else "batch_implementer_medium")
        agents.append("verification_engine_medium")
        if requires_browser:
            agents.append("browser_qa_medium")
        if high_risk_surface:
            agents.append("security_reviewer_high")
        reasoning = "high" if high_risk_surface or amb_i == 2 else "medium"
        verification = "full"
        spawn_policy = "bounded_control_plane"
    else:
        size = "XL"
        max_agents = 5
        agents = []
        if needs_architecture or amb_i == 2 or risk_i >= 2:
            agents.append("strategy_architect_xhigh")
        else:
            agents.append("code_mapper_low")
        if requires_docs:
            agents.append("docs_researcher_low")
        agents.append("complex_implementer_high")
        agents.append("verification_engine_medium")
        if requires_browser:
            agents.append("browser_qa_medium")
        if high_risk_surface or risk_i >= 2:
            agents.append("security_reviewer_high")
        reasoning = "xhigh" if "strategy_architect_xhigh" in agents else "high"
        verification = "full+review"
        spawn_policy = "architecture_first_then_bounded_workers"

    agents = dedupe_cap(agents, max_agents)
    context_capsule_required = size in {"M", "L", "XL"} or len(agents) > 1
    router_required = len(agents) > 2
    if size in {"M", "L", "XL"}:
        notes.append("Use Context Capsule as persistent storage, but dispatch only a scoped slice to each worker.")
    if router_required:
        notes.append("Use communication_router_low only after multiple handoffs or conflicts; never pre-route a single worker result.")
    if "strategy_architect_xhigh" in agents:
        notes.append("xhigh is read-only planning/architecture; implementation should be high/medium after the plan is clear.")
    if len(agents) == 1:
        notes.append("Single worker must complete: context coverage -> inspect -> patch/verify -> handoff.")

    return Recommendation(size, max_agents, agents, reasoning, context_capsule_required, router_required, requires_browser, verification, spawn_policy, notes)


def main() -> None:
    ap = argparse.ArgumentParser(description="Recommend token-efficient orchestration.")
    ap.add_argument("--task", required=True)
    ap.add_argument("--known-files", type=int, default=0)
    ap.add_argument("--surfaces", default="")
    ap.add_argument("--risk", choices=list(RISK_ORDER), default="medium")
    ap.add_argument("--ambiguity", choices=list(AMB_ORDER), default="medium")
    ap.add_argument("--requires-browser", default="false")
    ap.add_argument("--requires-docs", default="false")
    ap.add_argument("--failing-tests", type=int, default=0)
    ap.add_argument("--needs-architecture", default="false")
    ap.add_argument("--root-can-edit", default="true")
    ap.add_argument("--force-delegate", default="false")
    ap.add_argument("--json", action="store_true")
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
        needs_architecture=parse_bool(args.needs_architecture),
        root_can_edit=parse_bool(args.root_can_edit),
        force_delegate=parse_bool(args.force_delegate),
    )
    data = asdict(rec)
    data["task"] = args.task
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"Task: {args.task}")
        print(f"Size: {rec.size}")
        print(f"Reasoning: {rec.reasoning}")
        print(f"Spawn policy: {rec.spawn_policy}")
        print(f"Max agents: {rec.max_agents}")
        print(f"Agents: {', '.join(rec.default_agents) if rec.default_agents else 'none'}")
        print(f"Context Capsule required: {rec.context_capsule_required}")
        print(f"Router required: {rec.router_required}")
        print(f"Verification: {rec.verification}")
        for note in rec.notes:
            print(f"- {note}")


if __name__ == "__main__":
    main()
