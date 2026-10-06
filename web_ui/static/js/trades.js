/* Puck Dynasty Trade Center — single-page trade builder.
 * Click team tiles to pick a partner, click player/pick cards to add or
 * remove them from the deal. Live AI verdict, salary retention (0/25/50%),
 * pick protection, and result polling all live here.
 *
 * APIs (unchanged):
 *   GET  /api/trades/teams
 *   GET  /api/trades/assets?team_id=X
 *   GET  /api/trades/evaluate?target_team_id=&give_pids=&give_picks=&want_pids=&want_picks=&retention=&protection=
 *   POST /api/trades/propose
 *   GET  /api/trades/result
 */
const state = {
  teams: [],
  userTeam: null,
  userAbbr: '',
  userPlayers: [],
  userPicks: [],
  partnerId: '',
  partnerName: '',
  partnerPlayers: [],
  partnerPicks: [],
  givePids: new Set(),
  givePicks: new Set(),
  wantPids: new Set(),
  wantPicks: new Set(),
  retention: {},      // pid -> pct (25/50) on players we trade away
  retentionAcquire: {}, // pid -> pct (25/50) we ask the partner to keep on players we acquire
  protection: {},     // pickId -> 'top-3'|'top-10'|'lottery' on picks we trade away
  slotsUsed: 0,
  slotsMax: 3,
  partnerSlotsUsed: 0,   // partner club's retention ledger (for acquire-side terms)
  partnerSlotsMax: 3,
  protectionOptions: [],
  verdict: null,
  evalTimer: null,
  resultTimer: null,
};

const RETENTION_PCTS = [0, 25, 50]; // engine max is 50%
const PROT_FALLBACK = [
  {code: 'top-3', label: 'Top-3 protected'},
  {code: 'top-10', label: 'Top-10 protected'},
  {code: 'lottery', label: 'Lottery protected'},
];
/* Familiarity bands mirror position_training._BASE_FAMILIARITY so the
   fit badge matches what the sim will actually do. */
const FIT_OK = new Set(['C', 'LW', 'RW', 'LD', 'RD', 'G']);

const el = id => document.getElementById(id);

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function fmtSalary(s) {
  s = s || 0;
  if (s >= 1e6) return '$' + (s / 1e6).toFixed(2) + 'M';
  if (s >= 1e3) return '$' + Math.round(s / 1e3) + 'K';
  return '$' + s;
}

/* OVR badge color bands (match the rest of the web UI). */
function ovrClass(ov) {
  ov = Number(ov) || 0;
  if (ov >= 82) return 'ovr-hi';
  if (ov >= 72) return 'ovr-mid';
  return 'ovr-lo';
}

/* ---------- teams ---------- */
async function loadTeams() {
  try {
    const res = await fetch('/api/trades/teams');
    const data = await res.json();
    state.teams = data.teams || [];
    state.userTeam = data.user_team || null;
    const mine = state.teams.find(t => t.is_user);
    state.userAbbr = mine ? (mine.abbr || mine.name) : '';
    el('my-team-name').textContent = state.userTeam
      ? state.userTeam + ' — your roster' : 'Your roster';
    if (data.trade_block_count > 0) {
      el('trades-status').textContent =
        'Trade Center · ' + data.trade_block_count + ' player(s) on the block';
    }
    renderTeams('');
    await loadMyAssets();
  } catch (e) { console.error(e); }
}

function renderTeams(filter) {
  const grid = el('team-tiles');
  grid.innerHTML = '';
  const q = (filter || '').trim().toLowerCase();
  let shown = 0;
  for (const t of state.teams) {
    if (t.is_user) continue;
    const label = ((t.city || '') + ' ' + (t.name || '')).toLowerCase();
    if (q && !label.includes(q) && !(t.abbr || '').toLowerCase().includes(q)) continue;
    shown++;
    const d = document.createElement('div');
    d.className = 'team-tile' + ((t.abbr || t.name) === state.partnerId ? ' selected' : '');
    d.innerHTML = `
      <div class="t-abbr">${esc(t.abbr || '')}</div>
      <div class="t-name">${esc(t.city || '')} ${esc(t.name || '')}</div>
      <div class="t-record">${t.wins != null ? t.wins + '-' + t.losses + '-' + t.otl : ''}</div>
      ${t.on_block ? '<div class="t-block">on block</div>' : ''}`;
    d.addEventListener('click', () => selectPartner(t.abbr || t.name,
      (t.city || '') + ' ' + (t.name || '')));
    grid.appendChild(d);
  }
  if (!shown) grid.innerHTML = '<div class="empty-note">No teams match.</div>';
}

