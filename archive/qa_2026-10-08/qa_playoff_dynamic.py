# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: dynamic playoff scheduling — qualification, calendar, advancement.

Verifies, on a fake 32-team league through the REAL bracket code paths:
  1. NHL qualification: top 3 per division + 2 wild cards per conference
     (division rank beats raw points — a 4th-place team with MORE points
     than another division's 3rd-place team still misses).
  2. Round-1 NHL pairings: DW1 vs WC2, 2v3, 2v3, DW2 vs WC1.
  3. Round 1 lands on the calendar: every series dated, 56 entries
     published to league.schedule, 2-2-1-1-1 venues.
  4. Series completion stamps end_date; unplayed games pruned.
  5. Advancement GATE: partial round refuses; full round advances with
     next start = last series end + 2 days (dynamic timing).
  6. Full tournament to a champion through the real advance path.
  7. Save/load round-trip preserves series dates.

No repo files modified. No GameSim needed (series driven via
add_game_result, the same completion signal the sim produces).
"""
import sys
from types import SimpleNamespace
from datetime import date, timedelta

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

from playoff_system import PlayoffBracket, PlayoffSeries

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra else ""))

# ---------------------------------------------------------------- fake league
# 4 divisions x 8 teams. Crafted points so the NHL-format edge bites:
# Detroit (92 pts, ATL 6th) MISSES despite outpointing Pittsburgh
# (88 pts, MET 3rd) who gets the automatic top-3 division spot.
# Straight-top-8-by-points would take DET over PIT; the NHL does not.
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

teams, standings = [], {}
for div, rows in DIVS.items():
    for name, pts in rows:
        t = SimpleNamespace(
            team_name=name, league_name="National Hockey League",
            conference=DIV_CONF[div], division=div, roster=[],
            goals_for=260, goals_against=230)
        teams.append(t)
        standings[name] = {"Points": pts, "W": pts // 2}

# Regular-season schedule: last game April 12, 2027.
sched = [{"date": date(2027, 4, 12), "home_team": teams[0],
          "away_team": teams[1]}]
league = SimpleNamespace(teams=teams, standings=standings,
                         season_year=2026, rivalries=[], schedule=sched,
                         playoff_bracket=None)

# ------------------------------------------------------- 1. qualification
b = PlayoffBracket(league)
league.playoff_bracket = b  # the real game registers it on the league
b.generate_playoff_bracket()

east_names = [t.team_name for t in b.eastern_teams]
west_names = [t.team_name for t in b.western_teams]
check("16 teams qualify", len(east_names) == 8 and len(west_names) == 8,
      f"E={len(east_names)} W={len(west_names)}")
# Division rank beats points: DET (92, ATL 6th) OUT, PIT (88, MET 3rd) IN.
check("DET (92pts) misses despite outpointing PIT", "DET" not in east_names)
check("PIT (88pts, MET 3rd) qualifies", "PIT" in east_names)
# Wild cards: next 2 best in conference (pure points, as in the NHL).
check("East WC = TBL, BUF", set(east_names[6:8]) == {"TBL", "BUF"},
      str(east_names[6:8]))
check("West WC = MIN, VAN", set(west_names[6:8]) == {"MIN", "VAN"},
      str(west_names[6:8]))
# Bracket order: [DW1, DW2, D1#2, D1#3, D2#2, D2#3, WC1, WC2].
# East: DW1=BOS(112, ATL), DW2=CAR(110, MET); D1(ATL)=TOR,FLA; D2(MET)=NYR,PIT.
check("East bracket order",
      east_names == ["BOS","CAR","TOR","FLA","NYR","PIT","TBL","BUF"],
      str(east_names))
check("West bracket order",
      west_names == ["COL","EDM","DAL","WPG","VGK","LAK","MIN","VAN"],
      str(west_names))

# ------------------------------------------------------- 2. R1 pairings (NHL)
r1 = b.playoff_series["wild_card"]
pairs = [(s.team1.team_name, s.team2.team_name) for s in r1[:4]]
check("R1 East: DW1 vs WC2", pairs[0] == ("BOS", "BUF"), str(pairs[0]))
check("R1 East: ATL 2v3", pairs[1] == ("TOR", "FLA"), str(pairs[1]))
check("R1 East: MET 2v3", pairs[2] == ("NYR", "PIT"), str(pairs[2]))
check("R1 East: DW2 vs WC1", pairs[3] == ("CAR", "TBL"), str(pairs[3]))

# ------------------------------------------------------- 3. R1 on the calendar
po_entries = [e for e in league.schedule
              if isinstance(e, dict) and e.get("playoff")]
check("56 R1 entries published", len(po_entries) == 56, str(len(po_entries)))
r1_starts = {s.start_date for s in r1}
check("R1 starts 2d after last RS game",
      r1_starts == {date(2027, 4, 14)}, str(r1_starts))
s0 = r1[0]
check("7 game dates, every other day",
      len(s0.game_dates) == 7 and
      all((s0.game_dates[i+1]-s0.game_dates[i]).days == 2 for i in range(6)))
venues = [s0.home_team_for_game(i).team_name for i in range(1, 8)]
check("2-2-1-1-1 venues",
      venues == ["BOS","BOS","BUF","BUF","BOS","BUF","BOS"], str(venues))
entry = next(e for e in po_entries
             if e["series_id"] == s0.series_id and e["series_game"] == 3)
check("scheduled entry venue matches",
      entry["home_team"].team_name == "BUF"
      and entry["away_team"].team_name == "BOS")

# ------------------------------------------------------- 4. completion/pruning
# Sweep the first series in 4; take another to 7 with team2 winning.
for _ in range(4):
    r1[0].add_game_result(True)
b._stamp_played_game(r1[0], 3, 2)
b._prune_series_schedule(r1[0])
check("sweep: end_date = game 4 date",
      r1[0].end_date == r1[0].game_dates[3], str(r1[0].end_date))
left = [e for e in league.schedule
        if isinstance(e, dict) and e.get("series_id") == r1[0].series_id]
check("sweep: unplayed games 5-7 pruned", len(left) == 4, str(len(left)))
check("played entry stamped (game 4)",
      left[3].get("played") is True and left[3].get("home_score") == 3,
      str({k: left[3].get(k) for k in ("played", "home_score")}))

for i, t1w in enumerate([False, True, False, True, False, True, False]):
    r1[1].add_game_result(t1w)  # FLA (team2) wins 4-3
b._prune_series_schedule(r1[1])
check("7-gamer: winner is team2", r1[1].winner.team_name == "FLA")
check("7-gamer: end_date = game 7 date",
      r1[1].end_date == r1[1].game_dates[6])
check("7-gamer: nothing pruned",
      len([e for e in league.schedule if isinstance(e, dict)
           and e.get("series_id") == r1[1].series_id]) == 7)

# ------------------------------------------------------- 5. advancement gate
ok = b.advance_to_next_round("wild_card")
check("gate refuses partial round", ok is False)
check("no R2 series built on partial", b.playoff_series["division_semifinals"] == [])
check("current_round unmoved", b.current_round == "wild_card")

# Finish the rest of R1 (team1 sweeps each, fastest possible ends).
for s in r1[2:]:
    for _ in range(4):
        s.add_game_result(True)
    b._prune_series_schedule(s)
last_end = max(s.end_date for s in r1)
ok = b.advance_to_next_round("wild_card")
check("full round advances", ok is True)
r2 = b.playoff_series["division_semifinals"]
check("4 R2 series", len(r2) == 4, str(len(r2)))
# Fixed bracket: winner(A)=BOS vs winner(B)=FLA; winner(C) vs winner(D).
r2e = [(s.team1.team_name, s.team2.team_name) for s in r2[:2]]
check("R2 East bracket integrity",
      r2e == [("BOS", "FLA"), ("NYR", "CAR")], str(r2e))
r2_starts = {s.start_date for s in r2}
check("R2 starts 2d after LAST R1 series ended",
      r2_starts == {last_end + timedelta(days=2)},
      f"starts={r2_starts} last_end={last_end}")
check("R2 published to schedule",
      sum(1 for e in league.schedule if isinstance(e, dict)
          and e.get("round_key") == "division_semifinals") == 28)

# ------------------------------------------------------- 6. full tournament
def _finish_round(bracket, rkey):
    for s in bracket.playoff_series[rkey]:
        while not s.is_complete:
            s.add_game_result(True)  # team1 always wins
        bracket._prune_series_schedule(s)
    return bracket.advance_to_next_round(rkey)

check("R2 -> R3", _finish_round(b, "division_semifinals") is True)
check("2 conference finals",
      len(b.playoff_series["division_finals"]) == 2)
check("R3 -> SCF", _finish_round(b, "division_finals") is True)
check("1 SCF series", len(b.playoff_series["stanley_cup_final"]) == 1)
check("SCF -> champion", _finish_round(b, "stanley_cup_final") is True)
check("champion crowned", b.stanley_cup_champion is not None,
      getattr(b.stanley_cup_champion, "team_name", None))
check("current_round complete", b.current_round == "complete")
# Every round started after the previous round's last game.
for rkey, prev in (("division_semifinals", "wild_card"),
                   ("division_finals", "division_semifinals"),
                   ("stanley_cup_final", "division_finals")):
    prev_end = max(s.end_date for s in b.playoff_series[prev])
    starts = {s.start_date for s in b.playoff_series[rkey]}
    check(f"{rkey} after {prev} end+2",
          starts == {prev_end + timedelta(days=2)},
          f"{starts} vs {prev_end}")
# No playoff games on the same day for one team (sanity on the calendar).
bad = []
for t in teams:
    seen = set()
    for e in league.schedule:
        if isinstance(e, dict) and e.get("playoff"):
            for side in ("home_team", "away_team"):
                if e[side] is t:
                    if e["date"] in seen:
                        bad.append((t.team_name, str(e["date"])))
                    seen.add(e["date"])
check("no team double-booked on a playoff day", not bad, str(bad[:2]))

# ------------------------------------------------------- 7. save/load dates
from save_load_system import GameSaveManager
mgr = GameSaveManager.__new__(GameSaveManager)
blob = mgr._serialize_playoff_bracket(league)
s0b = next(s for s in blob["series"] if s["series_id"] == r1[0].series_id)
check("serialized start_date", s0b["start_date"] == "2027-04-14",
      str(s0b["start_date"]))
check("serialized end_date", s0b["end_date"] == r1[0].end_date.isoformat())
check("serialized 7 potential game_dates", len(s0b["game_dates"]) == 7)

league2 = SimpleNamespace(teams=teams, standings=standings,
                          season_year=2026, rivalries=[], schedule=[],
                          playoff_bracket=None)
mgr._restore_playoff_bracket(league2, blob)
rb = league2.playoff_bracket
rs0 = next(s for sl in rb.playoff_series.values() for s in sl
           if s.series_id == r1[0].series_id)
check("restored start_date", rs0.start_date == date(2027, 4, 14))
check("restored end_date", rs0.end_date == r1[0].end_date)
check("restored game_dates", rs0.game_dates == r1[0].game_dates)
check("restored winner", rs0.winner.team_name == "BOS")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
