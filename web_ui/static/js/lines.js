/* Puck Dynasty — game-style line editor (overhaul 2026-10-04)
 *
 * Two-panel editor: draggable roster cards on the left, visual line units
 * on the right. Drag-and-drop + click-to-place. Position-fit feedback
 * (green/yellow/red) uses the same familiarity table as position_training.
 * Writes go through POST /api/lines/set — the payload format is unchanged.
 */
'use strict';

/* ---------------- config ---------------- */
const LINE_SLOTS = [
  'LW1','C1','RW1','LW2','C2','RW2','LW3','C3','RW3','LW4','C4','RW4',
  'LD1','RD1','LD2','RD2','LD3','RD3','G1','G2',
];
const GOALIE_SLOTS = new Set(['G1', 'G2']);
const UNITS = [
  { title: 'Forwards', units: [
    { label: 'Line 1', slots: ['LW1','C1','RW1'] },
    { label: 'Line 2', slots: ['LW2','C2','RW2'] },
    { label: 'Line 3', slots: ['LW3','C3','RW3'] },
    { label: 'Line 4', slots: ['LW4','C4','RW4'] },
  ]},
  { title: 'Defense', units: [
    { label: 'Pairing 1', slots: ['LD1','RD1'] },
    { label: 'Pairing 2', slots: ['LD2','RD2'] },
    { label: 'Pairing 3', slots: ['LD3','RD3'] },
  ]},
  { title: 'Goalies', units: [
    { label: 'Net', slots: ['G1','G2'] },
  ]},
];
const SLOT_LABELS = { G1: 'Starter', G2: 'Backup' };

/* Familiarity table mirrored from position_training._BASE_FAMILIARITY.
 * Green  = natural position (exact match).
 * Yellow = playable (familiarity >= 60).
 * Red    = out of position. */
const FAM = {
  C:  { C:100, LW:65, RW:65, LD:35, RD:35, G:5 },
  LW: { LW:100, RW:80, C:65, LD:35, RD:35, G:5 },
  RW: { RW:100, LW:80, C:65, LD:35, RD:35, G:5 },
  LD: { LD:100, RD:75, C:35, LW:35, RW:35, G:5 },
  RD: { RD:100, LD:75, C:35, LW:35, RW:35, G:5 },
  D:  { D:100, LD:85, RD:85, C:35, LW:35, RW:35, G:5 },
  G:  { G:100 },
};
function slotPos(slot) {
  let m = /^([A-Z]+)\d+$/.exec(slot || '');
  if (m) return m[1];
  // Special-teams slots: 'PP1_LW' -> 'LW', 'PK2_RD' -> 'RD'.
  m = /^[A-Z]+\d+_([A-Z]+)$/.exec(slot || '');
  return m ? m[1] : '';
}
function baseFam(fromPos, toPos) {
  const f = String(fromPos || '').toUpperCase();
  const t = String(toPos || '').toUpperCase();
  if (FAM[f] && FAM[f][t] != null) return FAM[f][t];
  if (f === 'G' || t === 'G') return 5;
  return 30;
}
function fitClass(p, slot) {
  if (!p) return '';
  const sp = slotPos(slot);
  if (String(p.position || '').toUpperCase() === sp) return 'fit-green';
  return baseFam(p.position, sp) >= 60 ? 'fit-yellow' : 'fit-red';
}
function posGroup(p) {
  const pos = String(p.position || '').toUpperCase();
  if (pos === 'G') return 'G';
  if (pos === 'LD' || pos === 'RD' || pos === 'D') return 'D';
  return 'F';
}
function ovrBand(ovr) {
  ovr = Number(ovr || 0);
  return ovr >= 82 ? 'ovr-hi' : ovr >= 72 ? 'ovr-mid' : 'ovr-lo';
}

/* ---------------- state ---------------- */
const S = {
  byId: {},       // playerId -> full player object
  slots: {},      // slot -> player object | null
  initial: {},    // slot -> playerId snapshot (for cancel/dirty)
  filter: 'ALL',
  q: '',
  sel: null,      // {kind:'roster', id} | {kind:'slot', slot}
  dirty: false,
};
let dragPayload = null; // {src:'roster'|'slot', id, slot?}
let justDragged = false; // suppress click-to-profile right after a drag

