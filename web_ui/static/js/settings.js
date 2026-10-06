/* Puck Dynasty settings — 5 tabs, every setting writable.
 * Batch D: GET /api/settings -> {tabs:[{id,title,items:[{label,key,widget,options,value,hint}]}]};
 * edits POST /api/settings {key, value}. The backend validates, writes to
 * settings.json through the game's own loader, and reads back to verify. */
let SETTINGS_TABS = [];
let ACTIVE_TAB = null;

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    SETTINGS_TABS = data.tabs || [];
    document.getElementById('settings-note').textContent = data.note || '';
    ACTIVE_TAB = SETTINGS_TABS[0] ? SETTINGS_TABS[0].id : null;
    renderTabs();
    renderActiveTab();
    renderWatchMode();
  } catch (e) { console.error(e); }
}

function renderTabs() {
  const host = document.getElementById('settings-tabs');
  host.innerHTML = '';
  for (const t of SETTINGS_TABS) {
    const b = document.createElement('button');
    b.className = 'set-tab' + (t.id === ACTIVE_TAB ? ' active' : '');
    b.setAttribute('role', 'tab');
    b.textContent = t.title;
    b.addEventListener('click', () => {
      ACTIVE_TAB = t.id;
      host.querySelectorAll('.set-tab').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      renderActiveTab();
    });
    host.appendChild(b);
  }
}

function renderActiveTab() {
  const tab = SETTINGS_TABS.find(t => t.id === ACTIVE_TAB);
  const grid = document.getElementById('settings-grid');
  grid.innerHTML = '';
  if (!tab) { grid.innerHTML = '<div class="empty">No settings loaded.</div>'; return; }
  const card = document.createElement('div');
  card.className = 'set-card wide';
  card.innerHTML = `<h2>${esc(tab.title)}</h2>`;
  for (const it of tab.items || []) {
    card.appendChild(renderItem(it));
  }
  grid.appendChild(card);
}

function renderItem(it) {
  const row = document.createElement('div');
  row.className = 'set-row';
  const lab = document.createElement('div');
  lab.className = 'set-label';
  lab.innerHTML = `<span>${esc(it.label)}</span>` +
    (it.hint ? `<small class="set-hint">${esc(it.hint)}</small>` : '');
  const ctl = document.createElement('div');
  ctl.className = 'set-control';
  if (it.widget === 'bool') {
    const tgl = document.createElement('button');
    tgl.className = 'set-toggle' + (it.value ? ' on' : '');
    tgl.setAttribute('role', 'switch');
    tgl.setAttribute('aria-checked', String(!!it.value));
    tgl.textContent = it.value ? 'On' : 'Off';
    tgl.addEventListener('click', () => {
      const nv = !(tgl.dataset.val === 'true');
      tgl.dataset.val = String(nv);
      saveSetting(it.key, nv, tgl);
    });
    tgl.dataset.val = String(!!it.value);
    ctl.appendChild(tgl);
  } else if (it.widget === 'multiselect') {
    const sel = document.createElement('select');
    sel.multiple = true;
    sel.size = Math.min(6, (it.options || []).length || 3);
    const cur = new Set(it.value || []);
    for (const o of it.options || []) {
      const opt = document.createElement('option');
      opt.value = o;
      opt.textContent = o;
      if (cur.has(o)) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener('change', () =>
      saveSetting(it.key, Array.from(sel.selectedOptions).map(o => o.value), sel));
    ctl.appendChild(sel);
  } else {
    // select
    const sel = document.createElement('select');
    sel.className = 'set-select';
    for (const o of it.options || []) {
      const opt = document.createElement('option');
      opt.value = o;
      opt.textContent = o;
      if (String(o) === String(it.value)) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener('change', () => saveSetting(it.key, sel.value, sel));
    ctl.appendChild(sel);
  }
  row.appendChild(lab);
  row.appendChild(ctl);
  return row;
}

async function saveSetting(key, value, ctl) {
  const state = document.getElementById('settings-save-state');
  state.textContent = 'Saving…';
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key, value}),
    });
    const d = await res.json();
    if (!res.ok || !d.ok) throw new Error((d && d.error) || 'save failed');
    // Paint the fresh value straight from the game's own loader.
    updateControl(ctl, d.value);
    state.textContent = 'Saved ✓';
    setTimeout(() => { if (state.textContent === 'Saved ✓') state.textContent = ''; }, 2000);
  } catch (e) {
    state.textContent = 'Save failed';
    console.error(e);
    alert('Could not save setting: ' + e.message);
  }
}

function updateControl(ctl, value) {
  if (!ctl) return;
  if (ctl.classList && ctl.classList.contains('set-toggle')) {
    ctl.dataset.val = String(!!value);
    ctl.classList.toggle('on', !!value);
    ctl.setAttribute('aria-checked', String(!!value));
    ctl.textContent = value ? 'On' : 'Off';
  } else if (ctl.tagName === 'SELECT' && !ctl.multiple) {
    Array.from(ctl.options).forEach(o => { o.selected = String(o.value) === String(value); });
  } else if (ctl.tagName === 'SELECT' && ctl.multiple) {
    const cur = new Set(value || []);
    Array.from(ctl.options).forEach(o => { o.selected = cur.has(o.value); });
  }
}

/* Watch-mode card (existing behavior, kept; renders under the settings card). */
async function renderWatchMode() {
  try {
    const res = await fetch('/api/watch_mode');
    const data = await res.json();
    const mode = data.mode || 'quick';
    const grid = document.getElementById('settings-grid');
    const card = document.createElement('div');
    card.className = 'set-card wide';
    card.innerHTML = `<h2>Game Day</h2>
      <div class="set-row"><div class="set-label"><span>How to handle games</span>
        <small class="set-hint">Watch opens the live visualizer on game days. Quick sim resolves them instantly.</small></div>
        <div class="set-control"><div class="seg-toggle" role="group" aria-label="Game day mode">
          <button class="${mode === 'watch' ? 'active' : ''}" data-mode="watch">📺 Watch games</button>
          <button class="${mode === 'quick' ? 'active' : ''}" data-mode="quick">⚡ Quick sim all</button>
        </div></div>
      </div>`;
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
    grid.appendChild(card);
  } catch (e) { console.error(e); }
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
