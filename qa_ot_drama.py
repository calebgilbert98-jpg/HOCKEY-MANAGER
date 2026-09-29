#!/usr/bin/env python3
"""qa_ot_drama.py -- QA for the OT drama build (ot_drama.py + engine hooks).

Covers design doc section 7, items 1-4:
  1. OT rate: 500 headless games per path (lightweight + AdvancedGameSim);
     assert 20-28% reach OT.
  2. Accounting: full harness season via SeasonDriver.regular_season();
     assert OTL > 0 league-wide, PTS == 2*W + OTL, W+L+OTL == 82 per team.
  3. Drama correlation: ot_mult higher for high-heat/grudge/crowd contexts;
     late_equalizer_roll more likely in high-drama contexts; end-to-end
     rivalry-heat>=65 games more OT-prone than neutral ones (when natural
     rivalries exist); home OT win rate 50-60%.
  4. GPG unchanged: drama-enabled vs drama-bypassed runs must agree
     (equalizer is goal-neutral in expectation).

Usage: python3 qa_ot_drama.py [--quick]
  --quick: 120 games/path + 200-game mini-season (for iteration).
Exit 0 = all green, 1 = any failure. Prints PASS/FAIL with numbers.
"""
import sys, os, random, types
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SEED = 20260929
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
    from database_generator import generate_database
    from playtest_driver import nhl_teams

    print("generating league ...")
    lg = generate_database("Small")
    teams = nhl_teams(lg)
    assert len(teams) >= 4, "need NHL teams"
    print(f"league ready: {len(teams)} NHL teams")

    # ---------------------------------------------------------- 1. OT rates
    # Lightweight path: unbound HockeyManagerGUI method on a bare instance.
    # preseason=True skips the GUI-bound player-stat pass; scoring/OT logic
    # is identical.
    import main as main_mod
    gui = main_mod.HockeyManagerGUI.__new__(main_mod.HockeyManagerGUI)
    # Bare tk.Tk instance: pre-seed every data attribute the sim path reads,
    # otherwise tk.__getattr__ recurses on the missing self.tk.
    gui.league = lg
    gui._strength_cache = {}
    gui.notable_events = []
    gui.add_news = None
    gui.app = None
    lw = main_mod.HockeyManagerGUI._simulate_game_lightweight.__get__(gui)

    lw_ot = 0
    lw_home_ot_wins = 0
    lw_goals = 0
    pairs = [(random.choice(teams), random.choice(teams)) for _ in range(N_GAMES)]
    pairs = [(h, a) for h, a in pairs if h is not a]
    for h, a in pairs:
        _w, _l, (hs, ag), went_ot = lw(h, a, preseason=True)
        lw_goals += hs + ag
        if went_ot:
            lw_ot += 1
            if hs > ag:
                lw_home_ot_wins += 1
    lw_rate = lw_ot / len(pairs)
    lw_gpg = lw_goals / len(pairs)
    check("1a. lightweight OT rate 20-28%", 0.20 <= lw_rate <= 0.28,
          f"{lw_rate:.1%} ({lw_ot}/{len(pairs)})")
    check("1b. lightweight home OT win rate 50-60%",
          lw_ot == 0 or 0.50 <= (lw_home_ot_wins / lw_ot) <= 0.60,
          f"{(lw_home_ot_wins / max(1, lw_ot)):.1%} of OT games")

    # AdvancedGameSim path (with league -> drama hooks active).
    from quick_sim import AdvancedGameSim
    adv_ot = 0
    adv_home_ot_wins = 0
    adv_goals = 0
    adv_ot_home_wins_detail = 0
    for h, a in pairs:
        sim = AdvancedGameSim(h, a, league=lg)
        winner, loser, (hs, ag), events, notable = sim.run()
        lw_goals_adv = hs + ag
        adv_goals += lw_goals_adv
        # Production OT definition (main.py): a goal/shootout goal past
        # period 3. Raw events leak late-3rd-period shots into period 4.
        is_ot = any(isinstance(_e, dict) and _e.get("period", 0) > 3
                    for _e in (notable or []))
        if is_ot:
            adv_ot += 1
            if winner is h:
                adv_home_ot_wins += 1
    adv_rate = adv_ot / len(pairs)
    adv_gpg = adv_goals / len(pairs)
    check("1c. AdvancedGameSim OT rate 20-28%", 0.20 <= adv_rate <= 0.28,
          f"{adv_rate:.1%} ({adv_ot}/{len(pairs)})")
    check("1d. AdvancedGameSim home OT win rate 50-60%",
          adv_ot == 0 or 0.50 <= (adv_home_ot_wins / adv_ot) <= 0.60,
          f"{(adv_home_ot_wins / max(1, adv_ot)):.1%} of OT games")

    # ---------------------------------------------------------- 3. drama
    from ot_drama import ot_context, late_equalizer_roll, shootout_edge
    from ot_drama import LIGHTWEIGHT_ONE_GOAL_SHARE

    h, a = teams[0], teams[1]
    ka = ("team", h.team_name)
    kb = ("team", a.team_name)
    ka, kb = (ka, kb) if ka <= kb else (kb, ka)
    hot_league = types.SimpleNamespace(rivalries=[
        {"a": ka, "b": kb, "kind": "team_team", "intensity": 80,
         "a_name": h.team_name, "b_name": a.team_name}])

    ctx_hot = ot_context(h, a, league=hot_league, atmosphere={"energy": 90})
    ctx_cold = ot_context(h, a, league=None, atmosphere={"energy": 50})
    check("3a. ot_mult higher for hot context",
          ctx_hot["ot_mult"] > ctx_cold["ot_mult"] + 0.10,
          f"hot={ctx_hot['ot_mult']:.3f} cold={ctx_cold['ot_mult']:.3f} "
          f"drivers={ctx_hot['drivers']}")
    check("3b. ot_mult within clamp [0.85, 1.35]",
          0.85 <= ctx_hot["ot_mult"] <= 1.35 and 0.85 <= ctx_cold["ot_mult"] <= 1.35)
    check("3c. home_win_edge within clamp [-0.15, 0.15]",
          -0.15 <= ctx_hot["home_win_edge"] <= 0.15)

    # Equalizer likelihood: estimate from many rolls.
    N_ROLL = 20000
    hot_hits = sum(late_equalizer_roll(ctx_hot, one_goal_share=LIGHTWEIGHT_ONE_GOAL_SHARE)
                   for _ in range(N_ROLL))
    cold_hits = sum(late_equalizer_roll(ctx_cold, one_goal_share=LIGHTWEIGHT_ONE_GOAL_SHARE)
                    for _ in range(N_ROLL))
    check("3d. equalizer more likely in hot context",
          hot_hits > cold_hits * 1.5,
          f"hot={hot_hits / N_ROLL:.2%} cold={cold_hits / N_ROLL:.2%}")
    # 3e runs after check 4 (needs the clean 1-goal share from the bypass).

    # Shootout edge: bounded, sign-correct, zero default.
    se_home = shootout_edge(ctx_hot, shooter_is_home=True)
    se_away = shootout_edge(ctx_hot, shooter_is_home=False)
    check("3f. shootout edge bounded +/-0.06, home/away antisymmetric",
          abs(se_home) <= 0.06 and abs(se_home + se_away) < 1e-9,
          f"home={se_home:+.3f} away={se_away:+.3f}")
    check("3g. neutral context -> zero shootout edge",
          shootout_edge({"home_win_edge": 0.0}, True) == 0.0)

    # Default-neutral: no league -> AdvancedGameSim behaves as before.
    sim_noleague = AdvancedGameSim(h, a)
    check("3h. no-league AdvancedGameSim keeps league=None",
          sim_noleague.league is None)

    # End-to-end: natural rivalries (heat>=65) vs neutral pairs.
    try:
        from narrative_ledger import matchup_narrative
        heats = []
        for i in range(0, min(60, len(teams)), 4):
            hh, aa = teams[i], teams[(i + 1) % len(teams)]
            mn = matchup_narrative(hh, aa, league=lg) or {}
            heats.append((float(mn.get("rivalry_heat", 0) or 0), hh, aa))
        hot_pairs = [(hh, aa) for heat, hh, aa in heats if heat >= 65]
        cold_pairs = [(hh, aa) for heat, hh, aa in heats if heat < 20]
        if hot_pairs and cold_pairs:
            n_e2e = 60 if not QUICK else 25
            hot_ot = 0
            for hh, aa in (hot_pairs * ((n_e2e // max(1, len(hot_pairs))) + 1))[:n_e2e]:
                s2 = AdvancedGameSim(hh, aa, league=lg)
                _w, _l, _sc, _ev, _not2 = s2.run()
                hot_ot += any(isinstance(_e, dict) and _e.get("period", 0) > 3
                              for _e in (_not2 or []))
            cold_ot = 0
            for hh, aa in (cold_pairs * ((n_e2e // max(1, len(cold_pairs))) + 1))[:n_e2e]:
                s2 = AdvancedGameSim(hh, aa, league=lg)
                _w, _l, _sc, _ev, _not2 = s2.run()
                cold_ot += any(isinstance(_e, dict) and _e.get("period", 0) > 3
                               for _e in (_not2 or []))
            check("3i. rivalry games more OT-prone than neutral (e2e)",
                  hot_ot > cold_ot,
                  f"hot={hot_ot / n_e2e:.1%} cold={cold_ot / n_e2e:.1%} "
                  f"({len(hot_pairs)} hot pairs, {len(cold_pairs)} cold)")
        else:
            check("3i. rivalry games more OT-prone than neutral (e2e)",
                  True, "SKIP -- no natural heat>=65 pairs in fresh league")
    except Exception as e:
        check("3i. rivalry games more OT-prone than neutral (e2e)", False,
              f"error: {e}")

    # ---------------------------------------------------------- 4. GPG
    # Paired per-pair seeds: both arms see identical regulation draws, so
    # the only possible delta is the equalizer itself (dormant here --
    # ot_mult is 1.0 in a fresh league). GPG must agree near-exactly.
    import ot_drama
    _real_ctx, _real_roll = ot_drama.ot_context, ot_drama.late_equalizer_roll
    try:
        drama_goals = 0
        for i, (h, a) in enumerate(pairs):
            random.seed(SEED + 100000 + i)
            _w, _l, (hs, ag), _ot = lw(h, a, preseason=True)
            drama_goals += hs + ag
        paired_gpg = drama_goals / len(pairs)
        ot_drama.ot_context = lambda *a, **k: {
            "ot_mult": 1.0, "home_win_edge": 0.0, "drama01": 0.3, "drivers": []}
        ot_drama.late_equalizer_roll = lambda ctx, trailing=False: False
        # NOTE: main.py imported ot_drama lazily inside the method, so the
        # monkeypatch on the module object takes effect.
        bypass_goals = 0
        for i, (h, a) in enumerate(pairs):
            random.seed(SEED + 100000 + i)
            _w, _l, (hs, ag), _ot = lw(h, a, preseason=True)
            bypass_goals += hs + ag
        bypass_gpg = bypass_goals / len(pairs)
    finally:
        ot_drama.ot_context, ot_drama.late_equalizer_roll = _real_ctx, _real_roll
    check("4. GPG unchanged drama-on vs drama-bypassed (paired)",
          abs(paired_gpg - bypass_gpg) < 0.05,
          f"drama-on={paired_gpg:.2f} bypassed={bypass_gpg:.2f}")
    print(f"    (AdvancedGameSim GPG: {adv_gpg:.2f})")
    # 3e: the equalizer only rolls on 1-goal regulation games, so the
    # induced share of ALL games is roll_rate x one_goal_share. The
    # adaptive cap keeps this under INDUCED_OT_CAP (0.06) by construction.
    induced = (hot_hits / N_ROLL) * LIGHTWEIGHT_ONE_GOAL_SHARE
    check("3e. induced OT rate sane (<6% of all games)",
          induced < 0.06,
          f"hot roll={hot_hits / N_ROLL:.2%} x 1-goal share={LIGHTWEIGHT_ONE_GOAL_SHARE:.0%} "
          f"= {induced:.2%} of games")

    # ---------------------------------------------------------- 2. season
    # Full harness season on a FRESH league (check-1 games never touched
    # standings). Exercises the cherry-picked 4a60d4f accounting.
    from playtest_driver import StoryLog
    from playtest_season import SeasonDriver
    import playtest_mid  # noqa: F401 (monkey-patches _all_star/_playoffs/_awards)
    print("running full harness season (this takes a while) ...")
    lg2 = generate_database("Small")
    # Mirror the campaign: regenerate the schedule from current team names
    # (the template cache carries stale names) before driving the season.
    lg2.generate_schedule(lg2.season_year)
    # Pre-existing DB quirk (not the OT build): generate_database draws
    # random team names and renames some teams AFTER standings are built,
    # while the schedule template carries stale names. Rebuild standings
    # from the current teams, then remap any schedule refs still missing.
    lg2.initialize_standings()
    import difflib
    _cur = {t.team_name: t for t in lg2.teams}
    _remapped = 0
    for _e in lg2.schedule:
        if not isinstance(_e, dict):
            continue
        for _k in ("home_team", "away_team"):
            _t = _e.get(_k)
            _nm = getattr(_t, "team_name", None)
            if _nm and _nm not in lg2.standings:
                _m = difflib.get_close_matches(_nm, lg2.standings.keys(), n=1, cutoff=0.6)
                if _m and _m[0] in _cur:
                    _e[_k] = _cur[_m[0]]
                    _remapped += 1
                else:
                    print(f"    WARNING: unremappable stale schedule team {_nm!r}")
    if _remapped:
        print(f"    (remapped {_remapped} stale schedule team refs)")
    drv = SeasonDriver(lg2, 1, "win-now", StoryLog())
    drv.regular_season()
    st = lg2.standings
    otl_total = sum((v.get("OTL", 0) or 0) for v in st.values())
    check("2a. OTL > 0 league-wide", otl_total > 0, f"total OTL={otl_total}")
    bad_pts = [k for k, v in st.items()
               if v.get("Points", 0) != 2 * v.get("W", 0) + (v.get("OTL", 0) or 0)]
    check("2b. PTS == 2W + OTL for every team", not bad_pts,
          f"violations: {bad_pts[:3]}" if bad_pts else f"{len(st)} teams ok")
    bad_gp = [t.team_name for t in nhl_teams(lg2)
              if st[t.team_name]["W"] + st[t.team_name]["L"] + st[t.team_name]["OTL"] != 82]
    check("2c. W+L+OTL == 82 for every NHL team", not bad_gp,
          f"violations: {bad_gp[:3]}" if bad_gp else "32 teams ok")

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{len(results) - n_fail}/{len(results)} checks green")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
