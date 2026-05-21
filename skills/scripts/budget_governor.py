#!/usr/bin/env python3
"""Static orchestration budget governor.

Uses simple cost points rather than real token accounting. The goal is to stop
obvious over-orchestration before subagents are spawned.
"""
from __future__ import annotations

import argparse
import json
import sys

EFFORT_POINTS = {"low": 1, "medium": 2, "high": 4, "xhigh": 8}
AGENT_BASE = 2
SIZE_BUDGET = {"XS": 4, "S": 7, "M": 16, "L": 28, "XL": 44}


def split_csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def estimate(agents: list[str], reasoning: str, size: str, browser: bool, full_matrix: bool) -> dict:
    effort = EFFORT_POINTS[reasoning]
    # Infer per-agent effort from name suffix where possible.
    score = 0
    detail = []
    for a in agents:
        r = "medium"
        for k in ["xhigh", "high", "medium", "low"]:
            if a.endswith("_" + k) or a.endswith("-" + k):
                r = k
                break
        pts = AGENT_BASE + EFFORT_POINTS.get(r, effort)
        score += pts
        detail.append({"agent": a, "reasoning": r, "points": pts})
    if browser:
        score += 4
    if full_matrix:
        score += 5
    allowed = SIZE_BUDGET[size]
    return {"score": score, "budget": allowed, "status": "OKAY" if score <= allowed else "OVER_BUDGET", "detail": detail}


def main() -> None:
    ap = argparse.ArgumentParser(description="Check orchestration fan-out against a token-cost budget")
    ap.add_argument("--size", choices=list(SIZE_BUDGET), required=True)
    ap.add_argument("--agents", required=True, help="Comma-separated agent names")
    ap.add_argument("--reasoning", choices=list(EFFORT_POINTS), default="medium")
    ap.add_argument("--browser", action="store_true")
    ap.add_argument("--full-matrix", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = estimate(split_csv(args.agents), args.reasoning, args.size, args.browser, args.full_matrix)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['status']}: score {result['score']} / budget {result['budget']}")
        for d in result["detail"]:
            print(f"- {d['agent']}: {d['reasoning']} -> {d['points']} points")
        if result["status"] == "OVER_BUDGET":
            print("Recommendation: merge batches, downgrade reasoning, or run phases serially.")
    sys.exit(1 if result["status"] == "OVER_BUDGET" else 0)


if __name__ == "__main__":
    main()
