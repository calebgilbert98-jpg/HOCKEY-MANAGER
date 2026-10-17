/* Puck Dynasty web roster — 5-tab club management */
const state = {
  tab: 'nhl',
  players: [],
  counts: {},
  sortCol: 'overall',
  sortDir: -1,
  filters: {pos: 'All', age: 'All', ovr: 'All', search: ''},
  selected: new Set(),
};

const COLUMNS = [
  {id: 'sel', label: '', sortable: false},
  {id: 'jersey', label: '#', sortable: true},
  {id: 'name', label: 'Name', sortable: true},
  {id: 'position', label: 'Pos', sortable: true},
  {id: 'age', label: 'Age', sortable: true},
  {id: 'tier', label: 'Tier', sortable: true},
  {id: 'potential', label: 'Pot', sortable: true},
  {id: 'salary_fmt', label: 'Salary', sortable: true, sortKey: 'salary'},
  {id: 'contract_years', label: 'Yrs', sortable: true},
  {id: 'morale_100', label: 'Morale', sortable: true},
  {id: 'health', label: 'Health', sortable: false},
];

const BULK_ACTIONS = {
  nhl: [
    {label: 'Send to AHL', to: 'ahl', cls: 'secondary'},
    {label: 'Edit Lines', href: '/lines', cls: 'primary'},
  ],
  ahl: [
    {label: 'Call Up', to: 'nhl', cls: 'primary'},
    {label: 'Return to Junior', to: 'prospects', cls: 'secondary'},
  ],
  prospects: [
    {label: 'Promote to AHL', to: 'ahl', cls: 'primary'},
  ],
};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function moraleLabel(v) {
  if (v >= 80) return 'Elated';
  if (v >= 60) return 'Happy';
  if (v >= 40) return 'Content';
  if (v >= 20) return 'Unhappy';
  return 'Angry';
}

/* ---------- tab switching ---------- */
document.getElementById('roster-tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-tab]');
  if (!btn) return;
  document.querySelectorAll('#roster-tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.tab = btn.dataset.tab;
  state.selected.clear();
  showView();
});

function showView() {
  for (const v of ['table', 'depth', 'cap'])
    document.getElementById('view-' + v).classList.toggle('hidden', v !== viewForTab());
  if (state.tab === 'depth') loadDepth();
  else if (state.tab === 'cap') loadCap();
  else loadTab();
}

function viewForTab() {
  return state.tab === 'depth' ? 'depth' : state.tab === 'cap' ? 'cap' : 'table';
}

/* ---------- roster tables ---------- */
async function loadTab() {
  try {
    const res = await fetch('/api/roster?tab=' + state.tab);
    const data = await res.json();
    state.players = data.players || [];
    state.counts = data.counts || {};
    document.getElementById('cnt-nhl').textContent = `(${state.counts.nhl ?? ''})`;
    document.getElementById('cnt-ahl').textContent = `(${state.counts.ahl ?? ''})`;
    document.getElementById('cnt-prospects').textContent = `(${state.counts.prospects ?? ''})`;
    document.getElementById('roster-headline').textContent =
      `${state.counts.nhl ?? 0}/23 NHL · ${state.counts.ahl ?? 0} AHL · ${state.counts.prospects ?? 0} Prospects`;
    renderBulkActions();
    renderTable();
  } catch (e) { console.error(e); }
}

function filteredPlayers() {
  const f = state.filters;
  return state.players.filter(p => {
    if (f.pos !== 'All') {
      const g = p.position === 'G' ? 'G' : (p.position === 'D' || p.position.startsWith('L') && p.position.includes('D') || p.position === 'LD' || p.position === 'RD') ? 'D' : 'F';
      const pg = p.position === 'G' ? 'G' : (['D', 'LD', 'RD'].includes(p.position) ? 'D' : 'F');
      if (pg !== f.pos) return false;
    }
    if (f.age === 'U23' && p.age >= 23) return false;
    if (f.age === '23-29' && (p.age < 23 || p.age > 29)) return false;
    if (f.age === '30+' && p.age < 30) return false;
    if (f.ovr !== 'All' && p.overall < parseInt(f.ovr)) return false;
    if (f.search && !p.name.toLowerCase().includes(f.search.toLowerCase())) return false;
    return true;
  });
}