/* ---------- assets ---------- */
async function fetchAssets(teamId) {
  const res = await fetch('/api/trades/assets?team_id=' + encodeURIComponent(teamId));
  if (!res.ok) throw new Error('assets fetch failed: ' + res.status);
  return res.json();
}

async function loadMyAssets() {
  if (!state.userAbbr) return;
  try {
    const a = await fetchAssets(state.userAbbr);
    state.userPlayers = a.players || [];
    state.userPicks = a.picks || [];
    state.slotsUsed = a.retention_slots_used || 0;
    state.slotsMax = a.retention_slots_max || 3;
    state.protectionOptions = (a.protection_options && a.protection_options.length)
      ? a.protection_options : PROT_FALLBACK;
    pruneTerms();
    renderGive();
    updateSlots();
  } catch (e) { console.error(e); }
}

async function selectPartner(id, name) {
  state.partnerId = id;
  state.partnerName = name;
  state.wantPids.clear();
  state.wantPicks.clear();
  renderTeams(el('team-search').value);
  el('partner-name').textContent = name;
  if (!id) {
    state.partnerPlayers = [];
    state.partnerPicks = [];
    state.partnerSlotsUsed = 0;
    state.retentionAcquire = {};
    renderGet();
    renderDeal();
    updateSlots();
    resetVerdict('Select a partner team and add players or picks on both sides.');
    return;
  }
  try {
    const a = await fetchAssets(id);
    state.partnerPlayers = a.players || [];
    state.partnerPicks = a.picks || [];
    state.partnerSlotsUsed = a.retention_slots_used || 0;
    state.partnerSlotsMax = a.retention_slots_max || 3;
    state.retentionAcquire = {};
    pruneTerms();
    renderGet();
    renderDeal();
    updateSlots();
    scheduleEvaluate();
  } catch (e) { console.error(e); }
}

/* Drop retention/protection terms for assets no longer in the deal. */
function pruneTerms() {
  for (const k of Object.keys(state.retention)) {
    if (!state.givePids.has(k)) delete state.retention[k];
  }
  for (const k of Object.keys(state.retentionAcquire)) {
    if (!state.wantPids.has(k)) delete state.retentionAcquire[k];
  }
  for (const k of Object.keys(state.protection)) {
    if (!state.givePicks.has(k)) delete state.protection[k];
  }
}

/* Retention slots left for NEW terms (ledger use + this deal's terms). */
function slotsRemaining() {
  const fresh = Object.values(state.retention).filter(v => v > 0).length;
  return state.slotsMax - state.slotsUsed - fresh;
}

/* Partner retention slots left for NEW acquire-side terms. */
function slotsRemainingAcquire() {
  const fresh = Object.values(state.retentionAcquire).filter(v => v > 0).length;
  return state.partnerSlotsMax - state.partnerSlotsUsed - fresh;
}

function updateSlots() {
  const pill = el('retention-slots');
  const fresh = Object.values(state.retention).filter(v => v > 0).length;
  const used = state.slotsUsed + fresh;
  pill.textContent = 'Retention: ' + used + '/' + state.slotsMax + ' slots';
  pill.classList.toggle('full', used >= state.slotsMax);
  const ppill = el('retention-slots-partner');
  if (ppill) {
    const afresh = Object.values(state.retentionAcquire).filter(v => v > 0).length;
    const aused = state.partnerSlotsUsed + afresh;
    ppill.hidden = !state.partnerId;
    ppill.textContent = (state.partnerName ? state.partnerName.split(' ').pop() : 'Partner') +
      ' retention: ' + aused + '/' + state.partnerSlotsMax + ' slots';
    ppill.classList.toggle('full', aused >= state.partnerSlotsMax);
  }
}

