/* Puck Dynasty Media Center: wire / journalists / narratives / fines / fan buzz */
'use strict';

const MC = {
  tab: 'wire',
  wireFilter: 'All',
  wireSearch: '',
  cache: {},
};

const ENDPOINTS = {
  wire: '/api/news/wire',
  journalists: '/api/news/journalists',
  narratives: '/api/news/narratives',
  fines: '/api/news/fines',
  fanbuzz: '/api/news/fanbuzz',
};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

/* Category -> accent color (deep blue family + broadcast primaries; never teal) */
const CAT_COLORS = {
  'Prospects': '#3B82F6', 'Coaches': '#a78bfa', 'Rumors': '#f59e0b',
  'Draft': '#fb923c', 'Milestones': '#fbbf24', 'Players': '#4ade80',
  'Teams': '#f472b6', 'Injuries': '#f87171', 'Discipline': '#ef4444',
  'Signings': '#60a5fa', 'League': '#94a3b8',
};
function catColor(c) { return CAT_COLORS[c] || '#94a3b8'; }

const ARCH_STYLE = {
  stirrer:   {label: 'Stirrer',   color: '#f87171'},
  loyalist:  {label: 'Loyalist',  color: '#4ade80'},
  neutral:   {label: 'Neutral',   color: '#94a3b8'},
};

const SENT_STYLE = {
  'Electric': '#fbbf24', 'Happy': '#4ade80', 'Content': '#94a3b8',
  'Restless': '#f59e0b', 'Disgruntled': '#f87171', 'Toxic': '#ef4444',
};

/* ---------- tab switching ---------- */
function switchTab(tab) {
  MC.tab = tab;
  document.querySelectorAll('#media-tabs .tb-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.media-pane').forEach(p =>
    p.hidden = (p.id !== 'tab-' + tab));
  loadTab(tab);
}

async function loadTab(tab) {
  if (MC.cache[tab]) { renderTab(tab, MC.cache[tab]); return; }
  try {
    const res = await fetch(ENDPOINTS[tab]);
    const data = await res.json();
    MC.cache[tab] = data;
    renderTab(tab, data);
  } catch (e) { console.error('media center ' + tab, e); }
}

function renderTab(tab, data) {
  ({wire: renderWire, journalists: renderJournalists, narratives: renderNarratives,
    fines: renderFines, fanbuzz: renderFanbuzz}[tab] || (() => {}))(data);
  updateBadges(data, tab);
}

function updateBadges(data, tab) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v > 0 ? v : '';
  };
  if (tab === 'wire') set('badge-wire', data.count);
  if (tab === 'journalists') set('badge-journalists', data.count);
  if (tab === 'narratives') set('badge-narratives', data.count);
  if (tab === 'fines') set('badge-fines', data.count);
  if (tab === 'fanbuzz') set('badge-fanbuzz', data.count);
  const parts = [];
  if (MC.cache.wire) parts.push(MC.cache.wire.count + ' stories');
  if (MC.cache.narratives) parts.push(MC.cache.narratives.count + ' storylines');
  if (MC.cache.fines && MC.cache.fines.count) parts.push(MC.cache.fines.count + ' fines');
  const nc = document.getElementById('news-count');
  if (nc && parts.length) nc.textContent = parts.join(' · ');
}