const $ = (id) => document.getElementById(id);
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function note(text, cls) {
  const n = $('lines-note');
  n.textContent = text;
  n.className = 'le-note' + (cls ? ' ' + cls : '');
}
function slotOf(playerId) {
  playerId = String(playerId);
  for (const [slot, p] of Object.entries(S.slots)) {
    if (p && String(p.id) === playerId) return slot;
  }
  return null;
}

/* ---------------- boot ---------------- */
async function boot() {
  try {
    const res = await fetch('/api/lines/editable');
    const data = await res.json();
    buildIndex(data);
    applyInitial(data);
    renderAll();
    wireEvents();
  } catch (e) {
    note('Could not load the line editor: ' + e, 'err');
  }
}
function buildIndex(data) {
  for (const slot of Object.keys(data.pools || {})) {
    for (const p of data.pools[slot] || []) {
      S.byId[String(p.id)] = p;
    }
  }
}
function applyInitial(data) {
  for (const s of data.slots || []) {
    let p = null;
    if (s.player && s.player.id != null) {
      p = S.byId[String(s.player.id)] ||
        { id: String(s.player.id), name: s.player.name || '?', position: '?', overall: 0, age: 0 };
    }
    S.slots[s.slot] = p;
    S.initial[s.slot] = p ? String(p.id) : '';
  }
  // Guarantee every slot key exists.
  for (const slot of LINE_SLOTS) {
    if (!(slot in S.slots)) { S.slots[slot] = null; S.initial[slot] = ''; }
  }
  S.dirty = false;
  stApplyInitial(data); // special-teams tab state (hoisted below)
}

/* ---------------- roster panel ---------------- */
function rosterList() {
  const q = S.q.trim().toLowerCase();
  return Object.values(S.byId)
    .filter((p) => S.filter === 'ALL' || posGroup(p) === S.filter)
    .filter((p) => !q || String(p.name || '').toLowerCase().includes(q))
    .sort((a, b) => (b.overall || 0) - (a.overall || 0));
}
function renderRoster() {
  const host = $('roster-list');
  host.innerHTML = '';
  const list = rosterList();
  $('roster-count').textContent = list.length + ' players';
  for (const p of list) host.appendChild(rosterCard(p));
}
function rosterCard(p) {
  const pid = String(p.id);
  const el = document.createElement('div');
  el.className = 'le-pcard';
  el.draggable = true;
  el.dataset.id = pid;
  const dressed = slotOf(pid);
  if (S.sel && S.sel.kind === 'roster' && S.sel.id === pid) el.classList.add('selected');
  const face = p.portrait
    ? '<img class="le-face" src="' + esc(p.portrait) + '" alt="" loading="lazy" onerror="this.remove()">'
    : '';
  el.innerHTML =
    '<span class="ovr ' + ovrBand(p.overall) + '">' + esc(p.overall) + '</span>' +
    face +
    '<span class="nm clickable-text" data-href="/player/' + esc(pid) + '" title="Open player profile"><span class="n">' + esc(p.name) + '</span>' +
    '<span class="s">Age ' + esc(p.age) + '</span></span>' +
    '<span class="pos">' + esc(p.position) + '</span>' +
    (dressed ? '<span class="dressed">' + esc(dressed) + '</span>' : '');
  el.addEventListener('dragstart', (e) => {
    justDragged = true;
    setTimeout(() => { justDragged = false; }, 150);
    dragPayload = { src: 'roster', id: pid };
    el.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    try { e.dataTransfer.setData('text/plain', pid); } catch (_) {}
  });
  el.addEventListener('dragend', () => { el.classList.remove('dragging'); dragPayload = null; clearDropHints(); });
  el.addEventListener('click', () => onCardClick(pid));
  return el;
}
function onCardClick(pid) {
  if (STS.sel && STS.sel.kind === 'roster' && STS.sel.id === pid) { STS.sel = null; }
  else if ($('st-section') && !$('st-section').hidden) { STS.sel = { kind: 'roster', id: pid }; stRenderAll(); return; }
  else if (S.sel && S.sel.kind === 'roster' && S.sel.id === pid) { S.sel = null; }
  else { S.sel = { kind: 'roster', id: pid }; }
  renderAll();
}

