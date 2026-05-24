#!/usr/bin/env python3
"""Terminal control room for Agent Orchestration runs.

The TUI is filesystem-first: it reads .orchestration state, JSONL events,
controls, evidence, and memory artifacts. It does not need to introspect Codex
internals to be useful.
"""
from __future__ import annotations

import argparse
import curses
import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import latest_run_id, read_json, rebuild_index, run_dir, state_path, summarize_state  # noqa: E402
from orchestration_stats import run_stats  # noqa: E402
from usage_ledger import aggregate as usage_aggregate, derive_from_run, load_records  # noqa: E402
from codex_appserver_bridge import snapshot as codex_snapshot  # noqa: E402
from codex_session_cli import import_run_id_for_session, run_id_for_session  # noqa: E402

TABS = ["Sessions", "Overview", "DAG", "Workers", "Events", "Verification", "Memory", "Usage", "Codex", "Gates", "Stats"]
CODEX_DISCOVERY_LIMIT = 80
_CODEX_DISCOVERY_CACHE: tuple[float, str, list[dict[str, Any]]] = (0.0, "", [])


def codex_homes() -> list[Path]:
    homes: list[Path] = []
    candidates = [os.environ.get("AOC_CODEX_HOME"), os.environ.get("CODEX_HOME"), str(Path.home() / ".codex")]
    root_fallback = Path("/root/.codex")
    if root_fallback.exists() and os.access(root_fallback, os.R_OK):
        candidates.append(str(root_fallback))
    for raw in candidates:
        if not raw:
            continue
        p = Path(raw).expanduser().resolve()
        if p not in homes:
            homes.append(p)
    return homes


def short(text: Any, width: int) -> str:
    s = " ".join(str(text or "").split())
    if width <= 0:
        return ""
    if len(s) <= width:
        return s
    if width <= 3:
        return s[:width]
    return s[: max(1, width - 3)] + "..."


def source_badge(row: dict[str, Any] | None) -> str:
    row = row or {}
    raw_source = row.get("source_type") or row.get("source") or ""
    if isinstance(raw_source, dict):
        raw_source = raw_source.get("type") or ""
    source = str(raw_source).lower()
    run_id = str(row.get("run_id") or "")
    if run_id.startswith("codex:") or "codex_session" in source or source in {"codex", "codex_cli"}:
        return "CODEX"
    if "app_server" in source or "appserver" in source or "codex_appserver" in source:
        return "APP_SERVER"
    return "AOC"


def session_path(row: dict[str, Any] | None) -> str:
    row = row or {}
    return str(row.get("codex_session_path") or row.get("session_path") or row.get("path") or "")


def enrich_summary(summary: dict[str, Any], state: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    out = dict(summary)
    for key in ["source", "source_type", "codex_session_path", "codex_session_id", "imported_at", "last_summary"]:
        if state.get(key) is not None and out.get(key) in (None, ""):
            out[key] = state.get(key)
    out["source_badge"] = source_badge(out)
    if path and not out.get("state_path"):
        out["state_path"] = str(path)
    return out


def extract_codex_text(item: dict[str, Any]) -> str:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    for key in ["message", "text", "summary", "status"]:
        if payload.get(key):
            return str(payload.get(key))
    content = payload.get("content")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("input_text") or part.get("output_text") or ""))
        text = " ".join(p for p in parts if p)
        if text:
            return text
    return ""


def codex_run_id(session_id: str | None, path: Path, root: Path | None = None, meta: dict[str, Any] | None = None) -> str:
    if root is not None:
        return import_run_id_for_session(root, path, meta or {})
    return run_id_for_session(path, meta or {"id": session_id or path.stem})


def discover_codex_sessions(limit: int = CODEX_DISCOVERY_LIMIT, root: Path | None = None) -> list[dict[str, Any]]:
    global _CODEX_DISCOVERY_CACHE
    now_ts = time.time()
    cache_key = str(root.resolve()) if root else ""
    if limit == CODEX_DISCOVERY_LIMIT and cache_key == _CODEX_DISCOVERY_CACHE[1] and now_ts - _CODEX_DISCOVERY_CACHE[0] < 2.0:
        return [dict(row) for row in _CODEX_DISCOVERY_CACHE[2]]
    files: list[Path] = []
    for home in codex_homes():
        sessions_dir = home / "sessions"
        if sessions_dir.exists():
            files.extend(p for p in sessions_dir.glob("**/*.jsonl") if p.is_file())
    files = sorted(set(files), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:limit]
    rows: list[dict[str, Any]] = []
    for path in files:
        try:
            rows.append(summarize_codex_session(path, root=root))
        except Exception:
            continue
    if limit == CODEX_DISCOVERY_LIMIT:
        _CODEX_DISCOVERY_CACHE = (now_ts, cache_key, [dict(row) for row in rows])
    return rows


