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
from collections import deque
from tkinter import ttk

from game_classes import PlayerPosition
from simulation import GameSim

# ----------------------------------------------------------------------------
# Theme (matches app dark theme; square corners everywhere, pills on buttons)
# ----------------------------------------------------------------------------
BG = "#0e0e11"
CONTENT_BG = "#0e0e11"
TEXT = "#E8ECF1"
MUTED = "#8B93A5"
ACCENT = "#00ceb8"          # home
AWAY_COLOR = "#6CB4EE"      # away (ice blue)
PUCK_COLOR = "#111418"
# Broadcast-rink palette (real NHL look: bright ice, crisp markings)
ICE = "#CFE7F9"
LINE_RED = "#D31145"
LINE_BLUE = "#005EB8"
FACEOFF_RED = "#D31145"
BOARD_BLUE = "#1E88C7"
CREASE_BLUE = "#BFD9F2"
RINK_SURROUND = "#0e0e11"
INK = "#16161a"             # dark text on ice
FONT = "Segoe UI"

# Event types the "Next Big Moment" button jumps to
BIG_MOMENTS = ("goal", "penalty", "fight", "penalty_shot")

# Replay tuning (playback rate; snapshots are tick-based so any speed works)
REPLAY_RATE = 0.5
# History kept for instant replays: snapshots recorded every tick while playing
HISTORY_MAX = 1400

# Broadcast camera: follows the puck with easing (game-coord units)
CAM_ZOOM = 1.22

try:
    from pbp_sound import SoundEngine
except Exception:
    SoundEngine = None


def _abbr(team_name):
    """3-letter abbreviation for scoreboard-style readouts."""
    name = (team_name or "").upper().replace(".", "")
    words = [w for w in name.split() if w not in ("THE",)]
    if not words:
        return "???"
    return words[0][:3].ljust(3)[:3]


# ----------------------------------------------------------------------------
# Play-by-play commentary templates (no emoji; player names always used)
# ----------------------------------------------------------------------------
_GOAL_T = [
    "GOAL! {S} scores{how}{ast}! {score}",
    "GOAL! {S} buries it{how}{ast}! {score}",
    "GOAL! {S} wires it home{how}{ast}! {score}",
    "GOAL! {S} picks the corner{how}{ast}! {score}",
    "GOAL! {S} finishes it off{how}{ast}! {score}",
    "GOAL! What a finish by {S}{how}{ast}! {score}",
]
_SAVE_T = [
    "Save! {G} stones {S}{how}.",
    "{G} flashes the leather on {S}!",
    "{S} denied by {G}{how}.",
    "What a stop! {G} robs {S}.",
    "{G} holds his ground against {S}.",
]
_BLOCK_T = [
    "{B} gets in the lane to block {S}.",
    "Blocked! {B} sacrifices the body in front of {S}.",
    "{B} blocks the shot from {S}.",
]
_MISS_T = [
    "{S} misses the net.",
    "{S} fires wide of the goal.",
    "{S} rings one off the post!",
    "{S} can't hit the net{how}.",
]
_FACEOFF_T = [
    "Faceoff ({zone}): {W} wins the draw.",
    "{W} wins the faceoff cleanly.",
    "{W} beats his man on the draw ({zone}).",
    "{W} wins it back for his team.",
]
_HIT_T = [
    "{H} levels {T} with a {ht}.",
    "Big hit! {H} on {T}.",
    "{H} finishes the check on {T}.",
    "{H} sends {T} into the boards.",
]
_PASS_T = [
    "{P} to {R}, tape-to-tape{extra}.",
    "{P} finds {R} in stride{extra}.",
    "{P} dishes to {R}{extra}.",
    "{P} threads one to {R}{extra}.",
]
_BATTLE_T = [
    "{W} digs the puck free along the boards.",
    "{W} comes out of the scrum with the puck.",
    "{W} wins the battle and takes possession.",
]
_PENALTY_T = [
    "Penalty: {m} min to {P} ({team}) for {inf}.",
    "{P} heads to the box — {m} min for {inf} ({team}).",
    "Whistle: {P} ({team}) gets {m} for {inf}.",
]
_FIGHT_T = [
    "Fight! {P} drops the gloves!",
    "They're going! {P} in a tilt at center ice.",
]
_ICING_T = [
    "Icing against {team}.",
    "Icing called on {team}.",
]
_OFFSIDE_T = [
    "Offside — play whistled down.",
    "Offside against {team}.",
]

try:
    from modern_widgets import RoundedButton
except Exception:  # pragma: no cover - fallback if theme widgets unavailable
    RoundedButton = None


# ----------------------------------------------------------------------------
# Rink geometry (feet). x: 0 = home net, 200 = away net. y: 0..85.
# ----------------------------------------------------------------------------
RINK_L, RINK_W = 200.0, 85.0
HOME_NET_X, AWAY_NET_X = 11.0, 189.0
BOARDS_CORNER_R = 28.0  # NHL-regulation rounded corners


def clamp_boards(x, y, margin=2.0):
    """Project (x, y) onto the legal ice surface: the 200x85 rink with
    28-ft rounded corners. The boards are impenetrable -- dots and the
    puck stop at them instead of skating through."""
    R = BOARDS_CORNER_R
    x = min(RINK_L - margin, max(margin, x))
    y = min(RINK_W - margin, max(margin, y))
    for cx, cy in ((R, R), (RINK_L - R, R),
                   (R, RINK_W - R), (RINK_L - R, RINK_W - R)):
        in_x = (x < R) if cx == R else (x > RINK_L - R)
        in_y = (y < R) if cy == R else (y > RINK_W - R)
        if in_x and in_y:
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            lim = R - margin
            if d > lim:
                s = lim / d if d else 0.0
                x, y = cx + dx * s, cy + dy * s
    return x, y

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


def _build_lines(team):
    """4 forward lines + 3 D pairs + goalie, sorted by overall (best on L1/P1).

    Used for real on-the-fly line changes in the visualizer: the five
    skater dots keep their roles (C/LW/RW/D1/D2) but get a new player
    (and jersey number) every 45s (F) / 60s (D), matching the sim's
    rotation cadence.
    """
    skaters = [p for p in team.roster
               if getattr(p, "primary_position", None) != PlayerPosition.GOALIE]
    fw_pos = (PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
              PlayerPosition.RIGHT_WING)
    df_pos = (PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE)
    try:
        fw = sorted((p for p in skaters if p.primary_position in fw_pos),
                    key=lambda p: p.overall_rating(), reverse=True)
        df = sorted((p for p in skaters if p.primary_position in df_pos),
                    key=lambda p: p.overall_rating(), reverse=True)
    except Exception:
        fw, df = list(skaters), []

    def pad(group, n):
        if not group:
            return [None] * n
        return [group[i % len(group)] for i in range(n)]
    fw = pad(fw, 12)
    df = pad(df, 6)

    def fit(chunk, roles):
        """Greedily assign the best position-fit player to each role."""
        remaining = [p for p in chunk if p is not None]
        out = {}
        for role, want in roles:
            best = next((p for p in remaining
                         if getattr(p, "primary_position", None) == want), None)
            if best is None and remaining:
                best = remaining[0]
            if best in remaining:
                remaining.remove(best)
            out[role] = best
        return out

    lines = {"F": [], "D": []}
    for i in range(4):
        lines["F"].append(fit(fw[i * 3:(i + 1) * 3],
                              [("C", PlayerPosition.CENTER),
                               ("LW", PlayerPosition.LEFT_WING),
                               ("RW", PlayerPosition.RIGHT_WING)]))
    for i in range(3):
        lines["D"].append(fit(df[i * 2:(i + 1) * 2],
                              [("D1", PlayerPosition.LEFT_DEFENSE),
                               ("D2", PlayerPosition.RIGHT_DEFENSE)]))
    try:
        lines["G"] = team.get_starting_goalie()
    except Exception:
        lines["G"] = None
    return lines


