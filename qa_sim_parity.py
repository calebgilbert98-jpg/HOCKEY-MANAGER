#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_sim_parity.py -- lightweight vs AdvancedGameSim distribution parity.

Both engines simulate the SAME seeded team pairs (paired by matchup, not by
random draw). Measures per engine: home/away goals per game, score stddev,
home win %, OT rate, shutout rate, 1-goal-game rate, total-goals histogram,
and goal-differential response to team-strength gaps (scaling check).

Usage: python3 qa_sim_parity.py [--quick]
  --quick: 300 pairs (for iteration). Default: 2000 pairs.
Exit 0 = all deltas within tolerance, 1 = any failure.
"""
import sys, os, random, time, copy
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SEED = 20260929
N_PAIRS = 2000
QUICK = "--quick" in sys.argv
if QUICK:
    N_PAIRS = 300

# Tolerances (task spec; report actuals honestly)
TOL_OT = 0.02
TOL_GPG = 0.10
TOL_HOMEWIN = 0.02
TOL_SHUTOUT = 0.02
TOL_ONEGOAL = 0.03
TOL_STD = 0.15

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" -- {detail}" if detail else ""))


def collect(engine_name, games):
    """games: list of (home_goals, away_goals, went_ot, home_won)."""
    n = len(games)
    hg = [g[0] for g in games]
    ag = [g[1] for g in games]
    import statistics
    return {
        "n": n,
        "home_gpg": sum(hg) / n,
        "away_gpg": sum(ag) / n,
        "home_std": statistics.pstdev(hg),
        "away_std": statistics.pstdev(ag),
        "home_win": sum(1 for g in games if g[3]) / n,
        "ot_rate": sum(1 for g in games if g[2]) / n,
        "shutout": sum(1 for g in games if g[0] == 0 or g[1] == 0) / n,
        "one_goal": sum(1 for g in games if abs(g[0] - g[1]) == 1) / n,
        "total_hist": Counter(g[0] + g[1] for g in games),
    }


def main():
    random.seed(SEED)
    from database_generator import generate_database
    from playtest_driver import nhl_teams

    print("generating league ...")
    lg = generate_database("Small")
    teams = nhl_teams(lg)
    print(f"league ready: {len(teams)} NHL teams")

    pairs = []
    while len(pairs) < N_PAIRS:
        h, a = random.choice(teams), random.choice(teams)
        if h is not a:
            pairs.append((h, a))
    print(f"{len(pairs)} pairs")

    # ---- lightweight (bare-GUI trick, production-like league context) ----
    import main as main_mod
    gui = main_mod.HockeyManagerGUI.__new__(main_mod.HockeyManagerGUI)
    gui._strength_cache = {}
    gui.notable_events = []
    gui.add_news = None
    gui.app = None
    gui.league = lg
    lw = main_mod.HockeyManagerGUI._simulate_game_lightweight.__get__(gui)

    t0 = time.time()
    lw_games = []
    for i, (h, a) in enumerate(pairs):
        # Deep-copy per game: prevents injuries/mutations from one game
        # leaking into the next; reseed after setup so each pair is an
        # independent draw.
        hc, ac = copy.deepcopy(h), copy.deepcopy(a)
        random.seed(SEED + i)
        _w, _l, (hs, ag), went_ot = lw(hc, ac, preseason=True)
        lw_games.append((hs, ag, went_ot, hs > ag))
    t_lw = time.time() - t0

    # ---- AdvancedGameSim (reference; untouched) ----
    from quick_sim import AdvancedGameSim
    t0 = time.time()
    adv_games = []
    for i, (h, a) in enumerate(pairs):
        hc, ac = copy.deepcopy(h), copy.deepcopy(a)
        random.seed(SEED + 7919 + i)
        sim = AdvancedGameSim(hc, ac, league=lg)
        winner, loser, (hs, ag), events, notable = sim.run()
        is_ot = any(isinstance(_e, dict) and _e.get("period", 0) > 3
                    for _e in (notable or []))
        adv_games.append((hs, ag, is_ot, winner is hc))
    t_adv = time.time() - t0

    L = collect("lightweight", lw_games)
    A = collect("advanced", adv_games)

    print(f"\nlightweight: {t_lw:.1f}s for {len(pairs)} games "
          f"({1000*t_lw/len(pairs):.2f} ms/game)")
    print(f"advanced:    {t_adv:.1f}s for {len(pairs)} games "
          f"({1000*t_adv/len(pairs):.2f} ms/game)")

    def row(metric, lf, af, tol):
        d = abs(lf - af)
        flag = "OK " if d <= tol else "GAP"
        print(f"  [{flag}] {metric:22s} light={lf:6.3f} adv={af:6.3f} "
              f"delta={d:6.3f} (tol {tol})")
        return d <= tol

    print("\n--- divergence table ---")
    ok = True
    ok &= row("home goals/game", L["home_gpg"], A["home_gpg"], TOL_GPG)
    check("home GPG within tol", abs(L["home_gpg"] - A["home_gpg"]) <= TOL_GPG,
          f"{L['home_gpg']:.3f} vs {A['home_gpg']:.3f}")
    ok &= row("away goals/game", L["away_gpg"], A["away_gpg"], TOL_GPG)
    check("away GPG within tol", abs(L["away_gpg"] - A["away_gpg"]) <= TOL_GPG,
          f"{L['away_gpg']:.3f} vs {A['away_gpg']:.3f}")
    ok &= row("home score stddev", L["home_std"], A["home_std"], TOL_STD)
    check("home stddev within tol", abs(L["home_std"] - A["home_std"]) <= TOL_STD,
          f"{L['home_std']:.3f} vs {A['home_std']:.3f}")
    ok &= row("away score stddev", L["away_std"], A["away_std"], TOL_STD)
    check("away stddev within tol", abs(L["away_std"] - A["away_std"]) <= TOL_STD,
          f"{L['away_std']:.3f} vs {A['away_std']:.3f}")
    ok &= row("home win %", L["home_win"], A["home_win"], TOL_HOMEWIN)
    check("home win% within tol", abs(L["home_win"] - A["home_win"]) <= TOL_HOMEWIN,
          f"{L['home_win']:.3f} vs {A['home_win']:.3f}")
    ok &= row("OT rate", L["ot_rate"], A["ot_rate"], TOL_OT)
    check("OT rate within tol", abs(L["ot_rate"] - A["ot_rate"]) <= TOL_OT,
          f"{L['ot_rate']:.3f} vs {A['ot_rate']:.3f}")
    ok &= row("shutout rate", L["shutout"], A["shutout"], TOL_SHUTOUT)
    check("shutout within tol", abs(L["shutout"] - A["shutout"]) <= TOL_SHUTOUT,
          f"{L['shutout']:.3f} vs {A['shutout']:.3f}")
    ok &= row("1-goal game rate", L["one_goal"], A["one_goal"], TOL_ONEGOAL)
    check("1-goal rate within tol", abs(L["one_goal"] - A["one_goal"]) <= TOL_ONEGOAL,
          f"{L['one_goal']:.3f} vs {A['one_goal']:.3f}")

    # ---- total-goals histogram ----
    print("\n--- total goals histogram (share) ---")
    print(f"  {'total':>5} {'light':>7} {'adv':>7}")
    for t in range(0, 13):
        ls = L["total_hist"].get(t, 0) / L["n"]
        as_ = A["total_hist"].get(t, 0) / A["n"]
        if ls > 0.005 or as_ > 0.005:
            print(f"  {t:>5} {ls:7.3f} {as_:7.3f}")

    # ---- scaling check: goal-differential response to strength gaps ----
    print("\n--- scaling: mean goal diff (home-away) by strength-gap quintile ---")
    diffs = []
    for (h, a), gl, ga in zip(pairs, lw_games, adv_games):
        try:
            sdiff = gui._calculate_team_strength(h) - gui._calculate_team_strength(a)
        except Exception:
            sdiff = 0.0
        diffs.append((sdiff, gl[0] - gl[1], ga[0] - ga[1]))
    diffs.sort(key=lambda t: t[0])
    q = len(diffs) // 5
    for i in range(5):
        seg = diffs[i * q:(i + 1) * q] if i < 4 else diffs[i * q:]
        if not seg:
            continue
        lm = sum(s[1] for s in seg) / len(seg)
        am = sum(s[2] for s in seg) / len(seg)
        print(f"  Q{i+1} (strength gap {seg[0][0]:+.3f}..{seg[-1][0]:+.3f}): "
              f"light margin={lm:+.3f} adv margin={am:+.3f} "
              f"delta={abs(lm-am):.3f}")
    seg_all_l = sum(s[1] for s in diffs) / len(diffs)
    seg_all_a = sum(s[2] for s in diffs) / len(diffs)
    check("scaling: overall mean margin within 0.15",
          abs(seg_all_l - seg_all_a) <= 0.15,
          f"light={seg_all_l:+.3f} adv={seg_all_a:+.3f}")

    n_fail = sum(1 for _n, c, _d in results if not c)
    print(f"\n{len(results) - n_fail}/{len(results)} checks green")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
