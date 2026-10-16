#!/usr/bin/env python3
"""R8a: playoff race / clinch / elimination bucket tests (S item).

Bucket under test: daily_news._playoff_race_stories + its cutoff math.
Conventions: synthetic SimpleNamespace app/team fixtures (same shape as the
R7 probe harness); assertions on premises, not phrasing.

REV-C: the math is format-aware. The engine default is divisional
qualifying (top 3 per division + 2 wild cards per conference), so the
default test league is divisional; conference-format leagues use classic
top-half math. Cutoff sets hold team objects, never display names
(duplicate names must not cross-contaminate).
"""
import sys
import os
import re
import types
import random
from datetime import date

_REPO = os.environ.get(
    "R8A_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import daily_news as dn


def rec(gp, pace):
    pts = round(pace * gp)
    w = pts // 2
    otl = pts % 2
    return w, gp - w - otl, otl


def mkteam(name, conf, w, l, otl, nhl=True, division=""):
    return types.SimpleNamespace(
        team_name=name, conference=conf, division=division,
        league_name="National Hockey League" if nhl else "American Hockey League",
        wins=w, losses=l, ot_losses=otl)


def mkapp(teams, season_year=2026, season_len=82,
          playoff_format="divisional"):
    lg = types.SimpleNamespace(teams=teams, season_year=season_year,
                               playoff_format=playoff_format)
    return types.SimpleNamespace(league=lg, season_games_count=season_len,
                                 _daily_news_recent={})


def by_name(teams, name):
    return next(t for t in teams if t.team_name == name)


def clinch_keys(app):
    return [k for k in app._daily_news_recent if k[1] == "clinch"]


def elim_keys(app):
    return [k for k in app._daily_news_recent if k[1] == "eliminated"]


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
    assert s1, "expected stories on day 1"
    assert any(k[0].startswith("playoff:2026:Bruins#")
               for k in clinch_keys(app)), "clinch not marked"
    assert any(k[0].startswith("playoff:2026:Wings#")
               for k in elim_keys(app)), "elimination not marked"
    # Next day, same season: the decided teams must not get fresh
    # clinch/elimination stories.
    s2 = dn._playoff_race_stories(app, date(2027, 3, 21), random.Random(4))
    assert not any("Bruins" in s for s in s2), s2
    assert not any("Wings" in s for s in s2), s2


def test_clinch_premise_true():
    # Bruins at gp=76: verify the clinch claim against independent math.
    teams = eastern(76)
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 4)
    bruins = by_name(teams, "Bruins")
    assert id(bruins) in math["clinched"]
    # Independent check: fewer than 4 teams can finish above 103 pts.
    bruins_pts = next(r[2] for r in rows if r[0] is bruins)
    can_pass = sum(1 for r in rows
                   if r[0] is not bruins and r[3] > bruins_pts)
    assert can_pass < 4, can_pass
    stories = dn._playoff_race_stories(app, date(2027, 3, 20),
                                       random.Random(5))
    assert any("Bruins" in s and "CLINCHED" in s for s in stories)


def test_elimination_premise_true():
    teams = eastern(76)
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    wings = by_name(teams, "Wings")
    div_rows = {"": rows}
    div_locked, wc_locked, eliminated, _ = dn._pr_divisional_sets(
        rows, div_rows)
    assert id(wings) in eliminated
    # Independent check: Wings' max is 54; seven rivals sit above it, so
    # at least 7-3=4 are forced into the wild-card pool above them.
    wings_max = next(r[3] for r in rows if r[0] is wings)
    above = [r for r in rows if r[0] is not wings and r[2] > wings_max]
    assert len(above) - 3 >= 2, len(above)
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
    aces = by_name(teams, "Aces")
    assert id(aces) not in math["clinched"], math["clinched"]
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(7))
    assert not any("Aces" in s and "clinch" in s.lower() for s in stories)
    # Sanity: with the tie-block removed the old code DID call this a
    # clinch -- i.e. this fixture discriminates the two rules.
    can_pass_strict = sum(1 for o in rows
                          if o[0] is not aces and o[3] > 80)
    assert can_pass_strict == 0


