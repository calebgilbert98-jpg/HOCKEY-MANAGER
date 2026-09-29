"""Physicality engine (W5): officiating accuracy, dirty-hit revival,
personality-scaled fighting, fight game effects, heat decay, statement goals.

Additive layer over the existing sim resolution. Nothing here replaces
existing probability logic: the engine draws its infractions/hits/fights
exactly as before; this module classifies the moment (who, how dirty,
how heated) and applies the story consequences on top.

Design notes (from the brief):
- Officiating crews are per-game and mostly accurate (0.93-0.995). Dirty
  plays (boarding/charging/elbowing) are usually penalized; on a whiffed
  call the infraction goes unwhistled and feeds the heat engine instead
  of the penalty box. The whiff is on a REAL drawn infraction -- the old
  invented-roll "borderline hit" in controversy_system was retired in
  favor of this.
- Dirty hit types are real again: enforcer hot-head vs small star at
  center ice with speed = charging; a hot-head finishing a man along the
  boards = boarding. Every attempt exposes a hit-context dict (see
  HIT CONTEXT CONTRACT below) that W4's injury code reads for
  circumstance-scaled severity.
- Fights scale off personality/volatility: rats fight more than
  choirboys (instigation_tendency, consumed -- not duplicated), enforcers
  answer the bell, and the Enforcer trait's fight_win_mult (declared but
  never consumed until now) decides who wins.
- A won fight lifts the winner's bench: short-term finishing spark
  (explicit xG channel, ~5 game minutes, bigger in heated/rivalry games)
  plus an intensity bump. Fights are STORED in the rivalry record so
  they feed long-term memory (grudge floors hold the feud longer).
- Live heat decays during long calm stretches instead of only
  accumulating.
- Statement goals: a goal by the victim's team shortly after a dirty
  play on a teammate is tagged -- heat, rivalry wound, headline, and a
  stored incident that the offseason decay/grudge floors carry forward.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# HIT CONTEXT CONTRACT (W4 reads this; W5 writes it)
# ---------------------------------------------------------------------------
# set_last_hit_context(sim, build_hit_context(...)) is called on every hit
# attempt (successful or not) before the result resolves. W4's injury code
# reads last_hit_context(sim) to scale severity by circumstance.
#
# Fields (all defensive -- any may be missing on legacy/fake players):
#   hitter, victim        : player objects (or None)
#   hitter_name, victim_name : str
#   hitter_team, victim_team : str (team names, "" when unknown)
#   hit_type              : the HitType enum member used for the attempt
#   dirty                 : bool -- charging/boarding
#   speed                 : hitter's speed attribute (float)
#   location              : "center ice" | "along the boards" | "open ice"
#   impact                : 0 tired / 1 normal / 2 big (impact_system tiers)
#   period                : int
#   elapsed               : float -- game seconds elapsed
# ---------------------------------------------------------------------------

DIRTY_HIT_TYPE_NAMES = {"charging", "boarding"}


def _elapsed(sim: Any) -> float:
    try:
        period = max(1, int(getattr(sim, "period", 1)))
        clock = float(getattr(sim, "clock", 1200.0))
        return (period - 1) * 1200.0 + max(0.0, 1200.0 - clock)
    except Exception:
        return 0.0


def _pos_of(sim: Any, player: Any) -> Optional[Tuple[float, float]]:
    try:
        fn = getattr(sim, "_ppos_get", None)
        if fn is None:
            return None
        xy = fn(player)
        return (float(xy[0]), float(xy[1]))
    except Exception:
        return None


def _rink_location(sim: Any, player: Any) -> str:
    """Where the contact happened, in broadcast language. Rink is 200x85."""
    xy = _pos_of(sim, player)
    if xy is None:
        return "open ice"
    x, y = xy
    if y <= 12.0 or y >= 73.0:
        return "along the boards"
    if 80.0 <= x <= 120.0:
        return "center ice"
    return "open ice"


def _attr(p: Any, name: str, default: float = 50.0) -> float:
    try:
        v = getattr(p, name, default)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _archetype(p: Any) -> str:
    try:
        from player_archetypes import get_archetype
        return str(get_archetype(p) or "")
    except Exception:
        return str(getattr(p, "archetype", "") or "")


def build_hit_context(hitter: Any, victim: Any, hit_type: Any,
                      impact: int = 1, sim: Any = None) -> Dict[str, Any]:
    """Build the hit-context dict for one attempt. Never raises."""
    try:
        ht_name = ""
        try:
            ht_name = str(getattr(hit_type, "value", hit_type) or "")
        except Exception:
            ht_name = ""
        dirty = ht_name.lower() in DIRTY_HIT_TYPE_NAMES
        hteam, vteam = "", ""
        try:
            _gt = getattr(sim, "_get_player_team", None)
            if _gt is not None:
                hteam = getattr(_gt(hitter), "team_name", "") or ""
                vteam = getattr(_gt(victim), "team_name", "") or ""
        except Exception:
            pass
        return {
            "hitter": hitter,
            "victim": victim,
            "hitter_name": getattr(hitter, "full_name", "A checker"),
            "victim_name": getattr(victim, "full_name", "a skater"),
            "hitter_team": hteam,
            "victim_team": vteam,
            "hit_type": hit_type,
            "dirty": dirty,
            "speed": _attr(hitter, "speed", 50.0),
            "location": _rink_location(sim, victim),
            "impact": impact,
            "period": int(getattr(sim, "period", 1) or 1),
            "elapsed": _elapsed(sim),
        }
    except Exception:
        return {"hitter": hitter, "victim": victim, "hit_type": hit_type,
                "dirty": False, "speed": 50.0, "location": "open ice",
                "impact": impact, "period": 1, "elapsed": 0.0}


def set_last_hit_context(sim: Any, ctx: Dict[str, Any]) -> None:
    """Stash the latest attempt's context on the sim. W4 reads it."""
    try:
        sim._last_hit_context = ctx
    except Exception:
        pass


