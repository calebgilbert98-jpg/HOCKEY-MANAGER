"""Immortality: turn accumulated data into history that argues with itself.

  - Retirement: the game had no retirement flow (players aged forever), so
    this module runs one minimal additive pass each offseason. Conservative
    probabilities; nobody gets cut mid-prime.
  - Hall of Fame voting: a 12-person committee, 75% to get in, max 4 per
    class. Borderline candidates spark debate; rejection-then-induction arcs
    are the best stories. Uses league_history.induct() -- the existing
    structure, finally called.
  - Retired numbers: criteria-gated, with a ceremony that has consequences
    (the building is electric and the room wants to win it for him).
  - Era arguments: "greatest team ever" as a debated case, not a plaque.
  - History integrity: nothing here invents a past -- every honor derives
    from recorded career totals and recorded seasons.

All defensive; all plain data (save-safe).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Retirement (minimal additive pass -- the game had no retirement flow)
# ---------------------------------------------------------------------------

def _is_goalie(player: Any) -> bool:
    try:
        pos = getattr(player, "primary_position", None)
        return "GOALIE" in str(getattr(pos, "name", pos or "")).upper()
    except Exception:
        return False


def _player_name(player: Any) -> str:
    try:
        return (getattr(player, "full_name", None)
                or getattr(player, "name", None) or "A player")
    except Exception:
        return "A player"


def retire_probability(age: int, goalie: bool) -> float:
    """Conservative: 36/38 starts the conversation, nobody is forced early."""
    base = 38 if goalie else 36
    if age < base:
        return 0.0
    return min(0.95, 0.12 + 0.14 * (age - base))


def snapshot_player(player: Any, team_name: str, year: int) -> Dict[str, Any]:
    """Freeze a career into plain data at retirement."""
    try:
        pos = getattr(player, "primary_position", None)
        pos_name = str(getattr(pos, "name", pos or ""))
    except Exception:
        pos_name = ""
    snap = {
        "player_id": getattr(player, "id", None),
        "name": _player_name(player),
        "position": pos_name,
        "goalie": _is_goalie(player),
        "team_name": team_name,
        "number": getattr(player, "jersey_number", None),
        "age": int(getattr(player, "age", 35) or 35),
        "retired_year": year,
        "games": int(getattr(player, "career_games", 0) or 0),
        "goals": int(getattr(player, "career_goals", 0) or 0),
        "assists": int(getattr(player, "career_assists", 0) or 0),
        "points": int(getattr(player, "career_points", 0) or 0),
        "wins": int(getattr(player, "career_wins", 0) or 0),
        "shutouts": int(getattr(player, "career_shutouts", 0) or 0),
        "cups": int(getattr(player, "stanley_cups", 0) or 0),
        "awards": list(getattr(player, "awards_won", None) or []),
        "ballot_years": 0,
        "inducted": False,
    }
    return snap


def process_retirements(league: Any, year: int) -> List[Dict[str, Any]]:
    """One offseason pass. Returns snapshots of the players who hung them up.

    Removed from rosters into league.retired_players (plain data). Never
    touches anyone under the age line; probabilities are conservative.
    """
    retired: List[Dict[str, Any]] = []
    try:
        teams = getattr(league, "teams", None) or []
    except Exception:
        return retired
    if not isinstance(getattr(league, "retired_players", None), list):
        try:
            league.retired_players = []
        except Exception:
            return retired
    for team in teams:
        try:
            roster = list(getattr(team, "roster", None) or [])
            team_name = getattr(team, "team_name", "")
        except Exception:
            continue
        for player in roster:
            try:
                age = int(getattr(player, "age", 0) or 0)
                goalie = _is_goalie(player)
                if random.random() < retire_probability(age, goalie):
                    snap = snapshot_player(player, team_name, year)
                    league.retired_players.append(snap)
                    team.roster.remove(player)
                    retired.append(snap)
            except Exception:
                continue
    return retired


# ---------------------------------------------------------------------------
# Career score + HOF voting
# ---------------------------------------------------------------------------

def career_score(snap: Dict[str, Any]) -> float:
    """0-100: how immortal was this career? Cups and awards weigh heavily."""
    try:
        if snap.get("goalie"):
            s = (snap.get("wins", 0) / 300.0 * 45.0
                 + snap.get("shutouts", 0) / 60.0 * 10.0
                 + snap.get("games", 0) / 800.0 * 10.0)
        else:
            s = (snap.get("points", 0) / 1200.0 * 45.0
                 + snap.get("goals", 0) / 500.0 * 10.0
                 + snap.get("games", 0) / 1400.0 * 10.0)
        s += min(20.0, snap.get("cups", 0) * 7.0)
        s += min(15.0, len(snap.get("awards", [])) * 5.0)
        return round(max(0.0, min(100.0, s)), 1)
    except Exception:
        return 0.0


COMMITTEE_SIZE = 12
VOTES_REQUIRED = 9
CLASS_CAP = 4
BALLOT_WAIT_YEARS = 3


def hof_ballot(league: Any, history: Any, year: int) -> Dict[str, Any]:
    """Run one offseason Hall of Fame vote.

    Candidates: retired 3+ years, not yet inducted. 12 voters, 75% required,
    class capped at 4 (top vote-getters). 7-8 votes = borderline debate, stays
    on the ballot. Returns {inducted: [...], borderline: [...], waiting: n}.
    """
    report: Dict[str, Any] = {"inducted": [], "borderline": [],
                              "waiting": 0, "candidates": 0}
    try:
        retired = getattr(league, "retired_players", None) or []
        inducted_names = {h.get("name") for h in
                          (getattr(history, "hall_of_fame", None) or [])}
    except Exception:
        return report

    candidates = []
    for snap in retired:
        try:
            if snap.get("inducted") or snap.get("name") in inducted_names:
                continue
            if year - int(snap.get("retired_year", year)) < BALLOT_WAIT_YEARS:
                report["waiting"] += 1
                continue
            snap["ballot_years"] = int(snap.get("ballot_years", 0) or 0) + 1
            candidates.append(snap)
        except Exception:
            continue
    report["candidates"] = len(candidates)

    voted: List[Tuple[int, Dict[str, Any]]] = []
    for snap in candidates:
        try:
            score = career_score(snap)
            # Committee: yes if the career clears ~55, with human noise.
            # Legends are unanimous; compiler-types split the room.
            votes = sum(1 for _ in range(COMMITTEE_SIZE)
                        if score + random.uniform(-9, 9) >= 55.0)
            voted.append((votes, snap))
        except Exception:
            continue
    voted.sort(key=lambda v: -v[0])

    for votes, snap in voted[:CLASS_CAP]:
        try:
            if votes >= VOTES_REQUIRED:
                rec = history.induct(_snap_player_proxy(snap), year) \
                    if hasattr(history, "induct") else None
                snap["inducted"] = True
                report["inducted"].append({
                    "name": snap["name"], "votes": votes,
                    "score": career_score(snap),
                    "ballot_years": snap.get("ballot_years", 1),
                    "record": rec,
                })
            elif votes >= 7:
                report["borderline"].append({
                    "name": snap["name"], "votes": votes,
                    "score": career_score(snap),
                    "ballot_years": snap.get("ballot_years", 1),
                })
        except Exception:
            continue
    return report


class _SnapPlayer:
    """Thin proxy so history.induct() can read a snapshot like a player."""
    def __init__(self, snap: Dict[str, Any]):
        self._s = snap
        self.full_name = snap.get("name", "")
        self.team_name = snap.get("team_name", "")
        self.stanley_cups = snap.get("cups", 0)
        self.awards_won = list(snap.get("awards", []) or [])
        self.teams_played_for = [snap.get("team_name", "")]
        self.primary_position = snap.get("position", "")
        self.career_stats = {
            "games_played": snap.get("games", 0),
            "goals": snap.get("goals", 0),
            "assists": snap.get("assists", 0),
            "points": snap.get("points", 0),
            "wins": snap.get("wins", 0),
            "shutouts": snap.get("shutouts", 0),
        }

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._s.get(name)


def _snap_player_proxy(snap: Dict[str, Any]) -> _SnapPlayer:
    return _SnapPlayer(snap)


# ---------------------------------------------------------------------------
# Retired numbers
# ---------------------------------------------------------------------------

def retired_numbers(team: Any) -> List[Dict[str, Any]]:
    try:
        rn = getattr(team, "retired_numbers", None)
        if not isinstance(rn, list):
            rn = []
            team.retired_numbers = rn
        return rn
    except Exception:
        return []


def is_number_retired(team: Any, number: Any) -> bool:
    try:
        return any(r.get("number") == number for r in retired_numbers(team))
    except Exception:
        return False


def number_worthy(snap: Dict[str, Any]) -> bool:
    """Criteria: a career score that says franchise icon, plus staying power
    (800 games), a Cup, or individual hardware. One honor per career."""
    try:
        if career_score(snap) < 65.0:
            return False
        return (snap.get("games", 0) >= 800
                or snap.get("cups", 0) >= 1
                or len(snap.get("awards", [])) >= 1)
    except Exception:
        return False


def retire_number(team: Any, snap: Dict[str, Any], year: int) -> bool:
    """Hang a number. Schedules the ceremony for the next home game."""
    try:
        number = snap.get("number")
        if number is None or is_number_retired(team, number):
            return False
        retired_numbers(team).append({
            "number": number,
            "player": snap.get("name", ""),
            "year": year,
        })
        schedule_ceremony(team, "jersey_retirement",
                          player=snap.get("name", ""),
                          number=number)
        return True
    except Exception:
        return False


def assign_jersey_number(team: Any, player: Any,
                         taken: Optional[set] = None) -> int:
    """Pick a number that isn't retired by this team (or already taken)."""
    try:
        retired = {r.get("number") for r in retired_numbers(team)}
        used = set(taken or [])
        try:
            used.update(getattr(p, "jersey_number", None)
                        for p in (getattr(team, "roster", None) or []))
        except Exception:
            pass
        pool = [n for n in range(1, 99) if n not in retired and n not in used]
        number = random.choice(pool) if pool else random.randint(1, 98)
        player.jersey_number = number
        return number
    except Exception:
        return int(getattr(player, "jersey_number", 0) or 0)


