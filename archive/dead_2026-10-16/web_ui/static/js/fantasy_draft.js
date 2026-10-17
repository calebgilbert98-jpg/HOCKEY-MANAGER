/* Fantasy draft — simplified snake UI over the real FantasyDraftManager. */
let fdState = null;
let fdPos = '', fdQ = '';
let fdPoll = null;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}
function fmt$(n) { return '$' + Number(n || 0).toLocaleString('en-US'); }

async function loadFD() {
  try {
    fdState = await (await fetch('/api/fantasy_draft')).json();
  } catch (e) { console.error(e); return; }
  renderFD();
}

function renderFD() {
  const st = fdState;
  const status = document.getElementById('fd-status');
  const beginWrap = document.getElementById('fd-begin-wrap');
  const tabs = document.getElementById('fd-tabs');
  const show = (el, on) => { el.hidden = !on; };

  if (!st || !st.active) {
    show(beginWrap, !!(st && st.pending));
    show(tabs, false);
    ['available', 'mypicks', 'recent', 'order'].forEach(t =>
      show(document.getElementById('fd-tab-' + t), false));
    if (st && st.completed) {
      status.innerHTML = `<div class="fd-kicker">Draft complete</div>
        <div class="fd-big">All ${st.total_picks} picks are in.</div>
        <div class="fd-dim">Rosters have been redistributed. <a href="/roster">Review your roster →</a></div>`;
    } else {
      status.innerHTML = st && st.pending
        ? `<div class="fd-kicker">Draft pending</div><div class="fd-big">Your league is ready to draft.</div>`
        : `<div class="fd-big">No fantasy draft is pending.</div>
           <div class="fd-dim">Start a new game with the fantasy draft option to run one.</div>`;
    }
    document.getElementById('fd-count').textContent = '';
    stopPoll();
    return;
  }
  if (!st.started) {
    show(beginWrap, true);
    show(tabs, false);
    status.innerHTML = `<div class="fd-kicker">Draft pending</div>
      <div class="fd-big">Ready when you are.</div>`;
    return;
  }
  show(beginWrap, false);

  if (st.complete) {
    show(tabs, false);
    ['available', 'mypicks', 'recent', 'order'].forEach(t =>
      show(document.getElementById('fd-tab-' + t), false));
    status.innerHTML = `<div class="fd-kicker">Draft complete</div>
      <div class="fd-big">All ${st.total_picks} picks are in.</div>
      <div class="fd-dim">Rosters have been redistributed. <a href="/roster">Review your roster →</a></div>`;
    document.getElementById('fd-count').textContent = '';
    stopPoll();
    return;
  }

  show(tabs, true);
  const cur = st.current || {};
  const mine = !!cur.is_user_pick;
  document.getElementById('fd-count').textContent =
    `Pick ${cur.overall || '?'} of ${st.total_picks} · Round ${cur.round || '?'}`;
  status.innerHTML =
    `<div class="fd-kicker">${mine ? 'Your turn' : 'On the clock'}</div>
     <div class="fd-big">Pick #${cur.overall}: ${esc(cur.team || '')} ${mine ? '— you are up!' : 'selecting…'}</div>
     <div class="fd-dim">${st.picks_made} of ${st.total_picks} picks made · ${st.available_count} players in the pool</div>`;

  renderAvailable(st, mine);
  renderMyPicks(st);
  renderRecent(st);
  renderOrder(st);

  // While the AI chain runs (after your pick), keep polling until
  // it's your turn again or the draft completes.
  if (!mine) startPoll(); else stopPoll();
}

function startPoll() {
  stopPoll();
  fdPoll = setInterval(loadFD, 2000);
}
function stopPoll() {
  if (fdPoll) { clearInterval(fdPoll); fdPoll = null; }
}

function playerRow(p, canPick) {
  return `<div class="fd-prow">
    <div class="fd-pmain">
      <div class="fd-pname">${esc(p.name)}</div>
      <div class="fd-psub">${esc(p.position)} · Age ${p.age} · ${esc(p.former_team || '')}</div>
    </div>
    <div class="fd-povr">${p.overall}<span>ovr</span></div>
    <div class="fd-psal">${fmt$(p.salary)}</div>
    ${canPick ? `<button class="btn-primary fd-draft" data-pid="${esc(p.id)}">Draft</button>` : ''}
  </div>`;
}

