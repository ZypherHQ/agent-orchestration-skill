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

SCRIPT_DIR = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import emit_event, safe_id, update_index, update_json_atomic, validate_id, write_json_atomic  # type: ignore  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(text: str, n: int = 36) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:n] or "task"


def make_run_id(task: str) -> str:
    h = hashlib.sha1((task + str(time.time_ns())).encode("utf-8")).hexdigest()[:8]
    return safe_id(f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{slug(task, 28)}-{h}", "run_id")


def run_dir(root: Path, run_id: str) -> Path:
    return root / ".orchestration" / "runs" / validate_id(run_id, "run_id")


def state_path(root: Path, run_id: str) -> Path:
    return run_dir(root, run_id) / "state.json"


def load_state(root: Path, run_id: str) -> dict[str, Any]:
    p = state_path(root, run_id)
    if not p.exists():
        raise SystemExit(f"Run not found: {run_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(root: Path, run_id: str, state: dict[str, Any]) -> None:
    d = run_dir(root, run_id)
    for sub in ["dispatches", "handoffs", "evidence", "logs", "context", "controls", "memory"]:
        (d / sub).mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    write_json_atomic(state_path(root, run_id), state)


def init(args: argparse.Namespace) -> None:
    root = Path(args.root)
    run_id = safe_id(args.run_id, "run_id") if args.run_id else make_run_id(args.task)
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
    emit_event(root, event="run_created", run_id=run_id, status="initialized", summary=args.task, task=args.task)
    print(json.dumps({"run_id": run_id, "state": str(state_path(root, run_id))}, indent=2))


def update(args: argparse.Namespace) -> None:
    root = Path(args.root)
    run_id = validate_id(args.run_id, "run_id")
    files = [x.strip() for x in args.files.split(",") if x.strip()] if args.files else []
    path = state_path(root, run_id)
    if not path.exists():
        raise SystemExit(f"Run not found: {run_id}")

    event_holder: dict[str, Any] = {}

    def mutate(state: Any) -> dict[str, Any]:
        if not isinstance(state, dict):
            raise SystemExit(f"Run not found: {run_id}")
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
        if files:
            event["files"] = files
            claims = state.setdefault("files_claimed", {})
            for f in files:
                current_owner = claims.get(f)
                owner = args.agent or args.kind
                if current_owner is None:
                    claims[f] = owner
                elif current_owner != owner:
                    conflict = {"file": f, "current_owner": current_owner, "new_owner": owner, "event": event}
                    conflicts = state.setdefault("ownership_conflicts", [])
                    if conflict not in conflicts:
                        conflicts.append(conflict)
        if args.evidence:
            event["evidence"] = args.evidence
            state.setdefault("verification", []).append(event)
        state.setdefault("events", []).append(event)
        state["updated_at"] = now()
        event_holder["event"] = event
        return state

    state = update_json_atomic(path, {}, mutate)
    event = event_holder.get("event") or {"at": now(), "kind": args.kind, "summary": args.summary}
    emit_event(root, event=args.kind, run_id=run_id, status=state.get("status"), phase_id=args.phase, agent=args.agent, summary=args.summary, files=files, metadata={"evidence": args.evidence} if args.evidence else {}, update_state=False)
    update_index(root, state, event)
    print(json.dumps({"run_id": run_id, "status": state.get("status"), "event_count": len(state.get("events", []))}, indent=2))


def show(args: argparse.Namespace) -> None:
    state = load_state(Path(args.root), validate_id(args.run_id, "run_id"))
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
