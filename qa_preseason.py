# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: NHL preseason -- 96 exhibitions, zero regular-season footprint.

Part 1: schedule structure (seeds 2026/2027/2028/2031)
  - exactly 64 preseason entries, 4 per club (2026-27 CBA cap), Sep 22 - Oct 7 window
  - no club twice on one day, 3H/3A-ish band (2-4)
  - regular season untouched: 1344 games, 84 per club, no date overlap
Part 2: template cache round-trip preserves the preseason flag
Part 3: sim guards -- standings, player stats, career GP all untouched
  by preseason games (unbound method calls on stubs, no GUI boot)
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date
from collections import Counter, defaultdict

import game_classes as g

passed, failed = 0, 0
def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {detail}")

# ---------------------------------------------------------------- fakes
DIVS = {
    "Atlantic":  ["T1","T2","T3","T4","T5","T6","T7","T8"],
    "Metro":     ["T9","T10","T11","T12","T13","T14","T15","T16"],
    "Central":   ["T17","T18","T19","T20","T21","T22","T23","T24"],
    "Pacific":   ["T25","T26","T27","T28","T29","T30","T31","T32"],
}
CONF = {"Atlantic": "East", "Metro": "East", "Central": "West", "Pacific": "West"}

class FakeTeam:
    def __init__(self, name, div):
        self.team_name = name
        self.city = name
        self.division = div
        self.conference = CONF[div]
        self.league_name = "National Hockey League"
        self.roster = []

class Pos:
    def __init__(self, n): self.name = n

class FakePlayer:
    def __init__(self, pos, ovr):
        self.primary_position = Pos(pos)
        self._ovr = ovr
        self.is_injured = False
        self.stats = {"goals": 0, "assists": 0, "points": 0,
                      "games_played": 0}
        self.nhl_games_played = 0
    def overall_rating(self): return self._ovr

def make_league():
    # League() builds the real 32 NHL clubs itself (with
    # division/conference/league_name populated).
    lg = g.League("NHL")
    assert len(lg.teams) == 32, len(lg.teams)
    return lg

def entries(lg):
    pre = [e for e in lg.schedule
           if isinstance(e, dict) and e.get("preseason")]
    reg = [e for e in lg.schedule
           if isinstance(e, dict) and e.get("league") == "NHL"
           and not e.get("preseason")
           and e.get("home_team") != "NHL_EVENT"]
    return pre, reg

# ---------------------------------------------------------------- part 1
for seed in (2026, 2027, 2028, 2031):
    print(f"seed {seed}:")
    lg = make_league()
    lg.generate_schedule(season_year=seed, rotation_seed=seed)
    pre, reg = entries(lg)
    check("64 preseason entries", len(pre) == 64, f"got {len(pre)}")
    per = Counter()
    home_c = Counter()
    for e in pre:
        per[e["home_team"].team_name] += 1
        per[e["away_team"].team_name] += 1
        home_c[e["home_team"].team_name] += 1
    check("4 per club", all(v == 4 for v in per.values()) and len(per) == 32,
          f"{dict(per)}")
    check("home games 1-3 per club",
          all(1 <= v <= 3 for v in home_c.values()),
          f"{dict(home_c)}")
    lo, hi = date(seed, 9, 22), date(seed, 10, 7)
    check("dates within Sep 22 - Oct 7",
          all(lo <= e["date"] <= hi for e in pre))
    per_day = defaultdict(set)
    for e in pre:
        for t in (e["home_team"].team_name, e["away_team"].team_name):
            per_day[(e["date"], t)].add(1)
    check("no club twice in one day",
          all(len(v) == 1 for v in per_day.values()))
    maxday = Counter(e["date"] for e in pre)
    check("<= 8 games/day", max(maxday.values()) <= 8,
          f"max {max(maxday.values())}")
    check("1344 regular-season games", len(reg) == 1344, f"got {len(reg)}")
    regper = Counter()
    for e in reg:
        regper[e["home_team"].team_name] += 1
        regper[e["away_team"].team_name] += 1
    check("84 regular games per club",
          all(v == 84 for v in regper.values()) and len(regper) == 32)
    predates = {e["date"] for e in pre}
    regdates = {e["date"] for e in reg}
    check("no date overlap pre/regular", not (predates & regdates))
    regstart = min(regdates)
    check("regular season starts after preseason",
          regstart > max(predates), f"regular starts {regstart}")

