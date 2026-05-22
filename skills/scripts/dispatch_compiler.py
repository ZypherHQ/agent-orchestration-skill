#!/usr/bin/env python3
"""Compile a scoped, token-capped Dispatch Packet for a Codex leaf worker.

The Context Capsule is persistent storage, not prompt payload. This compiler
extracts only the smallest relevant capsule slice for the assigned worker.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FIELDS = [
    "role", "reasoning", "objective", "scope", "focus", "must_read", "allowed", "forbidden",
    "context", "confirmed", "rejected", "decisions", "tasks", "acceptance",
    "validation", "stop", "output",
]

DEFAULT_LIMITS = {
    "must_read": 8,
    "allowed": 8,
    "forbidden": 6,
    "confirmed": 5,
    "rejected": 3,
    "decisions": 3,
    "tasks": 8,
    "acceptance": 5,
    "validation": 4,
}
DEFAULT_CONTEXT_CHARS = 900
DEFAULT_ITEM_CHARS = 220
DEFAULT_PACKET_CHARS = 7000


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def short_text(value: Any, max_chars: int = DEFAULT_ITEM_CHARS) -> str:
    text = " ".join(str(value).strip().split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def item_to_text(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("path") and value.get("reason"):
            return f"{value['path']} — {value['reason']}"
        if value.get("path"):
            return str(value["path"])
        if value.get("value"):
            return str(value["value"])
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def split_items(value: str | list | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            text = short_text(item_to_text(v))
            if text:
                out.append(text)
        return out
    return [short_text(x) for x in str(value).split(";") if x.strip()]


def unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        norm = re.sub(r"\s+", " ", item).strip().lower()
        if norm and norm not in seen:
            out.append(item)
            seen.add(norm)
    return out


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9_./-]{3,}", text.lower()) if not t.startswith("http")}


def build_focus_terms(data: dict[str, Any]) -> set[str]:
    focus_blob = "\n".join(
        str(data.get(k, ""))
        for k in ["focus", "role", "objective", "scope", "tasks", "must_read", "allowed", "context"]
    )
    terms = tokenize(focus_blob)
    # Add basenames for path-like terms so app/cart/page.tsx also matches page.tsx.
    for term in list(terms):
        if "/" in term:
            terms.add(Path(term).name.lower())
    return terms


def relevance_sort(items: list[str], focus_terms: set[str]) -> list[str]:
    if not items or not focus_terms:
        return items

    def score(pair: tuple[int, str]) -> tuple[int, int]:
        idx, text = pair
        lower = text.lower()
        direct = sum(1 for t in focus_terms if t in lower)
        path_bonus = 1 if any(Path(t).name and Path(t).name in lower for t in focus_terms if "/" in t) else 0
        return (direct + path_bonus, -idx)

    scored = list(enumerate(items))
    scored.sort(key=score, reverse=True)
    # Keep relevant items first. If nothing scores, original order is preserved.
    if score(scored[0])[0] == 0:
        return items
    relevant = [text for idx, text in scored if score((idx, text))[0] > 0]
    fallback = [text for idx, text in sorted(scored) if score((idx, text))[0] == 0]
    return relevant + fallback




def filter_relevant_if_possible(items: list[str], focus_terms: set[str]) -> list[str]:
    if not items or not focus_terms:
        return items
    relevant: list[str] = []
    for text in items:
        lower = text.lower()
        if any(t in lower for t in focus_terms):
            relevant.append(text)
    return relevant if relevant else items


def capped_merge(explicit: list[str], capsule_items: list[str], cap: int, focus_terms: set[str]) -> list[str]:
    explicit = unique(explicit)[:cap]
    remaining = cap - len(explicit)
    if remaining <= 0:
        return explicit
    capsule_items = filter_relevant_if_possible(unique(capsule_items), focus_terms)
    capsule_items = relevance_sort(capsule_items, focus_terms)
    additions = [x for x in capsule_items if x.lower() not in {e.lower() for e in explicit}]
    return explicit + additions[:remaining]


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- None specified"


def capsule_digest(capsule: dict[str, Any]) -> dict[str, list[str] | str]:
    return {
        "task": short_text(capsule.get("task", ""), 300),
        "goal": short_text(capsule.get("parent_goal", ""), 300),
        "must_read": split_items(capsule.get("must_read")),
        "optional": split_items(capsule.get("useful_optional")),
        "forbidden": split_items(capsule.get("forbidden")),
        "confirmed": split_items(capsule.get("confirmed_facts")),
        "rejected": split_items(capsule.get("rejected_assumptions")),
        "decisions": split_items(capsule.get("decisions")),
        "ownership": split_items(capsule.get("ownership")),
        "acceptance": split_items(capsule.get("acceptance_criteria")),
        "validation": split_items(capsule.get("validation_commands")),
    }


def merge_capsule(
    data: dict[str, Any],
    capsule_path: str | None,
    limits: dict[str, int] | None = None,
    max_context_chars: int = DEFAULT_CONTEXT_CHARS,
) -> dict[str, Any]:
    if not capsule_path:
        return data
    limits = limits or DEFAULT_LIMITS
    raw_capsule = load_json(capsule_path)
    c = capsule_digest(raw_capsule)
    data = dict(data)
    focus_terms = build_focus_terms(data)

    for src, dst in [
        ("must_read", "must_read"),
        ("forbidden", "forbidden"),
        ("confirmed", "confirmed"),
        ("rejected", "rejected"),
        ("decisions", "decisions"),
        ("acceptance", "acceptance"),
        ("validation", "validation"),
    ]:
        explicit_items = split_items(data.get(dst))
        # Explicit must_read entries define the scoped coverage contract.
        # Do not silently expand them from the full capsule, or every worker
        # inherits unrelated context and token cost.
        if dst == "must_read" and explicit_items:
            data[dst] = unique(explicit_items)[: limits.get(dst, DEFAULT_LIMITS[dst])]
            continue
        section_terms = set() if dst == "forbidden" else focus_terms
        data[dst] = capped_merge(
            explicit_items,
            split_items(c.get(src)),
            limits.get(dst, DEFAULT_LIMITS.get(dst, 4)),
            section_terms,
        )

    # Optional context and ownership are not broadcast as lists. They are summarized
    # in a tiny pointer so workers know the capsule exists but do not load unrelated data.
    ctx_lines: list[str] = []
    if data.get("context"):
        ctx_lines.append(short_text(data["context"], 350))
    ctx_lines.append(f"Capsule source: {capsule_path}")
    if c.get("task"):
        ctx_lines.append(f"Task: {c['task']}")
    if c.get("goal"):
        ctx_lines.append(f"Goal: {c['goal']}")
    if data.get("focus"):
        ctx_lines.append(f"Slice focus: {short_text(data['focus'], 180)}")
    ctx_lines.append("Policy: capsule stays on disk; use only this scoped slice unless missing context blocks progress.")
    ownership = relevance_sort(split_items(c.get("ownership")), focus_terms)[:2]
    if ownership:
        ctx_lines.append("Relevant ownership: " + "; ".join(ownership))
    optional = relevance_sort(split_items(c.get("optional")), focus_terms)[:2]
    if optional:
        ctx_lines.append("Optional if blocked: " + "; ".join(optional))
    context = "\n".join(ctx_lines)
    if len(context) > max_context_chars:
        context = context[: max_context_chars - 1].rstrip() + "…"
    data["context"] = context
    data["_capsule_stats"] = {
        "source": capsule_path,
        "must_read_total": len(split_items(c.get("must_read"))),
        "facts_total": len(split_items(c.get("confirmed"))),
        "included_limits": limits,
        "included_context_chars": len(context),
    }
    return data


def cap_data(data: dict[str, Any], limits: dict[str, int], max_context_chars: int) -> dict[str, Any]:
    out = dict(data)
    for key, cap in limits.items():
        out[key] = unique(split_items(out.get(key)))[:cap]
    context = str(out.get("context", "No extra context provided."))
    if len(context) > max_context_chars:
        context = context[: max_context_chars - 1].rstrip() + "…"
    out["context"] = context
    return out


def packet(data: dict[str, Any], limits: dict[str, int] | None = None, max_context_chars: int = DEFAULT_CONTEXT_CHARS, max_packet_chars: int = DEFAULT_PACKET_CHARS) -> str:
    limits = limits or DEFAULT_LIMITS
    data = cap_data(data, limits, max_context_chars)
    role = data.get("role", "worker")
    reasoning = data.get("reasoning", "medium")
    objective = data.get("objective", "Complete the assigned scoped task.")
    scope = data.get("scope", "Only the files/areas listed in this packet.")
    must_read = split_items(data.get("must_read"))
    allowed = split_items(data.get("allowed"))
    forbidden = split_items(data.get("forbidden"))
    context = data.get("context", "No extra context provided.")
    confirmed = split_items(data.get("confirmed"))
    rejected = split_items(data.get("rejected"))
    decisions = split_items(data.get("decisions"))
    tasks = split_items(data.get("tasks"))
    acceptance = split_items(data.get("acceptance"))
    validation = split_items(data.get("validation"))
    stop = data.get("stop", "Stop if required context is missing, ownership overlaps another active writer, validation exposes unrelated failures, or the task would require broader scope than assigned.")
    output = data.get("output", "Return a concise Handoff Packet only: STATUS, SUMMARY, CONTEXT_COVERAGE, FILES_READ, FILES_CHANGED, CHANGES, VALIDATION, EVIDENCE, RISKS, PARENT_ACTION.")

    coverage = "Read every MUST READ item before editing. Report required_files_read, missing_context, and safe_to_modify. If anything required is unavailable, return ESCALATE_TO_PARENT instead of guessing."

    text = f"""ROLE:
{role}

