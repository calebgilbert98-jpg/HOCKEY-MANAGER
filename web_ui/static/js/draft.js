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
  document.querySelectorAll('main.draft-main .tb-panel')
    .forEach(p => p.classList.add('hidden'));
  document.getElementById('draft-tab-' + b.dataset.tab).classList.remove('hidden');
  if (b.dataset.tab === 'available') loadAvailable();
  if (b.dataset.tab === 'mypicks') loadMyPicks();
  if (b.dataset.tab === 'buzz') loadBuzz();
  if (b.dataset.tab === 'trades') loadTradeFeed();
  if (b.dataset.tab === 'grades') loadGrades();
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

/* Scout Report (shared by Available tab and Buzz tab) */
async function openScoutReport(pid) {
  if (!pid) return;
  try {
    const res = await fetch('/api/draft/scout_report?player_id=' + encodeURIComponent(pid));
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
}
document.getElementById('btn-scout').addEventListener('click', () => {
  const p = draftState.selected;
  if (!p) return alert('Select a prospect first.');
  openScoutReport(p.id);
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

/* ---------- Buzz tab ---------- */
const BUZZ_KINDS = {
  headline: { label: 'Headline', cls: 'k-head' },
  beat: { label: 'Beat', cls: 'k-beat' },
  reach: { label: 'Reach', cls: 'k-reach' },
  steal: { label: 'Steal', cls: 'k-steal' },
  milestone: { label: 'Milestone', cls: 'k-mile' },
  pick: { label: 'Pick', cls: 'k-pick' },
};

async function loadBuzz() {
  const host = document.getElementById('buzz-list');
  try {
    const res = await fetch('/api/draft/buzz');
    const data = await res.json();
    renderBuzz(host, data.items || []);
  } catch (e) {
    console.error(e);
    host.innerHTML = '<div class="empty">Could not load draft buzz.</div>';
  }
}

function renderBuzz(host, items) {
  if (!items.length) {
    host.innerHTML = '<div class="empty">No buzz yet.<br>The rumor mill fires up once the draft class takes shape.</div>';
    return;
  }
  host.innerHTML = '';
  for (const it of items) {
    const k = BUZZ_KINDS[it.kind] || BUZZ_KINDS.pick;
    const el = document.createElement('article');
    el.className = 'buzz-card' + (it.prospect_id ? ' has-prospect' : '');
    el.innerHTML = `
      <div class="buzz-top">
        <span class="buzz-kind ${k.cls}">${k.label}</span>
        ${it.overall ? `<span class="buzz-overall">Pick #${it.overall}</span>` : ''}
        ${it.team ? `<span class="buzz-team clickable-text" data-href="/team/${encodeURIComponent(it.team)}" title="Open team overview">${esc(it.team)}</span>` : ''}
      </div>
      <div class="buzz-title">${esc(it.title)}</div>
      <p class="buzz-text">${esc(it.text)}</p>
      ${it.prospect_id ? `<div class="buzz-foot"><span class="buzz-scout">View scout report →</span></div>` : ''}`;
    if (it.prospect_id) {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.clickable-text[data-href]')) return; // team link navigates
        openScoutReport(it.prospect_id);
      });
    }
    host.appendChild(el);
  }
}

/* ---------- Trade Feed tab ---------- */
async function loadTradeFeed() {
  const host = document.getElementById('trade-list');
  try {
    const res = await fetch('/api/draft/trade_feed');
    const data = await res.json();
    renderTradeFeed(host, data.deals || []);
  } catch (e) {
    console.error(e);
    host.innerHTML = '<div class="empty">Could not load the trade feed.</div>';
  }
}

function linkifyTeams(escapedText, teams) {
  let out = escapedText;
  const sorted = (teams || []).slice().sort((a, b) => b.length - a.length);
  for (const name of sorted) {
    if (!name) continue;
    const en = esc(name);
    if (out.indexOf(en) === -1) continue;
    out = out.split(en).join(
      `<span class="clickable-text" data-href="/team/${encodeURIComponent(name)}" title="Open team overview">${en}</span>`);
  }
  return out;
}

function renderTradeFeed(host, deals) {
  if (!deals.length) {
    host.innerHTML = '<div class="empty">No draft-day trades recorded yet.<br>Deals made on draft day land here, newest first.</div>';
    return;
  }
  host.innerHTML = '';
  for (const d of deals) {
    const el = document.createElement('div');
    el.className = 'trade-row' + (d.kind === 'rumor' ? ' is-rumor' : '');
    el.innerHTML = `
      <div class="trade-side">
        <span class="trade-kind ${d.kind === 'rumor' ? 'k-beat' : 'k-steal'}">${d.kind === 'rumor' ? 'Rumor' : 'Deal'}</span>
        ${d.year ? `<span class="trade-year">${d.year}</span>` : ''}
      </div>
      <div class="trade-text">${linkifyTeams(esc(d.text), d.teams || [])}</div>`;
    host.appendChild(el);
  }
}

/* ---------- Grades tab ---------- */
async function loadGrades() {
  const host = document.getElementById('grades-list');
  const head = document.getElementById('grades-head');
  try {
    const res = await fetch('/api/draft/grades');
    const data = await res.json();
    renderGrades(head, host, data);
  } catch (e) {
    console.error(e);
    head.innerHTML = '';
    host.innerHTML = '<div class="empty">Could not load draft grades.</div>';
  }
}

function renderGrades(head, host, data) {
  const rows = data.grades || [];
  if (!rows.length) {
    head.innerHTML = '';
    host.innerHTML = '<div class="empty">No drafts to grade yet.<br>Grades post here once a draft finishes —<br>or mid-draft as a live projection.</div>';
    return;
  }
  const isLive = data.source === 'live';
  head.innerHTML = `
    <span class="sum-pill ${isLive ? 'mine' : ''}">${isLive ? 'Live Projection' : 'Final Grades'}${data.year ? ' — ' + data.year + ' Entry Draft' : ''}</span>
    ${data.note ? `<span class="grades-note">${esc(data.note)}</span>` : ''}`;
  host.innerHTML = '';
  rows.forEach((g, i) => {
    const el = document.createElement('div');
    el.className = 'grade-row';
    el.innerHTML = `
      <div class="grade-rank">${i + 1}</div>
      <div class="grade-team"><span class="clickable-text" data-href="/team/${encodeURIComponent(g.name)}" title="Open team overview">${esc(g.name)}</span></div>
      <div class="grade-score">${Number(g.score).toFixed(2)}×</div>
      <div class="grade-badge" style="background:${esc(g.color || '#666')}">${esc(g.grade)}</div>
      <div class="grade-caret">▾</div>`;
    const detail = document.createElement('div');
    detail.className = 'grade-detail';
    detail.hidden = true;
    if (g.picks && g.picks.length) {
      detail.innerHTML = g.picks.map(p => `
        <div class="gpick-row">
          <span class="gpick-num">#${p.overall}</span>
          <span class="gpick-rd">Rd ${p.round}</span>
          <span class="gpick-name clickable-text" data-href="/player/${encodeURIComponent(p.player_id)}" title="Open player profile">${esc(p.player)}</span>
          <span class="gpick-vals">slot ${p.expected.toLocaleString()} vs value ${p.value.toLocaleString()}
            <b class="${p.delta >= 0 ? 'pos' : 'neg'}">${p.delta >= 0 ? '+' : ''}${p.delta.toLocaleString()}</b></span>
        </div>`).join('');
    } else {
      detail.innerHTML = `<div class="grade-why">Graded on total player value vs expected slot value across the class (engine curve): <b>${Number(g.score).toFixed(2)}×</b> expected value.</div>`;
    }
    el.addEventListener('click', (e) => {
      if (e.target.closest('.clickable-text[data-href]')) return; // team link navigates
      detail.hidden = !detail.hidden;
      el.classList.toggle('open', !detail.hidden);
    });
    host.appendChild(el);
    host.appendChild(detail);
  });
}
