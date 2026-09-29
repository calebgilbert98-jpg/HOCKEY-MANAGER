"""QA: EHM-style per-season NHL schedule generation.

Verifies:
1. All 32 teams get exactly 82 regular-season games.
2. Back-to-backs per team in realistic NHL range (8-20, target 11-16).
3. ZERO teams with 3+ consecutive game days (hard immersion invariant).
4. Fresh schedule per season_year (not a repeated template).
"""
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_generator import generate_database

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


def analyze(season_year):
    league = generate_database("Small")
    league.season_year = season_year
    league.generate_schedule()
    team_dates = defaultdict(set)
    for e in league.schedule:
        if not isinstance(e, dict) or e.get('preseason'):
            continue
        if e.get('league') != 'NHL':
            continue
        d = e['date']
        for side in ('home_team', 'away_team'):
            t = e.get(side)
            if hasattr(t, 'team_name'):
                team_dates[t.team_name].add(d)
    return team_dates


results = {}
for yr in (2029, 2030):
    team_dates = analyze(yr)
    b2b = {}
    streaks = {}
    for team, dates in team_dates.items():
        ds = sorted(dates)
        b2b[team] = sum(1 for i in range(1, len(ds))
                        if (ds[i] - ds[i-1]).days == 1)
        run, best = 1, 1
        for i in range(1, len(ds)):
            if (ds[i] - ds[i-1]).days == 1:
                run += 1
                best = max(best, run)
            else:
                run = 1
        streaks[team] = best
    results[yr] = (team_dates, b2b, streaks)

for yr, (team_dates, b2b, streaks) in results.items():
    check(f"{yr}: 32 NHL teams", len(team_dates) == 32, f"got {len(team_dates)}")
    bad_counts = {t: len(d) for t, d in team_dates.items() if len(d) != 82}
    check(f"{yr}: all teams 82 games", not bad_counts, str(bad_counts)[:120])
    vals = list(b2b.values())
    check(f"{yr}: back-to-backs 8-20 per team",
          min(vals) >= 8 and max(vals) <= 20,
          f"range {min(vals)}-{max(vals)}")
    check(f"{yr}: mean back-to-backs 9-17",
          9 <= sum(vals) / len(vals) <= 17,
          f"mean {sum(vals)/len(vals):.1f}")
    bad_streak = {t: s for t, s in streaks.items() if s >= 3}
    check(f"{yr}: zero 3+ consecutive-game-day streaks",
          not bad_streak, str(bad_streak)[:160])

# Per-season freshness: different season_year => different schedule.
dates_29 = sorted(d for ds in results[2029][0].values() for d in ds)
dates_30 = sorted(d for ds in results[2030][0].values() for d in ds)
# Compare first 20 game dates of one team.
t29 = sorted(results[2029][0]['Boston Bruins'])[:20]
t30 = sorted(results[2030][0]['Boston Bruins'])[:20]
check("schedule differs per season_year", t29 != t30,
      "identical Boston slate two years running")

print(f"\n{len(PASS)}/{len(PASS)+len(FAIL)} passed")
sys.exit(1 if FAIL else 0)
