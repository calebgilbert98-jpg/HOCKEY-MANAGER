/* Puck Dynasty web lines */
async function loadLines() {
  try {
    const res = await fetch('/api/lines');
    const data = await res.json();
    renderUnits(data.units || []);
    renderRoster(data.roster || []);
  } catch (e) { console.error(e); }
}

function renderUnits(units) {
  const host = document.getElementById('lines-units');
  host.innerHTML = '';
  const groups = {};
  for (const u of units) (groups[u.group] = groups[u.group] || []).push(u);
  const order = ['forwards', 'defense', 'goalies', 'other'];
  const titles = { forwards: 'Forwards', defense: 'Defense', goalies: 'Goalies', other: 'Other' };
  for (const g of order) {
    const list = groups[g];
    if (!list) continue;
    const sec = document.createElement('section');
    sec.innerHTML = `<h2 class="lines-h2">${titles[g] || g}</h2>`;
    for (const u of list) {
      const div = document.createElement('div');
      div.className = 'unit';
      let slotsHtml = '';
      for (const s of u.slots || []) {
        const p = s.player;
        if (p) {
          const cap = p.captaincy ? `<span class="tag-${p.captaincy.toLowerCase()}">${esc(p.captaincy)}</span>` : '';
          slotsHtml += `<div class="slot">
            <div class="slot-pos">${esc(s.slot)}</div>
            <div class="slot-name">${esc(p.name)}${cap}</div>
            <div class="slot-sub">${esc(p.position)} · ${p.overall} OVR</div>
          </div>`;
        } else {
          slotsHtml += `<div class="slot slot-empty">
            <div class="slot-pos">${esc(s.slot)}</div>
            <div class="slot-name">Empty</div>
          </div>`;
        }
      }
      div.innerHTML = `<div class="unit-label">${esc(u.label)}</div><div class="unit-row">${slotsHtml}</div>`;
      sec.appendChild(div);
    }
    host.appendChild(sec);
  }
}

function renderRoster(roster) {
  const host = document.getElementById('lines-roster');
  document.getElementById('lines-sub').textContent = `${roster.length} players on roster`;
  host.innerHTML = '';
  const sorted = [...roster].sort((a, b) => b.overall - a.overall);
  for (const p of sorted) {
    const el = document.createElement('div');
    el.className = 'roster-chip';
    el.innerHTML = `<span class="ov">${p.overall}</span>${esc(p.name)}<span class="pos">${esc(p.position)}</span>`;
    host.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadLines();