def summarize_codex_session(path: Path, root: Path | None = None) -> dict[str, Any]:
    session_id = ""
    created_at = ""
    updated_at = ""
    task = ""
    last_event: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    meta: dict[str, Any] = {}
    event_count = 0
    try:
        stat = path.stat()
        updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))
    except OSError:
        pass
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if not isinstance(item, dict):
                continue
            event_count += 1
            typ = str(item.get("type") or "codex_event")
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            ts = str(item.get("timestamp") or payload.get("timestamp") or "")
            if ts:
                updated_at = ts
                if not created_at:
                    created_at = ts
            if typ == "session_meta":
                meta = payload
                session_id = str(payload.get("id") or session_id)
                created_at = str(payload.get("timestamp") or created_at)
            if not task and typ in {"response_item", "event_msg"}:
                role = payload.get("role")
                text = extract_codex_text(item)
                if role == "user" and text:
                    task = text
            if not task and typ == "event_msg":
                text = extract_codex_text(item)
                if text and "token_count" not in text:
                    task = text
            if typ == "event_msg" and isinstance(payload.get("info"), dict):
                info = payload.get("info") or {}
                if isinstance(info.get("total_token_usage"), dict):
                    usage = info.get("total_token_usage") or {}
            last_event = {"ts": ts or updated_at, "event": typ, "summary": short(extract_codex_text(item) or typ, 160)}
    session_id = session_id or path.stem
    source = meta.get("source")
    role = meta.get("agent_role") or ""
    nickname = meta.get("agent_nickname") or ""
    if not task:
        task = f"Codex session {nickname or session_id}"
    return {
        "run_id": codex_run_id(session_id, path, root=root, meta=meta),
        "task": short(task, 160),
        "status": "discovered",
        "mode": role,
        "created_at": created_at,
        "updated_at": updated_at,
        "worker_count": 0,
        "test_event_count": 0,
        "event_count": event_count,
        "last_event": last_event.get("event", ""),
        "last_summary": last_event.get("summary", ""),
        "source": source if isinstance(source, str) else "codex_cli",
        "source_type": "codex_session_discovered",
        "source_badge": "CODEX",
        "codex_session_path": str(path),
        "codex_session_id": session_id,
        "last_event_object": last_event,
        "usage": usage,
    }


def find_discovered_session(run_id: str, root: Path | None = None) -> dict[str, Any]:
    for row in discover_codex_sessions(root=root):
        if row.get("run_id") == run_id:
            return row
    return {}


def is_discovered_codex_state(state: dict[str, Any]) -> bool:
    return str(state.get("source_type") or state.get("source") or "") == "codex_session_discovered"


def codex_state_from_summary(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "run_id": row.get("run_id"),
        "task": row.get("task"),
        "status": row.get("status", "discovered"),
        "mode": row.get("mode", ""),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
        "source": row.get("source", "codex_cli"),
        "source_type": row.get("source_type", "codex_session_discovered"),
        "codex_session_path": row.get("codex_session_path", ""),
        "codex_session_id": row.get("codex_session_id", ""),
        "last_event": row.get("last_event_object") or {"event": row.get("last_event", ""), "summary": row.get("last_summary", "")},
        "usage": row.get("usage") or {},
        "agents": {},
        "verification": [],
    }


def load_sessions(root: Path) -> list[dict[str, Any]]:
    idx = read_json(root / ".orchestration" / "index.json", {})
    rows_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(idx, dict):
        for raw in (idx.get("runs") or {}).values():
            if isinstance(raw, dict) and raw.get("run_id"):
                rows_by_id[str(raw.get("run_id"))] = enrich_summary(raw, raw)
    for sp in sorted((root / ".orchestration" / "runs").glob("*/state.json")):
        state = read_json(sp, {})
        if isinstance(state, dict):
            rid = str(state.get("run_id") or sp.parent.name)
            rows_by_id[rid] = enrich_summary(summarize_state(state), state, sp)
    imported_paths = {session_path(r) for r in rows_by_id.values() if session_path(r)}
    for row in discover_codex_sessions(root=root):
        if session_path(row) in imported_paths:
            continue
        rows_by_id[str(row.get("run_id"))] = row
    rows = list(rows_by_id.values())
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return rows


