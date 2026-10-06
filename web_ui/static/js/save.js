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
