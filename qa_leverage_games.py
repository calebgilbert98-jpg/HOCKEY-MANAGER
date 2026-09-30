#!/usr/bin/env python3
"""Within-line differentiation -- full-game verification.

  (b) GPG A/B: 200 games with leverage ON vs 200 with OFF (same seeds and
      matchup rotation). Expect no meaningful move vs the 2.058 baseline --
      leverage redistributes premium minutes WITHIN a team, it never touches
      goal probabilities.
  (a2) points/60 A/B: one 2nd-line winger rigged HOT (mesh_form=85) vs COLD
      (mesh_form=-85), 100 games each, re-rigged every game (mesh_form only
      updates post-game). Expect: TOI ~equal (quantity untouched) and a
      directional points/60 lift for the heater (better minutes, not more).

Run headless:  DISPLAY=:99 python3 qa_leverage_games.py
"""
import sys, os, random

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
from deployment_policy import get_game_toi
from main import GameManager
from save_load_system import GameSaveManager
gm = GameManager(); mgr = GameSaveManager(gm)
assert mgr.load_game(os.path.join(SAVES, "s2_deadline.hm")), "save load failed"
lg = gm.league
nhl = [t for t in lg.teams
       if "AHL" not in getattr(getattr(t, "league", None), "name", "")][:32]
if len(nhl) < 32:
    nhl = lg.teams[:32]
print(f"using {len(nhl)} teams for matchup rotation", flush=True)

from simulation import GameSim

def run_games(n, leverage_on, seed0=1000):
    """n games, rotating matchups; returns (total_goals, games)."""
    dp.LEVERAGE_ENABLED = leverage_on
    goals = 0
    m = len(nhl)
    for i in range(n):
        h, a = nhl[i % m], nhl[(i * 13 + 7) % m]
        if a is h:
            a = nhl[(i * 13 + 8) % m]
        random.seed(seed0 + i)
        sim = GameSim(h, a)
        sim.run()
        goals += sim.home_score + sim.away_score
    return goals, n

# ------------------------------------------------------------------ (b) GPG
N = 200
if os.environ.get("LEVERAGE_SKIP_GPG"):
    print("(GPG A/B skipped via LEVERAGE_SKIP_GPG)", flush=True)
else:
    g_on, n_on = run_games(N, True, seed0=5000)
    g_off, n_off = run_games(N, False, seed0=5000)
    gpg_on = g_on / n_on / 2
    gpg_off = g_off / n_off / 2
    print(f"GPG leverage ON : {gpg_on:.3f}  ({g_on} goals / {n_on} games)", flush=True)
    print(f"GPG leverage OFF: {gpg_off:.3f}  ({g_off} goals / {n_off} games)", flush=True)
    print(f"baseline (1312-game season): 2.058", flush=True)
    check("B1 GPG within noise of the OFF control",
          abs(gpg_on - gpg_off) < 0.25,
          f"delta {gpg_on - gpg_off:+.3f}")
    check("B2 GPG within noise of the 2.058 baseline",
          abs(gpg_on - 2.058) < 0.30, f"ON {gpg_on:.3f} vs 2.058")
    print()

# ------------------------------------------------------- (a2) points/60 A/B
# NOTE: every sim.run() mutates the league (post-game injuries at a 22%/
# team/game base rate + form updates), so each arm loads a FRESH league, and
# the probe aggregates over 36 players (12 teams x F1 line) x 40 games --
# single-player samples are pure injury lottery (verified 2026-09-30).
from deployment_policy import _game_lineup_for, _unit_players

N_TEAMS = 12
N2 = 60

def fresh_league():
    _gm = GameManager(); _mgr = GameSaveManager(_gm)
    assert _mgr.load_game(os.path.join(SAVES, "s2_deadline.hm"))
    _lg = _gm.league
    return [t for t in _lg.teams
            if "AHL" not in getattr(getattr(t, "league", None), "name", "")][:32]

def _f1_units(teams):
    """[(team, [3 F1 forwards])] for the first N_TEAMS teams."""
    out = []
    for team in teams[:N_TEAMS]:
        sim_tmp = GameSim(team, teams[N_TEAMS])
        lineup = _game_lineup_for(sim_tmp, team)
        players = [p for p in _unit_players(lineup, "F", 1)
                   if getattr(getattr(p, "primary_position", None),
                              "value", "") != "G"][:3]
        out.append((team, players))
    return out

