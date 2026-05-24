#!/usr/bin/env python3
"""Local web control room for orchestration runs.

Filesystem-first GUI: reads .orchestration artifacts and renders a lightweight
local dashboard. It does not introspect Codex internals or upload data.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from aoc_tui import (  # noqa: E402
    codex_homes,
    discover_codex_sessions,
    is_discovered_codex_state,
    load_controls,
    load_events,
    load_memory,
    load_plan,
    load_sessions,
    load_state,
    session_path,
    source_badge,
)
from event_emit import latest_run_id, read_json, rebuild_index, run_dir  # noqa: E402
from orchestration_stats import run_stats  # noqa: E402
from usage_ledger import aggregate as usage_aggregate, derive_from_run, load_records  # noqa: E402
from codex_appserver_bridge import snapshot as codex_snapshot  # noqa: E402

CSS = """
:root{color-scheme:light;--bg:#f8fafc;--panel:#fff;--muted:#64748b;--ink:#0f172a;--line:#dbe3ee;--blue:#1d4ed8;--green:#15803d;--amber:#b45309;--red:#b91c1c;}
*{box-sizing:border-box}body{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
header{padding:18px 24px;border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:2}h1{margin:0;font-size:22px}header p{margin:6px 0 0;color:var(--muted);font-size:13px}.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--amber);margin-right:6px}.status-dot.live{background:var(--green)}.status-dot.err{background:var(--red)}
main{display:grid;grid-template-columns:320px minmax(0,1fr);gap:16px;padding:16px;max-width:1500px;margin:0 auto}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}.card h2,.section-box h3{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0;padding:12px 14px;border-bottom:1px solid var(--line)}.card .body{padding:14px}.section-box{border:1px solid var(--line);border-radius:6px;overflow:hidden;background:#fbfdff}.section-box .body{padding:12px}.sessions button{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);background:#fff;color:inherit;padding:11px 13px;cursor:pointer}.sessions button:hover,.sessions button.active{background:#eef6ff}.sessions button:focus-visible,.tabs button:focus-visible{outline:2px solid var(--blue);outline-offset:-2px}.runid,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.runid{font-size:12px;color:#1e3a8a}.task{font-weight:650;margin-top:4px}.meta,.small{font-size:12px;color:var(--muted)}.meta{margin-top:5px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.metric{padding:12px;border:1px solid var(--line);border-radius:6px;background:#fbfdff}.metric b{display:block;font-size:22px}.metric span{color:var(--muted);font-size:12px}.pill{display:inline-flex;align-items:center;border-radius:999px;padding:3px 8px;font-size:12px;font-weight:650;border:1px solid var(--line);background:#f8fafc}.ok{color:var(--green);background:#f0fdf4}.warn{color:var(--amber);background:#fffbeb}.bad{color:var(--red);background:#fef2f2}.info{color:var(--blue);background:#eff6ff}.phase{padding:11px;border:1px solid var(--line);border-radius:6px;margin-bottom:10px;background:#fbfdff}.phase strong{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.worker{padding:11px;border-left:4px solid var(--blue);background:#f8fafc;border-radius:6px;margin:10px 0}.bar{height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden;margin-top:8px}.bar>i{display:block;height:100%;background:var(--blue);border-radius:999px}.event{display:grid;grid-template-columns:170px 190px 150px 1fr;gap:10px;border-bottom:1px solid var(--line);padding:8px 0;font-size:13px;align-items:start}pre{white-space:pre-wrap;background:#111827;color:#e5e7eb;border-radius:6px;padding:12px;overflow:auto}.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}.tabs button{border:1px solid var(--line);border-radius:999px;padding:7px 10px;background:#fff;color:var(--ink);cursor:pointer}.tabs button.active{background:#eff6ff;color:var(--blue);border-color:#bfdbfe}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:1050px){main{grid-template-columns:1fr}.grid,.two{grid-template-columns:1fr}.event{grid-template-columns:1fr}.sessions{max-height:42vh;overflow:auto}}
.source-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:5px}.pathline{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
"""

TABS = ["overview", "dag", "workers", "events", "verification", "memory", "usage", "codex", "gates", "stats"]


def esc(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def status_class(status: Any) -> str:
    s = str(status or "").lower()
    if s in {"pass", "passed", "ok", "success", "completed", "done", "finished"}:
        return "ok"
    if s in {"fail", "failed", "blocked", "rejected", "error"}:
        return "bad"
    if s in {"waiting", "running", "pending"}:
        return "warn"
    return "info"


def source_label(row: dict[str, Any] | None) -> str:
    row = row or {}
    raw = row.get("source_type") or row.get("source") or "aoc"
    if isinstance(raw, dict):
        return str(raw.get("type") or "aoc")
    return str(raw)


def progress_for_agent(agent: dict[str, Any]) -> int:
    events = [e.get("event", "") for e in agent.get("events", [])]
    checks = [("worker_dispatched", 10), ("worker_started", 20), ("context_coverage_passed", 35), ("inspection_complete", 50), ("patch_applied", 65), ("command_started", 75), ("command_finished", 85), ("handoff_received", 95), ("handoff_validated", 100)]
    val = 0
    for name, score in checks:
        if name in events:
            val = max(val, score)
    status = str(agent.get("status", "")).lower()
    if status in {"passed", "completed", "success", "ok"}:
        return 100
    if status in {"failed", "blocked", "rejected"}:
        return max(val, 40)
    return val


def select_run(root: Path, explicit: str | None) -> str | None:
    if explicit and explicit != "latest":
        return explicit
    return latest_run_id(root)


def usage_summary(root: Path, run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return {"totals": {}, "rows": []}
    state = load_state(root, run_id)
    if state and is_discovered_codex_state(state):
        usage = state.get("usage") if isinstance(state.get("usage"), dict) else {}
        return {
            "totals": {
                "total_tokens": usage.get("total_tokens", 0),
                "estimated_tokens": usage.get("total_tokens", 0),
                "cost_usd": 0.0,
                "records": 1 if usage else 0,
            },
            "rows": [{"key": "codex_session", **usage}] if usage else [],
        }
    try:
        records = load_records(root, run_id)
        records.append(derive_from_run(root, run_id))
        return usage_aggregate(records, "source")
    except Exception as exc:
        return {"error": str(exc), "totals": {}, "rows": []}


def collect(root: Path, run_id: str | None = None, with_codex: bool = False, codex_url: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    sessions = load_sessions(root)
    selected = run_id if run_id and run_id != "latest" else (sessions[0].get("run_id") if sessions else select_run(root, run_id))
    state = load_state(root, selected)
    plan = load_plan(root, selected)
    events = load_events(root, selected, 160)
    controls = load_controls(root, selected)
    memory = load_memory(root, selected)
    is_discovered_codex = bool(state and is_discovered_codex_state(state))
    try:
        if selected and state and not is_discovered_codex:
            stats = run_stats(root, selected)
        else:
            stats = {"status": state.get("status"), "event_count": len(events), "worker_count": 0}
    except Exception as exc:
        stats = {"error": str(exc)}
    usage = usage_summary(root, selected)
    codex = {}
    if with_codex and selected and state and not is_discovered_codex:
        try:
            codex = codex_snapshot(root, selected, codex_url)
        except Exception as exc:
            codex = {"error": str(exc)}
    discovery = {"codex_homes": [str(p) for p in codex_homes()], "commands": import_commands()}
    return {"repo": str(root), "selected_run": selected, "sessions": sessions, "state": state, "plan": plan, "events": events, "controls": controls, "memory": memory, "stats": stats, "usage": usage, "codex": codex, "codex_enabled": with_codex, "discovery": discovery}


def import_commands() -> list[str]:
    return [
        "aoc import",
        'aoc init "Fix checkout flow"',
        "aoc sessions",
    ]


def empty_state_html() -> str:
    homes = ", ".join(esc(p) for p in codex_homes())
    commands = "".join(f"<li><span class=\"mono\">{esc(cmd)}</span></li>" for cmd in import_commands())
    return f'<div class="body small"><p>No AOC runs or Codex sessions were found.</p><p>Next steps:</p><ul>{commands}</ul><p>Codex home troubleshooting: checked {homes}. Set <span class="mono">AOC_CODEX_HOME</span> or <span class="mono">CODEX_HOME</span> if your Codex data lives elsewhere.</p></div>'


def render_fragment(data: dict[str, Any], tab: str = "overview") -> tuple[str, str, str, str]:
    sessions = data.get("sessions") or []
    selected = data.get("selected_run")
    state = data.get("state") or {}
    stats = data.get("stats") or {}
    usage = data.get("usage") or {}
    totals = usage.get("totals") or {}
    task = state.get("task") or "No selected orchestration run"

    sidebar = []
    if sessions:
        for s in sessions:
            rid = s.get("run_id")
            active = " active" if rid == selected else ""
            badge = source_badge(s)
            path = session_path(s)
            sidebar.append(f'<button class="{active}" data-run="{esc(rid)}"><div class="source-row"><span class="pill info">{esc(badge)}</span><span class="runid">{esc(rid)}</span></div><div class="task">{esc(s.get("task") or "Untitled run")}</div><div class="meta">{esc(s.get("status") or "unknown")} | workers {esc(s.get("worker_count",0))} | tests {esc(s.get("test_event_count",0))} | last {esc(s.get("last_event") or "")}</div><div class="meta pathline">{esc(path)}</div></button>')
    else:
        sidebar.append(empty_state_html())

    overview = f'''
      <div class="grid">
        <div class="metric"><b>{esc(source_badge(state))}</b><span>Source</span></div>
        <div class="metric"><b>{esc(state.get('status','unknown'))}</b><span>Status</span></div>
        <div class="metric"><b>{esc(stats.get('worker_count',0))}</b><span>Workers</span></div>
        <div class="metric"><b>{esc(stats.get('event_count',0))}</b><span>Events</span></div>
        <div class="metric"><b>{esc(state.get('codex_session_id') or state.get('mode') or '-')}</b><span>Session / mode</span></div>
        <div class="metric"><b>{esc(stats.get('handoff_count',0))}</b><span>Handoffs</span></div>
        <div class="metric"><b>{esc(totals.get('estimated_tokens', stats.get('token_pressure_estimate',0)))}</b><span>Estimated pressure tokens</span></div>
      </div>
      <div class="section-box" style="margin-top:14px"><h3>Session Source</h3><div class="body small"><div>type: <span class="mono">{esc(source_label(state))}</span></div><div>path: <span class="mono">{esc(state.get('codex_session_path') or state.get('state_path') or '')}</span></div><div>imported: <span class="mono">{esc(state.get('imported_at') or '')}</span></div></div></div>
      <div class="two" style="margin-top:14px">
        <div class="section-box"><h3>Classification</h3><div class="body"><pre>{esc(json.dumps(state.get('classification') or {}, indent=2, ensure_ascii=False))}</pre></div></div>
        <div class="section-box"><h3>Last Event</h3><div class="body"><pre>{esc(json.dumps(state.get('last_event') or {}, indent=2, ensure_ascii=False))}</pre></div></div>
      </div>'''

    phases = (data.get("plan") or {}).get("phases") or []
    dag = ''.join(f'<div class="phase"><strong>{esc(p.get("id"))}</strong> <span class="pill info">{esc(p.get("kind"))}</span> <span class="pill">{esc(p.get("agent"))}</span> <span class="pill">{esc(p.get("reasoning"))}</span><p>{esc(p.get("objective"))}</p><div class="small">depends on: {esc(", ".join(p.get("depends_on") or []) or "root")}</div></div>' for p in phases) or '<p class="small">No DAG plan found.</p>'

    agents = state.get("agents") if isinstance(state.get("agents"), dict) else {}
    workers = ''.join(f'<div class="worker"><strong>{esc(name)}</strong> <span class="pill {status_class(a.get("status"))}">{esc(a.get("status","unknown"))}</span> <span class="pill">{esc(a.get("reasoning",""))}</span><div class="bar"><i style="width:{progress_for_agent(a)}%"></i></div><div class="small">scope: {esc(", ".join(a.get("scope") or []))}</div><div class="small">files: {esc(", ".join((a.get("files") or [])[:8]))}</div></div>' for name, a in sorted(agents.items())) or '<p class="small">No worker activity recorded.</p>'

    events = ''.join(f'<div class="event"><span class="mono">{esc(e.get("ts"))}</span><span>{esc(e.get("event"))}</span><span>{esc(e.get("agent"))}</span><span>{esc(e.get("summary"))}</span></div>' for e in (data.get("events") or [])[-100:]) or '<p class="small">No events yet.</p>'
    verification_items = state.get("verification") if isinstance(state.get("verification"), list) else []
    verification_events = [
        e for e in (data.get("events") or [])
        if str(e.get("event", "")).startswith(("verification_", "quality_gate", "test_"))
        or "test" in str(e.get("event", "")).lower()
    ]
    verification = ""
    if verification_items:
        verification += ''.join(
            f'<div class="event"><span>{esc((v or {}).get("command") or (v or {}).get("name") or "check") if isinstance(v, dict) else esc(v)}</span><span>{esc((v or {}).get("result") or (v or {}).get("status") or "unknown") if isinstance(v, dict) else ""}</span><span></span><span>{esc((v or {}).get("evidence") or (v or {}).get("summary") or "") if isinstance(v, dict) else ""}</span></div>'
            for v in verification_items[-30:]
        )
    if verification_events:
        verification += ''.join(f'<div class="event"><span class="mono">{esc(e.get("ts"))}</span><span>{esc(e.get("event"))}</span><span>{esc(e.get("status"))}</span><span>{esc(e.get("summary"))}</span></div>' for e in verification_events[-40:])
    if not verification:
        verification = '<p class="small">No verification records or test events found.</p>'
    memory = '<pre>' + esc('\n'.join(data.get("memory") or [])) + '</pre>'
    rows = usage.get("rows") or []
    usage_html = f'<div class="grid"><div class="metric"><b>{esc(totals.get("total_tokens",0))}</b><span>Real/imported tokens</span></div><div class="metric"><b>~{esc(totals.get("estimated_tokens",0))}</b><span>Estimated pressure</span></div><div class="metric"><b>${float(totals.get("cost_usd",0.0)):.4f}</b><span>Cost</span></div></div>' + ''.join(f'<div class="event"><span>{esc(r.get("key"))}</span><span>real {esc(r.get("total_tokens",0))}</span><span>est {esc(r.get("estimated_tokens",0))}</span><span>${float(r.get("cost_usd",0.0)):.4f}</span></div>' for r in rows)
    gates = ''.join(f'<div class="phase"><strong>{esc(g.get("gate_id"))}</strong> <span class="pill {status_class(g.get("status"))}">{esc(g.get("status"))}</span><p>{esc(g.get("reason"))}</p><div class="small">options: {esc("; ".join(g.get("options") or []))}</div></div>' for g in (data.get("controls") or [])) or '<p class="small">No STOP gates recorded.</p>'
    stats_html = '<pre>' + esc(json.dumps(stats, indent=2, ensure_ascii=False)) + '</pre>'

    codex_data = data.get("codex") or {}
    if data.get("codex_enabled"):
        codex_status = (codex_data.get("status") or {}) if isinstance(codex_data, dict) else {}
        codex_link = (codex_data.get("link") or {}) if isinstance(codex_data, dict) else {}
        codex_url_status = "ok" if (codex_status.get("meta_methods") or {}).get("ok") else "local"
        codex_html = (
            '<div class="grid">'
            f'<div class="metric"><b>{esc("linked" if codex_link else "none")}</b><span>Codex Thread Link</span></div>'
            f'<div class="metric"><b>{esc("yes" if codex_status.get("codex_bin") else "no")}</b><span>codex binary</span></div>'
            f'<div class="metric"><b>{esc(codex_url_status)}</b><span>codexui/app-server URL</span></div>'
            '</div>'
            '<div class="two" style="margin-top:14px">'
            f'<div class="section-box"><h3>Linked Thread</h3><div class="body"><pre>{esc(json.dumps(codex_link, indent=2, ensure_ascii=False))}</pre></div></div>'
            f'<div class="section-box"><h3>Bridge Status</h3><div class="body"><pre>{esc(json.dumps(codex_status, indent=2, ensure_ascii=False))}</pre></div></div>'
            '</div>'
        )
    else:
        codex_html = '<p class="small">Codex app-server/codexui bridge is disabled for this GUI session.</p><pre>aoc gui --with-codex --codex-url http://127.0.0.1:&lt;port&gt;</pre><p class="small">AOC keeps orchestration state in .orchestration/. Codex app-server integration is optional and should stay localhost-only unless you explicitly configure auth and remote access.</p>'

    tabs = ''.join(f'<button class="{"active" if tab == name else ""}" data-tab="{name}">{esc(name.title())}</button>' for name in TABS)
    content = {"overview": overview, "dag": dag, "workers": workers, "events": events, "verification": verification, "memory": memory, "usage": usage_html, "codex": codex_html, "gates": gates, "stats": stats_html}.get(tab, overview)
    return "".join(sidebar), tabs, content, str(task)


CLIENT_JS = r"""
const initial = __INITIAL__;
let data = initial;
let currentRun = initial.selected_run || "";
let currentTab = new URLSearchParams(location.search).get("tab") || "overview";
let source = null;
const token = new URLSearchParams(location.search).get("token") || "";
function esc(v){return String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
function statusClass(v){const s=String(v||"").toLowerCase(); if(["pass","passed","ok","success","completed","done","finished"].includes(s)) return "ok"; if(["fail","failed","blocked","rejected","error"].includes(s)) return "bad"; if(["waiting","running","pending"].includes(s)) return "warn"; return "info";}
function sourceType(s){const raw=(s&&s.source_type)||(s&&s.source)||""; return String(raw&&typeof raw==="object"?(raw.type||""):raw);}
function sourceBadge(s){const src=sourceType(s).toLowerCase(); const rid=String((s&&s.run_id)||""); if(rid.startsWith("codex:")||src.includes("codex_session")||src==="codex"||src==="codex_cli") return "CODEX"; if(src.includes("app_server")||src.includes("appserver")) return "APP_SERVER"; return "AOC";}
function sessionPath(s){return String((s&&s.codex_session_path)||(s&&s.session_path)||(s&&s.path)||"");}
function progress(a){const names=(a.events||[]).map(e=>e.event||""); const checks=[["worker_dispatched",10],["worker_started",20],["context_coverage_passed",35],["inspection_complete",50],["patch_applied",65],["command_started",75],["command_finished",85],["handoff_received",95],["handoff_validated",100]]; let v=0; for(const [n,s] of checks){if(names.includes(n)) v=Math.max(v,s);} const st=String(a.status||"").toLowerCase(); if(["passed","completed","success","ok"].includes(st)) return 100; if(["failed","blocked","rejected"].includes(st)) return Math.max(v,40); return v;}
function metric(v,l){return `<div class="metric"><b>${esc(v)}</b><span>${esc(l)}</span></div>`;}
function pre(v){return `<pre>${esc(JSON.stringify(v || {}, null, 2))}</pre>`;}
function emptyState(){const commands=(data.discovery&&data.discovery.commands)||["aoc import","aoc init \"Fix checkout flow\"","aoc sessions"]; const homes=((data.discovery&&data.discovery.codex_homes)||[]).join(", "); return `<div class="body small"><p>No AOC runs or Codex sessions were found.</p><p>Next steps:</p><ul>${commands.map(c=>`<li><span class="mono">${esc(c)}</span></li>`).join("")}</ul><p>Codex home troubleshooting: checked ${esc(homes)}. Set <span class="mono">AOC_CODEX_HOME</span> or <span class="mono">CODEX_HOME</span> if needed.</p></div>`;}
function renderSessions(){const box=document.getElementById("sessions"); const sessions=data.sessions||[]; if(!sessions.length){box.innerHTML=emptyState(); return;} box.innerHTML=sessions.map(s=>`<button class="${s.run_id===data.selected_run?'active':''}" data-run="${esc(s.run_id)}"><div class="source-row"><span class="pill info">${esc(sourceBadge(s))}</span><span class="runid">${esc(s.run_id)}</span></div><div class="task">${esc(s.task||"Untitled run")}</div><div class="meta">${esc(s.status||"unknown")} | workers ${esc(s.worker_count||0)} | tests ${esc(s.test_event_count||0)} | last ${esc(s.last_event||"")}</div><div class="meta pathline">${esc(sessionPath(s))}</div></button>`).join(""); box.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>selectRun(b.dataset.run)));}
function renderTabs(){const box=document.getElementById("tabs"); box.innerHTML=__TABS__.map(t=>`<button class="${t===currentTab?'active':''}" data-tab="${t}">${esc(t[0].toUpperCase()+t.slice(1))}</button>`).join(""); box.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{currentTab=b.dataset.tab; history.replaceState(null,"",urlFor(false)); render();}));}
function renderContent(){const state=data.state||{}, stats=data.stats||{}, usage=data.usage||{}, totals=usage.totals||{}; const events=data.events||[]; const controls=data.controls||[]; const plan=data.plan||{}; const agents=(state.agents&&typeof state.agents==="object")?state.agents:{}; let html="";
 if(currentTab==="overview"){html=`<div class="grid">${metric(sourceBadge(state),"Source")}${metric(state.status||"unknown","Status")}${metric(stats.worker_count||0,"Workers")}${metric(stats.event_count||0,"Events")}${metric(state.codex_session_id||state.mode||"-","Session / mode")}${metric(totals.estimated_tokens ?? stats.token_pressure_estimate ?? 0,"Estimated pressure tokens")}</div><div class="section-box" style="margin-top:10px"><h3>Session Source</h3><div class="body small"><div>type: <span class="mono">${esc(sourceType(state)||"aoc")}</span></div><div>path: <span class="mono">${esc(state.codex_session_path||state.state_path||"")}</span></div><div>imported: <span class="mono">${esc(state.imported_at||"")}</span></div></div></div><div class="two" style="margin-top:10px"><div class="section-box"><h3>Classification</h3><div class="body">${pre(state.classification||{})}</div></div><div class="section-box"><h3>Last Event</h3><div class="body">${pre(state.last_event||{})}</div></div></div>`;}
 else if(currentTab==="dag"){const phases=plan.phases||[]; html=phases.length?phases.map(p=>`<div class="phase"><strong>${esc(p.id)}</strong> <span class="pill info">${esc(p.kind)}</span> <span class="pill">${esc(p.agent)}</span> <span class="pill">${esc(p.reasoning)}</span><p>${esc(p.objective)}</p><div class="small">depends on: ${esc((p.depends_on||[]).join(", ")||"root")}</div></div>`).join(""):'<p class="small">No DAG plan found.</p>';}
 else if(currentTab==="workers"){const names=Object.keys(agents).sort(); html=names.length?names.map(n=>{const a=agents[n]||{}; return `<div class="worker"><strong>${esc(n)}</strong> <span class="pill ${statusClass(a.status)}">${esc(a.status||"unknown")}</span> <span class="pill">${esc(a.reasoning||"")}</span><div class="bar"><i style="width:${progress(a)}%"></i></div><div class="small">scope: ${esc((a.scope||[]).join(", "))}</div><div class="small">files: ${esc((a.files||[]).slice(0,8).join(", "))}</div></div>`}).join(""):'<p class="small">No worker activity recorded.</p>';}
 else if(currentTab==="events"){html=events.slice(-100).map(e=>`<div class="event"><span class="mono">${esc(e.ts)}</span><span>${esc(e.event)}</span><span>${esc(e.agent)}</span><span>${esc(e.summary)}</span></div>`).join("")||'<p class="small">No events yet.</p>';}
 else if(currentTab==="verification"){const checks=Array.isArray(state.verification)?state.verification:[]; const evs=events.filter(e=>String(e.event||"").startsWith("verification_")||String(e.event||"").startsWith("quality_gate")||String(e.event||"").startsWith("test_")||String(e.event||"").toLowerCase().includes("test")); html=checks.slice(-30).map(v=>`<div class="event"><span>${esc(v.command||v.name||v.check||"check")}</span><span>${esc(v.result||v.status||"unknown")}</span><span></span><span>${esc(v.evidence||v.summary||"")}</span></div>`).join("")+evs.slice(-40).map(e=>`<div class="event"><span class="mono">${esc(e.ts)}</span><span>${esc(e.event)}</span><span>${esc(e.status)}</span><span>${esc(e.summary)}</span></div>`).join(""); if(!html) html='<p class="small">No verification records or test events found.</p>';}
 else if(currentTab==="memory"){html=`<pre>${esc((data.memory||[]).join("\n"))}</pre>`;}
 else if(currentTab==="usage"){const rows=usage.rows||[]; html=`<div class="grid">${metric(totals.total_tokens||0,"Real/imported tokens")}${metric(totals.estimated_tokens||0,"Estimated pressure")}${metric("$"+Number(totals.cost_usd||0).toFixed(4),"Cost")}</div>`+rows.map(r=>`<div class="event"><span>${esc(r.key)}</span><span>real ${esc(r.total_tokens||0)}</span><span>est ${esc(r.estimated_tokens||0)}</span><span>$${Number(r.cost_usd||0).toFixed(4)}</span></div>`).join("");}
 else if(currentTab==="gates"){html=controls.length?controls.map(g=>`<div class="phase"><strong>${esc(g.gate_id)}</strong> <span class="pill ${statusClass(g.status)}">${esc(g.status)}</span><p>${esc(g.reason)}</p><div class="small">options: ${esc((g.options||[]).join("; "))}</div></div>`).join(""):'<p class="small">No STOP gates recorded.</p>';}
 else if(currentTab==="codex"){const discovery=data.discovery||{}; html=`<div class="section-box"><h3>Discovery / Import</h3><div class="body"><pre>${esc(JSON.stringify(discovery,null,2))}</pre></div></div>`+(data.codex_enabled?pre(data.codex||{}):'<p class="small">Codex app-server/codexui bridge is disabled for this GUI session.</p><pre>aoc gui --with-codex --codex-url http://127.0.0.1:&lt;port&gt;</pre>');}
 else {html=pre(stats);}
 document.getElementById("content").innerHTML=html;}
