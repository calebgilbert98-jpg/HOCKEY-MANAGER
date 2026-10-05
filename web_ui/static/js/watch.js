/* Puck Dynasty web visualizer — broadcast dark-rink canvas renderer.
 *
 * Dark "night game on TV" ice, jersey-numbered skater dots with trails,
 * puck with glow, broadcast scorebug, animated event banners, event ticker.
 *
 * SSE contract (unchanged, from web_ui/screens/watch.py):
 *   meta      {home, away, home_abbr, away_abbr}
 *   skate     {period, clock, score, skaters[{x,y,team,name,jersey}],
 *              goalies[{...}], puck{x,y}, possession}
 *   highlight {kind, text, team, period, clock, score}
 *   game_end  {score, home_abbr, away_abbr}
 */
(function () {
'use strict';

const canvas = document.getElementById('rink');
const ctx = canvas.getContext('2d');

// Rink coords: 200 x 85 ft (NHL)
const RL = 200, RW = 85;
let scale = 4, ox = 0, oy = 0, dpr = 1;

/* NHL primary colors by abbreviation (scorebug pills + skater dots). */
const NHL_COLORS = {
  ANA: '#B9975B', ARI: '#8C2633', BOS: '#FFB81C', BUF: '#002654', CGY: '#C8102E',
  CAR: '#CC0000', CHI: '#CF0A2C', COL: '#6F263D', CBJ: '#002654', DAL: '#006847',
  DET: '#CE1126', EDM: '#FF4C00', FLA: '#C8102E', LAK: '#111111', MIN: '#154734',
  MTL: '#AF1E2D', NSH: '#FFB81C', NJD: '#CE1126', NYI: '#00539B', NYR: '#0038A8',
  OTT: '#C52032', PHI: '#F74902', PIT: '#FCB514', SJS: '#006D75', SEA: '#68A2B9',
  STL: '#002F87', TBL: '#002868', TOR: '#00205B', VAN: '#00205B', VGK: '#B4975A',
  WSH: '#C8102E', WPG: '#041E42', UTA: '#6CACE4',
};
const FALLBACK = ['#1d4ed8', '#c8102e'];

function teamColor(abbr, idx) {
  return NHL_COLORS[String(abbr || '').toUpperCase()] || FALLBACK[idx % 2];
}
function readableText(hex) {
  // white text unless the bg is very light (e.g. BOS gold, PIT gold)
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.62 ? '#101418' : '#ffffff';
}

/* ---------------- state ---------------- */
let cur = null, prev = null, prevT = 0, curT = 0;
let paused = false, speed = 1;
let homeAbbr = '', awayAbbr = '';
let homeColor = FALLBACK[0], awayColor = FALLBACK[1];
let followName = null;

const puckTrail = [];
const skaterTrails = new Map();   // name -> [{x,y}]
const effects = [];               // {kind,x,y,born,life}
const bannerQueue = [];
let activeBanner = null;
let flashUntil = 0, flashRGB = '255,215,0';

const X = x => ox + x * scale;
const Y = y => oy + y * scale;

function resize() {
  const stage = canvas.parentElement;
  dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.max(1, Math.round(stage.clientWidth * dpr));
  canvas.height = Math.max(1, Math.round(stage.clientHeight * dpr));
  canvas.style.width = stage.clientWidth + 'px';
  canvas.style.height = stage.clientHeight + 'px';
  const s = Math.min(canvas.width / (RL + 6), canvas.height / (RW + 6));
  scale = s;
  ox = (canvas.width - RL * s) / 2;
  oy = (canvas.height - RW * s) / 2;
  rinkCache = null;
}
window.addEventListener('resize', resize);

/* ---------------- dark rink art (cached) ---------------- */
let rinkCache = null, rinkCacheKey = '';
function drawRink() {
  const key = canvas.width + 'x' + canvas.height;
  if (!rinkCache || rinkCacheKey !== key) {
    rinkCache = document.createElement('canvas');
    rinkCache.width = canvas.width; rinkCache.height = canvas.height;
    rinkCacheKey = key;
    paintRink(rinkCache.getContext('2d'));
  }
  ctx.drawImage(rinkCache, 0, 0);
}

function paintRink(c) {
  const W = canvas.width, H = canvas.height;
  const Xc = x => ox + x * scale, Yc = y => oy + y * scale;
  const R = (x, y, w, h, r) => {
    c.beginPath();
    c.moveTo(x + r, y);
    c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r);
    c.closePath();
  };

  // arena surround: near-black navy
  c.fillStyle = '#05080f';
  c.fillRect(0, 0, W, H);

  // dark ice: radial-ish gradient, lighter at center
  const g = c.createRadialGradient(W / 2, H / 2, 10, W / 2, H / 2, Math.max(W, H) * 0.7);
  g.addColorStop(0, '#182844');
  g.addColorStop(0.55, '#101b31');
  g.addColorStop(1, '#0a1322');
  c.fillStyle = g;
  R(Xc(-2), Yc(-2), (RL + 4) * scale, (RW + 4) * scale, 20 * scale); c.fill();

  // subtle skate-scratch sheen
  c.strokeStyle = 'rgba(140,170,220,0.05)'; c.lineWidth = 1;
  for (let i = 0; i < 40; i++) {
    const y0 = Yc(3 + ((i * 37) % 79));
    const x0 = Xc(4 + ((i * 53) % 192));
    c.beginPath(); c.moveTo(x0, y0);
    c.lineTo(x0 + 16 * scale / 4, y0 + 4 * scale / 4); c.stroke();
  }

  const lw = Math.max(1.5, scale * 0.55);
  const RED = '#e5484d', BLUE = '#3f8cff';

  // boards: dark steel frame with light top edge
  c.lineWidth = Math.max(6, scale * 1.6);
  c.strokeStyle = '#233654';
  R(Xc(0), Yc(0), RL * scale, RW * scale, 18 * scale); c.stroke();
  c.lineWidth = Math.max(1.5, scale * 0.28);
  c.strokeStyle = 'rgba(160,195,245,0.5)';
  R(Xc(0), Yc(0), RL * scale, RW * scale, 18 * scale); c.stroke();

  // center red line
  c.strokeStyle = RED; c.lineWidth = lw * 1.4;
  c.beginPath(); c.moveTo(Xc(100), Yc(2)); c.lineTo(Xc(100), Yc(83)); c.stroke();
  // blue lines
  c.strokeStyle = BLUE; c.lineWidth = lw * 2.6;
  for (const bx of [75, 125]) {
    c.beginPath(); c.moveTo(Xc(bx), Yc(2)); c.lineTo(Xc(bx), Yc(83)); c.stroke();
  }
  // goal lines
  c.strokeStyle = RED; c.lineWidth = lw * 0.9;
  for (const gx of [11, 189]) {
    c.beginPath(); c.moveTo(Xc(gx), Yc(4)); c.lineTo(Xc(gx), Yc(81)); c.stroke();
  }

  // center-ice circle + dot
  c.strokeStyle = 'rgba(63,140,255,0.75)'; c.lineWidth = lw;
  c.beginPath(); c.arc(Xc(100), Yc(42.5), 15 * scale / 4, 0, Math.PI * 2); c.stroke();
  c.fillStyle = BLUE;
  c.beginPath(); c.arc(Xc(100), Yc(42.5), 1.4 * scale / 4, 0, Math.PI * 2); c.fill();

  // end-zone faceoff circles: dot + ring + hash marks
  for (const gx of [11, 189]) {
    const sgn = gx < 100 ? 1 : -1;
    for (const dy of [20.5, 64.5]) {
      const ex = Xc(gx + 20 * sgn), ey = Yc(dy);
      c.strokeStyle = 'rgba(229,72,77,0.8)'; c.lineWidth = lw * 0.9;
      c.beginPath(); c.arc(ex, ey, 15 * scale / 4, 0, Math.PI * 2); c.stroke();
      c.fillStyle = RED;
      c.beginPath(); c.arc(ex, ey, 1.6 * scale / 4, 0, Math.PI * 2); c.fill();
      // hash ticks
      c.strokeStyle = 'rgba(229,72,77,0.65)'; c.lineWidth = lw * 0.7;
      for (const sx of [-1, 1]) {
        const hx = ex + sx * 5.5 * scale / 4;
        c.beginPath(); c.moveTo(hx - 1.6 * scale / 4, ey); c.lineTo(hx + 1.6 * scale / 4, ey); c.stroke();
      }
    }
  }
  // neutral-zone dots
  c.fillStyle = 'rgba(229,72,77,0.85)';
  for (const [dx, dy] of [[80, 20.5], [80, 64.5], [120, 20.5], [120, 64.5]]) {
    c.beginPath(); c.arc(Xc(dx), Yc(dy), 1.2 * scale / 4, 0, Math.PI * 2); c.fill();
  }

  // creases (translucent ice blue) + nets
  for (const gx of [11, 189]) {
    const dir = gx < 100 ? 1 : -1;
    c.fillStyle = 'rgba(120,170,240,0.16)';
    c.beginPath();
    c.arc(Xc(gx), Yc(42.5), 6 * scale / 4, dir > 0 ? -Math.PI / 2 : Math.PI / 2, dir > 0 ? Math.PI / 2 : Math.PI * 1.5);
    c.closePath(); c.fill();
    c.strokeStyle = 'rgba(229,72,77,0.7)'; c.lineWidth = lw * 0.7;
    c.beginPath();
    c.arc(Xc(gx), Yc(42.5), 6 * scale / 4, dir > 0 ? -Math.PI / 2 : Math.PI / 2, dir > 0 ? Math.PI / 2 : Math.PI * 1.5);
    c.stroke();
    // net frame
    c.strokeStyle = '#f0f4fa'; c.lineWidth = Math.max(2, lw);
    c.beginPath();
    c.moveTo(Xc(gx), Yc(38.5)); c.lineTo(Xc(gx + dir * 3.2), Yc(38.5));
    c.lineTo(Xc(gx + dir * 3.2), Yc(46.5)); c.lineTo(Xc(gx), Yc(46.5));
    c.stroke();
  }

  // trapezoid
  c.strokeStyle = 'rgba(229,72,77,0.35)'; c.lineWidth = lw * 0.7;
  for (const gx of [11, 189]) {
    const dir = gx < 100 ? 1 : -1;
    c.beginPath();
    c.moveTo(Xc(gx), Yc(34)); c.lineTo(Xc(gx + dir * 11), Yc(28));
    c.moveTo(Xc(gx), Yc(51)); c.lineTo(Xc(gx + dir * 11), Yc(57));
    c.stroke();
  }
}

/* ---------------- skaters ---------------- */
function skaterColor(team) { return team === 0 ? homeColor : awayColor; }

function drawSkater(x, y, team, opts) {
  opts = opts || {};
  const px = X(x), py = Y(y);
  const r = (opts.goalie ? 15 : 13) * scale / 4;
  const col = skaterColor(team);
  const key = opts.name || (team + ':' + Math.round(x) + ':' + Math.round(y));

  // motion trail
  let tr = skaterTrails.get(key);
  if (!tr) { tr = []; skaterTrails.set(key, tr); }
  tr.push({ x: px, y: py });
  if (tr.length > 7) tr.shift();
  for (let i = 0; i < tr.length; i++) {
    const a = (i / tr.length) * 0.22;
    ctx.fillStyle = hexA(col, a);
    ctx.beginPath();
    ctx.arc(tr[i].x, tr[i].y, r * (0.35 + 0.65 * i / tr.length), 0, Math.PI * 2);
    ctx.fill();
  }

  // drop shadow
  ctx.fillStyle = 'rgba(0,0,0,0.45)';
  ctx.beginPath(); ctx.arc(px + r * 0.22, py + r * 0.3, r, 0, Math.PI * 2); ctx.fill();

  // body
  ctx.fillStyle = col;
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  ctx.lineWidth = Math.max(2, r * 0.22);
  ctx.strokeStyle = '#f2f6fc';
  ctx.stroke();

  // jersey number
  const num = opts.jersey != null && opts.jersey !== '' ? String(opts.jersey) : '';
  if (num) {
    ctx.fillStyle = readableText(col);
    ctx.font = '800 ' + Math.round(r * 1.05) + 'px "Arial Narrow", Arial, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(num.length > 2 ? num.slice(0, 2) : num, px, py + r * 0.06);
  } else if (opts.goalie) {
    ctx.fillStyle = readableText(col);
    ctx.font = '800 ' + Math.round(r * 0.95) + 'px "Arial Narrow", Arial, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('G', px, py + r * 0.06);
  }

  // puck-carrier ring + name tag
  if (opts.hasPuck) {
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.arc(px, py, r + 5, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,215,0,0.85)'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(px, py, r + 8, 0, Math.PI * 2); ctx.stroke();
    if (opts.name) drawNameTag(px, py - r - 12, opts.name);
  }
  // followed player
  if (followName && opts.name === followName) {
    ctx.strokeStyle = '#7dd3fc'; ctx.lineWidth = 2;
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.arc(px, py, r + 11, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    if (opts.name) drawNameTag(px, py - r - 12, opts.name);
  }
}

function drawNameTag(px, py, name) {
  ctx.font = '700 12px "Arial Narrow", Arial, sans-serif';
  const w = ctx.measureText(name).width + 14;
  ctx.fillStyle = 'rgba(5,8,15,0.88)';
  const bx = px - w / 2, by = py - 10;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(bx, by, w, 20, 4); else ctx.rect(bx, by, w, 20);
  ctx.fill();
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(name, px, by + 10);
}

function hexA(hex, a) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return 'rgba(' + r + ',' + g + ',' + b + ',' + a.toFixed(3) + ')';
}

/* ---------------- puck ---------------- */
function drawPuck(x, y) {
  const px = X(x), py = Y(y);
  puckTrail.push({ x: px, y: py });
  if (puckTrail.length > 12) puckTrail.shift();
  for (let i = 0; i < puckTrail.length; i++) {
    const t = puckTrail[i], a = (i / puckTrail.length) * 0.3;
    ctx.fillStyle = 'rgba(180,200,235,' + a.toFixed(3) + ')';
    ctx.beginPath();
    ctx.arc(t.x, t.y, (1 + (i / puckTrail.length) * 2.4) * scale / 4, 0, Math.PI * 2);
    ctx.fill();
  }
  const r = 4.2 * scale / 4;
  // glow
  const glow = ctx.createRadialGradient(px, py, 0, px, py, r * 3.4);
  glow.addColorStop(0, 'rgba(160,200,255,0.5)');
  glow.addColorStop(1, 'rgba(160,200,255,0)');
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(px, py, r * 3.4, 0, Math.PI * 2); ctx.fill();
  // black puck, white ring so it reads on dark ice
  ctx.fillStyle = '#0b0d12';
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  ctx.lineWidth = 1.6; ctx.strokeStyle = 'rgba(240,244,250,0.9)';
  ctx.stroke();
}

/* ---------------- effects ---------------- */
function drawEffects(now) {
  for (let i = effects.length - 1; i >= 0; i--) {
    const e = effects[i];
    const age = (now - e.born) / 1000;
    if (age > e.life) { effects.splice(i, 1); continue; }
    const t = age / e.life, px = X(e.x), py = Y(e.y);
    if (e.kind === 'burst') {
      ctx.strokeStyle = 'rgba(255,200,80,' + ((1 - t) * 0.9).toFixed(3) + ')';
      ctx.lineWidth = 3 * (1 - t) + 1;
      ctx.beginPath(); ctx.arc(px, py, (4 + t * 30) * scale / 4, 0, Math.PI * 2); ctx.stroke();
      // sparks
      for (let s = 0; s < 8; s++) {
        const ang = (s / 8) * Math.PI * 2 + e.seed;
        const d = (6 + t * 34) * scale / 4;
        ctx.fillStyle = 'rgba(255,210,120,' + ((1 - t) * 0.85).toFixed(3) + ')';
        ctx.beginPath();
        ctx.arc(px + Math.cos(ang) * d, py + Math.sin(ang) * d, 2.2 * scale / 4, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (e.kind === 'goalring') {
      ctx.strokeStyle = 'rgba(255,215,0,' + (1 - t).toFixed(3) + ')';
      ctx.lineWidth = 5;
      ctx.beginPath(); ctx.arc(px, py, (6 + t * 70) * scale / 4, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,' + ((1 - t) * 0.8).toFixed(3) + ')';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(px, py, (3 + t * 44) * scale / 4, 0, Math.PI * 2); ctx.stroke();
    } else if (e.kind === 'saveflash') {
      ctx.strokeStyle = 'rgba(125,211,252,' + ((1 - t) * 0.9).toFixed(3) + ')';
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(px, py, (5 + t * 26) * scale / 4, 0, Math.PI * 2); ctx.stroke();
    }
  }
  if (now < flashUntil) {
    const a = ((flashUntil - now) / 650 * 0.2).toFixed(3);
    ctx.fillStyle = 'rgba(' + flashRGB + ',' + a + ')';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
}

/* ---------------- banners (center screen) ---------------- */
function queueBanner(text, sub, kind) {
  bannerQueue.push({ text, sub: sub || '', kind: kind || 'info', born: 0 });
}
function drawBanner(now) {
  if (!activeBanner) {
    const next = bannerQueue.shift();
    if (next) { next.born = now; activeBanner = next; }
    else return;
  }
  const b = activeBanner;
  const age = (now - b.born) / 1000;
  const HOLD = b.kind === 'goal' ? 3.2 : 2.2;
  if (age > HOLD + 0.45) { activeBanner = null; return; }

  // animate: scale in (0-0.25s), hold, fade out (last 0.45s)
  const inT = Math.min(1, age / 0.25);
  const outA = age > HOLD ? Math.max(0, 1 - (age - HOLD) / 0.45) : 1;
  const pop = 0.82 + 0.18 * (1 - Math.pow(1 - inT, 3));
  const alpha = Math.min(inT, outA);

  const isGoal = b.kind === 'goal';
  const fs = Math.round(canvas.width * (isGoal ? 0.075 : 0.048));
  ctx.save();
  ctx.globalAlpha = Math.max(0, alpha);
  ctx.translate(canvas.width / 2, canvas.height * 0.38);
  ctx.scale(pop, pop);
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';

  ctx.font = '900 ' + fs + 'px "Arial Narrow", Arial, sans-serif';
  const tw = ctx.measureText(b.text).width;
  const padX = fs * 0.9, bw = tw + padX * 2, bh = fs * 1.5;

  // backdrop bar
  ctx.fillStyle = 'rgba(4,7,14,0.88)';
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(-bw / 2, -bh / 2, bw, bh, 8); else ctx.rect(-bw / 2, -bh / 2, bw, bh);
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = isGoal ? '#ffd700' : b.kind === 'penalty' ? '#f59e0b' : '#3b82f6';
  ctx.stroke();

  ctx.fillStyle = isGoal ? '#ffd700' : '#ffffff';
  ctx.shadowColor = isGoal ? 'rgba(255,215,0,0.6)' : 'rgba(80,140,255,0.5)';
  ctx.shadowBlur = 18;
  ctx.fillText(b.text, 0, b.sub ? -fs * 0.22 : 0);
  ctx.shadowBlur = 0;
  if (b.sub) {
    ctx.font = '700 ' + Math.round(fs * 0.42) + 'px "Arial Narrow", Arial, sans-serif';
    ctx.fillStyle = '#dbe6fa';
    ctx.fillText(b.sub.slice(0, 72), 0, fs * 0.42);
  }
  ctx.restore();
}

/* ---------------- ticker ---------------- */
function tick(msg, cls) {
  const box = document.getElementById('event-ticker');
  const div = document.createElement('div');
  div.className = 'ticker-item' + (cls ? ' ' + cls : '');
  div.textContent = msg;
  box.prepend(div);
  while (box.children.length > 4) box.lastChild.remove();
  setTimeout(() => { if (div.parentNode) div.remove(); }, 7000);
}

/* ---------------- scorebug / status ---------------- */
function setScorebug(snap) {
  if (snap.home_abbr && snap.home_abbr !== homeAbbr && homeAbbr) {
    // abbr changed mid-stream; ignore (shouldn't happen)
  }
  if (snap.score) {
    document.getElementById('sb-home').textContent = snap.score.home;
    document.getElementById('sb-away').textContent = snap.score.away;
  }
  if (snap.period != null) {
    const p = document.getElementById('sb-period');
    p.textContent = snap.period > 3 ? 'OT' : 'P' + snap.period;
  }
  if (snap.clock) document.getElementById('sb-clock').textContent = snap.clock;
}
function applyTeamMeta(home, away, habbr, aabbr) {
  homeAbbr = habbr || ''; awayAbbr = aabbr || '';
  homeColor = teamColor(habbr, 0); awayColor = teamColor(aabbr, 1);
  const he = document.getElementById('sb-home-abbr');
  const ae = document.getElementById('sb-away-abbr');
  he.textContent = habbr || 'HOME'; ae.textContent = aabbr || 'AWAY';
  he.style.background = homeColor; he.style.color = readableText(homeColor);
  ae.style.background = awayColor; ae.style.color = readableText(awayColor);
  document.getElementById('ws-game').textContent =
    (away || 'Away') + ' at ' + (home || 'Home');
}

/* ---------------- frame ---------------- */
function lerp(a, b, t) { return a + (b - a) * t; }

function frame(now) {
  requestAnimationFrame(frame);
  drawRink();
  if (!paused && cur) {
    const span = Math.max(1, curT - prevT);
    const t = Math.min(1.15, Math.max(0, (now - prevT) / span));
    const tc = Math.min(1, t);
    const A = prev || cur, B = cur;
    if (B.type === 'skate') {
      const n = Math.min(A.skaters ? A.skaters.length : 0, B.skaters.length);
      for (let i = 0; i < n; i++) {
        const a = A.skaters[i], b = B.skaters[i];
        const x = lerp(a.x, b.x, tc), y = lerp(a.y, b.y, tc);
        const hasPuck = B.possession === b.team &&
          Math.hypot(B.puck.x - b.x, B.puck.y - b.y) < 4;
        drawSkater(x, y, b.team, {
          name: b.name, jersey: b.jersey, hasPuck: hasPuck, goalie: false,
        });
      }
      for (const gl of (B.goalies || [])) {
        drawSkater(gl.x, gl.y, gl.team, {
          name: gl.name, jersey: gl.jersey, hasPuck: false, goalie: true,
        });
      }
      drawPuck(lerp(A.puck.x, B.puck.x, tc), lerp(A.puck.y, B.puck.y, tc));
    }
  } else if (cur && cur.type === 'skate') {
    // paused: draw last frame statically (no trail growth)
    const B = cur;
    for (const s of B.skaters) drawSkater(s.x, s.y, s.team, { name: s.name, jersey: s.jersey });
    for (const gl of (B.goalies || [])) drawSkater(gl.x, gl.y, gl.team, { name: gl.name, jersey: gl.jersey, goalie: true });
    const px = X(B.puck.x), py = Y(B.puck.y), r = 4.2 * scale / 4;
    ctx.fillStyle = '#0b0d12';
    ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = 1.6; ctx.strokeStyle = 'rgba(240,244,250,0.9)'; ctx.stroke();
  }
  drawEffects(now);
  drawBanner(now);
}

/* ---------------- SSE ---------------- */
let es = null;
function connectStream() {
  if (es) es.close();
  es = new EventSource('/api/watch/stream?speed=' + speed);
  es.onmessage = handleMessage;
  es.onerror = () => tick('Stream interrupted — reconnecting…');
}

function handleMessage(e) {
  let msg;
  try { msg = JSON.parse(e.data); } catch (err) { return; }
  const now = performance.now();

  if (msg.type === 'meta') {
    applyTeamMeta(msg.home, msg.away, msg.home_abbr, msg.away_abbr);
    tick(msg.away + ' at ' + msg.home);
    queueBanner('FACEOFF', msg.away + ' at ' + msg.home, 'info');
    return;
  }
  if (msg.type === 'highlight') {
    setScorebug(msg);
    const k = msg.kind;
    if (k === 'goal') {
      const gx = msg.team === 0 ? 189 : 11;
      effects.push({ kind: 'goalring', x: gx, y: 42.5, born: now, life: 1.5, seed: Math.random() * 6 });
      flashUntil = now + 650; flashRGB = '255,215,0';
      // split "GOAL! Name (TEAM)" into banner + sub
      const m = /^GOAL!\s*(.*?)\s*(\(.*\))?$/.exec(msg.text || '');
      queueBanner('GOAL!', m ? m[1] : '', 'goal');
      tick(msg.text, 'goal');
    } else if (k === 'save' || k === 'big_save') {
      if (cur && cur.puck) effects.push({ kind: 'saveflash', x: cur.puck.x, y: cur.puck.y, born: now, life: 0.8, seed: 0 });
      queueBanner('SAVE', msg.text, 'info');
      tick(msg.text);
    } else if (k === 'hit') {
      if (cur && cur.puck) effects.push({ kind: 'burst', x: cur.puck.x, y: cur.puck.y, born: now, life: 0.7, seed: Math.random() * 6 });
      tick(msg.text);
    } else if (k === 'fight') {
      if (cur && cur.puck) effects.push({ kind: 'burst', x: cur.puck.x, y: cur.puck.y, born: now, life: 1.0, seed: Math.random() * 6 });
      queueBanner('FIGHT!', '', 'penalty');
      tick(msg.text, 'penalty');
    } else if (k === 'penalty') {
      queueBanner('PENALTY', msg.text, 'penalty');
      tick(msg.text, 'penalty');
    } else if (k === 'period_start') {
      queueBanner(msg.text.toUpperCase(), '', 'info');
      tick(msg.text);
    } else if (k === 'period_end') {
      queueBanner('END OF PERIOD', msg.text, 'info');
      tick(msg.text);
    } else if (k === 'game_start') {
      queueBanner('GAME ON', '', 'info');
    } else {
      tick(msg.text);
    }
    return;
  }
  if (msg.type === 'game_end') {
    setScorebug(msg);
    queueBanner('FINAL', (msg.away_abbr || '') + ' ' + msg.score.away + ' — ' +
      (msg.home_abbr || '') + ' ' + msg.score.home, 'goal');
    tick('Final: ' + msg.score.away + '–' + msg.score.home, 'goal');
    const live = document.getElementById('ws-live');
    live.innerHTML = '<span class="ws-dot"></span>FINAL';
    live.classList.add('final');
    if (es) es.close();
    return;
  }
  if (msg.type === 'skate') {
    prev = cur; prevT = curT;
    cur = msg; curT = performance.now();
    setScorebug(msg);
  }
}

/* ---------------- controls ---------------- */
const btnPause = document.getElementById('btn-pause');
const btnSpeed = document.getElementById('btn-speed');
function setPaused(p) {
  paused = p;
  btnPause.textContent = paused ? '▶' : '⏸';
  btnPause.classList.toggle('active', paused);
}
btnPause.addEventListener('click', () => setPaused(!paused));
btnSpeed.addEventListener('click', () => {
  speed = speed === 1 ? 2 : speed === 2 ? 4 : 1;
  btnSpeed.textContent = speed + '×';
  connectStream();
});
document.addEventListener('keydown', e => {
  if (e.code === 'Space' && e.target === document.body) {
    e.preventDefault();
    setPaused(!paused);
  }
});
// click a skater to follow (name tag + ring); click ice to clear
canvas.addEventListener('click', e => {
  if (!cur || !cur.skaters) return;
  const rect = canvas.getBoundingClientRect();
  const mx = (e.clientX - rect.left) * dpr, my = (e.clientY - rect.top) * dpr;
  let best = null, bestD = 30 * dpr;
  const all = cur.skaters.concat(cur.goalies || []);
  for (const s of all) {
    const d = Math.hypot(X(s.x) - mx, Y(s.y) - my);
    if (d < bestD) { bestD = d; best = s; }
  }
  followName = best && best.name ? best.name : null;
  if (followName) tick('Following ' + followName);
});

resize();
connectStream();
requestAnimationFrame(frame);

// Shared heartbeat: tells the game the tab is still open (every 30s).
(function () {
  const beat = () => fetch('/api/heartbeat', { method: 'POST' }).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

})();
