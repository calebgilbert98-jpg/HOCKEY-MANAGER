"""Coach season-record histories (head coaches AND assistants).

Every season, at rollover, each coaching-staff member gets one plain-dict
entry appended to ``staff.career_record``::

    {"season": "2025-26", "team": "Edmonton Oilers", "role": "Assistant Coach",
     "w": 48, "l": 26, "otl": 8, "playoff": "Won Stanley Cup",
     "jack_adams": False}

The staff card's "Record" tab renders this year-by-year, with career totals
and a trophy-case line -- the hiring/firing evidence Muck asked for.

Design notes (Sports Interactive veteran read):
- Assistants get entries too, with their own role stamped. A great power-play
  coach's record travels with him, not with the head coach he served under.
- Entries are plain dicts (save/load safe, same convention as
  Player.career_moments / career_accolades).
- Cap at 40 entries (a 40-year coaching career) -- cheap, bounded.
- Playoff result strings mirror what the history viewer shows for seasons.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Roles that earn a yearly record entry. Head coach plus every assistant
# specialty -- the staff card "Record" tab appears for all of these.
COACHING_ROLE_NAMES = {
    "Head Coach",
    "Assistant Coach",
    "Associate Coach",
    "Goalie Coach",
    "Power Play Coach",
    "Penalty Kill Coach",
}

MAX_RECORD_ENTRIES = 40


def is_coaching_role(staff: Any) -> bool:
    """True for head coaches and all assistant/specialty coaches."""
    try:
        role = getattr(staff, "role", None)
        name = str(getattr(role, "value", role) or "")
        return name in COACHING_ROLE_NAMES
    except Exception:
        return False


def role_display_name(staff: Any) -> str:
    role = getattr(staff, "role", None)
    return str(getattr(role, "value", role) or "Coach")


def season_label(season_year: int) -> str:
    """'2025-26' style label from the league's starting year."""
    return f"{season_year}-{str(season_year + 1)[2:]}"


def playoff_result_for_team(team: Any, bracket: Any,
                            champion: Any) -> str:
    """Best human-readable playoff result for one team from the bracket.

    Walks every series; the team's deepest round decides. Falls back to
    "Missed playoffs" when the team appears in no series.
    """
    try:
        if champion is not None and getattr(team, "id", None) == getattr(
                champion, "id", None):
            return "Won Stanley Cup"
        series_lists = []
        pbs = getattr(bracket, "playoff_series", None) or {}
        if isinstance(pbs, dict):
            for lst in pbs.values():
                series_lists.extend(lst or [])
        elif isinstance(pbs, (list, tuple)):
            series_lists.extend(pbs)
        best_round = ""
        best_depth = -1
        # Depth order mirrors the real playoff tree.
        depth = {"Wild Card Round": 0, "Division Semifinals": 1,
                 "Division Finals": 2, "Stanley Cup Final": 3}
        tid = getattr(team, "id", None)
        for s in series_lists:
            t1 = getattr(s, "team1", None)
            t2 = getattr(s, "team2", None)
            if tid not in (getattr(t1, "id", None), getattr(t2, "id", None)):
                continue
            if not getattr(s, "is_complete", False):
                continue
            rnd = str(getattr(s, "name", "") or "")
            d = depth.get(rnd, -1)
            if d > best_depth:
                best_depth = d
                best_round = rnd
        if best_depth < 0:
            return "Missed playoffs"
        if best_round == "Stanley Cup Final":
            return "Lost Stanley Cup Final"
        return f"Lost {best_round}" if best_round else "Lost playoffs"
    except Exception:
        return "Missed playoffs"


def record_staff_season(staff: Any, season: str, team_name: str,
                        w: int, l: int, otl: int, playoff: str,
                        jack_adams: bool = False) -> Dict[str, Any]:
    """Append one season entry to a coach's career_record. Idempotent per
    (season, team): if an entry for this season+team already exists it is
    updated in place rather than duplicated."""
    rec = getattr(staff, "career_record", None)
    if not isinstance(rec, list):
        rec = []
        try:
            staff.career_record = rec
        except Exception:
            return {}
    entry = {"season": season, "team": team_name,
             "role": role_display_name(staff),
             "w": int(w or 0), "l": int(l or 0), "otl": int(otl or 0),
             "playoff": playoff or "Missed playoffs",
             "jack_adams": bool(jack_adams)}
    for i, old in enumerate(rec):
        if (isinstance(old, dict) and old.get("season") == season
                and old.get("team") == team_name):
            rec[i] = entry
            return entry
    rec.append(entry)
    del rec[:-MAX_RECORD_ENTRIES]
    return entry


def career_totals(record: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate W/L/OTL, Cups, and Jack Adams wins from a career record."""
    t = {"w": 0, "l": 0, "otl": 0, "seasons": 0, "cups": 0, "adams": 0}
    for e in record or []:
        if not isinstance(e, dict):
            continue
        t["seasons"] += 1
        t["w"] += int(e.get("w", 0) or 0)
        t["l"] += int(e.get("l", 0) or 0)
        t["otl"] += int(e.get("otl", 0) or 0)
        if e.get("playoff") == "Won Stanley Cup":
            t["cups"] += 1
        if e.get("jack_adams"):
            t["adams"] += 1
    gp = t["w"] + t["l"] + t["otl"]
    t["win_pct"] = round(t["w"] / gp, 3) if gp else 0.0
    return t


def find_coach(teams: List[Any], coach_name: str,
               team_name: str) -> Optional[Any]:
    """Match a Jack Adams winner (name + team) to a Staff object.

    Prefers an exact full_name match on the winning team's coaching staff;
    falls back to team.coach, then to a league-wide name match.
    """
    want = (coach_name or "").strip().lower()
    if not want:
        return None
    match_team = None
    for t in teams or []:
        if str(getattr(t, "team_name", "") or "").strip().lower() == (
                team_name or "").strip().lower():
            match_team = t
            break
    search_teams = [match_team] if match_team is not None else list(teams or [])
    fallback = None
    for t in search_teams:
        staff_list = [s for s in list(getattr(t, "staff", None) or [])
                      if is_coaching_role(s)]
        for s in staff_list:
            nm = str(getattr(s, "full_name", "") or "").strip().lower()
            if nm == want:
                return s
            if fallback is None:
                fallback = s
        coach = getattr(t, "coach", None)
        if coach is not None and str(
                getattr(coach, "full_name", "") or "").strip().lower() == want:
            return coach
    # Exact name match failed: prefer the winning team's head coach, else the
    # first coaching staffer found, so the Adams always lands on a person.
    if match_team is not None:
        coach = getattr(match_team, "coach", None)
        if coach is not None and is_coaching_role(coach):
            return coach
    return fallback
