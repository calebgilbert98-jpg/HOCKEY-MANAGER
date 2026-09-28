"""Analytics Hub (module 04): give the simulation's depth a surface.

The engine already models the details -- this module makes them visible:

- xG model: the sim's own per-shot expected-goal value (shot location,
  shot type, chance quality, distance, tactics) aggregated per player,
  per line, and per team.
- Momentum graphs: the tracked momentum stream rendered post-game.
- Zone-entry maps: every successful entry, plotted where it happened.
- Line-level trends: rolling xG and chemistry per forward line.
- Ask the analyst: generated, evidence-based reports -- a diagnosis,
  not an answer key. Analytics should create a puzzle, not solve it.

The player-card Analytics tabs are preserved untouched; the hub is a
separate surface for diagnosing tactics, not decorating box scores.
"""

from collections import Counter, defaultdict


MAX_GAMES = 10

# Value labels for the sim's momentum values ("heavily_favoring_home" etc).
_MOMENTUM_VALUE = {
    "heavily_favoring_home": 3,
    "favoring_home": 2,
    "slightly_favoring_home": 1,
    "neutral": 0,
    "slightly_favoring_away": -1,
    "favoring_away": -2,
    "heavily_favoring_away": -3,
}


# ---------------------------------------------------------------------------
# Game records
# ---------------------------------------------------------------------------

def team_games(team):
    """Recent per-game analytics records, oldest first (max 10)."""
    try:
        games = list(getattr(team, "analytics_games", None) or [])
    except Exception:
        games = []
    return games[-MAX_GAMES:]


def latest_game(team):
    games = team_games(team)
    return games[-1] if games else None


def game_label(rec, team_name=""):
    """Short label like 'vs TOR · Mar 4 · 3-2 W'."""
    try:
        home, away = rec.get("home", ""), rec.get("away", "")
        hs, aws = rec.get("score", (0, 0))
        if team_name and team_name == home:
            opp, us, them = away, hs, aws
            tag = "vs"
        elif team_name and team_name == away:
            opp, us, them = home, aws, hs
            tag = "@"
        else:
            opp, us, them, tag = away, hs, aws, ""
        result = "W" if us > them else "L" if us < them else "T"
        date = (rec.get("date") or "").strip()
        bits = [f"{tag} {opp}".strip(), f"{us}-{them} {result}"]
        if date:
            bits.insert(1, date)
        return " · ".join(bits)
    except Exception:
        return "game"


def shots_for(rec, team_name):
    try:
        return [s for s in rec.get("shots", [])
                if s.get("team") == team_name]
    except Exception:
        return []


def entries_for(rec, team_name):
    try:
        return [e for e in rec.get("entries", [])
                if e.get("team") == team_name]
    except Exception:
        return []


def momentum_points(rec, team_name=""):
    """Momentum stream as (period, time, value) with value signed for
    the viewed team (positive = their momentum)."""
    pts = []
    try:
        home = rec.get("home", "")
        flip = -1 if (team_name and team_name != home) else 1
        for m in rec.get("momentum", []):
            raw = m.get("momentum", "neutral")
            val = _MOMENTUM_VALUE.get(str(raw), 0)
            pts.append({
                "period": int(m.get("period", 1) or 1),
                "time": float(m.get("time", 0) or 0),
                "value": val * flip,
                "trigger": str(m.get("trigger", "")),
            })
    except Exception:
        pass
    return pts


# ---------------------------------------------------------------------------
# xG aggregation (the engine's own per-shot model, summed up)
# ---------------------------------------------------------------------------

def team_xg(shots):
    xg = sum(float(s.get("xg", 0) or 0) for s in shots)
    goals = sum(1 for s in shots if s.get("outcome") == "goal")
    return round(xg, 2), goals


