#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA/probe: WS1 deployment-layer parity on the AdvGS path.

Paired-context agreement checks (D11-style): the same roster state fed to
GameSim's deployment decisions and AdvGS's approximations must agree.

Covers the WS1 implementation:
  1. _line_governor_factor == soft_cap_adjust_shares' full per-line factor
     (TOI gradient x shared _condition_governor_mult x shared
     _injury_risk_governor_mult, same binding skater) -- exact agreement.
  2. Per-shift canonical energy accounting: on-ice drain matches the shared
     shift_energy_drain; benched skaters recover 0.22/s x recovery mult;
     goalies untouched; PK 1.7x / PP 0.7x terms.
  3. reset_game_fatigue at AdvGS game start (no stale pool leaks in).
  4. Intermission recovery between regulation periods (shared constants).
  5. condition_deployment_mult sheds the rotation pick for worn bodies.
  6. Full-game smoke: energy pool moves, no crashes.

Deliberately NOT covered here (documented leave-outs, see report):
  * leverage_score/line_leverage -- no faithful AdvGS hook.
  * usage_featured 10-GP review -- AdvGS never consumes the flag.
  * postgame wear feed for AdvGS TOI (main.py day-advance) -- flagged.

Usage: python3 qa_parity_ws1.py   (needs no display)
Exit 0 if all pass, 1 if any fail.
"""
import sys, os, random

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# pt.py chdir pitfall guard: every game module must come from THIS worktree.
import quick_sim as _qs_check
assert _qs_check.__file__.startswith(_HERE), (
    f"quick_sim imported from {_qs_check.__file__}, not {_HERE}")

PASS, FAIL = 0, 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}", flush=True)
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}", flush=True)


def make_league():
    random.seed(20261001)
    from game_classes import League, PlayerPosition
    from player_generator import PlayerGenerator
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    for team in league.teams[:2]:
        for _ in range(12):
            team.roster.append(gen.create_player(
                position=random.choice([PlayerPosition.CENTER,
                                        PlayerPosition.LEFT_WING,
                                        PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(6):
            team.roster.append(gen.create_player(
                position=PlayerPosition.DEFENSE, team_name=team.team_name))
        for _ in range(2):
            team.roster.append(gen.create_player(
                position=PlayerPosition.GOALIE, team_name=team.team_name))
        for p in team.roster:
            p.condition = 100.0
    return league


def skaters(team):
    from game_classes import PlayerPosition
    return [p for p in team.roster
            if getattr(getattr(p, "primary_position", None), "name", "")
            != "GOALIE"]


class StubSim:
    """Duck-typed GameSim for deployment_policy.soft_cap_adjust_shares."""
    def __init__(self, home_team, away_team, lineups, toi_by_id):
        self.home_team = home_team
        self.away_team = away_team
        self.lineups = lineups
        self.player_toi_seconds = dict(toi_by_id)
        self.home_score = 0
        self.away_score = 0
        self.period = 1
        self.clock = 1200.0
        self.is_playoff = False


def main():
    print("=== QA: WS1 deployment-layer parity (AdvGS) ===", flush=True)
    import condition_system as cs
    import deployment_policy as dp
    from quick_sim import AdvancedGameSim
    from condition_system import (get_game_energy, sync_game_energy,
                                  shift_energy_drain, condition_deployment_mult)

    league = make_league()
    H, A = league.teams[0], league.teams[1]
    HN, AN = H.team_name, A.team_name

    # ------------------------------------------------------------------
    print("\n[1. governor factor agreement: AdvGS vs GameSim]", flush=True)
    sim = AdvancedGameSim(H, A)
    fw_lines = sim.lineups[HN]["Forwards"]
    assert len(fw_lines) >= 4, "need 4 forward lines for the probe"

    # Paired context: identical TOI ledgers and player state on both paths.
    toi = {}
    scenarios = [
        # (line, binding toi s, energy, condition, playing_hurt)
        (0, 1500.0, 100.0, 100.0, False),   # mid-gradient, fresh
        (1, 1700.0, 20.0, 60.0, False),     # gradient + gassed + worn
        (2, 1000.0, 100.0, 75.0, True),     # fresh TOI, playing hurt
        (3, 2400.0, 100.0, 100.0, False),   # past the backstop -> 0.0
    ]
    for li, btoi, energy, cond, hurt in scenarios:
        line = fw_lines[li]
        for j, p in enumerate(line):
            pid = p.id
            t = btoi if j == 0 else 200.0
            toi[pid] = t
            sim.stats[HN][pid]["toi"] = t
            p.condition = cond if j == 0 else 100.0
            sync_game_energy(p, energy if j == 0 else 100.0)
            p.playing_hurt = bool(hurt and j == 0)
    # Everyone else: fresh, low TOI.
    for p in skaters(H):
        if p.id not in toi:
            toi[p.id] = 100.0
            sim.stats[HN][p.id]["toi"] = 100.0
            p.condition = 100.0
            sync_game_energy(p, 100.0)
            p.playing_hurt = False

    stub = StubSim(H, A, {HN: sim.lineups[HN], AN: sim.lineups[AN]}, toi)
    state = sim._governor_state(HN)
    start_s, full_s, backstop_s = state

    def expected_factor(line):
        star = max([p for p in line if p],
                   key=lambda p: sim.stats[HN][p.id]["toi"])
        worst = sim.stats[HN][star.id]["toi"]
        if worst >= backstop_s:
            return 0.0
        toi_g = (1.0 if worst <= start_s else
                 1.0 - 0.75 * dp._smoothstep((worst - start_s)
                                             / max(1.0, full_s - start_s)))
        return max(0.05, toi_g * dp._condition_governor_mult(star)
                   * dp._injury_risk_governor_mult(star))

    qs_f, exp_f = [], []
    for li in range(4):
        line = fw_lines[li]
        q = sim._line_governor_factor(HN, line, state)
        e = expected_factor(line)
        qs_f.append(q)
        exp_f.append(e)
        check(f"line {li+1}: AdvGS factor == shared-decision factor",
              abs(q - e) < 1e-9, f"(qs={q:.6f} expected={e:.6f})")

    shares_in = [0.4, 0.3, 0.2, 0.1]
    shares_out = dp.soft_cap_adjust_shares(stub, H, "F", list(shares_in))
    check("GameSim soft_cap returns 4 renormalized shares",
          len(shares_out) == 4 and abs(sum(shares_out) - 1.0) < 1e-9,
          f"({shares_out})")
    # Per-line factor ratios are recoverable from the renormalized shares:
    # out_i/in_i = f_i / sum(in_j f_j), so ratios cancel the normalizer.
    for li in range(4):
        gs_ratio = ((shares_out[li] / shares_in[li])
                    / (shares_out[0] / shares_in[0]))
        qs_ratio = qs_f[li] / qs_f[0] if qs_f[0] else 0.0
        check(f"line {li+1}: GameSim/AdvGS factor ratio agrees",
              abs(gs_ratio - qs_ratio) < 1e-9,
              f"(gs={gs_ratio:.6f} qs={qs_ratio:.6f})")
    check("backstop zeroes the line on both paths",
          qs_f[3] == 0.0 and shares_out[3] == 0.0,
          f"(qs={qs_f[3]} gs_share={shares_out[3]})")
    check("fresh legs neutral on both (line 1 ~= TOI-only gradient)",
          abs(qs_f[0] - (1.0 - 0.75 * dp._smoothstep((1500.0 - start_s)
                                                    / (full_s - start_s)))) < 1e-9)

    # ------------------------------------------------------------------
    print("\n[2. per-shift canonical energy accounting]", flush=True)
    sim2 = AdvancedGameSim(H, A)
    p_ice = skaters(H)[0]
    p_bench = skaters(H)[-1]
    from game_classes import PlayerPosition
    goalie = [p for p in H.roster
              if getattr(getattr(p, "primary_position", None),
                         "name", "") == "GOALIE"][0]
    for p in (p_ice, p_bench, goalie):
        sync_game_energy(p, 100.0 if p is not goalie else 100.0)
    sync_game_energy(p_bench, 50.0)
    sync_game_energy(goalie, 77.0)
    exp_drain = shift_energy_drain(p_ice, 45.0)
    sim2._apply_shift_energy(HN, [p_ice], [], shift_s=45.0)
    check("on-ice skater drains the shared shift cost",
          abs(get_game_energy(p_ice) - (100.0 - exp_drain)) < 1e-9,
          f"({get_game_energy(p_ice):.4f} vs {100.0 - exp_drain:.4f})")
    exp_rec = (cs.BENCH_RECOVERY_PER_S
               * cs.fatigue_recovery_mult(p_bench) * 45.0)
    check("benched skater recovers 0.22/s x recovery mult",
          abs(get_game_energy(p_bench) - (50.0 + exp_rec)) < 1e-9,
          f"({get_game_energy(p_bench):.4f} vs {50.0 + exp_rec:.4f})")
    check("goalie pool untouched", abs(get_game_energy(goalie) - 77.0) < 1e-9)
    # PK / PP terms.
    sync_game_energy(p_ice, 100.0)
    sim2.pk_team = HN
    sim2._apply_shift_energy(HN, [p_ice], [], shift_s=45.0)
    check("PK skaters drain 1.7x",
          abs(get_game_energy(p_ice)
              - (100.0 - shift_energy_drain(p_ice, 45.0, on_pk=True))) < 1e-9)
    sim2.pk_team = None
    sync_game_energy(p_ice, 100.0)
    sim2.pp_team = HN
    sim2._apply_shift_energy(HN, [p_ice], [], shift_s=45.0)
    check("PP skaters drain 0.7x",
          abs(get_game_energy(p_ice)
              - (100.0 - shift_energy_drain(p_ice, 45.0, on_pp=True))) < 1e-9)
    sim2.pp_team = None
    # shift_energy_drain mirrors the tick loop's stamina term.
    p_hi = skaters(H)[1]
    p_hi.stamina = 95
    p_lo = skaters(H)[2]
    p_lo.stamina = 30
    check("high stamina drains less than low stamina",
          shift_energy_drain(p_hi, 45.0) < shift_energy_drain(p_lo, 45.0))

    # ------------------------------------------------------------------
    print("\n[3. canonical pool reset at AdvGS game start]", flush=True)
    for p in skaters(H) + skaters(A):
        sync_game_energy(p, 5.0)
    sim3 = AdvancedGameSim(H, A)
    stale = [p for p in skaters(H) + skaters(A)
             if abs(get_game_energy(p) - 100.0) > 1e-9]
    check("all skaters reset to 100 on construction", not stale,
          f"({len(stale)} stale)")

    # ------------------------------------------------------------------
    print("\n[4. intermission recovery (regulation only)]", flush=True)
    sim4 = AdvancedGameSim(H, A)
    p_w = skaters(H)[3]
    sync_game_energy(p_w, 40.0)
    exp_ir = 12.0 * cs.fatigue_recovery_mult(p_w)
    sim4.time = 1199.0
    sim4.period = 1
    sim4._advance_time(2.0)  # crosses the horn into period 2
    check("period advanced", sim4.period == 2)
    check("intermission recovers shared INTERMISSION_RECOVERY x mult",
          abs(get_game_energy(p_w) - min(100.0, 40.0 + exp_ir)) < 1e-9,
          f"({get_game_energy(p_w):.4f})")
    sync_game_energy(p_w, 40.0)
    sim4.time = 3599.0
    sim4.period = 3
    sim4._advance_time(2.0)  # 3rd -> OT: no intermission breather
    check("no recovery before OT", abs(get_game_energy(p_w) - 40.0) < 1e-9,
          f"({get_game_energy(p_w):.4f})")

    # ------------------------------------------------------------------
    print("\n[5. condition_deployment_mult sheds the rotation pick]", flush=True)
    pg = make_league()      # identical seed -> identical rosters, paired
    pg2 = make_league()
    H5, A5 = pg.teams[0], pg.teams[1]
    H5c, A5c = pg2.teams[0], pg2.teams[1]
    HN5 = H5.team_name
    ctl = AdvancedGameSim(H5c, A5c)   # all-fresh control (separate objects)
    sim5 = AdvancedGameSim(H5, A5)
    for s, _h in ((ctl, H5c), (sim5, H5)):
        for p in skaters(_h):
            s.stats[_h.team_name][p.id]["fatigue"] = 5  # uniform: ties
    # Gas line 1 on the test sim (set AFTER lineup resolution so the
    # play-hurt pass can't scratch them out from under the probe).
    for p in sim5.lineups[HN5]["Forwards"][0]:
        p.condition = 40.0
    _fw, _df, _g, fw_idx, _di = sim5._select_lines_idx(HN5)
    check("gassed line deprioritized in rotation", fw_idx != 0,
          f"(picked line {fw_idx + 1})")
    _fw, _df, _g, fw_idx_c, _di = ctl._select_lines_idx(H5c.team_name)
    check("fresh control still rolls line 1 on ties", fw_idx_c == 0,
          f"(picked line {fw_idx_c + 1})")
    # Shared-function unit checks.
    p100 = skaters(H5)[0]; p100.condition = 100.0; p100.playing_hurt = False
    p80 = skaters(H5)[4]; p80.condition = 80.0; p80.playing_hurt = False
    p60 = skaters(H5)[1]; p60.condition = 60.0; p60.playing_hurt = False
    p40 = skaters(H5)[2]; p40.condition = 40.0; p40.playing_hurt = False
    p_h = skaters(H5)[3]; p_h.condition = 85.0; p_h.playing_hurt = True
    check("cdm fresh(>=90) == 1.03",
          abs(condition_deployment_mult(p100) - 1.03) < 1e-9)
    check("cdm good == 1.00", condition_deployment_mult(p80) == 1.00)
    check("cdm worn(<70) == 0.94",
          abs(condition_deployment_mult(p60) - 0.94) < 1e-9)
    check("cdm gassed(<50) == 0.85",
          abs(condition_deployment_mult(p40) - 0.85) < 1e-9)
    check("cdm playing_hurt x0.90",
          abs(condition_deployment_mult(p_h) - 0.90) < 1e-9)

    # ------------------------------------------------------------------
    print("\n[6. full-game smoke]", flush=True)
    moved = 0
    for i in range(3):
        s = AdvancedGameSim(H, A)
        s.run()
        n_toi = sum(v.get("toi", 0)
                    for v in s.stats[HN].values()) + sum(
                        v.get("toi", 0) for v in s.stats[AN].values())
        check(f"game {i}: TOI accumulates", n_toi > 0, f"({n_toi:.0f}s)")
        low = [p for p in skaters(H) + skaters(A)
               if get_game_energy(p) < 99.0]
        moved += len(low)
        check(f"game {i}: canonical pool moves in play", len(low) > 0,
              f"({len(low)} skaters <99)")
    check("pool drains over games (not pinned at 100)", moved > 0)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
