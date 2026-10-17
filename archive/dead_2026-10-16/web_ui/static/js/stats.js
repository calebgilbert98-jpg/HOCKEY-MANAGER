/* Puck Dynasty web stats (league leaders) — leader sub-tabs, global
   filters, NHL league records. Ported from stats_standings_window.py. */
const leaderState = {
  ltab: 'scoring', pos: 'All', minGp: 0, team: 'All', award: 'hart',
  rtab: 'season',
};
let awardDefs = [];

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function playerLink(r) {
  const nm = r.id
    ? `<span class="clickable-text" data-href="/player/${esc(r.id)}" title="Open player profile">${esc(r.name)}</span>`
    : esc(r.name);
  return `${nm}<span class="pos-tag">${esc(r.pos || '')}</span><span class="pteam">${esc(r.team || '')}</span>`;
}

function leaderFilters() {
  const q = new URLSearchParams({ pos: leaderState.pos, min_gp: leaderState.minGp });
  if (leaderState.team !== 'All') q.set('team', leaderState.team);
  return q;
}

/* ---------- top-level tabs ---------- */
(function initStatsTabs() {
  const tabs = document.querySelectorAll('.st-tab');
  const panes = ['nhl', 'ahl', 'records', 'nhlrecords', 'xg'];
  const loaded = { nhl: true };
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.toggle('active', x === t));
    panes.forEach(k =>
      document.getElementById('pane-' + k).classList.toggle('hidden', k !== t.dataset.tab));
    const k = t.dataset.tab;
    if (!loaded[k]) { loaded[k] = true; loadTab(k); }
  }));
  function loadTab(k) {
    if (k === 'ahl') loadAhl();
    else if (k === 'records') loadRecords();
    else if (k === 'nhlrecords') loadNhlRecords();
    else if (k === 'xg') loadXg();
  }
})();

