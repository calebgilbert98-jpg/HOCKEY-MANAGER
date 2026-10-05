/* Puck Dynasty web settings */
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    renderSettings(data);
    renderWatchMode();
  } catch (e) { console.error(e); }
}

async function renderWatchMode() {
  try {
    const res = await fetch('/api/watch_mode');
    const data = await res.json();
    const mode = data.mode || 'quick';
    const grid = document.getElementById('settings-grid');
    const card = document.createElement('div');
    card.className = 'set-card';
    card.innerHTML = `<h2>Game Day</h2>
      <div class="set-row"><span>How to handle games</span>
        <div class="seg-toggle" role="group" aria-label="Game day mode">
          <button class="${mode === 'watch' ? 'active' : ''}" data-mode="watch">📺 Watch games</button>
          <button class="${mode === 'quick' ? 'active' : ''}" data-mode="quick">⚡ Quick sim all</button>
        </div>
      </div>
      <p class="set-hint">Watch opens the live visualizer on game days. Quick sim resolves them instantly.</p>`;
    card.querySelectorAll('.seg-toggle button').forEach(btn => {
      btn.addEventListener('click', async () => {
        const m = btn.dataset.mode;
        await fetch('/api/watch_mode', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({mode: m}),
        });
        card.querySelectorAll('.seg-toggle button').forEach(b =>
          b.classList.toggle('active', b.dataset.mode === m));
      });
    });
    grid.prepend(card);
  } catch (e) { console.error(e); }
}

function renderSettings(data) {
  document.getElementById('settings-note').textContent = data.note || '';
  const grid = document.getElementById('settings-grid');
  grid.innerHTML = '';
  for (const cat of data.categories || []) {
    const card = document.createElement('div');
    card.className = 'set-card';
    const rows = cat.items.map(it => {
      const known = it.value !== null && it.value !== undefined;
      const cls = !known ? 'unknown'
        : it.value === 'On' ? 'on'
        : it.value === 'Off' ? 'off' : '';
      return `<div class="set-row"><span>${esc(it.label)}</span>` +
             `<b class="set-val ${cls}">${known ? esc(it.value) : 'needs settings API'}</b></div>`;
    }).join('');
    card.innerHTML = `<h2>${esc(cat.title)}</h2>${rows}`;
    grid.appendChild(card);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadSettings();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
