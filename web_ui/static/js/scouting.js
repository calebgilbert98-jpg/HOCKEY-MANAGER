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
      <div class="a-player">${esc(p.name)}</div>
      <div class="a-meta">${esc(p.position)} · ${p.age || '?'} yrs · OVR ${p.overall || '?'}</div>
      <div class="a-scout">Scout: <b>${esc(s.name)}</b> <span>(${esc(s.role)})</span></div>
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
document.getElementById('assign-btn').addEventListener('click', async () => {
  const prospectId = document.getElementById('prospect-sel').value;
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

loadScouting();