function renderTable() {
  const head = document.getElementById('roster-head');
  head.innerHTML = COLUMNS.map(c => {
    if (c.id === 'sel') return `<th><input type="checkbox" id="sel-all"></th>`;
    const arrow = state.sortCol === (c.sortKey || c.id) ? (state.sortDir === 1 ? ' ▲' : ' ▼') : '';
    return `<th data-col="${c.sortKey || c.id}" class="${c.sortable ? 'sortable' : ''}">${esc(c.label)}${arrow}</th>`;
  }).join('');
  head.querySelectorAll('th.sortable').forEach(th =>
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (state.sortCol === col) state.sortDir *= -1;
      else { state.sortCol = col; state.sortDir = -1; }
      renderTable();
    }));
  const selAll = document.getElementById('sel-all');
  if (selAll) selAll.addEventListener('change', () => {
    state.selected.clear();
    if (selAll.checked) filteredPlayers().forEach(p => state.selected.add(p.id));
    renderTable();
  });

  const rows = filteredPlayers().sort((a, b) => {
    const k = state.sortCol;
    const av = a[k], bv = b[k];
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * state.sortDir;
    return String(av ?? '').localeCompare(String(bv ?? '')) * state.sortDir;
  });

  const body = document.getElementById('roster-body');
  body.innerHTML = rows.map(p => {
    const checked = state.selected.has(p.id) ? 'checked' : '';
    const health = (p.health || []).map(h =>
      `<span class="badge badge-${h.toLowerCase()}">${esc(h)}</span>`).join(' ');
    const cap = p.captaincy ? ` <span class="p-c">${esc(p.captaincy)}</span>` : '';
    const ntc = [p.ntc ? 'NTC' : '', p.nmc ? 'NMC' : ''].filter(Boolean).join(' ');
    const face = p.portrait
      ? `<img class="p-portrait" src="${esc(p.portrait)}" alt="" loading="lazy" onerror="this.remove()">`
      : '';
    return `<tr data-id="${esc(p.id)}" class="${p.injured ? 'injured' : ''}">
      <td><input type="checkbox" class="row-sel" data-id="${esc(p.id)}" ${checked}></td>
      <td class="jersey-cell" data-id="${esc(p.id)}" data-jersey="${esc(p.jersey)}" data-name="${esc(p.name)}" title="Click to change jersey number">#${esc(p.jersey)}</td>
      <td class="p-name clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile" data-id="${esc(p.id)}">${face}<span>${esc(p.name)}${cap}</span></td>
      <td>${esc(p.position)}</td>
      <td>${p.age}</td>
      <td><span class="tier">${esc(p.tier)}</span></td>
      <td>${p.potential}</td>
      <td>${esc(p.salary_fmt)}${ntc ? ` <span class="clause">${ntc}</span>` : ''}</td>
      <td>${p.contract_years || (p.has_contract ? '?' : '—')}</td>
      <td title="${moraleLabel(p.morale_100)}">${p.morale_100}</td>
      <td>${health}</td>
    </tr>`;
  }).join('');

  body.querySelectorAll('.row-sel').forEach(cb =>
    cb.addEventListener('change', () => {
      if (cb.checked) state.selected.add(cb.dataset.id);
      else state.selected.delete(cb.dataset.id);
      renderSummary();
    }));
  body.querySelectorAll('.p-name').forEach(td => {
    td.addEventListener('click', () => openProfile(td.dataset.id));
    td.addEventListener('contextmenu', e => { e.preventDefault(); openCtxMenu(e, td.dataset.id); });
  });
  body.querySelectorAll('.jersey-cell').forEach(td => {
    td.addEventListener('click', e => {
      e.stopPropagation();
      editJerseyNumber(td);
    });
  });
  renderSummary();
}

