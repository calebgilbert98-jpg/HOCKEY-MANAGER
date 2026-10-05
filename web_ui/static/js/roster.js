/* Puck Dynasty web roster */
async function loadRoster() {
  try {
    const res = await fetch('/api/roster');
    const players = await res.json();
    renderRoster(players);
  } catch (e) { console.error(e); }
}

function barColor(v) {
  if (v >= 75) return '#4CAF50';
  if (v >= 60) return '#8BC34A';
  if (v >= 45) return '#FFC107';
  if (v >= 30) return '#FF9800';
  return '#F44336';
}

function renderRoster(players) {
  const grid = document.getElementById('roster-grid');
  document.getElementById('roster-count').textContent =
    players.length + ' players';
  grid.innerHTML = '';
  // sort: captaincy first, then overall
  const rank = {C: 0, A: 1, '': 2};
  players.sort((a, b) =>
    (rank[a.captaincy] ?? 2) - (rank[b.captaincy] ?? 2) || b.overall - a.overall);
  for (const p of players) {
    const el = document.createElement('div');
    el.className = 'player-card' + (p.injured ? ' injured' : '');
    const sal = p.salary >= 1e6 ? '$' + (p.salary / 1e6).toFixed(2) + 'M'
                                : '$' + Math.round(p.salary / 1e3) + 'K';
    el.innerHTML = `
      <div class="p-head">
        <div class="p-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
        <div class="p-id">
          <div class="p-name">${esc(p.name)}${p.captaincy ? ' <span class="p-c">' + esc(p.captaincy) + '</span>' : ''}</div>
          <div class="p-sub">${esc(p.position)} · Age ${p.age} · ${sal}</div>
        </div>
      </div>
      <div class="p-bar"><span style="width:${Math.min(100, p.overall)}%;background:${barColor(p.overall)}"></span></div>
      ${p.injured ? '<div class="p-inj">Injured</div>' : ''}`;
    grid.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadRoster();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
