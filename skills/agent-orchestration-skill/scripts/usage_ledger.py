#!/usr/bin/env python3
"""Local usage ledger for orchestration runs.

This script is inspired by local-first usage analyzers such as ccusage, but it
is scoped to this orchestration layer. It keeps three concepts separate:

1. estimated orchestration pressure derived from local artifacts;
2. imported real usage from external tools such as ccusage JSON;
3. manually recorded usage from wrappers or future integrations.

It never uploads data and never parses private prompts unless they were already
written into orchestration artifacts by the user/skill.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import latest_run_id, read_json, run_dir, state_path, write_json_atomic  # noqa: E402

USAGE_SCHEMA = "agent_orchestration_usage_event"
SUMMARY_SCHEMA = "agent_orchestration_usage_summary"
CHAR_TOKEN_DIVISOR = 4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def orchestration_dir(root: Path) -> Path:
    return root / ".orchestration"


def usage_dir(root: Path) -> Path:
    return orchestration_dir(root) / "usage"


def usage_jsonl(root: Path) -> Path:
    return usage_dir(root) / "usage.jsonl"


def usage_summary_path(root: Path, run_id: str) -> Path:
    return run_dir(root, run_id) / "usage.json"


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def parse_iso_day(ts: str | None) -> str:
    if not ts:
        return "unknown"
    return str(ts)[:10]


def to_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:
        return default


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def tree_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def sum_sizes(paths: Iterable[Path]) -> int:
    return sum(file_size(p) for p in paths)


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


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out.setdefault("schema", USAGE_SCHEMA)
    out.setdefault("ts", utc_now())
    out.setdefault("source", "manual")
    out["input_tokens"] = to_int(out.get("input_tokens"))
    out["output_tokens"] = to_int(out.get("output_tokens"))
    out["reasoning_output_tokens"] = to_int(out.get("reasoning_output_tokens"))
    out["cached_input_tokens"] = to_int(out.get("cached_input_tokens"))
    out["cache_creation_tokens"] = to_int(out.get("cache_creation_tokens"))
    out["estimated_tokens"] = to_int(out.get("estimated_tokens"))
    out["cost_usd"] = to_float(out.get("cost_usd"))
    if out.get("total_tokens") in (None, ""):
        # Use explicit total when imported tools provide it; otherwise compute a conservative sum.
        out["total_tokens"] = (
            out["input_tokens"]
            + out["output_tokens"]
            + out["reasoning_output_tokens"]
            + out["cached_input_tokens"]
            + out["cache_creation_tokens"]
        )
    else:
        out["total_tokens"] = to_int(out.get("total_tokens"))
    return out


def append_usage(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    rec = normalize_record(record)
    append_jsonl(usage_jsonl(root), rec)
    rid = rec.get("run_id")
    if rid:
        append_jsonl(run_dir(root, str(rid)) / "usage.jsonl", rec)
    return rec


def load_records(root: Path, run_id: str | None = None) -> list[dict[str, Any]]:
    paths = [usage_jsonl(root)]
    if run_id:
        paths.insert(0, run_dir(root, run_id) / "usage.jsonl")
    seen: set[tuple[str, str, str]] = set()
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if run_id and obj.get("run_id") not in (None, "", run_id):
                continue
            key = (str(obj.get("ts", "")), str(obj.get("source", "")), str(obj.get("session_id") or obj.get("run_id") or i))
            if key in seen:
                continue
            seen.add(key)
            records.append(normalize_record(obj))
    records.sort(key=lambda r: str(r.get("ts") or ""))
    return records


def derive_from_run(root: Path, run_id: str) -> dict[str, Any]:
    rd = run_dir(root, run_id)
    state = read_json(state_path(root, run_id), {})
    events = load_events(rd)
    dispatch_files = tree_files(rd / "dispatches")
    handoff_files = tree_files(rd / "handoffs")
    evidence_files = tree_files(rd / "evidence")
    capsule_candidates = [rd / "context_capsule.json", orchestration_dir(root) / "context_capsule.json"]
    capsule_chars = 0
    for cp in capsule_candidates:
        if cp.exists():
            capsule_chars = file_size(cp)
            break
    dispatch_chars = sum_sizes(dispatch_files)
    handoff_chars = sum_sizes(handoff_files)
    evidence_chars = sum_sizes(evidence_files)
    event_chars = file_size(rd / "events.jsonl")

    # Only a slice of the capsule should be prompt payload. Count 25% as pressure.
    estimated_prompt_tokens = math.ceil((dispatch_chars + capsule_chars * 0.25) / CHAR_TOKEN_DIVISOR)
    estimated_output_tokens = math.ceil(handoff_chars / CHAR_TOKEN_DIVISOR)
    estimated_evidence_tokens = math.ceil((evidence_chars + event_chars * 0.1) / CHAR_TOKEN_DIVISOR)
    estimated_total = estimated_prompt_tokens + estimated_output_tokens + estimated_evidence_tokens
    reasoning_counts = Counter(str(e.get("reasoning")) for e in events if e.get("reasoning"))
    agent_counts = Counter(str(e.get("agent")) for e in events if e.get("agent"))
    token_fields = [
        "input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "cached_input_tokens",
        "cache_creation_tokens",
        "total_tokens",
        "cost_usd",
    ]
    embedded_actuals: dict[str, float] = {k: 0 for k in token_fields}
    for e in events:
        meta = e.get("metadata") if isinstance(e.get("metadata"), dict) else {}
        for k in token_fields:
            if k in e:
                embedded_actuals[k] += to_float(e.get(k))
            if k in meta:
                embedded_actuals[k] += to_float(meta.get(k))

    return normalize_record(
        {
            "ts": utc_now(),
            "source": "orchestration_estimate",
            "run_id": run_id,
            "session_id": run_id,
            "task": state.get("task", ""),
            "model": "unknown",
            "reasoning": ",".join(f"{k}:{v}" for k, v in sorted(reasoning_counts.items())) or "unknown",
            "estimated_tokens": estimated_total,
            "estimated_prompt_tokens": estimated_prompt_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_evidence_tokens": estimated_evidence_tokens,
            "dispatch_chars": dispatch_chars,
            "handoff_chars": handoff_chars,
            "evidence_chars": evidence_chars,
            "context_capsule_chars": capsule_chars,
            "event_chars": event_chars,
            "event_count": len(events),
            "worker_count": len(agent_counts),
            "agents": dict(agent_counts),
            "input_tokens": int(embedded_actuals["input_tokens"]),
            "output_tokens": int(embedded_actuals["output_tokens"]),
            "reasoning_output_tokens": int(embedded_actuals["reasoning_output_tokens"]),
            "cached_input_tokens": int(embedded_actuals["cached_input_tokens"]),
            "cache_creation_tokens": int(embedded_actuals["cache_creation_tokens"]),
            "total_tokens": int(embedded_actuals["total_tokens"]),
            "cost_usd": float(embedded_actuals["cost_usd"]),
        }
    )


def aggregate(records: list[dict[str, Any]], group_by: str = "session") -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}

    def group_key(r: dict[str, Any]) -> str:
        if group_by == "daily":
            return parse_iso_day(str(r.get("ts") or ""))
        if group_by == "agent":
            return str(r.get("agent") or "unknown")
        if group_by == "reasoning":
            return str(r.get("reasoning") or "unknown")
        if group_by == "source":
            return str(r.get("source") or "unknown")
        return str(r.get("run_id") or r.get("session_id") or "unknown")

    totals = {
        "records": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_tokens": 0,
        "total_tokens": 0,
        "estimated_tokens": 0,
        "cost_usd": 0.0,
    }
    for r in records:
        key = group_key(r)
        g = groups.setdefault(
            key,
            {
                "key": key,
                "records": 0,
                "sources": Counter(),
                "models": Counter(),
                "input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
                "cached_input_tokens": 0,
                "cache_creation_tokens": 0,
                "total_tokens": 0,
                "estimated_tokens": 0,
                "cost_usd": 0.0,
            },
        )
        g["records"] += 1
        g["sources"][str(r.get("source") or "unknown")] += 1
        if r.get("model"):
            g["models"][str(r.get("model"))] += 1
        for k in ["input_tokens", "output_tokens", "reasoning_output_tokens", "cached_input_tokens", "cache_creation_tokens", "total_tokens", "estimated_tokens"]:
            val = to_int(r.get(k))
            g[k] += val
            totals[k] += val
        cost = to_float(r.get("cost_usd"))
        g["cost_usd"] += cost
        totals["cost_usd"] += cost
        totals["records"] += 1
    rows: list[dict[str, Any]] = []
    for g in groups.values():
        row = dict(g)
        row["sources"] = dict(row["sources"])
        row["models"] = dict(row["models"])
        row["cost_usd"] = round(float(row["cost_usd"]), 6)
        rows.append(row)
    rows.sort(key=lambda x: str(x.get("key")))
    totals["cost_usd"] = round(float(totals["cost_usd"]), 6)
    return {"schema": SUMMARY_SCHEMA, "generated_at": utc_now(), "group_by": group_by, "rows": rows, "totals": totals}


def print_report(summary: dict[str, Any]) -> None:
    rows = summary.get("rows") or []
    totals = summary.get("totals") or {}
    print(f"Usage report grouped by {summary.get('group_by')}")
    print("key                              real_tokens  est_tokens  input  output  reasoning  cache  cost_usd  sources")
    print("-" * 118)
    for r in rows:
        cache = to_int(r.get("cached_input_tokens")) + to_int(r.get("cache_creation_tokens"))
        sources = ",".join(sorted((r.get("sources") or {}).keys()))
        print(
            f"{str(r.get('key'))[:32]:32} "
            f"{to_int(r.get('total_tokens')):11d} "
            f"{to_int(r.get('estimated_tokens')):10d} "
            f"{to_int(r.get('input_tokens')):6d} "
            f"{to_int(r.get('output_tokens')):7d} "
            f"{to_int(r.get('reasoning_output_tokens')):9d} "
            f"{cache:6d} "
            f"{to_float(r.get('cost_usd')):8.4f} "
            f"{sources}"
        )
    print("-" * 118)
    cache_total = to_int(totals.get("cached_input_tokens")) + to_int(totals.get("cache_creation_tokens"))
    print(
        f"{'TOTAL':32} {to_int(totals.get('total_tokens')):11d} {to_int(totals.get('estimated_tokens')):10d} "
        f"{to_int(totals.get('input_tokens')):6d} {to_int(totals.get('output_tokens')):7d} "
        f"{to_int(totals.get('reasoning_output_tokens')):9d} {cache_total:6d} {to_float(totals.get('cost_usd')):8.4f}"
    )
    print("\nNote: est_tokens is orchestration pressure, not provider billing. real_tokens are imported/recorded when available.")


def statusline(root: Path, run_id: str) -> str:
    records = load_records(root, run_id)
    derived = derive_from_run(root, run_id)
    summary = aggregate(records, "session")
    totals = summary.get("totals") or {}
    real = to_int(totals.get("total_tokens"))
    est = to_int(totals.get("estimated_tokens")) + to_int(derived.get("estimated_tokens"))
    cost = to_float(totals.get("cost_usd"))
    state = read_json(state_path(root, run_id), {})
    workers = len(state.get("agents") or {}) if isinstance(state.get("agents"), dict) else 0
    return f"{run_id} | workers {workers} | real {real:,} tok | est pressure ~{est:,} tok | ${cost:.4f}"


def budget_check(summary: dict[str, Any], max_real_tokens: int | None, max_estimated_tokens: int | None, max_cost_usd: float | None) -> dict[str, Any]:
    totals = summary.get("totals") or {}
    failures: list[str] = []
    real = to_int(totals.get("total_tokens"))
    est = to_int(totals.get("estimated_tokens"))
    cost = to_float(totals.get("cost_usd"))
    if max_real_tokens is not None and real > max_real_tokens:
        failures.append(f"real_tokens {real} > max_real_tokens {max_real_tokens}")
    if max_estimated_tokens is not None and est > max_estimated_tokens:
        failures.append(f"estimated_tokens {est} > max_estimated_tokens {max_estimated_tokens}")
    if max_cost_usd is not None and cost > max_cost_usd:
        failures.append(f"cost_usd {cost:.4f} > max_cost_usd {max_cost_usd:.4f}")
    return {"status": "FAIL" if failures else "PASS", "failures": failures, "totals": totals}


def cmd_record(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or ""
    meta: dict[str, Any] = {}
    if args.metadata_json:
        meta = json.loads(args.metadata_json)
    rec = append_usage(
        root,
        {
            "source": args.source,
            "run_id": run_id or None,
            "session_id": args.session_id or run_id or None,
            "phase_id": args.phase_id,
            "agent": args.agent,
            "model": args.model,
            "reasoning": args.reasoning,
            "input_tokens": args.input_tokens,
            "output_tokens": args.output_tokens,
            "reasoning_output_tokens": args.reasoning_output_tokens,
            "cached_input_tokens": args.cached_input_tokens,
            "cache_creation_tokens": args.cache_creation_tokens,
            "total_tokens": args.total_tokens,
            "estimated_tokens": args.estimated_tokens,
            "cost_usd": args.cost_usd,
            "metadata": meta,
        },
    )
    print(json.dumps(rec, indent=2, ensure_ascii=False) if args.json else f"recorded {rec.get('source')} usage for {rec.get('run_id') or rec.get('session_id')}")


def cmd_derive(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or ""
    if not run_id:
        raise SystemExit("No orchestration run found.")
    rec = derive_from_run(root, run_id)
    if args.record:
        rec = append_usage(root, rec)
        usage_summary_path(root, run_id).parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(usage_summary_path(root, run_id), aggregate(load_records(root, run_id), "session"))
    print(json.dumps(rec, indent=2, ensure_ascii=False) if args.json else f"estimated pressure for {run_id}: ~{rec['estimated_tokens']:,} tokens")


def cmd_report(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or ""
    if args.derive and run_id:
        # Do not append by default; include a transient derived row in this report.
        records = load_records(root, run_id if args.scope_run else None)
        records.append(derive_from_run(root, run_id))
    else:
        records = load_records(root, run_id if args.scope_run and run_id else None)
    summary = aggregate(records, args.group_by)
    if args.write and run_id:
        write_json_atomic(usage_summary_path(root, run_id), summary)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print_report(summary)


def cmd_statusline(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or ""
    if not run_id:
        raise SystemExit("No orchestration run found.")
    print(statusline(root, run_id))


def cmd_budget(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_id = args.run_id
    if run_id == "latest":
        run_id = latest_run_id(root) or ""
    records = load_records(root, run_id if args.scope_run and run_id else None)
    if args.derive and run_id:
        records.append(derive_from_run(root, run_id))
    summary = aggregate(records, "session")
    result = budget_check(summary, args.max_real_tokens, args.max_estimated_tokens, args.max_cost_usd)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["status"])
        for f in result["failures"]:
            print(f"- {f}")
    if result["status"] != "PASS":
        raise SystemExit(2)


def main() -> None:
    ap = argparse.ArgumentParser(description="Track local orchestration usage and token pressure")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("record", help="Record actual or estimated usage manually")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--source", default="manual")
    p.add_argument("--session-id")
    p.add_argument("--phase-id")
    p.add_argument("--agent")
    p.add_argument("--model")
    p.add_argument("--reasoning")
    p.add_argument("--input-tokens", type=int, default=0)
    p.add_argument("--output-tokens", type=int, default=0)
    p.add_argument("--reasoning-output-tokens", type=int, default=0)
    p.add_argument("--cached-input-tokens", type=int, default=0)
    p.add_argument("--cache-creation-tokens", type=int, default=0)
    p.add_argument("--total-tokens", type=int)
    p.add_argument("--estimated-tokens", type=int, default=0)
    p.add_argument("--cost-usd", type=float, default=0.0)
    p.add_argument("--metadata-json")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("derive", help="Derive token-pressure estimate from run artifacts")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--record", action="store_true", help="Append derived estimate to usage ledger")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_derive)

    p = sub.add_parser("report", help="Aggregate usage records")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--group-by", choices=["session", "daily", "agent", "reasoning", "source"], default="session")
    p.add_argument("--scope-run", action="store_true", help="Only include records for selected run")
    p.add_argument("--derive", action="store_true", help="Include transient derived estimate for selected run")
    p.add_argument("--write", action="store_true", help="Write run usage summary JSON")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("statusline", help="Print a compact usage status line")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.set_defaults(func=cmd_statusline)

    p = sub.add_parser("budget", help="Fail if usage exceeds given thresholds")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", default="latest")
    p.add_argument("--scope-run", action="store_true")
    p.add_argument("--derive", action="store_true")
    p.add_argument("--max-real-tokens", type=int)
    p.add_argument("--max-estimated-tokens", type=int)
    p.add_argument("--max-cost-usd", type=float)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_budget)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
