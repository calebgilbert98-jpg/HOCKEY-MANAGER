"""Linemate chemistry + line efficiency (2026-09-30, Muck).

One shared module, both engines (one decision, two fidelities). Scores how
well a line / special-teams unit *fits together* and turns that fit into a
bounded efficiency multiplier applied to grade-A chance creation — never to
finishing, never to grade ceilings.

What goes in (the brief):
  * Archetype fit (complementarity): two snipers are redundant, a playmaker
    without a finisher is wasted. Uses player_archetypes.complementarity.
  * Attribute/composite complementarity (pipeline purity: composites are
    read through attribute_composites.raw_composite ONLY, never raw
    attributes). Overlapping strengths diminish (the best sets the ceiling,
    the rest are marginal); complementary composites multiply (one man's
    chance_creation x another's finishing).
  * Talent + performance is the highest-weighted foundation. Chemistry
    modulates; it never overrides.
  * Morale / relationships: unit morale, pairwise affinity (bonds), and the
    coach-player fit under the morale blanket.
  * Situation branches (Muck 2026-09-30): PP dynamics are NOT EV dynamics.
    EV   = line balance (forecheck/cycle/rush roles, internal complementarity).
    PP   = formation completeness (point QB, net-front, one-timer, bumper /
           half-wall playmaker; two point QBs and no net-front = malformed).
    PK   = scheme coverage (shot-blockers, faceoff men, clearers, sticks;
           pressure vs passive box from coach philosophy).
  * Role-aware lines: slots carry INTENDED ROLES from coach philosophy
    (defensive coach's L3 = shutdown; offensive coach's L3 = sheltered
    scoring; L4 = energy / development; D pairs shutdown/puck-moving/
    sheltered). fit(line, intended_role, personnel).
  * Vision-vs-personnel gap: experimentation ledger (combos tried in
    low-leverage spots, outcomes tracked = chemistry discovery), graceful
    vision adaptation to what the roster can staff, stubborn coaches force
    the ideal and pay (adaptability-modulated).
  * Schemed-against relief flows THROUGH chemistry: chemistry_relief_share
    apportions the zero-sum relief budget by archetype fit with the star.
    (scenario_composites imports this; the budget stays zero-sum/bounded.)
  * PP micro-rotation: heaters get better looks WITHIN the unit — bounded
    share redistribution, never changes who dresses.
  * Special-teams personnel ranking: how the coach picks PP/PK units
    (deployment weighting directive extended: talent+performance highest,
    team direction, recency, relationships/morale, philosophy modulates;
    plus handedness for the one-timer side, faceoff ability, PK specialists).
  * Storytelling is first-class: every score carries story hooks
    (electric / gelling / disjointed / split-up) and detail=True explains
    WHY a line clicks in hockey language. Same stories, both engines.

Calibration philosophy (Muck 2026-09-30): NO league-mean pin. Chemistry is
truthful and bounded per-line; good-fit lines convert better, bad-fit
lines worse; the league total lands where honest hockey puts it. The
efficiency is anchored so an AVERAGE-talent, AVERAGE-fit line is ~1.0 —
drift is measured, never corrected.

Real-NHL special-teams bands (verified 2026-09-30, 2024-25 season):
  PP%  league ~21.5, spread ~13 (bottom) .. ~30 (top)
  PK%  league ~78.5, spread ~68 (bottom) .. ~88 (top)
  PP opportunities ~2.7/team/game (2024-25, 20-yr low; normal ~3.0-3.6)
  PP goals ~20% of all goals (reg season; ~27% playoffs)
  SH goals rare (~2.5-3% of goals)
The bands EMERGE from unit fit; nothing is pasted on.

Additive only. No finishing constants, no grade ceilings, no protected
levers touched. Everything defensive: any failure returns neutral (1.0).
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Defensive imports — the module must never crash a sim.
# ---------------------------------------------------------------------------

try:
    from attribute_composites import raw_composite as _raw_composite
except Exception:  # pragma: no cover
    _raw_composite = None

try:
    from player_archetypes import complementarity as _complementarity
except Exception:  # pragma: no cover
    _complementarity = None

try:
    from dressing_room import affinity as _affinity
except Exception:  # pragma: no cover
    _affinity = None

try:
    from deployment_policy import leverage_score as _leverage_score
except Exception:  # pragma: no cover
    _leverage_score = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EV, PP, PK = "ev", "pp", "pk"

# Efficiency rails: truthful, bounded per-line. Product rail [0.86, 1.14].
_EFF_MIN, _EFF_MAX = 0.86, 1.14
_TALENT_MIN, _TALENT_MAX = 0.93, 1.07   # talent+performance: highest-weighted
_FIT_MIN, _FIT_MAX = 0.90, 1.10        # chemistry modulates, never overrides

# PK denial: a great PK unit shaves the chance; a bad one doesn't. Small by
# design — the man advantage itself already lives in chance volume.
_DENY_MIN, _DENY_MAX = 0.94, 1.00

# PP micro-rotation look shares: bounded, mean-preserving.
_LOOK_MIN, _LOOK_MAX = 0.90, 1.15

# Composite keys (attribute_composites.py).
_C_CHANCE = "chance_creation"
_C_FINISH = "finishing"
_C_DEF = "defensive_play"
_C_FACE = "faceoff"
_C_PHYS = "physicality"
_C_SKATE = "skating"
_C_RETR = "puck_retrieval"
_C_DISC = "discipline"


# ---------------------------------------------------------------------------
# Small safe accessors
# ---------------------------------------------------------------------------

def _pid(p: Any) -> Any:
    try:
        return getattr(p, "id", None)
    except Exception:
        return None


def _role_name(p: Any) -> str:
    try:
        r = p.get_role()
        return getattr(r, "value", "") or str(r)
    except Exception:
        return ""


def _comp(p: Any, key: str) -> float:
    """Composite 0-100 via the shared pipeline. Never raw attributes."""
    try:
        if _raw_composite is not None:
            return max(0.0, min(100.0, float(_raw_composite(p, key))))
    except Exception:
        pass
    # Fallback: overall as a flat proxy (keeps the module total even if the
    # composites module is unavailable).
    try:
        return max(0.0, min(100.0, float(p.overall_rating())))
    except Exception:
        return 70.0


def _overall(p: Any) -> float:
    try:
        return max(1.0, min(99.0, float(p.overall_rating())))
    except Exception:
        return 75.0


def _morale01(p: Any) -> float:
    try:
        return max(0.0, min(1.0, float(getattr(p, "morale", 70) or 70) / 100.0))
    except Exception:
        return 0.70


def _form01(p: Any) -> float:
    """Recent performance, -1..1. mesh_form when available, else neutral.

    Mirrors deployment_policy._norm_form01: mesh_form is -1..1, but a
    0-100 scale is tolerated (divided by 100). This is the canonical
    recent-performance read — form is a FIRST-CLASS factor: heaters lift
    their line, cold players drag it.
    """
    try:
        f = float(getattr(p, "mesh_form", 0) or 0)
    except Exception:
        return 0.0
    if abs(f) > 1.0:
        f = f / 100.0
    return max(-1.0, min(1.0, f))


def _streak(p: Any) -> int:
    try:
        return int(getattr(p, "mesh_streak", 0) or 0)
    except Exception:
        return 0


def _pname(p: Any) -> str:
    for attr in ("full_name", "name"):
        try:
            v = getattr(p, attr, "")
            if v:
                return str(v)
        except Exception:
            pass
    return "He"


def _age(p: Any) -> Optional[float]:
    try:
        a = getattr(p, "age", None)
        return float(a) if a is not None else None
    except Exception:
        return None


def _hand(p: Any) -> str:
    try:
        return str(getattr(p, "handedness", "") or "").strip().lower()
    except Exception:
        return ""


def _is_dman(p: Any) -> bool:
    r = _role_name(p).lower()
    return "defenseman" in r or "defenceman" in r


def _pair_complementarity(r1: str, r2: str) -> float:
    try:
        if _complementarity is not None:
            return float(_complementarity(r1, r2))
    except Exception:
        pass
    return 0.0


def _pair_affinity(a: Any, b: Any) -> float:
    try:
        if _affinity is not None:
            return max(0.0, min(100.0, float(_affinity(a, b))))
    except Exception:
        pass
    return 50.0


def _coach_style_key(coach: Any) -> str:
    try:
        from reputation_system import coach_style as _cs
        s = _cs(coach)
        if isinstance(s, dict) and s.get("key"):
            return str(s["key"])
    except Exception:
        pass
    return "balanced"


def _coach_adaptability(coach: Any) -> float:
    """0..1. Stubborn coaches force their vision; adaptable ones adjust."""
    try:
        return max(0.0, min(1.0, (float(getattr(coach, "adaptability", 65)
                                       or 65) - 1.0) / 99.0))
    except Exception:
        return 0.65


def _resolve_coach(team: Any, sim: Any = None) -> Any:
    """Find the coach object for a team (object or name), defensively."""
    try:
        tobj = team
        tname = getattr(team, "team_name", team)
        if sim is not None and not hasattr(team, "team_name"):
            for cand in (getattr(sim, "home_team", None),
                         getattr(sim, "away_team", None)):
                if cand is not None and getattr(cand, "team_name", None) == tname:
                    tobj = cand
                    break
        for attr in ("head_coach", "coach"):
            c = getattr(tobj, attr, None)
            if c is not None:
                return c
    except Exception:
        pass
    return None


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# ---------------------------------------------------------------------------
# Situation detection — one shared helper so both engines agree.
# ---------------------------------------------------------------------------

def detect_situation(sim: Any = None, team: Any = None) -> str:
    """'pp' / 'pk' / 'ev' for the attacking team. Never raises.

    Handles quick_sim (sim.pp_team / sim.pk_team hold team NAMES) and
    GameSim (self._is_team_on_power_play(team) with team objects).
    """
    try:
        tname = getattr(team, "team_name", team)
        if sim is not None:
            pp_team = getattr(sim, "pp_team", None)
            pk_team = getattr(sim, "pk_team", None)
            if pp_team is not None or pk_team is not None:
                pp_name = getattr(pp_team, "team_name", pp_team)
                pk_name = getattr(pk_team, "team_name", pk_team)
                if tname is not None and tname == pp_name:
                    return PP
                if tname is not None and tname == pk_name:
                    return PK
                return EV
            # GameSim path: team objects + situation methods.
            if team is not None and hasattr(team, "team_name"):
                try:
                    if sim._is_team_on_power_play(team):
                        return PP
                except Exception:
                    pass
                try:
                    if sim._is_team_on_penalty_kill(team):
                        return PK
                except Exception:
                    pass
                return EV
            # No team given (GameSim shooter-weight path): read the global
            # situation enum. POWER_PLAY is stored from the home team's
            # perspective (see _is_team_on_power_play).
            try:
                sit = sim._get_current_situation()
                sname = getattr(sit, "name", str(sit)).upper()
                if "POWER_PLAY" in sname:
                    return PP
                if "PENALTY_KILL" in sname:
                    return PK
            except Exception:
                pass
    except Exception:
        pass
    return EV


# ---------------------------------------------------------------------------
# Role-aware lines: intended roles per slot, from coach philosophy.
# ---------------------------------------------------------------------------

# Philosophy axis derived from coach style.
_STYLE_PHILOSOPHY = {
    "drill_sergeant": "defensive",
    "tactician": "defensive",
    "motivator": "offensive",
    "players_coach": "balanced",
    "developer": "development",
    "balanced": "balanced",
}

# slot -> philosophy -> intended role
_SLOT_ROLE_MAP = {
    "F1": {"defensive": "scoring", "offensive": "scoring",
           "balanced": "scoring", "development": "scoring"},
    "F2": {"defensive": "two_way", "offensive": "scoring",
           "balanced": "two_way", "development": "two_way"},
    "F3": {"defensive": "shutdown", "offensive": "sheltered_scoring",
           "balanced": "two_way", "development": "development"},
    "F4": {"defensive": "energy", "offensive": "energy",
           "balanced": "energy", "development": "development"},
    "D1": {"defensive": "shutdown", "offensive": "two_way",
           "balanced": "shutdown", "development": "shutdown"},
    "D2": {"defensive": "two_way", "offensive": "puck_moving",
           "balanced": "two_way", "development": "two_way"},
    "D3": {"defensive": "sheltered", "offensive": "sheltered",
           "balanced": "sheltered", "development": "development"},
    "PP1": {"defensive": "pp_elite", "offensive": "pp_elite",
            "balanced": "pp_elite", "development": "pp_elite"},
    "PP2": {"defensive": "pp_secondary", "offensive": "pp_secondary",
            "balanced": "pp_secondary", "development": "pp_secondary"},
    "PK1": {"defensive": "pk_primary", "offensive": "pk_primary",
            "balanced": "pk_primary", "development": "pk_primary"},
    "PK2": {"defensive": "pk_secondary", "offensive": "pk_secondary",
            "balanced": "pk_secondary", "development": "pk_secondary"},
}

# Intended-role templates: desired archetype coverage + composite profile.
# A perfect shutdown line and a perfect scoring line are different
# perfections — each role is scored against its own ideal.
_ROLE_TEMPLATES = {
    "scoring": {
        "archetypes": {"Sniper", "Playmaker", "Power Forward",
                       "Offensive Defenseman", "Puck-Moving Defenseman"},
        "composites": {_C_FINISH: 1.0, _C_CHANCE: 0.9, _C_SKATE: 0.6,
                       _C_DEF: 0.25, _C_PHYS: 0.35},
    },
    "sheltered_scoring": {
        "archetypes": {"Sniper", "Playmaker", "Power Forward",
                       "Two-Way Forward"},
        "composites": {_C_FINISH: 0.9, _C_CHANCE: 0.8, _C_SKATE: 0.6,
                       _C_DEF: 0.4, _C_PHYS: 0.3},
    },
    "shutdown": {
        "archetypes": {"Two-Way Forward", "Grinder", "Defensive Defenseman",
                       "Physical Defenseman", "Two-Way Defenseman"},
        "composites": {_C_DEF: 1.0, _C_PHYS: 0.7, _C_DISC: 0.6,
                       _C_FACE: 0.5, _C_FINISH: 0.2, _C_CHANCE: 0.2},
    },
    "two_way": {
        "archetypes": {"Two-Way Forward", "Two-Way Defenseman", "Grinder",
                       "Playmaker", "Defensive Defenseman"},
        "composites": {_C_DEF: 0.7, _C_CHANCE: 0.6, _C_FINISH: 0.6,
                       _C_PHYS: 0.5, _C_SKATE: 0.5},
    },
    "energy": {
        "archetypes": {"Grinder", "Enforcer", "Power Forward",
                       "Physical Defenseman"},
        "composites": {_C_PHYS: 1.0, _C_SKATE: 0.7, _C_DISC: 0.5,
                       _C_DEF: 0.4, _C_RETR: 0.5},
    },
    "puck_moving": {
        "archetypes": {"Puck-Moving Defenseman", "Offensive Defenseman",
                       "Two-Way Defenseman", "Playmaker"},
        "composites": {_C_CHANCE: 0.9, _C_SKATE: 0.8, _C_RETR: 0.7,
                       _C_DEF: 0.5},
    },
    "sheltered": {
        "archetypes": {"Two-Way Defenseman", "Defensive Defenseman",
                       "Two-Way Forward"},
        "composites": {_C_DEF: 0.7, _C_DISC: 0.6, _C_SKATE: 0.5},
    },
    "development": {"archetypes": set(), "composites": {}},  # kids learning: no template penalty
    "balanced": {"archetypes": set(), "composites": {}},    # generic: internal fit only
}


def _philosophy_of(coach: Any) -> str:
    return _STYLE_PHILOSOPHY.get(_coach_style_key(coach), "balanced")


# Experiment ledger: chemistry discovery. Tracks combos a coach has tried
# in low-leverage spots and how they worked, so the vision-vs-personnel gap
# is handled honestly instead of by fiat.
_EXPERIMENT_LEDGER: Dict[Any, List[Dict[str, Any]]] = {}


def note_experiment(team_id: Any, unit_key: str, slot: str,
                    outcome01: float) -> None:
    """Record a tried combo's outcome (0..1 fit/efficiency observed).

    outcome01 >= 0.55: the kid seized the audition / the experiment worked.
    outcome01 < 0.45:  failed experiment — the coach learns, not the sim.
    """
    try:
        led = _EXPERIMENT_LEDGER.setdefault(team_id, [])
        for e in led:
            if e.get("unit_key") == unit_key and e.get("slot") == slot:
                e["n"] = int(e.get("n", 1)) + 1
                e["outcome"] = (float(e.get("outcome", 0.5)) * (e["n"] - 1)
                                + _clamp(outcome01, 0.0, 1.0)) / e["n"]
                return
        led.append({"unit_key": unit_key, "slot": slot,
                    "outcome": _clamp(outcome01, 0.0, 1.0), "n": 1})
    except Exception:
        pass


def get_experiment_ledger(team_id: Any) -> List[Dict[str, Any]]:
    try:
        return list(_EXPERIMENT_LEDGER.get(team_id, []))
    except Exception:
        return []


def intended_role_for_slot(coach: Any, slot: str,
                           roster: Optional[List[Any]] = None,
                           team_id: Any = None) -> Dict[str, Any]:
    """The intended role for a line slot, with vision-vs-personnel handling.

    Returns {"role", "adapted", "note"}:
      * role:    the (possibly adapted) intended role string.
      * adapted: True when the coach's vision was degraded toward what the
                 roster can actually staff.
      * note:    hockey-language explanation (storytelling surface).

    Stubborn coaches (low adaptability) force the ideal and pay for it in
    fit; adaptable coaches degrade gracefully and faster.
    """
    try:
        slot = str(slot or "F3").upper()
        phil = _philosophy_of(coach)
        ideal = _SLOT_ROLE_MAP.get(slot, _SLOT_ROLE_MAP["F3"]).get(phil, "two_way")
        if not roster:
            return {"role": ideal, "adapted": False,
                    "note": f"Coach's vision for {slot}: {ideal.replace('_', ' ')}."}
        cap = _roster_capability_for_role(roster, ideal)
        adapt = _coach_adaptability(coach)
        # Failed experiments teach: a combo that flopped here steers away.
        if team_id is not None:
            for e in _EXPERIMENT_LEDGER.get(team_id, []):
                if e.get("slot") == slot and e.get("n", 0) >= 2 \
                        and float(e.get("outcome", 0.5)) < 0.45:
                    ideal = "two_way"
                    return {"role": ideal, "adapted": True,
                            "note": (f"The {slot} experiment didn't take — "
                                     "coach goes back to a simple two-way look.")}
        if cap >= 0.55:
            return {"role": ideal, "adapted": False,
                    "note": f"Roster can staff it: {slot} plays {ideal.replace('_', ' ')}."}
        # Vision exceeds personnel. Adaptable coaches bend now; stubborn
        # coaches hold the ideal (the fit score will make them pay).
        if adapt >= 0.60:
            softened = "two_way" if ideal not in ("scoring", "pp_elite") else ideal
            return {"role": softened, "adapted": True,
                    "note": (f"Coach wants {ideal.replace('_', ' ')} on {slot} "
                             "but the roster can't staff it — expectations ease "
                             "toward a two-way game.")}
        return {"role": ideal, "adapted": False,
                "note": (f"Stubborn bench: coach forces {ideal.replace('_', ' ')} "
                         f"on {slot} anyway. The fit score will make him pay.")}
    except Exception:
        return {"role": "two_way", "adapted": False, "note": ""}


def _roster_capability_for_role(roster: List[Any], role: str) -> float:
    """0..1: can this roster staff the role's template?"""
    try:
        tmpl = _ROLE_TEMPLATES.get(role) or {}
        want_arch = tmpl.get("archetypes") or set()
        want_comp = tmpl.get("composites") or {}
        if not want_arch and not want_comp:
            return 1.0
        arch_hit = 0.0
        if want_arch:
            hits = sum(1 for p in roster if _role_name(p) in want_arch)
            arch_hit = min(1.0, hits / 3.0)
        comp_hit = 1.0
        if want_comp:
            tot = 0.0
            wsum = 0.0
            for key, w in want_comp.items():
                best = max((_comp(p, key) for p in roster), default=50.0)
                tot += (best / 100.0) * w
                wsum += w
            comp_hit = tot / wsum if wsum else 1.0
        return 0.5 * arch_hit + 0.5 * comp_hit
    except Exception:
        return 0.5


