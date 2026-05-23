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

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from event_emit import emit_event  # type: ignore  # noqa: E402
except Exception:
    emit_event = None  # type: ignore
from typing import Any

BASE_REQUIRED = ["STATUS", "SUMMARY", "VALIDATION"]
FORBIDDEN = ["next_handoff", "target_agent", "spawn_agent", "wait_agent", "resume_agent", "$agent-orchestration-skill"]
FIELD_ALIASES = {
    "STATUS": ["status"],
    "SUMMARY": ["summary"],
    "VALIDATION": ["validation", "tests_or_checks"],
    "CONTEXT_COVERAGE": ["context_coverage", "context coverage"],
    "FILES_READ": ["files_read", "files read", "files_touched_or_examined", "files touched inspected", "files_touched_inspected"],
}
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


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def flatten_value(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"{k}: {flatten_value(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "\n".join(flatten_value(v) for v in value)
    return str(value)


def parse_structured_packet(text: str) -> dict[str, str]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        loaded = json.loads(stripped)
    except json.JSONDecodeError:
        loaded = None
    if isinstance(loaded, dict):
        return {normalize_key(str(k)): flatten_value(v) for k, v in loaded.items()}

    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_ /-]+):\s*(.*)$", line)
        if match and not line.startswith((" ", "\t")):
            current = normalize_key(match.group(1))
            fields.setdefault(current, [])
            if match.group(2).strip():
                fields[current].append(match.group(2).strip())
            continue
        if current:
            fields[current].append(line.strip())
    return {key: "\n".join(vals).strip() for key, vals in fields.items()}


def field_text(fields: dict[str, str], aliases: list[str]) -> str:
    wanted = {normalize_key(alias) for alias in aliases}
    return "\n".join(value for key, value in fields.items() if key in wanted)


def has_field(fields: dict[str, str], upper: str, field: str) -> bool:
    if fields:
        return bool(field_text(fields, FIELD_ALIASES[field]))
    return field in upper


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
    fields = parse_structured_packet(text)
    upper = text.upper()
    lower = text.lower()
    for key in BASE_REQUIRED:
        if not has_field(fields, upper, key):
            problems.append(f"Missing required handoff field: {key}")
    if not has_field(fields, upper, "CONTEXT_COVERAGE") and "CONTEXT COVERAGE" not in upper:
        problems.append("Missing required handoff field: CONTEXT_COVERAGE")
    if not has_field(fields, upper, "FILES_READ") and "FILES READ" not in upper and "FILES TOUCHED / INSPECTED" not in upper:
        problems.append("Missing required handoff field: FILES_READ")
    for bad in FORBIDDEN:
        if bad.lower() in lower:
            problems.append(f"Forbidden routing/delegation text present: {bad}")
    if len(text) > 6000:
        problems.append("Handoff too long; summarize logs and point to evidence files")
    if re.search(r"(?i)chain of thought|private reasoning|scratchpad", text):
        problems.append("Handoff appears to include private reasoning; return evidence, not reasoning")

    required = unique([clean_required_item(x) for x in (required or []) if clean_required_item(x)])
    coverage_source = "\n".join(
        x for x in [
            field_text(fields, FIELD_ALIASES["CONTEXT_COVERAGE"]),
            field_text(fields, FIELD_ALIASES["FILES_READ"]),
        ] if x
    )
    norm_text = normalize(coverage_source or text)
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
    structured_or_text = coverage_source or text
    if missing and re.search(r"(?i)safe_to_modify\s*:\s*true", structured_or_text):
        problems.append("safe_to_modify=true conflicts with missing required context")
    if missing and re.search(r"(?i)missing_context\s*:\s*(\[\s*\]|none|\[?\s*none\s*\]?)", structured_or_text):
        problems.append("missing_context claims empty/none while required context is absent")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a leaf worker Handoff Packet")
    ap.add_argument("packet")
    ap.add_argument("--dispatch", help="Preferred Dispatch Packet for scoped coverage validation")
    ap.add_argument("--capsule", help="Fallback Context Capsule JSON for coverage validation")
    ap.add_argument("--required", action="append", default=[], help="Explicit required file/area for coverage validation")
    ap.add_argument("--full-capsule", action="store_true", help="Validate against every capsule must_read entry even if dispatch is present")
    ap.add_argument("--root", default=".", help="Repo root for optional event logging")
    ap.add_argument("--run-id", help="Optional run ID or latest for event logging")
    ap.add_argument("--phase-id", help="Optional phase ID for event logging")
    ap.add_argument("--agent", help="Optional agent name for event logging")
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
    if emit_event is not None and args.run_id:
        emit_event(Path(args.root), event="handoff_validated" if result["status"] == "OKAY" else "handoff_rejected", run_id=args.run_id, status="passed" if result["status"] == "OKAY" else "failed", phase_id=args.phase_id, agent=args.agent, summary=("handoff_validated" if result["status"] == "OKAY" else "; ".join(result.get("problems", [])[:2])), metadata={"problem_count": len(result.get("problems", []))}, update_state=True)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["status"])
        for p in problems:
            print(f"- {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
