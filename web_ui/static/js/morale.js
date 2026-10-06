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
    if (action === 'advise_coach') { openAdviseModal(); return; }
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
loadCrisisBanner();

/* ---- tabs: Room | Social Groups | Cascades | Team Talk | Rivalries | Coach ---- */
document.getElementById('morale-tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-tab]');
  if (!btn) return;
  document.querySelectorAll('#morale-tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const tab = btn.dataset.tab;
  ['room', 'groups', 'cascades', 'talk', 'rivalries', 'coach'].forEach(t =>
    document.getElementById('view-' + t).classList.toggle('hidden', t !== tab));
  if (tab === 'groups') renderSocial();
  if (tab === 'cascades') renderCascades();
  if (tab === 'talk') renderTalk();
  if (tab === 'rivalries') renderRivalries();
  if (tab === 'coach') renderCoachCarousel();
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

/* ================= Batch B: crisis, advice, rivalries, carousel ================= */

async function moraleResult() {
  try {
    const res = await fetch('/api/morale/advice-result');
    const d = await res.json();
    return d.result || null;
  } catch (e) { return null; }
}

/* ---- Captaincy crisis banner + resolution + receipts ---- */
const CRISIS_CHOICES = [
  {key: 'keep', label: 'Back him publicly', blurb: 'The C stays. The room steadies, barely — he is on notice, not exonerated.'},
  {key: 'challenge', label: 'Challenge him privately', blurb: 'Behind closed doors. He responds (leadership +3) or resents it (trade-request risk up).'},
  {key: 'strip', label: 'Strip the C', blurb: 'The C comes off. Loyalists grieve, the rest exhale. No successor named.'},
  {key: 'reassign', label: 'Reassign the C', blurb: 'Hand the C to a named successor. Legitimacy decides whether the room buys it.'},
];

async function loadCrisisBanner() {
  const host = document.getElementById('crisis-banner');
  const rhost = document.getElementById('receipts-body');
  if (!host) return;
  try {
    const res = await fetch('/api/morale/crisis');
    const d = await res.json();
    // Receipts always render (room decisions live under every banner state).
    if (rhost) {
      const rc = d.receipts || [];
      rhost.innerHTML = rc.length ? rc.map(r => `
        <div class="receipt">
          <div class="receipt-head"><strong>${esc(r.title)}</strong>
            <span class="dim">${esc(r.date)} · choice: ${esc(r.choice)}</span></div>
          ${(r.gained || []).length ? `<div class="resp resp-good">Gained: ${(r.gained || []).map(g => `${esc(g[0])} ${g[1] > 0 ? '+' : ''}${g[1]}`).join(', ')}</div>` : ''}
          ${(r.paid || []).length ? `<div class="resp resp-bad">Paid: ${(r.paid || []).map(g => `${esc(g[0])} ${g[1]}`).join(', ')}</div>` : ''}
          ${(r.relationships || []).map(x => `<div class="dim small">• ${esc(x)}</div>`).join('')}
        </div>`).join('') :
        '<div class="dim">No room decisions on record yet this season.</div>';
    }
    const c = d.crisis;
    if (!c) { host.classList.add('hidden'); host.innerHTML = ''; return; }
    const sev = '🔴'.repeat(Math.max(1, c.severity || 1));
    host.innerHTML = `
      <div class="crisis-head">${sev} <strong>Captaincy crisis:</strong>
        ${esc(c.captain_name)} is losing the room.
        Challengers: ${esc((c.challenger_names || []).join(', ') || 'none named')}.
        No decision fixes this instantly — choose the politics you can live with.</div>
      <div class="crisis-choices">
        ${CRISIS_CHOICES.map(ch => `
          <button class="tone-card crisis-card" data-choice="${ch.key}">
            <strong>${esc(ch.label)}</strong><span class="dim">${esc(ch.blurb)}</span>
          </button>`).join('')}
      </div>
      <div id="crisis-successor" class="hidden row-flex">
        <span class="dim">Successor:</span>
        <select id="crisis-successor-pick" class="nhl-input">
          ${(c.successors || []).map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}
        </select>
        <button class="btn primary" id="crisis-confirm">Confirm reassign</button>
      </div>
      <div id="crisis-result" class="advice-result"></div>`;
    host.classList.remove('hidden');
  } catch (e) { console.error(e); }
}

document.addEventListener('click', async (e) => {
  const card = e.target.closest('.crisis-card');
  if (!card || !document.getElementById('crisis-banner').contains(card)) return;
  const choice = card.dataset.choice;
  if (choice === 'reassign') {
    document.getElementById('crisis-successor').classList.remove('hidden');
    return;
  }
  await resolveCrisis(choice, '');
});
document.addEventListener('click', async (e) => {
  if (e.target.id !== 'crisis-confirm') return;
  const pick = document.getElementById('crisis-successor-pick');
  await resolveCrisis('reassign', pick ? pick.value : '');
});

async function resolveCrisis(choice, newCaptainId) {
  const host = document.getElementById('crisis-result');
  try {
    const res = await fetch('/api/morale/crisis/resolve', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({choice, new_captain_id: newCaptainId}),
    });
    const d = await res.json();
    if (!d.ok) { host.textContent = 'Could not send: ' + (d.error || 'unknown'); return; }
    host.textContent = 'Resolving… the room reacts after the next beat.';
    setTimeout(async () => {
      const r = await moraleResult();
      if (r && r.kind === 'crisis') {
        host.innerHTML = r.ok
          ? `<div class="resp resp-neutral">${(r.lines || []).map(esc).join('<br>')}</div>`
          : `<div class="resp resp-bad">${esc(r.error || 'failed')}</div>`;
        MDATA = null;
        setTimeout(() => { loadCrisisBanner(); loadMorale(); }, 1500);
      }
    }, 1200);
  } catch (err) { console.error(err); }
}

