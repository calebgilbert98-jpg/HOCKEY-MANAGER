"""Prospect development & farm production: EHM-style growth on steroids.

The years the NHL never sees -- junior, college, European leagues, the AHL --
are where real development happens (17-20, aside from generational talents who
develop anywhere). This module gives every prospect a statistically simulated
season each offseason, normalizes it through real NHL-equivalency (NHLe)
translation factors, and feeds it into the same breakout/bust potential engine
the NHL uses -- so late-round gems (Kucherov/Zetterberg/Datsyuk shapes) can
play their way up the ladder instead of being locked to their draft slot.

Design notes (EHM lineage, our engines on top):
- EHM core: age curves, potential grades as ceilings, determination/work ethic
  shaping growth, playing time and coaching quality mattering, injuries
  costing development. All present here.
- Steroids: our morale/confidence channel, league development quality, and
  role/opportunity all multiply into the yearly growth curve -- for NHL
  rookies too, not just prospects.
- Hidden truth: every prospect has a true_potential_grade (reality) and a
  potential_grade (the scouted belief). Development grows toward the TRUTH;
  scouting and on-ice production drag belief toward truth. Good scouting
  finds the late-round gem before the box scores do.

Performance: everything here runs ONCE per offseason per prospect. The farm
season is generated statistically (no game-by-game sim). Zero per-game cost.
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# League environments.
#
# nhle: NHL-equivalency translation factor -- established hockey-analytics
# values (Desjardins-style translations): a point in that league is worth
# this fraction of an NHL point. The great equalizer for cross-league
# production (a PPG in the KHL >> a PPG in the USHL).
# par: the overall rating that scores ~1.00 PPG in that league.
# games: typical season length.
# dev_junior / dev_pro: development quality multiplier for ages <=20 / 21+.
# The CHL is the best place on earth for a 17-year-old; the AHL is the best
# place for a 21-year-old. KHL teams don't play kids (0.85).
# ---------------------------------------------------------------------------
LEAGUE_ENVIRONMENTS: Dict[str, Dict[str, float]] = {
    "OHL":   {"nhle": 0.30, "par": 64, "games": 68, "dev_junior": 1.25, "dev_pro": 0.80},
    "WHL":   {"nhle": 0.30, "par": 64, "games": 68, "dev_junior": 1.25, "dev_pro": 0.80},
    "QMJHL": {"nhle": 0.28, "par": 64, "games": 68, "dev_junior": 1.25, "dev_pro": 0.80},
    "USHL":  {"nhle": 0.27, "par": 62, "games": 62, "dev_junior": 1.15, "dev_pro": 0.75},
    "NCAA":  {"nhle": 0.41, "par": 66, "games": 40, "dev_junior": 1.10, "dev_pro": 0.95},
    "SHL":   {"nhle": 0.59, "par": 70, "games": 52, "dev_junior": 1.00, "dev_pro": 1.10},
    "Liiga": {"nhle": 0.54, "par": 69, "games": 60, "dev_junior": 1.00, "dev_pro": 1.10},
    "KHL":   {"nhle": 0.83, "par": 74, "games": 68, "dev_junior": 0.85, "dev_pro": 1.15},
    "AHL":   {"nhle": 0.44, "par": 72, "games": 72, "dev_junior": 0.90, "dev_pro": 1.25},
    "NL":    {"nhle": 0.50, "par": 70, "games": 52, "dev_junior": 0.90, "dev_pro": 1.00},
}
NHL_PAR_OVERALL = 73.0  # rough NHL mean, for the role/opportunity leg

# Potential ladder mirrors Player.POTENTIAL_LADDER (kept local to avoid a
# hard import cycle; game_classes imports this module lazily).
POTENTIAL_LADDER = ["F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+",
                    "A-", "A", "A+"]

# Late-round gem seeding: probability the TRUE grade exceeds the displayed
# grade at generation, by draft round. The gem exists in the world whether
# or not anyone has scouted him -- that is what makes scouting rewarding.
# (Zetterberg: 7th round. Datsyuk: 6th. Kucherov: 2nd.)
_GEM_SEED = {
    1: (0.02, 0.00),
    2: (0.06, 0.02),
    3: (0.06, 0.02),
    4: (0.10, 0.04),
    5: (0.10, 0.04),
    6: (0.10, 0.04),
    7: (0.10, 0.04),
}
_MAX_TRUE_BUMP = {"F": 3, "D": 3, "D+": 2, "C-": 2, "C": 2, "C+": 1,
                  "B-": 1, "B": 1}

# Pedigree cushion (the Lafreniere rule): high picks get a long leash. A
# bust can still take them below this floor, but at quarter probability --
# Yakupovs happen, they just aren't the norm. Rounds 4+: no cushion; late
# picks wash out all the time. Values are max steps below draft-day hype.
_FLOOR_STEPS_BY_ROUND = {1: 2, 2: 3, 3: 3}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ladder() -> List[str]:
    try:
        from game_classes import Player
        return list(Player.POTENTIAL_LADDER)
    except Exception:
        return list(POTENTIAL_LADDER)


def _ladder_index(grade: str) -> int:
    ladder = _ladder()
    g = (grade or "C").strip().upper()
    if g not in ladder:
        g = g[:1] if g[:1] in ladder else "C"
        if g not in ladder:
            g = "C"
    try:
        return ladder.index(g)
    except ValueError:
        return ladder.index("C")


def _is_goalie(player: Any) -> bool:
    return getattr(getattr(player, "primary_position", None), "value", "") == "G"


def _overall(player: Any) -> float:
    try:
        return float(player.overall_rating())
    except Exception:
        return 65.0


def _morale(player: Any) -> float:
    return float(getattr(player, "morale", 70) or 70)


def true_grade(player: Any) -> str:
    """Reality. Falls back to the displayed grade for old saves."""
    return (getattr(player, "true_potential_grade", "") or
            getattr(player, "potential_grade", "C") or "C")


def displayed_grade(player: Any) -> str:
    return (getattr(player, "potential_grade", "C") or "C")


# ---------------------------------------------------------------------------
# League assignment
# ---------------------------------------------------------------------------
def _sticky_league(player: Any) -> Optional[str]:
    """Last year's league if still age-appropriate, else None.

    Junior rights are sticky: a CHL kid does not hop OHL -> WHL -> QMJHL
    every summer. Nationality routing only matters for the first
    assignment; after that the player stays put until he ages out.
    """
    last = (getattr(player, "farm_league", "") or "").strip().upper()
    if not last or last not in LEAGUE_ENVIRONMENTS:
        return None
    age = getattr(player, "age", 19) or 19
    junior_leagues = {"OHL", "WHL", "QMJHL", "USHL", "NCAA"}
    if age <= 20 and last in junior_leagues:
        # USHL is a pre-college league; everyone else stays through 20.
        if last == "USHL" and age >= 19:
            return None
        return last
    if age >= 21 and last not in junior_leagues:
        return last  # pro is pro
    return None


def assign_prospect_league(player: Any, current_assignment: Optional[str] = None,
                          rng: Any = random) -> str:
    """Pick the age/nationality-appropriate league for a prospect's season.

    Respects an explicit current assignment (AHL roster -> AHL). Otherwise:
    17-20 play junior/college/Europe by nationality; 21+ turn pro (AHL or a
    European top league).
    """
    if current_assignment and current_assignment in LEAGUE_ENVIRONMENTS:
        return current_assignment
    age = getattr(player, "age", 19) or 19
    nat = (getattr(player, "nationality", "") or "").lower()

    if age <= 20:
        if "canada" in nat or "canadian" in nat:
            return rng.choice(["OHL", "WHL", "QMJHL"])
        if "usa" in nat or "united states" in nat or "american" in nat:
            return "USHL" if age <= 18 else "NCAA"
        if "russia" in nat:
            return "KHL" if age >= 20 else rng.choice(["OHL", "WHL"])
        if "sweden" in nat or "swed" in nat:
            return "SHL"
        if "finland" in nat or "finn" in nat:
            return "Liiga"
        if "czech" in nat:
            return "NL"
        return rng.choice(["OHL", "WHL", "QMJHL", "USHL"])
    # 21+: pro hockey
    if "russia" in nat:
        return "KHL"
    if "sweden" in nat:
        return "SHL"
    if "finland" in nat:
        return "Liiga"
    return "AHL"


# ---------------------------------------------------------------------------
# Season simulation (statistical -- no game-by-game cost)
# ---------------------------------------------------------------------------
def _age_scoring_mult(age: int) -> float:
    if age <= 17:
        return 0.80
    if age == 18:
        return 0.90
    if age == 19:
        return 1.00
    return 1.05


def simulate_prospect_season(player: Any, league: Optional[str] = None,
                             rng: Any = random) -> Dict[str, Any]:
    """Generate one statistical season for a prospect and store it.

    Persists to player.farm_league / player.farm_season, and appends to
    player.farm_history (capped at 6 seasons). Runs once per offseason.
    """
    if league is None:
        # League stickiness: a prospect stays where he played last year if
        # it is still age-appropriate (a CHL kid does not hop OHL -> WHL ->
        # QMJHL every summer -- his junior club holds his rights).
        league = _sticky_league(player)
    league = assign_prospect_league(player, league, rng)
    env = LEAGUE_ENVIRONMENTS[league]
    age = getattr(player, "age", 19) or 19
    ovr = _overall(player)

    games = env["games"]
    gp = int(games * rng.uniform(0.72, 1.0))  # injuries, scratches, call-ups
    gp = max(gp, 5)

    if _is_goalie(player):
        base_sv = 0.890 + (ovr - env["par"]) * 0.0016
        sv = max(0.840, min(0.945, rng.gauss(base_sv, 0.012)))
        gaa = max(1.4, min(5.5, rng.gauss(3.1 - (ovr - env["par"]) * 0.06, 0.5)))
        w = int(gp * rng.uniform(0.35, 0.62))
        season = {"league": league, "gp": gp, "w": w, "l": gp - w,
                  "sv_pct": round(sv, 3), "gaa": round(gaa, 2)}
    else:
        exp_ppg = (1.0 + (ovr - env["par"]) * 0.055) * _age_scoring_mult(age)
        exp_ppg = max(0.05, min(2.6, exp_ppg))
        ppg = max(0.0, rng.lognormvariate(math.log(max(exp_ppg, 1e-6)), 0.22))
        pts = int(round(ppg * gp))
        # Goal share by archetype-ish proxy: shooting vs passing edge
        try:
            shoot = float(getattr(player, "shooting", 50) or 50)
            pas = float(getattr(player, "passing", 50) or 50)
            goal_share = 0.42 + (shoot - pas) / 400.0
        except Exception:
            goal_share = 0.42
        goal_share = max(0.25, min(0.60, goal_share))
        goals = int(round(pts * goal_share))
        # Defensive performance: plus/minus from defensive attributes vs
        # league par, scaled by ice time, with sample noise. Shutdown
        # defenders and two-way forwards finally get a number that tells
        # their story; one-dimensional scorers bleed against. The baseline
        # sits below overall par -- teenagers defend worse than their
        # overall suggests. Small samples are noisy on purpose: sample
        # size is a legitimate reason to be deceived, decorative numbers
        # are not.
        try:
            _def_avg = (float(getattr(player, "defensive_awareness", 50)
                              or 50)
                        + float(getattr(player, "checking", 50) or 50)
                        + float(getattr(player, "pokecheck", 50) or 50)) / 3.0
            _pm_exp = (_def_avg - (env["par"] - 12)) * gp * 0.016
            _pm = int(round(_pm_exp + rng.gauss(0, math.sqrt(max(gp, 1))
                                                 * 0.55)))
        except Exception:
            _pm = 0
        season = {"league": league, "gp": gp, "g": goals, "a": pts - goals,
                  "pts": pts, "ppg": round(pts / gp, 3) if gp else 0.0,
                  "plus_minus": _pm}

    player.farm_league = league
    player.farm_season = dict(season)
    hist = getattr(player, "farm_history", None)
    if not isinstance(hist, list):
        hist = []
        player.farm_history = hist
    hist.append(dict(season))
    while len(hist) > 6:
        hist.pop(0)
    return season


def _nhle_of_season(season: Dict[str, Any]) -> float:
    """NHLe PPG for one stored farm-season dict."""
    league = (season or {}).get("league", "")
    env = LEAGUE_ENVIRONMENTS.get(league)
    if not env:
        return 0.0
    return float((season or {}).get("ppg", 0.0) or 0.0) * env["nhle"]


def farm_nhle_ppg(player: Any) -> float:
    """NHL-equivalent points per game for the just-simulated farm season."""
    if _is_goalie(player):
        return 0.0
    return _nhle_of_season(getattr(player, "farm_season", None) or {})


# ---------------------------------------------------------------------------
# Breakout / bust evaluation (the gem engine)
# ---------------------------------------------------------------------------
def _prospect_thresholds(age: int):
    # Applied to NHLe PPG. NHLe compresses junior scoring, so these sit
    # below the NHL thresholds -- but only genuinely dominant age-relative
    # production clears them. Bust bar is low: kids are supposed to be raw.
    if age <= 20:
        return 0.50, 0.18
    if age <= 23:
        return 0.60, 0.25
    return 0.70, 0.32


def evaluate_prospect_season(player: Any, rng: Any = random) -> Optional[str]:
    """Breakout/bust potential movement from a farm season.

    Moves the TRUE grade (reality) and drags the displayed grade (belief)
    after it. Late-round grades need louder production to break out -- the
    door stays open, it just takes more knocking. Returns
    "breakout"/"bust"/"noticed"/None.
    """
    age = getattr(player, "age", 99) or 99
    if age >= 27:
        return None
    season = getattr(player, "farm_season", None) or {}
    gp = int(season.get("gp", 0) or 0)
    if gp < 15:  # unreliable sample -- no judgement
        return None

    ladder = _ladder()
    t_idx = _ladder_index(true_grade(player))
    d_idx = _ladder_index(displayed_grade(player))
    b_line = ladder.index("B-") if "B-" in ladder else 6

    reliability = min(1.0, gp / 40.0)

    breakout = bust = False
    if _is_goalie(player):
        sv = float(season.get("sv_pct", 0) or 0)
        if sv >= 0.915 and age <= 25:
            breakout = True
        elif sv < 0.890 and sv > 0 and t_idx >= b_line:
            bust = True
    else:
        nhle = farm_nhle_ppg(player)
        bo_ppg, bu_ppg = _prospect_thresholds(age)
        # Late-round pedigree: the door is open but the knock must be louder
        # (Kucherov had to dominate, not just produce).
        pedigree_mult = 1.10 if d_idx < ladder.index("C") else 1.0
        if nhle >= bo_ppg * pedigree_mult:
            breakout = True
        elif nhle < bu_ppg and t_idx >= b_line:
            bust = True

    result = None
    if breakout and t_idx < len(ladder) - 1:
        # Base 65% like the NHL engine, scaled by sample reliability; quieter
        # for low-pedigree prospects (they need to do it twice).
        p = 0.65 * reliability
        if d_idx < ladder.index("C"):
            p *= 0.80
        if rng.random() < p:
            player.true_potential_grade = ladder[t_idx + 1]
            result = "breakout"
        # The world notices loud production even when the grade doesn't move
        if d_idx < t_idx and rng.random() < 0.70 * reliability:
            player.potential_grade = ladder[min(d_idx + 1, t_idx)]
            result = result or "noticed"
    elif bust and t_idx > 0:
        p = 0.45 * reliability
        if d_idx >= ladder.index("A-"):
            p *= 1.20  # touted prospects live under the microscope
        floor_idx = pedigree_floor_index(player)
        if 0 <= floor_idx and t_idx - 1 < floor_idx:
            # Pedigree cushion: high picks get a long leash. The floor is
            # soft, not a wall -- Yakupovs still happen, rarely.
            p *= 0.25
        if rng.random() < min(p, 0.95):
            player.true_potential_grade = ladder[t_idx - 1]
            result = "bust"
        if d_idx > t_idx and rng.random() < 0.60:
            player.potential_grade = ladder[max(d_idx - 1, t_idx)]
            result = result or "noticed"

    # Hype cools: touted-as-elite (true A-/A+) prospects whose production is
    # solid but nowhere near elite-track get re-evaluated down -- the
    # Lafreniere adjustment. Very good, not generational. The pedigree
    # floor keeps them NHL-caliber (soft).
    if result is None:
        cool = False
        if _is_goalie(player):
            sv = float(season.get("sv_pct", 0) or 0)
            cool = 0 < sv < 0.900 and t_idx >= ladder.index("A-")
        else:
            nhle = farm_nhle_ppg(player)
            bo_ppg, _ = _prospect_thresholds(age)
            cool = (t_idx >= ladder.index("A-") and nhle < bo_ppg * 0.60)
        if cool:
            floor_idx = pedigree_floor_index(player)
            p = 0.30 * reliability
            if 0 <= floor_idx and t_idx - 1 < floor_idx:
                p *= 0.25
            if rng.random() < p:
                player.true_potential_grade = ladder[t_idx - 1]
                if d_idx > t_idx - 1 and rng.random() < 0.50:
                    player.potential_grade = ladder[d_idx - 1]
                result = "cooled"

    # Sustained strong (sub-breakout) years still move belief toward truth:
    # the Datsyuk story -- dominated at home, scouts eventually caught on.
    if result is None and not _is_goalie(player):
        nhle = farm_nhle_ppg(player)
        bo_ppg, _ = _prospect_thresholds(age)
        if d_idx < t_idx and nhle >= bo_ppg * 0.55:
            if rng.random() < 0.30 * reliability:
                player.potential_grade = ladder[d_idx + 1]
                result = "noticed"

    # Confidence follows the story.
    if result == "breakout":
        player.morale = min(100, _morale(player) + 8)
    elif result == "bust":
        player.morale = max(1, _morale(player) - 8)
    return result


# ---------------------------------------------------------------------------
# Development environment factor ("steroids" on the yearly curve)
# ---------------------------------------------------------------------------
def development_environment_factor(player: Any,
                                   league: Optional[str] = None) -> float:
    """0.70..1.50 multiplier on yearly growth for young players.

    The monthly engine owns coach influence; this owns everything else:
    the 17-20 prime window, league development quality, morale/confidence,
    and role/opportunity. Generational teens (true A+) develop regardless --
    the factor damps toward 1.0 for them.
    """
    age = getattr(player, "age", 25) or 25
    # The whole development curve slides with the player's arc (late
    # bloomers peak later, early peaks earlier) -- so the environment's
    # age windows slide with it. Otherwise the env curve would fight the
    # arc curve (e.g. muting a late bloomer's delayed prime).
    try:
        _shift = {"standard": 0, "late_bloomer": 2, "early_peak": -2}.get(
            getattr(player, "development_arc", "standard"), 0)
    except Exception:
        _shift = 0
    if age > 26 + _shift:
        return 1.0  # veterans are past the growth curve anyway

    factor = 1.0
    # 1. The prime window: real development starts 17-20 (shifted by arc).
    if age <= 20 + _shift:
        factor *= 1.20
    elif age <= 23 + _shift:
        factor *= 1.05
    else:
        factor *= 0.90

    # 2. League development quality for the age band.
    lg = league or getattr(player, "farm_league", "") or "AHL"
    env = LEAGUE_ENVIRONMENTS.get(lg)
    if env:
        factor *= env["dev_junior"] if age <= 20 else env["dev_pro"]
    elif lg == "NHL":
        factor *= 1.0

    # 3. Morale / confidence.
    factor *= 1.0 + (_morale(player) - 70) * 0.0025

    # 4. Role / opportunity: kids who run the league play more and grow more.
    par = env["par"] if env else NHL_PAR_OVERALL
    edge = (_overall(player) - par) / 12.0
    factor *= max(0.90, min(1.12, 1.0 + edge * 0.08))

    # 5. Generational talent develops regardless -- damp toward neutral.
    if age <= 23 + _shift and true_grade(player).strip().upper() == "A+":
        factor = 1.0 + (factor - 1.0) * 0.4

    return round(max(0.70, min(1.50, factor)), 3)


# ---------------------------------------------------------------------------
# Hidden truth: seeding + scouting reveal
# ---------------------------------------------------------------------------
def seed_true_potential(player: Any, draft_round: int = 4,
                        rng: Any = random) -> None:
    """Deal the hidden true grade at generation.

    Displayed grade stays as scouted; true may sit 1-2 steps higher for
    later picks. Also stamps draft_round and the pedigree floor (Lafreniere
    cushion). Called by the draft generator. Idempotent.
    """
    if getattr(player, "true_potential_grade", ""):
        return
    draft_round = max(1, min(7, int(draft_round or 4)))
    player.draft_round = draft_round
    displayed = displayed_grade(player)
    p1, p2 = _GEM_SEED.get(draft_round, (0.10, 0.04))
    bump = 0
    roll = rng.random()
    if roll < p2:
        bump = 2
    elif roll < p1 + p2:
        bump = 1
    ladder = _ladder()
    if bump:
        max_bump = _MAX_TRUE_BUMP.get(displayed.strip().upper(), 1)
        bump = min(bump, max_bump)
        idx = _ladder_index(displayed)
        player.true_potential_grade = ladder[min(idx + bump, len(ladder) - 1)]
    else:
        player.true_potential_grade = displayed
    # Pedigree floor: measured from draft-day hype (the higher of truth and
    # belief -- expectations are set by the hype).
    hype_idx = max(_ladder_index(displayed),
                   _ladder_index(player.true_potential_grade))
    steps = _FLOOR_STEPS_BY_ROUND.get(draft_round)
    player.pedigree_floor = ladder[max(0, hype_idx - steps)] \
        if steps is not None else ""


def pedigree_floor_index(player: Any) -> int:
    """Ladder index of the player's pedigree floor, or -1 for no floor."""
    fl = (getattr(player, "pedigree_floor", "") or "").strip().upper()
    if not fl:
        return -1
    return _ladder_index(fl)


