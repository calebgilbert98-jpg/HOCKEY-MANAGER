// Puck Dynasty tile hub — target-matched rendering (ARTIFACT_TARGET.jpg)
const TH_ICONS = {
  roster: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="8" r="3.6"/><path d="M3.5 19c.6-3.2 3.2-5 6.5-5s5.9 1.8 6.5 5"/><path d="M18.5 8v6M15.5 11h6"/></svg>',
  inbox: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 13l2.7-7.5h12.6L21 13v6a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19z"/><path d="M3 13h6l1.2 2h3.6L15 13h6"/></svg>',
  schedule: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/><path d="M7.5 13.5h3M7.5 16.5h5.5"/></svg>',
  stats: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16"/><path d="M7 20v-7M12 20V9M17 20v-10"/></svg>',
  lines: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M9 8.5h6M9 12h6M9 15.5h4"/></svg>',
  trades: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13l-3.5-3.5M20 16H7l3.5 3.5"/></svg>',
  scouting: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.3 15.3L20.5 20.5"/></svg>',
  staff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 19c.5-3 2.9-4.6 6-4.6s5.5 1.6 6 4.6"/><circle cx="17" cy="9" r="2.4"/><path d="M15.5 14.6c2.9.1 5 1.6 5.5 4.4"/></svg>',
  watch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="12.5" rx="2.5"/><path d="M10.5 9.8v4.4L14.5 12z"/></svg>',
  tactics: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8" fill="currentColor"/></svg>',
  default: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/></svg>',
};
const TH_PRIMARY = ['roster', 'inbox', 'schedule', 'stats'];

function thSeason(dateStr) {
  const m = String(dateStr || '').match(/(19|20)\d{2}/);
  if (!m) return 'FRANCHISE';
  const y = parseInt(m[0], 10);
  return `FRANCHISE · ${y}-${String(y + 1).slice(2)} SEASON`;
}

/* ---------- subtle team-color theming ----------
   Precomputes muted variants in JS (no color-mix dependency) and sets
   them as CSS vars on :root. Everything stays dark; tints are whispers. */