async function editJerseyNumber(td) {
  const pid = td.dataset.id;
  const name = td.dataset.name || 'player';
  const cur = parseInt(td.dataset.jersey) || 0;
  const raw = prompt(`Enter a new jersey number for ${name} (current #${cur}):\nRetired numbers stay retired; goalie numbers stay with goalies; duplicates blocked.`, String(cur));
  if (raw === null) return;
  const n = parseInt(String(raw).trim());
  if (!n || n < 1 || n > 98) { alert('Numbers run 1-98.'); return; }
  if (n === cur) return;
  td.textContent = '…';
  try {
    const res = await fetch('/api/jersey_numbers/set', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: pid, number: n}),
    });
    const data = await res.json();
    if (data.ok) {
      loadTab();  // refresh the table from live state
    } else {
      alert('Could not change jersey number: ' + (data.error || 'unknown error'));
      td.textContent = '#' + cur;
    }
  } catch (e) {
    console.error(e);
    alert('Request failed.');
    td.textContent = '#' + cur;
  }
}

function renderSummary() {
  const n = state.selected.size;
  const total = filteredPlayers().length;
  document.getElementById('roster-summary').textContent =
    n ? `${n} selected` : `${total} players`;
}

function renderBulkActions() {
  const host = document.getElementById('bulk-actions');
  const actions = BULK_ACTIONS[state.tab] || [];
  host.innerHTML = actions.map((a, i) =>
    a.href ? `<a class="btn ${a.cls}" href="${a.href}">${esc(a.label)}</a>`
           : `<button class="btn ${a.cls}" data-i="${i}">${esc(a.label)}</button>`
  ).join('');
  host.querySelectorAll('button').forEach(btn =>
    btn.addEventListener('click', () => {
      const a = actions[parseInt(btn.dataset.i)];
      bulkMove(a.to);
    }));
}

async function bulkMove(to) {
  const ids = [...state.selected];
  if (!ids.length) { alert('Select players first.'); return; }
  if (!confirm(`Move ${ids.length} player(s) to ${to.toUpperCase()}?`)) return;
  try {
    const res = await fetch('/api/roster/move', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_ids: ids, from: state.tab, to}),
    });
    const data = await res.json();
    if (!data.ok) { alert('Move failed to queue.'); return; }
    // Poll for the result (executes on the Tk main thread)
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 500));
      const rr = await fetch('/api/roster/move_result');
      const result = await rr.json();
      if (result.moved || (result.errors && result.errors.length)) {
        if (result.errors.length) alert('Some moves blocked:\n' + result.errors.join('\n'));
        else if (result.moved) { /* success, silent refresh */ }
        break;
      }
    }
    state.selected.clear();
    loadTab();
  } catch (e) { console.error(e); alert('Move failed.'); }
}

/* ---------- filters ---------- */
for (const [gid, key] of [['f-pos', 'pos'], ['f-age', 'age'], ['f-ovr', 'ovr']]) {
  document.getElementById(gid).addEventListener('click', e => {
    const btn = e.target.closest('button[data-v]');
    if (!btn) return;
    document.querySelectorAll(`#${gid} button`).forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.filters[key] = btn.dataset.v;
    renderTable();
  });
}
document.getElementById('f-search').addEventListener('input', e => {
  state.filters.search = e.target.value;
  renderTable();
});

