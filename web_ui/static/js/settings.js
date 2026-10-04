/* Puck Dynasty web settings */
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    renderSettings(data);
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
