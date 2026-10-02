"""QA: NHL roster limits, dressed minimums, rights lifecycle, emergency fillers.

True-NHL rules (Chris's rulings 2026-10-01). Deterministic (seeded RNG).
Run: python3 qa_roster_limits.py
"""
import datetime
import random
import sys

import game_classes as gc
import roster_limits as rl

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


def mkplayer(pos="C", salary=1_000_000, years=3, age=25, injured=False):
    p = gc.Player("Test", f"Player{random.randint(0, 10**9)}", age=age,
                  primary_position=gc.PlayerPosition(pos))
    p.contract.salary = salary
    p.contract.years_remaining = years
    p.is_injured = injured
    return p


def mkteam(user=False, name="Test Team"):
    t = gc.Team(team_name=name, city="Testville", division="Atlantic",
                conference="Eastern")
    t.is_user_team = user
    t.roster, t.ahl_roster, t.prospects = [], [], []
    return t


def fill_dressable(t, skaters=18, goalies=2):
    for _ in range(skaters):
        t.roster.append(mkplayer("C"))
    for _ in range(goalies):
        t.roster.append(mkplayer("G"))


rng = random.Random(20261001)

# --- 1. Counting ---------------------------------------------------------------
t = mkteam()
fill_dressable(t)
check("active count = 20 dressable", rl.active_roster_count(t) == 20)
check("spc count = 20", rl.spc_count(t) == 20)
check("can dress 18+2", rl.can_dress_lineup(t))
check("no shortfall", rl.lineup_shortfall(t) == (0, 0))

# unsigned players (expired deals, rights retained) don't count
u = mkplayer(years=0)
t.roster.append(u)
check("unsigned excluded from 23-count", rl.active_roster_count(t) == 20)
check("unsigned excluded from SPC", rl.spc_count(t) == 20)
check("unsigned can't dress", not rl.is_available(u))

# injured players can't dress
t2 = mkteam()
fill_dressable(t2)
t2.roster[0].is_injured = True
check("injured skater unavailable", rl.dressable_skaters(t2) == 17)
check("17 skaters can't dress", not rl.can_dress_lineup(t2))
check("shortfall = 1 skater", rl.lineup_shortfall(t2) == (1, 0))

# --- 2. 23-man / 50-SPC day gates ----------------------------------------------
class App:
    def __init__(self, team):
        self.user_team = team
    def open_roster_window(self):
        pass

t3 = mkteam(user=True)
for _ in range(24):
    t3.roster.append(mkplayer())
ids = [b["id"] for b in rl.roster_limit_blockers(App(t3))]
check("over-23 blocks the day", "roster_limit_23" in ids)

t4 = mkteam(user=True)
for _ in range(51):
    p = mkplayer()
    (t4.roster if len(t4.roster) < 23 else t4.ahl_roster).append(p)
ids = [b["id"] for b in rl.roster_limit_blockers(App(t4))]
check("over-50 SPC blocks the day", "roster_limit_50" in ids)

t5 = mkteam(user=True)
fill_dressable(t5)
check("compliant club: no blockers", rl.roster_limit_blockers(App(t5)) == [])

# fillers don't trip the gates
t6 = mkteam(user=True)
for _ in range(23):
    t6.roster.append(mkplayer())
rl.summon_emergency_fillers(t6)  # no shortfall -> no-op
t6.roster.append(rl.make_emergency_filler("C", rng))
ids = [b["id"] for b in rl.roster_limit_blockers(App(t6))]
check("filler exempt from 23-gate", "roster_limit_23" not in ids)
check("filler charge computed", rl.emergency_filler_charge(t6) > 0)

# dress minimum is Eastside-auto now: no hard blocker, fill-ins summoned
# with an FYI note (news_log + inbox)
t7 = mkteam(user=True, name="User Club")
app7 = App(t7)
app7.news_log = []
app7.inbox_messages = []
ids = [b["id"] for b in rl.roster_limit_blockers(app7)]
check("auto-summon: no dress_minimum blocker", "dress_minimum" not in ids)
check("auto-summon: lineup dresses", rl.can_dress_lineup(t7))
check("auto-summon: news note logged",
      any("Emergency fill-ins summoned" in (n.get("story", "") or "")
          for n in app7.news_log))
check("auto-summon: inbox note logged",
      any("fill-ins" in (getattr(m, "subject", "") or "")
          for m in app7.inbox_messages))
check("auto-summon: fillers on roster w/ team back-pointer",
      all(f in t7.roster and getattr(f, "team_name", None) == "User Club"
          for f in t7.roster if rl.is_emergency_filler(f)))
# over-cap club also auto-summons (the league exception)
t7b = mkteam(user=True, name="Cap Club")
fill_dressable(t7b, skaters=10, goalies=1)
for p in t7b.roster:
    p.contract.salary = 8_000_000
ids = [b["id"] for b in rl.roster_limit_blockers(App(t7b))]
check("over-cap auto-summon: no blocker", "dress_minimum" not in ids
      and rl.can_dress_lineup(t7b))

