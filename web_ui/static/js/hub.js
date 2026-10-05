// Puck Dynasty tile hub — target-matched rendering (ARTIFACT_TARGET.jpg)
const TH_ICONS = {
  roster: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="8" r="3.6"/><path d="M3.5 19c.6-3.2 3.2-5 6.5-5s5.9 1.8 6.5 5"/><path d="M18.5 8v6M15.5 11h6"/></svg>',
  inbox: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 13l2.7-7.5h12.6L21 13v6a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19z"/><path d="M3 13h6l1.2 2h3.6L15 13h6"/></svg>',
  schedule: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/><path d="M7.5 13.5h3M7.5 16.5h5.5"/></svg>',
  stats: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16"/><path d="M7 20v-7M12 20V9M17 20v-10"/></svg>',
  lines: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M9 8.5h6M9 12h6M9 15.5h4"/></svg>',
  trades: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13l-3.5-3.5M20 16H7l3.5 3.5"/></svg>',
  scouting: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.3 15.3L20.5 20.5"/></svg>',
  staff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 19c.5-3 2.9-4.6 6-4.6s5.5 1.6 6 4.6"/><circle cx="17" cy="9" r="2.4"/><path d="M15.5 14.6c2.9.1 5 1.6 5.5 4.4"/></svg>',
  watch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="12.5" rx="2.5"/><path d="M10.5 9.8v4.4L14.5 12z"/></svg>',
  tactics: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8" fill="currentColor"/></svg>',
  default: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/></svg>',
};
const TH_PRIMARY = ['roster', 'inbox', 'schedule', 'stats'];

function thSeason(dateStr) {
  const m = String(dateStr || '').match(/(19|20)\d{2}/);
  if (!m) return 'FRANCHISE';
  const y = parseInt(m[0], 10);
  return `FRANCHISE · ${y}-${String(y + 1).slice(2)} SEASON`;
}

async function loadState() {
  try {
    const res = await fetch('/api/state');
    const s = await res.json();
    renderHub(s);
  } catch (e) {
    console.error('API failed', e);
  } finally {
    // Reveal the page only once data (or failure) is in — no staggered load.
    const l = document.getElementById('th-loading');
    if (l) l.classList.add('done');
  }
}

function renderHub(s) {
  const team = s.team || {};
  const rec = team.record || {};
  document.getElementById('th-season').textContent = thSeason(s.date);
  document.getElementById('th-team').textContent = (team.name || '—').toUpperCase();
  document.getElementById('th-record').textContent =
    `${rec.w ?? 0}-${rec.l ?? 0}-${rec.otl ?? 0}`;

  // Hero next-game line (handles live + mock shapes)
  const ng = s.next_game;
  let nextTxt = 'Next: —';
  if (ng) {
    if (typeof ng.home === 'string' && typeof ng.away === 'string') {
      nextTxt = `Next: ${ng.away} at ${ng.home}`;
    } else if (ng.opponent) {
      const isHome = ng.is_home ?? ng.home;
      nextTxt = isHome ? `Next: ${ng.opponent} at ${team.name || ''}`
                       : `Next: ${team.name || ''} at ${ng.opponent}`;
    }
  }
  document.getElementById('th-next').textContent = nextTxt;

  // Tiles: primary four, then the rest under MORE
  const tiles = s.tiles || [];
  const grid = document.getElementById('th-grid');
  const more = document.getElementById('th-grid-more');
  grid.innerHTML = '';
  more.innerHTML = '';
  const primaries = [];
  const rest = [];
  for (const t of tiles) {
    if (t.id === 'continue') continue; // hero handles it
    (TH_PRIMARY.includes(t.id) ? primaries : rest).push(t);
  }
  // keep primary order stable
  primaries.sort((a, b) => TH_PRIMARY.indexOf(a.id) - TH_PRIMARY.indexOf(b.id));
  for (const t of primaries) grid.appendChild(thTile(t, false));
  for (const t of rest) more.appendChild(thTile(t, true));
  document.querySelector('.th-more-label').style.display = rest.length ? '' : 'none';
}

function thTile(t, compact) {
  const el = document.createElement('button');
  el.className = 'th-tile';
  el.setAttribute('aria-label', t.title);
  el.innerHTML = `
    ${t.badge ? `<span class="th-badge">${t.badge}</span>` : ''}
    <span class="th-icon">${TH_ICONS[t.id] || TH_ICONS.default}</span>
    <h3 class="th-label">${esc(t.title)}</h3>
    ${compact && t.subtitle ? `<p class="th-sub">${esc(t.subtitle)}</p>` : ''}`;
  el.addEventListener('click', () => openTile(t));
  return el;
}

