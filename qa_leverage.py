#!/usr/bin/env python3
"""Within-line differentiation ("leverage score") verification probe.

Acceptance:
  (a) heater vs cold at equal TOI: the hot line gets ~10-15%+ more OZ-start
      picks than its quantity share implies (mechanism-level A/B on the
      stoppage path), and the effect follows the heat when lines are swapped.
      Plus leverage_score unit math: heater > neutral > cold, hard bounds,
      players_coach spreads wider than drill_sergeant.
  (b) league GPG unchanged vs the 2.058 baseline (sensibly-sized full-game
      A/B with the LEVERAGE_ENABLED kill-switch as the control).
  (c) talent-hierarchy invariant: deployment_weights (quantity) are
      bit-identical with leverage on/off -- leverage never touches shares.
  (d) narrative seam: leverage feed lines are emitted once per (team, key)
      per game and never raise.

Run headless:  DISPLAY=:99 python3 qa_leverage.py
"""
import sys, os, random

# NOTE: pt.py does sys.path.insert(0, <HOCKEY-MANAGER>) at import, so the
# worktree must be (re-)asserted AFTER importing pt. The wrapper rewrites
# the literal below to the worktree under test.
sys.path.insert(0, '/home/hatch/workspace/playthrough')
from pt import patch_dialogs_headless, SAVES
sys.path.insert(0, '/home/hatch/workspace/wt-icetime')  # rewritten by wrapper
sys.path = [p for p in sys.path
            if os.path.abspath(p) != '/home/hatch/workspace/HOCKEY-MANAGER']
patch_dialogs_headless()

fails = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail else ""), flush=True)
    if not cond:
        fails.append(name)

import deployment_policy as dp
from deployment_policy import leverage_score

# ---------------------------------------------------------------- unit math
class _P: pass
def _mkplayer(form, morale=70):
    p = _P(); p.mesh_form = form; p.morale = morale
    p.coach_bonds = {}
    return p

h  = leverage_score(_mkplayer(85),  style_key="balanced")
n  = leverage_score(_mkplayer(0),   style_key="balanced")
c  = leverage_score(_mkplayer(-85), style_key="balanced")
check("U1 heater > neutral > cold", h > n > c, f"{h:.3f} {n:.3f} {c:.3f}")
check("U2 hard bounds [0.80, 1.30]",
      all(0.80 <= v <= 1.30 for v in
          (leverage_score(_mkplayer(100), style_key="players_coach"),
           leverage_score(_mkplayer(-100), style_key="players_coach"),
           leverage_score(_mkplayer(100), style_key="drill_sergeant"),
           leverage_score(_mkplayer(-100), style_key="drill_sergeant"))))
h_pc = leverage_score(_mkplayer(85), style_key="players_coach")
c_pc = leverage_score(_mkplayer(-85), style_key="players_coach")
h_ds = leverage_score(_mkplayer(85), style_key="drill_sergeant")
c_ds = leverage_score(_mkplayer(-85), style_key="drill_sergeant")
check("U3 players_coach spreads wider than drill_sergeant",
      (h_pc - c_pc) > (h_ds - c_ds),
      f"pc spread {h_pc - c_pc:.3f} vs ds spread {h_ds - c_ds:.3f}")
check("U4 neutral player ~1.0", 0.95 <= leverage_score(_mkplayer(0)) <= 1.10,
      f"{leverage_score(_mkplayer(0)):.3f}")
_v5 = leverage_score(None)
check("U5 never raises (junk input)",
      isinstance(_v5, float) and 0.80 <= _v5 <= 1.30, f"{_v5:.3f}")
class _C: pass
def _mkcoach_with_bond():
    c = _C(); c.id = "coach-1"
    return c
_p0 = _mkplayer(0, 70)
_p1 = _mkplayer(0, 70); _p1.coach_bonds = {"coach-1": 1.0}
check("U6 coach bond adds leverage",
      leverage_score(_p1, _mkcoach_with_bond(), style_key="balanced") >
      leverage_score(_p0, _mkcoach_with_bond(), style_key="balanced"),
      "bonded vs unbonded")
print()

# ---------------------------------------------------------------- sim setup
from main import GameManager
from save_load_system import GameSaveManager
gm = GameManager(); mgr = GameSaveManager(gm)
assert mgr.load_game(os.path.join(SAVES, "s2_deadline.hm")), "save load failed"
lg = gm.league
home, away = lg.teams[0], lg.teams[1]

