"""Coaching-aware individual practice: who teaches, who learns, and how the
system shapes it.

The individual practice engine used to take a flat ``trainer_quality``
number. This module replaces that number with the actual coaching staff:

- **Who runs the drill** -- the goalie coach takes the goalies; the
  assistant whose specialty matches the drill takes the skaters; the head
  coach oversees everything (his voice blends in).
- **Whether the coach knows how to teach it** -- ``attacking_coaching``
  teaches shooting, ``defensive_coaching`` teaches checking, and so on.
  A defensive specialist running a shooting drill for a Sniper is the
  wrong teacher; the model says so out loud.
- **Whether the player takes to the drill** -- archetype affinity (a
  Sniper lives for shooting practice, an Enforcer doesn't) crossed with
  attitude (coachability, work ethic, morale, determination).
- **Whether the personalities mesh** -- the existing coach-style /
  engagement-style fit model (reputation_system) gates friction or
  synergy, with a small morale cost when a bad fit meets a hard skate.
- **Whether the drill fits the system** -- an offensive club drilling
  shooting is training its identity; a trap club drilling shooting is
  just exercise. Aligned practice also nudges tactical familiarity.

Pure logic, no GUI. Every read is getattr-defensive so old saves and
partial stubs never raise. Multipliers are deliberately modest: coaching
is the difference between good and great development, never the whole
story (talent and age still dominate).

Scales: staff attributes are native 1-100; player coachability /
work_ethic / adaptability are 50-90; morale is 1-100.
"""

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Attribute -> drill. Lets background development (the weekly all-team
# tick) run through the same coaching model as practice sessions: each
# attribute is "taught" by the drill that trains it. One map, one
# mechanic, user and AI alike.
# ---------------------------------------------------------------------------
ATTRIBUTE_DRILL: Dict[str, str] = {
    "skating": "skating", "speed": "skating",
    "shooting": "shooting", "shooting_accuracy": "shooting",
    "passing": "passing", "vision": "passing", "puck_protection": "passing",
    "checking": "checking", "stick_checking": "checking",
    "blocking": "checking",
    "positioning": "defense", "defense": "defense",
    "faceoffs": "faceoffs",
    "strength": "conditioning",
    "hockey_iq": "hockey_iq",
    "leadership": "leadership", "composure": "leadership",
    "goaltending": "defense", "reflexes": "defense",
    "rebound_control": "defense",
}


def attribute_drill(attribute: str) -> Optional[str]:
    """Which practice drill trains this attribute (None if unmapped)."""
    try:
        return ATTRIBUTE_DRILL.get(str(attribute).lower())
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Drill -> coaching specialty. Each drill lists the staff attributes that
# teach it, most important first. Used to pick the right assistant and to
# rate how well a given coach teaches a given drill.
# ---------------------------------------------------------------------------
DRILL_SPECIALTY: Dict[str, Tuple[str, ...]] = {
    "skating": ("technical_coaching", "coaching_forwards",
                "coaching_defensemen"),
    "shooting": ("attacking_coaching", "technical_coaching",
                 "coaching_forwards"),
    "passing": ("attacking_coaching", "tactical_knowledge",
                "coaching_forwards"),
    "checking": ("defensive_coaching", "coaching_defensemen",
                 "coaching_forwards"),
    "defense": ("defensive_coaching", "tactical_knowledge",
                "coaching_defensemen"),
    "faceoffs": ("technical_coaching", "tactical_knowledge",
                 "coaching_forwards"),
    "conditioning": ("technical_coaching", "discipline",
                     "working_with_youngsters"),
    "hockey_iq": ("tactical_knowledge", "mental_coaching",
                  "attacking_coaching", "defensive_coaching"),
    "teamwork": ("man_management", "leadership", "motivating"),
    "leadership": ("leadership", "motivating", "man_management"),
}

# Practice types that are skater-only in spirit (goalies get little from
# them) and the goalie-friendly set. Used for the position sanity check.
_GOALIE_UNFRIENDLY = {"shooting", "checking", "faceoffs"}
_GOALIE_MULT = {"shooting": 0.55, "checking": 0.55, "faceoffs": 0.6,
                "passing": 0.75}


def _num(obj: Any, name: str, default: float = 50.0) -> float:
    try:
        v = getattr(obj, name, default)
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _position_group(player: Any) -> str:
    """'goalie' | 'defense' | 'offense' from the player's position."""
    try:
        pos = str(getattr(player, "primary_position", "") or "").upper()
        if "GOALIE" in pos or pos == "G":
            return "goalie"
        if "DEFENSE" in pos or pos in ("D", "LD", "RD"):
            return "defense"
        return "offense"
    except Exception:
        return "offense"


def _staff_list(team: Any) -> List[Any]:
    try:
        return list(getattr(team, "staff", []) or [])
    except Exception:
        return []


def _role_of(staff: Any) -> str:
    try:
        return str(getattr(getattr(staff, "role", None), "value", "") or "")
    except Exception:
        return ""


def head_coach_of(team: Any) -> Optional[Any]:
    """The team's head coach, or None.

    Prefers NHL-assignment staff: team.staff now also carries the club's
    AHL coaches, who must never be picked as the NHL bench boss.
    """
    cands = [stf for stf in _staff_list(team)
             if "Head Coach" in _role_of(stf)]
    for stf in cands:
        if (getattr(stf, "assignment", "nhl") or "nhl") == "nhl":
            return stf
    return cands[0] if cands else None


def assistants_of(team: Any) -> List[Any]:
    out = []
    for stf in _staff_list(team):
        r = _role_of(stf)
        if ("Assistant Coach" in r or "Associate Coach" in r) and (
                getattr(stf, "assignment", "nhl") or "nhl") == "nhl":
            out.append(stf)
    return out


def goalie_coach_of(team: Any) -> Optional[Any]:
    cands = [stf for stf in _staff_list(team)
             if "Goalie Coach" in _role_of(stf)]
    for stf in cands:
        if (getattr(stf, "assignment", "nhl") or "nhl") == "nhl":
            return stf
    return cands[0] if cands else None


def _staff_name(staff: Any) -> str:
    try:
        n = (f"{getattr(staff, 'first_name', '')} "
             f"{getattr(staff, 'last_name', '')}").strip()
        return n or "Coach"
    except Exception:
        return "Coach"


# ---------------------------------------------------------------------------
# Who runs the drill
# ---------------------------------------------------------------------------
def session_coach(team: Any, player: Any,
                  practice_type: str) -> Tuple[Optional[Any], str]:
    """Pick the coach running this drill.

    Goalies go to the goalie coach; skaters go to the assistant whose
    specialty best matches the drill; the head coach covers when nobody
    better is on staff. Returns (coach, role_label).
    """
    ptype = str(practice_type or "").lower()
    group = _position_group(player)
    if group == "goalie":
        gc = goalie_coach_of(team)
        if gc is not None:
            return gc, "Goalie coach"
    specs = DRILL_SPECIALTY.get(ptype, ("technical_coaching",))
    best, best_score = None, -1.0
    for ac in assistants_of(team):
        score = sum(_num(ac, a) for a in specs[:2]) / 2.0
        if score > best_score:
            best, best_score = ac, score
    if best is not None and best_score >= 55:
        return best, "Assistant"
    hc = head_coach_of(team)
    if hc is not None:
        return hc, "Head coach"
    # Nobody behind the bench at all: fall back to whoever exists.
    for stf in _staff_list(team):
        return stf, "Staff"
    return None, ""


def specialty_rating(coach: Any, practice_type: str) -> float:
    """0-100: how well this coach teaches this drill, from the attributes
    that actually teach it (first specialty listed weighs most)."""
    specs = DRILL_SPECIALTY.get(str(practice_type or "").lower(),
                                ("technical_coaching",))
    weights = (0.55, 0.30, 0.15)
    total, wsum = 0.0, 0.0
    for i, attr in enumerate(specs):
        w = weights[i] if i < len(weights) else 0.1
        total += _num(coach, attr) * w
        wsum += w
    return _clamp(total / wsum if wsum else 50.0, 1.0, 100.0)


def coach_drill_rating(coach: Any, player: Any,
                       practice_type: str) -> Tuple[float, List[str]]:
    """0-100: how good this coach is at developing THIS player in THIS
    drill -- and why, as human-readable drivers.

    Specialty for the drill is the core; position-group coaching and raw
    teaching ability (player_development) blend in; working_with_youngsters
    lifts kids; low adaptability punishes off-specialty drills (a coach
    who only knows one way teaches it badly when it's the wrong way).
    """
    drivers: List[str] = []
    if coach is None:
        return 50.0, ["No coach on staff"]
    ptype = str(practice_type or "").lower()
    spec = specialty_rating(coach, ptype)
    group = _position_group(player)
    group_attr = {"offense": "coaching_forwards",
                  "defense": "coaching_defensemen",
                  "goalie": "coaching_goalies"}[group]
    group_rate = _num(coach, group_attr)
    teaching = _num(coach, "player_development")
    rating = spec * 0.55 + group_rate * 0.25 + teaching * 0.20
    drivers.append(f"{_staff_name(coach)} teaches {ptype} "
                   f"at {spec:.0f}")
    # The youth touch.
    age = _num(player, "age", 26)
    if age <= 23:
        wwy = _num(coach, "working_with_youngsters")
        lift = (wwy - 50) / 50 * 8.0  # -8..+8
        rating += lift
        if abs(lift) >= 2:
            drivers.append(
                f"{'good' if lift > 0 else 'poor'} with youngsters "
                f"({wwy:.0f}) {'helps' if lift > 0 else 'costs'} "
                f"a {int(age)}-year-old")
    # Adaptability: a one-trick coach is exposed outside his specialty.
    adapt = _num(coach, "adaptability")
    if spec < 60 and adapt < 50:
        penalty = (50 - adapt) / 50 * 10.0  # up to -10
        rating -= penalty
        drivers.append(f"rigid system coach ({adapt:.0f} adaptability) "
                       f"outside his specialty")
    elif spec >= 70 and adapt >= 65:
        rating += 3.0
        drivers.append("adapts the drill to the player")
    return _clamp(rating, 1.0, 100.0), drivers


# ---------------------------------------------------------------------------
# Archetype affinity: which drills stick for which player types
# ---------------------------------------------------------------------------
# Archetype -> practice_type -> multiplier. 1.0 is neutral; >1 the drill
# is in the player's wheelhouse, <1 it barely sticks. Deliberately
# asymmetric: a Sniper CAN learn defense, just slower than shooting.
ARCHETYPE_PRACTICE_AFFINITY: Dict[str, Dict[str, float]] = {
    "Sniper": {"shooting": 1.4, "skating": 1.2, "hockey_iq": 1.15,
               "passing": 1.0, "conditioning": 1.0, "teamwork": 1.0,
               "leadership": 1.0, "faceoffs": 0.95, "defense": 0.8,
               "checking": 0.7},
    "Playmaker": {"passing": 1.4, "hockey_iq": 1.3, "skating": 1.15,
                  "shooting": 1.0, "faceoffs": 1.0, "conditioning": 1.0,
                  "teamwork": 1.1, "leadership": 1.0, "defense": 0.85,
                  "checking": 0.7},
    "Power Forward": {"checking": 1.3, "shooting": 1.2,
                      "conditioning": 1.2, "skating": 1.1, "passing": 1.0,
                      "defense": 1.0, "hockey_iq": 0.9, "teamwork": 1.0,
                      "leadership": 1.05, "faceoffs": 1.0},
    "Two-Way Forward": {"defense": 1.35, "hockey_iq": 1.2,
                        "checking": 1.15, "faceoffs": 1.1,
                        "skating": 1.05, "passing": 1.0, "shooting": 1.0,
                        "conditioning": 1.05, "teamwork": 1.1,
                        "leadership": 1.05},
    "Grinder": {"checking": 1.4, "conditioning": 1.3, "defense": 1.15,
                "skating": 1.05, "faceoffs": 1.0, "teamwork": 1.1,
                "hockey_iq": 0.9, "passing": 0.8, "shooting": 0.75,
                "leadership": 1.0},
    "Enforcer": {"checking": 1.4, "conditioning": 1.25, "defense": 1.0,
                 "skating": 1.0, "teamwork": 1.0, "leadership": 1.0,
                 "hockey_iq": 0.8, "passing": 0.65, "shooting": 0.65,
                 "faceoffs": 0.8},
    "Offensive Defenseman": {"passing": 1.35, "shooting": 1.25,
                             "skating": 1.2, "hockey_iq": 1.15,
                             "conditioning": 1.0, "defense": 1.0,
                             "teamwork": 1.0, "leadership": 1.0,
                             "faceoffs": 0.9, "checking": 0.85},
    "Defensive Defenseman": {"defense": 1.4, "checking": 1.3,
                             "hockey_iq": 1.15, "skating": 1.05,
                             "conditioning": 1.05, "passing": 0.95,
                             "teamwork": 1.05, "leadership": 1.05,
                             "shooting": 0.8, "faceoffs": 0.9},
    "Two-Way Defenseman": {"defense": 1.25, "hockey_iq": 1.2,
                           "passing": 1.15, "checking": 1.1,
                           "skating": 1.1, "shooting": 1.0,
                           "conditioning": 1.05, "teamwork": 1.05,
                           "leadership": 1.0, "faceoffs": 0.9},
    "Physical Defenseman": {"checking": 1.4, "defense": 1.2,
                            "conditioning": 1.2, "skating": 1.0,
                            "hockey_iq": 0.95, "teamwork": 1.0,
                            "leadership": 1.0, "passing": 0.8,
                            "shooting": 0.85, "faceoffs": 0.85},
    "Puck-Moving Defenseman": {"passing": 1.35, "skating": 1.3,
                               "hockey_iq": 1.2, "defense": 1.0,
                               "shooting": 1.0, "conditioning": 1.0,
                               "teamwork": 1.05, "leadership": 1.0,
                               "checking": 0.85, "faceoffs": 0.9},
    # Goalies train positioning, reads and athleticism; shooting drills
    # are someone else's job.
    "Butterfly Goalie": {"hockey_iq": 1.25, "conditioning": 1.2,
                         "skating": 1.15, "defense": 1.1, "teamwork": 1.0,
                         "leadership": 1.0, "passing": 0.7,
                         "faceoffs": 0.6, "checking": 0.55,
                         "shooting": 0.55},
    "Hybrid Goalie": {"hockey_iq": 1.25, "conditioning": 1.2,
                      "skating": 1.15, "defense": 1.1, "teamwork": 1.0,
                      "leadership": 1.0, "passing": 0.7, "faceoffs": 0.6,
                      "checking": 0.55, "shooting": 0.55},
    "Standup Goalie": {"hockey_iq": 1.25, "conditioning": 1.2,
                       "skating": 1.15, "defense": 1.1, "teamwork": 1.0,
                       "leadership": 1.0, "passing": 0.7, "faceoffs": 0.6,
                       "checking": 0.55, "shooting": 0.55},
}


def archetype_affinity(player: Any,
                       practice_type: str) -> Tuple[float, str]:
    """(multiplier 0.5..1.4, one-line why). Unknown archetypes are
    neutral; goalies get the goalie-unfriendly discount on top."""
    ptype = str(practice_type or "").lower()
    try:
        from player_archetypes import get_archetype as _get_arch
        arch = str(_get_arch(player) or "")
    except Exception:
        arch = str(getattr(player, "archetype", "") or "")
    mult = ARCHETYPE_PRACTICE_AFFINITY.get(arch, {}).get(ptype, 1.0)
    if _position_group(player) == "goalie":
        mult *= _GOALIE_MULT.get(ptype, 1.0)
    mult = _clamp(mult, 0.5, 1.4)
    if not arch:
        return mult, ""
    if mult >= 1.2:
        why = f"{arch}: {ptype} is his wheelhouse"
    elif mult >= 1.05:
        why = f"{arch}: takes to {ptype}"
    elif mult <= 0.75:
        why = f"{arch}: {ptype} barely sticks"
    elif mult <= 0.9:
        why = f"{arch}: {ptype} is a slow burn"
    else:
        why = ""
    return round(mult, 3), why


def archetype_loves(player: Any) -> str:
    """The drill this archetype responds to best (for UI hints)."""
    try:
        from player_archetypes import get_archetype as _get_arch
        arch = str(_get_arch(player) or "")
    except Exception:
        arch = ""
    table = ARCHETYPE_PRACTICE_AFFINITY.get(arch)
    if not table:
        return ""
    return max(table, key=table.get)


# ---------------------------------------------------------------------------
# Attitude: coachability, work ethic, morale, determination
# ---------------------------------------------------------------------------
def practice_attitude(player: Any) -> Tuple[float, str, List[str]]:
    """(multiplier 0.6..1.3, label, drivers). A checked-out player goes
    through the motions; an all-in kid squeezes every rep."""
    coachability = _num(player, "coachability", 70)   # 50-90
    work_ethic = _num(player, "work_ethic", 70)       # 50-90
    morale = _num(player, "morale", 70)               # 1-100
    determination = _num(player, "determination", 70)  # 50-90
    # Normalize each to 0..1 around its mid.
    cn = _clamp((coachability - 50) / 40, 0, 1)
    wn = _clamp((work_ethic - 50) / 40, 0, 1)
    mn = _clamp((morale - 1) / 99, 0, 1)
    dn = _clamp((determination - 50) / 40, 0, 1)
    score = 0.35 * cn + 0.30 * wn + 0.20 * mn + 0.15 * dn
    mult = _clamp(0.6 + score * 0.7, 0.6, 1.3)
    drivers = []
    if coachability < 58:
        drivers.append("low coachability: tunes the coach out")
    elif coachability > 80:
        drivers.append("sponge: soaks up coaching")
    if work_ethic < 58:
        drivers.append("coasts through reps")
    elif work_ethic > 80:
        drivers.append("first on, last off")
    if morale < 40:
        drivers.append("low morale: going through the motions")
    elif morale > 80:
        drivers.append("flying: brings energy to practice")
    if determination > 82 and mult > 1.0:
        drivers.append("determination carries him through hard skates")
    if score >= 0.75:
        label = "All-in"
    elif score >= 0.55:
        label = "Engaged"
    elif score >= 0.35:
        label = "Going through the motions"
    else:
        label = "Checked out"
    return round(mult, 3), label, drivers


# ---------------------------------------------------------------------------
# Coach x player fit: synergy or friction (reuses the relationship model)
# ---------------------------------------------------------------------------
def practice_fit_factor(coach: Any,
                        player: Any) -> Tuple[float, str, float]:
    """(multiplier 0.8..1.15, label, morale_cost). Wraps
    reputation_system.coach_player_fit: a drill sergeant and a
    needs-freedom skill player grate; a player's coach lifts a fragile
    kid. Bad fits on hard skates cost a little morale."""
    if coach is None:
        return 1.0, "", 0.0
    try:
        import reputation_system as _rs
        fit = float(_rs.coach_player_fit(coach, player))
        try:
            label = str(_rs.player_coach_response(
                player, coach).get("label", ""))
        except Exception:
            label = ""
    except Exception:
        return 1.0, "", 0.0
    mult = _clamp(1.0 + fit * 0.18, 0.8, 1.15)
    morale_cost = 0.0
    if fit <= -0.3:
        tag = "Friction"
        morale_cost = 2.0  # applied by the engine on intense+ sessions
    elif fit >= 0.3:
        tag = "Synergy"
    else:
        tag = "Neutral"
    if label and label not in ("Neutral",):
        tag = f"{tag} ({label.lower()})"
    return round(mult, 3), tag, morale_cost


# ---------------------------------------------------------------------------
# System fit: the club's identity shapes what practice is FOR
# ---------------------------------------------------------------------------
_SYSTEM_DRILLS = {
    "Offensive": {"shooting", "passing", "skating"},
    "Defensive": {"defense", "checking", "hockey_iq"},
    "Balanced": set(),
    "Very Offensive": {"shooting", "passing"},
    "Very Defensive": {"defense", "checking"},
    "Aggressive": {"checking", "conditioning"},
}


def system_practice_fit(team: Any,
                        practice_type: str) -> Tuple[float, str, bool]:
    """(multiplier, label, trains_system). An offensive club drilling
    shooting is training its identity (bonus + tactical familiarity);
    a trap club drilling shooting is just exercise."""
    ptype = str(practice_type or "").lower()
    if team is None:
        return 1.0, "", False
    even = str(getattr(team, "tactic_even_strength", "Balanced") or
               "Balanced")
    pp = str(getattr(team, "tactic_power_play", "") or "")
    pk = str(getattr(team, "tactic_penalty_kill", "") or "")
    drills = set(_SYSTEM_DRILLS.get(even, set()))
    drills |= _SYSTEM_DRILLS.get(pp, set())
    drills |= _SYSTEM_DRILLS.get(pk, set())
    if ptype in drills:
        if even == "Balanced" and not drills:
            return 1.03, "Balanced system: steady all-round work", True
        return 1.12, f"Fits the {even.lower()} system", True
    if even == "Balanced":
        return 1.03, "Balanced system: steady all-round work", False
    return 0.97, f"Outside the {even.lower()} identity", False


# ---------------------------------------------------------------------------
# The full breakdown: one entry point for the practice engine
# ---------------------------------------------------------------------------
def practice_breakdown(team: Any, player: Any,
                       practice_type: str) -> Dict[str, Any]:
    """Everything the engine needs, with human-readable reasons.

    Keys: coach, coach_role, coach_rating, coach_drivers, affinity,
    affinity_why, attitude, attitude_label, attitude_drivers, fit,
    fit_label, morale_cost, system, system_label, trains_system,
    fatigue_mult, total_mult, loves.
    """
    ptype = str(practice_type or "").lower()
    coach, role = session_coach(team, player, ptype) if team is not None \
        else (None, "")
    rating, coach_drivers = coach_drill_rating(coach, player, ptype)
    # 0-100 rating -> multiplier. 65 (a solid average coach) is 1.0, so a
    # league-average setup reproduces the old flat-trainer tuning; the
    # spread (0.76..1.18) is where staff quality actually matters now.
    coach_mult = _clamp(0.55 + (rating / 100.0) * 0.7, 0.55, 1.25)
    affinity, affinity_why = archetype_affinity(player, ptype)
    attitude, attitude_label, attitude_drivers = practice_attitude(player)
    fit, fit_label, morale_cost = practice_fit_factor(coach, player)
    system, system_label, trains_system = system_practice_fit(team, ptype)
    # A motivating coach manages load: slightly cheaper hard skates.
    motivating = _num(coach, "motivating", 50) if coach else 50.0
    fatigue_mult = _clamp(1.10 - motivating / 500.0, 0.90, 1.10)
    total = coach_mult * affinity * attitude * fit * system
    # Keep the combined swing inside a sane band: coaching is the
    # difference between good and great development, never the whole
    # story (talent and age still dominate). The ceiling matches the old
    # flat-trainer ceiling (1.3 trainer x 1.3 work ethic).
    total = _clamp(total, 0.45, 1.75)
    return {
        "coach": coach,
        "coach_name": _staff_name(coach) if coach else "",
        "coach_role": role,
        "coach_rating": round(rating, 1),
        "coach_mult": round(coach_mult, 3),
        "coach_drivers": coach_drivers,
        "affinity": affinity,
        "affinity_why": affinity_why,
        "attitude": attitude,
        "attitude_label": attitude_label,
        "attitude_drivers": attitude_drivers,
        "fit": fit,
        "fit_label": fit_label,
        "morale_cost": morale_cost,
        "system": system,
        "system_label": system_label,
        "trains_system": trains_system,
        "fatigue_mult": round(fatigue_mult, 3),
        "total_mult": round(total, 3),
        "loves": archetype_loves(player),
    }


def describe_session(breakdown: Dict[str, Any]) -> List[str]:
    """UI-ready 'why this works' lines, most important first."""
    lines: List[str] = []
    try:
        cn = breakdown.get("coach_name", "")
        if cn:
            lines.append(
                f"Run by {cn} ({breakdown.get('coach_role', 'coach')}) "
                f"-- teaches this drill at {breakdown.get('coach_rating', 50):.0f}")
        for d in (breakdown.get("coach_drivers") or [])[:2]:
            lines.append(d.capitalize())
        aw = breakdown.get("affinity_why", "")
        if aw:
            lines.append(aw.capitalize())
        al = breakdown.get("attitude_label", "")
        if al:
            lines.append(f"Attitude: {al}")
        for d in (breakdown.get("attitude_drivers") or [])[:2]:
            lines.append(d.capitalize())
        fl = breakdown.get("fit_label", "")
        if fl and not fl.startswith("Neutral"):
            lines.append(f"Coach fit: {fl}")
        sl = breakdown.get("system_label", "")
        if sl:
            lines.append(sl)
    except Exception:
        pass
    return lines
