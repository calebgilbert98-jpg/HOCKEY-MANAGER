"""QA for D41 Phase 2: real AHL league (background sim, no bloat).

Verifies:
1. Schedule: 720 games, exactly 48 per team, spread Oct-Apr, no team
   plays twice on one day.
2. Game sim speed: full 720-game season in <1s (<0.001s/game target).
3. Standings math: W/L/OTL/PTS/GF/GA correct; tiebreakers (pts, W, GD, GF).
4. Calder Cup: top-16 bracket completes, champion recorded in history,
   once-per-season guard, inbox headline posted.
5. No NHL conflicts: callup/senddown move players between
   team.roster <-> team.ahl_roster; the AHL club reads the SAME list
   object (dynamic aliasing); sims keep working.
6. Old-save backfill: a league with no ahl_* attrs gets a schedule
   generated, never raises.
7. Never raises on garbage input (None, empty league, <2 clubs, teams
   without parent_team, corrupt schedule entries).
"""
import sys
import os
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


class FakePlayer:
    _pid = 0
    def __init__(self, ovr, name="Test Player"):
        FakePlayer._pid += 1
        self._ovr = ovr
        self.full_name = name
        self.id = FakePlayer._pid
        self.ahl_stats = None
    def overall_rating(self):
        return self._ovr


class FakeNHLTeam:
    """NHL club: owns roster + ahl_roster (sole source of truth)."""
    def __init__(self, name, farm_ovrs):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.league_level = 1
        self.roster = []
        self.ahl_roster = [FakePlayer(o, f"{name} P{i}")
                           for i, o in enumerate(farm_ovrs)]
        self.affiliate_team = None
        self.is_user_team = False


class FakeAHLTeam:
    """AHL shell: no players of its own, just a parent link."""
    def __init__(self, name):
        self.team_name = name
        self.league_name = "American Hockey League"
        self.league_level = 2
        self.parent_team = None


class FakeInbox:
    def __init__(self):
        self.messages = []
    def add_message(self, m):
        self.messages.insert(0, m)


class FakeLeague:
    def __init__(self, nhl_teams, ahl_teams):
        self.teams = list(nhl_teams) + list(ahl_teams)
        self.season_year = 2026
        self.current_date = None


def make_league(n_ahl=30, farm_size=22, user_idx=0):
    nhl, ahl = [], []
    for i in range(n_ahl):
        # Vary farm strength so standings have shape.
        base = 62 + (i % 8)
        farm = [base + ((j * 7 + i) % 9) - 4 for j in range(farm_size)]
        t = FakeNHLTeam(f"NHL Club {i}", farm)
        a = FakeAHLTeam(f"AHL Club {i}")
        t.affiliate_team = a
        a.parent_team = t
        nhl.append(t)
        ahl.append(a)
    nhl[user_idx].is_user_team = True
    nhl[user_idx].inbox = FakeInbox()
    return FakeLeague(nhl, ahl), nhl, ahl


print("== D41 Phase 2 QA ==")
import ahl_league as A

# ---------------------------------------------------------------- 1. Schedule
league, nhl, ahl = make_league()
ok = A.generate_ahl_schedule(league)
sched = getattr(league, "ahl_schedule", None) or []
check("schedule generates", ok and isinstance(sched, list))
check("720 games scheduled", len(sched) == 720)

from collections import Counter
gp = Counter()
per_day = {}
for (dstr, h, a) in sched:
    gp[h] += 1
    gp[a] += 1
    per_day.setdefault(dstr, []).append((h, a))
check("48 games per team", all(v == 48 for v in gp.values()) and len(gp) == 30)

days = sorted(per_day)
check("spread Oct 2026 - Apr 2027",
      days[0] >= "2026-10-01" and days[-1] <= "2027-04-20")
dup_day = any(len({t for pair in pairs for t in pair}) != 2 * len(pairs)
              for pairs in per_day.values())
check("no team plays twice on one day", not dup_day)
check("schedule stamped to season",
      getattr(league, "ahl_schedule_season", None) == 2026)
check("no self-matchups", all(h != a for (_d, h, a) in sched))

# Deterministic per season: regenerate -> identical shape/dates.
sched2 = list(sched)
A.generate_ahl_schedule(league)
check("schedule deterministic per season_year",
      list(getattr(league, "ahl_schedule")) == sched2)