def player_xg_rows(shots):
    """Per-shooter: shots, xG, goals, goals-minus-xG. Sorted by xG."""
    agg = defaultdict(lambda: {"shots": 0, "xg": 0.0, "goals": 0})
    for s in shots:
        a = agg[s.get("shooter", "?")]
        a["shots"] += 1
        a["xg"] += float(s.get("xg", 0) or 0)
        if s.get("outcome") == "goal":
            a["goals"] += 1
    rows = [{"shooter": k, "shots": v["shots"],
             "xg": round(v["xg"], 2), "goals": v["goals"],
             "diff": round(v["goals"] - v["xg"], 2)}
            for k, v in agg.items()]
    rows.sort(key=lambda r: (-r["xg"], -r["shots"]))
    return rows


def line_xg_rows(shots, line_chem=None):
    """Per forward line: shots, xG, goals, latest chemistry."""
    agg = defaultdict(lambda: {"shots": 0, "xg": 0.0, "goals": 0})
    for s in shots:
        a = agg[s.get("line", "-")]
        a["shots"] += 1
        a["xg"] += float(s.get("xg", 0) or 0)
        if s.get("outcome") == "goal":
            a["goals"] += 1
    chem = line_chem or {}
    rows = [{"line": k, "shots": v["shots"],
             "xg": round(v["xg"], 2), "goals": v["goals"],
             "diff": round(v["goals"] - v["xg"], 2),
             "chemistry": (chem.get(k) or {}).get("chemistry", "-")}
            for k, v in agg.items() if k != "-"]
    order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3}
    rows.sort(key=lambda r: order.get(r["line"], 9))
    return rows


def rolling_line_trends(team, n=5):
    """Per-line xG across the last n games: {line: [(label, xg), ...]}."""
    trends = defaultdict(list)
    for rec in team_games(team)[-n:]:
        name = getattr(team, "team_name", "")
        lx = line_xg_rows(shots_for(rec, name))
        have = {r["line"]: r["xg"] for r in lx}
        for line in ("L1", "L2", "L3", "L4"):
            trends[line].append((game_label(rec, name), have.get(line, 0.0)))
    return dict(trends)


def entry_breakdown(entries):
    counts = Counter(e.get("type", "?") for e in entries)
    total = sum(counts.values())
    controlled = sum(c for t, c in counts.items()
                     if "CONTROLLED" in str(t).upper()
                     or "CARRY" in str(t).upper())
    return {
        "counts": dict(counts),
        "total": total,
        "controlled": controlled,
        "controlled_pct": round(100.0 * controlled / total, 1)
        if total else 0.0,
    }


# ---------------------------------------------------------------------------
# Ask the analyst: generated, evidence-based, uncertainty-aware
# ---------------------------------------------------------------------------