MODE / REASONING BUDGET:
{reasoning}

OBJECTIVE:
{objective}

SCOPE OWNERSHIP:
{scope}

MUST READ BEFORE EDITING:
{bullets(must_read)}

FILES / AREAS ALLOWED:
{bullets(allowed)}

FILES / AREAS FORBIDDEN:
{bullets(forbidden)}

CONTEXT CAPSULE SLICE:
{context}

CONFIRMED FACTS:
{bullets(confirmed)}

REJECTED ASSUMPTIONS:
{bullets(rejected)}

DECISIONS / CONSTRAINTS:
{bullets(decisions)}

TASK BUNDLE:
{bullets(tasks)}

ACCEPTANCE CRITERIA:
{bullets(acceptance)}

VALIDATION REQUIRED:
{bullets(validation)}

CONTEXT COVERAGE CHECK:
{coverage}

STOP CONDITIONS:
{stop}

SKILL / DELEGATION POLICY:
Do not invoke repo skills. Do not invoke $agent-orchestration-skill. Do not spawn, request, recommend, or plan child subagents. Treat this Dispatch Packet as complete unless required context is missing.

OUTPUT:
{output}
"""
    return text


def parse_limits(args: argparse.Namespace) -> dict[str, int]:
    limits = dict(DEFAULT_LIMITS)
    for key in DEFAULT_LIMITS:
        value = getattr(args, f"max_{key}", None)
        if value is not None:
            limits[key] = value
    return limits


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a scoped, token-capped Dispatch Packet for a leaf worker.")
    ap.add_argument("--from-json", help="JSON file with packet fields")
    ap.add_argument("--capsule", help="Context Capsule JSON to slice into the packet")
    ap.add_argument("--max-context-chars", type=int, default=DEFAULT_CONTEXT_CHARS)
    ap.add_argument("--max-packet-chars", type=int, default=DEFAULT_PACKET_CHARS)
    ap.add_argument("--stats", action="store_true", help="Print compact JSON stats to stderr")
    ap.add_argument("--allow-oversize", action="store_true", help="Print oversized packet instead of failing")
    ap.add_argument("--strict", action="store_true", help="Fail if the packet lacks scoped must-read context")
    list_fields = {"must_read", "allowed", "forbidden", "confirmed", "rejected", "decisions", "tasks", "acceptance", "validation"}
    for f in FIELDS:
        if f in list_fields:
            ap.add_argument(f"--{f.replace('_', '-')}", dest=f, action="append", default=None)
        else:
            ap.add_argument(f"--{f.replace('_', '-')}", dest=f, default=None)
    for key, default in DEFAULT_LIMITS.items():
        ap.add_argument(f"--max-{key.replace('_', '-')}", dest=f"max_{key}", type=int, default=None, help=f"Max {key} items; default {default}")
    args = ap.parse_args()
    limits = parse_limits(args)
    data = load_json(args.from_json)
    for f in FIELDS:
        v = getattr(args, f)
        if v is not None:
            data[f] = v
    data = merge_capsule(data, args.capsule, limits=limits, max_context_chars=args.max_context_chars)
    if args.strict and not split_items(data.get("must_read")):
        print("Strict Dispatch Packet requires at least one scoped --must-read item.", file=sys.stderr)
        raise SystemExit(2)
    text = packet(data, limits=limits, max_context_chars=args.max_context_chars, max_packet_chars=args.max_packet_chars)
    over_budget = len(text) > args.max_packet_chars
    if args.stats:
        stats = {
            "chars": len(text),
            "limits": limits,
            "capsule": data.get("_capsule_stats"),
            "packet_budget": args.max_packet_chars,
            "status": "OKAY" if not over_budget else "OVER_BUDGET",
        }
        print(json.dumps(stats, indent=2), file=sys.stderr)
    if over_budget and not args.allow_oversize:
        print(
            f"Dispatch Packet exceeds token budget: {len(text)} > {args.max_packet_chars}. "
            "Use a narrower --focus, fewer must-read files, or lower section caps.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    sys.stdout.write(text)
    sys.stdout.flush()
    raise SystemExit(0)


if __name__ == "__main__":
    main()
