"""
CSV roster import for Puck Dynasty.

A simple, documented alternative to the EHM database.db importer: describe
teams and players in two CSV files and start a career with them.  Useful for
hand-built rosters, or for data converted from other sources (e.g. an EHM
Editor spreadsheet export remapped to these columns).

File formats
------------
teams.csv — one row per team::

    team_name,city,division,conference,league

players.csv — one row per player.  Only the name columns are required;
everything else falls back to sensible defaults::

    first_name,last_name,team,position,age,nationality,height,weight,
    handedness,jersey_number,salary,contract_years,potential,
    skating,shooting,passing,deking,offensive_awareness,
    defensive_awareness,checking,faceoffs,strength,goaltending,
    determination,leadership,discipline

* ``team`` matches a ``team_name`` from teams.csv (blank = free agent).
* ``position`` is one of C, LW, RW, LD, RD, D, G (case-insensitive).
* Attributes are Puck Dynasty's internal ~50 scale (roughly 1-60).
* ``height`` may be like ``6'1"`` or centimetres; ``weight`` in lbs.

Use :func:`write_templates` to generate starter files with an example row.
"""

from __future__ import annotations

import csv
import os
import random
from typing import Any, Dict, List, Optional, Tuple

TEAM_HEADERS = ["team_name", "city", "division", "conference", "league"]

PLAYER_HEADERS = [
    "first_name", "last_name", "team", "position", "age", "nationality",
    "height", "weight", "handedness", "jersey_number", "salary",
    "contract_years", "potential",
    # core attributes (internal ~50 scale)
    "skating", "shooting", "passing", "deking", "offensive_awareness",
    "defensive_awareness", "checking", "faceoffs", "strength",
    "goaltending",
    # extended attributes (optional)
    "stickhandling", "vision", "shooting_accuracy", "shooting_power",
    "wristshot", "slapshot", "pokecheck", "bodycheck", "deflections",
    "acceleration", "agility", "speed", "stamina", "balance", "endurance",
    "anticipation", "decision_making", "hockey_iq", "creativity",
    "work_rate", "composure", "determination", "teamwork", "leadership",
    "discipline", "flair", "consistency", "important_matches",
    "reflexes", "positioning", "rebound_control", "glove_hand",
    "stick_side", "breakaway_skill",
]

_EXAMPLE_TEAMS = [
    ["Boston Bruins", "Boston", "Atlantic", "Eastern",
     "National Hockey League"],
    ["Toronto Maple Leafs", "Toronto", "Atlantic", "Eastern",
     "National Hockey League"],
]

_EXAMPLE_PLAYERS = [
    ["David", "Pastrnak", "Boston Bruins", "RW", "30", "Czechia",
     "6'0\"", "195", "Right", "88", "11250000", "4", "16",
     "46", "48", "44", "46", "47", "38", "36", "30", "40", "20",
     "40", "38", "44", "42", "40", "42", "46", "44", "42", "45",
     "43", "44", "42", "45", "44", "46", "42", "44", "40", "42",
     "44", "45", "46", "42", "44", "40", "20", "20", "20", "20",
     "20"],
    ["Auston", "Matthews", "Toronto Maple Leafs", "C", "29", "USA",
     "6'3\"", "215", "Left", "34", "13250000", "3", "17",
     "45", "49", "45", "45", "48", "40", "38", "42", "42", "20",
     "42", "40", "45", "43", "42", "44", "48", "45", "43", "44",
     "44", "45", "43", "46", "45", "47", "43", "45", "42", "44",
     "46", "44", "45", "42", "43", "20", "20", "20", "20", "20"],
]