def _role_match01(unit: List[Any], role: str) -> float:
    """0..1: how well this personnel matches the intended role's template."""
    try:
        tmpl = _ROLE_TEMPLATES.get(role) or {}
        want_arch = tmpl.get("archetypes") or set()
        want_comp = tmpl.get("composites") or {}
        if not want_arch and not want_comp:
            return 0.65  # generic roles: no opinion, mild prior
        parts = []
        if want_arch and unit:
            hits = sum(1 for p in unit if _role_name(p) in want_arch)
            parts.append(min(1.0, hits / max(1, len(unit))))
        if want_comp and unit:
            tot, wsum = 0.0, 0.0
            for key, w in want_comp.items():
                mean = sum(_comp(p, key) for p in unit) / len(unit)
                tot += (mean / 100.0) * w
                wsum += w
            # Normalize against a "good" benchmark (~72 avg on wanted comps).
            parts.append(_clamp((tot / wsum) / 0.72 if wsum else 0.65, 0.0, 1.0))
        return sum(parts) / len(parts) if parts else 0.65
    except Exception:
        return 0.65

# ---------------------------------------------------------------------------
# Fit scoring, by situation.
# ---------------------------------------------------------------------------

def _ev_internal_fit(unit: List[Any]) -> Tuple[float, Dict[str, float]]:
    """0..1 internal balance for 5v5: archetype complementarity +
    composite overlap (diminishing) / complementarity (multiplying) +
    morale & bonds. Returns (fit01, components)."""
    comps: Dict[str, float] = {}
    n = len(unit)
    if n < 2:
        return 0.65, {"reason": "solo"}
    roles = [_role_name(p) for p in unit]

    # 1) Archetype complementarity, pairwise. Classic combos (Playmaker+
    #    Sniper) score high; redundant pairs (Sniper+Sniper) drag.
    pair_vals = []
    for i in range(n):
        for j in range(i + 1, n):
            pair_vals.append(_pair_complementarity(roles[i], roles[j]))
    mean_pair = sum(pair_vals) / len(pair_vals) if pair_vals else 0.0
    arch01 = _clamp((mean_pair + 10.0) / 22.0, 0.0, 1.0)  # -10..12 -> 0..1
    comps["archetype"] = round(arch01, 3)

    # 2) Composite overlap: the best sets the ceiling, the rest are
    #    marginal. Two 90-finishers don't double the finishing.
    overlap_scores = []
    for key in (_C_FINISH, _C_CHANCE, _C_DEF):
        vals = sorted((_comp(p, key) for p in unit), reverse=True)
        eff = vals[0] + 0.35 * (vals[1] if n > 1 else 0) \
            + 0.15 * (vals[2] if n > 2 else 0)
        raw_sum = sum(vals)
        # Overlap ratio: how much of the raw total survives diminishing.
        overlap_scores.append(eff / raw_sum if raw_sum > 0 else 1.0)
    # A unit of clones (all snipers) overlaps hard -> lower.
    overlap01 = sum(overlap_scores) / len(overlap_scores)
    comps["overlap"] = round(overlap01, 3)

    # 3) Complementary composites MULTIPLY: the playmaker's chance_creation
    #    x the finisher's finishing. One without the other is wasted.
    mean_chance = sum(_comp(p, _C_CHANCE) for p in unit) / n / 100.0
    best_finish = max(_comp(p, _C_FINISH) for p in unit) / 100.0
    multiply01 = _clamp(mean_chance * best_finish * 1.6, 0.0, 1.0)
    comps["multiply"] = round(multiply01, 3)

    # 4) Morale & bonds: line morale + pairwise affinity.
    mean_morale = sum(_morale01(p) for p in unit) / n
    affs = []
    for i in range(n):
        for j in range(i + 1, n):
            affs.append(_pair_affinity(unit[i], unit[j]) / 100.0)
    mean_aff = sum(affs) / len(affs) if affs else 0.5
    room01 = _clamp(0.6 * mean_morale + 0.4 * mean_aff, 0.0, 1.0)
    comps["room"] = round(room01, 3)

    # 5) FORM — first-class. A linemate on a heater lifts his line; a cold
    #    player drags it. Hot lines stay together; cold lines get the
    #    coach's eye. Bounded: +/-0.10 on the fit, never near talent.
    forms = [_form01(p) for p in unit]
    mean_form = sum(forms) / n
    form_lift = 0.10 * mean_form
    comps["form"] = round(mean_form, 3)
    # Storytelling surface: who's driving it.
    try:
        _hi = max(range(n), key=lambda i: forms[i])
        _lo = min(range(n), key=lambda i: forms[i])
        if forms[_hi] >= 0.55:
            comps["heater"] = _pname(unit[_hi])
        if forms[_lo] <= -0.55:
            comps["ice_cold"] = _pname(unit[_lo])
    except Exception:
        pass

    fit = (0.32 * arch01 + 0.18 * overlap01 + 0.22 * multiply01
           + 0.18 * room01 + form_lift)
    return _clamp(fit, 0.0, 1.0), comps


