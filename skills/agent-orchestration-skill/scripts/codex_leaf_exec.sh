#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  cat >&2 <<'USAGE'
Usage:
  codex_leaf_exec.sh /path/to/repo '<prompt>'

Runs codex exec as a hard leaf worker by disabling multi-agent tools for this exec process.
USAGE
  exit 2
fi

REPO="$1"
shift

if [[ ! -d "$REPO" ]]; then
  echo "Target repo does not exist: $REPO" >&2
  exit 1
fi
if ! command -v codex >/dev/null 2>&1; then
  echo "Missing dependency: codex. Install the OpenAI Codex CLI and make sure codex is on PATH." >&2
  exit 127
fi

exec codex exec --cd "$REPO" --sandbox workspace-write \
  -c features.multi_agent=false \
  -c agents.max_depth=0 \
  -c agents.max_threads=1 \
  -c model_reasoning_effort=low \
  -c model_verbosity=low \
  -c model_reasoning_summary=none \
  "$@"
