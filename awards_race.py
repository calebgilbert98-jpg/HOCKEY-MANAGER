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


def _gp(p) -> int:
    return getattr(p, "games_played", 0) or 0


def _pts(p) -> int:
    return (getattr(p, "goals", 0) or 0) + (getattr(p, "assists", 0) or 0)


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
    return pos in ("D", "DEFENSE", "DEFENSEMAN", "DEFENCE", "DEFENCEMAN")


def _is_rookie(p) -> bool:
    return bool(getattr(p, "is_rookie", False))


def _sv_pct(p) -> float:
    sa = getattr(p, "shots_against", 0) or 0
    sv = getattr(p, "saves", 0) or 0
    return (sv / sa) if sa > 0 else 0.0


def _gaa(p) -> float:
    ga = (getattr(p, "shots_against", 0) or 0) - (getattr(p, "saves", 0) or 0)
    mins = getattr(p, "minutes_played", 0) or 0
    return (ga * 60 / mins) if mins > 0 else 99.0


def _team_points_pct(team) -> float:
    gp = getattr(team, "games_played", 0) or 0
    pts = getattr(team, "points", 0) or 0
    return (pts / (2 * gp)) if gp > 0 else 0.0


# ---------------------------------------------------------------------------
# Skater awards
# ---------------------------------------------------------------------------

def hart_race(players: List[Any], team_pct: Dict[str, float],
              min_gp: int = 20) -> List[Dict[str, Any]]:
    """Hart Trophy (MVP): points-driven with goals tiebreak + team success.

    Real history: the Hart goes to an elite scorer on a winning team.
    Score = points + 0.4*goals, multiplied by a team-success factor.
    """
    out = []
    for p in players:
        if _is_goalie(p) or _gp(p) < min_gp:
            continue
        pts = _pts(p)
        goals = getattr(p, "goals", 0) or 0
        team = getattr(p, "team_name", "") or ""
        pct = team_pct.get(team, 0.5)
        # Team factor: playoff-calibre teams (~.550+) get full credit,
        # lottery teams get discounted — mirrors real voting.
        team_factor = 0.75 + 0.5 * min(1.0, max(0.0, (pct - 0.400) / 0.250))
        score = (pts + 0.4 * goals) * team_factor
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
        out.append({"player": p, "score": _pts(p), "points": _pts(p),
                    "goals": getattr(p, "goals", 0) or 0,
                    "assists": getattr(p, "assists", 0) or 0})
    out.sort(key=lambda r: (r["score"], r["goals"]), reverse=True)
    return out


def rocket_race(players: List[Any], min_gp: int = 20) -> List[Dict[str, Any]]:
    """Rocket Richard Trophy: most goals. Pure goal-scoring title."""
    out = []
    for p in players:
        if _is_goalie(p) or _gp(p) < min_gp:
            continue
        out.append({"player": p, "score": getattr(p, "goals", 0) or 0,
                    "goals": getattr(p, "goals", 0) or 0,
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
        pm = getattr(p, "plus_minus", 0) or 0
        hits = getattr(p, "hits", 0) or 0
        blocks = getattr(p, "blocked_shots", 0) or 0
        score = pts * 2.0 + defense * 0.15 + pm * 0.3 + (hits + blocks) * 0.02
        out.append({"player": p, "score": score, "points": pts,
                    "goals": getattr(p, "goals", 0) or 0,
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
        takeaways = getattr(p, "takeaways", 0) or 0
        pm = getattr(p, "plus_minus", 0) or 0
        pts = _pts(p)
        score = (defense * 1.2 + fo * 0.5 + takeaways * 0.4
                 + pm * 0.8 + pts * 0.25)
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
        pim = getattr(p, "penalty_minutes", 0) or getattr(p, "penalties_in_minutes", 0) or 0
        if pts < 20:
            continue
        score = pts / (1.0 + pim / 12.0)
        out.append({"player": p, "score": score, "points": pts,
                    "pim": pim})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def calder_race(players: List[Any], min_gp: int = 10) -> List[Dict[str, Any]]:
    """Calder Trophy: rookie of the year. Points dominate for skaters."""
    out = []
    for p in players:
        if not _is_rookie(p) or _gp(p) < min_gp:
            continue
        if _is_goalie(p):
            # Rare but possible: rank goalies by SV% + wins
            sv = _sv_pct(p)
            w = getattr(p, "wins", 0) or 0
            score = sv * 100 + w * 0.8
            out.append({"player": p, "score": score, "points": None,
                        "sv_pct": sv, "wins": w, "goalie": True})
        else:
            pts = _pts(p)
            goals = getattr(p, "goals", 0) or 0
            score = pts + 0.3 * goals
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
        w = getattr(p, "wins", 0) or 0
        so = getattr(p, "shutouts", 0) or 0
        try:
            gsax = am.goalie_advanced(p).gsax if has_am else 0.0
        except Exception:
            gsax = 0.0
        # Elite SV% (~.920+) and low GAA (~2.30-) drive voting; wins matter.
        score = ((sv - 0.870) * 1000 * 2.0
                 + max(0.0, (3.50 - gaa)) * 12.0
                 + w * 0.7 + so * 1.5 + gsax * 0.8)
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

def rookie_skaters(players: List[Any], min_gp: int = 10) -> List[Dict[str, Any]]:
    """Rookie skater scoring leaders."""
    out = []
    for p in players:
        if not _is_rookie(p) or _is_goalie(p) or _gp(p) < min_gp:
            continue
        out.append({"player": p, "points": _pts(p),
                    "goals": getattr(p, "goals", 0) or 0,
                    "assists": getattr(p, "assists", 0) or 0,
                    "gp": _gp(p)})
    out.sort(key=lambda r: (r["points"], r["goals"]), reverse=True)
    return out


def rookie_goalies(players: List[Any], min_gp: int = 5) -> List[Dict[str, Any]]:
    """Rookie goaltender leaders, ranked by SV% then wins."""
    out = []
    for p in players:
        if not _is_rookie(p) or not _is_goalie(p) or _gp(p) < min_gp:
            continue
        out.append({"player": p, "sv_pct": _sv_pct(p), "gaa": _gaa(p),
                    "wins": getattr(p, "wins", 0) or 0,
                    "shutouts": getattr(p, "shutouts", 0) or 0,
                    "gp": _gp(p)})
    out.sort(key=lambda r: (r["sv_pct"], r["wins"]), reverse=True)
    return out


AWARD_DEFINITIONS = [
    ("Hart Memorial Trophy",
     "League MVP — voted by the PHWA. History: elite point production on a winning team.",
     "hart"),
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
