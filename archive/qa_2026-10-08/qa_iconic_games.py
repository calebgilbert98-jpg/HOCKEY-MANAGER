# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: iconic games -- detection, recording, starring, pruning, save/load.

The nights the franchise remembers (5-goal games, 7-point nights,
45-save shutouts, brawls, Game 7s, rivalry routs) must be detected once
per finished game, stored on both clubs (capped, plain dicts), logged to
the stars' career_moments, shown with a star toggle, and pruned at
season rollover unless starred.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from types import SimpleNamespace

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")


from game_classes import League, Team

_pos = SimpleNamespace(name="CENTER")
_gpos = SimpleNamespace(name="GOALIE")


def _mkplayer(pid, name, goalie=False):
    return SimpleNamespace(id=pid, full_name=name,
                           primary_position=_gpos if goalie else _pos,
                           career_moments=[])


def _mkteam(name):
    t = Team(name, "City", "Atlantic", "Eastern")
    return t


def _mksim(home, away, hlines, alines):
    """Fake sim: stats[team_name][pid] = {goals, assists, saves}."""
    sim = SimpleNamespace(
        stats={home.team_name: {str(pid): dict(l)
                                for pid, l in hlines.items()},
               away.team_name: {str(pid): dict(l)
                                for pid, l in alines.items()}},
        pending_headlines=[])
    return sim


from iconic_games import (detect_iconic, record_iconic_game, toggle_star,
                          prune_iconic_games, detect_and_record)

# --- Detection ---
home, away = _mkteam("Alpha"), _mkteam("Beta")
sniper = _mkplayer(1, "Snipe McGee")
playmaker = _mkplayer(2, "Dish Daniels")
wall = _mkplayer(30, "Brick Wallski", goalie=True)
home.roster = [sniper, playmaker, wall]
away.roster = [_mkplayer(3, "Rival Ron")]

sim = _mksim(home, away, {1: {"goals": 5, "assists": 1, "saves": 0}},
             {3: {"goals": 1, "assists": 0, "saves": 0}})
e = detect_iconic(home, away, 6, 2, sim, game_date="2028-03-01",
                  season_year=2028)
check("five-goal game detected",
      e is not None and e["kind"] == "five_goal_game"
      and "FIVE" in e["headline"] and e["winner"] == "Alpha"
      and e["season"] == 2028, str(e["kind"] if e else None))

sim = _mksim(home, away, {2: {"goals": 2, "assists": 5, "saves": 0}}, {})
e = detect_iconic(home, away, 7, 3, sim, game_date="2028-03-02",
                  season_year=2028)
check("seven-point night detected",
      e is not None and e["kind"] == "seven_point_night", str(e["kind"] if e else None))

sim = _mksim(home, away, {30: {"goals": 0, "assists": 0, "saves": 47}}, {})
e = detect_iconic(home, away, 2, 0, sim, game_date="2028-03-03",
                  season_year=2028)
check("45-save shutout detected",
      e is not None and e["kind"] == "epic_shutout", str(e["kind"] if e else None))

sim = _mksim(home, away, {30: {"goals": 0, "assists": 0, "saves": 58}}, {})
e = detect_iconic(home, away, 3, 4, sim, game_date="2028-03-04",
                  season_year=2028)
check("55-save barrage detected in a loss",
      e is not None and e["kind"] == "shot_barrage", str(e["kind"] if e else None))

sim = _mksim(home, away, {1: {"goals": 1, "assists": 0, "saves": 0}}, {})
e = detect_iconic(home, away, 4, 3, sim, brawl=True,
                  game_date="2028-03-05", season_year=2028)
check("brawl game detected",
      e is not None and e["kind"] == "brawl_game", str(e["kind"] if e else None))

sim = _mksim(home, away, {1: {"goals": 2, "assists": 1, "saves": 0}}, {})
e = detect_iconic(home, away, 3, 2, sim, is_playoff=True, series_game=7,
                  game_date="2028-05-01", season_year=2028)
check("game 7 win detected",
      e is not None and e["kind"] == "game7_win" and e["playoff"],
      str(e["kind"] if e else None))
e = detect_iconic(home, away, 3, 2, sim, is_playoff=True, series_game=7,
                  went_ot=True, game_date="2028-05-01", season_year=2028)
check("game 7 OT win outranks plain game 7",
      e is not None and e["kind"] == "game7_ot_win",
      str(e["kind"] if e else None))