function _hexRgb(hex) {
  const m = /^#([0-9a-f]{6})$/i.exec(String(hex || '').trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function _mixHex(a, b, t) {
  // t=0 -> a, t=1 -> b
  const ca = _hexRgb(a), cb = _hexRgb(b);
  if (!ca || !cb) return a;
  const c = ca.map((v, i) => Math.round(v + (cb[i] - v) * t));
  return '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
}
function _rgba(hex, alpha) {
  const c = _hexRgb(hex);
  if (!c) return hex;
  return `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
}
function applyTeamColors(tc) {
  const root = document.documentElement;
  const p = (tc && _hexRgb(tc.primary)) ? tc.primary : '#3B82F6';
  const s = (tc && _hexRgb(tc.secondary)) ? tc.secondary : '#1E40AF';
  const set = (k, v) => root.style.setProperty(k, v);
  set('--team1', p);
  set('--team2', s);
  set('--team1-deep', _mixHex(p, '#000000', 0.45));   // hero gradient start
  set('--team1-soft', _mixHex(p, '#0e1626', 0.55));   // muted borders/accents
  set('--team1-wash', _rgba(p, 0.10));                // faint row backgrounds
  set('--team1-glow', _rgba(p, 0.28));                // hover glows
}

async function loadState() {
  try {
    const res = await fetch('/api/state');
    const s = await res.json();
    renderHub(s);
  } catch (e) {
    console.error('API failed', e);
  } finally {
    // Reveal the page only once data (or failure) is in — no staggered load.
    const l = document.getElementById('th-loading');
    if (l) l.classList.add('done');
  }
}

function renderHub(s) {
  const team = s.team || {};
  const rec = team.record || {};
  applyTeamColors(s.team_colors);
  document.getElementById('th-season').textContent = thSeason(s.date);
  document.getElementById('th-team').textContent = (team.name || '—').toUpperCase();
  document.getElementById('th-record').textContent =
    `${rec.w ?? 0}-${rec.l ?? 0}-${rec.otl ?? 0}`;

  // Hero next-game line (handles live + mock shapes)
  const ng = s.next_game;
  let nextTxt = 'Next: —';
  if (ng) {
    if (typeof ng.home === 'string' && typeof ng.away === 'string') {
      nextTxt = `Next: ${ng.away} at ${ng.home}`;
    } else if (ng.opponent) {
      const isHome = ng.is_home ?? ng.home;
      nextTxt = isHome ? `Next: ${ng.opponent} at ${team.name || ''}`
                       : `Next: ${team.name || ''} at ${ng.opponent}`;
    }
  }
  document.getElementById('th-next').textContent = nextTxt;

  // Tiles: primary four, then the rest under MORE
  const tiles = s.tiles || [];
  const grid = document.getElementById('th-grid');
  const more = document.getElementById('th-grid-more');
  grid.innerHTML = '';
  more.innerHTML = '';
  const primaries = [];
  const rest = [];
  for (const t of tiles) {
    if (t.id === 'continue') continue; // hero handles it
    (TH_PRIMARY.includes(t.id) ? primaries : rest).push(t);
  }
  // keep primary order stable
  primaries.sort((a, b) => TH_PRIMARY.indexOf(a.id) - TH_PRIMARY.indexOf(b.id));
  for (const t of primaries) grid.appendChild(thTile(t, false));
  for (const t of rest) more.appendChild(thTile(t, true));
  document.querySelector('.th-more-label').style.display = rest.length ? '' : 'none';

  renderPanels(s.panels || {});
  renderStrip(s.stat_strip || {});
  renderTicker(s.ticker || []);
  renderDateStreakPills(s);
}

/* Batch D: header date + streak pills. */
function renderDateStreakPills(s) {
  const d = document.getElementById('th-date-pill');
  if (d) d.textContent = '📅 ' + (s.date || '—');
  const st = document.getElementById('th-streak-pill');
  if (st) {
    const p = s.panels || {};
    const streak = (p.form && p.form.streak) || (s.stat_strip && s.stat_strip.streak) || '—';
    st.textContent = '🔥 ' + streak;
  }
}

function fmtCap(n) {
  if (n == null) return '—';
  const v = Number(n);
  if (!isFinite(v)) return '—';
  const m = v / 1e6;
  return '$' + (m >= 10 ? m.toFixed(1) : m.toFixed(2)) + 'M';
}

function ord(n) {
  if (n == null) return '';
  const v = Number(n);
  if (!isFinite(v)) return '';
  const teen = v % 100;
  if (teen >= 11 && teen <= 13) return v + 'th';
  return v + ({1: 'st', 2: 'nd', 3: 'rd'}[v % 10] || 'th');
}

function renderStrip(st) {
  const el = document.getElementById('th-strip');
  if (!el) return;
  const dash = v => (v == null || v === '' ? '—' : v);
  const blocks = [
    {label: 'Record', val: dash(st.record), sub: st.gp != null ? `${st.gp} GP` : ''},
    {label: 'Points', val: dash(st.points), sub: st.div_rank ? `${ord(st.div_rank)} in division` : ''},
    {label: 'Goals / GM', val: dash(st.gpg), sub: st.off_rank ? `Offense: ${ord(st.off_rank)}` : 'Offense'},
    {label: 'Against / GM', val: dash(st.gapg), sub: st.def_rank ? `Defense: ${ord(st.def_rank)}` : 'Defense'},
    {label: 'Power Play', val: st.pp_pct != null ? st.pp_pct + '%' : '—', sub: 'Conversion'},
    {label: 'Penalty Kill', val: st.pk_pct != null ? st.pk_pct + '%' : '—', sub: 'Kill rate'},
    {label: 'Streak', val: dash(st.streak), sub: st.last10 ? `Last 10: ${st.last10}` : 'Last 10'},
    {label: 'Cap Space', val: fmtCap(st.cap_space), sub: 'Salary cap'},
  ];
  el.innerHTML = blocks.map(b =>
    `<div class="th-strip-block"><div class="th-strip-val">${b.val}</div>` +
    `<div class="th-strip-label">${b.label}</div>` +
    (b.sub ? `<div class="th-strip-sub">${b.sub}</div>` : '') + `</div>`
  ).join('');
}

function renderTicker(items) {
  const track = document.getElementById('th-ticker-track');
  const bar = document.getElementById('th-ticker');
  if (!track || !bar) return;
  if (!items.length) { bar.style.display = 'none'; return; }
  bar.style.display = '';
  const sep = '<span class="th-ticker-sep">◆</span>';
  const html = items.map(i =>
    `<span class="th-ticker-item ${i.kind === 'score' ? 'is-score' : ''}">${esc(i.text)}</span>`
  ).join(sep) + sep;
  // Duplicate for a seamless loop
  track.innerHTML = html + html;
}

function renderPanels(p) {
  // --- Next game ---
  const ng = p.next_game;
  const ngBody = document.getElementById('panel-next-body');
  if (ng) {
    ngBody.innerHTML = `
      <div class="th-ng-click clickable" data-href="/schedule" title="Open schedule">
      <div class="th-ng-date">${esc(ng.date)}${ng.time ? ' · ' + esc(ng.time) : ''}</div>
      <div class="th-ng-matchup">
        <div class="th-ng-team">
          <span class="th-ng-abbr">${esc(ng.away_abbr)}</span>
          <span class="th-ng-name">${esc(ng.away)}</span>
          <span class="th-ng-rec">${esc(ng.away_rec)}</span>
        </div>
        <div class="th-ng-at">@</div>
        <div class="th-ng-team">
          <span class="th-ng-abbr">${esc(ng.home_abbr)}</span>
          <span class="th-ng-name">${esc(ng.home)}</span>
          <span class="th-ng-rec">${esc(ng.home_rec)}</span>
        </div>
      </div>
      <div class="th-ng-venue">${ng.is_home ? 'HOME' : 'AWAY'}</div>
      </div>`;
  } else {
    ngBody.innerHTML = '<div class="th-empty">No upcoming games</div>';
  }

  // --- Division standings ---
  const divName = p.division ? p.division.toUpperCase() + ' DIVISION' : 'DIVISION STANDINGS';
  document.getElementById('panel-standings-head').textContent = divName;
  const st = document.getElementById('panel-standings-table');
  const rows = (p.standings || []).map((r, i) => `
    <tr class="${r.is_user ? 'me' : ''} clickable" data-href="/team/${encodeURIComponent(r.name)}" title="Open team overview">
      <td class="rk">${i + 1}</td>
      <td class="tm"><span class="abbr">${esc(r.abbr)}</span> ${esc(r.name)}</td>
      <td>${r.w}</td><td>${r.l}</td><td>${r.otl}</td><td class="pts">${r.pts}</td>
    </tr>`).join('');
  st.innerHTML = `<thead><tr><th>#</th><th>TEAM</th><th>W</th><th>L</th><th>OTL</th><th>PTS</th></tr></thead><tbody>${rows || '<tr><td colspan="6" class="th-empty">—</td></tr>'}</tbody>`;

  // --- Team leaders ---
  const ld = p.leaders || {};
  const leadImg = r => r.portrait
    ? `<img class="th-lead-face" src="${esc(r.portrait)}" alt="" loading="lazy" onerror="this.remove()">`
    : '';
  const lcol = (title, list, key) => `
    <div class="th-lead-col"><div class="th-lead-title">${title}</div>
      ${(list || []).map((r, i) => `
        <div class="th-lead-row${r.id ? ' clickable' : ''}"${r.id ? ` data-href="/player/${esc(r.id)}" title="Open player profile"` : ''}>
          <span class="rk">${i + 1}</span>
          ${leadImg(r)}
          <span class="nm">${esc(r.name)} <em>${esc(r.pos)}</em></span>
          <span class="vl">${r[key]}</span>
        </div>`).join('') || '<div class="th-empty">—</div>'}
    </div>`;
  document.getElementById('panel-leaders-body').innerHTML =
    lcol('POINTS', ld.points, 'pts') + lcol('GOALS', ld.goals, 'g') + lcol('ASSISTS', ld.assists, 'a');

  // --- Recent form ---
  const f = p.form || {};
  const games = (f.last5 || []).map(g => `
    <div class="th-form-game">
      <span class="th-form-res ${g.res}">${g.res}</span>
      <span class="th-form-opp">${g.home ? 'vs' : '@'} ${esc(g.opp_abbr)}</span>
      <span class="th-form-score">${esc(g.score)}</span>
    </div>`).join('');
  document.getElementById('panel-form-body').innerHTML = `
    <div class="th-streak">STREAK <b>${esc(f.streak || '—')}</b></div>
    <div class="th-form-list">${games || '<div class="th-empty">No games yet</div>'}</div>`;

  renderNewPanels(p);
}

