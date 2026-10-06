/* Puck Dynasty web stats (league leaders) */
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    renderStats(data);
  } catch (e) { console.error(e); }
}

function renderStats(data) {
  const sub = document.getElementById('stats-sub');
  const n = (data.scorers || []).length;
  sub.textContent = n ? 'Aggregated across all NHL clubs' : '';

  renderSkaterTable('scorers-table', data.scorers, 'pts');
  renderSkaterTable('goals-table', data.goals, 'g');
  renderGoalieTable('goalies-table', data.goalies);
  if (data.goalie_min_gp) {
    document.getElementById('goalie-min-note').textContent =
      'Min ' + data.goalie_min_gp + ' GP';
  }
}

function renderSkaterTable(id, rows, highlight) {
  const t = document.getElementById(id);
  if (!rows || !rows.length) {
    t.innerHTML = '<tr><td><div class="empty">No data yet.</div></td></tr>';
    return;
  }
  t.innerHTML = `
    <thead><tr>
      <th class="rank">#</th><th>Player</th>
      <th class="num">GP</th><th class="num">G</th><th class="num">A</th>
      <th class="stat">PTS</th><th class="num">+/-</th><th class="num">PIM</th>
    </tr></thead>
    <tbody>${rows.map((r, i) => `
      <tr>
        <td class="rank">${i + 1}</td>
        <td class="pname">${r.id ? `<span class="clickable-text" data-href="/player/${esc(r.id)}" title="Open player profile">${esc(r.name)}</span>` : esc(r.name)}<span class="pos-tag">${esc(r.pos)}</span>
            <span class="pteam">${esc(r.team)}</span></td>
        <td class="num">${r.gp}</td>
        <td class="num"${highlight === 'g' ? ' style="font-weight:800;color:var(--text)"' : ''}>${r.g}</td>
        <td class="num">${r.a}</td>
        <td class="stat"${highlight === 'pts' ? ' style="color:var(--accent)"' : ''}>${r.pts}</td>
        <td class="num">${r.pm > 0 ? '+' : ''}${r.pm}</td>
        <td class="num">${r.pim}</td>
      </tr>`).join('')}
    </tbody>`;
}

function renderGoalieTable(id, rows) {
  const t = document.getElementById(id);
  if (!rows || !rows.length) {
    t.innerHTML = '<tr><td><div class="empty">No qualifying goalies yet.</div></td></tr>';
    return;
  }
  t.innerHTML = `
    <thead><tr>
      <th class="rank">#</th><th>Goalie</th>
      <th class="num">GP</th><th class="stat">SV%</th>
      <th class="num">GAA</th><th class="num">SO</th>
    </tr></thead>
    <tbody>${rows.map((r, i) => `
      <tr>
        <td class="rank">${i + 1}</td>
        <td class="pname">${r.id ? `<span class="clickable-text" data-href="/player/${esc(r.id)}" title="Open player profile">${esc(r.name)}</span>` : esc(r.name)}<span class="pteam">${esc(r.team)}</span></td>
        <td class="num">${r.gp}</td>
        <td class="stat" style="color:var(--accent)">${r.sv_pct.toFixed(3)}</td>
        <td class="num">${r.gaa.toFixed(2)}</td>
        <td class="num">${r.so}</td>
      </tr>`).join('')}
    </tbody>`;
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadStats();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});

/* ---------- tabs ---------- */
(function initStatsTabs() {
  const tabs = document.querySelectorAll('.st-tab');
  const loaded = { nhl: true };
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.toggle('active', x === t));
    ['nhl', 'ahl', 'records', 'xg'].forEach(k =>
      document.getElementById('pane-' + k).classList.toggle('hidden', k !== t.dataset.tab));
    const k = t.dataset.tab;
    if (!loaded[k]) { loaded[k] = true; loadTab(k); }
  }));
  function loadTab(k) {
    if (k === 'ahl') loadAhl();
    else if (k === 'records') loadRecords();
    else if (k === 'xg') loadXg();
  }
})();

