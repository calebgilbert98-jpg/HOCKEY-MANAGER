#!/usr/bin/env python3
"""R8a: playoff race / clinch / elimination bucket tests (S item).

Bucket under test: daily_news._playoff_race_stories + its cutoff math.
Conventions: synthetic SimpleNamespace app/team fixtures (same shape as the
R7 probe harness); assertions on premises, not phrasing.
"""
import sys
import os
import types
import random
from datetime import date

_REPO = os.environ.get("R8A_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn


def rec(gp, pace):
    pts = round(pace * gp)
    w = pts // 2
    otl = pts % 2
    return w, gp - w - otl, otl


def mkteam(name, conf, w, l, otl, nhl=True):
    return types.SimpleNamespace(
        team_name=name, conference=conf,
        league_name="National Hockey League" if nhl else "American Hockey League",
        wins=w, losses=l, ot_losses=otl)


def mkapp(teams, season_year=2026, season_len=82):
    lg = types.SimpleNamespace(teams=teams, season_year=season_year)
    return types.SimpleNamespace(league=lg, season_games_count=season_len,
                                 _daily_news_recent={})


NAMES = ["Bruins", "Leafs", "Lightning", "Panthers",
         "Sabres", "Sens", "Habs", "Wings"]
PACES = [1.35, 1.15, 1.10, 1.05, 1.00, 0.97, 0.75, 0.55]


def eastern(gp, paces=PACES, names=NAMES):
    return [mkteam(n, "Eastern", *rec(gp, p)) for n, p in zip(names, paces)]


def test_window_gate_early_season():
    app = mkapp(eastern(20))
    assert dn._playoff_race_stories(app, date(2026, 11, 10),
                                    random.Random(1)) == []


def test_window_gate_season_over():
    app = mkapp(eastern(82))
    assert dn._playoff_race_stories(app, date(2027, 4, 20),
                                    random.Random(1)) == []


def test_window_gate_offseason():
    app = mkapp(eastern(70))
    assert dn._playoff_race_stories(app, date(2027, 7, 10),
                                    random.Random(1)) == []


def test_window_gate_gp_spread_distrust():
    teams = eastern(70)
    teams[0].wins, teams[0].losses, teams[0].ot_losses = rec(30, 1.35)
    app = mkapp(teams)
    assert dn._playoff_race_stories(app, date(2027, 3, 10),
                                    random.Random(1)) == []


def test_window_gate_bad_season_len():
    app = mkapp(eastern(70), season_len=0)
    assert dn._playoff_race_stories(app, date(2027, 3, 10),
                                    random.Random(1)) == []


def test_non_nhl_teams_ignored():
    teams = eastern(70)
    teams.append(mkteam("Marlies", "Eastern", *rec(70, 1.5), nhl=False))
    app = mkapp(teams)
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(1))
    assert not any("Marlies" in s for s in stories)


def test_clinch_and_elimination_fire_once_per_season():
    app = mkapp(eastern(76))
    d1 = date(2027, 3, 20)
    s1 = dn._playoff_race_stories(app, d1, random.Random(3))
    recent = app._daily_news_recent
    assert ("playoff:2026:Bruins", "clinch") in recent, "clinch not marked"
    assert ("playoff:2026:Wings", "eliminated") in recent, \
        "elimination not marked"
    # Next day, same season: the decided teams must not get fresh
    # clinch/elimination stories (race bubble excludes decided teams).
    s2 = dn._playoff_race_stories(app, date(2027, 3, 21), random.Random(4))
    assert not any("Bruins" in s for s in s2), s2
    assert not any("Wings" in s for s in s2), s2


def test_clinch_premise_true():
    # Bruins at gp=76: verify the clinch claim against independent math.
    teams = eastern(76)
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 4)
    assert "Bruins" in math["clinched"]
    # Independent check: fewer than 4 teams can finish above 103 pts.
    bruins_pts = next(r[2] for r in rows if r[4] == "Bruins")
    can_pass = sum(1 for r in rows
                   if r[4] != "Bruins" and r[3] > bruins_pts)
    assert can_pass < 4, can_pass
    stories = dn._playoff_race_stories(app, date(2027, 3, 20),
                                       random.Random(5))
    assert any("Bruins" in s and "CLINCHED" in s for s in stories)