function flashNote(msg) {
  const note = el('trade-note');
  note.textContent = msg;
  note.className = 'prop-note err';
}

/* ---------- asset cards ---------- */
function fitBadge(asset) {
  // Position fit is informational here; the sim applies familiarity.
  // We only flag the egregious case: skater asked to play goalie or vice versa.
  const pos = String(asset.position || '').toUpperCase();
  const isG = pos === 'G' || pos === 'GOALIE';
  return isG ? 'G' : pos;
}

function assetCard(asset, kind, side, checked) {
  const id = String(asset.id);
  const wrap = document.createElement('div');
  wrap.className = 'asset-card' + (kind === 'pick' ? ' pick' : '')
    + (checked ? ' in-deal' : '') + (asset.injured ? ' injured' : '');
  const info = kind === 'pick'
    ? `<span class="ac-name">${esc(asset.label)}</span>
       <span class="ac-sub">${asset.year ? 'Round ' + asset.round + ' · ' + asset.year : ''}${asset.protection ? ' · ' + esc(asset.protection) : ''}</span>`
    : `<span class="ac-ovr ${ovrClass(asset.overall)}">${asset.overall}</span>
       <span class="ac-info">
         <span class="ac-name">${asset.id ? `<span class="clickable-text" data-href="/player/${esc(asset.id)}" title="Open player profile">${esc(asset.name)}</span>` : esc(asset.name)}${asset.captaincy ? ' <span class="p-c">' + esc(asset.captaincy) + '</span>' : ''}</span>
         <span class="ac-sub">${esc(asset.position)} · Age ${asset.age} · ${fmtSalary(asset.salary)}</span>
       </span>
       ${asset.injured ? '<span class="ac-inj">INJ</span>' : ''}
       ${asset.level ? '<span class="ac-level">' + esc(asset.level) + '</span>' : ''}`;
  wrap.innerHTML = info + (checked ? '<span class="ac-check">✓</span>' : '');
  wrap.addEventListener('click', () => toggleAsset(id, kind, side));
  // Player name navigates to profile without toggling the card.
  const nm = wrap.querySelector('.clickable-text[data-href]');
  if (nm) nm.addEventListener('click', (e) => {
    e.stopPropagation();
    window.location.href = nm.dataset.href;
  });
  // Terms row: retention / protection under give-side assets in the
  // deal; retention requests under get-side players (ask the partner
  // club to retain salary on players we acquire).
  if (checked && (side === 'give' || (side === 'get' && kind === 'player'))) {
    const t = termsRow(asset, kind, side);
    if (t) wrap.appendChild(t);
  }
  return wrap;
}

/* Terms selector under an asset in the deal.
 * side 'give': retention OUR club keeps on outgoing players/picks protection.
 * side 'get':  retention we ask the PARTNER to keep on incoming players. */
