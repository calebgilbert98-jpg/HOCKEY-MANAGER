/* Puck Dynasty — completed-game box score page.
   Params: ?date=YYYY-MM-DD&home=<team name>&away=<team name, optional> */
(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  }
  function el(id) { return document.getElementById(id); }
  function playerLink(pl) {
    if (pl && pl.pid) return `<a class="plink" href="/player/${encodeURIComponent(pl.pid)}">${esc(pl.name)}</a>`;
    return esc((pl && pl.name) || '?');
  }

  let DATA = null;
  let playersTeam = null;
  let linesTeam = null;

  function strengthBadge(s) {
    if (!s || s === 'EV') return '';
    const cls = s === 'PP' ? 'b-pp' : (s === 'SH' ? 'b-sh' : 'b-en');
    return `<span class="badge ${cls}">${esc(s)}</span>`;
  }

  function renderHeader() {
    const h = DATA.home, a = DATA.away;
    el('bs-away-abbr').textContent = a.abbr;
    el('bs-away-name').textContent = a.name;
    el('bs-away-score').textContent = a.score;
    el('bs-home-abbr').textContent = h.abbr;
    el('bs-home-name').textContent = h.name;
    el('bs-home-score').textContent = h.score;
    el('bs-away-link').href = '/team/' + encodeURIComponent(a.name);
    el('bs-home-link').href = '/team/' + encodeURIComponent(h.name);
    el('bs-date').textContent = DATA.date_label;
    el('bs-note').textContent = DATA.note ? ' · ' + DATA.note : '';
    document.title = `${a.abbr} ${a.score} @ ${h.score} ${h.abbr} — Box Score`;
    const st = el('bs-stars');
    st.innerHTML = '';
    const stars = DATA.three_stars || [];
    if (stars.length) {
      const medals = ['1st', '2nd', '3rd'];
      const wrap = document.createElement('div');
      wrap.className = 'stars-row';
      stars.forEach((s, i) => {
        const d = document.createElement('div');
        d.className = 'star' + (i === 0 ? ' first' : '');
        d.innerHTML = `<span class="star-medal">★ ${medals[i] || ''}</span> ${playerLink(s)}` +
          (s.team ? ` <span class="star-team">(${esc(s.team)})</span>` : '') +
          (s.detail ? ` <span class="star-detail">${esc(s.detail)}</span>` : '');
        wrap.appendChild(d);
      });
      st.appendChild(wrap);
    }
  }

  function renderScoring() {
    const pane = el('pane-scoring');
    const goals = DATA.scoring || [];
    if (!goals.length) {
      pane.innerHTML = '<div class="empty">Detailed scoring data is unavailable for this game.</div>';
      return;
    }
    let html = '';
    let lastPeriod = null;
    for (const g of goals) {
      if (g.period_label !== lastPeriod) {
        lastPeriod = g.period_label;
        html += `<div class="goal-period">${esc(lastPeriod)}</div>`;
      }
      const assists = (g.assists || []).map(playerLink).join(', ');
      const running = `${esc(DATA.away.abbr)} ${g.away_running} – ${g.home_running} ${esc(DATA.home.abbr)}`;
      html += `<div class="goal-card">
        <div class="goal-left">
          <div class="goal-scorer">${playerLink(g.scorer)}${assists ? ` <span class="goal-assists">(${assists})</span>` : ' <span class="goal-assists">(unassisted)</span>'}</div>
          <div class="goal-sub">${esc(g.time_str)}${g.strength && g.strength !== 'EV' ? ' · ' + esc(g.strength) : ''}${g.goal_type ? ' · ' + esc(g.goal_type) : ''}</div>
        </div>
        <div class="goal-right">${strengthBadge(g.strength)}<span class="goal-running">${esc(running)}</span></div>
      </div>`;
    }
    pane.innerHTML = html;
  }

  function renderTeamToggle(toggleId, teamNames, current, onPick) {
    const t = el(toggleId);
    t.innerHTML = '';
    teamNames.forEach(n => {
      const b = document.createElement('button');
      b.className = 'team-toggle-btn' + (n === current ? ' active' : '');
      b.textContent = n;
      b.addEventListener('click', () => onPick(n));
      t.appendChild(b);
    });
  }

  function renderPlayers() {
    const teams = DATA.players || {};
    const names = Object.keys(teams);
    if (!playersTeam || !teams[playersTeam]) playersTeam = names[0];
    renderTeamToggle('players-toggle', names, playersTeam, (n) => { playersTeam = n; renderPlayers(); });
    const body = el('players-body');
    const t = teams[playersTeam] || {skaters: [], goalies: []};
    if (!t.has_stats) {
      body.innerHTML = '<div class="empty">Per-player stats are unavailable for this game.</div>';
      return;
    }
    let html = '<div class="sec-label">Skaters</div><div class="tbl-wrap"><table class="bs-table"><thead><tr>' +
      ['Player', 'Pos', 'G', 'A', 'P', 'SOG', 'Hits', 'Blk', 'FO'].map(h => `<th>${h}</th>`).join('') +
      '</tr></thead><tbody>' +
      t.skaters.map(s =>
        `<tr><td class="c-player">${playerLink(s.player)}</td><td>${esc(s.pos)}</td><td>${s.g}</td><td>${s.a}</td><td class="c-pts">${s.p}</td><td>${s.sog}</td><td>${s.hits}</td><td>${s.blk}</td><td>${esc(s.fo)}</td></tr>`
      ).join('') + '</tbody></table></div>';
    if (t.goalies.length) {
      html += '<div class="sec-label">Goaltenders</div><div class="tbl-wrap"><table class="bs-table"><thead><tr>' +
        ['Goaltender', 'SA', 'Saves', 'SV%', 'GA'].map(h => `<th>${h}</th>`).join('') +
        '</tr></thead><tbody>' +
        t.goalies.map(g =>
          `<tr><td class="c-player">${playerLink(g.player)}</td><td>${g.sa}</td><td>${g.saves}</td><td>${g.svp == null ? '–' : g.svp.toFixed(1) + '%'}</td><td>${g.ga}</td></tr>`
        ).join('') + '</tbody></table></div>';
    }
    body.innerHTML = html;
  }

  function ratingClass(r) {
    if (r == null) return '';
    if (r >= 7.0) return 'r-good';
    if (r >= 5.5) return 'r-mid';
    return 'r-bad';
  }

  function renderLines() {
    const lines = DATA.lines || {};
    const names = Object.keys(lines);
    if (!linesTeam || !lines[linesTeam]) linesTeam = names[0];
    renderTeamToggle('lines-toggle', names, linesTeam, (n) => { linesTeam = n; renderLines(); });
    const body = el('lines-body');
    const units = lines[linesTeam] || [];
    if (!units.length || !units.some(u => (u.players || []).length)) {
      body.innerHTML = '<div class="empty">Line combinations are unavailable for this game.</div>';
      return;
    }
    body.innerHTML = units.map(u => `
      <div class="line-block">
        <div class="line-head"><span class="line-label">${esc(u.label)}</span>
          <span class="line-rating ${ratingClass(u.rating)}">Rating ${u.rating == null ? '–' : u.rating.toFixed(1)}</span></div>
        <div class="tbl-wrap"><table class="bs-table"><thead><tr>
          ${['Player', 'Pos', 'G', 'A', 'P', 'Grade', 'Key Stats'].map(h => `<th>${h}</th>`).join('')}
        </tr></thead><tbody>
          ${(u.players || []).map(p =>
            `<tr><td class="c-player">${playerLink(p.player)}</td><td>${esc(p.pos)}</td><td>${p.g}</td><td>${p.a}</td><td>${p.p}</td><td class="${ratingClass(p.grade)}">${p.grade == null ? '–' : p.grade.toFixed(1)}</td><td class="c-why">${esc(p.why)}</td></tr>`
          ).join('')}
        </tbody></table></div>
      </div>`).join('');
  }

  function renderTeams() {
    const body = el('teams-body');
    const rows = DATA.team_stats || [];
    const a = DATA.away, h = DATA.home;
    body.innerHTML = `<div class="tbl-wrap"><table class="bs-table cmp"><thead><tr>
        <th></th><th>${esc(a.abbr)}</th><th>${esc(h.abbr)}</th></tr></thead><tbody>` +
      rows.map(r => `<tr><td class="c-label">${esc(r.label)}</td><td class="c-num">${esc(r.away)}</td><td class="c-num">${esc(r.home)}</td></tr>`).join('') +
      '</tbody></table></div>';
  }

  function initTabs() {
    el('bs-tabs').addEventListener('click', (e) => {
      const btn = e.target.closest('.bs-tab');
      if (!btn) return;
      document.querySelectorAll('.bs-tab').forEach(b => b.classList.toggle('active', b === btn));
      const tab = btn.dataset.tab;
      ['scoring', 'players', 'lines', 'teams'].forEach(t => {
        el('pane-' + t).hidden = (t !== tab);
      });
      if (tab === 'players') renderPlayers();
      if (tab === 'lines') renderLines();
      if (tab === 'teams') renderTeams();
    });
  }

  async function load() {
    const q = new URLSearchParams(window.location.search);
    const date = q.get('date') || '', home = q.get('home') || '', away = q.get('away') || '';
    if (!date || !home) {
      el('bs-loading').hidden = true;
      const err = el('bs-error');
      err.hidden = false;
      err.textContent = 'Missing game parameters. Open a box score from the Schedule page.';
      return;
    }
    try {
      const url = '/api/boxscore?' + new URLSearchParams({date, home, away}).toString();
      const res = await fetch(url);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'box score unavailable');
      DATA = data;
      el('bs-loading').hidden = true;
      el('bs-content').hidden = false;
      renderHeader();
      renderScoring();
    } catch (e) {
      el('bs-loading').hidden = true;
      const err = el('bs-error');
      err.hidden = false;
      err.textContent = 'Could not load the box score: ' + e.message;
    }
  }

  initTabs();
  load();

  /* Shared heartbeat: tells the game the tab is still open (every 30s). */
  (function () {
    const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
    beat();
    setInterval(beat, 30000);
  })();
})();
