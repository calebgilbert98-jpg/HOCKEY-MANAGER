#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Attribute composites (TRACK 2): logical per-event attribute combinations.

Modeled on the net-front battle combination in mesh_system.py (forward vs
defense+goalie, grade-A/B/C grader): one documented composite per game event,
each a weighted sum of member attributes with weights summing to 1.0 and a
rationale comment. The "finishing" composite is the exception: it aggregates
harmonically via mesh_system.finishing_rating (the ONE shared finishing
decision, per Muck 2026-10-01) -- raw_composite delegates there.

FORM/HEAT/STREAK STATEMENT (for the B1 talent-hierarchy composition check):
    NO composite input reads player form (mesh_form), heater state
    (_player_heat), streaks, confidence runs, or any per-player time-varying
    performance state. The only time-varying inputs are game CIRCUMSTANCE:
    fatigue/energy, morale (1-100 season mood), score state + clock, home ice,
    and rivalry heat. Heater-reward lives in deployment_policy scores and the
    leverage system -- NOT in this module. There is deliberately no
    double-reward of hot players here.

DESIGN CONTRACT (per Muck's directives):
  * STRICTLY ADDITIVE, never a retune: every composite ships as a small
    bounded amplifier (chemistry precedent: capped amplifier). The formula
    is prob *= composite_amplifier(...), with the clamp INSIDE this module.
    Rails are per-composite; scoring-adjacent events (finishing, goalie_save,
    chance_creation) carry tighter rails than the rest.
  * ONE DECISION, TWO FIDELITIES: this module is the single shared copy.
    GameSim (simulation.py) and AdvancedGameSim (quick_sim.py) both import
    it. There is no second copy of any composite.
  * NO NET-BATTLE OR SCORING WEIGHTS TOUCHED: mesh_system composites,
    grade weights, and scoring constants are not imported-and-retuned;
    amplifiers multiply on top of the existing decisions only.
  * "Realistic possibilities under the right circumstances": a 65-overall
    with maxed circumstance rises measurably but stays well below an 85's
    average case -- talent gradient holds. No 0%/100% mappings anywhere;
    the amplifier is a logistic (tanh) mapping with hard clamped rails.
    Every formula documents its input range and output range.
"""

import math

# ---------------------------------------------------------------------------
# Composite definitions.
#
# members: [(attribute_name, weight)] -- weights sum to 1.0 (asserted at
#          import). All attribute names are verified real Player fields in
#          game_classes.py; do not add invented ones.
# rationale: why THIS combination for THIS event.
# rails: (lo, hi) hard clamp on the amplifier output.
# ---------------------------------------------------------------------------

_COMPOSITES = {
    "chance_creation": {
        # Playmaking / chance creation: vision finds the lane, passing
        # delivers it, creativity + offensive awareness time it, hockey IQ
        # reads the developing play, flair unlocks the unexpected seam,
        # skating separation buys the time to make the play.
        "members": [
            ("vision", 0.30),
            ("passing", 0.20),
            ("passing_creativity", 0.15),
            ("offensive_awareness", 0.15),
            ("hockey_iq", 0.10),
            ("flair", 0.05),
            ("skating", 0.05),
        ],
        "rails": (0.97, 1.03),  # scoring-adjacent (chance volume): tight
    },
    "finishing": {
        # Finishing (2026-10-01 rebuild, per Muck): the diverse scoring
        # toolkit -- NOT just a shot. The release itself (_shot_tool: the
        # per-attempt wristshot/slapshot/one_timer/backhand, defaulting to
        # the shooter's best tool for the stable rating) leads, because
        # the release is what beats goalies; shooting_accuracy places it
        # (corners, not crests); composure keeps the hands under pressure
        # and pressure_player steadies the clutch release; hockey_iq reads
        # the goalie and picks the spot while anticipation reacts to the
        # developing chance; offensive_positioning puts him in the right
        # spot and off_the_puck finds the seam / loses coverage;
        # deflections is the tipping hand-eye; balance shoots in stride
        # through contact and strength wins the net-front spot to shoot
        # from; determination wins the second effort around the crease and
        # aggressiveness attacks the net instead of the perimeter.
        # Aggregated HARMONICALLY by mesh_system.finishing_rating (the
        # synergy gate) -- raw_composite delegates there, so this table
        # documents the members while the rating itself is the ONE shared
        # finishing decision (see mesh_system.FINISHING_MEMBERS; a QA
        # cross-check asserts the two tables stay in sync).
        "members": [
            ("_shot_tool", 0.22),
            ("shooting_accuracy", 0.16),
            ("composure", 0.10),
            ("hockey_iq", 0.08),
            ("offensive_positioning", 0.08),
            ("off_the_puck", 0.08),
            ("anticipation", 0.06),
            ("pressure_player", 0.05),
            ("deflections", 0.05),
            ("balance", 0.04),
            ("strength", 0.04),
            ("determination", 0.02),
            ("aggressiveness", 0.02),
        ],
        "rails": (0.94, 1.06),  # scoring-sensitive; widened 2026-10-01
                                # (Muck: finishing must matter more)
        "aggregation": "harmonic",  # resolved by mesh_system.finishing_rating
    },
    "defensive_play": {
        # Takeaways / blocks: defensive awareness reads the play,
        # defensive positioning closes lanes and gaps, shot_blocking is
        # the willingness+technique to eat it, pokecheck takes the puck,
        # anticipation times the stick, strength pins the carrier after.
        "members": [
            ("defensive_awareness", 0.25),
            ("defensive_positioning", 0.25),
            ("shot_blocking", 0.15),
            ("pokecheck", 0.15),
            ("anticipation", 0.10),
            ("strength", 0.10),
        ],
        "rails": (0.94, 1.06),
    },
    "physicality": {
        # Hits: checking is the technique, bodycheck the heavy tool,
        # strength and balance drive through contact, aggressiveness
        # commits to the hit, determination finishes it. NOTE:
        # hitting_tendency is the FREQUENCY GATE (who throws hits), not a
        # skill input -- it decides selection, not success.
        "members": [
            ("checking", 0.25),
            ("bodycheck", 0.20),
            ("strength", 0.20),
            ("balance", 0.15),
            ("aggressiveness", 0.10),
            ("determination", 0.10),
        ],
        "rails": (0.94, 1.06),
    },
    "faceoff": {
        # Faceoffs: faceoffs is the core draw skill, strength wins the
        # tie-up, composure steadies the big draws, faceoff_wins is the
        # technique-counterpoint attribute, awareness reads the opponent's
        # set (offensive zone = attack the draw, defensive zone = tie up).
        "members": [
            ("faceoffs", 0.45),
            ("strength", 0.20),
            ("composure", 0.15),
            ("faceoff_wins", 0.10),
            ("defensive_awareness", 0.05),
            ("offensive_awareness", 0.05),
        ],
        "rails": (0.94, 1.06),
    },
    "puck_retrieval": {
        # Board battles / loose pucks: strength and balance win the
        # scrum, loose_puck is the first-to-the-puck nose, work_rate keeps
        # the feet moving, determination wins the second effort,
        # forechecking is the hunt instinct.
        "members": [
            ("strength", 0.25),
            ("balance", 0.20),
            ("loose_puck", 0.20),
            ("work_rate", 0.15),
            ("determination", 0.10),
            ("forechecking", 0.10),
        ],
        "rails": (0.94, 1.06),
    },
    "goalie_save": {
        # Save composite (broad save toolkit; the mesh_system
        # goalie_skill_composite is the separate shared conversion
        # decision and is NOT retuned here): positioning covers the net,
        # reflexes win the desperation saves, rebound_control kills second
        # chances, composure steadies traffic, glove_hand and stick_side
        # are the per-side tools, breakaway_skill the 1v1 toolkit.
        # puck_handling is a distribution skill (excluded); goaltending is
        # the generic bucket mesh_system owns (excluded).
        "members": [
            ("positioning", 0.30),
            ("reflexes", 0.25),
            ("rebound_control", 0.15),
            ("composure", 0.10),
            ("glove_hand", 0.10),
            ("stick_side", 0.05),
            ("breakaway_skill", 0.05),
        ],
        "rails": (0.97, 1.03),  # scoring-sensitive: tight
    },
    "skating": {
        # Mobility: speed is the top gear, acceleration the first three
        # strides, agility the edges in traffic, balance keeps him upright
        # at pace, stamina lets him skate it shift after shift.
        "members": [
            ("speed", 0.30),
            ("acceleration", 0.25),
            ("agility", 0.20),
            ("balance", 0.15),
            ("stamina", 0.10),
        ],
        "rails": (0.95, 1.05),  # some scoring adjacency: mid-tight
    },
    "discipline": {
        # Penalty avoidance: discipline is the core foul-avoidance trait,
        # composure keeps the head when provoked, decision_making picks
        # the clean play over the lazy hook. Applied INVERTED: a high
        # discipline composite REDUCES penalty probability.
        "members": [
            ("discipline", 0.60),
            ("composure", 0.25),
            ("decision_making", 0.15),
        ],
        "rails": (0.96, 1.04),  # PP volume adjacency: tight, inverted
    },
}

# Weight-integrity gate: every composite's weights must sum to 1.0.
for _k, _d in _COMPOSITES.items():
    _s = sum(_w for _, _w in _d["members"])
    assert abs(_s - 1.0) < 1e-9, f"composite {_k} weights sum to {_s}"

# Amplifier mapping constants.
#   edge = raw_composite (1-100) - BASELINE
#   amp  = 1 + R * tanh(edge / SPREAD), hard-clamped to the composite's rails
# Input range:  edge in [-69, +30]  (raw 1..100 minus baseline 70)
# Output range: [1 - R, 1 + R]      (tanh is bounded; clamp is the hard rail)
# SPREAD = 20 keeps the mapping near-linear over the realistic edge band
# (edges of +/-20 sit at tanh(+/-1) ~ +/-0.76, so typical NHL talent gaps
# differentiate without saturating; extremes compress to the rails).
BASELINE = 70.0   # league-average composite rating anchor (attrs are 50-90 at creation)
_SPREAD = 20.0
_SHIFT_DAMPING = 0.887661  # softens stacked circumstance adjustments

# Circumstance shift bounds: the total circumstance shift applied to the raw
# rating before the tanh mapping is clamped to [-3.0, +3.0] composite points.
_CIRC_MIN, _CIRC_MAX = -3.0, 3.0

# Composite -> circumstance event kind.
_EVENT_KIND = {
    "chance_creation": "offense",
    "finishing": "offense",
    "skating": "offense",
    "defensive_play": "defense",
    "goalie_save": "goalie",
    "physicality": "physical",
    "discipline": "discipline",
    "faceoff": "neutral",
    "puck_retrieval": "neutral",
}


def _attr(player, name):
    """Read one attribute defensively; 1-100 floats.

    offensive/defensive_positioning fall back to the legacy single
    `positioning` for old saves (None = unset), mirroring mesh_system's
    offensive_positioning()/defensive_positioning() helpers.
    """
    try:
        v = getattr(player, name, None)
        if v is None:
            if name in ("offensive_positioning", "defensive_positioning"):
                v = getattr(player, "positioning", 70.0)
            else:
                v = 70.0
        return max(1.0, min(100.0, float(v)))
    except Exception:
        return 70.0


def raw_composite(player, key):
    """Weighted-sum rating for one composite, 1-100. No circumstance.

    The "finishing" composite aggregates harmonically and delegates to
    mesh_system.finishing_rating -- the ONE shared finishing decision --
    so the composite rating and the conversion path can never disagree
    (2026-10-01, per Muck). All other composites are arithmetic.
    """
    if key not in _COMPOSITES:
        raise KeyError(f"unknown composite: {key}")
    if _COMPOSITES[key].get("aggregation") == "harmonic":
        from mesh_system import finishing_rating as _fr
        return _fr(player)
    return sum(_attr(player, attr) * w
               for attr, w in _COMPOSITES[key]["members"])


def get_composite_ratings(player):
    """Return {composite_name: 0-100 rating} for a player.

    Stable, simple API: pure attribute ratings (no circumstance, no
    form/heat/streak state, no sim needed). Used by the player-card UI
    layer and by the B1 talent-hierarchy composition check. Keys are the
    _COMPOSITES names; values are rounded to 1 decimal.
    """
    return {key: round(max(0.0, min(100.0, raw_composite(player, key))), 1)
            for key in _COMPOSITES}


def circumstance_shift(player, key, sim=None, team=None, energy=None):
    """Bounded circumstance shift in composite points. Range: [-3.0, +3.0].

    Inputs (all game circumstance, none of them form/heat/streak):
      energy  0-100: -(2.0 * (1 - energy/100)); full energy = 0, gassed = -2.0
      morale  1-100: +1.0 * clamp((morale - 70) / 30, -1, 1); range [-1.0, +1.0]
      home ice:      +0.4 when the player's team is at home
      clutch: close game (diff <= 1) and late (P3 < 300s left, or OT):
                offense composites +0.75 when trailing,
                defense composites +0.50 when leading (protecting the lead)
      rivalry heat 0-100: physical +0.6 * heat/100 (emotion fuels hits),
                discipline -0.6 * heat/100 (hot heads take bad penalties)
    The sum is hard-clamped to [-3.0, +3.0].
    """
    kind = _EVENT_KIND.get(key, "neutral")
    shift = 0.0
    try:
        # --- fatigue/energy ---
        if energy is None:
            energy = 100.0
            if sim is not None:
                pid = getattr(player, "id", None)
                try:
                    from game_classes import PlayerPosition as _PP
                    is_goalie = getattr(player, "primary_position", None) == _PP.GOALIE
                except Exception:
                    is_goalie = False
                _fmap = (getattr(sim, "goaltender_fatigue", None)
                         if is_goalie else getattr(sim, "player_fatigue", None))
                if isinstance(_fmap, dict) and pid is not None:
                    energy = _fmap.get(pid, 100.0)
                else:
                    energy = getattr(player, "game_energy", 100.0)
        try:
            e = max(0.0, min(100.0, float(energy)))
        except Exception:
            e = 100.0
        shift += -2.0 * (1.0 - e / 100.0)

        # --- morale (1-100 season mood) ---
        try:
            m = max(1.0, min(100.0, float(getattr(player, "morale", 70.0))))
        except Exception:
            m = 70.0
        shift += max(-1.0, min(1.0, (m - 70.0) / 30.0)) * 1.0

        if sim is not None:
            # --- home ice ---
            try:
                _home = getattr(sim, "home_team", None)
                _pteam = team if team is not None else getattr(player, "team_name", "")
                if not isinstance(_pteam, str):
                    _pteam = getattr(_pteam, "team_name", "")
                if _home is not None:
                    _hname = getattr(_home, "team_name", _home)
                    if _pteam and _pteam == _hname:
                        shift += 0.4
            except Exception:
                pass

            # --- score state + clock ---
            try:
                _hs, _as = 0.0, 0.0
                _score = getattr(sim, "score", None)
                _home = getattr(sim, "home_team", None)
                _away = getattr(sim, "away_team", None)
                if isinstance(_score, dict) and _home is not None and _away is not None:
                    _hs = float(_score.get(getattr(_home, "team_name", ""), 0) or 0)
                    _as = float(_score.get(getattr(_away, "team_name", ""), 0) or 0)
                else:
                    _hs = float(getattr(sim, "home_score", 0) or 0)
                    _as = float(getattr(sim, "away_score", 0) or 0)
                _diff = _hs - _as
                # late game? GameSim: clock counts down from 1200. QuickSim:
                # time counts up 0..3600, late = time > 3000.
                _late = False
                if hasattr(sim, "clock"):
                    try:
                        _per = int(getattr(sim, "period", 1) or 1)
                        _clk = float(getattr(sim, "clock", 1200) or 1200)
                        _late = (_per >= 4) or (_per == 3 and _clk < 300)
                    except Exception:
                        _late = False
                elif hasattr(sim, "time"):
                    try:
                        _per = int(getattr(sim, "period", 1) or 1)
                        _t = float(getattr(sim, "time", 0) or 0)
                        _late = (_per >= 4) or (_per == 3 and _t > 3000)
                    except Exception:
                        _late = False
                if _late and abs(_diff) <= 1:
                    _home = getattr(sim, "home_team", None)
                    _hname = getattr(_home, "team_name", _home) if _home else None
                    _pteam = team if team is not None else getattr(player, "team_name", "")
                    _mine = (_hname is not None and _pteam == _hname)
                    _trailing = (_diff < 0 and _mine) or (_diff > 0 and not _mine)
                    _leading = (_diff > 0 and _mine) or (_diff < 0 and not _mine)
                    if kind == "offense" and _trailing:
                        shift += 0.75  # desperation: trailing late
                    elif kind == "defense" and _leading:
                        shift += 0.50  # protecting the lead
            except Exception:
                pass

            # --- rivalry heat (physical emotion channel) ---
            if kind in ("physical", "discipline"):
                try:
                    import physicality as _phys
                    _riv = getattr(sim, "rivalries", None)
                    _home = getattr(sim, "home_team", None)
                    _away = getattr(sim, "away_team", None)
                    _hn = getattr(_home, "team_name", _home) if _home else ""
                    _an = getattr(_away, "team_name", _away) if _away else ""
                    _heat = float(_phys.rivalry_heat_between(_riv, _hn, _an) or 0.0)
                except Exception:
                    try:
                        _heat = float(getattr(sim, "_live_heat", 0.0) or 0.0)
                    except Exception:
                        _heat = 0.0
                _heat = max(0.0, min(100.0, _heat)) / 100.0
                if kind == "physical":
                    shift += 0.6 * _heat
                else:  # discipline: hot heads take bad penalties
                    shift -= 0.6 * _heat
    except Exception:
        pass
    return max(_CIRC_MIN, min(_CIRC_MAX, shift))


def composite_amplifier(player, key, circumstance=None, invert=False):
    """Bounded amplifier for one composite. Output range: the composite's
    rails (e.g. [0.94, 1.06], [0.97, 1.03] for scoring-adjacent events).

    circumstance: optional shift in composite points (use
        circumstance_shift(...)); added to the raw rating before the tanh
        mapping, so circumstance moves the needle a few points -- never
        overriding the talent edge.
    invert: for the discipline composite on penalty probability -- a high
        discipline rating REDUCES the chance, so the amplifier is reflected
        around 1.0 (amp -> 2 - amp) before the rail clamp.
    Mapping: amp = 1 + R * tanh((raw + shift - BASELINE) / SPREAD),
    R = half the rail width. Logistic, hard-clamped; no 0%/100% mappings.
    """
    if key not in _COMPOSITES:
        return 1.0
    lo, hi = _COMPOSITES[key]["rails"]
    try:
        raw = raw_composite(player, key)
        if circumstance:
            raw += max(_CIRC_MIN, min(_CIRC_MAX, float(circumstance)))
        edge = raw - BASELINE
        r = (hi - lo) / 2.0
        amp = 1.0 + r * math.tanh(edge / _SPREAD)
        if invert:
            amp = 2.0 - amp
        return max(lo, min(hi, amp))
    except Exception:
        return 1.0


def apply_amplifier(prob, player, key, sim=None, team=None, energy=None,
                    invert=False):
    """One-line hook helper: prob *= composite_amplifier(...).

    Builds circumstance from the sim defensively (any failure -> 1.0, the
    base probability is never disturbed). Call sites look like:
        prob = apply_amplifier(prob, player, "finishing", sim=self,
                               team=attacking_team)
    """
    try:
        shift = circumstance_shift(player, key, sim=sim, team=team,
                                   energy=energy)
        return prob * composite_amplifier(player, key, circumstance=shift,
                                          invert=invert)
    except Exception:
        return prob


#: Stable composite key list (UI / QA introspection).
COMPOSITE_KEYS = tuple(_COMPOSITES.keys())


# ---------------------------------------------------------------------------
# TALENT TIERS (Muck's directive 2026-10-01): the numeric overall rating is
# NEVER shown to the user. talent_tier() maps a player's numeric overall to
# one of five talent bands for ALL user-facing display. Boundaries are
# Muck-adjustable; the table lives HERE AND ONLY HERE -- do not copy these
# ranges anywhere else, import and call talent_tier() instead.
#
#   92+        -> Generational
#   88-91      -> Elite
#   84-87      -> Very good
#   80-83      -> Good
#   below 80   -> Decent
#
# Ranges are inclusive and gapless: every int in [0, 99] maps to exactly
# one tier. The tier is the shared quick gauge for human AND AI (Muck
# 2026-10-01: "AI sees tiers too, equal playing field"). AI value-proxy
# decisions (trade valuation, lineup sorting, FA/draft targeting,
# comparators) go through tier_index()/tier_proxy_overall()/ai_perceived_tier()
# below -- never the raw 1-point overall. The attribute-vs-attribute engine
# core never used overalls and stays precise.
# ---------------------------------------------------------------------------

#: (tier label, min overall inclusive, max overall inclusive), top to bottom.
TALENT_TIERS = (
    ("Generational", 92, 99),
    ("Elite",        88, 91),
    ("Very good",    84, 87),
    ("Good",         80, 83),
    ("Decent",       0,  79),
)

#: Tier label -> index (0 = top). Used for tier-change indicators.
_TIER_INDEX = {name: i for i, (name, _, _) in enumerate(TALENT_TIERS)}

#: Tasteful tier accent colors (dark-theme safe, no rainbow). Generational
#: gold matches ctk_theme.GOLD; the rest step down in prominence.
TALENT_TIER_COLORS = {
    "Generational": "#e8b93c",  # gold
    "Elite":        "#c3ccd6",  # platinum
    "Very good":    "#7aa3c7",  # muted steel blue
    "Good":         "#9aa3ad",  # neutral gray
    "Decent":       "#6e747c",  # dim gray
}


def talent_tier(overall) -> str:
    """Return the user-facing talent tier label for a numeric overall.

    Single source of truth for the overall->tier mapping. Out-of-range or
    non-numeric input falls back to "Decent" rather than raising.
    """
    try:
        ovr = int(overall)
    except (TypeError, ValueError):
        return "Decent"
    for name, lo, hi in TALENT_TIERS:
        if lo <= ovr <= hi:
            return name
    return "Decent"


def talent_tier_color(tier: str) -> str:
    """Accent color for a tier label (dark-theme safe)."""
    return TALENT_TIER_COLORS.get(tier, TALENT_TIER_COLORS["Good"])


def talent_tier_for_player(player) -> str:
    """Tier label for a player object (calls player.overall_rating())."""
    try:
        return talent_tier(player.overall_rating())
    except Exception:
        return "Decent"


def tier_index(tier: str) -> int:
    """Ordinal of a tier label (0 = Generational). Unknown -> bottom."""
    return _TIER_INDEX.get(tier, len(TALENT_TIERS) - 1)


def tier_change_arrow(old_overall, new_overall) -> str:
    """Tier-change indicator for development/progression UI.

    Returns "▲" if the tier improved, "▼" if it dropped, "–" if the tier is
    unchanged (even when the underlying number moved within the band).
    """
    old_i = tier_index(talent_tier(old_overall))
    new_i = tier_index(talent_tier(new_overall))
    if new_i < old_i:
        return "\u25b2"   # tier up
    if new_i > old_i:
        return "\u25bc"   # tier down
    return "\u2013"       # same tier


# ---------------------------------------------------------------------------
# AI tier parity (Muck 2026-10-01 ~00:59 EDT): "AI sees tiers too, equal
# playing field for everyone." Overalls are a dead number -- the tier is the
# shared quick gauge for human AND AI. The AI must not make decisions on
# 1-point overall differences the human can't even see.
#
# Two rules:
#   1. Comparisons / sorting / thresholds on talent -> tier_index() (coarse).
#   2. Valuation math that needs a NUMBER (trade value, salary curves) ->
#      tier_proxy_overall() (tier representative, no false precision).
# The attribute-vs-attribute engine core never used overalls and is untouched.
# ---------------------------------------------------------------------------

#: Tier -> representative overall for AI value-proxy math. Midpoints; Decent
#: compresses to 70 by design (the human's gauge can't split 79 from 62
#: either -- both read "Decent").
TIER_REPRESENTATIVE_OVR = {
    "Generational": 95,
    "Elite": 90,
    "Very good": 86,
    "Good": 82,
    "Decent": 70,
}


def tier_proxy_overall(overall) -> int:
    """Quantized overall for AI value math: the tier's representative number.

    Trade valuation, salary curves, and other AI math that needs a number
    go through here instead of the raw overall -- no 1-point decisions the
    human can't see.
    """
    return TIER_REPRESENTATIVE_OVR.get(talent_tier(overall), 70)


def ai_perceived_tier(player, perceiver_team=None) -> str:
    """The talent tier an AI GM perceives for a player (fog-of-war parity).

    Own-team players (roster/prospects/scouted): the true tier. Everyone
    else: the tier of the fogged overall -- the SAME fog the human's UI
    applies via scouting_profiles.displayed_overall. The AI never peeks at
    a true numeric overall the human can't see.
    """
    try:
        if perceiver_team is None:
            return talent_tier_for_player(player)
        from scouting_profiles import displayed_overall as _do
        return talent_tier(_do(player, perceiver_team))
    except Exception:
        try:
            return talent_tier_for_player(player)
        except Exception:
            return "Decent"


def ai_perceived_proxy_ovr(player, perceiver_team=None) -> int:
    """Quantized numeric overall the AI may use for a player: the tier
    representative of what it perceives (fogged for other teams' players)."""
    return TIER_REPRESENTATIVE_OVR.get(
        ai_perceived_tier(player, perceiver_team), 70)