# ------------------------------------------------------- 2. Game sim speed
t0 = time.perf_counter()
results = [A.simulate_ahl_game(ahl[0], ahl[1]) for _ in range(720)]
dt = time.perf_counter() - t0
check("720 games sim in <1s", dt < 1.0)
print(f"       (720 games in {dt*1000:.1f}ms = {dt/720*1e6:.1f}us/game)")
check("scores are ints, winner decided",
      all(isinstance(r[0], int) and isinstance(r[1], int) and r[0] != r[1]
          for r in results))
check("OT flag is bool", all(isinstance(r[2], bool) for r in results))

# Score distribution sanity: mostly 1-6 goals, some OT.
ots = sum(1 for r in results if r[2])
tot = sum(r[0] + r[1] for r in results) / 720
check("plausible AHL scoring (~6 goals/game, some OT)",
      4.5 < tot < 8.0 and 0 < ots < 200)

# ------------------------------------------------------- 3. Standings math
league2, nhl2, ahl2 = make_league()
A.generate_ahl_schedule(league2)
A.update_ahl_standings(league2, 0, 1, 4, 2, went_ot=False)  # reg win
A.update_ahl_standings(league2, 0, 1, 3, 4, went_ot=True)   # OT loss
A.update_ahl_standings(league2, 2, 3, 5, 1, went_ot=False)
st = league2.ahl_standings
# Team 0: regulation win (2pts) + OT loss (1pt) = 3pts, 7GF/6GA/2GP.
check("regulation win = W + 2pts", st[0]["w"] == 1 and st[0]["pts"] == 3)
# Team 1: regulation loss (0pts) + OT win (2pts) = 2pts.
check("regulation loss = L, 0pts", st[1]["l"] == 1)
check("OT win = W + 2pts", st[1]["w"] == 1 and st[1]["pts"] == 2)
check("OT loss = OTL + 1pt", st[0]["otl"] == 1)
check("GF/GA/GP tracked",
      st[0]["gf"] == 7 and st[0]["ga"] == 6 and st[0]["gp"] == 2)

# Tiebreakers: same pts, more wins ranks higher; then GD; then GF.
league3, _, _ = make_league()
A.generate_ahl_schedule(league3)
s3 = league3.ahl_standings
s3[0] = {"w": 20, "l": 20, "otl": 8, "pts": 48, "gf": 140, "ga": 140, "gp": 48}
s3[1] = {"w": 22, "l": 22, "otl": 4, "pts": 48, "gf": 140, "ga": 140, "gp": 48}
s3[2] = {"w": 20, "l": 20, "otl": 8, "pts": 48, "gf": 150, "ga": 140, "gp": 48}
order = [i for i, _r in A.get_ahl_standings(league3)[:3]]
check("tiebreak: wins before GD", order[0] == 1)
check("tiebreak: GD before GF", order[1] == 2 and order[2] == 0)

# ------------------------------------------------- 4. Calder Cup
league4, nhl4, ahl4 = make_league()
A.generate_ahl_schedule(league4)
# Sim the whole regular season through the daily hook.
d = date(2026, 10, 1)
end = date(2027, 4, 20)
total_simmed = 0
while d <= end:
    total_simmed += A.simulate_ahl_scheduled_day(league4, d)
    d += timedelta(days=1)
check("full season sims all 720 games", total_simmed == 720)
played = getattr(league4, "ahl_played", set())
check("every game marked played", len(played) == 720)

# The last scheduled game auto-fires the Calder Cup via the daily hook.
check("Calder Cup auto-fires at season end",
      getattr(league4, "ahl_calder_done", None) == "2026-27")
hist = getattr(league4, "ahl_champions", [])
check("champion in league history",
      len(hist) == 1 and hist[0]["season"] == "2026-27"
      and hist[0]["champion_idx"] in range(30))
info = hist[0] if hist else {}
check("champion recorded", info.get("champion_idx") in range(30))
bracket = getattr(league4, "ahl_bracket", None) or {}
check("bracket persisted (4 rounds)",
      len(bracket.get("rounds", [])) == 4
      and [len(r) for r in bracket["rounds"]] == [8, 4, 2, 1])
