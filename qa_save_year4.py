"""qa_save_year4.py -- reproduce the year-4 save crash.

Drives a real League through 4 end_of_season() offseasons and runs the
REAL SaveLoadSystem.create_save_data() + pickle round-trip after each
season. Any serializer/pickle failure prints the full traceback --
that IS the crash signature.
"""
import sys
import os
import pickle
import traceback
from types import SimpleNamespace
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_generator import generate_database
from save_load_system import GameSaveManager as SaveLoadSystem

print("generating Small database ...", flush=True)
league = generate_database("Small")
print(f"league: {len(league.teams)} teams, "
      f"{len(league.get_all_players())} players", flush=True)

# Minimal game_manager the serializers expect.
gm = SimpleNamespace(
    league=league,
    user_team=next(t for t in league.teams
                   if getattr(t, "team_name", "") == "Toronto Maple Leafs"),
    current_date=date(2026, 10, 1),
    game_results=[],
    player_stats_history={},
    team_stats_history={},
    draft_classes={},
    scouting_reports={},
    settings={},
)
if gm.user_team is None:
    gm.user_team = league.teams[0]

sls = SaveLoadSystem(gm)
sls.save_directory = "/tmp/qa_saves"
os.makedirs(sls.save_directory, exist_ok=True)

failures = 0
for season in range(1, 6):
    print(f"\n=== season {season} (year {league.season_year}) ===", flush=True)
    try:
        league.end_of_season()
    except Exception:
        print("end_of_season raised:")
        traceback.print_exc()
        failures += 1
        continue
    # Age the league like the real rollover does.
    try:
        league.season_year = int(getattr(league, "season_year", 2026)) + 1
    except Exception:
        pass
    gm.current_date = date(league.season_year, 10, 1)

    # THE save path: create_save_data + pickle, exactly like save_game.
    try:
        save_data = sls.create_save_data()
    except Exception:
        print("create_save_data raised:")
        traceback.print_exc()
        failures += 1
        continue
    try:
        blob = pickle.dumps(save_data, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"save OK: {len(blob)/1e6:.1f} MB pickled", flush=True)
    except Exception:
        print("pickle.dumps raised:")
        traceback.print_exc()
        failures += 1
        continue
    # And back, like load_game does.
    try:
        pickle.loads(blob)
        print("load OK", flush=True)
    except Exception:
        print("pickle.loads raised:")
        traceback.print_exc()
        failures += 1

print(f"\n{failures} failures across 5 seasons")
sys.exit(1 if failures else 0)
