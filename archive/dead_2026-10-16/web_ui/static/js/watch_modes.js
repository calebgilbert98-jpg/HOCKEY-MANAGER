/* Puck Dynasty — Watch modes: Text / Shot Chart / Box Score.
   The canvas visualizer (watch.js) is untouched; these modes read the
   JSON-safe event log from /api/watch/events and the live box score
   from /api/watch/boxscore. */
(function () {
  'use strict';

  var mode = 'visual';
  var textTimer = null, boxTimer = null;
  var chartMarkers = [];   // {x, y, px, py, team, ev, goal}
  var lastTextCount = -1;

  /* ---------- mode tabs ---------- */
  var tabs = document.querySelectorAll('.wm-tab');
  tabs.forEach(function (t) {
    t.addEventListener('click', function () { setMode(t.dataset.mode); });
  });

  function setMode(m) {
    mode = m;
    tabs.forEach(function (t) { t.classList.toggle('active', t.dataset.mode === m); });
    ['visual', 'text', 'chart', 'box'].forEach(function (k) {
      document.getElementById('pane-' + k).classList.toggle('hidden', k !== m);
    });
    stopTimers();
    if (m === 'text') { renderText(true); textTimer = setInterval(function () { renderText(false); }, 5000); }
    if (m === 'chart') { renderChart(); }
    if (m === 'box') { renderBox(); boxTimer = setInterval(renderBox, 10000); }
    // Re-run the visualizer's resize handler when we return to it
    // (watch.js listens on window resize).
    if (m === 'visual') { try { window.dispatchEvent(new Event('resize')); } catch (e) {} }
  }

  function stopTimers() {
    if (textTimer) { clearInterval(textTimer); textTimer = null; }
    if (boxTimer) { clearInterval(boxTimer); boxTimer = null; }
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function fmtClock(sec) {
    sec = Math.max(0, Math.round(sec || 0));
    return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0');
  }

  function periodLabel(p) { return 'P' + (p || 1); }

  /* ---------- event -> one text line ---------- */
  function eventLine(ev) {
    var t = ev.type, clk = fmtClock(ev.clock), pl = periodLabel(ev.period);
    var pre = '<span class="tl-meta">' + esc(pl) + ' ' + esc(clk) + '</span> ';
    switch (t) {
      case 'game_start':
        return pre + '<span class="tl-big">Puck drop: ' + esc(ev.away_team || '') +
               ' at ' + esc(ev.home_team || '') + '</span>';
      case 'period_start': return pre + 'Start of period ' + esc(ev.period) + '.';
      case 'period_end': return pre + 'End of period ' + esc(ev.period) + '.';
      case 'game_end': return pre + '<span class="tl-big">Final.</span>';
      case 'shot': {
        var d = shotDesc(ev);
        return pre + 'Shot — <b>' + esc(ev.shooter || '?') + '</b>' + d.detail;
      }
      case 'missed_shot':
        return pre + 'Missed — <b>' + esc(ev.shooter || '?') + '</b>' + shotDesc(ev).detail + '.';
      case 'blocked_shot':
        return pre + 'Blocked — <b>' + esc(ev.shooter || '?') + '</b>' + shotDesc(ev).detail +
               (ev.blocker ? ' by <b>' + esc(ev.blocker) + '</b>' : '') + '.';
      case 'goal': {
        var a = ev.assists && ev.assists.length ? ' <span class="tl-dim">(assists: ' + esc(ev.assists.join(', ')) + ')</span>' : '';
        return pre + '<span class="tl-goal">🚨 GOAL — <b>' + esc(ev.shooter || '?') + '</b>' +
               shotDesc(ev).detail + a + ' <span class="tl-score">' +
               esc(ev.home_score) + '–' + esc(ev.away_score) + '</span></span>';
      }
      case 'penalty':
        return pre + '<span class="tl-pen">Penalty — <b>' + esc(ev.player || '?') + '</b> (' +
               esc(ev.infraction || ev.reason || 'infraction') + ').</span>';
      case 'penalty_shot':
        return pre + '<span class="tl-big">Penalty shot — <b>' + esc(ev.player || '?') + '</b>.</span>';
      case 'hit':
        return pre + 'Hit — <b>' + esc(ev.hitting_player || '?') + '</b> on <b>' +
               esc(ev.target_player || '?') + '</b>.';
      case 'fight': return pre + '<span class="tl-big">🥊 Fight!</span>';
      case 'milestone':
        return pre + '<span class="tl-big">⭐ ' + esc(String(ev.kind || 'milestone').replace(/_/g, ' ')) +
               (ev.player ? ' — <b>' + esc(ev.player) + '</b>' : '') + '</span>';
      case 'icing': return pre + 'Icing.';
      case 'offside': return pre + 'Offside.';
      case 'goalie_pulled': return pre + '<span class="tl-big">Empty net — goalie pulled.</span>';
      default:
        return pre + '<span class="tl-dim">' + esc(String(t).replace(/_/g, ' ')) + '.</span>';
    }
  }

  function shotDesc(ev) {
    var bits = [];
    if (ev.shot_type) bits.push(String(ev.shot_type).replace(/_/g, ' '));
    if (ev.location) bits.push(String(ev.location).replace(/_/g, ' '));
    if (ev.distance != null) bits.push(Math.round(ev.distance) + ' ft');
    return { detail: bits.length ? ' <span class="tl-dim">(' + esc(bits.join(', ')) + ')</span>' : '' };
  }

  /* ---------- text mode ---------- */
  function renderText(force) {
    var feed = document.getElementById('text-feed');
    fetch('/api/watch/events').then(function (r) { return r.json(); }).then(function (data) {
      var evs = data.events || [];
      if (!data.live && !evs.length) {
        feed.innerHTML = '<div class="tl-empty">No live game right now — text mode needs a live sim. Open the Visualizer tab or start your next game.</div>';
        return;
      }
      if (evs.length === lastTextCount && !force) return;
      lastTextCount = evs.length;
      var interesting = evs.filter(function (e) { return e.type !== 'skate'; });
      // Detail mode "key" (Batch E): text feed shows only the big moments.
      if (window.PD_DETAIL === 'key') {
        interesting = interesting.filter(function (e) {
          return /goal|penalty|fight|milestone|period_(start|end)|game_(start|end)|goalie_pulled/.test(e.type || '');
        });
      }
      var nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 120;
      feed.innerHTML = interesting.map(function (e) {
        return '<div class="tl-row tl-' + esc(e.type) + '">' + eventLine(e) + '</div>';
      }).join('') || '<div class="tl-empty">Waiting for the first whistle…</div>';
      if (nearBottom || force) feed.scrollTop = feed.scrollHeight;
      document.getElementById('ws-game').textContent =
        (data.away_abbr || '') + ' @ ' + (data.home_abbr || '');
    }).catch(function () {
      feed.innerHTML = '<div class="tl-empty">Could not reach the game feed.</div>';
    });
  }

  /* ---------- shot chart ---------- */
  var RINK_L = 200, RINK_W = 85;

  function teamIdx(ev, data) {
    var a = String(ev.attacking_team || '');
    if (data.home && a === data.home) return 0;
    if (data.away && a === data.away) return 1;
    return 0;
  }

  function renderChart() {
    var canvas = document.getElementById('shotchart');
    var wrap = canvas.parentElement;
    var W = Math.max(320, wrap.clientWidth), H = Math.max(220, Math.round(W * (RINK_W / RINK_L)));
    canvas.width = W; canvas.height = H;
    var ctx = canvas.getContext('2d');
    drawRink(ctx, W, H);
    chartMarkers = [];

    fetch('/api/watch/events').then(function (r) { return r.json(); }).then(function (data) {
      var evs = data.events || [];
      if (!data.live && !evs.length) {
        drawEmpty(ctx, W, H, 'No live game — shot chart needs a live sim.');
        setLegend(data, 0, 0, 0);
        return;
      }
      var sx = W / RINK_L, sy = H / RINK_W;
      var lastByShooter = {};
      var nShots = 0, nGoals = 0;
      evs.forEach(function (ev) {
        if (ev.type === 'shot' || ev.type === 'missed_shot' || ev.type === 'blocked_shot') {
          var p = ev.shooter_pos;
          if (!p || p.length < 2) return;
          var ti = teamIdx(ev, data);
          var mk = { x: +p[0], y: +p[1], team: ti, ev: ev, goal: false };
          chartMarkers.push(mk);
          if (ev.shooter) lastByShooter[String(ev.shooter)] = mk;
          nShots++;
        } else if (ev.type === 'goal') {
          nGoals++;
          var prev = ev.shooter ? lastByShooter[String(ev.shooter)] : null;
          if (prev) { prev.goal = true; prev.goalEv = ev; }
          else chartMarkers.push({ x: null, y: null, team: teamIdx(ev, data), ev: ev, goal: true });
        }
      });
      // draw markers
      chartMarkers.forEach(function (m) {
        if (m.x == null) return;
        m.px = m.x * sx; m.py = m.y * sy;
        var col = m.team === 0 ? '#3b82f6' : '#ef4444';
        ctx.beginPath();
        ctx.arc(m.px, m.py, m.goal ? 7 : 4.5, 0, Math.PI * 2);
        if (m.goal) {
          ctx.strokeStyle = '#ffd700'; ctx.lineWidth = 3; ctx.stroke();
          ctx.fillStyle = col; ctx.globalAlpha = 0.35; ctx.fill(); ctx.globalAlpha = 1;
        } else {
          ctx.fillStyle = col; ctx.globalAlpha = 0.85; ctx.fill(); ctx.globalAlpha = 1;
        }
      });
      setLegend(data, nShots, nGoals, chartMarkers.length);
      canvas.onclick = function (e) { chartClick(e, canvas); };
    }).catch(function () { drawEmpty(ctx, W, H, 'Could not load shot data.'); });
  }

  function setLegend(data, shots, goals, n) {
    var el = document.getElementById('chart-legend');
    el.innerHTML =
      '<div class="cl-row"><span class="cl-dot" style="background:#3b82f6"></span>' +
        esc(data.home_abbr || 'HOME') + ' shots</div>' +
      '<div class="cl-row"><span class="cl-dot" style="background:#ef4444"></span>' +
        esc(data.away_abbr || 'AWAY') + ' shots</div>' +
      '<div class="cl-row"><span class="cl-dot" style="border:2px solid #ffd700;background:transparent"></span>Goal</div>' +
      '<div class="cl-count">' + shots + ' shot attempts · ' + goals + ' goals</div>';
  }

  function chartClick(e, canvas) {
    var r = canvas.getBoundingClientRect();
    var mx = e.clientX - r.left, my = e.clientY - r.top;
    var best = null, bd = 14;
    chartMarkers.forEach(function (m) {
      if (m.x == null) return;
      var d = Math.hypot(m.px - mx, m.py - my);
      if (d < bd) { bd = d; best = m; }
    });
    var det = document.getElementById('chart-detail');
    if (!best) { det.innerHTML = '<div class="cd-empty">Click any shot marker for the play details.</div>'; return; }
    var ev = best.goalEv || best.ev;
    det.innerHTML =
      '<div class="cd-head">' + (best.goal ? '🚨 GOAL' : 'Shot attempt') + '</div>' +
      '<div class="cd-row"><span>Shooter</span><b>' + esc(ev.shooter || '?') + '</b></div>' +
      '<div class="cd-row"><span>Team</span><b>' + esc(ev.attacking_team || ev.scoring_team || '') + '</b></div>' +
      '<div class="cd-row"><span>When</span><b>' + esc(periodLabel(ev.period)) + ' ' + esc(fmtClock(ev.clock)) + '</b></div>' +
      (ev.shot_type ? '<div class="cd-row"><span>Shot</span><b>' + esc(String(ev.shot_type).replace(/_/g, ' ')) + '</b></div>' : '') +
      (ev.location ? '<div class="cd-row"><span>From</span><b>' + esc(String(ev.location).replace(/_/g, ' ')) + '</b></div>' : '') +
      (ev.distance != null ? '<div class="cd-row"><span>Distance</span><b>' + esc(Math.round(ev.distance)) + ' ft</b></div>' : '') +
      (ev.assists && ev.assists.length ? '<div class="cd-row"><span>Assists</span><b>' + esc(ev.assists.join(', ')) + '</b></div>' : '');
  }

  function drawEmpty(ctx, W, H, msg) {
    ctx.fillStyle = '#8b98b8'; ctx.font = '14px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(msg, W / 2, H / 2);
  }

  function drawRink(ctx, W, H) {
    var sx = W / RINK_L, sy = H / RINK_W;
    var X = function (x) { return x * sx; }, Y = function (y) { return y * sy; };
    // ice
    ctx.fillStyle = '#0a1424';
    roundRect(ctx, 0, 0, W, H, 18); ctx.fill();
    ctx.strokeStyle = '#e8edf5'; ctx.lineWidth = 2;
    // center red line + blue lines
    line(ctx, X(100), Y(0), X(100), Y(85), '#c8102e', 3);
    line(ctx, X(75), Y(0), X(75), Y(85), '#3b82f6', 3);
    line(ctx, X(125), Y(0), X(125), Y(85), '#3b82f6', 3);
    // goal lines + creases
    line(ctx, X(11), Y(0), X(11), Y(85), '#c8102e', 2);
    line(ctx, X(189), Y(0), X(189), Y(85), '#c8102e', 2);
    crease(ctx, X(11), Y(42.5), sx, 1); crease(ctx, X(189), Y(42.5), sx, -1);
    // faceoff dots/circles (neutral zone simplified)
    [[20, 22], [20, 63], [180, 22], [180, 63], [100, 22], [100, 63]].forEach(function (p) {
      ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 4, 0, Math.PI * 2);
      ctx.fillStyle = '#c8102e'; ctx.fill();
    });
    ctx.strokeStyle = 'rgba(232,237,245,.75)'; ctx.lineWidth = 1.5;
    [[69, 22], [69, 63], [131, 22], [131, 63]].forEach(function (p) {
      ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 15 * sx, 0, Math.PI * 2); ctx.stroke();
    });
    // boards
    ctx.strokeStyle = '#e8edf5'; ctx.lineWidth = 3;
    roundRect(ctx, 1.5, 1.5, W - 3, H - 3, 18); ctx.stroke();
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  function line(ctx, x1, y1, x2, y2, col, w) {
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
    ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke();
  }
  function crease(ctx, x, y, sx, dir) {
    ctx.beginPath();
    ctx.arc(x, y, 6 * sx, -Math.PI / 2, Math.PI / 2, dir < 0);
    ctx.fillStyle = 'rgba(59,130,246,.35)'; ctx.fill();
    ctx.strokeStyle = '#c8102e'; ctx.lineWidth = 1.5; ctx.stroke();
  }

  /* ---------- box score (full depth: Batch E) ---------- */
  function playerCell(r) {
    return '<span class="clickable-text" data-href="/player/' + esc(r.id) + '">' +
           esc(r.name) + '</span>';
  }

  /* Shared renderer: the live boxscore and the replay history payload
     share the same shape (skaters/goalies/scoring/lines/team_stats/stars). */
  function boxscoreHTML(data) {
    var hs = data.score.home, as = data.score.away;
    var per = data.period ? ' <span class="bs-per">P' + esc(data.period) + '</span>'
                          : (data.date ? ' <span class="bs-per">' + esc(data.date) + '</span>' : '');
    var note = '';
    if (data.shootout) note = ' <span class="bs-per">SO</span>';
    else if (data.overtime) note = ' <span class="bs-per">OT</span>';
    var html = '<div class="bs-head">' + esc(data.away_abbr) + ' ' + as + ' @ ' +
               esc(data.home_abbr) + ' ' + hs + per + note + '</div>';
    // 3 stars
    if (data.stars && data.stars.length) {
      var medals = ['1st', '2nd', '3rd'];
      html += '<div class="bs-stars">' + data.stars.map(function (s, i) {
        return '<span class="bs-star' + (i === 0 ? ' first' : '') + '">★ ' +
               esc(medals[i]) + ': ' + esc(s.name) +
               (s.team_name ? ' (' + esc(s.team_name) + ')' : '') + '</span>';
      }).join('') + '</div>';
    }
    // tabs
    html += '<div class="bs-tabs">' +
      ['scoring', 'players', 'lines', 'teams'].map(function (t, i) {
        var labels = { scoring: 'Scoring Summary', players: 'Player Stats', lines: 'Lines', teams: 'Team Stats' };
        return '<button class="bs-tab' + (i === 0 ? ' active' : '') + '" data-bstab="' + t + '">' + labels[t] + '</button>';
      }).join('') + '</div>';
    html += '<div class="bs-pane" data-bspane="scoring">' + scoringHTML(data) + '</div>';
    html += '<div class="bs-pane hidden" data-bspane="players">' + playersHTML(data) + '</div>';
    html += '<div class="bs-pane hidden" data-bspane="lines">' + linesHTML(data) + '</div>';
    html += '<div class="bs-pane hidden" data-bspane="teams">' + teamsHTML(data) + '</div>';
    return html;
  }

  function scoringHTML(data) {
    var list = data.scoring || [];
    if (!list.length) return '<div class="tl-empty">No scoring data yet.</div>';
    var lastP = null, html = '';
    list.forEach(function (g) {
      if (g.period !== lastP) {
        lastP = g.period;
        html += '<div class="bs-team">' + periodLabel(g.period) + '</div>';
      }
      var assists = (g.assists || []).join(', ');
      var sub = esc(g.clock || '');
      if (g.strength && g.strength !== 'EV') sub += ' · ' + esc(g.strength);
      if (g.goal_type) sub += ' · ' + esc(g.goal_type);
      if (g.empty_net) sub += ' · EN';
      html += '<div class="bs-goal"><div><b>' + esc(g.scorer) + '</b>' +
              (assists ? ' <span class="tl-dim">(' + esc(assists) + ')</span>' : ' <span class="tl-dim">(unassisted)</span>') +
              '<div class="tl-dim">' + sub + '</div></div>' +
              '<div class="bs-goal-score">' + esc(g.running || '') + '</div></div>';
    });
    return html;
  }

  function periodLabel(p) {
    p = Number(p) || 1;
    if (p <= 3) return 'Period ' + p;
    if (p === 4) return 'Overtime';
    return 'Shootout';
  }

  function playersHTML(data) {
    var html = '';
    [1, 0].forEach(function (ti) {
      var tname = ti === 0 ? data.home : data.away;
      var rows = (data.skaters || []).filter(function (r) { return r.team === ti; });
      var gs = (data.goalies || []).filter(function (r) { return r.team === ti; });
      html += '<div class="bs-team">' + esc(tname) + '</div>';
      html += '<table class="bs-table"><thead><tr><th>#</th><th>Player</th><th>Pos</th>' +
              '<th class="num">G</th><th class="num">A</th><th class="num">P</th>' +
              '<th class="num">SOG</th><th class="num">Hits</th>' +
              '<th class="num">Blk</th><th class="num">FO</th></tr></thead><tbody>' +
        rows.map(function (r) {
          return '<tr><td class="num">' + esc(r.jersey) + '</td>' +
            '<td>' + playerCell(r) + '</td><td>' + esc(r.pos || '') + '</td>' +
            '<td class="num">' + r.g + '</td><td class="num">' + r.a + '</td>' +
            '<td class="num bs-pts">' + r.pts + '</td><td class="num">' + r.sog + '</td>' +
            '<td class="num">' + r.hits + '</td><td class="num">' + (r.blk || 0) + '</td>' +
            '<td class="num">' + esc(r.fo || '0-0') + '</td></tr>';
        }).join('') + '</tbody></table>';
      if (gs.length) {
        html += '<table class="bs-table"><thead><tr><th>#</th><th>Goalie</th>' +
                '<th class="num">SA</th><th class="num">SV</th><th class="num">GA</th>' +
                '<th class="num">SV%</th></tr></thead><tbody>' +
          gs.map(function (r) {
            return '<tr><td class="num">' + esc(r.jersey) + '</td>' +
              '<td>' + playerCell(r) + '</td>' +
              '<td class="num">' + r.sa + '</td><td class="num">' + r.saves + '</td>' +
              '<td class="num">' + r.ga + '</td><td class="num">' + Number(r.sv_pct || 0).toFixed(3) + '</td></tr>';
          }).join('') + '</tbody></table>';
      }
    });
    return html;
  }

  function linesHTML(data) {
    var lines = data.lines || {};
    var html = '<div class="tl-dim" style="margin:6px 2px">5.0 = average game · 7.0+ = great · Key Stats shows what drove each grade.</div>';
    var any = false;
    [0, 1].forEach(function (ti) {
      var tname = ti === 0 ? data.home : data.away;
      var units = lines[String(ti)] || [];
      if (!units.length) return;
      any = true;
      html += '<div class="bs-team">' + esc(tname) + '</div>';
      units.forEach(function (L) {
        var rc = L.rating == null ? '' : (L.rating >= 7 ? 'g' : (L.rating >= 5.5 ? 'y' : 'r'));
        html += '<div class="bs-line-head"><span>' + esc(L.label) + '</span>' +
                '<span class="bs-grade ' + rc + '">Rating ' +
                (L.rating == null ? '—' : L.rating.toFixed(1)) + '</span></div>';
        html += '<table class="bs-table"><thead><tr><th>Player</th><th>Pos</th>' +
                '<th class="num">G</th><th class="num">A</th><th class="num">P</th>' +
                '<th class="num">Grade</th><th>Key Stats</th></tr></thead><tbody>' +
          (L.players || []).map(function (pl) {
            var gc = pl.grade == null ? '' : (pl.grade >= 7 ? 'g' : (pl.grade >= 5.5 ? 'y' : 'r'));
            return '<tr><td>' + esc(pl.name) + '</td><td>' + esc(pl.pos || '') + '</td>' +
              '<td class="num">' + pl.g + '</td><td class="num">' + pl.a + '</td>' +
              '<td class="num">' + pl.p + '</td>' +
              '<td class="num bs-grade ' + gc + '">' + (pl.grade == null ? '—' : pl.grade.toFixed(1)) + '</td>' +
              '<td class="tl-dim">' + esc(pl.why || '') + '</td></tr>';
          }).join('') + '</tbody></table>';
      });
    });
    if (!any) html += '<div class="tl-empty">Line data unavailable for this game.</div>';
    return html;
  }

  function teamsHTML(data) {
    var ts = data.team_stats || {};
    var rows = [
      ['Goals', 'goals'], ['Shots on Goal', 'shots'], ['Saves', 'saves'],
      ['Hits', 'hits'], ['Blocked Shots', 'blocks'], ['Faceoffs Won', 'fo_won'],
      ['Takeaways', 'takeaways'], ['Giveaways', 'giveaways'],
    ];
    var html = '<table class="bs-table"><thead><tr><th></th><th class="num">' +
               esc(data.away_abbr) + '</th><th class="num">' + esc(data.home_abbr) +
               '</th></tr></thead><tbody>' +
      rows.map(function (r) {
        var a = (ts['1'] || {})[r[1]], h = (ts['0'] || {})[r[1]];
        return '<tr><td>' + r[0] + '</td><td class="num">' + (a == null ? '—' : a) +
               '</td><td class="num">' + (h == null ? '—' : h) + '</td></tr>';
      }).join('');
    var pa = (ts['1'] || {}).pp, ph = (ts['0'] || {}).pp;
    if (pa != null || ph != null) {
      html += '<tr><td>Power Play</td><td class="num">' + esc(pa || '—') +
              '</td><td class="num">' + esc(ph || '—') + '</td></tr>';
    }
    return html + '</tbody></table>';
  }

  function wireBoxTabs(root) {
    var tabs = root.querySelectorAll('.bs-tab');
    tabs.forEach(function (t) {
      t.addEventListener('click', function () {
        tabs.forEach(function (x) { x.classList.toggle('active', x === t); });
        root.querySelectorAll('.bs-pane').forEach(function (p) {
          p.classList.toggle('hidden', p.dataset.bspane !== t.dataset.bstab);
        });
      });
    });
  }

  function renderBox() {
    var el = document.getElementById('boxscore');
    fetch('/api/watch/boxscore').then(function (r) { return r.json(); }).then(function (data) {
      if (!data.live || (!data.skaters.length && !data.goalies.length)) {
        el.innerHTML = '<div class="tl-empty">No live game right now — box score needs a live sim.</div>';
        return;
      }
      el.innerHTML = boxscoreHTML(data);
      wireBoxTabs(el);
    }).catch(function () {
      el.innerHTML = '<div class="tl-empty">Could not load the box score.</div>';
    });
  }

  // Exported for the replay page.
  window.PDBoxscore = { html: boxscoreHTML, wireTabs: wireBoxTabs };
})();