def test_elimination_premise_true():
    teams = eastern(76)
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 4)
    assert "Wings" in math["eliminated"]
    wings_max = next(r[3] for r in rows if r[4] == "Wings")
    above = sum(1 for r in rows if r[4] != "Wings" and r[2] > wings_max)
    assert above >= 4, above
    stories = dn._playoff_race_stories(app, date(2027, 3, 20),
                                       random.Random(6))
    assert any("Wings" in s and "eliminat" in s.lower() for s in stories)


def test_tie_blocks_clinch_conservative():
    # Aces 80 pts (gp 70). Four chasers at 56 pts (gp 70) have ceiling
    # exactly 80: they can TIE Aces but never pass. The clinch story
    # claims the berth is official, and a tie + lost tiebreaker knocks a
    # team out -- so ties must block the clinch (conservative rule).
    teams = [
        mkteam("Aces", "Eastern", 40, 30, 0),    # 80 pts, gp 70
        mkteam("Bees", "Eastern", 28, 42, 0),    # 56 pts, max 80
        mkteam("Cats", "Eastern", 28, 42, 0),
        mkteam("Dogs", "Eastern", 28, 42, 0),
        mkteam("Elks", "Eastern", 28, 42, 0),
        mkteam("Fins", "Eastern", 25, 45, 0),    # 50 pts, max 74
    ]
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    assert all(r[3] == 80 for r in rows[1:5]), "chasers must max at 80"
    math = dn._pr_cutoff_math(rows, 3)
    assert "Aces" not in math["clinched"], math["clinched"]
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(7))
    assert not any("Aces" in s and "clinch" in s.lower() for s in stories)
    # Sanity: with the tie-block removed the old code DID call this a
    # clinch -- i.e. this fixture discriminates the two rules.
    can_pass_strict = sum(1 for o in rows
                          if o[4] != "Aces" and o[3] > 80)
    assert can_pass_strict == 0


def test_race_story_premise_true():
    # Fixture with nobody clinched/eliminated yet, so the race story gets
    # a slot: the cutoff math says the race is live.
    paces = [1.35, 1.15, 1.10, 1.05, 1.00, 0.97, 0.85, 0.80]
    teams = [mkteam(n, "Eastern", *rec(66, p))
             for n, p in zip(NAMES, paces)]
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 4)
    assert not math["clinched"], math["clinched"]
    assert not math["eliminated"], math["eliminated"]
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(8))
    race = [s for s in stories if "playoff race" in s.lower()]
    assert race, f"no race story in {stories}"
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 4)
    line_pts = math["last_in"][2]
    first_out_pts = math["first_out"][2]
    assert 0 <= line_pts - first_out_pts <= dn.PLAYOFF_RACE_BAND_PTS
    for s in race:
        # every named (name, pts) pair in the story matches the records
        import re
        for name, pts in re.findall(r"([A-Za-z]+) \((\d+) pts\)", s):
            row = next(r for r in rows if r[4] == name)
            assert int(pts) == row[2], (name, pts, row[2])
            assert abs(row[2] - line_pts) <= dn.PLAYOFF_RACE_BAND_PTS


def test_no_unknown_team_rendered():
    teams = eastern(70)
    teams[2] = types.SimpleNamespace(
        team_name=None, conference="Eastern",
        league_name="National Hockey League",
        wins=38, losses=30, ot_losses=2)
    app = mkapp(teams)
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(9))
    assert not any("Unknown Team" in s for s in stories)


def test_never_raises_on_garbage():
    app = types.SimpleNamespace()
    assert dn._playoff_race_stories(app, date(2027, 3, 10),
                                    random.Random(1)) == []
    assert dn._playoff_race_stories(app, None, random.Random(1)) == []


def test_max_two_stories_per_day():
    # gp=70 fires clinch + elimination already; race must not push past 2.
    app = mkapp(eastern(70))
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(10))
    assert len(stories) <= 2


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
