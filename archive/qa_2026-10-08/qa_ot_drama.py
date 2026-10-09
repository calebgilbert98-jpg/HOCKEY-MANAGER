#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_ot_drama.py -- QA for the OT drama rebuild (ot_drama.py live levers).

Muck's approved rebuild (2026-09-30): NO synthetic post-regulation
equalizer. Drama acts as three LIVE in-game levers on every path:

  1. pull_aggression_secs: high-drama games pull the goalie earlier
     (extra seconds on the shared goalie_pull window) -- GameSim + AdvGS
     execute the pull live; the lightweight path resolves the same
     decision via late_six_on_five (honest 6v5 segment: tying goal,
     empty-netter, or nothing -- all real goals).
  2. ot_matchup_tilt: 3v3 personnel/matchup choices tilt OT finishing,
     bounded +/-0.05 -- all three paths.
  3. shootout_edge: context nudge on the shared player_traits shootout
     core -- both shift paths (lightweight OT always resolves).

Covers:
  A. Pure lever units: bounds, monotonicity, determinism, never-raises.
  B. No synthetic equalizer: late_equalizer_roll is gone from the module
     and from every call site.
  C. Short smoke: lightweight + AdvGS OT rates sane, home OT win share
     sane, no crashes; one GameSim game completes with the new hooks.
  D. GPG watch: paired drama-on vs drama-bypassed lightweight runs --
     prints the directional delta for Muck's calibration (not asserted
     tight; the 6v5 segment scores real goals by design).

Usage: python3 qa_ot_drama.py [--quick]
  --quick: 120 games/path (for iteration).
