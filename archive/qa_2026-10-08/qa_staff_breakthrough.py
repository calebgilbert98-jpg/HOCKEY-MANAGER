# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: staff breakthroughs -- results-driven, chance-based development.

A great season (wins, playoff runs, developing players into success
stories of varying degrees) becomes a CHANCE at a career leap, weighted
by coaching stock. Covers Chris's case: an AHL goalie coach who makes
his goalies NHL-ready can become an elite NHL-tier goalie coach.

Run: python3 qa_staff_breakthrough.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as gc
from game_classes import (
    League, Staff, StaffRole, Team,
    _STAFF_DEVELOP_ATTRS, _coach_breakthrough_story, _staff_season_score,
    roll_staff_breakthrough, roll_staff_breakthroughs, staff_is_icon,
)

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def mkcoach(role=StaffRole.GOALIE_COACH, age=45, rep=60, assignment="ahl"):
    s = Staff("Riser", "Coach", role)
    s.age = age
    s.reputation = rep
    s.assignment = assignment
    s.experience = 8
    s.years_with_team = 3
    for a in _STAFF_DEVELOP_ATTRS:
        setattr(s, a, 60)
    return s


def stories_for(weight, goalie_weight, seg="ahl"):
    other = "nhl" if seg == "ahl" else "ahl"
    return {"Testers": {seg: {"weight": weight, "goalie_weight": goalie_weight},
                        other: {"weight": 0.0, "goalie_weight": 0.0}}}


def trial_rate(mk, n, seed0):
    """Breakthrough rate over n seeded trials (fresh coach each time)."""
    hits = 0
    for i in range(n):
        random.seed(seed0 + i)
        s = mk()
        broke, _, _ = roll_staff_breakthrough(s, "Testers", *mk.stories)
        hits += broke
    return hits / n


# --- 1. Chris's case: AHL goalie coach, two NHL-ready goalies ------------------
def _ahl_hero():
    return mkcoach(StaffRole.GOALIE_COACH, age=45, rep=60, assignment="ahl")


_ahl_hero.stories = (stories_for(6.0, 6.0, "ahl"), None)
rate = trial_rate(_ahl_hero, 40, 5000)
check("AHL goalie hero breaks through often (chance ~0.65)",
      0.5 <= rate <= 1.0, f"rate={rate:.2f}")

# Score check: 6.0 goalie weight * 1.5 = 9.0
sc = _staff_season_score(_ahl_hero(), "Testers", stories_for(6.0, 6.0, "ahl"), None)
check("goalie story score scales (6 gw -> 9.0)", abs(sc - 9.0) < 1e-9,
      f"score={sc}")

# --- 2. chance, not guarantee: mid score gives mixed outcomes --------------------
def _mid():
    return mkcoach(StaffRole.GOALIE_COACH, age=45, rep=60, assignment="ahl")


_mid.stories = (stories_for(3.2, 3.2, "ahl"), None)  # score 4.8 -> chance 0.36
rate = trial_rate(_mid, 30, 6000)
check("mid season is a coin flip, not destiny", 0.15 < rate < 0.85,
      f"rate={rate:.2f}")

# --- 3. stagnant goalies -> quiet year ----------------------------------------------
def _stagnant():
    return mkcoach(StaffRole.GOALIE_COACH, age=45, rep=60, assignment="ahl")


_stagnant.stories = (stories_for(0.0, 0.0, "ahl"), None)
rate = trial_rate(_stagnant, 40, 7000)
check("no stories -> background chance only", rate < 0.25, f"rate={rate:.2f}")

# --- 4. Cup-winning head coach -------------------------------------------------------
cup_results = {"Testers": {"w": 52, "l": 22, "otl": 8, "win_pct": 0.634,
                           "playoff": "Won Stanley Cup", "champ": True,
                           "adams_id": None}}


def _champ():
    s = mkcoach(StaffRole.HEAD_COACH, age=55, rep=78, assignment="nhl")
    return s


_champ.stories = (stories_for(4.0, 0.0, "nhl"), cup_results)
sc = _staff_season_score(_champ(), "Testers", stories_for(4.0, 0.0, "nhl"),
                         cup_results)
check("Cup HC score: stories + win% + Cup", abs(sc - (2.0 + 2.0 + 3.0)) < 1e-9,
      f"score={sc}")
