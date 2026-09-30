"""QA: mid-draft scouting — right-click quick scout + research strip.

Run headless logic tests:
    python3 qa_draft_scouting.py
Run the Xvfb UI test (war-room screenshot + live right-click):
    xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_draft_scouting.py --ui
"""
import os
import random
import sys
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(20260701)

from game_classes import Player, PlayerPosition, Staff, StaffRole
import player_context_menu as pcm

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  ok  ' if cond else '  FAIL'} {name}"
          + (f" -- {detail}" if detail and not cond else ""))


# ------------------------------------------------------------------ fakes
_box_calls = []


class FakeBox:
    @staticmethod
    def showinfo(title, msg):
        _box_calls.append(("info", title, msg))

    @staticmethod
    def showwarning(title, msg):
        _box_calls.append(("warn", title, msg))


pcm.messagebox = FakeBox


class FakeMenu:
    instances = []

    def __init__(self, parent, tearoff=0):
        self.labels = []
        self.commands = {}
        FakeMenu.instances.append(self)

    def add_command(self, label=None, command=None, **kw):
        self.labels.append(label)
        self.commands[label] = command

    def add_separator(self):
        self.labels.append("---")

    def tk_popup(self, x, y):
        pass

    def grab_release(self):
        pass


_REAL_TK_MENU = pcm.tk.Menu  # real tkinter.Menu, before the fake
pcm.tk.Menu = FakeMenu


def make_scout(name="Ace", jpa=18, jpp=17,
               role=StaffRole.AMATEUR_SCOUT):
    s = Staff(name, "Scout", role, id=abs(hash(name)) % 10_000,
              age=45, nationality="Canada")
    s.judging_player_ability = jpa
    s.judging_player_potential = jpp
    return s


def make_prospect(i=1):
    return Player(f"Test{i}", "Prospect", 18, PlayerPosition.CENTER)


def make_app(scouts):
    team = SimpleNamespace(staff=list(scouts), scouting_reports={},
                           roster=[], ahl_roster=[], prospects=[])
    return SimpleNamespace(user_team=team, scouting_assignments={})


def make_menu(app):
    m = pcm.PlayerContextMenu.__new__(pcm.PlayerContextMenu)
    m.parent = SimpleNamespace(app=app)
    return m


# ------------------------------------------------- _quick_scout_player
def t_quick_scout_creates_report():
    _box_calls.clear()
    app = make_app([make_scout()])
    m = make_menu(app)
    p = make_prospect(1)
    ret = m._quick_scout_player(p)
    rep = app.user_team.scouting_reports.get(p.id)
    check("quick_scout: report created", rep is not None)
    check("quick_scout: single rushed viewing",
          getattr(rep, "viewings", 0) == 1,
          f"got {getattr(rep, 'viewings', 0)}")
    check("quick_scout: returns the report", ret is rep)
    check("quick_scout: accuracy graded",
          getattr(rep, "accuracy", None) in ("A", "B", "C", "D", "F"),
          f"got {getattr(rep, 'accuracy', None)}")
    check("quick_scout: potential scouted",
          bool(getattr(rep, "scouted_potential", None)))
    check("quick_scout: strengths scouted",
          bool(getattr(rep, "strengths", None)))
    check("quick_scout: assignment added",
          app.scouting_assignments.get(p) is not None)
    check("quick_scout: never modal (non-modal rule)",
          len(_box_calls) == 0, f"modal calls: {_box_calls}")


def t_quick_scout_existing_report():
    _box_calls.clear()
    app = make_app([make_scout()])
    m = make_menu(app)
    p = make_prospect(2)
    m._quick_scout_player(p)
    first = app.user_team.scouting_reports[p.id]
    n_assign = len(app.scouting_assignments)
    _box_calls.clear()
    ret = m._quick_scout_player(p)  # again: surface the existing take
    check("quick_scout: existing report reused",
          app.user_team.scouting_reports[p.id] is first)
    check("quick_scout: existing take adds no viewing",
          getattr(first, "viewings", 0) == 1)
    check("quick_scout: returns existing report", ret is first)
    check("quick_scout: no duplicate assignment",
          len(app.scouting_assignments) == n_assign)
    check("quick_scout: existing take never modal",
          len(_box_calls) == 0, f"modal calls: {_box_calls}")


