#!/usr/bin/env node
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, readFileSync, symlinkSync, rmSync, utimesSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const CLI = join(ROOT, 'bin', 'aoc.mjs');
const COMMAND_CONTRACT = join(ROOT, 'tools', 'aoc.commands.json');
const PACKAGE_JSON = join(ROOT, 'package.json');

function run(cmd, args, opts = {}) {
  const env = { ...process.env, ...(opts.env || {}) };
  for (const key of opts.envUnset || []) {
    delete env[key];
  }
  const res = spawnSync(cmd, args, {
    cwd: opts.cwd || ROOT,
    encoding: 'utf8',
    timeout: opts.timeout || 180000,
    env
  });
  if (res.status !== 0) {
    console.error(res.stdout);
    console.error(res.stderr);
    throw new Error(`command failed: ${cmd} ${args.join(' ')}`);
  }
  return res;
}

function pass(msg) { console.log(`PASS ${msg}`); }

function parseJsonResult(res, label) {
  try {
    return JSON.parse(res.stdout);
  } catch (err) {
    throw new Error(`${label} did not return JSON: ${res.stdout}`);
  }
}

function assertHelpIncludes(res, commands) {
  for (const command of commands) {
    if (!res.stdout.includes(command)) throw new Error(`help output missing command contract entry: ${command}`);
  }
}

function assertInstalledShimHelp(res, commands, label) {
  for (const command of commands) {
    if (!res.stdout.includes(command)) throw new Error(`${label} help output missing installed shim command: ${command}`);
  }
}

function assertSessionRows(payload, label) {
  const rows = Array.isArray(payload) ? payload : payload.sessions;
  if (!Array.isArray(rows)) throw new Error(`${label} did not return a session list`);
  return rows;
}

function assertUsageScopedTo(payload, expectedRunId, label) {
  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  const keys = rows.map(row => String(row.key || row.run_id || ''));
  if (!keys.includes(expectedRunId)) {
    throw new Error(`${label} did not report ${expectedRunId}: ${JSON.stringify(payload)}`);
  }
}

function requireCmd(cmd) {
  const res = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
  if (res.error) {
    throw new Error(`missing dependency: ${cmd}`);
  }
}

for (const cmd of ['bash', 'git', 'node', 'python3']) requireCmd(cmd);

if (!existsSync(COMMAND_CONTRACT)) throw new Error('missing tools/aoc.commands.json command contract');
const commandContract = JSON.parse(readFileSync(COMMAND_CONTRACT, 'utf8'));
const packageJson = JSON.parse(readFileSync(PACKAGE_JSON, 'utf8'));
if (!Array.isArray(commandContract.commands) || !commandContract.commands.length) {
  throw new Error('tools/aoc.commands.json missing non-empty commands array');
}
const contractCommands = commandContract.commands;
const helpIncludes = Array.isArray(commandContract.helpIncludes)
  ? commandContract.helpIncludes
  : contractCommands.filter(c => c.common).map(c => c.usage || c.name);
const installedShimCommands = Array.isArray(commandContract.installedShimCommands)
  ? commandContract.installedShimCommands
  : contractCommands.filter(c => c.installedShim !== false).map(c => c.name);
const installedShimHelpIncludes = Array.isArray(commandContract.installedShimHelpIncludes)
  ? commandContract.installedShimHelpIncludes
  : contractCommands.filter(c => c.installedShim !== false && c.common).map(c => c.name);
const codexSessionShimCommands = Array.isArray(commandContract.codexSessionShimCommands)
  ? commandContract.codexSessionShimCommands
  : ['sessions', 'current', 'use', 'import', 'watch', 'search'];
const packageFiles = Array.isArray(commandContract.packageFiles)
  ? commandContract.packageFiles
  : ['tools/aoc.commands.json', 'bin/aoc.mjs', 'install.sh', 'skills/agent-orchestration-skill/scripts/codex_session_cli.py'];
for (const command of codexSessionShimCommands) {
  if (!installedShimCommands.includes(command)) throw new Error(`command contract does not mark ${command} as installed-shim supported`);
}

const td = mkdtempSync(join(tmpdir(), 'aoc-npm-cli-'));
process.on('exit', () => rmSync(td, { recursive: true, force: true }));
const repo = join(td, 'repo');
const npmGuiAlias = join(td, 'aoc-gui');
const npmUsageAlias = join(td, 'aoc-usage');
symlinkSync(CLI, npmGuiAlias);
symlinkSync(CLI, npmUsageAlias);

run('mkdir', ['-p', repo]);
run('git', ['init', '-q'], { cwd: repo });

run('node', [CLI, 'install', repo]);
if (!existsSync(join(repo, 'skills', 'agent-orchestration-skill', 'scripts', 'aoc_gui.py'))) throw new Error('aoc_gui.py not installed under skills/');
if (existsSync(join(repo, '.skills'))) throw new Error('legacy .skills directory should not exist after install');
if (!existsSync(join(repo, '.orchestration', 'bin', 'aoc-gui'))) throw new Error('aoc-gui shim not installed');
const agents = readFileSync(join(repo, 'AGENTS.md'), 'utf8');
if (!agents.includes('exact literal invocation') || !agents.includes('Leaf mode')) throw new Error('install did not create AGENTS.md orchestration gate');
if ((agents.match(/BEGIN AGENT_ORCHESTRATION_SKILL_GATE/g) || []).length !== 1) throw new Error('AGENTS.md orchestration gate duplicated');
pass('npm CLI install command uses production skills/ layout');

const scripts = join(repo, 'skills', 'agent-orchestration-skill', 'scripts');
const help = run('node', [CLI, '--help']);
assertHelpIncludes(help, helpIncludes);
pass('help advertises short command contract');

