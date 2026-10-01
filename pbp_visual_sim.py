# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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
from popup_system import InGamePopup
from collections import deque

from game_classes import PlayerPosition
from simulation import GameSim
try:
    import reputation_system as _reputation
except Exception:
    _reputation = None
try:
    from team_identity_system import nhl_identity as _nhl_identity
except Exception:
    _nhl_identity = None
try:
    from team_identity_system import text_color_for_team as _team_fg
except Exception:
    _team_fg = None
try:
    from team_identity_system import dot_colors_for_team as _dot_colors_fn
except Exception:
    _dot_colors_fn = None
try:
    import ctk_theme as _ctk_theme
except Exception:
    _ctk_theme = None

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

def _vfont(size, weight="normal"):
    """Scale-aware canvas/widget font (honors Settings -> Font size).

    Registered with ui_scale: tier changes resize live visualizer text
    in place. Falls back to a plain tuple pre-root or headless.
    """
    try:
        from ui_scale import font as _mkfont
        return _mkfont(FONT, size, weight)
    except Exception:
        return (FONT, size, weight)

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


def _team_colors(team_name):
    """(bg, fg) pill colors in the team's true NHL colors. Never raises.

    Returns (None, None) when the team has no identity entry, so callers
    can fall back to the legacy colors.
    """
    try:
        if _nhl_identity is not None:
            c = _nhl_identity.get_team_colors(team_name)
            if c is not None:
                return c.primary, c.text_on_primary
    except Exception:
        pass
    return None, None


def _dot_colors(team_name):
    """(body, trim) two-color dot scheme for a team: primary body with a
    secondary-color outline ring, so each team's skaters wear both of
    the club's primary colors. Never raises.

    Returns (None, None) when the team has no identity entry, so callers
    can fall back to the legacy single-color dots.
    """
    try:
        if _dot_colors_fn is not None:
            body, trim = _dot_colors_fn(team_name)
            if body is not None:
                return body, trim
    except Exception:
        pass
    return None, None


