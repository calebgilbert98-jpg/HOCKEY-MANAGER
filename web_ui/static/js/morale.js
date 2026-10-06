/* Puck Dynasty web morale — full dressing room */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function chemColor(s) {
  if (s >= 65) return '#4CAF50';
  if (s >= 50) return '#FFC107';
  return '#F44336';
}

function respClass(r) {
  if (r === 'Bought in') return 'good';
  if (r === 'Tuning out') return 'warn';
  if (r === 'Quit on coach') return 'bad';
  return 'neutral';
}

async function loadMorale() {
  try {
    const res = await fetch('/api/morale');
    const d = await res.json();
    if (d.error) return;

    // Headline
    const chem = d.chemistry || {};
    document.getElementById('morale-headline').textContent =
      `Chemistry ${chem.score ?? '—'}/100 ${chem.label || ''}`;

    // Coach card
    const coach = d.coach;
    document.getElementById('coach-body').innerHTML = coach ? `
      <div class="coach-name">${coach.id ? `<span class="clickable-text" data-href="/staff/${esc(coach.id)}" title="Open staff profile">${esc(coach.name)}</span>` : esc(coach.name)}</div>
      <div class="coach-style">${esc(coach.style)}</div>
      <div class="dim">${esc(coach.description || '')}</div>
      <div class="coach-meta">GM trust: ${coach.gm_trust}/100</div>` :
      '<div class="dim">No head coach on staff.</div>';
    const lcBtn = document.getElementById('line-control-btn');
    if (lcBtn && coach) lcBtn.textContent =
      'Lines: ' + (coach.line_control === 'gm' ? 'YOU (GM)' : 'Coach');

    // Watch list
    const wl = d.watch_list || [];
    document.getElementById('watch-body').innerHTML = wl.length ?
      wl.map(i => {
        const icon = i.severity === 'high' ? '🔴' : i.severity === 'medium' ? '🟡' : '🟢';
        return `<div class="watch-item">${icon} ${esc(i.text)}</div>`;
      }).join('') :
      '<div class="dim">🟢 No structural issues detected. The room is stable.</div>';

    // Player response table
    document.getElementById('response-body').innerHTML = (d.players || []).map(p => `
      <tr>
        <td>${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}" title="Open player profile"><strong>${esc(p.name)}</strong></span>` : `<strong>${esc(p.name)}</strong>`}</td>
        <td>${esc(p.engagement || '—')}</td>
        <td><span class="resp resp-${respClass(p.response)}">${esc(p.response)}</span></td>
        <td>${p.happiness}/100</td>
        <td>${p.morale}</td>
        <td>${esc(p.tier)}</td>
      </tr>`).join('');

    // Dynamics feed
    const feed = d.feed || [];
    document.getElementById('feed-body').innerHTML = feed.length ?
      feed.map(e => {
        const icon = e.tone === 'up' ? '▲' : e.tone === 'down' ? '▼' : '•';
        const cls = e.tone === 'up' ? 'up' : e.tone === 'down' ? 'down' : '';
        return `<div class="feed-item"><span class="feed-icon ${cls}">${icon}</span>
          <span>${esc(e.date)} ${esc(e.text)}</span></div>`;
      }).join('') :
      '<div class="dim">No dynamics yet this season.</div>';

    // Hierarchy
    document.getElementById('hierarchy-body').innerHTML = (d.hierarchy || []).map(h => `
      <div class="hier-row"><strong>${esc(h.tier)}</strong> (${h.count}):
        ${esc(h.names.join(', '))}</div>`).join('');
  } catch (e) { console.error(e); }
}

// GM actions
document.querySelectorAll('#coach-card [data-action]').forEach(btn =>
  btn.addEventListener('click', async () => {
    const action = btn.dataset.action;
    btn.disabled = true;
    try {
      await fetch('/api/morale/action', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action}),
      });
      setTimeout(loadMorale, 1200);
    } catch (e) { console.error(e); }
    btn.disabled = false;
  }));

loadMorale();

/* ---- tabs: Room | Social Groups | Cascades | Team Talk ---- */
document.getElementById('morale-tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-tab]');
  if (!btn) return;
  document.querySelectorAll('#morale-tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const tab = btn.dataset.tab;
  ['room', 'groups', 'cascades', 'talk'].forEach(t =>
    document.getElementById('view-' + t).classList.toggle('hidden', t !== tab));
  if (tab === 'groups') renderSocial();
  if (tab === 'cascades') renderCascades();
  if (tab === 'talk') renderTalk();
});

let MDATA = null;
async function moraleData() {
  if (MDATA) return MDATA;
  const res = await fetch('/api/morale');
  MDATA = await res.json();
  return MDATA;
}

function barColor(v) {
  if (v >= 65) return '#4CAF50';
  if (v >= 50) return '#FFC107';
  return '#F44336';
}
function bar(v) {
  return `<div class="mini-bar"><div class="mini-fill" style="width:${Math.max(0, Math.min(100, v))}%;background:${barColor(v)}"></div></div>`;
}

async function renderSocial() {
  try {
    const d = await moraleData();
    const s = d.social || {};
    const atmo = s.atmosphere;
    document.getElementById('atmosphere-body').innerHTML = atmo ? `
      <div class="atmo-head">
        <div class="atmo-label">${esc(atmo.label)}</div>
        <div class="atmo-score" style="color:${barColor(atmo.score)}">${atmo.score}/100</div>
      </div>
      <div class="atmo-row"><span class="dim">Mood</span>${bar(atmo.mood)}<strong>${atmo.mood}</strong></div>
      <div class="atmo-row"><span class="dim">Cohesion</span>${bar(atmo.cohesion)}<strong>${atmo.cohesion}</strong></div>
      <p class="dim small">Mood is the room's mean morale; cohesion is how much of the roster sits inside bonded groups.</p>` :
      '<div class="dim">No dressing-room data yet.</div>';

    const grid = document.getElementById('clique-grid');
    grid.innerHTML = (s.cliques || []).map(c => `
      <div class="morale-card clique-card">
        <div class="clique-head">
          <h3 style="margin:0">${esc(c.name)}</h3>
          <span class="clique-kind">${esc(c.kind || '')}</span>
        </div>
        <div class="clique-meta dim">
          ${c.size} members · bond ${Math.round((c.bond || 0) * 100)}% · voice: <strong>${esc(c.leader || '—')}</strong>
          ${c.mean_age != null ? ` · avg age ${c.mean_age}` : ''}
          ${c.nationality ? ` · ${esc(c.nationality)}` : ''}
        </div>
        <div class="clique-mood"><span class="dim">Mood</span>${bar(c.mood)}<strong>${c.mood}</strong></div>
        <div class="clique-members">${(c.members || []).map(m =>
          m.id
            ? `<span class="clickable-text member-chip" data-href="/player/${esc(m.id)}" title="Open player profile">${esc(m.name)}</span>`
            : `<span class="member-chip">${esc(m.name)}</span>`).join('')}</div>
      </div>`).join('') || '<div class="dim">No circles formed yet — the room is all floaters.</div>';

    const fl = s.floaters || [];
    document.getElementById('floaters-body').innerHTML = fl.length ?
      fl.map(f => f.id
        ? `<span class="clickable-text member-chip" data-href="/player/${esc(f.id)}" title="Open player profile">${esc(f.name)}</span>`
        : `<span class="member-chip">${esc(f.name)}</span>`).join('') :
      '<div class="dim">Everyone belongs somewhere. Rare air.</div>';
  } catch (e) { console.error(e); }
}

