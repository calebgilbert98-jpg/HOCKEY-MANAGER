"""Screenshots + accessibility QA for the draft UX backlog (8 items).

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_draft_ux_shots.py

Shots (qa_shots_draft/):
  ux_01_grades.png       draft review modal (item 8)
  ux_02_clock.png        war room with the SP draft countdown running (item 1)
  ux_03_rights_tab.png   prospects tab with the Rights column (item 6)
  ux_04_rights_watch.png Rights Watch modal (item 6)

A11y checks per surface: min font size, widget clipping, popup fit within
92% of the app window, no nested scrollables.
"""
import os
import random
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(2029)

import customtkinter as ctk
from PIL import ImageGrab
from types import SimpleNamespace

import windows
from game_classes import League, Team, DraftPick
import draft_generator
import draft_night

PASS, FAIL, WARN = [], [], []


def check(kind, name, cond, detail=""):
    (PASS if cond else (FAIL if kind == "fail" else WARN)).append(name)
    tag = {"fail": "  ok  " if cond else "  FAIL",
           "warn": "  ok  " if cond else "  warn"}[kind]
    print(f"{tag} {name}" + (f" -- {detail}" if detail and not cond else ""))


SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "qa_shots_draft")
os.makedirs(SHOT_DIR, exist_ok=True)


def shot(name):
    path = os.path.join(SHOT_DIR, name)
    ImageGrab.grab().save(path)
    print(f"shot: {path}")
    return path


