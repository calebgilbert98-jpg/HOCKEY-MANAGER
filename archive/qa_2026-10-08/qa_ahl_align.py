"""QA for AHL per-player stat alignment (D41-2b).

The 48-game team schedule is the truth: per-player AHL ledgers must
never exceed their club's GP. Verifies:

1. Scheduled path: affiliated-farm skaters present all season finish
   with GP == team GP (48); goalies split starts, each <= team GP.
2. Mid-season callup: a player removed from the farm list freezes his
   GP while teammates keep accumulating.
3. Unaffiliated farms: simulate_ahl_day(only_unscheduled=True) rolls
   only for farm lists with no AHL club; affiliated players untouched.
4. Fallback path: simulate_ahl_day() with no schedule targets ~48 GP.
5. Recall gate: dressed games still count toward
   ahl_games_since_assignment.
6. Realistic production: P/GP and SV% in sane bands.
7. Performance: full-season batch (team sims + player lines) stays fast.
8. Never raises on garbage input.
9. No double-logging when a date is ticked twice.
"""
import sys
import os
import time
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ahl_league
import ahl_system

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


class FakeLedger:
    def __init__(self):
        self.games_played = 0
        self.goals = 0
        self.assists = 0
        self.shots = 0
        self.penalties = 0
        self.penalties_in_minutes = 0
        self.shots_against = 0
        self.saves = 0
        self.goals_against = 0
        self.shutouts = 0
        self.wins = 0
        self.losses = 0
        self.save_percentage = 0.0

    def _update_goalie_stats(self):
        sa = self.shots_against or 0
        self.save_percentage = (self.saves / sa) if sa else 0.0


class FakePlayer:
    _pid = 0

    def __init__(self, ovr, goalie=False):
        FakePlayer._pid += 1
        self._ovr = ovr
        self.id = FakePlayer._pid
        self.full_name = f"Test Player {self._pid}"
        self.ahl_stats = FakeLedger()
        if goalie:
            self.primary_position = "GOALIE"

    def overall_rating(self):
        return self._ovr


class FakeNHLTeam:
    def __init__(self, name, farm):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.league_level = 1
        self.roster = []
        self.ahl_roster = farm


class FakeAHLTeam:
    def __init__(self, name):
        self.team_name = name
        self.league_name = "American Hockey League"
        self.league_level = 2
        self.parent_team = None


class FakeLeague:
    def __init__(self, nhl_teams, ahl_teams):
        self.teams = list(nhl_teams) + list(ahl_teams)
        self.season_year = 2026


def make_league(n_affiliated=6, farm_size=24, n_goalies=2, seed=42):
    random.seed(seed)
    nhl, ahl = [], []
    for i in range(n_affiliated):
        farm = []
        for j in range(farm_size - n_goalies):
            farm.append(FakePlayer(60 + ((i * 7 + j) % 18)))
        for j in range(n_goalies):
            farm.append(FakePlayer(62 + ((i + j) % 10), goalie=True))
        t = FakeNHLTeam(f"NHL Club {i}", farm)
        nhl.append(t)
        a = FakeAHLTeam(f"AHL Club {i}")
        a.parent_team = t
        ahl.append(a)
    # One unaffiliated NHL club: its farm has no AHL shell.
    lone_farm = [FakePlayer(64 + (j % 10)) for j in range(12)]
    lone = FakeNHLTeam("Lone NHL Club", lone_farm)
    nhl.append(lone)
    return FakeLeague(nhl, ahl), nhl, ahl


def team_gp(league, ahl_idx):
    for idx, rec in ahl_league.get_ahl_standings(league):
        if idx == ahl_idx:
            return rec.get("gp", 0)
    return 0


def run_full_season(league):
    """Tick every calendar day Oct 1 -> Apr 30 like the daily path."""
    t0 = time.time()
    d = date(2026, 10, 1)
    end = date(2027, 4, 30)
    while d <= end:
        ahl_league.simulate_ahl_scheduled_day(league, d)
        d += timedelta(days=1)
    return time.time() - t0


print("== AHL per-player alignment ==")
league, nhl, ahl = make_league()
check("schedule generates", ahl_league.generate_ahl_schedule(league))

elapsed = run_full_season(league)
print(f"  (full-season batch with player lines: {elapsed:.2f}s)")

# 1. Team GP is 48 everywhere.
gps = [team_gp(league, i) for i in range(len(ahl))]
check("every club played 48", all(g == 48 for g in gps))

# 2. Affiliated skaters present all season: GP == team GP exactly.
ok_eq = True
ok_le = True
for i, a in enumerate(ahl):
    tgp = team_gp(league, i)
    for p in nhl[i].ahl_roster:
        gp = p.ahl_stats.games_played
        if gp > tgp:
            ok_le = False
        if not ahl_system._is_goalie(p) and gp != tgp:
            ok_eq = False
check("no player GP exceeds team GP", ok_le)
check("full-season skaters GP == team GP (48)", ok_eq)

