// Manager Hub — GM dashboard. Dark broadcast UI, deep blue accent.
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function pillFor(status) {
  const map = {
    hit: ["green", "Hit ✓"], on_track: ["green", "On track"],
    at_risk: ["yellow", "At risk"], behind: ["red", "Behind"],
    preseason: ["gray", "Preseason"], on: ["green", "On track"],
    within_reach: ["yellow", "Within reach"], off_the_pace: ["red", "Off the pace"],
    rebuild: ["blue", "Rebuild"]
  };
  const m = map[status] || ["gray", String(status)];
  return `<span class="pill ${m[0]}">${esc(m[1])}</span>`;
}

function statusBarClass(status) {
  return { hit: "st-ok", on_track: "st-ok", at_risk: "st-warn", behind: "st-bad" }[status] || "";
}

/* ================= Board ================= */
let boardData = null;

async function loadBoard() {
  const body = document.getElementById("board-body");
  try {
    const res = await fetch("/api/manager/board");
    const d = await res.json();
    if (!d.available) { body.innerHTML = '<div class="mgr-empty">Board data unavailable — no career attached.</div>'; return; }
    boardData = d;
    const confCls = d.confidence >= 70 ? "st-ok" : d.confidence >= 40 ? "" : d.confidence >= 20 ? "st-warn" : "st-bad";
    const r = d.record;
    const opts = d.expectations.map(e =>
      `<option value="${esc(e.key)}" ${e.key === d.expectation ? "selected" : ""}>${esc(e.label)}</option>`).join("");
    const conseq = (d.consequences && d.consequences.length)
      ? `<ul class="conseq-list">${d.consequences.map(c => `<li>${esc(c)}</li>`).join("")}</ul>` : "";
    const cutoff = d.cutoff_pace != null
      ? `<div class="verdict-lines">Playoff picture: the current league-wide cutoff pace is about ${d.cutoff_pace} points.</div>` : "";
    const gapTxt = d.verdict_gap == null ? "" : ` (${d.verdict_gap >= 0 ? "+" : ""}${d.verdict_gap} vs target pace)`;
    const paceLine = d.record.pace != null
      ? `Current pace: ${r.pts} points in ${r.gp} games (${d.record.pace} points per ${r.slate} games).` : "";
    body.innerHTML = `
      <div class="board-top">
        <div class="board-conf">${d.confidence}<small>/100</small></div>
        <div class="board-meta">
          <div class="pbar"><i class="${confCls}" style="width:${d.confidence}%"></i></div>
          <div class="pbar-label"><span>Board confidence</span><span>${esc(d.job_status)}</span></div>
          <div class="board-record">${r.w}W – ${r.l}L – ${r.otl}OTL · ${r.pts} pts</div>
          ${d.last_review ? `<div class="board-review">Latest review: ${esc(d.last_review)}</div>` : ""}
        </div>
      </div>
      <div class="expect-row">
        <label for="exp-sel" style="font-size:12.5px;color:#c7d0e0">Season expectation:</label>
        <select id="exp-sel" class="mgr-select">${opts}</select>
        <button class="mgr-btn" id="exp-save">Set Expectation</button>
        <div class="expect-desc" id="exp-desc"></div>
      </div>
      <div class="verdict-lines">
        ${esc(paceLine)}<br>
        Expectation (${esc(d.expectation_label)}): ${esc(d.target_note)}. ${pillFor(d.verdict)}${esc(gapTxt)}
      </div>
      ${cutoff}
      ${conseq}
      ${d.patience_status ? `<div class="patience-line">${esc(d.patience_status)}</div>` : ""}
      <div class="expect-row">
        <button class="mgr-btn ghost" id="patience-btn">Request a meeting with the owner</button>
      </div>`;
    document.getElementById("board-job").textContent = d.job_status;
    updateExpDesc(d);
    document.getElementById("exp-sel").addEventListener("change", e => {
      const k = e.target.value;
      const ex = d.expectations.find(x => x.key === k);
      document.getElementById("exp-desc").textContent = ex ? `${ex.label}: ${ex.description}` : "";
    });
    document.getElementById("exp-save").addEventListener("click", async () => {
      const k = document.getElementById("exp-sel").value;
      const rr = await fetch("/api/manager/board/expectation", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expectation: k })
      });
      if (rr.ok) loadBoard();
    });
    document.getElementById("patience-btn").addEventListener("click", async () => {
      const btn = document.getElementById("patience-btn");
      btn.disabled = true;
      const rr = await fetch("/api/manager/board/patience", { method: "POST" });
      const jd = await rr.json();
      alert(`${jd.headline || "Owner meeting"}\n\n${jd.body || jd.error || ""}`);
      btn.disabled = false;
      loadBoard();
    });
  } catch (e) {
    body.innerHTML = '<div class="mgr-empty">Could not load board data.</div>';
  }
}

