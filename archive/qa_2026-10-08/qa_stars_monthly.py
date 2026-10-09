# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: three stars of the game + NHL Player/Rookie of the Month.

Covers star selection on realistic NHL criteria (hat tricks, OT winners,
shutouts), recording onto players/results, first-star Signature Games
moments, monthly award selection/banking/idempotency, and save-safety of
the new fields.
"""
import json
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, ".")

from game_classes import Player, PlayerPosition, Team
import stars
from stars import (select_three_stars, record_game_stars,
                   select_monthly_winners, monthly_awards_tick,
                   stamp_monthly_baselines, signature_game_rows)

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL {name}")


_seq = [0]


def mk_player(first, last, pos, rookie=False):
    p = Player(first, last, 25, pos)
    _seq[0] += 1
    p.id = 1000 + _seq[0]
    p.is_rookie = rookie
    return p


def mk_teams():
    home = Team("Home", "City", "Div", "Conf")
    away = Team("Away", "City", "Div", "Conf")
    return home, away


def set_line(p, g=0, a=0, saves=0):
    return {"player": p, "g": g, "a": a, "saves": saves,
            "shots_on_goal": g + a, "hits": 0, "blocked_shots": 0,
            "faceoffs_won": 0, "faceoffs_lost": 0}


def goal_event(player, period=1, team="Home"):
    return {"event": "Goal", "player": player, "team": team, "period": period}


# ----------------------------------------------------------------------
# Three stars: selection criteria
# ----------------------------------------------------------------------

def test_hat_trick_first():
    home, away = mk_teams()
    hatty = mk_player("Hat", "Trick", PlayerPosition.CENTER)
    twopt = mk_player("Two", "Point", PlayerPosition.LEFT_WING)
    goalie = mk_player("Brick", "Wall", PlayerPosition.GOALIE)
    filler = mk_player("Fill", "Er", PlayerPosition.RIGHT_WING)
    home.roster = [hatty, twopt, goalie, filler]
    away.roster = [mk_player("Opp", "One", PlayerPosition.CENTER)]
    gr = {"home_score": 4, "away_score": 1, "winner": home,
          "notable_events": [goal_event(hatty), goal_event(hatty),
                             goal_event(hatty), goal_event(twopt)],
          "game_stats": {hatty.id: set_line(hatty, g=3, a=1),
                         twopt.id: set_line(twopt, g=0, a=2),
                         goalie.id: set_line(goalie, saves=24),
                         filler.id: set_line(filler, g=1, a=0)}}
    out = select_three_stars(gr, home, away)
    check("hat trick is 1st star",
          len(out) == 3 and out[0]["player_id"] == hatty.id
          and out[0]["rank"] == 1)
    check("three stars ranked", [s["rank"] for s in out] == [1, 2, 3])
    check("stars carry lines", "3 G, 1 A" in out[0]["line"])


def test_shutout_goalie_first():
    home, away = mk_teams()
    sniper = mk_player("Two", "Goals", PlayerPosition.CENTER)
    goalie = mk_player("Brick", "Wall", PlayerPosition.GOALIE)
    home.roster = [sniper, goalie]
    away.roster = [mk_player("Opp", "One", PlayerPosition.CENTER)]
    gr = {"home_score": 2, "away_score": 0, "winner": home,
          "notable_events": [goal_event(sniper), goal_event(sniper)],
          "game_stats": {sniper.id: set_line(sniper, g=2, a=0),
                         goalie.id: set_line(goalie, saves=38)}}
    out = select_three_stars(gr, home, away)
    check("38-save shutout beats 2-goal skater",
          out and out[0]["player_id"] == goalie.id)
    check("shutout noted in line", out and "shutout" in out[0]["line"])


def test_ot_winner_bump():
    home, away = mk_teams()
    ot_hero = mk_player("OT", "Hero", PlayerPosition.CENTER)
    reg = mk_player("Reg", "Ular", PlayerPosition.LEFT_WING)
    home.roster = [ot_hero, reg]
    away.roster = [mk_player("Opp", "One", PlayerPosition.CENTER)]
    gr = {"home_score": 3, "away_score": 2, "winner": home,
          "notable_events": [goal_event(reg, period=1),
                             goal_event(ot_hero, period=4)],
          "game_stats": {ot_hero.id: set_line(ot_hero, g=1, a=0),
                         reg.id: set_line(reg, g=1, a=1)}}
    out = select_three_stars(gr, home, away)
    check("OT winner outranks better regulation line",
          out and out[0]["player_id"] == ot_hero.id)
    check("OT winner noted", out and "OT winner" in out[0]["line"])


def test_losing_team_can_star():
    home, away = mk_teams()
    loser_star = mk_player("Lose", "Star", PlayerPosition.CENTER)
    winner_grinder = mk_player("Win", "Grinder", PlayerPosition.LEFT_WING)
    home.roster = [winner_grinder]
    away.roster = [loser_star]
    gr = {"home_score": 2, "away_score": 1, "winner": home,
          "notable_events": [goal_event(loser_star, team="Away")],
          "game_stats": {loser_star.id: set_line(loser_star, g=1, a=2),
                         winner_grinder.id: set_line(winner_grinder, g=1, a=0)}}
    out = select_three_stars(gr, home, away)
    # 1G 2A = 7 pts on losing team vs 1G 0A + win lean = 4: loser still stars
    check("big night on losing team still stars",
          any(s["player_id"] == loser_star.id for s in out))


def test_empty_game_stats():
    out = select_three_stars({"game_stats": {}}, None, None)
    check("no per-player stats -> no stars", out == [])


# ----------------------------------------------------------------------
# Three stars: recording
# ----------------------------------------------------------------------

def _two_star_game(preseason=False):
    home, away = mk_teams()
    s1 = mk_player("First", "Star", PlayerPosition.CENTER)
    s2 = mk_player("Second", "Star", PlayerPosition.GOALIE)
    home.roster = [s1, s2]
    away.roster = [mk_player("Opp", "One", PlayerPosition.CENTER)]
    gr = {"home_score": 3, "away_score": 1, "winner": home,
          "notable_events": [goal_event(s1), goal_event(s1)],
          "game_stats": {s1.id: set_line(s1, g=2, a=1),
                         s2.id: set_line(s2, saves=29)}}
    return home, away, s1, s2, gr


def test_record_counts_and_moment():
    home, away, s1, s2, gr = _two_star_game()
    out = record_game_stars(gr, home, away, preseason=False,
                            game_date=date(2026, 10, 15))
    check("stars stamped on result", gr.get("three_stars") == out
          and len(out) == 2)
    check("result stars are plain dicts",
          all(isinstance(s, dict) for s in out))
    try:
        json.dumps(out)
        js_ok = True
    except Exception:
        js_ok = False
    check("result stars JSON-serializable (save-safe)", js_ok)
    c1 = getattr(s1, "game_stars", {})
    check("1st star count bumped", c1.get("first") == 1)
    c2 = getattr(s2, "game_stars", {})
    check("2nd star count bumped", c2.get("second") == 1)
    moms = [m for m in getattr(s1, "career_moments", [])
            if isinstance(m, dict) and m.get("kind") == "first_star"]
    check("1st star lands in Signature Games",
          len(moms) == 1 and "1st Star of the Game" in moms[0]["label"])
    moms2 = [m for m in getattr(s2, "career_moments", [])
             if isinstance(m, dict) and m.get("kind") == "first_star"]
    check("2nd star gets no Signature Games moment", moms2 == [])


def test_preseason_no_stars():
    home, away, s1, s2, gr = _two_star_game()
    out = record_game_stars(gr, home, away, preseason=True,
                            game_date=date(2026, 9, 25))
    check("preseason names no stars", out == []
          and gr.get("three_stars") == [])
    check("preseason bumps no counts",
          getattr(s1, "game_stars", {}).get("first", 0) == 0)


def test_first_star_moment_idempotent():
    home, away, s1, s2, gr = _two_star_game()
    record_game_stars(gr, home, away, game_date=date(2026, 10, 15))
    # Simulate a second recording of the same night (must not double).
    stars._record_first_star_moment(
        s1, gr["three_stars"][0], gr, home, away, date(2026, 10, 15))
    moms = [m for m in s1.career_moments
            if isinstance(m, dict) and m.get("kind") == "first_star"]
    check("first-star moment not duplicated", len(moms) == 1)


# ----------------------------------------------------------------------
# Monthly awards
# ----------------------------------------------------------------------

def _set_stats(p, g=0, a=0, gp=0, w=0, so=0, saves=0, sa=0, ga=0):
    p.stats.goals = g
    p.stats.assists = a
    p.stats.games_played = gp
    p.stats.wins = w
    p.stats.shutouts = so
    p.stats.saves = saves
    p.stats.shots_against = sa
    p.stats.goals_against = ga


def _league_fixture():
    """Two NHL teams; baselines stamped, then a month of stats added."""
    t1 = Team("T1", "City", "Div", "Conf")
    t2 = Team("T2", "City", "Div", "Conf")
    star = mk_player("Point", "Leader", PlayerPosition.CENTER)
    grinder = mk_player("Depth", "Guy", PlayerPosition.LEFT_WING)
    parttimer = mk_player("Part", "Timer", PlayerPosition.RIGHT_WING)
    t1.roster = [star, grinder, parttimer]
    dom_goalie = mk_player("Dom", "Inant", PlayerPosition.GOALIE)
    avg_goalie = mk_player("Avg", "Joe", PlayerPosition.GOALIE)
    rook = mk_player("Rook", "Ie", PlayerPosition.CENTER, rookie=True)
    t2.roster = [dom_goalie, avg_goalie, rook]
    stamp_monthly_baselines([t1, t2])
    # The month:
    _set_stats(star, g=11, a=13, gp=13)          # 24 pts
    _set_stats(grinder, g=4, a=5, gp=13)         # 9 pts
    _set_stats(parttimer, g=8, a=7, gp=5)        # 15 pts but only 5 GP
    _set_stats(dom_goalie, gp=10, w=8, so=2, saves=282, sa=300, ga=18)
    _set_stats(avg_goalie, gp=9, w=5, so=0, saves=220, sa=245, ga=25)
    _set_stats(rook, g=6, a=8, gp=13)            # 14 pts, rookie
    return [t1, t2], star, dom_goalie, rook


def test_potm_points_leader():
    teams, star, dom_goalie, rook = _league_fixture()
    # Neutralize the dominant goalie for this test: make him average.
    _set_stats(dom_goalie, gp=10, w=5, so=0, saves=250, sa=280, ga=30)
    potm, rotm = select_monthly_winners(teams)
    check("POTM is the points leader",
          potm is not None and potm[0] is star)
    check("POTM line reads right",
          potm is not None and "24 points" in potm[2])
    check("5-GP scorer cannot win despite points",
          potm is not None and "Part Timer" not in potm[2])


def test_dominant_goalie_takes_month():
    teams, star, dom_goalie, rook = _league_fixture()
    potm, _ = select_monthly_winners(teams)
    check("dominant goalie month beats 24-point skater",
          potm is not None and potm[0] is dom_goalie)


def test_average_goalie_does_not_take_month():
    teams, star, dom_goalie, rook = _league_fixture()
    _set_stats(dom_goalie, gp=10, w=5, so=0, saves=250, sa=280, ga=30)
    potm, _ = select_monthly_winners(teams)
    check("average goalie month does not steal POTM",
          potm is not None and potm[0] is star)


def test_rotm_rookies_only():
    teams, star, dom_goalie, rook = _league_fixture()
    _, rotm = select_monthly_winners(teams)
    check("ROTM goes to a rookie",
          rotm is not None and rotm[0] is rook
          and "14 points" in rotm[2])


def test_rookie_cannot_win_both():
    t = Team("T", "City", "Div", "Conf")
    phenom = mk_player("Phe", "Nom", PlayerPosition.CENTER, rookie=True)
    vet = mk_player("Vet", "Eran", PlayerPosition.LEFT_WING)
    t.roster = [phenom, vet]
    stamp_monthly_baselines([t])
    _set_stats(phenom, g=14, a=16, gp=13)   # 30 pts -- best in league
    _set_stats(vet, g=5, a=5, gp=13)
    potm, rotm = select_monthly_winners([t])
    check("rookie phenom wins POTM",
          potm is not None and potm[0] is phenom)
    check("same rookie does not also win ROTM", rotm is None)


def test_monthly_tick_banks_and_announces():
    teams, star, dom_goalie, rook = _league_fixture()
    _set_stats(dom_goalie, gp=10, w=5, so=0, saves=250, sa=280, ga=30)
    news = []
    app = SimpleNamespace(
        league=SimpleNamespace(teams=teams),
        current_date=date(2026, 11, 1),
        add_news=lambda s: news.append(s))
    out = monthly_awards_tick(app)
    check("tick awards October 2026", out and out.get("month") == "Oct 2026")
    acc = {e.get("award"): e.get("year")
           for e in star.career_accolades if isinstance(e, dict)}
    check("POTM banked as accolade",
          acc.get("player_of_month") == "Oct 2026")
    acc_r = {e.get("award"): e.get("year")
             for e in rook.career_accolades if isinstance(e, dict)}
    check("ROTM banked as accolade",
          acc_r.get("rookie_of_month") == "Oct 2026")
    check("news announced", len(news) == 2
          and any("Player of the Month" in n for n in news)
          and any("Rookie of the Month" in n for n in news))
    moms = [m for m in star.career_moments
            if isinstance(m, dict) and m.get("kind") == "player_of_month"]
    check("POTM lands in Signature Games", len(moms) == 1)
    # Second tick with no new stats: nothing new, no duplicates.
    n_news = len(news)
    out2 = monthly_awards_tick(app)
    acc2 = [e for e in star.career_accolades
            if isinstance(e, dict) and e.get("award") == "player_of_month"]
    moms2 = [m for m in star.career_moments
             if isinstance(m, dict) and m.get("kind") == "player_of_month"]
    check("re-tick banks nothing new",
          len(acc2) == 1 and len(moms2) == 1 and len(news) == n_news)


def test_playoff_month_skipped():
    teams, star, dom_goalie, rook = _league_fixture()
    news = []
    app = SimpleNamespace(
        league=SimpleNamespace(teams=teams),
        current_date=date(2027, 6, 1),
        add_news=lambda s: news.append(s))
    out = monthly_awards_tick(app)
    check("May (playoffs) names no winners", out is None and news == [])
    # ...but baselines still re-stamped.
    check("baselines stamped through skipped month",
          getattr(star, "month_baseline", {}).get("g") == 11)


def test_new_fields_save_safe():
    home, away, s1, s2, gr = _two_star_game()
    record_game_stars(gr, home, away, game_date=date(2026, 10, 15))
    app = SimpleNamespace(
        league=SimpleNamespace(teams=[home, away]),
        current_date=date(2026, 11, 1),
        add_news=lambda s: None)
    stamp_monthly_baselines([home, away])
    blob = {
        "game_stars": getattr(s1, "game_stars", None),
        "month_baseline": getattr(s1, "month_baseline", None),
        "career_moments": getattr(s1, "career_moments", None),
    }
    try:
        json.dumps(blob)
        ok = True
    except Exception:
        ok = False
    check("new player fields JSON-serializable (save/load safe)", ok)


def _star_moment(dstr, detail="3 G, 1 A vs TOR (5-2 W)"):
    return {"date": dstr, "kind": "first_star",
            "label": "1st Star of the Game", "detail": detail}


def test_repeat_first_stars_collapse():
    moms = [_star_moment("2026-10-15"), _star_moment("2026-11-02"),
            _star_moment("2026-12-01"),
            {"date": "2026-10-20", "kind": "hat_trick",
             "label": "Hat trick", "detail": "3 G vs MTL"}]
    rows = signature_game_rows(moms)
    check("repeat 1st stars collapse to 2 rows",
          len(rows) == 2)
    agg = rows[0]
    check("aggregate shows tally",
          agg["line1"] == "\u2b50 1st Star of the Game \u00d73")
    check("aggregate lists every date",
          agg["detail"] == "Dec 01, 2026, Nov 02, 2026, Oct 15, 2026")
    check("aggregate consumes all star moments", agg["consumed"] == 3)
    check("hat trick keeps its own row",
          rows[1]["line1"].startswith("\U0001f3a9 Hat trick"))


def test_single_first_star_keeps_detail():
    rows = signature_game_rows([_star_moment("2026-10-15")])
    check("single 1st star is one row", len(rows) == 1)
    check("single 1st star keeps game line",
          rows[0]["detail"] == "3 G, 1 A vs TOR (5-2 W)"
          and "Oct 15, 2026" in rows[0]["line1"]
          and "\u00d7" not in rows[0]["line1"])


def test_aggregate_sits_chronologically():
    moms = [_star_moment("2026-10-15"), _star_moment("2026-10-18"),
            {"date": "2026-11-05", "kind": "hat_trick",
             "label": "Hat trick", "detail": "3 G vs MTL"}]
    rows = signature_game_rows(moms)
    check("newer hat trick rows above the star aggregate",
          rows[0]["line1"].startswith("\U0001f3a9")
          and "\u00d72" in rows[1]["line1"])


def test_more_count_with_aggregate():
    moms = [_star_moment(f"2026-12-{d:02d}") for d in (1, 5, 9)]
    moms += [{"date": f"2026-11-{d:02d}", "kind": "hat_trick",
              "label": "Hat trick", "detail": "3 G"} for d in range(1, 7)]
    rows = signature_game_rows(moms)
    check("9 moments -> 7 rows", len(rows) == 7)
    shown, total = rows[:6], sum(r["consumed"] for r in rows)
    consumed = sum(r["consumed"] for r in shown)
    check("consumed math leaves 1 hidden",
          total == 9 and consumed == 8 and total - consumed == 1)


def test_empty_moments():
    check("no moments -> no rows", signature_game_rows([]) == []
          and signature_game_rows(None) == [])


if __name__ == "__main__":
    test_hat_trick_first()
    test_shutout_goalie_first()
    test_ot_winner_bump()
    test_losing_team_can_star()
    test_empty_game_stats()
    test_record_counts_and_moment()
    test_preseason_no_stars()
    test_first_star_moment_idempotent()
    test_potm_points_leader()
    test_dominant_goalie_takes_month()
    test_average_goalie_does_not_take_month()
    test_rotm_rookies_only()
    test_rookie_cannot_win_both()
    test_monthly_tick_banks_and_announces()
    test_playoff_month_skipped()
    test_new_fields_save_safe()
    test_repeat_first_stars_collapse()
    test_single_first_star_keeps_detail()
    test_aggregate_sits_chronologically()
    test_more_count_with_aggregate()
    test_empty_moments()
    print(f"\n{ PASS } passed, { FAIL } failed"
          + (f": {FAILURES}" if FAILURES else ""))
    sys.exit(1 if FAIL else 0)
