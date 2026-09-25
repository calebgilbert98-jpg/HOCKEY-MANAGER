"""
Visual play-by-play match simulator for Puck Dynasty.

Eastside-style live game view: a canvas-drawn rink with player bubbles that
skate in real time, driven by events emitted from the sim engine
(GameSim.pbp_listeners — see simulation.py `_emit_pbp`).

Playback model: the full game sims in a background thread (~0.1s) while the
UI plays the recorded event stream back on a game-clock-paced timer, so
Play/Pause, 1x/2x/4x speed and Sim-to-End all work naturally.

Entry point: open_pbp_window(parent, home_team, away_team)
"""

import math
import random
import threading
import tkinter as tk
from tkinter import ttk

from game_classes import PlayerPosition
from simulation import GameSim

# ----------------------------------------------------------------------------
# Theme (matches app dark theme; square corners everywhere, pills on buttons)
# ----------------------------------------------------------------------------
BG = "#0B0F16"
CONTENT_BG = "#111826"
TEXT = "#E8ECF1"
MUTED = "#8B93A5"
ACCENT = "#E63946"          # home
AWAY_COLOR = "#6CB4EE"      # away (ice blue)
PUCK_COLOR = "#111418"
# Broadcast-rink palette (real NHL look: bright ice, crisp markings)
ICE = "#CFE7F9"
LINE_RED = "#D31145"
LINE_BLUE = "#005EB8"
FACEOFF_RED = "#D31145"
BOARD_BLUE = "#1E88C7"
CREASE_BLUE = "#BFD9F2"
RINK_SURROUND = "#0B0F16"
INK = "#1B2A41"             # dark text on ice
FONT = "Segoe UI"

try:
    from modern_widgets import RoundedButton
except Exception:  # pragma: no cover - fallback if theme widgets unavailable
    RoundedButton = None


# ----------------------------------------------------------------------------
# Rink geometry (feet). x: 0 = home net, 200 = away net. y: 0..85.
# ----------------------------------------------------------------------------
RINK_L, RINK_W = 200.0, 85.0
HOME_NET_X, AWAY_NET_X = 11.0, 189.0

SHOT_SPOTS = {  # for a team attacking in +x (home); mirrored for away
    "crease": (182, 42.5),
    "low_slot": (172, 42.5),
    "high_slot": (160, 42.5),
    "left_circle": (166, 27),
    "right_circle": (166, 58),
    "point": (145, 42.5),
    "left_wing": (150, 18),
    "right_wing": (150, 67),
    "behind_net": (193, 42.5),
}

FACEOFF_DOTS = {
    "center": (100, 42.5),
    "neutral_home": (82, 42.5),
    "neutral_away": (118, 42.5),
}


def _mirror_x(x):
    return RINK_L - x


def shot_spot(location, attacking_home):
    """Map a ShotLocation value name to rink coordinates for the attacking team."""
    x, y = SHOT_SPOTS.get(location, (160, 42.5))
    if not attacking_home:
        x = _mirror_x(x)
    # add a little jitter so repeated shots don't stack perfectly
    return (x + random.uniform(-2, 2), y + random.uniform(-3, 3))


def faceoff_dot(zone, winner_is_home):
    """zone is relative to the faceoff winner ('offensive_zone', etc.)."""
    if zone == "offensive_zone":
        x = 169 if winner_is_home else 31
    elif zone == "defensive_zone":
        x = 31 if winner_is_home else 169
    else:
        return FACEOFF_DOTS["center"]
    # pick the dot nearer to... just alternate sides deterministically-ish
    y = 30 if random.random() < 0.5 else 55
    return (x, y)


# ----------------------------------------------------------------------------
# Line construction
# ----------------------------------------------------------------------------
def _best_line(team):
    """Return dict with 5 skaters (C, LW, RW, D1, D2) + goalie for visualization."""
    skaters = [p for p in team.roster
               if p.primary_position != PlayerPosition.GOALIE]
    used = set()
    line = {}

    def pick(positions):
        cands = [p for p in skaters
                 if p.primary_position in positions and p.id not in used]
        if not cands:
            cands = [p for p in skaters if p.id not in used]
        if not cands:
            return None
        best = max(cands, key=lambda p: p.overall_rating())
        used.add(best.id)
        return best

    line["C"] = pick([PlayerPosition.CENTER])
    line["LW"] = pick([PlayerPosition.LEFT_WING])
    line["RW"] = pick([PlayerPosition.RIGHT_WING])
    line["D1"] = pick([PlayerPosition.LEFT_DEFENSE])
    line["D2"] = pick([PlayerPosition.RIGHT_DEFENSE])
    try:
        line["G"] = team.get_starting_goalie()
    except Exception:
        line["G"] = None
    return line


