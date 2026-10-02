# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Milestone watches: 500th goal, 500th assist, 1000th point, 1000th game,
300th win, 50-goal season, 100-point season.

A milestone should arrive with ceremony, not as a box score footnote. This
module scans for approaching milestones once per game day (cheap: integer
reads off career/season totals), drives pre-game presentation (milestone
watch news with escalating chase copy, a louder building via
arena_atmosphere's milestone_home flag, venue notes: at home / vs former
club / inside a rivalry), and records the moment it happens into the
narrative ledger with a four-viewpoint headline enriched with historical
context (Nth to do it, fastest ever, etc.).

Career chases persist across seasons (career totals never reset); season
chases reset. All defensive: unknown stats/positions/teams simply don't
produce watches.
"""

from __future__ import annotations

from typing import (Any, Dict, List, Set, Tuple)


# kind -> (label, career stat attr, target, watch window, goalie-only?, scope)
# scope "career" = lifetime totals, chase persists across seasons.
# scope "season" = current-season totals, chase resets each season.
WATCH_DEFS = {
    # -- Career milestones -----------------------------------------------
    "goals_500": ("500th career goal", "career_goals", 500, 5, False,
                  "career"),
    "assists_500": ("500th career assist", "career_assists", 500, 8, False,
                    "career"),
    "points_1000": ("1,000th career point", "career_points", 1000, 10, False,
                    "career"),
    "games_1000": ("1,000th career game", "career_games", 1000, 3, False,
                   "career"),
    "wins_300": ("300th career win", "career_wins", 300, 3, True,
                 "career"),
    # -- Season milestones -----------------------------------------------
    "season_goals_50": ("50-goal season", "goals", 50, 4, False,
                       "season"),
    "season_points_100": ("100-point season", "points", 100, 6, False,
                         "season"),
}


def _is_goalie(player: Any) -> bool:
    try:
        pos = getattr(player, "primary_position", None)
        return str(getattr(pos, "name", pos or "")).upper() == "GOALIE"
    except Exception:
        return False


def _player_name(player: Any) -> str:
    try:
        return (getattr(player, "full_name", None)
                or getattr(player, "name", None)
                or "A player")
    except Exception:
        return "A player"


def scan_watches(league: Any) -> List[Dict[str, Any]]:
    """One scan per game day: every active watch in the league.

    Returns [{player, team, team_name, kind, label, current, target,
    remaining, scope, season_year}]. Sorted by remaining (closest first).
    """
    watches: List[Dict[str, Any]] = []
    try:
        teams = getattr(league, "teams", None) or []
        season_year = getattr(league, "season_year", None)
    except Exception:
        return watches
    for team in teams:
        try:
            team_name = getattr(team, "team_name", "")
            roster = getattr(team, "roster", None) or []
        except Exception:
            continue
        for player in roster:
            try:
                goalie = _is_goalie(player)
                for kind, (label, attr, target, window, goalie_only,
                           scope) in WATCH_DEFS.items():
                    if goalie_only and not goalie:
                        continue
                    if not goalie_only and goalie and kind != "games_1000":
                        continue
                    current = int(getattr(player, attr, 0) or 0)
                    remaining = target - current
                    if 0 < remaining <= window:
                        watches.append({
                            "player": player,
                            "player_id": getattr(player, "id", None),
                            "player_name": _player_name(player),
                            "team": team,
                            "team_name": team_name,
                            "kind": kind,
                            "label": label,
                            "current": current,
                            "target": target,
                            "remaining": remaining,
                            "is_goalie": goalie,
                            "scope": scope,
                            "season_year": season_year,
                        })
            except Exception:
                continue
    watches.sort(key=lambda w: (w["remaining"], w["kind"]))
    return watches


def watch_teams_tonight(watches: List[Dict[str, Any]],
                        threshold: int = 2) -> Set[str]:
    """Team names with a watch close enough that tonight could be the night."""
    return {w["team_name"] for w in watches
            if w.get("remaining", 99) <= threshold and w.get("team_name")}


def venue_note(watch: Dict[str, Any], home_team: Any, away_team: Any,
               ledger: Any = None) -> str:
    """Where the milestone would happen: home ice, former club, rivalry."""
    notes: List[str] = []
    try:
        team_name = watch.get("team_name", "")
        home_name = getattr(home_team, "team_name", "")
        if team_name and team_name == home_name:
            notes.append("at home")
        # Former club: the player facing the team he used to play for.
        former = getattr(watch.get("player"), "former_teams", None) or []
        opp_name = getattr(away_team, "team_name", "")
        if team_name == home_name:
            opp_name = getattr(away_team, "team_name", "")
        else:
            opp_name = home_name
        for f in former:
            fname = f if isinstance(f, str) else getattr(f, "team_name", "")
            if fname and fname == opp_name:
                notes.append(f"against his former club ({fname})")
                break
    except Exception:
        pass
    # Inside a rivalry: the ledger knows the matchup's weight.
    try:
        if ledger is not None and home_team is not None \
                and away_team is not None:
            hn = getattr(home_team, "team_name", "")
            an = getattr(away_team, "team_name", "")
            if hn and an and float(
                    ledger.memory_weight(hn, an) or 0.0) >= 40.0:
                notes.append("in the middle of a feud")
    except Exception:
        pass
    return ", ".join(notes)


def chase_copy(watch: Dict[str, Any]) -> str:
    """Escalating countdown narrative for an approaching milestone.

    The closer the chase, the heavier the language -- 5 away is a note,
    1 away is an event.
    """
    try:
        name = watch.get("player_name", "A player")
        label = watch.get("label", "a milestone")
        remaining = int(watch.get("remaining", 99) or 99)
        scope = watch.get("scope", "career")
        if remaining <= 1:
            return (f"ONE away. {name} sits on the brink of his {label} -- "
                    f"tonight could be history.")
        if remaining == 2:
            return (f"Milestone watch: {name} is 2 away from his {label}. "
                    f"It could happen tonight.")
        if remaining <= 4:
            return (f"Chasing history: {name} is {remaining} away from his "
                    f"{label}, closing in fast.")
        unit = "career" if scope == "career" else "season"
        return (f"On the radar: {name} is {remaining} away from a "
                f"{label} this {unit}.")
    except Exception:
        return ""


def historical_context(league: Any, kind: str,
                       player: Any) -> Dict[str, str]:
    """Where this milestone sits in history: Nth to do it, fastest ever.

    Counts every skater/goalie already past the threshold (active rosters)
    plus already-celebrated hits this save. 'Fastest' compares games played:
    if the hitter needed fewer games than anyone else past the mark, it's
    the fastest.
    """
    out = {"club_line": "", "pace_line": ""}
    try:
        _def = WATCH_DEFS.get(kind)
        if not _def:
            return out
        _label, attr, target = _def[0], _def[1], _def[2]
        hitter_games = int(getattr(player, "career_games", 0) or 0)
        hitter_id = getattr(player, "id", None)
        achievers = 0
        fastest_games = None
        try:
            teams = getattr(league, "teams", None) or []
        except Exception:
            teams = []
        for team in teams:
            try:
                roster = getattr(team, "roster", None) or []
            except Exception:
                continue
            for p in roster:
                try:
                    if getattr(p, "id", None) == hitter_id:
                        continue
                    if int(getattr(p, attr, 0) or 0) >= target:
                        achievers += 1
                        pg = int(getattr(p, "career_games", 0) or 0)
                        if pg > 0 and (fastest_games is None
                                       or pg < fastest_games):
                            fastest_games = pg
                except Exception:
                    continue
        # Already-celebrated hits this save (retired/departed achievers).
        try:
            celebrated = getattr(league, "_milestone_celebrated", None) or set()
            for key in celebrated:
                try:
                    if isinstance(key, (tuple, list)) and len(key) >= 2 \
                            and key[1] == kind:
                        achievers += 1
                except Exception:
                    continue
        except Exception:
            pass
        n = achievers + 1
        if n == 1:
            out["club_line"] = (f"The first ever to reach {target} "
                                f"{_label.split(' ', 1)[-1]}.")
        elif n <= 3:
            out["club_line"] = (f"Joins immortal company -- only the {n}th "
                                f"to reach {_label}.")
        else:
            out["club_line"] = (f"Becomes the {n}th to reach {_label}.")
        if hitter_games > 0 and (fastest_games is None
                                 or hitter_games <= fastest_games):
            out["pace_line"] = (f"The fastest ever to {_label}, in just "
                                f"{hitter_games} games.")
        elif hitter_games > 0 and fastest_games:
            out["pace_line"] = (f"Reaches {_label} in {hitter_games} games.")
    except Exception:
        pass
    return out


def carryover_chases(app: Any) -> int:
    """Cross-season continuity: career chases that survived the offseason
    get a 'the chase resumes' news item, once per season.

    Returns the number of carryover notes emitted.
    """
    emitted = 0
    try:
        import milestones as _ms
    except Exception:
        return emitted
    try:
        league = getattr(app, "league", None)
        if league is None:
            return emitted
        season_year = getattr(league, "season_year", None)
        noted = getattr(league, "_milestone_carryover_noted", None)
        if not isinstance(noted, set):
            noted = set()
            league._milestone_carryover_noted = noted
        if season_year in noted:
            return emitted
        watches = _ms.scan_watches(league)
        career = [w for w in watches if w.get("scope") == "career"]
        if not career:
            noted.add(season_year)
            return emitted
        add_news = getattr(app, "add_news", None)
        for w in career:
            try:
                line = (f"The chase resumes: {w['player_name']} opens the "
                        f"season {w['remaining']} away from his {w['label']}.")
                if callable(add_news):
                    add_news(line)
                emitted += 1
            except Exception:
                continue
        noted.add(season_year)
    except Exception:
        pass
    return emitted


def celebrated_key(watch: Dict[str, Any]) -> Tuple[Any, ...]:
    """Idempotency key. Season-scoped milestones include the season year so
    a 50-goal season can be celebrated again next year."""
    try:
        if watch.get("scope") == "season":
            return (watch.get("player_id"), watch.get("kind", ""),
                    watch.get("season_year"))
    except Exception:
        pass
    return (watch.get("player_id"), watch.get("kind", ""))


def check_hits(league: Any, watches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Milestones reached since the last scan. Idempotent: marks celebrated.

    Call once at end of day, after sims updated career totals. Returns the
    watches that just hit and weren't celebrated before.
    """
    hits: List[Dict[str, Any]] = []
    try:
        celebrated = getattr(league, "_milestone_celebrated", None)
        if not isinstance(celebrated, set):
            celebrated = set()
            league._milestone_celebrated = celebrated
    except Exception:
        return hits
    for w in watches or []:
        try:
            key = celebrated_key(w)
            if key in celebrated:
                continue
            _def = WATCH_DEFS[w["kind"]]
            _label, attr, target = _def[0], _def[1], _def[2]
            current = int(getattr(w["player"], attr, 0) or 0)
            if current >= target:
                w = dict(w)
                w["current"] = current
                hits.append(w)
                celebrated.add(key)
        except Exception:
            continue
    return hits


