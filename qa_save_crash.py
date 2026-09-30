# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_save_crash.py -- save-path hardening.

1. setup_autosave binds GameSaveManager to the game manager, not the GUI.
2. A save failure writes the full traceback to saves/save_crash_log.txt
   (stdout is invisible in the built Windows exe).
3. 5-season save torture: real end_of_season + real create_save_data +
   pickle round-trip, zero failures (regression guard for the year-4
   save crash report).
"""
import sys
import os
import pickle
import traceback
from types import SimpleNamespace
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


# 1. autosave binds the game manager -------------------------------------
import main as _main
import inspect
src = inspect.getsource(_main.HockeyManagerGUI.setup_autosave)
check("setup_autosave passes game_manager, not the GUI",
      "GameSaveManager(gm)" in src and "GameSaveManager(self)" not in src,
      "still binds the GUI")

# 2. crash log on save failure -------------------------------------------
from save_load_system import GameSaveManager
gm = SimpleNamespace(league=None, user_team=None, current_date=None)
sls = GameSaveManager(gm)
sls.save_directory = "/tmp/qa_save_crash"
os.makedirs(sls.save_directory, exist_ok=True)
# Force create_save_data to explode.
sls.create_save_data = lambda: (_ for _ in ()).throw(
    RuntimeError("boom-year-4"))
try:
    import save_load_system as _sls_mod
    _sls_mod.messagebox.showerror = lambda *a, **k: None  # headless
except Exception:
    pass
ok = sls.save_game("crash_test.hm")
log = os.path.join(sls.save_directory, "save_crash_log.txt")
check("failed save returns False", ok is False)
check("crash log written", os.path.exists(log))
if os.path.exists(log):
    body = open(log).read()
    check("log has the traceback",
          "RuntimeError: boom-year-4" in body and "Traceback" in body)

# 3. five-season save torture ---------------------------------------------
from database_generator import generate_database
print("  (generating Small database ...)", flush=True)
league = generate_database("Small")
gm2 = SimpleNamespace(
    league=league,
    user_team=next((t for t in league.teams
                    if getattr(t, "team_name", "") == "Toronto Maple Leafs"),
                   league.teams[0]),
    current_date=date(2026, 10, 1),
    game_results=[],
    player_stats_history={},
    team_stats_history={},
    draft_classes={},
    scouting_reports={},
    settings={},
)
sls2 = GameSaveManager(gm2)
sls2.save_directory = "/tmp/qa_save_crash"
torture_fail = 0
for season in range(1, 6):
    try:
        league.end_of_season()
        league.season_year = int(getattr(league, "season_year", 2026)) + 1
        gm2.current_date = date(league.season_year, 10, 1)
        data = sls2.create_save_data()
        blob = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        pickle.loads(blob)
    except Exception:
        torture_fail += 1
        print(f"  season {season} save failed:")
        traceback.print_exc()
check("5 seasons save + load clean", torture_fail == 0,
      f"{torture_fail} failures")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