def t_quick_scout_no_scouts():
    _box_calls.clear()
    app = make_app([])
    m = make_menu(app)
    p = make_prospect(3)
    ret = m._quick_scout_player(p)  # must not raise
    check("quick_scout: returns None without scouts", ret is None)
    check("quick_scout: no report without scouts",
          p.id not in app.user_team.scouting_reports)
    check("quick_scout: no-scout path never modal",
          len(_box_calls) == 0, f"modal calls: {_box_calls}")


class FakeDraftView:
    """Duck-typed stand-in for the entry-draft war-room view."""
    def __init__(self):
        self.ticker_lines = []
        self.refreshes = 0

    def _ticker(self, line):
        self.ticker_lines.append(line)

    def _refresh_draft_research(self):
        self.refreshes += 1

    def winfo_children(self):
        return []


def make_menu_with_view(app, view):
    m = pcm.PlayerContextMenu.__new__(pcm.PlayerContextMenu)
    m.parent = SimpleNamespace(app=app)
    app.winfo_children = lambda: [view]
    return m


def t_quick_scout_posts_ticker_and_refresh():
    _box_calls.clear()
    app = make_app([make_scout()])
    view = FakeDraftView()
    m = make_menu_with_view(app, view)
    p = make_prospect(9)
    m._quick_scout_player(p)
    check("quick_scout: take lands on the draft ticker",
          len(view.ticker_lines) == 1
          and "War-room take" in view.ticker_lines[0]
          and p.full_name in view.ticker_lines[0],
          f"got {view.ticker_lines}")
    check("quick_scout: research strip refreshed inline",
          view.refreshes == 1, f"got {view.refreshes}")
    check("quick_scout: feedback never modal",
          len(_box_calls) == 0)


def t_quick_scout_no_scout_ticker_note():
    _box_calls.clear()
    app = make_app([])
    view = FakeDraftView()
    m = make_menu_with_view(app, view)
    p = make_prospect(10)
    ret = m._quick_scout_player(p)
    check("quick_scout: no-scout take returns None", ret is None)
    check("quick_scout: no-scout note on ticker",
          len(view.ticker_lines) == 1
          and "no scouts" in view.ticker_lines[0].lower(),
          f"got {view.ticker_lines}")


def t_quick_scout_take_line():
    app = make_app([make_scout()])
    m = make_menu(app)
    p = make_prospect(11)
    rep = m._quick_scout_player(p)
    line = pcm.PlayerContextMenu._take_line(p, rep)
    check("quick_scout: take line names player and scout",
          p.full_name in line and "Ace" in line, f"got {line!r}")
    check("quick_scout: take line carries grade + viewing count",
          "potential" in line and "1 viewing" in line, f"got {line!r}")


def t_quick_scout_prefers_amateur():
    _box_calls.clear()
    pro = make_scout("Pro", jpa=20, jpp=20,
                     role=StaffRole.PROFESSIONAL_SCOUT)
    am = make_scout("Am", jpa=12, jpp=12,
                    role=StaffRole.AMATEUR_SCOUT)
    app = make_app([pro, am])
    m = make_menu(app)
    p = make_prospect(4)
    m._quick_scout_player(p)
    rep = app.user_team.scouting_reports[p.id]
    check("quick_scout: amateur scout preferred for draft takes",
          getattr(getattr(rep, "scout", None), "role", None)
          == StaffRole.AMATEUR_SCOUT)