# 3. Goalies split starts realistically.
g_ok = True
for i, a in enumerate(ahl):
    tgp = team_gp(league, i)
    gl = [p for p in nhl[i].ahl_roster if ahl_system._is_goalie(p)]
    tot = sum(p.ahl_stats.games_played for p in gl)
    if not all(0 < p.ahl_stats.games_played <= tgp for p in gl):
        g_ok = False
    if not (15 <= tot <= 80):
        g_ok = False
check("goalies split starts within team GP", g_ok)

# 4. Realistic production bands.
tops = []
for i in range(len(ahl)):
    for p in nhl[i].ahl_roster:
        if ahl_system._is_goalie(p):
            continue
        gp = p.ahl_stats.games_played or 1
        ppg = (p.ahl_stats.goals + p.ahl_stats.assists) / gp
        tops.append(ppg)
tops.sort(reverse=True)
check("scoring leader P/GP sane (< 1.6)",
      len(tops) > 0 and tops[0] < 1.6)
svs = [p.ahl_stats.save_percentage for i in range(len(ahl))
       for p in nhl[i].ahl_roster if ahl_system._is_goalie(p)
       and p.ahl_stats.games_played >= 10]
check("goalie SV% sane (.850-.950)",
      len(svs) > 0 and all(0.850 <= s <= 0.950 for s in svs))

# 5. Mid-season callup freezes GP.
league2, nhl2, ahl2 = make_league(seed=7)
ahl_league.generate_ahl_schedule(league2)
mid = date(2027, 1, 15)
d = date(2026, 10, 1)
while d <= mid:
    ahl_league.simulate_ahl_scheduled_day(league2, d)
    d += timedelta(days=1)
called = nhl2[0].ahl_roster[0]
gp_at_callup = called.ahl_stats.games_played
nhl2[0].ahl_roster.remove(called)  # the callup
nhl2[0].roster.append(called)
d = mid + timedelta(days=1)
while d <= date(2027, 4, 30):
    ahl_league.simulate_ahl_scheduled_day(league2, d)
    d += timedelta(days=1)
mate_gp = nhl2[0].ahl_roster[0].ahl_stats.games_played
check("callup freezes GP while teammates continue",
      called.ahl_stats.games_played == gp_at_callup and mate_gp > gp_at_callup)

# 6. only_unscheduled: affiliated untouched, lone farm rolls.
league3, nhl3, ahl3 = make_league(seed=11)
ahl_league.generate_ahl_schedule(league3)
before = nhl3[0].ahl_roster[0].ahl_stats.games_played
random.seed(11)
for _ in range(184):
    ahl_system.simulate_ahl_day(league3, only_unscheduled=True)
after = nhl3[0].ahl_roster[0].ahl_stats.games_played
lone_gp = nhl3[-1].ahl_roster[0].ahl_stats.games_played
check("affiliated farm untouched by unscheduled rolls", after == before)
check("unaffiliated farm rolls ~48 GP", 25 <= lone_gp <= 70)

# 7. Fallback (no schedule): daily rolls target ~48.
class BareLeague:
    def __init__(self, teams):
        self.teams = teams
        self.season_year = 2026

farm = [FakePlayer(65 + (j % 12)) for j in range(20)]
bare = BareLeague([FakeNHLTeam("Bare Club", farm)])
random.seed(21)
for _ in range(184):
    ahl_system.simulate_ahl_day(bare)
fb_gp = farm[0].ahl_stats.games_played
check("fallback daily rolls target ~48 GP", 25 <= fb_gp <= 70)

# 8. Recall gate still counts dressed games.
p = FakePlayer(70)
p.ahl_games_since_assignment = 0
solo = FakeAHLTeam("Solo")
par = FakeNHLTeam("Parent", [p])
solo.parent_team = par
n = ahl_system.log_scheduled_game_for_club(solo)
check("dressed game counts toward recall gate",
      n == 1 and p.ahl_games_since_assignment == 1
      and p.ahl_stats.games_played == 1)

# 9. No double-logging on repeated ticks.
league4, nhl4, ahl4 = make_league(n_affiliated=4, seed=31)
ahl_league.generate_ahl_schedule(league4)
sched = league4.ahl_schedule
first_date = date.fromisoformat(sched[0][0])
ahl_league.simulate_ahl_scheduled_day(league4, first_date)
gp1 = nhl4[0].ahl_roster[0].ahl_stats.games_played
ahl_league.simulate_ahl_scheduled_day(league4, first_date)
gp2 = nhl4[0].ahl_roster[0].ahl_stats.games_played
check("repeat tick does not double-log", gp1 == gp2)

# 10. Never raises on garbage.
try:
    ahl_system.log_scheduled_game_for_club(None)
    ahl_system.log_scheduled_game_for_club(object())
    ahl_system.simulate_ahl_day(None, only_unscheduled=True)
    ahl_system.simulate_ahl_day(None)
    check("garbage input never raises", True)
except Exception as e:
    print(f"  raised: {e}")
    check("garbage input never raises", False)

# 11. Performance: full-season batch stays fast (< 2s incl. player lines).
check("full-season batch with player lines < 2s", elapsed < 2.0)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)