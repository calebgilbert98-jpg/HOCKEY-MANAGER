#!/usr/bin/env python3
"""playtest_campaign.py -- 7-season playtest campaigns.

Usage: python3 playtest_campaign.py A   # fantasy-draft league, authentic GM
       python3 playtest_campaign.py B   # standard league, authentic GM

Writes per-season JSON + story logs to ~/workspace/playtest-7season/campaign_{A,B}/
Extends the proven playtest_run harness: same SeasonDriver season loop, plus
the immersive-systems probes (playtest_systems), per-season save/load with a
mid-campaign continue-from-load, and special-event wiring.
"""
import sys, os, json, traceback, pickle
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playtest_driver import (StoryLog, nhl_teams, get_team, ovr, USER_TEAM_NAME)
from playtest_season import SeasonDriver
import playtest_mid      # noqa: F401 (monkey-patches)
import playtest_offseason  # noqa: F401 (monkey-patches)
import playtest_systems as psys
from database_generator import generate_database

BASE = os.path.expanduser("~/workspace/playtest-7season")

STRATEGIES_A = {1: "win-now", 2: "win-now", 3: "retool", 4: "win-now",
                5: "retool", 6: "win-now", 7: "all-in"}
STRATEGIES_B = {1: "win-now", 2: "retool", 3: "win-now", 4: "win-now",
                5: "retool", 6: "win-now", 7: "all-in"}

# chain the systems monthly probes into the driver's monthly hooks
_orig_monthly = SeasonDriver._monthly_hooks


def _monthly_hooks_plus(self, month, ugp):
    _orig_monthly(self, month, ugp)
    try:
        psys.monthly_systems(self, month)
    except Exception as e:
        self.story.bug(self.n, "systems monthly",
                       f"{e}\n{traceback.format_exc()[-300:]}", False,
                       "playtest_systems.py")


SeasonDriver._monthly_hooks = _monthly_hooks_plus


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


def save_load_roundtrip(lg, user, day, path, story, n, continue_from=False):
    """Save via GameSaveManager, load into a fresh manager, verify."""
    from save_load_system import GameSaveManager
    from types import SimpleNamespace
    try:
        stub = SimpleNamespace(league=lg, current_date=day, user_team=user)
        sm = GameSaveManager(stub)
        ok_save = sm.save_game(path)
        stub2 = SimpleNamespace(league=None, current_date=None, user_team=None)
        ok_load = GameSaveManager(stub2).load_game(path)
        lg2 = stub2.league
        ok = bool(ok_save and ok_load and lg2 is not None
                  and len([t for t in lg2.teams
                           if getattr(t, "league_name", "") ==
                           "National Hockey League"]) == 32)
        detail = f"save={ok_save} load={ok_load}"
        if ok and continue_from:
            # prove continuity: adopt the loaded league for the next season
            user2 = get_team(lg2, USER_TEAM_NAME)
            ok = user2 is not None and len(user2.roster) > 0
            detail += f" continue-ok={ok}"
        story.add(n, "9999", "saveload", ["save_load_system"],
                  f"Save/load round trip: {'OK' if ok else 'FAILED'} ({detail})",
                  "CONTINUED FROM LOADED GAME" if (ok and continue_from) else "")
        return (lg2, user2) if (ok and continue_from) else (None, None)
    except Exception as e:
        story.bug(n, "save/load",
                  f"{e}\n{traceback.format_exc()[-300:]}", False,
                  "save_load_system.py")
        return None, None


