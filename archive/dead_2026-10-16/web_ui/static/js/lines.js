/* Puck Dynasty — game-style line editor (redesign 2026-10-06)
 *
 * Tabs: OVERVIEW (read-only condensed view of every line/unit) +
 * LINE 1-4 (editable: forwards + defense pairing, goalies on Line 1) +
 * PP1/PP2/PK1/PK2 (editable special-teams units).
 *
 * Drag-and-drop + click-to-place. Position-fit feedback (green/yellow/red)
 * uses the same familiarity table as position_training.
 *
 * IMPORTANT: saves always POST the FULL slot map. The backend
 * (validate_lines_payload -> apply_lines_payload) rebuilds the entire
 * lineup from the payload and fills missing slots with None — a partial
 * POST would wipe the other lines. Tabs are view filters only.
 */
'use strict';

/* ---------------- config ---------------- */
const LINE_SLOTS = [
  'LW1','C1','RW1','LW2','C2','RW2','LW3','C3','RW3','LW4','C4','RW4',
  'LD1','RD1','LD2','RD2','LD3','RD3','G1','G2',
];
const GOALIE_SLOTS = new Set(['G1', 'G2']);
const SLOT_LABELS = { G1: 'Starter', G2: 'Backup' };

/* Per-tab slot layout. Line tabs carry their forward line + defense
 * pairing (hockey-accurate: 3 pairings, 4 forward lines); goalies live
 * on the Line 1 tab. */
const LINE_TAB_DEF = {
  line1: { n: 1, fw: ['LW1','C1','RW1'], df: ['LD1','RD1'], gk: ['G1','G2'] },
  line2: { n: 2, fw: ['LW2','C2','RW2'], df: ['LD2','RD2'], gk: [] },
  line3: { n: 3, fw: ['LW3','C3','RW3'], df: ['LD3','RD3'], gk: [] },
  line4: { n: 4, fw: ['LW4','C4','RW4'], df: [], gk: [] },
};
const ES_TAB_IDS = ['line1', 'line2', 'line3', 'line4'];
const ST_TAB_IDS = ['pp1', 'pp2', 'pk1', 'pk2'];
const ST_LINE_SLOTS = [
  'PP1_LW','PP1_C','PP1_RW','PP1_LD','PP1_RD',
  'PP2_LW','PP2_C','PP2_RW','PP2_LD','PP2_RD',
  'PK1_LW','PK1_RW','PK1_LD','PK1_RD',
  'PK2_LW','PK2_RW','PK2_LD','PK2_RD',
];
const ST_UNITS = [
  { label: 'PP1 — Power Play 1', short: 'PP1', slots: ['PP1_LW','PP1_C','PP1_RW','PP1_LD','PP1_RD'] },
  { label: 'PP2 — Power Play 2', short: 'PP2', slots: ['PP2_LW','PP2_C','PP2_RW','PP2_LD','PP2_RD'] },
  { label: 'PK1 — Penalty Kill 1', short: 'PK1', slots: ['PK1_LW','PK1_RW','PK1_LD','PK1_RD'] },
  { label: 'PK2 — Penalty Kill 2', short: 'PK2', slots: ['PK2_LW','PK2_RW','PK2_LD','PK2_RD'] },
];
const ST_TAB_UNIT = { pp1: 0, pp2: 1, pk1: 2, pk2: 3 };

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
/* Per-unit quality: average OVR of filled slots + fit breakdown.
 * Powers the NHL-14-style line rating badge in each unit header. */
