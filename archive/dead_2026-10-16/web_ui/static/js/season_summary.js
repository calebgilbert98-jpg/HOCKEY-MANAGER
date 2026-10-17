/* Puck Dynasty season summary + awards ceremony.
   Ported from main.py _show_season_summary (~19203) and
   awards_ceremony.py (~255). */
let ssData = null;
let ceremonyData = null;
let ceremonyIdx = 0;
let ceremonyRevealed = false;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

document.getElementById('ss-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#ss-tabs .tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('main.ss-main .tb-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('ss-tab-' + b.dataset.tab).classList.remove('hidden');
  if (b.dataset.tab === 'ceremony') loadCeremony();
});

async function boot() {
  try {
    ssData = await (await fetch('/api/season-summary')).json();
    renderSummary(ssData);
  } catch (e) {
    document.getElementById('ss-awards').innerHTML =
      '<div class="empty">Could not load season summary.</div>';
  }
}

function renderSummary(d) {
  document.getElementById('ss-title').textContent =
    d.season ? `${d.season} Season Complete!` : 'Season Summary';
  document.getElementById('ss-sub').textContent =
    d.season_over ? 'Final results' : 'Season still in progress — awards finalize at season end';

  // Awards
  const aw = d.awards || {};
  const host = document.getElementById('ss-awards');
  const names = Object.keys(aw);
  host.innerHTML = names.length ? names.map(n => {
    const w = aw[n];
    return `<div class="award-card">
      <div class="award-name">${esc(n)}</div>
      ${w ? `<div class="award-winner">${w.id ? `<span class="clickable-text" data-href="/player/${esc(w.id)}" title="Open player profile">${esc(w.name)}</span>` : esc(w.name)}</div>
      <div class="award-team">${esc(w.team)}</div>
      <div class="panel-note">${esc(w.stats)}</div>`
      : '<div class="panel-note">TBD</div>'}
    </div>`;
  }).join('') : '<div class="empty">Awards are decided when the season ends.</div>';

  // Leaders
  const lg = d.leaders || {};
  const lh = document.getElementById('ss-leaders');
  lh.innerHTML = Object.keys(lg).length ? Object.entries(lg).map(([k, rows]) => `
    <section class="bpanel leader-card">
      <div class="bpanel-h">${esc(k)}</div>
      <table class="leader-table"><tbody>
        ${(rows || []).map((r, i) => `<tr><td class="rank">${i + 1}</td>
          <td class="pname">${r.id ? `<span class="clickable-text" data-href="/player/${esc(r.id)}">${esc(r.name)}</span>` : esc(r.name)}<span class="pteam">${esc(r.team)}</span></td>
          <td class="stat">${esc(r.value)}</td></tr>`).join('')}
      </tbody></table>
    </section>`).join('')
    : '<div class="empty">No leaders yet.</div>';

  // Your team
  const t = d.team;
  const th = document.getElementById('ss-team');
  th.innerHTML = t ? `
    <section class="bpanel leader-card">
      <div class="bpanel-h">${esc(t.name)} <span class="panel-note">Season review</span></div>
      <div class="ss-record">${esc(t.record)}</div>
      ${t.position ? `<p>League position: <b>${t.position}</b> of ${t.of_teams}</p>` : ''}
      <div class="sd-h">Top scorers</div>
      <table class="leader-table"><tbody>
        ${(t.top_scorers || []).map(p => `<tr>
          <td class="pname">${p.id ? `<span class="clickable-text" data-href="/player/${esc(p.id)}">${esc(p.name)}</span>` : esc(p.name)}</td>
          <td class="num">${esc(p.line)}</td></tr>`).join('')}
      </tbody></table>
    </section>`
    : '<div class="empty">No team data.</div>';
}

/* ---------- awards ceremony ---------- */
async function loadCeremony() {
  const host = document.getElementById('ss-ceremony');
  if (ceremonyData) { renderCeremony(); return; }
  host.innerHTML = '<div class="empty">Building the ceremony…</div>';
  try {
    ceremonyData = await (await fetch('/api/awards-ceremony')).json();
    ceremonyIdx = 0;
    ceremonyRevealed = false;
    renderCeremony();
  } catch (e) {
    host.innerHTML = '<div class="empty">Could not build the ceremony.</div>';
  }
}