# PP formation roles. Each returns 0..1 coverage for a candidate.
def _pp_point_qb(p: Any) -> float:
    r = _role_name(p)
    score = _comp(p, _C_CHANCE) / 100.0 * 0.7 + _comp(p, _C_SKATE) / 100.0 * 0.3
    if r in ("Offensive Defenseman", "Puck-Moving Defenseman"):
        score = min(1.0, score + 0.25)
    elif r == "Playmaker" and not _is_dman(p):
        score = min(1.0, score + 0.10)
    return _clamp(score, 0.0, 1.0)


def _pp_net_front(p: Any) -> float:
    r = _role_name(p)
    score = (_comp(p, _C_PHYS) / 100.0 * 0.5
             + _comp(p, _C_FINISH) / 100.0 * 0.3
             + _comp(p, _C_RETR) / 100.0 * 0.2)
    if r == "Power Forward":
        score = min(1.0, score + 0.25)
    elif r == "Grinder":
        score = min(1.0, score + 0.10)
    return _clamp(score, 0.0, 1.0)


def _pp_one_timer(p: Any) -> float:
    r = _role_name(p)
    score = _comp(p, _C_FINISH) / 100.0 * 0.75 + _comp(p, _C_SKATE) / 100.0 * 0.25
    if r == "Sniper":
        score = min(1.0, score + 0.20)
    elif r == "Power Forward":
        score = min(1.0, score + 0.08)
    return _clamp(score, 0.0, 1.0)


