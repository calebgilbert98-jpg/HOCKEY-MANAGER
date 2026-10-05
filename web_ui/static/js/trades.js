/* Puck Dynasty web trade center — proposal builder */
const state = {
  teams: [],
  userTeam: null,
  partner: null,          // selected partner team name
  partnerRoster: [],      // roster of selected partner
  myRoster: [],           // user's roster
  getIds: new Set(),      // players we want from partner
  giveIds: new Set(),      // our players offered
};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function fmtSalary(s) {
  if (s >= 1e6) return '$' + (s / 1e6).toFixed(2) + 'M';
  if (s >= 1e3) return '$' + Math.round(s / 1e3) + 'K';
  return '$' + (s || 0);
}

/* ---- teams ---- */
async function loadTeams() {
  try {
    const res = await fetch('/api/trades/teams');
    const data = await res.json();
    state.teams = data.teams || [];
    state.userTeam = data.user_team || null;
    renderTeams();
    if (data.trade_block_count > 0) {
      document.getElementById('trades-status').textContent =
        'Trade Center · ' + data.trade_block_count + ' player(s) on the block';
    }
  } catch (e) { console.error(e); }
}

function renderTeams() {
  const grid = document.getElementById('team-tiles');
  grid.innerHTML = '';
  for (const t of state.teams) {
    const el = document.createElement('div');
    el.className = 'team-tile' + (t.is_user ? ' user' : '')
      + (t.name === state.partner ? ' selected' : '');
    el.innerHTML = `
      <div class="t-abbr">${esc(t.abbr)}</div>
      <div class="t-name">${esc(t.city)} ${esc(t.name)}</div>
      <div class="t-record">${t.wins}-${t.losses}-${t.otl}</div>
      ${t.on_block ? '<div class="t-block">on block</div>' : ''}
      ${t.is_user ? '<div class="t-you">YOU</div>' : ''}`;
    if (!t.is_user) {
      el.addEventListener('click', () => selectTeam(t.name));
    }
    grid.appendChild(el);
  }
}

/* ---- rosters ---- */
async function selectTeam(name) {
  state.partner = name;
  state.getIds.clear();
  renderTeams();
  try {
    const res = await fetch('/api/trades/roster?team=' + encodeURIComponent(name));
    const data = await res.json();
    state.partnerRoster = data.players || [];
    state.myRoster = data.my_roster || [];
    document.getElementById('partner-label').textContent =
      name + ' — roster (' + state.partnerRoster.length + ')';
    renderPartner();
    renderMine();
    renderProposal();
  } catch (e) { console.error(e); }
}

function playerRow(p, side, checked) {
  const el = document.createElement('label');
  el.className = 'player-row' + (p.injured ? ' injured' : '')
    + (checked ? ' checked' : '');
  el.innerHTML = `
    <input type="checkbox" data-id="${esc(p.id)}" data-side="${side}"${checked ? ' checked' : ''}>
    <span class="pr-ov">${p.overall}</span>
    <span class="pr-info">
      <span class="pr-name">${esc(p.name)}${p.captaincy ? ' <span class="p-c">' + esc(p.captaincy) + '</span>' : ''}</span>
      <span class="pr-sub">${esc(p.position)} · Age ${p.age} · ${fmtSalary(p.salary)}</span>
    </span>
    ${p.injured ? '<span class="pr-inj">INJ</span>' : ''}`;
  el.querySelector('input').addEventListener('change', onToggle);
  return el;
}

function renderPartner() {
  const list = document.getElementById('partner-list');
  list.innerHTML = '';
  const sorted = [...state.partnerRoster].sort((a, b) => b.overall - a.overall);
  if (!sorted.length) {
    list.innerHTML = '<div class="empty-note">No players found</div>';
    return;
  }
  for (const p of sorted) {
    list.appendChild(playerRow(p, 'get', state.getIds.has(String(p.id))));
  }
}

