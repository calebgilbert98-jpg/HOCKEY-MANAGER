/* Systems: Circumstance Shifts — tonight's per-player composite nudges. */
(function () {
  'use strict';
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }
  function fmt(v) {
    const n = Number(v) || 0;
    return (n > 0 ? '+' : '') + n.toFixed(2);
  }
  function cls(v) { return (Number(v) || 0) > 0.005 ? 'pos' : ((Number(v) || 0) < -0.005 ? 'neg' : ''); }

  const sel = document.getElementById('cs-composite');
  sel.addEventListener('change', () => load(sel.value));

  async function load(composite) {
    let d;
    try {
      const r = await fetch('/api/systems/circumstance?composite=' + encodeURIComponent(composite || 'finishing'));
      d = await r.json();
    } catch (e) { d = { error: 'load failed' }; }
    if (!d || d.error) {
      document.getElementById('cs-table').innerHTML = '<div class="sys-empty">Circumstance data unavailable.</div>';
      return;
    }
    if (!sel.options.length) {
      (d.composites || []).forEach((c) => {
        const o = document.createElement('option');
        o.value = c.key; o.textContent = c.label;
        if (c.key === d.composite) o.selected = true;
        sel.appendChild(o);
      });
    }
    sel.value = d.composite;
    document.getElementById('cs-note').textContent = d.note || '';
    const lbl = (d.composites || []).find((c) => c.key === d.composite);
    document.getElementById('cs-table-title').textContent =
      'Applied shifts — ' + (lbl ? lbl.label : d.composite);

    const oppCard = document.getElementById('cs-opp-card');
    if (d.opponent) {
      oppCard.hidden = false;
      const heat = d.opponent.heat || 0;
      const tone = heat >= 60 ? 'red' : (heat >= 40 ? 'gold' : 'blue');
      document.getElementById('cs-opp').innerHTML =
        `<div class="sys-row"><div class="sys-row-body">` +
        `<div class="sys-row-title">Opponent: <a class="sys-name" href="/team/${encodeURIComponent(d.opponent.name)}">${esc(d.opponent.name)}</a></div>` +
        `<div style="display:flex;align-items:center;gap:10px;margin-top:6px">` +
        `<span class="sys-bar" style="width:160px"><i style="width:${heat}%;background:var(--${tone === 'blue' ? 'accent' : tone})"></i></span>` +
        `<span class="sys-chip ${tone}">Rivalry heat ${Math.round(heat)}/100</span></div>` +
        `<div class="sys-row-meta">Heat feeds the physical (+emotion) and discipline (−hot heads) channels for both clubs.</div>` +
        `</div></div>`;
    } else {
      oppCard.hidden = true;
    }

    const rows = d.rows || [];
    let html = `<table class="sys-table"><thead><tr>` +
      `<th>Player</th><th>Pos</th>` +
      `<th class="num">Total</th><th class="num">Energy</th><th class="num">Morale</th>` +
      `<th class="num">Home</th><th class="num">Rivalry</th></tr></thead><tbody>`;
    rows.forEach((p) => {
      const face = p.portrait ? `<img class="sys-face" src="${esc(p.portrait)}" alt="" loading="lazy" onerror="this.remove()">` : '';
      html += `<tr><td>${face}<a class="sys-name" href="/player/${encodeURIComponent(p.id)}">${esc(p.name)}</a></td>` +
        `<td class="dim">${esc(p.pos)}</td>` +
        `<td class="num ${cls(p.total)}">${fmt(p.total)}</td>` +
        `<td class="num ${cls(p.energy)}">${fmt(p.energy)}</td>` +
        `<td class="num ${cls(p.morale)}">${fmt(p.morale)}</td>` +
        `<td class="num ${cls(p.home)}">${fmt(p.home)}</td>` +
        `<td class="num ${cls(p.rivalry)}">${fmt(p.rivalry)}</td></tr>`;
    });
    html += `</tbody></table>`;
    if (!rows.length) html = '<div class="sys-empty">No skaters on the roster.</div>';
    document.getElementById('cs-table').innerHTML = html;
  }
  load('finishing');
})();