function unitStats(slots, slotMap) {
  let sum = 0, filled = 0, green = 0, yellow = 0, red = 0, pts = 0;
  for (const slot of slots) {
    const p = slotMap[slot];
    if (!p) continue;
    filled++;
    sum += Number(p.overall || 0);
    pts += Number(p.goals || 0) + Number(p.assists || 0);
    const f = fitClass(p, slot);
    if (f === 'fit-green') green++;
    else if (f === 'fit-yellow') yellow++;
    else if (f === 'fit-red') red++;
  }
  return {
    filled, total: slots.length,
    avg: filled ? Math.round(sum / filled) : null,
    pts,
    green, yellow, red,
  };
}
function moraleBand(m) {
  m = Number(m || 70);
  return m >= 70 ? 'mor-hi' : m >= 50 ? 'mor-mid' : 'mor-lo';
}
/* Badges shared by roster cards and slot chips: INJ / C / A / FATIGUED / HOT / COLD. */
function badgeHtml(p) {
  let h = '';
  const cap = String(p.captaincy || '').toUpperCase();
  if (cap === 'C' || cap === 'A') h += '<span class="cap-badge" title="Team captaincy">' + esc(cap) + '</span>';
  const hs = Number(p.hot_streak || 0);
  if (hs > 0) h += '<span class="hot-badge" title="' + hs + '-game point streak — red hot">🔥' + hs + '</span>';
  else if (p.cold) h += '<span class="cold-badge" title="Scoreless drought (under 0.5 P/G, 72+ OVR)">❄️</span>';
  if (p.injured) h += '<span class="inj-badge" title="Injured">INJ</span>';
  else if (Number(p.condition || 100) < 80) h += '<span class="fat-badge" title="Low condition">TIRED</span>';
  return h;
}
/* Compact season stat line: "20 GP · 12-18-30" for skaters, ".915 SV%" for goalies. */
function statLine(p) {
  const gp = Number(p.games_played || 0);
  if (String(p.position || '').toUpperCase() === 'G') {
    const sv = p.save_pct != null ? Number(p.save_pct).toFixed(3).replace(/^0/, '') : '—';
    return gp + ' GP · ' + sv + ' SV%';
  }
  if (!gp) return 'No games yet';
  return gp + ' GP · ' + (p.goals || 0) + '-' + (p.assists || 0) + '-' + ((p.goals || 0) + (p.assists || 0));
}
/* Swap every slot of unit A with the matching slot of unit B
 * (LW1<->LW2, C1<->C2, ...). Works for ES and ST unit shapes. */
function swapUnitPlayers(slotsA, slotsB, slotMap) {
  for (let i = 0; i < Math.min(slotsA.length, slotsB.length); i++) {
    const a = slotsA[i], b = slotsB[i];
    const tmp = slotMap[a] || null;
    slotMap[a] = slotMap[b] || null;
    slotMap[b] = tmp;
  }
}

/* ---------------- state ---------------- */
const S = {
  byId: {},       // playerId -> full player object
  slots: {},      // slot -> player object | null (even strength)
  initial: {},    // slot -> playerId snapshot (for cancel/dirty)
  filter: 'ALL',
  sort: 'ovr',
  q: '',
  sel: null,      // {kind:'roster', id} | {kind:'slot', slot}
  dirty: false,
};
const STS = {
  slots: {},      // special-teams slot -> player object | null
  initial: {},
  sel: null,
  dirty: false,
};
const T = { tab: 'overview' };  // active tab id
let dragPayload = null; // {src:'roster'|'slot'|'st-roster'|'st-slot', id, slot?}
let justDragged = false; // suppress click-to-profile right after a drag

const $ = (id) => document.getElementById(id);
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function note(text, cls) {
  const n = $('lines-note');
  if (!n) return;
  n.textContent = text;
  n.className = 'le-note' + (cls ? ' ' + cls : '');
}
function stNote(text, cls) { note(text, cls); }  // single shared note line
function slotOf(playerId) {
  playerId = String(playerId);
  for (const [slot, p] of Object.entries(S.slots)) {
    if (p && String(p.id) === playerId) return slot;
  }
  return null;
}
function isESTab() { return T.tab === 'overview' || ES_TAB_IDS.includes(T.tab); }
function isSTTab() { return ST_TAB_IDS.includes(T.tab); }

