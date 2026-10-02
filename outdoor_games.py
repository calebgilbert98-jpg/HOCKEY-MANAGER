# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Legacy events: the Winter Classic and Stadium Series (additive).

One scheduling pass per season -- schedule_outdoor_games(league), called
right after league.generate_schedule() -- picks hosts and opponents, then
STAMPS the chosen regular-season home games (no 83rd game is added):

    game["outdoor"] = {"event", "venue", "capacity", "weather", "alumni",
                       "host", "season"}

The five spectacle ingredients:
- venue: a real stadium per franchise (capacity drives attendance).
- rivalry history: hosts/opponents are picked with the narrative ledger's
  memory weight, and the pre-game billing quotes it.
- alumni: a day-before alumni game, named from the franchise's Hall of
  Famers when the history has them, otherwise a scored result.
- weather framing: procedural game-day weather, PRESENTATION ONLY --
  disclosed in the billing, zero sim effect (the scoring band is not to
  be touched by spectacle).
- permanent season memory: results go to league.outdoor_history AND the
  narrative ledger (weight ~55), so future seasons' billing remembers
  who met outdoors and who won.

Game-day hooks (main.py): the outdoor stamp is read for the
_pre-game_atmosphere call (arena_atmosphere's outdoor flag pins the
building near-max -- the loudest night of the year), a pre-game inbox
note, and a post-game record_outdoor_result() call.

