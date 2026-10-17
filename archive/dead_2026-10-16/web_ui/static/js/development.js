/* Puck Dynasty web development screen — Batch D (2026-10-05)
   Ports: Assign Training Program, Practice Center (per-player drills),
   Coach Runs Practice, Positional Training, Offseason Programs. */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function ovColor(ov) {
  if (ov >= 85) return '#3B82F6';
  if (ov >= 75) return '#22c55e';
  if (ov >= 65) return '#e8b93c';
  return '#78716c';
}

const DEV = {
  data: null,
  catalog: {focuses: [], intensities: [], practice: {drills: [], intensities: [], fatigue_costs: {}}},
  players: [],
  playersById: {},
};

async function loadDev() {
  try {
    const res = await fetch('/api/development');
    const data = await res.json();
    DEV.data = data;
    DEV.players = data.players || [];
    DEV.playersById = {};
    for (const p of DEV.players) DEV.playersById[String(p.id)] = p;
    DEV.catalog = data.catalog || DEV.catalog;
    renderPrograms(data.programs || []);
    renderProspects(data.prospects || []);
    document.getElementById('dev-count').textContent =
      (data.programs || []).length + ' active programs';
    buildAssignForm();
    buildPracticeForm();
    buildPositionForm();
    buildOffseasonForm(data.offseason || {});
  } catch (e) { console.error(e); }
}

