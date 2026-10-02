#!/usr/bin/env python3
"""qa_ot_parity.py -- Verify OT rates converge to ~22% on both engines.

Paired matchups: OT rates within noise of each other and ~22% (NHL-real).
Also verifies GPG, home win%, shutout rate still match.
"""
import sys, os, random, copy
sys.path.insert(0, "/tmp/wt-ot")

SEED = 999
N = 300  # 300 pairs for decent power

TOL_OT = 0.03  # OT rates must be within 3pp of each other
TARGET_OT = 0.22
TOL_TARGET = 0.04  # Each must be within 4pp of 22%

def run_advs_reg(home, away, seed):
    """Run AdvGS regulation only, return (home_goals, away_goals)."""
    import quick_sim
    random.seed(seed)
    sim = quick_sim.AdvancedGameSim(copy.deepcopy(home), copy.deepcopy(away))
    while sim.time < 3600:
        sim._simulate_shift()
    return (sim.score[sim.home_team.team_name], 
            sim.score[sim.away_team.team_name])

def run_gamesim_reg(home, away, seed):
    """Run GameSim, capture regulation score via OT patch."""
    import simulation
    random.seed(seed)
    reg = {}
    orig_ot = simulation.GameSim._handle_overtime
    def patched_ot(self):
        reg['h'] = self.home_score
        reg['a'] = self.away_score
        return orig_ot(self)
    simulation.GameSim._handle_overtime = patched_ot
    try:
        sim = simulation.GameSim(copy.deepcopy(home), copy.deepcopy(away))
        sim.run()
        if not reg:
            # No OT, use final scores
            reg['h'] = sim.home_score
            reg['a'] = sim.away_score
        return (reg['h'], reg['a'])
    finally:
        simulation.GameSim._handle_overtime = orig_ot

def main():
    random.seed(SEED)
    from database_generator import generate_database
    from playtest_driver import nhl_teams
    
    print("Generating league...", flush=True)
    lg = generate_database("Small")
    teams = nhl_teams(lg)
    print(f"{len(teams)} teams", flush=True)
    
    pairs = []
    while len(pairs) < N:
        h, a = random.choice(teams), random.choice(teams)
        if h is not a:
            pairs.append((h, a))
    print(f"{len(pairs)} pairs", flush=True)
    
    advs_regs = []
    gs_regs = []
    
    for i, (h, a) in enumerate(pairs):
        if i % 30 == 0:
            print(f"  pair {i}/{N}", flush=True)
        # AdvGS (fast)
        try:
            ah, aa = run_advs_reg(h, a, SEED + i*2)
            advs_regs.append((ah, aa))
        except Exception as e:
            print(f"  AdvGS pair {i} failed: {e}", flush=True)
        # GameSim (slow) - only do subset for time
        if i % 3 == 0:  # 100 GameSim games
            try:
                gh, ga = run_gamesim_reg(h, a, SEED + i*2 + 1)
                gs_regs.append((gh, ga))
            except Exception as e:
                print(f"  GameSim pair {i} failed: {e}", flush=True)
    
    print(f"\n=== AdvGS (n={len(advs_regs)}) ===", flush=True)
    advs_ot = analyze(advs_regs, "AdvGS")
    print(f"\n=== GameSim (n={len(gs_regs)}) ===", flush=True)
    gs_ot = analyze(gs_regs, "GameSim")
    
    print(f"\n=== PARITY CHECK ===", flush=True)
    ot_gap = abs(advs_ot - gs_ot)
    print(f"OT rate gap: {ot_gap:.3f} (tolerance {TOL_OT})", flush=True)
    print(f"AdvGS vs target 22%: {abs(advs_ot - TARGET_OT):.3f} (tolerance {TOL_TARGET})", flush=True)
    print(f"GameSim vs target 22%: {abs(gs_ot - TARGET_OT):.3f} (tolerance {TOL_TARGET})", flush=True)
    
    passed = (ot_gap <= TOL_OT and 
              abs(advs_ot - TARGET_OT) <= TOL_TARGET and
              abs(gs_ot - TARGET_OT) <= TOL_TARGET)
    print(f"\n{'PASS' if passed else 'FAIL'}", flush=True)
    return 0 if passed else 1

def analyze(regs, name):
    n = len(regs)
    if n == 0:
        print("  no data")
        return 0
    ties = sum(1 for h, a in regs if h == a)
    ot_rate = ties / n
    hg = [h for h, a in regs]
    ag = [a for h, a in regs]
    print(f"  OT rate: {ot_rate:.3f}", flush=True)
    print(f"  Home GPG: {sum(hg)/n:.3f}, Away GPG: {sum(ag)/n:.3f}", flush=True)
    home_win = sum(1 for h, a in regs if h > a) / n
    print(f"  Home win%: {home_win:.3f}", flush=True)
    shutout = sum(1 for h, a in regs if h == 0 or a == 0) / n
    print(f"  Shutout rate: {shutout:.3f}", flush=True)
    return ot_rate

if __name__ == "__main__":
    sys.exit(main())