def _pp_bumper(p: Any) -> float:
    r = _role_name(p)
    score = (_comp(p, _C_CHANCE) / 100.0 * 0.6
             + _comp(p, _C_FINISH) / 100.0 * 0.25
             + _comp(p, _C_RETR) / 100.0 * 0.15)
    if r == "Playmaker":
        score = min(1.0, score + 0.20)
    return _clamp(score, 0.0, 1.0)


def _pp_fit(unit: List[Any]) -> Tuple[float, Dict[str, float]]:
    """0..1 PP formation completeness: point QB, net-front, one-timer,
    bumper/half-wall. Two point QBs + no net-front = malformed."""
    comps: Dict[str, float] = {}
    if len(unit) < 2:
        return 0.5, {"reason": "solo"}
    roles_needed = [("point_qb", _pp_point_qb), ("net_front", _pp_net_front),
                    ("one_timer", _pp_one_timer), ("bumper", _pp_bumper)]
    # Greedy assignment: each role takes its best remaining skater so one
    # star can't cover the whole formation on paper.
    remaining = list(unit)
    cover = {}
    for name, fn in roles_needed:
        if not remaining:
            cover[name] = 0.0
            continue
        best = max(remaining, key=fn)
        cover[name] = fn(best)
        remaining.remove(best)
    # Handedness: the one-timer side wants the off-wing shot. A unit whose
    # best one-timer threat shoots the same hand as the point QB's feed
    # side loses a touch (small, honest hockey detail).
    hands = {_hand(p) for p in unit if _hand(p)}
    hand_bonus = 0.03 if len(hands) > 1 else 0.0
    completeness = sum(cover.values()) / 4.0
    # Malformed penalty: the classic bad PP is a formation pattern — two
    # point QBs and nobody who plays net-front as a role. Role-based (not
    # composite-based): a sniper CAN screen in a pinch, but a unit with no
    # net-front archetype at all is perimeter by design.
    roles = [_role_name(p) for p in unit]
    qb_roles = sum(1 for r in roles
                   if r in ("Offensive Defenseman", "Puck-Moving Defenseman"))
    nf_roles = sum(1 for r in roles
                   if r in ("Power Forward", "Grinder", "Net-Front Presence"))
    malformed = 0.0
    if qb_roles >= 2 and nf_roles == 0:
        malformed = 0.18
    elif cover["point_qb"] > 0.65 and cover["net_front"] < 0.40:
        malformed = 0.18
    if cover["one_timer"] < 0.35 and cover["net_front"] < 0.40:
        malformed = max(malformed, 0.12)  # perimeter PP, nothing inside
    fit = _clamp(completeness + hand_bonus - malformed, 0.0, 1.0)
    comps.update({k: round(v, 3) for k, v in cover.items()})
    comps["completeness"] = round(completeness, 3)
    comps["malformed"] = round(malformed, 3)
    # Room still matters on the PP (bumper chemistry, QB trust).
    room = _room01(unit)
    comps["room"] = round(room, 3)
    fit = _clamp(0.80 * fit + 0.20 * room, 0.0, 1.0)
    # Form is first-class on the PP too: a hot unit stays together.
    try:
        _pf = sum(_form01(p) for p in unit) / len(unit)
        fit = _clamp(fit + 0.05 * _pf, 0.0, 1.0)
        comps["form"] = round(_pf, 3)
        _fms = [_form01(p) for p in unit]
        _hi = max(range(len(unit)), key=lambda i: _fms[i])
        if _fms[_hi] >= 0.55:
            comps["heater"] = _pname(unit[_hi])
    except Exception:
        pass
    return fit, comps


def _room01(unit: List[Any]) -> float:
    n = len(unit)
    if n < 2:
        return 0.65
    mean_morale = sum(_morale01(p) for p in unit) / n
    affs = [_pair_affinity(unit[i], unit[j]) / 100.0
            for i in range(n) for j in range(i + 1, n)]
    mean_aff = sum(affs) / len(affs) if affs else 0.5
    return _clamp(0.6 * mean_morale + 0.4 * mean_aff, 0.0, 1.0)


# PK scheme roles.
def _pk_shot_blocker(p: Any) -> float:
    return _clamp(_comp(p, _C_PHYS) / 100.0 * 0.5
                  + _comp(p, _C_DEF) / 100.0 * 0.5, 0.0, 1.0)


def _pk_faceoff_man(p: Any) -> float:
    return _clamp(_comp(p, _C_FACE) / 100.0, 0.0, 1.0)


def _pk_clearer(p: Any) -> float:
    return _clamp(_comp(p, _C_PHYS) / 100.0 * 0.5
                  + _comp(p, _C_SKATE) / 100.0 * 0.5, 0.0, 1.0)


def _pk_sticks(p: Any) -> float:
    r = _role_name(p)
    s = _comp(p, _C_DEF) / 100.0 * 0.7 + _comp(p, _C_DISC) / 100.0 * 0.3
    if r in ("Defensive Defenseman", "Two-Way Forward", "Two-Way Defenseman"):
        s = min(1.0, s + 0.15)
    return _clamp(s, 0.0, 1.0)


def _pk_fit(unit: List[Any], coach: Any = None) -> Tuple[float, Dict[str, float]]:
    """0..1 PK scheme coverage: shot-blockers, faceoff men, clearers,
    defensive sticks. Pressure vs passive box from coach philosophy."""
    comps: Dict[str, float] = {}
    if len(unit) < 2:
        return 0.5, {"reason": "solo"}
    style = _coach_style_key(coach)
    # Drill sergeants press; most others sit in the passive box.
    pressure = 1.0 if style == "drill_sergeant" else 0.0
    comps["scheme"] = "pressure" if pressure else "passive_box"
    roles_needed = [("shot_blocker", _pk_shot_blocker),
                    ("faceoff_man", _pk_faceoff_man),
                    ("clearer", _pk_clearer), ("sticks", _pk_sticks)]
    remaining = list(unit)
    cover = {}
    for name, fn in roles_needed:
        if not remaining:
            cover[name] = 0.0
            continue
        best = max(remaining, key=fn)
        cover[name] = fn(best)
        remaining.remove(best)
    coverage = sum(cover.values()) / 4.0
    # Pressure scheme needs wheels; a slow unit caught pressing pays.
    if pressure:
        mean_skate = sum(_comp(p, _C_SKATE) for p in unit) / len(unit) / 100.0
        coverage = _clamp(coverage - max(0.0, 0.55 - mean_skate) * 0.5,
                          0.0, 1.0)
        comps["pressure_skate_tax"] = round(max(0.0, 0.55 - mean_skate) * 0.5, 3)
    fit = _clamp(0.85 * coverage + 0.15 * _room01(unit), 0.0, 1.0)
    comps.update({k: round(v, 3) for k, v in cover.items()})
    comps["coverage"] = round(coverage, 3)
    return fit, comps


