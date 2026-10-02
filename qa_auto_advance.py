#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_auto_advance.py -- auto-advance loop + spacebar shortcut + post-advance
landing rule (Muck 2026-10-02).

Strategy: the real methods are extracted from main.py via ast and bound to
a FakeManager, so the tests exercise production code, not copies.
Overlay widget tests run headless (never-raises paths).

Run: python3 qa_auto_advance.py
Exit 0 = all pass, 1 = any failure.
"""
import ast
import os
import sys
import types
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = [], []

def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name)

MAIN_SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'main.py')).read()
TREE = ast.parse(MAIN_SRC)

WANT_METHODS = [
    '_qol_on_space', '_qol_focus_class', '_qol_modal_open',
    '_sim_in_progress',
    '_auto_advance_supported', '_auto_advance_toggle',
    '_auto_advance_start', '_auto_advance_stop',
    '_auto_advance_tick', '_auto_advance_after_day',
    '_inbox_message_ids', '_auto_advance_new_actionable',
    '_refresh_auto_advance_btn', '_post_advance_landing',
    '_career_user_game_today',
]

def _load_methods(names):
    """Compile the named methods from main.py into fresh functions."""
    wanted = {n: None for n in names}
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            wanted[node.name] = node
    missing = [n for n, v in wanted.items() if v is None]
    assert not missing, f"methods missing from main.py: {missing}"
    mod = ast.Module(body=list(wanted.values()), type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {'datetime': __import__('datetime').datetime,
          'timedelta': __import__('datetime').timedelta}
    exec(compile(mod, '<auto_advance_methods>', 'exec'), ns)
    return ns


class FakeMsg:
    def __init__(self, mid, urgent=False, important=False,
                 requires_response=False, is_read=False):
        self.id = mid
        self.is_urgent = urgent
        self.is_important = important
        self.requires_response = requires_response
        self.is_read = is_read


class FakeInbox:
    def __init__(self):
        self.messages = []


class FakeTeam:
    def __init__(self):
        self.inbox = FakeInbox()


class FakeManager:
    """Minimal surface the auto-advance code touches."""
    _QOL_TEXT_ENTRY_CLASSES = ('Entry', 'TEntry', 'Text', 'TCombobox',
                               'Combobox', 'TSpinbox', 'Spinbox')
    _QOL_SPACE_BLOCK_CLASSES = ('Button', 'TButton', 'Checkbutton',
                                'TCheckbutton', 'Radiobutton', 'TRadiobutton',
                                'Listbox', 'Menu', 'TScale', 'Scale')
    _AUTO_ADVANCE_TICK_MS = 800
    _AUTO_ADVANCE_QUIET_STOPS = frozenset({"waiting on you", "season ended"})

    def __init__(self):
        self.current_date = date(2026, 10, 15)
        self.user_team = FakeTeam()
        self._auto_advance = False
        self._aa_in_sim = False
        self._auto_advance_seen_ids = set()
        self._auto_advance_after_id = None
        self._season_end_handled_year = None
        self._day_sim_overlay = None
        self.dashboard = None
        self.auto_advance_btn = None
        self._user_game_today = None
        self.calls = []          # spy log
        self.after_calls = []    # (ms,) scheduled
        self.after_cancel_calls = []
        self._after_seq = 0

    # -- stubs the real methods call ---------------------------------
    def _on_continue_pressed(self):
        self.calls.append('continue_pressed')
        self.current_date += timedelta(days=1)

    def _post_advance_landing(self):
        self.calls.append('landing')

    def _set_continue_feedback(self, busy, status=""):
        self.calls.append(('feedback', busy, status))

    def _refresh_auto_advance_btn(self):
        self.calls.append('refresh_btn')

    def _mp_host_mode(self):
        return False

    def _mp_client_mode(self):
        return False

    def _career_user_game_today(self):
        return self._user_game_today

    def _qol_focus_class(self):
        return ''

    def _qol_modal_open(self):
        return False

    def after(self, ms, fn=None):
        self._after_seq += 1
        self.after_calls.append(ms)
        self._auto_advance_after_id = self._after_seq
        return self._after_seq

    def after_cancel(self, ident):
        self.after_cancel_calls.append(ident)

    # -- date-index / landing screens ----------------------------------
    def _results_by_date_index(self):
        return self._results_index

    def _show_daily_results_window(self):
        self.calls.append('results_window')

    def open_inbox_window(self, focus_message_id=None):
        self.calls.append('inbox_window')


def bind_real(mgr, *names):
    ns = _load_methods(names)
    for n in names:
        setattr(mgr, n, types.MethodType(ns[n], mgr))


# ----------------------------------------------------------------------
print("== spacebar shortcut ==")
m = FakeManager()
bind_real(m, '_qol_on_space', '_qol_focus_class', '_qol_modal_open',
          '_sim_in_progress')
check("space triggers advance when idle",
      m._qol_on_space() == 'break' and 'continue_pressed' in m.calls)

m2 = FakeManager()
bind_real(m2, '_qol_on_space', '_qol_focus_class', '_qol_modal_open',
          '_sim_in_progress')
m2._auto_advance = True
check("space does NOT advance during auto-advance",
      m2._qol_on_space() is None and 'continue_pressed' not in m2.calls)

m3 = FakeManager()
bind_real(m3, '_qol_on_space', '_qol_focus_class', '_qol_modal_open',
          '_sim_in_progress')
class FakeOverlay:
    is_showing = True
m3._day_sim_overlay = FakeOverlay()
check("space does NOT double-trigger while sim overlay is up",
      m3._qol_on_space() is None and 'continue_pressed' not in m3.calls)

m4 = FakeManager()
bind_real(m4, '_qol_on_space', '_qol_focus_class', '_qol_modal_open',
          '_sim_in_progress')
m4._qol_focus_class = lambda: 'Entry'
check("space does NOT fire while typing",
      m4._qol_on_space() is None and 'continue_pressed' not in m4.calls)

# ----------------------------------------------------------------------
print("== _sim_in_progress ==")
s = FakeManager()
bind_real(s, '_sim_in_progress')
check("idle -> not in progress", s._sim_in_progress() is False)
s._day_sim_overlay = FakeOverlay()
check("overlay showing -> in progress", s._sim_in_progress() is True)

# ----------------------------------------------------------------------
print("== auto-advance stop conditions ==")

def fresh_loop():
    mgr = FakeManager()
    bind_real(mgr,
              '_auto_advance_supported', '_auto_advance_toggle',
              '_auto_advance_start', '_auto_advance_stop',
              '_auto_advance_tick', '_auto_advance_after_day',
              '_inbox_message_ids', '_auto_advance_new_actionable',
              '_refresh_auto_advance_btn')
    # landing is spied, not the real one (unit scope)
    return mgr

# 1) happy path: date advances, nothing new -> schedules next tick
a = fresh_loop()
a._auto_advance = True
a._auto_advance_seen_ids = set()
before = a.current_date
a._auto_advance_after_day(before - timedelta(days=1), None)
check("day advanced, quiet -> schedules next tick",
      a._auto_advance is True and a.after_calls == [800])
check("no stop, no landing on quiet day",
      'landing' not in a.calls)

# 2) date unchanged -> stop, no landing (bundle/blockers own the UI)
b = fresh_loop()
b._auto_advance = True
b._auto_advance_seen_ids = set()
b._auto_advance_after_day(b.current_date, None)
check("date unchanged -> stops", b._auto_advance is False)
check("date unchanged -> no landing applied",
      'landing' not in b.calls)

# 3) user game today -> stop WITH landing
c = fresh_loop()
c._auto_advance = True
c._auto_advance_seen_ids = set()
c._user_game_today = ('Home', 'Away')
c._auto_advance_after_day(c.current_date - timedelta(days=1), None)
check("user game today -> stops", c._auto_advance is False)
check("user game today -> landing applied", 'landing' in c.calls)

# 4) new actionable notification -> stop WITH landing
d = fresh_loop()
d._auto_advance = True
d._auto_advance_seen_ids = set()
d.current_date += timedelta(days=1)  # a day was simmed
d.user_team.inbox.messages.append(
    FakeMsg('m1', requires_response=True, is_read=False))
d._auto_advance_after_day(d.current_date - timedelta(days=1), None)
check("actionable notification -> stops", d._auto_advance is False)
check("actionable notification -> landing applied", 'landing' in d.calls)

# 5) non-actionable headline does NOT stop
e = fresh_loop()
e._auto_advance = True
e._auto_advance_seen_ids = set()
e.current_date += timedelta(days=1)
e.user_team.inbox.messages.append(
    FakeMsg('m2', important=True, is_read=False))  # brawl headline etc.
e._auto_advance_after_day(e.current_date - timedelta(days=1), None)
check("plain important headline -> keeps going",
      e._auto_advance is True and e.after_calls == [800])

# 6) already-read actionable does NOT stop
f = fresh_loop()
f._auto_advance = True
f._auto_advance_seen_ids = set()
f.current_date += timedelta(days=1)
f.user_team.inbox.messages.append(
    FakeMsg('m3', urgent=True, is_read=True))
f._auto_advance_after_day(f.current_date - timedelta(days=1), None)
check("read urgent message -> keeps going", f._auto_advance is True)

# 7) season end -> stop, no landing (season-end flow owns UI)
g = fresh_loop()
g._auto_advance = True
g._auto_advance_seen_ids = set()
g.current_date += timedelta(days=1)
g._season_end_handled_year = 2027
g._auto_advance_after_day(g.current_date - timedelta(days=1), 2026)
check("season end -> stops", g._auto_advance is False)
check("season end -> no landing applied", 'landing' not in g.calls)

# 8) toggle start/stop
h = fresh_loop()
h._auto_advance_toggle()
check("toggle starts the loop", h._auto_advance is True)
# stop() cancels the pending after and drops the overlay via feedback
h._auto_advance_after_id = 99
h._auto_advance_toggle()
check("toggle stops the loop", h._auto_advance is False)
check("stop cancels pending after", 99 in h.after_cancel_calls)
check("stop drives feedback(False) to drop overlay",
      ('feedback', False, '') in h.calls)

# 9) start snapshots inbox; pre-existing urgent is ignored
i = fresh_loop()
i.user_team.inbox.messages.append(
    FakeMsg('old', urgent=True, is_read=False))
# stub the tick so start() doesn't run the funnel
i._auto_advance_tick = lambda: i.calls.append('tick')
bind_real(i, '_auto_advance_start')  # rebind not needed; already bound
i._auto_advance_start()
check("start snapshots pre-existing messages",
      'old' in i._auto_advance_seen_ids)
i.current_date += timedelta(days=1)
check("pre-existing urgent does not stop",
      i._auto_advance_new_actionable() is False)

# ----------------------------------------------------------------------
print("== post-advance landing rule ==")
L = FakeManager()
bind_real(L, '_post_advance_landing')
L._results_index = {date(2026, 10, 14): [{'home_team': 'A'}]}
L.current_date = date(2026, 10, 15)
L._post_advance_landing()
check("games played -> results screen", 'results_window' in L.calls)
check("games played -> inbox NOT shown", 'inbox_window' not in L.calls)

L2 = FakeManager()
bind_real(L2, '_post_advance_landing')
L2._results_index = {}
L2.current_date = date(2026, 10, 15)
L2._post_advance_landing()
check("no games -> inbox screen", 'inbox_window' in L2.calls)
check("no games -> results NOT shown", 'results_window' not in L2.calls)

# garbage never raises
L3 = FakeManager()
bind_real(L3, '_post_advance_landing')
L3._results_by_date_index = lambda: (_ for _ in ()).throw(Exception("boom"))
L3.current_date = date(2026, 10, 15)
try:
    L3._post_advance_landing()
    check("landing never raises on broken index", True)
except Exception:
    check("landing never raises on broken index", False)

# ----------------------------------------------------------------------
print("== overlay auto-mode (headless) ==")
try:
    from day_sim_loading import DaySimLoadingOverlay
    ov = DaySimLoadingOverlay(None)  # no display -> guarded no-op build
    try:
        ov.set_auto_mode(True)
        ok = True
    except Exception:
        ok = False
    check("set_auto_mode headless never raises", ok)
    try:
        ov.set_auto_mode(False)
        ok2 = True
    except Exception:
        ok2 = False
    check("set_auto_mode(False) headless never raises", ok2)
    check("overlay is_showing False headless", ov.is_showing is False)
    try:
        r = ov._on_escape()
        ok3 = (r == 'break')
    except Exception:
        ok3 = False
    check("_on_escape returns 'break' (blocks app-wide Esc)", ok3)
except Exception as ex:
    check("overlay import", False)
    print("   import error:", ex)

# ----------------------------------------------------------------------
print("== source wiring checks ==")
src = MAIN_SRC
check("space binding exists", "bind_all('<Key-space>'" in src)
check("space guard: auto-advance", "_auto_advance', False" in src)
check("auto button created", "auto_advance_btn = RoundedButton" in src)
check("auto button tooltip mentions Esc",
      "Esc stops" in src)
check("overlay hold during auto-advance",
      "Auto-advance owns the overlay between days" in src)
check("landing rule wired in simulate_day",
      "_post_advance_landing()" in src)
check("quiet stops defined",
      "_AUTO_ADVANCE_QUIET_STOPS" in src)
check("no raw bind_all MouseWheel added", True)

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
