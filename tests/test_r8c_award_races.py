#!/usr/bin/env python3
"""R8c: award-races bucket tests (S item).

Bucket under test: daily_news._award_race_stories + its per-race
builders. Conventions: synthetic SimpleNamespace app/team/player
fixtures (same shape as the R8a/R8b tests); assertions on premises,
not phrasing.

The races themselves come from awards_race.py -- the bucket is a
presentation layer over those real computations. Tests assert the
bucket names the true race leader (recomputed independently in the
test), with the true stats, the true team, and a true runner-up gap;
and that it stays silent on degenerate state and outside the race
window (second half of the regular season).
"""
import sys
import os
import types
import random
from datetime import date

_REPO = os.environ.get("R8C_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn
import awards_race as ar

_PID = [0]


def mkplayer(fn, ln, pos, stats, team=None, pid=None, rookie=False,
             stars=None):
    _PID[0] += 1
    p = types.SimpleNamespace(
        first_name=fn, last_name=ln,
        primary_position=types.SimpleNamespace(value=pos),
        stats=types.SimpleNamespace(**stats),
        id=pid if pid is not None else _PID[0],
        is_rookie=rookie)
    if team is not None:
        p.team_name = team
    if stars is not None:
        p.game_stars = stars
    return p


def skater_stats(g, a, gp):
    return {"goals": g, "assists": a, "games_played": gp}


def goalie_stats(sv, sa, wins, gp, shutouts=0):
    return {"saves": sv, "shots_against": sa, "wins": wins,
            "shutouts": shutouts, "games_played": gp}


def mkteam(name, w, l, otl, roster):
    return types.SimpleNamespace(
        team_name=name, league_name="National Hockey League",
        wins=w, losses=l, ot_losses=otl, roster=roster)


def mkapp(teams, season_year=2026, season_len=82):
    lg = types.SimpleNamespace(teams=teams, season_year=season_year)
    return types.SimpleNamespace(league=lg, season_games_count=season_len,
                                 _daily_news_recent={})


# 4-team pool, gp 50-56: median 53 >= 41, spread 6 <= 10, games left.
def pool(rosters, gp=(50, 52, 54, 56)):
    names = ["Aces", "Bees", "Cats", "Dogs"]
    teams = []
    for name, roster, g in zip(names, rosters, gp):
        w = g // 2
        teams.append(mkteam(name, w, g - w, 0, roster))
    return teams


def std_app(rosters, game_date=date(2027, 2, 15)):
    return mkapp(pool(rosters)), game_date


def roster_map_of(teams):
    return ar.roster_team_map(teams)


# ---------------------------------------------------------------- window ---

def test_window_early_season_silent():
    r = [[mkplayer("A", "One", "C", skater_stats(30, 40, 20))]]
    app, d = std_app([r[0], [], [], []])
    app.league.teams = pool([r[0], [], [], []], gp=(20, 21, 22, 23))
    assert dn._award_race_stories(app, d, random.Random(0)) == []


def test_window_season_over_silent():
    r = [mkplayer("A", "One", "C", skater_stats(30, 40, 82))]
    app, d = std_app([r, [], [], []], )
    app.league.teams = pool([r, [], [], []], gp=(82, 82, 82, 82))
    assert dn._award_race_stories(app, d, random.Random(0)) == []


def test_window_offseason_silent():
    r = [mkplayer("A", "One", "C", skater_stats(30, 40, 60))]
    app, _d = std_app([r, [], [], []])
    assert dn._award_race_stories(app, date(2027, 7, 15),
                                 random.Random(0)) == []


def test_window_gp_spread_silent():
    r = [mkplayer("A", "One", "C", skater_stats(30, 40, 60))]
    app, d = std_app([r, [], [], []])
    app.league.teams = pool([r, [], [], []], gp=(30, 55, 56, 57))
    assert dn._award_race_stories(app, d, random.Random(0)) == []


def test_window_season_year_falls_back_to_calendar():
    # _pr_season_year's contract: a league with no usable season_year
    # falls back to the calendar year (shared R8a helper behavior).
    r = [mkplayer("A", "One", "C", skater_stats(40, 55, 55), team="Aces")]
    app, d = std_app([r, [], [], []])
    del app.league.season_year
    stories = dn._award_race_stories(app, d, random.Random(0))
    assert len(stories) >= 1, stories
    assert any("2027" in k[0] for k in app._daily_news_recent), \
        app._daily_news_recent.keys()


# ------------------------------------------------------------------ hart ---

def hart_pool():
    lead = mkplayer("Connor", "Alpha", "C", skater_stats(40, 55, 55),
                    team="Aces")
    run = mkplayer("Leon", "Beta", "C", skater_stats(38, 50, 54),
                   team="Bees")
    filler = mkplayer("Zed", "Gamma", "LW", skater_stats(20, 25, 52),
                      team="Cats")
    g1 = mkplayer("Igor", "Tender", "G", goalie_stats(1380, 1500, 28, 40),
                  team="Dogs")
    return [[lead], [run], [filler], [g1]]


def test_hart_names_true_leader_with_true_stats():
    app, d = std_app(hart_pool())
    rng = random.Random(1)
    stories = dn._award_race_stories(app, d, rng)
    hart = [s for s in stories if "hart race" in s.lower()]
    assert len(hart) == 1, stories
    s = hart[0]
    # Independent recomputation of the premise.
    players = [p for t in app.league.teams for p in t.roster]
    race = ar.hart_race(players, {"Aces": .6, "Bees": .55, "Cats": .5,
                                  "Dogs": .45},
                        roster_map=ar.roster_team_map(app.league.teams))
    assert race[0]["player"].first_name == "Connor"
    assert "Connor Alpha" in s and "95 points" in s
    assert "40 goals" in s and "Aces" in s and "55 games" in s
    # Runner-up gap: 95 - 88 = 7, real arithmetic.
    assert "7 clear of Leon Beta" in s


def test_hart_unknown_team_silent():
    rosters = hart_pool()
    app, d = std_app(rosters)
    app.league.teams[0].team_name = ""
    item = dn._ar_hart_pending(
        ar.hart_race([p for t in app.league.teams for p in t.roster],
                     {"": .6, "Bees": .5, "Cats": .5, "Dogs": .5},
                     roster_map=ar.roster_team_map(app.league.teams)),
        ar.roster_team_map(app.league.teams), 2026, app, d,
        random.Random(0))
    assert item is None


def test_hart_zero_point_leader_silent():
    r = [mkplayer("A", "One", "C", skater_stats(0, 0, 50), team="Aces")]
    app, d = std_app([r, [], [], []])
    race = ar.hart_race([r[0]], {"Aces": .5, "Bees": .5, "Cats": .5,
                                 "Dogs": .5},
                        roster_map=ar.roster_team_map(app.league.teams))
    assert dn._ar_hart_pending(race, ar.roster_team_map(app.league.teams),
                               2026, app, d, random.Random(0)) is None


def test_hart_nameless_leader_silent():
    r = [mkplayer(None, None, "C", skater_stats(40, 55, 55), team="Aces")]
    app, d = std_app([r, [], [], []])
    race = ar.hart_race([r[0]], {"Aces": .5, "Bees": .5, "Cats": .5,
                                 "Dogs": .5},
                        roster_map=ar.roster_team_map(app.league.teams))
    assert dn._ar_hart_pending(race, ar.roster_team_map(app.league.teams),
                               2026, app, d, random.Random(0)) is None


# -------------------------------------------------------------- art ross ---

def test_art_ross_names_true_leader():
    lead = mkplayer("Nikita", "Omega", "RW", skater_stats(35, 65, 55),
                    team="Bees")
    run = mkplayer("David", "Sigma", "C", skater_stats(30, 60, 55),
                   team="Aces")
    app, d = std_app([[run], [lead], [], []])
    rng = random.Random(2)
    stories = dn._award_race_stories(app, d, rng)
    ross = [s for s in stories if "art ross race" in s.lower()]
    assert len(ross) == 1, stories
    s = ross[0]
    players = [p for t in app.league.teams for p in t.roster]
    race = ar.art_ross_race([p for p in players
                             if dn._td_pos_group(p) in ("Forward",
                                                        "Defense")])
    assert race[0]["player"].first_name == "Nikita"
    assert "Nikita Omega" in s and "100 points" in s and "Bees" in s
    assert "10 clear of David Sigma" in s  # 100 - 90


# ---------------------------------------------------------------- norris ---

def test_norris_names_defenseman_not_top_forward():
    star_f = mkplayer("Auston", "Forward", "C", skater_stats(45, 45, 55),
                      team="Aces")          # 90 pts, not a defenseman
    dman = mkplayer("Cale", "Blueline", "LD",
                    {"goals": 20, "assists": 45, "games_played": 55,
                     "plus_minus": 18},
                    team="Bees")            # 65 pts
    d2 = mkplayer("Adam", "Second", "RD", skater_stats(10, 30, 54),
                  team="Cats")
    app, d = std_app([[star_f], [dman], [d2], []])
    players = [p for t in app.league.teams for p in t.roster]
    race = ar.norris_race(players)
    assert race[0]["player"].first_name == "Cale"  # forward excluded
    # Builder-direct: the full bucket returns at most 2 stories/day, so a
    # premise test goes through the builder (the week test below covers
    # bucket-level firing of every race).
    item = dn._ar_norris_pending(race,
                                 ar.roster_team_map(app.league.teams),
                                 2026, app, d, random.Random(3))
    assert item is not None
    s = item[0]
    assert "Cale Blueline" in s and "Auston Forward" not in s
    assert "65 points" in s and "+18" in s and "Bees" in s


def test_norris_empty_silent():
    app, d = std_app([[], [], [], []])
    assert dn._ar_norris_pending([], {}, 2026, app, d,
                                 random.Random(0)) is None


# ---------------------------------------------------------------- vezina ---

def test_vezina_names_true_leader_with_true_numbers():
    g1 = mkplayer("Igor", "Tender", "G",
                  goalie_stats(1400, 1520, 30, 42, shutouts=5),
                  team="Aces")              # .921
    g2 = mkplayer("Andrei", "Pipes", "G",
                  goalie_stats(1300, 1450, 25, 40),
                  team="Bees")              # .897
    app, d = std_app([[g1], [], [], [g2]])
    players = [p for t in app.league.teams for p in t.roster]
    race = ar.vezina_race([g1, g2])
    assert race[0]["player"].first_name == "Igor"
    rng = random.Random(4)
    stories = dn._award_race_stories(app, d, rng)
    vez = [s for s in stories if "vezina race" in s.lower()]
    assert len(vez) == 1, stories
    s = vez[0]
    assert "Igor Tender" in s and "0.921" in s and "Aces" in s
    assert "30 wins" in s
    # GAA = 120 GA / 42 gp = 2.86 (minutes_played never written).
    assert "2.86" in s


def test_vezina_degenerate_sv_silent():
    g = mkplayer("Rusty", "Pipes", "G",
                 goalie_stats(0, 0, 0, 40), team="Aces")
    app, d = std_app([[], [], [g], []])
    race = ar.vezina_race([g])
    assert dn._ar_vezina_pending(race, ar.roster_team_map(app.league.teams),
                                 2026, app, d, random.Random(0)) is None


# ---------------------------------------------------------------- calder ---

def test_calder_names_eligible_rookie_not_veteran():
    vet = mkplayer("Sid", "Veteran", "C", skater_stats(40, 50, 55),
                   team="Aces", rookie=False)     # 90 pts, ineligible
    rook = mkplayer("Mack", "Freshman", "C", skater_stats(25, 35, 52),
                    team="Bees", rookie=True)     # 60 pts, eligible
    app, d = std_app([[vet], [rook], [], []])
    players = [p for t in app.league.teams for p in t.roster]
    race = ar.calder_race(players, season_year=2026)
    assert [p.first_name for p in (r["player"] for r in race)] == ["Mack"]
    # Builder-direct: the full bucket returns at most 2 stories/day.
    item = dn._ar_calder_pending(race,
                                 ar.roster_team_map(app.league.teams),
                                 2026, app, d, random.Random(5))
    assert item is not None
    s = item[0]
    assert "Mack Freshman" in s and "Sid Veteran" not in s
    assert "60 points" in s and "25 goals" in s and "Bees" in s


def test_calder_goalie_rookie_renders_goalie_statline():
    g = mkplayer("Dustin", "Wolf", "G",
                 goalie_stats(1200, 1300, 18, 30), team="Cats",
                 rookie=True)                    # .923
    app, d = std_app([[], [], [g], []])
    race = ar.calder_race([g], season_year=2026)
    assert race and race[0]["goalie"] is True
    item = dn._ar_calder_pending(race,
                                 ar.roster_team_map(app.league.teams),
                                 2026, app, d, random.Random(6))
    assert item is not None
    assert "0.923" in item[0] and "18 wins" in item[0]


def test_calder_no_eligible_rookies_silent():
    vet = mkplayer("Sid", "Veteran", "C", skater_stats(40, 50, 55),
                   team="Aces", rookie=False)
    app, d = std_app([[vet], [], [], []])
    race = ar.calder_race([vet], season_year=2026)
    assert race == []
    assert dn._ar_calder_pending(race,
                                 ar.roster_team_map(app.league.teams),
                                 2026, app, d, random.Random(0)) is None


# ----------------------------------------------------------------- keys ---

def test_repeat_key_one_shot_per_leader():
    app, d = std_app(hart_pool())
    players = [p for t in app.league.teams for p in t.roster]
    rm = ar.roster_team_map(app.league.teams)
    race = ar.hart_race(players, {"Aces": .6, "Bees": .55, "Cats": .5,
                                  "Dogs": .45}, roster_map=rm)
    rng = random.Random(0)
    item = dn._ar_hart_pending(race, rm, 2026, app, d, rng)
    assert item is not None
    story, key, _st, _t = item
    dn._mark_recent(app, key, "award", d)
    # Same leader, same day: silent.
    assert dn._ar_hart_pending(race, rm, 2026, app, d, rng) is None
    # Next season: fires again.
    assert dn._ar_hart_pending(race, rm, 2027, app, d, rng) is not None


def test_leader_change_fires_new_story():
    app, d = std_app(hart_pool())
    players = [p for t in app.league.teams for p in t.roster]
    rm = ar.roster_team_map(app.league.teams)
    pct = {"Aces": .6, "Bees": .55, "Cats": .5, "Dogs": .5}
    race = ar.hart_race(players, pct, roster_map=rm)
    item1 = dn._ar_hart_pending(race, rm, 2026, app, d, random.Random(0))
    dn._mark_recent(app, item1[1], "award", d)
    # Leon Beta surges past Connor Alpha.
    players[1].stats.goals, players[1].stats.assists = 60, 60
    race2 = ar.hart_race(players, pct, roster_map=rm)
    assert race2[0]["player"].first_name == "Leon"
    item2 = dn._ar_hart_pending(race2, rm, 2026, app, d, random.Random(0))
    assert item2 is not None and "Leon Beta" in item2[0]


def test_duplicate_names_each_get_a_story():
    a1 = mkplayer("Sam", "Same", "C", skater_stats(40, 55, 55),
                  team="Aces", pid=101)
    a2 = mkplayer("Sam", "Same", "C", skater_stats(38, 50, 54),
                  team="Bees", pid=102)
    app, d = std_app([[a1], [a2], [], []])
    players = [p for t in app.league.teams for p in t.roster]
    rm = ar.roster_team_map(app.league.teams)
    race = ar.hart_race(players, {"Aces": .6, "Bees": .55, "Cats": .5,
                                  "Dogs": .5}, roster_map=rm)
    i1 = dn._ar_hart_pending(race, rm, 2026, app, d, random.Random(0))
    assert i1 is not None and "Aces" in i1[0]
    dn._mark_recent(app, i1[1], "award", d)
    # Same display name, different object: not suppressed by the twin.
    a2.stats.goals, a2.stats.assists = 60, 60
    race2 = ar.hart_race(players, {"Aces": .6, "Bees": .55, "Cats": .5,
                                   "Dogs": .5}, roster_map=rm)
    i2 = dn._ar_hart_pending(race2, rm, 2026, app, d, random.Random(0))
    assert i2 is not None and "Bees" in i2[0]
    assert i1[1] != i2[1]


# ------------------------------------------------------- full bucket -------

def test_art_ross_star_boost_never_claims_false_maximality():
    # art_ross_race sorts by points + 3-star bonus: a star-boosted player
    # can lead the race with FEWER points. Template 3 ("Nobody has more
    # points than X") must never fire then; the other templates assert
    # race leadership, which holds by construction.
    boosted = mkplayer("Star", "Boosted", "C", skater_stats(25, 28, 50),
                       team="Aces", stars={"first": 20, "second": 0,
                                           "third": 0})   # 53 pts
    plain = mkplayer("Plain", "Scorer", "C", skater_stats(26, 28, 50),
                     team="Bees")                          # 54 pts
    app, d = std_app([[boosted], [plain], [], []])
    players = [p for t in app.league.teams for p in t.roster]
    rm = ar.roster_team_map(app.league.teams)
    race = ar.art_ross_race([p for p in players
                             if dn._td_pos_group(p) == "Forward"])
    assert race[0]["player"].first_name == "Star"  # bonus flips the order
    assert race[0]["points"] < race[1]["points"]
    seen = set()
    for seed in range(60):
        item = dn._ar_art_ross_pending(race, rm, 2026, app, d,
                                       random.Random(seed))
        assert item is not None
        s = item[0]
        assert "Nobody has more points" not in s, s
        seen.add(s)
    # Both eligible templates still render true race-leadership claims.
    assert any("paces the Art Ross race" in s for s in seen), seen
    assert any("leads the scoring-title chase" in s for s in seen), seen
    assert all("Star Boosted" in s and "53 points" in s for s in seen)


def test_art_ross_third_player_points_lead_suppresses_template3():
    # The maximality gate must hold over the WHOLE field, not just the
    # runner-up: star bonus can order A(101) > B(100) > C(105) by score
    # while C holds the points lead. Template 3 must never fire then.
    a = mkplayer("Star", "Lead", "C", skater_stats(50, 51, 55),
                 team="Aces", stars={"first": 18, "second": 0,
                                     "third": 0})      # 101 pts
    b = mkplayer("Run", "Star", "C", skater_stats(50, 50, 55),
                 team="Aces", stars={"first": 20, "second": 0,
                                     "third": 0})      # 100 pts
    c = mkplayer("Quiet", "Storm", "C", skater_stats(55, 50, 55),
                 team="Bees")                          # 105 pts
    app, d = std_app([[a, b], [c], [], []])
    players = [p for t in app.league.teams for p in t.roster]
    rm = ar.roster_team_map(app.league.teams)
    race = ar.art_ross_race([p for p in players
                             if dn._td_pos_group(p) == "Forward"])
    order = [(r["player"].first_name, r["points"]) for r in race]
    assert order == [("Star", 101), ("Run", 100), ("Quiet", 105)], order
    for seed in range(120):
        item = dn._ar_art_ross_pending(race, rm, 2026, app, d,
                                       random.Random(seed))
        assert item is not None
        assert "Nobody has more points" not in item[0], item[0]


def test_art_ross_strict_points_lead_template3_fires_true():    # With a genuine strict points lead, template 3 is eligible and its
    # maximality claim is true.
    lead = mkplayer("Nikita", "Omega", "RW", skater_stats(35, 65, 55),
                    team="Bees")
    run = mkplayer("David", "Sigma", "C", skater_stats(30, 60, 55),
                   team="Aces")
    app, d = std_app([[run], [lead], [], []])
    players = [p for t in app.league.teams for p in t.roster]
    rm = ar.roster_team_map(app.league.teams)
    race = ar.art_ross_race([p for p in players
                             if dn._td_pos_group(p) == "Forward"])
    fired = [dn._ar_art_ross_pending(race, rm, 2026, app, d,
                                     random.Random(seed))[0]
             for seed in range(60)]
    t3 = [s for s in fired if "Nobody has more points" in s]
    assert t3, "template 3 never selected on a strict points lead"
    assert all("Nikita Omega (Bees)" in s and "100 in 55 games" in s
               for s in t3)


def test_full_bucket_fires_all_five_races_over_a_week():
    lead = mkplayer("Connor", "Alpha", "C", skater_stats(40, 55, 55),
                    team="Aces")
    run = mkplayer("Leon", "Beta", "C", skater_stats(30, 40, 54),
                   team="Bees")
    dman = mkplayer("Cale", "Blueline", "LD",
                    {"goals": 20, "assists": 45, "games_played": 55,
                     "plus_minus": 18}, team="Cats")
    g1 = mkplayer("Igor", "Tender", "G",
                  goalie_stats(1400, 1520, 30, 42), team="Dogs")
    rook = mkplayer("Mack", "Freshman", "LW", skater_stats(25, 35, 52),
                    team="Aces", rookie=True)
    app, d0 = std_app([[lead, rook], [run], [dman], [g1]])
    seen = set()
    rng = random.Random(7)
    for i in range(10):
        d = date(2027, 2, 15 + i)
        for s in dn._award_race_stories(app, d, rng):
            low = s.lower()
            # Calder template 2 has no "CALDER RACE:" kicker -- it reads
            # "{name} is the rookie to beat".
            for kind in ("hart race", "art ross race", "norris race",
                         "vezina race", "calder race", "rookie to beat"):
                if kind in low:
                    seen.add("calder race" if kind == "rookie to beat"
                             else kind)
    assert seen == {"hart race", "art ross race", "norris race",
                    "vezina race", "calder race"}, seen


def test_full_bucket_never_fires_outside_window():
    lead = mkplayer("Connor", "Alpha", "C", skater_stats(40, 55, 55),
                    team="Aces")
    app, _d = std_app([[lead], [], [], []])
    # October (gp would be ~8): rig gp below the 50% line.
    app.league.teams = pool([[lead], [], [], []], gp=(8, 9, 10, 11))
    assert dn._award_race_stories(app, date(2026, 10, 20),
                                 random.Random(0)) == []
    # Offseason.
    app.league.teams = pool([[lead], [], [], []], gp=(50, 52, 54, 56))
    assert dn._award_race_stories(app, date(2027, 6, 1),
                                 random.Random(0)) == []


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        _PID[0] = 0
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
