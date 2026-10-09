# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Deterministic QA: staff morale as a living system (audit 2026-09-30).

Proves, per factor: every morale driver moves the target; the monthly tick
converges, clamps, and stays deterministic; the morale factor is neutral at
60 and bounded; and each wired consumer (parity coach quality, assistant
drift, practice drill rating) actually responds to morale.
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, '.')

import staff_morale as sm

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name +
          (f" -- {detail}" if detail and not cond else ""))


def staffer(**kw):
    base = dict(first_name="Test", last_name="Coach", morale=60,
                gm_trust=70, contract_years=3, ambition="climb",
                controversy=0, first_nhl_chair=False, years_with_team=2,
                motivating=70, man_management=70)
    base.update(kw)
    return SimpleNamespace(**base)


def team_of(*staff, name="Test Club", head=None):
    t = SimpleNamespace(team_name=name, staff=list(staff), roster=[],
                        head_coach=head if head is not None
                        else (staff[0] if staff else None))
    return t


print("== target drivers ==")
s = staffer()
t_win = sm.morale_target(s, None, win_pct=0.700)
t_mid = sm.morale_target(s, None, win_pct=0.500)
t_lose = sm.morale_target(s, None, win_pct=0.300)
check("winning lifts target", t_win > t_mid, f"{t_win} vs {t_mid}")
check("losing drags target", t_lose < t_mid, f"{t_lose} vs {t_mid}")
check("target bounded", 5.0 <= t_win <= 98.0 and 5.0 <= t_lose <= 98.0)

s2 = staffer(gm_trust=30)
check("low gm_trust drags", sm.morale_target(s2) < sm.morale_target(s),
      f"{sm.morale_target(s2)} vs {sm.morale_target(s)}")
s3 = staffer(contract_years=1)
check("expiring contract drags", sm.morale_target(s3) < sm.morale_target(s))
s4 = staffer(ambition="stanley_cup")
tm_rebuild = SimpleNamespace(team_name="X", staff=[], direction="rebuild")
check("ambition/direction mismatch drags",
      sm.morale_target(s4, tm_rebuild) < sm.morale_target(s4, None))
s5 = staffer(controversy=80)
check("controversy drags", sm.morale_target(s5) < sm.morale_target(s))
s6 = staffer(first_nhl_chair=True)
check("first chair lifts", sm.morale_target(s6) > sm.morale_target(s))
s7 = staffer(years_with_team=8)
check("settled tenure lifts", sm.morale_target(s7) > sm.morale_target(s))
check("none-safe target", sm.morale_target(None) == 60.0)

print("== monthly tick ==")
st = staffer(morale=90)
tm = team_of(st)
lines1 = sm.staff_morale_tick(tm, win_pct=0.300)   # losing: target < 90
check("tick pulls toward target", st.morale < 90, f"now {st.morale}")
m_before = st.morale
sm.staff_morale_tick(tm, win_pct=0.300)
check("tick keeps converging", st.morale < m_before or st.morale == 1)
st2 = staffer(morale=10)
tm2 = team_of(st2)
for _ in range(40):
    sm.staff_morale_tick(tm2, win_pct=0.750)
check("tick clamps at 100", st2.morale <= 100, f"{st2.morale}")
st3 = staffer(morale=95)
tm3 = team_of(st3)
for _ in range(40):
    sm.staff_morale_tick(tm3, win_pct=0.250)
check("tick clamps at 1", st3.morale >= 1, f"{st3.morale}")
# Determinism: identical runs, identical outcomes.
a, b = staffer(morale=80), staffer(morale=80)
ta, tb = team_of(a), team_of(b)
for _ in range(6):
    sm.staff_morale_tick(ta, win_pct=0.620)
    sm.staff_morale_tick(tb, win_pct=0.620)
check("tick deterministic", a.morale == b.morale, f"{a.morale} vs {b.morale}")
# Storytelling: crisis crossing reports once.
c = staffer(morale=35, gm_trust=20, controversy=80, contract_years=1,
            first_name="Grim", last_name="Bench")
tc = team_of(c)
news = []
for _ in range(6):
    news += sm.staff_morale_tick(tc, win_pct=0.200)
    if news:
        break
