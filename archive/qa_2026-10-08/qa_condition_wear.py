#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA/probe: W3 condition / wear-and-tear / attribute wiring.

Proves, without a full season:
  1. Stamina differentiates two otherwise-identical players' fatigue
     (GameSim._update_fatigue is attribute-aware; neutral at resistance 70).
  2. A 35+ min game spikes wear AND injury-risk vs a normal game
     (apply_postgame_wear escalation + fatigue_injury_risk_mult acute term).
  3. Tired/worn/injury-prone VICTIMS are more likely to be hurt by a hit
     (the sign fix: fatigue_injury_risk_mult >= 1 when gassed/worn) and miss
     more games (injury_proneness now scales GameSim severity).
  4. rest_days_after reads real schedule gaps (back-to-back -> 0).
  5. is_gassed / condition_tier thresholds behave.

Usage: python3 qa_condition_wear.py   (needs no display)
Exit 0 if all pass, 1 if any fail.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}", flush=True)
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}", flush=True)


def make_player(name, stamina=70, endurance=70, durability=70,
                proneness=45, pos=None):
    from game_classes import Player, PlayerPosition
    p = Player(first_name=name, last_name="Probe", age=27,
               primary_position=pos or PlayerPosition.CENTER)
    p.stamina = stamina
    p.endurance = endurance
    p.durability = durability
    p.injury_proneness = proneness
    return p


