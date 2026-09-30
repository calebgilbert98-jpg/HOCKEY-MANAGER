# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: day-one cap situations on the primary new-game path (seed 20260928).

Asserts every club starts compliant with a payroll posture near its real
2026-27 situation, contracts stay inside the 2026 market, and no team
starts in violation (the hard-compliance backstop).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random, statistics
random.seed(20260928)

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

from database_generator import DatabaseGenerator, DATABASE_CONFIGURATIONS
import real_cap_data as rcd
from salary_cap_system import cap_breakdown, DEFAULT_CAP

gen = DatabaseGenerator(DATABASE_CONFIGURATIONS['Small'])
league = gen.generate_comprehensive_database()
rcd.seed_real_dead_cap(league)
nhl = [t for t in league.teams
       if getattr(t, 'league_name', '') == 'National Hockey League']
check("32 NHL teams generated", len(nhl) == 32)

rooms, errs = [], []
for t in nhl:
    bd = cap_breakdown(t)
    room = bd["space"] / 1e6
    tgt = rcd.target_cap_room(rcd._team_key(t)) / 1e6
    rooms.append((t.team_name, room))
    errs.append(abs(room - tgt))
    if bd["over_cap"]:
        print(f"    OVER: {t.team_name} space ${room:.2f}M")

check("all 32 clubs cap-compliant on day one",
      all(r[1] >= 0 for r in rooms))
check("mean abs error vs real targets < $2.0M",
      statistics.mean(errs) < 2.0)
check("max abs error vs real targets < $5.0M", max(errs) < 5.0)

# Rank correlation: tight real clubs should be tight in-game.
order_real = sorted(nhl, key=lambda t: rcd.target_cap_room(rcd._team_key(t)))
order_game = sorted(nhl, key=lambda t: cap_breakdown(t)["space"])
rank_real = {t.team_name: i for i, t in enumerate(order_real)}
n = len(nhl)
d2 = sum((rank_real[t.team_name] - i) ** 2 for i, t in enumerate(order_game))
spearman = 1 - 6 * d2 / (n * (n * n - 1))
print(f"    spearman room-rank correlation: {spearman:.3f}")
# Rank correlation: tight real clubs should be tight in-game. The middle
# cluster has a dozen clubs within ~$2M of target, so near-tie rank
# shuffling there is noise; the identity checks above pin the extremes.
check("spearman rank correlation > 0.75", spearman > 0.75)

# Cap-crisis identity: the four real over-cap clubs start at <= $1M room.
tight = {"Toronto Maple Leafs", "Florida Panthers",
         "Columbus Blue Jackets", "Vegas Golden Knights"}
room_of = dict(rooms)
check("real over-cap clubs start tight (<= $1M room)",
      all(room_of[name] <= 1.0 for name in tight))
# Cap-flush identity: Detroit/Seattle/Vancouver start with $10M+ room.
flush = {"Detroit Red Wings", "Seattle Kraken", "Vancouver Canucks"}
check("real cap-flush clubs start loose (>= $10M room)",
      all(room_of[name] >= 10.0 for name in flush))

sals = [int(p.contract.salary)
        for t in nhl for p in t.roster if getattr(p, "contract", None)]
check("no contract above 20% of cap ($20.8M)", max(sals) <= 20_800_000)
med = statistics.median(sals)
print(f"    median salary ${med/1e6:.2f}M, max ${max(sals)/1e6:.1f}M")
check("median salary in [$1.5M, $4.0M]", 1_500_000 <= med <= 4_000_000)
check("record-type deals exist (>= $15M)", any(s >= 15_000_000 for s in sals))

two_way = sum(1 for t in nhl for p in t.roster
              if getattr(getattr(p, "contract", None), "two_way", False))
print(f"    two-way NHL deals: {two_way}")
check("two-way deals present on NHL rosters", two_way > 50)

check("all rosters 21-23 players",
      all(21 <= len(t.roster) <= 23 for t in nhl))

# Star-concentration disparity: cap-flush clubs must not carry a
# McDavid-level contract while capped-out contenders do. Blend factor
# t runs 0 (flat payroll) -> 1 (star-heavy payroll) by day-one target.
def _blend_t(team):
    key = rcd._team_key(team)
    tgt = (DEFAULT_CAP
           - rcd.total_dead_cap(key)
           - rcd.target_cap_room(key))
    return max(0.0, min(1.0, (tgt - 82_000_000) / 21_500_000))

top_sal = {}
for t in nhl:
    ss = sorted((int(getattr(getattr(p, "contract", None), "salary", 0) or 0)
                 for p in (t.roster or [])), reverse=True)
    top_sal[t.team_name] = ss[0] / 1e6 if ss else 0.0
flat = [t for t in nhl if _blend_t(t) <= 0.25]
heavy = [t for t in nhl if _blend_t(t) >= 0.85]
flat_max = max(top_sal[t.team_name] for t in flat)
heavy_min = min(top_sal[t.team_name] for t in heavy)
print(f"    flat clubs (t<=0.25) top salary: ${flat_max:.2f}M; "
      f"heavy clubs (t>=0.85) lowest top salary: ${heavy_min:.2f}M")
check("cap-flush clubs top out at role-player money (<= $8M)",
      flat_max <= 8.0)
check("capped-out clubs carry a star (>= $9.5M top deal)",
      heavy_min >= 9.5)
check("disparity ordering: every flat club's best-paid player earns "
      "less than every heavy club's", flat_max < heavy_min)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