function renderMine() {
  const list = document.getElementById('my-list');
  list.innerHTML = '';
  const sorted = [...state.myRoster].sort((a, b) => b.overall - a.overall);
  for (const p of sorted) {
    list.appendChild(playerRow(p, 'give', state.giveIds.has(String(p.id))));
  }
}

function onToggle(ev) {
  const id = String(ev.target.dataset.id);
  if (ev.target.dataset.side === 'get') {
    ev.target.checked ? state.getIds.add(id) : state.getIds.delete(id);
  } else {
    ev.target.checked ? state.giveIds.add(id) : state.giveIds.delete(id);
  }
  ev.target.closest('.player-row').classList.toggle('checked', ev.target.checked);
  renderProposal();
}

/* ---- proposal ---- */
function findPlayers(roster, ids) {
  const byId = new Map(roster.map(p => [String(p.id), p]));
  return [...ids].map(id => byId.get(id)).filter(Boolean);
}

function renderProposal() {
  const getting = findPlayers(state.partnerRoster, state.getIds);
  const giving = findPlayers(state.myRoster, state.giveIds);
  const chip = p =>
    `<div class="prop-chip"><span class="pr-ov sm">${p.overall}</span> ${esc(p.name)} <span class="dim">· ${esc(p.position)} · ${fmtSalary(p.salary)}</span></div>`;

  document.getElementById('prop-get').innerHTML =
    getting.length ? getting.map(chip).join('') : '<div class="empty-note">none</div>';
  document.getElementById('prop-give').innerHTML =
    giving.length ? giving.map(chip).join('') : '<div class="empty-note">none</div>';

  const getSal = getting.reduce((a, p) => a + (p.salary || 0), 0);
  const giveSal = giving.reduce((a, p) => a + (p.salary || 0), 0);
  document.getElementById('prop-totals').innerHTML =
    `<span>You get: <b>${fmtSalary(getSal)}</b></span><span>You give: <b>${fmtSalary(giveSal)}</b></span>`;

  const ok = state.partner && (getting.length || giving.length);
  const btn = document.getElementById('btn-propose');
  btn.disabled = !ok;
  document.getElementById('prop-note').textContent = '';
}

/* ---- propose ---- */
async function proposeTrade() {
  const btn = document.getElementById('btn-propose');
  btn.disabled = true;
  btn.textContent = 'Proposing…';
  try {
    const res = await fetch('/api/trades/propose', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        team: state.partner,
        give_ids: [...state.giveIds],
        get_ids: [...state.getIds],
      }),
    });
    const data = await res.json();
    const note = document.getElementById('prop-note');
    if (data.ok) {
      note.textContent = 'Proposal queued for ' + state.partner + ' — the GM will respond in-game.';
      note.className = 'prop-note ok';
      state.getIds.clear();
      state.giveIds.clear();
      renderPartner();
      renderMine();
      renderProposal();
    } else {
      note.textContent = 'Failed: ' + (data.error || 'could not queue proposal');
      note.className = 'prop-note err';
    }
  } catch (e) {
    const note = document.getElementById('prop-note');
    note.textContent = 'Failed: ' + e.message;
    note.className = 'prop-note err';
  }
  btn.textContent = 'Propose trade';
  renderProposal();
}

document.getElementById('btn-propose').addEventListener('click', proposeTrade);
loadTeams();


/* ============================================================
 * v2: Trade Builder modal — live AI evaluation (appended, 2026-10-04)
 * Namespaced `tb*` to avoid collisions with the v1 builder above.
 * ============================================================ */