check("series are best-of-5 (<=5 games)",
      all(s["games"] <= 5 for r in bracket["rounds"] for s in r))
check("once-per-season guard", A.run_calder_cup(league4) is None)
inbox = nhl4[0].inbox.messages
check("champion headline in user inbox",
      len(inbox) == 1 and "Calder Cup" in str(getattr(inbox[0], "subject", "")))

# Standings sanity after a full season: every team 48 GP, pts math.
st4 = league4.ahl_standings
check("all 30 clubs at 48 GP",
      all(st4[i]["gp"] == 48 for i in range(30)))
# Points invariant: every game awards 2 to the winner + 1 to an OT loser.
check("points math (2*W + OTL == PTS; W+L+OTL == GP)",
      all(r["pts"] == 2 * r["w"] + r["otl"] for r in st4.values())
      and all(r["w"] + r["l"] + r["otl"] == r["gp"] for r in st4.values())
      and sum(r["gp"] for r in st4.values()) == 720 * 2)

# Explicit run_calder_cup on a fresh league with hand-built standings.
league4b, nhl4b, ahl4b = make_league()
A.generate_ahl_schedule(league4b)
for i in range(30):
    league4b.ahl_standings[i] = {"w": 30 - i, "l": i, "otl": 0,
                                 "pts": (30 - i) * 2, "gf": 150, "ga": 100 + i,
                                 "gp": 30}
info4b = A.run_calder_cup(league4b)
check("explicit run_calder_cup completes", isinstance(info4b, dict))
check("top seed can win it all (sanity)",
      info4b.get("champion_idx") in range(30))
bracket4b = getattr(league4b, "ahl_bracket", None) or {}
check("bracket persisted (4 rounds, 8/4/2/1 series)",
      len(bracket4b.get("rounds", [])) == 4
      and [len(r) for r in bracket4b["rounds"]] == [8, 4, 2, 1])
check("series are best-of-5 (<=5 games)",
      all(s["games"] <= 5 for r in bracket4b["rounds"] for s in r))
check("once-per-season guard", A.run_calder_cup(league4b) is None)
inbox4b = nhl4b[0].inbox.messages
check("champion headline in user inbox",
      len(inbox4b) == 1 and "Calder Cup" in str(getattr(inbox4b[0], "subject", "")))

# maybe_run_calder_cup: no-op mid-season, fires when complete.
league5, _, _ = make_league()
A.generate_ahl_schedule(league5)
A.simulate_ahl_scheduled_day(league5, date(2026, 11, 1))
check("no Cup mid-season",
      A.maybe_run_calder_cup(league5, date(2026, 11, 1)) is None
      and getattr(league5, "ahl_calder_done", None) is None)

# --------------------------------------- 5. No conflicts with NHL roster ops
league6, nhl6, ahl6 = make_league()
A.generate_ahl_schedule(league6)
team = nhl6[3]
farm_before = team.ahl_roster
# CALLUP: move a player farm -> NHL roster.
p = farm_before.pop(0)
team.roster.append(p)
# SENDDOWN: move a different player NHL -> farm.
q = FakePlayer(80, "Demoted Vet")
team.ahl_roster.append(q)
check("callup/senddown mutate the same list",
      team.ahl_roster is farm_before)
roster = A.get_ahl_roster(ahl6[3])
check("AHL club reads the live list (dynamic aliasing)",
      roster is team.ahl_roster and q in roster and p not in roster)
# Strength follows the live roster.
s_before = A._team_strength(ahl6[3])
team.ahl_roster.append(FakePlayer(95, "Superstar Demotion"))
check("team strength tracks callups/senddowns live",
      A._team_strength(ahl6[3]) > s_before)
# Sims keep working after roster ops.
n = A.simulate_ahl_scheduled_day(league6, date(2026, 10, 5))
check("scheduled sims work after roster ops", n > 0)

# The 2 NHL clubs without affiliates: stat rolls but no AHL games.
class FakeNoAffiliate(FakeNHLTeam):
    pass
league7, nhl7, ahl7 = make_league()
lonely = FakeNoAffiliate("Expansion Club", [70] * 20)
league7.teams.append(lonely)  # no affiliate_team link
A.generate_ahl_schedule(league7)
check("unaffiliated club has no AHL shell in the league",
      all(A.get_ahl_roster(a) is not lonely.ahl_roster for a in ahl7))
