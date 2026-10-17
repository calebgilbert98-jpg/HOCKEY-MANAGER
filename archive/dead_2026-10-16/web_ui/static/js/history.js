/* Puck Dynasty web history — champions, full awards, career leaders,
   Hall of Fame, advanced stats + glossary, season reviews, franchise
   records. Ported from main.py LeagueHistoryView (~30206-30653). */
let histBase = null;
const histState = { tab: 'champions', leadersCat: 'points' };
const loadedTabs = { champions: true };

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

document.getElementById('hist-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#hist-tabs .tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('main.history-main .tb-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('hist-tab-' + b.dataset.tab).classList.remove('hidden');
  histState.tab = b.dataset.tab;
  if (!loadedTabs[b.dataset.tab]) { loadedTabs[b.dataset.tab] = true; loadHistTab(b.dataset.tab); }
});

function loadHistTab(k) {
  if (k === 'awards') loadAwardsFull();
  else if (k === 'leaders') loadCareerLeaders();
  else if (k === 'hof') loadHof();
  else if (k === 'advanced') loadAdvStats();
  else if (k === 'reviews') loadReviews();
  else if (k === 'records') loadFranchiseRecords();
}

async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    histBase = await res.json();
    renderChampions(histBase);
  } catch (e) { console.error(e); }
}

function renderChampions(data) {
  const empty = document.getElementById('empty');
  const list = document.getElementById('champ-list');
  const seasons = data.seasons || [];
  if (!data.has_data) {
    empty.hidden = false;
    document.getElementById('hist-tabs').hidden = true;
    return;
  }
  empty.hidden = true;
  list.innerHTML = seasons.length ? seasons.map(s => `
    <div class="champ-card">
      <div class="champ-year">${esc(s.year)}</div>
      <div class="champ-team">🏆 <span class="clickable-text" data-href="/team/${encodeURIComponent(s.champion)}" title="Open team overview">${esc(s.champion)}</span></div>
      <div class="champ-detail">${s.runner_up ? `def. ${esc(s.runner_up)}${s.series_score ? ' ' + esc(s.series_score) : ''}` : ''}</div>
      ${s.conn_smythe ? `<div class="champ-detail">Conn Smythe: ${esc(s.conn_smythe)}</div>` : ''}
    </div>`).join('')
    : '<div class="empty">No champions yet.</div>';
}

/* ---------- full awards (desktop showed every award; web truncated) ---------- */
async function loadAwardsFull(year) {
  const host = document.getElementById('awards-list');
  try {
    const q = year ? '?year=' + encodeURIComponent(year) : '';
    const d = await (await fetch('/api/history/awards-full' + q)).json();
    const sel = document.getElementById('awards-year');
    if (!sel.options.length && d.years.length) {
      sel.innerHTML = d.years.map(y => `<option value="${y}">${y}</option>`).join('');
      sel.value = String(d.year);
      sel.addEventListener('change', () => loadAwardsFull(sel.value));
    }
    const awards = d.awards || {};
    const names = Object.keys(awards);
    host.innerHTML = names.length ? names.map(n => `
      <div class="award-row">
        <span class="award-name">${esc(n)}</span>
        <span class="award-winner">${esc(awards[n])}</span>
      </div>`).join('')
      : '<div class="empty">No awards recorded for this season.</div>';
    if (d.runner_up) {
      host.insertAdjacentHTML('beforeend',
        `<div class="panel-note" style="margin-top:8px">Final: ${esc(d.series_score || '')}</div>`);
    }
  } catch (e) { host.innerHTML = '<div class="empty">Could not load awards.</div>'; }
}

/* ---------- career leaders ---------- */
const LEADER_CATS = ['points', 'goals', 'assists', 'wins', 'shutouts', 'save_pct'];

