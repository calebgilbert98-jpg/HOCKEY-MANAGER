# game_classes.py
# A refactored and improved version focusing on structure, scalability, and clarity.

import random
import itertools
import uuid
from datetime import datetime, timedelta
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from salary_cap_system import SalaryCapSystem
from datetime import date, timedelta, datetime, time

import os as _os

DEBUG_ENABLED = _os.environ.get("PUCK_DYNASTY_DEBUG", "").lower() in ("1", "true", "yes")


def debug_print(*args, **kwargs):
    """Print only when PUCK_DYNASTY_DEBUG=1 is set. Use for all DEBUG output."""
    if DEBUG_ENABLED:
        print(*args, **kwargs)


# --- Constants and Configuration ---
class GameBalance:
    MIN_ATTRIBUTE = 1
    MAX_ATTRIBUTE = 100
    DEFAULT_MIN_ATTRIBUTE = 50
    DEFAULT_MAX_ATTRIBUTE = 90
    
    PEAK_AGE_START = 27
    PEAK_AGE_END = 32
    DEVELOPMENT_CHANCE = 0.6
    DECLINE_CHANCE = 0.4

    MAX_SCOUTING_VIEWINGS = 15


# --- Development arcs: individual career-trajectory variance ---
# A player's arc is ONE factor in the development chain, never an override.
# It composes multiplicatively with the existing factors: potential-grade
# development_speed/peak_age (prospect generation), work ethic/determination,
# coach influence, training modifiers, and the environment factor (league
# quality, morale, opportunity). Same arc + different situation = different
# career; that is the point.
ARC_PEAK_SHIFT = {"standard": 0, "late_bloomer": 2, "early_peak": -2}
ARC_SPEED_MULT = {"standard": 1.0, "late_bloomer": 0.85, "early_peak": 1.15}
# How strongly the player's growth responds to his situation (env_factor):
# late bloomers are unlocked by good situations and buried by bad ones;
# early peaks are talent-driven and less situation-sensitive.
ARC_ENV_SENSITIVITY = {"standard": 1.0, "late_bloomer": 1.3, "early_peak": 0.7}


def roll_development_arc():
    """Roll a development arc: pure individual variance, 70/15/15.

    Deliberately INDEPENDENT of potential grade and draft position. The
    grade curve already encodes population-level shapes (lower grades peak
    later); the arc is the orthogonal surprise axis. A 7th-rounder is just
    as likely to be an early peak as a 1st-rounder is to be a late bloomer
    -- nobody is locked into a pathway. That is where the
    Zetterberg/Datsyuk/Kucherov stories come from: the gem engine moves the
    ceiling, the arc moves the shape of the road there, and neither knows
    about the other's roll.
    """
    return random.choices(["standard", "late_bloomer", "early_peak"],
                          weights=[70, 15, 15])[0]


def arc_peak_shift(player):
    """Years the player's whole development curve slides by arc."""
    return ARC_PEAK_SHIFT.get(getattr(player, "development_arc", "standard"), 0)