/* ---------------- units ---------------- */
function renderUnits() {
  const host = $('lines-units');
  host.innerHTML = '';
  for (const g of UNITS) {
    const sec = document.createElement('section');
    const h = document.createElement('div');
    h.className = 'le-unit-label';
    h.style.cssText = 'font-size:15px;margin:22px 0 12px;';
    h.textContent = g.title.toUpperCase();
    sec.appendChild(h);
    for (const u of g.units) {
      const div = document.createElement('div');
      div.className = 'le-unit';
      const lab = document.createElement('div');
      lab.className = 'le-unit-label';
      lab.textContent = u.label;
      const row = document.createElement('div');
      row.className = 'le-unit-row';
      for (const slot of u.slots) row.appendChild(slotEl(slot));
      div.appendChild(lab);
      div.appendChild(row);
      sec.appendChild(div);
    }
    host.appendChild(sec);
  }
}
function slotEl(slot) {
  const p = S.slots[slot];
  const el = document.createElement('div');
  el.className = 'le-slot' + (p ? ' filled ' + fitClass(p, slot) : '');
  el.dataset.slot = slot;
  if (S.sel && S.sel.kind === 'slot' && S.sel.slot === slot) el.classList.add('selected');
  const tag = document.createElement('div');
  tag.className = 'slot-tag';
  tag.textContent = SLOT_LABELS[slot] || slotPos(slot) + ' ' + slot.replace(/^[A-Z]+/, '');
  el.appendChild(tag);
  if (p) {
    const who = document.createElement('div');
    who.className = 'who';
    who.draggable = true;
    who.dataset.id = String(p.id);
    const wface = p.portrait
      ? '<img class="le-face" src="' + esc(p.portrait) + '" alt="" loading="lazy" onerror="this.remove()">'
      : '';
    who.innerHTML =
      wface +
      '<div class="n clickable-text" data-href="/player/' + esc(String(p.id)) + '" title="Open player profile">' + esc(p.name) + '</div>' +
      '<div class="s"><span class="' + ovrBand(p.overall) + '">' + esc(p.overall) + ' OVR</span> · ' +
      esc(p.position) + ' · Age ' + esc(p.age) + '</div>';
    who.addEventListener('dragstart', (e) => {
      justDragged = true;
      setTimeout(() => { justDragged = false; }, 150);
      dragPayload = { src: 'slot', slot, id: String(p.id) };
      who.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      try { e.dataTransfer.setData('text/plain', String(p.id)); } catch (_) {}
    });
    who.addEventListener('dragend', () => { who.classList.remove('dragging'); dragPayload = null; clearDropHints(); });
    who.addEventListener('click', (e) => { e.stopPropagation(); onSlotClick(slot); });
    el.appendChild(who);
    const x = document.createElement('button');
    x.className = 'unassign';
    x.title = 'Remove from lines';
    x.textContent = '✕';
    x.addEventListener('click', (e) => {
      e.stopPropagation();
      S.slots[slot] = null;
      markDirty();
      renderAll();
      note(p.name + ' removed from ' + slot + '.', '');
    });
    el.appendChild(x);
  } else {
    const hint = document.createElement('div');
    hint.className = 'slot-empty-hint';
    hint.textContent = 'Drop player here';
    el.appendChild(hint);
  }
  el.addEventListener('click', () => onSlotClick(slot));
  el.addEventListener('dragover', (e) => {
    if (!dragPayload) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    el.classList.add(validDrop(dragPayload, slot) ? 'drop-ok' : 'drop-bad');
  });
  el.addEventListener('dragleave', () => el.classList.remove('drop-ok', 'drop-bad'));
  el.addEventListener('drop', (e) => {
    e.preventDefault();
    if (dragPayload) handleDrop(dragPayload, slot);
    dragPayload = null;
    clearDropHints();
  });
  return el;
}
function onSlotClick(slot) {
  if (S.sel && S.sel.kind === 'slot' && S.sel.slot === slot) { S.sel = null; renderAll(); return; }
  if (S.sel) {
    // Selection pending: place onto this slot.
    const payload = S.sel.kind === 'roster'
      ? { src: 'roster', id: S.sel.id }
      : { src: 'slot', slot: S.sel.slot, id: slotPlayerId(S.sel.slot) };
    S.sel = null;
    if (payload.src === 'slot' && payload.slot === slot) { renderAll(); return; }
    handleDrop(payload, slot);
    return;
  }
  // Cross-tab: a special-teams selection -> place onto this ES slot too.
  if (STS.sel) {
    const pid = STS.sel.kind === 'slot' ? stSlotPlayerId(STS.sel.slot) : STS.sel.id;
    STS.sel = null;
    renderAll();
    if (pid) handleDrop({ src: 'roster', id: pid }, slot);
    return;
  }
  // No selection: select this slot's player (for swapping).
  if (S.slots[slot]) { S.sel = { kind: 'slot', slot }; renderAll(); }
}
function slotPlayerId(slot) {
  const p = S.slots[slot];
  return p ? String(p.id) : null;
}