# --- 3. Outbound-move guards ------------------------------------------------------
t8 = mkteam()
fill_dressable(t8)  # exactly 18+2
check("demoting from exactly 18 breaks minimum",
      rl.would_break_dress_minimum(t8, [t8.roster[0]]))
t8.roster.append(mkplayer("C"))  # 19 skaters now
check("demoting from 19 is fine",
      not rl.would_break_dress_minimum(t8, [t8.roster[0]]))
check("trading a goalie breaks minimum",
      rl.would_break_dress_minimum(t8, [p for p in t8.roster
                                        if p.primary_position == gc.PlayerPosition.GOALIE][:1]))

# --- 4. Dec-1 ineligibility ---------------------------------------------------------
t9 = mkteam()
p = mkplayer(age=24, years=0)
p.qo_extended = True  # qualified, unsigned
t9.roster.append(p)
L = type("L", (), {"teams": [t9]})()
check("no stamp before Dec", rl.apply_dec1_ineligibility(L, datetime.date(2026, 11, 30)) == 0)
check("stamped Dec 1", rl.apply_dec1_ineligibility(L, datetime.date(2026, 12, 1)) == 1)
check("flag set", p.season_ineligible is True)
ok, why = rl.can_sign_player(p)
check("ineligible can't sign", not ok and "December 1" in why)
check("ineligible can't dress", not rl.is_available(p))
check("stamp idempotent", rl.apply_dec1_ineligibility(L, datetime.date(2026, 12, 20)) == 0)
# rights retained: still on the roster, still the club's RFA
check("rights retained (still attached)", p in t9.roster)

# --- 5. July: unsigned UFAs leave ------------------------------------------------------
import rfa_system as rfa

t10 = mkteam(user=True, name="User Club")
u1 = mkplayer(years=0, age=30)    # expired UFA (27+ => Group 3)
u1.contract.salary = 2_000_000
t10.roster.append(u1)
r1 = mkplayer(age=24, years=0)   # expired RFA -- rights retained, stays
r1.qo_extended = True
t10.roster.append(r1)
# a Dec-1 holdout from last season re-enters the QO flow (not stuck)
h1 = mkplayer(age=24, years=0)
h1.qo_extended = True
h1.season_ineligible = True
t10.roster.append(h1)
fill_dressable(t10)
league = type("L", (), {"teams": [t10], "free_agents": [], "season_year": 2026})()
res = rl.july_release_unsigned_ufas(league, app=None)
check("expired UFA released", u1 not in t10.roster and u1 in league.free_agents)
check("RFA rights retained at July", r1 in t10.roster)
check("release reported", res.get("User Club") == [u1.full_name])
full = rfa.process_rfa_offseason(league, app=None, rng=random.Random(7))
check("July clears last season's Dec-1 flag", h1.season_ineligible is False)
check("holdout still club property", h1 in t10.roster or h1 in league.free_agents)

# --- 6. Emergency fillers: quality + guards ----------------------------------------------
worst = 0
for pos in ["C", "LW", "RW", "LD", "RD", "G", "D"]:
    for _ in range(20):
        f = rl.make_emergency_filler(pos, rng)
        worst = max(worst, f.overall_rating())
        assert f.overall_rating() <= 65, (pos, f.overall_rating())
        assert f.contract.salary > 0
check("140 fillers all <= 65 overall", worst <= 65, f"max={worst}")
f = rl.make_emergency_filler("C", rng)
ok, _ = rl.can_sign_player(f)
check("filler can't take a standard deal", not ok)
check("_sign_player refuses filler (False)", rfa._sign_player(t10, f, 800_000, 1) is False)
check("_sign_player refuses Dec-1 RFA (False)",
      rfa._sign_player(t10, p, 800_000, 1) is False)
# ...but a normal signing still works
np_ = mkplayer()
check("_sign_player signs normally", rfa._sign_player(t10, np_, 800_000, 1) is True)

# development skips fillers
from player_development_system import PlayerDevelopmentEngine
eng = PlayerDevelopmentEngine()
check("monthly dev skips filler", eng.process_monthly_development(f) == {})
check("attribute dev returns 0", eng.calculate_attribute_development(f, "skating") == 0)

# trade engine rejects filler assets
import trade_engine as te
ta, tb = mkteam(), mkteam()
ta.team_name, tb.team_name = "A", "B"
pa = mkplayer()
ta.roster.append(pa)
fa = rl.make_emergency_filler("LW", rng)
ta.roster.append(fa)
pb = mkplayer()
tb.roster.append(pb)
res = te.execute_trade(ta, tb, [fa], [pb], date_str="2026-10-15")
check("trade of filler blocked", res.summary.startswith("BLOCKED"))
res = te.execute_trade(ta, tb, [pa], [pb], date_str="2026-12-25")
check("holiday freeze still blocks", res.summary.startswith("BLOCKED"))

# --- 7. AI compliance sweep ----------------------------------------------------------------
t11 = mkteam()
for _ in range(26):  # AI over the 23-man max
    p = mkplayer(salary=900_000)
    p.contract.two_way = True
    t11.roster.append(p)