run('node', [CLI, 'init', '--repo', repo, '--run-id', 'npm-run', '--task', 'npm CLI smoke task']);
const positionalInit = parseJsonResult(run('node', [CLI, 'init', 'Fix checkout flow', '--repo', repo, '--json']), 'short positional init');
if (!positionalInit.run_id || positionalInit.run_id === 'latest') throw new Error(`short init did not generate a unique run id: ${positionalInit.run_id}`);
if (!existsSync(positionalInit.state)) throw new Error('short init state file missing');
pass('aoc init "task" --json generates a run id');
const generatedInit = parseJsonResult(run('node', [CLI, 'init', '--repo', repo, '--task', 'npm CLI generated run id task', '--json']), 'generated run init');
if (!generatedInit.run_id || generatedInit.run_id === 'latest') throw new Error(`init without --run-id should generate a unique run id, got ${generatedInit.run_id}`);
if (!existsSync(generatedInit.state)) throw new Error('generated run state file missing');
pass('npm CLI init without --run-id generates a run id');

const bundledSkillAoc = join(repo, 'skills', 'agent-orchestration-skill', 'bin', 'aoc');
const bundledSessions = assertSessionRows(parseJsonResult(run(bundledSkillAoc, ['sessions', '--json'], { cwd: repo }), 'bundled skill bin sessions --json'), 'bundled skill bin sessions --json');
if (!bundledSessions.some(r => r.run_id === 'npm-run') || !bundledSessions.some(r => r.run_id === generatedInit.run_id)) {
  throw new Error(`bundled skill bin sessions --json missing initialized runs: ${JSON.stringify(bundledSessions)}`);
}
pass('bundled skill bin aoc sessions --json works');
const bundledShortInit = parseJsonResult(run(bundledSkillAoc, ['init', 'Bundled skill checkout task', '--json'], { cwd: repo }), 'bundled skill bin short init');
if (!bundledShortInit.run_id || bundledShortInit.run_id === 'latest' || !existsSync(bundledShortInit.state)) {
  throw new Error(`bundled skill bin short init failed: ${JSON.stringify(bundledShortInit)}`);
}
const bundledShortState = JSON.parse(readFileSync(bundledShortInit.state, 'utf8'));
if (bundledShortState.task !== 'Bundled skill checkout task') throw new Error(`bundled skill bin short init did not preserve task: ${JSON.stringify(bundledShortState)}`);
pass('bundled skill bin aoc init "task" --json works');

const sessionsJson = parseJsonResult(run('node', [CLI, 'sessions', '--repo', repo, '--json']), 'sessions --json');
const sessionRows = assertSessionRows(sessionsJson, 'sessions --json');
if (!sessionRows.some(r => r.run_id === 'npm-run') || !sessionRows.some(r => r.run_id === generatedInit.run_id)) throw new Error(`sessions --json missing initialized runs: ${JSON.stringify(sessionRows)}`);
pass('aoc sessions --json lists initialized runs');
const currentJson = parseJsonResult(run('node', [CLI, 'current', '--repo', repo, '--json']), 'current --json');
if (!currentJson.run_id) throw new Error(`current --json missing run_id: ${JSON.stringify(currentJson)}`);
const useJson = parseJsonResult(run('node', [CLI, 'use', 'npm-run', '--repo', repo, '--json']), 'use --json');
if (useJson.run_id !== 'npm-run') throw new Error(`use did not select npm-run: ${JSON.stringify(useJson)}`);
const selectedJson = parseJsonResult(run('node', [CLI, 'current', '--repo', repo, '--json']), 'current after use');
if (selectedJson.run_id !== 'npm-run') throw new Error(`current did not report selected npm-run: ${JSON.stringify(selectedJson)}`);
pass('aoc current/use manage current run');

const outside = join(td, 'outside');
run('mkdir', ['-p', outside]);
const envResolvedCurrent = parseJsonResult(run('node', [CLI, 'current', '--json'], {
  cwd: outside,
  env: { AOC_REPO: repo, AOC_RUN_ID: 'npm-run' }
}), 'current with AOC_REPO/AOC_RUN_ID outside repo');
if (envResolvedCurrent.run_id !== 'npm-run' || !String(envResolvedCurrent.state || '').startsWith(repo)) {
  throw new Error(`AOC_REPO/AOC_RUN_ID did not resolve current run outside repo: ${JSON.stringify(envResolvedCurrent)}`);
}
const envResolvedSessions = assertSessionRows(parseJsonResult(run('node', [CLI, 'sessions', '--json'], {
  cwd: outside,
  env: { AOC_REPO: repo, AOC_RUN_ID: 'npm-run' }
}), 'sessions with AOC_REPO/AOC_RUN_ID outside repo'), 'sessions with AOC_REPO/AOC_RUN_ID outside repo');
if (!envResolvedSessions.some(r => r.run_id === 'npm-run')) throw new Error(`AOC_REPO did not resolve sessions outside repo: ${JSON.stringify(envResolvedSessions)}`);
pass('AOC_REPO/AOC_RUN_ID resolve sessions/current outside repo');

