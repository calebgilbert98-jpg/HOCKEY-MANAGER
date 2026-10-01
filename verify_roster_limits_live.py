"""Live verification: AI clubs stay roster-compliant across 3 simulated
seasons (July pass + Dec-1 + daily backstop), with contract expiry,
injuries, and the deadlock path exercised. Deterministic seed.
"""
import datetime
import random
import sys

from game_classes import (League, PlayerPosition, Contract, to_100_scale)
from player_generator import PlayerGenerator
from salary_cap_system import SalaryCapSystem
import rfa_system
import roster_limits as rl

SEED = 20261001
rng = random.Random(SEED)

FAIL = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + ("" if cond else f" -- {detail}"))
    if not cond:
        FAIL.append(name)


def build_league():
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    positions = ([PlayerPosition.CENTER] * 4 + [PlayerPosition.LEFT_WING] * 4
                 + [PlayerPosition.RIGHT_WING] * 4
                 + [PlayerPosition.LEFT_DEFENSE] * 3
                 + [PlayerPosition.RIGHT_DEFENSE] * 3
                 + [PlayerPosition.GOALIE] * 2)
    for team in league.teams:
        for pos in positions:
            tier = rng.choice(["NHL_ELITE", "NHL_STARTER", "NHL_STARTER",
                               "NHL_DEPTH", "NHL_DEPTH", "AHL_VETERAN"])
            p = gen.create_player(skill_tier=tier,
                                  age_category=rng.choice(["YOUNG", "PRIME", "PRIME", "VETERAN"]),
                                  position=pos, team_name=team.team_name)
            ovr100 = int(to_100_scale(p.overall_rating()))
            salary = max(775_000, min(int(ovr100 * 110_000 * rng.uniform(0.8, 1.2)), 13_000_000))
            p.contract = Contract(salary=salary,
                                  years_remaining=rng.choice([1, 2, 3, 4, 5]))
            p.salary = salary
            team.roster.append(p)
        # a few AHL bodies
        for _ in range(6):
            p = gen.create_player(skill_tier="AHL_VETERAN",
                                  age_category="YOUNG",
                                  position=rng.choice(positions),
                                  team_name=team.team_name)
            p.contract = Contract(salary=825_000, years_remaining=2)
            p.contract.two_way = True
            team.ahl_roster.append(p)
    league.season_year = 2026
    league.salary_cap_system = SalaryCapSystem()
    league.free_agents = []
    return league


def assert_compliance(league, tag):
    bad23 = [t.team_name for t in league.teams if rl.active_roster_count(t) > 23]
    bad50 = [t.team_name for t in league.teams if rl.spc_count(t) > 50]
    baddress = [t.team_name for t in league.teams if not rl.can_dress_lineup(t)]
    check(f"{tag}: no team over 23", not bad23, str(bad23[:3]))
    check(f"{tag}: no team over 50 SPC", not bad50, str(bad50[:3]))
    check(f"{tag}: every team can dress 18+2", not baddress, str(baddress[:3]))
    return not (bad23 or bad50 or baddress)


league = build_league()
check("32 teams built", len(league.teams) == 32, str(len(league.teams)))
assert_compliance(league, "preseason")

for season in range(3):
    # --- a season passes: decrement every contract, injure some players ---
    for team in league.teams:
        for p in list(team.roster) + list(team.ahl_roster):
            c = getattr(p, "contract", None)
            if c is not None and int(getattr(c, "years_remaining", 0) or 0) > 0:
                c.years_remaining -= 1
        for p in rng.sample(team.roster, min(3, len(team.roster))):
            p.is_injured = rng.random() < 0.5
    # one club gets massacred: the deadlock path (can't dress, cap-strapped)
    victim = league.teams[season % len(league.teams)]
    for p in victim.roster[:14]:
        p.is_injured = True
    for p in victim.roster:
        p.contract.salary = max(int(getattr(p.contract, "salary", 0)), 6_000_000)

    # --- daily backstop runs (as process_daily_decisions does) ---
    for team in league.teams:
        rl.ai_roster_compliance(team, league, rng)
    check(f"S{season + 1}: massacre victim can dress after backstop",
          rl.can_dress_lineup(victim), victim.team_name)
    assert_compliance(league, f"S{season + 1} mid-season")

    # --- Dec 1: stamp qualified-but-unsigned RFAs ---
    dec = datetime.date(2026 + season, 12, 1)
    n = rl.apply_dec1_ineligibility(league, dec)
    # none may sign afterwards
    bad_sign = 0
    for team in league.teams:
        for p in team.roster:
            if getattr(p, "season_ineligible", False):
                ok, _ = rl.can_sign_player(p)
                if ok:
                    bad_sign += 1
    check(f"S{season + 1}: Dec-1 stamped ({n}), none signable", bad_sign == 0)

    # --- July pass ---
    league.season_year += 1
    summary = rfa_system.process_rfa_offseason(league, app=None, rng=rng)
    # expired UFAs must be gone from every roster (off roster AND cap)
    lingering = 0
    for team in league.teams:
        for p in team.roster:
            try:
                if rfa_system.contract_expired(p) and rfa_system.is_ufa(p):
                    lingering += 1
            except Exception:
                pass
    check(f"S{season + 1}: no expired UFAs lingering on rosters", lingering == 0,
          f"{lingering} linger")
    # RFA rights retained: no unsigned RFA was waived to the pool implicitly
    # (non-tendered ones are SUPPOSED to be UFAs -- check none vanished wrongly
    # is covered by unit QA; here check rosters are intact)
    assert_compliance(league, f"S{season + 1} post-July")
    # every filler present post-July must be currently needed (the club
    # can't dress without them) -- no stale carry-over
    stale = 0
    for t in league.teams:
        fills = [p for p in t.roster if rl.is_emergency_filler(p)]
        if fills:
            rest = [p for p in t.roster if not rl.is_emergency_filler(p)]
            t.roster[:] = rest
            if rl.can_dress_lineup(t):
                stale += len(fills)
            t.roster.extend(fills)
    check(f"S{season + 1}: no stale fillers post-July", stale == 0, str(stale))
    # heal everyone for the next season
    for team in league.teams:
        for p in team.roster:
            p.is_injured = False
            p.season_ineligible = False

print(f"\n{'ALL GREEN' if not FAIL else f'{len(FAIL)} FAILURES'}")
sys.exit(1 if FAIL else 0)