/* ---------- 1. news wire ---------- */
function renderWire(data) {
  const items = data.items || [];
  const chips = document.getElementById('wire-chips');
  const cats = ['All'].concat(data.categories || []);
  chips.hidden = items.length === 0;
  chips.innerHTML = cats.map(c =>
    `<button class="chip${MC.wireFilter === c ? ' active' : ''}" data-cat="${esc(c)}">${esc(c)}</button>`
  ).join('');
  const feed = document.getElementById('wire-feed');
  document.getElementById('wire-empty').hidden = items.length > 0;
  feed.innerHTML = '';
  const q = (MC.wireSearch || '').toLowerCase();
  const filtered = items.filter(it => (MC.wireFilter === 'All' || it.category === MC.wireFilter) && (!q || (it.story || '').toLowerCase().includes(q)));
  if (!filtered.length) {
    feed.innerHTML = items.length > 0
      ? '<div class="filter-note">No stories in this category yet.</div>' : '';
    return;
  }
  // Batch D: two-pane reader — headline list on the left, full story on
  // the right (desktop media-window parity).
  const wrap = document.createElement('div');
  wrap.className = 'news-twopane';
  const listEl = document.createElement('div');
  listEl.className = 'news-list';
  const readerEl = document.createElement('article');
  readerEl.className = 'news-reader';
  wrap.appendChild(listEl);
  wrap.appendChild(readerEl);
  feed.appendChild(wrap);

  const paint = (sel) => {
    const item = filtered[sel];
    readerEl.style.borderLeftColor = catColor(item.category);
    const teams = (item.teams || []).map(t =>
      `<a class="team-chip" href="${esc(t.url)}">${esc(t.name)}</a>`).join('');
    readerEl.innerHTML = `
      <div class="news-item-head">
        <span class="cat-tag" style="background:${catColor(item.category)}22;color:${catColor(item.category)};border-color:${catColor(item.category)}55">${esc(item.category)}</span>
        <span class="news-date">${esc(item.date_label || '')}</span>
      </div>
      <p>${esc(item.story)}</p>
      <div class="news-detail">
        ${teams ? `<div class="news-teams"><span class="detail-k">Teams</span>${teams}</div>` : ''}
        <div class="news-full-date"><span class="detail-k">Filed</span> ${esc(item.date_label || 'Unknown date')}</div>
      </div>`;
    listEl.querySelectorAll('.news-list-row').forEach((r, i) =>
      r.classList.toggle('active', i === sel));
  };

  filtered.forEach((item, i) => {
    const r = document.createElement('button');
    r.className = 'news-list-row';
    const head = String(item.story || '').split('\n')[0].slice(0, 110);
    r.innerHTML = `
      <span class="cat-dot" style="background:${catColor(item.category)}"></span>
      <span class="news-list-text">${esc(head)}</span>
      <span class="news-list-date">${esc(item.date_label || '')}</span>`;
    r.addEventListener('click', () => paint(i));
    listEl.appendChild(r);
  });
  paint(0);
}

/* ---------- wire search + refresh (Batch C minor) ---------- */
document.getElementById('wire-search').addEventListener('input', e => {
  MC.wireSearch = e.target.value;
  if (MC.cache.wire) renderWire(MC.cache.wire);
});
document.getElementById('wire-refresh').addEventListener('click', async () => {
  const btn = document.getElementById('wire-refresh');
  const fresh = document.getElementById('wire-fresh');
  btn.disabled = true;
  try {
    const d = await (await fetch('/api/news/refresh', { method: 'POST' })).json();
    if (d.ok) {
      delete MC.cache.wire; // force a re-pull of the wire
      await loadTab('wire');
      fresh.textContent = `${d.count} stories${d.latest ? ' · latest ' + d.latest : ''}`;
    } else {
      fresh.textContent = 'Refresh failed';
    }
  } catch (e) {
    fresh.textContent = 'Refresh failed';
  }
  btn.disabled = false;
  setTimeout(() => { fresh.textContent = ''; }, 8000);
});

document.addEventListener('click', e => {
  const chip = e.target.closest('#wire-chips .chip');
  if (chip) {
    MC.wireFilter = chip.dataset.cat;
    document.querySelectorAll('#wire-chips .chip').forEach(c =>
      c.classList.toggle('active', c === chip));
    if (MC.cache.wire) renderWire(MC.cache.wire);
  }
  const tab = e.target.closest('#media-tabs .tb-tab');
  if (tab) switchTab(tab.dataset.tab);
});

/* ---------- 2. journalists ---------- */
function profileBar(label, val) {
  const v = Math.max(0, Math.min(100, val));
  return `<div class="prof-row"><span class="prof-k">${label}</span>
    <div class="prof-bar"><div class="prof-fill" style="width:${v}%"></div></div>
    <span class="prof-v">${v}</span></div>`;
}

