/* Puck Dynasty web visualizer — MODERN BROADCAST renderer.
 *
 * NHL 2024/25 broadcast look: smooth follow-cam tracking the puck,
 * directional skater indicators, shot markers, stats overlay, hover labels,
 * goal zoom punch-ins, enhanced ice art.
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

/* NHL primary colors by abbreviation. */
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
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.62 ? '#101418' : '#ffffff';
}
function hexA(hex, a) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return 'rgba(' + r + ',' + g + ',' + b + ',' + a.toFixed(3) + ')';
}

/* ---------------- state ---------------- */
let cur = null, prev = null, prevT = 0, curT = 0;
let paused = false, speed = 1;
let homeAbbr = '', awayAbbr = '';
let homeColor = FALLBACK[0], awayColor = FALLBACK[1];
let followName = null, hoverName = null;

const puckTrail = [];
const skaterTrails = new Map();   // key -> [{x,y}]
const skaterVel = new Map();      // key -> {dx,dy} smoothed velocity (rink ft/frame)
const effects = [];               // {kind,x,y,born,life,seed}
const shotMarkers = [];           // {x,y,team,born} — goal/save locations
const bannerQueue = [];
let activeBanner = null;
let flashUntil = 0, flashRGB = '255,215,0';

// client-tracked game stats (from highlight events)
const stats = {
  goals: [0, 0], hits: [0, 0], penalties: [0, 0], fights: 0,
};

/* ---------------- broadcast camera ---------------- */
const cam = { cx: 100, cy: 42.5, zoom: 1 };       // current (eased)
const camTarget = { cx: 100, cy: 42.5, zoom: 1 }; // desired
let camMode = 'follow';                            // 'follow' | 'full'
let punchUntil = 0, punchZoom = 1, punchX = 100, punchY = 42.5;

function updateCamera(now, dt) {
  // desired target
  if (punchUntil > now) {
    camTarget.cx = punchX; camTarget.cy = punchY; camTarget.zoom = punchZoom;
  } else if (camMode === 'follow' && cur && cur.type === 'skate') {
    camTarget.cx = renderPuck.x; camTarget.cy = renderPuck.y; camTarget.zoom = 1.55;
  } else {
    camTarget.cx = 100; camTarget.cy = 42.5; camTarget.zoom = 1;
  }
  // ease toward target (frame-rate independent)
  const k = Math.min(1, dt * 3.2);
  cam.cx += (camTarget.cx - cam.cx) * k;
  cam.cy += (camTarget.cy - cam.cy) * k;
  cam.zoom += (camTarget.zoom - cam.zoom) * Math.min(1, dt * 2.6);
  // keep camera inside rink bounds (with zoom-aware margin)
  const hw = (RL / 2) / cam.zoom, hh = (RW / 2) / cam.zoom;
  cam.cx = Math.max(100 - hw + 8, Math.min(100 + hw - 8, cam.cx));
  cam.cy = Math.max(42.5 - hh + 6, Math.min(42.5 + hh - 6, cam.cy));
}

// base mapping: rink coords -> device px at zoom=1, no camera offset
const X = x => ox + x * scale;
const Y = y => oy + y * scale;
// camera transform: apply before drawing world
function applyCamera() {
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.scale(cam.zoom, cam.zoom);
  ctx.translate(-X(cam.cx), -Y(cam.cy));
}
// screen (device px) -> rink coords (for hit testing)
function rinkFromScreen(sx, sy) {
  const bx = (sx - canvas.width / 2) / cam.zoom + X(cam.cx);
  const by = (sy - canvas.height / 2) / cam.zoom + Y(cam.cy);
  return { x: (bx - ox) / scale, y: (by - oy) / scale };
}
// rink coords -> screen device px (for DOM overlays)
function screenFromRink(x, y) {
  const bx = X(x), by = Y(y);
  return {
    x: canvas.width / 2 + (bx - X(cam.cx)) * cam.zoom,
    y: canvas.height / 2 + (by - Y(cam.cy)) * cam.zoom,
  };
}

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