def write_templates(directory: str) -> Tuple[str, str]:
    """Write blank teams.csv / players.csv templates with example rows.

    Returns the two file paths.
    """
    os.makedirs(directory, exist_ok=True)
    teams_path = os.path.join(directory, "teams.csv")
    players_path = os.path.join(directory, "players.csv")
    with open(teams_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(TEAM_HEADERS)
        w.writerows(_EXAMPLE_TEAMS)
    with open(players_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(PLAYER_HEADERS)
        w.writerows(_EXAMPLE_PLAYERS)
    return teams_path, players_path


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError, AttributeError):
        return default


def _norm_pos(value: Any) -> str:
    s = str(value or "").strip().upper()
    aliases = {"CENTRE": "C", "CENTER": "C", "LEFTWING": "LW",
               "RIGHTWING": "RW", "LEFTDEFENSE": "LD", "LEFTDEFENCE": "LD",
               "RIGHTDEFENSE": "RD", "RIGHTDEFENCE": "RD", "DEFENSE": "D",
               "DEFENCE": "D", "GOALKEEPER": "G", "GOALIE": "G", "NETMINDER": "G"}
    s = aliases.get(s.replace(" ", "").replace("-", ""), s)
    return s if s in ("C", "LW", "RW", "LD", "RD", "D", "G") else "C"


def _norm_height(value: Any) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    s = str(value).strip()
    if "'" in s:
        return s
    try:
        total_in = float(s) / 2.54
        feet = int(total_in // 12)
        inches = int(round(total_in % 12))
        return f"{feet}'{inches}\""
    except ValueError:
        return s


def import_league_from_csv(teams_path: str, players_path: str,
                           season_year: Optional[int] = None):
    """Build a Puck Dynasty League from teams.csv + players.csv.

    Returns (League, stats dict).  Raises ValueError on bad input.
    """
    from datetime import date
    from game_classes import League, Player, PlayerPosition

    for p, label in ((teams_path, "teams.csv"), (players_path, "players.csv")):
        if not p or not os.path.isfile(p):
            raise ValueError(f"{label} not found: {p}")

    with open(teams_path, newline="", encoding="utf-8-sig") as fh:
        team_rows = list(csv.DictReader(fh))
    with open(players_path, newline="", encoding="utf-8-sig") as fh:
        player_rows = list(csv.DictReader(fh))

    if not team_rows:
        raise ValueError("teams.csv contains no teams.")

    league = League("Imported CSV Rosters")
    league.season_year = season_year or date.today().year
    # Replace the template NHL teams with the CSV's teams.
    league.teams.clear()
    league.standings.clear()
    teams_by_name: Dict[str, Any] = {}
    for tr in team_rows:
        name = (tr.get("team_name") or "").strip()
        if not name:
            continue
        from game_classes import Team
        team = Team(
            team_name=name,
            city=(tr.get("city") or "").strip() or "Unknown",
            division=(tr.get("division") or "").strip() or "Imported",
            conference=(tr.get("conference") or "").strip() or "Imported",
        )
        if (tr.get("league") or "").strip():
            team.league_name = tr["league"].strip()
        league.teams.append(team)
        teams_by_name[name.lower()] = team

    stats = {"players": 0, "free_agents": 0, "skipped": 0,
             "teams": len(teams_by_name)}
    league.free_agents = []
    for pr in player_rows:
        fn = (pr.get("first_name") or "").strip()
        ln = (pr.get("last_name") or "").strip()
        if not fn or not ln:
            stats["skipped"] += 1
            continue
        try:
            pos = PlayerPosition(_norm_pos(pr.get("position")))
        except ValueError:
            pos = PlayerPosition.CENTER
        p = Player(first_name=fn, last_name=ln,
                   age=_to_int(pr.get("age"), 24),
                   primary_position=pos)
        # attributes
        for attr in PLAYER_HEADERS[13:]:
            raw = (pr.get(attr) or "").strip()
            if raw == "":
                continue
            try:
                setattr(p, attr,
                        max(1, min(99, _to_int(raw, 30))))
            except AttributeError:
                pass
        if (pr.get("nationality") or "").strip():
            p.nationality = pr["nationality"].strip()
        h = _norm_height(pr.get("height"))
        if h:
            p.height = h
        if (pr.get("weight") or "").strip():
            p.weight = max(120, min(320, _to_int(pr.get("weight"), 190)))
        if (pr.get("handedness") or "").strip().lower().startswith("l"):
            p.handedness = "Left"
        elif (pr.get("handedness") or "").strip().lower().startswith("r"):
            p.handedness = "Right"
        if (pr.get("jersey_number") or "").strip():
            num = _to_int(pr.get("jersey_number"), p.jersey_number)
            if 1 <= num <= 98:
                p.jersey_number = num
        if (pr.get("salary") or "").strip():
            p.contract.salary = max(0, _to_int(pr.get("salary"), 750000))
        if (pr.get("contract_years") or "").strip():
            p.contract.years_remaining = max(
                0, _to_int(pr.get("contract_years"), 1))
        if (pr.get("potential") or "").strip():
            pot = max(1, min(20, _to_int(pr.get("potential"), 12)))
            p.potential = pot
            p.potential_grade = ("A" if pot >= 17 else "B" if pot >= 14
                                 else "C" if pot >= 11 else
                                 "D" if pot >= 8 else "F")
        team = teams_by_name.get((pr.get("team") or "").strip().lower())
        if team is not None:
            team.add_player(p, "roster")
        else:
            league.free_agents.append(p)
            p.team_name = "Free Agent"
            stats["free_agents"] += 1
        stats["players"] += 1

    # Squad statuses per team.
    for team in league.teams:
        skaters = sorted(
            (pl for pl in team.roster
             if pl.primary_position != PlayerPosition.GOALIE),
            key=lambda pl: pl.overall_rating(), reverse=True)
        for i, pl in enumerate(skaters):
            if i < 3:
                pl.squad_status = "Star Player"
            elif i < 9:
                pl.squad_status = "Key Player"
            elif i < 15:
                pl.squad_status = "Regular Starter"
    league.initialize_standings()
    return league, stats


def preview_csv(players_path: str, limit: int = 8) -> List[Dict[str, str]]:
    """Return the first ``limit`` player rows for wizard previews."""
    if not players_path or not os.path.isfile(players_path):
        return []
    with open(players_path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows[:limit]:
        out.append({
            "name": f"{(r.get('first_name') or '').strip()} "
                    f"{(r.get('last_name') or '').strip()}".strip(),
            "team": (r.get("team") or "").strip() or "Free Agent",
            "pos": _norm_pos(r.get("position")),
            "age": (r.get("age") or "").strip() or "?",
        })
    return out
