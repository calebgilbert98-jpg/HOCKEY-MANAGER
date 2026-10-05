/* Puck Dynasty web morale */
async function loadMorale() {
  try {
    const res = await fetch('/api/morale');
    const data = await res.json();
    renderMorale(data);
  } catch (e) { console.error(e); }
}

function barColor(v) {
  if (v == null) return '#666';
  if (v >= 80) return '#4CAF50';
  if (v >= 60) return '#8BC34A';
  if (v >= 40) return '#FFC107';
  return '#F44336';
}

function renderMorale(data) {
  const players = data.players || [];
  const summary = document.getElementById('morale-summary');
  const list = document.getElementById('morale-list');
  const avg = data.average;
  const low = players.filter(p => p.morale != null && p.morale < 40).length;
  summary.innerHTML = `
    <div class="summary-card">
      <div class="summary-label">Team Average</div>
      <div class="summary-value" style="color:${barColor(avg)}">${avg == null ? '—' : avg}</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">Players</div>
      <div class="summary-value">${data.count || 0}</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">At Risk (&lt; 40)</div>
      <div class="summary-value" style="color:${low ? '#F44336' : '#4CAF50'}">${low}</div>
    </div>
    ${data.team_chemistry != null ? `
    <div class="summary-card">
      <div class="summary-label">Team Chemistry</div>
      <div class="summary-value" style="color:${barColor(data.team_chemistry)}">${data.team_chemistry}</div>
    </div>` : ''}`;
  list.innerHTML = '';
  if (!players.length) {
    list.innerHTML = '<div class="morale-empty">No players on the roster.</div>';
    return;
  }
  for (const p of players) {
    const el = document.createElement('div');
    const isLow = p.morale != null && p.morale < 40;
    el.className = 'morale-row' + (isLow ? ' low' : '');
    const val = p.morale == null ? '—' : p.morale;
    el.innerHTML = `
      <div class="m-name">${esc(p.name)}${p.captaincy ? ' <span class="p-c">' + esc(p.captaincy) + '</span>' : ''}</div>
      <div class="m-pos">${esc(p.position)}</div>
      <div class="m-bar"><span style="width:${p.morale == null ? 0 : Math.min(100, p.morale)}%;background:${barColor(p.morale)}"></span></div>
      <div class="m-val" style="color:${barColor(p.morale)}">${val}</div>
      ${p.injured ? '<div class="m-note">Injured</div>' : ''}`;
    list.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

document.addEventListener('DOMContentLoaded', loadMorale);

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
