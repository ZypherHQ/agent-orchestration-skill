#!/usr/bin/env python3
"""Compute compact orchestration statistics for the control room."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import latest_run_id, read_json, run_dir, state_path  # noqa: E402
from usage_ledger import aggregate as usage_aggregate, derive_from_run, load_records  # noqa: E402


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def size_of_files(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return total


def load_events(rd: Path) -> list[dict[str, Any]]:
    p = rd / "events.jsonl"
    out: list[dict[str, Any]] = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def run_stats(root: Path, run_id: str) -> dict[str, Any]:
    state = read_json(state_path(root, run_id), {})
    rd = run_dir(root, run_id)
    events = load_events(rd)
    agents = state.get("agents") if isinstance(state.get("agents"), dict) else {}
    event_counts = Counter(str(e.get("event", "unknown")) for e in events)
    status_counts = Counter(str(e.get("status", "unknown")) for e in events if e.get("status"))
    reasoning_counts = Counter(str(e.get("reasoning")) for e in events if e.get("reasoning"))
    started = parse_dt(state.get("created_at"))
    ended = parse_dt(state.get("updated_at"))
    duration = int((ended - started).total_seconds()) if started and ended else 0
    dispatches = sorted((rd / "dispatches").glob("**/*")) if (rd / "dispatches").exists() else []
    handoffs = sorted((rd / "handoffs").glob("**/*")) if (rd / "handoffs").exists() else []
    evidence = sorted((rd / "evidence").glob("**/*")) if (rd / "evidence").exists() else []
    dispatch_files = [p for p in dispatches if p.is_file()]
    handoff_files = [p for p in handoffs if p.is_file()]
    evidence_files = [p for p in evidence if p.is_file()]
    capsule_candidates = [rd / "context_capsule.json", root / ".orchestration" / "context_capsule.json"]
    capsule_size = 0
    for cp in capsule_candidates:
        if cp.exists():
            capsule_size = cp.stat().st_size
            break
    largest_dispatch = max([p.stat().st_size for p in dispatch_files], default=0)
    # Conservative token pressure proxy. This is not billed usage.
    token_pressure_estimate = round((size_of_files(dispatch_files) + size_of_files(handoff_files) + capsule_size * 0.25) / 4)
    try:
        usage_records = load_records(root, run_id)
        usage_records_with_estimate = usage_records + [derive_from_run(root, run_id)]
        usage_summary = usage_aggregate(usage_records_with_estimate, "session")
    except Exception:
        usage_summary = {"totals": {}}
    usage_totals = usage_summary.get("totals", {}) if isinstance(usage_summary, dict) else {}
    return {
        "run_id": run_id,
        "task": state.get("task", ""),
        "status": state.get("status", "unknown"),
        "duration_seconds": duration,
        "worker_count": len(agents),
        "agents": sorted(agents.keys()),
        "event_count": len(events),
        "event_counts": dict(event_counts),
        "status_counts": dict(status_counts),
        "reasoning_counts": dict(reasoning_counts),
        "dispatch_count": len(dispatch_files),
        "handoff_count": len(handoff_files),
        "evidence_count": len(evidence_files),
        "dispatch_chars_total": size_of_files(dispatch_files),
        "handoff_chars_total": size_of_files(handoff_files),
        "largest_dispatch_chars": largest_dispatch,
        "context_capsule_chars": capsule_size,
        "token_pressure_estimate": token_pressure_estimate,
        "usage_real_tokens": usage_totals.get("total_tokens", 0),
        "usage_estimated_tokens": usage_totals.get("estimated_tokens", token_pressure_estimate),
        "usage_cost_usd": usage_totals.get("cost_usd", 0.0),
        "usage_records": usage_totals.get("records", 0),
        "failures": event_counts.get("verification_failed", 0) + event_counts.get("handoff_rejected", 0) + event_counts.get("plan_gate_rejected", 0),
        "retries": event_counts.get("retry_scheduled", 0),
        "replans": event_counts.get("replan_requested", 0),
    }


def print_table(stats: dict[str, Any]) -> None:
    print(f"Run: {stats['run_id']}")
    print(f"Task: {stats['task']}")
    print(f"Status: {stats['status']} | Duration: {stats['duration_seconds']}s | Workers: {stats['worker_count']}")
    print(f"Events: {stats['event_count']} | Dispatches: {stats['dispatch_count']} | Handoffs: {stats['handoff_count']} | Evidence: {stats['evidence_count']}")
    print(f"Largest dispatch: {stats['largest_dispatch_chars']} chars | Capsule: {stats['context_capsule_chars']} chars")
    print(f"Estimated token pressure: ~{stats['token_pressure_estimate']} tokens (proxy, not billing)")
    print(f"Usage ledger: real={stats.get('usage_real_tokens', 0)} tokens | estimated={stats.get('usage_estimated_tokens', 0)} tokens | cost=${stats.get('usage_cost_usd', 0.0):.4f} | records={stats.get('usage_records', 0)}")
    if stats["reasoning_counts"]:
        print("Reasoning mix:")
        for k, v in sorted(stats["reasoning_counts"].items()):
            print(f"- {k}: {v}")
    if stats["event_counts"]:
        print("Top events:")
        for k, v in sorted(stats["event_counts"].items(), key=lambda x: (-x[1], x[0]))[:10]:
            print(f"- {k}: {v}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute orchestration run statistics")
    ap.add_argument("--root", default=".")
    ap.add_argument("--run-id", default="latest")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or ""
    if not run_id:
        raise SystemExit("No orchestration run found.")
    stats = run_stats(root, run_id)
    if args.json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print_table(stats)


if __name__ == "__main__":
    main()