Perf: one pass over the schedule at season setup; dict lookups on game
days. Nothing per-tick.
"""

import random
from datetime import date
from typing import Any, Dict, List, Optional

# Franchise -> (stadium, capacity). Real outdoor hosts use their real
# venues; everyone else gets a plausible football stadium.
VENUES: Dict[str, tuple] = {
    "Boston Bruins": ("Fenway Park", 37755),
    "Buffalo Sabres": ("Highmark Stadium", 71767),
    "Detroit Red Wings": ("Michigan Stadium", 107601),
    "Florida Panthers": ("loanDepot park", 37446),
    "Montréal Canadiens": ("Olympic Stadium", 56000),
    "Ottawa Senators": ("TD Place", 24000),
    "Tampa Bay Lightning": ("Raymond James Stadium", 65890),
    "Toronto Maple Leafs": ("BMO Field", 27980),
    "Carolina Hurricanes": ("Carter-Finley Stadium", 56919),
    "Columbus Blue Jackets": ("Ohio Stadium", 102780),
    "New Jersey Devils": ("MetLife Stadium", 82500),
    "New York Islanders": ("Yankee Stadium", 46905),
    "New York Rangers": ("Citi Field", 41922),
    "Philadelphia Flyers": ("Citizens Bank Park", 42792),
    "Pittsburgh Penguins": ("Acrisure Stadium", 68400),
    "Washington Capitals": ("Nationals Park", 41339),
    "Chicago Blackhawks": ("Wrigley Field", 41649),
    "Colorado Avalanche": ("Coors Field", 46905),
    "Dallas Stars": ("Cotton Bowl", 92100),
    "Minnesota Wild": ("Huntington Bank Stadium", 50805),
    "Nashville Predators": ("Nissan Stadium", 69143),
    "St. Louis Blues": ("Busch Stadium", 43975),
    "Utah Hockey Club": ("Rice-Eccles Stadium", 51444),
    "Winnipeg Jets": ("Princess Auto Stadium", 33234),
    "Anaheim Ducks": ("Angel Stadium", 45517),
    "Calgary Flames": ("McMahon Stadium", 35650),
    "Edmonton Oilers": ("Commonwealth Stadium", 56302),
    "Los Angeles Kings": ("Dodger Stadium", 56000),
    "San Jose Sharks": ("Levi's Stadium", 68500),
    "Seattle Kraken": ("T-Mobile Park", 47929),
    "Vancouver Canucks": ("BC Place", 54500),
    "Vegas Golden Knights": ("Allegiant Stadium", 65000),
}

_WEATHER = [
    (-12, "clear skies", "-12°C under clear skies"),
    (-8, "light snow", "-8°C with light snow falling"),
    (-5, "snow flurries", "-5°C, flurries drifting across the ice"),
    (-2, "overcast", "-2°C and overcast, perfect outdoor hockey weather"),
    (1, "mild", "1°C, soft ice and long sleeves on the benches"),
    (-15, "bitter cold", "-15°C, breath hanging in the air"),
]


def _team_name(t: Any) -> str:
    return getattr(t, "team_name", "") or ""


def _ledger() -> Any:
    try:
        from narrative_ledger import active_ledger
        return active_ledger()
    except Exception:
        return None


def _memory_weight(home: str, away: str) -> float:
    try:
        led = _ledger()
        if led is not None:
            return float(led.memory_weight(home, away) or 0.0)
    except Exception:
        pass
    return 0.0


def _recent_hosts(league: Any, years: int = 3,
                 season_year: Optional[int] = None) -> set:
    """Hosts from the last `years` completed seasons -- the rotation
    window. A club that hosted four seasons ago is eligible again, the
    way real outdoor rotation works (Chicago 2009/2015/2019/2025)."""
    hosts = set()
    try:
        for rec in getattr(league, "outdoor_history", []) or []:
            name = rec.get("host")
            if not name:
                continue
            if season_year is None:
                hosts.add(name)
                continue
            try:
                start = int(str(rec.get("season") or "").split("-")[0])
            except (ValueError, IndexError):
                # Unparseable season label: stay conservative, exclude.
                hosts.add(name)
                continue
            # Completed seasons inside the window: [season_year - years,
            # season_year). The current season's games are stamped at
            # setup, before any record for it exists.
            if season_year - years <= start < season_year:
                hosts.add(name)
    except Exception:
        pass
    return {h for h in hosts if h}


def _nhl_teams(league: Any) -> List[Any]:
    try:
        return [t for t in (getattr(league, "teams", []) or [])
                if getattr(t, "league_name", "") == "National Hockey League"]
    except Exception:
        return []


def _home_games_vs(schedule: List[Any], host: Any, opp_name: str,
                   target: date) -> List[Dict[str, Any]]:
    hn = _team_name(host)
    out = []
    for g in schedule or []:
        if not isinstance(g, dict):
            continue
        if _team_name(g.get("home_team")) != hn:
            continue
        if _team_name(g.get("away_team")) != opp_name:
            continue
        if g.get("outdoor"):
            continue
        gd = g.get("date")
        if not hasattr(gd, "toordinal"):
            continue
        out.append(g)
    out.sort(key=lambda g: abs((g["date"] - target).days))
    return out


def _pick_opponent(league: Any, host: Any, schedule: List[Any],
                   target: date) -> Optional[Any]:
    """The scheduled home opponent nearest the target date with the most
    ledger history against the host -- rivalry first, then market."""
    hn = _team_name(host)
    cands = []
    for g in schedule or []:
        if not isinstance(g, dict) or g.get("outdoor"):
            continue
        if _team_name(g.get("home_team")) != hn:
            continue
        gd = g.get("date")
        if not hasattr(gd, "toordinal"):
            continue
        away = g.get("away_team")
        an = _team_name(away)
        w = _memory_weight(hn, an)
        dist = abs((gd - target).days)
        cands.append((w, -dist, an, away, g))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return cands[0][3]


def _make_weather(rng: random.Random) -> Dict[str, Any]:
    temp_c, short, framing = rng.choice(_WEATHER)
    return {"temp_c": temp_c, "condition": short, "framing": framing}


def _alumni_game(league: Any, home_name: str, away_name: str,
                 rng: random.Random) -> Dict[str, Any]:
    """Day-before alumni game. Names from franchise Hall of Famers when the
    history has them; otherwise just a scored result."""
    names = {home_name: [], away_name: []}
    try:
        hist = getattr(league, "league_history", None)
        hof = getattr(hist, "hall_of_fame", None) or []
        for h in hof:
            team = h.get("team") or h.get("franchise") or ""
            nm = h.get("name") or ""
            if team in names and nm and len(names[team]) < 3:
                names[team].append(nm)
    except Exception:
        pass
    hs = rng.randint(3, 7)
    aws = rng.randint(2, 6)
    if hs == aws:
        hs += 1
    return {
        "home_score": hs, "away_score": aws,
        "home_alumni": names[home_name], "away_alumni": names[away_name],
    }


def schedule_outdoor_games(league: Any, season_year: Optional[int] = None,
                           rng: Optional[random.Random] = None) -> List[Dict[str, Any]]:
    """Pick and stamp this season's outdoor games. Returns the infos."""
    rng = rng or random.Random()
    try:
        if season_year is None:
            season_year = int(getattr(league, "season_year", date.today().year))
    except Exception:
        season_year = date.today().year
    schedule = getattr(league, "schedule", None) or []
    teams = _nhl_teams(league)
    if not teams or not schedule:
        return []

    recent = _recent_hosts(league, years=3, season_year=season_year)
    stamped: List[Dict[str, Any]] = []
    used_hosts: set = set()

    def _stage(event: str, target: date, game_cap: int) -> None:
        cands = [t for t in teams
                 if _team_name(t) not in recent and _team_name(t) not in used_hosts]
        if not cands:
            return
        # Host score: big stadium + some ledger heat + noise. Rotation is
        # handled by the recent-host exclusion, not by punishing markets.
        scored = []
        for t in cands:
            tn = _team_name(t)
            venue, cap = VENUES.get(tn, (f"{tn} Memorial Stadium", 40000))
            heat = 0.0
            try:
                for o in teams:
                    if o is not t:
                        heat = max(heat, _memory_weight(tn, _team_name(o)))
            except Exception:
                pass
            scored.append((cap / 1000.0 + heat / 10.0 + rng.uniform(0, 8), t))
        scored.sort(key=lambda s: s[0], reverse=True)
        for _, host in scored:
            opp = _pick_opponent(league, host, schedule, target)
            if opp is None:
                continue
            games = _home_games_vs(schedule, host, _team_name(opp), target)
            if not games:
                continue
            g = games[0]
            hn = _team_name(host)
            venue, cap = VENUES.get(hn, (f"{hn} Memorial Stadium", 40000))
            info = {
                "event": event,
                "host": hn,
                "away": _team_name(opp),
                "venue": venue,
                "capacity": cap,
                "attendance": min(cap, int(cap * rng.uniform(0.93, 1.0))),
                "weather": _make_weather(rng),
                "alumni": _alumni_game(league, hn, _team_name(opp), rng),
                "season": f"{season_year}-{str(season_year + 1)[-2:]}",
                "rivalry_weight": _memory_weight(hn, _team_name(opp)),
            }
            g["outdoor"] = info
            used_hosts.add(hn)
            stamped.append(info)
            if len(stamped) >= game_cap:
                return

    # The Winter Classic: New Year's Day. Then 1-2 Stadium Series games on
    # February Saturdays.
    _stage("Winter Classic", date(season_year + 1, 1, 1), 1)
    _stage("Stadium Series", date(season_year + 1, 2, 14), 2)
    _stage("Stadium Series", date(season_year + 1, 2, 21), 3)
    return stamped


