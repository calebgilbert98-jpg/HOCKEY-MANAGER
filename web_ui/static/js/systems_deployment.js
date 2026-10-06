/* Systems: Ice-Time Deployment — the coach's live ice plan. */
(function () {
  'use strict';
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }

  async function load() {
    let d;
    try {
      const r = await fetch('/api/systems/deployment');
      d = await r.json();
    } catch (e) { d = { error: 'load failed' }; }
    if (!d || d.error) {
      document.getElementById('dp-policy').innerHTML = '<div class="sys-empty">Deployment data unavailable.</div>';
      return;
    }
    const lines = [`Head coach: <b>${esc(d.coach_name)}</b>`,
      `Style: <b>${esc(d.style_label)}</b> · Tactical family: <b>${esc(String(d.family).replace(/^\w/, (c) => c.toUpperCase()))}</b>`];
    if (d.concentration != null) lines.push(`Deployment posture: <b>${esc(d.concentration_label)}</b>`);
    if (d.overload) lines.push(`<span class="sys-chip gold">Star-overload mode</span> <span class="sys-note">top talent soaks up the big minutes</span>`);
    document.getElementById('dp-policy').innerHTML =
      lines.map((l) => `<div class="sys-note" style="margin:3px 0">• ${l}</div>`).join('');

    const groups = d.groups || [];
    document.getElementById('dp-shares').innerHTML = groups.length
      ? groups.map((g) =>
        `<div class="sys-row-title" style="margin:10px 0 4px">${esc(g.title)}</div>` +
        g.rows.map((r) => {
          const pct = Math.round((r.share || 0) * 100);
          return `<div class="sys-row" style="align-items:center">` +
            `<div style="width:70px" class="sys-note">${esc(r.label)}</div>` +
            `<span class="sys-bar" style="width:220px"><i style="width:${pct}%;background:var(--accent)"></i></span>` +
            `<b style="width:52px">${pct}%</b></div>`;
        }).join('')).join('')
      : '<div class="sys-empty">No deployment data available.</div>';

    const caps = [
      ['Standard soft cap', '~30:00 per game'],
      ['Short-bench cap', '35:00 (fewer than 15 dressed skaters)'],
      ['Full stand-down', 'must-win playoff games, OT marathons'],
    ];
    const exc = d.cap_exceptions || [];
    document.getElementById('dp-caps').innerHTML =
      `<table class="sys-table"><tbody>` +
      caps.map((c) => `<tr><td>${esc(c[0])}</td><td class="dim">${esc(c[1])}</td></tr>`).join('') +
      `</tbody></table>` +
      `<div class="sys-note" style="margin-top:8px">` +
      (exc.length ? `Cap exceptions active right now: <b>${esc(exc.join(', '))}</b>`
                  : `No cap exceptions active at the base policy.`) + `</div>`;

    const advice = d.advice || [];
    document.getElementById('dp-advice').innerHTML = advice.length
      ? advice.map((a) => `<div class="sys-note" style="margin:3px 0">• ${esc(a)}</div>`).join('')
      : '<div class="sys-empty">None on file — the coach deploys on his own read.</div>';
  }
  load();
})();
