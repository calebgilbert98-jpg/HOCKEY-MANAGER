// Puck Dynasty web hub — tile rendering + API (POC)
async function loadState() {
  try {
    const res = await fetch('/api/state');
    const s = await res.json();
    renderHub(s);
  } catch (e) {
    console.error('API failed', e);
  }
}

function renderHub(s) {
  document.getElementById('team-name').textContent = s.team.name;
  document.getElementById('team-record').textContent =
    `${s.team.record.w}-${s.team.record.l}-${s.team.record.otl}`;
  document.getElementById('team-standing').textContent = s.team.standing;
  document.getElementById('game-date').textContent = s.date;
  document.getElementById('inbox-pill').textContent = s.inbox.unread;

  const grid = document.getElementById('tile-grid');
  grid.innerHTML = '';
  for (const t of s.tiles) {
    const el = document.createElement('div');
    el.className = `tile ${t.size}${t.accent ? ' accent' : ''}`;
    el.innerHTML = `
      ${t.badge ? `<span class="badge">${t.badge}</span>` : ''}
      <span class="icon">${t.icon}</span>
      <h3>${t.title}</h3>
      <p>${t.subtitle}</p>`;
    el.addEventListener('click', () => openTile(t));
    grid.appendChild(el);
  }
}

function openTile(t) {
  // POC: tiles acknowledge the click; real screens come with the bridge.
  console.log('open', t.id);
}

document.getElementById('btn-play').addEventListener('click', () => {
  console.log('play game');
});

loadState();
