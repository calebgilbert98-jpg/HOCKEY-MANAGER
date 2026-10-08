"""Team H fixes: FA frenzy single path, records redirect, shot chart viewer.

Headless tests using qtstub/PySide6. Run:
    python3 tests/test_native_team_h.py
"""
import ast
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "qtstub"))
sys.path.insert(0, REPO)
os.chdir(REPO)

from PySide6.QtGui import QPainter as _StubPainter  # noqa: E402

from native_ui.screens import free_agents  # noqa: E402
from native_ui.screens.records import RecordsScreen  # noqa: E402
from native_ui.screens.shot_chart_viewer import (  # noqa: E402
    ShotChartViewerScreen, RinkWidget)
import native_ui.screens.shot_chart_viewer as scv_mod  # noqa: E402
import native_ui.screens.fa_frenzy as faf_mod  # noqa: E402
import native_ui.screens.stats as stats_mod  # noqa: E402


def _src(path):
    with open(os.path.join(REPO, path)) as fh:
        return fh.read()


class FakeMainWindow:
    def __init__(self):
        self.calls = []
        self._screens = {}

    def show_screen(self, name):
        self.calls.append(name)


class FakeScroll:
    def __init__(self, widget):
        self._w = widget

    def widget(self):
        return self._w


class FakeTabs:
    def __init__(self, labels):
        self._labels = list(labels)
        self.focused = None

    def count(self):
        return len(self._labels)

    def tabText(self, i):
        return self._labels[i]

    def setCurrentIndex(self, i):
        self.focused = i


class FakeStore:
    def __init__(self):
        self.games = []
        self._by_id = {}

    def add(self, game_dict):
        self.games.append(game_dict)
        self._by_id[game_dict.get("game_id")] = game_dict

    def get(self, game_id):
        return self._by_id.get(game_id)

    def aggregate_team_shots(self, team_name, last_n=5):
        return []

    def for_player(self, player_id):
        return []


def _real_shots():
    return [
        {"x": 80, "y": 10, "side": "home", "result": "goal"},
        {"x": 70, "y": -12, "side": "away", "result": "save"},
        {"x": 60, "y": 5, "side": "home", "result": "block"},
        {"x": 55, "y": -20, "side": "away", "result": "miss"},
    ]


# ---------------------------------------------------------------- FIX 1 ---

def test_fix1_no_frenzy_dialog_class():
    tree = ast.parse(_src("native_ui/screens/free_agents.py"))
    classes = [n.name for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef)]
    assert "FrenzyDialog" not in classes, \
        "FrenzyDialog still exists -- frenzy must be screen-only"


def test_fix1_no_frenzy_dialog_references():
    src = _src("native_ui/screens/free_agents.py")
    assert "FrenzyDialog" not in src, "stray FrenzyDialog reference remains"


def test_fix1_open_frenzy_navigates_to_screen():
    tree = ast.parse(_src("native_ui/screens/free_agents.py"))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_open_frenzy":
            src = ast.dump(n)
            assert 'navigate_to' in src or 'show_screen' in src
            assert 'fa_frenzy' in src
            return
    raise AssertionError("_open_frenzy not found")


def test_fix1_banner_click_navigates():
    mw = FakeMainWindow()
    game = type("G", (), {"current_date": None})()
    screen = free_agents.FreeAgentsScreen(game, mw)
    assert mw.calls == [], "construction should not navigate"
    screen._banner_btn.click()
    assert mw.calls == ["fa_frenzy"], \
        f"banner must navigate to fa_frenzy screen, got {mw.calls}"


def test_fix1_banner_hidden_when_no_frenzy():
    # Adversarial: no FA pool, no frenzy day -> refresh must not crash
    # and the banner stays hidden.
    mw = FakeMainWindow()
    game = type("G", (), {"current_date": None})()
    screen = free_agents.FreeAgentsScreen(game, mw)
    screen.refresh()
    assert screen._banner_btn.isVisible() is False


def test_fix1_frenzy_offer_uses_free_agents_open_offer():
    # The dialog's Offer deep-link (set_offer_player -> open_offer with
    # missing-player warning) is ported into the screen: _on_offer must
    # navigate to free_agents and use the market screen's open_offer.
    src = _src("native_ui/screens/fa_frenzy.py")
    assert "open_offer" in src, \
        "_on_offer must reuse FreeAgentsScreen.open_offer"


# ---------------------------------------------------------------- FIX 2 ---

def test_fix2_records_redirects_to_stats():
    mw = FakeMainWindow()
    stats_inner = type("S", (), {})()
    stats_inner.tabs = FakeTabs(["Leaders", "Records", "NHL Records", "xG"])
    mw._screens["stats"] = FakeScroll(stats_inner)
    screen = RecordsScreen(object(), mw)
    assert mw.calls == [], "construction should not navigate yet"
    screen._redirect()
    assert mw.calls == ["stats"], f"expected ['stats'], got {mw.calls}"
    assert stats_inner.tabs.focused == 1, \
        f"Records tab not focused, got {stats_inner.tabs.focused}"


def test_fix2_records_refresh_redirects():
    mw = FakeMainWindow()
    mw._screens["stats"] = FakeScroll(type("S", (), {"tabs": None})())
    screen = RecordsScreen(object(), mw)
    screen.refresh()
    assert mw.calls == ["stats"]


def test_fix2_redirect_without_registered_stats():
    # Adversarial: stats screen not registered -> must not raise.
    mw = FakeMainWindow()
    screen = RecordsScreen(object(), mw)
    screen._redirect()  # should swallow the failure
    assert mw.calls == ["stats"]