/* ---------- AHL tab ---------- */
async function loadAhl() {
  try {
    const data = await (await fetch('/api/stats/ahl')).json();
    renderAhlSkaters(data.skaters || []);
    renderAhlGoalies(data.goalies || []);
    renderAhlStandings(data.standings || []);
  } catch (e) { console.error(e); }
}

function renderAhlSkaters(rows) {
  const t = document.getElementById('ahl-scorers');
  if (!rows.length) { t.innerHTML = '<tr><td><div class="empty">No AHL scoring data yet.</div></td></tr>'; return; }
  t.innerHTML = `<thead><tr><th class="rank">#</th><th>Player</th><th class="num">GP</th>
    <th class="num">G</th><th class="num">A</th><th class="stat">PTS</th><th class="num">PIM</th></tr></thead>
    <tbody>${rows.map((r, i) => `<tr><td class="rank">${i + 1}</td>
      <td class="pname">${r.id ? `<span class="clickable-text" data-href="/player/${esc(r.id)}">${esc(r.name)}</span>` : esc(r.name)}<span class="pos-tag">${esc(r.pos)}</span><span class="pteam">${esc(r.team)}</span></td>
      <td class="num">${r.gp}</td><td class="num">${r.g}</td><td class="num">${r.a}</td>
      <td class="stat" style="color:var(--accent)">${r.pts}</td><td class="num">${r.pim}</td></tr>`).join('')}</tbody>`;
}

function renderAhlGoalies(rows) {
  const t = document.getElementById('ahl-goalies');
  if (!rows.length) { t.innerHTML = '<tr><td><div class="empty">No qualifying AHL goalies yet.</div></td></tr>'; return; }
  t.innerHTML = `<thead><tr><th class="rank">#</th><th>Goalie</th><th class="num">GP</th>
    <th class="num">W</th><th class="stat">SV%</th><th class="num">GAA</th><th class="num">SO</th></tr></thead>
    <tbody>${rows.map((r, i) => `<tr><td class="rank">${i + 1}</td>
      <td class="pname">${r.id ? `<span class="clickable-text" data-href="/player/${esc(r.id)}">${esc(r.name)}</span>` : esc(r.name)}<span class="pteam">${esc(r.team)}</span></td>
      <td class="num">${r.gp}</td><td class="num">${r.w}</td>
      <td class="stat" style="color:var(--accent)">${r.sv_pct.toFixed(3)}</td>
      <td class="num">${r.gaa.toFixed(2)}</td><td class="num">${r.so}</td></tr>`).join('')}</tbody>`;
}

function renderAhlStandings(rows) {
  const t = document.getElementById('ahl-standings');
  if (!rows.length) { t.innerHTML = '<tr><td><div class="empty">No AHL standings yet.</div></td></tr>'; return; }
  t.innerHTML = `<thead><tr><th class="rank">#</th><th>Team</th><th class="num">GP</th>
    <th class="num">W</th><th class="num">L</th><th class="num">OTL</th>
    <th class="stat">PTS</th><th class="num">GF</th><th class="num">GA</th></tr></thead>
    <tbody>${rows.map((r, i) => `<tr><td class="rank">${i + 1}</td>
      <td class="pname">${esc(r.team) || '—'}</td><td class="num">${r.gp}</td><td class="num">${r.w}</td>
      <td class="num">${r.l}</td><td class="num">${r.otl}</td>
      <td class="stat" style="color:var(--accent)">${r.pts}</td>
      <td class="num">${r.gf}</td><td class="num">${r.ga}</td></tr>`).join('')}</tbody>`;
}

/* ---------- Records tab ---------- */
async function loadRecords() {
  try {
    const data = await (await fetch('/api/stats/records')).json();
    renderChampions(data.champions || []);
    renderRecordTeams(data.teams || [], data.empty);
  } catch (e) { console.error(e); }
}

