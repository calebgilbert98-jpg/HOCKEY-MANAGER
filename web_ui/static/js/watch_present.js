/* Puck Dynasty — Watch presentation layer (Batch E, 2026-10-06).
 *
 * Ports pbp_visual_sim.py's presentation elements to the web watch page:
 *  - win-probability bar (same formula: score lead + shot tilt, time-weighted)
 *  - intensity (tension) meter with contributor details
 *  - momentum strip (last-10-per-team deques, same weights/reading)
 *  - Next Big Moment button (jumps the text feed to the latest big moment)
 *  - tactics tab (team tactics + familiarity + identity lines)
 *  - sound toggle (WebAudio goal horn / whistle, persisted)
 *  - detail modes: full / key / text (EHM-style)
 *
 * Reads the retained JSON-safe event log from /api/watch/events (the
 * same feed watch_modes.js uses); the SSE visualizer stream is untouched.
 */
(function () {
'use strict';

var lastLen = 0;
var home = '', away = '', homeAbbr = '', awayAbbr = '';
var score = { home: 0, away: 0 }, period = 1, clockRem = 1200;
var shots = [0, 0];
var mom = [[], []];            // last-10 weights per team (0=home, 1=away)
var tensionLive = [];          // {label, points, t}
var bigMoments = [];           // indices into interesting events
var soundOn = (function () {
  try { return localStorage.getItem('pd_watch_sound') !== 'off'; } catch (e) { return true; }
})();
var audioCtx = null;

var BIG_RE = /goal|penalty|fight|penalty_shot/;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}

function teamIdx(ev) {
  // attacking_team / scoring_team name the attacking side;
  // defending_team names the goalie's side.
  var n = String(ev.attacking_team || ev.scoring_team || '');
  if (n && home && n === home) return 0;
  if (n && away && n === away) return 1;
  var d = String(ev.defending_team || '');
  if (d && home && d === home) return 0;
  if (d && away && d === away) return 1;
  return -1;
}

function pushMomentum(ti, w) {
  if (ti < 0) return;
  mom[ti].push(w);
  if (mom[ti].length > 10) mom[ti].shift();
}

function addTension(label, pts) {
  tensionLive.push({ label: label, points: pts, t: Date.now() });
  if (tensionLive.length > 24) tensionLive.shift();
}

/* ---------------- DOM ---------------- */
function build() {
  var bar = document.querySelector('.watch-bar');
  if (!bar || document.getElementById('wp-strip')) return;

  var strip = document.createElement('div');
  strip.id = 'wp-strip';
  strip.innerHTML =
    '<div class="wp-row">' +
      '<div class="wp-block wp-wp"><div class="wp-label">WIN PROB</div>' +
        '<div class="wp-bar"><div class="wp-fill-home" id="wp-fill-h"></div>' +
        '<div class="wp-fill-away" id="wp-fill-a"></div>' +
        '<span class="wp-teams"><span id="wp-ha">···</span><span id="wp-pct">50%</span>' +
        '<span id="wp-aa">···</span></span></div></div>' +
      '<div class="wp-block wp-ten"><div class="wp-label">INTENSITY <span id="wp-ten-num">–</span></div>' +
        '<div class="wp-meter"><div class="wp-meter-fill" id="wp-ten-fill"></div></div></div>' +
      '<div class="wp-block wp-mom"><div class="wp-label">MOMENTUM <span id="wp-mom-lab">Even</span></div>' +
        '<div class="wp-bar"><div class="wp-fill-home" id="wp-mom-h"></div>' +
        '<div class="wp-fill-away" id="wp-mom-a"></div></div></div>' +
    '</div>' +
    '<div class="wp-row wp-btns">' +
      '<button id="wp-next" title="Jump to the next big moment">⏭ Next Big Moment</button>' +
      '<button id="wp-tactics" title="Team tactics">📋 Tactics</button>' +
      '<button id="wp-sound" title="Arena sound"></button>' +
      '<span class="wp-detail-lab">Detail:</span>' +
      '<button class="wp-detail active" data-d="full">Full</button>' +
      '<button class="wp-detail" data-d="key">Key</button>' +
      '<button class="wp-detail" data-d="text">Text</button>' +
    '</div>' +
    '<div class="wp-panel hidden" id="wp-tactics-panel"></div>' +
    '<div class="wp-panel hidden" id="wp-ten-panel"></div>';
  bar.parentNode.insertBefore(strip, bar.nextSibling);

  document.getElementById('wp-next').addEventListener('click', jumpToMoment);
  document.getElementById('wp-tactics').addEventListener('click', toggleTactics);
  document.getElementById('wp-sound').addEventListener('click', toggleSound);
  document.querySelectorAll('.wp-detail').forEach(function (b) {
    b.addEventListener('click', function () { setDetail(b.dataset.d); });
  });
  document.querySelector('.wp-ten').addEventListener('click', toggleTensionPanel);
  refreshSoundBtn();
}

function refreshSoundBtn() {
  var b = document.getElementById('wp-sound');
  if (b) { b.textContent = soundOn ? '🔊 Sound' : '🔇 Muted'; b.classList.toggle('active', soundOn); }
}

function toggleSound() {
  soundOn = !soundOn;
  try { localStorage.setItem('pd_watch_sound', soundOn ? 'on' : 'off'); } catch (e) {}
  refreshSoundBtn();
}

function setDetail(d) {
  window.PD_DETAIL = d;
  document.querySelectorAll('.wp-detail').forEach(function (b) {
    b.classList.toggle('active', b.dataset.d === d);
  });
  var stage = document.getElementById('pane-visual');
  var textBtn = document.querySelector('.wm-tab[data-mode="text"]');
  if (d === 'text') {
    if (stage) stage.classList.add('hidden');
    if (textBtn) textBtn.click();
  } else {
    if (stage) stage.classList.remove('hidden');
    var visBtn = document.querySelector('.wm-tab[data-mode="visual"]');
    if (visBtn) visBtn.click();
  }
  try { localStorage.setItem('pd_watch_detail', d); } catch (e) {}
}

/* ---------------- event processing ---------------- */
function processEvents(evs) {
  var fresh = evs.slice(lastLen);
  lastLen = evs.length;
  fresh.forEach(function (ev) {
    if (!ev || ev.type === 'skate') return;
    var t = String(ev.type || '');
    var ti = teamIdx(ev);
    // score / clock state
    if (ev.home_score != null) score.home = ev.home_score;
    if (ev.away_score != null) score.away = ev.away_score;
    if (ev.period) period = ev.period;
    if (ev.clock != null) clockRem = ev.clock;
    // shots + momentum (pbp_visual_sim weights)
    if (/^(shot|missed_shot|blocked_shot)$/.test(t)) {
      if (ti >= 0) { shots[ti]++; pushMomentum(ti, 1); }
      addTension('Shot — ' + (ev.shooter || ''), 1);
    } else if (t === 'save') {
      var gti = teamIdx(ev); // goalie's side via defending_team
      if (gti >= 0) { pushMomentum(gti, 1); shots[1 - gti]++; }
      addTension('Save — ' + (ev.goalie || ''), 1);
    } else if (t === 'goal') {
      var sti = String(ev.scoring_team || '') === home ? 0
              : String(ev.scoring_team || '') === away ? 1 : -1;
      if (sti >= 0) { shots[sti]++; pushMomentum(sti, 3); }
      addTension('GOAL — ' + (ev.shooter || ''), 6);
      horn();
    } else if (t === 'penalty') {
      addTension('Penalty — ' + (ev.player || ''), 3);
      buzz();
    } else if (t === 'fight') {
      addTension('Fight!', 6);
    } else if (t === 'milestone') {
      addTension('Milestone', 4);
    } else if (t === 'period_end') {
      chime();
    }
    if (BIG_RE.test(t)) bigMoments.push(evs.indexOf(ev));
  });
  // decay tension contributors older than ~6 game-minutes is overkill;
  // keep the last 24 contributors like the desktop's live list.
  renderMeters();
}

function winProb() {
  var lead = score.home - score.away;
  var tRem = Math.max(0, clockRem + Math.max(0, 3 - period) * 1200);
  var x = lead * 1.7 / (1.0 + tRem / 750.0) + (shots[0] - shots[1]) * 0.015;
  var p = 1.0 / (1.0 + Math.exp(-x));
  return Math.min(0.98, Math.max(0.02, p));
}

function momentumReading() {
  var net = mom[0].reduce(function (a, b) { return a + b; }, 0) -
            mom[1].reduce(function (a, b) { return a + b; }, 0);
  var s = Math.max(-100, Math.min(100, net / 24 * 100));
  return { score: s, label: Math.abs(s) < 15 ? 'Even' : (s > 0 ? 'Home' : 'Away') };
}

function tensionValue() {
  var v = 20 + tensionLive.reduce(function (a, c) { return a + c.points; }, 0);
  return Math.min(100, Math.max(0, Math.round(v)));
}

function renderMeters() {
  var p = winProb();
  var fh = document.getElementById('wp-fill-h'), fa = document.getElementById('wp-fill-a');
  if (fh && fa) {
    fh.style.width = (p * 100).toFixed(1) + '%';
    fa.style.width = ((1 - p) * 100).toFixed(1) + '%';
    fh.style.left = '0'; fa.style.right = '0'; fa.style.left = 'auto';
  }
  var pct = document.getElementById('wp-pct');
  if (pct) pct.textContent = Math.round(p * 100) + '%';
  var ha = document.getElementById('wp-ha'), aa = document.getElementById('wp-aa');
  if (ha) ha.textContent = homeAbbr || '···';
  if (aa) aa.textContent = awayAbbr || '···';

  var tv = tensionValue();
  var tf = document.getElementById('wp-ten-fill'), tn = document.getElementById('wp-ten-num');
  if (tf) tf.style.width = tv + '%';
  if (tn) tn.textContent = tv;

  var m = momentumReading();
  var mh = document.getElementById('wp-mom-h'), ma = document.getElementById('wp-mom-a');
  if (mh && ma) {
    var hw = 50 + m.score / 2, aw = 50 - m.score / 2;
    mh.style.width = hw.toFixed(1) + '%'; ma.style.width = aw.toFixed(1) + '%';
    mh.style.left = '0'; ma.style.right = '0'; ma.style.left = 'auto';
  }
  var ml = document.getElementById('wp-mom-lab');
  if (ml) ml.textContent = m.label;
}

function toggleTensionPanel() {
  var p = document.getElementById('wp-ten-panel');
  if (!p) return;
  if (!p.classList.contains('hidden')) { p.classList.add('hidden'); return; }
  var rows = tensionLive.slice(-10).reverse().map(function (c) {
    return '<div class="wp-ten-row"><span>' + esc(c.label) + '</span><b>+' + c.points + '</b></div>';
  }).join('') || '<div class="wp-ten-row"><span>No big moments yet.</span></div>';
  p.innerHTML = '<div class="wp-panel-title">Intensity drivers</div>' + rows;
  p.classList.remove('hidden');
}

/* ---------------- Next Big Moment ---------------- */
function jumpToMoment() {
  // Switch to the text feed and jump to the latest big moment.
  var textBtn = document.querySelector('.wm-tab[data-mode="text"]');
  if (textBtn) textBtn.click();
  setTimeout(function () {
    var feed = document.getElementById('text-feed');
    if (!feed) return;
    var rows = feed.querySelectorAll('.tl-row');
    for (var i = rows.length - 1; i >= 0; i--) {
      var cls = rows[i].className || '';
      if (/tl-goal|tl-penalty|tl-fight|tl-penalty_shot/.test(cls)) {
        rows[i].scrollIntoView({ block: 'center' });
        rows[i].classList.add('rp-flash');
        (function (el) { setTimeout(function () { el.classList.remove('rp-flash'); }, 1600); })(rows[i]);
        return;
      }
    }
    feed.scrollTop = feed.scrollHeight;
  }, 350);
}

/* ---------------- tactics tab ---------------- */
var tacticsLoaded = false;
function toggleTactics() {
  var p = document.getElementById('wp-tactics-panel');
  if (!p) return;
  if (!p.classList.contains('hidden')) { p.classList.add('hidden'); return; }
  p.classList.remove('hidden');
  if (tacticsLoaded) return;
  tacticsLoaded = true;
  p.innerHTML = '<div class="wp-panel-title">Tactics — loading…</div>';
  fetch('/api/tactics').then(function (r) { return r.json(); }).then(function (d) {
    var html = '<div class="wp-panel-title">Tactics</div>';
    if (!d || !(d.groups || []).length) {
      p.innerHTML = html + '<div class="dim">No tactics data.</div>';
      return;
    }
    html += '<div class="wp-ten-row"><span>Familiarity</span><b>' + esc(d.familiarity || '?') + '</b></div>';
    html += '<div class="wp-ten-row"><span>Control</span><b>' + esc(d.control || '?') + '</b></div>';
    (d.identity_lines || []).forEach(function (l) {
      html += '<div class="wp-ten-row"><span>' + esc(l) + '</span></div>';
    });
    (d.groups || []).slice(0, 8).forEach(function (g) {
      html += '<div class="wp-ten-row"><span>' + esc(g.title) + '</span><b>' +
              esc(String(g.current).replace(/_/g, ' ')) + '</b></div>';
    });
    p.innerHTML = html;
  }).catch(function () {
    p.innerHTML = '<div class="wp-panel-title">Tactics</div><div class="dim">Could not load.</div>';
  });
}

/* ---------------- sound (WebAudio) ---------------- */
function ctx() {
  if (!audioCtx) {
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
    catch (e) { audioCtx = null; }
  }
  return audioCtx;
}
function tone(freq, dur, when, type, gain) {
  var c = ctx();
  if (!c || !soundOn) return;
  try {
    var o = c.createOscillator(), g = c.createGain();
    o.type = type || 'sine'; o.frequency.value = freq;
    g.gain.setValueAtTime(gain || 0.12, c.currentTime + when);
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + when + dur);
    o.connect(g); g.connect(c.destination);
    o.start(c.currentTime + when); o.stop(c.currentTime + when + dur + 0.05);
  } catch (e) {}
}
function horn() { // goal horn: two-tone blast
  tone(233, 0.7, 0, 'sawtooth', 0.10);
  tone(233, 0.7, 0.8, 'sawtooth', 0.10);
  tone(466, 0.4, 0, 'triangle', 0.06);
}
function buzz() { tone(140, 0.25, 0, 'square', 0.05); }
function chime() { tone(660, 0.3, 0, 'sine', 0.07); tone(880, 0.4, 0.25, 'sine', 0.07); }

/* ---------------- poll loop ---------------- */
function poll() {
  fetch('/api/watch/events').then(function (r) { return r.json(); }).then(function (d) {
    var evs = d.events || [];
    if (d.home) { home = d.home; away = d.away; homeAbbr = d.home_abbr; awayAbbr = d.away_abbr; }
    if (evs.length !== lastLen) processEvents(evs);
    else renderMeters();
  }).catch(function () {});
}

build();
try {
  var pref = localStorage.getItem('pd_watch_detail');
  if (pref === 'key' || pref === 'text') setDetail(pref);
} catch (e) {}
setInterval(poll, 3000);
poll();
})();
