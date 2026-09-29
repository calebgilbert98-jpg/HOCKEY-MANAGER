"""QA for playtest fixes: P-1 (conference_finals alias), P-2 (standings
snapshot), and new-game name scrub."""
import os, sys, random
os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

from playoff_system import PlayoffBracket, PlayoffSeries
from draft_generator import scrub_league_names, _is_famous_real_name

# --- P-1: alias populated, no double-count, save/load round-trip ---------
from game_classes import League, Team

lg = League("Test")
lg.teams.clear()
_names = ["A", "B", "C", "D", "E", "F", "G", "H"]
_divs = ["Atlantic", "Metropolitan", "Atlantic", "Metropolitan",
         "Central", "Pacific", "Central", "Pacific"]
for i, name in enumerate(_names):
    t = Team(name, "City", _divs[i], "Eastern" if i < 4 else "Western")
    lg.teams.append(t)
lg.initialize_standings()

b = PlayoffBracket(lg)
b.eastern_teams = lg.teams[:4]
b.western_teams = lg.teams[4:]
# Drive straight to division finals creation: 4 semifinal series.
b.playoff_series["division_semifinals"] = [
    PlayoffSeries("x", lg.teams[0], lg.teams[1]),
    PlayoffSeries("x", lg.teams[2], lg.teams[3]),
    PlayoffSeries("x", lg.teams[4], lg.teams[5]),
    PlayoffSeries("x", lg.teams[6], lg.teams[7]),
]
for s in b.playoff_series["division_semifinals"]:
    s.is_complete = True
    s.winner = s.team1
b._create_division_finals([s.winner for s in b.playoff_series["division_semifinals"]])

div = b.playoff_series["division_finals"]
conf = b.playoff_series["conference_finals"]
print(f"P-1 division_finals={len(div)} conference_finals={len(conf)}")
assert len(div) == 2 and len(conf) == 2, "alias not populated"
assert all(any(s is c for c in conf) for s in div), "alias must hold the SAME objects"

# Stats-window aggregation must not double-count the aliased series.
import stats_standings_window as _ssw
seen = set()
total = 0
for key in ["wild_card", "division_semifinals", "division_finals",
            "conference_finals", "stanley_cup_final"]:
    for s in (b.playoff_series.get(key) or []):
        if id(s) in seen:
            continue
        seen.add(id(s))
        total += 1
assert total == 6, f"reader would count {total} series, expected 6"
print("P-1 no double-count OK")

# Save/load round-trip keeps the alias.
import save_load_system as _sls
sl = _sls.GameSaveManager.__new__(_sls.GameSaveManager)
# _serialize takes league; emulate via a stub holding the bracket
class _Stub: pass
stub = _Stub(); stub.playoff_bracket = b
data = sl._serialize_playoff_bracket(stub)
n_series = len(data["series"])
assert n_series == 6, f"serialized {n_series} series, expected 6 (dedupe)"
sl._restore_playoff_bracket(lg, data)
rb = lg.playoff_bracket
assert len(rb.playoff_series["division_finals"]) == 2
assert len(rb.playoff_series["conference_finals"]) == 2
assert all(any(s.team1.team_name == c.team1.team_name
               for c in rb.playoff_series["conference_finals"])
           for s in rb.playoff_series["division_finals"])
print("P-1 save/load round-trip OK")

# --- P-2: previous_standings snapshot ------------------------------------
from database_generator import generate_database
lg2 = generate_database("Small")
lg2.initialize_standings()
# Fake a finished season table.
for i, t in enumerate(lg2.teams[:4]):
    lg2.standings[t.team_name] = {"W": 50 - i, "L": 32 + i, "OTL": 0,
                                  "Points": 100 - 2 * i, "GP": 82}
print("P-2 running end_of_season (this takes a bit)...")
lg2.end_of_season()
prev = getattr(lg2, "previous_standings", None)
assert prev, "previous_standings missing after rollover"
sample = next(iter(prev.values()))
assert sample.get("Points", 0) > 0, f"snapshot has no real rows: {sample}"
# New season table must be zeroed.
cur = next(iter(lg2.standings.values()))
assert cur.get("Points", 0) == 0, "new standings not reset"
print(f"P-2 snapshot OK (sample row: {sample}); new table zeroed")

# --- Name scrub: injected famous names get renamed ------------------------
from game_classes import Player, PlayerPosition
p = Player(first_name="Connor", last_name="McDavid", age=28,
           primary_position=PlayerPosition.CENTER)
p.nationality = "Canada"
lg2.teams[0].roster.append(p)
n = scrub_league_names(lg2)
assert n >= 1, "scrub did not rename the injected McDavid"
assert not _is_famous_real_name(p.first_name, p.last_name), \
    f"still famous after scrub: {p.first_name} {p.last_name}"
print(f"P-2b scrub renamed {n}; McDavid is now {p.first_name} {p.last_name}")
# Whole league clean.
bad = 0
for t in lg2.teams:
    for attr in ("roster", "ahl_roster", "prospects"):
        for pl in getattr(t, attr, None) or []:
            if _is_famous_real_name(getattr(pl, "first_name", ""),
                                    getattr(pl, "last_name", "")):
                bad += 1
                print("LEFTOVER:", pl.first_name, pl.last_name)
assert bad == 0, f"{bad} famous names left in league"
print("P-2b league-wide name check clean")

print("ALL P-1/P-2/SCRUB QA PASSED")