def last_hit_context(sim: Any) -> Optional[Dict[str, Any]]:
    """Read the latest hit context (W4's entry point). None if no attempt."""
    try:
        ctx = getattr(sim, "_last_hit_context", None)
        return ctx if isinstance(ctx, dict) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Dirty-hit revival: which hit type the engine throws
# ---------------------------------------------------------------------------

def choose_hit_type(hitter: Any, victim: Any, sim: Any = None) -> Any:
    """Pick the hit type for this attempt. Body checks by default; the
    canonical dirty cases fire where the context fits:

    - CHARGING: enforcer hot-head (or any high-aggression/low-discipline
      hitter with wheels) runs a star at center ice.
    - BOARDING: a hot-head finishes a man along the boards.

    Rates are small -- dirty majors are rare in the real league. Never
    raises; falls back to BODY_CHECK.
    """
    try:
        from simulation import HitType
    except Exception:
        return None
    try:
        arch = _archetype(hitter)
        aggr = _attr(hitter, "aggressiveness")
        disc = _attr(hitter, "discipline")
        spd = _attr(hitter, "speed")
        hot_head = (arch == "Enforcer") or (aggr >= 80 and disc <= 45)
        try:
            star = float(getattr(victim, "overall", 0) or 0) >= 82
        except Exception:
            star = False
        smallish = _attr(victim, "strength", 75.0) < 72
        loc = _rink_location(sim, victim)
        # The canonical case: enforcer hot-head vs small star, center ice,
        # with a head of steam.
        if (hot_head and loc == "center ice" and spd >= 75
                and (star or smallish)):
            if random.random() < 0.18:
                return HitType.CHARGING
        # Finishing a man along the wall, late and high.
        if hot_head and loc == "along the boards" and aggr >= 75:
            if random.random() < 0.12:
                return HitType.BOARDING
        return HitType.BODY_CHECK
    except Exception:
        try:
            from simulation import HitType as _HT
            return _HT.BODY_CHECK
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Officiating accuracy: per-game crews, whiffs on REAL infractions
# ---------------------------------------------------------------------------

CREW_ACCURACY_RANGE = (0.93, 0.995)

#: Infractions dirty enough that a whiffed call is a story. Everything
#: else is whistled at ~100% -- only the dirty stuff tests the crew.
DIRTY_INFRACTIONS = {"Boarding", "Charging", "Elbowing"}

#: Heat spike when a dirty call is missed outright.
MISSED_CALL_HEAT = 6.0


def init_crew(sim: Any) -> float:
    """Deal this game's officiating crew. Mostly sharp, never perfect."""
    try:
        acc = random.uniform(*CREW_ACCURACY_RANGE)
        sim._crew_accuracy = acc
        return acc
    except Exception:
        return 0.97


def crew_accuracy(sim: Any) -> float:
    try:
        acc = float(getattr(sim, "_crew_accuracy", 0.0) or 0.0)
        if acc <= 0.0:
            return init_crew(sim)
        return max(0.80, min(1.0, acc))
    except Exception:
        return 0.97


def is_missed_call(sim: Any, infraction_name: str) -> bool:
    """True when the crew whiffs a dirty call. Never raises."""
    try:
        if infraction_name not in DIRTY_INFRACTIONS:
            return False
        return random.random() > crew_accuracy(sim)
    except Exception:
        return False


def note_dirty_watch(sim: Any, offender: Any, team: Any,
                     infraction_name: str) -> None:
    """Arm the statement-goal watch: the *victim's* team (the team that
    didn't commit the foul) has ~10 game minutes to answer on the
    scoreboard. Stored on the sim; cleared by the next goal either way.
    """
    try:
        watch = getattr(sim, "_dirty_watch", None)
        if not isinstance(watch, dict):
            watch = {}
            sim._dirty_watch = watch
        home = getattr(sim, "home_team", None)
        victim_team = (getattr(sim, "away_team", None)
                       if team is home else home)
        vname = getattr(victim_team, "team_name", "") or ""
        if not vname:
            return
        watch[vname] = {
            "offender": getattr(offender, "full_name", "An opponent"),
            "offender_team": getattr(team, "team_name", "") or "",
            "infraction": infraction_name,
            "until": _elapsed(sim) + DIRTY_WATCH_WINDOW,
        }
    except Exception:
        pass


DIRTY_WATCH_WINDOW = 600.0  # 10 game minutes to answer


def _heat(sim: Any, amount: float, cap: float = 40.0) -> None:
    try:
        sim._live_heat = min(cap, max(0.0, float(getattr(sim, "_live_heat", 0.0)) + amount))
    except Exception:
        pass


