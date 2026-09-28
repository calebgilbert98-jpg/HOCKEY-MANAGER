"""Advanced hockey metrics model for Puck Dynasty.

Computes NHL-style advanced statistics (Corsi%, Fenwick%, xG%, PDO, zone
starts, GSAx, etc.) from player attributes (1-100 scale) and actual season
production. This is a *model* -- like Evolving-Hockey's RAPM or MoneyPuck's
xG, it estimates underlying performance from observable inputs rather than
tracking every shot attempt in the sim engine.

All functions are pure (no side effects) and safe to call from UI code.

Metric definitions follow the standard analytics glossary:
- CF% : share of shot attempts for while on ice (possession proxy)
- FF%  : share of unblocked attempts for (more repeatable than CF%)
- xGF% : expected-goal share while on ice (shot-quality-aware possession)
- PDO  : on-ice SH% + on-ice SV% (1.000 = league average; regresses to mean)
- OZ%  : share of shifts starting in the offensive zone (deployment context)
- ixG  : individual expected goals from the player's own shots
- GSAx : goals saved above expected (goalies)
- HDSV%: save % on high-danger shots (goalies)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attr(player: Any, name: str, default: int = 50) -> int:
    try:
        return int(getattr(player, name, default) or default)
    except (TypeError, ValueError):
        return default


def _stats(player: Any) -> Any:
    """Current-season PlayerStats (or a blank-like object)."""
    s = getattr(player, "stats", None)
    if s is None:
        # Some code paths store season stats under season_stats
        s = getattr(player, "season_stats", None)
    return s


def _parse_toi(toi_str: str) -> float:
    """Parse 'MM:SS' average TOI into minutes (float)."""
    try:
        parts = str(toi_str or "0:00").split(":")
        return int(parts[0]) + int(parts[1]) / 60.0
    except (ValueError, IndexError):
        return 0.0


def _is_goalie(player: Any) -> bool:
    pos = getattr(player, "primary_position", None)
    name = getattr(pos, "name", str(pos or "")).upper()
    return "GOAL" in name


# ---------------------------------------------------------------------------
# Skater metrics
# ---------------------------------------------------------------------------

@dataclass
class SkaterAdvanced:
    """Advanced metrics for a skater. Percentages are 0-100 scale."""
    sh_pct: float = 0.0        # shooting % (actual)
    ixg: float = 0.0           # individual expected goals (model)
    ixg_per60: float = 0.0
    cf_pct: float = 50.0       # Corsi For % estimate (model)
    ff_pct: float = 50.0       # Fenwick For % estimate (model)
    xgf_pct: float = 50.0      # expected-goal share estimate (model)
    pdo: float = 1.000         # on-ice SH% + SV% (model)
    oz_pct: float = 50.0       # offensive zone start % (model)
    p_per60: float = 0.0       # points per 60 (actual)
    g_per60: float = 0.0
    game_score: float = 0.0    # Dom Luszczyszyn Game Score (actual)
    hits: int = 0
    blocks: int = 0


def skater_advanced(player: Any, team_avg_sh_pct: float = 9.5,
                    team_avg_sv_pct: float = 0.905) -> SkaterAdvanced:
    """Compute advanced metrics for a skater.

    team_avg_sh_pct / team_avg_sv_pct anchor the PDO estimate; pass the
    player's team actuals when available.
    """
    m = SkaterAdvanced()
    st = _stats(player)
    goals = getattr(st, "goals", 0) or 0
    shots = getattr(st, "shots", 0) or 0
    assists = getattr(st, "assists", 0) or 0
    gp = getattr(st, "games_played", 0) or 0
    toi = _parse_toi(getattr(player, "avg_toi", "0:00"))
    toi_hours = (toi * max(gp, 1)) / 60.0 if toi else 0.0

    # --- Actuals ---
    m.sh_pct = (goals / shots * 100.0) if shots else 0.0
    m.hits = getattr(st, "hits", 0) or 0
    m.blocks = getattr(st, "blocks", 0) or 0
    if toi_hours > 0:
        m.p_per60 = (goals + assists) / toi_hours
        m.g_per60 = goals / toi_hours

    # Individual expected goals: shot volume x modeled shot quality.
    # Modeled finish: 6% base + shooting attribute contribution (up to ~14%
    # for elite shooters), plus a small playmaking bump for shot selection.
    shooting = _attr(player, "shooting")
    playmaking = _attr(player, "playmaking", _attr(player, "passing", 50))
    exp_sh_pct = 6.0 + (shooting / 100.0) * 8.0 + (playmaking / 100.0) * 1.5
    m.ixg = shots * exp_sh_pct / 100.0
    if toi_hours > 0:
        m.ixg_per60 = m.ixg / toi_hours

    # --- Possession proxies (model) ---
    # Skaters who move the puck (passing, puck handling, skating) drive
    # attempts for; defensively-aware skaters suppress attempts against.
    passing = _attr(player, "passing", playmaking)
    puck = _attr(player, "puck_handling", 50)
    skating = _attr(player, "skating", 50)
    def_aw = _attr(player, "defensive_awareness")
    off_drive = 0.45 * passing + 0.30 * puck + 0.25 * skating      # 1-100
    def_supp = 0.60 * def_aw + 0.25 * skating + 0.15 * _attr(player, "strength", 50)
    # Map to a share around 50%: each attribute point above/below 50 moves
    # the needle ~0.35pp (calibrated so elite two-way ~58%, replacement ~44%)
    m.cf_pct = round(50.0 + (off_drive - 50.0) * 0.22 + (def_supp - 50.0) * 0.13, 1)
    m.ff_pct = round(50.0 + (off_drive - 50.0) * 0.24 + (def_supp - 50.0) * 0.14, 1)
    m.cf_pct = max(35.0, min(65.0, m.cf_pct))
    m.ff_pct = max(35.0, min(65.0, m.ff_pct))

    # --- xGF% (model): shot quality for vs against ---
    # For: shooting + playmaking quality; Against: defensive awareness.
    xgf = (m.ixg * 1.15) + (assists * 0.28)          # quality-weighted offense
    xga = max(0.5, (100.0 - def_supp) / 100.0 * (toi / 18.0) * max(gp, 1) * 0.55)
    m.xgf_pct = round(100.0 * xgf / (xgf + xga), 1) if (xgf + xga) else 50.0
    m.xgf_pct = max(35.0, min(65.0, m.xgf_pct))

    # --- PDO: on-ice shooting + save % ---
    # On-ice SH% regresses toward team average; individual finishers nudge it.
    on_ice_sh = team_avg_sh_pct + (m.sh_pct - team_avg_sh_pct) * 0.35 if shots >= 20 else team_avg_sh_pct
    on_ice_sv = team_avg_sv_pct + (def_supp - 50.0) * 0.0004
    m.pdo = round((on_ice_sh / 100.0) + on_ice_sv, 3)

    # --- Zone starts (model): deployment follows role ---
    # Offensive instincts -> more OZ starts; defensive role -> more DZ.
    off_inst = _attr(player, "offensive_instincts", (shooting + playmaking) // 2)
    m.oz_pct = round(50.0 + (off_inst - def_aw) * 0.35, 1)
    m.oz_pct = max(30.0, min(70.0, m.oz_pct))

    # --- Game Score (Dom Luszczyszyn's formula, actuals) ---
    # G=0.75, A1=0.70, A2=0.55 (we only have total assists; split 60/40),
    # SOG=0.075, BLK=0.05, PIM=-0.15, plus on-ice proxies omitted.
    a1 = assists * 0.6
    a2 = assists * 0.4
    pim = getattr(st, "penalties_in_minutes", 0) or 0
    m.game_score = round(goals * 0.75 + a1 * 0.70 + a2 * 0.55
                         + shots * 0.075 + m.blocks * 0.05 - pim * 0.15, 2)
    return m


# ---------------------------------------------------------------------------
# Goalie metrics
# ---------------------------------------------------------------------------

@dataclass
class GoalieAdvanced:
    """Advanced metrics for a goalie."""
    gsax: float = 0.0        # goals saved above expected (model)
    gsaa: float = 0.0        # goals saved above average (actual)
    hdsv_pct: float = 0.0    # high-danger save % estimate (model)
    qs_pct: float = 0.0       # quality-start % estimate (model)
    sv_pct: float = 0.0       # actual save % (0-1)
    gaa: float = 0.0
    sa_per60: float = 0.0


def goalie_advanced(player: Any, league_avg_sv_pct: float = 0.905) -> GoalieAdvanced:
    """Compute advanced metrics for a goalie."""
    m = GoalieAdvanced()
    st = _stats(player)
    sa = getattr(st, "shots_against", 0) or 0
    saves = getattr(st, "saves", 0) or 0
    ga = getattr(st, "goals_against", 0) or 0
    gp = getattr(st, "games_played", 0) or 0
    wins = getattr(st, "wins", 0) or 0

    m.sv_pct = (saves / sa) if sa else 0.0
    m.gaa = getattr(st, "goals_against_avg", 0.0) or 0.0
    toi = _parse_toi(getattr(player, "avg_toi", "0:00"))
    if toi and gp:
        m.sa_per60 = sa / ((toi * gp) / 60.0)

    # GSAA: expected goals allowed at league-average SV% minus actual goals
    m.gsaa = round(sa * (1.0 - league_avg_sv_pct) - ga, 1)

    # GSAx (model): expected GA from shot quality faced.
    # Shot quality faced is proxied by team defense: weaker defensive teams
    # (low team def awareness) concede higher-danger chances.
    positioning = _attr(player, "positioning", 50)
    reflexes = _attr(player, "reflexes", _attr(player, "agility", 50))
    rebound = _attr(player, "rebound_control", 50)
    # Expected save % for an average goalie facing this workload, adjusted
    # by the goalie's own high-danger ability.
    hd_ability = (0.5 * positioning + 0.35 * reflexes + 0.15 * rebound)  # 1-100
    # High-danger SV% estimate: ~.780 league avg, +/- .004 per attribute point
    m.hdsv_pct = round(0.780 + (hd_ability - 50.0) * 0.004, 3)
    m.hdsv_pct = max(0.700, min(0.900, m.hdsv_pct))
    # xGA: assume ~28% of shots are high-danger at .780 avg, rest at .940 avg
    xga = sa * (0.28 * (1 - 0.780) + 0.72 * (1 - 0.940))
    # Credit the goalie's own HD ability vs the average assumption
    xga *= 1.0 + (0.780 - m.hdsv_pct) * 0.8
    m.gsax = round(xga - ga, 1)

    # Quality-start % estimate: modeled from consistency + overall ability
    consistency = _attr(player, "consistency", 50)
    overall = _attr(player, "overall", 75)
    m.qs_pct = round(max(0.0, min(1.0,
                        0.45 + (consistency - 50) * 0.006 + (overall - 75) * 0.008)), 3)
    return m


# ---------------------------------------------------------------------------
# Team metrics
# ---------------------------------------------------------------------------

@dataclass
class TeamAdvanced:
    """Advanced metrics for a team. Percentages on 0-100 scale."""
    cf_pct: float = 50.0
    ff_pct: float = 50.0
    xgf_pct: float = 50.0
    gf_pct: float = 50.0
    pdo: float = 1.000
    hdcf_pct: float = 50.0
    gf_per60: float = 0.0
    ga_per60: float = 0.0
    pp_pct: float = 0.0
    pk_pct: float = 0.0
    srs: float = 0.0          # simple rating: goal diff adjusted (schedule-naive)


def _team_attr_avg(team: Any, name: str, roster_attr: str = "roster") -> float:
    players = list(getattr(team, roster_attr, []) or [])
    if not players:
        return 50.0
    vals = [_attr(p, name) for p in players]
    return sum(vals) / len(vals)


def team_advanced(team: Any, league_avg_gf: float = 3.1) -> TeamAdvanced:
    """Compute team-level advanced metrics.

    league_avg_gf: league average goals-for per game (for SRS context).
    """
    m = TeamAdvanced()
    # Aggregate skater models across the NHL roster
    skaters = [p for p in getattr(team, "roster", []) or [] if not _is_goalie(p)]
    if skaters:
        cf = sum(skater_advanced(p).cf_pct for p in skaters) / len(skaters)
        ff = sum(skater_advanced(p).ff_pct for p in skaters) / len(skaters)
        xg = sum(skater_advanced(p).xgf_pct for p in skaters) / len(skaters)
        m.cf_pct = round(cf, 1)
        m.ff_pct = round(ff, 1)
        m.xgf_pct = round(xg, 1)

    # PDO from team shooting + team save %
    gf = getattr(team, "goals_for", 0) or 0
    ga = getattr(team, "goals_against", 0) or 0
    gp = getattr(team, "games_played", 0) or max(getattr(team, "wins", 0) + getattr(team, "losses", 0), 1)
    shots_for = sum((_stats(p) and getattr(_stats(p), "shots", 0) or 0) for p in skaters)
    shots_against = sum((_stats(p) and getattr(_stats(p), "shots_against", 0) or 0)
                        for p in getattr(team, "roster", []) if _is_goalie(p))
    team_sh = (gf / shots_for) if shots_for else 0.095
    team_sv = 1 - (ga / shots_against) if shots_against else 0.905
    # Guard against partial/test rosters producing impossible percentages
    if not (0.03 <= team_sh <= 0.20):
        team_sh = 0.095
    if not (0.850 <= team_sv <= 0.950):
        team_sv = 0.905
    m.pdo = round(team_sh + team_sv, 3)

    if gf + ga:
        m.gf_pct = round(100.0 * gf / (gf + ga), 1)
    # High-danger share tracks xG share closely; add a touch of noise-free spread
    m.hdcf_pct = round(max(35.0, min(65.0, m.xgf_pct + (m.cf_pct - 50.0) * 0.2)), 1)

    # Per-60 rates (regulation 60-minute games)
    if gp:
        m.gf_per60 = round(gf / gp, 2)
        m.ga_per60 = round(ga / gp, 2)

    # Special teams (actuals)
    ppo = getattr(team, "power_play_opportunities", 0) or 0
    ppg = getattr(team, "power_play_goals", 0) or 0
    pko = getattr(team, "penalty_kill_opportunities", 0) or ppo  # fallback symmetry
    pkga = getattr(team, "penalty_kill_goals_against", 0) or 0
    m.pp_pct = round(100.0 * ppg / ppo, 1) if ppo else 0.0
    m.pk_pct = round(100.0 * (pko - pkga) / pko, 1) if pko else 0.0

    # SRS: goal differential per game vs league average (schedule-naive)
    if gp:
        m.srs = round((gf - ga) / gp - 0.0, 2)  # league avg diff = 0
    return m


# ---------------------------------------------------------------------------
# League leaders in advanced categories
# ---------------------------------------------------------------------------

def league_leaders_advanced(players: List[Any], category: str,
                            limit: int = 10, minimum_gp: int = 10) -> List[Dict[str, Any]]:
    """Top players by an advanced metric.

    category: 'ixg' | 'xgf_pct' | 'cf_pct' | 'pdo' | 'p_per60' |
              'game_score' | 'gsax' | 'hdsv_pct' | 'sh_pct'
    """
    rows = []
    for p in players:
        st = _stats(p)
        gp = getattr(st, "games_played", 0) or 0
        if gp < minimum_gp:
            continue
        if _is_goalie(p):
            if category not in ("gsax", "hdsv_pct", "gsaa"):
                continue
            adv = goalie_advanced(p)
        else:
            if category in ("gsax", "hdsv_pct", "gsaa"):
                continue
            adv = skater_advanced(p)
        val = getattr(adv, category, None)
        if val is None:
            continue
        rows.append({"player": p, "value": val,
                     "name": getattr(p, "full_name", "?"),
                     "team": getattr(getattr(p, "team", None), "team_name", "")})
    return sorted(rows, key=lambda r: r["value"], reverse=True)[:limit]


# ---------------------------------------------------------------------------
# Metric glossary (for UI tooltips)
# ---------------------------------------------------------------------------

GLOSSARY: Dict[str, str] = {
    "CF%": "Corsi For %: share of all shot attempts (shots+misses+blocks) for the player's team while on ice. Raw possession proxy.",
    "FF%": "Fenwick For %: like Corsi but excludes blocked shots. Slightly more repeatable.",
    "xGF%": "Expected-goal share while on ice: xGF/(xGF+xGA). Shot-quality-aware possession; the best predictive process metric.",
    "ixG": "Individual expected goals: goal-probability value of the player's own shots (location, angle, shot quality).",
    "PDO": "On-ice shooting % + on-ice save % (avg 1.000). High PDO = likely lucky; regresses to the mean.",
    "OZ%": "Offensive-zone start %: deployment context. High OZ% = sheltered offensive minutes.",
    "P/60": "Points per 60 minutes: TOI-normalized production; fair across roles.",
    "Game Score": "Single-number game rating weighting goals, assists, shots, blocks and penalties.",
    "GSAx": "Goals Saved Above Expected: expected goals against minus actual goals allowed. Positive = above expected.",
    "GSAA": "Goals Saved Above Average: expected goals allowed at league-average save % minus actual goals allowed.",
    "HDSV%": "High-danger save %: the most predictive single-season goalie stat.",
    "QS%": "Quality-start %: share of starts with above-average save %.",
    "SH%": "Shooting %: goals divided by shots on goal.",
    "GF%": "Goal share at even strength: actual results vs the xGF% process.",
    "PP%": "Power-play conversion rate.",
    "PK%": "Penalty-kill success rate.",
    "SRS": "Simple Rating System: goal differential per game (schedule-naive).",
}