rate = trial_rate(_champ, 30, 8000)
check("Cup-winning HC usually breaks through", rate >= 0.35, f"rate={rate:.2f}")

# Jack Adams bump
hc = _champ()
adams_results = {"Testers": {"w": 40, "l": 35, "otl": 7, "win_pct": 0.488,
                             "playoff": "Missed playoffs", "champ": False,
                             "adams_id": hc.id}}
sc = _staff_season_score(hc, "Testers", stories_for(0.0, 0.0, "nhl"),
                         adams_results)
check("Jack Adams adds +3 to score", abs(sc - 3.0) < 1e-9, f"score={sc}")

# --- 5. breakthrough effects -----------------------------------------------------------
random.seed(9001)
hero = _ahl_hero()
spot_before = {a: getattr(hero, a) for a in
               ("coaching_goalies", "technical_coaching", "player_development")}
orig = gc.random.random
gc.random.random = lambda: 0.0  # force the breakthrough
try:
    broke, score, chance = roll_staff_breakthrough(
        hero, "Testers", stories_for(6.0, 6.0, "ahl"), None)
finally:
    gc.random.random = orig
check("breakthrough fires", broke is True)
# 3 sampled attrs were tracked; at least those move (+1..2 each)
tracked_jump = sum(getattr(hero, a) - spot_before[a] for a in spot_before)
check("breakthrough is a focused leap (+1..2 on sampled attrs)",
      tracked_jump >= 3,
      f"tracked_jump={tracked_jump}")
check("reputation jumps (+1..4)", 61 <= hero.reputation <= 64,
      f"rep={hero.reputation}")
check("stock banks +14", hero.stock == 14, f"stock={hero.stock}")
check("career leap counted", hero.career_breakthroughs == 1)

# --- 6. stock dynamics on a miss ----------------------------------------------------------
orig = gc.random.random
gc.random.random = lambda: 0.999  # force a miss
try:
    s = _ahl_hero()
    s.stock = 20
    broke, score, _ = roll_staff_breakthrough(
        s, "Testers", stories_for(6.0, 6.0, "ahl"), None)
    check("forced miss stays a miss", broke is False)
    check("great season without leap still banks stock (+5)", s.stock == 25,
          f"stock={s.stock}")

    bad_results = {"Testers": {"w": 25, "l": 50, "otl": 7, "win_pct": 0.305,
                               "playoff": "Missed playoffs", "champ": False,
                               "adams_id": None}}
    hcb = mkcoach(StaffRole.HEAD_COACH, age=55, rep=70, assignment="nhl")
    hcb.stock = 20
    broke, score, _ = roll_staff_breakthrough(
        hcb, "Testers", stories_for(0.0, 0.0, "nhl"), bad_results)
    check("terrible season burns stock (-10)", hcb.stock == 10,
          f"stock={hcb.stock} score={score}")
finally:
    gc.random.random = orig

# --- 7. situation dynamics in the full pass ----------------------------------------------
random.seed(9100)
league = League("NHL")
league.season_year = 2028
t = Team("Testers", "Testville", "Atlantic", "Eastern", "NHL", "GM", None)
t.staff = []
league.teams = [t]
# unemployed coach with glow: fades
fa = mkcoach(StaffRole.HEAD_COACH, age=50, rep=70, assignment="nhl")
fa.stock = 50
league.free_agent_staff = [fa]
# new-team coach: stock trimmed as he proves it again
newbie = mkcoach(StaffRole.ASSISTANT_COACH, age=40, rep=60, assignment="nhl")
newbie.stock = 50
newbie.years_with_team = 1
t.staff.append(newbie)
orig = gc.random.random
gc.random.random = lambda: 0.999  # no breakthroughs; pure stock mechanics
try:
    roll_staff_breakthroughs(league)
finally:
    gc.random.random = orig
check("unemployed coach's stock fades (x0.7)", fa.stock == 35, f"stock={fa.stock}")
check("new-situation coach's stock trimmed (x0.8)", newbie.stock == 40,
      f"stock={newbie.stock}")

