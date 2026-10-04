/* Puck Dynasty web free agents */
let FA_PLAYERS = [];
let FA_POS = 'ALL';
let FA_TYPE = 'ALL';
let FA_SORT = 'overall';

async function loadFA() {
  try {
    const res = await fetch('/api/free_agents');
    const data = await res.json();
    FA_PLAYERS = data.players || [];
    bindFilters();
    renderFA();
  } catch (e) { console.error(e); }
}

function bindFilters() {
  document.querySelectorAll('#pos-filter .fa-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#pos-filter .fa-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      FA_POS = btn.dataset.pos;
      renderFA();
    });
  });
  document.querySelectorAll('#type-filter .fa-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#type-filter .fa-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      FA_TYPE = btn.dataset.type;
      renderFA();
    });
  });
  document.getElementById('fa-sort').addEventListener('change', e => {
    FA_SORT = e.target.value;
    renderFA();
  });
}

function barColor(v) {
  if (v >= 75) return '#4CAF50';
  if (v >= 60) return '#8BC34A';
  if (v >= 45) return '#FFC107';
  if (v >= 30) return '#FF9800';
  return '#F44336';
}

function salaryStr(s) {
  s = s || 0;
  return s >= 1e6 ? '$' + (s / 1e6).toFixed(2) + 'M'
                  : '$' + Math.round(s / 1e3) + 'K';
}

function matchesPos(p) {
  if (FA_POS === 'ALL') return true;
  const pos = String(p.position || '');
  if (FA_POS === 'D') return /D\b|LD|RD|DEF/i.test(pos);
  return pos.split(/[\/, ]+/).includes(FA_POS);
}

function filtered() {
  let list = FA_PLAYERS.filter(p =>
    matchesPos(p) && (FA_TYPE === 'ALL' || p.fa_type === FA_TYPE));
  switch (FA_SORT) {
    case 'ask-asc': list.sort((a, b) => a.ask - b.ask); break;
    case 'ask-desc': list.sort((a, b) => b.ask - a.ask); break;
    case 'age': list.sort((a, b) => a.age - b.age); break;
    default: list.sort((a, b) => b.overall - a.overall);
  }
  return list;
}

function renderFA() {
  const list = document.getElementById('fa-list');
  const players = filtered();
  document.getElementById('fa-count').textContent =
    players.length + (players.length === 1 ? ' player' : ' players') + ' available';
  list.innerHTML = '';
  if (!players.length) {
    const el = document.createElement('div');
    el.className = 'fa-empty';
    el.textContent = 'No free agents match the current filters.';
    list.appendChild(el);
    return;
  }
  for (const p of players) {
    const el = document.createElement('div');
    el.className = 'fa-card';
    el.innerHTML = `
      <div class="fa-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
      <div class="fa-info">
        <div class="fa-name">${esc(p.name)} <span class="fa-tag">${esc(p.fa_type)}</span></div>
        <div class="fa-sub">${esc(p.position)} · Age ${p.age} · Asking ${salaryStr(p.ask)}</div>
      </div>
      <div class="fa-bar"><span style="width:${Math.min(100, p.overall)}%;background:${barColor(p.overall)}"></span></div>
      <button class="btn-offer" data-id="${esc(p.id)}">Make offer</button>`;
    const btn = el.querySelector('.btn-offer');
    btn.addEventListener('click', () => makeOffer(btn, p.id, p.ask, p.name));
    list.appendChild(el);
  }
}

async function makeOffer(btn, playerId, ask, name) {
  btn.disabled = true;
  btn.textContent = 'Offering…';
  try {
    const res = await fetch('/api/free_agents/offer', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: playerId, salary: ask})
    });
    const data = await res.json();
    if (data.ok) {
      btn.textContent = 'Offer sent ✓';
    } else {
      btn.textContent = 'Make offer';
      btn.disabled = false;
      alert('Could not send offer: ' + (data.error || 'unknown error'));
    }
  } catch (e) {
    console.error(e);
    btn.textContent = 'Make offer';
    btn.disabled = false;
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadFA();