def run_campaign(tag, seasons=7):
    fantasy = (tag == "A")
    cdir = os.path.join(BASE, f"campaign_{tag}")
    os.makedirs(cdir, exist_ok=True)
    strategies = STRATEGIES_A if fantasy else STRATEGIES_B
    story = StoryLog()

    if fantasy:
        import playtest_fantasy as pf
        print("Campaign A: running fantasy draft...", flush=True)
        d = pf.run_fantasy_draft(seed=20260929)
        lg, user = d["lg"], d["user"]
        rep = d["report"]
        with open(os.path.join(cdir, "fantasy_draft_audit.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        story.add(0, "2026-09-01", "fantasy_draft", ["fantasy_draft"],
                  f"Fantasy draft complete: audit "
                  f"{'PASSED' if rep['ok'] else 'FAILED'} "
                  f"({len(rep['issues'])} issues)",
                  f"Toronto roster: {len(user.roster)} players, "
                  f"avg ovr {sum(ovr(p) for p in user.roster)/max(len(user.roster),1):.1f}")
        for team, what, detail in rep["issues"]:
            story.bug(0, "fantasy draft audit", f"[{team}] {what} {detail}",
                      False, "fantasy_draft.py")
    else:
        print("Campaign B: generating standard database...", flush=True)
        lg = generate_database("Small")
        lg.initialize_standings()
        lg.initialize_all_draft_picks()
        user = get_team(lg, USER_TEAM_NAME)

    # seed rivalries for Toronto
    try:
        from reputation_system import declare_rivalry
        bos = get_team(lg, "Boston Bruins")
        mtl = [t for t in nhl_teams(lg)
               if "Canadiens" in t.team_name or "Montreal" in t.team_name]
        if bos:
            declare_rivalry(lg, user, bos, declared_by="user")
        if mtl:
            declare_rivalry(lg, user, mtl[0], declared_by="user")
        story.add(1, "2026-09-20", "rivalry",
                  ["rivalry_engine", "reputation_system"],
                  "Toronto declares Boston and Montreal blood rivals", "")
    except Exception as e:
        story.bug(1, "rivalry seeding", f"{e}", False, "reputation_system.py")
    print(f"User team: {user.team_name} ({len(user.roster)} players)", flush=True)

    for n in range(1, seasons + 1):
        strategy = strategies[n]
        print(f"\n===== CAMPAIGN {tag} SEASON {n} ({strategy}) "
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
            # save/load every season; season 4 continues from the loaded game
            sp = os.path.join(cdir, f"save_s{n}.dat")
            lg2, user2 = save_load_roundtrip(
                lg, user, drv.day, sp, story, n, continue_from=(n == 4))
            if lg2 is not None:
                lg, user = lg2, user2
                print(f"  [season {n}] continuing campaign from loaded game",
                      flush=True)
            with open(os.path.join(cdir, f"season{n}.json"), "w") as f:
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

    story.dump(os.path.join(cdir, "story_all.json"))
    # campaign summary markdown
    with open(os.path.join(cdir, "CAMPAIGN.md"), "w") as f:
        f.write(f"# Campaign {tag} ({'fantasy-draft' if fantasy else 'standard'} league)\n\n")
        for n in range(1, seasons + 1):
            p = os.path.join(cdir, f"season{n}.json")
            if not os.path.exists(p):
                continue
            d = json.load(open(p))
            sm = d["summary"]
            f.write(f"## Season {n} ({sm['year']}-{sm['year']+1}, {sm['strategy']})\n")
            f.write(f"Toronto: {sm['user_record']} ({sm['user_points']} pts, "
                    f"rank {sm['league_rank']}/32). Champion: {sm['champion']}\n")
            f.write(f"Trades: {sm['trades']}\n\n")
        f.write(f"## Bugs ({len(story.bugs)})\n")
        for b in story.bugs:
            f.write(f"- S{b['season']} [{b['where']}] {b['what'][:160]} "
                    f"(fixed={b['fixed']}) {b.get('file_line','')}\n")
    print(f"\nDone. Logs in {cdir}")


if __name__ == "__main__":
    tag = sys.argv[1].upper() if len(sys.argv) > 1 else "A"
    assert tag in ("A", "B"), "usage: playtest_campaign.py [A|B]"
    run_campaign(tag)
