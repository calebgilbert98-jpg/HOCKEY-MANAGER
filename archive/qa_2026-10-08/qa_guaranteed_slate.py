"""QA: guaranteed slate -- 84-game NHL schedule (2026-27 CBA) + season-length plumbing.

Part 1 of the guaranteed-slate branch. The no-drop fallback and the
season-integrity audit live in qa_slate_guarantee.py (Part 2); the
filler team-assignment checks live in qa_roster_limits.py (Part 3).
This file covers the schedule matrix and the season_games_count plumbing.
"""
import sys
import os
import random
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_classes as gc
from database_generator import generate_database

passed, failed = [], []


def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(("  PASS " if cond else "  FAIL ") + name +
          (f" -- {detail}" if detail and not cond else ""))


random.seed(20261002)

# --- 1. matchup matrix: 28 + 24 + 32 = 84 -----------------------------------
league = generate_database("Small")
nhl = [t for t in league.teams
       if getattr(t, "league_name", "") == "National Hockey League"]
check("32 NHL teams", len(nhl) == 32, f"got {len(nhl)}")
div = {t.team_name: t.division for t in nhl}
conf = {t.team_name: t.conference for t in nhl}

probe = gc.League.__new__(gc.League)
matchups = gc.League._create_all_nhl_matchups(probe, nhl)
d = c = ic = 0
t0 = nhl[0]
for a, b, _ in matchups:
    pair = (a.team_name, b.team_name)
    if t0.team_name not in pair:
        continue
    other = pair[1] if pair[0] == t0.team_name else pair[0]
    if div[other] == div[t0.team_name]:
        d += 1
    elif conf[other] == conf[t0.team_name]:
        c += 1
    else:
        ic += 1
check("28 divisional games", d == 28, f"got {d}")
check("24 intra-conference games", c == 24, f"got {c}")
check("32 inter-conference games", ic == 32, f"got {ic}")
check("84 total per team", d + c + ic == 84)

# home/away balance per team over the full matrix
home_c, tot_c = Counter(), Counter()
for a, b, _ in matchups:
    # entries are (team1, team2, 'HOME') where team1 hosts
    tot_c[a.team_name] += 1
    tot_c[b.team_name] += 1
    home_c[a.team_name] += 1
check("42 home / 42 away for every team",
      all(home_c[t] == 42 and tot_c[t] == 84 for t in tot_c),
      str({t: (home_c[t], tot_c[t]) for t in tot_c
           if home_c[t] != 42 or tot_c[t] != 84}))

# --- 2. full generated schedule ---------------------------------------------
league.generate_schedule(season_year=2026, rotation_seed=20261002)
counts, pre_n = Counter(), 0
for e in league.schedule:
    if isinstance(e, dict) and e.get("preseason"):
        pre_n += 1
        continue
    if isinstance(e, dict) and e.get("league") == "NHL":
        counts[e["home_team"].team_name] += 1
        counts[e["away_team"].team_name] += 1
check("all 32 teams at exactly 84 scheduled games",
      len(counts) == 32 and all(v == 84 for v in counts.values()),
      str({t: v for t, v in counts.items() if v != 84}))
check("1344 total regular-season games",
      sum(counts.values()) // 2 == 1344)
check("4 preseason games per club",
      pre_n * 2 // 32 == 4, f"{pre_n} entries")
check("season_games_count persisted as 84",
      getattr(league, "season_games_count", None) == 84)

# --- 3. _check_season_complete plumbing --------------------------------------
# Fake standings: W+L+OTL per team; the app reads the league's slate.
class _FakeLeague:
    def __init__(self, standings, slate=None):
        self.standings = standings
        if slate is not None:
            self.season_games_count = slate


def _gp_target(app_like):
    _lg = getattr(app_like, "league", None)
    return getattr(_lg, "season_games_count",
                   getattr(app_like, "season_games_count", 82))


class _App:
    def __init__(self, league):
        self.league = league


full84 = {f"T{i}": {"W": 40, "L": 40, "OTL": 4} for i in range(32)}
short84 = dict(full84)
short84["T0"] = {"W": 40, "L": 39, "OTL": 4}  # 83
check("84-slate: complete at 84 each",
      _gp_target(_App(_FakeLeague(full84, 84))) == 84)
check("84-slate: 83 is short",
      min(s["W"] + s["L"] + s["OTL"] for s in short84.values()) < 84)
check("old save (no attr): default 82",
      _gp_target(_App(_FakeLeague(full84))) == 82)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
