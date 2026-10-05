/* Puck Dynasty web visualizer — 60fps broadcast-style canvas renderer */
const canvas = document.getElementById('rink');
const ctx = canvas.getContext('2d');

// Rink coords: 200x85 ft. Canvas scales to fit.
const RL = 200, RW = 85;
let scale = 4, ox = 0, oy = 0;

// Team colors (updated from server meta when available)
const TEAM_COLORS = [
  { main: '#1d4ed8', glow: 'rgba(59,130,246,.55)' },   // home: blue
  { main: '#c8102e', glow: 'rgba(232,60,80,.55)' },    // away: red
];

function resize() {
  const stage = canvas.parentElement;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = stage.clientWidth * dpr;
  canvas.height = stage.clientHeight * dpr;
  canvas.style.width = stage.clientWidth + 'px';
  canvas.style.height = stage.clientHeight + 'px';
  const s = Math.min(canvas.width / RL, canvas.height / RW) * 0.96;
  scale = s;
  ox = (canvas.width - RL * s) / 2;
  oy = (canvas.height - RW * s) / 2;
}
window.addEventListener('resize', resize);

// Interpolated state
let cur = null, prev = null, prevT = 0, curT = 0;
let paused = false, speed = 1;
const trail = [];        // puck trail points
const skaterTrails = new Map();  // name -> recent positions
const effects = [];      // transient visual effects (goal flash, hit bursts)
let banner = null;       // {text, until, kind} event banner
let flashUntil = 0, flashColor = '255,255,255';

function X(x) { return ox + x * scale; }
function Y(y) { return oy + y * scale; }

