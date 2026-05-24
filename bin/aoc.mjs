#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { chmodSync, copyFileSync, existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PKG_ROOT = resolve(__dirname, '..');
const SKILL_DIR = join(PKG_ROOT, 'skills', 'agent-orchestration-skill');
const SCRIPTS = join(SKILL_DIR, 'scripts');
const INSTALL = join(PKG_ROOT, 'install.sh');
const COMMAND_CONTRACT_PATH = join(PKG_ROOT, 'tools', 'aoc.commands.json');

const originalArgv = process.argv.slice(2);
const invokedName = process.argv[1] ? process.argv[1].split(/[\\/]/).pop() : 'aoc';

const ROUTE_COMMANDS = new Set([
  'tui', 'control', 'dashboard', 'snapshot', 'gui', 'web', 'install', 'sessions', 'session',
  'current', 'use', 'import', 'watch', 'search', 'usage', 'report', 'statusline', 'budget',
  'ccusage', 'codex', 'codexui', 'init', 'new-run', 'publish-check', 'stats', 'events',
  'tail', 'memory', 'gates', 'gate', 'doctor', 'help', '-h', '--help', 'version', '-v', '--version'
]);

const SHIM_COMMANDS = new Set([
  'tui', 'control', 'dashboard', 'snapshot', 'gui', 'web', 'sessions', 'session', 'current',
  'use', 'import', 'watch', 'search', 'init', 'new-run', 'usage', 'report', 'statusline',
  'budget', 'ccusage', 'codex', 'codexui', 'publish-check', 'stats', 'events', 'tail',
  'memory', 'gates', 'gate', 'doctor', 'help', '-h', '--help', 'version', '--version', '-v'
]);

function loadCommandContract() {
  try {
    return JSON.parse(readFileSync(COMMAND_CONTRACT_PATH, 'utf8'));
  } catch (err) {
    console.error(`Unable to read AOC command contract: ${COMMAND_CONTRACT_PATH}`);
    console.error(err.message);
    process.exit(1);
  }
}

function validateCommandContract(contract) {
  const commands = Array.isArray(contract.commands) ? contract.commands : [];
  if (!commands.length) {
    console.error(`Invalid AOC command contract: no commands in ${COMMAND_CONTRACT_PATH}`);
    process.exit(1);
  }
  const missingFromRoute = [];
  const missingFromShim = [];
  for (const command of commands) {
    const names = [command.name, ...(command.aliases || [])].filter(Boolean);
    for (const name of names) {
      if (!ROUTE_COMMANDS.has(name)) missingFromRoute.push(name);
      if (command.installedShim !== false && !SHIM_COMMANDS.has(name)) missingFromShim.push(name);
    }
  }
  if (missingFromRoute.length || missingFromShim.length) {
    if (missingFromRoute.length) console.error(`Command contract has names not routed by bin/aoc.mjs: ${missingFromRoute.join(', ')}`);
    if (missingFromShim.length) console.error(`Command contract has names not supported by installed shims: ${missingFromShim.join(', ')}`);
    process.exit(1);
  }
}

const COMMAND_CONTRACT = loadCommandContract();
validateCommandContract(COMMAND_CONTRACT);

function commonCommandLines() {
  const commands = (COMMAND_CONTRACT.commands || []).filter(c => c.common);
  return commands.map(c => `  ${c.usage.padEnd(27)} ${c.summary}`);
}

function printHelp() {
  console.log(`Agentic Orchestration Control

Usage:
  npx agentic-orchestration-control [command] [options]
  npx agentic-orchestration-control --repo .

Common commands:
${commonCommandLines().join('\n')}

Options:
  --repo, --root <path>       Repo to inspect/control (default: current directory)
  --run-id <id|current|latest> Run ID for session-scoped commands
  --json                      Print JSON where supported
  --quiet                     Suppress non-essential output where supported
  --verbose                   Prefer verbose output where supported
  --no-open                   Do not auto-open browsers where supported
  --version, -v               Print package version

Short aliases after local/global install:
  aoc                         same as agentic-orchestration-control
  aoc gui                     GUI
  aoc usage                   usage report
  aoc budget 12000            budget check

Examples:
  npx agentic-orchestration-control install .
  npx agentic-orchestration-control
  npx agentic-orchestration-control gui
  aoc init "Fix checkout flow"
  aoc sessions
  aoc import latest
  aoc current
  npx agentic-orchestration-control sessions
  npx agentic-orchestration-control import latest
  npx agentic-orchestration-control current
  aoc use <run_id>
  npx agentic-orchestration-control use latest
  aoc search checkout
  npx agentic-orchestration-control search "handoff"
  npx agentic-orchestration-control usage
  npx agentic-orchestration-control budget 12000
  npx agentic-orchestration-control gui --with-codex
`);
}

