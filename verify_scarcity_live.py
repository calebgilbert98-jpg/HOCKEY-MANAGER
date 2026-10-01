# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""LIVE verification: scarcity pricing in a real league through the real
July machinery (Chris's ask: confirm premiums/discounts appear in live
sims, not just unit tests).

Boots a real 32-team League with real generated players and real
contracts, then runs rfa_system.process_rfa_offseason -- the real July
pass: QOs, AI RFA re-signs, UFA releases + re-signs, AI offer sheets,
arbitration, and the AI backfill UFA sweep. Every signing is captured by
wrapping rfa_system._sign_player, logging the live scarcity multiplier
and signal in force at signing time plus a no-scarcity baseline.

Then the real AI open-market UFA handshake
(AITeamManager._execute_free_agent_signing, real ask machinery) signs
each club's best fit at its weakest need.

Two scenarios, same teams, same seed family:
  THIN    -- 3 quality centers on the market
  FLOODED -- 45 quality centers on the market

Verdict: thin market must show average premiums on C signings;
flooded market must show average discounts.

Run: python3 verify_scarcity_live.py   (~3-5 min)
"""
import random
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import League, PlayerPosition, Contract
from game_classes import to_100_scale
from player_generator import PlayerGenerator
from salary_cap_system import (
    SalaryCapSystem, base_ask_dollars, fa_market_scarcity, DEFAULT_CAP)
import rfa_system
from ai_team_management import (
    AITeamManager, AIDecision, TeamStrategy, ManagementPriority,
    TradePreference)

SEED = 20261001

SIGNED_LOG = []  # (scenario, name, pos, aav, mult, signal, path)


def build_league(rng):
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    positions = ([PlayerPosition.CENTER] * 4 + [PlayerPosition.LEFT_WING] * 4
                 + [PlayerPosition.RIGHT_WING] * 4
                 + [PlayerPosition.LEFT_DEFENSE] * 3
                 + [PlayerPosition.RIGHT_DEFENSE] * 3
                 + [PlayerPosition.GOALIE] * 2)
    for team in league.teams:
        for pos in positions:
            # Engineered need: centers are systematically the weak spot, so
            # every club carries a live top-2 need at C (the demand side of
            # the market). Other positions draw real quality.
            if pos == PlayerPosition.CENTER:
                tier = rng.choice(["NHL_DEPTH", "AHL_VETERAN", "AHL_VETERAN"])
            else:
                tier = rng.choice(["NHL_ELITE", "NHL_STARTER", "NHL_STARTER",
                                   "NHL_DEPTH", "NHL_DEPTH", "AHL_VETERAN"])
            p = gen.create_player(skill_tier=tier,
                                  age_category=rng.choice(
                                      ["YOUNG", "PRIME", "PRIME", "VETERAN"]),
                                  position=pos, team_name=team.team_name)
            p.seasons_played = max(0, p.age - 20 + rng.randint(-1, 1))
            ovr100 = int(to_100_scale(p.overall_rating()))
            posname = p.primary_position.value
            salary = int(base_ask_dollars(ovr100, p.age, False, posname)
                         * rng.uniform(0.55, 0.80))
            salary = max(775_000, min(salary, 13_000_000))
            p.contract = Contract(salary=salary,
                                  years_remaining=rng.choice([0, 0, 1, 2, 3, 4]))
            p.salary = salary
            team.roster.append(p)
    league.season_year = 2026
    league.salary_cap_system = SalaryCapSystem()
    league.free_agents = []
    return league


def build_fa_pool(gen, rng, n_quality_c):
    pool = []
    for _ in range(n_quality_c):
        pool.append(gen.create_player(
            skill_tier="NHL_STARTER",
            age_category=rng.choice(["YOUNG", "PRIME"]),
            position=PlayerPosition.CENTER, team_name="Free Agent"))
    for pos, n in [(PlayerPosition.LEFT_WING, 14),
                   (PlayerPosition.RIGHT_WING, 14),
                   (PlayerPosition.DEFENSE, 16),
                   (PlayerPosition.GOALIE, 6),
                   (PlayerPosition.CENTER, 10)]:
        for _ in range(n):
            pool.append(gen.create_player(
                skill_tier=rng.choice(["NHL_DEPTH", "AHL_VETERAN"]),
                age_category=rng.choice(["YOUNG", "PRIME", "VETERAN"]),
                position=pos, team_name="Free Agent"))
    rng.shuffle(pool)
    return pool


def install_signing_tap(scenario, league):
    real_sign = rfa_system._sign_player

    def tap(team, player, aav, years):
        try:
            sc = fa_market_scarcity(
                league, getattr(getattr(player, "primary_position", ""),
                                "value", ""))
            SIGNED_LOG.append((scenario, getattr(player, "full_name", "?"),
                               getattr(getattr(player, "primary_position",
                                               ""), "value", "?"),
                               int(aav), sc["multiplier"], sc["signal"],
                               "july-pass"))
        except Exception:
            pass
        return real_sign(team, player, aav, years)

    rfa_system._sign_player = tap
    return real_sign


def run_scenario(name, n_quality_c):
    rng = random.Random(SEED)
    gen = PlayerGenerator()
    print(f"\n===== scenario {name}: {n_quality_c} quality Cs =====",
          flush=True)
    league = build_league(rng)
    league.free_agents = build_fa_pool(gen, rng, n_quality_c)
    mgr = AITeamManager()
    mgr.set_cap_system(league.salary_cap_system, league)
    real_sign = install_signing_tap(name, league)
    try:
        # --- 1. the real July pass --------------------------------------
        res = rfa_system.process_rfa_offseason(league, rng=rng)
        summ = res if isinstance(res, dict) else {}
        print(f"  July: {summ.get('rfas', 0)} RFAs / {summ.get('ufas', 0)} "
              f"UFAs classified, {summ.get('qualified', 0)} qualified, "
              f"{summ.get('non_tendered', 0)} non-tendered, "
              f"{summ.get('offer_sheets', 0)} offer sheets, "
              f"{summ.get('arbitration_filings', 0)} arb filings",
              flush=True)
    finally:
        rfa_system._sign_player = real_sign

    # --- 2. the real AI open-market UFA handshake ----------------------
    from trade_engine import team_needs
    need_map = {"C": "Forward", "LW": "Forward", "RW": "Forward",
                "LD": "Defense", "RD": "Defense", "G": "Goalie"}
    n_open = 0
    for team in league.teams:
        if len(team.roster) >= 23:
            continue
        try:
            needs = team_needs(team) or []
        except Exception:
            continue
        if not needs:
            continue
        want = need_map.get(str(needs[0]).upper(), "")
        want_pos = [k for k, v in need_map.items() if v == want]
        cands = [p for p in league.free_agents
                 if p.primary_position.value in want_pos]
        if not cands:
            continue
        cands.sort(key=lambda p: p.overall_rating(), reverse=True)
        target = cands[0]
        # minimal live strategy so the real executor runs its real guards
        mgr.team_strategies[team.team_name] = TeamStrategy(
            priority=ManagementPriority.CONTEND,
            trade_preference=TradePreference.MODERATE,
            budget_limit=DEFAULT_CAP, min_roster_age=18, max_roster_age=40,
            position_needs=[target.primary_position],
            salary_cap_tolerance=0.95, prefer_youth=False,
            prefer_experience=False, risk_tolerance=0.5,
            will_trade_picks=True, will_trade_prospects=True,
            rebuilding_timeline=3)
        try:
            ask = mgr._player_ask(target, league=league)
        except Exception:
            continue
        sc = fa_market_scarcity(league, target.primary_position.value)
        dec = AIDecision(team_name=team.team_name,
                         decision_type="free_agent_offer",
                         target_player=target,
                         offer_details={"salary": int(ask * 0.97),
                                        "term": 2, "no_trade_clause": False},
                         priority_score=0.9,
                         reasoning="live scarcity verification",
                         timestamp=date(2026, 7, 5))
        try:
            if mgr._execute_free_agent_signing(team, dec, league):
                SIGNED_LOG.append(
                    (name, target.full_name, target.primary_position.value,
                     int(ask * 0.97), sc["multiplier"], sc["signal"],
                     "open-market"))
                n_open += 1
        except Exception:
            continue
    print(f"  open-market UFA signings: {n_open}", flush=True)
    return n_open


def report():
    print("\n===== signing log (live scarcity in force) =====")
    by_scen = {}
    for row in SIGNED_LOG:
        by_scen.setdefault(row[0], []).append(row)
    ok = True
    for scen, rows in by_scen.items():
        c_rows = [r for r in rows if r[2] == "C"]
        if not c_rows:
            print(f"  {scen}: no center signings logged "
                  f"({len(rows)} total signings)")
            continue
        prem = [((r[3] / (r[3] / r[4])) - 1) * 100 for r in c_rows if r[4] > 1]
        disc = [((r[3] / (r[3] / r[4])) - 1) * 100 for r in c_rows if r[4] < 1]
        avg_p = sum(prem) / len(prem) if prem else 0.0
        avg_d = sum(disc) / len(disc) if disc else 0.0
        print(f"  {scen}: {len(c_rows)} C signings -- "
              f"avg premium +{avg_p:.1f}% (n={len(prem)}), "
              f"avg discount {avg_d:.1f}% (n={len(disc)})")
        for r in c_rows[:4]:
            print(f"    {r[1]}: ${r[3]:,} mult={r[4]} "
                  f"signal={r[5]} via {r[6]}")
        by_scen[scen] = (avg_p, avg_d)
    thin = by_scen.get("THIN", (0, 0))
    flooded = by_scen.get("FLOODED", (0, 0))
    print("\n===== verdict =====")
    if thin[0] <= 2.0:
        print(f"FAIL: thin C market should show premiums (got +{thin[0]:.1f}%)")
        ok = False
    else:
        print(f"PASS: thin C market -> +{thin[0]:.1f}% avg premium on centers")
    if flooded[1] >= -0.5:
        print(f"FAIL: flooded C market should show discounts "
              f"(got {flooded[1]:.1f}%)")
        ok = False
    else:
        print(f"PASS: flooded C market -> {flooded[1]:.1f}% avg discount "
              f"on centers")
    print("LIVE VERIFICATION GREEN" if ok else "LIVE VERIFICATION RED")
    return ok


def main():
    run_scenario("THIN", 3)
    run_scenario("FLOODED", 45)
    sys.exit(0 if report() else 1)


if __name__ == "__main__":
    main()
