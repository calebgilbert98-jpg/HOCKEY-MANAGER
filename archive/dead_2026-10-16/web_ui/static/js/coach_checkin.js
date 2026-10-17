/* Puck Dynasty coach check-in — quarterly conversation with the head coach.
   Trust effects are real (coach_checkins.py); voice lines are the desktop's. */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

const CI = { state: null, busy: false };
const BEAT_ORDER = ['expectations', 'room', 'rookies', 'tactics'];

async function loadCheckin() {
  try {
    const res = await fetch('/api/coach-checkin');
    const data = await res.json();
    CI.state = data;
    renderCheckin(data);
  } catch (e) { console.error(e); }
}

function renderCheckin(data) {
  const empty = document.getElementById('ci-empty');
  const layout = document.getElementById('ci-layout');
  if (!data.pending) {
    empty.hidden = false;
    layout.hidden = true;
    if (data.message) empty.textContent = data.message;
    return;
  }
  empty.hidden = true;
  layout.hidden = false;
  document.getElementById('ci-title').textContent =
    `${data.quarter_label} Check-In`;
  document.getElementById('ci-sub').textContent =
    `Game ${data.game} · mandate: ${data.mandate} · with ${data.coach_name}`;
  document.getElementById('ci-trust').textContent = Math.round(data.coach_trust);
  renderTranscript(data);
  renderBeats(data);
}

function renderTranscript(data) {
  const box = document.getElementById('ci-transcript');
  box.innerHTML = '';
  for (const r of data.transcript || []) {
    addSay(box, 'gm', 'You', r.gm_line || '');
    addSay(box, 'coach', data.coach_name.split(' ').slice(-1)[0], r.coach_line || '');
    if (r.delta) addNote(box, `Trust ${r.delta >= 0 ? '+' : ''}${r.delta}`);
  }
  box.scrollTop = box.scrollHeight;
}

function addSay(box, who, whoLabel, text) {
  const row = document.createElement('div');
  row.className = `ci-say ${who}`;
  row.innerHTML = `<div class="ci-who">${esc(whoLabel)}</div><div class="ci-text">${esc(text)}</div>`;
  box.appendChild(row);
}

function addNote(box, text) {
  const row = document.createElement('div');
  row.className = 'ci-note-line';
  row.textContent = text;
  box.appendChild(row);
}

function renderBeats(data) {
  const wrap = document.getElementById('ci-beats');
  wrap.innerHTML = '';
  const doneBeats = data.done_beats || [];
  const beatRows = document.getElementById('ci-beat-rows');
  beatRows.innerHTML = '';
  for (const r of data.transcript || []) {
    const row = document.createElement('div');
    row.className = 'ci-beat-row';
    row.innerHTML = `<div class="ci-beat-name">${esc(beatTitle(r.beat))}</div>
      <div class="ci-beat-delta ${r.delta >= 0 ? 'pos' : 'neg'}">${r.delta >= 0 ? '+' : ''}${esc(String(r.delta))}</div>`;
    beatRows.appendChild(row);
  }
  if (data.all_done) {
    document.getElementById('ci-finish').hidden = false;
    const total = (data.transcript || []).reduce((a, r) => a + (r.delta || 0), 0);
    document.getElementById('ci-summary').textContent =
      `All four beats covered. Net coach trust ${total >= 0 ? '+' : ''}${total}.`;
    return;
  }
  document.getElementById('ci-finish').hidden = true;
  const nextBeat = BEAT_ORDER.find(b => !doneBeats.includes(b));
  if (!nextBeat) return;
  const beat = data.beats[nextBeat];
  const box = document.createElement('div');
  box.className = 'ci-beat';
  let opts = '';
  for (const o of beat.options || []) {
    opts += `<button class="ci-option" data-beat="${esc(nextBeat)}" data-framing="${esc(o.key)}">
      <span class="ci-option-label">${esc(o.label)}</span>
      <span class="ci-option-line">${esc(o.line)}</span>
    </button>`;
  }
  box.innerHTML = `
    <div class="ci-beat-head">${esc(beat.title)}${beat.mandatory ? ' <span class="ci-mandatory">Bring it up</span>' : ''}</div>
    <div class="ci-beat-intro">${esc(beat.intro)}</div>
    ${opts}
    <div class="ci-hint">Pick the approach that fits the room.</div>`;
  wrap.appendChild(box);
  box.querySelectorAll('.ci-option').forEach(btn => {
    btn.addEventListener('click', () => answerBeat(btn.dataset.beat, btn.dataset.framing));
  });
}

function beatTitle(b) {
  return {expectations: 'Pace vs mandate', room: 'The room', rookies: 'Rookie usage', tactics: 'Tactics'}[b] || b;
}

async function answerBeat(beat, framing) {
  if (CI.busy) return;
  CI.busy = true;
  showResult('ci-result', true, '…');
  try {
    const res = await fetch('/api/coach-checkin/answer', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({beat, framing}),
    });
    const data = await res.json();
    if (!data.ok) { showResult('ci-result', false, 'Could not queue the answer.'); CI.busy = false; return; }
    const r = await pollCheckinResult(data.nonce, 'coach_checkin_beat');
    if (!r) { showResult('ci-result', false, 'No response from the game.'); CI.busy = false; return; }
    if (!r.ok) { showResult('ci-result', false, r.summary); CI.busy = false; return; }
    // append the exchange live, then re-render for the next beat
    const box = document.getElementById('ci-transcript');
    addSay(box, 'gm', 'You', r.gm_line || '');
    addSay(box, 'coach', (CI.state.coach_name || 'Coach').split(' ').slice(-1)[0], r.coach_line || '');
    addNote(box, `Trust ${r.delta >= 0 ? '+' : ''}${r.delta}`);
    box.scrollTop = box.scrollHeight;
    document.getElementById('ci-trust').textContent = Math.round(r.trust);
    document.getElementById('ci-result').hidden = true;
    await loadCheckin();
  } catch (e) {
    console.error(e);
    showResult('ci-result', false, 'Request failed.');
  } finally {
    CI.busy = false;
  }
}

async function finishCheckin() {
  if (CI.busy) return;
  CI.busy = true;
  try {
    const res = await fetch('/api/coach-checkin/finish', {method: 'POST'});
    const data = await res.json();
    if (!data.ok) { showResult('ci-result', false, 'Could not queue.'); CI.busy = false; return; }
    const r = await pollCheckinResult(data.nonce, 'coach_checkin_finish');
    if (!r) { showResult('ci-result', false, 'No response from the game.'); CI.busy = false; return; }
    showResult('ci-result', r.ok, r.summary);
    await loadCheckin();
  } catch (e) {
    console.error(e);
    showResult('ci-result', false, 'Request failed.');
  } finally {
    CI.busy = false;
  }
}

function showResult(elId, ok, summary) {
  const el = document.getElementById(elId);
  el.hidden = false;
  el.classList.toggle('good', !!ok);
  el.classList.toggle('bad', !ok);
  el.textContent = summary || '';
}

async function pollCheckinResult(nonce, marker) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch('/api/coach-checkin/result');
      const data = await res.json();
      const r = data.result;
      if (r && r.nonce === nonce && r.marker === marker) return r;
    } catch (e) {}
    await new Promise(r => setTimeout(r, 500));
  }
  return null;
}

document.getElementById('ci-wrap-btn').addEventListener('click', finishCheckin);

loadCheckin();

// Shared heartbeat.
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
