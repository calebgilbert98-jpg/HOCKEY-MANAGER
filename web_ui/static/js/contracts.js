/* Puck Dynasty web contracts */
async function loadContracts() {
  try {
    const res = await fetch('/api/contracts');
    const data = await res.json();
    renderContracts(data.contracts || [], data.summary || {});
  } catch (e) { console.error(e); }
}

function salaryStr(s) {
  s = s || 0;
  return s >= 1e6 ? '$' + (s / 1e6).toFixed(2) + 'M'
                  : '$' + Math.round(s / 1e3) + 'K';
}

function termStr(years) {
  if (years <= 0) return 'Expiring / signed out';
  return years + (years === 1 ? ' yr' : ' yrs') + ' left';
}

function renderContracts(contracts, summary) {
  const list = document.getElementById('contracts-list');
  const n = summary.player_count != null ? summary.player_count : contracts.length;
  document.getElementById('contracts-count').textContent =
    n + (n === 1 ? ' player' : ' players') + ' under contract';
  const capLine = document.getElementById('cap-line');
  if (summary.cap_ceiling) {
    const used = summary.total_cap_hit || 0;
    const pct = Math.round(used / summary.cap_ceiling * 100);
    capLine.textContent =
      `Cap hit: ${salaryStr(used)} / ${salaryStr(summary.cap_ceiling)} (${pct}% used)`;
  }
  list.innerHTML = '';
  if (!contracts.length) {
    const el = document.createElement('div');
    el.className = 'contracts-empty';
    el.textContent = 'No contracts on the roster.';
    list.appendChild(el);
    return;
  }
  for (const c of contracts) {
    const el = document.createElement('div');
    el.className = 'c-row' + (c.expiring ? ' expiring' : '');
    const clauses = [];
    if (c.no_movement) clauses.push('NMC');
    if (c.no_trade) clauses.push('NTC');
    if (c.two_way) clauses.push('2-way');
    el.innerHTML = `
      <div class="c-name">${esc(c.name)}${clauses.length ? ' <span class="c-clause">' + clauses.map(esc).join(' · ') + '</span>' : ''}</div>
      <div class="c-pos">${esc(c.position)} · Age ${c.age}</div>
      <div class="c-hit">${salaryStr(c.cap_hit)}</div>
      <div class="c-term${c.expiring ? ' hot' : ''}">${esc(termStr(c.years_remaining))}${c.expiring ? ' ⚠' : ''}</div>
      <button class="btn-extend" data-id="${esc(c.id)}">Extend</button>`;
    const btn = el.querySelector('.btn-extend');
    btn.addEventListener('click', () => extendContract(btn, c.id, c.name));
    list.appendChild(el);
  }
}

async function extendContract(btn, playerId, name) {
  btn.disabled = true;
  btn.textContent = 'Extending…';
  try {
    const res = await fetch('/api/contracts/extend', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: playerId})
    });
    const data = await res.json();
    if (data.ok) {
      btn.textContent = 'Extension queued ✓';
    } else {
      btn.textContent = 'Extend';
      btn.disabled = false;
      alert('Could not queue extension: ' + (data.error || 'unknown error'));
    }
  } catch (e) {
    console.error(e);
    btn.textContent = 'Extend';
    btn.disabled = false;
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadContracts();