function renderJournalists(data) {
  const markets = data.markets || [];
  document.getElementById('jour-empty').hidden = markets.length > 0;
  const intro = document.getElementById('jour-intro');
  intro.innerHTML = markets.length
    ? `<span>${esc(String(data.count))} reporters across ${esc(String(markets.length))} markets.</span>
       <span class="dim">Markets ranked by media intensity — the fishbowls lead.</span>`
    : '';
  const grid = document.getElementById('jour-grid');
  grid.innerHTML = '';
  for (const m of markets) {
    const card = document.createElement('div');
    card.className = 'jour-card';
    const reps = (m.reporters || []).map(r => {
      const st = ARCH_STYLE[r.archetype] || ARCH_STYLE.neutral;
      return `<div class="jour-rep">
        <div class="jour-rep-head">
          <span class="jour-name">${esc(r.name)}</span>
          <span class="arch-tag" style="color:${st.color};border-color:${st.color}55;background:${st.color}1c">${st.label}</span>
        </div>
        <div class="jour-blurb">${esc(r.archetype_blurb || '')}</div>
        <div class="jour-stats">
          <span title="Credibility">⭐ ${esc(String(r.credibility))}</span>
          <span title="Fan approval">👍 ${esc(String(r.fan_approval))}</span>
        </div>
      </div>`;
    }).join('');
    card.innerHTML = `
      <a class="jour-market" href="${esc(m.url)}">${esc(m.market)}</a>
      <div class="jour-prof">${profileBar('Intensity', m.intensity)}${profileBar('Adversarial', m.adversarial)}${profileBar('Loyalty', m.loyalty)}${profileBar('Patience', m.patience)}</div>
      <div class="jour-reps">${reps}</div>`;
    grid.appendChild(card);
  }
}

/* ---------- 3. narratives & beefs ---------- */
function renderNarratives(data) {
  const narrs = data.narratives || [];
  const beefs = data.beefs || [];
  document.getElementById('narr-empty').hidden = (narrs.length + beefs.length) > 0;
  document.getElementById('narr-head').hidden = narrs.length === 0;
  document.getElementById('beef-head').hidden = beefs.length === 0;
  const list = document.getElementById('narr-list');
  list.innerHTML = '';
  for (const n of narrs) {
    const heat = Math.max(0, Math.min(100, n.heat));
    const heatColor = heat >= 70 ? '#ef4444' : heat >= 40 ? '#f59e0b' : '#3B82F6';
    const subs = (n.subjects || []).map(s => `<span class="subj-chip">${esc(s.name)}</span>`).join('');
    const el = document.createElement('div');
    el.className = 'narr-card';
    el.innerHTML = `
      <div class="narr-top">
        <span class="cat-tag" style="background:#3B82F622;color:#3B82F6;border-color:#3B82F655">${esc(n.kind_label)}</span>
        ${n.team_url ? `<a class="team-chip" href="${esc(n.team_url)}">${esc(n.team)}</a>` : `<span class="dim">${esc(n.team)}</span>`}
      </div>
      <div class="narr-title">${esc(n.title)}</div>
      ${subs ? `<div class="narr-subs"><span class="detail-k">Subjects</span>${subs}</div>` : ''}
      <div class="heat-row"><span class="detail-k">Heat</span>
        <div class="heat-bar"><div class="heat-fill" style="width:${heat}%;background:${heatColor}"></div></div>
        <span class="heat-v">${esc(String(n.heat))}</span></div>`;
    list.appendChild(el);
  }
  const bl = document.getElementById('beef-list');
  bl.innerHTML = '';
  for (const b of beefs) {
    const lvlColor = b.level >= 3 ? '#ef4444' : b.level === 2 ? '#f59e0b' : '#94a3b8';
    const el = document.createElement('div');
    el.className = 'narr-card beef';
    el.innerHTML = `
      <div class="narr-top">
        <span class="cat-tag" style="color:${lvlColor};border-color:${lvlColor}55;background:${lvlColor}1c">⚔️ ${esc(b.level_label)}</span>
        ${b.team_url ? `<a class="team-chip" href="${esc(b.team_url)}">${esc(b.team)}</a>` : `<span class="dim">${esc(b.team)}</span>`}
      </div>
      <div class="narr-title">${esc(b.coach)} <span class="dim">vs.</span> ${esc(b.reporter)}</div>
      <div class="dim">${b.days_quiet ? esc(String(b.days_quiet)) + ' quiet days' : 'Fresh exchange'}</div>`;
    bl.appendChild(el);
  }
}

