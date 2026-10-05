/* Puck Dynasty web lines */
async function loadLines() {
  try {
    const res = await fetch('/api/lines');
    const data = await res.json();
    renderUnits(data.units || []);
    renderRoster(data.roster || []);
  } catch (e) { console.error(e); }
}

function renderUnits(units) {
  const host = document.getElementById('lines-units');
  host.innerHTML = '';
  const groups = {};
  for (const u of units) (groups[u.group] = groups[u.group] || []).push(u);
  const order = ['forwards', 'defense', 'goalies', 'other'];
  const titles = { forwards: 'Forwards', defense: 'Defense', goalies: 'Goalies', other: 'Other' };
  for (const g of order) {
    const list = groups[g];
    if (!list) continue;
    const sec = document.createElement('section');
    sec.innerHTML = `<h2 class="lines-h2">${titles[g] || g}</h2>`;
    for (const u of list) {
      const div = document.createElement('div');
      div.className = 'unit';
      let slotsHtml = '';
      for (const s of u.slots || []) {
        const p = s.player;
        if (p) {
          const cap = p.captaincy ? `<span class="tag-${p.captaincy.toLowerCase()}">${esc(p.captaincy)}</span>` : '';
          slotsHtml += `<div class="slot">
            <div class="slot-pos">${esc(s.slot)}</div>
            <div class="slot-name">${esc(p.name)}${cap}</div>
            <div class="slot-sub">${esc(p.position)} · ${p.overall} OVR</div>
          </div>`;
        } else {
          slotsHtml += `<div class="slot slot-empty">
            <div class="slot-pos">${esc(s.slot)}</div>
            <div class="slot-name">Empty</div>
          </div>`;
        }
      }
      div.innerHTML = `<div class="unit-label">${esc(u.label)}</div><div class="unit-row">${slotsHtml}</div>`;
      sec.appendChild(div);
    }
    host.appendChild(sec);
  }
}

function renderRoster(roster) {
  const host = document.getElementById('lines-roster');
  document.getElementById('lines-sub').textContent = `${roster.length} players on roster`;
  host.innerHTML = '';
  const sorted = [...roster].sort((a, b) => b.overall - a.overall);
  for (const p of sorted) {
    const el = document.createElement('div');
    el.className = 'roster-chip';
    el.innerHTML = `<span class="ov">${p.overall}</span>${esc(p.name)}<span class="pos">${esc(p.position)}</span>`;
    host.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

/* ---- In-page line editor (real write path) ---- */
let editData = null;

const GROUP_DEFS = [
  { title: 'Forwards', units: [1, 2, 3, 4].map(n => ({ label: 'Line ' + n, slots: ['LW' + n, 'C' + n, 'RW' + n] })) },
  { title: 'Defense', units: [1, 2, 3].map(n => ({ label: 'Pairing ' + n, slots: ['LD' + n, 'RD' + n] })) },
  { title: 'Goalies', units: [{ label: 'Goalies', slots: ['G1', 'G2'] }] },
];

function setNote(text, cls) {
  const n = document.getElementById('lines-note');
  n.textContent = text;
  n.className = 'lines-note' + (cls ? ' ' + cls : '');
}

function setEditMode(on) {
  document.getElementById('lines-units').classList.toggle('hidden', on);
  document.getElementById('lines-editor').classList.toggle('hidden', !on);
  document.getElementById('edit-lines-btn').classList.toggle('hidden', on);
  document.getElementById('save-lines-btn').classList.toggle('hidden', !on);
  document.getElementById('cancel-lines-btn').classList.toggle('hidden', !on);
}

async function enterEdit() {
  try {
    const res = await fetch('/api/lines/editable');
    editData = await res.json();
    renderEditor(editData);
    setEditMode(true);
    setNote('Pick a player for each slot, then Save Lines.');
  } catch (e) { setNote('Could not load editor: ' + e, 'err'); }
}

function renderEditor(data) {
  const host = document.getElementById('lines-editor');
  host.innerHTML = '';
  const curBySlot = {};
  for (const s of data.slots || []) curBySlot[s.slot] = s.player;
  for (const g of GROUP_DEFS) {
    const sec = document.createElement('section');
    sec.innerHTML = `<h2 class="lines-h2">${g.title}</h2>`;
    for (const u of g.units) {
      const div = document.createElement('div');
      div.className = 'unit';
      let html = `<div class="unit-label">${esc(u.label)}</div><div class="unit-row">`;
      for (const slot of u.slots) {
        const pool = (data.pools || {})[slot] || [];
        const cur = curBySlot[slot];
        const curId = cur ? String(cur.id) : '';
        const opts = [`<option value="">— Empty —</option>`].concat(pool.map(p =>
          `<option value="${esc(p.id)}"${String(p.id) === curId ? ' selected' : ''}>${esc(p.name)} — ${esc(p.position)}, ${p.overall} OVR</option>`
        )).join('');
        html += `<div class="slot slot-edit">
          <div class="slot-pos">${esc(slot)}</div>
          <select data-slot="${esc(slot)}" aria-label="${esc(slot)}">${opts}</select>
        </div>`;
      }
      div.innerHTML = html + '</div>';
      sec.appendChild(div);
    }
    host.appendChild(sec);
  }
  host.querySelectorAll('select').forEach(sel =>
    sel.addEventListener('change', highlightDupes));
}

function currentSelections() {
  const out = {};
  document.querySelectorAll('#lines-editor select').forEach(sel => {
    out[sel.dataset.slot] = sel.value;
  });
  return out;
}

function highlightDupes() {
  const seen = {};
  document.querySelectorAll('#lines-editor select').forEach(sel => {
    const v = sel.value;
    sel.classList.remove('slot-dupe');
    if (!v) return;
    if (seen[v]) { sel.classList.add('slot-dupe'); seen[v].classList.add('slot-dupe'); }
    else seen[v] = sel;
  });
}

async function saveLines() {
  const lines = currentSelections();
  const seen = {}, dupes = [];
  for (const [slot, pid] of Object.entries(lines)) {
    if (!pid) continue;
    if (seen[pid]) dupes.push(pid);
    else seen[pid] = slot;
  }
  if (dupes.length) { setNote('One player per slot — fix the highlighted duplicates.', 'err'); return; }
  try {
    const res = await fetch('/api/lines/set', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({lines}),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      setEditMode(false);
      setNote('Lines saved — they take effect on the game thread.', 'ok');
      loadLines();
    } else {
      setNote('Could not save: ' + (data.error || 'unknown error'), 'err');
    }
  } catch (e) { setNote('Request failed: ' + e, 'err'); }
}

document.getElementById('edit-lines-btn').addEventListener('click', enterEdit);
document.getElementById('cancel-lines-btn').addEventListener('click', () => {
  setEditMode(false); setNote('Current lines. Use Edit Lines to change them.');
});
document.getElementById('save-lines-btn').addEventListener('click', saveLines);

loadLines();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
