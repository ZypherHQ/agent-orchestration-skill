#!/usr/bin/env python3
"""Import and inspect local Codex rollout JSONL sessions as AOC runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import (  # noqa: E402
    latest_run_id,
    read_json,
    rebuild_index,
    run_dir,
    state_path,
    update_index,
    utc_now,
    validate_id,
    write_json_atomic,
)

try:
    from memory_index import search_index  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - search still works for imported logs.
    search_index = None  # type: ignore

STATE_EVENT_LIMIT = 250
MAX_TEXT = 4000
ROLL_OUT_RE = re.compile(r"^rollout-(?P<stamp>.+)-(?P<id>[A-Za-z0-9-]{12,})\.jsonl$")
CODEX_IMPORT_SOURCE = "codex_session_import"
LEGACY_CODEX_IMPORT_SOURCE = "codex_session"
CODEX_IMPORT_SOURCES = {CODEX_IMPORT_SOURCE, LEGACY_CODEX_IMPORT_SOURCE}


def safe_slug(value: Any, fallback: str = "id", max_len: int = 96) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("._-")
    text = text.replace("..", "-")
    return (text[:max_len].strip("._-") or fallback)


def short_text(value: Any, limit: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def codex_homes(arg: str | None = None) -> list[Path]:
    candidates = [arg, os.environ.get("AOC_CODEX_HOME"), os.environ.get("CODEX_HOME"), "~/.codex"]
    root_fallback = Path("/root/.codex")
    if root_fallback.exists() and os.access(root_fallback, os.R_OK):
        candidates.append(str(root_fallback))
    homes: list[Path] = []
    seen: set[str] = set()
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        key = str(path)
        if key not in seen:
            seen.add(key)
            homes.append(path)
    return homes


def codex_home(arg: str | None = None) -> Path:
    homes = codex_homes(arg)
    return homes[0] if homes else Path("~/.codex").expanduser().resolve()


def current_path(root: Path) -> Path:
    return root / ".orchestration" / "current.json"


def read_current(root: Path) -> dict[str, Any]:
    data = read_json(current_path(root), {})
    return data if isinstance(data, dict) else {}


def set_current(root: Path, run_id: str, source: str = "manual") -> dict[str, Any]:
    run_id = validate_id(run_id, "run_id")
    payload = {
        "schema": "agent_orchestration_current",
        "current_run_id": run_id,
        "updated_at": utc_now(),
        "source": source,
        "repo": str(root),
    }
    write_json_atomic(current_path(root), payload)
    return payload


def resolve_selected_run(root: Path, requested: str | None = None) -> str | None:
    if requested and requested != "current":
        if requested == "latest":
            return latest_run_id(root)
        return validate_id(requested, "run_id")
    current = read_current(root).get("current_run_id")
    if current:
        try:
            current = validate_id(current, "current_run_id")
            if state_path(root, current).exists():
                return current
        except ValueError:
            pass
    return latest_run_id(root)


def iter_session_files(home: Path | Iterable[Path]) -> list[Path]:
    homes = [home] if isinstance(home, Path) else list(home)
    files_by_path: dict[str, Path] = {}
    for one_home in homes:
        base = one_home / "sessions"
        if not base.exists():
            continue
        try:
            found = base.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/rollout-*.jsonl")
            for path in found:
                if path.is_file():
                    files_by_path[str(path.resolve())] = path
        except OSError:
            continue
    files = list(files_by_path.values())
    files.sort(key=lambda p: (p.stat().st_mtime, str(p)))
    return files


def safe_read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        raise SystemExit(f"Codex session file not found: {path}")
    for line_no, line in enumerate(lines, start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            errors += 1
            rows.append({"timestamp": "", "type": "jsonl_parse_error", "payload": {"line": line_no, "raw": raw[:500]}})
            continue
        if isinstance(item, dict):
            item["_line"] = line_no
            rows.append(item)
        else:
            rows.append({"timestamp": "", "type": "jsonl_value", "payload": item, "_line": line_no})
    return rows, errors


def first_meta(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and item.get("type") == "session_meta" and isinstance(item.get("payload"), dict):
                    return item["payload"]
                if isinstance(item, dict):
                    if item.get("session_id") or item.get("cwd") or str(item.get("type", "")).startswith("session"):
                        return {k: v for k, v in item.items() if k != "_line"}
                    payload = item.get("payload")
                    return payload if isinstance(payload, dict) else {}
    except FileNotFoundError:
        return {}
    return {}


def session_id_from_path(path: Path, meta: dict[str, Any] | None = None) -> str:
    if meta and meta.get("id"):
        return safe_slug(meta["id"], fallback="session", max_len=80)
    if meta and meta.get("session_id"):
        return safe_slug(meta["session_id"], fallback="session", max_len=80)
    match = ROLL_OUT_RE.match(path.name)
    if match:
        return safe_slug(match.group("id"), fallback="session", max_len=80)
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
    return f"session-{digest}"


def run_id_for_session(path: Path, meta: dict[str, Any] | None = None) -> str:
    return validate_id(safe_slug(f"codex-{session_id_from_path(path, meta)}", fallback="codex-session", max_len=96), "run_id")


def source_type_from_state(state: dict[str, Any]) -> str:
    source = state.get("source")
    if isinstance(source, dict):
        value = source.get("type") or state.get("source_type")
    else:
        value = state.get("source_type") or source
    return str(value or "")


def is_codex_import_state(state: dict[str, Any]) -> bool:
    return source_type_from_state(state) in CODEX_IMPORT_SOURCES


def codex_import_path(state: dict[str, Any]) -> str:
    source = state.get("source") if isinstance(state.get("source"), dict) else {}
    summary = state.get("codex_session") if isinstance(state.get("codex_session"), dict) else {}
    return str(state.get("codex_session_path") or source.get("path") or summary.get("path") or "")


def codex_import_session_id(state: dict[str, Any]) -> str:
    source = state.get("source") if isinstance(state.get("source"), dict) else {}
    summary = state.get("codex_session") if isinstance(state.get("codex_session"), dict) else {}
    return str(state.get("codex_session_id") or source.get("session_id") or summary.get("session_id") or "")


def same_codex_import_source(state: dict[str, Any], path: Path, session_id: str) -> bool:
    existing_path = codex_import_path(state)
    if existing_path:
        try:
            return Path(existing_path).expanduser().resolve() == path.expanduser().resolve()
        except OSError:
            return existing_path == str(path)
    existing_session_id = codex_import_session_id(state)
    return bool(existing_session_id and existing_session_id == session_id)


def import_run_id_for_session(root: Path, path: Path, meta: dict[str, Any] | None = None) -> str:
    base = run_id_for_session(path, meta)
    session_id = session_id_from_path(path, meta)
    for suffix in range(0, 1000):
        candidate = base if suffix == 0 else validate_id(f"{base}-{suffix + 1}", "run_id")
        existing_path = state_path(root, candidate)
        if not existing_path.exists():
            return candidate
        existing = read_json(existing_path, {})
        if isinstance(existing, dict) and is_codex_import_state(existing) and same_codex_import_source(existing, path, session_id):
            return candidate
    raise SystemExit(f"Unable to allocate non-conflicting Codex import run id for {path}")


def extract_payload_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return " ".join(extract_payload_text(item) for item in payload)
    if not isinstance(payload, dict):
        return short_text(payload)

    item_type = payload.get("type")
    if item_type == "function_call":
        name = payload.get("name") or payload.get("function")
        args = payload.get("arguments")
        return short_text(f"function_call {name or ''} {short_text(args, 1200)}")
    if item_type == "function_call_output":
        return short_text(payload.get("output") or payload.get("content"))
    if item_type == "message":
        return extract_payload_text(payload.get("content"))
    if "text" in payload:
        return short_text(payload.get("text"))
    if "message" in payload:
        return short_text(payload.get("message"))
    if "content" in payload:
        return extract_payload_text(payload.get("content"))
    if "output" in payload:
        return short_text(payload.get("output"))
    if "info" in payload:
        return short_text(payload.get("info"))
    return short_text({k: v for k, v in payload.items() if k not in {"base_instructions", "instructions"}})


def normalize_item(item: dict[str, Any], run_id: str) -> dict[str, Any]:
    if "payload" in item:
        payload = item.get("payload")
    else:
        payload = {k: v for k, v in item.items() if k not in {"timestamp", "_line"}}
    payload_dict = payload if isinstance(payload, dict) else {}
    raw_type = str(item.get("type") or payload_dict.get("type") or item.get("role") or payload_dict.get("role") or "codex_event")
    nested_type = str(payload_dict.get("type") or "")
    event = f"codex_{raw_type}"
    if nested_type and nested_type != raw_type:
        event = f"{event}_{nested_type}"
    event = re.sub(r"[^A-Za-z0-9_]+", "_", event).strip("_") or "codex_event"
    ts = str(item.get("timestamp") or payload_dict.get("timestamp") or "")
    if not ts:
        ts = utc_now()

    if raw_type == "session_meta" or raw_type.startswith("session"):
        summary = short_text(
            " ".join(
                part
                for part in [
                    "session",
                    f"cwd={payload_dict.get('cwd')}" if payload_dict.get("cwd") else "",
                    f"originator={payload_dict.get('originator')}" if payload_dict.get("originator") else "",
                    f"model={payload_dict.get('model')}" if payload_dict.get("model") else "",
                    f"role={payload_dict.get('agent_role')}" if payload_dict.get("agent_role") else "",
                ]
                if part
            )
        )
    elif raw_type == "event_msg" and nested_type == "token_count":
        usage = payload_dict.get("info") if isinstance(payload_dict.get("info"), dict) else {}
        total = usage.get("total_token_usage") if isinstance(usage.get("total_token_usage"), dict) else {}
        summary = short_text(f"token_count total={total.get('total_tokens', '')}")
    else:
        summary = short_text(extract_payload_text(payload), 600)
        if not summary:
            summary = short_text(raw_type)

    return {
        "ts": ts,
        "event": event,
        "run_id": run_id,
        "status": "observed",
        "summary": summary,
        "metadata": {
            "source": CODEX_IMPORT_SOURCE,
            "legacy_source": LEGACY_CODEX_IMPORT_SOURCE,
            "line": item.get("_line"),
            "type": raw_type,
            "payload_type": nested_type,
        },
        "text": short_text(extract_payload_text(payload), MAX_TEXT),
    }


def summarize_session(path: Path, rows: list[dict[str, Any]], errors: int, meta: dict[str, Any], run_id: str) -> dict[str, Any]:
    normalized = [normalize_item(item, run_id) for item in rows]
    first_ts = next((r.get("ts") for r in normalized if r.get("ts")), utc_now())
    last_ts = next((r.get("ts") for r in reversed(normalized) if r.get("ts")), first_ts)
    user_texts = [r["summary"] for r in normalized if "user" in r["event"] and r.get("summary")]
    task = user_texts[0] if user_texts else f"Imported Codex session {session_id_from_path(path, meta)}"
    event_counts: dict[str, int] = {}
    for row in normalized:
        event_counts[row["event"]] = event_counts.get(row["event"], 0) + 1
    return {
        "normalized": normalized,
        "summary": {
            "schema": "aoc_codex_session_import",
            "run_id": run_id,
            "source_type": CODEX_IMPORT_SOURCE,
            "session_id": session_id_from_path(path, meta),
            "path": str(path),
            "cwd": meta.get("cwd"),
            "originator": meta.get("originator"),
            "cli_version": meta.get("cli_version"),
            "thread_source": meta.get("thread_source"),
            "agent_nickname": meta.get("agent_nickname"),
            "agent_role": meta.get("agent_role"),
            "event_count": len(normalized),
            "parse_error_count": errors,
            "event_counts": event_counts,
            "first_ts": first_ts,
            "last_ts": last_ts,
            "task": task,
            "imported_at": utc_now(),
            "source_mtime": path.stat().st_mtime if path.exists() else None,
            "source_size": path.stat().st_size if path.exists() else None,
        },
    }


def imported_run_ids(root: Path) -> set[str]:
    out: set[str] = set()
    for sp in (root / ".orchestration" / "runs").glob("*/state.json"):
        state = read_json(sp, {})
        if isinstance(state, dict) and is_codex_import_state(state):
            rid = state.get("run_id") or sp.parent.name
            try:
                out.add(validate_id(rid, "run_id"))
            except ValueError:
                continue
    return out


def discover_rows(root: Path, home: Path | Iterable[Path]) -> list[dict[str, Any]]:
    imported = imported_run_ids(root)
    rows: list[dict[str, Any]] = []
    for path in iter_session_files(home):
        meta = first_meta(path)
        run_id = import_run_id_for_session(root, path, meta)
        stat = path.stat()
        rows.append(
            {
                "run_id": run_id,
                "session_id": session_id_from_path(path, meta),
                "source": CODEX_IMPORT_SOURCE if run_id in imported else "codex_discovered",
                "source_type": CODEX_IMPORT_SOURCE if run_id in imported else "codex_session_discovered",
                "status": "imported" if run_id in imported else "discovered",
                "task": f"Codex session {session_id_from_path(path, meta)}",
                "cwd": meta.get("cwd"),
                "path": str(path),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
                "size": stat.st_size,
            }
        )
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows


def aoc_rows(root: Path) -> list[dict[str, Any]]:
    index = read_json(root / ".orchestration" / "index.json", {})
    if not isinstance(index, dict) or not isinstance(index.get("runs"), dict):
        index = rebuild_index(root)
    rows = list((index.get("runs") or {}).values())
    for row in rows:
        rid = row.get("run_id")
        if rid:
            state = read_json(state_path(root, str(rid)), {})
            if isinstance(state, dict) and is_codex_import_state(state):
                row["source"] = source_type_from_state(state)
                row["source_type"] = source_type_from_state(state)
                row["session_id"] = codex_import_session_id(state)
                row["path"] = codex_import_path(state)
        row.setdefault("source", "aoc")
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return rows


def format_table(rows: list[dict[str, Any]], limit: int) -> None:
    rows = rows[:limit]
    if not rows:
        print("No sessions found.")
        return
    widths = [34, 16, 12, 20, 58]
    headers = ["RUN ID", "SOURCE", "STATUS", "UPDATED", "TASK/PATH"]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        detail = row.get("task") or row.get("path") or ""
        values = [
            short_text(row.get("run_id"), widths[0]),
            short_text(row.get("source"), widths[1]),
            short_text(row.get("status"), widths[2]),
            short_text(row.get("updated_at"), widths[3]),
            short_text(detail, widths[4]),
        ]
        print("  ".join(v.ljust(w) for v, w in zip(values, widths)))


def import_one(root: Path, path: Path, *, make_current: bool = True) -> dict[str, Any]:
    path = path.expanduser().resolve()
    meta = first_meta(path)
    run_id = import_run_id_for_session(root, path, meta)
    rows, errors = safe_read_jsonl(path)
    bundle = summarize_session(path, rows, errors, meta, run_id)
    normalized = bundle["normalized"]
    summary = bundle["summary"]
    rd = run_dir(root, run_id)
    for sub in ["dispatches", "handoffs", "evidence", "logs", "context", "controls", "memory"]:
        (rd / sub).mkdir(parents=True, exist_ok=True)

    events_path = rd / "events.jsonl"
    events_text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in normalized)
    events_path.write_text(events_text, encoding="utf-8")
    (rd / "logs" / "codex_session.jsonl").write_text(events_text, encoding="utf-8")
    write_json_atomic(rd / "codex_session.json", summary)
    (rd / "evidence" / "codex_session_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    excerpt = "\n".join(f"- {row.get('ts')} {row.get('event')}: {row.get('summary')}" for row in normalized[-40:])
    (rd / "evidence" / "codex_session_excerpt.md").write_text(excerpt + ("\n" if excerpt else ""), encoding="utf-8")

    old_state = read_json(rd / "state.json", {})
    if not isinstance(old_state, dict):
        old_state = {}
    state = {
        **old_state,
        "run_id": run_id,
        "task": old_state.get("task") or summary["task"],
        "mode": old_state.get("mode") or "codex_session",
        "status": "imported",
        "created_at": old_state.get("created_at") or summary["first_ts"],
        "updated_at": summary["last_ts"],
        "source_type": CODEX_IMPORT_SOURCE,
        "codex_session_path": str(path),
        "codex_session_id": summary["session_id"],
        "imported_at": summary["imported_at"],
        "classification": old_state.get("classification") or {},
        "phases": old_state.get("phases") or [],
        "agents": old_state.get("agents") or {},
        "events": normalized[-STATE_EVENT_LIMIT:],
        "files_claimed": old_state.get("files_claimed") or {},
        "verification": old_state.get("verification") or [],
        "budget": old_state.get("budget") or {},
        "risks": old_state.get("risks") or [],
        "source": {"type": CODEX_IMPORT_SOURCE, "legacy_type": LEGACY_CODEX_IMPORT_SOURCE, "path": str(path), "session_id": summary["session_id"]},
        "codex_session": summary,
        "last_event": normalized[-1] if normalized else {},
    }
    write_json_atomic(rd / "state.json", state)
    update_index(root, state, normalized[-1] if normalized else None)
    if make_current:
        set_current(root, run_id, source=CODEX_IMPORT_SOURCE)
    return {"run_id": run_id, "path": str(path), "event_count": len(normalized), "parse_error_count": errors, "state": str(rd / "state.json")}


def resolve_session_target(root: Path, home: Path | Iterable[Path], target: str | None, run_id: str | None = None) -> list[Path]:
    files = iter_session_files(home)
    if not files:
        homes = [home] if isinstance(home, Path) else list(home)
        searched = ", ".join(str(p / "sessions") for p in homes)
        raise SystemExit(f"No Codex rollout sessions found under {searched}")
    if run_id:
        target = run_id
    if not target or target in {"latest", "current"}:
        if target == "current":
            selected = resolve_selected_run(root, "current")
            if selected:
                for path in files:
                    meta = first_meta(path)
                    if import_run_id_for_session(root, path, meta) == selected:
                        return [path]
        return [files[-1]]
    if target == "all":
        return files
    candidate = Path(target).expanduser()
    if candidate.exists():
        return [candidate.resolve()]
    wanted = safe_slug(target, fallback="target")
    matches = []
    for path in files:
        meta = first_meta(path)
        if wanted in {import_run_id_for_session(root, path, meta), run_id_for_session(path, meta), session_id_from_path(path, meta), path.name}:
            matches.append(path)
    if matches:
        return matches
    raise SystemExit(f"No Codex session matched {target!r}")


def print_json_or_table(data: Any, as_json: bool, limit: int = 20) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        format_table(data if isinstance(data, list) else [data], limit)


def cmd_sessions(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    rows = aoc_rows(root)
    if not args.aoc_only:
        seen = {r.get("run_id") for r in rows}
        for row in discover_rows(root, codex_homes(args.codex_home)):
            if row.get("run_id") not in seen:
                rows.append(row)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    if args.json:
        print(json.dumps(rows[: args.limit], indent=2, ensure_ascii=False))
    else:
        format_table(rows, args.limit)


def cmd_current(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    rid = resolve_selected_run(root, args.run_id or "current")
    payload = {"run_id": rid, "current_run_id": rid, "state": str(state_path(root, rid)) if rid else "", "metadata": read_current(root)}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(rid or "No current session selected.")


def cmd_use(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    target = args.target or args.run_id
    if not target:
        raise SystemExit("Usage: aoc use <run_id|latest|codex_session_id|path>")
    if target == "latest":
        rid = latest_run_id(root)
        if not rid:
            paths = resolve_session_target(root, codex_homes(args.codex_home), "latest")
            imported = import_one(root, paths[0], make_current=True)
            rid = imported["run_id"]
    elif state_path(root, target).exists():
        rid = validate_id(target, "run_id")
        set_current(root, rid, source="manual")
    else:
        paths = resolve_session_target(root, codex_homes(args.codex_home), target)
        imported = import_one(root, paths[-1], make_current=True)
        rid = imported["run_id"]
    payload = set_current(root, rid, source="manual")
    payload["run_id"] = rid
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(rid)


def cmd_import(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    paths = resolve_session_target(root, codex_homes(args.codex_home), args.target, args.run_id)
    if args.limit and len(paths) > args.limit:
        paths = paths[-args.limit :]
    results = [import_one(root, path, make_current=not args.no_current) for path in paths]
    for result in results:
        result["imported"] = 1
    if args.json:
        payload: Any = results if len(results) != 1 else results[0]
        if isinstance(payload, list):
            payload = {"imported": len(results), "sessions": results}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for result in results:
            if not args.quiet:
                print(f"imported {result['event_count']} event(s) into {result['run_id']} from {result['path']}")


def cmd_normalize(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    paths = resolve_session_target(root, codex_homes(args.codex_home), args.target, args.run_id)
    payloads = []
    for path in paths:
        meta = first_meta(path)
        run_id = import_run_id_for_session(root, path, meta)
        rows, errors = safe_read_jsonl(path)
        bundle = summarize_session(path, rows, errors, meta, run_id)
        events = bundle["normalized"]
        if args.limit_events is not None:
            events = events[-max(0, args.limit_events) :]
        payloads.append({"summary": bundle["summary"], "events": events})
    result: Any = payloads[0] if len(payloads) == 1 else payloads
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for payload in payloads:
            summary = payload["summary"]
            print(f"{summary['run_id']} {summary['event_count']} event(s) {summary['path']}")


def cmd_watch(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    homes = codex_homes(args.codex_home)
    last: dict[str, tuple[float, int]] = {}
    try:
        while True:
            paths = resolve_session_target(root, homes, args.target, args.run_id) if (args.target or args.run_id) else iter_session_files(homes)
            if args.latest and paths:
                paths = [paths[-1]]
            if args.limit and len(paths) > args.limit:
                paths = paths[-args.limit :]
            changed = []
            for path in paths:
                stat = path.stat()
                marker = (stat.st_mtime, stat.st_size)
                key = str(path)
                if last.get(key) == marker and not args.once:
                    continue
                last[key] = marker
                changed.append(import_one(root, path, make_current=not args.no_current))
            if args.json and changed:
                print(json.dumps(changed, ensure_ascii=False), flush=True)
            elif changed and not args.quiet:
                for result in changed:
                    print(f"updated {result['run_id']} ({result['event_count']} event(s))", flush=True)
            if args.once:
                return
            time.sleep(max(0.25, args.interval))
    except KeyboardInterrupt:
        return


def search_imported_logs(root: Path, query: str, limit: int, run_id: str | None = None) -> list[dict[str, Any]]:
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_./-]{2,}", query)]
    rows: list[dict[str, Any]] = []
    run_dirs: Iterable[Path]
    if run_id:
        run_dirs = [run_dir(root, run_id)]
    else:
        run_dirs = (root / ".orchestration" / "runs").glob("*")
    for rd in run_dirs:
        state = read_json(rd / "state.json", {})
        if isinstance(state, dict) and is_codex_import_state(state):
            summary = state.get("codex_session") if isinstance(state.get("codex_session"), dict) else {}
            last_event = state.get("last_event") if isinstance(state.get("last_event"), dict) else {}
            blob = " ".join(
                str(value or "")
                for value in [
                    state.get("run_id") or rd.name,
                    state.get("task"),
                    state.get("source_type"),
                    state.get("codex_session_id"),
                    state.get("codex_session_path"),
                    summary.get("task"),
                    summary.get("path"),
                    last_event.get("event"),
                    last_event.get("summary"),
                ]
            ).lower()
            score = sum(1 for term in terms if term in blob)
            if score or not terms:
                rows.append(
                    {
                        "score": score,
                        "kind": "codex_session_state",
                        "run_id": state.get("run_id") or rd.name,
                        "path": str((rd / "state.json").relative_to(root)) if (rd / "state.json").is_relative_to(root) else str(rd / "state.json"),
                        "updated_at": state.get("updated_at", ""),
                        "excerpt": short_text(state.get("task") or summary.get("task") or last_event.get("summary"), 240),
                    }
                )
        path = rd / "logs" / "codex_session.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            blob = " ".join(str(row.get(k, "")) for k in ["event", "summary", "text"]).lower()
            score = sum(1 for term in terms if term in blob)
            if score or not terms:
                rows.append(
                    {
                        "score": score,
                        "kind": "codex_session",
                        "run_id": row.get("run_id") or rd.name,
                        "path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                        "updated_at": row.get("ts", ""),
                        "excerpt": short_text(row.get("summary") or row.get("text"), 240),
                    }
                )
    rows.sort(key=lambda r: (-int(r.get("score") or 0), str(r.get("updated_at") or "")), reverse=False)
    return rows[:limit]


def cmd_search(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    rid = resolve_selected_run(root, args.run_id) if args.run_id else None
    memory_rows: list[dict[str, Any]] = []
    if search_index is not None:
        try:
            memory_rows = search_index(root, args.query, args.limit)
        except Exception:
            memory_rows = []
    codex_rows = search_imported_logs(root, args.query, args.limit, rid)
    rows = (memory_rows + codex_rows)[: args.limit]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        if not rows:
            print("No search hits.")
            return
        for row in rows:
            print(f"{int(row.get('score') or 0):>2} | {short_text(row.get('kind'), 14):14} | {row.get('run_id', '')} | {row.get('path')} | {row.get('excerpt')}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Codex rollout session support for Agentic Orchestration Control")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sessions")
    p.add_argument("--root", default=".")
    p.add_argument("--codex-home")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--aoc-only", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sessions)

    p = sub.add_parser("current")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_current)

    p = sub.add_parser("use")
    p.add_argument("target", nargs="?")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id")
    p.add_argument("--codex-home")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_use)

    p = sub.add_parser("import")
    p.add_argument("target", nargs="?", help="Path, run_id/session_id, latest, current, or all")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id")
    p.add_argument("--codex-home")
    p.add_argument("--limit", type=int)
    p.add_argument("--no-current", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("normalize")
    p.add_argument("target", nargs="?", help="Path, run_id/session_id, latest, current, or all")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id")
    p.add_argument("--codex-home")
    p.add_argument("--limit-events", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_normalize)

    p = sub.add_parser("watch")
    p.add_argument("target", nargs="?")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id")
    p.add_argument("--codex-home")
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--latest", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--once", action="store_true")
    p.add_argument("--no-current", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
