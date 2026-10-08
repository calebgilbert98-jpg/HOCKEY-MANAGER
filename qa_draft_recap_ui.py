# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: draft recap native UI logic (headless).

Executes the REAL DraftRecapScreen / HistoryScreen code and the inbox
_special_action against a functional-minimal Qt stub (/tmp/qtstub) with
real recap data produced by conduct_entry_draft / conduct_fantasy_draft.

This proves the screens build and render without Python errors and show
the right content. It is NOT a visual test: a real-Qt offscreen render
was not possible in this container (no Mesa EGL); every Qt API call used
was cross-checked against the identical calls in the proven
awards_ceremony.py / history.py / inbox.py screens.
"""
import os
import random
import sys
from types import SimpleNamespace

_STUB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "qtstub")
sys.path.insert(0, _STUB_DIR)  # stub PySide6 BEFORE any screen import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

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


from game_classes import League, Team, DraftPick, EmailMessage
import draft_generator
import draft_recap as dr
from draft_night import conduct_entry_draft

from PySide6.QtWidgets import QWidget, QTableWidget, QLabel, QComboBox  # stub


def make_team(i, user=False):
    t = Team(f"Club{i}", f"City{i}", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.is_user_team = user
    return t


class FakePick(DraftPick):
    def __init__(self, rnd, team_name, year):
        super().__init__(year=year, round=rnd, original_team=team_name,
                         current_team=team_name)
        self.overall_pick = None


def run_entry_draft(year, seed, user_team=True):
    random.seed(seed)
    league = League("NHL")
    league.season_year = year
    league.draft_prospects_year = year
    teams = [make_team(i, user=(user_team and i == 0)) for i in range(4)]
    league.teams = teams
    league.draft_prospects = draft_generator.generate_draft_class(
        40, draft_year=year)
    order = []
    _ov = 0
    for rnd in range(1, 8):
        for t in teams:
            _ov += 1
            order.append((_ov, t, FakePick(rnd, t.team_name, year)))
    league.get_draft_order = lambda _y: order  # noqa: E731
    league.initialize_all_draft_picks = lambda: None  # noqa: E731
    app = SimpleNamespace(league=league, user_team=teams[0],
                          add_news=lambda s: None)
    picks = conduct_entry_draft(league, year, app=app, seed=seed,
                                allow_user_autodraft=True)
    return league, teams, picks


def walk_widgets(layout):
    """Yield every widget in a layout tree (depth-first)."""
    for kind, obj in list(layout._items):
        if kind == "widget" and isinstance(obj, QWidget):
            yield obj
            if obj.layout() is not None:
                yield from walk_widgets(obj.layout())
        elif kind == "layout":
            yield from walk_widgets(obj)


def tables_of(screen):
    return [w for w in walk_widgets(screen._content_layout)
            if isinstance(w, QTableWidget)]


def labels_of(screen):
    return [w for w in walk_widgets(screen._content_layout)
            if isinstance(w, QLabel)]


print("== UI-1: entry draft recap screen ==")
league, teams, picks = run_entry_draft(2029, 99)
from native_ui.screens.draft_recap import DraftRecapScreen

fake_main = SimpleNamespace(shown=[],
                            show_screen=lambda n: fake_main.shown.append(n))
fake_game = SimpleNamespace(game_manager=SimpleNamespace(
    league=league, user_team=teams[0]))
scr = DraftRecapScreen(fake_game, fake_main)
check("ui: screen instantiates", scr is not None)
try:
    scr.refresh()
    check("ui: refresh() completes without errors", True)
except Exception as e:
    check("ui: refresh() completes without errors", False, repr(e)[:200])

items = [(scr._draft_combo.itemText(i), scr._draft_combo.itemData(i))
         for i in range(scr._draft_combo.count())]
check("ui: draft selector lists the 2029 entry draft",
      ("2029 Entry Draft", "2029") in items, str(items))
check("ui: round selector has 7 rounds", scr._round_combo.count() == 7)

texts = [l.text() for l in labels_of(scr)]
check("ui: headline shows draft title",
      "2029 ENTRY DRAFT RECAP" in texts, str(texts[:3]))

tbls = tables_of(scr)
check("ui: five tables rendered (top10/user/best/reach/board)",
      len(tbls) == 5, f"got {len(tbls)}")
if len(tbls) == 5:
    top10, mine, best, reach, board = tbls
    check("ui: top-10 table has 10 rows", top10.rowCount() == 10)
    check("ui: top-10 first cell is #1",
          top10.cell_text(0, 0) == "#1", top10.cell_text(0, 0))
    check("ui: top-10 row shows OVR/age/pot/pos/team",
          top10.cell_text(0, 3).isdigit() and top10.cell_text(0, 7) != "",
          f"{top10.cell_text(0, 3)}|{top10.cell_text(0, 7)}")
    check("ui: user-picks table has 7 rows (Club0)",
          mine.rowCount() == 7, str(mine.rowCount()))
    check("ui: best-values table has 8 rows", best.rowCount() == 8)
    check("ui: reaches table has 8 rows", reach.rowCount() == 8)
    # best values sorted desc by value column
    def _val(t, r):
        try:
            return float(t.cell_text(r, 8).replace("x", ""))
        except Exception:
            return -1
    check("ui: best-values sorted by value desc",
          all(_val(best, r) >= _val(best, r + 1)
              for r in range(best.rowCount() - 1)))
    check("ui: reaches sorted by value asc",
          all(_val(reach, r) <= _val(reach, r + 1)
              for r in range(reach.rowCount() - 1)))
    check("ui: round-1 board has 4 rows", board.rowCount() == 4)
    check("ui: round-1 board first pick is #1",
          board.cell_text(0, 0) == "#1")

grade_labels = [t for t in texts if t.startswith("Draft grade:")]
check("ui: user draft grade shown",
      len(grade_labels) == 1 and grade_labels[0].split(": ")[1].strip()
      in ("A+", "A", "B+", "B", "C", "D", "F"),
      str(grade_labels))

# round switching re-renders the board
scr._round_combo.setCurrentIndex(6)  # round 7
tbls2 = tables_of(scr)
check("ui: switching to round 7 re-renders board",
      tbls2[-1].rowCount() == 4 and tbls2[-1].cell_text(0, 0) == "#25"
      and tbls2[-1].cell_text(0, 1) == "7",
      f"{tbls2[-1].cell_text(0, 0)}|{tbls2[-1].cell_text(0, 1)}")

print("== UI-2: draft selector across years ==")
league2, teams2, _p2 = run_entry_draft(2030, 4242)
# second entry draft on the SAME league -> two recaps to switch between
random.seed(777)
league2.draft_prospects = draft_generator.generate_draft_class(
    40, draft_year=2031)
order2 = []
_ov = 0
for rnd in range(1, 8):
    for t in teams2:
        _ov += 1
        order2.append((_ov, t, FakePick(rnd, t.team_name, 2031)))
league2.get_draft_order = lambda _y: order2  # noqa: E731
app2 = SimpleNamespace(league=league2, user_team=teams2[0],
                       add_news=lambda s: None)
conduct_entry_draft(league2, 2031, app=app2, seed=777,
                    allow_user_autodraft=True)
fake_game2 = SimpleNamespace(game_manager=SimpleNamespace(
    league=league2, user_team=teams2[0]))
scr2 = DraftRecapScreen(fake_game2, fake_main)
scr2.refresh()
keys2 = [scr2._draft_combo.itemData(i)
         for i in range(scr2._draft_combo.count())]
check("ui: selector lists both entry years", keys2 == ["2030", "2031"],
      str(keys2))
check("ui: latest draft pre-selected",
      scr2._draft_combo.currentData() == "2031",
      str(scr2._draft_combo.currentData()))
texts2 = [l.text() for l in labels_of(scr2)]
check("ui: shows 2031 headline", "2031 ENTRY DRAFT RECAP" in texts2)
scr2._draft_combo.setCurrentIndex(0)  # back to 2030
texts2b = [l.text() for l in labels_of(scr2)]
check("ui: switching draft re-renders headline",
      "2030 ENTRY DRAFT RECAP" in texts2b)

print("== UI-3: fantasy draft recap screen ==")
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
fake_game3 = SimpleNamespace(game_manager=gm)
scr3 = DraftRecapScreen(fake_game3, fake_main)
try:
    scr3.refresh()
    check("ui: fantasy refresh() completes without errors", True)
except Exception as e:
    check("ui: fantasy refresh() completes without errors", False,
          repr(e)[:200])
items3 = [(scr3._draft_combo.itemText(i), scr3._draft_combo.itemData(i))
          for i in range(scr3._draft_combo.count())]
check("ui: selector lists fantasy draft",
      ("Fantasy Draft", "fantasy") in items3, str(items3))
texts3 = [l.text() for l in labels_of(scr3)]
check("ui: fantasy headline", "FANTASY DRAFT RECAP" in texts3)
n_rounds = scr3._round_combo.count()
check("ui: fantasy round selector matches recap rounds",
      n_rounds == (fleague.draft_recap_history["fantasy"]["num_rounds"] or 0)
      and n_rounds > 0,
      str(n_rounds))
tbls3 = tables_of(scr3)
check("ui: fantasy renders five tables", len(tbls3) == 5,
      f"got {len(tbls3)}")
if len(tbls3) == 5:
    check("ui: fantasy top-10 first cell is #1",
          tbls3[0].cell_text(0, 0) == "#1")
    # every round of the full board renders
    ok = True
    for r in range(n_rounds):
        try:
            scr3._round_combo.setCurrentIndex(r)
            bt = tables_of(scr3)[-1]
            expect = sum(1 for p in
                         fleague.draft_recap_history["fantasy"]["picks"]
                         if p["round"] == r + 1)
            if bt.rowCount() != expect:
                ok = False
        except Exception:
            ok = False
            break
    check(f"ui: all {n_rounds} fantasy rounds render full boards", ok)

print("== UI-4: empty state ==")
empty_league = League("NHL")
empty_league.teams = [make_team(0, user=True)]
fake_game4 = SimpleNamespace(game_manager=SimpleNamespace(
    league=empty_league, user_team=empty_league.teams[0]))
scr4 = DraftRecapScreen(fake_game4, None)
try:
    scr4.refresh()
    check("ui: empty league refreshes without errors", True)
except Exception as e:
    check("ui: empty league refreshes without errors", False, repr(e)[:200])
check("ui: empty state message shown",
      scr4._empty.isVisible() and "No draft recaps yet" in scr4._empty.text())
check("ui: content hidden when empty", not scr4._content.isVisible())

print("== UI-5: inbox draft-recap action ==")
from native_ui.screens.inbox import _special_action
recap_msg = next(m for m in teams[0].inbox.messages
                 if "DRAFT RECAP" in getattr(m, "subject", ""))
check("ui: _special_action(recap msg) -> draft_recap",
      _special_action(fake_game, recap_msg) == "draft_recap")
pre_msg = EmailMessage(sender="NHL Commissioner", sender_type="League",
                       subject="🏒 FANTASY DRAFT - Ready to Begin!")
gm_pending = SimpleNamespace(league=league, pending_fantasy_draft=True)
check("ui: pre-draft fantasy msg still -> fantasy_draft (no regression)",
      _special_action(SimpleNamespace(game_manager=gm_pending), pre_msg)
      == "fantasy_draft")
other = EmailMessage(sender="Agent", sender_type="Agent",
                     subject="Contract talks")
check("ui: unrelated msg -> no special action",
      _special_action(fake_game, other) == "")
# the recap branch wins even if a (hypothetical) pending flag were set
check("ui: recap branch takes precedence over pending fantasy draft",
      _special_action(SimpleNamespace(game_manager=gm_pending), recap_msg)
      == "draft_recap")

print("== UI-6: history screen link ==")
from native_ui.screens.history import HistoryScreen
try:
    hs = HistoryScreen(fake_game2, fake_main)
    check("ui: history screen instantiates", True)
except Exception as e:
    check("ui: history screen instantiates", False, repr(e)[:200])
    hs = None
if hs is not None:
    btn = getattr(hs, "_recaps_btn", None)
    check("ui: history has Draft Recaps button", btn is not None)
    if btn is not None:
        check("ui: button labeled correctly",
              "Draft Recaps" in btn.text(), btn.text())
        btn.click()  # fires navigate_to -> main_window.show_screen
        check("ui: button navigates to draft_recap",
              fake_main.shown and fake_main.shown[-1] == "draft_recap",
              str(fake_main.shown[-3:]))

print(f"\n{'='*60}\nQA draft_recap_ui: {PASS} passed, {FAIL} failed")
if FAILURES:
    print("FAILURES:")
    for f in FAILURES:
        print(" -", f)
    sys.exit(1)
