"""Iconic games: the nights a franchise remembers.

Detection runs once per finished game inside
``narrative_incidents.process_postgame`` -- the same single pass that logs
career moments, so there is no extra per-game iteration cost beyond a few
integer comparisons. A game is iconic when it clears a bar the history
books would notice:

- 5+ goals by one skater (the 5-goal game)
- 7+ points by one skater (the Gagner line -- 8 points is the reference)
- 45+ save shutout, or 55+ saves in any result
- a line brawl, with a special callout when a goalie drops the gloves
  (the Battle of Alberta script)
- a Game 7 win, especially in overtime
- a 6+ goal rout in a rivalry game

Storage (all plain dicts -- save/load safe, tiny):

- ``team.iconic_games``: the club's canonical list, capped at 30 entries.
  Each entry carries a per-team ``starred`` flag.
- ``player.career_moments``: the night's stars get an ``iconic_game``
  moment in their established per-player log (sig 95, pruned like the
  rest).

Season memory: ``League.end_of_season`` calls :func:`prune_iconic_games`,
which drops unstarred entries from prior seasons. Starred entries
persist -- the user's curation is the franchise's permanent memory.

Never raises; never touches scoring or stats.
"""

from typing import Any, Dict, List, Optional, Tuple

# Cap per team: bounds save size and the dashboard list. Starred entries
# are pruned last, so a curator never loses a starred memory to the cap.
_ICONIC_CAP = 30

# Per-player moment significance: above every routine moment kind.
_ICONIC_MOMENT_SIG = 95
_MOMENT_CAP = 20

# (kind, weight) -- the highest-weight trigger becomes the entry's
# primary kind and headline; every trigger is recorded in "beats".
_KIND_WEIGHTS = {
    "game7_ot_win": 100,
    "five_goal_game": 90,
    "goalie_fight": 85,
    "seven_point_night": 80,
    "game7_win": 75,
    "epic_shutout": 70,
    "brawl_game": 65,
    "shot_barrage": 60,
    "rivalry_rout": 55,
}


def _dstr(game_date: Any) -> str:
    try:
        return game_date.isoformat() if hasattr(game_date, "isoformat") \
            else str(game_date or "")
    except Exception:
        return ""


def _sim_brawl(sim: Any) -> bool:
    """Did the live engine report a line brawl? (The quick sim rolls its
    brawl flag in process_postgame; the live sim models brawls live and
    reports them via pending_headlines.)"""
    try:
        for h in (getattr(sim, "pending_headlines", None) or []):
            if isinstance(h, dict) and h.get("kind") == "line_brawl":
                return True
    except Exception:
        pass
    return False


def _goalie_fight_names(sim: Any, home: Any, away: Any) -> List[str]:
    """Best-effort: goalie names appearing in a line-brawl's pairs.

    Only the live engine records brawl pairs (pending_headlines); the
    quick sim just rolls a brawl flag. Returns [] when unavailable.
    """
    try:
        pairs: List[Tuple[str, str]] = []
        for h in (getattr(sim, "pending_headlines", None) or []):
            if isinstance(h, dict) and h.get("kind") == "line_brawl":
                pairs.extend(h.get("pairs", None) or [])
        if not pairs:
            return []
        from narrative_incidents import _is_goalie
        goalies = set()
        for team in (home, away):
            for p in (getattr(team, "roster", None) or []):
                try:
                    if _is_goalie(p):
                        goalies.add(getattr(p, "full_name", ""))
                except Exception:
                    continue
        found: List[str] = []
        for a, b in pairs:
            for nm in (a, b):
                if nm in goalies and nm not in found:
                    found.append(nm)
        return found
    except Exception:
        return []


