"""QA: explicit ELC offer / sign-prospect negotiation flow.

Covers: the signing-age term table, the ELC band, the prospect ask model
(pedigree + selfishness), the handshake (accept/counter/reject), the
shared finalizer (contract + rights consumption + assignment), the
auto-sign refactor, and wiring probes for the view/handler/menu.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import salary_cap_system as scs
from game_classes import League, Player, PlayerPosition, Team

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


def prospect(seed=1, age=19, overall_pick=0, draft_round=0, selfishness=50):
    random.seed(seed)
    p = Player("Kirby", "Dachau", age, PlayerPosition.CENTER)
    p.contract = None
    # Coherent birth_date: the CBA 9.2 Sept-15 age must match the stated
    # age (June birthday -> Sept-15 age == age exactly).
    p.birth_date = f"{2026 - age}-06-15"
    p.overall_pick = overall_pick
    p.draft_round = draft_round
    p.selfishness = selfishness
    p.rights_team = "Test Team"
    p.rights_expiry_year = 2030
    p.rights_type = "CHL"
    p.drafted_year = 2026
    return p


def league_with(team_name="Test Team"):
    lg = League(league_name="Test League")
    t = Team(team_name=team_name, city="Test", division="X", conference="Y")
    lg.teams = [t]
    return lg, t


# 1. Signing-age term table (3/2/1); 25+ is outside the Entry Level
# System (new CBA killed the old European 25-27 exception).
check("age 18 -> 3 yrs", scs.elc_years_for_age(18) == 3)
check("age 21 -> 3 yrs", scs.elc_years_for_age(21) == 3)
check("age 22 -> 2 yrs", scs.elc_years_for_age(22) == 2)
check("age 23 -> 2 yrs", scs.elc_years_for_age(23) == 2)
check("age 24 -> 1 yr", scs.elc_years_for_age(24) == 1)
check("age 25 -> 0 yrs (not ELC-eligible)", scs.elc_years_for_age(25) == 0)
check("age 30 -> 0 yrs (not ELC-eligible)", scs.elc_years_for_age(30) == 0)
check("age 25 band is 0 yrs", scs.elc_band(25)[2] == 0)

# 2. ELC band sanity.
floor, ceil, yrs = scs.elc_band(19)
check("band floor<=ceiling, 3 yrs", floor <= ceil and yrs == 3,
      f"{floor} {ceil} {yrs}")
floor2, ceil2, yrs2 = scs.elc_band(22)
check("age 22 band is 2 yrs", yrs2 == 2)

# 3. Ask model: pedigree anchors, selfishness moves it.
top = prospect(seed=11, overall_pick=3)
ask_top = scs.elc_prospect_ask(top)
check("top-5 pick asks the ceiling", ask_top["salary"] == ask_top["ceiling"],
      repr(ask_top["salary"]))
check("top-5 pick asks max perf bonus",
      ask_top["performance_bonus"] == scs.ELC_PERF_BONUS_MAX)
late = prospect(seed=12, overall_pick=200, draft_round=7)
ask_late = scs.elc_prospect_ask(late)
check("7th-rounder asks near the floor",
      ask_late["salary"] <= ask_late["floor"] + (ask_late["ceiling"] - ask_late["floor"]) * 0.45,
      repr(ask_late["salary"]))
check("7th-rounder asks no perf bonus", ask_late["performance_bonus"] == 0)
greedy = prospect(seed=13, overall_pick=40, draft_round=2, selfishness=95)
meek = prospect(seed=13, overall_pick=40, draft_round=2, selfishness=5)
check("selfishness pushes the ask up",
      scs.elc_prospect_ask(greedy)["salary"] > scs.elc_prospect_ask(meek)["salary"])
check("ask carries flavor", bool(ask_top["flavor"]))
check("ask salary inside band",
      ask_top["floor"] <= ask_top["salary"] <= ask_top["ceiling"])

# 4. Handshake: accept / counter / reject.
ask = scs.elc_prospect_ask(prospect(seed=21, overall_pick=10))
r = scs.elc_handshake(ask, ask["salary"], ask["signing_bonus"], ask["performance_bonus"])
check("meeting the ask is accepted", r["verdict"] == "accepted", repr(r))
above = scs.elc_handshake(ask, ask["ceiling"], 0, 0)
check("ceiling base alone draws a counter (bonuses are the haggle)",
      above["verdict"] == "counter", repr(above))
insult = scs.elc_handshake(ask, int(ask["salary"] * 0.7), 0, 0)
check("70% of ask base is rejected", insult["verdict"] == "rejected",
      repr(insult))
ask_val = scs.elc_offer_value(ask["salary"], ask["signing_bonus"], ask["performance_bonus"])
near = scs.elc_handshake(ask, int(ask_val * 0.95), 0, 0)
check("95% of ask draws a counter", near["verdict"] == "counter", repr(near))
check("counter names the ask salary",
      (near["counter"] or {}).get("salary") == ask["salary"], repr(near))
low = scs.elc_handshake(ask, ask["floor"], 0, 0)
low_verdict_ok = low["verdict"] in ("rejected", "counter", "accepted")
# floor vs a top-10 ask: must not accept outright
check("floor offer to a top-10 pick is not accepted",
      low["verdict"] != "accepted", repr(low))

# 5. Shared finalizer: contract + rights + assignment. The fixture deal
# is CBA-legal: $925k base + $90k signing bonus = $1.015M aggregate,
# under the $1.025M 9.3(a) max; $500k Schedule-A perf bonus is capped
# separately. A $1M base + $100k SB ($1.1M aggregate) must be REFUSED.
lg, t = league_with()
p = prospect(seed=31, age=19, overall_pick=15)
t.prospects.append(p)
ok = lg.finalize_elc_signing(t, p, 925_000, 3, 90_000, 500_000)
check("finalize succeeds", ok)
c = p.contract
check("contract has negotiated terms",
      c is not None and c.salary == 925_000 and c.years_remaining == 3,
      repr(getattr(c, "salary", None)))
check("contract carries bonuses",
      getattr(c, "signing_bonus", 0) == 90_000
      and getattr(c, "performance_bonus", 0) == 500_000)
check("contract is two-way", bool(getattr(c, "two_way", False)))
check("contract is stamped entry-level", bool(getattr(c, "entry_level", False)))
check("slide state stamped",
      getattr(p, "elc_signing_sept15_age", None) == 19
      and getattr(p, "elc_slides_used", None) == 0
      and getattr(p, "elc_seasons_completed", None) == 0)
check("draft history preserved", getattr(p, "drafted_by", "") == "Test Team"
      and getattr(p, "elc_signed_season", None) == 2026)
check("rights consumed",
      p.rights_team == "" and p.drafted_year == 0 and p.rights_expiry_year == 0)
check("assigned somewhere real", p.playing_where in ("AHL", "Junior")
      or "Junior" in str(p.playing_where), repr(p.playing_where))
check("minor salary capped to draft-year max",
      (c.ahl_salary or 0) <= scs.elc_minor_salary_max(2026),
      repr(getattr(c, "ahl_salary", None)))

# 5b. Finalizer guards: wrong team / already signed.
lg2, t2 = league_with("Other Team")
p2 = prospect(seed=32)
p2.rights_team = "Test Team"
t2.prospects.append(p2)
check("finalize refuses non-rights-holder",
      lg2.finalize_elc_signing(t2, p2, 900_000, 3) is False)
p3 = prospect(seed=33)
p3.contract = "signed"
t.prospects.append(p3)
check("finalize refuses already-signed",
      lg.finalize_elc_signing(t, p3, 900_000, 3) is False)

# 5c. Finalizer enforces the CBA caps (fail closed).
p5 = prospect(seed=35, age=19, overall_pick=40)
t.prospects.append(p5)
check("finalize refuses over-aggregate deal (1M base + 100k SB > 1.025M)",
      lg.finalize_elc_signing(t, p5, 1_000_000, 3, 100_000, 0) is False)
check("refused prospect is untouched",
      p5.contract is None and p5.rights_team == "Test Team")
p6 = prospect(seed=36, age=26)
t.prospects.append(p6)
check("finalize refuses 25+ (not ELC-eligible)",
      lg.finalize_elc_signing(t, p6, 900_000, 1) is False)
p7 = prospect(seed=37, age=22, overall_pick=40)
t.prospects.append(p7)
ok7 = lg.finalize_elc_signing(t, p7, 900_000, 3)
check("forged 3-yr term for a 22yo is corrected to 2",
      ok7 and p7.contract.years_remaining == 2,
      repr(getattr(getattr(p7, "contract", None), "years_remaining", None)))

# 6. Auto-sign refactor still works (delegates to the finalizer).
lg3, t3 = league_with()
p4 = prospect(seed=34, age=20, overall_pick=50, draft_round=2)
t3.prospects.append(p4)
ok4 = lg3.sign_drafted_prospect(t3, p4)
check("auto-sign still signs", ok4 and p4.contract is not None)
check("auto-sign consumes rights", p4.rights_team == "" and p4.drafted_year == 0)

# 7. Wiring probes.
here = os.path.dirname(os.path.abspath(__file__))
src_win = open(os.path.join(here, "windows.py")).read()
src_main = open(os.path.join(here, "main.py")).read()
src_scs = open(os.path.join(here, "salary_cap_system.py")).read()
check("view has ELC mode", "is_elc" in src_win
      and "Entry-Level Contract" in src_win)
check("view has ELC submit path", "_submit_elc_offer" in src_win)
check("view shows agent ask in ELC context", "_refresh_elc_context" in src_win)
check("prospects menu offers ELC", "Offer ELC" in src_win)
check("handler exists", "def handle_elc_offer" in src_main)
check("handler finalizes via league", "finalize_elc_signing" in src_main)
check("opener passes is_elc", "is_elc=is_elc" in src_main)
check("band/ask/handshake helpers exist",
      all(s in src_scs for s in ("def elc_band", "def elc_prospect_ask",
                                 "def elc_handshake", "def elc_years_for_age")))

# 8. Promotion gate: no silent auto-sign, routes into contract talks.
check("promotion offers contract talks, not silent sign",
      "Open contract talks now?" in src_win and "is_elc=True" in src_win)
check("move_player no longer auto-signs",
      "sign_drafted_prospect" not in src_win)
check("bulk promote pre-filters unsigned prospects",
      "Unsigned prospects" in src_win and "Offer ELC" in src_win)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