/* ---- Advise Coach modal ---- */
let ADVISE_TYPES = [];
async function openAdviseModal() {
  const modal = document.getElementById('advise-modal');
  modal.classList.remove('hidden');
  document.getElementById('advise-result').textContent = '';
  try {
    const res = await fetch('/api/morale/advice-types');
    const d = await res.json();
    ADVISE_TYPES = d.types || [];
    const coach = d.coach;
    document.getElementById('advise-sub').textContent = coach
      ? `${coach.name} · GM trust ${coach.gm_trust}/100 — whether he listens depends on personality; brash coaches take advice as an insult.`
      : 'No head coach on staff.';
    document.getElementById('advise-types').innerHTML = ADVISE_TYPES
      .filter(t => t.key !== 'feature_player')
      .map(t => `<button class="btn secondary advise-btn" data-advice="${esc(t.key)}">${esc(t.label)}</button>`).join('');
    // Feature player picker (roster names from the response table data).
    const md = await moraleData();
    const players = (md.players || []);
    document.getElementById('feature-pick').innerHTML = players
      .map(p => `<option value="${esc(p.id || '')}">${esc(p.name)}</option>`).join('');
    if (d.featured) {
      document.getElementById('advise-result').innerHTML =
        `<div class="dim">Currently featured: <strong>${esc(d.featured.name)}</strong>. Rescind to hand usage back to the coach.</div>`;
    }
  } catch (e) { console.error(e); }
}
document.getElementById('advise-close').addEventListener('click', () =>
  document.getElementById('advise-modal').classList.add('hidden'));
document.getElementById('advise-types').addEventListener('click', async (e) => {
  const btn = e.target.closest('.advise-btn');
  if (!btn) return;
  await sendAdvice({advice: btn.dataset.advice});
});
document.getElementById('feature-request').addEventListener('click', async () => {
  const pid = document.getElementById('feature-pick').value;
  await sendAdvice({advice: 'feature_player', player_id: pid});
});
document.getElementById('feature-rescind').addEventListener('click', async () => {
  const pid = document.getElementById('feature-pick').value;
  await sendAdvice({advice: 'feature_player', player_id: pid, unfeature: true});
});

