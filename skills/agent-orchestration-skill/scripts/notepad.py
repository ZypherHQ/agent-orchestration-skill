#!/usr/bin/env python3
"""Append compact durable orchestration learnings."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

ALLOWED = {"learnings", "decisions", "issues", "verification", "problems"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Write a compact persistent notepad entry")
    ap.add_argument("--root", default=".")
    ap.add_argument("--kind", choices=sorted(ALLOWED), required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--insight", required=True)
    ap.add_argument("--impact", required=True)
    args = ap.parse_args()
    d = Path(args.root) / ".orchestration" / "notepads"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{args.kind}.md"
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = f"\n## {ts}\n- Context: {args.context}\n- Insight: {args.insight}\n- Future impact: {args.impact}\n"
    path.write_text((path.read_text(encoding="utf-8") if path.exists() else f"# {args.kind.title()}\n") + entry, encoding="utf-8")
    print(str(path))


if __name__ == "__main__":
    main()