const installedAoc = join(repo, '.orchestration', 'bin', 'aoc');
const installedEnvSessions = assertSessionRows(parseJsonResult(run(installedAoc, ['sessions', '--json'], {
  cwd: outside,
  env: { AOC_REPO: repo }
}), 'installed shim sessions with AOC_REPO outside repo'), 'installed shim sessions with AOC_REPO outside repo');
if (!installedEnvSessions.some(r => r.run_id === 'npm-run')) throw new Error(`installed shim AOC_REPO did not resolve repo: ${JSON.stringify(installedEnvSessions)}`);
const bundledEnvSessions = assertSessionRows(parseJsonResult(run(bundledSkillAoc, ['sessions', '--json'], {
  cwd: outside,
  env: { AOC_REPO: repo }
}), 'bundled skill shim sessions with AOC_REPO outside repo'), 'bundled skill shim sessions with AOC_REPO outside repo');
if (!bundledEnvSessions.some(r => r.run_id === 'npm-run')) throw new Error(`bundled skill shim AOC_REPO did not resolve repo: ${JSON.stringify(bundledEnvSessions)}`);
const nestedRepoDir = join(repo, 'nested', 'deeper');
run('mkdir', ['-p', nestedRepoDir]);
const installedNestedSessions = assertSessionRows(parseJsonResult(run(installedAoc, ['sessions', '--json'], {
  cwd: nestedRepoDir
}), 'installed shim sessions from nested git cwd'), 'installed shim sessions from nested git cwd');
if (!installedNestedSessions.some(r => r.run_id === 'npm-run')) throw new Error(`installed shim did not resolve nested git cwd: ${JSON.stringify(installedNestedSessions)}`);
const rootSkillAoc = join(ROOT, 'skills', 'agent-orchestration-skill', 'bin', 'aoc');
const bundledNestedSessions = assertSessionRows(parseJsonResult(run(rootSkillAoc, ['sessions', '--json'], {
  cwd: nestedRepoDir
}), 'source skill shim sessions from nested git cwd'), 'source skill shim sessions from nested git cwd');
if (!bundledNestedSessions.some(r => r.run_id === 'npm-run')) throw new Error(`source skill shim did not resolve nested git cwd: ${JSON.stringify(bundledNestedSessions)}`);
pass('installed and skill-local shims resolve AOC_REPO and nested git cwd');

parseJsonResult(run(installedAoc, ['init', '--run-id', 'parity-old', '--task', 'Installed shim old parity run'], { cwd: repo }), 'installed shim old parity init');
parseJsonResult(run(installedAoc, ['init', '--run-id', 'parity-new', '--task', 'Installed shim new parity run'], { cwd: repo }), 'installed shim new parity init');
const parityUseOld = parseJsonResult(run(installedAoc, ['use', 'parity-old', '--json'], { cwd: repo }), 'installed shim use old parity');
if (parityUseOld.run_id !== 'parity-old') throw new Error(`installed shim use old failed: ${JSON.stringify(parityUseOld)}`);
assertUsageScopedTo(parseJsonResult(run(installedAoc, ['usage', '--json'], { cwd: repo }), 'installed shim usage selected old'), 'parity-old', 'installed shim usage selected old');
const parityStats = parseJsonResult(run(installedAoc, ['stats', '--json'], { cwd: repo }), 'installed shim stats selected old');
if (parityStats.run_id !== 'parity-old') throw new Error(`installed shim stats did not honor selected old run: ${JSON.stringify(parityStats)}`);
assertUsageScopedTo(parseJsonResult(run(bundledSkillAoc, ['usage', '--json'], { cwd: repo }), 'bundled skill shim usage selected old'), 'parity-old', 'bundled skill shim usage selected old');
parseJsonResult(run(installedAoc, ['use', 'parity-new', '--json'], { cwd: repo }), 'installed shim use new parity');
assertUsageScopedTo(parseJsonResult(run(installedAoc, ['usage', '--json'], {
  cwd: repo,
  env: { AOC_RUN_ID: 'parity-old' }
}), 'installed shim usage env old'), 'parity-old', 'installed shim usage env old');
assertUsageScopedTo(parseJsonResult(run(bundledSkillAoc, ['usage', '--json'], {
  cwd: repo,
  env: { AOC_RUN_ID: 'parity-old' }
}), 'bundled skill shim usage env old'), 'parity-old', 'bundled skill shim usage env old');
pass('installed and skill-local run-scoped shims honor current and AOC_RUN_ID before latest');

const generatedShimInit = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['init', '--task', 'installed shim generated run id task'], { cwd: repo }), 'installed shim generated run init');
if (!generatedShimInit.run_id || generatedShimInit.run_id === 'latest' || generatedShimInit.run_id === '--task') throw new Error(`installed shim init misparsed run id: ${generatedShimInit.run_id}`);
if (!existsSync(generatedShimInit.state)) throw new Error('installed shim generated run state file missing');
pass('installed aoc init without --run-id generates a run id');
const generatedShimShortInit = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['init', 'Installed shim checkout task', '--json'], { cwd: repo }), 'installed shim short init');
if (!generatedShimShortInit.run_id || generatedShimShortInit.run_id === 'latest') throw new Error(`installed shim short init misparsed run id: ${generatedShimShortInit.run_id}`);
pass('installed aoc init "task" --json works');
const explicitShimInit = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['init', '--run', 'shim-run', '--task', 'installed shim explicit run task'], { cwd: repo }), 'installed shim explicit run init');
if (explicitShimInit.run_id !== 'shim-run') throw new Error(`installed shim --run was not honored: ${explicitShimInit.run_id}`);
pass('installed aoc init honors explicit --run');
const shimSessions = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['sessions', '--json'], { cwd: repo }), 'installed shim sessions');
if (!assertSessionRows(shimSessions, 'installed shim sessions').some(r => r.run_id === 'shim-run')) throw new Error('installed shim sessions did not list shim-run');
pass('installed aoc sessions --json works');
const shimVerboseSessions = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['sessions', '--verbose', '--json'], { cwd: repo }), 'installed shim sessions --verbose --json');
if (!assertSessionRows(shimVerboseSessions, 'installed shim sessions --verbose --json').some(r => r.run_id === 'shim-run')) {
  throw new Error(`installed shim sessions --verbose --json missing shim-run: ${JSON.stringify(shimVerboseSessions)}`);
}
pass('installed aoc sessions strips --verbose and preserves --json');
const shimCurrentRun = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['current', '--run-id', 'shim-run', '--json'], { cwd: repo }), 'installed shim current --run-id --json');
if (shimCurrentRun.run_id !== 'shim-run') throw new Error(`installed shim current did not honor --run-id: ${JSON.stringify(shimCurrentRun)}`);
pass('installed aoc current honors global --run-id');
assertInstalledShimHelp(run(join(repo, '.orchestration', 'bin', 'aoc'), ['help'], { cwd: repo }), installedShimHelpIncludes, 'npm-installed aoc shim');
pass('npm-installed aoc shim help covers command contract');

