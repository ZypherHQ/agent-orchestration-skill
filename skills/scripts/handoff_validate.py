#!/usr/bin/env python3
"""Validate compact Handoff Packets from leaf workers.

Prefer scoped Dispatch Packet validation over full Context Capsule validation. The
full capsule is root-owned memory and can include context for other workers; a
worker should be judged against its assigned packet.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BASE_REQUIRED = ["STATUS", "SUMMARY", "VALIDATION"]
FORBIDDEN = ["next_handoff", "target_agent", "spawn_agent", "wait_agent", "resume_agent", "$agent-orchestration-skill"]
SECTION_HEADERS = {
    "ROLE:", "MODE / REASONING BUDGET:", "OBJECTIVE:", "SCOPE OWNERSHIP:",
    "MUST READ BEFORE EDITING:", "FILES / AREAS ALLOWED:", "FILES / AREAS FORBIDDEN:",
    "CONTEXT CAPSULE SLICE:", "CONTEXT CAPSULE DIGEST:", "CONFIRMED FACTS:",
    "REJECTED ASSUMPTIONS:", "DECISIONS / CONSTRAINTS:", "TASK BUNDLE:",
    "ACCEPTANCE CRITERIA:", "VALIDATION REQUIRED:", "CONTEXT COVERAGE CHECK:",
    "STOP CONDITIONS:", "SKILL / DELEGATION POLICY:", "OUTPUT:",
}


def entry_path(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("path") or entry.get("value") or "").strip()
    return str(entry).strip()


def clean_required_item(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^-\s*", "", text).strip()
    if text.lower() in {"none", "none specified", "n/a"}:
        return ""
    for sep in [" — ", "::"]:
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    return text


def load_capsule_required(path: Path) -> list[str]:
    capsule = json.loads(path.read_text(encoding="utf-8"))
    return [entry_path(x) for x in capsule.get("must_read", []) if entry_path(x)]


def load_dispatch_required(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "MUST READ BEFORE EDITING:":
            in_section = True
            continue
        if in_section and stripped in SECTION_HEADERS:
            break
        if in_section:
            item = clean_required_item(stripped)
            if item:
                out.append(item)
    return out


def unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        item = item.strip()
        if item and item.lower() not in seen:
            out.append(item)
            seen.add(item.lower())
    return out


def normalize(s: str) -> str:
    return s.strip().strip('"\'').replace("\\", "/").lower()


def validate(text: str, required: list[str] | None = None) -> list[str]:
    problems: list[str] = []
    upper = text.upper()
    lower = text.lower()
    for key in BASE_REQUIRED:
        if key not in upper:
            problems.append(f"Missing required handoff field: {key}")
    if "CONTEXT_COVERAGE" not in upper and "CONTEXT COVERAGE" not in upper:
        problems.append("Missing required handoff field: CONTEXT_COVERAGE")
    if "FILES_READ" not in upper and "FILES READ" not in upper and "FILES TOUCHED / INSPECTED" not in upper:
        problems.append("Missing required handoff field: FILES_READ")
    for bad in FORBIDDEN:
        if bad.lower() in lower:
            problems.append(f"Forbidden routing/delegation text present: {bad}")
    if len(text) > 6000:
        problems.append("Handoff too long; summarize logs and point to evidence files")
    if re.search(r"(?i)chain of thought|private reasoning|scratchpad", text):
        problems.append("Handoff appears to include private reasoning; return evidence, not reasoning")

    required = unique([clean_required_item(x) for x in (required or []) if clean_required_item(x)])
    norm_text = normalize(text)
    missing: list[str] = []
    base_counts: dict[str, int] = {}
    normalized_required = [normalize(x) for x in required]
    for item in normalized_required:
        base = Path(item).name
        base_counts[base] = base_counts.get(base, 0) + 1
    for original, req in zip(required, normalized_required):
        base = Path(req).name
        base_allowed = len(base) >= 4 and base_counts.get(base, 0) == 1
        if req not in norm_text and (not base_allowed or base not in norm_text):
            missing.append(original)
    if missing:
        problems.append("Context Coverage missing required files/areas: " + ", ".join(missing[:10]))
    if missing and re.search(r"(?i)safe_to_modify\s*:\s*true", text):
        problems.append("safe_to_modify=true conflicts with missing required context")
    if missing and re.search(r"(?i)missing_context\s*:\s*\[?\s*(none|\[\])\s*\]?", text):
        problems.append("missing_context claims empty/none while required context is absent")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a leaf worker Handoff Packet")
    ap.add_argument("packet")
    ap.add_argument("--dispatch", help="Preferred Dispatch Packet for scoped coverage validation")
    ap.add_argument("--capsule", help="Fallback Context Capsule JSON for coverage validation")
    ap.add_argument("--required", action="append", default=[], help="Explicit required file/area for coverage validation")
    ap.add_argument("--full-capsule", action="store_true", help="Validate against every capsule must_read entry even if dispatch is present")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    required: list[str] = []
    required.extend(args.required)
    if args.dispatch:
        required.extend(load_dispatch_required(Path(args.dispatch)))
    if args.capsule and (args.full_capsule or not required):
        required.extend(load_capsule_required(Path(args.capsule)))
    text = Path(args.packet).read_text(encoding="utf-8", errors="replace")
    problems = validate(text, required)
    result = {"status": "REJECT" if problems else "OKAY", "problems": problems, "required_count": len(unique(required))}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["status"])
        for p in problems:
            print(f"- {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
