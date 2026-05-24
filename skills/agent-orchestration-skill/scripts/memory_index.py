#!/usr/bin/env python3
"""Build and search a lightweight inspectable memory index."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from event_emit import emit_event, latest_run_id, read_json, run_dir, utc_now, write_json_atomic  # noqa: E402

MAX_SEARCH_FILE_BYTES = 1_000_000


def text_excerpt(text: str, n: int = 220) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= n else compact[: n - 1] + "…"


def rel_path(path: Path, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def add_doc(docs: list[dict[str, Any]], path: Path, root: Path, kind: str, run_id: str | None = None) -> None:
    if not path.exists() or not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return
    docs.append({
        "path": rel_path(path, root),
        "kind": kind,
        "run_id": run_id or "",
        "chars": len(text),
        "updated_at": utc_now(),
        "excerpt": text_excerpt(text),
    })


def capsule_docs(path: Path, root: Path, docs: list[dict[str, Any]], run_id: str | None = None) -> None:
    if not path.exists():
        return
    try:
        capsule = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        add_doc(docs, path, root, "context_capsule_raw", run_id)
        return
    pieces = []
    for key in ["must_read", "forbidden", "confirmed_facts", "rejected_assumptions", "decisions", "acceptance_criteria", "validation_commands", "blockers", "evidence_refs"]:
        values = capsule.get(key) or []
        if values:
            pieces.append(f"{key}: " + "; ".join(str(v.get('path') or v.get('value') or v) if isinstance(v, dict) else str(v) for v in values[:8]))
    docs.append({
        "path": rel_path(path, root),
        "kind": "context_capsule",
        "run_id": run_id or capsule.get("run_id", ""),
        "chars": path.stat().st_size,
        "updated_at": capsule.get("updated_at", utc_now()),
        "excerpt": text_excerpt(" | ".join(pieces) or capsule.get("task", "")),
    })


def native_run_docs(root: Path, run_id: str | None = None) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    if run_id:
        run_dirs = [run_dir(root, run_id)]
    else:
        run_dirs = [sp.parent for sp in sorted((root / ".orchestration" / "runs").glob("*/state.json"))]
    for rd in run_dirs:
        rid = rd.name
        add_doc(docs, rd / "state.json", root, "aoc_state", rid)
        add_doc(docs, rd / "events.jsonl", root, "aoc_events", rid)
    return docs


def doc_key(doc: dict[str, Any]) -> tuple[str, str, str]:
    return (str(doc.get("path", "")), str(doc.get("kind", "")), str(doc.get("run_id", "")))


def doc_file_text(root: Path, doc: dict[str, Any]) -> str:
    raw = str(doc.get("path") or "")
    if not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    try:
        if not path.is_file() or path.stat().st_size > MAX_SEARCH_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def build_index(root: Path, run_id: str | None = None) -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    orch = root / ".orchestration"
    # Global durable memory.
    for p in sorted((orch / "notepads").glob("**/*.md")):
        add_doc(docs, p, root, "notepad")
    for p in sorted((orch / "memory" / "wiki").glob("**/*.md")):
        add_doc(docs, p, root, "wiki")
    capsule_docs(orch / "context_capsule.json", root, docs)
    # Run-scoped artifacts.
    run_ids: list[str] = []
    if run_id:
        run_ids = [run_id]
    else:
        for sp in sorted((orch / "runs").glob("*/state.json")):
            run_ids.append(sp.parent.name)
    for rid in run_ids:
        rd = run_dir(root, rid)
        add_doc(docs, rd / "state.json", root, "aoc_state", rid)
        add_doc(docs, rd / "events.jsonl", root, "aoc_events", rid)
        capsule_docs(rd / "context_capsule.json", root, docs, rid)
        for sub, kind in [("handoffs", "handoff"), ("dispatches", "dispatch"), ("evidence", "evidence"), ("logs", "log")]:
            for p in sorted((rd / sub).glob("**/*")):
                if p.is_file() and p.stat().st_size <= 200_000:
                    add_doc(docs, p, root, kind, rid)
    index = {"schema": "agent_orchestration_memory_index", "updated_at": utc_now(), "doc_count": len(docs), "docs": docs}
    out = orch / "memory" / "index.json"
    write_json_atomic(out, index)
    emit_event(root, "memory_index_built", run_id=run_id, status="ok", summary=f"Indexed {len(docs)} memory/evidence docs", update_state=bool(run_id))
    return index


def search_index(root: Path, query: str, limit: int = 10) -> list[dict[str, Any]]:
    path = root / ".orchestration" / "memory" / "index.json"
    idx = read_json(path, {})
    if not isinstance(idx, dict) or not idx.get("docs"):
        idx = build_index(root)
    terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9_./-]{2,}", query)]
    docs_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for doc in idx.get("docs", []):
        if isinstance(doc, dict):
            docs_by_key[doc_key(doc)] = doc
    for doc in native_run_docs(root):
        docs_by_key[doc_key(doc)] = doc
    rows = []
    for doc in docs_by_key.values():
        blob = " ".join(
            [
                " ".join(str(doc.get(k, "")) for k in ["path", "kind", "run_id", "excerpt"]),
                doc_file_text(root, doc),
            ]
        ).lower()
        score = sum(1 for t in terms if t in blob)
        if score or not terms:
            d = dict(doc)
            d["score"] = score
            rows.append(d)
    rows.sort(key=lambda d: (-d["score"], d.get("updated_at", "")), reverse=False)
    return rows[:limit]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build/search orchestration memory index")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", help="Limit to a run ID or latest")
    p.add_argument("--json", action="store_true")
    p.set_defaults(cmd_func="build")
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--root", default=".")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(cmd_func="search")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.cmd_func == "build":
        rid = args.run_id
        if rid == "latest":
            rid = latest_run_id(root)
        idx = build_index(root, rid)
        if args.json:
            print(json.dumps(idx, indent=2, ensure_ascii=False))
        else:
            print(f"Indexed {idx['doc_count']} memory/evidence document(s).")
    else:
        rows = search_index(root, args.query, args.limit)
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            if not rows:
                print("No memory hits.")
            for r in rows:
                print(f"{r.get('score', 0):>2} | {r.get('kind'):10} | {r.get('path')} | {r.get('excerpt')}")


if __name__ == "__main__":
    main()
