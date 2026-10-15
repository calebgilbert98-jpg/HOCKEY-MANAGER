#!/usr/bin/env python3
"""R8d: game-heroics bucket tests (S item).

Bucket under test: daily_news._heroics_stories. Conventions: synthetic
SimpleNamespace app/team/player fixtures (same shape as the R8a/R8b/R8c
tests); assertions on premises, not phrasing.

The bucket is a presentation layer over the league's persisted per-game
recap feed (league._results_by_date -> game result dicts with per-player
game_stats lines, scores, overtime/shootout flags, notable Goal events).
Tests assert the bucket names the true hero with true numbers, the true
team, and a true score; and that it stays silent on degenerate state,
outside the season window, and on false premises (a 2-goal game is not a
hat trick; a 1-goal-against game is not a shutout; a shootout winner is
not an OT winner).
"""
import sys
import os
import types
import random
from datetime import date

_REPO = os.environ.get("R8D_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn

_PID = [0]


def mkplayer(fn, ln, pos, pid=None):
    _PID[0] += 1
    return types.SimpleNamespace(
        first_name=fn, last_name=ln,
        primary_position=types.SimpleNamespace(value=pos),
        id=pid if pid is not None else _PID[0])


def mkteam(name, roster, league_name="National Hockey League"):
    return types.SimpleNamespace(team_name=name, league_name=league_name,
                                 roster=list(roster))


def line(p, g=0, a=0, saves=0):
    return {"player": p, "g": g, "a": a, "saves": saves}


def goal_event(p, team_name, period, time="12:34"):
    return {"event": "Goal", "player": p, "team": team_name,
            "period": period, "time": time}


def mkresult(home, away, hs, aws, gstats, overtime=False, shootout=False,
             events=None, winner=None):
    if winner is None:
        winner = home if hs > aws else away
    return {
        "date": None,
        "home_team": home, "away_team": away,
        "home_score": hs, "away_score": aws,
        "winner": winner,
        "game_stats": dict(gstats),
        "notable_events": list(events or []),
        "overtime": overtime, "shootout": shootout,
    }


GAME_DAY = date(2027, 1, 14)
NEWS_DAY = date(2027, 1, 15)  # production: news runs after the date bump


def mkapp(results, season_year=2026):
    lg = types.SimpleNamespace(
        teams=[], season_year=season_year,
        _results_by_date={GAME_DAY: list(results)})
    return types.SimpleNamespace(league=lg, _daily_news_recent={})


def stories(app, day=NEWS_DAY, seed=7):
    return dn._heroics_stories(app, day, random.Random(seed))


def std_pair():
    """Two NHL teams with a skater + goalie each; returns dict of parts."""
    s1 = mkplayer("Sid", "Crosby", "C")
    g1 = mkplayer("Marc", "Fleury", "G")
    s2 = mkplayer("Alex", "Ovechkin", "LW")
    g2 = mkplayer("Braden", "Holtby", "G")
    home = mkteam("Pittsburgh Penguins", [s1, g1])
    away = mkteam("Washington Capitals", [s2, g2])
    return locals()


def names(sts):
    return " | ".join(sts)


# ---------------------------------------------------------------- hat trick

def test_hat_trick_fires():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 5, 2,
                   {1: line(d["s1"], g=3, a=1), 2: line(d["g1"], saves=20),
                    3: line(d["s2"], g=1), 4: line(d["g2"], saves=22)})
    sts = stories(mkapp([res]))
    assert len(sts) >= 1, names(sts)
    assert any("Sid Crosby" in s and "3" in s for s in sts), names(sts)


def test_hat_trick_names_true_team_and_score():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 5, 2,
                   {1: line(d["s1"], g=3), 2: line(d["g1"], saves=20)})
    sts = stories(mkapp([res]))
    assert any("Pittsburgh Penguins" in s and "5-2" in s for s in sts), names(sts)


def test_two_goals_is_not_a_hat_trick():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 4, 2,
                   {1: line(d["s1"], g=2, a=1), 2: line(d["g1"], saves=20)})
    sts = stories(mkapp([res]))
    assert not any("Sid Crosby" in s for s in sts), names(sts)


def test_hat_trick_in_loss_never_claims_win():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 2, 5,
                   {1: line(d["s1"], g=3), 2: line(d["g1"], saves=15)})
    sts = stories(mkapp([res]))
    assert any("Sid Crosby" in s for s in sts), names(sts)
    assert not any("win over" in s or "to a " in s and "victory" in s
                   for s in sts), names(sts)


# ------------------------------------------------------- multi-point games

def test_four_point_night_fires():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 6, 3,
                   {1: line(d["s1"], g=1, a=3), 2: line(d["g1"], saves=18)})
    sts = stories(mkapp([res]))
    assert any("Sid Crosby" in s and "4" in s for s in sts), names(sts)


def test_five_point_night_fires():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 7, 3,
                   {1: line(d["s1"], g=2, a=3), 2: line(d["g1"], saves=18)})
    sts = stories(mkapp([res]))
    assert any("Sid Crosby" in s and "5" in s for s in sts), names(sts)


