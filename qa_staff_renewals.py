# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: D5 follow-up -- expired staff get a renewal offer BEFORE the pool.

User club: expired deals are HELD (not auto-released) and arrive as one
interactive inbox message (action_type="staff_renewal"). Accept ->
fresh deal; decline/ignore -> free-agent pool. AI clubs auto-decide via
ai_renew_staff_decision (re-sign the valued, walk the rest). A walked
head coach triggers the in-house promote fallback on every path.

Run: python3 qa_staff_renewals.py  (from the worktree root; headless)
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as gc
from game_classes import League, Staff, StaffRole, Team
import staff_renewals as sr

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def mkstaff(first, last, role, career_rep=0, years=1, rep=60):
    s = Staff(first, last, role)
    s.career_reputation = career_rep
    s.reputation = rep
    s.contract_years = years
    s.age = 50
    s.years_with_team = 3
    s.salary = 200000
    return s


def mkteams(user=True):
    league = League("NHL")
    league.season_year = 2028
    league.free_agent_staff = []
    ut = Team("Users", "Testville", "Atlantic", "Eastern", "NHL", "GM", None)
    if user:
        league.user_team = ut
    league.teams = [ut]
    return league, ut


def add_ai_team(league, staffers):
    t = Team("Bots", "Aitown", "Atlantic", "Eastern", "NHL", "GM", None)
    t.staff = list(staffers)
    league.teams.append(t)
    return t


class FakeApp:
    def __init__(self):
        self.sent = []

    def send_email_to_user(self, msg):
        self.sent.append(msg)


random.seed(7)

# --- 1. user expired staffer: held, NOT auto-released -------------------------
lg, ut = mkteams()
ast = mkstaff("Hold", "Me", StaffRole.ASSISTANT_COACH, career_rep=75, years=1)
ut.staff = [ast]
news = gc.tick_staff_contracts(lg)
check("user expired staffer held employed (not auto-released)",
      ast in ut.staff and ast not in lg.free_agent_staff,
      f"staff={len(ut.staff)} pool={len(lg.free_agent_staff)}")
check("offer stashed for the inbox",
      len(getattr(lg, "staff_renewal_offers", []) or []) == 1)
check("held offer produces no news line (the message is the notice)",
      news == [], f"news={news}")

# --- 2. inbox renewal item queued ---------------------------------------------
app = FakeApp()
n = sr.queue_user_renewal_message(lg, ut, app)
check("renewal message queued", n == 1 and len(app.sent) == 1, f"n={n}")
msg = app.sent[0]
check("message is an interactive staff_renewal item",
      getattr(msg, "action_type", None) == "staff_renewal"
      and bool(getattr(msg, "requires_response", False)))
check("message carries the offer card",
      len((getattr(msg, "action_data", None) or {}).get("offers", [])) == 1)

# --- 3. accept: fresh deal, stays employed ------------------------------------
ok, lines = sr.apply_renewal_decision(lg, ast.id, 2)
check("accept keeps him employed with fresh contract_years",
      ok and ast in ut.staff and ast.contract_years == 2
      and ast not in lg.free_agent_staff,
      f"ok={ok} years={ast.contract_years}")
check("accepted offer leaves the stash",
      len(getattr(lg, "staff_renewal_offers", []) or []) == 0)

# --- 4. decline: walks to the pool --------------------------------------------
lg2, ut2 = mkteams()
sct = mkstaff("Walk", "Away", StaffRole.AMATEUR_SCOUT, career_rep=30, years=1)
ut2.staff = [sct]
gc.tick_staff_contracts(lg2)
ok2, lines2 = sr.apply_renewal_decision(lg2, sct.id, None)
check("decline releases to free_agent_staff",
      ok2 and sct in lg2.free_agent_staff and sct not in ut2.staff,
      f"ok={ok2} lines={lines2}")

# --- 5. ignore: resolve_pending_renewals walks him, closes message -----------
lg3, ut3 = mkteams()
ign = mkstaff("Ig", "Nore", StaffRole.SKILLS_COACH, career_rep=40, years=1)
ut3.staff = [ign]
gc.tick_staff_contracts(lg3)
app3 = FakeApp()
sr.queue_user_renewal_message(lg3, ut3, app3)
ut3.inbox = SimpleNamespace(messages=list(app3.sent))
rnews = sr.resolve_pending_renewals(lg3)
check("ignored offer walks to the pool",
      ign in lg3.free_agent_staff and ign not in ut3.staff)
check("ignore produces a walk news line",
      any("no renewal agreed" in str(x) for x in rnews), f"news={rnews}")
check("ignore closes the inbox message",
      all(getattr(m, "action_done", False) for m in ut3.inbox.messages))