def scout_reveal_step(player: Any, scout_jpp: int = 50,
                      rng: Any = random) -> bool:
    """A scout report nudges the displayed grade toward the true grade.

    Better judging-player-potential = more likely the org learns the truth.
    Returns True if the displayed grade moved.
    """
    t_idx = _ladder_index(true_grade(player))
    d_idx = _ladder_index(displayed_grade(player))
    if t_idx == d_idx:
        return False
    # JPP 50 -> ~35% to learn; JPP 90 -> ~75%.
    p = 0.35 + (max(0, min(100, scout_jpp)) - 50) * 0.01
    if rng.random() < max(0.05, min(0.95, p)):
        ladder = _ladder()
        step = 1 if t_idx > d_idx else -1
        player.potential_grade = ladder[d_idx + step]
        return True
    return False


# ---------------------------------------------------------------------------
# Call-up readiness (0-100): is this kid ready for NHL minutes?
# ---------------------------------------------------------------------------
def callup_readiness(player: Any) -> float:
    """0-100 readiness score. Overall vs the NHL bar, age-adjusted, with a
    bump for farm production trending the right way."""
    ovr = _overall(player)
    age = getattr(player, "age", 22) or 22
    score = (ovr - 68.0) * 5.0  # 68 = replacement level, 88 = plug-and-play
    if age <= 20:
        score -= 8  # kids need to dominate first
    elif age >= 24:
        score += 4
    # Farm trend: last two seasons of NHLe production
    hist = getattr(player, "farm_history", None) or []
    if len(hist) >= 1 and not _is_goalie(player):
        last = hist[-1]
        env = LEAGUE_ENVIRONMENTS.get(last.get("league", ""), {})
        nhle = float(last.get("ppg", 0) or 0) * env.get("nhle", 0)
        score += max(-6, min(10, (nhle - 0.35) * 25))
    if _is_goalie(player) and len(hist) >= 1:
        sv = float(hist[-1].get("sv_pct", 0) or 0)
        score += max(-6, min(10, (sv - 0.900) * 250))
    if _is_goalie(player) and bool(getattr(player, "generational_goalie", False)):
        # The fate roll: a generational goalie prospect jumps the queue.
        # The Price/Fleury path -- the organization clears a lane for him.
        score += 15
    return round(max(0.0, min(100.0, score)), 1)