# --- 8. non-coaching roles don't roll ------------------------------------------------------
scout = Staff("Eye", "Ball", StaffRole.AMATEUR_SCOUT)
scout.age, scout.reputation, scout.stock = 45, 60, 30
broke, score, chance = roll_staff_breakthrough(
    scout, "Testers", stories_for(9.0, 9.0, "nhl"), cup_results)
check("scouts don't get coaching breakthroughs",
      broke is False and score == 0.0 and chance == 0.0)

# --- 9. end_of_season integration --------------------------------------------------------------
random.seed(9200)
league2 = League("NHL")
league2.season_year = 2028
t2 = Team("Testers", "Testville", "Atlantic", "Eastern", "NHL", "GM", None)
ghc = mkcoach(StaffRole.GOALIE_COACH, age=45, rep=74, assignment="ahl")
hhc = mkcoach(StaffRole.HEAD_COACH, age=55, rep=78, assignment="nhl")
hhc.years_with_team = 5
t2.staff = [ghc, hhc]
league2.teams = [t2]
league2.free_agent_staff = []
league2.overseas_staff = []
league2._staff_results_cache = {
    "Testers": {"w": 52, "l": 22, "otl": 8, "win_pct": 0.634,
                "playoff": "Won Stanley Cup", "champ": True,
                "adams_id": hhc.id}}
orig = gc.random.random
gc.random.random = lambda: 0.0  # force every chance roll to hit
try:
    league2.end_of_season()
finally:
    gc.random.random = orig
check("rollover breakthrough: goalie coach leaps",
      ghc.career_breakthroughs >= 1,
      f"leaps={ghc.career_breakthroughs}")
check("rollover breakthrough: Cup+Adams HC leaps",
      hhc.career_breakthroughs >= 1)
check("results cache consumed", not hasattr(league2, "_staff_results_cache"))
check("breakthrough news recorded",
      bool(getattr(league2, "staff_breakthrough_news", [])),
      f"news={getattr(league2, 'staff_breakthrough_news', [])}")
check("stories computed", isinstance(getattr(league2, "_staff_stories", None), dict)
      and "Testers" in league2._staff_stories)

# --- 10. scout-voiced breakthrough news --------------------------------------------------
random.seed(41)
_sg = mkcoach(StaffRole.GOALIE_COACH, age=45, rep=80, assignment="nhl")
_sg.first_name, _sg.last_name = "Goalie", "Guru"
_stories10 = {"Testers": {"nhl": {"weight": 6.0, "goalie_weight": 6.0,
                                  "headline": ("Kid Keeper", 5, 74, True)},
                          "ahl": {"weight": 0.0, "goalie_weight": 0.0,
                                  "headline": None}}}
_cup10 = {"Testers": {"w": 52, "l": 22, "otl": 8, "win_pct": 0.634,
                      "playoff": "Won Stanley Cup", "champ": True,
                      "adams_id": None}}
_s10 = _coach_breakthrough_story(_sg, "Testers", _stories10, _cup10)
check("scout voice present", "Scouts are buzzing" in _s10, _s10)
check("names the story player", "Kid Keeper" in _s10 and "74 to 79" in _s10,
      _s10)
check("cites the Cup", "Stanley Cup" in _s10, _s10)
check("goalie quote used",
      any(q in _s10 for q in gc._SCOUT_COACH_QUOTES["goalie"]), _s10)

_sh = mkcoach(StaffRole.HEAD_COACH, age=55, rep=85, assignment="nhl")
_sh.first_name, _sh.last_name = "Bench", "Boss"
_adams10 = {"Testers": {"w": 48, "l": 26, "otl": 8, "win_pct": 0.585,
                        "playoff": "Lost Round 2", "champ": False,
                        "adams_id": _sh.id}}
_s10b = _coach_breakthrough_story(_sh, "Testers", {}, _adams10)
check("cites the Jack Adams", "Jack Adams" in _s10b, _s10b)
check("head-coach quote used",
      any(q in _s10b for q in gc._SCOUT_COACH_QUOTES["head"]), _s10b)

_s10c = _coach_breakthrough_story(_sh, "Testers", {}, {})
check("no-evidence story still valid",
      "Scouts are buzzing" in _s10c and " after " not in _s10c, _s10c)
check("no mechanical rep readout", "rep " not in _s10c.lower()
      or "reputation" not in _s10c.lower(), _s10c)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