/* ---------------- placement ---------------- */
function playerIsGoalie(p) { return String(p.position || '').toUpperCase() === 'G'; }
function validDrop(payload, slot) {
  const p = S.byId[String(payload.id)];
  if (!p) return false;
  const needGoalie = GOALIE_SLOTS.has(slot);
  return playerIsGoalie(p) === needGoalie;
}
function handleDrop(payload, targetSlot) {
  const p = S.byId[String(payload.id)];
  if (!p) return;
  if (!validDrop(payload, targetSlot)) {
    const want = GOALIE_SLOTS.has(targetSlot) ? 'Goalies can only play in net.' : 'Only skaters can play this slot.';
    note(want, 'err');
    const el = document.querySelector('.le-slot[data-slot="' + targetSlot + '"]');
    if (el) { el.classList.add('le-shake'); setTimeout(() => el.classList.remove('le-shake'), 600); }
    return;
  }
  const srcSlot = payload.src === 'slot' ? payload.slot : slotOf(p.id);
  if (srcSlot === targetSlot) return;
  const occupant = S.slots[targetSlot];
  if (occupant && String(occupant.id) === String(p.id)) return;
  // Place; displaced occupant swaps into the source slot (or back to roster).
  S.slots[targetSlot] = p;
  if (srcSlot && srcSlot !== targetSlot) S.slots[srcSlot] = occupant || null;
  markDirty();
  renderAll();
  const fit = fitClass(p, targetSlot);
  const fitNote = fit === 'fit-red' ? ' — out of position!' : fit === 'fit-yellow' ? ' — playable out of position.' : '.';
  note(p.name + ' → ' + targetSlot + fitNote, fit === 'fit-red' ? 'err' : '');
}
function unassignAll() {
  for (const slot of LINE_SLOTS) S.slots[slot] = null;
  S.sel = null;
  markDirty();
  renderAll();
}
function clearDropHints() {
  document.querySelectorAll('.le-slot.drop-ok,.le-slot.drop-bad').forEach((el) => {
    el.classList.remove('drop-ok', 'drop-bad');
  });
  document.querySelectorAll('.le-roster.drop-target').forEach((el) => el.classList.remove('drop-target'));
}

/* ---------------- toolbar ---------------- */
function markDirty() {
  S.dirty = true;
  $('btn-save').disabled = false;
}
function snapshotIds() {
  const out = {};
  for (const slot of LINE_SLOTS) out[slot] = S.slots[slot] ? String(S.slots[slot].id) : '';
  return out;
}
function autoBest() {
  const all = Object.values(S.byId);
  const gk = all.filter((p) => playerIsGoalie(p)).sort((a, b) => (b.overall || 0) - (a.overall || 0));
  const sk = all.filter((p) => !playerIsGoalie(p)).sort((a, b) => (b.overall || 0) - (a.overall || 0));
  const used = new Set();
  const next = {};
  const takeGoalie = () => {
    const p = gk.find((x) => !used.has(String(x.id)));
    if (p) used.add(String(p.id));
    return p || null;
  };
  next.G1 = takeGoalie();
  next.G2 = takeGoalie();
  // Line order first (strongest line gets the best players), exact position
  // match preferred, best remaining skater as fallback.
  const order = ['LW1','C1','RW1','LW2','C2','RW2','LW3','C3','RW3','LW4','C4','RW4',
                 'LD1','RD1','LD2','RD2','LD3','RD3'];
  for (const slot of order) {
    const want = slotPos(slot);
    let pick = sk.find((x) => !used.has(String(x.id)) && String(x.position || '').toUpperCase() === want)
            || sk.find((x) => !used.has(String(x.id)));
    if (pick) used.add(String(pick.id));
    next[slot] = pick || null;
  }
  S.slots = next;
  S.sel = null;
  markDirty();
  renderAll();
  note('Auto Best applied — review the fits, then Save Lines.', 'ok');
}
function cancelEdits() {
  for (const slot of LINE_SLOTS) {
    const id = S.initial[slot];
    S.slots[slot] = id ? (S.byId[id] || null) : null;
  }
  S.sel = null;
  S.dirty = false;
  $('btn-save').disabled = true;
  renderAll();
  note('Changes reverted.', '');
}
async function saveLines() {
  const lines = snapshotIds();
  $('btn-save').disabled = true;
  try {
    const res = await fetch('/api/lines/set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lines }),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      for (const slot of LINE_SLOTS) S.initial[slot] = lines[slot];
      S.dirty = false;
      renderAll();
      note('Lines saved — they take effect on the game thread.', 'ok');
    } else {
      $('btn-save').disabled = false;
      note('Could not save: ' + (data.error || 'unknown error'), 'err');
    }
  } catch (e) {
    $('btn-save').disabled = false;
    note('Request failed: ' + e, 'err');
  }
}

