/* Puck Dynasty web schedule — full rebuild (Batch A).
   Month filter, My Team / League tabs, sortable columns, and per-game
   actions: Box Score (played), Watch (today's user game), Simulate
   (past games that were never played). */
(function () {
  'use strict';

  const state = {
    games: [], months: [], userTeam: '',
    tab: 'mine', month: 'all',
    sort: {key: 'date', dir: 1},
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  }
  function el(id) { return document.getElementById(id); }

  function teamLink(name) {
    return `<a class="plink" href="/team/${encodeURIComponent(name)}">${esc(name)}</a>`;
  }

  function boxScoreUrl(g) {
    return '/boxscore?' + new URLSearchParams({date: g.date_iso, home: g.home, away: g.away}).toString();
  }

  async function load() {
    try {
      const res = await fetch('/api/schedule_full');
      const data = await res.json();
      state.games = data.games || [];
      state.months = data.months || [];
      state.userTeam = data.user_team || '';
      renderMonthOptions();
      render();
    } catch (e) {
      console.error('schedule load failed', e);
      el('sched-empty').hidden = false;
      el('sched-empty').textContent = 'Could not load the schedule.';
    }
  }

  function renderMonthOptions() {
    const sel = el('month-select');
    sel.innerHTML = '<option value="all">All</option>';
    for (const m of state.months) {
      const o = document.createElement('option');
      o.value = m.key;
      o.textContent = m.label;
      sel.appendChild(o);
    }
    sel.value = state.month;
  }

  function filtered() {
    let rows = state.games.slice();
    if (state.tab === 'mine') rows = rows.filter(g => g.is_user);
    if (state.month !== 'all') rows = rows.filter(g => g.month === state.month);
    const {key, dir} = state.sort;
    const val = (g) => {
      if (key === 'date') return g.date_iso || '';
      if (key === 'matchup') return (g.away + ' ' + g.home).toLowerCase();
      if (key === 'score') return g.played ? (g.away_score + g.home_score) : -1;
      if (key === 'status') return (g.played ? '0' : '1') + g.status;
      return '';
    };
    rows.sort((a, b) => {
      const va = val(a), vb = val(b);
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return 0;
    });
    return rows;
  }

  function scoreCell(g) {
    if (!g.played) return '<span class="s-dash">–</span>';
    let s = `${g.away_score} – ${g.home_score}`;
    if (g.shootout) s += ' <span class="s-note">SO</span>';
    else if (g.overtime) s += ' <span class="s-note">OT</span>';
    return s;
  }

  function actionCell(g) {
    if (g.played && g.date_iso) {
      return `<a class="sched-action" href="${boxScoreUrl(g)}">Box Score</a>`;
    }
    if (g.is_today && g.is_user && !g.played) {
      return `<a class="sched-action primary" href="/watch">Watch</a>`;
    }
    if (!g.played && g.is_past && g.date_iso) {
      // Scheduled for a past date but never played — simmable (desktop parity).
      return `<button class="sched-action btn" data-sim="${esc(g.date_iso)}|${esc(g.home)}|${esc(g.away)}">Simulate</button>`;
    }
    return '<span class="s-dash">–</span>';
  }

  function statusCell(g) {
    let cls = 'st-sched';
    if (g.played) cls = 'st-final';
    else if (g.is_today) cls = 'st-today';
    return `<span class="st ${cls}">${esc(g.status)}</span>` +
      (g.preseason ? ' <span class="s-tag">Pre</span>' : '');
  }

  function render() {
    const rows = filtered();
    el('tab-mine').classList.toggle('active', state.tab === 'mine');
    el('tab-league').classList.toggle('active', state.tab === 'league');
    const played = state.games.filter(g => g.played).length;
    el('sched-count').textContent =
      `${state.games.length} games · ${played} played` +
      (state.tab === 'mine' && state.userTeam ? ` · ${state.userTeam}` : '');

    // sort indicators
    document.querySelectorAll('#sched-table th.sortable').forEach(th => {
      const ind = th.querySelector('.sort-ind');
      ind.textContent = th.dataset.sort === state.sort.key
        ? (state.sort.dir === 1 ? ' ▲' : ' ▼') : '';
    });

    const body = el('sched-body');
    body.innerHTML = '';
    el('sched-empty').hidden = rows.length > 0;
    const frag = document.createDocumentFragment();
    for (const g of rows) {
      const tr = document.createElement('tr');
      if (g.is_today) tr.className = 'row-today';
      tr.innerHTML =
        `<td class="c-date">${esc(g.date_label)}</td>` +
        `<td class="c-match">${teamLink(g.away)} <span class="s-at">@</span> ${teamLink(g.home)}</td>` +
        `<td class="c-score">${scoreCell(g)}</td>` +
        `<td class="c-status">${statusCell(g)}</td>` +
        `<td class="c-actions">${actionCell(g)}</td>`;
      frag.appendChild(tr);
    }
    body.appendChild(frag);
  }

  async function simulateGame(dateIso, home, away) {
    if (!confirm(`Simulate ${away} @ ${home} (${dateIso})? This records the result in your season.`)) return;
    try {
      await fetch('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'sim_missed_game', date_iso: dateIso, home, away}),
      });
      setTimeout(load, 1200);
    } catch (e) {
      console.error('simulate failed', e);
    }
  }

  function initControls() {
    el('tab-mine').addEventListener('click', () => { state.tab = 'mine'; render(); });
    el('tab-league').addEventListener('click', () => { state.tab = 'league'; render(); });
    el('month-select').addEventListener('change', (e) => { state.month = e.target.value; render(); });
    document.querySelectorAll('#sched-table th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const k = th.dataset.sort;
        if (state.sort.key === k) state.sort.dir *= -1;
        else state.sort = {key: k, dir: 1};
        render();
      });
    });
    el('sched-body').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-sim]');
      if (!btn) return;
      const [dateIso, home, away] = btn.dataset.sim.split('|');
      simulateGame(dateIso, home, away);
    });
  }

  initControls();
  load();

  /* Shared heartbeat: tells the game the tab is still open (every 30s). */
  (function () {
    const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
    beat();
    setInterval(beat, 30000);
  })();

  /* Shared: clickable entities navigate via data-href (not from action controls). */
  document.addEventListener('click', (e) => {
    if (e.target.closest('button, a, input, select')) return;
    const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
    if (t) window.location.href = t.dataset.href;
  });
})();