/* ---------------- boot ---------------- */
async function boot() {
  try {
    const res = await fetch('/api/lines/editable');
    const data = await res.json();
    buildIndex(data);
    applyInitial(data);
    wireEvents();
    switchTab('overview');
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
  for (const slot of LINE_SLOTS) {
    if (!(slot in S.slots)) { S.slots[slot] = null; S.initial[slot] = ''; }
  }
  S.dirty = false;
  stApplyInitial(data);
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

/* ---------------- tabs ---------------- */
function switchTab(id) {
  T.tab = id;
  S.sel = null;
  STS.sel = null;
  document.querySelectorAll('#le-tabs .le-tab').forEach((b) => {
    const on = b.dataset.tab === id;
    b.classList.toggle('on', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  // Overview is read-only: hide the roster sidebar for max width.
  $('le-grid').classList.toggle('no-sidebar', id === 'overview');
  renderAll();
}
function tabSlotsES() {
  // All ES slots for the active line tab (for toolbar scoping).
  const def = LINE_TAB_DEF[T.tab];
  if (!def) return [];
  return def.fw.concat(def.df, def.gk);
}
function tabSlotsST() {
  const ui = ST_TAB_UNIT[T.tab];
  return ui == null ? [] : ST_UNITS[ui].slots;
}

/* ---------------- roster panel ---------------- */
function rosterList() {
  const q = S.q.trim().toLowerCase();
  const filtered = Object.values(S.byId)
    .filter((p) => {
      if (S.filter === 'ALL') return true;
      if (S.filter === 'HOT') return Number(p.hot_streak || 0) > 0;
      if (S.filter === 'COLD') return !!p.cold;
      return posGroup(p) === S.filter;
    })
    .filter((p) => !q || String(p.name || '').toLowerCase().includes(q));
  const pts = (p) => (Number(p.goals || 0) + Number(p.assists || 0));
  switch (S.sort) {
    case 'pts': filtered.sort((a, b) => pts(b) - pts(a) || (b.overall || 0) - (a.overall || 0)); break;
    case 'hot': filtered.sort((a, b) => (b.hot_streak || 0) - (a.hot_streak || 0) || pts(b) - pts(a)); break;
    case 'age': filtered.sort((a, b) => (a.age || 0) - (b.age || 0)); break;
    case 'name': filtered.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''))); break;
    default: filtered.sort((a, b) => (b.overall || 0) - (a.overall || 0));
  }
  return filtered;
}
function renderRoster() {
  const host = $('roster-list');
  if (!host) return;
  host.innerHTML = '';
  const list = rosterList();
  $('roster-count').textContent = list.length + ' players';
  for (const p of list) host.appendChild(rosterCard(p));
}
function rosterCard(p) {
  const pid = String(p.id);
  const el = document.createElement('div');
  el.className = 'le-pcard' + (p.injured ? ' is-injured' : '');
  el.draggable = true;
  el.dataset.id = pid;
  const dressed = slotOf(pid) || stSlotOf(pid);
  if ((S.sel && S.sel.kind === 'roster' && S.sel.id === pid) ||
      (STS.sel && STS.sel.kind === 'roster' && STS.sel.id === pid)) el.classList.add('selected');
  const face = p.portrait
    ? '<img class="le-face" src="' + esc(p.portrait) + '" alt="" loading="lazy" onerror="this.remove()">'
    : '';
  const mor = Math.max(0, Math.min(100, Number(p.morale == null ? 70 : p.morale)));
  el.innerHTML =
    '<span class="ovr ' + ovrBand(p.overall) + '">' + esc(p.overall) + '</span>' +
    face +
    '<span class="nm"><span class="n clickable-text" data-href="/player/' + esc(pid) + '" title="' + esc(p.name) + ' — open player profile">' + esc(p.name) + '</span>' +
    '<span class="s">Age ' + esc(p.age) + ' · ' + esc(statLine(p)) + '</span></span>' +
    '<span class="badges">' + badgeHtml(p) + '</span>' +
    '<span class="pos">' + esc(p.position) + '</span>' +
    (dressed ? '<span class="dressed">' + esc(dressed) + '</span>' : '') +
    '<span class="morale-bar" title="Morale ' + mor + '"><span class="' + moraleBand(mor) + '" style="width:' + mor + '%"></span></span>';
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
  if (T.tab === 'overview') return; // read-only
  if (isSTTab()) {
    if (STS.sel && STS.sel.kind === 'roster' && STS.sel.id === pid) STS.sel = null;
    else STS.sel = { kind: 'roster', id: pid };
    S.sel = null;
    renderAll();
    return;
  }
  // ES line tab.
  if (S.sel && S.sel.kind === 'roster' && S.sel.id === pid) S.sel = null;
  else S.sel = { kind: 'roster', id: pid };
  STS.sel = null;
  renderAll();
}

/* ---------------- editable slots (shared) ---------------- */
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
      badgeHtml(p) +
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
  if (S.slots[slot]) { S.sel = { kind: 'slot', slot }; renderAll(); }
}
function slotPlayerId(slot) {
  const p = S.slots[slot];
  return p ? String(p.id) : null;
}
function stSlotTag(slot) {
  const m = /^([A-Z]+\d+)_([A-Z]+)$/.exec(slot || '');
  return m ? m[1] + ' · ' + m[2] : slot;
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
      badgeHtml(p) +
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
      renderAll();
      note(p.name + ' removed from ' + stSlotTag(slot) + '.', '');
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
function stOnSlotClick(slot) {
  if (STS.sel && STS.sel.kind === 'slot' && STS.sel.slot === slot) { STS.sel = null; renderAll(); return; }
  if (STS.sel) {
    const payload = STS.sel.kind === 'roster'
      ? { src: 'st-roster', id: STS.sel.id }
      : { src: 'st-slot', slot: STS.sel.slot, id: stSlotPlayerId(STS.sel.slot) };
    STS.sel = null;
    if (payload.src === 'st-slot' && payload.slot === slot) { renderAll(); return; }
    stHandleDrop(payload, slot);
    return;
  }
  // Cross-tab: an even-strength slot's player selected -> place them here too.
  if (S.sel && S.sel.kind === 'slot') {
    const pid = slotPlayerId(S.sel.slot);
    S.sel = null;
    renderAll();
    if (pid) stHandleDrop({ src: 'st-roster', id: pid }, slot);
    return;
  }
  if (STS.slots[slot]) { STS.sel = { kind: 'slot', slot }; renderAll(); }
}
function stSlotPlayerId(slot) {
  const p = STS.slots[slot];
  return p ? String(p.id) : null;
}
function stSlotOf(playerId) {
  playerId = String(playerId);
  for (const [slot, p] of Object.entries(STS.slots)) {
    if (p && String(p.id) === playerId) return slot;
  }
  return null;
}

/* ---- shared editable unit block (label + OVR badge + swap + slots) ---- */
function editableUnit(label, slots, slotMap, slotElFn, swaps, dirtyFn) {
  const div = document.createElement('div');
  div.className = 'le-unit';
  const lab = document.createElement('div');
  lab.className = 'le-unit-label';
  const nameSpan = document.createElement('span');
  nameSpan.textContent = label;
  lab.appendChild(nameSpan);
  const st = unitStats(slots, slotMap);
  if (st.avg != null) {
    const badge = document.createElement('span');
    badge.className = 'unit-ovr ' + ovrBand(st.avg);
    badge.title = st.filled + '/' + st.total + ' slots filled · ' + st.pts + ' PTS · ' +
      st.green + ' natural, ' + st.yellow + ' playable, ' + st.red + ' out of position';
    badge.textContent = st.avg + ' OVR';
    lab.appendChild(badge);
    if (st.filled < st.total) {
      const inc = document.createElement('span');
      inc.className = 'unit-incomplete';
      inc.textContent = st.filled + '/' + st.total;
      lab.appendChild(inc);
    }
  }
  if (swaps && swaps.length) {
    const swapWrap = document.createElement('span');
    swapWrap.className = 'unit-swap';
    for (const sw of swaps) {
      const btn = document.createElement('button');
      btn.className = 'swap-btn';
      btn.title = 'Swap with ' + sw.label;
      btn.textContent = sw.dir === 'up' ? '▲' : sw.dir === 'down' ? '▼' : '⇄';
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        swapUnitPlayers(sw.slots, slots, slotMap);
        S.sel = null; STS.sel = null;
        dirtyFn();
        renderAll();
        note(label + ' ⇄ ' + sw.label + ' swapped.', '');
      });
      swapWrap.appendChild(btn);
    }
    lab.appendChild(swapWrap);
  }
  const row = document.createElement('div');
  row.className = 'le-unit-row';
  for (const slot of slots) row.appendChild(slotElFn(slot));
  div.appendChild(lab);
  div.appendChild(row);
  return div;
}

