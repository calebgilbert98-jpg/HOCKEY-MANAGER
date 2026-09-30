# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Playtest-driven QA: BUG-013 (traded-pick ownership at draft time),
BUG-014 (league_name save/load round-trip)."""
import os, sys
os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")
from collections import Counter

# --- BUG-014: league_name round-trip -------------------------------------
from database_generator import generate_database
from game_classes import League
from save_load_system import GameSaveManager

lg = generate_database("Small")
c0 = Counter(getattr(t, "league_name", "?") for t in lg.teams)
assert c0 == {"National Hockey League": 32, "American Hockey League": 30}, c0
print("gen 32/30 OK")

import tkinter.messagebox as _mb
def _no_modal(*a, **k):
    raise RuntimeError("modal blocked in headless QA: " + str(a))
for _fn in ("showerror", "showinfo", "showwarning", "askyesno",
            "askokcancel", "askquestion", "askretrycancel"):
    setattr(_mb, _fn, _no_modal)
del _fn, _no_modal
from datetime import datetime
class FakeGM: pass
gm = FakeGM(); gm.league = lg; gm.current_date = datetime(2026, 11, 1); gm.user_team = None
gm.scout_region_assignments = {}; gm.inbox_messages = []
mgr = GameSaveManager(gm)
assert mgr.save_game("/tmp/leaguename_test.hm"), "save failed"
gm2 = FakeGM(); mgr2 = GameSaveManager(gm2)
assert mgr2.load_game("/tmp/leaguename_test.hm"), "load failed"
c1 = Counter(getattr(t, "league_name", "?") for t in gm2.league.teams)
assert c1 == {"National Hockey League": 32, "American Hockey League": 30}, c1
print("BUG-014 round-trip OK:", dict(c1))

# --- BUG-013: traded pick drafted by current_team holder -----------------
from game_classes import Team
la = League("T", season_year=2027)
la.teams.clear()
a = Team("Alpha", "A", "D1", "C1"); a.league_name = "National Hockey League"
b = Team("Beta", "B", "D1", "C1"); b.league_name = "National Hockey League"
la.teams = [a, b]
la.standings = {"Alpha": {"Points": 60}, "Beta": {"Points": 100}}
la.lottery_results = {}
a.initialize_draft_picks([2027]); b.initialize_draft_picks([2027])
# Beta's 1st, traded to Alpha via the trade-engine model (current_team only)
pk = next(p for p in b.get_picks_for_year(2027) if p.round == 1)
pk.current_team = "Alpha"
order = la.get_draft_order(2027)
owners = {}
for ov, team, _dp in order:
    if _dp is pk:
        owners[ov] = team.team_name
print("traded-pick owners:", owners)
assert all(v == "Alpha" for v in owners.values()), owners
# untraded picks still resolve to their own club
for ov, team, _dp in order:
    if _dp.original_team == "Alpha" and _dp.round == 2:
        assert team.team_name == "Alpha", team.team_name
print("BUG-013 ownership OK")

# lottery _current_owner_name honors current_team
from draft_lottery import _current_owner_name
assert _current_owner_name(la, "Beta", 2027) == "Alpha"
assert _current_owner_name(la, "Alpha", 2027) == "Alpha"
print("lottery owner name OK")
print("ALL PLAYTEST FIX QA PASSED")