# ----------------------------------------------------------------------------
# The visualizer window
# ----------------------------------------------------------------------------
class PBPVisualSim(tk.Toplevel):
    GAME_RATE = 12.0  # game-seconds per real second at 1x

    def __init__(self, parent, sim, home_team, away_team,
                 home_line=None, away_line=None, on_complete=None):
        super().__init__(parent)
        self.title(f"Live Sim — {home_team.team_name} vs {away_team.team_name}")
        self.configure(bg=BG)
        self.geometry("1280x570")
        self.minsize(1100, 540)

        self.sim = sim
        self.home_team = home_team
        self.away_team = away_team
        self.home_line = home_line or _best_line(home_team)
        self.away_line = away_line or _best_line(away_team)
        self.on_complete = on_complete  # called once (on UI thread) when game_end plays
        self._complete_fired = False

        # -- event stream state --
        self.events = []          # filled by sim thread via listener
        self.cursor = 0
        self.playhead = 0.0       # game seconds consumed
        self.playing = False
        self.speed = 1
        self.sim_done = False
        self.hold_until = 0.0     # real-time hold (goal celebrations)
        self.closed = False

        # -- on-ice state --
        self.dots = {}            # dot_id -> dict(player, team_home, role, x, y, tx, ty, items...)
        self.puck = {"x": 100.0, "y": 42.5}
        self.puck_flight = None   # (x0,y0,x1,y1, start_real, dur, on_arrive)
        self.pending_outcome = None
        self.possession_home = None   # True/False/None
        self.carrier_id = None
        self.penalty_box = set()      # dot_ids
        self.shootout_mode = False
        self.shootout_state = None
        self._instant = False         # True during sim-to-end: no flights

        self._build_widgets()
        self._draw_rink()
        self._create_dots()
        self._faceoff_formation(100, 42.5, winner_is_home=True, teleport=True)
        self._feed("Game about to begin…", tag="period")

        # start sim in background
        sim.pbp_listeners.append(self._on_sim_event)
        t = threading.Thread(target=self._run_sim, daemon=True)
        t.start()

        self._tick()

    # ------------------------------------------------------------------
    # Sim thread
    # ------------------------------------------------------------------
    def _run_sim(self):
        try:
            self.sim.simulate_game()
        finally:
            self.sim_done = True

    def _on_sim_event(self, ev):
        self.events.append(ev)

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    def _pill(self, parent, text, command, w=86, padx=3):
        if RoundedButton is not None:
            b = RoundedButton(parent, text=text, command=command, width=w,
                              height=30, bg="#232E44", fg=TEXT)
            b.pack(side="left", padx=padx)
            return b
        b = tk.Button(parent, text=text, command=command, bg="#1B2637",
                      fg=TEXT, relief="flat", padx=10, pady=4)
        b.pack(side="left", padx=padx)
        return b

    def _build_widgets(self):
        # Scoreboard bar
        top = tk.Frame(self, bg=CONTENT_BG)
        top.pack(fill="x", padx=10, pady=(10, 6))
        self.score_var = tk.StringVar(value="–  –")
        tk.Label(top, textvariable=self.score_var, bg=CONTENT_BG, fg=TEXT,
                 font=(FONT, 18, "bold")).pack(side="left", padx=12, pady=8)
        self.clock_var = tk.StringVar(value="P1 20:00")
        tk.Label(top, textvariable=self.clock_var, bg=CONTENT_BG, fg=ACCENT,
                 font=(FONT, 16, "bold")).pack(side="left", padx=12)
        tk.Label(top, text="LIVE SIM", bg=ACCENT, fg="white",
                 font=(FONT, 10, "bold"), padx=8, pady=2).pack(side="right", padx=12)

        # Main split
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=10, pady=4)

        # Rink canvas (940x400 @ 4.7 px/ft)
        self.scale = 4.7
        self.rink_w, self.rink_h = int(RINK_L * self.scale), int(RINK_W * self.scale)
        rink_frame = tk.Frame(main, bg=BG)
        rink_frame.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(rink_frame, width=self.rink_w, height=self.rink_h,
                                bg=RINK_SURROUND, highlightthickness=0, bd=0)
        self.canvas.pack(padx=4, pady=4)

        # Live team-stats strip under the rink (Shots / Hits / Faceoffs / PIM)
        self.team_stats = {"home": {"Shots": 0, "Hits": 0, "FO": 0, "PIM": 0},
                           "away": {"Shots": 0, "Hits": 0, "FO": 0, "PIM": 0}}
        self._stat_vars = {}
        strip = tk.Frame(rink_frame, bg=BG)
        strip.pack(fill="x", padx=4, pady=(0, 6))
        for i, label in enumerate(("Shots", "Hits", "Faceoffs", "PIM")):
            key = {"Shots": "Shots", "Hits": "Hits", "Faceoffs": "FO", "PIM": "PIM"}[label]
            cell = tk.Frame(strip, bg=CONTENT_BG)
            cell.grid(row=0, column=i, sticky="ew", padx=3)
            strip.grid_columnconfigure(i, weight=1)
            hv = tk.StringVar(value="0")
            av = tk.StringVar(value="0")
            self._stat_vars[key] = (hv, av)
            tk.Label(cell, textvariable=hv, font=(FONT, 13, "bold"),
                     bg=CONTENT_BG, fg=ACCENT).pack(side="left", padx=(10, 0))
            tk.Label(cell, text=label, font=(FONT, 9),
                     bg=CONTENT_BG, fg=MUTED).pack(side="left", padx=6)
            tk.Label(cell, textvariable=av, font=(FONT, 13, "bold"),
                     bg=CONTENT_BG, fg=AWAY_COLOR).pack(side="right", padx=(0, 10))

        # Right panel: feed + controls
        right = tk.Frame(main, bg=CONTENT_BG, width=300)
        right.pack(side="right", fill="y", padx=(6, 0))
        right.pack_propagate(False)

        tk.Label(right, text="PLAY BY PLAY", bg=CONTENT_BG, fg=ACCENT,
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=10, pady=(8, 2))

        # Controls (packed before the feed so they always keep their space)
        ctl = tk.Frame(right, bg=CONTENT_BG)
        ctl.pack(side="bottom", fill="x", padx=8, pady=8)
        self.play_btn = self._pill(ctl, "Pause", self._toggle_play, w=72)
        spd = tk.Frame(ctl, bg=CONTENT_BG)
        spd.pack(side="left", padx=2)
        self.speed_btns = {}
        for label, val in (("1x", 1), ("2x", 2), ("4x", 4)):
            b = self._pill(spd, label, lambda v=val: self._set_speed(v), w=38)
            self.speed_btns[val] = b
        self._pill(ctl, "End", self._sim_to_end, w=56)

        self.feed = tk.Text(right, bg="#0D1420", fg=TEXT, font=(FONT, 10),
                            wrap="word", relief="flat", highlightthickness=0,
                            padx=8, pady=6, height=22)
        self.feed.pack(fill="both", expand=True, padx=8, pady=4)
        self.feed.tag_config("goal", foreground="#7CFC98", font=(FONT, 10, "bold"))
        self.feed.tag_config("period", foreground=ACCENT, font=(FONT, 10, "bold"))
        self.feed.tag_config("penalty", foreground="#FFD166")
        self.feed.tag_config("shot", foreground="#9FD8FF")
        self.feed.config(state="disabled")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Rink drawing (square corners)
    # ------------------------------------------------------------------
    def X(self, x):
        return x * self.scale

    def Y(self, y):
        return y * self.scale

    def _rr_points(self, x0, y0, x1, y1, r, steps=10):
        """Point list for a rounded rectangle (for boards / ice outline)."""
        pts = []
        corners = [(x1 - r, y0 + r, 270, 360), (x1 - r, y1 - r, 0, 90),
                   (x0 + r, y1 - r, 90, 180), (x0 + r, y0 + r, 180, 270)]
        for cx, cy, a0, a1 in corners:
            for i in range(steps + 1):
                a = math.radians(a0 + (a1 - a0) * i / steps)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    def _draw_rink(self):
        """Clip-art NHL rink matching the reference image: near-white ice
        with soft blue edge tint, bold blue board frame, thin red goal
        lines, thick blue lines, red faceoff circles (dot + inner hash
        ticks), blue creases, small nets on the goal lines."""
        c = self.canvas
        W, H = self.rink_w, self.rink_h
        rr = 28 * self.scale

        # --- ice: soft vignette, near-white center -> light blue edges ---
        c.create_polygon(self._rr_points(8, 8, W - 8, H - 8, rr),
                         fill="#CFE4F6", outline="")
        c.create_polygon(self._rr_points(28, 28, W - 28, H - 28, rr - 20),
                         fill="#DDEBF9", outline="")
        c.create_polygon(self._rr_points(60, 60, W - 60, H - 60, rr - 52),
                         fill="#EFF6FD", outline="")

        # --- lines ---
        c.create_line(self.X(100), 12, self.X(100), H - 12, fill=LINE_RED, width=3)
        for bx in (75, 125):
            c.create_line(self.X(bx), 12, self.X(bx), H - 12, fill=LINE_BLUE, width=9)
        for gx in (HOME_NET_X, AWAY_NET_X):
            c.create_line(self.X(gx), 12, self.X(gx), H - 12, fill=LINE_RED, width=2)

        # --- center: blue circle + dot ---
        cx, cy = self.X(100), self.Y(42.5)
        c.create_oval(cx - 66, cy - 66, cx + 66, cy + 66,
                      outline=LINE_BLUE, width=3)
        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=LINE_BLUE)

        # --- end-zone faceoff circles (20 ft out, 22 ft off center) ---
        for gx in (HOME_NET_X, AWAY_NET_X):
            sgn = 1 if gx == HOME_NET_X else -1
            for dy in (20.5, 64.5):
                ex, ey = self.X(gx + 20 * sgn), self.Y(dy)
                c.create_oval(ex - 66, ey - 66, ex + 66, ey + 66,
                              outline=FACEOFF_RED, width=3)
                # dot with white stripe
                c.create_oval(ex - 9, ey - 9, ex + 9, ey + 9,
                              fill=FACEOFF_RED, outline="")
                c.create_line(ex - 9, ey, ex + 9, ey, fill="white", width=3)
                # inner hash ticks flanking the dot
                for sx in (-1, 1):
                    hx = ex + sx * 22
                    c.create_line(hx - 9, ey, hx + 9, ey,
                                  fill=FACEOFF_RED, width=3)

        # --- neutral-zone dots ---
        for dx, dy in ((80, 20.5), (80, 64.5), (120, 20.5), (120, 64.5)):
            ex, ey = self.X(dx), self.Y(dy)
            c.create_oval(ex - 5, ey - 5, ex + 5, ey + 5, fill=FACEOFF_RED)

        # --- creases (light blue) ---
        for nx, flip in ((HOME_NET_X, 1), (AWAY_NET_X, -1)):
            c.create_arc(self.X(nx) - 28 * flip, self.Y(42.5) - 28,
                         self.X(nx) + 28 * flip, self.Y(42.5) + 28,
                         start=270 if flip > 0 else 90, extent=180,
                         fill=CREASE_BLUE, outline=LINE_RED, width=2)

        # --- nets: small, sitting on the goal line ---
        self.goal_items = {}
        for nx, side in ((HOME_NET_X, "home"), (AWAY_NET_X, "away")):
            d = 10 if side == "away" else -10
            x0, x1 = self.X(nx) - 5, self.X(nx) + d
            y0, y1 = self.Y(42.5) - 14, self.Y(42.5) + 14
            items = [c.create_rectangle(min(x0, x1), y0, max(x0, x1), y1,
                                        fill="white", outline=LINE_RED, width=3)]
            for i in range(1, 3):
                yy = y0 + i * (y1 - y0) / 3
                items.append(c.create_line(min(x0, x1), yy, max(x0, x1), yy,
                                           fill="#9AA8BC", width=1))
            self.goal_items[side] = items

        # --- goal lights (hidden until a goal) ---
        self.lights = {}
        for nx, side in ((HOME_NET_X, "home"), (AWAY_NET_X, "away")):
            lx = self.X(nx) - 26 if side == "home" else self.X(nx) + 26
            it = c.create_oval(lx - 10, self.Y(30) - 10, lx + 10, self.Y(30) + 10,
                               fill="#FF2E3E", outline="white", width=2,
                               state="hidden")
            self.lights[side] = it

        # --- boards: bold blue frame ---
        boards = self._rr_points(8, 8, W - 8, H - 8, rr)
        c.create_polygon(boards, outline=BOARD_BLUE, fill="", width=18)

    def _bump_stat(self, side, key, amount=1):
        """Increment a team stat ('home'/'away', 'Shots'/'Hits'/'FO'/'PIM')."""
        self.team_stats[side][key] += amount
        hv, av = self._stat_vars[key]
        hv.set(str(self.team_stats["home"][key]))
        av.set(str(self.team_stats["away"][key]))

    def _side_of(self, team_name):
        return "home" if team_name == self.home_team.team_name else "away"

    # ------------------------------------------------------------------
    # Dots
    # ----------------------------------------------------------------------------
    def _create_dots(self):
        c = self.canvas
        idx = 0
        for is_home, line in ((True, self.home_line), (False, self.away_line)):
            color = ACCENT if is_home else AWAY_COLOR
            for role in ("C", "LW", "RW", "D1", "D2"):
                p = line.get(role)
                if p is None:
                    continue
                self._make_dot(f"S{idx}", p, is_home, role, color, r=13)
                idx += 1
            g = line.get("G")
            if g is not None:
                self._make_dot(f"G{idx}", g, is_home, "G", color, r=15)
                idx += 1
        # puck
        px, py = self.X(self.puck["x"]), self.Y(self.puck["y"])
        self.puck_item = c.create_oval(px - 5, py - 5, px + 5, py + 5,
                                       fill="#111418", outline="white", width=1)

    def _make_dot(self, dot_id, player, is_home, role, color, r=13):
        c = self.canvas
        num = getattr(player, "jersey_number", None) or "–"
        # start off-ice; formations will place them
        x, y = (100.0, 42.5)
        oval = c.create_oval(self.X(x) - r, self.Y(y) - r,
                             self.X(x) + r, self.Y(y) + r,
                             fill=color, outline="white", width=2)
        fg = "white" if is_home else "#0B0F16"
        txt = c.create_text(self.X(x), self.Y(y), text=str(num),
                            fill=fg, font=(FONT, 9, "bold"))
        self.dots[dot_id] = {
            "id": dot_id, "player": player, "is_home": is_home,
            "role": role, "x": x, "y": y, "tx": x, "ty": y,
            "oval": oval, "text": txt, "r": r,
            "nudge": None,  # (dx, dy, until) hit animation
        }

    def _dot_by_player(self, player):
        if player is None:
            return None
        pid = getattr(player, "id", None)
        for d in self.dots.values():
            if getattr(d["player"], "id", None) == pid:
                return d
        return None

    def _move_dot(self, d, x, y):
        d["x"], d["y"] = x, y
        c = self.canvas
        r = d["r"]
        c.coords(d["oval"], self.X(x) - r, self.Y(y) - r,
                 self.X(x) + r, self.Y(y) + r)
        c.coords(d["text"], self.X(x), self.Y(y))

    # ------------------------------------------------------------------
    # Formations & targets
    # ------------------------------------------------------------------
    def _faceoff_formation(self, dx, dy, winner_is_home, teleport=False):
        """Line dots up at a faceoff dot. dir = winner's attack direction."""
        wdir = 1 if winner_is_home else -1
        spots = {}  # dot_id -> (x, y)
        for d in self.dots.values():
            role, home = d["role"], d["is_home"]
            if role == "G":
                gx = HOME_NET_X if home else AWAY_NET_X
                spots[d["id"]] = (gx, 42.5)
                continue
            wins = (home == winner_is_home)
            s = 1 if wins else -1  # winner on attack side of dot
            if role == "C":
                spots[d["id"]] = (dx + 2.5 * s * wdir, dy)
            elif role in ("LW", "RW"):
                side = -1 if role == "LW" else 1
                spots[d["id"]] = (dx - 7 * s * wdir, dy + 11 * side)
            else:  # D1, D2
                side = -1 if role == "D1" else 1
                spots[d["id"]] = (dx - 17 * s * wdir, dy + 12 * side)
        for did, (x, y) in spots.items():
            d = self.dots[did]
            x = min(max(x, 6), 194)
            y = min(max(y, 6), 79)
            if teleport:
                self._move_dot(d, x, y)
            d["tx"], d["ty"] = x, y
        self.puck["x"], self.puck["y"] = dx, dy
        self.puck_flight = None
        self.pending_outcome = None

    def _attack_dir(self, is_home):
        return 1 if is_home else -1

    def _net_x(self, is_home, attacking):
        """x of the net the team is attacking (True) or defending (False)."""
        if attacking:
            return AWAY_NET_X if is_home else HOME_NET_X
        return HOME_NET_X if is_home else AWAY_NET_X

    def _update_targets(self):
        """Simple hockey sense: skate to formation spots around the puck."""
        px, py = self.puck["x"], self.puck["y"]
        for d in self.dots.values():
            if d["id"] in self.penalty_box:
                d["tx"], d["ty"] = 100, 4
                continue
            home, role = d["is_home"], d["role"]
            if role == "G":
                own = self._net_x(home, attacking=False)
                # shuffle with puck
                d["tx"] = own
                d["ty"] = 42.5 + max(-8, min(8, (py - 42.5) * 0.35))
                continue
            has_puck = (self.possession_home == home) if self.possession_home is not None else None
            adir = self._attack_dir(home)
            anx = self._net_x(home, attacking=True)     # net we attack
            onx = self._net_x(home, attacking=False)    # net we defend
            jx = random.uniform(-2.5, 2.5)
            jy = random.uniform(-2.5, 2.5)
            if d["id"] == self.carrier_id:
                d["tx"], d["ty"] = px, py
            elif has_puck:
                # offensive shape: forwards to slot/half-boards, D to points
                if role == "C":
                    d["tx"], d["ty"] = anx - 26 * adir + jx, 42.5 + jy
                elif role == "LW":
                    d["tx"], d["ty"] = anx - 38 * adir + jx, 20 + jy
                elif role == "RW":
                    d["tx"], d["ty"] = anx - 38 * adir + jx, 65 + jy
                elif role == "D1":
                    d["tx"], d["ty"] = anx - 56 * adir + jx, 30 + jy
                else:
                    d["tx"], d["ty"] = anx - 56 * adir + jx, 55 + jy
            else:
                # defensive shape: collapse between puck and own net
                if role in ("D1", "D2"):
                    side = -7 if role == "D1" else 7
                    d["tx"], d["ty"] = onx + 16 * adir + jx, 42.5 + side + jy
                elif role == "C":
                    d["tx"], d["ty"] = onx + 26 * adir + jx, 42.5 + jy
                elif role == "LW":
                    d["tx"], d["ty"] = onx + 32 * adir + jx, 24 + jy
                else:
                    d["tx"], d["ty"] = onx + 32 * adir + jx, 61 + jy
            d["tx"] = min(max(d["tx"], 5), 195)
            d["ty"] = min(max(d["ty"], 5), 80)

    # ------------------------------------------------------------------
    # Feed
    # ------------------------------------------------------------------
    def _stamp(self, ev):
        p = ev.get("period", 1)
        clk = ev.get("clock", 0)
        return f"P{p} {int(clk // 60):02d}:{int(clk % 60):02d}"

    def _feed(self, msg, tag=None, ev=None):
        self.feed.config(state="normal")
        prefix = f"{self._stamp(ev)} — " if ev else ""
        self.feed.insert("end", prefix + msg + "\n", tag or ())
        self.feed.see("end")
        # cap length
        lines = int(self.feed.index("end-1c").split(".")[0])
        if lines > 600:
            self.feed.delete("1.0", "200.0")
        self.feed.config(state="disabled")

    @staticmethod
    def _pname(p):
        if p is None:
            return "?"
        num = getattr(p, "jersey_number", "?")
        last = getattr(p, "last_name", "") or getattr(p, "full_name", "?")
        return f"#{num} {last}"

    # ------------------------------------------------------------------
    # Event application
    # ------------------------------------------------------------------
    def _consume(self, ev):
        et = ev["type"]
        if et == "game_start":
            self._update_scoreboard(ev)
        elif et == "period_start":
            self.penalty_box.clear()
            for d in self.dots.values():
                self.canvas.itemconfig(d["oval"], state="normal")
            self._feed(f"Start of period {ev.get('period', 1)}.", tag="period", ev=ev)
            self._faceoff_formation(100, 42.5, winner_is_home=True)
            self.possession_home = None
            self.carrier_id = None
            self._update_scoreboard(ev)
        elif et == "period_end":
            self._feed(f"End of period {ev.get('period', 1)}. "
                       f"{self.home_team.team_name} {ev['home_score']} - "
                       f"{ev['away_score']} {self.away_team.team_name}.",
                       tag="period", ev=ev)
            self._update_scoreboard(ev)
        elif et == "faceoff":
            self._on_faceoff(ev)
        elif et == "shot":
            self._on_shot(ev)
        elif et in ("goal", "save", "blocked_shot", "missed_shot"):
            self._stage_outcome(ev)
        elif et == "hit":
            self._on_hit(ev)
        elif et == "penalty":
            self._on_penalty(ev)
        elif et == "shootout_start":
            self._feed("Shootout!", tag="period", ev=ev)
            self.shootout_mode = True
        elif et == "shootout_attempt":
            self._on_shootout_attempt(ev)
        elif et == "shootout_end":
            self._feed(f"Shootout over — {ev['winner']} wins "
                       f"{ev['home_score']}-{ev['away_score']}.", tag="goal", ev=ev)
            self._update_scoreboard(ev)
        elif et == "game_end":
            self._feed(f"Final: {self.home_team.team_name} {ev['home_score']} - "
                       f"{ev['away_score']} {self.away_team.team_name}. "
                       f"{ev.get('winner', '')} wins!", tag="goal", ev=ev)
            self._update_scoreboard(ev)
            self.playing = False
            self._refresh_play_btn()
            if not self._complete_fired:
                self._complete_fired = True
                cb = self.on_complete
                sim = self.sim
                if cb is not None:
                    self.after(500, lambda: cb(sim))

    def _on_faceoff(self, ev):
        winner_is_home = ev["winner_team"] == self.home_team.team_name
        dx, dy = faceoff_dot(ev.get("zone", "neutral_zone"), winner_is_home)
        self._faceoff_formation(dx, dy, winner_is_home, teleport=False)
        self.possession_home = winner_is_home
        w = self._dot_by_player(ev.get("winner_player"))
        self.carrier_id = w["id"] if w else None
        self._feed(f"Faceoff ({ev.get('zone', '').replace('_', ' ')}): "
                   f"{self._pname(ev.get('winner_player'))} wins it.",
                   ev=ev)
        self._bump_stat("home" if winner_is_home else "away", "FO")
        self._update_scoreboard(ev)

    def _on_shot(self, ev):
        att_home = ev["attacking_team"] == self.home_team.team_name
        self._bump_stat("home" if att_home else "away", "Shots")
        sx, sy = shot_spot(ev.get("location", "high_slot"), att_home)
        shooter_dot = self._dot_by_player(ev.get("shooter"))
        if shooter_dot:
            sx, sy = shooter_dot["x"], shooter_dot["y"]
        nx = AWAY_NET_X if att_home else HOME_NET_X
        self.possession_home = att_home
        self.carrier_id = shooter_dot["id"] if shooter_dot else None
        # peek: the outcome event should already be in the stream
        outcome = None
        if self.cursor < len(self.events):
            nxt = self.events[self.cursor]
            if nxt["type"] in ("goal", "save", "blocked_shot", "missed_shot"):
                outcome = nxt
                self.cursor += 1
                self.playhead = max(self.playhead, outcome.get("t", self.playhead))
        self.puck_flight = (sx, sy, nx, 42.5, self._now(), 0.45, outcome)
        self.pending_outcome = outcome
        if self._instant:
            # sim-to-end: apply immediately, no animation
            self.puck_flight = None
            self.pending_outcome = None
            if outcome:
                self._apply_outcome(outcome)
                self._scatter_puck(outcome)
        st = ev.get("shot_type", "").replace("_", " ")
        self._feed(f"{st.title()} by {self._pname(ev.get('shooter'))} "
                   f"from {ev.get('location', '').replace('_', ' ')}…",
                   tag="shot", ev=ev)

    def _stage_outcome(self, ev):
        # applied when the puck flight lands (see _tick)
        if self.puck_flight is None:
            self._apply_outcome(ev)
        else:
            self.pending_outcome = ev

    def _apply_outcome(self, ev):
        et = ev["type"]
        if et == "goal":
            att_home = ev["scoring_team"] == self.home_team.team_name
            side = "away" if att_home else "home"
            self._flash_light(side)
            assists = ", ".join(self._pname(a) for a in ev.get("assists", []))
            extra = f" (assists: {assists})" if assists else ""
            self._feed(f"GOAL! {self._pname(ev.get('shooter'))}{extra}. "
                       f"{ev['home_score']}-{ev['away_score']}",
                       tag="goal", ev=ev)
            self.hold_until = self._now() + 1.6
            self.possession_home = None
            self.carrier_id = None
            self._update_scoreboard(ev)
        elif et == "save":
            self._feed(f"Saved by {self._pname(ev.get('goalie'))} "
                       f"on {self._pname(ev.get('shooter'))}.", ev=ev)
            # goalie covers: defending team keeps it
            def_home = ev.get("defending_team") == self.home_team.team_name
            self.possession_home = def_home
            self.carrier_id = None
            self._update_scoreboard(ev)
        elif et == "blocked_shot":
            self._feed(f"Shot blocked by {self._pname(ev.get('blocker'))}.", ev=ev)
            def_home = ev.get("defending_team") == self.home_team.team_name
            self.possession_home = def_home
            self.carrier_id = None
        elif et == "missed_shot":
            self._feed(f"{self._pname(ev.get('shooter'))} misses the net.", ev=ev)
            att_home = ev.get("attacking_team") == self.home_team.team_name
            self.possession_home = att_home

    def _on_hit(self, ev):
        h = self._dot_by_player(ev.get("hitting_player"))
        t = self._dot_by_player(ev.get("target_player"))
        if h and t:
            # lunge hitter toward target briefly
            h["nudge"] = (t["x"], t["y"], self._now() + 0.35)
        if ev.get("result") == "turnover_caused":
            th = ev.get("hitting_player")
            self.possession_home = (getattr(th, "team_name", None) == self.home_team.team_name)
            self.carrier_id = h["id"] if h else None
        hp = ev.get("hitting_player")
        self._bump_stat(self._side_of(getattr(hp, "team_name", None)), "Hits")
        self._feed(f"{ev.get('hit_type', 'hit').replace('_', ' ').title()} — "
                   f"{self._pname(ev.get('hitting_player'))} on "
                   f"{self._pname(ev.get('target_player'))}.", ev=ev)

    def _on_penalty(self, ev):
        d = self._dot_by_player(ev.get("player"))
        if d:
            self.penalty_box.add(d["id"])
            self.canvas.itemconfig(d["oval"], state="normal")
        self._bump_stat(self._side_of(ev.get("team")), "PIM", ev.get("minutes", 2))
        self._feed(f"Penalty: {ev.get('minutes', 2)} min — "
                   f"{self._pname(ev.get('player'))} ({ev.get('team', '')}).",
                   tag="penalty", ev=ev)

    def _on_shootout_attempt(self, ev):
        shooter = ev.get("shooter")
        att_home = (getattr(shooter, "team_name", None) == self.home_team.team_name)
        nx = AWAY_NET_X if att_home else HOME_NET_X
        d = self._dot_by_player(shooter)
        sx, sy = (100.0, 42.5)
        if d:
            self._move_dot(d, 100.0, 42.5)
            d["tx"], d["ty"] = nx - (30 if att_home else -30), 42.5
        self.puck["x"], self.puck["y"] = sx, sy
        self.puck_flight = (sx, sy, nx, 42.5, self._now(), 0.9, None)
        self.pending_outcome = None
        self._shootout_pending = ev
        self.carrier_id = d["id"] if d else None
        if self._instant:
            self.puck_flight = None
            self._shootout_pending = None
            self._apply_shootout(ev)
            self._scatter_puck(ev)

    def _apply_shootout(self, ev):
        if ev.get("scored"):
            att_home = (getattr(ev.get("shooter"), "team_name", None)
                        == self.home_team.team_name)
            self._flash_light("away" if att_home else "home")
            self._feed(f"Shootout: {self._pname(ev.get('shooter'))} scores!",
                       tag="goal", ev=ev)
            self.hold_until = self._now() + 1.2
            if att_home:
                self._so_score = (getattr(self, "_so_score", (0, 0))[0] + 1,
                                  getattr(self, "_so_score", (0, 0))[1])
            else:
                self._so_score = (getattr(self, "_so_score", (0, 0))[0],
                                  getattr(self, "_so_score", (0, 0))[1] + 1)
        else:
            self._feed(f"Shootout: {self._pname(ev.get('shooter'))} stopped by "
                       f"{self._pname(ev.get('goalie'))}.", ev=ev)
        self._update_scoreboard(ev)

    # ------------------------------------------------------------------
    # Scoreboard / lights
    # ------------------------------------------------------------------
    def _update_scoreboard(self, ev=None):
        if ev and "home_score" in ev:
            hs, aws = ev["home_score"], ev["away_score"]
        else:
            hs = aws = 0
            for e in self.events[:self.cursor]:
                hs, aws = e.get("home_score", hs), e.get("away_score", aws)
        hn = self.home_team.team_name
        an = self.away_team.team_name
        self.score_var.set(f"{hn} {hs} — {aws} {an}")
        if ev:
            clk = ev.get("clock", 0)
            p = ev.get("period", 1)
            label = f"OT{p - 3}" if p > 3 else f"P{p}"
            self.clock_var.set(f"{label} {int(clk // 60):02d}:{int(clk % 60):02d}")

    def _flash_light(self, side):
        self.canvas.itemconfig(self.lights[side], state="normal")
        self._light_until = self._now() + 1.4
        self._light_side = side

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _toggle_play(self):
        self.playing = not self.playing
        self._refresh_play_btn()

    def _refresh_play_btn(self):
        if RoundedButton is None:
            return
        try:
            self.play_btn.set_text("Play" if not self.playing else "Pause")
        except Exception:
            pass

    def _set_speed(self, v):
        self.speed = v

    def _sim_to_end(self):
        # wait for sim, then consume everything instantly
        while not self.sim_done:
            self.update()
            self.after(50)
        self._instant = True
        try:
            while self.cursor < len(self.events):
                ev = self.events[self.cursor]
                self.cursor += 1
                self.playhead = max(self.playhead, ev.get("t", self.playhead))
                self._consume(ev)
        finally:
            self._instant = False
        self.puck_flight = None
        self.pending_outcome = None
        self._shootout_pending = None
        self.hold_until = 0
        for d in self.dots.values():
            self._move_dot(d, d["tx"], d["ty"])
        self._update_targets()
        self.playing = False
        self._refresh_play_btn()

    def _on_close(self):
        self.closed = True
        try:
            self.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    @staticmethod
    def _now():
        import time
        return time.time()

    def _tick(self):
        if self.closed:
            return
        try:
            self._step()
        except Exception:
            pass
        self.after(50, self._tick)

    def _step(self):
        now = self._now()
        # goal light timeout
        if getattr(self, "_light_until", 0) and now > self._light_until:
            self.canvas.itemconfig(self.lights[self._light_side], state="hidden")
            self._light_until = 0

        # advance playback
        if self.playing and now >= self.hold_until and self.events:
            dt = 0.05 * self.speed * self.GAME_RATE
            target = self.playhead + dt
            # don't run past un-simulated events; sim is fast so this rarely binds
            while self.cursor < len(self.events) and self.events[self.cursor].get("t", 0) <= target:
                ev = self.events[self.cursor]
                self.cursor += 1
                self.playhead = max(self.playhead, ev.get("t", self.playhead))
                self._consume(ev)
            else:
                self.playhead = target
            if self.sim_done and self.cursor >= len(self.events):
                self.playing = False
                self._refresh_play_btn()
        elif not self.playing and not self.events and self.sim_done:
            pass

        # start playback automatically once the first events arrive
        if not self.playing and self.events and not getattr(self, "_autostarted", False):
            self._autostarted = True
            self.playing = True
            self._refresh_play_btn()

        # puck flight animation
        if self.puck_flight:
            x0, y0, x1, y1, t0, dur, outcome = self.puck_flight
            k = min(1.0, (now - t0) / dur)
            e = 1 - (1 - k) ** 2  # ease-out
            self.puck["x"] = x0 + (x1 - x0) * e
            self.puck["y"] = y0 + (y1 - y0) * e
            if k >= 1.0:
                self.puck_flight = None
                if self.pending_outcome is not None:
                    oc = self.pending_outcome
                    self.pending_outcome = None
                    self._apply_outcome(oc)
                    # puck ends: goal -> in net; save -> corner; block -> loose; miss -> behind net
                    self._scatter_puck(oc)
                elif getattr(self, "_shootout_pending", None):
                    so = self._shootout_pending
                    self._shootout_pending = None
                    self._apply_shootout(so)
                    self._scatter_puck(so)

        # hit nudge
        for d in self.dots.values():
            if d["nudge"]:
                nx, ny, until = d["nudge"]
                if now < until:
                    d["tx"], d["ty"] = nx, ny
                else:
                    d["nudge"] = None

        # drift dots toward targets
        if not self.puck_flight:
            self._update_targets()
        for d in self.dots.values():
            x, y = d["x"], d["y"]
            d["x"] = x + (d["tx"] - x) * 0.14
            d["y"] = y + (d["ty"] - y) * 0.14
            self._move_dot(d, d["x"], d["y"])

        # puck follows carrier when not flying
        if not self.puck_flight:
            if self.carrier_id and self.carrier_id in self.dots:
                c = self.dots[self.carrier_id]
                self.puck["x"], self.puck["y"] = c["x"] + 1.5, c["y"] + 1.5

        # draw puck
        px, py = self.X(self.puck["x"]), self.Y(self.puck["y"])
        self.canvas.coords(self.puck_item, px - 5, py - 5, px + 5, py + 5)

        # live clock interpolation between events
        if self.events and self.cursor > 0:
            last = self.events[self.cursor - 1]
            clk = max(0, last.get("clock", 0) - (self.playhead - last.get("t", 0)))
            p = last.get("period", 1)
            label = f"OT{p - 3}" if p > 3 else f"P{p}"
            self.clock_var.set(f"{label} {int(clk // 60):02d}:{int(clk % 60):02d}")

    def _scatter_puck(self, ev):
        et = ev["type"]
        att_home = (ev.get("attacking_team") or ev.get("scoring_team")
                    or getattr(ev.get("shooter"), "team_name", None)) == self.home_team.team_name
        if et == "goal":
            nx = AWAY_NET_X if att_home else HOME_NET_X
            self.puck["x"], self.puck["y"] = nx, 42.5
        elif et == "save":
            nx = AWAY_NET_X if att_home else HOME_NET_X
            self.puck["x"] = nx - 14 if att_home else nx + 14
            self.puck["y"] = random.choice([18, 67])
        elif et == "blocked_shot":
            d = self._dot_by_player(ev.get("blocker"))
            if d:
                self.puck["x"], self.puck["y"] = d["x"], d["y"]
        elif et == "missed_shot":
            nx = AWAY_NET_X if att_home else HOME_NET_X
            self.puck["x"], self.puck["y"] = nx + (8 if att_home else -8), 42.5 + random.uniform(-14, 14)
        elif et == "shootout_attempt":
            self.puck["x"], self.puck["y"] = 100, 42.5


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------
def open_pbp_window(parent, home_team, away_team, on_complete=None):
    """Open the visual play-by-play simulator for a game.

    parent: tk widget (usually the main app root)
    home_team, away_team: Team objects with full rosters
    on_complete: optional callable(sim) fired once on the UI thread when the
        final whistle plays, so the host app can process the result.
    Returns the PBPVisualSim window. Does not block.
    """
    sim = GameSim(home_team, away_team)
    win = PBPVisualSim(parent, sim, home_team, away_team,
                       home_line=_best_line(home_team),
                       away_line=_best_line(away_team),
                       on_complete=on_complete)
    return win