function openTile(t) {
  const known = ['inbox','roster','schedule','lines','waivers','captains',
    'trades','trade_block','free_agents','staff','development','camp','morale',
    'standings','stats','playoffs','calendar','news','history','finances',
    'contracts','scouting','draft','settings','save','tactics'];
  if (known.includes(t.id)) { window.location.href = '/' + t.id; return; }
  console.log('open', t.id);
}

/* ---------- hero: Continue flow ---------- */
function heroActivate() {
  continueFlow();
}
document.getElementById('th-hero').addEventListener('click', heroActivate);
document.getElementById('th-hero').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); heroActivate(); }
});

async function continueFlow() {
  let st;
  try {
    st = await (await fetch('/api/continue_state')).json();
  } catch (e) { return; }
  if (!st.blocked) {
    if (confirm('Advance the day?')) advanceDay(st);
    return;
  }
  showBlockerModal(st.blockers);
}

async function advanceDay(st) {
  // If watch mode is on and today has games, open the visualizer instead.
  try {
    const wm = await (await fetch('/api/watch_mode')).json();
    if (wm.mode === 'watch' && st && st.has_games) {
      window.location.href = '/watch';
      return;
    }
  } catch (e) { /* fall through to quick sim */ }
  fetch('/api/command', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({op: 'advance_day'}),
  }).then(() => setTimeout(() => window.location.reload(), 800));
}

function showBlockerModal(blockers) {
  closeBlockerModal();
  const ov = document.createElement('div');
  ov.className = 'modal-ov'; ov.id = 'blocker-modal';
  const cards = blockers.map(b => `
    <div class="blocker-card">
      <div class="b-title">${esc(b.title)}</div>
      <div class="b-detail">${esc(b.detail)}</div>
      <div class="b-actions">
        ${b.web_route ? `<a class="btn-ghost" href="${b.web_route}">Fix it →</a>` : ''}
        ${b.has_auto ? `<button class="btn-auto" data-bid="${esc(b.id)}">⚡ ${esc(b.auto_label)}</button>` : ''}
      </div>
    </div>`).join('');
  ov.innerHTML = `
    <div class="modal-card">
      <h2>Can't advance yet</h2>
      <p class="modal-sub">${blockers.length} thing${blockers.length === 1 ? '' : 's'} need${blockers.length === 1 ? 's' : ''} your attention before the day can advance.</p>
      ${cards}
      <button class="modal-close" id="blocker-close">Close</button>
    </div>`;
  document.body.appendChild(ov);
  document.getElementById('blocker-close').addEventListener('click', closeBlockerModal);
  ov.addEventListener('click', e => { if (e.target === ov) closeBlockerModal(); });
  ov.querySelectorAll('.btn-auto').forEach(btn =>
    btn.addEventListener('click', async () => {
      btn.disabled = true; btn.textContent = 'Working…';
      await fetch('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'resolve_blocker', blocker_id: btn.dataset.bid, kind: 'auto'}),
      });
      setTimeout(async () => {
        const st = await (await fetch('/api/continue_state')).json();
        if (st.blocked) showBlockerModal(st.blockers);
        else { closeBlockerModal(); advanceDay(); }
      }, 800);
    }));
}

function closeBlockerModal() {
  const m = document.getElementById('blocker-modal');
  if (m) m.remove();
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

/* ---------- top bar: back + menu ---------- */
document.getElementById('btn-back').addEventListener('click', () => {
  if (history.length > 1) history.back();
});
const menuBtn = document.getElementById('btn-menu');
const menu = document.getElementById('th-menu');
menuBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  menu.hidden = !menu.hidden;
});
document.addEventListener('click', (e) => {
  if (!menu.hidden && !e.target.closest('.th-menuwrap')) menu.hidden = true;
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (!menu.hidden) menu.hidden = true;
    closeBlockerModal();
  }
});

function exitGame() {
  if (!confirm('Exit Puck Dynasty? Make sure your career is saved.')) return;
  fetch('/api/exit', {method: 'POST'}).catch(() => {});
  document.body.innerHTML = '<div style="display:flex;height:100vh;align-items:center;justify-content:center;color:#888;font-size:18px">Puck Dynasty has exited. You can close this tab.</div>';
}
document.getElementById('btn-exit')?.addEventListener('click', exitGame);
document.getElementById('menu-exit')?.addEventListener('click', exitGame);

loadState();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
