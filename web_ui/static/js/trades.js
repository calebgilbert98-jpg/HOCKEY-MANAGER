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
  protection: {},     // pickId -> 'top-3'|'top-10'|'lottery' on picks we trade away
  slotsUsed: 0,
  slotsMax: 3,
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
    renderGet();
    renderDeal();
    resetVerdict('Select a partner team and add players or picks on both sides.');
    return;
  }
  try {
    const a = await fetchAssets(id);
    state.partnerPlayers = a.players || [];
    state.partnerPicks = a.picks || [];
    renderGet();
    renderDeal();
    scheduleEvaluate();
  } catch (e) { console.error(e); }
}

/* Drop retention/protection terms for assets no longer in the deal. */
function pruneTerms() {
  for (const k of Object.keys(state.retention)) {
    if (!state.givePids.has(k)) delete state.retention[k];
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

function updateSlots() {
  const pill = el('retention-slots');
  const fresh = Object.values(state.retention).filter(v => v > 0).length;
  const used = state.slotsUsed + fresh;
  pill.textContent = 'Retention: ' + used + '/' + state.slotsMax + ' slots';
  pill.classList.toggle('full', used >= state.slotsMax);
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
         <span class="ac-name">${esc(asset.name)}${asset.captaincy ? ' <span class="p-c">' + esc(asset.captaincy) + '</span>' : ''}</span>
         <span class="ac-sub">${esc(asset.position)} · Age ${asset.age} · ${fmtSalary(asset.salary)}</span>
       </span>
       ${asset.injured ? '<span class="ac-inj">INJ</span>' : ''}
       ${asset.level ? '<span class="ac-level">' + esc(asset.level) + '</span>' : ''}`;
  wrap.innerHTML = info + (checked ? '<span class="ac-check">✓</span>' : '');
  wrap.addEventListener('click', () => toggleAsset(id, kind, side));
  // Terms row (retention / protection) under give-side assets in the deal.
  if (side === 'give' && checked) {
    const t = termsRow(asset, kind);
    if (t) wrap.appendChild(t);
  }
  return wrap;
}

/* Terms selector under a give-side asset in the deal. */
function termsRow(asset, kind) {
  const id = String(asset.id);
  const div = document.createElement('div');
  div.className = 'terms-row';
  // stopPropagation so changing terms doesn't toggle the card
  div.addEventListener('click', e => e.stopPropagation());
  if (kind === 'player') {
    const cur = state.retention[id] || 0;
    const noSlots = slotsRemaining() <= 0 && cur === 0;
    const capHit = asset.cap_hit || asset.salary || 0;
    const sel = document.createElement('select');
    sel.className = 'terms-select';
    sel.title = noSlots
      ? 'No retention slots left (max ' + state.slotsMax + ' per club)'
      : 'Salary your club keeps on this player (NHL max 50%)';
    for (const pct of RETENTION_PCTS) {
      const o = document.createElement('option');
      o.value = String(pct);
      o.textContent = 'Retain ' + pct + '%';
      if (pct === cur) o.selected = true;
      if (pct > 0 && noSlots) o.disabled = true;
      sel.appendChild(o);
    }
    sel.addEventListener('change', ev => {
      const pct = parseInt(ev.target.value, 10) || 0;
      const prev = state.retention[id] || 0;
      if (pct === 0) delete state.retention[id];
      else state.retention[id] = pct;
      if (slotsRemaining() < 0) {
        if (prev === 0) delete state.retention[id];
        else state.retention[id] = prev;
        ev.target.value = String(prev);
        flashNote('Retention slot limit reached (' + state.slotsMax +
          ' per club) — remove a term to add another.');
        return;
      }
      updateSlots();
      renderGive(); // refresh disabled states + previews
      scheduleEvaluate();
    });
    const amt = document.createElement('span');
    amt.className = 'terms-amt';
    amt.textContent = cur > 0 ? 'you keep ' + fmtSalary(Math.round(capHit * cur / 100)) : '';
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
  if (side === 'give') { renderGive(); updateSlots(); }
  else renderGet();
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
      ? ' <span class="dc-ret">(' + state.retention[id] + '% ret.)</span>' : '';
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
  badge.textContent = v === 'accept' ? 'GM accepts' : v === 'counter' ? 'GM counters' : 'GM rejects';
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

  // Propose only when the REAL AI verdict says accept and retention passed.
  const retBad = (d.retention_errors && d.retention_errors.length) ||
    d.retention_valid === false;
  el('btn-propose').disabled = v !== 'accept' || !!retBad;
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
  termsEl.innerHTML = bits.map(b => '<div>' + esc(b) + '</div>').join('');
  termsEl.hidden = !bits.length;
}

/* ---------- propose ---------- */
async function propose() {
  const v = state.verdict;
  if (!v || String(v.verdict).toLowerCase() !== 'accept') return;
  const btn = el('btn-propose');
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
        pick_protection: state.protection,
      }),
    });
    const data = await res.json();
    if (data.ok) {
      note.textContent = 'Trade queued — executing on the game thread. Watching for the result…';
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
      if (r && r.marker === 'execute_trade') {
        clearInterval(state.resultTimer);
        state.resultTimer = null;
        if (r.ok) {
          note.textContent = 'Trade completed: ' + (r.summary || 'done.');
          note.className = 'prop-note ok';
          state.givePids.clear(); state.givePicks.clear();
          state.wantPids.clear(); state.wantPicks.clear();
          state.retention = {};
          state.protection = {};
          await loadMyAssets();
          selectPartner(state.partnerId, state.partnerName);
        } else {
          note.textContent = 'Trade blocked: ' + (r.summary || 'the GM rejected it at execution.');
          note.className = 'prop-note err';
          btn.disabled = false;
          btn.textContent = 'Propose trade';
          scheduleEvaluate();
        }
      } else if (tries > 60) {
        clearInterval(state.resultTimer);
        state.resultTimer = null;
        note.textContent = 'No execution result yet — check the game / inbox.';
        btn.disabled = false;
        btn.textContent = 'Propose trade';
      }
    } catch (e) { /* keep polling */ }
  }, 1000);
}

/* ---------- init ---------- */
el('team-search').addEventListener('input', e => renderTeams(e.target.value));
el('btn-propose').addEventListener('click', propose);

loadTeams();

// Shared heartbeat: tells the game the tab is still open (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