/* ---------------- enhanced rink art (cached) ---------------- */
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

  // arena surround: near-black navy with vignette
  const vg = c.createRadialGradient(W / 2, H / 2, H * 0.2, W / 2, H / 2, Math.max(W, H) * 0.75);
  vg.addColorStop(0, '#0a101d');
  vg.addColorStop(1, '#030509');
  c.fillStyle = vg;
  c.fillRect(0, 0, W, H);

  // ice: bright white like real NHL ice, subtle cool tint at edges
  const g = c.createRadialGradient(W / 2, H / 2, 10, W / 2, H / 2, Math.max(W, H) * 0.7);
  g.addColorStop(0, '#ffffff');
  g.addColorStop(0.6, '#f4f8fc');
  g.addColorStop(1, '#dfe9f2');
  c.fillStyle = g;
  R(Xc(-2), Yc(-2), (RL + 4) * scale, (RW + 4) * scale, 20 * scale); c.fill();

  // ice sheen: diagonal light streaks (arena lighting reflections)
  const sheen = c.createLinearGradient(0, 0, W, H);
  sheen.addColorStop(0, 'rgba(255,255,255,0.25)');
  sheen.addColorStop(0.4, 'rgba(255,255,255,0)');
  sheen.addColorStop(0.6, 'rgba(180,210,240,0.08)');
  sheen.addColorStop(1, 'rgba(255,255,255,0.12)');
  c.fillStyle = sheen;
  R(Xc(-2), Yc(-2), (RL + 4) * scale, (RW + 4) * scale, 20 * scale); c.fill();

  // skate scratches: subtle gray marks like real worn ice
  c.lineWidth = 1;
  for (let i = 0; i < 90; i++) {
    const y0 = Yc(3 + ((i * 37) % 79));
    const x0 = Xc(4 + ((i * 53) % 192));
    const len = (8 + ((i * 29) % 22)) * scale / 4;
    c.strokeStyle = 'rgba(120,140,170,' + (0.05 + ((i * 13) % 5) * 0.02).toFixed(3) + ')';
    c.beginPath(); c.moveTo(x0, y0);
    c.lineTo(x0 + len, y0 + len * 0.25); c.stroke();
  }

  const lw = Math.max(1.5, scale * 0.55);
  const RED = '#d42a1e', BLUE = '#1a56db';

  // boards: dark steel with glass reflection hint on top edge
  // boards: white with yellow kickplate (NHL style)
  c.lineWidth = Math.max(6, scale * 1.6);
  c.strokeStyle = '#f8fafc';
  R(Xc(0), Yc(0), RL * scale, RW * scale, 18 * scale); c.stroke();
  // yellow kickplate stripe at bottom of boards
  c.lineWidth = Math.max(2, scale * 0.5);
  c.strokeStyle = '#facc15';
  R(Xc(0), Yc(0), RL * scale, RW * scale, 18 * scale); c.stroke();
  // glass above boards
  c.lineWidth = Math.max(1.5, scale * 0.28);
  const glass = c.createLinearGradient(Xc(0), Yc(-2), Xc(0), Yc(6));
  glass.addColorStop(0, 'rgba(180,210,240,0.35)');
  glass.addColorStop(1, 'rgba(180,210,240,0.05)');
  c.strokeStyle = glass;
  R(Xc(0), Yc(0), RL * scale, RW * scale, 18 * scale); c.stroke();

  // center red line: solid NHL red
  c.strokeStyle = RED; c.lineWidth = lw * 1.2;
  c.beginPath(); c.moveTo(Xc(100), Yc(2)); c.lineTo(Xc(100), Yc(83)); c.stroke();

  // blue lines: solid NHL blue
  c.strokeStyle = BLUE; c.lineWidth = lw * 2.6;
  for (const bx of [75, 125]) {
    c.beginPath(); c.moveTo(Xc(bx), Yc(2)); c.lineTo(Xc(bx), Yc(83)); c.stroke();
  }

  // goal lines
  c.strokeStyle = RED; c.lineWidth = lw * 0.9;
  for (const gx of [11, 189]) {
    c.beginPath(); c.moveTo(Xc(gx), Yc(4)); c.lineTo(Xc(gx), Yc(81)); c.stroke();
  }

  // center-ice: double ring + dot (broadcast style)
  c.strokeStyle = 'rgba(77,159,255,0.85)'; c.lineWidth = lw;
  // center-ice faceoff circle: solid NHL blue ring + dot
  c.strokeStyle = BLUE; c.lineWidth = lw;
  c.beginPath(); c.arc(Xc(100), Yc(42.5), 7.5 * scale, 0, Math.PI * 2); c.stroke();
  c.fillStyle = BLUE;
  c.beginPath(); c.arc(Xc(100), Yc(42.5), 0.5 * scale, 0, Math.PI * 2); c.fill();

  // end-zone faceoff circles with proper hash marks
  for (const gx of [11, 189]) {
    const sgn = gx < 100 ? 1 : -1;
    for (const dy of [20.5, 64.5]) {
      const ex = Xc(gx + 20 * sgn), ey = Yc(dy);
      // outer ring: solid NHL red
      c.strokeStyle = RED; c.lineWidth = lw * 0.9;
      c.beginPath(); c.arc(ex, ey, 7.5 * scale, 0, Math.PI * 2); c.stroke();
      // center dot: solid red
      c.fillStyle = RED;
      c.beginPath(); c.arc(ex, ey, 1.0 * scale, 0, Math.PI * 2); c.fill();
      // hash marks: solid red, 2 ft long
      c.strokeStyle = RED; c.lineWidth = lw * 0.75;
      const hr = 7.5 * scale, hl = 1.0 * scale;
      for (const a of [Math.PI * 0.32, Math.PI * 0.68, Math.PI * 1.32, Math.PI * 1.68]) {
        const hx = ex + Math.cos(a) * hr, hy = ey + Math.sin(a) * hr;
        const tx = Math.cos(a + Math.PI / 2), ty = Math.sin(a + Math.PI / 2);
        c.beginPath();
        c.moveTo(hx - tx * hl, hy - ty * hl);
        c.lineTo(hx + tx * hl, hy + ty * hl);
        c.stroke();
      }
    }
  }
  // neutral-zone dots: solid red
  c.fillStyle = RED;
  for (const [dx, dy] of [[80, 20.5], [80, 64.5], [120, 20.5], [120, 64.5]]) {
    c.beginPath(); c.arc(Xc(dx), Yc(dy), 1.0 * scale, 0, Math.PI * 2); c.fill();
  }

  // creases: NHL light blue with red edge
  for (const gx of [11, 189]) {
    const dir = gx < 100 ? 1 : -1;
    const a0 = dir > 0 ? -Math.PI / 2 : Math.PI / 2;
    const a1 = dir > 0 ? Math.PI / 2 : Math.PI * 1.5;
    c.fillStyle = '#bfe0f5';
    c.beginPath(); c.arc(Xc(gx), Yc(42.5), 6 * scale, a0, a1); c.closePath(); c.fill();
    c.strokeStyle = RED; c.lineWidth = lw * 0.7;
    c.beginPath(); c.arc(Xc(gx), Yc(42.5), 6 * scale, a0, a1); c.stroke();

    // net: white frame + mesh hint
    c.strokeStyle = 'rgba(200,215,235,0.25)'; c.lineWidth = 1;
    for (let ny = 39; ny <= 46; ny += 1.4) {
      c.beginPath();
      c.moveTo(Xc(gx), Yc(ny)); c.lineTo(Xc(gx + dir * 3.2), Yc(ny));
      c.stroke();
    }
    c.strokeStyle = '#eef3fb'; c.lineWidth = Math.max(2.2, lw);
    c.beginPath();
    c.moveTo(Xc(gx), Yc(38.5)); c.lineTo(Xc(gx + dir * 3.2), Yc(38.5));
    c.lineTo(Xc(gx + dir * 3.2), Yc(46.5)); c.lineTo(Xc(gx), Yc(46.5));
    c.stroke();
    // red goal line accent on posts
    c.strokeStyle = RED; c.lineWidth = Math.max(1.5, lw * 0.7);
    c.beginPath();
    c.moveTo(Xc(gx), Yc(38.5)); c.lineTo(Xc(gx), Yc(46.5));
    c.stroke();
  }

  // trapezoid
  c.strokeStyle = 'rgba(240,67,58,0.4)'; c.lineWidth = lw * 0.7;
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

