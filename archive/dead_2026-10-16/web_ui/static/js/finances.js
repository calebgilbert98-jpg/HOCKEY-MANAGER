/* Puck Dynasty — finances screen: cap dashboard rendering */
(function () {
  "use strict";

  function money(v) {
    v = Number(v) || 0;
    var neg = v < 0;
    var a = Math.abs(v);
    var s;
    if (a >= 1e6) s = "$" + (a / 1e6).toFixed(1) + "M";
    else if (a >= 1e3) s = "$" + Math.round(a / 1e3) + "K";
    else s = "$" + Math.round(a);
    return (neg ? "-" : "") + s;
  }

  function pctOfCap(v, cap) {
    if (!cap) return "—";
    return ((Number(v) || 0) / cap * 100).toFixed(1) + "%";
  }

  function row(label, value, cls, note) {
    var d = document.createElement("div");
    d.className = "bd-row" + (cls ? " " + cls : "");
    var l = document.createElement("span");
    l.textContent = label;
    if (note) {
      var n = document.createElement("div");
      n.className = "bd-note";
      n.textContent = note;
      var wrap = document.createElement("div");
      wrap.appendChild(l); wrap.appendChild(n); l = wrap;
    }
    var r = document.createElement("span");
    r.className = "num"; r.textContent = money(value);
    d.appendChild(l); d.appendChild(r);
    return d;
  }

  function render(d) {
    document.getElementById("fin-team").textContent =
      (d.team ? d.team + " — " : "") + "salary cap & budget";

    // --- hero ---
    var status = d.status || "comfortable";
    var statusEl = document.getElementById("fin-status");
    var labels = {
      comfortable: "● Comfortable — cap room available",
      tight: "● Tight — very little cap room",
      over: "● Over the cap — action required",
      under_floor: "● Under the cap floor — action required"
    };
    statusEl.textContent = labels[status] || labels.comfortable;
    statusEl.className = "fin-status " + (status === "under_floor" ? "over" : status);

    var payrollEl = document.getElementById("fin-payroll");
    payrollEl.textContent = money(d.total);
    document.getElementById("fin-cap").textContent = money(d.cap);

    var spaceEl = document.getElementById("fin-space");
    spaceEl.textContent = (d.space < 0 ? "" : "+") + money(d.space);
    spaceEl.className = "fin-value big " + (status === "under_floor" ? "over" : status);

    // gauge: payroll vs cap, floor marker
    var gauge = document.getElementById("fin-gauge");
    var pct = d.cap ? Math.min(100, Math.max(0, d.total / d.cap * 100)) : 0;
    gauge.style.width = pct.toFixed(1) + "%";
    gauge.className = "gauge-fill " + (status === "under_floor" ? "over" : status);

    var floorMark = document.getElementById("fin-floor-mark");
    floorMark.style.left = (d.cap ? (d.floor / d.cap * 100).toFixed(1) : 0) + "%";
    floorMark.title = "Cap floor " + money(d.floor);

    document.getElementById("fin-gauge-label").textContent =
      money(d.total) + " payroll · " + pctOfCap(d.total, d.cap) + " of cap";
    document.getElementById("fin-floor-label").textContent =
      d.under_floor
        ? "⚠ Below the floor — " + money(Math.abs(d.total - d.floor)) + " short"
        : money(d.total - d.floor) + " above the floor";

    // --- breakdown ---
    var bd = document.getElementById("fin-breakdown");
    bd.innerHTML = "";
    bd.appendChild(row("Active roster cap charge", d.roster_charge));
    var b = d.breakdown || {};
    var comps = [
      ["buyouts", "Buyouts", ""],
      ["seeded_buyout", "Buyouts (seeded)", ""],
      ["retained", "Retained salary", "slots used: " + (b.retention_slots || "0/3")],
      ["seeded_retained", "Retained (seeded)", ""],
      ["seeded_overage", "Performance-bonus overage (seeded)", ""]
    ];
    comps.forEach(function (c) {
      var v = Number(b[c[0]]) || 0;
      if (v !== 0) bd.appendChild(row(c[1], v, "dead", c[2] || null));
    });
    var buried = Number(b.buried) || 0;
    if (buried !== 0) {
      bd.appendChild(row("Buried one-way money (AHL)", buried, "",
        "informational — already included in roster charge"));
    }
    if (d.dead_cap) bd.appendChild(row("Total dead cap", d.dead_cap, "dead"));
    bd.appendChild(row("Total cap charge", d.total, "total"));

    // --- owner budget ---
    var ob = d.owner_budget || {};
    var leftEl = document.getElementById("fin-budget-left");
    leftEl.textContent = money(ob.remaining);
    leftEl.className = "fin-value big " + ((ob.remaining || 0) < 0 ? "over" : "comfortable");
    var bg = document.getElementById("fin-budget-gauge");
    bg.style.width = (ob.budget
      ? Math.min(100, Math.max(0, (ob.remaining / ob.budget) * 100)) : 0).toFixed(1) + "%";
    document.getElementById("fin-budget-spent").textContent =
      money(ob.spent) + " spent on bonuses";
    document.getElementById("fin-budget-total").textContent =
      money(ob.remaining) + " of " + money(ob.budget) + " remaining";

    // --- top cap hits ---
    var tb = document.getElementById("fin-hits");
    tb.innerHTML = "";
    (d.top_hits || []).forEach(function (h, i) {
      var tr = document.createElement("tr");
      var cells = [i + 1, h.name, h.position, h.age, h.overall,
        money(h.salary), pctOfCap(h.salary, d.cap)];
      cells.forEach(function (c, j) {
        var td = document.createElement("td");
        td.textContent = c;
        if (j >= 5) td.className = "num";
        tr.appendChild(td);
      });
      if (h.injured) {
        var badge = document.createElement("span");
        badge.className = "inj"; badge.textContent = "IR";
        tr.cells[1].appendChild(badge);
      }
      tb.appendChild(tr);
    });
    if (!d.top_hits || !d.top_hits.length) {
      var tr = document.createElement("tr");
      var td = document.createElement("td");
      td.colSpan = 7; td.textContent = "No roster data available.";
      tr.appendChild(td); tb.appendChild(tr);
    }
  }

  /* Buyout calculator ------------------------------------------------- */
  var BO_CANDIDATES = [];
  var BO_SELECTED = null;

  function boMoney(v) {
    v = Math.round(Number(v) || 0);
    return "$" + v.toLocaleString("en-US");
  }

  function loadBuyouts() {
    fetch("/api/finances/buyouts")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        BO_CANDIDATES = d.candidates || [];
        renderBuyoutList();
        var w = d.window || {};
        var note = document.getElementById("buyout-window-note");
        note.textContent = w.ok ? "(window open: Jun 15–30)" :
          (w.reason ? "(" + w.reason + ")" : "");
        var act = document.getElementById("buyout-active");
        var rows = d.active_buyouts || [];
        act.innerHTML = rows.length
          ? rows.map(function (r) { return "<span>" + r.year + ": " + boMoney(r.hit) + "</span>"; }).join(" · ")
          : "No active buyouts.";
      })
      .catch(function () { /* calculator is optional */ });
  }

  function renderBuyoutList() {
    var list = document.getElementById("buyout-list");
    list.innerHTML = "";
    if (!BO_CANDIDATES.length) {
      list.innerHTML = "<p class='fin-note'>No buyout candidates (no remaining term on the roster).</p>";
      return;
    }
    BO_CANDIDATES.forEach(function (c) {
      var el = document.createElement("div");
      el.className = "buyout-row" + (BO_SELECTED && BO_SELECTED.id === c.id ? " sel" : "");
      var warn = (c.nmc || c.ntc) ? " <span class='buyout-block' title='NMC/NTC blocks buyouts without consent'>" + (c.nmc ? "NMC" : "NTC") + "</span>" : "";
      el.innerHTML = "<div class='buyout-name'>" + esc(c.name) + warn + "</div>" +
        "<div class='buyout-sub'>" + esc(c.position) + " · Age " + c.age + " · " +
        boMoney(c.cap_hit) + "/yr × " + c.years_left + " left</div>";
      el.addEventListener("click", function () {
        BO_SELECTED = c;
        renderBuyoutList();
        renderBuyoutDetail();
      });
      list.appendChild(el);
    });
  }

  function renderBuyoutDetail() {
    var det = document.getElementById("buyout-detail");
    var c = BO_SELECTED;
    if (!c) {
      det.innerHTML = "<p class='fin-note'>Select a player to see their buyout breakdown.</p>";
      return;
    }
    var blocked = (c.nmc || c.ntc);
    var sched = (c.schedule || []).map(function (r) {
      var txt = r.savings >= 0
        ? "saves " + boMoney(r.savings)
        : "dead money " + boMoney(-r.savings);
      return "<div class='buyout-sched-row'>Year " + r.year + ": " + boMoney(r.cap_hit) + " cap hit — " + txt + "</div>";
    }).join("");
    det.innerHTML =
      "<div class='buyout-name big'>" + esc(c.name) + "</div>" +
      "<div class='buyout-sub'>Age " + c.age + " · " + esc(c.position) + " · " +
      boMoney(c.cap_hit) + "/yr × " + c.years_left + " yr</div>" +
      "<div class='buyout-total'>Buyout cost: " + boMoney(c.buyout_cost) + "</div>" +
      "<div class='buyout-sub'>Cap hit: " + boMoney(c.annual_dead) + "/yr for " + c.dead_years + " years</div>" +
      "<div class='buyout-sched'>" + sched + "</div>" +
      (blocked
        ? "<p class='buyout-block-note'>⚠️ " + (c.nmc ? "No-movement" : "No-trade") +
          " clause — buyout blocked without the player's consent.</p>"
        : "<button class='btn danger' id='buyout-exec'>Execute Buyout</button>") +
      "<div class='buyout-result' id='buyout-result'></div>";
    if (!blocked) {
      document.getElementById("buyout-exec").addEventListener("click", executeBuyout);
    }
  }

  function executeBuyout() {
    var c = BO_SELECTED;
    if (!c) return;
    if (!confirm("Buy out " + c.name + "? He becomes a free agent. Cost: " + boMoney(c.buyout_cost) +
        " spread as " + boMoney(c.annual_dead) + "/yr over " + c.dead_years + " years.")) return;
    document.getElementById("buyout-result").textContent = "Processing…";
    fetch("/api/finances/buyouts/execute", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({player_id: c.id})
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        document.getElementById("buyout-result").textContent =
          d.ok ? "✔ Buyout executed — " + c.name + " is now a free agent." : "✘ " + (d.error || "Buyout failed.");
        if (d.ok) {
          BO_SELECTED = null;
          loadBuyouts();
        }
      })
      .catch(function () {
        document.getElementById("buyout-result").textContent = "✘ Request failed.";
      });
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>\"]/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;"}[c];
    });
  }

  loadBuyouts();

  fetch("/api/finances")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.error) {
        document.getElementById("fin-status").textContent = "● " + d.error;
        return;
      }
      render(d);
    })
    .catch(function () {
      document.getElementById("fin-status").textContent = "● Failed to load finances";
    });
})();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