function termsRow(asset, kind, side) {
  const id = String(asset.id);
  const div = document.createElement('div');
  div.className = 'terms-row';
  // stopPropagation so changing terms doesn't toggle the card
  div.addEventListener('click', e => e.stopPropagation());
  if (kind === 'player') {
    const acquire = side === 'get';
    const store = acquire ? state.retentionAcquire : state.retention;
    const cur = store[id] || 0;
    const remaining = acquire ? slotsRemainingAcquire() : slotsRemaining();
    const maxSlots = acquire ? state.partnerSlotsMax : state.slotsMax;
    const noSlots = remaining <= 0 && cur === 0;
    const capHit = asset.cap_hit || asset.salary || 0;
    const sel = document.createElement('select');
    sel.className = 'terms-select';
    sel.title = acquire
      ? (noSlots
        ? 'Partner has no retention slots left (max ' + maxSlots + ' per club)'
        : 'Salary you ask ' + (state.partnerName || 'the partner') + ' to keep on this player (NHL max 50%)')
      : (noSlots
        ? 'No retention slots left (max ' + maxSlots + ' per club)'
        : 'Salary your club keeps on this player (NHL max 50%)');
    for (const pct of RETENTION_PCTS) {
      const o = document.createElement('option');
      o.value = String(pct);
      o.textContent = (acquire ? 'Ask ' : 'Retain ') + pct + '%';
      if (pct === cur) o.selected = true;
      if (pct > 0 && noSlots) o.disabled = true;
      sel.appendChild(o);
    }
    sel.addEventListener('change', ev => {
      const pct = parseInt(ev.target.value, 10) || 0;
      const prev = store[id] || 0;
      if (pct === 0) delete store[id];
      else store[id] = pct;
      const left = acquire ? slotsRemainingAcquire() : slotsRemaining();
      if (left < 0) {
        if (prev === 0) delete store[id];
        else store[id] = prev;
        ev.target.value = String(prev);
        flashNote('Retention slot limit reached (' + maxSlots +
          ' per club) — remove a term to add another.');
        return;
      }
      updateSlots();
      if (acquire) renderGet(); else renderGive(); // refresh disabled states + previews
      scheduleEvaluate();
    });
    const amt = document.createElement('span');
    amt.className = 'terms-amt';
    amt.textContent = cur > 0
      ? (acquire ? 'they keep ' : 'you keep ') + fmtSalary(Math.round(capHit * cur / 100)) : '';
    div.append(sel, amt);
  } else {
    const cur = state.protection[id] || '';
    const sel = document.createElement('select');
    sel.className = 'terms-select';
    sel.title = 'Protection on this pick (NHL: top-3 / top-10 / lottery)';
    const none = document.createElement('option');
    none.value = '';
    none.textContent = 'No protection';
    if (!cur) none.selected = true;
    sel.appendChild(none);
    for (const opt of state.protectionOptions) {
      const o = document.createElement('option');
      o.value = opt.code;
      o.textContent = opt.label;
      if (opt.code === cur) o.selected = true;
      sel.appendChild(o);
    }
    sel.addEventListener('change', ev => {
      const code = ev.target.value || '';
      if (!code) delete state.protection[id];
      else state.protection[id] = code;
      scheduleEvaluate();
    });
    div.append(sel);
  }
  return div;
}

function renderList(listEl, items, kind, side, selSet) {
  listEl.innerHTML = '';
  const sorted = [...items].sort((a, b) =>
    kind === 'pick' ? (a.year - b.year) || (a.round - b.round)
                    : (b.overall - a.overall));
  if (!sorted.length) {
    listEl.innerHTML = '<div class="empty-note">None</div>';
    return;
  }
  for (const a of sorted) {
    listEl.appendChild(assetCard(a, kind, side, selSet.has(String(a.id))));
  }
}

function renderGive() {
  renderList(el('give-players'), state.userPlayers, 'player', 'give', state.givePids);
  renderList(el('give-picks'), state.userPicks, 'pick', 'give', state.givePicks);
}

function renderGet() {
  renderList(el('get-players'), state.partnerPlayers, 'player', 'get', state.wantPids);
  renderList(el('get-picks'), state.partnerPicks, 'pick', 'get', state.wantPicks);
}

function toggleAsset(id, kind, side) {
  const set = {
    'give:player': state.givePids, 'give:pick': state.givePicks,
    'get:player': state.wantPids, 'get:pick': state.wantPicks,
  }[side + ':' + kind];
  if (!set) return;
  set.has(id) ? set.delete(id) : set.add(id);
  pruneTerms();
  if (side === 'give') renderGive();
  else renderGet();
  updateSlots();
  renderDeal();
  scheduleEvaluate();
}

/* Deal summary: only the pieces actually being offered, at a glance. */
function dealChip(asset, kind, side) {
  const id = String(asset.id);
  const chip = document.createElement('div');
  chip.className = 'deal-chip' + (kind === 'pick' ? ' pick' : '');
  chip.title = 'Click to remove from the deal';
  if (kind === 'pick') {
    chip.innerHTML = `<span class="dc-name">${esc(asset.label)}</span>
      <span class="dc-sub">${asset.year ? asset.year + ' R' + asset.round : ''}</span>
      <span class="dc-x">✕</span>`;
  } else {
    const ret = side === 'give' && state.retention[id]
      ? ' <span class="dc-ret">(' + state.retention[id] + '% ret.)</span>'
      : (side === 'get' && state.retentionAcquire[id]
        ? ' <span class="dc-ret">(' + state.retentionAcquire[id] + '% ret. by them)</span>' : '');
    chip.innerHTML = `<span class="dc-ovr ${ovrClass(asset.overall)}">${asset.overall}</span>
      <span class="dc-info"><span class="dc-name">${esc(asset.name)}</span>
      <span class="dc-sub">${esc(asset.position)} · ${fmtSalary(asset.salary)}${ret}</span></span>
      <span class="dc-x">✕</span>`;
  }
  chip.addEventListener('click', () => toggleAsset(id, kind, side));
  return chip;
}