function renderAvailable(st, mine) {
  const q = fdQ.toLowerCase();
  const list = (st.available || []).filter(p =>
    (!fdPos || p.position === fdPos) &&
    (!q || (p.name || '').toLowerCase().includes(q)));
  const el = document.getElementById('fd-available');
  el.innerHTML = list.length
    ? list.map(p => playerRow(p, mine)).join('')
    : `<div class="empty">No players match.</div>`;
  el.querySelectorAll('.fd-draft').forEach(b =>
    b.addEventListener('click', () => makePick(b.dataset.pid, b)));
}

async function makePick(pid, btn) {
  btn.disabled = true;
  btn.textContent = '…';
  try {
    await fetch('/api/fantasy_draft/pick', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: pid}),
    });
  } catch (e) { console.error(e); }
  setTimeout(loadFD, 800);
  startPoll();
}

function renderMyPicks(st) {
  const el = document.getElementById('fd-mypicks');
  const mine = st.my_picks || [];
  el.innerHTML = mine.length ? mine.map(p =>
    `<div class="fd-prow"><div class="fd-pmain">
       <div class="fd-pname">#${p.overall} — ${esc(p.player)}</div>
     </div><div class="fd-povr">${p.ovr}<span>ovr</span></div></div>`
  ).join('') : `<div class="empty">No picks yet.</div>`;
}

function renderRecent(st) {
  const el = document.getElementById('fd-recent');
  const rec = (st.recent_picks || []).slice().reverse();
  el.innerHTML = rec.length ? rec.map(p =>
    `<div class="fd-prow"><div class="fd-pmain">
       <div class="fd-pname">#${p.overall} — ${esc(p.player)}</div>
       <div class="fd-psub">${esc(p.team)}</div>
     </div><div class="fd-povr">${p.ovr}<span>ovr</span></div></div>`
  ).join('') : `<div class="empty">No picks yet.</div>`;
}

function renderOrder(st) {
  const el = document.getElementById('fd-order');
  el.innerHTML = (st.draft_order || []).map((t, i) =>
    `<div class="fd-prow"><div class="fd-pmain">
       <div class="fd-pname">${i + 1}. ${esc(t)}</div>
     </div></div>`).join('') || `<div class="empty">—</div>`;
}

// tabs
document.getElementById('fd-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#fd-tabs .tb-tab').forEach(t =>
    t.classList.toggle('active', t === b));
  ['available', 'mypicks', 'recent', 'order'].forEach(t =>
    document.getElementById('fd-tab-' + t).hidden = t !== b.dataset.tab);
});

// filters
document.getElementById('fd-pos').addEventListener('click', e => {
  const b = e.target.closest('.tb-pill');
  if (!b) return;
  document.querySelectorAll('#fd-pos .tb-pill').forEach(p =>
    p.classList.toggle('active', p === b));
  fdPos = b.dataset.pos;
  if (fdState) renderAvailable(fdState, !!(fdState.current && fdState.current.is_user_pick));
});
document.getElementById('fd-q').addEventListener('input', e => {
  fdQ = e.target.value;
  if (fdState) renderAvailable(fdState, !!(fdState.current && fdState.current.is_user_pick));
});

// begin
document.getElementById('fd-begin').addEventListener('click', async e => {
  const b = e.target;
  b.disabled = true; b.textContent = 'Starting…';
  try {
    if (!confirm('Begin the fantasy draft? Every NHL roster will be emptied into one draft pool (a safety checkpoint is taken first).')) {
      b.disabled = false; b.textContent = 'Begin Draft'; return;
    }
    await fetch('/api/fantasy_draft/begin', {method: 'POST'});
  } catch (err) { console.error(err); }
  setTimeout(loadFD, 1000);
  startPoll();
});

loadFD();

// Shared heartbeat (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat(); setInterval(beat, 30000);
})();
