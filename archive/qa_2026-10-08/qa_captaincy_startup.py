# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Bug 3: captain picker must not fire mid-construction at startup.

Regression test for the after_idle -> after(250) fix (follows 5259ebd).
Simulates the new-game __init__ sequence: the blocker raise is scheduled,
then update_idletasks() runs (as _create_nav_pill does during the dashboard
build). The picker must NOT appear during construction; it must appear
once the timer fires (mainloop running, __init__ done).
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from popup_system import register
from game_classes import PlayerPosition
from main import GameManager

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


class StubPlayer:
    _id = 0

    def __init__(self, name, pos, leadership=50):
        StubPlayer._id += 1
        self.id = StubPlayer._id
        self.full_name = name
        self.primary_position = pos
        self.leadership = leadership
        self.captaincy = None


def make_team():
    t = SimpleNamespace(team_name="Test Club", city="Test", roster=[],
                        _captaincy_auto_assigned=False)
    for i in range(6):
        t.roster.append(StubPlayer(f"Skater {i:02d}", PlayerPosition.CENTER,
                                  leadership=50 + i))
    for i in range(2):
        t.roster.append(StubPlayer(f"Goalie {i:02d}", PlayerPosition.GOALIE,
                                  leadership=90))
    return t


root = tk.Tk()
root.geometry("1400x900")
register(root)
root.withdraw()

team = make_team()
gm = GameManager.__new__(GameManager)
gm._captaincy_choice_pending = False
gm.user_team = team
gm.league = SimpleNamespace(standings={})
app = SimpleNamespace(
    BG_COLOR="#0e0e11", FONT_FAMILY="Segoe UI",
    user_team=team, game_manager=gm,
    update_all_views=lambda: None,
    popup_manager=root.popup_manager,
    add_news=lambda s: None,
)
gm.app = app


def raise_if_pending():
    # mirrors HockeyManagerGUI._raise_captaincy_blocker_if_pending
    ut = gm.user_team
    if (gm is not None and ut is not None
            and getattr(gm, "_captaincy_choice_pending", False)
            and gm._captaincy_needs_choice(ut)):
        gm._require_captaincy_choice(ut)


# arm the pending flag the way _claim_user_team_captaincy does
gm._captaincy_choice_pending = True

fired = []


def tracked_raise():
    fired.append(True)
    raise_if_pending()


# Fixed scheduling: after(250, ...) -- must survive update_idletasks()
# (the old after_idle fired here, raising the modal mid-construction).
root.after(250, tracked_raise)
root.update_idletasks()  # what _create_nav_pill does during dashboard build
check("picker NOT raised by update_idletasks (mid-construction safe)",
      fired == [])


def drive_and_quit():
    import windows
    mgr = root.popup_manager
    popups = [e.get("popup") for e in mgr._stack]
    win = next((p for p in popups
                if isinstance(p, windows.MandatoryCaptainsWindow)), None)
    check("picker raised after timer fires (post-construction)", win is not None)
    if win is not None:
        v = win._view
        v.captain_var.set("Skater 05")
        v.alternate1_var.set("Skater 03")
        v.alternate2_var.set("Skater 04")
        v.save_captains()
    root.quit()


root.after(1200, drive_and_quit)
root.mainloop()
check("valid pick persisted after timed raise",
      [p.full_name for p in team.roster if p.captaincy == "C"] == ["Skater 05"])
check("pending flag cleared", gm._captaincy_choice_pending is False)

# Source-level regression guard: no after_idle scheduling of the blocker.
src = open("main.py").read()
check("no after_idle(_raise_captaincy_blocker_if_pending) in main.py",
      "after_idle(self._raise_captaincy_blocker_if_pending)" not in src)

root.destroy()
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