function printVersion() {
  const pkg = JSON.parse(readFileSync(join(PKG_ROOT, 'package.json'), 'utf8'));
  console.log(pkg.version || '0.0.0');
}

function optionConsumesValue(arg) {
  return ['--repo', '--root', '--run-id', '--run'].includes(arg);
}

function extractCommand(args) {
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--') break;
    if (optionConsumesValue(a)) {
      i++;
      continue;
    }
    if (a.startsWith('--repo=') || a.startsWith('--root=') || a.startsWith('--run-id=') || a.startsWith('--run=')) {
      continue;
    }
    if (a.startsWith('-')) continue;
    return { first: a, args: [...args.slice(0, i), ...args.slice(i + 1)] };
  }
  return { first: 'tui', args };
}

function isDirectory(path) {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function findGitRoot(start) {
  const cwd = resolve(start || process.cwd());
  const res = spawnSync('git', ['rev-parse', '--show-toplevel'], {
    cwd,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
    shell: false
  });
  const found = res.status === 0 ? String(res.stdout || '').trim() : '';
  return found ? resolve(found) : null;
}

function cwdLooksLikeRepo(cwd) {
  return ['.orchestration', 'package.json', 'skills', '.git'].some(marker => existsSync(join(cwd, marker)));
}

function resolveRepo(common) {
  const explicit = common.repoArg || process.env.AOC_REPO || '';
  if (explicit) {
    const repo = resolve(explicit);
    if (!isDirectory(repo)) {
      console.error(`Resolved repository is not a directory: ${repo}`);
      process.exit(2);
    }
    return repo;
  }
  const gitRoot = findGitRoot(process.cwd());
  if (gitRoot) return gitRoot;
  const cwd = resolve(process.cwd());
  if (cwdLooksLikeRepo(cwd)) return cwd;
  console.error('Unable to resolve repository. Use --repo <path> or set AOC_REPO, or run from a git/worktree root or a project directory containing .orchestration, package.json, skills, or .git.');
  process.exit(2);
}

function parseCommon(args) {
  const out = { repoArg: null, runId: null, json: false, quiet: false, verbose: false, noOpen: false, rest: [] };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--') {
      out.rest.push(...args.slice(i + 1));
      break;
    }
    if ((a === '--repo' || a === '--root') && args[i + 1]) {
      out.repoArg = args[++i];
    } else if (a.startsWith('--repo=')) {
      out.repoArg = a.slice('--repo='.length);
    } else if (a.startsWith('--root=')) {
      out.repoArg = a.slice('--root='.length);
    } else if ((a === '--run-id' || a === '--run') && args[i + 1]) {
      out.runId = args[++i];
    } else if (a.startsWith('--run-id=')) {
      out.runId = a.slice('--run-id='.length);
    } else if (a.startsWith('--run=')) {
      out.runId = a.slice('--run='.length);
    } else if (a === '--json') {
      out.json = true;
    } else if (a === '--quiet' || a === '-q') {
      out.quiet = true;
    } else if (a === '--verbose') {
      out.verbose = true;
    } else if (a === '--no-open') {
      out.noOpen = true;
    } else {
      out.rest.push(a);
    }
  }
  return out;
}

function readJson(path, fallback = {}) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return fallback;
  }
}

function validRunId(value) {
  return typeof value === 'string'
    && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value)
    && !value.includes('/')
    && !value.includes('\\')
    && !value.includes('..');
}

function stateExists(repo, runId) {
  return validRunId(runId) && existsSync(join(repo, '.orchestration', 'runs', runId, 'state.json'));
}

function currentRunFileId(repo) {
  try {
    const runId = readFileSync(join(repo, '.orchestration', 'current-run'), 'utf8').trim().split(/\s+/)[0];
    return stateExists(repo, runId) ? runId : null;
  } catch {
    return null;
  }
}