def t_quick_scout_non_scout_staff_ignored():
    _box_calls.clear()
    coach = Staff("Bench", "Boss", StaffRole.HEAD_COACH, id=777,
                  age=50, nationality="Canada")
    app = make_app([coach])
    m = make_menu(app)
    p5 = make_prospect(5)
    ret = m._quick_scout_player(p5)
    check("quick_scout: coach is not a scout",
          ret is None and p5.id not in app.user_team.scouting_reports
          and len(_box_calls) == 0)


# ------------------------------------------------------- menu wiring
def t_menu_labels():
    FakeMenu.instances.clear()
    app = make_app([make_scout()])
    m = make_menu(app)
    p = make_prospect(6)
    evt = SimpleNamespace(x_root=100, y_root=100)
    m.show_context_menu(evt, p, quick_scout=True)
    labels = FakeMenu.instances[-1].labels
    check("menu: quick-scout entry present (draft)",
          "\u26a1 Quick Scout (war-room take)" in labels,
          f"got {labels[:4] if labels else labels}")
    FakeMenu.instances.clear()
    m.show_context_menu(evt, p, quick_scout=False)
    labels = FakeMenu.instances[-1].labels
    check("menu: plain Scout Player entry elsewhere",
          "Scout Player" in labels
          and "\u26a1 Quick Scout (war-room take)" not in labels)


def t_menu_quick_command_calls_quick_scout():
    FakeMenu.instances.clear()
    app = make_app([make_scout()])
    m = make_menu(app)
    p = make_prospect(7)
    calls = []
    orig = pcm.PlayerContextMenu._quick_scout_player
    pcm.PlayerContextMenu._quick_scout_player = \
        lambda self, pl: calls.append(pl)
    try:
        m.show_context_menu(SimpleNamespace(x_root=1, y_root=1), p,
                            quick_scout=True)
        menu = FakeMenu.instances[-1]
        menu.commands["\u26a1 Quick Scout (war-room take)"]()
    finally:
        pcm.PlayerContextMenu._quick_scout_player = orig
    check("menu: quick-scout entry invokes war-room take",
          calls == [p])


def t_app_resolution():
    app = make_app([make_scout()])
    m = make_menu(app)
    check("_app: resolves via .app", m._app() is app)
    m2 = pcm.PlayerContextMenu.__new__(pcm.PlayerContextMenu)
    m2.parent = SimpleNamespace(user_team=app.user_team)
    check("_app: resolves direct user_team", m2._app() is m2.parent)


# --------------------------------------------- fantasy draft handler
def t_fantasy_tree_handler():
    import fantasy_draft
    real_cls = pcm.PlayerContextMenu
    shown = []

    class RecMenu:
        def __init__(self, parent):
            self.parent = parent

        def show_context_menu(self, event, player, additional_options=None,
                              quick_scout=False):
            shown.append((player, quick_scout))

    pcm.PlayerContextMenu = RecMenu
    try:
        p = make_prospect(8)

        class FakeTree:
            def __init__(self, row, values):
                self._row, self._values = row, values

            def identify_row(self, y):
                return self._row

            def selection_set(self, item):
                pass

            def item(self, iid, opt=None):
                return self._values

        app = SimpleNamespace(tree_maps={"I001": p})
        fake_self = SimpleNamespace(app=app)
        evt = SimpleNamespace(y=10)

        # A: matching row -> menu with quick_scout
        shown.clear()
        fantasy_draft.FantasyDraftView._draft_tree_context_menu(
            fake_self, evt, FakeTree("I001", (p.full_name,)))
        check("fantasy: right-click opens quick-scout menu",
              len(shown) == 1 and shown[0][0] is p
              and shown[0][1] is True)

        # B: item-id collision across trees (name mismatch) -> silent
        shown.clear()
        fantasy_draft.FantasyDraftView._draft_tree_context_menu(
            fake_self, evt, FakeTree("I001", ("Somebody Else",)))
        check("fantasy: wrong-tree row ignored", shown == [])

        # C: click on empty space -> silent
        shown.clear()
        fantasy_draft.FantasyDraftView._draft_tree_context_menu(
            fake_self, evt, FakeTree("", ()))
        check("fantasy: empty click ignored", shown == [])

        # D: unknown item -> silent
        shown.clear()
        fantasy_draft.FantasyDraftView._draft_tree_context_menu(
            fake_self, evt, FakeTree("I999", ("Nobody",)))
        check("fantasy: unknown item ignored", shown == [])
    finally:
        pcm.PlayerContextMenu = real_cls


