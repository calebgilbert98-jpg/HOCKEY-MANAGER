# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA R2 (revised): Player Comparison tool, EHM/FM24-style.

The "Compare with:" dropdown defaults to RECENTLY VIEWED players (most
recent first) plus the user's own club (NHL/AHL/prospects, OVR desc).
Recently-viewed is recorded on player-card open (main.open_player_profile
hook -> player_context_menu.record_recently_viewed), capped at 15, and
persisted on the save.

Run headless:  DISPLAY=:99 python3 qa_ui_repairs/qa_r2_compare.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from datetime import date

from game_classes import Player, PlayerPosition
import player_context_menu as pcm
from player_context_menu import PlayerContextMenu

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


root = tk.Tk()
root.withdraw()


def mk(pid, first, last, pos, age=24):
    p = Player(first_name=first, last_name=last, age=age,
               primary_position=pos)
    p.id = pid
    return p


subject = mk("s1", "Liam", "Lavoie", PlayerPosition.CENTER)
mates = [
    mk("m1", "Aatu", "Raty", PlayerPosition.CENTER),
    mk("m2", "Cole", "Caufield", PlayerPosition.RIGHT_WING),
    mk("m3", "Miro", "Heiskanen", PlayerPosition.LEFT_DEFENSE),
]
prospect = mk("p1", "Ivan", "Demidov", PlayerPosition.RIGHT_WING, age=19)
rv1 = mk("r1", "Auston", "Matthews", PlayerPosition.CENTER)
rv2 = mk("r2", "Connor", "McDavid", PlayerPosition.CENTER)

team = SimpleNamespace(roster=[subject] + mates, ahl_roster=[],
                       prospects=[prospect], team_name="User Club")
league = SimpleNamespace(teams=[team], get_all_players=lambda: (
    team.roster + team.ahl_roster + team.prospects + [rv1, rv2]))
gm = SimpleNamespace(user_team=team, league=league)
app = SimpleNamespace(
    user_team=team, game_manager=gm,
    BG_COLOR="#1E1E1E", HEADER_COLOR="white",
    TEXT_COLOR="white", CONTENT_BG="#2A2A2A", ACCENT_COLOR="#D13438",
)

# Simulate the contracts-tab depth: the menu's parent is a real widget whose
# .parent chain reaches the app only after 3 hops.
host = tk.Frame(root)
host.parent = SimpleNamespace(parent=app)  # 3rd hop -> app
menu = PlayerContextMenu(host)

# --- 1. recently-viewed recording -------------------------------------------
check("no recently-viewed at start",
      list(getattr(gm, "recently_viewed_players", None) or []) == [])
pcm.record_recently_viewed(app, rv1)
pcm.record_recently_viewed(app, rv2)
pcm.record_recently_viewed(app, rv1)  # re-view bumps to front
check("recently-viewed recorded in recency order",
      list(gm.recently_viewed_players) == ["r1", "r2"],
      str(getattr(gm, "recently_viewed_players", None)))
# Cap: 15 entries max.
for i in range(20):
    pcm.record_recently_viewed(app, mk(f"x{i}", "X", f"Y{i}",
                                       PlayerPosition.CENTER))
check("recently-viewed capped at 15",
      len(gm.recently_viewed_players) == pcm.RECENTLY_VIEWED_CAP,
      str(len(gm.recently_viewed_players)))
# Restore the two real recently-viewed for the ordering checks below.
gm.recently_viewed_players = ["r1", "r2"]
resolved = pcm.get_recently_viewed_players(app)
check("recently-viewed resolves to player objects, most-recent first",
      [p.id for p in resolved] == ["r1", "r2"],
      str([p.id for p in resolved]))
check("open_player_profile hook installed in main.py",
      "record_recently_viewed" in open("main.py").read())

# --- 2. compare list: recently-viewed first, then own club -------------------
players = menu._get_all_players(exclude=subject)
ids = [p.id for p in players]
check("compare list non-empty", len(players) >= 5, f"got {len(players)}")
check("recently-viewed lead the list",
      ids[:2] == ["r1", "r2"], str(ids[:5]))
check("subject excluded", "s1" not in ids)
check("own-club players and prospects follow",
      all(x in ids for x in ("m1", "m2", "m3", "p1")), str(ids))
# Own-club tail is OVR-desc sorted.
tail = [p for p in players if p.id not in ("r1", "r2")]
ovrs = [int(p.overall_rating()) for p in tail]
check("own-club section sorted by OVR desc",
      ovrs == sorted(ovrs, reverse=True), str(ovrs))