const tbState = {
  userTeam: null,
  userPlayers: [],   // {..player, level}
  userPicks: [],
  partnerId: '',
  partnerName: '',
  partnerPlayers: [],
  partnerPicks: [],
  givePids: new Set(),
  givePicks: new Set(),
  wantPids: new Set(),
  wantPicks: new Set(),
  retention: {},      // pid -> pct (25/50) retained on players we trade away
  protection: {},     // pickId -> 'top-3'|'top-10'|'lottery' on picks we trade away
  slotsUsed: 0,       // retention slots already used by our club (from server)
  slotsMax: 3,
  protectionOptions: [], // [{code, label}] from the engine via /api/trades/assets
  verdict: null,     // last /api/trades/evaluate payload
  evalTimer: null,
  resultTimer: null,
};

/* Fallback protection options if the assets payload lacks them (same
   codes the engine uses — trade_engine.protection_label). */
const PROT_FALLBACK = [
  {code: 'top-3', label: 'Top-3 protected'},
  {code: 'top-10', label: 'Top-10 protected'},
  {code: 'lottery', label: 'Lottery protected'},
];
const RETENTION_PCTS = [0, 25, 50]; // engine max is 50%

const tbEl = id => document.getElementById(id);

async function tbOpen() {
  tbEl('tb-overlay').hidden = false;
  document.body.style.overflow = 'hidden';
  await tbLoadTeams();
  await tbLoadMyAssets();
}

function tbClose() {
  tbEl('tb-overlay').hidden = true;
  document.body.style.overflow = '';
  if (tbState.resultTimer) { clearInterval(tbState.resultTimer); tbState.resultTimer = null; }
}

async function tbLoadTeams() {
  try {
    const res = await fetch('/api/trades/teams');
    const data = await res.json();
    tbState.userTeam = data.user_team || null;
    const sel = tbEl('tb-partner-select');
    sel.innerHTML = '<option value="">— select a team —</option>';
    for (const t of (data.teams || [])) {
      if (t.is_user) continue;
      const opt = document.createElement('option');
      // assets API accepts abbr, name, or team_name; abbr is shortest
      opt.value = t.abbr || t.name;
      opt.textContent = `${t.city} ${t.name}${t.on_block ? ' · on block' : ''}`;
      sel.appendChild(opt);
    }
    tbEl('tb-your-team').textContent = tbState.userTeam
      ? 'Your team: ' + tbState.userTeam : '';
  } catch (e) { console.error(e); }
}

/* team_id lookup for assets: use abbr primarily (API matches it) */
async function tbFetchAssets(teamId) {
  const res = await fetch('/api/trades/assets?team_id=' + encodeURIComponent(teamId));
  if (!res.ok) throw new Error('assets fetch failed: ' + res.status);
  return res.json();
}

async function tbLoadMyAssets() {
  try {
    // user team lookup: teams list gives abbr; find it for the user team
    const res = await fetch('/api/trades/teams');
    const data = await res.json();
    const mine = (data.teams || []).find(t => t.is_user);
    const id = mine ? (mine.abbr || mine.name) : null;
    if (!id) return;
    const a = await tbFetchAssets(id);
    tbState.userPlayers = a.players || [];
    tbState.userPicks = a.picks || [];
    tbState.slotsUsed = a.retention_slots_used || 0;
    tbState.slotsMax = a.retention_slots_max || 3;
    tbState.protectionOptions = (a.protection_options && a.protection_options.length)
      ? a.protection_options : PROT_FALLBACK;
    tbPruneTerms();
    tbRenderGive();
    tbUpdateSlots();
  } catch (e) { console.error(e); }
}

/* Drop retention/protection terms for assets no longer in the deal. */
function tbPruneTerms() {
  for (const k of Object.keys(tbState.retention)) {
    if (!tbState.givePids.has(k)) delete tbState.retention[k];
  }
  for (const k of Object.keys(tbState.protection)) {
    if (!tbState.givePicks.has(k)) delete tbState.protection[k];
  }
}

/* Retention slots left for NEW terms (ledger use + this deal's terms). */
function tbSlotsRemaining() {
  const fresh = Object.values(tbState.retention).filter(v => v > 0).length;
  return tbState.slotsMax - tbState.slotsUsed - fresh;
}

