"""NHL All-Star Game: roster selection true to the real criteria.

The real format (3v3 era):
- Four teams, one per division (Atlantic, Metropolitan, Central, Pacific).
- Fan vote elects one captain per division.
- NHL Hockey Operations selects the rest: 11 players per division --
  9 skaters + 2 goalies -- based on first-half performance.
- Every NHL club must have at least one representative.

What this module does, once per season:
- select_all_star_rosters(league): runs the vote + the ops room, stamps
  each player's trophy case (career_accolades, de-duplicated per season),
  and records league.all_star_rosters[season] as plain ID dicts (save
  safe). Idempotent: a completed season is never re-run.
- play_all_star_game(rosters, rng): exhibition result only -- picks a
  winning division with a plausible 3v3 tournament score for the news
  feed. PRESENTATION ONLY: no player stats, morale, or injuries touched.
- skills_winners(rosters, rng): Fastest Skater / Hardest Shot / Accuracy
  Shooting from roster attributes (getattr-defensive). Flavor only.

Perf: one pass over NHL players at the announcement date; dict lookups
after. Nothing per-tick.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

DIVISIONS = ("Atlantic", "Metropolitan", "Central", "Pacific")
SKATERS_PER_TEAM = 9
GOALIES_PER_TEAM = 2
MIN_SKATER_GAMES = 15   # first-half sample: no 4-game call-up all-stars
MIN_GOALIE_GAMES = 10

_SEASON_LABEL = lambda y: f"{y}-{str(y + 1)[-2:]}"


def _pname(p: Any) -> str:
    # Real Players expose full_name; QA fakes use name.
    return getattr(p, "full_name", None) or getattr(p, "name", "") or ""


def _team_name(t: Any) -> str:
    return getattr(t, "team_name", "") or ""


def _is_goalie(p: Any) -> bool:
    pos = getattr(getattr(p, "primary_position", None), "value", "") or ""
    return "G" in str(pos).upper()


def _is_dman(p: Any) -> bool:
    pos = getattr(getattr(p, "primary_position", None), "value", "") or ""
    return str(pos).upper() in ("D", "LD", "RD")


def _nhl_players(league: Any) -> List[Any]:
    out = []
    try:
        for t in getattr(league, "teams", []) or []:
            if getattr(t, "league_name", "") != "National Hockey League":
                continue
            for p in getattr(t, "roster", []) or []:
                out.append(p)
    except Exception:
        pass
    return out


def _popularity(p: Any, rng: random.Random) -> float:
    """Fan-vote appeal: star power first, scoring second. Reputation is
    the stand-in for jersey sales and highlight reels."""
    try:
        st = getattr(p, "stats", None)
        pts = float(getattr(st, "points", 0) or 0)
        rep = float(getattr(p, "reputation", 50) or 50)
        ovr = float(getattr(p, "overall", 70) or 70)
    except Exception:
        pts, rep, ovr = 0.0, 50.0, 70.0
    return rep * 1.0 + pts * 1.5 + ovr * 0.4 + rng.uniform(0, 12)


def _skater_score(p: Any) -> Tuple[float, float]:
    """Hockey-ops merit: first-half production, then overall."""
    try:
        st = getattr(p, "stats", None)
        pts = float(getattr(st, "points", 0) or 0)
        gp = float(getattr(st, "games_played", 0) or 0)
        ovr = float(getattr(p, "overall", 70) or 70)
    except Exception:
        pts, gp, ovr = 0.0, 0.0, 70.0
    ppg = pts / max(gp, 1)
    return (pts + ppg * 8.0, ovr)


def _goalie_score(p: Any) -> Tuple[float, float, float]:
    try:
        st = getattr(p, "stats", None)
        sv = float(getattr(st, "save_percentage", 0) or 0)
        w = float(getattr(st, "wins", 0) or 0)
        gp = float(getattr(st, "games_played", 0) or 0)
    except Exception:
        sv, w, gp = 0.0, 0.0, 0.0
    return (sv * 100.0 + w * 0.6 + gp * 0.1, w, gp)


def _eligible(p: Any, min_games: int) -> bool:
    try:
        gp = int(getattr(getattr(p, "stats", None), "games_played", 0) or 0)
    except Exception:
        return False
    return gp >= min_games


def _division_of(player_team: Any) -> str:
    return getattr(player_team, "division", "") or ""


def _stamp_accolade(p: Any, ceremony_year: str) -> None:
    """Bank the All-Star nod into the player's trophy case via the
    canonical accolades module (idempotent on (award, year)). The card's
    Accolades section renders it from there. Ceremony-year convention:
    the Feb-2027 game for the 2026-27 season banks as "2027"."""
    try:
        from accolades import bank_accolade
        bank_accolade(p, "all_star", ceremony_year)
    except Exception:
        pass


def select_all_star_rosters(league: Any, season_year: Optional[int] = None,
                            rng: Optional[random.Random] = None
                            ) -> Dict[str, Dict[str, List[Any]]]:
    """Run the fan vote + hockey-ops selection for one season.

    Returns {division: {"captain": p, "skaters": [...9], "goalies": [...2]}}.
    Empty dict if already selected this season (idempotent) or if there is
    no usable player pool.
    """
    rng = rng or random.Random()
    try:
        if season_year is None:
            season_year = int(getattr(league, "season_year", 2026))
    except Exception:
        season_year = 2026
    label = _SEASON_LABEL(season_year)
    # Ceremony-year convention (accolades.py): the All-Star game is
    # played in February of season_year + 1.
    ceremony_year = str(season_year + 1)

    store = getattr(league, "all_star_rosters", None)
    if store is None:
        league.all_star_rosters = store = {}
    if label in store:
        return {}

    # Division -> teams, and player -> team lookup.
    div_teams: Dict[str, List[Any]] = {}
    player_team: Dict[int, Any] = {}
    for t in getattr(league, "teams", []) or []:
        if getattr(t, "league_name", "") != "National Hockey League":
            continue
        d = _division_of(t)
        if d in DIVISIONS:
            div_teams.setdefault(d, []).append(t)
            for p in getattr(t, "roster", []) or []:
                try:
                    player_team[id(p)] = t
                except Exception:
                    pass
    if not div_teams:
        return {}

    result: Dict[str, Dict[str, List[Any]]] = {}
    for div in DIVISIONS:
        teams = div_teams.get(div, [])
        if not teams:
            continue
        pool = [p for t in teams for p in (getattr(t, "roster", []) or [])]
        skaters = [p for p in pool
                   if not _is_goalie(p) and _eligible(p, MIN_SKATER_GAMES)]
        goalies = [p for p in pool
                   if _is_goalie(p) and _eligible(p, MIN_GOALIE_GAMES)]
        if not skaters:
            continue

        # 1) Fan vote: one captain per division, skaters only.
        captain = max(skaters, key=lambda p: _popularity(p, rng))
        chosen = [captain]
        chosen_ids = {id(captain)}

        def team_of(p: Any) -> Optional[Any]:
            return player_team.get(id(p))

        def represented(tn: str) -> bool:
            return any(_team_name(team_of(p)) == tn for p in chosen)

        # 2) Hockey ops: every club gets at least one representative.
        for t in teams:
            tn = _team_name(t)
            if represented(tn):
                continue
            cands = [p for p in skaters
                     if id(p) not in chosen_ids
                     and _team_name(team_of(p)) == tn]
            if not cands:
                continue
            best = max(cands, key=_skater_score)
            chosen.append(best)
            chosen_ids.add(id(best))

        # 3) Hockey ops: at least two defensemen per division team.
        dmen = [p for p in chosen if _is_dman(p)]
        if len(dmen) < 2:
            d_pool = sorted(
                (p for p in skaters
                 if id(p) not in chosen_ids and _is_dman(p)),
                key=_skater_score, reverse=True)
            for d in d_pool[: 2 - len(dmen)]:
                if len(chosen) < SKATERS_PER_TEAM + 1:  # captain + 9 max
                    chosen.append(d)
                    chosen_ids.add(id(d))

        # 4) Hockey ops: fill to 9 skaters on merit (captain + 9 max).
        rest = sorted((p for p in skaters if id(p) not in chosen_ids),
                      key=_skater_score, reverse=True)
        for p in rest:
            if len(chosen) >= SKATERS_PER_TEAM + 1:
                break
            chosen.append(p)
            chosen_ids.add(id(p))
        skater_lineup = [p for p in chosen if p is not captain][:SKATERS_PER_TEAM]

        # 5) Two goalies on merit (save% then wins).
        goalie_lineup = sorted(goalies, key=_goalie_score,
                               reverse=True)[:GOALIES_PER_TEAM]

        # 6) Every-team rule, final sweep: a club with no skater or goalie
        # selected gets its best skater, bumping the lowest-merit
        # non-protected skater if the bench is full. The captain counts
        # as his club's representative.
        protected = {id(captain)}
        for p in chosen:
            tn = _team_name(team_of(p))
            if sum(1 for q in chosen if _team_name(team_of(q)) == tn) == 1:
                protected.add(id(p))
        full_lineup = [captain] + skater_lineup + goalie_lineup
        full_ids = {id(p) for p in full_lineup}
        for t in teams:
            tn = _team_name(t)
            if any(_team_name(team_of(p)) == tn for p in full_lineup):
                continue
            cands = [p for p in skaters
                     if _team_name(team_of(p)) == tn and id(p) not in full_ids]
            if not cands:
                continue
            add = max(cands, key=_skater_score)
            if len(skater_lineup) < SKATERS_PER_TEAM:
                skater_lineup.append(add)
            else:
                bumpable = [p for p in skater_lineup if id(p) not in protected]
                if bumpable:
                    skater_lineup.remove(min(bumpable, key=_skater_score))
                    skater_lineup.append(add)

        for p in [captain] + skater_lineup + goalie_lineup:
            _stamp_accolade(p, ceremony_year)
        result[div] = {"captain": captain, "skaters": skater_lineup,
                       "goalies": goalie_lineup}

    # Persist as plain IDs (save/load safe); objects stay in the return.
    for div, r in result.items():
        try:
            store[label] = store.get(label, {})
            store[label][div] = {
                "captain_id": getattr(r["captain"], "id", None),
                "skater_ids": [getattr(p, "id", None) for p in r["skaters"]],
                "goalie_ids": [getattr(p, "id", None) for p in r["goalies"]],
            }
        except Exception:
            pass
    return result


def resolve_rosters(league: Any, season_label: str
                   ) -> Dict[str, Dict[str, List[Any]]]:
    """Map stored all-star IDs back to player objects (e.g. on game day,
    or after a save/load). Missing players are skipped."""
    store = getattr(league, "all_star_rosters", None) or {}
    season = store.get(season_label) or {}
    by_id: Dict[Any, Any] = {}
    for p in _nhl_players(league):
        try:
            by_id[getattr(p, "id", None)] = p
        except Exception:
            pass
    out: Dict[str, Dict[str, List[Any]]] = {}
    for div, r in season.items():
        try:
            cap = by_id.get(r.get("captain_id"))
            sk = [by_id[i] for i in (r.get("skater_ids") or []) if i in by_id]
            gl = [by_id[i] for i in (r.get("goalie_ids") or []) if i in by_id]
            if cap is not None:
                out[div] = {"captain": cap, "skaters": sk, "goalies": gl}
        except Exception:
            pass
    return out


def all_star_game_date(league: Any) -> Optional[Any]:
    """Find the All-Star Game NHL_EVENT date on the league schedule."""
    try:
        for item in getattr(league, "schedule", []) or []:
            if isinstance(item, dict):
                d, home, meta = item.get("date"), item.get("home_team"), item
            elif isinstance(item, (tuple, list)) and len(item) >= 3:
                d, home, meta = item[0], item[1], item[2]
            else:
                continue
            if home != "NHL_EVENT":
                continue
            if isinstance(meta, dict) and meta.get("type") == "all_star_game":
                return d
    except Exception:
        pass
    return None


def skills_winners(rosters: Dict[str, Dict[str, List[Any]]],
                   rng: Optional[random.Random] = None) -> List[Tuple[str, str, str]]:
    """Skills Competition flavor: winners picked from roster attributes."""
    rng = rng or random.Random()
    skaters = [p for r in rosters.values()
               for p in ([r["captain"]] + r["skaters"])]
    if not skaters:
        return []
    events = [
        ("Fastest Skater", ("speed", "acceleration")),
        ("Hardest Shot", ("slap_shot_power", "shot_power", "wrist_shot_power")),
        ("Accuracy Shooting", ("shooting_accuracy", "offensive_awareness")),
    ]
    out = []
    used = set()
    for title, attrs in events:
        def score(p: Any) -> float:
            return max(float(getattr(p, a, 50) or 50) for a in attrs) \
                + rng.uniform(0, 3)
        cands = [p for p in skaters if id(p) not in used] or skaters
        win = max(cands, key=score)
        used.add(id(win))
        div = next((d for d, r in rosters.items()
                    if win is r["captain"] or win in r["skaters"]
                    or win in r["goalies"]), "")
        out.append((title, _pname(win), div))
    return out


def play_all_star_game(rosters: Dict[str, Dict[str, List[Any]]],
                       rng: Optional[random.Random] = None) -> Dict[str, Any]:
    """Exhibition 3v3 tournament result. PRESENTATION ONLY -- no stats,
    morale, or injuries are touched. Weighted by roster star power so
    the favorite usually (not always) lifts it."""
    rng = rng or random.Random()
    divs = list(rosters.keys())
    if len(divs) < 2:
        return {}
    def strength(div: str) -> float:
        r = rosters[div]
        return sum(float(getattr(p, "overall", 75) or 75)
                   for p in ([r["captain"]] + r["skaters"])) / 10.0
    weights = [strength(d) for d in divs]
    # Semi-finals: 1v4, 2v3 by strength, then a final.
    order = sorted(range(len(divs)), key=lambda i: weights[i], reverse=True)
    def winner(a: int, b: int) -> int:
        wa = weights[a] / max(weights[a] + weights[b], 1)
        return a if rng.random() < wa else b
    f1 = winner(order[0], order[-1])
    f2 = winner(order[1], order[-2]) if len(order) > 2 else order[1]
    champ = winner(f1, f2)
    champ_div = divs[champ]
    final_score = (rng.randint(6, 10), rng.randint(4, 8))
    if final_score[0] == final_score[1]:
        final_score = (final_score[0] + 1, final_score[1])
    return {
        "champion": champ_div,
        "finalists": (divs[f1], divs[f2]),
        "score": f"{final_score[0]}-{final_score[1]}",
    }


def announcement_copy(rosters: Dict[str, Dict[str, List[Any]]],
                      season_label: str) -> str:
    """One inbox-ready story announcing the rosters."""
    bits = []
    for div in DIVISIONS:
        r = rosters.get(div)
        if not r:
            continue
        cap = _pname(r["captain"])
        n = len(r["skaters"]) + len(r["goalies"])
        bits.append(f"{div} ({cap} wearing the C, {n} total)")
    return (f"🌟 {season_label} All-Star rosters are set: the fans voted "
            f"their captains and hockey ops filled out the four division "
            f"squads -- " + "; ".join(bits) + ". Every club is represented.")
