/* Puck Dynasty web standings — view modes, team analytics, division
   analysis, divisions grid. Ported from stats_standings_window.py. */
const standState = {
  view: 'League Overview', sort: 'Points', advanced: true,
  taCat: 'Overall Performance', taMode: 'League Rankings', taFilter: 'All Teams',
  div: 'All Divisions', divType: 'Standings',
};
const TA_CATS = ['Overall Performance', 'Offensive Stats', 'Defensive Stats',
  'Goaltending', 'Advanced Analytics'];
const TA_FILTERS = ['All Teams', 'Eastern Conference', 'Western Conference',
  'Division Rivals', 'Playoff Teams'];
const DIV_TYPES = ['Standings', 'Head-to-Head', 'Strength of Schedule', 'Division vs League'];

/* ---------- tabs ---------- */
document.getElementById('stand-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#stand-tabs .tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('main.stand-main .tb-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('stand-tab-' + b.dataset.tab).classList.remove('hidden');
  if (b.dataset.tab === 'overview') loadViews();
  if (b.dataset.tab === 'analytics') loadTeamAnalytics();
  if (b.dataset.tab === 'division') loadDivisionAnalysis();
  if (b.dataset.tab === 'grid') loadDivisionsGrid();
});

/* ---------- overview: 6 view modes ---------- */
async function loadViews() {
  const q = new URLSearchParams({
    view: standState.view, sort: standState.sort,
    advanced: standState.advanced ? '1' : '0',
  });
  try {
    const res = await fetch('/api/standings/views?' + q);
    const d = await res.json();
    renderViewPills(d.views || []);
    renderOverview(d);
  } catch (e) { console.error(e); }
}

function renderViewPills(views) {
  const host = document.getElementById('view-pills');
  host.innerHTML = '';
  for (const v of views) {
    const b = document.createElement('button');
    b.className = 'tb-pill' + (v === standState.view ? ' active' : '');
    b.dataset.v = v;
    b.textContent = v;
    b.addEventListener('click', () => { standState.view = v; loadViews(); });
    host.appendChild(b);
  }
}

function renderOverview(d) {
  const wrap = document.getElementById('stand-tables');
  const rows = d.rows || [];
  if (d.user_team) {
    document.getElementById('stand-sub').textContent =
      d.user_team + ' · ' + d.view;
  }
  wrap.innerHTML = '';
  if (!rows.length) {
    wrap.innerHTML = '<div class="empty">No standings available yet.</div>';
    return;
  }
  const adv = d.advanced;
  const cutoff = d.cutoff;
  const ncols = adv ? 11 : 7;
  const block = document.createElement('div');
  block.className = 'conf-block';
  block.innerHTML = `
    <div class="conf-title">${esc(d.view)} <span class="panel-note">${rows.length} teams</span></div>
    <div class="stand-card">
      <table class="stand-table">
        <thead><tr>
          <th class="rank">#</th><th>Team</th>
          <th class="num">GP</th><th class="num">W</th><th class="num">L</th>
          <th class="num">OTL</th>
          ${adv ? '<th class="num">GF</th><th class="num">GA</th><th class="num">DIFF</th><th class="num">PT%</th>' : ''}
          <th class="pts">PTS</th>
        </tr></thead>
        <tbody>${rows.map((r, i) => {
          const cut = cutoff != null && i === cutoff;
          const diffCls = r.diff >= 0 ? 'pos' : 'neg';
          const diffTxt = (r.diff >= 0 ? '+' : '') + r.diff;
          return `${cut ? `<tr class="cutoff-row"><td colspan="${ncols}"><span class="cutoff-line">— playoff cut line —</span></td></tr>` : ''}
          <tr class="${r.is_user ? 'user-team' : ''} clickable" data-href="/team/${encodeURIComponent(r.name)}" title="Open team overview">
            <td class="rank">${i + 1}</td>
            <td class="tname">${esc(r.name)}<span class="div-tag">${esc(r.division || '')}</span>${r.streak ? `<span class="streak-tag">${esc(r.streak)}</span>` : ''}</td>
            <td class="num">${r.gp}</td><td class="num">${r.w}</td>
            <td class="num">${r.l}</td><td class="num">${r.otl}</td>
            ${adv ? `<td class="num">${r.gf}</td><td class="num">${r.ga}</td>
              <td class="num ${diffCls}">${diffTxt}</td>
              <td class="num">${(r.pt_pct * 100).toFixed(1)}</td>` : ''}
            <td class="pts">${r.pts}</td>
          </tr>`;
        }).join('')}
        </tbody>
      </table>
    </div>`;
  wrap.appendChild(block);
}

document.getElementById('sort-pills').addEventListener('click', e => {
  const b = e.target.closest('.tb-pill');
  if (!b) return;
  document.querySelectorAll('#sort-pills .tb-pill').forEach(p => p.classList.remove('active'));
  b.classList.add('active');
  standState.sort = b.dataset.v;
  loadViews();
});
document.getElementById('adv-toggle').addEventListener('change', e => {
  standState.advanced = e.target.checked;
  loadViews();
});

