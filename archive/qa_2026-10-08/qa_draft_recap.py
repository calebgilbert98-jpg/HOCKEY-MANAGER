# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: draft recap feature (fantasy + entry).

Verifies, against the acceptance criteria:
- conduct_entry_draft() -> league.draft_recap_history[str(year)] with all
  picks, each having overall_pick, round, team_name, player_name,
  overall_rating, age, potential, position
- GameManager.conduct_fantasy_draft() -> league.draft_recap_history['fantasy']
  with the same structure
- draft_recap.build_fantasy_draft_recap / build_entry_draft_recap exist
- Full round-by-round board (not just top 10)
- Best values / biggest reaches derived from pick_slot_value /
  drafted_player_value
- Inbox message posted after each draft (subject contains DRAFT RECAP)
- Recap data is JSON-serializable and survives save/load
- Adversarial: empty draft, missing attrs, no user team, headless,
  idempotent rebuilds, bad year input
- Native DraftRecapScreen instantiates and refresh()es without errors
  (offscreen Qt)
"""
import json
import os
import random
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")
        print(f"  FAIL {name} {detail}")


from game_classes import League, Team, DraftPick
import draft_generator
import draft_recap as dr
from draft_night import conduct_entry_draft, pick_slot_value, drafted_player_value

REQUIRED_KEYS = {"overall_pick", "round", "team_name", "player_name",
                 "overall_rating", "age", "potential", "position"}


def make_team(i, user=False):
    t = Team(f"Club{i}", f"City{i}", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.is_user_team = user
    return t


class FakePick(DraftPick):
    def __init__(self, rnd, team_name, year=2029):
        super().__init__(year=year, round=rnd, original_team=team_name,
                         current_team=team_name)
        self.overall_pick = None


def make_draft_league(n_teams=4, n_prospects=40, year=2029, seed=1234,
                      user_team=True):
    random.seed(seed)
    league = League("NHL")
    league.season_year = year
    league.draft_prospects_year = year
    teams = [make_team(i, user=(user_team and i == 0))
             for i in range(n_teams)]
    league.teams = teams
    league.draft_prospects = draft_generator.generate_draft_class(
        n_prospects, draft_year=year)
    order = []
    _ov = 0
    for rnd in range(1, 8):
        for t in teams:
            _ov += 1
            order.append((_ov, t, FakePick(rnd, t.team_name, year=year)))
    league.get_draft_order = lambda _y: order  # noqa: E731
    league.initialize_all_draft_picks = lambda: None  # noqa: E731
    return league, teams, order


def make_app(league, teams):
    news = []
    app = SimpleNamespace(
        league=league, user_team=teams[0], ai_manager=None,
        add_news=lambda s: news.append(s),
        mp_host=None, current_date="2029-06-27")
    app._news = news
    return app


def check_pick_shape(name, picks):
    ok = all(REQUIRED_KEYS <= set(p.keys()) for p in picks)
    check(f"{name}: every pick has required keys", ok)
    return ok


print("== A. entry draft recap ==")
league, teams, order = make_draft_league()
app = make_app(league, teams)
picks = conduct_entry_draft(league, 2029, app=app, seed=99,
                            allow_user_autodraft=True)
check("entry: picks made", len(picks) == 28, f"got {len(picks)}")
check("entry: recap key exists", "2029" in (league.draft_recap_history or {}))
recap = league.draft_recap_history.get("2029") or {}
check("entry: recap is a dict", isinstance(recap, dict))
check("entry: all picks stored", recap.get("num_picks") == len(picks),
      f"{recap.get('num_picks')} vs {len(picks)}")
check_pick_shape("entry", recap.get("picks") or [])
rpicks = recap.get("picks") or []
check("entry: overalls are 1..N in order",
      [p["overall_pick"] for p in rpicks] == list(range(1, 29)))
check("entry: rounds derived (overall-1)//4+1",
      all(p["round"] == (p["overall_pick"] - 1) // 4 + 1 for p in rpicks))
check("entry: num_rounds == 7", recap.get("num_rounds") == 7)
check("entry: every round has 4 picks",
      all(sum(1 for p in rpicks if p["round"] == r) == 4
          for r in range(1, 8)))
check("entry: grades for all 4 teams",
      len(recap.get("grades") or []) == 4
      and all(len(g) == 3 for g in recap["grades"]),
      str(recap.get("grades")))
check("entry: grades match draft_grades()",
      [g[0] for g in recap["grades"]] ==
      [t for t, _g, _r in __import__("draft_night").draft_grades(picks)])
bd = recap.get("positional_breakdown") or {}
check("entry: positional breakdown sums to num_picks",
      sum(bd.values()) == recap.get("num_picks"), str(bd))
check("entry: value_ratio computed on picks",
      sum(1 for p in rpicks if p.get("value_ratio") is not None) > 20)
# best value should be a late pick with a high ratio; reaches the reverse
valued = sorted([p for p in rpicks if p.get("value_ratio") is not None],
                key=lambda p: p["value_ratio"], reverse=True)
check("entry: best value has ratio >= 1", valued[0]["value_ratio"] >= 1,
      str(valued[0]["value_ratio"]))
worst = sorted([p for p in rpicks if p.get("value_ratio") is not None],
               key=lambda p: p["value_ratio"])
check("entry: biggest reach has lowest ratio",
      worst[0]["value_ratio"] <= worst[-1]["value_ratio"])
check("entry: draft_recap_latest set",
      getattr(league, "draft_recap_latest", "") == "2029")
subjects = [getattr(m, "subject", "") for m in teams[0].inbox.messages]
check("entry: inbox recap message posted",
      any("DRAFT RECAP" in s for s in subjects), str(subjects))
check("entry: user picks tagged to Club0",
      any(p["team_name"] == "Club0" for p in rpicks))

print("== B. fantasy draft recap ==")
from game_manager import GameManager
random.seed(11)
gm = GameManager("Test League")
fleague = gm.league
fleague.season_year = 2026
fteams = []
for i in range(4):
    t = Team(f"FClub{i}", f"FCity{i}", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.is_user_team = (i == 0)
    t.roster = draft_generator.generate_draft_class(20, draft_year=2000)
    fteams.append(t)
fleague.teams = fteams
gm.user_team = fteams[0]
gm.conduct_fantasy_draft()
check("fantasy: recap key exists",
      "fantasy" in (fleague.draft_recap_history or {}))
frecap = fleague.draft_recap_history.get("fantasy") or {}
fpicks = frecap.get("picks") or []
check("fantasy: all picks stored",
      frecap.get("num_picks") == len(fpicks) and len(fpicks) > 0,
      f"{frecap.get('num_picks')}")
check_pick_shape("fantasy", fpicks)
check("fantasy: overalls are 1..N in order",
      [p["overall_pick"] for p in fpicks] == list(range(1, len(fpicks) + 1)))
check("fantasy: rounds come from DraftPick.round_num",
      all(1 <= p["round"] <= 40 for p in fpicks))
check("fantasy: every round grouped",
      all(sum(1 for p in fpicks if p["round"] == r) >= 1
          for r in range(1, int(frecap.get("num_rounds") or 0) + 1)))
check("fantasy: grades for all 4 teams",
      len(frecap.get("grades") or []) == 4)
fbd = frecap.get("positional_breakdown") or {}
check("fantasy: positional breakdown sums to num_picks",
      sum(fbd.values()) == frecap.get("num_picks"), str(fbd))
check("fantasy: draft_recap_latest set",
      getattr(fleague, "draft_recap_latest", "") == "fantasy")
fsubjects = [getattr(m, "subject", "") for m in fteams[0].inbox.messages]
check("fantasy: inbox recap message posted",
      any("DRAFT RECAP" in s for s in fsubjects), str(fsubjects))
check("fantasy: accessor list_draft_recaps",
      dr.list_draft_recaps(fleague) == ["fantasy"])
check("fantasy: accessor get_draft_recap",
      dr.get_draft_recap(fleague, "fantasy") is frecap)
check("fantasy: recap JSON-serializable",
      bool(json.dumps(frecap)))
check("entry: recap JSON-serializable", bool(json.dumps(recap)))

print("== C. adversarial ==")
# empty draft
empty_rec = dr.build_entry_draft_recap(league, 2031, [])
check("adversarial: empty picks_made -> 0-pick recap, no crash",
      isinstance(empty_rec, dict) and empty_rec.get("num_picks") == 0
      and empty_rec.get("picks") == [])
# player with missing attrs
bare = SimpleNamespace()
weird_rec = dr.build_entry_draft_recap(league, 2032,
                                       [("Club0", 1, bare),
                                        ("Club1", 2, None)])
wp = weird_rec.get("picks") or []
check("adversarial: missing attrs -> defaults, no crash",
      len(wp) == 1 and wp[0]["player_name"] == "?"
      and wp[0]["overall_rating"] is None
      and wp[0]["position"] == "?")
# no user team -> no inbox, no crash
league2, teams2, _o2 = make_draft_league(year=2033, seed=5, user_team=False)
n_inbox_before = sum(len(t.inbox.messages) for t in teams2)
r2 = dr.build_entry_draft_recap(
    league2, 2033, [("Club0", 1, bare)])
check("adversarial: no user team -> recap built, no inbox, no crash",
      r2.get("num_picks") == 1
      and sum(len(t.inbox.messages) for t in teams2) == n_inbox_before)
# headless conduct (app=None)
league3, teams3, _o3 = make_draft_league(year=2034, seed=6, user_team=False)
p3 = conduct_entry_draft(league3, 2034, app=None, seed=6,
                         allow_user_autodraft=True)
check("adversarial: headless app=None conducts + recaps",
      len(p3) == 28 and "2034" in (league3.draft_recap_history or {}))
# idempotent rebuild: same object, no duplicate inbox
msg_count = len(teams[0].inbox.messages)
again = dr.build_entry_draft_recap(league, 2029, picks)
check("adversarial: rebuild is idempotent (same object)",
      again is recap)
check("adversarial: rebuild posts no duplicate inbox",
      len(teams[0].inbox.messages) == msg_count)
# bad year input
bad = dr.build_entry_draft_recap(league, "not-a-year", picks)
check("adversarial: bad year -> {} no crash", bad == {})
# unknown key accessors
check("adversarial: get_draft_recap unknown -> None",
      dr.get_draft_recap(league, "1999") is None)
# fantasy rebuild idempotent
fagain = dr.build_fantasy_draft_recap(fleague, SimpleNamespace(
    draft_picks=[]))
check("adversarial: fantasy rebuild idempotent",
      fagain is frecap)

print("== D. save/load round-trip ==")
# save_load_system imports customtkinter at module level for its legacy
# SaveLoadView UI class; the GameSaveManager logic under test does not
# need it, so stub the UI-only modules (same env as CI here).
import types as _types
_ctk_stub = _types.ModuleType("customtkinter")
_ctk_stub.CTkFrame = type("CTkFrame", (), {})
for _mod, _obj in (("customtkinter", _ctk_stub),):
    if _mod not in sys.modules:
        sys.modules[_mod] = _obj
if "ctk_theme" not in sys.modules:
    _ctk_theme_stub = _types.ModuleType("ctk_theme")
    _ctk_theme_stub.BG = "#000000"
    sys.modules["ctk_theme"] = _ctk_theme_stub
from save_load_system import GameSaveManager as _SLS
_gm = SimpleNamespace(league=league, league_history=None,
                      narrative_ledger=None)
_saver = _SLS(_gm)
_tmp = tempfile.mkdtemp()
_path = os.path.join(_tmp, "recap_test.save")
check("save/load: save succeeds", _saver.save_game(_path), _path)
_gm2 = SimpleNamespace(league=None, league_history=None,
                       narrative_ledger=None)
_loader = _SLS(_gm2)
check("save/load: load succeeds", _loader.load_game(_path), _path)
_lg2 = _gm2.league
_r2 = (_lg2.draft_recap_history or {}).get("2029") or {}
check("save/load: recap survives",
      _r2.get("num_picks") == 28 and len(_r2.get("picks") or []) == 28)
_p0 = (_r2.get("picks") or [{}])[0]
check("save/load: pick shape survives",
      REQUIRED_KEYS <= set(_p0.keys())
      and _p0.get("overall_pick") == 1 and _p0.get("round") == 1)
check("save/load: grades survive",
      len(_r2.get("grades") or []) == 4)
check("save/load: draft_recap_latest survives",
      # latest was overwritten by the 2031/2032 adversarial builds
      getattr(_lg2, "draft_recap_latest", "") == "2032",
      str(getattr(_lg2, "draft_recap_latest", "")))
# old save without the keys -> graceful defaults
_orig_ser = _saver._serialize_league


def _stripped_ser():
    _d = _orig_ser()
    _d.pop("draft_recap_history", None)
    _d.pop("draft_recap_latest", None)
    return _d


_saver._serialize_league = _stripped_ser
_path_old = os.path.join(_tmp, "recap_test_old.save")
_old_ok = _saver.save_game(_path_old)
_gm3 = SimpleNamespace(league=None, league_history=None,
                       narrative_ledger=None)
_s3 = _SLS(_gm3)
_old_ok = _old_ok and _s3.load_game(_path_old)
_lg3 = _gm3.league
_old_ok = (_old_ok
           and getattr(_lg3, "draft_recap_history", None) == {}
           and getattr(_lg3, "draft_recap_latest", "") == "")
check("save/load: old save without keys loads with defaults",
      _old_ok is True, str(_old_ok)[:120])

print("== E. native UI screen ==")
_UI_OK = False
try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication  # noqa: F401
    _UI_OK = True
except ImportError:
    _UI_OK = False
if _UI_OK:
    # Real Qt available: instantiate + refresh the screen offscreen.
    from PySide6.QtWidgets import QApplication
    _qt_app = QApplication.instance() or QApplication([])
    from native_ui.screens.draft_recap import DraftRecapScreen
    fake_game = SimpleNamespace(game_manager=gm)
    scr = DraftRecapScreen(fake_game, None)
    check("ui: screen instantiates", scr is not None)
    try:
        scr.refresh()
        check("ui: refresh() renders without errors", True)
    except Exception as e:
        check("ui: refresh() renders without errors", False, repr(e)[:200])
    items = [scr._draft_combo.itemData(i)
             for i in range(scr._draft_combo.count())]
    check("ui: draft selector lists fantasy draft", "fantasy" in items,
          str(items))
    import native_ui.main_window as _mw
    import inspect as _inspect
    src = _inspect.getsource(_mw)
    check("ui: draft_recap registered in main_window",
          '"draft_recap": DraftRecapScreen' in src
          and "from native_ui.screens.draft_recap import DraftRecapScreen"
          in src)
else:
    # No Qt in this container: run the stub-harness UI suite, which
    # executes the real screen code paths with real recap data.
    import subprocess as _sp
    _r = _sp.run([sys.executable,
                  os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "qa_draft_recap_ui.py")],
                 capture_output=True, text=True, timeout=600)
    check("ui: stub-harness UI suite passes", _r.returncode == 0,
          (_r.stdout or "")[-600:] + (_r.stderr or "")[-300:])
    _mw_src = open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "native_ui", "main_window.py")).read()
    check("ui: draft_recap registered in main_window",
          '"draft_recap": DraftRecapScreen' in _mw_src
          and "from native_ui.screens.draft_recap import DraftRecapScreen"
          in _mw_src)

print(f"\n{'='*60}\nQA draft_recap: {PASS} passed, {FAIL} failed")
if FAILURES:
    print("FAILURES:")
    for f in FAILURES:
        print(" -", f)
    sys.exit(1)
