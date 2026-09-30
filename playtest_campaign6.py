#!/usr/bin/env python3
"""playtest_campaign6.py -- 6-season playtest campaigns (2026-09-29 round).

Usage: PLAYTEST_USER_TEAM="Washington Capitals" python3 playtest_campaign6.py A
       PLAYTEST_USER_TEAM="Colorado Avalanche"  python3 playtest_campaign6.py B

Writes per-season JSON + story logs to ~/workspace/playtest-6season/campaign_{A,B}/
Adapted from the 7-season playtest_campaign.py:
  - 6 seasons, user team from env (no Toronto hardcode)
  - trade-deadline trigger fires on the DERIVED deadline date
    (trade_deadline_date: last RS game - 40d), not the old month==3 check
  - per-season deadline instrumentation (derived date, freeze-gate probe)
  - awards extended: Norris/Selke via awards_race, top-5 goals/assists
  - ottawa_watch: per-season Ottawa snapshot for the contention audit
"""
import sys, os, json, traceback
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

USER_TEAM = os.environ.get("PLAYTEST_USER_TEAM", "Washington Capitals")

from playtest_driver import (StoryLog, nhl_teams, get_team, ovr)
import playtest_driver as _pd
import playtest_mid as _pm
import playtest_offseason as _po
import playtest_fantasy as _pf
import playtest_season as _pse

# de-Toronto the harness modules (they read the module global at call time).
# NOTE: playtest_season binds USER_TEAM_NAME via `from playtest_driver import`
# at its own import time, so it must be patched explicitly too — otherwise
# SeasonDriver.user silently resolves to Toronto for the whole campaign.
for _m in (_pd, _pm, _po, _pf, _pse):
    try:
        _m.USER_TEAM_NAME = USER_TEAM
    except Exception:
        pass
assert _pse.USER_TEAM_NAME == USER_TEAM, "de-Toronto routing failed"

from playtest_season import SeasonDriver
import playtest_mid      # noqa: F401 (monkey-patches)
import playtest_offseason  # noqa: F401 (monkey-patches)
import playtest_systems as psys
from database_generator import generate_database, NHL_TEAMS, NHL_TEAM_INFO

BASE = os.path.expanduser("~/workspace/playtest-6season")

STRATEGIES_A = {1: "win-now", 2: "win-now", 3: "retool", 4: "win-now",
                5: "retool", 6: "all-in"}
STRATEGIES_B = {1: "win-now", 2: "retool", 3: "win-now", 4: "win-now",
                5: "retool", 6: "all-in"}

# chain the systems monthly probes into the driver's monthly hooks,
# and move the trade-deadline trigger onto the DERIVED deadline date.
_orig_monthly = SeasonDriver._monthly_hooks


def _derived_dl(lg):
    try:
        from trade_deadline_manager import trade_deadline_date as _tdd
        return _tdd(lg)
    except Exception:
        return None


def _monthly_hooks_plus(self, month, ugp):
    # suppress the old hardcoded month==3 trigger; we fire on the derived date
    self._deadline_done = True
    _orig_monthly(self, month, ugp)
    try:
        psys.monthly_systems(self, month)
    except Exception as e:
        self.story.bug(self.n, "systems monthly",
                       f"{e}\n{traceback.format_exc()[-300:]}", False,
                       "playtest_systems.py")
    # derived-deadline trigger: monthly ticks only land on month
    # boundaries, so fire at the first tick of the deadline's month.
    # Waiting for a tick on/after the deadline DAY itself lands on the
    # April tick -- after the trade freeze has engaged -- and every
    # deadline deal gets vetoed (0 trades in the 2026-09-29 campaigns).
    try:
        if not getattr(self, "_dl6_done", False):
            dl = _derived_dl(self.lg)
            if dl is not None and self.day >= date(dl.year, dl.month, 1):
                self._dl6_done = True
                self.story.add(
                    self.n, self.day, "deadline_trigger",
                    ["trade_deadline_manager"],
                    f"Deadline activity at monthly tick {self.day} "
                    f"(derived deadline {dl.isoformat()})", "")
                self._trade_deadline()
                # freeze-gate probe: deadline day open, day after frozen
                try:
                    import trade_engine as te
                    f_dl, _ = te._trade_freeze_active(dl.isoformat(), self.lg)
                    f_nx, _ = te._trade_freeze_active(
                        (dl + timedelta(days=1)).isoformat(), self.lg)
                    self.story.add(
                        self.n, dl, "deadline_probe", ["trade_engine"],
                        f"Deadline gate probe: day-of open={not f_dl}, "
                        f"day-after frozen={f_nx}",
                        "" if (not f_dl and f_nx) else "GATE MISMATCH")
                    if f_dl or not f_nx:
                        self.story.bug(
                            self.n, "deadline gate",
                            f"freeze gate wrong around derived deadline {dl}: "
                            f"day-of frozen={f_dl}, day-after frozen={f_nx}",
                            False, "trade_engine.py")
                except Exception as e:
                    self.story.bug(self.n, "deadline probe", f"{e}", False,
                                   "trade_engine.py")
    except Exception as e:
        self.story.bug(self.n, "derived deadline trigger", f"{e}", False,
                       "playtest_campaign6.py")