def _sh_attack_fit(unit: List[Any]) -> Tuple[float, Dict[str, float]]:
    """Shorthanded attack: no formation — a faceoff man for the draw, a
    fast stick for the breakaway, simple sticks otherwise. Rare by nature."""
    if len(unit) < 2:
        return 0.5, {"reason": "solo"}
    face = max((_pk_faceoff_man(p) for p in unit), default=0.0)
    speed = max((_comp(p, _C_SKATE) for p in unit), default=50.0) / 100.0
    sticks = sum(_pk_sticks(p) for p in unit) / len(unit)
    fit = _clamp(0.35 * face + 0.35 * speed + 0.30 * sticks, 0.0, 1.0)
    return fit, {"faceoff_man": round(face, 3), "speed": round(speed, 3),
                 "sticks": round(sticks, 3), "room": round(_room01(unit), 3)}


# ---------------------------------------------------------------------------
# Talent + performance: the highest-weighted foundation.
# ---------------------------------------------------------------------------

def _talent_mult(unit: List[Any]) -> Tuple[float, Dict[str, float]]:
    """Anchored so an average-talent line is ~1.0. Chemistry modulates
    around this; it never overrides it."""
    info: Dict[str, float] = {}
    if not unit:
        return 1.0, info
    mean_ovr = sum(_overall(p) for p in unit) / len(unit)
    mean_form = sum(_form01(p) for p in unit) / len(unit)
    mult = 1.0 + (mean_ovr - 75.0) * 0.004      # 90ovr -> 1.06, 60ovr -> 0.94
    mult *= 1.0 + 0.03 * mean_form              # hot/cold nudges, bounded
    info = {"mean_overall": round(mean_ovr, 1),
            "mean_form": round(mean_form, 3)}
    return _clamp(mult, _TALENT_MIN, _TALENT_MAX), info


def _fit_to_mult(fit01: float) -> float:
    """Average fit -> ~1.0. Truthful: no league pin, just the anchor."""
    return _clamp(0.90 + 0.20 * _clamp(fit01, 0.0, 1.0),
                  _FIT_MIN, _FIT_MAX)

# ---------------------------------------------------------------------------
# Storytelling: every score carries hooks; detail=True explains WHY.
# ---------------------------------------------------------------------------

def _story_for(fit01: float, situation: str, intended_role: Optional[str],
               comps: Dict[str, float]) -> Tuple[str, List[str], str]:
    """(headline_hook, tags, why) in hockey language."""
    tags: List[str] = []
    if fit01 >= 0.72:
        hook, tags = "electric", ["electric", "clicking"]
    elif fit01 >= 0.58:
        hook, tags = "gelling", ["gelling", "finding-it"]
    elif fit01 >= 0.42:
        hook, tags = "ordinary", ["ordinary", "workmanlike"]
    else:
        hook, tags = "disjointed", ["disjointed", "split-up-candidate"]

    bits: List[str] = []
    if situation == PP:
        cov = {k: comps.get(k, 0) for k in
               ("point_qb", "net_front", "one_timer", "bumper")}
        best = max(cov, key=cov.get)
        worst = min(cov, key=cov.get)
        names = {"point_qb": "a point quarterback", "net_front": "net-front presence",
                 "one_timer": "a one-timer threat", "bumper": "a bumper playmaker"}
        bits.append(f"best piece is {names[best]}")
        if cov[worst] < 0.40:
            bits.append(f"missing {names[worst]}")
        if comps.get("malformed", 0) > 0:
            bits.append("too much perimeter, nothing inside")
    elif situation == PK:
        cov = {k: comps.get(k, 0) for k in
               ("shot_blocker", "faceoff_man", "clearer", "sticks")}
        worst = min(cov, key=cov.get)
        names = {"shot_blocker": "shot-blockers", "faceoff_man": "a faceoff man",
                 "clearer": "clearers", "sticks": "defensive sticks"}
        if cov[worst] < 0.45:
            bits.append(f"short on {names[worst]}")
        else:
            bits.append(f"{comps.get('scheme', 'passive_box')} holding shape")
    else:
        a = comps.get("archetype", 0.5)
        m = comps.get("multiply", 0.5)
        o = comps.get("overlap", 0.5)
        if a >= 0.65:
            bits.append("archetypes complement each other")
        elif a < 0.40:
            bits.append("too many of the same player")
        if m >= 0.60:
            bits.append("the setup man has someone to feed")
        elif m < 0.35:
            bits.append("nobody to finish what gets created")
        if o < 0.55:
            bits.append("stepping on each other's strengths")
    if intended_role:
        bits.append(f"asked to play {intended_role.replace('_', ' ')}")
    # Form stories — the ones fans remember.
    try:
        heater = comps.get("heater")
        cold = comps.get("ice_cold")
        if heater:
            bits.append(f"{heater} is heating up and can't be taken off the ice")
            tags.append("heater")
        if cold:
            bits.append(f"{cold} has gone cold — the coach's eye is on him")
            tags.append("ice-cold")
    except Exception:
        pass
    why = ("This unit is " + hook + " because " + "; ".join(bits) + "."
           if bits else f"This unit is {hook}.")
    return hook, tags, why


class FitReport:
    """What detail=True returns: the number plus the story."""
    def __init__(self, efficiency: float, fit01: float, situation: str,
                 intended_role: Optional[str], components: Dict[str, float],
                 talent: Dict[str, float], hook: str, tags: List[str],
                 why: str):
        self.efficiency = efficiency
        self.fit01 = fit01
        self.situation = situation
        self.intended_role = intended_role
        self.components = components
        self.talent = talent
        self.hook = hook
        self.tags = tags
        self.why = why

    def __float__(self) -> float:
        return float(self.efficiency)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"FitReport(eff={self.efficiency:.3f} fit={self.fit01:.2f} "
                f"sit={self.situation} hook={self.hook})")


# ---------------------------------------------------------------------------
# The core: unit efficiency, cached per unit per game on the sim.
# ---------------------------------------------------------------------------

def _cache_on(sim: Any) -> Optional[Dict]:
    try:
        c = getattr(sim, "_line_chem_cache", None)
        if c is None:
            c = {}
            setattr(sim, "_line_chem_cache", c)
        return c
    except Exception:
        return None


def _emitted_on(sim: Any) -> Optional[set]:
    try:
        s = getattr(sim, "_line_chem_stories", None)
        if s is None:
            s = set()
            setattr(sim, "_line_chem_stories", s)
        return s
    except Exception:
        return None


def _try_emit_story(sim: Any, unit_key: Tuple, hook: str, why: str,
                    situation: str, efficiency: float) -> None:
    """Once per unit per game, notable units earn a headline/pbp note.
    Only engines with a headline channel hear it (GameSim); the story data
    itself lives in the shared module either way."""
    try:
        emitted = _emitted_on(sim)
        if emitted is None or unit_key in emitted:
            return
        emitted.add(unit_key)
        if abs(efficiency - 1.0) < 0.045:
            return  # only notable units get ink
        payload = {"kind": "line_chemistry", "hook": hook,
                   "text": why, "situation": situation,
                   "efficiency": round(efficiency, 3)}
        headlines = getattr(sim, "pending_headlines", None)
        if isinstance(headlines, list):
            headlines.append(payload)
            return
        emit = getattr(sim, "_emit_pbp", None)
        if callable(emit):
            try:
                emit("line_chemistry", **payload)
            except Exception:
                pass
    except Exception:
        pass