/* ==================================================================
 * Batch D: the dashboard_home.py cards the web was missing — schedule
 * (Upcoming/Results scopes), injuries, morale, prospects, milestones,
 * iconic games, inbox-recent. Player/team names link somewhere real.
 * ================================================================== */
function renderNewPanels(p) {
  // --- Schedule (scope dropdown) ---
  const sc = p.schedule || {};
  const scopeSel = document.getElementById('panel-sched-scope');
  const schedBody = document.getElementById('panel-sched-body');
  const paintSched = () => {
    const scope = scopeSel.value;
    const rows = (scope === 'results' ? sc.results : sc.upcoming) || [];
    schedBody.innerHTML = rows.length ? rows.map(r => `
      <div class="th-sched-row">
        <span class="th-sched-date">${esc(r.date)}</span>
        <span class="th-sched-opp">${esc(r.where)} ${esc(r.opp_abbr)}</span>
        ${r.score ? `<span class="th-form-res ${r.result}">${r.result}</span><span class="th-form-score">${esc(r.score)}</span>` : ''}
      </div>`).join('')
      : '<div class="th-empty">—</div>';
  };
  scopeSel.onchange = paintSched;
  paintSched();

  // --- Injuries ---
  const inj = p.injuries || {};
  document.getElementById('panel-inj-body').innerHTML =
    (inj.players || []).length
      ? (inj.players || []).map(pl => `
        <div class="th-lead-row${pl.id ? ' clickable' : ''}"${pl.id ? ` data-href="/player/${esc(pl.id)}" title="Open player profile"` : ''}>
          <span class="nm">${esc(pl.name)}</span>
          <span class="vl">${esc(pl.desc)} · ${esc(pl.out)} out</span>
        </div>`).join('')
      : '<div class="th-empty">No injuries</div>';

  // --- Morale ---
  const mo = p.morale || {};
  document.getElementById('panel-morale-body').innerHTML = `
    <div class="th-streak">AVG <b>${esc(mo.average)} · ${esc(mo.label)}</b></div>
    ${(mo.bands || []).map(b => `
      <div class="th-sched-row"><span>${esc(b.band)}</span><span class="vl">${b.count} players</span></div>`).join('')}`;

  // --- Prospects ---
  const pr = p.prospects || {};
  document.getElementById('panel-prosp-body').innerHTML =
    (pr.players || []).length
      ? (pr.players || []).map(pl => `
        <div class="th-lead-row${pl.id ? ' clickable' : ''}"${pl.id ? ` data-href="/player/${esc(pl.id)}" title="Open player profile"` : ''}>
          <span class="nm">${esc(pl.name)} <em>${esc(pl.position)} · ${pl.age}</em></span>
          <span class="vl">${esc(pl.potential)}${pl.tier ? ' · ' + esc(pl.tier) : ''}</span>
        </div>`).join('')
      : '<div class="th-empty">No prospects tracked</div>';

  // --- Milestones ---
  const mi = p.milestones || {};
  document.getElementById('panel-mile-body').innerHTML =
    (mi.items || []).length
      ? (mi.items || []).map(m => `
        <div class="th-sched-row clickable" data-href="/player/${esc(m.player_id)}" title="Open player profile">
          <span class="nm">${esc(m.name)}</span><span class="vl">🏆 ${esc(m.text)}</span>
        </div>`).join('')
      : '<div class="th-empty">No milestones near</div>';

  // --- Iconic games ---
  const ic = p.iconic_games || {};
  document.getElementById('panel-iconic-body').innerHTML =
    (ic.entries || []).length
      ? (ic.entries || []).map(e => `
        <div class="th-sched-row">
          <span class="nm">${e.starred ? '⭐ ' : ''}${esc(e.headline)}</span>
          <span class="vl">${esc(e.date)}${e.score ? ' · ' + esc(e.score) : ''}</span>
        </div>`).join('') +
        (ic.more ? `<div class="th-empty">+${ic.more} more in League History</div>` : '')
      : '<div class="th-empty">No iconic games yet</div>';

  // --- Inbox recent ---
  const ib = p.inbox_recent || {};
  document.getElementById('panel-inbox-body').innerHTML =
    (ib.messages || []).length
      ? (ib.messages || []).map(m => `
        <div class="th-sched-row clickable" data-href="/inbox" title="Open inbox">
          <span class="nm${m.is_read ? '' : ' th-unread'}">${m.action ? '🔴 ' : ''}${m.urgent ? '🟡 ' : ''}${esc(m.subject)}</span>
          <span class="vl">${esc(m.sender)}</span>
        </div>`).join('') +
        (ib.unread ? `<div class="th-empty">${ib.unread} unread</div>` : '')
      : '<div class="th-empty">Inbox is quiet</div>';
}

