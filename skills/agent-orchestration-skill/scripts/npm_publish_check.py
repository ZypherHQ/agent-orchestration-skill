#!/usr/bin/env python3
"""Pre-publish checks for the npm/npx AOC package."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

BYTECODE_EXCLUDES = ["!**/__pycache__/", "!**/__pycache__/**", "!**/*.pyc", "!**/*.pyo"]


def fail(msg: str) -> None:
    print(f"FAIL {msg}")
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"PASS {msg}")


def path_has_payload(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file() or path.is_symlink():
        return True
    try:
        return any(path.iterdir())
    except OSError:
        return True


def load_package(root: Path) -> dict[str, Any]:
    p = root / "package.json"
    if not p.exists():
        fail("package.json missing")
    return json.loads(p.read_text(encoding="utf-8"))


def valid_semver(v: str) -> bool:
    return re.match(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$", v or "") is not None


def is_python_bytecode_artifact(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return "/__pycache__/" in f"/{normalized}" or normalized.endswith((".pyc", ".pyo"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate npm package readiness")
    ap.add_argument("--root", default=".")
    ap.add_argument("--pack-dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    pkg = load_package(root)

    name = pkg.get("name") or ""
    if not re.match(r"^(?:@[a-z0-9_.-]+/)?[a-z0-9_.-]+$", name):
        fail(f"invalid npm package name: {name}")
    ok(f"package name: {name}")

    if not valid_semver(pkg.get("version", "")):
        fail(f"invalid semver version: {pkg.get('version')}")
    ok(f"semver version: {pkg.get('version')}")

    if pkg.get("private") is True:
        fail("private must not be true for public npm publish")
    ok("package is publishable")

    if not pkg.get("bin") or not isinstance(pkg.get("bin"), dict):
        fail("bin map missing")
    for cmd, rel in pkg["bin"].items():
        path = root / rel
        if not path.exists():
            fail(f"bin target missing for {cmd}: {rel}")
        first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        if not first.startswith("#!"):
            fail(f"bin target {rel} missing shebang")
        if os.name != "nt" and not os.access(path, os.X_OK):
            fail(f"bin target {rel} is not executable")
    ok(f"validated {len(pkg['bin'])} bin commands")

    for required in ["README.md", "LICENSE", "install.sh", "docs/README.md", "skills/agent-orchestration-skill/SKILL.md", "subagents/config.toml"]:
        if not (root / required).exists():
            fail(f"required publish file missing: {required}")
    ok("required publish files present")

    forbidden_payload_dirs = [".skills", ".agents", ".codex"]
    for forbidden in forbidden_payload_dirs:
        if path_has_payload(root / forbidden):
            fail(f"forbidden production path contains payload: {forbidden}")
    forbidden_files = ["skills/agent-orchestration-skill/scripts/demo_run.py"]
    for forbidden in forbidden_files:
        if (root / forbidden).exists():
            fail(f"forbidden production path present: {forbidden}")
    ok("forbidden legacy/demo paths absent")

    for rel in ["tests/aggressive_validation.py", "tests/npm_cli_validation.mjs", "tools/fix-permissions.mjs"]:
        if not (root / rel).exists():
            fail(f"required validation tool missing: {rel}")
    ok("production validation tools present")

    files = pkg.get("files") or []
    for required in ["bin/", "tools/", "skills/", "subagents/", "docs/", "install.sh", "README.md", "LICENSE", "tests/"]:
        if required not in files:
            fail(f"package.json files does not include {required}")
    ok("package files allowlist includes runtime payload")

    for required in BYTECODE_EXCLUDES:
        if required not in files:
            fail(f"package.json files does not exclude Python bytecode artifact pattern: {required}")
    ok("package files excludes Python bytecode artifacts")

    if pkg.get("repository", {}).get("url", "").find("ZypherHQ/agent-orchestration-skill") == -1:
        fail("repository.url should point to ZypherHQ/agent-orchestration-skill")
    ok("repository metadata points to GitHub repo")

    if args.pack_dry_run:
        with tempfile.TemporaryDirectory(prefix="aoc-npm-cache-") as cache:
            env = {**os.environ, "npm_config_cache": cache}
            res = subprocess.run(["npm", "pack", "--dry-run", "--json"], cwd=root, text=True, capture_output=True, check=False, env=env)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr)
            fail("npm pack --dry-run failed")
        output = res.stdout + res.stderr
        try:
            pack_entries = json.loads(res.stdout)
        except json.JSONDecodeError as exc:
            print(output)
            fail(f"npm pack --dry-run --json produced invalid JSON: {exc}")
        if not isinstance(pack_entries, list) or not pack_entries:
            print(output)
            fail("npm pack --dry-run --json produced no package entries")
        packed_files = [f.get("path", "") for f in pack_entries[0].get("files", []) if isinstance(f, dict)]
        for needle in ["package.json", "bin/aoc.mjs", "tools/fix-permissions.mjs", "docs/README.md", "skills/agent-orchestration-skill/SKILL.md", "tests/aggressive_validation.py"]:
            if needle not in packed_files:
                fail(f"npm pack dry run did not include {needle}")
        for bad in [".skills/", ".agents/", ".codex/", "demo_run.py"]:
            if bad in output:
                fail(f"npm pack dry run includes forbidden path: {bad}")
        for bad in packed_files:
            if is_python_bytecode_artifact(bad):
                fail(f"npm pack dry run includes Python bytecode artifact: {bad}")
        ok("npm pack --dry-run includes core payload and excludes legacy/demo/bytecode paths")

    print("NPM PUBLISH CHECK PASSED")


if __name__ == "__main__":
    main()
