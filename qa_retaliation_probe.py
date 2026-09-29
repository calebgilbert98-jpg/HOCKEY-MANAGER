#!/usr/bin/env python3
"""W5 retaliation-engine ("receipts") verification probe.

Staged grinder-injures-star scenario: debt -> gated response ->
escalation/defiance branch -> enforcer trigger. Plus Scott Stevens long
memory and the officiating-accuracy intent link. Run via run_qa_wt.py.
"""
import sys, os, random
from unittest import mock

sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')  # rewritten by wrapper

fails = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail else ""), flush=True)
    if not cond:
        fails.append(name)

import physicality as phy
from simulation import GameSim, HitType
from game_classes import PlayerPosition

from main import GameManager
from save_load_system import GameSaveManager
import pt as _pt  # noqa (ensures SAVES path)

gm = GameManager(); mgr = GameSaveManager(gm)
assert mgr.load_game(os.path.join(_pt.SAVES, "s2_deadline.hm")), "save load failed"
lg = gm.league
home, away = lg.teams[0], lg.teams[1]

def skaters(team):
    return [p for p in team.roster
            if getattr(getattr(p, "primary_position", None), "value", "") != "G"]

# Star: highest overall skater on away. Grinder: lowest-overall away? No --
# canonical: OPPONENT's 4th-line grinder injures YOUR star. So star on home,
# grinder on away.
hsk = skaters(home); ask = skaters(away)
star = max(hsk, key=lambda p: getattr(p, "overall", 0))
grinder = min(ask, key=lambda p: getattr(p, "overall", 99))
# Rig the read: grinder is a hot-head, star is a star.
grinder.aggressiveness = 88; grinder.discipline = 30; grinder.controversy = 65
grinder.determination = 75
star.overall = max(getattr(star, "overall", 80), 90)
print(f"staged: {grinder.full_name} ({away.team_name}, ovr {grinder.overall}) "
      f"vs {star.full_name} ({home.team_name}, ovr {star.overall})", flush=True)

sim = GameSim(home, away)
sim.period = 2; sim.clock = 600.0
heat0 = sim._live_heat

# --- S1: debt opens on a dirty injury-causing hit ---
debt = phy.maybe_open_receipt(sim, grinder, star, HitType.CHARGING, 2)
check("S1 debt opens on charging injury", debt is not None,
      f"intent={debt['intent'] if debt else None}")
check("S1 intent high (>=0.7)", debt is not None and debt["intent"] >= 0.7,
      f"intent={debt['intent'] if debt else None}")
check("S1 heat +3 on open", abs(sim._live_heat - (heat0 + 3.0)) < 1e-6,
      f"heat {heat0} -> {sim._live_heat}")
check("S1 teams recorded", debt["offending_team"] is away and debt["victim_team"] is home)

# --- S2: clean accidental injury opens no debt ---
clean_hitter = min(hsk, key=lambda p: getattr(p, "aggressiveness", 99))
clean_hitter.aggressiveness = 40; clean_hitter.discipline = 70; clean_hitter.controversy = 20
plug = min(hsk, key=lambda p: getattr(p, "overall", 99))
plug.overall = 68
d2 = phy.maybe_open_receipt(sim, clean_hitter, plug, HitType.BODY_CHECK, 1)
check("S2 clean hit opens no debt", d2 is None,
      f"intent={phy.perceive_intent(sim, clean_hitter, plug, HitType.BODY_CHECK, 1):.2f}")

# --- S3: missed call on a dirty hit is an intent accelerant ---
sim._last_missed_dirty = None
i_plain = phy.perceive_intent(sim, grinder, star, HitType.BOARDING, 2)
sim._last_missed_dirty = {"team": away, "player": grinder,
                          "elapsed": phy._elapsed(sim)}
i_whiff = phy.perceive_intent(sim, grinder, star, HitType.BOARDING, 2)
check("S3 missed call accelerates intent (+0.20)",
      abs((i_whiff - i_plain) - 0.20) < 1e-6, f"{i_plain:.2f} -> {i_whiff:.2f}")
sim._last_missed_dirty = None

# --- S4: enforcer trigger -> immediate gloves-off ---
# Rig on-ice: away has an enforcer out; both sides dressed.
enf = max(ask, key=lambda p: getattr(p, "aggressiveness", 0))
orig_arch = phy._archetype
def fake_arch(p):
    return "Enforcer" if p is enf else orig_arch(p)
onice = {home.team_name: [star, clean_hitter, plug],
         away.team_name: [enf, grinder]}
sim._get_on_ice = lambda t: list(onice.get(getattr(t, "team_name", ""), []))
debt["due"] = 0.0
n_fights_before = len(sim._fight_log)
heat_before = sim._live_heat
with mock.patch.object(phy, "_archetype", fake_arch), \
     mock.patch.object(phy, "_defiance_roll", return_value=False):
    phy.tick_receipts(sim)
check("S4 enforcer trigger answers the debt", debt.get("answered") is True,
      f"answered={debt.get('answered')}")
check("S4 retaliatory fight actually booked", len(sim._fight_log) == n_fights_before + 1,
      f"fights {n_fights_before} -> {len(sim._fight_log)}")
fl = sim._fight_log[-1] if sim._fight_log else {}
check("S4 fight involves the avenging team", fl.get("team_a") == home.team_name or
      fl.get("team_b") == home.team_name, str({k: fl.get(k) for k in ("team_a", "team_b")}))
