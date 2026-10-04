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
  const known = ['inbox','roster','schedule','watch','lines','waivers','captains',
    'trades','trade_block','free_agents','staff','development','camp','morale',
    'standings','stats','playoffs','calendar','news','history','finances',
    'contracts','scouting','draft','settings','save'];
  if (known.includes(t.id)) { window.location.href = '/' + t.id; return; }
  if (t.id === 'continue') { continueFlow(); return; }
  console.log('open', t.id);
}

async function continueFlow() {
  let st;
  try {
    st = await (await fetch('/api/continue_state')).json();
  } catch (e) { return; }
  if (!st.blocked) {
    if (confirm('Advance the day?')) advanceDay();
    return;
  }
  showBlockerModal(st.blockers);
}

function advanceDay() {
  fetch('/api/command', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({op: 'advance_day'}),
  }).then(() => setTimeout(() => window.location.reload(), 800));
}

function showBlockerModal(blockers) {
  closeBlockerModal();
  const ov = document.createElement('div');
  ov.className = 'modal-ov'; ov.id = 'blocker-modal';
  const cards = blockers.map(b => `
    <div class="blocker-card">
      <div class="b-title">${esc(b.title)}</div>
      <div class="b-detail">${esc(b.detail)}</div>
      <div class="b-actions">
        ${b.web_route ? `<a class="btn-ghost" href="${b.web_route}">Fix it →</a>` : ''}
        ${b.has_auto ? `<button class="btn-auto" data-bid="${esc(b.id)}">⚡ ${esc(b.auto_label)}</button>` : ''}
      </div>
    </div>`).join('');
  ov.innerHTML = `
    <div class="modal-card">
      <h2>Can't advance yet</h2>
      <p class="modal-sub">${blockers.length} thing${blockers.length === 1 ? '' : 's'} need${blockers.length === 1 ? 's' : ''} your attention before the day can advance.</p>
      ${cards}
      <button class="modal-close" id="blocker-close">Close</button>
    </div>`;
  document.body.appendChild(ov);
  document.getElementById('blocker-close').addEventListener('click', closeBlockerModal);
  ov.addEventListener('click', e => { if (e.target === ov) closeBlockerModal(); });
  ov.querySelectorAll('.btn-auto').forEach(btn =>
    btn.addEventListener('click', async () => {
      btn.disabled = true; btn.textContent = 'Working…';
      await fetch('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'resolve_blocker', blocker_id: btn.dataset.bid, kind: 'auto'}),
      });
      setTimeout(async () => {
        const st = await (await fetch('/api/continue_state')).json();
        if (st.blocked) showBlockerModal(st.blockers);
        else { closeBlockerModal(); advanceDay(); }
      }, 800);
    }));
}

function closeBlockerModal() {
  const m = document.getElementById('blocker-modal');
  if (m) m.remove();
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

document.getElementById('btn-play').addEventListener('click', () => {
  console.log('play game');
});

loadState();