# ---------------------------------------------------------------- part 2
print("template round-trip:")
lg = make_league()
lg.generate_schedule(season_year=2026, rotation_seed=2026)
pre0, reg0 = entries(lg)
tpl = lg._load_schedule_template(2026, 2026)
check("template cached", tpl is not None and len(tpl) > 0)
lg2 = make_league()
ok = lg2._apply_schedule_template(tpl)
check("template applied", ok)
pre1, reg1 = entries(lg2)
check("preseason count survives round-trip", len(pre1) == len(pre0) == 64,
      f"{len(pre0)} -> {len(pre1)}")
check("regular count survives round-trip", len(reg1) == len(reg0) == 1344,
      f"{len(reg0)} -> {len(reg1)}")
sig = lambda es: sorted((e["date"].isoformat(), e["home_team"].team_name,
                         e["away_team"].team_name, bool(e.get("preseason")))
                        for e in es)
check("identical slates", sig(pre0 + reg0) == sig(pre1 + reg1))

# ---------------------------------------------------------------- part 3
print("sim guards:")
import main as M

class Stub: pass
stub = Stub()
stub._strength_cache = {}
# Give the stub the full method surface (no __init__, no tkinter).
import inspect as _inspect
for _name, _fn in _inspect.getmembers(M.HockeyManagerGUI, _inspect.isfunction):
    try:
        setattr(stub, _name, _fn.__get__(stub))
    except Exception:
        pass
# injuries: deterministic off
M.roll_game_injury = lambda team: None

def mkclub(name):
    t = FakeTeam(name, "Atlantic")
    poss = (["CENTER"] * 4 + ["LEFT_WING"] * 4 + ["RIGHT_WING"] * 4
            + ["LEFT_DEFENSE"] * 3 + ["RIGHT_DEFENSE"] * 3 + ["GOALIE"] * 2)
    t.roster = [FakePlayer(p, 82) for p in poss]
    return t

home, away = mkclub("T1"), mkclub("T2")
stats_before = {id(p): dict(p.stats) for t in (home, away) for p in t.roster}
gp_before = {id(p): p.nhl_games_played for t in (home, away) for p in t.roster}
random.seed(7)
w, l, scores, ot = M.HockeyManagerGUI._simulate_game_lightweight.__get__(stub)(
    home, away, preseason=True)
stats_after = {id(p): dict(p.stats) for t in (home, away) for p in t.roster}
check("lightweight preseason: no stat writes", stats_before == stats_after)
check("lightweight preseason: sane score",
      isinstance(scores, tuple) and 0 <= scores[0] <= 15 and 0 <= scores[1] <= 15,
      f"{scores}")

M.HockeyManagerGUI._credit_nhl_games_played.__get__(stub)(home, away, preseason=True)
gp_after = {id(p): p.nhl_games_played for t in (home, away) for p in t.roster}
check("preseason: no career GP credited", gp_before == gp_after)
M.HockeyManagerGUI._credit_nhl_games_played.__get__(stub)(home, away, preseason=False)
gp_after2 = {id(p): p.nhl_games_played for t in (home, away) for p in t.roster}
check("regular: career GP credited",
      all(v == 1 for v in gp_after2.values()))

lg3 = make_league()
stub.league = lg3
M.HockeyManagerGUI._update_standings_fast.__get__(stub)(
    home, away, home, (3, 2), went_to_ot=False, preseason=True)
tot = sum(v["W"] + v["L"] + v["OTL"] + v["Points"]
          for v in lg3.standings.values())
check("preseason: standings untouched", tot == 0, f"total={tot}")
M.HockeyManagerGUI._update_standings_fast.__get__(stub)(
    home, away, home, (3, 2), went_to_ot=False, preseason=False)
check("regular: standings update",
      lg3.standings["T1"]["W"] == 1 and lg3.standings["T1"]["Points"] == 2
      and lg3.standings["T2"]["L"] == 1)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
