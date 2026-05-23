#!/usr/bin/env python3
"""Run verification commands and write JSON/Markdown evidence."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from event_emit import emit_event  # type: ignore  # noqa: E402
except Exception:
    emit_event = None  # type: ignore


SHELL_TOKENS = {"|", "||", "&", "&&", ";", "<", ">", ">>", "2>", "2>>"}


def command_display(spec: Any) -> str:
    if isinstance(spec, dict):
        if isinstance(spec.get("argv"), list):
            return " ".join(shlex.quote(str(x)) for x in spec["argv"])
        if isinstance(spec.get("cmd"), list):
            return " ".join(shlex.quote(str(x)) for x in spec["cmd"])
        if spec.get("shell") is not None:
            return str(spec["shell"])
    if isinstance(spec, list):
        return " ".join(shlex.quote(str(x)) for x in spec)
    return str(spec)


def normalize_command(spec: Any, allow_shell: bool) -> tuple[list[str] | str | None, bool, str | None]:
    if isinstance(spec, dict):
        if "argv" in spec:
            spec = spec["argv"]
        elif "cmd" in spec:
            spec = spec["cmd"]
        elif "shell" in spec:
            if not allow_shell:
                return None, False, "Command uses shell mode; rerun with --shell to allow explicit shell execution."
            return str(spec["shell"]), True, None
        else:
            return None, False, "Command object must contain argv, cmd, or shell."
    if isinstance(spec, list):
        argv = [str(x) for x in spec if str(x)]
        if not argv:
            return None, False, "Command argv is empty."
        return argv, False, None
    cmd = str(spec).strip()
    if not cmd:
        return None, False, "Command is empty."
    if allow_shell:
        return cmd, True, None
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        return None, False, f"Could not parse command argv: {exc}"
    if not argv:
        return None, False, "Command argv is empty."
    if any(token in SHELL_TOKENS for token in argv) or "$(" in cmd or "`" in cmd or "\n" in cmd:
        return None, False, "Shell syntax detected; rerun with --shell or provide a JSON argv command spec."
    return argv, False, None


def load_command_specs(args: argparse.Namespace) -> list[Any]:
    specs: list[Any] = []
    for raw in args.command_json or []:
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --command-json: {exc}") from exc
        if isinstance(loaded, list) and (not loaded or isinstance(loaded[0], (list, dict))):
            specs.extend(loaded)
        else:
            specs.append(loaded)
    if args.commands_file:
        try:
            loaded = json.loads(Path(args.commands_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --commands-file JSON: {exc}") from exc
        if not isinstance(loaded, list):
            raise SystemExit("--commands-file must contain a JSON list of command specs")
        specs.extend(loaded)
    specs.extend(args.commands or [])
    if not specs:
        raise SystemExit("No commands provided.")
    return specs


def run(spec: Any, cwd: Path, timeout: int, allow_shell: bool) -> dict:
    start = time.time()
    display = command_display(spec)
    cmd, shell_mode, error = normalize_command(spec, allow_shell)
    if error:
        return {
            "command": display,
            "returncode": 2,
            "duration_seconds": 0,
            "stdout_tail": "",
            "stderr_tail": error,
            "not_run": True,
        }
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), shell=shell_mode, text=True, capture_output=True, timeout=timeout)
        return {
            "command": display,
            "returncode": proc.returncode,
            "duration_seconds": round(time.time() - start, 2),
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as e:
        return {
            "command": display,
            "returncode": 124,
            "duration_seconds": timeout,
            "stdout_tail": (e.stdout or "")[-4000:] if isinstance(e.stdout, str) else "",
            "stderr_tail": (e.stderr or "")[-4000:] if isinstance(e.stderr, str) else "",
            "timeout": True,
        }
    except FileNotFoundError as exc:
        return {
            "command": display,
            "returncode": 127,
            "duration_seconds": round(time.time() - start, 2),
            "stdout_tail": "",
            "stderr_tail": str(exc),
        }


def markdown(results: list[dict]) -> str:
    lines = ["# Quality Gate Report", ""]
    for r in results:
        status = "PASS" if r["returncode"] == 0 else "FAIL"
        lines.append(f"## {status}: `{r['command']}`")
        lines.append(f"- returncode: {r['returncode']}")
        lines.append(f"- duration_seconds: {r['duration_seconds']}")
        if r.get("stdout_tail"):
            lines.append("\n### stdout tail\n```\n" + r["stdout_tail"] + "\n```")
        if r.get("stderr_tail"):
            lines.append("\n### stderr tail\n```\n" + r["stderr_tail"] + "\n```")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run verification commands.")
    ap.add_argument("commands", nargs="*", help="Commands to run as argv-split strings by default. Use --shell for shell syntax.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default=".orchestration/quality-gate")
    ap.add_argument("--run-id", help="Optional orchestration run ID or latest for event logging")
    ap.add_argument("--shell", action="store_true", help="Allow explicit shell execution for command strings or {\"shell\": ...} specs")
    ap.add_argument("--command-json", action="append", default=[], help="JSON command spec: [\"npm\",\"test\"] or {\"argv\":[...]}; may repeat")
    ap.add_argument("--commands-file", help="JSON file containing a list of command specs")
    args = ap.parse_args()
    root = Path(args.root)
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for c in load_command_specs(args):
        if emit_event is not None and args.run_id:
            emit_event(root, event="command_started", run_id=args.run_id, status="running", summary=command_display(c), update_state=True)
        r = run(c, root, args.timeout, allow_shell=args.shell)
        results.append(r)
        if emit_event is not None and args.run_id:
            emit_event(root, event="command_finished", run_id=args.run_id, status="passed" if r["returncode"] == 0 else "failed", summary=r["command"], metadata={"returncode": r["returncode"], "duration_seconds": r["duration_seconds"]}, update_state=True)
    (out / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out / "report.md").write_text(markdown(results), encoding="utf-8")
    report = markdown(results)
    print(report)
    all_ok = all(r["returncode"] == 0 for r in results)
    if emit_event is not None and args.run_id:
        emit_event(root, event="quality_gate_completed" if all_ok else "verification_failed", run_id=args.run_id, status="passed" if all_ok else "failed", summary=f"Quality gate {'passed' if all_ok else 'failed'}: {len(results)} command(s)", metadata={"evidence": str(out / "report.md")}, update_state=True)
    raise SystemExit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
