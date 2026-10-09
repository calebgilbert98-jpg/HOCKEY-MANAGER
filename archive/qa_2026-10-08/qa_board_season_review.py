# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Smoke: BUG-011 wiring -- BoardSystem.season_review() has a real caller.

_offseason_board_review() (new in main.py) resolves the user's playoff
result from the bracket, calls board.season_review(), stashes the facts
for the season-review inbox card, and rolls the season (1 -> 2).
"""
from types import SimpleNamespace

import main
from manager_career import BoardSystem

App = main.HockeyManagerGUI
passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {detail}")


def series(t1, t2, winner, w1, w2):
    return SimpleNamespace(
        team1=SimpleNamespace(team_name=t1),
        team2=SimpleNamespace(team_name=t2),
        winner=SimpleNamespace(team_name=winner),
        team1_wins=w1, team2_wins=w2)


def fake_app(board, bracket):
    from types import MethodType
    news = []
    app = SimpleNamespace(
        user_team=SimpleNamespace(team_name="Chicago Blackhawks"),
        league=SimpleNamespace(playoff_bracket=bracket),
        open_windows={},
        career=SimpleNamespace(board=board),
        add_news=news.append)
    # Bind the real methods (in production both live on the app).
    app._user_playoff_result = MethodType(App._user_playoff_result, app)
    app._offseason_board_review = MethodType(App._offseason_board_review, app)
    return app


def main_test():
    # User wins R1, loses R2; someone else wins the Cup.
    bracket = SimpleNamespace(
        playoff_series={
            "round1": [series("Chicago Blackhawks", "Detroit Red Wings",
                              "Chicago Blackhawks", 4, 2)],
            "round2": [series("Chicago Blackhawks", "Colorado Avalanche",
                              "Colorado Avalanche", 1, 4)],
        },
        stanley_cup_champion=SimpleNamespace(team_name="Winnipeg Jets"))
    board = BoardSystem()
    board.expectation = "playoffs"
    board.confidence = 60
    app = fake_app(board, bracket)

    made, rounds, cup = app._user_playoff_result()
    check("playoff result parsed", (made, rounds, cup) == (True, 1, False),
          f"got {(made, rounds, cup)}")

    app._offseason_board_review()
    check("season rolled 1 -> 2", board.season_number == 2,
          f"season_number={board.season_number}")
    check("expectation met: confidence up",
          board.confidence > 60, f"confidence={board.confidence}")
    sr = app._season_review_board
    check("facts stashed for inbox card",
          sr["made_playoffs"] and sr["playoff_rounds_won"] == 1
          and not sr["won_cup"] and "headline" in sr, str(sr))

    # Missed everything in year 1: honeymoon floors at 1, no sack.
    board2 = BoardSystem()
    board2.expectation = "win_cup"
    board2.confidence = 5
    bracket2 = SimpleNamespace(
        playoff_series={"round1": [series("Boston Bruins", "Toronto Maple Leafs",
                                          "Boston Bruins", 4, 0)]},
        stanley_cup_champion=SimpleNamespace(team_name="Boston Bruins"))
    app2 = fake_app(board2, bracket2)
    made2, rounds2, cup2 = app2._user_playoff_result()
    check("non-playoff team parsed", (made2, rounds2, cup2) == (False, 0, False),
          f"got {(made2, rounds2, cup2)}")
    app2._offseason_board_review()
    check("year-1 honeymoon: not sacked, confidence floored",
          not board2.sacked and board2.confidence >= 1,
          f"sacked={board2.sacked} conf={board2.confidence}")
    check("season rolled", board2.season_number == 2)

    # No bracket at all: defensive, still rolls the season.
    board3 = BoardSystem()
    board3.expectation = "rebuild"
    app3 = fake_app(board3, None)
    app3._offseason_board_review()
    check("missing bracket: no crash, season rolls",
          board3.season_number == 2, f"season_number={board3.season_number}")

    # No career (pure sim mode): no-op, no crash.
    app4 = SimpleNamespace(user_team=None, league=None, open_windows={},
                           career=None)
    try:
        App._offseason_board_review(app4)
        check("no career: silent no-op", True)
    except Exception as e:  # noqa: BLE001
        check("no career: silent no-op", False, str(e))

    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main_test()
