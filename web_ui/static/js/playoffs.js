/* Puck Dynasty web playoffs */
async function loadPlayoffs() {
  try {
    const res = await fetch('/api/playoffs');
    const data = await res.json();
    renderPlayoffs(data);
  } catch (e) { console.error(e); }
}

function renderPlayoffs(data) {
  const bracket = document.getElementById('bracket');
  const empty = document.getElementById('empty');
  const status = document.getElementById('playoffs-status');
  bracket.innerHTML = '';

  if (!data.started) {
    bracket.hidden = true;
    empty.hidden = false;
    status.textContent = 'Not yet started';
    return;
  }
  empty.hidden = true;
  bracket.hidden = false;

  if (data.champion) {
    status.textContent = `🏆 ${esc(data.champion)} win the Stanley Cup`;
  } else if (data.current_round) {
    status.textContent = `Now: ${esc(data.current_round)}`;
  }

  for (const round of data.rounds) {
    if (!round.series.length) continue;
    const col = document.createElement('div');
    col.className = 'round-col';
    const isCurrent = data.current_round === round.label;
    col.innerHTML = `<div class="round-title">${isCurrent ? '<span class="live-dot"></span>' : ''}${esc(round.label)}</div>`;
    for (const s of round.series) {
      col.appendChild(seriesCard(s));
    }
    bracket.appendChild(col);
  }
}

function seriesCard(s) {
  const el = document.createElement('div');
  el.className = 'series-card' + (s.complete ? ' done' : ' live');
  const t1w = s.complete && s.winner === s.team1;
  const t2w = s.complete && s.winner === s.team2;
  const lead1 = !s.complete && (s.leader === s.team1);
  const lead2 = !s.complete && (s.leader === s.team2);
  el.innerHTML = `
    <div class="series-row">
      <span class="series-team ${t1w ? 'winner' : 'loser'}">
        <span class="abbr-sm">${esc(s.team1)}</span>
        <span class="series-score">${s.team1_wins}</span>
      </span>
      ${t1w ? '<span class="series-note"><span class="cup">★</span></span>' : (lead1 ? '<span class="series-note">leads</span>' : '')}
    </div>
    <div class="series-row">
      <span class="series-team ${t2w ? 'winner' : 'loser'}">
        <span class="abbr-sm">${esc(s.team2)}</span>
        <span class="series-score">${s.team2_wins}</span>
      </span>
      ${t2w ? '<span class="series-note"><span class="cup">★</span></span>' : (lead2 ? '<span class="series-note">leads</span>' : '')}
    </div>`;
  if (s.complete && s.winner) {
    const note = document.createElement('div');
    note.className = 'series-note';
    note.innerHTML = `<span class="cup">🏆</span> ${esc(s.winner)} wins ${esc(s.score)}`;
    el.appendChild(note);
  }
  return el;
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadPlayoffs();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
