#!/usr/bin/env python3
"""Manage root-owned Context Capsules without prompt bloat.

A Context Capsule preserves important state on disk. Workers should receive only a
small scoped slice through Dispatch Packets, never the whole capsule by default.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from event_emit import emit_event  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - event logging should never break capsule management
    emit_event = None  # type: ignore

LIST_SECTIONS = [
    "must_read", "useful_optional", "forbidden", "confirmed_facts", "rejected_assumptions",
    "decisions", "ownership", "acceptance_criteria", "validation_commands", "blockers", "evidence_refs",
]
SLICE_DEFAULTS = {
    "must_read": 8,
    "useful_optional": 3,
    "forbidden": 6,
    "confirmed_facts": 6,
    "rejected_assumptions": 4,
    "decisions": 4,
    "ownership": 3,
    "acceptance_criteria": 6,
    "validation_commands": 5,
    "blockers": 3,
    "evidence_refs": 4,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def split_entry(value: str) -> dict[str, str]:
    value = value.strip()
    if "::" in value:
        path, reason = value.split("::", 1)
        return {"path": path.strip(), "reason": reason.strip()}
    if any(sep in value for sep in ["/", "\\"]) or "." in Path(value).name:
        return {"path": value}
    return {"value": value}


def entry_to_text(entry: Any) -> str:
    if isinstance(entry, dict):
        if entry.get("path") and entry.get("reason"):
            return f"{entry['path']} — {entry['reason']}"
        return str(entry.get("path") or entry.get("value") or "").strip()
    return str(entry).strip()


def empty_capsule(task: str, goal: str = "", run_id: str = "", task_id: str = "") -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": "context_capsule",
        "task_id": task_id,
        "run_id": run_id,
        "task": task,
        "parent_goal": goal,
        "created_at": now(),
        "updated_at": now(),
        "policy": "persistent storage, not prompt payload; dispatch only scoped slices",
    }
    for section in LIST_SECTIONS:
        data[section] = []
    return data


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Context Capsule not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, capsule: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    capsule["updated_at"] = now()
    path.write_text(json.dumps(capsule, indent=2, ensure_ascii=False), encoding="utf-8")


def infer_root_from_path(path: Path) -> Path:
    parts = list(path.resolve().parts)
    if ".orchestration" in parts:
        idx = parts.index(".orchestration")
        if idx > 0:
            return Path(*parts[:idx])
    return Path(".").resolve()


def maybe_emit(path: Path, event: str, run_id: str | None = None, summary: str = "", metadata: dict[str, Any] | None = None) -> None:
    if emit_event is None:
        return
    try:
        emit_event(infer_root_from_path(path), event=event, run_id=run_id or None, status="ok", summary=summary, metadata=metadata or {})
    except Exception:
        pass


def add_many(capsule: dict[str, Any], section: str, values: list[str]) -> None:
    if not values:
        return
    if section not in LIST_SECTIONS:
        raise SystemExit(f"Unsupported section: {section}")
    target = capsule.setdefault(section, [])
    existing = {entry_to_text(x).lower() for x in target}
    for raw in values:
        item = split_entry(raw)
        key = entry_to_text(item).lower()
        if key and key not in existing:
            target.append(item)
            existing.add(key)


def parse_focus(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        for part in raw.replace(";", ",").split(","):
            term = part.strip().lower()
            if term and term not in out:
                out.append(term)
    return out


def prioritize(entries: list[Any], focus: list[str]) -> list[Any]:
    if not focus:
        return entries
    def score(e: Any) -> tuple[int, int]:
        txt = entry_to_text(e).lower()
        return (sum(1 for term in focus if term in txt), -len(txt))
    return sorted(entries, key=score, reverse=True)


def slice_capsule(capsule: dict[str, Any], focus: list[str], limits: dict[str, int]) -> tuple[dict[str, Any], dict[str, int]]:
    scoped: dict[str, Any] = {
        "task_id": capsule.get("task_id", ""),
        "run_id": capsule.get("run_id", ""),
        "task": capsule.get("task", ""),
        "parent_goal": capsule.get("parent_goal", ""),
        "policy": "scoped slice only; full capsule remains root-owned storage",
    }
    omitted: dict[str, int] = {}
    for section in LIST_SECTIONS:
        entries = prioritize(list(capsule.get(section) or []), focus)
        limit = max(0, int(limits.get(section, SLICE_DEFAULTS.get(section, 4))))
        scoped[section] = entries[:limit]
        omitted[section] = max(0, len(entries) - limit)
    return scoped, omitted


def text_list(entries: list[Any]) -> list[str]:
    return [entry_to_text(e) for e in entries if entry_to_text(e)]


def render_text(capsule: dict[str, Any], max_chars: int = 1600, focus: list[str] | None = None, max_items: int | None = None) -> str:
    limits = dict(SLICE_DEFAULTS)
    if max_items is not None:
        limits = {k: max_items for k in limits}
    scoped, omitted = slice_capsule(capsule, focus or [], limits)
    lines: list[str] = []
    header = capsule.get("task_id") or capsule.get("run_id") or capsule.get("task") or "context"
    lines.append(f"CONTEXT CAPSULE DIGEST: {header}")
    lines.append("Policy: digest only; full capsule stays root-owned storage.")
    if focus:
        lines.append("Focus: " + ", ".join((focus or [])[:6]))
    if scoped.get("task"):
        lines.append(f"Task: {scoped['task']}")
    if scoped.get("parent_goal"):
        lines.append(f"Goal: {scoped['parent_goal']}")
    labels = [
        ("must_read", "Must read before editing"),
        ("forbidden", "Forbidden files/areas"),
        ("confirmed_facts", "Confirmed facts"),
        ("rejected_assumptions", "Rejected assumptions"),
        ("decisions", "Decisions/constraints"),
        ("ownership", "Ownership"),
        ("acceptance_criteria", "Acceptance criteria"),
        ("validation_commands", "Validation"),
        ("blockers", "Blockers"),
        ("evidence_refs", "Evidence refs"),
    ]
    for key, label in labels:
        vals = scoped.get(key) or []
        if not vals and not omitted.get(key):
            continue
        lines.append(f"\n{label}:")
        for item in text_list(vals):
            lines.append(f"- {item}")
        if omitted.get(key):
            lines.append(f"- ... {omitted[key]} more stored on disk")
    text = "\n".join(lines).strip() + "\n"
    if len(text) > max_chars:
        text = text[: max_chars - 96].rstrip() + "\n... [digest truncated; dispatch a narrower slice instead of broadcasting full context]\n"
    return text


def cmd_init(args: argparse.Namespace) -> None:
    capsule = empty_capsule(args.task, args.goal or "", args.run_id or "", args.task_id or "")
    for section, attr in [
        ("must_read", "must_read"), ("useful_optional", "optional"), ("forbidden", "forbidden"),
        ("confirmed_facts", "fact"), ("rejected_assumptions", "rejected"), ("decisions", "decision"),
        ("ownership", "ownership"), ("acceptance_criteria", "acceptance"), ("validation_commands", "validation"),
        ("blockers", "blocker"), ("evidence_refs", "evidence"),
    ]:
        add_many(capsule, section, getattr(args, attr))
    out = Path(args.out)
    save(out, capsule)
    maybe_emit(out, "context_capsule_created", capsule.get("run_id"), f"Context Capsule created for {args.task}", {"must_read": len(capsule["must_read"]), "capsule": str(out)})
    print(json.dumps({"status": "OKAY", "capsule": str(out), "must_read": len(capsule["must_read"])}, indent=2))


def cmd_add(args: argparse.Namespace) -> None:
    path = Path(args.file)
    capsule = load(path)
    add_many(capsule, args.section, args.value)
    save(path, capsule)
    maybe_emit(path, "context_capsule_updated", capsule.get("run_id"), f"Updated capsule section {args.section}", {"section": args.section, "count": len(capsule.get(args.section, []))})
    print(json.dumps({"status": "OKAY", "capsule": str(path), "section": args.section, "count": len(capsule.get(args.section, []))}, indent=2))


def cmd_render(args: argparse.Namespace) -> None:
    print(render_text(load(Path(args.file)), args.max_chars, parse_focus(args.focus), args.max_items), end="")


def cmd_slice(args: argparse.Namespace) -> None:
    capsule_path = Path(args.file)
    capsule = load(capsule_path)
    limits = dict(SLICE_DEFAULTS)
    if args.max_items is not None:
        limits = {k: args.max_items for k in limits}
    for section in LIST_SECTIONS:
        v = getattr(args, "max_" + section, None)
        if v is not None:
            limits[section] = v
    scoped, omitted = slice_capsule(capsule, parse_focus(args.focus), limits)
    context_lines = [f"Capsule: {capsule_path}", "Scoped slice only. Full capsule remains root-owned storage."]
    if scoped.get("task"):
        context_lines.append("Task: " + str(scoped["task"]))
    if scoped.get("parent_goal"):
        context_lines.append("Goal: " + str(scoped["parent_goal"]))
    out = {
        "context": "\n".join(context_lines),
        "must_read": scoped.get("must_read", []),
        "forbidden": scoped.get("forbidden", []),
        "confirmed": scoped.get("confirmed_facts", []),
        "rejected": scoped.get("rejected_assumptions", []),
        "decisions": scoped.get("decisions", []),
        "acceptance": scoped.get("acceptance_criteria", []),
        "validation": scoped.get("validation_commands", []),
        "_omitted": omitted,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_stats(args: argparse.Namespace) -> None:
    capsule = load(Path(args.file))
    digest = render_text(capsule, args.max_chars, parse_focus(args.focus), args.max_items)
    counts = {k: len(capsule.get(k) or []) for k in LIST_SECTIONS}
    print(json.dumps({"status": "OKAY", "counts": counts, "render_chars": len(digest), "max_chars": args.max_chars}, indent=2))


def cmd_merge_handoff(args: argparse.Namespace) -> None:
    path = Path(args.file)
    capsule = load(path)
    handoff_path = Path(args.handoff)
    status = "unknown"
    for line in handoff_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().lower().startswith("status"):
            status = line.split(":", 1)[-1].strip() or status
            break
    add_many(capsule, "evidence_refs", [f"{handoff_path}::handoff status {status}"])
    if args.fact:
        add_many(capsule, "confirmed_facts", args.fact)
    if args.blocker:
        add_many(capsule, "blockers", args.blocker)
    save(path, capsule)
    maybe_emit(path, "context_capsule_updated", capsule.get("run_id"), f"Merged handoff {handoff_path}", {"handoff": str(handoff_path)})
    print(json.dumps({"status": "OKAY", "capsule": str(path), "merged_handoff": str(handoff_path)}, indent=2))


def add_common_init_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--must-read", action="append", default=[])
    p.add_argument("--optional", action="append", default=[])
    p.add_argument("--forbidden", action="append", default=[])
    p.add_argument("--fact", action="append", default=[])
    p.add_argument("--rejected", action="append", default=[])
    p.add_argument("--decision", action="append", default=[])
    p.add_argument("--ownership", action="append", default=[])
    p.add_argument("--acceptance", action="append", default=[])
    p.add_argument("--validation", action="append", default=[])
    p.add_argument("--blocker", action="append", default=[])
    p.add_argument("--evidence", action="append", default=[])


def add_slice_limit_args(p: argparse.ArgumentParser) -> None:
    for section, default in sorted(SLICE_DEFAULTS.items()):
        p.add_argument(f"--max-{section.replace('_', '-')}", dest="max_" + section, type=int, default=None, help=f"Max {section} entries, default {default}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Context Capsule manager")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--task", required=True)
    p.add_argument("--goal", default="")
    p.add_argument("--run-id", default="")
    p.add_argument("--task-id", default="")
    p.add_argument("--out", default=".orchestration/context_capsule.json")
    add_common_init_args(p)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("add")
    p.add_argument("--file", required=True)
    p.add_argument("--section", required=True, choices=LIST_SECTIONS)
    p.add_argument("--value", action="append", required=True)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("render")
    p.add_argument("--file", required=True)
    p.add_argument("--focus", action="append", default=[])
    p.add_argument("--max-chars", type=int, default=1600)
    p.add_argument("--max-items", type=int, default=None)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("slice")
    p.add_argument("--file", required=True)
    p.add_argument("--focus", action="append", default=[])
    p.add_argument("--max-items", type=int, default=None)
    add_slice_limit_args(p)
    p.set_defaults(func=cmd_slice)

    p = sub.add_parser("stats")
    p.add_argument("--file", required=True)
    p.add_argument("--focus", action="append", default=[])
    p.add_argument("--max-chars", type=int, default=1600)
    p.add_argument("--max-items", type=int, default=None)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("merge-handoff")
    p.add_argument("--file", required=True)
    p.add_argument("--handoff", required=True)
    p.add_argument("--fact", action="append", default=[])
    p.add_argument("--blocker", action="append", default=[])
    p.set_defaults(func=cmd_merge_handoff)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