def run_form_arm(n, mode, seed0):
    """mode 'hot'/'cold': F1 units rigged to mesh_form +/-85 every game.

    Returns (points, toi_seconds) aggregated over all probe players.
    """
    _nhl = fresh_league()
    units = _f1_units(_nhl)
    dp.LEVERAGE_ENABLED = True
    pts = toi = 0.0
    m = len(_nhl)
    for i in range(n):
        for team, players in units:
            for p in players:
                p.mesh_form = 85 if mode == "hot" else -85  # re-rig each game
        h = _nhl[i % N_TEAMS]
        a = _nhl[(i * 13 + 7) % m]
        if a is h:
            a = _nhl[(i * 13 + 8) % m]
        random.seed(seed0 + i)
        sim = GameSim(h, a)
        sim.run()
        for team, players in units:
            for p in players:
                gs = sim.game_stats.get(p.id, {})
                pts += gs.get('g', 0) + gs.get('a', 0)
                toi += get_game_toi(sim, p)
    return pts, toi

pts_hot, toi_hot = run_form_arm(N2, "hot", seed0=9000)
pts_cold, toi_cold = run_form_arm(N2, "cold", seed0=9000)
p60_hot = pts_hot / (toi_hot / 3600) if toi_hot else 0
p60_cold = pts_cold / (toi_cold / 3600) if toi_cold else 0
print(f"F1-line probe ({N_TEAMS} teams x 3 forwards x {N2} games):", flush=True)
print(f"HOT : {pts_hot:.0f} pts in {toi_hot/60:.0f} min -> {p60_hot:.2f} pts/60", flush=True)
print(f"COLD: {pts_cold:.0f} pts in {toi_cold/60:.0f} min -> {p60_cold:.2f} pts/60", flush=True)
toi_ratio = toi_hot / toi_cold if toi_cold else 0
# mesh_form legitimately moves quantity a touch (bounded +/-5% by the clamp);
# the check is that the heater's edge is NOT a minutes edge.
check("A3 heater TOI within the quantity-clamp band of cold TOI",
      0.90 <= toi_ratio <= 1.10, f"ratio {toi_ratio:.3f}")
check("A4 heater points/60 directionally above cold",
      p60_hot > p60_cold,
      f"{p60_hot:.2f} vs {p60_cold:.2f} "
      f"(lift {(p60_hot/p60_cold - 1)*100:+.1f}%)" if p60_cold else "")
print()

# A5: leverage ON vs OFF with form untouched -- quantity must not move.
# Aggregated over the F1 units of 12 teams so the injury lottery washes out.
def run_leverage_arm(n, leverage_on, seed0):
    _nhl = fresh_league()
    units = _f1_units(_nhl)
    dp.LEVERAGE_ENABLED = leverage_on
    toi = 0.0
    m = len(_nhl)
    for i in range(n):
        h = _nhl[i % N_TEAMS]
        a = _nhl[(i * 13 + 7) % m]
        if a is h:
            a = _nhl[(i * 13 + 8) % m]
        random.seed(seed0 + i)
        sim = GameSim(h, a)
        sim.run()
        for team, players in units:
            for p in players:
                toi += get_game_toi(sim, p)
    dp.LEVERAGE_ENABLED = True
    return toi

toi_on = run_leverage_arm(N2, True, seed0=9200)
toi_off = run_leverage_arm(N2, False, seed0=9200)
print(f"leverage ON  F1 TOI: {toi_on/60:.0f} min over {N2} games", flush=True)
print(f"leverage OFF F1 TOI: {toi_off/60:.0f} min over {N2} games", flush=True)
check("A5 leverage ON vs OFF: quantity (TOI) statistically unchanged",
      abs(toi_on - toi_off) / max(1, toi_off) < 0.07,
      f"ratio {toi_on/max(1,toi_off):.3f}")
print()

if fails:
    print(f"{len(fails)} FAILURES: {fails}")
    sys.exit(1)
print("ALL FULL-GAME LEVERAGE CHECKS PASSED")
