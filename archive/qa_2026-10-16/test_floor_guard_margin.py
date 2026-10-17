#!/usr/bin/env python3
"""Margin proof for the headless fantasy-draft salary-floor guard.

Incident: 2026-10-12 fresh sim run perma-froze on day 1 -- a value-drafted
club came out of the fantasy draft at $57.33M against a $78M floor, and the
headless floor auto-action plateaued at $67.13M (bounded upgrade loop +
50-contract gate + thin post-draft FA pool), so the day could never advance.

The guard in GameManager.conduct_fantasy_draft steers late-round picks so
every club's projected post-normalization NHL payroll clears floor + $1M
margin. This test proves the margin empirically instead of asserting it in
a comment: full headless setup + fantasy draft (the same path the sim
runner uses), then the post-draft normalizer runs inside
conduct_fantasy_draft exactly as in production -- and afterwards every NHL
club must satisfy cap_breakdown(team)["under_floor"] is False.

If this fails, the guard (or its projection basis) is wrong -- fix the
guard until it passes. Never weaken the assertion.
"""
import os, sys, time
sys.path.insert(0, os.path.expanduser("~/workspace/hockey-manager"))
os.chdir(os.path.expanduser("~/workspace/hockey-manager"))

from game_manager import GameManager
from salary_cap_system import SALARY_CAP_FLOOR, cap_breakdown

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"[{PASS if cond else FAIL}] {name}"
          + (f" -- {detail}" if detail and not cond else ""), flush=True)


gm = GameManager()
gm._headless_sim = True
gm.apply_startup_settings({
    'database_size': 'Small', 'fantasy_draft': True, 'fog_of_war': True,
    'user_league': 'NHL', 'gm_name': 'GM Bot', 'playoff_format': 'divisional',
})
gm.set_user_team("Carolina Hurricanes")
gm.setup_new_game()
print("SETUP DONE", flush=True)

t0 = time.time()
gm.conduct_fantasy_draft()
print(f"DRAFT DONE in {time.time() - t0:.1f}s", flush=True)

FLOOR = int(SALARY_CAP_FLOOR)
check("floor constant is $78M", FLOOR == 78_000_000, f"got ${FLOOR}")

# All NHL clubs: league_name is the predicate the draft itself uses
# (conduct_fantasy_draft collects teams by league_name == "National
# Hockey League"; the AHL is "American Hockey League").
nhl_teams = [t for t in (getattr(gm.league, 'teams', None) or [])
             if getattr(t, 'league_name', None) == 'National Hockey League']
# De-dupe by team_name.
seen = set()
clubs = []
for t in nhl_teams:
    nm = getattr(t, 'team_name', None)
    if nm and nm not in seen:
        seen.add(nm)
        clubs.append(t)
print(f"NHL clubs found: {len(clubs)}", flush=True)

payrolls = []
bad = []
for t in clubs:
    try:
        bd = cap_breakdown(t)
        total = int(bd.get('total') or 0)
        under = bool(bd.get('under_floor'))
    except Exception as e:
        bad.append((getattr(t, 'team_name', '?'), f"cap_breakdown raised: {e}"))
        continue
    payrolls.append((getattr(t, 'team_name', '?'), total, under))
    if under:
        bad.append((getattr(t, 'team_name', '?'),
                    f"${total / 1e6:.2f}M < ${FLOOR / 1e6:.2f}M floor"))

check(f"all {len(clubs)} NHL clubs above the salary floor",
      not bad, "; ".join(f"{n}: {d}" for n, d in bad[:8]))

# Sanity: the normalizer must have run (23-man NHL rosters, not the raw
# 40-man draft squads). If normalization silently failed, payrolls would
# measure the 40-man squads (~$120M) and the test would pass trivially.
oversized = [(getattr(t, 'team_name', '?'), len(t.roster or []))
             for t in clubs if len(getattr(t, 'roster', None) or []) > 23]
check("all NHL rosters are post-normalization shape (<=23 skaters)",
      not oversized, "; ".join(f"{n}: {c}" for n, c in oversized[:8]))

# Report shape: how close did anyone get? If the minimum payroll sits well
# above floor+margin, the guard steered; if nobody got near $79M, the test
# may have passed trivially and should be re-examined.
payrolls.sort(key=lambda r: r[1])
if payrolls:
    lo_name, lo_pay, _ = payrolls[0]
    hi_name, hi_pay, _ = payrolls[-1]
    near = [(n, p) for n, p, u in payrolls if p < FLOOR + 1_000_000]
    print(f"min payroll: {lo_name} ${lo_pay / 1e6:.2f}M | "
          f"max: {hi_name} ${hi_pay / 1e6:.2f}M | "
          f"clubs under floor+$1M margin: {len(near)}", flush=True)
    for n, p in near[:10]:
        print(f"  near-margin: {n} ${p / 1e6:.2f}M", flush=True)

fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed", flush=True)
sys.exit(1 if fails else 0)
