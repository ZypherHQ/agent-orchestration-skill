#!/usr/bin/env python3
"""Detect common project test/build commands without executing them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def exists(root: Path, name: str) -> bool:
    return (root / name).exists()


def package_scripts(root: Path) -> dict:
    p = root / "package.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("scripts", {}) or {}
    except Exception:
        return {}


def detect(root: Path) -> list[dict]:
    commands = []
    scripts = package_scripts(root)
    pm = "npm"
    if exists(root, "pnpm-lock.yaml"):
        pm = "pnpm"
    elif exists(root, "yarn.lock"):
        pm = "yarn"
    for key, label in [("lint", "lint"), ("typecheck", "typecheck"), ("test", "test"), ("build", "build"), ("test:e2e", "e2e")]:
        if key in scripts:
            cmd = f"{pm} run {key}" if pm != "yarn" else f"yarn {key}"
            commands.append({"label": label, "command": cmd})
    if exists(root, "pytest.ini") or exists(root, "pyproject.toml"):
        commands.append({"label": "python-tests", "command": "pytest"})
    if exists(root, "go.mod"):
        commands.append({"label": "go-tests", "command": "go test ./..."})
    if exists(root, "Cargo.toml"):
        commands.append({"label": "rust-tests", "command": "cargo test"})
    if exists(root, "docker-compose.yml") or exists(root, "docker-compose.yaml"):
        commands.append({"label": "docker-config", "command": "docker compose config"})
    return commands


def main() -> None:
    ap = argparse.ArgumentParser(description="Suggest verification commands.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    cmds = detect(Path(args.root))
    if args.json:
        print(json.dumps({"commands": cmds}, indent=2))
    else:
        if not cmds:
            print("No standard commands detected. Ask a worker to inspect project docs/package scripts.")
        for c in cmds:
            print(f"{c['label']}: {c['command']}")

if __name__ == "__main__":
    main()