function renderDeal() {
  const sec = el('deal-summary');
  const getBox = el('deal-get');
  const giveBox = el('deal-give');
  getBox.innerHTML = '';
  giveBox.innerHTML = '';
  let count = 0;
  const byId = id => state.partnerPlayers.concat(state.partnerPicks)
    .find(a => String(a.id) === String(id));
  const myById = id => state.userPlayers.concat(state.userPicks)
    .find(a => String(a.id) === String(id));
  for (const pid of state.wantPids) {
    const a = byId(pid);
    if (a) { getBox.appendChild(dealChip(a, 'player', 'get')); count++; }
  }
  for (const pid of state.wantPicks) {
    const a = byId(pid);
    if (a) { getBox.appendChild(dealChip(a, 'pick', 'get')); count++; }
  }
  for (const pid of state.givePids) {
    const a = myById(pid);
    if (a) { giveBox.appendChild(dealChip(a, 'player', 'give')); count++; }
  }
  for (const pid of state.givePicks) {
    const a = myById(pid);
    if (a) { giveBox.appendChild(dealChip(a, 'pick', 'give')); count++; }
  }
  if (!count) {
    getBox.innerHTML = '<div class="empty-note">Nothing selected</div>';
    giveBox.innerHTML = '<div class="empty-note">Nothing selected</div>';
  }
  sec.hidden = count === 0;
}

/* ---------- live AI verdict ---------- */
function scheduleEvaluate() {
  if (state.evalTimer) clearTimeout(state.evalTimer);
  state.evalTimer = setTimeout(evaluate, 450);
}

function resetVerdict(msg) {
  state.verdict = null;
  const badge = el('verdict-badge');
  badge.className = 'verdict-badge';
  badge.textContent = '—';
  el('verdict-reason').textContent = msg || 'Select a partner team and add players or picks on both sides.';
  el('verdict-bars').innerHTML = '';
  el('give-val').textContent = '';
  el('get-val').textContent = '';
  const terms = el('verdict-terms');
  terms.innerHTML = '';
  terms.hidden = true;
  el('btn-propose').disabled = true;
}

async function evaluate() {
  if (!state.partnerId) { resetVerdict(); return; }
  const q = new URLSearchParams({
    target_team_id: state.partnerId,
    give_pids: [...state.givePids].join(','),
    give_picks: [...state.givePicks].join(','),
    want_pids: [...state.wantPids].join(','),
    want_picks: [...state.wantPicks].join(','),
    retention: Object.entries(state.retention)
      .filter(([, v]) => v > 0).map(([k, v]) => k + ':' + v).join(','),
    retention_acquire: Object.entries(state.retentionAcquire)
      .filter(([, v]) => v > 0).map(([k, v]) => k + ':' + v).join(','),
    protection: Object.entries(state.protection)
      .map(([k, v]) => k + ':' + v).join(','),
  });
  el('verdict-badge').textContent = '…';
  try {
    const res = await fetch('/api/trades/evaluate?' + q.toString());
    const data = await res.json();
    state.verdict = data;
    renderVerdict(data);
  } catch (e) {
    console.error(e);
    resetVerdict('Could not reach the trade evaluator: ' + e.message);
  }
}