/* ---------------- tab content ---------------- */
function renderContent() {
  const host = $('tab-content');
  host.innerHTML = '';
  if (T.tab === 'overview') { renderOverview(host); return; }
  if (ES_TAB_IDS.includes(T.tab)) { renderLineTab(host, LINE_TAB_DEF[T.tab]); return; }
  if (ST_TAB_IDS.includes(T.tab)) { renderSTTab(host, ST_TAB_IDS.indexOf(T.tab)); }
}
function renderLineTab(host, def) {
  const sec = document.createElement('section');
  sec.className = 'le-ice';
  const fwSwaps = [];
  if (def.n > 1) fwSwaps.push({ dir: 'up', label: 'Line ' + (def.n - 1), slots: LINE_TAB_DEF['line' + (def.n - 1)].fw });
  if (def.n < 4) fwSwaps.push({ dir: 'down', label: 'Line ' + (def.n + 1), slots: LINE_TAB_DEF['line' + (def.n + 1)].fw });
  sec.appendChild(editableUnit('Line ' + def.n + ' — Forwards', def.fw, S.slots, slotEl, fwSwaps, markDirty));
  if (def.df.length) {
    const dfSwaps = [];
    if (def.n > 1 && LINE_TAB_DEF['line' + (def.n - 1)].df.length) {
      dfSwaps.push({ dir: 'up', label: 'Pairing ' + (def.n - 1), slots: LINE_TAB_DEF['line' + (def.n - 1)].df });
    }
    if (def.n < 3 && LINE_TAB_DEF['line' + (def.n + 1)].df.length) {
      dfSwaps.push({ dir: 'down', label: 'Pairing ' + (def.n + 1), slots: LINE_TAB_DEF['line' + (def.n + 1)].df });
    }
    sec.appendChild(editableUnit('Pairing ' + def.n + ' — Defense', def.df, S.slots, slotEl, dfSwaps, markDirty));
  }
  if (def.gk.length) {
    sec.appendChild(editableUnit('Goalies', def.gk, S.slots, slotEl, [], markDirty));
  }
  host.appendChild(sec);
}
function renderSTTab(host, ui) {
  const sec = document.createElement('section');
  sec.className = 'le-ice';
  const u = ST_UNITS[ui];
  // Swappable pairs: PP1<->PP2, PK1<->PK2.
  const pair = { 0: 1, 1: 0, 2: 3, 3: 2 }[ui];
  const swaps = pair != null
    ? [{ dir: 'swap', label: ST_UNITS[pair].short, slots: ST_UNITS[pair].slots }]
    : [];
  sec.appendChild(editableUnit(u.label, u.slots, STS.slots, stSlotEl, swaps, stMarkDirty));
  const hint = document.createElement('p');
  hint.className = 'le-note';
  hint.textContent = 'PP units need 5 skaters, PK units need 4; a cleared unit falls back to the sim\u2019s defaults.';
  sec.appendChild(hint);
  host.appendChild(sec);
}

