#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""playtest_run.py -- run the 5-season playtest. Usage:
   python3 playtest_run.py [num_seasons]   (default 5)
Writes /tmp/playtest_logs/season{N}.json
"""
import sys, os, json, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playtest_driver import (StoryLog, nhl_teams, get_team, ovr, USER_TEAM_NAME,
                             STRATEGIES, LOG_DIR)
from playtest_season import SeasonDriver
import playtest_mid      # noqa: F401 (monkey-patches)
import playtest_offseason  # noqa: F401 (monkey-patches)
from database_generator import generate_database


def season_summary(lg, user, champ):
    st = lg.standings[user.team_name]
    standings = sorted(
        ((t.team_name, lg.standings[t.team_name]["W"],
          lg.standings[t.team_name]["L"], lg.standings[t.team_name]["OTL"],
          lg.standings[t.team_name]["Points"]) for t in nhl_teams(lg)),
        key=lambda r: r[4], reverse=True)
    leaders = []
    for t in nhl_teams(lg):
        for p in t.roster:
            if p.primary_position.name != "GOALIE" and p.stats.games_played > 0:
                leaders.append((p.full_name, t.team_name,
                                p.stats.goals, p.stats.assists,
                                p.stats.goals + p.stats.assists))
    leaders.sort(key=lambda r: r[4], reverse=True)
    tor = [(p.full_name, p.stats.goals, p.stats.assists,
            p.stats.goals + p.stats.assists)
           for p in user.roster if p.primary_position.name != "GOALIE"]
    tor.sort(key=lambda r: r[3], reverse=True)
    return {
        "user_record": f"{st['W']}-{st['L']}-{st['OTL']}",
        "user_points": st["Points"],
        "league_rank": next(i for i, r in enumerate(standings, 1)
                            if r[0] == user.team_name),
        "champion": champ.team_name if champ is not None else None,
        "standings_top10": standings[:10],
        "scoring_top10": leaders[:10],
        "toronto_scoring": tor[:12],
        "trades": [],
    }


def main():
    n_seasons = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    story = StoryLog()
    print("Generating database...", flush=True)
    lg = generate_database("Small")
    lg.initialize_standings()  # generation renames template teams (main.py:253)
    lg.initialize_all_draft_picks()
    user = get_team(lg, USER_TEAM_NAME)
    # seed league lore: Toronto's blood rivalries so the rivalry engine fires
    try:
        from reputation_system import declare_rivalry
        bos = get_team(lg, "Boston Bruins")
        mtl = [t for t in nhl_teams(lg) if "Canadiens" in t.team_name or "Montreal" in t.team_name]
        if bos:
            declare_rivalry(lg, user, bos, declared_by="user")
        if mtl:
            declare_rivalry(lg, user, mtl[0], declared_by="user")
        story.add(1, "2026-09-20", "rivalry",
                  ["rivalry_engine", "reputation_system"],
                  "Toronto declares Boston and Montreal blood rivals",
                  "Circle those dates on the calendar.")
    except Exception as e:
        story.bug(1, "rivalry seeding", f"{e}", False, "reputation_system.py:2383")
    print(f"User team: {user.team_name} ({len(user.roster)} players)", flush=True)

    for n in range(1, n_seasons + 1):
        strategy = STRATEGIES[n]
        print(f"\n===== SEASON {n} ({strategy}) year={lg.season_year} =====", flush=True)
        drv = SeasonDriver(lg, n, strategy, story)
        try:
            drv.preseason()
            lg.generate_schedule(lg.season_year)
            drv.regular_season()
            drv._awards()
            champ = drv._playoffs()
            drv._champ = champ  # coaching carousel must not fire his coach
            summ = season_summary(lg, user, champ)
            summ["trades"] = drv.trades_made
            summ["strategy"] = strategy
            summ["year"] = lg.season_year
            drv._offseason()
            # save/load round trip every season (headless stub manager)
            try:
                from save_load_system import GameSaveManager
                from types import SimpleNamespace
                stub = SimpleNamespace(league=lg, current_date=drv.day,
                                       user_team=user)
                sm = GameSaveManager(stub)
                sp = os.path.join(LOG_DIR, f"save_s{n}.dat")
                ok_save = sm.save_game(sp)
                stub2 = SimpleNamespace(league=None, current_date=None,
                                        user_team=None)
                sm2 = GameSaveManager(stub2)
                ok_load = sm2.load_game(sp)
                lg2 = stub2.league
                ok = bool(ok_save and ok_load and lg2 is not None
                          and len(nhl_teams(lg2)) == 32)
                story.add(n, "9999", "saveload", ["save_load_system"],
                          f"Save/load round trip: {'OK' if ok else 'FAILED'} "
                          f"(save={ok_save}, load={ok_load})", "")
            except Exception as e:
                story.bug(n, "save/load", f"{e}\n{traceback.format_exc()[-300:]}",
                          False, "save_load_system.py")
            with open(os.path.join(LOG_DIR, f"season{n}.json"), "w") as f:
                json.dump({"summary": summ,
                           "events": [e for e in story.events if e["season"] == n],
                           "bugs": [b for b in story.bugs if b["season"] == n]},
                          f, indent=1, default=str)
            print(f"Season {n}: {summ['user_record']} "
                  f"({summ['user_points']} pts, rank {summ['league_rank']}), "
                  f"champ={summ['champion']}", flush=True)
        except Exception as e:
            story.bug(n, "season driver",
                      f"UNHANDLED: {e}\n{traceback.format_exc()[-800:]}",
                      False, "")
            print(f"SEASON {n} CRASHED: {e}", flush=True)
            traceback.print_exc()

    story.dump(os.path.join(LOG_DIR, "story_all.json"))
    print("\nDone. Logs in", LOG_DIR)


if __name__ == "__main__":
    main()
