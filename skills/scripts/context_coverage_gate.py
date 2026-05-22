#!/usr/bin/env python3
"""Validate that a worker handoff covers the required context for its scoped dispatch.

Prefer validating against a Dispatch Packet, because the full Context Capsule may
contain entries for other workers. The capsule is persistent root memory; the
Dispatch Packet is the worker's actual required context.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

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


def normalize_path(p: str) -> str:
    return p.strip().strip('"\'').replace("\\", "/").lower()


def clean_required_item(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^-\s*", "", text).strip()
    if text.lower() in {"none", "none specified", "n/a"}:
        return ""
    # Drop reason text while preserving the path/area.
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
    lines = text.splitlines()
    in_section = False
    out: list[str] = []
    for line in lines:
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


def validate(required: list[str], handoff: str, require_explicit: bool = True) -> list[str]:
    problems: list[str] = []
    lower = handoff.lower()
    if require_explicit and "context" not in lower:
        problems.append("Handoff lacks context coverage section")
    for bad in FORBIDDEN:
        if bad.lower() in lower:
            problems.append(f"Forbidden delegation/routing text present: {bad}")
    normalized_text = normalize_path(handoff)
    normalized_required = [normalize_path(path) for path in required]
    basename_counts: dict[str, int] = {}
    for nreq in normalized_required:
        base = Path(nreq).name
        basename_counts[base] = basename_counts.get(base, 0) + 1
    missing: list[str] = []
    for path, n in zip(required, normalized_required):
        basename = Path(n).name
        basename_allowed = len(basename) >= 4 and basename_counts.get(basename, 0) == 1
        if n not in normalized_text and (not basename_allowed or basename not in normalized_text):
            missing.append(path)
    if missing:
        problems.append("Required context not covered: " + ", ".join(missing[:10]))
    if re.search(r"(?i)safe_to_modify\s*:\s*true", handoff) and missing:
        problems.append("Handoff claims safe_to_modify=true while required context is missing")
    if re.search(r"(?i)missing_context\s*:\s*\[?\s*none\s*\]?", handoff) and missing:
        problems.append("Handoff claims no missing context but required context is absent")
    return problems


def unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        item = item.strip()
        if item and item.lower() not in seen:
            out.append(item)
            seen.add(item.lower())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Context Coverage Gate")
    ap.add_argument("--capsule", help="Context Capsule JSON. Used only when no dispatch/required list is provided, unless --full-capsule is set.")
    ap.add_argument("--dispatch", help="Dispatch Packet for this worker; preferred source of required context")
    ap.add_argument("--required", action="append", default=[], help="Explicit required file/area for this worker")
    ap.add_argument("--full-capsule", action="store_true", help="Validate against every must_read entry in the capsule")
    ap.add_argument("--handoff", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-explicit-section", action="store_true", help="Do not require the word context in the handoff")
    args = ap.parse_args()

    required: list[str] = []
    if args.required:
        required.extend(args.required)
    if args.dispatch:
        required.extend(load_dispatch_required(Path(args.dispatch)))
    if args.capsule and (args.full_capsule or not required):
        required.extend(load_capsule_required(Path(args.capsule)))
    required = unique([clean_required_item(x) for x in required if clean_required_item(x)])
    if not required:
        raise SystemExit("No required context found. Provide --dispatch, --required, or --capsule.")

    handoff = Path(args.handoff).read_text(encoding="utf-8", errors="replace")
    problems = validate(required, handoff, require_explicit=not args.no_explicit_section)
    result = {"status": "REJECT" if problems else "OKAY", "problems": problems, "required_count": len(required), "required": required}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["status"])
        for p in problems:
            print(f"- {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
