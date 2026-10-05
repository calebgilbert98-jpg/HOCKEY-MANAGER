/* Puck Dynasty web scouting */
async function loadScouting() {
  try {
    const res = await fetch('/api/scouting');
    const data = await res.json();
    renderAssignments(data.assignments || []);
    renderReports(data.reports || []);
    fillForm(data.scouts || [], data.prospects || []);
    document.getElementById('scout-count').textContent =
      data.assignment_count + ' active assignment' + (data.assignment_count === 1 ? '' : 's');
  } catch (e) { console.error(e); }
}

function renderAssignments(items) {
  const grid = document.getElementById('assign-grid');
  grid.innerHTML = '';
  if (!items.length) {
    grid.innerHTML = '<div class="empty">No active assignments. Send a scout out with the button above.</div>';
    return;
  }
  for (const a of items) {
    const p = a.player || {}, s = a.scout || {}, r = a.report || {};
    const el = document.createElement('div');
    el.className = 'assign-card';
    const acc = (r.accuracy || '?').toLowerCase();
    el.innerHTML = `
      <div class="a-player">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile">${esc(p.name)}</span>` : esc(p.name)}</div>
      <div class="a-meta">${esc(p.position)} · ${p.age || '?'} yrs · OVR ${p.overall || '?'}</div>
      <div class="a-scout">Scout: ${s.id ? `<span class="clickable-text" data-href="/staff/${esc(s.id)}" title="Open staff profile"><b>${esc(s.name)}</b></span>` : `<b>${esc(s.name)}</b>`} <span>(${esc(s.role)})</span></div>
      <div class="a-progress">
        <span class="acc ${acc}">${esc(r.accuracy || '?')}</span>
        <span class="a-detail">${r.viewings || 0} viewings · ${esc(r.region || '')} · ${r.reliability != null ? Math.round(r.reliability * 100) + '% reliable' : ''}</span>
      </div>`;
    grid.appendChild(el);
  }
}

function renderReports(items) {
  const list = document.getElementById('report-list');
  list.innerHTML = '';
  if (!items.length) {
    list.innerHTML = '<div class="empty">No scouting reports yet.</div>';
    return;
  }
  for (const r of items) {
    const el = document.createElement('div');
    el.className = 'report-row';
    const done = (r.accuracy || '').toUpperCase() === 'A';
    el.innerHTML = `
      <span class="acc ${(r.accuracy || 'f').toLowerCase()}">${esc(r.accuracy)}</span>
      <div class="r-name">${esc(r.player_name)}
        <small>${esc(r.player_position)} · scouted by ${esc(r.scout_name)}</small>
      </div>
      <div class="r-region">${esc(r.region)}${r.competition && r.competition !== 'Unknown' ? ' · ' + esc(r.competition) : ''}</div>
      <div class="r-pot">${r.scouted_potential ? 'Potential: ' + esc(r.scouted_potential) : ''}</div>
      ${done ? '<span class="r-done">COMPLETE</span>' : ''}`;
    list.appendChild(el);
  }
}

function fillForm(scouts, prospects) {
  const ps = document.getElementById('prospect-sel');
  const ss = document.getElementById('scout-sel');
  ps.innerHTML = prospects.map(p =>
    `<option value="${esc(p.id)}">${esc(p.name)} — ${esc(p.position)}, OVR ${p.overall}</option>`).join('')
    || '<option value="">No prospects available</option>';
  ss.innerHTML = scouts.map(s =>
    `<option value="${esc(s.id)}">${esc(s.name)} (${esc(s.role)})</option>`).join('')
    || '<option value="">No scouts on staff</option>';
}

document.getElementById('new-btn').addEventListener('click', () => {
  document.getElementById('modal').classList.remove('hidden');
  document.getElementById('assign-msg').textContent = '';
});
document.getElementById('cancel-btn').addEventListener('click', () => {
  document.getElementById('modal').classList.add('hidden');
});
document.getElementById('assign-btn').addEventListener('click', async () => {  const prospectId = document.getElementById('prospect-sel').value;
  const scoutId = document.getElementById('scout-sel').value;
  const msg = document.getElementById('assign-msg');
  if (!prospectId || !scoutId) {
    msg.textContent = 'Pick both a prospect and a scout.'; msg.className = 'err'; return;
  }
  try {
    const res = await fetch('/api/scouting/assignment', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prospect_id: prospectId, scout_id: scoutId}),
    });
    const data = await res.json();
    if (data.ok) {
      msg.textContent = 'Assignment queued — it takes effect on the game thread.'; msg.className = 'ok';
      setTimeout(() => { document.getElementById('modal').classList.add('hidden'); loadScouting(); }, 900);
    } else {
      msg.textContent = 'Failed: ' + (data.error || 'unknown error'); msg.className = 'err';
    }
  } catch (e) { msg.textContent = 'Request failed: ' + e; msg.className = 'err'; }
});

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

/* ---- Regional beats (real assignment flow) ---- */
async function loadBeats() {
  try {
    const res = await fetch('/api/scouting/options');
    const data = await res.json();
    renderBeats(data.scouts || []);
    fillBeatForm(data);
  } catch (e) { console.error(e); }
}

function renderBeats(scouts) {
  const grid = document.getElementById('beat-grid');
  grid.innerHTML = '';
  if (!scouts.length) {
    grid.innerHTML = '<div class="empty">No scouts on staff. Hire scouts via Staff to cover regions.</div>';
    return;
  }
  for (const s of scouts) {
    const el = document.createElement('div');
    el.className = 'beat-card' + (s.current_region ? '' : ' beat-idle');
    el.innerHTML = `
      <div class="a-player">${esc(s.name)}</div>
      <div class="a-meta">${esc(s.role)} · ability ${s.judging_ability} · potential ${s.judging_potential}</div>
      <div class="beat-region">${s.current_region ? '📍 ' + esc(s.current_region) : '<i>Unassigned</i>'}</div>`;
    grid.appendChild(el);
  }
}

function fillBeatForm(data) {
  const ss = document.getElementById('beat-scout-sel');
  const rs = document.getElementById('beat-region-sel');
  const scouts = data.scouts || [];
  ss.innerHTML = scouts.map(s =>
    `<option value="${esc(s.id)}">${esc(s.name)} (${esc(s.role)})${s.current_region ? ' — ' + esc(s.current_region) : ''}</option>`
  ).join('') || '<option value="">No scouts on staff</option>';
  const opt = r => `<option value="${esc(r)}">${esc(r)}</option>`;
  const am = (data.amateur_regions || []).map(opt).join('');
  const pro = (data.pro_leagues || []).map(opt).join('');
  rs.innerHTML =
    (am ? `<optgroup label="Amateur regions">${am}</optgroup>` : '') +
    (pro ? `<optgroup label="Pro leagues">${pro}</optgroup>` : '') +
    (!(am || pro) ? (data.regions || []).map(opt).join('') : '');
}

async function submitBeat(recall) {
  const scoutId = document.getElementById('beat-scout-sel').value;
  const region = recall ? '' : document.getElementById('beat-region-sel').value;
  const msg = document.getElementById('beat-msg');
  if (!scoutId) { msg.textContent = 'Pick a scout first.'; msg.className = 'err'; return; }
  try {
    const res = await fetch('/api/scouting/assign', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scout_id: scoutId, region: region}),
    });
    const data = await res.json();
    if (data.ok) {
      msg.textContent = (data.message || 'Done') + ' Takes effect on the game thread.';
      msg.className = 'ok';
      setTimeout(() => { document.getElementById('beat-modal').classList.add('hidden'); loadBeats(); }, 900);
    } else {
      msg.textContent = 'Failed: ' + (data.error || 'unknown error'); msg.className = 'err';
    }
  } catch (e) { msg.textContent = 'Request failed: ' + e; msg.className = 'err'; }
}

document.getElementById('beat-btn').addEventListener('click', () => {
  document.getElementById('beat-modal').classList.remove('hidden');
  document.getElementById('beat-msg').textContent = '';
});
document.getElementById('beat-cancel-btn').addEventListener('click', () => {
  document.getElementById('beat-modal').classList.add('hidden');
});
document.getElementById('beat-assign-btn').addEventListener('click', () => submitBeat(false));
document.getElementById('beat-recall-btn').addEventListener('click', () => submitBeat(true));

loadScouting();
loadBeats();

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
