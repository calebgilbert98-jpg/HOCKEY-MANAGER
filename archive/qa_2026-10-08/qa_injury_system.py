#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: W4 injury system (icetime-ecosystem) -- real-data grounded + medical staff.

Covers injury_data.py (the shared decision) and the engine call sites:
  A. Grounded calibration: severity mean ~8.04-9.3 games, concussion share
     ~5.5%, body-region mix, concussion absence ~13.8 games (capped 82).
  B. General-roll rates: per-engine rates defined; goalie victims rare;
     proneness/age/re-aggravation weights move the needle the right way.
  C. apply_injury: sets fields, medical-staff scaling, long-term flags +
     AI call-up bookkeeping, concussion protocol flag.
  D. Hit path: HIT_INJURY_PROB_SCALE=0.15; dirty hits bump severity;
     enforcer-vs-small-star mismatch raises concussion odds (nonzero but
     not cartoonish); open-ice collisions bump.
  E. Medical staff: recovery_time_mult bounds 0.80-1.20; setback odds fall
     with better staff; repeat concussion 2.25x.
  F. Call-site wiring: quick_sim delegates (signature unchanged),
     simulation scales INJURY_CAUSED weight, GameSim has the general roll.

Usage: python3 qa_injury_system.py   (exit 0 = all pass)
"""
import sys, os, random
sys.path.insert(0, '/home/hatch/workspace/wt-icetime')
os.environ.setdefault("DISPLAY", ":99")

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS: {name}", flush=True)
    else:
        FAIL += 1; print(f"  FAIL: {name} {detail}", flush=True)

class FakePos:
    def __init__(self, name): self.name = name

class FakePlayer:
    _i = 0
    def __init__(self, pos="CENTER", age=25, ovr=80, proneness=10,
                 weight=190, archetype="TWO_WAY"):
        FakePlayer._i += 1
        self.id = FakePlayer._i
        self.first_name, self.last_name = "Test", f"Player{FakePlayer._i}"
        self.full_name = f"Test Player{FakePlayer._i}"
        self.primary_position = FakePos(pos)
        self.age = age
        self.overall_rating = ovr
        self.injury_proneness = proneness
        self.weight = weight
        self.archetype = archetype  # what player_archetypes.get_archetype reads
        self.player_archetype = archetype
        self.is_injured = False
        self.injury_type = "None"
        self.games_remaining_injured = 0
        self.last_injury = None
        self.days_missed = 0
        self.career_games_missed = 0
        self.career_concussions = 0
        self.games_since_return = None
        self.in_concussion_protocol = False
        self.injured_today = False

class FakeStaff:
    def __init__(self, role, overall):
        self.role = role; self.overall_rating = overall

class FakeTeam:
    def __init__(self, roster, staff=()):
        self.roster = roster
        self.staff_members = list(staff)
        self.injury_callup_queue = []
        self.team_name = "Fake"
        self._inj_flags = {}
    def get_staff_by_role(self, role):
        # mirrors game_classes.Team.get_staff_by_role (role: StaffRole enum)
        want = str(getattr(role, "name", role or "")).upper()
        return [s for s in self.staff_members
                if str(getattr(s, "role", "")).upper() == want]
    def __repr__(self): return "FakeTeam"

def main():
    random.seed(20260929)
    print("=== QA: W4 injury system ===", flush=True)
    import injury_data as inj

    # ---- A: grounded calibration --------------------------------------
    print("\n[A] calibration", flush=True)
    n = 20000
    tot, conc, regions = 0, 0, {}
    for _ in range(n):
        s = inj.roll_severity()
        tot += s["games"]; conc += s["concussion"]
        regions[s["region"]] = regions.get(s["region"], 0) + 1
    mean_sev = tot / n
    check("severity mean in grounded band (8.04-9.3)", 8.0 <= mean_sev <= 9.4,
          f"mean={mean_sev:.2f}")
    conc_share = conc / n
    check("concussion share ~5.5% (R3)", 0.04 <= conc_share <= 0.07,
          f"share={conc_share:.3f}")
    check("head region ~21% (R2)", 0.17 <= regions.get("HEAD", 0) / n <= 0.26,
          f"head={regions.get('HEAD',0)/n:.3f}")
    check("knee region ~8.7% (R2)", 0.06 <= regions.get("KNEE", 0) / n <= 0.12,
          f"knee={regions.get('KNEE',0)/n:.3f}")
    cg = [inj.concussion_games() for _ in range(5000)]
    check("concussion absence mean ~13.8 (R3)", 12.0 <= sum(cg)/len(cg) <= 16.0,
          f"mean={sum(cg)/len(cg):.2f}")
    check("concussion absence capped at 82", max(cg) <= 82)

    # ---- B: general roll rates ----------------------------------------
    print("\n[B] general roll rates", flush=True)
    check("quick-engine rate 0.31 (R1)", inj.QUICK_ENGINE_GENERAL_RATE == 0.31)
    check("gamesim rate 0.22 (non-hit share)", inj.GENERAL_INJURY_BASE_RATE == 0.22)
    mk = lambda **kw: FakePlayer(**kw)
    team = FakeTeam([mk() for _ in range(18)] + [mk(pos="GOALIE"), mk(pos="GOALIE")])
    hits = 0; trials = 4000; goalie_hits = 0
    for _ in range(trials):
        for p in team.roster: p.is_injured = False
        v, _spec = inj.roll_general_injury(team, base_prob=inj.QUICK_ENGINE_GENERAL_RATE)
        if v is not None:
            hits += 1
            if v.primary_position.name == "GOALIE": goalie_hits += 1
    rate = hits / trials
    check("measured rate in band (~0.31)", 0.24 <= rate <= 0.38, f"rate={rate:.3f}")
    check("goalies rarely hurt", hits == 0 or goalie_hits / hits < 0.25,
          f"goalie share={goalie_hits/max(hits,1):.3f}")
    # proneness weight direction
    fragile = FakeTeam([mk(proneness=20) for _ in range(10)] +
                       [mk(proneness=5) for _ in range(10)])
    fh = 0; ft = 3000
    for _ in range(ft):
        for p in fragile.roster: p.is_injured = False
        v, _s = inj.roll_general_injury(fragile, base_prob=1.0)
        if v is not None and v.injury_proneness == 20: fh += 1
    check("fragile players picked more often", fh / ft > 0.55, f"share={fh/ft:.3f}")
    # re-aggravation window
    rusher = FakeTeam([mk() for _ in range(20)])
    rusher.roster[0].games_since_return = 3
    rh = 0; rt = 3000
    for _ in range(rt):
        for p in rusher.roster: p.is_injured = False
        v, _s = inj.roll_general_injury(rusher, base_prob=1.0)
        if v is rusher.roster[0]: rh += 1
    check("recent returnee hit harder (1.6x)", rh / rt > 0.06, f"share={rh/rt:.3f}")

    # ---- C: apply_injury ----------------------------------------------
    print("\n[C] apply_injury", flush=True)
    p = mk(); t = FakeTeam([p])
    games = inj.apply_injury(p, {"games": 6, "type": "Sprained knee",
                                 "concussion": False, "region": "KNEE"}, t)
    check("sets injury fields", p.is_injured and p.injury_type == "Sprained knee"
          and p.games_remaining_injured == games and p.injured_today)
    check("seeds career ledger", p.career_games_missed >= 6)
    check("no flag for short injury", not t._inj_flags)
    p2 = mk(); t2 = FakeTeam([p2])
    inj.apply_injury(p2, {"games": 12, "type": "Torn ACL",
                          "concussion": False, "region": "KNEE"}, t2)
    check("AI call-up queued at 10+ games", len(t2.injury_callup_queue) == 1)
    check("needs_injury_replacement set", getattr(t2, "needs_injury_replacement", False))
    p3 = mk(); t3 = FakeTeam([p3])
    inj.apply_injury(p3, {"games": 8, "type": "Concussion",
                          "concussion": True, "region": "HEAD"}, t3)
    check("concussion protocol flag set", p3.in_concussion_protocol)
    check("career concussion counted", p3.career_concussions == 1)
    # medical staff scaling on recovery time
    elite = FakeTeam([mk()], [FakeStaff("TEAM_DOCTOR", 90),
                              FakeStaff("PHYSIOTHERAPIST", 88)])
    poor = FakeTeam([mk()], [FakeStaff("TEAM_DOCTOR", 30),
                             FakeStaff("PHYSIOTHERAPIST", 32)])
    check("elite staff speeds recovery", inj.recovery_time_mult(elite) < 1.0)
    check("poor staff slows recovery", inj.recovery_time_mult(poor) > 1.0)
    check("recovery mult bounded 0.80-1.20",
          0.80 <= inj.recovery_time_mult(elite) <= 1.20
          and 0.80 <= inj.recovery_time_mult(poor) <= 1.20)
    check("no staff -> neutral", inj.recovery_time_mult(FakeTeam([mk()])) == 1.0)

    # ---- D: hit path ---------------------------------------------------
    print("\n[D] hit path", flush=True)
    check("hit scale 0.15 (measured calibration)", inj.HIT_INJURY_PROB_SCALE == 0.15)
    hitter = mk(archetype="Enforcer", ovr=78, weight=230)
    star = mk(ovr=92, weight=185, archetype="Sniper")
    ctx = inj.hit_circumstance(hitter, star, "BODY_CHECK", 2)
    check("mismatch flagged", ctx["mismatch"], str(ctx))
    # concussion odds: mismatch + big impact should be meaningfully > base
    c_n, c_m = 0, 0; trials = 4000
    for _ in range(trials):
        g, _t, c = inj.hit_injury_spec(4, inj.hit_circumstance(
            mk(archetype="Enforcer", ovr=78, weight=235),
            mk(ovr=93, weight=180, archetype="Sniper"), "BODY_CHECK", 2))
        c_m += c
        g2, _t2, c2 = inj.hit_injury_spec(4, inj.hit_circumstance(
            mk(ovr=80, weight=200), mk(ovr=80, weight=200), "BODY_CHECK", 0))
        c_n += c2
    check("mismatch concussion rate elevated", c_m / trials > 3 * (c_n / trials + 1e-9),
          f"mismatch={c_m/trials:.3f} normal={c_n/trials:.3f}")
    check("mismatch concussion not cartoonish", c_m / trials < 0.35,
          f"{c_m/trials:.3f}")
    # dirty hit severity bump
    d_tot, c_tot, n2 = 0, 0, 3000
    for _ in range(n2):
        g, _t, _c = inj.hit_injury_spec(4, {"dirty": True, "mismatch": False,
                                            "open_ice": False, "concussion_odds": 0.0})
        d_tot += g
        g2, _t2, _c2 = inj.hit_injury_spec(4, {"dirty": False, "mismatch": False,
                                               "open_ice": False, "concussion_odds": 0.0})
        c_tot += g2
    check("dirty hits miss more games", d_tot > c_tot * 1.3,
          f"dirty={d_tot/n2:.2f} clean={c_tot/n2:.2f}")

    # ---- E: medical staff / setbacks -----------------------------------
    print("\n[E] setbacks + staff", flush=True)
    sp, se = 0, 0; trials = 6000
    for _ in range(trials):
        hurt_poor = mk(); hurt_poor.games_remaining_injured = 8
        hurt_elite = mk(); hurt_elite.games_remaining_injured = 8
        sp += 1 if inj.roll_setback(hurt_poor, poor) else 0
        se += 1 if inj.roll_setback(hurt_elite, elite) else 0
    check("setbacks happen (~5% base)", 0.03 <= sp / trials <= 0.08,
          f"poor={sp/trials:.3f}")
    check("elite staff cuts setbacks", se < sp * 0.75,
          f"elite={se/trials:.3f} poor={sp/trials:.3f}")
    # repeat concussion 2.25x
    p4 = mk(); p4.career_concussions = 1
    r1 = [inj.concussion_games() for _ in range(2000)]
    r2 = [inj.concussion_games(player=p4) for _ in range(2000)]
    check("repeat concussion 2.25x time loss", sum(r2)/len(r2) > sum(r1)/len(r1) * 1.8,
          f"first={sum(r1)/len(r1):.1f} repeat={sum(r2)/len(r2):.1f}")

    # ---- F: call-site wiring -------------------------------------------
    print("\n[F] call-site wiring", flush=True)
    import inspect
    import quick_sim
    sig = inspect.signature(quick_sim.roll_game_injury)
    check("roll_game_injury signature unchanged", list(sig.parameters) == ["team"])
    src = inspect.getsource(quick_sim.AdvancedGameSim._process_gameplay_injuries)
    check("quick sim uses grounded rate", "QUICK_ENGINE_GENERAL_RATE" in src)
    import simulation
    src2 = inspect.getsource(simulation.GameSim._resolve_hit_result)
    check("hit path scaled by HIT_INJURY_PROB_SCALE", "HIT_INJURY_PROB_SCALE" in src2)
    check("GameSim has general injury roll",
          hasattr(simulation.GameSim, "_process_general_injuries"))
    import main as appmod
    src3 = inspect.getsource(appmod.HockeyManagerGUI._simulate_game_lightweight)
    check("batch sim uses grounded rate", "QUICK_ENGINE_GENERAL_RATE" in src3)
    src4 = inspect.getsource(appmod.GameManager._process_injury_recovery)
    check("recovery rework: setbacks", "roll_setback" in src4)
    check("recovery rework: days_missed ticks", "days_missed" in src4)
    check("recovery rework: re-aggravation clock", "games_since_return" in src4)

    # ---- G: W3 -> W4 fatigue contract ----------------------------------
    print("\n[G] W3 fatigue contract", flush=True)
    import condition_system as cs
    gf = mk(); gf.game_energy = 5.0; gf.condition = 50.0
    fr = mk()
    check("wrapper consumes real W3 fn (gassed > 1.0)",
          inj.fatigue_injury_risk_mult(gf) == cs.fatigue_injury_risk_mult(gf) > 1.0)
    check("fresh players neutral (1.0)", inj.fatigue_injury_risk_mult(fr) == 1.0)
    mixed = FakeTeam([mk() for _ in range(10)])
    for p in mixed.roster[:5]:
        p.game_energy = 5.0; p.condition = 50.0; p._gassed = True
    for p in mixed.roster[5:]:
        p._gassed = False
    gh = 0; gt = 0
    for _ in range(3000):
        for p in mixed.roster: p.is_injured = False
        v, _s = inj.roll_general_injury(mixed, base_prob=1.0)
        if v is not None:
            gt += 1; gh += getattr(v, "_gassed", False)
    check("gassed players absorb disproportionate injuries",
          gt > 0 and gh / gt > 0.65, f"gassed share={gh/max(gt,1):.3f}")

    print(f"\n=== {PASS} passed, {FAIL} failed ===", flush=True)
    return 1 if FAIL else 0

if __name__ == "__main__":
    sys.exit(main())