def to_100_scale(value):
    """DEPRECATED: Attributes are now native 100-scale. This is kept for
    backward compatibility with old saves and external callers.

    Now a clamp-only passthrough. The old heuristic (doubling values < 55)
    corrupted legitimate native sub-55 ratings, e.g. prospects displayed
    at twice their real overall in scouting windows.
    """
    try:
        return max(1, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 50


# --- Enumerations for Clarity ---
class PlayerPosition(Enum):
    CENTER = "C"
    LEFT_WING = "LW"
    RIGHT_WING = "RW"
    LEFT_DEFENSE = "LD"
    RIGHT_DEFENSE = "RD"
    DEFENSE = "D"
    GOALIE = "G"

    @property
    def attribute_weights(self):
        weights = {
            PlayerPosition.CENTER: {
                'skating': 0.2, 'shooting': 0.25, 'passing': 0.25,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.LEFT_WING: {
                'skating': 0.2, 'shooting': 0.3, 'passing': 0.2,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.RIGHT_WING: {
                'skating': 0.2, 'shooting': 0.3, 'passing': 0.2,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.LEFT_DEFENSE: {
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.RIGHT_DEFENSE: {
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.DEFENSE: {  # <-- FIXED HERE
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.GOALIE: {
                'glove': 0.25, 'blocker': 0.25, 'pads': 0.25,
                'reflexes': 0.15, 'positioning': 0.1
            }
        }
        return weights[self]

class PlayerRole(Enum):
    SNIPER = "Sniper"
    PLAYMAKER = "Playmaker"
    POWER_FORWARD = "Power Forward"
    GRINDER = "Grinder"
    ENFORCER = "Enforcer"
    TWO_WAY_FORWARD = "Two-Way Forward"
    OFFENSIVE_DEFENSEMAN = "Offensive Defenseman"
    DEFENSIVE_DEFENSEMAN = "Defensive Defenseman"
    TWO_WAY_DEFENSEMAN = "Two-Way Defenseman"
    GOALIE = "Goalie"

class StaffRole(Enum):
    # Management
    GENERAL_MANAGER = "General Manager"
    ASSISTANT_GENERAL_MANAGER = "Assistant General Manager"
    
    # Coaching Staff
    HEAD_COACH = "Head Coach"
    ASSISTANT_COACH = "Assistant Coach"
    ASSOCIATE_COACH = "Associate Coach"
    GOALIE_COACH = "Goalie Coach"
    POWER_PLAY_COACH = "Power Play Coach"
    PENALTY_KILL_COACH = "Penalty Kill Coach"
    
    # Development Staff
    SKILLS_COACH = "Skills Coach"
    CONDITIONING_COACH = "Conditioning Coach"
    SKATING_COACH = "Skating Coach"
    
    # Scouting Staff
    HEAD_SCOUT = "Head Scout"
    PROFESSIONAL_SCOUT = "Professional Scout"
    AMATEUR_SCOUT = "Amateur Scout"
    ANALYTICS_DIRECTOR = "Analytics Director"
    EUROPEAN_SCOUT = "European Scout"
    ADVANCE_SCOUT = "Advance Scout"
    
    # Medical & Support Staff
    TEAM_DOCTOR = "Team Doctor"
    PHYSIOTHERAPIST = "Physiotherapist"
    EQUIPMENT_MANAGER = "Equipment Manager"
    STRENGTH_COACH = "Strength & Conditioning Coach"
    
    # Analytics & Media
    VIDEO_COACH = "Video Coach"
    STATISTICIAN = "Statistician"
    MEDIA_RELATIONS = "Media Relations"

# --- Data-Driven Class Structures ---
@dataclass
class Contract:
    """Holds all player contract details."""
    salary: int = 750000
    years_remaining: int = 0
    signing_bonus: int = 0
    performance_bonus: int = 0
    no_trade_clause: bool = False
    # Full no-movement clause: blocks trades AND waiver/AHL assignment.
    no_movement_clause: bool = False
    # Modified NTC: size of the player's no-trade list (0 = none). When the
    # actual teams are known they live in no_trade_list; otherwise the list
    # is private (as in real life) and the waiver engine estimates the
    # chance the destination is on it from modified_ntc_teams.
    modified_ntc_teams: int = 0
    # Teams this player refuses to be traded to (real-life submitted list).
    no_trade_list: list = field(default_factory=list)
    # One-transaction waiver: destination team name the player already
    # approved. Cleared when the trade completes or the deal dies.
    ntc_waiver_for: str = ""
    # Two-way contract: the deal carries a separate minor-league salary.
    # When the player is assigned to the minors he is paid ahl_salary, and
    # per the NHL burial rule the two-way minor-league salary does not
    # count against the NHL salary cap (a one-way deal in the minors
    # counts salary minus the burial exemption instead).
    two_way: bool = False
    ahl_salary: int = 0
    # Entry-level contract marker (CBA Article 9): set by
    # League.finalize_elc_signing. The season rollover reads it for the
    # slide rule; the trade/waiver engines treat ELCs as two-way.
    entry_level: bool = False
    # When modified_ntc_teams is an approved-teams list (not a no-trade
    # list), set alongside it.
    modified_ntc_approved: bool = False

@dataclass
class PlayerStats:
    """Tracks player statistics for a season."""
    goals: int = 0
    assists: int = 0
    penalties_in_minutes: int = 0
    saves: int = 0
    penalties: int = 0
    shots: int = 0
    games_played: int = 0
    shots_against: int = 0  # For goalies: total shots faced
    wins: int = 0  # Goalie wins
    losses: int = 0  # Goalie losses (incl. OTL?)
    goals_against: int = 0  # Goalie goals against
    shutouts: int = 0  # Goalie shutouts
    save_percentage: float = 0.0  # 0-1 decimal
    goals_against_avg: float = 0.0

    # Defensive season record (shutdown defensemen need a performance
    # trail, not just points). Rolled per game from defensive attributes
    # by roll_defensive_game_stats(); read by update_potential_from_season.
    hits: int = 0
    takeaways: int = 0
    blocked_shots: int = 0

    @property
    def points(self) -> int:
        return self.goals + self.assists

    def _update_goalie_stats(self):
        """Update calculated goalie statistics (SV% as 0-1 decimal, GAA)."""
        if self.shots_against > 0:
            self.save_percentage = self.saves / self.shots_against
        else:
            self.save_percentage = 0.0

        games = max(self.wins + self.losses, 1)
        self.goals_against_avg = self.goals_against / games


def roll_defensive_game_stats(player, rng=None):
    """One game's defensive record for a skater, from his attributes.

    The single shared roll behind every sim path (lightweight batch,
    AdvancedGameSim user games, watched GameSim): a shutdown defenseman's
    season leaves a statistical trail in player.stats (hits, takeaways,
    blocked_shots) that update_potential_from_season reads. Uniform across
    paths so the evaluator's thresholds mean the same thing everywhere.

    Returns (hits, takeaways, blocked_shots). Never raises.
    """
    import math as _math
    _r = rng or random
    try:
        _pos = getattr(getattr(player, "primary_position", None),
                       "value", "") or ""
        _is_d = str(_pos).upper() in ("D", "LD", "RD")
        _da = float(getattr(player, "defensive_awareness", 50) or 50)
        _chk = float(getattr(player, "checking", 50) or 50)
        _poke = float(getattr(player, "pokecheck", 50) or 50)

        def _draw(mean):
            if mean <= 0:
                return 0
            return max(0, int(round(_r.gauss(mean, _math.sqrt(mean)))))

        hits = _draw(0.55 * (_chk / 50.0) * (1.3 if _is_d else 1.0))
        takeaways = _draw(0.40 * (_poke / 50.0))
        blocked = _draw((1.15 if _is_d else 0.35) * (_da / 50.0))
        return hits, takeaways, blocked
    except Exception:
        return 0, 0, 0


# --- Season-history stint tracker -------------------------------------------
# Per-team stints for the player-card History tab. A stint opens when a
# player joins an NHL roster (Team.add_player, roster only) and closes when
# he leaves it (Team.remove_player) or at League.end_of_season. Only NHL
# roster time is tracked -- AHL/prospect moves never open stints.
#
# Stint stats are deltas: the anchor snapshots player.stats at open, the
# close subtracts it. Plain dicts throughout -- pickle/save-load safe.

# PlayerStats field -> stint dict key.
_STINT_STAT_MAP = (
    ("games_played", "gp"),
    ("goals", "g"),
    ("assists", "a"),
    ("penalties_in_minutes", "pim"),
    ("shots", "shots"),
    ("wins", "w"),
    ("losses", "l"),
    ("saves", "sv"),
    ("shots_against", "sa"),
    ("goals_against", "ga"),
    ("shutouts", "so"),
)


def _team_abbr_safe(team_name):
    """Three-letter team code without risking a circular import."""
    try:
        from playoff_system import team_abbr as _ta
        return _ta(team_name)
    except Exception:
        pass
    try:
        return (str(team_name)[:3].upper() if team_name else "???")
    except Exception:
        return "???"


def _snapshot_stint_stats(player):
    """Current player.stats as a plain {field: int} dict. Never raises."""
    try:
        _stats = getattr(player, "stats", None)
        return {f: int(getattr(_stats, f, 0) or 0)
                for f, _k in _STINT_STAT_MAP}
    except Exception:
        return {f: 0 for f, _k in _STINT_STAT_MAP}


def open_stint(player, team_abbr):
    """Open an NHL stint anchor for this team. Idempotent. Never raises."""
    try:
        if player is None or not team_abbr:
            return
        _anchor = getattr(player, "stint_anchor", None)
        if isinstance(_anchor, dict) and _anchor.get("team") == team_abbr:
            return  # already tracking this stint
        if isinstance(_anchor, dict) and _anchor.get("team"):
            close_stint(player)  # different team open: seal it first
        player.stint_anchor = {"team": team_abbr,
                               "baseline": _snapshot_stint_stats(player)}
    except Exception:
        pass


def close_stint(player):
    """Seal the open stint into a plain dict and queue it for finalizing.

    Returns the stint dict (without a season label -- League.end_of_season
    stamps it) or None when no stint was open. Never raises.
    """
    try:
        if player is None:
            return None
        _anchor = getattr(player, "stint_anchor", None)
        if not isinstance(_anchor, dict) or not _anchor.get("team"):
            return None
        _base = _anchor.get("baseline") or {}
        _now = _snapshot_stint_stats(player)
        _stint = {"team": _anchor.get("team")}
        for _f, _k in _STINT_STAT_MAP:
            _stint[_k] = max(
                0,
                int(_now.get(_f, 0) or 0) - int(_base.get(_f, 0) or 0))
        player.stint_anchor = None
        _pending = getattr(player, "_stint_pending", None)
        if not isinstance(_pending, list):
            _pending = []
            player._stint_pending = _pending
        _pending.append(_stint)
        return _stint
    except Exception:
        return None


def current_season_splits(player):
    """Per-team stint dicts for the in-progress season (no season label).

    Closed stints this season first, then the live open stint computed
    against its baseline. Used by the profile Overview card. Never raises.
    """
    _splits = []
    try:
        if player is None:
            return _splits
        for _s in (getattr(player, "_stint_pending", None) or []):
            if isinstance(_s, dict) and _s.get("team"):
                _splits.append(dict(_s))
        _anchor = getattr(player, "stint_anchor", None)
        if isinstance(_anchor, dict) and _anchor.get("team"):
            _base = _anchor.get("baseline") or {}
            _now = _snapshot_stint_stats(player)
            _cur = {"team": _anchor.get("team")}
            for _f, _k in _STINT_STAT_MAP:
                _cur[_k] = max(
                    0,
                    int(_now.get(_f, 0) or 0) - int(_base.get(_f, 0) or 0))
            _splits.append(_cur)
    except Exception:
        pass
    return _splits


player_id_counter = itertools.count()

@dataclass(eq=False)
class Player:
    """Represents a single, deeply detailed hockey player."""
    first_name: str
    last_name: str
    age: int
    primary_position: PlayerPosition
    
    id: int = field(default_factory=lambda: next(player_id_counter), init=False)
    jersey_number: int = field(default_factory=lambda: random.randint(1, 98))
    captaincy: str = None # 'C', 'A', or None
    
    # Personal information with realistic defaults
    nationality: str = "Canada"
    birthplace: str = "Unknown"
    height: str = field(default_factory=lambda: f"{random.randint(5, 6)}'{random.randint(6, 11)}\"")  # 5'6" to 6'11"
    weight: int = field(default_factory=lambda: random.randint(160, 230))  # 160-230 lbs
    handedness: str = field(default_factory=lambda: random.choice(["Left", "Right"]))
    birth_date: str = field(default_factory=lambda: f"{random.randint(1995, 2006)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}")
    draft_year: int = field(default_factory=lambda: random.randint(2010, 2024))
    draft_position: str = field(default_factory=lambda: f"Round {random.randint(1, 7)}, Pick {random.randint(1, 31)}")
    
    determination: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    teamwork: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    leadership: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    discipline: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    flair: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    consistency: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    important_matches: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    morale: int = 70  # 1-100 scale (form/confidence)

    # Football Manager-style career fields (happiness, squad status, chats)
    happiness: int = 70  # 0-100, how happy the player is at the club

    # Development arc: career trajectory variance (late bloomers / early peaks).
    # Pure individual variance, independent of grade and draft position --
    # nobody is locked into a pathway. The arc is one multiplicative factor
    # among many -- never an override.
    development_arc: str = field(default_factory=roll_development_arc)

    # Reputation system (ratchet 0-100; visible attitude/volatility 0-100)
    reputation: int = 0
    controversy: int = 0
    relationships: Dict[int, int] = field(default_factory=dict)  # other player id -> -100..100 (friend..rival)
    # Family in the hockey world: linked at generation by rare shared
    # surname (the Staals/Hughes treatment). List of other player ids.
    # Old-save safe: read via getattr(player, 'family_ids', []).
    # Career game log: signature single-game performances (hat tricks,
    # shutouts, 40-save nights...). Bounded at ~20 entries, pruned by
    # significance -- so a kid's huge night isn't forgotten when he's the
    # next man up or a trade chip. Old-save safe: read via
    # getattr(player, 'career_moments', []).
    career_moments: list = field(default_factory=list)
    # Trophy case: permanent, de-duplicated award/Cup wins.
    # Plain dicts {"award": key, "year": label} -- save/load safe.
    # Old-save safe: read via getattr(player, 'career_accolades', []).
    career_accolades: list = field(default_factory=list)
    # Season history: finalized per-team stints, one dict per stint --
    # {"season": 2027, "team": "OTT", "gp": 41, "g": 12, "a": 18,
    #  "pim": 22, "shots": 98, "w": 0, "l": 0, "sv": 0, "sa": 0,
    #  "ga": 0, "so": 0}. Appended at League.end_of_season from the
    # stint tracker below. Plain dicts -- save/load safe (pickle).
    # Old-save safe: read via getattr(player, 'season_history', []).
    season_history: list = field(default_factory=list)
    # Live stint anchor: {"team": "OTT", "baseline": {stat: value}} while
    # the player is on an NHL roster, else None. Opened by Team.add_player
    # (roster only), closed by Team.remove_player / League.end_of_season.
    # Old-save safe: read via getattr(player, 'stint_anchor', None).
    stint_anchor: object = field(default=None)
    family_ids: list = field(default_factory=list)
    reputation_history: list = field(default_factory=list)
    controversy_history: list = field(default_factory=list)
    squad_status: str = "Rotation"  # Star Player / Key Player / Regular Starter / Rotation / Prospect / Surplus
    playing_time_concern: int = 0  # 0-100, worry about lack of ice time
    transfer_requested: bool = False
    promise_made: str = ""  # e.g. "more_icetime"
    last_chat: str = ""  # ISO date of last private chat

    # Career and development tracking
    pro_debut: str = field(default_factory=lambda: f"{random.randint(2015, 2024)}-{random.randint(10, 12)}-{random.randint(1, 28):02d}")
    teams_count: int = field(default_factory=lambda: random.randint(1, 4))
    team_tenure: str = field(default_factory=lambda: random.choice(["This season", "2 years", "3 years", "4+ years"]))
    peak_rating: int = field(default_factory=lambda: random.randint(12, 20))
    potential: int = field(default_factory=lambda: random.randint(10, 20))
    
    # Health and injury tracking  
    is_injured: bool = False
    days_missed: int = 0
    career_games_missed: int = field(default_factory=lambda: random.randint(0, 50))
    last_injury: str = "None"
    injury_type: str = "None"
    games_remaining_injured: int = 0
    
    # Development attributes
    coachability: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    work_ethic: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    adaptability: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    team_chemistry: int = field(default_factory=lambda: random.randint(10, 20))

    # Traits: exceptional abilities (e.g. 'big_hitter', 'speedster') inferred
    # from attributes. See player_traits.py. Stored as trait ID strings.
    traits: list = field(default_factory=list)
    # Goalie personality (see goalie_personality.py): 'fiery' | 'calm' |
    # 'unorthodox'. Assigned at generation; skaters leave it "".
    goalie_temperament: str = ""
    # Generational goalie prospect: the rare Price/Fleury fast-track -- a
    # small chance at generation for elite-potential goalies to jump into an
    # NHL role by fate instead of the usual slow goalie curve.
    generational_goalie: bool = False
    line_chemistry: int = field(default_factory=lambda: random.randint(10, 20))

    # Perfect-mesh form tracker (-1.0 cold .. 1.0 hot) and heater counter.
    # Written by mesh_system.record_performance(), read back as a mesh input:
    # moments -> streaks -> (sometimes) breakouts. Defaults keep old saves fine.
    mesh_form: float = 0.0
    mesh_streak: int = 0
    
    # SEASON STATISTICS - Reset each season
    games_played: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    penalty_minutes: int = 0
    shots: int = 0
    avg_toi: str = "0:00"
    
    # Goalie specific season stats
    wins: int = 0
    losses: int = 0
    save_percentage: float = 0.000
    goals_against_avg: float = 0.00
    shutouts: int = 0
    saves: int = 0
    goals_against: int = 0
    shots_against: int = 0
    
    # CAREER STATISTICS - Accumulated over multiple seasons
    career_games: int = 0
    career_goals: int = 0
    career_assists: int = 0
    career_points: int = 0
    career_penalty_minutes: int = 0
    career_shots: int = 0
    
    # Goalie career stats
    career_wins: int = 0
    career_losses: int = 0
    career_shutouts: int = 0
    career_saves: int = 0
    career_goals_against: int = 0
    career_shots_against: int = 0
    career_games_goalie: int = 0
    
    # STREAKS AND SPECIAL ACHIEVEMENTS
    current_point_streak: int = 0
    current_goal_streak: int = 0
    longest_point_streak: int = 0
    longest_goal_streak: int = 0
    hat_tricks_season: int = 0
    hat_tricks_career: int = 0
    
    # RECORD TRACKING
    seasons_played: int = 0
    is_rookie: bool = True

    # Waiver related attributes
    on_waivers: bool = False
    waiver_days: int = 0
    nhl_games_played: int = 0  # career NHL GP; seeded at generation, accrued per game played
    # New-CBA paper-transaction rule (2026): a player assigned (loaned) to
    # the AHL must play at least one AHL game before he can be recalled.
    #   None -> grandfathered (old save / never assigned) -> recall OK
    #   0    -> assigned, hasn't dressed yet              -> recall BLOCKED
    #   >= 1 -> has played down there                     -> recall OK
    ahl_games_since_assignment: Optional[int] = None
    # NHL games played in each PRECEDING season (most recent last).
    # Drives Calder eligibility (25-game / 6-game rules). European pro
    # leagues don't count -- only NHL GP is recorded here.
    prior_nhl_gp: List[int] = field(default_factory=list)

    skating: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    strength: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    injury_proneness: int = field(default_factory=lambda: max(5, min(98, int(random.gauss(45, 20)))))  # 1-100; higher = more prone

    shooting: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    passing: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    deking: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))

    offensive_awareness: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    defensive_awareness: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    checking: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    faceoffs: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    goaltending: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    shoot_pass_tendency: int = field(default_factory=lambda: random.randint(0, 100))
    hitting_tendency: int = field(default_factory=lambda: random.randint(0, 100))

    potential_grade: str = field(default_factory=lambda: random.choice(['A', 'B', 'C', 'D', 'F']))
    # Prospect development (prospect_development.py): the hidden TRUTH vs the
    # scouted belief. Development grows toward true_potential_grade;
    # potential_grade is what the world believes. Old saves backfill truth =
    # belief in ensure_reputation_fields.
    true_potential_grade: str = ""
    farm_league: str = ""
    farm_season: dict = field(default_factory=dict)
    farm_history: list = field(default_factory=list)
    # Draft pedigree: round picked + the soft bust floor (Lafreniere cushion).
    draft_round: int = 0
    pedigree_floor: str = ""

    # Drafted-prospect rights lifecycle (Part 5). The club that drafted the
    # prospect holds his NHL rights until rights_expiry_year. Old-save safe:
    # always read these via getattr(player, <name>, <default>) -- saves
    # pickled before this change have no such attributes (pickle does not
    # call __init__).
    rights_team: str = ""
    rights_expiry_year: int = 0
    rights_type: str = ""  # "CHL" | "NCAA" | "EUROPE"
    drafted_year: int = 0
    playing_where: str = ""
    camp_invite: bool = False
    draft_reentry: bool = False

    contract: Contract = field(default_factory=Contract)
    stats: PlayerStats = field(default_factory=PlayerStats)
    # Playoff-only ledger: folded from GameSim.game_stats after each playoff
    # game by playoff_system. Feeds the Conn Smythe race and any future
    # playoff leaderboards. Reset alongside stats in league.end_of_season().
    # Old-save safe: always read via getattr(player, 'playoff_stats', None).
    playoff_stats: PlayerStats = field(default_factory=PlayerStats)
    # AHL-only ledger: generated by ahl_system (no AHL game sim exists).
    # NEVER mixed with NHL numbers -- NHL screens read stats/playoff_stats
    # from team.roster; the AHL screen reads ahl_stats from team.ahl_roster.
    # Reset alongside stats in league.end_of_season().
    # Old-save safe: always read via getattr(player, 'ahl_stats', None).
    ahl_stats: PlayerStats = field(default_factory=PlayerStats)

    # Salary retention (real NHL retained-salary transactions): when this
    # player is traded, his former club may keep up to 50% of the cap hit.
    # retained_amount lowers THIS player's cap hit for his current club;
    # the retaining club carries it as dead cap in team.retained_salary.
    retained_amount: int = 0
    retained_team_name: str = ""
    
    team_name: str = "Free Agent"
    x: int = 0  # X position on ice
    y: int = 0  # Y position on ice

    # New attributes (all initialized 5-20)
    stickhandling: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    vision: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    shooting_accuracy: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    shooting_power: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    passing_accuracy: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    passing_creativity: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    first_pass: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    breakout_passes: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    forechecking: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    puck_protection: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    deflections: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    shot_blocking: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    hockey_iq: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    composure: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    aggressiveness: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    work_rate: int = field(default_factory=lambda: random.randint(50, 85))
    anticipation: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    decision_making: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    focus: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    confidence: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    acceleration: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    balance: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    endurance: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    agility: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    speed: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    stamina: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    durability: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    # New attributes replacing pace and offensive_read
    off_the_puck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))  # Movement without puck
    
    # Physical and tactical attributes
    wristshot: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    slapshot: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    pokecheck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    bodycheck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    one_timer: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    backhand: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    faceoff_wins: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    screen_shots: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    loose_puck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    creativity: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    pressure_player: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))  # Performance under pressure
    # Goalie-specific attributes
    reflexes: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    positioning: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    rebound_control: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    puck_handling: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    glove_hand: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    stick_side: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    breakaway_skill: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    # Waiver attributes
    on_waivers: bool = False
    waiver_days: int = 0
    nhl_games_played: int = 0  # career NHL GP; seeded at generation, accrued per game played
    # New-CBA paper-transaction rule (2026): a player assigned (loaned) to
    # the AHL must play at least one AHL game before he can be recalled.
    # None = grandfathered (old save / never assigned) -> recall OK.
    ahl_games_since_assignment: Optional[int] = None

    def __post_init__(self):
        """Adjusts attributes based on position after initialization."""
        if self.primary_position == PlayerPosition.CENTER:
            self.faceoffs = random.randint(30, 45)
        elif self.primary_position == PlayerPosition.GOALIE:
            self.goaltending = random.randint(30, 45)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
        
    def __hash__(self):
        """Make Player objects hashable based on their ID."""
        return hash(self.id)
        
    def __eq__(self, other):
        """Compare Player objects based on their ID."""
        if not isinstance(other, Player):
            return False
        return self.id == other.id

    def get_role(self) -> PlayerRole:
        """Dynamically determines the player's role based on their attributes (native 1-100 scale)."""
        if self.primary_position == PlayerPosition.GOALIE:
            return PlayerRole.GOALIE
        
        if self.primary_position in (PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE):
            if self.offensive_awareness > 70 and self.shooting > 65:
                return PlayerRole.OFFENSIVE_DEFENSEMAN
            if self.defensive_awareness > 70 and self.checking > 65:
                return PlayerRole.DEFENSIVE_DEFENSEMAN
            return PlayerRole.TWO_WAY_DEFENSEMAN
            
        if self.shooting > 75 and self.offensive_awareness > 70:
            return PlayerRole.SNIPER
        if self.passing > 75 and self.flair > 70:
            return PlayerRole.PLAYMAKER
        if self.strength > 70 and self.checking > 68 and self.hitting_tendency > 60:
            return PlayerRole.POWER_FORWARD
        if self.strength > 75 and self.checking > 75 and self.discipline < 35:
            return PlayerRole.ENFORCER
        if self.determination > 68 and self.teamwork > 68 and self.defensive_awareness > 60:
            return PlayerRole.GRINDER
        return PlayerRole.TWO_WAY_FORWARD

    def overall_rating(self) -> int:
        """Calculates a weighted overall rating based on position, including all attributes."""
        if self.primary_position == PlayerPosition.GOALIE:
            rating = (
                self.goaltending * 0.12 +
                self.reflexes * 0.15 +
                self.positioning * 0.15 +
                self.rebound_control * 0.12 +
                self.puck_handling * 0.08 +
                self.glove_hand * 0.08 +
                self.stick_side * 0.08 +
                self.breakaway_skill * 0.08 +
                self.confidence * 0.05 +
                self.focus * 0.05 +
                self.composure * 0.04
            )
        elif self.primary_position == PlayerPosition.CENTER:
            rating = (
                self.skating * 0.08 +
                self.shooting * 0.06 +
                self.shooting_accuracy * 0.06 +
                self.shooting_power * 0.05 +
                self.passing * 0.07 +
                self.passing_accuracy * 0.06 +
                self.passing_creativity * 0.06 +
                self.deking * 0.05 +
                self.stickhandling * 0.06 +
                self.vision * 0.06 +
                self.hockey_iq * 0.06 +
                self.offensive_awareness * 0.06 +
                self.defensive_awareness * 0.05 +
                self.faceoffs * 0.07 +
                self.faceoff_wins * 0.04 +
                self.composure * 0.04 +
                self.endurance * 0.04 +
                self.determination * 0.04 +
                self.off_the_puck * 0.04 +
                self.one_timer * 0.03 +
                self.loose_puck * 0.02
            )
        elif self.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
            rating = (
                self.skating * 0.09 +
                self.shooting * 0.08 +
                self.shooting_accuracy * 0.07 +
                self.shooting_power * 0.07 +
                self.wristshot * 0.06 +
                self.slapshot * 0.05 +
                self.passing * 0.06 +
                self.passing_accuracy * 0.05 +
                self.passing_creativity * 0.05 +
                self.deking * 0.06 +
                self.stickhandling * 0.06 +
                self.vision * 0.06 +
                self.hockey_iq * 0.06 +
                self.offensive_awareness * 0.07 +
                self.defensive_awareness * 0.04 +
                self.composure * 0.04 +
                self.endurance * 0.04 +
                self.determination * 0.04 +
                self.off_the_puck * 0.05 +
                self.one_timer * 0.04 +
                self.backhand * 0.03 +
                self.screen_shots * 0.03
            )
        elif self.primary_position in (PlayerPosition.DEFENSE,
                                             PlayerPosition.LEFT_DEFENSE,
                                             PlayerPosition.RIGHT_DEFENSE):
            rating = (
                self.skating * 0.08 +
                self.passing * 0.06 +
                self.passing_accuracy * 0.06 +
                self.passing_creativity * 0.05 +
                self.strength * 0.07 +
                self.checking * 0.07 +
                self.bodycheck * 0.06 +
                self.defensive_awareness * 0.09 +
                self.shot_blocking * 0.07 +
                self.pokecheck * 0.06 +
                self.anticipation * 0.06 +
                self.hockey_iq * 0.06 +
                self.composure * 0.05 +
                self.aggressiveness * 0.05 +
                self.balance * 0.05 +
                self.endurance * 0.05 +
                self.determination * 0.05 +
                self.slapshot * 0.04 +
                self.loose_puck * 0.04 +
                self.pressure_player * 0.04
            )
        else:
            # Fallback for other positions
            rating = (
                self.skating * 0.10 +
                self.shooting * 0.08 +
                self.passing * 0.08 +
                self.deking * 0.07 +
                self.stickhandling * 0.07 +
                self.vision * 0.07 +
                self.hockey_iq * 0.07 +
                self.offensive_awareness * 0.07 +
                self.defensive_awareness * 0.07 +
                self.composure * 0.07 +
                self.endurance * 0.07 +
                self.determination * 0.07 +
                self.off_the_puck * 0.05 +
                self.loose_puck * 0.04
            )
        return max(1, min(99, int(rating)))
    def _potential_cap(self) -> int:
        """Overall-rating ceiling implied by the player's potential grade.

        Grades map onto the live overall scale (generated players sit
        ~62-83; generational talents reach ~90). Tier gaps preserve the
        original design's spacing (a full grade ~ 6-7 points).

        Uses the TRUE (hidden) grade: a late-round gem develops toward what
        he really is, not what the scouts think. Falls back to the displayed
        grade for old saves.
        """
        g = ((getattr(self, "true_potential_grade", "") or
              self.potential_grade) or 'C').strip().upper()
        base = {'A': 87, 'B': 82, 'C': 76, 'D': 69, 'F': 62}
        cap = base.get(g[:1], 76)
        if len(g) > 1:
            if g[1] == '+':
                cap += 3
            elif g[1] == '-':
                cap -= 3
        return cap

    # Ordered grade ladder for dynamic potential movement
    POTENTIAL_LADDER = ["F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]

    # Development curves per potential grade. Higher-touted prospects
    # develop faster but peak earlier; lower-touted types develop slower and
    # peak later -- the late-bloomer shape (Zetterberg/Datsyuk). Values mirror
    # the draft generator's grade table.
    GRADE_DEVELOPMENT = {
        "A+": {"development_speed": 1.5, "peak_age": 25},
        "A":  {"development_speed": 1.4, "peak_age": 26},
        "A-": {"development_speed": 1.3, "peak_age": 26},
        "B+": {"development_speed": 1.2, "peak_age": 27},
        "B":  {"development_speed": 1.1, "peak_age": 27},
        "B-": {"development_speed": 1.0, "peak_age": 27},
        "C+": {"development_speed": 0.9, "peak_age": 28},
        "C":  {"development_speed": 0.8, "peak_age": 28},
        "C-": {"development_speed": 0.7, "peak_age": 29},
        "D":  {"development_speed": 0.6, "peak_age": 30},
        "D+": {"development_speed": 0.6, "peak_age": 30},
        "F":  {"development_speed": 0.5, "peak_age": 31},
    }

    def _grade_development(self) -> dict:
        # True grade drives the curve too: a hidden gem develops on a star's
        # schedule (faster, earlier peak), not a grinder's.
        g = ((getattr(self, "true_potential_grade", "") or
              self.potential_grade) or "C").strip().upper()
        return self.GRADE_DEVELOPMENT.get(g,
               self.GRADE_DEVELOPMENT.get(g[:1], {"development_speed": 0.8,
                                                 "peak_age": 28}))

    def update_potential_from_season(self):
        """Dynamically adjust potential_grade based on just-completed season.

        Breakout years raise the ceiling (a C prospect who scores like a
        star becomes a B); highly-touted prospects who underperform see
        their ceiling drop. This runs at season end, BEFORE stats reset.

        Only applies to players in development years (age < 27) who played
        meaningful games. Movement is one grade step, probabilistic.
        """
        if self.age >= 27:
            return

        is_goalie = getattr(getattr(self, 'primary_position', None), 'value', '') == 'G'
        gp = getattr(self.stats, 'games_played', 0)

        # Meaningful sample size
        min_gp = 15 if is_goalie else 20
        if gp < min_gp:
            return

        current = (self.potential_grade or 'C').strip().upper()
        # Normalize to ladder (handle bare 'A'/'B'/etc.)
        if current not in self.POTENTIAL_LADDER:
            # Map bare grades to ladder equivalents
            bare_map = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'F': 'F'}
            current = bare_map.get(current[:1], 'C')
        try:
            idx = self.POTENTIAL_LADDER.index(current)
        except ValueError:
            return

        breakout = False
        bust = False

        if is_goalie:
            sv = getattr(self.stats, 'save_percentage', 0)
            # Breakout: .915+ SV% over meaningful games at young age
            if sv >= 0.915 and self.age <= 25:
                breakout = True
            # Bust: below .890 despite high expectations
            elif sv < 0.890 and sv > 0 and idx >= self.POTENTIAL_LADDER.index("B-"):
                bust = True
        else:
            points = getattr(self.stats, 'points', 0)
            ppg = points / gp if gp > 0 else 0
            # Age-adjusted expectations: younger players get more credit
            # for the same production (breakout trajectory)
            if self.age <= 20:
                breakout_ppg, bust_ppg = 0.65, 0.25
            elif self.age <= 23:
                breakout_ppg, bust_ppg = 0.85, 0.35
            else:  # 24-26
                breakout_ppg, bust_ppg = 1.00, 0.45

            if ppg >= breakout_ppg:
                breakout = True
            elif ppg < bust_ppg and idx >= self.POTENTIAL_LADDER.index("B-"):
                bust = True

            # Shutdown defensemen: an elite defensive season moves the
            # ceiling too -- the evaluator was offense-only and never saw
            # them. Strong defensive play also shields a low-scoring D
            # from the bust tag: he's earning his grade in his own end.
            try:
                _pos = getattr(getattr(self, "primary_position", None),
                               "value", "")
                if str(_pos).upper() in ("D", "LD", "RD"):
                    _st = self.stats
                    _def_rate = ((getattr(_st, "blocked_shots", 0) or 0)
                                 + (getattr(_st, "takeaways", 0) or 0)) / gp
                    if _def_rate >= 2.4:
                        breakout = True
                    elif _def_rate >= 1.9:
                        bust = False
            except Exception:
                pass

        # Apply movement (probabilistic, one step)
        if breakout and idx < len(self.POTENTIAL_LADDER) - 1:
            if random.random() < 0.65:  # 65% chance breakout sticks
                self.potential_grade = self.POTENTIAL_LADDER[idx + 1]
        elif bust and idx > 0:
            _bust_p = 0.45  # 45% chance bust drops potential
            try:
                # Pedigree cushion: high picks get a long leash even in the
                # NHL -- the floor is soft, not a wall.
                import prospect_development as _pd
                if idx - 1 < _pd.pedigree_floor_index(self):
                    _bust_p *= 0.3
            except Exception:
                pass
            if random.random() < _bust_p:
                self.potential_grade = self.POTENTIAL_LADDER[idx - 1]

    def age_one_year(self, env_factor: float = 1.0):
        """Handles player aging, development, and decline.

        env_factor: the prospect-development environment multiplier
        (prospect_development.development_environment_factor) -- age window,
        league quality, morale, role. Defaults to 1.0 (old behavior).
        """
        self.age += 1
        if self.contract.years_remaining > 0:
            self.contract.years_remaining -= 1

        potential_cap = self._potential_cap()
        dev = self._grade_development()

        # Development arc: the player's individual trajectory variance, wired
        # in as a factor alongside the grade factors -- it shifts the grade's
        # peak age, scales its development speed, and tunes how strongly the
        # player's situation (env_factor: league quality, morale, opportunity)
        # moves his growth. Same grade + same arc + different situation =
        # different career. Nothing here overrides the grade curve; the arc
        # multiplies with it.
        arc = getattr(self, "development_arc", "standard")
        peak_shift = ARC_PEAK_SHIFT.get(arc, 0)
        speed_mult = ARC_SPEED_MULT.get(arc, 1.0)
        env_sens = ARC_ENV_SENSITIVITY.get(arc, 1.0)

        # Development closes a fraction of the gap to the player's ceiling
        # each year: prospects surge, established players refine slowly.
        # Higher-touted grades develop faster (development_speed) but stop
        # earlier (peak_age); late-round types grow slower and longer.
        # Peak age is the last developing year: a late-blooming grade keeps
        # growing long after an early-peaking one has stopped. The arc slides
        # that whole window for the individual.
        if self.age <= dev["peak_age"] + peak_shift and self.overall_rating() < potential_cap:
            gap = potential_cap - self.overall_rating()
            if self.age <= 20:
                frac = 0.25
            elif self.age <= 23:
                frac = 0.18
            elif self.age <= 26:
                frac = 0.10
            else:
                frac = 0.05
            frac *= dev["development_speed"] * speed_mult
            # Farm/junior environment: the 17-20 window, league quality,
            # morale, and opportunity compound here (EHM on steroids).
            # Arc x circumstance: a late bloomer is unlocked (or buried) by
            # his situation far more than a talent-driven early peak is.
            try:
                env_mult = max(0.5, min(1.6, float(env_factor)))
                env_mult = 1.0 + (env_mult - 1.0) * env_sens
                frac *= env_mult
            except Exception:
                pass
            frac *= random.uniform(0.8, 1.2)
            # Convert the desired overall gain into attribute points. A +1 to a
            # random OVR attribute is worth ~1/len(ovr_attrs) overall, and 75%
            # of development points land on OVR attributes (empirically ~0.9x
            # after weight skew and flavor-list overlap).
            gain = gap * frac
            # Surge cap scales with the grade's development speed so elite
            # teens can actually surge; floor keeps ceilings reachable
            # instead of asymptoting forever short of them. Never overshoot.
            gain = min(gain, 7.0 * dev["development_speed"])
            gain = max(gain, 2.0 * dev["development_speed"])
            gain = min(gain, gap)
            per_point = 0.9 / max(1, len(self._ovr_attributes()))
            attr_points = max(1, int(gain / per_point))
            for _ in range(attr_points):
                self._change_random_attribute(1)
        elif self.age > GameBalance.PEAK_AGE_END + peak_shift:
            if random.random() < GameBalance.DECLINE_CHANCE:
                self._change_random_attribute(-1)

    def _ovr_attributes(self) -> list:
        """Attribute names that feed this player's positional overall rating."""
        if self.primary_position == PlayerPosition.GOALIE:
            return ['goaltending', 'reflexes', 'positioning', 'rebound_control',
                    'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill',
                    'confidence', 'focus', 'composure']
        if self.primary_position == PlayerPosition.CENTER:
            return ['skating', 'shooting', 'shooting_accuracy', 'shooting_power',
                    'passing', 'passing_accuracy', 'passing_creativity', 'deking',
                    'stickhandling', 'vision', 'hockey_iq', 'offensive_awareness',
                    'defensive_awareness', 'faceoffs', 'faceoff_wins', 'composure',
                    'endurance', 'determination', 'off_the_puck', 'one_timer',
                    'loose_puck']
        if self.primary_position in (PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING):
            return ['skating', 'shooting', 'shooting_accuracy', 'shooting_power',
                    'wristshot', 'slapshot', 'passing', 'passing_accuracy',
                    'passing_creativity', 'deking', 'stickhandling', 'vision',
                    'hockey_iq', 'offensive_awareness', 'defensive_awareness',
                    'composure', 'endurance', 'determination', 'off_the_puck',
                    'one_timer', 'backhand', 'screen_shots']
        if self.primary_position in (PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE,
                                     PlayerPosition.RIGHT_DEFENSE):
            return ['skating', 'passing', 'passing_accuracy', 'passing_creativity',
                    'strength', 'checking', 'bodycheck', 'defensive_awareness',
                    'shot_blocking', 'pokecheck', 'anticipation', 'hockey_iq',
                    'composure', 'aggressiveness', 'balance', 'endurance',
                    'determination', 'slapshot', 'loose_puck', 'pressure_player']
        return ['skating', 'shooting', 'passing', 'deking', 'stickhandling',
                'vision', 'hockey_iq', 'offensive_awareness', 'defensive_awareness',
                'composure', 'endurance', 'determination', 'off_the_puck',
                'loose_puck']

    def _change_random_attribute(self, amount: int):
        """Helper to randomly increase or decrease a skill attribute."""
        # Development targets attributes that actually move the player's OVR;
        # occasionally (25%) it touches a secondary attribute for flavor.
        if random.random() < 0.75:
            skill_attributes = self._ovr_attributes()
        else:
            skill_attributes = [
            'skating', 'strength', 'shooting', 'passing', 'deking',
            'offensive_awareness', 'defensive_awareness', 'checking', 'faceoffs',
            'goaltending', 'determination', 'teamwork', 'leadership', 'discipline', 'flair',
            'stickhandling', 'vision', 'shooting_accuracy', 'shooting_power',
            'passing_accuracy', 'passing_creativity', 'puck_protection', 'deflections',
            'shot_blocking', 'hockey_iq', 'composure', 'aggressiveness', 'work_rate',
            'anticipation', 'decision_making', 'focus', 'confidence', 'acceleration',
            'balance', 'endurance', 'agility', 'speed', 'stamina', 'durability',
            'off_the_puck', 'wristshot', 'slapshot', 'pokecheck', 'bodycheck',
            'one_timer', 'backhand', 'faceoff_wins', 'screen_shots', 'loose_puck',
            'creativity', 'pressure_player', 'reflexes', 'positioning', 'rebound_control',
            'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill'
        ]
        
        attr_to_change = random.choice(skill_attributes)
        current_value = getattr(self, attr_to_change)
        
        new_value = max(GameBalance.MIN_ATTRIBUTE, min(GameBalance.MAX_ATTRIBUTE, current_value + amount))
        
        setattr(self, attr_to_change, new_value)

    @property
    def value(self):
        """Calculate player's market value based on attributes and performance."""
        # Base value determined by overall rating
        base_value = self.overall_rating() * 100000
        
        # Age modifier - players in their prime (23-29) get premium
        age_modifier = 1.0
        if 23 <= self.age <= 29:
            age_modifier = 1.2
        elif self.age >= 30:
            # Declining value with age
            age_modifier = max(0.5, 1.0 - ((self.age - 30) * 0.05))
        
        # Position modifier - centers and first-line defensemen get premium
        position_modifier = 1.0
        if self.primary_position == PlayerPosition.CENTER:
            position_modifier = 1.15
        elif self.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            position_modifier = 1.1
        elif self.primary_position == PlayerPosition.GOALIE:
            # Goalies have different value curve
            position_modifier = 1.0 if self.overall_rating() >= 75 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if self.age <= 25:
            potential_map = {'A': 1.5, 'B': 1.3, 'C': 1.1, 'D': 1.0, 'F': 0.9}
            potential_modifier = potential_map.get(self.potential_grade, 1.0)
        
        # Stats performance bonus (simplified for now)
        stats = getattr(self, 'stats', None)
        performance_bonus = 0
        if stats:
            performance_bonus = getattr(stats, 'goals', 0) * 50000 + getattr(stats, 'assists', 0) * 30000
        
        # Calculate final market value
        market_value = (base_value * age_modifier * position_modifier * potential_modifier) + performance_bonus
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
    
    def negotiate_contract(self, salary, years):
        min_salary = self.value * 0.9
        max_salary = self.value * 1.2
        if min_salary <= salary <= max_salary and years >= 1:
            return True
        return False
    
    def add_game_stats(self, goals=0, assists=0, penalty_minutes=0, plus_minus=0, shots=0,
                      wins=0, losses=0, saves=0, goals_against=0, shots_against=0, shutout=False):
        """Add statistics from a single game"""
        # Season stats
        self.games_played += 1
        self.goals += goals
        self.assists += assists
        self.points = self.goals + self.assists
        self.penalty_minutes += penalty_minutes
        self.plus_minus += plus_minus
        self.shots += shots
        
        # Career stats  
        self.career_games += 1
        self.career_goals += goals
        self.career_assists += assists
        self.career_points = self.career_goals + self.career_assists
        self.career_penalty_minutes += penalty_minutes
        self.career_shots += shots
        
        # Goalie stats
        if self.primary_position == PlayerPosition.GOALIE:
            self.wins += wins
            self.losses += losses
            self.saves += saves
            self.goals_against += goals_against
            self.shots_against += shots_against
            
            self.career_wins += wins
            self.career_losses += losses
            self.career_saves += saves
            self.career_goals_against += goals_against
            self.career_shots_against += shots_against
            if wins > 0 or losses > 0:
                self.career_games_goalie += 1
                
            if shutout:
                self.shutouts += 1
                self.career_shutouts += 1
                
            # Update percentages
            self._update_goalie_stats()
        
        # Handle streaks
        if goals + assists > 0:
            self.current_point_streak += 1
            self.longest_point_streak = max(self.longest_point_streak, self.current_point_streak)
        else:
            self.current_point_streak = 0
            
        if goals > 0:
            self.current_goal_streak += 1
            self.longest_goal_streak = max(self.longest_goal_streak, self.current_goal_streak)
        else:
            self.current_goal_streak = 0
            
        # Track hat tricks
        if goals >= 3:
            self.hat_tricks_season += 1
            self.hat_tricks_career += 1
    
    def _update_goalie_stats(self):
        """Update calculated goalie statistics"""
        if self.shots_against > 0:
            self.save_percentage = self.saves / self.shots_against
        else:
            self.save_percentage = 0.0
            
        games = max(self.wins + self.losses, 1)
        self.goals_against_avg = self.goals_against / games
    
    def reset_season_stats(self):
        """Reset season statistics for a new season"""
        # Archive the finished season's NHL GP for Calder eligibility
        # BEFORE zeroing. Only NHL games count -- AHL/European pro
        # seasons don't touch rookie status.
        try:
            prior = getattr(self, "prior_nhl_gp", None)
            if prior is None:
                prior = []
                self.prior_nhl_gp = prior
            prior.append(int(getattr(self, "games_played", 0) or 0))
            del prior[:-5]  # keep the last five seasons; older is irrelevant
        except Exception:
            pass
        self.games_played = 0
        self.goals = 0
        self.assists = 0
        self.points = 0
        self.penalty_minutes = 0
        self.plus_minus = 0
        self.shots = 0
        self.wins = 0
        self.losses = 0
        self.shutouts = 0
        self.saves = 0
        self.goals_against = 0
        self.shots_against = 0
        self.save_percentage = 0.0
        self.goals_against_avg = 0.0
        self.hat_tricks_season = 0
        self.current_point_streak = 0
        self.current_goal_streak = 0
        
        self.seasons_played += 1
        self.is_rookie = (self.seasons_played == 1)
    
    def get_ppg(self) -> float:
        """Get points per game"""
        if self.games_played == 0:
            return 0.0
        return self.points / self.games_played
    
    def get_career_ppg(self) -> float:
        """Get career points per game"""
        if self.career_games == 0:
            return 0.0
        return self.career_points / self.career_games
    
    def get_goals_per_game(self) -> float:
        """Get goals per game"""
        if self.games_played == 0:
            return 0.0
        return self.goals / self.games_played
    
    def get_shooting_percentage(self) -> float:
        """Get shooting percentage"""
        if self.shots == 0:
            return 0.0
        return (self.goals / self.shots) * 100
    
    def get_career_save_percentage(self) -> float:
        """Get career save percentage for goalies"""
        if self.career_shots_against == 0:
            return 0.0
        return self.career_saves / self.career_shots_against
    
    def get_career_gaa(self) -> float:
        """Get career goals against average"""
        if self.career_games_goalie == 0:
            return 0.0
        return self.career_goals_against / self.career_games_goalie
    
    def get_stat_for_record_check(self, stat_type: str) -> int:
        """Get current stat value for record comparison"""
        stat_mapping = {
            'single_season_goals': self.goals,
            'single_season_assists': self.assists, 
            'single_season_points': self.points,
            'single_season_pim': self.penalty_minutes,
            'single_season_wins': self.wins,
            'single_season_shutouts': self.shutouts,
            'career_goals': self.career_goals,
            'career_assists': self.career_assists,
            'career_points': self.career_points,
            'career_pim': self.career_penalty_minutes,
            'career_wins': self.career_wins,
            'career_shutouts': self.career_shutouts,
            'career_games': self.career_games,
            'longest_point_streak': self.current_point_streak,
            'longest_goal_streak': self.current_goal_streak,
            'most_hat_tricks_season': self.hat_tricks_season,
            'most_hat_tricks_career': self.hat_tricks_career,
        }
        return stat_mapping.get(stat_type, 0)

def _staff_attr_100() -> int:
    """Lifelike 1-100 staff attribute: bell curve around 65 (NHL-calibre
    competence), clamped 30-99. True 90+ elites and sub-40 liabilities are
    rare -- the granularity the sim engine deserves."""
    return max(30, min(99, int(random.gauss(65, 12))))


# ---------------------------------------------------------------------------
# Staff market: budgets, asks, and approach rules (Sept 2026)
#
# Every club operates under an annual staff payroll budget (hockey-ops
# spending, separate from the player salary cap). Top coaches cost real
# money, so clubs must budget for them. Approach rules mirror real hockey:
# unemployed staff and overseas coaches can be talked to any time; another
# club's AHL staff can only be approached in the offseason; another club's
# NHL staff are not approachable.
# ---------------------------------------------------------------------------

# Base annual ask by role for a mid-reputation staffer. The actual ask
# scales with reputation; the user types an exact dollar offer against it.
_STAFF_ASK_BASE = {
    StaffRole.HEAD_COACH: 2_200_000,
    StaffRole.ASSOCIATE_COACH: 800_000,
    StaffRole.ASSISTANT_COACH: 600_000,
    StaffRole.GOALIE_COACH: 500_000,
    StaffRole.POWER_PLAY_COACH: 450_000,
    StaffRole.PENALTY_KILL_COACH: 450_000,
    StaffRole.GENERAL_MANAGER: 1_500_000,
    StaffRole.ASSISTANT_GENERAL_MANAGER: 700_000,
    StaffRole.HEAD_SCOUT: 350_000,
    StaffRole.ANALYTICS_DIRECTOR: 400_000,
    StaffRole.PROFESSIONAL_SCOUT: 175_000,
    StaffRole.AMATEUR_SCOUT: 175_000,
    StaffRole.EUROPEAN_SCOUT: 175_000,
    StaffRole.ADVANCE_SCOUT: 175_000,
    StaffRole.SKILLS_COACH: 300_000,
    StaffRole.SKATING_COACH: 300_000,
    StaffRole.CONDITIONING_COACH: 300_000,
}
_STAFF_ASK_DEFAULT = 250_000


def staff_market_ask(staff) -> int:
    """What a staffer asks per year on the open market.

    Role base scaled by reputation: a 95-rep head coach asks ~$4M, a
    50-rep scout ~$220k. Rounded to the nearest $25k.
    """
    base = _STAFF_ASK_BASE.get(getattr(staff, "role", None), _STAFF_ASK_DEFAULT)
    try:
        rep = max(0, min(100, int(getattr(staff, "reputation", 50) or 50)))
    except Exception:
        rep = 50
    ask = base * (0.6 + (rep / 100.0) * 1.3)
    return int(round(ask / 25_000.0) * 25_000)


# Annual staff payroll budgets by market tier. Big-market clubs outspend
# small-market clubs on hockey ops, as in real life. Tunable in one place.
_STAFF_BUDGET_BIG = 13_000_000
_STAFF_BUDGET_MID = 10_000_000
_STAFF_BUDGET_SMALL = 7_000_000

_STAFF_BUDGET_BIG_MARKETS = {
    "Toronto Maple Leafs", "Montreal Canadiens", "NY Rangers",
    "Chicago Blackhawks", "Boston Bruins", "Detroit Red Wings",
    "Philadelphia Flyers", "Los Angeles Kings",
}
_STAFF_BUDGET_SMALL_MARKETS = {
    "Buffalo Sabres", "Ottawa Senators", "Winnipeg Jets",
    "Carolina Hurricanes", "Columbus Blue Jackets", "Florida Panthers",
    "Utah Hockey Club", "Anaheim Ducks", "San Jose Sharks",
    "Nashville Predators",
}


def default_staff_budget(team_name: str) -> int:
    """Annual staff payroll budget for a club, by market tier."""
    name = str(team_name or "")
    if name in _STAFF_BUDGET_BIG_MARKETS:
        return _STAFF_BUDGET_BIG
    if name in _STAFF_BUDGET_SMALL_MARKETS:
        return _STAFF_BUDGET_SMALL
    return _STAFF_BUDGET_MID


def team_can_afford_staff(team, salary: int) -> bool:
    """True if the club can take on this annual salary within its budget."""
    try:
        budget = int(getattr(team, "staff_budget", _STAFF_BUDGET_MID) or 0)
        payroll = sum(int(getattr(s, "salary", 0) or 0)
                      for s in (getattr(team, "staff", None) or []))
        return payroll + int(salary or 0) <= budget
    except Exception:
        return True


def is_offseason(current_date) -> bool:
    """Coaching silly season: May through September (the codebase's own
    phase logic treats May/early-June plus Aug-Sep as off-season)."""
    try:
        return int(getattr(current_date, "month", 0)) in (5, 6, 7, 8, 9)
    except Exception:
        return False


def can_approach_staff(staff, employer_team=None, user_team=None,
                       current_date=None):
    """Approach rules for the staff market.

    employer_team is None for pool staff (free agents, overseas).
    Returns (allowed: bool, reason: str).
    """
    try:
        if (employer_team is not None and user_team is not None
                and employer_team is user_team):
            return False, "Already on your staff."
        if employer_team is None:
            # Unemployed free agents and overseas coaches: fair game.
            return True, ""
        club = getattr(employer_team, "team_name", "that club")
        assignment = getattr(staff, "assignment", "nhl") or "nhl"
        if assignment == "ahl":
            if is_offseason(current_date):
                return True, ""
            return (False,
                    f"Under contract with {club}'s AHL club \u2014 "
                    "minor-league staff can only be approached in the offseason.")
        return (False,
                f"Under contract with {club}'s NHL staff \u2014 not available.")
    except Exception:
        return True, ""


# ---------------------------------------------------------------------------
# Staff aging and development (Sept 2026)
#
# Coaches develop like players do: young staff grow with experience, prime
# staff hold steady, and coaches 60+ regress -- unless they have icon status
# in the league (icon_level "icon" or reputation 85+), in which case their
# craft holds. Staff were previously ageless and immortal; every season
# rollover now ages them one year, moves their coaching attributes by age
# band, and gently retires the oldest so the coaching carousel keeps
# turning.
# ---------------------------------------------------------------------------

# Every coaching attribute that moves with age/experience (1-100 scale).
_STAFF_DEVELOP_ATTRS = (
    "coaching_forwards", "coaching_defensemen", "coaching_goalies",
    "tactical_knowledge", "game_preparation", "match_preparation",
    "working_with_youngsters", "player_development",
    "man_management", "motivating", "discipline", "leadership",
    "judging_player_ability", "judging_player_potential",
    "media_handling", "determination", "adaptability",
    "level_of_discipline", "attacking_coaching", "defensive_coaching",
    "mental_coaching", "technical_coaching",
)

# Reputation at/above this counts as icon status in the league: the game
# already prices and covets these coaches as legends.
_STAFF_ICON_REPUTATION = 85


def staff_is_icon(staff) -> bool:
    """Icon status in the league: stamped icons and 85+ reputation coaches."""
    try:
        if getattr(staff, "icon_level", "") == "icon":
            return True
        return int(getattr(staff, "reputation", 0) or 0) >= _STAFF_ICON_REPUTATION
    except Exception:
        return False


def _staff_growth_rate(age: int, icon: bool) -> float:
    """Base attribute points per year by age band (before employment factor
    and diminishing returns). Deliberately modest: a 28-year-old riser
    gains ~1.5/yr at the low end, and the headroom curve below grinds that
    toward zero as he approaches elite levels. Nobody maxes out."""
    if age <= 34:
        return 1.2
    if age <= 44:
        return 0.6
    if age <= 54:
        return 0.0
    if age <= 59:
        return -0.5
    # 60+: past their prime unless they're an icon of the league.
    return 0.0 if icon else -2.0


def _staff_headroom(attr_value: int) -> float:
    """Diminishing returns on growth: 60->70 is easy, 90->95 is a grind.

    Scales development by headroom to 95, so the age curve asymptotes at
    elite and can never push past it -- only breakthrough seasons (below)
    can carry a coach into the 96-99 band, one hard-earned point at a
    time. Applies to growth only; the age curve hits fading veterans at
    full force.
    """
    try:
        return max(0.0, min(1.0, (95 - int(attr_value or 60)) / 35.0))
    except Exception:
        return 1.0


def develop_staff_member(staff, employed: bool = True,
                         assignment: str = "nhl") -> dict:
    """Move one staffer's coaching attributes for a season of experience.

    Returns {attr: delta} for the attributes that changed (transparency for
    QA/UI). Employed coaches develop faster than the unemployed; NHL chairs
    develop fastest. Attributes clamp to the 25-99 band.
    """
    deltas = {}
    try:
        age = int(getattr(staff, "age", 40) or 40)
    except Exception:
        age = 40
    icon = staff_is_icon(staff)
    base = _staff_growth_rate(age, icon)
    # Employment factor: working coaches sharpen faster; an employed
    # veteran also holds off decline a little better.
    if employed:
        emp = 1.25 if (assignment or "nhl") == "nhl" else 1.0
    else:
        emp = 0.5
    if base < 0 and employed:
        emp = min(emp, 0.75)
    for attr in _STAFF_DEVELOP_ATTRS:
        try:
            cur = int(getattr(staff, attr, 65) or 65)
        except Exception:
            continue
        noise = random.uniform(-0.75, 0.75)
        # Diminishing returns on the way up: the closer to elite, the
        # slower the climb, and the age curve tops out at 95 -- anything
        # above that is breakthrough-built and only breakthroughs or
        # decline move it. Decline hits at full force.
        if base > 0:
            if cur >= 96:
                continue
            delta = int(round(base * emp * _staff_headroom(cur) + noise))
            cap = 95
        elif base < 0:
            delta = int(round(base * emp + noise))
            cap = 99
        else:
            # Prime plateau (45-54): hold serve. A whisper of +/-1 keeps
            # cards alive, but it never pushes past 95.
            if cur >= 96:
                continue
            r = random.random()
            if r < 0.90:
                continue
            delta = 1 if r < 0.95 else -1
            cap = 95
        if delta == 0:
            continue
        new = max(25, min(cap, cur + delta))
        if new == cur:
            continue
        setattr(staff, attr, new)
        deltas[attr] = new - cur
    # Reputation drifts with the craft for non-icons: a fading veteran
    # slowly loses league standing; a rising young coach gains it. Icons
    # keep theirs -- that's what icon status means. Steady development
    # alone can build a name to ~80; beyond that takes results
    # (breakthroughs), so aging never mints legends by itself.
    try:
        if not icon and deltas:
            avg = sum(deltas.values()) / len(deltas)
            rep = int(getattr(staff, "reputation", 50) or 50)
            if avg > 0.5 and rep < 80:
                staff.reputation = min(80, rep + 1)
            elif avg < -0.25 and rep > 10:
                drop = 2 if random.random() < 0.5 else 1
                staff.reputation = max(10, rep - drop)
    except Exception:
        pass
    return deltas


def age_staff_one_year(staff, employed: bool = True,
                       assignment: str = "nhl") -> bool:
    """Age one staffer a year: +1 age, +1 experience if employed, attribute
    development. Returns True if the staffer retires this rollover."""
    try:
        staff.age = int(getattr(staff, "age", 40) or 40) + 1
        if employed:
            staff.experience = int(getattr(staff, "experience", 0) or 0) + 1
    except Exception:
        pass
    develop_staff_member(staff, employed=employed, assignment=assignment)
    # Retirement: the carousel keeps turning. Non-icons start considering
    # it at 66 with rising odds; icons coach deep into their 70s.
    try:
        age = int(getattr(staff, "age", 66) or 66)
        icon = staff_is_icon(staff)
        if icon:
            if age >= 72:
                return random.random() < min(0.75, (age - 71) * 0.10)
        else:
            if age >= 66:
                return random.random() < min(0.75, (age - 65) * 0.10)
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Staff breakthroughs: results-driven development (Sept 2026)
#
# Age/experience moves every coach along a predictable curve (see the aging
# section above), but careers are also made by RESULTS: winning hockey
# games and turning players into success stories. Each season rollover,
# every employed coach gets a season score from (a) team results -- win%,
# playoff rounds, Cups, Jack Adams nods -- and (b) player-development
# success stories on his roster, in varying degrees: a +2 improvement
# counts, a +7 breakout counts more, and pushing a goalie over the
# NHL-ready line counts extra for the goalie coach. The score becomes a
# CHANCE (never a guarantee) at a breakthrough leap, weighted by the
# coach's career stock -- momentum that rises with great seasons and
# decays with failure, unemployment, new situations, and the age curve.
# An AHL goalie coach who twice makes his goalies NHL-ready can genuinely
# become an elite NHL-tier goalie coach; a Cup-winning 66-year-old can
# hold off the age curve for one more run.
# ---------------------------------------------------------------------------

def _staff_spotlight_attrs(role):
    """The attributes a breakthrough moves for each coaching role."""
    if role == StaffRole.GOALIE_COACH:
        return ("coaching_goalies", "technical_coaching",
                "player_development", "working_with_youngsters",
                "mental_coaching")
    if role == StaffRole.HEAD_COACH:
        return ("tactical_knowledge", "leadership", "man_management",
                "motivating", "game_preparation", "match_preparation")
    if role in (StaffRole.ASSOCIATE_COACH, StaffRole.ASSISTANT_COACH,
                StaffRole.POWER_PLAY_COACH, StaffRole.PENALTY_KILL_COACH,
                StaffRole.SKILLS_COACH, StaffRole.SKATING_COACH):
        return ("coaching_forwards", "coaching_defensemen",
                "tactical_knowledge", "working_with_youngsters",
                "player_development")
    return ("man_management", "motivating", "leadership",
            "tactical_knowledge", "determination", "adaptability")


def _staff_season_score(staff, team_name, stories, results):
    """Season score: development stories (varying degrees) + team results."""
    score = 0.0
    try:
        role = getattr(staff, "role", None)
        st = (stories or {}).get(team_name) or {}
        _seg = "ahl" if (getattr(staff, "assignment", "nhl")
                         or "nhl") == "ahl" else "nhl"
        seg = st.get(_seg) or {}
        tw = float(seg.get("weight", 0.0) or 0.0)
        gw = float(seg.get("goalie_weight", 0.0) or 0.0)
        if role == StaffRole.GOALIE_COACH:
            score += gw * 1.5 + max(0.0, tw - gw) * 0.25
        elif role == StaffRole.HEAD_COACH:
            score += tw * 0.5
        elif role in (StaffRole.ASSOCIATE_COACH, StaffRole.ASSISTANT_COACH):
            score += tw * 0.75
        else:
            score += tw * 0.25
        r = (results or {}).get(team_name) or {}
        if r:
            if role == StaffRole.HEAD_COACH:
                wpct = float(r.get("win_pct", 0.5) or 0.5)
                if wpct >= 0.600:
                    score += 2.0
                elif wpct >= 0.550:
                    score += 1.0
                elif wpct < 0.400:
                    score -= 2.0
                playoff = str(r.get("playoff", "") or "")
                if "Won Stanley Cup" in playoff:
                    score += 3.0
                elif "Lost Stanley Cup Final" in playoff:
                    score += 2.0
                elif playoff.startswith("Lost"):
                    score += 1.0
            if (r.get("adams_id") is not None
                    and r.get("adams_id") == getattr(staff, "id", None)):
                score += 3.0
    except Exception:
        pass
    return score


def roll_staff_breakthrough(staff, team_name, stories=None, results=None):
    """One coach's end-of-season fortune roll.

    Returns (broke_through: bool, score: float, chance: float). A
    breakthrough lifts the role's spotlight attributes and reputation and
    banks stock; a quiet year still moves stock with the season's shape.
    """
    try:
        import coach_records as _cr
        if not _cr.is_coaching_role(staff):
            return False, 0.0, 0.0
    except Exception:
        pass
    score = _staff_season_score(staff, team_name, stories, results)
    stock = int(getattr(staff, "stock", 0) or 0)
    chance = 0.02 + 0.07 * max(score, 0.0) + stock / 600.0
    chance = max(0.02, min(0.70, chance))
    if random.random() < chance:
        # A breakthrough is a focused leap: 2-3 areas step up, not the
        # whole card. Past 95 every leap is worth exactly one point, and
        # 97 is the developed ceiling -- 98+ is born, not made.
        spot = _staff_spotlight_attrs(getattr(staff, "role", None))
        leap_attrs = random.sample(spot, min(3, len(spot)))
        for attr in leap_attrs:
            try:
                cur = int(getattr(staff, attr, 65) or 65)
                if cur >= 97:
                    continue
                bhr = max(0.05, min(1.0, (97 - cur) / 40.0))
                inc = max(1, int(round(random.randint(1, 2) * bhr)))
                setattr(staff, attr, min(97, cur + inc))
            except Exception:
                pass
        try:
            rep = int(getattr(staff, "reputation", 50) or 50)
            staff.reputation = min(99, rep + random.randint(1, 4))
        except Exception:
            pass
        staff.stock = max(-100, min(100, stock + 14))
        staff.career_breakthroughs = \
            int(getattr(staff, "career_breakthroughs", 0) or 0) + 1
        return True, score, chance
    # No leap: the season's shape still moves the stock.
    if score >= 3.0:
        stock += 5
    elif score <= -2.0:
        stock -= 10
    staff.stock = max(-100, min(100, stock))
    return False, score, chance


# Scout-voiced coach breakthrough stories: the player riser stories in
# draft_stories.py speak through scouts ("scouts say his second half
# forced its way into every first-round conversation"), so coaching
# breakthroughs get the same treatment -- a scout quote plus the actual
# evidence (the development story, the results), not a mechanical
# rep/stock readout.
_SCOUT_COACH_QUOTES = {
    "goalie": [
        "His goalies come out NHL-ready -- that's the hardest thing to teach.",
        "Technique, tracking, composure -- his guys have all three.",
    ],
    "head": [
        "He squeezes more out of a roster than anyone in the league.",
        "Players run through walls for him, and the details never slip.",
    ],
    "assistant": [
        "The details guy -- players swear by him.",
        "Ask around the room: he's the coach they all credit.",
    ],
    "default": [
        "Everybody in the business knows the name now.",
        "He's the next big thing behind a bench -- it's just a matter of when.",
    ],
}


def _coach_breakthrough_story(staff, team_name, stories=None, results=None):
    """Scout-voiced breakthrough copy for one coach. Returns the story
    string, or "" if there is nothing to say."""
    try:
        nm = (f"{getattr(staff, 'first_name', '')} "
              f"{getattr(staff, 'last_name', '')}").strip() or "A coach"
        role = getattr(getattr(staff, "role", None), "value", "coach")
        role_l = str(role).lower()
        if "goalie" in role_l:
            quotes = _SCOUT_COACH_QUOTES["goalie"]
        elif "head coach" in role_l:
            quotes = _SCOUT_COACH_QUOTES["head"]
        elif "coach" in role_l:
            quotes = _SCOUT_COACH_QUOTES["assistant"]
        else:
            quotes = _SCOUT_COACH_QUOTES["default"]
        quote = random.choice(quotes)

        seg = "ahl" if (getattr(staff, "assignment", "nhl") or "nhl") == "ahl" \
            else "nhl"
        st = (stories or {}).get(team_name) or {}
        head = (st.get(seg) or {}).get("headline")
        evidence = []
        if head:
            try:
                _pn, _d, _b, _g = head
                evidence.append(
                    f"took {_pn} from {_b} to {_b + _d} overall")
            except Exception:
                pass
        r = (results or {}).get(team_name) or {}
        if r:
            if r.get("champ"):
                evidence.append("a Stanley Cup")
            elif "Lost Stanley Cup Final" in str(r.get("playoff", "")):
                evidence.append("a run to the Final")
            if (r.get("adams_id") is not None
                    and r.get("adams_id") == getattr(staff, "id", None)):
                evidence.append("the Jack Adams")
            try:
                _wp = float(r.get("win_pct", 0) or 0)
                if _wp >= 0.600 and not r.get("champ"):
                    evidence.append(
                        f"a {r.get('w', 0)}-{r.get('l', 0)}-"
                        f"{r.get('otl', 0)} season")
            except Exception:
                pass
        ev = (" after " + "; ".join(evidence)) if evidence else ""
        return (f'\U0001f4f0 "{quote}" Scouts are buzzing about {nm}, '
                f"the {team_name} {role}{ev}.")
    except Exception:
        return ""


def roll_staff_breakthroughs(league):
    """Season-rollover breakthrough pass over every club's coaching staff.

    Reads the development stories computed earlier in this rollover
    (league._staff_stories) and the team results stashed pre-rollover by
    the UI flow (league._staff_results_cache, when present). Situation
    dynamics: a new room means proving it again (stock fades), the age
    curve closes the window for old non-icons, and unemployment fades the
    glow. Notable leaps are collected on league.staff_breakthrough_news.
    """
    stories = getattr(league, "_staff_stories", None) or {}
    results = getattr(league, "_staff_results_cache", None) or {}
    news = []
    try:
        for team in getattr(league, "teams", []) or []:
            tname = getattr(team, "team_name", "")
            for s in list(getattr(team, "staff", []) or []):
                try:
                    broke, score, _chance = roll_staff_breakthrough(
                        s, tname, stories, results)
                except Exception:
                    continue
                # Situation dynamics: a new room means proving it again;
                # the age curve closes the window for old non-icons.
                try:
                    st = int(getattr(s, "stock", 0) or 0)
                    if (getattr(s, "years_with_team", 99) or 99) <= 1:
                        st = int(st * 0.8)
                    if (int(getattr(s, "age", 40) or 40) >= 60
                            and not staff_is_icon(s)):
                        st = int(st * 0.9)
                    s.stock = max(-100, min(100, st))
                except Exception:
                    pass
                if broke and (score >= 5.0
                              or int(getattr(s, "reputation", 0) or 0) >= 75):
                    _story = _coach_breakthrough_story(s, tname, stories,
                                                       results)
                    if _story:
                        news.append(_story)
        # Unemployment fades the glow: out of the game, out of mind.
        for s in list(getattr(league, "free_agent_staff", None) or []):
            try:
                s.stock = int(int(getattr(s, "stock", 0) or 0) * 0.7)
            except Exception:
                pass
    except Exception:
        pass
    if news:
        box = getattr(league, "staff_breakthrough_news", None)
        if not isinstance(box, list):
            box = []
            league.staff_breakthrough_news = box
        box.extend(news)
    # One-shot: the results cache was stashed pre-rollover by the UI flow.
    try:
        if hasattr(league, "_staff_results_cache"):
            delattr(league, "_staff_results_cache")
    except Exception:
        pass
    return news


@dataclass
class Staff:
    """Represents a non-player staff member with detailed EHM-style attributes."""
    first_name: str
    last_name: str
    role: StaffRole
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    age: int = field(default_factory=lambda: random.randint(25, 65))
    nationality: str = field(default_factory=lambda: random.choice(['USA', 'Canada', 'Russia', 'Sweden', 'Finland', 'Czech Republic']))
    
    # Core Coaching Attributes (1-20 scale)
    coaching_forwards: int = field(default_factory=lambda: _staff_attr_100())
    coaching_defensemen: int = field(default_factory=lambda: _staff_attr_100())
    coaching_goalies: int = field(default_factory=lambda: _staff_attr_100())
    
    # Tactical Knowledge
    tactical_knowledge: int = field(default_factory=lambda: _staff_attr_100())
    game_preparation: int = field(default_factory=lambda: _staff_attr_100())
    match_preparation: int = field(default_factory=lambda: _staff_attr_100())
    
    # Player Development
    working_with_youngsters: int = field(default_factory=lambda: _staff_attr_100())
    player_development: int = field(default_factory=lambda: _staff_attr_100())
    
    # Management Skills
    man_management: int = field(default_factory=lambda: _staff_attr_100())
    motivating: int = field(default_factory=lambda: _staff_attr_100())
    discipline: int = field(default_factory=lambda: _staff_attr_100())
    leadership: int = field(default_factory=lambda: _staff_attr_100())
    
    # Scouting Abilities
    judging_player_ability: int = field(default_factory=lambda: _staff_attr_100())
    judging_player_potential: int = field(default_factory=lambda: _staff_attr_100())
    
    # Communication & Relationships
    media_handling: int = field(default_factory=lambda: _staff_attr_100())
    determination: int = field(default_factory=lambda: _staff_attr_100())
    adaptability: int = field(default_factory=lambda: _staff_attr_100())
    
    # Specialized Skills (position-dependent)
    level_of_discipline: int = field(default_factory=lambda: _staff_attr_100())
    attacking_coaching: int = field(default_factory=lambda: _staff_attr_100())
    defensive_coaching: int = field(default_factory=lambda: _staff_attr_100())
    mental_coaching: int = field(default_factory=lambda: _staff_attr_100())
    technical_coaching: int = field(default_factory=lambda: _staff_attr_100())

    # Morale (1-100 scale, display-only; the sim engine does not read staff morale)
    morale: int = field(default_factory=lambda: max(10, min(99, int(random.gauss(60, 15)))))
    
    # Contract Information
    salary: int = field(default_factory=lambda: random.randint(75000, 500000))
    contract_years: int = field(default_factory=lambda: random.randint(1, 5))
    
    # Performance Tracking (reputation on the 1-100 scale)
    reputation: int = field(default_factory=lambda: max(10, min(95, int(random.gauss(50, 15)))))
    experience: int = field(default_factory=lambda: random.randint(1, 30))  # Years of experience
    years_with_team: int = field(default_factory=lambda: random.randint(0, 4))  # Tenure with current team (room-status shelf life)
    gm_trust: int = 70  # 0-100 GM-coach trust; evolves as advice is taken/ignored
    ambition: str = "climb"  # stanley_cup | climb | developer | hometown | lifer
    favorite_team: str = ""  # Boyhood team (Suzuki wants the Habs)
    icon_team: str = ""  # Franchise where he is a legend as a PLAYER (""/team).
    # The Coffey effect: hiring YOUR icon behind the bench moves the room.
    icon_level: str = ""  # "" | "star" | "icon" (stamped at retirement)
    # Where he coaches: "nhl" (club's NHL staff), "ahl" (club's AHL staff),
    # "overseas" (European club). Free agents live in league pools; the flag
    # is only meaningful for staff employed by a team.
    assignment: str = "nhl"
    current_club: str = ""  # e.g. "Frölunda HC (SHL)" for overseas coaches
    assistant_effect: Optional[float] = None  # current effectiveness 0-100;
    # None seeds from prowess on first tick, then drifts with results/mesh
    control_need: int = 50  # 0-100: Babcock 95 (authoritarian) ... Cooper 25 (collaborative)
    first_nhl_chair: bool = False  # Rookie NHL head coach promoted from AHL: defers to the GM who believed in him
    # Reputation system (0-100 career standing; visible attitude/volatility 0-100)
    career_reputation: int = 0
    controversy: int = 0
    reputation_history: list = field(default_factory=list)
    controversy_history: list = field(default_factory=list)
    connections: list = field(default_factory=list)  # allies who vouch for him: team names where his guys are
    # Year-by-year coaching record (head coaches AND assistants): list of
    # plain dicts {"season", "team", "role", "w", "l", "otl", "playoff",
    # "jack_adams"}. Recorded at season rollover by coach_records.
    # Shown on the staff card "Record" tab; informs hiring/firing.
    # Old-save safe: read via getattr(staff, 'career_record', []).
    career_record: list = field(default_factory=list)
    # Trophy case for coaches: plain dicts {"award": key, "year": label} --
    # "stanley_cup" and "jack_adams". Same bank_accolade/idempotent rules as
    # players (accolades.py). Old-save safe: getattr(staff, 'career_accolades', []).
    career_accolades: list = field(default_factory=list)
    # Pro-scout track record (analytics wave 1: trust from evidence, not
    # hidden JPA). tip_record: {"calls": n, "hits": n}; tip_history: last
    # 12 graded calls [{"player", "kind" ("buy"/"sell"), "result"
    # ("hit"/"miss"), "date"}]. Graded by analytics_scouting.grade_tip_ledger
    # and the steal/sell watches -- never set by hand.
    tip_record: dict = field(default_factory=lambda: {"calls": 0, "hits": 0})
    tip_history: list = field(default_factory=list)

    # Coaching momentum (-100..100): rises with breakthrough seasons and
    # great results, decays with failure, unemployment, new situations,
    # and the age curve. Feeds the breakthrough chance each rollover --
    # careers have trajectories, not just attributes.
    stock: int = 0
    # Career leap count: how many breakthrough seasons this coach has had.
    # The story of a riser, shown on the staff card.
    career_breakthroughs: int = 0

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def overall_rating(self) -> int:
        """Calculate overall rating based on role-specific attributes"""
        if self.role in [StaffRole.HEAD_COACH, StaffRole.ASSISTANT_COACH, StaffRole.ASSOCIATE_COACH]:
            return int((
                self.tactical_knowledge * 0.25 +
                self.man_management * 0.20 +
                self.motivating * 0.15 +
                self.coaching_forwards * 0.15 +
                self.coaching_defensemen * 0.15 +
                self.discipline * 0.10
            ))
        elif self.role == StaffRole.GOALIE_COACH:
            return int((
                self.coaching_goalies * 0.40 +
                self.technical_coaching * 0.25 +
                self.working_with_youngsters * 0.20 +
                self.man_management * 0.15
            ))
        elif 'SCOUT' in self.role.value.upper():
            return int((
                self.judging_player_ability * 0.35 +
                self.judging_player_potential * 0.35 +
                self.determination * 0.15 +
                self.adaptability * 0.15
            ))
        elif self.role == StaffRole.ANALYTICS_DIRECTOR:
            # Same mean as analytics_scouting.analytics_director_quality
            # so the card rating and the department quality agree.
            return int(round((self.judging_player_ability +
                              self.tactical_knowledge +
                              self.adaptability) / 3.0))
        elif self.role == StaffRole.GENERAL_MANAGER:
            return int((
                self.judging_player_ability * 0.20 +
                self.judging_player_potential * 0.20 +
                self.man_management * 0.20 +
                self.tactical_knowledge * 0.15 +
                self.media_handling * 0.15 +
                self.determination * 0.10
            ))
        else:
            # General staff rating
            return int((
                self.determination * 0.30 +
                self.adaptability * 0.25 +
                self.man_management * 0.25 +
                self.discipline * 0.20
            ))
    
    def get_attributes_for_role(self) -> dict:
        """Role-relevant attributes for profile cards and comparisons.

        The coaching set mirrors what the practice engine prices
        (coach_practice): drill teaching quality, positional coaching,
        development touch, management, and tactical/system knowledge --
        so the card shows the numbers that actually move development.
        """
        coaching = {
            'attacking_coaching': self.attacking_coaching,
            'defensive_coaching': self.defensive_coaching,
            'technical_coaching': self.technical_coaching,
            'mental_coaching': self.mental_coaching,
            'coaching_forwards': self.coaching_forwards,
            'coaching_defensemen': self.coaching_defensemen,
            'coaching_goalies': self.coaching_goalies,
            'player_development': self.player_development,
            'working_with_youngsters': self.working_with_youngsters,
            'tactical_knowledge': self.tactical_knowledge,
            'man_management': self.man_management,
            'motivating': self.motivating,
            'discipline': self.discipline,
            'leadership': self.leadership,
            'adaptability': self.adaptability,
        }
        if self.role == StaffRole.GOALIE_COACH:
            order = ['coaching_goalies', 'technical_coaching',
                     'working_with_youngsters', 'man_management',
                     'motivating', 'mental_coaching', 'adaptability',
                     'discipline']
            return {k: coaching[k] for k in order}
        if self.role in (StaffRole.HEAD_COACH, StaffRole.ASSISTANT_COACH,
                         StaffRole.ASSOCIATE_COACH, StaffRole.POWER_PLAY_COACH,
                         StaffRole.PENALTY_KILL_COACH, StaffRole.SKILLS_COACH,
                         StaffRole.CONDITIONING_COACH,
                         StaffRole.SKATING_COACH):
            return coaching
        if 'SCOUT' in self.role.value.upper():
            return {
                'judging_player_ability': self.judging_player_ability,
                'judging_player_potential': self.judging_player_potential,
                'determination': self.determination,
                'adaptability': self.adaptability,
            }
        return {
            'leadership': self.leadership,
            'man_management': self.man_management,
            'tactical_knowledge': self.tactical_knowledge,
            'judging_player_ability': self.judging_player_ability,
            'determination': self.determination,
            'adaptability': self.adaptability,
            'media_handling': self.media_handling,
        }

    def get_role_description(self) -> str:
        """Get a description of what this staff member does"""
        descriptions = {
            StaffRole.GENERAL_MANAGER: "Oversees all hockey operations, trades, signings, and strategic planning.",
            StaffRole.HEAD_COACH: "Leads the team, makes strategic decisions, and manages game tactics.",
            StaffRole.ASSISTANT_COACH: "Supports the head coach with tactical planning and player development.",
            StaffRole.GOALIE_COACH: "Specializes in goaltender training and development.",
            StaffRole.HEAD_SCOUT: "Leads scouting operations and evaluates talent across all levels.",
            StaffRole.PROFESSIONAL_SCOUT: "Scouts professional leagues for trade targets and free agents.",
            StaffRole.AMATEUR_SCOUT: "Evaluates amateur players for the NHL draft.",
            StaffRole.EUROPEAN_SCOUT: "Focuses on European leagues and international talent.",
            StaffRole.ANALYTICS_DIRECTOR: "Runs the analytics department: sharper models, fresher numbers, tighter confidence intervals in everything you see.",
            StaffRole.SKILLS_COACH: "Develops individual player skills and techniques.",
            StaffRole.CONDITIONING_COACH: "Manages player fitness and physical conditioning.",
        }
        return descriptions.get(self.role, "Provides specialized support to the organization.")
    
    def negotiate_contract(self, salary, years):
        """Determine if staff member will accept contract offer"""
        reputation_modifier = self.reputation / 10
        min_salary = int(self.salary * (0.8 + reputation_modifier * 0.1))
        max_salary = int(self.salary * (1.2 + reputation_modifier * 0.2))
        
        if min_salary <= salary <= max_salary and 1 <= years <= 5:
            # Higher reputation staff are pickier
            acceptance_chance = 0.8 - (self.reputation - 10) * 0.02
            return random.random() < acceptance_chance
        return False
    
    @staticmethod
    def is_unique_role(role: StaffRole) -> bool:
        """Check if a role should be unique per team (only one allowed)"""
        unique_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH
        ]
        return role in unique_roles
    
    @staticmethod
    def is_essential_role(role: StaffRole) -> bool:
        """Check if a role is essential for team operation"""
        essential_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH,
            StaffRole.ASSISTANT_GENERAL_MANAGER,
            StaffRole.HEAD_SCOUT
        ]
        return role in essential_roles
    
    @staticmethod
    def get_role_department(role: StaffRole) -> str:
        """Get the department/category for a staff role"""
        departments = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',
            
            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',
            
            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',
            
            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',
            
            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',
            StaffRole.EQUIPMENT_MANAGER: 'Medical',
            
            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics'
        }
        return departments.get(role, 'Other')