// ---- static rink art, cached to an offscreen canvas ----
let rinkCache = null, rinkCacheKey = '';
function drawRink() {
  const key = canvas.width + 'x' + canvas.height;
  if (!rinkCache || rinkCacheKey !== key) {
    rinkCache = document.createElement('canvas');
    rinkCache.width = canvas.width; rinkCache.height = canvas.height;
    rinkCacheKey = key;
    const c = rinkCache.getContext('2d');
    const Xc = x => ox + x * scale, Yc = y => oy + y * scale;
    const rr = (x, y, w, h, r) => {
      c.beginPath(); c.moveTo(x + r, y);
      c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
      c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
    };
    // ice base with vertical sheen
    const g = c.createLinearGradient(0, 0, canvas.width, canvas.height);
    g.addColorStop(0, '#e8f0f7'); g.addColorStop(.5, '#d7e3ee');
    g.addColorStop(1, '#c3d4e3');
    c.fillStyle = g;
    rr(Xc(0), Yc(0), RL * scale, RW * scale, 22 * scale); c.fill();
    // skate-mark texture (subtle scratches)
    c.strokeStyle = 'rgba(255,255,255,.5)'; c.lineWidth = 1;
    for (let i = 0; i < 26; i++) {
      const y0 = Yc(4 + (i * 37 % 77));
      const x0 = Xc(6 + (i * 53 % 188));
      c.beginPath(); c.moveTo(x0, y0);
      c.lineTo(x0 + 14 * scale / 4, y0 + 3 * scale / 4); c.stroke();
    }
    // zone tint: offensive zones slightly warm
    c.fillStyle = 'rgba(200,60,60,.04)';
    rr(Xc(0), Yc(0), 75 * scale, RW * scale, 0); c.fill();
    rr(Xc(125), Yc(0), 75 * scale, RW * scale, 0); c.fill();
    const lw = Math.max(1, 2 * scale / 4);
    // center line (checkered feel: thicker red)
    c.strokeStyle = '#c0392b'; c.lineWidth = lw * 2.2;
    c.beginPath(); c.moveTo(Xc(100), Yc(0)); c.lineTo(Xc(100), Yc(85)); c.stroke();
    // blue lines
    c.strokeStyle = '#2e6fd8'; c.lineWidth = lw * 3.2;
    for (const bx of [75, 125]) {
      c.beginPath(); c.moveTo(Xc(bx), Yc(0)); c.lineTo(Xc(bx), Yc(85)); c.stroke();
    }
    // goal lines + creases
    c.strokeStyle = '#c0392b'; c.lineWidth = lw;
    for (const gx of [11, 189]) {
      c.beginPath(); c.moveTo(Xc(gx), Yc(6)); c.lineTo(Xc(gx), Yc(79)); c.stroke();
      c.fillStyle = 'rgba(150,190,235,.55)';
      c.beginPath(); c.arc(Xc(gx), Yc(42.5), 6 * scale / 4, 0, Math.PI * 2); c.fill();
      c.strokeStyle = 'rgba(192,57,43,.7)';
      c.beginPath(); c.arc(Xc(gx), Yc(42.5), 6 * scale / 4, 0, Math.PI * 2); c.stroke();
      // net (red frame)
      c.strokeStyle = '#e74c3c'; c.lineWidth = lw * 1.6;
      const dir = gx < 100 ? -1 : 1;
      c.beginPath();
      c.moveTo(Xc(gx), Yc(38.5)); c.lineTo(Xc(gx + dir * 3.5), Yc(38.5));
      c.lineTo(Xc(gx + dir * 3.5), Yc(46.5)); c.lineTo(Xc(gx), Yc(46.5));
      c.stroke();
    }
    // faceoff dots + circles
    c.fillStyle = '#c0392b';
    const dots = [[69, 22], [69, 63], [131, 22], [131, 63], [100, 42.5]];
    for (const [dx, dy] of dots) {
      c.beginPath(); c.arc(Xc(dx), Yc(dy), 1.1 * scale / 4, 0, Math.PI * 2); c.fill();
    }
    c.strokeStyle = 'rgba(192,57,43,.55)'; c.lineWidth = 1.5 * scale / 4;
    for (const [dx, dy] of [[69, 22], [69, 63], [131, 22], [131, 63]]) {
      c.beginPath(); c.arc(Xc(dx), Yc(dy), 9 * scale / 4, 0, Math.PI * 2); c.stroke();
    }
    // trapezoid behind nets
    c.strokeStyle = 'rgba(192,57,43,.4)'; c.lineWidth = lw;
    for (const gx of [11, 189]) {
      const dir = gx < 100 ? 1 : -1;
      c.beginPath();
      c.moveTo(Xc(gx), Yc(34)); c.lineTo(Xc(gx + dir * 11), Yc(28));
      c.moveTo(Xc(gx), Yc(51)); c.lineTo(Xc(gx + dir * 11), Yc(57));
      c.stroke();
    }
  }
  ctx.drawImage(rinkCache, 0, 0);
}

function drawSkater(x, y, team, hasPuck, name) {
  const px = X(x), py = Y(y), r = 2.6 * scale / 4;
  const col = TEAM_COLORS[team] || TEAM_COLORS[0];
  // motion trail
  if (name) {
    let tr = skaterTrails.get(name);
    if (!tr) { tr = []; skaterTrails.set(name, tr); }
    tr.push({x: px, y: py});
    if (tr.length > 6) tr.shift();
    for (let i = 0; i < tr.length; i++) {
      const a = (i / tr.length) * 0.28;
      ctx.fillStyle = col.glow.replace(/[\d.]+\)$/, a.toFixed(2) + ')');
      ctx.beginPath(); ctx.arc(tr[i].x, tr[i].y, r * (0.4 + 0.6 * i / tr.length), 0, Math.PI * 2); ctx.fill();
    }
  }
  // glow
  const glow = ctx.createRadialGradient(px, py, 0, px, py, r * 3);
  glow.addColorStop(0, col.glow); glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(px, py, r * 3, 0, Math.PI * 2); ctx.fill();
  // body with shading
  const bg = ctx.createRadialGradient(px - r * .3, py - r * .3, r * .1, px, py, r);
  bg.addColorStop(0, '#ffffff'); bg.addColorStop(.35, col.main); bg.addColorStop(1, '#0a0a0a');
  ctx.fillStyle = bg;
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  if (hasPuck) {
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(px, py, r + 3, 0, Math.PI * 2); ctx.stroke();
  }
}

