"""Web dashboard for the Kick Points Miner.

A lightweight Flask dashboard (ported from the kick-points project) that
visualizes the state of every monitored channel. The monitor threads push
their status into a shared context; the dashboard only reads it, so it can
never break the mining loop.
"""

import threading
from datetime import datetime

from flask import Flask, Response, jsonify, request
from loguru import logger
from .prediction_logger import prediction_logger

data_lock = threading.Lock()

# Shared state, updated by ChannelMonitor threads.
shared_context = {
    "status": "Initializing",          # Active / Initializing
    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "channels": {},                    # username -> info dict
    "total_messages_sent": 0,
    "total_errors": 0,
}

app = Flask(__name__)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#0b0e11">
<title>KICKMINER · Dashboard</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%2353fc18'/%3E%3Cpath d='M9 7h4v7l6-7h5l-7 8.5L24 25h-5l-6-8v8H9z' fill='%230b0e11'/%3E%3C/svg%3E">
<style>
:root {
    --green: #53fc18;
    --green-dim: rgba(83,252,24,.12);
    --green-border: rgba(83,252,24,.32);
    --bg: #0b0e11;
    --bg-2: #12151a;
    --card: #171a1f;
    --card-hover: #1c2026;
    --border: #262a31;
    --text: #efeff1;
    --text-2: #adadb8;
    --muted: #7a7a85;
    --red: #f04747;
    --red-dim: rgba(240,71,71,.14);
    --orange: #faa61a;
    --orange-dim: rgba(250,166,26,.14);
    --blue: #4aa8ff;
    --radius: 12px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    font-family: 'Inter', 'Segoe UI', -apple-system, system-ui, sans-serif;
    background: radial-gradient(1200px 500px at 50% -200px, rgba(83,252,24,.08), transparent), var(--bg);
    color: var(--text);
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
}
button, input, select { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--green); outline-offset: 2px; }
.container { max-width: 1280px; margin: 0 auto; padding: 0 20px 40px; }

/* ---------- Top bar ---------- */
.topbar {
    position: sticky; top: 0; z-index: 20;
    background: rgba(11,14,17,.82);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
}
.topbar-inner {
    max-width: 1280px; margin: 0 auto; padding: 12px 20px;
    display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-logo {
    width: 30px; height: 30px; border-radius: 8px; background: var(--green);
    display: grid; place-items: center;
}
.brand-logo svg { width: 18px; height: 18px; fill: var(--bg); }
.brand h1 { font-size: 20px; font-weight: 800; letter-spacing: 1.5px; }
.brand h1 span { color: var(--green); }
.brand small { display: block; font-size: 10px; letter-spacing: 1.2px; text-transform: uppercase; color: var(--muted); margin-top: -2px; }
.top-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.updated { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }

.pill {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 5px 12px; border-radius: 999px;
    font-size: 11px; font-weight: 700; letter-spacing: .6px; text-transform: uppercase;
    border: 1px solid var(--border); color: var(--text-2); background: var(--bg-2);
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill.ok { color: var(--green); background: var(--green-dim); border-color: var(--green-border); }
.pill.ok .dot { animation: pulse 2s infinite; }
.pill.warn { color: var(--orange); background: var(--orange-dim); border-color: rgba(250,166,26,.35); }
.pill.bad { color: var(--red); background: var(--red-dim); border-color: rgba(240,71,71,.35); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }

.btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 12px; border-radius: 8px; cursor: pointer;
    background: var(--bg-2); border: 1px solid var(--border);
    font-size: 12px; font-weight: 600; color: var(--text-2);
    transition: all .15s;
}
.btn:hover { border-color: var(--green); color: var(--green); background: var(--green-dim); }
.btn svg { width: 14px; height: 14px; }

.banner {
    display: none; margin: 14px 0 0; padding: 10px 14px; border-radius: 10px;
    background: var(--red-dim); border: 1px solid rgba(240,71,71,.35); color: #ff9a9a; font-size: 13px;
}
.banner.show { display: block; }

/* ---------- Stats ---------- */
.stats {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px; margin: 20px 0;
}
.stat {
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 16px; display: flex; gap: 12px; align-items: center;
}
.stat-ico {
    width: 38px; height: 38px; border-radius: 10px; flex-shrink: 0;
    display: grid; place-items: center; font-size: 18px; background: var(--green-dim);
}
.stat.red .stat-ico { background: var(--red-dim); }
.stat.orange .stat-ico { background: var(--orange-dim); }
.stat.blue .stat-ico { background: rgba(74,168,255,.14); }
.stat .v { font-size: 22px; font-weight: 800; line-height: 1.1; font-variant-numeric: tabular-nums; }
.stat .l { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .6px; margin-top: 2px; }
.stat .sub { font-size: 11px; color: var(--text-2); }

/* ---------- Toolbar ---------- */
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
.search {
    flex: 1 1 220px; min-width: 180px; position: relative;
}
.search input {
    width: 100%; padding: 9px 12px 9px 34px; border-radius: 10px;
    background: var(--card); border: 1px solid var(--border);
    font-size: 13px;
}
.search input::placeholder { color: var(--muted); }
.search input:focus { border-color: var(--green-border); outline: none; }
.search svg { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); width: 15px; height: 15px; color: var(--muted); }
.search kbd {
    position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
    font-size: 10px; color: var(--muted); border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px;
}
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
    padding: 6px 12px; border-radius: 999px; cursor: pointer;
    background: var(--card); border: 1px solid var(--border);
    font-size: 12px; font-weight: 600; color: var(--text-2); transition: all .15s;
}
.chip .n { color: var(--muted); margin-left: 4px; font-variant-numeric: tabular-nums; }
.chip:hover { border-color: #3a3f48; }
.chip.active { background: var(--green-dim); border-color: var(--green-border); color: var(--green); }
.chip.active .n { color: var(--green); }
select.sort {
    padding: 8px 10px; border-radius: 10px; background: var(--card); border: 1px solid var(--border);
    font-size: 12px; cursor: pointer;
}

/* ---------- Layout ---------- */
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 18px; align-items: start; }
@media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 12px; }