def analyst_report(team):
    """Return [(heading, [lines])] grounded in the team's game records.

    A diagnosis, not an answer key: observations plus open questions.
    """
    games = team_games(team)
    name = getattr(team, "team_name", "")
    if not games:
        return [("No data yet",
                 ["Play a game and the analyst will have something "
                  "to work with."])]

    recent = games[-5:]
    shots = [s for g in recent for s in shots_for(g, name)]
    entries = [e for g in recent for e in entries_for(g, name)]

    sections = []

    # -- Finishing vs chance creation -------------------------------------
    xg = sum(float(s.get("xg", 0) or 0) for s in shots)
    goals = sum(1 for s in shots if s.get("outcome") == "goal")
    diff = goals - xg
    lines = [
        f"Last {len(recent)} games: {goals} goals on {xg:.1f} expected "
        f"({len(shots)} shots).",
    ]
    if diff <= -1.5:
        lines.append("The chances are there; the finish isn't. That's "
                     "usually shooting luck, not the system -- it tends "
                     "to even out.")
    elif diff >= 1.5:
        lines.append("Outscoring the chances. Enjoy it, but don't budget "
                     "on it -- the model says this pace is borrowed.")
    else:
        lines.append("Finishing is tracking the chances. What you see is "
                     "roughly what the chances deserved.")
    if shots:
        lines.append(f"Average chance quality: {xg / len(shots):.3f} xG "
                     "per shot.")
    sections.append(("Finishing vs. chance creation", lines))

    # -- Shot quality ------------------------------------------------------
    if shots:
        hd = sum(1 for s in shots if float(s.get("xg", 0) or 0) >= 0.12)
        lines = [
            f"High-danger share: {hd}/{len(shots)} shots "
            f"({100.0 * hd / len(shots):.0f}%).",
        ]
        if hd / len(shots) < 0.25:
            lines.append("A lot of perimeter looks. If the shot map "
                         "shows everything from outside, the issue is "
                         "chance quality, not the shooters.")
        else:
            lines.append("Getting to the dangerous ice. If the goals "
                         "still aren't coming, that's a finishing "
                         "question, not a systems one.")
        sections.append(("Shot quality", lines))

    # -- Momentum ----------------------------------------------------------
    lg = latest_game(team)
    pts = momentum_points(lg, name) if lg else []
    if pts:
        vals = [p["value"] for p in pts]
        swing = max(vals) - min(vals)
        talk_driven = sum(1 for p in pts
                          if "talk" in p["trigger"].lower()
                          or "dressing" in p["trigger"].lower())
        lines = [
            f"Biggest swing last game: {swing:+d} momentum steps.",
            f"Momentum shifts tracked: {len(pts)}.",
        ]
        if talk_driven:
            lines.append(f"{talk_driven} shift(s) followed a team talk -- "
                         "the room is listening, for better or worse.")
        if swing >= 4:
            lines.append("A rollercoaster. When the game tilts this far, "
                         "look at what started the slide -- the trigger "
                         "log on the Momentum tab names it.")
        sections.append(("Momentum", lines))

    # -- Zone entries ------------------------------------------------------
    eb = entry_breakdown(entries)
    if eb["total"]:
        lines = [
            f"Controlled entries: {eb['controlled']}/{eb['total']} "
            f"({eb['controlled_pct']:.0f}%).",
        ]
        if eb["controlled_pct"] < 40:
            lines.append("The breakout is leaking -- most entries are "
                         "dump-ins. Controlled entries are where the "
                         "xG comes from; check whether the breakout "
                         "tactic actually favors carrying it in.")
        else:
            lines.append("Winning the blue line. If the xG still lags, "
                         "the problem starts after the entry, not "
                         "before it.")
        sections.append(("Zone entries", lines))

    # -- Lines -------------------------------------------------------------
    if lg:
        lx = line_xg_rows(shots_for(lg, name), lg.get("lines"))
        if lx:
            best = max(lx, key=lambda r: r["xg"])
            worst = min(lx, key=lambda r: r["xg"])
            lines = [
                f"Last game xG by line: " +
                ", ".join(f"{r['line']} {r['xg']:.1f}" for r in lx) + ".",
                f"{best['line']} drove play "
                f"({best['xg']:.1f} xG, chemistry {best['chemistry']}).",
            ]
            if worst["xg"] < best["xg"] / 2 and len(lx) > 1:
                lines.append(f"{worst['line']} is a passenger right now "
                             f"({worst['xg']:.1f} xG). Matchup problem, "
                             "chemistry problem, or just one game?")
            sections.append(("Lines", lines))

    # -- Open questions ----------------------------------------------------
    pr = player_xg_rows(shots)
    if pr:
        hot = pr[0]
        cold = [r for r in pr
                if r["shots"] >= 5 and r["diff"] <= -1.0]
        lines = []
        if cold:
            c = cold[0]
            lines.append(f"{c['shooter']}: {c['goals']} goals on "
                         f"{c['xg']:.1f} xG ({c['shots']} shots). "
                         "Slump or decline? The shot map is the tiebreak.")
        lines.append(f"{hot['shooter']} is generating the most "
                     f"({hot['xg']:.1f} xG). Ride that line while it's "
                     "hot -- or sell high? Your call.")
        sections.append(("What to watch", lines))

    return sections


# ---------------------------------------------------------------------------
# AnalyticsHubView -- the dedicated screen
# ---------------------------------------------------------------------------

