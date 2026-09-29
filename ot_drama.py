"""OT drama: which games reach overtime and who wins it, shaped by the room.

Chris's five factors -- game intensity, player/coach morale and situational
state, rivalry heat, grudge matches, atmospheric/fan factors -- feed an
OT-likelihood multiplier and a home OT win edge. Pure reads only: this
module never writes to teams, the league, or the standings, and never
raises -- missing inputs degrade to quiet neutrals (same contract as
narrative_ledger.matchup_narrative).

Additive by design (Caleb owns the engine): callers pass the context into
existing resolution code via optional parameters with behavior-preserving
defaults. Regulation scoring is never touched -- OT likelihood moves via
the explicit, capped late-equalizer roll, not by shifting the GPG
equilibrium.
"""

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# §8 tuning constants -- every knob lives here, in one place.
# ---------------------------------------------------------------------------
OT_MULT_CLAMP = (0.85, 1.35)      # max drama swing on OT likelihood
RIVALRY_OT_WEIGHT = 0.25          # heat/100 * this added to ot_mult
INTENSITY_OT_WEIGHT = 0.10        # league tension contribution
GRUDGE_OT_BONUS = 0.15            # flat bonus for grudge matches
GRUDGE_HOME_EDGE = 0.03           # home pride edge in grudge games
EQUALIZER_RATE = 0.45             # (ot_mult - 1) * this = induced-tie prob
EQUALIZER_P_CAP = 0.20            # hard per-game ceiling on the equalizer roll
INDUCED_OT_CAP = 0.06             # design §8: induced OT stays under ~6% of games
# The equalizer only rolls on 1-goal games, so the per-game cap is scaled
# by the calling path's structural 1-goal share: cap = min(P_CAP,
# INDUCED_OT_CAP / share). The design doc assumed ~25%; the lightweight
# goal model (σ=1.0 per side) lands ~72% within a goal structurally.
DEFAULT_ONE_GOAL_SHARE = 0.25
LIGHTWEIGHT_ONE_GOAL_SHARE = 0.72
# AdvancedGameSim regulation ends within a goal ~1/3 of the time
# (measured 0.33 on the Small database; OT games excluded).
ADVANCED_ONE_GOAL_SHARE = 0.35
WIN_EDGE_CLAMP = (-0.15, 0.15)    # max home OT win-probability edge
MORALE_WIN_WEIGHT = 0.10          # per 100 morale-diff points
SITUATION_WIN_WEIGHT = 0.50       # per 1.0 xg_mult diff (~+/-0.08 in practice)
CROWD_WIN_WEIGHT = 0.06           # per +/-50 energy from neutral
SHOOTOUT_EDGE_MAX = 0.06          # max shootout probability nudge
SHOOTOUT_EDGE_DAMP = 0.40         # shootouts are coin flips; edge matters less


def _avg_morale(team: Any) -> Any:
    """Mean player morale (native 1-100, 70 neutral). None if unreadable."""
    try:
        roster = getattr(team, "roster", None) or []
        vals = [float(getattr(p, "morale", 70)) for p in roster
                if getattr(p, "morale", None) is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)
    except Exception:
        return None