def test_division_and_wc_races_fire():
    # One 8-team division: a 3rd-place race (Lightning 73 vs Panthers 69)
    # and a wild-card race (Leafs 76 vs Lightning 73) both live.
    paces = [1.35, 1.15, 1.10, 1.05, 1.00, 0.97, 0.85, 0.80]
    teams = [mkteam(n, "Eastern", *rec(66, p))
             for n, p in zip(NAMES, paces)]
    app = mkapp(teams)
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(8))
    race = [s for s in stories if "pts)" in s]
    assert len(race) == 2, f"expected division + WC races, got {stories}"
    assert any("Lightning (73 pts)" in s and "Panthers (69 pts)" in s
               for s in race), race
    assert any("Leafs (76 pts)" in s and "Lightning (73 pts)" in s
               for s in race), race
    # Every named (name, pts) pair matches the records.
    import re
    rows = dn._pr_pool_records(teams, 82)
    for s in race:
        for name, pts in re.findall(r"([A-Za-z]+) \((\d+) pts\)", s):
            row = next(r for r in rows if r[4] == name)
            assert int(pts) == row[2], (name, pts, row[2])


def test_race_fires_on_tie_at_the_line():
    # Last-in and first-out tied exactly at the division 3rd-place
    # cutoff: the race is maximally live. (With a strict below-the-line
    # requirement this stayed silent -- a false negative.)
    teams = [
        mkteam("Aces", "Eastern", 45, 25, 0),    # 90 pts, gp 70
        mkteam("Bees", "Eastern", 41, 29, 0),    # 82 pts, gp 70
        mkteam("Cats", "Eastern", 40, 30, 0),    # 80 pts, gp 70 (last in)
        mkteam("Dogs", "Eastern", 40, 30, 0),    # 80 pts, gp 70 (first out)
        mkteam("Elks", "Eastern", 35, 35, 0),    # 70 pts, gp 70
        mkteam("Fins", "Eastern", 20, 50, 0),    # 40 pts, gp 70
    ]
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 3)
    assert math["last_in"][2] == math["first_out"][2] == 80
    cats = by_name(teams, "Cats")
    assert id(cats) not in math["clinched"]  # 3 can reach >= 80, not < 3
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(11))
    race = [s for s in stories if "pts)" in s]
    assert race, f"no race story on a tied cutoff: {stories}"
    assert any("Cats" in s and "Dogs" in s for s in race)


def test_race_omits_games_when_remaining_differs():
    # Named bubble teams with different games remaining: no story may
    # state a shared games number (it would be false for some of them).
    teams = [
        mkteam("Aces", "Eastern", 45, 25, 0),    # 90 pts, gp 70 (12 left)
        mkteam("Bees", "Eastern", 38, 32, 0),    # 76 pts, gp 70 (12 left)
        mkteam("Cats", "Eastern", 37, 33, 0),    # 74 pts, gp 70 (12 left)
        mkteam("Dogs", "Eastern", 37, 29, 0),    # 74 pts, gp 66 (16 left)
        mkteam("Elks", "Eastern", 36, 30, 0),    # 72 pts, gp 66 (16 left)
        mkteam("Fins", "Eastern", 20, 50, 0),    # 40 pts, gp 70
    ]
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 3)
    assert math["last_in"][2] - math["first_out"][2] <= 4
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(12))
    race = [s for s in stories if "pts)" in s]
    assert race, f"no race story: {stories}"
    for s in race:
        assert "game" not in s.lower(), f"shared games number stated: {s}"


def test_no_unknown_team_rendered():
    teams = eastern(70)
    teams[2] = types.SimpleNamespace(
        team_name=None, conference="Eastern", division="",
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


def test_conference_format_uses_top_half_math():
    # playoff_format="conference": classic top-half-per-conference
    # qualifying; the old top-half math governs.
    teams = eastern(76)
    app = mkapp(teams, playoff_format="conference")
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 4)
    assert id(by_name(teams, "Bruins")) in math["clinched"]
    assert id(by_name(teams, "Wings")) in math["eliminated"]
    stories = dn._playoff_race_stories(app, date(2027, 3, 20),
                                       random.Random(5))
    assert any("Bruins" in s and "CLINCHED" in s for s in stories)
    assert any("Wings" in s and "eliminat" in s.lower() for s in stories)