/* ---------- team analytics ---------- */
function renderTaPills() {
  const host = document.getElementById('ta-cat-pills');
  host.innerHTML = '';
  for (const c of TA_CATS) {
    const b = document.createElement('button');
    b.className = 'tb-pill' + (c === standState.taCat ? ' active' : '');
    b.dataset.v = c;
    b.textContent = c;
    b.addEventListener('click', () => { standState.taCat = c; loadTeamAnalytics(); });
    host.appendChild(b);
  }
  const fh = document.getElementById('ta-filter-pills');
  fh.innerHTML = '';
  for (const f of TA_FILTERS) {
    const b = document.createElement('button');
    b.className = 'tb-pill' + (f === standState.taFilter ? ' active' : '');
    b.dataset.v = f;
    b.textContent = f;
    b.addEventListener('click', () => { standState.taFilter = f; loadTeamAnalytics(); });
    fh.appendChild(b);
  }
}
document.getElementById('ta-mode-pills').addEventListener('click', e => {
  const b = e.target.closest('.tb-pill');
  if (!b) return;
  document.querySelectorAll('#ta-mode-pills .tb-pill').forEach(p => p.classList.remove('active'));
  b.classList.add('active');
  standState.taMode = b.dataset.v;
  loadTeamAnalytics();
});

async function loadTeamAnalytics() {
  renderTaPills();
  const q = new URLSearchParams({
    category: standState.taCat, mode: standState.taMode,
    team_filter: standState.taFilter,
  });
  try {
    const res = await fetch('/api/standings/team-analytics?' + q);
    const d = await res.json();
    renderTeamAnalytics(d);
  } catch (e) { console.error(e); }
}

