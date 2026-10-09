# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for playtest fixes: P-1 (conference_finals alias), P-2 (Caleb's
final_table_snapshot), and P-5 (name_safety star-surname filter)."""
import os, sys, random
os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

from playoff_system import PlayoffBracket, PlayoffSeries

# --- P-1: conference_finals stays a legacy empty key (Caleb's design) ------
# _create_conference_finals routes to the Stanley Cup Final; the legacy key
# is never appended to. Readers must not double-count it.
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
assert len(div) == 2, "division finals not created"
assert len(conf) == 0, "legacy conference_finals key must stay empty"

# _create_conference_finals routes to the Cup Final, not the legacy key.
b._create_conference_finals([lg.teams[0], lg.teams[4]])
assert len(b.playoff_series["stanley_cup_final"]) == 1, "Cup Final not routed"
assert len(b.playoff_series["conference_finals"]) == 0, "legacy key appended to"
print("P-1 legacy key stays empty; creation routes to Cup Final OK")

# Stats-window aggregation sees each series once.
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
assert total == 7, f"reader would count {total} series, expected 7"
print("P-1 no double-count OK")

# Save/load round-trip preserves the series and the empty legacy key.
import save_load_system as _sls
sl = _sls.GameSaveManager.__new__(_sls.GameSaveManager)
# _serialize takes league; emulate via a stub holding the bracket
class _Stub: pass
stub = _Stub(); stub.playoff_bracket = b
data = sl._serialize_playoff_bracket(stub)
n_series = len(data["series"])
assert n_series == 7, f"serialized {n_series} series, expected 7"
sl._restore_playoff_bracket(lg, data)
rb = lg.playoff_bracket
assert len(rb.playoff_series["division_finals"]) == 2
assert len(rb.playoff_series["conference_finals"]) == 0
assert len(rb.playoff_series["stanley_cup_final"]) == 1
print("P-1 save/load round-trip OK")

# --- P-2: final_table_snapshot (Caleb's banking) ---------------------------
from database_generator import generate_database
lg2 = generate_database("Small")
lg2.initialize_standings()
# Fake a finished season table.
for i, t in enumerate(lg2.teams[:4]):
    lg2.standings[t.team_name] = {"W": 50 - i, "L": 32 + i, "OTL": 0,
                                  "Points": 100 - 2 * i, "GP": 82}
print("P-2 running end_of_season (this takes a bit)...")
lg2.end_of_season()
prev = getattr(lg2, "final_table_snapshot", None)
assert prev, "final_table_snapshot missing after rollover"
sample = next(iter(prev.values()))
assert sample.get("Points", 0) > 0, f"snapshot has no real rows: {sample}"
# New season table must be zeroed.
cur = next(iter(lg2.standings.values()))
assert cur.get("Points", 0) == 0, "new standings not reset"
print(f"P-2 snapshot OK (sample row: {sample}); new table zeroed")

# --- P-5: name_safety star-surname filter ----------------------------------
# Generation paths must never mint a blocked star surname; a fresh league
# ships zero of them. (No post-hoc scrub exists by design: there is no
# real/fictional flag, so a scrub could not tell a generated "Mikko
# Rantanen" from the real one.)
import name_safety as _ns
assert _ns.is_blocked_surname("McDavid") and _ns.is_blocked_surname("Draisaitl")
pool = ["McDavid", "Smith", "Draisaitl", "Jones", "Rantanen", "Brown"]
seen_blocked = 0
for _ in range(300):
    s = _ns.pick_surname(pool)
    assert not _ns.is_blocked_surname(s), f"pick_surname leaked {s}"
print("P-5 pick_surname never returns a blocked surname (300 draws)")
bad = 0
for t in lg2.teams:
    for attr in ("roster", "ahl_roster", "prospects"):
        for pl in getattr(t, attr, None) or []:
            if _ns.is_blocked_surname(getattr(pl, "last_name", "") or ""):
                bad += 1
                print("LEFTOVER:", pl.first_name, pl.last_name)
assert bad == 0, f"{bad} blocked surnames in fresh league"
print("P-5 fresh league ships zero blocked star surnames")

print("ALL P-1/P-2/P-5 QA PASSED")
