/* Puck Dynasty web morale — full dressing room */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function chemColor(s) {
  if (s >= 65) return '#4CAF50';
  if (s >= 50) return '#FFC107';
  return '#F44336';
}

function respClass(r) {
  if (r === 'Bought in') return 'good';
  if (r === 'Tuning out') return 'warn';
  if (r === 'Quit on coach') return 'bad';
  return 'neutral';
}

async function loadMorale() {
  try {
    const res = await fetch('/api/morale');
    const d = await res.json();
    if (d.error) return;

    // Headline
    const chem = d.chemistry || {};
    document.getElementById('morale-headline').textContent =
      `Chemistry ${chem.score ?? '—'}/100 ${chem.label || ''}`;

    // Coach card
    const coach = d.coach;
    document.getElementById('coach-body').innerHTML = coach ? `
      <div class="coach-name">${esc(coach.name)}</div>
      <div class="coach-style">${esc(coach.style)}</div>
      <div class="dim">${esc(coach.description || '')}</div>
      <div class="coach-meta">GM trust: ${coach.gm_trust}/100</div>` :
      '<div class="dim">No head coach on staff.</div>';
    const lcBtn = document.getElementById('line-control-btn');
    if (lcBtn && coach) lcBtn.textContent =
      'Lines: ' + (coach.line_control === 'gm' ? 'YOU (GM)' : 'Coach');

    // Watch list
    const wl = d.watch_list || [];
    document.getElementById('watch-body').innerHTML = wl.length ?
      wl.map(i => {
        const icon = i.severity === 'high' ? '🔴' : i.severity === 'medium' ? '🟡' : '🟢';
        return `<div class="watch-item">${icon} ${esc(i.text)}</div>`;
      }).join('') :
      '<div class="dim">🟢 No structural issues detected. The room is stable.</div>';

    // Player response table
    document.getElementById('response-body').innerHTML = (d.players || []).map(p => `
      <tr>
        <td><strong>${esc(p.name)}</strong></td>
        <td>${esc(p.engagement || '—')}</td>
        <td><span class="resp resp-${respClass(p.response)}">${esc(p.response)}</span></td>
        <td>${p.happiness}/100</td>
        <td>${p.morale}</td>
        <td>${esc(p.tier)}</td>
      </tr>`).join('');

    // Dynamics feed
    const feed = d.feed || [];
    document.getElementById('feed-body').innerHTML = feed.length ?
      feed.map(e => {
        const icon = e.tone === 'up' ? '▲' : e.tone === 'down' ? '▼' : '•';
        const cls = e.tone === 'up' ? 'up' : e.tone === 'down' ? 'down' : '';
        return `<div class="feed-item"><span class="feed-icon ${cls}">${icon}</span>
          <span>${esc(e.date)} ${esc(e.text)}</span></div>`;
      }).join('') :
      '<div class="dim">No dynamics yet this season.</div>';

    // Hierarchy
    document.getElementById('hierarchy-body').innerHTML = (d.hierarchy || []).map(h => `
      <div class="hier-row"><strong>${esc(h.tier)}</strong> (${h.count}):
        ${esc(h.names.join(', '))}</div>`).join('');
  } catch (e) { console.error(e); }
}

// GM actions
document.querySelectorAll('#coach-card [data-action]').forEach(btn =>
  btn.addEventListener('click', async () => {
    const action = btn.dataset.action;
    btn.disabled = true;
    try {
      await fetch('/api/morale/action', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action}),
      });
      setTimeout(loadMorale, 1200);
    } catch (e) { console.error(e); }
    btn.disabled = false;
  }));

loadMorale();

(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
