/* Puck Dynasty team overview */
const TEAM_NAME = decodeURIComponent(window.location.pathname.split('/team/')[1] || '');

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function fmtCap(v) {
  if (!v) return '—';
  return '$' + (v / 1e6).toFixed(2) + 'M';
}

async function loadTeam() {
  let d;
  try {
    const res = await fetch('/api/team/' + encodeURIComponent(TEAM_NAME));
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const dbg = err.debug ? `<br><small style="font-size:12px">Requested: ${esc(err.debug.requested)}<br>Teams in league: ${err.debug.league_teams}<br>User team: ${esc(err.debug.user_team)}<br>Sample: ${esc((err.debug.sample_names||[]).join(', '))}</small>` : '';
      document.getElementById('tm-name').innerHTML = 'Team not found' + dbg;
      return;
    }
    d = await res.json();
  } catch (e) { console.error(e); return; }
  renderTeam(d);
}

function renderTeam(d) {
  document.title = d.name + ' — Puck Dynasty';
  document.getElementById('tm-name').textContent = d.name.toUpperCase();
  document.getElementById('tm-div').textContent =
    [d.division, d.conference].filter(Boolean).join(' · ').toUpperCase() || '—';
  const r = d.record || {};
  document.getElementById('tm-rec').textContent =
    `${r.w ?? 0}-${r.l ?? 0}-${r.otl ?? 0}`;
  const bits = [];
  if (d.div_rank) bits.push(`${d.div_rank}${['st','nd','rd'][d.div_rank-1] || 'th'} in ${esc(d.division)}`);
  bits.push(`Streak ${esc(d.streak || '—')}`);
  bits.push(`Cap space ${fmtCap(d.cap_space)}`);
  if (d.is_user) {
    bits.push('<a href="/roster">Full roster →</a>');
    document.querySelector('.tm-head').setAttribute('data-is-user-team', '1');
  }
  document.getElementById('tm-sub').innerHTML = bits.join(' · ');

  // Leaders
  const L = document.getElementById('tm-leaders');
  if (d.leaders && d.leaders.length) {
    L.innerHTML = d.leaders.map((p, i) => `
      <div class="tm-lead-row${p.id ? ' clickable-text' : ''}"${p.id ? ` data-href="/player/${esc(p.id)}" title="Open player profile"` : ''}>
        <span class="rank">${i + 1}</span>
        ${p.portrait ? `<img class="tm-face" src="${esc(p.portrait)}" alt="" loading="lazy" onerror="this.remove()">` : ''}
        <span class="nm">${esc(p.name)} <span class="pos">${esc(p.position)}</span></span>
        <span class="st">${p.g}G · ${p.a}A · <b>${p.pts} PTS</b></span>
      </div>`).join('');
  } else {
    L.innerHTML = '<div class="empty">No stats yet.</div>';
  }

  // Form
  const F = document.getElementById('tm-form');
  if (d.form && d.form.length) {
    F.innerHTML = d.form.map(g => `
      <div class="tm-form-row">
        <span class="res ${g.res}">${esc(g.res)}</span>
        <span class="opp">${esc(g.vs)} ${esc(g.opp)}</span>
        <span class="score">${esc(g.score)}</span>
      </div>`).join('');
  } else {
    F.innerHTML = '<div class="empty">No games yet.</div>';
  }

  // Roster
  const P = document.getElementById('tm-players');
  document.getElementById('tm-count').textContent = `(${d.player_count || 0})`;
  if (d.players && d.players.length) {
    P.innerHTML = d.players.map(p => `
      <div class="tm-prow${p.id ? ' clickable' : ''}"${p.id ? ` data-href="/player/${esc(p.id)}" title="Open player profile"` : ''}>
        ${p.portrait ? `<img class="tm-face" src="${esc(p.portrait)}" alt="" loading="lazy" onerror="this.remove()">` : ''}
        <span class="nm">${esc(p.name)}</span>
        <span class="pos">${esc(p.position)}</span>
        <span class="ovr">${p.overall} OVR</span>
      </div>`).join('');
  } else {
    P.innerHTML = '<div class="empty">No roster data.</div>';
  }
}

loadTeam();

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});

// Shared heartbeat
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
