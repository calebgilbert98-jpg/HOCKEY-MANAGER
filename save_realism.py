# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""New-save realism (Muck 2026-10-02).

When a new save starts, the world should already be alive -- not a blank
slate. This module simulates training camp (Sep 12-30) and the preseason
schedule during new-save setup, so opening night arrives with:

- camp ratings/standouts on every club (training_camp system),
- preseason results (scores only -- exhibitions never touch season lines),
- camp + preseason storylines in the news feed,
- current_date advanced past September to opening night.

Entry point: simulate_camp_and_preseason(manager), called from
GameManager.setup_new_game() after schedule generation. Everything is
never-raises; a failure here must never block new-save creation.
"""

import random
from datetime import date

# Camp window mirrors training_camp.CAMP_START/CAMP_END.
_CAMP_START = (9, 12)
_CAMP_END = (9, 30)


def _is_nhl_team(team):
    try:
        return str(getattr(team, "league_name", "") or "") == "National Hockey League"
    except Exception:
        return False


def _team_map(league):
    """team_name -> Team for NHL clubs."""
    out = {}
    try:
        for t in (getattr(league, "teams", None) or []):
            if _is_nhl_team(t):
                out[str(getattr(t, "team_name", ""))] = t
    except Exception:
        pass
    return out


def _run_camp(league, year):
    """Drive every camp day Sep 12-30 through the existing camp system."""
    try:
        import training_camp as _tc
    except Exception:
        return
    for day in range(_CAMP_START[1], _CAMP_END[1] + 1):
        try:
            _tc.run_camp_day(league, date(year, 9, day), app=None)
        except Exception:
            continue


def _preseason_games(league):
    """Yield (game_date, home_name, away_name) for preseason schedule entries."""
    try:
        schedule = getattr(league, "schedule", None) or []
    except Exception:
        return
    for g in schedule:
        try:
            if not isinstance(g, dict) or not g.get("preseason"):
                continue
            gd = g.get("date")
            home = g.get("home_team")
            away = g.get("away_team")
            if gd is None or not home or not away:
                continue
            yield gd, str(home), str(away)
        except Exception:
            continue


def _sim_preseason(manager, league):
    """Sim every preseason game via the lightweight engine (preseason=True).

    Returns (results, records): results is a list of
    (game_date, home, away, home_goals, away_goals); records maps
    team_name -> [w, l, otl].
    """
    results = []
    records = {}
    try:
        teams = _team_map(league)
    except Exception:
        return results, records
    for gd, home_name, away_name in _preseason_games(league):
        try:
            home = teams.get(home_name)
            away = teams.get(away_name)
            if home is None or away is None:
                continue
            # Lightweight sim, preseason=True: scores stand, season lines
            # untouched, injuries still possible (shared rate).
            winner, loser, (hg, ag), went_ot = \
                manager._simulate_game_lightweight(home, away, preseason=True)
            results.append((gd, home_name, away_name, hg, ag))
            for nm in (home_name, away_name):
                records.setdefault(nm, [0, 0, 0])
            if winner is home:
                records[home_name][0] += 1
                records[away_name][1 if not went_ot else 2] += 1
            else:
                records[away_name][0] += 1
                records[home_name][1 if not went_ot else 2] += 1
        except Exception:
            continue
    return results, records


def _camp_storylines(league):
    """Collect (date, story) tuples from camp results: standouts, busts."""
    stories = []
    try:
        for team in (getattr(league, "teams", None) or []):
            if not _is_nhl_team(team):
                continue
            tname = str(getattr(team, "team_name", ""))
            for p in (getattr(team, "camp_roster", None) or []):
                try:
                    if bool(getattr(p, "camp_standout", False)):
                        avg = float(getattr(p, "camp_avg", 0.0) or 0.0)
                        stories.append((
                            date(2026, 9, 30),
                            f"🏕️ CAMP STANDOUT: {p.first_name} {p.last_name} "
                            f"({tname}) turned heads with a {avg:.1f} camp "
                            f"average -- forcing his way into the roster conversation.",
                        ))
                    elif float(getattr(p, "camp_avg", 99) or 99) <= 4.0:
                        ratings = list(getattr(p, "camp_ratings", None) or [])
                        if len(ratings) >= 2:
                            stories.append((
                                date(2026, 9, 30),
                                f"🏕️ CAMP DISAPPOINTMENT: {p.first_name} "
                                f"{p.last_name} ({tname}) struggled to a "
                                f"{float(getattr(p, 'camp_avg', 0)):.1f} camp "
                                f"average -- his roster spot is in jeopardy.",
                            ))
                except Exception:
                    continue
    except Exception:
        pass
    # Cap: the league doesn't need 200 camp stories. Keep the best ones.
    random.shuffle(stories)
    return stories[:12]


def _preseason_storylines(records, results):
    """(date, story) tuples from preseason results."""
    stories = []
    try:
        if not records:
            return stories
        # Best / worst preseason clubs.
        ranked = sorted(records.items(),
                        key=lambda kv: (kv[1][0], -kv[1][1]), reverse=True)
        if ranked:
            best, (bw, bl, bo) = ranked[0]
            stories.append((
                date(2026, 9, 30),
                f"🏒 PRESEASON: {best} finished the exhibition slate "
                f"{bw}-{bl}-{bo}, looking sharp ahead of opening night.",
            ))
            worst, (ww, wl, wo) = ranked[-1]
            if worst != best:
                stories.append((
                    date(2026, 9, 30),
                    f"🏒 PRESEASON: {worst} stumbled to {ww}-{wl}-{wo} in "
                    f"exhibitions -- questions already swirling.",
                ))
        # Highest-scoring exhibition.
        if results:
            hg_game = max(results, key=lambda r: r[3] + r[4])
            _gd, _h, _a, _hg, _ag = hg_game
            if _hg + _ag >= 8:
                stories.append((
                    date(2026, 9, 30),
                    f"🏒 PRESEASON SHOOTOUT: {_h} edged {_a} {_hg}-{_ag} "
                    f"in the wildest exhibition of September.",
                ))
    except Exception:
        pass
    return stories


def _opening_night(league, year):
    """First non-preseason game date, or Oct 1 as fallback."""
    try:
        best = None
        for g in (getattr(league, "schedule", None) or []):
            try:
                if not isinstance(g, dict) or g.get("preseason"):
                    continue
                gd = g.get("date")
                if gd is None:
                    continue
                if best is None or gd < best:
                    best = gd
            except Exception:
                continue
        if best is not None:
            return best
    except Exception:
        pass
    return date(year, 10, 1)


def simulate_camp_and_preseason(manager):
    """Simulate camp + preseason during new-save setup. Never raises.

    Called from GameManager.setup_new_game() after the schedule exists.
    Leaves league.preseason_stories (chronological (date, story) list)
    for the GUI to merge into the news feed, and advances
    manager.current_date to opening night.
    """
    try:
        league = getattr(manager, "league", None)
        if league is None:
            return
        year = int(getattr(league, "season_year", 2026) or 2026)

        # 1. Training camp: Sep 12-30 through the existing system.
        _run_camp(league, year)

        # 2. Preseason exhibitions: fast lightweight sim, no season lines.
        _results, _records = _sim_preseason(manager, league)
        try:
            league.preseason_results = [
                {"date": gd.isoformat() if hasattr(gd, "isoformat") else str(gd),
                 "home": h, "away": a, "home_goals": hg, "away_goals": ag}
                for gd, h, a, hg, ag in _results
            ]
        except Exception:
            pass

        # 3. Storylines feed the narrative system.
        stories = []
        try:
            stories.extend(_camp_storylines(league))
            stories.extend(_preseason_storylines(_records, _results))
        except Exception:
            pass
        try:
            stories.sort(key=lambda s: s[0])
            league.preseason_stories = [
                {"date": d, "story": s} for d, s in stories
            ]
        except Exception:
            try:
                league.preseason_stories = []
            except Exception:
                pass

        # 4. The world starts at opening night, not Sep 1.
        try:
            manager.current_date = _opening_night(league, year)
        except Exception:
            pass
    except Exception:
        pass
