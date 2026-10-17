/* Puck Dynasty Save / Load — real in-page save manager.
 *
 * Lists saves from the game's saves directory (GameSaveManager), saves
 * the current game under a custom name, loads a chosen save, and deletes
 * saves. Writes go through the Flask backend onto the Tk main thread;
 * outcomes are polled with a nonce. No Tk window is ever opened.
 */
const el = id => document.getElementById(id);

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function status(msg, kind) {
  const n = el('save-status');
  n.textContent = msg || '';
  n.className = 'save-status ' + (kind || '');
}

function newNonce() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}

async function loadMeta() {
  try {
    const res = await fetch('/api/save');
    const d = await res.json();
    el('save-team').textContent = d.team || '—';
    el('save-date').textContent = d.current_date || '—';
  } catch (e) { console.error(e); }
}

async function loadSaves() {
  const tbody = el('save-rows');
  try {
    const res = await fetch('/api/save/list');
    const d = await res.json();
    const saves = d.saves || [];
    el('save-count').textContent = saves.length
      ? '(' + saves.length + ')' : '';
    const auto = d.autosave || {};
    el('save-auto').textContent = auto.enabled
      ? 'On (every ' + (auto.frequency_days || '?') + ' days)' +
        (auto.last ? ' · last ' + auto.last : '')
      : 'Off';
    if (!saves.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-note">No saves yet — save your game above.</td></tr>';
      return;
    }
    tbody.innerHTML = '';
    for (const s of saves) {
      const tr = document.createElement('tr');
      const badge = s.is_autosave
        ? '<span class="badge-auto">Auto</span>'
        : '<span class="badge-manual">Manual</span>';
      tr.innerHTML =
        '<td><div class="save-fname">' + esc(s.filename) + '</div>' +
        (s.description ? '<div class="save-desc">' + esc(s.description) + '</div>' : '') +
        (s.category && s.category !== 'General'
          ? '<div class="save-desc">' + esc(s.category) + '</div>' : '') + '</td>' +
        '<td>' + esc(s.team) + '</td>' +
        '<td>' + esc(s.game_date) + '</td>' +
        '<td>' + esc(s.modified) + '</td>' +
        '<td>' + (s.size_kb >= 1024
          ? (s.size_kb / 1024).toFixed(1) + ' MB' : s.size_kb + ' KB') + '</td>' +
        '<td>' + badge + '</td>' +
        '<td class="col-actions"></td>';
      const actions = tr.querySelector('.col-actions');
      const loadBtn = document.createElement('button');
      loadBtn.className = 'btn-ghost';
      loadBtn.textContent = 'Load';
      loadBtn.addEventListener('click', () => doLoad(s));
      const delBtn = document.createElement('button');
      delBtn.className = 'btn-ghost danger';
      delBtn.textContent = 'Delete';
      delBtn.addEventListener('click', () => doDelete(s));
      actions.append(loadBtn, delBtn);
      // Batch D: rename / properties / export per save.
      const renBtn = document.createElement('button');
      renBtn.className = 'btn-ghost';
      renBtn.textContent = 'Rename';
      renBtn.addEventListener('click', () => doRename(s));
      const propBtn = document.createElement('button');
      propBtn.className = 'btn-ghost';
      propBtn.textContent = 'Properties';
      propBtn.addEventListener('click', () => doProperties(s));
      const expBtn = document.createElement('button');
      expBtn.className = 'btn-ghost';
      expBtn.textContent = 'Export';
      expBtn.addEventListener('click', () => doExport(s));
      actions.append(renBtn, propBtn, expBtn);
      tbody.appendChild(tr);
    }
  } catch (e) {
    console.error(e);
    tbody.innerHTML = '<tr><td colspan="7" class="empty-note">Could not load saves: ' +
      esc(e.message) + '</td></tr>';
  }
}

/* Poll /api/save/result until the nonce resolves (or 90s timeout). */
async function pollResult(nonce, busyMsg) {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 1000));
    try {
      const res = await fetch('/api/save/result?nonce=' + encodeURIComponent(nonce));
      const d = await res.json();
      if (!d.pending && d.result) return d.result;
    } catch (e) { /* keep polling */ }
  }
  return {ok: false, message: 'Timed out waiting for the game — ' + busyMsg};
}

