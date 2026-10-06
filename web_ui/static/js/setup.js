/* Puck Dynasty setup page — full v0.18.4 launcher parity */
const $ = id => document.getElementById(id);
let pollTimer = null;

const DB_HINTS = {
  default: '~8,000 players · recommended',
  small: '~2,500 players · fastest',
  medium: '~6,000 players · balanced',
  large: '~12,000 players · slowest',
};
const LEAGUES = ['NHL', 'AHL', 'ECHL', 'KHL'];
const SIM_DETAILS = [
  ['full', 'Full — event-by-event'],
  ['quick', 'Quick — scores + standings'],
  ['scores', 'Scores only'],
];
const SIM_DEFAULTS = { NHL: 'full', AHL: 'quick', ECHL: 'scores', KHL: 'quick' };

const state = {
  dbSize: 'default',
  leagues: ['NHL', 'AHL'],
  simDetail: { ...SIM_DEFAULTS },
  playoffFormat: 'divisional',
  userLeague: 'NHL',
  teamsByLeague: {},
  startDate: 'September 1, 2024',
  seasonLength: 'Default (84 Games)',
  difficulty: 'Professional',
  tradeDifficulty: 'Realistic',
  cpuIQ: 'Medium (Balanced)',
  selectedSave: null,
};

/* ---------- tabs ---------- */
function initTabs() {
  $('setup-tabs').addEventListener('click', e => {
    const btn = e.target.closest('button[data-tab]');
    if (!btn) return;
    document.querySelectorAll('#setup-tabs button').forEach(b =>
      b.classList.toggle('active', b === btn));
    document.querySelectorAll('.setup-tab').forEach(t =>
      t.classList.toggle('hidden', t.id !== 'tab-' + btn.dataset.tab));
  });
}

/* ---------- pill groups ---------- */
function pillGroup(elId, onPick) {
  const el = $(elId);
  el.addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    el.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    onPick(btn.dataset.val);
  });
}

/* ---------- GM profile ---------- */
const GM_FIRST = ['Alex','Jordan','Casey','Taylor','Morgan','Jamie','Riley','Cameron','Blake','Avery','Michael','David','John','Robert','Chris','Daniel','Mark','Paul','Steve','Kevin'];
const GM_LAST = ['Anderson','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Thomas','Taylor','Moore','Jackson','Martin','Lee'];

function randomGMName() {
  return GM_FIRST[Math.floor(Math.random() * GM_FIRST.length)] + ' ' +
         GM_LAST[Math.floor(Math.random() * GM_LAST.length)];
}

function gmProfile() {
  return {
    name: $('gm-name').value.trim() || 'General Manager',
    age: parseInt($('gm-age').value, 10) || 35,
    experience: $('gm-exp').value,
    background: $('gm-bg').value,
    management_style: $('gm-style').value,
    contract_length: $('gm-contract').value,
    reputation: $('gm-rep').value,
  };
}

function renderGMPreview() {
  const p = gmProfile();
  $('gm-preview').innerHTML =
    `<b>${esc(p.name)}</b>, ${p.age} — ${esc(p.experience)}<br>` +
    `${esc(p.background)} · ${esc(p.management_style)}<br>` +
    `${esc(p.contract_length)} · Reputation: ${esc(p.reputation)}`;
}

function randomGMProfile() {
  $('gm-name').value = randomGMName();
  $('gm-age').value = String(28 + Math.floor(Math.random() * 38));
  const pick = id => {
    const sel = $(id);
    sel.selectedIndex = Math.floor(Math.random() * sel.options.length);
  };
  pick('gm-exp'); pick('gm-bg'); pick('gm-style');
  pick('gm-contract'); pick('gm-rep');
  renderGMPreview();
}

function initGMTab() {
  // age options 28-70
  const ageSel = $('gm-age');
  for (let a = 28; a <= 70; a++) {
    const o = document.createElement('option');
    o.value = String(a); o.textContent = String(a);
    if (a === 35) o.selected = true;
    ageSel.appendChild(o);
  }
  ['gm-name','gm-age','gm-exp','gm-bg','gm-style','gm-contract','gm-rep']
    .forEach(id => $(id).addEventListener('input', renderGMPreview));
  $('btn-gm-random-name').addEventListener('click', () => {
    $('gm-name').value = randomGMName();
    renderGMPreview();
  });
  $('btn-gm-random').addEventListener('click', randomGMProfile);
  renderGMPreview();
}

