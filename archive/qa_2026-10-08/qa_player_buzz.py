"""Adversarial test for player-level Fan Buzz (native_ui/screens/news.py).

Uses REAL game_classes.Player objects from PlayerGenerator (not mocks).
Verifies:
  1. Payload rows EXACTLY match direct reputation_system.fan_favourite_score
     calls on the same real players (no invented data).
  2. Traded star: removed from roster -> disappears from payload.
  3. New season (games_played=0/1, points=0): nobody >=70 -> empty favs.
  4. Season progression: boosting points raises score / changes ranking.
  5. Missing league / missing user team -> None (no crash).
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reputation_system as rs
from player_generator import PlayerGenerator
from native_ui.screens import news


class FakeLeague:
    def __init__(self, teams):
        self.teams = teams
        self.rivalries = []


class FakeTeam:
    def __init__(self, name, roster):
        self.team_name = name
        self.roster = roster


class FakeGM:
    def __init__(self, league, user_team):
        self.league = league
        self.user_team = user_team


class FakeGame:
    def __init__(self, league, user_team):
        self.game_manager = FakeGM(league, user_team)
        self.current_date = None


def pname(p):
    return getattr(p, "full_name", "") or (
        f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip())


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    return ok


def make_roster():
    gen = PlayerGenerator()
    # star captain: long tenure, high reputation/leadership, big production
    star = gen.create_player(skill_tier="NHL_ELITE", age_category="PRIME")
    star.captaincy = "C"
    star.team_tenure = "6 seasons"
    star.reputation = 90
    star.leadership = 88
    star.games_played = 50
    star.goals, star.assists = 25, 35
    star.points = 60
    star.controversy = 30
    # second-line producer, short tenure
    mid = gen.create_player(skill_tier="NHL_STARTER", age_category="PRIME")
    mid.team_tenure = "This season"
    mid.reputation = 55
    mid.leadership = 60
    mid.games_played = 50
    mid.goals, mid.assists = 12, 18
    mid.points = 30
    mid.controversy = 40
    # depth grinder, long tenure, no production
    depth = gen.create_player(skill_tier="NHL_DEPTH", age_category="VETERAN")
    depth.team_tenure = "4+ seasons"
    depth.reputation = 45
    depth.leadership = 70
    depth.games_played = 48
    depth.goals, depth.assists = 4, 6
    depth.points = 10
    depth.controversy = 20
    # rookie phenom hype: young, producing
    rook = gen.create_player(skill_tier="NHL_STARTER", age_category="YOUNG")
    rook.age = 20
    rook.team_tenure = "This season"
    rook.reputation = 40
    rook.leadership = 45
    rook.games_played = 45
    rook.goals, rook.assists = 15, 17
    rook.points = 32
    rook.controversy = 35
    return [star, mid, depth, rook]


def main():
    ok = True
    roster = make_roster()
    team = FakeTeam("Test Team", roster)
    league = FakeLeague([team])
    game = FakeGame(league, team)

    # --- 1. baseline: payload vs direct engine calls -------------------------
    pb = news._playerbuzz_payload(game)
    ok &= check(pb is not None, "1a payload not None")
    ok &= check(pb["team_name"] == "Test Team", "1b team name matches")
    direct = {id(p): float((rs.fan_favourite_score(p, team, rivalries=[]) or {})
                          .get("score", 0) or 0) for p in roster}
    ok &= check(len(pb["rows"]) == len(roster),
                f"1c rows={len(pb['rows'])} == roster={len(roster)}")
    ok &= check(all(abs(r["score"] - direct[id(r["player"])]) < 1e-9
                    for r in pb["rows"]),
                "1d every row score == direct engine score")
    scores = [r["score"] for r in pb["rows"]]
    ok &= check(scores == sorted(scores, reverse=True),
                "1e rows sorted descending")
    ok &= check({pname(r["player"]) for r in pb["rows"]}
                == {pname(p) for p in roster},
                "1f payload names == real roster names")
    favs = [r for r in pb["rows"] if r["score"] >= news._FAN_FAV_THRESHOLD]
    rising = [r for r in pb["rows"]
              if news._ON_RISE_THRESHOLD <= r["score"] < news._FAN_FAV_THRESHOLD]
    print(f"    rows: " + ", ".join(
        f"{pname(r['player']).split()[-1]}={r['score']:.0f}({r['tier']})"
        for r in pb["rows"]))
    print(f"    favs={len(favs)}, rising={len(rising)}")

    # --- 2. traded star -------------------------------------------------------
    star = max(roster, key=lambda p: direct[id(p)])
    team.roster = [p for p in roster if p is not star]
    pb2 = news._playerbuzz_payload(game)
    ok &= check(all(r["player"] is not star for r in pb2["rows"])
                and len(pb2["rows"]) == len(roster) - 1,
                "2 traded star disappears from payload")
    team.roster = roster  # restore

    # --- 3. new season ---------------------------------------------------------
    fresh = make_roster()
    for p in fresh:
        p.games_played = 1
        p.goals = p.assists = p.points = 0
        p.team_tenure = "This season"
        p.reputation = 30
    team3 = FakeTeam("Fresh Team", fresh)
    pb3 = news._playerbuzz_payload(FakeGame(league, team3))
    favs3 = [r for r in pb3["rows"] if r["score"] >= news._FAN_FAV_THRESHOLD]
    ok &= check(len(favs3) == 0,
                f"3 new season: no fan favourites "
                f"(max={max(r['score'] for r in pb3['rows']):.0f})")

    # --- 4. season progression -------------------------------------------------
    before = {id(r["player"]): r["score"] for r in pb["rows"]}
    cold = min(roster, key=lambda p: before[id(p)])
    cold.goals, cold.assists, cold.points = 30, 40, 70
    cold.games_played = 55
    pb4 = news._playerbuzz_payload(game)
    after = {id(r["player"]): r["score"] for r in pb4["rows"]}
    ok &= check(after[id(cold)] > before[id(cold)],
                f"4 hot streak raises score "
                f"({before[id(cold)]:.0f} -> {after[id(cold)]:.0f})")

    # --- 5. missing pieces ----------------------------------------------------
    ok &= check(news._playerbuzz_payload(FakeGame(None, None)) is None,
                "5a no league -> None")
    ok &= check(news._playerbuzz_payload(FakeGame(league, None)) is None,
                "5b no user team -> None")

    print("\nALL PASS" if ok else "\nSOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
