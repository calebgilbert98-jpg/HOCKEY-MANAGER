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
