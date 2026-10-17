/* Puck Dynasty AHL hub — standings, scores, Calder Cup, team, prospects.
   Ported from ahl_league_window.py + ahl_stats_window.py ("Who's Cooking"). */
let ahlTeamIdx = null;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function playerLink(id, name) {
  return id
    ? `<span class="clickable-text" data-href="/player/${esc(id)}" title="Open player profile">${esc(name)}</span>`
    : esc(name);
}

document.getElementById('ahl-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#ahl-tabs .tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('main.ahl-main .tb-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('ahl-tab-' + b.dataset.tab).classList.remove('hidden');
  if (b.dataset.tab === 'standings') loadAhlStandings();
  if (b.dataset.tab === 'scores') loadAhlScores();
  if (b.dataset.tab === 'calder') loadAhlCalder();
  if (b.dataset.tab === 'team') loadAhlTeam();
  if (b.dataset.tab === 'prospects') loadAhlProspects();
});

/* ---------- standings ---------- */
async function loadAhlStandings() {
  try {
    const d = await (await fetch('/api/ahl/standings')).json();
    const rows = d.standings || [];
    const t = document.getElementById('ahl-standings');
    t.innerHTML = rows.length ? `<thead><tr><th class="rank">#</th><th>Farm Club</th>
      <th class="num">GP</th><th class="num">W</th><th class="num">L</th><th class="num">OTL</th>
      <th class="pts">PTS</th><th class="num">PT%</th><th class="num">GF</th><th class="num">GA</th>
      <th>NHL Affiliate</th></tr></thead>
      <tbody>${rows.map((r, i) => `<tr>
        <td class="rank">${i + 1}</td>
        <td class="tname">${esc(r.team)}</td>
        <td class="num">${r.gp}</td><td class="num">${r.w}</td>
        <td class="num">${r.l}</td><td class="num">${r.otl}</td>
        <td class="pts">${r.pts}</td><td class="num">${(r.pt_pct * 100).toFixed(1)}</td>
        <td class="num">${r.gf}</td><td class="num">${r.ga}</td>
        <td><span class="clickable-text" data-href="/team/${encodeURIComponent(r.affiliate)}" title="Open team overview">${esc(r.affiliate)}</span></td>
      </tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No AHL standings yet.</div></td></tr>';
  } catch (e) { console.error(e); }
}

