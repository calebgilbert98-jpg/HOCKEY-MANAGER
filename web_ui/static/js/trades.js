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
