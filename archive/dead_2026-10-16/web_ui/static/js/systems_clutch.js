/* Systems: Clutch Factors — qualitative close-game read (signs only). */
(function () {
  'use strict';
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }
  const GLYPH = { lifting: ['▲', 'green'], dragging: ['▼', 'red'], neutral: ['▬', 'blue'] };

  async function load() {
    let d;
    try {
      const r = await fetch('/api/systems/clutch');
      d = await r.json();
    } catch (e) { d = { error: 'load failed' }; }
    if (!d || d.error || !d.verdict) {
      document.getElementById('cl-verdict').innerHTML =
        '<div class="sys-empty">Clutch read unavailable.</div>';
      return;
    }
    const v = d.verdict;
    document.getElementById('cl-verdict').innerHTML =
      `<div class="sys-verdict"><span class="sys-chip ${esc(v.tone)}">${esc(v.label)}</span>` +
      `<div><div class="sys-blurb">${esc(v.blurb)}</div>` +
      `<div class="sys-fine">Built from seven live inputs below. The exact blend is the sim's business — this is the shape of it.</div></div></div>`;
    document.getElementById('cl-factors').innerHTML = (d.factors || []).map((f) => {
      const [glyph, tone] = GLYPH[f.sign] || GLYPH.neutral;
      return `<div class="sys-row"><span class="sys-chip ${tone}">${glyph}</span>` +
        `<div class="sys-row-body"><div class="sys-row-title">${esc(f.label)} — ` +
        `<span class="sys-sign">${esc(f.sign)}</span></div>` +
        `<div class="sys-row-story">${esc(f.story)}</div></div></div>`;
    }).join('');
  }
  load();
})();