/* ---------- leader sub-tabs ---------- */
document.getElementById('leader-tabs').addEventListener('click', e => {
  const b = e.target.closest('.lt-tab');
  if (!b) return;
  document.querySelectorAll('#leader-tabs .lt-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  leaderState.ltab = b.dataset.ltab;
  loadLeaderTab();
});

document.getElementById('lf-pos').addEventListener('click', e => {
  const b = e.target.closest('.tb-pill');
  if (!b) return;
  document.querySelectorAll('#lf-pos .tb-pill').forEach(p => p.classList.remove('active'));
  b.classList.add('active');
  leaderState.pos = b.dataset.v;
  loadLeaderTab();
});
document.getElementById('lf-min-gp').addEventListener('change', e => {
  leaderState.minGp = Math.max(0, parseInt(e.target.value || '0', 10));
  loadLeaderTab();
});
document.getElementById('lf-team').addEventListener('change', e => {
  leaderState.team = e.target.value;
  loadLeaderTab();
});

async function loadTeams() {
  try {
    const d = await (await fetch('/api/standings/views?view=League+Overview')).json();
    const sel = document.getElementById('lf-team');
    const names = [...new Set((d.rows || []).map(r => r.name))].sort();
    sel.innerHTML = '<option value="All">All teams</option>' +
      names.map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join('');
  } catch (e) { /* non-fatal */ }
}

function loadLeaderTab() {
  document.getElementById('award-race-bar').hidden = leaderState.ltab !== 'awards';
  const f = leaderFilters();
  const body = document.getElementById('leaders-body');
  body.innerHTML = '<div class="empty">Loading…</div>';
  if (leaderState.ltab === 'scoring') loadScoring(f);
  else if (leaderState.ltab === 'advanced') loadAdvanced(f);
  else if (leaderState.ltab === 'goaltending') loadGoaltending(f);
  else if (leaderState.ltab === 'breakout') loadBreakout(f);
  else if (leaderState.ltab === 'rookies') loadRookies();
  else if (leaderState.ltab === 'awards') loadAwardRace();
  else if (leaderState.ltab === 'milestones') loadMilestones();
}

async function loadScoring(f) {
  const body = document.getElementById('leaders-body');
  try {
    const d = await (await fetch('/api/stats?' + f)).json();
    document.getElementById('stats-sub').textContent =
      'Aggregated across all NHL clubs';
    const scorers = d.scorers || [];
    const goals = d.goals || [];
    const goalies = d.goalies || [];
    body.innerHTML = `
      <section class="bpanel leader-card">
        <div class="bpanel-h">🏆 Scoring Leaders <span class="panel-note">Top 10</span></div>
        <table class="leader-table" id="lt-scorers"></table>
      </section>
      <section class="bpanel leader-card">
        <div class="bpanel-h">🥅 Goal Leaders <span class="panel-note">Top 5</span></div>
        <table class="leader-table" id="lt-goals"></table>
      </section>
      <section class="bpanel leader-card">
        <div class="bpanel-h">🧤 Save % Leaders <span class="panel-note">${d.goalie_min_gp ? 'Min ' + d.goalie_min_gp + ' GP' : ''}</span></div>
        <table class="leader-table" id="lt-goalies"></table>
      </section>`;
    renderSkaterTable('lt-scorers', scorers, 'pts');
    renderSkaterTable('lt-goals', goals, 'g');
    renderGoalieTable('lt-goalies', goalies);
  } catch (e) {
    body.innerHTML = '<div class="empty">Could not load leaders.</div>';
  }
}

function renderSkaterTable(id, rows, highlight) {
  const t = document.getElementById(id);
  if (!t) return;
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
        <td class="pname">${playerLink(r)}</td>
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
  if (!t) return;
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
        <td class="pname">${playerLink(r)}</td>
        <td class="num">${r.gp}</td>
        <td class="stat" style="color:var(--accent)">${Number(r.sv_pct).toFixed(3)}</td>
        <td class="num">${Number(r.gaa).toFixed(2)}</td>
        <td class="num">${r.so}</td>
      </tr>`).join('')}
    </tbody>`;
}

/* ---------- advanced stats ---------- */
async function loadAdvanced(f) {
  const body = document.getElementById('leaders-body');
  try {
    const d = await (await fetch('/api/stats/advanced?' + f)).json();
    body.innerHTML = `
      <section class="bpanel leader-card" style="grid-column:1/-1">
        <div class="bpanel-h">📊 Advanced Stats <span class="panel-note">ixG · CF% · xGF% · PDO · P/60 · Game Score · SH% — modeled from attributes &amp; production</span></div>
        <table class="leader-table" id="lt-advanced"></table>
      </section>
      <section class="bpanel leader-card" style="grid-column:1/-1">
        <div class="bpanel-h">🧤 Goalie Advanced <span class="panel-note">GSAx · high-danger SV%</span></div>
        <table class="leader-table" id="lt-advgoalies"></table>
      </section>`;
    const sk = d.skaters || [];
    const gt = document.getElementById('lt-advanced');
    gt.innerHTML = sk.length ? `<thead><tr><th class="rank">#</th><th>Player</th>
      <th class="num">GP</th><th class="num">ixG</th><th class="num">CF%</th><th class="num">xGF%</th>
      <th class="num">PDO</th><th class="num">P/60</th><th class="stat">GSc</th><th class="num">SH%</th></tr></thead>
      <tbody>${sk.map((r, i) => `<tr><td class="rank">${i + 1}</td>
        <td class="pname">${playerLink(r)}</td><td class="num">${r.gp}</td>
        <td class="num">${r.ixg}</td><td class="num">${r.cf_pct}</td>
        <td class="num">${r.xgf_pct}</td><td class="num">${r.pdo}</td>
        <td class="num">${r.p_per60}</td><td class="stat" style="color:var(--accent)">${r.game_score}</td>
        <td class="num">${r.sh_pct}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No data yet.</div></td></tr>';
    const gl = d.goalies || [];
    const gg = document.getElementById('lt-advgoalies');
    gg.innerHTML = gl.length ? `<thead><tr><th class="rank">#</th><th>Goalie</th>
      <th class="num">GP</th><th class="stat">GSAx</th><th class="num">HDSV%</th>
      <th class="num">SV%</th><th class="num">GAA</th></tr></thead>
      <tbody>${gl.map((r, i) => `<tr><td class="rank">${i + 1}</td>
        <td class="pname">${playerLink(r)}</td><td class="num">${r.gp}</td>
        <td class="stat" style="color:var(--accent)">${r.gsax}</td>
        <td class="num">${r.hdsv ? Number(r.hdsv).toFixed(3) : '—'}</td>
        <td class="num">${Number(r.sv_pct).toFixed(3)}</td><td class="num">${Number(r.gaa).toFixed(2)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No data yet.</div></td></tr>';
  } catch (e) { body.innerHTML = '<div class="empty">Could not load advanced stats.</div>'; }
}

/* ---------- goaltending ---------- */
async function loadGoaltending(f) {
  const body = document.getElementById('leaders-body');
  try {
    const d = await (await fetch('/api/stats/advanced?' + f)).json();
    const gl = d.goalies || [];
    body.innerHTML = `
      <section class="bpanel leader-card" style="grid-column:1/-1">
        <div class="bpanel-h">🧤 Goaltending Leaders <span class="panel-note">Traditional + GSAx</span></div>
        <table class="leader-table" id="lt-goalies2"></table>
      </section>`;
    const t = document.getElementById('lt-goalies2');
    t.innerHTML = gl.length ? `<thead><tr><th class="rank">#</th><th>Goalie</th>
      <th class="num">GP</th><th class="num">W</th><th class="stat">SV%</th>
      <th class="num">GAA</th><th class="num">GSAx</th><th class="num">SO</th><th class="num">SA</th></tr></thead>
      <tbody>${gl.map((r, i) => `<tr><td class="rank">${i + 1}</td>
        <td class="pname">${playerLink(r)}</td><td class="num">${r.gp}</td>
        <td class="num">${r.w}</td>
        <td class="stat" style="color:var(--accent)">${Number(r.sv_pct).toFixed(3)}</td>
        <td class="num">${Number(r.gaa).toFixed(2)}</td><td class="num">${r.gsax}</td>
        <td class="num">${r.so}</td><td class="num">${r.sa}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No qualifying goalies yet.</div></td></tr>';
  } catch (e) { body.innerHTML = '<div class="empty">Could not load goaltending.</div>'; }
}

/* ---------- breakout ---------- */
async function loadBreakout(f) {
  const body = document.getElementById('leaders-body');
  try {
    const d = await (await fetch('/api/stats/breakout?' + f)).json();
    const rows = d.players || [];
    body.innerHTML = `
      <section class="bpanel leader-card" style="grid-column:1/-1">
        <div class="bpanel-h">🚀 Breakout Players <span class="panel-note">Age ≤ 26 · elite process + regression signals</span></div>
        <table class="leader-table" id="lt-breakout"></table>
      </section>`;
    const t = document.getElementById('lt-breakout');
    t.innerHTML = rows.length ? `<thead><tr><th class="rank">#</th><th>Player</th>
      <th class="num">Age</th><th class="num">GP</th><th class="num">PTS</th>
      <th class="num">xGF%</th><th class="num">ixG−G</th><th class="num">PDO</th>
      <th class="num">P/60</th><th>Signal</th></tr></thead>
      <tbody>${rows.map((r, i) => `<tr><td class="rank">${i + 1}</td>
        <td class="pname">${playerLink(r)}</td><td class="num">${r.age}</td>
        <td class="num">${r.gp}</td><td class="num">${r.pts}</td>
        <td class="num">${r.xgf_pct}</td><td class="num">${r.ixg_vs_g}</td>
        <td class="num">${r.pdo}</td><td class="num">${r.p_per60}</td>
        <td class="rec-cat">${esc(r.signal)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No breakout candidates yet.</div></td></tr>';
  } catch (e) { body.innerHTML = '<div class="empty">Could not load breakout players.</div>'; }
}

/* ---------- rookies ---------- */
async function loadRookies() {
  const body = document.getElementById('leaders-body');
  try {
    const d = await (await fetch('/api/stats/rookies')).json();
    const sk = d.skaters || [], gl = d.goalies || [];
    body.innerHTML = `
      <section class="bpanel leader-card">
        <div class="bpanel-h">🌱 Rookie Scoring <span class="panel-note">Calder eligible</span></div>
        <table class="leader-table" id="lt-rsk"></table>
      </section>
      <section class="bpanel leader-card">
        <div class="bpanel-h">🧤 Rookie Goaltending</div>
        <table class="leader-table" id="lt-rg"></table>
      </section>`;
    const t1 = document.getElementById('lt-rsk');
    t1.innerHTML = sk.length ? `<thead><tr><th class="rank">#</th><th>Player</th>
      <th class="num">GP</th><th class="num">G</th><th class="num">A</th><th class="stat">P</th></tr></thead>
      <tbody>${sk.map((r, i) => `<tr><td class="rank">${i + 1}</td>
        <td class="pname">${playerLink(r)}</td><td class="num">${r.gp}</td>
        <td class="num">${r.g}</td><td class="num">${r.a}</td>
        <td class="stat" style="color:var(--accent)">${r.pts}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No rookie skaters yet.</div></td></tr>';
    const t2 = document.getElementById('lt-rg');
    t2.innerHTML = gl.length ? `<thead><tr><th class="rank">#</th><th>Goalie</th>
      <th class="num">GP</th><th class="num">W</th><th class="stat">SV%</th><th class="num">GAA</th></tr></thead>
      <tbody>${gl.map((r, i) => `<tr><td class="rank">${i + 1}</td>
        <td class="pname">${playerLink(r)}</td><td class="num">${r.gp}</td>
        <td class="num">${r.w}</td>
        <td class="stat" style="color:var(--accent)">${Number(r.sv_pct).toFixed(3)}</td>
        <td class="num">${Number(r.gaa).toFixed(2)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No rookie goalies yet.</div></td></tr>';
  } catch (e) { body.innerHTML = '<div class="empty">Could not load rookies.</div>'; }
}

/* ---------- award races ---------- */
async function loadAwardRace() {
  const body = document.getElementById('leaders-body');
  try {
    const d = await (await fetch('/api/stats/award-races?award=' + encodeURIComponent(leaderState.award))).json();
    awardDefs = d.awards || [];
    renderAwardPills();
    document.getElementById('award-desc').textContent =
      (d.name ? d.name + ': ' : '') + (d.description || '');
    const rows = d.rows || [];
    body.innerHTML = `
      <section class="bpanel leader-card" style="grid-column:1/-1">
        <div class="bpanel-h">🏅 ${esc(d.name || 'Award Race')} <span class="panel-note">Top 15 candidates</span></div>
        <table class="leader-table" id="lt-awards"></table>
      </section>`;
    const t = document.getElementById('lt-awards');
    t.innerHTML = rows.length ? `<thead><tr><th class="rank">#</th><th>Candidate</th>
      <th class="num">Team</th><th class="stat">Score</th><th>Case</th></tr></thead>
      <tbody>${rows.map(r => `<tr><td class="rank">${r.rank}</td>
        <td class="pname">${r.is_team ? esc(r.name)
          : r.id ? `<span class="clickable-text" data-href="/player/${esc(r.id)}" title="Open player profile">${esc(r.name)}</span>` : esc(r.name)}</td>
        <td class="num">${esc(r.team)}</td>
        <td class="stat" style="color:var(--accent)">${r.score}</td>
        <td class="rec-cat">${esc(r.detail)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No candidates yet.</div></td></tr>';
  } catch (e) { body.innerHTML = '<div class="empty">Could not load award races.</div>'; }
}

function renderAwardPills() {
  const host = document.getElementById('award-pills');
  host.innerHTML = '';
  for (const a of awardDefs) {
    const b = document.createElement('button');
    b.className = 'tb-pill' + (a.key === leaderState.award ? ' active' : '');
    b.textContent = a.name;
    b.addEventListener('click', () => { leaderState.award = a.key; loadAwardRace(); });
    host.appendChild(b);
  }
}

/* ---------- milestones ---------- */
async function loadMilestones() {
  const body = document.getElementById('leaders-body');
  try {
    const d = await (await fetch('/api/stats/milestones')).json();
    const rows = d.watch || [];
    body.innerHTML = `
      <section class="bpanel leader-card" style="grid-column:1/-1">
        <div class="bpanel-h">🎯 Milestone Watch <span class="panel-note">Players closing in on career marks</span></div>
        <table class="leader-table" id="lt-miles"></table>
      </section>`;
    const t = document.getElementById('lt-miles');
    t.innerHTML = rows.length ? `<thead><tr><th>Player</th><th>Milestone</th>
      <th class="num">Current</th><th class="num">Needed</th><th class="num">This Season</th></tr></thead>
      <tbody>${rows.map(r => `<tr>
        <td class="pname">${playerLink(r)}</td>
        <td class="rec-cat">${esc(r.milestone)}</td>
        <td class="num">${r.current}</td>
        <td class="stat" style="color:var(--accent)">${r.needed}</td>
        <td class="num">${r.season}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No players approaching career milestones yet — check back as the season progresses.</div></td></tr>';
  } catch (e) { body.innerHTML = '<div class="empty">Could not load milestones.</div>'; }
}

/* ---------- NHL league records ---------- */
document.getElementById('nhlrec-tabs').addEventListener('click', e => {
  const b = e.target.closest('.lt-tab');
  if (!b) return;
  document.querySelectorAll('#nhlrec-tabs .lt-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  leaderState.rtab = b.dataset.rtab;
  loadNhlRecords();
});

let nhlRecCache = null;
async function loadNhlRecords() {
  const head = document.getElementById('nhlrec-head');
  const body = document.getElementById('nhlrec-body');
  body.innerHTML = '<div class="empty">Loading…</div>';
  try {
    if (!nhlRecCache) nhlRecCache = await (await fetch('/api/stats/nhl-records')).json();
    const d = nhlRecCache;
    head.innerHTML = `⭐ NHL Records <span class="panel-note">${d.total || 0} official records${d.achievements_count ? ' · ' + d.achievements_count + ' broken' : ''}</span>`;
    const t = leaderState.rtab;
    if (t === 'chase') renderChase(body, d.chase || []);
    else if (t === 'achievements') renderAchievements(body, d.achievements || []);
    else renderRecordBook(body, d[t] || []);
  } catch (e) { body.innerHTML = '<div class="empty">Could not load NHL records.</div>'; }
}

function fmtRecEntry(e) {
  if (!e) return '—';
  let s = `${esc(e.player)}: <b>${esc(e.value)}</b> <span class="rec-season">${esc(e.season)}</span> · ${esc(e.team)}`;
  if (e.games) s += ` <span class="panel-note">(${e.games} GP)</span>`;
  if (e.info) s += `<br><span class="panel-note">${esc(e.info)}</span>`;
  return s;
}

function renderRecordBook(body, rows) {
  if (!rows.length) { body.innerHTML = '<div class="empty">No records in this book yet.</div>'; return; }
  body.innerHTML = `<table class="leader-table"><thead><tr><th>Record</th><th>Holder</th><th>Rookie Record</th></tr></thead>
    <tbody>${rows.map(r => `<tr>
      <td class="rec-cat">${esc(r.label)}</td>
      <td>${fmtRecEntry(r.record)}</td>
      <td>${r.rookie_record ? fmtRecEntry(r.rookie_record) : '<span class="panel-note">—</span>'}</td>
    </tr>`).join('')}</tbody></table>`;
}

function renderChase(body, rows) {
  if (!rows.length) { body.innerHTML = '<div class="empty">Nobody is 25%+ of the way to a record yet.</div>'; return; }
  body.innerHTML = `<p class="panel-note" style="margin:0 0 10px">Players currently chasing NHL records (25%+ progress toward the record).</p>
    <table class="leader-table"><thead><tr><th class="rank">#</th><th>Player</th><th>Record</th>
    <th class="num">Current</th><th class="num">Target</th><th class="num">Needed</th><th class="stat">Progress</th></tr></thead>
    <tbody>${rows.map((r, i) => `<tr><td class="rank">${i + 1}</td>
      <td class="pname">${r.id ? `<span class="clickable-text" data-href="/player/${esc(r.id)}" title="Open player profile">${esc(r.player)}</span>` : esc(r.player)}<span class="pos-tag">${esc(r.pos)}</span><span class="pteam">${esc(r.team)}</span></td>
      <td class="rec-cat">${esc(r.record)}</td>
      <td class="num">${r.current}</td><td class="num">${r.target}</td>
      <td class="num">${r.needed}</td>
      <td class="stat" style="color:var(--accent)">${r.pct}%</td></tr>`).join('')}</tbody></table>`;
}

function renderAchievements(body, rows) {
  if (!rows.length) { body.innerHTML = '<div class="empty">No records broken in this career yet.</div>'; return; }
  body.innerHTML = `<table class="leader-table"><thead><tr><th>Date</th><th>Player</th><th>Record</th><th class="num">New Value</th><th class="num">Previous</th></tr></thead>
    <tbody>${rows.map(r => `<tr><td class="rank">${esc(r.date)}</td>
      <td class="pname">${esc(r.player)}</td><td class="rec-cat">${esc(r.record)}</td>
      <td class="num"><b>${esc(r.value)}</b></td><td class="num">${esc(r.previous)}</td></tr>`).join('')}</tbody></table>`;
}

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

/* ---------- Records tab (franchise book) ---------- */
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
  ctx.beginPath(); ctx.moveTo(X(pts[0].t), mid);
  pts.forEach(p => ctx.lineTo(X(p.t), Y(p.v)));
  ctx.lineTo(X(pts[pts.length - 1].t), mid); ctx.closePath();
  ctx.fillStyle = 'rgba(59,130,246,.18)'; ctx.fill();
  ctx.beginPath();
  pts.forEach((p, i) => i ? ctx.lineTo(X(p.t), Y(p.v)) : ctx.moveTo(X(p.t), Y(p.v)));
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2; ctx.stroke();
}

/* ---------- boot ---------- */
loadTeams();
loadLeaderTab();

// Shared heartbeat: tells the game the tab is still open (every 30s).
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