/* ---------- presets ---------- */
const PRESETS = {
  arcade: {
    dbSize: 'small', seasonLength: 'Short Season (20 Games)',
    difficulty: 'Amateur', tradeDifficulty: 'Easy', cpuIQ: 'Medium (Balanced)',
    fantasy: true, cap: false, injuries: false, morale: true,
    progression: false, composite: false, fog: true,
  },
  realistic: {
    dbSize: 'default', seasonLength: 'Default (84 Games)',
    difficulty: 'Realistic', tradeDifficulty: 'Realistic', cpuIQ: 'High (Challenging)',
    fantasy: false, cap: true, injuries: true, morale: true,
    progression: true, composite: false, fog: true,
  },
  challenge: {
    dbSize: 'large', seasonLength: 'Default (84 Games)',
    difficulty: 'Hall of Fame', tradeDifficulty: 'Nearly Impossible', cpuIQ: 'Maximum (Ruthless)',
    fantasy: false, cap: true, injuries: true, morale: true,
    progression: true, composite: true, fog: true,
  },
  quick: {
    dbSize: 'small', seasonLength: 'Short Season (20 Games)',
    difficulty: 'Rookie', tradeDifficulty: 'Very Easy', cpuIQ: 'Low (Predictable)',
    fantasy: false, cap: true, injuries: false, morale: false,
    progression: true, composite: false, fog: false,
  },
};

function applyPreset(name) {
  const p = PRESETS[name];
  if (!p) return;
  setPill('db-size-pills', p.dbSize);
  state.dbSize = p.dbSize;
  $('db-size-hint').textContent = DB_HINTS[p.dbSize] || '';
  setPill('season-len-pills', p.seasonLength);
  state.seasonLength = p.seasonLength;
  setPill('difficulty-pills', p.difficulty);
  state.difficulty = p.difficulty;
  $('opt-trade-diff').value = p.tradeDifficulty;
  state.tradeDifficulty = p.tradeDifficulty;
  $('opt-cpu-iq').value = p.cpuIQ;
  state.cpuIQ = p.cpuIQ;
  $('opt-fantasy').checked = p.fantasy;
  $('opt-cap').checked = p.cap;
  $('opt-injuries').checked = p.injuries;
  $('opt-morale').checked = p.morale;
  $('opt-progression').checked = p.progression;
  $('opt-composite').checked = p.composite;
  $('opt-fog').checked = p.fog;
}

function setPill(elId, val) {
  document.querySelectorAll(`#${elId} button`).forEach(b =>
    b.classList.toggle('active', b.dataset.val === val));
}

/* ---------- team/league pickers ---------- */
function renderSimDetailRows() {
  const host = $('sim-detail-rows');
  host.innerHTML = '';
  for (const lg of state.leagues) {
    const row = document.createElement('div');
    row.className = 'sim-row';
    const lab = document.createElement('span');
    lab.className = 'sim-league';
    lab.textContent = lg;
    const sel = document.createElement('select');
    sel.className = 'nhl';
    sel.dataset.league = lg;
    for (const [val, label] of SIM_DETAILS) {
      const o = document.createElement('option');
      o.value = val; o.textContent = label;
      if (state.simDetail[lg] === val) o.selected = true;
      sel.appendChild(o);
    }
    sel.addEventListener('change', () => { state.simDetail[lg] = sel.value; });
    row.appendChild(lab);
    row.appendChild(sel);
    host.appendChild(row);
  }
}

function refreshTeamPicker() {
  const sel = $('team-picker');
  const teams = state.teamsByLeague[state.userLeague] || [];
  sel.innerHTML = '';
  teams.forEach(t => {
    const o = document.createElement('option');
    o.value = t.name; o.textContent = `${t.abbr} — ${t.name}`;
    sel.appendChild(o);
  });
  if (!teams.length) {
    const o = document.createElement('option');
    o.textContent = 'Random'; o.value = 'Random';
    sel.appendChild(o);
  }
  updateStartButtons();
}

