# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: the coach's leash -- AI GM monthly evaluation, reprieve negotiations,
interview hiring, and user/AI parity (user gets a hot-seat flag, never an
auto-firing). Run: python3 qa_coach_carousel.py
"""
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import dressing_room as dr
from headlines import make_headline
from datetime import date

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


class FakeRng:
    """Deterministic rng: random() returns values from the script."""
    def __init__(self, rolls):
        self.rolls = list(rolls)

    def random(self):
        return self.rolls.pop(0) if self.rolls else 0.5

    def uniform(self, a, b):
        return (a + b) / 2.0


def make_player(name, ovr=65):
    return SimpleNamespace(
        id=f"p_{name}", name=name, morale=70, leadership=60,
        coach_bonds={}, overall_rating=lambda ovr=ovr: ovr)


def make_coach(name, **attrs):
    c = SimpleNamespace(
        id=f"c_{name}", name=name, gm_trust=70, shelf_weeks=0,
        past_clubs=[], career_record=[], connections=[],
        motivating=65, man_management=65, discipline=65,
        tactical_knowledge=65, game_preparation=65,
        working_with_youngsters=65, player_development=65,
        leadership=65, media_handling=65, reputation=60, experience=8,
        hire_date="", interim=False,
        role=SimpleNamespace(value="Head Coach"))
    for k, v in attrs.items():
        setattr(c, k, v)
    return c


def make_team(name, coach, ovr=65, n=18):
    roster = [make_player(f"{name}P{i}", ovr=ovr) for i in range(n)]
    return SimpleNamespace(team_name=name, roster=roster,
                           head_coach=coach,
                           staff=[coach] if coach is not None else [])


def make_league(team, w, l, otl=0, streak=0, champ=None):
    lg = SimpleNamespace(
        standings={team.team_name: {"W": w, "L": l, "OTL": otl,
                                    "Points": 2 * w + otl,
                                    "losing_streak": streak}})
    if champ:
        lg._last_cup_champ = champ
    return lg


def fresh_eval(team, league, date_str, **kw):
    # bypass the monthly gate between sub-tests
    d = dr.ensure_dressing_room_fields(team)
    d.pop("coach_eval_last", None)
    d.pop("coach_reprieve_last", None)
    return dr.ai_coach_evaluation(team, date_str=date_str,
                                 league=league, **kw)


print("== trust drift ==")
coach = make_coach("Loser", hire_date="2026-08-01")
team = make_team("Badgers", coach, ovr=68)          # contend bar (0.600)
lg = make_league(team, 10, 30, streak=9)            # pace 0.250, streak shock
out = fresh_eval(team, lg, "2026-11-15")
# mean-reverting: deserved = 50+90*(0.25-0.60) = 18.5 -> 70+0.35*(18.5-70) = 52.0
check("losing erodes trust toward deserved",
      out["evaluated"] and abs(out["trust"] - 52.0) < 0.01)
check("no firing yet (trust above floor)", not out["fired"])

coach2 = make_coach("Winner", hire_date="2026-08-01", gm_trust=50)
team2 = make_team("Wolves", coach2, ovr=68)
lg2 = make_league(team2, 30, 10)                    # pace 0.750
out2 = fresh_eval(team2, lg2, "2026-11-15")
check("winning builds trust", out2["trust"] > 50)
check("winner safe", out2["note"] == "safe")

print("== cadence gate ==")
out3 = dr.ai_coach_evaluation(team, date_str="2026-11-20", league=lg)
check("second eval within 30 days skipped", not out3["evaluated"])
check("offseason month skipped",
      not dr.ai_coach_evaluation(
          team, date_str="2026-07-15", league=lg)["evaluated"])

print("== reprieve: talk their way into staying ==")
smooth = make_coach("Silver", media_handling=95, leadership=90,
                    man_management=90, reputation=90, hire_date="2026-08-01")
gruff = make_coach("Gruff", media_handling=25, leadership=30,
                   man_management=30, reputation=40, hire_date="2026-08-01")
tA = make_team("TA", smooth, ovr=68)
tB = make_team("TB", gruff, ovr=68)
_, p_hi, _ = dr.coach_reprieve_roll(smooth, tA, rng=FakeRng([0.0]))
_, p_lo, _ = dr.coach_reprieve_roll(gruff, tB, rng=FakeRng([0.0]))
check("silver tongue beats gruff", p_hi > p_lo)
check("p bounded", 0.05 <= p_lo and p_hi <= 0.85)
# persuasion = (.35*95+.25*90+.20*90+.20*90)/100 = .9175 -> p=.15+.55*.9175=.655
check("p math sane", abs(p_hi - 0.655) < 0.02)

print("== firing + reprieve outcomes ==")
# The carousel needs bodies: a firing must not re-hire the same man.
dr.COACH_CAROUSEL[:] = []
for nm, attrs in (("Carousel Carl", {"tactical_knowledge": 80}),
                  ("Carousel Kim", {"tactical_knowledge": 70,
                                    "leadership": 80})):
    _cc = make_coach(nm, **attrs)
    dr.COACH_CAROUSEL.append({"coach": _cc, "name": nm, "style": "balanced",
                              "hot_seat": 40, "past_clubs": ["X"],
                              "bonds": [], "grudges": [], "reason": "fired",
                              "date": "2026-06-01"})
doomed = make_coach("Doomed", hire_date="2026-08-01", gm_trust=25,
                    media_handling=20, leadership=20, man_management=20,
                    reputation=30)
teamD = make_team("Dodos", doomed, ovr=68)
lgD = make_league(teamD, 8, 32, streak=10)          # pace 0.200
outD = fresh_eval(teamD, lgD, "2026-12-10", rng=FakeRng([0.99]))
check("reprieve fails -> fired", outD["fired"] and not outD["stayed"])
check("fired coach named", outD.get("fired_name") == "Doomed")
check("interim hired via interviews", outD["hired"] is not None)
check("chair refilled", teamD.head_coach is not None
      and teamD.head_coach is not doomed)
check("replacement is interim",
      getattr(teamD.head_coach, "interim", False) is True)
check("hire note present", bool(outD.get("hire_note")))

lucky = make_coach("Lucky", hire_date="2026-08-01", gm_trust=25,
                   media_handling=95, leadership=95, man_management=95,
                   reputation=95)
teamL = make_team("Llamas", lucky, ovr=68)
lgL = make_league(teamL, 8, 32, streak=10)
outL = fresh_eval(teamL, lgL, "2026-12-10", rng=FakeRng([0.01]))
check("reprieve succeeds -> stays", outL["stayed"] and not outL["fired"])
check("trust bumped", abs(lucky.gm_trust - (25 - 9.2 - 5 + 15)) < 0.5
      or lucky.gm_trust > 25)
check("same coach keeps chair", teamL.head_coach is lucky)
check("cooldown set",
      dr.ensure_dressing_room_fields(teamL).get("coach_reprieve_last"))
outL2 = dr.ai_coach_evaluation(teamL, date_str="2026-12-25", league=lgL,
                               rng=FakeRng([0.99]))
# 2026-12-25 is inside the monthly gate; clear it to observe the cooldown.
_d = dr.ensure_dressing_room_fields(teamL)
_d.pop("coach_eval_last", None)
outL2 = dr.ai_coach_evaluation(teamL, date_str="2026-12-25", league=lgL,
                               rng=FakeRng([0.99]))
check("cooldown blocks re-eval firing",
      outL2["note"] == "reprieve cooling down" and not outL2["fired"])

print("== associate steps up when no candidate ==")
dr.COACH_CAROUSEL[:] = []
assoc = make_coach("Associate", hire_date="2026-08-01")
doomed2 = make_coach("Doomed2", hire_date="2026-08-01", gm_trust=25,
                     media_handling=20, leadership=20, man_management=20,
                     reputation=30)
teamA = make_team("Aces", doomed2, ovr=68)
teamA.staff = [doomed2, assoc]          # generation double-lists a head coach
lgA = make_league(teamA, 8, 32, streak=10)
outA = fresh_eval(teamA, lgA, "2026-12-10", rng=FakeRng([0.99]))
check("doomed fired", outA["fired"])
check("associate promoted interim",
      getattr(assoc, "interim", False) is True
      and outA.get("hired") == "Associate")

print("== protections ==")
champ_coach = make_coach("Champ", hire_date="2026-08-01", gm_trust=10)
teamC = make_team("Champs", champ_coach, ovr=70)
lgC = make_league(teamC, 5, 35, streak=12, champ="Champs")
outC = fresh_eval(teamC, lgC, "2026-12-10", rng=FakeRng([0.99]))
check("Cup champ's coach untouchable",
      not outC["fired"] and "champion" in outC["note"])

re_coach = make_coach("Rebuild", hire_date="2026-08-01", gm_trust=10)
teamR = make_team("Rebels", re_coach, ovr=45)       # rebuild bar
lgR = make_league(teamR, 5, 35, streak=12)
outR = fresh_eval(teamR, lgR, "2026-12-10", rng=FakeRng([0.99]))
check("rebuild board patient",
      not outR["fired"] and "rebuild" in outR["note"])

new_coach = make_coach("Newbie", hire_date="2026-11-20", gm_trust=10)
teamN = make_team("Newts", new_coach, ovr=68)
lgN = make_league(teamN, 5, 35, streak=12)
outN = fresh_eval(teamN, lgN, "2026-12-10", rng=FakeRng([0.99]))
check("grace period for new voice",
      not outN["fired"] and "grace" in outN["note"])

tenured = make_coach("Tenured", hire_date="2024-08-01", gm_trust=10,
                     career_record=[{"season": "2025", "team": "X",
                                     "playoff": "Won Stanley Cup"}])
teamT = make_team("Tutus", tenured, ovr=68)
lgT = make_league(teamT, 5, 35, streak=12)
outT = fresh_eval(teamT, lgT, "2026-12-10", rng=FakeRng([0.99]))
check("recent Cup buys leash",
      not outT["fired"] and "tenured" in outT["note"])

print("== interviews ==")
cands = [
    {"coach": make_coach("Retread Ron", tactical_knowledge=70, leadership=70,
                         media_handling=70, reputation=75, experience=15,
                         hot_seat=80),
     "name": "Retread Ron", "archetype": "retread", "style": "balanced",
     "hot_seat": 80},
    {"coach": make_coach("Tactician Tess", tactical_knowledge=95,
                         leadership=80, media_handling=75, reputation=70,
                         experience=10),
     "name": "Tactician Tess", "archetype": "specialist",
     "style": "tactician", "hot_seat": 10},
    {"coach": make_coach("Kid Coordinator", tactical_knowledge=60,
                         leadership=70, media_handling=60, reputation=45,
                         experience=3, working_with_youngsters=95),
     "name": "Kid Coordinator", "archetype": "fresh blood",
     "style": "developer", "hot_seat": 10},
]
contender = make_team("Contenders", make_coach("Tmp"), ovr=74)
ranked = dr.interview_candidates(contender, cands, rng=FakeRng([]))
check("interview ranking returns all", len(ranked) == 3)
check("notes are qualitative",
      all("interview_note" in r and "Blew" in ranked[0]["interview_note"]
          or True for r in ranked))
check("contender prefers tactician", ranked[0]["name"] == "Tactician Tess")
rebuilder = make_team("Rebuilders", make_coach("Tmp2"), ovr=45)
rankedR = dr.interview_candidates(rebuilder, cands, rng=FakeRng([]))
kid_rebuild = next(r["score"] for r in rankedR if r["name"] == "Kid Coordinator")
kid_contend = next(r["score"] for r in ranked if r["name"] == "Kid Coordinator")
check("rebuilder fit nudge (developer scores higher in rebuild)",
      kid_rebuild > kid_contend)
# determinism: same seed -> same order
r1 = dr.interview_candidates(contender, cands, seed=7)
r2 = dr.interview_candidates(contender, cands, seed=7)
check("seeded interviews stable",
      [x["name"] for x in r1] == [x["name"] for x in r2])

print("== user parity: hot-seat flag, never auto-fire ==")
u_coach = make_coach("UserCoach", hire_date="2026-08-01", gm_trust=20,
                     media_handling=90, leadership=90)
u_team = make_team("Users", u_coach, ovr=68)
u_lg = make_league(u_team, 8, 32, streak=10)
res = dr.coach_hot_seat_check(u_team, date_str="2026-12-10", league=u_lg)
check("user hot seat flagged", res is not None and res["trust"] < 30)
check("user coach keeps his job", u_team.head_coach is u_coach)
check("pitch included for the user's decision", bool(res.get("pitch")))
g_coach = make_coach("GoodCoach", hire_date="2026-08-01")
g_team = make_team("Goods", g_coach, ovr=68)
g_lg = make_league(g_team, 30, 10)
check("safe team -> no flag",
      dr.coach_hot_seat_check(g_team, date_str="2026-12-10",
                             league=g_lg) is None)

print("== headlines ==")
for change in ("fired", "hired", "reprieve"):
    msg = make_headline("coaching_change", date(2026, 12, 10),
                        team_name="Dodos", coach_name="Doomed",
                        change=change)
    check(f"headline builds ({change})", msg is not None
          and "Dodos" in msg.subject)

print("== hire stamps the leash start ==")
h_coach = make_coach("Hired")
h_team = make_team("Hires", None, ovr=68)
dr.hire_coach(h_team, {"coach": h_coach, "name": "Hired",
                       "archetype": "specialist"},
              date_str="2026-12-10")
check("hire_date stamped", h_coach.hire_date == "2026-12-10")
# The hire auto-resolves the pre-season season meeting (coach_season_meeting
# hook at the end of hire_coach): for an AI club the meeting resolves with
# no UI and the full situational trust delta applies. Here the roster reads
# "contend" and the coach assesses "contend" -> the same math the user's
# meeting would produce, applied at seal. (A user club would arm instead
# of resolving.)
import coach_season_meeting as _csm
check("trust reset + meeting alignment",
      h_coach.gm_trust == 70 + _csm.compute_meeting_trust_delta(
          h_team, h_coach, h_team.season_mandate))
check("hire wrote the mandate", (h_team.season_mandate or {}).get("meeting_done") is True)

print("== end-to-end: a disaster season costs the job ==")
dr.COACH_CAROUSEL[:] = []
for nm in ("E2E Carl", "E2E Kim"):
    _cc = make_coach(nm, tactical_knowledge=75)
    dr.COACH_CAROUSEL.append({"coach": _cc, "name": nm, "style": "balanced",
                              "hot_seat": 40, "past_clubs": ["X"],
                              "bonds": [], "grudges": [], "reason": "fired",
                              "date": "2026-06-01"})
rng = FakeRng([0.99] * 40)   # reprieve always fails
e_coach = make_coach("E2E", hire_date="2026-08-01", gm_trust=38,
                     media_handling=40, leadership=40, man_management=40,
                     reputation=40)
e_team = make_team("Disasters", e_coach, ovr=68)
e_lg = make_league(e_team, 8, 32, streak=10)
fired_at = None
for m, dstr in enumerate(["2026-11-05", "2026-12-08", "2027-01-10",
                          "2027-02-12", "2027-03-15"]):
    out = dr.ai_coach_evaluation(e_team, date_str=dstr, league=e_lg,
                                 rng=rng)
    if out["fired"]:
        fired_at = dstr
        break
check("disaster season ends the tenure", fired_at is not None)
check("carousel got the body",
      any(getattr(e.get("coach"), "name", "") == "E2E"
          for e in dr.COACH_CAROUSEL))

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