/* ---------- depth chart ---------- */
async function loadDepth() {
  try {
    const res = await fetch('/api/roster/depth');
    const data = await res.json();
    const host = document.getElementById('depth-units');
    host.innerHTML = (data.units || []).map(u => `
      <div class="depth-unit">
        <h3>${esc(u.label || u.group)}</h3>
        <div class="depth-slots">
          ${(u.slots || []).map(s => s.player ? `
            <div class="depth-slot" data-id="${esc(s.player.id)}">
              <div class="slot-pos">${esc(s.slot)}</div>
              <div class="slot-name">${esc(s.player.name)}</div>
              <div class="slot-sub">${esc(s.player.position)} · ${s.player.overall} OVR</div>
            </div>` : `
            <div class="depth-slot empty"><div class="slot-pos">${esc(s.slot)}</div><div class="slot-name">Empty</div></div>`
          ).join('')}
        </div>
      </div>`).join('') || '<p>No lines set. <a href="/lines">Edit lines →</a></p>';
    host.querySelectorAll('.depth-slot[data-id]').forEach(el =>
      el.addEventListener('click', () => openProfile(el.dataset.id)));
  } catch (e) { console.error(e); }
}

/* ---------- salary cap ---------- */
async function loadCap() {
  try {
    const res = await fetch('/api/roster/cap');
    const d = await res.json();
    document.getElementById('cap-overview').innerHTML = `
      <div class="cap-bar-row"><span>Cap usage</span><strong>${d.pct}%</strong></div>
      <div class="cap-bar"><span style="width:${Math.min(100, d.pct)}%"></span></div>
      <div class="cap-grid">
        <div><label>Salary Cap</label><strong>${esc(d.cap_fmt)}</strong></div>
        <div><label>Payroll</label><strong>${esc(d.payroll_fmt)}</strong></div>
        <div><label>Cap Space</label><strong class="${d.space < 0 ? 'neg' : 'pos'}">${esc(d.space_fmt)}</strong></div>
        ${d.dead_cap ? `<div><label>Dead Cap</label><strong>${esc(d.dead_fmt)}</strong></div>` : ''}
      </div>`;
    document.getElementById('cap-body').innerHTML = (d.contracts || []).map(c => `
      <tr><td>${esc(c.name)}</td><td>${esc(c.position)}</td>
      <td>${esc(c.salary_fmt)}</td><td>${c.years}</td>
      <td>${[c.ntc ? 'NTC' : '', c.nmc ? 'NMC' : ''].filter(Boolean).join(' ')}</td></tr>`
    ).join('');
  } catch (e) { console.error(e); }
}

/* ---------- player profile modal ---------- */
async function openProfile(pid) {
  try {
    const res = await fetch('/api/roster/player/' + encodeURIComponent(pid));
    if (!res.ok) return;
    const p = await res.json();
    const attrs = p.attributes || {};
    const attrBars = Object.entries(attrs).map(([k, v]) => `
      <div class="attr-row"><span>${esc(k.replace(/_/g, ' '))}</span>
      <div class="attr-bar"><span style="width:${v}%;background:${barColor(v)}"></span></div>
      <strong>${v}</strong></div>`).join('');
    document.getElementById('profile-card').innerHTML = `
      <button class="modal-x" id="profile-x">✕</button>
      <h2>${esc(p.name)} ${p.captaincy ? `<span class="p-c">${esc(p.captaincy)}</span>` : ''}</h2>
      <div class="p-sub">${esc(p.position)} · Age ${p.age} · #${esc(p.jersey)} · ${esc(p.tier)} (${p.overall} OVR)</div>
      <div class="p-facts">
        <div><label>Salary</label><strong>${esc(p.salary_fmt)}</strong></div>
        <div><label>Contract</label><strong>${p.contract_years} yr${p.contract_years === 1 ? '' : 's'}</strong></div>
        <div><label>Morale</label><strong>${moraleLabel(p.morale_100)} (${p.morale_100})</strong></div>
        <div><label>Health</label><strong>${(p.health || []).join(', ') || 'Healthy'}</strong></div>
      </div>
      ${attrBars ? `<h3>Attributes</h3><div class="attr-list">${attrBars}</div>` : ''}
      <div class="profile-actions">
        <button class="btn secondary" id="pa-trade">Add to Trade Block</button>
        <button class="btn secondary" id="pa-extend">Contract Extension</button>
      </div>`;
    document.getElementById('profile-modal').classList.remove('hidden');
    document.getElementById('profile-x').onclick = closeProfile;
    document.getElementById('profile-modal').onclick = e => {
      if (e.target.id === 'profile-modal') closeProfile();
    };
    document.getElementById('pa-trade').onclick = () => {
      fetch('/api/command', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'trade_block_add', player_id: p.id})});
      closeProfile();
    };
    document.getElementById('pa-extend').onclick = () => {
      window.location = '/contracts?player=' + encodeURIComponent(p.id);
    };
  } catch (e) { console.error(e); }
}

