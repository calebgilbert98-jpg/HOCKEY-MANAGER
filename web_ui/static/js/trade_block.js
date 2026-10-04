/* Puck Dynasty web trade block */
async function loadBlock() {
  try {
    const res = await fetch('/api/trade_block');
    const data = await res.json();
    renderBlock(data.players || []);
  } catch (e) { console.error(e); }
}

function barColor(v) {
  if (v >= 75) return '#4CAF50';
  if (v >= 60) return '#8BC34A';
  if (v >= 45) return '#FFC107';
  if (v >= 30) return '#FF9800';
  return '#F44336';
}

function salaryStr(s) {
  s = s || 0;
  return s >= 1e6 ? '$' + (s / 1e6).toFixed(2) + 'M'
                  : '$' + Math.round(s / 1e3) + 'K';
}

function renderBlock(players) {
  const grid = document.getElementById('block-grid');
  document.getElementById('block-count').textContent =
    players.length + (players.length === 1 ? ' player' : ' players') + ' available';
  grid.innerHTML = '';
  if (!players.length) {
    const el = document.createElement('div');
    el.className = 'block-empty';
    el.textContent = 'No players on the trade block right now.';
    grid.appendChild(el);
    return;
  }
  for (const p of players) {
    const el = document.createElement('div');
    el.className = 'block-card';
    el.innerHTML = `
      <div class="b-head">
        <div class="b-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
        <div>
          <div class="b-name">${esc(p.name)}</div>
          ${p.team ? '<div><span class="b-team">' + esc(p.team) + '</span></div>' : ''}
        </div>
      </div>
      <div class="b-sub">${esc(p.position)} · Age ${p.age} · ${salaryStr(p.salary)}</div>
      <div class="b-bar" style="margin-top:10px"><span style="width:${Math.min(100, p.overall)}%;background:${barColor(p.overall)}"></span></div>`;
    grid.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadBlock();
