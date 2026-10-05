/* Puck Dynasty web entry-draft board */
async function loadDraft() {
  try {
    const res = await fetch('/api/draft');
    const data = await res.json();
    renderDraft(data);
  } catch (e) { console.error(e); }
}

function renderDraft(d) {
  const board = document.getElementById('board');
  const summary = document.getElementById('draft-summary');
  document.getElementById('draft-count').textContent =
    d.active ? `Pick ${d.current_overall} of ${d.total_slots}` : '';
  if (!d.active) {
    document.getElementById('draft-title').textContent = 'Entry Draft';
    summary.innerHTML = '';
    board.innerHTML = '<div class="empty">No draft in progress.<br>The entry draft will appear here once the season reaches draft day.</div>';
    return;
  }
  document.getElementById('draft-title').textContent = d.year ? d.year + ' Entry Draft' : 'Entry Draft';
  const myPicks = d.user_picks || [];
  summary.innerHTML =
    `<span class="sum-pill">${d.made_count} / ${d.total_slots} picks made</span>` +
    (myPicks.length
      ? `<span class="sum-pill mine">Your next pick${myPicks.length > 1 ? 's' : ''}: ${myPicks.slice(0, 5).map(p => '#' + p).join(', ')}${myPicks.length > 5 ? ' +' + (myPicks.length - 5) + ' more' : ''}</span>`
      : '<span class="sum-pill">No remaining picks</span>');
  board.innerHTML = '';
  let lastRound = null;
  for (const b of (d.board || [])) {
    if (b.round !== lastRound) {
      lastRound = b.round;
      const h = document.createElement('div');
      h.className = 'round-head';
      h.textContent = lastRound > 0 ? 'Round ' + lastRound : 'Picks';
      board.appendChild(h);
    }
    const el = document.createElement('div');
    el.className = 'pick-row' +
      (b.is_user_pick ? ' mine' : '') +
      (b.is_current ? ' current' : '') +
      (b.made ? ' done' : '');
    const pr = b.prospect || {};
    el.innerHTML = `
      <div class="pick-num">#${b.overall}</div>
      <div class="pick-owner">${esc(b.owner)}${b.is_user_pick ? ' ⭐' : ''}</div>
      <div class="pick-player">${b.made
        ? `${esc(pr.name || '?')}<small>${esc(pr.position || '')}${pr.age ? ' · ' + pr.age + ' yrs' : ''}${pr.overall ? ' · OVR ' + pr.overall : ''}</small>`
        : '<span class="tbd">To be selected…</span>'}</div>`;
    board.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadDraft();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