function skaterKey(team, name, x, y) {
  return team + '|' + (name || Math.round(x) + ',' + Math.round(y));
}

function drawSkater(x, y, team, opts) {
  opts = opts || {};
  const px = X(x), py = Y(y);
  const r = (opts.goalie ? 16 : 13.5) * scale / 4;
  const col = skaterColor(team);
  const key = opts.key || skaterKey(team, opts.name, x, y);

  // --- velocity tracking for facing indicator ---
  let vel = skaterVel.get(key);
  if (!vel) { vel = { dx: 0, dy: 0 }; skaterVel.set(key, vel); }
  // previous drawn position stored on the trail head
  let tr = skaterTrails.get(key);
  if (!tr) { tr = []; skaterTrails.set(key, tr); }
  const lastPt = tr.length ? tr[tr.length - 1] : null;
  if (lastPt) {
    const idx = 1 / Math.max(1, scale); // normalize-ish
    vel.dx = vel.dx * 0.82 + (px - lastPt.x) * 0.18;
    vel.dy = vel.dy * 0.82 + (py - lastPt.y) * 0.18;
  }
  tr.push({ x: px, y: py });
  if (tr.length > 8) tr.shift();

  const spd = Math.hypot(vel.dx, vel.dy);
  const moving = spd > 0.6;

  // motion trail (longer when fast)
  const trailLen = tr.length;
  for (let i = 0; i < trailLen; i++) {
    const f = i / trailLen;
    const a = f * (moving ? 0.30 : 0.16);
    ctx.fillStyle = hexA(col, a);
    ctx.beginPath();
    ctx.arc(tr[i].x, tr[i].y, r * (0.3 + 0.7 * f), 0, Math.PI * 2);
    ctx.fill();
  }

  // drop shadow
  ctx.fillStyle = 'rgba(0,0,0,0.45)';
  ctx.beginPath(); ctx.arc(px + r * 0.22, py + r * 0.3, r, 0, Math.PI * 2); ctx.fill();

  // body with subtle vertical shading
  const bodyG = ctx.createRadialGradient(px - r * 0.3, py - r * 0.35, r * 0.1, px, py, r);
  bodyG.addColorStop(0, hexA(col, 1));
  bodyG.addColorStop(1, shade(col, -28));
  ctx.fillStyle = bodyG;
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  // dark outline for visibility on white ice, then thin white inner ring
  ctx.lineWidth = Math.max(2.5, r * 0.28);
  ctx.strokeStyle = 'rgba(15,23,42,0.85)';
  ctx.stroke();
  ctx.lineWidth = Math.max(1, r * 0.1);
  ctx.strokeStyle = 'rgba(255,255,255,0.9)';
  ctx.stroke();

  // facing indicator: small wedge in movement direction
  if (moving && !opts.goalie) {
    const ang = Math.atan2(vel.dy, vel.dx);
    const wr = r * 0.52;
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(ang);
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.beginPath();
    ctx.moveTo(r + wr * 0.9, 0);
    ctx.lineTo(r - wr * 0.2, -wr * 0.55);
    ctx.lineTo(r - wr * 0.2, wr * 0.55);
    ctx.closePath(); ctx.fill();
    ctx.restore();
  }

  // jersey number
  const num = opts.jersey != null && opts.jersey !== '' ? String(opts.jersey) : '';
  ctx.fillStyle = readableText(col);
  ctx.font = '800 ' + Math.round(r * 1.02) + 'px "Arial Narrow", Arial, sans-serif';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  if (num) {
    ctx.fillText(num.length > 2 ? num.slice(0, 2) : num, px, py + r * 0.06);
  } else if (opts.goalie) {
    ctx.fillText('G', px, py + r * 0.06);
  }

  // puck-carrier ring
  if (opts.hasPuck) {
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.arc(px, py, r + 5, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,215,0,0.85)'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(px, py, r + 8, 0, Math.PI * 2); ctx.stroke();
    drawNameTag(px, py - r - 14, opts.name, col);
  }
  // followed / hovered player
  const tagged = (followName && opts.name === followName) ||
                 (hoverName && opts.name === hoverName && opts.name !== followName);
  if (tagged) {
    const isFollow = followName && opts.name === followName;
    ctx.strokeStyle = isFollow ? '#7dd3fc' : 'rgba(255,255,255,0.65)';
    ctx.lineWidth = 2;
    if (isFollow) ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.arc(px, py, r + 11, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    drawNameTag(px, py - r - 14, opts.name, col);
  }
}

function shade(hex, amt) {
  const h = hex.replace('#', '');
  let r = parseInt(h.slice(0, 2), 16) + amt;
  let g = parseInt(h.slice(2, 4), 16) + amt;
  let b = parseInt(h.slice(4, 6), 16) + amt;
  r = Math.max(0, Math.min(255, r)); g = Math.max(0, Math.min(255, g)); b = Math.max(0, Math.min(255, b));
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
}

function drawNameTag(px, py, name, teamCol) {
  if (!name) return;
  ctx.font = '700 12px "Arial Narrow", Arial, sans-serif';
  const w = ctx.measureText(name).width + 16;
  const bx = px - w / 2, by = py - 10;
  ctx.fillStyle = 'rgba(4,7,14,0.92)';
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(bx, by, w, 20, 4); else ctx.rect(bx, by, w, 20);
  ctx.fill();
  if (teamCol) {
    ctx.fillStyle = teamCol;
    ctx.fillRect(bx, by, 3, 20);
  }
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(name, px + 1.5, by + 10);
}

/* ---------------- puck ---------------- */
let puckSpeedSm = 0;
function drawPuck(x, y) {
  const px = X(x), py = Y(y);
  const last = puckTrail.length ? puckTrail[puckTrail.length - 1] : null;
  const inst = last ? Math.hypot(px - last.x, py - last.y) : 0;
  puckSpeedSm = puckSpeedSm * 0.85 + inst * 0.15;

  puckTrail.push({ x: px, y: py });
  const maxTrail = 8 + Math.min(10, Math.round(puckSpeedSm * 1.2));
  while (puckTrail.length > maxTrail) puckTrail.shift();
  for (let i = 0; i < puckTrail.length; i++) {
    const t = puckTrail[i], f = i / puckTrail.length;
    const a = f * (0.18 + Math.min(0.25, puckSpeedSm * 0.02));
    ctx.fillStyle = 'rgba(180,200,235,' + a.toFixed(3) + ')';
    ctx.beginPath();
    ctx.arc(t.x, t.y, (1 + f * 2.6) * scale / 4, 0, Math.PI * 2);
    ctx.fill();
  }
  const r = 4.4 * scale / 4;
  // glow scales with speed
  const glowR = r * (3.2 + Math.min(2.5, puckSpeedSm * 0.25));
  const glow = ctx.createRadialGradient(px, py, 0, px, py, glowR);
  glow.addColorStop(0, 'rgba(170,210,255,0.55)');
  glow.addColorStop(1, 'rgba(170,210,255,0)');
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(px, py, glowR, 0, Math.PI * 2); ctx.fill();
  // puck with highlight
  ctx.fillStyle = '#0b0d12';
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  ctx.lineWidth = 1.6; ctx.strokeStyle = 'rgba(240,244,250,0.9)';
  ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.35)';
  ctx.beginPath(); ctx.arc(px - r * 0.3, py - r * 0.3, r * 0.28, 0, Math.PI * 2); ctx.fill();
}