# ---------------------------------------------------------------------------
# Ceremonies (with consequences)
# ---------------------------------------------------------------------------

def schedule_ceremony(team: Any, kind: str, **info: Any) -> None:
    """Queue a pregame ceremony for the team's next home game."""
    try:
        team._pending_ceremony = {"kind": kind, "info": dict(info)}
    except Exception:
        pass


def consume_ceremony(app: Any, home_team: Any, sim: Any = None) -> bool:
    """Run tonight's ceremony: crowd is electric (via atmosphere), and the
    room wants to win it for him -- a small one-game home finishing bump.
    Bounded: 1.02 for one game, then it's gone. Returns True when consumed.
    """
    try:
        cer = getattr(home_team, "_pending_ceremony", None)
        if not isinstance(cer, dict):
            return False
        home_team._pending_ceremony = None
        kind = cer.get("kind", "")
        info = cer.get("info", {}) or {}
        if kind == "jersey_retirement":
            line = (f"Pregame ceremony: {home_team.team_name} raise "
                    f"{info.get('player', 'a legend')}'s "
                    f"No. {info.get('number', '')} to the rafters.")
        elif kind == "hof_induction":
            line = (f"Pregame ceremony: {info.get('player', 'a legend')} "
                    f"celebrates Hall of Fame induction at "
                    f"{home_team.team_name}.")
        else:
            line = f"Pregame ceremony at {home_team.team_name}."
        try:
            app.add_news(line + " The building is electric -- the room "
                                "wants to win this one for him.")
        except Exception:
            pass
        # The consequence, bounded: +2% finishing for the home side tonight.
        try:
            if sim is not None:
                tb = getattr(sim, "team_boost", None)
                if isinstance(tb, dict):
                    hn = home_team.team_name
                    tb[hn] = max(0.9, min(1.1, tb.get(hn, 1.0) * 1.02))
        except Exception:
            pass
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Era arguments: "greatest team ever" as a debated case
# ---------------------------------------------------------------------------