function tbUpdateSlots() {
  const el = tbEl('tb-retention-slots');
  if (!el) return;
  const fresh = Object.values(tbState.retention).filter(v => v > 0).length;
  const used = tbState.slotsUsed + fresh;
  el.textContent = 'Retention: ' + used + '/' + tbState.slotsMax + ' slots';
  el.classList.toggle('full', used >= tbState.slotsMax);
}

function tbFlashNote(msg) {
  const note = tbEl('tb-note');
  if (!note) return;
  note.textContent = msg;
  note.className = 'prop-note err';
}

async function tbOnPartnerChange() {
  const sel = tbEl('tb-partner-select');
  tbState.partnerId = sel.value;
  tbState.partnerName = sel.value ? sel.options[sel.selectedIndex].text : '';
  tbState.wantPids.clear();
  tbState.wantPicks.clear();
  if (!tbState.partnerId) {
    tbState.partnerPlayers = [];
    tbState.partnerPicks = [];
    tbRenderGet();
    tbResetVerdict('Select a partner team and add assets on both sides.');
    return;
  }
  try {
    const a = await tbFetchAssets(tbState.partnerId);
    tbState.partnerPlayers = a.players || [];
    tbState.partnerPicks = a.picks || [];
    tbRenderGet();
    tbScheduleEvaluate();
  } catch (e) { console.error(e); }
}

function tbRow(asset, kind, side, checked) {
  // asset: player dict or pick dict; kind 'player'|'pick'
  const wrap = document.createElement('div');
  wrap.className = 'tb-asset';
  const el = document.createElement('label');
  const id = String(asset.id);
  el.className = 'player-row' + (kind === 'pick' ? ' tb-pick-row' : '')
    + (checked ? ' checked' : '')
    + (asset.injured ? ' injured' : '');
  const dataAttr = kind === 'pick' ? 'data-pick' : 'data-pid';
  const info = kind === 'pick'
    ? `<span class="pr-info"><span class="pr-name">${esc(asset.label)}</span>
       <span class="pr-sub">${asset.protection ? 'Protected: ' + esc(asset.protection) + ' · ' : ''}${esc(asset.original_team || '')}</span></span>`
    : `<span class="pr-ov">${asset.overall}</span>
       <span class="pr-info"><span class="pr-name">${esc(asset.name)}${asset.captaincy ? ' <span class="p-c">' + esc(asset.captaincy) + '</span>' : ''}</span>
       <span class="pr-sub">${esc(asset.position)} · Age ${asset.age} · ${fmtSalary(asset.salary)}</span></span>
       ${asset.injured ? '<span class="pr-inj">INJ</span>' : ''}
       ${asset.level ? '<span class="tb-level">' + esc(asset.level) + '</span>' : ''}`;
  el.innerHTML = `<input type="checkbox" ${dataAttr}="${esc(id)}" data-side="${side}" data-kind="${kind}"${checked ? ' checked' : ''}>${info}`;
  el.querySelector('input').addEventListener('change', tbOnToggle);
  wrap.appendChild(el);
  // Deal terms: retention (players) / protection (picks) on assets WE give.
  if (side === 'give' && checked) wrap.appendChild(tbTermsRow(asset, kind));
  return wrap;
}

