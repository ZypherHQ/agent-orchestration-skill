#!/usr/bin/env python3
"""Merge concise subagent Handoff Packets and detect conflicts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from collections import defaultdict

FILE_RX = re.compile(r"(?:^|[\s`])([\w./-]+\.(?:ts|tsx|js|jsx|py|go|rs|java|kt|php|rb|json|toml|ya?ml|css|scss|md|sql|prisma))(?:[\s`,]|$)")


def extract_files(text: str) -> set[str]:
    return {m.group(1).strip("` ,") for m in FILE_RX.finditer(text)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Route multiple Handoff Packets.")
    ap.add_argument("packets", nargs="+", help="Markdown/text files containing handoff packets")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    items = []
    owners = defaultdict(list)
    for p in args.packets:
        path = Path(p)
        text = path.read_text(encoding="utf-8")
        files = sorted(extract_files(text))
        item = {"packet": str(path), "files": files, "summary": text[:800]}
        items.append(item)
        for f in files:
            owners[f].append(str(path))
    conflicts = {f: ps for f, ps in owners.items() if len(ps) > 1}
    result = {"packets": items, "conflicts": conflicts, "packet_count": len(items)}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Packets: {len(items)}")
        if conflicts:
            print("\nFile ownership conflicts:")
            for f, ps in conflicts.items():
                print(f"- {f}: {', '.join(ps)}")
        else:
            print("No file ownership conflicts detected.")
        print("\nRouting digest:")
        for item in items:
            print(f"\n## {item['packet']}")
            if item['files']:
                print("Files: " + ", ".join(item['files']))
            print(item['summary'].replace("\n", " ")[:500])

if __name__ == "__main__":
    main()
