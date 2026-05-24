#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "Usage: ./install.sh <repo>" >&2
  exit 1
fi
if [[ ! -d "$TARGET" ]]; then
  echo "Target does not exist: $TARGET" >&2
  exit 1
fi

require_cmd() {
  local cmd="$1" hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing dependency: $cmd. $hint" >&2
    exit 127
  fi
}

require_cmd bash "Install Bash and make sure bash is on PATH."
require_cmd python3 "Install Python 3 and make sure python3 is on PATH."

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$(cd "$TARGET" && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"
SKILL_NAME="agent-orchestration-skill"
SKILL_SRC="$SRC_DIR/skills/$SKILL_NAME"
SUBAGENT_SRC="$SRC_DIR/subagents"
SKILL_DST="$TARGET_DIR/skills/$SKILL_NAME"
SUBAGENT_DST="$TARGET_DIR/subagents"

if [[ ! -d "$SKILL_SRC" ]]; then
  echo "Missing bundled skill directory: $SKILL_SRC" >&2
  exit 1
fi
if [[ ! -d "$SUBAGENT_SRC" ]]; then
  echo "Missing bundled subagents directory: $SUBAGENT_SRC" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR/skills" "$TARGET_DIR/subagents" "$TARGET_DIR/.orchestration/bin"

real_or_empty() {
  if [[ -e "$1" ]]; then (cd "$1" 2>/dev/null && pwd) || realpath "$1"; fi
}

same_path() {
  local a="$1" b="$2"
  [[ -e "$a" && -e "$b" ]] || return 1
  [[ "$(realpath "$a")" == "$(realpath "$b")" ]]
}

BACKUP=""
backup_dir() {
  if [[ -z "$BACKUP" ]]; then
    BACKUP="$TARGET_DIR/.orchestration-backup-$TS"
    mkdir -p "$BACKUP"
  fi
  echo "$BACKUP"
}

move_to_backup() {
  local src="$1" rel="$2"
  [[ -e "$src" ]] || return 0
  local b
  b="$(backup_dir)"
  mkdir -p "$b/$(dirname "$rel")"
  mv "$src" "$b/$rel"
}

copy_dir_contents() {
  local src="$1" dst="$2"
  rm -rf "$dst"
  mkdir -p "$(dirname "$dst")"
  cp -a "$src" "$dst"
}

# Self-install guard: when installing into this package repo itself, the source skill is
# already the target skill. Never move it to a backup. This prevents the previous
# failure where `node bin/aoc.mjs install .` moved `skills/agent-orchestration-skill`
# into `.orchestration-backup-*` and broke subsequent commands.
if same_path "$SKILL_SRC" "$SKILL_DST"; then
  SELF_INSTALL=1
else
  SELF_INSTALL=0
fi

# Back up legacy hidden layouts. The supported production layout is:
#   skills/<skill-name>/
#   subagents/*.toml
if [[ -d "$TARGET_DIR/.skills" ]]; then
  move_to_backup "$TARGET_DIR/.skills" ".skills"
fi
if [[ -d "$TARGET_DIR/.agents/skills/$SKILL_NAME" ]]; then
  move_to_backup "$TARGET_DIR/.agents/skills/$SKILL_NAME" ".agents/skills/$SKILL_NAME"
fi
if [[ -d "$TARGET_DIR/.codex/agents" ]]; then
  mkdir -p "$(backup_dir)/.codex"
  cp -a "$TARGET_DIR/.codex/agents" "$(backup_dir)/.codex/agents"
fi

STALE_SKILLS=(
  agentic-orchestration-control
  subagent-brief-factory parallel-task-planner docs-research-context7 codebase-360-audit
  implementation-handoff-guard aggressive-verification-gate browser-qa-agent
  re-audit-regression-hunt pr-ready-finalizer subagent-communication-router
)
for s in "${STALE_SKILLS[@]}"; do
  if [[ -d "$TARGET_DIR/skills/$s" && "$s" != "$SKILL_NAME" ]]; then
    move_to_backup "$TARGET_DIR/skills/$s" "stale-skills/$s"
  fi
done

if [[ "$SELF_INSTALL" == "0" ]]; then
  if [[ -d "$SKILL_DST" ]]; then
    move_to_backup "$SKILL_DST" "skills/$SKILL_NAME"
  fi
  copy_dir_contents "$SKILL_SRC" "$SKILL_DST"
else
  echo "Self-install detected; preserving bundled skills/$SKILL_NAME source directory."
fi

# Install/refresh subagent configs. On self-install this is also the source, so skip.
if [[ -d "$SUBAGENT_DST" ]] && same_path "$SUBAGENT_SRC" "$SUBAGENT_DST"; then
  :
else
  mkdir -p "$SUBAGENT_DST"
  cp -a "$SUBAGENT_SRC/." "$SUBAGENT_DST/"
fi

cat > "$TARGET_DIR/.orchestration/bin/agentic-orchestration-control" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONTROL="$REPO_ROOT/skills/agent-orchestration-skill/bin/agentic-orchestration-control"
if [[ ! -x "$CONTROL" ]]; then
  echo "Missing executable wrapper: $CONTROL" >&2
  exit 1
fi
exec "$CONTROL" "$@"
SHIM
chmod +x "$TARGET_DIR/.orchestration/bin/agentic-orchestration-control"
cp "$TARGET_DIR/.orchestration/bin/agentic-orchestration-control" "$TARGET_DIR/.orchestration/bin/aoc"
cat > "$TARGET_DIR/.orchestration/bin/agentic-orchestration-gui" <<'GUI_SHIM'
#!/usr/bin/env bash
set -euo pipefail
CONTROL="$(dirname "${BASH_SOURCE[0]}")/agentic-orchestration-control"
if [[ ! -x "$CONTROL" ]]; then
  echo "Missing executable wrapper: $CONTROL" >&2
  exit 1
fi
exec "$CONTROL" gui "$@"
GUI_SHIM
cp "$TARGET_DIR/.orchestration/bin/agentic-orchestration-gui" "$TARGET_DIR/.orchestration/bin/aoc-gui"
cat > "$TARGET_DIR/.orchestration/bin/agentic-orchestration-usage" <<'USAGE_SHIM'
#!/usr/bin/env bash
set -euo pipefail
CONTROL="$(dirname "${BASH_SOURCE[0]}")/agentic-orchestration-control"
if [[ ! -x "$CONTROL" ]]; then
  echo "Missing executable wrapper: $CONTROL" >&2
  exit 1
fi
if [[ $# -eq 0 || "${1:-}" == -* ]]; then
  exec "$CONTROL" usage "$@"
else
  exec "$CONTROL" "$@"
fi
USAGE_SHIM
cp "$TARGET_DIR/.orchestration/bin/agentic-orchestration-usage" "$TARGET_DIR/.orchestration/bin/aoc-usage"
chmod +x "$TARGET_DIR/.orchestration/bin/agentic-orchestration-control" "$TARGET_DIR/.orchestration/bin/aoc" "$TARGET_DIR/.orchestration/bin/agentic-orchestration-gui" "$TARGET_DIR/.orchestration/bin/aoc-gui" "$TARGET_DIR/.orchestration/bin/agentic-orchestration-usage" "$TARGET_DIR/.orchestration/bin/aoc-usage"

# Ensure executable bits survive zip/unzip and WSL copies.
find "$SKILL_DST/bin" -maxdepth 1 -type f -exec chmod +x {} \; 2>/dev/null || true
find "$SKILL_DST/scripts" -type f -name '*.sh' -exec chmod +x {} \; 2>/dev/null || true

python3 - "$TARGET_DIR/AGENTS.md" <<'PYAGENTS'
import re, sys
from pathlib import Path
p = Path(sys.argv[1])
txt = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
txt = re.sub(r'<!-- BEGIN AGENT_ORCHESTRATION_SKILL_GATE -->.*?<!-- END AGENT_ORCHESTRATION_SKILL_GATE -->\s*', '', txt, flags=re.S)
for pat in [
    r'Every substantial coding task should use.*?\n',
    r'Use `\$agent-orchestration-skill` only when explicitly requested or when.*?\n',
    r'when the task clearly benefits from orchestration.*?\n',
]:
    txt = re.sub(pat, '', txt, flags=re.I)
block = r'''
<!-- BEGIN AGENT_ORCHESTRATION_SKILL_GATE -->
Agent Orchestration Skill gate:
Use `$agent-orchestration-skill` only when the user prompt contains that exact literal invocation. Do not invoke it implicitly for generic coding, testing, audit, debugging, or subagent tasks.

Normal mode: when the literal is absent, work normally. Do not create orchestration artifacts, run ledgers, context capsules, DAG plans, or skill-driven subagent workflows.

Leaf mode: if the prompt says `You are a subagent`, `verification subagent`, `worker`, `leaf worker`, `LEAF_EXEC_MODE`, `Run exactly these commands`, `Do not edit files`, or `Return only a YAML Handoff Packet`, do not invoke skills and do not spawn/request/recommend child agents. Execute only the bounded task and return only the requested packet.

Spawned workers are leaf workers: no skills, no nested subagents, no routing fields such as `target_agent` or `next_handoff`; return `ESCALATE_TO_PARENT` when blocked.
<!-- END AGENT_ORCHESTRATION_SKILL_GATE -->
'''.strip()
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text((txt.rstrip() + '\n\n' if txt.strip() else '') + block + '\n', encoding='utf-8')
PYAGENTS

python3 "$SKILL_DST/scripts/token_budget_linter.py" --root "$TARGET_DIR"

if [[ -n "$BACKUP" ]]; then
  echo "Backed up replaced legacy files to $BACKUP"
fi

echo "Installed agent orchestration skill into $TARGET_DIR"
echo "Skill directory: $TARGET_DIR/skills/agent-orchestration-skill"
echo "Subagents directory: $TARGET_DIR/subagents"
echo "Explicit invocation only: Use \$agent-orchestration-skill for this task."
echo "Control room TUI: cd $TARGET_DIR && .orchestration/bin/aoc"
echo "Control room GUI: cd $TARGET_DIR && .orchestration/bin/aoc gui"
echo "Usage report: cd $TARGET_DIR && .orchestration/bin/aoc usage"