def apply_missed_call(sim: Any, player: Any, team: Any,
                      infraction_name: str) -> Dict[str, Any]:
    """The crew whiffed a real dirty call: no whistle. Heat spikes, the
    rivalry record remembers the bad call, DoPS still gets its look at
    the play (same stash shape the live path has always used)."""
    out: Dict[str, Any] = {"missed": True, "infraction": infraction_name}
    try:
        pname = getattr(player, "full_name", "A checker")
        tname = getattr(team, "team_name", "") or ""
        home = getattr(sim, "home_team", None)
        victim_team = (getattr(sim, "away_team", None)
                       if team is home else home)
        vname = getattr(victim_team, "team_name", "") or "the opposition"
        _heat(sim, MISSED_CALL_HEAT)
        try:
            sim._log_event(
                f"{pname} ({tname}) gets away with {infraction_name} -- "
                f"NO CALL! The {vname} bench is livid.", "PENALTY")
        except Exception:
            pass
        try:
            sim._emit_pbp("missed_call", player=pname, team=tname,
                          infraction=infraction_name, victim_team=vname)
        except Exception:
            pass
        try:
            from reputation_system import record_game_incident
            record_game_incident(
                getattr(sim, "rivalries", []), team, victim_team, "bad_call",
                f"{pname} ({tname}) {infraction_name} on {vname} went uncalled")
        except Exception:
            pass
        # DoPS look (additive): the same stash the old invented-roll path
        # fed, so post-game review treats a real whiff identically.
        try:
            hcon = _attr(player, "controversy",
                         _attr(player, "base_controversy", 30.0))
            hits = getattr(sim, "_live_borderline_hits", None)
            if not isinstance(hits, list):
                hits = []
                sim._live_borderline_hits = hits
            hits.append({
                "kind": "controversial_hit",
                "hitter": pname, "hitter_team": tname,
                "victim": vname, "victim_team": vname,
                "hitter_controversy": max(0.0, min(100.0, hcon)),
            })
        except Exception:
            pass
        out.update({"player": pname, "team": tname, "victim_team": vname})
        # Officiating link for the retaliation engine: a whiffed dirty call
        # makes the next injury-causing hit by the same team read
        # intentional (perceive_intent consults this).
        try:
            sim._last_missed_dirty = {"team": team, "player": player,
                                      "elapsed": _elapsed(sim)}
        except Exception:
            pass
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Personality-scaled fighting
# ---------------------------------------------------------------------------

def _instigation(p: Any) -> float:
    try:
        from controversy_system import instigation_tendency
        return max(0.0, min(1.0, float(instigation_tendency(p))))
    except Exception:
        return 0.3


def personnel_fight_mult(home_roster: Any, away_roster: Any) -> float:
    """Roster-level fight scaling: a room full of rats fights at multiples
    of a room full of choirboys at the same tension. Grounded so the
    league-average roster multiplies by ~1.0 (league fight rate unchanged
    on average -- only the distribution moves). Never raises."""
    try:
        def _mean(roster):
            vals = [_instigation(p) for p in (roster or [])]
            return sum(vals) / len(vals) if vals else 0.30

        def _enforcers(roster):
            n = 0
            for p in (roster or []):
                if _archetype(p) == "Enforcer":
                    n += 1
            return n

        hm, am = _mean(home_roster), _mean(away_roster)
        # League-average instigation ~0.30 -> mult 1.0; rats (~0.55) -> ~1.8;
        # choirboys (~0.18) -> ~0.6.
        mult = ((hm + am) / 2.0) / 0.30
        mult *= 1.0 + 0.05 * min(4, _enforcers(home_roster)
                                 + _enforcers(away_roster))
        return max(0.45, min(2.25, mult))
    except Exception:
        return 1.0


def pick_fight_instigator(skaters: List[Any], heat: float = 0.0,
                          rivalry: float = 0.0) -> Optional[Any]:
    """Who drops the gloves first: weighted by personality, not proximity.

    Consumes (never duplicates) instigation_tendency: the rat with a
    hot head starts it; the choirboy almost never does. Enforcers and
    power forwards answer the bell; heat and rivalry raise everyone's
    temperature. Never raises.
    """
    try:
        cands = [p for p in (skaters or []) if p is not None]
        if not cands:
            return None

        def _w(p):
            try:
                w = 0.05 + _instigation(p)
                arch = _archetype(p)
                if arch == "Enforcer":
                    w *= 1.7
                elif arch in ("Grinder", "Power Forward"):
                    w *= 1.25
                # Undisciplined players go more readily.
                w *= 1.0 + (100.0 - _attr(p, "discipline", 50.0)) / 250.0
                w *= 1.0 + max(0.0, heat) / 150.0
                w *= 1.0 + max(0.0, rivalry) / 200.0
                return max(0.01, w)
            except Exception:
                return 0.05

        weights = [_w(p) for p in cands]
        if sum(weights) <= 0:
            return None
        return random.choices(cands, weights=weights, k=1)[0]
    except Exception:
        return None


def pick_willing_combatant(skaters: List[Any]) -> Optional[Any]:
    """The other side's answer: the willing combatant, not a random
    victim. Enforcers and heavy, willing players take the dance; skill
    players almost never do. Never raises."""
    try:
        cands = [p for p in (skaters or []) if p is not None]
        if not cands:
            return None

        def _w(p):
            try:
                w = 0.05 + _instigation(p)
                if _archetype(p) == "Enforcer":
                    w *= 1.9
                w *= 0.5 + _attr(p, "strength", 60.0) / 100.0
                return max(0.01, w)
            except Exception:
                return 0.05

        weights = [_w(p) for p in cands]
        if sum(weights) <= 0:
            return None
        return random.choices(cands, weights=weights, k=1)[0]
    except Exception:
        return None


def _fight_win_bonus(p: Any) -> float:
    """The Enforcer trait's fight_win_mult, finally consumed."""
    try:
        from player_traits import get_sim_bonus
        return max(0.5, float(get_sim_bonus(p, "fight_win_mult", 1.0)))
    except Exception:
        return 1.0


