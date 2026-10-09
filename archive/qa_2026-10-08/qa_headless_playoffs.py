# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: headless playoff path + season continuity.

Verifies:
1. PlayoffBracket generates a real bracket headless (no GUI); the
   legacy 'conference_finals' key stays empty by design (division_finals
   holds the conference-final series).
2. Headless series resolution completes every round to a champion
   (mocked fast game sim; exercises loop/fallback/advance logic).
3. Season continuity: draft_year derives from league.season_year (game
   state), NOT current_date.year -- manual date manipulation around the
   playoff gap cannot skip/mis-year the draft.
4. _validate_season_continuity detects gaps, passes clean history,
   never raises on garbage.
"""
import os
import sys
from types import SimpleNamespace, MethodType
from datetime import date

os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/tmp/wt-headless")

# Silence all popups (headless).
import tkinter.messagebox as _mb
_mb.showinfo = _mb.showwarning = _mb.showerror = _mb.askyesno = lambda *a, **k: None
try:
    import popup_system as _ps
    _ps.messagebox.showinfo = _ps.messagebox.showwarning = \
        _ps.messagebox.showerror = _ps.messagebox.askyesno = lambda *a, **k: None
except Exception:
    pass

PASS, FAIL = [], []
def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra else ""))

# ---------------------------------------------------------------- bracket
from playoff_system import PlayoffBracket

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
    for tname, pts in rows:
        teams.append(SimpleNamespace(
            team_name=tname, league_name="National Hockey League",
            conference=DIV_CONF[div], division=div, roster=[],
            ahl_roster=[], prospects=[]))
        standings[tname] = {"Points": pts, "Wins": pts // 2,
                            "Losses": 30, "OTL": 5}

league = SimpleNamespace(
    teams=teams, standings=standings, season_year=2026,
    playoff_bracket=None, rivalries=[],
    lottery_held_years=[], draft_held_years=[],
    draft_conducted_years=[])

bracket = PlayoffBracket(league)
bracket.generate_playoff_bracket()
league.playoff_bracket = bracket

check("bracket generated", bool(getattr(bracket, "playoff_series", None)))
check("ROUND_ORDER has 4 rounds",
      PlayoffBracket.ROUND_ORDER == ['wild_card', 'division_semifinals',
                                    'division_finals', 'stanley_cup_final'])
check("legacy conference_finals key stays empty",
      (bracket.playoff_series or {}).get('conference_finals') == [])
_r1 = (bracket.playoff_series or {}).get('wild_card', [])
check("8 wild-card series", len(_r1) == 8, f"got {len(_r1)}")

# ------------------------------------------------- headless series resolve
_call_count = [0]
_orig_sim = PlayoffBracket.simulate_playoff_game
def _fast_sim(self, series):
    _call_count[0] += 1
    _team1_wins_game = (series.games_played % 2 == 0)
    series.add_game_result(_team1_wins_game, {"mock": True})
    return (3, 2) if _team1_wins_game else (2, 3)
PlayoffBracket.simulate_playoff_game = _fast_sim

try:
    for round_name in PlayoffBracket.ROUND_ORDER:
        bracket.current_round = round_name
        for series in (bracket.playoff_series.get(round_name) or []):
            _attempts = 0
            while not series.is_complete and _attempts < 14:
                _attempts += 1
                try:
                    bracket.simulate_playoff_game(series)
                except Exception as _e:
                    try:
                        _home_is_t1 = (series.home_team_for_game(
                            series.games_played + 1) is series.team1)
                        series.add_game_result(
                            _home_is_t1,
                            {"fallback": True, "reason": str(_e)[:120]})
                    except Exception:
                        break
        bracket.advance_to_next_round(round_name)
finally:
    PlayoffBracket.simulate_playoff_game = _orig_sim

check("series resolved via headless loop", _call_count[0] > 0,
      f"{_call_count[0]} games")
champ = getattr(bracket, "stanley_cup_champion", None)
check("champion decided", champ is not None,
      getattr(champ, "team_name", "?") if champ else "none")
check("no stall: every round advanced",
      getattr(bracket, "current_round", "") == "complete",
      f"current_round={getattr(bracket, 'current_round', '?')}")

# ------------------------------------------------- season continuity
import main as _main_mod
_HasMethod = hasattr(_main_mod.HockeyManagerGUI, "_validate_season_continuity")
check("continuity guard exists on HockeyManagerGUI", _HasMethod)

def _stub_app(season_year, hist_years, cur_date):
    app = SimpleNamespace()
    app.league = SimpleNamespace(season_year=season_year)
    hist = SimpleNamespace()
    hist.seasons = [{"year": y} for y in hist_years]
    app.league_history = hist
    app.current_date = cur_date
    app._news = []
    app.add_news = lambda m: app._news.append(m)
    app._validate_season_continuity = MethodType(
        _main_mod.HockeyManagerGUI._validate_season_continuity, app)
    return app

if _HasMethod:
    a1 = _stub_app(2026, [2024, 2025], date(2027, 1, 15))
    check("continuity: clean mid-season passes",
          a1._validate_season_continuity() is True)

    a2 = _stub_app(2026, [2024, 2025, 2026], date(2027, 6, 10))
    check("continuity: just-recorded passes",
          a2._validate_season_continuity() is True)

    a3 = _stub_app(2028, [2024, 2025], date(2029, 6, 10))
    check("continuity: skipped season detected",
          a3._validate_season_continuity() is False)
    check("continuity: break logged loudly",
          any("continuity break" in m for m in a3._news))

    a4 = _stub_app(2027, [2024, 2025, 2027], date(2028, 1, 15))
    check("continuity: internal history gap detected",
          a4._validate_season_continuity() is False)

    a5 = _stub_app(2026, [], date(2026, 10, 1))
    check("continuity: empty history passes",
          a5._validate_season_continuity() is True)

    a6 = SimpleNamespace()
    a6.league = None
    a6.league_history = None
    a6.current_date = None
    a6.add_news = lambda m: (_ for _ in ()).throw(RuntimeError("nope"))
    a6._validate_season_continuity = MethodType(
        _main_mod.HockeyManagerGUI._validate_season_continuity, a6)
    try:
        a6._validate_season_continuity()
        check("continuity: garbage never raises", True)
    except Exception as e:
        check("continuity: garbage never raises", False, str(e)[:60])

# 7. draft_year derives from game state, not the wall date.
_src = open("/tmp/wt-headless/main.py").read()
check("tentpoles: draft_year from league.season_year",
      'draft_year = int(getattr(league, "season_year", 0) or 0) + 1' in _src)
check("tentpoles: no current_date.year for draft_year",
      "draft_year = self.current_date.year" not in _src)
check("guard wired into _start_offseason",
      "_validate_season_continuity()" in _src)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