const directRepo = join(td, 'direct-bash-repo');
run('mkdir', ['-p', directRepo]);
run('git', ['init', '-q'], { cwd: directRepo });
run('bash', [join(ROOT, 'install.sh'), directRepo], { timeout: 240000 });
const directShim = join(directRepo, '.orchestration', 'bin', 'aoc');
assertInstalledShimHelp(run(directShim, ['help'], { cwd: directRepo }), installedShimHelpIncludes, 'direct bash install aoc shim');
const directInit = parseJsonResult(run(directShim, ['init', '--run-id', 'direct-run', '--task', 'Direct bash shim checkout task'], { cwd: directRepo }), 'direct bash shim init');
if (directInit.run_id !== 'direct-run') throw new Error(`direct bash shim init did not create direct-run: ${JSON.stringify(directInit)}`);
const directShortInit = parseJsonResult(run(directShim, ['init', 'Direct short task', '--json'], { cwd: directRepo }), 'direct bash shim short init');
if (!directShortInit.run_id || directShortInit.run_id === 'latest') throw new Error(`direct bash shim short init misparsed run id: ${JSON.stringify(directShortInit)}`);
if (!existsSync(directShortInit.state)) throw new Error('direct bash shim short init state file missing');
const directShortState = JSON.parse(readFileSync(directShortInit.state, 'utf8'));
if (directShortState.task !== 'Direct short task') throw new Error(`direct bash shim short init did not preserve task: ${JSON.stringify(directShortState)}`);
pass('direct bash install.sh aoc init "task" --json works');
const directSessions = assertSessionRows(parseJsonResult(run(directShim, ['sessions', '--json'], { cwd: directRepo }), 'direct bash shim sessions'), 'direct bash shim sessions');
if (!directSessions.some(r => r.run_id === 'direct-run')) throw new Error(`direct bash shim sessions missing direct-run: ${JSON.stringify(directSessions)}`);
const crossRepoSessions = assertSessionRows(parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['sessions', '--repo', directRepo, '--json'], { cwd: repo }), 'installed shim sessions --repo --json'), 'installed shim sessions --repo --json');
if (!crossRepoSessions.some(r => r.run_id === 'direct-run') || crossRepoSessions.some(r => r.run_id === 'shim-run')) {
  throw new Error(`installed shim sessions --repo did not switch roots cleanly: ${JSON.stringify(crossRepoSessions)}`);
}
pass('installed aoc sessions --repo strips global flag and switches root');
const directUse = parseJsonResult(run(directShim, ['use', 'direct-run', '--json'], { cwd: directRepo }), 'direct bash shim use');
if (directUse.run_id !== 'direct-run') throw new Error(`direct bash shim use did not select direct-run: ${JSON.stringify(directUse)}`);
const directCurrent = parseJsonResult(run(directShim, ['current', '--json'], { cwd: directRepo }), 'direct bash shim current');
if (directCurrent.run_id !== 'direct-run') throw new Error(`direct bash shim current did not report direct-run: ${JSON.stringify(directCurrent)}`);
const directCodexHome = join(td, 'direct-codex-home');
const directRolloutDir = join(directCodexHome, 'sessions', '2026', '05', '24');
mkdirSync(directRolloutDir, { recursive: true });
const directRollout = join(directRolloutDir, 'rollout-direct-shim-session.jsonl');
writeFileSync(directRollout, [
  JSON.stringify({ timestamp: '2026-05-24T11:00:00Z', type: 'session.started', session_id: 'direct-shim-session', cwd: directRepo, model: 'gpt-5' }),
  JSON.stringify({ timestamp: '2026-05-24T11:00:01Z', role: 'user', content: 'Direct shim checkout import' }),
  JSON.stringify({ timestamp: '2026-05-24T11:00:02Z', role: 'assistant', content: 'Direct shim import visible.' })
].join('\n') + '\n', 'utf8');
const directEmptyHome = join(td, 'direct-empty-home');
mkdirSync(directEmptyHome, { recursive: true });
const directImportEnv = { HOME: directEmptyHome };
const directImportRunOpts = { cwd: directRepo, env: directImportEnv, envUnset: ['AOC_CODEX_HOME', 'CODEX_HOME'] };
const directImport = parseJsonResult(run(directShim, ['import', directRollout, '--json'], directImportRunOpts), 'direct bash shim import');
if (directImport.run_id !== 'codex-direct-shim-session') throw new Error(`direct bash shim import used unstable run id: ${JSON.stringify(directImport)}`);
const directGlobalImport = parseJsonResult(run(directShim, ['--repo', directRepo, 'import', directRollout, '--json'], { cwd: td, env: directImportEnv, envUnset: ['AOC_CODEX_HOME', 'CODEX_HOME'] }), 'direct bash shim import with global repo');
if (directGlobalImport.run_id !== 'codex-direct-shim-session') throw new Error(`direct bash shim import with global repo lost explicit path target: ${JSON.stringify(directGlobalImport)}`);
const directLatestOpts = { cwd: directRepo, env: { HOME: directEmptyHome, AOC_CODEX_HOME: directCodexHome }, envUnset: ['CODEX_HOME'] };
const directLatestImport = parseJsonResult(run(directShim, ['import', '--no-current', 'latest', '--json'], directLatestOpts), 'direct bash shim import --no-current latest');
if (directLatestImport.run_id !== 'codex-direct-shim-session') throw new Error(`direct bash shim import --no-current latest did not pin latest in place: ${JSON.stringify(directLatestImport)}`);
const directLatestWatch = parseJsonResult(run(directShim, ['watch', '--no-current', 'latest', '--once', '--json'], directLatestOpts), 'direct bash shim watch --no-current latest --once');
if (!Array.isArray(directLatestWatch) || !directLatestWatch.some(r => r.run_id === 'codex-direct-shim-session')) throw new Error(`direct bash shim watch --no-current latest did not pin latest in place: ${JSON.stringify(directLatestWatch)}`);
pass('direct bash install.sh aoc shim pins latest after import/watch flags');
const directWatch = parseJsonResult(run(directShim, ['watch', directRollout, '--once', '--json'], directImportRunOpts), 'direct bash shim watch --once');
if (!Array.isArray(directWatch) || !directWatch.some(r => r.run_id === 'codex-direct-shim-session')) throw new Error(`direct bash shim watch did not refresh imported session: ${JSON.stringify(directWatch)}`);
const directSearch = parseJsonResult(run(directShim, ['search', 'checkout', '--json'], { cwd: directRepo }), 'direct bash shim search');
if (!Array.isArray(directSearch) || !directSearch.some(r => r.run_id === 'codex-direct-shim-session')) throw new Error(`direct bash shim search did not find imported session: ${JSON.stringify(directSearch)}`);
for (const command of codexSessionShimCommands) {
  const helpText = run(directShim, ['help'], { cwd: directRepo }).stdout;
  if (!helpText.includes(command)) throw new Error(`direct bash install shim help omitted Codex session command: ${command}`);
}
pass('direct bash install.sh aoc shim supports sessions/current/use/import/watch/search');