# --- 3. save persistence round-trip ------------------------------------------
from save_load_system import GameSaveManager as SaveLoadSystem
sls = SaveLoadSystem(gm)
sls._serialize_league = lambda: {}
sls._serialize_schedule = lambda: {}
sls._get_current_settings = lambda: {}
gm.current_date = date(2026, 9, 29)
data = sls.create_save_data()
check("save data carries recently_viewed_players",
      data.get("recently_viewed_players") == ["r1", "r2"],
      str(data.get("recently_viewed_players")))
# Restore onto a fresh manager (old-save path: key missing -> skipped).
gm2 = SimpleNamespace()
sls2 = SaveLoadSystem(gm2)
sls2._restore_league = lambda d: None
sls2._restore_user_team = lambda d: None
sls2._restore_schedule = lambda d: None
sls2._restore_coach_carousel = lambda d: None
sls2._restore_game_state({"version": "99.0",
                          "recently_viewed_players": ["r1", "r2"]})
check("recently-viewed restored on load",
      list(getattr(gm2, "recently_viewed_players", [])) == ["r1", "r2"])
gm3 = SimpleNamespace()
sls3 = SaveLoadSystem(gm3)
sls3._restore_league = lambda d: None
sls3._restore_user_team = lambda d: None
sls3._restore_schedule = lambda d: None
sls3._restore_coach_carousel = lambda d: None
sls3._restore_game_state({"version": "99.0"})
check("old save without the key loads (no crash, no attr)",
      not hasattr(gm3, "recently_viewed_players"))

# --- 4. build the real dialog -------------------------------------------------
menu._create_enhanced_comparison_window(subject)
root.update_idletasks()
popups = [c for c in host.winfo_children() if type(c).__name__ == "InGamePopup"]
check("comparison dialog created", len(popups) == 1, f"found {len(popups)}")
win = popups[0]

combos = walk(win, lambda w: isinstance(w, ttk.Combobox))
check("quick-compare combobox present", len(combos) >= 1, f"found {len(combos)}")
combo = combos[0]
vals = list(combo.cget("values"))
check("dropdown populated with multiple options", len(vals) > 1, f"got {len(vals)}")
check("subject excluded from dropdown", subject.full_name not in vals)
check("recently-viewed lead the dropdown",
      vals[0] == rv1.full_name and vals[1] == rv2.full_name, str(vals[:3]))
check("teammates + prospect listed in dropdown",
      all(m.full_name in vals for m in mates + [prospect]), str(vals))

# --- 5. drive a real comparison ------------------------------------------------
combo.current(0)
picked = combo.get()
check("a selection is possible", bool(picked), "empty selection")
btns = walk(win, lambda w: isinstance(w, ttk.Button) and w.cget("text") == "Compare Players")
check("'Compare Players' button present", len(btns) == 1, f"found {len(btns)}")
btns[0].invoke()
root.update_idletasks()

trees = walk(win, lambda w: isinstance(w, ttk.Treeview))
check("results treeview rendered", len(trees) >= 1, f"found {len(trees)}")
rows = trees[0].get_children() if trees else []
check("results contain attribute rows", len(rows) >= 5, f"got {len(rows)}")
if rows:
    cols = trees[0].cget("columns")
    check("result columns name both players",
          cols[1] == subject.full_name and cols[2] == picked, str(cols))
    first = trees[0].item(rows[0], "values")
    check("first result row is the Overall Rating comparison",
          first[0] == "Overall Rating" and len(first) == 4, str(first))

# Quick Compare tab is first.
nb = walk(win, lambda w: isinstance(w, ttk.Notebook))
check("Quick Compare is the first tab",
      bool(nb) and str(nb[0].tab(0, "text")) == "Quick Compare",
      str([nb[0].tab(i, "text") for i in range(3)] if nb else []))

# --- 6. other tabs render -------------------------------------------------------
texts = walk(win, lambda w: type(w).__name__ == "ScrolledText")
check("analysis/peer text panes present", len(texts) >= 2, f"got {len(texts)}")
blob = "\n".join(t.get("1.0", "end") for t in texts)
check("Detailed Analysis tab renders for the subject",
      "DETAILED PLAYER ANALYSIS" in blob and "Liam Lavoie" in blob)
check("analysis text uses real line breaks (no literal backslash-n)",
      "\n" in blob and "\\n" not in blob)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
root.destroy()
sys.exit(1 if FAIL else 0)
