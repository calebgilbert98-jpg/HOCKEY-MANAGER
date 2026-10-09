"""QA: NHL assistant coach AI hiring + staff-market UI wiring (Muck 2026-10-02).

Covers:
  1. Vacancy fill: AI hires when below the 2-assistant target; no-op when full.
  2. Carousel first: a willing ex-head coach is hired as assistant and
     dropped from the carousel (role re-stamped ASSISTANT_COACH).
  3. Refusal gates respected: a just-fired HC refuses the firing club's
     assistant chair (same-team demotion insult) -- the AI skips him.
  4. Fit over fame: FA-pool scoring prefers philosophy alignment with the
     current head coach over raw reputation.
  5. House cleaning: a new head coach may release his worst-fit assistant
     (p=1 forced) and the chair is refilled.
  6. Headline verb: "hired_assistant" renders "named assistant coach".
  7. Never raises on garbage input.
  8. UI wiring present: staff-market flags carousel members; the user hire
     path drops carousel membership.
"""
import sys
sys.path.insert(0, '/tmp/wt-asst')

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

print("== Assistant coach AI hiring + UI ==")

from types import SimpleNamespace as SN
from datetime import date, timedelta
from game_classes import Staff, StaffRole
import dressing_room as dr
import reputation_system as rs

# ---------------------------------------------------------------- helpers
def make_staff(role=StaffRole.ASSISTANT_COACH, age=45, reputation=70,
               philosophy="", assignment="nhl"):
    s = Staff(first_name="Test", last_name="Staffer", role=role, age=age,
              reputation=reputation)
    s.coaching_philosophy = philosophy
    s.assignment = assignment
    s.current_club = ""
    s.years_with_team = 0
    return s

def make_team(name, ahl_coach=True):
    t = SN(team_name=name, staff=[], roster=[], head_coach=None)
    if ahl_coach:
        # Isolate assistant-chair tests from the AHL front-office backfill
        # (ensure_ahl_front_office hires willing carousel coaches as AHL
        # head coach -- legitimate ecosystem behavior, but noise here).
        ahl_hc = make_staff(role=StaffRole.HEAD_COACH, philosophy="balanced",
                            assignment="ahl")
        t.staff.append(ahl_hc)
    return t

def make_league(teams):
    return SN(teams=teams, free_agent_staff=[], rivalries=[])

def carousel_entry(coach, firing_club, days_ago, reason="fired"):
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    return {"coach": coach, "name": coach.full_name, "style": "balanced",
            "hot_seat": 70 if reason == "fired" else 40,
            "bonds": [], "grudges": [],
            "past_clubs": [firing_club] if firing_club else [],
            "reason": reason, "date": d,
            "firing_club": firing_club}

def reset_carousel():
    dr.COACH_CAROUSEL[:] = []

# ------------------------------------------------- 1. vacancy fill / no-op
reset_carousel()
team = make_team("Sharks")
league = make_league([team])
# FA pool: one career assistant available.
fa = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=65,
                philosophy="defensive")
league.free_agent_staff.append(fa)
hc = make_staff(role=StaffRole.HEAD_COACH, philosophy="defensive")
team.staff.append(hc)
team.head_coach = hc

hired = dr.ai_hire_assistant_coach(team, league=league, date_str="2026-10-02")
check("vacancy filled from FA pool", hired is fa)
check("hired lands on team.staff as NHL assistant",
      hired in team.staff
      and hired.role == StaffRole.ASSISTANT_COACH
      and hired.assignment == "nhl")
check("hired leaves the FA pool", fa not in league.free_agent_staff)

# Full bench -> no-op.
a2 = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=60)
team.staff.append(a2)
check("no-op when bench is full (2 assistants)",
      dr.ai_hire_assistant_coach(team, league=league,
                                 date_str="2026-10-02") is None)

# ------------------------------------------------- 2. carousel first
reset_carousel()
team2 = make_team("Kings")
league2 = make_league([team2])
hc2 = make_staff(role=StaffRole.HEAD_COACH, philosophy="offensive")
team2.staff.append(hc2)
team2.head_coach = hc2
# Willing ex-HC (fired 200 days ago elsewhere -> insult window passed).
exhc = make_staff(role=StaffRole.HEAD_COACH, age=42, reputation=78,
                  philosophy="offensive")
exhc.ambition = "climb"
exhc.stock = 0
exhc.controversy = 20
dr.COACH_CAROUSEL.append(carousel_entry(exhc, "Ducks", 200))
# Also a FA-pool assistant, so we can tell carousel won.
fa2 = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=90,
                 philosophy="offensive")
league2.free_agent_staff.append(fa2)
league2.free_agent_staff.append(exhc)  # fired coaches sit in the pool too

hired2 = dr.ai_hire_assistant_coach(team2, league=league2,
                                    date_str="2026-10-02")
check("carousel ex-HC preferred over FA pool", hired2 is exhc)
check("ex-HC re-stamped as assistant",
      exhc.role == StaffRole.ASSISTANT_COACH and exhc.assignment == "nhl")
check("hired ex-HC dropped from carousel",
      rs.carousel_entry_for(exhc) is None)