run('python3', [join(scripts, 'event_emit.py'), '--root', repo, '--run-id', 'npm-run', '--event', 'worker_dispatched', '--agent', 'batch_implementer_medium', '--reasoning', 'medium', '--summary', 'npm smoke worker']);
const dispatchDir = join(repo, '.orchestration', 'runs', 'npm-run', 'dispatches');
run('mkdir', ['-p', dispatchDir]);
writeFileSync(join(dispatchDir, 'P1.md'), 'TASK: npm smoke\nMUST_READ:\n- package.json\n', 'utf8');

const noFlag = run('node', [CLI], { cwd: repo });
if (!noFlag.stdout.includes('Orchestrator sessions') || !noFlag.stdout.includes('npm-run')) throw new Error('aoc no-flag behavior did not render repo sessions from cwd');
pass('aoc no-flag behavior resolves current repo');

const emptyRepo = join(td, 'empty-repo');
run('mkdir', ['-p', emptyRepo]);
run('git', ['init', '-q'], { cwd: emptyRepo });
const emptyGui = run('node', [CLI, 'gui', '--once'], { cwd: emptyRepo });
if (!emptyGui.stdout.includes('<!doctype html>') || !emptyGui.stdout.includes('Agentic Orchestration Control')) throw new Error('GUI pre-init view did not render');
const emptyTui = run('node', [CLI], { cwd: emptyRepo });
if (!emptyTui.stdout.includes('Agentic Orchestration Control') && !emptyTui.stdout.includes('Orchestrator sessions')) throw new Error('TUI pre-init view did not render');
pass('TUI/GUI render before init');

const fakeHome = join(td, 'fake-home');
const fakeHomeRolloutDir = join(fakeHome, '.codex', 'sessions', '2026', '05', '24');
mkdirSync(fakeHomeRolloutDir, { recursive: true });
const fakeHomeRollout = join(fakeHomeRolloutDir, 'rollout-home-discovery.jsonl');
writeFileSync(fakeHomeRollout, [
  JSON.stringify({ timestamp: '2030-01-01T00:00:00Z', type: 'session_meta', payload: { id: 'home-discovery-session', timestamp: '2030-01-01T00:00:00Z', cwd: emptyRepo, model: 'gpt-5' } }),
  JSON.stringify({ timestamp: '2030-01-01T00:00:01Z', type: 'event_msg', payload: { role: 'user', message: 'Home discovery checkout session' } }),
  JSON.stringify({ timestamp: '2030-01-01T00:00:02Z', type: 'event_msg', payload: { role: 'assistant', message: 'Default HOME Codex discovery is visible.' } })
].join('\n') + '\n', 'utf8');
utimesSync(fakeHomeRollout, new Date('2030-01-01T00:00:00Z'), new Date('2030-01-01T00:00:00Z'));
const fakeHomeEnv = { HOME: fakeHome };
const fakeHomeSnapshot = run('node', [CLI, '--repo', emptyRepo, '--snapshot'], {
  env: fakeHomeEnv,
  envUnset: ['AOC_CODEX_HOME', 'CODEX_HOME']
});
if (!fakeHomeSnapshot.stdout.includes('Home discovery checkout session') || !fakeHomeSnapshot.stdout.includes('codex-home-discovery-session')) {
  throw new Error(`TUI snapshot did not discover default HOME Codex session: ${fakeHomeSnapshot.stdout}`);
}
const fakeHomeGui = run('node', [CLI, 'gui', '--repo', emptyRepo, '--once'], {
  env: fakeHomeEnv,
  envUnset: ['AOC_CODEX_HOME', 'CODEX_HOME']
});
if (!fakeHomeGui.stdout.includes('Home discovery checkout session') || !fakeHomeGui.stdout.includes('codex-home-discovery-session')) {
  throw new Error('GUI pre-init view did not discover default HOME Codex session');
}
pass('pre-init TUI/GUI discover default HOME .codex sessions without AOC_CODEX_HOME');

