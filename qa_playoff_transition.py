# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: season -> playoffs transition is seamless.

Verifies PlayoffView auto-generates the real bracket when the regular
season is complete (no manual Generate click), and shows a projection
when it isn't.
"""
import os
import sys
from types import SimpleNamespace
from datetime import date

os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

import tkinter.messagebox as _mb
_mb.showinfo = _mb.showwarning = _mb.showerror = _mb.askyesno = lambda *a, **k: None
try:
    import popup_system as _ps
    _ps.messagebox.showinfo = _ps.messagebox.showwarning = \
        _ps.messagebox.showerror = _ps.messagebox.askyesno = lambda *a, **k: None
except Exception:
    pass

import customtkinter as ctk
from playoff_system import PlayoffBracket, PlayoffView

PASS, FAIL = [], []
def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra else ""))

DIVS = {
    "Atlantic":     [("BOS",112),("TOR",108),("FLA",104),("TBL",100),
                     ("BUF",96),("DET",92),("MTL",80),("OTT",76)],
    "Metropolitan": [("CAR",110),("NYR",106),("PIT",88),("WSH",87),
                     ("NYI",84),("NJD",82),("PHI",80),("CBJ",78)],
    "Central":      [("COL",114),("DAL",109),("WPG",102),("MIN",99),
                     ("NSH",89),("STL",85),("UTA",81),("CHI",77)],
    "Pacific":      [("EDM",111),("VGK",107),("LAK",98),("VAN",95),
                     ("CGY",91),("ANA",87),("SEA",83),("SJS",79)],
}
DIV_CONF = {"Atlantic": "Eastern", "Metropolitan": "Eastern",
            "Central": "Western", "Pacific": "Western"}
teams, standings = [], {}
for div, rows in DIVS.items():
    for name, pts in rows:
        teams.append(SimpleNamespace(
            team_name=name, league_name="National Hockey League",
            conference=DIV_CONF[div], division=div, roster=[],
            goals_for=260, goals_against=230))
        standings[name] = {"Points": pts, "W": pts // 2}

def make_league():
    return SimpleNamespace(teams=teams, standings=standings, season_year=2026,
                           rivalries=[], playoff_bracket=None,
                           schedule=[{"date": date(2027, 4, 12),
                                      "home_team": teams[0],
                                      "away_team": teams[1]}])

def make_app(league, complete):
    return SimpleNamespace(
        league=league, current_date=date(2027, 4, 13),
        _check_season_complete=lambda: complete,
        FONT_FAMILY="Arial", BG_COLOR="#0B0F14", CONTENT_BG="#0B0F14")

# --- season complete: bracket auto-builds, silently, on window open
league = make_league()
app = make_app(league, True)
root = ctk.CTk(); root.geometry("1600x900")
view = PlayoffView(root, app=app)
view.pack(fill="both", expand=True)
root.update_idletasks(); root.update()
b = view.playoff_bracket
check("auto-bracket built on open", b is not None)
check("8 R1 series", len(b.playoff_series["wild_card"]) == 8 if b else False)
check("not a projection", b is not None and b.is_projection is False)
check("registered on league", league.playoff_bracket is b)
check("R1 on the calendar",
      sum(1 for e in league.schedule if isinstance(e, dict)
          and e.get("playoff")) == 56)
root.destroy()

# --- season NOT complete: no auto-bracket (projection tree instead)
league2 = make_league()
app2 = make_app(league2, False)
root2 = ctk.CTk(); root2.geometry("1600x900")
view2 = PlayoffView(root2, app=app2)
view2.pack(fill="both", expand=True)
root2.update_idletasks(); root2.update()
check("no auto-bracket mid-season", view2.playoff_bracket is None)
check("no playoff entries mid-season",
      not any(isinstance(e, dict) and e.get("playoff")
              for e in league2.schedule))
root2.destroy()

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