/* ---------------- shot markers ---------------- */
function drawShotMarkers(now) {
  for (let i = shotMarkers.length - 1; i >= 0; i--) {
    const m = shotMarkers[i];
    const age = (now - m.born) / 1000;
    if (age > 25) { shotMarkers.splice(i, 1); continue; }
    const fade = age < 20 ? 1 : 1 - (age - 20) / 5;
    const px = X(m.x), py = Y(m.y);
    const col = m.team === 0 ? homeColor : awayColor;
    ctx.save();
    ctx.globalAlpha = fade * 0.9;
    ctx.strokeStyle = m.scored ? '#ffd700' : col;
    ctx.lineWidth = 2.5;
    const s = 7 * scale / 4;
    if (m.scored) {
      // star burst for goals
      ctx.beginPath();
      for (let k = 0; k < 8; k++) {
        const a = k * Math.PI / 4;
        const rr = k % 2 ? s * 0.45 : s;
        ctx.lineTo(px + Math.cos(a) * rr, py + Math.sin(a) * rr);
      }
      ctx.closePath(); ctx.stroke();
    } else {
      // X for saves
      ctx.beginPath();
      ctx.moveTo(px - s * 0.6, py - s * 0.6); ctx.lineTo(px + s * 0.6, py + s * 0.6);
      ctx.moveTo(px + s * 0.6, py - s * 0.6); ctx.lineTo(px - s * 0.6, py + s * 0.6);
      ctx.stroke();
    }
    ctx.restore();
  }
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
      for (let s = 0; s < 10; s++) {
        const ang = (s / 10) * Math.PI * 2 + e.seed;
        const d = (6 + t * 38) * scale / 4;
        ctx.fillStyle = 'rgba(255,210,120,' + ((1 - t) * 0.85).toFixed(3) + ')';
        ctx.beginPath();
        ctx.arc(px + Math.cos(ang) * d, py + Math.sin(ang) * d, 2.2 * scale / 4, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (e.kind === 'goalring') {
      const w1 = (1 - t);
      ctx.strokeStyle = 'rgba(255,215,0,' + w1.toFixed(3) + ')';
      ctx.lineWidth = 5;
      ctx.beginPath(); ctx.arc(px, py, (6 + t * 80) * scale / 4, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,' + (w1 * 0.8).toFixed(3) + ')';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(px, py, (3 + t * 50) * scale / 4, 0, Math.PI * 2); ctx.stroke();
    } else if (e.kind === 'saveflash') {
      ctx.strokeStyle = 'rgba(125,211,252,' + ((1 - t) * 0.9).toFixed(3) + ')';
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(px, py, (5 + t * 26) * scale / 4, 0, Math.PI * 2); ctx.stroke();
    }
  }
  if (now < flashUntil) {
    const a = ((flashUntil - now) / 650 * 0.22).toFixed(3);
    ctx.fillStyle = 'rgba(' + flashRGB + ',' + a + ')';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
}

/* ---------------- banners ---------------- */
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
  const HOLD = b.kind === 'goal' ? 3.4 : 2.2;
  if (age > HOLD + 0.45) { activeBanner = null; return; }

  // slide down + scale in, hold, fade out
  const inT = Math.min(1, age / 0.3);
  const outA = age > HOLD ? Math.max(0, 1 - (age - HOLD) / 0.45) : 1;
  const ease = 1 - Math.pow(1 - inT, 3);
  const slideY = (1 - ease) * -70;
  const pop = 0.85 + 0.15 * ease;
  const alpha = Math.min(inT, outA);

  const isGoal = b.kind === 'goal';
  const fs = Math.round(canvas.width * (isGoal ? 0.072 : 0.046));
  ctx.save();
  ctx.globalAlpha = Math.max(0, alpha);
  ctx.translate(canvas.width / 2, canvas.height * 0.34 + slideY);
  ctx.scale(pop, pop);
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';

  ctx.font = '900 ' + fs + 'px "Arial Narrow", Arial, sans-serif';
  const tw = ctx.measureText(b.text).width;
  const padX = fs * 0.9, bw = tw + padX * 2, bh = fs * 1.5;

  // backdrop with accent edge
  ctx.fillStyle = 'rgba(4,7,14,0.9)';
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(-bw / 2, -bh / 2, bw, bh, 10); else ctx.rect(-bw / 2, -bh / 2, bw, bh);
  ctx.fill();
  const accent = isGoal ? '#ffd700' : b.kind === 'penalty' ? '#f59e0b' : '#3b82f6';
  ctx.lineWidth = 3;
  ctx.strokeStyle = accent;
  ctx.stroke();
  // top accent bar
  ctx.fillStyle = accent;
  ctx.fillRect(-bw / 2 + 10, -bh / 2, bw - 20, 3);

  ctx.fillStyle = isGoal ? '#ffd700' : '#ffffff';
  ctx.shadowColor = isGoal ? 'rgba(255,215,0,0.65)' : 'rgba(80,140,255,0.5)';
  ctx.shadowBlur = 20;
  ctx.fillText(b.text, 0, b.sub ? -fs * 0.22 : 0);
  ctx.shadowBlur = 0;
  if (b.sub) {
    ctx.font = '700 ' + Math.round(fs * 0.4) + 'px "Arial Narrow", Arial, sans-serif';
    ctx.fillStyle = '#dbe6fa';
    ctx.fillText(b.sub.slice(0, 76), 0, fs * 0.42);
  }
  ctx.restore();
}

/* ---------------- ticker ---------------- */
function tick(msg, cls) {
  const box = document.getElementById('event-ticker');
  if (!box) return;
  const div = document.createElement('div');
  div.className = 'ticker-item' + (cls ? ' ' + cls : '');
  div.textContent = msg;
  box.prepend(div);
  while (box.children.length > 4) box.lastChild.remove();
  setTimeout(() => { if (div.parentNode) div.remove(); }, 8000);
}

/* ---------------- scorebug / status ---------------- */
function setScorebug(snap) {
  if (snap.score) {
    document.getElementById('sb-home').textContent = snap.score.home;
    document.getElementById('sb-away').textContent = snap.score.away;
    stats.goals = [snap.score.home, snap.score.away];
    renderStatsOverlay();
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
  // team color edge on scorebug
  document.getElementById('scorebug').style.setProperty('--home-col', homeColor);
  document.getElementById('scorebug').style.setProperty('--away-col', awayColor);
  document.getElementById('ws-game').textContent =
    (away || 'Away') + ' at ' + (home || 'Home');
  renderStatsOverlay();
}

/* ---------------- stats overlay ---------------- */
let statsVisible = false;
function renderStatsOverlay() {
  const ov = document.getElementById('stats-overlay');
  if (!ov) return;
  ov.classList.toggle('hidden', !statsVisible);
  if (!statsVisible) return;
  const row = (label, h, a) =>
    '<div class="st-row"><span class="st-label">' + label + '</span>' +
    '<span class="st-val">' + h + '</span><span class="st-val">' + a + '</span></div>';
  ov.innerHTML =
    '<div class="st-head"><span></span><span>' + esc(homeAbbr || 'HOME') + '</span><span>' + esc(awayAbbr || 'AWAY') + '</span></div>' +
    row('Goals', stats.goals[0], stats.goals[1]) +
    row('Hits', stats.hits[0], stats.hits[1]) +
    row('Penalties', stats.penalties[0], stats.penalties[1]) +
    row('Fights', stats.fights, '—');
}
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* ---------------- frame ---------------- */
function lerp(a, b, t) { return a + (b - a) * t; }
/* Smoothstep for natural easing (no linear hitch at endpoints). */
function smooth(t) { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); }
let lastFrameT = 0;

/* ---- Persistent render state with spring physics ----
 * Each skater/puck has a render position that springs toward the latest
 * server target. This gives buttery motion even with irregular updates:
 * no index-matching, no teleporting, no linear-easing hitches. */
const renderSkaters = new Map(); // key -> {x,y,vx,vy,tx,ty,team,name,jersey,goalie}
const renderPuck = { x: 100, y: 42.5, vx: 0, vy: 0, tx: 100, ty: 42.5 };

function skaterRenderKey(team, name, goalie) {
  return (goalie ? 'G|' : 'S|') + team + '|' + (name || '?');
}

/* Spring constants: stiff enough to track, loose enough to look like skating. */
const SPRING_K = 90;   // spring stiffness (1/s^2)
const SPRING_D = 14;   // damping (1/s) — critically damped-ish for no overshoot

function springStep(s, dt) {
  // Semi-implicit Euler: stable and smooth.
  const ax = SPRING_K * (s.tx - s.x) - SPRING_D * s.vx;
  const ay = SPRING_K * (s.ty - s.y) - SPRING_D * s.vy;
  s.vx += ax * dt;
  s.vy += ay * dt;
  s.x += s.vx * dt;
  s.y += s.vy * dt;
}

function updateRenderTargets(msg) {
  if (!msg || msg.type !== 'skate') return;
  const seen = new Set();
  for (const sk of (msg.skaters || [])) {
    const key = skaterRenderKey(sk.team, sk.name, false);
    seen.add(key);
    let r = renderSkaters.get(key);
    if (!r) {
      r = { x: sk.x, y: sk.y, vx: 0, vy: 0, tx: sk.x, ty: sk.y,
            team: sk.team, name: sk.name, jersey: sk.jersey, goalie: false };
      renderSkaters.set(key, r);
    }
    r.tx = sk.x; r.ty = sk.y;
    r.team = sk.team; r.name = sk.name; r.jersey = sk.jersey;
  }
  for (const gl of (msg.goalies || [])) {
    const key = skaterRenderKey(gl.team, gl.name, true);
    seen.add(key);
    let r = renderSkaters.get(key);
    if (!r) {
      r = { x: gl.x, y: gl.y, vx: 0, vy: 0, tx: gl.x, ty: gl.y,
            team: gl.team, name: gl.name, jersey: gl.jersey, goalie: true };
      renderSkaters.set(key, r);
    }
    r.tx = gl.x; r.ty = gl.y;
  }
  // Remove skaters who left the ice (line change) — fade them out.
  for (const key of renderSkaters.keys()) {
    if (!seen.has(key)) renderSkaters.delete(key);
  }
  if (msg.puck) { renderPuck.tx = msg.puck.x; renderPuck.ty = msg.puck.y; }
}

function drawWorld(now, dt) {
  if (!cur || cur.type !== 'skate') return;
  // Spring every render entity toward its target.
  for (const r of renderSkaters.values()) springStep(r, dt);
  springStep(renderPuck, dt);

  const puckX = renderPuck.x, puckY = renderPuck.y;
  for (const r of renderSkaters.values()) {
    const hasPuck = !r.goalie && cur.possession === r.team &&
      Math.hypot(puckX - r.x, puckY - r.y) < 4;
    drawSkater(r.x, r.y, r.team, {
      name: r.name, jersey: r.jersey, hasPuck: hasPuck, goalie: r.goalie,
      key: skaterRenderKey(r.team, r.name, r.goalie),
    });
  }
  drawPuck(puckX, puckY);
}

function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.1, (now - lastFrameT) / 1000 || 0.016);
  lastFrameT = now;

  updateCamera(now, paused ? 0 : dt);

  ctx.save();
  applyCamera();
  drawRink();
  drawShotMarkers(now);
  if (!paused && cur) {
    drawWorld(now, dt);
  } else if (cur && cur.type === 'skate') {
    // paused: static frame (no trail growth)
    const B = cur;
    for (const s of B.skaters)
      drawSkater(s.x, s.y, s.team, { name: s.name, jersey: s.jersey, key: s.team + '|' + (s.name || '') });
    for (const gl of (B.goalies || []))
      drawSkater(gl.x, gl.y, gl.team, { name: gl.name, jersey: gl.jersey, goalie: true, key: gl.team + '|G|' + (gl.name || '') });
    const px = X(B.puck.x), py = Y(B.puck.y), r = 4.4 * scale / 4;
    ctx.fillStyle = '#0b0d12';
    ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = 1.6; ctx.strokeStyle = 'rgba(240,244,250,0.9)'; ctx.stroke();
  }
  drawEffects(now);
  ctx.restore(); // back to screen space

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