def _attack_a_fixture():
    # REV-C attack A: X sits 6th in the Atlantic with five division
    # rivals strictly above its ceiling -- divisionally dead (and
    # wild-card dead: 5 Atlantic teams above its max force >=2 into the
    # pool). Conference top-half math (5 < 8) used to call this a clinch.
    atl = [
        mkteam("AD1", "Eastern", 54, 22, 0, division="Atlantic"),  # 108
        mkteam("AD2", "Eastern", 53, 23, 0, division="Atlantic"),  # 106
        mkteam("AD3", "Eastern", 52, 24, 0, division="Atlantic"),  # 104
        mkteam("AW1", "Eastern", 52, 24, 0, division="Atlantic"),  # 104
        mkteam("AW2", "Eastern", 51, 25, 0, division="Atlantic"),  # 102
        mkteam("X",   "Eastern", 44, 32, 0, division="Atlantic"),  # 88
        mkteam("AA7", "Eastern", 30, 46, 0, division="Atlantic"),  # 60
        mkteam("AA8", "Eastern", 28, 48, 0, division="Atlantic"),  # 56
    ]
    metro = [mkteam("M%d" % i, "Eastern", 35, 41, 0,
                    division="Metropolitan") for i in range(1, 9)]  # 70
    return atl + metro


def test_divisional_no_false_clinch():
    teams = _attack_a_fixture()
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    div_rows = {}
    for r in rows:
        div_rows.setdefault(dn._pr_division(r[0]), []).append(r)
    div_locked, wc_locked, eliminated, _ = dn._pr_divisional_sets(
        rows, div_rows)
    x = by_name(teams, "X")
    assert id(x) not in div_locked and id(x) not in wc_locked
    assert id(x) in eliminated, "X is divisionally + wild-card dead"
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(21))
    assert not any("X" in s and "CLINCHED" in s for s in stories), stories
    assert not any(re.search(r"X \(\d+ pts\)", s) for s in stories), stories


def test_divisionally_dead_team_gets_elimination_story():
    # X is truly dead (see above); its elimination story must fire
    # within a few days (one decided-team story per day).
    import re  # noqa: F401  (kept for symmetry; unused here)
    teams = _attack_a_fixture()
    app = mkapp(teams)
    seen = []
    for d in range(5):
        stories = dn._playoff_race_stories(
            app, date(2027, 3, 10 + d), random.Random(30 + d))
        seen.extend(stories)
    assert any("X" in s and "eliminat" in s.lower() for s in seen), seen


def test_duplicate_team_names_no_cross_contamination():
    # REV-C attacks C/D: two teams sharing a display name must not
    # contaminate each other's cutoff math (identity is the object).
    # Aces#1 (100): Aces#2 (max 110), Cee (max 109), Dee (max 108) can
    # all reach 100 -- 3 blockers, so NO clinch. Name-based identity
    # dropped the twin and falsely clinched.
    teams = [
        mkteam("Aces", "Eastern", 50, 26, 0),          # 100, max 112
        mkteam("Aces", "Eastern", 49, 27, 0),          # 98, max 110
        mkteam("Cee", "Eastern", 48, 27, 1),           # 97, max 109
        mkteam("Dee", "Eastern", 48, 28, 0),           # 96, max 108
        mkteam("Eels", "Eastern", 30, 46, 0),          # 60
        mkteam("Fins", "Eastern", 30, 46, 0),          # 60
    ]
    app = mkapp(teams)
    rows = dn._pr_pool_records(teams, 82)
    math = dn._pr_cutoff_math(rows, 3)
    aces1, aces2 = teams[0], teams[1]
    assert id(aces1) not in math["clinched"], "false clinch via twin"
    assert id(aces2) not in math["clinched"]
    stories = dn._playoff_race_stories(app, date(2027, 3, 10),
                                       random.Random(22))
    assert not any("Aces" in s and "CLINCHED" in s for s in stories), stories
    # Attack D direction: a truly-dead twin must still be caught.
    duds = [
        mkteam("Duds", "Eastern", 20, 56, 0),          # 40, max 52
        mkteam("Duds", "Eastern", 45, 31, 0),          # 90, max 102
        mkteam("Ay", "Eastern", 44, 32, 0),            # 88
        mkteam("Bee", "Eastern", 43, 33, 0),           # 86
        mkteam("Eels", "Eastern", 30, 46, 0),          # 60
        mkteam("Fins", "Eastern", 30, 46, 0),          # 60
    ]
    app2 = mkapp(duds)
    rows2 = dn._pr_pool_records(duds, 82)
    div_rows2 = {"": rows2}
    _, _, eliminated2, _ = dn._pr_divisional_sets(rows2, div_rows2)
    assert id(duds[0]) in eliminated2, "dead twin must be caught"
    assert id(duds[1]) not in eliminated2, "live twin must not be smeared"
    stories2 = dn._playoff_race_stories(app2, date(2027, 3, 10),
                                        random.Random(23))
    assert any("20-56-0" in s and "eliminat" in s.lower()
               for s in stories2), stories2


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