function drawPuck(x, y) {
  const px = X(x), py = Y(y);
  trail.push({x: px, y: py});
  if (trail.length > 14) trail.shift();
  for (let i = 0; i < trail.length; i++) {
    const t = trail[i], a = i / trail.length;
    ctx.fillStyle = `rgba(20,20,20,${a * .35})`;
    ctx.beginPath(); ctx.arc(t.x, t.y, (1 + a * 2) * scale / 4, 0, Math.PI * 2); ctx.fill();
  }
  const r = 1.5 * scale / 4;
  const glow = ctx.createRadialGradient(px, py, 0, px, py, r * 4);
  glow.addColorStop(0, 'rgba(0,0,0,.5)'); glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(px, py, r * 4, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#111';
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,.25)';
  ctx.beginPath(); ctx.arc(px - r * .3, py - r * .3, r * .45, 0, Math.PI * 2); ctx.fill();
}

function drawEffects(now) {
  for (let i = effects.length - 1; i >= 0; i--) {
    const e = effects[i];
    const age = (now - e.born) / 1000;
    if (age > e.life) { effects.splice(i, 1); continue; }
    const t = age / e.life, px = X(e.x), py = Y(e.y);
    if (e.kind === 'burst') {
      // expanding ring
      ctx.strokeStyle = `rgba(255,200,60,${(1 - t) * .9})`;
      ctx.lineWidth = 3 * (1 - t) + 1;
      ctx.beginPath(); ctx.arc(px, py, (4 + t * 26) * scale / 4, 0, Math.PI * 2); ctx.stroke();
    } else if (e.kind === 'goalring') {
      ctx.strokeStyle = `rgba(255,215,0,${(1 - t)})`;
      ctx.lineWidth = 4;
      ctx.beginPath(); ctx.arc(px, py, (6 + t * 60) * scale / 4, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = `rgba(255,255,255,${(1 - t) * .8})`;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(px, py, (3 + t * 40) * scale / 4, 0, Math.PI * 2); ctx.stroke();
    }
  }
  // screen flash
  if (now < flashUntil) {
    const a = (flashUntil - now) / 600 * 0.22;
    ctx.fillStyle = `rgba(${flashColor},${a.toFixed(3)})`;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
}

function drawBanner(now) {
  if (!banner || now > banner.until) return;
  const w = Math.min(canvas.width * .8, 560);
  const h = 44 * (canvas.width / 1000);
  const x = (canvas.width - w) / 2, y = canvas.height - h - 18;
  const a = Math.min(1, (banner.until - now) / 400, (now - banner.from) / 200);
  ctx.globalAlpha = Math.max(0, a);
  ctx.fillStyle = 'rgba(8,12,24,.88)';
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x, y, w, h, 10); else ctx.rect(x, y, w, h);
  ctx.fill();
  ctx.strokeStyle = banner.kind === 'goal' ? '#ffd700' : 'rgba(59,130,246,.8)';
  ctx.lineWidth = 2; ctx.stroke();
  ctx.fillStyle = banner.kind === 'goal' ? '#ffd700' : '#fff';
  ctx.font = `600 ${Math.round(h * .42)}px system-ui, sans-serif`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(banner.text.slice(0, 64), canvas.width / 2, y + h / 2);
  ctx.globalAlpha = 1;
}

function showBanner(text, kind) {
  const now = performance.now();
  banner = { text, kind: kind || 'info', from: now, until: now + 3600 };
}

function lerp(a, b, t) { return a + (b - a) * t; }

function frame(now) {
  requestAnimationFrame(frame);
  if (paused || !cur) return;
  const span = Math.max(1, curT - prevT);
  let t = (now - prevT) / span;
  t = Math.min(1.2, Math.max(0, t));
  const A = prev || cur, B = cur;
  drawRink();
  if (B.type === 'skate') {
    const n = Math.min(A.skaters ? A.skaters.length : 0, B.skaters.length);
    for (let i = 0; i < n; i++) {
      const x = lerp(A.skaters[i].x, B.skaters[i].x, Math.min(1, t));
      const y = lerp(A.skaters[i].y, B.skaters[i].y, Math.min(1, t));
      const hasPuck = B.possession === B.skaters[i].team &&
        Math.hypot(B.puck.x - B.skaters[i].x, B.puck.y - B.skaters[i].y) < 4;
      drawSkater(x, y, B.skaters[i].team, hasPuck, B.skaters[i].name);
    }
    for (const gl of B.goalies) drawSkater(gl.x, gl.y, gl.team, false, gl.name);
    const px = lerp(A.puck.x, B.puck.x, Math.min(1, t));
    const py = lerp(A.puck.y, B.puck.y, Math.min(1, t));
    drawPuck(px, py);
  }
  drawEffects(now);
  drawBanner(now);
}

function setScorebug(snap) {
  if (snap.home_abbr) document.getElementById('sb-home-abbr').textContent = snap.home_abbr;
  if (snap.away_abbr) document.getElementById('sb-away-abbr').textContent = snap.away_abbr;
  if (snap.score) {
    document.getElementById('sb-home').textContent = snap.score.home;
    document.getElementById('sb-away').textContent = snap.score.away;
  }
  if (snap.period) document.getElementById('sb-period').textContent = 'P' + snap.period;
  if (snap.clock) document.getElementById('sb-clock').textContent = snap.clock;
}

// SSE stream (reconnects when speed changes)
let es = null;
function connectStream() {
  if (es) es.close();
  es = new EventSource('/api/watch/stream?speed=' + speed);
  es.onmessage = handleMessage;
}
function handleMessage(e) {
  try {
    const msg = JSON.parse(e.data);
    const now = performance.now();
    if (msg.type === 'meta') {
      if (msg.home_abbr) document.getElementById('sb-home-abbr').textContent = msg.home_abbr;
      if (msg.away_abbr) document.getElementById('sb-away-abbr').textContent = msg.away_abbr;
      showBanner(`${msg.away} at ${msg.home}`, 'info');
      return;
    }
    if (msg.type === 'highlight') {
      setScorebug(msg);
      if (msg.kind === 'goal') {
        const gx = msg.team === 0 ? 189 : 11;  // net that was scored on
        effects.push({kind: 'goalring', x: gx, y: 42.5, born: now, life: 1.4});
        flashUntil = now + 600; flashColor = '255,215,0';
        showBanner(msg.text, 'goal');
      } else if (msg.kind === 'hit' || msg.kind === 'fight') {
        // burst at puck location
        if (cur && cur.puck) effects.push({kind: 'burst', x: cur.puck.x, y: cur.puck.y, born: now, life: 0.7});
        if (msg.kind === 'fight') showBanner(msg.text, 'info');
      } else if (msg.kind === 'period_start' || msg.kind === 'period_end' || msg.kind === 'game_start') {
        showBanner(msg.text, 'info');
      }
      return;
    }
    if (msg.type === 'game_end') {
      setScorebug(msg);
      showBanner(`FINAL: ${msg.home_abbr} ${msg.score.home} — ${msg.away_abbr} ${msg.score.away}`, 'goal');
      es.close();
      return;
    }
    if (msg.type === 'skate') {
      prev = cur; prevT = curT;
      cur = msg; curT = performance.now();
      setScorebug(msg);
    }
  } catch (err) {}
};

document.getElementById('btn-pause').addEventListener('click', e => {
  paused = !paused;
  e.target.textContent = paused ? '▶' : '⏸';
});
document.getElementById('btn-speed').addEventListener('click', e => {
  speed = speed === 1 ? 2 : speed === 2 ? 4 : 1;
  e.target.textContent = speed + '×';
  connectStream();  // reconnect at the new pace
});

resize();
connectStream();
requestAnimationFrame(frame);

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