async function sendAdvice(detail) {
  const host = document.getElementById('advise-result');
  host.textContent = 'Advising…';
  try {
    await fetch('/api/morale/action', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'advise_coach', detail}),
    });
    setTimeout(async () => {
      const r = await moraleResult();
      if (r && r.kind === 'advise_coach') {
        host.innerHTML = r.ok
          ? `<div class="${r.listened ? 'resp resp-good' : 'resp resp-bad'}">${r.listened ? 'LISTENED' : 'IGNORED'}${r.probability != null ? ` (p=${Math.round(r.probability * 100)}%)` : ''}: ${esc(r.text || '')}</div>`
          : `<div class="resp resp-bad">${esc(r.error || 'Advice lost in the noise.')}</div>`;
        MDATA = null;
        setTimeout(loadMorale, 800);
      }
    }, 1200);
  } catch (e) { host.textContent = 'Could not send.'; }
}

/* ---- Rivalries ---- */
async function renderRivalries() {
  const body = document.getElementById('rivalries-body');
  try {
    const res = await fetch('/api/morale/rivalries');
    const d = await res.json();
    const icons = {coach: '🔥', team: '🏒', player: '🥊'};
    body.innerHTML = (d.entries || []).length ? (d.entries || []).map(x => `
      <div class="watch-item">${icons[x.category] || '•'} ${x.solidified ? '🔒 ' : ''}<strong>${esc(x.label)}</strong>
        <span class="dim">— heat ${x.intensity} (${esc(x.origin || 'bad blood')})</span></div>`).join('') :
      '<div class="dim">No bad blood on record. Yet.</div>';
    const tp = document.getElementById('rival-team-pick');
    const cp = document.getElementById('rival-coach-pick');
    const opts = (d.teams || []).map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join('');
    tp.innerHTML = opts || '<option>(no other teams)</option>';
    cp.innerHTML = opts || '<option>(no other teams)</option>';
    const db = document.getElementById('declared-body');
    db.innerHTML = (d.declared || []).length ? (d.declared || []).map(x => `
      <div class="watch-item">📢 Declared rival: <strong>${esc(x.label)}</strong>
        <span class="dim">(${x.intensity})</span>
        <button class="btn secondary small" data-renounce="${esc(x.kind)}" data-target="${esc(x.label)}">Renounce</button></div>`).join('') :
      '<div class="dim">No declared rivalries.</div>';
  } catch (e) { console.error(e); }
}
document.getElementById('declare-team-rival').addEventListener('click', async () => {
  const target = document.getElementById('rival-team-pick').value;
  await declareRivalry('team', target);
});
document.getElementById('declare-coach-rival').addEventListener('click', async () => {
  const target = document.getElementById('rival-coach-pick').value;
  await declareRivalry('coach', target);
});
async function declareRivalry(kind, target) {
  await fetch('/api/morale/rivalries/declare', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({kind, target}),
  });
  setTimeout(async () => {
    const r = await moraleResult();
    if (r && r.kind === 'declare_rivalry') {
      document.getElementById('declared-body').innerHTML =
        `<div class="${r.ok ? 'resp resp-good' : 'resp resp-bad'}">${esc(r.ok ? r.text : (r.error || 'failed'))}</div>`;
    }
    setTimeout(renderRivalries, 600);
  }, 1200);
}
document.getElementById('declared-body').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-renounce]');
  if (!btn) return;
  await fetch('/api/morale/rivalries/renounce', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({kind: btn.dataset.renounce, target: btn.dataset.target}),
  });
  setTimeout(async () => {
    const r = await moraleResult();
    if (r && r.kind === 'renounce_rivalry') {
      document.getElementById('declared-body').innerHTML =
        `<div class="resp resp-neutral">${esc(r.text || r.error || '')}</div>`;
    }
    setTimeout(renderRivalries, 600);
  }, 1200);
});

