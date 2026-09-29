"""QA: playoff seeding format choice — divisional vs conference.

Verifies on fake 32-team leagues through the REAL bracket code paths:
  1. make_config carries playoff_format (default divisional; garbage ->
     divisional); PLAYOFF_FORMATS documents both options.
  2. League.playoff_format defaults to divisional; _playoff_format()
     normalizes missing/garbage league values to divisional.
  3. Divisional qualification: DET (95 pts, ATL 6th) OUT despite
     outpointing PIT (88 pts, MET 3rd) who is IN; bracket order +
     round-1 pairings (DW1 vs WC2, 2v3, 2v3, DW2 vs WC1).
  4. Conference qualification: DET (95) IN as the 8-seed, PIT OUT;
     seed order best-first; round-1 pairings 1v8/2v7/3v6/4v5.
  5. Conference rounds 2-3 RESEED by conference seed (highest remaining
     hosts lowest), not the fixed bracket.
  6. Upset-watch hype tag fires in both formats for 1v8-type series.
  7. Save/load: _serialize_league writes playoff_format; _restore_league
     restores it; old saves (key missing) default to divisional.

No repo files modified. Series driven via add_game_result (the same
completion signal the sim produces).
"""
import sys
from types import SimpleNamespace
from datetime import date

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

from playoff_system import PlayoffBracket
from new_game_setup import make_config, PLAYOFF_FORMATS
from game_classes import League
from save_load_system import GameSaveManager

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra else ""))

# ------------------------------------------------------------- 1. config
check("PLAYOFF_FORMATS documents both options",
      set(PLAYOFF_FORMATS) == {"divisional", "conference"})
check("make_config default is divisional",
      make_config()["playoff_format"] == "divisional")
check("make_config passes conference through",
      make_config(playoff_format="conference")["playoff_format"] == "conference")
check("make_config rejects garbage",
      make_config(playoff_format="1v8-please")["playoff_format"] == "divisional")

# ------------------------------------------------------------- 2. league
check("League default is divisional",
      League(league_name="NHL").playoff_format == "divisional")
b0 = PlayoffBracket(SimpleNamespace(teams=[], standings={},
                                    rivalries=[], schedule=[]))
check("missing attr reads as divisional", b0._playoff_format() == "divisional")
b0.league.playoff_format = "bogus"
check("garbage normalizes to divisional",
      b0._playoff_format() == "divisional")
b0.league.playoff_format = "conference"
check("conference reads back", b0._playoff_format() == "conference")

# ------------------------------------------------------------- fake league
# Crafted so the two formats QUALIFY DIFFERENTLY: DET (95, ATL 6th) is 9th
# in the East on points but still misses in divisional (division rank
# beats points); in conference format DET takes the 8-seed and PIT (88,
# MET 3rd) drops out.
DIVS = {
    "Atlantic":     [("BOS",112),("TOR",108),("FLA",104),("TBL",100),
                     ("BUF",96),("DET",95),("MTL",80),("OTT",76)],
    "Metropolitan": [("CAR",110),("NYR",106),("PIT",88),("WSH",87),
                     ("NYI",84),("NJD",82),("PHI",80),("CBJ",78)],
    "Central":      [("COL",114),("DAL",109),("WPG",102),("MIN",99),
                     ("NSH",89),("STL",85),("UTA",81),("CHI",77)],
    "Pacific":      [("EDM",111),("VGK",107),("LAK",98),("VAN",95),
                     ("CGY",91),("ANA",87),("SEA",83),("SJS",79)],
}
DIV_CONF = {"Atlantic": "Eastern", "Metropolitan": "Eastern",
            "Central": "Western", "Pacific": "Western"}

def make_fake_league(fmt):
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
    lg = SimpleNamespace(teams=teams, standings=standings,
                         season_year=2026, rivalries=[], schedule=sched,
                         playoff_bracket=None, playoff_format=fmt)
    return lg

def series_pair(s):
    return frozenset((s.team1.team_name, s.team2.team_name))

def sweep_for(series, winner_name):
    t1 = series.team1.team_name == winner_name
    for _ in range(4):
        series.add_game_result(t1)

# ------------------------------------------------------------- 3. divisional
lg = make_fake_league("divisional")
b = PlayoffBracket(lg)
lg.playoff_bracket = b
b.generate_playoff_bracket()
east = [t.team_name for t in b.eastern_teams]
check("divisional: 8 East", len(east) == 8, str(east))
check("divisional: DET (95) misses", "DET" not in east)
check("divisional: PIT (88, MET 3rd) qualifies", "PIT" in east)
check("divisional: bracket order",
      east == ["BOS","CAR","TOR","FLA","NYR","PIT","TBL","BUF"], str(east))
r1 = b.playoff_series["wild_card"][:4]
pairs = {series_pair(s) for s in r1}
check("divisional R1: DW1vWC2 / 2v3 / 2v3 / DW2vWC1",
      pairs == {frozenset(("BOS","BUF")), frozenset(("TOR","FLA")),
                frozenset(("NYR","PIT")), frozenset(("CAR","TBL"))},
      str(sorted(tuple(sorted(p)) for p in pairs)))
s0 = next(s for s in r1 if series_pair(s) == frozenset(("BOS","BUF")))
check("divisional: BOS/BUF tagged Upset watch",
      "Upset watch" in (s0.hype_tags or []), str(s0.hype_tags))