def fight_outcome(a: Any, b: Any) -> Tuple[Any, Any, str]:
    """Decide a fight. Win score is multi-attribute -- strength,
    aggressiveness and determination, times the fighter's fight_win_mult
    (enforcers know how to do this). Returns (winner, loser, method).
    Never raises.
    """
    try:
        if b is None:
            return a, None, "unanswered"
        sa = ((_attr(a, "strength") + _attr(a, "aggressiveness")
               + _attr(a, "determination")) / 3.0) * _fight_win_bonus(a)
        sb = ((_attr(b, "strength") + _attr(b, "aggressiveness")
               + _attr(b, "determination")) / 3.0) * _fight_win_bonus(b)
        p_a = sa / (sa + sb) if (sa + sb) > 0 else 0.5
        winner = a if random.random() < p_a else b
        loser = b if winner is a else a
        method = "decision"
        r = random.random()
        if abs(p_a - 0.5) > 0.18 and r < 0.25:
            method = "knockdown"
        elif r < 0.08:
            method = "draw"
            return a, b, method
        return winner, loser, method
    except Exception:
        return a, b, "decision"


# ---------------------------------------------------------------------------
# Fight game effects: bench spark, intensity, storage
# ---------------------------------------------------------------------------

SPARK_WINDOW = 300.0        # 5 game minutes of lifted bench
SPARK_MULT = 1.05           # base finishing lift for the winner's team
SPARK_MULT_HEATED = 1.07    # rivalry / boiling games: bigger answer


def _team_of(sim: Any, player: Any) -> Any:
    try:
        fn = getattr(sim, "_get_player_team", None)
        return fn(player) if fn else None
    except Exception:
        return None


def apply_fight_spark(sim: Any, winner_team: Any,
                      heated: bool = False) -> None:
    """The winner's bench gets a short-term lift: explicit, logged, and
    time-boxed. Applied as its own xG channel (never inside momentum.py,
    which stays read-only by design)."""
    try:
        tname = getattr(winner_team, "team_name", "") or ""
        if not tname:
            return
        sparks = getattr(sim, "_fight_spark", None)
        if not isinstance(sparks, dict):
            sparks = {}
            sim._fight_spark = sparks
        sparks[tname] = {
            "until": _elapsed(sim) + SPARK_WINDOW,
            "mult": SPARK_MULT_HEATED if heated else SPARK_MULT,
            "heated": bool(heated),
        }
    except Exception:
        pass


def fight_spark_mult(sim: Any, attacking_team: Any) -> float:
    """xG multiplier for the attacking side from an active bench spark.
    1.0 when nothing is burning. Never raises."""
    try:
        tname = getattr(attacking_team, "team_name", "") or ""
        sparks = getattr(sim, "_fight_spark", None)
        if not isinstance(sparks, dict):
            return 1.0
        s = sparks.get(tname)
        if not s:
            return 1.0
        if _elapsed(sim) > float(s.get("until", 0.0)):
            return 1.0
        return max(1.0, min(1.12, float(s.get("mult", 1.0))))
    except Exception:
        return 1.0


def rivalry_heat_between(rivalries: Any, home: Any, away: Any) -> float:
    """0-100 bad blood right now (caleb's heat plumbing -- read only)."""
    try:
        from reputation_system import get_rivalry_heat
        res = get_rivalry_heat(rivalries or [], home, away)
        if isinstance(res, dict):
            return max(0.0, min(100.0, float(res.get("heat", 0.0))))
        return max(0.0, min(100.0, float(res or 0.0)))
    except Exception:
        return 0.0


def store_fight(sim: Any, fighter_a: Any, team_a: Any, fighter_b: Any,
                team_b: Any, winner: Any, method: str) -> Dict[str, Any]:
    """Persist a fight: the rivalry record (long-term memory), the game's
    fight log, and the grudge floor that makes the feud decay slower.
    Never raises."""
    out: Dict[str, Any] = {"stored": False}
    try:
        an = getattr(fighter_a, "full_name", "A fighter")
        bn = getattr(fighter_b, "full_name", "An opponent") \
            if fighter_b is not None else "no opponent"
        wn = getattr(winner, "full_name", an)
        atn = getattr(team_a, "team_name", "") or ""
        btn = getattr(team_b, "team_name", "") or ""
        detail = f"{an} ({atn}) vs {bn} ({btn}) -- {wn} takes it ({method})"
        # Persistent record #1: the rivalry store (survives saves, feeds
        # future tension via decayed wounds; the narrative-ledger bridge
        # inside record_game_incident carries it to media/fans/inbox).
        try:
            from reputation_system import record_game_incident, feed_grudge
            record_game_incident(getattr(sim, "rivalries", []),
                                 team_a, team_b, "fight", detail)
            # Persistent record #2: deepen the grudge floor so the
            # offseason decay holds this feud longer.
            feed_grudge(getattr(sim, "rivalries", []), team_a, team_b,
                        grudge=2)
        except Exception:
            pass
        # Persistent record #3: the game's own fight log (box-score grade
        # facts: who, who won, when).
        try:
            log = getattr(sim, "_fight_log", None)
            if not isinstance(log, list):
                log = []
                sim._fight_log = log
            log.append({
                "a": an, "a_team": atn,
                "b": bn, "b_team": btn,
                "winner": wn, "method": method,
                "period": int(getattr(sim, "period", 1) or 1),
                "elapsed": _elapsed(sim),
            })
        except Exception:
            pass
        out.update({"stored": True, "detail": detail, "winner": wn})
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Live heat decay
# ---------------------------------------------------------------------------

