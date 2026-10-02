"""QA: coach job-seeking — unemployed HCs considering AHL/NHL assistant jobs.

Covers Muck's directives (2026-10-02):
  1. Same-team demotion insult: just-fired HC refuses an assistant job with
     the team that fired him, but considers one elsewhere.
  2. Rivalry gate: won't coach his old club's bitter rival (heavy penalty /
     refusal), mirroring the player-defection bands (50/70).
  3. Step-down willingness: age, unemployment length, reputation, Cup wins,
     ambition, and stock shape AHL-head / NHL-assistant appeal.
  4. AI wiring: carousel-first AHL hiring, refusal filter in interviews.
"""
import sys
sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

print("== Coach job-seeking ==")

from types import SimpleNamespace as SN
from game_classes import Staff, StaffRole
import reputation_system as rs
import dressing_room as dr

# ---------------------------------------------------------------- helpers
def make_coach(age=45, reputation=70, ambition="climb", cup=False,
               stock=0, controversy=20):
    c = Staff(first_name="Test", last_name="Coach", role=StaffRole.HEAD_COACH,
              age=age, reputation=reputation)
    c.ambition = ambition
    c.stock = stock
    c.controversy = controversy
    c.career_accolades = [{"award": "stanley_cup", "year": "2025"}] if cup else []
    return c

def make_team(name, win_pct=0.5):
    return SN(team_name=name, roster=[])

def make_entry(coach, firing_club, days_ago, reason="fired"):
    from datetime import date, timedelta
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    return {"coach": coach, "name": coach.full_name, "style": "balanced",
            "hot_seat": 70 if reason == "fired" else 40,
            "bonds": [], "grudges": [],
            "past_clubs": [firing_club] if firing_club else [],
            "reason": reason, "date": d}

TEAM_A = make_team("Sharks", win_pct=0.45)    # the firing club (rebuild)
TEAM_B = make_team("Kings", win_pct=0.62)     # contender elsewhere
TEAM_C = make_team("Ducks", win_pct=0.40)     # rebuild elsewhere

# ---------------------------------------------------------------- 1. same-team demotion insult
coach = make_coach(age=48, reputation=72)
entry = make_entry(coach, "Sharks", days_ago=10)
ap = rs.coach_job_appeal(coach, TEAM_A, job_role="assistant",
                         carousel_entry=entry, date_str="")
check("just-fired HC REFUSES assistant job with firing team",
      ap.get("refused") is True and ap["score"] == 0)
check("refusal reason mentions the firing",
      any("fired him as head coach" in r for r in ap["reasons"]))

# Same coach, different team: considered, not refused.
ap2 = rs.coach_job_appeal(coach, TEAM_B, job_role="assistant",
                          carousel_entry=entry, date_str="",
                          team_context={"win_pct": 0.62})
check("just-fired HC CONSIDERS assistant job elsewhere",
      ap2.get("refused") is False and ap2["score"] > 0)

# After 6 months, the insult fades to a heavy penalty (not a ban).
entry_old = make_entry(coach, "Sharks", days_ago=200)
ap3 = rs.coach_job_appeal(coach, TEAM_A, job_role="assistant",
                          carousel_entry=entry_old, date_str="")
check("6-month-old firing: same-team assistant = penalty, not refusal",
      ap3.get("refused") is False and ap3["score"] < 50
      and any("Swallowing his pride" in r for r in ap3["reasons"]))

# Head-coach job with the firing team is NOT the demotion insult.
ap4 = rs.coach_job_appeal(coach, TEAM_A, job_role="head_coach",
                          carousel_entry=entry, date_str="")
check("same-team HEAD coach job not hit by demotion insult",
      ap4.get("refused") is False)

# ---------------------------------------------------------------- 2. rivalry gate
# Build a bitter team_team rivalry: Sharks vs Ducks, intensity 80.
rivs = []
rs.add_rivalry(rivs, make_team("Sharks"), make_team("Ducks"),
               "team_team", 80, "declared", "Bad blood.", grudge=85)
coach_r = make_coach(age=50, reputation=75)
entry_r = make_entry(coach_r, "Sharks", days_ago=300)
ap5 = rs.coach_job_appeal(coach_r, TEAM_C, job_role="head_coach",
                          carousel_entry=entry_r, rivalries=rivs)
check("bitter rival (80) of old club => hard refusal",
      ap5.get("refused") is True and ap5["score"] == 0
      and any("Bitter rival" in r for r in ap5["reasons"]))

# Hated but not bitter: 55 => heavy penalty, no refusal.
rivs2 = []
rs.add_rivalry(rivs2, make_team("Sharks"), make_team("Kings"),
               "team_team", 55, "playoff", "Heated.", grudge=60)
ap6 = rs.coach_job_appeal(coach_r, TEAM_B, job_role="assistant",
                          carousel_entry=entry_r, rivalries=rivs2,
                          team_context={"win_pct": 0.62})
