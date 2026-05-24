#!/usr/bin/env python3
"""Compatibility entry point for watching Codex sessions."""
from __future__ import annotations

import sys

from codex_session_cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1].startswith("-"):
        sys.argv.insert(1, "watch")
    main()
