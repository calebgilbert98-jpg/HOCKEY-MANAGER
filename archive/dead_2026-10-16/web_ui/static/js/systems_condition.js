/* Systems: Roster Condition — worst-first fatigue table. */
(function () {
  'use strict';
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }
  const BAR = { green: 'var(--green)', blue: 'var(--accent)', gold: 'var(--gold)', red: 'var(--red)' };

  async function load() {
    let d;
    try {
      const r = await fetch('/api/systems/condition');
      d = await r.json();
    } catch (e) { d = { error: 'load failed' }; }
    if (!d || d.error) {
      document.getElementById('rc-table').innerHTML = '<div class="sys-empty">Condition data unavailable.</div>';
      return;
    }
    const counts = d.counts || {};
    const bits = ['FRESH', 'GOOD', 'WORN', 'GASSED'].map(
      (t) => `<b>${counts[t] || 0}</b> ${t.charAt(0) + t.slice(1).toLowerCase()}`);
    let note = bits.join(' · ');
    if (d.rest_days != null) note += ` &nbsp;·&nbsp; ${d.rest_days} rest day${d.rest_days === 1 ? '' : 's'} before the next game`;
    document.getElementById('rc-summary').innerHTML =
      `<div class="sys-bits">${note}</div>` +
      ((d.gassed || []).length
        ? `<div class="sys-note" style="margin-top:8px">Needs rest: <b class="neg">${(d.gassed || []).map(esc).join(', ')}</b></div>`
        : '');

    const rows = d.rows || [];
    let html = `<table class="sys-table"><thead><tr>` +
      `<th>Player</th><th>Pos</th><th>Condition</th><th>Tier</th>` +
      `<th class="num">Energy</th><th class="num">Inj risk</th><th class="num">Last TOI</th>` +
      `</tr></thead><tbody>`;
    rows.forEach((p) => {
      const face = p.portrait ? `<img class="sys-face" src="${esc(p.portrait)}" alt="" loading="lazy" onerror="this.remove()">` : '';
      html += `<tr><td>${face}<a class="sys-name" href="/player/${encodeURIComponent(p.id)}">${esc(p.name)}</a></td>` +
        `<td class="dim">${esc(p.pos)}</td>` +
        `<td><span style="display:inline-flex;align-items:center;gap:8px">` +
        `<span class="sys-bar" style="width:100px"><i style="width:${p.cond}%;background:${BAR[p.tone] || BAR.blue}"></i></span>` +
        `<b>${p.cond}</b></span></td>` +
        `<td><span class="sys-chip ${esc(p.tone)}">${esc(p.tier)}</span></td>` +
        `<td class="num">${p.energy}</td>` +
        `<td class="num">${Number(p.risk).toFixed(2)}x</td>` +
        `<td class="num dim">${p.last_toi} min</td></tr>`;
    });
    html += `</tbody></table>`;
    if (!rows.length) html = '<div class="sys-empty">No skaters on the roster.</div>';
    document.getElementById('rc-table').innerHTML = html;
  }
  load();
})();
