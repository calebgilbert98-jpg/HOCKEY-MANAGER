/* Puck Dynasty — completed-game replay (Batch E, 2026-10-06).
 *
 * Ports GAME_VIEWER.py's viewing modes (Watch All / Highlights / Text)
 * for finished games: pick a past game, replay its stored play-by-play
 * with an All/Highlights filter, jump between big moments with the
 * "Next Big Moment" button (pbp_visual_sim parity), and drill into the
 * full-depth box score (scoring, players, lines grades, team stats).
 */
(function () {
'use strict';

var sel = document.getElementById('replay-select');
var main = document.getElementById('replay-main');
var feed = document.getElementById('replay-feed');
var boxEl = document.getElementById('replay-boxscore');
var bug = document.getElementById('replay-scorebug');

var events = [];
var mode = 'all';       // all | highlights | text
var cursor = 0;         // next-big-moment cursor (index into events)
var meta = {};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}

function fmtTs(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0');
}

function periodLabel(p) {
  p = Number(p) || 1;
  if (p <= 3) return 'P' + p;
  if (p === 4) return 'OT';
  return 'SO';
}

/* GAME_VIEWER._is_highlight parity: goals, high-danger saves, majors. */
function isHighlight(e) {
  var t = String(e.type || '').toUpperCase();
  if (t.indexOf('GOAL') >= 0) return true;
  if (t.indexOf('SAVE') >= 0) return String(e.shot_quality || '').toLowerCase() === 'high';
  if (t.indexOf('PENALTY') >= 0) return Number(e.minutes || 0) >= 5;
  return false;
}

/* pbp_visual_sim BIG_MOMENTS parity. */
var BIG = { GOAL_ADVANCED: 1, GOAL: 1, PENALTY: 1, FIGHT: 1, PENALTY_SHOT: 1 };
function isBig(e) {
  var t = String(e.type || '').toUpperCase();
  for (var k in BIG) if (t.indexOf(k) >= 0) return true;
  return false;
}

function eventLine(e) {
  var t = String(e.type || '').toUpperCase();
  var pre = '<span class="tl-meta">' + esc(periodLabel(e.period)) + ' ' + esc(fmtTs(e.timestamp)) + '</span> ';
  var desc = e.desc ? esc(e.desc) : null;
  if (t.indexOf('GOAL') >= 0) {
    var a = (e.assist_ids && e.assist_ids.length)
      ? ' <span class="tl-dim">(assists: ' + esc(e.assist_ids.join(', ')) + ')</span>' : '';
    var who = e.scorer_id ? '<b>' + esc(e.scorer_id) + '</b>' : (desc || 'Goal');
    return pre + '<span class="tl-goal">🚨 GOAL — ' + who + a + '</span>';
  }
  if (t.indexOf('PENALTY_SHOT') >= 0)
    return pre + '<span class="tl-big">Penalty shot — <b>' + esc(e.player_id || '?') + '</b>.</span>';
  if (t.indexOf('PENALTY') >= 0)
    return pre + '<span class="tl-pen">Penalty — <b>' + esc(e.player_id || '?') +
           '</b> (' + (e.minutes || 2) + ' min).</span>';
  if (t.indexOf('FIGHT') >= 0) return pre + '<span class="tl-big">🥊 Fight!</span>';
  if (t.indexOf('SAVE') >= 0)
    return pre + 'Save — <b>' + esc(e.goaltender_id || '?') + '</b>' +
           (e.shot_quality ? ' <span class="tl-dim">(' + esc(e.shot_quality) + ' danger)</span>' : '') + '.';
  if (t.indexOf('SHOT') >= 0)
    return pre + 'Shot — <b>' + esc(e.shooter_id || '?') + '</b>.';
  if (t.indexOf('HIT') >= 0) return pre + 'Hit — <b>' + esc(e.hitting_player_id || '?') +
           '</b> on <b>' + esc(e.target_player_id || '?') + '</b>.';
  if (t.indexOf('FACEOFF') >= 0) return pre + '<span class="tl-dim">Faceoff.</span>';
  if (t.indexOf('PERIOD_START') >= 0) return pre + 'Start of period ' + esc(e.period) + '.';
  if (t.indexOf('PERIOD_END') >= 0) return pre + 'End of period ' + esc(e.period) + '.';
  if (desc) return pre + desc;
  return pre + '<span class="tl-dim">' + esc(String(e.type || '').replace(/_/g, ' ')) + '.</span>';
}

function renderFeed() {
  var list = events.filter(function (e) {
    return mode !== 'highlights' || isHighlight(e);
  });
  if (!list.length) {
    feed.innerHTML = '<div class="tl-empty">No events in this view.</div>';
    return;
  }
  if (mode === 'text') {
    feed.innerHTML = list.map(function (e, i) {
      return '<div class="rp-line" data-i="' + i + '">' + eventLine(e) + '</div>';
    }).join('');
  } else {
    feed.innerHTML = list.map(function (e, i) {
      var big = isBig(e) ? ' rp-big' : '';
      return '<div class="rp-event' + big + '" data-i="' + i + '">' + eventLine(e) + '</div>';
    }).join('');
  }
  feed.scrollTop = feed.scrollHeight;
}

/* Next Big Moment: jump the feed to the next goal/penalty/fight. */
function nextMoment() {
  if (!events.length) return;
  var list = events.filter(function (e) {
    return mode !== 'highlights' || isHighlight(e);
  });
  var start = Math.min(cursor, list.length - 1);
  for (var i = start; i < list.length; i++) {
    if (isBig(list[i])) {
      cursor = i + 1;
      var el = feed.querySelector('[data-i="' + i + '"]');
      if (el) {
        el.scrollIntoView({ block: 'center' });
        el.classList.add('rp-flash');
        setTimeout(function () { el.classList.remove('rp-flash'); }, 1600);
      } else {
        feed.scrollTop = feed.scrollHeight;
      }
      return;
    }
  }
  cursor = 0;
  toast('No more big moments — replay restarts from the top.');
}

function toast(msg) {
  var t = document.createElement('div');
  t.className = 'mp-toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function () { t.classList.add('show'); }, 30);
  setTimeout(function () { t.classList.remove('show'); setTimeout(function () { t.remove(); }, 400); }, 2200);
}

function loadGame(idx) {
  if (idx === '') { main.classList.add('hidden'); return; }
  main.classList.remove('hidden');
  feed.innerHTML = '<div class="tl-empty">Loading play-by-play…</div>';
  boxEl.innerHTML = '<div class="tl-empty">Loading box score…</div>';
  fetch('/api/watch/replay_events?idx=' + encodeURIComponent(idx))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d.ok) { feed.innerHTML = '<div class="tl-empty">Could not load.</div>'; return; }
      meta = d;
      events = d.events || [];
      cursor = 0;
      bug.innerHTML = '<span class="sb-team">' + esc(d.away_abbr || d.away) + '</span>' +
        '<span class="sb-score">' + d.away_score + '</span>' +
        '<span class="sb-mid"><span class="sb-period">FINAL</span></span>' +
        '<span class="sb-score">' + d.home_score + '</span>' +
        '<span class="sb-team">' + esc(d.home_abbr || d.home) + '</span>';
      renderFeed();
    }).catch(function () {
      feed.innerHTML = '<div class="tl-empty">Could not load the event log.</div>';
    });
  fetch('/api/watch/boxscore_history?idx=' + encodeURIComponent(idx))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d.ok) { boxEl.innerHTML = '<div class="tl-empty">No box score.</div>'; return; }
      boxEl.innerHTML = window.PDBoxscore.html(d);
      window.PDBoxscore.wireTabs(boxEl);
    }).catch(function () {
      boxEl.innerHTML = '<div class="tl-empty">Could not load the box score.</div>';
    });
}

