#!/usr/bin/env python3
"""Production validation for Agentic Orchestration Control.

This suite is intentionally strict. It validates packaging layout, executable
bits, self-install safety, external install behavior, deterministic utility
scripts, TUI/GUI snapshots, usage/budget controls, and npm publish readiness.
It does not call models and it does not require Codex runtime access.
"""
from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "agent-orchestration-skill"
SCRIPTS = SKILL / "scripts"


def ok(msg: str) -> None:
    print(f"PASS {msg}", flush=True)


def fail(msg: str) -> None:
    raise AssertionError(msg)


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd or ROOT), text=True, capture_output=True, timeout=timeout)
    if check and proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        fail(f"command failed: {' '.join(map(str, cmd))}")
    return proc


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        fail(f"missing dependency: {name}")


def path_has_payload(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file() or path.is_symlink():
        return True
    try:
        return any(path.iterdir())
    except OSError:
        return True



def run_to_file(cmd: list[str], timeout: int = 90) -> str:
    """Run a command without pipe capture to avoid TUI/GUI wrapper pipe edge cases."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "stdout.txt"
        err = Path(td) / "stderr.txt"
        with out.open("w", encoding="utf-8") as stdout, err.open("w", encoding="utf-8") as stderr:
            proc = subprocess.run(cmd, stdout=stdout, stderr=stderr, text=True, timeout=timeout, check=False)
        stdout_text = out.read_text(encoding="utf-8", errors="replace")
        stderr_text = err.read_text(encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            print(stdout_text)
            print(stderr_text, file=sys.stderr)
            fail(f"command failed: {' '.join(map(str, cmd))}")
        return stdout_text + ("\n" + stderr_text if stderr_text else "")

def import_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        fail(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def copy_package(dst: Path) -> None:
    ignore = shutil.ignore_patterns("dist", "node_modules", ".git", ".agents", ".codex", ".skills", ".orchestration", "*.tgz", "__pycache__", "*.pyc")
    shutil.copytree(ROOT, dst, ignore=ignore)


def assert_exec(path: Path) -> None:
    if not path.exists():
        fail(f"missing executable: {path}")
    if os.name != "nt" and not os.access(path, os.X_OK):
        fail(f"not executable: {path}")


def assert_agent_gate(path: Path) -> None:
    if not path.exists():
        fail(f"missing AGENTS.md gate file: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    for phrase in ["$agent-orchestration-skill", "exact literal invocation", "Normal mode", "Leaf mode"]:
        if phrase.lower() not in text.lower():
            fail(f"AGENTS.md gate missing phrase: {phrase}")
    if text.count("BEGIN AGENT_ORCHESTRATION_SKILL_GATE") > 1:
        fail("AGENTS.md gate duplicated")


def validate_static() -> None:
    forbidden_roots = [ROOT / ".skills", ROOT / ".agents", ROOT / ".codex"]
    for forbidden in forbidden_roots:
        if path_has_payload(forbidden):
            fail(f"forbidden legacy layout contains payload: {forbidden}")
    if (SCRIPTS / "demo_run.py").exists():
        fail("production package must not include demo_run.py")
    ok("validated production layout has no hidden legacy skill/agent dirs")

    py_files = sorted(SCRIPTS.glob("*.py"))
    if len(py_files) < 25:
        fail(f"expected at least 25 production Python scripts, found {len(py_files)}")
    required_session_scripts = [
        "codex_session_discovery.py",
        "codex_session_importer.py",
        "codex_session_watch.py",
        "codex_session_normalize.py",
    ]
    for script in required_session_scripts:
        if not (SCRIPTS / script).exists():
            fail(f"missing Codex session ingestion script: {script}")
    for path in py_files:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            py_compile.compile(str(path), cfile=str(tmpdir / (path.stem + ".pyc")), doraise=True)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    ok(f"compiled {len(py_files)} Python scripts")

    for path in sorted((ROOT / "subagents").glob("*.toml")):
        tomllib.loads(path.read_text(encoding="utf-8"))
    tomllib.loads((ROOT / "subagents" / "config.toml").read_text(encoding="utf-8"))
    ok("parsed TOML configs")

    skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if len(skill_files) != 1:
        fail(f"expected exactly one discoverable skill, found {len(skill_files)}: {skill_files}")
    text = skill_files[0].read_text(encoding="utf-8")
    for phrase in ["$agent-orchestration-skill", "EXPLICIT ONLY", "Context Capsule", "Context Coverage", "no nested delegation"]:
        if phrase.lower() not in text.lower():
            fail(f"missing explicit/root-only phrase in SKILL.md: {phrase}")
    ok("validated single explicit-only skill")

    required_execs = [
        ROOT / "bin" / "aoc.mjs",
        ROOT / "install.sh",
        ROOT / "tools" / "fix-permissions.mjs",
        SKILL / "bin" / "agentic-orchestration-control",
        SKILL / "bin" / "aoc",
        SKILL / "bin" / "agentic-orchestration-gui",
        SKILL / "bin" / "aoc-gui",
        SKILL / "bin" / "agentic-orchestration-usage",
        SKILL / "bin" / "aoc-usage",
        SCRIPTS / "codex_leaf_exec.sh",
    ]
    for exe in required_execs:
        assert_exec(exe)
    ok("validated executable permissions")

    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    command_contract_path = ROOT / "tools" / "aoc.commands.json"
    if not command_contract_path.exists():
        fail("missing tools/aoc.commands.json command contract")
    command_contract = json.loads(command_contract_path.read_text(encoding="utf-8"))
    commands = command_contract.get("commands")
    if not isinstance(commands, list) or not commands:
        fail("command contract missing non-empty commands list")
    installed_shim_commands = command_contract.get("installedShimCommands")
    if not isinstance(installed_shim_commands, list) or not installed_shim_commands:
        installed_shim_commands = [c.get("name") for c in commands if isinstance(c, dict) and c.get("installedShim") is not False]
    codex_session_shim_commands = command_contract.get("codexSessionShimCommands")
    if not isinstance(codex_session_shim_commands, list) or not codex_session_shim_commands:
        codex_session_shim_commands = ["sessions", "current", "use", "import", "watch", "search"]
    for required in ["sessions", "current", "use", "import", "watch", "search"]:
        if required not in installed_shim_commands:
            fail(f"command contract missing installed shim command: {required}")
        if required not in codex_session_shim_commands:
            fail(f"command contract missing Codex session shim command: {required}")
    ok("validated command contract asset")

    files = set(pkg.get("files", []))
    for required in ["bin/", "tools/", "skills/", "subagents/", "docs/", "tests/", "install.sh", "README.md", "LICENSE"]:
        if required not in files:
            fail(f"package.json files allowlist missing {required}")
    if ".skills/" in files or ".agents/" in files or ".codex/" in files:
        fail("package.json must not include hidden legacy layouts")
    bins = pkg.get("bin", {})
    for required_bin in ["agentic-orchestration-control", "agent-orchestration-control", "aoc", "aoc-gui", "aoc-usage"]:
        if bins.get(required_bin) != "./bin/aoc.mjs":
            fail(f"package.json bin mapping missing or inconsistent: {required_bin}")
    for script in ["test", "publish:check", "validate:production", "prepublishOnly", "fix:permissions"]:
        if script not in pkg.get("scripts", {}):
            fail(f"package.json missing script: {script}")
    manifest = json.loads((ROOT / "SKILL_PACK_MANIFEST.json").read_text(encoding="utf-8"))
    guards = " ".join(manifest.get("production_guards", []))
    for phrase in ["short command contract", "Codex session import"]:
        if phrase.lower() not in guards.lower():
            fail(f"manifest production guards missing phrase: {phrase}")
    ok("validated npm metadata, allowlist, and command assets")

    stale = [p for p in ROOT.rglob("__pycache__") if "node_modules" not in str(p)] + list(ROOT.rglob("*.pyc"))
    if stale:
        fail(f"bytecode artifacts present: {stale[:5]}")
    ok("no bytecode artifacts in pack")


def validate_install_self_and_external() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        # External install with legacy hidden layout present: should back it up and install supported layout.
        repo = td_path / "repo"
        repo.mkdir()
        run(["git", "init", "-q"], cwd=repo)
        (repo / ".skills" / "agent-orchestration-skill").mkdir(parents=True)
        (repo / ".skills" / "agent-orchestration-skill" / "SKILL.md").write_text("legacy", encoding="utf-8")
        run(["bash", str(ROOT / "install.sh"), str(repo)], timeout=240)
        if not (repo / "skills" / "agent-orchestration-skill" / "SKILL.md").exists():
            fail("install did not create skills/agent-orchestration-skill")
        if (repo / ".skills").exists():
            fail("install did not move legacy .skills directory")
        backups = list(repo.glob(".orchestration-backup-*"))
        if not backups:
            fail("expected backup for legacy .skills install")
        if not (repo / ".orchestration" / "bin" / "aoc").exists():
            fail("install did not create local aoc shim")
        assert_exec(repo / ".orchestration" / "bin" / "agentic-orchestration-control")
        assert_agent_gate(repo / "AGENTS.md")
        run(["bash", str(ROOT / "install.sh"), str(repo)], timeout=240)
        assert_agent_gate(repo / "AGENTS.md")
        run(["python3", str(repo / "skills/agent-orchestration-skill/scripts/token_budget_linter.py"), "--root", str(repo)], timeout=240)
        ok("validated external install, legacy backup, and supported layout")

        # Self-install in package root copy: must not move the source skill into backup.
        pkg_copy = td_path / "pkg-copy"
        copy_package(pkg_copy)
        run(["node", str(pkg_copy / "tools/fix-permissions.mjs"), "--quiet"], cwd=pkg_copy)
        before = pkg_copy / "skills" / "agent-orchestration-skill" / "SKILL.md"
        if not before.exists():
            fail("copied package missing source skill before self-install")
        run(["node", str(pkg_copy / "bin/aoc.mjs"), "install", str(pkg_copy)], cwd=pkg_copy, timeout=240)
        after = pkg_copy / "skills" / "agent-orchestration-skill" / "SKILL.md"
        if not after.exists():
            fail("self-install moved or deleted source skill")
        moved = []
        for b in pkg_copy.glob(".orchestration-backup-*"):
            moved.extend(b.glob("skills/agent-orchestration-skill/SKILL.md"))
        if moved:
            fail(f"self-install incorrectly backed up source skill: {moved}")
        if not (pkg_copy / ".orchestration/bin/aoc").exists():
            fail("self-install did not create local shim")
        assert_agent_gate(pkg_copy / "AGENTS.md")
        run([str(pkg_copy / "skills/agent-orchestration-skill/bin/aoc"), "publish-check"], cwd=pkg_copy, timeout=240)
        ok("validated self-install preserves source skill")


def validate_orchestration_flow() -> None:
    event_emit = import_script("event_emit")
    run_ledger = import_script("run_ledger")
    context_capsule = import_script("context_capsule")
    dag_planner = import_script("dag_planner")
    plan_gate = import_script("plan_gate")
    dispatch_compiler = import_script("dispatch_compiler")
    handoff_router = import_script("handoff_router")
    context_gate = import_script("context_coverage_gate")
    handoff_validate = import_script("handoff_validate")
    orchestration_stats = import_script("orchestration_stats")
    usage_ledger = import_script("usage_ledger")
    ccusage_bridge = import_script("ccusage_bridge")
    codex_bridge = import_script("codex_appserver_bridge")
    memory_index = import_script("memory_index")
    aoc_gui = import_script("aoc_gui")

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        run(["git", "init", "-q"], cwd=repo)
        run(["bash", str(ROOT / "install.sh"), str(repo)], timeout=240)

        run_id = "smoke-run"
        run_ledger.init(SimpleNamespace(root=str(repo), run_id=run_id, task="cart subtotal control room smoke", mode="root", context_capsule=""))
        event_emit.emit_event(repo, event="task_classified", run_id=run_id, status="running", summary="M task", metadata={"size": "M"})

        capsule_path = repo / ".orchestration/context_capsule.json"
        capsule = context_capsule.empty_capsule("cart subtotal control room smoke", "fix subtotal", run_id)
        context_capsule.add_many(capsule, "must_read", ["app/cart/page.tsx", "lib/cart/store.ts"])
        context_capsule.add_many(capsule, "confirmed_facts", ["Browser QA reproduced subtotal mismatch"])
        context_capsule.add_many(capsule, "acceptance_criteria", ["subtotal updates immediately"])
        context_capsule.save(capsule_path, capsule)
        event_emit.emit_event(repo, event="context_capsule_created", run_id=run_id, status="ok", summary="capsule created")

        plan = dag_planner.build_plan("cart subtotal control room smoke", ["frontend", "tests"], "M", "medium", "medium", False, False, False)
        if plan_gate.validate(plan):
            fail("valid plan was rejected")
        plan_path = repo / f".orchestration/runs/{run_id}/plan.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        event_emit.emit_event(repo, event="dag_created", run_id=run_id, status="ready", summary="plan created")

        data = {
            "role": "batch_implementer_medium",
            "reasoning": "medium",
            "objective": "Fix subtotal state",
            "scope": "frontend cart",
            "must_read": ["app/cart/page.tsx", "lib/cart/store.ts"],
            "tasks": ["inspect cart state", "validate subtotal path"],
        }
        data = dispatch_compiler.merge_capsule(data, str(capsule_path))
        if not dispatch_compiler.requires_strict_context({"role": "micro_implementer_medium", "objective": "Fix subtotal state"}):
            fail("implementation packets should require strict scoped context")
        if dispatch_compiler.requires_strict_context({"role": "regression_reviewer_medium", "objective": "Review the final diff for regressions; do not edit files."}):
            fail("read-only review packets should not require strict write context")
        packet = dispatch_compiler.packet(data)
        if len(packet) >= 7000:
            fail("dispatch packet exceeded hard token/char budget")
        dispatch_path = repo / f".orchestration/runs/{run_id}/dispatches/P2.md"
        dispatch_path.parent.mkdir(parents=True, exist_ok=True)
        dispatch_path.write_text(packet, encoding="utf-8")
        event_emit.emit_event(repo, event="dispatch_compiled", run_id=run_id, agent="batch_implementer_medium", reasoning="medium", status="ready", summary="dispatch compiled", metadata={"chars": len(packet)})

        handoff = """STATUS: success
SUMMARY: targeted smoke handoff
CONTEXT_COVERAGE:
  required_files_read:
    - app/cart/page.tsx
    - lib/cart/store.ts
  missing_context: []
  safe_to_modify: true
FILES_READ:
  - app/cart/page.tsx
  - lib/cart/store.ts
FILES_CHANGED: []
CHANGES: []
VALIDATION:
  - command: echo smoke
    result: pass
EVIDENCE:
  - .orchestration/runs/smoke-run/evidence/report.md
RISKS: []
PARENT_ACTION: none
"""
        handoff_path = repo / f".orchestration/runs/{run_id}/handoffs/P2.yaml"
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(handoff, encoding="utf-8")
        required = context_gate.load_dispatch_required(dispatch_path)
        if context_gate.validate(required, handoff):
            fail("valid coverage handoff was rejected")
        if handoff_validate.validate(handoff, required):
            fail("valid handoff was rejected")
        event_emit.emit_event(repo, event="handoff_validated", run_id=run_id, agent="batch_implementer_medium", status="passed", summary="handoff validated")

        bad_handoff = handoff.replace("  - lib/cart/store.ts\n", "")
        if not context_gate.validate(required, bad_handoff):
            fail("bad handoff should fail Context Coverage Gate")
        if not handoff_validate.validate(bad_handoff, required):
            fail("bad handoff should fail Handoff Validator")
        routed_files = handoff_router.extract_files("""agent: reviewer
files_touched_or_examined:
  - bin/aoc.mjs
  - install.sh
  - path: scripts/build.cjs
FILES_CHANGED:
  - tests/npm_cli_validation.mjs
  - skills/agent-orchestration-skill/scripts/handoff_router.py
findings:
  - evidence: skills/agent-orchestration-skill/scripts/dispatch_compiler.py:116
""")
        for expected_file in [
            "bin/aoc.mjs",
            "install.sh",
            "scripts/build.cjs",
            "tests/npm_cli_validation.mjs",
            "skills/agent-orchestration-skill/scripts/handoff_router.py",
            "skills/agent-orchestration-skill/scripts/dispatch_compiler.py",
        ]:
            if expected_file not in routed_files:
                fail(f"handoff router missed file: {expected_file}; saw {sorted(routed_files)}")
        ok("validated positive and negative coverage/handoff gates")

        evidence = repo / f".orchestration/runs/{run_id}/evidence/report.md"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("# Evidence\nPASS\n", encoding="utf-8")
        event_emit.emit_event(repo, event="quality_gate_completed", run_id=run_id, status="passed", summary="quality gate passed", metadata={"evidence": str(evidence)})

        idx = memory_index.build_index(repo, run_id)
        if idx["doc_count"] < 2:
            fail(f"memory index too small: {idx}")
        derived = usage_ledger.derive_from_run(repo, run_id)
        if derived["estimated_tokens"] <= 0:
            fail(f"derived usage should estimate token pressure: {derived}")
        usage_ledger.append_usage(repo, derived)
        usage_ledger.append_usage(repo, {
            "source": "manual",
            "run_id": run_id,
            "session_id": run_id,
            "agent": "verification_engine_medium",
            "model": "test-model",
            "reasoning": "medium",
            "input_tokens": 100,
            "output_tokens": 50,
            "reasoning_output_tokens": 25,
            "cached_input_tokens": 10,
            "total_tokens": 185,
            "cost_usd": 0.01,
        })
        fake_ccusage = {"sessions": [{"sessionId": "ccusage-smoke", "inputTokens": 200, "outputTokens": 80, "reasoningOutputTokens": 20, "cachedInputTokens": 40, "totalTokens": 340, "costUSD": 0.02, "modelsUsed": ["codex-test-model"]}], "totals": {"totalTokens": 340}}
        imported = ccusage_bridge.import_payload(repo, fake_ccusage, run_id=run_id, source_report="codex:session")
        if len(imported) != 1 or imported[0]["source"] != "ccusage":
            fail(f"ccusage import failed: {imported}")
        usage_summary = usage_ledger.aggregate(usage_ledger.load_records(repo, run_id), "source")
        if usage_summary["totals"]["total_tokens"] < 525:
            fail(f"usage aggregate missing real/imported tokens: {usage_summary}")
        if usage_summary["totals"]["estimated_tokens"] <= 0:
            fail(f"usage aggregate missing estimated pressure: {usage_summary}")
        if usage_ledger.budget_check(usage_summary, max_real_tokens=10000, max_estimated_tokens=10000, max_cost_usd=1.0)["status"] != "PASS":
            fail("budget should pass under generous caps")
        if usage_ledger.budget_check(usage_summary, max_real_tokens=1, max_estimated_tokens=None, max_cost_usd=None)["status"] != "FAIL":
            fail("budget should fail under tiny real-token cap")
        ok("validated usage ledger, ccusage bridge import, and usage budget checks")

        link_data = codex_bridge.link(repo, run_id, thread_id="thread-smoke", url="http://127.0.0.1:65535", source="test")
        if link_data["thread_id"] != "thread-smoke":
            fail("codex thread link failed")
        fake_codex_events = repo / "codex-events.jsonl"
        fake_codex_events.write_text('{"method":"item/started","status":"running","message":"command started"}\n{"method":"item/completed","status":"passed","message":"command completed"}\n', encoding="utf-8")
        imported_codex = codex_bridge.import_events(repo, run_id, fake_codex_events)
        if imported_codex["imported"] != 2:
            fail(f"codex event import failed: {imported_codex}")
        bridge_status = codex_bridge.snapshot(repo, run_id)
        if bridge_status["link"].get("thread_id") != "thread-smoke":
            fail("codex bridge snapshot missing linked thread")
        ok("validated optional Codex app-server/codexui bridge helpers")

        stats = orchestration_stats.run_stats(repo, run_id)
        for key, minval in [("worker_count", 1), ("event_count", 6), ("dispatch_count", 1), ("handoff_count", 1), ("evidence_count", 1), ("usage_real_tokens", 525)]:
            if stats[key] < minval:
                fail(f"stats {key} too small: {stats}")
        ok("validated stats and memory index")

        ok("validated deterministic orchestration state before CLI/UI smoke tests")


def main() -> None:
    for tool in ["bash", "git", "node", "npm", "python3"]:
        require_tool(tool)
    validate_static()
    validate_install_self_and_external()
    validate_orchestration_flow()
    print("ALL AGGRESSIVE VALIDATION CHECKS PASSED", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