function renderChampions(rows) {
  const t = document.getElementById('champions-table');
  if (!rows.length) { t.innerHTML = '<tr><td><div class="empty">No completed seasons on record yet.</div></td></tr>'; return; }
  t.innerHTML = `<thead><tr><th>Season</th><th>Champion</th><th>Runner-up</th><th>Series</th><th>Conn Smythe</th></tr></thead>
    <tbody>${rows.map(r => `<tr><td class="rank">${esc(r.year)}</td>
      <td class="pname">🏆 ${esc(r.champion || '—')}</td><td>${esc(r.runner_up || '—')}</td>
      <td class="num">${esc(r.series || '—')}</td><td>${esc(r.smythe || '—')}</td></tr>`).join('')}</tbody>`;
}

function renderRecordTeams(teams, empty) {
  const el = document.getElementById('records-teams');
  if (!teams.length) {
    el.innerHTML = empty ? '<div class="empty" style="margin-top:12px">The record book is empty — records are written as seasons complete.</div>' : '';
    return;
  }
  el.innerHTML = teams.map(tm => `
    <section class="bpanel leader-card rec-team">
      <div class="bpanel-h">${esc(tm.team)} <span class="panel-note">Franchise records</span></div>
      ${tm.groups.map(g => `
        <div class="rec-group-h">${esc(g.label)}</div>
        <table class="leader-table"><tbody>
          ${g.records.map(r => `<tr>
            <td class="rec-cat">${esc(r.category)}${r.season ? ` <span class="rec-season">${esc(r.season)}</span>` : ''}</td>
            <td class="pname rec-player">${r.player_id ? `<span class="clickable-text" data-href="/player/${esc(r.player_id)}">${esc(r.player)}</span>` : esc(r.player)}</td>
            <td class="stat rec-val">${esc(r.value)}</td>
          </tr>`).join('')}
        </tbody></table>`).join('')}
    </section>`).join('');
}

/* ---------- xG Analytics tab ---------- */
async function loadXg() {
  const body = document.getElementById('xg-body');
  body.innerHTML = '<div class="empty">Loading analytics…</div>';
  try {
    const data = await (await fetch('/api/stats/analytics')).json();
    if (data.empty) { body.innerHTML = `<div class="empty">${esc(data.reason || 'No data.')}</div>`; return; }
    if (data.source === 'live') renderXgLive(body, data);
    else renderXgArchive(body, data);
  } catch (e) { body.innerHTML = '<div class="empty">Could not load analytics.</div>'; }
}

function renderXgLive(body, data) {
  const [h, a] = data.teams;
  const src = data.source === 'live' ? 'Live game' : 'Last tracked game';
  body.innerHTML = `
    <div class="bpanel leader-card xg-head">
      <div class="bpanel-h">📈 Expected Goals <span class="panel-note">${esc(src)} · ${esc(data.game.away)} @ ${esc(data.game.home)}${data.score ? ` · ${data.score.away}–${data.score.home}` : ''}</span></div>
      <div class="xg-duel">
        ${xgTeamCard(a, '#ef4444')}${xgTeamCard(h, '#3b82f6')}
      </div>
    </div>
    <div class="leaders-grid">
      <section class="bpanel leader-card">
        <div class="bpanel-h">🌊 Momentum <span class="panel-note">Game flow</span></div>
        <canvas id="xg-momentum" height="150"></canvas>
        <div class="xg-legend"><span><i class="sw" style="background:#3b82f6"></i>${esc(data.game.home)}</span><span><i class="sw" style="background:#ef4444"></i>${esc(data.game.away)}</span></div>
      </section>
      <section class="bpanel leader-card">
        <div class="bpanel-h">🎯 Shot Quality by Zone</div>
        <table class="leader-table" id="xg-zones"></table>
      </section>
    </div>
    <section class="bpanel leader-card">
      <div class="bpanel-h">📰 Analyst Report</div>
      <div class="xg-report">${esc(data.report).replace(/\n/g, '<br>')}</div>
    </section>`;
  // zones table (combined)
  const zones = {};
  data.teams.forEach(t => Object.entries(t.zones || {}).forEach(([z, c]) => {
    zones[z] = zones[z] || [0, 0]; zones[z][t.name === data.game.home ? 1 : 0] += c;
  }));
  const zt = document.getElementById('xg-zones');
  const zrows = Object.entries(zones).sort((a, b) => b[1][0] + b[1][1] - (a[1][0] + a[1][1]));
  zt.innerHTML = `<thead><tr><th>Zone</th><th class="num">${esc(data.game.away)}</th><th class="num">${esc(data.game.home)}</th></tr></thead>
    <tbody>${zrows.map(([z, c]) => `<tr><td class="rec-cat">${esc(z.replace(/_/g, ' '))}</td><td class="num">${c[0]}</td><td class="num">${c[1]}</td></tr>`).join('')}</tbody>`;
  drawMomentum(document.getElementById('xg-momentum'), data.momentum || [], data.game);
}

