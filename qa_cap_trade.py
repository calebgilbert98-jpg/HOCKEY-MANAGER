# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: cap infrastructure -- modern numbers, central accounting, trade sheds,
dead-cap seeding/clearing, save/load, old-save safety."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
random.seed(7)
import game_classes as g
from game_classes import PlayerPosition

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name, cap=104_000_000):
    t = g.Team(name, "T", "D", "C"); t.salary_cap = cap; return t

def mkplayer(salary):
    p = g.Player(first_name="A", last_name="B", age=27,
                 primary_position=PlayerPosition.CENTER)
    p.contract.salary = salary
    return p

# -- 1. modern cap numbers ---------------------------------------------------
from salary_cap_system import SalaryCapSystem, DEFAULT_CAP
check("default cap is $104M (2026-27)", DEFAULT_CAP == 104_000_000)
check("Team default salary_cap $104M",
      g.Team("X", "X", "D", "C").salary_cap == 104_000_000)
c = SalaryCapSystem(seed=3)
check("announced 2027-28 cap $113.5M", c.advance_cap_year(2027) == 113_500_000)

# -- 2. central cap accounting ------------------------------------------------
import salary_cap_system as scs
t = mkteam("T")
t.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M roster
t.buyout_cap_hits = {2026: 1_000_000}
t.real_buyout_cap = 500_000
t.real_retained_salary = 250_000
t.real_bonus_overage = 125_000
bd = scs.cap_breakdown(t)
check("breakdown roster $100M", bd["roster"] == 100_000_000)
check("breakdown dead cap $1.875M", bd["dead_cap"] == 1_875_000)
check("breakdown total $101.875M", bd["total"] == 101_875_000)
check("breakdown space $2.125M", bd["space"] == 2_125_000)
check("not over cap", bd["over_cap"] is False)
check("cap_space helper agrees", scs.cap_space(t) == 2_125_000)
check("total_cap_charge helper agrees", scs.total_cap_charge(t) == 101_875_000)

# old-save safety: team with none of the newer attributes
t_old = mkteam("Old")
t_old.roster.extend([mkplayer(5_000_000) for _ in range(20)])
for attr in ("buyout_cap_hits", "real_buyout_cap", "real_retained_salary",
             "real_bonus_overage", "real_dead_cap_seeded"):
    if hasattr(t_old, attr):
        delattr(t_old, attr)
bd_old = scs.cap_breakdown(t_old)
check("old save: dead cap 0", bd_old["dead_cap"] == 0)
check("old save: total == roster", bd_old["total"] == 100_000_000)

# -- 3. trade shed logic ------------------------------------------------------
import trade_engine as te
CAP = 104_000_000
user = mkteam("User"); partner = mkteam("Partner")
star = mkplayer(9_000_000)
user.roster.extend([star] + [mkplayer(4_500_000) for _ in range(20)] + [mkplayer(8_000_000)])
# payroll = 9 + 90 + 8 = $107M > $104M
check("cap hit reads contract.salary", te._player_cap_hit(star) == 9_000_000)
dump = mkplayer(2_000_000); partner.roster.append(dump)

check("over-cap shed to compliant ALLOWED",
      te._cap_ok_after(user, [star], [dump]) is True)
# $107M - $9M + $8.5M = $106.5M: still over, but STRICTLY reduced -> ALLOWED
check("over-cap partial shed (still over) ALLOWED",
      te._cap_ok_after(user, [star], [mkplayer(8_500_000)]) is True)
# neutral: $107M - $9M + $9M = $107M -> REJECTED
check("over-cap neutral swap REJECTED",
      te._cap_ok_after(user, [star], [mkplayer(9_000_000)]) is False)
# worsening -> REJECTED
check("over-cap adding salary REJECTED",
      te._cap_ok_after(user, [mkplayer(1_000_000)], [mkplayer(5_000_000)]) is False)

u2 = mkteam("U2"); u2.roster.extend([mkplayer(3_000_000) for _ in range(20)])  # $60M
check("compliant lateral swap ALLOWED",
      te._cap_ok_after(u2, [u2.roster[0]], [mkplayer(3_000_000)]) is True)
check("compliant add within space ALLOWED",
      te._cap_ok_after(u2, [], [mkplayer(3_000_000)]) is True)
# compliant team pushing over -> REJECTED
u3 = mkteam("U3"); u3.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M
check("compliant trade that breaks cap REJECTED",
      te._cap_ok_after(u3, [], [mkplayer(5_000_000)]) is False)

# AI partner over the cap sheds too (parity) -- same function, same rule
p_over = mkteam("POver")
p_over.roster.extend([mkplayer(5_000_000) for _ in range(21)] + [dump])  # $107M
check("AI over-cap partial shed ALLOWED (parity)",
      te._cap_ok_after(p_over, [dump, p_over.roster[0]], [mkplayer(1_000_000)]) is True)
check("AI over-cap neutral REJECTED (parity)",
      te._cap_ok_after(p_over, [p_over.roster[0]], [mkplayer(5_000_000)]) is False)

# dead cap counts in totals but doesn't move in a trade
u4 = mkteam("U4")
u4.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M roster
u4.real_retained_salary = 5_000_000  # $105M total -> over
check("dead cap makes team over (blocks neutral deal)",
      te._cap_ok_after(u4, [u4.roster[0]], [mkplayer(5_000_000)]) is False)
