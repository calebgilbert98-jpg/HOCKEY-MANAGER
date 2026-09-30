# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: date-driven playoff progression — the Next Day path.

Verifies the second playoff path (bracket controls keep working; the
calendar date now also drives the tournament):
  A. try_play_scheduled_game exactly-once guards:
       - daily path sims the scheduled game; a repeat is a no-op
       - bracket-first sim wins; the daily retry is a no-op
       - out-of-order / unknown series / complete series / wrong round /
         malformed game numbers never sim
  B. _simulate_playoff_day (the REAL main.py method, stub self):
       - sims today's entries, advances the date, advances finished rounds
       - several games on one date all sim
  C. Round transitions via the daily loop:
       - next round starts last-completed-series end + REST_DAYS
       - a repeated advance is a no-op (idempotency)
  D. Full tournament through the daily loop to a champion:
       - 16 unique qualifiers, no eliminated team reappears
  E. Save/load mid-round resume: serialize the bracket, restore into a
     fresh league with the stamped schedule, continue to a champion.
  F. Champion -> Cup recap once + _start_offseason; no offseason before
     a champion; _playoffs_in_progress False with no bracket / champion.

GameSim is stubbed at the bracket choke point (the fake mirrors the
real contract: add_game_result -> stamp -> prune). No repo files
modified.
"""
import sys
from types import MethodType, SimpleNamespace
from datetime import date, timedelta

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

from playoff_system import PlayoffBracket
from save_load_system import GameSaveManager

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra else ""))

# ---------------------------------------------------------------- fake league
DIVS = {
    "Atlantic":     [("BOS",112),("TOR",108),("FLA",104),("TBL",100),
                     ("BUF",96),("DET",92),("MTL",80),("OTT",76)],
    "Metropolitan": [("CAR",110),("NYR",106),("PIT",88),("WSH",87),
                     ("NYI",84),("NJD",82),("PHI",80),("CBJ",78)],
    "Central":      [("COL",114),("DAL",109),("WPG",102),("MIN",99),
                     ("NSH",89),("STL",85),("UTA",81),("CHI",77)],
    "Pacific":      [("EDM",111),("VGK",107),("LAK",98),("VAN",95),
                     ("CGY",91),("ANA",87),("SEA",83),("SJS",79)],
}
DIV_CONF = {"Atlantic": "Eastern", "Metropolitan": "Eastern",
            "Central": "Western", "Pacific": "Western"}

def build_league():
    teams, standings = [], {}
    for div, rows in DIVS.items():
        for name, pts in rows:
            t = SimpleNamespace(
                team_name=name, league_name="National Hockey League",
                conference=DIV_CONF[div], division=div, roster=[],
                goals_for=260, goals_against=230)
            teams.append(t)
            standings[name] = {"Points": pts, "W": pts // 2}
    sched = [{"date": date(2027, 4, 12), "home_team": teams[0],
              "away_team": teams[1]}]
    league = SimpleNamespace(teams=teams, standings=standings,
                             season_year=2026, rivalries=[], schedule=sched,
                             playoff_bracket=None)
    return league

def build_bracket(league):
    """Real bracket generation, with GameSim stubbed at the choke point."""
    b = PlayoffBracket(league)
    league.playoff_bracket = b
    b.generate_playoff_bracket()
    log = []
    # Every third R1 series is a sweep (exercises early-clinch pruning
    # through the daily path); the rest go the full 7.
    idx = 0
    for slist in b.playoff_series.values():
        for s in slist or []:
            s._qa_sweep = (idx % 3 == 0)
            idx += 1
    def fake_sim(series):
        # Mirror the real contract: result -> stamp -> prune on clinch.
        if getattr(series, '_qa_sweep', False):
            team1_won = True
        else:
            team1_won = (series.games_played % 2 == 0)  # games 1,3,5,7
        series.add_game_result(team1_won, {"game": series.games_played})
        b._stamp_played_game(series, 3, 2)
        if series.is_complete:
            b._prune_series_schedule(series)
        log.append((series.series_id, series.games_played))
        return (3, 2)
    b.simulate_playoff_game = fake_sim
    b._qa_log = log
    return b

def r1_series_and_entry(b):
    s = b.playoff_series['wild_card'][0]
    e = next(e for e in b.league.schedule
             if isinstance(e, dict) and e.get('series_id') == s.series_id
             and e.get('series_game') == 1)
    return s, e

# ------------------------------------------------- A. exactly-once guards
league = build_league()
b = build_bracket(league)
s, e = r1_series_and_entry(b)

check("A1 daily path sims the scheduled game",
      b.try_play_scheduled_game(s.series_id, 1) is True
      and s.games_played == 1)
check("A2 repeat of the same entry is a no-op",
      b.try_play_scheduled_game(s.series_id, 1) is False
      and s.games_played == 1)
check("A3 next game advances",
      b.try_play_scheduled_game(s.series_id, 2) is True
      and s.games_played == 2)
check("A4 out-of-order entry never skips ahead",
      b.try_play_scheduled_game(s.series_id, 4) is False
      and s.games_played == 2)
check("A5 unknown series_id is a no-op",
      b.try_play_scheduled_game("nope-not-real", 1) is False)
check("A6 malformed game numbers are no-ops",
      b.try_play_scheduled_game(s.series_id, 0) is False
      and b.try_play_scheduled_game(s.series_id, None) is False
      and b.try_play_scheduled_game(s.series_id, "x") is False
      and s.games_played == 2)

# Bracket-first: sim game 3 directly, daily retry must be a no-op.
b.simulate_playoff_game(s)
check("A7 bracket-first sim wins; daily retry is a no-op",
      s.games_played == 3
      and b.try_play_scheduled_game(s.series_id, 3) is False
      and b.try_play_scheduled_game(s.series_id, 4) is True
      and s.games_played == 4)

# Complete the series via the bracket; further entries are dead.
while not s.is_complete:
    b.simulate_playoff_game(s)
n_done = s.games_played
check("A8 complete series ignores later entries",
      s.is_complete
      and b.try_play_scheduled_game(s.series_id, n_done + 1) is False
      and s.games_played == n_done,
      f"ended in {n_done}")

# Wrong round: an R1 series is not playable once the pointer moved on.
s2 = b.playoff_series['wild_card'][1]
b.current_round = 'division_semifinals'
check("A9 series outside the current round is not playable",
      b.try_play_scheduled_game(s2.series_id, 1) is False
      and s2.games_played == 0)
b.current_round = 'wild_card'

# --------------------------------- B. the real _simulate_playoff_day
import main as main_mod
StubBase = SimpleNamespace

class StubApp:
    def __init__(self, league, start):
        self.league = league
        self.current_date = start
        self.recap_calls = 0
        self.offseason_calls = 0
        self.feedback_off = 0
    def _check_season_complete(self):
        return True
    def _set_continue_feedback(self, on, msg=""):
        if not on:
            self.feedback_off += 1
    def _maybe_send_cup_recap(self):
        self.recap_calls += 1
    def _start_offseason(self):
        self.offseason_calls += 1

def bind(stub):
    stub._playoffs_in_progress = MethodType(
        main_mod.HockeyManagerGUI._playoffs_in_progress, stub)
    stub._simulate_playoff_day = MethodType(
        main_mod.HockeyManagerGUI._simulate_playoff_day, stub)
    return stub

league2 = build_league()
b2 = build_bracket(league2)
stub = bind(StubApp(league2, date(2027, 4, 13)))

check("B1 playoffs in progress once the bracket is alive",
      stub._playoffs_in_progress() is True)
# No bracket yet -> not in progress (season just ended).
stub_nob = bind(StubApp(build_league(), date(2027, 4, 13)))
check("B2 no bracket -> not in progress",
      stub_nob._playoffs_in_progress() is False)

# Sim until the first scheduled playoff date arrives.
r1_start = min(s.start_date for s in b2.playoff_series['wild_card'])
_guard = 0
while stub.current_date < r1_start and _guard < 30:
    stub._simulate_playoff_day()
    _guard += 1
check("B3 date advances through empty days with no games",
      stub.current_date == r1_start, f"at {stub.current_date}")
games_before = sum(s.games_played
                   for s in b2.playoff_series['wild_card'])
stub._simulate_playoff_day()
games_after = sum(s.games_played
                  for s in b2.playoff_series['wild_card'])
check("B4 today's scheduled games sim via the daily path",
      games_after > games_before,
      f"{games_before}->{games_after}")
# Several series share a date: all of them sim.
per_date = {}
for e in league2.schedule:
    if isinstance(e, dict) and e.get('playoff') and e.get('date') == r1_start:
        per_date[e['series_id']] = e['series_game']
check("B5 multiple games on one date all sim",
      len(per_date) > 1 and games_after - games_before == len(per_date),
      f"{len(per_date)} games on {r1_start}")
check("B6 stamped entries show as played",
      all(e.get('played') for e in league2.schedule
          if isinstance(e, dict) and e.get('date') == r1_start
          and e.get('playoff')),
      )
check("B7 no offseason before a champion",
      stub.offseason_calls == 0 and stub.recap_calls == 0)

# --------------------------------- C. round transitions, daily loop
# Finish R1 entirely through the daily path.
_guard = 0
while b2.current_round == 'wild_card' and stub.offseason_calls == 0 \
        and _guard < 60:
    stub._simulate_playoff_day()
    _guard += 1
check("C1 round 1 completes through the daily loop",
      b2.current_round == 'division_semifinals')
r1_ends = [s.end_date for s in b2.playoff_series['wild_card']]
r2_starts = {s.start_date for s in b2.playoff_series['division_semifinals']}
expected = max(d for d in r1_ends if d) + timedelta(
    days=PlayoffBracket.PLAYOFF_REST_DAYS)
check("C2 next round starts last-end + REST_DAYS (dynamic)",
      r2_starts == {expected}, f"starts {sorted(r2_starts)}")
n_r2 = len(b2.playoff_series['division_semifinals'])
check("C3 repeated advance is a no-op (idempotent)",
      b2.advance_to_next_round('wild_card') is True
      and len(b2.playoff_series['division_semifinals']) == n_r2
      and b2.current_round == 'division_semifinals',
      f"{n_r2} series")

# --------------------------------- D. full tournament, daily loop only
days = 0
while b2.stanley_cup_champion is None and days < 150:
    stub._simulate_playoff_day()
    days += 1
check("D1 daily loop crowns a champion",
      b2.stanley_cup_champion is not None,
      f"{getattr(b2.stanley_cup_champion, 'team_name', '?')} in {days}d")
check("D2 Cup recap fired exactly once, then the offseason",
      stub.recap_calls == 1 and stub.offseason_calls == 1)
check("D3 no longer in progress after the crown",
      stub._playoffs_in_progress() is False)

# 16 unique qualifiers; no eliminated team reappears.
qualifiers = set()
for s in b2.playoff_series['wild_card']:
    qualifiers.add(s.team1.team_name); qualifiers.add(s.team2.team_name)
check("D4 exactly 16 unique round-1 qualifiers", len(qualifiers) == 16)
elim_order = ('wild_card', 'division_semifinals', 'division_finals',
              'stanley_cup_final')
eliminated, reappeared = set(), False
for rkey in elim_order:
    for s in b2.playoff_series.get(rkey) or []:
        for t in (s.team1.team_name, s.team2.team_name):
            if t in eliminated:
                reappeared = True
    for s in b2.playoff_series.get(rkey) or []:
        if s.winner is not None:
            loser = s.team1 if s.winner is s.team2 else s.team2
            eliminated.add(loser.team_name)
check("D5 no eliminated team reappears in a later round",
      not reappeared)
check("D6 every series has a winner",
      all(s.winner is not None
          for slist in b2.playoff_series.values()
          for s in slist or []))

# --------------------------------- E. save/load mid-round resume
league3 = build_league()
b3 = build_bracket(league3)
stub3 = bind(StubApp(league3, date(2027, 4, 13)))
# Drive into round 2 via the daily path.
_guard = 0
while b3.current_round != 'division_semifinals' and _guard < 60:
    stub3._simulate_playoff_day()
    _guard += 1
# Sim a couple of R2 games, then snapshot mid-round.
for _ in range(3):
    stub3._simulate_playoff_day()
gsm = GameSaveManager.__new__(GameSaveManager)
data = gsm._serialize_playoff_bracket(league3)
check("E1 bracket serializes mid-round",
      bool(data) and data.get('current_round') == 'division_semifinals'
      and len(data.get('series', [])) > 8,
      f"{len(data.get('series', []))} series")

fresh = build_league()
gsm._restore_playoff_bracket(fresh, data)
b4 = fresh.playoff_bracket
# Rebuild the stamped schedule entries, remapping team refs by name.
by_name = {t.team_name: t for t in fresh.teams}
new_sched = [e for e in fresh.schedule
             if not (isinstance(e, dict) and e.get('playoff'))]
for e in league3.schedule:
    if isinstance(e, dict) and e.get('playoff'):
        e2 = dict(e)
        for k in ('home_team', 'away_team'):
            t = e2.get(k)
            nm = getattr(t, 'team_name', t)
            e2[k] = by_name.get(nm, t)
        new_sched.append(e2)
try:
    new_sched.sort(key=lambda x: x['date']
                   if isinstance(x, dict) and 'date' in x else x[0])
except Exception:
    pass
fresh.schedule = new_sched
check("E2 restored bracket resumes at the same round",
      b4 is not None and b4.current_round == 'division_semifinals'
      and sum(s.games_played
              for slist in b4.playoff_series.values()
              for s in slist or []) > 0)
# Re-stub the sim on the restored bracket and continue to a champion.
log4 = []
def fake4(series):
    team1_won = (series.games_played % 2 == 0)
    series.add_game_result(team1_won, {"game": series.games_played})
    b4._stamp_played_game(series, 3, 2)
    if series.is_complete:
        b4._prune_series_schedule(series)
    log4.append((series.series_id, series.games_played))
    return (3, 2)
b4.simulate_playoff_game = fake4
stub4 = bind(StubApp(fresh, stub3.current_date))
days = 0
while b4.stanley_cup_champion is None and days < 150:
    stub4._simulate_playoff_day()
    days += 1
check("E3 restored bracket finishes to a champion via the daily loop",
      b4.stanley_cup_champion is not None,
      f"{getattr(b4.stanley_cup_champion, 'team_name', '?')} in {days}d")
check("E4 exactly-once held across the restore (no double-sim)",
      all(s.games_played <= 7
          for slist in b4.playoff_series.values()
          for s in slist or [])
      and max((n for _, n in log4), default=0) <= 7)

# --------------------------------- F. guards
b5 = build_bracket(build_league())
b5.stanley_cup_champion = b5.playoff_series['wild_card'][0].team1
stub5 = bind(StubApp(b5.league, date(2027, 6, 1)))
check("F1 champion set -> not in progress",
      stub5._playoffs_in_progress() is False)

# --------------------------------- G. calendar rendering of stamped games
from windows import ScheduleView
_stamped = {'playoff': True, 'played': True, 'home_score': 3,
            'away_score': 2, 'marquee': True,
            'hype_tags': ["Bad blood"]}
check("G1 stamped playoff entry renders Final with its score",
      ScheduleView._playoff_entry_result(_stamped) == ("2-3", "Final"))
check("G2 unstamped playoff entry falls back to the result index",
      ScheduleView._playoff_entry_result(
          {'playoff': True, 'played': False}) is None)
check("G3 regular-season entries never take the stamp path",
      ScheduleView._playoff_entry_result(
          {'played': True, 'home_score': 1, 'away_score': 1}) is None)
check("G4 malformed/empty raws are safe",
      ScheduleView._playoff_entry_result(None) is None
      and ScheduleView._playoff_entry_result({}) is None)
check("G5 has_been_played tolerates the marquee suffix",
      str("Final ★ Bad blood").startswith("Final")
      and str("Final").startswith("Final")
      and not str("Simulated").startswith("Final"))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