function renderPrograms(programs) {
  const grid = document.getElementById('prog-grid');
  grid.innerHTML = '';
  document.getElementById('prog-empty').hidden = programs.length > 0;
  for (const pr of programs) {
    const p = pr.player || {};
    const el = document.createElement('div');
    el.className = 'prog-card';
    el.innerHTML = `
      <div class="prog-head">
        <div class="ov" style="--c:${ovColor(p.overall || 0)}">${esc(p.overall || 0)}</div>
        <div>
          <div class="prog-name">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile">${esc(p.name)}</span>` : esc(p.name)}</div>
          <div class="prog-sub">${esc(p.position)} · Age ${esc(p.age)}${p.injured ? ' · Injured' : ''}</div>
        </div>
      </div>
      <div class="prog-tags">
        <span class="tag">${esc(pr.focus)}</span>
        <span class="tag intensity">${esc(pr.intensity)}</span>
        ${pr.assigned ? `<span class="tag assigned">since ${esc(pr.assigned)}</span>` : ''}
      </div>
      ${p.id ? `<button class="btn-danger btn-sm" data-cancel="${esc(p.id)}">Cancel Program</button>` : ''}`;
    grid.appendChild(el);
  }
  grid.querySelectorAll('[data-cancel]').forEach(btn => {
    btn.addEventListener('click', () => cancelProgram(btn.dataset.cancel, btn));
  });
}

function renderProspects(prospects) {
  const list = document.getElementById('prospect-list');
  list.innerHTML = '';
  document.getElementById('prospect-empty').hidden = prospects.length > 0;
  for (const p of prospects) {
    const el = document.createElement('div');
    el.className = 'prospect-row';
    el.innerHTML = `
      <div class="pr-ov" style="--c:${ovColor(p.overall || 0)}">${esc(p.overall || 0)}</div>
      <div>
          <div class="pr-name">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile">${esc(p.name)}</span>` : esc(p.name)}</div>
        <div class="pr-sub">${esc(p.position)} · Age ${esc(p.age)}</div>
      </div>
      <span class="pr-squad ${p.squad === 'AHL' ? 'ahl' : ''}">${esc(p.squad || '')}</span>
      <div class="pr-bar"><span style="width:${Math.min(100, p.overall || 0)}%;background:${ovColor(p.overall || 0)}"></span></div>
      ${p.in_program ? '<span class="pr-badge">IN PROGRAM</span>' : '<span></span>'}`;
    list.appendChild(el);
  }
}

/* ---------- shared helpers ---------- */

function fillPlayerSelect(selId, filterFn) {
  const sel = document.getElementById(selId);
  sel.innerHTML = '';
  const list = DEV.players.filter(filterFn || (() => true));
  for (const p of list) {
    const opt = document.createElement('option');
    opt.value = p.id;
    const bits = [`${p.name} (${p.position})`, `Age ${p.age}`, p.squad];
    if (p.injured) bits.push('INJURED');
    if (p.in_program) bits.push('IN PROGRAM');
    opt.textContent = bits.join(' · ');
    opt.disabled = !!p.injured;
    sel.appendChild(opt);
  }
  return sel;
}

function playerLabel(p) {
  if (!p) return '';
  return `${p.name} (${p.position})`;
}

function showResult(elId, ok, summary) {
  const el = document.getElementById(elId);
  el.hidden = false;
  el.classList.toggle('good', !!ok);
  el.classList.toggle('bad', !ok);
  el.textContent = summary || (ok ? 'Done.' : 'Failed.');
}

async function pollResult(nonce, marker, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 12000);
  while (Date.now() < deadline) {
    try {
      const res = await fetch('/api/development/result');
      const data = await res.json();
      const r = data.result;
      if (r && r.nonce === nonce && r.marker === marker) return r;
    } catch (e) {}
    await new Promise(r => setTimeout(r, 500));
  }
  return null;
}

async function postDev(url, body, resultEl, marker) {
  const btn = document.activeElement;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {}),
    });
    const data = await res.json();
    if (!data.ok) {
      showResult(resultEl, false, 'Could not queue the command.');
      return;
    }
    const note = document.getElementById(resultEl.replace('-result', '-note'));
    if (note) note.textContent = 'Working…';
    const r = await pollResult(data.nonce, marker);
    if (note) note.textContent = '';
    if (!r) {
      showResult(resultEl, false, 'No response from the game — it may be busy.');
      return;
    }
    showResult(resultEl, r.ok, r.summary);
    await loadDev(); // refresh fatigue / programs / schedules
  } catch (e) {
    console.error(e);
    showResult(resultEl, false, 'Request failed.');
  } finally {
    if (btn && btn.blur) btn.blur();
  }
}

/* ---------- assign training program ---------- */

function buildAssignForm() {
  fillPlayerSelect('assign-player', p => !p.injured);
  const fg = document.getElementById('assign-focus');
  fg.innerHTML = '';
  DEV.catalog.focuses.forEach((f, i) => {
    const lab = document.createElement('label');
    lab.className = 'dev-radio';
    lab.innerHTML = `<input type="radio" name="assign-focus" value="${esc(f)}"${i === 0 ? ' checked' : ''}> <span>${esc(f)}</span>`;
    fg.appendChild(lab);
  });
  const ig = document.getElementById('assign-intensity');
  ig.innerHTML = '';
  DEV.catalog.intensities.forEach((iv, i) => {
    const lab = document.createElement('label');
    lab.className = 'dev-radio';
    lab.innerHTML = `<input type="radio" name="assign-intensity" value="${esc(iv)}"${iv === 'Standard' ? ' checked' : ''}> <span>${esc(iv)}</span>`;
    ig.appendChild(lab);
  });
  document.getElementById('assign-btn').addEventListener('click', assignProgram);
  document.getElementById('assign-player').addEventListener('change', updateAssignNote);
  updateAssignNote();
}

function updateAssignNote() {
  const pid = document.getElementById('assign-player').value;
  const p = DEV.playersById[String(pid)];
  const note = document.getElementById('assign-note');
  if (!p) { note.textContent = ''; return; }
  note.textContent = `${playerLabel(p)} · fatigue ${p.fatigue}%${p.in_program ? ' · already in a program (re-assign replaces it)' : ''}. Program runs weekly for 30 days; a first session runs immediately.`;
}

function assignProgram() {
  const pid = document.getElementById('assign-player').value;
  const focus = (document.querySelector('input[name="assign-focus"]:checked') || {}).value;
  const intensity = (document.querySelector('input[name="assign-intensity"]:checked') || {}).value;
  if (!pid || !focus) { showResult('assign-result', false, 'Pick a player and a focus.'); return; }
  postDev('/api/development/assign-program',
    {player_id: pid, focus, intensity}, 'assign-result', 'assign_training_program');
}

function cancelProgram(pid, btn) {
  btn.disabled = true;
  postDev('/api/development/cancel-program', {player_id: pid}, 'assign-result', 'cancel_training_program');
}

/* ---------- practice center ---------- */

function buildPracticeForm() {
  fillPlayerSelect('prac-player', p => !p.injured);
  const ds = document.getElementById('prac-drill');
  ds.innerHTML = '';
  for (const d of DEV.catalog.practice.drills) {
    const opt = document.createElement('option');
    opt.value = d.key;
    opt.textContent = d.label;
    ds.appendChild(opt);
  }
  const is = document.getElementById('prac-intensity');
  is.innerHTML = '';
  for (const iv of DEV.catalog.practice.intensities) {
    const opt = document.createElement('option');
    opt.value = iv;
    opt.textContent = iv.charAt(0).toUpperCase() + iv.slice(1);
    if (iv === 'moderate') opt.selected = true;
    is.appendChild(opt);
  }
  const refresh = () => updatePracticePreview();
  ds.addEventListener('change', refresh);
  is.addEventListener('change', refresh);
  document.getElementById('prac-player').addEventListener('change', refresh);
  document.getElementById('prac-run-btn').addEventListener('click', () => {
    postDev('/api/development/practice/run',
      pracPayload(), 'prac-result', 'run_practice_session');
  });
  document.getElementById('prac-sched-btn').addEventListener('click', () => {
    const pw = parseInt(document.getElementById('sched-per-week').value, 10) || 3;
    const w = parseInt(document.getElementById('sched-weeks').value, 10) || 4;
    postDev('/api/development/practice/schedule',
      {...pracPayload(), sessions: pw * w}, 'prac-result', 'schedule_practice');
  });
  document.getElementById('prac-stop-btn').addEventListener('click', () => {
    postDev('/api/development/practice/stop',
      {player_id: document.getElementById('prac-player').value},
      'prac-result', 'stop_practice_schedule');
  });
  document.getElementById('coach-runs-btn').addEventListener('click', () => {
    postDev('/api/development/practice/coach-runs', {}, 'prac-result', 'coach_runs_practice');
  });
  updatePracticePreview();
}

function pracPayload() {
  return {
    player_id: document.getElementById('prac-player').value,
    drill: document.getElementById('prac-drill').value,
    intensity: document.getElementById('prac-intensity').value,
  };
}

async function updatePracticePreview() {
  const {player_id, drill, intensity} = pracPayload();
  const p = DEV.playersById[String(player_id)];
  const drillInfo = DEV.catalog.practice.drills.find(d => d.key === drill);
  document.getElementById('prac-trains').textContent =
    drillInfo ? drillInfo.trains.join(', ') : '';
  const cost = DEV.catalog.practice.fatigue_costs[intensity];
  const cur = document.getElementById('prac-current');
  cur.textContent = p && p.schedule ? `Current schedule: ${p.schedule}` : '';
  const costEl = document.getElementById('prac-cost');
  if (!p) { costEl.textContent = ''; return; }
  costEl.textContent = `+${cost != null ? cost : '?'}% fatigue (now ${p.fatigue}%) — checking…`;
  try {
    const res = await fetch('/api/development/practice/can', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id, drill, intensity}),
    });
    const data = await res.json();
    costEl.textContent = `+${data.fatigue_cost != null ? data.fatigue_cost : '?'}% fatigue (now ${p.fatigue}%) — ${data.ok ? '✓ ' + esc(data.reason) : '✗ ' + esc(data.reason)}`;
  } catch (e) {
    costEl.textContent = `+${cost != null ? cost : '?'}% fatigue (now ${p.fatigue}%)`;
  }
}

/* ---------- positional training ---------- */

function buildPositionForm() {
  fillPlayerSelect('pos-player', p => !p.injured);
  document.getElementById('pos-player').addEventListener('change', renderPosFam);
  document.getElementById('pos-train-btn').addEventListener('click', () => {
    const pid = document.getElementById('pos-player').value;
    const target = (document.querySelector('input[name="pos-target"]:checked') || {}).value;
    if (!pid || !target) { showResult('pos-result', false, 'Pick a player and a position.'); return; }
    postDev('/api/development/position/train',
      {player_id: pid, target}, 'pos-result', 'assign_position_training');
  });
  renderPosFam();
}

function renderPosFam() {
  const pid = document.getElementById('pos-player').value;
  const p = DEV.playersById[String(pid)];
  const box = document.getElementById('pos-fam');
  box.innerHTML = '';
  const note = document.getElementById('pos-note');
  if (!p || !p.position_training) { box.innerHTML = '<span class="dev-note">No player selected.</span>'; return; }
  const pt = p.position_training;
  const fam = pt.familiarity || {};
  for (const pos of pt.eligible) {
    const v = fam[pos] != null ? fam[pos] : 0;
    const row = document.createElement('label');
    row.className = 'fam-row';
    row.innerHTML = `
      <input type="radio" name="pos-target" value="${esc(pos)}"${pt.target === pos ? ' checked' : ''}>
      <span class="fam-pos">${esc(pos)}</span>
      <span class="fam-bar"><span style="width:${Math.min(100, v)}%"></span></span>
      <span class="fam-val">${esc(String(Math.round(v)))}</span>
      ${pt.target === pos ? '<span class="fam-target">TRAINING</span>' : ''}`;
    box.appendChild(row);
  }
  if (!pt.eligible.length) {
    note.textContent = 'Goalies cannot train skater positions.';
  } else {
    note.textContent = `Primary ${esc(pt.primary)}. Young, high-IQ players learn fastest. Diminishing returns near 100.`;
  }
}

/* ---------- offseason programs ---------- */

function buildOffseasonForm(offseason) {
  const locked = !offseason.assignable;
  document.getElementById('offseason-locked').hidden = !locked;
  document.getElementById('offseason-panel').hidden = locked;
  if (locked) return;
  fillPlayerSelect('off-player');
  const ff = document.getElementById('off-focus');
  ff.innerHTML = '';
  for (const f of DEV.catalog.focuses) {
    const opt = document.createElement('option');
    opt.value = f; opt.textContent = f;
    ff.appendChild(opt);
  }
  const fi = document.getElementById('off-intensity');
  fi.innerHTML = '';
  for (const iv of DEV.catalog.intensities) {
    const opt = document.createElement('option');
    opt.value = iv; opt.textContent = iv;
    if (iv === 'Standard') opt.selected = true;
    fi.appendChild(opt);
  }
  const update = () => {
    const pid = document.getElementById('off-player').value;
    const p = DEV.playersById[String(pid)];
    document.getElementById('off-note').textContent =
      p && p.offseason ? `${playerLabel(p)}: ${p.offseason.focus} (${p.offseason.intensity})` : '';
  };
  document.getElementById('off-player').addEventListener('change', update);
  document.getElementById('off-assign-btn').addEventListener('click', () => {
    postDev('/api/development/offseason/assign', {
      player_id: document.getElementById('off-player').value,
      focus: document.getElementById('off-focus').value,
      intensity: document.getElementById('off-intensity').value,
    }, 'off-result', 'assign_offseason_program');
  });
  document.getElementById('off-clear-btn').addEventListener('click', () => {
    postDev('/api/development/offseason/clear', {
      player_id: document.getElementById('off-player').value,
    }, 'off-result', 'clear_offseason_program');
  });
  update();
}

loadDev();

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

/* ================= Batch B: development analytics + recommendations ================= */

let DEV_AN = null;

function gradeColor(g) {
  if (g === 'A+' || g === 'A') return '#4CAF50';
  if (g === 'B+' || g === 'B') return '#8BC34A';
  if (g === 'C+' || g === 'C') return '#FFC107';
  return '#F44336';
}

async function loadDevAnalytics() {
  try {
    const res = await fetch('/api/development/analytics');
    DEV_AN = await res.json();
    renderDevAnalytics();
  } catch (e) { console.error(e); }
}

function renderDevAnalytics() {
  const d = DEV_AN;
  if (!d) return;
  const o = d.overview || {};
  document.getElementById('dev-overview').innerHTML = `
    <div class="ov-stat"><strong>${o.total_players || 0}</strong><span>Total players</span></div>
    <div class="ov-stat"><strong>${o.avg_age || 0}</strong><span>Average age</span></div>
    <div class="ov-stat"><strong>${o.avg_potential || 0}</strong><span>Average potential</span></div>`;
  document.getElementById('dev-positions').innerHTML = (d.positions || []).map(p => `
    <div class="attr-row"><span><strong>${esc(p.position)}</strong></span>
      <span class="dim">${p.count} players</span>
      <span class="dim">Pot: ${p.avg_potential}</span></div>`).join('') ||
    '<div class="dim">No data.</div>';
  document.getElementById('dev-ages').innerHTML = (d.age_bands || []).map(b => `
    <div class="attr-row"><span><strong>${esc(b.band)}</strong></span>
      <span class="dim">${b.count} players</span>
      <div class="mini-bar"><div class="mini-fill" style="width:${o.total_players ? Math.round(b.count / o.total_players * 100) : 0}%;background:#3B82F6"></div></div></div>`).join('');

  const q = (document.getElementById('dev-an-q').value || '').toLowerCase();
  const squad = document.getElementById('dev-an-squad').value || 'all';
  const onlyRecs = document.getElementById('dev-an-recs').checked;
  const prioColor = {HIGH: '#F44336', MED: '#FFC107', LOW: '#3B82F6'};
  const players = (d.players || []).filter(p => {
    if (q && !(p.name || '').toLowerCase().includes(q)) return false;
    if (squad !== 'all' && p.squad !== squad) return false;
    if (onlyRecs && !(p.recommendations || []).length) return false;
    return true;
  }).slice(0, 40);
  document.getElementById('dev-player-cards').innerHTML = players.map(p => `
    <div class="dev-card dev-player">
      <div class="dev-player-head">
        ${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile"><strong>${esc(p.name)}</strong></span>` : `<strong>${esc(p.name)}</strong>`}
        <span class="dim">${esc(p.position || '')} · ${p.age} · OVR ${p.overall} · ${esc(p.squad || '')}</span>
      </div>
      <div class="dev-attrs">${(p.key_attributes || []).map(a => `
        <div class="attr-row"><span>${esc(a.name)}</span>
          <div class="mini-bar"><div class="mini-fill" style="width:${a.value}%;background:${gradeColor(a.grade)}"></div></div>
          <strong>${a.value}</strong><span class="grade" style="color:${gradeColor(a.grade)}">${esc(a.grade)}</span>
        </div>`).join('')}</div>
      ${(p.recommendations || []).length ? `<div class="dev-recs">
        <div class="recs-title">Development Focus Recommendations</div>
        ${(p.recommendations || []).map(r => `
          <div class="rec-row"><span class="prio" style="color:${prioColor[r.priority] || '#8b98ab'}">${esc(r.priority)}</span>
            <span><strong>${esc(r.area)}:</strong> ${esc(r.reason)}</span></div>`).join('')}
      </div>` : '<div class="dim small">No recommendations — a balanced profile.</div>'}
    </div>`).join('') || '<div class="dim">No players match.</div>';
}

['dev-an-q', 'dev-an-squad', 'dev-an-recs'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener(el.tagName === 'INPUT' && el.type !== 'checkbox' ? 'input' : 'change', () => {
    clearTimeout(window._devAnT);
    window._devAnT = setTimeout(renderDevAnalytics, 200);
  });
});

loadDevAnalytics();
