/* Puck Dynasty web entry-draft board */
async function loadDraft() {
  try {
    const res = await fetch('/api/draft');
    const data = await res.json();
    renderDraft(data);
  } catch (e) { console.error(e); }
}

function renderDraft(d) {
  const board = document.getElementById('board');
  const summary = document.getElementById('draft-summary');
  document.getElementById('draft-count').textContent =
    d.active ? `Pick ${d.current_overall} of ${d.total_slots}` : '';
  if (!d.active) {
    document.getElementById('draft-title').textContent = 'Entry Draft';
    summary.innerHTML = '';
    board.innerHTML = '<div class="empty">No draft in progress.<br>The entry draft will appear here once the season reaches draft day.</div>';
    return;
  }
  document.getElementById('draft-title').textContent = d.year ? d.year + ' Entry Draft' : 'Entry Draft';
  const myPicks = d.user_picks || [];
  summary.innerHTML =
    `<span class="sum-pill">${d.made_count} / ${d.total_slots} picks made</span>` +
    (myPicks.length
      ? `<span class="sum-pill mine">Your next pick${myPicks.length > 1 ? 's' : ''}: ${myPicks.slice(0, 5).map(p => '#' + p).join(', ')}${myPicks.length > 5 ? ' +' + (myPicks.length - 5) + ' more' : ''}</span>`
      : '<span class="sum-pill">No remaining picks</span>');
  board.innerHTML = '';
  let lastRound = null;
  for (const b of (d.board || [])) {
    if (b.round !== lastRound) {
      lastRound = b.round;
      const h = document.createElement('div');
      h.className = 'round-head';
      h.textContent = lastRound > 0 ? 'Round ' + lastRound : 'Picks';
      board.appendChild(h);
    }
    const el = document.createElement('div');
    el.className = 'pick-row' +
      (b.is_user_pick ? ' mine' : '') +
      (b.is_current ? ' current' : '') +
      (b.made ? ' done' : '');
    const pr = b.prospect || {};
    el.innerHTML = `
      <div class="pick-num">#${b.overall}</div>
      <div class="pick-owner">${esc(b.owner)}${b.is_user_pick ? ' ⭐' : ''}</div>
      <div class="pick-player">${b.made
        ? `${esc(pr.name || '?')}<small>${esc(pr.position || '')}${pr.age ? ' · ' + pr.age + ' yrs' : ''}${pr.overall ? ' · OVR ' + pr.overall : ''}</small>`
        : '<span class="tbd">To be selected…</span>'}</div>`;
    board.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadDraft();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

/* ---------- War room tabs ---------- */
const draftState = { availPos: 'All', availQ: '', selected: null };
document.getElementById('draft-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#draft-tabs .tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('#draft-tab-board,#draft-tab-available,#draft-tab-mypicks')
    .forEach(p => p.classList.add('hidden'));
  document.getElementById('draft-tab-' + b.dataset.tab).classList.remove('hidden');
  if (b.dataset.tab === 'available') loadAvailable();
  if (b.dataset.tab === 'mypicks') loadMyPicks();
});

async function loadAvailable() {
  const q = new URLSearchParams({ pos: draftState.availPos });
  if (draftState.availQ) q.set('q', draftState.availQ);
  try {
    const res = await fetch('/api/draft/available?' + q);
    const data = await res.json();
    renderAvailable(data.prospects || []);
  } catch (e) { console.error(e); }
}
function renderAvailable(prospects) {
  const host = document.getElementById('available-list');
  host.innerHTML = prospects.length ? '' : '<div class="empty">No prospects available.</div>';
  draftState.selected = null;
  document.getElementById('btn-draft-selected').disabled = true;
  for (const p of prospects) {
    const el = document.createElement('div');
    el.className = 'fa-card';
    el.innerHTML = `
      <div class="fa-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
      <div class="fa-info">
        <div class="fa-name">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile">${esc(p.name)}</span>` : esc(p.name)}</div>
        <div class="fa-sub">${esc(p.position)} · Age ${p.age} · Potential ${esc(p.potential)}</div>
      </div>
      <div class="fa-bar"><span style="width:${Math.min(100, p.overall)}%;background:${barColor(p.overall)}"></span></div>`;
    el.addEventListener('click', () => {
      host.querySelectorAll('.fa-card').forEach(c => c.classList.remove('selected'));
      el.classList.add('selected');
      draftState.selected = p;
      document.getElementById('btn-draft-selected').disabled = false;
    });
    el.addEventListener('dblclick', () => { draftState.selected = p; askDraftConfirm(p); });
    const nm = el.querySelector('.clickable-text[data-href]');
    if (nm) nm.addEventListener('click', (e) => {
      e.stopPropagation();
      window.location.href = nm.dataset.href;
    });
    host.appendChild(el);
  }
}
document.getElementById('av-pos').addEventListener('click', e => {
  const b = e.target.closest('.tb-pill');
  if (!b) return;
  document.querySelectorAll('#av-pos .tb-pill').forEach(p => p.classList.remove('active'));
  b.classList.add('active');
  draftState.availPos = b.dataset.v;
  loadAvailable();
});
document.getElementById('av-q').addEventListener('input', e => {
  draftState.availQ = e.target.value;
  loadAvailable();
});
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

/* Draft Selected (2-step confirm) */
document.getElementById('btn-draft-selected').addEventListener('click', () => {
  if (draftState.selected) askDraftConfirm(draftState.selected);
});
function askDraftConfirm(p) {
  document.getElementById('confirm-text').textContent =
    `Draft ${p.name} (${p.position}, ${p.overall} OVR)? This cannot be undone.`;
  document.getElementById('confirm-modal').hidden = false;
  document.getElementById('confirm-ok').onclick = async () => {
    document.getElementById('confirm-modal').hidden = true;
    await fetch('/api/draft/pick', { method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ player_id: p.id }) });
    setTimeout(() => { loadDraft(); loadAvailable(); }, 800);
  };
}
document.getElementById('confirm-cancel').addEventListener('click', () =>
  document.getElementById('confirm-modal').hidden = true);

/* Sim Pick */
document.getElementById('btn-sim-pick').addEventListener('click', async () => {
  await fetch('/api/draft/sim_pick', { method: 'POST' });
  setTimeout(() => { loadDraft(); loadAvailable(); }, 800);
});

/* Scout Report */
document.getElementById('btn-scout').addEventListener('click', async () => {
  const p = draftState.selected;
  if (!p) return alert('Select a prospect first.');
  try {
    const res = await fetch('/api/draft/scout_report?player_id=' + encodeURIComponent(p.id));
    const d = await res.json();
    if (d.error) return alert(d.error);
    document.getElementById('scout-title').textContent = 'Scout Report — ' + d.name;
    let html = `<p>${esc(d.position)} · Age ${d.age} · ${d.overall} OVR</p>`;
    if (d.report) html += `<p>${esc(d.report)}</p>`;
    if (d.strengths && d.strengths.length)
      html += '<h4>Strengths</h4><ul>' + d.strengths.map(s => `<li>${esc(s)}</li>`).join('') + '</ul>';
    if (d.weaknesses && d.weaknesses.length)
      html += '<h4>Weaknesses</h4><ul>' + d.weaknesses.map(s => `<li>${esc(s)}</li>`).join('') + '</ul>';
    const attrs = d.attributes || {};
    const rows = Object.entries(attrs).map(([k, v]) =>
      `<div class="mk-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
    if (rows) html += '<h4>Attributes</h4>' + rows;
    document.getElementById('scout-body').innerHTML = html;
    document.getElementById('scout-modal').hidden = false;
  } catch (e) { console.error(e); }
});
document.getElementById('scout-close').addEventListener('click', () =>
  document.getElementById('scout-modal').hidden = true);

/* My Picks tab */
async function loadMyPicks() {
  try {
    const res = await fetch('/api/draft');
    const d = await res.json();
    const host = document.getElementById('mypicks-list');
    if (!d.active) { host.innerHTML = '<div class="empty">No draft in progress.</div>'; return; }
    const mine = (d.board || []).filter(b => b.is_user_pick);
    host.innerHTML = mine.length ? '' : '<div class="empty">You have no picks in this draft.</div>';
    for (const b of mine) {
      const el = document.createElement('div');
      el.className = 'pick-row' + (b.made ? '' : ' mine');
      el.innerHTML = `<span class="pick-num">#${b.overall}</span>
        <span>Round ${b.round}</span>
        <span>${b.made ? '— ' + esc((b.prospect || {}).name || 'picked') : '<b>Available</b>'}</span>`;
      host.appendChild(el);
    }
  } catch (e) { console.error(e); }
}

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, label')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