/* ==================================================================
 * Batch D: FinancesWindow parity tabs — Projections, Reports,
 * Management, Contracts, Cap Position (+ AHL payroll).
 * The existing cap dashboard above stays the default tab.
 * ================================================================== */
(function () {
  "use strict";

  function money(v) {
    v = Number(v) || 0;
    var neg = v < 0;
    var a = Math.abs(v);
    var s;
    if (a >= 1e6) s = "$" + (a / 1e6).toFixed(1) + "M";
    else if (a >= 1e3) s = "$" + Math.round(a / 1e3) + "K";
    else s = "$" + Math.round(a);
    return (neg ? "-" : "") + s;
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  }
  var STATUS_CLS = {
    "signed": "st-signed", "extension_candidate": "st-ext",
    "expiring": "st-exp", "ufa": "st-ufa", "rfa": "st-rfa",
    "entry-level": "st-elc", "long-term": "st-lt", "overpaid": "st-over"
  };

  /* ---- tab switching ---- */
  var LOADED = {};
  document.getElementById("fin-tabs").addEventListener("click", function (e) {
    var b = e.target.closest(".fin-tab");
    if (!b) return;
    document.querySelectorAll("#fin-tabs .fin-tab").forEach(function (t) {
      t.classList.remove("active");
    });
    b.classList.add("active");
    document.querySelectorAll(".fin-tab-panel").forEach(function (p) {
      p.hidden = true;
    });
    document.getElementById("fin-tab-" + b.dataset.tab).hidden = false;
    var tab = b.dataset.tab;
    if (!LOADED[tab]) {
      LOADED[tab] = true;
      if (tab === "projections") loadProjections();
      if (tab === "reports") loadReports();
      if (tab === "management") loadManagement();
      if (tab === "contracts") loadContracts();
      if (tab === "cap") loadCapPosition();
    }
  });

  /* ---- Projections: year picker + committed vs expiring ---- */
  async function loadProjections() {
    var sel = document.getElementById("proj-year");
    try {
      // Prime the picker from the current projection payload (season).
      var r0 = await fetch("/api/finances/projections");
      var d0 = await r0.json();
      var season = d0.season || new Date().getFullYear();
      sel.innerHTML = "";
      for (var y = season; y <= season + 7; y++) {
        var o = document.createElement("option");
        o.value = y; o.textContent = y + "-" + String(y + 1).slice(2);
        sel.appendChild(o);
      }
      sel.value = String(season);
      sel.addEventListener("change", refreshProjections);
      await refreshProjections();
    } catch (e) { console.error(e); }
  }
  async function refreshProjections() {
    var year = document.getElementById("proj-year").value;
    try {
      var res = await fetch("/api/finances/projections?year=" + encodeURIComponent(year));
      var d = await res.json();
      document.getElementById("proj-committed").textContent = money(d.committed_payroll);
      document.getElementById("proj-cap").textContent = money(d.projected_cap);
      var sp = document.getElementById("proj-space");
      sp.textContent = (d.projected_space < 0 ? "" : "+") + money(d.projected_space);
      sp.className = "fin-value big " + (d.projected_space < 0 ? "over" : "comfortable");
      document.getElementById("proj-expiring-count").textContent =
        "(" + (d.expiring_count || 0) + " expiring before then)";
      var tb = document.getElementById("proj-expiring");
      tb.innerHTML = "";
      for (var i = 0; i < (d.expiring || []).length; i++) {
        var p = d.expiring[i];
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + (p.id
            ? '<span class="clickable-text" data-href="/player/' + esc(p.id) + '">' + esc(p.name) + "</span>"
            : esc(p.name)) + "</td>" +
          "<td>" + esc(p.position) + "</td>" +
          "<td>" + esc(p.age) + "</td>" +
          "<td><span class=\"st-badge " + (STATUS_CLS[p.status] || "") + "\">" + esc(p.status) + "</span></td>" +
          "<td class=\"num\">" + money(p.salary) + "</td>" +
          "<td class=\"num\">" + money(p.estimated_ask) + "</td>";
        tb.appendChild(tr);
      }
      if (!(d.expiring || []).length)
        tb.innerHTML = '<tr><td colspan="6" class="empty-note">Everyone is signed through ' + esc(year) + ".</td></tr>";
    } catch (e) { console.error(e); }
  }

  /* ---- Reports: the 5 desktop financial reports ---- */
  async function loadReports() {
    var sel = document.getElementById("report-select");
    try {
      var res = await fetch("/api/finances/reports");
      var d = await res.json();
      sel.innerHTML = "";
      (d.reports || []).forEach(function (r) {
        var o = document.createElement("option");
        o.value = r.key; o.textContent = r.label;
        sel.appendChild(o);
      });
      sel.addEventListener("change", refreshReport);
      await refreshReport();
    } catch (e) { console.error(e); }
  }
  async function refreshReport() {
    var key = document.getElementById("report-select").value;
    var host = document.getElementById("report-body");
    host.innerHTML = '<div class="empty-note">Loading report…</div>';
    try {
      var res = await fetch("/api/finances/reports?report=" + encodeURIComponent(key));
      var d = await res.json();
      host.innerHTML = renderReport(d.data || {});
    } catch (e) {
      host.innerHTML = '<div class="empty-note">Could not load the report.</div>';
    }
  }
  function renderReport(data) {
    // Generic renderer: title + optional summary rows + table + notes.
    var html = "";
    if (data.title) html += '<div class="bpanel-sub-h">' + esc(data.title) + "</div>";
    if (data.summary && data.summary.length) {
      html += '<div class="rep-summary">';
      data.summary.forEach(function (s) {
        html += '<div class="bd-row"><span>' + esc(s[0]) + '</span><span class="num">' +
          (typeof s[1] === "number" ? money(s[1]) : esc(s[1])) + "</span></div>";
      });
      html += "</div>";
    }
    if (data.columns && data.rows) {
      html += '<table class="fin-table"><thead><tr>' +
        data.columns.map(function (c) {
          return "<th" + (c.num ? ' class="num"' : "") + ">" + esc(c.label || c) + "</th>";
        }).join("") + "</tr></thead><tbody>";
      data.rows.forEach(function (r) {
        html += "<tr>" + r.map(function (cell, i) {
          var num = data.columns[i] && data.columns[i].num;
          return '<td class="' + (num ? "num" : "") + '">' +
            (num && typeof cell === "number" ? money(cell) : esc(cell)) + "</td>";
        }).join("") + "</tr>";
      });
      html += "</tbody></table>";
    }
    if (data.notes && data.notes.length) {
      html += '<div class="rep-notes">' + data.notes.map(function (n) {
        return "<div>• " + esc(n) + "</div>";
      }).join("") + "</div>";
    }
    return html || '<div class="empty-note">This report returned no data.</div>';
  }

  /* ---- Management: recommendations + quick actions ---- */
  async function loadManagement() {
    var host = document.getElementById("mgmt-list");
    host.innerHTML = '<div class="empty-note">Loading recommendations…</div>';
    try {
      var res = await fetch("/api/finances/management");
      var d = await res.json();
      host.innerHTML = "";
      var head = document.createElement("div");
      head.className = "fin-hero-mini";
      head.innerHTML =
        '<div class="fin-number"><span class="fin-label">Payroll</span><span class="fin-value">' + money(d.payroll) + '</span></div>' +
        '<div class="fin-number"><span class="fin-label">Utilization</span><span class="fin-value">' + esc(d.utilization_pct) + '%</span></div>' +
        '<div class="fin-number"><span class="fin-label">Cap space</span><span class="fin-value big">' + (d.space < 0 ? "" : "+") + money(d.space) + "</span></div>";
      host.appendChild(head);
      (d.recommendations || []).forEach(function (r) {
        var el = document.createElement("div");
        el.className = "rec-row lvl-" + esc(r.level || "info");
        el.innerHTML = '<span class="rec-dot"></span><span>' + esc(r.text) + "</span>";
        host.appendChild(el);
      });
      var actWrap = document.createElement("div");
      actWrap.className = "mgmt-actions";
      (d.quick_actions || []).forEach(function (a) {
        var b = document.createElement("button");
        b.className = "btn-ghost";
        b.textContent = a.label;
        b.disabled = !a.enabled;
        b.addEventListener("click", function () {
          if (a.route) { window.location.href = a.route; return; }
          b.disabled = true;
          fetch("/api/command", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({op: a.op})
          }).then(function (r) { return r.json(); })
            .then(function (dd) {
              alert(dd.ok ? "Queued: " + a.label : "Could not queue the action.");
            }).catch(function () {
              alert("Could not queue the action.");
            }).finally(function () { b.disabled = !a.enabled; });
        });
        actWrap.appendChild(b);
      });
      host.appendChild(actWrap);
    } catch (e) {
      host.innerHTML = '<div class="empty-note">Could not load recommendations.</div>';
    }
  }

  /* ---- Contracts: filters + status labels + clause badges ---- */
  var CTR = {pos: "", status: "", q: ""};
  async function loadContracts() {
    document.getElementById("ctr-pos").addEventListener("change", function (e) {
      CTR.pos = e.target.value; refreshContracts();
    });
    document.getElementById("ctr-status").addEventListener("change", function (e) {
      CTR.status = e.target.value; refreshContracts();
    });
    document.getElementById("ctr-q").addEventListener("input", function (e) {
      CTR.q = e.target.value; refreshContracts();
    });
    await refreshContracts();
  }
  async function refreshContracts() {
    var params = new URLSearchParams();
    if (CTR.pos) params.set("pos", CTR.pos);
    if (CTR.status) params.set("filter", CTR.status);
    if (CTR.q) params.set("q", CTR.q);
    var tb = document.getElementById("ctr-rows");
    try {
      var res = await fetch("/api/finances/contracts?" + params.toString());
      var d = await res.json();
      // Populate the status filter once from the backend's filter list.
      var sel = document.getElementById("ctr-status");
      if (!sel.options.length || sel.options.length === 1) {
        sel.innerHTML = '<option value="">All</option>' +
          (d.filters || []).filter(function (f) { return f !== "all"; }).map(function (f) {
            return '<option value="' + esc(f) + '">' + esc(f) + "</option>";
          }).join("");
        sel.value = CTR.status;
      }
      tb.innerHTML = "";
      for (var i = 0; i < (d.contracts || []).length; i++) {
        var c = d.contracts[i];
        var badges = "";
        if (c.no_trade) badges += ' <span class="st-badge st-ntc">NTC</span>';
        if (c.no_movement) badges += ' <span class="st-badge st-nmc">NMC</span>';
        if (c.two_way) badges += ' <span class="st-badge st-2w">2-way</span>';
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + (c.id
            ? '<span class="clickable-text" data-href="/player/' + esc(c.id) + '">' + esc(c.name) + "</span>" + badges
            : esc(c.name) + badges) + "</td>" +
          "<td>" + esc(c.position) + "</td>" +
          "<td>" + esc(c.age) + "</td>" +
          "<td><span class=\"st-badge " + (STATUS_CLS[c.status] || "") + "\">" + esc(c.status) + "</span></td>" +
          "<td class=\"num\">" + money(c.salary) + "</td>" +
          "<td class=\"num\">" + esc(c.years_left) + "</td>" +
          "<td class=\"num\">" + money(c.estimated_ask) + "</td>";
        tb.appendChild(tr);
      }
      if (!(d.contracts || []).length)
        tb.innerHTML = '<tr><td colspan="7" class="empty-note">No contracts match these filters.</td></tr>';
    } catch (e) { console.error(e); }
  }

  /* ---- Cap position breakdown + AHL payroll ---- */
  async function loadCapPosition() {
    try {
      var res = await fetch("/api/finances/cap_position");
      var d = await res.json();
      var host = document.getElementById("cap-breakdown");
      host.innerHTML = "";
      var posd = d.position_breakdown || {};
      Object.keys(posd).forEach(function (k) {
        var v = posd[k] || {};
        var el = document.createElement("div");
        el.className = "bd-row";
        el.innerHTML = "<span>" + esc(k) + " (" + esc(v.count) + " players)</span>" +
          '<span class="num">' + money(v.total) +
          ' <small class="fin-note">avg ' + money(v.avg) + "</small></span>";
        host.appendChild(el);
      });
      var ahl = d.ahl || {};
      document.getElementById("cap-ahl").innerHTML =
        '<div class="bd-row"><span>AHL roster size</span><span class="num">' + esc(ahl.count) + " players</span></div>" +
        '<div class="bd-row"><span>AHL payroll</span><span class="num">' + money(ahl.payroll) + "</span></div>" +
        '<div class="bd-row"><span>Bury threshold</span><span class="num">' + money(ahl.bury_threshold) + "</span></div>" +
        '<div class="bd-row"><span>Buried salary (counts vs cap)</span><span class="num">' + money(ahl.buried_salary) + "</span></div>";
    } catch (e) { console.error(e); }
  }

  // Clickable player names navigate (shared pattern; the base finances
  // IIFE does not own these rows).
  document.addEventListener("click", function (e) {
    if (e.target.closest("button, a, input, select")) return;
    var t = e.target.closest(".clickable-text[data-href]");
    if (t) window.location.href = t.dataset.href;
  });
})();