function updateExpDesc(d) {
  const ex = d.expectations.find(x => x.key === d.expectation);
  document.getElementById("exp-desc").textContent = ex ? `${ex.label}: ${ex.description}` : "";
}

/* ================= Season goals ================= */
async function loadGoals() {
  const body = document.getElementById("goals-body");
  const note = document.getElementById("goals-note");
  try {
    const res = await fetch("/api/manager/goals");
    const d = await res.json();
    if (!d.available) { body.innerHTML = '<div class="mgr-empty">Season goals unavailable.</div>'; return; }
    note.textContent = d.goals.length ? `${d.goals.length} goal${d.goals.length > 1 ? "s" : ""} set` : "None set yet";
    const rows = d.goals.map(g => `
      <div class="goal-row" data-gid="${esc(g.player_id)}">
        <div class="goal-head">
          <div><div class="goal-name">${esc(g.name)}</div>
          <div class="goal-sub">${esc(g.label)}: ${g.current}/${g.target}</div></div>
          <div style="text-align:right">${pillFor(g.status)}</div>
          <div class="goal-progress">
            <div class="pbar"><i class="${statusBarClass(g.status)}" style="width:${g.pct}%"></i></div>
            <div class="pbar-label"><span>${g.pct}% of target</span>
            <span>${g.expected_pct ? "pace target " + g.expected_pct + "%" : ""}</span></div>
          </div>
        </div>
        <div class="goal-detail">
          <div><strong>Status:</strong> ${esc(statusText(g.status))} — ${g.current} of ${g.target} ${esc(g.label.toLowerCase())}.
          Season pace expects ~${g.expected_pct}% by now.</div>
          <div><strong>Reward on hit:</strong> +4 ${esc((g.reward_attrs || []).join(", "))}, +5 potential, morale surge.</div>
          ${g.set_date ? `<div><strong>Set:</strong> ${esc(g.set_date)}</div>` : ""}
          <div class="row-actions">
            <button class="mgr-btn danger" data-clear="${esc(g.player_id)}">Clear goal</button>
          </div>
        </div>
      </div>`).join("");
    const types = (d.goal_types || []).concat(d.goalie_goal_types || [])
      .map(t => `<option value="${esc(t.key)}">${esc(t.label)}</option>`).join("");
    const players = (d.players_without_goals || [])
      .map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
    body.innerHTML = `
      ${rows || '<div class="mgr-empty">No season goals set yet — set one per player below.</div>'}
      <div class="set-goal-form">
        <select id="sg-player" class="mgr-select">${players || '<option value="">(everyone has a goal)</option>'}</select>
        <select id="sg-type" class="mgr-select">${types}</select>
        <input id="sg-target" class="mgr-input" type="number" min="1" value="20" style="width:80px" placeholder="Target">
        <button class="mgr-btn" id="sg-set">Set Goal</button>
      </div>
      <div class="expect-desc">Hit it: +4 to two skills, +5 potential, morale surge. Miss it: small morale dip, no attribute penalty. One player per goal type per team.</div>`;
    body.querySelectorAll(".goal-row").forEach(row => {
      row.addEventListener("click", e => {
        if (e.target.closest("[data-clear]")) return;
        row.classList.toggle("open");
      });
    });
    body.querySelectorAll("[data-clear]").forEach(btn => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/manager/goals/${encodeURIComponent(btn.dataset.clear)}`, { method: "DELETE" });
        loadGoals();
      });
    });
    document.getElementById("sg-set").addEventListener("click", async () => {
      const pid = document.getElementById("sg-player").value;
      const gtype = document.getElementById("sg-type").value;
      const target = document.getElementById("sg-target").value;
      if (!pid) { alert("No player available to set a goal for."); return; }
      const rr = await fetch("/api/manager/goals", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_id: pid, goal_type: gtype, target })
      });
      const jd = await rr.json();
      if (!rr.ok) { alert(jd.error || "Could not set goal."); return; }
      loadGoals();
    });
  } catch (e) {
    body.innerHTML = '<div class="mgr-empty">Could not load season goals.</div>';
  }
}

function statusText(s) {
  return { hit: "Hit", on_track: "On track", at_risk: "At risk", behind: "Behind pace", preseason: "Preseason" }[s] || s;
}

/* ================= Analytics ================= */
async function loadAnalytics() {
  const body = document.getElementById("analytics-body");
  const note = document.getElementById("analytics-note");
  try {
    const res = await fetch("/api/manager/analytics");
    const d = await res.json();
    if (!d.available) {
      body.innerHTML = `<div class="mgr-empty">${esc(d.message || "No analytics yet.")}</div>`;
      return;
    }
    note.textContent = `Last ${d.window} games`;
    const diffCls = d.diff >= 1.5 ? "good" : d.diff <= -1.5 ? "bad" : "";
    const qualCls = d.avg_chance_quality >= 0.10 ? "good" : d.avg_chance_quality < 0.07 ? "warn" : "";
    const maxXg = Math.max(1, ...d.games.map(g => Math.max(g.xg_for, g.xg_against)));
    const spark = d.games.map(g =>
      `<i style="height:${Math.round(100 * g.xg_for / maxXg)}%" title="${esc(g.label)}: xG ${g.xg_for}"></i>`).join("");
    const gameRows = d.games.map(g => `
      <tr><td>${esc(g.label)}</td><td class="num">${g.xg_for.toFixed(2)}</td>
      <td class="num">${g.goals_for}</td><td class="num">${g.shots}</td>
      <td class="num">${g.xg_against.toFixed(2)}</td></tr>`).join("");
    const lineRows = (d.lines || []).map(l =>
      `<tr><td>${esc(l.line)}</td><td class="num">${l.shots}</td>
      <td class="num">${l.xg.toFixed(2)}</td><td class="num">${l.goals}</td>
      <td class="num">${esc(String(l.chemistry))}</td></tr>`).join("");
    const gradeRows = (d.grades || []).map(g =>
      `<tr><td>Grade ${esc(g.grade)}</td><td class="num">${g.shots}</td>
      <td class="num">${g.xg.toFixed(2)}</td><td class="num">${g.goals}</td>
      <td class="num">${(g.conv * 100).toFixed(1)}%</td></tr>`).join("");
    const hs = d.hot_shooter;
    const mom = d.momentum;
    body.innerHTML = `
      <div class="tile-grid">
        <div class="tile"><div class="t-label">xG (for)</div><div class="t-value">${d.xg_for.toFixed(1)}</div>
          <div class="t-sub">${d.window}-game window</div></div>
        <div class="tile"><div class="t-label">Goals</div><div class="t-value ${diffCls}">${d.goals_for}</div>
          <div class="t-sub">${d.diff >= 0 ? "+" : ""}${d.diff.toFixed(1)} vs xG</div></div>
        <div class="tile"><div class="t-label">xG (against)</div><div class="t-value">${d.xg_against.toFixed(1)}</div>
          <div class="t-sub">${d.shots} shots for</div></div>
        <div class="tile"><div class="t-label">Chance quality</div><div class="t-value ${qualCls}">${d.avg_chance_quality.toFixed(3)}</div>
          <div class="t-sub">xG per shot</div></div>
        <div class="tile"><div class="t-label">High-danger share</div><div class="t-value">${(d.high_danger_share * 100).toFixed(0)}<small>%</small></div>
          <div class="t-sub">${d.high_danger_count}/${d.shots} shots</div></div>
        <div class="tile"><div class="t-label">Controlled entries</div><div class="t-value">${d.controlled_entries_pct.toFixed(0)}<small>%</small></div>
          <div class="t-sub">${d.entries_total} entries</div></div>
      </div>
      <div class="bpanel-h" style="margin-top:6px">xG by game</div>
      <div class="spark" title="xG for per game">${spark}</div>
      <table class="mgr-table">
        <thead><tr><th>Game</th><th class="num">xG for</th><th class="num">G</th>
        <th class="num">Shots</th><th class="num">xG against</th></tr></thead>
        <tbody>${gameRows}</tbody>
      </table>
      ${lineRows ? `<div class="bpanel-h" style="margin-top:10px">Last game — xG by line</div>
      <table class="mgr-table"><thead><tr><th>Line</th><th class="num">Shots</th>
      <th class="num">xG</th><th class="num">G</th><th class="num">Chem</th></tr></thead>
      <tbody>${lineRows}</tbody></table>` : ""}
      ${gradeRows ? `<div class="bpanel-h" style="margin-top:10px">Chance quality</div>
      <table class="mgr-table"><thead><tr><th>Grade</th><th class="num">Shots</th>
      <th class="num">xG</th><th class="num">G</th><th class="num">Conv</th></tr></thead>
      <tbody>${gradeRows}</tbody></table>` : ""}
      <div class="verdict-lines" style="margin-top:10px">
        ${hs ? `Top chance generator: <strong>${esc(hs.shooter)}</strong> — ${hs.xg.toFixed(1)} xG on ${hs.shots} shots (${hs.goals} goals, ${hs.diff >= 0 ? "+" : ""}${hs.diff.toFixed(1)} vs xG).<br>` : ""}
        ${mom ? `Momentum last game: ${mom.shifts} tracked shifts, biggest swing ${mom.swing >= 0 ? "+" : ""}${mom.swing} steps, ended ${mom.latest > 0 ? "with" : mom.latest < 0 ? "against" : "neutral to"} you.` : ""}
      </div>`;
  } catch (e) {
    body.innerHTML = '<div class="mgr-empty">Could not load analytics.</div>';
  }
}

/* ================= GM relationships ================= */
let relRows = [], relSort = { col: "respect", rev: true };

async function loadRels() {
  const body = document.getElementById("rels-body");
  const note = document.getElementById("rels-note");
  try {
    const res = await fetch("/api/manager/relationships");
    const d = await res.json();
    if (!d.available) { body.innerHTML = '<div class="mgr-empty">Relationships unavailable — reputation system not attached.</div>'; return; }
    relRows = d.rows || [];
    note.textContent = `Your stature: ${d.own ? d.own.stature : 50}/100`;
    renderRels();
  } catch (e) {
    document.getElementById("rels-body").innerHTML = '<div class="mgr-empty">Could not load relationships.</div>';
  }
}

function sortKey(r, col) {
  if (["stature", "respect", "heat"].includes(col)) return Number(r[col]) || 0;
  return String(r[col] || "").toLowerCase();
}

function renderRels() {
  const body = document.getElementById("rels-body");
  const rows = [...relRows].sort((a, b) => {
    const va = sortKey(a, relSort.col), vb = sortKey(b, relSort.col);
    return (va < vb ? -1 : va > vb ? 1 : 0) * (relSort.rev ? -1 : 1);
  });
  const cols = [["team", "Team"], ["gm", "GM"], ["stature", "Stature"], ["respect", "Respect"],
                ["tier", "Tier"], ["heat", "Heat"], ["trend", "Trend"]];
  const ths = cols.map(([c, label]) => {
    const arrow = relSort.col === c ? (relSort.rev ? " ▼" : " ▲") : "";
    return `<th class="sortable" data-sort="${c}">${label}${arrow}</th>`;
  }).join("");
  const trs = rows.map(r => {
    const cls = r.tier === "warm" ? "rel-warm" : r.tier === "cold" ? "rel-cold" : "";
    const respCls = r.respect >= 65 ? "good" : r.respect < 35 ? "bad" : "";
    const heatCls = r.heat >= 60 ? "bad" : r.heat <= 20 ? "good" : "";
    return `<tr class="clickable ${cls}" data-team="${esc(r.team)}">
      <td>${esc(r.team)}</td><td>${esc(r.gm)}</td>
      <td class="num">${r.stature}</td>
      <td class="num ${respCls ? "t-value " + respCls : ""}" style="${respCls ? "font-weight:700" : ""}">${r.respect}</td>
      <td>${esc(r.tier)}</td>
      <td class="num" style="${heatCls ? "font-weight:700;color:" + (heatCls === "bad" ? "#f87171" : "#4ade80") : ""}">${r.heat}</td>
      <td style="font-size:15px">${esc(r.arrow)}</td></tr>`;
  }).join("");
  body.innerHTML = `
    <div style="font-size:11.5px;color:#9aa4b8;margin-bottom:8px">
      Stature: your league-wide reputation (0–100). Respect: how this GM views you (0–100, 50 = neutral).
      Heat: personal friction (0–100). ↑ warming · ↓ cooling · → steady. Click a row for detail.</div>
    <table class="mgr-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>
    <div class="rel-detail" id="rel-detail"></div>`;
  body.querySelectorAll("th.sortable").forEach(th => {
    th.addEventListener("click", () => {
      const c = th.dataset.sort;
      if (relSort.col === c) relSort.rev = !relSort.rev;
      else { relSort.col = c; relSort.rev = ["stature", "respect", "heat"].includes(c); }
      renderRels();
    });
  });
  body.querySelectorAll("tr.clickable").forEach(tr => {
    tr.addEventListener("click", () => showRelDetail(tr.dataset.team));
  });
}

async function showRelDetail(teamName) {
  const box = document.getElementById("rel-detail");
  box.classList.add("show");
  box.innerHTML = "Loading…";
  try {
    const res = await fetch(`/api/manager/relationships/${encodeURIComponent(teamName)}`);
    const d = await res.json();
    if (!res.ok) { box.innerHTML = "GM not found."; return; }
    const tierPill = d.tier === "warm" ? "green" : d.tier === "cold" ? "red" : d.tier === "cordial" ? "green" : "yellow";
    box.innerHTML = `
      <div style="font-size:15px;font-weight:800;color:#fff;margin-bottom:6px">${esc(d.gm)}
        <span style="font-size:12px;color:#9aa4b8;font-weight:400">— ${esc(d.team)}</span></div>
      <div class="tile-grid">
        <div class="tile"><div class="t-label">Stature</div><div class="t-value">${d.stature}</div></div>
        <div class="tile"><div class="t-label">Respect</div><div class="t-value">${d.respect}</div>
          <div class="t-sub"><span class="pill ${tierPill}">${esc(d.tier)}</span></div></div>
        <div class="tile"><div class="t-label">Heat</div><div class="t-value">${d.heat}</div></div>
        <div class="tile"><div class="t-label">Trend</div><div class="t-value">${esc(d.arrow)}</div>
          <div class="t-sub">${esc(d.trend)}</div></div>
      </div>
      <div style="margin-top:6px">Respect decays toward this GM's stature baseline${d.respect_baseline != null ? ` (about ${Math.round(d.respect_baseline)})` : ""} over time. Fair dealing builds it; lopsided trades and offer sheets erode it.</div>`;
  } catch (e) {
    box.innerHTML = "Could not load GM detail.";
  }
}

/* ================= Profile + press ================= */
async function loadProfile() {
  const body = document.getElementById("profile-body");
  try {
    const res = await fetch("/api/manager/profile");
    const d = await res.json();
    if (!d.available) { body.innerHTML = '<div class="mgr-empty">Profile unavailable.</div>'; return; }
    const p = d.profile || {};
    const bio = (d.bio || []).map(l => l === "" ? "<br>" : esc(l)).join("<br>");
    const sr = d.season_record;
    body.innerHTML = `
      <div class="prof-hero">
        <div class="prof-rep">${p.reputation}<small>/100 reputation</small></div>
        <div>
          <div class="prof-level">${esc(p.level || "")}</div>
          <div class="prof-record">Career: ${p.career_wins}W – ${p.career_losses}L – ${p.career_otl}OTL
            · Titles ${p.titles_won} · Playoffs ${p.playoff_appearances} · ${p.seasons_managed} seasons</div>
          ${sr ? `<div class="prof-record">This season: ${sr.w}W – ${sr.l}L – ${sr.otl}OTL</div>` : ""}
        </div>
      </div>
      ${bio ? `<div class="bio-lines">${bio}</div>` : ""}
      ${d.appointment && d.appointment.club ? `<div class="bio-lines"><span class="dim">Club:</span> ${esc(d.appointment.club)}${d.appointment.since ? ` <span class="dim">· in charge since</span> ${esc(d.appointment.since)}` : ""}</div>` : ""}`;
  } catch (e) {
    body.innerHTML = '<div class="mgr-empty">Could not load profile.</div>';
  }
}

async function loadPress() {
  const body = document.getElementById("press-body");
  try {
    const res = await fetch("/api/manager/press");
    const d = await res.json();
    const entries = d.entries || [];
    if (!entries.length) { body.innerHTML = '<div class="mgr-empty">No press conferences held yet.</div>'; return; }
    body.innerHTML = entries.map(e => `
      <div class="press-item"><div class="press-meta">[${esc(e.date)}] ${esc(e.type)}</div>
      <div class="press-sum">${esc(e.summary)}</div></div>`).join("");
  } catch (e) {
    body.innerHTML = '<div class="mgr-empty">Could not load press history.</div>';
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadBoard(); loadGoals(); loadAnalytics(); loadRels(); loadProfile(); loadPress();
});