riv = [{"kind": "team_team", "a_name": "Alpha", "b_name": "Beta"}]
sim = _mksim(home, away, {1: {"goals": 2, "assists": 2, "saves": 0}}, {})
e = detect_iconic(home, away, 8, 1, sim, rivalries=riv,
                  game_date="2028-03-06", season_year=2028)
check("rivalry rout detected",
      e is not None and e["kind"] == "rivalry_rout",
      str(e["kind"] if e else None))
# Same blowout, no rivalry: not iconic.
e = detect_iconic(home, away, 8, 1, sim, rivalries=[],
                  game_date="2028-03-06", season_year=2028)
check("non-rivalry blowout is not iconic", e is None,
      str(e["kind"] if e else None))

sim = _mksim(home, away, {1: {"goals": 1, "assists": 1, "saves": 0}},
             {3: {"goals": 1, "assists": 0, "saves": 0}})
e = detect_iconic(home, away, 3, 2, sim, game_date="2028-03-07",
                  season_year=2028)
check("ordinary game is not iconic", e is None,
      str(e["kind"] if e else None))

# Priority: a 5-goal game in a brawl leads with the 5-goal game.
sim = _mksim(home, away, {1: {"goals": 5, "assists": 0, "saves": 0}}, {})
e = detect_iconic(home, away, 6, 4, sim, brawl=True,
                  game_date="2028-03-08", season_year=2028)
check("rarest trigger leads",
      e is not None and e["kind"] == "five_goal_game"
      and "brawl_game" in e["beats"], str(e["kind"] if e else None))

# --- Recording: both clubs, dedupe, cap ---
home2, away2 = _mkteam("Gamma"), _mkteam("Delta")
# Give the fake players to the new teams before detection (the player
# index resolves stat lines through the rosters).
gp = _mkplayer(1, "Snipe McGee")
home2.roster = [gp]
e = detect_iconic(home2, away2, 6, 2,
                  _mksim(home2, away2,
                         {1: {"goals": 5, "assists": 0, "saves": 0}}, {}),
                  game_date="2028-03-09", season_year=2028)
check("detection works for record test", e is not None and e["kind"] == "five_goal_game")
from iconic_games import detect_and_record as _dar
# detect_and_record also logs the stars' career moments.
n = 0
e2 = _dar(home2, away2, 6, 2,
          _mksim(home2, away2, {1: {"goals": 5, "assists": 0, "saves": 0}},
                 {}),
          game_date="2028-03-09", season_year=2028)
check("detect_and_record returns the entry",
      e2 is not None and e2["kind"] == "five_goal_game")
check("recorded on both clubs",
      len(home2.iconic_games) == 1 and len(away2.iconic_games) == 1,
      str((len(home2.iconic_games), len(away2.iconic_games))))
n = record_iconic_game(home2, away2, e)
n = record_iconic_game(home2, away2, e)
check("double-record dedupes",
      len(home2.iconic_games) == 1, str(len(home2.iconic_games)))

# Cap: unstarred pruned first, starred survive.
for i in range(35):
    record_iconic_game(home2, away2,
                       dict(e, id=f"2028|x{i}|Gamma|Delta|brawl_game",
                            kind="brawl_game",
                            headline=f"Brawl {i}",
                            date=f"2028-01-{(i % 28) + 1:02d}"))
home2.iconic_games[0]["starred"] = True
record_iconic_game(home2, away2,
                   dict(e, id="2028|final|Gamma|Delta|brawl_game",
                        kind="brawl_game", headline="Final"))
check("cap holds at 30",
      len(home2.iconic_games) == 30, str(len(home2.iconic_games)))
check("starred entry survives the cap",
      any(x.get("starred") for x in home2.iconic_games))

# --- Player moments ---
check("star gets an iconic_game moment",
      any(isinstance(m, dict) and m.get("kind") == "iconic_game"
          for m in gp.career_moments),
      str(gp.career_moments))

# --- Star toggle --- (index 0 is currently starred from the cap test)
eid = home2.iconic_games[0]["id"]
st = toggle_star(home2, eid)
check("toggle unstars a starred entry", st is False
      and home2.iconic_games[0]["starred"] is False, str(st))
st = toggle_star(home2, eid)
check("toggle re-stars", st is True, str(st))
check("toggle on missing id returns None",
      toggle_star(home2, "nope") is None)