/* ---------- career action bar (outside the tabs) ---------- */
function teamsLoaded() {
  const sel = $('team-picker');
  return !!(sel && sel.options.length &&
    sel.options[0].textContent !== 'Loading teams…');
}
/* Start Career stays disabled until a real team is selected. */
function updateStartButtons() {
  const ok = teamsLoaded() && !!$('team-picker').value;
  $('btn-new').disabled = !ok;
  $('btn-quick').disabled = !teamsLoaded();
  $('setup-actions-hint').textContent = ok
    ? ''
    : 'Select a team to start your career.';
}
/* Quick Start: basic defaults, randomized GM + team, straight in. */
function basicConfig() {
  const gm = gmProfile(); // already randomized by quickStart()
  return {
    mode: 'new',
    team: $('team-picker').value,
    gm_name: gm.name,
    gm_profile: gm,
    database_size: 'default',
    leagues: ['NHL', 'AHL'],
    sim_detail: { NHL: 'full', AHL: 'quick' },
    fog_of_war: true,
    fantasy_draft: false,
    salary_cap: true,
    injuries: true,
    morale_system: true,
    start_date: 'September 1, 2024',
    season_length: 'Default (84 Games)',
    difficulty: 'Professional',
    trade_difficulty: 'Realistic',
    cpu_gm_intelligence: 'Medium (Balanced)',
    international_players: true,
    start_without_cap_penalties: false,
    realistic_progression: true,
    show_composite_ratings: false,
    playoff_format: 'divisional',
    user_league: 'NHL',
  };
}
async function quickStart() {
  randomGMProfile();
  const sel = $('team-picker');
  if (sel.options.length > 0) {
    sel.selectedIndex = Math.floor(Math.random() * sel.options.length);
  }
  updateStartButtons();
  await startNew(basicConfig());
}

/* ---------- saves ---------- */
async function loadSaves() {
  try {
    const r = await fetch('/api/saves');
    const d = await r.json();
    const list = $('save-list');
    state.selectedSave = null;
    $('btn-save-delete').disabled = true;
    if (!d.saves.length) {
      list.innerHTML = '<p class="dim">No saved games yet.</p>';
    } else {
      list.innerHTML = '';
      d.saves.forEach(s => {
        const b = document.createElement('button');
        b.className = 'save-row';
        b.dataset.path = s.path;
        const dt = new Date(s.mtime * 1000).toLocaleDateString();
        b.innerHTML = `<span>${esc(s.name)}</span><span class="dim">${dt}</span>`;
        b.addEventListener('click', () => {
          list.querySelectorAll('.save-row').forEach(x => x.classList.remove('selected'));
          b.classList.add('selected');
          state.selectedSave = s;
          $('btn-save-delete').disabled = false;
        });
        b.addEventListener('dblclick', () => startLoad(s.path));
        list.appendChild(b);
      });
    }
  } catch (e) {
    $('save-list').innerHTML = '<p class="dim">Could not list saves.</p>';
  }
}

/* ---------- multiplayer ---------- */
let mpPoll = null;

async function mpHost() {
  const name = $('mp-host-name').value.trim() || 'Host';
  const port = parseInt($('mp-host-port').value, 10) || 27107;
  const st = $('mp-host-status');
  st.textContent = 'Starting host…';
  try {
    const r = await fetch('/api/mp/host', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, port}),
    });
    const d = await r.json();
    if (d.ok) {
      st.innerHTML = `Hosting on <b>${esc(d.ips.join(', '))}</b>:${d.port}<br>Share your Radmin VPN IP with friends.`;
      $('mp-lobby').classList.remove('hidden');
      pollLobby();
    } else {
      st.textContent = 'Failed: ' + (d.error || 'unknown');
    }
  } catch (e) { st.textContent = 'Failed: ' + e.message; }
}

async function pollLobby() {
  clearInterval(mpPoll);
  mpPoll = setInterval(async () => {
    try {
      const r = await fetch('/api/mp/lobby');
      const d = await r.json();
      const list = $('mp-lobby-list');
      list.innerHTML = (d.members || []).map(m =>
        `<div class="mp-member">${esc(m.name)}${m.team ? ' — ' + esc(m.team) : ' (no team)'}</div>`
      ).join('') || '<p class="dim">Waiting for players…</p>';
    } catch (e) {}
  }, 2000);
}