/* ---- overview: condensed read-only grid of every line/unit ---- */
function ovChip(slot, p) {
  const el = document.createElement('div');
  el.className = 'ov-chip' + (p ? ' ' + fitClass(p, slot) : ' empty');
  const isST = /^[A-Z]+\d+_/.test(slot || '');
  const tag = isST ? stSlotTag(slot) : slotPos(slot) + slot.replace(/^[A-Z]+/, '');
  const nm = p
    ? '<span class="ov-name clickable-text" data-href="/player/' + esc(String(p.id)) + '" title="Open player profile">' + esc(p.name) + '</span>'
    : '<span class="ov-name dim">—</span>';
  const ovr = p ? '<span class="ovr ' + ovrBand(p.overall) + '">' + esc(p.overall) + '</span>' : '';
  el.innerHTML = '<span class="ov-tag">' + esc(tag) + '</span>' + nm + ovr;
  return el;
}
function ovLineRow(label, slots, slotMap) {
  const row = document.createElement('div');
  row.className = 'ov-row';
  const lab = document.createElement('div');
  lab.className = 'ov-row-label';
  lab.textContent = label;
  const st = unitStats(slots, slotMap);
  if (st.avg != null) {
    const b = document.createElement('span');
    b.className = 'unit-ovr ' + ovrBand(st.avg);
    b.textContent = st.avg;
    lab.appendChild(b);
  }
  row.appendChild(lab);
  const chips = document.createElement('div');
  chips.className = 'ov-chips';
  for (const slot of slots) chips.appendChild(ovChip(slot, slotMap[slot]));
  row.appendChild(chips);
  return row;
}
function renderOverview(host) {
  const wrap = document.createElement('div');
  wrap.className = 'ov-wrap';
  // Even strength column.
  const esCol = document.createElement('div');
  esCol.className = 'ov-col';
  const esH = document.createElement('div');
  esH.className = 'ov-sec-label';
  esH.textContent = 'Even Strength';
  esCol.appendChild(esH);
  for (let n = 1; n <= 4; n++) {
    const def = LINE_TAB_DEF['line' + n];
    esCol.appendChild(ovLineRow('Line ' + n, def.fw, S.slots));
  }
  const dpair = document.createElement('div');
  dpair.className = 'ov-sub-label';
  dpair.textContent = 'Defense Pairings';
  esCol.appendChild(dpair);
  for (let n = 1; n <= 3; n++) {
    esCol.appendChild(ovLineRow('Pair ' + n, ['LD' + n, 'RD' + n], S.slots));
  }
  esCol.appendChild(ovLineRow('Goalies', ['G1', 'G2'], S.slots));
  // Special teams column.
  const stCol = document.createElement('div');
  stCol.className = 'ov-col';
  const stH = document.createElement('div');
  stH.className = 'ov-sec-label';
  stH.textContent = 'Special Teams';
  stCol.appendChild(stH);
  for (const u of ST_UNITS) {
    stCol.appendChild(ovLineRow(u.short, u.slots, STS.slots));
  }
  wrap.appendChild(esCol);
  wrap.appendChild(stCol);
  host.appendChild(wrap);
  const foot = document.createElement('p');
  foot.className = 'le-note';
  foot.textContent = 'Read-only overview — pick a line or unit tab above to edit.';
  host.appendChild(foot);
}