check("schedule still 720 games (30 clubs only)",
      len(league7.ahl_schedule) == 720)

# ------------------------------------------------- 6. Old-save backfill
class OldSaveLeague:
    """Pickled before D41 Phase 2: no ahl_* attributes at all."""
    def __init__(self, nhl, ahl):
        self.teams = list(nhl) + list(ahl)
        self.season_year = 2026

old = OldSaveLeague(*make_league()[1:])
check("backfill generates schedule on old save",
      A.backfill_ahl_league(old) is True
      and len(getattr(old, "ahl_schedule", [])) == 720)
check("backfill idempotent (live schedule kept)",
      A.backfill_ahl_league(old) is True
      and len(getattr(old, "ahl_schedule", [])) == 720)
check("old save sims a day without raising",
      A.simulate_ahl_scheduled_day(old, date(2026, 10, 3)) >= 0)

# Season rollover: new schedule, fresh standings, Cup backstop.
league8, _, _ = make_league()
A.generate_ahl_schedule(league8)
# Sim only HALF the season: the daily auto-Cup never fires, so the
# rollover backstop must crown from the partial standings.
d = date(2026, 10, 1)
while d <= date(2027, 1, 15):
    A.simulate_ahl_scheduled_day(league8, d)
    d += timedelta(days=1)
check("Cup not fired mid-season (rollover test setup)",
      getattr(league8, "ahl_calder_done", None) is None)
league8.season_year = 2027  # end_of_season already incremented
A.ahl_season_rollover(league8)
check("rollover backstop crowns champion for old season",
      any(h.get("season") == "2026-27"
          for h in getattr(league8, "ahl_champions", [])))
check("rollover generates new-season schedule",
      getattr(league8, "ahl_schedule_season", None) == 2027
      and len(league8.ahl_schedule) == 720)
check("rollover zeroes standings",
      all(v == 0 for r in league8.ahl_standings.values() for v in r.values()))
check("champion history survives rollover",
      len(getattr(league8, "ahl_champions", [])) == 1)

# ------------------------------------------------- 7. Never raises on garbage
garbage_calls = [
    lambda: A.generate_ahl_schedule(None),
    lambda: A.generate_ahl_schedule(object()),
    lambda: A.ahl_schedule_active(None),
    lambda: A.simulate_ahl_game(None, None),
    lambda: A.simulate_ahl_game(object(), object()),
    lambda: A.update_ahl_standings(None, 0, 1, 3, 2),
    lambda: A.get_ahl_standings(None),
    lambda: A.simulate_ahl_scheduled_day(None, None),
    lambda: A.run_calder_cup(None),
    lambda: A.maybe_run_calder_cup(None, None),
    lambda: A.ahl_season_rollover(None),
    lambda: A.backfill_ahl_league(None),
    lambda: A.get_ahl_roster(None),
    lambda: A.get_ahl_roster(object()),
]
ok = True
for i, fn in enumerate(garbage_calls):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"       RAISED on garbage case {i}: {e!r}")
check("never raises on garbage input", ok)

# Degenerate leagues: empty, 1 club, clubs without parents.
class BareLeague:
    def __init__(self, teams):
        self.teams = teams
        self.season_year = 2026
check("empty league: no schedule, no crash",
      A.generate_ahl_schedule(BareLeague([])) is False
      and A.ahl_schedule_active(BareLeague([])) is False)
one = BareLeague([FakeAHLTeam("Lonely")])
check("single club: no schedule, fallback signal",
      A.generate_ahl_schedule(one) is False
      and A.run_calder_cup(one) is None)
parentless = BareLeague([FakeAHLTeam(f"C{i}") for i in range(6)])
A.generate_ahl_schedule(parentless)
check("parentless clubs sim with baseline strength",
      A.simulate_ahl_scheduled_day(parentless, date(2026, 10, 10)) >= 0)
check("corrupt schedule entry skipped, not fatal",
      A.update_ahl_standings(parentless, 99, -1, 3, 2) in (True, False))

print(f"\n== {PASS} passed, {FAIL} failed ==")
sys.exit(1 if FAIL else 0)
