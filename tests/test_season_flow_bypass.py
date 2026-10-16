"""Regression tests: FIX-BACK on 580e693 (season_flow.py quick-advance guard).

580e693 added the ``_quick_dlg is not None`` disjunct to the _advance_days
busy guard. Correct on the normal path, but under automation bypass
(PUCK_DYNASTY_NO_MODAL=1, modal.automation_bypass()) run_threaded completes
synchronously: on_done -> _finish_quick_advance already ran inside the
run_threaded call, clearing the run's state (_quick_dlg=None,
_quick_cleaned=True). The unconditional ``self._quick_dlg = dlg``
afterwards re-armed a STALE non-None marker, so every later _advance_days
was refused as "Busy" although nothing was running. (The stale marker also
feeds is_background_sim_running() (48f5b9f) and the main_window Continue
guard (230f661) -- fixing the marker fixes all three.)

Covers:
  T1. bypass double _advance_days: first advance completes synchronously ->
      _quick_dlg must be None afterwards -> second advance proceeds (not
      refused as Busy); is_background_sim_running() stays False.
  T2. normal path (no bypass), X-close abandonment: the guard still refuses
      re-entry while _quick_dlg is set (the original race the 580e693
      disjunct closed); after the watchdog reclaims the run, advancing
      works again (no stuck marker).

Run: QT_QPA_PLATFORM=offscreen python3 tests/test_season_flow_bypass.py
Also pytest-collectable (test_* functions with plain asserts).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import PySide6 as _pyside6  # noqa: E402

if "qtstub" in (_pyside6.__file__ or ""):
    # test_native_team_h imports qtstub's fake PySide6 into this pytest
    # process (its screens also import PySide6 lazily inside methods, so the
    # binding must stay process-global). The two bindings are mutually
    # exclusive and this module needs the real QApplication/QTimer event
    # loop, so it opts out here: run it directly as a script instead.
    import pytest  # noqa: E402

    pytest.skip(
        "real PySide6 required: qtstub shadow active in this pytest process "
        "(imported by test_native_team_h); run directly: "
        "QT_QPA_PLATFORM=offscreen python3 tests/test_season_flow_bypass.py",
        allow_module_level=True,
    )

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

# Singleton-safe: another Qt test module imported earlier in the same pytest
# process may already own the QApplication instance.
app = QApplication.instance() or QApplication([])

from native_ui.screens.season_flow import SeasonFlowScreen  # noqa: E402


# --------------------------------------------------------------------------
# fakes
# --------------------------------------------------------------------------
class FakeMainWindow:
    def show_screen(self, name):
        pass

    def show_blockers(self, blockers):
        pass


class FakeGame:
    def __init__(self):
        self.league = object()
        self.current_date = date(2026, 10, 11)
        self._ui_notify = lambda kind, *a, **k: None
        self.sim_days = 0

    def get_continue_state(self):
        return ("ok", [])

    def simulate_day(self):
        self.sim_days += 1


def make_screen():
    screen = SeasonFlowScreen(FakeGame(), FakeMainWindow())
    assert screen._automation is not None, "engine failed to init"
    return screen


class DialogCapture:
    """Capture QMessageBox statics so tests never block on a modal."""

    def __init__(self):
        self.titles = []

    def __enter__(self):
        self._orig_info = QMessageBox.information
        self._orig_crit = QMessageBox.critical
        cap = self

        def _info(*a, **k):
            cap.titles.append(a[1] if len(a) > 1 else "")
            return QMessageBox.Ok

        def _crit(*a, **k):
            cap.titles.append(a[1] if len(a) > 1 else "")
            return QMessageBox.Ok

        QMessageBox.information = staticmethod(_info)
        QMessageBox.critical = staticmethod(_crit)
        return self

    def __exit__(self, *exc):
        QMessageBox.information = self._orig_info
        QMessageBox.critical = self._orig_crit
        return False


class BypassEnv:
    """Set/unset PUCK_DYNASTY_NO_MODAL for the duration."""

    def __init__(self, enabled):
        self.enabled = enabled
        self._had = "PUCK_DYNASTY_NO_MODAL" in os.environ
        self._old = os.environ.get("PUCK_DYNASTY_NO_MODAL")

    def __enter__(self):
        if self.enabled:
            os.environ["PUCK_DYNASTY_NO_MODAL"] = "1"
        else:
            os.environ.pop("PUCK_DYNASTY_NO_MODAL", None)
        return self

    def __exit__(self, *exc):
        if self._had:
            os.environ["PUCK_DYNASTY_NO_MODAL"] = self._old
        else:
            os.environ.pop("PUCK_DYNASTY_NO_MODAL", None)
        return False


def pump_until(pred, timeout=10.0, label=""):
    deadline = time.time() + timeout
    while not pred() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    assert pred(), f"timed out waiting: {label}"


# --------------------------------------------------------------------------
# T1: automation bypass -- no stale _quick_dlg marker
# --------------------------------------------------------------------------
def test_bypass_double_advance_no_stale_marker():
    """Under PUCK_DYNASTY_NO_MODAL=1 run_threaded completes synchronously.

    First _advance_days must leave _quick_dlg None (the synchronous on_done
    already cleaned up); the second _advance_days must proceed, not be
    refused as Busy. is_background_sim_running() must stay False.
    """
    with BypassEnv(True), DialogCapture() as cap:
        screen = make_screen()
        assert not screen.is_background_sim_running()

        screen._advance_days(3)
        assert screen.game.sim_days == 3, "bypass worker did not run"
        assert screen._quick_dlg is None, (
            "STALE MARKER: _quick_dlg re-armed after synchronous bypass "
            "completion -- every later advance would be refused as Busy")
        assert not screen.is_background_sim_running()

        screen._advance_days(3)
        assert screen.game.sim_days == 6, (
            "second advance did not run -- refused as Busy?")
        assert screen._quick_dlg is None
        assert not screen.is_background_sim_running()

        assert cap.titles == ["Advanced", "Advanced"], (
            f"expected two 'Advanced' dialogs, got {cap.titles}")


# --------------------------------------------------------------------------
# T2: normal path -- X-close abandonment still guarded, then recoverable
# --------------------------------------------------------------------------
def test_normal_path_xclose_still_guarded_then_recovers():
    """Without bypass, while _quick_dlg is set the guard must refuse
    re-entry (the original race the disjunct closed); after an X-close the
    watchdog reclaims the run and advancing works again."""
    with BypassEnv(False), DialogCapture() as cap:
        screen = make_screen()

        screen._advance_days(7)
        dlg = screen._quick_dlg
        assert dlg is not None, (
            "normal path must arm _quick_dlg while the run is in flight")

        # Re-entry while in flight -> refused as Busy, marker not clobbered.
        screen._advance_days(7)
        assert "Busy" in cap.titles, (
            f"re-entry while in flight must be refused as Busy, got "
            f"{cap.titles}")
        assert screen._quick_dlg is dlg, "_quick_dlg must not be clobbered"
        assert screen.is_background_sim_running()

        # Simulate user X-close: closeEvent marks _closed WITHOUT the cancel
        # event, so run_threaded's own poll returns early and on_done never
        # fires -- the _poll_quick_abandon watchdog owns cleanup.
        dlg.close()
        pump_until(lambda: screen._quick_dlg is None,
                   label="watchdog reclaim after X-close")
        assert screen._quick_cleaned is True
        assert screen._sim_in_progress is False
        assert not screen.is_background_sim_running()
        # The worker notify guard must not leak onto the shared game object.
        assert not hasattr(screen.game, "_sf_notify_guard_original"), (
            "notify guard leaked after X-close abandonment")

        # A fresh advance now proceeds (marker not stuck).
        n_busy_before = cap.titles.count("Busy")
        screen._advance_days(7)
        assert cap.titles.count("Busy") == n_busy_before, (
            "advance after watchdog cleanup must not be refused as Busy")
        pump_until(lambda: screen._quick_dlg is None
                   and screen._quick_cleaned,
                   label="normal completion of follow-up advance")
        assert not screen.is_background_sim_running()


# --------------------------------------------------------------------------
# runner (plain script; also pytest-collectable)
# --------------------------------------------------------------------------
_TESTS = [
    test_bypass_double_advance_no_stale_marker,
    test_normal_path_xclose_still_guarded_then_recovers,
]


def main():
    failed = []
    for fn in _TESTS:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 -- report, keep going
            failed.append((fn.__name__, e))
            print(f"FAIL {fn.__name__}: {e}")
        else:
            print(f"PASS {fn.__name__}")
    print(f"\n{len(_TESTS) - len(failed)}/{len(_TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