check("crisis crossing makes news", len(news) == 1, str(news))
news2 = sm.staff_morale_tick(tc, win_pct=0.200)
check("no news spam below the line", len(news2) == 0, str(news2))
# Spark crossing.
sp = staffer(morale=60, gm_trust=90, first_nhl_chair=True,
             first_name="Sunny", last_name="Disposition")
ts = team_of(sp)
sp_news = []
for _ in range(10):
    sp_news += sm.staff_morale_tick(ts, win_pct=0.800)
check("spark crossing makes news", any("spark" in n for n in sp_news),
      str(sp_news))
check("tick never raises", sm.staff_morale_tick(None) == [])

print("== morale factor ==")
check("neutral at 60", sm.morale_factor(60) == 1.0)
check("happy lifts", sm.morale_factor(95) > 1.0)
check("miserable drags", sm.morale_factor(20) < 1.0)
check("bounded top", sm.morale_factor(100) == 1.10)
check("bounded bottom", sm.morale_factor(1) == 0.90)
check("monotonic",
      sm.morale_factor(20) < sm.morale_factor(60) < sm.morale_factor(95))
check("garbage-safe", sm.morale_factor("xx") == 1.0)
hc = staffer(morale=90)
tmc = team_of(hc)
check("head coach factor reads bench boss",
      sm.head_coach_morale_factor(tmc) == sm.morale_factor(90))
check("no coach -> 1.0",
      sm.head_coach_morale_factor(SimpleNamespace()) == 1.0)

print("== wired consumers ==")
import parity_engine as pe
pe.DISABLED = False
qh = SimpleNamespace(motivating=80, man_management=80, morale=95)
ql = SimpleNamespace(motivating=80, man_management=80, morale=15)
th = SimpleNamespace(team_name="H", head_coach=qh, _parity_state={})
tl = SimpleNamespace(team_name="L", head_coach=ql, _parity_state={})
qh_v = pe._coach_quality(th)
ql_v = pe._coach_quality(tl)
check("parity coach quality responds to morale", qh_v > ql_v,
      f"happy {qh_v:.3f} vs miserable {ql_v:.3f}")
check("parity quality stays in band", 0.0 <= ql_v <= qh_v <= 1.0)

import assistant_coaches as ac
def _tm_ac(morale):
    a = SimpleNamespace(first_name="A", last_name="C",
                        role=SimpleNamespace(value="Assistant Coach"),
                        attacking_coaching=70, defensive_coaching=70,
                        coaching_goalies=50, tactical_knowledge=70,
                        man_management=70, reputation=60, experience=8,
                        years_with_team=1, morale=morale, icon_team="",
                        icon_level="", assistant_effect=70.0)
    return SimpleNamespace(team_name="T", staff=[a], roster=[],
                           tactics_familiarity=85), a
tm_hi, a_hi = _tm_ac(90)
tm_lo, a_lo = _tm_ac(20)
ac.assistants_monthly_tick(tm_hi, win_pct=0.500)
ac.assistants_monthly_tick(tm_lo, win_pct=0.500)
check("assistant drift rewards high morale",
      a_hi.assistant_effect > 70.0, f"{a_hi.assistant_effect}")
check("assistant drift punishes low morale",
      a_lo.assistant_effect < 70.0, f"{a_lo.assistant_effect}")

import coach_practice as cp
ph = SimpleNamespace(first_name="H", last_name="C", morale=95,
                     attacking_coaching=80, defensive_coaching=60,
                     coaching_goalies=50, coaching_forwards=70,
                     coaching_defensemen=60, player_development=70,
                     working_with_youngsters=60, tactical_knowledge=70,
                     adaptability=60)
pl = SimpleNamespace(first_name="L", last_name="C", morale=10,
                     attacking_coaching=80, defensive_coaching=60,
                     coaching_goalies=50, coaching_forwards=70,
                     coaching_defensemen=60, player_development=70,
                     working_with_youngsters=60, tactical_knowledge=70,
                     adaptability=60)
plyr = SimpleNamespace(age=25, primary_position="C", archetype="sniper")
rh, _ = cp.coach_drill_rating(ph, plyr, "shooting")
rl, _ = cp.coach_drill_rating(pl, plyr, "shooting")
check("drill rating responds to coach morale", rh > rl,
      f"inspired {rh:.1f} vs checked-out {rl:.1f}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