HEAT_DECAY_PER_SECOND = 0.004  # ~5 heat per quiet period


def decay_heat(sim: Any, seconds: float) -> None:
    """Cool the room during calm stretches: heat decays with game time so
    a chippy first period stops inflating fight odds all night. Spikes
    (fights, majors, missed calls) still land on top. Never raises."""
    try:
        secs = max(0.0, float(seconds or 0.0))
        if secs <= 0:
            return
        h = float(getattr(sim, "_live_heat", 0.0) or 0.0)
        sim._live_heat = max(0.0, h - secs * HEAT_DECAY_PER_SECOND)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Statement goals
# ---------------------------------------------------------------------------

def check_statement_goal(sim: Any, scoring_team: Any,
                         shooter: Any) -> Optional[Dict[str, Any]]:
    """A goal by the victim's team while the dirty-play watch is live is
    a STATEMENT goal: heat, a rivalry wound, a headline, and a stored
    incident the offseason decay/grudge floors carry forward. Any goal by
    the offending team first kills the watch quietly. Never raises."""
    try:
        watch = getattr(sim, "_dirty_watch", None)
        if not isinstance(watch, dict):
            return None
        tname = getattr(scoring_team, "team_name", "") or ""
        w = watch.pop(tname, None)
        if w is None:
            # The offending team scoring kills every live watch.
            watch.clear()
            return None
        if _elapsed(sim) > float(w.get("until", 0.0)):
            return None
        offender = w.get("offender", "An opponent")
        oteam = w.get("offender_team", "")
        infraction = w.get("infraction", "a dirty play")
        sname = getattr(shooter, "full_name", "A scorer")
        # Short-term: heat spike now.
        _heat(sim, 4.0)
        # Long-term: stored wound + deeper grudge floor.
        try:
            from reputation_system import record_game_incident, feed_grudge
            home = getattr(sim, "home_team", None)
            opp = (getattr(sim, "away_team", None)
                   if scoring_team is home else home)
            record_game_incident(
                getattr(sim, "rivalries", []), scoring_team, opp,
                "statement_goal",
                f"{sname} ({tname}) answers {offender}'s {infraction} "
                f"with a goal -- statement made")
            feed_grudge(getattr(sim, "rivalries", []), scoring_team, opp,
                        grudge=1)
        except Exception:
            pass
        # Headline spec (headlines.py builds it; unknown kinds are
        # dropped safely there).
        try:
            pending = getattr(sim, "pending_headlines", None)
            if not isinstance(pending, list):
                pending = []
                sim.pending_headlines = pending
            pending.append({
                "kind": "statement_goal",
                "scoring_team": tname,
                "shooter": sname,
                "victim_team": oteam,
                "offender": offender,
                "infraction": infraction,
                "period": int(getattr(sim, "period", 1) or 1),
                "home_score": int(getattr(sim, "home_score", 0) or 0),
                "away_score": int(getattr(sim, "away_score", 0) or 0),
            })
        except Exception:
            pass
        try:
            sim._log_event(
                f"STATEMENT GOAL! {sname} answers {offender}'s {infraction} "
                f"-- the {tname} bench erupts.", "GOAL")
        except Exception:
            pass
        text = (f"STATEMENT GOAL by {sname} ({tname}) -- answering "
                f"{offender}'s {infraction}")
        try:
            sim._emit_pbp("statement_goal", scoring_team=tname,
                          shooter=sname, offender=offender,
                          infraction=infraction)
        except Exception:
            pass
        return {"text": text, "shooter": sname, "team": tname,
                "offender": offender, "infraction": infraction}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Retaliation engine ("receipts") -- W5
# ---------------------------------------------------------------------------
# A perceived-intent injury opens a retaliation DEBT owed by the offending
# team. The debt persists until answered or the game ends; unanswered debt
# settles into the rivalry store's long-term memory. Whether/how it gets
# answered is gated by player volatility, coach temperament + team identity,
# game situation, and the atmosphere meter. Answers climb an escalation
# ladder (chippy -> beef -> fight), and if the offending team defies the
# receipt instead of accepting it, the game tilts toward a brawl.
# Coaches order/permit responses per philosophy -- but high-volatility
# players sometimes police the game themselves regardless of orders.

RECEIPT_INTENT_FLOOR = 0.45      # below this the hit reads accidental: no debt
RECEIPT_MAX_OPEN = 2            # per team per game
RECEIPT_HEAT_OPEN = 3.0         # heat when a debt opens
RECEIPT_HEAT_CHIPPY = 2.0
RECEIPT_HEAT_BEEF = 3.0
RECEIPT_HEAT_DEFIED = 6.0
RECEIPT_HEAT_ACCEPTED = -2.0
RECEIPT_ANSWER_DELAY = (120.0, 420.0)   # game-seconds before a receipt comes due
MISSED_CALL_MEMORY = 90.0       # a whiffed dirty call accelerates intent this long


def _tension(sim: Any) -> float:
    """The sim's live tension meter as a float (0.0 when unavailable)."""
    try:
        return float(sim._live_tension())
    except Exception:
        return 0.0


def _receipts(sim: Any) -> List[Dict[str, Any]]:
    debts = getattr(sim, "_receipts", None)
    if not isinstance(debts, list):
        debts = []
        sim._receipts = debts
    return debts


