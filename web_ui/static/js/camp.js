/* Puck Dynasty web camp screen */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

async function loadCamp() {
  try {
    const res = await fetch('/api/camp');
    const data = await res.json();
    renderCamp(data);
  } catch (e) { console.error(e); }
}

function renderCamp(data) {
  const stories = data.stories || [];
  document.getElementById('camp-window').textContent =
    'Camp window: ' + (data.camp_window || '');
  const over = (data.roster_size || 0) > 23 ? ' — camp invites have the roster over the 23-man limit, so cut/waiver decisions are pending' : '';
  document.getElementById('camp-note').textContent =
    `Camp ran ${data.camp_window || 'Sep 12–30'} and its storylines are below. ` +
    `${data.roster_size || 0} players are currently on the roster${over}.`;

  const tl = document.getElementById('timeline');
  tl.innerHTML = '';
  document.getElementById('camp-empty').hidden = stories.length > 0;
  for (const s of stories) {
    const el = document.createElement('div');
    el.className = 'tl-item';
    el.innerHTML = `
      <div class="tl-card">
        <div class="tl-date">${esc(s.date)}</div>
        <div class="tl-story">${esc(s.story)}</div>
      </div>`;
    tl.appendChild(el);
  }
}

loadCamp();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
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
