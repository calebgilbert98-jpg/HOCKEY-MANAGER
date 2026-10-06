/* Draft lottery — televised countdown reveal (simplified port of LotteryRevealView). */
let lot = null;
let lotIdx = 0;
let lotDone = false;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

async function loadLot() {
  try {
    lot = await (await fetch('/api/lottery')).json();
  } catch (e) { console.error(e); return; }
  if (!lot || !lot.active) {
    document.getElementById('lot-team').textContent = 'No lottery results available.';
    document.getElementById('lot-next').disabled = true;
    document.getElementById('lot-skip').disabled = true;
    return;
  }
  document.getElementById('lot-year').textContent = lot.year || '';
  revealNext();
}

function mvText(r) {
  if (r.movement > 0) return `(+${r.movement} ▲)`;
  if (r.movement < 0) return `(${r.movement} ▼)`;
  return '';
}

function revealNext() {
  const order = (lot && lot.reveal_order) || [];
  if (lotIdx >= order.length) { finish(); return; }
  const r = order[lotIdx];
  document.getElementById('lot-pick').textContent = '#' + r.pick;
  document.getElementById('lot-team').textContent = r.team;
  document.getElementById('lot-detail').textContent =
    `${r.odds_pct}% odds ${mvText(r)} — ${r.reaction}`;
  const board = document.getElementById('lot-board');
  const row = document.createElement('div');
  row.className = 'lot-row' + (r.pick <= 2 ? ' top' : '');
  row.innerHTML = `<span class="lot-rpick">#${r.pick}</span>
    <span class="lot-rteam">${esc(r.team)}</span>
    <span class="lot-rmv">${esc(mvText(r))}</span>`;
  board.prepend(row);
  lotIdx++;
  if (lotIdx >= order.length) finish();
}

function revealAll() {
  while (lotIdx < ((lot && lot.reveal_order) || []).length) revealNext();
}

function finish() {
  if (lotDone) return;
  lotDone = true;
  document.getElementById('lot-next').disabled = true;
  document.getElementById('lot-skip').disabled = true;
  document.getElementById('lot-finale').hidden = false;
}

document.getElementById('lot-next').addEventListener('click', revealNext);
document.getElementById('lot-skip').addEventListener('click', revealAll);
document.getElementById('lot-draft').addEventListener('click', async () => {
  await clearPending();
  window.location.href = '/draft';
});
document.getElementById('lot-done').addEventListener('click', async () => {
  await clearPending();
  window.location.href = '/inbox';
});

async function clearPending() {
  try {
    await fetch('/api/lottery/clear', {method: 'POST'});
  } catch (e) { /* never blocks navigation */ }
}

loadLot();

// Shared heartbeat (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat(); setInterval(beat, 30000);
})();