async function doSave() {
  const btn = el('btn-save');
  const name = el('save-name').value.trim();
  btn.disabled = true;
  status('Saving…');
  try {
    const res = await fetch('/api/save/do', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, nonce: newNonce()}),
    });
    const d = await res.json();
    if (!d.ok) { status('Could not queue the save.', 'err'); return; }
    const r = await pollResult(d.nonce, 'it may still have saved; check the list below.');
    status(r.message, r.ok ? 'ok' : 'err');
    if (r.ok) { el('save-name').value = ''; loadSaves(); loadMeta(); }
  } catch (e) {
    status('Save failed: ' + e.message, 'err');
  } finally {
    btn.disabled = false;
  }
}

async function doLoad(s) {
  if (!window.confirm('Load "' + s.filename + '"? Any unsaved progress will be lost.')) return;
  status('Loading "' + s.filename + '"…');
  try {
    const res = await fetch('/api/save/load', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({save_id: s.id, nonce: newNonce()}),
    });
    const d = await res.json();
    if (!d.ok) { status('Could not queue the load.', 'err'); return; }
    const r = await pollResult(d.nonce, 'check whether the game date changed.');
    status(r.message, r.ok ? 'ok' : 'err');
    if (r.ok) { loadSaves(); loadMeta(); }
  } catch (e) {
    status('Load failed: ' + e.message, 'err');
  }
}

async function doDelete(s) {
  if (!window.confirm('Delete "' + s.filename + '" permanently?')) return;
  status('Deleting "' + s.filename + '"…');
  try {
    const res = await fetch('/api/save/delete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({save_id: s.id, nonce: newNonce()}),
    });
    const d = await res.json();
    if (!d.ok) { status('Could not queue the delete.', 'err'); return; }
    const r = await pollResult(d.nonce, 'check the list below.');
    status(r.message, r.ok ? 'ok' : 'err');
    if (r.ok) loadSaves();
  } catch (e) {
    status('Delete failed: ' + e.message, 'err');
  }
}

el('btn-save').addEventListener('click', doSave);
el('save-name').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSave();
});

loadMeta();
loadSaves();

// Shared heartbeat: tells the game the tab is still open (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

/* ==================================================================
 * Batch D: quick-save slots, rename, properties, export/import,
 * autosave config, Ctrl+S. Mirrors save_load_system.py quick slots,
 * rename_save, autosave options, and save-file export.
 * ================================================================== */

async function loadQuickSlots() {
  const grid = el('qs-grid');
  try {
    const res = await fetch('/api/save/quick_slots');
    const d = await res.json();
    grid.innerHTML = '';
    for (const s of (d.slots || [])) {
      const card = document.createElement('div');
      card.className = 'qs-card' + (s.exists ? '' : ' empty');
      card.innerHTML =
        '<div class="qs-slot">Slot ' + s.slot + '</div>' +
        (s.exists
          ? '<div class="qs-name">' + esc(s.name) + '</div>' +
            '<div class="qs-meta">' + esc(s.game_date || '') + '<br>' + esc(s.modified || '') + '</div>'
          : '<div class="qs-meta">Empty</div>') +
        '<button class="btn-primary btn-sm" data-slot="' + s.slot + '">' +
        (s.exists ? 'Overwrite quick-save' : 'Quick-save here') + '</button>';
      card.querySelector('button').addEventListener('click', () => doQuickSave(s.slot));
      grid.appendChild(card);
    }
  } catch (e) {
    grid.innerHTML = '<div class="empty-note">Could not load quick-save slots.</div>';
  }
}

async function doQuickSave(slot) {
  status('Quick-saving to slot ' + slot + '…');
  try {
    const res = await fetch('/api/save/quicksave', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slot, nonce: newNonce()}),
    });
    const d = await res.json();
    if (!d.ok) { status('Could not queue the quick-save.', 'err'); return; }
    const r = await pollResult(d.nonce, 'check slot ' + slot + ' below.');
    status(r.message, r.ok ? 'ok' : 'err');
    if (r.ok) { loadQuickSlots(); loadSaves(); loadMeta(); }
  } catch (e) {
    status('Quick-save failed: ' + e.message, 'err');
  }
}