/* ---- Coach carousel ---- */
async function renderCoachCarousel() {
  const cur = document.getElementById('carousel-current');
  const list = document.getElementById('carousel-list');
  const hot = document.getElementById('hotseat-body');
  try {
    const res = await fetch('/api/morale/coach/candidates');
    const d = await res.json();
    const c = d.current;
    cur.innerHTML = c ? `
      <div class="coach-name">${c.id ? `<span class="clickable-text" data-href="/staff/${esc(c.id)}" title="Open staff profile">${esc(c.name)}</span>` : esc(c.name)}</div>
      <div class="coach-style">${esc(c.style)} ${c.axis ? `(${esc(c.axis)})` : ''}</div>
      <div class="coach-meta">GM trust: ${c.gm_trust}/100${c.shelf_weeks ? ` · message age ${c.shelf_weeks} wks` : ''}</div>` :
      '<div class="dim">No head coach. The carousel is your friend — pick below.</div>';
    hot.innerHTML = d.hot_seat ? `<div class="repeat-warn">🔥 ${esc(JSON.stringify(d.hot_seat))}</div>` : '';
    const archIcon = {retread: '♻️', specialist: '📋', 'fresh blood': '🌱'};
    list.innerHTML = (d.candidates || []).length ? (d.candidates || []).map(x => `
      <div class="candidate-row">
        <div class="candidate-head">${archIcon[x.archetype] || '•'} <strong>${esc(x.name)}</strong>
          <span class="dim">${esc(x.archetype)}${x.source === 'promotion' ? ' · in-house' : ' · carousel'}</span></div>
        <div class="dim small">${esc(x.note || '')}</div>
        <button class="btn secondary small" data-hire-idx="${x.idx}">Hire</button>
      </div>`).join('') :
      '<div class="dim">No candidates on the carousel right now.</div>';
  } catch (e) { console.error(e); }
}
document.getElementById('carousel-list').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-hire-idx]');
  if (!btn) return;
  btn.disabled = true;
  try {
    await fetch('/api/morale/coach/hire', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({candidate_idx: parseInt(btn.dataset.hireIdx, 10)}),
    });
    setTimeout(async () => {
      const r = await moraleResult();
      if (r && r.kind === 'hire_coach') {
        btn.closest('.candidate-row').insertAdjacentHTML('beforeend',
          `<div class="${r.ok ? 'resp resp-good' : 'resp resp-bad'}">${esc(r.ok ? (r.lines || []).join(' ') : (r.error || 'failed'))}</div>`);
      }
      MDATA = null;
      setTimeout(() => { renderCoachCarousel(); loadMorale(); }, 1500);
    }, 1200);
  } catch (err) { console.error(err); btn.disabled = false; }
});
document.getElementById('fire-coach-btn').addEventListener('click', async (e) => {
  const btn = e.target;
  if (!btn.dataset.armed) {
    btn.dataset.armed = '1';
    btn.textContent = 'Confirm: fire the coach?';
    setTimeout(() => { delete btn.dataset.armed; btn.textContent = 'Fire Coach'; }, 4000);
    return;
  }
  delete btn.dataset.armed;
  btn.textContent = 'Fire Coach';
  btn.disabled = true;
  try {
    await fetch('/api/morale/coach/fire', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({reason: 'fired'}),
    });
    setTimeout(async () => {
      const r = await moraleResult();
      document.getElementById('carousel-current').insertAdjacentHTML('beforeend',
        r && r.kind === 'fire_coach'
          ? `<div class="${r.ok ? 'resp resp-neutral' : 'resp resp-bad'}">${esc(r.ok ? r.text : (r.error || 'failed'))}</div>`
          : '');
      MDATA = null;
      setTimeout(() => { renderCoachCarousel(); loadMorale(); }, 1500);
    }, 1200);
  } catch (err) { console.error(err); }
  btn.disabled = false;
});
