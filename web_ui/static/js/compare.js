/* Compare Players page — search/add players, render side-by-side table
   with winner highlighting per row. */
(function () {
  'use strict';

  var MAX = 4;
  var playerIds = [];
  var activeSlot = -1;
  var searchTimer = null;

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c];
    });
  }

  function barColor(v) {
    if (v >= 75) return '#4CAF50';
    if (v >= 60) return '#8BC34A';
    if (v >= 45) return '#FFC107';
    if (v >= 30) return '#FF9800';
    return '#F44336';
  }

  /* ---------- slots ---------- */
  function renderSlots(playersById) {
    var host = $('cmp-slots');
    var html = '';
    for (var i = 0; i < MAX; i++) {
      var pid = playerIds[i];
      if (pid && playersById[pid]) {
        var p = playersById[pid];
        html += '<div class="cmp-slot filled" data-slot="' + i + '">' +
          (p.portrait ? '<img src="' + esc(p.portrait) + '" alt="" onerror="this.remove()">' : '') +
          '<span class="s-name">' + esc(p.name) + '</span>' +
          '<span class="s-team">' + esc(p.team) + ' · ' + esc(p.position) + '</span>' +
          '<button class="s-x" data-remove="' + i + '">Remove</button></div>';
      } else {
        html += '<div class="cmp-slot" data-slot="' + i + '"><span style="font-size:22px">+</span><span>Add player</span></div>';
      }
    }
    host.innerHTML = html;
  }

  /* ---------- search ---------- */
  function openSearch(slot) {
    activeSlot = slot;
    var wrap = $('cmp-search-wrap');
    wrap.hidden = false;
    var input = $('cmp-search');
    input.value = '';
    $('cmp-results').innerHTML = '';
    input.focus();
    input.oninput = function () {
      clearTimeout(searchTimer);
      var q = input.value.trim();
      if (q.length < 2) { $('cmp-results').innerHTML = ''; return; }
      searchTimer = setTimeout(function () { runSearch(q); }, 220);
    };
  }

  function runSearch(q) {
    fetch('/api/compare/search?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var res = d.results || [];
        if (!res.length) {
          $('cmp-results').innerHTML = '<div class="cmp-result"><span class="r-name">No matches</span></div>';
          return;
        }
        $('cmp-results').innerHTML = res.map(function (r) {
          var already = playerIds.indexOf(String(r.id)) !== -1;
          return '<div class="cmp-result" data-pid="' + esc(r.id) + '"' +
            (already ? ' style="opacity:.4;pointer-events:none"' : '') + '>' +
            (r.portrait ? '<img src="' + esc(r.portrait) + '" alt="" onerror="this.remove()">' : '') +
            '<span class="r-name">' + esc(r.name) + '</span>' +
            '<span class="r-meta">' + esc(r.team) + ' · ' + esc(r.position) + '</span>' +
            '<span class="r-ovr">' + r.overall + ' OVR</span></div>';
        }).join('');
      })
      .catch(function () { $('cmp-results').innerHTML = ''; });
  }

  /* ---------- data + table ---------- */
  function loadComparison() {
    if (playerIds.length < 2) {
      $('cmp-empty').hidden = false;
      $('cmp-table-wrap').hidden = true;
      renderSlots({});
      syncUrl();
      return;
    }
    $('cmp-empty').hidden = true;
    fetch('/api/compare?ids=' + playerIds.map(encodeURIComponent).join(','))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var players = d.players || [];
        var byId = {};
        players.forEach(function (p) { byId[String(p.id)] = p; });
        // drop ids that no longer resolve
        playerIds = players.map(function (p) { return String(p.id); });
        renderSlots(byId);
        renderTable(players);
        $('cmp-table-wrap').hidden = false;
        syncUrl();
      })
      .catch(function (e) { console.error(e); });
  }

  function syncUrl() {
    var u = new URL(window.location.href);
    ['p1', 'p2', 'p3', 'p4'].forEach(function (k) { u.searchParams.delete(k); });
    playerIds.forEach(function (id, i) { u.searchParams.set('p' + (i + 1), id); });
    window.history.replaceState(null, '', u.toString());
  }

  function sectionRow(label, ncols) {
    return '<tr class="cmp-section"><th class="rowlabel">' + esc(label) + '</th>' +
      new Array(ncols).fill('<td></td>').join('') + '</tr>';
  }

  // Row spec: {label, get(p) -> {display, numval|null, bar:bool, higherBetter:bool}}
  function dataRow(label, players, get) {
    var cells = players.map(function (p) {
      var c = get(p) || {};
      var disp = (c.display == null || c.display === '') ? '—' : c.display;
      var inner;
      if (c.bar && typeof c.numval === 'number') {
        var v = Math.max(0, Math.min(100, Math.round(c.numval)));
        inner = '<span class="attr-cell"><span class="attr-bar"><span class="fill" style="width:' +
          v + '%;background:' + barColor(v) + '"></span></span>' +
          '<span class="attr-val">' + v + '</span></span>';
      } else {
        inner = esc(disp);
      }
      return { html: '<td>' + inner + '</td>', numval: (typeof c.numval === 'number' ? c.numval : null),
               higherBetter: c.higherBetter !== false };
    });
    // winner highlighting
    var vals = cells.map(function (c) { return c.numval; }).filter(function (v) { return v !== null; });
    var cls = cells.map(function () { return ''; });
    if (vals.length >= 2) {
      var hb = cells[0].higherBetter;
      var best = hb ? Math.max.apply(null, vals) : Math.min.apply(null, vals);
      var worst = hb ? Math.min.apply(null, vals) : Math.max.apply(null, vals);
      if (best !== worst) {
        cells.forEach(function (c, i) {
          if (c.numval === best) cls[i] = 'win';
          else if (c.numval === worst) cls[i] = 'lose';
        });
      }
    }
    var tds = cells.map(function (c, i) {
      return c.html.replace('<td>', '<td' + (cls[i] ? ' class="' + cls[i] + '"' : '') + '>');
    }).join('');
    return '<tr><th class="rowlabel">' + esc(label) + '</th>' + tds + '</tr>';
  }

  function statGetter(row) {
    return function (p) {
      var s = (p.stats || []).concat(p.contract || []).find(function (r) { return r.key === row; });
      if (!s) return { display: '—' };
      var nv = (typeof s.numval === 'number') ? s.numval : null;
      if (nv === null && s.num) { var n = Number(s.value); nv = isNaN(n) ? null : n; }
      return { display: s.value, numval: nv, higherBetter: s.higher_better !== false };
    };
  }

  function attrGetter(label) {
    return function (p) {
      var found = null;
      (p.attr_groups || []).forEach(function (g) {
        (g.rows || []).forEach(function (r) {
          if (r.label === label) found = r;
        });
      });
      if (!found) return { display: '—' };
      return { display: found.value, numval: found.value, bar: true, higherBetter: true };
    };
  }

  function renderTable(players) {
    var n = players.length;
    // header
    $('cmp-thead').innerHTML = '<tr><th class="rowlabel"></th>' + players.map(function (p) {
      return '<th><div class="cmp-phead">' +
        (p.portrait ? '<img src="' + esc(p.portrait) + '" alt="" onerror="this.remove()">' : '') +
        '<div class="ph-name"><a href="/player/' + esc(p.id) + '">' + esc(p.name) + '</a></div>' +
        '<div class="ph-meta">' + esc(p.team) + ' · ' + esc(p.position) + ' · Age ' + p.age + '</div>' +
        '<div><span class="ph-ovr">' + p.overall + ' OVR</span></div>' +
        '</div></th>';
    }).join('') + '</tr>';

    var html = '';
    // stat rows: union of keys, skaters and goalies interleaved sensibly
    var statOrder = ['GP', 'G', 'A', 'PTS', '+/-', 'PIM', 'HIT', 'BLK', 'SOG',
                     'W', 'SV%', 'GAA', 'SO', 'SA'];
    var statLabels = {};
    players.forEach(function (p) {
      (p.stats || []).forEach(function (s) { statLabels[s.key] = s.label; });
    });
    html += sectionRow('Season Stats', n);
    statOrder.forEach(function (key) {
      if (!statLabels[key]) return;
      // only show rows relevant to at least one compared player
      html += dataRow(statLabels[key], players, statGetter(key));
    });
    // contract
    html += sectionRow('Contract', n);
    html += dataRow('Cap Hit', players, statGetter('CAPHIT'));
    html += dataRow('Term Remaining', players, statGetter('TERM'));

    // attributes: union of labels per group, in profile order
    var groups = [];
    players.forEach(function (p) {
      (p.attr_groups || []).forEach(function (g) {
        var ex = groups.find(function (x) { return x.name === g.name; });
        if (!ex) { groups.push({ name: g.name, labels: [] }); ex = groups[groups.length - 1]; }
        (g.rows || []).forEach(function (r) {
          if (ex.labels.indexOf(r.label) === -1) ex.labels.push(r.label);
        });
      });
    });
    groups.forEach(function (g) {
      html += sectionRow(g.name + ' Attributes', n);
      g.labels.forEach(function (label) {
        html += dataRow(label, players, attrGetter(label));
      });
    });

    $('cmp-tbody').innerHTML = html;
  }

  /* ---------- events ---------- */
  document.addEventListener('click', function (e) {
    var rm = e.target.closest('[data-remove]');
    if (rm) {
      e.stopPropagation();
      playerIds.splice(parseInt(rm.getAttribute('data-remove'), 10), 1);
      $('cmp-search-wrap').hidden = true;
      loadComparison();
      return;
    }
    var res = e.target.closest('.cmp-result[data-pid]');
    if (res) {
      var pid = res.getAttribute('data-pid');
      if (activeSlot >= 0 && playerIds.length < MAX && playerIds.indexOf(pid) === -1) {
        if (activeSlot < playerIds.length) playerIds[activeSlot] = pid;
        else playerIds.push(pid);
      }
      $('cmp-search-wrap').hidden = true;
      loadComparison();
      return;
    }
    var slot = e.target.closest('.cmp-slot[data-slot]');
    if (slot && !slot.classList.contains('filled')) {
      openSearch(parseInt(slot.getAttribute('data-slot'), 10));
      return;
    }
    // click outside search closes it
    if (!e.target.closest('#cmp-search-wrap') && !e.target.closest('.cmp-slot')) {
      $('cmp-search-wrap').hidden = true;
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') $('cmp-search-wrap').hidden = true;
  });

  // shared heartbeat
  (function () {
    var beat = function () { fetch('/api/heartbeat', { method: 'POST' }).catch(function () {}); };
    beat();
    setInterval(beat, 30000);
  })();

  /* ---------- init from URL ---------- */
  (function init() {
    var u = new URL(window.location.href);
    ['p1', 'p2', 'p3', 'p4'].forEach(function (k) {
      var v = (u.searchParams.get(k) || '').trim();
      if (v && playerIds.length < MAX && playerIds.indexOf(v) === -1) playerIds.push(v);
    });
    loadComparison();
  })();
})();
