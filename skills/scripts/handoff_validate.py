#!/usr/bin/env python3
"""Validate compact Handoff Packets from leaf workers."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = ["STATUS", "SUMMARY", "FILES", "VALIDATION"]
FORBIDDEN = ["next_handoff", "target_agent", "spawn_agent", "wait_agent", "$agentic-orchestration-control"]


def validate(text: str) -> list[str]:
    problems: list[str] = []
    upper = text.upper()
    for key in REQUIRED:
        if key not in upper:
            problems.append(f"Missing required handoff field: {key}")
    for bad in FORBIDDEN:
        if bad.lower() in text.lower():
            problems.append(f"Forbidden routing/delegation text present: {bad}")
    if len(text) > 6000:
        problems.append("Handoff too long; summarize logs and point to evidence files")
    if re.search(r"(?i)chain of thought|private reasoning|scratchpad", text):
        problems.append("Handoff appears to include private reasoning; return evidence, not reasoning")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a leaf worker handoff packet")
    ap.add_argument("packet")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    text = Path(args.packet).read_text(encoding="utf-8", errors="replace")
    problems = validate(text)
    result = {"status": "REJECT" if problems else "OKAY", "problems": problems}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["status"])
        for p in problems:
            print(f"- {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