function currentJsonRunId(repo) {
  const data = readJson(join(repo, '.orchestration', 'current.json'), {});
  const runId = data.current_run_id || data.run_id;
  return stateExists(repo, runId) ? runId : null;
}

function latestRunId(repo) {
  const index = readJson(join(repo, '.orchestration', 'index.json'), {});
  if (stateExists(repo, index.latest_run_id)) return index.latest_run_id;
  const runsDir = join(repo, '.orchestration', 'runs');
  if (!existsSync(runsDir)) return null;
  let latest = null;
  try {
    for (const entry of readdirSync(runsDir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const statePath = join(runsDir, entry.name, 'state.json');
      if (!existsSync(statePath)) continue;
      const state = readJson(statePath, {});
      const runId = state.run_id || entry.name;
      if (!stateExists(repo, runId)) continue;
      const updated = String(state.updated_at || state.created_at || '');
      if (!latest || updated > latest.updated) latest = { runId, updated };
    }
  } catch {
    return null;
  }
  return latest ? latest.runId : null;
}

function selectedRun(common, repo) {
  if (common.runId && common.runId !== 'current') return { runId: common.runId, source: 'cli' };
  if (!common.runId && process.env.AOC_RUN_ID && process.env.AOC_RUN_ID !== 'current') return { runId: process.env.AOC_RUN_ID, source: 'env' };
  const currentRun = currentRunFileId(repo);
  if (currentRun) return { runId: currentRun, source: 'current-run' };
  const currentJson = currentJsonRunId(repo);
  if (currentJson) return { runId: currentJson, source: 'current.json' };
  const latest = latestRunId(repo);
  if (latest) return { runId: latest, source: 'latest' };
  return { runId: null, source: 'none' };
}

function jsonArg(common) {
  return common.json ? ['--json'] : [];
}

function quietArg(common) {
  return common.quiet ? ['--quiet'] : [];
}

function noOpenArg(common) {
  return common.noOpen ? ['--no-open'] : [];
}

function codexDiscoveryRequested(rest) {
  return Boolean(process.env.AOC_CODEX_HOME || process.env.CODEX_HOME)
    || rest.includes('--codex-home')
    || rest.some(arg => arg.startsWith('--codex-home='));
}

function explicitCodexHomes(rest) {
  const homes = [];
  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i];
    if (arg === '--codex-home' && rest[i + 1]) {
      homes.push(rest[++i]);
    } else if (arg.startsWith('--codex-home=')) {
      homes.push(arg.slice('--codex-home='.length));
    }
  }
  if (process.env.AOC_CODEX_HOME) homes.push(process.env.AOC_CODEX_HOME);
  if (process.env.CODEX_HOME) homes.push(process.env.CODEX_HOME);
  return [...new Set(homes.filter(Boolean).map(home => resolve(home)))];
}

function rolloutFilesUnder(home) {
  const base = join(home, 'sessions');
  const out = [];
  const stack = [base];
  while (stack.length) {
    const dir = stack.pop();
    if (!dir || !existsSync(dir)) continue;
    let entries = [];
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(path);
      } else if (entry.isFile() && entry.name.startsWith('rollout-') && entry.name.endsWith('.jsonl')) {
        out.push(path);
      }
    }
  }
  return out;
}

function latestExplicitCodexSession(rest) {
  const candidates = [];
  for (const home of explicitCodexHomes(rest)) {
    for (const path of rolloutFilesUnder(home)) {
      try {
        candidates.push({ path, mtime: statSync(path).mtimeMs });
      } catch {
        // Ignore files that disappear while resolving.
      }
    }
  }
  candidates.sort((a, b) => a.mtime - b.mtime || a.path.localeCompare(b.path));
  return candidates.length ? candidates[candidates.length - 1].path : null;
}

function firstPositionalIndex(args) {
  const valueOptions = new Set(['--codex-home', '--limit', '--interval']);
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--') return i + 1 < args.length ? i + 1 : -1;
    if (valueOptions.has(arg)) {
      i++;
      continue;
    }
    if (arg.startsWith('-')) continue;
    return i;
  }
  return -1;
}