def outdoor_info_for(game: Any) -> Optional[Dict[str, Any]]:
    """Read the outdoor stamp off a schedule entry (dict or tuple)."""
    try:
        if isinstance(game, dict):
            return game.get("outdoor") or None
    except Exception:
        pass
    return None


def pregame_presentation(info: Dict[str, Any], ledger: Any = None) -> Dict[str, str]:
    """Billing copy for the inbox note and the visualizer feed."""
    event = info.get("event", "Outdoor Game")
    host, away = info.get("host", ""), info.get("away", "")
    venue = info.get("venue", "")
    wx = info.get("weather", {}) or {}
    alum = info.get("alumni", {}) or {}
    att = info.get("attendance", 0)

    title = f"{event}: {away} at {host}"
    venue_line = (f"Outdoors at {venue} -- {att:,} fans braving "
                  f"{wx.get('framing', 'the cold')}.")
    if alum:
        hs, aws = alum.get("home_score", 0), alum.get("away_score", 0)
        hn = ", ".join((alum.get("home_alumni") or [])[:2])
        an = ", ".join((alum.get("away_alumni") or [])[:2])
        who = f" ({hn})" if hn else ""
        whoa = f" ({an})" if an else ""
        alumni_line = (f"Yesterday's alumni game: {host}{who} {hs}, "
                       f"{away}{whoa} {aws}.")
    else:
        alumni_line = ""
    w = float(info.get("rivalry_weight") or 0.0)
    if w >= 60:
        rivalry_line = (f"Bad blood under the open sky -- these two have "
                        f"history, and {att:,} witnesses.")
    elif w >= 30:
        rivalry_line = "Some history between these two adds an edge."
    else:
        rivalry_line = "A new chapter, written outdoors."
    return {"title": title, "venue_line": venue_line,
            "alumni_line": alumni_line, "rivalry_line": rivalry_line}


