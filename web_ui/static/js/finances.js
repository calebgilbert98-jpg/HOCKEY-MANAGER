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
