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
    # Individual awards for the immortality math come from the trophy case
    # (career_accolades), the same source the season rollover banks to.
    # Cups are counted separately via stanley_cups, so team awards stay out
    # of the individual-award tally. Falls back to awards_won for old data.
    _awards: List[str] = []
    try:
        for _e in (getattr(player, "career_accolades", None) or []):
            if isinstance(_e, dict):
                _k = str(_e.get("award", "") or "")
                if _k and _k != "stanley_cup":
                    _awards.append(_k)
    except Exception:
        _awards = []
    if not _awards:
        try:
            _awards = list(getattr(player, "awards_won", None) or [])
        except Exception:
            _awards = []
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
        "awards": _awards,
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
# Jersey numbers: favorites, legality, arrival assignment, preseason
# finalization. Every player is dealt a preferred and a second-choice
# number once (never re-dealt); they want them on arrival, and at the
# preseason finalization they switch to a freed favorite unless they've
# started a legacy with the current number.
# ---------------------------------------------------------------------------

# League-wide: Gretzky's 99 is retired everywhere.
LEAGUE_RETIRED_NUMBERS = frozenset({99})

# Real retired numbers per franchise, verified against NHL.com/team
# announcements as of September 2026. Keyed by the in-game team_name.
# Seeded at generation; old saves backfill the same set. (Utah: the NHL
# treats the Mammoth as an expansion franchise with no Coyotes history --
# zero retired numbers. Winnipeg's original-Jets banners are honored,
# not retired.)
REAL_RETIRED_NUMBERS: Dict[str, List[int]] = {
    "Anaheim Ducks": [8, 9, 27],
    "Arizona Coyotes": [19],
    "Boston Bruins": [2, 3, 4, 5, 7, 8, 9, 15, 16, 22, 24, 33, 77],
    "Buffalo Sabres": [2, 7, 11, 14, 16, 18, 30, 39],
    "Calgary Flames": [9, 12, 30, 34],
    "Carolina Hurricanes": [2, 10, 12, 17],
    "Chicago Blackhawks": [1, 3, 7, 9, 18, 21, 35, 81],
    "Colorado Avalanche": [19, 21, 23, 33, 52, 77],
    "Columbus Blue Jackets": [61],
    "Dallas Stars": [7, 8, 9, 19, 26, 56],
    "Detroit Red Wings": [1, 4, 5, 7, 9, 10, 12, 19, 91],
    "Edmonton Oilers": [3, 4, 7, 9, 11, 17, 31],
    "Florida Panthers": [1, 37, 93],
    "Los Angeles Kings": [4, 16, 18, 20, 23, 30],
    "Minnesota Wild": [1, 9],
    "Montreal Canadiens": [1, 2, 3, 4, 5, 7, 9, 10, 12, 16, 18, 19, 23, 29, 33],
    "Nashville Predators": [35],
    "New Jersey Devils": [3, 4, 26, 27, 30],
    "New York Islanders": [5, 9, 19, 22, 23, 27, 31, 91],
    "New York Rangers": [1, 2, 3, 7, 9, 11, 19, 30, 35],
    "Ottawa Senators": [4, 8, 11, 25],
    "Philadelphia Flyers": [1, 2, 4, 7, 16, 88],
    "Pittsburgh Penguins": [21, 66, 68],
    "San Jose Sharks": [12, 19],
    "Seattle Kraken": [32],
    "St. Louis Blues": [2, 3, 5, 8, 11, 16, 24, 44],
    "Tampa Bay Lightning": [4, 26],
    "Toronto Maple Leafs": [1, 4, 5, 6, 7, 9, 10, 13, 14, 17, 21, 27, 93],
    "Utah Hockey Club": [],
    "Utah Mammoth": [],
    "Vancouver Canucks": [10, 12, 16, 19, 22, 33],
    "Vegas Golden Knights": [58],
    "Washington Capitals": [5, 7, 11, 32],
    "Winnipeg Jets": [],
}

# Numbers no skater may wear: 1 and 30 are goalie numbers. (Also enforced
# in the user-facing assign dialog.)
SKATER_BARRED_NUMBERS = frozenset({1, 30})