# ------------------------------------------------------- research
def t_next_owned_pick():
    import windows
    uteam, other = object(), object()
    dp1 = SimpleNamespace(overall_pick=1)
    dp2 = SimpleNamespace(overall_pick=2)
    dp3 = SimpleNamespace(overall_pick=33)
    v = windows.DraftView.__new__(windows.DraftView)
    v.draft_order = [[1, other, dp1], [1, uteam, dp2], [2, uteam, dp3]]
    v.current_pick = 0
    v.app = SimpleNamespace(user_team=uteam)
    check("research: next owned pick found",
          v._next_owned_pick() == (2, 1))
    v.current_pick = 1
    check("research: later owned pick found",
          v._next_owned_pick() == (33, 2))
    v.draft_order = [[1, other, dp1]]
    check("research: none owned -> None", v._next_owned_pick() is None)


def run_headless():
    print("== draft mid-scout: headless logic ==")
    t_quick_scout_creates_report()
    t_quick_scout_existing_report()
    t_quick_scout_no_scouts()
    t_quick_scout_posts_ticker_and_refresh()
    t_quick_scout_no_scout_ticker_note()
    t_quick_scout_take_line()
    t_quick_scout_prefers_amateur()
    t_quick_scout_non_scout_staff_ignored()
    t_menu_labels()
    t_menu_quick_command_calls_quick_scout()
    t_app_resolution()
    t_fantasy_tree_handler()
    t_next_owned_pick()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return not FAIL


# ------------------------------------------------------------------ UI
def drive_picks(view, root, app, n):
    """Synchronously drive n picks (AI steps + user auto-picks)."""
    try:
        if view._ai_after_id:
            view.after_cancel(view._ai_after_id)
    except Exception:
        pass
    view._ai_after_id = None
    view._sim_active = True
    _orig_pace = view._set_pace
    view._set_pace = lambda *a, **k: None
    start = view.current_pick
    guard = 0
    try:
        while (view.current_pick - start < n
               and view.current_pick < len(view.draft_order)
               and guard < n + 500):
            guard += 1
            _r, _t, _dp = view.draft_order[view.current_pick]
            if _t == app.user_team or getattr(_t, 'is_user_team', False):
                view.auto_pick()
            else:
                view._ai_step()
            root.update()
    finally:
        view._set_pace = _orig_pace
        view._sim_active = False
        try:
            if getattr(view, '_ai_after_id', None):
                view.after_cancel(view._ai_after_id)
        except Exception:
            pass
        view._ai_after_id = None
    root.update()
    return view.current_pick - start


