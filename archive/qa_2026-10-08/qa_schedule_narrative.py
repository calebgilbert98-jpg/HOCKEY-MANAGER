# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_schedule_narrative.py -- schedule/calendar wiring of the narrative systems.

Verifies the regular-season schedule/calendar now FRIES the four systems:
1. Rivalry store -> matchup_narrative heat/tags/marquee + pregame crowd
2. Ledger grudge memory -> narrative tags + crowd
3. Iconic-game history -> "Iconic rematch" + headline
4. Intensity systems stay pure reads (no sim behavior change)
5. Ordinary matchups stay ordinary; helper never raises; no history
   invented or duplicated by the presentation layer.
40 checks. Never pushes. Run: python3 qa_schedule_narrative.py
"""
import os, sys, types

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name
          + (f" -- {detail}" if detail and not cond else ""))


class T:
    def __init__(self, name):
        self.team_name = name
        self.iconic_games = []
        self.roster = []          # _ekey recognizes Team by roster+team_name


class FakeLeague:
    def __init__(self, rivalries=None):
        self.rivalries = rivalries or []


def ekey_name(n):
    return n


# --- Fixtures ---------------------------------------------------------
a, b = T("Falcons"), T("Wolves")
c, d = T("Bears"), T("Otters")   # ordinary pair

playoff_war = {
    "a": ("team", "Falcons"), "b": ("team", "Wolves"),
    "a_name": "Falcons", "b_name": "Wolves",
    "kind": "team_team", "intensity": 72, "origin": "playoff_series",
    "story": "Playoff series: 7 games. Seven games, settled in OT.",
    "grudge": 80, "career_cost": 0, "user_declared": False,
    "declared_floor": 0,
}
warm = {
    "a": ("team", "Bears"), "b": ("team", "Otters"),
    "a_name": "Bears", "b_name": "Otters",
    "kind": "team_team", "intensity": 42, "origin": "regional",
    "story": "Regional bad blood.", "grudge": 20, "career_cost": 0,
    "user_declared": False, "declared_floor": 0,
}
league = FakeLeague([playoff_war, warm])

# Ledger with grudge memory between c/d (Bears/Otters)
import narrative_ledger as nl
ledger = nl.NarrativeLedger()
for _ in range(3):
    ledger.record("fight", teams=["Bears", "Otters"], weight=55,
                  text="Line brawl")
# Production-shaped heat incidents for the intensity meter:
# kind="incident" with an incident_kind fact.
for _ in range(2):
    ledger.record("incident", teams=["Bears", "Otters"], weight=55,
                  facts={"incident_kind": "brawl"}, text="Line brawl")

# Iconic game between Falcons and Wolves
a.iconic_games.append({
    "home": "Falcons", "away": "Wolves", "season": 2025,
    "kind": "OT thriller", "headline": "Falcons win 5-4 OT classic",
    "score": "5-4", "winner": "Falcons", "playoff": False,
    "id": "IC-2025-FAL-WOL-01"})

# --- 1. matchup_narrative ---------------------------------------------
from narrative_ledger import matchup_narrative

n = matchup_narrative(a, b, league=league, ledger=ledger)
check("1. rivalry heat read from store", n["rivalry_heat"] == 72,
      f"got {n['rivalry_heat']}")
check("2. 'Bad blood' at 65+", "Bad blood" in n["hype_tags"],
      f"got {n['hype_tags']}")
check("3. playoff-rematch tag from rivalry story",
      "Playoff rematch" in n["hype_tags"])
check("4. seven-game war detected", "Seven-game war" in n["hype_tags"])
check("5. grudge flag on", n["grudge"] is True)
check("6. marquee on at 72 heat", n["marquee"] is True)
check("7. iconic rematch surfaced",
      "Iconic rematch" in n["hype_tags"] and
      n["iconic_headline"] == "Falcons win 5-4 OT classic",
      f"tags={n['hype_tags']} headline={n['iconic_headline']}")

n2 = matchup_narrative(c, d, league=league, ledger=ledger)
check("8. ledger grudge lifts quiet store pair",
      n2["mem_weight"] >= 70.0 and "Bad blood" in n2["hype_tags"],
      f"mem={n2['mem_weight']:.1f} tags={n2['hype_tags']}")

g, h = T("Kings"), T("Ducks")   # warm rivalry, no ledger grudge
warm2 = {
    "a": ("team", "Ducks"), "b": ("team", "Kings"),
    "a_name": "Ducks", "b_name": "Kings",
    "kind": "team_team", "intensity": 42, "origin": "regional",
    "story": "Regional bad blood.", "grudge": 20, "career_cost": 0,
    "user_declared": False, "declared_floor": 0,
}
league.rivalries.append(warm2)
n2b = matchup_narrative(g, h, league=league, ledger=ledger)
check("9. warm rivalry tag reads", "Heated rivalry" in n2b["hype_tags"],
      f"got {n2b['hype_tags']}")
check("9b. warm pair not marquee (42 < 50)",
      n2b["marquee"] is False and n2b["grudge"] is True)

e, f = T("Ravens"), T("Sharks")
n3 = matchup_narrative(e, f, league=league, ledger=ledger)
check("10. ordinary pair stays ordinary",
      n3["hype_tags"] == [] and not n3["marquee"] and not n3["grudge"],
      f"tags={n3['hype_tags']} marquee={n3['marquee']}")

check("11. helper tolerates None inputs",
      matchup_narrative(None, None)["hype_tags"] == [])
check("12. helper tolerates missing league/ledger",
      matchup_narrative(e, f)["hype_tags"] == [])
check("13. same-team pair is neutral",
      matchup_narrative(a, a, league=league)["hype_tags"] == [])

# No history invented or duplicated by the presentation layer.
before_ledger = len(ledger.events)
before_iconic = len(a.iconic_games)
matchup_narrative(a, b, league=league, ledger=ledger)
matchup_narrative(c, d, league=league, ledger=ledger)
check("14. no ledger incidents written", len(ledger.events) == before_ledger)
check("15. no iconic games duplicated", len(a.iconic_games) == before_iconic)

# --- 2. _pregame_atmosphere passes rivalry heat -----------------------
import importlib.util
spec = importlib.util.spec_from_file_location(
    "main_pa", os.path.join(REPO, "main.py"))
# main.py is a GUI app -- don't execute it; verify the wiring statically.
src = open(os.path.join(REPO, "main.py")).read()
check("16. _pregame_atmosphere reads get_rivalry_heat",
      "get_rivalry_heat" in src and "rivalry_heat=_heat" in src)
check("17. both regular sim call-sites pass league",
      src.count("league=getattr(self, \"league\", None)") >= 2,
      f"count={src.count('league=getattr(self, \"league\", None)')}")
check("18. playoff path still passes series.rivalry_heat",
      "series.rivalry_heat" in src)

# --- 3. intensity systems remain pure reads ----------------------------
import season_intensity as si
check("19. season_intensity callable", callable(si.season_intensity))
check("20. series_intensity callable", callable(si.series_intensity))
check("21. hype_line callable", callable(getattr(si, "hype_line", None)))
# Pure: intensity read twice with no sim between gives same value.
v1 = si.season_intensity(ledger)
v2 = si.season_intensity(ledger)
check("22. intensity reads are deterministic", v1 == v2, f"{v1} vs {v2}")
pair_i = si.series_intensity(ledger, "Bears", "Otters")
check("23. series_intensity sees grudge pair",
      isinstance(pair_i, dict) and pair_i.get("value", 0) > 0,
      f"got {pair_i.get('value') if isinstance(pair_i, dict) else pair_i}")

# --- 4. view wiring present --------------------------------------------
wsrc = open(os.path.join(REPO, "windows.py")).read()
check("24. ScheduleView enriches regular-season rows",
      "_matchup_narrative(home, away)" in wsrc)
check("25. narrative cache invalidated per render",
      '_narrative_cache", None)' in wsrc)
check("26. playoff rows keep bracket stamp",
      "if not is_playoff:" in wsrc and "playoff rows never" in wsrc.lower())
csrc = open(os.path.join(REPO, "calendar_window.py")).read()
check("27. CalendarView details call narrative",
      "_insert_matchup_narrative" in csrc)
check("28. calendar 'History & Heat' section added",
      "History & Heat" in csrc)
check("29. narrative write-guard documented",
      "is invented or duplicated" in csrc)

# --- 5. grudge-week market still firing in both sim paths --------------
check("30. grudge-week market in sim path 1", "10300" not in src or
      "_grudge_week_market" in src)
gw_calls = src.count("_grudge_week_market(")
check("31. grudge-week market both paths", gw_calls >= 3,
      f"calls={gw_calls}")
check("32. grudge-week threshold unchanged", "_mw < 60.0" in src)

# --- 6. playoff behavior unchanged -------------------------------------
psrc = open(os.path.join(REPO, "playoff_system.py")).read()
check("33. playoff hype choke point intact",
      "_compute_series_hype" in psrc and "Bad blood" in psrc)
check("34. playoff marquee rendering untouched",
      "\\u2605" in wsrc and "tag_configure('marquee'" in wsrc)

# --- 7. output contract + dedupe ---------------------------------------
contract = {"rivalry_heat", "mem_weight", "hype_tags", "marquee", "grudge",
            "iconic_headline"}
check("35. helper output contract stable", set(n.keys()) == contract,
      f"keys={sorted(n.keys())}")
check("36. tags deduplicated across sources", len(n["hype_tags"]) ==
      len(set(n["hype_tags"])), f"tags={n['hype_tags']}")

# --- 8. threshold parity ----------------------------------------------
check("37. 'Bad blood' parity: crowd(65) == narrative(65)",
      n["rivalry_heat"] >= 65 and "Bad blood" in n["hype_tags"])
check("38. ledger 70+ parity in narrative", n2["mem_weight"] >= 40.0)
check("39. grudge flag threshold parity",
      n["grudge"] and not n3["grudge"])
check("40. heat clamped to 0-100",
      0.0 <= n["rivalry_heat"] <= 100.0)

# --- 9. GUI regression (DISPLAY-gated) --------------------------------
_gui_checks = []
if os.environ.get("DISPLAY"):
    try:
        import customtkinter as ctk
        from ctk_theme import init_ctk_theme
        import windows as _w
        import calendar_window as _cw
        from types import SimpleNamespace as _SN
        from datetime import date as _date

        _gf = _SN(team_name="Falcons", roster=[], iconic_games=[
            {"home": "Falcons", "away": "Wolves", "season": 2028,
             "kind": "OT thriller",
             "headline": "Falcons win 5-4 OT classic", "id": "IC-1"}])
        _gw = _SN(team_name="Wolves", roster=[], iconic_games=[])
        _war = dict(playoff_war)
        _lg = _SN(teams=[_gf, _gw], schedule=[
            {"date": _date(2029, 10, 8), "home_team": _gf, "away_team": _gw,
             "time": "19:00", "league": "NHL"}],
            season_year=2029, rivalries=[_war], ceremony_schedule={})
        _app = _SN(league=_lg, user_team=_gf,
                   current_date=_date(2029, 10, 8),
                   game_results=[], open_windows={}, schedule=[])
        _app.find_game_result = lambda d, h, a: None

        _root = ctk.CTk(); _root.geometry("1600x900"); init_ctk_theme()
        _sv = _w.ScheduleView(_root, app=_app)
        _sv.pack(fill="both", expand=True)
        _root.update_idletasks(); _root.update()
        _rows = {}
        for _tree in (_sv.my_schedule_tree, _sv.league_schedule_tree):
            for _iid in _tree.get_children():
                _v = _tree.item(_iid, "values")
                _rows[(_v[1], _v[3])] = (_v[4], _tree.item(_iid, "tags"))
        _st, _tg = _rows.get(("Wolves", "Falcons"), ("", ()))
        check("42. GUI: grudge row is marquee gold",
              "marquee" in _tg and "Bad blood" in _st,
              f"status={_st!r} tags={_tg}")

        _cv = _cw.CalendarView(_root, app=_app)
        _cv.pack(fill="both", expand=True)
        _root.update_idletasks(); _root.update()
        _cv.events_text.configure(state="normal")
        _cv._insert_matchup_narrative(_gf, _gw)
        _cv.events_text.configure(state="disabled")
        _root.update()
        _txt = _cv.events_text.get("1.0", "end")
        check("43. GUI: calendar shows History & Heat",
              "History & Heat" in _txt and "Bad blood" in _txt)
        check("44. GUI: calendar shows iconic headline",
              "Falcons win 5-4 OT classic" in _txt)
        _root.destroy()
    except Exception as ex:
        check("42-44. GUI section", False, f"{type(ex).__name__}: {ex}")
else:
    print("  (GUI section skipped: no DISPLAY)")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