# --- 6. AI: re-signs a high-rep staffer ---------------------------------------
lg4, ut4 = mkteams()
ai_hc = mkstaff("Val", "Ued", StaffRole.HEAD_COACH, career_rep=85, years=1)
add_ai_team(lg4, [ai_hc])
news4 = gc.tick_staff_contracts(lg4)
check("AI re-signs valued head coach (fresh 3-year deal)",
      ai_hc.contract_years == 3 and ai_hc not in lg4.free_agent_staff,
      f"years={ai_hc.contract_years}")
check("AI re-sign is reported",
      any("re-signed Val Ued" in str(x) for x in news4), f"news={news4}")

# --- 7. AI: releases a low-rep staffer ----------------------------------------
ai_scout = mkstaff("Not", "Valued", StaffRole.AMATEUR_SCOUT,
                   career_rep=20, years=1)
ait = add_ai_team(lg4, [ai_scout])
news4b = gc.tick_staff_contracts(lg4)
check("AI releases low-rep staffer to the pool",
      ai_scout in lg4.free_agent_staff and ai_scout not in ait.staff)

# --- 8. AI: struggling head coach walks (the rep floor) -----------------------
lg5, _ut5 = mkteams()
ai_hc2 = mkstaff("Strug", "Gling", StaffRole.HEAD_COACH, career_rep=50,
                 years=1, rep=45)
ai_ast = mkstaff("Next", "Up", StaffRole.ASSISTANT_COACH, career_rep=30,
                 years=3, rep=55)
ait5 = add_ai_team(lg5, [ai_hc2, ai_ast])
gc.tick_staff_contracts(lg5)
check("AI walks a sub-60 head coach",
      ai_hc2 in lg5.free_agent_staff)
check("walked AI head coach triggers in-house promote",
      ai_ast.role == StaffRole.HEAD_COACH and ai_ast.contract_years == 3,
      f"role={ai_ast.role} years={ai_ast.contract_years}")

# --- 9. user lets head coach walk -> in-house promote fallback -----------------
lg6, ut6 = mkteams()
uhc = mkstaff("Bench", "Boss", StaffRole.HEAD_COACH, career_rep=80, years=1)
uast = mkstaff("Heir", "Apparent", StaffRole.ASSISTANT_COACH,
               career_rep=60, years=1, rep=62)
uast2 = mkstaff("Second", "Best", StaffRole.ASSISTANT_COACH,
                career_rep=55, years=3, rep=50)
ut6.staff = [uhc, uast, uast2]
gc.tick_staff_contracts(lg6)
ok6, lines6 = sr.apply_renewal_decision(lg6, uhc.id, None)
check("walked user head coach reaches the pool",
      ok6 and uhc in lg6.free_agent_staff and uhc not in ut6.staff)
check("best in-house assistant promoted (fresh 3-year HC deal)",
      uast.role == StaffRole.HEAD_COACH and uast.contract_years == 3,
      f"role={uast.role} years={uast.contract_years}")
check("promote reported in the decision news",
      any("promoted Heir Apparent" in str(x) for x in lines6),
      f"lines={lines6}")
check("promoted assistant's own pending offer is moot",
      all((o or {}).get("staff") is not uast
          for o in (getattr(lg6, "staff_renewal_offers", None) or [])))

# --- 10. tick backstop: stale offers resolve as walks --------------------------
lg7, ut7 = mkteams()
stale = mkstaff("St", "Ale", StaffRole.GOALIE_COACH, career_rep=90, years=0)
ut7.staff = [stale]
lg7.staff_renewal_offers = [{"team": ut7, "staff": stale}]
news7 = gc.tick_staff_contracts(lg7)
check("stale pending offer resolved by the tick backstop",
      stale in lg7.free_agent_staff and stale not in ut7.staff
      and not (getattr(lg7, "staff_renewal_offers", None) or []))

# --- 11. ai_renew_staff_decision boundaries ------------------------------------
d = gc.ai_renew_staff_decision
hc60 = mkstaff("A", "B", StaffRole.HEAD_COACH, career_rep=60)
hc59 = mkstaff("A", "B", StaffRole.HEAD_COACH, career_rep=59)
sc70 = mkstaff("A", "B", StaffRole.AMATEUR_SCOUT, career_rep=70)
sc69 = mkstaff("A", "B", StaffRole.AMATEUR_SCOUT, career_rep=69)
check("AI rule: HC rep 60 re-signs, 59 walks; scout 70 re-signs, 69 walks",
      d(hc60, None) and not d(hc59, None)
      and d(sc70, None) and not d(sc69, None))

# --- 12. renewal year options ---------------------------------------------------
ok12, _ = sr.apply_renewal_decision(lg, ast.id, 3)  # already decided
check("double decision on a resolved offer is a clean no-op",
      ok12 is False)
check("renewal terms constants",
      sr.RENEWAL_YEAR_OPTIONS == (1, 2, 3)
      and sr.RENEWAL_DEFAULT_YEARS == 2)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