const rootFallbackProbe = `
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, ${JSON.stringify(scripts)})
import codex_session_cli
import aoc_tui

original_exists = Path.exists
original_access = os.access

def assert_no_root_home(loader):
    homes = [str(p) for p in loader()]
    if "/root/.codex" in homes:
        raise AssertionError(f"inaccessible root fallback leaked into discovery homes: {homes}")

def exists_denied(self):
    if str(self) == "/root/.codex":
        raise PermissionError("stat denied")
    return original_exists(self)

def exists_true_for_root(self):
    if str(self) == "/root/.codex":
        return True
    return original_exists(self)

def access_denied(path, mode):
    if str(path) == "/root/.codex":
        raise PermissionError("access denied")
    return original_access(path, mode)

with tempfile.TemporaryDirectory() as home:
    os.environ["HOME"] = home
    os.environ.pop("AOC_CODEX_HOME", None)
    os.environ.pop("CODEX_HOME", None)
    with patch.object(Path, "exists", exists_denied):
        assert_no_root_home(lambda: codex_session_cli.codex_homes(None))
        assert_no_root_home(aoc_tui.codex_homes)
    with patch.object(Path, "exists", exists_true_for_root), patch("os.access", access_denied):
        assert_no_root_home(lambda: codex_session_cli.codex_homes(None))
        assert_no_root_home(aoc_tui.codex_homes)
`;
run('python3', ['-c', rootFallbackProbe]);
pass('Codex /root/.codex fallback is permission-safe');

const tuiScrollProbe = `
import sys
from pathlib import Path

sys.path.insert(0, ${JSON.stringify(scripts)})
import aoc_tui

sessions = [
    {
        "run_id": f"run-{i:02d}",
        "status": "active",
        "task": f"Task {i}",
        "last_event": f"event {i}",
        "source_path": f"/tmp/session-{i}.jsonl",
    }
    for i in range(20)
]

lines = aoc_tui.lines_sessions(Path("."), sessions, 12)
target = aoc_tui.selected_session_line(sessions, 12)
scroll = aoc_tui.keep_line_visible(0, target, 6, len(lines))
if scroll <= 0:
    raise AssertionError(f"session viewport did not scroll down: scroll={scroll}, target={target}")
if not (scroll <= target < scroll + 6):
    raise AssertionError(f"selected row outside viewport: scroll={scroll}, target={target}")

top_target = aoc_tui.selected_session_line(sessions, 0)
top_scroll = aoc_tui.keep_line_visible(scroll, top_target, 6, len(lines), context_before=2)
if top_scroll != 0:
    raise AssertionError(f"session viewport did not return to top: {top_scroll}")
`;
run('python3', ['-c', tuiScrollProbe]);
pass('TUI sessions viewport follows Up/Down selection');

const fakeCodexHome = join(td, 'fake-codex-home');
const rolloutDir = join(fakeCodexHome, 'sessions', '2026', '05', '24');
mkdirSync(rolloutDir, { recursive: true });
const rollout = join(rolloutDir, 'rollout-checkout.jsonl');
writeFileSync(rollout, [
  JSON.stringify({ timestamp: '2026-05-24T10:00:00Z', type: 'session.started', session_id: 'checkout-session', cwd: repo, model: 'gpt-5' }),
  JSON.stringify({ timestamp: '2026-05-24T10:00:01Z', role: 'user', content: 'Fix checkout flow' }),
  JSON.stringify({ timestamp: '2026-05-24T10:00:03Z', role: 'assistant', content: 'I will inspect checkout.' }),
  JSON.stringify({ timestamp: '2026-05-24T10:00:04Z', type: 'tool_call', name: 'shell', command: 'npm test', status: 'completed' }),
  '{"malformed":'
].join('\n') + '\n', 'utf8');
const imported = parseJsonResult(run('node', [CLI, 'import', '--repo', repo, '--json'], { env: { AOC_CODEX_HOME: fakeCodexHome } }), 'codex session import');
const importedCount = imported.imported ?? imported.imported_count ?? (Array.isArray(imported.sessions) ? imported.sessions.length : 0);
if (importedCount < 1) throw new Error(`fake AOC_CODEX_HOME import did not import a session: ${JSON.stringify(imported)}`);
const importedSessions = assertSessionRows(parseJsonResult(run('node', [CLI, 'sessions', '--repo', repo, '--json']), 'sessions after import'), 'sessions after import');
const importedRow = importedSessions.find(r => String(r.source || '').includes('codex') || String(r.run_id || '').startsWith('codex-'));
if (!importedRow) throw new Error(`imported Codex session not visible in sessions list: ${JSON.stringify(importedSessions)}`);
if (importedRow.run_id !== 'codex-checkout-session') throw new Error(`imported Codex session run id was not stable: ${JSON.stringify(importedRow)}`);
const importedGui = run('node', [CLI, 'gui', '--repo', repo, '--run-id', importedRow.run_id, '--once']);
if (!importedGui.stdout.includes('Agentic Orchestration Control') || !importedGui.stdout.includes('Fix checkout flow') || !importedGui.stdout.includes(importedRow.run_id)) throw new Error('GUI did not show stable imported Codex session id');
const importedTui = run('node', [CLI, 'snapshot', '--repo', repo, '--run-id', importedRow.run_id]);
if (!importedTui.stdout.includes('Fix checkout flow') || !importedTui.stdout.includes(importedRow.run_id)) throw new Error('TUI snapshot did not show stable imported Codex session id');
pass('fake AOC_CODEX_HOME import has stable run id across sessions, TUI, and GUI');