def _favorite_pool(is_goalie: bool) -> List[Tuple[int, int]]:
    """(number, weight) pools. Iconic numbers weigh heavier; 99 never
    appears (league-retired); skaters never get 1/30 as favorites."""
    if is_goalie:
        return [(30, 10), (31, 10), (35, 9), (32, 7), (33, 6), (34, 6),
                (37, 5), (40, 5), (41, 5), (29, 4), (1, 4), (36, 3),
                (38, 3), (39, 3), (60, 2), (70, 2), (72, 2), (73, 2)]
    return [(19, 10), (91, 9), (88, 9), (9, 8), (11, 7), (27, 7), (13, 6),
            (17, 6), (92, 6), (97, 6), (8, 5), (10, 5), (16, 5), (18, 5),
            (20, 5), (21, 5), (26, 5), (28, 5), (71, 5), (81, 5), (87, 5),
            (7, 4), (12, 4), (14, 4), (15, 4), (22, 4), (24, 4), (25, 4),
            (29, 4), (44, 4), (55, 4), (77, 4), (93, 4),
            (23, 3), (39, 3), (42, 3), (43, 3), (45, 3), (46, 3), (47, 3),
            (48, 3), (49, 3), (50, 3), (51, 3), (52, 3), (53, 3), (54, 3),
            (56, 3), (57, 3), (59, 3), (61, 3), (62, 3), (63, 3), (64, 3),
            (65, 3), (67, 3), (68, 3), (69, 3), (72, 3), (73, 3), (74, 3),
            (75, 3), (76, 3), (78, 3), (79, 3), (80, 3), (82, 3), (83, 3),
            (84, 3), (85, 3), (86, 3), (89, 3), (90, 3), (94, 3), (95, 3),
            (96, 3), (98, 3)]


def deal_favorite_numbers(is_goalie: bool) -> Tuple[int, int]:
    """Deal (preferred, second) once per player. Distinct, never 99."""
    pool = _favorite_pool(is_goalie)
    nums = [n for n, _ in pool]
    weights = [w for _, w in pool]
    preferred = random.choices(nums, weights=weights, k=1)[0]
    rest = [n for n in nums if n != preferred]
    rw = [w for n, w in pool if n != preferred]
    second = random.choices(rest, weights=rw, k=1)[0]
    return preferred, second


def seed_retired_numbers(team: Any) -> int:
    """Seed a team's retired numbers: league-wide 99 plus the franchise's
    real retired numbers (as of Sept 2026). Idempotent. Returns newly added."""
    added = 0
    try:
        rn = retired_numbers(team)
        have = {r.get("number") for r in rn}
        name = getattr(team, "team_name", "") or ""
        for num in sorted(LEAGUE_RETIRED_NUMBERS):
            if num not in have:
                rn.append({"number": num, "player": "Wayne Gretzky",
                           "year": 2000, "league_wide": True})
                have.add(num)
                added += 1
        for num in REAL_RETIRED_NUMBERS.get(name, []):
            if num not in have:
                rn.append({"number": num, "player": "", "year": 0,
                           "historic": True})
                have.add(num)
                added += 1
    except Exception:
        pass
    return added


def number_selectable(team: Any, number: Any, is_goalie: bool) -> bool:
    """Can anyone wear this number in this organization right now? Checks
    the NHL roster and the AHL roster -- a shared pool, since call-ups
    must not collide."""
    try:
        n = int(number)
    except Exception:
        return False
    if not (1 <= n <= 98):
        return False
    if n in LEAGUE_RETIRED_NUMBERS:
        return False
    if not is_goalie and n in SKATER_BARRED_NUMBERS:
        return False
    if is_number_retired(team, n):
        return False
    try:
        for attr in ("roster", "ahl_roster"):
            for p in (getattr(team, attr, None) or []):
                if int(getattr(p, "jersey_number", 0) or 0) == n:
                    return False
    except Exception:
        pass
    return True


def _first_free_number(team: Any, is_goalie: bool,
                       skip: Optional[set] = None) -> Optional[int]:
    skip = set(skip or ())
    for n in range(1, 99):
        if n in skip:
            continue
        if number_selectable(team, n, is_goalie):
            return n
    return None


