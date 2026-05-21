#!/usr/bin/env python3
"""Compile a concise Dispatch Packet for a Codex subagent."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIELDS = [
    "role", "reasoning", "objective", "scope", "allowed", "forbidden",
    "context", "tasks", "acceptance", "validation", "stop", "output"
]


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def split_items(value: str | list | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [x.strip() for x in str(value).split(";") if x.strip()]


def packet(data: dict) -> str:
    role = data.get("role", "worker")
    reasoning = data.get("reasoning", "medium")
    objective = data.get("objective", "Complete the assigned scoped task.")
    scope = data.get("scope", "Only the files/areas listed in this packet.")
    allowed = split_items(data.get("allowed"))
    forbidden = split_items(data.get("forbidden"))
    context = data.get("context", "No extra context provided.")
    tasks = split_items(data.get("tasks"))
    acceptance = split_items(data.get("acceptance"))
    validation = split_items(data.get("validation"))
    stop = data.get("stop", "Stop if required scope is missing, ownership overlaps another agent, or validation exposes unrelated failures.")
    output = data.get("output", "Return a concise Handoff Packet only: STATUS, SUMMARY, FILES, CHANGES, VALIDATION, RISKS, NEXT ACTION.")

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- None specified"

    return f"""ROLE:\n{role}\n\nMODE / REASONING BUDGET:\n{reasoning}\n\nOBJECTIVE:\n{objective}\n\nSCOPE OWNERSHIP:\n{scope}\n\nFILES / AREAS ALLOWED:\n{bullets(allowed)}\n\nFILES / AREAS FORBIDDEN:\n{bullets(forbidden)}\n\nCONTEXT DIGEST:\n{context}\n\nTASK BUNDLE:\n{bullets(tasks)}\n\nACCEPTANCE CRITERIA:\n{bullets(acceptance)}\n\nVALIDATION REQUIRED:\n{bullets(validation)}\n\nSTOP CONDITIONS:\n{stop}\n\nSKILL POLICY:\nDo not invoke repo skills. Do not invoke $agentic-orchestration-control. Do not spawn subagents. Treat this Dispatch Packet as complete unless blocked.\n\nOUTPUT:\n{output}\n"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a short subagent Dispatch Packet.")
    ap.add_argument("--from-json", help="JSON file with packet fields")
    for f in FIELDS:
        ap.add_argument(f"--{f}", default=None)
    args = ap.parse_args()
    data = load_json(args.from_json)
    for f in FIELDS:
        v = getattr(args, f)
        if v is not None:
            data[f] = v
    sys.stdout.write(packet(data))

if __name__ == "__main__":
    main()
