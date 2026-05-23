#!/usr/bin/env python3
"""Tail global or per-run orchestration events."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import latest_run_id, global_events_path, run_events_path  # noqa: E402


def event_path(root: Path, run_id: str | None) -> Path:
    if run_id == "latest":
        run_id = latest_run_id(root)
    return run_events_path(root, run_id) if run_id else global_events_path(root)


def read_last(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def follow_jsonl(path: Path, start_at_end: bool = True) -> Iterator[dict]:
    while not path.exists():
        time.sleep(0.4)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        if start_at_end:
            f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.4)
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def short(s: object, n: int) -> str:
    text = " ".join(str(s or "").split())
    if len(text) <= n:
        return text
    if n <= 3:
        return text[:n]
    return text[: n - 3] + "..."


def print_event(ev: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(ev, ensure_ascii=False))
        return
    print(
        f"{short(ev.get('ts'), 20):20} "
        f"{short(ev.get('event'), 26):26} "
        f"{short(ev.get('agent'), 24):24} "
        f"{short(ev.get('status'), 12):12} "
        f"{short(ev.get('summary'), 80)}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Tail orchestration events")
    ap.add_argument("--root", default=".")
    ap.add_argument("--run-id", help="Run ID or latest. Omit for global events.")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    path = event_path(root, args.run_id)
    if not args.follow:
        for ev in read_last(path, args.limit):
            print_event(ev, args.json)
        return
    for ev in read_last(path, args.limit):
        print_event(ev, args.json)
    for ev in follow_jsonl(path, start_at_end=True):
        print_event(ev, args.json)


if __name__ == "__main__":
    main()
