/* Puck Dynasty web captains */
let candidates = [];

async function loadCaptains() {
  try {
    const res = await fetch('/api/captains');
    const data = await res.json();
    candidates = data.candidates || [];
    renderCurrent(data);
    renderPicker(data);
    renderCandidates(data);
  } catch (e) { console.error(e); }
}

function setCur(id, who, label) {
  const el = document.getElementById(id);
  el.querySelector('.cur-name').textContent = who ? who.name : '—';
  if (!el.querySelector('.cur-sub')) {
    const sub = document.createElement('div');
    sub.className = 'cur-sub';
    el.appendChild(sub);
  }
  el.querySelector('.cur-sub').textContent = who
    ? `${who.position} · ${who.overall} OVR · Leadership ${who.leadership}`
    : 'Not set';
}

function renderCurrent(data) {
  setCur('cur-c', data.captain);
  setCur('cur-a1', data.alternates && data.alternates[0]);
  setCur('cur-a2', data.alternates && data.alternates[1]);
}

function fillSelect(selId, selectedId) {
  const sel = document.getElementById(selId);
  sel.innerHTML = '<option value="">— none —</option>';
  for (const c of candidates) {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = `${c.name} (${c.position}, ${c.overall} OVR, Ldr ${c.leadership})`;
    if (String(c.id) === String(selectedId)) opt.selected = true;
    sel.appendChild(opt);
  }
}

function renderPicker(data) {
  const cur = data.captain || {}, a = data.alternates || [];
  fillSelect('pick-c', cur.id);
  fillSelect('pick-a1', a[0] && a[0].id);
  fillSelect('pick-a2', a[1] && a[1].id);
}

function renderCandidates(data) {
  const host = document.getElementById('capt-candidates');
  host.innerHTML = '';
  const curIds = new Set([
    data.captain && String(data.captain.id),
    ...((data.alternates || []).map(x => x && String(x.id))),
  ]);
  for (const c of candidates) {
    const el = document.createElement('div');
    el.className = 'cand';
    el.title = 'Click to select as captain';
    el.innerHTML = `<span class="nm">${esc(c.name)}</span>
      ${curIds.has(String(c.id)) ? '<span class="cur">CURRENT ' + esc(c.captaincy) + '</span>' : ''}
      <span class="ld">Ldr ${c.leadership}</span>
      <div class="sub">${esc(c.position)} · Age ${c.age} · ${c.overall} OVR${c.injured ? ' · Injured' : ''}</div>`;
    el.addEventListener('click', () => {
      document.getElementById('pick-c').value = c.id;
      document.getElementById('pick-status').textContent = `${c.name} selected as captain`;
    });
    host.appendChild(el);
  }
}

async function saveCaptains() {
  const status = document.getElementById('pick-status');
  status.className = 'pick-status';
  const payload = {
    captain_id: document.getElementById('pick-c').value || null,
    alt1_id: document.getElementById('pick-a1').value || null,
    alt2_id: document.getElementById('pick-a2').value || null,
  };
  const ids = [payload.captain_id, payload.alt1_id, payload.alt2_id].filter(Boolean);
  if (new Set(ids.map(String)).size !== ids.length) {
    status.textContent = 'The same player cannot hold two letters.';
    status.classList.add('err');
    return;
  }
  status.textContent = 'Saving…';
  try {
    const res = await fetch('/api/captains', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const out = await res.json();
    if (out.ok) {
      status.textContent = 'Queued — takes effect in the game shortly.';
      status.classList.add('ok');
      setTimeout(loadCaptains, 1500); // refresh once the main thread applies it
    } else {
      status.textContent = 'Failed: ' + (out.error || 'unknown error');
      status.classList.add('err');
    }
  } catch (e) {
    status.textContent = 'Failed: ' + e.message;
    status.classList.add('err');
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

document.getElementById('capt-save').addEventListener('click', saveCaptains);
loadCaptains();