async function doRename(s) {
  const name = prompt('Rename save "' + s.filename + '":', s.filename.replace(/\.hm$/, ''));
  if (!name || !name.trim()) return;
  status('Renaming…');
  try {
    const res = await fetch('/api/save/rename', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({save_id: s.id, new_name: name.trim(), nonce: newNonce()}),
    });
    const d = await res.json();
    if (!d.ok) { status('Could not queue the rename.', 'err'); return; }
    const r = await pollResult(d.nonce, 'check the list below.');
    status(r.message, r.ok ? 'ok' : 'err');
    if (r.ok) loadSaves();
  } catch (e) {
    status('Rename failed: ' + e.message, 'err');
  }
}

async function doProperties(s) {
  const body = el('props-body');
  body.innerHTML = 'Loading…';
  el('props-modal').hidden = false;
  try {
    const res = await fetch('/api/save/properties?save_id=' + encodeURIComponent(s.id));
    const p = await res.json();
    const row = (k, v) => '<div class="save-row"><span>' + esc(k) + '</span><b>' + esc(v) + '</b></div>';
    body.innerHTML =
      row('Filename', p.filename || s.filename) +
      row('Team', p.team || s.team || '—') +
      row('Game date', p.game_date || s.game_date || '—') +
      row('Season', p.season || '—') +
      row('Modified', p.modified || s.modified || '—') +
      row('Size', (p.size_kb >= 1024 ? (p.size_kb / 1024).toFixed(1) + ' MB' : (p.size_kb || s.size_kb) + ' KB')) +
      row('Type', p.is_autosave ? 'Autosave' : 'Manual') +
      (p.description ? row('Description', p.description) : '');
  } catch (e) {
    body.innerHTML = '<div class="empty-note">Could not load properties.</div>';
  }
}
el('props-close').addEventListener('click', () => { el('props-modal').hidden = true; });
el('props-ok').addEventListener('click', () => { el('props-modal').hidden = true; });

function doExport(s) {
  window.location.href = '/api/save/export?save_id=' + encodeURIComponent(s.id);
}

el('btn-import').addEventListener('click', async () => {
  const file = el('import-file').files[0];
  const note = el('import-status');
  if (!file) { note.textContent = 'Choose a .hm file first.'; return; }
  note.textContent = 'Importing…';
  try {
    const res = await fetch('/api/save/import?name=' + encodeURIComponent(file.name), {
      method: 'POST',
      headers: {'Content-Type': 'application/octet-stream'},
      body: file,
    });
    const d = await res.json();
    note.textContent = d.message || (d.ok ? 'Imported.' : 'Import failed.');
    if (d.ok) loadSaves();
  } catch (e) {
    note.textContent = 'Import failed: ' + e.message;
  }
});

async function loadAutosaveConfig() {
  try {
    const res = await fetch('/api/save/list');
    const d = await res.json();
    const auto = d.autosave || {};
    el('auto-enabled').textContent = auto.enabled ? 'On' : 'Off';
    el('auto-freq').value = String(auto.frequency_days || 7);
  } catch (e) { console.error(e); }
}
el('btn-autosave-save').addEventListener('click', async () => {
  const note = el('autosave-status');
  note.textContent = 'Saving…';
  try {
    const res = await fetch('/api/save/autosave_config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        enabled: true,
        frequency_days: parseInt(el('auto-freq').value, 10) || 7,
        nonce: newNonce(),
      }),
    });
    const d = await res.json();
    if (!d.ok) { note.textContent = 'Could not save.'; return; }
    const r = await pollResult(d.nonce, 'check the autosave line above.');
    note.textContent = r.message || (r.ok ? 'Saved.' : 'Failed.');
    if (r.ok) { loadAutosaveConfig(); loadSaves(); }
  } catch (e) {
    note.textContent = 'Save failed: ' + e.message;
  }
});

/* Ctrl+S quicksave anywhere on the page (desktop save_load_system.py:3214). */
document.addEventListener('keydown', async (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    status('Quick-saving…');
    try {
      const res = await fetch('/api/save/quick_slots');
      const d = await res.json();
      const slots = d.slots || [];
      // Use the newest occupied slot, else the first empty one.
      let slot = slots.find(s => !s.exists);
      const occupied = slots.filter(s => s.exists);
      if (occupied.length) {
        occupied.sort((a, b) => String(b.modified).localeCompare(String(a.modified)));
        slot = occupied[0];
      }
      if (!slot) { status('No quick-save slots available.', 'err'); return; }
      await doQuickSave(slot.slot);
    } catch (err) {
      status('Quick-save failed: ' + err.message, 'err');
    }
  }
});

loadQuickSlots();
loadAutosaveConfig();
