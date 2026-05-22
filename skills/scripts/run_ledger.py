#!/usr/bin/env python3
"""Persistent orchestration run ledger.

Creates a lightweight control-plane record under .orchestration/runs/<run_id>/.
This is deterministic bookkeeping only; it does not call models.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(text: str, n: int = 36) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:n] or "task"


def make_run_id(task: str) -> str:
    h = hashlib.sha1((task + str(time.time_ns())).encode("utf-8")).hexdigest()[:8]
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{slug(task, 28)}-{h}"


def run_dir(root: Path, run_id: str) -> Path:
    return root / ".orchestration" / "runs" / run_id


def state_path(root: Path, run_id: str) -> Path:
    return run_dir(root, run_id) / "state.json"


def load_state(root: Path, run_id: str) -> dict[str, Any]:
    p = state_path(root, run_id)
    if not p.exists():
        raise SystemExit(f"Run not found: {run_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(root: Path, run_id: str, state: dict[str, Any]) -> None:
    d = run_dir(root, run_id)
    for sub in ["dispatches", "handoffs", "evidence", "logs", "context"]:
        (d / sub).mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    state_path(root, run_id).write_text(json.dumps(state, indent=2), encoding="utf-8")


def init(args: argparse.Namespace) -> None:
    root = Path(args.root)
    run_id = args.run_id or make_run_id(args.task)
    state = {
        "run_id": run_id,
        "task": args.task,
        "mode": args.mode,
        "status": "initialized",
        "context_capsule": args.context_capsule,
        "created_at": now(),
        "updated_at": now(),
        "classification": {},
        "phases": [],
        "agents": {},
        "events": [],
        "files_claimed": {},
        "verification": [],
        "budget": {},
        "risks": [],
    }
    save_state(root, run_id, state)
    print(json.dumps({"run_id": run_id, "state": str(state_path(root, run_id))}, indent=2))


def update(args: argparse.Namespace) -> None:
    root = Path(args.root)
    state = load_state(root, args.run_id)
    if args.status:
        state["status"] = args.status
    event = {"at": now(), "kind": args.kind, "summary": args.summary}
    if args.agent:
        event["agent"] = args.agent
        agent = state.setdefault("agents", {}).setdefault(args.agent, {"events": [], "status": "unknown"})
        agent["events"].append(event)
        if args.agent_status:
            agent["status"] = args.agent_status
    if args.phase:
        event["phase"] = args.phase
    if args.files:
        files = [x.strip() for x in args.files.split(",") if x.strip()]
        event["files"] = files
        for f in files:
            state.setdefault("files_claimed", {}).setdefault(f, args.agent or args.kind)
    if args.evidence:
        event["evidence"] = args.evidence
        state.setdefault("verification", []).append(event)
    state.setdefault("events", []).append(event)
    save_state(root, args.run_id, state)
    print(json.dumps({"run_id": args.run_id, "status": state.get("status"), "event_count": len(state.get("events", []))}, indent=2))


def show(args: argparse.Namespace) -> None:
    state = load_state(Path(args.root), args.run_id)
    print(json.dumps(state, indent=2))


def list_runs(args: argparse.Namespace) -> None:
    root = Path(args.root) / ".orchestration" / "runs"
    rows = []
    for p in sorted(root.glob("*/state.json"), reverse=True):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
            rows.append({"run_id": s.get("run_id"), "status": s.get("status"), "task": s.get("task"), "updated_at": s.get("updated_at")})
        except Exception:
            pass
    print(json.dumps(rows[: args.limit], indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Orchestration run ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--root", default=".")
    p.add_argument("--task", required=True)
    p.add_argument("--mode", default="root")
    p.add_argument("--run-id")
    p.add_argument("--context-capsule", default="")
    p.set_defaults(func=init)

    p = sub.add_parser("update")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", required=True)
    p.add_argument("--status")
    p.add_argument("--kind", default="note")
    p.add_argument("--summary", required=True)
    p.add_argument("--phase")
    p.add_argument("--agent")
    p.add_argument("--agent-status")
    p.add_argument("--files")
    p.add_argument("--evidence")
    p.set_defaults(func=update)

    p = sub.add_parser("show")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=show)

    p = sub.add_parser("list")
    p.add_argument("--root", default=".")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=list_runs)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