# ---------------------------------------------------------------------------
# One-call offseason processing for a prospect
# ---------------------------------------------------------------------------
def process_prospect_offseason(player: Any, league: Optional[str] = None,
                               rng: Any = random) -> Dict[str, Any]:
    """Simulate the farm season, evaluate it, return a summary.

    Caller (League.end_of_season) runs this BEFORE age_one_year so the new
    grades shape the growth curve.
    """
    season = simulate_prospect_season(player, league, rng)
    result = evaluate_prospect_season(player, rng)
    # Persist the season's story (breakout/bust/noticed/cooled/None) so the
    # accolades system can weight awards by form, not just raw production.
    try:
        player.farm_result = result
    except Exception:
        pass
    return {"league": season.get("league"), "gp": season.get("gp"),
            "result": result,
            "true": true_grade(player), "displayed": displayed_grade(player)}


# ---------------------------------------------------------------------------
# Situational readiness: is he ready *right now, here*?
#
# Talent (callup_readiness) is the base. The situation moves it -- through a
# LOT of small attribute-driven terms, not a few flat bumps. Two kids with
# the same overall in the same injury crisis get different numbers because
# composure, big-game temperament, experience, confidence, work ethic,
# consistency, physical maturity, versatility, contract hunger, the coach's
# fit, and the team's situation all weigh in. Same scenario, different kid,
# different answer -- like real life.
#
# Legs:
#   1. Opportunity: an injured NHL regular at his position opens a door.
#      The bump scales with the hole's size AND how close this kid is to
#      filling it, then ~10 personal terms shape it further.
#   2. Line fit: the opening has to match his archetype -- scaled by the
#      attributes that define his role, not a flat +4.
#   3. Coach fit: response label plus the continuous fit score.
#   4. Farm trend: the slope of his production, not just up/down.
#   5. The fast channel: his live NHL audition (stamped at call-up in
#      main.call_up_to_nhl). Produce and the old grade stops mattering.
#   6. Room fit: chemistry with the group he'd join.
# ---------------------------------------------------------------------------

