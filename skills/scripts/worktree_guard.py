#!/usr/bin/env python3
"""Safe git worktree helper for larger orchestration runs.

Default mode is read-only planning. Creation requires --create.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def git_root(path: Path) -> Path | None:
    p = run(["git", "rev-parse", "--show-toplevel"], path)
    return Path(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None


def status(root: Path) -> dict:
    p = run(["git", "status", "--porcelain=v1"], root)
    return {"returncode": p.returncode, "dirty": bool(p.stdout.strip()), "porcelain": p.stdout.strip().splitlines(), "stderr": p.stderr.strip()}


def main() -> None:
    ap = argparse.ArgumentParser(description="Plan or create an isolated orchestration worktree")
    ap.add_argument("--root", default=".")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    start = Path(args.root).resolve()
    root = git_root(start)
    if not root:
        raise SystemExit("Not inside a git repo")
    st = status(root)
    branch = f"agent/{args.run_id}"
    wt = root.parent / f"{root.name}-{args.run_id}"
    result = {"git_root": str(root), "dirty": st["dirty"], "planned_branch": branch, "planned_worktree": str(wt), "status": "PLAN_ONLY"}
    if st["dirty"]:
        result["warning"] = "Main checkout has uncommitted changes; isolated worktree is recommended for L/XL work. Preserve unrelated work."
    if args.create:
        if wt.exists():
            result["status"] = "EXISTS"
        else:
            proc = run(["git", "worktree", "add", "-b", branch, str(wt), "HEAD"], root)
            result.update({"status": "CREATED" if proc.returncode == 0 else "FAILED", "returncode": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]})
            if proc.returncode != 0:
                print(json.dumps(result, indent=2) if args.json else result)
                sys.exit(1)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Status: {result['status']}")
        print(f"Git root: {root}")
        print(f"Dirty: {st['dirty']}")
        print(f"Branch: {branch}")
        print(f"Worktree: {wt}")
        if result.get("warning"):
            print(f"Warning: {result['warning']}")


if __name__ == "__main__":
    main()