function renderVerdict(d) {
  const badge = el('verdict-badge');
  const v = String(d.verdict || 'reject').toLowerCase();
  badge.className = 'verdict-badge ' + (v === 'accept' ? 'accept' : v === 'counter' ? 'counter' : 'reject');
  badge.textContent = v === 'accept' ? 'Likely: accepts' : v === 'counter' ? 'Likely: counters' : 'Likely: rejects';
  el('verdict-reason').textContent = d.reason || '';

  const gv = d.give_value || 0, pv = d.get_value || 0;
  el('give-val').textContent = gv ? '(' + gv + ' pts)' : '';
  el('get-val').textContent = pv ? '(' + pv + ' pts)' : '';
  const max = Math.max(gv, pv, 1);
  el('verdict-bars').innerHTML = `
    <div class="vbar-row"><span class="vbar-label">You give</span>
      <div class="vbar-track"><div class="vbar-fill give" style="width:${(100 * gv / max).toFixed(1)}%"></div></div>
      <span class="vbar-pts">${gv} pts</span></div>
    <div class="vbar-row"><span class="vbar-label">You get</span>
      <div class="vbar-track"><div class="vbar-fill get" style="width:${(100 * pv / max).toFixed(1)}%"></div></div>
      <span class="vbar-pts">${pv} pts</span></div>
    ${d.label ? `<div class="vbar-row"><span class="vbar-label">Valuation</span><span>${esc(d.label)}</span></div>` : ''}`;

  // Propose when the deal is non-empty and retention terms pass.
  // The verdict below is the AI's LIKELY reaction (advisory): the real
  // answer arrives 1-3 sim days later via the inbox (accept / counter /
  // reject), exactly like the desktop Trade Center.
  const retBad = (d.retention_errors && d.retention_errors.length) ||
    d.retention_valid === false ||
    (d.retention_acquire_errors && d.retention_acquire_errors.length) ||
    d.retention_acquire_valid === false;
  const hasAssets = state.givePids.size + state.givePicks.size +
    state.wantPids.size + state.wantPicks.size > 0;
  // Batch A: the freeze keeps the propose button off no matter what.
  el('btn-propose').disabled = !hasAssets || !!retBad || !!state.frozen;
  el('trade-note').textContent = '';
  el('trade-note').className = 'prop-note';

  const termsEl = el('verdict-terms');
  const bits = [];
  if (d.terms_note) bits.push(d.terms_note);
  if (d.protection_adjustment > 0) {
    bits.push('Pick protection discounts your offer by ≈' +
      d.protection_adjustment + ' pts to the receiving GM (estimate).');
  }
  if (d.retention_errors && d.retention_errors.length) {
    bits.push('⚠ Retention problem: ' + d.retention_errors.join(' '));
  }
  if (d.retention_acquire_errors && d.retention_acquire_errors.length) {
    bits.push('⚠ Partner retention problem: ' + d.retention_acquire_errors.join(' '));
  }
  termsEl.innerHTML = bits.map(b => '<div>' + esc(b) + '</div>').join('');
  termsEl.hidden = !bits.length;
}

/* ---------- propose ---------- */
async function propose() {
  const btn = el('btn-propose');
  if (btn.disabled) return;
  btn.disabled = true;
  btn.textContent = 'Proposing…';
  const note = el('trade-note');
  try {
    const res = await fetch('/api/trades/propose', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        target_team_id: state.partnerId,
        give_pids: [...state.givePids],
        give_picks: [...state.givePicks],
        want_pids: [...state.wantPids],
        want_picks: [...state.wantPicks],
        retention: state.retention,
        retention_acquire: state.retentionAcquire,
        pick_protection: state.protection,
      }),
    });
    const data = await res.json();
    if (data.ok) {
      note.textContent = 'Offer sent — the other GM answers in 1-3 days via your inbox. Watching for the result…';
      note.className = 'prop-note';
      pollResult();
    } else {
      note.textContent = 'Failed: ' + (data.error || 'could not queue trade');
      note.className = 'prop-note err';
      btn.disabled = false;
      btn.textContent = 'Propose trade';
    }
  } catch (e) {
    note.textContent = 'Failed: ' + e.message;
    note.className = 'prop-note err';
    btn.disabled = false;
    btn.textContent = 'Propose trade';
  }
}