def test_five_point_with_hat_trick_names_it():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 7, 3,
                   {1: line(d["s1"], g=3, a=2), 2: line(d["g1"], saves=18)})
    found = False
    for seed in range(30):
        sts = stories(mkapp([res]), seed=seed)
        if any("Sid Crosby" in s and "hat trick" in s.lower() for s in sts):
            found = True
            break
    assert found, "no rendering of the 5-point+hat-trick branch in 30 seeds"


def test_five_point_outranks_bare_hat_trick():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 7, 3,
                   {1: line(d["s1"], g=3, a=2), 2: line(d["g1"], saves=18)})
    sts = stories(mkapp([res]))
    assert any("Sid Crosby" in s and s.startswith("FIVE-POINT NIGHT:")
               for s in sts), names(sts)


def test_three_points_is_not_a_heroic():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 5, 2,
                   {1: line(d["s1"], g=1, a=2), 2: line(d["g1"], saves=20)})
    sts = stories(mkapp([res]))
    assert not any("Sid Crosby" in s for s in sts), names(sts)


# ----------------------------------------------------------------- shutout

def test_shutout_fires():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 3, 0,
                   {1: line(d["s1"], g=1), 2: line(d["g1"], saves=28),
                    4: line(d["g2"], saves=30)})
    sts = stories(mkapp([res]))
    assert any("Marc Fleury" in s and "28" in s for s in sts), names(sts)


def test_shutout_requires_zero_allowed():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 3, 1,
                   {2: line(d["g1"], saves=28), 4: line(d["g2"], saves=30)})
    sts = stories(mkapp([res]))
    assert not any("Marc Fleury" in s for s in sts), names(sts)


def test_shutout_requires_saves():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 3, 0,
                   {2: line(d["g1"], saves=0)})
    sts = stories(mkapp([res]))
    assert not any("Marc Fleury" in s for s in sts), names(sts)


def test_shutout_requires_goalie_line():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 3, 0,
                   {1: line(d["s1"], g=1)})
    sts = stories(mkapp([res]))
    assert sts == [], names(sts)


def test_shutout_needs_winner_match():
    d = std_pair()
    # Degenerate: 0-0 final recorded with a "winner" -- not a shutout.
    res = mkresult(d["home"], d["away"], 0, 0,
                   {2: line(d["g1"], saves=28)}, winner=d["home"])
    sts = stories(mkapp([res]))
    assert not any("Marc Fleury" in s for s in sts), names(sts)


def test_goalie_excluded_from_skater_feats():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 3, 0,
                   {2: line(d["g1"], g=3, saves=28)})
    sts = stories(mkapp([res]))
    assert not any("HAT TRICK" in s and "Marc Fleury" in s for s in sts), \
        names(sts)


# ---------------------------------------------------------------- OT winner

def test_ot_winner_fires():
    d = std_pair()
    evs = [goal_event(d["s1"], "Pittsburgh Penguins", 1),
           goal_event(d["s2"], "Washington Capitals", 2),
           goal_event(d["s1"], "Pittsburgh Penguins", 4, "03:12")]
    res = mkresult(d["home"], d["away"], 3, 2,
                   {1: line(d["s1"], g=2), 2: line(d["g1"], saves=24)},
                   overtime=True, events=evs)
    sts = stories(mkapp([res]))
    assert any("Sid Crosby" in s and "3-2" in s for s in sts), names(sts)


def test_shootout_winner_is_not_ot_winner():
    d = std_pair()
    evs = [goal_event(d["s1"], "Pittsburgh Penguins", 1),
           {"event": "Shootout Goal", "player": d["s2"],
            "team": "Washington Capitals", "period": 5}]
    res = mkresult(d["home"], d["away"], 2, 3,
                   {3: line(d["s2"], g=1)}, overtime=True, shootout=True,
                   events=evs)
    sts = stories(mkapp([res]))
    assert not any("Alex Ovechkin" in s and ("OT" in s or "overtime" in s)
                   for s in sts), names(sts)


def test_ot_winner_needs_one_goal_margin():
    d = std_pair()
    evs = [goal_event(d["s1"], "Pittsburgh Penguins", 4)]
    res = mkresult(d["home"], d["away"], 4, 2,
                   {1: line(d["s1"], g=1)}, overtime=True, events=evs)
    sts = stories(mkapp([res]))
    assert not any("Sid Crosby" in s for s in sts), names(sts)


def test_ot_winner_needs_ot_goal_event():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 3, 2,
                   {1: line(d["s1"], g=1)}, overtime=True, events=[])
    sts = stories(mkapp([res]))
    assert not any("Sid Crosby" in s for s in sts), names(sts)


def test_ot_winner_must_be_on_winning_team():
    d = std_pair()
    # Corrupt state: OT goal credited to the loser.
    evs = [goal_event(d["s2"], "Washington Capitals", 4)]
    res = mkresult(d["home"], d["away"], 3, 2,
                   {3: line(d["s2"], g=1)}, overtime=True, events=evs)
    sts = stories(mkapp([res]))
    assert not any("Alex Ovechkin" in s for s in sts), names(sts)


# ------------------------------------------------------------- dedup / caps