check("hated rival (55) => -25 penalty, still considers",
      ap6.get("refused") is False
      and any("Hated rival" in r for r in ap6["reasons"]))

# Mild: 40 => small penalty.
rivs3 = []
rs.add_rivalry(rivs3, make_team("Sharks"), make_team("Kings"),
               "team_team", 40, "regional", "Simmering.", grudge=40)
ap7 = rs.coach_job_appeal(coach_r, TEAM_B, job_role="assistant",
                          carousel_entry=entry_r, rivalries=rivs3,
                          team_context={"win_pct": 0.62})
check("mild rival (40) => -10, not refused",
      ap7.get("refused") is False
      and any("Bad blood" in r for r in ap7["reasons"]))

# No rivalry at all => no penalty.
ap8 = rs.coach_job_appeal(coach_r, TEAM_B, job_role="assistant",
                          carousel_entry=entry_r, rivalries=[],
                          team_context={"win_pct": 0.62})
check("no rivalry => no rivalry penalty",
      not any("rival" in r.lower() for r in ap8["reasons"]))

# ---------------------------------------------------------------- 3. step-down willingness
# Young coach, AHL head: eager.
young = make_coach(age=36, reputation=62)
ey = make_entry(young, "Sharks", days_ago=120)
apy = rs.coach_job_appeal(young, TEAM_C, job_role="ahl_head",
                          carousel_entry=ey, date_str="")
check("young HC (36) wants the AHL job",
      apy["score"] >= 60
      and any("rebuild his stock" in r for r in apy["reasons"]))

# Veteran, fresh firing, AHL: no.
vet = make_coach(age=60, reputation=78)
ev = make_entry(vet, "Sharks", days_ago=30)
apv = rs.coach_job_appeal(vet, TEAM_C, job_role="ahl_head",
                          carousel_entry=ev, date_str="")
check("veteran (60), 30 days out, rejects AHL buses",
      apv["score"] < 50
      and any("ride AHL buses" in r for r in apv["reasons"]))

# Same veteran, 400 days out: pride negotiable.
ev2 = make_entry(vet, "Sharks", days_ago=400)
apv2 = rs.coach_job_appeal(vet, TEAM_C, job_role="ahl_head",
                           carousel_entry=ev2, date_str="")
check("veteran, 400 days out, warmer to AHL",
      apv2["score"] > apv["score"])

# Elite coach, rebuild assistant: no. Contender assistant: yes.
elite = make_coach(age=55, reputation=90)
ee = make_entry(elite, "Sharks", days_ago=200)
ape_r = rs.coach_job_appeal(elite, TEAM_C, job_role="assistant",
                            carousel_entry=ee, date_str="",
                            team_context={"win_pct": 0.40})
ape_c = rs.coach_job_appeal(elite, TEAM_B, job_role="assistant",
                            carousel_entry=ee, date_str="",
                            team_context={"win_pct": 0.62})
check("elite (90) won't assist a rebuild",
      ape_r["score"] < 45
      and any("carry bags for a rebuild" in r for r in ape_r["reasons"]))
check("elite prefers contender staff over rebuild staff",
      ape_c["score"] > ape_r["score"])

# Recent Cup winner, fresh: not taking a demotion.
champ = make_coach(age=52, reputation=88, cup=True)
ec = make_entry(champ, "Sharks", days_ago=60)
apc = rs.coach_job_appeal(champ, TEAM_B, job_role="assistant",
                          carousel_entry=ec, date_str="",
                          team_context={"win_pct": 0.62})
check("recent Cup winner (60 days) shuns demotion",
      any("lifting the Cup" in r or "lifted the Cup" in r
          for r in apc["reasons"]))

# Long unemployment: hunger beats pride.
long_out = make_coach(age=48, reputation=65)
el = make_entry(long_out, "Sharks", days_ago=800)
apl = rs.coach_job_appeal(long_out, TEAM_C, job_role="assistant",
                          carousel_entry=el, date_str="",
                          team_context={"win_pct": 0.40})
short = make_entry(long_out, "Sharks", days_ago=60)
aps = rs.coach_job_appeal(long_out, TEAM_C, job_role="assistant",
                          carousel_entry=short, date_str="",
                          team_context={"win_pct": 0.40})
check("800 days out >> 60 days out for assistant willingness",
      apl["score"] > aps["score"] + 15)

# Developer ambition loves the AHL.
dev = make_coach(age=44, reputation=66, ambition="developer")
ed = make_entry(dev, "Sharks", days_ago=150)
apd = rs.coach_job_appeal(dev, TEAM_C, job_role="ahl_head",
                          carousel_entry=ed, date_str="")
check("developer ambition boosts AHL appeal",
      any("workshop" in r for r in apd["reasons"]))

# Cratered stock: desperate. Hot stock: picky.
cold = make_coach(age=47, reputation=64, stock=-50)
eh = make_entry(cold, "Sharks", days_ago=200)
ap_cold = rs.coach_job_appeal(cold, TEAM_C, job_role="assistant",
                              carousel_entry=eh, date_str="",
                              team_context={"win_pct": 0.45})
