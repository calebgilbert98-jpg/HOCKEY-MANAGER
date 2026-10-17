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
      </div>
      <div class="a-actions">
        <button class="btn-new cancel-assign" data-pid="${esc(p.id || '')}">Cancel assignment</button>
      </div>`;
    grid.appendChild(el);
  }
}

/* Cancel a live assignment (desktop right-click -> Cancel Assignment). */
document.getElementById('assign-grid').addEventListener('click', async (e) => {
  const btn = e.target.closest('.cancel-assign');
  if (!btn || !btn.dataset.pid) return;
  if (!confirm('Stop scouting this player? The scout is freed up; any report filed so far is kept.')) return;
  btn.disabled = true;
  try {
    const res = await fetch('/api/scouting/assignment/cancel', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: btn.dataset.pid}),
    });
    const data = await res.json();
    if (data.ok) {
      setTimeout(async () => {
        try {
          const rr = await fetch('/api/scouting/result');
          const rd = await rr.json();
          const r = rd.result;
          if (r && !r.ok) alert(r.error || 'Could not cancel.');
        } catch (_) {}
        loadScouting();
      }, 1200);
    } else {
      alert('Could not cancel: ' + (data.error || 'unknown'));
      btn.disabled = false;
    }
  } catch (err) { console.error(err); btn.disabled = false; }
});

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

/* ================= Batch B: tabs, scouting staff, player database ================= */

document.getElementById('scout-tabs').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-tab]');
  if (!btn) return;
  document.querySelectorAll('#scout-tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const tab = btn.dataset.tab;
  ['work', 'staff', 'database'].forEach(t =>
    document.getElementById('view-' + t).classList.toggle('hidden', t !== tab));
  if (tab === 'staff') renderScoutStaff();
  if (tab === 'database') loadDatabase();
});

/* ---- Scouting staff list ---- */
async function renderScoutStaff() {
  const body = document.getElementById('scout-staff-body');
  const ov = document.getElementById('scout-overview');
  try {
    const res = await fetch('/api/scouting/staff');
    const d = await res.json();
    const o = d.overview || {};
    ov.innerHTML = `
      <div class="ov-stat"><strong>${o.staff_count || 0}</strong><span>Scouts</span></div>
      <div class="ov-stat"><strong>${o.active_assignments || 0}</strong><span>Active assignments</span></div>
      <div class="ov-stat"><strong>${o.completed_reports || 0}</strong><span>Completed reports</span></div>
      <div class="ov-stat"><strong>${o.budget_remaining != null ? '$' + Number(o.budget_remaining).toLocaleString() : '—'}</strong><span>Staff budget left</span></div>`;
    body.innerHTML = (d.scouts || []).map(s => `
      <tr>
        <td>${s.id ? `<span class="clickable-text" data-href="/staff/${esc(s.id)}" title="Open staff profile"><strong>${esc(s.name)}</strong></span>` : `<strong>${esc(s.name)}</strong>`}</td>
        <td>${esc(s.role || '—')}</td>
        <td>${s.judging_ability}</td>
        <td>${s.judging_potential}</td>
        <td>${esc(s.region || '<i class="dim">—</i>')}</td>
        <td>${s.workload || 0} active</td>
        <td class="dim small">${esc(s.track_record || 'no graded calls yet')}</td>
        <td>${s.age || '—'}</td>
        <td>${s.experience || 0}y</td>
      </tr>`).join('') || '<tr><td colspan="9" class="dim">No scouts on staff.</td></tr>';
  } catch (e) { console.error(e); }
}

/* ---- Player database with advanced filters ---- */
const DB_AGE = {all: [16, 60], u18: [16, 17], 1822: [18, 22], 2329: [23, 29], '30p': [30, 60]};
let dbState = {offset: 0, limit: 100, total: 0, teamsLoaded: false};

function dbParams() {
  const age = DB_AGE[document.getElementById('db-age').value] || DB_AGE.all;
  return {
    q: document.getElementById('db-q').value.trim(),
    position: document.getElementById('db-position').value,
    status: document.getElementById('db-status').value,
    team: document.getElementById('db-team').value,
    age_min: age[0], age_max: age[1],
    ovr_min: document.getElementById('db-ovr').value,
    limit: dbState.limit, offset: dbState.offset,
  };
}

async function loadDatabase() {
  const body = document.getElementById('db-body');
  try {
    const qs = new URLSearchParams(dbParams()).toString();
    const res = await fetch('/api/scouting/database?' + qs);
    const d = await res.json();
    dbState.total = d.total || 0;
    if (!dbState.teamsLoaded && (d.teams || []).length) {
      dbState.teamsLoaded = true;
      document.getElementById('db-team').innerHTML =
        '<option value="">All teams</option>' +
        d.teams.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join('');
    }
    const stLabel = {nhl: 'NHL', ahl: 'AHL', prospects: 'Prospect', free_agents: 'FA', draft: 'Draft'};
    body.innerHTML = (d.players || []).map(p => `
      <tr>
        <td>${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile"><strong>${esc(p.name)}</strong></span>` : `<strong>${esc(p.name)}</strong>`}</td>
        <td>${esc(p.position || '—')}</td>
        <td>${p.age || '—'}</td>
        <td><strong>${p.overall || '—'}</strong></td>
        <td>${esc(p.team || '—')}</td>
        <td>${stLabel[p.status] || esc(p.status || '—')}</td>
        <td>${p.games_played || 0}</td>
        <td>${p.goals || 0}</td>
        <td>${p.assists || 0}</td>
        <td>${p.salary ? '$' + Number(p.salary).toLocaleString() : '—'}</td>
      </tr>`).join('') || '<tr><td colspan="10" class="dim">No players match these filters.</td></tr>';
    document.getElementById('db-count').textContent =
      `${dbState.total.toLocaleString()} players`;
    const pages = Math.max(1, Math.ceil(dbState.total / dbState.limit));
    const page = Math.floor(dbState.offset / dbState.limit) + 1;
    document.getElementById('db-page').textContent = `Page ${page} of ${pages}`;
  } catch (e) { console.error(e); }
}

let dbDebounce = null;
function dbRefresh(reset) {
  if (reset) dbState.offset = 0;
  clearTimeout(dbDebounce);
  dbDebounce = setTimeout(loadDatabase, 250);
}
['db-q', 'db-position', 'db-status', 'db-team', 'db-age', 'db-ovr'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => dbRefresh(true));
});
document.getElementById('db-clear').addEventListener('click', () => {
  document.getElementById('db-q').value = '';
  document.getElementById('db-position').value = 'all';
  document.getElementById('db-status').value = 'all';
  document.getElementById('db-team').value = '';
  document.getElementById('db-age').value = 'all';
  document.getElementById('db-ovr').value = '1';
  dbRefresh(true);
});
document.getElementById('db-prev').addEventListener('click', () => {
  dbState.offset = Math.max(0, dbState.offset - dbState.limit);
  loadDatabase();
});
document.getElementById('db-next').addEventListener('click', () => {
  if (dbState.offset + dbState.limit < dbState.total) dbState.offset += dbState.limit;
  loadDatabase();
});
