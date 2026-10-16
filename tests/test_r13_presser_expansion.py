#!/usr/bin/env python3
"""R13: Presser expansion tests (S-M item).

The 75 postmatch bank questions are {"q", "when"} entries; 11 carry
premise-restrictive `when` gates (losing-streak / playoff-race / trade-
deadline situational premises). Conventions: synthetic SimpleNamespace
fixtures (same shape as the R8* tests); assertions on premises, not
phrasing. A gate that raises excludes the question (fail closed); ungated
questions are always eligible.
"""
import sys
import os
import types
from datetime import date

_REPO = os.environ.get(
    "R13_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import media_engine as me

check_failed = 0


def check(name, cond):
    global check_failed
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check_failed += 1


def mkteam(name, wins=20, losses=20, otl=5, trail=None,
           league_name="National Hockey League", conf="Eastern"):
    t = types.SimpleNamespace(team_name=name, league_name=league_name,
                              conference=conf, wins=wins, losses=losses,
                              ot_losses=otl)
    if trail is not None:
        t.recent_results = list(trail)
    return t


def mkleague(teams):
    return types.SimpleNamespace(teams=list(teams), schedule=[])


def gctx(**kw):
    g = {"won": False, "streak": 0, "days_to_deadline": None,
         "pts_off_cutoff": None, "gp": 0, "in_season": True}
    g.update(kw)
    return g


# -- bank schema -----------------------------------------------------------
banks = [me._STIRRER_QUESTIONS, me._LOYALIST_QUESTIONS, me._NEUTRAL_QUESTIONS]
total = sum(len(b) for b in banks)
gated = [e for b in banks for e in b if e.get("when") is not None]
check("75 bank entries", total == 75)
check(">=6 gated entries", len(gated) >= 6)
check("every entry is {q, when} with str q",
      all(set(e.keys()) == {"q", "when"} and isinstance(e["q"], str)
          for b in banks for e in b))
check("no duplicate question text",
      len({e["q"] for b in banks for e in b}) == total)
check("every gate is callable",
      all(callable(e["when"]) for e in gated))

# -- gate semantics ----------------------------------------------------------
# streak gates: exclude the cases the premise denies
check("home_loss_pattern: loss+streak2 eligible",
      me._g_home_loss_pattern(gctx(won=False, streak=2)))
check("home_loss_pattern: win excluded",
      not me._g_home_loss_pattern(gctx(won=True, streak=5)))
check("home_loss_pattern: streak1 excluded",
      not me._g_home_loss_pattern(gctx(won=False, streak=1)))
check("home_skid: loss+streak3 eligible",
      me._g_home_skid(gctx(won=False, streak=3)))
check("home_skid: streak2 excluded",
      not me._g_home_skid(gctx(won=False, streak=2)))
check("fracture: streak3 eligible",
      me._g_fracture(gctx(streak=3)))
check("fracture: streak2 excluded",
      not me._g_fracture(gctx(streak=2)))
check("losing_stretch: streak4 eligible",
      me._g_losing_stretch(gctx(streak=4)))
check("losing_stretch: streak3 excluded",
      not me._g_losing_stretch(gctx(streak=3)))
check("deep_skid: streak5 eligible",
      me._g_deep_skid(gctx(streak=5)))
check("deep_skid: streak4 excluded",
      not me._g_deep_skid(gctx(streak=4)))

# deadline window: 0..14 inclusive, fail closed outside/unknown
check("deadline: day 0 eligible", me._g_deadline_window(gctx(days_to_deadline=0)))
check("deadline: day 14 eligible",
      me._g_deadline_window(gctx(days_to_deadline=14)))
check("deadline: day 15 excluded",
      not me._g_deadline_window(gctx(days_to_deadline=15)))
check("deadline: past deadline excluded",
      not me._g_deadline_window(gctx(days_to_deadline=-1)))
check("deadline: unknown date excluded",
      not me._g_deadline_window(gctx(days_to_deadline=None)))

# playoff race: late season, within 6 pts of the cut
check("race: 60gp gap+6 eligible",
      me._g_playoff_race(gctx(gp=60, pts_off_cutoff=6)))
check("race: 60gp gap-6 eligible",
      me._g_playoff_race(gctx(gp=60, pts_off_cutoff=-6)))
check("race: gap7 excluded",
      not me._g_playoff_race(gctx(gp=70, pts_off_cutoff=7)))
check("race: 59gp excluded",
      not me._g_playoff_race(gctx(gp=59, pts_off_cutoff=0)))
check("race: unknown gap excluded",
      not me._g_playoff_race(gctx(gp=70, pts_off_cutoff=None)))
check("race: offseason excluded",
      not me._g_playoff_race(gctx(gp=70, pts_off_cutoff=0, in_season=False)))

# gates never raise, even on garbage
for gate in (me._g_home_loss_pattern, me._g_home_skid, me._g_fracture,
             me._g_losing_stretch, me._g_deep_skid, me._g_deadline_window,
             me._g_playoff_race):
    try:
        gate({})
        gate(None)
        ok = True
    except Exception:
        ok = False
    check("gate %s never raises" % gate.__name__, ok)


# -- eligibility filter ------------------------------------------------------
check("ungated always eligible",
      me._presser_question_eligible({"q": "x", "when": None}, gctx()))
check("raising gate excludes (fail closed)",
      not me._presser_question_eligible(
          {"q": "x", "when": lambda g: 1 / 0}, gctx()))
check("non-dict entry handled",
      me._presser_question_eligible({"when": None}, gctx()) is True)

# every bank keeps ungated questions, so filtering can never empty a pool
for name, bank in (("stirrer", me._STIRRER_QUESTIONS),
                   ("loyalist", me._LOYALIST_QUESTIONS),
                   ("neutral", me._NEUTRAL_QUESTIONS)):
    ungated = [e for e in bank if e.get("when") is None]
    check("%s bank has ungated fallback (%d)" % (name, len(ungated)),
          len(ungated) > 0)
    # hostile ctx: nothing readable -> only ungated survive, never zero
    hostile = {"won": False, "streak": 0, "days_to_deadline": None,
               "pts_off_cutoff": None, "gp": 0, "in_season": False}
    elig = [e for e in bank if me._presser_question_eligible(e, hostile)]
    check("%s bank non-empty under hostile ctx" % name, len(elig) > 0)


# -- gate ctx from real-shaped fixtures --------------------------------------
t = mkteam("Sliders", wins=10, losses=30, otl=5,
           trail=["L", "L", "L", "L", "L", "W", "L"])
lg = mkleague([t] + [mkteam("T%d" % i, wins=25, losses=15, otl=5)
                      for i in range(15)])
g = me._presser_gate_ctx(lg, t, won=False, game_date=date(2027, 1, 15))
check("gate ctx reads trailing streak 1 (W snaps)", g["streak"] == 1)
t.recent_results = ["L"] * 6
g = me._presser_gate_ctx(lg, t, won=False, game_date=date(2027, 1, 15))
check("gate ctx reads trailing streak 6", g["streak"] == 6)
check("gate ctx gp", g["gp"] == 45)
check("gate ctx in_season", g["in_season"] is True)
check("gate ctx playoff gap is numeric", isinstance(g["pts_off_cutoff"], int))
check("gate ctx never raises on None league/team/date",
      me._presser_gate_ctx(None, None, False, None) is not None)

# -- tonight_recorded: the two presser paths --------------------------------
# User-game path: tonight already in the trail.
t = mkteam("U", wins=10, losses=10, otl=0, trail=["L", "L", "L"])
g = me._presser_gate_ctx(mkleague([t]), t, won=False,
                         game_date=date(2027, 1, 15), tonight_recorded=True)
check("recorded path: 3 trailing L -> streak 3", g["streak"] == 3)
# Batch path: tonight NOT in the trail yet; a loss extends it by one.
g = me._presser_gate_ctx(mkleague([t]), t, won=False,
                         game_date=date(2027, 1, 15), tonight_recorded=False)
check("batch path: 3 recorded L + tonight's loss -> streak 4",
      g["streak"] == 4)
# A win snaps the skid on EITHER path -- even with a stale losing trail.
t = mkteam("W", wins=10, losses=10, otl=0, trail=["L", "L", "L", "L", "L"])
g = me._presser_gate_ctx(mkleague([t]), t, won=True,
                         game_date=date(2027, 1, 15), tonight_recorded=False)
check("batch path: win tonight -> streak 0 despite stale trail",
      g["streak"] == 0)
g = me._presser_gate_ctx(mkleague([t]), t, won=True,
                         game_date=date(2027, 1, 15), tonight_recorded=True)
check("recorded path: win tonight -> streak 0", g["streak"] == 0)

# -- cross-season / corrupt-trail guards (mirror R8e) -------------------------
# Trail holds last April's skid; the ledger is 0-2 this season.
t = mkteam("X", wins=0, losses=2, otl=0, trail=["L"] * 8)
g = me._presser_gate_ctx(mkleague([t]), t, won=False,
                         game_date=date(2026, 10, 5), tonight_recorded=True)
check("cross-season: streak capped by this season's GP (2)", g["streak"] == 2)
# Corrupt: trail claims 5 straight but the ledger holds 1 loss.
t = mkteam("C", wins=3, losses=1, otl=0, trail=["L"] * 5)
g = me._presser_gate_ctx(mkleague([t]), t, won=False,
                         game_date=date(2027, 1, 15), tonight_recorded=True)
check("corrupt trail: ledger can't hold the skid -> streak 0",
      g["streak"] == 0)

# -- playoff-race elimination --------------------------------------------------
def race_ctx(gap, gp, pts, cutoff, season_len, playoffs=False):
    return {"won": True, "streak": 0, "days_to_deadline": 30,
            "pts_off_cutoff": gap, "pts": pts, "cutoff_pts": cutoff,
            "season_len": season_len, "gp": gp, "in_season": True,
            "playoffs": playoffs}

# 6 back, 2 games left, 82-game season: max +4 < 6 -> eliminated.
check("race: eliminated team excluded",
      not me._g_playoff_race(race_ctx(-6, 80, 90, 96, 82)))
# 6 back, 12 games left: max +24 >= 6 -> still alive.
check("race: alive team eligible",
      me._g_playoff_race(race_ctx(-6, 70, 90, 96, 82)))
# Above the cut can never be "eliminated".
check("race: team above cut eligible",
      me._g_playoff_race(race_ctx(4, 80, 100, 96, 82)))
# Unknown season length: elimination check skipped, gate still works.
check("race: unknown season_len degrades gracefully",
      me._g_playoff_race(race_ctx(-6, 70, 90, 96, None)))
# Playoffs: an 8th seed (gap 0, 82 GP) in an April playoff game is NOT
# "in a playoff race" -- the race is over, they're in.
check("race: excluded during playoff games",
      not me._g_playoff_race(race_ctx(0, 82, 96, 96, 82, playoffs=True)))
# ...but the same state in the regular season is eligible.
check("race: same state in regular season eligible",
      me._g_playoff_race(race_ctx(0, 82, 96, 96, 82, playoffs=False)))

def test_script_checks_all_pass():
    """Aggregate: every module-level check() above recorded zero failures.

    The file's historical script convention runs its checks at import; this
    test makes the result visible to pytest instead of only to the script's
    exit code.
    """
    assert check_failed == 0, f"{check_failed} check(s) failed"


if __name__ == "__main__":
    print("failed:", check_failed)
    sys.exit(1 if check_failed else 0)