function fmtNum(v) {
  if (typeof v !== 'number') return v;
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function renderTeamAnalytics(d) {
  const host = document.getElementById('ta-table');
  const rows = d.rows || [];
  const avgs = d.averages || {};
  const vsAvg = d.mode === 'vs League Average';
  const cat = d.category || '';
  const cols = cat === 'Offensive Stats'
    ? [['gf_gp', 'GF/GP'], ['gf', 'GF'], ['pp_pct', 'PP%'], ['goal_share', 'Goal Share%']]
    : cat === 'Defensive Stats'
    ? [['ga_gp', 'GA/GP'], ['ga', 'GA'], ['pk_pct', 'PK%'], ['diff', '+/-']]
    : cat === 'Goaltending'
    ? [['team_sv_pct', 'SV%'], ['team_gaa', 'Team GAA'], ['ga', 'GA'], ['pk_pct', 'PK%']]
    : cat === 'Advanced Analytics'
    ? [['goal_share', 'Goal Share%'], ['pythag_pts', 'xPts'], ['diff', '+/-'], ['pt_pct', 'PT%']]
    : [['pts', 'PTS'], ['w', 'W'], ['diff', '+/-'], ['goal_share', 'Goal Share%']];
  host.innerHTML = `
    <div class="conf-block">
      <div class="conf-title">${esc(cat)}${vsAvg ? ' <span class="panel-note">Δ vs league average</span>' : ''}</div>
      <div class="stand-card"><table class="stand-table">
        <thead><tr><th class="rank">#</th><th>Team</th>
          ${cols.map(c => `<th class="num">${c[1]}</th>`).join('')}</tr></thead>
        <tbody>${rows.map((r, i) => `
          <tr class="${r.is_user ? 'user-team' : ''} clickable" data-href="/team/${encodeURIComponent(r.name)}" title="Open team overview">
            <td class="rank">${i + 1}</td>
            <td class="tname">${esc(r.name)}<span class="div-tag">${esc(r.division || '')}</span></td>
            ${cols.map(c => {
              let v = r[c[0]];
              let cls = 'num';
              if (vsAvg && avgs[c[0]] != null && typeof v === 'number') {
                const delta = v - avgs[c[0]];
                v = (delta >= 0 ? '+' : '') + delta.toFixed(c[0] === 'diff' ? 0 : 2);
                cls += delta >= 0 ? ' pos' : ' neg';
              } else if (typeof v === 'number' && c[0] === 'diff') {
                v = (v >= 0 ? '+' : '') + v;
                cls += v.toString().startsWith('+') ? ' pos' : ' neg';
              } else if (c[0] === 'team_sv_pct' && typeof v === 'number') {
                v = v.toFixed(3);
              } else {
                v = fmtNum(v);
              }
              return `<td class="${cls}">${v}</td>`;
            }).join('')}
          </tr>`).join('')}
        </tbody>
      </table></div>
    </div>`;
}

/* ---------- division analysis ---------- */
function renderDivPills(divisions) {
  const host = document.getElementById('div-pills');
  host.innerHTML = '';
  for (const dv of ['All Divisions', ...divisions]) {
    const b = document.createElement('button');
    b.className = 'tb-pill' + (dv === standState.div ? ' active' : '');
    b.dataset.v = dv;
    b.textContent = dv;
    b.addEventListener('click', () => { standState.div = dv; loadDivisionAnalysis(); });
    host.appendChild(b);
  }
  const th = document.getElementById('div-type-pills');
  th.innerHTML = '';
  for (const t of DIV_TYPES) {
    const b = document.createElement('button');
    b.className = 'tb-pill' + (t === standState.divType ? ' active' : '');
    b.dataset.v = t;
    b.textContent = t;
    b.addEventListener('click', () => { standState.divType = t; loadDivisionAnalysis(); });
    th.appendChild(b);
  }
}

async function loadDivisionAnalysis() {
  const q = new URLSearchParams({ division: standState.div, analysis: standState.divType });
  try {
    const res = await fetch('/api/standings/division-analysis?' + q);
    const d = await res.json();
    renderDivPills(d.divisions || []);
    renderDivisionAnalysis(d);
  } catch (e) { console.error(e); }
}

function renderDivisionAnalysis(d) {
  const host = document.getElementById('div-body');
  const a = d.analysis || 'Standings';
  let extra = '';
  if (a === 'Division vs League' && d.division_compare) {
    extra = `<div class="conf-block"><div class="conf-title">Division vs League</div>
      <div class="stand-card"><table class="stand-table"><thead><tr>
      <th>Division</th><th class="num">Teams</th><th class="num">Avg Pts</th>
      <th class="num">Avg GF</th><th class="num">Avg GA</th><th class="num">Goal Share%</th></tr></thead>
      <tbody>${d.division_compare.map(r => `
        <tr><td class="tname">${esc(r.division)}</td><td class="num">${r.teams}</td>
        <td class="num">${r.avg_pts}</td><td class="num">${r.avg_gf}</td>
        <td class="num">${r.avg_ga}</td><td class="num">${r.goal_share}</td></tr>`).join('')}
      </tbody></table></div></div>`;
  }
  if (a === 'Strength of Schedule' && d.sos) {
    extra = `<div class="conf-block"><div class="conf-title">Remaining Strength of Schedule <span class="panel-note">avg opponent PT%</span></div>
      <div class="stand-card"><table class="stand-table"><thead><tr>
      <th>Team</th><th class="num">Games Left</th><th class="num">Opp PT%</th></tr></thead>
      <tbody>${d.sos.map(r => `
        <tr class="${r.name === d.user_team ? 'user-team' : ''} clickable" data-href="/team/${encodeURIComponent(r.name)}" title="Open team overview">
        <td class="tname">${esc(r.name)}</td><td class="num">${r.games_left}</td>
        <td class="num">${(r.opp_pt_pct * 100).toFixed(1)}</td></tr>`).join('')}
      </tbody></table></div></div>`;
  }
  if (a === 'Head-to-Head' && d.note) {
    extra = `<div class="empty">${esc(d.note)}</div>`;
  }
  const rows = d.rows || [];
  host.innerHTML = extra + `
    <div class="conf-block">
      <div class="conf-title">${esc(d.division || '')} — ${esc(a)}</div>
      <div class="stand-card"><table class="stand-table">
        <thead><tr><th class="rank">#</th><th>Team</th>
        <th class="num">GP</th><th class="num">W</th><th class="num">L</th>
        <th class="num">OTL</th><th class="num">DIFF</th><th class="pts">PTS</th></tr></thead>
        <tbody>${rows.map((r, i) => `
          <tr class="${r.is_user ? 'user-team' : ''} clickable" data-href="/team/${encodeURIComponent(r.name)}" title="Open team overview">
            <td class="rank">${i + 1}</td>
            <td class="tname">${esc(r.name)}<span class="div-tag">${esc(r.division || '')}</span></td>
            <td class="num">${r.gp}</td><td class="num">${r.w}</td>
            <td class="num">${r.l}</td><td class="num">${r.otl}</td>
            <td class="num ${r.diff >= 0 ? 'pos' : 'neg'}">${r.diff >= 0 ? '+' : ''}${r.diff}</td>
            <td class="pts">${r.pts}</td></tr>`).join('')}
        </tbody>
      </table></div>
    </div>`;
}

/* ---------- divisions grid ---------- */
async function loadDivisionsGrid() {
  try {
    const res = await fetch('/api/standings/divisions-grid');
    const d = await res.json();
    const host = document.getElementById('div-grid');
    host.innerHTML = '';
    for (const dv of (d.divisions || [])) {
      const card = document.createElement('div');
      card.className = 'stand-card div-grid-card';
      card.innerHTML = `
        <div class="conf-title div-grid-title">${esc(dv.name)}</div>
        <table class="stand-table"><tbody>
          ${dv.rows.map((r, i) => `
            <tr class="${r.is_user ? 'user-team' : ''} clickable" data-href="/team/${encodeURIComponent(r.name)}" title="Open team overview">
              <td class="rank">${i + 1}</td>
              <td class="tname">${esc(r.name)}</td>
              <td class="num">${r.w}-${r.l}-${r.otl}</td>
              <td class="pts">${r.pts}</td></tr>`).join('')}
        </tbody></table>`;
      host.appendChild(card);
    }
    if (!(d.divisions || []).length) host.innerHTML = '<div class="empty">No divisions yet.</div>';
  } catch (e) { console.error(e); }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadViews();

// Shared heartbeat: tells the game the tab is still open (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, label')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