def assign_arrival_number(team: Any, player: Any, year: int) -> int:
    """Give an arriving player (draft/signing/trade) his number: preferred
    if free and legal, else second choice, else first free legal number.
    Stamps jersey_number_since for the legacy rule."""
    try:
        goalie = _is_goalie(player)
        for cand in (getattr(player, "preferred_number", 0),
                     getattr(player, "second_number", 0)):
            try:
                if cand and number_selectable(team, cand, goalie):
                    player.jersey_number = int(cand)
                    player.jersey_number_since = int(year)
                    return int(cand)
            except Exception:
                continue
        free = _first_free_number(team, goalie)
        if free is not None:
            player.jersey_number = free
            player.jersey_number_since = int(year)
            return free
    except Exception:
        pass
    return int(getattr(player, "jersey_number", 0) or 0)


def _has_legacy_with_number(player: Any, year: int) -> bool:
    """Has this player started a legacy with his current number? Grandfathered
    players (jersey_number_since None, e.g. old saves) count as legacy --
    nobody gets reshuffled under them."""
    try:
        since = getattr(player, "jersey_number_since", None)
        if since is None:
            return True
        if int(year) - int(since) >= 3:
            return True
        # Won anything wearing it? Any accolade banked since the number
        # was adopted counts -- Cups included.
        for e in (getattr(player, "career_accolades", None) or []):
            if not isinstance(e, dict):
                continue
            ystr = str(e.get("year", "") or "")
            digits = "".join(c for c in ystr[:4] if c.isdigit())
            if digits and int(digits) >= int(since):
                return True
    except Exception:
        return True
    return False


def finalize_team_numbers(team: Any, year: int) -> List[Dict[str, Any]]:
    """Preseason number finalization, run with the captaincy pass. For each
    roster player: fix illegal numbers (retired/collisions/#1/#30 skaters),
    then if a favorite (preferred, else second) is free and legal and the
    player has no legacy with the current number, he switches. Returns the
    list of switches for news."""
    switches: List[Dict[str, Any]] = []
    try:
        roster = list(getattr(team, "roster", None) or [])
        roster = roster + list(getattr(team, "ahl_roster", None) or [])
    except Exception:
        return switches
    try:
        year = int(year)
    except Exception:
        return switches
    for player in roster:
        try:
            goalie = _is_goalie(player)
            cur = int(getattr(player, "jersey_number", 0) or 0)
            # Fix illegal numbers first: retired, taken twice anywhere in
            # the organization, or a skater in 1/30. The player keeps
            # seniority for the repair pick.
            _org_count = 0
            try:
                for _attr in ("roster", "ahl_roster"):
                    for _p in (getattr(team, _attr, None) or []):
                        if int(getattr(_p, "jersey_number", 0) or 0) == cur:
                            _org_count += 1
            except Exception:
                _org_count = 1
            legal_now = (
                cur and cur not in LEAGUE_RETIRED_NUMBERS
                and (goalie or cur not in SKATER_BARRED_NUMBERS)
                and not is_number_retired(team, cur)
                and _org_count == 1
            )
            if not legal_now:
                new = assign_arrival_number(team, player, year)
                if new and new != cur:
                    switches.append({"player": player, "old": cur,
                                     "new": new, "reason": "repair"})
                continue
            # A freed favorite: preferred first, then second choice.
            for want in (getattr(player, "preferred_number", 0),
                         getattr(player, "second_number", 0)):
                try:
                    want = int(want or 0)
                except Exception:
                    continue
                if not want or want == cur:
                    continue
                if not number_selectable(team, want, goalie):
                    continue
                if _has_legacy_with_number(player, year):
                    continue
                player.jersey_number = want
                player.jersey_number_since = year
                switches.append({"player": player, "old": cur, "new": want,
                                 "reason": "favorite"})
                break
        except Exception:
            continue
    return switches


def initial_number_assignment(team: Any, year: int) -> None:
    """League generation: veterans pick first. Seniority order (career games,
    then overall) so established players land their favorites."""
    try:
        roster = list(getattr(team, "roster", None) or [])
    except Exception:
        return
    def _seniority(p):
        try:
            return (int(getattr(p, "career_games", 0) or 0),
                    float(getattr(p, "overall", 50) or 50))
        except Exception:
            return (0, 0)
    for player in sorted(roster, key=_seniority, reverse=True):
        try:
            assign_arrival_number(team, player, year)
        except Exception:
            continue


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


