# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: AI extension planning -- franchise pieces, forward book, GM dynamics.

Run: python3 qa_ai_extension_planning.py
"""
import sys
from datetime import date

sys.path.insert(0, ".")
import ai_extension_planning as aep

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


class C:
    def __init__(self, salary, yrs, elc=False):
        self.salary = salary
        self.years_remaining = yrs
        self.entry_level = elc


class P:
    def __init__(self, name, ovr, age, salary, yrs, grade="C", rnd=0,
                 elc=False, drafted_by="", happiness=70, loyalty=60):
        self.full_name = name
        self._ovr = ovr
        self.age = age
        self.contract = C(salary, yrs, elc)
        self.potential_grade = grade
        self.true_potential_grade = ""
        self.draft_round = rnd
        self.drafted_by = drafted_by
        self.rights_team = drafted_by
        self.happiness = happiness
        self.loyalty = loyalty

    def overall_rating(self):
        return self._ovr


class T:
    def __init__(self, name, roster):
        self.team_name = name
        self.roster = roster


class G:
    def __init__(self, team_name, patience=0.5, loyalty=0.5, aggression=0.5,
                 exp=10, tenure=2, rep=50):
        self.team_name = team_name
        self.patience = patience
        self.loyalty = loyalty
        self.aggression = aggression
        self.experience_years = exp
        self.tenure_years = tenure
        self.reputation = rep


class S:
    def __init__(self, priority="MAINTAIN"):
        self.priority = type("PV", (), {"value": priority})()


def ask_fn(p):
    # Simple stand-in for the shared ask machinery: ovr-driven.
    return {95: 15_000_000, 88: 9_500_000, 80: 5_500_000,
            74: 3_200_000, 70: 1_500_000}.get(p._ovr, 2_000_000)


STAR = P("Star C", 95, 27, 11_000_000, 1, grade="A", rnd=1, drafted_by="X")
KID = P("Kid W", 74, 20, 925_000, 1, grade="B", rnd=1, elc=True, drafted_by="X")
GRINDER = P("Grinder", 80, 31, 4_000_000, 1, grade="C", rnd=4)
DEPTH = P("Depth D", 70, 29, 1_200_000, 1, grade="D", rnd=6)
DUE_NEXT = P("DueNext C", 88, 26, 7_000_000, 2, grade="A", rnd=1, drafted_by="X")
gm = G("X")
strat = S()


def test_piece_identification():
    print("== piece identification ==")
    check("95-ovr star is a piece", aep.is_franchise_piece(STAR, gm, strat))
    check("20yo B-potential 1st-rounder at 74 ovr is a piece (face value be damned)",
          aep.is_franchise_piece(KID, gm, strat),
          f"score={aep.franchise_score(KID, gm, strat):.0f}")
    check("31yo 80-ovr grinder is not a piece",
          not aep.is_franchise_piece(GRINDER, gm, strat))
    check("70-ovr depth is not a piece",
          not aep.is_franchise_piece(DEPTH, gm, strat))
    # Rebuilder demotes the veteran but keeps the kid
    rs = S("REBUILD")
    check("rebuilder still keeps the kid",
          aep.is_franchise_piece(KID, gm, rs))
    vet = P("Vet W", 84, 33, 6_000_000, 1, grade="C", rnd=2)
    check("rebuilder drops the 33yo 84 (asset, not core)",
          not aep.is_franchise_piece(vet, gm, rs),
          f"score={aep.franchise_score(vet, gm, rs):.0f}")


def test_gm_subjectivity():
    print("== GM subjectivity ==")
    loyal = G("X", loyalty=0.95)
    cold = G("X", loyalty=0.05)
    s_loyal = aep.franchise_score(KID, loyal, strat)
    s_cold = aep.franchise_score(KID, cold, strat)
    check("loyal GM values the homegrown kid more", s_loyal > s_cold,
          f"{s_loyal:.0f} vs {s_cold:.0f}")
    patient = G("X", patience=0.95)
    win_now = G("X", patience=0.05, aggression=0.95)
    check("patient GM bets bigger on the future piece",
          aep.franchise_score(KID, patient, strat) >
          aep.franchise_score(KID, win_now, strat))


def test_projection_ability():
    print("== projection vs GM ability ==")
    good = G("X", exp=18, tenure=8, rep=85)
    bad = G("X", exp=2, tenure=1, rep=30)
    check("good GM ability reads high", aep.gm_ability01(good) > 0.6,
          f"{aep.gm_ability01(good):.2f}")
    check("bad GM ability reads low", aep.gm_ability01(bad) < 0.4,
          f"{aep.gm_ability01(bad):.2f}")
    star_true = ask_fn(STAR)
    pg, pb = (aep.project_extension_cost(STAR, ask_fn, good),
              aep.project_extension_cost(STAR, ask_fn, bad))
    check("good GM projects the star ask within 3%",
          abs(pg - star_true) / star_true < 0.03, f"{pg:,} vs {star_true:,}")
    check("bad GM underestimates the star ask (surprise coming)",
          pb < star_true, f"{pb:,} vs {star_true:,}")
    dg, db = (aep.project_extension_cost(DEPTH, ask_fn, good),
              aep.project_extension_cost(DEPTH, ask_fn, bad))
    check("bad GM overrates depth (overpay pipeline)", db > dg,
          f"{db:,} vs {dg:,}")


def test_forward_book():
    print("== forward book ==")
    roster = [STAR, KID, GRINDER, DEPTH, DUE_NEXT]
    team = T("X", roster)
    charge = sum(p.contract.salary for p in roster)
    ep = aep.plan(team, identity=gm, strategy=strat, ask_fn=ask_fn,
                  cap_ceiling=104_000_000, current_charge=charge,
                  current_date=date(2026, 10, 15))
    names = [p.full_name for (p, s) in ep.pieces]
    check("star + kid + due-next are pieces", set(names) == {
          "Star C", "Kid W", "DueNext C"}, str(names))
    check("reservation covers the raises (star 4M + due-next 2.5M + kid)",
          ep.reserved >= 6_500_000, f"${ep.reserved:,}")
    check("due-next-year piece reserves money but isn't in the queue",
          all(q["player"].full_name != "DueNext C" for q in ep.queue))
    qnames = [q["player"].full_name for q in ep.queue]
    check("queue is piece-first", qnames[0] in ("Star C", "Kid W"), str(qnames))
    check("queue holds eligible only (yr 0/1)", all(
        q["years_remaining"] in (0, 1) for q in ep.queue))
    # The Muck scenario: $15M man due next year eats the depth budget
    big = P("Franchise C", 96, 26, 9_000_000, 2, grade="A", rnd=1,
            drafted_by="X")
    ask_big = lambda p: 15_500_000 if p is big else ask_fn(p)  # noqa: E731
    team2 = T("X", [big, GRINDER, DEPTH])
    charge2 = sum(p.contract.salary for p in team2.roster)
    ep2 = aep.plan(team2, identity=gm, strategy=strat, ask_fn=ask_big,
                   cap_ceiling=104_000_000, current_charge=charge2,
                   current_date=date(2026, 10, 15))
    check("$15M man reserves ~$6.5M raise", ep2.reserved >= 6_000_000,
          f"${ep2.reserved:,}")
    print(f"       discretionary with $15M man due: ${ep2.discretionary:,}")


def test_crunch_and_personality():
    print("== crunch + personality ==")
    # Cap-strapped club: core doesn't fit -> pieces only
    s1 = P("Star C", 95, 27, 11_000_000, 1, grade="A", rnd=1, drafted_by="X")
    s2 = P("Star W", 93, 28, 10_500_000, 1, grade="A", rnd=1, drafted_by="X")
    ask_crunch = lambda p: {95: 15_000_000, 93: 15_000_000}.get(  # noqa: E731
        p._ovr, 2_000_000)
    team = T("X", [s1, s2, DEPTH])
    charge = 103_000_000  # nearly no room; raises push it over
    ep = aep.plan(team, identity=gm, strategy=strat, ask_fn=ask_crunch,
                  cap_ceiling=104_000_000, current_charge=charge,
                  current_date=date(2026, 10, 15))
    check("crunch flagged when the core doesn't fit", ep.crunch,
          f"disc=${ep.discretionary:,}")
    # Aggressive GM pays the sweetener to lock the piece early
    aggro = G("X", aggression=0.9)
    ep_a = aep.plan(T("X", [STAR]), identity=aggro, strategy=strat,
                    ask_fn=ask_fn, cap_ceiling=104_000_000,
                    current_charge=11_000_000,
                    current_date=date(2026, 10, 15))
    q = ep_a.queue[0]
    check("aggressive GM offers above projection to lock the piece",
          q["max_offer"] > q["projected"], f"{q['max_offer']:,} vs {q['projected']:,}")
    check("piece priority tops depth priority",
          q["priority"] > 0.6, f"{q['priority']}")


def test_parity_rulebook():
    print("== parity: one rulebook ==")
    import transaction_windows as tw
    for yrs, expected in ((0, True), (1, True), (2, False)):
        p = P("T", 80, 27, 3_000_000, yrs)
        ok, _why = tw.check_window("extension", date(2026, 10, 15),
                                   ctx={"player": p})
        check(f"user gate: years_remaining={yrs} -> {expected}", ok == expected)
    # The AI evaluator must use the same function (no local copy)
    import ai_team_management as atm
    import inspect
    src_e = inspect.getsource(atm.AITeamManager._evaluate_contract_extensions)
    src_x = inspect.getsource(atm.AITeamManager._execute_contract_extension)
    check("evaluator calls transaction_windows.check_window",
          "transaction_windows" in src_e and "check_window" in src_e)
    check("executor calls transaction_windows.check_window",
          "transaction_windows" in src_x and "check_window" in src_x)
    check("no local years_remaining==1 copies remain",
          "years_remaining\", 0) or 0) != 1" not in src_e
          and "years_remaining\", 0) or 0) != 1" not in src_x)


def test_integration_wiring():
    print("== integration wiring ==")
    import ai_team_management as atm
    import inspect
    src_p = inspect.getsource(atm.AITeamManager.process_daily_decisions)
    check("pass builds the forward book", "_build_extension_plan" in src_p)
    check("manager stores per-team plans", "_ext_plans" in src_p)
    src_f = inspect.getsource(atm.AITeamManager._evaluate_free_agency)
    check("UFA budget subtracts reserved core money", "reserved" in src_f)
    check("UFA skipped in a crunch", "crunch" in src_f)


if __name__ == "__main__":
    test_piece_identification()
    test_gm_subjectivity()
    test_projection_ability()
    test_forward_book()
    test_crunch_and_personality()
    test_parity_rulebook()
    test_integration_wiring()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