/* Terms selector under a checked give-side asset. */
function tbTermsRow(asset, kind) {
  const id = String(asset.id);
  const div = document.createElement('div');
  div.className = 'tb-terms';
  if (kind === 'player') {
    const cur = tbState.retention[id] || 0;
    const noSlots = tbSlotsRemaining() <= 0 && cur === 0;
    const capHit = asset.cap_hit || asset.salary || 0;
    const sel = document.createElement('select');
    sel.className = 'tb-ret-select';
    sel.dataset.retPid = id;
    sel.title = noSlots
      ? 'No retention slots left (max ' + tbState.slotsMax + ' per club)'
      : 'Salary your club keeps on this player (NHL max 50%)';
    for (const pct of RETENTION_PCTS) {
      const o = document.createElement('option');
      o.value = String(pct);
      o.textContent = pct + '%';
      if (pct === cur) o.selected = true;
      if (pct > 0 && noSlots) o.disabled = true; // clamp: never exceed slots
      sel.appendChild(o);
    }
    sel.addEventListener('change', tbOnRetentionChange);
    const lbl = document.createElement('span');
    lbl.className = 'tb-terms-label';
    lbl.textContent = 'Retain salary';
    const amt = document.createElement('span');
    amt.className = 'tb-ret-amt';
    amt.textContent = cur > 0 ? 'you keep ' + fmtSalary(Math.round(capHit * cur / 100)) : '';
    div.append(lbl, sel, amt);
  } else {
    const cur = tbState.protection[id] || '';
    const sel = document.createElement('select');
    sel.className = 'tb-prot-select';
    sel.dataset.protPick = id;
    sel.title = 'Protection on this pick (NHL: top-3 / top-10 / lottery)';
    const none = document.createElement('option');
    none.value = '';
    none.textContent = 'No protection';
    if (!cur) none.selected = true;
    sel.appendChild(none);
    for (const opt of tbState.protectionOptions) {
      const o = document.createElement('option');
      o.value = opt.code;
      o.textContent = opt.label;
      if (opt.code === cur) o.selected = true;
      sel.appendChild(o);
    }
    sel.addEventListener('change', tbOnProtectionChange);
    const lbl = document.createElement('span');
    lbl.className = 'tb-terms-label';
    lbl.textContent = 'Pick protection';
    div.append(lbl, sel);
  }
  return div;
}

function tbOnRetentionChange(ev) {
  const pid = ev.target.dataset.retPid;
  const pct = parseInt(ev.target.value, 10) || 0;
  const prev = tbState.retention[pid] || 0;
  if (pct === 0) delete tbState.retention[pid];
  else tbState.retention[pid] = pct;
  if (tbSlotsRemaining() < 0) {
    // Clamp: never exceed the slot limit — revert the change.
    if (prev === 0) delete tbState.retention[pid];
    else tbState.retention[pid] = prev;
    ev.target.value = String(prev);
    tbFlashNote('Retention slot limit reached (' + tbState.slotsMax +
      ' per club) — remove a term to add another.');
    return;
  }
  tbUpdateSlots();
  tbRenderGive(); // refresh other selects' disabled state + previews
  tbScheduleEvaluate();
}

function tbOnProtectionChange(ev) {
  const pid = ev.target.dataset.protPick;
  const code = ev.target.value || '';
  if (!code) delete tbState.protection[pid];
  else tbState.protection[pid] = code;
  tbScheduleEvaluate();
}

function tbRenderList(elId, items, kind, side, selSet) {
  const list = tbEl(elId);
  list.innerHTML = '';
  if (!items.length) {
    list.innerHTML = '<div class="empty-note">None</div>';
    return;
  }
  const sorted = [...items].sort((a, b) =>
    kind === 'pick'
      ? (a.year - b.year) || (a.round - b.round)
      : (b.overall - a.overall));
  for (const a of sorted) {
    list.appendChild(tbRow(a, kind, side, selSet.has(String(a.id))));
  }
}

function tbRenderGive() {
  tbRenderList('tb-give-players', tbState.userPlayers, 'player', 'give', tbState.givePids);
  tbRenderList('tb-give-picks', tbState.userPicks, 'pick', 'give', tbState.givePicks);
}

function tbRenderGet() {
  tbRenderList('tb-get-players', tbState.partnerPlayers, 'player', 'get', tbState.wantPids);
  tbRenderList('tb-get-picks', tbState.partnerPicks, 'pick', 'get', tbState.wantPicks);
}