def ot_context(home_team: Any, away_team: Any, league: Any = None,
               atmosphere: Any = None, is_playoff: bool = False) -> Dict[str, Any]:
    """Aggregate the five drama factors into OT likelihood + home edge.

    Returns {"ot_mult", "home_win_edge", "drama01", "drivers"}.
    drama01 is ot_mult normalized to 0..1 across OT_MULT_CLAMP (neutral 0.3).
    drivers are human-readable strings for news/narrative copy.
    Never raises.
    """
    out: Dict[str, Any] = {
        "ot_mult": 1.0,
        "home_win_edge": 0.0,
        "drama01": 0.3,
        "drivers": [],
    }
    try:
        ot_mult = 1.0
        edge = 0.0
        drivers: List[str] = []

        # 1. League intensity (season tension; playoff series intensity later).
        try:
            from narrative_ledger import active_ledger
            from season_intensity import season_intensity
            _inten = season_intensity(active_ledger()) or {}
            _iv = float(_inten.get("value", 0.0) or 0.0)
            ot_mult += (_iv / 100.0) * INTENSITY_OT_WEIGHT
            if _iv >= 65:
                drivers.append("High league tension")
        except Exception:
            pass

        # 2+3. Rivalry heat + grudge memory (read-only via narrative ledger).
        try:
            from narrative_ledger import matchup_narrative
            _mn = matchup_narrative(home_team, away_team, league=league) or {}
            _heat = float(_mn.get("rivalry_heat", 0.0) or 0.0)
            ot_mult += (_heat / 100.0) * RIVALRY_OT_WEIGHT
            if _heat >= 65:
                drivers.append("Bad blood")
            elif _heat >= 35:
                drivers.append("Simmering rivalry")
            if _mn.get("grudge"):
                ot_mult += GRUDGE_OT_BONUS
                edge += GRUDGE_HOME_EDGE
                drivers.append("Grudge match")
        except Exception:
            pass

        # 4. Player morale: the hotter room wants it more.
        try:
            _mh = _avg_morale(home_team)
            _ma = _avg_morale(away_team)
            if _mh is not None and _ma is not None:
                edge += ((_mh - _ma) / 100.0) * MORALE_WIN_WEIGHT
                if abs(_mh - _ma) >= 12:
                    drivers.append("Hot room" if _mh > _ma else "Cold room")
        except Exception:
            pass

        # 5. Situational state: room/bench/hunger edge per side.
        try:
            from reputation_system import situations_factor
            _sh = situations_factor(home_team) or {}
            _sa = situations_factor(away_team) or {}
            _xh = float(_sh.get("xg_mult", 1.0) or 1.0)
            _xa = float(_sa.get("xg_mult", 1.0) or 1.0)
            edge += (_xh - _xa) * SITUATION_WIN_WEIGHT
        except Exception:
            pass

        # 6. Atmosphere: a jacked building lifts the home side.
        try:
            _energy = None
            if isinstance(atmosphere, dict):
                _energy = atmosphere.get("energy")
            if _energy is not None:
                _energy = float(_energy)
                edge += ((_energy - 50.0) / 50.0) * CROWD_WIN_WEIGHT
                if _energy >= 80:
                    drivers.append("Roaring crowd")
        except Exception:
            pass

        ot_mult = max(OT_MULT_CLAMP[0], min(OT_MULT_CLAMP[1], ot_mult))
        edge = max(WIN_EDGE_CLAMP[0], min(WIN_EDGE_CLAMP[1], edge))
        out["ot_mult"] = ot_mult
        out["home_win_edge"] = edge
        out["drama01"] = (ot_mult - OT_MULT_CLAMP[0]) / (OT_MULT_CLAMP[1] - OT_MULT_CLAMP[0])
        out["drivers"] = drivers
    except Exception:
        pass
    return out


def late_equalizer_roll(ctx: Dict[str, Any],
                        trailing_team_is_home: bool = False,
                        one_goal_share: float = DEFAULT_ONE_GOAL_SHARE) -> bool:
    """Late-equalizer roll -- call ONLY when regulation ends 1-goal apart.

    Models the pulled-goalie / 6-on-5 score that forces OT in big games.
    Probability is (ot_mult - 1) * EQUALIZER_RATE, capped per game at
    min(EQUALIZER_P_CAP, INDUCED_OT_CAP / one_goal_share) so the induced
    OT rate stays under ~6% of games for the calling path's structural
    1-goal share. Cold/neutral contexts (ot_mult <= 1) never fire.

    Scoring-equilibrium note: the equalizer models a REAL scored goal (the
    empty-netter) plus the ensuing OT winner, so each induced OT adds ~2
    goals vs its regulation counterfactual. At ~4% induced games that is
    ~+0.08 GPG league-wide -- negligible against the ~6.1 equilibrium, and
    inherent to having more OT games at all (OT always ends with a goal).
    Regulation scoring means are never touched. Never raises.
    """
    try:
        import random
        _mult = float((ctx or {}).get("ot_mult", 1.0))
        _p = (_mult - 1.0) * EQUALIZER_RATE
        if _p <= 0:
            return False
        _share = float(one_goal_share or DEFAULT_ONE_GOAL_SHARE)
        _cap = min(EQUALIZER_P_CAP, INDUCED_OT_CAP / max(_share, 1e-6))
        _p = min(_p, _cap)
        return random.random() < _p
    except Exception:
        return False


def shootout_edge(ctx: Dict[str, Any], shooter_is_home: bool = False) -> float:
    """Small probability nudge for the shared shootout core.

    Damped from home_win_edge (shootouts are coin flips; edges matter
    less), clamped to +/-SHOOTOUT_EDGE_MAX. Positive favors the shooter.
    Never raises.
    """
    try:
        _e = float((ctx or {}).get("home_win_edge", 0.0))
        _nudge = _e * SHOOTOUT_EDGE_DAMP
        _nudge = max(-SHOOTOUT_EDGE_MAX, min(SHOOTOUT_EDGE_MAX, _nudge))
        return _nudge if shooter_is_home else -_nudge
    except Exception:
        return 0.0