function pinExplicitCodexLatest(rest) {
  const homes = explicitCodexHomes(rest);
  if (!homes.length) return rest;
  const positional = firstPositionalIndex(rest);
  if (positional !== -1 && rest[positional] !== 'latest') return rest;
  const latest = latestExplicitCodexSession(rest);
  if (!latest) return rest;
  const pinned = [...rest];
  if (positional === -1) pinned.push(latest);
  else pinned[positional] = latest;
  return pinned;
}

function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, {
    stdio: opts.stdio ?? 'inherit',
    cwd: opts.cwd ?? process.cwd(),
    env: { ...process.env, ...(opts.env ?? {}) },
    shell: false
  });
  if (res.error) {
    if (res.error.code === 'ENOENT') {
      console.error(`Missing dependency: ${cmd}. ${opts.hint ?? 'Install it and retry.'}`);
    } else {
      console.error(`Failed to run ${cmd}: ${res.error.message}`);
    }
    process.exit(1);
  }
  process.exit(res.status ?? 0);
}

function requireCommand(cmd, hint) {
  const res = spawnSync(cmd, ['--version'], { stdio: 'ignore', shell: false });
  if (res.error) {
    if (res.error.code === 'ENOENT') {
      console.error(`Missing dependency: ${cmd}. ${hint}`);
    } else {
      console.error(`Unable to check dependency ${cmd}: ${res.error.message}`);
    }
    process.exit(127);
  }
}

function pythonScript(script, args, repo, opts = {}) {
  const p = join(SCRIPTS, script);
  if (!existsSync(p)) {
    console.error(`Missing bundled script: ${p}`);
    process.exit(1);
  }
  requireCommand('python3', 'Install Python 3 and make sure python3 is on PATH.');
  run('python3', [p, ...args], { cwd: repo, env: opts.env, hint: 'Install Python 3 and make sure python3 is on PATH.' });
}

function pythonScriptOutput(script, args, repo, opts = {}) {
  const p = join(SCRIPTS, script);
  if (!existsSync(p)) {
    console.error(`Missing bundled script: ${p}`);
    process.exit(1);
  }
  requireCommand('python3', 'Install Python 3 and make sure python3 is on PATH.');
  const res = spawnSync('python3', [p, ...args], {
    cwd: repo,
    env: { ...process.env, ...(opts.env ?? {}) },
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
    shell: false
  });
  if (res.error) {
    console.error(`Failed to run python3: ${res.error.message}`);
    process.exit(1);
  }
  return { status: res.status ?? 0, stdout: String(res.stdout || '') };
}

function ensureInstallExists() {
  if (!existsSync(INSTALL)) {
    console.error(`Missing install script: ${INSTALL}`);
    process.exit(1);
  }
}

function installedShimScript() {
  return [
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    'REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"',
    'CONTROL="$REPO_ROOT/skills/agent-orchestration-skill/bin/agentic-orchestration-control"',
    'if [[ ! -x "$CONTROL" ]]; then',
    '  echo "Missing executable wrapper: $CONTROL" >&2',
    '  exit 1',
    'fi',
    'exec "$CONTROL" "$@"'
  ].join('\n') + '\n';
}

function refreshInstalledShims(target) {
  const binDir = join(target, '.orchestration', 'bin');
  const control = join(binDir, 'agentic-orchestration-control');
  if (!existsSync(binDir)) return;
  writeFileSync(control, installedShimScript(), 'utf8');
  chmodSync(control, 0o755);
  for (const name of ['aoc']) {
    copyFileSync(control, join(binDir, name));
    chmodSync(join(binDir, name), 0o755);
  }
}

function hasRunState(repo) {
  const runs = join(repo, '.orchestration', 'runs');
  if (!existsSync(runs)) return false;
  try {
    return readdirSync(runs, { withFileTypes: true }).some(entry => entry.isDirectory() && existsSync(join(runs, entry.name, 'state.json')));
  } catch {
    return false;
  }
}

function codexDiscoveryEnvForPassiveViews(repo, selected) {
  return {};
}

function runPassiveTextView(script, args, repo, env) {
  if (Object.keys(env).length > 0 && !process.stdout.isTTY) {
    const out = pythonScriptOutput(script, args, repo, { env });
    process.stdout.write(out.stdout.includes('No sessions') || out.stdout.includes('No orchestration sessions') ? out.stdout : `${out.stdout}\nNo sessions\n`);
    process.exit(out.status);
  }
  pythonScript(script, args, repo, { env });
}

