#!/usr/bin/env python3
"""Group tasks/files into fewer subagent batches by surface and ownership."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from collections import defaultdict

PATTERNS = [
    ("frontend", re.compile(r"(^|/)(app|pages|components|src/ui|src/components|client|frontend)/|\.(tsx|jsx|vue|svelte|css|scss)$")),
    ("backend", re.compile(r"(^|/)(api|server|backend|routes|controllers|services)/|\.(go|rs|py|rb|php|java|kt|cs)$")),
    ("database", re.compile(r"(^|/)(db|database|migrations|prisma|schema)/|schema\.(sql|prisma)$")),
    ("tests", re.compile(r"(^|/)(test|tests|spec|__tests__)/|\.(test|spec)\.")),
    ("infra", re.compile(r"(^|/)(docker|k8s|infra|deploy|\.github)/|Dockerfile|docker-compose|\.ya?ml$")),
    ("docs", re.compile(r"(^|/)(docs|documentation)/|\.md$")),
]


def surface_for(path_or_task: str) -> str:
    p = path_or_task.lower()
    for name, rx in PATTERNS:
        if rx.search(p):
            return name
    return "general"


def read_items(args) -> list[str]:
    items: list[str] = []
    if args.items:
        items.extend(args.items)
    if args.file:
        items.extend([line.strip() for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip()])
    if args.json_file:
        raw = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, str):
                    items.append(x)
                elif isinstance(x, dict):
                    items.append(x.get("path") or x.get("task") or json.dumps(x))
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch related work to avoid one agent per file.")
    ap.add_argument("items", nargs="*", help="File paths or task lines")
    ap.add_argument("--file", help="Text file with one item per line")
    ap.add_argument("--json-file", help="JSON list of strings or objects")
    ap.add_argument("--max-batches", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    groups = defaultdict(list)
    for item in read_items(args):
        groups[surface_for(item)].append(item)

    # Merge tiny docs/tests/general into related implementation batch where sensible.
    if len(groups.get("docs", [])) <= 2 and "frontend" in groups:
        groups["frontend"].extend(groups.pop("docs", []))
    if len(groups.get("tests", [])) <= 3:
        target = "frontend" if "frontend" in groups else "backend" if "backend" in groups else None
        if target:
            groups[target].extend(groups.pop("tests", []))

    batches = [{"batch": name, "items": vals, "recommended_agent": "batch_implementer_medium" if name not in {"docs"} else "docs_researcher_medium"} for name, vals in groups.items()]
    if len(batches) > args.max_batches:
        # Keep largest batches separate, merge the rest into general.
        batches.sort(key=lambda b: len(b["items"]), reverse=True)
        keep = batches[:args.max_batches-1]
        merged = []
        for b in batches[args.max_batches-1:]:
            merged.extend(b["items"])
        keep.append({"batch": "mixed_tail", "items": merged, "recommended_agent": "batch_implementer_medium"})
        batches = keep

    result = {"batch_count": len(batches), "batches": batches}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Batch count: {len(batches)}")
        for b in batches:
            print(f"\n[{b['batch']}] -> {b['recommended_agent']}")
            for item in b["items"]:
                print(f"- {item}")

if __name__ == "__main__":
    main()
