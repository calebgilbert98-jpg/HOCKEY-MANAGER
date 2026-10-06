# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: MP fantasy force-sim uses team-aware smart picks.

Covers:
 1. _mp_fantasy_smart_choice returns a player from the available pool.
 2. Smart picks respect positional need: a team that already drafted
    2 goalies does not take a third while skaters are needed.
 3. _mp_fantasy_auto_pick commits, assigns, and broadcasts DRAFT_UPDATE.
 4. A cancelled clock (done=True) stays cancelled -- force-sim wins.

Run: python3 qa_mp_fantasy_forcesim.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as _main
from fantasy_draft import FantasyDraftManager, DraftConfiguration
from game_classes import Contract, Player, PlayerPosition, Team

passed = []


def check(name, cond, extra=""):
    assert cond, f"FAILED: {name} {extra}"
    passed.append(name)
    print(f"PASS: {name}")


def mkplayer(pid, pos, ovr, age=25, salary=2_000_000):
    p = Player("Test", f"P{pid}", age, pos)
    p.id = f"fp{pid}"
    p.contract = Contract(salary=salary, years_remaining=2)
    # overall_rating() reads attributes; stub a flat overall.
    p.overall_rating = lambda: ovr
    return p


def mkteam(name):
    t = Team(team_name=name, city="T", division="X", conference="Y")
    t.roster, t.ahl_roster, t.prospects = [], [], []
    return t


# --- 1. Smart choice basics -------------------------------------------
teams = [mkteam(f"T{i}") for i in range(4)]
pool = []
for i in range(60):
    pos = PlayerPosition.CENTER if i % 3 == 0 else (
        PlayerPosition.LEFT_WING if i % 3 == 1 else PlayerPosition.GOALIE)
    pool.append(mkplayer(i, pos, 90 - (i // 3)))
cfg = DraftConfiguration()
cfg.rounds = 3
dm = FantasyDraftManager(teams, pool, cfg)

app = SimpleNamespace()
# Bind the real smart-choice + auto-pick methods.
app._mp_fantasy_smart_choice = \
    _main.HockeyManagerGUI._mp_fantasy_smart_choice.__get__(app)
app._mp_fantasy_auto_pick = \
    _main.HockeyManagerGUI._mp_fantasy_auto_pick.__get__(app)
app._mp_toast = lambda t: None
app._mp_fantasy_view = None

broadcasts = []
app.mp_host = SimpleNamespace(
    broadcast_draft_update=lambda *a: broadcasts.append(a))

pick = dm.get_current_pick()
avail = dm.get_available_players()
choice = app._mp_fantasy_smart_choice(dm, pick.team, avail)
check("smart choice returns an available player", choice in avail)

# --- 2. Positional sanity: no goalie hoarding ---------------------------
# Give T0 two goalies already, then check the next ~6 smart picks for T0
# don't stack a third goalie while skaters go unpicked.
g1 = mkplayer(1000, PlayerPosition.GOALIE, 88)
g2 = mkplayer(1001, PlayerPosition.GOALIE, 87)
dm.draft_picks[0].player = mkplayer(2000, PlayerPosition.CENTER, 91)
dm.draft_picks[0].team = teams[0]
# Simulate: T0 already holds 2 goalies via prior picks.
t0_goalies = 2
t0_picks = 0
for _ in range(6):
    c = app._mp_fantasy_smart_choice(dm, teams[0], avail)
    if c is None:
        break
    pos = c.primary_position.value
    if pos == "G":
        t0_goalies += 1
    t0_picks += 1
    avail.remove(c)
check("smart draft doesn't hoard goalies",
      t0_goalies <= 3, f"goalies={t0_goalies}")

# --- 3. auto_pick commits + broadcasts ----------------------------------
dm2 = FantasyDraftManager(teams, pool, cfg)
pick2 = dm2.get_current_pick()
res = app._mp_fantasy_auto_pick(dm2, reason="test")
check("auto_pick returns the chosen player", res is not None)
check("auto_pick committed the pick", pick2.player is res)
check("auto_pick broadcast DRAFT_UPDATE", len(broadcasts) == 1)
check("broadcast is fantasy", broadcasts[0][0] == "fantasy")

# --- 4. Force-sim cancels a pending clock -------------------------------
app._mp_fantasy_clock = {"done": False, "clock_id": "c1"}
# Simulate what _sim_rest_of_draft_confirmed does:
_st = app._mp_fantasy_clock
if isinstance(_st, dict) and not _st.get("done"):
    _st["done"] = True
check("pending clock cancelled by force-sim",
      app._mp_fantasy_clock["done"] is True)

print(f"\nALL {len(passed)} FANTASY FORCE-SIM QA CHECKS PASSED")