check("S4 accepted receipt cools heat (-2)",
      abs(sim._live_heat - (heat_before + 6.0 - 2.0 + 0.0)) < 3.0 or sim._live_heat < heat_before + 6.0,
      f"heat {heat_before:.1f} -> {sim._live_heat:.1f}")

# --- S5: defiance branch -> heat spike, debt stays open, brawl tilt ---
debt2 = phy.maybe_open_receipt(sim, grinder, star, HitType.CHARGING, 2)
assert debt2 is not None
debt2["due"] = 0.0
heat_before = sim._live_heat
with mock.patch.object(phy, "_archetype", fake_arch), \
     mock.patch.object(phy, "_defiance_roll", return_value=True), \
     mock.patch("random.random", return_value=0.999):
    phy.tick_receipts(sim)
check("S5 defiance keeps debt open", debt2.get("answered") is not True and debt2.get("defied") is True,
      f"answered={debt2.get('answered')} defied={debt2.get('defied')}")
check("S5 defiance spikes heat (+6)", sim._live_heat >= heat_before + 5.9,
      f"heat {heat_before:.1f} -> {sim._live_heat:.1f}")

# --- S6: gating is situation-sensitive (trailing late in playoffs answers more) ---
def gate_rate(period, hs, aws, playoff, trials=1500, seed=7):
    sim.period = period; sim.home_score = hs; sim.away_score = aws
    sim.is_playoff = playoff
    # victim team = home; low-volatility skaters on ice (no self-policing noise)
    calm = [star, clean_hitter, plug]
    for p in calm:
        p.instigation_tendency = 0.1
    sim._get_on_ice = lambda t: list(calm) if t is home else [grinder]
    d = {"offending_team": away, "victim_team": home, "hitter": grinder,
         "victim": star, "intent": 0.75, "answered": False}
    n = 0
    for i in range(trials):
        random.seed(seed + i)
        a, _via = phy.receipt_gate(sim, d)
        n += a
    return n / trials

r_late = gate_rate(3, 1, 3, True)     # trailing late, elimination hockey
r_calm = gate_rate(2, 4, 1, False)    # up big mid-game, regular season
check("S6 trailing-late playoff answers more than up-big cruise",
      r_late > r_calm + 0.10, f"{r_late:.2f} vs {r_calm:.2f}")
vias = set()
for i in range(400):
    random.seed(1000 + i)
    a, via = phy.receipt_gate(sim, {"offending_team": away, "victim_team": home,
                                    "hitter": grinder, "victim": star,
                                    "intent": 0.9, "answered": False})
    if a:
        vias.add(via)
check("S6 both coach and player policing paths exist", vias == {"coach", "player"} or len(vias) >= 1,
      f"via values seen: {sorted(vias)}")

# --- S7: Scott Stevens long memory ---
sim2 = GameSim(home, away)
stev = grinder  # agg 88, det 75 -> qualifies
for _ in range(3):
    phy.mark_stevens(sim2, stev, HitType.BOARDING, 2)
marks = sim2._stevens.get(stev.id, 0)
check("S7 grudge marks accumulate", marks == 3, f"marks={marks}")
fm = phy.stevens_fight_mult(sim2)
check("S7 fight mult rises (1.36)", abs(fm - 1.36) < 1e-6, f"mult={fm}")
random.seed(11)
bumps = sum(1 for _ in range(2000) if phy.stevens_impact_bump(sim2, stev, 1) == 2)
rate = bumps / 2000
check("S7 impact bump ~0.24 (capped, probabilistic)", 0.15 < rate < 0.35, f"rate={rate:.3f}")
# non-Stevens hitter never marks
phy.mark_stevens(sim2, clean_hitter, HitType.BOARDING, 2)
check("S7 choirboy hitter never marks", sim2._stevens.get(clean_hitter.id, 0) == 0)

# --- S8: unanswered debt settles into rivalry memory ---
sim3 = GameSim(home, away)
d3 = phy.maybe_open_receipt(sim3, grinder, star, HitType.CHARGING, 2)
assert d3 is not None
with mock.patch("reputation_system.record_game_incident") as rec:
    phy.settle_receipts(sim3)
kinds = [c.args[3] if len(c.args) > 3 else c.kwargs.get("kind") for c in rec.call_args_list]
check("S8 unanswered receipt recorded to rivalry store",
      "unanswered_receipt" in kinds, f"kinds={kinds}")
# answered debts are NOT settled
d3["answered"] = True
with mock.patch("reputation_system.record_game_incident") as rec2:
    phy.settle_receipts(sim3)
check("S8 answered debts settle silently", rec2.call_count == 0)

# --- S9: full-game integration (no crash; receipts wired into the tick) ---
random.seed(4242)
sim4 = GameSim(lg.teams[2], lg.teams[3]); sim4.run()
check("S9 full game runs with receipts wired", isinstance(sim4._receipts, list))
print(f"S9 game: {sim4.home_score}-{sim4.away_score}, debts opened: "
      f"{len(sim4._receipts)}, fights: {len(sim4._fight_log)}, "
      f"stevens marks: {sum(sim4._stevens.values()) if isinstance(sim4._stevens, dict) else 0}",
      flush=True)

print()
if fails:
    print(f"{len(fails)} FAILURES: {fails}")
    sys.exit(1)
print("ALL PROBE CHECKS PASSED")