# ---------------------------------------------------------------- FIX 3 ---

def test_fix3_set_view_loads_real_shots():
    store = FakeStore()
    store.add({"game_id": "G123", "home": "Bruins", "away": "Leafs",
               "shots": _real_shots()})
    game = type("G", (), {"shot_chart_store": store,
                          "game_manager": None})()
    screen = ShotChartViewerScreen(game, FakeMainWindow())
    screen.set_view(game_id="G123")
    assert len(screen._shots) == 4
    assert "Bruins" in screen._chart_title and "Leafs" in screen._chart_title
    assert screen._count_label.text() == "4 shots, 1 goals"
    assert len(screen._rink._shots) == 4


def test_fix3_set_view_unknown_game_empty_state():
    # Adversarial: unknown game id -> empty state, no crash.
    store = FakeStore()
    game = type("G", (), {"shot_chart_store": store,
                          "game_manager": None})()
    screen = ShotChartViewerScreen(game, FakeMainWindow())
    screen.set_view(game_id="NOPE")
    assert screen._shots == []
    assert "0 shots, 0 goals" in screen._count_label.text()
    assert len(screen._rink._shots) == 0


def test_fix3_rink_renders_each_shot():
    # paintEvent must draw a marker per shot without raising.
    rink = RinkWidget()
    rink.set_shots(_real_shots())

    painters = []

    class Rec(_StubPainter):
        def __init__(self, w=None):
            super().__init__(w)
            painters.append(self)

    old = scv_mod.QPainter
    scv_mod.QPainter = Rec
    try:
        rink.paintEvent(None)
    finally:
        scv_mod.QPainter = old
    p = painters[0]
    kinds = [op[0] for op in p.ops]
    assert "line" in kinds, "goal X (lines) missing"
    assert "ellipse" in kinds, "save/miss circles missing"
    assert "polygon" in kinds, "block triangle missing"
    assert ("end",) in p.ops


def test_fix3_stats_xg_has_shot_chart_button():
    # stats.py xG tab must navigate to shot_chart_viewer with game context.
    src = _src("native_ui/screens/stats.py")
    assert "shot_chart_viewer" in src, \
        "stats.py must reference the shot_chart_viewer screen"
    tree = ast.parse(src)
    methods = [n.name for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert any("shot_chart" in m for m in methods), \
        "stats.py needs a shot-chart navigation handler"


def test_fix3_xg_handler_navigates_with_game_id():
    mw = FakeMainWindow()
    viewer = type("V", (), {})()
    viewer.set_view_calls = []
    viewer.set_view = lambda **kw: viewer.set_view_calls.append(kw)
    mw._screens["shot_chart_viewer"] = FakeScroll(viewer)
    game = type("G", (), {})()
    stats = stats_mod.StatsScreen.__new__(stats_mod.StatsScreen)
    stats.game = game
    stats.main_window = mw
    handler = getattr(stats, "_open_shot_chart", None)
    assert handler is not None, "StatsScreen._open_shot_chart missing"
    handler("G123")
    assert mw.calls == ["shot_chart_viewer"], \
        f"expected navigation to shot_chart_viewer, got {mw.calls}"
    assert viewer.set_view_calls == [{"game_id": "G123"}], \
        f"set_view not called with game context: {viewer.set_view_calls}"


def test_fix3_xg_end_to_end_real_store():
    # Integration: stats xG tab with a REAL ShotChartStore -> click
    # "View shot chart" -> viewer navigates, loads real shots, renders.
    from shot_charts import ShotChartStore
    from PySide6.QtWidgets import QPushButton

    store = ShotChartStore()
    store.add({"game_id": "G7", "date": "2026-10-01",
               "home": "Bruins", "away": "Leafs",
               "shots": _real_shots()})

    mw = FakeMainWindow()
    game = type("G", (), {"shot_chart_store": store,
                          "game_manager": None})()
    viewer = ShotChartViewerScreen(game, mw)
    mw._screens["shot_chart_viewer"] = FakeScroll(viewer)

    stats = stats_mod.StatsScreen(game, mw)
    stats._render_xg()

    btns = [w for w in stats._xg_layout.widgets()
            if isinstance(w, QPushButton)
            and "shot chart" in w.text().lower()]
    assert len(btns) == 1, \
        f"expected one shot-chart button, found {len(btns)}"
    btns[0].click()

    assert mw.calls and mw.calls[-1] == "shot_chart_viewer", \
        f"expected navigation to viewer, got {mw.calls}"
    assert len(viewer._shots) == 4, \
        f"viewer should hold 4 real shots, got {len(viewer._shots)}"
    assert viewer._count_label.text() == "4 shots, 1 goals"
    assert len(viewer._rink._shots) == 4


def test_fix1_frenzy_screen_empty_state_no_crash():
    # Adversarial: no frenzy day -> screen shows empty state, no crash.
    screen = faf_mod.FaFrenzyScreen.__new__(faf_mod.FaFrenzyScreen)
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    game = type("G", (), {"current_date": None})()
    mw = FakeMainWindow()
    faf_mod.BaseScreen.__init__(screen, game, mw)
    screen.refresh()
    assert screen._empty.isVisible() is True
    assert screen._cols.isVisible() is False


# ---------------------------------------------------------------- runner ---

_TESTS = [v for k, v in sorted(globals().items())
          if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    failed = 0
    for t in _TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(_TESTS) - failed}/{len(_TESTS)} passed")
    sys.exit(1 if failed else 0)