async function renderCascades() {
  try {
    const d = await moraleData();
    const c = d.cascades || {};
    const log = c.log || [];
    document.getElementById('cascade-log').innerHTML = log.length ?
      log.slice().reverse().map(l => `<div class="feed-item"><span class="feed-icon">•</span><span>${esc(l)}</span></div>`).join('') :
      '<div class="dim">Nothing has shaken the room yet this season.</div>';
    const arr = c.arrivals || [];
    document.getElementById('arrivals-body').innerHTML = arr.length ?
      arr.map(a => `
        <div class="arrival-row">
          <div>${a.id ? `<span class="clickable-text" data-href="/player/${esc(a.id)}" title="Open player profile"><strong>${esc(a.name)}</strong></span>` : `<strong>${esc(a.name)}</strong>`}</div>
          <div class="atmo-row"><span class="dim">Settled</span>${bar(a.integration)}<strong>${a.integration}%</strong></div>
        </div>`).join('') :
      '<div class="dim">No new faces this season.</div>';
  } catch (e) { console.error(e); }
}

/* ---- team talk ---- */
const talkState = {tone: 'calm', situation: 'pregame', score: 'tied', speaker: 'coach', rival: false, streak: 0};
let talkDebounce = null;

const TIER_LABEL = {landed: 'Landed (+2)', steady: 'Steady (+1)', flat: 'Flat (0)', backfired: 'Backfired (−1)'};
const TIER_CLASS = {landed: 'good', steady: 'neutral', flat: 'warn', backfired: 'bad'};

function syncTalkState() {
  talkState.situation = document.querySelector('#talk-situation .active')?.dataset.v || 'pregame';
  talkState.score = document.querySelector('#talk-score .active')?.dataset.v || 'tied';
  talkState.speaker = document.querySelector('#talk-speaker .active')?.dataset.v || 'coach';
  talkState.rival = document.getElementById('talk-rival').checked;
  talkState.streak = parseInt(document.getElementById('talk-streak').value || '0', 10) || 0;
}

