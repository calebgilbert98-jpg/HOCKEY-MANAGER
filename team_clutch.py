"""team_clutch.py -- dynamic per-team clutch factor, shared by both sim engines.

Chris 2026-09-29: clutch must be genuinely dynamic per team, driven by
players' and teams' talent, morale, situation, trend, heat, intensity and
recent performance. The old lightweight clutch_factor saturated at exactly
1.00 for every club (forward tiers were written against the wrong rating
scale -- every 1-100 forward cleared the "generational" bar), so clutch
differentiated nothing.

This module computes ONE factor both engines call, so factor parity holds
by construction:
- lightweight (main.py): the OT winner edge (home-away)*0.08 and the
  close-game tip use the differential.
- advanced (quick_sim.py): scales the clutch-moment chance boost per
  shooting team.

Returns a float in [0.85, 1.15]; 1.00 = neutral.

Blend (all existing systems, additive; per-term caps; total clamped):
  roster talent    +/-0.06  marquee-player tiers, native 1-100 (fixed scale bug)
  temperament      +/-0.03  pressure_player/composure of key players (day-one)
  traits/tags      [0,+0.04] "clutch"/"big_game_goalie" traits, playoff tags
                             (latent in fresh leagues; career layer)
  morale           +/-0.035 team_chemistry (morale x leadership)
  situation        +/-0.02  situations_factor composite (room/bench/hunger)
  trend            +/-0.025 parity_engine cross-game form (read-only)
  heat             [0,+0.02] matchup heat x big-game comfort (optional ctx)

Pure read: never mutates team/league/player state. Never raises -- any
failure degrades to 1.00.
"""

# ----------------------------------------------------------------------
# Band + weights (tuning review)
# ----------------------------------------------------------------------
CLUTCH_LO, CLUTCH_HI = 0.85, 1.15

# Roster big-game talent: native 1-100 tiers for top 3F + top 2D + top G.
# Calibrated 2026-09-29 on a fresh 32-team league: total mean ~0.091,
# sd ~0.015, range [0.048, 0.112].
_TALENT_TIERS = ((95, 0.044), (93, 0.036), (91, 0.028), (89, 0.020),
                 (87, 0.012), (85, 0.006), (83, 0.002))
_TALENT_BASELINE = 0.091
_TALENT_SCALE = 1.5
_TALENT_CAP = 0.06

# Big-game temperament: pressure_player/composure of the key players.
# Fresh-league team average ~69, sd ~3.3, range [61, 75].
_TEMPERAMENT_CENTER = 69.0
_TEMPERAMENT_SLOPE = 0.003
_TEMPERAMENT_CAP = 0.03

# Earned big-game identity (career layer; latent in fresh leagues).
_TRAIT_BONUS_EACH = 0.01
_TRAIT_BONUS_CAP = 0.04
_BIG_GAME_TRAITS = ("clutch", "big_game_goalie")
_BIG_GAME_TAGS = ("playoff_performer", "mr_game_7")

# Room state via team_chemistry (morale x leadership, 1-100).
# Fresh-league mean ~68.6, range [66, 70]; toxic rooms collapse it.
_MORALE_CENTER = 68.5
_MORALE_SLOPE = 0.004
_MORALE_CAP = 0.035

# Situation composite (situations_factor score, -10..10).
# Fresh-league mean ~3.9 (hungry young rooms); swings with the season.
_SITUATION_CENTER = 4.0
_SITUATION_SLOPE = 0.004
_SITUATION_CAP = 0.02

# Cross-game momentum (parity_engine form, -100..100; read-only here).
_TREND_CAP = 0.025

# Matchup heat (0-100): big-game rooms lift, fragile rooms don't.
_HEAT_CAP = 0.02


def _tier_points(rating, tiers):
    try:
        r = float(rating)
    except (TypeError, ValueError):
        return 0.0
    for cutoff, pts in tiers:
        if r >= cutoff:
            return pts
    return 0.0


def _key_players(team):
    """Top 3F + top 2D + top G by overall_rating()."""
    try:
        roster = list(getattr(team, "roster", None) or [])
        srt = sorted(roster, key=lambda p: p.overall_rating(), reverse=True)
    except Exception:
        return []
    out, nf, nd, ng = [], 0, 0, 0
    for p in srt:
        try:
            pos = p.primary_position.name
        except Exception:
            continue
        if pos in ("LEFT_WING", "RIGHT_WING", "CENTER") and nf < 3:
            out.append(p)
            nf += 1
        elif pos in ("LEFT_DEFENSE", "RIGHT_DEFENSE") and nd < 2:
            out.append(p)
            nd += 1
        elif pos == "GOALIE" and ng < 1:
            out.append(p)
            ng += 1
        if nf >= 3 and nd >= 2 and ng >= 1:
            break
    return out


def _roster_talent_term(team):
    """Marquee-player big-game talent. +/-0.06."""
    players = _key_players(team)
    total = 0.0
    for p in players:
        try:
            total += _tier_points(p.overall_rating(), _TALENT_TIERS)
        except Exception:
            pass
    term = (total - _TALENT_BASELINE) * _TALENT_SCALE
    return max(-_TALENT_CAP, min(_TALENT_CAP, term)), total