function closeProfile() {
  document.getElementById('profile-modal').classList.add('hidden');
}

function barColor(v) {
  if (v >= 75) return '#4CAF50';
  if (v >= 60) return '#8BC34A';
  if (v >= 45) return '#FFC107';
  if (v >= 30) return '#FF9800';
  return '#F44336';
}

/* ---------- context menu ---------- */
function openCtxMenu(e, pid) {
  const menu = document.getElementById('ctx-menu');
  const p = state.players.find(x => x.id === pid);
  if (!p) return;
  const items = [
    ['View Profile', () => openProfile(pid)],
    ['Add to Trade Block', () => fetch('/api/command', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({op: 'trade_block_add', player_id: pid})})],
    ['Contract Extension', () => window.location = '/contracts?player=' + encodeURIComponent(pid)],
  ];
  // Roster-specific moves
  if (state.tab === 'nhl') items.push(['Send to AHL', () => quickMove([pid], 'nhl', 'ahl')]);
  if (state.tab === 'ahl') items.push(['Call Up to NHL', () => quickMove([pid], 'ahl', 'nhl')]);
  if (state.tab === 'prospects' && !p.has_contract) items.push(['Offer ELC…', () => window.location = '/contracts?player=' + encodeURIComponent(pid) + '&elc=1']);
  if (state.tab === 'prospects' && p.has_contract) items.push(['Promote to AHL', () => quickMove([pid], 'prospects', 'ahl')]);

  menu.innerHTML = items.map((it, i) => `<button data-i="${i}">${esc(it[0])}</button>`).join('');
  menu.style.left = Math.min(e.clientX, window.innerWidth - 200) + 'px';
  menu.style.top = e.clientY + 'px';
  menu.classList.remove('hidden');
  menu.querySelectorAll('button').forEach(btn =>
    btn.addEventListener('click', () => { menu.classList.add('hidden'); items[parseInt(btn.dataset.i)][1](); }));
  const close = ev => {
    if (!menu.contains(ev.target)) { menu.classList.add('hidden'); document.removeEventListener('click', close); }
  };
  setTimeout(() => document.addEventListener('click', close), 10);
}

async function quickMove(ids, from, to) {
  try {
    await fetch('/api/roster/move', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_ids: ids, from, to})});
    setTimeout(loadTab, 1500);
  } catch (e) { console.error(e); }
}

/* ---------- init ---------- */
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeProfile(); });
showView();

(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, .row-sel')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});

/* ---- Batch B: captaincy-crisis banner (resolution UI lives on /morale) ---- */
async function loadRosterCrisisBanner() {
  const host = document.getElementById('roster-crisis-banner');
  if (!host) return;
  try {
    const res = await fetch('/api/morale/crisis');
    const d = await res.json();
    const c = d.crisis;
    if (!c) { host.classList.add('hidden'); return; }
    const sev = '🔴'.repeat(Math.max(1, c.severity || 1));
    host.innerHTML = `
      <div class="crisis-head">${sev} <strong>Captaincy crisis:</strong>
        ${String(c.captain_name).replace(/[&<>"]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))} is losing the room.</div>
      <a class="btn secondary" href="/morale" style="text-decoration:none">Open the dressing room to resolve it</a>`;
    host.classList.remove('hidden');
  } catch (e) { /* banner stays hidden */ }
}
loadRosterCrisisBanner();