/* ---------- 4. fines ledger ---------- */
function renderFines(data) {
  const fines = data.fines || [];
  document.getElementById('fines-empty').hidden = fines.length > 0;
  const sum = document.getElementById('fines-summary');
  sum.hidden = fines.length === 0;
  if (fines.length) {
    sum.innerHTML = `<div class="fines-total"><span class="fines-total-k">Season total</span>
      <span class="fines-total-v">${esc(data.season_total_label || '$0')}</span></div>
      <div class="dim">${esc(String(data.count))} fine${data.count === 1 ? '' : 's'} handed down</div>`;
  }
  const list = document.getElementById('fines-list');
  list.innerHTML = '';
  for (const f of fines) {
    const el = document.createElement('div');
    el.className = 'fine-row';
    el.innerHTML = `
      <div class="fine-amount">${esc(f.amount_label)}</div>
      <div class="fine-main">
        <div class="fine-name">${esc(f.name)}${f.role ? ` <span class="dim">(${esc(f.role)})</span>` : ''}</div>
        <div class="fine-reason">${esc(f.reason)}</div>
        <div class="fine-meta">${f.team_url ? `<a class="team-chip" href="${esc(f.team_url)}">${esc(f.team)}</a>` : esc(f.team)}${f.date_label ? ` <span class="dim">· ${esc(f.date_label)}</span>` : ''}</div>
      </div>`;
    list.appendChild(el);
  }
}

/* ---------- 5. fan buzz ---------- */
function renderFanbuzz(data) {
  const teams = data.teams || [];
  document.getElementById('buzz-empty').hidden = teams.length > 0;
  const sum = document.getElementById('buzz-summary');
  sum.hidden = teams.length === 0;
  if (teams.length) {
    const s = data.summary || {};
    const order = ['Electric', 'Happy', 'Content', 'Restless', 'Disgruntled', 'Toxic'];
    sum.innerHTML = order.filter(k => s[k]).map(k =>
      `<span class="buzz-pill" style="border-color:${SENT_STYLE[k]}66;color:${SENT_STYLE[k]}">${esc(k)} · ${esc(String(s[k]))}</span>`
    ).join('');
  }
  const grid = document.getElementById('buzz-grid');
  grid.innerHTML = '';
  for (const t of teams) {
    const c = SENT_STYLE[t.label] || '#94a3b8';
    const v = Math.max(0, Math.min(100, t.sentiment));
    const drivers = (t.drivers || []).map(d => {
      const delta = Number(d.delta) || 0;
      const cls = delta > 0 ? 'up' : delta < 0 ? 'down' : '';
      const sign = delta > 0 ? '+' : '';
      return `<div class="driver"><span class="driver-delta ${cls}">${sign}${esc(String(d.delta))}</span>
        <span class="driver-reason">${esc(d.reason || '—')}</span>
        ${d.date ? `<span class="dim driver-date">${esc(d.date)}</span>` : ''}</div>`;
    }).join('');
    const el = document.createElement('div');
    el.className = 'buzz-card';
    el.innerHTML = `
      <a class="buzz-team" href="${esc(t.url)}">${esc(t.name)}</a>
      <div class="buzz-line">
        <span class="sent-tag" style="color:${c};border-color:${c}66;background:${c}1c">${esc(t.label)}</span>
        <span class="buzz-val">${esc(String(t.sentiment))}</span>
      </div>
      <div class="sent-bar"><div class="sent-fill" style="width:${v}%;background:${c}"></div></div>
      <div class="buzz-tone dim">Media tone: <b>${esc(t.media_tone)}</b></div>
      ${drivers ? `<div class="buzz-drivers"><div class="detail-k">Recent buzz</div>${drivers}</div>` : '<div class="dim">No recorded buzz drivers.</div>'}`;
    grid.appendChild(el);
  }
}

/* ---------- boot ---------- */
loadTab('wire');

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