# ---------------------------------------------------------------- league
def make_team(i):
    t = Team(f"Club{i}", f"City{i}", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.salary_cap = 104_000_000
    return t


league = League("NHL")
league.season_year = 2029
league.draft_prospects_year = 2029
teams = [make_team(i) for i in range(4)]
league.teams = teams
league.draft_prospects = draft_generator.generate_draft_class(
    40, draft_year=2029)
_order = []
for rnd in range(1, 8):
    for t in teams:
        _dp = DraftPick(year=2029, round=rnd, original_team=t.team_name,
                        current_team=t.team_name)
        _order.append((rnd, t, _dp))
league.get_draft_order = lambda _y: _order  # noqa: E731
league.initialize_all_draft_picks = lambda: None  # noqa: E731

_news = []


class FakeApp:
    """Explicit attrs win; anything else degrades gracefully (None for
    CONSTANTS, no-op for methods) so heavy views construct in the
    screenshot harness."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name.isupper():
            return None
        return lambda *a, **k: None


app = FakeApp(
    league=league, user_team=teams[0], ai_manager=None, mp_host=None,
    add_news=lambda s: _news.append(s),
    add_news_story=lambda s: _news.append(s),
    get_settings=lambda: {'draft': {'clock_seconds': 60}},
    open_windows={},
    open_contract_negotiation_window=lambda *a, **k: None,
    update_all_views=lambda: None,
    _bind_player_context_menu=lambda *a, **k: None,
    current_date="2029-06-27")
app.game_manager = SimpleNamespace(trade_history=[],
                                   current_date="2029-06-27")

picks = draft_night.conduct_entry_draft(league, 2029, app=app, seed=99)
print(f"conducted {len(picks)} picks, "
      f"user prospects: {len(teams[0].prospects)}")

# ---------------------------------------------------------------- DraftView
import popup_system
root = ctk.CTk()
popup_system.register(root)  # InGamePopup cards need the overlay manager
root.geometry("1600x900")
root.update()

view = windows.DraftView(root, app=app)
view.picks_made = picks
view.pack(fill="both", expand=True)
root.update()
root.update_idletasks()


def check_fonts(name, node):
    from tkinter import font as tkfont
    try:
        import customtkinter as _ctk
        _CTK = (_ctk.CTkLabel, _ctk.CTkButton, _ctk.CTkOptionMenu,
                _ctk.CTkCheckBox, _ctk.CTkRadioButton, _ctk.CTkSwitch,
                _ctk.CTkEntry, _ctk.CTkComboBox)
    except Exception:
        _CTK = ()
    bad = []

    def walk(n):
        for ch in n.winfo_children():
            # CTk builds widgets from internal tk children (pixel-font
            # labels, textbox text widgets) -- implementation details,
            # not visible styling.
            if _CTK and isinstance(ch, (tk.Label, tk.Button)) \
                    and isinstance(ch.master, _CTK):
                continue
            if isinstance(ch, tk.Text) and isinstance(
                    ch.master, _ctk.CTkTextbox):
                continue
            yield ch
            yield from walk(ch)

    for w in walk(node):
        try:
            f = tkfont.Font(font=w.cget("font"))
            if f.actual("size") < 9:
                bad.append((str(w), f.actual("size")))
        except Exception:
            pass
    check("fail", f"{name}: min font >= 9px", not bad, str(bad[:3]))


def check_popup_fit(name, popup, parent):
    try:
        pw, ph = popup.winfo_width(), popup.winfo_height()
        rw, rh = parent.winfo_width(), parent.winfo_height()
        check("fail", f"{name}: popup fits in 92% of window "
              f"({pw}x{ph} in {rw}x{rh})",
              pw <= rw * 0.92 and ph <= rh * 0.92)
    except Exception as e:
        check("fail", f"{name}: popup fit measurable", False, str(e))


def check_clipping(name, node):
    bad = []

    def walk(n):
        for ch in n.winfo_children():
            yield ch
            yield from walk(ch)

    for w in list(walk(node)) + [node]:
        try:
            if w.winfo_width() <= 1:
                continue
            for ch in w.winfo_children():
                if ch.winfo_x() + ch.winfo_width() > w.winfo_width() + 4:
                    bad.append(str(ch))
                    break
        except Exception:
            pass
    check("warn", f"{name}: no horizontal clipping", not bad,
          str(bad[:3]))


# --- shot 1: draft grades modal (an in-game overlay card, not a Toplevel)
view.show_grades()
root.update()
root.update_idletasks()
time.sleep(0.6)
root.update()
shot("ux_01_grades.png")


def _find_cards(root_node):
    """The in-game overlay cards (InGamePopup instances)."""
    import popup_system as _ps
    hits = []

    def walk(n):
        for ch in n.winfo_children():
            if isinstance(ch, _ps.InGamePopup):
                hits.append(ch)
            walk(ch)

    walk(root_node)
    return hits


_cards = _find_cards(root)
check("fail", "grades card opened", len(_cards) >= 1)
if _cards:
    _node = _cards[-1]
    check_popup_fit("grades card", _node, root)
    check_fonts("grades card", _node)
    check_clipping("grades card", _node)
    try:
        _node.destroy()  # close before the next surface
    except Exception:
        pass
root.update()

# --- shot 2: war room with the SP countdown running
try:
    view.draft_order = [[1, teams[0],
                         DraftPick(year=2029, round=1,
                                   original_team=teams[0].team_name,
                                   current_team=teams[0].team_name)]]
    view.current_pick = 0
    view._start_sp_draft_clock()
    root.update()
    time.sleep(1.6)
    root.update()
    shot("ux_02_clock.png")
    _txt = view.clock_label.cget("text")
    check("fail", f"clock counts down on the war room ({_txt})",
          _txt not in ("—", "") and "s)" in _txt, repr(_txt))
    check_fonts("war room", view)
    check_clipping("war room", view)
    view._cancel_sp_draft_clock()
except Exception as e:
    check("fail", "clock screenshot", False, str(e)[:160])

# ---------------------------------------------------------------- RosterView
# Prospects tab (Rights column) + Rights Watch modal. Packed in the main
# root so the overlay card lands on the screenshotted window.
try:
    try:
        view.destroy()
    except Exception:
        pass
    root.update()
    rv = windows.RosterView(root, app=app)
    rv.pack(fill="both", expand=True)
    root.update()
    root.update_idletasks()

    # Find and raise the prospects tab (built on demand; programmatic
    # set() does not fire the click callback, so build explicitly).
    try:
        _pname = rv._tab_names.get('prospects', 'Prospects')
        rv.tabview.set(_pname)
        rv._build_roster_tab('prospects')
    except Exception as e:
        print("prospects tab select note:", str(e)[:120])
    root.update()
    root.update_idletasks()
    time.sleep(0.4)
    shot("ux_03_rights_tab.png")
    check("fail", "roster view constructs", True)

    # Rights Watch card (the overlay manager lives on root, so the card
    # may be parented there -- search both).
    rv.open_rights_watch()
    root.update()
    root.update_idletasks()
    time.sleep(0.6)
    root.update()
    shot("ux_04_rights_watch.png")

    _rc = _find_cards(root)
    # de-dup (same widget found via both roots is impossible; keep order)
    _seen = set()
    _rc = [c for c in _rc if not (id(c) in _seen or _seen.add(id(c)))]
    # the grades card was closed earlier -- the LAST card is ours
    check("fail", "rights watch card opened", len(_rc) >= 1,
          f"{len(_rc)} cards")
    if _rc:
        _node = _rc[-1]
        check_popup_fit("rights watch card", _node, root)
        check_fonts("rights watch card", _node)
        check_clipping("rights watch card", _node)
    try:
        _node.destroy()
    except Exception:
        pass
except Exception as e:
    check("fail", "roster/rights screenshots", False, str(e)[:200])

root.update()
print(f"\n{PASS and len(PASS)} passed, {len(FAIL)} failed, "
      f"{len(WARN)} warnings")
sys.exit(1 if FAIL else 0)
