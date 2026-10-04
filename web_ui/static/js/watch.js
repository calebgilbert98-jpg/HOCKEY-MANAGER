/* Puck Dynasty web visualizer — 60fps canvas renderer */
const canvas = document.getElementById('rink');
const ctx = canvas.getContext('2d');

// Rink coords: 200x85 ft. Canvas scales to fit.
const RL = 200, RW = 85;
let scale = 4, ox = 0, oy = 0;

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
const trail = [];  // puck trail points

function X(x) { return ox + x * scale; }
function Y(y) { return oy + y * scale; }

function drawRink() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  // ice
  const g = ctx.createLinearGradient(0, 0, 0, canvas.height);
  g.addColorStop(0, '#dfe9f2'); g.addColorStop(1, '#c9d8e6');
  ctx.fillStyle = g;
  roundRect(X(0), Y(0), RL * scale, RW * scale, 22 * scale);
  ctx.fill();
  // subtle ice texture
  ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) {
    ctx.beginPath();
    const yy = Y(8 + i * 15 + Math.sin(Date.now() / 3000 + i) * 2);
    ctx.moveTo(X(4), yy); ctx.lineTo(X(196), yy); ctx.stroke();
  }
  ctx.strokeStyle = '#c0392b'; ctx.lineWidth = 2 * scale / 4;
  // center line + blue lines
  ctx.beginPath(); ctx.moveTo(X(100), Y(0)); ctx.lineTo(X(100), Y(85)); ctx.stroke();
  ctx.strokeStyle = '#2e6fd8'; ctx.lineWidth = 4 * scale / 4;
  for (const bx of [75, 125]) {
    ctx.beginPath(); ctx.moveTo(X(bx), Y(0)); ctx.lineTo(X(bx), Y(85)); ctx.stroke();
  }
  // goal lines + creases
  ctx.strokeStyle = '#c0392b'; ctx.lineWidth = 2 * scale / 4;
  for (const gx of [11, 189]) {
    ctx.beginPath(); ctx.moveTo(X(gx), Y(6)); ctx.lineTo(X(gx), Y(79)); ctx.stroke();
    ctx.fillStyle = 'rgba(160,200,240,.5)';
    ctx.beginPath(); ctx.arc(X(gx), Y(42.5), 6 * scale / 4, 0, Math.PI * 2); ctx.fill();
  }
  // faceoff dots + circles
  ctx.fillStyle = '#c0392b';
  const dots = [[69, 22], [69, 63], [131, 22], [131, 63], [100, 42.5]];
  for (const [dx, dy] of dots) {
    ctx.beginPath(); ctx.arc(X(dx), Y(dy), 1.1 * scale / 4, 0, Math.PI * 2); ctx.fill();
  }
  ctx.strokeStyle = 'rgba(192,57,43,.55)'; ctx.lineWidth = 1.5 * scale / 4;
  for (const [dx, dy] of [[69, 22], [69, 63], [131, 22], [131, 63]]) {
    ctx.beginPath(); ctx.arc(X(dx), Y(dy), 9 * scale / 4, 0, Math.PI * 2); ctx.stroke();
  }
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawSkater(x, y, team, hasPuck) {
  const px = X(x), py = Y(y), r = 2.6 * scale / 4;
  const color = team === 0 ? '#1d4ed8' : '#b8860b';
  // glow
  const glow = ctx.createRadialGradient(px, py, 0, px, py, r * 3);
  glow.addColorStop(0, team === 0 ? 'rgba(59,130,246,.55)' : 'rgba(232,185,60,.55)');
  glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(px, py, r * 3, 0, Math.PI * 2); ctx.fill();
  // body with shading
  const bg = ctx.createRadialGradient(px - r * .3, py - r * .3, r * .1, px, py, r);
  bg.addColorStop(0, '#ffffff'); bg.addColorStop(.35, color); bg.addColorStop(1, '#0a0a0a');
  ctx.fillStyle = bg;
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  if (hasPuck) {
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(px, py, r + 3, 0, Math.PI * 2); ctx.stroke();
  }
}

function drawPuck(x, y) {
  const px = X(x), py = Y(y);
  // trail
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

function lerp(a, b, t) { return a + (b - a) * t; }

function frame(now) {
  requestAnimationFrame(frame);
  if (paused || !cur) return;
  // interpolate between snapshots
  const span = Math.max(1, curT - prevT);
  let t = (now - prevT) / span;
  t = Math.min(1.2, Math.max(0, t));
  const A = prev || cur, B = cur;
  drawRink();
  const n = Math.min(A.skaters.length, B.skaters.length);
  for (let i = 0; i < n; i++) {
    const x = lerp(A.skaters[i].x, B.skaters[i].x, Math.min(1, t));
    const y = lerp(A.skaters[i].y, B.skaters[i].y, Math.min(1, t));
    const hasPuck = B.possession === B.skaters[i].team &&
      Math.hypot(B.puck.x - B.skaters[i].x, B.puck.y - B.skaters[i].y) < 4;
    drawSkater(x, y, B.skaters[i].team, hasPuck);
  }
  for (const gl of B.goalies) drawSkater(gl.x, gl.y, gl.team, false);
  const px = lerp(A.puck.x, B.puck.x, Math.min(1, t));
  const py = lerp(A.puck.y, B.puck.y, Math.min(1, t));
  drawPuck(px, py);
}

// SSE stream
const es = new EventSource('/api/watch/stream');
es.onmessage = e => {
  try {
    const snap = JSON.parse(e.data);
    prev = cur; prevT = curT;
    cur = snap; curT = performance.now();
    document.getElementById('sb-home').textContent = snap.score.home;
    document.getElementById('sb-away').textContent = snap.score.away;
    document.getElementById('sb-period').textContent = 'P' + snap.period;
    document.getElementById('sb-clock').textContent = snap.clock;
  } catch (err) {}
};

document.getElementById('btn-pause').addEventListener('click', e => {
  paused = !paused;
  e.target.textContent = paused ? '▶' : '⏸';
});
document.getElementById('btn-speed').addEventListener('click', e => {
  speed = speed === 1 ? 2 : speed === 2 ? 4 : 1;
  e.target.textContent = speed + '×';
});

resize();
requestAnimationFrame(frame);