function xgTeamCard(t, color) {
  return `<div class="xg-team"><div class="xg-tname" style="border-color:${color}">${esc(t.name)}</div>
    <div class="xg-xg">${t.xg.toFixed(2)}<span>xG</span></div>
    <div class="xg-sub">${t.shots} shots · ${t.goals} goals</div></div>`;
}

function renderXgArchive(body, data) {
  const g = data.game;
  body.innerHTML = `
    <div class="bpanel leader-card xg-head">
      <div class="bpanel-h">📈 Expected Goals <span class="panel-note">Archived game · ${esc(g.away)} @ ${esc(g.home)}${g.date ? ' · ' + esc(g.date) : ''}</span></div>
      <div class="xg-duel"><div class="xg-team"><div class="xg-tname">Game total</div>
        <div class="xg-xg">${data.total_xg.toFixed(2)}<span>xG</span></div>
        <div class="xg-sub">${data.shots} shots · ${data.goals} goals</div></div></div>
    </div>
    <div class="leaders-grid">
      <section class="bpanel leader-card">
        <div class="bpanel-h">🎯 Shot Quality by Zone</div>
        <table class="leader-table"><thead><tr><th>Zone</th><th class="num">Shots</th><th class="stat">xG</th></tr></thead>
        <tbody>${Object.entries(data.zone_counts || {}).sort((a, b) => b[1] - a[1]).map(([z, c]) =>
          `<tr><td class="rec-cat">${esc(z.replace(/_/g, ' '))}</td><td class="num">${c}</td><td class="stat">${(data.zone_xg[z] || 0).toFixed(2)}</td></tr>`).join('')}</tbody></table>
      </section>
      <section class="bpanel leader-card">
        <div class="bpanel-h">📰 Analyst Report</div>
        <div class="xg-report">${esc(data.report).replace(/\n/g, '<br>')}</div>
      </section>
    </div>`;
}

function drawMomentum(canvas, series, game) {
  if (!canvas) return;
  const W = canvas.parentElement.clientWidth - 28, H = 150;
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#0b1220'; ctx.fillRect(0, 0, W, H);
  const mid = H / 2;
  ctx.strokeStyle = '#2a3c5f'; ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(W, mid); ctx.stroke();
  if (!series.length) {
    ctx.fillStyle = '#5b6a8c'; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('No momentum data for this game.', W / 2, mid); return;
  }
  const map = { heavily_favoring_home: 3, favoring_home: 2, slightly_favoring_home: 1, neutral: 0,
    slightly_favoring_away: -1, favoring_away: -2, heavily_favoring_away: -3 };
  const pts = series.map(e => ({ t: e.t || 0, v: map[e.v] != null ? map[e.v] : 0 }));
  const tMax = Math.max(1, ...pts.map(p => p.t));
  const X = t => (t / tMax) * (W - 8) + 4, Y = v => mid - (v / 3) * (mid - 10);
  // fill
  ctx.beginPath(); ctx.moveTo(X(pts[0].t), mid);
  pts.forEach(p => ctx.lineTo(X(p.t), Y(p.v)));
  ctx.lineTo(X(pts[pts.length - 1].t), mid); ctx.closePath();
  ctx.fillStyle = 'rgba(59,130,246,.18)'; ctx.fill();
  ctx.beginPath();
  pts.forEach((p, i) => i ? ctx.lineTo(X(p.t), Y(p.v)) : ctx.moveTo(X(p.t), Y(p.v)));
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2; ctx.stroke();
}
