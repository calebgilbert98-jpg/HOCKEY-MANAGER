# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""AHL narratives -- the farm league as part of the living story ecosystem.

Muck's directive: the AHL isn't a separate world. Calder Cup races,
standout prospects knocking on the door, Cinderella runs, and callup
stories all feed the SAME narrative/media/headline systems as the NHL
(Buckets 1-5). No parallel story machinery.

Triggers (checked weekly from the daily maintenance path):
  - calder_race: teams bunched around the playoff cut line late season
  - prospect_watch: a farm standout with elite P/GP "knocking on the door"
  - cinderella: a low seed winning a Calder Cup series
  - callup: a hot AHL scorer earning NHL minutes (detected, not hooked)

Delivery: headlines.make_headline("ahl_story") + headlines.deliver,
so inbox, news feed, and daily caps all behave identically to NHL
stories.

Never raises: every entry point is try/except guarded.
"""

from datetime import date

_NARRATIVE_COOLDOWN_DAYS = 14
_RACE_CUTOFF_MONTH = 1  # Calder races matter from January on
_RACE_BAND_PTS = 4  # within 4 pts of the cut line = "in the race"
_PROSPECT_MIN_GP = 15
_PROSPECT_MIN_PPG = 1.0


def _team_name(team):
    try:
        return str(getattr(team, "team_name", "AHL club"))
    except Exception:
        return "AHL club"


def _pname(p):
    try:
        return (getattr(p, "full_name", None)
                or getattr(p, "name", None) or "Unknown")
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# Narrative generators (pure: build the story dict, don't deliver)
# ---------------------------------------------------------------------------

def calder_race_narrative(league, current_date=None):
    """A tight Calder Cup playoff race: teams bunched at the cut line."""
    try:
        import ahl_league as _al
        teams = _al.ahl_team_list(league)
        if len(teams) < 16:
            return None
        # Only late-season.
        try:
            d = current_date
            month = d.month if hasattr(d, "month") else 1
            if month < _RACE_CUTOFF_MONTH or month > 4:
                return None
        except Exception:
            pass
        rows = _al.get_ahl_standings(league)
        if len(rows) < 16:
            return None
        cut_pts = int(rows[15][1].get("pts", 0))
        in_race = []
        for idx, rec in rows:
            try:
                pts = int(rec.get("pts", 0))
                if abs(pts - cut_pts) <= _RACE_BAND_PTS:
                    in_race.append((_al._tname(teams, idx), pts))
            except Exception:
                continue
        if len(in_race) < 3:
            return None
        names = ", ".join(n for n, _ in in_race[:6])
        return {
            "story_type": "calder_race",
            "headline": f"Calder Cup race tightening: {len(in_race)} "
                        f"clubs within {_RACE_BAND_PTS} points",
            "body": (f"The AHL playoff picture is a logjam. {names} "
                     f"are separated by {_RACE_BAND_PTS} points around the "
                     f"cut line with the regular season winding down. "
                     f"Every point matters now."),
            "team_name": in_race[0][0],
            "involved": [n for n, _ in in_race],
        }
    except Exception:
        return None


def prospect_watch_narrative(league, user_team=None):
    """A farm standout tearing it up -- 'knocking on the door'."""
    try:
        import ahl_system as _ahl

        class _FakeLeague:
            def __init__(self, teams):
                self.teams = teams

        teams = list(getattr(league, "teams", None) or [])
        cooks = _ahl.cooking(_FakeLeague(teams), limit=5)
        best = None
        for p, tname, led, ppg in cooks:
            try:
                if int(getattr(led, "games_played", 0) or 0) < _PROSPECT_MIN_GP:
                    continue
                if float(ppg) < _PROSPECT_MIN_PPG:
                    continue
                best = (p, tname, led, ppg)
                break
            except Exception:
                continue
        if best is None:
            return None
        p, tname, led, ppg = best
        name = _pname(p)
        age = getattr(p, "age", "")
        pts = int(getattr(led, "goals", 0) or 0) + int(
            getattr(led, "assists", 0) or 0)
        gp = int(getattr(led, "games_played", 0) or 0)
        yours = ""
        try:
            if user_team is not None:
                for t in teams:
                    if getattr(t, "team_name", None) == getattr(
                            user_team, "team_name", None):
                        # is this prospect on the user's farm?
                        farm = getattr(t, "ahl_roster", None) or []
                        if any(getattr(q, "full_name", None) ==
                               getattr(p, "full_name", None)
                               for q in farm):
                            yours = " Your prospect is knocking."
                            break
        except Exception:
            pass
        return {
            "story_type": "prospect_watch",
            "headline": f"{name} knocking on the door "
                        f"({ppg:.2f} P/GP in the AHL)",
            "body": (f"{name} ({tname}{', age ' + str(age) if age else ''}) "
                     f"has {pts} points in {gp} AHL games and is forcing "
                     f"the conversation upstairs.{yours}"),
            "team_name": tname,
            "involved": [tname],
        }
    except Exception:
        return None


def cinderella_narrative(league):
    """A low seed won a Calder Cup series -- Cinderella run."""
    try:
        import ahl_league as _al
        bracket = getattr(league, "ahl_bracket", None)
        if not isinstance(bracket, dict):
            return None
        seen = getattr(league, "_ahl_cinderella_noted", None)
        if not isinstance(seen, set):
            seen = set()
            league._ahl_cinderella_noted = seen
        teams = _al.ahl_team_list(league)
        # Seeds: bracket rounds store (home, away) as AHL indices; the
        # first-round pairings are 1v16, 2v15 ... per _bracket_pairings.
        # A "Cinderella" = a team seeded 13-16 winning any series.
        rows = _al.get_ahl_standings(league)
        seed_of = {}
        for seed, (idx, _rec) in enumerate(rows[:16], 1):
            seed_of[idx] = seed
        for ri, rnd in enumerate(bracket.get("rounds", [])):
            for si, s in enumerate(rnd):
                try:
                    key = (ri, si)
                    if key in seen:
                        continue
                    w = int(s["winner"])
                    seed = seed_of.get(w)
                    if seed is not None and seed >= 13:
                        seen.add(key)
                        wn = _al._tname(teams, w)
                        rn_names = ["first round", "second round",
                                    "conference finals", "Calder Cup final"]
                        rn = (rn_names[ri] if ri < len(rn_names)
                              else f"round {ri + 1}")
                        return {
                            "story_type": "cinderella",
                            "headline": f"Cinderella in the AHL: "
                                        f"No. {seed} seed {wn} advances",
                            "body": (f"The {wn} just keep winning. Seeded "
                                     f"No. {seed}, they took the {rn} and "
                                     f"the Calder Cup dream is alive."),
                            "team_name": wn,
                            "involved": [wn],
                        }
                except Exception:
                    continue
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Weekly driver (called from the daily maintenance path)
# ---------------------------------------------------------------------------

def maybe_fire_ahl_narratives(app, league=None, current_date=None):
    """Fire at most one AHL narrative per week. Returns True if fired."""
    try:
        if league is None:
            try:
                gm = getattr(app, "game_manager", app)
                league = getattr(gm, "league", None)
            except Exception:
                league = None
        if league is None:
            return False
        # Weekly gate + cooldown.
        try:
            last = getattr(league, "_ahl_narrative_last", None)
            if last and current_date:
                from datetime import date as _d
                d_now = (current_date if hasattr(current_date, "date")
                         else _d.fromisoformat(str(current_date)[:10]))
                d_then = (_d.fromisoformat(str(last)[:10])
                          if isinstance(last, str) else last)
                if (d_now - d_then).days < 7:
                    return False
        except Exception:
            pass

        user_team = None
        try:
            gm = getattr(app, "game_manager", app)
            user_team = getattr(gm, "user_team", None)
        except Exception:
            pass

        story = None
        # Cinderella takes priority (playoff moment), then races, then
        # the weekly prospect watch.
        for gen in (lambda: cinderella_narrative(league),
                    lambda: calder_race_narrative(league, current_date),
                    lambda: prospect_watch_narrative(league, user_team)):
            try:
                story = gen()
            except Exception:
                story = None
            if story:
                break
        if not story:
            return False

        try:
            from headlines import make_headline, deliver
            d = current_date or date.today()
            msg = make_headline(
                "ahl_story", d,
                headline=story["headline"],
                body=story["body"],
                story_type=story["story_type"],
                team_name=story.get("team_name", ""))
            if msg is None:
                return False
            ok = deliver(app, msg, involved=tuple(
                story.get("involved", ())))
            if ok:
                try:
                    league._ahl_narrative_last = str(d)[:10]
                except Exception:
                    pass
            return bool(ok)
        except Exception:
            return False
    except Exception:
        return False
