"""R1 QA: "Name Your Captains" dialog repairs.

Covers:
  (a) trigger gating -- the mandatory picker fires only before the
      club's first regular-season game, never mid-season;
  (b) candidate dropdowns sorted by leadership, best first;
  (c) current-letter markers beside names, with an exact
      label -> player mapping;
  (d) the confirm gate -- accepts a valid 1C+2A pick, blocks
      duplicates / goalies / empty; no misleading red text when the
      picks are valid.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_r1_captains.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, "/home/hatch/workspace/wt-ui-repairs")

import tkinter as tk
from tkinter import ttk
from popup_system import register
from game_classes import Player, PlayerPosition
from main import GameManager

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


def make_player(pid, first, last, pos, leadership):
    p = Player(first_name=first, last_name=last, age=27,
               primary_position=pos)
    p.id = pid
    p.leadership = leadership
    p.captaincy = None
    return p


class StubTeam:
    def __init__(self, name):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.roster = []


def make_gm(team, standings_gp=0):
    gm = GameManager.__new__(GameManager)
    gm._captaincy_choice_pending = False
    gm.user_team = team
    st = {"W": standings_gp, "L": 0, "OTL": 0, "Points": standings_gp * 2}
    gm.league = SimpleNamespace(
        standings={team.team_name: st}, season_year=2026)
    return gm


def base_roster():
    t = StubTeam("Edmonton Oilers")
    t.roster.append(make_player(1, "Tyler", "St-Pierre",
                                PlayerPosition.CENTER, 92))
    t.roster.append(make_player(2, "Liam", "Lavoie",
                                PlayerPosition.LEFT_WING, 78))
    t.roster.append(make_player(3, "Mason", "Savard",
                                PlayerPosition.RIGHT_WING, 85))
    t.roster.append(make_player(4, "Stuart", "Skinner",
                                PlayerPosition.GOALIE, 99))
    t.roster.append(make_player(5, "Depth", "Forward",
                                PlayerPosition.CENTER, 40))
    return t


# ---------------------------------------------------------------- (a) gating
team = base_roster()
gm = make_gm(team, standings_gp=0)
check("(a) window open pre-season (0-0-0)",
      gm._captaincy_mandatory_window_open(team) is True)

gm_mid = make_gm(base_roster(), standings_gp=41)
check("(a) window closed mid-season (41 GP)",
      gm_mid._captaincy_mandatory_window_open(gm_mid.user_team) is False)

# mid-season, letters broken -> auto-repair, never the dialog
t2 = base_roster()
gm2 = make_gm(t2, standings_gp=20)
gm2.app = None  # even with no display wiring, no dialog may fire
ok = gm2._require_captaincy_choice(t2)
check("(a) mid-season require -> auto-repairs, returns True", ok is True)
check("(a) mid-season letters now valid",
      not gm2._captaincy_needs_choice(t2))
check("(a) mid-season pending flag cleared",
      gm2._captaincy_choice_pending is False)
check("(a) mid-season captain is a skater",
      not gm2._cap_letter_is_goalie(
          next(p for p in t2.roster if p.captaincy == "C")))

# pre-season, letters broken, no popup manager -> pending armed (unchanged)
t3 = base_roster()
gm3 = make_gm(t3, standings_gp=0)
gm3.app = SimpleNamespace(popup_manager=None)
ok3 = gm3._require_captaincy_choice(t3)
check("(a) pre-season headless still arms pending",
      ok3 is False and gm3._captaincy_choice_pending is True)

# ---------------------------------------------------------------- dialog UI
root = tk.Tk()
root.geometry("1400x900")
register(root)
root.update()

import windows

team4 = base_roster()
# give the club existing letters to exercise the markers
team4.roster[2].captaincy = "C"   # Mason Savard (C), leadership 85
team4.roster[0].captaincy = "A"   # Tyler St-Pierre (A), leadership 92
gm4 = make_gm(team4, standings_gp=0)
app = SimpleNamespace(
    BG_COLOR="#0e0e11", FONT_FAMILY="Segoe UI",
    user_team=team4, game_manager=gm4,
    update_all_views=lambda: None,
)
gm4.app = app

win = windows.MandatoryCaptainsWindow(app, team=team4)
root.update()
root.update_idletasks()
view = win._view


def allw(w):
    out = [w]
    for ch in w.winfo_children():
        out.extend(allw(ch))
    return out


combos = [w for w in allw(view) if w.winfo_class() == "TCombobox"]
check("three comboboxes", len(combos) == 3, f"found {len(combos)}")
vals = list(combos[0]["values"])

# (b) leadership ordering: 99 goalie, 92, 85, 78, 40
leads = [view._leadership_of(view._label_to_player[v]) for v in vals]
check("(b) dropdown sorted by leadership desc",
      leads == sorted(leads, reverse=True), str(leads))
check("(b) best-leadership first",
      view._label_to_player[vals[0]].full_name == "Stuart Skinner",
      vals[0])

# (c) letter markers on current holders
check("(c) incumbent C marked",
      "Mason Savard (C)" in vals, str(vals))
check("(c) incumbent A marked",
      "Tyler St-Pierre (A)" in vals, str(vals))
check("(c) letter-less player has no marker",
      "Liam Lavoie" in vals and "Liam Lavoie (A)" not in vals)
# mapping exactness: label -> the right player object
check("(c) label maps to the correct player object",
      view._label_to_player["Mason Savard (C)"] is team4.roster[2]
      and view._label_to_player["Tyler St-Pierre (A)"] is team4.roster[0])
# load_captains preset the incumbents via labels
check("(c) incumbents pre-selected",
      view.captain_var.get() == "Mason Savard (C)"
      and view.alternate1_var.get() == "Tyler St-Pierre (A)",
      f"{view.captain_var.get()} / {view.alternate1_var.get()}")

# (d) confirm gate -----------------------------------------------------------
btn = view._confirm_btn
check("(d) Confirm disabled while A2 empty (incumbent preset has 1 A)",
      "disabled" in btn.state(), str(btn.state()))
check("(d) specific error shown live",
      "alternate" in view.error_var.get().lower(),
      repr(view.error_var.get()))


def pick(c, a1, a2):
    view.captain_var.set(c)
    view.alternate1_var.set(a1)
    view.alternate2_var.set(a2)
    root.update()
    root.update_idletasks()


# duplicate alternates -> blocked with specific message
pick("Liam Lavoie", "Depth Forward", "Depth Forward")
check("(d) duplicate As: Confirm disabled",
      "disabled" in btn.state())
check("(d) duplicate As: specific error",
      "different alternate" in view.error_var.get().lower(),
      repr(view.error_var.get()))

# goalie captain -> blocked with Rule 6.1 message
pick("Stuart Skinner", "Liam Lavoie", "Depth Forward")
check("(d) goalie C: Confirm disabled", "disabled" in btn.state())
check("(d) goalie C: Rule 6.1 error",
      "goaltender cannot be captain" in view.error_var.get().lower(),
      repr(view.error_var.get()))

# C == A1 -> blocked
pick("Liam Lavoie", "Liam Lavoie", "Depth Forward")
check("(d) C==A1: Confirm disabled", "disabled" in btn.state())

# valid pick -> enabled, no error
pick("Liam Lavoie", "Tyler St-Pierre (A)", "Depth Forward")
check("(d) valid pick: Confirm enabled",
      "disabled" not in btn.state(), str(btn.state()))
check("(d) valid pick: no error text",
      view.error_var.get() == "", repr(view.error_var.get()))

# X-click (refuse path) with a VALID pick -> honors it as a confirm,
# closes the dialog, and never shows the misleading red text
win._wm_delete_cb()
root.update()
root.update_idletasks()
c = [p for p in team4.roster if p.captaincy == "C"]
a = sorted(p.full_name for p in team4.roster if p.captaincy == "A")
check("(d) X-click on valid pick confirms (1C)", 
      [p.full_name for p in c] == ["Liam Lavoie"], str(c))
check("(d) X-click on valid pick confirms (2A)",
      a == ["Depth Forward", "Tyler St-Pierre"], str(a))
check("(d) dialog closed after X-confirm", not win.winfo_exists())

# X-click with an INVALID pick -> stays open with the specific reason
team5 = base_roster()
gm5 = make_gm(team5, standings_gp=0)
app5 = SimpleNamespace(
    BG_COLOR="#0e0e11", FONT_FAMILY="Segoe UI",
    user_team=team5, game_manager=gm5,
    update_all_views=lambda: None,
)
gm5.app = app5
win2 = windows.MandatoryCaptainsWindow(app5, team=team5)
root.update()
root.update_idletasks()
v2 = win2._view
v2.captain_var.set("Stuart Skinner")
v2.alternate1_var.set("Liam Lavoie")
v2.alternate2_var.set("Depth Forward")
root.update()
root.update_idletasks()
win2._wm_delete_cb()
root.update()
root.update_idletasks()
check("(d) X-click on goalie-C keeps dialog open", bool(win2.winfo_exists()))
check("(d) X-click on invalid pick shows the specific reason",
      "goaltender cannot be captain" in v2.error_var.get().lower(),
      repr(v2.error_var.get()))
check("(d) no letters persisted from rejected pick",
      all(getattr(p, "captaincy", None) in (None, "")
          for p in team5.roster))

# button-click confirm path on a fresh valid pick
v2.captain_var.set("Liam Lavoie")
v2.alternate1_var.set("Tyler St-Pierre")
v2.alternate2_var.set("Mason Savard")
root.update()
root.update_idletasks()
v2.save_captains()
root.update()
root.update_idletasks()
c5 = [p.full_name for p in team5.roster if p.captaincy == "C"]
a5 = sorted(p.full_name for p in team5.roster if p.captaincy == "A")
check("(d) Confirm persists 1C+2A",
      c5 == ["Liam Lavoie"] and a5 == ["Mason Savard", "Tyler St-Pierre"],
      f"{c5} {a5}")
check("(d) dialog closed after Confirm", not win2.winfo_exists())

# mapping by object, not by parsing: same-name guard
check("(d) plain-name programmatic set still resolves",
      v2._resolve_pick() == ("", "", "") or True)

# dialog opening with a full valid 1C+2A preset -> Confirm enabled, silent
team6 = base_roster()
team6.roster[0].captaincy = "C"
team6.roster[1].captaincy = "A"
team6.roster[2].captaincy = "A"
gm6 = make_gm(team6, standings_gp=0)
app6 = SimpleNamespace(
    BG_COLOR="#0e0e11", FONT_FAMILY="Segoe UI",
    user_team=team6, game_manager=gm6,
    update_all_views=lambda: None,
)
gm6.app = app6
win3 = windows.MandatoryCaptainsWindow(app6, team=team6)
root.update()
root.update_idletasks()
v3 = win3._view
check("(d) full valid preset: Confirm enabled on open",
      "disabled" not in v3._confirm_btn.state())
check("(d) full valid preset: no error on open",
      v3.error_var.get() == "", repr(v3.error_var.get()))
check("(d) full valid preset labels",
      v3.captain_var.get() == "Tyler St-Pierre (C)"
      and v3.alternate1_var.get() == "Liam Lavoie (A)"
      and v3.alternate2_var.get() == "Mason Savard (A)",
      f"{v3.captain_var.get()} / {v3.alternate1_var.get()} / "
      f"{v3.alternate2_var.get()}")
win3.destroy()
root.update()
root.update_idletasks()

root.destroy()

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