/* ---------------- toolbar (contextual) ---------------- */
function renderToolbar() {
  const bar = $('le-toolbar');
  const ab = $('btn-autobest'), cl = $('btn-clear'), ca = $('btn-cancel'), sv = $('btn-save');
  if (T.tab === 'overview') {
    bar.style.display = 'none';
    note('Read-only overview — pick a line or unit tab above to edit.', '');
    return;
  }
  bar.style.display = '';
  if (isESTab()) {
    const def = LINE_TAB_DEF[T.tab];
    const scope = 'Line ' + def.n;
    ab.textContent = 'Auto Best';
    ab.title = 'Fill ' + scope + ' with the best available players';
    ab.onclick = () => autoBestLine(def);
    cl.textContent = 'Clear';
    cl.title = 'Empty ' + scope + ' slots';
    cl.onclick = () => {
      if (confirm('Clear ' + scope + '?')) { clearLine(def); }
    };
    ca.onclick = cancelEdits;
    sv.textContent = 'Save Lines';
    sv.title = 'Save all even-strength lines';
    sv.onclick = saveLines;
    sv.disabled = !S.dirty;
  } else {
    const ui = ST_TAB_UNIT[T.tab];
    const u = ST_UNITS[ui];
    ab.textContent = 'Auto Best';
    ab.title = 'Fill ' + u.short + ' with the best available skaters';
    ab.onclick = () => autoBestSTUnit(u);
    cl.textContent = 'Clear';
    cl.title = 'Empty ' + u.short;
    cl.onclick = () => {
      if (confirm('Clear ' + u.short + '?')) { clearSTUnit(u); }
    };
    ca.onclick = stCancelEdits;
    sv.textContent = 'Save';
    sv.title = 'Save all special-teams units';
    sv.onclick = stSave;
    sv.disabled = !STS.dirty;
  }
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
  const injNote = p.injured ? ' ⚠️ ' + p.name.split(' ').slice(-1)[0] + ' is INJURED.' : '';
  note(p.name + ' → ' + targetSlot + fitNote + injNote, (fit === 'fit-red' || p.injured) ? 'err' : '');
}
function clearLine(def) {
  for (const slot of def.fw.concat(def.df, def.gk)) S.slots[slot] = null;
  S.sel = null;
  markDirty();
  renderAll();
  note('Line ' + def.n + ' cleared.', '');
}
function clearSTUnit(u) {
  for (const slot of u.slots) STS.slots[slot] = null;
  STS.sel = null;
  stMarkDirty();
  renderAll();
  note(u.short + ' cleared — a cleared unit falls back to the sim defaults on save.', '');
}
function clearDropHints() {
  document.querySelectorAll('.le-slot.drop-ok,.le-slot.drop-bad').forEach((el) => {
    el.classList.remove('drop-ok', 'drop-bad');
  });
  document.querySelectorAll('.le-roster.drop-target').forEach((el) => el.classList.remove('drop-target'));
}

