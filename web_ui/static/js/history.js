/* Puck Dynasty web history */
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    renderHistory(data);
  } catch (e) { console.error(e); }
}

function renderHistory(data) {
  const empty = document.getElementById('empty');
  const sub = document.getElementById('history-sub');
  if (!data.has_data) {
    document.getElementById('champions').hidden = true;
    document.getElementById('records').hidden = true;
    empty.hidden = false;
    sub.textContent = 'Fresh league';
    return;
  }
  empty.hidden = true;

  const list = document.getElementById('champ-list');
  list.innerHTML = '';
  sub.textContent = `${data.seasons.length} season${data.seasons.length === 1 ? '' : 's'} recorded`;
  if (!data.seasons.length) {
    document.getElementById('champions').hidden = true;
  } else {
    for (const s of data.seasons) {
      list.appendChild(champCard(s));
    }
  }

  if (data.records) {
    const grid = document.getElementById('record-grid');
    grid.innerHTML = '';
    const cards = [
      ['Skater career records', data.records.skater_career],
      ['Skater single-season records', data.records.skater_season],
      ['Goalie career records', data.records.goalie_career],
      ['Goalie single-season records', data.records.goalie_season],
      ['Team season records', data.records.team_season],
      ['Streaks', data.records.streaks],
    ];
    for (const [label, r] of cards) {
      const el = document.createElement('div');
      el.className = 'record-card';
      el.innerHTML = `
        <div class="record-label">${esc(label)}</div>
        <div class="record-value">${r.records}</div>
        <div class="record-sub">${r.franchises} franchises</div>`;
      grid.appendChild(el);
    }
    document.getElementById('records').hidden = false;
  }
  if (data.hall_of_fame_count) {
    sub.textContent += ` · ${data.hall_of_fame_count} HOF inductees`;
  }
}

function champCard(s) {
  const el = document.createElement('div');
  el.className = 'champ-card';
  const detail = [s.runner_up ? `def. ${esc(s.runner_up)}` : '',
                  s.series_score ? esc(s.series_score) : ''].filter(Boolean).join(' ');
  const awards = [];
  if (s.conn_smythe) awards.push(`Conn Smythe: <b>${esc(s.conn_smythe)}</b>`);
  if (s.presidents_trophy) awards.push(`Presidents': <b>${esc(s.presidents_trophy)}</b>`);
  const extraAwards = Object.entries(s.awards || {}).slice(0, 3)
    .map(([k, v]) => `${esc(k)}: <b>${esc(v)}</b>`);
  el.innerHTML = `
    <div class="champ-year">${esc(s.year)}</div>
    <div class="champ-cup">🏆</div>
    <div>
      <div class="champ-team">${esc(s.champion)}</div>
      ${detail ? `<div class="champ-detail">${detail}</div>` : ''}
    </div>
    <div class="champ-meta">${[...awards, ...extraAwards].join('<br>')}</div>`;
  return el;
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadHistory();

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