/* The command executes on the Tk main thread; poll for its outcome. */
async function pollResult() {
  const note = el('trade-note');
  const btn = el('btn-propose');
  let tries = 0;
  if (state.resultTimer) clearInterval(state.resultTimer);
  state.resultTimer = setInterval(async () => {
    tries++;
    try {
      const res = await fetch('/api/trades/result');
      const data = await res.json();
      const r = data.result;
      if (r && (r.marker === 'execute_trade' || r.marker === 'trade_counter_negotiation')) {
        clearInterval(state.resultTimer);
        state.resultTimer = null;
        if (r.ok) {
          if (r.pending) {
            // Async negotiation: the offer/counter sits with the other GM.
            note.textContent = (r.marker === 'trade_counter_negotiation' ? 'Counter sent: ' : 'Offer sent: ') +
              (r.summary || 'awaiting the GM\u2019s answer.') + ' Track it below in Open negotiations.';
            note.className = 'prop-note ok';
          } else {
            note.textContent = 'Done: ' + (r.summary || 'resolved — check your inbox.');
            note.className = 'prop-note ok';
          }
          state.givePids.clear(); state.givePicks.clear();
          state.wantPids.clear(); state.wantPicks.clear();
          state.retention = {};
          state.retentionAcquire = {};
          state.protection = {};
          await loadMyAssets();
          selectPartner(state.partnerId, state.partnerName);
          loadNegotiations();
        } else {
          note.textContent = 'Trade blocked: ' + (r.summary || 'the proposal could not be sent.');
          note.className = 'prop-note err';
          btn.disabled = false;
          btn.textContent = 'Propose trade';
          scheduleEvaluate();
        }
      } else if (tries > 60) {
        clearInterval(state.resultTimer);
        state.resultTimer = null;
        note.textContent = 'No result yet — check the game / inbox.';
        btn.disabled = false;
        btn.textContent = 'Propose trade';
      }
    } catch (e) { /* keep polling */ }
  }, 1000);
}

/* ---------- open negotiations (async trade talks) ---------- */
function statusLabel(n) {
  if (n.status === 'awaiting_ai') return 'With ' + n.partner + '’s GM — answer due ' + (n.response_due || 'soon');
  if (n.status === 'awaiting_user') return 'Their move — check your inbox to answer';
  return n.status;
}
async function loadNegotiations() {
  const host = el('neg-list');
  const sec = el('neg-section');
  try {
    const res = await fetch('/api/trades/negotiations');
    const data = await res.json();
    const negs = data.negotiations || [];
    sec.hidden = negs.length === 0;
    host.innerHTML = '';
    for (const n of negs) {
      const card = document.createElement('div');
      card.className = 'neg-card';
      const hist = (n.history || []).map(h =>
        '<div class="neg-hist-row"><span class="neg-hist-date">' + esc(h.date) + '</span>' +
        '<span class="neg-hist-by by-' + esc(h.by) + '">' + esc(h.by === 'user' ? 'You' : h.by === 'ai' ? n.partner + ' GM' : 'League') + '</span>' +
        '<span class="neg-hist-sum">' + esc(h.summary) + '</span></div>').join('');
      card.innerHTML =
        '<div class="neg-head"><span class="neg-partner">' + esc(n.partner) + '</span>' +
        '<span class="neg-status st-' + esc(n.status) + '">' + esc(statusLabel(n)) + '</span></div>' +
        '<div class="neg-terms"><div><span class="neg-k">You send:</span> ' + esc(n.you_send) + '</div>' +
        '<div><span class="neg-k">You get:</span> ' + esc(n.you_get) + '</div></div>' +
        (n.last_message ? '<div class="neg-last">' + esc(n.last_message) + '</div>' : '') +
        '<div class="neg-hist">' + hist + '</div>' +
        '<div class="neg-actions">' +
        '<a class="btn-ghost" href="/inbox">Open inbox to answer</a>' +
        (n.status === 'awaiting_user'
          ? '<button class="btn-ghost" data-counter="' + esc(n.id) + '">Counter with current builder terms</button>'
          : '') +
        '</div>';
      host.appendChild(card);
    }
    host.querySelectorAll('button[data-counter]').forEach(b =>
      b.addEventListener('click', () => counterNegotiation(b.dataset.counter)));
  } catch (e) { /* negotiations panel is non-critical */ }
}
/* Answer an AI counter with the current builder terms (desktop parity:
 * trade_negotiation.send_counter — the thread stays open, patience decays,
 * the AI answers again in 1-3 days via the inbox). */