def load_state(root: Path, run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return {}
    state = read_json(state_path(root, run_id), {})
    if isinstance(state, dict) and state:
        return state
    return codex_state_from_summary(find_discovered_session(str(run_id), root=root))


def load_events(root: Path, run_id: str | None, limit: int = 80) -> list[dict[str, Any]]:
    if not run_id:
        return []
    if not state_path(root, run_id).exists():
        row = find_discovered_session(str(run_id), root=root)
        path = Path(str(row.get("codex_session_path") or ""))
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if not isinstance(item, dict):
                continue
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            events.append({
                "ts": item.get("timestamp") or payload.get("timestamp") or "",
                "event": item.get("type") or "codex_event",
                "agent": payload.get("agent_nickname") or payload.get("agent_role") or "",
                "status": payload.get("status") or "",
                "summary": extract_codex_text(item) or item.get("type") or "codex_event",
            })
        return events
    p = run_dir(root, run_id) / "events.jsonl"
    if not p.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                events.append(obj)
        except Exception:
            continue
    return events


def load_plan(root: Path, run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return {}
    if not state_path(root, run_id).exists():
        return {}
    rd = run_dir(root, run_id)
    for p in [rd / "plan.json", root / ".orchestration" / "plan.json"]:
        if p.exists():
            return read_json(p, {})
    return {}


def load_controls(root: Path, run_id: str | None) -> list[dict[str, Any]]:
    if not run_id:
        return []
    if not state_path(root, run_id).exists():
        return []
    controls = []
    for p in sorted((run_dir(root, run_id) / "controls").glob("*.json")):
        data = read_json(p, {})
        if isinstance(data, dict):
            controls.append(data)
    return controls


def load_memory(root: Path, run_id: str | None) -> list[str]:
    lines: list[str] = []
    state = load_state(root, run_id) if run_id else {}
    if state and is_discovered_codex_state(state):
        return [
            "Discovered Codex session",
            f"  source: {state.get('source_type')}",
            f"  path: {state.get('codex_session_path')}",
            "Import with:",
            "  aoc import",
            "or initialize an AOC run first:",
            '  aoc init "Fix checkout flow"',
        ]
    candidates = []
    if run_id:
        rd = run_dir(root, run_id)
        candidates.extend([rd / "context_capsule.json"])
    candidates.extend([root / ".orchestration" / "context_capsule.json", root / ".orchestration" / "memory" / "index.json"])
    for p in candidates:
        if not p.exists():
            continue
        data = read_json(p, {})
        lines.append(f"{p.relative_to(root) if p.is_relative_to(root) else p}")
        if isinstance(data, dict) and data.get("schema") == "context_capsule":
            for key in ["must_read", "forbidden", "confirmed_facts", "rejected_assumptions", "decisions", "acceptance_criteria", "validation_commands"]:
                vals = data.get(key) or []
                if vals:
                    lines.append(f"  {key}:")
                    for v in vals[:6]:
                        if isinstance(v, dict):
                            val = v.get("path") or v.get("value") or v
                        else:
                            val = v
                        lines.append(f"    - {short(val, 90)}")
        elif isinstance(data, dict) and data.get("docs"):
            lines.append(f"  indexed docs: {data.get('doc_count', len(data.get('docs', [])))}")
            for d in data.get("docs", [])[:10]:
                lines.append(f"    - {d.get('kind')}: {short(d.get('path'), 60)}")
    if not lines:
        lines.append("No context capsule or memory index found yet.")
    return lines


def progress_for_agent(agent: dict[str, Any]) -> int:
    events = [e.get("event", "") for e in agent.get("events", [])]
    checks = [
        ("worker_dispatched", 10),
        ("worker_started", 20),
        ("context_coverage_passed", 35),
        ("inspection_complete", 50),
        ("patch_applied", 65),
        ("command_started", 75),
        ("command_finished", 85),
        ("handoff_received", 95),
        ("handoff_validated", 100),
    ]
    val = 0
    for name, score in checks:
        if name in events:
            val = max(val, score)
    status = str(agent.get("status", "")).lower()
    if status in {"passed", "completed", "success", "ok"}:
        return 100
    if status in {"failed", "blocked", "rejected"}:
        return max(val, 40)
    return val


def lines_sessions(root: Path, sessions: list[dict[str, Any]], selected: int) -> list[str]:
    out = ["Orchestrator sessions", ""]
    if not sessions:
        return out + empty_state_lines()
    for i, r in enumerate(sessions):
        marker = ">" if i == selected else " "
        badge = source_badge(r)
        path = session_path(r)
        last = r.get("last_event") or ""
        out.append(f"{marker} [{badge:10}] {short(r.get('run_id'), 32):32} {short(r.get('status'), 11):11} W:{r.get('worker_count',0):<2} T:{r.get('test_event_count',0):<2} {short(r.get('task'), 50)}")
        if path or last:
            out.append(f"    last={short(last, 24)} path={short(path, 82)}")
    return out


def empty_state_lines() -> list[str]:
    homes = ", ".join(str(p) for p in codex_homes())
    return [
        "No AOC runs or Codex sessions were found.",
        "",
        "Next steps:",
        "  aoc import",
        '  aoc init "Fix checkout flow"',
        "  aoc sessions",
        "",
        "Codex home troubleshooting:",
        f"  checked: {homes}",
        "  set AOC_CODEX_HOME or CODEX_HOME if your Codex data lives elsewhere.",
    ]


def lines_overview(root: Path, run_id: str | None) -> list[str]:
    state = load_state(root, run_id)
    if not state:
        return ["No selected session."] + [""] + empty_state_lines()
    out = [f"Run: {state.get('run_id')}", f"Task: {state.get('task', '')}", ""]
    out.append(f"Source: {source_badge(state)} ({state.get('source_type') or state.get('source') or 'aoc'})")
    if state.get("codex_session_id"):
        out.append(f"Codex session: {state.get('codex_session_id')}")
    if state.get("codex_session_path"):
        out.append(f"Session path: {state.get('codex_session_path')}")
    if state.get("imported_at"):
        out.append(f"Imported: {state.get('imported_at')}")
    out.append(f"Status: {state.get('status', 'unknown')}")
    out.append(f"Created: {state.get('created_at', '')}")
    out.append(f"Updated: {state.get('updated_at', '')}")
    cls = state.get("classification") or {}
    if cls:
        out.append("")
        out.append("Classification:")
        for k, v in cls.items():
            out.append(f"  - {k}: {v}")
    budget = state.get("budget") or {}
    if budget:
        out.append("")
        out.append("Budget:")
        for k, v in budget.items():
            out.append(f"  - {k}: {v}")
    last = state.get("last_event") or {}
    if last:
        out.append("")
        out.append("Last event:")
        out.append(f"  {last.get('ts', '')} {last.get('event', '')} {last.get('summary', '')}")
    return out


def lines_dag(root: Path, run_id: str | None) -> list[str]:
    plan = load_plan(root, run_id)
    if not plan:
        return ["No DAG plan found for this session."]
    out = [f"DAG: {plan.get('task', '')}", ""]
    phases = plan.get("phases") or []
    for p in phases:
        deps = ",".join(p.get("depends_on") or []) or "root"
        out.append(f"{p.get('id')} [{p.get('kind')}] {p.get('agent')} ({p.get('reasoning')})")
        out.append(f"  depends_on: {deps}")
        out.append(f"  {short(p.get('objective'), 110)}")
        out.append("")
    return out


def lines_workers(root: Path, run_id: str | None) -> list[str]:
    state = load_state(root, run_id)
    agents = state.get("agents") if isinstance(state.get("agents"), dict) else {}
    if not agents:
        return ["No worker activity recorded yet."]
    out = ["Worker lanes", ""]
    for name, a in sorted(agents.items()):
        progress = progress_for_agent(a)
        out.append(f"{name} | {a.get('status','unknown')} | {a.get('reasoning','')} | {progress}%")
        if a.get("scope"):
            out.append(f"  scope: {', '.join(a.get('scope') or [])}")
        if a.get("files"):
            out.append(f"  files: {', '.join(a.get('files')[:6])}")
        le = a.get("last_event") or {}
        if le:
            out.append(f"  last: {le.get('event')} {short(le.get('summary'), 90)}")
        out.append("")
    return out


def lines_events(root: Path, run_id: str | None) -> list[str]:
    events = load_events(root, run_id, 100)
    if not events:
        return ["No events recorded yet."]
    out = ["Event timeline", ""]
    for ev in events[-60:]:
        out.append(f"{short(ev.get('ts'), 20):20} {short(ev.get('event'), 26):26} {short(ev.get('agent'), 24):24} {short(ev.get('status'), 10):10} {short(ev.get('summary'), 90)}")
    return out


def lines_verification(root: Path, run_id: str | None) -> list[str]:
    state = load_state(root, run_id)
    events = load_events(root, run_id, 120)
    verification = state.get("verification") if isinstance(state.get("verification"), list) else []
    test_events = [
        e for e in events
        if str(e.get("event", "")).startswith(("verification_", "quality_gate", "test_"))
        or "test" in str(e.get("event", "")).lower()
    ]
    out = ["Verification", ""]
    if verification:
        out.append("State verification records:")
        for item in verification[-20:]:
            if isinstance(item, dict):
                cmd = item.get("command") or item.get("name") or item.get("check") or "check"
                result = item.get("result") or item.get("status") or "unknown"
                out.append(f"  {short(cmd, 56):56} {short(result, 12):12} {short(item.get('evidence') or item.get('summary'), 70)}")
            else:
                out.append(f"  - {short(item, 120)}")
        out.append("")
    if test_events:
        out.append("Recent verification events:")
        for ev in test_events[-30:]:
            out.append(f"  {short(ev.get('ts'), 20):20} {short(ev.get('event'), 28):28} {short(ev.get('status'), 12):12} {short(ev.get('summary'), 80)}")
    if not verification and not test_events:
        out.append("No verification records or test events found yet.")
    return out


def lines_codex(root: Path, run_id: str | None) -> list[str]:
    if not run_id:
        return ["No selected session."]
    state = load_state(root, run_id)
    if state and is_discovered_codex_state(state):
        return [
            "Discovered Codex session",
            "",
            f"session_id: {state.get('codex_session_id') or 'unknown'}",
            f"source: {state.get('source_type') or state.get('source')}",
            f"path: {state.get('codex_session_path')}",
            "",
            "Import with:",
            "  aoc import",
            "Bridge is optional. Use GUI with:",
            "  aoc gui --with-codex --codex-url http://127.0.0.1:<port>",
            "Keep app-server/codexui localhost-only unless auth is configured.",
        ]
    try:
        data = codex_snapshot(root, run_id)
    except Exception as exc:
        return [f"Codex bridge error: {exc}"]
    status = data.get("status") or {}
    link = data.get("link") or {}
    out = ["Codex app-server / codexui bridge", ""]
    out.append(f"codex binary: {status.get('codex_bin') or 'not found'}")
    out.append(f"node: {status.get('node_bin') or 'not found'}")
    out.append(f"npx: {status.get('npx_bin') or 'not found'}")
    if link:
        out.append("")
        out.append("Linked thread:")
        out.append(f"  thread_id: {link.get('thread_id') or 'unknown'}")
        out.append(f"  url: {link.get('url') or 'not set'}")
    out.append("")
    out.append("Bridge is optional. Use GUI with:")
    out.append("  aoc gui --with-codex --codex-url http://127.0.0.1:<port>")
    out.append("Keep app-server/codexui localhost-only unless auth is configured.")
    return out

def lines_gates(root: Path, run_id: str | None) -> list[str]:
    gates = load_controls(root, run_id)
    if not gates:
        return ["No STOP gates recorded."]
    out = ["STOP gates", ""]
    for g in gates:
        out.append(f"{g.get('gate_id')} | {g.get('status')} | {g.get('kind')}")
        out.append(f"  reason: {short(g.get('reason'), 100)}")
        opts = g.get("options") or []
        if opts:
            out.append("  options: " + "; ".join(opts))
        out.append("")
    return out


def lines_usage(root: Path, run_id: str | None) -> list[str]:
    if not run_id:
        return ["No selected session."]
    out = ["Usage control", ""]
    state = load_state(root, run_id)
    if state and is_discovered_codex_state(state):
        usage = state.get("usage") if isinstance(state.get("usage"), dict) else {}
        if usage:
            out.append(f"real/imported tokens: {usage.get('total_tokens', 0)}")
            out.append(f"input tokens: {usage.get('input_tokens', 0)}")
            out.append(f"output tokens: {usage.get('output_tokens', 0)}")
        else:
            out.append("No token usage event found in this Codex session.")
        out.append("")
        out.append("Import with:")
        out.append("  aoc import")
        return out
    try:
        records = load_records(root, run_id)
        records_with_estimate = records + [derive_from_run(root, run_id)]
        summary = usage_aggregate(records_with_estimate, "source")
    except Exception as exc:
        return [f"Could not compute usage: {exc}"]
    totals = summary.get("totals", {})
    out.append(f"real tokens: {totals.get('total_tokens', 0)}")
    out.append(f"estimated pressure: ~{totals.get('estimated_tokens', 0)} tokens")
    out.append(f"cost: ${float(totals.get('cost_usd', 0.0)):.4f}")
    out.append(f"records: {totals.get('records', 0)}")
    out.append("")
    out.append("By source:")
    for row in summary.get("rows", []):
        out.append(
            f"  {short(row.get('key'), 24):24} real={row.get('total_tokens', 0):>8} "
            f"est={row.get('estimated_tokens', 0):>8} cost=${float(row.get('cost_usd', 0.0)):.4f}"
        )
    out.append("")
    out.append("Commands:")
    out.append("  aoc usage")
    out.append("  aoc budget 12000")
    out.append("")
    out.append("Note: estimated pressure is not provider billing; imported ccusage records are shown as real tokens when available.")
    return out


def lines_stats(root: Path, run_id: str | None) -> list[str]:
    if not run_id:
        return ["No selected session."]
    state = load_state(root, run_id)
    if state and is_discovered_codex_state(state):
        events = load_events(root, run_id, 200)
        return [
            "Stats",
            "",
            f"status: {state.get('status')}",
            f"source: {state.get('source_type')}",
            f"event_count: {len(events)}",
            f"codex_session_id: {state.get('codex_session_id')}",
            f"codex_session_path: {state.get('codex_session_path')}",
        ]
    try:
        stats = run_stats(root, run_id)
    except Exception as exc:
        return [f"Could not compute stats: {exc}"]
    out = ["Stats", ""]
    for key in ["status", "duration_seconds", "worker_count", "event_count", "dispatch_count", "handoff_count", "evidence_count", "largest_dispatch_chars", "context_capsule_chars", "token_pressure_estimate", "failures", "retries", "replans"]:
        out.append(f"{key}: {stats.get(key)}")
    if stats.get("reasoning_counts"):
        out.append("")
        out.append("Reasoning mix:")
        for k, v in stats["reasoning_counts"].items():
            out.append(f"  - {k}: {v}")
    return out


def tab_lines(root: Path, tab: int, sessions: list[dict[str, Any]], selected: int, run_id: str | None) -> list[str]:
    name = TABS[tab]
    if name == "Sessions":
        return lines_sessions(root, sessions, selected)
    if name == "Overview":
        return lines_overview(root, run_id)
    if name == "DAG":
        return lines_dag(root, run_id)
    if name == "Workers":
        return lines_workers(root, run_id)
    if name == "Events":
        return lines_events(root, run_id)
    if name == "Verification":
        return lines_verification(root, run_id)
    if name == "Memory":
        return load_memory(root, run_id)
    if name == "Usage":
        return lines_usage(root, run_id)
    if name == "Codex":
        return lines_codex(root, run_id)
    if name == "Gates":
        return lines_gates(root, run_id)
    if name == "Stats":
        return lines_stats(root, run_id)
    return []


def snapshot(root: Path, run_id: str | None = None) -> str:
    sessions = load_sessions(root)
    selected = 0
    if run_id == "latest" or not run_id:
        run_id = sessions[0].get("run_id") if sessions else None
    elif sessions:
        for i, s in enumerate(sessions):
            if s.get("run_id") == run_id:
                selected = i
                break
    sections = []
    for tab in range(len(TABS)):
        sections.append(f"## {TABS[tab]}")
        sections.extend(tab_lines(root, tab, sessions, selected, run_id)[:30])
        sections.append("")
    return "\n".join(sections)


def safe_add(stdscr: Any, y: int, x: int, text: str, width: int, attr: int = 0) -> None:
    if width <= 0:
        return
    try:
        stdscr.addnstr(y, x, text, width, attr)
    except curses.error:
        return


def draw(stdscr: Any, root: Path, run_id_arg: str | None, interval: float) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    tab = 0
    selected = 0
    scroll = 0
    paused = False
    interval = max(0.5, interval)
    while True:
        stdscr.timeout(-1 if paused else max(100, int(interval * 1000)))
        sessions = load_sessions(root)
        if run_id_arg and run_id_arg != "latest":
            for i, s in enumerate(sessions):
                if s.get("run_id") == run_id_arg:
                    selected = i
                    break
        selected = max(0, min(selected, max(0, len(sessions) - 1)))
        run_id = sessions[selected].get("run_id") if sessions else None
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if h < 5 or w < 32:
            safe_add(stdscr, 0, 0, short("AOC: terminal too small", w), w, curses.A_REVERSE)
            if h > 1:
                safe_add(stdscr, 1, 0, short("Resize or use --snapshot", w), w)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch in (ord("q"), 27):
                return
            continue
        title = f" Agentic Orchestration Control | repo={root} | run={run_id or 'none'} "
        live = "paused" if paused else "live"
        title = short(f"{title}| {live} {interval:.1f}s ", w)
        safe_add(stdscr, 0, 0, title.ljust(w), w, curses.A_REVERSE)
        tabs = "  ".join((f"[{t}]" if i == tab else f" {t} ") for i, t in enumerate(TABS))
        safe_add(stdscr, 1, 0, short(tabs, w).ljust(w), w, curses.A_BOLD)
        help_line = "Tab/Left/Right views | Up/Down select/scroll | r refresh | p pause | +/- interval | q quit | --snapshot"
        safe_add(stdscr, h - 1, 0, short(help_line, w).ljust(w), w, curses.A_REVERSE)
        lines = tab_lines(root, tab, sessions, selected, run_id)
        max_body = h - 4
        if tab == 0:
            scroll = 0
        else:
            scroll = max(0, min(scroll, max(0, len(lines) - max_body)))
        for row, line in enumerate(lines[scroll : scroll + max_body], start=3):
            attr = curses.A_NORMAL
            if line.startswith(">"):
                attr = curses.A_BOLD
            safe_add(stdscr, row, 0, short(line, w - 1), w - 1, attr)
        stdscr.refresh()
        ch = stdscr.getch()
        if ch == -1:
            continue
        if ch in (ord("q"), 27):
            return
        if ch in (ord("r"),):
            continue
        if ch in (ord("p"), ord(" ")):
            paused = not paused
            continue
        if ch in (ord("+"), ord("=")):
            interval = min(60.0, interval + 0.5)
            continue
        if ch in (ord("-"), ord("_")):
            interval = max(0.5, interval - 0.5)
            continue
        if ch in (curses.KEY_RIGHT, ord("\t")):
            tab = (tab + 1) % len(TABS)
            scroll = 0
        elif ch == curses.KEY_LEFT:
            tab = (tab - 1) % len(TABS)
            scroll = 0
        elif ch == curses.KEY_DOWN:
            if tab == 0:
                selected = min(selected + 1, max(0, len(sessions) - 1))
            else:
                scroll += 1
        elif ch == curses.KEY_UP:
            if tab == 0:
                selected = max(0, selected - 1)
            else:
                scroll = max(0, scroll - 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Open the local orchestration control-room TUI")
    ap.add_argument("--repo", "--root", dest="root", default=".")
    ap.add_argument("--run", "--run-id", dest="run_id", default="latest")
    ap.add_argument("--snapshot", action="store_true", help="Print a non-interactive dashboard snapshot")
    ap.add_argument("--json", action="store_true", help="Print sessions + selected stats as JSON")
    ap.add_argument("--interval", type=float, default=2.0, help="Live TUI refresh interval in seconds")
    ap.add_argument("--rebuild-index", action="store_true", help="Explicitly rebuild .orchestration/index.json before reading")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.rebuild_index:
        rebuild_index(root)
    if args.json:
        sessions = load_sessions(root)
        rid = args.run_id
        if rid == "latest":
            rid = latest_run_id(root)
        payload = {"sessions": sessions, "selected_run": rid, "stats": run_stats(root, rid) if rid else {}}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if args.snapshot or not sys.stdout.isatty() or os.environ.get("TERM", "") in {"", "dumb"}:
        print(snapshot(root, args.run_id))
        return
    curses.wrapper(draw, root, args.run_id, args.interval)


if __name__ == "__main__":
    main()