def detect_iconic(home: Any, away: Any,
                  home_score: int, away_score: int,
                  sim: Any,
                  went_ot: bool = False, shootout: bool = False,
                  rivalries: Optional[list] = None,
                  is_playoff: bool = False, series_game: int = 0,
                  brawl: bool = False,
                  game_date: Any = None,
                  season_year: Any = None) -> Optional[Dict[str, Any]]:
    """Evaluate a finished game. Returns an iconic-game entry or None."""
    try:
        from narrative_incidents import (_game_lines, _is_goalie,
                                         _player_index, _team_name,
                                         _is_rivalry_game)
        hn, an = _team_name(home), _team_name(away)
        idx = _player_index(home, away)
        dstr = _dstr(game_date)
        winner = hn if home_score > away_score else (
            an if away_score > home_score else hn)

        triggers: List[Tuple[str, Dict[str, Any]]] = []
        stars: List[Dict[str, Any]] = []

        def _star(p: Any, team_name: str, detail: str) -> None:
            try:
                stars.append({
                    "name": getattr(p, "full_name", "Unknown"),
                    "team": team_name,
                    "detail": detail,
                    "player_id": getattr(p, "id", None),
                })
            except Exception:
                pass

        top_skater = None
        top_points = -1
        for line in _game_lines(sim, idx):
            p = line["player"]
            goals, assists, saves = (line["goals"], line["assists"],
                                    line["saves"])
            points = goals + assists
            pname = getattr(p, "full_name", "Unknown")
            pteam = line.get("team_name") or hn
            if pteam not in (hn, an):
                pteam = hn
            opp = an if pteam == hn else hn
            if _is_goalie(p):
                if saves <= 0:
                    continue
                # Shutout check: the opponent's score vs this goalie's team.
                o_score = away_score if pteam == hn else home_score
                if o_score == 0 and saves >= 45:
                    triggers.append(("epic_shutout", {"player": p}))
                    _star(p, pteam,
                          f"{saves}-save shutout vs {opp}")
                elif saves >= 55:
                    triggers.append(("shot_barrage", {"player": p}))
                    _star(p, pteam,
                          f"{saves} saves vs {opp}")
                continue
            if points > top_points:
                top_points = points
                top_skater = (p, pteam, points, goals, assists)
            if goals >= 5:
                triggers.append(("five_goal_game", {"player": p}))
                _star(p, pteam, f"{goals} G, {assists} A vs {opp}")
            elif points >= 7:
                triggers.append(("seven_point_night", {"player": p}))
                _star(p, pteam, f"{goals} G, {assists} A vs {opp}")

        # Team-level triggers.
        if brawl:
            gfs = _goalie_fight_names(sim, home, away)
            if gfs:
                triggers.append(("goalie_fight", {"goalies": gfs}))
                for nm in gfs:
                    stars.append({"name": nm, "team": "",
                                  "detail": "dropped the gloves",
                                  "player_id": None})
            else:
                triggers.append(("brawl_game", {}))
        if is_playoff and series_game == 7 and home_score != away_score:
            if went_ot:
                triggers.append(("game7_ot_win", {}))
            else:
                triggers.append(("game7_win", {}))
        try:
            if (not is_playoff and abs(home_score - away_score) >= 6
                    and _is_rivalry_game(home, away, rivalries or [])):
                triggers.append(("rivalry_rout", {}))
        except Exception:
            pass

        if not triggers:
            return None

        # Team-level kinds with no individual star yet: credit the
        # night's top scorer so the player log has a face.
        if not stars and top_skater is not None and top_points > 0:
            p, pteam, _pts, g, a = top_skater
            opp = an if pteam == hn else hn
            _star(p, pteam, f"{g} G, {a} A vs {opp}")

        # Primary kind = highest weight.
        triggers.sort(key=lambda t: _KIND_WEIGHTS.get(t[0], 0),
                      reverse=True)
        kind = triggers[0][0]
        score = f"{home_score}-{away_score}"
        loser = an if winner == hn else hn

        def _pname(t: Tuple[str, Dict[str, Any]]) -> str:
            pl = (t[1] or {}).get("player")
            return getattr(pl, "full_name", "Unknown") if pl else "Unknown"

        ot_tag = " in overtime" if went_ot else ""
        if kind == "five_goal_game":
            headline = (f"{_pname(triggers[0])} scores FIVE in a "
                        f"{score} win over {loser}")
        elif kind == "seven_point_night":
            headline = (f"{_pname(triggers[0])}'s monster night powers "
                        f"{winner} past {loser} {score}")
        elif kind == "goalie_fight":
            gs = (triggers[0][1] or {}).get("goalies", [])
            headline = (f"Goalies go! {' and '.join(gs)} drop the gloves "
                        f"as {winner} tops {loser} {score}")
        elif kind == "epic_shutout":
            headline = (f"{_pname(triggers[0])} stones {loser} {score}")
        elif kind == "shot_barrage":
            headline = (f"{_pname(triggers[0])} stands on his head in a "
                        f"{score} battle with {loser}")
        elif kind == "brawl_game":
            headline = (f"Line brawl erupts as {winner} beats "
                        f"{loser} {score}")
        elif kind == "game7_ot_win":
            headline = (f"{winner} takes Game 7{ot_tag}, {score} over "
                        f"{loser}")
        elif kind == "game7_win":
            headline = (f"{winner} wins Game 7, {score} over {loser}")
        else:  # rivalry_rout
            headline = (f"{winner} humiliates {loser} {score} in a "
                        f"rivalry rout")

        season = season_year
        try:
            season = int(season) if season is not None else None
        except Exception:
            season = None
        entry = {
            "id": f"{season}|{dstr}|{hn}|{an}|{kind}",
            "date": dstr,
            "season": season,
            "kind": kind,
            "headline": headline,
            "beats": [t[0] for t in triggers],
            "home": hn,
            "away": an,
            "score": score,
            "winner": winner,
            "ot": bool(went_ot),
            "shootout": bool(shootout),
            "playoff": bool(is_playoff),
            "series_game": int(series_game or 0),
            "stars": stars,
            "starred": False,
        }
        return entry
    except Exception:
        return None