function renderCeremony() {
  const host = document.getElementById('ss-ceremony');
  const script = (ceremonyData && ceremonyData.script) || [];
  if (!script.length) {
    host.innerHTML = '<div class="empty">No awards to present yet — the ceremony follows the season.</div>';
    return;
  }
  const e = script[ceremonyIdx];
  const dots = script.map((_, i) =>
    `<span class="cdot ${i < ceremonyIdx ? 'done' : ''} ${i === ceremonyIdx ? 'cur' : ''}">●</span>`).join('');
  host.innerHTML = `
    <div class="ceremony-stage">
      <div class="ceremony-kicker">NHL Awards ${esc(ceremonyData.season || '')}</div>
      <div class="ceremony-progress">Award ${ceremonyIdx + 1} of ${script.length}</div>
      <div class="ceremony-dots">${dots}</div>
      <div class="ceremony-trophy">${esc(e.trophy)}</div>
      <div class="ceremony-flavor">${esc(e.flavor)}</div>
      <div class="ceremony-finalists">
        <div class="sd-h">Finalists</div>
        ${e.finalists.map(f => `
          <div class="finalist-card">
            <div class="finalist-name">${f.id ? `<span class="clickable-text" data-href="/player/${esc(f.id)}">${esc(f.name)}</span>` : esc(f.name)}</div>
            <div class="panel-note">${esc(f.team)} · ${esc(f.stats)}</div>
          </div>`).join('') || '<div class="panel-note">—</div>'}
      </div>
      <div class="ceremony-winner" ${ceremonyRevealed ? '' : 'hidden'}>
        <div class="sd-h gold">Winner</div>
        <div class="winner-name">${e.winner.id ? `<span class="clickable-text" data-href="/player/${esc(e.winner.id)}">${esc(e.winner.name)}</span>` : esc(e.winner.name)}</div>
        <div class="panel-note">${esc(e.winner.team)} · ${esc(e.winner.stats)}</div>
        ${e.vote_story ? `<p class="vote-story">${esc(e.vote_story)}</p>` : ''}
        ${e.electorate ? `<p class="panel-note">Decided by: ${esc(e.electorate)}</p>` : ''}
      </div>
      <div class="ceremony-controls">
        ${ceremonyRevealed ? '' : '<button class="tb-btn tb-accent" id="cer-reveal">Reveal Winner</button>'}
        <button class="tb-btn" id="cer-next">${ceremonyIdx + 1 >= script.length ? 'Finish' : 'Next Award →'}</button>
        <button class="tb-btn" id="cer-all">Reveal All</button>
      </div>
    </div>`;
  const rv = document.getElementById('cer-reveal');
  if (rv) rv.addEventListener('click', () => { ceremonyRevealed = true; renderCeremony(); });
  document.getElementById('cer-next').addEventListener('click', () => {
    if (ceremonyIdx + 1 >= script.length) {
      host.innerHTML = '<div class="ceremony-stage"><div class="ceremony-trophy">🏆 That\u2019s a wrap</div><p class="panel-note">All awards presented. See you next season.</p></div>';
      return;
    }
    ceremonyIdx += 1;
    ceremonyRevealed = false;
    renderCeremony();
  });
  document.getElementById('cer-all').addEventListener('click', () => {
    host.innerHTML = `<div class="ceremony-stage">
      <div class="ceremony-kicker">NHL Awards ${esc(ceremonyData.season || '')}</div>
      <div class="ceremony-trophy">🏆 Full Results</div>
      <table class="leader-table"><thead><tr><th>Award</th><th>Winner</th><th>Team</th></tr></thead>
      <tbody>${script.map(s => `<tr>
        <td class="rec-cat">${esc(s.trophy)}</td>
        <td class="pname">${s.winner.id ? `<span class="clickable-text" data-href="/player/${esc(s.winner.id)}">${esc(s.winner.name)}</span>` : esc(s.winner.name)}</td>
        <td class="num">${esc(s.winner.team)}</td></tr>`).join('')}</tbody></table>
    </div>`;
  });
}

boot();

// Shared heartbeat
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