function goalPunch(teamIdx, now) {
  // camera punch-in on the net that was scored on
  punchX = teamIdx === 0 ? 189 : 11;
  punchY = 42.5;
  punchZoom = 2.4;
  punchUntil = now + 1600;
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
    const px = cur && cur.puck ? cur.puck.x : 100;
    const py = cur && cur.puck ? cur.puck.y : 42.5;
    if (k === 'goal') {
      const gx = msg.team === 0 ? 189 : 11;
      effects.push({ kind: 'goalring', x: gx, y: 42.5, born: now, life: 1.6, seed: Math.random() * 6 });
      shotMarkers.push({ x: px, y: py, team: msg.team, scored: true, born: now });
      flashUntil = now + 650; flashRGB = '255,215,0';
      goalPunch(msg.team, now);
      const m = /^GOAL!\s*(.*?)\s*(\(.*\))?$/.exec(msg.text || '');
      queueBanner('GOAL!', m ? m[1] : '', 'goal');
      tick(msg.text, 'goal');
    } else if (k === 'save' || k === 'big_save') {
      effects.push({ kind: 'saveflash', x: px, y: py, born: now, life: 0.8, seed: 0 });
      shotMarkers.push({ x: px, y: py, team: msg.team, scored: false, born: now });
      queueBanner(k === 'big_save' ? 'BIG SAVE' : 'SAVE', msg.text, 'info');
      tick(msg.text);
    } else if (k === 'hit') {
      stats.hits[msg.team === 0 ? 0 : 1]++;
      effects.push({ kind: 'burst', x: px, y: py, born: now, life: 0.7, seed: Math.random() * 6 });
      tick(msg.text);
      renderStatsOverlay();
    } else if (k === 'fight') {
      stats.fights++;
      effects.push({ kind: 'burst', x: px, y: py, born: now, life: 1.0, seed: Math.random() * 6 });
      queueBanner('FIGHT!', '', 'penalty');
      tick(msg.text, 'penalty');
      renderStatsOverlay();
    } else if (k === 'penalty') {
      stats.penalties[msg.team === 0 ? 0 : 1]++;
      queueBanner('PENALTY', msg.text, 'penalty');
      tick(msg.text, 'penalty');
      renderStatsOverlay();
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
    updateRenderTargets(msg);
    setScorebug(msg);
  }
}

