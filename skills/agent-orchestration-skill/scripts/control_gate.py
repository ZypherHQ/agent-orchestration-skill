#!/usr/bin/env python3
"""Create and resolve human-control STOP gates for orchestration runs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import emit_event, latest_run_id, read_json, run_dir, safe_id, state_path, utc_now, validate_id, write_json_atomic  # noqa: E402

BLOCKING_GATE_STATUSES = {"waiting", "reject", "rejected", "replan", "pause"}
RESOLVED_GATE_STATUSES = {"approve", "approved", "resume", "merge", "downgrade"}


def resolve(root: Path, run_id: str) -> str:
    if run_id == "latest":
        found = latest_run_id(root)
        if not found:
            raise SystemExit("No orchestration run found.")
        return found
    try:
        return validate_id(run_id, "run_id")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def gate_path(root: Path, run_id: str, gate_id: str) -> Path:
    return run_dir(root, run_id) / "controls" / f"{safe_id(gate_id, 'gate_id', fallback='gate')}.json"


def write_gate(root: Path, run_id: str, gate: dict[str, Any]) -> Path:
    path = gate_path(root, run_id, gate["gate_id"])
    write_json_atomic(path, gate)
    return path


def request(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = resolve(root, args.run_id)
    gate_id = safe_id(args.gate_id, "gate_id", fallback="gate")
    gate = {
        "gate_id": gate_id,
        "run_id": run_id,
        "status": "waiting",
        "kind": args.kind,
        "reason": args.reason,
        "options": args.option or [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    path = write_gate(root, run_id, gate)
    emit_event(root, "stop_gate_waiting", run_id=run_id, status="waiting", phase_id=args.phase_id, summary=args.reason, metadata={"gate_id": gate_id, "kind": args.kind})
    print(json.dumps({"status": "waiting", "gate": str(path)}, indent=2))


def decide(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = resolve(root, args.run_id)
    gate_id = safe_id(args.gate_id, "gate_id", fallback="gate")
    path = gate_path(root, run_id, gate_id)
    gate = read_json(path, {})
    if not gate:
        gate = {"gate_id": gate_id, "run_id": run_id, "kind": "manual", "created_at": utc_now()}
    gate.update({"status": args.action, "decision": args.action, "reason": args.reason, "updated_at": utc_now()})
    if args.payload:
        try:
            gate["payload"] = json.loads(args.payload)
        except json.JSONDecodeError:
            gate["payload"] = args.payload
    write_gate(root, run_id, gate)
    emit_event(root, f"gate_{args.action}", run_id=run_id, status=args.action, summary=args.reason, metadata={"gate_id": gate_id})
    print(json.dumps(gate, indent=2, ensure_ascii=False))


def status(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = resolve(root, args.run_id)
    controls = sorted((run_dir(root, run_id) / "controls").glob("*.json"))
    rows = [read_json(p, {}) for p in controls]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        if not rows:
            print("No gates recorded.")
            return
        for g in rows:
            print(f"{g.get('gate_id')} | {g.get('status')} | {g.get('kind')} | {g.get('reason', '')}")


def gate_blockers(root: Path, run_id: str) -> list[dict[str, Any]]:
    controls = sorted((run_dir(root, run_id) / "controls").glob("*.json"))
    blockers: list[dict[str, Any]] = []
    for p in controls:
        gate = read_json(p, {})
        if not isinstance(gate, dict):
            continue
        status = str(gate.get("status", "")).lower()
        if status in BLOCKING_GATE_STATUSES or status not in RESOLVED_GATE_STATUSES:
            blockers.append({
                "type": "control_gate",
                "gate_id": gate.get("gate_id") or p.stem,
                "status": gate.get("status"),
                "reason": gate.get("reason", ""),
                "path": str(p),
            })
    return blockers


def ownership_blockers(root: Path, run_id: str) -> list[dict[str, Any]]:
    state = read_json(state_path(root, run_id), {})
    if not isinstance(state, dict):
        return []
    blockers: list[dict[str, Any]] = []
    for conflict in state.get("ownership_conflicts", []) or []:
        if isinstance(conflict, dict):
            blockers.append({"type": "ownership_conflict", **conflict})
    claims = state.get("files_claimed", {})
    if isinstance(claims, dict):
        for file, owners in claims.items():
            if isinstance(owners, list):
                unique_owners = sorted({str(x) for x in owners if x})
                if len(unique_owners) > 1:
                    blockers.append({"type": "ownership_conflict", "file": file, "owners": unique_owners})
    return blockers


def enforce(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = resolve(root, args.run_id)
    blockers = gate_blockers(root, run_id) + ownership_blockers(root, run_id)
    result = {"status": "BLOCKED" if blockers else "CLEAR", "run_id": run_id, "blockers": blockers}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["status"])
        for blocker in blockers:
            if blocker["type"] == "control_gate":
                print(f"- gate {blocker.get('gate_id')} is {blocker.get('status')}: {blocker.get('reason', '')}")
            else:
                print(f"- ownership conflict on {blocker.get('file')}: {blocker.get('current_owner') or blocker.get('owners')} -> {blocker.get('new_owner', '')}")
    raise SystemExit(1 if blockers else 0)


def main() -> None:
    ap = argparse.ArgumentParser(description="Manage orchestration STOP gates")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("request")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--gate-id", required=True)
    p.add_argument("--kind", default="manual")
    p.add_argument("--reason", required=True)
    p.add_argument("--phase-id")
    p.add_argument("--option", action="append", default=[])
    p.set_defaults(func=request)

    for name in ["approve", "reject", "replan", "pause", "resume", "downgrade", "merge"]:
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        p.add_argument("--run-id", default="latest")
        p.add_argument("--gate-id", required=True)
        p.add_argument("--reason", default="")
        p.add_argument("--payload", help="Optional JSON/string decision payload")
        p.set_defaults(func=decide, action=name)

    p = sub.add_parser("status")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=status)

    p = sub.add_parser("enforce")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=enforce)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