def unit_efficiency(unit: List[Any], situation: str = EV,
                    intended_role: Optional[str] = None,
                    sim: Any = None, team: Any = None,
                    coach: Any = None, detail: bool = False):
    """Bounded efficiency multiplier for a unit's grade-A chance creation.

    situation: 'ev' | 'pp' | 'pk' (attacking team's perspective).
    Applied at the grade-A chance sites in both engines — never to
    finishing, never to grade ceilings. Cached per unit per game on sim.

    detail=True returns a FitReport (number + story hooks + WHY).
    """
    try:
        skaters = [p for p in (unit or []) if p is not None]
        if not skaters:
            # Additive safety: no unit, no opinion — exactly neutral.
            if detail:
                return FitReport(efficiency=1.0, fit01=0.5,
                                 situation=situation or EV, intended_role=None,
                                 components={}, talent={}, hook="ordinary",
                                 tags=["ordinary"],
                                 why="No unit to score; neutral.")
            return 1.0
        situation = str(situation or EV).lower()
        if situation not in (EV, PP, PK):
            situation = EV
        if coach is None:
            coach = _resolve_coach(team, sim)

        key = (frozenset(_pid(p) for p in skaters), situation,
               str(intended_role or ""))
        cache = _cache_on(sim) if sim is not None else None
        if cache is not None and key in cache and not detail:
            return cache[key]

        # --- fit branch by situation ---
        if situation == PP:
            fit01, fcomps = _pp_fit(skaters)
            role = intended_role or "pp_elite"
            role01 = 1.0  # formation completeness IS the PP role
        elif situation == PK:
            fit01, fcomps = _sh_attack_fit(skaters)
            role = intended_role or "pk_attack"
            role01 = 1.0
        else:
            fit01, fcomps = _ev_internal_fit(skaters)
            role = intended_role
            role01 = _role_match01(skaters, role) if role else 0.65
            # Intended role bends the internal fit, it doesn't replace it:
            # a perfect shutdown line and a perfect scoring line are
            # different perfections.
            fit01 = _clamp(0.70 * fit01 + 0.30 * role01, 0.0, 1.0)

        tmult, tinfo = _talent_mult(skaters)
        fmult = _fit_to_mult(fit01)
        eff = _clamp(tmult * fmult, _EFF_MIN, _EFF_MAX)

        hook, tags, why = _story_for(fit01, situation, role
                                     if situation == EV else None, fcomps)

        if cache is not None and not detail:
            cache[key] = eff
            _try_emit_story(sim, key, hook, why, situation, eff)
            return eff
        if cache is not None and detail:
            # Still warm the fast path for the engine.
            cache[key] = eff
        rep = FitReport(efficiency=round(eff, 4), fit01=round(fit01, 3),
                        situation=situation, intended_role=role,
                        components=fcomps, talent=tinfo,
                        hook=hook, tags=tags, why=why)
        return rep if detail else rep.efficiency
    except Exception:
        if detail:
            return FitReport(efficiency=1.0, fit01=0.5, situation=EV,
                             intended_role=None, components={}, talent={},
                             hook="ordinary", tags=["ordinary"],
                             why="Chemistry unavailable; neutral.")
        return 1.0


def pk_denial_factor(defending_unit: List[Any], coach: Any = None,
                     sim: Any = None, team: Any = None) -> float:
    """The defending PK unit's scheme coverage as a chance multiplier.

    A great PK ([shot-blockers, faceoff men, clearers, sticks] all covered)
    shaves up to 6% off the chance; a malformed one shaves nothing. Always
    <= 1.0. Both engines apply it at the same point as unit_efficiency.
    """
    try:
        skaters = [p for p in (defending_unit or []) if p is not None]
        if coach is None:
            coach = _resolve_coach(team, sim)
        fit01, _ = _pk_fit(skaters, coach=coach)
        # Below-average coverage shaves nothing; a perfect PK shaves 6%.
        return _clamp(1.0 - 0.06 * _clamp((fit01 - 0.45) / 0.55, 0.0, 1.0),
                      _DENY_MIN, _DENY_MAX)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# PP zone sustenance: formation completeness on the VOLUME channel.
#
# A well-structured PP (point QB + net-front + one-timer + bumper, no
# malformed flag) sustains zone time and generates its looks; a malformed
# PP (perimeter, nothing inside) gets cleared and struggles to re-enter.
#
# Shared by both engines (parity by construction):
#   - GameSim applies it to zone sustenance (keep-ins, clear disruption,
#     5v4 forecheck strip) -- the volume funnel into SOG.
#   - quick_sim applies it to PP shot_prob -- the same funnel, no zones.
# Never touches finishing or grade ceilings. Anchored at the league-average
# PP1 (fit ~0.85 -> 1.00) so the channel differentiates structure without
# moving the league mean on its own.
# ---------------------------------------------------------------------------
# Anchored at the measured on-ice PP-unit mean (PP1/PP2 rotation, soft-cap
# governance), not the PP1 paper mean -- the channel must be ~1.0 for the
# average unit actually deployed, or it weakens the league's PPs outright.
PP_FIT_ANCHOR = 0.76
_PP_SUS_MIN, _PP_SUS_MAX = 0.75, 1.25


def pp_zone_sustenance(unit: List[Any], sim: Any = None,
                       team: Any = None) -> float:
    """0.75..1.25 PP zone-sustenance multiplier from formation completeness.

    unit: the 5-man PP unit (skaters). sim/team thread through to the shared
    unit_efficiency cache (detail=True warms the fast path).
    """
    try:
        rep = unit_efficiency(unit, situation=PP, sim=sim, team=team,
                              detail=True)
        fit01 = float(getattr(rep, "fit01", PP_FIT_ANCHOR))
    except Exception:
        fit01 = PP_FIT_ANCHOR
    return _clamp(1.0 + 2.0 * (fit01 - PP_FIT_ANCHOR),
                  _PP_SUS_MIN, _PP_SUS_MAX)

# ---------------------------------------------------------------------------
# Schemed-against relief, apportioned THROUGH chemistry.
#
# The relief budget stays zero-sum and bounded (scenario_composites owns
# that). This function decides WHO converts it: shares weight by archetype
# complementarity with the star. The net-front guy next to a schemed
# playmaker eats; a redundant second sniper gets table scraps. Shares sum
# to 1.0 over the linemates, so the unit-wide dividend never exceeds the
# budget no matter the unit size. (This is the Raffl fix: the old code gave
# EVERY linemate the full budget.)
# ---------------------------------------------------------------------------

def chemistry_relief_share(shooter: Any, star: Any,
                           unit: List[Any]) -> float:
    """0..1 share of the schemed-against relief budget for this shooter.
    Never raises; falls back to an even split."""
    try:
        # Shares are computed over every non-star linemate (the shooter's
        # own weight included); they sum to 1.0 across the unit.
        mates = [p for p in (unit or [])
                 if p is not None and p is not star
                 and _pid(p) != _pid(star)]
        if not mates:
            return 1.0
        star_role = _role_name(star)
        weights = []
        for m in mates:
            c = _pair_complementarity(star_role, _role_name(m))
            # -10..12 -> weight; floor so nobody is fully shut out.
            w = max(0.12, (c + 10.0) / 22.0)
            # Finishers convert relief best: the dividend is chance volume.
            w *= 0.75 + 0.50 * (_comp(m, _C_FINISH) / 100.0)
            weights.append(w)
        total = sum(weights)
        if total <= 0:
            return 1.0 / len(mates)
        # Find the shooter's weight by identity.
        sw = None
        for m, w in zip(mates, weights):
            if m is shooter or _pid(m) == _pid(shooter):
                sw = w
                break
        if sw is None:
            return 1.0 / len(mates)
        return _clamp(sw / total, 0.0, 1.0)
    except Exception:
        try:
            n = len([p for p in (unit or []) if p is not None]) - 1
            return 1.0 / max(1, n)
        except Exception:
            return 1.0


# ---------------------------------------------------------------------------
# PP micro-rotation: heaters get better looks WITHIN the unit.
#
# Bounded share redistribution (mean 1.0, [0.90, 1.15]) applied to the
# shooter-choice weight on the power play. Never changes WHO dresses —
# the unit is the unit; this only tilts which stick the puck finds.
# Coach philosophy modulates via deployment_policy.leverage_score
# (heaters ride under adaptable coaches; stubborn coaches flatten it).
# ---------------------------------------------------------------------------

def pp_look_shares(unit: List[Any], coach: Any = None,
                   sim: Any = None, team: Any = None) -> Dict[Any, float]:
    """{player_id: look-share multiplier}. Mean 1.0 over the unit."""
    try:
        skaters = [p for p in (unit or []) if p is not None]
        if not skaters:
            return {}
        if coach is None:
            coach = _resolve_coach(team, sim)
        raw: Dict[Any, float] = {}
        for p in skaters:
            try:
                if _leverage_score is not None:
                    lv = float(_leverage_score(p, coach=coach))
                else:
                    lv = 1.0
            except Exception:
                lv = 1.0
            # Only the heater half of leverage tilts looks; slumps don't
            # lose their PP spot (that would change who dresses).
            tilt = 1.0 + max(0.0, lv - 1.0) * 0.5
            raw[_pid(p)] = _clamp(tilt, _LOOK_MIN, _LOOK_MAX)
        mean = sum(raw.values()) / len(raw)
        if mean <= 0:
            return {k: 1.0 for k in raw}
        return {k: _clamp(v / mean, _LOOK_MIN, _LOOK_MAX)
                for k, v in raw.items()}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# How the coach picks special-teams personnel.