# --------------------------------- 3. same-team demotion insult respected
reset_carousel()
team3 = make_team("Ducks")
league3 = make_league([team3])
hc3 = make_staff(role=StaffRole.HEAD_COACH, philosophy="balanced")
team3.staff.append(hc3)
team3.head_coach = hc3
fresh = make_staff(role=StaffRole.HEAD_COACH, age=44, reputation=80,
                   philosophy="balanced")
fresh.ambition = "climb"
fresh.stock = 0
fresh.controversy = 20
dr.COACH_CAROUSEL.append(carousel_entry(fresh, "Ducks", 10))  # just fired HERE
fa3 = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=62,
                 philosophy="balanced")
league3.free_agent_staff.append(fa3)
league3.free_agent_staff.append(fresh)

hired3 = dr.ai_hire_assistant_coach(team3, league=league3,
                                    date_str="2026-10-02")
check("just-fired HC skipped for his own club's assistant chair",
      hired3 is fa3)
check("refused ex-HC stays on carousel",
      rs.carousel_entry_for(fresh) is not None)

# ------------------------------------------------- 4. fit over fame
reset_carousel()
team4 = make_team("Flames")
league4 = make_league([team4])
hc4 = make_staff(role=StaffRole.HEAD_COACH, philosophy="defensive")
team4.staff.append(hc4)
team4.head_coach = hc4
famous = make_staff(role=StaffRole.ASSISTANT_COACH, age=55, reputation=95,
                    philosophy="offensive")   # big name, wrong system
fit = make_staff(role=StaffRole.ASSISTANT_COACH, age=40, reputation=68,
                 philosophy="defensive")      # lesser name, right system
s_famous = dr._assistant_fit_score(famous, hc4)
s_fit = dr._assistant_fit_score(fit, hc4)
check("fit scoring prefers system fit over raw reputation", s_fit > s_famous)

# ------------------------------------------------- 5. house cleaning
reset_carousel()
team5 = make_team("Oilers")
league5 = make_league([team5])
new_hc = make_staff(role=StaffRole.HEAD_COACH, philosophy="offensive")
team5.staff.append(new_hc)
team5.head_coach = new_hc
good_fit = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=70,
                      philosophy="offensive")
bad_fit = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=70,
                     philosophy="defensive")
team5.staff.extend([good_fit, bad_fit])
repl = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=66,
                  philosophy="offensive")
league5.free_agent_staff.append(repl)

# Run several times: the released coach must NEVER be re-hired as his
# own replacement (regression for the top-3 random pick).
_rehire_bug = False
for _ in range(10):
    t = make_team("OilersX")
    l5 = make_league([t])
    nhc = make_staff(role=StaffRole.HEAD_COACH, philosophy="offensive")
    t.staff.append(nhc)
    t.head_coach = nhc
    bf = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=70,
                    philosophy="defensive")
    gf = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=70,
                    philosophy="offensive")
    t.staff.extend([gf, bf])
    rp = make_staff(role=StaffRole.ASSISTANT_COACH, reputation=66,
                    philosophy="offensive")
    l5.free_agent_staff.append(rp)
    dr._maybe_house_clean_assistants(t, nhc, l5, "2026-10-02", p=1.0)
    if bf in t.staff:
        _rehire_bug = True
check("released coach never re-hired as own replacement (10x)",
      not _rehire_bug)

dr._maybe_house_clean_assistants(team5, new_hc, league5, "2026-10-02", p=1.0)
assts = dr._nhl_assistants(team5)
check("worst-fit assistant released to FA pool",
      bad_fit not in team5.staff and bad_fit in league5.free_agent_staff)
check("good-fit assistant kept", good_fit in team5.staff)
check("vacancy refilled to target", len(assts) == 2)
check("replacement hired from pool", repl in team5.staff)

# ------------------------------------------------- 6. headline verb
import headlines as hl
msg = hl._coaching_change_headline(date(2026, 10, 2), "Sharks", "Jane Doe",
                                   change="hired_assistant")
check("assistant headline verb",
      msg is not None and "named assistant coach" in msg.subject)
msg2 = hl._coaching_change_headline(date(2026, 10, 2), "Sharks", "John Doe",
                                    change="hired")
check("head-coach headline verb unchanged",
      msg2 is not None and "named head coach" in msg2.subject)

# ------------------------------------------------- 7. never raises
for bad in (None, "garbage", 123, SN()):
    try:
        dr.ai_hire_assistant_coach(bad)
        dr.ai_hire_assistant_coach(bad, league=bad, date_str=bad)
        dr._maybe_house_clean_assistants(bad, bad, bad, bad)
        dr._nhl_assistants(bad)
        dr._assistant_fit_score(bad, bad)
        ok = True
    except Exception:
        ok = False
    check(f"never raises on {type(bad).__name__}", ok)

# --------------------------------- 8. UI wiring present (source checks)
import pathlib
_w = pathlib.Path("/tmp/wt-asst/windows.py").read_text()
_m = pathlib.Path("/tmp/wt-asst/main.py").read_text()
check("staff market flags carousel members",
      "Ex-HC carousel" in _w and "carousel_entry_for" in _w)
check("user hire path drops carousel membership",
      "drop_from_carousel" in _m)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