/* ---------------- render + events ---------------- */
function renderAll() {
  renderRoster();
  renderUnits();
  $('btn-save').disabled = !S.dirty;
  const n = Object.values(S.slots).filter(Boolean).length;
  $('lines-sub').textContent = n + ' of ' + LINE_SLOTS.length + ' slots filled' + (S.dirty ? ' · unsaved changes' : '');
  stRenderAll(); // special-teams tab (hoisted below)
}
function wireEvents() {
  $('btn-autobest').addEventListener('click', autoBest);
  $('btn-clear').addEventListener('click', () => {
    if (confirm('Clear all line assignments?')) {
      unassignAll();
      note('All slots cleared.', '');
    }
  });
  $('btn-cancel').addEventListener('click', cancelEdits);
  $('btn-save').addEventListener('click', saveLines);
  $('roster-search').addEventListener('input', (e) => { S.q = e.target.value; renderRoster(); });
  document.querySelectorAll('.le-filter').forEach((b) => {
    b.addEventListener('click', () => {
      document.querySelectorAll('.le-filter').forEach((x) => x.classList.remove('on'));
      b.classList.add('on');
      S.filter = b.dataset.f;
      renderRoster();
    });
  });
  // Roster panel is a drop target: dragging a dressed player here removes them.
  const panel = $('roster-panel');
  panel.addEventListener('dragover', (e) => {
    if (dragPayload && dragPayload.src === 'slot') {
      e.preventDefault();
      panel.classList.add('drop-target');
    }
  });
  panel.addEventListener('dragleave', () => panel.classList.remove('drop-target'));
  panel.addEventListener('drop', (e) => {
    e.preventDefault();
    panel.classList.remove('drop-target');
    if (dragPayload && dragPayload.src === 'slot') {
      const p = S.slots[dragPayload.slot];
      S.slots[dragPayload.slot] = null;
      markDirty();
      renderAll();
      if (p) note(p.name + ' removed from ' + dragPayload.slot + '.', '');
    }
    dragPayload = null;
    clearDropHints();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && S.sel) { S.sel = null; renderAll(); }
    if (e.key === 'Escape' && STS.sel) { STS.sel = null; renderAll(); }
  });
  $('tab-es').addEventListener('click', () => switchTab('es'));
  $('tab-st').addEventListener('click', () => switchTab('st'));
  $('btn-st-autobest').addEventListener('click', stAutoBest);
  $('btn-st-clear').addEventListener('click', () => {
    if (confirm('Clear all special-teams assignments?')) stClearAll();
  });
  $('btn-st-cancel').addEventListener('click', stCancelEdits);
  $('btn-st-save').addEventListener('click', stSave);
}

boot();

