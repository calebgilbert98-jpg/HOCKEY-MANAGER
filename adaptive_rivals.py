# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Adaptive Rivals: AI teams scout the user and make a hockey answer.

Each AI team plays its own philosophical identity (zone modules installed
via tactics.py). Before a game vs the user's team, the AI checks its
tactical intel — how the user's *specific systems* have performed against
it in recent meetings — and installs the hockey answer for the most
damaging one, using the TACTICAL_COUNTERS table:

- Your umbrella PP is at 32% vs them -> they sit in a passive box tonight
- Your 2-1-2 swarm is eating their breakouts -> short controlled exits
- Your 1-3-1 trap strangles them -> chip-and-chase, never carry it in

Answers are philosophy-gated: a Chaos & Pressure room answers with
pressure, a Stranglehold room with structure. Cross-family answers only
happen when the coach is highly adaptable or the room is getting shelled.
One-game game-plan tweak, not a system overhaul: small familiarity dip,
reverted after the game.

Without intel yet (early season), falls back to the blunt read: you score
a lot -> they get more defensive; you defend well -> they open up.

Engine boundary: reads tactics, never changes sim math. Purely additive.
"""

from typing import Any, Dict, List, Optional, Tuple

import tactics as _tx


# Fallback nudge scales (structure -> pressure) per category, for the
# no-intel early-season read. Philosophy still gates: a structure team
# nudges toward structure, a pressure team toward pressure.
_FALLBACK_SCALES = {
    "dzone": ["dz_box", "dz_hybrid", "dz_slide_match"],
    "forecheck": ["forecheck_122", "forecheck_212_swarm"],
    "neutral_zone": ["nz_trap_131", "nz_regroup", "nz_counterpress"],
    "ozone": ["oz_cycle", "oz_flow", "oz_micro", "oz_rush"],
    "breakout": ["bo_controlled", "bo_direct", "bo_stretch"],
}

# plan entry: (category, old_key, new_key, reason)
Plan = List[Tuple[str, str, str, str]]


def _coach_adaptability(team: Any) -> float:
    try:
        coach = _tx._coach_for(team)
        return float(getattr(coach, "adaptability", 60) or 60)
    except Exception:
        return 60.0


def _module_label(category: str, key: str) -> str:
    try:
        return _tx.CATALOGS.get(category, {}).get(key, {}).get("name", key)
    except Exception:
        return key


def plan_adaptation(ai_team: Any, user_team: Any,
                    game_results: List[Any]) -> Plan:
    """Pure planning: what would this AI team change for tonight's game?

    Returns [(category, old_key, new_key, reason)]. Empty = no answer
    (nothing's hurting them, or nothing fits their philosophy).
    """
    plan: Plan = []
    try:
        _tx.ensure_team_tactics(ai_team)
        _tx.ensure_team_tactics(user_team)
        mine = _tx.team_tactics(ai_team)
        fam = _tx.team_family(ai_team)
        adapt = _coach_adaptability(ai_team)

        # 1) Intel-driven: answer the specific system that's beating them.
        damaging = _tx.damaging_user_systems(ai_team, user_team)
        for _cat_u, sys_key, heat in damaging:
            counter = _tx.TACTICAL_COUNTERS.get(sys_key)
            if not counter:
                continue
            cat, answer, why = counter
            if mine.get(cat) == answer:
                continue  # already playing the answer
            dire = heat >= 1.8
            if (not _tx.families_compatible(fam, answer)
                    and adapt < 75 and not dire):
                continue  # won't betray the philosophy for this
            old = mine.get(cat, "")
            plan.append((cat, old, answer,
                         f"your { _module_label(_cat_u, sys_key) } is at "
                         f"{heat:.1f}x the answer threshold vs them — "
                         f"{why}"))
            break  # one answer per game: coaches fix the biggest leak

        if plan:
            return plan

        # 2) Fallback: blunt GF/GA read (no intel yet).
        tendencies = scout_user_tendencies(user_team, game_results)
        gf = tendencies["goals_for_per_game"]
        ga = tendencies["goals_against_per_game"]
        if gf > 3.5:
            # Getting shelled: nudge the D-zone a step toward structure.
            plan.extend(_nudge(mine, fam, "dzone", toward="structure",
                               reason="you're scoring in bunches — "
                                      "they're collapsing to protect the house"))
        elif ga < 2.5:
            # Can't buy a goal vs you: nudge the attack toward pressure.
            plan.extend(_nudge(mine, fam, "ozone", toward="pressure",
                               reason="they can't solve your defense — "
                                      "they're opening the attack up"))
    except Exception:
        pass
    return plan


def _nudge(mine: Dict[str, str], fam: str, category: str,
           toward: str, reason: str) -> Plan:
    """Move one module one step along its fallback scale, philosophy-gated."""
    try:
        scale = _FALLBACK_SCALES.get(category, [])
        cur = mine.get(category)
        if cur not in scale:
            return []
        idx = scale.index(cur)
        step = -1 if toward == "structure" else 1
        nxt = scale[max(0, min(len(scale) - 1, idx + step))]
        if nxt == cur:
            return []
        if not _tx.families_compatible(fam, nxt):
            return []
        return [(category, cur, nxt, reason)]
    except Exception:
        return []


def apply_adaptation(ai_team: Any, plan: Plan) -> None:
    """Install a planned adaptation for tonight's game.

    A game-plan tweak, not a system overhaul: small familiarity dip (-5),
    because new reads are messy even for one night. The plan carries the
    originals so revert is exact.
    """
    try:
        _tx.ensure_team_tactics(ai_team)
        for cat, _old, new, _reason in plan:
            if ai_team.tactics.get(cat) != new:
                ai_team.tactics[cat] = new
        fam = _tx._get(ai_team, "tactics_familiarity", 85)
        ai_team.tactics_familiarity = max(40.0, fam - 5)
        _tx._bust_tactics_cache(ai_team)
    except Exception:
        pass


def revert_adaptation(ai_team: Any, plan: Plan) -> None:
    """Restore pre-game systems after the final horn."""
    try:
        for cat, old, _new, _reason in plan:
            if old:
                ai_team.tactics[cat] = old
        _tx._bust_tactics_cache(ai_team)
    except Exception:
        pass


def adapt_for_opponent(ai_team: Any, user_team: Any,
                       game_results: List[Any]) -> Plan:
    """Plan + apply. Returns the plan (for reporting / revert)."""
    plan = plan_adaptation(ai_team, user_team, game_results)
    if plan:
        apply_adaptation(ai_team, plan)
    return plan


def revert_to_base(ai_team: Any, plan: Optional[Plan] = None) -> None:
    """Backward-compatible revert. Prefers the plan; falls back to the
    legacy base_tactics stamp if some old caller has no plan."""
    try:
        if plan:
            revert_adaptation(ai_team, plan)
            return
        base = getattr(ai_team, "base_tactics", None)
        if base:
            for k, v in base.items():
                setattr(ai_team, k, v)
    except Exception:
        pass


def adaptation_report_lines(ai_team: Any, user_team: Any,
                            game_results: List[Any]) -> List[str]:
    """Human-readable lines for the pre-game scout report. Empty = the
    opponent is playing their own game tonight."""
    lines = []
    try:
        for cat, _old, new, reason in plan_adaptation(ai_team, user_team,
                                                      game_results):
            label = _module_label(cat, new)
            lines.append(f"They've made a hockey answer: {label} — {reason}.")
    except Exception:
        pass
    return lines


def assign_base_identity(team: Any) -> Dict[str, str]:
    """Legacy entry point: ensure the team has seeded zone modules.
    (The old flat-slider identity is superseded by ensure_team_tactics.)"""
    try:
        return dict(_tx.ensure_team_tactics(team))
    except Exception:
        return {}


def scout_user_tendencies(user_team: Any, game_results: List[Any],
                          last_n: int = 10) -> Dict[str, float]:
    """Analyze user's last N games for blunt tendencies (fallback read)."""
    tendencies = {
        "goals_for_per_game": 3.0,
        "goals_against_per_game": 3.0,
        "penalties_drawn_per_game": 3.0,
        "power_play_pct": 0.20,
    }
    try:
        user_name = user_team.team_name
        recent = []
        for gr in reversed(game_results):
            home = getattr(gr, 'home_team', None)
            away = getattr(gr, 'away_team', None)
            if home is None:
                if isinstance(gr, dict):
                    home = gr.get('home_team') or gr.get('home')
                    away = gr.get('away_team') or gr.get('away')
                else:
                    continue
            home_name = home.team_name if hasattr(home, 'team_name') else str(home)
            away_name = away.team_name if hasattr(away, 'team_name') else str(away)
            if user_name not in (home_name, away_name):
                continue
            recent.append(gr)
            if len(recent) >= last_n:
                break

        if not recent:
            return tendencies

        gf_total, ga_total = 0, 0
        for gr in recent:
            try:
                if isinstance(gr, dict):
                    hs = gr.get('home_score', 0)
                    aws = gr.get('away_score', 0)
                    hn = gr.get('home_team') or gr.get('home')
                    hn = hn.team_name if hasattr(hn, 'team_name') else str(hn)
                else:
                    hs = getattr(gr, 'home_score', 0)
                    aws = getattr(gr, 'away_score', 0)
                    hn = getattr(gr.home_team, 'team_name', '')
                if hn == user_name:
                    gf_total += hs
                    ga_total += aws
                else:
                    gf_total += aws
                    ga_total += hs
            except Exception:
                continue

        n = len(recent)
        tendencies["goals_for_per_game"] = gf_total / n if n else 3.0
        tendencies["goals_against_per_game"] = ga_total / n if n else 3.0
    except Exception:
        pass
    return tendencies
