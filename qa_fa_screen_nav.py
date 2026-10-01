# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Bugs 6/7/8 harness: drive the REAL show_screen/_teardown_screen cache
machinery with real FreeAgencyView and InboxView.

6: advancing from the FA screen must not freeze (update_views on a big FA pool)
7: leaving the FA screen via show_dashboard must restore the dashboard
8: opening the inbox must show the inbox, never free agency
"""
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import customtkinter as ctk

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


class StubPlayer:
    _id = 0

    def __init__(self, n):
        StubPlayer._id += 1
        self.id = StubPlayer._id
        self.full_name = f"FA Player {n:05d}"
        self.age = 27
        self.nationality = "Canada"
        self.salary = 1000000
        self.contract_years = 2
        self.draft_eligible = False
        from game_classes import PlayerPosition
        self.primary_position = PlayerPosition.CENTER
        self.contract = SimpleNamespace(salary=1000000, years=2)

    def overall_rating(self):
        return 75

    def __getattr__(self, name):
        # Nav-machinery test: any stat the tree columns read defaults sanely.
        if name.startswith("__"):
            raise AttributeError(name)
        defaults = {"potential_grade": "B", "age": 27, "height": "6'1\"",
                    "weight": 195, "shoots": "L", "status": "UFA"}
        return defaults.get(name, 50)


class StubInbox:
    messages = []
    unread_count = 0
    def get_urgent_messages(self):
        return []
    def get_unread_messages(self):
        return []
    def get_all_messages(self):
        return []
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: []


import main as main_mod
from windows import FreeAgencyView
from inbox_window import InboxView


class Harness:
    """Plain object borrowing the REAL screen-machinery methods."""
    show_screen = main_mod.HockeyManagerGUI.show_screen
    _teardown_screen = main_mod.HockeyManagerGUI._teardown_screen
    _get_cached_screen = main_mod.HockeyManagerGUI._get_cached_screen
    _refresh_cached_view = main_mod.HockeyManagerGUI._refresh_cached_view
    show_dashboard = main_mod.HockeyManagerGUI.show_dashboard
    _push_screen_history = main_mod.HockeyManagerGUI._push_screen_history
    open_free_agency_window = main_mod.HockeyManagerGUI.open_free_agency_window
    open_inbox_window = main_mod.HockeyManagerGUI.open_inbox_window
    refresh_screen_navbar = lambda self: None
    update_dashboard_data = lambda self: None
    _update_nav_history_buttons = lambda self: None
    _sort_treeview_generic = \
        main_mod.HockeyManagerGUI._sort_treeview_generic \
        if hasattr(main_mod.HockeyManagerGUI, "_sort_treeview_generic") \
        else lambda self, *a, **k: None

    # class-level maps the methods read
    _SCREEN_CACHE_REFRESH = \
        main_mod.HockeyManagerGUI._SCREEN_CACHE_REFRESH
    _SCREEN_CACHE_STATIC_KWARGS = {}

    @property
    def user_team(self):
        return self.game_manager.user_team

    def __getattr__(self, name):
        # Anything the FA/inbox views call that the harness doesn't model
        # (offer sheets, etc.) is irrelevant to the screen-machinery test.
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None

    def __init__(self, root):
        # wire only what show_screen needs
        self.main_container = ctk.CTkFrame(root)
        self.main_container.pack(fill="both", expand=True)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self._dashboard_frame = ctk.CTkFrame(self.main_container)
        self._dashboard_frame.grid(row=1, column=0, sticky="nsew")
        self._dashboard_grid = {"row": 1, "column": 0, "sticky": "nsew"}
        self.open_windows = {}
        self._screen_cache = {}
        self._SCREEN_CACHE_SIZE = 6
        self._current_screen = None
        self._suppress_history = False
        self._screen_history = []
        self._history_index = -1
        self.tree_maps = {}
        gm = SimpleNamespace(
            free_agents=[StubPlayer(i) for i in range(300)],
            fa_staff=[],
            user_team=SimpleNamespace(
                team_name="Test", city="Test",
                roster=[], salary_cap=88000000,
                inbox=StubInbox()),
        )
        gm.league = SimpleNamespace(
            teams=[], free_agent_staff=[], free_agents=gm.free_agents)
        self.game_manager = gm
        self.app = self
        self.league = SimpleNamespace(free_agent_staff=[])


def run():
    root = tk.Tk()
    root.geometry("1400x900")
    app = Harness(root)
    root.update()

    # --- open the FA screen for real ---
    fa = app.open_free_agency_window()
    root.update()
    check("FA screen opened",
          app._current_screen is not None
          and app._current_screen["id"] == "free_agency")
    check("FA holder visible", bool(app._current_screen["holder"].winfo_ismapped())
          if app._current_screen else False)

    # --- bug 7: leave via show_dashboard ---
    t0 = time.time()
    app.show_dashboard()
    root.update()
    dt = time.time() - t0
    check("show_dashboard returns promptly", dt < 5, f"{dt:.1f}s")
    check("current screen cleared", app._current_screen is None)
    check("dashboard restored",
          bool(app._dashboard_frame.winfo_ismapped()))

    # --- bug 8: inbox click must show the inbox, not FA ---
    # (first park FA in the cache to mimic real navigation)
    fa2 = app.open_free_agency_window()
    root.update()
    inbox = app.open_inbox_window()
    root.update()
    cur = app._current_screen
    check("inbox opened as current", cur is not None and cur["id"] == "inbox",
          str(cur["id"]) if cur else "None")
    check("current view is InboxView",
          isinstance(cur["view"], InboxView) if cur else False,
          type(cur["view"]).__name__ if cur else "None")
    check("FA holder parked (not visible)",
          not bool(app._screen_cache.get("free_agency", (None,))[0]
                     .winfo_ismapped())
          if app._screen_cache.get("free_agency") else True)

    # --- bug 6: update_views on the FA view must not freeze ---
    fa3 = app.open_free_agency_window()
    root.update()
    t0 = time.time()
    try:
        fa3.update_views()
        root.update()
        dt = time.time() - t0
        check("FA update_views completes", dt < 20, f"{dt:.1f}s for 300 FAs")
    except Exception as e:
        check("FA update_views completes", False, f"{type(e).__name__}: {e}")


    # --- hardening: a view that dies mid-construction must not strand ---
    class BoomView(ctk.CTkFrame):
        def __init__(self, master, app=None):
            super().__init__(master)
            raise RuntimeError("synthetic construction failure")
    n_before = len(app.main_container.winfo_children())
    try:
        app.show_screen("boom", "Boom", BoomView)
        check("failing view raises", False)
    except RuntimeError:
        check("failing view raises", True)
    root.update()
    n_after = len(app.main_container.winfo_children())
    check("no orphaned holder/navbar", n_after <= n_before,
          f"{n_before} -> {n_after}")
    check("dashboard restored after failure",
          bool(app._dashboard_frame.winfo_ismapped()))
    check("no current screen after failure", app._current_screen is None)

    root.destroy()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    run()