# ------------------------------------------------------------- 4. conference
lg2 = make_fake_league("conference")
b2 = PlayoffBracket(lg2)
lg2.playoff_bracket = b2
b2.generate_playoff_bracket()
east2 = [t.team_name for t in b2.eastern_teams]
check("conference: 8 East", len(east2) == 8, str(east2))
check("conference: DET (95) takes the 8-seed", "DET" in east2)
check("conference: PIT (88) drops out", "PIT" not in east2)
check("conference: seed order best-first",
      east2 == ["BOS","CAR","TOR","NYR","FLA","TBL","BUF","DET"], str(east2))
r1c = b2.playoff_series["wild_card"][:4]
pairsc = {series_pair(s) for s in r1c}
check("conference R1: 1v8/2v7/3v6/4v5",
      pairsc == {frozenset(("BOS","DET")), frozenset(("CAR","BUF")),
                 frozenset(("TOR","TBL")), frozenset(("NYR","FLA"))},
      str(sorted(tuple(sorted(p)) for p in pairsc)))
s0c = next(s for s in r1c if series_pair(s) == frozenset(("BOS","DET")))
check("conference: BOS/DET tagged Upset watch",
      "Upset watch" in (s0c.hype_tags or []), str(s0c.hype_tags))
check("conference: 56 R1 games published to schedule",
      sum(1 for e in lg2.schedule if isinstance(e, dict)
          and e.get("round_key") == "wild_card") == 56)

# ------------------------------------------------------------- 5. reseed
# Rig R1: 1-seed BOS, 7-seed BUF (upset), 6-seed TBL (upset), 4-seed NYR.
for s in r1c:
    p = series_pair(s)
    if p == frozenset(("BOS","DET")): w = "BOS"
    elif p == frozenset(("CAR","BUF")): w = "BUF"
    elif p == frozenset(("TOR","TBL")): w = "TBL"
    elif p == frozenset(("NYR","FLA")): w = "NYR"
    else: w = s.team1.team_name
    sweep_for(s, w)
    b2._prune_series_schedule(s)
# West: team1 sweeps, only need a complete round.
for s in b2.playoff_series["wild_card"][4:]:
    for _ in range(4):
        s.add_game_result(True)
    b2._prune_series_schedule(s)
check("conference R1 completes", all(s.is_complete for s in
      b2.playoff_series["wild_card"]))
ok = b2.advance_to_next_round("wild_card")
check("R1 advances", ok is True)
r2e = b2.playoff_series["division_semifinals"][:2]
r2pairs = {series_pair(s) for s in r2e}
check("conference R2 reseeded (1v7, 4v6)",
      r2pairs == {frozenset(("BOS","BUF")), frozenset(("NYR","TBL"))},
      str(sorted(tuple(sorted(p)) for p in r2pairs)))
for s in r2e:  # higher seed hosts: higher seed is team1
    hi = min(s.team1.standings_position, s.team2.standings_position)
    check(f"R2 {s.team1.team_name}/{s.team2.team_name}: higher seed is team1",
          s.team1.standings_position == hi,
          f"seeds {s.team1.standings_position}v{s.team2.standings_position}")
# Rig R2: BOS over BUF, NYR over TBL -> R3 must be 1v4 = BOS/NYR.
for s in r2e:
    sweep_for(s, "BOS" if "BOS" in (s.team1.team_name, s.team2.team_name) else "NYR")
    b2._prune_series_schedule(s)
for s in b2.playoff_series["division_semifinals"][2:]:
    while not s.is_complete:
        s.add_game_result(True)
    b2._prune_series_schedule(s)
check("R2 -> R3", b2.advance_to_next_round("division_semifinals") is True)
r3e = b2.playoff_series["division_finals"][:1]
check("conference R3 is 1v4 BOS/NYR",
      series_pair(r3e[0]) == frozenset(("BOS","NYR")),
      f"{r3e[0].team1.team_name}v{r3e[0].team2.team_name}")
check("R3: higher seed (BOS) is team1",
      r3e[0].team1.team_name == "BOS")

# ------------------------------------------------------------- 7. save/load
mgr = GameSaveManager.__new__(GameSaveManager)
real = League(league_name="National Hockey League", season_year=2026)
real.playoff_format = "conference"
mgr.game_manager = SimpleNamespace(league=real)
blob = mgr._serialize_league()
check("serialized playoff_format", blob.get("playoff_format") == "conference",
      str(blob.get("playoff_format")))
real2 = League(league_name="National Hockey League", season_year=2026)
real2.playoff_format = "divisional"  # prove restore overwrites
mgr2 = GameSaveManager.__new__(GameSaveManager)
mgr2.game_manager = SimpleNamespace(league=real2)
mgr2._restore_league(blob)
check("restored playoff_format", real2.playoff_format == "conference")
# Old save (key missing) -> divisional default.
real3 = League(league_name="National Hockey League", season_year=2026)
blob_old = dict(blob); blob_old.pop("playoff_format", None)
mgr3 = GameSaveManager.__new__(GameSaveManager)
mgr3.game_manager = SimpleNamespace(league=real3)
mgr3._restore_league(blob_old)
check("old save defaults to divisional",
      real3.playoff_format == "divisional")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
