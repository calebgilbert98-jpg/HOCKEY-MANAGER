# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""NHL award races for Puck Dynasty.

Ranks candidates for each major NHL award using the criterion that
actually drives real-world voting, based on winner history:

- Hart (MVP): points dominate (last 20 winners all top-3 scorers),
  goals as tiebreak, playoff-team bonus.
- Art Ross: most points. Pure.
- Rocket Richard: most goals. Pure.
- Norris: defenseman points dominate modern voting
  (Karlsson 101, Josi 96, Makar 86 all won on offense first).
- Vezina: GMs vote on SV% + GAA + wins (Hellebuyck/Ullmark/Shesterkin
  pattern); GSAx shown as the modern analytical cross-check.
- Calder: rookie points dominate (Bedard, Celebrini, Kaprizov, Beniers).
- Selke: defensive forwards — defensive awareness, faceoffs, takeaways,
  plus/minus, two-way scoring (Bergeron/Barkov/Couturier pattern).
- Lady Byng: high points with minimal PIM (Kucherov/Fox/Slavin pattern).
- Jack Adams: biggest overachievement vs roster expectation.
- Jennings: fewest team goals against (goalie, 25+ GP) — team based.

All functions are pure queries over current season totals; no sim-engine
changes and no per-game cost.
"""

from typing import Any, Dict, List, Tuple

# ----------------------------------------------------------------------
# 3-star recognition (Item 8): season star counts feed award races.
# ----------------------------------------------------------------------
# Additive alongside the existing weights (nothing retuned): each player's
# race score gets a small percentage bump per weighted star (read through
# stars.weighted_star_count: 1st = 1.0, 2nd = 0.5, 3rd = 0.25). The
# percentage form keeps the term scale-agnostic across races (a Hart score
# ~140 and a Calder score ~70 get proportionally the same nudge).
STAR_RACE_SCORE_PCT = 0.004   # +0.4% of race score per weighted star
STAR_RACE_STAR_CAP = 20       # weighted stars beyond this add nothing
                              # (max bonus = 0.004 * 20 = +8% of score)


def _star_race_bonus(score: float, p: Any) -> float:
    """Additive star-count bump for an award-race score.

    Zero when the player has no season stars, so existing ordering is
    unchanged unless stars are present.
    """
    try:
        from stars import weighted_star_count as _wsc
        w = min(_wsc(p), STAR_RACE_STAR_CAP)
    except Exception:
        w = 0.0
    if w <= 0 or score <= 0:
        return 0.0
    return score * STAR_RACE_SCORE_PCT * w


def _stat(p: Any, *names: str) -> Any:
    """Season-stat read honoring the sim's real write path.

    The live sim writes season totals to ``p.stats.*`` (main.py,
    quick_sim fold); the flat Player attributes (``p.goals`` etc.) are
    only ever written by the never-called ``Player.add_game_stats``.
    Read ``p.stats`` first, fall back to the flat attribute so QA fakes
    and old saves that hand-set flat attrs keep working. Pure read-path
    fix: no weights, thresholds, or formulas change.
    """
    stats = getattr(p, "stats", None)
    for n in names:
        if stats is not None:
            v = getattr(stats, n, None)
            if v:
                return v
        v = getattr(p, n, None)
        if v:
            return v
    return 0


def _gp(p) -> int:
    return _stat(p, "games_played") or 0


def _pts(p) -> int:
    return (_stat(p, "goals") or 0) + (_stat(p, "assists") or 0)


def _pos_value(p) -> str:
    """Position as an uppercase code, handling enums and strings."""
    pos = getattr(p, "primary_position", None)
    if pos is None:
        pos = getattr(p, "position", "")
    val = getattr(pos, "value", pos)  # enums like PlayerPosition.DEFENSE -> "D"
    return str(val or "").upper()


def _is_goalie(p) -> bool:
    pos = _pos_value(p)
    return pos in ("G", "GOALIE", "GOALTENDER") or getattr(p, "is_goalie", False)


def _is_defenseman(p) -> bool:
    pos = _pos_value(p)
    return pos in ("D", "LD", "RD", "DEFENSE", "DEFENSEMAN", "DEFENCE",
                   "DEFENCEMAN")


def _is_rookie(p) -> bool:
    return bool(getattr(p, "is_rookie", False))


def calder_season_year(d) -> int:
    """September-year of the season containing date d.

    The Calder's September-15 age cutoff belongs to the season's START
    year: June 2027 awards judge the 2026-27 season (year 2026).
    """
    try:
        return int(d.year) if int(d.month) >= 9 else int(d.year) - 1
    except Exception:
        import datetime as _dt
        _td = _dt.date.today()
        return _td.year if _td.month >= 9 else _td.year - 1


def _migrate_prior_gp(p) -> List[int]:
    """Backfill prior_nhl_gp for saves that predate it.

    Old saves only kept the is_rookie flag. A flagged rookie was in his
    first NHL season (0 prior NHL GP) -- exact. For everyone else, use
    career NHL GP minus the current season: if that exceeds 25, the
    player must have had a disqualifying season (sentinel 999).
    """
    prior = getattr(p, "prior_nhl_gp", None)
    if isinstance(prior, list):
        return prior
    # Old save: only the is_rookie flag survived. A flagged rookie was in
    # his first NHL season (0 prior NHL GP) -- exact. Anyone else has
    # prior professional seasons of unknowable NHL GP; the conservative
    # call preserves the old behavior (non-rookies were never candidates).
    # Real per-season tracking takes over from here via reset_season_stats.
    prior = [] if getattr(p, "is_rookie", False) else [999]
    try:
        p.prior_nhl_gp = prior
    except Exception:
        pass
    return prior


def _calder_age_ok(p, season_year: int) -> bool:
    """26 or younger on September 15 of the season's start year.

    Turning 27 ON September 15 disqualifies (must not have attained the
    27th birthday by that date). Unparseable birth dates fail open.
    """
    try:
        bstr = (getattr(p, "birth_date", "") or "").strip()
        y, m, d = [int(x) for x in bstr.split("-")[:3]]
        return (y, m, d) > (season_year - 27, 9, 15)
    except Exception:
        return True


def calder_eligible(p, season_year: int = None) -> Tuple[bool, str]:
    """Centralized Calder Memorial Trophy eligibility.

    Real NHL rules, end to end:
    - Age: 26 or younger on September 15 of the season's start year.
    - Games: no more than 25 NHL games in any single preceding season,
      nor more than 6 NHL games in each of any two preceding seasons.
    - Only NHL games count: AHL time and European pro leagues (KHL, SHL,
      Liiga...) never disqualify -- a 24-year-old KHL veteran with 0 NHL
      games is a rookie here, as in real life.

    Returns (eligible, reason). The reason string explains the ruling
    for UI tooltips and the audit trail.
    """
    import datetime as _dt
    if season_year is None:
        _td = _dt.date.today()
        season_year = _td.year if _td.month >= 9 else _td.year - 1
    try:
        season_year = int(season_year)
    except Exception:
        return False, "no season year"

    if not _calder_age_ok(p, season_year):
        return False, "age: 27+ on September 15"
    prior = _migrate_prior_gp(p) or []
    try:
        if any(int(g or 0) > 25 for g in prior):
            return False, "played 25+ NHL games in a prior season"
        if sum(1 for g in prior if int(g or 0) > 6) >= 2:
            return False, "played 6+ NHL games in two prior seasons"
    except Exception:
        pass
    return True, "eligible rookie"


def _sv_pct(p) -> float:
    sa = _stat(p, "shots_against") or 0
    sv = _stat(p, "saves") or 0
    return (sv / sa) if sa > 0 else 0.0


def _gaa(p) -> float:
    ga = (_stat(p, "shots_against") or 0) - (_stat(p, "saves") or 0)
    mins = getattr(p, "minutes_played", 0) or 0
    if mins > 0:
        return ga * 60 / mins
    # minutes_played is never written in production, which used to make this
    # return 99.0 for every goalie (dead Vezina GAA term). Fall back to
    # goals-against per game, which keeps the term's 3.50 anchor valid.
    gp = _gp(p)
    return (ga / gp) if gp > 0 else 99.0


def _team_points_pct(team) -> float:
    gp = getattr(team, "games_played", 0) or 0
    pts = getattr(team, "points", 0) or 0
    return (pts / (2 * gp)) if gp > 0 else 0.0


# ---------------------------------------------------------------------------
# Skater awards
# ---------------------------------------------------------------------------

def roster_team_map(teams: List[Any]) -> Dict[int, str]:
    """Authoritative player -> team mapping from roster membership.

    Player.team_name is a convenience label that can go stale (trades,
    callups, old saves). The roster is the truth: if a player is in a
    team's roster list, that team is his team.
    """
    out: Dict[int, str] = {}
    for t in teams or []:
        try:
            tname = getattr(t, "team_name", "") or ""
            for p in list(getattr(t, "roster", []) or []):
                try:
                    out[int(getattr(p, "id", -1) or -1)] = tname
                except Exception:
                    continue
        except Exception:
            continue
    return out


def hart_race(players: List[Any], team_pct: Dict[str, float],
              min_gp: int = 20,
              roster_map: Dict[int, str] = None) -> List[Dict[str, Any]]:
    """Hart Trophy (MVP): points-driven with goals tiebreak + team success.

    Real history: the Hart goes to an elite scorer on a winning team.
    Score = points + 0.4*goals, multiplied by a team-success factor.

    Team-success weighting comes from the authoritative roster mapping
    (roster_map), not the player's team_name label, which can go stale
    after trades or in old saves.
    """
    out = []
    for p in players:
        if _is_goalie(p) or _gp(p) < min_gp:
            continue
        pts = _pts(p)
        goals = _stat(p, "goals") or 0
        try:
            pid = int(getattr(p, "id", -1) or -1)
        except Exception:
            pid = -1
        if roster_map is not None and pid in roster_map:
            team = roster_map[pid]
        else:
            team = getattr(p, "team_name", "") or ""
        pct = team_pct.get(team, 0.5)
        # Team factor: playoff-calibre teams (~.550+) get full credit,
        # lottery teams get discounted — mirrors real voting.
        team_factor = 0.75 + 0.5 * min(1.0, max(0.0, (pct - 0.400) / 0.250))
        score = (pts + 0.4 * goals) * team_factor
        score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
        out.append({"player": p, "score": score, "points": pts,
                    "goals": goals, "team_pct": pct})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def lindsay_race(players: List[Any], team_pct: Dict[str, float],
                 min_gp: int = 20,
                 roster_map: Dict[int, str] = None) -> List[Dict[str, Any]]:
    """Ted Lindsay Award: most outstanding player as voted by the players.

    Real history: the NHLPA vote tracks the Hart closely but with less
    team-success bias -- players respect pure individual brilliance even
    on losing teams (McDavid won it in 2017-18 while Edmonton missed
    the playoffs). Score = points + 0.5*goals with only a mild team
    factor, so it can diverge from the Hart on bad teams.
    """
    out = []
    for p in players:
        if _is_goalie(p) or _gp(p) < min_gp:
            continue
        pts = _pts(p)
        goals = _stat(p, "goals") or 0
        try:
            pid = int(getattr(p, "id", -1) or -1)
        except Exception:
            pid = -1
        if roster_map is not None and pid in roster_map:
            team = roster_map[pid]
        else:
            team = getattr(p, "team_name", "") or ""
        pct = team_pct.get(team, 0.5)
        # Players discount losing teams far less than writers do.
        team_factor = 0.90 + 0.20 * min(1.0, max(0.0, pct))
        score = (pts + 0.5 * goals) * team_factor
        score += _star_race_bonus(score, p)
        out.append({"player": p, "score": score, "points": pts,
                    "goals": goals, "team_pct": pct})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def art_ross_race(players: List[Any], min_gp: int = 20) -> List[Dict[str, Any]]:
    """Art Ross Trophy: most points. Pure scoring title."""
    out = []
    for p in players:
        if _is_goalie(p) or _gp(p) < min_gp:
            continue
        score = _pts(p)
        score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
        out.append({"player": p, "score": score, "points": _pts(p),
                    "goals": _stat(p, "goals") or 0,
                    "assists": _stat(p, "assists") or 0})
    out.sort(key=lambda r: (r["score"], r["goals"]), reverse=True)
    return out


def rocket_race(players: List[Any], min_gp: int = 20) -> List[Dict[str, Any]]:
    """Maurice "Rocket" Richard Trophy: most goals. Pure goal-scoring title."""
    out = []
    for p in players:
        if _is_goalie(p) or _gp(p) < min_gp:
            continue
        score = _stat(p, "goals") or 0
        score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
        out.append({"player": p, "score": score,
                    "goals": _stat(p, "goals") or 0,
                    "points": _pts(p)})
    out.sort(key=lambda r: (r["score"], r["points"]), reverse=True)
    return out


def norris_race(players: List[Any], min_gp: int = 20) -> List[Dict[str, Any]]:
    """Norris Trophy: best defenseman. Modern voting is offense-first.

    Score = points (dominant) + defensive contribution
    (defensive awareness + plus/minus + hits/blocks proxy).
    """
    out = []
    for p in players:
        if not _is_defenseman(p) or _gp(p) < min_gp:
            continue
        pts = _pts(p)
        defense = (getattr(p, "defensive_awareness", 50) or 50)
        pm = _stat(p, "plus_minus") or 0
        hits = _stat(p, "hits") or 0
        blocks = _stat(p, "blocked_shots") or 0
        score = pts * 2.0 + defense * 0.15 + pm * 0.3 + (hits + blocks) * 0.02
        score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
        out.append({"player": p, "score": score, "points": pts,
                    "goals": _stat(p, "goals") or 0,
                    "plus_minus": pm})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def selke_race(players: List[Any], min_gp: int = 20) -> List[Dict[str, Any]]:
    """Selke Trophy: best defensive forward.

    Bergeron/Barkov/Couturier pattern: elite defensive awareness,
    faceoff dominance, takeaways, strong plus/minus, two-way scoring.
    Forwards only.
    """
    out = []
    for p in players:
        if _is_goalie(p) or _is_defenseman(p) or _gp(p) < min_gp:
            continue
        defense = getattr(p, "defensive_awareness", 50) or 50
        fo = getattr(p, "faceoffs", 50) or 50
        takeaways = _stat(p, "takeaways") or 0
        pm = _stat(p, "plus_minus") or 0
        pts = _pts(p)
        score = (defense * 1.2 + fo * 0.5 + takeaways * 0.4
                 + pm * 0.8 + pts * 0.25)
        score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
        out.append({"player": p, "score": score, "points": pts,
                    "plus_minus": pm, "takeaways": takeaways,
                    "defense": defense})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def byng_race(players: List[Any], min_gp: int = 20) -> List[Dict[str, Any]]:
    """Lady Byng Trophy: skill + sportsmanship.

    Kucherov/Fox/Slavin pattern: elite production with minimal PIM.
    Score = points discounted steeply by penalty minutes.
    """
    out = []
    for p in players:
        if _is_goalie(p) or _gp(p) < min_gp:
            continue
        pts = _pts(p)
        pim = (_stat(p, "penalty_minutes", "penalties_in_minutes") or 0)
        if pts < 20:
            continue
        score = pts / (1.0 + pim / 12.0)
        score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
        out.append({"player": p, "score": score, "points": pts,
                    "pim": pim})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def calder_race(players: List[Any], min_gp: int = 10,
                season_year: int = None) -> List[Dict[str, Any]]:
    """Calder Trophy: rookie of the year. Points dominate for skaters.

    Eligibility is centralized in calder_eligible() (age + prior-games
    rules); pass the season's September-year for the age cutoff.
    """
    out = []
    for p in players:
        eligible, _reason = calder_eligible(p, season_year)
        if not eligible or _gp(p) < min_gp:
            continue
        if _is_goalie(p):
            # Rare but possible: rank goalies by SV% + wins
            sv = _sv_pct(p)
            w = _stat(p, "wins") or 0
            score = sv * 100 + w * 0.8
            score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
            out.append({"player": p, "score": score, "points": None,
                        "sv_pct": sv, "wins": w, "goalie": True})
        else:
            pts = _pts(p)
            goals = _stat(p, "goals") or 0
            score = pts + 0.3 * goals
            score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
            out.append({"player": p, "score": score, "points": pts,
                        "goals": goals, "goalie": False})
    # Skaters and goalies compete on separate scales; skaters first by
    # convention (a goalie only wins the Calder in exceptional years).
    skaters = sorted([r for r in out if not r.get("goalie")],
                     key=lambda r: r["score"], reverse=True)
    goalies = sorted([r for r in out if r.get("goalie")],
                     key=lambda r: r["score"], reverse=True)
    return skaters + goalies


# ---------------------------------------------------------------------------
# Goalie awards
# ---------------------------------------------------------------------------

def vezina_race(goalies: List[Any], min_gp: int = 15) -> List[Dict[str, Any]]:
    """Vezina Trophy: best goaltender.

    GMs vote on the SV% + GAA + wins profile (Hellebuyck/Ullmark/
    Shesterkin pattern). GSAx is shown as the modern cross-check.
    """
    try:
        import advanced_metrics as am
        has_am = True
    except Exception:
        has_am = False
    out = []
    for p in goalies:
        if _gp(p) < min_gp:
            continue
        sv = _sv_pct(p)
        gaa = _gaa(p)
        w = _stat(p, "wins") or 0
        so = _stat(p, "shutouts") or 0
        try:
            gsax = am.goalie_advanced(p).gsax if has_am else 0.0
        except Exception:
            gsax = 0.0
        # Elite SV% (~.920+) and low GAA (~2.30-) drive voting; wins matter.
        score = ((sv - 0.870) * 1000 * 2.0
                 + max(0.0, (3.50 - gaa)) * 12.0
                 + w * 0.7 + so * 1.5 + gsax * 0.8)
        score += _star_race_bonus(score, p)  # Item 8: 3-star recognition
        out.append({"player": p, "score": score, "sv_pct": sv, "gaa": gaa,
                    "wins": w, "shutouts": so, "gsax": gsax})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def jennings_race(teams: List[Any], min_goalie_gp: int = 25) -> List[Dict[str, Any]]:
    """Jennings Trophy: fewest team goals against (goalies with 25+ GP).

    Team-based award; lists the qualifying goalie tandem(s) on the
    stingiest teams.
    """
    out = []
    for t in teams:
        roster = list(getattr(t, "roster", []) or [])
        goalies = [p for p in roster if _is_goalie(p) and _gp(p) >= min_goalie_gp]
        if not goalies:
            continue
        ga = getattr(t, "goals_against", 0) or 0
        gp = getattr(t, "games_played", 0) or 1
        names = ", ".join(getattr(p, "full_name",
                                  getattr(p, "name", "?")) for p in goalies)
        out.append({"team": getattr(t, "team_name", "?"), "score": -ga,
                    "goals_against": ga, "ga_per_game": ga / gp,
                    "goalies": names})
    out.sort(key=lambda r: r["goals_against"])
    return out


# ---------------------------------------------------------------------------
# Coach award
# ---------------------------------------------------------------------------

def adams_race(teams: List[Any]) -> List[Dict[str, Any]]:
    """Jack Adams Award: coach of the most overachieving team.

    Compares actual points% against expectation from roster strength
    (average overall). Biggest positive surprise wins — the classic
    "did more with less" ballot.
    """
    out = []
    for t in teams:
        gp = getattr(t, "games_played", 0) or 0
        if gp < 10:
            continue
        roster = list(getattr(t, "roster", []) or [])
        skaters = [p for p in roster if not _is_goalie(p)]
        if not skaters:
            continue
        def _ovr(p):
            fn = getattr(p, "overall_rating", None)
            try:
                return float(fn()) if callable(fn) else float(fn or 75)
            except (TypeError, ValueError):
                return 75.0
        avg_ovr = sum(_ovr(p) for p in skaters) / len(skaters)
        # Expected points%: ~.300 at 70 OVR -> ~.650 at 90 OVR
        expected = 0.300 + (avg_ovr - 70) * 0.0175
        actual = _team_points_pct(t)
        over = actual - expected
        coach = getattr(t, "coach", None)
        coach_name = (getattr(coach, "full_name", None)
                      or getattr(coach, "name", None) or "Head Coach")
        out.append({"team": getattr(t, "team_name", "?"), "score": over,
                    "coach": coach_name, "actual_pct": actual,
                    "expected_pct": expected,
                    "points": getattr(t, "points", 0) or 0})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Rookie leaders
# ---------------------------------------------------------------------------

def rookie_skaters(players: List[Any], min_gp: int = 10,
                 season_year: int = None) -> List[Dict[str, Any]]:
    """Rookie skater scoring leaders (Calder-eligible only)."""
    out = []
    for p in players:
        eligible, _ = calder_eligible(p, season_year)
        if not eligible or _is_goalie(p) or _gp(p) < min_gp:
            continue
        out.append({"player": p, "points": _pts(p),
                    "goals": _stat(p, "goals") or 0,
                    "assists": _stat(p, "assists") or 0,
                    "gp": _gp(p)})
    out.sort(key=lambda r: (r["points"], r["goals"]), reverse=True)
    return out


def rookie_goalies(players: List[Any], min_gp: int = 5,
                 season_year: int = None) -> List[Dict[str, Any]]:
    """Rookie goaltender leaders, ranked by SV% then wins (Calder-eligible)."""
    out = []
    for p in players:
        eligible, _ = calder_eligible(p, season_year)
        if not eligible or not _is_goalie(p) or _gp(p) < min_gp:
            continue
        out.append({"player": p, "sv_pct": _sv_pct(p), "gaa": _gaa(p),
                    "wins": _stat(p, "wins") or 0,
                    "shutouts": _stat(p, "shutouts") or 0,
                    "gp": _gp(p)})
    out.sort(key=lambda r: (r["sv_pct"], r["wins"]), reverse=True)
    return out


AWARD_DEFINITIONS = [
    ("Hart Memorial Trophy",
     "League MVP — voted by the PHWA. History: elite point production on a winning team.",
     "hart"),
    ("Ted Lindsay Award",
     "Most outstanding player — voted by the NHLPA. Pure brilliance, less team bias than the Hart.",
     "ted_lindsay"),
    ("Art Ross Trophy",
     "Scoring champion — most points. Pure.",
     "art_ross"),
    ("Maurice \"Rocket\" Richard Trophy",
     "Goal-scoring champion — most goals. Pure.",
     "rocket"),
    ("James Norris Memorial Trophy",
     "Best defenseman — modern voting is offense-first: points dominate.",
     "norris"),
    ("Vezina Trophy",
     "Best goaltender — GMs vote the SV% + GAA + wins profile.",
     "vezina"),
    ("Calder Memorial Trophy",
     "Rookie of the year — rookie point production dominates.",
     "calder"),
    ("Frank J. Selke Trophy",
     "Best defensive forward — two-way dominance, faceoffs, takeaways.",
     "selke"),
    ("Lady Byng Memorial Trophy",
     "Sportsmanship + skill — elite points with minimal penalty minutes.",
     "byng"),
    ("Jack Adams Award",
     "Best coach — biggest overachievement vs roster expectation.",
     "adams"),
    ("William M. Jennings Trophy",
     "Fewest team goals against — qualifying goaltenders (25+ GP).",
     "jennings"),
]


# ---------------------------------------------------------------------------
# Awards voting simulation (for the Awards Ceremony hub)
# ---------------------------------------------------------------------------
# The race models decide the winners. These functions generate the *voting
# story* behind each result: who voted, how many ballots, and plausible
# vote totals conditioned on the official winner. Deterministic per
# (season_year, award) so re-opening the ceremony shows the same numbers.

# award key -> (voting body label, number of voters, ballot slots)
# None means the award is decided by pure statistics, not a vote.
VOTER_POOLS = {
    "hart":        ("PHWA writers", 178, 5),
    "ted_lindsay": ("NHLPA players", 712, 3),
    "norris":      ("PHWA writers", 178, 5),
    "vezina":      ("NHL general managers", 32, 3),
    "calder":      ("PHWA writers", 178, 5),
    "selke":       ("PHWA writers", 178, 5),
    "byng":        ("PHWA writers", 178, 5),
    "adams":       ("NHL broadcasters", 112, 3),
    "conn_smythe": ("PHWA writers", 18, 3),
    "rocket":      None,   # most goals -- pure stat
    "art_ross":    None,   # most points -- pure stat
    "jennings":    None,   # fewest team GA -- pure stat
}

# Classic NHL ballot points: 10-7-5-3-1 for a 5-slot ballot,
# 5-3-1 for a 3-slot ballot.
_BALLOT_POINTS = {5: (10, 7, 5, 3, 1), 3: (5, 3, 1)}


def simulate_voting(race, winner, award_key, season_year=0):
    """Generate a plausible voting story for an award result.

    ``race``: ranked list of {"player", "score", ...} entries.
    ``winner``: the official winner's player object (from the race).
    Returns a dict with:
      - voting_body: label or None for stat-decided awards
      - voters: number of ballots cast
      - results: list of {player, points, first_place, share} in order
      - winner_points / winner_first / winner_share for the headline
    Deterministic for a given (season_year, award_key).
    """
    pool = VOTER_POOLS.get(award_key)
    if pool is None:
        return {"voting_body": None, "voters": 0, "results": [],
                "winner_points": 0, "winner_first": 0, "winner_share": 0.0}
    body, n_voters, slots = pool
    import random
    rng = random.Random(hash(("awards_vote", int(season_year or 0),
                              award_key)) & 0xFFFFFFFF)

    # Candidate pool: top 8 by race score (writers/players/GMs only
    # seriously consider a handful of names).
    cands = [r for r in race if r.get("player") is not None][:8]
    if not cands:
        return {"voting_body": body, "voters": n_voters, "results": [],
                "winner_points": 0, "winner_first": 0, "winner_share": 0.0}
    # Ensure the official winner is in the candidate pool.
    wids = set()
    for r in cands:
        try:
            wids.add(int(getattr(r["player"], "id", -1) or -1))
        except Exception:
            pass
    try:
        wid = int(getattr(winner, "id", -1) or -1)
    except Exception:
        wid = -1
    if wid not in wids:
        cands = [{"player": winner, "score": max(
            (r.get("score", 0) for r in cands), default=1) * 1.1}] + cands[:7]

    # Base appeal from race score; the official winner gets a narrative
    # push so the simulated vote agrees with the official result.
    appeals = []
    top_score = max((float(r.get("score", 0) or 0) for r in cands), default=1.0)
    for r in cands:
        try:
            is_w = int(getattr(r["player"], "id", -1) or -1) == wid
        except Exception:
            is_w = False
        s = float(r.get("score", 0) or 0)
        appeal = 0.15 + 0.85 * (s / top_score if top_score else 0)
        if is_w:
            appeal *= 1.6  # the story the season told
        appeals.append(max(appeal, 0.05))

    points_for = [0] * len(cands)
    firsts_for = [0] * len(cands)
    pts_table = _BALLOT_POINTS[slots]
    for _ in range(n_voters):
        # Each voter ranks `slots` distinct candidates, weighted by
        # appeal with a dash of voter idiosyncrasy.
        weights = [a * rng.uniform(0.6, 1.4) for a in appeals]
        order = sorted(range(len(cands)),
                       key=lambda i: weights[i], reverse=True)[:slots]
        for rank, ci in enumerate(order):
            points_for[ci] += pts_table[rank]
            if rank == 0:
                firsts_for[ci] += 1

    # If noise produced an upset, rescale so the official winner still
    # tops the table (the race is authoritative; this is presentation).
    try:
        widx = next(i for i, r in enumerate(cands)
                    if int(getattr(r["player"], "id", -1) or -1) == wid)
    except StopIteration:
        widx = 0
    best = max(points_for)
    if points_for[widx] < best:
        points_for[widx] = best + rng.randint(1, max(1, n_voters // 20))
        firsts_for[widx] = max(firsts_for[widx],
                               max(firsts_for) + rng.randint(0, 3))

    total_pts = sum(points_for) or 1
    order = sorted(range(len(cands)),
                   key=lambda i: points_for[i], reverse=True)
    results = []
    for i in order:
        results.append({
            "player": cands[i]["player"],
            "points": points_for[i],
            "first_place": firsts_for[i],
            "share": points_for[i] / total_pts,
        })
    w = results[0]
    return {"voting_body": body, "voters": n_voters, "results": results,
            "winner_points": w["points"], "winner_first": w["first_place"],
            "winner_share": w["share"]}