function route(rawArgs) {
  let args = [...rawArgs];
  if (args.includes('-h') || args.includes('--help')) {
    printHelp();
    return;
  }
  if (args.includes('-v') || args.includes('--version')) {
    printVersion();
    return;
  }

  // Let binary aliases imply a default command while still accepting options.
  if (invokedName === 'aoc-gui' && (!args[0] || args[0].startsWith('-'))) args.unshift('gui');
  if (invokedName === 'aoc-usage' && (!args[0] || args[0].startsWith('-'))) args.unshift('usage');

  const extracted = extractCommand(args);
  const first = extracted.first;
  args = extracted.args;
  const cmd = first.toLowerCase();
  const common = parseCommon(args);
  const rest = common.rest;

  switch (cmd) {
    case 'help':
      printHelp();
      return;
    case 'install': {
      ensureInstallExists();
      const target = rest[0] ? resolve(rest[0]) : resolveRepo(common);
      requireCommand('bash', 'Install Bash and make sure bash is on PATH.');
      const res = spawnSync('bash', [INSTALL, target], {
        stdio: 'inherit',
        cwd: PKG_ROOT,
        env: process.env,
        shell: false
      });
      if (res.error) {
        console.error(`Failed to run bash: ${res.error.message}`);
        process.exit(1);
      }
      if ((res.status ?? 0) !== 0) process.exit(res.status ?? 1);
      refreshInstalledShims(target);
      return;
    }
  }

  const repo = resolveRepo(common);
  const selected = selectedRun(common, repo);
  const runId = selected.runId || 'latest';
  const resolvedRunArgs = selected.runId ? ['--run-id', selected.runId] : [];
  const passiveRunArgs = selected.runId ? ['--run-id', selected.runId] : [];
  const explicitRunArgs = ['cli', 'env'].includes(selected.source) && selected.runId ? ['--run-id', selected.runId] : [];

  switch (cmd) {
    case 'tui':
    case 'control':
    case 'dashboard':
      runPassiveTextView('aoc_tui.py', ['--repo', repo, ...passiveRunArgs, ...jsonArg(common), ...rest], repo, codexDiscoveryEnvForPassiveViews(repo, selected));
      return;
    case 'snapshot':
      runPassiveTextView('aoc_tui.py', ['--repo', repo, '--snapshot', ...passiveRunArgs, ...jsonArg(common), ...rest], repo, codexDiscoveryEnvForPassiveViews(repo, selected));
      return;
    case 'gui':
    case 'web': {
      const viewEnv = codexDiscoveryEnvForPassiveViews(repo, selected);
      const guiArgs = ['--repo', repo, ...passiveRunArgs, ...jsonArg(common), ...noOpenArg(common), ...rest];
      if (rest.includes('--once') && Object.keys(viewEnv).length > 0) {
        const out = pythonScriptOutput('aoc_gui.py', guiArgs, repo, { env: viewEnv });
        process.stdout.write(out.stdout.includes('No orchestration sessions') ? out.stdout : `${out.stdout}\n<!-- No orchestration sessions -->\n`);
        process.exit(out.status);
      }
      pythonScript('aoc_gui.py', guiArgs, repo, { env: viewEnv });
      return;
    }
    case 'sessions':
    case 'session':
      pythonScript('codex_session_cli.py', [
        'sessions',
        '--root',
        repo,
        ...(hasRunState(repo) && !codexDiscoveryRequested(rest) ? ['--aoc-only'] : []),
        ...jsonArg(common),
        ...rest
      ], repo);
      return;
    case 'current':
      pythonScript('codex_session_cli.py', ['current', '--root', repo, ...resolvedRunArgs, ...jsonArg(common), ...rest], repo);
      return;
    case 'use':
      pythonScript('codex_session_cli.py', ['use', '--root', repo, ...explicitRunArgs, ...jsonArg(common), ...rest], repo);
      return;
    case 'import':
      pythonScript('codex_session_cli.py', ['import', '--root', repo, ...explicitRunArgs, ...jsonArg(common), ...quietArg(common), ...pinExplicitCodexLatest(rest)], repo);
      return;
    case 'watch':
      pythonScript('codex_session_cli.py', ['watch', '--root', repo, ...explicitRunArgs, ...jsonArg(common), ...quietArg(common), ...pinExplicitCodexLatest(rest)], repo);
      return;
    case 'search':
      if (!rest.length) {
        console.error('Usage: aoc search <query>');
        process.exit(2);
      }
      pythonScript('codex_session_cli.py', ['search', '--root', repo, ...resolvedRunArgs, ...jsonArg(common), ...rest], repo);
      return;
    case 'usage':
    case 'report': {
      const hasReportSubcmd = rest[0] && ['record', 'derive', 'report', 'statusline', 'budget'].includes(rest[0]);
      const usageSupportsJson = !hasReportSubcmd || ['record', 'derive', 'report', 'budget'].includes(rest[0]);
      const usageArgs = hasReportSubcmd
        ? rest
        : ['report', '--run-id', runId, '--scope-run', '--derive', ...rest];
      pythonScript('usage_ledger.py', [...usageArgs, '--root', repo, ...(usageSupportsJson ? jsonArg(common) : [])], repo);
      return;
    }
    case 'statusline':
      pythonScript('usage_ledger.py', ['statusline', '--root', repo, '--run-id', runId, ...rest], repo);
      return;
    case 'budget': {
      const budgetArgs = ['budget', '--run-id', runId, '--scope-run', '--derive'];
      if (rest[0] && /^\d+(\.\d+)?$/.test(rest[0])) {
        budgetArgs.push('--max-estimated-tokens', rest.shift());
      } else if (!rest.some(x => x.startsWith('--max-'))) {
        budgetArgs.push('--max-estimated-tokens', '12000');
      }
      pythonScript('usage_ledger.py', [...budgetArgs, '--root', repo, ...jsonArg(common), ...rest], repo);
      return;
    }
    case 'ccusage': {
      const ccArgs = rest.length ? rest : ['doctor'];
      const sub = ccArgs[0];
      const withRoot = sub === 'doctor' ? ccArgs : [...ccArgs, '--root', repo];
      pythonScript('ccusage_bridge.py', [...withRoot, ...jsonArg(common)], repo);
      return;
    }
    case 'codex': {
      const codexArgs = rest.length ? rest : ['doctor'];
      const sub = codexArgs[0];
      const withRoot = ['doctor', 'start-help'].includes(sub) ? codexArgs : [...codexArgs, '--root', repo, '--run-id', runId];
      const supportsJson = ['doctor', 'status', 'link', 'import'].includes(sub);
      pythonScript('codex_appserver_bridge.py', [...withRoot, ...(supportsJson ? jsonArg(common) : [])], repo);
      return;
    }
    case 'codexui':
      pythonScript('codex_appserver_bridge.py', ['codexui', ...rest], repo);
      return;
    case 'init':
    case 'new-run': {
      const initArgs = [...rest];
      if (initArgs[0] && !initArgs[0].startsWith('-')) {
        initArgs.unshift('--task');
      }
      pythonScript('run_ledger.py', ['init', '--root', repo, ...explicitRunArgs, ...initArgs], repo);
      return;
    }
    case 'publish-check':
      pythonScript('npm_publish_check.py', ['--root', PKG_ROOT, ...rest], PKG_ROOT);
      return;
    case 'stats':
      pythonScript('orchestration_stats.py', ['--root', repo, '--run-id', runId, ...jsonArg(common), ...rest], repo);
      return;
    case 'events':
    case 'tail':
      pythonScript('event_tail.py', ['--root', repo, '--run-id', runId, ...jsonArg(common), ...rest], repo);
      return;
    case 'memory': {
      const memoryArgs = rest.length ? rest : ['build', '--run-id', runId];
      pythonScript('memory_index.py', [...memoryArgs, '--root', repo, ...jsonArg(common)], repo);
      return;
    }
    case 'gates':
    case 'gate': {
      const gateArgs = rest.length ? rest : ['status'];
      const supportsJson = ['status', 'enforce'].includes(gateArgs[0]);
      pythonScript('control_gate.py', [...gateArgs, '--root', repo, ...(supportsJson ? jsonArg(common) : [])], repo);
      return;
    }
    case 'doctor':
      pythonScript('token_budget_linter.py', ['--root', repo, ...rest], repo);
      return;
    case 'version':
    case '--version': {
      printVersion();
      return;
    }
    default:
      console.error(`Unknown command: ${cmd}\n`);
      printHelp();
      process.exit(2);
  }
}

route(originalArgv);
