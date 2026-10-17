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
  const banner = document.getElementById('proj-banner');
  bracket.innerHTML = '';

  // Projection banner: before Round 1 the bracket is a standings
  // projection (desktop _set_projection_banner ~2221).
  if (!data.started && data.is_projection) {
    banner.hidden = false;
    loadProjection();
  } else {
    banner.hidden = true;
  }

  if (!data.started && !data.is_projection) {
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
  } else if (data.is_projection) {
    status.textContent = 'Projected bracket';
  }

  for (const round of data.rounds) {
    if (!round.series.length) continue;
    bracket.appendChild(roundCol(round, data));
  }
}

function roundCol(round, data) {
  const col = document.createElement('div');
  col.className = 'round-col';
  const isCurrent = data.current_round === round.label;
  col.innerHTML = `<div class="round-title">${isCurrent ? '<span class="live-dot"></span>' : ''}${esc(round.label)}</div>`;
  for (const s of round.series) {
    col.appendChild(seriesCard(s));
  }
  return col;
}

/* Projection bracket from standings (desktop _build_projection_bracket). */
async function loadProjection() {
  const bracket = document.getElementById('bracket');
  try {
    const d = await (await fetch('/api/playoffs/projection')).json();
    if (!d.available) return;
    bracket.hidden = false;
    document.getElementById('empty').hidden = true;
    bracket.innerHTML = '';
    for (const round of d.rounds) {
      if (!round.series.length) continue;
      bracket.appendChild(roundCol(round, { current_round: null }));
    }
    if (!bracket.children.length) {
      bracket.hidden = true;
      document.getElementById('empty').hidden = false;
    }
  } catch (e) { console.error(e); }
}

/* ---------- series detail ---------- */
document.getElementById('series-close').addEventListener('click', () =>
  document.getElementById('series-modal').hidden = true);
document.getElementById('series-modal').addEventListener('click', e => {
  if (e.target.id === 'series-modal')
    document.getElementById('series-modal').hidden = true;
});

async function openSeriesDetail(s) {
  if (!s.id) return;
  const modal = document.getElementById('series-modal');
  const body = document.getElementById('series-body');
  document.getElementById('series-title').textContent =
    `${s.team1} vs ${s.team2}`;
  document.getElementById('series-sub').textContent = 'Loading…';
  body.innerHTML = '<div class="empty">Loading series detail…</div>';
  modal.hidden = false;
  try {
    const d = await (await fetch('/api/playoffs/series/' + encodeURIComponent(s.id))).json();
    if (!d.found) { body.innerHTML = '<div class="empty">Series not found.</div>'; return; }
    renderSeriesDetail(d);
  } catch (e) {
    body.innerHTML = '<div class="empty">Could not load series detail.</div>';
  }
}

function renderSeriesDetail(d) {
  const [t1, t2] = d.teams;
  document.getElementById('series-sub').textContent =
    `${esc(d.round)}${d.projected ? ' · projection' : ''}`;
  const body = document.getElementById('series-body');
  const teamLine = t =>
    `<div class="sd-team">
      <div class="sd-tabbr">${esc(t.abbr)}${t.seed ? ` <span class="panel-note">#${esc(t.seed)}</span>` : ''}</div>
      <div class="sd-tname clickable-text" data-href="/team/${encodeURIComponent(t.name)}" title="Open team overview">${esc(t.name)}</div>
      <div class="panel-note">${t.record.w}-${t.record.l}-${t.record.otl} · ${t.gf} GF / ${t.ga} GA</div>
    </div>`;
  let html = `
    <div class="sd-status">${esc(d.status)}</div>
    <div class="sd-score">${esc(d.score.score)}${d.score.complete ? ' · final' : ''}</div>
    <div class="sd-vs">${teamLine(t1)}<div class="sd-vs-x">VS</div>${teamLine(t2)}</div>`;
  if (d.projected) {
    html += '<p class="panel-note">Tale of the tape (regular season). Projection only — the real series starts at 0–0.</p>';
  }
  if (d.games && d.games.length) {
    html += `<div class="sd-h">Games</div><table class="stand-table"><tbody>` +
      d.games.map(g => `<tr><td class="rank">G${g.game}</td>
        <td class="tname">${g.team1_won ? esc(t1.abbr) : esc(t2.abbr)} win</td>
        <td class="num">${esc(g.score)}${g.ot ? ' (OT)' : ''}</td></tr>`).join('') +
      '</tbody></table>';
  }
  if (d.storylines && d.storylines.length) {
    html += `<div class="sd-h">Storylines</div><ul class="sd-list">` +
      d.storylines.map(l => `<li>${esc(l)}</li>`).join('') + '</ul>';
  }
  if (d.players_to_watch && d.players_to_watch.length) {
    html += `<div class="sd-h">Players to watch <span class="panel-note">playoff scoring</span></div>
      <table class="stand-table"><tbody>` +
      d.players_to_watch.map(p => `<tr><td class="rank">${esc(p.team)}</td>
        <td class="tname">${esc(p.name)}</td>
        <td class="num">${p.pts} pts (${p.g}G, ${p.a}A)</td></tr>`).join('') +
      '</tbody></table>';
  }
  if (d.road_ahead) {
    html += `<div class="sd-h">Road ahead</div>
      <p class="panel-note">Winner advances to the <b>${esc(d.road_ahead.round)}</b>${d.road_ahead.opponent && d.road_ahead.opponent !== 'TBD' ? ' vs <b>' + esc(d.road_ahead.opponent) + '</b>' : ''}.</p>`;
  }
  body.innerHTML = html;
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
        ${s.team1_name ? `<span class="abbr-sm clickable-text" data-href="/team/${encodeURIComponent(s.team1_name)}" title="Open team overview">${esc(s.team1)}</span>` : `<span class="abbr-sm">${esc(s.team1)}</span>`}
        <span class="series-score">${s.team1_wins}</span>
      </span>
      ${t1w ? '<span class="series-note"><span class="cup">★</span></span>' : (lead1 ? '<span class="series-note">leads</span>' : '')}
    </div>
    <div class="series-row">
      <span class="series-team ${t2w ? 'winner' : 'loser'}">
        ${s.team2_name ? `<span class="abbr-sm clickable-text" data-href="/team/${encodeURIComponent(s.team2_name)}" title="Open team overview">${esc(s.team2)}</span>` : `<span class="abbr-sm">${esc(s.team2)}</span>`}
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
  // Series detail (desktop SeriesDetailPopup): click a series -> its
  // storylines panel. Team links inside still navigate.
  if (s.id) {
    el.classList.add('clickable-series');
    el.title = 'Open series detail';
    el.addEventListener('click', (e) => {
      if (e.target.closest('.clickable-text[data-href]')) return;
      openSeriesDetail(s);
    });
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

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, label')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
