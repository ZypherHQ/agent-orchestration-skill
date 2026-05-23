#!/usr/bin/env python3
"""List, rebuild, and inspect orchestration sessions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import latest_run_id, read_json, rebuild_index, index_path, state_path  # noqa: E402


def load_index(root: Path) -> dict[str, Any]:
    idx = read_json(index_path(root), {})
    if not isinstance(idx, dict) or not idx.get("runs"):
        idx = rebuild_index(root)
    return idx


def rows_from_index(index: dict[str, Any]) -> list[dict[str, Any]]:
    runs = index.get("runs") if isinstance(index.get("runs"), dict) else {}
    rows = list(runs.values())
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return rows


def short(text: Any, width: int) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= width else s[: width - 1] + "…"


def print_table(rows: list[dict[str, Any]], limit: int) -> None:
    rows = rows[:limit]
    if not rows:
        print("No orchestration sessions found.")
        return
    headers = ["RUN ID", "STATUS", "WORKERS", "TESTS", "UPDATED", "TASK"]
    widths = [34, 12, 7, 6, 20, 52]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        vals = [
            short(r.get("run_id"), widths[0]),
            short(r.get("status"), widths[1]),
            str(r.get("worker_count", 0)),
            str(r.get("test_event_count", 0)),
            short(r.get("updated_at"), widths[4]),
            short(r.get("task"), widths[5]),
        ]
        print("  ".join(v.ljust(w) for v, w in zip(vals, widths)))


def cmd_list(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    idx = load_index(root)
    rows = rows_from_index(idx)
    if args.json:
        print(json.dumps(rows[: args.limit], indent=2, ensure_ascii=False))
    else:
        print_table(rows, args.limit)


def cmd_latest(args: argparse.Namespace) -> None:
    rid = latest_run_id(Path(args.root).resolve())
    if not rid:
        raise SystemExit("No orchestration sessions found.")
    print(rid)


def cmd_rebuild(args: argparse.Namespace) -> None:
    idx = rebuild_index(Path(args.root).resolve())
    if args.json:
        print(json.dumps(idx, indent=2, ensure_ascii=False))
    else:
        print(f"Rebuilt index: {len(idx.get('runs', {}))} run(s). latest={idx.get('latest_run_id', '')}")


def cmd_show(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or ""
    if not run_id:
        raise SystemExit("No run ID provided and no latest session found.")
    state = read_json(state_path(root, run_id), {})
    if not state:
        raise SystemExit(f"Run not found: {run_id}")
    print(json.dumps(state, indent=2, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect orchestration session index")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--root", default=".")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("latest")
    p.add_argument("--root", default=".")
    p.set_defaults(func=cmd_latest)

    p = sub.add_parser("rebuild")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_rebuild)

    p = sub.add_parser("show")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.set_defaults(func=cmd_show)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
