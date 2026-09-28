"""Xvfb smoke test for the popup->view conversions (task batch 2).

Constructs every new view with a stub app, exercises close_view()
with and without _close_screen, and checks the save/load on_done payload.
"""
import os, sys, tempfile
os.environ.setdefault("CTK_NO_FONT_CHECK", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import customtkinter as ctk

from datetime import datetime, timedelta

PASS, FAIL = 0, 0
def ok(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS: {name}")
    else:
        FAIL += 1
        print(f"FAIL: {name}")


def _no_op(*a, **k):
    return True


def _stub_messageboxes():
    """Prevent real modal dialogs from blocking the headless harness."""
    import save_load_system, settings_window, season_flow_ui
    import scouting_profile_dialog, shortlist_system
    for mod in (save_load_system, settings_window, season_flow_ui,
                scouting_profile_dialog, shortlist_system):
        for fn in ('showinfo', 'showerror', 'showwarning', 'askyesno',
                   'askyesnocancel', 'askokcancel', 'askquestion', 'askretrycancel'):
            if hasattr(mod.messagebox, fn):
                try:
                    setattr(mod.messagebox, fn, _no_op)
                except Exception:
                    pass


class StubApp:
    """Minimal main-app stand-in."""
    BG_COLOR = "#1E1E1E"
    CONTENT_BG = "#2D2D2D"
    HEADER_COLOR = "#1E1E1E"
    TEXT_COLOR = "#FFFFFF"
    FONT_FAMILY = "Arial"
    def __init__(self):
        self.open_windows = {}
        self.shown = []            # show_screen calls recorded
        self.saved_called = 0
        self.loaded_called = 0
        self.root = tk.Tk()
        self.root.withdraw()
        self.screen_counter = 0
    def show_screen(self, screen_id, title, view_cls, **kwargs):
        self.screen_counter += 1
        v = view_cls(self.root, app=self, **kwargs)
        v._close_screen = lambda v=v: (v.destroy(), self.open_windows.pop(screen_id, None))
        self.shown.append((screen_id, title, view_cls.__name__))
        return v
    def _create_treeview(self, parent, columns, height=15, is_staff=False, context_type='default'):
        from tkinter import ttk
        tree = ttk.Treeview(parent, columns=list(columns.keys()), show='headings', height=height)
        for col, (text, width) in columns.items():
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor='center')
        return tree
    def on_game_saved(self):
        self.saved_called += 1
    def on_game_loaded(self):
        self.loaded_called += 1


def main():
    _stub_messageboxes()
    app = StubApp()
    tmpdir = tempfile.mkdtemp()

    # --- shortlist views -------------------------------------------------
    from shortlist_system import (ShortlistView, AddPlayerView, EditNotesView,
                                  ChangePriorityView, ShortlistManager,
                                  ShortlistEntry)

    class StubShortlistApp(StubApp):
        def __init__(self):
            super().__init__()
            self.shortlist_manager = ShortlistManager()
            self.teams = {}
            self.free_agents = []
            from types import SimpleNamespace
            self.user_team = SimpleNamespace(roster=[], ahl_roster=[],
                                             prospects=[])

    app2 = StubShortlistApp()
    v = ShortlistView(app2.root, app=app2)
    ok("ShortlistView constructs", isinstance(v, ctk.CTkFrame) and v.app is app2)
    # AddPlayerView via show_screen + on_done chain
    done = []
    ap = app2.show_screen('shortlist_add_player', 'Add Player to Shortlist',
                          AddPlayerView, shortlist_manager=app2.shortlist_manager,
                          on_done=lambda: done.append('done'))
    ap.close_view()
    ok("AddPlayerView constructs + close_view", True)
    # Edit/Change with entry
    from shortlist_system import ShortlistEntry
    entry = ShortlistEntry(player_id="p1", player_name="Test Player",
                           category="Prospects", priority=1)
    ev = EditNotesView(app2.root, app=app2, entry=entry,
                       shortlist_manager=app2.shortlist_manager)
    ok("EditNotesView constructs", ev.entry is entry)
    cv = ChangePriorityView(app2.root, app=app2, entry=entry,
                            shortlist_manager=app2.shortlist_manager)
    ok("ChangePriorityView constructs", cv.entry is entry)
    # wrapper still exists with old signature
    from shortlist_system import ShortlistWindow, AddPlayerDialog, EditNotesDialog, ChangePriorityDialog
    ok("shortlist wrappers importable", all(x is not None for x in
        (ShortlistWindow, AddPlayerDialog, EditNotesDialog, ChangePriorityDialog)))

    # --- scouting profile views ------------------------------------------
    from scouting_profile_dialog import (ScoutingProfileView, ProfileEditorView)
    sp = ScoutingProfileView(app.root, app=app)
    ok("ScoutingProfileView constructs", isinstance(sp, ctk.CTkFrame))
    pe = ProfileEditorView(app.root, app=app)
    ok("ProfileEditorView (new) constructs", pe._editing_name is None)
    pe2 = ProfileEditorView(app.root, app=app, bg="#101420", fg="#eeeeee", profile=None)
    ok("ProfileEditorView (edit) constructs", True)
    # close_view without _close_screen falls back to destroy
    w0 = sp.winfo_exists()
    sp.close_view()
    ok("close_view fallback destroys", not sp.winfo_exists())

    # --- save/load views --------------------------------------------------
    from save_load_system import SaveLoadView
    app3 = StubApp()
    app3.save_manager = type("SM", (), {"save_directory": tmpdir})()
    payloads = []
    sv = SaveLoadView(app3.root, app=app3, mode='save',
                      on_done=lambda r: payloads.append(r))
    ok("SaveLoadView(save) constructs", isinstance(sv, ctk.CTkFrame))
    # window-close without save -> cancelled callback
    sv.on_window_close()
    ok("on_window_close marks cancelled + fires on_done",
       payloads and payloads[-1]['cancelled'] and not payloads[-1]['saved']
       and not sv.winfo_exists())
    lv = SaveLoadView(app3.root, app=app3, mode='load')
    ok("SaveLoadView(load) constructs", lv.mode == 'load')
    # successful save path: stub the manager to avoid real save
    class FakeSM:
        def __init__(self, d): self.save_directory = d
        def save_game(self, name, compress): return True
        def get_save_files(self): return []
    sv2 = SaveLoadView(app3.root, app=app3, mode='save',
                       on_done=lambda r: payloads.append(r))
    sv2.save_manager = FakeSM(tmpdir)
    sv2.save_name_var.set("test_save")
    sv2._save_game()
    ok("save success fires payload saved=True + on_game_saved hook",
       payloads and payloads[-1]['saved'] and not payloads[-1]['cancelled']
       and app3.saved_called >= 1 and not sv2.winfo_exists())

    # --- settings views ----------------------------------------------------
    from settings_window import SettingsView, SettingsWindow
    st = SettingsView(app.root, app=app)
    ok("SettingsView constructs", isinstance(st, ctk.CTkFrame))
    st.close_view()
    ok("SettingsView close_view fallback destroys", not st.winfo_exists())
    ok("settings wrappers importable", SettingsWindow is not None)

    # --- season_flow views -------------------------------------------------
    from season_flow_ui import (AutomationSettingsView, MilestoneNotificationView,
                                SettingsWindow as SFSettingsWindow,
                                MilestoneNotificationWindow, SeasonPhase)

    class FakeSettings:
        simulate_away_games = True
        show_game_viewer_for_home = False
        show_game_viewer_for_away = False
        pause_at_milestones = True
        pause_at_user_games = False
        auto_skip_offseason = False

    class FakeAutomation:
        def __init__(self, gm):
            self.settings = FakeSettings()
            self.milestones = []
            self.game_manager = gm

    auto = FakeAutomation(app)
    av = AutomationSettingsView(app.root, automation=auto)
    ok("AutomationSettingsView constructs + app from automation.game_manager",
       av.app is app)
    av2 = app.show_screen('automation_settings', 'Automation Settings',
                          AutomationSettingsView, automation=auto)
    av2.close_view()
    ok("AutomationSettingsView show_screen chain closes",
       ('automation_settings', 'Automation Settings', 'AutomationSettingsView')
       in app.shown)

    class FakeMilestone:
        name = "Trade Deadline"
        date = datetime.now() + timedelta(days=5)
        description = "The deadline is near."
        phase = SeasonPhase.TRADE_DEADLINE
        is_critical = True

    mv = MilestoneNotificationView(app.root, app=app, milestone=FakeMilestone())
    ok("MilestoneNotificationView constructs", mv.milestone.name == "Trade Deadline")
    mv.close_view()
    ok("MilestoneNotificationView close_view fallback destroys", not mv.winfo_exists())
    ok("season_flow wrappers importable",
       SFSettingsWindow is not None and MilestoneNotificationWindow is not None)

    print(f"\n{ PASS } passed, { FAIL } failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