def test_one_story_per_player_per_game():
    d = std_pair()
    # Hat trick AND the OT winner: one story for Crosby (hat trick wins).
    evs = [goal_event(d["s1"], "Pittsburgh Penguins", 1),
           goal_event(d["s2"], "Washington Capitals", 2),
           goal_event(d["s1"], "Pittsburgh Penguins", 4)]
    res = mkresult(d["home"], d["away"], 4, 3,
                   {1: line(d["s1"], g=3, a=1)}, overtime=True, events=evs)
    sts = stories(mkapp([res]))
    n = sum(1 for s in sts if "Sid Crosby" in s)
    assert n == 1, names(sts)
    assert "HAT TRICK" in sts[0], names(sts)


def test_max_three_per_day():
    parts = []
    results = []
    for i in range(4):
        s = mkplayer("Hat", f"Trick{i}", "C")
        g = mkplayer("Goal", f"Ie{i}", "G")
        h = mkteam(f"Home{i} HC", [s, g])
        a = mkteam(f"Away{i} AC", [mkplayer("Op", f"Pos{i}", "C")])
        res = mkresult(h, a, 5, 1, {1: line(s, g=3), 2: line(g, saves=20)})
        results.append(res)
        parts.append((s, g, h, a))
    sts = stories(mkapp(results))
    assert len(sts) <= 3, names(sts)
    assert len(sts) == 3, names(sts)


def test_one_shot_per_game_day():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 5, 2, {1: line(d["s1"], g=3)})
    app = mkapp([res])
    first = stories(app)
    assert len(first) >= 1
    second = stories(app)
    assert second == [], names(second)


def test_new_game_day_fires_again():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 5, 2, {1: line(d["s1"], g=3)})
    app = mkapp([res])
    assert len(stories(app)) >= 1
    # Next day, another hat trick: the key carries the game day.
    day2 = date(2027, 1, 15)
    app.league._results_by_date[day2] = [res]
    again = dn._heroics_stories(app, date(2027, 1, 16), random.Random(7))
    assert len(again) >= 1, names(again)


# ------------------------------------------------------- fail-closed gates

def test_offseason_silent():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 5, 2, {1: line(d["s1"], g=3)})
    lg = types.SimpleNamespace(
        teams=[], season_year=2026,
        _results_by_date={date(2027, 7, 14): [res]})
    app = types.SimpleNamespace(league=lg, _daily_news_recent={})
    assert dn._heroics_stories(app, date(2027, 7, 15), random.Random(7)) == []


def test_no_results_silent():
    d = std_pair()
    app = mkapp([])
    assert stories(app) == []


def test_malformed_result_skipped():
    d = std_pair()
    good = mkresult(d["home"], d["away"], 5, 2, {1: line(d["s1"], g=3)})
    app = mkapp(["junk", None, 42, good])
    sts = stories(app)
    assert any("Sid Crosby" in s for s in sts), names(sts)


def test_unknown_player_never_renders():
    d = std_pair()
    ghost = types.SimpleNamespace(first_name="", last_name="",
                                  primary_position=types.SimpleNamespace(
                                      value="C"), id=999)
    h2 = mkteam("Pittsburgh Penguins", [ghost, d["g1"]])
    res = mkresult(h2, d["away"], 5, 2, {1: line(ghost, g=4)})
    sts = stories(mkapp([res]))
    assert not any("Unknown Player" in s for s in sts), names(sts)
    assert sts == [], names(sts)


def test_unknown_team_never_renders():
    d = std_pair()
    bad = mkteam("", [d["s1"], d["g1"]])
    res = mkresult(bad, d["away"], 5, 2, {1: line(d["s1"], g=3)})
    sts = stories(mkapp([res]))
    assert not any("Unknown Team" in s for s in sts), names(sts)
    assert sts == [], names(sts)


def test_non_nhl_result_skipped():
    d = std_pair()
    ahl_home = mkteam("Hershey Bears", [d["s1"], d["g1"]],
                      league_name="American Hockey League")
    res = mkresult(ahl_home, d["away"], 5, 2, {1: line(d["s1"], g=3)})
    sts = stories(mkapp([res]))
    assert sts == [], names(sts)


def test_never_raises_on_junk():
    assert dn._heroics_stories(object(), NEWS_DAY, random.Random(7)) == []
    assert dn._heroics_stories(None, NEWS_DAY, random.Random(7)) == []
    lg = types.SimpleNamespace(season_year=2026, _results_by_date="nope")
    app = types.SimpleNamespace(league=lg, _daily_news_recent={})
    assert dn._heroics_stories(app, NEWS_DAY, random.Random(7)) == []


def test_negative_stats_fail_closed():
    d = std_pair()
    res = mkresult(d["home"], d["away"], 5, 2,
                   {1: line(d["s1"], g=-3, a=8)})
    sts = stories(mkapp([res]))
    assert not any("Sid Crosby" in s for s in sts), names(sts)


def run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    bad = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            bad += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            bad += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"{len(fns) - bad}/{len(fns)} passed")
    return bad


if __name__ == "__main__":
    sys.exit(1 if run_all() else 0)