def _attr(player: Any, name: str, default: float = 50.0) -> float:
    try:
        v = getattr(player, name, default)
        return float(default if v is None else v)
    except (TypeError, ValueError):
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _pos_group(player: Any) -> str:
    pos = (getattr(getattr(player, "primary_position", None), "value", "")
           or "").upper()
    if pos == "G":
        return "G"
    if pos == "D":
        return "D"
    return "F"


def _skater_archetype(player: Any) -> str:
    """Rough role: what job does this skater do?"""
    if _is_goalie(player):
        return "goalie"
    scores = {
        "scorer": _attr(player, "shooting") + _attr(player, "hockey_iq"),
        "playmaker": _attr(player, "passing") + _attr(player, "vision"),
        "checker": _attr(player, "checking") + _attr(player, "strength"),
        "shutdown": _attr(player, "defense") + _attr(player, "strength"),
        "puck-mover": _attr(player, "skating") + _attr(player, "passing"),
    }
    return max(scores, key=scores.get)


# The two attributes that define each archetype's toolbox.
_ARCHETYPE_KEYS = {
    "scorer": ("shooting", "hockey_iq"),
    "playmaker": ("passing", "vision"),
    "checker": ("checking", "strength"),
    "shutdown": ("defense", "strength"),
    "puck-mover": ("skating", "passing"),
}