/* ---------------- ES toolbar actions ---------------- */
function markDirty() {
  S.dirty = true;
}
function snapshotIds() {
  const out = {};
  for (const slot of LINE_SLOTS) out[slot] = S.slots[slot] ? String(S.slots[slot].id) : '';
  return out;
}
/* Fill one line tab with the best undressed players by position. */
function autoBestLine(def) {
  const all = Object.values(S.byId);
  const used = new Set();
  for (const p of Object.values(S.slots)) if (p) used.add(String(p.id));
  // Free the tab's own slots first so its players are re-pickable.
  for (const slot of def.fw.concat(def.df, def.gk)) {
    const p = S.slots[slot];
    if (p) used.delete(String(p.id));
  }
  const sk = all.filter((p) => !playerIsGoalie(p)).sort((a, b) => (b.overall || 0) - (a.overall || 0));
  const gk = all.filter((p) => playerIsGoalie(p)).sort((a, b) => (b.overall || 0) - (a.overall || 0));
  const pickSkater = (want) => {
    let pick = sk.find((x) => !used.has(String(x.id)) && String(x.position || '').toUpperCase() === want)
             || sk.find((x) => !used.has(String(x.id)));
    if (pick) used.add(String(pick.id));
    return pick || null;
  };
  const pickGoalie = () => {
    const p = gk.find((x) => !used.has(String(x.id)));
    if (p) used.add(String(p.id));
    return p || null;
  };
  for (const slot of def.fw) S.slots[slot] = pickSkater(slotPos(slot));
  for (const slot of def.df) S.slots[slot] = pickSkater(slotPos(slot));
  for (const slot of def.gk) S.slots[slot] = pickGoalie();
  S.sel = null;
  markDirty();
  renderAll();
  note('Auto Best applied to Line ' + def.n + ' — review the fits, then Save Lines.', 'ok');
}
function cancelEdits() {
  for (const slot of LINE_SLOTS) {
    const id = S.initial[slot];
    S.slots[slot] = id ? (S.byId[id] || null) : null;
  }
  S.sel = null;
  S.dirty = false;
  renderAll();
  note('Changes reverted.', '');
}
async function saveLines() {
  // FULL payload always — the backend rebuilds the entire lineup and
  // fills missing slots with None, so a partial POST would wipe lines.
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
      renderAll();
      note('Could not save: ' + (data.error || 'unknown error'), 'err');
    }
  } catch (e) {
    renderAll();
    note('Request failed: ' + e, 'err');
  }
}

/* ---------------- ST toolbar actions ---------------- */
function stMarkDirty() {
  STS.dirty = true;
}
function stSnapshotIds() {
  const out = {};
  for (const slot of ST_LINE_SLOTS) out[slot] = STS.slots[slot] ? String(STS.slots[slot].id) : '';
  return out;
}
/* Fill one ST unit with the best skaters not already on another ST unit. */
function autoBestSTUnit(u) {
  const sk = Object.values(S.byId).filter((p) => !playerIsGoalie(p))
    .sort((a, b) => (b.overall || 0) - (a.overall || 0));
  const used = new Set();
  for (const [slot, p] of Object.entries(STS.slots)) {
    if (p && !u.slots.includes(slot)) used.add(String(p.id));
  }
  const fw = sk.filter((p) => posGroup(p) === 'F');
  const df = sk.filter((p) => posGroup(p) === 'D');
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
  const needF = u.slots.filter((s) => ['LW', 'C', 'RW'].includes(slotPos(s))).length;
  const needD = u.slots.length - needF;
  const players = take(fw, needF).concat(take(df, needD));
  u.slots.forEach((slot, i) => { STS.slots[slot] = players[i] || null; });
  STS.sel = null;
  stMarkDirty();
  renderAll();
  note('Auto Best applied to ' + u.short + ' — review the fits, then Save.', 'ok');
}
function stCancelEdits() {
  for (const slot of ST_LINE_SLOTS) {
    const id = STS.initial[slot];
    STS.slots[slot] = id ? (S.byId[id] || null) : null;
  }
  STS.sel = null;
  STS.dirty = false;
  renderAll();
  note('Changes reverted.', '');
}
async function stSave() {
  // Client-side completeness check (server re-validates anyway).
  for (const u of ST_UNITS) {
    const filled = u.slots.filter((s) => STS.slots[s]).length;
    if (filled > 0 && filled < u.slots.length) {
      note(u.short + ' is incomplete (' + filled + '/' + u.slots.length +
             ') — fill every spot or clear the unit.', 'err');
      return;
    }
  }
  // FULL ST payload always (same backend rebuild semantics as ES).
  const st = stSnapshotIds();
  $('btn-save').disabled = true;
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
      renderAll();
      note('Special teams saved — they take effect on the game thread.', 'ok');
    } else {
      renderAll();
      note('Could not save: ' + (data.error || 'unknown error'), 'err');
    }
  } catch (e) {
    renderAll();
    note('Request failed: ' + e, 'err');
  }
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
    note('Goalies cannot play special teams.', 'err');
    return;
  }
  const dup = stSlotOf(p.id);
  const srcSlot = (payload.src === 'st-slot') ? payload.slot : dup;
  if (dup && dup !== targetSlot && dup !== srcSlot) {
    note(p.name + ' is already on ' + stSlotTag(dup) + ' — one player, one special-teams job.', 'err');
    return;
  }
  if (srcSlot === targetSlot) return;
  const occupant = STS.slots[targetSlot];
  if (occupant && String(occupant.id) === String(p.id)) return;
  STS.slots[targetSlot] = p;
  if (srcSlot && srcSlot !== targetSlot) STS.slots[srcSlot] = occupant || null;
  stMarkDirty();
  renderAll();
  const fit = fitClass(p, targetSlot);
  const fitNote = fit === 'fit-red' ? ' — out of position!' : fit === 'fit-yellow' ? ' — playable out of position.' : '.';
  note(p.name + ' → ' + stSlotTag(targetSlot) + fitNote, fit === 'fit-red' ? 'err' : '');
}