async function counterNegotiation(negId) {
  const note = el('trade-note');
  const hasAssets = state.givePids.size + state.givePicks.size +
    state.wantPids.size + state.wantPicks.size > 0;
  if (!hasAssets) {
    note.textContent = 'Build your counter in the deal columns above first, then press this button again.';
    note.className = 'prop-note err';
    return;
  }
  note.textContent = 'Sending counter…';
  note.className = 'prop-note';
  try {
    const res = await fetch('/api/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        op: 'trade_counter_negotiation',
        negotiation_id: negId,
        give_pids: [...state.givePids],
        give_picks: [...state.givePicks],
        want_pids: [...state.wantPids],
        want_picks: [...state.wantPicks],
        retention: state.retention,
        retention_acquire: state.retentionAcquire,
        pick_protection: state.protection,
      }),
    });
    const data = await res.json();
    if (data.ok) { pollResult(); }
    else {
      note.textContent = 'Counter failed: ' + (data.error || 'could not send');
      note.className = 'prop-note err';
    }
  } catch (e) {
    note.textContent = 'Counter failed: ' + e.message;
    note.className = 'prop-note err';
  }
}

/* ---------- init ---------- */
el('team-search').addEventListener('input', e => renderTeams(e.target.value));
el('btn-propose').addEventListener('click', propose);

/* Batch A: trade-freeze banner. When frozen, proposals are blocked
   server-side (transaction_windows.check_window("trade")); the banner
   explains why and the propose button stays disabled. */
async function checkTradeWindow() {
  try {
    const res = await fetch('/api/trades/window');
    const w = await res.json();
    state.frozen = !!w.frozen;
    let banner = el('trade-freeze-banner');
    if (w.frozen) {
      if (!banner) {
        banner = document.createElement('div');
        banner.id = 'trade-freeze-banner';
        banner.className = 'freeze-banner';
        const main = document.querySelector('.trades-main');
        main.insertBefore(banner, main.firstChild);
      }
      banner.innerHTML = `<span class="freeze-ico">⛔</span><span>${esc(w.reason || 'Trades are frozen.')}</span>`;
      banner.hidden = false;
      const btn = el('btn-propose');
      if (btn) { btn.disabled = true; btn.title = w.reason || 'Trades are frozen'; }
    } else if (banner) {
      banner.hidden = true;
    }
  } catch (e) { /* banner is best-effort; the server still enforces */ }
}

loadTeams().then(preselectFromURL);
checkTradeWindow();
loadNegotiations();
setInterval(loadNegotiations, 30000); // keep the thread view fresh

/* Pre-selection from context menus: /trades?team=<name>&player=<id> */
async function preselectFromURL() {
  try {
    const params = new URLSearchParams(window.location.search);
    const teamName = params.get('team');
    const playerId = params.get('player');
    if (!teamName && !playerId) return;
    /* Resolve team: explicit ?team= wins; otherwise look up the player's team. */
    let targetName = teamName;
    if (!targetName && playerId) {
      try {
        const pr = await fetch('/api/player/' + encodeURIComponent(playerId));
        if (pr.ok) {
          const pd = await pr.json();
          targetName = (pd.header && pd.header.team_name) || null;
        }
      } catch (e) { /* ignore */ }
    }
    if (!targetName || !state.teams) return;
    const team = state.teams.find(t =>
      (t.name || '').toLowerCase() === targetName.toLowerCase());
    if (!team) return;
    await selectPartner(team.id, team.name);
    if (playerId && state.partnerPlayers) {
      const found = state.partnerPlayers.some(p => String(p.id) === String(playerId));
      if (found) {
        state.wantPids.add(String(playerId));
        renderGet(); renderDeal(); scheduleEvaluate();
      }
    }
  } catch (e) { console.error(e); }
}

// Shared heartbeat: tells the game the tab is still open (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (not from action controls;
// asset-card names handle their own navigation with stopPropagation above).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, .asset-card')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