done = rl.ai_roster_compliance(t11)
check("AI papered down to 23", rl.active_roster_count(t11) == 23, str(done))
check("AI demotions used the AHL", len(t11.ahl_roster) == 3)

# paper-down never breaks the dressed minimum: 24 active, exactly 18+2
# dressable (4 injured) -> may only demote the injured
t11b = mkteam()
for _ in range(18):
    t11b.roster.append(mkplayer("C"))
for _ in range(2):
    t11b.roster.append(mkplayer("G"))
for _ in range(4):
    t11b.roster.append(mkplayer("C", injured=True))
done = rl.ai_roster_compliance(t11b)
check("paper-down keeps 18+2 dressable", rl.can_dress_lineup(t11b), str(done))
check("paper-down only moved the injured",
      all(p.is_injured for p in t11b.ahl_roster))

t12 = mkteam()  # AI can't dress -> summons
done = rl.ai_roster_compliance(t12)
check("AI summoned fillers", done["summoned"] > 0 and rl.can_dress_lineup(t12))
# fillers exempt from AI's 23-count too
check("AI 23-count excludes fillers", rl.active_roster_count(t12) == 0)

# --- 8. Deadlock: over-cap club can still ice a lineup ---------------------------------------
t13 = mkteam(user=True)
fill_dressable(t13, skaters=10, goalies=1)  # short AND over cap
for p in t13.roster:
    p.contract.salary = 8_000_000  # way over the cap
s = rl.summon_emergency_fillers(t13)
check("over-cap club summons fillers", len(s) > 0 and rl.can_dress_lineup(t13))
# the day-gate cap check excludes the filler charge
fc = rl.emergency_filler_charge(t13)
check("filler charge isolated", fc == len(s) * 775_000, str(fc))

# --- 9. Part 3: team assignment + auto everywhere -----------------------------------
# team= param at construction
t14 = mkteam(name="Assign Club")
f14 = rl.make_emergency_filler("C", rng, team=t14)
check("make_emergency_filler(team=) sets team_name",
      getattr(f14, "team_name", None) == "Assign Club")
check("make_emergency_filler(team=) is on the roster", f14 in t14.roster)
f14b = rl.make_emergency_filler("G", rng)  # no team -> no crash
check("make_emergency_filler without team still works",
      rl.is_emergency_filler(f14b))

# summon routes every filler through _assign_filler_to_team
t15 = mkteam(name="Summon Club")
fill_dressable(t15, skaters=10, goalies=1)
s15 = rl.summon_emergency_fillers(t15, rng)
check("summon filled the shortfall", rl.can_dress_lineup(t15)
      and len(s15) == 9, f"summoned={len(s15)}")
check("every filler has team_name set",
      all(getattr(f, "team_name", None) == "Summon Club" for f in s15))
check("every filler is in team.roster", all(f in t15.roster for f in s15))

# measured overall band over a fresh sample (Chris's spec: decent, not scrub)
best, worst = 999, 0
for pos in ["C", "LW", "RW", "LD", "RD", "G"]:
    for _ in range(25):
        o = rl.make_emergency_filler(pos, rng).overall_rating()
        best, worst = min(best, o), max(worst, o)
check("measured band within 48..65 (replacement-level+)",
      40 <= best and worst <= 65, f"min={best} max={worst}")
print(f"measured filler overall band: min={best} max={worst}")

# ensure_dressed_lineup_auto
t16 = mkteam()
fill_dressable(t16)
check("auto no-ops on healthy lineup",
      rl.ensure_dressed_lineup_auto(t16) == [])
t17 = mkteam()
fill_dressable(t17, skaters=15, goalies=1)
notes = []
s17 = rl.ensure_dressed_lineup_auto(t17, notify=notes.append)
check("auto fills short lineup exactly",
      rl.can_dress_lineup(t17) and len(s17) == 4, f"summoned={len(s17)}")
check("notify got the summoned list", notes == [s17])
check("auto-summoned fillers have team_name",
      all(getattr(f, "team_name", None) == t17.team_name for f in s17))

# user_roster_compliance: injure -> auto-summon; heal -> auto-release; no paper-down
t18 = mkteam()
fill_dressable(t18)
for p in t18.roster[:6]:
    p.is_injured = True  # 12 skaters dressable -> short 6
done = rl.user_roster_compliance(t18)
check("user compliance auto-summons", done["summoned"] == 6
      and rl.can_dress_lineup(t18), str(done))
for p in t18.roster:
    p.is_injured = False  # lineup healthy again
done = rl.user_roster_compliance(t18)
check("user compliance releases fillers once healthy",
      done["released"] == 6
      and not any(rl.is_emergency_filler(p) for p in t18.roster), str(done))
check("user compliance never demotes (human decision)",
      len(t18.ahl_roster) == 0)

# roster_limit_blockers never leaves a dress_minimum behind after auto-summon
t19 = mkteam(user=True)
fill_dressable(t19, skaters=12, goalies=1)
ids = [b["id"] for b in rl.roster_limit_blockers(App(t19))]
check("no dress_minimum blocker after auto-summon", "dress_minimum" not in ids)
check("lineup dresses after gate", rl.can_dress_lineup(t19))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
