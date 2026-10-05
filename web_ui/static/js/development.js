/* Puck Dynasty web development screen */
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

async function loadDev() {
  try {
    const res = await fetch('/api/development');
    const data = await res.json();
    renderPrograms(data.programs || []);
    renderProspects(data.prospects || []);
    document.getElementById('dev-count').textContent =
      (data.programs || []).length + ' active programs';
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
      </div>`;
    grid.appendChild(el);
  }
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