document.querySelectorAll('.rm-tab[data-rmode]').forEach(function (t) {
  t.addEventListener('click', function () {
    mode = t.dataset.rmode;
    cursor = 0;
    document.querySelectorAll('.rm-tab[data-rmode]').forEach(function (x) {
      x.classList.toggle('active', x === t);
    });
    renderFeed();
  });
});
document.getElementById('btn-next-moment').addEventListener('click', nextMoment);
sel.addEventListener('change', function () { loadGame(sel.value); });

/* picker */
fetch('/api/watch/past_games').then(function (r) { return r.json(); }).then(function (d) {
  (d.games || []).forEach(function (g) {
    var o = document.createElement('option');
    o.value = g.idx;
    var tag = g.shootout ? ' (SO)' : (g.overtime ? ' (OT)' : '');
    o.textContent = g.date + ' — ' + g.away + ' ' + g.away_score + ' @ ' +
                    g.home + ' ' + g.home_score + tag;
    sel.appendChild(o);
  });
  if ((d.games || []).length) {
    sel.value = d.games[0].idx;
    loadGame(sel.value);
  } else {
    sel.innerHTML = '<option value="">No completed games yet</option>';
  }
}).catch(function () {});

/* deep link: /replay?idx=N */
try {
  var qi = new URLSearchParams(window.location.search).get('idx');
  if (qi) {
    var iv = setInterval(function () {
      if (sel.options.length > 1) {
        clearInterval(iv);
        sel.value = qi;
        loadGame(qi);
      }
    }, 300);
    setTimeout(function () { clearInterval(iv); }, 5000);
  }
} catch (e) {}
})();
