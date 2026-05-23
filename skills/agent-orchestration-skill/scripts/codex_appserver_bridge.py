#!/usr/bin/env python3
"""Safe bridge helpers for Codex app-server / codexui style integrations.

This script does not start remote tunnels or grant permissions. It gives the
AOC Control Room a deterministic way to:
- check local Codex/codexapp availability,
- link an AOC run to a Codex thread/app-server URL,
- read codexui/app-server metadata endpoints when explicitly provided,
- import JSON/JSONL events into the AOC event bus.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import emit_event, latest_run_id, read_json, run_dir, write_json_atomic  # noqa: E402


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def command_result(cmd: list[str], timeout: int = 8) -> dict[str, Any]:
    try:
        res = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "command": cmd,
            "ok": res.returncode == 0,
            "exit_code": res.returncode,
            "stdout": (res.stdout or "").strip()[:2000],
            "stderr": (res.stderr or "").strip()[:2000],
        }
    except Exception as exc:
        return {"command": cmd, "ok": False, "error": str(exc)}


def http_json(url: str, timeout: int = 5) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - explicit local/user-provided URL helper
            body = resp.read(2_000_000).decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body[:4000]}
            return {"ok": True, "status": getattr(resp, "status", None), "url": url, "data": data}
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def normalize_url(base: str | None) -> str | None:
    if not base:
        return None
    base = base.strip().rstrip("/")
    if not base:
        return None
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    return base


def doctor(url: str | None = None, json_out: bool = False) -> dict[str, Any]:
    codex = shutil.which("codex")
    node = shutil.which("node")
    npx = shutil.which("npx")
    out: dict[str, Any] = {
        "checked_at": now(),
        "codex_bin": codex,
        "node_bin": node,
        "npx_bin": npx,
        "safe_defaults": {
            "host": "127.0.0.1",
            "tunnel": "disabled_by_default",
            "sandbox": "workspace-write recommended",
            "approval_policy": "on-request recommended",
        },
        "commands": {},
    }
    if codex:
        out["commands"]["codex_version"] = command_result([codex, "--version"])
        out["commands"]["codex_app_server_help"] = command_result([codex, "app-server", "--help"])
    if npx:
        # Do not install/run codexapp here. Only tell the user it can be launched.
        out["codexui_hint"] = "Use `npx codexapp` separately, then pass --url http://127.0.0.1:<port> if you want AOC to read its local metadata endpoints."
    base = normalize_url(url or os.environ.get("AOC_CODEXUI_URL") or os.environ.get("AOC_CODEX_APP_URL"))
    if base:
        out["url"] = base
        out["meta_methods"] = http_json(f"{base}/codex-api/meta/methods")
        out["events_endpoint"] = f"{base}/codex-api/events"
        out["ws_endpoint"] = f"{base}/codex-api/ws"
    if not json_out:
        print_human_status(out)
    return out


def print_human_status(data: dict[str, Any]) -> None:
    print("Codex app-server / codexui bridge status")
    print(f"checked_at: {data.get('checked_at')}")
    print(f"codex: {data.get('codex_bin') or 'not found'}")
    print(f"node:  {data.get('node_bin') or 'not found'}")
    print(f"npx:   {data.get('npx_bin') or 'not found'}")
    cmds = data.get("commands") or {}
    for name, result in cmds.items():
        print(f"{name}: {'PASS' if result.get('ok') else 'WARN'}")
        if result.get("stdout"):
            print(f"  {result.get('stdout').splitlines()[0]}")
        if result.get("stderr") and not result.get("ok"):
            print(f"  {result.get('stderr').splitlines()[0]}")
    if data.get("url"):
        mm = data.get("meta_methods") or {}
        print(f"url: {data.get('url')}")
        print(f"meta methods: {'PASS' if mm.get('ok') else 'WARN'}")
        if mm.get("error"):
            print(f"  {mm.get('error')}")
    print("safe default: local-only observer; no tunnel or danger-full-access is started by AOC.")


def link(root: Path, run_id: str, thread_id: str | None, url: str | None, source: str = "manual") -> dict[str, Any]:
    if run_id == "latest":
        run_id = latest_run_id(root) or "latest"
    rd = run_dir(root, run_id)
    rd.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "aoc_codex_link",
        "linked_at": now(),
        "run_id": run_id,
        "thread_id": thread_id,
        "url": normalize_url(url),
        "source": source,
    }
    write_json_atomic(rd / "codex_thread.json", payload)
    emit_event(root, event="codex_thread_linked", run_id=run_id, status="linked", summary=f"linked Codex thread {thread_id or 'unknown'}", metadata=payload)
    return payload


def read_lines(path: Path) -> list[Any]:
    if path.suffix.lower() == ".jsonl":
        out = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                out.append({"raw": line})
        return out
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("events", "items", "notifications", "turns", "messages"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []


def import_events(root: Path, run_id: str, path: Path, source: str = "codex_appserver") -> dict[str, Any]:
    if run_id == "latest":
        run_id = latest_run_id(root) or "latest"
    rows = read_lines(path)
    count = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        event = item.get("event") or item.get("method") or item.get("type") or item.get("name") or "codex_event"
        summary = item.get("summary") or item.get("message") or item.get("status") or event
        metadata = {"source": source, "codex": item}
        emit_event(root, event=f"codex_{event}".replace("/", "_"), run_id=run_id, status=str(item.get("status") or "observed"), summary=str(summary)[:500], metadata=metadata)
        count += 1
    emit_event(root, event="codex_events_imported", run_id=run_id, status="ok", summary=f"imported {count} Codex events", metadata={"path": str(path), "source": source})
    return {"run_id": run_id, "imported": count, "path": str(path)}


def snapshot(root: Path, run_id: str, url: str | None = None) -> dict[str, Any]:
    if run_id == "latest":
        run_id = latest_run_id(root) or "latest"
    rd = run_dir(root, run_id)
    link_data = read_json(rd / "codex_thread.json", {})
    status = doctor(url or link_data.get("url"), json_out=True)
    return {"run_id": run_id, "link": link_data, "status": status}


def main() -> None:
    ap = argparse.ArgumentParser(description="Safe Codex app-server/codexui bridge for AOC Control Room")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor")
    p.add_argument("--url", default=None, help="Optional codexui/codex app UI URL, e.g. http://127.0.0.1:3000")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("status")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--url", default=None)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("link")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--thread-id", default=None)
    p.add_argument("--url", default=None)
    p.add_argument("--source", default="manual")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("import")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--input", required=True)
    p.add_argument("--source", default="codex_appserver")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("start-help")

    p = sub.add_parser("codexui")

    args = ap.parse_args()
    if args.cmd == "doctor":
        data = doctor(args.url, json_out=args.json)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    if args.cmd == "status":
        data = snapshot(Path(args.root).resolve(), args.run_id, args.url)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print_human_status(data.get("status") or {})
            link_data = data.get("link") or {}
            if link_data:
                print(f"linked run: {link_data.get('run_id')} thread: {link_data.get('thread_id') or 'unknown'}")
        return
    if args.cmd == "link":
        data = link(Path(args.root).resolve(), args.run_id, args.thread_id, args.url, args.source)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Linked run {data['run_id']} to Codex thread {data.get('thread_id') or 'unknown'}")
        return
    if args.cmd == "import":
        data = import_events(Path(args.root).resolve(), args.run_id, Path(args.input), args.source)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Imported {data['imported']} Codex events into run {data['run_id']}")
        return
    if args.cmd in {"start-help", "codexui"}:
        print("Safe local options:")
        print("  1. Start codexui/codexapp separately: npx codexapp --host 127.0.0.1")
        print("  2. Start AOC GUI: aoc gui --with-codex --codex-url http://127.0.0.1:<port>")
        print("  3. Keep tunnels/off-host access opt-in only, with auth/password enabled.")
        return


if __name__ == "__main__":
    main()