async function mpStartGame() {
  // Collect full new-game config and start as host
  const cfg = collectConfig();
  cfg.multiplayer_host = true;
  await startNew(cfg);
}

async function mpJoin() {
  const ip = $('mp-join-ip').value.trim();
  const port = parseInt($('mp-join-port').value, 10) || 27107;
  const name = $('mp-join-name').value.trim() || 'Guest';
  const st = $('mp-join-status');
  if (!ip) { st.textContent = 'Enter the host IP address.'; return; }
  st.textContent = 'Connecting…';
  try {
    const r = await fetch('/api/mp/join', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ip, port, name}),
    });
    const d = await r.json();
    if (d.ok) {
      st.textContent = 'Connected! Claim your team below.';
      const teams = $('mp-team-list');
      teams.innerHTML = '';
      (d.teams || []).forEach(t => {
        const b = document.createElement('button');
        b.className = 'mp-team-btn' + (t.claimed ? ' claimed' : '');
        b.textContent = t.name + (t.claimed ? ` (${t.by})` : '');
        b.disabled = !!t.claimed;
        b.addEventListener('click', () => mpClaimTeam(t.id));
        teams.appendChild(b);
      });
      $('mp-team-claim').classList.remove('hidden');
      pollJoinStatus();
    } else {
      st.textContent = 'Failed: ' + (d.error || 'could not connect');
    }
  } catch (e) { st.textContent = 'Failed: ' + e.message; }
}

async function mpClaimTeam(teamId) {
  try {
    const r = await fetch('/api/mp/claim', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({team_id: teamId}),
    });
    const d = await r.json();
    if (d.ok) {
      $('mp-join-status').textContent = 'Team claimed! Waiting for host to start…';
      // refresh team list
      mpJoin();
    }
  } catch (e) {}
}

let mpJoinPoll = null;
async function pollJoinStatus() {
  clearInterval(mpJoinPoll);
  mpJoinPoll = setInterval(async () => {
    try {
      const r = await fetch('/api/mp/status');
      const d = await r.json();
      if (d.game_started) {
        clearInterval(mpJoinPoll);
        window.location.href = '/';
      }
    } catch (e) {}
  }, 2000);
}

/* ---------- new game ---------- */
function collectConfig() {
  return {
    mode: 'new',
    team: $('team-picker').value,
    gm_name: $('gm-name').value.trim() || 'General Manager',
    gm_profile: gmProfile(),
    database_size: state.dbSize,
    leagues: state.leagues,
    sim_detail: Object.fromEntries(
      state.leagues.map(lg => [lg, state.simDetail[lg] || SIM_DEFAULTS[lg]])
    ),
    fog_of_war: $('opt-fog').checked,
    fantasy_draft: $('opt-fantasy').checked,
    salary_cap: $('opt-cap').checked,
    injuries: $('opt-injuries').checked,
    morale_system: $('opt-morale').checked,
    start_date: state.startDate,
    season_length: state.seasonLength,
    difficulty: state.difficulty,
    trade_difficulty: state.tradeDifficulty,
    cpu_gm_intelligence: state.cpuIQ,
    international_players: $('opt-intl').checked,
    start_without_cap_penalties: $('opt-no-penalties').checked,
    realistic_progression: $('opt-progression').checked,
    show_composite_ratings: $('opt-composite').checked,
    playoff_format: state.playoffFormat,
    user_league: state.userLeague,
  };
}

async function startNew(cfg) {
  showProgress('Starting…');
  await fetch('/api/setup', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(cfg || collectConfig()),
  });
  poll();
}

async function startLoad(path) {
  showProgress('Loading…');
  await fetch('/api/setup', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mode: 'load', path}),
  });
  poll();
}

function showProgress(detail) {
  $('setup-progress').classList.remove('hidden');
  $('setup-detail').textContent = detail;
  document.querySelector('.setup-wrap').style.pointerEvents = 'none';
}

