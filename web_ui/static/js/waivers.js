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
        <div class="w-name">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile">${esc(p.name)}</span>` : esc(p.name)}</div>
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
loadEligible();

function loadEligible() {
  fetch('/api/waivers/eligible')
    .then(r => r.json())
    .then(d => renderEligible(d.players || []))
    .catch(e => console.error(e));
}

function renderEligible(players) {
  const list = document.getElementById('eligible-list');
  list.innerHTML = '';
  if (!players.length) {
    const el = document.createElement('div');
    el.className = 'wire-empty';
    el.textContent = 'No waiver-eligible players on your roster.';
    list.appendChild(el);
    return;
  }
  players.sort((a, b) => (b.overall || 0) - (a.overall || 0));
  for (const p of players) {
    const el = document.createElement('div');
    el.className = 'wire-card';
    const clauseTag = p.nmc_block ? ' <span class="w-clause bad">NMC</span>'
      : (p.clause === 'NTC' ? ' <span class="w-clause">NTC</span>' : '');
    const exemptTag = p.waiver_exempt ? ' <span class="w-exempt">exempt — demotes freely</span>' : '';
    el.innerHTML = `
      <div class="w-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
      <div class="w-info">
        <div class="w-name">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile">${esc(p.name)}</span>` : esc(p.name)}${clauseTag}</div>
        <div class="w-sub">${esc(p.position)} · Age ${p.age} · ${salaryStr(p.salary)}${exemptTag}</div>
      </div>
      <button class="btn-waive" data-id="${esc(p.id)}" data-name="${esc(p.name)}" ${p.nmc_block ? 'disabled title="No-movement clause blocks waiver placement"' : ''}>${p.waiver_exempt ? 'Demote' : 'Waive'}</button>`;
    const btn = el.querySelector('.btn-waive');
    btn.addEventListener('click', () => placeOnWaivers(btn, p.id, p.name, !!p.waiver_exempt));
    list.appendChild(el);
  }
}

async function placeOnWaivers(btn, playerId, name, exempt) {
  if (exempt) {
    // Waiver-exempt players skip the wire: demote straight to the AHL
    // (same destination as the desktop's waive-and-assign).
    if (!confirm(`Send ${name} to the AHL? He is waiver-exempt and clears freely.`)) return;
    btn.disabled = true;
    btn.textContent = 'Sending…';
    try {
      const res = await fetch('/api/roster/move', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({player_ids: [playerId], from: 'nhl', to: 'ahl'}),
      });
      const data = await res.json();
      if (data.ok !== false) {
        btn.textContent = 'Sent ✓';
        loadEligible();
      } else {
        btn.textContent = 'Demote';
        btn.disabled = false;
        alert('Could not demote: ' + (data.error || 'unknown error'));
      }
    } catch (e) {
      console.error(e);
      btn.textContent = 'Demote';
      btn.disabled = false;
    }
    return;
  }
  if (!confirm(`Place ${name} on waivers? Other teams will have a chance to claim him (2-day wire).`)) return;
  btn.disabled = true;
  btn.textContent = 'Waiving…';
  try {
    const res = await fetch('/api/waivers/place', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: playerId}),
    });
    const data = await res.json();
    if (data.ok) {
      btn.textContent = 'On Waivers ✓';
      loadEligible();
      loadWire();
    } else {
      btn.textContent = 'Waive';
      btn.disabled = false;
      alert('Could not place on waivers: ' + (data.error || 'unknown error'));
    }
  } catch (e) {
    console.error(e);
    btn.textContent = 'Waive';
    btn.disabled = false;
  }
}

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
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