function tbOnToggle(ev) {
  const id = ev.target.dataset.kind === 'pick'
    ? (ev.target.dataset.pick || '') : (ev.target.dataset.pid || '');
  const set = {
    'give:player': tbState.givePids, 'give:pick': tbState.givePicks,
    'get:player': tbState.wantPids, 'get:pick': tbState.wantPicks,
  }[ev.target.dataset.side + ':' + ev.target.dataset.kind];
  if (!set) return;
  ev.target.checked ? set.add(id) : set.delete(id);
  tbPruneTerms(); // drop retention/protection on removed assets
  // Re-render the affected column so terms selectors appear/disappear.
  if (ev.target.dataset.side === 'give') tbRenderGive();
  else tbRenderGet();
  tbUpdateSlots();
  tbScheduleEvaluate();
}

function tbScheduleEvaluate() {
  if (tbState.evalTimer) clearTimeout(tbState.evalTimer);
  tbState.evalTimer = setTimeout(tbEvaluate, 450);
}

function tbResetVerdict(msg) {
  tbState.verdict = null;
  tbEl('tb-badge').className = 'tb-verdict-badge';
  tbEl('tb-badge').textContent = '—';
  tbEl('tb-reason').textContent = msg || 'Select a partner team and add assets on both sides.';
  tbEl('tb-bars').innerHTML = '';
  tbEl('tb-give-val').textContent = '';
  tbEl('tb-get-val').textContent = '';
  const termsEl = tbEl('tb-terms');
  if (termsEl) { termsEl.innerHTML = ''; termsEl.hidden = true; }
  tbEl('tb-propose').disabled = true;
}

async function tbEvaluate() {
  const q = new URLSearchParams({
    target_team_id: tbState.partnerId,
    give_pids: [...tbState.givePids].join(','),
    give_picks: [...tbState.givePicks].join(','),
    want_pids: [...tbState.wantPids].join(','),
    want_picks: [...tbState.wantPicks].join(','),
    // Gap 2: deal terms ride along so the live verdict reflects them.
    retention: Object.entries(tbState.retention)
      .filter(([, v]) => v > 0).map(([k, v]) => k + ':' + v).join(','),
    protection: Object.entries(tbState.protection)
      .map(([k, v]) => k + ':' + v).join(','),
  });
  if (!tbState.partnerId) { tbResetVerdict(); return; }
  tbEl('tb-badge').textContent = '…';
  try {
    const res = await fetch('/api/trades/evaluate?' + q.toString());
    const data = await res.json();
    tbState.verdict = data;
    tbRenderVerdict(data);
  } catch (e) {
    console.error(e);
    tbResetVerdict('Could not reach the trade evaluator: ' + e.message);
  }
}

