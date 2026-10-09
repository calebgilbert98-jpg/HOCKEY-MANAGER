# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for the AHL UI build: standings/scores/Calder Cup/team/prospects
screens build without errors, data displays correctly, navigation works,
and AHL narratives fire through the shared headline system.

Run: python3 qa_ahl_ui.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = []
FAIL = []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print(f"  PASS: {name}")
    except AssertionError as e:
        FAIL.append((name, str(e)))
        print(f"  FAIL: {name}: {e}")
    except Exception as e:
        FAIL.append((name, f"{type(e).__name__}: {e}"))
        print(f"  ERROR: {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=3)


# ---------------------------------------------------------------------------
# Backend: results tracking
# ---------------------------------------------------------------------------

def _make_league():
    import ahl_league as al

    class T:
        def __init__(self, name, parent=None):
            self.team_name = name
            self.league_level = 2
            self.league_name = "American Hockey League"
            self.parent_team = parent
            self.ahl_roster = []

    class L:
        season_year = 2026

    parents = [type("P", (), {"team_name": f"NHL Club {i}",
                              "ahl_roster": []})() for i in range(4)]
    league = L()
    league.teams = [T(f"AHL Club {i}", parents[i]) for i in range(4)]
    return league, al


def test_record_result():
    league, al = _make_league()
    assert al._record_result(league, "2026-10-05", 0, 1, 4, 2) is True
    recent = al.get_ahl_recent_results(league, n=5)
    assert len(recent) == 1
    assert recent[0]["home_score"] == 4
    assert recent[0]["away_score"] == 2
    # ring buffer cap
    for i in range(150):
        al._record_result(league, "2026-10-06", 0, 1, 1, 0)
    assert len(league.ahl_results) <= al._AHL_RESULTS_CAP


def test_recent_results_newest_first():
    league, al = _make_league()
    al._record_result(league, "2026-10-01", 0, 1, 2, 1)
    al._record_result(league, "2026-10-02", 2, 3, 5, 4)
    recent = al.get_ahl_recent_results(league, n=5)
    assert recent[0]["date"] == "2026-10-02"
    assert recent[1]["date"] == "2026-10-01"


def test_upcoming_filters_played():
    league, al = _make_league()
    league.ahl_schedule = [("2026-10-10", 0, 1), ("2026-10-11", 2, 3),
                           ("2026-10-01", 0, 2)]
    league.ahl_played = {2}  # the Oct 1 game already played
    up = al.get_ahl_upcoming(league, "2026-10-05", n=10)
    assert len(up) == 2, f"expected 2 upcoming, got {len(up)}"
    assert up[0]["date"] == "2026-10-10"


def test_team_schedule():
    league, al = _make_league()
    league.ahl_schedule = [("2026-10-10", 0, 1), ("2026-10-11", 2, 3),
                           ("2026-10-12", 0, 3)]
    league.ahl_played = set()
    sched = al.get_ahl_team_schedule(league, 0, "2026-10-05", n=10)
    assert len(sched) == 2
    assert sched[0]["home"] is True
    assert sched[1]["home"] is True  # team 0 is home in (0,3)


def test_backend_never_raises():
    import ahl_league as al
    assert al.get_ahl_recent_results(None) == []
    assert al.get_ahl_upcoming(None, None) == []
    assert al.get_ahl_team_schedule(None, 0, None) == []
    assert al._record_result(None, None, 0, 0, 0, 0) is False
    assert al._tname([], 99) == "AHL club 99"


# ---------------------------------------------------------------------------
# Headline builder
# ---------------------------------------------------------------------------

def test_ahl_story_headline():
    from headlines import make_headline
    from datetime import date
    msg = make_headline("ahl_story", date(2026, 10, 5),
                        headline="Test race", body="Test body",
                        story_type="calder_race", team_name="Wolves")
    assert msg is not None
    assert "Test race" in msg.subject
    assert msg.category == "AHL Story"


def test_ahl_story_unknown_kind():
    from headlines import make_headline
    from datetime import date
    assert make_headline("nope_not_real", date(2026, 10, 5)) is None


# ---------------------------------------------------------------------------
# Narratives (pure generators)
# ---------------------------------------------------------------------------

def test_narratives_never_raise():
    import ahl_narratives as an
    assert an.calder_race_narrative(None) is None
    assert an.prospect_watch_narrative(None) is None
    assert an.cinderella_narrative(None) is None
    assert an.maybe_fire_ahl_narratives(None) is False


def test_cinderella_detection():
    import ahl_league as al
    import ahl_narratives as an
    league, _ = _make_league()

    class T:
        def __init__(self, name):
            self.team_name = name
            self.league_level = 2
            self.league_name = "American Hockey League"
            self.parent_team = None
            self.ahl_roster = []
    # 16 teams so seeds 13-16 exist
    league.teams = [T(f"Club {i}") for i in range(16)]
    # fake standings: index order == seed order
    league.ahl_standings = {i: {"pts": 100 - i * 2, "w": 0, "gp": 0}
                            for i in range(16)}
    # bracket: 15-seed (idx 14) wins round 0
    league.ahl_bracket = {"season": "2026-27", "rounds": [
        [{"home": 0, "away": 14, "winner": 14, "games": 5}],
    ], "champion_idx": 14, "runner_up_idx": 0}
    story = an.cinderella_narrative(league)
    assert story is not None, "expected a cinderella story"
    assert story["story_type"] == "cinderella"
    assert "15" in story["headline"]
    # idempotent: second call finds nothing new
    assert an.cinderella_narrative(league) is None


# ---------------------------------------------------------------------------
# UI: view builds without a display (Xvfb) -- widget smoke test
# ---------------------------------------------------------------------------

def _tk_root():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        return root
    except Exception as e:
        raise AssertionError(f"no display: {e}")


def test_view_imports():
    import ahl_league_window as w
    assert hasattr(w, "AHLLeagueView")
    assert w.AHLLeagueView.TABS == ["Standings", "Scores", "Calder Cup",
                                    "Team", "Prospects"]


def test_view_builds():
    import ahl_league_window as w

    class FakeApp:
        def __init__(self, root):
            self.open_windows = {}

        @property
        def game_manager(self):
            return self

        @property
        def league(self):
            return None

        @property
        def current_date(self):
            return None

    # needs customtkinter; skip gracefully if unavailable
    try:
        import customtkinter  # noqa
    except Exception:
        print("    (customtkinter unavailable -- widget test skipped)")
        return
    root = _tk_root()
    try:
        app = FakeApp(root)
        view = w.AHLLeagueView(root, app=app)
        # all five tabs built
        assert len(view._tab_frames) == 5
        # tab switching doesn't raise
        for t in w.AHLLeagueView.TABS:
            view._select_tab(t)
        # refresh with no league doesn't raise
        view.refresh_all()
        view.destroy()
    finally:
        root.destroy()


def test_main_wiring():
    # open_ahl_stats_window now opens the league hub
    import ast
    src = open(os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "main.py")).read()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and \
                node.name == "open_ahl_stats_window":
            body = ast.get_source_segment(src, node)
            assert "AHLLeagueView" in body, \
                "open_ahl_stats_window should open AHLLeagueView"
            assert "'ahl_league'" in body or '"ahl_league"' in body
            found = True
    assert found, "open_ahl_stats_window not found in main.py"


if __name__ == "__main__":
    print("AHL UI QA")
    for name, fn in sorted([(k, v) for k, v in list(globals().items())
                            if k.startswith("test_")]):
        check(name, fn)
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