/* ---------------- render + events ---------------- */
function renderAll() {
  renderRoster();
  renderToolbar();
  renderContent();
  const n = Object.values(S.slots).filter(Boolean).length;
  const dirtyTxt = (S.dirty || STS.dirty) ? ' · unsaved changes' : '';
  $('lines-sub').textContent = n + ' of ' + LINE_SLOTS.length + ' slots filled' + dirtyTxt;
}
function wireEvents() {
  document.querySelectorAll('#le-tabs .le-tab').forEach((b) => {
    b.addEventListener('click', () => switchTab(b.dataset.tab));
  });
  $('roster-search').addEventListener('input', (e) => { S.q = e.target.value; renderRoster(); });
  $('roster-sort').addEventListener('change', (e) => { S.sort = e.target.value; renderRoster(); });
  // Roster filter pills only — scoped to the pill container so the tab
  // buttons (own .le-tab class) can never be hijacked into the filter
  // logic (2026-10-06 bugfix).
  document.querySelectorAll('.le-filters .le-filter').forEach((b) => {
    b.addEventListener('click', () => {
      document.querySelectorAll('.le-filters .le-filter').forEach((x) => x.classList.remove('on'));
      b.classList.add('on');
      S.filter = b.dataset.f;
      renderRoster();
    });
  });
  // Roster panel is a drop target: dragging a dressed player here removes them.
  const panel = $('roster-panel');
  panel.addEventListener('dragover', (e) => {
    if (dragPayload && (dragPayload.src === 'slot' || dragPayload.src === 'st-slot')) {
      e.preventDefault();
      panel.classList.add('drop-target');
    }
  });
  panel.addEventListener('dragleave', () => panel.classList.remove('drop-target'));
  panel.addEventListener('drop', (e) => {
    e.preventDefault();
    panel.classList.remove('drop-target');
    if (dragPayload) {
      if (dragPayload.src === 'slot') {
        const p = S.slots[dragPayload.slot];
        S.slots[dragPayload.slot] = null;
        markDirty();
        if (p) note(p.name + ' removed from ' + dragPayload.slot + '.', '');
      } else if (dragPayload.src === 'st-slot') {
        const p = STS.slots[dragPayload.slot];
        STS.slots[dragPayload.slot] = null;
        stMarkDirty();
        if (p) note(p.name + ' removed from ' + stSlotTag(dragPayload.slot) + '.', '');
      }
      renderAll();
    }
    dragPayload = null;
    clearDropHints();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && (S.sel || STS.sel)) { S.sel = null; STS.sel = null; renderAll(); }
  });
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
