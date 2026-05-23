#!/usr/bin/env python3
"""Static orchestration budget governor.

This is intentionally conservative. It stops obvious over-orchestration before
subagents are spawned: too many workers, too much reasoning, or oversized
Dispatch Packets.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

EFFORT_POINTS = {"low": 1, "medium": 2, "high": 4, "xhigh": 8}
AGENT_BASE = 2
SIZE_BUDGET = {"XS": 4, "S": 7, "M": 14, "L": 25, "XL": 40}
SIZE_AGENT_CAP = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 6}
DISPATCH_CHAR_UNIT = 1400


def split_csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def infer_reasoning(agent: str, fallback: str) -> str:
    for k in ["xhigh", "high", "medium", "low"]:
        if agent.endswith("_" + k) or agent.endswith("-" + k):
            return k
    return fallback


def estimate(
    agents: list[str],
    reasoning: str,
    size: str,
    browser: bool,
    full_matrix: bool,
    dispatch_chars: int = 0,
) -> dict:
    detail = []
    score = 0
    recommendations: list[str] = []
    for a in agents:
        r = infer_reasoning(a, reasoning)
        pts = AGENT_BASE + EFFORT_POINTS.get(r, EFFORT_POINTS[reasoning])
        # Scouting is useful but should stay cheap.
        if any(k in a for k in ["scout", "mapper", "researcher", "router", "finalizer"]):
            pts = min(pts, AGENT_BASE + EFFORT_POINTS["low"])
        score += pts
        detail.append({"agent": a, "reasoning": r, "points": pts})
    if browser:
        score += 4
    if full_matrix:
        score += 5
    if dispatch_chars:
        # Packet size is a repeated cost if broadcast to workers. Penalize it.
        score += max(0, math.ceil(dispatch_chars / DISPATCH_CHAR_UNIT) - 1)
    allowed = SIZE_BUDGET[size]
    hard_failures: list[str] = []
    if len(agents) > SIZE_AGENT_CAP[size]:
        hard_failures.append(f"Too many agents for {size}: {len(agents)} > {SIZE_AGENT_CAP[size]}")
        recommendations.append("Merge related work into one bundled worker or run phases serially.")
    if size in {"XS", "S", "M"} and any(infer_reasoning(a, reasoning) == "xhigh" for a in agents):
        hard_failures.append("xhigh is not allowed for XS/S/M orchestration.")
        recommendations.append("Use medium for normal writes, high for complex writes, and reserve xhigh for large read-only strategy.")
    if dispatch_chars > 7000:
        hard_failures.append(f"Dispatch Packet too large: {dispatch_chars} chars > 7000")
        recommendations.append("Pass a narrower Context Capsule slice instead of broadcasting full context.")
    if score > allowed:
        recommendations.append("Reduce fan-out, downgrade reasoning, remove redundant scout, or shorten dispatch packets.")
    status = "OKAY" if score <= allowed and not hard_failures else "OVER_BUDGET"
    return {
        "score": score,
        "budget": allowed,
        "status": status,
        "agent_cap": SIZE_AGENT_CAP[size],
        "detail": detail,
        "hard_failures": hard_failures,
        "recommendations": recommendations,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Check orchestration fan-out against a token-cost budget")
    ap.add_argument("--size", choices=list(SIZE_BUDGET), required=True)
    ap.add_argument("--agents", required=True, help="Comma-separated agent names")
    ap.add_argument("--reasoning", choices=list(EFFORT_POINTS), default="medium")
    ap.add_argument("--browser", action="store_true")
    ap.add_argument("--full-matrix", action="store_true")
    ap.add_argument("--dispatch-chars", type=int, default=0, help="Largest Dispatch Packet char count, if known")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = estimate(split_csv(args.agents), args.reasoning, args.size, args.browser, args.full_matrix, args.dispatch_chars)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['status']}: score {result['score']} / budget {result['budget']} | agent cap {result['agent_cap']}")
        for d in result["detail"]:
            print(f"- {d['agent']}: {d['reasoning']} -> {d['points']} points")
        for f in result["hard_failures"]:
            print(f"Hard stop: {f}")
        for r in result["recommendations"]:
            print(f"Recommendation: {r}")
    sys.exit(1 if result["status"] == "OVER_BUDGET" else 0)


if __name__ == "__main__":
    main()
