"""QA R4: Manager Hub -> Profile tab renders its full intended content.

The tab previously showed only the bare reputation/career block; the manager
biography (GM profile), appointment info, current-season record and
preferences now render alongside it.

Run headless:  DISPLAY=:99 python3 qa_ui_repairs/qa_r4_hub_profile.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import customtkinter as ctk

import manager_career as mc
from game_classes import GMProfile
from manager_hub_window import ManagerHubView

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def walk(w, pred, out=None):
    out = [] if out is None else out
    try:
        if pred(w):
            out.append(w)
        children = w.winfo_children()
    except Exception:
        return out
    for c in children:
        walk(c, pred, out)
    return out


def label_texts(frame):
    return [w.cget("text") for w in walk(frame, lambda w: isinstance(w, ttk.Label))]


root = ctk.CTk()
root.withdraw()

# --- full bio ---------------------------------------------------------------
gmp = GMProfile()
gmp.name = "Test GM"
gmp.age = 42
gmp.birthplace = "Toronto, ON"
gmp.nationality = "Canadian"
gmp.management_style = "Analytics-Based"
gmp.education_level = "MBA"
gmp.risk_tolerance = "Aggressive"
gmp.former_player = True
gmp.playing_position = "Center"
gmp.nhl_games_played = 512
gmp.career_points = 388
gmp.coaching_experience = True
gmp.years_coaching = 6

career = mc.CareerState()
career.profile.reputation = 45
career.profile.career_wins = 41
career.profile.seasons_managed = 2
career.career_start_date = "2024-09-01"
career.board.season_wins = 10
career.board.season_losses = 8

team = SimpleNamespace(team_name="Test Club", roster=[], gm_profile=gmp)
app = SimpleNamespace(career=career, user_team=team, BG_COLOR="#1a1a1a",
                      current_date=__import__("datetime").date(2026, 9, 29))

view = ManagerHubView(root, app=app)
view.pack()
root.update_idletasks()

tabs = [view.notebook.tab(i, "text").strip() for i in view.notebook.tabs()]
check("Profile tab exists", "Profile" in tabs, str(tabs))
pidx = tabs.index("Profile")
profile_frame = view.nametowidget(view.notebook.tabs()[pidx])
texts = label_texts(profile_frame)
blob = "\n".join(texts)

check("header shows manager name", any("Test GM" in t for t in texts),
      str(texts[:4]))
check("personal section rendered",
      "Age: 42" in blob and "Birthplace: Toronto, ON" in blob
      and "Nationality: Canadian" in blob and "Education: MBA" in blob)
check("management style section rendered",
      "Analytics-Based" in blob and "Risk tolerance: Aggressive" in blob)
check("playing background rendered",
      "512 NHL games" in blob and "388 career points" in blob)
check("coaching background rendered", "6 years coaching experience" in blob)
check("appointment section rendered",
      "Club: Test Club" in blob and "In charge since: 2024-09-01" in blob)
check("reputation block rendered", "45/100" in blob)
check("career record rendered", "41W" in blob and "Titles won: 0" in blob
      and "Seasons managed: 2" in blob)
check("current-season record rendered", "Current season: 10W - 8L" in blob)

boxes = walk(profile_frame, lambda w: isinstance(w, ttk.Checkbutton))
check("media-prompts checkbox present", len(boxes) == 1, f"found {len(boxes)}")
check("prompts checkbox label intact",
      boxes and "press conferences" in boxes[0].cget("text").lower())
before = career.prompts_enabled
boxes[0].invoke()
check("prompts checkbox still toggles the career flag",
      career.prompts_enabled == (not before))
boxes[0].invoke()  # restore

# --- old-save safety: team without a gm_profile must not break the tab -----
team2 = SimpleNamespace(team_name="Old Club", roster=[])
# NOTE: no gm_profile attribute at all -> exercises the old-save guard.
app2 = SimpleNamespace(career=mc.CareerState(), user_team=team2,
                       BG_COLOR="#1a1a1a",
                       current_date=__import__("datetime").date(2026, 9, 29))
try:
    view2 = ManagerHubView(root, app=app2)
    view2.pack()
    root.update_idletasks()
    tabs2 = [view2.notebook.tab(i, "text").strip() for i in view2.notebook.tabs()]
    pidx2 = tabs2.index("Profile")
    f2 = view2.nametowidget(view2.notebook.tabs()[pidx2])
    blob2 = "\n".join(label_texts(f2))
    check("profile tab renders with no gm_profile (old save)",
          "No manager biography on file." in blob2 and "Reputation" in blob2)
except Exception as e:  # noqa: BLE001
    check("profile tab renders with no gm_profile (old save)", False, repr(e))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
root.destroy()
sys.exit(1 if FAIL else 0)
