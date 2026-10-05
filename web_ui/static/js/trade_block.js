/* Puck Dynasty web trade block — 3 tabs: Your Block / Interest / Others */
const tbState = { tab: 'mine', filters: { pos: 'All', min_ovr: '', max_age: '' },
                  selected: new Set() };

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
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

/* ---------- tabs ---------- */
document.getElementById('tb-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('.tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('.tb-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('tab-' + b.dataset.tab).classList.remove('hidden');
  tbState.tab = b.dataset.tab;
  if (b.dataset.tab === 'mine') loadMine();
  if (b.dataset.tab === 'interest') loadInterest();
  if (b.dataset.tab === 'others') loadOthers();
});

/* ---------- Tab 1: Your Block ---------- */
async function loadMine() {
  const f = tbState.filters;
  const q = new URLSearchParams({ pos: f.pos });
  if (f.min_ovr) q.set('min_ovr', f.min_ovr);
  if (f.max_age) q.set('max_age', f.max_age);
  try {
    const res = await fetch('/api/trade_block?' + q);
    const data = await res.json();
    renderMine(data.players || []);
  } catch (e) { console.error(e); }
}

function renderMine(players) {
  const grid = document.getElementById('block-grid');
  document.getElementById('block-count').textContent =
    players.length + (players.length === 1 ? ' player' : ' players') + ' on your block';
  grid.innerHTML = '';
  if (!players.length) {
    grid.innerHTML = '<div class="block-empty">No players on the trade block. Use “Add Players” to list someone.</div>';
    return;
  }
  for (const p of players) {
    const el = document.createElement('div');
    el.className = 'block-card' + (tbState.selected.has(p.id) ? ' selected' : '');
    el.innerHTML = `
      <label class="b-check"><input type="checkbox" data-pid="${esc(p.id)}"
        ${tbState.selected.has(p.id) ? 'checked' : ''}></label>
      <div class="b-head">
        <div class="b-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
        <div>
          <div class="b-name">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile">${esc(p.name)}</span>` : esc(p.name)}</div>
          <div class="b-sub">${esc(p.position)} · Age ${p.age} · ${salaryStr(p.salary)}</div>
        </div>
      </div>
      <div class="b-bar"><span style="width:${Math.min(100, p.overall)}%;background:${barColor(p.overall)}"></span></div>
      <div class="b-row-actions">
        <button class="tb-mini" data-shop="${esc(p.id)}">Shop</button>
        <button class="tb-mini" data-value="${esc(p.id)}">Value</button>
      </div>`;
    grid.appendChild(el);
  }
}

document.getElementById('block-grid').addEventListener('change', e => {
  const cb = e.target.closest('input[type=checkbox]');
  if (!cb) return;
  if (cb.checked) tbState.selected.add(cb.dataset.pid);
  else tbState.selected.delete(cb.dataset.pid);
  cb.closest('.block-card').classList.toggle('selected', cb.checked);
});
document.getElementById('block-grid').addEventListener('click', async e => {
  const sh = e.target.closest('[data-shop]');
  const va = e.target.closest('[data-value]');
  if (sh) return showShop(sh.dataset.shop);
  if (va) return showSuggest(va.dataset.value);
});

document.getElementById('pill-pos').addEventListener('click', e => {
  const b = e.target.closest('.tb-pill');
  if (!b) return;
  document.querySelectorAll('#pill-pos .tb-pill').forEach(p => p.classList.remove('active'));
  b.classList.add('active');
  tbState.filters.pos = b.dataset.v;
});
document.getElementById('btn-apply-filters').addEventListener('click', () => {
  tbState.filters.min_ovr = document.getElementById('f-min-ovr').value;
  tbState.filters.max_age = document.getElementById('f-max-age').value;
  loadMine();
});

document.getElementById('btn-remove').addEventListener('click', async () => {
  if (!tbState.selected.size) return alert('Select players first.');
  await fetch('/api/trade_block/remove', { method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ player_ids: [...tbState.selected] }) });
  tbState.selected.clear();
  setTimeout(loadMine, 800);
});

document.getElementById('btn-simulate').addEventListener('click', async () => {
  await fetch('/api/trade_block/simulate_offers', { method: 'POST' });
  alert('Offer simulation queued — check your inbox for incoming offers.');
});
document.getElementById('btn-interest').addEventListener('click', async () => {
  await fetch('/api/trade_block/generate_interest', { method: 'POST' });
  alert('Interest generation queued — check the Trade Interest tab shortly.');
});

/* Add-players modal */
document.getElementById('btn-add').addEventListener('click', async () => {
  document.getElementById('add-modal').classList.remove('hidden');
  try {
    const res = await fetch('/api/roster');
    const data = await res.json();
    const players = data.players || data || [];
    renderAddList(players, '');
  } catch (e) { console.error(e); }
});
document.getElementById('add-search').addEventListener('input', async e => {
  const res = await fetch('/api/roster');
  const data = await res.json();
  renderAddList(data.players || data || [], e.target.value.toLowerCase());
});
function renderAddList(players, q) {
  const host = document.getElementById('add-list');
  host.innerHTML = '';
  const addSel = new Set();
  for (const p of players) {
    if (q && !(p.name || '').toLowerCase().includes(q)) continue;
    const el = document.createElement('label');
    el.className = 'tb-add-row';
    el.innerHTML = `<input type="checkbox" data-pid="${esc(p.id)}">
      <span>${esc(p.name)}</span>
      <span class="dim">${esc(p.position)} · ${p.overall} OVR</span>`;
    host.appendChild(el);
  }
  host.onchange = e => {
    const cb = e.target.closest('input[type=checkbox]');
    if (cb.checked) addSel.add(cb.dataset.pid); else addSel.delete(cb.dataset.pid);
  };
  document.getElementById('add-confirm').onclick = async () => {
    if (!addSel.size) return;
    await fetch('/api/trade_block/add', { method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ player_ids: [...addSel] }) });
    document.getElementById('add-modal').classList.add('hidden');
    setTimeout(loadMine, 800);
  };
}
document.getElementById('add-cancel').addEventListener('click', () =>
  document.getElementById('add-modal').classList.add('hidden'));

/* Shop / Suggest modals */
async function showShop(pid) {
  try {
    const res = await fetch('/api/trade_block/shop?player_id=' + encodeURIComponent(pid));
    const d = await res.json();
    document.getElementById('info-title').textContent = 'Shop: ' + d.player;
    let html = `<p>Market value: <b>${'$' + d.market_value.toLocaleString()}</b><br>
      Trade-block value (15% discount): <b>${'$' + d.block_value.toLocaleString()}</b></p>`;
    if (d.interested && d.interested.length) {
      html += '<h3>Interested teams</h3><ul>' +
        d.interested.map(i => `<li>${esc(i.team)} — ${esc(i.interest)}</li>`).join('') + '</ul>';
    } else html += '<p class="dim">No teams showing significant interest yet. Try Generate Interest.</p>';
    document.getElementById('info-body').innerHTML = html;
    document.getElementById('info-modal').classList.remove('hidden');
  } catch (e) { console.error(e); }
}
async function showSuggest(pid) {
  document.getElementById('btn-suggest').disabled = true;
  try {
    const res = await fetch('/api/trade_block/suggest?player_ids=' + encodeURIComponent(pid));
    const d = await res.json();
    const p = (d.players || [])[0];
    if (p) {
      document.getElementById('info-title').textContent = 'Trade Value: ' + p.player;
      document.getElementById('info-body').innerHTML =
        `<p>Market value: <b>${'$' + p.market_value.toLocaleString()}</b><br>
         Trade-block value: <b>${'$' + p.block_value.toLocaleString()}</b> (15% discount)</p>`;
      document.getElementById('info-modal').classList.remove('hidden');
    }
  } catch (e) { console.error(e); }
  document.getElementById('btn-suggest').disabled = false;
}
document.getElementById('btn-suggest').addEventListener('click', async () => {
  const ids = [...tbState.selected];
  if (!ids.length) return alert('Select players first.');
  try {
    const res = await fetch('/api/trade_block/suggest?player_ids=' + ids.map(encodeURIComponent).join(','));
    const d = await res.json();
    document.getElementById('info-title').textContent = 'Trade Values';
    document.getElementById('info-body').innerHTML =
      '<ul>' + (d.players || []).map(p =>
        `<li><b>${esc(p.player)}</b>: ${'$' + p.market_value.toLocaleString()} → block ${'$' + p.block_value.toLocaleString()}</li>`).join('') + '</ul>';
    document.getElementById('info-modal').classList.remove('hidden');
  } catch (e) { console.error(e); }
});
document.getElementById('info-close').addEventListener('click', () =>
  document.getElementById('info-modal').classList.add('hidden'));

/* ---------- Tab 2: Trade Interest ---------- */
async function loadInterest() {
  try {
    const res = await fetch('/api/trade_block/interest');
    const data = await res.json();
    const list = data.interest || [];
    const host = document.getElementById('interest-list');
    const badge = document.getElementById('interest-badge');
    badge.textContent = list.length || '';
    host.innerHTML = list.length ? '' : '<div class="block-empty">No AI interest yet. Add players to your block and hit “Generate Interest”.</div>';
    for (const r of list) {
      const el = document.createElement('div');
      el.className = 'tb-interest-row';
      el.innerHTML = `
        <div><b>${esc(r.player)}</b>
          <span class="dim">— ${esc(r.team)} interested (${esc(r.interest)})</span></div>
        <div class="tb-row-btns">
          <button class="tb-mini" data-neg="${esc(r.player)}">Negotiate</button>
          <button class="tb-mini tb-danger" data-decline="${esc(r.player)}" data-team="${esc(r.team)}">Decline</button>
        </div>`;
      host.appendChild(el);
    }
  } catch (e) { console.error(e); }
}
document.getElementById('interest-list').addEventListener('click', async e => {
  const neg = e.target.closest('[data-neg]');
  const dec = e.target.closest('[data-decline]');
  if (neg) { location.href = '/trades'; return; }
  if (dec) {
    await fetch('/api/trade_block/decline_interest', { method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ player: dec.dataset.decline, team: dec.dataset.team }) });
    setTimeout(loadInterest, 600);
  }
});

/* ---------- Tab 3: Other Teams ---------- */
async function loadOthers() {
  try {
    const res = await fetch('/api/trade_block/others');
    const data = await res.json();
    const grid = document.getElementById('others-grid');
    const players = data.players || [];
    grid.innerHTML = players.length ? '' : '<div class="block-empty">No other teams have players on the block right now.</div>';
    for (const p of players) {
      const el = document.createElement('div');
      el.className = 'block-card';
      el.innerHTML = `
        <div class="b-head">
          <div class="b-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
          <div>
            <div class="b-name">${esc(p.player)}</div>
            <div><span class="b-team">${esc(p.team)}</span></div>
          </div>
        </div>
        <div class="b-sub">${esc(p.position)}</div>
        <div class="b-row-actions">
          <button class="tb-mini" data-exp="${esc(p.player_id)}" data-pn="${esc(p.player)}" data-tm="${esc(p.team)}">Express Interest</button>
          <button class="tb-mini" data-trade="${esc(p.team)}">Negotiate</button>
        </div>`;
      grid.appendChild(el);
    }
  } catch (e) { console.error(e); }
}
document.getElementById('others-grid').addEventListener('click', async e => {
  const ex = e.target.closest('[data-exp]');
  const tr = e.target.closest('[data-trade]');
  if (ex) {
    await fetch('/api/trade_block/express_interest', { method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ player_id: ex.dataset.exp, player: ex.dataset.pn, team: ex.dataset.tm }) });
    alert('Interest recorded.');
  }
  if (tr) location.href = '/trades?team=' + encodeURIComponent(tr.dataset.trade);
});

loadMine();

/* Shared heartbeat */
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, label')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
