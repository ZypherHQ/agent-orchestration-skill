#!/usr/bin/env python3
"""Merge concise subagent Handoff Packets and detect conflicts."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

FILE_RX = re.compile(r"(?:^|[\s`'\"(])([\w./-]+\.(?:mjs|cjs|sh|ts|tsx|js|jsx|py|go|rs|java|kt|php|rb|json|toml|ya?ml|css|scss|md|sql|prisma))(?:[\s`'\",):]|$)")
STRUCTURED_FILE_KEYS = {
    "files",
    "files_changed",
    "files_examined",
    "files_read",
    "files_touched",
    "files_touched_or_examined",
}


def extract_files(text: str) -> set[str]:
    return extract_structured_files(text) | {m.group(1).strip("`'\" ,)") for m in FILE_RX.finditer(text)}


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def files_from_value(value: str) -> set[str]:
    return {m.group(1).strip("`'\" ,)") for m in FILE_RX.finditer(value)}


def extract_structured_files(text: str) -> set[str]:
    files: set[str] = set()
    try:
        payload = json.loads(text)
    except Exception:
        payload = None
    if isinstance(payload, dict):
        for key, value in payload.items():
            if normalize_key(str(key)) in STRUCTURED_FILE_KEYS:
                files.update(files_from_structured_value(value))

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = re.match(r"^(\s*)([A-Za-z][A-Za-z0-9_ -]*):\s*(.*)$", lines[i])
        if not match or normalize_key(match.group(2)) not in STRUCTURED_FILE_KEYS:
            i += 1
            continue
        base_indent = len(match.group(1))
        remainder = match.group(3).strip()
        files.update(files_from_value(remainder))
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent and re.match(r"^\s*[A-Za-z][A-Za-z0-9_ -]*:", line):
                break
            files.update(files_from_value(line))
            i += 1
    return files


def files_from_structured_value(value) -> set[str]:
    if isinstance(value, str):
        return files_from_value(value)
    if isinstance(value, list):
        out: set[str] = set()
        for item in value:
            out.update(files_from_structured_value(item))
        return out
    if isinstance(value, dict):
        out: set[str] = set()
        for key, inner in value.items():
            if normalize_key(str(key)) in {"path", "file", "filename"}:
                out.update(files_from_value(str(inner)))
            else:
                out.update(files_from_structured_value(inner))
        return out
    return set()


def main() -> None:
    ap = argparse.ArgumentParser(description="Route multiple Handoff Packets.")
    ap.add_argument("packets", nargs="+", help="Markdown/text files containing handoff packets")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--enforce", action="store_true", help="Exit nonzero when file ownership conflicts are detected")
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
    if args.enforce and conflicts:
        sys.exit(1)

if __name__ == "__main__":
    main()
