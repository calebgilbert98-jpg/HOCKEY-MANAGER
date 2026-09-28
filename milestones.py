"""Milestone watches: 500th goal, 1000th game, 300th win.

A milestone should arrive with ceremony, not as a box score footnote. This
module scans for approaching milestones once per game day (cheap: integer
reads off career totals), drives pre-game presentation (milestone watch
news, a louder building via arena_atmosphere's milestone_home flag, venue
notes: at home / vs former club / inside a rivalry), and records the moment
it happens into the narrative ledger with a four-viewpoint headline.

All defensive: unknown stats/positions/teams simply don't produce watches.
"""

from __future__ import annotations

from typing import (Any, Dict, List, Set, Tuple)


# kind -> (label, career stat attr, target, watch window, goalie-only?)
WATCH_DEFS = {
    "goals_500": ("500th career goal", "career_goals", 500, 5, False),
    "games_1000": ("1,000th career game", "career_games", 1000, 3, False),
    "wins_300": ("300th career win", "career_wins", 300, 3, True),
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
    remaining}]. Sorted by remaining (closest first).
    """
    watches: List[Dict[str, Any]] = []
    try:
        teams = getattr(league, "teams", None) or []
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
                for kind, (label, attr, target, window, goalie_only) in \
                        WATCH_DEFS.items():
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


def celebrated_key(watch: Dict[str, Any]) -> Tuple[Any, str]:
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
            _label, attr, target, _window, _g = WATCH_DEFS[w["kind"]]
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
        game_date = getattr(app, "current_date", None)
        spec = {
            "kind": "milestone_hit",
            "player": name,
            "milestone": label,
            "team": team,
            "game_date": game_date,
            "room_line": f"The room empties onto the ice -- {label} for {name}.",
            "fans_line": f"A standing ovation that doesn't end -- {name}'s {label}.",
            "media_line": f"{name} etches his name in: {label}, "
                          f"one of the game's immortal marks.",
            "league_line": f"The league salutes {name}: {label}.",
            "involved": (team,),
        }
        return bool(_deliver_spec(app, spec))
    except Exception:
        return False
