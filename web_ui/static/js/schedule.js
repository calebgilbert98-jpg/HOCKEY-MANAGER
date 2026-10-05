/* Puck Dynasty web schedule */
async function loadSchedule() {
  try {
    const res = await fetch('/api/schedule');
    const games = await res.json();
    renderSchedule(games);
  } catch (e) { console.error(e); }
}

function renderSchedule(games) {
  const list = document.getElementById('game-list');
  document.getElementById('sched-count').textContent =
    games.length + ' upcoming games';
  list.innerHTML = '';
  if (!games.length) {
    list.innerHTML = '<div class="empty">No upcoming games.</div>';
    return;
  }
  for (const g of games) {
    const el = document.createElement('div');
    el.className = 'game-row';
    el.innerHTML = `
      <div class="g-date">${esc(g.date)}</div>
      <div class="g-match">
        <span class="g-team">${esc(g.is_home ? g.home : g.away)}</span>
        <span class="g-vs">${g.is_home ? 'vs' : '@'}</span>
        <span class="g-team opp">${esc(g.opponent)}</span>
      </div>
      ${g.preseason ? '<span class="g-tag">Preseason</span>' : ''}
      ${g.is_home ? '<span class="g-tag home">Home</span>' : ''}`;
    list.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadSchedule();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