function render(){document.getElementById("repoLine").innerHTML=`<span id="liveDot" class="status-dot live"></span>${esc(data.repo)} | <span class="mono">${esc(data.selected_run||"no-run")}</span>`; document.getElementById("panelTitle").textContent=(data.state&&data.state.task)||"No selected orchestration run"; renderSessions(); renderTabs(); renderContent();}
function urlFor(includePath=true){const qs=new URLSearchParams(); if(currentRun) qs.set("run",currentRun); qs.set("tab",currentTab); if(token) qs.set("token",token); return (includePath?"/":"?")+qs.toString();}
async function selectRun(run){currentRun=run||""; history.replaceState(null,"",urlFor(false)); await fetchSnapshot(); startStream();}
async function fetchSnapshot(){const qs=new URLSearchParams(); if(currentRun) qs.set("run",currentRun); if(token) qs.set("token",token); const res=await fetch("/api/snapshot?"+qs.toString()); if(res.ok){data=await res.json(); currentRun=data.selected_run||currentRun; render();}}
function startStream(){if(source) source.close(); if(!window.EventSource){setInterval(fetchSnapshot, __POLL_MS__); return;} const qs=new URLSearchParams(); if(currentRun) qs.set("run",currentRun); if(token) qs.set("token",token); source=new EventSource("/events?"+qs.toString()); source.onmessage=(ev)=>{data=JSON.parse(ev.data); currentRun=data.selected_run||currentRun; render();}; source.onerror=()=>{const dot=document.getElementById("liveDot"); if(dot) dot.className="status-dot err";};}
render(); startStream();
"""


def render_page(data: dict[str, Any], tab: str = "overview", live: bool = True, refresh_interval: float = 2.0) -> str:
    selected = data.get("selected_run")
    sidebar, tabs, content, task = render_fragment(data, tab if tab in TABS else "overview")
    script = ""
    if live:
        initial = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        js = CLIENT_JS.replace("__INITIAL__", initial)
        js = js.replace("__TABS__", json.dumps(TABS))
        js = js.replace("__POLL_MS__", str(max(1000, int(refresh_interval * 1000))))
        script = f"<script>{js}</script>"
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Agentic Orchestration Control</title><style>{CSS}</style></head><body><header><h1>Agentic Orchestration Control</h1><p id="repoLine"><span class="status-dot{' live' if live else ''}"></span>{esc(data.get('repo'))} | <span class="mono">{esc(selected or 'no-run')}</span></p></header><main><aside id="sessions" class="card sessions"><h2>Orchestrator Sessions</h2>{sidebar}</aside><section><div class="card"><h2 id="panelTitle">{esc(task)}</h2><div class="body"><div id="tabs" class="tabs">{tabs}</div><div id="content">{content}</div></div></div></section></main>{script}</body></html>'''


class Handler(BaseHTTPRequestHandler):
    root: Path = Path.cwd()
    default_run: str | None = None
    with_codex: bool = False
    codex_url: str | None = None
    auth_token: str | None = None
    refresh_interval: float = 2.0

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def authorized(self, qs: dict[str, list[str]]) -> bool:
        if not self.auth_token:
            return True
        supplied = (qs.get("token") or [""])[0]
        header = self.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            supplied = header[7:].strip()
        return secrets.compare_digest(str(supplied), str(self.auth_token))

    def send(self, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_unauthorized(self) -> None:
        body = b"Unauthorized\n"
        self.send_response(401)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def stream(self, run_id: str | None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        while True:
            data = collect(self.root, run_id, self.with_codex, self.codex_url)
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            try:
                self.wfile.write(f"data: {body}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            time.sleep(max(0.5, self.refresh_interval))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if not self.authorized(qs):
            self.send_unauthorized()
            return
        run_id = (qs.get("run") or [self.default_run])[0]
        tab = (qs.get("tab") or ["overview"])[0]
        if parsed.path == "/events":
            self.stream(run_id)
            return
        if parsed.path == "/api/discovery":
            payload = {
                "codex_homes": [str(p) for p in codex_homes()],
                "sessions": discover_codex_sessions(root=self.root),
                "commands": import_commands(),
            }
            self.send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/import-help":
            payload = {
                "safe": True,
                "side_effects": "none",
                "commands": import_commands(),
                "note": "This endpoint only exposes local import guidance. Run imports from the CLI so file trust and run ownership stay explicit.",
            }
            self.send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        data = collect(self.root, run_id, self.with_codex, self.codex_url)
        if parsed.path.startswith("/api"):
            self.send(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        self.send(render_page(data, tab, live=True, refresh_interval=self.refresh_interval).encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Open local web GUI for orchestration sessions")
    ap.add_argument("--repo", "--root", dest="root", default=".")
    ap.add_argument("--run", "--run-id", dest="run_id", default="latest")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--once", action="store_true", help="Print a single HTML snapshot and exit")
    ap.add_argument("--refresh-interval", type=float, default=2.0, help="Live browser refresh interval in seconds")
    ap.add_argument("--allow-remote", action="store_true", help="Allow non-localhost binding. Requires --auth-token.")
    ap.add_argument("--auth-token", default=os.environ.get("AOC_GUI_TOKEN"), help="Bearer/query token required for GUI requests")
    ap.add_argument("--rebuild-index", action="store_true", help="Explicitly rebuild .orchestration/index.json before reading")
    ap.add_argument("--with-codex", action="store_true", help="Show optional Codex app-server/codexui bridge status")
    ap.add_argument("--codex-url", default=None, help="Optional codexui/app-server HTTP URL, for example http://127.0.0.1:3000")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.rebuild_index:
        rebuild_index(root)
    rid = None if args.run_id == "latest" else args.run_id
    data = collect(root, rid, args.with_codex, args.codex_url)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    if args.once:
        print(render_page(data, live=False, refresh_interval=args.refresh_interval))
        return
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if args.host not in local_hosts:
        if not args.allow_remote:
            raise SystemExit("Refusing non-localhost bind without --allow-remote.")
        if not args.auth_token:
            raise SystemExit("--allow-remote requires --auth-token or AOC_GUI_TOKEN.")
    Handler.root = root
    Handler.default_run = rid
    Handler.with_codex = args.with_codex
    Handler.codex_url = args.codex_url
    Handler.auth_token = args.auth_token
    Handler.refresh_interval = max(0.5, args.refresh_interval)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    host, port = server.server_address
    token_qs = f"?token={quote(args.auth_token)}" if args.auth_token else ""
    url = f"http://{host}:{port}/{token_qs}"
    print(f"Agentic Orchestration Control GUI: {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping GUI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