# ---------------------------------------------------------------------------
# Scheduled real-life jersey retirements -- first season
# ---------------------------------------------------------------------------
# The three ceremonies announced for 2026-27, staged in the sim's FIRST
# season on the real month/day so the rafters match reality and the
# retirement pipeline proves itself live. Real names only: these legends are
# history, not generated players, so the ceremony honors the man himself
# regardless of who the sim generated.
#
# New games stamp absolute dates from their inaugural season_year onto
# league.ceremony_schedule (persisted). Old saves without a schedule fall
# back to the real 2026-27 dates; anything past-dated is retired quietly by
# retire_overdue_ceremonies() instead of firing late.
CEREMONY_TEMPLATES: List[Dict[str, Any]] = [
    {"team": "Boston Bruins", "number": 37, "player": "Patrice Bergeron",
     "month": 12, "day": 1, "offset": 0,
     "note": "the Selke standard-bearer who captained Boston for 19 seasons"},
    {"team": "Anaheim Ducks", "number": 15, "player": "Ryan Getzlaf",
     "month": 1, "day": 30, "offset": 1,
     "note": "the 2007 Cup-winning captain and franchise scoring king"},
    {"team": "Los Angeles Kings", "number": 11, "player": "Anze Kopitar",
     "month": 2, "day": 24, "offset": 1,
     "note": "the two-time Cup champion who defined Kings hockey"},
]

# The real 2026-27 dates, used for old saves that predate the schedule.
REAL_CEREMONY_DATES: List[Dict[str, Any]] = [
    dict(t, date=f"{2026 + t['offset']}-{t['month']:02d}-{t['day']:02d}")
    for t in CEREMONY_TEMPLATES
]


def ceremony_schedule_for(first_season_year: int) -> List[Dict[str, Any]]:
    """Absolute-date ceremony schedule for a league whose first season is
    ``first_season_year`` (e.g. 2026 -> 2026-27: Dec 1 2026, Jan 30 / Feb 24
    2027)."""
    try:
        y = int(first_season_year)
    except Exception:
        y = 2026
    return [dict(t, date=f"{y + t['offset']}-{t['month']:02d}-{t['day']:02d}")
            for t in CEREMONY_TEMPLATES]


def _ceremony_schedule(league: Any) -> List[Dict[str, Any]]:
    sched = getattr(league, "ceremony_schedule", None)
    if sched:
        return [dict(c) for c in sched]
    # Old save: the real dates are the truth.
    return [dict(c) for c in REAL_CEREMONY_DATES]


def _find_team_by_name(league: Any, name: str) -> Optional[Any]:
    for t in getattr(league, "teams", None) or []:
        if getattr(t, "team_name", "") == name:
            return t
    return None


def ceremonies_due(league: Any, today: Any) -> List[Tuple[Any, Dict[str, Any]]]:
    """(team, ceremony) pairs whose date is today and number not yet retired.

    Idempotent: once the number is retired the ceremony never re-fires."""
    out: List[Tuple[Any, Dict[str, Any]]] = []
    try:
        today_s = str(getattr(today, "isoformat", lambda: today)())
    except Exception:
        today_s = str(today)
    for c in _ceremony_schedule(league):
        if str(c.get("date")) != today_s:
            continue
        team = _find_team_by_name(league, c.get("team", ""))
        if team is None:
            continue
        if is_number_retired(team, int(c.get("number", 0))):
            continue
        out.append((team, c))
    return out


def retire_overdue_ceremonies(league: Any, today: Any) -> List[str]:
    """Old-save backfill: ceremonies whose date passed without firing get
    their numbers retired quietly (one inbox note each). Idempotent -- a
    retired number never re-fires."""
    stories: List[str] = []
    try:
        today_s = str(getattr(today, "isoformat", lambda: today)())
    except Exception:
        today_s = str(today)
    for c in _ceremony_schedule(league):
        if str(c.get("date", "")) >= today_s:
            continue
        team = _find_team_by_name(league, c.get("team", ""))
        if team is None:
            continue
        n = int(c.get("number", 0))
        if is_number_retired(team, n):
            continue
        year = int(str(c.get("date", "2026"))[:4])
        retire_number(team, {"number": n, "name": str(c.get("player", ""))},
                      year)
        stories.append(
            f"\U0001f3d2 Previously retired: {team.team_name} No. {n} -- "
            f"{c.get('player', '')} ({c.get('date', '')}).")
    return stories


