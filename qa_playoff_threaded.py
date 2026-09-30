# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: threaded playoff Sim All (no more ~69s UI freeze) + sim_progress.run_threaded.

Run under xvfb:  xvfb-run -a python3 qa_playoff_threaded.py
"""
import sys
import threading
import time
from types import SimpleNamespace, MethodType
from unittest.mock import patch
sys.path.insert(0, ".")

import tkinter as tk
import sim_progress
import playoff_system as ps

PASS, FAIL = [], []


def check(n, c, d=""):
    (PASS if c else FAIL).append(n)
    print(("  ok  " if c else "  FAIL") + f" {n}" + (f" -- {d}" if d and not c else ""))


def pump(root, secs, stop_fn=None):
    """Pump the tk event loop up to `secs`, exiting early when stop_fn()."""
    end = time.time() + secs
    while time.time() < end:
        root.update()
        if stop_fn is not None and stop_fn():
            return True
        time.sleep(0.02)
    return stop_fn() if stop_fn is not None else False


root = tk.Tk()
root.withdraw()
parent = tk.Toplevel(root)
parent.withdraw()

# ---------- 1: run_threaded completes, progress lands on UI thread ----------
done = {}
fractions = []
ui_threads = set()


def worker_ok(cancel_event, progress):
    for i in range(1, 6):
        time.sleep(0.02)
        progress(i / 5.0, f"step {i}")


def on_done_ok(cancelled, error):
    done.update(cancelled=cancelled, error=error)
    ui_threads.add(threading.current_thread() is threading.main_thread())


sim_progress.run_threaded(parent, "Test run", worker_ok, on_done_ok)
pump(root, 5, lambda: "cancelled" in done)
check("run_threaded completes: on_done(False, None)",
      done.get("cancelled") is False and done.get("error") is None, str(done))
check("on_done runs on the UI thread", ui_threads == {True}, str(ui_threads))

# ---------- 2: worker exception surfaces on UI thread ----------
done2 = {}


def worker_boom(cancel_event, progress):
    progress(0.1, "about to fail")
    raise RuntimeError("sim exploded")


def on_done_boom(cancelled, error):
    done2.update(cancelled=cancelled, error=error)


sim_progress.run_threaded(parent, "Test boom", worker_boom, on_done_boom)
pump(root, 5, lambda: "cancelled" in done2)
check("worker exception -> on_done(False, RuntimeError)",
      done2.get("cancelled") is False
      and isinstance(done2.get("error"), RuntimeError), str(done2))

# ---------- 3: cancel is honored; worker sees the event ----------
done3 = {}
saw_cancel = {}


def worker_slow(cancel_event, progress):
    for i in range(100):
        if cancel_event.is_set():
            saw_cancel["yes"] = True
            return
        time.sleep(0.03)
        progress(i / 100.0)


def on_done_cancel(cancelled, error):
    done3.update(cancelled=cancelled, error=error)


dlg = sim_progress.run_threaded(parent, "Test cancel", worker_slow, on_done_cancel)
# let it start, then cancel from the UI thread like the Cancel button does
pump(root, 0.3)
dlg._on_cancel()
check("cancel button sets the event", dlg.was_cancelled())
pump(root, 5, lambda: "cancelled" in done3)
check("cancelled run -> on_done(True, None)",
      done3.get("cancelled") is True and done3.get("error") is None, str(done3))
check("worker observed the cancel event", saw_cancel.get("yes") is True)

# ---------- 4: UI stays responsive mid-sim ----------
responsive = {}
done4 = {}


def worker_blocky(cancel_event, progress):
    time.sleep(0.6)  # one long game sim on the worker
    progress(1.0, "done")


def on_done_resp(cancelled, error):
    done4["done"] = True
    responsive["flag_seen"] = responsive.get("flag") is True


sim_progress.run_threaded(parent, "Test responsive", worker_blocky, on_done_resp)
root.after(150, lambda: responsive.update(flag=True))  # UI-thread timer mid-sim
pump(root, 5, lambda: "done" in done4)
check("main-loop timers fire during the sim (no freeze)",
      responsive.get("flag_seen") is True, str(responsive))


# ---------- stub bracket for the playoff wiring tests ----------
class StubSeries:
    def __init__(self):
        self.is_complete = False


class StubBracket:
    def __init__(self):
        # keyed by the REAL round order: only the first round has a series
        self.playoff_series = {r: ([StubSeries()] if i == 0 else [])
                               for i, r in enumerate(ps.PlayoffBracket.ROUND_ORDER)}
        self.current_round = None
        self.stanley_cup_champion = None
        self.games = 0

    def simulate_playoff_game(self, series):
        assert threading.current_thread() is not threading.main_thread, \
            "sim ran on the UI thread!"
        time.sleep(0.02)
        self.games += 1
        series.is_complete = True

    def advance_to_next_round(self, round_name):
        self.stanley_cup_champion = SimpleNamespace(team_name="Test Champs")

    def get_playoff_status(self):
        return {"stanley_cup_champion": self.stanley_cup_champion,
                "current_round": "round1",
                "completed_series": 1, "total_series": 1}


def make_view(bulk):
    """A real tk widget carrying PlayoffView's sim-all methods bound to it,
    with a stub bracket. Bracket rendering is stubbed (orthogonal)."""
    view = tk.Frame(parent)
    view.app = SimpleNamespace(_bulk_simming=bulk, save_manager=None,
                               FONT_FAMILY="Segoe UI")
    view.playoff_bracket = StubBracket()
    view._simulate_all_playoffs = MethodType(
        ps.PlayoffView._simulate_all_playoffs, view)
    view._finish_all_playoffs = MethodType(
        ps.PlayoffView._finish_all_playoffs, view)
    # Bracket rendering is orthogonal (needs full series objects); the
    # wiring under test is the sim loop + finish sequence.
    view._display_bracket = lambda: None
    view._update_status_display = lambda: None
    return view


shown = []


class FakeMB:
    def showwarning(self, *a, **k):
        shown.append(("warning", a))
    def showinfo(self, *a, **k):
        shown.append(("info", a))
    def showerror(self, *a, **k):
        shown.append(("error", a))
    def askyesno(self, *a, **k):
        return True


# ---------- 5: headless/bulk path stays synchronous ----------
with patch.object(ps, "messagebox", FakeMB()), \
     patch.object(sim_progress, "create_fallback_save", return_value=None):
    shown.clear()
    v = make_view(bulk=True)
    t0 = time.time()
    v._simulate_all_playoffs()
    elapsed = time.time() - t0
    check("headless path completes synchronously",
          v.playoff_bracket.stanley_cup_champion is not None
          and v.playoff_bracket.games == 1, str(elapsed))
    check("headless path shows champion popup",
          any(k == "info" and "Complete" in str(a) for k, a in shown), str(shown))

# ---------- 6: interactive path threads, then finishes on UI thread ----------
with patch.object(ps, "messagebox", FakeMB()), \
     patch.object(sim_progress, "confirm_heavy_sim", return_value=True), \
     patch.object(sim_progress, "create_fallback_save", return_value=None):
    shown.clear()
    v = make_view(bulk=False)
    v._simulate_all_playoffs()  # returns immediately; worker runs behind dialog
    finished = pump(root, 8,
                    lambda: v.playoff_bracket.stanley_cup_champion is not None
                    and any(k == "info" and "Complete" in str(a) for k, a in shown))
    check("threaded Sim All completes + champion popup on UI thread",
          finished and v.playoff_bracket.games == 1, f"games={v.playoff_bracket.games}")

# ---------- 7: sync dialog still works (non-threaded callers unaffected) ----------
d = sim_progress.SimProgressDialog(parent, title="sync check")
try:
    d.update(0.5, "half")
    check("sync SimProgressDialog.update pumps without error", True)
finally:
    d.close()
check("sync dialog closes cleanly", d._closed is True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