const nativeCollisionRunId = 'codex-native-collision';
const nativeCollision = parseJsonResult(run('node', [CLI, 'init', '--repo', repo, '--run-id', nativeCollisionRunId, '--task', 'Native collision state']), 'native collision init');
const nativeCollisionState = nativeCollision.state;
const beforeNativeCollision = JSON.parse(readFileSync(nativeCollisionState, 'utf8'));
const collisionHome = join(td, 'collision-codex-home');
const collisionRolloutDir = join(collisionHome, 'sessions', '2026', '05', '24');
mkdirSync(collisionRolloutDir, { recursive: true });
const collisionRollout = join(collisionRolloutDir, 'rollout-native-collision.jsonl');
writeFileSync(collisionRollout, [
  JSON.stringify({ timestamp: '2026-05-24T12:00:00Z', type: 'session.started', session_id: 'native-collision', cwd: repo, model: 'gpt-5' }),
  JSON.stringify({ timestamp: '2026-05-24T12:00:01Z', role: 'user', content: 'Codex collision import must not overwrite native state' })
].join('\n') + '\n', 'utf8');
const collisionImport = parseJsonResult(run('node', [CLI, 'import', collisionRollout, '--repo', repo, '--json'], { env: { AOC_CODEX_HOME: collisionHome } }), 'codex collision import');
const afterNativeCollision = JSON.parse(readFileSync(nativeCollisionState, 'utf8'));
if (collisionImport.run_id === nativeCollisionRunId) throw new Error(`Codex import reused native run id instead of avoiding collision: ${JSON.stringify(collisionImport)}`);
if (afterNativeCollision.task !== beforeNativeCollision.task || afterNativeCollision.mode !== beforeNativeCollision.mode || afterNativeCollision.status !== beforeNativeCollision.status || afterNativeCollision.codex_session) {
  throw new Error(`Codex import overwrote native collision state: before=${JSON.stringify(beforeNativeCollision)} after=${JSON.stringify(afterNativeCollision)}`);
}
pass('Codex import collision does not overwrite native run state');

const nativeSearchRunId = 'native-search-coverage';
const nativeStateNeedle = 'native-state-only-search-marker-aoc-20260524';
const nativeEventNeedle = 'native-event-only-search-marker-aoc-20260524';
const nativeSearchRun = parseJsonResult(run('node', [CLI, 'init', '--repo', repo, '--run-id', nativeSearchRunId, '--task', 'Native AOC search coverage']), 'native search coverage init');
const nativeSearchState = JSON.parse(readFileSync(nativeSearchRun.state, 'utf8'));
nativeSearchState.state_only_marker = nativeStateNeedle;
writeFileSync(nativeSearchRun.state, JSON.stringify(nativeSearchState, null, 2) + '\n', 'utf8');
const nativeStateSearchRows = parseJsonResult(run('node', [CLI, 'search', nativeStateNeedle, '--repo', repo, '--json']), 'native state search');
if (!Array.isArray(nativeStateSearchRows) || !nativeStateSearchRows.some(r => r.run_id === nativeSearchRunId && String(r.path || '').endsWith('state.json'))) {
  throw new Error(`aoc search did not find native state.json content: ${JSON.stringify(nativeStateSearchRows)}`);
}
run('python3', [join(scripts, 'event_emit.py'), '--root', repo, '--run-id', nativeSearchRunId, '--event', 'search_event_only', '--summary', nativeEventNeedle, '--no-state']);
if (readFileSync(nativeSearchRun.state, 'utf8').includes(nativeEventNeedle)) {
  throw new Error('event-only search marker leaked into state.json');
}
const nativeEventSearchRows = parseJsonResult(run('node', [CLI, 'search', nativeEventNeedle, '--repo', repo, '--json']), 'native events search');
if (!Array.isArray(nativeEventSearchRows) || !nativeEventSearchRows.some(r => r.run_id === nativeSearchRunId && String(r.path || '').endsWith('events.jsonl'))) {
  throw new Error(`aoc search did not find native events.jsonl content: ${JSON.stringify(nativeEventSearchRows)}`);
}
pass('aoc search --json searches native state.json and events.jsonl content');

const snap = run('node', [CLI, 'snapshot', '--repo', repo, '--run-id', 'npm-run']);
if (!snap.stdout.includes('Agentic Orchestration Control') && !snap.stdout.includes('Orchestrator sessions')) throw new Error('snapshot did not render dashboard');
pass('npm CLI snapshot command');

const gui = run('node', [CLI, 'gui', '--repo', repo, '--run-id', 'npm-run', '--once']);
if (!gui.stdout.includes('<!doctype html>') || !gui.stdout.includes('Agentic Orchestration Control')) throw new Error('GUI snapshot did not render HTML');
pass('npm CLI GUI snapshot command');

const guiAlias = run(join(repo, '.orchestration', 'bin', 'aoc-gui'), ['--run-id', 'npm-run', '--once'], { cwd: repo });
if (!guiAlias.stdout.includes('<!doctype html>') || !guiAlias.stdout.includes('Agentic Orchestration Control')) throw new Error('aoc-gui alias did not render HTML');
pass('installed aoc-gui alias command');

const npmGuiAliasResult = run(npmGuiAlias, ['--repo', repo, '--run-id', 'npm-run', '--once']);
if (!npmGuiAliasResult.stdout.includes('<!doctype html>') || !npmGuiAliasResult.stdout.includes('Agentic Orchestration Control')) throw new Error('npm aoc-gui bin alias did not render HTML');
pass('npm aoc-gui bin alias command');

const usage = run('node', [CLI, 'usage', '--repo', repo, '--run-id', 'npm-run']);
if (!usage.stdout.includes('Usage report')) throw new Error('usage command did not render report');
pass('npm CLI usage command');

const usageAlias = run(join(repo, '.orchestration', 'bin', 'aoc-usage'), ['--run-id', 'npm-run'], { cwd: repo });
if (!usageAlias.stdout.includes('Usage report')) throw new Error('aoc-usage alias did not render report');
pass('installed aoc-usage alias command');