hot = make_coach(age=47, reputation=64, stock=70)
ap_hot = rs.coach_job_appeal(hot, TEAM_C, job_role="assistant",
                             carousel_entry=eh, date_str="",
                             team_context={"win_pct": 0.45})
check("cratered stock => more willing than hot stock",
      ap_cold["score"] > ap_hot["score"])

# No carousel entry (career assistant): step-down logic skipped, base intact.
outsider = make_coach(age=50, reputation=70)
apo = rs.coach_job_appeal(outsider, TEAM_B, job_role="assistant",
                          team_context={"win_pct": 0.62})
check("non-carousel candidate: base appeal, no step-down reasons",
      apo.get("refused") is False and apo["score"] > 0
      and apo.get("days_unemployed") == 0)

# ---------------------------------------------------------------- 4. helpers + AI wiring
# carousel_candidates_for_role finds willing coaches, excludes refusals.
dr.COACH_CAROUSEL.clear()
c_willing = make_coach(age=38, reputation=64)
e_willing = make_entry(c_willing, "Sharks", days_ago=400)  # cooled off
c_refuse = make_coach(age=49, reputation=70)
e_refuse = make_entry(c_refuse, "Sharks", days_ago=10)  # just fired by Sharks
dr.COACH_CAROUSEL.extend([e_willing, e_refuse])
try:
    cands = rs.carousel_candidates_for_role(
        TEAM_A, "assistant", date_str="")  # TEAM_A = Sharks (firing club)
    names = [c["coach"].full_name for c in cands]
    check("carousel helper excludes same-team demotion refusal",
          len(cands) == 1 and cands[0]["coach"] is c_willing)
    cands_b = rs.carousel_candidates_for_role(
        TEAM_B, "assistant", date_str="",
        team_context={"win_pct": 0.62})
    check("carousel helper includes both for a neutral team",
          len(cands_b) == 2)
    check("carousel helper sorted by appeal desc",
          cands_b[0]["appeal"]["score"] >= cands_b[-1]["appeal"]["score"])
finally:
    dr.COACH_CAROUSEL.clear()

# carousel_entry_for lookup.
dr.COACH_CAROUSEL.append(e_willing)
try:
    found = rs.carousel_entry_for(c_willing)
    check("carousel_entry_for finds by id", found is e_willing)
    check("carousel_entry_for None for outsider",
          rs.carousel_entry_for(make_coach()) is None)
    check("drop_from_carousel removes",
          rs.drop_from_carousel(c_willing) is True
          and len(dr.COACH_CAROUSEL) == 0)
finally:
    dr.COACH_CAROUSEL.clear()

# ensure_ahl_front_office hires a willing carousel coach before generating.
t_ahl = make_team("Wolves")
t_ahl.staff = []
c_ahl = make_coach(age=37, reputation=63)
e_ahl = make_entry(c_ahl, "Sharks", days_ago=150)
dr.COACH_CAROUSEL.append(e_ahl)
try:
    got = rs.ensure_ahl_front_office(t_ahl, league=None, date_str="")
    ahl_coaches = [s for s in t_ahl.staff
                   if "Head Coach" in str(getattr(getattr(s, "role", None),
                                                 "value", ""))
                   and str(getattr(s, "assignment", "")).lower() == "ahl"]
    check("AHL backfill hires willing carousel coach",
          got is True and len(ahl_coaches) == 1
          and ahl_coaches[0] is c_ahl)
    check("hired coach leaves the carousel",
          len(dr.COACH_CAROUSEL) == 0)
finally:
    dr.COACH_CAROUSEL.clear()

# Empty carousel => fresh face generated (old behavior preserved).
t_ahl2 = make_team("Bears")
t_ahl2.staff = []
got2 = rs.ensure_ahl_front_office(t_ahl2)
check("empty carousel => fresh face still generated", got2 is True
      and any("Head Coach" in str(getattr(getattr(s, "role", None),
                                         "value", ""))
              for s in t_ahl2.staff))

# ---------------------------------------------------------------- 5. never raises
for bad in [None, 0, "x", {}, []]:
    try:
        r = rs.coach_job_appeal(bad, bad, team_context=None,
                                job_role="bogus",
                                carousel_entry={"date": "not-a-date"},
                                rivalries="nope", date_str="also-bad")
        check(f"never raises on garbage ({type(bad).__name__})",
              isinstance(r, dict) and "score" in r)
    except Exception as ex:
        check(f"never raises on garbage ({type(bad).__name__}): {ex}", False)
try:
    rs.carousel_candidates_for_role(None, "assistant")
    rs.coach_rivalry_check(None, None)
    rs.drop_from_carousel(None)
    rs.ensure_ahl_front_office(None)
    check("helpers never raise on None", True)
except Exception as ex:
    check(f"helpers never raise on None: {ex}", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
