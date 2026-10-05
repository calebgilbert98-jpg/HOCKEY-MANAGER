/* Puck Dynasty web standings */
async function loadStandings() {
  try {
    const res = await fetch('/api/standings');
    const data = await res.json();
    renderStandings(data);
  } catch (e) { console.error(e); }
}

function renderStandings(data) {
  const wrap = document.getElementById('stand-tables');
  const confs = data.conferences || {};
  const names = Object.keys(confs);
  if (data.user_team) {
    document.getElementById('stand-sub').textContent =
      data.user_team + ' · ' + names.length + ' conference' + (names.length === 1 ? '' : 's');
  }
  wrap.innerHTML = '';
  if (!names.length) {
    wrap.innerHTML = '<div class="empty">No standings available yet.</div>';
    return;
  }
  // Single "League" group -> one table; otherwise one table per conference.
  for (const conf of names) {
    const rows = confs[conf];
    const block = document.createElement('div');
    block.className = 'conf-block';
    block.innerHTML = `
      <div class="conf-title">${esc(conf)}</div>
      <div class="stand-card">
        <table class="stand-table">
          <thead><tr>
            <th class="rank">#</th><th>Team</th>
            <th class="num">GP</th><th class="num">W</th><th class="num">L</th>
            <th class="num">OTL</th><th class="pts">PTS</th>
          </tr></thead>
          <tbody>${rows.map((r, i) => `
            <tr class="${r.is_user ? 'user-team' : ''}">
              <td class="rank">${i + 1}</td>
              <td class="tname">${esc(r.name)}<span class="div-tag">${esc(r.division || '')}</span></td>
              <td class="num">${r.gp}</td>
              <td class="num">${r.w}</td>
              <td class="num">${r.l}</td>
              <td class="num">${r.otl}</td>
              <td class="pts">${r.pts}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
    wrap.appendChild(block);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadStandings();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
