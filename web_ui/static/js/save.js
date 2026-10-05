/* Puck Dynasty web save/load */
async function loadSaveInfo() {
  try {
    const res = await fetch('/api/save');
    const data = await res.json();
    document.getElementById('save-team').textContent = data.team || '—';
    document.getElementById('save-date').textContent = data.current_date || '—';
    document.getElementById('save-last').textContent = data.last_save || '—';
  } catch (e) { console.error(e); }
}

async function postCommand(op) {
  const res = await fetch('/api/command', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({op}),
  });
  return res.json();
}

function status(msg, kind) {
  const el = document.getElementById('save-status');
  el.textContent = msg;
  el.className = 'save-status ' + (kind || '');
}

function wireTile(id, op, confirmText) {
  const el = document.getElementById(id);
  const go = async () => {
    if (confirmText && !window.confirm(confirmText)) return;
    status('Sending command…');
    try {
      const r = await postCommand(op);
      if (r && r.ok) status(`“${op}” queued — the game will handle it.`, 'ok');
      else status('Command failed: ' + ((r && r.error) || 'unknown'), 'err');
    } catch (e) {
      status('Command failed: ' + e.message, 'err');
    }
  };
  el.addEventListener('click', go);
  el.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
  });
}

wireTile('tile-save', 'save_game');
wireTile('tile-load', 'load_game',
  'Load a saved game? Any unsaved progress will be lost.');
loadSaveInfo();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