def record_milestone_hit(app: Any, hit: Dict[str, Any],
                         home_team_name: str = "",
                         away_team_name: str = "") -> bool:
    """Ledger event + four-viewpoint headline for a milestone hit.

    Returns True when the headline was delivered.
    """
    try:
        from narrative_ledger import get_ledger
        from headlines import deliver_spec as _deliver_spec
    except Exception:
        return False
    try:
        name = hit.get("player_name", "A player")
        label = hit.get("label", "a milestone")
        team = hit.get("team_name", "")
        kind = hit.get("kind", "")
        facts = {"player": name, "milestone": label, "team": team,
                 "at_home": team == home_team_name}
        try:
            led = get_ledger(app)
            # record(): the ledger's append API (a previous led.add() call
            # silently no-oped, so milestone entries never landed).
            led.record(kind="milestone", weight=70,
                       teams=[team, away_team_name or home_team_name],
                       players=[name],
                       text=f"{name} reaches {label}",
                       facts=facts)
        except Exception:
            pass
        # Historical weight: Nth to do it, fastest ever.
        hist_lines = []
        hist = {}
        try:
            league = getattr(app, "league", None)
            hist = historical_context(league, kind, hit.get("player")) or {}
            if hist.get("club_line"):
                hist_lines.append(hist["club_line"])
            if hist.get("pace_line"):
                hist_lines.append(hist["pace_line"])
        except Exception:
            hist = {}
        hist_text = " ".join(hist_lines)
        game_date = getattr(app, "current_date", None)
        media_line = (f"{name} etches his name in: {label}, "
                      f"one of the game's immortal marks.")
        if hist_text:
            media_line += f" {hist_text}"
        fans_line = (f"A standing ovation that doesn't end -- {name}'s "
                     f"{label}.")
        if hist.get("pace_line"):
            fans_line += f" {hist['pace_line']}"
        spec = {
            "kind": "milestone_hit",
            "player": name,
            "milestone": label,
            "team": team,
            "game_date": game_date,
            "room_line": f"The room empties onto the ice -- {label} for {name}.",
            "fans_line": fans_line,
            "media_line": media_line,
            "league_line": f"The league salutes {name}: {label}."
                           + (f" {hist['club_line']}" if hist.get("club_line") else ""),
            "involved": (team,),
        }
        return bool(_deliver_spec(app, spec))
    except Exception:
        return False