# --- Prune at rollover ---
lg = League("NHL")
lg.season_year = 2029  # rollover already incremented
t = _mkteam("Eps")
t.iconic_games = [
    {"id": "a", "season": 2028, "starred": False, "date": "2028-03-01"},
    {"id": "b", "season": 2028, "starred": True, "date": "2028-03-02"},
    {"id": "c", "season": 2029, "starred": False, "date": "2029-10-01"},
]
lg.teams = [t]
pruned = prune_iconic_games(lg)
check("unstarred prior-season entries pruned",
      pruned == 1 and {x["id"] for x in t.iconic_games} == {"b", "c"},
      str([x["id"] for x in t.iconic_games]))

# --- Save/load round-trip ---
from save_load_system import GameSaveManager
lg2 = League("NHL")
lg2.season_year = 2028
t2 = _mkteam("Zeta")
t2.iconic_games = [
    {"id": "z1", "season": 2028, "starred": True, "kind": "five_goal_game",
     "headline": "Snipe scores FIVE", "date": "2028-03-01", "score": "6-2",
     "winner": "Zeta", "stars": [{"name": "Snipe McGee"}]},
]
lg2.teams = [t2]
gm = SimpleNamespace(league=lg2, league_history=None,
                     narrative_ledger=None)
tmp = tempfile.mkdtemp()
path = __import__("os").path.join(tmp, "iconic_test.save")
check("save succeeds", GameSaveManager(gm).save_game(path), path)
gm3 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
check("load succeeds", GameSaveManager(gm3).load_game(path), path)
zt = (gm3.league.teams or [None])[0]
zg = getattr(zt, "iconic_games", None) or []
check("iconic games survive save/load with starred flags",
      len(zg) == 1 and zg[0]["starred"] is True
      and zg[0]["headline"] == "Snipe scores FIVE", str(zg))
# Old save without the key -> empty list, no crash.
gm4 = SimpleNamespace(league=lg2, league_history=None,
                      narrative_ledger=None)
data = GameSaveManager(gm4)._serialize_league()
data["teams"][0].pop("iconic_games", None)
from game_classes import League as _L
gm5 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
gm5.league = _L("NHL")
gm5.league.teams = []
try:
    GameSaveManager(gm5)._restore_league(data)
    zt5 = (gm5.league.teams or [None])[0]
    check("old save: iconic_games defaults to empty",
          getattr(zt5, "iconic_games", None) == [])
except Exception as ex:  # noqa: BLE001
    check("old save restores without iconic_games", False, str(ex))

# --- process_postgame integration ---
import narrative_incidents as ni
h3, a3 = _mkteam("Eta"), _mkteam("Theta")
sp = _mkplayer(9, "Hatty Harold")
h3.roster = [sp]
sim3 = _mksim(h3, a3, {9: {"goals": 5, "assists": 0, "saves": 0}}, {})
res = ni.process_postgame(sim3, h3, a3, 6, 1, game_date="2028-03-10",
                          season_year=2028)
check("process_postgame flags iconic",
      res.get("iconic") is True, str(res.get("iconic")))
check("process_postgame records on the club",
      len(getattr(h3, "iconic_games", [])) == 1,
      str(len(getattr(h3, "iconic_games", []))))
check("process_postgame logs the player's moment",
      any(isinstance(m, dict) and m.get("kind") == "iconic_game"
          for m in sp.career_moments))

# Live-sim brawl path: the engine reports via pending_headlines, not the
# rolled brawl flag.
h4, a4 = _mkteam("Iota"), _mkteam("Kappa")
h4.roster = [_mkplayer(11, "Tough Tony")]
sim4 = _mksim(h4, a4, {11: {"goals": 0, "assists": 1, "saves": 0}}, {})
sim4.pending_headlines = [{"kind": "line_brawl",
                           "pairs": [("Tough Tony", "Rival Ron")]}]
e4 = detect_and_record(h4, a4, 4, 3, sim4, brawl=False,
                       game_date="2028-03-11", season_year=2028)
check("live-sim brawl detected via pending_headlines",
      e4 is not None and e4["kind"] == "brawl_game",
      str(e4["kind"] if e4 else None))

print(f"\n{'='*60}\nQA iconic_games: {PASS} passed, {FAIL} failed")
for f in FAILURES:
    print(f"  FAIL: {f}")
sys.exit(1 if FAIL else 0)