def stage_ceremony(team: Any, ceremony: Dict[str, Any]) -> str:
    """Retire the ceremony number and return the inbox story.

    If a generated player currently wears the number, he is moved to a new
    one first (preferring his own favorite) -- the rafters are sacred."""
    n = int(ceremony.get("number", 0))
    name = str(ceremony.get("player", ""))
    year = int(str(ceremony.get("date", "2026"))[:4])
    moved_note = ""
    try:
        incumbent = next(
            (p for p in (getattr(team, "roster", None) or [])
             if getattr(p, "jersey_number", None) == n), None)
        if incumbent is not None:
            # The number being retired can never be re-dealt to him.
            saved = (getattr(incumbent, "preferred_number", 0),
                     getattr(incumbent, "second_number", 0))
            if saved[0] == n:
                incumbent.preferred_number = 0
            if saved[1] == n:
                incumbent.second_number = 0
            incumbent.jersey_number = None
            assign_arrival_number(team, incumbent, year)
            incumbent.preferred_number, incumbent.second_number = saved
            if getattr(incumbent, "jersey_number", None) == n:
                # Last resort: first free legal number that isn't n.
                for cand in range(2, 99):
                    if cand != n and number_selectable(
                            team, cand, _is_goalie(incumbent)):
                        incumbent.jersey_number = cand
                        break
            moved_note = (
                f" {incumbent.first_name} {incumbent.last_name}, who wore "
                f"No. {n}, switches to No. "
                f"{getattr(incumbent, 'jersey_number', '?')} out of respect.")
    except Exception:
        pass
    retire_number(team, {"number": n, "name": name}, year)
    return (
        f"\U0001f3d2 JERSEY RETIREMENT -- {team.team_name}: No. {n} rises to "
        f"the rafters for {name}, {ceremony.get('note', 'a franchise icon')}."
        f"{moved_note} No {team.team_name} player will wear No. {n} again.")


# ---------------------------------------------------------------------------
# Stanley Cup awarding recap
# ---------------------------------------------------------------------------
def _had_cup_before(p: Any) -> bool:
    return any(isinstance(e, dict) and e.get("award") == "stanley_cup"
               for e in (getattr(p, "career_accolades", None) or []))


def _playoff_pts(p: Any) -> Tuple[int, int, int]:
    ps = getattr(p, "playoff_stats", None)
    g = int(getattr(ps, "goals", 0) or 0)
    a = int(getattr(ps, "assists", 0) or 0)
    gp = int(getattr(ps, "games_played", 0) or 0)
    return g, a, gp


