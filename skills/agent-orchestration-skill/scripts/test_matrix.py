#!/usr/bin/env python3
"""Detect common project test/build commands without executing them."""
from __future__ import annotations

import argparse
import json
import re
import tomllib
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


def has_pytest_config(root: Path) -> bool:
    if exists(root, "pytest.ini"):
        return True
    for name in ["setup.cfg", "tox.ini"]:
        p = root / name
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace").lower()
            if "[pytest]" in text or "[tool:pytest]" in text:
                return True
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except Exception:
            return False
        if isinstance(data.get("tool"), dict) and isinstance(data["tool"].get("pytest"), dict):
            return True
        blob = json.dumps(data).lower()
        if re.search(r"\bpytest\b", blob):
            return True
    return False


def has_pytest_files(root: Path) -> bool:
    skip = {"node_modules", ".git", ".orchestration", "dist", "build", "__pycache__"}
    for base in [root / "tests", root / "test"]:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in skip for part in path.relative_to(root).parts):
                continue
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                return True
    for path in root.glob("test_*.py"):
        if path.is_file():
            return True
    return False


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
    if has_pytest_config(root) or has_pytest_files(root):
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
