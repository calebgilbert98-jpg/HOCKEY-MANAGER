/* Puck Dynasty web waiver wire */
async function loadWire() {
  try {
    const res = await fetch('/api/waivers');
    const data = await res.json();
    renderWire(data.players || []);
  } catch (e) { console.error(e); }
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

function deadlineStr(days) {
  if (days <= 0) return 'Expires today';
  return days + (days === 1 ? ' day left' : ' days left');
}

function renderWire(players) {
  const list = document.getElementById('wire-list');
  document.getElementById('wire-count').textContent =
    players.length + (players.length === 1 ? ' player' : ' players') + ' on waivers';
  list.innerHTML = '';
  if (!players.length) {
    const el = document.createElement('div');
    el.className = 'wire-empty';
    el.textContent = 'The waiver wire is empty.';
    list.appendChild(el);
    return;
  }
  for (const p of players) {
    const el = document.createElement('div');
    el.className = 'wire-card';
    el.innerHTML = `
      <div class="w-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
      <div class="w-info">
        <div class="w-name">${esc(p.name)}</div>
        <div class="w-sub">${esc(p.position)} · Age ${p.age} · ${salaryStr(p.salary)}${p.waiver_team ? ' · from ' + esc(p.waiver_team) : ''}</div>
      </div>
      <div class="w-clock">⏱ ${esc(deadlineStr(p.waiver_days))}</div>
      <button class="btn-claim" data-id="${esc(p.id)}" data-name="${esc(p.name)}">Claim</button>`;
    const btn = el.querySelector('.btn-claim');
    btn.addEventListener('click', () => claimWaiver(btn, p.id, p.name));
    list.appendChild(el);
  }
}

async function claimWaiver(btn, playerId, name) {
  btn.disabled = true;
  btn.textContent = 'Claiming…';
  try {
    const res = await fetch('/api/waivers/claim', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: playerId}),
    });
    const data = await res.json();
    if (data.ok) {
      btn.textContent = 'Claimed ✓';
    } else {
      btn.textContent = 'Claim';
      btn.disabled = false;
      console.error('claim failed:', data);
    }
  } catch (e) {
    console.error(e);
    btn.textContent = 'Claim';
    btn.disabled = false;
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadWire();
