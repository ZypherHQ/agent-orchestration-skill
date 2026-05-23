#!/usr/bin/env python3
"""Optional bridge from ccusage JSON into the orchestration usage ledger.

ccusage is treated as an external local-first source of truth when available.
This bridge can either parse a JSON file produced by ccusage or run a focused
Codex report command and import the result.
"""
from __future__ import annotations

import argparse
import json
import shutil
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import latest_run_id  # noqa: E402
from usage_ledger import append_usage, to_float, to_int  # noqa: E402


def pick(obj: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return default


def model_name(row: dict[str, Any]) -> str:
    val = pick(row, "model", "modelName", "models", "modelsUsed", default="")
    if isinstance(val, list):
        return ",".join(str(x) for x in val)
    if isinstance(val, dict):
        return ",".join(str(k) for k in val.keys())
    return str(val or "")


def normalize_ccusage_row(row: dict[str, Any], *, run_id: str | None, source_report: str, fallback_id: str) -> dict[str, Any]:
    session_id = str(pick(row, "sessionId", "session_id", "id", "conversationId", "conversation_id", "session", default=fallback_id))
    return {
        "source": "ccusage",
        "source_report": source_report,
        "run_id": run_id,
        "session_id": session_id,
        "agent": pick(row, "agent", "source", default="codex"),
        "model": model_name(row),
        "input_tokens": to_int(pick(row, "inputTokens", "input_tokens")),
        "output_tokens": to_int(pick(row, "outputTokens", "output_tokens")),
        "reasoning_output_tokens": to_int(pick(row, "reasoningOutputTokens", "reasoning_output_tokens", "thinkingTokens")),
        "cached_input_tokens": to_int(pick(row, "cachedInputTokens", "cacheReadTokens", "cache_read_tokens")),
        "cache_creation_tokens": to_int(pick(row, "cacheCreationTokens", "cache_creation_tokens")),
        "total_tokens": to_int(pick(row, "totalTokens", "total_tokens")),
        "cost_usd": to_float(pick(row, "costUSD", "totalCost", "cost_usd")),
        "metadata": {
            "date": pick(row, "date", "day", "month", "week", default=""),
            "project": pick(row, "project", "instance", "projectName", default=""),
            "first_activity": pick(row, "firstActivity", "createdAt", "created_at", default=""),
            "last_activity": pick(row, "lastActivity", "updatedAt", "updated_at", default=""),
        },
    }


def rows_from_payload(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    for key in ["sessions", "daily", "weekly", "monthly", "data", "rows"]:
        val = payload.get(key)
        if isinstance(val, list):
            return key, [x for x in val if isinstance(x, dict)]
    totals = payload.get("totals")
    if isinstance(totals, dict):
        return "totals", [totals]
    return "unknown", []


def import_payload(root: Path, payload: dict[str, Any], *, run_id: str | None, source_report: str | None = None) -> list[dict[str, Any]]:
    report, rows = rows_from_payload(payload)
    imported: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        rec = normalize_ccusage_row(row, run_id=run_id, source_report=source_report or report, fallback_id=f"ccusage-{report}-{i}")
        imported.append(append_usage(root, rec))
    return imported


def split_command(command: str) -> list[str]:
    return shlex.split(command) if any(ch.isspace() for ch in command.strip()) else [command]


def run_ccusage(ccusage_bin: str, source: str, report: str, offline: bool, extra: list[str]) -> dict[str, Any]:
    cmd = split_command(ccusage_bin)
    if source != "all":
        cmd.append(source)
    cmd.extend([report, "--json"])
    if offline:
        cmd.append("--offline")
    cmd.extend(extra)
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise SystemExit(f"ccusage failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ccusage did not return JSON: {exc}\n{proc.stdout[:500]}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("ccusage JSON root was not an object")
    return payload


def cmd_import(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or None
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Input JSON root must be an object")
    imported = import_payload(root, payload, run_id=run_id, source_report=args.source_report)
    print(json.dumps({"imported": len(imported), "records": imported}, indent=2, ensure_ascii=False) if args.json else f"imported {len(imported)} ccusage record(s)")


def cmd_run(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or None
    payload = run_ccusage(args.ccusage_bin, args.source, args.report, args.offline, args.extra)
    imported = import_payload(root, payload, run_id=run_id, source_report=f"{args.source}:{args.report}")
    print(json.dumps({"imported": len(imported), "payload": payload}, indent=2, ensure_ascii=False) if args.json else f"imported {len(imported)} ccusage record(s) from {args.source} {args.report}")


def cmd_doctor(args: argparse.Namespace) -> None:
    cmd = split_command(args.ccusage_bin)
    path = shutil.which(cmd[0])
    status = {"ccusage_bin": args.ccusage_bin, "available": bool(path), "path": path or ""}
    if path:
        proc = subprocess.run(cmd + ["--version"], text=True, capture_output=True, timeout=30)
        status["version"] = proc.stdout.strip() or proc.stderr.strip()
        status["returncode"] = proc.returncode
    print(json.dumps(status, indent=2, ensure_ascii=False) if args.json else (f"ccusage available: {status.get('version', path)}" if path else "ccusage not found on PATH"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Import ccusage JSON into the orchestration usage ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import", help="Import a ccusage JSON file")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--input", required=True)
    p.add_argument("--source-report")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("run", help="Run ccusage and import the JSON result")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--ccusage-bin", default="ccusage")
    p.add_argument("--source", default="codex", choices=["all", "codex", "claude", "opencode", "amp", "droid", "codebuff", "hermes", "pi", "goose", "openclaw", "kilo", "kimi", "qwen", "copilot", "gemini"])
    p.add_argument("--report", default="session", choices=["daily", "weekly", "monthly", "session"])
    p.add_argument("--offline", action="store_true", default=True)
    p.add_argument("--no-offline", dest="offline", action="store_false")
    p.add_argument("--extra", nargs="*", default=[])
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("doctor", help="Check ccusage availability")
    p.add_argument("--ccusage-bin", default="ccusage")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