def build_cup_recap(champ: Any, bracket: Any, league: Any) -> str:
    """The Cup-night story: winners, Conn Smythe, the Cup's first two
    carriers, the heroes, and the coach's victory interview."""
    cname = getattr(champ, "team_name", "The champions")
    roster = [p for p in (getattr(champ, "roster", None) or [])]

    def _pn(p: Any) -> str:
        return f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()

    # --- the Final, and the score ---
    opp_name, score_txt = "the Final", ""
    try:
        for s in ((getattr(bracket, "playoff_series", None) or {})
                  .get("stanley_cup_final", None) or []):
            w = getattr(s, "winner", None)
            if w is champ or getattr(w, "team_name", None) == cname:
                t1, t2 = getattr(s, "team1", None), getattr(s, "team2", None)
                champ_is_t1 = (t1 is champ
                               or getattr(t1, "team_name", None) == cname)
                cw = int(getattr(s, "team1_wins" if champ_is_t1 else "team2_wins", 0) or 0)
                lw = int(getattr(s, "team2_wins" if champ_is_t1 else "team1_wins", 0) or 0)
                opp = t2 if champ_is_t1 else t1
                opp_name = getattr(opp, "team_name", "the opposition")
                score_txt = f" {cw}-{lw}"
                break
    except Exception:
        pass

    # --- Conn Smythe ---
    smythe = getattr(bracket, "conn_smythe_winner", None)
    smythe_name = (getattr(bracket, "conn_smythe_name", None)
                   or (_pn(smythe) if smythe is not None else ""))
    smythe_bit = ""
    if smythe is not None and smythe_name:
        g, a, gp = _playoff_pts(smythe)
        smythe_bit = (f" Conn Smythe winner {smythe_name} ({g}G-{a}A in "
                      f"{gp} playoff games) was voted playoff MVP.")
    elif smythe_name:
        smythe_bit = f" Conn Smythe winner {smythe_name} was voted playoff MVP."

    # --- the Cup's journey: captain first, then a veteran ---
    caps = [p for p in roster if getattr(p, "captaincy", None) == "C"]
    first = caps[0] if caps else None
    if first is None:
        first = smythe if smythe in roster else None
    if first is None and roster:
        sk = [p for p in roster if not _is_goalie(p)] or roster
        first = max(sk, key=lambda p: int(getattr(p, "career_points", 0) or 0))
    first_name = _pn(first) if first is not None else "the captain"
    cands = [p for p in roster
             if p is not first and not _is_goalie(p)]
    first_timers = [p for p in cands if not _had_cup_before(p)]
    pool = first_timers or cands
    second = (max(pool, key=lambda p: (int(getattr(p, "career_games", 0) or 0),
                                       int(getattr(p, "age", 0) or 0)))
              if pool else None)
    carry_bit = ""
    if second is not None:
        cg = int(getattr(second, "career_games", 0) or 0)
        if not _had_cup_before(second):
            why = (f"a veteran of {cg} NHL games, finally a champion"
                   if cg else "finally a champion")
        else:
            why = (f"a veteran of {cg} NHL games" if cg else "a veteran")
        carry_bit = (f" {_pn(first)} took the traditional first skate, then "
                     f"handed it to {_pn(second)} -- {why}.")

    # --- the heroes ---
    named_ids = {id(first), id(second)}
    if smythe is not None:
        named_ids.add(id(smythe))
    heroes = sorted((p for p in roster if not _is_goalie(p)
                     and id(p) not in named_ids),
                    key=lambda p: _playoff_pts(p)[0] + _playoff_pts(p)[1],
                    reverse=True)[:3]
    hero_bits = []
    for h in heroes:
        g, a, gp = _playoff_pts(h)
        if g + a > 0:
            hero_bits.append(f"{_pn(h)} ({g}G-{a}A, {gp} GP)")
    hero_bit = (" Also starring: " + "; ".join(hero_bits) + "."
                if hero_bits else "")

    # --- the coach's victory interview ---
    coach = getattr(champ, "head_coach", None)
    if coach is None:
        try:
            import reputation_system as _rs
            coach = _rs._head_coach_of(champ)
        except Exception:
            coach = None
    coach_name = (f"{getattr(coach, 'first_name', '')} "
                  f"{getattr(coach, 'last_name', '')}").strip()
    try:
        _sy = int(getattr(league, "season_year", 2026) or 2026)
    except Exception:
        _sy = 2026
    _qrng = random.Random(f"cup-{cname}-{_sy}")
    _who = coach_name or "the head coach"
    quotes = [
        (f"\"You dream about this as a kid on the outdoor rink. To do it "
         f"with this group, in this room -- there's no feeling like it,\" "
         f"{_who} said, the Cup gleaming behind him. \"They refused to "
         f"lose.\""),
        (f"\"Sixteen wins. That's all anyone remembers,\" {_who} said. "
         f"\"{first_name} set the tone every single day since September, "
         f"and when it got hard, this team got harder. I'm just lucky I "
         f"get to stand behind their bench.\""),
        (f"\"People will talk about the goals, but championships are won "
         f"in the dirty areas,\" {_who} said. \"Every blocked shot, every "
         f"backcheck -- that's what that trophy is. This group paid the "
         f"price.\""),
        (f"\"I've been around a long time and I've never seen a room like "
         f"this one,\" {_who} said. \"They played for each other. You "
         f"can't coach that. You just try not to get in the way.\""),
    ]
    quote = _qrng.choice(quotes)

    story = (
        f"\U0001f3c6 STANLEY CUP CHAMPIONS -- {cname}! They defeat "
        f"{opp_name}{score_txt} to win the Cup.{smythe_bit}{carry_bit}"
        f"{hero_bit}\n\n{quote}\n\nThe parade route will be announced "
        f"tomorrow. {cname} -- champions.")
    return story