#
# The deployment weighting directive, extended to ST selection:
#   1. talent + performance HIGHEST-weighted;
#   2. team direction (rebuilder plays kids on PP2; contender leans vets);
#   3. recency (hot players earn PP looks — bounded);
#   4. coach-player relationships, under the morale blanket;
#   5. coach philosophy modulates every scaling.
# Hockey specifics: handedness (one-timer side), faceoff ability for PP
# starts, PK specialists. Returns players sorted best-first with scores.
# ---------------------------------------------------------------------------

def rank_special_teams_candidates(players: List[Any], unit: str = "pp",
                                  coach: Any = None, team: Any = None,
                                  team_direction: Optional[str] = None,
                                  detail: bool = False) -> List[Any]:
    """Rank skaters for a PP or PK unit. Shared API; the engines' shift
    logic calls this where a clean seam exists (documented below)."""
    try:
        unit = str(unit or "pp").lower()
        is_pp = unit.startswith("pp")
        if coach is None:
            coach = _resolve_coach(team)
        style = _coach_style_key(coach)
        scored = []
        for p in players or []:
            if p is None:
                continue
            try:
                score, parts = _st_candidate_score(p, is_pp, coach, style,
                                                   team_direction)
            except Exception:
                score, parts = 0.5, {}
            scored.append((score, p, parts))
        scored.sort(key=lambda t: t[0], reverse=True)
        if detail:
            return [(p, round(s, 3), parts) for s, p, parts in scored]
        return [p for _, p, _ in scored]
    except Exception:
        return list(players or [])


def _st_candidate_score(p: Any, is_pp: bool, coach: Any, style: str,
                        team_direction: Optional[str]) -> Tuple[float, Dict]:
    parts: Dict[str, float] = {}
    # 1) Talent + performance: the highest-weighted foundation.
    # THE BOUND: performance is real (heaters earn looks) but talent stays
    # the foundation — an 8-point overall gap survives anything but a
    # max heater, and a ~20-point gap survives everything. Form wins
    # close races; it never inverts tiers.
    talent = _overall(p) / 100.0
    perf = 0.5 + 0.5 * _form01(p)  # 0..1
    parts["talent"] = round(0.80 * talent + 0.20 * perf, 3)

    # 2) Team direction: rebuilders play kids on PP2; contenders lean vets.
    direction = (team_direction or "contender").lower()
    age = _age(p)
    dir_bonus = 0.0
    if age is not None:
        if direction.startswith("rebuild"):
            if age <= 24:
                dir_bonus = 0.06   # kids get the PP2 audition
            elif age >= 32:
                dir_bonus = -0.05  # fading vets cede the reps
        else:
            if age >= 30:
                dir_bonus = 0.04   # contenders trust veterans
            elif age <= 21:
                dir_bonus = -0.04
    parts["direction"] = round(dir_bonus, 3)

    # 3) Recency: hot players earn PP looks (bounded — wins close races,
    #    never inverts tiers: max swing 0.04 vs ~0.10 per 20 overall pts).
    rec = 0.04 * max(0.0, _form01(p))
    # Stubborn coaches resist the hot hand; adaptable ride it.
    adapt = _coach_adaptability(coach)
    rec *= 0.4 + 0.6 * adapt
    parts["recency"] = round(rec, 3)

    # 4) Relationships under the morale blanket: coach trust + morale.
    trust = 0.0
    try:
        bonds = getattr(p, "coach_bonds", None) or {}
        ckey = str(getattr(coach, "id", "") or "")
        trust = float(bonds.get(ckey, 0.5)) if isinstance(bonds, dict) else 0.5
        trust = (trust - 0.5) * 0.10
    except Exception:
        trust = 0.0
    morale_tilt = (_morale01(p) - 0.70) * 0.10
    # Players' coaches let relationships swing; drill sergeants flatten them.
    rel_w = {"players_coach": 1.4, "motivator": 1.2, "drill_sergeant": 0.5,
             "tactician": 0.8, "developer": 1.0, "balanced": 1.0}.get(style, 1.0)
    parts["relationships"] = round((trust + morale_tilt) * rel_w, 3)

    # 5) Hockey specifics.
    hockey = 0.0
    if is_pp:
        # One-timer side: off-hand shooters score the flank bonus.
        r = _role_name(p)
        if r == "Sniper":
            hockey += 0.05
        if _hand(p) == "left":
            hockey += 0.015  # most goalies/teams set for right-side feeds
        # Faceoff ability for PP starts (centers).
        hockey += 0.06 * (_comp(p, _C_FACE) / 100.0) * (1.0 if "Center" in str(
            getattr(p, "primary_position", "")) else 0.4)
        # Formation-role coverage: being a real PP piece matters.
        hockey += 0.08 * max(_pp_point_qb(p), _pp_net_front(p),
                             _pp_one_timer(p), _pp_bumper(p))
    else:
        # PK specialists: blocks, clears, faceoffs, sticks.
        hockey += 0.08 * max(_pk_shot_blocker(p), _pk_faceoff_man(p),
                             _pk_clearer(p), _pk_sticks(p))
        try:
            traits = getattr(p, "traits", None) or []
            tnames = {str(getattr(t, "name", t)).lower() for t in traits}
            if "penalty killer" in tnames or "shot blocker" in tnames:
                hockey += 0.05
        except Exception:
            pass
    # Philosophy modulates the hockey-specifics too: tacticians weight
    # structure (PK) specialists more; motivators weight PP flash.
    if not is_pp and style in ("tactician", "drill_sergeant"):
        hockey *= 1.15
    if is_pp and style == "motivator":
        hockey *= 1.10
    parts["hockey"] = round(hockey, 3)

    # Developers force-feed youth on PP2 regardless of direction.
    if style == "developer" and is_pp and age is not None and age <= 23:
        parts["development"] = 0.06
    else:
        parts["development"] = 0.0

    total = (0.62 * parts["talent"] + parts["direction"] + parts["recency"]
             + parts["relationships"] + 0.55 * parts["hockey"]
             + parts["development"])
    # Keep it bounded and legible: talent dominates, the rest modulates.
    return _clamp(total, 0.0, 1.0), parts

# ---------------------------------------------------------------------------
# The hot-hand audition: form in coach selection (Muck 2026-09-30).
#
# Who's hot earns the PP looks, the audition on a higher line, the extra
# shift in a big moment (that last one is leverage_score's existing lane).
# A depth player or call-up on a tear forces the vision-vs-personnel
# question — the coach has to find him minutes. Post-injury returnees get
# sheltered looks. Breakout streaks (mesh_streak) count double.
#
# THE BOUND (standing rule): recency NEVER permanently overrides the
# talent hierarchy. A two-week heater earns a LOOK — one line up, tracked
# in the experiment ledger. Sustained performance earns the spot; a faded
# heater goes back down. A grinder doesn't become a first-liner forever
# because of October.
# ---------------------------------------------------------------------------

_HEATER_GATE = 0.55    # matches mesh_system._STREAK_GATE
_COLD_GATE = -0.55
_AUDITION_GAMES = 3    # sustained this long -> earns the spot
_AUDITION_FADE = 0.15  # form below this -> the look ends, back down
_TALENT_GUARD = 12.0   # heater's overall within 12 of the target line's mean


def _gp(p: Any) -> int:
    try:
        return int(getattr(p, "games_played", 0) or 0)
    except Exception:
        return 0


def _team_auditions(team: Any) -> Dict[Any, Dict]:
    try:
        d = getattr(team, "_lc_auditions", None)
        if d is None:
            d = {}
            setattr(team, "_lc_auditions", d)
        return d
    except Exception:
        return {}


def _find_in_lines(fw_lines: List[List[Any]], pid: Any) -> Optional[Tuple[int, int]]:
    for li, line in enumerate(fw_lines or []):
        for si, p in enumerate(line or []):
            if p is not None and _pid(p) == pid:
                return li, si
    return None


def _line_mean_ovr(line: List[Any]) -> float:
    ps = [p for p in (line or []) if p is not None]
    if not ps:
        return 75.0
    return sum(_overall(p) for p in ps) / len(ps)


