#!/usr/bin/env python3
"""Append orchestration events and keep session indexes in sync.

This script is the filesystem event bus for the optional control-room/TUI layer.
It is deterministic and model-free. Events are compact JSONL records designed to
be read by the dashboard without parsing verbose agent logs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_EVENT_LIMIT = 250
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def orchestration_dir(root: Path) -> Path:
    return root / ".orchestration"


def slugify_id(value: Any, fallback: str = "id", max_len: int = 96) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text)
    text = text.replace("..", "-")
    text = text.strip("._-")
    return (text[:max_len].strip("._-") or fallback)


def validate_id(value: Any, label: str = "id") -> str:
    text = str(value or "").strip()
    if (
        not SAFE_ID_RE.fullmatch(text)
        or "/" in text
        or "\\" in text
        or ".." in text
        or text in {".", ".."}
    ):
        raise ValueError(f"Invalid {label}: {value!r}")
    return text


def safe_id(value: Any, label: str = "id", fallback: str = "id", max_len: int = 96) -> str:
    return validate_id(slugify_id(value, fallback=fallback, max_len=max_len), label)


def run_dir(root: Path, run_id: str) -> Path:
    return orchestration_dir(root) / "runs" / validate_id(run_id, "run_id")


def state_path(root: Path, run_id: str) -> Path:
    return run_dir(root, run_id) / "state.json"


def index_path(root: Path) -> Path:
    return orchestration_dir(root) / "index.json"


def global_events_path(root: Path) -> Path:
    return orchestration_dir(root) / "events.jsonl"


def run_events_path(root: Path, run_id: str) -> Path:
    return run_dir(root, run_id) / "events.jsonl"


def lock_path(path: Path) -> Path:
    return path.parent / f".{path.name}.lock"


@contextmanager
def file_lock(path: Path, timeout: float = 30.0):
    """Serialize read-modify-write operations for one state file."""
    lock = lock_path(path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is not None:
        with lock.open("a+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return

    lock_dir = lock.with_suffix(lock.suffix + ".d")
    deadline = time.monotonic() + timeout
    while True:
        try:
            lock_dir.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock: {lock_dir}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock_dir.rmdir()
        except FileNotFoundError:
            pass


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json_atomic_unlocked(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def write_json_atomic(path: Path, data: Any) -> None:
    with file_lock(path):
        _write_json_atomic_unlocked(path, data)


def update_json_atomic(path: Path, default: Any, updater) -> Any:
    with file_lock(path):
        data = read_json(path, default)
        updated = updater(data)
        _write_json_atomic_unlocked(path, updated)
        return updated


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    with file_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def csv_items(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        item = chunk.strip()
        if item and item not in out:
            out.append(item)
    return out


def parse_meta(items: list[str] | None, metadata_json: str | None) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if metadata_json:
        try:
            loaded = json.loads(metadata_json)
            if isinstance(loaded, dict):
                meta.update(loaded)
            else:
                meta["value"] = loaded
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --metadata-json: {exc}") from exc
    for item in items or []:
        if "=" not in item:
            meta[item] = True
            continue
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        if v.lower() in {"true", "false"}:
            meta[k] = v.lower() == "true"
        else:
            try:
                meta[k] = int(v)
            except ValueError:
                meta[k] = v
    return meta


def task_slug(task: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", task.lower()).strip("-")
    return slug[:42] or "task"


def latest_run_id(root: Path) -> str | None:
    index = read_json(index_path(root), {})
    latest = index.get("latest_run_id") if isinstance(index, dict) else None
    if latest:
        try:
            latest = validate_id(latest, "latest_run_id")
        except ValueError:
            latest = None
    if latest and state_path(root, latest).exists():
        return str(latest)
    runs = []
    for sp in (orchestration_dir(root) / "runs").glob("*/state.json"):
        try:
            s = json.loads(sp.read_text(encoding="utf-8"))
            run_id = s.get("run_id") or sp.parent.name
            run_id = validate_id(run_id, "run_id")
            runs.append((s.get("updated_at") or s.get("created_at") or "", run_id))
        except Exception:
            continue
    if not runs:
        return None
    runs.sort(reverse=True)
    return runs[0][1]


def resolve_run_id(root: Path, run_id: str | None) -> str | None:
    if not run_id:
        return None
    if run_id == "latest":
        found = latest_run_id(root)
        if not found:
            raise SystemExit("No orchestration run exists yet.")
        return found
    try:
        return validate_id(run_id, "run_id")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def ensure_state(root: Path, run_id: str, task: str | None = None) -> dict[str, Any]:
    run_id = validate_id(run_id, "run_id")
    path = state_path(root, run_id)
    if path.exists():
        return read_json(path, {})
    now = utc_now()
    state = {
        "run_id": run_id,
        "task": task or task_slug(run_id),
        "status": "initialized",
        "created_at": now,
        "updated_at": now,
        "classification": {},
        "phases": [],
        "agents": {},
        "events": [],
        "files_claimed": {},
        "verification": [],
        "budget": {},
        "risks": [],
    }
    write_json_atomic(path, state)
    return state


def summarize_state(state: dict[str, Any], last_event: dict[str, Any] | None = None) -> dict[str, Any]:
    agents = state.get("agents") if isinstance(state.get("agents"), dict) else {}
    tests = state.get("verification") if isinstance(state.get("verification"), list) else []
    return {
        "run_id": state.get("run_id"),
        "task": state.get("task", ""),
        "status": state.get("status", "unknown"),
        "mode": state.get("mode", ""),
        "created_at": state.get("created_at", ""),
        "updated_at": state.get("updated_at", ""),
        "worker_count": len(agents),
        "test_event_count": len(tests),
        "last_event": (last_event or {}).get("event") or state.get("last_event", {}).get("event", ""),
        "last_summary": (last_event or {}).get("summary") or state.get("last_event", {}).get("summary", ""),
    }


def rebuild_index(root: Path) -> dict[str, Any]:
    runs: dict[str, Any] = {}
    latest: tuple[str, str] | None = None
    for sp in sorted((orchestration_dir(root) / "runs").glob("*/state.json")):
        state = read_json(sp, {})
        try:
            run_id = validate_id(state.get("run_id") or sp.parent.name, "run_id")
        except ValueError:
            continue
        runs[run_id] = summarize_state(state)
        updated = str(state.get("updated_at") or state.get("created_at") or "")
        if latest is None or updated > latest[0]:
            latest = (updated, run_id)
    index = {
        "schema": "agent_orchestration_index",
        "updated_at": utc_now(),
        "latest_run_id": latest[1] if latest else "",
        "runs": runs,
    }
    write_json_atomic(index_path(root), index)
    return index


def update_index(root: Path, state: dict[str, Any], event: dict[str, Any] | None = None) -> None:
    path = index_path(root)
    run_id = validate_id(state.get("run_id"), "run_id")

    def mutate(index: Any) -> dict[str, Any]:
        if not isinstance(index, dict):
            index = {}
        runs = index.setdefault("runs", {})
        runs[run_id] = summarize_state(state, event)
        index["schema"] = "agent_orchestration_index"
        index["updated_at"] = utc_now()
        index["latest_run_id"] = run_id
        return index

    update_json_atomic(path, {}, mutate)


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    keep = ["ts", "event", "status", "phase_id", "agent", "summary", "reasoning", "scope", "files", "metadata"]
    return {k: event[k] for k in keep if k in event and event[k] not in (None, "", [], {})}


def emit_event(
    root: str | Path = ".",
    event: str = "note",
    run_id: str | None = None,
    status: str | None = None,
    phase_id: str | None = None,
    agent: str | None = None,
    summary: str | None = None,
    reasoning: str | None = None,
    scope: list[str] | None = None,
    files: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    task: str | None = None,
    update_state: bool = True,
) -> dict[str, Any]:
    rootp = Path(root).resolve()
    resolved = resolve_run_id(rootp, run_id)
    ev: dict[str, Any] = {
        "ts": utc_now(),
        "event": event,
    }
    if resolved:
        ev["run_id"] = resolved
    if status:
        ev["status"] = status
    if phase_id:
        ev["phase_id"] = phase_id
    if agent:
        ev["agent"] = agent
    if summary:
        ev["summary"] = summary
    if reasoning:
        ev["reasoning"] = reasoning
    if scope:
        ev["scope"] = scope
    if files:
        ev["files"] = files
    if metadata:
        ev["metadata"] = metadata

    append_jsonl(global_events_path(rootp), ev)

    if resolved:
        append_jsonl(run_events_path(rootp, resolved), ev)
        if update_state:
            path = state_path(rootp, resolved)
            with file_lock(path):
                state = read_json(path, {})
                if not isinstance(state, dict) or not state:
                    now = utc_now()
                    state = {
                        "run_id": resolved,
                        "task": task or task_slug(resolved),
                        "status": "initialized",
                        "created_at": now,
                        "updated_at": now,
                        "classification": {},
                        "phases": [],
                        "agents": {},
                        "events": [],
                        "files_claimed": {},
                        "verification": [],
                        "budget": {},
                        "risks": [],
                    }
                state["updated_at"] = ev["ts"]
                if status:
                    state["status"] = status
                state["last_event"] = compact_event(ev)
                events = state.setdefault("events", [])
                events.append(compact_event(ev))
                if len(events) > STATE_EVENT_LIMIT:
                    state["events"] = events[-STATE_EVENT_LIMIT:]
                if agent:
                    ag = state.setdefault("agents", {}).setdefault(agent, {"events": [], "status": "unknown"})
                    if status:
                        ag["status"] = status
                    if reasoning:
                        ag["reasoning"] = reasoning
                    if phase_id:
                        ag["phase_id"] = phase_id
                    if scope:
                        ag["scope"] = scope
                    if files:
                        ag.setdefault("files", [])
                        for f in files:
                            if f not in ag["files"]:
                                ag["files"].append(f)
                            claims = state.setdefault("files_claimed", {})
                            current_owner = claims.get(f)
                            if current_owner is None:
                                claims[f] = agent
                            elif current_owner != agent:
                                conflict = {"file": f, "current_owner": current_owner, "new_owner": agent, "event": compact_event(ev)}
                                conflicts = state.setdefault("ownership_conflicts", [])
                                if conflict not in conflicts:
                                    conflicts.append(conflict)
                    ag["last_event"] = compact_event(ev)
                    ag.setdefault("events", []).append(compact_event(ev))
                    if len(ag["events"]) > 50:
                        ag["events"] = ag["events"][-50:]
                if event in {"command_finished", "verification_passed", "verification_failed", "quality_gate_completed"}:
                    state.setdefault("verification", []).append(compact_event(ev))
                _write_json_atomic_unlocked(path, state)
            update_index(rootp, state, ev)
    else:
        # Keep index fresh even for global-only events.
        def mutate(idx: Any) -> dict[str, Any]:
            if not isinstance(idx, dict):
                idx = {"schema": "agent_orchestration_index", "runs": {}}
            idx["updated_at"] = utc_now()
            return idx

        update_json_atomic(index_path(rootp), {}, mutate)
    return ev


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit a compact orchestration event")
    ap.add_argument("--root", default=".")
    ap.add_argument("--run-id", help="Run ID, or 'latest'")
    ap.add_argument("--event", required=True, help="Event name, e.g. worker_dispatched")
    ap.add_argument("--status")
    ap.add_argument("--phase-id")
    ap.add_argument("--agent")
    ap.add_argument("--summary", default="")
    ap.add_argument("--reasoning")
    ap.add_argument("--scope", help="Comma/semicolon separated scope labels")
    ap.add_argument("--files", help="Comma/semicolon separated files/areas")
    ap.add_argument("--meta", action="append", default=[], help="Metadata key=value or flag; may repeat")
    ap.add_argument("--metadata-json", help="JSON object merged into metadata")
    ap.add_argument("--task", help="Task title if creating missing state")
    ap.add_argument("--no-state", action="store_true", help="Only append JSONL event; do not update state/index")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    ev = emit_event(
        root=args.root,
        run_id=args.run_id,
        event=args.event,
        status=args.status,
        phase_id=args.phase_id,
        agent=args.agent,
        summary=args.summary,
        reasoning=args.reasoning,
        scope=csv_items(args.scope),
        files=csv_items(args.files),
        metadata=parse_meta(args.meta, args.metadata_json),
        task=args.task,
        update_state=not args.no_state,
    )
    if args.json:
        print(json.dumps(ev, indent=2, ensure_ascii=False))
    else:
        bits = [ev.get("ts", ""), ev.get("event", "")]
        if ev.get("run_id"):
            bits.append(str(ev["run_id"]))
        if ev.get("agent"):
            bits.append(str(ev["agent"]))
        if ev.get("status"):
            bits.append(str(ev["status"]))
        print(" | ".join(bits))


if __name__ == "__main__":
    main()