def _hole_tag(star_ovr: float) -> str:
    if star_ovr >= 80:
        return "Major piece down"
    if star_ovr >= 74:
        return "Regular down"
    return "Depth injury"


def _moment_terms(player: Any, star_ovr: float, team: Any,
                  out: List) -> None:
    """The ~10 personal terms that make the same hole a different question
    for every kid. Each is small; together they separate the league."""
    terms = [
        # The spotlight: some kids shrink, some grow.
        ("Composure in the spotlight",
         (_attr(player, "composure", 60) - 60) / 20.0 * 2.0),
        ("Big-game temperament",
         (_attr(player, "pressure_player", 50) - 50) / 25.0 * 2.0),
        # What's he feeling right now?
        ("Confidence right now",
         (_attr(player, "morale", 70) - 70) * 0.05
         + (_attr(player, "confidence", 60) - 60) * 0.04),
        # Workers force their way into lineups.
        ("Work ethic / determination",
         ((_attr(player, "determination", 55)
           + _attr(player, "work_ethic", 55)) / 2.0 - 55) * 0.06),
        # Coaches trust kids who bring it every night.
        ("Consistency coaches trust",
         (_attr(player, "consistency", 55) - 55) * 0.05),
        # Smart two-way kids slide up and down the lineup.
        ("Versatility",
         ((_attr(player, "hockey_iq", 55)
           + _attr(player, "off_the_puck", 55)) / 2.0 - 60) * 0.05),
        # Fragile kids are a gamble when the games matter.
        ("Durability question",
         -max(0.0, _attr(player, "injury_proneness", 50) - 55) * 0.06),
    ]
    # NHL experience: never played a shift vs been around.
    g = _attr(player, "nhl_games_played", 0)
    if g <= 0:
        terms.append(("Never played an NHL shift", -2.0))
    elif g >= 80:
        terms.append(("Been around the league", 2.0))
    elif g >= 20:
        terms.append(("Has a taste of the NHL", 1.0))
    # A top-six/top-four hole is a man's job -- boys get exposed.
    if star_ovr >= 80:
        terms.append(("Physical maturity for the role",
                      ((_attr(player, "strength", 55)
                        + _attr(player, "balance", 55)
                        + _attr(player, "stamina", 55)) / 3.0 - 60) * 0.06))
    # Contract-year hunger: playing for his next deal.
    try:
        if getattr(getattr(player, "contract", None), "years_remaining", 0) == 1:
            terms.append(("Contract-year hunger", 1.5))
    except Exception:
        pass
    # The team's situation sets the leash length.
    try:
        w = float(getattr(team, "wins", 0) or 0)
        l = float(getattr(team, "losses", 0) or 0)
        ot = float(getattr(team, "ot_losses", 0) or 0)
        if w + l + ot >= 10:
            pct = w / (w + l + ot)
            if pct >= 0.600:
                terms.append(("Contender -- short leash", -2.0))
            elif pct <= 0.400:
                terms.append(("Rebuild -- kids get runway", 2.0))
    except Exception:
        pass
    for label, d in terms:
        if abs(d) >= 0.5:
            out.append((label, round(d, 1)))