@dataclass
class ScoutingReport:
    """Enhanced EHM-style scouting report with detailed analysis and reliability tracking."""
    player: Player
    scout: Staff
    scouted_attributes: Dict[str, str] = field(default_factory=dict)
    scouted_potential: Optional[str] = None
    viewings: int = 0
    accuracy: str = 'F'  # Letter grade A-F for report accuracy
    last_viewed: Optional[datetime] = None
    reliability: float = 0.0  # 0.0 to 1.0 scale
    notes: str = ""
    
    # Enhanced scouting features
    region_coverage: str = "Unknown"  # Which region this player was scouted in
    competition_level: str = "Unknown"  # Level of competition observed
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    comparable_players: List[str] = field(default_factory=list)
    injury_history_known: bool = False
    personality_assessment: str = ""
    coachability_rating: int = 0  # 1-20 scale
    interview_conducted: bool = False
    
    # Projection data
    projected_draft_position: Optional[int] = None
    projected_nhl_arrival: Optional[str] = None  # "1-2 years", "3-4 years", etc.
    ceiling_rating: int = 0  # Potential ceiling (1-20)
    floor_rating: int = 0   # Likely floor (1-20)
    
    def calculate_reliability(self) -> float:
        """Calculate how reliable this scouting report is (0.0 to 1.0)"""
        base_reliability = {
            'A': 0.95,
            'B': 0.80,
            'C': 0.65, 
            'D': 0.45,
            'F': 0.25
        }.get(self.accuracy, 0.25)
        
        # Scout skill factor
        scout_skill = (self.scout.judging_player_ability + self.scout.judging_player_potential) / 40.0
        
        # Experience bonus
        exp_bonus = min(0.1, self.scout.experience * 0.003)
        
        # Interview bonus
        interview_bonus = 0.05 if self.interview_conducted else 0.0
        
        return min(1.0, base_reliability * scout_skill + exp_bonus + interview_bonus)

    def update_report(self, player: Player, scout: Staff):
        """Updates the report with enhanced EHM-style scouting mechanics."""
        self.viewings += 1
        self.last_viewed = datetime.now()
        
        # Determine competition level
        if player.age < 20:
            competition_levels = ["Junior A", "Junior B", "College", "International Junior"]
            self.competition_level = random.choice(competition_levels)
        else:
            competition_levels = ["AHL", "ECHL", "European Pro", "KHL", "International"]
            self.competition_level = random.choice(competition_levels)
        
        # Region assignment based on scout specialization
        if self.scout.role == StaffRole.EUROPEAN_SCOUT:
            self.region_coverage = random.choice(["Sweden", "Finland", "Russia", "Czech Republic", "Germany", "Switzerland"])
        elif self.scout.role == StaffRole.AMATEUR_SCOUT:
            self.region_coverage = random.choice(["Western Canada", "Eastern Canada", "USA West", "USA East", "USA Central"])
        else:
            self.region_coverage = random.choice(["North America", "Europe", "International"])
        
        # Calculate accuracy based on viewings, scout skill, and role match
        base_viewings = self.viewings
        
        # Scout skill bonus viewings
        skill_bonus = (self.scout.judging_player_ability + self.scout.judging_player_potential) // 10
        effective_viewings = base_viewings + skill_bonus
        
        # Determine accuracy grade
        if effective_viewings >= 20: 
            self.accuracy = 'A'
        elif effective_viewings >= 15: 
            self.accuracy = 'B'
        elif effective_viewings >= 10: 
            self.accuracy = 'C'
        elif effective_viewings >= 5: 
            self.accuracy = 'D'
        else: 
            self.accuracy = 'F'
        
        # Update reliability
        self.reliability = self.calculate_reliability()
        
        # Scout attributes with position-specific focus
        self._scout_attributes(player, scout)
        
        # Scout potential with advanced projections
        self._scout_potential_and_projections(player, scout)
        
        # Generate comprehensive notes
        self._generate_advanced_notes(player, scout)
        
        # Conduct interview if scout is good enough and enough viewings
        if self.viewings >= 3 and scout.man_management > 12 and random.random() < 0.3:
            self._conduct_player_interview(player)

    def _scout_attributes(self, player: Player, scout: Staff):
        """Scout player attributes with position-specific accuracy."""
        # Determine key attributes by position
        if player.primary_position == PlayerPosition.GOALIE:
            primary_attrs = ['goaltending', 'reflexes', 'positioning', 'rebound_control']
            secondary_attrs = ['puck_handling', 'determination', 'discipline', 'composure']
        elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            primary_attrs = ['defensive_awareness', 'checking', 'passing', 'shot_blocking', 'skating']
            secondary_attrs = ['shooting', 'strength', 'vision', 'teamwork', 'discipline']
        else:  # Forwards
            primary_attrs = ['shooting', 'passing', 'offensive_awareness', 'deking', 'skating']
            secondary_attrs = ['defensive_awareness', 'checking', 'faceoffs', 'determination', 'composure']
        
        all_attrs = primary_attrs + secondary_attrs
        
        # Scout accuracy modifiers
        accuracy_variance = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'F': 4}[self.accuracy]
        primary_accuracy = max(0, accuracy_variance - 1)  # Primary attributes more accurate
        
        for attr in all_attrs:
            if not hasattr(player, attr):
                continue
                
            true_value = getattr(player, attr)
            is_primary = attr in primary_attrs
            variance = primary_accuracy if is_primary else accuracy_variance
            
            # Generate scouted value
            if self.accuracy == 'A' and is_primary and random.random() < 0.9:
                # A-grade scouts get exact values on key attributes
                self.scouted_attributes[attr] = str(true_value)
            elif variance == 0:
                self.scouted_attributes[attr] = str(true_value)
            else:
                # Create ranges based on accuracy
                lower = max(1, true_value - random.randint(0, variance))
                upper = min(20, true_value + random.randint(0, variance))
                
                if lower == upper:
                    self.scouted_attributes[attr] = str(lower)
                else:
                    self.scouted_attributes[attr] = f"{lower}-{upper}"

    def _scout_potential_and_projections(self, player: Player, scout: Staff):
        """Scout potential with advanced projection system."""
        # Potential scouting accuracy based on JPP
        jpp = scout.judging_player_potential
        
        potential_grades = ["F", "D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
        # Scouts see through to the TRUE grade (hidden gem mechanic): a great
        # scout's report centers on what the kid really is, not the label.
        _true_g = (getattr(player, "true_potential_grade", "") or
                   getattr(player, "potential_grade", "C") or "C").strip().upper()
        if _true_g not in potential_grades:
            _true_g = {"D+": "D"}.get(_true_g, _true_g[:1])
        true_index = potential_grades.index(_true_g) if _true_g in potential_grades else 5
        
        # Variance decreases with higher JPP
        variance = max(1, 4 - (jpp // 5))
        scouted_index = max(0, min(len(potential_grades)-1, true_index + random.randint(-variance, variance)))
        self.scouted_potential = potential_grades[scouted_index]

        # The org learns: a good report nudges the displayed grade toward the
        # truth. This is what makes assigning your best scout to a late-round
        # kid rewarding -- he finds the Zetterberg before the box scores do.
        try:
            if getattr(player, "age", 99) < 25:
                import prospect_development as _pd
                _pd.scout_reveal_step(player, scout_jpp=jpp)
        except Exception:
            pass
        
        # Project ceiling and floor
        base_overall = player.overall_rating() if hasattr(player, 'overall_rating') else 50
        
        # Ceiling projection (optimistic)
        ceiling_modifier = random.randint(5, 15) if player.age < 23 else random.randint(0, 8)
        self.ceiling_rating = min(20, (base_overall + ceiling_modifier) // 5)
        
        # Floor projection (conservative)
        floor_modifier = random.randint(-5, 5) if player.age < 25 else random.randint(-2, 2)
        self.floor_rating = max(5, (base_overall + floor_modifier) // 5)
        
        # NHL arrival projection
        if player.age >= 23:
            self.projected_nhl_arrival = "Ready now"
        elif player.age >= 21:
            self.projected_nhl_arrival = "1-2 years"
        elif player.age >= 19:
            self.projected_nhl_arrival = "2-3 years"
        else:
            self.projected_nhl_arrival = "3-5 years"
        
        # Draft position projection for young players
        if player.age <= 18:
            potential_to_draft = {
                "A+": (1, 5), "A": (3, 12), "A-": (8, 25),
                "B+": (15, 45), "B": (25, 75), "B-": (40, 120),
                "C+": (60, 150), "C": (100, 210), "C-": (150, 210),
                "D": (180, 210), "F": (200, 210)
            }
            
            if self.scouted_potential in potential_to_draft:
                min_pick, max_pick = potential_to_draft[self.scouted_potential]
                # Add scout uncertainty
                uncertainty = 20 if self.accuracy in ['D', 'F'] else 10
                min_pick = max(1, min_pick - uncertainty)
                max_pick = min(210, max_pick + uncertainty)
                self.projected_draft_position = random.randint(min_pick, max_pick)

    def _generate_advanced_notes(self, player: Player, scout: Staff):
        """Generate comprehensive scouting notes with detailed analysis."""
        notes = []
        
        # Potential assessment
        potential_descriptions = {
            "A+": "Generational talent with franchise-altering potential. Could become one of the greatest players in the league.",
            "A": "Elite talent with superstar potential. Projects as a franchise cornerstone for years to come.",
            "A-": "Excellent potential with top-line/top-pairing upside. Should develop into an impact player.",
            "B+": "Very good potential with solid first-line/first-pairing ceiling. Projects as a core player.",
            "B": "Good potential with middle-six/top-four upside. Should become a reliable NHL regular.",
            "B-": "Above average potential. Projects as a useful middle-six/second-pairing contributor.",
            "C+": "Average potential with bottom-six/third-pairing ceiling. Could carve out an NHL role.",
            "C": "Limited upside but should develop into a depth player at the NHL level.",
            "C-": "Below average potential. May struggle to establish himself as an NHL regular.",
            "D": "Low ceiling. Likely career minor leaguer with limited NHL opportunities.",
            "F": "Very limited potential. Unlikely to reach professional hockey."
        }
        
        notes.append(potential_descriptions.get(self.scouted_potential, "Potential assessment ongoing."))
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        for attr, value_str in self.scouted_attributes.items():
            avg_value = self.get_attribute_value(attr)
            
            if avg_value >= 16:
                strengths.append(attr)
            elif avg_value <= 8:
                weaknesses.append(attr)
        
        # Add descriptive strengths
        if 'skating' in strengths:
            notes.append("Elite skating ability with exceptional speed and agility.")
        elif 'shooting' in strengths:
            notes.append("Possesses a lethal shot with accuracy and power.")
        elif 'passing' in strengths:
            notes.append("Excellent vision and playmaking ability.")
        elif 'defensive_awareness' in strengths:
            notes.append("Outstanding defensive instincts and positioning.")
        
        # Add comparable players for high-potential prospects
        if self.scouted_potential in ['A+', 'A', 'A-'] and self.accuracy in ['A', 'B']:
            comparables = [
                "Reminds me of a young Connor McDavid in terms of hockey IQ",
                "Similar playing style to Nathan MacKinnon",
                "Comparable to Erik Karlsson in terms of offensive awareness",
                "Has shades of Sidney Crosby's competitiveness",
                "Playing style reminiscent of Auston Matthews",
                "Comparable to Cale Makar's skating ability"
            ]
            self.comparable_players = [random.choice(comparables)]
            notes.append(self.comparable_players[0])
        
        # Competition level context
        notes.append(f"Scouted primarily in {self.competition_level} competition.")
        
        # Add projection timeline
        notes.append(f"Projected NHL readiness: {self.projected_nhl_arrival}.")
        
        if self.projected_draft_position:
            notes.append(f"Current draft projection: {self.projected_draft_position} overall.")
        
        self.notes = " ".join(notes)
        self.strengths = strengths
        self.weaknesses = weaknesses

    def _conduct_player_interview(self, player: Player):
        """Conduct a player interview to assess personality and coachability."""
        self.interview_conducted = True
        
        # Generate personality assessment
        personalities = [
            "Highly motivated and driven competitor",
            "Quiet leader who leads by example", 
            "Vocal presence with natural leadership qualities",
            "Team-first player with excellent character",
            "Intense competitor with strong work ethic",
            "Coachable player who accepts instruction well",
            "Independent thinker who needs proper motivation"
        ]
        
        self.personality_assessment = random.choice(personalities)
        
        # Coachability rating (influenced by actual player attributes if available)
        base_coachability = 10
        if hasattr(player, 'determination'):
            base_coachability += (player.determination - 10) // 2
        if hasattr(player, 'discipline'):
            base_coachability += (player.discipline - 10) // 2
        
        self.coachability_rating = max(1, min(20, base_coachability + random.randint(-3, 3)))

    def get_attribute_value(self, attr_name: str) -> int:
        """Extract numeric value from scouted attribute (handles ranges)."""
        if attr_name not in self.scouted_attributes:
            return 10
            
        attr_val = self.scouted_attributes[attr_name]
        
        if '-' in attr_val:
            lower, upper = map(int, attr_val.split('-'))
            return (lower + upper) // 2
        else:
            return int(attr_val)

    def get_confidence_level(self) -> str:
        """Return a description of scout confidence in this report."""
        confidence_map = {
            'A': "Very High Confidence",
            'B': "High Confidence", 
            'C': "Moderate Confidence",
            'D': "Low Confidence",
            'F': "Very Low Confidence"
        }
        return confidence_map.get(self.accuracy, "Unknown")
    
    def is_recommendation_positive(self) -> bool:
        """Determine if scout recommends this player."""
        if self.scouted_potential in ['A+', 'A', 'A-', 'B+']:
            return True
        elif self.scouted_potential in ['B', 'B-'] and self.accuracy in ['A', 'B']:
            return True
        return False

# --- Email and Inbox System (EHM-style) ---
@dataclass
class EmailMessage:
    """Represents an email message in the inbox system, similar to EHM."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    sender_type: str = "System"  # "System", "Agent", "Scout", "Media", "Owner", "Player", "Staff"
    subject: str = ""
    content: str = ""
    date_sent: date = field(default_factory=date.today)
    date_read: Optional[date] = None
    is_read: bool = False
    is_important: bool = False
    is_urgent: bool = False
    category: str = "General"  # "Trade", "Scouting", "Contracts", "Injuries", "Development", "Media", "League", "General"
    attachments: List[str] = field(default_factory=list)  # For potential future file attachments
    requires_response: bool = False
    response_deadline: Optional[date] = None
    priority: int = 1  # 1=Low, 2=Medium, 3=High, 4=Urgent

    # Headline / lore system: rare league news (brawls, trade requests, ...)
    # expires after news_ttl_days GAME-days unless the user saved it
    # (is_saved, "save for later") or it marks a major milestone for the
    # user's own team (is_milestone). game_date_sent anchors the TTL to the
    # game calendar instead of the wall clock.
    is_saved: bool = False
    is_milestone: bool = False
    news_ttl_days: Optional[int] = None
    game_date_sent: Optional[date] = None
    
    # Related game objects (for context)
    related_player_id: Optional[str] = None
    related_team: Optional[str] = None
    related_contract_id: Optional[str] = None

    # Interactive inbox actions (game-day bundle, press conferences, ...).
    # action_type: None | "game_day" | "postmatch_presser"
    # action_data: pickle-safe dict with the questions/options and answers.
    # action_done: True once the user completed the interactive part.
    action_type: Optional[str] = None
    action_data: dict = field(default_factory=dict)
    action_done: bool = False

    def mark_as_read(self):
        """Mark this email as read."""
        if not self.is_read:
            self.is_read = True
            self.date_read = date.today()
    
    def is_overdue(self) -> bool:
        """Check if this email's response is overdue."""
        if self.requires_response and self.response_deadline:
            return date.today() > self.response_deadline
        return False
    
    def get_age_days(self) -> int:
        """Get the age of this email in days."""
        return (date.today() - self.date_sent).days

    def to_dict(self) -> dict:
        """Pickle-free dict form for save files and multiplayer snapshots."""
        data = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, date):
                value = value.isoformat()
            data[name] = value
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Rebuild from to_dict(); tolerant of missing/extra keys (old saves)."""
        try:
            known = set(cls.__dataclass_fields__)
            clean = {k: v for k, v in dict(data).items() if k in known}
            for k in ("date_sent", "date_read", "response_deadline",
                      "game_date_sent"):
                v = clean.get(k)
                if isinstance(v, str):
                    try:
                        clean[k] = date.fromisoformat(v)
                    except ValueError:
                        clean[k] = None
            return cls(**clean)
        except Exception:
            return None

@dataclass 
class EmailInbox:
    """Manages the player's email inbox system, similar to EHM."""
    messages: List[EmailMessage] = field(default_factory=list)
    unread_count: int = 0
    total_messages: int = 0
    auto_delete_after_days: int = 365  # Auto-delete old emails after 1 year
    
    def add_message(self, message: EmailMessage):
        """Add a new message to the inbox."""
        self.messages.insert(0, message)  # Add to front for newest first
        if not message.is_read:
            self.unread_count += 1
        self.total_messages += 1
        self._cleanup_old_messages()
    
    def mark_message_read(self, message_id: str):
        """Mark a specific message as read."""
        for message in self.messages:
            if message.id == message_id and not message.is_read:
                message.mark_as_read()
                self.unread_count = max(0, self.unread_count - 1)
                break
    
    def mark_all_read(self):
        """Mark all messages as read."""
        for message in self.messages:
            if not message.is_read:
                message.mark_as_read()
        self.unread_count = 0
    
    def delete_message(self, message_id: str):
        """Delete a specific message."""
        for i, message in enumerate(self.messages):
            if message.id == message_id:
                if not message.is_read:
                    self.unread_count = max(0, self.unread_count - 1)
                del self.messages[i]
                break
    
    def get_messages_by_category(self, category: str) -> List[EmailMessage]:
        """Get all messages in a specific category."""
        return [msg for msg in self.messages if msg.category == category]
    
    def get_unread_messages(self) -> List[EmailMessage]:
        """Get all unread messages."""
        return [msg for msg in self.messages if not msg.is_read]

    def prune_expired(self, game_date) -> int:
        """Remove headline/news messages older than their TTL (game-days).

        Saved messages (is_saved) and milestones for the user's team
        (is_milestone) never expire. Only messages carrying news_ttl_days
        are touched -- everything else keeps the 365-day backstop. Runs
        once per day-advance; O(n) over the inbox.
        Returns the number of messages removed.
        """
        if game_date is None:
            return 0
        kept: List[EmailMessage] = []
        removed_unread = 0
        for msg in self.messages:
            ttl = getattr(msg, "news_ttl_days", None)
            sent = getattr(msg, "game_date_sent", None)
            if (ttl is not None and sent is not None
                    and not getattr(msg, "is_saved", False)
                    and not getattr(msg, "is_milestone", False)):
                try:
                    age = (game_date - sent).days
                except Exception:
                    age = 0
                if age > ttl:
                    if not msg.is_read:
                        removed_unread += 1
                    continue
            kept.append(msg)
        removed = len(self.messages) - len(kept)
        if removed:
            self.messages = kept
            self.unread_count = max(0, self.unread_count - removed_unread)
        return removed
    
    def get_urgent_messages(self) -> List[EmailMessage]:
        """Get all urgent messages."""
        return [msg for msg in self.messages if msg.is_urgent or msg.priority >= 4]
    
    def get_overdue_messages(self) -> List[EmailMessage]:
        """Get all messages that require a response and are overdue."""
        return [msg for msg in self.messages if msg.is_overdue()]
    
    def _cleanup_old_messages(self):
        """Remove messages older than the auto-delete threshold."""
        cutoff_date = date.today() - timedelta(days=self.auto_delete_after_days)
        initial_count = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.date_sent >= cutoff_date]
        deleted_count = initial_count - len(self.messages)
        if deleted_count > 0:
            print(f"Auto-deleted {deleted_count} old email messages")

class EmailGenerator:
    """Generates realistic emails for various game events, similar to EHM."""
    
    @staticmethod
    def create_trade_offer_email(offering_team: str, target_player: str, offered_players: List[str]) -> EmailMessage:
        """Create an email for a trade offer."""
        subject = f"Trade Offer from {offering_team}"
        content = f"Dear General Manager,\n\n"
        content += f"The {offering_team} have submitted a trade proposal:\n\n"
        content += f"They are requesting: {target_player}\n"
        content += f"They are offering: {', '.join(offered_players)}\n\n"
        content += f"Please review this proposal and respond at your earliest convenience.\n\n"
        content += f"Regards,\nLeague Office"
        
        return EmailMessage(
            sender=f"{offering_team} GM",
            sender_type="Agent",
            subject=subject,
            content=content,
            category="Trade",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=3),
            priority=3,
            related_team=offering_team
        )
    
    @staticmethod
    def create_injury_report_email(player_name: str, injury_type: str, expected_return: str) -> EmailMessage:
        """Create an email for a player injury."""
        subject = f"Injury Report: {player_name}"
        content = f"Medical Department Update\n\n"
        content += f"Player: {player_name}\n"
        content += f"Injury: {injury_type}\n"
        content += f"Expected Return: {expected_return}\n\n"
        content += f"We will continue to monitor {player_name}'s recovery and provide updates as necessary.\n\n"
        content += f"Dr. Smith\nTeam Physician"
        
        return EmailMessage(
            sender="Medical Staff",
            sender_type="Staff",
            subject=subject,
            content=content,
            category="Injuries",
            is_important=True,
            priority=3,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_scouting_report_email(scout_name: str, player_name: str, potential_grade: str) -> EmailMessage:
        """Create an email for a completed scouting report."""
        subject = f"Scouting Report: {player_name}"
        content = f"Scouting Department Report\n\n"
        content += f"Scout: {scout_name}\n"
        content += f"Player: {player_name}\n"
        content += f"Potential Grade: {potential_grade}\n\n"
        content += f"The complete scouting report is now available in the scouting system.\n\n"
        content += f"Best regards,\n{scout_name}\nScout"
        
        return EmailMessage(
            sender=scout_name,
            sender_type="Scout",
            subject=subject,
            content=content,
            category="Scouting",
            priority=2,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_contract_negotiation_email(player_name: str, agent_name: str, demand_type: str) -> EmailMessage:
        """Create an email for contract negotiations."""
        subject = f"Contract Negotiation: {player_name}"
        content = f"Dear General Manager,\n\n"
        content += f"I am writing on behalf of my client, {player_name}.\n\n"
        content += f"{demand_type}\n\n"
        content += f"Please contact me to discuss terms.\n\n"
        content += f"Best regards,\n{agent_name}\nPlayer Agent"
        
        return EmailMessage(
            sender=agent_name,
            sender_type="Agent",
            subject=subject,
            content=content,
            category="Contracts",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=7),
            priority=2,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_media_request_email(journalist_name: str, topic: str) -> EmailMessage:
        """Create an email for a media interview request."""
        subject = f"Interview Request: {topic}"
        content = f"Dear General Manager,\n\n"
        content += f"I am writing to request an interview regarding {topic}.\n\n"
        content += f"Would you be available for a brief discussion this week?\n\n"
        content += f"Best regards,\n{journalist_name}\nSports Journalist"
        
        return EmailMessage(
            sender=journalist_name,
            sender_type="Media",
            subject=subject,
            content=content,
            category="Media",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=2),
            priority=1
        )
    
    @staticmethod
    def create_league_announcement_email(subject: str, content: str) -> EmailMessage:
        """Create an email for league announcements."""
        return EmailMessage(
            sender="League Office",
            sender_type="System",
            subject=subject,
            content=content,
            category="League",
            is_important=True,
            priority=2
        )

# Anchor year for draft-pick future discounting (DraftPick.value). The app
# sets this from the league's live season so a 2029 pick in a 2029 save
# isn't discounted as if it were five drafts away; it defaults to the
# current calendar year. (Previously hardcoded to 2024, which silently
# deepened the discount every season a save ran.)
_PICK_VALUE_ANCHOR_YEAR = None


def set_pick_value_anchor_year(year):
    """Pin the future-pick discount anchor to the live season year."""
    global _PICK_VALUE_ANCHOR_YEAR
    try:
        _PICK_VALUE_ANCHOR_YEAR = int(year)
    except Exception:
        pass


def _pick_value_anchor():
    if _PICK_VALUE_ANCHOR_YEAR:
        return _PICK_VALUE_ANCHOR_YEAR
    return date.today().year


@dataclass
class DraftPick:
    """Represents a draft pick that can be owned and traded."""
    year: int  # Draft year
    round: int  # Round number (1-7)
    original_team: str  # Team that originally owned this pick
    current_team: str  # Team that currently owns this pick
    overall_pick: int = 0  # Overall pick number (calculated when draft order is set)
    is_conditional: bool = False  # If this pick has conditions attached
    condition: str = ""  # Description of any conditions
    # Structured pick protection (real NHL lottery protection): "", "top-3",
    # "top-10", or "lottery". Set on the trade screen; resolved at the draft
    # lottery by League.resolve_pick_protections().
    protection: str = ""
    traded_from: str = ""  # Team this pick was traded from (if applicable)
    trade_date: str = ""  # When this pick was traded
    # Standings-implied slot for a 1st whose real draft order isn't set yet
    # (0 = unknown -> mid-round default). Refreshed as standings move by
    # trade_engine.project_pick_slots(); the real order always wins.
    # Valuation prefers this over the blind #16 default.
    projected_overall: int = 0

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """Calculate overall pick number based on round."""
        if self.overall_pick == 0:
            # Estimate overall pick (32 teams per round). Mid-round is the
            # honest default for an unknown pick - estimating pick #1 of the
            # round inflates trade value via the lottery premium.
            self.overall_pick = ((self.round - 1) * 32) + 16
    
    @property
    def description(self) -> str:
        """Get a description of this draft pick."""
        r = self.round
        suffix = "th" if 11 <= (r % 100) <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(r % 10, "th")
        if self.original_team == self.current_team:
            return f"{self.year} {r}{suffix} Round Pick"
        else:
            return f"{self.year} {r}{suffix} Round Pick (from {self.original_team})"
    
    @property
    def is_expired(self) -> bool:
        """True once the pick's draft year has passed. An expired pick is
        dead paper: the draft it belonged to already happened. BUG-016 --
        the draft never consumed/pruned picks, so expired picks stayed
        tradeable at full value forever (the AI even asked for them)."""
        try:
            # <= : during season S (season_year=S) the S draft was already
            # held in June, so S picks are dead. The next live draft is
            # always season_year+1.
            return int(self.year) <= int(_pick_value_anchor())
        except Exception:
            return False

    @property
    def value(self) -> int:
        """Calculate the trade value of this draft pick."""
        # Expired picks are worthless (BUG-016). Nominal 1, not 0, so
        # ratio math never divides by zero.
        if self.is_expired:
            return 1
        # Base value decreases with later rounds and later years
        base_values = {1: 1000, 2: 500, 3: 250, 4: 125, 5: 100, 6: 75, 7: 50}
        base_value = base_values.get(self.round, 25)

        # Decrease value for future years (anchored to the live season --
        # a hardcoded 2024 here deepened the discount every year a save
        # ran, undervaluing every future pick in long saves).
        year_penalty = max(0, (self.year - _pick_value_anchor()) * 50)

        # Conditional picks are worth less
        conditional_penalty = 200 if self.is_conditional else 0

        return max(25, base_value - year_penalty - conditional_penalty)

    def can_be_traded(self) -> bool:
        """Check if this pick can be traded (some leagues have rules)."""
        # Expired picks are dead paper (BUG-016).
        if self.is_expired:
            return False
        # Basic rule: can't trade conditional picks that haven't been fulfilled
        if self.is_conditional and self.condition:
            return False
        return True

@dataclass
class GMProfile:
    """Represents the General Manager's profile and background."""
    name: str = "Your Name"
    age: int = 35
    birthplace: str = "Toronto, ON"
    nationality: str = "Canadian"
    
    # Playing background
    former_player: bool = False
    playing_position: str = "Center"  # If former player
    nhl_games_played: int = 0
    career_points: int = 0
    
    # Management background  
    coaching_experience: bool = False
    years_coaching: int = 0
    assistant_gm_experience: bool = False
    years_as_assistant: int = 0
    
    # Education & Skills
    education_level: str = "University Degree"  # High School, College, University Degree, MBA
    management_style: str = "Balanced"  # Analytics-Based, Traditional, Player-First, Balanced
    
    # Personality traits that could affect gameplay
    risk_tolerance: str = "Moderate"  # Conservative, Moderate, Aggressive
    loyalty_to_players: str = "Medium"  # Low, Medium, High
    media_savvy: str = "Good"  # Poor, Average, Good, Excellent
    
    def __post_init__(self):
        """Validate GM profile data after initialization."""
        if self.age < 25:
            self.age = 25
        elif self.age > 70:
            self.age = 70

def is_human_managed(team: object) -> bool:
    """True when a real person runs this club: the local user's team OR a
    team claimed by a multiplayer client (stamped on the host's canonical
    Team by the MP bridge). AI systems must skip these clubs -- same rule
    for the couch GM and the remote one."""
    try:
        if bool(getattr(team, "is_user_team", False)):
            return True
        if bool(getattr(team, "is_human_managed", False)):
            return True
    except Exception:
        pass
    return False


@dataclass
class Team:
    """Represents a single hockey team with a deep organizational structure."""
    team_name: str
    city: str
    division: str
    conference: str
    league_name: str = "National Hockey League"  # Default to NHL
    gm_name: str = "General Manager"  # Name of the team's GM
    gm_profile: GMProfile = field(default_factory=GMProfile)  # Full GM profile
    
    roster: List[Player] = field(default_factory=list)
    ahl_roster: List[Player] = field(default_factory=list)
    prospects: List[Player] = field(default_factory=list)
    staff: List[Staff] = field(default_factory=list)
    lineup: Dict[str, Player] = field(default_factory=dict)
    
    is_user_team: bool = False
    # Multiplayer: stamped True on the host's canonical Team when a remote
    # client claims this club (and cleared when they leave). Lets every
    # "skip the human" check cover client-managed clubs too -- the AI must
    # never manage a team a real person is running. Old-save safe: read
    # only via getattr(..., False) / is_human_managed().
    is_human_managed: bool = False
    salary_cap: int = 104000000  # 2026-27 NHL cap (modern day)
    # Annual hockey-ops staff payroll budget (league-wide rule, market-tiered;
    # see default_staff_budget). Hiring is blocked when it would exceed this.
    staff_budget: int = 10_000_000

    def staff_payroll(self) -> int:
        """Current annual staff payroll (all employed staff)."""
        try:
            return sum(int(getattr(s, "salary", 0) or 0)
                       for s in (self.staff or []))
        except Exception:
            return 0

    def staff_budget_remaining(self) -> int:
        """Uncommitted staff budget dollars."""
        try:
            return int(self.staff_budget or 0) - self.staff_payroll()
        except Exception:
            return 0
    scouting_reports: Dict[int, ScoutingReport] = field(default_factory=dict)
    inbox: EmailInbox = field(default_factory=EmailInbox)  # Email inbox system
    # Retained-salary ledger (real NHL: max 3 active retentions per club).
    # Each entry: {"player_id", "player_name", "amount", "seasons_remaining"}.
    # Counts as dead cap in salary_cap_system.total_cap_charge(); ticks down
    # in League.end_of_season().
    retained_salary: list = field(default_factory=list)
    
    # Team tactics (connected to strategy UI and sim engine)
    # Even strength: 'Offensive', 'Balanced', 'Defensive'
    tactic_even_strength: str = "Balanced"
    # Power play: 'Very Offensive', 'Offensive', 'Balanced'
    tactic_power_play: str = "Offensive"
    # Penalty kill: 'Aggressive', 'Defensive', 'Very Defensive'
    tactic_penalty_kill: str = "Defensive"
    # Line matching: 'Aggressive', 'Standard', 'Conservative'
    tactic_line_matching: str = "Standard"
    # Per-line matchup preferences (lines-screen "Match to line" dropdowns):
    # which OPPONENT forward line (1-4) each of my lines/pairs wants to face
    # at home with last change. None = coach's auto response. The sim reads
    # these in shift_engine._matching_response; unset entries fall back to
    # the automatic behavior. {'F': [None]*4, 'D': [None]*3}
    line_matchups: dict = field(
        default_factory=lambda: {"F": [None, None, None, None],
                                  "D": [None, None, None]})
    # Dressing-room dynamics (Morale screen): event feed + who picks the lines
    dynamics_log: List[dict] = field(default_factory=list)
    # Analytics scouting state (monthly tips + steal validation).
    # scout_*_tips: {player_id: {jpa, correct, scout}} from the monthly
    # pro-scout dispatch. steal_watch: {player_id: {...}} tracking
    # tipped players acquired via trade until their post-trade
    # production validates (or quietly expires) the scout's call.
    scout_buy_tips: Dict[int, dict] = field(default_factory=dict)
    scout_sell_tips: Dict[int, dict] = field(default_factory=dict)
    steal_watch: Dict[int, dict] = field(default_factory=dict)
    # Analytics wave 1 (information asymmetry):
    # - tip_ledger: every filed pro-scout tip awaiting grading, keyed
    #   f"{kind}:{player_id}:{date}". Graded monthly by
    #   analytics_scouting.grade_tip_ledger; feeds each scout's track record.
    # - sell_watch: {player_id: {...}} tracking sell-tipped players the team
    #   actually traded away, until regression validates (or expiry doubts)
    #   the call. Mirror of steal_watch.
    # - analytics_quality (0-100): the analytics department's quality. Drives
    #   ONLY what the user sees -- confidence intervals, data lag, noise in
    #   displayed metrics -- never player outcomes or ground-truth analysis.
    # - analytics_philosophy (0-100): how much the trade AI trusts process
    #   metrics. Drifts slowly with evidence, regresses on leadership change;
    #   each club keeps its own formula (never league-wide convergence).
    tip_ledger: Dict[str, dict] = field(default_factory=dict)
    sell_watch: Dict[int, dict] = field(default_factory=dict)
    analytics_quality: int = 35
    analytics_philosophy: float = 30.0
    philosophy_baseline: float = 30.0
    _prev_gm_name: str = ""
    _analytics_snapshot: dict = field(default_factory=dict)
    line_control: str = "coach"  # 'coach' | 'gm'
    # Roster continuity for the situations factor: offseason snapshot of NHL
    # roster names + measured summer turnover (0-1). High churn = gelling
    # penalty; a kept core = battle-tested bonus. Ticked each offseason.
    prev_roster_names: List[str] = field(default_factory=list)
    roster_churn: float = 0.2
    # Forecheck: '2-1-2', '1-2-2', '1-4' (pressure scheme in the other team's end)
    tactic_forecheck: str = "2-1-2"
    # Offensive-zone formation: 'Overload', 'Umbrella', 'Spread', 'Crash the Net'
    tactic_offense: str = "Spread"
    
    # Draft picks owned by this team
    draft_picks: Dict[int, List[DraftPick]] = field(default_factory=dict)  # Year -> List of picks
    
    # Team Statistics for Standings
    wins: int = 0
    losses: int = 0
    ties: int = 0
    ot_losses: int = 0
    games_played: int = 0
    # Streak tracking (season_review.py builds the year-end story from
    # these; archived to franchise_records at the season review).
    win_streak: int = 0          # current consecutive wins
    longest_win_streak: int = 0  # season best

    # Archived season-review cards, keyed by season year. Written at
    # deliver_season_review() each offseason; read back any later season
    # from the League History -> Season Reviews tab. Plain dicts so the
    # save pickles cleanly.
    season_reviews: Dict[int, dict] = field(default_factory=dict)

    @property
    def payroll(self) -> int:
        return sum(p.contract.salary for p in self.roster)

    @property
    def cap_space(self) -> int:
        # Central cap accounting: waiver shed, retention, burial, and all
        # dead cap flow through here, so every reader (AI claims, FA
        # checks, cap screens, the over-cap blocker) sees the same number
        # the league office enforces.
        try:
            from salary_cap_system import cap_space as _central_cap_space
            return int(_central_cap_space(self))
        except Exception:
            return self.salary_cap - self.payroll
    
    @property
    def team_chemistry(self) -> int:
        """Calculates team chemistry based on player morale and leadership."""
        if not self.roster:
            return 50
        # morale and leadership are both native 1-100
        avg_morale = sum(p.morale for p in self.roster) / len(self.roster)
        avg_leadership = sum(to_100_scale(p.leadership) for p in self.roster) / len(self.roster)
        return max(1, min(100, int(avg_morale * 0.6 + avg_leadership * 0.4)))
    
    @property
    def points(self) -> int:
        """Calculate total points (2 for win, 1 for tie/OT loss)"""
        return (self.wins * 2) + self.ties + self.ot_losses
    
    @property
    def winning_percentage(self) -> float:
        """Calculate winning percentage"""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played
    
    @property
    def record_string(self) -> str:
        """Get team record as a formatted string"""
        if self.ot_losses > 0:
            return f"{self.wins}-{self.losses}-{self.ot_losses}"
        elif self.ties > 0:
            return f"{self.wins}-{self.losses}-{self.ties}"
        else:
            return f"{self.wins}-{self.losses}"

    def add_player(self, player: Player, roster_type: str = "roster"):
        """Adds a player to the specified roster (roster, ahl, prospects)."""
        roster_map = { "roster": self.roster, "ahl": self.ahl_roster, "prospects": self.prospects }
        if roster_type in roster_map:
            roster_map[roster_type].append(player)
            player.team_name = self.team_name
            # Season-history stint tracker: NHL roster joins open a stint.
            # AHL/prospect moves never open stints.
            if roster_type == "roster":
                try:
                    open_stint(player, _team_abbr_safe(self.team_name))
                except Exception:
                    pass
        else:
            raise ValueError("Invalid roster type specified.")

    def remove_player(self, player: Player):
        """Removes a player from any list they are on."""
        # Remember where he played: the player-decision model uses the last
        # club for loyalty / bad-blood math (signing with a hated rival).
        try:
            player.last_team_name = self.team_name
        except Exception:
            pass
        # Season-history stint tracker: leaving the NHL roster seals the
        # open stint. AHL/prospect-only players have no stint to seal.
        try:
            _was_nhl = player in self.roster
        except Exception:
            _was_nhl = False
        if player in self.roster: self.roster.remove(player)
        if player in self.ahl_roster: self.ahl_roster.remove(player)
        if player in self.prospects: self.prospects.remove(player)
        player.team_name = "Free Agent"
        if _was_nhl:
            try:
                close_stint(player)
            except Exception:
                pass

    def get_players_by_position(self, position: PlayerPosition) -> List[Player]:
        return [p for p in self.roster if p.primary_position == position]

    def get_starting_goalie(self) -> Player:
        goalies = self.get_players_by_position(PlayerPosition.GOALIE)
        if not goalies:
            return Player("Default", "Goalie", 99, PlayerPosition.GOALIE, goaltending=1)
        return max(goalies, key=lambda g: g.overall_rating())
    
    def validate_staff_structure(self) -> Dict[str, List[str]]:
        """Validate the team's staff structure and return any issues"""
        issues = {'errors': [], 'warnings': []}
        
        # Check for unique role violations
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        role_counts = {}
        
        for staff_member in self.staff:
            role = staff_member.role
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # Check unique role constraints
        for role in unique_roles:
            count = role_counts.get(role, 0)
            if count == 0:
                issues['errors'].append(f"Missing {role.value}")
            elif count > 1:
                issues['errors'].append(f"Multiple {role.value}s ({count})")
        
        # Check essential roles
        essential_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH
        ]
        
        for role in essential_roles:
            if role not in role_counts:
                issues['warnings'].append(f"Missing {role.value}")
        
        # Check total staff count
        if len(self.staff) < 8:
            issues['warnings'].append(f"Only {len(self.staff)} staff members (recommended: 10-15)")
        elif len(self.staff) > 20:
            issues['warnings'].append(f"Very large staff ({len(self.staff)} members)")
        
        return issues
    
    def get_staff_by_role(self, role: StaffRole) -> List[Staff]:
        """Get all staff members with a specific role"""
        return [staff for staff in self.staff if staff.role == role]
    
    def has_unique_roles(self) -> bool:
        """Check if team has exactly one of each unique role"""
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        for role in unique_roles:
            staff_with_role = self.get_staff_by_role(role)
            if len(staff_with_role) != 1:
                return False
        return True
    
    def update_record(self, result: str, overtime: bool = False):
        """Update team record based on game result.

        Also tracks the current/longest win streak -- the season-review
        builder and the franchise record book read these. Only regulation
        + OT/SO wins extend a win streak; anything else snaps it.
        """
        self.games_played += 1

        if result.upper() == "WIN":
            self.wins += 1
            self.win_streak += 1
            if self.win_streak > self.longest_win_streak:
                self.longest_win_streak = self.win_streak
        elif result.upper() == "LOSS":
            if overtime:
                self.ot_losses += 1
            else:
                self.losses += 1
            self.win_streak = 0
        elif result.upper() == "TIE":
            self.ties += 1
            self.win_streak = 0
    
    def reset_season_record(self):
        """Reset team record for new season"""
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.ot_losses = 0
        self.games_played = 0
        self.win_streak = 0
        self.longest_win_streak = 0
    
    def generate_sample_season_record(self, games_played: int = 25):
        """Generate a realistic sample season record for demonstration purposes"""
        import random
        
        # Reset current record
        self.reset_season_record()
        
        # Based on team quality (average roster rating), determine win probability
        if self.roster:
            avg_rating = sum(p.overall_rating() for p in self.roster[:20]) / min(20, len(self.roster))
            # Convert rating (0-20) to win probability (0.3 - 0.7)
            base_win_probability = 0.3 + (avg_rating / 20.0) * 0.4
        else:
            base_win_probability = 0.5  # Default 50% win rate
        
        # Simulate games
        for _ in range(games_played):
            self.games_played += 1
            
            # Random outcome based on team strength
            outcome_roll = random.random()
            
            if outcome_roll < base_win_probability:
                self.wins += 1
            elif outcome_roll < base_win_probability + 0.08:  # 8% chance of OT loss
                self.ot_losses += 1
            elif outcome_roll < base_win_probability + 0.12:  # 4% chance of tie (rare in modern NHL)
                self.ties += 1
            else:
                self.losses += 1

    def initialize_draft_picks(self, years: List[int]):
        """Initialize standard draft picks for specified years."""
        for year in years:
            if year not in self.draft_picks:
                self.draft_picks[year] = []
                
            # Add standard 7 rounds of picks if they don't exist
            existing_rounds = {pick.round for pick in self.draft_picks[year]}
            for round_num in range(1, 8):  # Rounds 1-7
                if round_num not in existing_rounds:
                    pick = DraftPick(
                        year=year,
                        round=round_num,
                        original_team=self.team_name,
                        current_team=self.team_name
                    )
                    self.draft_picks[year].append(pick)

    def get_picks_for_year(self, year: int) -> List[DraftPick]:
        """Get all draft picks owned by this team for a specific year."""
        return self.draft_picks.get(year, [])

    def get_tradeable_picks(self, years: List[int] = None) -> List[DraftPick]:
        """Get all tradeable draft picks owned by this team."""
        if years is None:
            years = list(self.draft_picks.keys())
        
        tradeable = []
        for year in years:
            for pick in self.draft_picks.get(year, []):
                if pick.can_be_traded():
                    tradeable.append(pick)
        return tradeable

    def trade_pick(self, pick: DraftPick, to_team: str, trade_details: str = ""):
        """Trade a draft pick to another team."""
        if pick not in self.draft_picks.get(pick.year, []):
            raise ValueError("Team does not own this draft pick")
        
        if not pick.can_be_traded():
            raise ValueError("This draft pick cannot be traded")
        
        # Update pick ownership
        pick.traded_from = self.team_name
        pick.current_team = to_team
        pick.trade_date = str(date.today())
        
        # Remove from this team's picks
        self.draft_picks[pick.year].remove(pick)

    def receive_pick(self, pick: DraftPick):
        """Receive a draft pick from a trade."""
        # Ensure the year exists in our picks dictionary
        if pick.year not in self.draft_picks:
            self.draft_picks[pick.year] = []
        
        # Update ownership
        pick.current_team = self.team_name
        
        # Add to our picks
        self.draft_picks[pick.year].append(pick)

    def get_draft_pick_summary(self) -> str:
        """Get a summary of all draft picks owned."""
        if not self.draft_picks:
            return "No draft picks"
        
        summary_parts = []
        for year in sorted(self.draft_picks.keys()):
            picks = self.draft_picks[year]
            if picks:
                rounds = sorted([pick.round for pick in picks])
                summary_parts.append(f"{year}: Rounds {', '.join(map(str, rounds))}")
        
        return "; ".join(summary_parts) if summary_parts else "No draft picks"

    def count_picks_by_round(self, year: int) -> Dict[int, int]:
        """Count how many picks the team has in each round for a given year."""
        picks = self.get_picks_for_year(year)
        round_counts = {}
        
        for pick in picks:
            round_counts[pick.round] = round_counts.get(pick.round, 0) + 1
        
        return round_counts

# ---------------------------------------------------------------------------
# Prospect development tracks (new-CBA junior assignment rules live here so
# the UI, waivers, and QA all share one rulebook).
# ---------------------------------------------------------------------------
_CHL_JUNIOR_LEAGUES = ("OHL", "QMJHL", "WHL")


def junior_track_of(player) -> str:
    """Development track from the player's junior league.

    Returns "CHL" (OHL/QMJHL/WHL), "NCAA", or "EUROPE" (everyone else).
    Derived from junior_league, which -- unlike rights_type -- survives
    signing, so this works for signed prospects too.
    """
    try:
        jl = (getattr(player, "junior_league", "") or "").strip().upper()
    except Exception:
        jl = ""
    if jl in _CHL_JUNIOR_LEAGUES:
        return "CHL"
    if jl == "NCAA":
        return "NCAA"
    return "EUROPE"


def prospect_ahl_eligible(player) -> bool:
    """Can this prospect be assigned to the AHL?

    New CBA (2026): a 19-year-old CHL player drafted in the FIRST ROUND
    may be loaned to the AHL (no per-team limit). Every other under-20
    CHL player goes back to junior -- 18-year-olds are never eligible.
    NCAA, European, and age-20+ players are always eligible.
    """
    try:
        _age = int(getattr(player, "age", 20) or 20)
    except Exception:
        _age = 20
    if junior_track_of(player) == "CHL" and _age < 20:
        if _age >= 19:
            try:
                if int(getattr(player, "draft_round", 0) or 0) == 1:
                    return True
            except Exception:
                pass
        return False
    return True


def junior_assignment_label(player) -> str:
    """Where a junior-aged signed prospect plays: his junior league."""
    try:
        return (getattr(player, "junior_league", "") or "").strip() or "Junior"
    except Exception:
        return "Junior"


def bank_final_table(standings):
    """Copy the final standings table before a season rollover zeroes it.

    P-2: League.end_of_season() calls initialize_standings(), which clears
    lg.standings by design. This returns an independent snapshot
    ({team_name: {W/L/OTL/Points}}) that offseason consumers can read after
    the rollover. Never raises; never mutates the input.
    """
    try:
        return {str(_name): dict(_row or {})
                for _name, _row in (standings or {}).items()}
    except Exception:
        return {}


@dataclass
class League:
    """Represents the entire league, structured like the NHL."""
    league_name: str
    season_year: int = field(default_factory=lambda: datetime.now().year)
    teams: List[Team] = field(default_factory=list)
    free_agents: List[Player] = field(default_factory=list)  # Kept for compatibility, but may be overridden
    free_agent_staff: List[Staff] = field(default_factory=list)
    # Coaches employed by European clubs (SHL, Liiga, NL, DEL, KHL ...).
    # Scouted and approached like free agents -- no NHL contract to wait out.
    overseas_staff: List[Staff] = field(default_factory=list)
    draft_prospects: List[Player] = field(default_factory=list)
    # CHL prospects who re-enter the draft after their rights expire
    # (Part 5 rights lifecycle). The UI/draft layer reads this after the
    # rollover. Old-save safe: read via getattr(self, 'draft_reentries', [])
    # -- pickled leagues predating this change have no such attribute.
    draft_reentries: List[Player] = field(default_factory=list)
    # Rights-lifecycle news strings collected during the offseason rollover
    # (re-entries, UFAs, retirements, holdout warnings, league changes).
    # The UI layer posts these; old-save safe, same getattr caveat as above.
    rights_news: List[str] = field(default_factory=list)
    # Junior/college award headlines from prospect_accolades (flushed to
    # the inbox by the UI layer, same as rights_news).
    prospect_awards_news: List[str] = field(default_factory=list)
    # ELC slide headlines from the offseason rollover (CBA 9.1(d)):
    # "X's entry-level contract slides a year (<10 NHL games)". The UI
    # layer posts these, same as rights_news. Old-save safe via getattr.
    elc_slide_news: List[str] = field(default_factory=list)
    # Rivalry-review verdicts from the triennial offseason review
    # (solidified / entrenched / buried / declared only). The UI layer
    # posts these, same as rights_news. Old-save safe via getattr.
    rivalry_review_news: List[str] = field(default_factory=list)
    # Staff breakthrough headlines from the offseason rollover: coaches
    # who made a career leap this year. The UI layer posts these, same
    # as rights_news. Old-save safe via getattr.
    staff_breakthrough_news: List[str] = field(default_factory=list)
    schedule: List[Tuple[date, Team, Team]] = field(default_factory=list)
    standings: Dict[str, Dict] = field(default_factory=dict)
    current_game_index: int = 0
    _game_manager: object = field(default=None, init=False, repr=False)  # Reference to game manager
    # Tentpole event state (persisted in saves): years the entry draft was
    # held, and (event, year) pairs the user was already prompted about.
    draft_held_years: List[int] = field(default_factory=list)
    # Years the entry draft's picks were actually conducted (war room or
    # headless conductor). Guards against double-conducting a draft.
    draft_conducted_years: List[int] = field(default_factory=list)
    # Draft grades by year ({str(year): [(team, grade, ratio)]}), persisted
    # so the war room's review modal and future seasons can look back.
    draft_grades_history: Dict[str, list] = field(default_factory=dict)
    # All-Star rosters by season label ("2026-27" -> {division:
    # {captain_id, skater_ids, goalie_ids}}). Plain IDs, save/load safe.
    # Old-save safe: read via getattr(league, 'all_star_rosters', {}).
    all_star_rosters: Dict[str, dict] = field(default_factory=dict)
    event_day_prompted: List[List] = field(default_factory=list)
    # Draft lottery state (persisted in saves): televised reveal rows per
    # year ({pick, team, original_team, odds_pct, movement}) and the years
    # the May 8 lottery was already held.
    lottery_results: Dict[int, List[Dict]] = field(default_factory=dict)
    lottery_held_years: List[int] = field(default_factory=list)
    # International windows (persisted): years each tournament was held and
    # a short history of results for billing.
    intl_held: Dict[str, List[int]] = field(
        default_factory=lambda: {"olympics": [], "worlds": []})
    intl_history: List[Dict] = field(default_factory=list)
    # Olympic prep between announcement (Feb 9) and medal day (Feb 22):
    # plain-data rosters + coaches per year; years already announced.
    intl_prep: Dict[int, Dict] = field(default_factory=dict)
    intl_announced: List[int] = field(default_factory=list)
    # League-wide bad blood: coach-coach, GM-coach, player-player, team-team
    rivalries: List[dict] = field(default_factory=list)
    # Dynamic salary cap system: growth, history, market-setting contracts.
    # Defaults keep old saves working (from_dict with empty dict).
    salary_cap_system: object = field(default_factory=SalaryCapSystem)
    
    def set_game_manager(self, game_manager):
        """Set reference to game manager for database access."""
        self._game_manager = game_manager
    
    def __post_init__(self):
        self.setup_nhl_teams()
        # Pin the draft-pick future discount to this save's season so
        # long-running saves don't undervalue future picks.
        try:
            set_pick_value_anchor_year(self.season_year)
        except Exception:
            pass

    def setup_nhl_teams(self):
        """Initializes the league with all 32 real NHL teams (2024-25 season)."""
        teams_data = {
            # Eastern Conference
            "Metropolitan": {
                "Carolina Hurricanes": "Raleigh", "Columbus Blue Jackets": "Columbus", 
                "New Jersey Devils": "Newark", "New York Islanders": "New York", 
                "New York Rangers": "New York", "Philadelphia Flyers": "Philadelphia", 
                "Pittsburgh Penguins": "Pittsburgh", "Washington Capitals": "Washington"
            },
            "Atlantic": {
                "Boston Bruins": "Boston", "Buffalo Sabres": "Buffalo", 
                "Detroit Red Wings": "Detroit", "Florida Panthers": "Sunrise", 
                "Montréal Canadiens": "Montreal", "Ottawa Senators": "Ottawa", 
                "Tampa Bay Lightning": "Tampa Bay", "Toronto Maple Leafs": "Toronto"
            },
            # Western Conference
            "Central": {
                "Chicago Blackhawks": "Chicago", "Colorado Avalanche": "Denver", 
                "Dallas Stars": "Dallas", "Minnesota Wild": "St. Paul", 
                "Nashville Predators": "Nashville", "St. Louis Blues": "St. Louis", 
                "Utah Hockey Club": "Salt Lake City", "Winnipeg Jets": "Winnipeg"
            },
            "Pacific": {
                "Anaheim Ducks": "Anaheim", "Calgary Flames": "Calgary", 
                "Edmonton Oilers": "Edmonton", "Los Angeles Kings": "Los Angeles", 
                "San Jose Sharks": "San Jose", "Seattle Kraken": "Seattle", 
                "Vancouver Canucks": "Vancouver", "Vegas Golden Knights": "Las Vegas"
            }
        }
        for division, teams in teams_data.items():
            conference = "Eastern" if division in ["Metropolitan", "Atlantic"] else "Western"
            for name, city in teams.items():
                team = Team(name, city, division, conference)
                team.league_name = "National Hockey League"  # Mark as NHL team
                self.teams.append(team)
        # Wave 1: each club gets its own analytics identity (department
        # quality + trade-AI philosophy vary club to club).
        try:
            import analytics_scouting as _as
            _as.seed_analytics_identities(self.teams)
        except Exception:
            pass
        self.initialize_standings()

    def initialize_standings(self):
        """Sets up the standings dictionary for each team.

        Rebuilds from scratch so stale keys (e.g. template team names from
        before database generation renamed teams) are removed and every
        current team is present.
        """
        self.standings.clear()
        for team in self.teams:
            self.standings[team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}

    # ------------------------------------------------------------------
    # Schedule template cache.
    #
    # generate_schedule() is deterministic for a given (season_year,
    # league structure): it seeds `random` from the season year before the
    # constraint solver runs. The solver takes ~13s; the cached template --
    # (date, home_name, away_name) tuples -- rebuilds in milliseconds by
    # mapping team names back onto the current Team objects. Bump
    # SCHEDULE_CACHE_VERSION whenever the scheduling algorithm changes so
    # stale templates are never served.
    # ------------------------------------------------------------------
    # v2: template entries carry the preseason flag (6-tuples). v1 caches
    # predate preseason games and are ignored. v3: the Olympic break
    # (Feb 10-24, Olympic years) keeps NHL games off those dates.
    SCHEDULE_CACHE_VERSION = 3
    SCHEDULE_CACHE_DIR = _os.path.join("saves", "schedule_cache")

    def _schedule_cache_path(self, season_year, seed):
        import hashlib
        teams_key = "|".join(sorted(
            f"{t.team_name}@{getattr(t, 'league_name', '')}"
            for t in self.teams))
        raw = (f"v{self.SCHEDULE_CACHE_VERSION}|{season_year}|{seed}|"
               f"{teams_key}")
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return _os.path.join(self.SCHEDULE_CACHE_DIR,
                             f"template_{season_year}_{digest}.pkl.gz")

    def _load_schedule_template(self, season_year, seed):
        """Return the cached template list, or None on any miss/problem."""
        import gzip, pickle
        path = self._schedule_cache_path(season_year, seed)
        try:
            with open(path, "rb") as fh:
                template = pickle.loads(gzip.decompress(fh.read()))
            if isinstance(template, list) and template:
                return template
        except (OSError, ValueError, EOFError):
            pass
        return None

    def _save_schedule_template(self, season_year, seed):
        """Serialize the freshly generated schedule as a name-based template."""
        import gzip, pickle
        template = []
        for entry in self.schedule:
            if isinstance(entry, dict):
                home, away = entry.get('home_team'), entry.get('away_team')
                if not (hasattr(home, 'team_name')
                        and hasattr(away, 'team_name')):
                    return  # unknown shape: don't cache
                d = entry.get('date')
                template.append((
                    'G',
                    d.isoformat() if hasattr(d, 'isoformat') else str(d),
                    home.team_name, away.team_name,
                    entry.get('league', ''),
                    bool(entry.get('preseason', False))))
            elif isinstance(entry, (tuple, list)) and len(entry) >= 3:
                d = entry[0]
                template.append((
                    'E',
                    d.isoformat() if hasattr(d, 'isoformat') else str(d),
                    str(entry[1]), entry[2]))
            else:
                return  # unknown shape: don't cache
        if not template:
            return
        try:
            _os.makedirs(self.SCHEDULE_CACHE_DIR, exist_ok=True)
            tmp = self._schedule_cache_path(season_year, seed) + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(gzip.compress(
                    pickle.dumps(template, protocol=pickle.HIGHEST_PROTOCOL)))
            _os.replace(tmp, self._schedule_cache_path(season_year, seed))
        except OSError:
            pass

    def _apply_schedule_template(self, template):
        """Rebuild self.schedule from a cached template. False => regenerate."""
        by_name = {t.team_name: t for t in self.teams}
        rebuilt = []
        try:
            for item in template:
                kind = item[0]
                game_date = date.fromisoformat(item[1])
                if kind == 'G':
                    # v2 entries carry the preseason flag (6-tuple); v1
                    # entries (5-tuple) predate preseason games.
                    preseason = bool(item[5]) if len(item) > 5 else False
                    _, _, home_name, away_name, league = item[:5]
                    home, away = by_name.get(home_name), by_name.get(away_name)
                    if home is None or away is None:
                        return False  # structure changed
                    _g = {'date': game_date, 'home_team': home,
                          'away_team': away, 'league': league}
                    if preseason:
                        _g['preseason'] = True
                    rebuilt.append(_g)
                elif kind == 'E':
                    _, _, event_kind, payload = item
                    rebuilt.append((game_date, event_kind, payload))
                else:
                    return False
        except (ValueError, IndexError, TypeError):
            return False
        # Light validation: every NHL team must have exactly 82
        # regular-season games (preseason exhibitions don't count).
        counts = {}
        for e in rebuilt:
            if (isinstance(e, dict) and e.get('league') == 'NHL'
                    and not e.get('preseason')):
                for side in ('home_team', 'away_team'):
                    name = e[side].team_name
                    counts[name] = counts.get(name, 0) + 1
        if counts and any(c != 82 for c in counts.values()):
            return False
        self.schedule.clear()
        self.schedule.extend(rebuilt)
        self.schedule.sort(key=lambda x: x['date']
                           if isinstance(x, dict) and 'date' in x else x[0])
        return True

    def generate_schedule(self, season_year=None, rotation_seed=None):
        """Generate complete league schedule with authentic NHL rotating patterns and realistic distribution.

        Args:
            season_year: The year this season starts (default: the league's
                season_year, which defaults to the current year)
            rotation_seed: Optional seed for reproducible schedule variations (uses season_year if None)
        """
        if season_year is None:
            season_year = self.season_year
        print(f"🏒 Generating league schedule for {season_year}-{season_year+1} season...")

        # Fresh schedule = fresh season: reset the parity engine's season
        # table (target-on-back / trap-game tiers) and every team's
        # cross-game form. Additive; never raises.
        try:
            import parity_engine as _pe
            _pe.new_season()
            for _t in getattr(self, "teams", []) or []:
                try:
                    # Keep the current coach key: a new season is not a
                    # coaching change (no phantom new-coach bounce).
                    _ck = _pe._coach_key(_t)
                    _t._parity_state = {"form": 0.0, "streak": 0,
                                        "winless": 0, "coach_key": _ck,
                                        "new_coach_games": 0}
                except Exception:
                    pass
        except Exception:
            pass

        # Set up seasonal rotation seed
        if rotation_seed is None:
            rotation_seed = season_year

        # Fast path: the solver is deterministic per (season_year, league
        # structure), so a cached template rebuilds the identical schedule
        # in milliseconds instead of ~13s of constraint solving.
        template = self._load_schedule_template(season_year, rotation_seed)
        if template is not None and self._apply_schedule_template(template):
            print(f"⚡ Schedule loaded from template cache "
                  f"({len(self.schedule)} entries).")
            return

        random.seed(rotation_seed)  # For reproducible but varied schedules
        
        self.schedule.clear()
        
        # Group teams by league
        leagues = {}
        for team in self.teams:
            league_name = getattr(team, 'league_name', 'National Hockey League')
            if league_name not in leagues:
                leagues[league_name] = []
            leagues[league_name].append(team)
        
        # Generate schedule for each league separately
        for league_name, league_teams in leagues.items():
            if len(league_teams) < 2:
                continue  # Skip leagues with less than 2 teams
                
            print(f"Generating schedule for {league_name} ({len(league_teams)} teams)")
            if league_name == "National Hockey League":
                self._generate_authentic_nhl_schedule(league_teams, season_year, rotation_seed)
                # Preseason: every NHL club plays 6 exhibitions (3H/3A)
                # across late September, like the real league. Runs after
                # the regular-season solver so dates never collide.
                try:
                    self._generate_preseason_schedule(league_teams, season_year,
                                                      rotation_seed)
                except Exception as _e:
                    print(f"⚠️ Preseason generation skipped: {_e}")
            else:
                self._generate_other_league_schedule(league_teams, league_name)
        
        # Sort all games by date
        self.schedule.sort(key=lambda x: x['date'] if isinstance(x, dict) and 'date' in x else x[0])
        
        # Verify schedule integrity
        self._verify_complete_schedule_integrity()

        # Cache the template so the next new game with the same league
        # structure skips the constraint solver entirely.
        self._save_schedule_template(season_year, rotation_seed)

        # Reset random seed to avoid affecting other game elements
        import time
        random.seed(int(time.time()))

    def _generate_authentic_nhl_schedule(self, nhl_teams, season_year, rotation_seed):
        """Generate NHL schedule with simple chronological approach to prevent consecutive games."""
        print("🏒 Building NHL schedule with simple consecutive games prevention...")
        
        if len(nhl_teams) != 32:
            print(f"⚠️ Warning: Expected 32 NHL teams, got {len(nhl_teams)}")
            return
        
        # Initialize NHL games only (preserve existing schedule for other leagues)
        nhl_games = []
        self.games = {}
        
        # Create all required matchups first (82 games per team = 1,312 total games)
        all_matchups = self._create_all_nhl_matchups(nhl_teams)
        print(f"Created {len(all_matchups)} total matchups")
        
        # Schedule games chronologically with consecutive games prevention
        self._schedule_games_chronologically(all_matchups, nhl_teams, season_year)
        
        # Add NHL special events (All-Star, Trade Deadline, Draft, etc.)
        calendar_data = self._create_authentic_nhl_calendar(season_year)
        self._add_nhl_special_events(calendar_data['events'], season_year)

    def _generate_preseason_schedule(self, nhl_teams, season_year,
                                     rotation_seed=None):
        """NHL preseason: 6 exhibitions per club (3 home / 3 away), played
        across late September into early October, before the Oct 8 opener --
        like the real league. Entries carry ``preseason: True`` so the
        daily sim quick-sims them without touching standings, season
        stats, career GP, board/morale, or milestones.

        Pairing shape mirrors real preseason travel: 2 intra-division
        rounds, 2 intra-conference rounds, 2 league-wide rounds (circle
        method, so every club gets exactly 6 games; rematches across
        rounds are possible, like real September home-and-homes).
        """
        from datetime import date as _date, time as _time, timedelta as _td
        teams = [t for t in nhl_teams
                 if getattr(t, 'league_name', 'National Hockey League')
                 == 'National Hockey League']
        if len(teams) != 32:
            print(f"⚠️ Preseason: expected 32 NHL teams, got {len(teams)}")
            return

        rng = random.Random((rotation_seed or season_year) * 7919 + 13)

        def circle_round(group, rnd):
            """One round-robin round (circle method) for an even group."""
            n = len(group)
            order = list(group)
            if n % 2:
                order.append(None)
                n += 1
            fixed, rest = order[0], order[1:]
            k = rnd % (n - 1) if n > 1 else 0
            rot = list(rest) if k == 0 else rest[-k:] + rest[:-k]
            ring = [fixed] + rot
            pairs = []
            for i in range(n // 2):
                a, b = ring[i], ring[n - 1 - i]
                if a is not None and b is not None:
                    pairs.append((a, b))
            return pairs

        divisions = {}
        for t in teams:
            divisions.setdefault(getattr(t, 'division', '?'), []).append(t)
        conferences = {}
        for t in teams:
            conferences.setdefault(getattr(t, 'conference', '?'), []).append(t)

        pair_rounds = []  # 6 rounds x 16 pairings
        # Rounds 1-2: intra-division (regional, like real September hockey).
        for div_teams in divisions.values():
            grp = sorted(div_teams, key=lambda t: t.team_name)
            rng.shuffle(grp)
            for rnd in range(2):
                pair_rounds.append(circle_round(grp, rnd))
        # Rounds 3-4: intra-conference cross-division.
        for conf_teams in conferences.values():
            grp = sorted(conf_teams, key=lambda t: t.team_name)
            rng.shuffle(grp)
            for rnd in range(2):
                pair_rounds.append(circle_round(grp, rnd))
        # Rounds 5-6: league-wide.
        grp = sorted(teams, key=lambda t: t.team_name)
        rng.shuffle(grp)
        for rnd in range(2):
            pair_rounds.append(circle_round(grp, rnd))

        # Balance home/away to 3 and 3 per club.
        home_count = {t.team_name: 0 for t in teams}
        games_count = {t.team_name: 0 for t in teams}
        fixtures = []  # (team_a, team_b, home_team)
        for ridx, pairs in enumerate(pair_rounds):
            for a, b in pairs:
                if home_count[a.team_name] < home_count[b.team_name]:
                    home = a
                elif home_count[b.team_name] < home_count[a.team_name]:
                    home = b
                else:
                    home = a if (ridx % 2 == 0) else b
                fixtures.append((a, b, home))
                home_count[home.team_name] += 1
                games_count[a.team_name] += 1
                games_count[b.team_name] += 1

        # Repair pass: flip venues until every club is exactly 3H/3A.
        # (Total homes == 3 x clubs, so overs and unders always pair up.)
        for _pass in range(8):
            over = [t for t in teams if home_count[t.team_name] > 3]
            under = {t.team_name for t in teams
                     if home_count[t.team_name] < 3}
            if not over or not under:
                break
            moved = False
            for i, (a, b, home) in enumerate(fixtures):
                if home.team_name in under:
                    continue
                away = b if home is a else a
                if (home.team_name in {t.team_name for t in over}
                        and away.team_name in under):
                    fixtures[i] = (a, b, away)
                    home_count[home.team_name] -= 1
                    home_count[away.team_name] += 1
                    moved = True
                    break
            if not moved:
                break

        # Dates: Sep 22 -> Oct 5 (opener is Oct 8), max 8 games/day,
        # never two games in one day for the same club.
        start = _date(season_year, 9, 22)
        end = _date(season_year, 10, 5)
        overflow_end = _date(season_year, 10, 7)
        all_dates = []
        _d = start
        while _d <= overflow_end:
            all_dates.append(_d)
            _d += _td(days=1)
        busy = {t.team_name: set() for t in teams}
        daily = {}
        entries = []
        for a, b, home in fixtures:
            away = b if home is a else a
            placed = False
            # all_dates is chronological (window first, Oct 6-7 overflow
            # last), so the first fitting date is always preferred.
            for d in all_dates:
                if d in busy[a.team_name] or d in busy[b.team_name]:
                    continue
                if daily.get(d, 0) >= 8:
                    continue
                entries.append({
                    'date': d,
                    'home_team': home,
                    'away_team': away,
                    'time': _time(19, 0),
                    'league': 'NHL',
                    'preseason': True,
                })
                busy[a.team_name].add(d)
                busy[b.team_name].add(d)
                daily[d] = daily.get(d, 0) + 1
                placed = True
                break
            if not placed:
                print(f"⚠️ Preseason: could not place "
                      f"{a.team_name} vs {b.team_name}")

        # Sanity: every club exactly 6 games; home split 2-4 (the real
        # league doesn't play perfectly even September slates either).
        bad = [t.team_name for t in teams
               if games_count.get(t.team_name, 0) != 6
               or not 2 <= home_count.get(t.team_name, 0) <= 4]
        self.schedule.extend(entries)
        print(f"🏒 Preseason: {len(entries)} exhibitions scheduled "
              f"({start.isoformat()} -> {end.isoformat()})"
              + (f" -- ⚠️ imbalance: {bad}" if bad else ""))

    def _create_all_nhl_matchups(self, nhl_teams):
        """Create all required NHL matchups in a simple way - exactly 82 games per team."""
        print("Creating all NHL matchups...")
        
        # Organize teams by division and conference
        divisions = {
            'Atlantic': [t for t in nhl_teams if t.division == 'Atlantic'],
            'Metropolitan': [t for t in nhl_teams if t.division == 'Metropolitan'], 
            'Central': [t for t in nhl_teams if t.division == 'Central'],
            'Pacific': [t for t in nhl_teams if t.division == 'Pacific']
        }
        
        all_matchups = []
        
        # Each team needs exactly 82 games total
        # Simple approach: Each team plays every other team in the league ~2-3 times
        
        # For each team, schedule games against all 31 other teams
        interconference_games_assigned = 0  # Track to keep total at 82 per team
        
        for i, team1 in enumerate(nhl_teams):
            for j, team2 in enumerate(nhl_teams):
                if i < j:  # Avoid duplicates - each pair only once
                    # Decide how many games between these teams based on relationship
                    if team1.division == team2.division:
                        # Division rivals: 4 games each (4 × 7 = 28 games per team)
                        games_count = 4
                    elif team1.conference == team2.conference:
                        # Same conference, different division: 3 games each (3 × 8 = 24 games per team)
                        games_count = 3  
                    else:
                        # Different conference: 2 games each (2 × 16 = 32 games per team)
                        # Total: 28 + 24 + 32 = 84, which is 2 over our target
                        # So reduce some inter-conference games from 2 to 1
                        if (i + j) % 16 < 14:  # 14 out of 16 inter-conference matchups get 2 games
                            games_count = 2
                        else:  # 2 out of 16 inter-conference matchups get 1 game  
                            games_count = 1
                        # This gives: 28 + 24 + (2×14 + 1×2) = 28 + 24 + 30 = 82 games
                    
                    # Add the games (alternating home/away)
                    for game_num in range(games_count):
                        if game_num % 2 == 0:
                            all_matchups.append((team1, team2, 'HOME'))  # team1 hosts
                        else:
                            all_matchups.append((team2, team1, 'HOME'))  # team2 hosts
        
        # Shuffle matchups to distribute them randomly throughout season
        random.shuffle(all_matchups)
        print(f"Created {len(all_matchups)} total games")
        return all_matchups

    def _schedule_games_chronologically(self, all_matchups, nhl_teams, season_year):
        """Schedule games chronologically with REALISTIC NHL conflict prevention - allows back-to-backs but prevents 3+ consecutive games."""
        print("Scheduling games with REALISTIC NHL scheduling rules...")
        
        # Initialize NHL-specific storage
        nhl_games = []
        
        # Track when each team last played AND what games are scheduled per day
        team_last_played = {team.team_name: None for team in nhl_teams}
        team_second_last_played = {team.team_name: None for team in nhl_teams}  # Track two days back
        team_games_scheduled = {team.team_name: 0 for team in nhl_teams}
        team_back_to_backs = {team.team_name: 0 for team in nhl_teams}  # Track back-to-back count
        games_by_date = {}  # Track which teams play on each date
        
        # Create season dates using the same range as the calendar for consistency
        season_start = date(season_year, 10, 8)   # Match calendar start
        season_end = date(season_year + 1, 4, 25)  # Match extended calendar end
        
        # Get NHL calendar events for proper break scheduling
        calendar_data = self._create_authentic_nhl_calendar(season_year)
        calendar_events = calendar_data['events']
        
        current_date = season_start
        scheduled_matchups = []
        remaining_matchups = all_matchups.copy()
        
        max_games_per_day = 16  # Maximum NHL games per day (each game uses 2 teams)
        max_back_to_backs_per_team = 25  # More flexible to ensure all games get scheduled
        
        # Track progress and apply progressive flexibility
        days_into_season = 0
        total_season_days = (season_end - season_start).days
        
        # Season pacing - reduce daily games to spread over full calendar
        # Real NHL averages 6.9 games/day over 191 days
        target_daily_games = max(4, min(16, int(1312 / total_season_days * 1.2)))  # Slight buffer
        
        while current_date <= season_end and remaining_matchups:
            days_into_season += 1
            season_progress = days_into_season / total_season_days if total_season_days > 0 else 0
            
            # NHL Calendar breaks - skip certain dates to spread season
            should_skip_date = False
            
            # Check for official NHL break periods
            # Christmas break (Dec 24-26) - reduced games
            if current_date.month == 12 and current_date.day in [24, 25, 26]:
                if len(remaining_matchups) > 200:  # Only skip if plenty of games remain
                    should_skip_date = True
            
            # New Year's Day - reduced games  
            elif current_date.month == 1 and current_date.day == 1:
                if len(remaining_matchups) > 150:
                    should_skip_date = True
                    
            # Check for All-Star break using actual calendar dates
            else:
                # Check if current date is in any official break period
                for break_name, break_period in [
                    ('thanksgiving_break', calendar_events.get('thanksgiving_break')),
                    ('christmas_break', calendar_events.get('christmas_break')),
                    ('all_star_break', calendar_events.get('all_star_break')),
                    ('olympic_break', calendar_events.get('olympic_break'))
                ]:
                    if break_period and isinstance(break_period, tuple) and len(break_period) == 2:
                        break_start, break_end = break_period
                        if break_start <= current_date <= break_end:
                            should_skip_date = True
                            break  # Exit the loop early if we found a break
            
            if should_skip_date:
                current_date += timedelta(days=1)
                continue
            
            # Dynamically adjust daily games based on season progress to spread games
            season_progress = days_into_season / total_season_days if total_season_days > 0 else 0
            
            # IMPROVED Progressive daily limit - more gradual increases to prevent clustering
            remaining_days = max(1, total_season_days - days_into_season)
            needed_daily = len(remaining_matchups) / remaining_days if remaining_days > 0 else target_daily_games
            
            if season_progress < 0.4:  # Early season - conservative scheduling
                daily_limit = max(4, target_daily_games - 1)
            elif season_progress < 0.7:  # Mid season - normal pace  
                daily_limit = target_daily_games
            elif season_progress < 0.85:  # Late season - gradual increase
                daily_limit = min(target_daily_games + 2, int(needed_daily * 1.2))
            else:  # Final stretch - controlled increase with limits
                # Cap at 12 games per day even in final stretch to prevent clustering
                daily_limit = min(12, max(target_daily_games, int(needed_daily * 1.1)))
            
            # MODIFIED EMERGENCY MODE: More restrictive - only for very end of season
            emergency_mode = season_progress > 0.90 and len(remaining_matchups) > 50
            
            # Initialize tracking for this date
            if current_date not in games_by_date:
                games_by_date[current_date] = set()  # Set of team names playing today
            
            daily_games = []
            teams_playing_today = games_by_date[current_date].copy()
            
            # Try to schedule games for today
            attempts = 0
            max_attempts = len(remaining_matchups) * 3  # More attempts to find valid games
            
            while len(daily_games) < daily_limit and remaining_matchups and attempts < max_attempts:
                attempts += 1
                matchup_found = False
                
                for i, (team1, team2, venue) in enumerate(remaining_matchups):
                    team1_name = team1.team_name
                    team2_name = team2.team_name
                    
                    # CRITICAL FIX: Check if EITHER team is already playing today
                    if team1_name in teams_playing_today or team2_name in teams_playing_today:
                        continue  # Skip - one of the teams already has a game today
                    
                    # Relaxed constraints in emergency mode
                    if not emergency_mode:
                        # ENHANCED RULE: Prevent 3+ consecutive games with stricter enforcement
                        yesterday = current_date - timedelta(days=1)
                        day_before_yesterday = current_date - timedelta(days=2)
                        
                        team1_played_yesterday = team_last_played.get(team1_name) == yesterday
                        team1_played_day_before = team_second_last_played.get(team1_name) == day_before_yesterday
                        team2_played_yesterday = team_last_played.get(team2_name) == yesterday
                        team2_played_day_before = team_second_last_played.get(team2_name) == day_before_yesterday
                        
                        # STRONGER 3-consecutive prevention - now includes late season
                        if (team1_played_yesterday and team1_played_day_before) or (team2_played_yesterday and team2_played_day_before):
                            continue  # Would create 3+ consecutive games - forbidden
                        
                        # PROGRESSIVE back-to-back limits with IMPROVED logic
                        is_back_to_back_team1 = team1_played_yesterday
                        is_back_to_back_team2 = team2_played_yesterday
                        
                        # More generous back-to-back limits but stricter consecutive limits
                        progressive_limit = max(22, int(28 - (6 * season_progress)))
                        
                        if is_back_to_back_team1 and team_back_to_backs[team1_name] >= progressive_limit:
                            continue  # Team1 has used up their progressive back-to-back budget
                        if is_back_to_back_team2 and team_back_to_backs[team2_name] >= progressive_limit:
                            continue  # Team2 has used up their progressive back-to-back budget
                    else:
                        # EMERGENCY MODE: Still prevent 3+ consecutive even in emergency
                        yesterday = current_date - timedelta(days=1)
                        day_before_yesterday = current_date - timedelta(days=2)
                        
                        team1_played_yesterday = team_last_played.get(team1_name) == yesterday
                        team1_played_day_before = team_second_last_played.get(team1_name) == day_before_yesterday
                        team2_played_yesterday = team_last_played.get(team2_name) == yesterday
                        team2_played_day_before = team_second_last_played.get(team2_name) == day_before_yesterday
                        
                        # Even in emergency mode, prevent excessive consecutive games
                        if (team1_played_yesterday and team1_played_day_before) or (team2_played_yesterday and team2_played_day_before):
                            continue  # Still prevent 3+ consecutive in emergency mode
                    
                    # This game is valid - schedule it!
                    game_data = {
                        'date': current_date,
                        'home_team': team1 if venue == 'HOME' else team2,
                        'away_team': team2 if venue == 'HOME' else team1,
                        'time': time(19, 0),  # 7:00 PM
                        'league': 'NHL'
                    }
                    
                    daily_games.append(game_data)
                    scheduled_matchups.append((team1, team2, venue))
                    
                    # Update tracking - BOTH teams are now playing today
                    teams_playing_today.add(team1_name)
                    teams_playing_today.add(team2_name)
                    
                    # Update game history tracking
                    team_second_last_played[team1_name] = team_last_played[team1_name]
                    team_second_last_played[team2_name] = team_last_played[team2_name]
                    team_last_played[team1_name] = current_date
                    team_last_played[team2_name] = current_date
                    
                    # Update game counters
                    team_games_scheduled[team1_name] += 1
                    team_games_scheduled[team2_name] += 1
                    
                    # Update back-to-back counters only if not in emergency mode
                    if not emergency_mode or (is_back_to_back_team1 or is_back_to_back_team2):
                        if is_back_to_back_team1:
                            team_back_to_backs[team1_name] += 1
                        if is_back_to_back_team2:
                            team_back_to_backs[team2_name] += 1
                    
                    # Remove this matchup from remaining
                    remaining_matchups.pop(i)
                    matchup_found = True
                    break
                
                # If we couldn't find a valid matchup, try with MORE CAREFUL relaxed rules
                if not matchup_found and season_progress > 0.75:
                    # Try again with carefully relaxed constraints - still prevent excessive consecutive games
                    for i, (team1, team2, venue) in enumerate(remaining_matchups):
                        team1_name = team1.team_name
                        team2_name = team2.team_name
                        
                        # CRITICAL: Still check if EITHER team is already playing today
                        if team1_name in teams_playing_today or team2_name in teams_playing_today:
                            continue  # Skip - one of the teams already has a game today
                        
                        # IMPROVED: Still prevent 3+ consecutive games even in relaxed mode
                        yesterday = current_date - timedelta(days=1)
                        day_before = current_date - timedelta(days=2)
                        
                        team1_played_yesterday = team_last_played.get(team1_name) == yesterday
                        team1_played_day_before = team_second_last_played.get(team1_name) == day_before
                        team2_played_yesterday = team_last_played.get(team2_name) == yesterday
                        team2_played_day_before = team_second_last_played.get(team2_name) == day_before
                        
                        # Still enforce 3-consecutive limit even in relaxed mode (prevents 9-game streaks!)
                        if (team1_played_yesterday and team1_played_day_before) or (team2_played_yesterday and team2_played_day_before):
                            continue  # Would create 3+ consecutive - still forbidden even in relaxed mode
                        
                        # Valid game found with careful relaxed rules
                        game_data = {
                            'date': current_date,
                            'home_team': team1 if venue == 'HOME' else team2,
                            'away_team': team2 if venue == 'HOME' else team1,
                            'time': time(19, 0),  # 7:00 PM
                            'league': 'NHL'
                        }
                        
                        daily_games.append(game_data)
                        scheduled_matchups.append((team1, team2, venue))
                        
                        # Update tracking
                        teams_playing_today.add(team1_name)
                        teams_playing_today.add(team2_name)
                        
                        team_second_last_played[team1_name] = team_last_played[team1_name]
                        team_second_last_played[team2_name] = team_last_played[team2_name]
                        team_last_played[team1_name] = current_date
                        team_last_played[team2_name] = current_date
                        
                        team_games_scheduled[team1_name] += 1
                        team_games_scheduled[team2_name] += 1
                        
                        # Track back-to-backs in relaxed mode too
                        is_back_to_back_team1 = team1_played_yesterday
                        is_back_to_back_team2 = team2_played_yesterday
                        if is_back_to_back_team1:
                            team_back_to_backs[team1_name] += 1
                        if is_back_to_back_team2:
                            team_back_to_backs[team2_name] += 1
                        
                        remaining_matchups.pop(i)
                        matchup_found = True
                        break
                
                # If we still couldn't find a valid matchup, stop trying for today
                if not matchup_found:
                    break
            
            # Store which teams played today for future reference
            games_by_date[current_date] = teams_playing_today
            
            # Add today's games to the NHL schedule
            if daily_games:
                nhl_games.extend(daily_games)
                if current_date.strftime('%Y-%m-%d') not in self.games:
                    self.games[current_date.strftime('%Y-%m-%d')] = []
                self.games[current_date.strftime('%Y-%m-%d')].extend(daily_games)
                
                # Verify no team plays twice today
                team_count_today = {}
                for game in daily_games:
                    home_team = game['home_team'].team_name
                    away_team = game['away_team'].team_name
                    team_count_today[home_team] = team_count_today.get(home_team, 0) + 1
                    team_count_today[away_team] = team_count_today.get(away_team, 0) + 1
                
                # Check for violations
                violations = [team for team, count in team_count_today.items() if count > 1]
                if violations:
                    print(f"🚨 ERROR: Teams playing multiple games on {current_date}: {violations}")
                    
            current_date += timedelta(days=1)
        
        # Report results
        print(f"\n✅ PROPER NHL Scheduling complete!")
        print(f"Total games scheduled: {len(scheduled_matchups)}")
        print(f"Remaining unscheduled: {len(remaining_matchups)}")
        
        # FORCE-SCHEDULE REMAINING: If games couldn't be placed, try harder
        # This ensures all 1,312 matchups (82 per team) get scheduled
        if remaining_matchups:
            print(f"\n🔧 Force-scheduling {len(remaining_matchups)} remaining games...")
            remaining_matchups = self._force_schedule_remaining(
                remaining_matchups, nhl_teams, nhl_games, games_by_date,
                team_last_played, team_second_last_played, team_games_scheduled,
                season_start, season_end
            )
            print(f"After force-schedule: {len(remaining_matchups)} still unscheduled")
        
        # Verify no same-day conflicts across the entire schedule
        print("\n🔍 Verifying no same-day conflicts...")
        for check_date, games in self.games.items():
            teams_on_date = []
            for game in games:
                if hasattr(game, 'get'):  # It's a dictionary
                    teams_on_date.extend([game['home_team'].team_name, game['away_team'].team_name])
            
            # Check for duplicates
            if len(teams_on_date) != len(set(teams_on_date)):
                duplicate_teams = [team for team in set(teams_on_date) if teams_on_date.count(team) > 1]
                print(f"🚨 CONFLICT on {check_date}: {duplicate_teams} play multiple games")
        
        print("✅ Same-day conflict verification complete!")
        
        # Check each team's game count
        for team_name, count in team_games_scheduled.items():
            if count != 82:
                print(f"⚠️ {team_name}: {count} games (target: 82)")
        
        print("✅ Fixed NHL scheduling - NO MORE MULTIPLE GAMES PER DAY!")
        
        # HARD GUARANTEE: No team ever plays 3+ consecutive days.
        # This validation pass catches any violations from any code path
        # and reschedules the middle game of each streak to a nearby open date.
        nhl_games = self._enforce_no_three_in_a_row(nhl_games, nhl_teams)
        
        # Add NHL games to main schedule
        self.schedule.extend(nhl_games)
        print(f"✅ Added {len(nhl_games)} NHL games to main schedule")
    
    def _force_schedule_remaining(self, remaining_matchups, nhl_teams, nhl_games, games_by_date,
                                   team_last_played, team_second_last_played, team_games_scheduled,
                                   season_start, season_end):
        """Force-schedule games that couldn't be placed in the main loop.
        
        Tries every date in the season for each remaining matchup.
        Only enforces hard constraints: no same-day doubleheaders, no 3-in-a-row.
        Returns list of matchups that still couldn't be scheduled (should be empty).
        """
        from datetime import timedelta
        
        still_remaining = []
        
        for team1, team2, venue in remaining_matchups:
            team1_name = team1.team_name
            team2_name = team2.team_name
            scheduled = False
            
            # Try every date in the season
            check_date = season_start
            while check_date <= season_end and not scheduled:
                # Skip if either team already plays this date
                teams_today = games_by_date.get(check_date, set())
                if team1_name in teams_today or team2_name in teams_today:
                    check_date += timedelta(days=1)
                    continue
                
                # Check no-three-in-a-row (hard constraint)
                yesterday = check_date - timedelta(days=1)
                day_before = check_date - timedelta(days=2)
                
                t1_y = team_last_played.get(team1_name) == yesterday
                t1_db = team_second_last_played.get(team1_name) == day_before
                t2_y = team_last_played.get(team2_name) == yesterday
                t2_db = team_second_last_played.get(team2_name) == day_before
                
                if (t1_y and t1_db) or (t2_y and t2_db):
                    check_date += timedelta(days=1)
                    continue
                
                # Valid date found! Schedule the game
                game_data = {
                    'date': check_date,
                    'home_team': team1 if venue == 'HOME' else team2,
                    'away_team': team2 if venue == 'HOME' else team1,
                    'league': 'NHL'
                }
                nhl_games.append(game_data)
                
                # Update tracking
                if check_date not in games_by_date:
                    games_by_date[check_date] = set()
                games_by_date[check_date].add(team1_name)
                games_by_date[check_date].add(team2_name)
                
                # Update last played (need to be careful - this is simplified)
                # For force-schedule, we just update the most recent
                team_last_played[team1_name] = check_date
                team_last_played[team2_name] = check_date
                team_games_scheduled[team1_name] += 1
                team_games_scheduled[team2_name] += 1
                
                scheduled = True
            
            if not scheduled:
                still_remaining.append((team1, team2, venue))
        
        return still_remaining
    
    def _enforce_no_three_in_a_row(self, games, nhl_teams):
        """Ensure no team plays 3+ consecutive days. Fixes violations by moving the middle game.
        
        Args:
            games: List of game dicts with 'date', 'home_team', 'away_team'
            nhl_teams: List of Team objects
            
        Returns:
            The games list with violations fixed (games moved to nearby open dates)
        """
        from collections import defaultdict
        
        def get_team_name(team):
            return team.team_name if hasattr(team, 'team_name') else str(team)
        
        def find_violations(game_list):
            """Find all (team_name, d1, d2, d3) 3-in-a-row violations."""
            team_dates = defaultdict(list)
            for g in game_list:
                d = g['date']
                team_dates[get_team_name(g['home_team'])].append(d)
                team_dates[get_team_name(g['away_team'])].append(d)
            
            violations = []
            for team, dates in team_dates.items():
                dates = sorted(set(dates))
                for i in range(len(dates) - 2):
                    d1, d2, d3 = dates[i], dates[i+1], dates[i+2]
                    if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                        violations.append((team, d1, d2, d3))
            return violations
        
        def teams_playing_on(game_list, check_date):
            """Get set of team names playing on a given date."""
            playing = set()
            for g in game_list:
                if g['date'] == check_date:
                    playing.add(get_team_name(g['home_team']))
                    playing.add(get_team_name(g['away_team']))
            return playing
        
        def would_create_violation(game_list, team_name, new_date):
            """Check if moving a team's game to new_date would create a 3-in-a-row."""
            team_dates = set()
            for g in game_list:
                d = g['date']
                t1 = get_team_name(g['home_team'])
                t2 = get_team_name(g['away_team'])
                if t1 == team_name or t2 == team_name:
                    team_dates.add(d)
            team_dates.add(new_date)
            dates = sorted(team_dates)
            for i in range(len(dates) - 2):
                d1, d2, d3 = dates[i], dates[i+1], dates[i+2]
                if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                    return True
            return False
        
        violations = find_violations(games)
        if not violations:
            print("✅ Schedule validation: no 3-in-a-row violations found")
            return games
        
        print(f"⚠️ Schedule validation: found {len(violations)} 3-in-a-row violations, fixing...")
        
        # Get the full date range of the schedule
        all_dates = sorted(set(g['date'] for g in games))
        if not all_dates:
            return games
        min_date, max_date = all_dates[0], all_dates[-1]
        
        fixed = 0
        # Try to fix each violation by moving the middle game (d2)
        for team_name, d1, d2, d3 in violations:
            # Find the game on d2 involving this team
            target_game = None
            for g in games:
                if g['date'] == d2 and (get_team_name(g['home_team']) == team_name or 
                                        get_team_name(g['away_team']) == team_name):
                    target_game = g
                    break
            
            if not target_game:
                continue
            
            home_name = get_team_name(target_game['home_team'])
            away_name = get_team_name(target_game['away_team'])
            
            # Look for an open date where neither team plays
            # Strategy 1: Nearby dates (14 days)
            # Strategy 2: Wider window (30 days)  
            # Strategy 3: Full season scan
            # Strategy 4: Swap with another game
            moved = False
            
            # Strategy 1-3: Find open date (expanding search)
            for max_offset in [14, 30, 1000]:  # 1000 = full season
                if moved:
                    break
                for offset in range(1, max_offset + 1):
                    if moved:
                        break
                    for new_date in [d2 + timedelta(days=offset), d2 - timedelta(days=offset)]:
                        if new_date < min_date or new_date > max_date:
                            continue
                        if max_offset == 1000 and offset > (max_date - min_date).days:
                            break
                        
                        playing = teams_playing_on(games, new_date)
                        if home_name in playing or away_name in playing:
                            continue
                        
                        # Don't create new violations
                        other_games = [g for g in games if g is not target_game]
                        if would_create_violation(other_games, home_name, new_date):
                            continue
                        if would_create_violation(other_games, away_name, new_date):
                            continue
                        
                        # Safe to move
                        target_game['date'] = new_date
                        fixed += 1
                        moved = True
                        break
                    if max_offset == 1000 and offset > (max_date - min_date).days:
                        break
            
            # Strategy 4: If still not moved, try swapping with another game
            # Find a game on a date where our teams don't play, swap dates
            if not moved:
                for other_game in games:
                    if other_game is target_game:
                        continue
                    other_date = other_game['date']
                    other_home = get_team_name(other_game['home_team'])
                    other_away = get_team_name(other_game['away_team'])
                    
                    # Can't swap if it would cause same-day conflict
                    # (our teams would play on other_date, their teams on d2)
                    playing_on_other = teams_playing_on(games, other_date)
                    playing_on_d2 = teams_playing_on(games, d2)
                    
                    # After swap: our game moves to other_date, their game moves to d2
                    # Check: our teams not already on other_date (we know they're not, we checked)
                    # Check: their teams not already on d2 (excluding our game)
                    other_teams_on_d2 = playing_on_d2 - {home_name, away_name}
                    if other_home in other_teams_on_d2 or other_away in other_teams_on_d2:
                        continue
                    
                    # Check no new violations would be created
                    # (Simplified: just check the four teams involved)
                    temp_games = [g for g in games if g is not target_game and g is not other_game]
                    # Simulate the swap
                    if would_create_violation(temp_games, home_name, other_date):
                        continue
                    if would_create_violation(temp_games, away_name, other_date):
                        continue
                    if would_create_violation(temp_games, other_home, d2):
                        continue
                    if would_create_violation(temp_games, other_away, d2):
                        continue
                    
                    # Safe to swap
                    target_game['date'], other_game['date'] = other_date, d2
                    fixed += 1
                    moved = True
                    print(f"🔄 Swapped games to fix 3-in-a-row for {team_name}")
                    break
            
            if not moved:
                # ABSOLUTE LAST RESORT: This should never happen with 200-day season
                # But if it does, we log it as a critical error
                print(f"🚨 CRITICAL: Could not fix 3-in-a-row for {team_name} on {d2} ({home_name} vs {away_name})")
        
        # Final check
        remaining = find_violations(games)
        if remaining:
            print(f"⚠️ Schedule validation: {len(remaining)} violations remain after fix attempt")
        else:
            print(f"✅ Schedule validation: fixed {fixed} games, no 3-in-a-row violations remain")
        
        return games
    
    def _create_authentic_nhl_matchup_pattern(self, nhl_teams, season_year, rotation_seed):
        """Create authentic NHL matchup assignments using real NHL rotation logic.
        
        Each team plays exactly 82 games:
        - 26 games vs division rivals (7 rivals, some get 4 games, others get 3)
        - 24 games vs same-conference non-division (8 teams × 3 games each)  
        - 32 games vs other conference (16 teams × 2 games each)
        """
        print(f"🔄 Creating {season_year} NHL matchup pattern with rotation seed {rotation_seed}...")
        
        if len(nhl_teams) != 32:
            print(f"⚠️ Warning: Expected 32 NHL teams, got {len(nhl_teams)}")
            return {}
        
        # Organize teams by divisions
        divisions = self._organize_nhl_divisions(nhl_teams)
        
        # Verify division structure
        if len(divisions) != 4 or any(len(teams) != 8 for teams in divisions.values()):
            print("⚠️ Error: Invalid NHL division structure")
            return {}
        
        # Create the seasonal matchup assignments
        matchup_assignments = {}
        
        # Step 1: Division games (26 per team, rotating 4-game vs 3-game assignments)
        self._assign_divisional_games(divisions, matchup_assignments, rotation_seed)
        
        # Step 2: Conference games (24 per team, rotating intensity)  
        self._assign_conference_games(divisions, matchup_assignments, rotation_seed)
        
        # Step 3: Interconference games (32 per team, rotating home/away)
        self._assign_interconference_games(divisions, matchup_assignments, season_year)
        
        # Verify each team has exactly 82 games
        self._verify_matchup_assignments(matchup_assignments, nhl_teams)
        
        return matchup_assignments
    
    def _organize_nhl_divisions(self, nhl_teams):
        """Organize teams into proper NHL divisional structure."""
        divisions = {
            'Eastern_Metropolitan': [],
            'Eastern_Atlantic': [],
            'Western_Central': [],
            'Western_Pacific': []
        }
        
        for team in nhl_teams:
            if team.conference == 'Eastern' and team.division == 'Metropolitan':
                divisions['Eastern_Metropolitan'].append(team)
            elif team.conference == 'Eastern' and team.division == 'Atlantic':
                divisions['Eastern_Atlantic'].append(team) 
            elif team.conference == 'Western' and team.division == 'Central':
                divisions['Western_Central'].append(team)
            elif team.conference == 'Western' and team.division == 'Pacific':
                divisions['Western_Pacific'].append(team)
        
        print(f"📊 NHL Division Structure:")
        for div_name, teams in divisions.items():
            print(f"  {div_name}: {len(teams)} teams")
        
        return divisions
    
    def _assign_divisional_games(self, divisions, matchup_assignments, rotation_seed):
        """Assign divisional games with authentic NHL structure (26 games per team)."""
        print("⚡ Assigning divisional rivalries...")
        
        for div_name, div_teams in divisions.items():
            # Each team plays exactly 26 divisional games against 7 rivals
            # Real NHL: 3 rivals × 4 games + 4 rivals × 3 games = 26 games (rotating annually)
            
            for i, team in enumerate(div_teams):
                if team.team_name not in matchup_assignments:
                    matchup_assignments[team.team_name] = []
                
                # Get division rivals (the other 7 teams)
                division_rivals = [t for t in div_teams if t != team]
                
                # Use rotation seed to determine which teams get more/fewer games
                random.seed(rotation_seed + hash(team.team_name) % 1000)
                random.shuffle(division_rivals)
                
                # Assign 26 total divisional games: start with 2 per rival, then distribute extras
                # 7 rivals × 2 games = 14 base games, need 12 more to reach 26
                
                # Give everyone base 2 games (1 home, 1 away)
                for rival in division_rivals:
                    matchup_assignments[team.team_name].append(('HOME', rival))
                    matchup_assignments[team.team_name].append(('AWAY', rival))
                
                # Distribute 12 extra games among the 7 rivals
                for j in range(12):  # 12 extra games to get from 14 to 26
                    rival = division_rivals[j % len(division_rivals)]
                    # Alternate home/away for extra games
                    venue = 'HOME' if j % 2 == 0 else 'AWAY'
                    matchup_assignments[team.team_name].append((venue, rival))
    
    def _assign_conference_games(self, divisions, matchup_assignments, rotation_seed):
        """Assign same-conference, different-division games (24 per team)."""
        print("🏒 Assigning conference rivalries...")
        
        # Eastern Conference: Metropolitan vs Atlantic (bidirectional)
        self._assign_interdivisional_games(
            divisions['Eastern_Metropolitan'], 
            divisions['Eastern_Atlantic'], 
            matchup_assignments, 
            rotation_seed
        )
        self._assign_interdivisional_games(
            divisions['Eastern_Atlantic'], 
            divisions['Eastern_Metropolitan'], 
            matchup_assignments, 
            rotation_seed
        )
        
        # Western Conference: Central vs Pacific (bidirectional)
        self._assign_interdivisional_games(
            divisions['Western_Central'], 
            divisions['Western_Pacific'], 
            matchup_assignments, 
            rotation_seed
        )
        self._assign_interdivisional_games(
            divisions['Western_Pacific'], 
            divisions['Western_Central'], 
            matchup_assignments, 
            rotation_seed
        )
    
    def _assign_interdivisional_games(self, div1_teams, div2_teams, matchup_assignments, rotation_seed):
        """Assign games between two divisions in same conference (24 games per team)."""
        # Each team needs exactly 24 games against the 8 teams from the other division
        # NHL Pattern: each team plays all 8 opponents exactly 3 times = 24 games
        
        for i, team1 in enumerate(div1_teams):
            if team1.team_name not in matchup_assignments:
                matchup_assignments[team1.team_name] = []
            
            # Each team plays all 8 teams from other division exactly 3 times
            for team2 in div2_teams:
                # 3 games: 2 home, 1 away OR 1 home, 2 away (alternates by rotation)
                random.seed(rotation_seed + hash(team1.team_name + team2.team_name) % 1000)
                if random.randint(0, 1) == 0:
                    # Pattern A: 2 home, 1 away
                    matchup_assignments[team1.team_name].append(('HOME', team2))
                    matchup_assignments[team1.team_name].append(('HOME', team2))
                    matchup_assignments[team1.team_name].append(('AWAY', team2))
                else:
                    # Pattern B: 1 home, 2 away  
                    matchup_assignments[team1.team_name].append(('HOME', team2))
                    matchup_assignments[team1.team_name].append(('AWAY', team2))
                    matchup_assignments[team1.team_name].append(('AWAY', team2))
    
    def _assign_interconference_games(self, divisions, matchup_assignments, season_year):
        """Assign interconference games with rotating home/away (32 per team)."""
        print("🌐 Assigning interconference matchups...")
        
        eastern_teams = divisions['Eastern_Metropolitan'] + divisions['Eastern_Atlantic']
        western_teams = divisions['Western_Central'] + divisions['Western_Pacific']
        
        # Each Eastern team plays each Western team exactly 2 games (16 × 2 = 32 games)
        for east_team in eastern_teams:
            if east_team.team_name not in matchup_assignments:
                matchup_assignments[east_team.team_name] = []
            
            for west_team in western_teams:
                if west_team.team_name not in matchup_assignments:
                    matchup_assignments[west_team.team_name] = []
                
                # 2 games: rotate who hosts more (1 home, 1 away each team)
                # Add one home game for Eastern team
                matchup_assignments[east_team.team_name].append(('HOME', west_team))
                matchup_assignments[west_team.team_name].append(('AWAY', east_team))
                
                # Add one home game for Western team  
                matchup_assignments[west_team.team_name].append(('HOME', east_team))
                matchup_assignments[east_team.team_name].append(('AWAY', west_team))
    
    def _verify_matchup_assignments(self, matchup_assignments, nhl_teams):
        """Verify that each team has exactly 82 games assigned."""
        print("✅ Verifying matchup assignments...")
        
        all_teams_valid = True
        for team in nhl_teams:
            team_games = len(matchup_assignments.get(team.team_name, []))
            if team_games != 82:
                print(f"⚠️ {team.team_name}: {team_games} games (should be 82)")
                all_teams_valid = False
        
        if all_teams_valid:
            print("✅ All 32 teams have exactly 82 games assigned!")
        else:
            print("❌ Matchup assignment validation failed!")
        
        return all_teams_valid
    
    def _create_authentic_nhl_calendar(self, season_year):
        """Create authentic NHL season calendar with flexible scheduling."""
        print(f"📅 Creating {season_year}-{season_year+1} NHL calendar...")
        
        # Flexible NHL season dates - extend season to match real NHL timing
        season_start = date(season_year, 10, 8)   # Start a few days earlier  
        season_end = date(season_year + 1, 4, 25)  # End late April like real NHL
        
        # Define NHL calendar events and restrictions
        calendar_events = {
            'season_start': season_start,
            'season_end': season_end,
            'thanksgiving_break': (
                date(season_year, 11, 24),  # Just Thanksgiving day
                date(season_year, 11, 24)   # Single day break
            ),
            'christmas_break': (
                date(season_year, 12, 24),  # Christmas Eve to Christmas day
                date(season_year, 12, 25)   # Shorter break for more flexibility
            ),
            'all_star_break': (
                date(season_year + 1, 2, 5),   # Typically first week of February
                date(season_year + 1, 2, 11)
            ),
            'olympic_break': (
                # NHL goes dark for the Olympic tournament (Feb 10-24),
                # Olympic years only. None otherwise -- the break checks
                # below skip non-tuple entries.
                date(season_year + 1, 2, 10),
                date(season_year + 1, 2, 24)
            ) if ((season_year + 1) % 4 == 2) else None,
            'trade_deadline': date(season_year + 1, 3, 8),  # First Friday in March
            'entry_draft': date(season_year + 1, 6, 27),   # Late June
            'free_agency': date(season_year + 1, 7, 1)     # July 1st
        }
        
        # Generate schedulable dates with NHL preferences
        available_dates = []
        current_date = season_start
        
        while current_date <= season_end:
            # Check for breaks
            in_break = False
            
            # Check each break period
            for break_name, break_period in [
                ('thanksgiving_break', calendar_events['thanksgiving_break']),
                ('christmas_break', calendar_events['christmas_break']),
                ('all_star_break', calendar_events['all_star_break']),
                ('olympic_break', calendar_events.get('olympic_break'))
            ]:
                if isinstance(break_period, tuple) and len(break_period) == 2:
                    if break_period[0] <= current_date <= break_period[1]:
                        in_break = True
                        break
            
            if not in_break:
                # More flexible NHL scheduling - include most days
                weekday = current_date.weekday()  # 0=Monday, 6=Sunday
                
                # More inclusive day selection for maximum scheduling flexibility
                if weekday == 0:  # Monday - use regularly
                    schedule_probability = 0.7  # Increased from 0.4
                elif weekday in [1, 3, 5]:  # Tuesday, Thursday, Saturday - preferred
                    schedule_probability = 1.0
                elif weekday == 6:  # Sunday - common for afternoon games
                    schedule_probability = 0.95  # Increased from 0.9
                else:  # Wednesday, Friday - use frequently
                    schedule_probability = 0.9  # Increased from 0.8
                
                # Include most dates to provide better scheduling flexibility
                if random.random() < schedule_probability:
                    available_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        print(f"📅 Generated {len(available_dates)} available game dates")
        print(f"🎯 Season: {season_start} to {season_end}")
        
        return {
            'available_dates': available_dates,
            'events': calendar_events,
            'season_info': {
                'start': season_start,
                'end': season_end,
                'year': season_year
            }
        }
    
    def _distribute_nhl_games_realistically(self, matchup_assignments, nhl_teams, season_calendar):
        """Simple, robust NHL scheduling that ABSOLUTELY prevents 3+ consecutive games."""
        print("� Distributing games with STRICT consecutive games prevention...")
        
        available_dates = season_calendar['available_dates']
        season_info = season_calendar['season_info']
        
        # Initialize team tracking for realistic distribution
        team_tracking = {}
        for team in nhl_teams:
            team_tracking[team.team_name] = {
                'games_scheduled': 0,
                'home_games': 0,
                'away_games': 0,
                'back_to_backs': 0,
                'back_to_back_budget': 20,  # More realistic back-to-back budget - NHL teams average 15-20
                'last_game': None,
                'second_last_game': None, 
                'consecutive_games': 0,
                'schedule': []
            }
        
        # Initialize daily game tracking
        daily_game_count = {date: 0 for date in available_dates}
        
        # Track daily capacity (NHL typically schedules 10-15 games per night)
        daily_games = {date: [] for date in available_dates}
        max_games_per_day = 15
        
        # Convert matchup assignments to schedulable games list
        # The key insight: each assignment represents exactly half of one game
        # We need to process only HOME assignments to avoid counting each game twice
        games_to_schedule = []
        total_assignments = sum(len(assignments) for assignments in matchup_assignments.values())
        
        for team_name, assignments in matchup_assignments.items():
            for venue, opponent in assignments:
                if venue == 'HOME':
                    # Only process HOME assignments to create each game exactly once
                    # This team is home, opponent is away
                    home_team = next(t for t in nhl_teams if t.team_name == team_name)
                    away_team = opponent
                    games_to_schedule.append((home_team, away_team))
        
        print(f"📋 Scheduling {len(games_to_schedule)} total games...")
        
        # Schedule games using intelligent distribution with retry logic
        scheduled_games = []
        unscheduled_games = []
        
        # Sort games by priority (division games first, then conference, then interconference)
        def game_priority(game):
            home_team, away_team = game
            if home_team.division == away_team.division:
                return 1  # Division games - highest priority, spread throughout season
            elif home_team.conference == away_team.conference:
                return 2  # Conference games - second priority
            else:
                return 3  # Interconference - can cluster more
        
        games_to_schedule.sort(key=game_priority)
        
        # First pass: Try to schedule all games with strict constraints
        print("🎯 First pass: Scheduling with strict constraints...")
        total_games = len(games_to_schedule)
        for i, (home_team, away_team) in enumerate(games_to_schedule):
            if i % 200 == 0:  # Progress updates
                print(f"  Progress: {i}/{total_games} games ({i/total_games*100:.1f}%)")
            
            # Find optimal date for this matchup
            best_date = self._find_optimal_nhl_game_date(
                home_team, away_team, available_dates, team_tracking, daily_game_count, season_calendar
            )
            
            if best_date:
                # Schedule the game
                scheduled_games.append((best_date, home_team, away_team))
                daily_game_count[best_date] += 1
                
                # Update team tracking
                self._update_nhl_team_tracking(
                    home_team, away_team, best_date, team_tracking
                )
            else:
                # Could not schedule with current constraints - save for retry
                unscheduled_games.append((home_team, away_team))
        
        # Second pass: Retry unscheduled games with shuffled order and relaxed constraints
        if unscheduled_games:
            print(f"⚠️ {len(unscheduled_games)} games remain unscheduled. Retrying with relaxed constraints...")
            
            # Shuffle the unscheduled games to try different ordering
            import random
            random.shuffle(unscheduled_games)
            
            # Retry each unscheduled game with more flexible date selection
            for home_team, away_team in unscheduled_games:
                # Try with more flexible constraints
                best_date = self._find_best_game_date_flexible(
                    home_team, away_team, available_dates, team_tracking, daily_game_count
                )
                
                if best_date:
                    scheduled_games.append((best_date, home_team, away_team))
                    daily_game_count[best_date] += 1
                    
                    self._update_nhl_team_tracking(
                        home_team, away_team, best_date, team_tracking
                    )
                else:
                    print(f"⚠️ Still could not schedule {home_team.team_name} vs {away_team.team_name}")
        
        # Add scheduled games to main schedule
        self.schedule.extend(scheduled_games)
        
        # Print distribution summary
        self._report_schedule_stats_enhanced(team_tracking, nhl_teams)
        
        print(f"✅ Successfully scheduled {len(scheduled_games)} NHL games")
    
    def _find_best_game_date_flexible(self, home_team, away_team, available_dates, team_tracking, daily_game_count):
        """More flexible date finding for games that couldn't be scheduled normally."""
        MAX_DAILY_GAMES = 20  # Relaxed limit
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Check if date is too busy (relaxed constraint)
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check ONLY the critical constraints
            home_valid, home_priority = self._check_team_constraints_flexible(
                home_team, game_date, team_tracking, True
            )
            away_valid, away_priority = self._check_team_constraints_flexible(
                away_team, game_date, team_tracking, False
            )
            
            if home_valid and away_valid:
                combined_priority = home_priority + away_priority
                candidate_dates.append((game_date, combined_priority))
        
        # Return best date (lowest penalty)
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        return None
    
    def _check_team_constraints_flexible(self, team, game_date, team_tracking, is_home_team):
        """More flexible constraint checking that only blocks absolute violations."""
        team_name = team.team_name
        track = team_tracking[team_name]
        
        last_game = track['last_game']
        second_last_game = track['second_last_game']
        
        # HARD CONSTRAINTS (absolute violations only)
        
        # 1. No same-day games (absolute rule)
        scheduled_dates = {scheduled_date for scheduled_date, _, _ in track['schedule']}
        if game_date in scheduled_dates:
            return False, float('inf')
        
        # 2. NEVER allow 3+ consecutive games (non-negotiable)
        if (last_game and second_last_game and
            last_game == game_date - timedelta(days=1) and
            second_last_game == game_date - timedelta(days=2)):
            return False, float('inf')
        
        # ALL OTHER CONSTRAINTS ARE NOW SOFT (penalties only)
        priority = 0
        
        # Back-to-back penalty (but don't hard block unless absolutely necessary)
        is_back_to_back = (last_game and last_game == game_date - timedelta(days=1))
        if is_back_to_back:
            back_to_back_budget = track['back_to_back_budget']
            
            # Only hard block if completely out of budget AND we have other options
            if back_to_back_budget <= 0:
                priority += 1000  # Very high penalty but not infinite
            else:
                priority += 50  # Regular back-to-back penalty
        
        return True, priority
        
        # Print distribution summary
        self._print_scheduling_summary(team_tracking, nhl_teams)
        
        print(f"✅ Successfully scheduled {len(scheduled_games)} NHL games")
    
    def _find_optimal_game_date(self, home_team, away_team, available_dates, team_tracking, daily_games, max_per_day):
        """Find optimal date for a game considering back-to-backs, rest, and balance."""
        best_date = None
        best_score = -1
        
        # Get team tracking info
        home_track = team_tracking[home_team.team_name]
        away_track = team_tracking[away_team.team_name]
        
        # Look through available dates for best fit
        for game_date in available_dates:
            # Skip if day is already at capacity
            if len(daily_games[game_date]) >= max_per_day:
                continue
            
            score = 0
            
            # Check back-to-back situations for both teams
            home_last_game = home_track.get('last_game_date')
            away_last_game = away_track.get('last_game_date')
            
            # Prevent excessive back-to-backs
            would_be_home_b2b = (home_last_game and 
                                (game_date - home_last_game).days == 1)
            would_be_away_b2b = (away_last_game and 
                                (game_date - away_last_game).days == 1)
            
            # Block if either team would exceed back-to-back limit
            if would_be_home_b2b and home_track['back_to_backs'] >= home_track['max_back_to_backs']:
                continue
            if would_be_away_b2b and away_track['back_to_backs'] >= away_track['max_back_to_backs']:
                continue
            
            # Prevent 3+ consecutive games - STRICT enforcement
            if home_track['consecutive_games'] >= 2 and would_be_home_b2b:
                # Home team already has 2+ consecutive games, would make 3+
                continue
            if away_track['consecutive_games'] >= 2 and would_be_away_b2b:
                # Away team already has 2+ consecutive games, would make 3+
                continue
            
            # Prefer adequate rest between games
            if home_last_game:
                home_rest = (game_date - home_last_game).days
                if home_rest >= 2:
                    score += 10  # Good rest
                elif home_rest == 1:
                    score += 2   # Back-to-back (acceptable if under limit)
            else:
                score += 5  # First game
            
            if away_last_game:
                away_rest = (game_date - away_last_game).days
                if away_rest >= 2:
                    score += 10
                elif away_rest == 1:
                    score += 2
            else:
                score += 5
            
            # Prefer balanced monthly distribution
            month = game_date.month
            home_month_games = home_track['monthly_distribution'][month]
            away_month_games = away_track['monthly_distribution'][month]
            
            if home_month_games < 7 and away_month_games < 7:  # Target ~7 games per month
                score += 5
            
            # Prefer moderate daily game count
            daily_count = len(daily_games[game_date])
            if 6 <= daily_count <= 10:  # Sweet spot
                score += 3
            elif daily_count <= 5:
                score += 1
            
            if score > best_score:
                best_score = score
                best_date = game_date
        
        return best_date
    
    def _update_team_tracking_realistic(self, home_team, away_team, game_date, team_tracking):
        """Update team tracking with realistic NHL patterns."""
        home_track = team_tracking[home_team.team_name]
        away_track = team_tracking[away_team.team_name]
        
        # Update game counts
        home_track['games_scheduled'] += 1
        home_track['home_games'] += 1
        away_track['games_scheduled'] += 1
        away_track['away_games'] += 1
        
        # Update monthly distribution
        month = game_date.month
        home_track['monthly_distribution'][month] += 1
        away_track['monthly_distribution'][month] += 1
        
        # Check and update back-to-back status
        for team, track in [(home_team, home_track), (away_team, away_track)]:
            last_game = track.get('last_game_date')
            if last_game and (game_date - last_game).days == 1:
                track['back_to_backs'] += 1
                track['consecutive_games'] += 1  # Increment consecutive games
            else:
                track['consecutive_games'] = 1  # Reset to 1 (this game is the first in new streak)
            
            # Update schedule and last game date
            venue = 'HOME' if team == home_team else 'AWAY'
            opponent = away_team if team == home_team else home_team
            track['schedule'].append((game_date, opponent, venue))
            track['last_game_date'] = game_date
    
    def _print_scheduling_summary(self, team_tracking, nhl_teams):
        """Print summary of scheduling results."""
        print("\n📊 Scheduling Summary:")
        
        back_to_back_counts = [track['back_to_backs'] for track in team_tracking.values()]
        min_b2b = min(back_to_back_counts)
        max_b2b = max(back_to_back_counts)
        avg_b2b = sum(back_to_back_counts) / len(back_to_back_counts)
        
        print(f"   Back-to-backs: {min_b2b}-{max_b2b} (avg: {avg_b2b:.1f}) - NHL target: 7-16")
        
        # Check teams with concerning back-to-back counts
        problematic_teams = [name for name, track in team_tracking.items() 
                           if track['back_to_backs'] > 20]
        if problematic_teams:
            print(f"⚠️ Teams with >20 back-to-backs: {len(problematic_teams)}")
        else:
            print("✅ All teams have realistic back-to-back counts!")
    
    def _add_nhl_special_events(self, calendar_events, season_year):
        """Add NHL special events to the schedule."""
        print("⭐ Adding NHL special events...")
        
        # All-Star Week Events
        all_star_start, all_star_end = calendar_events['all_star_break']
        
        # All-Star Skills Competition
        skills_date = all_star_start + timedelta(days=2)
        self.schedule.append((skills_date, 'NHL_EVENT', {
            'type': 'all_star_skills',
            'title': '⚡ NHL All-Star Skills Competition',
            'description': f'{season_year} NHL All-Star Skills Competition'
        }))
        
        # All-Star Game (ALWAYS the day after Skills Competition)
        game_date = skills_date + timedelta(days=1)  # Fixed: 1 day after Skills, not 3 days after start
        self.schedule.append((game_date, 'NHL_EVENT', {
            'type': 'all_star_game',
            'title': '🌟 NHL All-Star Game',
            'description': f'{season_year} NHL All-Star Game'
        }))
        
        # Trade Deadline
        trade_deadline = calendar_events['trade_deadline']
        self.schedule.append((trade_deadline, 'NHL_EVENT', {
            'type': 'trade_deadline',
            'title': '📈 NHL Trade Deadline',
            'description': 'Final day for trades before playoffs (3 PM ET)'
        }))
        
        # Entry Draft (after season ends)
        draft_date = calendar_events['entry_draft']
        self.schedule.append((draft_date, 'NHL_EVENT', {
            'type': 'entry_draft',
            'title': '🎯 NHL Entry Draft',
            'description': f'{season_year} NHL Entry Draft'
        }))
        
        # Free Agency Opens 
        free_agency_date = calendar_events['free_agency']
        self.schedule.append((free_agency_date, 'NHL_EVENT', {
            'type': 'free_agency',
            'title': '💰 NHL Free Agency Opens',
            'description': 'Unrestricted free agents can sign with any team'
        }))
        
        print(f"✅ Added {5} NHL special events for {season_year} season")
    
    def _verify_complete_schedule_integrity(self):
        """Verify the complete generated schedule meets NHL standards."""
        print("\n🔍 Verifying schedule integrity...")
        
        # Count games by league
        nhl_games = []
        special_events = []
        
        for game_item in self.schedule:
            # Preseason exhibitions never count toward the 82-game slate.
            if isinstance(game_item, dict) and game_item.get('preseason'):
                continue
            # Handle both dictionary and tuple formats
            if isinstance(game_item, dict):
                # Check if it's an NHL game
                if game_item.get('league') == 'NHL':
                    nhl_games.append(game_item)
                # Check if it's a special event
                elif game_item.get('home_team') == 'NHL_EVENT' or 'NHL_EVENT' in str(game_item):
                    special_events.append(game_item)
            elif isinstance(game_item, (tuple, list)) and len(game_item) >= 3:
                # Old format: check for special events
                if game_item[1] == 'NHL_EVENT':
                    special_events.append(game_item)
                else:
                    # Legacy tuple format: only count if both teams are NHL teams
                    # (other leagues like the AHL also use tuples in old saves)
                    if hasattr(game_item[1], 'team_name') and hasattr(game_item[2], 'team_name'):
                        home_lg = getattr(game_item[1], 'league_name', 'National Hockey League')
                        away_lg = getattr(game_item[2], 'league_name', 'National Hockey League')
                        if home_lg == 'National Hockey League' and away_lg == 'National Hockey League':
                            nhl_games.append(game_item)
        
        # Verify NHL teams get exactly 82 games each
        nhl_team_counts = {}
        for game_entry in nhl_games:
            # Handle different schedule formats
            if isinstance(game_entry, dict):
                # New format: dictionary with date, home_team, away_team, etc.
                home_team = game_entry.get('home_team')
                away_team = game_entry.get('away_team')
                league = game_entry.get('league', '')
                
                # Only count NHL games
                if league == 'NHL' and hasattr(home_team, 'team_name') and hasattr(away_team, 'team_name'):
                    home_name = home_team.team_name
                    away_name = away_team.team_name
                    nhl_team_counts[home_name] = nhl_team_counts.get(home_name, 0) + 1
                    nhl_team_counts[away_name] = nhl_team_counts.get(away_name, 0) + 1
            elif isinstance(game_entry, (tuple, list)) and len(game_entry) >= 3:
                # Old format: tuple/list with (date, home_team, away_team)
                game_date, home_team, away_team = game_entry[0], game_entry[1], game_entry[2]
                if hasattr(home_team, 'team_name') and hasattr(away_team, 'team_name'):
                    home_name = home_team.team_name
                    away_name = away_team.team_name
                    nhl_team_counts[home_name] = nhl_team_counts.get(home_name, 0) + 1
                    nhl_team_counts[away_name] = nhl_team_counts.get(away_name, 0) + 1
        
        # Check results
        total_teams = len(nhl_team_counts)
        teams_with_82 = sum(1 for count in nhl_team_counts.values() if count == 82)
        
        print(f"📊 NHL Schedule Verification:")
        print(f"   Total teams: {total_teams}")
        print(f"   Teams with 82 games: {teams_with_82}")
        print(f"   Total NHL games: {len(nhl_games)}")
        _preseason_n = sum(
            1 for g in self.schedule
            if isinstance(g, dict) and g.get('preseason'))
        print(f"   Preseason exhibitions: {_preseason_n}")
        print(f"   Special events: {len(special_events)}")
        
        if teams_with_82 == total_teams and len(nhl_games) == 1312:  # 32 teams * 82 games / 2
            print("✅ PERFECT NHL SCHEDULE!")
            print("   🎯 All teams: exactly 82 games")
            print("   🎯 Total games: exactly 1,312")
            print("   🎯 Seasonal rotation: implemented")
            return True
        else:
            print("❌ Schedule verification failed!")
            if teams_with_82 != total_teams:
                print(f"   ⚠️ {total_teams - teams_with_82} teams don't have 82 games")
            if len(nhl_games) != 1312:
                print(f"   ⚠️ Expected 1,312 total games, got {len(nhl_games)}")
            return False
        
        # Free Agency begins (typically July 1st)
        free_agency_date = date(self.season_year + 1, 7, 1)
        self.schedule.append((free_agency_date, 'NHL_EVENT', {
            'type': 'free_agency',
            'title': '💼 NHL Free Agency Opens',
            'description': 'Unrestricted free agents can sign with any team'
        }))
        
        print(f"✅ Added 5 NHL special events to schedule")
    
    def _find_optimal_nhl_game_date(self, home_team, away_team, available_dates, 
                                  team_tracking, daily_game_count, calendar_info):
        """Find optimal date with strict back-to-back management."""
        MAX_DAILY_GAMES = 16
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Skip if day is too busy
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check team constraints
            home_valid, home_penalty = self._check_nhl_team_constraints(
                home_team, game_date, team_tracking, True, calendar_info
            )
            away_valid, away_penalty = self._check_nhl_team_constraints(
                away_team, game_date, team_tracking, False, calendar_info
            )
            
            if home_valid and away_valid:
                # Calculate total penalty (lower is better)
                total_penalty = home_penalty + away_penalty
                
                # Add home/away balance bonus
                home_balance = self._calculate_nhl_home_away_balance(
                    home_team, team_tracking, True
                )
                away_balance = self._calculate_nhl_home_away_balance(
                    away_team, team_tracking, False
                )
                
                total_penalty += home_balance + away_balance
                candidate_dates.append((game_date, total_penalty))
        
        # Return best date (lowest penalty)
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        # No valid dates found - do NOT schedule rather than violate constraints
        return None
    
    def _check_nhl_team_constraints(self, team, game_date, team_tracking, 
                                  is_home_team, calendar_info):
        """Check NHL scheduling constraints with realistic back-to-back management."""
        track = team_tracking[team.team_name]
        
        # HARD CONSTRAINTS (must pass)
        
        # 1. No same-day games (absolute rule)
        if any(scheduled_date == game_date for scheduled_date, _, _ in track['schedule']):
            return False, float('inf')
        
        # 2. ONLY prevent 3+ consecutive games (this is the key fix)
        last_game = track['last_game']
        second_last_game = track['second_last_game']
        
        if (last_game and second_last_game and 
            last_game == game_date - timedelta(days=1) and
            second_last_game == game_date - timedelta(days=2)):
            return False, float('inf')  # Would create 3 consecutive games - FORBIDDEN
        
        # SOFT CONSTRAINTS (affect priority - lower penalty is better)
        penalty = 0
        
        # Back-to-back management - now more lenient
        is_back_to_back = (track['last_game'] and 
                          track['last_game'] == game_date - timedelta(days=1))
        
        if is_back_to_back:
            # Light penalty for back-to-backs but don't prevent them
            penalty += 10  # Reduced from 25+
            
            # Only start restricting if we have way too many
            if track['back_to_back_budget'] <= 0:
                penalty += 100  # Heavy penalty but not forbidden
        
        # Rest day bonuses (encourage variety)
        if track['last_game']:
            days_rest = (game_date - track['last_game']).days - 1
            if days_rest == 0:      # Back-to-back 
                penalty += 5
            elif days_rest == 1:    # 1 day rest (good)
                penalty -= 5
            elif days_rest == 2:    # 2 days rest (better) 
                penalty -= 10
            elif days_rest >= 3:    # 3+ days rest (optimal)
                penalty -= 15
            elif days_rest > 7:     # Too much rest
                penalty += days_rest - 7
        
        # Trade deadline considerations (schedule easier games late)
        trade_deadline = calendar_info.get('trade_deadline')
        if trade_deadline and game_date > trade_deadline:
            penalty += 5  # Slight penalty for post-deadline games
        
        return True, penalty
    
    def _calculate_nhl_home_away_balance(self, team, team_tracking, is_home_game):
        """Calculate penalty for home/away imbalance (target: 41 home, 41 away)."""
        track = team_tracking[team.team_name]
        
        current_home = track['home_games']
        current_away = track['away_games']
        games_played = track['games_scheduled']
        
        if games_played == 0:
            return 0  # No penalty for first game
        
        # Calculate current ratio
        if is_home_game:
            new_home = current_home + 1
            new_away = current_away
        else:
            new_home = current_home  
            new_away = current_away + 1
        
        total_games = new_home + new_away
        home_ratio = new_home / total_games if total_games > 0 else 0.5
        
        # Target is 50/50 split (41 home, 41 away out of 82)
        target_ratio = 0.5
        imbalance = abs(home_ratio - target_ratio)
        
        # Penalty increases with imbalance
        if imbalance > 0.15:      # More than 15% off
            return 15
        elif imbalance > 0.10:    # More than 10% off
            return 10
        elif imbalance > 0.05:    # More than 5% off
            return 5
        else:
            return 0
    
    def _update_nhl_team_tracking(self, home_team, away_team, game_date, team_tracking):
        """Update team tracking after scheduling an NHL game."""
        for team in [home_team, away_team]:
            track = team_tracking[team.team_name]
            is_home = (team == home_team)
            
            # Check for back-to-back
            is_back_to_back = (track['last_game'] and 
                             track['last_game'] == game_date - timedelta(days=1))
            
            # Update tracking
            track['games_scheduled'] += 1
            if is_home:
                track['home_games'] += 1
            else:
                track['away_games'] += 1
            
            if is_back_to_back:
                track['back_to_backs'] += 1
                track['back_to_back_budget'] -= 1
            
            # Update consecutive games tracking
            if is_back_to_back:
                track['consecutive_games'] += 1
            else:
                track['consecutive_games'] = 1
            
            # Update last game tracking for consecutive games prevention
            track['second_last_game'] = track['last_game']
            track['last_game'] = game_date
            
            # Update schedule
            opponent = away_team if is_home else home_team
            track['schedule'].append((game_date, opponent.team_name, 'HOME' if is_home else 'AWAY'))
    
    def _report_nhl_schedule_compliance(self, nhl_teams):
        """Report NHL schedule compliance and statistics."""
        print("\n🏒 NHL SCHEDULE COMPLIANCE REPORT")
        print("=" * 50)
        
        # Collect statistics (filter out NHL special events)
        team_stats = {}
        for team in nhl_teams:
            team_name = team.team_name
            team_games = [(date, home_team, away_team) for date, home_team, away_team in self.schedule 
                         if home_team != 'NHL_EVENT' and 
                         (home_team.team_name == team_name or away_team.team_name == team_name)]
            
            home_games = sum(1 for _, home_team, _ in team_games if home_team.team_name == team_name)
            away_games = len(team_games) - home_games
            
            # Count back-to-backs
            dates = sorted([date for date, _, _ in team_games])
            back_to_backs = sum(1 for i in range(len(dates)-1) 
                              if (dates[i+1] - dates[i]).days == 1)
            
            team_stats[team_name] = {
                'total_games': len(team_games),
                'home_games': home_games,
                'away_games': away_games, 
                'back_to_backs': back_to_backs
            }
        
        # Summary statistics
        total_games = [stats['total_games'] for stats in team_stats.values()]
        home_games = [stats['home_games'] for stats in team_stats.values()]  
        away_games = [stats['away_games'] for stats in team_stats.values()]
        back_to_backs = [stats['back_to_backs'] for stats in team_stats.values()]
        
        print(f"✅ Teams: {len(nhl_teams)}")
        print(f"✅ Total games: {len(self.schedule)}")
        print(f"✅ Games per team: {sum(total_games)/len(total_games):.1f} avg")
        print(f"✅ Home games per team: {sum(home_games)/len(home_games):.1f} avg")
        print(f"✅ Away games per team: {sum(away_games)/len(away_games):.1f} avg")
        print(f"🎯 Back-to-backs per team: {sum(back_to_backs)/len(back_to_backs):.1f} avg")
        print(f"🎯 Back-to-back range: {min(back_to_backs)}-{max(back_to_backs)} per team")
        
        # Check compliance
        games_82 = sum(1 for games in total_games if games == 82)
        home_away_balanced = sum(1 for i in range(len(home_games)) 
                               if abs(home_games[i] - away_games[i]) <= 2)
        back_to_back_compliant = sum(1 for bb in back_to_backs if 7 <= bb <= 16)
        
        print(f"\n📊 COMPLIANCE CHECK:")
        print(f"   82 games per team: {games_82}/{len(nhl_teams)} teams ✅" if games_82 == len(nhl_teams) else f"   82 games per team: {games_82}/{len(nhl_teams)} teams ❌")
        print(f"   Balanced home/away: {home_away_balanced}/{len(nhl_teams)} teams ✅" if home_away_balanced >= len(nhl_teams) * 0.9 else f"   Balanced home/away: {home_away_balanced}/{len(nhl_teams)} teams ❌")
        print(f"   Back-to-backs 7-16: {back_to_back_compliant}/{len(nhl_teams)} teams ✅" if back_to_back_compliant >= len(nhl_teams) * 0.8 else f"   Back-to-backs 7-16: {back_to_back_compliant}/{len(nhl_teams)} teams 🎯")
    
    def _generate_other_league_schedule(self, league_teams, league_name):
        """Generate schedule for non-NHL leagues with proper same-day conflict prevention."""
        if len(league_teams) < 2:
            return

        # Short league code for schedule entries (matches NHL dict format)
        league_codes = {
            "National Hockey League": "NHL",
            "American Hockey League": "AHL",
        }
        league_code = league_codes.get(league_name, league_name)

        print(f"🏒 Generating schedule for {league_name} ({len(league_teams)} teams)")
        
        # Create all matchups (each team plays each other team twice - home and away)
        matchups = []
        for team1 in league_teams:
            for team2 in league_teams:
                if team1 != team2:
                    matchups.append((team1, team2))
        
        print(f"Created {len(matchups)} total matchups for {league_name}")
        
        # Determine season dates
        season_start = date(self.season_year, 10, 1)
        season_end = date(self.season_year + 1, 3, 31)
        
        # Create available dates (Monday-Saturday)
        available_dates = []
        current_date = season_start
        while current_date <= season_end:
            if current_date.weekday() < 6:  # Monday-Saturday
                available_dates.append(current_date)
            current_date += timedelta(days=1)
        
        print(f"📅 Available dates: {len(available_dates)} for {league_name}")
        
        # Track which teams are playing on which dates to prevent conflicts
        team_schedules = {team.team_name: [] for team in league_teams}
        team_date_sets = {team.team_name: set() for team in league_teams}
        scheduled_games = 0

        def _would_be_three_in_a_row(team_name, game_date):
            """True if scheduling game_date gives the team 3+ consecutive game days."""
            ds = team_date_sets[team_name]
            prev = game_date - timedelta(days=1)
            prev2 = game_date - timedelta(days=2)
            nxt = game_date + timedelta(days=1)
            nxt2 = game_date + timedelta(days=2)
            # game_date + previous two days
            if prev in ds and prev2 in ds:
                return True
            # game_date between two existing game days
            if prev in ds and nxt in ds:
                return True
            # game_date + next two days
            if nxt in ds and nxt2 in ds:
                return True
            return False

        # Schedule games with same-day conflict prevention
        for home_team, away_team in matchups:
            game_scheduled = False

            # Try to find a date where both teams are available
            for game_date in available_dates:
                # Check if either team already has a game on this date
                if (game_date not in team_date_sets[home_team.team_name] and
                    game_date not in team_date_sets[away_team.team_name] and
                    not _would_be_three_in_a_row(home_team.team_name, game_date) and
                    not _would_be_three_in_a_row(away_team.team_name, game_date)):
                    
                    # Schedule the game (dict format matches NHL entries)
                    from datetime import time as dt_time
                    self.schedule.append({
                        'date': game_date,
                        'home_team': home_team,
                        'away_team': away_team,
                        'time': dt_time(19, 0),
                        'league': league_code,
                    })
                    
                    # Mark both teams as busy on this date
                    team_schedules[home_team.team_name].append(game_date)
                    team_schedules[away_team.team_name].append(game_date)
                    team_date_sets[home_team.team_name].add(game_date)
                    team_date_sets[away_team.team_name].add(game_date)
                    
                    scheduled_games += 1
                    game_scheduled = True
                    break
            
            if not game_scheduled:
                print(f"⚠️ Could not schedule {home_team.team_name} vs {away_team.team_name}")
        
        print(f"✅ Scheduled {scheduled_games}/{len(matchups)} games for {league_name}")
        
        # Verify no same-day conflicts
        self._verify_no_same_day_conflicts_for_league(league_teams, league_name)
    
    def _verify_no_same_day_conflicts_for_league(self, league_teams, league_name):
        """Verify that no team in this league plays multiple games on the same day."""
        from collections import defaultdict

        team_names = {team.team_name for team in league_teams}
        team_games_by_date = defaultdict(lambda: defaultdict(int))

        def _team_name(t):
            return t.team_name if hasattr(t, 'team_name') else str(t)

        # Count games per team per date for this league (handles dict and tuple formats)
        for entry in self.schedule:
            if isinstance(entry, dict):
                game_date = entry.get('date')
                home_team, away_team = entry.get('home_team'), entry.get('away_team')
            elif isinstance(entry, (tuple, list)) and len(entry) >= 3:
                game_date, home_team, away_team = entry[0], entry[1], entry[2]
            else:
                continue
            if game_date is None or home_team is None or away_team is None:
                continue
            hn, an = _team_name(home_team), _team_name(away_team)
            if hn in team_names:
                team_games_by_date[game_date][hn] += 1
            if an in team_names:
                team_games_by_date[game_date][an] += 1

        # Check for conflicts
        conflicts_found = False
        for game_date, team_counts in team_games_by_date.items():
            for team_name, game_count in team_counts.items():
                if game_count > 1:
                    print(f"⚠️ CONFLICT: {team_name} has {game_count} games on {game_date} in {league_name}")
                    conflicts_found = True

        if not conflicts_found:
            print(f"✅ No same-day conflicts found in {league_name}")

        return not conflicts_found
        
        if not conflicts_found:
            print(f"✅ No same-day conflicts found in {league_name}")
        
        return not conflicts_found

    def _verify_nhl_schedule_integrity(self):
        """Verify NHL schedule meets all requirements."""
        print("\n🔍 Verifying NHL schedule integrity...")
        
        # Collect team statistics (filter out NHL special events)
        team_schedules = {}
        for game_date, home_team, away_team in self.schedule:
            # Skip NHL special events
            if home_team == 'NHL_EVENT':
                continue
                
            # Track home team
            if home_team.team_name not in team_schedules:
                team_schedules[home_team.team_name] = []
            team_schedules[home_team.team_name].append((game_date, away_team.team_name, 'HOME'))
            
            # Track away team  
            if away_team.team_name not in team_schedules:
                team_schedules[away_team.team_name] = []
            team_schedules[away_team.team_name].append((game_date, home_team.team_name, 'AWAY'))
        
        # Check for violations
        same_day_violations = 0
        back_to_back_violations = 0
        consecutive_violations = 0
        
        for team_name, schedule in team_schedules.items():
            schedule.sort()  # Sort by date
            
            # Check same-day violations
            dates = [game_date for game_date, _, _ in schedule]
            if len(dates) != len(set(dates)):
                same_day_violations += 1
                print(f"❌ {team_name}: Multiple games on same day")
            
            # Check back-to-back and consecutive game violations
            back_to_backs = 0
            max_consecutive = 0
            current_consecutive = 0
            
            for i in range(len(dates)):
                if i > 0:
                    days_diff = (dates[i] - dates[i-1]).days
                    if days_diff == 1:
                        back_to_backs += 1
                        current_consecutive += 1
                    else:
                        max_consecutive = max(max_consecutive, current_consecutive)
                        current_consecutive = 1
                else:
                    current_consecutive = 1
            
            max_consecutive = max(max_consecutive, current_consecutive)
            
            if back_to_backs > 16:  # Allow up to 16 back-to-backs
                back_to_back_violations += 1
            
            if max_consecutive > 3:  # Max 3 consecutive games
                consecutive_violations += 1
        
        # Summary
        total_teams = len(team_schedules)
        print(f"📊 INTEGRITY SUMMARY:")
        print(f"   Same-day violations: {same_day_violations}/{total_teams} teams")
        print(f"   Excessive back-to-backs: {back_to_back_violations}/{total_teams} teams") 
        print(f"   Excessive consecutive games: {consecutive_violations}/{total_teams} teams")
        
        if same_day_violations == 0:
            print("✅ No same-day violations detected")
        if back_to_back_violations <= total_teams * 0.1:  # Allow 10% of teams to exceed
            print("✅ Back-to-back violations within acceptable range")
        if consecutive_violations == 0:
            print("✅ No excessive consecutive game violations")
    
    def _generate_nhl_game_dates(self, start_date, end_date):
        """Generate realistic NHL game dates based on actual NHL scheduling patterns."""
        valid_dates = []
        current_date = start_date
        
        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Monday, 6=Sunday
            
            # NHL typically plays:
            # - Tuesday through Sunday (avoid Monday)
            # - More games on Tue/Thu/Sat/Sun, fewer on Wed/Fri
            if weekday == 0:  # Monday - very rare
                if random.random() < 0.1:  # Only 10% chance
                    valid_dates.append(current_date)
            elif weekday in [1, 3, 5, 6]:  # Tue, Thu, Sat, Sun - primary days
                valid_dates.append(current_date)
            elif weekday in [2, 4]:  # Wed, Fri - secondary days
                if random.random() < 0.7:  # 70% chance
                    valid_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        return valid_dates
    
    def _find_best_game_date(self, home_team, away_team, available_dates, 
                            team_tracking, daily_game_count):
        """Find the best date for a game considering all NHL scheduling constraints."""
        MAX_DAILY_GAMES = 16
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Check if date is too busy
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check constraints for both teams
            home_valid, home_priority = self._check_team_constraints_enhanced(
                home_team, game_date, team_tracking, True  # is_home_team
            )
            away_valid, away_priority = self._check_team_constraints_enhanced(
                away_team, game_date, team_tracking, False  # is_home_team
            )
            
            if home_valid and away_valid:
                # Calculate combined priority (lower is better)
                # Add home/away balance bonus to priority
                home_balance_bonus = self._calculate_home_away_bonus(home_team, team_tracking, True)
                away_balance_bonus = self._calculate_home_away_bonus(away_team, team_tracking, False)
                
                combined_priority = (home_priority + away_priority + 
                                   home_balance_bonus + away_balance_bonus)
                candidate_dates.append((game_date, combined_priority))
        
        # Sort by priority and return best date
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        return None
    
    def _check_team_constraints_enhanced(self, team, game_date, team_tracking, is_home_team):
        """Enhanced constraint checking that's more flexible to allow complete schedule generation."""
        team_name = team.team_name
        track = team_tracking[team_name]
        
        last_game = track['last_game']
        second_last_game = track['second_last_game']
        
        # HARD CONSTRAINTS (must pass)
        
        # 1. No same-day games (absolute rule)
        scheduled_dates = {scheduled_date for scheduled_date, _, _ in track['schedule']}
        if game_date in scheduled_dates:
            return False, float('inf')
        
        # 2. STRICTLY prevent 3+ consecutive games (non-negotiable)
        if (last_game and second_last_game and
            last_game == game_date - timedelta(days=1) and
            second_last_game == game_date - timedelta(days=2)):
            return False, float('inf')
        
        # SOFT CONSTRAINTS (affect priority - lower priority is better)
        priority = 0
        
        # Check back-to-back status
        is_back_to_back = (last_game and last_game == game_date - timedelta(days=1))
        back_to_back_budget = track['back_to_back_budget']
        
        if is_back_to_back:
            # Apply back-to-back penalties but don't hard block (except when budget is exhausted)
            if back_to_back_budget <= 0:
                # Hard block only when completely out of budget
                return False, float('inf')
            
            # Base penalty for back-to-backs
            priority += 25
            
            # Escalating penalty as budget gets lower
            budget_used = 14 - back_to_back_budget
            priority += budget_used * 5
            
            # Season-based penalties
            games_scheduled = track['games_scheduled']
            season_progress = games_scheduled / 82.0
            if season_progress > 0.5:
                priority += 20
            if season_progress > 0.7:
                priority += 40
        
        # Prefer good spacing between games
        if last_game and not is_back_to_back:
            days_since_last = (game_date - last_game).days
            if days_since_last == 2:  # 1 day rest - good
                priority -= 5
            elif days_since_last == 3:  # 2 days rest - optimal
                priority -= 10
            elif days_since_last >= 6:  # Too much rest - penalize lightly
                priority += (days_since_last - 5) * 2
        
        # Home/away balance bonus
        games_scheduled = track['games_scheduled']
        if games_scheduled > 10:  # Only apply after several games scheduled
            home_games = track['home_games']
            away_games = track['away_games']
            current_home_ratio = home_games / games_scheduled if games_scheduled > 0 else 0.5
            
            if is_home_team:
                if current_home_ratio < 0.4:  # Need more home games
                    priority -= 8
                elif current_home_ratio > 0.6:  # Too many home games
                    priority += 8
            else:  # Away game
                if current_home_ratio > 0.6:  # Need more away games
                    priority -= 8
                elif current_home_ratio < 0.4:  # Too many away games
                    priority += 8
        
        return True, priority
    
    def _calculate_home_away_bonus(self, team, team_tracking, is_home_game):
        """Calculate priority bonus/penalty for maintaining home/away balance."""
        track = team_tracking[team.team_name]
        home_games = track['home_games']
        away_games = track['away_games']
        total_games = track['games_scheduled']
        
        # Target: 41 home, 41 away games (82 total)
        if total_games == 0:
            return 0  # No bias for first game
        
        current_home_ratio = home_games / total_games if total_games > 0 else 0.5
        target_ratio = 0.5  # 50/50 split
        
        if is_home_game:
            # If we're scheduling a home game
            new_home_ratio = (home_games + 1) / (total_games + 1)
            if new_home_ratio > 0.6:  # Too many home games
                return 5  # Penalty
            elif current_home_ratio < 0.4:  # Need more home games
                return -3  # Bonus
        else:
            # If we're scheduling an away game  
            new_away_ratio = (away_games + 1) / (total_games + 1)
            if new_away_ratio > 0.6:  # Too many away games
                return 5  # Penalty
            elif current_home_ratio > 0.6:  # Need more away games
                return -3  # Bonus
        
        return 0  # No adjustment needed
    

    
    def _update_team_tracking_after_game(self, home_team, away_team, game_date, team_tracking):
        """Update tracking information after scheduling a game with enhanced back-to-back budget tracking."""
        for team in [home_team, away_team]:
            team_name = team.team_name
            track = team_tracking[team_name]
            is_home_game = (team == home_team)
            
            # Check if this creates a back-to-back
            is_back_to_back = (track['last_game'] and 
                             track['last_game'] == game_date - timedelta(days=1))
            
            # Update tracking
            track['second_last_game'] = track['last_game']
            track['last_game'] = game_date
            track['games_scheduled'] += 1
            
            # Update home/away counts
            if is_home_game:
                track['home_games'] += 1
            else:
                track['away_games'] += 1
            
            # Update back-to-back tracking and budget
            if is_back_to_back:
                track['back_to_backs'] += 1
                track['back_to_back_budget'] -= 1  # Consume one from budget
            
            # Update consecutive games count
            if is_back_to_back:
                track['consecutive_games'] += 1
            else:
                track['consecutive_games'] = 1
            
            # Add to schedule
            opponent = away_team if team == home_team else home_team
            home_away = 'home' if is_home_game else 'away'
            track['schedule'].append((game_date, opponent.team_name, home_away))
    
    def _report_schedule_stats_enhanced(self, team_tracking, teams):
        """Enhanced reporting with home/away balance and back-to-back budget tracking."""
        total_back_to_backs = 0
        total_games = 0
        total_home_games = 0
        total_away_games = 0
        back_to_back_violations = []
        home_away_violations = []
        
        for team in teams:
            track = team_tracking[team.team_name]
            total_back_to_backs += track['back_to_backs']
            total_games += track['games_scheduled']
            total_home_games += track['home_games']
            total_away_games += track['away_games']
            
            # Check back-to-back violations
            if track['back_to_backs'] > 14:
                back_to_back_violations.append(
                    f"{team.team_name}: {track['back_to_backs']} back-to-backs (budget remaining: {track['back_to_back_budget']})"
                )
            
            # Check home/away balance (should be close to 41/41)
            home_games = track['home_games']
            away_games = track['away_games']
            total_team_games = home_games + away_games
            
            if total_team_games > 0:
                home_ratio = home_games / total_team_games
                if abs(home_ratio - 0.5) > 0.15:  # More than 15% imbalance
                    home_away_violations.append(
                        f"{team.team_name}: {home_games}H/{away_games}A ({home_ratio:.1%} home)"
                    )
        
        # Calculate averages
        avg_back_to_backs = total_back_to_backs / len(teams) if teams else 0
        avg_games = total_games / len(teams) if teams else 0
        avg_home_games = total_home_games / len(teams) if teams else 0
        avg_away_games = total_away_games / len(teams) if teams else 0
        
        print(f"✓ Enhanced Schedule Generation Complete:")
        print(f"  Average total games per team: {avg_games:.1f}")
        print(f"  Average home games per team: {avg_home_games:.1f}")
        print(f"  Average away games per team: {avg_away_games:.1f}")
        print(f"  Average back-to-backs per team: {avg_back_to_backs:.1f}")
        
        # Report violations
        if back_to_back_violations:
            print(f"⚠️ Back-to-back violations ({len(back_to_back_violations)}):")
            for violation in back_to_back_violations[:5]:
                print(f"  {violation}")
            if len(back_to_back_violations) > 5:
                print(f"  ... and {len(back_to_back_violations) - 5} more")
        else:
            print(f"✅ All teams within back-to-back limit (≤14)")
        
        if home_away_violations:
            print(f"⚠️ Home/Away balance issues ({len(home_away_violations)}):")
            for violation in home_away_violations[:5]:
                print(f"  {violation}")
        else:
            print(f"✅ All teams have balanced home/away games (~50/50)")
    
    def _report_schedule_stats(self, team_tracking, teams):
        """Legacy reporting method - kept for compatibility."""
        self._report_schedule_stats_enhanced(team_tracking, teams)

    def end_of_season(self):
        """Handles all end-of-season logic like aging players and resetting stats.

        ORDERING CONTRACT (P-2): this call zeroes lg.standings by design for
        the new season. Any points-based offseason logic (coaching carousel,
        awards, waiver snapshots) MUST run BEFORE end_of_season(), or read
        the banked `final_table_snapshot` below -- reading lg.standings after
        the rollover silently returns zeros.
        """
        # Prospect development (EHM on steroids): farm/junior seasons are
        # simulated statistically and evaluated BEFORE aging, so breakout
        # years reshape the growth curve. NHL-roster players keep the
        # existing NHL-stat evaluation; everyone else with real NHL games
        # (call-ups) does too.
        try:
            import prospect_development as _pd
        except Exception:
            _pd = None
        nhl_ids = set()
        ahl_ids = set()
        try:
            for _t in self.teams:
                for _p in _t.roster:
                    nhl_ids.add(_p.id)
                for _p in getattr(_t, "ahl_roster", []):
                    ahl_ids.add(_p.id)
        except Exception:
            pass
        # Snapshot player overalls BEFORE development: the staff
        # breakthrough pass compares against these to find this season's
        # player-development success stories (varying degrees, not just
        # elite leaps).
        _overall_before = {}
        try:
            for _t in self.teams:
                for _p in (list(getattr(_t, "roster", []) or [])
                           + list(getattr(_t, "ahl_roster", []) or [])):
                    try:
                        _overall_before[getattr(_p, "id", None)] = \
                            _p.overall_rating()
                    except Exception:
                        pass
        except Exception:
            pass
        all_players = self.get_all_players()
        for player in all_players:
            try:
                _age = getattr(player, "age", 99) or 99
                _nhl_gp = getattr(getattr(player, "stats", None),
                                  "games_played", 0) or 0
                if _pd is not None and _nhl_gp < 15 and _age < 27 \
                        and player.id not in nhl_ids:
                    # Farm/junior track: simulate the season in an
                    # age-appropriate league, evaluate breakout/bust.
                    _league = "AHL" if player.id in ahl_ids else None
                    _pd.process_prospect_offseason(player, league=_league)
                else:
                    # Dynamic potential: breakout/bust seasons adjust the
                    # ceiling BEFORE stats are wiped and aging is applied.
                    player.update_potential_from_season()
            except Exception:
                pass
            try:
                _on_nhl = player.id in nhl_ids
                # Env eligibility slides with the arc: a late bloomer's
                # situation still matters at 27-28; an early peak's stops
                # mattering sooner. (development_environment_factor itself
                # returns 1.0 past the shifted window, so this is just the
                # gate matching the curve.)
                _env = _pd.development_environment_factor(
                    player, league="NHL" if _on_nhl else None) \
                    if (_pd is not None and (getattr(player, "age", 99) or 99)
                        <= 26 + arc_peak_shift(player)) \
                    else 1.0
            except Exception:
                _env = 1.0
            player.age_one_year(env_factor=_env)
            # Calder archive: record this season's NHL GP for rookie
            # eligibility BEFORE stats are wiped. Only NHL-roster games
            # count -- minor-league seasons never touch rookie status
            # (real rule: AHL/KHL/SHL time doesn't disqualify). Keep the
            # last five seasons; older is irrelevant to the thresholds.
            try:
                _gp_season = int(getattr(getattr(player, "stats", None),
                                         "games_played", 0) or 0)
                _prior = getattr(player, "prior_nhl_gp", None)
                if not isinstance(_prior, list):
                    _prior = []
                    player.prior_nhl_gp = _prior
                _prior.append(_gp_season if player.id in nhl_ids else 0)
                del _prior[:-5]
            except Exception:
                pass
            # ELC slide (CBA 9.1(d)): an 18/19-year-old (Sept-15 signing
            # age) who played fewer than 10 NHL games this season gets
            # an extra contract year. Runs AFTER age_one_year's
            # decrement, so the net effect is the season doesn't burn a
            # year. Only players stamped by finalize_elc_signing carry
            # the slide state -- older saves simply don't slide.
            try:
                _elc_c = getattr(player, "contract", None)
                _elc_on = bool(getattr(_elc_c, "entry_level", False))
                if _elc_on and getattr(_elc_c, "years_remaining", 0) > 0:
                    from salary_cap_system import elc_slide_applies as _slide_ok
                    try:
                        _gp_s = int(getattr(getattr(player, "stats", None),
                                            "games_played", 0) or 0)
                    except Exception:
                        _gp_s = 0
                    if player.id not in nhl_ids:
                        _gp_s = 0
                    _sage_sign = getattr(player, "elc_signing_sept15_age",
                                         None)
                    if _sage_sign is not None and _slide_ok(
                            _sage_sign,
                            getattr(player, "elc_slides_used", 0) or 0,
                            getattr(player, "elc_seasons_completed", 0) or 0,
                            _gp_s,
                            getattr(player, "birth_date", ""),
                            getattr(player, "elc_signed_season", None)):
                        _elc_c.years_remaining = \
                            int(_elc_c.years_remaining) + 1
                        player.elc_slides_used = \
                            int(getattr(player, "elc_slides_used", 0) or 0) + 1
                        try:
                            _nm = getattr(player, "name", "A prospect")
                            _box = getattr(self, "elc_slide_news", None)
                            if not isinstance(_box, list):
                                _box = []
                                self.elc_slide_news = _box
                            _box.append(
                                f"{_nm}'s entry-level contract slides "
                                f"a year (<10 NHL games).")
                        except Exception:
                            pass
                if _elc_on:
                    player.elc_seasons_completed = \
                        int(getattr(player, "elc_seasons_completed", 0) or 0) + 1
            except Exception:
                pass
            # Season-history stints: seal the open NHL stint (or synthesize
            # one from a zero baseline for players who never went through
            # add_player, e.g. league-creation rosters), stamp every stint
            # with this season, and append to season_history -- all BEFORE
            # the stats wipe below. Zero-GP stints are skipped. A fresh
            # anchor is then opened for the new season.
            try:
                _season = int(getattr(self, "season_year", 0) or 0)
                _anchor = getattr(player, "stint_anchor", None)
                if not isinstance(_anchor, dict) or not _anchor.get("team"):
                    try:
                        _cur_team = None
                        for _t in (getattr(self, "teams", None) or []):
                            try:
                                if player in (getattr(_t, "roster", None)
                                              or []):
                                    _cur_team = _t
                                    break
                            except Exception:
                                continue
                        if _cur_team is not None:
                            open_stint(
                                player,
                                _team_abbr_safe(
                                    getattr(_cur_team, "team_name", "")))
                    except Exception:
                        pass
                # Seal the open stint; it lands in _stint_pending alongside
                # any stints sealed mid-season by trades/waivers.
                close_stint(player)
                _pending = getattr(player, "_stint_pending", None)
                _all_stints = [_s for _s in (_pending or [])
                               if isinstance(_s, dict)]
                for _st in _all_stints:
                    try:
                        if int(_st.get("gp", 0) or 0) <= 0:
                            continue
                        _st["season"] = _season
                        _hist = getattr(player, "season_history", None)
                        if not isinstance(_hist, list):
                            _hist = []
                            player.season_history = _hist
                        _hist.append(_st)
                    except Exception:
                        continue
                try:
                    player._stint_pending = []
                except Exception:
                    pass
            except Exception:
                pass
            player.stats = PlayerStats()
            # Fresh stint anchor for the new season, opened AFTER the wipe
            # so the baseline is zeroed stats.
            try:
                _new_team = None
                for _t in (getattr(self, "teams", None) or []):
                    try:
                        if player in (getattr(_t, "roster", None) or []):
                            _new_team = _t
                            break
                    except Exception:
                        continue
                if _new_team is not None:
                    open_stint(
                        player,
                        _team_abbr_safe(
                            getattr(_new_team, "team_name", "")))
            except Exception:
                pass
            # Fresh playoff ledger for the new season (the Conn Smythe race
            # reads it during the playoffs; wiped here with everything else).
            try:
                player.playoff_stats = PlayerStats()
            except Exception:
                pass
            # Fresh AHL ledger too -- farm stats never carry across seasons.
            try:
                player.ahl_stats = PlayerStats()
            except Exception:
                pass
            # Farm-confidence flags reset with the ledger: one buzz note
            # per prospect per season; the live buzz flag is recomputed
            # weekly anyway, but a new season starts everyone quiet.
            try:
                player.ahl_buzz_note_sent = False
                player.ahl_callup_buzz = False
            except Exception:
                pass

        # Coaching success stories: player overall deltas this rollover,
        # split by NHL/AHL roster so AHL coaches get credit for AHL
        # development. Varying degrees: +2 counts, +7 breakouts count
        # more, and crossing the NHL-ready line counts extra.
        try:
            _stories = {}
            for _t in self.teams:
                _tn = getattr(_t, "team_name", "")
                _segs = {}
                for _seg, _plist in (
                        ("nhl", list(getattr(_t, "roster", []) or [])),
                        ("ahl", list(getattr(_t, "ahl_roster", []) or []))):
                    _tw = 0.0
                    _gw = 0.0
                    _best = None  # headline story: biggest single leap
                    for _p in _plist:
                        try:
                            _before = _overall_before.get(
                                getattr(_p, "id", None))
                            if _before is None:
                                continue
                            _after = _p.overall_rating()
                            _delta = int(_after) - int(_before)
                            _age = int(getattr(_p, "age", 99) or 99)
                            if _age > 29 or _delta < 2:
                                continue
                            _w = (1.0 + (1.0 if _delta >= 4 else 0.0)
                                  + (1.0 if _delta >= 7 else 0.0))
                            _pos = getattr(
                                getattr(_p, "primary_position", None),
                                "name", "")
                            _is_g = "GOALIE" in str(_pos)
                            _thresh = 76 if _is_g else 78
                            if _before < _thresh <= _after:
                                _w += 1.0
                            _tw += _w
                            if _is_g:
                                _gw += _w
                            if _best is None or _delta > _best[1]:
                                _pname = (
                                    f"{getattr(_p, 'first_name', '')} "
                                    f"{getattr(_p, 'last_name', '')}").strip()
                                _best = (_pname or "a young player",
                                         _delta, int(_before), _is_g)
                        except Exception:
                            pass
                    _segs[_seg] = {"weight": _tw, "goalie_weight": _gw,
                                   "headline": _best}
                _stories[_tn] = _segs
            self._staff_stories = _stories
        except Exception:
            pass
        # Breakthrough roll: results + stories become a CHANCE at a career
        # leap (never a guarantee), weighted by each coach's stock. Runs
        # before the aging pass so a great season can hold off the age
        # curve for one more run.
        try:
            roll_staff_breakthroughs(self)
        except Exception:
            pass

        # Staff aging and development: young coaches grow with experience,
        # 60+ non-icons regress, icons hold their craft. Staff were
        # previously ageless; every rollover now ages them one year, moves
        # their coaching attributes by age band, and retires the oldest so
        # the coaching carousel keeps turning. Guarded so it can never
        # break the season rollover.
        try:
            _retirees = []

            def _age_staff_list(staff_list, employed, assignment_fn=None):
                for _s in list(staff_list or []):
                    try:
                        _asg = (assignment_fn(_s) if assignment_fn
                                else "nhl") or "nhl"
                    except Exception:
                        _asg = "nhl"
                    try:
                        if age_staff_one_year(_s, employed=employed,
                                             assignment=_asg):
                            _retirees.append(_s)
                    except Exception:
                        pass

            for _t in self.teams:
                _age_staff_list(
                    getattr(_t, "staff", []), True,
                    lambda s: getattr(s, "assignment", "nhl"))
            _age_staff_list(getattr(self, "free_agent_staff", []), False)
            _age_staff_list(getattr(self, "overseas_staff", []), True,
                            lambda s: "overseas")
            for _s in _retirees:
                try:
                    for _t in self.teams:
                        _lst = getattr(_t, "staff", None)
                        if _lst is not None and _s in _lst:
                            _lst.remove(_s)
                    _lst = getattr(self, "free_agent_staff", None)
                    if _lst is not None and _s in _lst:
                        _lst.remove(_s)
                    _lst = getattr(self, "overseas_staff", None)
                    if _lst is not None and _s in _lst:
                        _lst.remove(_s)
                except Exception:
                    pass
            if _retirees:
                _box = getattr(self, "staff_retirement_news", None)
                if not isinstance(_box, list):
                    _box = []
                    self.staff_retirement_news = _box
                for _s in _retirees:
                    try:
                        _nm = (f"{getattr(_s, 'first_name', '')} "
                               f"{getattr(_s, 'last_name', '')}").strip()
                        if not _nm:
                            _nm = "A coach"
                        _role = getattr(getattr(_s, "role", None),
                                        "value", "staffer")
                        _box.append(
                            f"{_nm} ({_role}, age "
                            f"{getattr(_s, 'age', '?')}) has retired.")
                    except Exception:
                        pass
        except Exception:
            pass

        # Junior/college awards for prospects: one lightweight pass over
        # the farm_season data the prospect offseason sim just produced
        # (Memorial Cup, league honors, Hobey Baker, WJC medals). Pure
        # Python, no UI, no per-day cost. Guarded so it can never break
        # the season rollover.
        try:
            import prospect_accolades as _pa
            _ending = int(getattr(self, "season_year", 0) or 0)
            # Isolated RNG: end_of_season callers may rely on the global
            # stream; awards are cosmetic and stay on their own.
            _msgs = _pa.roll_prospect_awards(
                self,
                f"{_ending}-{str(_ending + 1)[2:]}",
                str(_ending + 1),
                rng=random.Random())
            if _msgs:
                _box = getattr(self, "prospect_awards_news", None)
                if not isinstance(_box, list):
                    _box = []
                    self.prospect_awards_news = _box
                _box.extend(str(_m) for _m in _msgs)
        except Exception:
            pass

        self.season_year += 1
        # BUG-016: the entry draft for season_year was held in June, so
        # picks stamped with that year or earlier are dead paper. The
        # draft never consumed them and initialize_draft_picks() only ever
        # adds, so without this they accumulated forever -- tradeable at
        # full value (the AI even asked for expired 1sts). Sweep every
        # club's lists by identity (a traded pick's object can sit in the
        # original club's list per BUG-013).
        try:
            for _t in getattr(self, "teams", None) or []:
                _dp = getattr(_t, "draft_picks", None)
                if not isinstance(_dp, dict):
                    continue
                for _yr in list(_dp.keys()):
                    _before = list(_dp[_yr] or [])
                    _kept = [p for p in _before
                             if int(getattr(p, "year", _yr) or 0) > self.season_year]
                    if len(_kept) != len(_before):
                        if _kept:
                            _dp[_yr] = _kept
                        else:
                            del _dp[_yr]
        except Exception:
            pass
        # Iconic games: only starred entries stay past the season that
        # produced them. Unstarred memories fade as the new season
        # begins; the user's curation is the franchise's permanent
        # memory. Guarded so it can never break the season rollover.
        try:
            from iconic_games import prune_iconic_games
            prune_iconic_games(self)
        except Exception:
            pass
        # Rivalry lifecycle: yearly offseason decay, plus the full
        # review (solidify / simmer / fade / bury) every third season,
        # exactly as designed. Regional hate never fully dies; declared
        # and solidified feuds have floors. Guarded so it can never
        # break the season rollover.
        try:
            import reputation_system as _rs
            _rivs = getattr(self, "rivalries", None)
            if isinstance(_rivs, list) and _rivs:
                _rs.decay_rivalries(_rivs, years=1)
                if int(self.season_year or 0) % 3 == 0:
                    _verdicts = _rs.review_rivalries(_rivs, years=3) or []
                    # Verdicts worth headlining: only real transitions, not
                    # the routine simmer/fade noise.
                    _news = [str(_v.get("text", ""))
                             for _v in _verdicts
                             if str(_v.get("outcome", "")) in
                             ("solidified", "entrenched", "buried", "declared")]
                    if _news:
                        _rbox = getattr(self, "rivalry_review_news", None)
                        if not isinstance(_rbox, list):
                            _rbox = []
                            self.rivalry_review_news = _rbox
                        _rbox.extend(_news)
        except Exception:
            pass
        # Keep the draft-pick future discount anchored to the live season.
        try:
            set_pick_value_anchor_year(self.season_year)
        except Exception:
            pass

        # Advance the salary cap for the new season (2-4% growth).
        # Existing contracts are NOT touched; only new demands scale.
        try:
            cap_sys = self.salary_cap_system
            if cap_sys is None:
                cap_sys = SalaryCapSystem()
                self.salary_cap_system = cap_sys
            new_cap = cap_sys.advance_cap_year(self.season_year)
            for team in self.teams:
                team.salary_cap = new_cap
        except Exception:
            pass

        # Expire buyout dead-cap years that are now in the past
        for team in self.teams:
            hits = getattr(team, 'buyout_cap_hits', None)
            if hits:
                for yr in [y for y in hits if y < self.season_year]:
                    del hits[yr]

        # Expire seeded real-life 2026-27 dead-cap penalties once the league
        # moves past that season; from here the game's own buyout/retention/
        # bonus systems own dead cap.
        try:
            import real_cap_data
            n_exp = real_cap_data.expire_seeded_dead_cap(self, self.season_year)
            if n_exp:
                print(f"Expired seeded real-life dead-cap penalties for {n_exp} teams.")
        except Exception:
            pass
        
        # Tick down retained-salary ledgers: each entry lasts the remaining
        # term of the player's contract at the time of the trade. Expired
        # entries drop off. A player can carry two retentions (two clubs);
        # his retained_amount clears only when NO club still holds him.
        _live_retained_ids = set()
        for team in self.teams:
            ledger = getattr(team, "retained_salary", None)
            if ledger:
                kept = []
                for e in ledger:
                    try:
                        e["seasons_remaining"] = int(e.get("seasons_remaining", 0)) - 1
                    except Exception:
                        e["seasons_remaining"] = 0
                    if e["seasons_remaining"] > 0:
                        kept.append(e)
                        _live_retained_ids.add(e.get("player_id"))
                team.retained_salary = kept
        if _live_retained_ids is not None:
            try:
                for p in self.get_all_players():
                    if (getattr(p, "retained_amount", 0)
                            and getattr(p, "id", None) not in _live_retained_ids):
                        p.retained_amount = 0
                        p.retained_team_name = ""
            except Exception:
                pass

        # Initialize draft picks for upcoming years
        self.initialize_all_draft_picks()

        # Bank the final table before the reset: waiver priority runs on
        # last season's final standings until November 1 (waiver_logic).
        try:
            import waiver_logic as _wl
            _wl.snapshot_final_standings(self)
        except Exception:
            pass

        # P-2: bank the FULL final table (W/L/OTL/Points per club) before
        # initialize_standings() zeroes it. The waiver snapshot above keeps
        # points/games only; this is the general-purpose copy any other
        # offseason consumer can read after the rollover. Old-save safe:
        # plain attribute, read via getattr with a default.
        try:
            self.final_table_snapshot = bank_final_table(self.standings)
            self.final_table_season = str(getattr(self, "season_year", "") or "")
        except Exception:
            pass

        # M-NTC lists live and die with the contract: learned entries
        # persist across seasons and only clear when the player signs a
        # new deal (trade_engine.refresh_mntc_lists).
        try:
            import trade_engine as _te_mntc
            _te_mntc.refresh_mntc_lists(self)
        except Exception:
            pass

        self.initialize_standings()
        # Team-level records must reset too (initialize_standings only
        # zeroes the standings dict; without this team.wins/losses
        # accumulate across seasons in a continuing career).
        for _t in self.teams:
            try:
                _t.reset_season_record()
            except Exception:
                pass
        self.generate_schedule(season_year=self.season_year)

        # Part 5: drafted-prospect rights lifecycle (unsigned rights expiry,
        # CHL draft re-entries, holdout warnings, leaving junior). Guarded so
        # a data bug here can never crash the season rollover.
        try:
            self._rollover_draft_rights()
        except Exception:
            pass

        # Preseason media poll: snapshot every club's predicted finish from
        # opening-night roster strength. The season-review card grades each
        # team against this (the "vs media expectations" axis). Rosters are
        # final here -- draft and rights rollover are done above. Guarded so
        # it can never break the rollover; seasons that predate this snapshot
        # simply grade against the board mandate instead.
        try:
            from season_review import snapshot_preseason_predictions
            snapshot_preseason_predictions(self)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Part 5: unsigned drafted-prospect rights lifecycle
    #
    # Simplified real-world model:
    #   CHL (OHL/QMJHL/WHL)   -> rights 2 years; unsigned + still
    #                             draft-eligible (age <= 20) re-enters the
    #                             next draft, otherwise UFA.
    #   NCAA                   -> rights 4 years, then UFA.
    #   Europe (everyone else) -> rights 4 years, then UFA.
    #   Any                    -> 5 full unsigned years post-draft -> retired.
    # Rights stamping normally happens at draft time in the draft UI
    # (windows.py DraftView.execute_pick, owned by another worker). As a
    # backstop, _rollover_draft_rights also stamps any prospect found in a
    # team's prospects list that has no rights yet (drafted_year == 0) and
    # is young enough to be a recent pick (age <= 21), inferring the draft
    # year as the current season year. "Unsigned" == rights_team != "";
    # signed prospects have their rights fields cleared and are skipped.
    # ------------------------------------------------------------------
    _RIGHTS_CHL_LEAGUES = _CHL_JUNIOR_LEAGUES
    _RIGHTS_JUNIOR_LEAGUES = ("OHL", "WHL", "QMJHL", "USHL", "BCHL", "AJHL",
                              "SJHL", "MJHL", "NOJHL", "OJHL", "CCHL")
    # Where unsigned prospects can land when they age out of junior (a
    # sensible minors/European club by nationality; no full contract sim).
    _RIGHTS_LEAVE_JUNIOR = {
        "russia": ("KHL", "MHL"),
        "sweden": ("SHL", "HockeyAllsvenskan"),
        "finland": ("Liiga", "Liiga"),
        "czech": ("Czech Extraliga", "Czech Extraliga"),
        "slovakia": ("Slovak Extraliga", "Slovak Extraliga"),
        "germany": ("DEL", "DEL"),
        "switzerland": ("NL", "NL"),
        "united states": ("AHL", "ECHL"),
        "usa": ("AHL", "ECHL"),
    }

    def stamp_draft_rights(self, player, team_name, draft_year):
        """Stamp draft rights on a freshly drafted prospect.

        Intended to be called at draft time by the draft UI layer; the
        season rollover backstop also calls this for unstamped prospects
        it finds in team.prospects. rights_type comes from the player's
        junior league: OHL/QMJHL/WHL -> CHL, NCAA -> NCAA (4-year
        rights), anything else -> EUROPE (4-year rights).

        New CBA (2026): CHL rights now match the NCAA/European scale --
        4 years for 18-year-olds, 3 years for 19-year-olds (was a flat
        2 years). Overagers keep 2.
        """
        try:
            jl = (getattr(player, "junior_league", "") or "").strip().upper()
            if jl in self._RIGHTS_CHL_LEAGUES:
                _dage = int(getattr(player, "age", 18) or 18)
                _dur = 4 if _dage <= 18 else (3 if _dage == 19 else 2)
                rtype, duration = "CHL", _dur
            elif jl == "NCAA":
                rtype, duration = "NCAA", 4
            else:
                rtype, duration = "EUROPE", 4
            player.rights_team = team_name
            player.drafted_year = int(draft_year)
            player.rights_type = rtype
            player.rights_expiry_year = int(draft_year) + duration
            if not getattr(player, "playing_where", ""):
                player.playing_where = getattr(player, "junior_league", "") or "Junior"
            player.draft_reentry = False
        except Exception:
            pass

    def finalize_elc_signing(self, team, player, salary, years,
                             signing_bonus=0, performance_bonus=0,
                             ahl_salary=None):
        """Sign an unsigned drafted prospect to explicit ELC terms.

        The shared finalizer for every ELC path: the auto-sign
        (sign_drafted_prospect computes the terms) and the negotiated
        offer (the ELC negotiation view / handle_elc_offer). One
        rulebook: rights-holder check, ELC eligibility (Sept-15 signing
        age through the 3/2/1 table -- 25+ is NOT ELC-eligible and is
        refused), Contract creation (two-way, with signing + performance
        bonuses, all capped to the CBA limits), rights consumption, and
        eligibility-based assignment (junior-aged CHL -> junior, everyone
        else -> AHL). Returns True on success.

        Stamps the slide-rule state (signing Sept-15 age, slides used)
        and preserves the draft history (drafted_by, signing season)
        before the rights fields are cleared.
        """
        try:
            from salary_cap_system import (
                elc_years_for_age, elc_max_annual_comp,
                elc_minor_salary_max, league_minimum_salary,
                ELC_SIGNING_BONUS_PCT, ELC_PERF_BONUS_MAX)
            try:
                from draft_generator import age_on_sept15 as _age_on_sept15
            except Exception:
                _age_on_sept15 = None
            team_name = team if isinstance(team, str) else getattr(team, "team_name", "")
            team_obj = None
            if isinstance(team, str):
                for t in (getattr(self, "teams", []) or []):
                    if getattr(t, "team_name", "") == team:
                        team_obj = t
                        break
            else:
                team_obj = team
            if team_obj is None:
                return False
            prospects = getattr(team_obj, "prospects", []) or []
            if player not in prospects:
                return False
            # Only the rights holder can sign; already-signed prospects
            # (rights cleared) are skipped. The contract check is explicit:
            # a prospect who somehow holds both is never re-signed. Note
            # every Player is born with a placeholder Contract
            # (years_remaining == 0), so "has a contract" means a LIVE
            # deal -- the placeholder is not a signing.
            _c = getattr(player, "contract", None)
            if _c is not None and int(getattr(_c, "years_remaining", 0) or 0) > 0:
                return False
            rights_team = getattr(player, "rights_team", "") or ""
            if not rights_team or rights_team != getattr(team_obj, "team_name", ""):
                return False
            season_year = int(getattr(self, "season_year", 0) or 0) or None
            # CBA 9.2: "age" for Article 9 is the player's age on
            # September 15 of the signing year -- not his current age.
            _sage = None
            if _age_on_sept15 is not None:
                try:
                    _sage = _age_on_sept15(getattr(player, "birth_date", ""),
                                           season_year or 2026)
                except Exception:
                    _sage = None
            if _sage is None:
                _sage = int(getattr(player, "age", 20) or 20)
            # The 3/2/1 table is canonical: it overrides whatever term
            # was passed in, and 0 years means not ELC-eligible (25+).
            years = elc_years_for_age(_sage)
            if years <= 0:
                return False
            # Cap the money to the CBA limits (fail closed -- a forged
            # over-max offer never becomes a contract).
            _max_annual = elc_max_annual_comp(season_year)
            _min_annual = league_minimum_salary(season_year)
            salary = int(salary or 0)
            signing_bonus = int(signing_bonus or 0)
            performance_bonus = int(performance_bonus or 0)
            if not (_min_annual <= salary <= _max_annual):
                return False
            if signing_bonus < 0 or \
                    signing_bonus > int(ELC_SIGNING_BONUS_PCT * salary):
                return False
            if not (0 <= performance_bonus <= ELC_PERF_BONUS_MAX):
                return False
            # 9.3(a): base salary + signing bonus (+ games-played
            # bonuses, not modeled) may not exceed the max annual
            # compensation. Schedule-A performance bonuses are capped
            # separately and are NOT part of this aggregate.
            if salary + signing_bonus > _max_annual:
                return False
            _draft_year = getattr(player, "drafted_year", 0) or 0
            _minor_max = elc_minor_salary_max(_draft_year or season_year)
            if ahl_salary is None:
                try:
                    from player_generator import PlayerGenerator
                    _s, _y, _tw, ahl_salary = \
                        PlayerGenerator().determine_contract_info(player, "NHL_ROOKIE")
                except Exception:
                    ahl_salary = None
            ahl_salary = int(ahl_salary or _minor_max)
            ahl_salary = max(0, min(ahl_salary, _minor_max))
            player.contract = Contract(salary=salary,
                                       years_remaining=int(years),
                                       two_way=True,
                                       ahl_salary=ahl_salary,
                                       signing_bonus=signing_bonus,
                                       performance_bonus=performance_bonus,
                                       entry_level=True)
            # Slide-rule state (CBA 9.1(d)): the rollover reads the
            # signing Sept-15 age, the used-slide count, and the seasons
            # completed under this SPC.
            player.elc_signing_sept15_age = int(_sage)
            player.elc_slides_used = 0
            player.elc_seasons_completed = 0
            player.elc_signed_season = int(season_year or 0) or None
            # Rights consumed: the prospect is now signed. drafted_year is
            # cleared too -- it now means "drafted but never signed", which
            # the five-year unsigned-retirement scan relies on. The draft
            # history itself is preserved first (drafted_by / signing
            # season / pick stay on the player).
            player.drafted_by = rights_team
            player.rights_team = ""
            player.rights_expiry_year = 0
            player.rights_type = ""
            player.drafted_year = 0
            player.camp_invite = False
            # Assignment on signing (real life / Eastside): a signed
            # prospect goes where he's eligible. CHL under-20s go back
            # to junior (except a 19-year-old first-rounder, who may
            # stay up in the AHL -- the user can promote him after).
            # Signing an NHL deal ends NCAA eligibility, so an
            # ex-college player can only go to the minors or the NHL,
            # never back to college. Everyone else starts in the AHL.
            _track = junior_track_of(player)
            if _track == "CHL" and _sage < 20:
                player.playing_where = junior_assignment_label(player)
            else:
                player.playing_where = "AHL"
            # Rivalry lifecycle: a signing is a transfer. ELC kids almost
            # never carry ledger history, but the chokepoint stays uniform
            # -- every signing path funnels through on_player_transfer.
            try:
                from reputation_system import on_player_transfer as _opt
                _rivs = getattr(self, "rivalries", None)
                if isinstance(_rivs, list):
                    _opt(_rivs, player, from_team=None, to_team=team_obj)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def sign_drafted_prospect(self, team, player):
        """Sign an unsigned drafted prospect to an ELC-like deal.

        Reuses the existing contract-creation path
        (player_generator.PlayerGenerator.determine_contract_info, which
        routes age <= 24 prospects through the ENTRY_LEVEL gate with the
        real 3/2/1 signing-age term and the new-CBA band). No new cap
        logic: the deal is a plain Contract assignment, and cap reads it
        through the existing systems. On success the rights fields are
        cleared (the prospect is no longer "unsigned") and playing_where
        is set by real eligibility: junior-aged CHL prospects return to
        junior, ex-college players go to the AHL (an NHL deal ends NCAA
        eligibility -- never back to college), everyone else to the AHL;
        returns True. Returns False when the prospect isn't this team's
        unsigned rights-holder asset, or when he isn't ELC-eligible
        (25+).
        """
        try:
            from player_generator import PlayerGenerator
            salary, years, two_way, ahl_salary = \
                PlayerGenerator().determine_contract_info(player, "NHL_ROOKIE")
        except Exception:
            salary, years, two_way, ahl_salary = 925000, 3, True, 85000
        return self.finalize_elc_signing(team, player, salary, years,
                                         ahl_salary=ahl_salary)

    def invite_prospect_to_camp(self, team_name, player):
        """Invite an unsigned drafted prospect to development camp.

        Sets camp_invite=True. Deliberately gives NO attribute boost:
        prospect_development.process_prospect_offseason simulates a whole
        season (stats, grade evaluation) -- far too heavy for a camp
        invite. Returns a news string for the UI layer.
        """
        try:
            player.camp_invite = True
            name = getattr(player, "full_name", "Prospect")
        except Exception:
            name = "Prospect"
        return (f"{name} has been invited to {team_name}'s development camp.")

    def _rollover_draft_rights(self, reference_year=None):
        """Advance the unsigned drafted-prospect rights lifecycle one season.

        Two call paths, same math:
          * Draft day (main.py): called BEFORE the draft is held, with
            reference_year = the draft year about to be held. Expiring CHL
            prospects who are still eligible re-enter THAT draft (the class
            generator folds league.draft_reentries in).
          * League.end_of_season (backstop): reference_year is None and the
            already-incremented season_year is used; the next draft is then
            season_year + 1.
        A per-draft-year guard keeps the two paths from running twice for
        the same offseason.
        News strings are collected on league.rights_news for the UI layer
        to post.
        """
        season_year = int(getattr(self, "season_year", 0) or 0)
        if not season_year:
            return
        # The upcoming draft, relative to which expiry/re-entry is computed.
        next_draft = int(reference_year) if reference_year else season_year + 1
        # Expiry math keys off the season the upcoming draft belongs to:
        # on draft day season_year is the season just ending (draft year -
        # 1), so reference_year restores the draft-relative count.
        base_year = int(reference_year) if reference_year else season_year
        # One rollover per ending season: the draft-day call (base_year =
        # draft year) and the end_of_season backstop (base_year = draft
        # year, post-increment) share the key base_year - 1.
        _cycle = base_year - 1
        if getattr(self, "_rights_rolled_for", None) == _cycle:
            return
        news = getattr(self, "rights_news", None)
        if not isinstance(news, list):
            news = []
            self.rights_news = news
        reentries = getattr(self, "draft_reentries", None)
        if not isinstance(reentries, list):
            reentries = []
            self.draft_reentries = reentries
        for team in (getattr(self, "teams", []) or []):
            team_name = getattr(team, "team_name", "Team")
            prospects = list(getattr(team, "prospects", []) or [])
            for player in prospects:
                try:
                    self._rollover_one_prospect_rights(player, team, team_name,
                                                       base_year, next_draft,
                                                       news, reentries)
                except Exception:
                    continue

        # Five unsigned years -> retirement, for players whose rights already
        # expired. The per-prospect retirement branch above only sees players
        # still holding rights; an expired prospect leaves the prospect pool
        # (UFA) at year 2/4, so without this scan he would sit in the free
        # agent pool forever. drafted_year > 0 means "drafted but never
        # signed" (sign_drafted_prospect clears it); never-drafted free
        # agents have drafted_year == 0 and are skipped.
        try:
            fa_pool = getattr(self, "free_agents", None)
            if isinstance(fa_pool, list):
                for player in list(fa_pool):
                    try:
                        dy = int(getattr(player, "drafted_year", 0) or 0)
                        if not dy:
                            continue
                        if getattr(player, "rights_team", ""):
                            continue
                        if base_year - dy < 5:
                            continue
                        fa_pool.remove(player)
                        player.team_name = "Retired"
                        player.drafted_year = 0
                        news.append(
                            f"{getattr(player, 'full_name', 'Prospect')} has "
                            f"retired after five unsigned years since being "
                            f"drafted.")
                    except Exception:
                        continue
        except Exception:
            pass
        self._rights_rolled_for = _cycle

    def _rollover_one_prospect_rights(self, player, team, team_name,
                                      base_year, next_draft, news, reentries):
        # Backstop stamp: draft-time stamping lives in the draft UI layer
        # (another worker owns it). Any prospect in a team's prospects list
        # that has no rights yet and is young enough to be a recent pick
        # gets stamped now, inferring the draft year as the current season
        # year.
        drafted_year = int(getattr(player, "drafted_year", 0) or 0)
        if drafted_year == 0 and not getattr(player, "rights_team", ""):
            # Signed prospects (hold a live deal) are never "unsigned rights"
            # assets -- the stamp is only for unsigned draftees the draft
            # UI failed to stamp. Every Player carries a placeholder
            # Contract (years_remaining == 0); only a live deal counts.
            _bc = getattr(player, "contract", None)
            if _bc is not None and int(getattr(_bc, "years_remaining", 0) or 0) > 0:
                return
            if int(getattr(player, "age", 99) or 99) <= 21:
                self.stamp_draft_rights(player, team_name, base_year)
                news.append(
                    f"{getattr(player, 'full_name', 'Prospect')} ({team_name}) "
                    f"rights registered for the {base_year} draft class.")
            else:
                # Older unstamped prospect: pre-dates the rights system,
                # leave alone (not "unsigned" under this system).
                return
        drafted_year = int(getattr(player, "drafted_year", 0) or 0)
        if not drafted_year:
            return
        # "Unsigned" == the rights are still held. Signed prospects have
        # their rights fields cleared (sign_drafted_prospect) and skip.
        if not getattr(player, "rights_team", ""):
            return
        name = getattr(player, "full_name", "Prospect")
        age = int(getattr(player, "age", 99) or 99)
        rtype = getattr(player, "rights_type", "") or "EUROPE"
        years_unsigned = base_year - drafted_year
        rights_expiry = int(getattr(player, "rights_expiry_year", 0) or 0)

        def _clear_rights():
            player.rights_team = ""
            player.rights_expiry_year = 0
            player.rights_type = ""
            player.camp_invite = False

        # Retirement: five full unsigned years post-draft, any track.
        if years_unsigned >= 5:
            if player in getattr(team, "prospects", []):
                team.prospects.remove(player)
            player.team_name = "Retired"
            _clear_rights()
            news.append(
                f"{name} ({team_name}) has retired after five unsigned "
                f"years; his draft rights lapse.")
            return

        # CHL: rights last 4 years (drafted at 18) or 3 years (drafted at
        # 19) under the new CBA -- the scan keys off the stamped
        # rights_expiry_year, not a hardcoded 2. Still draft-eligible ->
        # re-enters the next draft; otherwise becomes an unrestricted
        # free agent. Eligibility is the exact NHL rule
        # (is_draft_eligible): NA prospects age out at 20, Europeans at
        # 22 (a 23-year-old never re-enters -- UFA, directly signable).
        # With 4-year CHL rights a prospect usually ages out before his
        # rights lapse, so CHL re-entry is now rare -- as in real life.
        # next_draft is the upcoming draft: on draft day it is the draft
        # about to be held (so re-entries land in this year's class); in
        # the end_of_season backstop it is season_year + 1.
        _chl_expired = (base_year >= rights_expiry) if rights_expiry > 0 \
            else (years_unsigned >= 2)
        if rtype == "CHL" and _chl_expired:
            _eligible = False
            try:
                from draft_generator import is_draft_eligible as _elig
                _eligible = bool(_elig(
                    getattr(player, "birth_date", ""),
                    getattr(player, "nationality", ""),
                    next_draft))
            except Exception:
                _eligible = age <= 20
            if _eligible:
                player.draft_reentry = True
                # Real NHL rule: the club that held (and lost) his rights may
                # not re-select him in the immediate re-entry draft.
                player.draft_reentry_from = team_name
                # The old rights die here: he re-enters as a clean prospect
                # and gets fresh rights stamped when (and if) he's drafted
                # again. A stale rights_team would make him an immortal FA
                # (or double-count the rights holder) in later cycles.
                _clear_rights()
                if player in getattr(team, "prospects", []):
                    team.prospects.remove(player)
                if player not in reentries:
                    reentries.append(player)
                news.append(
                    f"{name} ({team_name}) re-enters the draft after his "
                    f"CHL rights expired unsigned.")
            else:
                _clear_rights()
                if player in getattr(team, "prospects", []):
                    team.prospects.remove(player)
                player.team_name = "Free Agent"
                _fa = getattr(self, "free_agents", None)
                if isinstance(_fa, list) and player not in _fa:
                    _fa.append(player)
                news.append(
                    f"{name} ({team_name}) becomes an unrestricted free "
                    f"agent after his CHL rights expired unsigned.")
            return

        # NCAA / Europe: rights last 4 years, then UFA.
        if rtype in ("NCAA", "EUROPE") and years_unsigned >= 4:
            _clear_rights()
            if player in getattr(team, "prospects", []):
                team.prospects.remove(player)
            player.team_name = "Free Agent"
            _fa = getattr(self, "free_agents", None)
            if isinstance(_fa, list) and player not in _fa:
                _fa.append(player)
            news.append(
                f"{name} ({team_name}) becomes an unrestricted free agent "
                f"after his {rtype} rights expired unsigned.")
            return

        # Leave junior: unsigned, age 20+, still playing in a junior
        # league -> small yearly chance to take a minors/European club
        # deal. He stays signable by the rights holder (rights untouched);
        # only playing_where changes. Deterministic per (year, player id)
        # so replays agree without touching the global RNG.
        where = (getattr(player, "playing_where", "") or "").strip().upper()
        if age >= 20 and where in self._RIGHTS_JUNIOR_LEAGUES:
            prng = random.Random((base_year * 1000003) ^ int(getattr(player, "id", 0) or 0))
            if prng.random() < 0.25:
                nat = (getattr(player, "nationality", "") or "").lower()
                dest = None
                for key, clubs in self._RIGHTS_LEAVE_JUNIOR.items():
                    if key in nat:
                        dest = clubs[0] if clubs else None
                        break
                if dest is None:
                    dest = "AHL" if prng.random() < 0.8 else "ECHL"
                player.playing_where = dest
                news.append(
                    f"{name} ({team_name}) has left junior to play for a "
                    f"{dest} club; his rights are still held.")

        # Holdout warning: high-reputation prospect, unsigned, within one
        # year of rights expiry OR within one year of the 5-year
        # retirement cliff.
        rep = int(getattr(player, "reputation", 0) or 0)
        if rep >= 70 and getattr(player, "rights_team", ""):
            yrs_to_expiry = rights_expiry - base_year
            yrs_to_retire = 5 - years_unsigned
            if yrs_to_expiry <= 1 or yrs_to_retire <= 1:
                if yrs_to_retire <= 1:
                    news.append(
                        f"{name} ({team_name}) is considering retirement "
                        f"with his unsigned rights about to lapse.")
                else:
                    news.append(
                        f"{name} ({team_name}) may hold out -- his draft "
                        f"rights expire after this season.")

    def initialize_all_draft_picks(self):
        """Initialize draft picks for all teams for the next few years."""
        # The next live draft is always season_year+1 (this season's draft
        # was already held in June). Dealing season_year picks gives every
        # team dead paper -- BUG-016.
        # Seven drafts out: picks that far ahead are tradeable (real clubs
        # deal that far out), valued with a per-year discount, and both
        # the protection roll-forward and offer-sheet compensation
        # (up to four 1sts, walking forward through the signing club's
        # own upcoming picks) reach as far as picks exist.
        future_years = [self.season_year + 1 + i for i in range(7)]
        
        for team in self.teams:
            team.initialize_draft_picks(future_years)

    # Protection zones for conditional 1st-rounders (real NHL usage).
    PROTECTION_ZONES = {"top-3": 3, "top-10": 10, "lottery": 16}

    def resolve_pick_protections(self, year: int) -> List[str]:
        """Resolve conditional 1st-round picks for a draft year.

        Real NHL lottery protection: if a traded 1st-rounder lands inside
        its protected zone, the original club keeps this year's pick and
        the holder instead receives the original club's next-year
        1st-rounder, unprotected (protection consumed either way).

        Idempotent per (pick id, year): resolved picks are recorded in
        ``self._protections_resolved`` so repeated draft-order builds don't
        double-defer or duplicate news. Returns human-readable event lines.
        """
        events: List[str] = []
        resolved = getattr(self, "_protections_resolved", None)
        if resolved is None:
            resolved = set()
            self._protections_resolved = resolved

        # Lottery position by ORIGINAL team (traded picks keep original slot).
        lotto_pos = {}
        try:
            _lr = getattr(self, "lottery_results", None) or {}
            for _k, _rows in _lr.items():
                if int(_k) == int(year):
                    for _r in (_rows or []):
                        lotto_pos[_r.get("original_team")] = _r.get("pick")
                    break
        except Exception:
            pass
        if not lotto_pos:
            # No televised lottery stored: fall back to reverse standings.
            try:
                _sorted = sorted(
                    self.teams,
                    key=lambda t: self.standings.get(t.team_name, {}).get("Points", 0))
                lotto_pos = {t.team_name: i + 1 for i, t in enumerate(_sorted)}
            except Exception:
                return events

        by_name = {t.team_name: t for t in self.teams}
        for team in self.teams:
            for pick in (getattr(team, "draft_picks", {}) or {}).get(year, []):
                try:
                    if pick.round != 1:
                        continue
                    prot = getattr(pick, "protection", "") or ""
                    if prot not in self.PROTECTION_ZONES:
                        continue
                    if pick.current_team == pick.original_team:
                        # Never traded (or already reverted): consume stale flag.
                        pick.protection = ""
                        pick.is_conditional = False
                        continue
                    key = (str(getattr(pick, "id", "")), int(year))
                    if key in resolved:
                        continue
                    pos = lotto_pos.get(pick.original_team)
                    if pos is None:
                        continue
                    zone = self.PROTECTION_ZONES[prot]
                    holder = pick.current_team
                    orig = by_name.get(pick.original_team)
                    # Protection only bites INSIDE the zone: a top-10
                    # protected pick landing at #15 overall conveys normally.
                    in_zone = pos is not None and int(pos) <= int(zone)
                    # Find the deferral asset: the original club's own 1st
                    # in year+1 -- and if that's already been traded, the
                    # obligation ROLLS FORWARD (as far as picks exist --
                    # seven drafts out) instead of silently dying. A
                    # protection that voids because the original club
                    # flipped its next 1st is the exploit: real clubs
                    # can't shed the debt by trading the payment away.
                    defer = None
                    defer_year = None
                    if orig is not None and in_zone:
                        for _dy in (year + 1, year + 2, year + 3, year + 4,
                                    year + 5, year + 6, year + 7):
                            for cand in (getattr(orig, "draft_picks", {}) or {}).get(_dy, []):
                                if (cand.round == 1
                                        and cand.current_team == orig.team_name):
                                    defer = cand
                                    defer_year = _dy
                                    break
                            if defer is not None:
                                break
                    # Last resort: no own 1st available seven drafts out.
                    # Real-world fallback -- the obligation converts to
                    # the original club's next available 2nd-rounder.
                    second = None
                    second_year = None
                    if orig is not None and in_zone and defer is None:
                        for _dy in (year, year + 1, year + 2, year + 3,
                                    year + 4, year + 5, year + 6):
                            for cand in (getattr(orig, "draft_picks", {}) or {}).get(_dy, []):
                                if (cand.round == 2
                                        and cand.current_team == orig.team_name):
                                    second = cand
                                    second_year = _dy
                                    break
                            if second is not None:
                                break
                    # Protection is consumed whatever happens.
                    pick.protection = ""
                    pick.is_conditional = False
                    pick.condition = ""
                    resolved.add(key)
                    if in_zone and defer is not None and orig is not None:
                        pick.current_team = orig.team_name  # reverts this year
                        defer.current_team = holder
                        defer.protection = ""
                        defer.is_conditional = False
                        defer.condition = ""
                        zone_label = {"top-3": "top-3", "top-10": "top-10",
                                      "lottery": "lottery"}[prot]
                        _when = (f"{defer_year} 1st-rounder"
                                 if defer_year == year + 1
                                 else f"{defer_year} 1st-rounder (deferred -- "
                                      f"the {year + 1} 1st had been traded)")
                        events.append(
                            f"Pick protection triggered: {orig.team_name} keeps "
                            f"its {year} 1st-rounder (#{pos} overall, {zone_label} "
                            f"protected); {holder} receives {orig.team_name}'s "
                            f"{_when} instead.")
                    elif in_zone and second is not None and orig is not None:
                        pick.current_team = orig.team_name  # reverts this year
                        second.current_team = holder
                        events.append(
                            f"Pick protection triggered: {orig.team_name} keeps "
                            f"its {year} 1st-rounder (#{pos} overall); with no "
                            f"1st-rounder available through {year + 7}, the "
                            f"obligation converts to {orig.team_name}'s "
                            f"{second_year} 2nd-rounder for {holder}.")
                    elif in_zone:
                        # Nothing left to convey (no 1st seven drafts out,
                        # no 2nd six drafts out): the club stripped its
                        # own cupboard, so the holder keeps this year's
                        # pick and the void is on the record.
                        events.append(
                            f"Pick protection could not be honored: "
                            f"{pick.original_team} holds no 1st or 2nd-round "
                            f"pick through {year + 7} to defer or convert to, "
                            f"so {holder} keeps the {year} 1st-rounder "
                            f"(#{pos} overall) and the protection is void.")
                    # Outside the zone the pick simply conveys: the holder
                    # keeps it and the spent protection is noted for the log.
                    elif pos is not None:
                        events.append(
                            f"Pick protection not triggered: {holder} keeps "
                            f"{orig.team_name if orig else pick.original_team}'s "
                            f"{year} 1st-rounder (#{pos} overall, outside the "
                            f"{prot} zone).")
                except Exception:
                    continue
        if events:
            try:
                _news = getattr(self, "pick_protection_news", None)
                if _news is None:
                    _news = []
                    self.pick_protection_news = _news
                _news.extend(events)
            except Exception:
                pass
        return events

    def get_draft_order(self, year: int) -> List[Tuple[int, Team, DraftPick]]:
        """Generate the draft order for a specific year based on standings.
        
        Returns:
            List of tuples: (overall_pick_number, team, draft_pick)
        """
        draft_order = []
        # Resolve pick protections FIRST: a protected pick that lands in its
        # protected zone reverts to the original club this year, and the
        # holder instead receives the original club's next-year 1st
        # (protection consumed). Idempotent per (pick id, year).
        try:
            self.resolve_pick_protections(year)
        except Exception:
            pass
        
        # Sort teams by points (worst to best for each round).
        # NHL Entry Draft only: AHL clubs hold pick objects in the data
        # model but do not draft. Iterating all 62 teams once produced a
        # 434-pick order that exhausted the 224-prospect class mid-draft.
        _nhl_teams = [t for t in self.teams
                      if getattr(t, 'league_name', '') == 'National Hockey League']
        _draft_teams = _nhl_teams or list(self.teams)
        sorted_teams = sorted(_draft_teams,
                            key=lambda t: self.standings.get(t.team_name, {}).get('Points', 0))

        # Draft lottery: round 1 follows the televised lottery order.
        # lottery_results[year] rows key on the ORIGINAL team (a traded pick
        # keeps its original slot); teams outside the top 16 keep their
        # reverse-standings slot after pick 16.
        lotto_pos = {}
        try:
            _lr = getattr(self, "lottery_results", None) or {}
            for _k, _rows in _lr.items():
                if int(_k) == int(year):
                    for _r in (_rows or []):
                        lotto_pos[_r.get("original_team")] = _r.get("pick")
                    break
        except Exception:
            lotto_pos = {}

        def _orig_name(pick):
            try:
                return next(t for t in self.teams
                            if t.team_name == pick.original_team).team_name
            except StopIteration:
                return getattr(pick, "original_team", "")

        for round_num in range(1, 8):  # 7 rounds
            round_picks = []
            
            # Get all picks for this round and year
            for team in sorted_teams:
                team_picks = [pick for pick in team.get_picks_for_year(year) 
                            if pick.round == round_num]
                
                for pick in team_picks:
                    # Find the team that currently owns this pick.
                    # Ownership follows the trade engine: a traded pick's
                    # current_team names the selecting club (the pick object
                    # stays in the original club's list). Dict membership
                    # is stale after trades, so it is only a fallback.
                    want = str(getattr(pick, "current_team", "") or "")
                    current_owner = next(
                        (t for t in _draft_teams
                         if str(getattr(t, "team_name", "")) == want),
                        None)
                    if current_owner is None:
                        for owner_team in _draft_teams:
                            if pick in owner_team.get_picks_for_year(year):
                                current_owner = owner_team
                                break
                    
                    if current_owner:
                        round_picks.append((current_owner, pick))
            
            # Sort by original team's standing (traded picks keep original position)
            if round_num == 1 and lotto_pos:
                def _lotto_key(x):
                    orig = _orig_name(x[1])
                    if orig in lotto_pos:
                        return lotto_pos[orig]
                    try:
                        return 16 + sorted_teams.index(
                            next(t for t in self.teams
                                 if t.team_name == x[1].original_team))
                    except (StopIteration, ValueError):
                        return 48
                round_picks.sort(key=_lotto_key)
            else:
                round_picks.sort(key=lambda x: sorted_teams.index(
                    next(t for t in self.teams if t.team_name == x[1].original_team)
                ))
            
            # Assign overall pick numbers
            for i, (current_owner, pick) in enumerate(round_picks):
                overall_pick = ((round_num - 1) * 32) + i + 1
                pick.overall_pick = overall_pick
                draft_order.append((overall_pick, current_owner, pick))
        
        return draft_order

    def simulate_draft_lottery(self, year: int):
        """Simulate draft lottery for first round picks (if applicable).

        Real NHL odds via draft_lottery.py (bottom 11, two draws for #1/#2).
        Idempotent: a no-op when this year's televised lottery already ran.
        """
        try:
            from draft_lottery import run_lottery
            stored = getattr(self, "lottery_results", None) or {}
            if year in stored and stored[year]:
                return
            run_lottery(self, year)
        except Exception:
            pass

    def trade_draft_pick(self, pick: DraftPick, from_team: Team, to_team: Team, trade_details: str = ""):
        """Execute a draft pick trade between two teams."""
        if pick not in from_team.get_picks_for_year(pick.year):
            raise ValueError(f"{from_team.team_name} does not own this draft pick")
        
        # Execute the trade
        from_team.trade_pick(pick, to_team.team_name, trade_details)
        to_team.receive_pick(pick)
        
        return True

    def _verify_schedule_integrity(self):
        """Comprehensive verification of NHL scheduling rules and constraints."""
        from collections import defaultdict
        
        print("🔍 Verifying NHL schedule integrity...")
        
        # Group games by date and team
        team_games_by_date = defaultdict(lambda: defaultdict(list))
        team_schedules = defaultdict(list)  # List of (date, opponent, home/away) for each team
        
        for game_date, home_team, away_team in self.schedule:
            home_name = home_team.team_name
            away_name = away_team.team_name
            
            team_games_by_date[game_date][home_name].append('home')
            team_games_by_date[game_date][away_name].append('away')
            
            team_schedules[home_name].append((game_date, away_name, 'home'))
            team_schedules[away_name].append((game_date, home_name, 'away'))
        
        violations = []
        team_stats = {}
        
        # Check Rule 1: No team plays multiple games on the same day
        same_day_violations = []
        for game_date, teams_data in team_games_by_date.items():
            for team_name, games in teams_data.items():
                if len(games) > 1:
                    same_day_violations.append(f"{team_name} has {len(games)} games on {game_date}")
        
        # Check each team's schedule for NHL compliance
        for team_name, schedule in team_schedules.items():
            # Sort by date
            schedule.sort(key=lambda x: x['date'] if isinstance(x, dict) and 'date' in x else x[0])
            
            # Calculate team statistics
            total_games = len(schedule)
            back_to_backs = 0
            consecutive_streaks = []
            current_streak = 1
            max_consecutive = 1
            
            for i in range(1, len(schedule)):
                prev_date = schedule[i-1][0]
                curr_date = schedule[i][0]
                days_between = (curr_date - prev_date).days
                
                if days_between == 1:  # Back-to-back
                    back_to_backs += 1
                    current_streak += 1
                else:
                    if current_streak > 1:
                        consecutive_streaks.append(current_streak)
                    max_consecutive = max(max_consecutive, current_streak)
                    current_streak = 1
            
            # Don't forget the last streak
            if current_streak > 1:
                consecutive_streaks.append(current_streak)
            max_consecutive = max(max_consecutive, current_streak)
            
            team_stats[team_name] = {
                'games': total_games,
                'back_to_backs': back_to_backs,
                'max_consecutive': max_consecutive,
                'consecutive_streaks': consecutive_streaks
            }
            
            # Check Rule 2: No more than 14 back-to-backs per team
            if back_to_backs > 14:
                violations.append(f"{team_name}: {back_to_backs} back-to-backs (limit: 14)")
            
            # Check Rule 3: No more than 2 consecutive games
            if max_consecutive > 2:
                violations.append(f"{team_name}: {max_consecutive} consecutive games (limit: 2)")
        
        # Check Rule 4: Reasonable daily game distribution
        daily_game_counts = defaultdict(int)
        for game_date, _, _ in self.schedule:
            daily_game_counts[game_date] += 1
        
        busy_days = [(date, count) for date, count in daily_game_counts.items() if count > 16]
        
        # Generate comprehensive report
        print(f"\n📊 SCHEDULE INTEGRITY REPORT")
        print(f"{'='*50}")
        
        # Same-day violations (most critical)
        if same_day_violations:
            print(f"❌ CRITICAL: Same-day game violations ({len(same_day_violations)}):")
            for violation in same_day_violations[:10]:
                print(f"   • {violation}")
            if len(same_day_violations) > 10:
                print(f"   ... and {len(same_day_violations) - 10} more")
        else:
            print(f"✅ Same-day games: PASSED (no team plays multiple games same day)")
        
        # Back-to-back violations
        back_to_back_violations = [v for v in violations if "back-to-backs" in v]
        if back_to_back_violations:
            print(f"❌ Back-to-back violations ({len(back_to_back_violations)}):")
            for violation in back_to_back_violations[:5]:
                print(f"   • {violation}")
        else:
            print(f"✅ Back-to-back limit: PASSED (all teams ≤14 back-to-backs)")
        
        # Consecutive game violations
        consecutive_violations = [v for v in violations if "consecutive games" in v]
        if consecutive_violations:
            print(f"❌ Consecutive game violations ({len(consecutive_violations)}):")
            for violation in consecutive_violations[:5]:
                print(f"   • {violation}")
        else:
            print(f"✅ Consecutive games: PASSED (no team plays >2 consecutive)")
        
        # Daily distribution
        if busy_days:
            print(f"⚠️ Busy days (>16 games): {len(busy_days)}")
            for date, count in sorted(busy_days, key=lambda x: x[1], reverse=True)[:3]:
                print(f"   • {date}: {count} games")
        else:
            print(f"✅ Daily distribution: PASSED (≤16 games per day)")
        
        # Overall statistics
        if team_stats:
            avg_games = sum(stats['games'] for stats in team_stats.values()) / len(team_stats)
            avg_back_to_backs = sum(stats['back_to_backs'] for stats in team_stats.values()) / len(team_stats)
            
            print(f"\n📈 LEAGUE STATISTICS")
            print(f"   Teams: {len(team_stats)}")
            print(f"   Total games: {len(self.schedule)}")
            print(f"   Avg games per team: {avg_games:.1f}")
            print(f"   Avg back-to-backs per team: {avg_back_to_backs:.1f}")
        
        # Final verdict
        total_violations = len(same_day_violations) + len(violations)
        if total_violations == 0:
            print(f"\n🎉 SCHEDULE INTEGRITY: EXCELLENT")
            print(f"   All NHL scheduling rules satisfied!")
        elif len(same_day_violations) == 0:
            print(f"\n✅ SCHEDULE INTEGRITY: GOOD")
            print(f"   Critical rules satisfied, {len(violations)} minor violations")
        else:
            print(f"\n❌ SCHEDULE INTEGRITY: NEEDS IMPROVEMENT") 
            print(f"   {total_violations} total violations found")
        
        print(f"{'='*50}\n")

    def get_all_players(self) -> List[Player]:
        """Returns a list of every single player in the game world."""
        all_players = list(self.free_agents)
        all_players.extend(self.draft_prospects)
        for team in self.teams:
            all_players.extend(team.roster)
            all_players.extend(team.ahl_roster)
            all_players.extend(team.prospects)
        return all_players

    def add_team(self, team: Team):
        """Add a team to the league."""
        self.teams.append(team)
        # Initialize standings for this team
        self.standings[team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}

    def _simple_schedule_nhl_games(self):
        """Simple NHL scheduling that absolutely prevents 3+ consecutive games.
        
        Uses a straightforward chronological approach with basic constraint checking.
        """
        print("Starting simple NHL schedule generation...")
        
        # Initialize schedule and games dictionary
        self.schedule = []
        self.games = {}
        
        # Initialize team tracking
        team_tracking = {}
        for team in self.teams:
            team_tracking[team.team_name] = {
                'games_scheduled': 0,
                'last_game_date': None,
                'consecutive_count': 0,
                'back_to_back_used': 0,
                'home_games': 0,
                'away_games': 0
            }
        
        # Get all possible game dates (assuming season starts October 1st, 2024)
        season_start = datetime(2024, 10, 1)
        season_end = datetime(2025, 4, 20)  # NHL season typically ends in April
        all_dates = []
        current_date = season_start
        while current_date <= season_end:
            # Skip certain days if needed (e.g., Christmas)
            if current_date.month == 12 and current_date.day == 25:
                current_date += timedelta(days=1)
                continue
            all_dates.append(current_date)
            current_date += timedelta(days=1)
        
        print(f"Season dates: {len(all_dates)} days from {season_start} to {season_end}")
        
        # Generate all required matchups (82 games per team means 1312 total games)
        required_matchups = []
        
        # Intra-division games (4 games each = 4*7*2 = 56 games per team, intra-division)
        # Each team plays 4 games against 7 other teams in division
        for division in ['Atlantic', 'Metropolitan', 'Central', 'Pacific']:
            division_teams = [t for t in self.teams if t.division == division]
            for i, team1 in enumerate(division_teams):
                for j, team2 in enumerate(division_teams):
                    if i < j:  # Avoid duplicates
                        # Add 4 games between these teams (2 home, 2 away each)
                        for game_num in range(4):
                            if game_num < 2:
                                required_matchups.append((team1.team_name, team2.team_name))
                            else:
                                required_matchups.append((team2.team_name, team1.team_name))
        
        # Inter-division games within conference (3 games each)
        conferences = ['Eastern', 'Western']
        for conf in conferences:
            conf_teams = [t for t in self.teams if t.conference == conf]
            divisions = list(set(t.division for t in conf_teams))
            
            for div1 in divisions:
                for div2 in divisions:
                    if div1 != div2:
                        div1_teams = [t for t in conf_teams if t.division == div1]
                        div2_teams = [t for t in conf_teams if t.division == div2]
                        
                        for team1 in div1_teams:
                            for team2 in div2_teams:
                                # Add 3 games (alternating home/away)
                                for game_num in range(3):
                                    if game_num == 0:
                                        required_matchups.append((team1.team_name, team2.team_name))
                                    elif game_num == 1:
                                        required_matchups.append((team2.team_name, team1.team_name))
                                    else:
                                        # Alternate which team gets extra home game
                                        if hash(team1.team_name + team2.team_name) % 2 == 0:
                                            required_matchups.append((team1.team_name, team2.team_name))
                                        else:
                                            required_matchups.append((team2.team_name, team1.team_name))
        
        # Inter-conference games (2 games each)
        eastern_teams = [t for t in self.teams if t.conference == 'Eastern']
        western_teams = [t for t in self.teams if t.conference == 'Western']
        
        for east_team in eastern_teams:
            for west_team in western_teams:
                # Add 2 games (1 home, 1 away)
                required_matchups.append((east_team.team_name, west_team.team_name))
                required_matchups.append((west_team.team_name, east_team.team_name))
        
        print(f"Generated {len(required_matchups)} required matchups")
        
        # Shuffle matchups to randomize scheduling order
        random.shuffle(required_matchups)
        
        # Schedule games chronologically
        scheduled_games = 0
        failed_attempts = 0
        max_failed_attempts = 1000
        
        for home_team, away_team in required_matchups:
            game_scheduled = False
            
            # Try to schedule this game on the earliest possible date
            for date in all_dates:
                if self._teams_can_play_simple(home_team, away_team, date, team_tracking):
                    # Schedule the game
                    game_id = f"game_{len(self.games) + 1}"
                    self.games[game_id] = {
                        'game_id': game_id,
                        'home_team': home_team,
                        'away_team': away_team,
                        'date': date.strftime('%Y-%m-%d'),
                        'time': '19:00',  # Default 7 PM start
                        'venue': f"{home_team} Arena"
                    }
                    
                    # Also add to schedule list for compatibility
                    home_team_obj = next(t for t in self.teams if t.team_name == home_team)
                    away_team_obj = next(t for t in self.teams if t.team_name == away_team)
                    self.schedule.append((date.date(), home_team_obj, away_team_obj))
                    
                    # Update team tracking
                    for team in [home_team, away_team]:
                        team_data = team_tracking[team]
                        team_data['games_scheduled'] += 1
                        
                        if team_data['last_game_date']:
                            days_diff = (date - team_data['last_game_date']).days
                            if days_diff == 1:
                                team_data['consecutive_count'] += 1
                                if team == home_team:
                                    team_data['back_to_back_used'] += 1
                            else:
                                team_data['consecutive_count'] = 1
                        else:
                            team_data['consecutive_count'] = 1
                        
                        team_data['last_game_date'] = date
                        
                        if team == home_team:
                            team_data['home_games'] += 1
                        else:
                            team_data['away_games'] += 1
                    
                    scheduled_games += 1
                    game_scheduled = True
                    break
            
            if not game_scheduled:
                failed_attempts += 1
                print(f"Failed to schedule {home_team} vs {away_team} - failed attempts: {failed_attempts}")
                
                if failed_attempts >= max_failed_attempts:
                    print("Too many failed scheduling attempts. Stopping.")
                    break
        
        print(f"Scheduled {scheduled_games} games successfully")
        
        # Print final statistics
        for team_name, data in team_tracking.items():
            print(f"{team_name}: {data['games_scheduled']} games, "
                  f"{data['home_games']} home, {data['away_games']} away, "
                  f"{data['back_to_back_used']} back-to-backs")
        
        return True

    def _teams_can_play_simple(self, home_team, away_team, date, team_tracking):
        """Simple constraint checking - only prevents 3+ consecutive games."""
        
        # Check if both teams can play on this date
        for team in [home_team, away_team]:
            team_data = team_tracking[team]
            
            # Skip if team already has a game on this date
            game_today = any(
                game['date'] == date.strftime('%Y-%m-%d') and 
                (game['home_team'] == team or game['away_team'] == team)
                for game in self.games.values()
            )
            if game_today:
                return False
            
            # Check for 3+ consecutive games
            if team_data['last_game_date']:
                days_diff = (date - team_data['last_game_date']).days
                
                if days_diff == 1:  # This would be back-to-back
                    # Check if this would create 3 consecutive games
                    if team_data['consecutive_count'] >= 2:
                        return False  # Would create 3+ in a row
                    
                    # Allow some back-to-backs (teams typically have 10-15 per season)
                    if team_data['back_to_back_used'] >= 15:
                        return False
        
        return True





