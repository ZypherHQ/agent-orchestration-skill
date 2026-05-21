#!/usr/bin/env python3
"""Check that the orchestration pack stays token-efficient."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

OLD_SKILLS = {
    "subagent-brief-factory", "parallel-task-planner", "docs-research-context7",
    "codebase-360-audit", "implementation-handoff-guard", "aggressive-verification-gate",
    "browser-qa-agent", "re-audit-regression-hunt", "pr-ready-finalizer",
    "subagent-communication-router",
}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    _, fm, _rest = text.split("---", 2)
    out = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Lint skill/agent token economy.")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--max-skills", type=int, default=1)
    args = ap.parse_args()
    root = Path(args.root)
    skills_dir = root / ".agents" / "skills"
    problems = []
    skill_paths = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.exists() else []
    if len(skill_paths) > args.max_skills:
        problems.append(f"Too many discoverable repo skills: {len(skill_paths)} > {args.max_skills}")
    for sp in skill_paths:
        name = sp.parent.name
        fm = parse_frontmatter(sp)
        desc = fm.get("description", "")
        if name in OLD_SKILLS:
            problems.append(f"Old v1.x phase skill still installed: {name}")
        if len(desc) > 240:
            problems.append(f"Skill description too long for token economy: {name} ({len(desc)} chars)")
        if name == "agentic-orchestration-control" and "ROOT ORCHESTRATOR ONLY" not in desc:
            problems.append("Master skill description should say ROOT ORCHESTRATOR ONLY")
    agents = sorted((root / ".codex" / "agents").glob("*.toml")) if (root / ".codex" / "agents").exists() else []
    for apath in agents:
        txt = apath.read_text(encoding="utf-8")
        if "model_reasoning_effort" not in txt:
            problems.append(f"Agent lacks explicit model_reasoning_effort: {apath.name}")
        if "profile =" not in txt:
            problems.append(f"Agent lacks explicit profile workaround: {apath.name}")
        if "Do not invoke" not in txt and "do not invoke" not in txt:
            problems.append(f"Agent lacks no-skill guard: {apath.name}")
        if "LEAF WORKER CONTRACT" not in txt:
            problems.append(f"Agent lacks leaf-worker contract: {apath.name}")
        if "ESCALATE_TO_PARENT" not in txt:
            problems.append(f"Agent lacks escalation-to-parent protocol: {apath.name}")
        if "[features]" not in txt or "multi_agent = false" not in txt:
            problems.append(f"Agent does not disable multi-agent tools: {apath.name}")
        if "[agents]" not in txt or "max_depth = 0" not in txt:
            problems.append(f"Agent does not set child max_depth=0: {apath.name}")
        if "max_threads = 1" not in txt:
            problems.append(f"Agent does not cap worker-local max_threads=1: {apath.name}")
    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        amd = agents_md.read_text(encoding="utf-8", errors="replace")
        stale_patterns = [
            "next_handoff:",
            "target_agent: <agent type or name>",
            "$subagent-communication-router",
            "Every substantial coding task should use `$agentic-orchestration-control` and spawn specialized subagents unless the task is truly trivial",
        ]
        for pat in stale_patterns:
            if pat in amd:
                problems.append(f"AGENTS.md still contains stale v1 orchestration pattern: {pat}")
        if "Runtime mode router" not in amd:
            problems.append("AGENTS.md lacks v2.2 Runtime mode router guard")

    leaf_exec = root / ".agents" / "skills" / "agentic-orchestration-control" / "scripts" / "codex_leaf_exec.sh"
    if not leaf_exec.exists():
        problems.append("Missing codex_leaf_exec.sh hard leaf exec wrapper")

    if problems:
        print("Token budget lint: FAIL")
        for p in problems:
            print(f"- {p}")
        sys.exit(1)
    print("Token budget lint: PASS")
    print(f"Discoverable skills: {len(skill_paths)}")
    print(f"Custom agents checked: {len(agents)}")

if __name__ == "__main__":
    main()