/* ---------- Channel card ---------- */
.card {
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 16px 12px; position: relative; overflow: hidden; transition: border-color .15s, background .15s, transform .15s;
    animation: fadeIn .25s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
.card:hover { background: var(--card-hover); border-color: #343942; }
.card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: #444; }
.card.online::before { background: var(--green); }
.card.error::before { background: var(--red); }
.card.flash { border-color: var(--green); box-shadow: 0 0 0 1px var(--green-border), 0 0 24px rgba(83,252,24,.12); }

.c-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.c-name { display: flex; align-items: center; gap: 8px; min-width: 0; }
.c-name a { font-weight: 700; font-size: 15px; color: var(--text); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.c-name a:hover { color: var(--green); }
.sdot { width: 8px; height: 8px; border-radius: 50%; background: #555; flex-shrink: 0; }
.sdot.online { background: var(--green); box-shadow: 0 0 8px rgba(83,252,24,.6); animation: pulse 2s infinite; }
.sdot.error { background: var(--red); }
.tag { font-size: 10px; font-weight: 700; letter-spacing: .5px; text-transform: uppercase; padding: 2px 7px; border-radius: 5px; flex-shrink: 0; }
.tag.online { background: var(--green-dim); color: var(--green); }
.tag.offline { background: rgba(255,255,255,.07); color: var(--muted); }
.tag.error { background: var(--red-dim); color: var(--red); }
.watch {
    display: inline-flex; align-items: center; gap: 4px; padding: 4px 9px; border-radius: 7px;
    border: 1px solid var(--border); color: var(--text-2); text-decoration: none; font-size: 11px; font-weight: 600;
    transition: all .15s; flex-shrink: 0;
}
.watch:hover { border-color: var(--green); color: var(--green); background: var(--green-dim); }
.watch svg { width: 11px; height: 11px; }

.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0 8px; }
.m .mv { font-size: 17px; font-weight: 800; font-variant-numeric: tabular-nums; }
.m .ml { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
.m .mv.g { color: var(--green); }
.m .mv.r { color: var(--red); }

.wr { margin: 4px 0 2px; }
.wr-bar { height: 5px; border-radius: 3px; background: rgba(240,71,71,.35); overflow: hidden; }
.wr-bar > i { display: block; height: 100%; background: var(--green); border-radius: 3px; transition: width .4s; }
.wr-txt { display: flex; justify-content: space-between; font-size: 10px; color: var(--muted); margin-top: 3px; }

.pred {
    margin-top: 10px; padding: 9px 10px; border-radius: 8px;
    background: var(--green-dim); border-left: 3px solid var(--green); font-size: 12px;
}
.pred.won { background: rgba(83,252,24,.18); }
.pred.lost, .pred.failed { background: var(--red-dim); border-left-color: var(--red); }
.pred.refunded, .pred.idle { background: rgba(255,255,255,.04); border-left-color: #555; color: var(--muted); }
.pred-t { font-weight: 700; margin-bottom: 4px; line-height: 1.3; word-break: break-word; }
.pred-r { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; color: var(--text-2); }
.badge {
    font-size: 9px; font-weight: 800; letter-spacing: .5px; text-transform: uppercase;
    padding: 2px 6px; border-radius: 4px; background: var(--green-dim); color: var(--green); border: 1px solid var(--green-border);
}
.badge.lost, .badge.failed { background: var(--red-dim); color: var(--red); border-color: rgba(240,71,71,.4); }
.badge.refunded, .badge.cancelled { background: rgba(255,255,255,.08); color: var(--muted); border-color: var(--border); }
.badge.pending, .badge.active { background: var(--orange-dim); color: var(--orange); border-color: rgba(250,166,26,.4); }

.c-foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 10px; font-size: 11px; color: var(--muted); }
.c-foot .last { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.hist-btn { background: none; border: none; cursor: pointer; color: var(--text-2); font-size: 11px; font-weight: 600; padding: 2px 4px; border-radius: 4px; flex-shrink: 0; }
.hist-btn:hover { color: var(--green); }
.hist { margin-top: 8px; border-top: 1px dashed var(--border); padding-top: 8px; display: none; }
.hist.open { display: block; }
.hist-row { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; padding: 3px 0; color: var(--text-2); }
.hist-row .ht { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.hist-row .hm { color: var(--muted); font-variant-numeric: tabular-nums; flex-shrink: 0; }

/* ---------- Side panel ---------- */
.panel { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; position: sticky; top: 76px; }
@media (max-width: 1000px) { .panel { position: static; } }
.panel h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .8px; color: var(--text-2); margin-bottom: 10px; display: flex; justify-content: space-between; }
.feed { list-style: none; max-height: 480px; overflow-y: auto; }
.feed li { padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 12px; display: grid; gap: 3px; }
.feed li:last-child { border-bottom: none; }
.feed .fh { display: flex; justify-content: space-between; gap: 8px; }
.feed .fc { font-weight: 700; color: var(--text); }
.feed .ft { color: var(--muted); font-variant-numeric: tabular-nums; }
.feed .fd { color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { text-align: center; padding: 48px 16px; color: var(--muted); }
.empty .ico { font-size: 40px; margin-bottom: 8px; }
.empty .tx { font-size: 14px; }

/* ---------- Skeleton ---------- */
.sk { height: 150px; border-radius: var(--radius); background: linear-gradient(90deg, var(--card) 25%, #20242a 50%, var(--card) 75%); background-size: 200% 100%; animation: sh 1.4s infinite; }
@keyframes sh { to { background-position: -200% 0; } }

/* ---------- Toasts ---------- */
.toasts { position: fixed; right: 16px; bottom: 16px; display: grid; gap: 8px; z-index: 50; max-width: calc(100vw - 32px); }
.toast {
    background: var(--bg-2); border: 1px solid var(--green-border); border-left: 3px solid var(--green);
    border-radius: 10px; padding: 10px 14px; font-size: 13px; min-width: 240px; max-width: 360px;
    box-shadow: 0 8px 28px rgba(0,0,0,.45); animation: tin .25s ease;
}
.toast.lost { border-color: rgba(240,71,71,.4); border-left-color: var(--red); }
.toast b { display: block; margin-bottom: 2px; }
.toast span { color: var(--text-2); font-size: 12px; }
@keyframes tin { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: none; } }

.footer { text-align: center; margin-top: 28px; color: var(--muted); font-size: 12px; }

@media (max-width: 600px) {
    .container { padding: 0 12px 32px; }
    .topbar-inner { padding: 10px 12px; }
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: repeat(2, 1fr); }
    .updated { display: none; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
</head>
<body>

<header class="topbar">
    <div class="topbar-inner">
        <div class="brand">
            <div class="brand-logo"><svg viewBox="0 0 24 24"><path d="M5 3h4v7l6-7h5l-7 8.5L21 21h-5l-6-8v8H5z"/></svg></div>
            <div><h1><span>KICK</span>MINER</h1><small>Channel points farmer</small></div>
        </div>
        <div class="top-actions">
            <span class="updated" id="updated">Connecting…</span>
            <span class="pill warn" id="conn"><span class="dot"></span><span id="conn-t">Connecting</span></span>
            <button class="btn" id="pause" type="button" aria-pressed="false" title="Pause or resume auto-refresh">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/></svg>
                <span id="pause-t">Pause</span>
            </button>
        </div>
    </div>
</header>

<main class="container" aria-live="polite">
    <div class="banner" id="banner" role="alert">⚠️ Can't reach the miner right now. Showing the last known data — retrying automatically.</div>

    <section class="stats" id="stats" aria-label="Summary"></section>

    <div class="toolbar">
        <div class="search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
            <input id="q" type="search" placeholder="Search channels…" autocomplete="off" aria-label="Search channels">
            <kbd>/</kbd>
        </div>
        <div class="chips" id="chips" role="tablist" aria-label="Filter channels"></div>
        <select class="sort" id="sort" aria-label="Sort channels">
            <option value="status">Sort: Status</option>
            <option value="name">Sort: Name</option>
            <option value="votes">Sort: Most votes</option>
            <option value="winrate">Sort: Win rate</option>
            <option value="msgs">Sort: Messages</option>
        </select>
    </div>

    <div class="layout">
        <section id="channels" aria-label="Channels">
            <div class="grid"><div class="sk"></div><div class="sk"></div><div class="sk"></div></div>
        </section>
        <aside class="panel" aria-label="Recent prediction activity">
            <h2><span>Recent predictions</span><span id="feed-n" style="color:var(--muted)"></span></h2>
            <ul class="feed" id="feed"><li class="fd">Waiting for activity…</li></ul>
        </aside>
    </div>

    <div class="footer">Auto-refresh every 5s · Started <span id="started">—</span></div>
</main>

<div class="toasts" id="toasts" aria-live="polite"></div>

<script>
(function () {
"use strict";

const REFRESH_MS = 5000;
const EXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';

const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = n => (Number(n) || 0).toLocaleString();
const store = {
    get(k, d) { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
};

let state = { data: null, filter: store.get("km_filter", "all"), sort: store.get("km_sort", "status"), q: "" };
let paused = false, lastOk = 0, timer = null, firstLoad = true;
const expanded = new Set();
const prev = {};      // username -> {voted, won, lost}
const flashUntil = {}; // username -> ts

// ---------- helpers ----------
function winStats(i) {
    const w = i.predictions_won || 0, l = i.predictions_lost || 0, d = w + l;
    return { w, l, d, rate: d ? Math.round(w / d * 100) : null };
}
function statusOf(i) { return i.status || "offline"; }
function fmtTime(v) { return (!v || v === "N/A" || v === "None" || v === "null") ? "—" : v; }

// ---------- toasts ----------
function toast(title, body, kind) {
    const el = document.createElement("div");
    el.className = "toast " + (kind || "");
    el.innerHTML = "<b>" + esc(title) + "</b><span>" + esc(body) + "</span>";
    $("toasts").appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 300); }, 6000);
    while ($("toasts").children.length > 4) $("toasts").firstChild.remove();
}

function detectChanges(channels) {
    Object.keys(channels).forEach(name => {
        const i = channels[name], cur = { voted: i.predictions_voted || 0, won: i.predictions_won || 0, lost: i.predictions_lost || 0 };
        const p = prev[name];
        if (p && !firstLoad) {
            const t = i.active_prediction && i.active_prediction.title ? i.active_prediction.title : "prediction";
            if (cur.voted > p.voted) { toast("🗳️ Voted in " + name, t); flashUntil[name] = Date.now() + 6000; }
            if (cur.won > p.won) { toast("🏆 Won in " + name, t); flashUntil[name] = Date.now() + 6000; }
            if (cur.lost > p.lost) { toast("❌ Lost in " + name, t, "lost"); }
        }
        prev[name] = cur;
    });
}

// ---------- render: stats ----------
function renderStats(data, names) {
    const ch = data.channels || {};
    let live = 0, votes = 0, won = 0, lost = 0, avail = 0;
    names.forEach(n => {
        const i = ch[n];
        if (statusOf(i) === "online") live++;
        votes += i.predictions_voted || 0; won += i.predictions_won || 0; lost += i.predictions_lost || 0;
        if (i.active_prediction && ["voted", "active", "pending", undefined].includes(i.active_prediction.status)) avail++;
    });
    const d = won + lost, wr = d ? Math.round(won / d * 100) : null;
    const items = [
        { c: "", ico: "📺", v: names.length, l: "Channels", s: live + " live now" },
        { c: "", ico: "🗳️", v: num(votes), l: "Votes placed", s: avail ? avail + " open now" : "none open" },
        { c: "", ico: "🏆", v: wr === null ? "—" : wr + "%", l: "Win rate", s: won + "W · " + lost + "L" },
        { c: "blue", ico: "💬", v: num(data.total_messages_sent), l: "Messages sent", s: "all channels" },
        { c: (data.total_errors ? "red" : "orange"), ico: data.total_errors ? "⚠️" : "✅", v: num(data.total_errors), l: "Errors", s: data.total_errors ? "check logs" : "all good" }
    ];
    $("stats").innerHTML = items.map(x =>
        '<div class="stat ' + x.c + '"><div class="stat-ico">' + x.ico + '</div><div><div class="v">' + x.v +
        '</div><div class="l">' + x.l + '</div><div class="sub">' + esc(x.s) + '</div></div></div>').join("");
}

// ---------- render: chips ----------
const FILTERS = [
    ["all", "All", () => true],
    ["online", "Live", i => statusOf(i) === "online"],
    ["offline", "Offline", i => statusOf(i) === "offline"],
    ["error", "Errors", i => statusOf(i) === "error" || (i.errors || 0) > 0],
    ["pred", "Predictions", i => !!(i.active_prediction || (i.predictions_voted || 0) > 0)]
];
function renderChips(ch, names) {
    $("chips").innerHTML = FILTERS.map(([k, label, fn]) => {
        const n = names.filter(x => fn(ch[x])).length;
        return '<button type="button" role="tab" aria-selected="' + (state.filter === k) + '" class="chip' + (state.filter === k ? " active" : "") +
            '" data-f="' + k + '">' + label + '<span class="n">' + n + '</span></button>';
    }).join("");
}

// ---------- render: cards ----------
function predBlock(i) {
    const p = i.active_prediction;
    if (!p) {
        return i.predictions_available ? '<div class="pred idle"><div class="pred-r">No active predictions</div></div>' : "";
    }
    const st = (p.status || "voted").toLowerCase();
    const pts = p.points_won > 0 ? ' · <b style="color:var(--green)">+' + num(p.points_won) + ' pts</b>' : "";
    const amt = p.amount > 0 ? ' · ' + num(p.amount) + ' pts' : "";
    const win = p.winning_outcome ? ' · Winner: ' + esc(p.winning_outcome) : "";
    return '<div class="pred ' + esc(st) + '"><div class="pred-t">' + esc(p.title || "Active prediction") + '</div><div class="pred-r">' +
        (p.voted_outcome ? 'Voted: <b>' + esc(p.voted_outcome) + '</b>' : 'Open to vote') + amt + pts +
        ' <span class="badge ' + esc(st) + '">' + esc(st) + '</span>' + win + '</div></div>';
}

function histBlock(name, i) {
    const h = i.prediction_history || [];
    if (!h.length) return "";
    const open = expanded.has(name);
    const rows = h.map(e => '<div class="hist-row"><span class="ht" title="' + esc(e.title) + '">' + esc(e.title || "Prediction") +
        (e.voted_outcome ? " → " + esc(e.voted_outcome) : "") + '</span><span class="hm"><span class="badge ' + esc(e.status) + '">' + esc(e.status || "?") + '</span> ' + esc(e.timestamp || "") + '</span></div>').join("");
    return '<div class="hist' + (open ? " open" : "") + '" id="h-' + esc(name) + '">' + rows + '</div>';
}

function card(name, i) {
    const s = statusOf(i), ws = winStats(i), h = i.prediction_history || [];
    const flash = (flashUntil[name] || 0) > Date.now() ? " flash" : "";
    const bar = ws.d ? '<div class="wr"><div class="wr-bar"><i style="width:' + ws.rate + '%"></i></div><div class="wr-txt"><span>Win rate</span><span>' + ws.rate + '% (' + ws.d + ' decided)</span></div></div>' : "";
    return '<article class="card ' + s + flash + '" data-name="' + esc(name) + '">' +
        '<div class="c-top"><div class="c-name"><span class="sdot ' + s + '"></span><a href="https://kick.com/' + encodeURIComponent(name) + '" target="_blank" rel="noopener">' + esc(name) + '</a>' +
        '<span class="tag ' + s + '">' + (s === "online" ? "Live" : s) + '</span></div>' +
        '<a class="watch" href="https://kick.com/' + encodeURIComponent(name) + '" target="_blank" rel="noopener" title="Watch on Kick" aria-label="Watch ' + esc(name) + ' on Kick">' + EXT + '</a></div>' +
        '<div class="metrics">' +
        '<div class="m"><div class="mv">' + num(i.predictions_voted) + '</div><div class="ml">Votes</div></div>' +
        '<div class="m"><div class="mv g">' + ws.w + '<span style="color:var(--muted);font-weight:500"> / </span><span class="r" style="color:var(--red)">' + ws.l + '</span></div><div class="ml">Won / Lost</div></div>' +
        '<div class="m"><div class="mv">' + num(i.messages_sent) + '</div><div class="ml">Messages</div></div></div>' +
        bar + predBlock(i) +
        '<div class="c-foot"><span class="last" title="Last chat message">' + (i.last_message ? "💬 " + esc(i.last_message) : "Updated " + esc(fmtTime(i.last_update))) + '</span>' +
        (h.length ? '<button class="hist-btn" type="button" data-h="' + esc(name) + '">' + (expanded.has(name) ? "Hide" : "History (" + h.length + ")") + '</button>' : "") +
        ((i.errors || 0) > 0 ? '<span class="tag error" title="Errors">' + i.errors + ' err</span>' : "") + '</div>' +
        histBlock(name, i) + '</article>';
}

const SORTS = {
    status: (ch) => (a, b) => ({ online: 0, error: 1, offline: 2 }[statusOf(ch[a])] ?? 3) - ({ online: 0, error: 1, offline: 2 }[statusOf(ch[b])] ?? 3) || a.localeCompare(b),
    name: () => (a, b) => a.localeCompare(b),
    votes: ch => (a, b) => (ch[b].predictions_voted || 0) - (ch[a].predictions_voted || 0) || a.localeCompare(b),
    winrate: ch => (a, b) => ((winStats(ch[b]).rate ?? -1) - (winStats(ch[a]).rate ?? -1)) || a.localeCompare(b),
    msgs: ch => (a, b) => (ch[b].messages_sent || 0) - (ch[a].messages_sent || 0) || a.localeCompare(b)
};

function renderChannels(ch, all) {
    const fn = (FILTERS.find(f => f[0] === state.filter) || FILTERS[0])[2];
    const q = state.q.trim().toLowerCase();
    const names = all.filter(n => fn(ch[n]) && (!q || n.toLowerCase().includes(q))).sort((SORTS[state.sort] || SORTS.status)(ch));
    const box = $("channels");
    if (!all.length) {
        box.innerHTML = '<div class="empty"><div class="ico">⏳</div><div class="tx">Waiting for the first channel check…</div></div>';
    } else if (!names.length) {
        box.innerHTML = '<div class="empty"><div class="ico">🔍</div><div class="tx">No channels match your filter.</div></div>';
    } else {
        box.innerHTML = '<div class="grid">' + names.map(n => card(n, ch[n])).join("") + '</div>';
    }
}

// ---------- render: feed ----------
function renderFeed(ch, all) {
    const rows = [];
    all.forEach(n => (ch[n].prediction_history || []).forEach((e, idx) => rows.push({ n, e, idx })));
    rows.sort((a, b) => String(b.e.timestamp || "").localeCompare(String(a.e.timestamp || "")) || a.idx - b.idx);
    const top = rows.slice(0, 15);
    $("feed-n").textContent = rows.length ? rows.length + " total" : "";
    $("feed").innerHTML = top.length ? top.map(r =>
        '<li><div class="fh"><span class="fc">' + esc(r.n) + '</span><span class="ft">' + esc(r.e.timestamp || "") + '</span></div>' +
        '<div class="fd" title="' + esc(r.e.title) + '">' + esc(r.e.title || "Prediction") + '</div>' +
        '<div><span class="badge ' + esc(r.e.status) + '">' + esc(r.e.status || "?") + '</span>' +
        (r.e.voted_outcome ? ' <span class="fd">' + esc(r.e.voted_outcome) + (r.e.amount ? " · " + num(r.e.amount) + " pts" : "") + '</span>' : "") + '</div></li>').join("")
        : '<li class="fd">No predictions yet. Votes will show up here.</li>';
}

// ---------- main render ----------
function render(data) {
    const ch = data.channels || {};
    const all = Object.keys(ch);
    detectChanges(ch);
    firstLoad = false;

    const active = data.status === "Active";
    $("conn").className = "pill " + (active ? "ok" : "warn");
    $("conn-t").textContent = active ? "Active" : (data.status || "Starting");
    $("started").textContent = data.started_at || "—";

    renderStats(data, all);
    renderChips(ch, all);
    renderChannels(ch, all);
    renderFeed(ch, all);
}

// ---------- fetch loop ----------
async function refresh() {
    try {
        const res = await fetch("/api/data", { cache: "no-store" });
        if (!res.ok) throw new Error(res.status);
        state.data = await res.json();
        lastOk = Date.now();
        $("banner").classList.remove("show");
        render(state.data);
    } catch (e) {
        $("banner").classList.add("show");
        $("conn").className = "pill bad";
        $("conn-t").textContent = "Offline";
    }
}
function schedule() { clearInterval(timer); if (!paused) timer = setInterval(refresh, REFRESH_MS); }
setInterval(() => {
    if (!lastOk) return;
    const s = Math.round((Date.now() - lastOk) / 1000);
    $("updated").textContent = paused ? "Paused" : "Updated " + (s < 2 ? "just now" : s + "s ago");
}, 1000);

// ---------- events ----------
function rerender() { if (state.data) render(state.data); }
$("q").addEventListener("input", e => { state.q = e.target.value; rerender(); });
$("sort").value = state.sort;
$("sort").addEventListener("change", e => { state.sort = e.target.value; store.set("km_sort", state.sort); rerender(); });
$("chips").addEventListener("click", e => {
    const b = e.target.closest("[data-f]"); if (!b) return;
    state.filter = b.dataset.f; store.set("km_filter", state.filter); rerender();
});
$("channels").addEventListener("click", e => {
    const b = e.target.closest("[data-h]"); if (!b) return;
    const n = b.dataset.h;
    expanded.has(n) ? expanded.delete(n) : expanded.add(n);
    rerender();
});
$("pause").addEventListener("click", () => {
    paused = !paused;
    $("pause").setAttribute("aria-pressed", paused);
    $("pause-t").textContent = paused ? "Resume" : "Pause";
    if (!paused) refresh();
    schedule();
});
document.addEventListener("keydown", e => {
    if (e.key === "/" && document.activeElement !== $("q")) { e.preventDefault(); $("q").focus(); }
    if (e.key === "Escape" && document.activeElement === $("q")) { $("q").value = ""; state.q = ""; $("q").blur(); rerender(); }
});
document.addEventListener("visibilitychange", () => { if (!document.hidden && !paused) refresh(); });

refresh(); schedule();
})();
</script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    # Served as-is (not via Jinja) so JS template literals can't be misparsed.
    resp = Response(HTML_TEMPLATE, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/data")
def get_data():
    with data_lock:
        # Create a copy of channels data and ensure all channels have the active_predictions field
        channels_data = {}
        for username, channel_info in shared_context["channels"].items():
            channels_data[username] = dict(channel_info)  # Copy the dict
            # Ensure active_predictions field exists - set to True if there's an active prediction
            channels_data[username]["active_predictions"] = bool(channel_info.get("active_prediction"))
            
        return jsonify({
            "status": shared_context["status"],
            "started_at": shared_context["started_at"],
            "channels": channels_data,
            "total_messages_sent": shared_context["total_messages_sent"],
            "total_errors": shared_context["total_errors"],
        })


@app.route("/health")
def health():
    return jsonify({"ok": True, "status": shared_context["status"]})


@app.route("/api/predictions")
def get_predictions():
    """Get prediction statistics and recent events."""
    try:
        stats = prediction_logger.get_prediction_stats()
        recent_events = prediction_logger.get_recent_predictions(hours=24)
        
        return jsonify({
            "stats": stats,
            "recent_events": recent_events[:20],  # Last 20 events
            "success": True
        })
    except Exception as e:
        logger.error(f"Error fetching prediction data: {e}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500


@app.route("/api/predictions/<username>")
def get_channel_predictions(username: str):
    """Get prediction data for a specific channel."""
    try:
        stats = prediction_logger.get_prediction_stats(username)
        recent_events = prediction_logger.get_recent_predictions(username, hours=168)  # Last week
        
        return jsonify({
            "username": username,
            "stats": stats,
            "recent_events": recent_events,
            "success": True
        })
    except Exception as e:
        logger.error(f"Error fetching prediction data for {username}: {e}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500


@app.route("/api/points/<username>", methods=["GET"])
def get_points(username: str):
    """Get channel points for a user/channel."""
    try:
        from .config import Config
        from .client import KickClient
        config = Config.load()
        client = KickClient(config.authorization)
        points_data = client.get_channel_points(username)
        return jsonify({
            "username": username,
            "points_data": points_data,
            "success": points_data is not None
        })
    except Exception as e:
        logger.error(f"Error getting points for {username}: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/points/<username>/set", methods=["POST"])
def set_points(username: str):
    """Set channel points for a user/channel."""
    try:
        data = request.get_json(silent=True) or {}
        amount = int(data.get("amount") or data.get("points") or request.args.get("amount") or 0)
        from .config import Config
        from .client import KickClient
        config = Config.load()
        client = KickClient(config.authorization)
        success = client.set_channel_points(username, amount)
        return jsonify({
            "username": username,
            "amount": amount,
            "success": success
        })
    except Exception as e:
        logger.error(f"Error setting points for {username}: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/points/<username>/update", methods=["POST"])
def update_points(username: str):
    """Update channel points by delta."""
    try:
        data = request.get_json(silent=True) or {}
        delta = int(data.get("delta") or data.get("amount") or request.args.get("delta") or 0)
        from .config import Config
        from .client import KickClient
        config = Config.load()
        client = KickClient(config.authorization)
        success = client.update_channel_points(username, delta)
        return jsonify({
            "username": username,
            "delta": delta,
            "success": success
        })
    except Exception as e:
        logger.error(f"Error updating points for {username}: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/debug/<username>")
def debug_channel_data(username: str):
    """Debug endpoint to inspect raw channel data."""
    try:
        from .config import Config
        from .client import KickClient
        config = Config.load()
        client = KickClient(config.authorization)
        channel_data = client.get_channel(username)
        points_data = client.get_channel_points(username)
        prediction_data = client.get_latest_prediction_data(username)
        result = {
            "username": username,
            "channel_data": channel_data,
            "points_data": points_data,
            "prediction_data": prediction_data,
            "success": True
        }
        if channel_data or points_data:
            return jsonify(result)
        else:
            return jsonify({
                "username": username,
                "error": "No channel data found",
                "data": result,
                "success": False
            }), 404
            
    except Exception as e:
        logger.error(f"Error debugging channel data for {username}: {e}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500


def register_channel(username: str) -> None:
    """Add a channel to the dashboard (shown as pending until first check)."""
    with data_lock:
        shared_context["channels"].setdefault(username, {
            "status": "offline",
            "messages_sent": 0,
            "errors": 0,
            "last_update": "N/A",
            "last_message": None,
            "predictions_voted": 0,
            "predictions_won": 0,
            "predictions_lost": 0,
            "predictions_refunded": 0,
            "predictions_available": False,
            "active_prediction": None,
            "prediction_history": [],
        })


def update_channel(username: str, status: str,
                   sent_message: str | None = None,
                   prediction_info: dict | None = None) -> None:
    """Update dashboard state for one channel after a check.

    status == "prediction_vote" increments the prediction counter and logs the vote
    without changing the channel's online/offline status.
    """
    with data_lock:
        info = shared_context["channels"].setdefault(username, {
            "status": "offline",
            "messages_sent": 0,
            "predictions_voted": 0,
            "predictions_won": 0,
            "predictions_lost": 0,
            "predictions_refunded": 0,
            "errors": 0,
            "last_update": "N/A",
            "last_message": None,
            "predictions_available": False,
            "active_prediction": None,
            "prediction_history": [],
        })
        
        if status == "prediction_vote":
            info["predictions_voted"] += 1
            info["last_update"] = datetime.now().strftime("%H:%M:%S")
            if prediction_info:
                info["active_prediction"] = prediction_info
                info["predictions_available"] = True
                # Add to history (keep last 10)
                history_entry = {
                    "id": prediction_info.get("id"),
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "title": prediction_info.get("title", "Unknown"),
                    "voted_outcome": prediction_info.get("voted_outcome"),
                    "amount": prediction_info.get("amount", 0),
                    "status": prediction_info.get("status", "unknown")
                }
                info["prediction_history"].insert(0, history_entry)
                info["prediction_history"] = info["prediction_history"][:10]
            return
            
        info["status"] = status
        info["last_update"] = datetime.now().strftime("%H:%M:%S")
        if sent_message:
            info["messages_sent"] += 1
            info["last_message"] = sent_message
            shared_context["total_messages_sent"] += 1
        if status == "error":
            info["errors"] += 1
            shared_context["total_errors"] += 1


def record_prediction_result(username: str, result_info: dict) -> None:
    """Record win/loss result of a prediction for a channel."""
    with data_lock:
        info = shared_context["channels"].get(username)
        if not info:
            return

        res = result_info.get("result", "").lower()
        if res in ("won", "win"):
            info["predictions_won"] = info.get("predictions_won", 0) + 1
        elif res in ("lost", "lose"):
            info["predictions_lost"] = info.get("predictions_lost", 0) + 1
        elif res in ("refunded", "cancelled", "canceled"):
            info["predictions_refunded"] = info.get("predictions_refunded", 0) + 1

        pred_id = result_info.get("id")

        # Update entry in history
        for h in info.get("prediction_history", []):
            if not pred_id or h.get("id") == pred_id or h.get("title") == result_info.get("title"):
                h["status"] = res
                h["winning_outcome"] = result_info.get("winning_outcome")
                h["points_won"] = result_info.get("points_won", 0)
                break

        # Update active prediction status
        if info.get("active_prediction"):
            if not pred_id or info["active_prediction"].get("id") == pred_id:
                info["active_prediction"]["status"] = res
                info["active_prediction"]["winning_outcome"] = result_info.get("winning_outcome")
                info["active_prediction"]["points_won"] = result_info.get("points_won", 0)

        info["last_update"] = datetime.now().strftime("%H:%M:%S")


def update_channel_prediction_info(username: str, prediction_info: dict) -> None:
    """Update prediction info for a channel without changing vote count."""
    with data_lock:
        info = shared_context["channels"].get(username)
        if info:
            info["active_prediction"] = prediction_info
            info["predictions_available"] = True
            info["last_update"] = datetime.now().strftime("%H:%M:%S")


def update_channel_prediction_availability(username: str, has_predictions: bool) -> None:
    """Update whether a channel has active predictions available."""
    with data_lock:
        info = shared_context["channels"].get(username)
        if info:
            info["predictions_available"] = has_predictions
            if not has_predictions:
                info["active_prediction"] = None
            info["last_update"] = datetime.now().strftime("%H:%M:%S")


def set_active() -> None:
    with data_lock:
        shared_context["status"] = "Active"


def start_server(port: int = 5000) -> None:
    """Start the dashboard in a background thread (never blocks mining)."""

    def run() -> None:
        import logging
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        logger.info(f"Web Dashboard available at http://localhost:{port}")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False,
                threaded=True)

    threading.Thread(target=run, daemon=True, name="web-dashboard").start()
