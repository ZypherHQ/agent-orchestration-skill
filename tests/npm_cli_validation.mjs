#!/usr/bin/env node
import { mkdtempSync, writeFileSync, existsSync, readFileSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const CLI = join(ROOT, 'bin', 'aoc.mjs');

function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, {
    cwd: opts.cwd || ROOT,
    encoding: 'utf8',
    timeout: opts.timeout || 180000,
    env: { ...process.env, ...(opts.env || {}) }
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

function requireCmd(cmd) {
  const res = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
  if (res.error) {
    throw new Error(`missing dependency: ${cmd}`);
  }
}

for (const cmd of ['bash', 'git', 'node', 'python3']) requireCmd(cmd);

const td = mkdtempSync(join(tmpdir(), 'aoc-npm-cli-'));
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
run('node', [CLI, 'init', '--repo', repo, '--run-id', 'npm-run', '--task', 'npm CLI smoke task']);
const generatedInit = parseJsonResult(run('node', [CLI, 'init', '--repo', repo, '--task', 'npm CLI generated run id task']), 'generated run init');
if (!generatedInit.run_id || generatedInit.run_id === 'latest') throw new Error(`init without --run-id should generate a unique run id, got ${generatedInit.run_id}`);
if (!existsSync(generatedInit.state)) throw new Error('generated run state file missing');
pass('npm CLI init without --run-id generates a run id');
const generatedShimInit = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['init', '--task', 'installed shim generated run id task'], { cwd: repo }), 'installed shim generated run init');
if (!generatedShimInit.run_id || generatedShimInit.run_id === 'latest' || generatedShimInit.run_id === '--task') throw new Error(`installed shim init misparsed run id: ${generatedShimInit.run_id}`);
if (!existsSync(generatedShimInit.state)) throw new Error('installed shim generated run state file missing');
pass('installed aoc init without --run-id generates a run id');
const explicitShimInit = parseJsonResult(run(join(repo, '.orchestration', 'bin', 'aoc'), ['init', '--run', 'shim-run', '--task', 'installed shim explicit run task'], { cwd: repo }), 'installed shim explicit run init');
if (explicitShimInit.run_id !== 'shim-run') throw new Error(`installed shim --run was not honored: ${explicitShimInit.run_id}`);
pass('installed aoc init honors explicit --run');
run('python3', [join(scripts, 'event_emit.py'), '--root', repo, '--run-id', 'npm-run', '--event', 'worker_dispatched', '--agent', 'batch_implementer_medium', '--reasoning', 'medium', '--summary', 'npm smoke worker']);
const dispatchDir = join(repo, '.orchestration', 'runs', 'npm-run', 'dispatches');
run('mkdir', ['-p', dispatchDir]);
writeFileSync(join(dispatchDir, 'P1.md'), 'TASK: npm smoke\nMUST_READ:\n- package.json\n', 'utf8');

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

const budget = run('node', [CLI, 'budget', '12000', '--repo', repo, '--run-id', 'npm-run']);
if (!budget.stdout.includes('PASS') && !budget.stdout.includes('FAIL')) throw new Error('budget command did not render budget status');
pass('npm CLI budget command');

run(join(ROOT, 'skills', 'agent-orchestration-skill', 'bin', 'aoc'), ['publish-check']);
pass('skill-local aoc publish-check command');

console.log('ALL NPM CLI VALIDATION CHECKS PASSED');
process.exit(0);
