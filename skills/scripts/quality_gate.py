#!/usr/bin/env python3
"""Run verification commands and write JSON/Markdown evidence."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def run(cmd: str, cwd: Path, timeout: int) -> dict:
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), shell=True, text=True, capture_output=True, timeout=timeout)
        return {
            "command": cmd,
            "returncode": proc.returncode,
            "duration_seconds": round(time.time() - start, 2),
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as e:
        return {
            "command": cmd,
            "returncode": 124,
            "duration_seconds": timeout,
            "stdout_tail": (e.stdout or "")[-4000:] if isinstance(e.stdout, str) else "",
            "stderr_tail": (e.stderr or "")[-4000:] if isinstance(e.stderr, str) else "",
            "timeout": True,
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
    ap.add_argument("commands", nargs="+", help="Commands to run. Quote each command.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default=".orchestration/quality-gate")
    args = ap.parse_args()
    root = Path(args.root)
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    results = [run(c, root, args.timeout) for c in args.commands]
    (out / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out / "report.md").write_text(markdown(results), encoding="utf-8")
    print(markdown(results))
    raise SystemExit(0 if all(r["returncode"] == 0 for r in results) else 1)

if __name__ == "__main__":
    main()