Exit 0 = all green, 1 = any failure.
"""
import sys, os, random, types
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SEED = 20260930
N_GAMES = 500
QUICK = "--quick" in sys.argv
if QUICK:
    N_GAMES = 120

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" -- {detail}" if detail else ""))


def main():
    random.seed(SEED)
    import ot_drama

    # ---------------------------------------------------------- A. levers
    print("== A. pure lever units ==")
    check("A1. synthetic equalizer removed from module",
          not hasattr(ot_drama, "late_equalizer_roll"))
    check("A2. equalizer constants removed",
          not any(hasattr(ot_drama, n) for n in
                  ("EQUALIZER_RATE", "EQUALIZER_P_CAP", "INDUCED_OT_CAP",
                   "LIGHTWEIGHT_ONE_GOAL_SHARE", "ADVANCED_ONE_GOAL_SHARE",
                   "DEFAULT_ONE_GOAL_SHARE")))

    _neutral = {"ot_mult": 1.0, "home_win_edge": 0.0, "drama01": 0.3,
                "drivers": []}
    _hot = {"ot_mult": 1.35, "home_win_edge": 0.15, "drama01": 1.0,
            "drivers": ["Bad blood"]}
    check("A3. pull aggression 0 at neutral",
          ot_drama.pull_aggression_secs(_neutral) == 0.0)
    check("A4. pull aggression maxed at full drama",
          ot_drama.pull_aggression_secs(_hot) == ot_drama.PULL_AGGRESSION_MAX_SECS)
    _mid = dict(_hot, drama01=0.65)
    check("A5. pull aggression monotonic",
          0.0 < ot_drama.pull_aggression_secs(_mid)
          < ot_drama.PULL_AGGRESSION_MAX_SECS)
    check("A6. pull aggression never raises",
          ot_drama.pull_aggression_secs(None) == 0.0
          and ot_drama.pull_aggression_secs({}) == 0.0)

    _hc = types.SimpleNamespace(tactical_knowledge=90, match_preparation=85,
                                attacking_coaching=88)
    _ac = types.SimpleNamespace(tactical_knowledge=50, match_preparation=50,
                                attacking_coaching=50)
    _t0 = ot_drama.ot_matchup_tilt(_neutral)
    _t_hot = ot_drama.ot_matchup_tilt(_hot, home_coach=_hc, away_coach=_ac)
    _t_no_coach = ot_drama.ot_matchup_tilt(_hot)
    check("A7. matchup tilt bounded +/-0.05",
          all(abs(ot_drama.ot_matchup_tilt(
              {"home_win_edge": e}, home_coach=_hc, away_coach=_ac)) <= 0.05
              for e in (-0.15, 0.0, 0.15)))
    check("A8. matchup tilt sign follows home edge",
          _t_hot > 0 and ot_drama.ot_matchup_tilt(
              {"home_win_edge": -0.15}, home_coach=_hc,
              away_coach=_ac) < 0)
    check("A9. coach acumen gap moves the tilt",
          _t_hot > _t_no_coach,
          f"with coaches={_t_hot:+.4f} without={_t_no_coach:+.4f}")
    check("A10. neutral context -> zero tilt", _t0 == 0.0)
    check("A11. tilt never raises",
          ot_drama.ot_matchup_tilt(None) == 0.0)

    # 6v5 segment rates: 20k rolls, seeded rng for determinism.
    _r = random.Random(7)
    _outs = Counter(ot_drama.late_six_on_five(_neutral, rng=_r)[0]
                    for _ in range(20000))
    _tie = _outs["tie"] / 20000
    _en = _outs["empty_net"] / 20000
    check("A12. 6v5 outcomes valid",
          set(_outs) <= {"tie", "empty_net", "none"})
    check("A13. neutral 6v5: tie ~15%, EN ~24%",
          0.10 <= _tie <= 0.20 and 0.18 <= _en <= 0.30,
          f"tie={_tie:.1%} en={_en:.1%}")
    _r2 = random.Random(7)
    _outs_hot = Counter(ot_drama.late_six_on_five(_hot, rng=_r2)[0]
                        for _ in range(20000))
    _tie_hot = _outs_hot["tie"] / 20000
    check("A14. drama pulls earlier -> more late ties (honest mechanism)",
          _tie_hot > _tie,
          f"hot tie={_tie_hot:.1%} vs neutral tie={_tie:.1%}")
    _seg, _secs = ot_drama.late_six_on_five(_hot, trailing_team_is_home=True)
    check("A15. hot pull window = base + aggression",
          abs(_secs - (ot_drama.SIX_ON_FIVE_BASE_SECS
                       + ot_drama.PULL_AGGRESSION_MAX_SECS)) < 1e-9,
          f"{_secs:.0f}s")
    check("A16. 6v5 never raises",
          ot_drama.late_six_on_five(None, rng=random.Random(1))[0] in
          ("tie", "empty_net", "none"))

    # Shootout edge (unchanged semantics).
    se_home = ot_drama.shootout_edge(_hot, shooter_is_home=True)
    se_away = ot_drama.shootout_edge(_hot, shooter_is_home=False)
    check("A17. shootout edge bounded +/-0.06, antisymmetric",
          abs(se_home) <= 0.06 and abs(se_home + se_away) < 1e-9,
          f"home={se_home:+.3f} away={se_away:+.3f}")
    check("A18. neutral context -> zero shootout edge",
          ot_drama.shootout_edge({"home_win_edge": 0.0}, True) == 0.0)

    # ot_context still aggregates the five factors.
    from database_generator import generate_database
    from playtest_driver import nhl_teams
    print("generating league ...")
    lg = generate_database("Small")
    teams = nhl_teams(lg)
    assert len(teams) >= 4, "need NHL teams"
    print(f"league ready: {len(teams)} NHL teams")
    h, a = teams[0], teams[1]
    ka = ("team", h.team_name)
    kb = ("team", a.team_name)
    ka, kb = (ka, kb) if ka <= kb else (kb, ka)
    hot_league = types.SimpleNamespace(rivalries=[
        {"a": ka, "b": kb, "kind": "team_team", "intensity": 80,
         "a_name": h.team_name, "b_name": a.team_name}])
    ctx_hot = ot_drama.ot_context(h, a, league=hot_league,
                                  atmosphere={"energy": 90})
    ctx_cold = ot_drama.ot_context(h, a, league=None,
                                   atmosphere={"energy": 50})
    check("A19. ot_mult higher for hot context",
          ctx_hot["ot_mult"] > ctx_cold["ot_mult"] + 0.10,
          f"hot={ctx_hot['ot_mult']:.3f} cold={ctx_cold['ot_mult']:.3f} "
          f"drivers={ctx_hot['drivers']}")
    check("A20. pull aggression higher for hot context",
          ot_drama.pull_aggression_secs(ctx_hot)
          > ot_drama.pull_aggression_secs(ctx_cold))

    # ---------------------------------------------------------- B. smoke
    print("== B. engine smoke ==")
    import main as main_mod
    gui = main_mod.HockeyManagerGUI.__new__(main_mod.HockeyManagerGUI)
    gui.league = lg
    gui._strength_cache = {}
    gui.notable_events = []
    gui.add_news = None
    gui.app = None
    lw = main_mod.HockeyManagerGUI._simulate_game_lightweight.__get__(gui)

    lw_ot = lw_home_ot_wins = lw_goals = 0
    pairs = [(random.choice(teams), random.choice(teams))
             for _ in range(N_GAMES)]
    pairs = [(hh, aa) for hh, aa in pairs if hh is not aa]
    for hh, aa in pairs:
        _w, _l, (hs, ag), went_ot = lw(hh, aa, preseason=True)
        lw_goals += hs + ag
        if went_ot:
            lw_ot += 1
            if hs > ag:
                lw_home_ot_wins += 1
    lw_rate = lw_ot / len(pairs)
    lw_gpg = lw_goals / len(pairs)
    check("B1. lightweight OT rate sane (15-30%)",
          0.15 <= lw_rate <= 0.30, f"{lw_rate:.1%} ({lw_ot}/{len(pairs)})")
    check("B2. lightweight home OT win share sane (40-65%)",
          lw_ot == 0 or 0.40 <= (lw_home_ot_wins / lw_ot) <= 0.65,
          f"{(lw_home_ot_wins / max(1, lw_ot)):.1%} of OT games")
    print(f"    lightweight GPG: {lw_gpg:.3f}")

    # B2b. The 6v5 lever must actually FIRE end-to-end (a kwarg-name
    # mismatch once left it dead behind `except: pass`). Spy with the
    # exact production signature; assert it gets called on 1-goal games.
    _seg_calls = []
    _real_65_b = ot_drama.late_six_on_five
    def _spy_65(ctx, trailing_team_is_home=False, rng=None):
        _seg_calls.append(trailing_team_is_home)
        return _real_65_b(ctx, trailing_team_is_home=trailing_team_is_home,
                          rng=rng)
    ot_drama.late_six_on_five = _spy_65
    try:
        for hh, aa in pairs[:60]:
            lw(hh, aa, preseason=True)
    finally:
        ot_drama.late_six_on_five = _real_65_b
    check("B2b. 6v5 segment fires on 1-goal games (no dead lever)",
          len(_seg_calls) > 0, f"{len(_seg_calls)} segment calls / 60 games")

    from quick_sim import AdvancedGameSim
    adv_ot = adv_home_ot_wins = adv_goals = 0
    for hh, aa in pairs:
        sim = AdvancedGameSim(hh, aa, league=lg)
        winner, loser, (hs, ag), events, notable = sim.run()
        adv_goals += hs + ag
        is_ot = any(isinstance(_e, dict) and _e.get("period", 0) > 3
                    for _e in (notable or []))
        if is_ot:
            adv_ot += 1
            if winner is hh:
                adv_home_ot_wins += 1
    adv_rate = adv_ot / len(pairs)
    adv_gpg = adv_goals / len(pairs)
    check("B3. AdvancedGameSim OT rate sane (15-30%)",
          0.15 <= adv_rate <= 0.30, f"{adv_rate:.1%} ({adv_ot}/{len(pairs)})")
    check("B4. AdvancedGameSim home OT win share sane (40-65%)",
          adv_ot == 0 or 0.40 <= (adv_home_ot_wins / adv_ot) <= 0.65,
          f"{(adv_home_ot_wins / max(1, adv_ot)):.1%} of OT games")
    print(f"    AdvancedGameSim GPG: {adv_gpg:.3f}")

    # One watched GameSim game: the new hooks (lazy ctx, pull aggression,
    # OT tilt, shootout edge) must not crash the detailed path.
    try:
        from simulation import GameSim
        _gh, _ga = teams[2], teams[3]
        _gsim = GameSim(_gh, _ga, rivalries=getattr(lg, "rivalries", []))
        _gsim.run()
        _gscore = (_gsim.home_score, _gsim.away_score)
        check("B5. GameSim completes with drama hooks",
              isinstance(_gscore, tuple) and sum(_gscore) >= 0,
              f"final {_gscore[0]}-{_gscore[1]}")
    except Exception as e:
        import traceback; traceback.print_exc()
        check("B5. GameSim completes with drama hooks", False, f"{e}")

    # ---------------------------------------------------------- D. GPG
    print("== D. GPG watch (directional, for calibration) ==")
    _real_ctx = ot_drama.ot_context
    _real_65 = ot_drama.late_six_on_five
    try:
        drama_goals = 0
        for i, (hh, aa) in enumerate(pairs):
            random.seed(SEED + 100000 + i)
            _w, _l, (hs, ag), _ot = lw(hh, aa, preseason=True)
            drama_goals += hs + ag
        on_gpg = drama_goals / len(pairs)
        # Bypass: neutral context + no 6v5 segment. main.py imports the
        # module lazily inside the method, so this monkeypatch lands.
        ot_drama.ot_context = lambda *a, **k: {
            "ot_mult": 1.0, "home_win_edge": 0.0, "drama01": 0.3,
            "drivers": []}
        ot_drama.late_six_on_five = lambda *a, **k: ("none", 0.0)
        bypass_goals = 0
        for i, (hh, aa) in enumerate(pairs):
            random.seed(SEED + 100000 + i)
            _w, _l, (hs, ag), _ot = lw(hh, aa, preseason=True)
            bypass_goals += hs + ag
        off_gpg = bypass_goals / len(pairs)
    finally:
        ot_drama.ot_context, ot_drama.late_six_on_five = _real_ctx, _real_65
    _delta = on_gpg - off_gpg
    print(f"    drama-on GPG={on_gpg:.3f} bypassed={off_gpg:.3f} "
          f"delta={_delta:+.3f} (directional; full-season validation later)")
    check("D1. drama GPG delta bounded (<0.30, directional flag)",
          abs(_delta) < 0.30, f"delta={_delta:+.3f}")

    print()
    n_pass = sum(1 for _, c, _ in results if c)
    n_fail = len(results) - n_pass
    print(f"{n_pass} passed, {n_fail} failed")
    for name, cond, detail in results:
        if not cond:
            print(f"  FAILED: {name} {detail}")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