async function loadCareerLeaders() {
  const host = document.getElementById('leaders-table');
  try {
    const d = await (await fetch('/api/history/career-leaders?category=' +
      encodeURIComponent(histState.leadersCat))).json();
    const pills = document.getElementById('leaders-cats');
    if (!pills.children.length) {
      for (const c of (d.categories || LEADER_CATS)) {
        const b = document.createElement('button');
        b.className = 'tb-pill' + (c === d.category ? ' active' : '');
        b.dataset.cat = c;
        b.textContent = c === 'save_pct' ? 'SV%' : c.toUpperCase();
        b.addEventListener('click', () => { histState.leadersCat = b.dataset.cat; loadCareerLeaders(); });
        pills.appendChild(b);
      }
    } else {
      [...pills.children].forEach(b =>
        b.classList.toggle('active', b.dataset.cat === d.category));
    }
    const rows = d.leaders || [];
    host.innerHTML = rows.length ? `<thead><tr><th class="rank">#</th><th>Player</th>
      <th>Team</th><th class="num">GP</th><th class="stat">${esc(d.value_label || '')}</th></tr></thead>
      <tbody>${rows.map(r => `<tr><td class="rank">${r.rank}</td>
        <td class="pname">${esc(r.name)}</td><td>${esc(r.team)}</td>
        <td class="num">${r.games}</td>
        <td class="stat" style="color:var(--accent)">${esc(r.value)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No leaders yet.</div></td></tr>';
  } catch (e) { host.innerHTML = '<tr><td><div class="empty">Could not load leaders.</div></td></tr>'; }
}

/* ---------- Hall of Fame ---------- */
async function loadHof() {
  const host = document.getElementById('hof-list');
  try {
    const d = await (await fetch('/api/history/hall-of-fame')).json();
    document.getElementById('hof-bar').textContent = d.bar || '';
    const rows = d.inductees || [];
    host.innerHTML = rows.length ? rows.map(ind => `
      <div class="hof-card">
        <div class="hof-name">${esc(ind.name)} <span class="panel-note">(${esc(ind.position)})</span></div>
        <div class="hof-year">Inducted ${esc(ind.year_inducted)}</div>
        <div class="hof-line">${esc(ind.line)}</div>
        ${ind.cups ? `<div class="hof-cups">🏆 ${ind.cups}× Stanley Cup</div>` : ''}
        ${ind.awards && ind.awards.length ? `<div class="panel-note">${ind.awards.map(esc).join(' · ')}</div>` : ''}
      </div>`).join('')
      : `<div class="empty">No Hall of Famers yet.<br>Players are inducted at retirement when they clear the bar.</div>`;
  } catch (e) { host.innerHTML = '<div class="empty">Could not load the Hall of Fame.</div>'; }
}

/* ---------- advanced stats + glossary ---------- */
async function loadAdvStats() {
  try {
    const d = await (await fetch('/api/history/advanced-stats')).json();
    document.getElementById('adv-note').textContent = d.note || '';
    const tt = document.getElementById('adv-teams');
    const teams = d.teams || [];
    tt.innerHTML = teams.length ? `<thead><tr><th>Team</th><th class="num">CF%</th>
      <th class="num">FF%</th><th class="num">xGF%</th><th class="num">GF%</th>
      <th class="num">PDO</th><th class="num">PP%</th><th class="num">PK%</th><th class="num">SRS</th></tr></thead>
      <tbody>${teams.map(t => `<tr><td class="pname">${esc(t.team)}</td>
        <td class="num">${t.cf_pct}</td><td class="num">${t.ff_pct}</td>
        <td class="num">${t.xgf_pct}</td><td class="num">${t.gf_pct}</td>
        <td class="num">${t.pdo}</td><td class="num">${t.pp_pct}</td>
        <td class="num">${t.pk_pct}</td><td class="num">${t.srs}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No data yet.</div></td></tr>';
    const al = document.getElementById('adv-leaders');
    al.innerHTML = Object.entries(d.leaders || {}).map(([label, info]) => `
      <div class="adv-col">
        <div class="adv-col-h" title="${esc(info.definition || '')}">${esc(label)}</div>
        ${(info.rows || []).map((r, i) => `<div class="adv-row">${i + 1}. ${esc(r.name)} <b>(${esc(r.value)})</b></div>`).join('')
        || '<div class="panel-note">—</div>'}
      </div>`).join('');
    const gl = document.getElementById('glossary');
    gl.innerHTML = Object.entries(d.glossary || {}).map(([k, v]) => `
      <div class="gloss-row"><span class="gloss-term">${esc(k)}</span>
      <span class="gloss-def">${esc(v)}</span></div>`).join('')
      || '<div class="empty">No glossary yet.</div>';
  } catch (e) { console.error(e); }
}

/* ---------- season reviews ---------- */
async function loadReviews(team, year) {
  try {
    const q = new URLSearchParams();
    if (team) q.set('team', team);
    if (year) q.set('year', year);
    const d = await (await fetch('/api/history/season-reviews?' + q)).json();
    const ts = document.getElementById('reviews-team');
    if (!ts.options.length && d.teams.length) {
      ts.innerHTML = d.teams.map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join('');
      ts.value = d.team || d.teams[0];
      ts.addEventListener('change', () => loadReviews(ts.value, null));
    }
    const ys = document.getElementById('reviews-year');
    ys.innerHTML = (d.years || []).map(y => `<option value="${esc(y)}">${esc(y)}</option>`).join('')
      || '<option value="">—</option>';
    if (d.year) ys.value = d.year;
    ys.onchange = () => loadReviews(ts.value, ys.value);
    document.getElementById('review-card').textContent =
      (d.lines || []).join('\n') ||
      'No season reviews archived for this club yet. They appear here at the end of each season.';
  } catch (e) {
    document.getElementById('review-card').textContent = 'Could not load season reviews.';
  }
}

/* ---------- franchise records ---------- */
async function loadFranchiseRecords() {
  try {
    const data = histBase || await (await fetch('/api/history')).json();
    const grid = document.getElementById('record-grid');
    const fr = data.records;
    if (!fr) { grid.innerHTML = '<div class="empty">No franchise records yet.</div>'; return; }
    const cards = [
      ['Skater — Career', fr.skater_career], ['Skater — Season', fr.skater_season],
      ['Goalie — Career', fr.goalie_career], ['Goalie — Season', fr.goalie_season],
      ['Team — Season', fr.team_season], ['Streaks', fr.streaks],
    ];
    grid.innerHTML = cards.map(([label, s]) => `
      <div class="record-card">
        <div class="record-label">${esc(label)}</div>
        <div class="record-count">${s ? s.records : 0}</div>
        <div class="panel-note">${s ? s.franchises : 0} franchises</div>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

loadHistory();

// Shared heartbeat
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