class AnalyticsHubView(__import__("customtkinter").CTkFrame):
    """Analytics Hub: shot/xG maps, momentum graphs, zone entries, line
    trends, and Ask the Analyst. The player-card Analytics tabs are
    preserved untouched -- this is the tactics-diagnosis surface."""

    TABS = ["Shots & xG", "Momentum", "Zone Entries", "Lines",
            "Ask the Analyst"]

    def __init__(self, parent, app=None):
        import customtkinter as ctk
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading,
            body, TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER, TEXT,
            TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE, ROW_HOVER,
            ROW_SELECTED,
        )
        self._ctk = ctk
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()

        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self.configure(fg_color=BG)

        self._team = getattr(self.app, "user_team", None)
        self._games = team_games(self._team)
        self._game_idx = len(self._games) - 1
        self._tab = "Shots & xG"
        self._tab_btns = {}

        self._build_header()
        self._build_tabs()
        self._content = ctk.CTkScrollableFrame(self, fg_color=BG)
        self._content.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._render()

    # -- frame -------------------------------------------------------------
    def _build_header(self):
        ctk = self._ctk
        ct = self._ct
        bar = ctk.CTkFrame(self, fg_color=ct["PANEL"], corner_radius=0)
        bar.pack(fill="x")
        self._heading(bar, "Analytics Hub").pack(side="left", padx=16,
                                                 pady=10)
        name = getattr(self._team, "team_name", "?")
        self._body(bar, f"{name} · last {len(self._games)} games",
                   text_color=ct["TEXT_DIM"]).pack(side="left", padx=4)

        if self._games:
            labels = [game_label(g, name) for g in self._games]
            self._game_var = ctk.StringVar(value=labels[self._game_idx])
            menu = ctk.CTkOptionMenu(
                bar, values=labels, variable=self._game_var,
                command=self._on_game,
                fg_color=ct["CARD"], button_color=ct["TEAL"],
                button_hover_color=ct["TEAL_HOVER"])
            menu.pack(side="right", padx=16, pady=10)

    def _on_game(self, label):
        name = getattr(self._team, "team_name", "")
        for i, g in enumerate(self._games):
            if game_label(g, name) == label:
                self._game_idx = i
                break
        self._render()

    def _build_tabs(self):
        ctk = self._ctk
        ct = self._ct
        row = ctk.CTkFrame(self, fg_color=ct["BG"])
        row.pack(fill="x", padx=12, pady=(8, 0))
        for tab in self.TABS:
            btn = ctk.CTkButton(
                row, text=tab, width=130, height=30,
                fg_color=ct["TEAL"] if tab == self._tab else ct["CARD"],
                hover_color=ct["TEAL_HOVER"],
                text_color="white" if tab == self._tab else ct["TEXT"],
                command=lambda t=tab: self._switch_tab(t))
            btn.pack(side="left", padx=(0, 8))
            self._tab_btns[tab] = btn

    def _switch_tab(self, tab):
        ctk = self._ctk
        ct = self._ct
        self._tab = tab
        for t, b in self._tab_btns.items():
            b.configure(fg_color=ct["TEAL"] if t == tab else ct["CARD"],
                        text_color="white" if t == tab else ct["TEXT"])
        self._render()

    def _render(self):
        for w in self._content.winfo_children():
            w.destroy()
        if not self._games:
            self._body(self._content,
                       "No games recorded yet. Play a game and the hub "
                       "will light up.",
                       text_color=self._ct["TEXT_DIM"]).pack(pady=40)
            return
        {"Shots & xG": self._render_shots,
         "Momentum": self._render_momentum,
         "Zone Entries": self._render_entries,
         "Lines": self._render_lines,
         "Ask the Analyst": self._render_analyst}[self._tab]()

    def _game(self):
        return self._games[self._game_idx]

    def _team_name(self):
        return getattr(self._team, "team_name", "")

    # -- small helpers ------------------------------------------------------
    def _card(self, title):
        ctk = self._ctk
        ct = self._ct
        card = ctk.CTkFrame(self._content, fg_color=ct["CARD"],
                            corner_radius=8)
        card.pack(fill="x", padx=4, pady=6)
        self._heading(card, title).pack(anchor="w", padx=14, pady=(10, 2))
        return card

    def _table(self, parent, headers, rows, widths=None):
        ctk = self._ctk
        ct = self._ct
        widths = widths or [110] * len(headers)
        for j, h in enumerate(headers):
            self._body(parent, h, text_color=ct["TEXT_FAINT"]).grid(
                row=0, column=j, padx=6, pady=2, sticky="w")
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                self._body(parent, str(v)).grid(
                    row=i + 1, column=j, padx=6, pady=1, sticky="w")

    def _rink_xform(self, canvas, x0, x1):
        W = int(canvas["width"])
        H = int(canvas["height"])
        pad = 14
        def f(x, y):
            cx = pad + (x - x0) / (x1 - x0) * (W - 2 * pad)
            cy = pad + y / 85.0 * (H - 2 * pad)
            return cx, cy
        return f

    def _draw_rink(self, cv, x0=100.0, x1=200.0, ice="#1d2b33"):
        ct = self._ct
        f = self._rink_xform(cv, x0, x1)
        W = int(cv["width"])
        H = int(cv["height"])
        cv.create_rectangle(4, 4, W - 4, H - 4, fill=ice,
                            outline=ct["BORDER"], width=2)
        # red line / blue line / goal line
        for x, color in ((100.0, "#c0392b"), (125.0, "#2980b9"),
                         (189.0, "#c0392b")):
            if x0 <= x <= x1:
                ax, ay = f(x, 0)
                _, by = f(x, 85)
                cv.create_line(ax, ay, ax, by, fill=color, width=3)
        # faceoff circles (attacking zone)
        for cy0 in (20.5, 64.5):
            ax, ay = f(169, cy0)
            r = 15 / (x1 - x0) * (W - 28)
            cv.create_oval(ax - r, ay - r, ax + r, ay + r,
                           outline="#7f8c8d", width=1)
            cv.create_oval(ax - 2, ay - 2, ax + 2, ay + 2,
                           fill="#7f8c8d", outline="")
        # crease + net
        if x1 >= 189:
            ax, ay = f(189, 42.5)
            r = 6 / (x1 - x0) * (W - 28)
            cv.create_arc(ax - r, ay - r, ax + r, ay + r, start=270,
                          extent=180, fill="#3d6b8c", outline="")
            nx, _ = f(190.5, 42.5)
            cv.create_rectangle(nx - 3, ay - 8, nx + 3, ay + 8,
                                fill="#c0392b", outline="")
        return f

    # -- Shots & xG ----------------------------------------------------------
    def _render_shots(self):
        ctk = self._ctk
        ct = self._ct
        rec = self._game()
        name = self._team_name()
        shots = shots_for(rec, name)
        xg, goals = team_xg(shots)

        card = self._card(f"Shot map · {game_label(rec, name)}")
        self._body(card, f"{len(shots)} shots · {xg:.2f} xG · {goals} goals", text_color=ct["TEXT_DIM"]).pack(anchor="w",
                                                    padx=14, pady=(0, 6))
        cv = ctk.CTkCanvas(card, width=880, height=340, bg="#1d2b33",
                           highlightthickness=0)
        cv.pack(padx=14, pady=(0, 6))
        f = self._draw_rink(cv, 100.0, 200.0)
        colors = {"goal": ct["GREEN"], "save": ct["BLUE"],
                  "blocked": "#7f8c8d", "disallowed": "#f1c40f",
                  "pending": "#ecf0f1"}
        for s in shots:
            cx, cy = f(s.get("x", 160), s.get("y", 42.5))
            r = 3 + float(s.get("xg", 0) or 0) * 14
            col = colors.get(s.get("outcome"), "#ecf0f1")
            if s.get("outcome") == "disallowed":
                cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                               outline=col, width=2)
            else:
                cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                               fill=col, outline="")
            if s.get("outcome") == "goal":
                cv.create_oval(cx - r - 2, cy - r - 2, cx + r + 2,
                               cy + r + 2, outline=ct["GOLD"], width=2)
        legend = ctk.CTkFrame(card, fg_color="transparent")
        legend.pack(anchor="w", padx=14, pady=(0, 10))
        for label, col in (("Goal", ct["GREEN"]), ("Save", ct["BLUE"]),
                           ("Blocked", "#7f8c8d"),
                           ("Disallowed", "#f1c40f")):
            self._body(legend, f"● {label}", text_color=col).pack(side="left",
                                                             padx=(0, 12))
        self._body(card, "Dot size = chance quality (xG). All shots shown "
                   "attacking right.",
                   text_color=ct["TEXT_FAINT"]).pack(anchor="w", padx=14,
                                                pady=(0, 10))

        card2 = self._card("Chance creation by player (engine xG)")
        rows = player_xg_rows(shots)
        inner = ctk.CTkFrame(card2, fg_color="transparent")
        inner.pack(anchor="w", padx=14, pady=(0, 10))
        self._table(inner, ["Player", "Shots", "xG", "Goals", "G-xG"],
                    [[r["shooter"], r["shots"], f"{r['xg']:.2f}",
                      r["goals"], f"{r['diff']:+.2f}"] for r in rows[:14]])

    # -- Momentum -------------------------------------------------------------
    def _render_momentum(self):
        ctk = self._ctk
        ct = self._ct
        rec = self._game()
        name = self._team_name()
        pts = momentum_points(rec, name)

        card = self._card(f"Momentum · {game_label(rec, name)}")
        if not pts:
            self._body(card, "No momentum shifts tracked this game.",
                       text_color=ct["TEXT_DIM"]).pack(padx=14, pady=10)
            return
        self._body(card, "Positive = your momentum. Ticks mark what moved it.", text_color=ct["TEXT_DIM"]).pack(anchor="w", padx=14,
                                                    pady=(0, 6))
        W, H = 880, 300
        cv = ctk.CTkCanvas(card, width=W, height=H, bg="#1d2b33",
                           highlightthickness=0)
        cv.pack(padx=14, pady=(0, 6))
        pad, mid = 30, H // 2
        step = H / 2 / 3.4
        cv.create_line(pad, mid, W - pad, mid, fill=ct["BORDER"], width=1)
        n = len(pts)
        xs = [pad + i / max(n - 1, 1) * (W - 2 * pad) for i in range(n)]
        ys = [mid - p["value"] * step for p in pts]
        prev_period = pts[0]["period"]
        for i in range(1, n):
            if pts[i]["period"] != prev_period:
                cv.create_line(xs[i], 10, xs[i], H - 10, fill="#3a4a55",
                               dash=(4, 4))
                cv.create_text(xs[i] + 4, 14, text=f"P{pts[i]['period']}",
                               fill=ct["TEXT_FAINT"], anchor="w",
                               font=("", 9))
                prev_period = pts[i]["period"]
        for i in range(1, n):
            col = ct["GREEN"] if ys[i] <= mid else ct["RED"]
            cv.create_line(xs[i - 1], ys[i - 1], xs[i], ys[i], fill=col,
                           width=2)
        for i, p in enumerate(pts):
            col = ct["GREEN"] if p["value"] >= 0 else ct["RED"]
            cv.create_oval(xs[i] - 3, ys[i] - 3, xs[i] + 3, ys[i] + 3,
                           fill=col, outline="")
        # annotate the biggest swing
        swings = sorted(range(1, n),
                        key=lambda i: abs(ys[i] - ys[i - 1]),
                        reverse=True)[:3]
        for i in swings:
            trig = pts[i]["trigger"].replace("_", " ")
            if trig:
                cv.create_text(xs[i], max(ys[i] - 14, 12), text=trig,
                               fill=ct["TEXT_FAINT"], font=("", 9))
        vals = [p["value"] for p in pts]
        card2 = self._card("Game flow")
        self._body(card2, f"Shifts tracked: {n} · biggest swing: "
                   f"{max(vals) - min(vals):+d} steps · finished "
                   f"{vals[-1]:+d}.",
                   text_color=ct["TEXT_DIM"]).pack(anchor="w", padx=14,
                                              pady=(0, 10))

    # -- Zone entries -----------------------------------------------------------
    def _render_entries(self):
        ctk = self._ctk
        ct = self._ct
        rec = self._game()
        name = self._team_name()
        entries = entries_for(rec, name)
        eb = entry_breakdown(entries)

        card = self._card(f"Zone entries · {game_label(rec, name)}")
        self._body(card, f"{eb['total']} successful entries · "
                   f"{eb['controlled_pct']:.0f}% controlled", text_color=ct["TEXT_DIM"]).pack(anchor="w", padx=14,
                                                    pady=(0, 6))
        cv = ctk.CTkCanvas(card, width=880, height=340, bg="#1d2b33",
                           highlightthickness=0)
        cv.pack(padx=14, pady=(0, 6))
        f = self._draw_rink(cv, 0.0, 200.0)
        tcolors = {"CONTROLLED_CARRY": ct["GREEN"], "DUMP_IN": "#e67e22",
                   "CONTROLLED_PASS": ct["BLUE"]}
        for e in entries:
            cx, cy = f(e.get("x", 125), e.get("y", 42.5))
            col = tcolors.get(str(e.get("type")), "#7f8c8d")
            cv.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=col,
                           outline="")
        legend = ctk.CTkFrame(card, fg_color="transparent")
        legend.pack(anchor="w", padx=14, pady=(0, 10))
        for label, col in (("Carry-in", ct["GREEN"]),
                           ("Dump-in", "#e67e22"),
                           ("Pass entry", ct["BLUE"])):
            self._body(legend, f"● {label}", text_color=col).pack(side="left",
                                                             padx=(0, 12))
        if eb["counts"]:
            card2 = self._card("Entry mix")
            inner = ctk.CTkFrame(card2, fg_color="transparent")
            inner.pack(anchor="w", padx=14, pady=(0, 10))
            self._table(inner, ["Type", "Count"],
                        [[t.replace("_", " ").title(), c]
                         for t, c in sorted(eb["counts"].items(),
                                            key=lambda kv: -kv[1])])

    # -- Lines --------------------------------------------------------------------
    def _render_lines(self):
        ctk = self._ctk
        ct = self._ct
        rec = self._game()
        name = self._team_name()
        shots = shots_for(rec, name)
        rows = line_xg_rows(shots, rec.get("lines"))

        card = self._card(f"Line trends · {game_label(rec, name)}")
        if not rows:
            self._body(card, "No line data this game.",
                       text_color=ct["TEXT_DIM"]).pack(padx=14, pady=10)
        else:
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(anchor="w", padx=14, pady=(0, 6))
            self._table(inner, ["Line", "Shots", "xG", "Goals", "G-xG",
                                "Chemistry"],
                        [[r["line"], r["shots"], f"{r['xg']:.2f}",
                          r["goals"], f"{r['diff']:+.2f}",
                          r["chemistry"]] for r in rows])
            self._body(card, "Chemistry is the engine's live line-chemistry "
                       "rating for this game.",
                       text_color=ct["TEXT_FAINT"]).pack(anchor="w", padx=14,
                                                    pady=(0, 10))

        trends = rolling_line_trends(self._team, n=5)
        card2 = self._card("Rolling xG by line (last 5 games)")
        inner2 = ctk.CTkFrame(card2, fg_color="transparent")
        inner2.pack(fill="x", padx=14, pady=(0, 10))
        games5 = team_games(self._team)[-5:]
        labels = [game_label(g, name) for g in games5]
        self._table(inner2, ["Line"] + [l.split(" · ")[0] for l in labels],
                    [[line] + [f"{xg:.1f}" for _, xg in trends[line]]
                     for line in ("L1", "L2", "L3", "L4")
                     if line in trends])

    # -- Ask the analyst ------------------------------------------------------------
    def _render_analyst(self):
        ct = self._ct
        for heading_text, lines in analyst_report(self._team):
            card = self._card(heading_text)
            for ln in lines:
                self._body(card, "•  " + ln,
                           text_color=ct["TEXT"]).pack(anchor="w", padx=14,
                                                  pady=2)
            self._ctk.CTkFrame(card, fg_color="transparent",
                               height=8).pack()