def _luminance(hex_color):
    """Relative luminance of a hex color, 0 (black) to 1 (white).
    Never raises."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    except Exception:
        return 0.5


def _user_accent():
    """Current UI accent: the controlled team's color once the app theme
    has been applied, otherwise the legacy teal. Never raises."""
    try:
        if _ctk_theme is not None:
            return _ctk_theme.TEAL
    except Exception:
        pass
    return ACCENT


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
# Feed templates: written for a radio-broadcaster read -- clear
# subject-verb-object, plain words, no insider jargon. Names come from
# _pname() ("#43 Gomez") and every line is prefixed with the game clock.
_SAVE_T = [
    "Save by {G} — {S} denied{how}.",
    "{G} makes the stop on {S}{how}.",
    "{S} can't beat {G}{how}.",
    "{G} shuts the door on {S}{how}.",
]
_BLOCK_T = [
    "{B} blocks the shot from {S}.",
    "Blocked! {B} steps in front of {S}.",
    "{B} sacrifices the body to block {S}.",
]
_MISS_T = [
    "{S} misses the net.",
    "{S} fires wide of the goal.",
    "{S} rings one off the post!",
    "{S} can't find the target{how}.",
]
_FACEOFF_T = [
    "Faceoff ({zone}): {W} wins it.",
    "{W} wins the faceoff cleanly.",
    "{W} wins the draw ({zone}).",
    "{W} wins it back for his team.",
]
_HIT_T = [
    "{H} catches {T} with a {ht}.",
    "{H} finishes his check on {T}.",
    "{H} drives {T} into the boards.",
]
_PASS_T = [
    "{P} to {R}{extra}.",
    "{P} finds {R}{extra}.",
    "{P} moves it ahead to {R}{extra}.",
    "{P} connects with {R}{extra}.",
]
_BATTLE_T = [
    "{W} digs the puck free along the boards.",
    "{W} comes out of the scrum with the puck.",
    "{W} wins the battle for the puck.",
]
_PENALTY_T = [
    "Penalty: {m} min to {P} ({team}) for {inf}.",
    "{P} heads to the box — {m} min for {inf} ({team}).",
    "Whistle: {P} ({team}) gets {m} for {inf}.",
]
# Importance-scaled variants: the broadcast voice follows the impact
# tier, so you can feel how big a play was from the language alone.
# Tired plays get flat dismissal, big plays get the call of the night,
# and normal plays use the base templates above. Words like "big" and
# "huge" are reserved for the tier-2 pools -- the base sets never claim
# a routine play was a big one.
_SAVE_T2 = [
    "What a stop by {G}! {S} is robbed{how}.",
    "{G} says NO{how} — absolute robbery on {S}!",
    "Unbelievable! {G} turns away {S}{how}.",
    "Big save! {G} flashes the glove on {S}{how}!",
]
_SAVE_T0 = [
    "{G} swallows it up — easy save{how}.",
    "Routine stop for {G}{how}.",
    "{S}'s weak effort is handled easily by {G}.",
]
_HIT_T2 = [
    "{H} DESTROYS {T} with a {ht}!",
    "What a hit! {H} levels {T}!",
    "Big hit! {H} catches {T} flush!",
    "{H} absolutely trucks {T} into the boards!",
]
_HIT_T0 = [
    "{H} leans on {T} along the boards.",
    "{H} gives {T} a bump — nothing more.",
    "{H} rubs {T} out quietly.",
]
_MISS_T0 = [
    "{S} fires it wide — never threatened{how}.",
    "{S} misses badly{how}.",
]
_BLOCK_T2 = [
    "What a block! {B} lays out to deny {S}!",
    "{B} sacrifices everything — huge block on {S}!",
]
_GOAL_T2 = [  # story goals only: the biggest calls of the night
    "WHAT A GOAL! {S} buries it{how}{ast}! {score}",
    "WHAT A GOAL! {S} wires it home{how}{ast}! {score}",
    "UNBELIEVABLE! {S} scores{how}{ast}! {score}",
]


def _tier_pick(base, electric, flat, ev):
    """Pick a feed template matching the event's impact tier.

    ev may predate the impact engine (no "impact" key) -- those fall
    back to the base templates, never to the electric or flat pools."""
    imp = (ev or {}).get("impact", "normal")
    if imp == "big" and electric:
        return random.choice(electric)
    if imp == "tired" and flat:
        return random.choice(flat)
    return random.choice(base)
_FIGHT_T = [
    "Fight! {P} drops the gloves!",
    "They're going! {P} in a fight at center ice.",
]
_ICING_T = [
    "Icing against {team}.",
    "Icing called on {team}.",
]
_OFFSIDE_T = [
    "Offside — play whistled down.",
    "Offside against {team}.",
]

# ----------------------------------------------------------------------------
# EHM-style presentation detail: how much of the game gets the full on-ice
# treatment. "full" animates everything; "extended" keeps the feed for
# routine puck movement; "key" animates only the moments that matter;
# "text" is a pure text broadcast (rink hidden, feed only).
# ----------------------------------------------------------------------------
DETAIL_MODES = ("full", "extended", "key", "text")
DETAIL_LABELS = {"full": "Full Game", "extended": "Extended",
                 "key": "Key Moments", "text": "Text Only"}
# Short pill labels: the detail row shares the panel with the playback
# controls, so the pills stay compact enough to never clip at 450px.
DETAIL_SHORT = {"full": "Full", "extended": "Extended",
                "key": "Key", "text": "Text"}
# Event types that always earn on-ice treatment in key-moment mode.
_DETAIL_HIGHLIGHT_TYPES = {
    "game_start", "period_start", "period_end", "game_end",
    "goal", "penalty", "fight", "line_brawl", "penalty_shot",
    "shootout", "shootout_end", "goalie_pulled", "timeout",
}
# Event types demoted to feed-only lines in extended mode (routine play).
_DETAIL_EXTENDED_ROUTINE = {
    "pass", "skate", "battle", "dump", "carry", "takeaway",
    "line_change", "faceoff",
}


def _detail_prefs_path():
    try:
        import os
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "settings.json")
    except Exception:
        return "settings.json"


def _load_detail_pref():
    """Sticky EHM-style detail preference (visualizer_detail). Defensive:
    any failure returns 'full'."""
    try:
        import json
        with open(_detail_prefs_path(), "r", encoding="utf-8") as f:
            pref = (json.load(f).get("ui_preferences") or {}
                    ).get("visualizer_detail", "full")
        return pref if pref in DETAIL_MODES else "full"
    except Exception:
        return "full"


def _save_detail_pref(mode):
    """Persist the detail preference. Best-effort, never raises."""
    try:
        import json
        import os
        p = _detail_prefs_path()
        data = {}
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        ui = data.get("ui_preferences") or {}
        ui["visualizer_detail"] = mode
        data["ui_preferences"] = ui
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

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




# ----------------------------------------------------------------------------
# The visualizer window
# ----------------------------------------------------------------------------
class PBPVisualSim(InGamePopup):
    GAME_RATE = 8.0  # game-seconds per real second at 1x
    TICK_DT = 1.0 / 30.0  # real seconds per animation frame (~30fps)
    # Dot skating speeds in rink-feet per GAME-second. Like puck flights,
    # dots move in game-time (scaled by playback speed) so they track the
    # sim's discrete positions at any speed: at 1x a skater covers ~80
    # ft per wall-second, fast enough to reach reception spots during a
    # pass flight instead of lagging a full zone behind (which forced
    # cross-ice settle glides -- the teleport look).
    SKATE_SPEED = 30.0   # legacy real-time constant (kept for reference)
    SKATE_GS = 10.0      # skaters: tracks the sim's p90 positional speed
    GOALIE_GS = 4.0      # goalies shuffle; they rarely leave the crease
    # Puck flights are measured in game-seconds (playhead), not wall seconds,
    # so the puck always glides between touches no matter the playback speed.
    # At 1x (8 game-sec per wall-sec) a pass reads as ~0.28s of glide.
    # --- puck flight durations (game-seconds). Scaled by distance so a 130-ft
    # breakout and a 20-ft dish both travel at believable speeds instead of
    # the long pass becoming a rocket. Speeds in ft per game-second at the
    # 8x playback rate: pass ~64 ft/s real, shot ~96 ft/s real, loose ~24 ft/s.
    PASS_SPEED_FTGS = 16.0    # pass glide speed
    SHOT_SPEED_FTGS = 24.0    # shot speed
    LOOSE_SPEED_FTGS = 6.0    # takeaway / rebound / scatter slide speed
    # Event types that move the puck or stop play: a flight must land
    # before the next one of these fires, so the puck visibly rests on a
    # stick between touches instead of living permanently mid-flight
    # (the "bouncing back and forth on a string" look).
    _PUCK_TOUCH_TYPES = frozenset({
        "pass", "shot", "faceoff", "goal", "save", "blocked_shot",
        "missed_shot", "battle", "takeaway", "penalty", "icing",
        "offside", "goalie_freeze", "delayed_penalty", "fight",
    })
    MIN_PASS_GS = 1.0
    MIN_SHOT_GS = 1.0
    MIN_LOOSE_GS = 1.2
    SHOOTOUT_FLIGHT_GS = 2.5
    GOALIE_SPEED = 14.0  # legacy real-time constant (kept for reference)
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
                 home_line=None, away_line=None, on_complete=None,
                 rivalries=None, is_playoff=False, series_game=0,
                 user_team=None, outdoor=None):
        super().__init__(parent)
        self.title(f"Live Sim — {home_team.team_name} vs {away_team.team_name}")
        self.configure(bg=BG)
        self.geometry("1280x800")
        self.minsize(1100, 700)

        self.sim = sim
        self.home_team = home_team
        self.away_team = away_team
        self.user_team = user_team
        # Winter Classic / Stadium Series info dict (or None).
        self._outdoor = outdoor
        # Tactics tab state (EHM-style in-game whiteboard).
        self._tac_tab = "pbp"
        self._tac_pending = {}
        self._tac_response_text = ""
        # True NHL colors for both clubs (score bug, banners); the UI
        # accent follows the team the user controls (ctk_theme, themed by
        # the app when a team is picked).
        self._home_tc = _team_colors(home_team.team_name)
        self._away_tc = _team_colors(away_team.team_name)
        self._home_primary = self._home_tc[0] or ACCENT
        self._away_primary = self._away_tc[0] or AWAY_COLOR
        # Two-color on-ice dots: (body, trim) per team so skaters wear both
        # primary colors; falls back to body-only legacy dots when unknown.
        self._home_dc = _dot_colors(home_team.team_name)
        self._away_dc = _dot_colors(away_team.team_name)
        # Team-colored stat text (readable on the dark UI).
        try:
            self._home_fg = _team_fg(home_team.team_name) if _team_fg else ACCENT
            self._away_fg = _team_fg(away_team.team_name) if _team_fg else AWAY_COLOR
        except Exception:
            self._home_fg, self._away_fg = ACCENT, AWAY_COLOR
        # UI chrome accent: the team the user controls (falls back to teal
        # when no team has been themed yet).
        self._ui_accent = _user_accent()
        self.home_line = home_line or _best_line(home_team)
        self.away_line = away_line or _best_line(away_team)
        self.on_complete = on_complete  # called once (on UI thread) when game_end plays
        self._complete_fired = False

        # -- game intensity (tension) meter: pre-game drivers from the
        #    rivalry/personality engine, plus live in-game moments --
        self._tension_live = []  # in-game contributors: {"label", "points"}
        self._tension_open = False
        try:
            self._tension_base = _reputation.game_tension_breakdown(
                home_team, away_team, rivalries or [],
                is_playoff=is_playoff,
                series_game=series_game) if _reputation else {"tension": 0.0, "drivers": []}
        except Exception:
            self._tension_base = {"tension": 0.0, "drivers": []}

        # -- situations factor: the room, the bench, and the kids, compounded
        #    into each side's pre-game finishing edge (own channel) --
        self._situation = {"home": None, "away": None}
        try:
            if _reputation:
                self._situation["home"] = _reputation.situations_factor(
                    home_team, {"is_playoff": is_playoff})
                self._situation["away"] = _reputation.situations_factor(
                    away_team, {"is_playoff": is_playoff})
        except Exception:
            pass

        # -- event stream state --
        self.events = []          # filled by sim thread via listener
        self.cursor = 0
        self.playhead = 0.0       # game seconds consumed
        self.playing = False
        self.speed = 1
        self.sim_done = False
        self.hold_until = 0.0     # real-time hold (goal celebrations)
        self.closed = False

        # -- EHM-style presentation detail: full / extended / key / text --
        self.detail_mode = _load_detail_pref()
        if self.detail_mode not in DETAIL_MODES:
            self.detail_mode = "full"
        self._detail_btns = {}

        # -- momentum (recent shots/goals/fights, last ~10 per team) --
        self._mom = {"home": deque(maxlen=10), "away": deque(maxlen=10)}
        self._mom_dirty = True
        self._momentum_open = False

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
        # (x0,y0,x1,y1, g0,g1, tag): puck flights run on GAME clock (playhead),
        # not wall clock, so a flight always spans real game time and can never
        # be preempted by the next event -- the puck glides touch to touch.
        # New flights always launch from the puck's current rendered spot, so
        # even an overlap redirects mid-glide instead of snapping (teleport).
        self.puck_flight = None
        self._flight_cut_short = False
        self.pending_outcome = None
        self._post_ping = False    # shot flight aimed at the iron
        self._aimed_miss = False   # shot flight already aimed wide
        self.possession_home = None   # True/False/None
        self.carrier_id = None
        self.penalty_box = set()      # dot_ids
        # Sim-authoritative skater spots: the sim runs the tactical engine
        # that decides who gets open, who converges on battles, etc. Its
        # positions (from "skate" snapshots) win over our local formation
        # guess so the picture matches the play being described.
        self._sim_pos = {}            # player_id -> (x, y) in rink coords
        self._sim_pos_t = 0.0         # playhead time of last _sim_pos update
        self._sim_jobs = {}           # player_id -> job code from the sim
        self._sim_phases = {}         # team_name -> phase code from the sim
        self.shootout_mode = False
        self.shootout_state = None
        self._instant = False         # True during sim-to-end: no flights
        self.puck_target = None       # sim-authored puck destination (eased)
        self._pass_arrival = None     # pass event awaiting flight landing
        self._settle_carrier = None    # carrier to award when a settle glide lands
        self._takeaway_arrival = None  # carrier dot id awaiting glide landing
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
                              height=34, bg="#232E44", fg=TEXT,
                              font=_vfont(11, "bold"))
            b.pack(side="left", padx=padx)
            return b
        b = tk.Button(parent, text=text, command=command, bg="#1B2637",
                      fg=TEXT, font=_vfont(11, "bold"), relief="flat",
                      padx=10, pady=6)
        b.pack(side="left", padx=padx)
        return b

    def _jersey_icon(self, parent, team_name, tc):
        """2x team icon styled like the club's jersey: primary body, a
        secondary hem stripe with trim pinstripes, and a crest carrying
        the team abbreviation. Never raises."""
        W, H = 132, 64
        cv = tk.Canvas(parent, width=W, height=H, bg="#16161a",
                       highlightthickness=0, bd=0)
        try:
            primary = (tc[0] if tc and tc[0] else ACCENT)
            fg = (tc[1] if tc and tc[1] else "#0e0e11")
            dc = _dot_colors(team_name)
            secondary = dc[1] if dc and dc[1] else "white"
            trim = None
            try:
                if _nhl_identity is not None:
                    c = _nhl_identity.get_team_colors(team_name)
                    if c is not None:
                        trim = c.text_on_secondary
            except Exception:
                trim = None
            if not trim or trim.lower() == secondary.lower():
                trim = (primary if primary.lower() != secondary.lower()
                        else "#ffffff")
            # jersey body
            cv.create_rectangle(0, 0, W, H, fill=primary, outline="")
            # hem stripes: trim / secondary / trim
            y0 = H - 20
            cv.create_rectangle(0, y0, W, y0 + 3, fill=trim, outline="")
            cv.create_rectangle(0, y0 + 3, W, y0 + 11,
                                fill=secondary, outline="")
            cv.create_rectangle(0, y0 + 11, W, y0 + 14, fill=trim, outline="")
            # crest with the abbreviation
            cw, ch = 68, 30
            cx0, cy0 = (W - cw) // 2, 7
            cv.create_rectangle(cx0, cy0, cx0 + cw, cy0 + ch,
                                fill=primary, outline=trim, width=2)
            cv.create_text(W // 2, cy0 + ch // 2 + 1,
                           text=_abbr(team_name),
                           fill=fg, font=_vfont(15, "bold"))
        except Exception:
            pass
        return cv

    def _build_widgets(self):
        # Broadcast score bug: [BOS][1 – 2][BUF][P3 04:32]  WIN PROB  LIVE
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 6))
        bug = tk.Frame(top, bg="#16161a")
        bug.pack(side="left")
        self._jersey_icon(bug, self.home_team.team_name,
                          self._home_tc).pack(side="left")
        self.score_var = tk.StringVar(value="0 – 0")
        tk.Label(bug, textvariable=self.score_var, bg="#16161a", fg="white",
                 font=_vfont(18, "bold"), padx=10).pack(side="left")
        self._jersey_icon(bug, self.away_team.team_name,
                          self._away_tc).pack(side="left")
        self.clock_var = tk.StringVar(value="P1 20:00")
        tk.Label(bug, textvariable=self.clock_var, bg="#23262e", fg=_user_accent(),
                 font=_vfont(14, "bold"), padx=10, pady=6).pack(side="left")

        # Win probability (home perspective), next to the bug
        probf = tk.Frame(top, bg=BG)
        probf.pack(side="left", padx=(18, 0))
        tk.Label(probf, text="WIN PROB", bg=BG, fg="#AEB6C8",
                 font=_vfont(10, "bold")).pack(anchor="w")
        prow = tk.Frame(probf, bg=BG)
        prow.pack()
        self.prob_canvas = tk.Canvas(prow, width=150, height=16, bg="#23262e",
                                     highlightthickness=0, bd=0)
        self.prob_canvas.pack(side="left")
        self.prob_var = tk.StringVar(value="50%")
        tk.Label(prow, textvariable=self.prob_var, bg=BG, fg=TEXT,
                 font=_vfont(12, "bold"), width=5).pack(side="left", padx=(6, 0))

        # Game intensity (tension) meter, next to win probability.
        # Click it to expand the list of factors driving the rating.
        tensf = tk.Frame(top, bg=BG)
        tensf.pack(side="left", padx=(18, 0))
        tk.Label(tensf, text="INTENSITY", bg=BG, fg="#AEB6C8",
                 font=_vfont(10, "bold")).pack(anchor="w")
        trow = tk.Frame(tensf, bg=BG)
        trow.pack()
        self.tension_canvas = tk.Canvas(trow, width=150, height=16, bg="#23262e",
                                        highlightthickness=0, bd=0, cursor="hand2")
        self.tension_canvas.pack(side="left")
        self.tension_var = tk.StringVar(value="–")
        self.tension_num = tk.Label(trow, textvariable=self.tension_var, bg=BG,
                                    fg=TEXT, font=_vfont(12, "bold"), width=5,
                                    cursor="hand2")
        self.tension_num.pack(side="left", padx=(6, 0))
        for _w in (tensf, trow, self.tension_canvas, self.tension_num):
            _w.bind("<Button-1>", lambda e: self._toggle_tension_panel())

        tk.Label(top, text="LIVE SIM", bg=self._ui_accent, fg="white",
                 font=_vfont(11, "bold"), padx=8, pady=2).pack(side="right", padx=12)

        # Slim bar under the scoreboard: on-ice units, momentum, next moment
        sub = tk.Frame(self, bg=CONTENT_BG)
        sub.pack(fill="x", padx=10, pady=(0, 4))

        units = tk.Frame(sub, bg=CONTENT_BG)
        units.pack(side="left")
        tk.Label(units, text="ON ICE", bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10, "bold")).pack(anchor="w", padx=4)
        urow = tk.Frame(sub, bg=CONTENT_BG)
        urow.pack(side="left", padx=(4, 0))
        self.units_home_var = tk.StringVar(value="–")
        self.units_away_var = tk.StringVar(value="–")
        tk.Label(urow, textvariable=self.units_home_var, bg=CONTENT_BG,
                 fg=self._home_fg, font=_vfont(12, "bold")).pack(side="left", padx=(0, 14))
        tk.Label(urow, textvariable=self.units_away_var, bg=CONTENT_BG,
                 fg=self._away_fg, font=_vfont(12, "bold")).pack(side="left")

        # Live matchup readout: who's on against whom, and who's winning it.
        muf = tk.Frame(sub, bg=CONTENT_BG)
        muf.pack(side="left", padx=(18, 0))
        tk.Label(muf, text="MATCHUP", bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10, "bold")).pack(anchor="w", padx=4)
        self.matchup_var = tk.StringVar(value="\u2013")
        self.matchup_lbl = tk.Label(muf, textvariable=self.matchup_var,
                                    bg=CONTENT_BG, fg=TEXT,
                                    font=_vfont(11, "bold"))
        self.matchup_lbl.pack(anchor="w", padx=4)

        btnf = tk.Frame(sub, bg=CONTENT_BG)
        btnf.pack(side="right", padx=4)
        self._pill(btnf, "Next Big Moment", self._jump_to_next_moment, w=150)
        # The last-change lever lives here, not on a pregame screen: only
        # the home coach gets it.
        try:
            if getattr(self, "user_team", None) is getattr(self, "home_team", None) \
                    and self.user_team is not None:
                self._pill(btnf, "Matchups", self._toggle_matchup_panel, w=110)
        except Exception:
            pass

        momf = tk.Frame(sub, bg=CONTENT_BG)
        momf.pack(side="left", fill="x", expand=True, padx=14)
        tk.Label(momf, text="MOMENTUM", bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10, "bold")).pack(anchor="w")
        self.mom_canvas = tk.Canvas(momf, height=22, bg=CONTENT_BG,
                                    highlightthickness=0, bd=0)
        self.mom_canvas.pack(fill="x")
        self.mom_canvas.bind("<Configure>", lambda e: self._draw_momentum())
        self.mom_canvas.configure(cursor="hand2")
        self.mom_canvas.bind("<Button-1>", lambda e: self._toggle_momentum_panel())

        # Intensity breakdown panel (hidden until the meter is clicked).
        # Lists every factor driving the rating, + heating / - cooling.
        self.tension_panel = tk.Frame(self, bg=CONTENT_BG)
        tph = tk.Frame(self.tension_panel, bg=CONTENT_BG)
        tph.pack(fill="x", padx=14, pady=(4, 0))
        tk.Label(tph, text="WHAT'S DRIVING THE INTENSITY", bg=CONTENT_BG,
                 fg="#AEB6C8", font=_vfont(10, "bold")).pack(side="left")
        tk.Label(tph, text="click the meter to hide", bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10)).pack(side="right")
        self.tension_list = tk.Frame(self.tension_panel, bg=CONTENT_BG)
        self.tension_list.pack(fill="x", padx=14, pady=(0, 4))

        # Momentum drivers panel (hidden until the strip is clicked).
        # Shows exactly why the meter reads what it reads.
        self.momentum_panel = tk.Frame(self, bg=CONTENT_BG)
        mph = tk.Frame(self.momentum_panel, bg=CONTENT_BG)
        mph.pack(fill="x", padx=14, pady=(4, 0))
        tk.Label(mph, text="WHAT'S DRIVING THE MOMENTUM", bg=CONTENT_BG,
                 fg="#AEB6C8", font=_vfont(10, "bold")).pack(side="left")
        tk.Label(mph, text="click the strip to hide", bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10)).pack(side="right")
        self.momentum_list = tk.Frame(self.momentum_panel, bg=CONTENT_BG)
        self.momentum_list.pack(fill="x", padx=14, pady=(0, 4))

        # Matchup control panel (hidden until the Matchups button is pressed).
        # Live shadow assignments + where the chances came from.
        self._matchup_open = False
        self._shadow_vars = {}
        self.matchup_panel = tk.Frame(self, bg=CONTENT_BG)
        muph = tk.Frame(self.matchup_panel, bg=CONTENT_BG)
        muph.pack(fill="x", padx=14, pady=(4, 0))
        tk.Label(muph, text="LINE MATCHING -- LAST CHANGE IS YOURS",
                 bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10, "bold")).pack(side="left")
        tk.Label(muph, text="takes effect at the next stoppage",
                 bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10)).pack(side="right")
        self.matchup_body = tk.Frame(self.matchup_panel, bg=CONTENT_BG)
        self.matchup_body.pack(fill="x", padx=14, pady=(0, 4))

        # Main split
        main = tk.Frame(self, bg=BG)
        self._main_frame = main
        main.pack(fill="both", expand=True, padx=10, pady=4)

        # Rink canvas (940x400 @ 4.7 px/ft)
        self.scale = 4.7
        self.rink_w, self.rink_h = int(RINK_L * self.scale), int(RINK_W * self.scale)
        rink_frame = tk.Frame(main, bg=BG)
        rink_frame.pack(side="left", fill="both", expand=True)
        self._rink_frame = rink_frame
        self.canvas = tk.Canvas(rink_frame, width=self.rink_w, height=self.rink_h,
                                bg=RINK_SURROUND, highlightthickness=0, bd=0)
        self.canvas.pack(padx=4, pady=4)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        rink_frame.bind("<Configure>", self._on_rink_frame_configure)

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
            tk.Label(cell, textvariable=hv, font=_vfont(13, "bold"),
                     bg=CONTENT_BG, fg=self._home_fg).pack(side="left", padx=(10, 0))
            tk.Label(cell, text=label, font=_vfont(9),
                     bg=CONTENT_BG, fg=MUTED).pack(side="left", padx=6)
            tk.Label(cell, textvariable=av, font=_vfont(13, "bold"),
                     bg=CONTENT_BG, fg=self._away_fg).pack(side="right", padx=(0, 10))

        # Live goalie stats cell: "<last> saves/shots" per side
        gcell = tk.Frame(strip, bg=CONTENT_BG)
        gcell.grid(row=0, column=4, sticky="ew", padx=3)
        strip.grid_columnconfigure(4, weight=1)
        self._goalie_home_var = tk.StringVar(value="–")
        self._goalie_away_var = tk.StringVar(value="–")
        tk.Label(gcell, textvariable=self._goalie_home_var, font=_vfont(10, "bold"),
                 bg=CONTENT_BG, fg=self._home_fg).pack(side="left", padx=(10, 0))
        tk.Label(gcell, text="Goalies", font=_vfont(9),
                 bg=CONTENT_BG, fg=MUTED).pack(side="left", padx=6)
        tk.Label(gcell, textvariable=self._goalie_away_var, font=_vfont(10, "bold"),
                 bg=CONTENT_BG, fg=self._away_fg).pack(side="right", padx=(0, 10))

        # Advanced team-stats row, live from the sim: PP / PK / FO% / Blocks.
        # Coach's view of where the game is being won or lost. One spanning
        # row with four uniform cells so it never inherits row 0's widths.
        self._adv_vars = {}
        advrow = tk.Frame(strip, bg=CONTENT_BG)
        advrow.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(4, 0))
        for _c in range(4):
            advrow.columnconfigure(_c, weight=1, uniform="adv")
        for i, (label, key) in enumerate((("PP", "PP"), ("PK", "PK"),
                                         ("FO%", "FOP"), ("Blocks", "BLK"))):
            acell = tk.Frame(advrow, bg=CONTENT_BG)
            acell.grid(row=0, column=i, sticky="ew", padx=3)
            hv = tk.StringVar(value="–")
            av = tk.StringVar(value="–")
            self._adv_vars[key] = (hv, av)
            tk.Label(acell, textvariable=hv, font=_vfont(11, "bold"),
                     bg=CONTENT_BG, fg=self._home_fg).pack(side="left", padx=(10, 0))
            tk.Label(acell, text=label, font=_vfont(9),
                     bg=CONTENT_BG, fg=MUTED).pack(side="left", padx=6)
            tk.Label(acell, textvariable=av, font=_vfont(11, "bold"),
                     bg=CONTENT_BG, fg=self._away_fg).pack(side="right", padx=(0, 10))

        # Players to watch: hottest / coldest skaters by live game rating
        # (EHM-style 1-10, recomputed from the sim's per-player game stats).
        watch = tk.Frame(rink_frame, bg=BG)
        watch.pack(fill="x", padx=4, pady=(4, 6))
        tk.Label(watch, text="PLAYERS TO WATCH", bg=BG, fg=MUTED,
                 font=_vfont(9, "bold")).pack(anchor="w", padx=6)
        wcols = tk.Frame(watch, bg=BG)
        wcols.pack(fill="x", pady=(2, 0))
        hotf = tk.Frame(wcols, bg=CONTENT_BG)
        hotf.pack(side="left", fill="both", expand=True, padx=(0, 3))
        coldf = tk.Frame(wcols, bg=CONTENT_BG)
        coldf.pack(side="left", fill="both", expand=True, padx=(3, 0))
        tk.Label(hotf, text="▲ ON FIRE", bg=CONTENT_BG, fg="#7CFC98",
                 font=_vfont(9, "bold")).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Label(coldf, text="▼ STRUGGLING", bg=CONTENT_BG, fg="#FF8A7A",
                 font=_vfont(9, "bold")).pack(anchor="w", padx=8, pady=(4, 0))
        self._watch_hot_rows = []
        self._watch_cold_rows = []
        for _ in range(3):
            for _rows, _fg in ((self._watch_hot_rows, "#7CFC98"),
                               (self._watch_cold_rows, "#FF8A7A")):
                _parent = hotf if _rows is self._watch_hot_rows else coldf
                nv, rv = tk.StringVar(value="–"), tk.StringVar(value="")
                _row = tk.Frame(_parent, bg=CONTENT_BG)
                _row.pack(fill="x", padx=8)
                tk.Label(_row, textvariable=nv, font=_vfont(10),
                         bg=CONTENT_BG, fg=TEXT).pack(side="left")
                tk.Label(_row, textvariable=rv, font=_vfont(10, "bold"),
                         bg=CONTENT_BG, fg=_fg).pack(side="right")
                _rows.append((nv, rv))

        # Right panel: feed + controls (width adapts to the window; see
        # _on_window_configure). Crucial details stay legible at any size.
        right = tk.Frame(main, bg=CONTENT_BG, width=320)
        right.pack(side="right", fill="y", padx=(6, 0))
        right.pack_propagate(False)
        self._right_panel = right
        self._right_w = 320
        self.bind("<Configure>", self._on_window_configure)

        tabbar = tk.Frame(right, bg=CONTENT_BG)
        tabbar.pack(fill="x", padx=8, pady=(8, 2))
        self._tab_pbp_btn = self._pill(tabbar, "PBP",
                                       lambda: self._show_tac_tab("pbp"), w=76)
        self._tab_tac_btn = self._pill(tabbar, "Tactics",
                                       lambda: self._show_tac_tab("tactics"), w=100)
        self._refresh_toggle_btn(self._tab_pbp_btn, True)

        # Controls (packed before the feed so they always keep their space)
        ctl = tk.Frame(right, bg=CONTENT_BG)
        ctl.pack(side="bottom", fill="x", padx=8, pady=8)
        # EHM-style detail selector: how much of the game plays out on ice.
        drow = tk.Frame(ctl, bg=CONTENT_BG)
        drow.pack(fill="x", pady=(0, 8))
        tk.Label(drow, text="DETAIL", bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(10, "bold")).pack(side="left", padx=(2, 4))
        for mode in DETAIL_MODES:
            b = self._pill(drow, DETAIL_SHORT[mode],
                           lambda m=mode: self._set_detail_mode(m), w=84)
            self._detail_btns[mode] = b
            # Share the row equally: the pills can never overflow the
            # panel no matter how narrow the window gets.
            b.pack_configure(fill="x", expand=True)
            self._refresh_toggle_btn(b, mode == self.detail_mode)
        # Playback controls, split over two rows so nothing ever clips
        # at the panel edge: transport first, view toggles second.
        prow = tk.Frame(ctl, bg=CONTENT_BG)
        prow.pack(fill="x", pady=(0, 6))
        self.play_btn = self._pill(prow, "Pause", self._toggle_play, w=72)
        spd = tk.Frame(prow, bg=CONTENT_BG)
        spd.pack(side="left", padx=2)
        self.speed_btns = {}
        for label, val in (("1x", 1), ("2x", 2), ("4x", 4)):
            b = self._pill(spd, label, lambda v=val: self._set_speed(v), w=38)
            self.speed_btns[val] = b
        self.auto_btn = self._pill(prow, "Auto", self._toggle_auto, w=56)
        self._pill(prow, "End", self._sim_to_end, w=56)
        vrow = tk.Frame(ctl, bg=CONTENT_BG)
        vrow.pack(fill="x")
        self.shotmap_btn = self._pill(vrow, "Shot Map", self._toggle_shotmap, w=84)
        self.cam_btn = self._pill(vrow, "Cam", self._toggle_cam, w=56)
        self._refresh_toggle_btn(self.cam_btn, False)
        self.sound_btn = self._pill(vrow, "Sound", self._toggle_sound, w=68)
        self._refresh_toggle_btn(self.sound_btn, self._sound_on)

        # PBP tab frame: the classic feed, untouched.
        self._pbp_frame = tk.Frame(right, bg=CONTENT_BG)
        self._pbp_frame.pack(fill="both", expand=True)
        self.feed = tk.Text(self._pbp_frame, bg="#0D1420", fg=TEXT, font=_vfont(12),
                            wrap="word", relief="flat", highlightthickness=0,
                            padx=10, pady=8, height=22, spacing1=2, spacing3=3)
        self.feed.pack(fill="both", expand=True, padx=8, pady=4)
        # Tactics tab frame: EHM-style in-game whiteboard (built on first open).
        self._tactics_frame = tk.Frame(right, bg=CONTENT_BG)
        self._tactics_built = False
        self.feed.tag_config("goal", foreground="#7CFC98", font=_vfont(13, "bold"))
        self.feed.tag_config("period", foreground=self._ui_accent, font=_vfont(12, "bold"))
        self.feed.tag_config("penalty", foreground="#FFD166", font=_vfont(12, "bold"))
        self.feed.tag_config("shot", foreground="#9FD8FF")
        self.feed.tag_config("fight", foreground="#FF8A5C", font=_vfont(12, "bold"))
        self.feed.tag_config("summary", foreground=self._ui_accent, font=_vfont(13, "bold"))
        self.feed.tag_config("big", foreground="#FFFFFF", font=_vfont(12, "bold"))
        self.feed.tag_config("info", foreground="#AEB6C8")
        self.feed.config(state="disabled")

        self._update_goalie_labels()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Tactics tab: EHM-style in-game whiteboard
    # ------------------------------------------------------------------
    def _my_team(self):
        """The user's club in this game (falls back to home)."""
        try:
            un = getattr(self.user_team, "team_name", None)
            if un == self.home_team.team_name:
                return self.home_team
            if un == self.away_team.team_name:
                return self.away_team
        except Exception:
            pass
        return self.home_team

    def _opp_team(self):
        my = self._my_team()
        return self.away_team if my is self.home_team else self.home_team

    def _tac_ctx(self):
        """In-game context for the coach's response: losing big = dry spell."""
        ctx = {"win_pct": 0.5, "losing_streak": 0}
        try:
            hs, aws = self._cur_score
            my = self._my_team()
            diff = (hs - aws) if my is self.home_team else (aws - hs)
            if diff <= -2:
                ctx["losing_streak"] = 3
        except Exception:
            pass
        return ctx

    def _show_tac_tab(self, which):
        self._tac_tab = which
        try:
            self._refresh_toggle_btn(self._tab_pbp_btn, which == "pbp")
            self._refresh_toggle_btn(self._tab_tac_btn, which == "tactics")
            if which == "tactics":
                self._pbp_frame.pack_forget()
                self._tactics_frame.pack(fill="both", expand=True)
                self._refresh_tactics_tab()
            else:
                self._tactics_frame.pack_forget()
                self._pbp_frame.pack(fill="both", expand=True)
        except Exception:
            pass

    def _on_tac_pick(self, cat, display_name, key_of):
        try:
            import tactics as _tx
            my = self._my_team()
            key = key_of.get(display_name)
            if not key:
                return
            cur = _tx.team_tactics(my).get(cat)
            if key == cur:
                self._tac_pending.pop(cat, None)
            elif _tx.get_tactics_control(my) == "gm":
                _tx.set_team_system(my, cat, key, mid_game=True)
                self._tac_pending.pop(cat, None)
                self._tac_response_text = ""
            else:
                self._tac_pending[cat] = key
            self._refresh_tactics_tab()
        except Exception:
            pass

    def _refresh_tactics_tab(self):
        f = self._tactics_frame
        for w in f.winfo_children():
            w.destroy()
        try:
            import tactics as _tx
            import reputation_system as _rs
        except Exception:
            tk.Label(f, text="Tactics unavailable.", bg=CONTENT_BG, fg=TEXT,
                     font=_vfont(11)).pack(padx=10, pady=10)
            return
        my, opp = self._my_team(), self._opp_team()
        try:
            _tx.ensure_team_tactics(my)
            _tx.ensure_team_tactics(opp)
        except Exception:
            pass
        my_abbr, opp_abbr = _abbr(my.team_name), _abbr(opp.team_name)
        control = _tx.get_tactics_control(my)
        coach = None
        try:
            for stf in getattr(my, "staff", []) or []:
                if "Head Coach" in str(getattr(getattr(stf, "role", None), "value", "")):
                    coach = stf
                    break
        except Exception:
            pass

        hdr = tk.Frame(f, bg=CONTENT_BG)
        hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(hdr, text="TACTICS", bg=CONTENT_BG, fg=self._ui_accent,
                 font=_vfont(12, "bold")).pack(side="left")
        badge = "YOU CALL IT" if control == "gm" else "COACH IN CONTROL"
        tk.Label(hdr, text=badge, bg=CONTENT_BG,
                 fg="#FFD166" if control == "gm" else "#AEB6C8",
                 font=_vfont(10, "bold")).pack(side="right")

        tk.Label(f, text=f"{my_abbr} -- YOUR WHITEBOARD", bg=CONTENT_BG,
                 fg=TEXT, font=_vfont(11, "bold")).pack(anchor="w", padx=10)
        cats = [("forecheck", "Forechk", "FORECHECK_SYSTEMS"),
                ("neutral_zone", "NeutZne", "NEUTRAL_ZONE_SYSTEMS"),
                ("dzone", "D-Zone", "DZONE_SYSTEMS"),
                ("ozone", "O-Zone", "OZONE_SYSTEMS"),
                ("breakout", "Brkout", "BREAKOUT_SYSTEMS"),
                ("pp", "PowPly", "POWERPLAY_SYSTEMS"),
                ("pk", "PenKill", "PENALTY_KILL_SYSTEMS")]
        cur = _tx.team_tactics(my)
        for cat, short, attr in cats:
            catalog = getattr(_tx, attr)
            row = tk.Frame(f, bg=CONTENT_BG)
            row.pack(fill="x", padx=10, pady=1)
            tk.Label(row, text=short, bg=CONTENT_BG, fg="#AEB6C8",
                     font=_vfont(10, "bold"), width=9, anchor="w").pack(side="left")
            names = [v.get("name", k) for k, v in catalog.items()]
            key_of = {v.get("name", k): k for k, v in catalog.items()}
            shown_key = self._tac_pending.get(cat, cur.get(cat))
            var = tk.StringVar(value=catalog.get(shown_key, {}).get("name", names[0]))
            om = tk.OptionMenu(row, var, *names)
            om.configure(bg="#232E44", fg=TEXT, activebackground="#2E3B55",
                         activeforeground=TEXT, highlightthickness=0, relief="flat",
                         font=_vfont(10), width=20, anchor="w")
            try:
                om["menu"].configure(bg="#232E44", fg=TEXT,
                                     activebackground="#2E3B55", font=_vfont(10))
            except Exception:
                pass
            om.pack(side="left", fill="x", expand=True)
            var.trace_add("write", lambda *a, c=cat, v=var,
                          ko=key_of: self._on_tac_pick(c, v.get(), ko))

        fam = float(getattr(my, "tactics_familiarity", 85) or 85)
        tk.Label(f, text=f"Familiarity {fam:.0f}% -- changes take effect "
                         f"live (new reads are messy mid-game).",
                 bg=CONTENT_BG, fg="#AEB6C8", font=_vfont(10),
                 wraplength=290, justify="left").pack(anchor="w", padx=10, pady=(4, 0))
        try:
            ident = " / ".join(_tx.describe_team_tactics(my))
        except Exception:
            ident = ""
        tk.Label(f, text=ident, bg=CONTENT_BG, fg=TEXT, font=_vfont(10),
                 wraplength=290, justify="left").pack(anchor="w", padx=10)

        if self._tac_response_text:
            tk.Label(f, text=self._tac_response_text, bg=CONTENT_BG, fg="#FFD166",
                     font=_vfont(10, "italic"), wraplength=290,
                     justify="left").pack(anchor="w", padx=10, pady=(4, 0))

        brow = tk.Frame(f, bg=CONTENT_BG)
        brow.pack(fill="x", padx=10, pady=(6, 2))
        if control == "coach" and self._tac_pending:
            self._pill(brow, "Suggest", self._on_tac_suggest, w=76)
            self._pill(brow, "Enforce", self._on_tac_enforce, w=76)
            self._pill(brow, "Take over", self._on_tac_takeover, w=96)
        elif control == "gm":
            self._pill(brow, "Hand back", self._on_tac_handback, w=96)

        sep = tk.Frame(f, bg="#2A3648", height=1)
        sep.pack(fill="x", padx=10, pady=(8, 6))
        tk.Label(f, text=f"{opp_abbr} -- OPPONENT (AI)", bg=CONTENT_BG,
                 fg=self._ui_accent, font=_vfont(11, "bold")).pack(anchor="w", padx=10)
        ocur = _tx.team_tactics(opp)
        def _onm(cat, attr):
            return getattr(_tx, attr).get(ocur.get(cat), {}).get("name", "--")
        onames = {
            "forecheck": _onm("forecheck", "FORECHECK_SYSTEMS"),
            "neutral_zone": _onm("neutral_zone", "NEUTRAL_ZONE_SYSTEMS"),
            "dzone": _onm("dzone", "DZONE_SYSTEMS"),
            "ozone": _onm("ozone", "OZONE_SYSTEMS"),
            "breakout": _onm("breakout", "BREAKOUT_SYSTEMS"),
            "pp": _onm("pp", "POWERPLAY_SYSTEMS"),
            "pk": _onm("pk", "PENALTY_KILL_SYSTEMS"),
        }
        for lbl, val in (("FC", onames["forecheck"]), ("NZ", onames["neutral_zone"]),
                         ("DZ", onames["dzone"]), ("OZ", onames["ozone"]),
                         ("BO", onames["breakout"]),
                         ("PP", onames["pp"]), ("PK", onames["pk"])):
            r = tk.Frame(f, bg=CONTENT_BG)
            r.pack(fill="x", padx=10)
            tk.Label(r, text=lbl, bg=CONTENT_BG, fg="#AEB6C8",
                     font=_vfont(10, "bold"), width=5, anchor="w").pack(side="left")
            tk.Label(r, text=val, bg=CONTENT_BG, fg=TEXT,
                     font=_vfont(10), anchor="w").pack(side="left")
        ofam = float(getattr(opp, "tactics_familiarity", 85) or 85)
        cname = ""
        try:
            for stf in getattr(opp, "staff", []) or []:
                if "Head Coach" in str(getattr(getattr(stf, "role", None), "value", "")):
                    cname = getattr(stf, "full_name", "")
                    break
        except Exception:
            pass
        tk.Label(f, text=f"Familiarity {ofam:.0f}%"
                         + (f" -- coached by {cname}" if cname else ""),
                 bg=CONTENT_BG, fg="#AEB6C8", font=_vfont(10),
                 wraplength=290, justify="left").pack(anchor="w", padx=10, pady=(2, 8))

    def _on_tac_suggest(self):
        try:
            from tkinter import messagebox as _mb
            import tactics as _tx
            import reputation_system as _rs
            my = self._my_team()
            if not self._tac_pending:
                return
            res = _rs.suggest_tactics_to_coach(my, dict(self._tac_pending),
                                               self._tac_ctx(), mid_game=True)
            if res.get("applied"):
                self._tac_pending.clear()
            self._tac_response_text = res.get("text", "")
            self._refresh_tactics_tab()
        except Exception:
            pass

    def _on_tac_enforce(self):
        try:
            from popup_system import confirm_card as _cc
            import tactics as _tx
            import reputation_system as _rs
            my = self._my_team()
            if not self._tac_pending:
                return

            def _do_enforce(_my=my):
                res = _rs.enforce_tactics(_my, dict(self._tac_pending),
                                          self._tac_ctx(), mid_game=True)
                if res.get("applied"):
                    self._tac_pending.clear()
                self._tac_response_text = res.get("text", "")
                self._refresh_tactics_tab()

            # Gating T2-Phase 3: non-modal confirm; dismiss = no overrule.
            _cc(self, "Enforce Tactics",
                "Overrule your head coach and enforce these "
                "systems right now? He won't forget it.",
                on_yes=_do_enforce)
        except Exception:
            pass

    def _on_tac_takeover(self):
        try:
            from popup_system import confirm_card as _cc
            import tactics as _tx
            import reputation_system as _rs
            my = self._my_team()

            def _do_takeover(_my=my):
                res = _rs.take_over_tactics(_my, self._tac_ctx())
                if res.get("changed"):
                    for cat, key in list(self._tac_pending.items()):
                        _tx.set_team_system(_my, cat, key, mid_game=True)
                    self._tac_pending.clear()
                self._tac_response_text = res.get("text", "")
                self._refresh_tactics_tab()

            # Gating T2-Phase 3: non-modal confirm; dismiss = coach keeps it.
            _cc(self, "Take Over Whiteboard",
                "Take permanent control of tactics from your "
                "head coach?",
                on_yes=_do_takeover)
        except Exception:
            pass

    def _on_tac_handback(self):
        try:
            import reputation_system as _rs
            res = _rs.hand_back_tactics(self._my_team())
            self._tac_response_text = res.get("text", "")
            self._refresh_tactics_tab()
        except Exception:
            pass

    def _toggle_cam(self):
        self._set_camera(not self._cam["on"])

    def _set_detail_mode(self, mode):
        """EHM-style presentation detail. Text mode hides the rink and runs
        a fast text broadcast; key/extended filter per-event animation
        through _feed_only(); full game is unchanged."""
        if mode not in DETAIL_MODES:
            return
        self.detail_mode = mode
        _save_detail_pref(mode)
        for m, b in self._detail_btns.items():
            try:
                self._refresh_toggle_btn(b, m == mode)
            except Exception:
                pass
        is_text = (mode == "text")
        try:
            if is_text:
                self._rink_frame.pack_forget()
                self._right_panel.pack_forget()
                self._right_panel.pack(side="left", fill="both", expand=True,
                                       padx=(10, 10))
            else:
                self._right_panel.pack_forget()
                self._rink_frame.pack(side="left", fill="both", expand=True)
                self._right_panel.pack(side="right", fill="y", padx=(6, 0))
                self._right_panel.pack_propagate(False)
                self._right_panel.configure(width=self._right_w)
        except Exception:
            pass
        self._feed(f"Detail: {DETAIL_LABELS[mode]}.", tag="info")

    # ------------------------------------------------------------------
    # Responsive layout: legible from a 13" laptop to a big monitor.
    # The feed panel takes a share of the window width; the rink
    # shrink-to-fits its frame (never below a playable minimum).
    # ------------------------------------------------------------------
    def _on_window_configure(self, event):
        # <Configure> bubbles up from children -- only the toplevel itself.
        if event.widget is not self or self.detail_mode == "text":
            return
        try:
            w = max(1, int(event.width))
            target = min(480, max(300, int(w * 0.30)))
            if abs(target - self._right_w) >= 20:
                self._right_w = target
                self._right_panel.configure(width=target)
        except Exception:
            pass

    def _on_rink_frame_configure(self, event):
        if event.widget is not getattr(self, "_rink_frame", None):
            return
        # Never rescale mid-animation: flights and the broadcast camera
        # work in pixel space, and a rescale would visibly snap them.
        if (getattr(self, "puck_flight", None) or getattr(self, "_replay", False)
                or self._cam.get("on") or self.detail_mode == "text"):
            return
        try:
            fw, fh = max(1, int(event.width)), max(1, int(event.height))
            scale = min((fw - 12) / RINK_L, (fh - 12) / RINK_W, 4.7)
            scale = max(2.6, scale)  # playable minimum
            if abs(scale - self.scale) / self.scale < 0.04:
                return
            self.scale = scale
            self.rink_w, self.rink_h = int(RINK_L * scale), int(RINK_W * scale)
            self.canvas.configure(width=self.rink_w, height=self.rink_h)
            self.canvas.delete("rink")
            self._draw_rink()
            for d in self.dots.values():
                self._move_dot(d, d["x"], d["y"])
            # the puck repositions itself on the next tick via X()/Y()
        except Exception:
            pass

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
                          fill="#5A6274", font=_vfont(7, "bold"))
            self._penalty_boxes[side] = (bx0, bx1)

        # --- benches (center ice, top/bottom boards) ---
        cxm = self._RX(100)
        for y0 in (2, H - 24):
            c.create_rectangle(cxm - 70, y0, cxm + 70, y0 + 22,
                               outline="#3A4152", width=1)
            c.create_text(cxm, y0 + 11, text="BENCH",
                          fill="#5A6274", font=_vfont(7, "bold"))

        # --- broadcast REPLAY bug (hidden unless replaying) ---
        self._replay_dot = c.create_oval(14, 14, 26, 26, fill="#FF2E3E",
                                         outline="", state="hidden")
        self._replay_text = c.create_text(34, 20, text="REPLAY", anchor="w",
                                          fill="white", font=_vfont(11, "bold"),
                                          state="hidden")

        # --- tactic phase indicators: subtle, top corners. Shows what each
        # unit is executing (Forecheck 2-1-2, Umbrella PP, ...) so the GM can
        # tell if the tactics are working by watching. Updated from the
        # sim's phase stream; hidden when unknown.
        # Positioned just below the rink top edge to avoid the score bug.
        self._phase_home_text = c.create_text(10, 36, anchor="w",
                                              fill="#8a93a3", font=_vfont(9),
                                              state="hidden")
        self._phase_away_text = c.create_text(self.rink_w - 10, 36, anchor="e",
                                              fill="#8a93a3", font=_vfont(9),
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

    def _refresh_advanced_stats(self):
        """Advanced team stats row, read live from the sim's team_stats:
        PP (goals/opps + %), PK (kills/opps + %), FO%, blocked shots.
        Never raises."""
        try:
            ts = getattr(self.sim, "team_stats", None) or {}
            h = ts.get(self.home_team.team_name) or {}
            a = ts.get(self.away_team.team_name) or {}

            def _pct(n, d):
                return (100.0 * n / d) if d else 0.0

            hpp = f"{h.get('power_play_goals', 0)}/{h.get('power_play_opportunities', 0)} " \
                  f"{_pct(h.get('power_play_goals', 0), h.get('power_play_opportunities', 0)):.0f}%"
            app = f"{a.get('power_play_goals', 0)}/{a.get('power_play_opportunities', 0)} " \
                  f"{_pct(a.get('power_play_goals', 0), a.get('power_play_opportunities', 0)):.0f}%"
            hk = h.get('penalty_kill_opportunities', 0) - h.get('penalty_kill_goals_against', 0)
            ak = a.get('penalty_kill_opportunities', 0) - a.get('penalty_kill_goals_against', 0)
            hpk = f"{hk}/{h.get('penalty_kill_opportunities', 0)} " \
                  f"{_pct(hk, h.get('penalty_kill_opportunities', 0)):.0f}%"
            apk = f"{ak}/{a.get('penalty_kill_opportunities', 0)} " \
                  f"{_pct(ak, a.get('penalty_kill_opportunities', 0)):.0f}%"
            hfo = _pct(h.get('faceoffs_won', 0),
                       h.get('faceoffs_won', 0) + h.get('faceoffs_lost', 0))
            afo = _pct(a.get('faceoffs_won', 0),
                       a.get('faceoffs_won', 0) + a.get('faceoffs_lost', 0))
            vals = {
                "PP": (hpp, app),
                "PK": (hpk, apk),
                "FOP": (f"{hfo:.0f}%", f"{afo:.0f}%"),
                "BLK": (str(h.get('blocked_shots_by_team', 0)),
                        str(a.get('blocked_shots_by_team', 0))),
            }
            for key, (hv, av) in self._adv_vars.items():
                try:
                    hv.set(vals[key][0])
                    av.set(vals[key][1])
                except Exception:
                    pass
        except Exception:
            pass

    def _live_rating(self, pid):
        """EHM-style 1-10 live game rating for a player, from the sim's
        per-player game_stats. None when the player has seen no action."""
        try:
            gs = (getattr(self.sim, "game_stats", None) or {}).get(pid)
            if not gs:
                return None
            pos = getattr(gs.get("player"), "position", "") or ""
            if pos == "G":
                sa = gs.get("shots_against", 0) or 0
                if not sa:
                    return None
                svp = (gs.get("saves", 0) or 0) / sa
                r = (6.0 + (svp - 0.890) * 25.0
                     + 0.20 * (gs.get("high_danger_saves", 0) or 0))
            else:
                g = gs.get("g", 0) or 0
                ag = gs.get("a", 0) or 0
                sog = gs.get("shots_on_goal", 0) or 0
                hits = gs.get("hits", 0) or 0
                tk = gs.get("takeaways", 0) or 0
                gv = gs.get("giveaways", 0) or 0
                blk = gs.get("blocked_shots_by", 0) or 0
                fo = gs.get("faceoffs_won", 0) or 0
                pen = gs.get("physical_penalties", 0) or 0
                if not (g + ag + sog + hits + fo + tk + gv + blk + pen
                        + (gs.get("faceoffs_taken", 0) or 0)):
                    return None
                r = (6.0 + 1.5 * g + 1.0 * ag + 0.12 * sog + 0.10 * hits
                     + 0.20 * tk + 0.10 * blk + 0.05 * fo
                     - 0.40 * gv - 0.30 * pen)
            return max(1.0, min(10.0, round(r, 1)))
        except Exception:
            return None

    def _refresh_watch_list(self):
        """Players-to-watch panel: 3 hottest / 3 coldest by live rating.
        Never raises."""
        try:
            gs_all = getattr(self.sim, "game_stats", None) or {}
            rated = []
            for pid in gs_all:
                r = self._live_rating(pid)
                if r is None:
                    continue
                p = gs_all[pid].get("player")
                name = (getattr(p, "last_name", None)
                        or str(getattr(p, "name", "?")).split()[-1])
                rated.append((name, r))
            rated.sort(key=lambda t: t[1], reverse=True)
            # Absolute gates so the labels stay honest: "on fire" means
            # genuinely hot, "struggling" genuinely cold. Empty sides show -.
            hot = [t for t in rated if t[1] > 6.5][:3]
            cold = [t for t in rated if t[1] < 6.5][-3:][::-1]
            for i, (nv, rv) in enumerate(self._watch_hot_rows):
                if i < len(hot):
                    nv.set(hot[i][0])
                    rv.set(f"{hot[i][1]:.1f}")
                else:
                    nv.set("–")
                    rv.set("")
            for i, (nv, rv) in enumerate(self._watch_cold_rows):
                if i < len(cold):
                    nv.set(cold[i][0])
                    rv.set(f"{cold[i][1]:.1f}")
                else:
                    nv.set("–")
                    rv.set("")
        except Exception:
            pass

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
            if is_home:
                # Home side wears its colors: primary body, secondary ring.
                body = self._home_primary
                dc = self._home_dc
                trim = (dc[1] if dc and dc[1] else "white")
            else:
                # Away side always wears white (real road whites), with the
                # club's primary as the trim stripe so each skater still
                # reads as their team at a glance.
                body = "#FFFFFF"
                dc = self._away_dc
                trim = (dc[0] if dc and dc[0] else self._away_primary)
            for role in ("C", "LW", "RW", "D1", "D2"):
                p = line.get(role)
                if p is None:
                    continue
                self._make_dot(f"S{idx}", p, is_home, role, body, trim, r=13)
                idx += 1
            g = line.get("G")
            if g is not None:
                self._make_dot(f"G{idx}", g, is_home, "G", body, trim, r=15)
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

    def _make_dot(self, dot_id, player, is_home, role, body, trim="white", r=13):
        c = self.canvas
        num = getattr(player, "jersey_number", None) or "–"
        # start off-ice; formations will place them
        x, y = (100.0, 42.5)
        sx, sy = self.X(x) + 2.5, self.Y(y) + 3.5
        shadow = c.create_oval(sx - r, sy - r, sx + r, sy + r,
                               fill="#8fa3b8", outline="", tags=("dot",))
        # two-color team dot: body in the team's colors (home primary /
        # away white), outline ring in the club's secondary (home) or
        # primary (away) so both sides read at a glance
        oval = c.create_oval(self.X(x) - r, self.Y(y) - r,
                             self.X(x) + r, self.Y(y) + r,
                             fill=body, outline=trim, width=3,
                             tags=("dot",))
        if is_home:
            fg = (self._home_tc[1] if self._home_tc else None) or "white"
        else:
            # White away jersey: dark numbers. Prefer the club's primary
            # when it's dark (authentic road look), else near-black.
            fg = None
            try:
                _prim = (self._away_dc[0]
                         if self._away_dc and self._away_dc[0]
                         else self._away_primary)
                if _prim and _luminance(_prim) < 0.35:
                    fg = _prim
            except Exception:
                fg = None
            fg = fg or "#101014"
        txt = c.create_text(self.X(x), self.Y(y), text=str(num),
                            fill=fg, font=_vfont(9, "bold"), tags=("dot",))
        # facing tick: short line showing skate direction (updated per tick)
        tick = c.create_line(self.X(x), self.Y(y), self.X(x), self.Y(y),
                             fill=fg, width=2, tags=("dot",))
        self.dots[dot_id] = {
            "id": dot_id, "player": player, "is_home": is_home,
            "role": role, "x": x, "y": y, "tx": x, "ty": y,
            "oval": oval, "text": txt, "shadow": shadow, "tick": tick,
            "r": r, "fx": 1.0, "fy": 0.0, "color": body, "trim": trim,
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
        # knockdown: draw flattened (wide ellipse) to read as crumpled ice-level
        if self._now() < d.get("knockdown_until", 0):
            c.coords(d["oval"], px - r * 1.4, py - r * 0.55,
                     px + r * 1.4, py + r * 0.55)
            c.coords(d["text"], px, py)
            c.coords(d["shadow"], px - r + 2.5, py - r + 3.5,
                     px + r + 2.5, py + r + 3.5)
            return
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
        if teleport:
            # Game init only: place the puck on the dot. Everywhere else the
            # puck glides to the dot via the faceoff ceremony -- snapping it
            # here (e.g. at a period start) reads as a teleport.
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
            sim_fresh = (self.playhead - self._sim_pos_t) < 1.2
            if (sp is not None and sim_fresh and d["role"] != "G"
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
                    # Spread: slot + wide wingers + active points. Weak-side
                    # skaters drift toward the puck for one-timer lanes;
                    # points walk the line with puck movement.
                    puck_drift = (py - 42.5) * 0.12
                    if role == "C":
                        tx, ty = (anx - 13 * adir, 42.5) if behind else \
                            (anx - 27 * adir, 42.5 + puck_drift)
                    elif role in ("LW", "RW"):
                        mine = ((role == "LW") == (py < 42.5))
                        if behind and mine:
                            tx, ty = anx - 30 * adir, strong_y
                        elif mine:
                            tx, ty = anx - 37 * adir, strong_y
                        else:
                            tx, ty = anx - 45 * adir, weak_y + puck_drift
                    else:
                        # points walk the blue line as the puck moves
                        px_shift = max(-6, min(6, (px - (anx - 40 * adir)) * 0.1))
                        tx, ty = (anx - 57 * adir + px_shift, 30.0 + puck_drift) \
                            if role == "D1" else \
                            (anx - 57 * adir + px_shift, 55.0 + puck_drift)
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
                # one checker pressures, nobody else dives in. Landmarks
                # shuffle with the puck (weak-side rotation) so defenders
                # never stand statuesque -- EHM-style constant adjustment.
                puck_y_pull = (py - 42.5) * 0.18
                if d["id"] in st["check1"]:
                    tx, ty = px - 4 * adir, py
                elif role in ("D1", "D2"):
                    behind = ((adir == 1 and px < onx + 6) or
                              (adir == -1 and px > onx - 6))
                    s = 35.0 if role == "D1" else 50.0
                    base_x = (onx + 8 * adir) if behind else (onx + 13 * adir)
                    tx, ty = base_x, s + puck_y_pull
                elif role == "C":
                    tx, ty = onx + 22 * adir, 42.5 + puck_y_pull * 1.2
                else:
                    mine = ((role == "LW") == (py < 42.5))
                    bx = (onx + 30 * adir) if mine else (onx + 33 * adir)
                    by = strong_y if mine else weak_y
                    tx, ty = bx, by + puck_y_pull * 0.7
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
        # ---- cross-team separation: no 10-man piles on loose pucks ----
        # Teammates keep 8ft; opponents keep 4ft (battles are 1v1, not 5v5).
        all_skaters = [d for d in self.dots.values()
                       if d["role"] != "G" and d["id"] not in self.penalty_box]
        for _ in range(2):
            for i in range(len(all_skaters)):
                for j in range(i + 1, len(all_skaters)):
                    a, b = all_skaters[i], all_skaters[j]
                    if a["is_home"] == b["is_home"]:
                        continue  # teammates handled above
                    # battle pair gets a pass -- they're supposed to be close
                    if a.get("nudge") or b.get("nudge"):
                        continue
                    dx, dy = b["tx"] - a["tx"], b["ty"] - a["ty"]
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist >= 4.0 or dist < 0.01:
                        continue
                    ux, uy = dx / dist, dy / dist
                    push = (4.0 - dist) / 2
                    a["tx"] -= ux * push
                    a["ty"] -= uy * push
                    b["tx"] += ux * push
                    b["ty"] += uy * push

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
    def _is_highlight(self, ev):
        """Does this event earn on-ice treatment in key-moment mode?

        Only structural events (goals, penalties, fights, period
        boundaries) and story-gated big moments qualify. A big save or
        hit that isn't story-worthy is, by the engine's own definition,
        just a good play -- it gets a feed line, not the stage."""
        et = ev.get("type")
        if et in _DETAIL_HIGHLIGHT_TYPES:
            return True
        if ev.get("story"):  # story-gated big moments always qualify
            return True
        return False

    def _feed_only(self, ev):
        """EHM-style detail filter: True when this event should update the
        scoreboard/stats and print its feed line, but skip all on-ice
        animation (consumed via the instant path)."""
        if self._instant:
            return False
        m = self.detail_mode
        if m == "full":
            return False
        if m == "text":
            return True
        if m == "key":
            return not self._is_highlight(ev)
        return ev.get("type") in _DETAIL_EXTENDED_ROUTINE  # extended

    def _consume(self, ev):
        if self._feed_only(ev):
            prev, self._instant = self._instant, True
            try:
                self._consume_inner(ev)
            finally:
                self._instant = prev
            return
        self._consume_inner(ev)

    def _consume_inner(self, ev):
        et = ev["type"]
        if et == "game_start":
            self._update_scoreboard(ev)
            if not self._instant:
                hab = _abbr(self.home_team.team_name)
                aab = _abbr(self.away_team.team_name)
                if self._outdoor is not None:
                    # Winter Classic / Stadium Series: venue + weather card.
                    _od = self._outdoor
                    _wx = (_od.get("weather") or {}).get("framing", "")
                    self._card_show(
                        _od.get("event", "OUTDOOR GAME").upper(),
                        f"{_od.get('venue', '')} -- {_wx}", hold=3.4)
                    self._feed(
                        f"{_od.get('event')}: {aab} vs {hab}, outdoors at "
                        f"{_od.get('venue', '')} ({_wx}).", tag="special",
                        ev=ev)
                else:
                    self._card_show("PUCK DYNASTY", f"{hab}  vs  {aab}",
                                    hold=2.8)
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
        elif et == "timeout":
            self._feed(f"{ev.get('team', '')} call their timeout -- "
                       f"{ev.get('reason', 'to set up the late push')}.",
                       tag="info", ev=ev)
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
        elif et == "coach_order":
            self._feed(f"{ev.get('coach', 'The coach')} has sent his guys out -- "
                       f"the {ev.get('team', '')} are looking to punish.",
                       tag="info", ev=ev)
        elif et == "tactics_change":
            self._feed(f"TACTICS: {ev.get('text', '')}", tag="info", ev=ev)
        elif et == "brawl":
            pairs = ev.get("pairs", []) or []
            desc = ", ".join(f"{h.split()[-1]} vs {a.split()[-1]}" for h, a in pairs)
            self._feed(f"LINE BRAWL! {desc} -- every skater on the ice gets "
                       f"a 10-minute misconduct.", tag="fight", ev=ev)
            if not self._instant:
                self._banner_show("fight", "LINE BRAWL!", desc, color="#ff5a5a")
                self._shake(mag=6.0, dur=0.8)
        elif et == "controversy":
            self._feed(ev.get("text", "Controversy on the ice -- the call is disputed."),
                       tag="info", ev=ev)
            if ev.get("outcome") == "rally" and not self._instant:
                self._banner_show("info", "LOCKED IN",
                                  ev.get("text", "")[:80], color="#7fd4ff")
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
            if getattr(self, "_shootout_hidden", False):
                for od in self.dots.values():
                    try:
                        self.canvas.itemconfig(od["oval"], state="normal")
                        self.canvas.itemconfig(od["text"], state="normal")
                        self.canvas.itemconfig(od["tick"], state="normal")
                        self.canvas.itemconfig(od["shadow"], state="normal")
                    except Exception:
                        pass
                self._shootout_hidden = False
            self.shootout_mode = False
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
            self._sim_pos_t = self.playhead
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
        new_carrier = d["id"] if d else None
        if self._instant or self._faceoff_ceremony:
            self.carrier_id = new_carrier
        elif new_carrier != self.carrier_id:
            if self.puck_flight or self._takeaway_arrival == new_carrier:
                pass  # a glide is already handling this handoff; don't fight it
            elif new_carrier is None:
                self.carrier_id = None
            else:
                # General no-snap rule: if the puck isn't already with the new
                # carrier, glide it over instead of teleporting it across the
                # ice. Covers takeaways, interceptions, and recoveries after
                # the puck scatters loose.
                nd = self.dots.get(new_carrier)
                if (nd is not None and math.hypot(self.puck["x"] - nd["x"],
                                                  self.puck["y"] - nd["y"]) > 6.0):
                    self._glide_puck_to(new_carrier,
                                        self._loose_flight_gs(
                                            self.puck["x"], self.puck["y"],
                                            nd["x"], nd["y"]),
                                        arrival_kind="takeaway")
                else:
                    self.carrier_id = new_carrier

    def _flight_gs(self, x0, y0, x1, y1, speed, floor):
        """Distance-scaled flight duration: believable speed whatever the range."""
        import math as _m
        return max(floor, _m.hypot(x1 - x0, y1 - y0) / speed)

    def _pass_flight_gs(self, x0, y0, x1, y1):
        return self._flight_gs(x0, y0, x1, y1, self.PASS_SPEED_FTGS,
                               self.MIN_PASS_GS)

    def _shot_flight_gs(self, x0, y0, x1, y1):
        return self._flight_gs(x0, y0, x1, y1, self.SHOT_SPEED_FTGS,
                               self.MIN_SHOT_GS)

    def _loose_flight_gs(self, x0, y0, x1, y1):
        return self._flight_gs(x0, y0, x1, y1, self.LOOSE_SPEED_FTGS,
                               self.MIN_LOOSE_GS)

    def _award_carrier(self, carrier_dot_id):
        """Give the puck to a carrier without snapping: if his dot has
        skated away from the puck's current spot, glide it to his stick
        via a settle flight instead of teleporting.
        Settle flights are capped: if the receiver keeps outskating the
        puck (gap never closes), we stop re-launching and award directly.
        Without the cap, the flight-landing handler re-calls this forever,
        the flight never clears, and event consumption blocks behind it --
        the game soft-locks mid-period."""
        d = self.dots.get(carrier_dot_id) if carrier_dot_id else None
        if d is None:
            self.carrier_id = carrier_dot_id
            self._settle_retries = 0
            return
        gap = math.hypot(d["x"] - self.puck["x"], d["y"] - self.puck["y"])
        if gap > 6.0 and not self._instant and self._settle_retries < 3:
            self._settle_retries += 1
            self._launch_flight(self.puck["x"], self.puck["y"],
                                d["x"] + 1.5, d["y"] + 1.5,
                                self._loose_flight_gs(self.puck["x"], self.puck["y"],
                                                      d["x"], d["y"]),
                                "settle")
            self._settle_carrier = d["id"]
        else:
            # Gap closed, instant mode, or retries exhausted: award directly.
            # A rare snap beats a stuck game.
            self._settle_retries = 0
            self._settle_carrier = None
            self.carrier_id = d["id"]
            self.puck["x"], self.puck["y"] = d["x"] + 1.5, d["y"] + 1.5
        self.puck_target = None

    def _next_puck_gap(self, t0):
        """Game-seconds from t0 until the next puck-moving or play-stopping
        event still ahead in the stream, or None if none is scheduled."""
        for i in range(self.cursor, len(self.events)):
            ev = self.events[i]
            if ev.get("type") in self._PUCK_TOUCH_TYPES:
                t = ev.get("t", t0)
                if t > t0 + 0.05:
                    return t - t0
        return None

    def _launch_flight(self, x0, y0, x1, y1, dur_gs, tag, cap_to_next=True):
        import time as _t
        # Watchdog timestamp: if this flight lives too long (wall clock),
        # _step force-clears it so consumption can't block forever.
        self._flight_launched_wall = _t.time()
        """Start a game-clock puck flight from (x0, y0) to (x1, y1).

        One flight is in the air at a time: a new launch preempts any old
        one, so the old flight's pending handoff is dropped here. Without
        this, a preempted flight's stale arrival state could fire when the
        new flight lands and hand possession to the wrong player.

        The flight is capped so it lands (with the puck resting on the
        stick) before the sim's next puck touch: a glide that overruns
        the next event reads as the puck bouncing on a string.
        """
        g0 = self.playhead
        cut_short = False
        if cap_to_next and tag != "shot":
            # Shots always fly their full physical duration: the outcome was
            # pre-consumed and must apply with the puck at its aimed target
            # (net/goalie/post/wide). The blocking loop delays the next
            # event until it lands -- a few game-seconds of lag that
            # self-corrects at the next sparse stretch.
            gap = self._next_puck_gap(g0)
            if gap is not None:
                allowed = max(1.0, gap)
                if dur_gs > allowed:
                    # The sim's next touch comes before the puck could
                    # physically arrive: truncate instead of compressing.
                    # The puck travels at true speed for the available
                    # time and stops short -- reads as a cut-off pass /
                    # interception, never a teleport. The next event
                    # picks the puck up from exactly where it is, and
                    # the arrival handoff is skipped (see landing).
                    frac = allowed / dur_gs
                    x1 = x0 + (x1 - x0) * frac
                    y1 = y0 + (y1 - y0) * frac
                    dur_gs = allowed
                    cut_short = True
        self.puck_flight = (x0, y0, x1, y1, g0, g0 + dur_gs, tag)
        self._flight_cut_short = cut_short
        if tag != "pass":
            self._pass_arrival = None
        if tag != "takeaway":
            self._takeaway_arrival = None
        if tag != "shootout":
            self._shootout_pending = None
        if tag != "settle":
            self._settle_carrier = None
        if tag != "shot":
            # A preempted shot never lands: drop its aimed-miss/post state.
            self._post_ping = False
            self._aimed_miss = False

    def _glide_puck_to(self, carrier_dot_id, dur_gs, arrival_kind=None):
        """Start a game-clock puck glide to a dot; the carrier takes over
        when it lands. Never snaps: launches from the puck's current spot."""
        d = self.dots.get(carrier_dot_id)
        if d is None:
            self.carrier_id = carrier_dot_id
            return
        sx, sy = self.puck["x"], self.puck["y"]
        tag = "takeaway" if arrival_kind == "takeaway" else "glide"
        self._launch_flight(sx, sy, d["x"] + 1.5, d["y"] + 1.5, dur_gs, tag)
        if arrival_kind == "takeaway":
            self._takeaway_arrival = carrier_dot_id
        self.carrier_id = None  # puck in transit

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
        rp = ev.get("receiver_pos") or (100.0, 42.5)
        rd = self._dot_by_player(ev.get("receiver"))
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
            # Launch from the puck's CURRENT spot, not the passer's dot: the
            # puck was on his stick in the normal case (identical), and in the
            # rare overlap case this redirects mid-glide instead of snapping.
            sx, sy = self.puck["x"], self.puck["y"]
            self._launch_flight(sx, sy, rx, ry,
                            self._pass_flight_gs(sx, sy, rx, ry), "pass")
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
                       f"{self._pname(ev.get('interceptor'))}!", ev=ev)

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
        # The net is empty: the G dot becomes the 6th skater (XF) right
        # now -- no frame where a tender stands in an empty net. He'll skate
        # out as a forward; _sync_dots_to_sim keeps the role on later events.
        for d in self.dots.values():
            if d["is_home"] == home and d["role"] == "G":
                d["role"] = "XF"
                d["r"] = 13
                # send him out to join the attack, not standing in the crease
                anx = AWAY_NET_X if home else HOME_NET_X
                adir = 1 if home else -1
                d["tx"], d["ty"] = anx - 30 * adir, 42.5

    def _on_goalie_back(self, ev):
        home = ev.get("team") == self.home_team.team_name
        self._en["home" if home else "away"] = False
        self._update_scoreboard(ev)
        # Goalie returns: the XF reverts to G and heads back to his net.
        for d in self.dots.values():
            if d["is_home"] == home and d["role"] == "XF":
                d["role"] = "G"
                d["r"] = 15

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
        # A goal replay started by the flushed outcome must not run over the
        # faceoff ceremony -- they both drive the puck and would fight.
        self._cancel_replay()
        self.carrier_id = None
        self.possession_home = None
        # The ceremony owns the puck: a stale puck_target from before the
        # whistle would fight the linesman's glide and pop the puck around.
        self.puck_target = None
        if self._sound_on and self._sfx is not None:
            try:
                self._sfx.whistle()
            except Exception:
                pass
        # Neutral-zone draws are routine: run a half-length ceremony so the
        # game flows; offensive/defensive-zone draws keep the full TV
        # treatment. Presentation-only -- sim timing is untouched.
        _z = str(ev.get("zone", ""))
        _scale = 0.5 if _z in ("neutral_zone", "neutral zone") else 1.0
        self._faceoff_ceremony = {
            "el": 0.0, "phase": "whistle",
            "dx": dx, "dy": dy,
            "winner_is_home": winner_is_home,
            "ev": ev,
            "puck_from": (self.puck["x"], self.puck["y"]),
            "t_whistle": self._FO_WHISTLE * _scale,
            "t_lineup": self._FO_LINEUP * _scale,
            "t_set": self._FO_SET * _scale,
            "t_drop": self._FO_DROP,
        }
        _fo_total = ((self._FO_WHISTLE + self._FO_LINEUP + self._FO_SET)
                     * _scale + self._FO_DROP)
        self.hold_until = max(self.hold_until,
                              self._now() + _fo_total + 0.2)

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
        t_whistle = c.get("t_whistle", self._FO_WHISTLE)
        t_lineup = c.get("t_lineup", self._FO_LINEUP)
        t_set = c.get("t_set", self._FO_SET)
        t_drop = c.get("t_drop", self._FO_DROP)
        if el < t_whistle:
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
            k = min(1.0, (el - t_whistle) / t_lineup)
            fx, fy = c["puck_from"]
            self.puck["x"] = fx + (c["dx"] - fx) * k
            self.puck["y"] = fy + (c["dy"] - fy) * k
            if el >= t_whistle + t_lineup:
                c["phase"] = "set"
                for d in self.dots.values():
                    d["ceremony_glide"] = False
        elif c["phase"] == "set":
            if el >= t_whistle + t_lineup + t_set:
                c["phase"] = "drop"
        elif c["phase"] == "drop":
            # puck-drop hop, then the winner takes possession
            k = ((el - t_whistle - t_lineup - t_set)
                 / t_drop)
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
        self._trail_color = self._home_primary if att_home else self._away_primary
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
                    # Rush there, release on arrival. The delay is honest:
                    # burst speed covers dist/51 ft/s, so he actually arrives
                    # before fire_at instead of being snapped there.
                    delay = dist / 40.0
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
        # Capture shooter for shot chart export (id + name)
        _shooter = ev.get("shooter")
        _shooter_id = getattr(_shooter, 'id', None) if _shooter else None
        _shooter_name = getattr(_shooter, 'full_name',
                                getattr(_shooter, 'name', None)) if _shooter else None
        self._last_shot = (sx, sy, side, _shooter_id, _shooter_name)
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
        """Launch the puck flight once the shooter has his lane.

        The flight is aimed by the already-peeked outcome, so the net is
        a physical barrier: goals fly inside the mouth, saves die on the
        goalie, blocks die on the blocker, misses sail wide (or ping the
        iron) -- the puck never flies through the net without a goal.
        """
        # Launch from the puck's current spot (on the shooter's stick in the
        # normal case) so the release never snaps.
        sx, sy = self.puck["x"], self.puck["y"]
        toward_away = nx > 100  # shooting at AWAY_NET_X=189 or HOME_NET_X=11
        dirn = 1 if toward_away else -1
        otype = outcome.get("type") if outcome else None
        self._post_ping = False
        self._aimed_miss = False
        if otype == "goal":
            # Inside the mouth, off-center: it visibly crosses the line.
            tx, ty = nx + 0.7 * dirn, 42.5 + random.uniform(-1.1, 1.1)
        elif otype == "save":
            gd = self._dot_by_id(self._cur_goalie.get(
                "away" if toward_away else "home"))
            if gd is not None:
                tx, ty = gd["x"], gd["y"]
            else:
                tx, ty = nx, 42.5 + random.uniform(-1.2, 1.2)
        elif otype == "blocked_shot":
            bd = self._dot_by_player(outcome.get("blocker"))
            if bd is not None:
                tx, ty = bd["x"], bd["y"]
            else:
                tx, ty = (sx + nx) / 2.0, (sy + 42.5) / 2.0
        elif otype == "missed_shot":
            if random.random() < 0.22:
                # Off the iron: dead on the drawn post, then a deflection.
                tx, ty = nx, 42.5 + random.choice((-1.6, 1.6))
                self._post_ping = True
            else:
                # Wide of the post: past the goal line but outside the net.
                tx, ty = (nx + 6.0 * dirn,
                          42.5 + random.choice((-1.0, 1.0))
                          * random.uniform(4.5, 8.5))
                self._aimed_miss = True
        else:
            tx, ty = nx, 42.5
        self._launch_flight(sx, sy, tx, ty,
                            self._shot_flight_gs(sx, sy, tx, ty), "shot")
        self.pending_outcome = outcome

    def _step_pending_shot(self, now):
        ps = self._pending_shot
        if ps is None:
            return
        if self._faceoff_ceremony:
            # Whistle blew while the shooter was skating in: the play is
            # dead. Discard the shot -- its outcome was already flushed and
            # applied by _on_faceoff. Firing it now would fight the
            # ceremony's puck glide and pop the puck across the ice.
            self._pending_shot = None
            return
        if now >= ps["fire_at"]:
            d = self.dots.get(ps["shooter_id"])
            if d is not None:
                gap = math.hypot(d["x"] - ps["sx"], d["y"] - ps["sy"])
                if gap > 3.0:
                    # Not there yet -- keep skating, don't snap him (or the
                    # puck on his stick) across the ice. Re-check shortly.
                    ps["fire_at"] = now + 0.1
                    return
            self._pending_shot = None
            if d is not None:
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
            # Big story-worthy saves get the broadcast treatment: a lower
            # third and a camera jolt, like a goal. Everything else stays
            # quiet so the big ones mean something.
            if ev.get("impact") == "big" and ev.get("story") and not self._instant:
                try:
                    # Banner wears the defending (goalie's) team color.
                    _att_home = ev.get("attacking_team") == self.home_team.team_name
                    _save_color = self._away_primary if _att_home else self._home_primary
                    self._banner_show(
                        "big_save", "WHAT A SAVE!",
                        f"{self._pname(ev.get('goalie'))} robs "
                        f"{self._pname(ev.get('shooter'))}",
                        color=_save_color)
                    self._shake(mag=3.0, dur=0.35)
                except Exception:
                    pass
            self._feed(msg,
                       tag=("big" if (ev.get("impact") == "big"
                                      and ev.get("story")) else None),
                       ev=ev)
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
            self._feed(_tier_pick(_BLOCK_T, _BLOCK_T2, None, ev).format(B=B, S=S), ev=ev)
            self._record_shotmap("block")
            def_home = ev.get("defending_team") == self.home_team.team_name
            self.possession_home = def_home
            self.carrier_id = None
        elif et == "missed_shot":
            S = self._pname(ev.get("shooter"))
            st = (ev.get("shot_type") or "").replace("_", " ")
            how = f" {st}" if st else ""
            self._feed(_tier_pick(_MISS_T, None, _MISS_T0, ev).format(S=S, how=how), ev=ev)
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
        color = self._home_primary if att_home else self._away_primary
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
        self._flash_until = now + 0.08
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
        # _last_shot is (x, y, side) or (x, y, side, shooter_id, shooter_name)
        parts = self._last_shot
        x, y, side = parts[0], parts[1], parts[2]
        shooter_id = parts[3] if len(parts) > 3 else None
        shooter_name = parts[4] if len(parts) > 4 else None
        self._last_shot = None
        # Store as dict (x, y, side, result, period, shooter) for export
        period = getattr(self, 'period', 1)
        self._shotmap.append({
            "x": x, "y": y, "side": side, "result": result,
            "period": period,
            "shooter_id": shooter_id, "shooter_name": shooter_name,
        })
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
        for s in self._shotmap:
            # Support both dict (new) and tuple (legacy) formats
            if isinstance(s, dict):
                x, y, side, result = s["x"], s["y"], s["side"], s["result"]
            else:
                x, y, side, result = s
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
                col = self._home_primary if side == "home" else self._away_primary
                c.create_oval(px - 4, py - 4, px + 4, py + 4, fill=col,
                              outline="white", width=1, tags=("shotmap", "fx"))
            elif result == "block":
                c.create_rectangle(px - 4, py - 4, px + 4, py + 4,
                                   fill="#8a8f9c", outline="", tags=("shotmap", "fx"))
            else:  # miss
                c.create_text(px, py, text="x", fill="#c9ced8",
                              font=_vfont(10, "bold"), tags=("shotmap", "fx"))
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
                          fill="white", font=_vfont(17, "bold")),
            c.create_text(x0 + 24, y_hide + 48, text=sub, anchor="w",
                          fill=MUTED, font=_vfont(11)),
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
                          font=_vfont(46, "bold")),
        ]
        if sub:
            items.append(c.create_text(W / 2, H / 2 + 32, text=sub,
                                       fill=self._ui_accent, font=_vfont(18, "bold")))
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
            win = InGamePopup(self)
            win.title("Player")
            win.configure(bg="#16161a")
            win.geometry("260x300")
            self._card_win = win
        else:
            for w in win.winfo_children():
                w.destroy()
        col = self._home_primary if d["is_home"] else self._away_primary
        team = (self.home_team.team_name if d["is_home"]
                else self.away_team.team_name)
        tk.Label(win, text=self._fullname(p), bg="#16161a", fg="white",
                 font=_vfont(13, "bold"), wraplength=240).pack(pady=(10, 0))
        pos = getattr(getattr(p, "primary_position", None), "name",
                      "?").replace("_", " ")
        try:
            ovr = int(round(p.overall_rating()))
        except Exception:
            ovr = "?"
        tk.Label(win, text=f"{team} · {pos} · {ovr} OVR", bg="#16161a",
                 fg=col, font=_vfont(10, "bold")).pack(pady=(0, 8))
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
                     font=_vfont(10)).pack(side="left")
            tk.Label(r, text=val, bg="#16161a", fg="white",
                     font=_vfont(10, "bold")).pack(side="right")
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
        win = InGamePopup(self)
        win.title("Three Stars")
        win.configure(bg="#16161a")
        win.geometry("340x430")
        self._stars_win = win
        tk.Label(win, text="THREE STARS", bg="#16161a", fg=self._ui_accent,
                 font=_vfont(13, "bold")).pack(pady=(12, 4))
        medals = ("1st", "2nd", "3rd")
        for i, s in enumerate(stars):
            card = tk.Frame(win, bg="#0e0e11")
            card.pack(fill="x", padx=12, pady=6)
            tk.Label(card, text=f"{medals[i]} STAR", bg="#0e0e11",
                     fg="#FFD166", font=_vfont(9, "bold")).pack(anchor="w",
                     padx=10, pady=(8, 0))
            tk.Label(card, text=s["name"], bg="#0e0e11", fg="white",
                     font=_vfont(12, "bold")).pack(anchor="w", padx=10)
            tk.Label(card, text=s["line"], bg="#0e0e11", fg="#a1a1aa",
                     font=_vfont(10)).pack(anchor="w", padx=10)
            for h in s["moments"]:
                b = tk.Button(card, text=f"Watch: {h['label'][:44]}",
                              command=lambda h=h: self._play_highlight(h),
                              bg="#23262e", fg="white", relief="flat",
                              font=_vfont(9), anchor="w", padx=8, pady=3)
                b.pack(fill="x", padx=10, pady=2)
            tk.Frame(card, bg="#0e0e11", height=8).pack()
        tk.Button(win, text="Close", command=win.destroy, bg="#23262e",
                  fg="white", relief="flat", padx=12, pady=4).pack(pady=10)

    # -- richer commentary helpers --------------------------------------
    def _goal_text(self, ev):
        S = self._pname(ev.get("shooter"))
        # Score always names the teams: "WPG 2, CAR 1" reads instantly.
        score = (f"{_abbr(self.home_team.team_name)} {ev.get('home_score', 0)}, "
                 f"{_abbr(self.away_team.team_name)} {ev.get('away_score', 0)}")
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
        pool = _GOAL_T2 if ev.get("story") else _GOAL_T
        return random.choice(pool).format(S=S, how=how, ast=ast_txt,
                                         score=score)

    def _save_text(self, ev):
        G = self._pname(ev.get("goalie"))
        S = self._pname(ev.get("shooter"))
        st = (ev.get("shot_type") or "").replace("_", " ")
        how = f" on the {st}" if st else ""
        return _tier_pick(_SAVE_T, _SAVE_T2, _SAVE_T0, ev).format(
            G=G, S=S, how=how)

    def _on_hit(self, ev):
        h = self._dot_by_player(ev.get("hitting_player"))
        t = self._dot_by_player(ev.get("target_player"))
        if h and t:
            # lunge hitter toward target briefly
            h["nudge"] = (t["x"], t["y"], self._now() + 0.35)
        if ev.get("result") == "turnover_caused":
            th = ev.get("hitting_player")
            self.possession_home = (getattr(th, "team_name", None) == self.home_team.team_name)
            if not self._instant and h is not None:
                hd = self.dots.get(h["id"]) if h else None
                self._glide_puck_to(h["id"],
                                    self._loose_flight_gs(
                                        self.puck["x"], self.puck["y"],
                                        hd["x"], hd["y"]) if hd else self.MIN_LOOSE_GS,
                                    arrival_kind="takeaway")
            else:
                self.carrier_id = h["id"] if h else None
        hp = ev.get("hitting_player")
        self._bump_stat(self._player_side(hp), "Hits")
        self._pstat(hp, "HIT")
        ht = ev.get("hit_type", "hit").replace("_", " ")
        self._feed(_tier_pick(_HIT_T, _HIT_T2, _HIT_T0, ev).format(
            H=self._pname(ev.get("hitting_player")),
            T=self._pname(ev.get("target_player")), ht=ht),
            tag=("big" if (ev.get("impact") == "big"
                            and ev.get("story")) else None),
            ev=ev)
        # impact burst at the target; bigger hits shake the camera.
        # Prefer the engine's explicit impact tier; fall back to the old
        # heuristics for events from older engines.
        if t and not self._instant:
            self._spawn_burst(t["x"], t["y"])
            big = (ev.get("impact", "normal") == "big"
                   or ev.get("hit_type", "hit") != "hit"
                   or ev.get("result") == "turnover_caused")
            if big:
                self._shake(mag=2.5, dur=0.3)
                # knockdown: target crumples and stays down briefly.
                # Duration scales with hit violence; he can't skate while down.
                down_gs = 1.5 if ev.get("result") == "turnover_caused" else 1.0
                t["knockdown_until"] = self._now() + down_gs
                t["tx"], t["ty"] = t["x"], t["y"]  # stay where he fell
                # Big hits raise the temperature in the building.
                try:
                    self._tension_add(
                        f"Big hit: {self._pname(ev.get('hitting_player'))} "
                        f"on {self._pname(ev.get('target_player'))}", 3.0)
                except Exception:
                    pass

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
                color=self._home_primary if home else self._away_primary)
        # Majors heat the game up.
        if mins >= 5:
            try:
                self._tension_add(
                    f"Major penalty: {self._pname(ev.get('player'))}", 4.0)
            except Exception:
                pass

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
        color = self._home_primary if home else self._away_primary
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
        # Fights spike the intensity.
        try:
            self._tension_add(f"Fight: {self._pname(ev.get('player'))}", 6.0)
        except Exception:
            pass

    def _on_shootout_attempt(self, ev):
        shooter = ev.get("shooter")
        att_home = self._player_side(shooter, ev, "shooting_team") == "home"
        nx = AWAY_NET_X if att_home else HOME_NET_X
        d = self._dot_by_player(shooter)
        # Clear the ice: only shooter, goalies, and puck stay visible.
        shooter_id = d["id"] if d else None
        for od in self.dots.values():
            if od["role"] == "G" or od["id"] == shooter_id:
                continue
            try:
                self.canvas.itemconfig(od["oval"], state="hidden")
                self.canvas.itemconfig(od["text"], state="hidden")
                self.canvas.itemconfig(od["tick"], state="hidden")
                self.canvas.itemconfig(od["shadow"], state="hidden")
            except Exception:
                pass
        self._shootout_hidden = True
        sx, sy = (100.0, 42.5)
        if d:
            self._move_dot(d, 100.0, 42.5)
            d["tx"], d["ty"] = nx - (30 if att_home else -30), 42.5
        self.puck["x"], self.puck["y"] = sx, sy
        self._launch_flight(sx, sy, nx, 42.5, self.SHOOTOUT_FLIGHT_GS,
                            "shootout")
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
        self._draw_tension()

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
        c.create_rectangle(0, 0, W * p, H, fill=self._home_primary, outline="")
        c.create_rectangle(W * p, 0, W, H, fill=self._away_primary, outline="")
        hab = _abbr(self.home_team.team_name)
        aab = _abbr(self.away_team.team_name)
        c.create_text(4, H / 2, text=hab, anchor="w",
                      fill=self._home_tc[1] or "#0e0e11",
                      font=_vfont(8, "bold"))
        c.create_text(W - 4, H / 2, text=aab, anchor="e",
                      fill=self._away_tc[1] or "#0e0e11",
                      font=_vfont(8, "bold"))

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

    def _momentum_reading(self):
        """Fused momentum from momentum.py (story + crowd + recent chances /
        territory, with labeled drivers). Falls back to the local
        recent-events deques when the sim has no tracker."""
        try:
            from momentum import read_momentum as _rm
            sim = getattr(self, "sim", None)
            if sim is not None and getattr(sim, "_momentum_events", None) is not None:
                return _rm(sim)
        except Exception:
            pass
        net = self._momentum_net()
        s = max(-100.0, min(100.0, net / 24.0 * 100.0))
        side = "Even" if abs(s) < 15 else ("Home" if s > 0 else "Away")
        return {"score": s, "label": side, "drivers": [],
                "risk_home": 1.0, "risk_away": 1.0}

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
        r = self._momentum_reading()
        frac = max(-1.0, min(1.0, float(r.get("score", 0.0)) / 100.0))
        mid = W / 2
        top, bot = H / 2 - 6, H / 2 + 6
        c.create_rectangle(2, top, W - 2, bot, fill="#23262e", outline="")
        if frac > 0.01:
            c.create_rectangle(mid, top, mid + frac * (W / 2 - 2), bot,
                               fill=self._home_primary, outline="")
        elif frac < -0.01:
            c.create_rectangle(mid + frac * (W / 2 - 2), top, mid, bot,
                               fill=self._away_primary, outline="")
        c.create_line(mid, 2, mid, H - 2, fill="#555A66", width=1)
        hab = _abbr(self.home_team.team_name)
        aab = _abbr(self.away_team.team_name)
        c.create_text(4, H / 2, text=hab, anchor="w",
                      fill=self._home_fg, font=_vfont(8, "bold"))
        c.create_text(W - 4, H / 2, text=aab, anchor="e",
                      fill=self._away_fg, font=_vfont(8, "bold"))
        # Readable: state label + top driver, centered on the strip.
        lbl = r.get("label", "")
        drv = (r.get("drivers") or [""])[0]
        txt = lbl + (f" -- {drv}" if drv else "")
        if txt:
            c.create_text(mid, H / 2, text=txt,
                          fill="#F2F4F8", font=_vfont(8, "bold"))
        if getattr(self, "_momentum_open", False):
            self._render_momentum_panel()

    def _toggle_momentum_panel(self):
        try:
            self._momentum_open = not getattr(self, "_momentum_open", False)
            if self._momentum_open:
                self._render_momentum_panel()
                self.momentum_panel.pack(fill="x", padx=10, pady=(0, 4),
                                         before=self._main_frame)
            else:
                self.momentum_panel.pack_forget()
        except Exception:
            pass

    def _render_momentum_panel(self):
        lst = getattr(self, "momentum_list", None)
        if lst is None:
            return
        for w in lst.winfo_children():
            w.destroy()
        r = self._momentum_reading()
        for d in (r.get("drivers") or [])[:6]:
            tk.Label(lst, text=f"\u2022 {d}", bg=CONTENT_BG, fg=TEXT,
                     font=_vfont(9), anchor="w").pack(anchor="w", padx=4)
        if not (r.get("drivers") or []):
            tk.Label(lst, text="No momentum drivers yet -- play some hockey.",
                     bg=CONTENT_BG, fg=MUTED,
                     font=_vfont(9)).pack(anchor="w", padx=4)
        # Risk is the point: what the AI does with it, in the open.
        try:
            tk.Label(lst,
                     text=(f"AI risk appetite -- "
                           f"{_abbr(self.home_team.team_name)} "
                           f"{r.get('risk_home', 1.0):.2f} / "
                           f"{_abbr(self.away_team.team_name)} "
                           f"{r.get('risk_away', 1.0):.2f} "
                           f"(moves goalie-pull timing, never conversion)"),
                     bg=CONTENT_BG, fg="#AEB6C8",
                     font=_vfont(9, "italic"), anchor="w",
                     wraplength=900, justify="left").pack(anchor="w", padx=4,
                                                          pady=(4, 0))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Last-change line matching: the live lever
    # ------------------------------------------------------------------

    def _toggle_matchup_panel(self):
        try:
            self._matchup_open = not getattr(self, "_matchup_open", False)
            if self._matchup_open:
                self._render_matchup_panel()
                self.matchup_panel.pack(fill="x", padx=10, pady=(0, 4),
                                        before=self._main_frame)
            else:
                self.matchup_panel.pack_forget()
        except Exception:
            pass

    def _render_matchup_panel(self):
        body = getattr(self, "matchup_body", None)
        if body is None:
            return
        for w in body.winfo_children():
            w.destroy()
        try:
            from matchups import (set_shadow, preset_shutdown, preset_shelter_scorers, preset_auto, report)
        except Exception:
            return
        home = self.home_team

        top = tk.Frame(body, bg=CONTENT_BG)
        top.pack(fill="x", pady=(0, 4))
        # Shadow assignments: my line -> their line.
        for unit, n, ulab in (("F", 4, "line"), ("D", 3, "pair")):
            for away_line in range(1, 5):
                row = tk.Frame(top, bg=CONTENT_BG)
                row.pack(side="left", padx=(0, 18))
                tk.Label(row, text=f"Their {away_line}{ulab[0]}",
                         bg=CONTENT_BG, fg=MUTED,
                         font=_vfont(9, "bold")).pack(anchor="w")
                key = (unit, away_line)
                var = tk.StringVar(value="Auto")
                # reflect current prefs
                try:
                    prefs = list((getattr(home, "line_matchups", None) or {})
                                 .get(unit) or [])
                    for i, want in enumerate(prefs[:n]):
                        if want == away_line:
                            var.set(f"My {i + 1}")
                except Exception:
                    pass
                opts = ["Auto"] + [f"My {i}" for i in range(1, n + 1)]
                om = tk.OptionMenu(row, var, *opts,
                                   command=lambda v, u=unit, a=away_line:
                                   self._on_shadow_pick(u, a, v))
                om.configure(bg="#232E44", fg=TEXT, relief="flat",
                             font=_vfont(9), highlightthickness=0)
                om.pack(anchor="w")
                self._shadow_vars[key] = var

        prow = tk.Frame(body, bg=CONTENT_BG)
        prow.pack(fill="x", pady=(6, 2))
        tk.Label(prow, text="Presets:", bg=CONTENT_BG, fg=MUTED,
                 font=_vfont(9, "bold")).pack(side="left", padx=(0, 8))
        for label, fn in (("Shutdown their stars", preset_shutdown),
                          ("Shelter my scorers", preset_shelter_scorers),
                          ("Auto (coach)", preset_auto)):
            self._pill(prow, label,
                       lambda f=fn: self._on_matchup_preset(f), w=170)

        # Where the chances came from, live.
        # Where the chances came from, live (refreshed on a throttle).
        tk.Label(body, text="WHERE THE CHANCES CAME FROM",
                 bg=CONTENT_BG, fg="#AEB6C8",
                 font=_vfont(9, "bold")).pack(anchor="w", pady=(6, 0))
        self.matchup_table = tk.Frame(body, bg=CONTENT_BG)
        self.matchup_table.pack(fill="x")
        self._matchup_tick = 0
        self._refresh_matchup_table()

    def _refresh_matchup_table(self):
        tbl = getattr(self, "matchup_table", None)
        if tbl is None:
            return
        for w in tbl.winfo_children():
            w.destroy()
        try:
            from matchups import report
        except Exception:
            return
        rep = report(getattr(self, "sim", None))
        if rep:
            for r in rep[:6]:
                hd = "HD %s-%s" % (r["hd_for"], r["hd_against"])
                g = "G %s-%s" % (r["goals_for"], r["goals_against"])
                line = ("Your %s vs their %s: %s \u00b7 %s"
                        % (r["home_line"], r["away_line"], hd, g))
                if r["verdict"]:
                    line += " -- %s" % r["verdict"]
                tk.Label(tbl, text="\u2022 " + line, bg=CONTENT_BG, fg=TEXT,
                         font=_vfont(9), anchor="w",
                         wraplength=1000, justify="left").pack(anchor="w")
        else:
            tk.Label(tbl, text="No dangerous chances logged yet.",
                     bg=CONTENT_BG, fg=MUTED,
                     font=_vfont(9)).pack(anchor="w")
    def _on_shadow_pick(self, unit, away_line, value):
        try:
            from matchups import set_shadow
            home_line = None
            if value.startswith("My "):
                home_line = int(value.split()[-1])
            set_shadow(self.home_team, away_line, home_line, unit)
            who = "my %s" % home_line if home_line else "coach's auto"
            what = "line" if unit == "F" else "pair"
            self._feed("Matchup set: %s %s vs their %s -- takes effect "
                        "at the next stoppage." % (who, what, away_line),
                       tag="info")
        except Exception:
            pass

    def _on_matchup_preset(self, fn):
        try:
            fn(self.home_team)
            self._render_matchup_panel()
            self._feed("Matchup preset applied -- takes effect at the next "
                       "stoppage.", tag="info")
        except Exception:
            pass

    def _update_matchup_readout(self):
        try:
            from matchups import current_matchup
            cm = current_matchup(getattr(self, "sim", None))
            if cm:
                txt = (f"L{cm['home_line']} vs L{cm['away_line']} "
                       f"· {cm['edge']}")
            else:
                txt = "–"
            cache = self._units_cache
            if txt != cache.get("matchup"):
                self.matchup_var.set(txt)
                cache["matchup"] = txt
                edge = (cm or {}).get("edge", "")
                if edge in ("strong edge", "edge"):
                    self.matchup_lbl.configure(fg="#7bc96f")
                elif edge in ("outmatched", "strongly outmatched"):
                    self.matchup_lbl.configure(fg="#ff9f5c")
                else:
                    self.matchup_lbl.configure(fg=TEXT)
            # keep the open panel's attribution table fresh
            if getattr(self, "_matchup_open", False):
                self._render_matchup_panel()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Game intensity (tension) meter
    # ------------------------------------------------------------------

    def _tension_value(self):
        """Current 0-100 intensity: pre-game drivers + live moments."""
        try:
            v = float(self._tension_base.get("tension", 0.0))
            v += sum(float(d.get("points", 0)) for d in self._tension_live)
            return max(0.0, min(100.0, round(v, 1)))
        except Exception:
            return 0.0

    def _tension_add(self, label, points):
        """Log an in-game moment as a live intensity contributor."""
        try:
            self._tension_live.append({"label": label,
                                       "points": round(float(points), 1)})
            if len(self._tension_live) > 12:
                self._tension_live.pop(0)
            self._draw_tension()
            if self._tension_open:
                self._render_tension_panel()
        except Exception:
            pass

    @staticmethod
    def _tension_color(v):
        if v >= 75:
            return "#ff6b6b"
        if v >= 50:
            return "#ff9f5c"
        if v >= 25:
            return "#ffd166"
        return "#7bc96f"

    @staticmethod
    def _tension_mood(v):
        if v >= 75:
            return "BOILING"
        if v >= 50:
            return "CHIPPY"
        if v >= 25:
            return "HEATING"
        return "CALM"

    def _draw_tension(self):
        c = getattr(self, "tension_canvas", None)
        if c is None:
            return
        try:
            W, H = int(c["width"]), int(c["height"])
        except Exception:
            return
        v = self._tension_value()
        c.delete("all")
        c.create_rectangle(0, 0, W * v / 100.0, H,
                           fill=self._tension_color(v), outline="")
        c.create_text(W / 2, H / 2, text=self._tension_mood(v),
                      fill="#0e0e11", font=_vfont(8, "bold"))
        try:
            self.tension_var.set(f"{int(round(v))}")
        except Exception:
            pass

    def _toggle_tension_panel(self):
        try:
            self._tension_open = not self._tension_open
            if self._tension_open:
                self._render_tension_panel()
                self.tension_panel.pack(fill="x", padx=10, pady=(0, 4),
                                        before=self._main_frame)
            else:
                self.tension_panel.pack_forget()
        except Exception:
            pass

    def _render_tension_panel(self):
        lst = getattr(self, "tension_list", None)
        if lst is None:
            return
        for w in lst.winfo_children():
            w.destroy()
        drivers = (list(self._tension_base.get("drivers", []))
                   + list(self._tension_live))
        drivers.sort(key=lambda d: -abs(d.get("points", 0)))
        if not drivers:
            tk.Label(lst, text="No intensity data for this game.",
                     bg=CONTENT_BG, fg=MUTED,
                     font=_vfont(9)).pack(anchor="w", padx=4)
            return
        for d in drivers[:14]:
            pts = d.get("points", 0)
            row = tk.Frame(lst, bg=CONTENT_BG)
            row.pack(fill="x", padx=4)
            fg = "#ff9f5c" if pts > 0 else "#7bc96f"
            sign = "+" if pts > 0 else ""
            tk.Label(row, text=f"{sign}{pts:g}", bg=CONTENT_BG, fg=fg,
                     font=_vfont(9, "bold"), width=7,
                     anchor="e").pack(side="left")
            tk.Label(row, text=d.get("label", ""), bg=CONTENT_BG, fg=TEXT,
                     font=_vfont(9), anchor="w").pack(side="left", padx=(8, 0))

        # Situations channel: each side's pre-game edge and what's driving it.
        try:
            sit = getattr(self, "_situation", None) or {}
            shown = False
            for key in ("home", "away"):
                bd = sit.get(key)
                if not bd:
                    continue
                if not shown:
                    tk.Label(lst, text="SITUATIONS -- finishing edge",
                             bg=CONTENT_BG, fg=MUTED,
                             font=_vfont(8, "bold")).pack(anchor="w",
                                                          padx=4, pady=(6, 0))
                    shown = True
                sc = bd.get("score", 0)
                fg = "#ff9f5c" if sc > 0 else ("#7bc96f" if sc < 0 else MUTED)
                sign = "+" if sc > 0 else ""
                tk.Label(lst, text=f"{bd.get('team', key)}: {sign}{sc:g}",
                         bg=CONTENT_BG, fg=fg,
                         font=_vfont(9, "bold")).pack(anchor="w", padx=4)
                for drv in (bd.get("drivers") or [])[:4]:
                    v = drv.get("value", 0)
                    fg2 = "#ff9f5c" if v > 0 else "#7bc96f"
                    s2 = "+" if v > 0 else ""
                    tk.Label(lst, text=f"    {s2}{v:g}  {drv.get('label', '')}",
                             bg=CONTENT_BG, fg=fg2,
                             font=_vfont(8)).pack(anchor="w", padx=4)
        except Exception:
            pass

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
        self._update_matchup_readout()

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
        self._takeaway_arrival = None
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
        if p >= 3:
            # The matchup story of the night: where the chances came from.
            try:
                from matchups import report as _mu_report
                _vers = [r["verdict"] for r in _mu_report(getattr(self, "sim", None))
                         if r["verdict"]][:2]
                for _v in _vers:
                    self._feed(f"• Matchups: {_v}.", tag="summary", ev=ev)
            except Exception:
                pass

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
        self._takeaway_arrival = None
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

        # coach's corner: advanced stats + players-to-watch, ~1Hz throttle
        if now - getattr(self, "_last_coach_refresh", 0.0) >= 1.0:
            self._last_coach_refresh = now
            try:
                self._refresh_advanced_stats()
            except Exception:
                pass
            try:
                self._refresh_watch_list()
            except Exception:
                pass

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
            if self.detail_mode == "text":
                # Text-only broadcast: the feed is the show -- run it fast
                # enough to feel like a live wire, slow enough to read.
                eff = max(eff, 1.0) * 25.0
            dt = self.TICK_DT * eff * self.GAME_RATE
            target = self.playhead + dt
            # don't run past un-simulated events; sim is fast so this rarely binds
            # (stop immediately if a replay started mid-loop, or a puck flight
            # launched -- the flight owns the puck until it lands, and the
            # next event must wait its turn instead of preempting it)
            while (self.cursor < len(self.events)
                   and self.events[self.cursor].get("t", 0) <= target
                   and not self._replay
                   and not self._faceoff_ceremony
                   and self.puck_flight is None):
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

        # puck flight animation (game-clock: spans real game time, so the
        # puck glides touch-to-touch and is never preempted by the next event)
        if self.puck_flight:
            # Watchdog: a flight living too long (wall clock) is stuck --
            # force-clear it so event consumption (and game_end) can't block
            # forever behind a visual glitch. A stuck visual beats a stuck game.
            import time as _t2
            _fw = getattr(self, "_flight_launched_wall", 0) or 0
            if _fw and (_t2.time() - _fw) > 15:
                print(f"VIZ WATCHDOG: force-cleared stuck '{self.puck_flight[6]}' "
                      f"flight (ph={self.playhead:.0f})", flush=True)
                self.puck_flight = None
                self._settle_carrier = None
                self._takeaway_arrival = None
                self._pass_arrival = None
                self.pending_outcome = None
        if self.puck_flight:
            x0, y0, x1, y1, g0, g1, tag = self.puck_flight
            k = min(1.0, (self.playhead - g0) / max(0.001, g1 - g0))
            # Constant velocity: a real puck glides on ice at steady pace.
            # (Ease-out made every flight decelerate into its target like
            # the puck was magnet-drawn -- the "on a string" look.)
            self.puck["x"] = x0 + (x1 - x0) * k
            self.puck["y"] = y0 + (y1 - y0) * k
            if k >= 1.0:
                self.puck_flight = None
                cut = self._flight_cut_short
                self._flight_cut_short = False
                if cut:
                    # Truncated flight: the sim's next touch arrived before
                    # the puck could physically get there. It stops where
                    # it is -- no arrival handoff (the receiver never got
                    # it), no scatter. The imminent next event claims the
                    # puck from exactly this spot.
                    pass
                elif self.pending_outcome is not None:
                    oc = self.pending_outcome
                    self.pending_outcome = None
                    if self._post_ping and oc.get("type") == "missed_shot":
                        self._post_ping = False
                        self._apply_outcome(oc)
                        self._deflect_off_post(oc)
                    else:
                        self._apply_outcome(oc)
                        # puck ends: goal -> stays in the net (the flight
                        # aimed it inside the mouth); save -> rebound off
                        # the goalie; block -> loose off the blocker;
                        # aimed wide miss -> already loose, no extra glide.
                        self._scatter_puck(oc)
                elif getattr(self, "_pass_arrival", None):
                    pa = self._pass_arrival
                    self._pass_arrival = None
                    rd = self._dot_by_player(pa.get("receiver") if pa.get("completed")
                                             else pa.get("interceptor"))
                    self._award_carrier(rd["id"] if rd else None)
                elif getattr(self, "_shootout_pending", None):
                    so = self._shootout_pending
                    self._shootout_pending = None
                    self._apply_shootout(so)
                    self._scatter_puck(so)
                elif getattr(self, "_takeaway_arrival", None):
                    # takeaway glide landed: the new carrier has it on his stick
                    ta = self._takeaway_arrival
                    self._takeaway_arrival = None
                    self._settle_retries = 0
                    self._award_carrier(ta)
                elif tag == "settle" and getattr(self, "_settle_carrier", None):
                    # settle glide landed: puck should be on the receiver's
                    # stick; if he kept skating, settle again (converges: the
                    # receiver is skating to the puck, not away from it)
                    sc = self._settle_carrier
                    self._settle_carrier = None
                    self._award_carrier(sc)

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
                # knocked down: stays crumpled where he fell, can't skate.
                # The dot draws flattened (see _move_dot) until he gets up.
                if now < d.get("knockdown_until", 0):
                    d["tx"], d["ty"] = d["x"], d["y"]
                    self._move_dot(d, d["x"], d["y"])
                    continue
                elif d.get("knockdown_until"):
                    d["knockdown_until"] = 0  # back on his skates
                # smooth skating: constant-velocity glide toward the target.
                # No exponential easing -- dots skate like players, covering
                # ground at a steady pace instead of zooming then crawling.
                # Game-time: scaled by playback speed like puck flights, so
                # dots track the sim's discrete positions at 1x and 4x alike.
                dt_gs = self.TICK_DT * (self._auto_speed()
                                        if self.auto_pace else self.speed) \
                    * self.GAME_RATE
                if d.get("ceremony_glide"):
                    step = self.CEREMONY_SPEED * self.TICK_DT  # broadcast beat
                elif d["role"] == "G":
                    step = self.GOALIE_GS * dt_gs
                elif now < d.get("rush_until", 0):
                    step = self.SKATE_GS * 1.7 * dt_gs  # bursting to the lane
                else:
                    step = self.SKATE_GS * dt_gs
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
                    if math.hypot(self.puck["x"] - c["x"],
                                  self.puck["y"] - c["y"]) > 12.0:
                        # Carrier is far from the puck (e.g. faceoff winner
                        # not yet at the dot): glide it to him instead of
                        # snapping it across the ice.
                        self.puck_target = (c["x"] + 1.5, c["y"] + 1.5)
                    else:
                        self.puck["x"], self.puck["y"] = c["x"] + 1.5, c["y"] + 1.5
                elif self.puck_target and not self._faceoff_ceremony:
                    tx, ty = self.puck_target
                    pdx, pdy = tx - self.puck["x"], ty - self.puck["y"]
                    pdist = math.hypot(pdx, pdy)
                    # game-time like everything else (was real-time: froze
                    # relative to the sim at higher playback speeds)
                    pstep = 5.0 * self.TICK_DT * (
                        self._auto_speed() if self.auto_pace
                        else self.speed) * self.GAME_RATE
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

        # goal flash: brief translucent pop on a goal. Stippled (not
        # solid) so the puck stays trackable through it -- a solid white
        # frame was whiting out the screen at the moment of the goal.
        if now < self._flash_until:
            if not getattr(self, "_flash_item", None):
                self._flash_item = self.canvas.create_rectangle(
                    0, 0, self.rink_w, self.rink_h, fill="white", outline="",
                    stipple="gray50")
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

    def _deflect_off_post(self, oc):
        """The shot hit the iron: ping it loose with a feed call."""
        S = self._pname(oc.get("shooter"))
        self._feed(f"{S} rings it off the post!", tag="shot", ev=oc)
        px, py = self.puck["x"], self.puck["y"]
        tx, ty = clamp_boards(px + random.uniform(-16, 16),
                              py + random.uniform(-12, 12))
        self._launch_flight(px, py, tx, ty,
                            self._loose_flight_gs(px, py, tx, ty), "scatter")

    def _scatter_puck(self, ev):
        et = ev["type"]
        att_home = (ev.get("attacking_team") or ev.get("scoring_team")
                    or getattr(ev.get("shooter"), "team_name", None)) == self.home_team.team_name
        if et == "goal":
            # The flight already put it inside the mouth: leave it there.
            return
        # Rebounds glide instead of snapping -- a save/block/miss reads as
        # the puck bouncing loose, not teleporting.
        if self._instant:
            glide = None
        else:
            glide = (self.puck["x"], self.puck["y"])
        if et == "save":
            nx = AWAY_NET_X if att_home else HOME_NET_X
            tx, ty = (nx - 14 if att_home else nx + 14), random.choice([18, 67])
        elif et == "blocked_shot":
            d = self._dot_by_player(ev.get("blocker"))
            tx, ty = (d["x"], d["y"]) if d else (self.puck["x"], self.puck["y"])
        elif et == "missed_shot":
            if self._aimed_miss:
                # Already sailed wide and loose: no second glide.
                self._aimed_miss = False
                return
            nx = AWAY_NET_X if att_home else HOME_NET_X
            tx, ty = nx + (8 if att_home else -8), 42.5 + random.uniform(-14, 14)
        elif et == "shootout_attempt":
            tx, ty = 100, 42.5
        else:
            return
        if glide:
            sx, sy = glide
            self._launch_flight(sx, sy, tx, ty,
                                self._loose_flight_gs(sx, sy, tx, ty),
                                "scatter")
        else:
            self.puck["x"], self.puck["y"] = tx, ty


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------
def open_pbp_window(parent, home_team, away_team, on_complete=None,
                    rivalries=None, is_playoff=False, series_game=0,
                    user_team=None, outdoor=None, coach_instruction=None):
    """Open the visual play-by-play simulator for a game.

    parent: tk widget (usually the main app root)
    home_team, away_team: Team objects with full rosters
    on_complete: optional callable(sim) fired once on the UI thread when the
        final whistle plays, so the host app can process the result.
    rivalries: optional list of rivalry records (league.rivalries) so the
        intensity meter can account for bad blood between the clubs.
    outdoor: optional outdoor-game info dict (Winter Classic/Stadium
        Series) -- drives the pre-game card, feed lines, and the crowd
        energy bump in the sim.
    coach_instruction: D1 -- the user's explicit coach instruction from
        the game-day bundle (e.g. "play_harder"), applied to the user's
        team via the standard set_coach_instruction channel. The AI fill
        (simulation._ai_coach_instructions) never overwrites it.
    Returns the PBPVisualSim window. Does not block.
    """
    sim = GameSim(home_team, away_team, is_playoff=is_playoff,
                  rivalries=rivalries, series_game=series_game)
    if coach_instruction:
        # Explicit user call: provenance "explicit", so the AI fill
        # (which ran at sim construction, and re-runs at intermissions)
        # keeps its hands off.
        try:
            _uname = getattr(user_team, "team_name", None)
            if _uname:
                if coach_instruction == "none":
                    # "Let the game come to us": clear any AI fill and
                    # hold the explicit provenance.
                    sim.set_coach_instruction(_uname, None)
                    sim._coach_instruction_source[_uname] = "explicit"
                else:
                    sim.set_coach_instruction(_uname, coach_instruction)
        except Exception:
            pass
    if outdoor is not None:
        # The loudest night of the regular season: pin the building near-max
        # through the existing two-sided crowd channel.
        try:
            from arena_atmosphere import pregame_crowd
            _atm = pregame_crowd(home_team, away_team, outdoor=True)
            sim._crowd_energy = float(_atm.get("energy", 50.0))
            sim._crowd_mood = float(_atm.get("mood", 30.0))
        except Exception:
            pass
    win = PBPVisualSim(parent, sim, home_team, away_team,
                       home_line=_best_line(home_team),
                       away_line=_best_line(away_team),
                       on_complete=on_complete,
                       rivalries=rivalries, is_playoff=is_playoff,
                       series_game=series_game,
                       user_team=user_team, outdoor=outdoor)
    return win
