"""Controversial plays, instigators, and the leadership response.

Hotheads stir the pot, grinders run people, greasy players crash the
crease -- and sometimes the call on the ice is wrong. This module models
the plays the league office hates: uncalled goalie interference, missed
too-many-men, borderline hits, disallowed goals, and the coach's
challenge (with its real delay-of-game price for getting it wrong).

What happens NEXT is the hockey part. A bad call that implies malicious
intent moves momentum and intensity -- but the direction is earned, not
scripted. Good leadership (a real captain, a strong room, a coach the
players believe in) locks the boys in and turns outrage into fuel. A
room with nobody to grab the wheel deflates, and the comeback dies.

Real-world grounding, 2021-22 .. 2025-26:
- Coach's challenges run ~200/season (~0.15/game). In 2025-26, 163
  challenges by the Olympic break: 67 for goalie interference, 24
  overturned (36%). Historically GI challenges succeed 45-55% in the
  regular season but only 22-30% in the playoffs; offside challenges
  have overturned 756 goals since 2015-16 (~69/season).
- A failed challenge is a 2-minute delay-of-game minor. That is the
  actual rule, not our invention (e.g. Vegas' failed GI challenge in
  SCF G2 2026 -> Carolina scored on the ensuing power play).
- Headline-grade controversies over the span: Kadri's Cup-winning OT
  goal on an uncalled too-many-men (SCF G4 2022); the Islanders' go-ahead
  goal waved off with 9.6 seconds left (Jan 2025, "embarrassing"); the
  Barbashev no-goal in SCF G2 2026; the 10-minute MTL-BUF review in the
  2025 playoffs after which the Habs scored minutes later -- controversy
  as pure momentum fuel.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Rates (per game / per goal / per period)
# ---------------------------------------------------------------------------

CHALLENGE_RATE_PER_GOAL = 0.03   # ~3% of goals draw a look (~200 challenges / ~7000 goals)
CREASE_MULT = 2.2                # crease/slot goals invite crease-crash scrutiny
PLAYOFF_CHALLENGE_MULT = 1.3     # more is at stake; coaches reach for the card

GI_OVERTURN_REG = 0.42           # 36% in 25-26; 45-55% historically
GI_OVERTURN_PO = 0.27            # playoffs: 22-30%
OFFSIDE_OVERTURN = 0.60          # offside is usually clear-cut on video
KICK_OVERTURN = 0.35             # "distinct kicking motion" is a judgment call

UNCALLED_PER_PERIOD = 0.012      # ~0.04/game of notable missed calls

# ---------------------------------------------------------------------------
# 1. Who stirs the pot
# ---------------------------------------------------------------------------

# Archetype agitation weight. Grinders and enforcers live in the grey areas;
# skill players rarely go looking for it.
ARCHETYPE_AGITATION = {
    "Enforcer": 0.30,
    "Grinder": 0.26,
    "Power Forward": 0.16,
    "Physical Defenseman": 0.12,
    "Two-Way Forward": 0.06,
    "Shutdown Defenseman": 0.06,
    "Defensive Defenseman": 0.05,
}

_HOTHEAD_GRINDERS = ("Grinder", "Enforcer")


def instigation_tendency(player: Any) -> float:
    """0..1 likelihood this player stirs the pot, runs someone, or instigates.

    Locked identity first (base_controversy never re-deals), archetype
    second, greasiness third: high aggressiveness + low discipline is the
    classic rat profile. The hothead grinder -- high controversy AND a
    grinder/enforcer archetype -- is the nightmare combo.
    """
    try:
        from reputation_system import controversy_baseline
        base = controversy_baseline(player) / 100.0
    except Exception:
        base = getattr(player, "controversy", 30) / 100.0
    arch = getattr(player, "archetype", "") or ""
    arch_w = ARCHETYPE_AGITATION.get(arch, 0.04)
    # A saint doesn't become a rat just because he forechecks hard.
    arch_w *= (0.35 + 0.65 * base)
    aggr = getattr(player, "aggressiveness", 50) / 100.0
    disc = getattr(player, "discipline", 50) / 100.0
    grease = max(0.0, aggr - 0.55) * max(0.0, 0.75 - disc) * 1.6
    t = 0.50 * base + arch_w + grease
    if base >= 0.55 and arch in _HOTHEAD_GRINDERS:
        t += 0.12  # hothead grinder: the league's least favorite shift
    return max(0.0, min(0.95, t))


def pick_instigator(skaters: List[Any]) -> Optional[Any]:
    """Weighted pick of the skater most likely to start something."""
    cands = [p for p in skaters if p is not None]
    if not cands:
        return None
    weights = [0.02 + instigation_tendency(p) for p in cands]
    if sum(weights) <= 0:
        return None
    return random.choices(cands, weights=weights, k=1)[0]


def _on_ice_skaters(sim: Any, team: Any) -> List[Any]:
    try:
        skaters = sim._get_on_ice(team)
    except Exception:
        skaters = []
    try:
        from game_classes import PlayerPosition
        return [p for p in skaters
                if p is not None and getattr(p, "primary_position", None) != PlayerPosition.GOALIE]
    except Exception:
        return [p for p in skaters if p is not None]


def _team_name(team: Any) -> str:
    return getattr(team, "team_name", getattr(team, "name", "Team")) or "Team"


def _heat(sim: Any, amount: float) -> None:
    """Nudge live intensity. Mirrors the fight/brawl heat bookkeeping."""
    try:
        sim._live_heat = min(40.0, float(getattr(sim, "_live_heat", 0.0)) + amount)
    except Exception:
        pass


def _log(sim: Any, text: str, kind: str = "CONTROVERSY", **pbp) -> None:
    try:
        sim._log_event(text, kind)
    except Exception:
        pass
    try:
        sim._emit_pbp("controversy", text=text, **pbp)
    except Exception:
        pass


def _rivalry_incident(sim: Any, team_a: Any, team_b: Any, kind: str, detail: str) -> None:
    try:
        from reputation_system import record_game_incident
        rivalries = getattr(sim, "rivalries", None)
        if rivalries is not None:
            record_game_incident(rivalries, team_a, team_b, kind, detail)
    except Exception:
        pass


def _dynamics(team: Any, event_type: str, text: str,
              morale_delta: int = 0, tone: str = "neutral") -> None:
    try:
        from reputation_system import record_team_event
        record_team_event(team, event_type, text,
                          morale_delta=morale_delta, tone=tone)
    except Exception:
        pass


def _head_coach(sim: Any, team: Any) -> Optional[Any]:
    try:
        return sim._find_head_coach(team)
    except Exception:
        return None


def _is_brash(coach: Any) -> bool:
    """Brash coaches challenge more and take controversy personally."""
    try:
        from reputation_system import controversy_baseline
        return controversy_baseline(coach) >= 60
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 2. Momentum -- the controversy channel is NOT story-budget capped.
# ---------------------------------------------------------------------------

def controversy_momentum_shift(sim: Any, team: Any, steps: int) -> int:
    """Move the momentum needle up to `steps` toward `team`.

    Deliberately bypasses the impact engine's per-game story budget: a
    blown call in a tied third period SHOULD be allowed to swing a game
    harder than a routine hit. The gate is context -- this is only ever
    called from a real controversy, never from routine play.
    """
    try:
        from simulation import GameMomentum
        order = list(GameMomentum)
        cur = order.index(sim.momentum)
        home_side = (team is getattr(sim, "home_team", None))
        target = cur - steps if home_side else cur + steps
        target = max(0, min(len(order) - 1, target))
        moved = abs(target - cur)
        if moved:
            sim.momentum = order[target]
            try:
                sim.momentum_history.append(
                    (getattr(sim, "period", 1), sim.momentum))
            except Exception:
                pass
        return moved
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# 3. The leadership response -- "lock in the boys" or deflate
# ---------------------------------------------------------------------------

def leadership_pool(team: Any, coach: Any) -> float:
    """0..1: how much leadership this room can draw on right now.

    Half the room's leaders (captain + hierarchy), half the coach
    (leadership + motivating + the influence he's banked).
    """
    room = 0.5
    try:
        from reputation_system import team_hierarchy
        roster = [p for p in getattr(team, "roster", []) if p is not None]
        tiers = team_hierarchy(roster)
        leaders = tiers.get("Team Leaders", []) or []
        if not leaders:
            # No anointed leaders: the three most leadery skaters speak up.
            leaders = sorted(roster,
                             key=lambda p: getattr(p, "leadership", 0),
                             reverse=True)[:3]
        if leaders:
            room = sum(getattr(p, "leadership", 50) for p in leaders) / (
                100.0 * len(leaders))
    except Exception:
        pass
    bench = 0.5
    try:
        if coach is not None:
            lead = getattr(coach, "leadership", 10) / 20.0
            mot = getattr(coach, "motivating", 10) / 20.0
            inf = getattr(coach, "influence", 50) / 100.0
            bench = 0.5 * lead + 0.3 * mot + 0.2 * inf
    except Exception:
        pass
    return max(0.0, min(1.0, 0.5 * room + 0.5 * bench))


def leadership_response(sim: Any, team: Any, coach: Any, adversity: float,
                        context: str) -> Dict[str, Any]:
    """The room answers a controversy. Returns the outcome dict.

    adversity 0..1 compounds: down a goal, failed challenge, now
    shorthanded, playoff stakes, rivalry hatred. High leadership locks
    the boys in (momentum TO the wronged team, uncapped); a leaderless
    room deflates (momentum to the other bench, morale dips).
    """
    pool = leadership_pool(team, coach)
    success_p = max(0.05, min(0.95, 0.15 + pool * 0.9 - adversity * 0.5))
    rallied = random.random() < success_p
    opp = getattr(sim, "away_team", None) if team is getattr(
        sim, "home_team", None) else getattr(sim, "home_team", None)
    tname = _team_name(team)

    if rallied:
        steps = 1 + round(adversity * 3)  # no cap when the context earns it
        moved = controversy_momentum_shift(sim, team, steps)
        _heat(sim, 4.0)
        narratives = [
            f"{tname} are furious -- and focused. The bench has locked in.",
            f"Us-against-the-world: {tname} come out flying after the call.",
            f"The {tname} bench is up. That call just made this personal.",
        ]
        text = random.choice(narratives)
        _log(sim, f"{text} ({context})",
             team=tname, outcome="rally")
        _dynamics(team, "controversy_rally",
                  f"Room locked in after {context} -- outrage turned to fuel.",
                  morale_delta=4, tone="up")
        return {"outcome": "rally", "steps": moved, "success_p": success_p,
                "text": text}
    # Deflate: nobody grabbed the wheel; the comeback dies a little.
    steps = 1 + round(adversity * 2)
    moved = controversy_momentum_shift(sim, opp, steps) if opp is not None else 0
    _heat(sim, 2.0)
    narratives = [
        f"{tname} are still arguing the call -- heads are gone.",
        f"The air is out of the {tname} bench. That one hurt.",
        f"{tname} look deflated. No answer coming from the leadership group.",
    ]
    text = random.choice(narratives)
    _log(sim, f"{text} ({context})", team=tname, outcome="deflate")
    _dynamics(team, "controversy_deflate",
              f"Room deflated after {context} -- nobody settled the bench.",
              morale_delta=-5, tone="down")
    return {"outcome": "deflate", "steps": moved, "success_p": success_p,
            "text": text}


# ---------------------------------------------------------------------------
# 4. The coach's challenge (goal review)
# ---------------------------------------------------------------------------

_CHALLENGE_KINDS = (
    ("goaltender_interference", 0.55),
    ("offside", 0.25),
    ("distinct_kicking_motion", 0.20),
)


def coach_challenge_decision(coach: Any, ctx: Dict[str, Any]) -> Tuple[bool, float]:
    """Should the coach throw the challenge flag? Returns (challenge, overturn_p).

    Brash coaches reach for it on emotion; desperate/late/close games pull
    everyone toward it; a coach already burned once tonight gets gun-shy.
    The price of being wrong is a delay-of-game minor -- the real rule.
    """
    base = 0.55
    if coach is not None and _is_brash(coach):
        base += 0.20
    if ctx.get("trailing"):
        base += 0.15
    if ctx.get("late_close"):
        base += 0.20
    if ctx.get("already_failed"):
        base -= 0.30
    if ctx.get("is_playoff"):
        base += 0.10  # everything matters more; GI success is lower though
    will = random.random() < max(0.05, min(0.95, base))
    kind = ctx.get("kind", "goaltender_interference")
    po = bool(ctx.get("is_playoff"))
    overturn = {"goaltender_interference": GI_OVERTURN_PO if po else GI_OVERTURN_REG,
                "offside": OFFSIDE_OVERTURN,
                "distinct_kicking_motion": KICK_OVERTURN}.get(kind, 0.4)
    return will, overturn


def _crease_area(location: Any) -> bool:
    try:
        name = getattr(location, "name", "") or str(location)
    except Exception:
        name = ""
    return name in ("CREASE", "LOW_SLOT", "HIGH_SLOT")


def review_goal_scoring_play(sim: Any, attacking_team: Any, defending_team: Any,
                             shooter: Any, location: Any,
                             shot_type: Any = None) -> str:
    """Pre-record review of a goal. Returns "goal" or "disallowed".

    Called BEFORE the goal hits the scoresheet, so a disallowed goal never
    needs stat surgery. Handles the challenge decision, the overturn roll,
    the failed-challenge minor, and the leadership response to the fallout.
    """
    is_po = bool(getattr(sim, "is_playoff", False))
    p = CHALLENGE_RATE_PER_GOAL
    if _crease_area(location):
        p *= CREASE_MULT
    if is_po:
        p *= PLAYOFF_CHALLENGE_MULT
    if random.random() >= p:
        return "goal"

    kinds, weights = zip(*_CHALLENGE_KINDS)
    kind = random.choices(kinds, weights=weights, k=1)[0]
    kind_label = kind.replace("_", " ")

    coach = _head_coach(sim, defending_team)
    dname = _team_name(defending_team)
    aname = _team_name(attacking_team)
    sname = getattr(shooter, "full_name", "The shooter")

    try:
        sd = sim.home_score - sim.away_score
        if defending_team is not sim.home_team:
            sd = -sd
        # sd is the score BEFORE this goal lands; the goal puts them down one more.
        trailing_after = (sd - 1) < 0
        period = getattr(sim, "period", 1)
        clock = getattr(sim, "clock", 1200)
        late_close = period >= 3 and clock < 300 and abs(sd - 1) <= 1
    except Exception:
        trailing_after, late_close = False, False

    ctx = {"kind": kind, "trailing": trailing_after, "late_close": late_close,
           "is_playoff": is_po,
           "already_failed": bool(getattr(sim, "_challenge_failed", False))}
    will, overturn_p = coach_challenge_decision(coach, ctx)

    if not will:
        # Nobody threw the flag. The goal stands; the room grumbles.
        if random.random() < 0.35:
            _log(sim, f"{sname} scores for {aname} -- {dname} wanted "
                      f"{kind_label}, but no challenge coming.",
                 team=dname)
        return "goal"

    _log(sim, f"{sname} scores... but {dname} are challenging for "
              f"{kind_label}! The play is under review.",
         team=dname, kind_detail=kind)

    if random.random() < overturn_p:
        # OVERTURNED -- no goal. The crease crash is real; the feud remembers.
        _log(sim, f"After review: NO GOAL. {kind_label} -- "
                  f"the {dname} bench erupts.",
             team=dname, kind_detail=kind)
        _heat(sim, 5.0)
        _dynamics(defending_team, "challenge_won",
                  f"Challenge won ({kind_label}) -- goal wiped off the board.",
                  morale_delta=5, tone="up")
        _dynamics(attacking_team, "challenge_lost",
                  f"Goal disallowed ({kind_label}) -- the room is stunned.",
                  morale_delta=-4, tone="down")
        if kind == "goaltender_interference":
            _rivalry_incident(sim, attacking_team, defending_team,
                              "controversial_hit",
                              f"crease crash on {sname}'s disallowed goal")
        controversy_momentum_shift(sim, defending_team, 1)
        _headline_spec(sim, "disallowed_goal",
                       scoring_team=aname, defending_team=dname,
                       shooter=sname, call_kind=kind_label,
                       period=getattr(sim, "period", 1))
        return "disallowed"

    # The call STANDS -- and the failed challenge costs a minor. The rule.
    _log(sim, f"The call on the ice stands -- good goal. {dname} lose the "
              f"challenge: delay-of-game minor.",
         team=dname, kind_detail=kind)
    try:
        sim._challenge_failed = True
    except Exception:
        pass
    _serve_delay_of_game(sim, defending_team,
                         detail=f"failed {kind_label} challenge")
    _heat(sim, 6.0)

    # Chris's scenario: down a goal on a controversy, challenge missed,
    # now shorthanded. Leadership decides whether this ignites or deflates.
    adversity = 0.30 + 0.25  # failed challenge + shorthanded
    if trailing_after:
        adversity += 0.25
    if is_po:
        adversity += 0.15
    try:
        from reputation_system import get_rivalry_heat
        rivalries = getattr(sim, "rivalries", None)
        if rivalries is not None and get_rivalry_heat(
                rivalries, defending_team, attacking_team) >= 50:
            adversity += 0.10
    except Exception:
        pass
    adversity = min(1.0, adversity)
    leadership_response(sim, defending_team, coach, adversity,
                        f"failed {kind_label} challenge, now shorthanded")
    _headline_spec(sim, "failed_challenge",
                   scoring_team=aname, defending_team=dname,
                   shooter=sname, call_kind=kind_label,
                   period=getattr(sim, "period", 1))
    return "goal"


def _serve_delay_of_game(sim: Any, team: Any, detail: str = "") -> None:
    """Book the real price of a failed challenge: 2 minutes, served by a skater."""
    try:
        skaters = _on_ice_skaters(sim, team)
        if not skaters:
            return
        server = random.choice(skaters)
        sim._resolve_penalty(server, team,
                             ("Delay of game", 2,
                              detail or "failed coach's challenge"))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 5. Uncalled incidents -- the plays that should have been whistled
# ---------------------------------------------------------------------------

def maybe_uncalled_incident(sim: Any) -> bool:
    """One gated roll per period: a missed call with malicious undertones."""
    pnum = getattr(sim, "period", 1)
    key = f"_cz_uncalled_p{pnum}"
    if getattr(sim, key, False):
        return False
    try:
        setattr(sim, key, True)
    except Exception:
        return False
    if random.random() >= UNCALLED_PER_PERIOD:
        return False

    home, away = getattr(sim, "home_team", None), getattr(sim, "away_team", None)
    if home is None or away is None:
        return False
    # The "attacking" side is whoever gets away with it this time.
    attacking_team = home if random.random() < 0.5 else away
    defending_team = away if attacking_team is home else home
    kind = random.choices(
        ("run_goalie", "missed_tmm", "borderline_hit"),
        weights=(0.40, 0.30, 0.30), k=1)[0]
    if kind == "run_goalie":
        return _uncalled_run_goalie(sim, attacking_team, defending_team)
    if kind == "missed_tmm":
        return _uncalled_tmm(sim, attacking_team, defending_team)
    return _uncalled_borderline_hit(sim, attacking_team, defending_team)


def _uncalled_run_goalie(sim: Any, attacking_team: Any,
                         defending_team: Any) -> bool:
    """A crease crash, no call. The goalie is shaken; the bench is livid."""
    crasher = pick_instigator(_on_ice_skaters(sim, attacking_team))
    cname = getattr(crasher, "full_name", "An attacker") if crasher else "An attacker"
    try:
        goalie = sim._selected_goalie(defending_team)
        gname = getattr(goalie, "full_name", "the goalie")
    except Exception:
        gname = "the goalie"
    aname, dname = _team_name(attacking_team), _team_name(defending_team)
    _log(sim, f"{cname} barrels into {gname} -- NO CALL! The {dname} bench "
              f"is screaming for goaltender interference.",
         team=dname, kind_detail="run_goalie")
    _heat(sim, 5.0)
    _rivalry_incident(sim, attacking_team, defending_team, "bad_call",
                      f"{cname} ran {gname}, no call")
    controversy_momentum_shift(sim, attacking_team, 1)
    coach = _head_coach(sim, defending_team)
    leadership_response(sim, defending_team, coach, 0.35,
                        "goalie run, no call")
    _dynamics(attacking_team, "got_away_with_it",
              f"{cname} crashed the crease with impunity -- the room smells blood.",
              morale_delta=3, tone="up")
    return True


def _uncalled_tmm(sim: Any, attacking_team: Any, defending_team: Any) -> bool:
    """Too many men, missed -- the Kadri special. Extended pressure follows."""
    aname, dname = _team_name(attacking_team), _team_name(defending_team)
    _log(sim, f"The {aname} get away with too many men -- the {dname} bench "
              f"is apoplectic as the pressure builds.",
         team=dname, kind_detail="missed_tmm")
    _heat(sim, 4.0)
    _rivalry_incident(sim, attacking_team, defending_team, "bad_call",
                      "uncalled too many men led to extended pressure")
    controversy_momentum_shift(sim, attacking_team, 2)
    coach = _head_coach(sim, defending_team)
    leadership_response(sim, defending_team, coach, 0.40,
                        "uncalled too many men")
    return True


def _uncalled_borderline_hit(sim: Any, hitting_team: Any,
                             victim_team: Any) -> bool:
    """A late/high hit on a notable player, uncalled. Feud fuel."""
    hitter = pick_instigator(_on_ice_skaters(sim, hitting_team))
    hname = getattr(hitter, "full_name", "A checker") if hitter else "A checker"
    victims = _on_ice_skaters(sim, victim_team)
    # Rats target stars; everyone else hits who's there.
    def _rep(p):
        try:
            from reputation_system import league_perception
            return league_perception(p)
        except Exception:
            return getattr(p, "overall_rating", 60)
    target = None
    if victims:
        if hitter is not None and instigation_tendency(hitter) > 0.45:
            weights = [0.3 + _rep(p) / 100.0 for p in victims]
            target = random.choices(victims, weights=weights, k=1)[0]
        else:
            target = random.choice(victims)
    tname = getattr(target, "full_name", "a skater") if target else "a skater"
    htn, vtn = _team_name(hitting_team), _team_name(victim_team)
    _log(sim, f"{hname} levels {tname} with a borderline hit -- NO CALL! "
              f"The {vtn} want blood.",
         team=vtn, kind_detail="borderline_hit")
    _heat(sim, 6.0)
    _rivalry_incident(sim, hitting_team, victim_team, "controversial_hit",
                      f"{hname} ran {tname}, uncalled")
    coach = _head_coach(sim, victim_team)
    leadership_response(sim, victim_team, coach, 0.45,
                        f"uncalled borderline hit on {tname}")
    # DoPS record (additive): stash the dealt hitter/victim identity in the
    # same d-dict shape the rolled path uses, so the post-game hook can run
    # this live hit through _dops_suspension_review. The log line and the
    # rivalry wound above are unchanged; nothing else reads this list and
    # it is consumed exactly once by narrative_incidents.
    try:
        _hcon = float(getattr(hitter, "controversy",
                              getattr(hitter, "base_controversy", 30)) or 30) \
            if hitter is not None else 30.0
    except Exception:
        _hcon = 30.0
    try:
        _hits = getattr(sim, "_live_borderline_hits", None)
        if not isinstance(_hits, list):
            _hits = []
            sim._live_borderline_hits = _hits
        _hits.append({
            "kind": "controversial_hit",
            "hitter": hname, "hitter_team": htn,
            "victim": tname, "victim_team": vtn,
            "hitter_controversy": max(0.0, min(100.0, _hcon)),
        })
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# 6. Pot-stirring -- instigators between whistles
# ---------------------------------------------------------------------------

def maybe_pot_stirring(sim: Any) -> bool:
    """After-whistle agitation. Hotheads yap; sometimes the target bites.

    The classic: the rat chirps a star, the star takes the retaliation
    minor. 65% only the target sits, 25% offsetting, 10% the instigator
    gets caught being too obvious.
    """
    pnum = getattr(sim, "period", 1)
    key = f"_cz_stir_p{pnum}"
    if getattr(sim, key, False):
        return False
    try:
        setattr(sim, key, True)
    except Exception:
        return False

    home, away = getattr(sim, "home_team", None), getattr(sim, "away_team", None)
    if home is None or away is None:
        return False
    for team, opp in ((home, away), (away, home)):
        inst = pick_instigator(_on_ice_skaters(sim, team))
        if inst is None:
            continue
        t = instigation_tendency(inst)
        mult = 1.0
        try:
            from reputation_system import get_rivalry_heat
            rivalries = getattr(sim, "rivalries", None)
            if rivalries is not None:
                mult += get_rivalry_heat(rivalries, team, opp) / 150.0
        except Exception:
            pass
        try:
            sd = sim.home_score - sim.away_score
            if team is not sim.home_team:
                sd = -sd
            if sd < 0:
                mult += 0.25  # trailing teams stir
        except Exception:
            pass
        if getattr(sim, "is_playoff", False):
            mult += 0.20
        if random.random() >= t * 0.55 * mult:
            continue
        _resolve_stirring(sim, inst, team, opp)
        return True
    return False


def _resolve_stirring(sim: Any, inst: Any, team: Any, opp: Any) -> None:
    iname = getattr(inst, "full_name", "The agitator")
    tname, oname = _team_name(team), _team_name(opp)
    targets = _on_ice_skaters(sim, opp)
    target = None
    if targets:
        def _rep(p):
            try:
                from reputation_system import league_perception
                return league_perception(p)
            except Exception:
                return getattr(p, "overall_rating", 60)
        weights = [0.3 + _rep(p) / 100.0 for p in targets]
        target = random.choices(targets, weights=weights, k=1)[0]
    if target is None:
        return
    tname2 = getattr(target, "full_name", "his man")
    verbs = ["is in the ear of", "is chirping", "gives a shot to after the whistle",
             "is all over"]
    _log(sim, f"{iname} {random.choice(verbs)} {tname2} -- the refs are watching.",
         team=oname, kind_detail="stirring")
    roll = random.random()
    detail = f"retaliation after {iname}'s agitation"
    if roll < 0.65:
        # The classic: only the retaliator sits.
        _log(sim, f"{tname2} takes the bait -- retaliation minor. "
                  f"{iname} skates away smiling.",
             team=oname, kind_detail="retaliation")
        try:
            sim._resolve_penalty(target, opp,
                                 (random.choice(["Roughing", "Unsportsmanlike conduct"]),
                                  2, detail))
        except Exception:
            pass
        controversy_momentum_shift(sim, team, 1)
    elif roll < 0.90:
        _log(sim, f"Offsetting minors -- {iname} and {tname2} both sit.",
             team=oname, kind_detail="offsetting")
        for p, tm in ((inst, team), (target, opp)):
            try:
                sim._resolve_penalty(p, tm, ("Roughing", 2, "offsetting after-whistle"))
            except Exception:
                pass
    else:
        _log(sim, f"The refs catch {iname} this time -- instigator minor.",
             team=tname, kind_detail="instigator")
        try:
            sim._resolve_penalty(inst, team, ("Unsportsmanlike conduct", 2,
                                              "instigating after the whistle"))
        except Exception:
            pass
        controversy_momentum_shift(sim, opp, 1)
    _heat(sim, 2.0)


# ---------------------------------------------------------------------------
# 7. Per-tick entry point (called from GameSim._simulate_period)
# ---------------------------------------------------------------------------

def period_controversy_tick(sim: Any) -> None:
    """Single entry wired into the sim loop. Internally gated so the
    per-period rolls happen at most once each; cheap to call every tick."""
    try:
        maybe_uncalled_incident(sim)
    except Exception:
        pass
    try:
        maybe_pot_stirring(sim)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 8. Headline specs -- only the biggest controversies make the news
# ---------------------------------------------------------------------------

def _headline_spec(sim: Any, event: str, **kw) -> None:
    """Queue a controversy headline spec, the way brawls do.

    Only genuinely rare, high-leverage moments: a disallowed goal or a
    failed challenge in the 3rd period/OT of a close game. The daily cap
    in headlines.py keeps the newsroom honest.
    """
    try:
        period = int(kw.get("period", getattr(sim, "period", 1)))
        if period < 3 and event != "disallowed_goal":
            return
        spec = {"kind": "controversial_call", "event": event}
        spec.update(kw)
        home = _team_name(getattr(sim, "home_team", None))
        away = _team_name(getattr(sim, "away_team", None))
        spec["involved"] = (home, away)
        spec["home_score"] = getattr(sim, "home_score", 0)
        spec["away_score"] = getattr(sim, "away_score", 0)
        pending = getattr(sim, "pending_headlines", None)
        if pending is not None:
            pending.append(spec)
    except Exception:
        pass