# ----------------------------------------------------------------------------
# The visualizer window
# ----------------------------------------------------------------------------
class PBPVisualSim(tk.Toplevel):
    GAME_RATE = 8.0  # game-seconds per real second at 1x
    TICK_DT = 1.0 / 30.0  # real seconds per animation frame (~30fps)
    # Smooth-skating speeds in rink-feet per real second. Dots glide toward
    # their targets at constant velocity (no exponential rubber-banding), so
    # motion reads as continuous skating instead of choppy teleporting.
    SKATE_SPEED = 30.0   # skaters: brisk but natural on the broadcast view
    GOALIE_SPEED = 14.0  # goalies shuffle; they rarely leave the crease
    CEREMONY_SPEED = 6.0  # faceoff glide to the dot: slow and deliberate
    # Quick faceoff beats (no ceremony every whistle): brief whistle freeze,
    # glide to the dot, set, drop. ~1.5s total so stoppages read as breaks
    # in play without stalling the broadcast.
    _FO_WHISTLE = 0.3
    _FO_LINEUP = 0.6
    _FO_SET = 0.3
    _FO_DROP = 0.3
    _FO_TOTAL = _FO_WHISTLE + _FO_LINEUP + _FO_SET + _FO_DROP

    def __init__(self, parent, sim, home_team, away_team,
                 home_line=None, away_line=None, on_complete=None):
        super().__init__(parent)
        self.title(f"Live Sim — {home_team.team_name} vs {away_team.team_name}")
        self.configure(bg=BG)
        self.geometry("1280x630")
        self.minsize(1100, 580)

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

        # -- momentum (recent shots/goals/fights, last ~10 per team) --
        self._mom = {"home": deque(maxlen=10), "away": deque(maxlen=10)}
        self._mom_dirty = True

        # -- per-period summary tracking --
        self._period_stats = {"shots": {"home": 0, "away": 0},
                              "goals": {"home": 0, "away": 0},
                              "notes": []}

        # -- live goalie stats: pid -> {name, shots, saves} --
        self._goalie_stats = {}
        self._cur_goalie = {"home": None, "away": None}
        self._en = {"home": False, "away": False}  # goalie pulled: empty net
        for side, line in (("home", self.home_line), ("away", self.away_line)):
            g = line.get("G")
            pid = getattr(g, "id", None)
            if pid is not None:
                self._goalie_stats[pid] = {"name": self._gname(g),
                                           "shots": 0, "saves": 0}
                self._cur_goalie[side] = pid

        # -- cached units readout text (avoid redundant StringVar writes) --
        self._units_cache = {"home": None, "away": None}

        # -- on-ice state --
        self.dots = {}            # dot_id -> dict(player, team_home, role, x, y, tx, ty, items...)
        self.puck = {"x": 100.0, "y": 42.5}
        self.puck_flight = None   # (x0,y0,x1,y1, start_real, dur, on_arrive)
        self.pending_outcome = None
        self.possession_home = None   # True/False/None
        self.carrier_id = None
        self.penalty_box = set()      # dot_ids
        # Sim-authoritative skater spots: the sim runs the tactical engine
        # that decides who gets open, who converges on battles, etc. Its
        # positions (from "skate" snapshots) win over our local formation
        # guess so the picture matches the play being described.
        self._sim_pos = {}            # player_id -> (x, y) in rink coords
        self._sim_jobs = {}           # player_id -> job code from the sim
        self._sim_phases = {}         # team_name -> phase code from the sim
        self.shootout_mode = False
        self.shootout_state = None
        self._instant = False         # True during sim-to-end: no flights
        self.puck_target = None       # sim-authored puck destination (eased)
        self._pass_arrival = None     # pass event awaiting flight landing
        self._shootout_pending = None # shootout attempt awaiting flight landing
        self._battle_winner = None
        self._battle_settle_at = 0.0
        self._cur_score = (0, 0)       # (home, away) as currently displayed

        # -- broadcast replay system --
        # history: deque of (playhead_t, {dot_id: (x, y)}, (puck_x, puck_y),
        #                   home_score, away_score), recorded every tick
        self._history = deque(maxlen=HISTORY_MAX)
        self._last_snap_t = -1.0
        self._replay = None           # None or dict(frames, rt, dur, label)
        self._highlights = []         # list of dict(start_t, end_t, label, pid, frames)
        self._stars = None            # computed at game_end
        self._stars_win = None

        # -- puck trail (shot flights) --
        self._trail = deque(maxlen=30)
        self._trail_color = ACCENT
        self._trail_item = None

        # -- shot map overlay: list of (x, y, side, result); result in
        #    {"goal","save","block","miss"}; cleared each period
        self._shotmap = []
        self._shotmap_on = False
        self._last_shot = None        # (x, y, side) awaiting outcome
        self._pending_shot = None     # delayed release while shooter skates in

        # -- per-player live game stats: pid -> dict(G,A,SOG,HIT,PIM,FO) --
        self._pstats = {}

        # -- smart broadcast pacing --
        self.auto_pace = False

        # -- player card popup --
        self._card_win = None
        self._card_pid = None

        # -- penalty release timers: dot_id -> release playhead (game-sec) --
        self._penalty_timers = {}

        # -- broadcast camera (puck-follow pan; zoom fixed at CAM_ZOOM) --
        # Default OFF: the whole ice stays visible so no player gets lost.
        self._cam = {"x": 100.0, "on": False, "shake_until": 0.0,
                     "shake_mag": 0.0}
        self._pan_applied = 0.0

        # -- lower-third banner: dict(state, t0, kind, title, sub, color) --
        self._banner = None
        self._banner_items = []

        # -- full-rink broadcast cards (period intros etc.) --
        self._card_until = 0.0
        self._card_items = []

        # -- quick faceoff state: dict(el, phase, dx, dy, winner_is_home, ev,
        #    puck_from) while a stoppage break is playing out --
        self._faceoff_ceremony = None
        # -- goal celebration state --
        self._celly = None          # {"dot", "until", "cx", "cy", "t0"}
        self._celly_pending = None  # (shooter, att_home) waiting on replay
        self._flash_until = 0.0

        # -- on-ice effects --
        self._marks = deque()             # (canvas_item, birth_real); cap 140
        self._bursts = []                 # (items, t0, cx, cy)

        # -- win probability (home perspective) --
        self._winprob = 0.5

        # -- arena sound (silent-safe: no backend -> no-ops) --
        self._sfx = SoundEngine(enabled=True) if SoundEngine else None
        self._sound_on = bool(self._sfx and self._sfx.available)

        self._build_widgets()
        self._draw_rink()
        self._create_dots()
        # On-ice units are driven by the sim's authoritative skate events;
        # the dots start on the opening lines until the first sync arrives.
        # (_line_change kept as a stub for the bench-glide hooks below.)
        self._line_change = {"home": None, "away": None}
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
        # Broadcast score bug: [BOS][1 – 2][BUF][P3 04:32]  WIN PROB  LIVE
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 6))
        bug = tk.Frame(top, bg="#16161a")
        bug.pack(side="left")
        tk.Label(bug, text=_abbr(self.home_team.team_name), bg=ACCENT,
                 fg="#0e0e11", font=(FONT, 13, "bold"),
                 padx=10, pady=6).pack(side="left")
        self.score_var = tk.StringVar(value="0 – 0")
        tk.Label(bug, textvariable=self.score_var, bg="#16161a", fg="white",
                 font=(FONT, 16, "bold"), padx=10).pack(side="left")
        tk.Label(bug, text=_abbr(self.away_team.team_name), bg=AWAY_COLOR,
                 fg="#0e0e11", font=(FONT, 13, "bold"),
                 padx=10, pady=6).pack(side="left")
        self.clock_var = tk.StringVar(value="P1 20:00")
        tk.Label(bug, textvariable=self.clock_var, bg="#23262e", fg=ACCENT,
                 font=(FONT, 13, "bold"), padx=10, pady=6).pack(side="left")

        # Win probability (home perspective), next to the bug
        probf = tk.Frame(top, bg=BG)
        probf.pack(side="left", padx=(18, 0))
        tk.Label(probf, text="WIN PROB", bg=BG, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w")
        prow = tk.Frame(probf, bg=BG)
        prow.pack()
        self.prob_canvas = tk.Canvas(prow, width=150, height=14, bg="#23262e",
                                     highlightthickness=0, bd=0)
        self.prob_canvas.pack(side="left")
        self.prob_var = tk.StringVar(value="50%")
        tk.Label(prow, textvariable=self.prob_var, bg=BG, fg=TEXT,
                 font=(FONT, 10, "bold"), width=5).pack(side="left", padx=(6, 0))

        tk.Label(top, text="LIVE SIM", bg=ACCENT, fg="white",
                 font=(FONT, 10, "bold"), padx=8, pady=2).pack(side="right", padx=12)

        # Slim bar under the scoreboard: on-ice units, momentum, next moment
        sub = tk.Frame(self, bg=CONTENT_BG)
        sub.pack(fill="x", padx=10, pady=(0, 4))

        units = tk.Frame(sub, bg=CONTENT_BG)
        units.pack(side="left")
        tk.Label(units, text="ON ICE", bg=CONTENT_BG, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=4)
        urow = tk.Frame(sub, bg=CONTENT_BG)
        urow.pack(side="left", padx=(4, 0))
        self.units_home_var = tk.StringVar(value="–")
        self.units_away_var = tk.StringVar(value="–")
        tk.Label(urow, textvariable=self.units_home_var, bg=CONTENT_BG,
                 fg=ACCENT, font=(FONT, 10, "bold")).pack(side="left", padx=(0, 14))
        tk.Label(urow, textvariable=self.units_away_var, bg=CONTENT_BG,
                 fg=AWAY_COLOR, font=(FONT, 10, "bold")).pack(side="left")

        btnf = tk.Frame(sub, bg=CONTENT_BG)
        btnf.pack(side="right", padx=4)
        self._pill(btnf, "Next Big Moment", self._jump_to_next_moment, w=150)

        momf = tk.Frame(sub, bg=CONTENT_BG)
        momf.pack(side="left", fill="x", expand=True, padx=14)
        tk.Label(momf, text="MOMENTUM", bg=CONTENT_BG, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w")
        self.mom_canvas = tk.Canvas(momf, height=22, bg=CONTENT_BG,
                                    highlightthickness=0, bd=0)
        self.mom_canvas.pack(fill="x")
        self.mom_canvas.bind("<Configure>", lambda e: self._draw_momentum())

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
        self.canvas.bind("<Button-1>", self._on_canvas_click)

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

        # Live goalie stats cell: "<last> saves/shots" per side
        gcell = tk.Frame(strip, bg=CONTENT_BG)
        gcell.grid(row=0, column=4, sticky="ew", padx=3)
        strip.grid_columnconfigure(4, weight=1)
        self._goalie_home_var = tk.StringVar(value="–")
        self._goalie_away_var = tk.StringVar(value="–")
        tk.Label(gcell, textvariable=self._goalie_home_var, font=(FONT, 10, "bold"),
                 bg=CONTENT_BG, fg=ACCENT).pack(side="left", padx=(10, 0))
        tk.Label(gcell, text="Goalies", font=(FONT, 9),
                 bg=CONTENT_BG, fg=MUTED).pack(side="left", padx=6)
        tk.Label(gcell, textvariable=self._goalie_away_var, font=(FONT, 10, "bold"),
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
        self.auto_btn = self._pill(ctl, "Auto", self._toggle_auto, w=56)
        self._pill(ctl, "End", self._sim_to_end, w=56)
        self.shotmap_btn = self._pill(ctl, "Shot Map", self._toggle_shotmap, w=84)
        self.cam_btn = self._pill(ctl, "Cam", self._toggle_cam, w=56)
        self._refresh_toggle_btn(self.cam_btn, False)
        self.sound_btn = self._pill(ctl, "Sound", self._toggle_sound, w=68)
        self._refresh_toggle_btn(self.sound_btn, self._sound_on)

        self.feed = tk.Text(right, bg="#0D1420", fg=TEXT, font=(FONT, 10),
                            wrap="word", relief="flat", highlightthickness=0,
                            padx=8, pady=6, height=22)
        self.feed.pack(fill="both", expand=True, padx=8, pady=4)
        self.feed.tag_config("goal", foreground="#7CFC98", font=(FONT, 10, "bold"))
        self.feed.tag_config("period", foreground=ACCENT, font=(FONT, 10, "bold"))
        self.feed.tag_config("penalty", foreground="#FFD166")
        self.feed.tag_config("shot", foreground="#9FD8FF")
        self.feed.tag_config("fight", foreground="#FF8A5C", font=(FONT, 10, "bold"))
        self.feed.tag_config("summary", foreground=ACCENT, font=(FONT, 11, "bold"))
        self.feed.tag_config("info", foreground=MUTED)
        self.feed.config(state="disabled")

        self._update_goalie_labels()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle_cam(self):
        self._set_camera(not self._cam["on"])

    def _toggle_sound(self):
        self._sound_on = not self._sound_on
        if self._sfx is not None:
            self._sfx.enabled = self._sound_on
        self._refresh_toggle_btn(self.sound_btn, self._sound_on)

    # ------------------------------------------------------------------
    # Rink drawing (square corners)
    # ------------------------------------------------------------------
    def _RX(self, x):
        """Raw pixel x at neutral camera (used when drawing the rink)."""
        return x * self.scale

    def _RY(self, y):
        """Raw pixel y at neutral camera (used when drawing the rink)."""
        return y * self.scale

    def _cam_z(self):
        return CAM_ZOOM if self._cam["on"] else 1.0

    def X(self, x):
        z = self._cam_z()
        return (x - self._cam["x"]) * self.scale * z + self.rink_w / 2

    def Y(self, y):
        z = self._cam_z()
        return (y - 42.5) * self.scale * z + self.rink_h / 2

    # ------------------------------------------------------------------
    # Broadcast camera: puck-following pan (+ optional screen shake)
    # ------------------------------------------------------------------
    def _set_camera(self, on):
        """Toggle the puck-following broadcast camera."""
        if on == self._cam["on"]:
            return
        c = self.canvas
        cx, cy = self.rink_w / 2, self.rink_h / 2
        if self._cam["on"]:
            # turning OFF: undo pan first, then un-zoom
            c.move("rink", -self._pan_applied, 0)
            c.move("fx", -self._pan_applied, 0)
            k = 1.0 / CAM_ZOOM
        else:
            k = CAM_ZOOM
        c.scale("rink", cx, cy, k, k)
        c.scale("fx", cx, cy, k, k)
        self._cam["on"] = on
        self._cam["x"] = 100.0
        self._pan_applied = 0.0
        self._refresh_toggle_btn(self.cam_btn, on)

    def _update_camera(self, now):
        cam = self._cam
        if not cam["on"]:
            return
        z = CAM_ZOOM
        vw = self.rink_w / (self.scale * z)
        # lookahead toward the attacking end
        if self.possession_home is True:
            look = 12.0
        elif self.possession_home is False:
            look = -12.0
        else:
            look = 0.0
        want = min(max(self.puck["x"] + look,
                       vw / 2 - 10), 200.0 - vw / 2 + 10)
        # constant-velocity pan (no exponential easing): the broadcast camera
        # glides after the play instead of whipping then crawling.
        cdx = want - cam["x"]
        cstep = 45.0 * self.TICK_DT
        if abs(cdx) <= cstep:
            cam["x"] = want
        else:
            cam["x"] += math.copysign(cstep, cdx)
        # screen shake: decaying random offset while celebrating / big hits
        shake = 0.0
        if now < cam["shake_until"]:
            k = (cam["shake_until"] - now) / 0.6
            shake = random.uniform(-1, 1) * cam["shake_mag"] * max(0.0, k)
        target_px = -(cam["x"] - 100.0) * self.scale * z + shake
        dx = target_px - self._pan_applied
        if abs(dx) > 0.05:
            self.canvas.move("rink", dx, 0)
            self.canvas.move("fx", dx, 0)
            self._pan_applied = target_px

    def _shake(self, mag=5.0, dur=0.6):
        self._cam["shake_until"] = self._now() + dur
        self._cam["shake_mag"] = mag

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
        c.create_line(self._RX(100), 12, self._RX(100), H - 12, fill=LINE_RED, width=3)
        for bx in (75, 125):
            c.create_line(self._RX(bx), 12, self._RX(bx), H - 12, fill=LINE_BLUE, width=9)
        for gx in (HOME_NET_X, AWAY_NET_X):
            c.create_line(self._RX(gx), 12, self._RX(gx), H - 12, fill=LINE_RED, width=2)

        # --- center: blue circle + dot ---
        cx, cy = self._RX(100), self._RY(42.5)
        c.create_oval(cx - 66, cy - 66, cx + 66, cy + 66,
                      outline=LINE_BLUE, width=3)
        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=LINE_BLUE)

        # --- end-zone faceoff circles (20 ft out, 22 ft off center) ---
        for gx in (HOME_NET_X, AWAY_NET_X):
            sgn = 1 if gx == HOME_NET_X else -1
            for dy in (20.5, 64.5):
                ex, ey = self._RX(gx + 20 * sgn), self._RY(dy)
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
            ex, ey = self._RX(dx), self._RY(dy)
            c.create_oval(ex - 5, ey - 5, ex + 5, ey + 5, fill=FACEOFF_RED)

        # --- creases (light blue) ---
        for nx, flip in ((HOME_NET_X, 1), (AWAY_NET_X, -1)):
            c.create_arc(self._RX(nx) - 28 * flip, self._RY(42.5) - 28,
                         self._RX(nx) + 28 * flip, self._RY(42.5) + 28,
                         start=270 if flip > 0 else 90, extent=180,
                         fill=CREASE_BLUE, outline=LINE_RED, width=2)

        # --- nets: small, sitting on the goal line ---
        self.goal_items = {}
        for nx, side in ((HOME_NET_X, "home"), (AWAY_NET_X, "away")):
            d = 10 if side == "away" else -10
            x0, x1 = self._RX(nx) - 5, self._RX(nx) + d
            y0, y1 = self._RY(42.5) - 14, self._RY(42.5) + 14
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
            lx = self._RX(nx) - 26 if side == "home" else self._RX(nx) + 26
            it = c.create_oval(lx - 10, self._RY(30) - 10, lx + 10, self._RY(30) + 10,
                               fill="#FF2E3E", outline="white", width=2,
                               state="hidden")
            self.lights[side] = it

        # --- boards: bold blue frame ---
        boards = self._rr_points(8, 8, W - 8, H - 8, rr)
        c.create_polygon(boards, outline=BOARD_BLUE, fill="", width=18)

        # --- penalty boxes (top corners, outside the ice) ---
        self._penalty_boxes = {}
        for side, fx in (("home", 0.06), ("away", 0.94)):
            bx0, bx1 = W * fx - 46, W * fx + 46
            c.create_rectangle(bx0, 2, bx1, 26, outline="#3A4152", width=1)
            c.create_text((bx0 + bx1) / 2, 14, text="PENALTY",
                          fill="#5A6274", font=(FONT, 7, "bold"))
            self._penalty_boxes[side] = (bx0, bx1)

        # --- benches (center ice, top/bottom boards) ---
        cxm = self._RX(100)
        for y0 in (2, H - 24):
            c.create_rectangle(cxm - 70, y0, cxm + 70, y0 + 22,
                               outline="#3A4152", width=1)
            c.create_text(cxm, y0 + 11, text="BENCH",
                          fill="#5A6274", font=(FONT, 7, "bold"))

        # --- broadcast REPLAY bug (hidden unless replaying) ---
        self._replay_dot = c.create_oval(14, 14, 26, 26, fill="#FF2E3E",
                                         outline="", state="hidden")
        self._replay_text = c.create_text(34, 20, text="REPLAY", anchor="w",
                                          fill="white", font=(FONT, 11, "bold"),
                                          state="hidden")

        # --- tactic phase indicators: subtle, top corners. Shows what each
        # unit is executing (Forecheck 2-1-2, Umbrella PP, ...) so the GM can
        # tell if the tactics are working by watching. Updated from the
        # sim's phase stream; hidden when unknown.
        # Positioned just below the rink top edge to avoid the score bug.
        self._phase_home_text = c.create_text(10, 36, anchor="w",
                                              fill="#8a93a3", font=(FONT, 9),
                                              state="hidden")
        self._phase_away_text = c.create_text(self.rink_w - 10, 36, anchor="e",
                                              fill="#8a93a3", font=(FONT, 9),
                                              state="hidden")
        self._last_phase_home = None
        self._last_phase_away = None

        # --- puck trail (single polyline, redrawn each tick) ---
        self._trail_item = c.create_line(0, 0, 0, 0, fill=ACCENT, width=3,
                                         smooth=True, state="hidden")

        # --- broadcast camera: tag static art; per-tick items (dots, puck,
        # trail) are repositioned through X()/Y() so they follow automatically.
        # The REPLAY bug lives in viewport space and never pans.
        c.addtag_all("rink")
        for it in (self._trail_item, self._replay_dot, self._replay_text):
            c.dtag(it, "rink")
        if self._cam["on"]:
            z = CAM_ZOOM
            c.scale("rink", self.rink_w / 2, self.rink_h / 2, z, z)

    def _bump_stat(self, side, key, amount=1):
        """Increment a team stat ('home'/'away', 'Shots'/'Hits'/'FO'/'PIM')."""
        self.team_stats[side][key] += amount
        hv, av = self._stat_vars[key]
        hv.set(str(self.team_stats["home"][key]))
        av.set(str(self.team_stats["away"][key]))

    def _side_of(self, team_name):
        return "home" if team_name == self.home_team.team_name else "away"

    def _player_side(self, player, ev=None, name_key=None):
        """Resolve 'home'/'away' for a player object.

        Uses our on-ice dots first (authoritative for the presentation
        layer), falling back to a team-name comparison. Needed because
        generated/test players may carry team_name='Free Agent' while the
        event's team-name fields are reliable.
        """
        pid = getattr(player, "id", None)
        if pid is not None:
            for d in self.dots.values():
                if getattr(d["player"], "id", None) == pid:
                    return "home" if d["is_home"] else "away"
            for side, cur in self._cur_goalie.items():
                if cur == pid:
                    return side
        if ev is not None and name_key:
            return self._side_of(ev.get(name_key))
        return self._side_of(getattr(player, "team_name", None))

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
        # puck (+ soft glow behind it)
        px, py = self.X(self.puck["x"]), self.Y(self.puck["y"])
        self.puck_glow = c.create_oval(px - 11, py - 11, px + 11, py + 11,
                                       fill="#bcd6ee", outline="")
        self.puck_item = c.create_oval(px - 5, py - 5, px + 5, py + 5,
                                       fill="#111418", outline="white", width=1)
        # puck-carrier ring: subtle pulsing halo so the eye tracks the play
        self.carrier_ring = c.create_oval(0, 0, 0, 0, outline="#ffffff",
                                          width=2, tags=("fxring",),
                                          state="hidden")

    def _make_dot(self, dot_id, player, is_home, role, color, r=13):
        c = self.canvas
        num = getattr(player, "jersey_number", None) or "–"
        # start off-ice; formations will place them
        x, y = (100.0, 42.5)
        sx, sy = self.X(x) + 2.5, self.Y(y) + 3.5
        shadow = c.create_oval(sx - r, sy - r, sx + r, sy + r,
                               fill="#8fa3b8", outline="", tags=("dot",))
        oval = c.create_oval(self.X(x) - r, self.Y(y) - r,
                             self.X(x) + r, self.Y(y) + r,
                             fill=color, outline="white", width=2,
                             tags=("dot",))
        fg = "white" if is_home else "#0e0e11"
        txt = c.create_text(self.X(x), self.Y(y), text=str(num),
                            fill=fg, font=(FONT, 9, "bold"), tags=("dot",))
        # facing tick: short line showing skate direction (updated per tick)
        tick = c.create_line(self.X(x), self.Y(y), self.X(x), self.Y(y),
                             fill="white", width=2, tags=("dot",))
        self.dots[dot_id] = {
            "id": dot_id, "player": player, "is_home": is_home,
            "role": role, "x": x, "y": y, "tx": x, "ty": y,
            "oval": oval, "text": txt, "shadow": shadow, "tick": tick,
            "r": r, "fx": 1.0, "fy": 0.0, "color": color,
            "nudge": None,  # (dx, dy, until) hit animation
            "jx": random.uniform(-2.5, 2.5),  # fixed personal jitter
            "jy": random.uniform(-2.5, 2.5),
            "drift_phase": random.uniform(0, 6.283),  # idle life-drift
            "drift_amp": random.uniform(1.0, 2.2),  # feet of drift
        }

    def _set_dot_visible(self, d, visible):
        state = "normal" if visible else "hidden"
        c = self.canvas
        for key in ("shadow", "oval", "text", "tick"):
            try:
                c.itemconfig(d[key], state=state)
            except Exception:
                pass

    def _dot_by_player(self, player):
        if player is None:
            return None
        return self._dot_by_id(getattr(player, "id", None))

    def _dot_by_id(self, pid):
        if pid is None:
            return None
        for d in self.dots.values():
            if getattr(d["player"], "id", None) == pid:
                return d
        return None

    def _move_dot(self, d, x, y):
        # The boards are impenetrable: clamp every dot onto the legal ice
        # surface so nobody ever skates through them.
        x, y = clamp_boards(x, y)
        # update facing from movement direction
        dx, dy = x - d["x"], y - d["y"]
        if dx * dx + dy * dy > 0.004:
            m = math.hypot(dx, dy)
            d["fx"], d["fy"] = dx / m, dy / m
        d["x"], d["y"] = x, y
        c = self.canvas
        r = d["r"]
        px, py = self.X(x), self.Y(y)
        # On-ice life: settled skaters never stand statuesque -- a slow,
        # small drift around their spot so the whole rink breathes even
        # between sim events. Render-time only; logical position untouched.
        if self._drift_on(d):
            t = self._now()
            amp = d["drift_amp"] * self.scale * self._cam_z()
            px += amp * math.sin(t * 0.9 + d["drift_phase"])
            py += amp * 0.7 * math.cos(t * 0.65 + d["drift_phase"] * 1.3)
        c.coords(d["oval"], px - r, py - r, px + r, py + r)
        c.coords(d["text"], px, py)
        c.coords(d["shadow"], px - r + 2.5, py - r + 3.5,
                 px + r + 2.5, py + r + 3.5)
        fx, fy = d["fx"], d["fy"]
        c.coords(d["tick"], px + fx * (r + 1), py + fy * (r + 1),
                 px + fx * (r + 7), py + fy * (r + 7))

    def _drift_on(self, d):
        """Whether this dot gets idle life-drift right now."""
        if d["role"] == "G":
            return False
        if d["id"] == self.carrier_id:
            return False
        if d.get("ceremony_glide"):
            return False
        if d["id"] in self.penalty_box:
            return False
        # only when settled near its target (gliding dots already move)
        if math.hypot(d["tx"] - d["x"], d["ty"] - d["y"]) > 3.0:
            return False
        return True

    # ------------------------------------------------------------------
    # Formations & targets
    # ------------------------------------------------------------------
    def _faceoff_spots(self, dx, dy, winner_is_home):
        """Faceoff formation targets: dot_id -> (x, y). No side effects."""
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
            elif role in ("LW", "RW", "XF"):
                side = -1 if role == "LW" else 1
                spots[d["id"]] = (dx - 7 * s * wdir, dy + 11 * side)
            else:  # D1, D2
                side = -1 if role == "D1" else 1
                spots[d["id"]] = (dx - 17 * s * wdir, dy + 12 * side)
        return spots

    def _faceoff_formation(self, dx, dy, winner_is_home, teleport=False):
        """Line dots up at a faceoff dot. dir = winner's attack direction."""
        spots = self._faceoff_spots(dx, dy, winner_is_home)
        for did, (x, y) in spots.items():
            d = self.dots[did]
            x = min(max(x, 6), 194)
            y = min(max(y, 6), 79)
            if teleport:
                self._move_dot(d, x, y)
            d["tx"], d["ty"] = x, y
        self.puck["x"], self.puck["y"] = dx, dy
        # Flush any in-flight shot outcome first: a faceoff always follows a
        # goal, and silently discarding the pending outcome would lose goals.
        if self.pending_outcome is not None and not self._instant:
            oc = self.pending_outcome
            self.pending_outcome = None
            self.puck_flight = None
            self._apply_outcome(oc)
        else:
            self.puck_flight = None
            self.pending_outcome = None

    def _attack_dir(self, is_home):
        return 1 if is_home else -1

    def _net_x(self, is_home, attacking):
        """x of the net the team is attacking (True) or defending (False)."""
        if attacking:
            return AWAY_NET_X if is_home else HOME_NET_X
        return HOME_NET_X if is_home else AWAY_NET_X

    def _pp_team(self):
        """'home'/'away'/None based on current on-ice manpower."""
        h = sum(1 for did, d in self.dots.items()
                if d["is_home"] and d["role"] != "G"
                and did not in self.penalty_box)
        a = sum(1 for did, d in self.dots.items()
                if not d["is_home"] and d["role"] != "G"
                and did not in self.penalty_box)
        if h > a:
            return "home"
        if a > h:
            return "away"
        return None

    def _update_targets(self):
        """Tactical positioning engine (EHM-style formation slots).

        Every skater holds a zone-anchored formation slot driven by puck
        location, possession, role, and manpower -- the way real systems
        work. Only the puck carrier (attack) or a designated checker or
        two (defense/forecheck/loose puck) ever goes to the puck; everyone
        else keeps their shape, holds the weak side, and stays goal-side.
        A separation pass guarantees teammates never pile up. Runs every
        tick; sim skate snapshots only feed puck position + carrier.
        """
        if self._faceoff_ceremony:
            return  # faceoff owns every dot's targets until the puck drops
        px, py = self.puck["x"], self.puck["y"]
        pp = self._pp_team()
        strong_y, weak_y = (24.0, 61.0) if py < 42.5 else (61.0, 24.0)

        # ---- per-team tactical state, computed once per tick ----
        tstate = {}
        for home in (True, False):
            side = "home" if home else "away"
            adir = 1 if home else -1
            anx = AWAY_NET_X if home else HOME_NET_X   # net we attack
            onx = HOME_NET_X if home else AWAY_NET_X   # net we defend
            has = ((self.possession_home == home)
                   if self.possession_home is not None else None)
            oz = (adir == 1 and px > 135) or (adir == -1 and px < 65)
            dz = (adir == 1 and px < 65) or (adir == -1 and px > 135)
            is_pp = pp == side
            is_pk = pp is not None and not is_pp
            skaters = [d for d in self.dots.values()
                       if d["is_home"] == home and d["role"] != "G"
                       and d["id"] not in self.penalty_box
                       and not (self._line_change.get(side)
                                and d["role"] in self._line_change[side]["roles"])]
            fwds = [d for d in skaters if d["role"] in ("C", "LW", "RW")]
            def _dist(d):
                return ((d["x"] - px) ** 2 + (d["y"] - py) ** 2) ** 0.5
            by_dist = sorted(skaters, key=_dist)
            fwd_by_dist = sorted(fwds, key=_dist)
            team = self.home_team if home else self.away_team
            tstate[side] = dict(adir=adir, anx=anx, onx=onx, has=has, oz=oz,
                                dz=dz, is_pp=is_pp, is_pk=is_pk,
                                skaters=skaters, fwds=fwds,
                                forecheck=getattr(team, "tactic_forecheck",
                                                  "2-1-2"),
                                offense=getattr(team, "tactic_offense",
                                                "Spread"),
                                check1={d["id"] for d in by_dist[:1]},
                                check2={d["id"] for d in by_dist[:2]},
                                fcheck1=([d["id"] for d in fwd_by_dist[:1]] or
                                          [None])[0],
                                fcheck2=[d["id"] for d in fwd_by_dist[:2]],
                                fwd_by_dist=fwd_by_dist)

        # ---- assign targets ----
        for d in self.dots.values():
            if d["id"] in self.penalty_box:
                side = "home" if d["is_home"] else "away"
                i = sum(1 for o in self.dots.values()
                        if o["id"] in self.penalty_box
                        and ("home" if o["is_home"] else "away") == side
                        and o["id"] < d["id"])
                bx = 12 + i * 7 if side == "home" else 188 - i * 7
                d["tx"], d["ty"] = bx, 3
                continue
            side = "home" if d["is_home"] else "away"
            ch = self._line_change.get(side)
            if ch is not None and d["role"] in ch["roles"]:
                d["tx"] = 100 + d["jx"] * 3
                d["ty"] = 5 if side == "home" else 80
                continue
            # Sim-authoritative spot: the sim decided this player is open,
            # converging on a battle, holding a formation lane, etc. Trust
            # it over our local formation guess. (Carrier sticks to the puck
            # and goalies keep their crease logic below.)
            pid = getattr(d.get("player"), "id", None)
            sp = self._sim_pos.get(pid) if pid is not None else None
            if (sp is not None and d["role"] != "G"
                    and d["id"] != self.carrier_id):
                d["tx"], d["ty"] = sp[0], sp[1]
                continue
            role, home = d["role"], d["is_home"]
            if role == "G":
                own = self._net_x(home, attacking=False)
                dist = abs(px - own)
                out = min(7.0, max(1.0, (34.0 - dist) * 0.28))
                toward = 1.0 if px >= own else -1.0
                d["tx"] = own + toward * out
                d["ty"] = 42.5 + max(-8, min(8, (py - 42.5) * 0.35))
                continue
            if d.get("nudge"):
                continue  # hit/battle lunge owns this dot briefly
            st = tstate[side]
            adir, anx, onx = st["adir"], st["anx"], st["onx"]
            has = st["has"]
            if d["id"] == self.carrier_id:
                if self._now() < d.get("rush_until", 0):
                    continue  # shot rush: his lane, not the puck, owns his feet
                d["tx"], d["ty"] = px, py
                continue
            jx, jy = d["jx"], d["jy"]
            tx, ty = None, None

            if has is None:
                # loose puck: two nearest race for it, everyone else holds
                # a neutral wedge -- a 1v1/2v2 battle, never a 10-man pile
                if d["id"] in st["check2"]:
                    k = sorted(st["check2"]).index(d["id"])
                    tx, ty = px + (k * 3 - 1.5) * adir, py + (k - 0.5) * 4
                elif st["dz"]:
                    tx, ty = self._slot_dz(role, adir, onx, py)
                else:
                    tx, ty = self._slot_nz(role, px, py, adir, onx)
            elif has and st["is_pp"]:
                tx, ty = self._slot_pp(role, adir, anx,
                                behind_net=((adir == 1 and px > anx - 28) or
                                            (adir == -1 and px < anx + 28)))
            elif has and st["oz"]:
                # 5v5 offensive formation follows the coach's tactic
                behind = ((adir == 1 and px > anx - 6) or
                          (adir == -1 and px < anx + 6))
                off = st["offense"]
                if role == "XF":
                    # extra attacker camps the net-front with the goalie out
                    tx, ty = anx - 14 * adir, 42.5
                elif off == "Umbrella":
                    # D walk the line, C high slot, wingers down low
                    if role == "C":
                        tx, ty = anx - 40 * adir, 42.5
                    elif role in ("LW", "RW"):
                        tx, ty = (anx - 22 * adir, 24.0) if role == "LW" \
                            else (anx - 22 * adir, 61.0)
                    else:
                        tx, ty = (anx - 57 * adir, 30.0) if role == "D1" \
                            else (anx - 57 * adir, 55.0)
                elif off == "Overload":
                    # numbers to the strong side
                    if role == "C":
                        tx, ty = anx - 26 * adir, 42.5
                    elif role in ("LW", "RW"):
                        mine = ((role == "LW") == (py < 42.5))
                        tx, ty = (anx - 24 * adir, strong_y) if mine \
                            else (anx - 44 * adir, weak_y)
                    elif role == "D1":
                        tx, ty = (anx - 40 * adir, strong_y)
                    else:
                        tx, ty = (anx - 54 * adir, 42.5)
                elif off == "Crash the Net":
                    # bodies on the doorstep, D bombing from the points
                    if role in ("C", "LW", "RW"):
                        s = {"C": 42.5, "LW": 38.0, "RW": 47.0}[role]
                        tx, ty = anx - 13 * adir, s
                    else:
                        tx, ty = (anx - 52 * adir, 30.0) if role == "D1" \
                            else (anx - 52 * adir, 55.0)
                else:
                    # Spread: slot + wide wingers + active points
                    if role == "C":
                        tx, ty = (anx - 13 * adir, 42.5) if behind else \
                            (anx - 27 * adir, 42.5)
                    elif role in ("LW", "RW"):
                        mine = ((role == "LW") == (py < 42.5))
                        if behind and mine:
                            tx, ty = anx - 30 * adir, strong_y
                        elif mine:
                            tx, ty = anx - 37 * adir, strong_y
                        else:
                            tx, ty = anx - 45 * adir, weak_y  # stay wide
                    else:
                        tx, ty = (anx - 57 * adir, 30.0) if role == "D1" \
                            else (anx - 57 * adir, 55.0)
            elif has:
                # breakout / regroup through the middle
                if role == "C":
                    tx, ty = px - 16 * adir, 42.5
                elif role in ("LW", "RW"):
                    mine = ((role == "LW") == (py < 42.5))
                    tx, ty = (px + 22 * adir, strong_y) if mine else \
                        (px + 30 * adir, weak_y)
                else:
                    tx, ty = (px - 10 * adir, 33.0) if role == "D1" else \
                        (px - 10 * adir, 52.0)
            elif st["is_pk"]:
                # tight box; nearest forward takes the point man only when
                # the puck is high
                if role in ("D1", "D2"):
                    s = 36.0 if role == "D1" else 49.0
                    tx, ty = onx + 12 * adir, s
                else:
                    high = ((adir == 1 and px > onx + 42) or
                            (adir == -1 and px < onx - 42))
                    if high and d["id"] == st["fcheck1"]:
                        tx, ty = px - 6 * adir, py
                    else:
                        tx, ty = onx + 25 * adir, 31.0 if role != "RW" else 54.0
            elif st["dz"]:
                # wedge + 1: D own the house, C the slot, wingers contain;
                # one checker pressures, nobody else dives in
                if d["id"] in st["check1"]:
                    tx, ty = px - 4 * adir, py
                elif role in ("D1", "D2"):
                    behind = ((adir == 1 and px < onx + 6) or
                              (adir == -1 and px > onx - 6))
                    s = 35.0 if role == "D1" else 50.0
                    tx, ty = (onx + 8 * adir, s) if behind else \
                        (onx + 13 * adir, s)
                elif role == "C":
                    tx, ty = onx + 22 * adir, 42.5
                else:
                    mine = ((role == "LW") == (py < 42.5))
                    tx, ty = (onx + 30 * adir, strong_y) if mine else \
                        (onx + 33 * adir, weak_y)
            elif st["oz"]:
                # Forecheck follows the coach's tactic: 2-1-2 sends two
                # hunters, 1-2-2 staggers F2/F3, 1-4 drops everyone back.
                fc = st["forecheck"]
                if role == "XF":
                    # extra attacker stays high as the safety valve
                    tx, ty = px - 22 * adir, 42.5
                elif fc == "1-4":
                    # one checker contains, four back toward neutral ice
                    if d["id"] == st["fcheck1"]:
                        tx, ty = px - 8 * adir, py
                    elif role in ("C", "LW", "RW"):
                        tx, ty = px - 26 * adir, 32.0 if role != "RW" else 53.0
                    else:
                        tx, ty = (anx - 62 * adir, 32.0) if role == "D1" else \
                            (anx - 62 * adir, 53.0)
                elif fc == "1-2-2":
                    # F1 pressures, F2/F3 stagger, D hold the line deeper
                    if d["id"] == st["fcheck1"]:
                        tx, ty = px, py
                    elif role in ("C", "LW", "RW"):
                        tx, ty = px - 16 * adir, 32.0 if role != "RW" else 53.0
                    else:
                        tx, ty = (anx - 55 * adir, 32.0) if role == "D1" else \
                            (anx - 55 * adir, 53.0)
                else:
                    # 2-1-2: two hunters, F3 high, D hold the line
                    hunters = st["fcheck2"]
                    if d["id"] in hunters:
                        if hunters[0] == d["id"]:
                            tx, ty = px, py
                        else:
                            tx, ty = px + 11 * adir, 42.5 + (py - 42.5) * 0.4
                    elif role in ("C", "LW", "RW"):
                        tx, ty = px + 24 * adir, 42.5
                    else:
                        tx, ty = (anx - 50 * adir, 32.0) if role == "D1" else \
                            (anx - 50 * adir, 53.0)
            else:
                # neutral zone 1-2-2: F1 pressures, F2/F3 clog the middle,
                # D gap up at their own blue line instead of backing in
                if d["id"] == st["fcheck1"]:
                    tx, ty = px - 5 * adir, py
                elif role in ("C", "LW", "RW"):
                    tx, ty = px - 13 * adir, 32.0 if role != "RW" else 53.0
                else:
                    tx, ty = (onx + 48 * adir, 32.0) if role == "D1" else \
                        (onx + 48 * adir, 53.0)
            d["tx"] = min(max(tx + jx, 5), 195)
            d["ty"] = min(max(ty + jy, 5), 80)

        # ---- separation: teammates never share a phone booth ----
        for home in (True, False):
            mates = [d for d in self.dots.values()
                     if d["is_home"] == home and d["role"] != "G"
                     and d["id"] not in self.penalty_box]
            for _ in range(2):
                for i in range(len(mates)):
                    for j in range(i + 1, len(mates)):
                        a, b = mates[i], mates[j]
                        dx, dy = b["tx"] - a["tx"], b["ty"] - a["ty"]
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist >= 8.0 or dist < 0.01:
                            continue
                        ux, uy = dx / dist, dy / dist
                        push = (8.0 - dist)
                        a_anchor = a["id"] == self.carrier_id
                        b_anchor = b["id"] == self.carrier_id
                        if not a_anchor:
                            sh = push if b_anchor else push / 2
                            a["tx"] -= ux * sh
                            a["ty"] -= uy * sh
                        if not b_anchor:
                            sh = push if a_anchor else push / 2
                            b["tx"] += ux * sh
                            b["ty"] += uy * sh
            for d in mates:
                d["tx"] = min(max(d["tx"], 5), 195)
                d["ty"] = min(max(d["ty"], 5), 80)

    def _slot_dz(self, role, adir, onx, py):
        """Defensive-zone wedge slot for a non-checker (role discipline)."""
        strong_y, weak_y = (24.0, 61.0) if py < 42.5 else (61.0, 24.0)
        if role in ("D1", "D2"):
            return (onx + 13 * adir, 35.0 if role == "D1" else 50.0)
        if role == "C":
            return (onx + 22 * adir, 42.5)
        mine = (role == "LW") == (py < 42.5)
        return ((onx + 30 * adir, strong_y) if mine
                else (onx + 33 * adir, weak_y))

    def _slot_nz(self, role, px, py, adir, onx):
        """Neutral-zone 1-2-2 slot: clog the middle, D gap at the line."""
        if role in ("C", "LW", "RW"):
            return (px - 13 * adir, 32.0 if role != "RW" else 53.0)
        return (onx + 48 * adir, 32.0 if role == "D1" else 53.0)

    def _slot_pp(self, role, adir, anx, behind_net):
        """Power-play umbrella slot."""
        if role == "C":
            return ((anx - 14 * adir, 42.5) if behind_net
                    else (anx - 33 * adir, 42.5))
        if role == "LW":
            return (anx - 40 * adir, 22.0)
        if role == "RW":
            return (anx - 40 * adir, 63.0)
        return (anx - 58 * adir, 30.0 if role == "D1" else 55.0)

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

    @staticmethod
    def _gname(p):
        """Short goalie name for the stats strip (last name only)."""
        if p is None:
            return "?"
        last = getattr(p, "last_name", "") or getattr(p, "full_name", "?")
        return str(last).split()[-1][:12]

    # ------------------------------------------------------------------
    # Event application
    # ------------------------------------------------------------------
    def _consume(self, ev):
        et = ev["type"]
        if et == "game_start":
            self._update_scoreboard(ev)
            if not self._instant:
                hab = _abbr(self.home_team.team_name)
                aab = _abbr(self.away_team.team_name)
                self._card_show("PUCK DYNASTY", f"{hab}  vs  {aab}", hold=2.8)
        elif et == "period_start":
            self.penalty_box.clear()
            self._penalty_timers.clear()
            for d in self.dots.values():
                self._set_dot_visible(d, True)
            self._period_stats = {"shots": {"home": 0, "away": 0},
                                  "goals": {"home": 0, "away": 0},
                                  "notes": []}
            self._shotmap = []
            self._last_shot = None
            self._redraw_shotmap()
            self._feed(f"Start of period {ev.get('period', 1)}.", tag="period", ev=ev)
            self._faceoff_formation(100, 42.5, winner_is_home=True)
            self.possession_home = None
            self.carrier_id = None
            self._update_scoreboard(ev)
            p = ev.get("period", 1)
            if p > 1 and not self._instant:
                ords = {2: "2ND", 3: "3RD"}
                pl = ords.get(p, f"{p}TH")
                hs, aws = self._cur_score
                self._card_show(f"{pl} PERIOD",
                                f"{_abbr(self.home_team.team_name)} {hs} – "
                                f"{aws} {_abbr(self.away_team.team_name)}")
        elif et == "period_end":
            self._feed(f"End of period {ev.get('period', 1)}. "
                       f"{self.home_team.team_name} {ev['home_score']} - "
                       f"{ev['away_score']} {self.away_team.team_name}.",
                       tag="period", ev=ev)
            self._insert_period_summary(ev)
            self._update_scoreboard(ev)
            if not self._instant:
                p = ev.get("period", 1)
                ords = {1: "1ST", 2: "2ND", 3: "3RD"}
                pl = ords.get(p, f"{p}TH")
                self._card_show(f"END OF {pl}",
                                f"{_abbr(self.home_team.team_name)} "
                                f"{ev['home_score']} – {ev['away_score']} "
                                f"{_abbr(self.away_team.team_name)}")
        elif et == "faceoff":
            self._on_faceoff(ev)
        elif et == "goalie_pulled":
            self._on_goalie_pulled(ev)
        elif et == "goalie_back":
            self._on_goalie_back(ev)
        elif et == "shot":
            self._on_shot(ev)
        elif et in ("goal", "save", "blocked_shot", "missed_shot"):
            self._stage_outcome(ev)
        elif et == "hit":
            self._on_hit(ev)
        elif et == "penalty":
            self._on_penalty(ev)
        elif et == "delayed_penalty":
            self._on_delayed_penalty(ev)
        elif et == "goalie_freeze":
            self._feed(f"{self._pname(ev.get('goalie'))} covers the puck -- "
                       f"faceoff coming up in the {ev.get('team', '')} zone.",
                       tag="info", ev=ev)
        elif et == "fight":
            self._on_fight(ev)
        elif et == "milestone":
            self._on_milestone(ev)
        elif et == "icing":
            self._feed(random.choice(_ICING_T).format(
                team=ev.get("team", "")), tag="info", ev=ev)
        elif et == "offside":
            if ev.get("intentional"):
                self._feed(f"Intentional offside on {ev.get('team', '')} -- "
                           f"the faceoff comes all the way back.", tag="info", ev=ev)
            else:
                self._feed(random.choice(_OFFSIDE_T).format(
                    team=ev.get("team", "")), tag="info", ev=ev)
        elif et == "penalty_shot":
            self._feed(f"Penalty shot awarded: {self._pname(ev.get('player'))} "
                       f"({ev.get('team', '')})…", tag="shot", ev=ev)
        elif et == "skate":
            self._on_skate(ev)
        elif et == "pass":
            self._on_pass(ev)
        elif et == "battle":
            self._on_battle(ev)
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
            self._show_stars()
            if not self._complete_fired:
                self._complete_fired = True
                cb = self.on_complete
                sim = self.sim
                if cb is not None:
                    self.after(500, lambda: cb(sim))

    def _on_skate(self, ev):
        """Sim movement snapshot: the sim's tactical engine positions every
        skater (who got open, battle piles, formation shapes). Those spots
        are authoritative -- _update_targets sends dots to them -- so the
        picture matches the sim's brain. The sim's on-ice units are
        authoritative too: the dots are synced to the sim's actual players
        (line rotation, PP/PK, icing, matching)."""
        pk = ev.get("puck")
        if pk:
            self.puck_target = (pk[0], pk[1])
        pos = ev.get("positions")
        if pos:
            self._sim_pos = {pid: (p[0], p[1]) for pid, p in pos.items()}
        # Tactical jobs from the sim: what each skater is TRYING to do
        # (f1_pressure, slot, point, ...). The visualizer is a view of the
        # sim, so it reads intent instead of guessing it.
        jobs = ev.get("jobs")
        if jobs:
            self._sim_jobs = dict(jobs)
        # Team phases: the plan each unit is executing (oz_attack,
        # dz_coverage, forecheck, ...). Drives the tactic legibility overlay.
        phases = ev.get("phases")
        if phases:
            self._sim_phases = dict(phases)
        for is_home, key in ((True, "on_ice_home"), (False, "on_ice_away")):
            ids = ev.get(key)
            if ids:
                self._sync_dots_to_sim(is_home, ids)
        cpid = ev.get("possession_player")
        d = self._dot_by_id(cpid)
        if d is None and cpid is not None:
            # transient sim state (e.g. a line change resolving mid-tick):
            # the puck carrier is always shown, slotted by position
            d = self._force_carrier_dot(cpid)
        self.carrier_id = d["id"] if d else None

    def _force_carrier_dot(self, cpid):
        """Slot an undotted puck carrier into his position's dot so the
        carrier ring never loses him during transient sim states."""
        player, is_home = None, True
        for ih, team in ((True, self.home_team), (False, self.away_team)):
            for p in team.roster:
                if getattr(p, "id", None) == cpid:
                    player, is_home = p, ih
                    break
            if player is not None:
                break
        if player is None:
            return None
        want = getattr(getattr(player, "primary_position", None), "name", "")
        role_pos = {"C": "CENTER", "LW": "LEFT_WING", "RW": "RIGHT_WING",
                    "D1": "LEFT_DEFENSE", "D2": "RIGHT_DEFENSE"}
        dots = [d for d in self.dots.values()
                if d["is_home"] == is_home and d["role"] != "G"]
        d = next((x for x in dots
                  if role_pos.get(x["role"]) == want), None)
        if d is None and dots:
            d = dots[0]
        if d is None:
            return None
        d["player"] = player
        num = getattr(player, "jersey_number", None) or "-"
        try:
            self.canvas.itemconfig(d["text"], text=str(num))
        except Exception:
            pass
        return d

    def _sync_dots_to_sim(self, is_home, ids):
        """Remap the skater dots to the sim's on-ice player ids,
        slotting each into the role that best fits his position.
        With the goalie pulled, the goalie dot becomes the 6th skater
        (XF, extra forward); it reverts when the goalie returns."""
        goalie_dot = next((d for d in self.dots.values()
                           if d["is_home"] == is_home and d["role"] == "G"),
                          None)
        if len(ids) >= 6 and goalie_dot is not None:
            goalie_dot["role"] = "XF"
            goalie_dot["r"] = 13
        else:
            xf = next((d for d in self.dots.values()
                       if d["is_home"] == is_home and d["role"] == "XF"),
                      None)
            if xf is not None:
                xf["role"] = "G"
                xf["r"] = 15
        dots = [d for d in self.dots.values()
                if d["is_home"] == is_home and d["role"] not in ("G", "XF")]
        if not dots:
            return
        cur = {getattr(d["player"], "id", None) for d in dots}
        xf_dot = next((d for d in self.dots.values()
                       if d["is_home"] == is_home and d["role"] == "XF"), None)
        if xf_dot is not None:
            cur.add(getattr(xf_dot["player"], "id", None))
        if cur == set(ids):
            return
        team = self.home_team if is_home else self.away_team
        by_id = {getattr(p, "id", None): p for p in team.roster}
        players = [by_id[i] for i in ids if i in by_id]
        if len(players) < 5:
            have = {getattr(p, "id", None) for p in players}
            for d in dots:
                if len(players) >= 5:
                    break
                p = d["player"]
                if getattr(p, "id", None) not in have:
                    players.append(p)
                    have.add(getattr(p, "id", None))
        remaining = list(players)
        if xf_dot is not None and remaining:
            # extra attacker: best remaining forward on the XF dot
            def _is_fwd(p):
                return getattr(getattr(p, "primary_position", None),
                               "name", "") in ("CENTER", "LEFT_WING",
                                               "RIGHT_WING")
            fwds = [p for p in remaining if _is_fwd(p)]
            pick = fwds[0] if fwds else remaining[0]
            remaining.remove(pick)
            if getattr(xf_dot["player"], "id", None) != getattr(pick, "id", None):
                xf_dot["player"] = pick
                num = getattr(pick, "jersey_number", None) or "-"
                try:
                    self.canvas.itemconfig(xf_dot["text"], text=str(num))
                except Exception:
                    pass
        role_pos = {"C": "CENTER", "LW": "LEFT_WING", "RW": "RIGHT_WING",
                    "D1": "LEFT_DEFENSE", "D2": "RIGHT_DEFENSE"}
        for role in ("C", "LW", "RW", "D1", "D2"):
            d = next((x for x in dots if x["role"] == role), None)
            if d is None or not remaining:
                continue
            want = role_pos[role]
            pick = next((p for p in remaining
                         if getattr(getattr(p, "primary_position", None),
                                     "name", "") == want),
                        remaining[0])
            remaining.remove(pick)
            if getattr(d["player"], "id", None) != getattr(pick, "id", None):
                d["player"] = pick
                num = getattr(pick, "jersey_number", None) or "-"
                try:
                    self.canvas.itemconfig(d["text"], text=str(num))
                except Exception:
                    pass

    def _on_pass(self, ev):
        pp = ev.get("passer_pos") or (100.0, 42.5)
        rp = ev.get("receiver_pos") or (100.0, 42.5)
        pd = self._dot_by_player(ev.get("passer"))
        rd = self._dot_by_player(ev.get("receiver"))
        sx, sy = (pd["x"], pd["y"]) if pd else (pp[0], pp[1])
        # The puck flies to the sim's receiver spot -- the patch of ice the
        # receiver actually skated to to get open -- and his dot is sent
        # there now so the pass visibly hits a man in space. On a pickoff
        # it goes to the defender who read it instead.
        if ev.get("completed"):
            rx, ry = rp[0], rp[1]
            if rd is not None:
                rd["tx"], rd["ty"] = rx, ry
        else:
            ide = self._dot_by_player(ev.get("interceptor"))
            if ide is not None:
                rx, ry = ide["x"], ide["y"]
            elif rd is not None:
                rx, ry = rd["x"], rd["y"]
            else:
                rx, ry = rp[0], rp[1]
        if self._instant:
            d = self._dot_by_player(ev.get("receiver") if ev.get("completed")
                                    else ev.get("interceptor"))
            self.carrier_id = d["id"] if d else None
            self.puck["x"], self.puck["y"] = rx, ry
        else:
            self.puck_flight = (sx, sy, rx, ry, self._now(), 0.45, None)
            self._pass_arrival = ev
            self.carrier_id = None  # puck in transit
        self.puck_target = None
        if ev.get("completed"):
            extra = " (got open)" if ev.get("got_open") else ""
            self._feed(random.choice(_PASS_T).format(
                P=self._pname(ev.get("passer")),
                R=self._pname(ev.get("receiver")), extra=extra), ev=ev)
        else:
            self._feed(f"Pass by {self._pname(ev.get('passer'))} picked off by "
                       f"{self._pname(ev.get('interceptor'))}!", tag="penalty", ev=ev)

    def _on_battle(self, ev):
        spot = ev.get("puck_spot") or (100.0, 42.5)
        now = self._now()
        for key in ("player_a", "player_b"):
            d = self._dot_by_player(ev.get(key))
            if d:
                d["nudge"] = (spot[0], spot[1], now + 0.5)
        w = self._dot_by_player(ev.get("winner"))
        self._feed(random.choice(_BATTLE_T).format(
            W=self._pname(ev.get("winner"))), ev=ev)
        if self._instant:
            self.carrier_id = w["id"] if w else None
            self.puck["x"], self.puck["y"] = spot[0], spot[1]
        else:
            self._battle_winner = w["id"] if w else None
            self._battle_settle_at = now + 0.55
            self.hold_until = max(self.hold_until, now + 0.55)

    def _on_goalie_pulled(self, ev):
        """Broadcast the empty-net gamble: feed line + EN on the bug."""
        home = ev.get("team") == self.home_team.team_name
        self._en["home" if home else "away"] = True
        self._feed(f"{ev.get('team', '')} pull the goalie -- extra attacker "
                   f"on with {ev.get('home_score', 0)}-{ev.get('away_score', 0)} "
                   f"on the board.", tag="info", ev=ev)
        self._update_scoreboard(ev)

    def _on_goalie_back(self, ev):
        home = ev.get("team") == self.home_team.team_name
        self._en["home" if home else "away"] = False
        self._update_scoreboard(ev)

    def _on_faceoff(self, ev):
        winner_is_home = ev["winner_team"] == self.home_team.team_name
        # The sim now ships the exact NHL faceoff dot (faceoff_x/faceoff_y);
        # fall back to the old zone heuristic for legacy events.
        fx, fy = ev.get("faceoff_x"), ev.get("faceoff_y")
        if fx is None or fy is None:
            dx, dy = faceoff_dot(ev.get("zone", "neutral_zone"), winner_is_home)
        else:
            dx, dy = fx, fy
        if self._instant:
            # fast path (sim-to-end / big-moment jump): no faceoff pause
            self._faceoff_formation(dx, dy, winner_is_home, teleport=False)
            self.possession_home = winner_is_home
            w = self._dot_by_player(ev.get("winner_player"))
            self.carrier_id = w["id"] if w else None
            zone = ev.get("zone", "").replace("_", " ")
            self._feed(random.choice(_FACEOFF_T).format(
                zone=zone, W=self._pname(ev.get("winner_player"))), ev=ev)
            self._bump_stat("home" if winner_is_home else "away", "FO")
            self._pstat(ev.get("winner_player"), "FO")
            self._update_scoreboard(ev)
            return
        # Broadcast faceoff: whistle freeze -> glide to the dot ->
        # set formation -> puck drop. Quick at every stoppage; the sim
        # supplies the NHL-correct dot for the whistle.
        self._cancel_faceoff_ceremony()
        # a goal celebration still running is over; everyone lines up
        self._celly = None
        self._celly_pending = None
        for d in self.dots.values():
            d["converge"] = None
            d["glunge"] = None
            d["ceremony_glide"] = False
            d["tx"], d["ty"] = d["x"], d["y"]  # freeze on the whistle
        # flush any in-flight shot outcome: a faceoff always follows a goal,
        # and silently discarding the pending outcome would lose goals
        if self.pending_outcome is not None:
            oc = self.pending_outcome
            self.pending_outcome = None
            self.puck_flight = None
            self._apply_outcome(oc)
        else:
            self.puck_flight = None
            self.pending_outcome = None
        self.carrier_id = None
        self.possession_home = None
        if self._sound_on and self._sfx is not None:
            try:
                self._sfx.whistle()
            except Exception:
                pass
        self._faceoff_ceremony = {
            "el": 0.0, "phase": "whistle",
            "dx": dx, "dy": dy,
            "winner_is_home": winner_is_home,
            "ev": ev,
            "puck_from": (self.puck["x"], self.puck["y"]),
        }
        self.hold_until = max(self.hold_until,
                              self._now() + self._FO_TOTAL + 0.2)

    def _cancel_faceoff_ceremony(self):
        """Drop ceremony state (jump/sim-to-end); dots keep current targets."""
        if self._faceoff_ceremony is None:
            return
        self._faceoff_ceremony = None
        for d in self.dots.values():
            d["ceremony_glide"] = False

    def _step_faceoff_ceremony(self):
        """Advance the faceoff ceremony one tick (only while playing)."""
        c = self._faceoff_ceremony
        if c is None or not self.playing:
            return
        c["el"] += 0.05
        el = c["el"]
        if el < self._FO_WHISTLE:
            return  # whistle freeze: everyone stopped
        if c["phase"] == "whistle":
            # skate to the dot with a slow deliberate glide
            spots = self._faceoff_spots(c["dx"], c["dy"],
                                        c["winner_is_home"])
            for did, (x, y) in spots.items():
                d = self.dots.get(did)
                if d:
                    d["tx"] = min(max(x, 6), 194)
                    d["ty"] = min(max(y, 6), 79)
                    d["ceremony_glide"] = True
            c["phase"] = "lineup"
        elif c["phase"] == "lineup":
            # linesman carries the puck to the dot
            k = min(1.0, (el - self._FO_WHISTLE) / self._FO_LINEUP)
            fx, fy = c["puck_from"]
            self.puck["x"] = fx + (c["dx"] - fx) * k
            self.puck["y"] = fy + (c["dy"] - fy) * k
            if el >= self._FO_WHISTLE + self._FO_LINEUP:
                c["phase"] = "set"
                for d in self.dots.values():
                    d["ceremony_glide"] = False
        elif c["phase"] == "set":
            if el >= self._FO_WHISTLE + self._FO_LINEUP + self._FO_SET:
                c["phase"] = "drop"
        elif c["phase"] == "drop":
            # puck-drop hop, then the winner takes possession
            k = ((el - self._FO_WHISTLE - self._FO_LINEUP - self._FO_SET)
                 / self._FO_DROP)
            if k < 1.0:
                self.puck["x"] = c["dx"]
                self.puck["y"] = c["dy"] - math.sin(k * math.pi) * 2.5
            else:
                self._finalize_faceoff()

    def _finalize_faceoff(self):
        """Puck is down: award possession, announce the draw winner."""
        c = self._faceoff_ceremony
        self._faceoff_ceremony = None
        if c is None:
            return
        ev = c["ev"]
        winner_is_home = c["winner_is_home"]
        self.puck["x"], self.puck["y"] = c["dx"], c["dy"]
        self.possession_home = winner_is_home
        w = self._dot_by_player(ev.get("winner_player"))
        self.carrier_id = w["id"] if w else None
        if w:
            w["tx"], w["ty"] = self.puck["x"], self.puck["y"]
        zone = ev.get("zone", "").replace("_", " ")
        self._feed(random.choice(_FACEOFF_T).format(
            zone=zone, W=self._pname(ev.get("winner_player"))), ev=ev)
        self._bump_stat("home" if winner_is_home else "away", "FO")
        self._pstat(ev.get("winner_player"), "FO")
        self._update_scoreboard(ev)

    def _on_shot(self, ev):
        att_home = ev["attacking_team"] == self.home_team.team_name
        side = "home" if att_home else "away"
        self._bump_stat(side, "Shots")
        self._period_stats["shots"][side] += 1
        self._push_momentum(side, 1)
        self._pstat(ev.get("shooter"), "SOG")
        self._trail_color = ACCENT if att_home else AWAY_COLOR
        shooter_dot = self._dot_by_player(ev.get("shooter"))
        sp = ev.get("shooter_pos")
        rush = False
        if sp is not None:
            # Authoritative: the sim put the shooter at his shooting spot
            # as the chance developed. Trust it over the dot's lagging
            # visual position so shots never start from the wrong ice.
            sx, sy = sp[0], sp[1]
            if shooter_dot and not self._instant:
                dist = math.hypot(shooter_dot["x"] - sx,
                                  shooter_dot["y"] - sy)
                if dist > 4.0:
                    # He skates into his lane and lets it go -- no teleport.
                    # Rush there, release on arrival; capped so the
                    # broadcast keeps pace. The puck rides his stick meanwhile.
                    delay = min(0.6, dist / 45.0)
                    fire_at = self._now() + delay
                    shooter_dot["tx"], shooter_dot["ty"] = sx, sy
                    shooter_dot["rush_until"] = fire_at
                    self._pending_shot = {
                        "sx": sx, "sy": sy, "side": side,
                        "att_home": att_home,
                        "shooter_id": shooter_dot["id"],
                        "fire_at": fire_at,
                    }
                    self.hold_until = max(self.hold_until, fire_at + 0.05)
                    rush = True
            if not rush and shooter_dot:
                self._move_dot(shooter_dot, sx, sy)
                shooter_dot["tx"], shooter_dot["ty"] = sx, sy
        elif shooter_dot:
            sx, sy = shooter_dot["x"], shooter_dot["y"]
        else:
            sx, sy = shot_spot(ev.get("location", "high_slot"), att_home)
        self._last_shot = (sx, sy, side)
        nx = AWAY_NET_X if att_home else HOME_NET_X
        self.possession_home = att_home
        self.carrier_id = shooter_dot["id"] if shooter_dot else None
        # flush any still-pending outcome from a previous shot: a quick
        # second shot must not silently drop the first shot's outcome.
        # (A goal flushed here is mid-action — save its highlight but don't
        # hijack the broadcast with a replay for it.)
        if self.pending_outcome is not None and not self._instant:
            oc = self.pending_outcome
            self.pending_outcome = None
            self._no_replay_once = True
            try:
                self._apply_outcome(oc)
            finally:
                self._no_replay_once = False
        # peek: the outcome event should already be in the stream
        outcome = None
        if self.cursor < len(self.events):
            nxt = self.events[self.cursor]
            if nxt["type"] in ("goal", "save", "blocked_shot", "missed_shot"):
                outcome = nxt
                self.cursor += 1
                self.playhead = max(self.playhead, outcome.get("t", self.playhead))
        self.puck_flight = None
        if self._instant:
            # sim-to-end: apply immediately, no animation
            self.pending_outcome = None
            if outcome:
                self._apply_outcome(outcome)
                self._scatter_puck(outcome)
        elif rush:
            # the flight launches from _step once the shooter skates in
            self._pending_shot["nx"] = nx
            self._pending_shot["outcome"] = outcome
            self.pending_outcome = outcome
        else:
            self._fire_shot(sx, sy, nx, outcome)
        st = ev.get("shot_type", "").replace("_", " ")
        self._feed(f"{st.title()} by {self._pname(ev.get('shooter'))} "
                   f"from {ev.get('location', '').replace('_', ' ')}…",
                   tag="shot", ev=ev)
        # goalie reaction: exaggerated lunge toward the shot line
        # (on a rush, he reads the wind-up and is set for the release)
        if not self._instant:
            gpid = self._cur_goalie.get("away" if att_home else "home")
            gd = self._dot_by_id(gpid) if gpid else None
            if gd:
                gx = AWAY_NET_X if att_home else HOME_NET_X
                lx = gx + (-4.0 if att_home else 4.0)
                ly = 42.5 + (sy - 42.5) * 0.35
                lunge_t = self._now() + 0.5
                if rush and self._pending_shot is not None:
                    lunge_t = self._pending_shot["fire_at"] + 0.5
                gd["glunge"] = (lx, ly, lunge_t)

    def _fire_shot(self, sx, sy, nx, outcome):
        """Launch the puck flight once the shooter has his lane."""
        self.puck_flight = (sx, sy, nx, 42.5, self._now(), 0.45, outcome)
        self.pending_outcome = outcome

    def _step_pending_shot(self, now):
        ps = self._pending_shot
        if ps is None:
            return
        if now >= ps["fire_at"] or self._faceoff_ceremony:
            self._pending_shot = None
            d = self.dots.get(ps["shooter_id"])
            if d is not None:
                # arrive exactly on the spot; the gap is sub-foot by now
                self._move_dot(d, ps["sx"], ps["sy"])
                d["tx"], d["ty"] = ps["sx"], ps["sy"]
                d.pop("rush_until", None)
            self._fire_shot(ps["sx"], ps["sy"], ps["nx"], ps["outcome"])

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
            self._push_momentum("home" if att_home else "away", 3)
            self._period_stats["goals"]["home" if att_home else "away"] += 1
            msg = self._goal_text(ev)
            self._feed(msg, tag="goal", ev=ev)
            self._note("goal", msg, ev)
            if not ev.get("empty_net"):
                self._goalie_shot(side, scored=True)
            self._pstat(ev.get("shooter"), "G")
            for a in ev.get("assists") or []:
                self._pstat(a, "A")
            self._record_shotmap("goal")
            self._save_highlight(ev, "goal")
            self._maybe_start_goal_replay(ev)
            self._celebrate_goal(ev, att_home)
            self.hold_until = max(self.hold_until, self._now() + 1.6)
            self.possession_home = None
            self.carrier_id = None
            self._update_scoreboard(ev)
        elif et == "save":
            msg = self._save_text(ev)
            self._feed(msg, ev=ev)
            side = self._player_side(ev.get("goalie"), ev, "defending_team")
            self._goalie_shot(side, goalie=ev.get("goalie"), scored=False)
            self._record_shotmap("save")
            # goalie covers: defending team keeps it
            self.possession_home = (side == "home")
            self.carrier_id = None
            self._update_scoreboard(ev)
        elif et == "blocked_shot":
            B = self._pname(ev.get("blocker"))
            S = self._pname(ev.get("shooter"))
            self._feed(random.choice(_BLOCK_T).format(B=B, S=S), ev=ev)
            self._record_shotmap("block")
            def_home = ev.get("defending_team") == self.home_team.team_name
            self.possession_home = def_home
            self.carrier_id = None
        elif et == "missed_shot":
            S = self._pname(ev.get("shooter"))
            st = (ev.get("shot_type") or "").replace("_", " ")
            how = f" {st}" if st else ""
            self._feed(random.choice(_MISS_T).format(S=S, how=how), ev=ev)
            self._record_shotmap("miss")
            att_home = ev.get("attacking_team") == self.home_team.team_name
            self.possession_home = att_home

    # ------------------------------------------------------------------
    # Broadcast replays & highlights
    # ------------------------------------------------------------------
    def _celebrate_goal(self, ev, att_home):
        """Goal sequence: lower-third, horn, flash, shake, celly, converge."""
        if self._instant:
            return
        now = self._now()
        color = ACCENT if att_home else AWAY_COLOR
        S = self._pname(ev.get("shooter"))
        ast = ev.get("assists") or []
        sub = S
        if ast:
            sub += "  (assists: " + ", ".join(self._pname(a) for a in ast) + ")"
        sub += f"   {ev.get('home_score', 0)}-{ev.get('away_score', 0)}"
        self._banner_show("goal", "GOAL!", sub, color=color)
        if self._sound_on and self._sfx is not None:
            try:
                self._sfx.goal_horn()
            except Exception:
                pass
        self._shake(mag=6.0, dur=0.7)
        self._flash_until = now + 0.14
        # beaten goalie flashes red
        gpid = self._cur_goalie.get("away" if att_home else "home")
        gd = self._dot_by_id(gpid) if gpid else None
        if gd:
            gd["beaten_until"] = now + 0.9
        # the on-ice celly waits for the slow-mo replay to finish so the
        # lap and the mob are actually visible
        if self._replay:
            self._celly_pending = (ev.get("shooter"), att_home)
        else:
            self._start_celly(ev.get("shooter"), att_home)

    def _start_celly(self, shooter, att_home):
        """Scorer's victory lap + teammates mobbing him."""
        now = self._now()
        sd = self._dot_by_player(shooter)
        if not sd:
            return
        self._celly = {"dot": sd, "until": now + 2.0,
                       "cx": sd["x"], "cy": sd["y"], "t0": now}
        # nearby teammates converge on the scorer (per-tick override,
        # applied after _update_targets so formations don't undo it)
        for d in self.dots.values():
            if d is sd or d["is_home"] != att_home:
                continue
            if (d["x"] - sd["x"]) ** 2 + (d["y"] - sd["y"]) ** 2 > 45 ** 2:
                continue
            try:
                if self.canvas.itemcget(d["oval"], "state") == "hidden":
                    continue
            except Exception:
                pass
            ang = random.uniform(0, 6.28)
            d["converge"] = (sd["x"] + math.cos(ang) * 6,
                             sd["y"] + math.sin(ang) * 6,
                             now + 2.2)

    def _recent_frames(self, n=90):
        """Last n recorded snapshots (~n*50ms of viewed action).

        Tick-based (not game-clock-based) so replays work at any speed.
        """
        h = self._history
        return list(h)[-n:] if len(h) > n else list(h)

    @staticmethod
    def _interp_frames(frames, t):
        """Interpolate dot/puck positions at game-time t from frames."""
        if not frames:
            return None
        if t <= frames[0][0]:
            f = frames[0]
            return dict(f[1]), f[2], f[3], f[4]
        for i in range(1, len(frames)):
            t0, t1 = frames[i - 1][0], frames[i][0]
            if t0 <= t <= t1:
                fa, fb = frames[i - 1], frames[i]
                k = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
                pos = {}
                for did, (xa, ya) in fa[1].items():
                    xb, yb = fb[1].get(did, (xa, ya))
                    pos[did] = (xa + (xb - xa) * k, ya + (yb - ya) * k)
                px = fa[2][0] + (fb[2][0] - fa[2][0]) * k
                py = fa[2][1] + (fb[2][1] - fa[2][1]) * k
                return pos, (px, py), fa[3], fa[4]
        f = frames[-1]
        return dict(f[1]), f[2], f[3], f[4]

    def _start_replay(self, frames, label):
        if len(frames) < 3 or self._replay:
            return False
        start_t, end_t = frames[0][0], frames[-1][0]
        # real-seconds of footage, played at REPLAY_RATE, capped
        dur = max(2.0, min(9.0, len(frames) * 0.05 / REPLAY_RATE))
        self._replay = {"frames": frames, "rt": 0.0, "dur": dur,
                        "start_t": start_t, "end_t": end_t, "label": label}
        self.hold_until = max(self.hold_until, self._now() + dur + 0.4)
        self.canvas.itemconfig(self._replay_dot, state="normal")
        self.canvas.itemconfig(self._replay_text, state="normal")
        self._feed(f"REPLAY: {label}", tag="info")
        return True

    def _step_replay(self):
        rp = self._replay
        if rp is None:
            return
        rp["rt"] += 0.05
        frac = min(1.0, rp["rt"] / rp["dur"])
        t = rp["start_t"] + (rp["end_t"] - rp["start_t"]) * frac
        interp = self._interp_frames(rp["frames"], t)
        if interp:
            pos, (px, py), hs, aws = interp
            for did, (x, y) in pos.items():
                d = self.dots.get(did)
                if d:
                    self._move_dot(d, x, y)
            self.puck["x"], self.puck["y"] = px, py
            self.score_var.set(f"{hs} – {aws}")
        if rp["rt"] >= rp["dur"]:
            self._end_replay()

    def _end_replay(self):
        if not self._replay:
            return
        self._replay = None
        self.canvas.itemconfig(self._replay_dot, state="hidden")
        self.canvas.itemconfig(self._replay_text, state="hidden")
        # snap dots back to live targets so playback resumes cleanly
        for d in self.dots.values():
            self._move_dot(d, d["tx"], d["ty"])
        self.hold_until = 0
        self._update_scoreboard()
        # a goal's on-ice celebration was waiting for the replay
        if getattr(self, "_celly_pending", None):
            shooter, att_home = self._celly_pending
            self._celly_pending = None
            self._start_celly(shooter, att_home)

    def _cancel_replay(self):
        self._end_replay()

    def _maybe_start_goal_replay(self, ev):
        if self._instant or self._replay:
            return
        if getattr(self, "_no_replay_once", False):
            return
        frames = self._recent_frames(80)
        self._start_replay(frames, self._goal_text(ev))

    def _save_highlight(self, ev, kind, label=None):
        t = ev.get("t", self.playhead)
        frames = self._recent_frames(110)
        if len(frames) < 3:
            return
        # during instant consume the history is stale; don't clip wrong action
        if abs(frames[-1][0] - t) > 30:
            return
        pid = None
        if kind == "goal":
            label = label or self._goal_text(ev)
            pid = getattr(ev.get("shooter"), "id", None)
        elif kind == "fight":
            label = label or f"Fight: {self._pname(ev.get('player'))}"
            pid = getattr(ev.get("player"), "id", None)
        self._highlights.append({"start_t": frames[0][0],
                                 "end_t": frames[-1][0],
                                 "label": label or kind, "pid": pid,
                                 "frames": frames, "kind": kind})

    def _play_highlight(self, h):
        self._cancel_replay()
        self.playing = False
        self._refresh_play_btn()
        self._start_replay(h["frames"], h["label"])

    # ------------------------------------------------------------------
    # Shot map overlay
    # ------------------------------------------------------------------
    def _record_shotmap(self, result):
        if self._last_shot is None:
            return
        x, y, side = self._last_shot
        self._last_shot = None
        self._shotmap.append((x, y, side, result))
        if self._shotmap_on:
            self._redraw_shotmap()

    def _toggle_shotmap(self):
        self._shotmap_on = not self._shotmap_on
        self._redraw_shotmap()
        self._refresh_toggle_btn(self.shotmap_btn, self._shotmap_on)

    def _redraw_shotmap(self):
        c = self.canvas
        c.delete("shotmap")
        if not self._shotmap_on:
            return
        for x, y, side, result in self._shotmap:
            px, py = self.X(x), self.Y(y)
            if result == "goal":
                col = "#00ff9d"
                r = 7
                c.create_line(px - r, py, px + r, py, fill=col, width=2,
                              tags=("shotmap", "fx"))
                c.create_line(px, py - r, px, py + r, fill=col, width=2,
                              tags=("shotmap", "fx"))
                c.create_line(px - r * 0.7, py - r * 0.7, px + r * 0.7,
                              py + r * 0.7, fill=col, width=2, tags=("shotmap", "fx"))
                c.create_line(px - r * 0.7, py + r * 0.7, px + r * 0.7,
                              py - r * 0.7, fill=col, width=2, tags=("shotmap", "fx"))
            elif result == "save":
                col = ACCENT if side == "home" else AWAY_COLOR
                c.create_oval(px - 4, py - 4, px + 4, py + 4, fill=col,
                              outline="white", width=1, tags=("shotmap", "fx"))
            elif result == "block":
                c.create_rectangle(px - 4, py - 4, px + 4, py + 4,
                                   fill="#8a8f9c", outline="", tags=("shotmap", "fx"))
            else:  # miss
                c.create_text(px, py, text="x", fill="#c9ced8",
                              font=(FONT, 10, "bold"), tags=("shotmap", "fx"))
        # keep markers under the player dots
        try:
            first = next(iter(self.dots.values()))
            c.tag_lower("shotmap", first["shadow"])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Lower-third banners & full-rink broadcast cards (viewport space)
    # ------------------------------------------------------------------
    def _banner_show(self, kind, title, sub="", color=ACCENT):
        """Slide-in lower third; replaces any live banner."""
        self._banner_hide()
        c = self.canvas
        W, H = self.rink_w, self.rink_h
        bw, bh = 470, 66
        x0 = (W - bw) / 2
        y_hide, y_show = H + 10, H - bh - 14
        items = [
            c.create_rectangle(x0, y_hide, x0 + bw, y_hide + bh,
                               fill="#101014", outline=""),
            c.create_rectangle(x0, y_hide, x0 + 6, y_hide + bh,
                               fill=color, outline=""),
            c.create_text(x0 + 24, y_hide + 24, text=title, anchor="w",
                          fill="white", font=(FONT, 17, "bold")),
            c.create_text(x0 + 24, y_hide + 48, text=sub, anchor="w",
                          fill=MUTED, font=(FONT, 11)),
        ]
        for it in items:
            c.tag_raise(it)
        self._banner = {"items": items, "t0": self._now(),
                        "y_hide": y_hide, "y_show": y_show,
                        "y_cur": y_hide}

    def _banner_hide(self):
        if self._banner:
            for it in self._banner["items"]:
                try:
                    self.canvas.delete(it)
                except Exception:
                    pass
            self._banner = None

    def _update_phase_indicators(self):
        """Subtle top-corner labels showing each unit's current phase."""
        # Phase codes -> readable labels
        labels = {
            "oz_attack": "Attacking",
            "dz_coverage": "D-Zone Coverage",
            "forecheck": "Forecheck",
            "breakout": "Breakout",
            "nz_play": "Neutral Zone",
            "pp_setup": "Power Play",
            "pk_coverage": "Penalty Kill",
            "pp_breakout": "PP Breakout",
            "pk_forecheck": "PK Forecheck",
        }
        # team_phases is keyed by team_name (Team has no numeric id).
        home_name = getattr(getattr(self, "home_team", None), "team_name", None)
        away_name = getattr(getattr(self, "away_team", None), "team_name", None)
        hp = self._sim_phases.get(home_name) if home_name else None
        ap = self._sim_phases.get(away_name) if away_name else None

        def fmt(phase):
            if not phase:
                return None
            base = labels.get(phase, phase.replace("_", " ").title())
            # Append the tactic name for forecheck/attack phases
            if phase in ("forecheck", "pk_forecheck"):
                tac = getattr(getattr(self, "home_team", None),
                              "tactic_forecheck", "")
                if tac:
                    base += f" {tac}"
            elif phase in ("oz_attack", "pp_setup"):
                tac = getattr(getattr(self, "home_team", None),
                              "tactic_offense", "")
                if tac:
                    base += f" {tac}"
            return base

        ht, at = fmt(hp), fmt(ap)
        if ht != self._last_phase_home:
            self._last_phase_home = ht
            if ht:
                self.canvas.itemconfig(self._phase_home_text, text=ht,
                                       state="normal")
            else:
                self.canvas.itemconfig(self._phase_home_text, state="hidden")
        if at != self._last_phase_away:
            self._last_phase_away = at
            if at:
                self.canvas.itemconfig(self._phase_away_text, text=at,
                                       state="normal")
            else:
                self.canvas.itemconfig(self._phase_away_text, state="hidden")

    def _step_banner(self, now):
        b = self._banner
        if not b:
            return
        el = now - b["t0"]
        if el < 0.35:
            k = el / 0.35
            y = b["y_hide"] + (b["y_show"] - b["y_hide"]) * (1 - (1 - k) ** 2)
        elif el < 3.4:
            y = b["y_show"]
        elif el < 3.75:
            k = (el - 3.4) / 0.35
            y = b["y_show"] + (b["y_hide"] - b["y_show"]) * k * k
        else:
            self._banner_hide()
            return
        dy = y - b["y_cur"]
        b["y_cur"] = y
        if abs(dy) > 0.01:
            for it in b["items"]:
                self.canvas.move(it, 0, dy)

    def _card_show(self, title, sub="", hold=2.6):
        """Full-rink broadcast card (period intros, intermissions)."""
        self._card_hide()
        c = self.canvas
        W, H = self.rink_w, self.rink_h
        items = [
            c.create_rectangle(0, 0, W, H, fill="#0b0b0e", stipple="gray50"),
            c.create_text(W / 2, H / 2 - 26, text=title, fill="white",
                          font=(FONT, 46, "bold")),
        ]
        if sub:
            items.append(c.create_text(W / 2, H / 2 + 32, text=sub,
                                       fill=ACCENT, font=(FONT, 18, "bold")))
        for it in items:
            c.tag_raise(it)
        self._card_items = items
        self._card_until = self._now() + hold

    def _card_hide(self):
        for it in self._card_items:
            try:
                self.canvas.delete(it)
            except Exception:
                pass
        self._card_items = []
        self._card_until = 0.0

    # ------------------------------------------------------------------
    # Smart broadcast pacing
    # ------------------------------------------------------------------
    def _toggle_auto(self):
        self.auto_pace = not self.auto_pace
        self._refresh_toggle_btn(self.auto_btn, self.auto_pace)
        self._feed("Auto pacing " + ("ON — broadcast-style speed control."
                                     if self.auto_pace else "off."),
                   tag="info")

    @staticmethod
    def _refresh_toggle_btn(btn, on):
        """Show toggle state with a trailing dot (works for pills/buttons)."""
        try:
            cur = btn.cget("text").replace(" ●", "")
            btn.config(text=cur + (" ●" if on else ""))
        except Exception:
            pass

    def _set_speed(self, v):
        self.speed = v
        if self.auto_pace:
            self.auto_pace = False
            self._refresh_toggle_btn(self.auto_btn, False)

    def _auto_speed(self):
        """Broadcast-style speed: slow in the zones, fast through neutral."""
        if self.puck_flight or self._replay:
            return 1
        px = self.puck["x"]
        if px < 67 or px > 133:
            return 1
        return 3

    # ------------------------------------------------------------------
    # Clickable players -> live stat card
    # ------------------------------------------------------------------
    def _on_canvas_click(self, event):
        if self._replay:
            self._end_replay()  # click skips the replay
            return
        best, bd = None, 26
        for d in self.dots.values():
            try:
                if self.canvas.itemcget(d["oval"], "state") == "hidden":
                    continue
            except Exception:
                pass
            dist = math.hypot(self.X(d["x"]) - event.x,
                              self.Y(d["y"]) - event.y)
            if dist < bd:
                best, bd = d, dist
        if best is not None:
            self._show_player_card(best)
        elif self._card_win is not None:
            try:
                self._card_win.destroy()
            except Exception:
                pass
            self._card_win = None

    @staticmethod
    def _fullname(p):
        full = (getattr(p, "full_name", None) or "").strip()
        if full:
            return full
        first = (getattr(p, "first_name", None) or "").strip()
        last = (getattr(p, "last_name", None) or "").strip()
        return (first + " " + last).strip() or "?"

    def _show_player_card(self, d):
        p = d["player"]
        pid = getattr(p, "id", None)
        win = self._card_win
        if win is None or not win.winfo_exists():
            win = tk.Toplevel(self)
            win.title("Player")
            win.configure(bg="#16161a")
            win.geometry("260x300")
            self._card_win = win
        else:
            for w in win.winfo_children():
                w.destroy()
        col = ACCENT if d["is_home"] else AWAY_COLOR
        team = (self.home_team.team_name if d["is_home"]
                else self.away_team.team_name)
        tk.Label(win, text=self._fullname(p), bg="#16161a", fg="white",
                 font=(FONT, 13, "bold"), wraplength=240).pack(pady=(10, 0))
        pos = getattr(getattr(p, "primary_position", None), "name",
                      "?").replace("_", " ")
        try:
            ovr = int(round(p.overall_rating()))
        except Exception:
            ovr = "?"
        tk.Label(win, text=f"{team} · {pos} · {ovr} OVR", bg="#16161a",
                 fg=col, font=(FONT, 10, "bold")).pack(pady=(0, 8))
        body = tk.Frame(win, bg="#16161a")
        body.pack(fill="both", expand=True, padx=14)
        if d["role"] == "G":
            gs = self._goalie_stats.get(pid, {"saves": 0, "shots": 0})
            sv = (gs["saves"] / gs["shots"]) if gs["shots"] else 0.0
            rows = [("Saves", str(gs["saves"])),
                    ("Shots faced", str(gs["shots"])),
                    ("Save %", f"{sv:.3f}")]
        else:
            st = self._pstats.get(pid, {})
            pts = st.get("G", 0) + st.get("A", 0)
            rows = [("Goals", str(st.get("G", 0))),
                    ("Assists", str(st.get("A", 0))),
                    ("Points", str(pts)),
                    ("Shots", str(st.get("SOG", 0))),
                    ("Hits", str(st.get("HIT", 0))),
                    ("PIM", str(st.get("PIM", 0))),
                    ("Faceoff wins", str(st.get("FO", 0)))]
        for label, val in rows:
            r = tk.Frame(body, bg="#16161a")
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, bg="#16161a", fg="#a1a1aa",
                     font=(FONT, 10)).pack(side="left")
            tk.Label(r, text=val, bg="#16161a", fg="white",
                     font=(FONT, 10, "bold")).pack(side="right")
        tk.Button(win, text="Close", command=win.destroy, bg="#23262e",
                  fg="white", relief="flat", padx=12, pady=4).pack(pady=10)

    # ------------------------------------------------------------------
    # Three stars
    # ------------------------------------------------------------------
    def _compute_stars(self):
        cands = []  # (score, kind, pid, name, line)
        for pid, st in self._pstats.items():
            score = st["G"] * 3 + st["A"] * 2 + st["SOG"] * 0.15 \
                + st["HIT"] * 0.05
            p = st.get("player")
            line = (f"{st['G']}G {st['A']}A · {st['SOG']} shots · "
                    f"{st['HIT']} hits")
            cands.append((score, "skater", pid, self._fullname(p), line))
        for pid, gs in self._goalie_stats.items():
            if gs["shots"] >= 12:
                sv = gs["saves"] / max(1, gs["shots"])
                score = gs["saves"] * 0.18 + (3 if sv >= 0.94 else 0)
                line = (f"{gs['saves']}/{gs['shots']} saves "
                        f"({sv:.3f} SV%)")
                cands.append((score, "goalie", pid, gs["name"], line))
        cands.sort(key=lambda c: c[0], reverse=True)
        stars = []
        for _score, _kind, pid, name, line in cands[:3]:
            moments = [h for h in self._highlights
                       if h["pid"] == pid][:3]
            stars.append({"name": name, "line": line, "moments": moments})
        return stars

    def _show_stars(self):
        stars = self._compute_stars()
        if not stars:
            return
        self._stars = stars
        win = tk.Toplevel(self)
        win.title("Three Stars")
        win.configure(bg="#16161a")
        win.geometry("340x430")
        self._stars_win = win
        tk.Label(win, text="THREE STARS", bg="#16161a", fg=ACCENT,
                 font=(FONT, 13, "bold")).pack(pady=(12, 4))
        medals = ("1st", "2nd", "3rd")
        for i, s in enumerate(stars):
            card = tk.Frame(win, bg="#0e0e11")
            card.pack(fill="x", padx=12, pady=6)
            tk.Label(card, text=f"{medals[i]} STAR", bg="#0e0e11",
                     fg="#FFD166", font=(FONT, 9, "bold")).pack(anchor="w",
                     padx=10, pady=(8, 0))
            tk.Label(card, text=s["name"], bg="#0e0e11", fg="white",
                     font=(FONT, 12, "bold")).pack(anchor="w", padx=10)
            tk.Label(card, text=s["line"], bg="#0e0e11", fg="#a1a1aa",
                     font=(FONT, 10)).pack(anchor="w", padx=10)
            for h in s["moments"]:
                b = tk.Button(card, text=f"Watch: {h['label'][:44]}",
                              command=lambda h=h: self._play_highlight(h),
                              bg="#23262e", fg="white", relief="flat",
                              font=(FONT, 9), anchor="w", padx=8, pady=3)
                b.pack(fill="x", padx=10, pady=2)
            tk.Frame(card, bg="#0e0e11", height=8).pack()
        tk.Button(win, text="Close", command=win.destroy, bg="#23262e",
                  fg="white", relief="flat", padx=12, pady=4).pack(pady=10)

    # -- richer commentary helpers --------------------------------------
    def _goal_text(self, ev):
        S = self._pname(ev.get("shooter"))
        score = f"{ev.get('home_score', 0)}-{ev.get('away_score', 0)}"
        if ev.get("empty_net"):
            return f"{S} scores into the EMPTY NET! {score}"
        ast = ev.get("assists") or []
        ast_txt = (" (assists: " + ", ".join(self._pname(a) for a in ast) + ")"
                   if ast else "")
        st = (ev.get("shot_type") or "").replace("_", " ")
        loc = (ev.get("location") or "").replace("_", " ")
        if st and loc:
            how = f" on a {st} from the {loc}"
        elif st:
            how = f" on a {st}"
        elif loc:
            how = f" from the {loc}"
        else:
            how = ""
        return random.choice(_GOAL_T).format(S=S, how=how, ast=ast_txt,
                                             score=score)

    def _save_text(self, ev):
        G = self._pname(ev.get("goalie"))
        S = self._pname(ev.get("shooter"))
        st = (ev.get("shot_type") or "").replace("_", " ")
        how = f" on the {st}" if st else ""
        return random.choice(_SAVE_T).format(G=G, S=S, how=how)

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
        self._bump_stat(self._player_side(hp), "Hits")
        self._pstat(hp, "HIT")
        ht = ev.get("hit_type", "hit").replace("_", " ")
        self._feed(random.choice(_HIT_T).format(
            H=self._pname(ev.get("hitting_player")),
            T=self._pname(ev.get("target_player")), ht=ht), ev=ev)
        # impact burst at the target; bigger hits shake the camera
        if t and not self._instant:
            self._spawn_burst(t["x"], t["y"])
            if ev.get("hit_type", "hit") != "hit" or \
                    ev.get("result") == "turnover_caused":
                self._shake(mag=2.5, dur=0.3)

    def _spawn_burst(self, x, y, color="#ffd166"):
        items = []
        for i in range(8):
            ang = i * math.pi / 4 + random.uniform(-0.2, 0.2)
            it = self.canvas.create_line(self.X(x), self.Y(y),
                                         self.X(x), self.Y(y),
                                         fill=color, width=3,
                                         tags=("fxburst",))
            items.append((it, ang))
        try:
            self.canvas.tag_raise("fxburst")
        except Exception:
            pass
        self._bursts.append({"items": items, "t0": self._now(),
                             "x": x, "y": y})

    def _pstat(self, player, key, amount=1):
        """Accumulate a live per-player game stat (for cards + 3 stars)."""
        pid = getattr(player, "id", None)
        if pid is None:
            return
        st = self._pstats.get(pid)
        if st is None:
            st = {"G": 0, "A": 0, "SOG": 0, "HIT": 0, "PIM": 0, "FO": 0,
                  "player": player}
            self._pstats[pid] = st
        st[key] = st.get(key, 0) + amount

    def _on_delayed_penalty(self, ev):
        # The arm is up but play continues -- the penalized player stays on
        # the ice until the whistle (the real "penalty" event hides his dot).
        # The other end is already empty: "goalie_pulled" arrived with it.
        msg = (f"Delayed penalty coming -- "
               f"{self._pname(ev.get('player'))} ({ev.get('team', '')}, "
               f"{ev.get('infraction', 'a foul')}). Play continues, "
               f"extra attacker on!")
        self._feed(msg, tag="penalty", ev=ev)
        self._note("penalty", msg, ev)

    def _on_penalty(self, ev):
        d = self._dot_by_player(ev.get("player"))
        mins = ev.get("minutes", 2)
        if d:
            self.penalty_box.add(d["id"])
            self._set_dot_visible(d, False)
            # release when the penalty expires on the game clock
            self._penalty_timers[d["id"]] = self.playhead + mins * 60
        self._bump_stat(self._side_of(ev.get("team")), "PIM", mins)
        self._pstat(ev.get("player"), "PIM", mins)
        msg = random.choice(_PENALTY_T).format(
            m=mins, P=self._pname(ev.get("player")),
            team=ev.get("team", ""), inf=ev.get("infraction", "a foul"))
        self._feed(msg, tag="penalty", ev=ev)
        self._note("penalty", msg, ev)
        if not self._instant:
            home = self._side_of(ev.get("team")) == "home"
            self._banner_show(
                "penalty", "PENALTY",
                f"{self._pname(ev.get('player'))} — {mins} min for "
                f"{ev.get('infraction', 'a foul')}",
                color=ACCENT if home else AWAY_COLOR)

    def _release_penalties(self):
        """Unhide dots whose penalties expired on the game clock."""
        done = [did for did, rel in self._penalty_timers.items()
                if self.playhead >= rel]
        for did in done:
            del self._penalty_timers[did]
            self.penalty_box.discard(did)
            d = self.dots.get(did)
            if d:
                self._set_dot_visible(d, True)

    def _on_milestone(self, ev):
        """Broadcast milestone: hat-trick watch, hat trick, shutout bid."""
        kind = ev.get("kind", "")
        name = self._pname(ev.get("player"))
        home = self._side_of(ev.get("team")) == "home"
        color = ACCENT if home else AWAY_COLOR
        if kind == "hat_trick_watch":
            title, sub = "HAT-TRICK WATCH", f"{name} has two -- one more for the hats"
            tag = "goal"
        elif kind == "hat_trick":
            title, sub = "HAT TRICK!", f"{name} -- throw the hats!"
            tag = "goal"
        elif kind == "shutout_bid":
            title, sub = "SHUTOUT BID", f"{name} is perfect through two periods"
            tag = "info"
        else:
            return
        self._feed(f"{title} -- {sub}.", tag=tag, ev=ev)
        self._note("milestone", f"{title}: {sub}", ev)
        if not self._instant:
            self._banner_show("milestone", title, sub, color=color)

    def _on_fight(self, ev):
        msg = random.choice(_FIGHT_T).format(
            P=self._pname(ev.get("player")))
        self._feed(msg, tag="fight", ev=ev)
        self._push_momentum(self._side_of(ev.get("team")), 2)
        self._note("fight", msg, ev)
        self._save_highlight(ev, "fight", msg)
        if not self._instant:
            self._banner_show("fight", "FIGHT!",
                              self._pname(ev.get("player")), color="#ff8a5c")
            self._shake(mag=4.0, dur=0.5)

    def _on_shootout_attempt(self, ev):
        shooter = ev.get("shooter")
        att_home = self._player_side(shooter, ev, "shooting_team") == "home"
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
        side = self._player_side(ev.get("goalie"))
        att_home = (side == "away")
        self._goalie_shot(side, goalie=ev.get("goalie"),
                          scored=bool(ev.get("scored")))
        if ev.get("scored"):
            self._flash_light(side)
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
        self._cur_score = (hs, aws)
        en = []
        if self._en.get("home"):
            en.append(f"{_abbr(hn)} EN")
        if self._en.get("away"):
            en.append(f"{_abbr(an)} EN")
        self.score_var.set(f"{hs} – {aws}" + (f"  {' '.join(en)}" if en else ""))
        if ev:
            clk = ev.get("clock", 0)
            p = ev.get("period", 1)
            label = f"OT{p - 3}" if p > 3 else f"P{p}"
            self.clock_var.set(f"{label} {int(clk // 60):02d}:{int(clk % 60):02d}")
        self._winprob = self._calc_winprob(hs, aws)
        self.prob_var.set(f"{int(round(self._winprob * 100))}%")
        self._draw_winprob()

    def _calc_winprob(self, hs, aws):
        """Home win probability: score lead + shot tilt, time-weighted."""
        lead = hs - aws
        t_rem = 3600.0
        try:
            if self.events and self.cursor > 0:
                last = self.events[self.cursor - 1]
                p = last.get("period", 1)
                clk = last.get("clock", 0)
                t_rem = max(0.0, clk + max(0, 3 - p) * 1200)
        except Exception:
            pass
        x = lead * 1.7 / (1.0 + t_rem / 750.0)
        try:
            x += (self.team_stats["home"]["Shots"]
                  - self.team_stats["away"]["Shots"]) * 0.015
        except Exception:
            pass
        p = 1.0 / (1.0 + math.exp(-x))
        return min(0.98, max(0.02, p))

    def _draw_winprob(self):
        c = getattr(self, "prob_canvas", None)
        if c is None:
            return
        try:
            W, H = int(c["width"]), int(c["height"])
        except Exception:
            return
        c.delete("all")
        p = self._winprob
        c.create_rectangle(0, 0, W * p, H, fill=ACCENT, outline="")
        c.create_rectangle(W * p, 0, W, H, fill=AWAY_COLOR, outline="")
        hab = _abbr(self.home_team.team_name)
        aab = _abbr(self.away_team.team_name)
        c.create_text(4, H / 2, text=hab, anchor="w", fill="#0e0e11",
                      font=(FONT, 8, "bold"))
        c.create_text(W - 4, H / 2, text=aab, anchor="e", fill="#0e0e11",
                      font=(FONT, 8, "bold"))

    def _flash_light(self, side):
        self.canvas.itemconfig(self.lights[side], state="normal")
        self._light_until = self._now() + 1.4
        self._light_toggle = self._now()
        self._light_side = side

    # ------------------------------------------------------------------
    # Momentum meter
    # ------------------------------------------------------------------

    def _push_momentum(self, side, weight):
        if side in self._mom:
            self._mom[side].append(weight)
            self._mom_dirty = True

    def _momentum_net(self):
        return sum(self._mom["home"]) - sum(self._mom["away"])

    def _draw_momentum(self):
        c = getattr(self, "mom_canvas", None)
        if c is None:
            return
        try:
            W = c.winfo_width()
            H = c.winfo_height()
        except Exception:
            return
        if W < 30 or H < 8:
            return
        c.delete("all")
        net = self._momentum_net()
        frac = max(-1.0, min(1.0, net / 24.0))
        mid = W / 2
        top, bot = H / 2 - 6, H / 2 + 6
        c.create_rectangle(2, top, W - 2, bot, fill="#23262e", outline="")
        if frac > 0.01:
            c.create_rectangle(mid, top, mid + frac * (W / 2 - 2), bot,
                               fill=ACCENT, outline="")
        elif frac < -0.01:
            c.create_rectangle(mid + frac * (W / 2 - 2), top, mid, bot,
                               fill=AWAY_COLOR, outline="")
        c.create_line(mid, 2, mid, H - 2, fill="#555A66", width=1)
        hab = _abbr(self.home_team.team_name)
        aab = _abbr(self.away_team.team_name)
        c.create_text(4, H / 2, text=hab, anchor="w",
                      fill=ACCENT, font=(FONT, 8, "bold"))
        c.create_text(W - 4, H / 2, text=aab, anchor="e",
                      fill=AWAY_COLOR, font=(FONT, 8, "bold"))

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # On-ice units readout + real line changes (mirrors the sim's rotation)
    # ------------------------------------------------------------------
    def _game_clock(self):
        """(clock seconds remaining, period) from the playhead."""
        if not self.events or self.cursor == 0:
            return 1200, 1
        last = self.events[self.cursor - 1]
        clk = max(0, last.get("clock", 0) -
                  (self.playhead - last.get("t", 0)))
        return clk, last.get("period", 1)

    def _line_indices(self):
        """0-based (forward line, D pair) from elapsed game time.

        Retained for compatibility; the sim's authoritative on-ice units
        (skate events) drive line changes now.
        """
        clk, _p = self._game_clock()
        el = max(0, 1200 - int(clk))
        return (el // 45) % 4, (el // 60) % 3

    def _update_units(self):
        clk, period = self._game_clock()
        hm = sum(1 for did in self.penalty_box
                 if self.dots.get(did, {}).get("is_home"))
        am = sum(1 for did in self.penalty_box
                 if did in self.dots and not self.dots[did]["is_home"])
        hsuf = " PP" if hm < am else (" SH" if hm > am else "")
        asuf = " PP" if am < hm else (" SH" if am > hm else "")
        ot = f" OT{period - 3}" if period > 3 else ""
        hab = _abbr(self.home_team.team_name)
        aab = _abbr(self.away_team.team_name)
        htxt = f"{hab}{hsuf}{ot}"
        atxt = f"{aab}{asuf}{ot}"
        if htxt != self._units_cache["home"]:
            self.units_home_var.set(htxt)
            self._units_cache["home"] = htxt
        if atxt != self._units_cache["away"]:
            self.units_away_var.set(atxt)
            self._units_cache["away"] = atxt

    # ------------------------------------------------------------------
    # Next big moment jump
    # ------------------------------------------------------------------
    def _jump_to_next_moment(self):
        self._cancel_replay()
        self._cancel_faceoff_ceremony()
        target = None
        for i in range(self.cursor, len(self.events)):
            if self.events[i].get("type") in BIG_MOMENTS:
                target = i
                break
        if target is None:
            if self.sim_done:
                self._feed("No more big moments — the game is over.",
                           tag="info")
            return
        self._instant = True
        try:
            while self.cursor <= target:
                ev = self.events[self.cursor]
                self.cursor += 1
                self.playhead = max(self.playhead, ev.get("t", self.playhead))
                self._consume(ev)
        finally:
            self._instant = False
        self.puck_flight = None
        self.pending_outcome = None
        self._shootout_pending = None
        self._pass_arrival = None
        self._battle_winner = None
        self._battle_settle_at = 0.0
        self._cancel_faceoff_ceremony()
        self.hold_until = 0
        self._update_scoreboard()

    # ------------------------------------------------------------------
    # Period summary cards
    # ------------------------------------------------------------------
    def _note(self, tag, msg, ev):
        self._period_stats["notes"].append((tag, msg, ev))

    def _insert_period_summary(self, ev):
        p = ev.get("period", 1)
        label = f"OT{p - 3}" if p > 3 else f"P{p}"
        hab = _abbr(self.home_team.team_name)
        aab = _abbr(self.away_team.team_name)
        hs, aws = ev.get("home_score", 0), ev.get("away_score", 0)
        self._feed(f"—— {label} SUMMARY: {hab} {hs} · {aws} {aab} ——",
                   tag="summary", ev=ev)
        sh = self._period_stats["shots"]["home"]
        sa = self._period_stats["shots"]["away"]
        gh = self._period_stats["goals"]["home"]
        ga = self._period_stats["goals"]["away"]
        self._feed(f"Shots: {hab} {sh} · {aab} {sa}    "
                   f"Goals: {hab} {gh} · {aab} {ga}", tag="info", ev=ev)
        for tag, msg, nev in self._period_stats["notes"][-8:]:
            self._feed(f"• {msg}", tag=tag, ev=nev)

    # ------------------------------------------------------------------
    # Live goalie stats
    # ------------------------------------------------------------------
    def _goalie_shot(self, side, goalie=None, scored=False):
        """Record a shot faced by `side`'s current goalie."""
        pid = (getattr(goalie, "id", None) if goalie is not None
               else self._cur_goalie.get(side))
        if pid is None:
            return
        st = self._goalie_stats.get(pid)
        if st is None:
            st = {"name": self._gname(goalie), "shots": 0, "saves": 0}
            self._goalie_stats[pid] = st
        st["shots"] += 1
        if not scored:
            st["saves"] += 1
        self._cur_goalie[side] = pid
        self._update_goalie_labels()

    def _update_goalie_labels(self):
        hv = getattr(self, "_goalie_home_var", None)
        if hv is None:
            return
        for side, var in (("home", self._goalie_home_var),
                          ("away", self._goalie_away_var)):
            st = self._goalie_stats.get(self._cur_goalie.get(side))
            var.set(f"{st['name']} {st['saves']}/{st['shots']}" if st else "–")

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
        self._cancel_replay()
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
        self._pass_arrival = None
        self._battle_winner = None
        self._battle_settle_at = 0.0
        self._cancel_faceoff_ceremony()
        self.hold_until = 0
        for d in self.dots.values():
            self._move_dot(d, d["tx"], d["ty"])
        self._update_targets()
        self.playing = False
        self._refresh_play_btn()

    def _on_close(self):
        self.closed = True
        for attr in ("_card_win", "_stars_win"):
            try:
                w = getattr(self, attr, None)
                if w is not None and w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
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
        if self.closed:
            return
        try:
            self.after(33, self._tick)
        except Exception:
            pass

    def _step(self):
        now = self._now()
        # goal light: blink while the celebration lasts
        if getattr(self, "_light_until", 0):
            if now > self._light_until:
                self.canvas.itemconfig(self.lights[self._light_side],
                                       state="hidden")
                self._light_until = 0
            elif now >= getattr(self, "_light_toggle", 0):
                cur = self.canvas.itemcget(self.lights[self._light_side],
                                           "state")
                self.canvas.itemconfig(
                    self.lights[self._light_side],
                    state="hidden" if cur == "normal" else "normal")
                self._light_toggle = now + 0.22

        # broadcast camera follows the puck (runs even during replays/holds)
        self._update_camera(now)

        # tactic phase indicators: what each unit is executing right now
        self._update_phase_indicators()

        # lower-third banner animation + broadcast card expiry
        self._step_banner(now)
        if self._card_until and now >= self._card_until:
            self._card_hide()

        # faceoff ceremony: whistle -> skate to the dot -> set -> puck drop
        self._step_faceoff_ceremony()

        # delayed shot release: the shooter skates into his lane, then fires
        self._step_pending_shot(now)

        # advance playback (auto-pace overrides manual speed)
        # (a faceoff ceremony blocks consumption even if its hold expired
        #  during a pause — the break in play must finish first)
        if (self.playing and now >= self.hold_until and self.events
                and not self._faceoff_ceremony):
            eff = self._auto_speed() if self.auto_pace else self.speed
            dt = self.TICK_DT * eff * self.GAME_RATE
            target = self.playhead + dt
            # don't run past un-simulated events; sim is fast so this rarely binds
            # (stop immediately if a replay started mid-loop)
            while (self.cursor < len(self.events)
                   and self.events[self.cursor].get("t", 0) <= target
                   and not self._replay):
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
                elif getattr(self, "_pass_arrival", None):
                    pa = self._pass_arrival
                    self._pass_arrival = None
                    d = self._dot_by_player(pa.get("receiver") if pa.get("completed")
                                            else pa.get("interceptor"))
                    self.carrier_id = d["id"] if d else None
                    self.puck_target = None
                elif getattr(self, "_shootout_pending", None):
                    so = self._shootout_pending
                    self._shootout_pending = None
                    self._apply_shootout(so)
                    self._scatter_puck(so)

        # broadcast replay takes over all dot/puck motion
        if self._replay:
            self._step_replay()
        else:
            # hit nudge
            for d in self.dots.values():
                if d["nudge"]:
                    nx, ny, until = d["nudge"]
                    if now < until:
                        d["tx"], d["ty"] = nx, ny
                    else:
                        d["nudge"] = None

            # drift dots toward targets (kept live even during puck flights)
            self._update_targets()
            # goalie lunge: exaggerated reaction to a shot, then recover
            # converge: teammates mobbing the scorer hold their mob spots
            for d in self.dots.values():
                gl = d.get("glunge")
                if gl:
                    lx, ly, until = gl
                    if now < until:
                        d["tx"], d["ty"] = lx, ly
                    else:
                        d["glunge"] = None
                cv = d.get("converge")
                if cv:
                    cx, cy, until = cv
                    if now < until:
                        d["tx"], d["ty"] = cx, cy
                    else:
                        d["converge"] = None
            celly_dot = (self._celly["dot"] if self._celly
                         and now < self._celly["until"] else None)
            if self._celly and now >= self._celly["until"]:
                self._celly = None
            for d in self.dots.values():
                if d is celly_dot:
                    continue  # scorer does his victory lap below
                x, y = d["x"], d["y"]
                # skate marks: fast dots carve fading trails into the ice
                dx, dy = x - d.get("_px", x), y - d.get("_py", y)
                d["_px"], d["_py"] = x, y
                if dx * dx + dy * dy > 0.25 and random.random() < 0.45:
                    it = self.canvas.create_line(
                        self.X(x - dx), self.Y(y - dy),
                        self.X(x), self.Y(y),
                        fill="#a9c6e8", width=2, tags=("fx", "fxmarks"))
                    self._marks.append((it, now))
                    if len(self._marks) > 140:
                        old_it, _ = self._marks.popleft()
                        try:
                            self.canvas.delete(old_it)
                        except Exception:
                            pass
                # smooth skating: constant-velocity glide toward the target.
                # No exponential easing -- dots skate like players, covering
                # ground at a steady pace instead of zooming then crawling.
                if d.get("ceremony_glide"):
                    spd = self.CEREMONY_SPEED
                elif d["role"] == "G":
                    spd = self.GOALIE_SPEED
                elif now < d.get("rush_until", 0):
                    spd = self.SKATE_SPEED * 1.7  # bursting into the shot lane
                else:
                    spd = self.SKATE_SPEED
                step = spd * self.TICK_DT
                dx, dy = d["tx"] - x, d["ty"] - y
                dist = math.hypot(dx, dy)
                if dist <= step + 0.15:
                    d["x"], d["y"] = d["tx"], d["ty"]
                elif dist > 0:
                    d["x"] = x + dx / dist * step
                    d["y"] = y + dy / dist * step
                self._move_dot(d, d["x"], d["y"])
            # goal celly: scorer skates a little victory circle
            if celly_dot is not None:
                cl = self._celly
                k = (now - cl["t0"]) / max(0.01, cl["until"] - cl["t0"])
                ang = k * 4.6
                d = celly_dot
                d["x"] = cl["cx"] + math.cos(ang) * 3.2
                d["y"] = cl["cy"] + math.sin(ang) * 3.2
                d["_px"], d["_py"] = d["x"], d["y"]
                self._move_dot(d, d["x"], d["y"])
            # puck-carrier ring: follow the carrier dot, gentle pulse
            cd = self.dots.get(self.carrier_id)
            try:
                vis = (cd is not None and
                       self.canvas.itemcget(cd["oval"], "state") == "normal")
            except Exception:
                vis = False
            if vis and not self._faceoff_ceremony:
                r = 17 + 2.0 * math.sin(now * 6.0)
                try:
                    self.canvas.coords(
                        self.carrier_ring,
                        self.X(cd["x"]) - r, self.Y(cd["y"]) - r,
                        self.X(cd["x"]) + r, self.Y(cd["y"]) + r)
                    self.canvas.itemconfig(self.carrier_ring, state="normal")
                    try:
                        self.canvas.tag_raise("fxring")
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                try:
                    self.canvas.itemconfig(self.carrier_ring, state="hidden")
                except Exception:
                    pass
            # beaten goalie flashes red briefly
            for d in self.dots.values():
                if d["role"] == "G":
                    beaten = now < d.get("beaten_until", 0)
                    want = "#ff5c5c" if beaten else d.get("color", "")
                    if want and d.get("_beat_col") != want:
                        d["_beat_col"] = want
                        try:
                            self.canvas.itemconfig(d["oval"], fill=want)
                        except Exception:
                            pass
            # fade old skate marks
            while self._marks and now - self._marks[0][1] > 3.2:
                it, _ = self._marks.popleft()
                try:
                    self.canvas.delete(it)
                except Exception:
                    pass
            if self._marks:
                try:
                    self.canvas.tag_lower("fxmarks", "dot")
                except Exception:
                    pass
            # hit bursts: expand + fade over 0.45s
            if self._bursts:
                keep = []
                for b in self._bursts:
                    k = (now - b["t0"]) / 0.45
                    if k >= 1:
                        for it, _ in b["items"]:
                            try:
                                self.canvas.delete(it)
                            except Exception:
                                pass
                        continue
                    r = 4 + 30 * k
                    bx, by = self.X(b["x"]), self.Y(b["y"])
                    for it, ang in b["items"]:
                        self.canvas.coords(it, bx, by,
                                           bx + math.cos(ang) * r,
                                           by + math.sin(ang) * r)
                        self.canvas.itemconfig(it,
                                               width=max(1, int(3 * (1 - k))))
                    keep.append(b)
                self._bursts = keep

            # puck rides on the carrier's stick (no laggy easing behind him);
            # a loose puck glides quickly to its target spot.
            if not self.puck_flight:
                if self.carrier_id and self.carrier_id in self.dots:
                    c = self.dots[self.carrier_id]
                    self.puck["x"], self.puck["y"] = c["x"] + 1.5, c["y"] + 1.5
                elif self.puck_target:
                    tx, ty = self.puck_target
                    pdx, pdy = tx - self.puck["x"], ty - self.puck["y"]
                    pdist = math.hypot(pdx, pdy)
                    pstep = 40.0 * self.TICK_DT
                    if pdist <= pstep:
                        self.puck["x"], self.puck["y"] = tx, ty
                    elif pdist > 0:
                        self.puck["x"] += pdx / pdist * pstep
                        self.puck["y"] += pdy / pdist * pstep

            # battle winner takes the puck once the pile settles
            if self._battle_settle_at and now >= self._battle_settle_at:
                self._battle_settle_at = 0.0
                self.carrier_id = self._battle_winner
                self._battle_winner = None

            # penalty expirations on the game clock
            if self._penalty_timers:
                self._release_penalties()

            # line changes are driven by the sim's authoritative on-ice
            # units (skate events) -- no independent rotation here

            # record position history for replays/highlights
            if self.playing and not self._instant:
                pos = {did: (d["x"], d["y"]) for did, d in self.dots.items()}
                hs, aws = self._cur_score
                self._history.append((self.playhead, pos,
                                      (self.puck["x"], self.puck["y"]),
                                      hs, aws))

            # puck trail: grow during flights, fade after
            if self.puck_flight:
                self._trail.append((self.puck["x"], self.puck["y"]))
            elif self._trail:
                for _ in range(3):
                    if self._trail:
                        self._trail.popleft()
            if self._trail and len(self._trail) > 1:
                coords = []
                for (x, y) in self._trail:
                    coords += [self.X(x), self.Y(y)]
                self.canvas.coords(self._trail_item, *coords)
                self.canvas.itemconfig(self._trail_item,
                                       fill=self._trail_color, state="normal")
                self.canvas.tag_raise(self._trail_item)
            else:
                self.canvas.itemconfig(self._trail_item, state="hidden")

        # live readouts: on-ice units + momentum meter
        self._update_units()
        if self._mom_dirty:
            self._mom_dirty = False
            self._draw_momentum()

        # draw puck (+ glow); the boards are impenetrable for the puck too
        _px, _py = clamp_boards(self.puck["x"], self.puck["y"])
        px, py = self.X(_px), self.Y(_py)
        self.canvas.coords(self.puck_item, px - 5, py - 5, px + 5, py + 5)
        self.canvas.coords(self.puck_glow, px - 11, py - 11, px + 11, py + 11)

        # goal flash: full-rink white pop on a goal
        if now < self._flash_until:
            if not getattr(self, "_flash_item", None):
                self._flash_item = self.canvas.create_rectangle(
                    0, 0, self.rink_w, self.rink_h, fill="white", outline="")
                self.canvas.tag_raise(self._flash_item)
            self.canvas.itemconfig(self._flash_item, state="normal")
            self.canvas.tag_raise(self._flash_item)
        elif getattr(self, "_flash_item", None):
            self.canvas.itemconfig(self._flash_item, state="hidden")

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