/* ==================================================================
 * Batch D: auto-advance loop (main.py:8639 _auto_advance parity).
 * 800ms/tick through the normal Continue funnel. Stops on:
 *   - blockers (Continue is blocked)
 *   - the user's team playing today (game day)
 *   - a NEW actionable message arriving (trade offer, RFA, etc.)
 * ================================================================== */
const AutoAdvance = {
  timer: null,
  seenActionable: null,

  async toggle() {
    if (this.timer) { this.stop('toggled off'); return; }
    await this.start();
  },

  async start() {
    const st = await (await fetch('/api/continue_state')).json().catch(() => null);
    if (!st) return;
    if (st.blocked) { showBlockerModal(st.blockers); return; }
    this.seenActionable = await this.actionableCount();
    this.timer = setInterval(() => this.tick(), 800);
    const b = document.getElementById('btn-auto-advance');
    b.classList.add('on');
    b.textContent = '⏸ Auto-advancing…';
    note('Auto-advance on — simming days until something needs you.');
  },

  stop(reason) {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    const b = document.getElementById('btn-auto-advance');
    if (b) { b.classList.remove('on'); b.textContent = '▶ Auto-advance'; }
    if (reason) note('Auto-advance stopped: ' + reason + '.');
  },

  async actionableCount() {
    try {
      const r = await fetch('/api/inbox?filter=action');
      const msgs = await r.json();
      return msgs.length;
    } catch (e) { return 0; }
  },

  async tick() {
    try {
      const st = await (await fetch('/api/continue_state')).json();
      if (st.blocked) {
        this.stop('needs your attention');
        showBlockerModal(st.blockers);
        return;
      }
      if (st.has_games) {
        this.stop('game day — your team plays today');
        return;
      }
      const n = await this.actionableCount();
      if (n > (this.seenActionable || 0)) {
        this.stop('a message needs your answer');
        window.location.href = '/inbox?filter=action';
        return;
      }
      this.seenActionable = n;
      await fetch('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'advance_day'}),
      });
    } catch (e) {
      this.stop('error — ' + e.message);
    }
  },
};

