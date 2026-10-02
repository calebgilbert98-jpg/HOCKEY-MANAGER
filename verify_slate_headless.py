"""Headless verification: every scheduled game produces a result, even under
error injection. Runs the REAL HockeyManagerGUI._simulate_games_batch
(unbound, with a stub app) over a full generated 84-game schedule while
the lightweight sim randomly explodes -- then asserts all 32 clubs reach
84 GP and the season completes. This is the structural answer to
BUG-003/004/005: games can no longer silently vanish.
"""
import sys
import os
import random
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as _main_mod
from database_generator import generate_database

HockeyManagerGUI = _main_mod.HockeyManagerGUI

FAIL_RATE = 0.10  # 10% of lightweight sims raise -- far worse than reality
rng = random.Random(20261002)

results = {"pass": [], "fail": []}


def check(name, cond, detail=""):
    (results["pass"] if cond else results["fail"]).append(name)
    print(("  PASS " if cond else "  FAIL ") + name +
          (f" -- {detail}" if detail and not cond else ""))


class FakeApp:
    """Minimal app surface for _simulate_games_batch."""

    def __init__(self, fail_rate):
        self.user_team = None
        self._slate_fallbacks = 0
        self._season_integrity_shortfall = None
        self.fail_rate = fail_rate
        self.gp = Counter()
        self.news_log = None
        self.league = None
        self.game_results = []

    def _league_sim_detail(self, league_key):
        return "quick"  # tier 0 == lightweight path

    def _simulate_game_lightweight(self, home_team, away_team,
                                   preseason=False):
        if rng.random() < self.fail_rate:
            raise RuntimeError("injected sim explosion (None-team style)")
        # simple plausible result
        hs = rng.randint(1, 5)
        aws = rng.randint(0, 4)
        went_ot = False
        if hs == aws:
            went_ot = True
            if rng.random() < 0.5:
                hs += 1
            else:
                aws += 1
        winner = home_team if hs > aws else away_team
        loser = away_team if hs > aws else home_team
        return winner, loser, (hs, aws), went_ot

    def _update_standings_fast(self, home_team, away_team, winner, scores,
                               went_to_ot, preseason=False):
        if preseason:
            return
        self.gp[home_team.team_name] += 1
        self.gp[away_team.team_name] += 1

    def _grudge_week_market(self, *a, **k):
        pass

    def _grudge_week_grade(self, *a, **k):
        pass

    def _narrative_postgame(self, *a, **k):
        pass

    def _snapshot_game_toi_fatigue(self, *a, **k):
        pass

    def _deliver_outdoor_pregame(self, *a, **k):
        pass

    def _credit_nhl_games_played(self, *a, **k):
        pass


# bind the real guarantee machinery onto the fake
FakeApp._sim_game_guaranteed = HockeyManagerGUI._sim_game_guaranteed
FakeApp._slate_deterministic_result = \
    HockeyManagerGUI._slate_deterministic_result
FakeApp._log_slate_fallback = HockeyManagerGUI._log_slate_fallback
FakeApp._record_game_result = HockeyManagerGUI._record_game_result
# _record_game_result touches derived indexes only when they alias the
# live list; the fake keeps them detached.
FakeApp._results_index_src = None

for season_no, seed in enumerate((20261002, 20261003), start=1):
    print(f"--- season {season_no} (seed {seed}) ---")
    league = generate_database("Small")
    league.generate_schedule(season_year=2026, rotation_seed=seed)
    games = [e for e in league.schedule
             if isinstance(e, dict) and e.get("league") == "NHL"
             and not e.get("preseason")]
    app = FakeApp(FAIL_RATE)
    # news_log as a plain list, like the real app
    app.news_log = []
    HockeyManagerGUI._simulate_games_batch(app, games)
    check(f"s{season_no}: all 1344 games simulated", len(games) == 1344,
          f"got {len(games)}")
    check(f"s{season_no}: all 32 clubs at 84 GP",
          len(app.gp) == 32 and all(v == 84 for v in app.gp.values()),
          str({t: v for t, v in app.gp.items() if v != 84}))
    check(f"s{season_no}: fallbacks fired (injection worked)",
          app._slate_fallbacks > 0,
          f"fallbacks={app._slate_fallbacks}")
    # every fallback was logged loudly
    check(f"s{season_no}: fallback news-log lines present",
          len(app.news_log) > 0, f"lines={len(app.news_log)}")

print(f"\n{len(results['pass'])} passed, {len(results['fail'])} failed")
sys.exit(1 if results["fail"] else 0)
