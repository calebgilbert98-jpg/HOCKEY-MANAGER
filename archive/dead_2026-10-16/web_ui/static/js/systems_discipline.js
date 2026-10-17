/* Systems: Discipline List — active suspensions + season rap sheet. */
(function () {
  'use strict';
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }
  const teamLink = (t) => `<a class="sys-name" href="/team/${encodeURIComponent(t)}">${esc(t)}</a>`;
  const playerLink = (p) =>
    `<a class="sys-name" href="/player/${encodeURIComponent(p.id)}">${esc(p.name)}</a>`;

  async function load() {
    let d;
    try {
      const r = await fetch('/api/systems/discipline');
      d = await r.json();
    } catch (e) { d = { error: 'load failed' }; }
    if (!d || d.error) {
      document.getElementById('dp-active').innerHTML = '<div class="sys-empty">Discipline data unavailable.</div>';
      return;
    }
    const active = d.active || [];
    document.getElementById('dp-active-sub').textContent =
      active.length ? `${active.length} player${active.length === 1 ? '' : 's'} sidelined by DoPS.` : 'No active suspensions.';
    document.getElementById('dp-active').innerHTML = active.length
      ? `<table class="sys-table"><thead><tr><th></th><th>Player</th><th>Team</th><th class="num">Games left</th></tr></thead><tbody>` +
        active.map((a) => {
          const face = a.portrait ? `<img class="sys-face" src="${esc(a.portrait)}" alt="" loading="lazy" onerror="this.remove()">` : '';
          return `<tr><td style="width:110px"><span class="sys-chip red">Suspended</span></td>` +
            `<td>${face}${playerLink(a)}</td><td>${teamLink(a.team)}</td>` +
            `<td class="num"><b>${a.games} game${a.games === 1 ? '' : 's'}</b></td></tr>`;
        }).join('') + `</tbody></table>`
      : '<div class="sys-empty">The league is behaving itself.</div>';

    const hist = d.history || [];
    document.getElementById('dp-history').innerHTML = hist.length
      ? hist.map((h) =>
        `<div class="sys-row"><div class="sys-row-body">` +
        `<div class="sys-row-title">${teamLink(h.team)}</div>` +
        h.entries.map((e) => {
          const tag = e.count >= 2 ? ` — <b class="neg">repeat offender (${e.count}x)</b>` : '';
          let line = `• ${playerLink(e)}: ${e.count} suspension${e.count === 1 ? '' : 's'}${tag}`;
          if (e.desc) line += ` — ${esc(e.desc)}`;
          if (e.date) line += ` <span class="sys-row-meta">(${esc(e.date)})</span>`;
          return `<div class="sys-note" style="margin-top:3px">${line}</div>`;
        }).join('') + `</div></div>`).join('')
      : '<div class="sys-empty">No suspensions recorded this season.</div>';
  }
  load();
})();
