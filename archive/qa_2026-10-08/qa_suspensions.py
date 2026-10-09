# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: DoPS suspension (discipline) pipeline.

The suspension kickoff extends the existing controversial-hit DoPS review:
one review decision can now suspend (lineup, team games served) or fine
(the untouched existing path). Everything scales off the ORIGINAL
parameters -- the hitter's dealt personality attributes (discipline /
aggressiveness / controversy), the victim's post-game state, star status
on the native 100-point scale, and repeat-offender history from
controversy_history. No new heat numbers, no scoring changes.
"""
import random
import sys

sys.path.insert(0, ".")

from game_classes import Player, PlayerPosition, Team
import narrative_incidents as ni

PASS, FAIL = 0, 0
FAILURES = []


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL {name}")


def mk_player(first, last, pos, discipline=50, aggressiveness=50,
              controversy=30, overall=75):
    p = Player(first, last, 25, pos)
    p.discipline = discipline
    p.aggressiveness = aggressiveness
    p.controversy = controversy
    p.base_controversy = controversy
    p.overall_rating = lambda: overall
    return p


def mk_team(name, hitter, victim):
    t = Team(name, "City", "Div", "Conf")
    h = Team("Opp", "City", "Div", "Conf")
    t.roster = [hitter] + [mk_player(f"T{i}", "Depth", PlayerPosition.CENTER)
                           for i in range(15)]
    h.roster = [victim] + [mk_player(f"O{i}", "Depth", PlayerPosition.CENTER)
                           for i in range(15)]
    return t, h


def mk_detail(hitter, victim, controversy=30):
    return {"kind": "controversial_hit",
            "hitter": hitter.full_name, "hitter_team": "HT",
            "victim": victim.full_name, "victim_team": "OT",
            "hitter_controversy": controversy}


class FakeApp:
    league = None
    current_date = "2026-10-15"


# -- 1. Review scales with dirtiness ---------------------------------------
# Fresh players per iteration: a suspension appends to controversy_history
# (repeat-offender state), which must not leak across trials.
def mk_goon():
    return mk_player("Goon", "McGoon", PlayerPosition.LEFT_WING,
                     discipline=12, aggressiveness=96, controversy=92)


def mk_gent():
    return mk_player("Gent", "LeGent", PlayerPosition.LEFT_WING,
                     discipline=88, aggressiveness=22, controversy=8)


goon_susp = gent_susp = 0
N = 3000
random.seed(42)
for _ in range(N):
    _g, _v = mk_goon(), mk_player("Vic", "Tim", PlayerPosition.CENTER)
    ht, ot = mk_team("HT", _g, _v)
    r = ni._dops_suspension_review(FakeApp(), mk_detail(_g, _v,
                                                       controversy=92),
                                   ht, ot, "2026-10-15", ())
    goon_susp += 1 if r["games"] > 0 else 0
for _ in range(N):
    _g, _v = mk_gent(), mk_player("Vic", "Tim", PlayerPosition.CENTER)
    ht, ot = mk_team("HT", _g, _v)
    r = ni._dops_suspension_review(FakeApp(), mk_detail(_g, _v,
                                                       controversy=8),
                                   ht, ot, "2026-10-15", ())
    gent_susp += 1 if r["games"] > 0 else 0
print(f"  goon suspended {goon_susp}/{N}, gentleman {gent_susp}/{N}")
check("dirtiness scales suspension chance", goon_susp > gent_susp * 2)
check("goon rate in sane band", 0.05 < goon_susp / N < 0.85)
check("gentleman rate in sane band", 0.0 <= gent_susp / N < 0.30)

# -- 2. Games formula -------------------------------------------------------
# Force the review's coin flip via a namespace-local random shim (patching
# ni.random only touches narrative_incidents' namespace, never the global
# random module the fixtures use).
_real_ni_random = ni.random


class _FakeRandom:
    def __init__(self, val):
        self.val = val

    def random(self):
        return self.val


ni.random = _FakeRandom(0.0)  # always suspend
try:
    # Clean first-timer, no injury, non-star victim -> 1 game
    h = mk_player("Clean", "Player", PlayerPosition.CENTER,
                  discipline=70, aggressiveness=40, controversy=20)
    v = mk_player("Reg", "Ular", PlayerPosition.CENTER, overall=78)
    ht, ot = mk_team("HT", h, v)
    r = ni._dops_suspension_review(FakeApp(), mk_detail(h, v), ht, ot,
                                   "2026-10-15", ())
    check("clean first offense = 1 game", r["games"] == 1)

    # Goon (disc<30) injuring a star victim -> 1+1+1+1 = 4
    h2 = mk_player("Goon", "Two", PlayerPosition.LEFT_WING,
                   discipline=15, aggressiveness=95, controversy=90)
    v2 = mk_player("Star", "Victim", PlayerPosition.CENTER, overall=95)
    v2.is_injured = True
    ht2, ot2 = mk_team("HT", h2, v2)
    r2 = ni._dops_suspension_review(FakeApp(), mk_detail(h2, v2), ht2, ot2,
                                    "2026-10-15", ())
    check("goon injuring star = 4 games", r2["games"] == 4)
    check("suspension attrs set",
          h2.suspension_games_remaining == 4
          and h2.suspension_reason != ""
          and h2.suspended_today is True)

    # Repeat offender: 2 priors -> +4 games (2*min(2,3))
    h3 = mk_player("Rep", "Eat", PlayerPosition.CENTER,
                   discipline=70, aggressiveness=40, controversy=20)
    h3.controversy_history = [
        {"date": "2026-01-01", "type": "suspension", "severity": 5,
         "description": "x", "controversy_after": 40},
        {"date": "2026-02-01", "type": "suspension", "severity": 6,
         "description": "x", "controversy_after": 50}]
    v3 = mk_player("Reg", "Ular2", PlayerPosition.CENTER, overall=78)
    ht3, ot3 = mk_team("HT", h3, v3)
    r3 = ni._dops_suspension_review(FakeApp(), mk_detail(h3, v3), ht3, ot3,
                                    "2026-10-15", ())
    check("repeat offender (2 priors) = 5 games", r3["games"] == 5)
    check("repeat offender recorded in history",
          sum(1 for e in h3.controversy_history
              if e.get("type") == "suspension") == 3)

    # Cap: 3+ priors + everything -> capped at 10
    h4 = mk_player("Men", "Ace", PlayerPosition.LEFT_WING,
                   discipline=10, aggressiveness=99, controversy=99)
    h4.controversy_history = [
        {"date": "2026-01-01", "type": "suspension", "severity": 9,
         "description": "x", "controversy_after": 90} for _ in range(5)]
    v4 = mk_player("Star", "Two", PlayerPosition.CENTER, overall=96)
    v4.is_injured = True
    ht4, ot4 = mk_team("HT", h4, v4)
    r4 = ni._dops_suspension_review(FakeApp(), mk_detail(h4, v4), ht4, ot4,
                                    "2026-10-15", ())
    check("worst case capped at 10 games", r4["games"] == 10)

    # Ghost hitter (not on roster) -> no suspension, no crash
    d5 = dict(mk_detail(h, v))
    d5["hitter"] = "Nobody Nobody"
    r5 = ni._dops_suspension_review(FakeApp(), d5, ht, ot, "2026-10-15", ())
    check("unknown hitter -> no suspension", r5["games"] == 0)
finally:
    ni.random = _real_ni_random

# -- 3. Lineup exclusion ----------------------------------------------------
from quick_sim import best_lines

star = mk_player("Top", "Line", PlayerPosition.CENTER,
                 discipline=20, aggressiveness=90, controversy=80,
                 overall=92)
star.suspension_games_remaining = 3
t5 = Team("LT", "City", "Div", "Conf")
t5.roster = [star] + [mk_player(f"D{i}", "P", PlayerPosition.CENTER,
                               overall=70) for i in range(14)]
lines = best_lines(t5)
dressed = []
for grp in ("Forwards", "Defense", "Goalies"):
    for line in (lines.get(grp) or []):
        for p in (line or []):
            if p is not None:
                dressed.append(p.full_name)
check("best_lines excludes suspended star", star.full_name not in dressed)

# Scrub replaces the slot with an eligible skater
t5.lineup = {"Forwards": [[star,
                           mk_player("C1", "P", PlayerPosition.CENTER,
                                     overall=80),
                           mk_player("R1", "P", PlayerPosition.RIGHT_WING,
                                     overall=80)]],
             "Defense": [], "Goalies": []}
fixed = ni._scrub_suspended_from_lineup(t5)
slot = t5.lineup["Forwards"][0][0]
check("scrub replaces suspended slot",
      fixed >= 1 and slot.full_name != star.full_name
      and not (getattr(slot, "suspension_games_remaining", 0) or 0))
check("flat keys refreshed",
      t5.lineup.get("F1_LW") is not None
      and t5.lineup["F1_LW"].full_name == slot.full_name)

# Advanced sim: a STALE stored lineup with a suspended player must be
# scrubbed at construction (AdvancedGameSim reads team.lineup as-is).
from quick_sim import AdvancedGameSim

starA = mk_player("Adv", "Star", PlayerPosition.LEFT_WING, overall=90)
starA.suspension_games_remaining = 2
tA = Team("AT", "City", "Div", "Conf")
tA.roster = [starA] + [mk_player(f"A{i}", "P", PlayerPosition.LEFT_WING,
                                 overall=70) for i in range(14)]
tA.lineup = {"Forwards": [[starA,
                           mk_player("AC", "P", PlayerPosition.CENTER,
                                     overall=80),
                           mk_player("AR", "P", PlayerPosition.RIGHT_WING,
                                     overall=80)]],
             "Defense": [], "Goalies": []}
tB = Team("BT", "City", "Div", "Conf")
tB.roster = [mk_player(f"B{i}", "P", PlayerPosition.CENTER, overall=70)
             for i in range(15)]
try:
    sim = AdvancedGameSim(tA, tB)
    adv_dressed = []
    for line in (tA.lineup.get("Forwards") or []):
        for p in (line or []):
            if p is not None:
                adv_dressed.append(p.full_name)
    check("advanced sim scrubs stored lineup",
          starA.full_name not in adv_dressed)
except Exception as e:
    check(f"advanced sim scrubs stored lineup (exc: {e})", False)

# -- 4. Games-served countdown ----------------------------------------------
from main import GameManager

susp = mk_player("Serve", "Me", PlayerPosition.CENTER, overall=82)
susp.suspension_games_remaining = 2
susp.suspended_today = True
t6 = Team("UT", "City", "Div", "Conf")
t6.roster = [susp]
t7 = Team("OT2", "City", "Div", "Conf")
t7.roster = [mk_player("O", "P", PlayerPosition.CENTER)]


class FakeGM:
    league = type("L", (), {"teams": [t6, t7]})()
    user_team = t6
    news_log = []
    current_date = "2026-10-16"


gm = FakeGM()
# Same-day tick after issuance: guard holds, flag clears, no service
GameManager._process_suspension_service(gm, {"UT", "OT2"})
check("suspended_today guard holds",
      susp.suspension_games_remaining == 2 and susp.suspended_today is False)
# Next team game: serves one
GameManager._process_suspension_service(gm, {"UT", "OT2"})
check("ticks per team game", susp.suspension_games_remaining == 1)
# Team idle: no tick
GameManager._process_suspension_service(gm, {"OT2"})
check("idle team does not tick", susp.suspension_games_remaining == 1)
# Final game: expires, reason cleared, user news
GameManager._process_suspension_service(gm, {"UT"})
check("expiry clears suspension",
      susp.suspension_games_remaining == 0 and susp.suspension_reason == "")
check("user notified on return", len(gm.news_log) == 1)

# -- 5. Headline spec --------------------------------------------------------
from headlines import make_headline
from datetime import date

msg = make_headline("suspension", date(2026, 10, 15), name="Goon McGoon",
                    team="HT", games=4, victim="Vic Tim")
check("suspension headline builds",
      msg is not None and "SUSPENDED" in msg.subject and "4 game" in msg.subject)

# -- 6. Fine path preserved when no suspension --------------------------------
# Drive the REAL consequence pass with the review forced to decline --
# the fine roll must still fire at its original rate.
_orig_review = ni._dops_suspension_review
ni._dops_suspension_review = lambda *a, **k: {"games": 0}
try:
    fined_n = susp_n = 0
    M = 3000
    random.seed(7)
    for _ in range(M):
        hf = mk_player("Hot", "Head", PlayerPosition.LEFT_WING,
                       discipline=40, aggressiveness=70, controversy=60)
        vf = mk_player("Vic", "F", PlayerPosition.CENTER)
        ht, ot = mk_team("HT", hf, vf)
        ht.team_name, ot.team_name = "HT", "OT"
        drama = ni.apply_incident_consequences(
            FakeApp(), ht, ot, ["controversial_hit"],
            [mk_detail(hf, vf, controversy=60)], False, (3, 2),
            "2026-10-15", None, [])
        for dd in drama:
            if dd.get("kind") == "controversial_hit":
                fined_n += 1 if dd.get("fined") else 0
                susp_n += 1 if dd.get("suspended") else 0
    rate = fined_n / M
    print(f"  fine rate via real pass: {rate:.3f} (expect ~0.48), "
          f"suspensions: {susp_n}")
    check("fine rate unchanged", 0.40 < rate < 0.56)
    check("no suspensions when review declines", susp_n == 0)
finally:
    ni._dops_suspension_review = _orig_review

# -- 7. AI/user parity: review has no user/AI branch --------------------------
import inspect

src = inspect.getsource(ni._dops_suspension_review)
check("review has no user/AI branch",
      "user_team" not in src and "is_ai" not in src and "human" not in src)

# -- 8. Save/load round-trip --------------------------------------------------
try:
    from save_load_system import GameSaveManager
    _gsm = GameSaveManager(None)
    sp = mk_player("Save", "Me", PlayerPosition.CENTER, overall=80)
    sp.suspension_games_remaining = 3
    sp.suspension_reason = "Illegal hit on Vic Tim"
    sp.suspended_today = True
    data = _gsm._serialize_player(sp)
    rp = _gsm._restore_player(data)
    check("suspension attrs survive save/load",
          getattr(rp, "suspension_games_remaining", -1) == 3
          and getattr(rp, "suspension_reason", "") == "Illegal hit on Vic Tim"
          and getattr(rp, "suspended_today", False) is True)
except Exception as e:
    check(f"suspension attrs survive save/load (exc: {e})", False)

# -- 9. End-to-end: serves exactly N team games, then returns -------------
from main import GameManager as _GM2

starE = mk_player("End", "ToEnd", PlayerPosition.CENTER, overall=88)
starE.suspension_games_remaining = 3
starE.suspended_today = True  # issued after today's game
tE = Team("ET", "City", "Div", "Conf")
tE.roster = [starE] + [mk_player(f"E{i}", "P", PlayerPosition.CENTER,
                                 overall=70) for i in range(17)]
tF = Team("FT", "City", "Div", "Conf")
tF.roster = [mk_player(f"F{i}", "P", PlayerPosition.CENTER, overall=70)
             for i in range(18)]


class FakeGM2:
    league = type("L", (), {"teams": [tE, tF]})()
    user_team = tF
    news_log = []
    current_date = "2026-10-20"


gm2 = FakeGM2()
team_games_missed = 0
for day in range(8):
    # Team plays every other day
    plays = (day % 2 == 0)
    played = {"ET", "FT"} if plays else {"FT"}
    was_out = starE.suspension_games_remaining > 0
    guard_day = bool(getattr(starE, "suspended_today", False))
    _GM2._process_suspension_service(gm2, played)
    dressed_names = {p.full_name for grp in
                     ("Forwards", "Defense", "Goalies")
                     for line in (best_lines(tE).get(grp) or [])
                     for p in (line or []) if p is not None}
    if plays and was_out and not guard_day:
        team_games_missed += 1
    if starE.suspension_games_remaining > 0:
        check(f"day {day}: suspended star out of lineup",
              starE.full_name not in dressed_names)
    else:
        check(f"day {day}: reinstated star dresses",
              starE.full_name in dressed_names)
check("served exactly 3 team games", team_games_missed == 3)
check("reason cleared on return", starE.suspension_reason == "")

# -- 10. Lightweight path feels the absence ------------------------------------
import main as main_mod


class FakeApp2:
    _strength_cache = {}


# NOTE (2026-09-30): ratings must sit in the realistic NHL band (~78-85).
# The 2026-09-29 parity re-anchor normalizes strength to 0.5 + (avg-70)/40
# clamped at a 0.5 floor, so the old all-45s synthetic roster clamped both
# readings at the floor and the comparison could never hold.
star9 = mk_player("Star", "Nine", PlayerPosition.CENTER, overall=88)
t9 = Team("ST", "City", "Div", "Conf")
t9.roster = [star9] + [mk_player(f"R{i}", "P", PlayerPosition.CENTER,
                                 overall=78) for i in range(19)]
app9 = FakeApp2()
s_full = main_mod.HockeyManagerGUI._calculate_team_strength(app9, t9)
star9.suspension_games_remaining = 2
app9._strength_cache = {}
s_susp = main_mod.HockeyManagerGUI._calculate_team_strength(app9, t9)
check("lightweight strength drops without suspended star", s_susp < s_full)

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("FAILURES:")
    for f in FAILURES:
        print(f" - {f}")
sys.exit(1 if FAILURES else 0)