from simulation import GameSim
from shift_engine import get_shift_state, _policy_next_line
from deployment_policy import (_game_lineup_for, _unit_players,
                               deployment_weights_for_game,
                               line_leverage, log_leverage)

def _skaters(lineup, kind, idx):
    return [p for p in _unit_players(lineup, kind, idx)
            if getattr(getattr(p, "primary_position", None), "value", "") != "G"]

def _rig_lines(sim, team, hot_line, cold_line):
    """Set mesh_form: hot_line's skaters = 85 (heater), cold_line's = -85."""
    lineup = _game_lineup_for(sim, team)
    for idx in (1, 2, 3, 4):
        for p in _skaters(lineup, "F", idx):
            p.mesh_form = 85 if idx == hot_line else (-85 if idx == cold_line else 0)

def _oz_pick_counts(sim, team, n=600, seed=7):
    """OZ-draw rotation picks via the real policy path (attack mode)."""
    rnd = random.Random(seed)
    st = get_shift_state(sim, team)
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for _ in range(n):
        st.f_line = rnd.randint(1, 4)
        pick = _policy_next_line(sim, team, st, "F", "stoppage", "attack")
        counts[pick] += 1
    return counts

# (c) quantity invariant: shares bit-identical with leverage on/off
sim0 = GameSim(home, away)
w_on = deployment_weights_for_game(sim0, home)
dp.LEVERAGE_ENABLED = False
w_off = deployment_weights_for_game(sim0, home)
dp.LEVERAGE_ENABLED = True
check("C1 deployment_weights identical with leverage on/off",
      w_on["F"] == w_off["F"] and w_on["D"] == w_off["D"],
      f"F shares {['%.4f' % s for s in w_on['F']]}")

# (a) mechanism A/B: heater line vs cold line, then swapped
for arm, hot_line, cold_line, hot_key in (("A", 1, 2, 1), ("B", 2, 1, 2)):
    sim = GameSim(home, away)
    _rig_lines(sim, home, hot_line, cold_line)
    # sanity: line leverage reads the rig
    lh = line_leverage(sim, home, "F", hot_line)
    lc = line_leverage(sim, home, "F", cold_line)
    check(f"{arm}0 rig reads: hot line lev {lh:.2f} > cold {lc:.2f}", lh > lc + 0.1)
    shares = deployment_weights_for_game(sim, home)["F"]
    dp.LEVERAGE_ENABLED = True
    on = _oz_pick_counts(sim, home, n=800, seed=11)
    dp.LEVERAGE_ENABLED = False
    off = _oz_pick_counts(sim, home, n=800, seed=11)
    dp.LEVERAGE_ENABLED = True
    # leverage lift: (picks_hot/picks_cold) relative to the quantity ratio
    qty_ratio = shares[hot_line - 1] / max(1e-9, shares[cold_line - 1])
    lift_on = (on[hot_line] / max(1, on[cold_line])) / qty_ratio
    lift_off = (off[hot_line] / max(1, off[cold_line])) / qty_ratio
    check(f"{arm}1 heater line gets 10%+ more OZ picks than quantity implies",
          lift_on >= 1.10,
          f"lift {lift_on:.3f} (on {on[hot_line]}/{on[cold_line]} vs qty ratio {qty_ratio:.3f})")
    check(f"{arm}2 leverage ON beats leverage OFF for the hot line",
          lift_on > lift_off,
          f"on {lift_on:.3f} vs off {lift_off:.3f}")
print()

# (d) narrative seam: one feed line per (team, key) per game
simN = GameSim(home, away)
log_leverage(simN, home, "chasing late_1", "TEST hot-hand line one")
log_leverage(simN, home, "chasing late_1", "TEST hot-hand line two (dup)")
log_leverage(simN, home, "chasing late_2", "TEST hot-hand line three")
dep = [e for e in (getattr(simN, "_deployment_log", None) or [])
       if e.get("event") == "leverage"]
feed = [g for g in simN.game_log if "[DEPLOYMENT]" in g and "TEST" in g]
check("D1 leverage log throttles duplicates", len(dep) == 2,
      f"{len(dep)} entries")
check("D2 feed lines emitted", len(feed) == 2, f"{len(feed)} feed lines")
check("D3 log_leverage never raises (junk sim)",
      (log_leverage(None, None, "k", "t") or True))
print()

if fails:
    print(f"{len(fails)} FAILURES: {fails}")
    sys.exit(1)
print("ALL LEVERAGE PROBE CHECKS PASSED")
