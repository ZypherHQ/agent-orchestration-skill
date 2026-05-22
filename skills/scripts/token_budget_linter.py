#!/usr/bin/env python3
"""Check that the orchestration pack stays token-efficient and context-safe."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STALE_PHASE_SKILLS = {
    "subagent-brief-factory", "parallel-task-planner", "docs-research-context7",
    "codebase-360-audit", "implementation-handoff-guard", "aggressive-verification-gate",
    "browser-qa-agent", "re-audit-regression-hunt", "pr-ready-finalizer",
    "subagent-communication-router",
}

STALE_AGENT_FILES = {
    "code-mapper-medium.toml",
    "docs-researcher-medium.toml",
    "micro-implementer-low.toml",
    "deep-debugger-xhigh.toml",
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
    ap = argparse.ArgumentParser(description="Lint skill/agent token economy and context safety.")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--max-skills", type=int, default=1)
    args = ap.parse_args()
    root = Path(args.root)
    problems: list[str] = []

    skills_dir = root / ".agents" / "skills"
    skill_paths = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.exists() else []
    if len(skill_paths) > args.max_skills:
        problems.append(f"Too many discoverable repo skills: {len(skill_paths)} > {args.max_skills}")
    for sp in skill_paths:
        name = sp.parent.name
        fm = parse_frontmatter(sp)
        desc = fm.get("description", "")
        txt = sp.read_text(encoding="utf-8", errors="replace")
        if name in STALE_PHASE_SKILLS:
            problems.append(f"Stale phase skill still installed: {name}")
        if len(desc) > 260:
            problems.append(f"Skill description too long for token economy: {name} ({len(desc)} chars)")
        if name == "agent-orchestration-skill" and "EXPLICIT ONLY" not in desc:
            problems.append("Master skill description should say EXPLICIT ONLY")
        if name == "agent-orchestration-skill" and "$agent-orchestration-skill" not in desc:
            problems.append("Master skill description should include the exact explicit invocation")
        if name == "agent-orchestration-skill":
            for phrase in ["Context Capsule", "Context Coverage", "no nested delegation"]:
                if phrase.lower() not in txt.lower() and phrase.lower() not in desc.lower():
                    problems.append(f"Master skill lacks required context/leaf phrase: {phrase}")

    agents_dir = root / ".codex" / "agents"
    agents = sorted(agents_dir.glob("*.toml")) if agents_dir.exists() else []
    for stale in STALE_AGENT_FILES:
        if (agents_dir / stale).exists():
            problems.append(f"Stale agent file still installed: {stale}")
    for apath in agents:
        txt = apath.read_text(encoding="utf-8")
        name_match = re.search(r'^name\s*=\s*"([^"]+)"', txt, re.M)
        agent_name = name_match.group(1) if name_match else apath.stem
        if "model_reasoning_effort" not in txt:
            problems.append(f"Agent lacks explicit model_reasoning_effort: {apath.name}")
        if "profile =" not in txt:
            problems.append(f"Agent lacks explicit profile: {apath.name}")
        if "Do not invoke" not in txt and "do not invoke" not in txt:
            problems.append(f"Agent lacks no-skill guard: {apath.name}")
        if "LEAF WORKER CONTRACT" not in txt:
            problems.append(f"Agent lacks leaf-worker contract: {apath.name}")
        if "ESCALATE_TO_PARENT" not in txt:
            problems.append(f"Agent lacks escalation-to-parent protocol: {apath.name}")
        if "Context Coverage Check" not in txt:
            problems.append(f"Agent lacks Context Coverage requirement: {apath.name}")
        if "scoped context slice" not in txt:
            problems.append(f"Agent lacks full-capsule loading guard: {apath.name}")
        if "[features]" not in txt or "multi_agent = false" not in txt:
            problems.append(f"Agent does not disable multi-agent tools: {apath.name}")
        if "[agents]" not in txt or "max_depth = 0" not in txt:
            problems.append(f"Agent does not set child max_depth=0: {apath.name}")
        if "max_threads = 1" not in txt:
            problems.append(f"Agent does not cap worker-local max_threads=1: {apath.name}")
        effort_match = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', txt, re.M)
        effort = effort_match.group(1) if effort_match else ""
        if any(k in agent_name for k in ["scout", "mapper", "researcher"]) and effort != "low":
            problems.append(f"Scout/research agent should use low reasoning: {apath.name}")
        if "implementer" in agent_name and "complex" not in agent_name and effort != "medium":
            problems.append(f"Normal implementer should use medium reasoning: {apath.name}")
        if "complex_implementer" in agent_name and effort != "high":
            problems.append(f"Complex implementer should use high reasoning: {apath.name}")
        if "xhigh" in agent_name and "sandbox_mode = \"read-only\"" not in txt:
            problems.append(f"xhigh agent should be read-only planning/strategy by default: {apath.name}")

    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        amd = agents_md.read_text(encoding="utf-8", errors="replace")
        stale_patterns = [
            "next_handoff:",
            "target_agent: <agent type or name>",
            "$subagent-communication-router",
            "Every substantial coding task should use `$agent-orchestration-skill` and spawn specialized subagents unless the task is truly trivial",
            "Codex Agentic Orchestration Pack ",
        ]
        for pat in stale_patterns:
            if pat in amd:
                problems.append(f"AGENTS.md still contains stale orchestration pattern: {pat}")
        required = ["$agent-orchestration-skill", "exact literal invocation", "Normal mode", "Leaf mode"]
        for phrase in required:
            if phrase.lower() not in amd.lower():
                problems.append(f"AGENTS.md lacks explicit-only guard phrase: {phrase}")
        forbidden_auto = [
            "when the task clearly benefits from orchestration",
            "when the user explicitly asks for orchestration, multiagents/subagents",
            "Use `$agent-orchestration-skill` only when explicitly requested or when",
            "Every substantial coding task should use",
        ]
        for phrase in forbidden_auto:
            if phrase.lower() in amd.lower():
                problems.append(f"AGENTS.md still permits implicit orchestration: {phrase}")

    skill_root = root / ".agents" / "skills" / "agent-orchestration-skill"
    for script in ["codex_leaf_exec.sh", "context_capsule.py", "context_coverage_gate.py", "handoff_validate.py", "dispatch_compiler.py"]:
        if not (skill_root / "scripts" / script).exists():
            problems.append(f"Missing required script: {script}")
    for ref in ["context-capsule.md", "context-coverage-gate.md"]:
        if not (skill_root / "references" / ref).exists():
            problems.append(f"Missing required reference: {ref}")

    dispatch_compiler = skill_root / "scripts" / "dispatch_compiler.py"
    if dispatch_compiler.exists():
        dc = dispatch_compiler.read_text(encoding="utf-8", errors="replace")
        for phrase in ["DEFAULT_LIMITS", "DEFAULT_CONTEXT_CHARS = 900", "DEFAULT_PACKET_CHARS = 7000", "CONTEXT CAPSULE SLICE"]:
            if phrase not in dc:
                problems.append(f"Dispatch compiler lacks token cap/slice guard: {phrase}")
    if skill_paths:
        master_text = skill_paths[0].read_text(encoding="utf-8", errors="replace")
        for phrase in ["No full capsule broadcast", "Dispatch budgets", "capsule stays on disk"]:
            if phrase.lower() not in master_text.lower():
                problems.append(f"Master skill lacks token-saving dispatch policy: {phrase}")

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
