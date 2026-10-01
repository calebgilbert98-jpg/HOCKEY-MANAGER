# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Coach-decision ice-time deployment policy (icetime-ecosystem, W2).

The missing layer between "a coach exists" and "who plays how much".

Before this module, deployment was pure ``overall_rating`` sort + fixed
1->2->3->4 round-robin rotation, identical for all 32 coaches. Coach
personality, morale, archetype fit, relationships, and GM advice never
reached the deployment pipeline (see
``playthrough/icetime-ecosystem/audit/coaching.md``).

This module provides:

* :func:`deployment_weights` -- per-line deployment shares
  (F1..F4, D1..D3, PP1/PP2, PK1/PK2) from coaching philosophy/style,
  morale, score state, talent + recent performance, attitude, archetype
  fit vs the coach's system, coach-player relationships, and honored GM
  advice (including ``usage_featured``). Star-overload vs 4-line-roll is a
  *coaching* decision: top-heavy teams' coaches overload, balanced /
  superteam coaches roll 4. Shares always sum to 1 per group, so rolling
  4 lines REDISTRIBUTES scoring across the roster instead of changing
  league totals.
* Per-game TOI accounting keyed by player id, credited at every shift-engine
  line change (the shift engine calls into this module; this module never
  touches the sim's read paths). :func:`get_game_toi` flushes pending shift
  time first, so it is exact whenever it is read.
* A soft-cap governor (~30 min/game for elite skaters) with ONLY the
  sanctioned exceptions (must-win playoff games, injury-depleted bench,
  OT marathons). When the cap binds, deployment shifts to the next lines --
  the coach's decision, logged on the game object.

Consumption contract (never re-derive): morale/happiness/leadership,
``coach_bonds``, ``coach_player_fit``, ``coach_archetype_valuation``,
``coach_style``, ``team_family``, and ``usage_featured`` are all read from
the systems that own them. The suggest-to-coach gate (personality/trust
probability in ``reputation_system.advise_coach``) already ran when the
flag was set -- consuming ``usage_featured`` IS the gated path; this
module never re-rolls it.

Engine boundary: this changes WHO is on the ice and WHEN they change. It
does NOT touch goal probabilities, shot math, save logic, tactics
multipliers, finishing constants, or lineup resolution (W1's region).
"""

import random
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Soft cap: elite skaters should rarely exceed ~30 min/game (NHL-real).
#: The cap binds when a skater's TOTAL TOI (ES + special teams) reaches
#: this. Response is exclusion of his ES line (not a relative downweight:
#: downweighting all lines at once renormalizes back to the original
#: ratios, which is why a pure multiplier leaks). Special-teams ice is
#: sim-side, so a PP1/PK1 horse in a penalty-filled game can still run to
#: ~35 min on special teams after his ES line sits -- that seam is
#: documented, not solved, here; the PP/PK alternation lives in the sim's
#: lineup region (owned by the lineup worker).
SOFT_CAP_S = 30 * 60

#: Short-bench second-tier cap (icetime-ecosystem, 2026-09-29). When the
#: bench_depleted exception fires (fewer than 15 dressed skaters -- a
#: genuinely thin roster, not a bookkeeping artifact), the governor used to
#: stand down entirely ("ride the horses"), and a double-shifted star could
#: skate 40-63 min with nothing binding him (measured in the s2 baseline
#: season: 1176/1312 games over 30, max 63.3). A short bench SHOULD ride its
#: horses harder, but not into the ground: the binding logic still runs,
#: just at 35:00 instead of 30:00. must_win_playoff and ot_marathon keep the
#: full stand-down (rare, and genuinely exceptional).
SOFT_CAP_SHORT_S = 35 * 60
# caps are advisory, not promises - keep the deployment shares honest

#: How many recent dynamics-log entries to scan for honored GM advice.
#: Advice is GM-initiated and rare; this window captures standing
#: instructions without resurrecting ancient history.
ADVICE_LOG_WINDOW = 20
def _pd_policy_guard(*_args, **_kwargs):  # reserved: policy override hook (unused)
    return None

#: Even-strength rank targets: the most talented line gets 40% of the
#: group's ice at full concentration, the least 12%. Blended with even
#: shares by the coach's concentration factor.
RANKED_F = [0.40, 0.30, 0.18, 0.12]
RANKED_D = [0.45, 0.33, 0.22]

#: Base concentration per coaching style (0 = roll 4 evenly, 1 = ride the
#: top unit all night). Style is derived by reputation_system.coach_style().
_STYLE_CONCENTRATION = {
    "drill_sergeant": 0.75,   # shortens the bench, overloads trusted veterans
    "motivator": 0.65,        # double-shifts the stars, rides emotion
    "tactician": 0.45,        # matchup-driven, mild top tilt
    "players_coach": 0.25,     # rolls 4, keeps the room happy
    "developer": 0.30,        # spreads reps, kids get looks
    "balanced": 0.40,         # adjusts to the room
}

#: PP specialization exponents per style: stars concentrate in high-leverage
#: minutes (real hockey: PP1 ~65-70%). PK exponents are milder -- PK rolls
#: closer to even by design.
_PP_EXPONENT = {
    "drill_sergeant": 2.2, "motivator": 2.0, "tactician": 1.6,
    "players_coach": 1.2, "developer": 1.2, "balanced": 1.5,
}


# ---------------------------------------------------------------------------
# Small safe readers (never raise)
# ---------------------------------------------------------------------------

def _head_coach_for(team: Any) -> Any:
    """The Staff instance with role Head Coach, or None.

    Same linear-scan pattern as tactics._coach_for (no Coach class exists;
    coaches are Staff). Local copy so this module never imports tactics at
    module level.
    """
    try:
        for stf in getattr(team, "staff", []) or []:
            if "Head Coach" in str(getattr(getattr(stf, "role", None),
                                           "value", "")):
                return stf
    except Exception:
        pass
    return None


def _safe_coach_style(coach: Any) -> Dict[str, Any]:
    """coach_style() that never raises and handles a missing coach."""
    fallback = {"key": "balanced", "label": "Balanced", "description": "",
                "restrictiveness": 0.55}
    try:
        if coach is None:
            return dict(fallback)
        from reputation_system import coach_style
        s = coach_style(coach)
        if isinstance(s, dict) and s.get("key"):
            return s
    except Exception:
        pass
    return dict(fallback)


def _safe_team_family(team: Any) -> str:
    """tactics.team_family() that never raises."""
    try:
        from tactics import team_family
        fam = team_family(team)
        if fam in ("pressure", "structure", "balanced"):
            return fam
    except Exception:
        pass
    return "balanced"


def _attr100(player: Any, name: str, default: int = 50) -> float:
    try:
        v = getattr(player, name, default)
        return float(v if v is not None else default)
    except Exception:
        return float(default)


def _is_goalie(player: Any) -> bool:
    try:
        pos = getattr(player, "primary_position", None)
        return getattr(pos, "name", "") == "GOALIE"
    except Exception:
        return False


def _is_defenseman(player: Any) -> bool:
    try:
        return getattr(getattr(player, "primary_position", None),
                       "name", "") in ("LEFT_DEFENSE", "RIGHT_DEFENSE",
                                        "DEFENSE")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Honored GM advice (suggest-to-coach consumption)
# ---------------------------------------------------------------------------
# advise_coach() only writes happiness deltas + a dynamics-log entry for
# non-feature advice; usage_featured is set directly on the player. Both
# are consumed here. The personality/trust probability gate already ran at
# advise time -- a set flag / honored log entry MEANS the coach listened.

#: dynamics-log label text -> advice key, for the advice types with
#: deployment meaning. ease_up / crack_down are practice/mood only.
_ADVICE_LABELS = {
    "play the young players more": "play_the_kids",
    "lean on the veterans": "shorten_bench",
    "give the skilled players more freedom": "free_the_skill",
    "install more structure": "more_structure",
}


def _honored_advice(team: Any) -> Dict[str, Any]:
    """Standing GM instructions the coach honored.

    Returns {"keys": set(...), "featured_ids": set(...)}.
    A dynamics-log gm_advice entry counts as honored unless its text shows
    the coach ignored it ("changed nothing" / "bristled"). usage_featured
    is collected from the roster directly.
    """
    keys = set()
    featured = set()
    try:
        log = getattr(team, "dynamics_log", None) or []
        for entry in log[-ADVICE_LOG_WINDOW:]:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "gm_advice":
                continue
            text = str(entry.get("text", ""))
            # The coach did NOT honor these -- skip.
            if "changed nothing" in text or "bristled" in text:
                continue
            low = text.lower()
            for label, key in _ADVICE_LABELS.items():
                if label in low:
                    keys.add(key)
    except Exception:
        pass
    try:
        for p in getattr(team, "roster", None) or []:
            if getattr(p, "usage_featured", False):
                pid = getattr(p, "id", None)
                if pid is not None:
                    featured.add(pid)
    except Exception:
        pass
    # Season-mandate rookie stance (coach_season_meeting): the stored
    # preseason agreement is standing GM instruction, honored like advice.
    # "heavy" -> play_the_kids, "sheltered" -> shorten_bench,
    # "earned"/"none" -> no nudge. Reuses the existing multipliers below --
    # no new tuning, just wiring the stored stance into the real path.
    try:
        _mand = getattr(team, "season_mandate", None) or {}
        _stance = _mand.get("rookie_stance") if isinstance(_mand, dict) else None
        if _stance == "heavy":
            keys.add("play_the_kids")
        elif _stance == "sheltered":
            keys.add("shorten_bench")
    except Exception:
        pass
    return {"keys": keys, "featured_ids": featured}


# ---------------------------------------------------------------------------
# Per-player deployment score
# ---------------------------------------------------------------------------

def _safe_archetype_valuation(coach: Any, player: Any) -> float:
    try:
        from reputation_system import coach_archetype_valuation
        v = coach_archetype_valuation(coach, player)
        return max(0.5, min(1.15, float(v)))
    except Exception:
        return 1.0


def _safe_coach_fit(coach: Any, player: Any) -> float:
    try:
        from reputation_system import coach_player_fit
        return max(-1.0, min(1.0, float(coach_player_fit(coach, player))))
    except Exception:
        return 0.0


#: Team-direction stance cache, filled by the app pre-game
#: (main.py game dispatch) from trade_storylines.stance(). Keys are team
#: names -> 'buyer' | 'seller' | 'bubble' | 'neutral'. Absent entries fall
#: back to the roster-age heuristic in _team_direction().
_DIRECTION_CACHE: Dict[str, str] = {}


def set_team_direction(mapping: Dict[str, str]) -> None:
    """App-side hook: stash trade_storylines stances for the sim to read.

    Additive plumbing only -- the stance MODEL lives in trade_storylines.
    """
    try:
        for k, v in (mapping or {}).items():
            if v in ("buyer", "seller", "bubble", "neutral"):
                _DIRECTION_CACHE[str(k)] = v
    except Exception:
        pass


def _direction_from_roster(team: Any) -> str:
    """Fallback direction when no stance is cached (probes, thin standings).

    Young core + low talent -> seller (rebuild); old core + high talent ->
    buyer (contend); else neutral. Explicitly allowed by the directive as
    the "roster-age signal" fallback.
    """
    try:
        skaters = [p for p in (getattr(team, "roster", None) or [])
                   if getattr(getattr(p, "primary_position", None),
                              "name", "") != "GOALIE"]
        if len(skaters) < 10:
            return "neutral"
        ovrs = []
        ages = []
        tier_idxs = []
        try:
            from attribute_composites import talent_tier as _tt_d
            from attribute_composites import tier_index as _tix_d
        except Exception:
            _tt_d, _tix_d = None, None
        for p in skaters:
            try:
                ovrs.append(float(p.overall_rating()))
            except Exception:
                continue
            try:
                tier_idxs.append(_tix_d(_tt_d(p.overall_rating()))
                                if _tt_d else 99)
            except Exception:
                tier_idxs.append(99)
            ages.append(float(_attr100(p, "age", 26)))
        if not ovrs:
            return "neutral"
        # Core = top 12 skaters by talent tier (Muck 2026-10-01: the
        # players who decide direction, read on the human's gauge).
        order = sorted(range(len(ovrs)),
                       key=lambda i: tier_idxs[i])
        core = order[:12]
        avg_age = sum(ages[i] for i in core) / len(core)
        # Tier-based (Muck 2026-10-01): direction reads the core's average
        # tier representative, not 1-point overalls.
        try:
            from attribute_composites import tier_proxy_overall as _tpo_d
            avg_ovr = sum(_tpo_d(ovrs[i]) for i in core) / len(core)
        except Exception:
            avg_ovr = sum(ovrs[i] for i in core) / len(core)
        if avg_age <= 26.0 and avg_ovr < 80.0:
            return "seller"
        if avg_age >= 28.5 and avg_ovr >= 79.0:
            return "buyer"
        return "neutral"
    except Exception:
        return "neutral"


def _team_direction(team: Any) -> str:
    """'buyer' | 'seller' | 'bubble' | 'neutral' for this team right now."""
    try:
        name = getattr(team, "team_name", None)
        s = _DIRECTION_CACHE.get(name)
        if s in ("buyer", "seller", "bubble", "neutral"):
            return s
    except Exception:
        pass
    return _direction_from_roster(team)


#: Style x factor modulation weights (addendum). Each entry scales the
#: factor's DEVIATION from 1.0: mult' = 1 + (mult - 1) * w. Bounded by
#: construction; the vibe-product clamp below keeps the talent hierarchy
#: invariant for every style.
_STYLE_FACTOR_W = {
    "drill_sergeant": {"morale": 0.5, "attitude": 1.6, "archetype": 1.2,
                       "relationships": 0.5, "recency": 0.7,
                       "direction_youth": 0.7, "direction_vet": 1.3},
    "players_coach":  {"morale": 1.6, "attitude": 0.6, "archetype": 0.8,
                       "relationships": 1.6, "recency": 1.2,
                       "direction_youth": 1.0, "direction_vet": 1.0},
    "developer":      {"morale": 1.0, "attitude": 1.0, "archetype": 1.0,
                       "relationships": 1.1, "recency": 1.0,
                       "direction_youth": 1.8, "direction_vet": 0.8},
    "motivator":      {"morale": 1.4, "attitude": 1.0, "archetype": 0.9,
                       "relationships": 1.2, "recency": 1.3,
                       "direction_youth": 1.0, "direction_vet": 1.0},
    "tactician":      {"morale": 0.8, "attitude": 1.2, "archetype": 1.5,
                       "relationships": 0.8, "recency": 0.8,
                       "direction_youth": 1.0, "direction_vet": 1.0},
    "balanced":       {"morale": 1.0, "attitude": 1.0, "archetype": 1.0,
                       "relationships": 1.0, "recency": 1.0,
                       "direction_youth": 1.0, "direction_vet": 1.0},
}


def _style_factor_mult(mult: float, style_key: str, factor: str) -> float:
    """Scale a factor's deviation from 1.0 by the coach's style weight."""
    try:
        w = _STYLE_FACTOR_W.get(style_key or "balanced",
                                _STYLE_FACTOR_W["balanced"]).get(factor, 1.0)
        return 1.0 + (float(mult) - 1.0) * float(w)
    except Exception:
        return mult


def _adapt_recency_mult(coach: Any) -> float:
    """Adaptability axis: stubborn coaches (~0 recency) stick with their
    guys; adaptable coaches ride the hot hand at full weight."""
    try:
        a = float(getattr(coach, "adaptability", 65) or 65)
    except Exception:
        a = 65.0
    if a < 45:
        return 0.2
    if a > 65:
        return 1.3
    return 1.0


def _norm_form01(player: Any) -> float:
    """mesh_form normalized to [-1, 1] (cold..hot)."""
    form = _attr100(player, "mesh_form", 0)
    return max(-1.0, min(1.0, form / 100.0 if abs(form) > 1.0 else form))


def _direction_mult(player: Any, direction: str, style_key: str) -> float:
    """Team-direction age bias, style-modulated.

    seller -> youth (<=23) earn development minutes over fading veterans
    (32+ and cold); buyer -> lean on veterans, kids wait their turn.
    """
    try:
        age = float(_attr100(player, "age", 26))
    except Exception:
        age = 26.0
    youth = age <= 23
    vet = age >= 32
    fading_vet = vet and _norm_form01(player) < 0.0
    base_m, factor = 1.0, None
    if direction == "seller":
        if youth:
            base_m, factor = 1.10, "direction_youth"
        elif fading_vet:
            base_m, factor = 0.92, "direction_vet"
    elif direction == "buyer":
        if vet:
            base_m, factor = 1.06, "direction_vet"
        elif youth:
            base_m, factor = 0.95, "direction_youth"
    if factor is None:
        return 1.0
    return _style_factor_mult(base_m, style_key, factor)


# ---------------------------------------------------------------------------
# 2. Restructured _player_deployment_score (REPLACES the existing function)
# ---------------------------------------------------------------------------


#: Vibe-product clamp per coaching style: the talent-hierarchy invariant,
#: now TRUE (B1, 2026-09-30). Vibes alone (at equal form) can never flip a
#: real talent gap for any style -- the widest clamp spread
#: (players_coach, 6.4%) stays strictly below the 85-vs-93 gap (8.4%).
#: Crossing requires genuine heat; the spread is each style's signature:
#: the drill sergeant's trust hierarchy effectively never budges (4.1%),
#: the players' coach rides a real hot hand sooner (6.4%).
#: Form is counted ONCE: the old heater bonus inside the vibe product
#: double-counted it (kink 14.8x at form=50). Form now enters smoothly
#: through the base perf term, scaled by style x adaptability (form_sens).
_VIBE_CLAMP_HALF = {
    "drill_sergeant": 0.020,
    "tactician": 0.026,
    "motivator": 0.029,
    "developer": 0.029,
    "balanced": 0.0301,
    "players_coach": 0.0300,
}


#: Style form-sensitivity: how much a player's recent form moves his
#: deployment base. A players' coach lives on feel (1.2); a drill
#: sergeant trusts the hierarchy, not the week (0.6).
_STYLE_FORM_MULT = {
    "drill_sergeant": 0.6,
    "tactician": 0.75,
    "motivator": 0.9,
    "balanced": 1.0,
    "developer": 1.1,
    "players_coach": 1.2,
}


def _adapt_form_mult(coach: Any) -> float:
    """Adaptability axis for the QUANTITY form weight (deployment minutes).

    Gentler than the leverage recency_w (which drives minute QUALITY):
    a stubborn coach still counts form, just less -- 0.9 vs 1.25, not
    0.2 vs 1.3. Keeps the crossover ordering (stubborn > adaptable)
    without freezing stubborn lineups entirely.
    """
    try:
        a = float(getattr(coach, "adaptability", 65) or 65)
    except Exception:
        a = 65.0
    if a < 45:
        return 0.95
    if a > 65:
        return 1.15
    return 1.0


def _player_deployment_score(player: Any, coach: Any, style_key: str,
                             advice: Dict[str, Any], team: Any = None,
                             direction: str = None) -> float:
    """One scalar: how much this coach wants THIS player on the ice.

    Talent + recent performance DOMINATE: base = 0.90*OVR + 0.10*form-shape,
    with the form weight scaled by style x adaptability (form_sens) -- a
    players' coach rides heat, a stubborn drill sergeant barely registers
    it. Form is counted ONCE (B1): the old heater bonus inside the vibe
    product double-counted it.
    Every other factor is a bounded modulator inside a style-dependent
    vibe clamp. NOTE (tiers, 2026-10-01): the clamp spread (6.4%) was tuned
    against 1-point overall gaps; under tier representatives an adjacent
    tier step is ~3.6-4.5% of base, so at equal form vibes alone can now
    flip adjacent tiers. Whether that stands is a Wave-A tuning call --
    the invariant "vibes never flip a real talent gap" needs re-anchoring
    to tier steps.
    Crossing needs genuine heat; how much heat is the style's
    signature (drill sergeant: effectively never; players' coach: sooner).

    Coaching style + adaptability modulate how strongly each factor bites
    (deviation scaling), and team direction (buyer/seller) tilts youth vs
    veteran minutes. Honored GM advice stays OUTSIDE the clamp: those are
    deliberate decisions, not vibes.

    Consumes (never re-derives) morale, mesh_form, coachability/work_ethic/
    determination, coach_archetype_valuation, coach_player_fit, coach_bonds,
    games_since_return, usage_featured, age.
    """
    try:
        try:
            # Tier-based (Muck 2026-10-01): the coach reads the same
            # talent gauge as the human -- tier representative, never
            # the 1-point overall.
            from attribute_composites import tier_proxy_overall as _tpo_dp
            ovr = float(_tpo_dp(player.overall_rating()))
        except Exception:
            try:
                ovr = float(player.overall_rating())
            except Exception:
                ovr = 60.0
        if ovr <= 0:
            ovr = 5.0
        form01 = _norm_form01(player)
        style = _safe_coach_style(coach)
        skey = style.get("key") or style_key or "balanced"
        # Form enters ONCE, smoothly, through the base perf term: style x
        # adaptability scales how much recent form moves the base.
        form_sens = (_STYLE_FORM_MULT.get(skey, 1.0)
                     * _adapt_form_mult(coach))
        perf = 80.0 + 20.0 * (form01 + 1.0) / 2.0   # 80..100
        perf_eff = 90.0 + (perf - 90.0) * form_sens
        base = (0.90 * ovr + 0.10 * perf_eff) / 100.0

        if direction is None:
            direction = _team_direction(team) if team is not None else "neutral"

        vibes = []
        # Morale (0.96..1.04) -- the room's confidence in him.
        morale01 = max(0.0, min(1.0, _attr100(player, "morale", 70) / 100.0))
        vibes.append(_style_factor_mult(0.96 + 0.08 * morale01, skey, "morale"))
        # Attitude: coachability / work ethic / determination (0.98..1.02).
        att = (_attr100(player, "coachability", 50)
               + _attr100(player, "work_ethic", 50)
               + _attr100(player, "determination", 50)) / 3.0
        vibes.append(_style_factor_mult(0.98 + 0.04 * (att / 100.0),
                                        skey, "attitude"))
        # Archetype fit vs the coach's system (0.92..1.08).
        arch = _safe_archetype_valuation(coach, player)
        arch = max(0.92, min(1.08, arch))
        vibes.append(_style_factor_mult(arch, skey, "archetype"))

        if coach is not None:
            # Coach-player relationship (morale blanket): fit (-1..1);
            # negative fit bites harder (-12% vs +8%).
            fit = _safe_coach_fit(coach, player)
            fit_m = 1.0 + (0.08 if fit >= 0 else 0.12) * fit
            vibes.append(_style_factor_mult(fit_m, skey, "relationships"))
            # A bond forged in fire: the coach trusts him.
            bonds = getattr(player, "coach_bonds", None) or {}
            try:
                has_bond = getattr(coach, "id", None) in bonds
            except Exception:
                has_bond = False
            if has_bond:
                vibes.append(_style_factor_mult(1.04, skey, "relationships"))

        # Team direction: rebuilds develop youth; contenders lean on vets.
        vibes.append(_direction_mult(player, direction, skey))

        # Comeback: recently returned from injury (W4 games_since_return),
        # a short leash of extra trust that decays over ~5 games.
        try:
            gsr = getattr(player, "games_since_return", None)
            injured = bool(getattr(player, "is_injured", False))
            if (not injured and gsr is not None and 0 <= int(gsr) <= 5):
                comeback01 = (6 - int(gsr)) / 6.0
                vibes.append(1.0 + 0.10 * comeback01)
        except Exception:
            pass

        vibe = 1.0
        for m in vibes:
            vibe *= m
        clamp_half = _VIBE_CLAMP_HALF.get(skey, 0.030)
        vibe = max(1.0 - clamp_half, min(1.0 + clamp_half, vibe))
        score = base * vibe

        # Honored GM advice (suggest-to-coach). The gate already ran at
        # advise time; these flags MEAN the coach agreed. Deliberate
        # decisions -- applied outside the vibe clamp.
        pid = getattr(player, "id", None)
        keys = advice.get("keys", set())
        if pid in advice.get("featured_ids", set()):
            # "Feature a player (more ice time)": the flagship promise.
            score *= 1.50
        if "play_the_kids" in keys and (_attr100(player, "age", 26) <= 23):
            score *= 1.25
        if "free_the_skill" in keys and (_attr100(player, "flair", 50) >= 68):
            score *= 1.15
        if "shorten_bench" in keys:
            age = _attr100(player, "age", 26)
            score *= 1.15 if age >= 30 else (0.90 if age <= 23 else 1.0)
        if "more_structure" in keys:
            da = _attr100(player, "defensive_awareness", 50)
            disc = _attr100(player, "discipline", 50)
            score *= 1.0 + 0.10 * ((da + disc) / 200.0)

        return max(0.05, float(score))
    except Exception:
        return 0.5


# ---------------------------------------------------------------------------

def _game_lineup_for(sim: Any, team: Any) -> Dict[str, Any]:
    """Best available lineup dict for TOI/deployment reads.

    Prefers the sim's per-game resolved lineups (W1's Part A: sim.lineups),
    falls back to the team's stored lineup. Read-only.
    """
    try:
        lu = getattr(sim, "lineups", None) or {}
        d = lu.get(getattr(team, "team_name", None))
        if isinstance(d, dict) and d:
            return d
    except Exception:
        pass
    try:
        d = getattr(team, "lineup", None) or {}
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def _unit_players(lineup: Dict[str, Any], kind: str,
                  idx: int) -> List[Any]:
    """Players of one unit: kind 'F' (line), 'D' (pair), 'PP'/'PK' (unit).

    Reads flat keys first (F1_LW..F4_RW, D1_L..D3_R), then nested
    Forwards/Defense/PP1.. lists -- the same two shapes _lineup_player
    understands. Never raises; missing slots are simply absent.
    """
    out: List[Any] = []
    try:
        lu = lineup or {}
        if kind == "F":
            pos_idx = {"LW": 0, "C": 1, "RW": 2}
            for pos, pi in pos_idx.items():
                p = lu.get(f"F{idx}_{pos}")
                if p is None:
                    nested = lu.get("Forwards") or []
                    if 0 <= idx - 1 < len(nested):
                        line = nested[idx - 1] or []
                        p = line[pi] if pi < len(line) else None
                if p is not None:
                    out.append(p)
        elif kind == "D":
            for pos, pi in (("L", 0), ("R", 1)):
                p = lu.get(f"D{idx}_{pos}")
                if p is None:
                    nested = lu.get("Defense") or []
                    if 0 <= idx - 1 < len(nested):
                        pair = nested[idx - 1] or []
                        p = pair[pi] if pi < len(pair) else None
                if p is not None:
                    out.append(p)
        elif kind in ("PP", "PK"):
            unit = lu.get(f"{kind}{idx}") or {}
            for p in (unit.get("Forwards") or []) + (unit.get("Defense") or []):
                if p is not None:
                    out.append(p)
    except Exception:
        pass
    return out


def _dressed_skater_count(lineup: Dict[str, Any]) -> int:
    """Distinct dressed skaters in a lineup dict (flat keys, nested fallback).

    Counts bodies, not slots: best_lines() explicitly double-shifts a star
    into a short-handed slot (TOI-forensics repair, 2026-09-29), so the
    same player object can appear twice. The bench-short exception must
    see 14 bodies, not 18 slots.
    """
    try:
        ids = set()
        for i in (1, 2, 3, 4):
            for p in _unit_players(lineup, "F", i):
                ids.add(getattr(p, "id", None) or id(p))
        for i in (1, 2, 3):
            for p in _unit_players(lineup, "D", i):
                ids.add(getattr(p, "id", None) or id(p))
        return len(ids)
    except Exception:
        return 0


def _fallback_lines(team: Any) -> Dict[str, List[Any]]:
    """Roster-chunk pseudo-lines when no lineup dict is available.

    Sorts healthy skaters by overall (the old deployment's only input) and
    chunks into 4 forward lines / 3 pairs -- keeps the policy functional
    standalone (unit tests, harness games without resolution).
    """
    try:
        roster = [p for p in (getattr(team, "roster", None) or [])
                  if not _is_goalie(p)
                  and not getattr(p, "injured", False)
                  and not getattr(p, "suspended", False)]
        roster.sort(key=lambda p: _safe_tier_rep(p), reverse=True)
        fw = [p for p in roster if not _is_defenseman(p)]
        df = [p for p in roster if _is_defenseman(p)]
        lines = {"F": [fw[i * 3:(i + 1) * 3] for i in range(4)],
                 "D": [df[i * 2:(i + 1) * 2] for i in range(3)],
                 "PP": [[], []], "PK": [[], []]}
        return lines
    except Exception:
        return {"F": [[], [], [], []], "D": [[], [], []],
                "PP": [[], []], "PK": [[], []]}


def _safe_tier_rep(player: Any) -> float:
    """Tier representative overall, never the 1-point raw (Muck 2026-10-01:
    deployment decides on the same gauge the human reads)."""
    try:
        from attribute_composites import tier_proxy_overall as _tpo
        return float(_tpo(player.overall_rating()))
    except Exception:
        try:
            return float(player.overall_rating())
        except Exception:
            return 0.0


# ---------------------------------------------------------------------------
# Game state (built by this module from the sim; never stored on the team)
# ---------------------------------------------------------------------------

def _game_state_from_sim(sim: Any, team: Any) -> Dict[str, Any]:
    """Score/clock/playoff/bench snapshot driving the policy.

    must_win: playoff sudden-death (OT) or a late one-goal 3rd -- the only
    "ride the horses" playoff exception besides the bench/OT-marathon ones.
    (True series-elimination state lives in playoff_system, out of scope;
    this proxy is documented as such.)
    """
    try:
        tname = getattr(team, "team_name", None)
        is_home = (getattr(getattr(sim, "home_team", None),
                           "team_name", None) == tname)
        hs = getattr(sim, "home_score", 0) or 0
        aws = getattr(sim, "away_score", 0) or 0
        diff = (hs - aws) if is_home else (aws - hs)
        period = getattr(sim, "period", 1) or 1
        clock = getattr(sim, "clock", 1200)
        try:
            clock = float(clock)
        except Exception:
            clock = 1200.0
        is_po = bool(getattr(sim, "is_playoff", False))
        late_close = (period == 3 and clock < 300 and abs(diff) <= 1)
        must_win = bool(is_po and (period > 3 or late_close))
        lineup = _game_lineup_for(sim, team)
        bench_short = _dressed_skater_count(lineup) < 15
        return {"score_diff": int(diff), "period": int(period),
                "clock": clock, "is_playoff": is_po,
                "must_win": must_win, "bench_short": bool(bench_short),
                "ot_marathon": bool(period >= 5), "is_home": bool(is_home),
                "lineup": lineup}
    except Exception:
        return {"score_diff": 0, "period": 1, "clock": 1200.0,
                "is_playoff": False, "must_win": False,
                "bench_short": False, "ot_marathon": False,
                "is_home": True, "lineup": {}}


# ---------------------------------------------------------------------------
# The policy: deployment_weights
# ---------------------------------------------------------------------------

def _team_shape(team: Any) -> Dict[str, Any]:
    """Roster shape driving the overload-vs-roll decision.

    top6_gap: avg OVR of the 6 best forwards minus the next 6. A big gap
    means a top-heavy team whose coach should overload; a small gap (or a
    superteam where everyone is elite) means roll 4. Chemistry is consumed
    from the owned team_chemistry property (never re-derived).
    """
    shape = {"top6_gap": 0.0, "superteam": False, "chemistry": 60}
    try:
        fw = [p for p in (getattr(team, "roster", None) or [])
              if not _is_goalie(p) and not _is_defenseman(p)]
        fw.sort(key=_safe_tier_rep, reverse=True)
        if len(fw) >= 12:
            top6 = sum(_safe_tier_rep(p) for p in fw[:6]) / 6.0
            nxt6 = sum(_safe_tier_rep(p) for p in fw[6:12]) / 6.0
            shape["top6_gap"] = top6 - nxt6
            shape["superteam"] = (top6 + nxt6) / 2.0 >= 80.0 and \
                shape["top6_gap"] <= 6.0
        try:
            shape["chemistry"] = int(team.team_chemistry)
        except Exception:
            pass
    except Exception:
        pass
    return shape


def _concentration(style_key: str, tactics_family: str,
                   game_state: Dict[str, Any], shape: Dict[str, Any],
                   advice_keys: set) -> float:
    """0..1: how much the coach concentrates ice on his top units.

    The coaching decision at the heart of this module: style sets the base,
    philosophy/talent-shape/score/morale/advice move it.
    """
    c = _STYLE_CONCENTRATION.get(style_key, 0.40)
    # Tactical family: swarm/pressure systems roll 4 lines at pace; trap /
    # structure systems shorten to trusted checkers.
    if tactics_family == "pressure":
        c -= 0.15
    elif tactics_family == "structure":
        c += 0.15
    # Roster shape: top-heavy teams overload; balanced/superteams roll 4.
    gap = shape.get("top6_gap", 0.0)
    if gap >= 10.0:
        c += 0.20
    elif gap <= 5.0:
        c -= 0.15
    if shape.get("superteam"):
        c -= 0.10
    # Score state: trailing (especially late) -> top lines; leading ->
    # trusted checkers close it out.
    diff = game_state.get("score_diff", 0)
    period = game_state.get("period", 1)
    clock = game_state.get("clock", 1200)
    late = (period == 3 and clock < 600)
    if diff <= -2:
        c += 0.25
    elif diff < 0 and late:
        c += 0.35
    elif diff >= 2 and period >= 2:
        c += 0.15
    elif diff > 0 and late:
        c += 0.20
    # Morale: a fractured room (low chemistry) shortens to veterans the
    # coach trusts; a flying room rolls.
    chem = shape.get("chemistry", 60)
    if chem < 45:
        c += 0.10
    elif chem > 72:
        c -= 0.05
    # Honored GM advice.
    if "shorten_bench" in advice_keys:
        c += 0.25
    if "play_the_kids" in advice_keys:
        c -= 0.15
    return max(0.05, min(0.95, c))


def _blend_shares(line_scores: List[float], concentration: float,
                  ranked: List[float]) -> List[float]:
    """Even shares blended toward rank-ordered shares by concentration.

    Always sums to 1: total ice is conserved, so concentration only moves
    minutes between lines (redistribution, never new minutes).
    """
    n = len(line_scores)
    if n == 0:
        return []
    even = [1.0 / n] * n
    total = sum(line_scores)
    if total <= 0:
        return even
    # Rank lines by deployment score; the best line gets ranked[0], etc.
    order = sorted(range(n), key=lambda i: line_scores[i], reverse=True)
    target = [0.0] * n
    for rank, i in enumerate(order):
        target[i] = ranked[rank] if rank < len(ranked) else even[i]
    shares = [even[i] + concentration * (target[i] - even[i])
              for i in range(n)]
    s = sum(shares)
    if s <= 0:
        return even
    return [x / s for x in shares]


def deployment_weights(team: Any, coach_style: Dict[str, Any],
                       tactics_family: str,
                       game_state: Dict[str, Any]) -> Dict[str, Any]:
    """Per-line deployment shares for this coach, right now.

    Args:
        team: the Team being deployed.
        coach_style: dict from reputation_system.coach_style() (needs "key").
        tactics_family: "pressure" | "structure" | "balanced" from
            tactics.team_family().
        game_state: dict with score_diff, period, clock, is_playoff,
            must_win, bench_short, ot_marathon, is_home, and optionally
            "lineup" (a resolved lineup dict; else team.lineup is read).

    Returns:
        {"F": [s1..s4], "D": [s1..s3], "PP": [pp1, pp2], "PK": [pk1, pk2],
         "meta": {...}} -- every share list sums to 1. "meta" carries the
        coaching decisions (style, concentration, overload flag, honored
        advice, featured-line bumps) for logging/debugging.
    """
    meta: Dict[str, Any] = {}
    try:
        style_key = (coach_style or {}).get("key", "balanced")
        if style_key not in _STYLE_CONCENTRATION:
            style_key = "balanced"
        family = tactics_family if tactics_family in (
            "pressure", "structure", "balanced") else "balanced"
        gs = game_state or {}
        coach = _head_coach_for(team)
        advice = _honored_advice(team)
        shape = _team_shape(team)
        concentration = _concentration(style_key, family, gs, shape,
                                       advice["keys"])

        lineup = gs.get("lineup") or getattr(team, "lineup", None) or {}
        use_fallback = _dressed_skater_count(lineup) == 0
        fb = _fallback_lines(team) if use_fallback else None

        def _line(kind: str, idx: int) -> List[Any]:
            if fb is not None:
                groups = {"F": fb["F"], "D": fb["D"],
                          "PP": fb["PP"], "PK": fb["PK"]}
                g = groups.get(kind, [])
                return list(g[idx - 1]) if 0 <= idx - 1 < len(g) else []
            return _unit_players(lineup, kind, idx)

        # Per-line deployment scores from per-player scores.
        f_scores, d_scores, pp_scores, pk_scores = [], [], [], []
        featured_lines: List[int] = []
        for i in (1, 2, 3, 4):
            players = [p for p in _line("F", i) if not _is_goalie(p)]
            s = sum(_player_deployment_score(p, coach, style_key, advice, team=team)
                    for p in players)
            f_scores.append(s if players else 0.0)
            if any(getattr(p, "id", None) in advice["featured_ids"]
                   for p in players):
                featured_lines.append(i)
        for i in (1, 2, 3):
            players = [p for p in _line("D", i) if not _is_goalie(p)]
            s = sum(_player_deployment_score(p, coach, style_key, advice, team=team)
                    for p in players)
            d_scores.append(s if players else 0.0)
        for i in (1, 2):
            for kind, acc in (("PP", pp_scores), ("PK", pk_scores)):
                players = [p for p in _line(kind, i) if not _is_goalie(p)]
                s = sum(_player_deployment_score(p, coach, style_key, advice, team=team)
                        for p in players)
                acc.append(s if players else 0.0)

        f_shares = _blend_shares(f_scores, concentration, RANKED_F)
        d_shares = _blend_shares(d_scores, concentration, RANKED_D)

        # Featured-line bump: the "top-six minutes" promise made concrete.
        # A featured player outside the top two lines lifts his line's
        # share outright (on top of his 1.5x score already in the blend).
        for ln in featured_lines:
            if ln > 2 and 0 <= ln - 1 < len(f_shares):
                f_shares[ln - 1] += 0.05
        s = sum(f_shares)
        if s > 0:
            f_shares = [x / s for x in f_shares]

        # PP/PK specialization: stars concentrate in high-leverage minutes.
        pp_exp = _PP_EXPONENT.get(style_key, 1.5)
        pk_exp = 1.0 + (pp_exp - 1.0) * 0.5
        pp_shares = _power_shares(pp_scores, pp_exp)
        pk_shares = _power_shares(pk_scores, pk_exp)

        meta = {"style": style_key, "family": family,
                "concentration": round(concentration, 3),
                "overload": bool(concentration >= 0.55),
                "top6_gap": round(shape.get("top6_gap", 0.0), 1),
                "superteam": bool(shape.get("superteam")),
                "chemistry": shape.get("chemistry"),
                "advice": sorted(advice["keys"]),
                "featured_lines": featured_lines,
                "fallback_lines": bool(use_fallback),
                "score_diff": gs.get("score_diff", 0),
                "period": gs.get("period", 1)}
        return {"F": f_shares, "D": d_shares, "PP": pp_shares,
                "PK": pk_shares, "meta": meta}
    except Exception:
        return {"F": [0.25, 0.25, 0.25, 0.25],
                "D": [1 / 3.0, 1 / 3.0, 1 / 3.0],
                "PP": [0.5, 0.5], "PK": [0.5, 0.5],
                "meta": {"fallback": True, "error": True}}


def _power_shares(scores: List[float], exponent: float) -> List[float]:
    """Special-teams shares: score^exponent, normalized (sums to 1)."""
    n = len(scores)
    if n == 0:
        return []
    even = [1.0 / n] * n
    try:
        powered = [max(0.0, s) ** exponent for s in scores]
        total = sum(powered)
        if total <= 0:
            return even
        return [p / total for p in powered]
    except Exception:
        return even


def score_state_thresholds(game_state: Dict[str, Any],
                           concentration: float) -> Tuple[int, int]:
    """(chase_at, protect_at): goal-diff thresholds for bench-shortening.

    Defaults (-2, +2) preserve the historical behavior; an aggressive
    coach (high concentration) trailing late starts chasing at -1.
    """
    try:
        chase, protect = -2, 2
        late = (game_state.get("period", 1) == 3
                and game_state.get("clock", 1200) < 600)
        if (late and game_state.get("score_diff", 0) < 0
                and concentration >= 0.60):
            chase = -1
        return chase, protect
    except Exception:
        return -2, 2


# ---------------------------------------------------------------------------
# Cached per-game entry point (what the shift engine calls)
# ---------------------------------------------------------------------------

def deployment_weights_for_game(sim: Any, team: Any) -> Dict[str, Any]:
    """deployment_weights with coach style / tactics family / game state
    derived from the sim, cached per team per game-state bucket.

    The cache key is (period, clamped goal diff, late-game flag, dressed
    count): the policy recomputes only when the situation actually changes,
    not on every line change. The soft-cap governor is applied separately
    and stays live (see soft_cap_adjust_shares).
    """
    fallback = {"F": [0.25, 0.25, 0.25, 0.25],
                "D": [1 / 3.0, 1 / 3.0, 1 / 3.0],
                "PP": [0.5, 0.5], "PK": [0.5, 0.5],
                "meta": {"fallback": True}}
    try:
        cache = getattr(sim, "_deployment_cache", None)
        if cache is None:
            sim._deployment_cache = cache = {}
        tname = getattr(team, "team_name", None) or str(id(team))
        gs = _game_state_from_sim(sim, team)
        late = bool(gs["period"] == 3 and gs["clock"] < 600)
        key = (gs["period"], max(-3, min(3, gs["score_diff"])), late,
               _dressed_skater_count(gs.get("lineup") or {}))
        ent = cache.get(tname)
        if ent is not None and ent[0] == key:
            return ent[1]
        coach = _head_coach_for(team)
        style = _safe_coach_style(coach)
        family = _safe_team_family(team)
        weights = deployment_weights(team, style, family, gs)
        cache[tname] = (key, weights)
        return weights
    except Exception:
        return dict(fallback)


# ---------------------------------------------------------------------------
# Per-game TOI accounting (keyed by player id, stored on the game object)
# ---------------------------------------------------------------------------

def _toi_store(sim: Any) -> Dict[int, float]:
    d = getattr(sim, "_game_toi", None)
    if d is None:
        sim._game_toi = d = {}
    return d


def _raw_toi(sim: Any, pid: Any) -> float:
    """Player's TOI seconds so far this game.

    Prefers the per-tick ground-truth ledger (simulation._update_fatigue's
    player_toi_seconds): it credits actual on-ice skaters every tick, so it
    sees special-teams unit alternation, manpower transitions, and fill-in
    double-shifts that the per-change W2 ledger (credited by lineup slot
    at change time) systematically misses for PP/PK players. Falls back to
    W2's _game_toi when the tick ledger is unavailable. The soft-cap
    governor reads through here, so it binds on real ice time.
    """
    try:
        w3 = getattr(sim, "player_toi_seconds", None)
        if w3:
            v = w3.get(pid)
            if v is not None:
                return float(v)
    except Exception:
        pass
    try:
        return float((getattr(sim, "_game_toi", None) or {}).get(pid, 0.0))
    except Exception:
        return 0.0


def _credit_players(sim: Any, players: List[Any], seconds: float) -> None:
    if seconds <= 0 or not players:
        return
    try:
        store = _toi_store(sim)
        for p in players:
            pid = getattr(p, "id", None)
            if pid is None:
                continue
            store[pid] = store.get(pid, 0.0) + seconds
    except Exception:
        pass


def _special_teams_state(sim: Any, team: Any) -> Tuple[str, int]:
    """('PP'|'PK'|'EV', unit_idx): which unit is actually on the ice.

    Mirrors the manpower / special-unit decision in
    simulation.GameSim._get_on_ice (penalized-skater counts, PP1/PP2 clock
    alternation, no special teams in 3v3 OT) so TOI credits the unit the
    sim dressed -- never two copies of the decision, just a read of it.
    """
    try:
        if (getattr(sim, "period", 1) or 1) == 4:
            return ("EV", 0)  # 3v3 OT dresses from even-strength slots
        tname = getattr(team, "team_name", None)
        is_home = (getattr(getattr(sim, "home_team", None),
                           "team_name", None) == tname)
        from game_classes import PlayerPosition

        def _mp_skaters(penlist):
            out = []
            for pen in penlist or []:
                try:
                    if not pen.get("manpower_loss", True):
                        continue
                    pl = pen.get("player")
                    if (pl is not None
                            and getattr(pl, "primary_position", None)
                            != PlayerPosition.GOALIE):
                        out.append(pl)
                except Exception:
                    continue
            return out

        home_pen = getattr(sim, "home_penalties", None) or []
        away_pen = getattr(sim, "away_penalties", None) or []
        mine = _mp_skaters(home_pen if is_home else away_pen)
        theirs = _mp_skaters(away_pen if is_home else home_pen)
        try:
            clock = int(getattr(sim, "clock", 0) or 0)
        except Exception:
            clock = 0
        idx = (clock // 45) % 2 + 1  # same alternation the sim dresses
        if len(mine) < len(theirs):
            return ("PP", idx)
        if len(mine) > len(theirs):
            return ("PK", idx)
        return ("EV", 0)
    except Exception:
        return ("EV", 0)


def _starting_goalie(lineup: Dict[str, Any]) -> Any:
    try:
        g = (lineup or {}).get("G1")
        if g is not None:
            return g
        nested = (lineup or {}).get("Goalies") or []
        return nested[0] if nested else None
    except Exception:
        return None


def credit_forwards_elapsed(sim: Any, team: Any, st: Any,
                            clock: float) -> None:
    """Credit the outgoing forward unit's elapsed ice time.

    Manpower-aware: during a PP/PK the credit goes to the special-teams
    unit the sim actually dressed, not the even-strength line index.
    Called by the shift engine BEFORE the line index advances.
    """
    try:
        start = getattr(st, "f_shift_start", None)
        if start is None:
            return
        elapsed = float(start) - float(clock)
        if elapsed <= 0:
            return
        mode, unit_idx = _special_teams_state(sim, team)
        lineup = _game_lineup_for(sim, team)
        if mode == "PP":
            # Forwards hook credits the FORWARD slice of the unit only: the
            # defense hook (credit_defense_elapsed) credits the D slice of
            # the same unit for the same elapsed window. Crediting the whole
            # unit here double-counted every PP/PK defenseman's special-teams
            # TOI (found 2026-09-29: a PP1/PK1 D reading 65 min in a 60-min
            # game), which also fed the soft-cap governor phantom minutes.
            players = [p for p in _unit_players(lineup, "PP", unit_idx)
                       if not _is_defenseman(p)]
        elif mode == "PK":
            players = [p for p in _unit_players(lineup, "PK", unit_idx)
                       if not _is_defenseman(p)]
        else:
            players = _unit_players(lineup, "F", getattr(st, "f_line", 1))
        _credit_players(sim, players, elapsed)
    except Exception:
        pass


def credit_defense_elapsed(sim: Any, team: Any, st: Any,
                           clock: float) -> None:
    """Credit the outgoing D unit's elapsed ice time (manpower-aware)."""
    try:
        start = getattr(st, "d_shift_start", None)
        if start is None:
            return
        elapsed = float(start) - float(clock)
        if elapsed <= 0:
            return
        mode, unit_idx = _special_teams_state(sim, team)
        lineup = _game_lineup_for(sim, team)
        if mode == "PP":
            # Defense slice only (the forwards hook credits the F slice of
            # the same unit). No whole-unit fallback: on a 5-forward PP
            # there is simply no D TOI to credit, and falling back to the
            # whole unit would double-count the forwards (same 2026-09-29
            # fix as credit_forwards_elapsed).
            players = [p for p in _unit_players(lineup, "PP", unit_idx)
                       if _is_defenseman(p)]
        elif mode == "PK":
            players = [p for p in _unit_players(lineup, "PK", unit_idx)
                       if _is_defenseman(p)]
        else:
            players = _unit_players(lineup, "D", getattr(st, "d_pair", 1))
        _credit_players(sim, players, elapsed)
    except Exception:
        pass


def credit_goalie_elapsed(sim: Any, team: Any, st: Any,
                          clock: float) -> None:
    """Credit the starting goalie's elapsed time in net."""
    try:
        last = getattr(st, "_toi_flush_clock", None)
        if last is None:
            st._toi_flush_clock = float(clock)
            return
        elapsed = float(last) - float(clock)
        if elapsed <= 0:
            return
        goalie = _starting_goalie(_game_lineup_for(sim, team))
        if goalie is not None:
            _credit_players(sim, [goalie], elapsed)
        st._toi_flush_clock = float(clock)
    except Exception:
        pass


def flush_team_toi(sim: Any, team: Any) -> None:
    """Credit all pending shift time for a team (idempotent).

    Called at period boundaries, at game end, and by get_game_toi before
    reading -- so TOI is exact whenever observed. Safe to call repeatedly:
    crediting resets the shift clocks it reads.
    """
    try:
        states = getattr(sim, "_shift_states", None) or {}
        key = getattr(team, "team_name", id(team))
        st = states.get(key)
        if st is None:
            return
        clock = getattr(sim, "clock", 0)
        try:
            clock = float(clock)
        except Exception:
            clock = 0.0
        flush_team_toi_at_clock(sim, team, st, clock)
    except Exception:
        pass


def flush_team_toi_at_clock(sim: Any, team: Any, st: Any,
                            clock: float) -> None:
    """Credit a team's current units as of `clock`, then reset shift clocks.

    The shift-engine hook for period boundaries (clock = 0.0, the horn):
    the truncated shift is credited before the clocks reset. Idempotent.
    """
    try:
        credit_forwards_elapsed(sim, team, st, clock)
        credit_defense_elapsed(sim, team, st, clock)
        credit_goalie_elapsed(sim, team, st, clock)
        st.f_shift_start = clock
        st.d_shift_start = clock
    except Exception:
        pass


def get_game_toi(game: Any, player: Any) -> float:
    """Seconds of ice time credited to `player` in this game.

    Flushes both teams' pending shift time first, so the final shift --
    which no line change ever closes -- is included. Never raises.
    """
    try:
        for team in (getattr(game, "home_team", None),
                     getattr(game, "away_team", None)):
            if team is not None:
                flush_team_toi(game, team)
        return _raw_toi(game, getattr(player, "id", None))
    except Exception:
        return 0.0


def finalize_game_toi(game: Any) -> Dict[int, float]:
    """Flush all pending TOI and return the full {player_id: seconds} map."""
    try:
        for team in (getattr(game, "home_team", None),
                     getattr(game, "away_team", None)):
            if team is not None:
                flush_team_toi(game, team)
        return dict(getattr(game, "_game_toi", None) or {})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Soft-cap governor (~30 min for elite skaters)
# ---------------------------------------------------------------------------

def _log_deployment(sim: Any, team: Any, event: Dict[str, Any]) -> None:
    """Record a deployment decision on the game object (and the feed)."""
    try:
        log = getattr(sim, "_deployment_log", None)
        if log is None:
            sim._deployment_log = log = []
        entry = {"team": getattr(team, "team_name", "?"),
                 "period": getattr(sim, "period", 1)}
        try:
            entry["clock"] = round(float(getattr(sim, "clock", 0)), 1)
        except Exception:
            pass
        entry.update(event or {})
        log.append(entry)
    except Exception:
        pass
    try:
        text = event.get("text") if isinstance(event, dict) else None
        if text and hasattr(sim, "_log_event"):
            sim._log_event(str(text), "DEPLOYMENT")
    except Exception:
        pass


def soft_cap_exceptions(game_state: Dict[str, Any]) -> Dict[str, bool]:
    """Which soft-cap exceptions are active right now.

    Exceptions ONLY: must-win playoff games, an injury-depleted bench,
    OT marathons. Anything else -- the cap binds.
    """
    gs = game_state or {}
    return {"must_win_playoff": bool(gs.get("must_win")),
            "bench_depleted": bool(gs.get("bench_short")),
            "ot_marathon": bool(gs.get("ot_marathon"))}


def soft_cap_adjust_shares(sim: Any, team: Any, side: str,
                           shares: List[float]) -> List[float]:
    """Apply the ~30-min soft cap to one group's shares.

    For each line/pair, the binding skater is the one with the most TOI so
    far; when his TOTAL (ES + special teams) hits the cap (and no exception
    applies) his ES line is excluded from the rotation and its ice
    redistributes to the next lines -- the coach's decision, logged once
    per line per game. Exclusion (not a relative downweight): if every
    line bound at once, a multiplier would renormalize back to the original
    ratios and nobody would ever sit. If all lines are capped, the least-
    capped line stays available so deployment never stalls. Never raises;
    returns the input shares unchanged on any failure.

    Short-bench games (bench_depleted) bind at 35:00 rather than standing
    down entirely; must-win playoff games and OT marathons still ride.
    """
    try:
        shares = list(shares)
        n = len(shares)
        if n == 0:
            return shares
        gs = _game_state_from_sim(sim, team)
        exc = soft_cap_exceptions(gs)
        if exc.get("must_win_playoff") or exc.get("ot_marathon"):
            return shares  # exceptions: ride the horses
        cap_s = SOFT_CAP_SHORT_S if exc.get("bench_depleted") else SOFT_CAP_S
        short_bench = cap_s > SOFT_CAP_S
        lineup = _game_lineup_for(sim, team)
        kind = "F" if side == "F" else "D"
        bound = []
        for i in range(n):
            players = [p for p in _unit_players(lineup, kind, i + 1)
                       if not _is_goalie(p)]
            if not players:
                continue
            tois = [(_raw_toi(sim, getattr(p, "id", None)), p)
                    for p in players]
            worst_s, star = max(tois, key=lambda t: t[0])
            if worst_s >= cap_s:
                bound.append((i + 1, worst_s, star))
        if not bound:
            return shares
        bound_lines = {line_no for line_no, _, _ in bound}
        if len(bound_lines) >= n:
            # Everyone is capped: keep the least-capped line skating so
            # deployment never stalls; the soft cap has done all it can.
            least = min(bound, key=lambda b: b[1])[0]
            bound_lines.discard(least)
        for line_no in bound_lines:
            shares[line_no - 1] = 0.0
        total = sum(shares)
        if total > 0:
            shares = [s / total for s in shares]
        else:
            # Safety net (should be unreachable: all-capped keeps one
            # line): fall back to even shares rather than stalling.
            shares = [1.0 / n] * n
        # Log once per line per game (no feed spam across 60 minutes).
        logged = getattr(sim, "_soft_cap_logged", None)
        if logged is None:
            sim._soft_cap_logged = logged = set()
        tname = getattr(team, "team_name", "?")
        for line_no, worst_s, star in bound:
            key = (tname, side, line_no)
            if key in logged:
                continue
            logged.add(key)
            pname = getattr(star, "full_name", "a skater")
            unit = "line" if side == "F" else "pair"
            cap_label = "35 (short bench)" if short_bench else "30"
            cap_trigger = "35:00" if short_bench else "30:00"
            _log_deployment(sim, team, {
                "event": "soft_cap_bind",
                "line": line_no, "side": side,
                "player": pname,
                "toi_min": round(worst_s / 60.0, 1),
                "action": (f"{pname} at {worst_s / 60.0:.1f} min "
                           f"(soft-cap trigger {cap_trigger}, cap ~{cap_label}) -- deployment "
                           f"shifts to next "
                           f"{'lines' if side == 'F' else 'pairs'}"),
                "text": (f"{tname}: {pname} hits the "
                         f"{'35-min short-bench' if short_bench else '~30-min'} "
                         f"soft cap; "
                         f"the {line_no}{_ordinal(line_no)} {unit} sits "
                         f"while the next units take the ice."),
            })
        return shares
    except Exception:
        return list(shares)


def _ordinal(n: int) -> str:
    return {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")


def deployment_log(game: Any) -> List[Dict[str, Any]]:
    """The game's deployment decisions (soft-cap binds etc.)."""
    try:
        return list(getattr(game, "_deployment_log", None) or [])
    except Exception:
        return []


def pick_weighted_line(shares: List[float], n: int,
                       exclude: Optional[int] = None) -> int:
    """1-based weighted pick from shares; `exclude` is a 1-based line that
    may not be picked (a change means a change). Falls back to uniform."""
    try:
        if len(shares) != n:
            shares = [1.0 / n] * n
        w = [s if (i + 1) != exclude else 0.0 for i, s in enumerate(shares)]
        if sum(w) <= 0:
            w = list(shares)
        if sum(w) <= 0:
            w = [1.0 / n] * n
        return random.choices(range(1, n + 1), weights=w, k=1)[0]
    except Exception:
        return random.randint(1, n)


# ---------------------------------------------------------------------------
# WITHIN-LINE DIFFERENTIATION ("leverage score") -- 2026-09-29
#
# Ice time is two separate quantities:
#   * QUANTITY -- how many minutes a player skates. Governed by
#     _player_deployment_score() + deployment_weights(), hard-clamped to
#     [0.95, 1.05] of the raw table weight. Talent hierarchy intact.
#   * QUALITY -- how PREMIUM those minutes are: offensive-zone starts,
#     soft matchups, clutch shifts, the best power-play seconds.
#
# leverage_score() answers the quality question. A heater does not get MORE
# ice -- he gets BETTER ice: more OZ draws, the mismatch against the other
# team's 4th line, the 6-on-5 shift with the goalie pulled. League scoring
# totals never move: this is pure redistribution of premium minutes WITHIN
# a team's minutes.
#
# Because leverage never changes WHO plays, it may swing harder than the
# quantity clamp: [0.80, 1.30]. A max heater gets +30% premium-shift weight;
# an ice-cold slumper gets -20% (sheltered from premium minutes).
# ---------------------------------------------------------------------------

#: Master kill-switch for within-line differentiation. The shift-engine hooks
#: all consult this: with it off, every hook falls back to the pre-leverage
#: behavior (plain deployment-share weighting). Old saves are unaffected
#: either way -- leverage only reads per-game state.
LEVERAGE_ENABLED = True

#: Hard bounds on the leverage multiplier.
_LEVERAGE_LO = 0.80
_LEVERAGE_HI = 1.30

#: Style amplitude on the leverage DEVIATION from 1.0. A players' coach rides
#: the hot hand hard; a drill sergeant barely differentiates -- same player,
#: same streak, different coach, different leverage. Mirrors the philosophy
#: of _STYLE_FACTOR_W (style modulates how strongly each factor bites).
_LEVERAGE_AMPLITUDE = {
    "drill_sergeant": 0.5,
    "tactician": 0.8,
    "developer": 1.0,
    "balanced": 1.0,
    "motivator": 1.2,
    "players_coach": 1.3,
}

#: Narrative throttle: one feed line per (team, key, line) per game.
def log_leverage(sim: Any, team: Any, key: str, text: str) -> None:
    """Log a leverage decision to the deployment log + broadcast feed.

    Throttled to one line per (team, key) per game so the feed reads like a
    broadcast ("riding the hot hand") rather than a telemetry dump.
    """
    try:
        if not LEVERAGE_ENABLED:
            return
        logged = getattr(sim, "_leverage_logged", None)
        if logged is None:
            sim._leverage_logged = logged = set()
        k = (getattr(team, "team_name", "?"), key)
        if k in logged:
            return
        logged.add(k)
        _log_deployment(sim, team, {"event": "leverage", "key": key,
                                   "text": text})
    except Exception:
        pass


def leverage_score(player: Any, coach: Any = None,
                   style_key: Optional[str] = None,
                   team: Any = None) -> float:
    """How PREMIUM should this player's shifts be? (within-line differentiation)

    Same input family as _player_deployment_score() -- heater/streak form
    (mesh_form), morale, coach trust/relationships, coach philosophy -- but a
    SEPARATE decision: this never touches quantity (minutes), only quality
    (which minutes).

    Returns a multiplier centered on 1.0, clamped to [0.80, 1.30]:

    * heater (form01 > 0.5): up to +30%, scaled by coach adaptability
      (the hot hand rides; stubborn coaches resist it).
    * slump (form01 < -0.5): down to -20% (cold players get sheltered).
    * morale: 0.90 + 0.20 * morale01 -- confident players get the big draws.
    * relationships (coach fit + coach_bonds): trusted players get leverage.
    * style: every component deviation is scaled through _STYLE_FACTOR_W
      (recency / relationships / morale factors), then the total deviation
      from 1.0 is scaled by _LEVERAGE_AMPLITUDE for the coach's philosophy.

    Never raises: returns 1.0 (neutral) on any failure.
    """
    try:
        skey = style_key or _safe_coach_style(coach).get("key") or "balanced"
        recency_w = _adapt_recency_mult(coach)
        form01 = _norm_form01(player)
        comps: List[tuple] = []

        # Heater: genuine hot streaks earn premium shifts. The adaptability
        # scale keeps stubborn coaches from chasing noise.
        heat01 = max(0.0, min(1.0, (form01 - 0.5) / 0.5))
        if heat01 > 0.0:
            comps.append(("recency", 1.0 + 0.30 * heat01 * recency_w))
        # Slump: ice-cold players get sheltered from premium minutes.
        cold01 = max(0.0, min(1.0, (-form01 - 0.5) / 0.5))
        if cold01 > 0.0:
            comps.append(("recency", 1.0 - 0.20 * cold01 * recency_w))
        # Morale: confidence gets the big draws.
        morale01 = max(0.0, min(1.0, _attr100(player, "morale", 70) / 100.0))
        comps.append(("morale", 0.90 + 0.20 * morale01))

        if coach is not None:
            # Relationships under the morale blanket: trusted players get
            # the premium minutes. Coach bonds (the personal click) add on.
            fit = _safe_coach_fit(coach, player)
            fit_m = 1.0 + (0.10 if fit >= 0.0 else 0.15) * fit
            comps.append(("relationships", fit_m))
            bonds = getattr(player, "coach_bonds", None) or {}
            try:
                has_bond = getattr(coach, "id", None) in bonds
            except Exception:
                has_bond = False
            if has_bond:
                comps.append(("relationships", 1.10))

        lev = 1.0
        for factor, m in comps:
            lev *= _style_factor_mult(m, skey, factor)
        amp = _LEVERAGE_AMPLITUDE.get(skey, 1.0)
        lev = 1.0 + (lev - 1.0) * amp
        return max(_LEVERAGE_LO, min(_LEVERAGE_HI, lev))
    except Exception:
        return 1.0


def line_leverage(sim: Any, team: Any, kind: str, idx: int) -> float:
    """Mean leverage multiplier of a unit's skaters (1.0 = neutral).

    kind in {"F", "D"}; idx is 1-based. Used by the shift engine to weight
    OZ-start allocation, mismatch exploitation, and clutch-shift picks.
    """
    try:
        lineup = _game_lineup_for(sim, team)
        players = [p for p in _unit_players(lineup, kind, idx)
                   if not _is_goalie(p)]
        if not players:
            return 1.0
        coach = _head_coach_for(team)
        vals = [leverage_score(p, coach, team=team) for p in players]
        return sum(vals) / max(1, len(vals))
    except Exception:
        return 1.0


def line_leverage_leader(sim: Any, team: Any, kind: str,
                         idx: int) -> Optional[Any]:
    """Highest-leverage skater on a unit (for narrative lines); None if none."""
    try:
        lineup = _game_lineup_for(sim, team)
        players = [p for p in _unit_players(lineup, kind, idx)
                   if not _is_goalie(p)]
        if not players:
            return None
        coach = _head_coach_for(team)
        return max(players, key=lambda p: leverage_score(p, coach, team=team))
    except Exception:
        return None


def line_trust(sim: Any, team: Any, kind: str, idx: int) -> float:
    """Mean DEFENSIVE trust of a unit's skaters: 0.80..1.20.

    Defensive awareness + discipline: trusted defensive types soak D-zone
    draws and protect-lead shifts. The defensive counterpart to line_leverage
    (leverage is about offensive premium minutes; trust is about defensive
    responsibility).
    """
    try:
        lineup = _game_lineup_for(sim, team)
        players = [p for p in _unit_players(lineup, kind, idx)
                   if not _is_goalie(p)]
        if not players:
            return 1.0
        vals = []
        for p in players:
            da = _attr100(p, "defensive_awareness", 50)
            di = _attr100(p, "discipline", 50)
            vals.append(0.80 + 0.40 * ((da + di) / 200.0))
        return sum(vals) / max(1, len(vals))
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# PP micro-rotation -- OPEN ITEM (2026-09-29)
#
# Within PP1/PP2, leverage SHOULD decide who stays the full 2 minutes vs who
# rotates early (the hot unit overlaps). There is deliberately NO hook here
# yet: PP units are dressed by the clock alternation PP{(clock//45)%2+1} in
# simulation._get_on_ice (the sim/lineup region), and the TOI-credit functions
# above mirror that alternation exactly (the 2026-09-29 ee16b37 lesson: the
# dressing source of truth and the credit source of truth must move together).
#
# The safe design when the sim owner takes this on: a shared helper here,
# e.g. pp_overlap_skater(sim, team) -> Optional[player], consulted by BOTH
# the _get_on_ice dressing filter (keep the outgoing unit's highest-leverage
# skater dressed for the first 45s of the incoming unit's window) AND the
# _special_teams_state-based credit functions above (credit him to the unit
# he is actually skating with). One decision, two consumers -- never a
# dressing change without the matching credit change.
# ---------------------------------------------------------------------------
