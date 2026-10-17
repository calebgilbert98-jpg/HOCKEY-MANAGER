/* Systems: Rivalry Dashboard — your feuds + league heat. */
(function () {
  'use strict';
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }
  const teamLink = (t) => `<a class="sys-name" href="/team/${encodeURIComponent(t)}">${esc(t)}</a>`;
  const ACCENT = { red: 'var(--red)', gold: 'var(--gold)', blue: 'var(--accent)', slate: '#8b95a7' };

  function block(r) {
    const bits = [];
    if (r.origin) bits.push('Origin: ' + esc(r.origin));
    if (r.date) bits.push('since ' + esc(r.date));
    return `<div class="sys-row"><span class="sys-chip ${esc(r.tone)}">${esc(r.band)}</span>` +
      `<div class="sys-row-body">` +
      `<div class="sys-row-title">${teamLink(r.a)} <span class="dim">vs</span> ${teamLink(r.b)}` +
      ` <span class="sys-row-meta">· ${esc(r.kind)}</span></div>` +
      `<div style="display:flex;align-items:center;gap:10px;margin-top:6px">` +
      `<span class="sys-bar" style="width:200px"><i style="width:${r.intensity}%;background:${ACCENT[r.tone] || ACCENT.blue}"></i></span>` +
      `<span class="sys-note">Intensity ${r.intensity} · Grudge ${r.grudge}</span></div>` +
      (bits.length ? `<div class="sys-row-meta">${bits.join(' &nbsp;·&nbsp; ')}</div>` : '') +
      (r.story ? `<div class="sys-row-story">${esc(r.story)}</div>` : '') +
      `</div></div>`;
  }

  async function load() {
    let d;
    try {
      const r = await fetch('/api/systems/rivalry');
      d = await r.json();
    } catch (e) { d = { error: 'load failed' }; }
    if (!d || d.error) {
      document.getElementById('rv-mine').innerHTML = '<div class="sys-empty">Rivalry data unavailable.</div>';
      return;
    }
    const mine = d.mine || [], hottest = d.hottest || [];
    document.getElementById('rv-mine-sub').textContent = mine.length
      ? `${mine.length} live record${mine.length === 1 ? '' : 's'} involving your club.`
      : 'No rivalries on the books — quiet rooms win Cups too.';
    document.getElementById('rv-mine').innerHTML = mine.length
      ? mine.map(block).join('')
      : '<div class="sys-empty">Nothing simmering at home.</div>';
    document.getElementById('rv-hottest').innerHTML = hottest.length
      ? hottest.map(block).join('')
      : '<div class="sys-empty">Nothing simmering league-wide.</div>';
  }
  load();
})();