def _log_iconic_moments(entry: Dict[str, Any], home: Any, away: Any) -> int:
    """Append iconic_game moments to the night's stars. Returns count."""
    logged = 0
    try:
        from narrative_incidents import _player_index, _team_name
        hn, an = _team_name(home), _team_name(away)
        idx = _player_index(home, away)
        by_id = {}
        for key, p in (idx or {}).items():
            try:
                by_id[getattr(p, "id", None)] = p
            except Exception:
                continue
        dstr = entry.get("date", "")
        for s in (entry.get("stars", None) or []):
            if not isinstance(s, dict):
                continue
            pid = s.get("player_id")
            p = by_id.get(pid)
            if p is None:
                continue
            pteam = s.get("team") or hn
            opp = an if pteam == hn else hn
            scoreline = f"{entry.get('score', '')}"
            sig = _ICONIC_MOMENT_SIG + (20 if entry.get("playoff") else 0)
            moments = getattr(p, "career_moments", None)
            if not isinstance(moments, list):
                try:
                    p.career_moments = moments = []
                except Exception:
                    continue
            if any(isinstance(m, dict) and m.get("date") == dstr
                   and m.get("kind") == "iconic_game" for m in moments):
                continue
            moments.append({
                "date": dstr, "kind": "iconic_game",
                "label": "Iconic game", "detail": entry.get("headline", ""),
                "opp": opp, "score": scoreline,
                "playoff": bool(entry.get("playoff")),
                "sig": sig,
            })
            if len(moments) > _MOMENT_CAP:
                moments.sort(key=lambda m: (
                    m.get("sig", 0) if isinstance(m, dict) else 0,
                    m.get("date", "") if isinstance(m, dict) else ""))
                del moments[0:len(moments) - _MOMENT_CAP]
                moments.sort(key=lambda m: m.get("date", "")
                             if isinstance(m, dict) else "",
                             reverse=True)
            logged += 1
    except Exception:
        pass
    return logged


def record_iconic_game(home: Any, away: Any,
                       entry: Dict[str, Any]) -> int:
    """Store the entry on both clubs' iconic-games lists (capped).

    Returns the number of clubs that recorded it. Never raises.
    """
    recorded = 0
    try:
        for team in (home, away):
            try:
                lst = getattr(team, "iconic_games", None)
                if not isinstance(lst, list):
                    lst = []
                    team.iconic_games = lst
                if any(isinstance(e, dict) and e.get("id") == entry.get("id")
                       for e in lst):
                    recorded += 1
                    continue
                e = dict(entry)
                e["starred"] = False
                lst.append(e)
                while len(lst) > _ICONIC_CAP:
                    drop = next(
                        (i for i, x in enumerate(lst)
                         if isinstance(x, dict) and not x.get("starred")),
                        0)
                    del lst[drop]
                recorded += 1
            except Exception:
                continue
    except Exception:
        pass
    return recorded


def detect_and_record(home: Any, away: Any,
                      home_score: int, away_score: int,
                      sim: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
    """Detect, record on both clubs, and log player moments.

    Returns the entry or None. Never raises.
    """
    try:
        brawl = bool(kwargs.pop("brawl", False)) or _sim_brawl(sim)
        entry = detect_iconic(home, away, home_score, away_score, sim,
                              brawl=brawl, **kwargs)
        if entry is None:
            return None
        record_iconic_game(home, away, entry)
        _log_iconic_moments(entry, home, away)
        return entry
    except Exception:
        return None


def toggle_star(team: Any, entry_id: str) -> Optional[bool]:
    """Flip a team's starred flag on an iconic-game entry.

    Returns the new state, or None when the entry isn't found.
    """
    try:
        for e in (getattr(team, "iconic_games", None) or []):
            if isinstance(e, dict) and e.get("id") == entry_id:
                e["starred"] = not bool(e.get("starred"))
                return bool(e["starred"])
    except Exception:
        pass
    return None


def prune_iconic_games(league: Any) -> int:
    """Drop unstarred entries from prior seasons at season rollover.

    Starred entries persist indefinitely -- the user's curation is the
    franchise's permanent memory. Returns the number pruned.
    """
    pruned = 0
    try:
        try:
            season = int(getattr(league, "season_year", 0) or 0)
        except Exception:
            season = 0
        for team in (getattr(league, "teams", None) or []):
            try:
                lst = getattr(team, "iconic_games", None)
                if not isinstance(lst, list):
                    continue
                kept = []
                for e in lst:
                    if not isinstance(e, dict):
                        continue
                    try:
                        eseason = int(e.get("season", season) or season)
                    except Exception:
                        eseason = season
                    if e.get("starred") or eseason >= season:
                        kept.append(e)
                    else:
                        pruned += 1
                team.iconic_games = kept
            except Exception:
                continue
    except Exception:
        pass
    return pruned
