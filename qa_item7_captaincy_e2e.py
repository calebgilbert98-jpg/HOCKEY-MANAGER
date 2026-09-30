"""Item 7 e2e: _require_captaincy_choice blocking path under xvfb.

Drives the REAL modal (grab_set + wait_window): an after() callback picks
valid letters and confirms while _require_captaincy_choice blocks. Then a
second run where the driver picks a goalie as C, verifies the blocker stays
open with an inline error, then picks valid letters.
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(20260929)

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


class StubTeam:
    def __init__(self, name):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.roster = []


def make_team():
    t = StubTeam("Test Club")
    for i in range(14):
        t.roster.append(StubPlayer(f"Skater {i:02d}", PlayerPosition.CENTER,
                                  leadership=50 + i))
    for i in range(2):
        t.roster.append(StubPlayer(f"Goalie {i:02d}", PlayerPosition.GOALIE,
                                  leadership=90))
    return t


root = tk.Tk()
root.geometry("1400x900")
register(root)
root.update()

news = []
team = make_team()
gm = GameManager.__new__(GameManager)
gm._captaincy_choice_pending = False
gm.user_team = team

app = SimpleNamespace(
    BG_COLOR="#0e0e11", FONT_FAMILY="Segoe UI",
    user_team=team, game_manager=gm,
    update_all_views=lambda: None,
    popup_manager=root.popup_manager,
    add_news=news.append,
)
gm.app = app


def letters():
    c = [p.full_name for p in team.roster if p.captaincy == "C"]
    a = sorted(p.full_name for p in team.roster if p.captaincy == "A")
    return c, a


# --- run 1: driver confirms a valid pick while _require blocks ---
import windows


def drive_valid():
    # find the live blocker via the popup manager stack
    mgr = root.popup_manager
    popups = [e.get("popup") for e in mgr._stack]
    win = next((p for p in popups
                if isinstance(p, windows.MandatoryCaptainsWindow)), None)
    assert win is not None, "blocker card never appeared"
    v = win._view
    v.captain_var.set("Skater 13")
    v.alternate1_var.set("Skater 11")
    v.alternate2_var.set("Skater 12")
    v.save_captains()


root.after(600, drive_valid)
ok = gm._require_captaincy_choice(team)
root.update(); root.update_idletasks()
check("blocking require returns True on valid pick", ok is True)
check("pending flag cleared", gm._captaincy_choice_pending is False)
c, a = letters()
check("1C persisted", c == ["Skater 13"], str(c))
check("2A persisted", a == ["Skater 11", "Skater 12"], str(a))
check("captain announcement news story",
      any("Skater 13" in s and "captain" in s for s in news), str(news))

# --- run 2: driver first picks goalie-C (rejected, stays open), then valid ---
team2 = make_team()
gm.user_team = team2
app.user_team = team2
news.clear()
state = {"phase": 0}


def drive_reject_then_valid():
    mgr = root.popup_manager
    popups = [e.get("popup") for e in mgr._stack]
    win = next((p for p in popups
                if isinstance(p, windows.MandatoryCaptainsWindow)), None)
    assert win is not None, "blocker card never appeared (run 2)"
    v = win._view
    if state["phase"] == 0:
        v.captain_var.set("Goalie 00")
        v.alternate1_var.set("Skater 00")
        v.alternate2_var.set("Skater 01")
        v.save_captains()
        state["phase"] = 1
        state["still_open"] = bool(win.winfo_exists())
        state["err"] = v.error_var.get()
        state["win"] = win
        root.after(400, drive_reject_then_valid)
    else:
        v.captain_var.set("Skater 05")
        v.save_captains()


root.after(600, drive_reject_then_valid)
ok2 = gm._require_captaincy_choice(team2)
root.update(); root.update_idletasks()
check("goalie-C rejected: card stayed open", state.get("still_open") is True)
check("goalie-C rejected: inline Rule 6.1 error",
      "goaltender cannot be captain" in state.get("err", ""),
      state.get("err", ""))
check("blocking require returns True after correction", ok2 is True)
c2, a2 = [p.full_name for p in team2.roster if p.captaincy == "C"], \
    sorted(p.full_name for p in team2.roster if p.captaincy == "A")
check("corrected 1C+2A persisted",
      c2 == ["Skater 05"] and a2 == ["Skater 00", "Skater 01"],
      f"{c2} {a2}")

root.destroy()
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