def greatness_score(season_record: Dict[str, Any]) -> float:
    """0-100 from recorded facts only: regular-season dominance + playoff run."""
    try:
        score = 0.0
        standings = season_record.get("standings") or []
        champ = season_record.get("champion", "")
        for row in standings:
            name = row.get("team") or row.get("name") or ""
            if name == champ:
                pts = float(row.get("points", row.get("pts", 0)) or 0)
                gf = float(row.get("gf", row.get("goals_for", 0)) or 0)
                ga = float(row.get("ga", row.get("goals_against", 0)) or 0)
                score += min(55.0, pts / 130.0 * 55.0)
                score += min(25.0, max(0.0, (gf - ga)) / 100.0 * 25.0)
                break
        # Playoff dominance: sweeps > sevens.
        series = str(season_record.get("series_score", "") or "")
        try:
            w, l = series.split("-")
            total = int(w) + int(l)
            if total > 0:
                score += min(20.0, (int(w) / total) * 20.0)
        except Exception:
            score += 10.0
        return round(max(0.0, min(100.0, score)), 1)
    except Exception:
        return 0.0


def era_argument(history: Any) -> Optional[Dict[str, Any]]:
    """The new champion vs the best ever: coronation or genuine debate.

    Fires only when there's something to argue about: the new champion sets
    a new best (coronation), or lands within 8 points of it (debate). A
    champion 20 points off the pace gets no argument -- history is honest.
    """
    try:
        champs = history.champions_list() if history is not None else []
        if len(champs) < 2:
            return None
        newest = champs[0]
        past = champs[1:]
        new_score = greatness_score(newest)
        best = max(past, key=greatness_score)
        best_score = greatness_score(best)
        gap = new_score - best_score
        if gap > 0:
            return {"verdict": "coronation", "gap": round(gap, 1),
                    "new": newest, "new_score": new_score,
                    "best": best, "best_score": best_score}
        if gap >= -8.0:
            return {"verdict": "debate", "gap": round(gap, 1),
                    "new": newest, "new_score": new_score,
                    "best": best, "best_score": best_score}
        return None
    except Exception:
        return None


def era_argument_news(arg: Dict[str, Any]) -> str:
    """Two sides, one paragraph each -- the disagreement is the story."""
    try:
        new = arg["new"]
        best = arg["best"]
        nc = new.get("champion", "The champions")
        ny = new.get("year", "")
        bc = best.get("champion", "a past champion")
        by = best.get("year", "")
        if arg["verdict"] == "coronation":
            return (f"Greatest team ever? The bar just moved. {nc} ({ny}) "
                    f"post a greatness mark of {arg['new_score']} -- past "
                    f"{bc} ({by}) at {arg['best_score']}. The old guard says "
                    f"eras can't be compared; the numbers say they just were.")
        return (f"Greatest team ever? It's a real argument now. {nc} ({ny}) "
                f"grade at {arg['new_score']}, a whisper behind {bc} ({by}) "
                f"at {arg['best_score']}. One side says rings are rings; the "
                f"other says dominance is dominance. Settle it how you like.")
    except Exception:
        return ""