const npmUsageAliasResult = run(npmUsageAlias, ['--repo', repo, '--run-id', 'npm-run']);
if (!npmUsageAliasResult.stdout.includes('Usage report')) throw new Error('npm aoc-usage bin alias did not render report');
pass('npm aoc-usage bin alias command');

const search = run('node', [CLI, 'search', 'checkout', '--repo', repo, '--json']);
const searchRows = parseJsonResult(search, 'search --json');
if (!Array.isArray(searchRows) || searchRows.length < 1) throw new Error(`search --json did not return hits for imported/native session data: ${search.stdout}`);
pass('aoc search --json searches local session data');

const budget = run('node', [CLI, 'budget', '12000', '--repo', repo, '--run-id', 'npm-run']);
if (!budget.stdout.includes('PASS') && !budget.stdout.includes('FAIL')) throw new Error('budget command did not render budget status');
pass('npm CLI budget command');

const packDir = join(td, 'pack');
const npmCache = join(td, 'npm-cache');
const npmHome = join(td, 'npm-home');
run('mkdir', ['-p', packDir]);
run('mkdir', ['-p', npmCache]);
run('mkdir', ['-p', npmHome]);
const npmIsolatedEnv = { npm_config_cache: npmCache, NPM_CONFIG_CACHE: npmCache, HOME: npmHome };
const packPayload = parseJsonResult(run('npm', ['pack', '--pack-destination', packDir, '--json'], {
  cwd: ROOT,
  timeout: 240000,
  env: npmIsolatedEnv
}), 'npm pack --json');
const packed = Array.isArray(packPayload) ? packPayload[0] : packPayload;
const packedFile = packed && packed.filename ? join(packDir, packed.filename) : '';
if (!packedFile || !existsSync(packedFile)) throw new Error(`npm pack did not create tarball in clean temp dir: ${JSON.stringify(packPayload)}`);
if (packed.name !== packageJson.name || packed.version !== packageJson.version) {
  throw new Error(`npm pack tarball does not match package.json: ${JSON.stringify({ expected: { name: packageJson.name, version: packageJson.version }, packed: { name: packed.name, version: packed.version, filename: packed.filename } })}`);
}
const packedPaths = new Set((packed.files || []).map(f => f.path));
for (const required of packageFiles) {
  if (!packedPaths.has(required)) throw new Error(`npm pack tarball missing command contract file: ${required}`);
}
pass('npm pack tarball smoke includes command contract assets and current package version');
const packedTarball = packedFile;
const packedHelp = run('npx', ['--yes', '--package', packedTarball, 'agentic-orchestration-control', '--help'], {
  cwd: ROOT,
  timeout: 240000,
  env: npmIsolatedEnv
});
assertHelpIncludes(packedHelp, codexSessionShimCommands);
const packedRepo = join(td, 'packed-npx-repo');
run('mkdir', ['-p', packedRepo]);
run('git', ['init', '-q'], { cwd: packedRepo });
run('npx', ['--yes', '--package', packedTarball, 'agentic-orchestration-control', 'install', packedRepo], {
  cwd: ROOT,
  timeout: 240000,
  env: npmIsolatedEnv
});
const packedShortInit = parseJsonResult(run('npx', ['--yes', '--package', packedTarball, 'agentic-orchestration-control', 'init', 'Packed tarball short task', '--repo', packedRepo, '--json'], {
  cwd: ROOT,
  timeout: 240000,
  env: npmIsolatedEnv
}), 'packed tarball npx short init');
if (!packedShortInit.run_id || !existsSync(packedShortInit.state)) throw new Error(`packed tarball npx short init did not create state: ${JSON.stringify(packedShortInit)}`);
const packedBundledSkillAoc = join(packedRepo, 'skills', 'agent-orchestration-skill', 'bin', 'aoc');
const packedBundledSessions = assertSessionRows(parseJsonResult(run(packedBundledSkillAoc, ['sessions', '--json'], {
  cwd: packedRepo,
  timeout: 240000,
  env: npmIsolatedEnv
}), 'packed installed bundled skill bin sessions'), 'packed installed bundled skill bin sessions');
if (!packedBundledSessions.some(r => r.run_id === packedShortInit.run_id)) {
  throw new Error(`packed installed bundled skill bin sessions did not see packed run: ${JSON.stringify(packedBundledSessions)}`);
}
const packedNativeNeedle = 'packed-native-search-marker-aoc-20260524';
const packedState = JSON.parse(readFileSync(packedShortInit.state, 'utf8'));
packedState.packed_native_search_marker = packedNativeNeedle;
writeFileSync(packedShortInit.state, JSON.stringify(packedState, null, 2) + '\n', 'utf8');
const packedNativeSearch = parseJsonResult(run('npx', ['--yes', '--package', packedTarball, 'agentic-orchestration-control', 'search', packedNativeNeedle, '--repo', packedRepo, '--json'], {
  cwd: ROOT,
  timeout: 240000,
  env: npmIsolatedEnv
}), 'packed tarball npx native search');
if (!Array.isArray(packedNativeSearch) || !packedNativeSearch.some(r => r.run_id === packedShortInit.run_id && String(r.path || '').endsWith('state.json'))) {
  throw new Error(`packed tarball npx search did not find native state content: ${JSON.stringify(packedNativeSearch)}`);
}
pass('fresh npm pack tarball npx help/install/short init/bundled shim/native search smoke works with isolated npm cache');

run(join(ROOT, 'skills', 'agent-orchestration-skill', 'bin', 'aoc'), ['publish-check']);
pass('skill-local aoc publish-check command');

console.log('ALL NPM CLI VALIDATION CHECKS PASSED');
process.exit(0);