/* ---------- scores ---------- */
async function loadAhlScores() {
  try {
    const d = await (await fetch('/api/ahl/scores')).json();
    const recent = d.recent || [], upcoming = d.upcoming || [];
    const tr = document.getElementById('ahl-recent');
    tr.innerHTML = recent.length ? `<thead><tr><th>Date</th><th>Away</th><th class="num">Final</th><th>Home</th></tr></thead>
      <tbody>${recent.map(r => `<tr><td class="rank">${esc(r.date)}</td>
        <td class="tname">${esc(r.away)}</td><td class="pts">${esc(r.final)}</td>
        <td class="tname">${esc(r.home)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No finals yet.</div></td></tr>';
    const tu = document.getElementById('ahl-upcoming');
    tu.innerHTML = upcoming.length ? `<thead><tr><th>Date</th><th>Away</th><th></th><th>Home</th></tr></thead>
      <tbody>${upcoming.map(g => `<tr><td class="rank">${esc(g.date)}</td>
        <td class="tname">${esc(g.away)}</td><td class="num">@</td>
        <td class="tname">${esc(g.home)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">Nothing scheduled.</div></td></tr>';
    document.getElementById('ahl-scores-note').textContent =
      `${recent.length} recent finals — ${upcoming.length} games upcoming.`;
  } catch (e) { console.error(e); }
}

/* ---------- Calder Cup ---------- */
async function loadAhlCalder() {
  const host = document.getElementById('ahl-calder');
  try {
    const d = await (await fetch('/api/ahl/calder')).json();
    let html = '';
    if (d.rounds && d.rounds.length) {
      html += `<div class="conf-title">Bracket ${d.season ? '— ' + esc(d.season) : ''}</div>`;
      for (const rnd of d.rounds) {
        html += `<div class="calder-round"><div class="calder-round-h">${esc(rnd.name)}</div>`;
        for (const s of rnd.series) {
          html += `<div class="calder-series">
            <span class="calder-match">${esc(s.away)} vs ${esc(s.home)}</span>
            <span class="calder-result">${s.winner ? `🏆 ${esc(s.winner)} wins${s.games ? ' in ' + s.games : ''}` : 'TBD'}</span>
          </div>`;
        }
        html += '</div>';
      }
      if (d.champion) {
        html += `<div class="calder-champ">🏆 ${esc(d.champion)} — Calder Cup Champions</div>`;
      }
    }
    if (d.champions && d.champions.length) {
      html += '<div class="conf-title" style="margin-top:18px">Past Champions</div><div class="stand-card"><table class="stand-table"><tbody>' +
        d.champions.map(c => `<tr><td class="rank">${esc(c.season)}</td>
          <td class="tname">🏆 ${esc(c.champion)}</td><td class="num">def.</td><td class="tname">${esc(c.runner_up)}</td></tr>`).join('') +
        '</tbody></table></div>';
    }
    if (!html) {
      html = '<div class="empty">No Calder Cup played yet — the playoffs run when the AHL regular season ends.</div>';
    } else {
      html += `<p class="panel-note">${esc(d.note || '')}</p>`;
    }
    host.innerHTML = html;
  } catch (e) { host.innerHTML = '<div class="empty">Could not load the Calder Cup bracket.</div>'; }
}

/* ---------- team ---------- */
async function loadAhlTeam() {
  try {
    const q = ahlTeamIdx != null ? '?idx=' + ahlTeamIdx : '';
    const d = await (await fetch('/api/ahl/team' + q)).json();
    const picker = document.getElementById('ahl-team-picker');
    if (!picker.options.length) {
      picker.innerHTML = (d.teams || []).map(t =>
        `<option value="${t.idx}">${esc(t.name)}</option>`).join('');
      if (d.selected) {
        ahlTeamIdx = d.selected.idx;
        picker.value = String(ahlTeamIdx);
      }
      picker.addEventListener('change', () => {
        ahlTeamIdx = parseInt(picker.value, 10);
        loadAhlTeam();
      });
    }
    const s = d.selected;
    const host = document.getElementById('ahl-team-body');
    if (!s) { host.innerHTML = '<div class="empty">Select a farm club.</div>'; return; }
    const r = s.record;
    host.innerHTML = `
      <div class="ahl-team-head">
        <div>
          <div class="ahl-team-name">${esc(s.name)}</div>
          <div class="panel-note">${r.w}-${r.l}-${r.otl} — ${r.pts} PTS${s.affiliate ? ' · NHL affiliate: ' + esc(s.affiliate) : ''}</div>
        </div>
      </div>
      <div class="ahl-two">
        <div class="stand-card">
          <div class="conf-title ahl-card-title">Roster <span class="panel-note">${s.roster.length} players</span></div>
          <table class="stand-table"><thead><tr><th>Player</th><th class="num">Pos</th>
            <th class="num">Age</th><th class="num">OVR</th><th class="num">GP</th>
            <th class="num">G</th><th class="num">A</th><th class="num">PTS</th></tr></thead>
            <tbody>${s.roster.map(p => `<tr>
              <td class="pname">${playerLink(p.id, p.player)}</td>
              <td class="num">${esc(p.pos)}</td><td class="num">${p.age}</td>
              <td class="num">${p.ovr}</td><td class="num">${p.gp}</td>
              <td class="num">${p.g}</td><td class="num">${p.a}</td>
              <td class="pts">${p.pts}</td></tr>`).join('')}</tbody></table>
        </div>
        <div class="stand-card">
          <div class="conf-title ahl-card-title">Upcoming <span class="panel-note">next 12</span></div>
          <table class="stand-table"><tbody>
            ${s.schedule.length ? s.schedule.map(g => `<tr>
              <td class="rank">${esc(g.date)}</td>
              <td class="num">${g.home ? 'vs' : '@'}</td>
              <td class="tname">${esc(g.opponent)}</td></tr>`).join('')
              : '<tr><td><div class="empty">Nothing scheduled.</div></td></tr>'}
          </tbody></table>
        </div>
      </div>`;
  } catch (e) { console.error(e); }
}

/* ---------- prospects ---------- */
async function loadAhlProspects() {
  try {
    const d = await (await fetch('/api/ahl/prospects')).json();
    const sk = d.skaters || [], ck = d.cooking || [], gl = d.goalies || [];
    const t1 = document.getElementById('ahl-pros-scorers');
    t1.innerHTML = sk.length ? `<thead><tr><th class="rank">#</th><th>Player</th>
      <th class="num">Farm</th><th class="num">Pos</th><th class="num">Age</th>
      <th class="num">GP</th><th class="num">G</th><th class="num">A</th><th class="num">PTS</th></tr></thead>
      <tbody>${sk.map(r => `<tr><td class="rank">${r.rank}</td>
        <td class="pname">${playerLink(r.id, r.player)}</td>
        <td class="num">${esc(r.team)}</td><td class="num">${esc(r.pos)}</td>
        <td class="num">${r.age}</td><td class="num">${r.gp}</td>
        <td class="num">${r.g}</td><td class="num">${r.a}</td>
        <td class="pts">${r.pts}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No AHL games logged yet.</div></td></tr>';
    const t2 = document.getElementById('ahl-pros-cooking');
    t2.innerHTML = ck.length ? `<thead><tr><th class="rank">#</th><th>Player</th>
      <th class="num">Farm</th><th class="num">GP</th><th class="num">PTS</th><th class="stat">P/GP</th></tr></thead>
      <tbody>${ck.map(r => `<tr><td class="rank">${r.rank}</td>
        <td class="pname">${playerLink(r.id, r.player)}<span class="pos-tag">${esc(r.pos)}</span></td>
        <td class="num">${esc(r.team)}</td><td class="num">${r.gp}</td>
        <td class="num">${r.pts}</td>
        <td class="stat" style="color:var(--accent)">${r.ppg.toFixed(2)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">Nobody cooking yet.</div></td></tr>';
    const t3 = document.getElementById('ahl-pros-goalies');
    t3.innerHTML = gl.length ? `<thead><tr><th class="rank">#</th><th>Goalie</th>
      <th class="num">Farm</th><th class="num">GP</th><th class="num">W</th>
      <th class="num">GAA</th><th class="stat">SV%</th></tr></thead>
      <tbody>${gl.map(r => `<tr><td class="rank">${r.rank}</td>
        <td class="pname">${playerLink(r.id, r.player)}</td>
        <td class="num">${esc(r.team)}</td><td class="num">${r.gp}</td>
        <td class="num">${r.w}</td><td class="num">${r.gaa.toFixed(2)}</td>
        <td class="stat" style="color:var(--accent)">${r.svp.toFixed(3)}</td></tr>`).join('')}</tbody>`
      : '<tr><td><div class="empty">No qualifying goalies yet.</div></td></tr>';
    document.getElementById('ahl-pros-note').textContent =
      sk.length ? `${sk.length} skaters with AHL games — all farms — NHL numbers never appear here.` : '';
  } catch (e) { console.error(e); }
}

async function boot() {
  try {
    const d = await (await fetch('/api/ahl/overview')).json();
    if (d.user_farm_idx != null) ahlTeamIdx = d.user_farm_idx;
    if (d.empty) {
      document.querySelector('main.ahl-main').insertAdjacentHTML('beforeend',
        '<div class="empty">No AHL data yet — the farm league starts with the season.</div>');
    }
  } catch (e) { /* non-fatal */ }
  loadAhlStandings();
}

boot();

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