function note(msg) {
  const n = document.getElementById('auto-note');
  if (n) { n.textContent = msg; }
}

document.getElementById('btn-auto-advance')?.addEventListener('click', (e) => {
  e.stopPropagation(); // the hero itself advances one day
  AutoAdvance.toggle();
});

/* ==================================================================
 * Batch D: global shortcuts.
 *   Space = advance one day (Continue)
 *   Ctrl+S = quicksave
 *   ? = keyboard shortcut cheatsheet
 * ================================================================== */
function showCheatsheet() {
  const ov = document.createElement('div');
  ov.className = 'modal-ov';
  ov.id = 'cheatsheet-modal';
  ov.innerHTML = `
    <div class="modal-card">
      <h2>Keyboard shortcuts</h2>
      <div class="th-sched-row"><span><b>Space</b></span><span class="vl">Advance one day (Continue)</span></div>
      <div class="th-sched-row"><span><b>Ctrl+S</b></span><span class="vl">Quick-save</span></div>
      <div class="th-sched-row"><span><b>?</b></span><span class="vl">This cheatsheet</span></div>
      <div class="th-sched-row"><span><b>Esc</b></span><span class="vl">Close dialogs</span></div>
      <button class="modal-close" id="cheatsheet-close">Close</button>
    </div>`;
  document.body.appendChild(ov);
  const close = () => ov.remove();
  document.getElementById('cheatsheet-close').addEventListener('click', close);
  ov.addEventListener('click', (e) => { if (e.target === ov) close(); });
}

document.addEventListener('keydown', (e) => {
  const tag = (e.target.tagName || '').toLowerCase();
  const typing = tag === 'input' || tag === 'textarea' || tag === 'select';
  if (e.key === '?' && !typing) { showCheatsheet(); return; }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    fetch('/api/save/quicksave', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({nonce: Date.now().toString(36)}),
    }).then(() => note('Quick-saved ✓')).catch(() => note('Quick-save failed.'));
    return;
  }
  if (e.key === ' ' && !typing && !document.getElementById('blocker-modal')) {
    // Skip when the hero itself has focus (it handles Space on its own).
    if (e.target.closest && e.target.closest('#th-hero')) return;
    e.preventDefault();
    heroActivate();
  }
});

function thTile(t, compact) {
  const el = document.createElement('button');
  el.className = 'th-tile';
  el.setAttribute('aria-label', t.title);
  el.innerHTML = `
    ${t.badge ? `<span class="th-badge">${t.badge}</span>` : ''}
    <span class="th-icon">${TH_ICONS[t.id] || TH_ICONS.default}</span>
    <h3 class="th-label">${esc(t.title)}</h3>
    ${compact && t.subtitle ? `<p class="th-sub">${esc(t.subtitle)}</p>` : ''}`;
  el.addEventListener('click', () => openTile(t));
  return el;
}

function openTile(t) {
  const known = ['inbox','roster','schedule','lines','waivers','captains',
    'trades','trade_block','free_agents','staff','development','camp','morale',
    'standings','stats','playoffs','calendar','news','history','finances',
    'contracts','scouting','draft','settings','save','tactics'];
  if (known.includes(t.id)) { window.location.href = '/' + t.id; return; }
  console.log('open', t.id);
}