def run_ui():
    """Xvfb: build the war room, right-click a prospect row + card,
    screenshot the research strip. Needs a display."""
    import tkinter as tk
    import customtkinter as ctk
    from PIL import ImageGrab
    import main as main_mod
    import windows
    import draft_generator
    import draft_night
    import popup_system
    from game_classes import League, Team, DraftPick

    shot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "qa_shots_draft")
    os.makedirs(shot_dir, exist_ok=True)

    def shot(name):
        path = os.path.join(shot_dir, name)
        ImageGrab.grab().save(path)
        print(f"shot: {path}")
        return path

    league = League("NHL")
    league.season_year = 2029
    league.draft_prospects_year = 2029
    teams = []
    for i in range(4):
        t = Team(f"Club{i}", f"City{i}", "Atlantic", "Eastern")
        t.league_name = "National Hockey League"
        t.salary_cap = 104_000_000
        teams.append(t)
    league.teams = teams
    league.draft_prospects = draft_generator.generate_draft_class(
        40, draft_year=2029)
    _order = []
    for rnd in range(1, 8):
        for t in teams:
            _order.append((rnd, t, DraftPick(
                year=2029, round=rnd, original_team=t.team_name,
                current_team=t.team_name)))
    league.get_draft_order = lambda _y: _order
    league.initialize_all_draft_picks = lambda: None

    # user club gets a real scouting department
    teams[0].staff = [make_scout("UIAce", 18, 17)]
    teams[0].scouting_reports = {}

    class FakeApp:
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
        add_news=lambda s: None, add_news_story=lambda s: None,
        get_settings=lambda: {"draft": {"clock_seconds": 60}},
        open_windows={},
        open_contract_negotiation_window=lambda *a, **k: None,
        update_all_views=lambda: None,
        current_date="2029-06-27",
        tree_maps={},
        scouting_assignments={})
    app.game_manager = SimpleNamespace(trade_history=[],
                                       current_date="2029-06-27")
    # real right-click wiring from main
    app._bind_player_context_menu = types.MethodType(
        main_mod.HockeyManagerGUI._bind_player_context_menu, app)
    app._show_player_context_menu = types.MethodType(
        main_mod.HockeyManagerGUI._show_player_context_menu, app)

    root = ctk.CTk()
    popup_system.register(root)
    root.geometry("1600x900")
    root.update()

    view = windows.DraftView(root, app=app)
    view.pack(fill="both", expand=True)
    root.update()
    root.update_idletasks()
    made = drive_picks(view, root, app, 6)
    check("ui: drove 6 picks (mid-draft state)", made == 6,
          f"drove {made}")
    root.update()
    root.update_idletasks()

    # --- research strip: open the Scout Report tab and refresh
    view._draft_board_tab("Scout Report")
    view._refresh_draft_research()
    root.update()
    root.update_idletasks()
    title = view._research_title.cget("text")
    check("ui: research title names the next owned pick",
          "YOUR NEXT PICK" in title and "#" in title, title)
    rows = view._research_list.get(0, tk.END)
    check("ui: research list populated", len(rows) >= 4,
          f"{len(rows)} rows")
    check("ui: research rows show report status",
          any("unscouted" in r or "your take" in r for r in rows))
    shot("scout_01_research_tab.png")

    # --- right-click the available tree: real menu, quick-scout entry
    recorded_menus = []
    tk.Menu = _REAL_TK_MENU  # undo the headless fake for the UI run
    real_menu_cls = _REAL_TK_MENU

    # Menus need a widget parent; production passes the app (a tk.Tk).
    # The FakeApp isn't a widget, so substitute the test root -- the menu
    # content (labels, quick_scout flag) is what this test asserts.
    _orig_pcm_init = pcm.PlayerContextMenu.__init__

    def _patched_pcm_init(self, parent):
        if not isinstance(parent, tk.Wm):
            parent = root
        _orig_pcm_init(self, parent)

    pcm.PlayerContextMenu.__init__ = _patched_pcm_init

    class RecMenu(real_menu_cls):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._rec_labels = []
            recorded_menus.append(self)

        def add_command(self, cnf=None, **kw):
            self._rec_labels.append(kw.get("label", ""))
            super().add_command(cnf, **kw)

        def add_separator(self, cnf=None, **kw):
            self._rec_labels.append("---")
            super().add_separator(cnf, **kw)

    taken = []
    orig_qs = pcm.PlayerContextMenu._quick_scout_player
    pcm.PlayerContextMenu._quick_scout_player = \
        lambda self, pl: taken.append(pl)  # probe only: don't run scouting
    tk.Menu = RecMenu
    try:
        view._draft_board_tab("Available")
        root.update()
        tree = view.available_tree
        children = tree.get_children()
        check("ui: available tree has rows", len(children) > 0)
        item = children[0]
        bbox = tree.bbox(item)
        check("ui: row bbox visible", bool(bbox))
        x, y = bbox[0] + 5, bbox[1] + bbox[3] // 2
        tree.event_generate("<Button-3>", x=x, y=y)
        root.update()
        root.update_idletasks()
        check("ui: right-click opened a menu", len(recorded_menus) > 0)
        menu = recorded_menus[-1]
        check("ui: quick-scout entry in menu",
              "\u26a1 Quick Scout (war-room take)" in menu._rec_labels,
              str(menu._rec_labels[:4]))
        expected = view._prospect_by_id(item)
        menu.invoke(menu._rec_labels.index(
            "\u26a1 Quick Scout (war-room take)"))
        root.update()
        check("ui: quick scout invoked for the right-clicked prospect",
              taken == [expected])
        menu.unpost()
        shot("scout_02_context_menu.png")

        # --- prospect card right-click
        view._on_available_select.__self__  # bound check
        tree.selection_set(item)
        view._on_available_select()
        root.update()
        card = view.prospect_card
        card.event_generate("<Button-3>", x=10, y=10)
        root.update()
        root.update_idletasks()
        card_menu = recorded_menus[-1]
        check("ui: card right-click opens quick-scout menu",
              "\u26a1 Quick Scout (war-room take)" in card_menu._rec_labels,
              str(card_menu._rec_labels[:4]))
        card_menu.unpost()

        # --- Research button jumps to the Scout Report tab
        view._draft_board_tab("Available")
        root.update()
        view.research_button.invoke()
        root.update()
        check("ui: Research button opens Scout Report tab",
              view._board_tab_frames["Scout Report"].winfo_ismapped())

        # --- research freshness: after 6 picks the strip names only
        # prospects still in the pool (no drafted players).
        view._draft_board_tab("Scout Report")
        root.update()
        pool_ids = {id(pp) for pp in league.draft_prospects}
        stale = [pp.full_name for pp in view._research_players
                 if id(pp) not in pool_ids]
        check("ui: research strip has no drafted prospects",
              not stale, f"stale: {stale[:3]}")
        check("ui: research strip populated",
              len(view._research_players) > 0)
    finally:
        tk.Menu = real_menu_cls
        pcm.PlayerContextMenu.__init__ = _orig_pcm_init
        pcm.PlayerContextMenu._quick_scout_player = orig_qs

    # --- a11y: fonts + clipping on the research strip.
    # Read the CONFIGURED size (CTk converts 10pt -> -10px internally;
    # measuring the pixel-converted internal widget misreads as ~7).
    bad_fonts = []

    def configured_size(w):
        try:
            f = w.cget("font")
        except Exception:
            return None
        try:
            if isinstance(f, (tuple, list)) and len(f) >= 2 \
                    and isinstance(f[1], int):
                return abs(f[1])
            if hasattr(f, "cget"):  # CTkFont object
                return abs(int(f.cget("size")))
        except Exception:
            pass
        return None

    def walk(n):
        for ch in n.winfo_children():
            size = configured_size(ch)
            if isinstance(size, int) and size < 8:
                bad_fonts.append((str(ch), size))
            walk(ch)

    walk(view._board_tab_frames["Scout Report"])
    check("ui: no tiny fonts in research tab", not bad_fonts,
          str(bad_fonts[:3]))
    lst = view._research_list
    check("ui: research list visible",
          lst.winfo_ismapped() and lst.winfo_height() > 40,
          f"h={lst.winfo_height()}")
    rw, rh = root.winfo_width(), root.winfo_height()
    check("ui: window fits 1600x900", rw <= 1600 and rh <= 900,
          f"{rw}x{rh}")
    shot("scout_03_war_room.png")
    root.destroy()

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return not FAIL


if __name__ == "__main__":
    ok = run_ui() if "--ui" in sys.argv else run_headless()
    sys.exit(0 if ok else 1)
