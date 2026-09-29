#!/usr/bin/env python3
"""Resume Campaign A from the season-3 save, running seasons 4-7."""
import sys, os, json, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from types import SimpleNamespace

from playtest_driver import (StoryLog, nhl_teams, get_team, ovr, USER_TEAM_NAME)
from playtest_season import SeasonDriver
import playtest_mid
import playtest_offseason
import playtest_systems as psys
from playtest_campaign import season_summary, save_load_roundtrip, STRATEGIES_A

BASE = os.path.expanduser("~/workspace/playtest-7season")
CDIR = os.path.join(BASE, "campaign_A")

_orig_monthly = SeasonDriver._monthly_hooks


def _monthly_hooks_plus(self, month, ugp):
    _orig_monthly(self, month, ugp)
    try:
        psys.monthly_systems(self, month)
    except Exception as e:
        self.story.bug(self.n, "systems monthly",
                       f"{e}\n{traceback.format_exc()[-300:]}", False,
                       "playtest_systems.py")


# only patch once (playtest_campaign already patched it on import)
if SeasonDriver._monthly_hooks is _orig_monthly:
    SeasonDriver._monthly_hooks = _monthly_hooks_plus


def main():
    from save_load_system import GameSaveManager
    stub = SimpleNamespace(league=None, current_date=None, user_team=None)
    ok = GameSaveManager(stub).load_game(os.path.join(CDIR, "save_s3.dat"))
    assert ok and stub.league, "could not load save_s3.dat"
    lg, user = stub.league, get_team(stub.league, USER_TEAM_NAME)
    print(f"Resumed: {user.team_name}, year={lg.season_year}", flush=True)
    story = StoryLog()
    # reload prior story events for continuity
    sp = os.path.join(CDIR, "story_all.json")
    for n in range(4, 8):
        strategy = STRATEGIES_A[n]
        print(f"\n===== CAMPAIGN A SEASON {n} ({strategy}) "
              f"year={lg.season_year} =====", flush=True)
        drv = SeasonDriver(lg, n, strategy, story)
        try:
            drv.preseason()
            psys.preseason_systems(drv)
            lg.generate_schedule(lg.season_year)
            drv.regular_season()
            drv._awards()
            champ = drv._playoffs()
            drv._champ = champ
            summ = season_summary(lg, user, champ)
            summ["trades"] = drv.trades_made
            summ["strategy"] = strategy
            summ["year"] = lg.season_year
            drv._offseason()
            psys.offseason_systems(drv)
            fp = os.path.join(CDIR, f"save_s{n}.dat")
            lg2, user2 = save_load_roundtrip(
                lg, user, drv.day, fp, story, n, continue_from=(n == 4))
            if lg2 is not None:
                lg, user = lg2, user2
                print(f"  [season {n}] continuing from loaded game",
                      flush=True)
            with open(os.path.join(CDIR, f"season{n}.json"), "w") as f:
                json.dump({"summary": summ,
                           "events": [e for e in story.events
                                      if e["season"] == n],
                           "bugs": [b for b in story.bugs
                                    if b["season"] == n]},
                          f, indent=1, default=str)
            print(f"Season {n}: {summ['user_record']} "
                  f"({summ['user_points']} pts, rank {summ['league_rank']}), "
                  f"champ={summ['champion']}", flush=True)
        except Exception:
            print(f"SEASON {n} CRASHED", flush=True)
            traceback.print_exc()
            break
    story.dump(os.path.join(CDIR, "story_resume.json"))
    print("Done")


if __name__ == "__main__":
    main()