/* ---------- hero: Continue flow ---------- */
function heroActivate() {
  continueFlow();
}
document.getElementById('th-hero').addEventListener('click', heroActivate);
document.getElementById('th-hero').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); heroActivate(); }
});

async function continueFlow() {
  // Multiplayer (Batch E): the Continue button becomes the EHM ready
  // vote. Clients vote; the host votes too (the day advances only when
  // every manager is ready). Spectators can't advance.
  let mpRole = 'none';
  try {
    const mp = await (await fetch('/api/mp/state')).json();
    mpRole = mp.role || 'none';
    if (mpRole === 'spectator') {
      mpToast('Spectating — management actions are disabled.');
      return;
    }
    if (mpRole === 'client') {
      await mpToggleReady();
      return;
    }
  } catch (e) { /* fall through to single-player flow */ }
  let st;
  try {
    st = await (await fetch('/api/continue_state')).json();
  } catch (e) { return; }
  if (!st.blocked) {
    // Host mode: the click is a ready vote, not an instant advance.
    if (mpRole === 'host') { advanceDay(st); return; }
    if (confirm('Advance the day?')) advanceDay(st);
    return;
  }
  showBlockerModal(st.blockers);
}

/* ---------- multiplayer ready gate (Batch E) ---------- */
async function mpToggleReady() {
  const title = document.querySelector('.th-hero-title');
  const prev = title ? title.textContent : '';
  if (title) title.textContent = '…';
  try {
    const r = await fetch('/api/mp/ready', {method: 'POST'});
    const d = await r.json();
    if (!d.ok) { if (title) title.textContent = prev; return; }
    const nonce = d.nonce;
    for (let i = 0; i < 20; i++) {
      await new Promise(res => setTimeout(res, 500));
      const r2 = await fetch('/api/mp/result?nonce=' + encodeURIComponent(nonce));
      const d2 = await r2.json();
      if (d2.pending) continue;
      const res = d2.result || {};
      if (res.blocked) {
        showBlockerModal(res.blockers || []);
      } else if (!res.ok) {
        mpToast(res.message || 'Vote failed.');
      }
      break;
    }
  } catch (e) {}
  mpRefreshHero();
}

/* Repaint the hero button for the MP ready state (polled).
   Uses the non-draining /api/mp/state so trade-offer events stay in
   the inbox for the MP bar's /api/mp/game poll. */
let mpHeroTimer = null;
async function mpRefreshHero() {
  try {
    const mp = await (await fetch('/api/mp/state')).json();
    if (!mp || mp.role === 'none') return false;
    const adv = mp.advance || {};
    const title = document.querySelector('.th-hero-title');
    const next = document.getElementById('th-next');
    const counts = adv.needed_count
      ? ' (' + (adv.ready_count || 0) + '/' + adv.needed_count + ')' : '';
    if (mp.role === 'host') {
      const me = adv.me_ready ? '✓ READY — CLICK TO UNREADY' : 'READY? (CLICK WHEN DONE FOR TODAY)';
      if (title) title.textContent = (adv.me_ready ? '✓ READY' : 'READY?') + counts;
      if (next) {
        const waiting = (adv.waiting || []).join(', ');
        next.textContent = adv.all_ready ? 'Everyone is ready — advancing…'
          : waiting ? 'Waiting on: ' + waiting : 'Click when done for today';
      }
      void me;
    } else if (mp.role === 'client') {
      if (title) title.textContent = (adv.me_ready ? '✓ READY' : 'READY?') + counts;
      if (next) {
        const waiting = (adv.waiting || []).join(', ');
        next.textContent = adv.all_ready ? 'Everyone is ready — host advances…'
          : waiting ? 'Waiting on: ' + waiting : 'Vote to advance the day';
      }
    } else {
      if (title) title.textContent = 'SPECTATING';
      if (next) next.textContent = 'Watch the league unfold — no management actions';
    }
    return true;
  } catch (e) { return false; }
}

function mpToast(msg) {
  try {
    const t = document.createElement('div');
    t.className = 'mp-toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.classList.add('show'), 30);
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, 3200);
  } catch (e) {}
}

async function advanceDay(st) {
  // If watch mode is on and today has games, open the visualizer instead.
  try {
    const wm = await (await fetch('/api/watch_mode')).json();
    if (wm.mode === 'watch' && st && st.has_games) {
      window.location.href = '/watch';
      return;
    }
  } catch (e) { /* fall through to quick sim */ }
  // Batch A: after the day sims, show the daily results (desktop parity
  // for _post_advance_landing) instead of a bare reload — when the simmed
  // day had games. The results API also drives the inbox nudge.
  showDayLoading();
  fetch('/api/command', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({op: 'advance_day'}),
  }).then(() => setTimeout(showDailyResults, 1400))
    .catch(() => { hideDayLoading(); window.location.reload(); });
}