def _temperament_term(team):
    """Big-game temperament from pressure_player/composure. +/-0.03."""
    players = _key_players(team)
    vals = []
    for p in players:
        try:
            pp = float(getattr(p, "pressure_player", 69) or 69)
            co = float(getattr(p, "composure", 69) or 69)
            vals.append((pp + co) / 2.0)
        except Exception:
            continue
    if not vals:
        return 0.0
    avg = sum(vals) / len(vals)
    term = (avg - _TEMPERAMENT_CENTER) * _TEMPERAMENT_SLOPE
    return max(-_TEMPERAMENT_CAP, min(_TEMPERAMENT_CAP, term))


def _trait_term(team):
    """Clutch traits + earned playoff tags. [0, +0.04]."""
    bonus = 0.0
    for p in _key_players(team):
        try:
            traits = getattr(p, "traits", None) or []
            tags = getattr(p, "clutch_tags", None) or []
            if any(t in _BIG_GAME_TRAITS for t in traits) or \
               any(t in _BIG_GAME_TAGS for t in tags):
                bonus += _TRAIT_BONUS_EACH
        except Exception:
            continue
    return min(_TRAIT_BONUS_CAP, bonus)


def _morale_term(team):
    """Room state via team_chemistry. +/-0.035."""
    try:
        chem = float(team.team_chemistry)
    except Exception:
        return 0.0
    term = (chem - _MORALE_CENTER) * _MORALE_SLOPE
    return max(-_MORALE_CAP, min(_MORALE_CAP, term))


def _situation_term(team, situation_score=None):
    """Room/bench/hunger situation composite. +/-0.02.

    situation_score: precomputed situations_factor()["score"] when the
    caller already paid for it (the lightweight computes situations once
    per team per game for its own channel); computed here otherwise.
    """
    try:
        if situation_score is None:
            from reputation_system import situations_factor
            sc = float((situations_factor(team) or {}).get("score", 0.0) or 0.0)
        else:
            sc = float(situation_score or 0.0)
    except Exception:
        return 0.0
    term = (sc - _SITUATION_CENTER) * _SITUATION_SLOPE
    return max(-_SITUATION_CAP, min(_SITUATION_CAP, term))


def _trend_term(team):
    """Cross-game form/momentum (parity_engine state; read-only). +/-0.025."""
    try:
        st = getattr(team, "_parity_state", None) or {}
        form = float(st.get("form", 0.0) or 0.0)
    except Exception:
        return 0.0
    return max(-_TREND_CAP, min(_TREND_CAP, (form / 100.0) * _TREND_CAP))


def _heat_term(talent_total, matchup_heat):
    """Heated games lift big-game rooms; fragile rooms get nothing. [0,+0.02]."""
    try:
        heat = max(0.0, min(100.0, float(matchup_heat)))
    except (TypeError, ValueError):
        return 0.0
    if heat <= 0:
        return 0.0
    try:
        comfort = max(0.0, min(1.0,
                               0.5 + (talent_total - _TALENT_BASELINE)
                               / _TALENT_BASELINE * 0.5))
    except Exception:
        comfort = 0.5
    return (heat / 100.0) * _HEAT_CAP * comfort


def team_clutch_factor(team, league=None, matchup_heat=None,
                       situation_score=None):
    """Dynamic per-team clutch factor in [0.85, 1.15]. Pure read.

    team: Team object. league: reserved for future standings-based stakes.
    matchup_heat: 0-100 for this game (rivalry heat / drama), optional.
    situation_score: precomputed situations_factor()["score"], optional --
    the lightweight passes the value it already computed for its own
    situations channel so the room isn't re-resolved per game.
    """
    try:
        talent_term, talent_total = _roster_talent_term(team)
        value = 1.0
        value += talent_term
        value += _temperament_term(team)
        value += _trait_term(team)
        value += _morale_term(team)
        value += _situation_term(team, situation_score)
        value += _trend_term(team)
        if matchup_heat is not None:
            value += _heat_term(talent_total, matchup_heat)
        return max(CLUTCH_LO, min(CLUTCH_HI, value))
    except Exception:
        return 1.0


def clutch_breakdown(team, league=None, matchup_heat=None,
                     situation_score=None):
    """Diagnostic: per-component contributions. For QA/tuning only."""
    out = {"base": 1.0}
    try:
        talent_term, talent_total = _roster_talent_term(team)
        out["talent"] = round(talent_term, 4)
        out["temperament"] = round(_temperament_term(team), 4)
        out["traits"] = round(_trait_term(team), 4)
        out["morale"] = round(_morale_term(team), 4)
        out["situation"] = round(_situation_term(team, situation_score), 4)
        out["trend"] = round(_trend_term(team), 4)
        out["heat"] = round(_heat_term(talent_total, matchup_heat)
                            if matchup_heat is not None else 0.0, 4)
        out["total"] = round(team_clutch_factor(team, league, matchup_heat,
                                                situation_score), 4)
    except Exception:
        out["total"] = 1.0
    return out