def _hit_type_name(hit_type: Any) -> str:
    try:
        v = getattr(hit_type, "value", hit_type)
        return str(v or "").lower()
    except Exception:
        return ""


def perceive_intent(sim: Any, hitter: Any, victim: Any,
                    hit_type: Any = None, impact: int = 1) -> float:
    """How intentional did that injury-causing hit READ? 0..1.

    Draws on the officiating-accuracy model: a recent missed call on a
    dirty hit by the same team is itself a heat/intent accelerant -- the
    victim's bench is sure the league won't protect them, so the next
    borderline play reads dirty."""
    try:
        score = 0.25
        if _hit_type_name(hit_type) in ("charging", "boarding"):
            score += 0.45
        if int(impact or 1) >= 2:
            score += 0.15
        agg = _attr(hitter, "aggressiveness", 50.0)
        dis = _attr(hitter, "discipline", 50.0)
        con = _attr(hitter, "controversy",
                    _attr(hitter, "base_controversy", 30.0))
        if agg >= 80:
            score += 0.10
        if dis <= 35:
            score += 0.10
        if con >= 60:
            score += 0.10
        if _attr(victim, "overall", 60.0) >= 85:
            score += 0.10  # stars draw targeted hits
        # Officiating link: a recent whiffed dirty call by the hitter's
        # team makes this one read intentional.
        try:
            last = getattr(sim, "_last_missed_dirty", None)
            if isinstance(last, dict):
                hteam = _team_of(sim, hitter)
                if (last.get("team") is hteam
                        and _elapsed(sim) - float(last.get("elapsed", 0.0))
                        <= MISSED_CALL_MEMORY):
                    score += 0.20
        except Exception:
            pass
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.25


def maybe_open_receipt(sim: Any, hitter: Any, victim: Any,
                       hit_type: Any = None, impact: int = 1) -> Optional[Dict[str, Any]]:
    """An injury-causing hit with perceived intent opens a retaliation debt.
    Returns the debt dict, or None if the hit reads accidental."""
    try:
        intent = perceive_intent(sim, hitter, victim, hit_type, impact)
        if intent < RECEIPT_INTENT_FLOOR:
            return None
        debts = _receipts(sim)
        off_team = _team_of(sim, hitter)
        vic_team = _team_of(sim, victim)
        open_for = [d for d in debts
                    if not d.get("answered") and d.get("offending_team") is off_team]
        if len(open_for) >= RECEIPT_MAX_OPEN:
            return None
        delay = random.uniform(*RECEIPT_ANSWER_DELAY)
        debt = {
            "offending_team": off_team, "victim_team": vic_team,
            "hitter": hitter, "hitter_id": getattr(hitter, "id", None),
            "victim": victim, "victim_id": getattr(victim, "id", None),
            "intent": round(intent, 3),
            "created": _elapsed(sim),
            "due": _elapsed(sim) + delay,
            "answered": False, "escalation": 0, "defied": False,
            "via": None,
        }
        debts.append(debt)
        hname = getattr(hitter, "full_name", "A checker")
        vname = getattr(victim, "full_name", "a star")
        tname = getattr(off_team, "team_name", "")
        vtname = getattr(vic_team, "team_name", "")
        _heat(sim, RECEIPT_HEAT_OPEN)
        try:
            sim._log_event(
                f"RECEIPT OPEN: {hname} ({tname}) hurt {vname} ({vtname}) on "
                f"a hit that read intentional -- the {vtname} bench has not "
                f"forgotten.", "HIT")
        except Exception:
            pass
        try:
            sim._emit_pbp("receipt_open", hitter=hname, victim=vname,
                          offending_team=tname, victim_team=vtname,
                          intent=round(intent, 2))
        except Exception:
            pass
        return debt
    except Exception:
        return None


def _victim_coach_answer(sim: Any, debt: Dict[str, Any]) -> Tuple[float, bool]:
    """Coach direction: (probability bump, ordered?). Coaches are the key
    lever -- they order or permit responses per philosophy/team identity."""
    try:
        from reputation_system import coach_reprisal_tendency
        coach = None
        try:
            coach = sim._find_head_coach(debt["victim_team"])
        except Exception:
            coach = None
        tendency = coach_reprisal_tendency(coach) if coach is not None else 0.3
        ordered = tendency >= 0.6
        physical = 0.5
        try:
            import tactics as _tx
            physical = float(_tx.resolve_team_tactics(
                debt["victim_team"]).get("physical", 0.5))
        except Exception:
            pass
        bump = (tendency - 0.4) * 0.5 + (physical - 0.5) * 0.2
        return bump, ordered
    except Exception:
        return 0.0, False