async function showDailyResults() {
  hideDayLoading();
  let data = null;
  try {
    data = await (await fetch('/api/daily_results')).json();
  } catch (e) { /* fall through to reload */ }
  if (data && data.ok && data.games_played > 0) {
    showResultsModal(data);
    refreshInboxBadge();
  } else {
    window.location.reload();
  }
}

async function refreshInboxBadge() {
  try {
    const s = await (await fetch('/api/state')).json();
    const n = s && s.inbox ? (s.inbox.unread || 0) : 0;
    const badge = document.querySelector('[aria-label="Inbox"] .th-badge');
    if (badge) {
      badge.textContent = n;
      badge.style.display = n > 0 ? '' : 'none';
    }
  } catch (e) { /* best-effort */ }
}

function showDayLoading() {
  closeResultsModal();
  const ov = document.createElement('div');
  ov.className = 'modal-ov'; ov.id = 'day-loading';
  ov.innerHTML = `<div class="modal-card day-loading-card">
    <div class="th-spinner"></div><div>Simulating the day…</div></div>`;
  document.body.appendChild(ov);
}
function hideDayLoading() {
  const m = document.getElementById('day-loading');
  if (m) m.remove();
}

/* ---------- daily results modal (Games / Standings / News tabs) ---------- */
function closeResultsModal() {
  const m = document.getElementById('results-modal');
  if (m) m.remove();
}

function resultsGameRow(g) {
  const note = g.note ? ` <span class="res-note">${esc(g.note)}</span>` : '';
  const bs = g.date_iso
    ? `<a class="res-box" href="${'/boxscore?' + new URLSearchParams({date: g.date_iso, home: g.home, away: g.away}).toString()}">Box&nbsp;Score&nbsp;→</a>`
    : '';
  return `<div class="res-game">
    <a class="res-team" href="/team/${encodeURIComponent(g.away)}">${esc(g.away_abbr)}</a>
    <span class="res-score">${g.away_score} – ${g.home_score}</span>
    <a class="res-team" href="/team/${encodeURIComponent(g.home)}">${esc(g.home_abbr)}</a>
    ${note}
    ${bs}
  </div>`;
}

function showResultsModal(d) {
  closeResultsModal();
  const ov = document.createElement('div');
  ov.className = 'modal-ov'; ov.id = 'results-modal';
  const gamesHtml = (d.games || []).map(resultsGameRow).join('') ||
    '<div class="res-empty">No games recorded.</div>';
  const userHtml = d.user_game ? `
    <div class="res-usergame">
      <div class="res-usergame-title">Your game</div>
      ${resultsGameRow(d.user_game)}
      ${(d.highlights || []).map(h => `<div class="res-hl">▸ ${esc(h)}</div>`).join('')}
    </div>` : '';
  const stRows = (d.standings || []).map((r, i) =>
    `<tr class="${r.is_user ? 'row-user' : ''}"><td class="c-rank">${i + 1}</td>` +
    `<td class="c-team"><a class="plink" href="/team/${encodeURIComponent(r.team)}">${esc(r.team)}</a></td>` +
    `<td>${r.gp}</td><td>${r.w}</td><td>${r.l}</td><td>${r.otl}</td>` +
    `<td class="c-pts">${r.pts}</td><td>${r.gf}</td><td>${r.ga}</td><td>${r.diff > 0 ? '+' : ''}${r.diff}</td></tr>`
  ).join('');
  const newsHtml = (d.news || []).map(n =>
    `<div class="res-news-item"><span class="res-news-date">${esc(n.date)}</span>${esc(n.story)}</div>`
  ).join('') || '<div class="res-empty">No news today.</div>';
  ov.innerHTML = `
  <div class="modal-card results-card">
    <h2>Daily Results</h2>
    <p class="modal-sub">${esc(d.date_label)} · ${d.games_played} game${d.games_played === 1 ? '' : 's'}</p>
    ${userHtml}
    <div class="res-tabs" role="tablist">
      <button class="res-tab active" data-rtab="games">Games</button>
      <button class="res-tab" data-rtab="standings">Standings</button>
      <button class="res-tab" data-rtab="news">News</button>
    </div>
    <div class="res-pane" data-rpane="games">${gamesHtml}</div>
    <div class="res-pane" data-rpane="standings" hidden>
      <div class="tbl-wrap"><table class="res-table"><thead><tr>
        <th>#</th><th>Team</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>PTS</th><th>GF</th><th>GA</th><th>DIFF</th>
      </tr></thead><tbody>${stRows}</tbody></table></div>
    </div>
    <div class="res-pane" data-rpane="news" hidden>${newsHtml}</div>
    <button class="modal-close" id="results-close">Continue</button>
  </div>`;
  document.body.appendChild(ov);
  ov.querySelectorAll('.res-tab').forEach(t => t.addEventListener('click', () => {
    ov.querySelectorAll('.res-tab').forEach(x => x.classList.toggle('active', x === t));
    ov.querySelectorAll('.res-pane').forEach(p => { p.hidden = p.dataset.rpane !== t.dataset.rtab; });
  }));
  const done = () => { closeResultsModal(); window.location.reload(); };
  document.getElementById('results-close').addEventListener('click', done);
  ov.addEventListener('click', e => { if (e.target === ov) done(); });
}