function tbRenderVerdict(d) {
  const badge = tbEl('tb-badge');
  const v = String(d.verdict || 'reject').toLowerCase();
  badge.className = 'tb-verdict-badge ' + (v === 'accept' ? 'accept' : v === 'counter' ? 'counter' : 'reject');
  badge.textContent = v === 'accept' ? 'GM accepts' : v === 'counter' ? 'GM counters' : 'GM rejects';
  tbEl('tb-reason').textContent = d.reason || '';

  const gv = d.give_value || 0, pv = d.get_value || 0;
  tbEl('tb-give-val').textContent = gv ? `(${gv} pts)` : '';
  tbEl('tb-get-val').textContent = pv ? `(${pv} pts)` : '';
  const max = Math.max(gv, pv, 1);
  tbEl('tb-bars').innerHTML = `
    <div class="tb-bar-row"><span class="tb-bar-label">You give</span>
      <div class="tb-bar-track"><div class="tb-bar-fill give" style="width:${(100 * gv / max).toFixed(1)}%"></div></div>
      <span class="tb-bar-pts">${gv} pts</span></div>
    <div class="tb-bar-row"><span class="tb-bar-label">You get</span>
      <div class="tb-bar-track"><div class="tb-bar-fill get" style="width:${(100 * pv / max).toFixed(1)}%"></div></div>
      <span class="tb-bar-pts">${pv} pts</span></div>
    ${d.label ? `<div class="tb-bar-row"><span class="tb-bar-label">Valuation</span><span>${esc(d.label)}</span></div>` : ''}`;

  // Propose is only enabled when the REAL AI verdict says accept AND
  // every retention term passed the engine's server-side dry run.
  const retBad = (d.retention_errors && d.retention_errors.length) ||
    d.retention_valid === false;
  tbEl('tb-propose').disabled = v !== 'accept' || !!retBad;
  tbEl('tb-note').textContent = '';
  tbEl('tb-note').className = 'prop-note';

  // Gap 2: render the deal's terms under the verdict (retention kept,
  // pick protection, protection value estimate, retention errors).
  const termsEl = tbEl('tb-terms');
  if (termsEl) {
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
}

async function tbPropose() {
  const v = tbState.verdict;
  if (!v || String(v.verdict).toLowerCase() !== 'accept') return;
  const btn = tbEl('tb-propose');
  btn.disabled = true;
  btn.textContent = 'Proposing…';
  const note = tbEl('tb-note');
  try {
    const res = await fetch('/api/trades/propose', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        target_team_id: tbState.partnerId,
        give_pids: [...tbState.givePids],
        give_picks: [...tbState.givePicks],
        want_pids: [...tbState.wantPids],
        want_picks: [...tbState.wantPicks],
        retention: tbState.retention,       // {pid: pct} — server re-validates
        pick_protection: tbState.protection, // {pickId: code} — stamped at execution
      }),
    });
    const data = await res.json();
    if (data.ok) {
      note.textContent = 'Trade queued — executing on the game thread. Watching for the result…';
      note.className = 'prop-note';
      tbPollResult();
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
async function tbPollResult() {
  const note = tbEl('tb-note');
  const btn = tbEl('tb-propose');
  let tries = 0;
  if (tbState.resultTimer) clearInterval(tbState.resultTimer);
  tbState.resultTimer = setInterval(async () => {
    tries++;
    try {
      const res = await fetch('/api/trades/result');
      const data = await res.json();
      const r = data.result;
      if (r && r.marker === 'execute_trade') {
        clearInterval(tbState.resultTimer);
        tbState.resultTimer = null;
        if (r.ok) {
          note.textContent = 'Trade completed: ' + (r.summary || 'done.');
          note.className = 'prop-note ok';
          // clear the builder; refresh asset lists
          tbState.givePids.clear(); tbState.givePicks.clear();
          tbState.wantPids.clear(); tbState.wantPicks.clear();
          tbState.retention = {};
          tbState.protection = {};
          await tbLoadMyAssets();
          tbOnPartnerChange();
        } else {
          note.textContent = 'Trade blocked: ' + (r.summary || 'the GM rejected it at execution.');
          note.className = 'prop-note err';
          btn.disabled = false;
          btn.textContent = 'Propose trade';
          tbScheduleEvaluate(); // re-run eval against live state
        }
      } else if (tries > 60) {
        clearInterval(tbState.resultTimer);
        tbState.resultTimer = null;
        note.textContent = 'No execution result yet — check the game / inbox.';
        btn.disabled = false;
        btn.textContent = 'Propose trade';
      }
    } catch (e) { /* keep polling */ }
  }, 1000);
}

tbEl('btn-trade-builder').addEventListener('click', tbOpen);
tbEl('tb-close').addEventListener('click', tbClose);
tbEl('tb-overlay').addEventListener('click', e => {
  if (e.target === tbEl('tb-overlay')) tbClose();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !tbEl('tb-overlay').hidden) tbClose();
});
tbEl('tb-partner-select').addEventListener('change', tbOnPartnerChange);
tbEl('tb-propose').addEventListener('click', tbPropose);

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