// Shared heartbeat: tells the game the tab is still open (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', { method: 'POST' }).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (suppressed right after drags).
document.addEventListener('click', (e) => {
  if (justDragged) return;
  if (e.target.closest('button, a, input, select')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});

/* ============================================================
 * Special Teams editor (PP1/PP2/PK1/PK2) — second tab.
 *
 * Same drag + click-to-place machinery as the even-strength
 * editor, skaters only. Slots map 1:1 to the server's
 * ST_SLOTS (PP1_LW..PP2_RD, PK1_LW..PK2_RD); a unit must be fully
 * filled (PP: 5, PK: 4) or fully empty — a cleared unit falls back
 * to the sim's default special-teams deployment. Writes go through
 * POST /api/lines/set_st.
 * ============================================================ */
const ST_LINE_SLOTS = [
  'PP1_LW','PP1_C','PP1_RW','PP1_LD','PP1_RD',
  'PP2_LW','PP2_C','PP2_RW','PP2_LD','PP2_RD',
  'PK1_LW','PK1_RW','PK1_LD','PK1_RD',
  'PK2_LW','PK2_RW','PK2_LD','PK2_RD',
];
const ST_UNITS = [
  { label: 'PP1 — Power Play 1', slots: ['PP1_LW','PP1_C','PP1_RW','PP1_LD','PP1_RD'] },
  { label: 'PP2 — Power Play 2', slots: ['PP2_LW','PP2_C','PP2_RW','PP2_LD','PP2_RD'] },
  { label: 'PK1 — Penalty Kill 1', slots: ['PK1_LW','PK1_RW','PK1_LD','PK1_RD'] },
  { label: 'PK2 — Penalty Kill 2', slots: ['PK2_LW','PK2_RW','PK2_LD','PK2_RD'] },
];
const STS = { slots: {}, initial: {}, sel: null, dirty: false };

function stSlotTag(slot) {
  const m = /^([A-Z]+\d+)_([A-Z]+)$/.exec(slot || '');
  return m ? m[1] + ' · ' + m[2] : slot;
}
function stApplyInitial(data) {
  for (const s of data.st_slots || []) {
    let p = null;
    if (s.player && s.player.id != null) {
      p = S.byId[String(s.player.id)] ||
        { id: String(s.player.id), name: s.player.name || '?', position: '?', overall: 0, age: 0 };
    }
    STS.slots[s.slot] = p;
    STS.initial[s.slot] = p ? String(p.id) : '';
  }
  for (const slot of ST_LINE_SLOTS) {
    if (!(slot in STS.slots)) { STS.slots[slot] = null; STS.initial[slot] = ''; }
  }
  STS.dirty = false;
}
function stSlotOf(playerId) {
  playerId = String(playerId);
  for (const [slot, p] of Object.entries(STS.slots)) {
    if (p && String(p.id) === playerId) return slot;
  }
  return null;
}
function stMarkDirty() {
  STS.dirty = true;
  $('btn-st-save').disabled = false;
}
function stSnapshotIds() {
  const out = {};
  for (const slot of ST_LINE_SLOTS) out[slot] = STS.slots[slot] ? String(STS.slots[slot].id) : '';
  return out;
}
function stUnitOf(slot) {
  return ST_UNITS.find((u) => u.slots.includes(slot)) || null;
}

/* ---- ST rendering ---- */
function stRenderUnits() {
  const host = $('st-units');
  host.innerHTML = '';
  for (const u of ST_UNITS) {
    const sec = document.createElement('section');
    const div = document.createElement('div');
    div.className = 'le-unit';
    const lab = document.createElement('div');
    lab.className = 'le-unit-label';
    lab.textContent = u.label;
    const row = document.createElement('div');
    row.className = 'le-unit-row';
    for (const slot of u.slots) row.appendChild(stSlotEl(slot));
    div.appendChild(lab);
    div.appendChild(row);
    sec.appendChild(div);
    host.appendChild(sec);
  }
}
function stSlotEl(slot) {
  const p = STS.slots[slot];
  const el = document.createElement('div');
  el.className = 'le-slot' + (p ? ' filled ' + fitClass(p, slot) : '');
  el.dataset.slot = slot;
  if (STS.sel && STS.sel.kind === 'slot' && STS.sel.slot === slot) el.classList.add('selected');
  const tag = document.createElement('div');
  tag.className = 'slot-tag';
  tag.textContent = stSlotTag(slot);
  el.appendChild(tag);
  if (p) {
    const who = document.createElement('div');
    who.className = 'who';
    who.draggable = true;
    who.dataset.id = String(p.id);
    const wface = p.portrait
      ? '<img class="le-face" src="' + esc(p.portrait) + '" alt="" loading="lazy" onerror="this.remove()">'
      : '';
    who.innerHTML =
      wface +
      '<div class="n clickable-text" data-href="/player/' + esc(String(p.id)) + '" title="Open player profile">' + esc(p.name) + '</div>' +
      '<div class="s"><span class="' + ovrBand(p.overall) + '">' + esc(p.overall) + ' OVR</span> · ' +
      esc(p.position) + ' · Age ' + esc(p.age) + '</div>';
    who.addEventListener('dragstart', (e) => {
      justDragged = true;
      setTimeout(() => { justDragged = false; }, 150);
      dragPayload = { src: 'st-slot', slot, id: String(p.id) };
      who.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      try { e.dataTransfer.setData('text/plain', String(p.id)); } catch (_) {}
    });
    who.addEventListener('dragend', () => { who.classList.remove('dragging'); dragPayload = null; clearDropHints(); });
    who.addEventListener('click', (e) => { e.stopPropagation(); stOnSlotClick(slot); });
    el.appendChild(who);
    const x = document.createElement('button');
    x.className = 'unassign';
    x.title = 'Remove from special teams';
    x.textContent = '✕';
    x.addEventListener('click', (e) => {
      e.stopPropagation();
      STS.slots[slot] = null;
      stMarkDirty();
      stRenderAll();
      stNote(p.name + ' removed from ' + stSlotTag(slot) + '.', '');
    });
    el.appendChild(x);
  } else {
    const hint = document.createElement('div');
    hint.className = 'slot-empty-hint';
    hint.textContent = 'Drop skater here';
    el.appendChild(hint);
  }
  el.addEventListener('click', () => stOnSlotClick(slot));
  el.addEventListener('dragover', (e) => {
    if (!dragPayload) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    el.classList.add(stValidDrop(dragPayload, slot) ? 'drop-ok' : 'drop-bad');
  });
  el.addEventListener('dragleave', () => el.classList.remove('drop-ok', 'drop-bad'));
  el.addEventListener('drop', (e) => {
    e.preventDefault();
    if (dragPayload) stHandleDrop(dragPayload, slot);
    dragPayload = null;
    clearDropHints();
  });
  return el;
}
function stNote(text, cls) {
  const n = $('st-note');
  n.textContent = text;
  n.className = 'le-note' + (cls ? ' ' + cls : '');
}
function stOnSlotClick(slot) {
  if (STS.sel && STS.sel.kind === 'slot' && STS.sel.slot === slot) { STS.sel = null; stRenderAll(); return; }
  if (STS.sel) {
    const payload = STS.sel.kind === 'roster'
      ? { src: 'st-roster', id: STS.sel.id }
      : { src: 'st-slot', slot: STS.sel.slot, id: stSlotPlayerId(STS.sel.slot) };
    STS.sel = null;
    if (payload.src === 'st-slot' && payload.slot === slot) { stRenderAll(); return; }
    stHandleDrop(payload, slot);
    return;
  }
  // Cross-tab: an even-strength slot's player selected -> place them here
  // too (special-teamers usually also skate even strength).
  if (S.sel && S.sel.kind === 'slot') {
    const pid = slotPlayerId(S.sel.slot);
    S.sel = null;
    renderAll();
    if (pid) stHandleDrop({ src: 'st-roster', id: pid }, slot);
    return;
  }
  if (STS.slots[slot]) { STS.sel = { kind: 'slot', slot }; stRenderAll(); }
}
function stSlotPlayerId(slot) {
  const p = STS.slots[slot];
  return p ? String(p.id) : null;
}

/* ---- ST placement: skaters only, no cross-unit duplicates ---- */
function stValidDrop(payload, slot) {
  const p = S.byId[String(payload.id)];
  if (!p) return false;
  if (playerIsGoalie(p)) return false;
  if (payload.src === 'st-slot' && payload.slot === slot) return true;
  const cur = stSlotOf(p.id);
  return cur === null || cur === slot;
}
function stHandleDrop(payload, targetSlot) {
  const p = S.byId[String(payload.id)];
  if (!p) return;
  if (playerIsGoalie(p)) {
    stNote('Goalies cannot play special teams.', 'err');
    return;
  }
  const dup = stSlotOf(p.id);
  const srcSlot = (payload.src === 'st-slot') ? payload.slot : dup;
  if (dup && dup !== targetSlot && dup !== srcSlot) {
    stNote(p.name + ' is already on ' + stSlotTag(dup) + ' — one player, one special-teams job.', 'err');
    return;
  }
  if (srcSlot === targetSlot) return;
  const occupant = STS.slots[targetSlot];
  if (occupant && String(occupant.id) === String(p.id)) return;
  STS.slots[targetSlot] = p;
  if (srcSlot && srcSlot !== targetSlot) STS.slots[srcSlot] = occupant || null;
  stMarkDirty();
  stRenderAll();
  const fit = fitClass(p, targetSlot);
  const fitNote = fit === 'fit-red' ? ' — out of position!' : fit === 'fit-yellow' ? ' — playable out of position.' : '.';
  stNote(p.name + ' → ' + stSlotTag(targetSlot) + fitNote, fit === 'fit-red' ? 'err' : '');
}
/* Roster cards (ES panel) can also be dropped onto ST slots: selecting a
 * roster card then clicking an ST slot places it. Handled in onCardClick
 * above (ST tab active -> STS selection). */

/* ---- ST toolbar ---- */
function stAutoBest() {
  const sk = Object.values(S.byId).filter((p) => !playerIsGoalie(p))
    .sort((a, b) => (b.overall || 0) - (a.overall || 0));
  const fw = sk.filter((p) => posGroup(p) === 'F');
  const df = sk.filter((p) => posGroup(p) === 'D');
  const used = new Set();
  const take = (pool, n) => {
    const out = [];
    for (const p of pool) {
      if (out.length >= n) break;
      if (used.has(String(p.id))) continue;
      used.add(String(p.id));
      out.push(p);
    }
    return out;
  };
  // Mirror the desktop auto-deploy: best offense on PP1, best defense on PK1.
  const pp1 = take(fw, 3).concat(take(df, 2));
  const pp2 = take(fw, 3).concat(take(df, 2));
  const pk1 = take(fw, 2).concat(take(df, 2));
  const pk2 = take(fw, 2).concat(take(df, 2));
  const assign = (unit, players) => {
    unit.slots.forEach((slot, i) => { STS.slots[slot] = players[i] || null; });
  };
  assign(ST_UNITS[0], pp1);
  assign(ST_UNITS[1], pp2);
  assign(ST_UNITS[2], pk1);
  assign(ST_UNITS[3], pk2);
  STS.sel = null;
  stMarkDirty();
  stRenderAll();
  stNote('Auto Best applied to special teams — review the fits, then Save Special Teams.', 'ok');
}
function stClearAll() {
  for (const slot of ST_LINE_SLOTS) STS.slots[slot] = null;
  STS.sel = null;
  stMarkDirty();
  stRenderAll();
  stNote('All special-teams slots cleared — cleared units fall back to the sim defaults on save.', '');
}
function stCancelEdits() {
  for (const slot of ST_LINE_SLOTS) {
    const id = STS.initial[slot];
    STS.slots[slot] = id ? (S.byId[id] || null) : null;
  }
  STS.sel = null;
  STS.dirty = false;
  $('btn-st-save').disabled = true;
  stRenderAll();
  stNote('Changes reverted.', '');
}
async function stSave() {
  // Client-side completeness check (server re-validates anyway).
  for (const u of ST_UNITS) {
    const filled = u.slots.filter((s) => STS.slots[s]).length;
    if (filled > 0 && filled < u.slots.length) {
      stNote(u.label.split(' — ')[0] + ' is incomplete (' + filled + '/' + u.slots.length +
             ') — fill every spot or clear the unit.', 'err');
      return;
    }
  }
  const st = stSnapshotIds();
  $('btn-st-save').disabled = true;
  try {
    const res = await fetch('/api/lines/set_st', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ st }),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      for (const slot of ST_LINE_SLOTS) STS.initial[slot] = st[slot];
      STS.dirty = false;
      stRenderAll();
      stNote('Special teams saved — they take effect on the game thread.', 'ok');
    } else {
      $('btn-st-save').disabled = false;
      stNote('Could not save: ' + (data.error || 'unknown error'), 'err');
    }
  } catch (e) {
    $('btn-st-save').disabled = false;
    stNote('Request failed: ' + e, 'err');
  }
}
function stRenderAll() {
  stRenderUnits();
  $('btn-st-save').disabled = !STS.dirty;
  const n = Object.values(STS.slots).filter(Boolean).length;
  $('st-sub').textContent = n + ' of ' + ST_LINE_SLOTS.length + ' slots filled' + (STS.dirty ? ' · unsaved changes' : '');
}
function switchTab(which) {
  const es = which === 'es';
  $('tab-es').classList.toggle('on', es);
  $('tab-st').classList.toggle('on', !es);
  $('es-section').hidden = !es;
  $('st-section').hidden = es;
}