function showBlockerModal(blockers) {
  closeBlockerModal();
  const ov = document.createElement('div');
  ov.className = 'modal-ov'; ov.id = 'blocker-modal';
  // Batch A: every blocker gets its desktop action set — primary jump
  // (web route with the desktop's own button label), auto-resolve, and
  // the secondary quick fix (e.g. "IR injured players").
  const cards = blockers.map(b => `
    <div class="blocker-card">
      <div class="b-title">${esc(b.title)}</div>
      <div class="b-detail">${esc(b.detail)}</div>
      <div class="b-actions">
        ${b.web_route ? `<a class="btn-primary-blue" href="${b.web_route}">${esc(b.primary_label || 'Fix it →')}</a>` : ''}
        ${b.has_auto ? `<button class="btn-auto" data-bid="${esc(b.id)}" data-kind="auto">⚡ ${esc(b.auto_label)}</button>` : ''}
        ${b.has_secondary ? `<button class="btn-secondary" data-bid="${esc(b.id)}" data-kind="secondary">${esc(b.secondary_label)}</button>` : ''}
      </div>
    </div>`).join('');
  ov.innerHTML = `
    <div class="modal-card">
      <h2>Can't advance yet</h2>
      <p class="modal-sub">${blockers.length} thing${blockers.length === 1 ? '' : 's'} need${blockers.length === 1 ? 's' : ''} your attention before the day can advance.</p>
      ${cards}
      <button class="modal-close" id="blocker-close">Close</button>
    </div>`;
  document.body.appendChild(ov);
  document.getElementById('blocker-close').addEventListener('click', closeBlockerModal);
  ov.addEventListener('click', e => { if (e.target === ov) closeBlockerModal(); });
  ov.querySelectorAll('.btn-auto, .btn-secondary').forEach(btn =>
    btn.addEventListener('click', async () => {
      btn.disabled = true; btn.textContent = 'Working…';
      await fetch('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'resolve_blocker', blocker_id: btn.dataset.bid, kind: btn.dataset.kind || 'auto'}),
      });
      setTimeout(async () => {
        const st = await (await fetch('/api/continue_state')).json();
        if (st.blocked) showBlockerModal(st.blockers);
        else { closeBlockerModal(); advanceDay(); }
      }, 800);
    }));
}

function closeBlockerModal() {
  const m = document.getElementById('blocker-modal');
  if (m) m.remove();
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

/* ---------- top bar: back + menu ---------- */
document.getElementById('btn-back').addEventListener('click', () => {
  if (history.length > 1) history.back();
});
const menuBtn = document.getElementById('btn-menu');
const menu = document.getElementById('th-menu');
menuBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  menu.hidden = !menu.hidden;
});
document.addEventListener('click', (e) => {
  if (!menu.hidden && !e.target.closest('.th-menuwrap')) menu.hidden = true;
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (!menu.hidden) menu.hidden = true;
    closeBlockerModal();
  }
});

function exitGame() {
  if (!confirm('Exit Puck Dynasty? Make sure your career is saved.')) return;
  fetch('/api/exit', {method: 'POST'}).catch(() => {});
  document.body.innerHTML = '<div style="display:flex;height:100vh;align-items:center;justify-content:center;color:#888;font-size:18px">Puck Dynasty has exited. You can close this tab.</div>';
}
document.getElementById('btn-exit')?.addEventListener('click', exitGame);
document.getElementById('menu-exit')?.addEventListener('click', exitGame);

loadState();

// Multiplayer hero repaint (Batch E): only polls when an MP game is active.
mpRefreshHero().then(function (active) {
  if (active && !mpHeroTimer) {
    mpHeroTimer = setInterval(mpRefreshHero, 3000);
  }
});

// Delegated clicks for at-a-glance panels: any .clickable with data-href navigates.
document.addEventListener('click', (e) => {
  const t = e.target.closest('.clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
