#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PKG_ROOT = resolve(__dirname, '..');
const SKILL_DIR = join(PKG_ROOT, 'skills', 'agent-orchestration-skill');
const SCRIPTS = join(SKILL_DIR, 'scripts');
const INSTALL = join(PKG_ROOT, 'install.sh');

const originalArgv = process.argv.slice(2);
const invokedName = process.argv[1] ? process.argv[1].split(/[\\/]/).pop() : 'aoc';

function printHelp() {
  console.log(`Agentic Orchestration Control

Usage:
  npx agentic-orchestration-control [command] [options]
  npx agentic-orchestration-control --repo .

Common commands:
  tui                         Open the terminal control room (default)
  gui                         Open the local web GUI
  install [repo]              Install the skill pack into a repo (default: current directory)
  usage                       Show run-scoped usage report with derived pressure
  budget [max]                Check usage budget (default max estimated tokens: 12000)
  ccusage [doctor|run|import] Bridge external ccusage JSON into the usage ledger
  codex [doctor|status|link|import|start-help] Optional Codex app-server/codexui bridge
  codexui                     Show safe codexui helper commands
  init                        Initialize a production run ledger
  publish-check               Validate npm publish readiness
  stats                       Show orchestration run statistics
  events                      Tail orchestration events
  memory [build|search]       Build/search memory index
  gates                       Manage STOP gates
  snapshot                    Print non-interactive TUI snapshot
  doctor                      Run local pack sanity checks

Options:
  --repo, --root <path>       Repo to inspect/control (default: current directory)
  --run-id <id|latest>        Run ID for session-scoped commands
  --json                      Print JSON where supported
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
  npx agentic-orchestration-control usage
  npx agentic-orchestration-control budget 12000
  npx agentic-orchestration-control gui --with-codex
`);
}

function printVersion() {
  const pkg = JSON.parse(readFileSync(join(PKG_ROOT, 'package.json'), 'utf8'));
  console.log(pkg.version || '0.0.0');
}

function parseCommon(args) {
  const out = { repo: process.cwd(), runId: null, rest: [] };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if ((a === '--repo' || a === '--root') && args[i + 1]) {
      out.repo = resolve(args[++i]);
    } else if (a.startsWith('--repo=')) {
      out.repo = resolve(a.slice('--repo='.length));
    } else if (a.startsWith('--root=')) {
      out.repo = resolve(a.slice('--root='.length));
    } else if ((a === '--run-id' || a === '--run') && args[i + 1]) {
      out.runId = args[++i];
    } else if (a.startsWith('--run-id=')) {
      out.runId = a.slice('--run-id='.length);
    } else if (a.startsWith('--run=')) {
      out.runId = a.slice('--run='.length);
    } else {
      out.rest.push(a);
    }
  }
  return out;
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

function pythonScript(script, args, repo) {
  const p = join(SCRIPTS, script);
  if (!existsSync(p)) {
    console.error(`Missing bundled script: ${p}`);
    process.exit(1);
  }
  requireCommand('python3', 'Install Python 3 and make sure python3 is on PATH.');
  run('python3', [p, ...args], { cwd: repo, hint: 'Install Python 3 and make sure python3 is on PATH.' });
}

function ensureInstallExists() {
  if (!existsSync(INSTALL)) {
    console.error(`Missing install script: ${INSTALL}`);
    process.exit(1);
  }
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

  const first = args[0] && !args[0].startsWith('-') ? args.shift() : 'tui';
  const cmd = first.toLowerCase();
  const common = parseCommon(args);
  const repo = common.repo;
  const runId = common.runId || 'latest';
  const rest = common.rest;

  switch (cmd) {
    case 'help':
      printHelp();
      return;
    case 'install': {
      ensureInstallExists();
      const target = rest[0] ? resolve(rest[0]) : repo;
      requireCommand('bash', 'Install Bash and make sure bash is on PATH.');
      run('bash', [INSTALL, target], { cwd: PKG_ROOT, hint: 'Install Bash and make sure bash is on PATH.' });
      return;
    }
    case 'tui':
    case 'control':
    case 'dashboard':
      pythonScript('aoc_tui.py', ['--repo', repo, ...(common.runId ? ['--run-id', runId] : []), ...rest], repo);
      return;
    case 'snapshot':
      pythonScript('aoc_tui.py', ['--repo', repo, '--snapshot', ...(common.runId ? ['--run-id', runId] : []), ...rest], repo);
      return;
    case 'gui':
    case 'web':
      pythonScript('aoc_gui.py', ['--repo', repo, ...(common.runId ? ['--run-id', runId] : []), ...rest], repo);
      return;
    case 'usage':
    case 'report': {
      const hasReportSubcmd = rest[0] && ['record', 'derive', 'report', 'statusline', 'budget'].includes(rest[0]);
      const usageArgs = hasReportSubcmd
        ? rest
        : ['report', '--run-id', runId, '--scope-run', '--derive', ...rest];
      pythonScript('usage_ledger.py', [...usageArgs, '--root', repo], repo);
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
      pythonScript('usage_ledger.py', [...budgetArgs, '--root', repo, ...rest], repo);
      return;
    }
    case 'ccusage': {
      const ccArgs = rest.length ? rest : ['doctor'];
      const sub = ccArgs[0];
      const withRoot = sub === 'doctor' ? ccArgs : [...ccArgs, '--root', repo];
      pythonScript('ccusage_bridge.py', withRoot, repo);
      return;
    }
    case 'codex': {
      const codexArgs = rest.length ? rest : ['doctor'];
      const sub = codexArgs[0];
      const withRoot = ['doctor', 'start-help'].includes(sub) ? codexArgs : [...codexArgs, '--root', repo, '--run-id', runId];
      pythonScript('codex_appserver_bridge.py', withRoot, repo);
      return;
    }
    case 'codexui':
      pythonScript('codex_appserver_bridge.py', ['codexui', ...rest], repo);
      return;
    case 'init':
    case 'new-run':
      pythonScript('run_ledger.py', ['init', '--root', repo, ...(common.runId ? ['--run-id', common.runId] : []), ...rest], repo);
      return;
    case 'publish-check':
      pythonScript('npm_publish_check.py', ['--root', PKG_ROOT, ...rest], PKG_ROOT);
      return;
    case 'stats':
      pythonScript('orchestration_stats.py', ['--root', repo, '--run-id', runId, ...rest], repo);
      return;
    case 'events':
    case 'tail':
      pythonScript('event_tail.py', ['--root', repo, '--run-id', runId, ...rest], repo);
      return;
    case 'memory': {
      const memoryArgs = rest.length ? rest : ['build', '--run-id', runId];
      pythonScript('memory_index.py', [...memoryArgs, '--root', repo], repo);
      return;
    }
    case 'gates':
    case 'gate': {
      const gateArgs = rest.length ? rest : ['status'];
      pythonScript('control_gate.py', [...gateArgs, '--root', repo], repo);
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