async function poll() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const r = await fetch('/api/setup_status');
      const d = await r.json();
      if (d.detail) $('setup-detail').textContent = d.detail;
      if (d.status === 'ready' && d.game_ready) {
        clearInterval(pollTimer);
        window.location.href = '/';
      } else if (d.status === 'error') {
        clearInterval(pollTimer);
        $('setup-detail').textContent = 'Error: ' + (d.detail || 'setup failed');
      }
    } catch (e) {}
  }, 1200);
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function heartbeat() {
  fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
}

/* ---------- init ---------- */
async function init() {
  initTabs();
  initGMTab();

  pillGroup('db-size-pills', v => {
    state.dbSize = v;
    $('db-size-hint').textContent = DB_HINTS[v] || '';
  });
  pillGroup('playoff-pills', v => { state.playoffFormat = v; });
  pillGroup('start-date-pills', v => { state.startDate = v; });
  pillGroup('season-len-pills', v => { state.seasonLength = v; });
  pillGroup('difficulty-pills', v => { state.difficulty = v; });
  pillGroup('preset-pills', v => applyPreset(v));

  $('opt-trade-diff').addEventListener('change', e => { state.tradeDifficulty = e.target.value; });
  $('opt-cpu-iq').addEventListener('change', e => { state.cpuIQ = e.target.value; });

  // league toggles (multi-select)
  $('league-pills').addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    btn.classList.toggle('active');
    const active = [...$('league-pills').querySelectorAll('button.active')]
      .map(b => b.dataset.val);
    if (!active.length) { btn.classList.add('active'); return; }
    state.leagues = active;
    if (!state.leagues.includes(state.userLeague)) {
      state.userLeague = state.leagues[0];
      $('league-picker').value = state.userLeague;
    }
    renderSimDetailRows();
    refreshTeamPicker();
  });

  const lp = $('league-picker');
  LEAGUES.forEach(lg => {
    const o = document.createElement('option');
    o.value = lg; o.textContent = lg;
    lp.appendChild(o);
  });
  lp.addEventListener('change', () => {
    state.userLeague = lp.value;
    if (!state.leagues.includes(state.userLeague)) {
      state.leagues.push(state.userLeague);
      document.querySelector(`#league-pills button[data-val="${state.userLeague}"]`)
        ?.classList.add('active');
      renderSimDetailRows();
    }
    refreshTeamPicker();
  });

  try {
    const r = await fetch('/api/teams');
    const d = await r.json();
    state.teamsByLeague = { NHL: d.teams || [] };
    try {
      const r2 = await fetch('/api/teams?league=AHL');
      const d2 = await r2.json();
      if (d2.teams?.length) state.teamsByLeague.AHL = d2.teams;
    } catch (e) {}
    refreshTeamPicker();
  } catch (e) {
    $('team-picker').innerHTML = '<option>Boston Bruins</option>';
  }

  $('btn-random').addEventListener('click', () => {
    const sel = $('team-picker');
    if (sel.options.length > 1) {
      sel.selectedIndex = Math.floor(Math.random() * sel.options.length);
    }
  });

  renderSimDetailRows();
  await loadSaves();

  // save actions
  $('btn-save-delete').addEventListener('click', async () => {
    if (!state.selectedSave) return;
    if (!confirm('Delete save "' + state.selectedSave.name + '"?')) return;
    await fetch('/api/saves/delete', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: state.selectedSave.path}),
    });
    await loadSaves();
  });
  $('btn-save-import').addEventListener('click', () => $('save-file-input').click());
  $('save-file-input').addEventListener('change', async e => {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append('file', f);
    await fetch('/api/saves/import', {method: 'POST', body: fd});
    await loadSaves();
  });

  // multiplayer
  $('btn-mp-host').addEventListener('click', mpHost);
  $('btn-mp-join').addEventListener('click', mpJoin);
  $('btn-mp-start').addEventListener('click', mpStartGame);

  $('btn-new').addEventListener('click', () => startNew());
  $('btn-quick').addEventListener('click', quickStart);
  $('team-picker').addEventListener('change', updateStartButtons);
  updateStartButtons();
  heartbeat();
  setInterval(heartbeat, 30000);
}

init();