SeasonDriver._monthly_hooks = _monthly_hooks_plus


def _tm_of(lg, p):
    for t in nhl_teams(lg):
        if p in t.roster:
            return t.team_name
    return "?"


def _snapshot_leaders(lg):
    """Regular-season scoring leaders snapshot.

    Must be taken BEFORE _playoffs(): distribute_stats() credits playoff
    points into the same p.stats fields, so a post-playoffs read mixes
    playoff scoring into the "regular-season" leaders.
    """
    skaters = [p for t in nhl_teams(lg) for p in t.roster
               if p.primary_position.name != "GOALIE"]
    leaders = sorted(((p.full_name, _tm_of(lg, p), p.stats.goals,
                       p.stats.assists, p.stats.goals + p.stats.assists)
                      for p in skaters if p.stats.games_played > 0),
                     key=lambda r: r[4], reverse=True)
    return (leaders[:10],
            sorted(leaders, key=lambda r: r[2], reverse=True)[:5],
            sorted(leaders, key=lambda r: r[3], reverse=True)[:5])


def season_summary(lg, user, champ, rs_leaders=None):
    st = lg.standings[user.team_name]
    standings = sorted(
        ((t.team_name, lg.standings[t.team_name]["W"],
          lg.standings[t.team_name]["L"], lg.standings[t.team_name]["OTL"],
          lg.standings[t.team_name]["Points"]) for t in nhl_teams(lg)),
        key=lambda r: r[4], reverse=True)
    skaters = [p for t in nhl_teams(lg) for p in t.roster
               if p.primary_position.name != "GOALIE"]
    if rs_leaders is not None:
        leaders10, goals5, assists5 = rs_leaders
    else:
        leaders = sorted(((p.full_name, _tm_of(lg, p), p.stats.goals,
                           p.stats.assists, p.stats.goals + p.stats.assists)
                          for p in skaters if p.stats.games_played > 0),
                         key=lambda r: r[4], reverse=True)
        leaders10 = leaders[:10]
        goals5 = sorted(leaders, key=lambda r: r[2], reverse=True)[:5]
        assists5 = sorted(leaders, key=lambda r: r[3], reverse=True)[:5]
    tor = sorted(((p.full_name, p.stats.goals, p.stats.assists,
                   p.stats.goals + p.stats.assists)
                  for p in user.roster
                  if p.primary_position.name != "GOALIE"),
                 key=lambda r: r[3], reverse=True)
    # awards by the game's own logic
    norris = selke = None
    try:
        import awards_race as ar
        nr = ar.norris_race(skaters)
        if nr:
            w = nr[0]["player"]
            norris = (w.full_name, _tm_of(lg, w), nr[0]["points"])
        sr = ar.selke_race(skaters)
        if sr:
            w = sr[0]["player"]
            selke = (w.full_name, _tm_of(lg, w), sr[0]["points"])
    except Exception:
        pass
    # ottawa watch: contention audit snapshot
    ottawa = None
    try:
        ott = get_team(lg, "Ottawa Senators")
        ost = lg.standings["Ottawa Senators"]
        orank = next(i for i, r in enumerate(standings, 1)
                     if r[0] == "Ottawa Senators")
        topsk = sorted(
            (p for p in ott.roster if p.primary_position.name != "GOALIE"),
            key=lambda p: ovr(p), reverse=True)[:6]
        topg = sorted(
            (p for p in ott.roster if p.primary_position.name == "GOALIE"),
            key=lambda p: ovr(p), reverse=True)[:2]
        ottawa = {
            "record": f"{ost['W']}-{ost['L']}-{ost['OTL']}",
            "points": ost["Points"], "rank": orank,
            "top_skaters": [(p.full_name, ovr(p), p.stats.goals,
                             p.stats.assists) for p in topsk],
            "top_goalies": [(g.full_name, ovr(g)) for g in topg],
            "cap_space": getattr(ott, "cap_space", None),
            "roster_size": len(ott.roster),
        }
    except Exception:
        pass
    return {
        "user_record": f"{st['W']}-{st['L']}-{st['OTL']}",
        "user_points": st["Points"],
        "league_rank": next(i for i, r in enumerate(standings, 1)
                            if r[0] == user.team_name),
        "champion": champ.team_name if champ is not None else None,
        "standings_top10": standings[:10],
        "scoring_top10": leaders10,
        "goals_top5": goals5,
        "assists_top5": assists5,
        "norris": norris,
        "selke": selke,
        "user_scoring": tor[:12],
        "ottawa_watch": ottawa,
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
        stub2 = SimpleNamespace(league=None, current_date=None,
                                        user_team=None)
        ok_load = GameSaveManager(stub2).load_game(path)
        lg2 = stub2.league
        ok = bool(ok_save and ok_load and lg2 is not None
                  and len([t for t in lg2.teams
                           if getattr(t, "league_name", "") ==
                           "National Hockey League"]) == 32)
        detail = f"save={ok_save} load={ok_load}"
        if ok and continue_from:
            user2 = get_team(lg2, USER_TEAM)
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


def play_season(tag, cdir, n, lg, user, strategies, story):
    """Run one season; returns (lg, user) possibly replaced by a loaded game."""
    from playtest_season import SeasonDriver  # noqa (already imported)
    strategy = strategies[n]
    print(f"\n===== CAMPAIGN {tag} SEASON {n} ({strategy}) "
          f"year={lg.season_year} =====", flush=True)
    drv = SeasonDriver(lg, n, strategy, story)
    try:
        drv.preseason()
        psys.preseason_systems(drv)
        lg.generate_schedule(lg.season_year)
        # log the derived trade deadline for this season
        dl = _derived_dl(lg)
        if dl is not None:
            story.add(n, dl, "deadline_derived", ["trade_deadline_manager"],
                      f"Derived trade deadline: {dl.isoformat()} "
                      f"(40d before last RS game)", "")
        drv.regular_season()
        drv._awards()
        # snapshot regular-season leaders BEFORE the playoffs: the harness
        # credits playoff points into the same p.stats fields
        rs_leaders = _snapshot_leaders(lg)
        champ = drv._playoffs()
        drv._champ = champ
        summ = season_summary(lg, user, champ, rs_leaders)
        summ["trades"] = drv.trades_made
        summ["strategy"] = strategy
        summ["year"] = lg.season_year
        summ["user_team"] = USER_TEAM
        summ["derived_deadline"] = dl.isoformat() if dl else None
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
    return lg, user


def write_campaign_md(tag, cdir, seasons, story, fantasy):
    with open(os.path.join(cdir, "CAMPAIGN.md"), "w") as f:
        f.write(f"# Campaign {tag} ({'fantasy-draft' if fantasy else 'standard'} league)\n\n")
        f.write(f"User team: {USER_TEAM}\n\n")
        for n in range(1, seasons + 1):
            p = os.path.join(cdir, f"season{n}.json")
            if not os.path.exists(p):
                continue
            d = json.load(open(p))
            sm = d["summary"]
            f.write(f"## Season {n} ({sm['year']}-{sm['year']+1}, {sm['strategy']})\n")
            f.write(f"{USER_TEAM}: {sm['user_record']} ({sm['user_points']} pts, "
                    f"rank {sm['league_rank']}/32). Champion: {sm['champion']}\n")
            f.write(f"Derived deadline: {sm.get('derived_deadline')}\n")
            f.write(f"Trades: {sm['trades']}\n\n")
        f.write(f"## Bugs ({len(story.bugs)})\n")
        for b in story.bugs:
            f.write(f"- S{b['season']} [{b['where']}] {b['what'][:160]} "
                    f"(fixed={b['fixed']}) {b.get('file_line','')}\n")


def _setup_league(tag, cdir, story):
    """Build the league + user team for a fresh campaign."""
    fantasy = (tag == "A")
    if fantasy:
        import playtest_fantasy as pf
        print(f"Campaign {tag}: running fantasy draft "
              f"(user team: {USER_TEAM})...", flush=True)
        d = pf.run_fantasy_draft(seed=20260929)
        lg, user = d["lg"], d["user"]
        rep = d["report"]
        with open(os.path.join(cdir, "fantasy_draft_audit.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        story.add(0, "2026-09-01", "fantasy_draft", ["fantasy_draft"],
                  f"Fantasy draft complete: audit "
                  f"{'PASSED' if rep['ok'] else 'FAILED'} "
                  f"({len(rep['issues'])} issues)",
                  f"{USER_TEAM} roster: {len(user.roster)} players, "
                  f"avg ovr {sum(ovr(p) for p in user.roster)/max(len(user.roster),1):.1f}")
        for team, what, detail in rep["issues"]:
            story.bug(0, "fantasy draft audit", f"[{team}] {what} {detail}",
                      False, "fantasy_draft.py")
    else:
        print(f"Campaign {tag}: generating standard database "
              f"(user team: {USER_TEAM})...", flush=True)
        lg = generate_database("Small")
        lg.initialize_standings()
        lg.initialize_all_draft_picks()
        user = get_team(lg, USER_TEAM)

    # seed rivalries for the user team: two same-division opponents
    try:
        from reputation_system import declare_rivalry
        div = NHL_TEAM_INFO[USER_TEAM]["division"]
        rivals = [t for t in NHL_TEAMS
                  if NHL_TEAM_INFO[t]["division"] == div and t != USER_TEAM][:2]
        for rname in rivals:
            rteam = get_team(lg, rname)
            if rteam:
                declare_rivalry(lg, user, rteam, declared_by="user")
        story.add(1, "2026-09-20", "rivalry",
                  ["rivalry_engine", "reputation_system"],
                  f"{USER_TEAM} declares {rivals[0]} and {rivals[1]} blood rivals"
                  if len(rivals) == 2 else f"{USER_TEAM} declares a blood rival",
                  "Circle those dates on the calendar.")
    except Exception as e:
        story.bug(1, "rivalry seeding", f"{e}", False, "reputation_system.py")
    print(f"User team: {user.team_name} ({len(user.roster)} players)", flush=True)
    return lg, user


def run_campaign(tag, seasons=6):
    fantasy = (tag == "A")
    cdir = os.path.join(BASE, f"campaign_{tag}")
    os.makedirs(cdir, exist_ok=True)
    strategies = STRATEGIES_A if fantasy else STRATEGIES_B
    story = StoryLog()
    lg, user = _setup_league(tag, cdir, story)
    for n in range(1, seasons + 1):
        lg, user = play_season(tag, cdir, n, lg, user, strategies, story)
    story.dump(os.path.join(cdir, "story_all.json"))
    write_campaign_md(tag, cdir, seasons, story, fantasy)
    print(f"\nDone. Logs in {cdir}")


def resume_campaign(tag, from_season, seasons=6):
    """Resume after a crash: load save_s{from_season-1}.dat, continue."""
    fantasy = (tag == "A")
    cdir = os.path.join(BASE, f"campaign_{tag}")
    strategies = STRATEGIES_A if fantasy else STRATEGIES_B
    story = StoryLog()
    # restore prior story
    sp_all = os.path.join(cdir, "story_all.json")
    if os.path.exists(sp_all):
        try:
            d = json.load(open(sp_all))
            story.events = d.get("events", [])
            story.bugs = d.get("bugs", [])
        except Exception:
            pass
    from save_load_system import GameSaveManager
    from types import SimpleNamespace
    sp = os.path.join(cdir, f"save_s{from_season - 1}.dat")
    stub = SimpleNamespace(league=None, current_date=None, user_team=None)
    if not GameSaveManager(stub).load_game(sp):
        raise RuntimeError(f"resume failed: could not load {sp}")
    lg = stub.league
    user = get_team(lg, USER_TEAM)
    print(f"Resumed campaign {tag} at season {from_season} "
          f"(year={lg.season_year})", flush=True)
    for n in range(from_season, seasons + 1):
        lg, user = play_season(tag, cdir, n, lg, user, strategies, story)
    story.dump(os.path.join(cdir, "story_all.json"))
    write_campaign_md(tag, cdir, seasons, story, fantasy)
    print(f"\nDone. Logs in {cdir}")


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "A"
    if len(sys.argv) > 2 and sys.argv[2] == "resume":
        resume_campaign(tag, int(sys.argv[3]),
                        int(sys.argv[4]) if len(sys.argv) > 4 else 6)
    else:
        seasons = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        run_campaign(tag, seasons)