def _line_fit_terms(player: Any, star: Any, grp: str, out: List) -> None:
    """Does the opening match his game? Scaled by the attributes behind
    his archetype -- a 90-shooting sniper owns a scorer's hole in a way a
    68-shooting 'scorer' doesn't."""
    if grp == "G":
        return
    hole_arch = _skater_archetype(star)
    kid_arch = _skater_archetype(player)
    keys = _ARCHETYPE_KEYS.get(kid_arch, ("shooting", "hockey_iq"))
    toolbox = (_attr(player, keys[0]) + _attr(player, keys[1])) / 2.0
    if kid_arch == hole_arch:
        d = max(0.0, toolbox - 62) * 0.15
        if d >= 0.5:
            out.append((f"Built for the {hole_arch} role", round(d, 1)))
    elif {kid_arch, hole_arch} <= {"scorer", "playmaker"}:
        d = max(0.0, toolbox - 64) * 0.10
        if d >= 0.5:
            out.append(("Skill game translates to the hole", round(d, 1)))
    elif (kid_arch in ("checker", "shutdown")) != \
            (hole_arch in ("checker", "shutdown")):
        d = -max(1.0, (64 - toolbox) * 0.12)
        out.append(("Wrong role for the opening", round(d, 1)))


def situational_readiness(player: Any,
                          team: Any = None) -> Tuple[float, List]:
    """(score 0-100, breakdown [(label, delta), ...]).

    team: the NHL club (needs .roster for the opportunity leg, .staff for
    the coach leg, wins/losses for the situation leg). Without it, returns
    the base talent score with farm-trend and audition legs only.
    Every leg is defensive -- missing data just means no adjustment.
    """
    base = callup_readiness(player)
    deltas: List = []
    if getattr(player, "is_injured", False):
        return 0.0, [("Injured -- not an option", -round(base, 1))]
    grp = _pos_group(player)

    # 1. Opportunity: an injured regular at his position opens a door.
    if team is not None:
        try:
            holes = [p for p in (getattr(team, "roster", []) or [])
                     if getattr(p, "is_injured", False)
                     and _pos_group(p) == grp and p is not player]
            if holes:
                star = max(holes, key=_overall)
                star_ovr = _overall(star)
                kid_ovr = _overall(player)
                # How big is the void...
                hole = 3.0 + max(0.0, star_ovr - 70) * 0.35
                # ...and how much of it can THIS kid fill?
                gap = _clamp((kid_ovr - star_ovr + 10) / 14.0, 0.0, 1.0)
                d = hole * (0.45 + 0.55 * gap)
                name = getattr(star, "full_name",
                               getattr(star, "last_name", "A regular"))
                deltas.append(
                    (f"{_hole_tag(star_ovr)}: {name} out -- the door is open",
                     round(d, 1)))
                _moment_terms(player, star_ovr, team, deltas)
                _line_fit_terms(player, star, grp, deltas)
        except Exception:
            pass

    # 2. Coach fit: the right coach for THIS kid -- label plus the
    # continuous fit underneath it.
    if team is not None:
        try:
            import reputation_system as _rs
            coach = _rs._head_coach_of(team)
            if coach is not None:
                resp = _rs.player_coach_response(player, coach)
                label = resp.get("label", "")
                bump = {"Bought in": 5, "Tuning out": -5,
                        "Quit on coach": -10}.get(label, 0)
                fit = _rs.coach_player_fit(coach, player)
                total = bump + fit * 4.0
                if abs(total) >= 0.5:
                    deltas.append((f"Coach fit: {label}"
                                   + (f" ({fit:+.2f})" if fit else ""),
                                   round(total, 1)))
        except Exception:
            pass

    # 2b. Assistant coaches: specialists develop the kids at their position.
    # Deliberately modest -- the head coach is the main influence; a
    # franchise icon adds only a small edge (never unbalanced).
    if team is not None:
        try:
            import assistant_coaches as _ac
            for _alabel, _apts in _ac.assistant_development_deltas(player, team):
                deltas.append((_alabel, _apts))
        except Exception:
            pass


    # 3. Farm trend: the SLOPE of his production, not just up/down.
    try:
        hist = getattr(player, "farm_history", None) or []
        if len(hist) >= 2:
            if _is_goalie(player):
                now = float(hist[-1].get("sv_pct", 0) or 0)
                prev = float(hist[-2].get("sv_pct", 0) or 0)
                d = _clamp((now - prev) * 400.0, -6.0, 6.0)
                if abs(d) >= 0.5:
                    deltas.append(("Save % trending " +
                                   ("up" if d > 0 else "down"), round(d, 1)))
            else:
                now, prev = _nhle_of_season(hist[-1]), _nhle_of_season(hist[-2])
                d = _clamp((now - prev) * 40.0, -8.0, 8.0)
                if abs(d) >= 0.5:
                    deltas.append(("Production trending " +
                                   ("up" if d > 0 else "down"), round(d, 1)))
    except Exception:
        pass

    # 4. The fast channel: his live NHL audition. Production since the
    # call-up stamp moves the number within days -- step up for an injured
    # star and the old grade stops mattering. Younger kids making the jump
    # make a louder statement.
    try:
        aud = getattr(player, "nhl_audition", None)
        if isinstance(aud, dict):
            dgp = ((getattr(player, "games_played", 0) or 0)
                   - (aud.get("games_played", 0) or 0))
            dpts = ((getattr(player, "goals", 0) or 0)
                    + (getattr(player, "assists", 0) or 0)
                    - (aud.get("goals", 0) or 0)
                    - (aud.get("assists", 0) or 0))
            if dgp >= 3:
                ppg = dpts / dgp
                age = _attr(player, "age", 22)
                statement = 1.0 + max(0.0, 23 - age) * 0.10
                if ppg >= 0.60:
                    d = 10.0 * statement
                    deltas.append(("Showing he belongs", round(d, 1)))
                elif ppg >= 0.35:
                    deltas.append(("Holding his own", 6.0))
                elif dgp >= 6 and ppg < 0.15:
                    deltas.append(("Overmatched so far", -8.0))
                streak = int(_attr(player, "current_point_streak", 0))
                if streak >= 4 and ppg >= 0.35:
                    deltas.append(("Riding a heater", 2.0))
    except Exception:
        pass

    # 5. Room fit: the group he'd be joining.
    if team is not None:
        try:
            chem = _attr(player, "team_chemistry", 50)
            if chem >= 70:
                deltas.append(("Fits the room", 1.0))
            elif chem <= 35:
                deltas.append(("Room fit question", -1.5))
        except Exception:
            pass

    # Sanity: the moment can swing a kid a lot, but not into absurdity.
    total = sum(d for _, d in deltas)
    total = _clamp(total, -32.0, 32.0)
    score = _clamp(base + total, 0.0, 100.0)
    return round(score, 1), deltas