def hot_hand_auditions(team: Any, lineup: Any, coach: Any = None,
                       returnees: Optional[List[Any]] = None):
    """Apply the hot-hand audition to a game-day lineup. Returns
    (lineup, notes). Idempotent per call: active auditions are unapplied
    first, then re-evaluated, so repeat calls within a game don't stack.

    * Heaters (form >= 0.55) on L3/L4 earn a one-line bump audition,
      swapping with a cold player above. Talent-guarded.
    * Ice-cold (form <= -0.55) top-sixers get the coach's eye (note;
      the bump-down happens through the swap).
    * Returnees (explicit list) get sheltered: down a line, bounded.
    * PP2: the hottest dressed forward outside the PP units swaps in for
      the coldest PP2 forward. One swap, talent-guarded.
    * Sustained (>= 3 games, form >= 0.35) -> earns the spot (ledger).
      Faded (form < 0.15) -> back down (ledger).

    Never changes who dresses — only which line. Never raises.
    """
    notes: List[str] = []
    try:
        if not isinstance(lineup, dict):
            return lineup, notes
        fw = lineup.get("Forwards")
        if not isinstance(fw, list) or len(fw) < 4:
            return lineup, notes
        if coach is None:
            coach = _resolve_coach(team)
        adapt = _coach_adaptability(coach)
        team_id = getattr(team, "team_name", None) or id(team)
        active = _team_auditions(team)

        # -- 1) unapply active auditions (idempotency) -------------------
        for pid, aud in list(active.items()):
            a = _find_in_lines(fw, pid)
            b = _find_in_lines(fw, aud.get("partner_pid"))
            if a and b:
                (li_a, si_a), (li_b, si_b) = a, b
                fw[li_a][si_a], fw[li_b][si_b] = fw[li_b][si_b], fw[li_a][si_a]

        # -- 2) resolve active auditions by games played -----------------
        # (earned auditions are permanent arrangements now — skip)
        for pid, aud in list(active.items()):
            if aud.get("earned"):
                continue
            loc = _find_in_lines(fw, pid)
            if not loc:
                del active[pid]
                continue
            p = fw[loc[0]][loc[1]]
            elapsed = _gp(p) - int(aud.get("start_gp", 0))
            form = _form01(p)
            slot = f"F{aud.get('from_line', 3) + 1}"
            ukey = f"audition:{pid}:{slot}"
            if elapsed >= _AUDITION_GAMES:
                if form >= 0.35:
                    # Sustained — earns the spot (arrangement stays applied).
                    note_experiment(team_id, ukey, slot, 0.78)
                    notes.append(
                        f"{_pname(p)} seized the audition — the "
                        f"{slot.replace('F', 'line ')} spot is his.")
                    aud["earned"] = True
                elif form < _AUDITION_FADE:
                    note_experiment(team_id, ukey, slot, 0.32)
                    notes.append(
                        f"{_pname(p)}'s heater cooled — back down the lineup.")
                    del active[pid]
                # else: still auditioning; re-applied in step 3.

        # -- 3) new auditions (stubborn coaches resist recency) ----------
        if adapt >= 0.45:
            _new_heater_auditions(fw, active, notes, team_id)
            _new_returnee_shelters(fw, active, notes, team_id,
                                   returnees or [])
        else:
            # Stubborn bench: no auditions — but the cold still get noticed.
            for li in (0, 1):
                for p in fw[li] or []:
                    if p is not None and _form01(p) <= _COLD_GATE:
                        notes.append(
                            f"{_pname(p)} has gone quiet, but this coach "
                            "doesn't chase heaters — the lines stay.")

        # -- 4) re-apply all still-active auditions (earned ones are now
        #      permanent arrangements — they stay applied) -----------------
        for pid, aud in active.items():
            a = _find_in_lines(fw, pid)
            b = _find_in_lines(fw, aud.get("partner_pid"))
            if a and b and a[0] != b[0]:
                (li_a, si_a), (li_b, si_b) = a, b
                fw[li_a][si_a], fw[li_b][si_b] = fw[li_b][si_b], fw[li_a][si_a]

        # -- 5) PP2 hot-swap (bounded: one swap, doesn't change who dresses)
        _pp2_hot_swap(lineup, notes)

        try:
            setattr(team, "_lc_lineup_notes", notes)
        except Exception:
            pass
        return lineup, notes
    except Exception:
        return lineup, notes


def _new_heater_auditions(fw: List[List[Any]], active: Dict, notes: List[str],
                          team_id: Any) -> None:
    """Heaters on L3/L4 earn a one-line bump; the coldest above goes down."""
    try:
        for li in (3, 2):  # L4, then L3
            for p in list(fw[li] or []):
                if p is None:
                    continue
                pid = _pid(p)
                if pid in active:
                    continue
                form = _form01(p)
                # Breakout streaks count double: mesh_streak >= 3 lowers the gate.
                gate = _HEATER_GATE - (0.10 if _streak(p) >= 3 else 0.0)
                if form < gate:
                    continue
                target = li - 1
                # Talent guard: no grinder-to-first-line fairy tales.
                if _overall(p) < _line_mean_ovr(fw[target]) - _TALENT_GUARD:
                    notes.append(
                        f"{_pname(p)} is on fire, but the talent gap to line "
                        f"{target + 1} is real — the look waits.")
                    continue
                # Swap partner: the coldest on the line above, must be cold
                # or far enough off the heater's pace.
                cands = [q for q in (fw[target] or []) if q is not None
                         and _pid(q) not in active]
                if not cands:
                    continue
                partner = min(cands, key=_form01)
                pf = _form01(partner)
                if not (pf <= -0.20 or (pf < 0.20 and form - pf >= 0.90)):
                    continue
                active[pid] = {"partner_pid": _pid(partner),
                               "from_line": li, "to_line": target,
                               "start_gp": _gp(p), "kind": "heater"}
                if pf <= _COLD_GATE:
                    notes.append(
                        f"{_pname(p)} can't be taken off the ice — he gets a "
                        f"look on line {target + 1} while {_pname(partner)} "
                        "tries to find his game further down.")
                else:
                    notes.append(
                        f"{_pname(p)} earns an audition on line {target + 1} — "
                        "a two-week heater is a look, not a promotion.")
                return  # one audition per line per game keeps it legible
    except Exception:
        pass


def _new_returnee_shelters(fw: List[List[Any]], active: Dict, notes: List[str],
                           team_id: Any, returnees: List[Any]) -> None:
    """Post-injury returnees get sheltered: down a line, bounded."""
    try:
        rids = {_pid(p) for p in (returnees or []) if p is not None}
        if not rids:
            return
        for li in (0, 1, 2):
            for p in list(fw[li] or []):
                if p is None or _pid(p) not in rids or _pid(p) in active:
                    continue
                below = li + 1
                cands = [q for q in (fw[below] or []) if q is not None
                         and _pid(q) not in active and _form01(q) <= 0.30]
                if not cands:
                    continue
                partner = min(cands, key=_form01)
                active[_pid(p)] = {"partner_pid": _pid(partner),
                                   "from_line": li, "to_line": below,
                                   "start_gp": _gp(p), "kind": "returnee"}
                notes.append(
                    f"{_pname(p)} eases back in on line {below + 1} — "
                    "sheltered minutes while the legs come back.")
                return
    except Exception:
        pass


def _pp2_hot_swap(lineup: Dict, notes: List[str]) -> None:
    """One bounded PP2 swap: hottest dressed forward in, coldest out."""
    try:
        pp1 = lineup.get("PP1") or {}
        pp2 = lineup.get("PP2") or {}
        pp2f = pp2.get("Forwards")
        if not isinstance(pp2f, list):
            return
        on_pp = {_pid(p) for k in ("PP1", "PP2")
                 for p in ((lineup.get(k) or {}).get("Forwards") or [])
                 if p is not None}
        dressed = [p for line in (lineup.get("Forwards") or [])
                   for p in (line or []) if p is not None]
        hot = [p for p in dressed
               if _pid(p) not in on_pp and _form01(p) >= _HEATER_GATE]
        if not hot:
            return
        cand = max(hot, key=_form01)
        cold = [p for p in pp2f if p is not None and _form01(p) < 0.0]
        if not cold:
            return
        out = min(cold, key=_form01)
        if _overall(cand) < _line_mean_ovr(pp2f) - 10.0:
            return
        i_in = next((i for i, p in enumerate(dressed)
                     if p is not None and _pid(p) == _pid(cand)), None)
        i_out = next((i for i, p in enumerate(pp2f)
                      if p is not None and _pid(p) == _pid(out)), None)
        if i_in is None or i_out is None:
            return
        # Swap within the dressed group: PP2 membership changes, the
        # 18 skaters dressed don't.
        li_in = _find_in_lines(lineup["Forwards"], _pid(cand))
        if not li_in:
            return
        fw = lineup["Forwards"]
        fw[li_in[0]][li_in[1]], pp2f[i_out] = pp2f[i_out], fw[li_in[0]][li_in[1]]
        notes.append(
            f"{_pname(cand)}'s heater earns him a PP2 look — "
            f"{_pname(out)} slides out of the second unit.")
    except Exception:
        pass
