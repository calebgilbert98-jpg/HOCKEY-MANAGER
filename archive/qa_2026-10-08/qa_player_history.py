# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: player season history with mid-season splits.

  1. Mid-season trade produces two stints (OTT + BOS).
  2. League.end_of_season finalizes stints into season_history BEFORE
     the player.stats wipe.
  3. Save/load round-trip preserves season_history (pickle + serializer).
  4. AHL moves never open stints; NHL call-up/send-down open/close them.
  5. Zero-GP stints are skipped at finalization.
  6. History tab + Overview splits build headless without errors.

Headless: run with DISPLAY=:99 (Xvfb). No GUI boot for 1-5; 6 builds the
profile window on a hidden root.
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as g

passed, failed = 0, 0
def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {detail}")

def make_team(name):
    t = g.Team(team_name=name, city=name, division="Atlantic",
               conference="East")
    return t

def make_player():
    return g.Player("Test", "Winger", 25, g.PlayerPosition.CENTER,
                    shooting=80, passing=80)

def set_stats(p, gp, goals, assists):
    p.stats.games_played = gp
    p.stats.goals = goals
    p.stats.assists = assists

# ---------------------------------------------------------------- 1: trade
ott = make_team("Ottawa Senators")
bos = make_team("Boston Bruins")
p = make_player()

ott.add_player(p)                       # opens OTT stint
check("add_player opens stint",
      isinstance(getattr(p, "stint_anchor", None), dict)
      and p.stint_anchor.get("team") == "OTT",
      f"anchor={getattr(p, 'stint_anchor', None)}")

set_stats(p, 41, 12, 18)                # first half in Ottawa
ott.remove_player(p)                    # seals OTT stint
bos.add_player(p)                       # opens BOS stint
check("trade seals old stint, opens new",
      p.stint_anchor.get("team") == "BOS"
      and len(getattr(p, "_stint_pending", [])) == 1,
      f"anchor={p.stint_anchor} pending={getattr(p, '_stint_pending', None)}")

set_stats(p, 79, 27, 38)                # second half in Boston
_pending = p._stint_pending[0]
check("sealed stint has OTT delta stats",
      _pending.get("team") == "OTT" and _pending.get("gp") == 41
      and _pending.get("g") == 12 and _pending.get("a") == 18,
      f"pending={_pending}")

_live = g.current_season_splits(p)
check("current_season_splits shows both stints",
      len(_live) == 2 and _live[0]["team"] == "OTT"
      and _live[1]["team"] == "BOS" and _live[1]["gp"] == 38
      and _live[1]["g"] == 15 and _live[1]["a"] == 20,
      f"splits={_live}")

# ------------------------------------------------- 2: end_of_season
league = g.League(league_name="Test League", season_year=2027)
league.add_team(ott)
league.add_team(bos)
# p is on BOS roster; also add a never-traded player and a healthy scratch
p2 = make_player()
ott.add_player(p2)
set_stats(p2, 82, 30, 40)
p3 = make_player()
bos.add_player(p3)                      # 0 GP healthy scratch
league.free_agents = []
league.draft_prospects = []

league.end_of_season()

check("season_history has two stints for traded player",
      len(p.season_history) == 2,
      f"history={p.season_history}")
_teams = [s["team"] for s in p.season_history]
check("stint teams are OTT then BOS", _teams == ["OTT", "BOS"],
      f"teams={_teams}")
check("stints stamped with season",
      all(s.get("season") == 2027 for s in p.season_history),
      f"history={p.season_history}")
_bos_stint = [s for s in p.season_history if s["team"] == "BOS"][0]
check("BOS stint has second-half deltas",
      _bos_stint["gp"] == 38 and _bos_stint["g"] == 15
      and _bos_stint["a"] == 20,
      f"bos={_bos_stint}")
check("stats wiped after finalize",
      p.stats.games_played == 0 and p.stats.goals == 0)
check("pending drained, fresh anchor opened",
      p._stint_pending == []
      and isinstance(p.stint_anchor, dict)
      and p.stint_anchor.get("team") == "BOS",
      f"anchor={p.stint_anchor} pending={p._stint_pending}")
check("untraded player gets one full-season stint",
      len(p2.season_history) == 1
      and p2.season_history[0]["team"] == "OTT"
      and p2.season_history[0]["gp"] == 82,
      f"p2 history={p2.season_history}")
check("zero-GP scratch gets no stint", p3.season_history == [],
      f"p3 history={p3.season_history}")
# Fresh anchors opened for the new season
check("new-season anchor opened post-rollover",
      isinstance(p.stint_anchor, dict) and p.stint_anchor["team"] == "BOS",
      f"anchor={p.stint_anchor}")

# ------------------------------------------------- 3: save/load
sl = None
try:
    from save_load_system import GameSaveManager
    sl = GameSaveManager(game_manager=None)
    _ser = sl._serialize_player(p)
    check("serializer handles season_history",
          isinstance(_ser.get("season_history"), list)
          and len(_ser["season_history"]) == 2
          and _ser["season_history"][0]["team"] == "OTT",
          f"keys={list(_ser.keys())[:5]}")
except Exception as e:
    check("serializer handles season_history", False, f"exc={e}")

try:
    _blob = pickle.dumps(p)
    _p2 = pickle.loads(_blob)
    check("pickle round-trip preserves history",
          _p2.season_history == p.season_history
          and len(_p2.season_history) == 2)
    check("pickle round-trip preserves anchor",
          isinstance(_p2.stint_anchor, dict)
          and _p2.stint_anchor["team"] == "BOS")
except Exception as e:
    check("pickle round-trip preserves history", False, f"exc={e}")

# ------------------------------------------------- 4: AHL moves
ahl_team = make_team("Providence Bruins")
pa = make_player()
ahl_team.add_player(pa, "ahl")           # AHL assignment: no stint
check("AHL add opens no stint", pa.stint_anchor is None,
      f"anchor={pa.stint_anchor}")
ahl_team.remove_player(pa)              # off AHL roster
ahl_team.add_player(pa, "roster")       # call-up: stint opens
check("call-up opens NHL stint",
      isinstance(pa.stint_anchor, dict)
      and pa.stint_anchor["team"] == "PRO",
      f"anchor={pa.stint_anchor}")
set_stats(pa, 10, 2, 3)
ahl_team.remove_player(pa)              # send-down: stint seals
ahl_team.add_player(pa, "ahl")
check("send-down seals stint, AHL re-add opens none",
      pa.stint_anchor is None and len(pa._stint_pending) == 1
      and pa._stint_pending[0]["gp"] == 10,
      f"anchor={pa.stint_anchor} pending={pa._stint_pending}")

# ------------------------------------------------- 6: UI smoke (headless)
try:
    import tkinter as tk
    from modern_profile import PlayerProfile
    root = tk.Tk()
    root.withdraw()
    prof = PlayerProfile(root, p)        # p has 2-stint history
    check("History tab registered",
          "History" in getattr(prof, "_tab_pages", {}))
    # Build the history page explicitly
    _page = prof._tab_pages["History"]
    check("History page builds", _page is not None)
    # Overview with splits: give p a live two-team split
    pm = make_player()
    ott.add_player(pm)
    set_stats(pm, 20, 5, 5)
    ott.remove_player(pm)
    bos.add_player(pm)
    set_stats(pm, 35, 9, 11)
    prof2 = PlayerProfile(root, pm)
    check("profile with mid-season mover builds", True)
    root.destroy()
except Exception as e:
    check("History tab registered", False, f"exc={e}")
    check("History page builds", False, f"exc={e}")
    check("profile with mid-season mover builds", False, f"exc={e}")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
