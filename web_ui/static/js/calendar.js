/* Puck Dynasty web calendar */
let calGames = [];
let calToday = '';          // 'YYYY-MM-DD'
let calTeam = '';
let viewYear = 0;
let viewMonth = 0;          // 0-11

const MONTH_NAMES = ['January','February','March','April','May','June',
  'July','August','September','October','November','December'];

async function loadCalendar() {
  try {
    const res = await fetch('/api/calendar');
    const data = await res.json();
    calGames = data.games || [];
    calToday = data.today || '';
    calTeam = data.team || '';
    initView();
    wireNav();
    renderCalendar();
    renderEmpty();
  } catch (e) { console.error(e); }
}

function initView() {
  const m = /^(\d{4})-(\d{2})-\d{2}$/.exec(calToday || '');
  if (m) {
    viewYear = parseInt(m[1], 10);
    viewMonth = parseInt(m[2], 10) - 1;
  } else {
    const now = new Date();
    viewYear = now.getFullYear();
    viewMonth = now.getMonth();
  }
}

function wireNav() {
  document.getElementById('prev-month').addEventListener('click', () => shiftMonth(-1));
  document.getElementById('next-month').addEventListener('click', () => shiftMonth(1));
}

function shiftMonth(delta) {
  viewMonth += delta;
  while (viewMonth < 0) { viewMonth += 12; viewYear -= 1; }
  while (viewMonth > 11) { viewMonth -= 12; viewYear += 1; }
  renderCalendar();
}

function renderEmpty() {
  document.getElementById('cal-empty').hidden = calGames.length > 0;
}

function renderCalendar() {
  document.getElementById('cal-title').textContent =
    `${MONTH_NAMES[viewMonth]} ${viewYear}`;
  const mineThisMonth = calGames.filter(g =>
    g.mine && g.date.startsWith(`${pad(viewYear)}-${pad(viewMonth + 1)}`)).length;
  document.getElementById('cal-sub').textContent =
    `${calTeam ? calTeam + ' · ' : ''}${mineThisMonth} game${mineThisMonth === 1 ? '' : 's'} this month`;

  // index games by date string
  const byDate = {};
  for (const g of calGames) {
    if (!g.date) continue;
    (byDate[g.date] = byDate[g.date] || []).push(g);
  }

  const grid = document.getElementById('cal-grid');
  grid.innerHTML = '';
  const first = new Date(viewYear, viewMonth, 1).getDay();   // 0 = Sun
  const days = new Date(viewYear, viewMonth + 1, 0).getDate();
  for (let i = 0; i < first; i++) {
    const pad1 = document.createElement('div');
    pad1.className = 'cal-day pad';
    grid.appendChild(pad1);
  }
  for (let d = 1; d <= days; d++) {
    const iso = `${pad(viewYear)}-${pad(viewMonth + 1)}-${pad(d)}`;
    grid.appendChild(dayCell(d, iso, byDate[iso] || []));
  }
}

function dayCell(dayNum, iso, games) {
  const cell = document.createElement('div');
  cell.className = 'cal-day';
  const mine = games.filter(g => g.mine);
  const other = games.length - mine.length;
  if (iso === calToday) cell.classList.add('is-today');
  if (mine.length) cell.classList.add('has-mine');

  let html = `<div class="cal-date">${dayNum}</div>`;
  for (const g of mine) {
    const ha = g.is_home ? 'vs' : '@';
    html += `<div class="cal-game${g.preseason ? ' pre' : ''}">`
      + `<span class="cal-ha">${ha}</span> ${esc(g.opponent)}`
      + (g.preseason ? ' <span class="cal-tag">PRE</span>' : '')
      + `</div>`;
  }
  if (other > 0) {
    html += `<div class="cal-other">${other} other game${other === 1 ? '' : 's'}</div>`;
  }
  cell.innerHTML = html;
  return cell;
}

function pad(n) { return String(n).padStart(2, '0'); }

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadCalendar();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
