/* Puck Dynasty setup page */
const $ = id => document.getElementById(id);
let pollTimer = null;

async function init() {
  // teams
  try {
    const r = await fetch('/api/teams');
    const d = await r.json();
    const sel = $('team-picker');
    sel.innerHTML = '';
    d.teams.forEach(t => {
      const o = document.createElement('option');
      o.value = t.name; o.textContent = `${t.abbr} — ${t.name}`;
      if (t.name === 'Boston Bruins') o.selected = true;
      sel.appendChild(o);
    });
  } catch (e) {
    $('team-picker').innerHTML = '<option>Boston Bruins</option>';
  }
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
    body: JSON.stringify({mode: 'new', team, gm_name: gm}),
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