check("dead-cap team can still shed",
      te._cap_ok_after(u4, [u4.roster[0]], [mkplayer(1_000_000)]) is True)

# -- 4. AI consider path -------------------------------------------------------
resp = te.ai_consider_trade(partner, [dump], [star], user_team=user)
check("ai_consider_trade runs (no crash)",
      resp.decision in ("accept", "reject", "counter"))

# -- 5. dead-cap data + seeding -------------------------------------------------
import real_cap_data
check("dead-cap table covers 32 teams", len(real_cap_data.DEAD_CAP_2026_27) == 32)
check("all tuples non-negative",
      all(b >= 0 and r >= 0 and o >= 0
          for (b, r, o) in real_cap_data.DEAD_CAP_2026_27.values()))
b, r, o = real_cap_data.get_dead_cap("Boston Bruins")
check("Boston 615K retained", (b, r, o) == (0, 615_000, 0))
check("Vancouver total $6.267M",
      real_cap_data.total_dead_cap("Vancouver Canucks") == 6_267_000)
check("San Jose total $6.535M",
      real_cap_data.total_dead_cap("San Jose Sharks") == 6_535_000)
check("Ottawa total $1.875M",
      real_cap_data.total_dead_cap("Ottawa Senators") == 1_875_000)
check("Detroit zero", real_cap_data.total_dead_cap("Detroit Red Wings") == 0)

league = type("L", (), {"teams": [mkteam("Boston Bruins"),
                                  mkteam("Ottawa Senators"),
                                  mkteam("Detroit Red Wings")]})()
n = real_cap_data.seed_real_dead_cap(league)
check("seeding returns team count", n == 3)
check("Boston seeded 615K retained",
      league.teams[0].real_retained_salary == 615_000
      and league.teams[0].real_dead_cap_seeded is True)
check("Ottawa seeded 1.875M",
      league.teams[1].real_buyout_cap + league.teams[1].real_retained_salary == 1_875_000)
check("Detroit seeded zeros", real_cap_data.seeded_dead_cap_total(league.teams[2]) == 0)
# idempotent
check("re-seed is idempotent", real_cap_data.seed_real_dead_cap(league) == 0)
# central accounting sees the seeded penalties
check("seeded penalties hit cap charge",
      scs.total_cap_charge(league.teams[0]) == scs.roster_cap_charge(league.teams[0]) + 615_000)

# -- 6. clear toggle ------------------------------------------------------------
clr = real_cap_data.clear_dead_cap(league)
check("clear returns team count", clr == 3)
check("clear zeroes penalties",
      all(real_cap_data.seeded_dead_cap_total(t) == 0 for t in league.teams))
# in-game buyouts survive the clear
league2 = type("L", (), {"teams": [mkteam("Boston Bruins")]})()
real_cap_data.seed_real_dead_cap(league2)
league2.teams[0].buyout_cap_hits = {2026: 999_000}
real_cap_data.clear_dead_cap(league2)
check("clear preserves in-game buyouts",
      league2.teams[0].buyout_cap_hits == {2026: 999_000})

# -- 7. expiry at rollover --------------------------------------------------------
league3 = type("L", (), {"teams": [mkteam("San Jose Sharks")]})()
real_cap_data.seed_real_dead_cap(league3)
check("no expiry within 2026-27",
      real_cap_data.expire_seeded_dead_cap(league3, 2026) == 0)
check("expiry after rollover",
      real_cap_data.expire_seeded_dead_cap(league3, 2027) == 1
      and real_cap_data.seeded_dead_cap_total(league3.teams[0]) == 0)

# -- 8. save/load round-trip -------------------------------------------------------
t_sv = mkteam("Boston Bruins")
t_sv.roster.extend([mkplayer(5_000_000)])
t_sv.real_buyout_cap, t_sv.real_retained_salary = 0, 615_000
t_sv.real_bonus_overage, t_sv.real_dead_cap_seeded = 0, True
# emulate the save dict path
saved = {
    'buyout_cap_hits': dict(getattr(t_sv, 'buyout_cap_hits', {}) or {}),
    'real_buyout_cap': int(getattr(t_sv, 'real_buyout_cap', 0) or 0),
    'real_retained_salary': int(getattr(t_sv, 'real_retained_salary', 0) or 0),
    'real_bonus_overage': int(getattr(t_sv, 'real_bonus_overage', 0) or 0),
    'real_dead_cap_seeded': bool(getattr(t_sv, 'real_dead_cap_seeded', False)),
}
t_ld = mkteam("Boston Bruins")
t_ld.real_buyout_cap = int(saved.get('real_buyout_cap', 0) or 0)
t_ld.real_retained_salary = int(saved.get('real_retained_salary', 0) or 0)
t_ld.real_bonus_overage = int(saved.get('real_bonus_overage', 0) or 0)
t_ld.real_dead_cap_seeded = bool(saved.get('real_dead_cap_seeded', False))
check("save/load preserves seeded penalties",
      real_cap_data.seeded_dead_cap_total(t_ld) == 615_000
      and t_ld.real_dead_cap_seeded is True)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
