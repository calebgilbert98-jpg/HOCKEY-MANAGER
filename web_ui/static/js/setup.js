/* Puck Dynasty setup page — full v0.18.4 option parity */
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
};

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
    sel.addEventListener('change', () => {
      state.simDetail[lg] = sel.value;
    });
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
    o.textContent = 'Random';
    o.value = 'Random';
    sel.appendChild(o);
  }
}

async function init() {
  // pill groups
  pillGroup('db-size-pills', v => {
    state.dbSize = v;
    $('db-size-hint').textContent = DB_HINTS[v] || '';
  });
  pillGroup('playoff-pills', v => { state.playoffFormat = v; });

  // league toggles (multi-select)
  $('league-pills').addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    btn.classList.toggle('active');
    const active = [...$('league-pills').querySelectorAll('button.active')]
      .map(b => b.dataset.val);
    if (!active.length) { btn.classList.add('active'); return; } // keep ≥1
    state.leagues = active;
    if (!state.leagues.includes(state.userLeague)) {
      state.userLeague = state.leagues[0];
      $('league-picker').value = state.userLeague;
    }
    renderSimDetailRows();
    refreshTeamPicker();
  });

  // league picker for user team
  const lp = $('league-picker');
  LEAGUES.forEach(lg => {
    const o = document.createElement('option');
    o.value = lg; o.textContent = lg;
    lp.appendChild(o);
  });
  lp.addEventListener('change', () => {
    state.userLeague = lp.value;
    // ensure the league is active
    if (!state.leagues.includes(state.userLeague)) {
      state.leagues.push(state.userLeague);
      document.querySelector(`#league-pills button[data-val="${state.userLeague}"]`)
        ?.classList.add('active');
      renderSimDetailRows();
    }
    refreshTeamPicker();
  });

  // teams
  try {
    const r = await fetch('/api/teams');
    const d = await r.json();
    // group by league — API returns flat list; NHL teams have real names
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

  // saves
  try {
    const r = await fetch('/api/saves');
    const d = await r.json();
    const list = $('save-list');
    if (!d.saves.length) {
      list.innerHTML = '<p class="dim">No saved games yet.</p>';
    } else {
      list.innerHTML = '';
      d.saves.forEach(s => {
        const b = document.createElement('button');
        b.className = 'save-row';
        const dt = new Date(s.mtime * 1000).toLocaleDateString();
        b.innerHTML = `<span>${s.name}</span><span class="dim">${dt}</span>`;
        b.addEventListener('click', () => startLoad(s.path));
        list.appendChild(b);
      });
    }
  } catch (e) {
    $('save-list').innerHTML = '<p class="dim">Could not list saves.</p>';
  }
  $('btn-new').addEventListener('click', startNew);
  heartbeat();
  setInterval(heartbeat, 30000);
}

async function startNew() {
  const team = $('team-picker').value;
  const gm = $('gm-name').value || 'General Manager';
  showProgress('Starting…');
  await fetch('/api/setup', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      mode: 'new',
      team,
      gm_name: gm,
      database_size: state.dbSize,
      leagues: state.leagues,
      sim_detail: Object.fromEntries(
        state.leagues.map(lg => [lg, state.simDetail[lg] || SIM_DEFAULTS[lg]])
      ),
      fog_of_war: $('opt-fog').checked,
      fantasy_draft: $('opt-fantasy').checked,
      playoff_format: state.playoffFormat,
      user_league: state.userLeague,
    }),
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
  document.querySelector('.setup-cols').style.opacity = '0.35';
  document.querySelector('.setup-cols').style.pointerEvents = 'none';
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

function heartbeat() {
  fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
}

init();