def receipt_gate(sim: Any, debt: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Should the debt be answered now, and by whose authority? Returns
    (answer, via) where via is 'coach' | 'player' | None.

    Player policing exists alongside coach direction: a high-volatility
    skater sometimes takes the receipt himself regardless of orders."""
    try:
        intent = float(debt.get("intent", 0.5))
        p = 0.15 + 0.55 * intent
        bump, ordered = _victim_coach_answer(sim, debt)
        p += bump
        if ordered:
            p += 0.15
        # Game situation: trailing late (elimination hockey) lowers the bar.
        try:
            home = sim.home_team is debt["victim_team"]
            diff = (sim.home_score - sim.away_score) if home \
                else (sim.away_score - sim.home_score)
            period = int(getattr(sim, "period", 1) or 1)
            if period >= 3 and diff < 0:
                p += 0.15  # trailing late: pride is all that's left
                if getattr(sim, "is_playoff", False):
                    p += 0.10
            elif diff >= 3:
                p -= 0.10  # up big: take the two points, skip the receipt
        except Exception:
            pass
        # Atmosphere: a loud, tense room makes answers more likely.
        try:
            t = _tension(sim)
            if t >= 80:
                p += 0.10
            elif t >= 60:
                p += 0.05
        except Exception:
            pass
        # Player policing: high-volatility skaters act on their own.
        on_ice = []
        try:
            on_ice = sim._get_on_ice(debt["victim_team"]) or []
        except Exception:
            on_ice = []
        hottest = None
        for sk in on_ice:
            inst = _instigation(sk)
            if inst >= 0.70 and random.random() < (inst - 0.60) * 1.2:
                hottest = sk
                break
        if hottest is not None:
            return True, "player"
        p = max(0.02, min(0.95, p))
        if random.random() < p:
            return True, ("coach" if ordered else "player")
        return False, None
    except Exception:
        return False, None


def _on_ice_enforcer(sim: Any, team: Any) -> Optional[Any]:
    """The enforcer trigger: if the avenging team's enforcer is on the ice
    when a receipt is owed, that's an immediate gloves-off moment."""
    try:
        for sk in sim._get_on_ice(team) or []:
            if _archetype(sk) == "Enforcer":
                return sk
        return None
    except Exception:
        return None


def _receipt_avenger(sim: Any, debt: Dict[str, Any]) -> Optional[Any]:
    """Who answers: the enforcer if he's out there, else the most
    hot-headed skater on the ice."""
    try:
        enf = _on_ice_enforcer(sim, debt["victim_team"])
        if enf is not None:
            return enf
        on_ice = sim._get_on_ice(debt["victim_team"]) or []
        if on_ice:
            return pick_fight_instigator(list(on_ice),
                                         heat=getattr(sim, "_live_heat", 0.0))
        return None
    except Exception:
        return None


def _receipt_target(sim: Any, debt: Dict[str, Any]) -> Tuple[Optional[Any], Any]:
    """The receipt is for the HITTER first; if he's not dressed anymore,
    any willing combatant from the offending team will do."""
    try:
        hitter = debt.get("hitter")
        dressed_ids = set()
        try:
            for t in (sim.home_team, sim.away_team):
                for sk in sim._get_on_ice(t) or []:
                    dressed_ids.add(getattr(sk, "id", None))
        except Exception:
            pass
        if hitter is not None and getattr(hitter, "id", None) in dressed_ids:
            return hitter, debt["offending_team"]
        try:
            cands = sim._get_on_ice(debt["offending_team"]) or []
            opp = pick_willing_combatant(list(cands))
            if opp is not None:
                return opp, debt["offending_team"]
        except Exception:
            pass
        return None, debt["offending_team"]
    except Exception:
        return None, debt.get("offending_team")


def _defiance_roll(sim: Any, debt: Dict[str, Any]) -> bool:
    """After a retaliatory answer: does the offending team ACCEPT it as
    necessary (back off) or DEFY it (their personalities/coaching)? Defiance
    tilts the game toward a brawl."""
    try:
        from reputation_system import coach_reprisal_tendency
        p_accept = 0.55
        try:
            coach = sim._find_head_coach(debt["offending_team"])
            if coach is not None:
                p_accept += (_attr(coach, "discipline", 50.0) / 100.0) * 0.2
                p_accept -= coach_reprisal_tendency(coach) * 0.25
        except Exception:
            pass
        try:
            on_ice = sim._get_on_ice(debt["offending_team"]) or []
            if on_ice:
                p_accept -= max(_instigation(sk) for sk in on_ice) * 0.2
        except Exception:
            pass
        try:
            t = _tension(sim)
            if t >= 75:
                p_accept -= 0.15
        except Exception:
            pass
        return random.random() >= max(0.15, min(0.9, p_accept))
    except Exception:
        return False


def _answer_receipt_with_fight(sim: Any, debt: Dict[str, Any],
                               via: str) -> None:
    """Escalation ladder top: the receipt is answered with a fight, then
    the accept/defy branch resolves."""
    try:
        avenger = _receipt_avenger(sim, debt)
        target, off_team = _receipt_target(sim, debt)
        vic_team = debt["victim_team"]
        aname = getattr(avenger, "full_name", "An avenger") \
            if avenger is not None else "The bench"
        tname = getattr(target, "full_name", "a willing combatant") \
            if target is not None else "a willing combatant"
        if avenger is None or target is None:
            # Nobody to dance with: the receipt curdles into pure heat.
            _heat(sim, RECEIPT_HEAT_BEEF)
            debt["due"] = _elapsed(sim) + 300.0
            return
        try:
            sim._log_event(
                f"RECEIPT ANSWERED ({via}): {aname} goes after {tname} -- "
                f"the debt is being collected.", "FIGHT")
        except Exception:
            pass
        sim._book_fight_pair(avenger, vic_team, target, off_team)
        if _defiance_roll(sim, debt):
            debt["defied"] = True
            _heat(sim, RECEIPT_HEAT_DEFIED)
            try:
                sim._log_event(
                    f"The {getattr(off_team, 'team_name', '')} bench DEFIES "
                    f"the receipt -- this is tilting toward a brawl.", "FIGHT")
            except Exception:
                pass
            # Defiance meaningfully raises the brawl odds right now.
            try:
                from reputation_system import brawl_probability
                t = _tension(sim)
                bp = brawl_probability(t, bool(getattr(sim, "is_playoff", False)))
                if random.random() < min(0.30, bp * 5.0):
                    sim._run_brawl("a defied receipt")
            except Exception:
                pass
            debt["due"] = _elapsed(sim) + 300.0  # still simmering
        else:
            debt["answered"] = True
            debt["via"] = via
            _heat(sim, RECEIPT_HEAT_ACCEPTED)
            try:
                sim._log_event(
                    f"The {getattr(off_team, 'team_name', '')} accept the "
                    f"receipt as necessary -- they back off.", "FIGHT")
            except Exception:
                pass
    except Exception:
        pass


def tick_receipts(sim: Any) -> None:
    """Per-tick driver: due debts get gated; the enforcer trigger fires
    immediately when the avenging team's enforcer is on the ice."""
    try:
        for debt in _receipts(sim):
            if debt.get("answered"):
                continue
            if _elapsed(sim) < float(debt.get("due", 0.0)):
                continue
            vic_team = debt["victim_team"]
            # Enforcer trigger: gloves off, right now.
            enf = _on_ice_enforcer(sim, vic_team)
            if enf is not None and float(debt.get("intent", 0.0)) >= 0.5:
                _answer_receipt_with_fight(sim, debt, "enforcer")
                continue
            answer, via = receipt_gate(sim, debt)
            if not answer:
                debt["due"] = _elapsed(sim) + 300.0
                continue
            level = int(debt.get("escalation", 0) or 0) + 1
            debt["escalation"] = level
            debt["via"] = via
            if level <= 1:
                _heat(sim, RECEIPT_HEAT_CHIPPY)
                try:
                    sim._log_event(
                        f"Chippy play: the "
                        f"{getattr(vic_team, 'team_name', '')} are running "
                        f"the {getattr(debt['offending_team'], 'team_name', '')} "
                        f"every shift -- a receipt is owed.", "HIT")
                except Exception:
                    pass
                debt["due"] = _elapsed(sim) + 240.0
            elif level == 2:
                _heat(sim, RECEIPT_HEAT_BEEF)
                try:
                    sim._log_event(
                        f"Beefs after the whistle: the receipt for "
                        f"{getattr(debt.get('victim'), 'full_name', 'the star')} "
                        f"is coming due.", "FIGHT")
                except Exception:
                    pass
                debt["due"] = _elapsed(sim) + 240.0
            else:
                _answer_receipt_with_fight(sim, debt, via or "coach")
    except Exception:
        pass


def settle_receipts(sim: Any) -> None:
    """Game over: unanswered debts feed the rivalry store's long-term
    memory, so the story survives into the next meeting."""
    try:
        open_debts = [d for d in _receipts(sim) if not d.get("answered")]
        if not open_debts:
            return
        from reputation_system import record_game_incident
        for debt in open_debts:
            try:
                hname = getattr(debt.get("hitter"), "full_name", "A checker")
                vname = getattr(debt.get("victim"), "full_name", "a star")
                record_game_incident(
                    getattr(sim, "rivalries", []),
                    debt["offending_team"], debt["victim_team"],
                    "unanswered_receipt",
                    f"{hname} hurt {vname} on a hit that read intentional "
                    f"and no receipt ever came")
            except Exception:
                pass
        try:
            sim._log_event(
                f"{len(open_debts)} retaliation debt(s) go unpaid -- the "
                f"rivalry will remember.", "HIT")
        except Exception:
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Scott Stevens long memory: high-aggression / high-determination hitters
# hold grudges WITHIN a game. The game state gets chippier as it goes --
# more fights than baseline, more punishing big hits -- modulated by the
# personnel on each side.
# ---------------------------------------------------------------------------

def mark_stevens(sim: Any, hitter: Any, hit_type: Any = None,
                 impact: int = 1) -> None:
    """A Stevens-type (aggression >= 75, determination >= 70) throwing a
    dirty hit or a big-impact hit holds the grudge. Marks cap at 4."""
    try:
        if _attr(hitter, "aggressiveness", 50.0) < 75:
            return
        if _attr(hitter, "determination", 50.0) < 70:
            return
        dirty = _hit_type_name(hit_type) in ("charging", "boarding")
        if not dirty and int(impact or 1) < 2:
            return
        marks = getattr(sim, "_stevens", None)
        if not isinstance(marks, dict):
            marks = {}
            sim._stevens = marks
        hid = getattr(hitter, "id", None)
        marks[hid] = min(4, int(marks.get(hid, 0) or 0) + 1)
    except Exception:
        pass


def stevens_fight_mult(sim: Any) -> float:
    """Chippier room: grudges raise the fight target above baseline."""
    try:
        marks = getattr(sim, "_stevens", None)
        if not isinstance(marks, dict) or not marks:
            return 1.0
        total = sum(int(v or 0) for v in marks.values())
        return min(1.6, 1.0 + 0.12 * total)
    except Exception:
        return 1.0


def stevens_impact_bump(sim: Any, hitter: Any, impact: int) -> int:
    """Grudge-holding hitters finish a little more punishingly: a small,
    capped chance to lift the impact tier one step. Additive only -- never
    retunes the shared impact classifier."""
    try:
        marks = getattr(sim, "_stevens", None)
        if not isinstance(marks, dict):
            return impact
        m = int(marks.get(getattr(hitter, "id", None), 0) or 0)
        if m >= 2 and int(impact or 1) < 3 \
                and random.random() < min(0.24, 0.08 * m):
            return int(impact) + 1
        return impact
    except Exception:
        return impact
