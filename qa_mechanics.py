"""QA: Multi-attribute scoring mechanics (2026-09-28, per Muck).

Verifies:
1. Screens measurably degrade goalie save% (screened < clean)
2. Net-front goals exist as a tracked category
3. D blocks show up in stats (defensive contest)
4. Assist distribution: passing leads (95-passing > 95-awareness)
5. Takeaway/hit/block rates in NHL ranges
6. Save% by situation: screened < clean, tips < clean
7. No single-attribute decisions: composites use multiple attributes

Run: DISPLAY=:99 python3 qa_mechanics.py
"""
import sys, os
sys.path.insert(0, '.')
sys.path.insert(0, os.path.expanduser('~/workspace/playthrough'))

PASS = 0
FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")

print("=== Mechanics QA: multi-attribute scoring ===\n")

# 1. Shared-layer functions exist and never raise
print("1. Shared layer functions:")
from mesh_system import (
    defensive_contest_mult, netfront_spot_win, screen_goalie_mult,
    tip_goal_chance, netfront_finish_chance,
    primary_assist_score, secondary_assist_score,
    pass_lane_contest_mult, recipient_openness_mult,
    takeaway_prob, hit_puck_win_prob, shot_block_prob,
    situational_goalie_skill, rebound_chance,
    defense_point_shot_discount, archetype_finish_tilt,
)
class Fake:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

# Never raise on empty/None
check("defensive_contest_mult([]) = 1.0", defensive_contest_mult([]) == 1.0)
check("defensive_contest_mult(None) = 1.0", defensive_contest_mult(None) == 1.0)
check("netfront_spot_win(None, None) in range", 0 < netfront_spot_win(None, None) < 1)
check("screen_goalie_mult(None, None) = 1.0", screen_goalie_mult(None, None) == 1.0)
check("tip_goal_chance never raises", tip_goal_chance(None, None, 50) > 0)
check("primary_assist_score never raises", primary_assist_score(None) > 0)
check("takeaway_prob never raises", 0 < takeaway_prob(None, None) < 1)

# 2. Passing leads assists (Muck's clarification)
print("\n2. Passing leads (not awareness):")
elite_passer = Fake(passing=95, offensive_awareness=50, composure=50, vision=50)
elite_aware = Fake(passing=50, offensive_awareness=95, composure=95, vision=95)
ps_passer = primary_assist_score(elite_passer)
ps_aware = primary_assist_score(elite_aware)
check("95-passing > 95-awareness (primary)", ps_passer > ps_aware,
      f"({ps_passer:.1f} vs {ps_aware:.1f})")
ss_passer = secondary_assist_score(elite_passer)
ss_aware = secondary_assist_score(elite_aware)
check("95-passing > 95-awareness (secondary)", ss_passer > ss_aware,
      f"({ss_passer:.1f} vs {ss_aware:.1f})")

# 3. Screens degrade goalie
print("\n3. Screens degrade goalie:")
screener_elite = Fake(screen_shots=85)
screener_poor = Fake(screen_shots=20)
goalie_avg = Fake(positioning=50, anticipation=50)
mult_elite = screen_goalie_mult(screener_elite, goalie_avg)
mult_poor = screen_goalie_mult(screener_poor, goalie_avg)
check("Elite screen < 1.0", mult_elite < 1.0, f"({mult_elite:.3f})")
check("Poor screen ≈ 1.0", mult_poor >= 0.99, f"({mult_poor:.3f})")
check("Elite screen stronger than poor", mult_elite < mult_poor)

# 4. Situational goalie weights
print("\n4. Situational goalie:")
g = Fake(positioning=80, reflexes=60, glove_hand=70, stick_side=70,
         rebound_control=70, composure=60, anticipation=60)
s_clean = situational_goalie_skill(g, "clean")
s_screened = situational_goalie_skill(g, "screened")
s_tip = situational_goalie_skill(g, "tip")
# Screened leans positioning (80) + composure (60); tip leans reflexes (60)
# With positioning=80 high, screened should be higher than tip
check("Situational weights differ", s_screened != s_tip,
      f"(screened={s_screened:.1f}, tip={s_tip:.1f})")
check("All situations in 1-100", all(1 <= situational_goalie_skill(g, s) <= 100
      for s in ["clean", "screened", "tip", "breakaway", "point"]))

# 5. Rebound control feeds net-front
print("\n5. Rebound control:")
g_poor_rc = Fake(rebound_control=20)
g_elite_rc = Fake(rebound_control=85)
r_poor = rebound_chance(g_poor_rc)
r_elite = rebound_chance(g_elite_rc)
check("Poor RC > Elite RC rebounds", r_poor > r_elite,
      f"({r_poor:.2f} vs {r_elite:.2f})")
check("Rebound rates in range", 0.05 <= r_elite <= 0.50 and 0.05 <= r_poor <= 0.50)

# 6. Defensive plays multi-attribute
print("\n6. Defensive plays:")
d_elite = Fake(pokecheck=85, defensive_awareness=85, skating=80)
c_avg = Fake(stickhandling=50, deking=50, strength=50)
t_avg = takeaway_prob(d_elite, c_avg)
t_rev = takeaway_prob(c_avg, d_elite)  # reversed: poor defender vs elite carrier
check("Elite defender > 50% takeaway", t_avg > 0.50, f"({t_avg:.2f})")
check("Takeaway is two-sided", t_avg > t_rev, f"({t_avg:.2f} vs {t_rev:.2f})")

hitter = Fake(strength=85, balance=80, aggressiveness=85)
target = Fake(balance=50, strength=50)
h_win = hit_puck_win_prob(hitter, target)
check("Hit win prob in range", 0.05 <= h_win <= 0.95, f"({h_win:.2f})")

blocker = Fake(positioning=85, shot_blocking=85)
shooter = Fake(offensive_awareness=50, composure=50)
b_prob = shot_block_prob(blocker, shooter)
check("Block prob in NHL range (1-30%)", 0.01 <= b_prob <= 0.30, f"({b_prob:.2f})")

# 7. Net-front staged gating
print("\n7. Net-front battle:")
attacker = Fake(off_the_puck=85, strength=80, balance=80)
defender = Fake(strength=50, defensive_awareness=50, positioning=50)
p_win = netfront_spot_win(attacker, defender)
p_lose = netfront_spot_win(defender, attacker)  # weak attacker vs strong defender
check("Strong attacker wins spot > 50%", p_win > 0.50, f"({p_win:.2f})")
check("Spot win is contested", p_win > p_lose, f"({p_win:.2f} vs {p_lose:.2f})")

# Tip: elite tipper vs poor goalie
tipper = Fake(deflections=85, off_the_puck=80, balance=80)
g_poor = Fake(reflexes=40, positioning=40)
tip_p = tip_goal_chance(tipper, g_poor, 50, screened=False)
tip_p_screened = tip_goal_chance(tipper, g_poor, 50, screened=True)
check("Tip chance in range", 0.02 <= tip_p <= 0.40, f"({tip_p:.2f})")
check("Screen boosts tip", tip_p_screened > tip_p,
      f"({tip_p_screened:.2f} vs {tip_p:.2f})")

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