async function renderTalk() {
  try {
    const d = await moraleData();
    const t = d.talk || {};
    // Pending talks
    const pend = t.pending || {};
    const pendHtml = ['pregame', 'intermission'].map(k => {
      const p = pend[k];
      return p ? `<div class="pending-talk"><strong>${k === 'pregame' ? 'Pregame' : 'Intermission'}:</strong>
        ${esc(p.speaker)} gave a <strong>${esc(p.tone)}</strong> talk — ${esc(p.outcome)}.
        <span class="dim">${esc(p.note)}</span></div>` : '';
    }).join('');
    document.getElementById('talk-pending').innerHTML = pendHtml ||
      '<div class="dim">No talk pending — the room is waiting to hear something.</div>';

    // Speakers
    const spk = document.getElementById('talk-speaker');
    spk.innerHTML = (t.speakers || [{key: 'coach', label: 'Head Coach'}, {key: 'captain', label: 'Captain'}])
      .map((s, i) => `<button data-v="${esc(s.key)}" class="${i === 0 ? 'active' : ''}">${esc(s.label)}</button>`).join('');

    // Tones
    const tones = document.getElementById('talk-tones');
    tones.innerHTML = (t.tones || []).map(x =>
      `<button class="tone-card ${x.key === talkState.tone ? 'active' : ''}" data-tone="${esc(x.key)}">
         <strong>${esc(x.label)}</strong><span class="dim">${esc(x.blurb)}</span>
       </button>`).join('');

    updateTalkPreview();
  } catch (e) { console.error(e); }
}

async function updateTalkPreview() {
  syncTalkState();
  const host = document.getElementById('talk-preview');
  host.innerHTML = '<div class="dim">Reading the room…</div>';
  try {
    const res = await fetch('/api/morale/talk/preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        tone: talkState.tone, situation: talkState.situation,
        score_state: talkState.score, speaker: talkState.speaker,
        rival: talkState.rival, streak: talkState.streak,
      }),
    });
    const p = await res.json();
    if (!p.ok) { host.innerHTML = '<div class="dim">Preview unavailable.</div>'; return; }
    host.innerHTML = `
      <div class="preview-grid">
        <div><span class="dim">Tone fit</span><strong style="color:${barColor(p.fit)}"> ${p.fit}/100</strong>
          <span class="dim">(${esc(p.speaker_name)}, influence ${p.speaker_influence})</span></div>
        <div><span class="dim">Likely outcome</span>
          ${p.likely.map(t => `<span class="resp resp-${TIER_CLASS[t]}">${TIER_LABEL[t]}</span>`).join(' ')}</div>
      </div>
      ${p.repeat ? `<div class="repeat-warn">⚠ ${esc(p.repeat_note)}</div>` : ''}`;
  } catch (e) { host.innerHTML = '<div class="dim">Preview unavailable.</div>'; }
}

function scheduleTalkPreview() {
  clearTimeout(talkDebounce);
  talkDebounce = setTimeout(updateTalkPreview, 250);
}

document.getElementById('morale-tabs').addEventListener('click', scheduleTalkPreview);
['talk-situation', 'talk-score', 'talk-speaker'].forEach(id => {
  document.getElementById(id).addEventListener('click', e => {
    const btn = e.target.closest('button[data-v]');
    if (!btn) return;
    document.querySelectorAll('#' + id + ' button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    scheduleTalkPreview();
  });
});
document.getElementById('talk-tones').addEventListener('click', e => {
  const btn = e.target.closest('[data-tone]');
  if (!btn) return;
  talkState.tone = btn.dataset.tone;
  document.querySelectorAll('#talk-tones .tone-card').forEach(b =>
    b.classList.toggle('active', b === btn));
  scheduleTalkPreview();
});
document.getElementById('talk-rival').addEventListener('change', scheduleTalkPreview);
document.getElementById('talk-streak').addEventListener('input', scheduleTalkPreview);

document.getElementById('talk-deliver').addEventListener('click', async e => {
  const btn = e.target;
  syncTalkState();
  btn.disabled = true;
  try {
    await fetch('/api/morale/talk', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        tone: talkState.tone, situation: talkState.situation,
        score_state: talkState.score, speaker: talkState.speaker,
        rival: talkState.rival, streak: talkState.streak,
      }),
    });
    MDATA = null; // refresh pending state
    setTimeout(async () => { await renderTalk(); }, 1200);
  } catch (err) { console.error(err); }
  btn.disabled = false;
});

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