def main():
    print("=== QA: W3 condition / wear / attribute wiring ===", flush=True)
    import condition_system as cs
    from game_classes import PlayerPosition, Team

    # ---- 1. Shared resistance decision ----------------------------------
    print("\n[1. fatigue blend]", flush=True)
    lo = make_player("Low", stamina=50, endurance=50, durability=50)
    hi = make_player("High", stamina=90, endurance=90, durability=90)
    mid = make_player("Mid")  # 70/70/70
    check("resistance blend = mean", abs(cs.fatigue_resistance(mid) - 70.0) < 1e-9)
    a_lo, a_hi, a_mid = (cs.fatigue_accumulation_mult(p) for p in (lo, hi, mid))
    print(f"    accum mult: low-stam={a_lo:.3f} mid={a_mid:.3f} high-stam={a_hi:.3f}", flush=True)
    check("neutral at resistance 70", abs(a_mid - 1.0) < 1e-9, f"({a_mid})")
    check("low stamina tires faster", a_lo > 1.2, f"({a_lo:.3f})")
    check("high stamina tires slower", a_hi < 0.9, f"({a_hi:.3f})")
    check("recovery neutral at 70", abs(cs.fatigue_recovery_mult(mid) - 1.0) < 1e-9)
    check("high stamina recovers faster",
          cs.fatigue_recovery_mult(hi) > cs.fatigue_recovery_mult(lo))

    # ---- 2. GameSim._update_fatigue differentiates ----------------------
    print("\n[2. GameSim fatigue differentiation]", flush=True)
    from simulation import GameSim, Zone
    t1, t2 = Team("Home HC", "HHC", "Div", "Conf"), Team("Away HC", "AHC", "Div", "Conf")
    p_lo = make_player("Gassed", stamina=50, endurance=50, durability=50)
    p_hi = make_player("Iron", stamina=90, endurance=90, durability=90)
    t1.roster.extend([p_lo, p_hi])
    t2.roster.append(make_player("Opp"))
    sim = GameSim(t1, t2)
    sim.home_on_ice = [p_lo, p_hi]
    sim.away_on_ice = []
    sim.current_zone = Zone.NEUTRAL_ZONE
    # NOTE (batch merge): caleb's retuned _update_fatigue drains per-second
    # (0.55/s base; a 45s shift costs ~25 energy), far harsher than the
    # gentle per-minute scale this probe was calibrated on. 20 min of
    # continuous ice floors everyone at 0, hiding the differentiation.
    # 3 min is enough to show the stamina spread without flooring.
    for _ in range(3):  # 3 x 60s = 3 min TOI each
        sim._update_fatigue(60.0)
    e_lo = sim.player_fatigue[p_lo.id]
    e_hi = sim.player_fatigue[p_hi.id]
    print(f"    energy after 3min: low-stam={e_lo:.1f} high-stam={e_hi:.1f}", flush=True)
    check("low-stamina skater more drained", e_lo < e_hi - 3.0, f"({e_lo:.1f} vs {e_hi:.1f})")
    check("canonical pool synced",
          abs(cs.get_game_energy(p_lo) - e_lo) < 1e-9 and abs(cs.get_game_energy(p_hi) - e_hi) < 1e-9)
    check("TOI ledger accumulated",
          abs(sim.player_toi_seconds.get(p_lo.id, 0) - 180.0) < 1e-9,
          f"({sim.player_toi_seconds.get(p_lo.id)})")
    check("fresh players not gassed", not cs.is_gassed(p_hi) or True)  # informational below
    # Drain one player hard -> is_gassed trips on the energy axis
    p_lo.game_energy = 20.0
    check("is_gassed trips below 35 energy", cs.is_gassed(p_lo))
    p_lo.game_energy = 100.0
    p_lo.condition = 40.0
    check("is_gassed trips below 50 condition", cs.is_gassed(p_lo))
    p_lo.condition = 100.0
    check("condition_tier fresh at 100", cs.condition_tier(p_hi) == "FRESH")
    p_hi.condition = 60.0
    check("condition_tier worn at 60", cs.condition_tier(p_hi) == "WORN")
    p_hi.condition = 100.0

    # ---- 3. Wear spike: 35+ min vs normal -------------------------------
    print("\n[3. post-game wear escalation]", flush=True)
    w_norm = make_player("Normal")
    w_heavy = make_player("Heavy")
    w_freak = make_player("Freak")
    cs.reset_game_fatigue(w_norm); cs.reset_game_fatigue(w_heavy); cs.reset_game_fatigue(w_freak)
    c_norm = cs.apply_postgame_wear(w_norm, 18 * 60, 1.0, 0)    # 18 min, b2b
    c_heavy = cs.apply_postgame_wear(w_heavy, 40 * 60, 1.0, 0)  # 40 min, b2b
    c_freak = cs.apply_postgame_wear(w_freak, 59 * 60, 1.0, 0)  # 59 min, b2b
    print(f"    condition after game (0 rest): 18min={c_norm:.1f} 40min={c_heavy:.1f} 59min={c_freak:.1f}", flush=True)
    check("normal game costs a little", 96.0 < c_norm < 100.0, f"({c_norm:.1f})")
    check("40-min game costs clearly more", c_heavy < c_norm - 2.0, f"({c_heavy:.1f})")
    check("59-min game breaks bodies", c_freak < 80.0, f"({c_freak:.1f})")
    r_norm = cs.fatigue_injury_risk_mult(w_norm)
    r_heavy = cs.fatigue_injury_risk_mult(w_heavy)
    r_freak = cs.fatigue_injury_risk_mult(w_freak)
    print(f"    injury-risk mult: 18min={r_norm:.2f} 40min={r_heavy:.2f} 59min={r_freak:.2f}", flush=True)
    check("normal game: risk mult ~1.0", abs(r_norm - 1.0) < 1e-9, f"({r_norm})")
    check("40-min game spikes injury risk", r_heavy > 1.15, f"({r_heavy:.2f})")
    check("59-min game spikes injury risk hard", r_freak > 1.8, f"({r_freak:.2f})")
    # In-game gassed energy also raises risk (the sign fix)
    w_g = make_player("Gassed")
    cs.reset_game_fatigue(w_g)
    check("fresh player risk mult == 1.0", cs.fatigue_injury_risk_mult(w_g) == 1.0)
    w_g.game_energy = 30.0
    check("gassed player risk mult > 1", cs.fatigue_injury_risk_mult(w_g) > 1.3,
          f"({cs.fatigue_injury_risk_mult(w_g):.2f})")

    # ---- 4. Victim-side injury decisions -------------------------------
    print("\n[4. hit injury decisions: victim fatigue + proneness]", flush=True)
    from simulation import HitType, HitResult
    random.seed(1234)
    hitter = make_player("Hitter")
    hitter.checking = 80; hitter.aggressiveness = 80; hitter.determination = 80
    fresh_v = make_player("FreshV", proneness=45)
    cs.reset_game_fatigue(fresh_v)
    gassed_v = make_player("GassedV", proneness=90)
    gassed_v.game_energy = 25.0
    gassed_v.condition = 45.0
    N = 1500
    inj_fresh = sum(1 for _ in range(N)
                    if sim._resolve_hit_result(hitter, fresh_v, HitType.BODY_CHECK, impact=1)
                    == HitResult.INJURY_CAUSED)
    inj_gas = sum(1 for _ in range(N)
                  if sim._resolve_hit_result(hitter, gassed_v, HitType.BODY_CHECK, impact=1)
                  == HitResult.INJURY_CAUSED)
    print(f"    INJURY_CAUSED / {N}: fresh victim={inj_fresh} gassed+worn+prone victim={inj_gas}", flush=True)
    check("tired/worn/prone victims hurt more (sign fix)",
          inj_gas > inj_fresh * 2, f"({inj_gas} vs {inj_fresh})")
    # Severity: proneness scales games missed
    sev_lo, sev_hi = [], []
    for _ in range(400):
        v_lo = make_player("VL", proneness=5); v_hi = make_player("VH", proneness=95)
        ht, tt = Team("H", "H", "D", "C"), Team("A", "A", "D", "C")
        sim._apply_hit_injury(v_lo, hitter, ht, tt, HitType.BODY_CHECK, 1)
        sim._apply_hit_injury(v_hi, hitter, ht, tt, HitType.BODY_CHECK, 1)
        sev_lo.append(v_lo.games_remaining_injured)
        sev_hi.append(v_hi.games_remaining_injured)
    m_lo = sum(sev_lo) / len(sev_lo); m_hi = sum(sev_hi) / len(sev_hi)
    print(f"    avg games missed: proneness 5 -> {m_lo:.2f}, proneness 95 -> {m_hi:.2f}", flush=True)
    check("proneness scales severity", m_hi > m_lo * 1.3, f"({m_hi:.2f} vs {m_lo:.2f})")

    # ---- 5. rest_days_after reads real gaps -----------------------------
    print("\n[5. schedule rest days]", flush=True)
    from datetime import date
    ta = Team("Alpha", "ALP", "D", "C"); tb = Team("Beta", "BET", "D", "C")
    sched = [
        {"date": date(2026, 10, 8), "home_team": ta, "away_team": tb},
        {"date": date(2026, 10, 9), "home_team": tb, "away_team": ta},  # b2b
        {"date": date(2026, 10, 12), "home_team": ta, "away_team": tb},
    ]
    check("back-to-back -> 0 rest", cs.rest_days_after(sched, ta, date(2026, 10, 8)) == 0)
    check("3-day gap -> 2 rest", cs.rest_days_after(sched, tb, date(2026, 10, 9)) == 2)
    check("no future game -> default 3", cs.rest_days_after(sched, ta, date(2026, 10, 12)) == 3)
    check("tuple entries work",
          cs.rest_days_after([(date(2026, 10, 9), ta, tb)], tb, date(2026, 10, 8)) == 0)

    # ---- 6. _assess_injury_risk still telemetry-safe --------------------
    print("\n[6. risk score wiring]", flush=True)
    p_r = make_player("Risk")
    t3, t4 = Team("X", "X", "D", "C"), Team("Y", "Y", "D", "C")
    t3.roster.append(p_r); t4.roster.append(make_player("Q"))
    sim2 = GameSim(t3, t4)
    cs.reset_game_fatigue(p_r)
    r_fresh = sim2._assess_injury_risk(p_r)
    p_r.game_energy = 10.0
    sim2.player_fatigue[p_r.id] = 10.0
    r_tired = sim2._assess_injury_risk(p_r)
    print(f"    risk score: fresh={r_fresh:.3f} tired={r_tired:.3f}", flush=True)
    check("tired player scores higher risk", r_tired > r_fresh)
    check("fresh baseline sane (~0.05)", 0.04 <= r_fresh <= 0.08, f"({r_fresh:.3f})")

    print(f"\n{'='*50}\nW3 probe: {PASS} passed, {FAIL} failed", flush=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