def record_outdoor_result(app: Any, info: Dict[str, Any],
                          home_score: int, away_score: int) -> Dict[str, Any]:
    """Permanent season memory: league history + narrative ledger."""
    host, away = info.get("host"), info.get("away")
    winner = host if home_score > away_score else away
    rec = {
        "season": info.get("season"), "event": info.get("event"),
        "host": host, "away": away,
        "venue": info.get("venue"), "attendance": info.get("attendance"),
        "weather": (info.get("weather") or {}).get("framing"),
        "home_score": home_score, "away_score": away_score,
        "winner": winner,
    }
    try:
        league = getattr(app, "league", app)
        hist = getattr(league, "outdoor_history", None)
        if hist is None:
            league.outdoor_history = hist = []
        if not any(r.get("season") == rec["season"]
                   and r.get("event") == rec["event"]
                   and r.get("host") == rec["host"] for r in hist):
            hist.append(rec)
    except Exception:
        pass
    # The ledger remembers outdoor meetings so future billing can callback.
    # Idempotent like the history append above: re-sims don't double-count.
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app)
        _prior = led.between(host, away, kinds=["outdoor_game"]) \
            if hasattr(led, "between") else []
        _dup = any(e.get("facts", {}).get("season") == info.get("season")
                   and e.get("facts", {}).get("event") == info.get("event")
                   for e in _prior)
        if not _dup:
            led.record(
                "outdoor_game", teams=[host, away], weight=55,
                facts={"event": info.get("event"),
                       "season": info.get("season"),
                       "venue": info.get("venue"), "winner": winner,
                       "score": f"{home_score}-{away_score}"},
                text=f"{winner} won the {info.get('season')} "
                     f"{info.get('event')} {home_score}-{away_score} at "
                     f"{info.get('venue')}.",
            )
    except Exception:
        pass
    # Narrative ignition (Muck 2026-10-02): outdoor games are can't-miss
    # events -- they get a headline, not just a ledger entry.
    try:
        from headlines import deliver_spec as _deliver_spec
        _deliver_spec(app, {
            "kind": "special_event",
            "event_kind": "outdoor_game",
            "text": f"{winner} won the {info.get('season')} "
                    f"{info.get('event')} {home_score}-{away_score} at "
                    f"{info.get('venue')} "
                    f"({info.get('attendance', '')} fans braved the cold).",
            "home": host, "away": away,
            "involved": (host, away),
        })
    except Exception:
        pass
    return rec