/* ---------------- controls ---------------- */
const btnPause = document.getElementById('btn-pause');
const btnSpeed = document.getElementById('btn-speed');
const btnCam = document.getElementById('btn-cam');
const btnStats = document.getElementById('btn-stats');
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
function setCamMode(m) {
  camMode = m;
  btnCam.textContent = camMode === 'follow' ? '🎥' : '🏟';
  btnCam.title = camMode === 'follow' ? 'Follow cam (click for full rink)' : 'Full rink (click for follow cam)';
  btnCam.classList.toggle('active', camMode === 'follow');
}
btnCam.addEventListener('click', () => setCamMode(camMode === 'follow' ? 'full' : 'follow'));
btnStats.addEventListener('click', () => {
  statsVisible = !statsVisible;
  btnStats.classList.toggle('active', statsVisible);
  renderStatsOverlay();
});
document.addEventListener('keydown', e => {
  if (e.code === 'Space' && e.target === document.body) {
    e.preventDefault();
    setPaused(!paused);
  }
  if ((e.key === 'c' || e.key === 'C') && e.target === document.body) {
    setCamMode(camMode === 'follow' ? 'full' : 'follow');
  }
});

// click a skater to follow; click ice to clear
canvas.addEventListener('click', e => {
  if (!cur || !cur.skaters) return;
  const rect = canvas.getBoundingClientRect();
  const mx = (e.clientX - rect.left) * dpr, my = (e.clientY - rect.top) * dpr;
  const rp = rinkFromScreen(mx, my);
  let best = null, bestD = 4; // rink feet
  const all = cur.skaters.concat(cur.goalies || []);
  for (const s of all) {
    const d = Math.hypot(s.x - rp.x, s.y - rp.y);
    if (d < bestD) { bestD = d; best = s; }
  }
  followName = best && best.name ? best.name : null;
  if (followName) tick('Following ' + followName);
});

// hover: nearest player name tag
let hoverRaf = 0;
canvas.addEventListener('mousemove', e => {
  if (hoverRaf) return;
  hoverRaf = requestAnimationFrame(() => {
    hoverRaf = 0;
    if (!cur || !cur.skaters) { hoverName = null; return; }
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * dpr, my = (e.clientY - rect.top) * dpr;
    const rp = rinkFromScreen(mx, my);
    let best = null, bestD = 3.2;
    const all = cur.skaters.concat(cur.goalies || []);
    for (const s of all) {
      const d = Math.hypot(s.x - rp.x, s.y - rp.y);
      if (d < bestD) { bestD = d; best = s; }
    }
    const nh = best && best.name ? best.name : null;
    if (nh !== hoverName) {
      hoverName = nh;
      canvas.style.cursor = nh ? 'pointer' : 'default';
    }
  });
});
canvas.addEventListener('mouseleave', () => { hoverName = null; });

setCamMode('follow');
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
