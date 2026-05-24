#!/usr/bin/env node
import { existsSync, chmodSync, rmSync, readdirSync, statSync, unlinkSync } from 'node:fs';
import { resolve, join } from 'node:path';

const root = resolve(new URL('..', import.meta.url).pathname);
const quiet = process.argv.includes('--quiet');
const files = [
  'bin/aoc.mjs',
  'install.sh',
  'tools/fix-permissions.mjs',
  'skills/agent-orchestration-skill/bin/agentic-orchestration-control',
  'skills/agent-orchestration-skill/bin/agentic-orchestration-gui',
  'skills/agent-orchestration-skill/bin/agentic-orchestration-usage',
  'skills/agent-orchestration-skill/bin/aoc',
  'skills/agent-orchestration-skill/bin/aoc-gui',
  'skills/agent-orchestration-skill/bin/aoc-usage',
  'skills/agent-orchestration-skill/scripts/codex_leaf_exec.sh'
];
let changed = 0;
for (const rel of files) {
  const path = join(root, rel);
  if (!existsSync(path)) continue;
  chmodSync(path, 0o755);
  changed += 1;
}

function cleanBytecode(dir) {
  if (!existsSync(dir)) return 0;
  let removed = 0;
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    let st;
    try { st = statSync(path); } catch { continue; }
    if (st.isDirectory()) {
      if (entry === '__pycache__') {
        rmSync(path, { recursive: true, force: true });
        removed += 1;
      } else if (!['node_modules', '.git', '.agents', '.codex', '.orchestration', 'dist'].includes(entry)) {
        removed += cleanBytecode(path);
      }
    } else if (entry.endsWith('.pyc') || entry.endsWith('.pyo')) {
      unlinkSync(path);
      removed += 1;
    }
  }
  return removed;
}
const removed = cleanBytecode(root);
if (!quiet) console.log(`Normalized executable permissions for ${changed} files; removed ${removed} Python bytecode artifacts.`);
