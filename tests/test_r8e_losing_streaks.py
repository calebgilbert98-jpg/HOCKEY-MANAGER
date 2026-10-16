#!/usr/bin/env python3
"""R8e: losing-streaks bucket tests (S item).

Bucket under test: daily_news._streaks_stories. Conventions: synthetic
SimpleNamespace app/team fixtures (same shape as the R8a/R8b/R8c/R8d
tests); assertions on premises, not phrasing.

The bucket is a presentation layer over team.recent_results -- the
'W'/'L'/'OTL' trail GameManager._record_game_result maintains. Tests assert
the bucket fires for real 5+ skids with the true streak length and the true
W-L-OTL record, and stays silent on short skids, snapped trails, missing
feeds, corrupt ledger/trail mismatches, cross-season trail leaks, the
offseason, and false premises (an OTL is a loss; a 'W' or junk entry snaps
the skid; one story per (season, team, streak length)).
"""
import sys
import os
import types
import random
from datetime import date

_REPO = os.environ.get(
    "R8E_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import daily_news as dn


def mkteam(name, trail, w, l, otl, league_name="National Hockey League"):
    t = types.SimpleNamespace(team_name=name, league_name=league_name,
                              wins=w, losses=l, ot_losses=otl)
    if trail is not None:
        t.recent_results = list(trail)
    return t


def mkapp(teams, season_year=2026):
    league = types.SimpleNamespace(teams=list(teams), season_year=season_year)
    app = types.SimpleNamespace(league=league, _daily_news_recent={})
    return app


def run_bucket(app, day, seed=424242):
    rng = random.Random(seed)
    return dn._streaks_stories(app, day, rng)


DAY = date(2027, 1, 15)  # mid-season


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed += 1
check.failed = 0


# -- streak counting -------------------------------------------------------
t = mkteam("T", ["W", "L", "L", "L", "L", "L"], 3, 5, 0)
check("5 trailing L -> streak 5", dn._streak_current_losing(t) == 5)

t = mkteam("T", ["L", "L", "L", "L", "OTL"], 3, 4, 1)
check("trailing OTL extends the skid", dn._streak_current_losing(t) == 5)

t = mkteam("T", ["L", "L", "L", "L", "L", "W"], 4, 5, 0)
check("trailing W snaps the skid", dn._streak_current_losing(t) == 0)

t = mkteam("T", ["L", "L", "L", "L", "L", "X"], 4, 5, 0)
check("junk entry snaps the skid", dn._streak_current_losing(t) == 0)

t = mkteam("T", None, 4, 5, 0)
check("missing trail -> 0", dn._streak_current_losing(t) == 0)

t = mkteam("T", [], 4, 5, 0)
check("empty trail -> 0", dn._streak_current_losing(t) == 0)

t = mkteam("T", ["l", "otl", "L", "L", "L"], 3, 4, 1)
check("codes are case-insensitive", dn._streak_current_losing(t) == 5)

# -- band ------------------------------------------------------------------
check("band 5..7 is skid", all(dn._streak_band(n) == "skid" for n in (5, 6, 7)))
check("band 8+ is freefall", all(dn._streak_band(n) == "freefall" for n in (8, 9, 30)))

# -- firing / silence ------------------------------------------------------
app = mkapp([mkteam("Skidders", ["L"] * 5, 8, 9, 2)])
stories = run_bucket(app, DAY)
check("5-game skid fires one story", len(stories) == 1)
s = stories[0]
check("story names the team", "Skidders" in s)
check("story states the true streak length", "5" in s)
check("story states the true record", "8-9-2" in s)
check("no Unknown Team/Player", "Unknown" not in s)

app = mkapp([mkteam("Shorties", ["L"] * 4 + ["W"], 8, 4, 0)])
check("4-game skid is silent", run_bucket(app, DAY) == [])

app = mkapp([mkteam("Mixed", ["L"] * 4 + ["OTL"], 8, 4, 1)])
check("4L+1OTL (5-game skid) fires", len(run_bucket(app, DAY)) == 1)

app = mkapp([mkteam("Freefallers", ["L"] * 9, 2, 15, 3)])
stories = run_bucket(app, DAY, seed=7)
check("9-game skid fires", len(stories) == 1)
check("9-game skid uses freefall band",
      any(stories[0] == tpl.format(team="Freefallers", n=9, w=2, l=15, otl=3, gp=20)
          for tpl in dn._FREEFALL_TEMPLATES))

app = mkapp([mkteam("Quiet", ["W", "W", "L", "W"], 10, 4, 0)])
check("no skid -> silent", run_bucket(app, DAY) == [])

app = mkapp([mkteam("NoTrail", None, 2, 12, 0)])
check("missing trail -> silent", run_bucket(app, DAY) == [])

# -- corrupt-state cross-checks --------------------------------------------
# Trail claims 5 straight Ls but the ledger holds 1 loss: impossible.
app = mkapp([mkteam("Ghosts", ["L"] * 5, 10, 1, 0)])
check("ledger can't hold the skid -> silent", run_bucket(app, DAY) == [])

# Cross-season leak: April's 4 Ls leak into October; team is 0-2-0.
app = mkapp([mkteam("Leakers", ["L"] * 4 + ["L", "L"], 0, 2, 0)])
check("cross-season leak capped below threshold -> silent",
      run_bucket(app, DAY) == [])

# Same leak, but the team really did lose every game this season
# (0-5-0 with 3 old L's in the trail: last 5 entries are this season).
app = mkapp([mkteam("Realskid", ["L"] * 3 + ["L"] * 5, 0, 5, 0)])
stories = run_bucket(app, DAY)
check("capped streak fires at true length",
      len(stories) == 1 and "5" in stories[0] and "0-5-0" in stories[0])

# -- one-shot semantics ----------------------------------------------------
app = mkapp([mkteam("Skidders", ["L"] * 5, 8, 9, 2)])
first = run_bucket(app, DAY)
second = run_bucket(app, DAY)
check("same (team, length) does not re-fire", first and second == [])

# Streak growth re-fires with the new number.
t = app.league.teams[0]
t.recent_results.append("L")
t.losses = 10
third = run_bucket(app, DAY)
check("streak growth re-fires", len(third) == 1 and "6" in third[0])

# -- calendar / identity gates ---------------------------------------------
app = mkapp([mkteam("Skidders", ["L"] * 5, 8, 9, 2)])
check("offseason is silent", run_bucket(app, date(2027, 7, 15)) == [])

app = mkapp([mkteam("Skidders", ["L"] * 5, 8, 9, 2)], season_year=0)
check("season_year falls back to calendar year",
      len(run_bucket(app, DAY)) == 1)

ghost = types.SimpleNamespace(recent_results=["L"] * 6, wins=8, losses=9,
                              ot_losses=2)  # no team_name
app = mkapp([ghost])
check("nameless team is silent", run_bucket(app, DAY) == [])

# -- volume / ordering -----------------------------------------------------
teams = [mkteam("Five", ["L"] * 5, 8, 5, 0),
         mkteam("Eight", ["L"] * 8, 4, 8, 1),
         mkteam("Six", ["L"] * 6, 7, 6, 2)]
app = mkapp(teams)
stories = run_bucket(app, DAY)
check("max 2 stories per day", len(stories) == 2)
check("longest skid leads", "Eight" in stories[0] and "8" in stories[0])
check("second-longest is second", "Six" in stories[1])

# Tie on streak length: worse ledger leads.
teams = [mkteam("Mild", ["L"] * 5, 12, 5, 0),
         mkteam("Dire", ["L"] * 5, 3, 14, 1)]
app = mkapp(teams)
stories = run_bucket(app, DAY)
check("worse ledger breaks ties", "Dire" in stories[0])

# Duplicate team names render once, not twice.
app = mkapp([mkteam("Dupes", ["L"] * 6, 5, 6, 0),
             mkteam("Dupes", ["L"] * 7, 4, 7, 0)])
stories = run_bucket(app, DAY)
check("duplicate names dedupe to one story", len(stories) == 1)

# -- registration ----------------------------------------------------------
names = [g[0] for g in dn._GENERATORS]
check("bucket registered in _GENERATORS", "streaks" in names)

def test_script_checks_all_pass():
    """Aggregate: every module-level check() above recorded zero failures.

    The file's historical script convention runs its checks at import; this
    test makes the result visible to pytest instead of only to the script's
    exit code.
    """
    assert check.failed == 0, f"{check.failed} check(s) failed"


if __name__ == "__main__":
    print("FAILED: %d" % check.failed)
    sys.exit(1 if check.failed else 0)
