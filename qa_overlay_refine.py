#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_overlay_refine.py -- verify the day-sim toast never blocks crucial UI
and the Game Day Watch/Quick choice is never blocked.

Muck 2026-10-02:
  1. "the simulating screen doesnt cover crucial info" -> small,
     non-modal, bottom-right corner toast (never centered, never grab_set).
  2. "the option is there just getting blocked by the loading maybe" ->
     the toast must not block _ask_game_mode_dialog; the game loop hides
     the toast before the choice and re-shows it after a Quick Sim pick.

Run headless: python3 qa_overlay_refine.py
Widget tests need a display (Xvfb on :99).
"""
import sys
import os
import ast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def main():
    print("== toast is non-modal (source) ==")
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'day_sim_loading.py')) as f:
            toast_src = f.read()
        # No grab_set *call* anywhere (comments may mention it).
        has_grab_call = False
        for line in toast_src.splitlines():
            s = line.strip()
            if s.startswith('#'):
                continue
            if 'grab_set()' in s:
                has_grab_call = True
        check("no grab_set() call in day_sim_loading.py", not has_grab_call)
        check("compact width (300)", "_W = 300" in toast_src)
        check("compact height (108)", "_H = 108" in toast_src)
        check("corner positioning (bottom-right math)",
              "winfo_width()" in toast_src and "- self._MARGIN" in toast_src)
        check("not centered (no // 2 centering)",
              "(parent.winfo_width() // 2)" not in toast_src)
        check("no widget-level Escape binding on toast",
              "win.bind('<Escape>'" not in toast_src
              and 'win.bind("<Escape>"' not in toast_src)
    except Exception as e:
        check(f"source checks ({e})", False)

    print("== game loop hides toast around the choice (source) ==")
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'main.py')) as f:
            main_src = f.read()
        # Find the 'ask' branch of the user-game presentation logic.
        idx = main_src.find("elif mode == 'ask':")
        check("ask branch exists", idx != -1)
        if idx != -1:
            window = main_src[idx:idx + 1400]
            check("toast hidden before _ask_game_mode_dialog",
                  "_update_day_sim_overlay(False)" in window
                  and window.find("_update_day_sim_overlay(False)")
                  < window.find("_ask_game_mode_dialog"))
            check("toast re-shown after Quick Sim pick",
                  '_update_day_sim_overlay(True, "Simulating games...")'
                  in window)
            check("no re-show when Watch Live picked "
                  "(visualizer owns the UI)",
                  "if not use_game_viewer:" in window)
        # The choice dialog itself stays modal & unmissable.
        check("_ask_game_mode_dialog keeps its own grab_set",
              "def _ask_game_mode_dialog" in main_src
              and "dlg.grab_set()" in main_src)
    except Exception as e:
        check(f"game-loop source checks ({e})", False)

    print("== _qol_on_escape guards the toast (source) ==")
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'main.py')) as f:
            main_src2 = f.read()
        idx = main_src2.find("def _qol_on_escape")
        check("_qol_on_escape exists", idx != -1)
        if idx != -1:
            # Grab just this method's body (up to the next def at same indent).
            rest = main_src2[idx:]
            lines = rest.splitlines()
            body = [lines[0]]
            for ln in lines[1:]:
                if ln.startswith("    def ") or ln.startswith("    @"):
                    break
                body.append(ln)
            body_src = "\n".join(body)
            check("checks _day_sim_overlay is_showing",
                  "_day_sim_overlay" in body_src
                  and "is_showing" in body_src)
            check("stops auto-advance on Esc",
                  '_auto_advance_stop("esc")' in body_src)
            check("swallows Esc while toast up (returns 'break')",
                  "return 'break'" in body_src)
    except Exception as e:
        check(f"escape-guard source checks ({e})", False)

    print("== _qol_on_escape logic (fake manager, no display) ==")
    try:
        # Extract the real method bodies via AST and exec them onto a
        # fake manager, so we test the real code, not a copy.
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'main.py')) as f:
            tree = ast.parse(f.read())
        wanted = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if (isinstance(item, ast.FunctionDef)
                            and item.name in ('_qol_on_escape',
                                              '_qol_typing_focus',
                                              '_qol_focus_class')):
                        wanted[item.name] = item
        check("extracted 3 real methods via AST", len(wanted) == 3)
        if len(wanted) == 3:
            mod = ast.Module(body=list(wanted.values()), type_ignores=[])
            ast.fix_missing_locations(mod)
            ns = {}
            exec(compile(mod, '<qol>', 'exec'), ns)

            class FakeOverlay:
                def __init__(self, showing):
                    self._showing = showing
                @property
                def is_showing(self):
                    return self._showing

            class FakeMgr:
                _QOL_TEXT_ENTRY_CLASSES = ('Entry', 'TEntry', 'Text',
                                           'TCombobox', 'Spinbox')
                def __init__(self):
                    self._day_sim_overlay = None
                    self._auto_advance = False
                    self.stopped = []
                    self._focus = None
                def focus_get(self):
                    return self._focus
                def _auto_advance_stop(self, reason=""):
                    self.stopped.append(reason)

            import types
            def bind(mgr):
                for name, fn in ns.items():
                    if name.startswith('_qol_'):
                        setattr(mgr, name,
                                types.MethodType(fn, mgr))
                return mgr

            # Case 1: toast showing, auto-advance on -> Esc stops loop.
            m1 = bind(FakeMgr())
            m1._day_sim_overlay = FakeOverlay(True)
            m1._auto_advance = True
            r1 = m1._qol_on_escape()
            check("Esc stops auto-advance while toast up",
                  m1.stopped == ["esc"] and r1 == 'break')

            # Case 2: toast showing, no auto-advance -> Esc swallowed,
            # overlay NOT destroyed.
            m2 = bind(FakeMgr())
            m2._day_sim_overlay = FakeOverlay(True)
            r2 = m2._qol_on_escape()
            check("Esc swallowed mid-sim (toast survives)",
                  m2.stopped == [] and r2 == 'break'
                  and m2._day_sim_overlay.is_showing)

            # Case 3: no toast -> normal path (no focus -> None).
            m3 = bind(FakeMgr())
            r3 = m3._qol_on_escape()
            check("no toast -> normal Esc path (None, nothing closed)",
                  r3 is None)
    except Exception as e:
        check(f"fake-manager logic test ({e})", False)

    print("== widget tests (needs display) ==")
    display = os.environ.get('DISPLAY')
    if not display:
        print("  SKIP: no DISPLAY (widget tests need Xvfb)")
    else:
        try:
            import tkinter as tk
            from day_sim_loading import DaySimLoadingOverlay

            root = tk.Tk()
            root.geometry("1200x800+100+100")
            root.update_idletasks()

            ov = DaySimLoadingOverlay(root)
            check("toast builds and is showing", ov.is_showing)

            # Size: compact, not the old 380x160.
            try:
                root.update_idletasks()
                w = ov._window.winfo_width()
                h = ov._window.winfo_height()
                check(f"toast compact ({w}x{h} <= 320x140)",
                      w <= 320 and h <= 140)
            except Exception as e:
                check(f"toast compact ({e})", False)

            # Position: bottom-right quadrant, not centered.
            try:
                x = ov._window.winfo_x()
                y = ov._window.winfo_y()
                # Parent at +100+100, 1200x800. Corner ~= (976, 668).
                # Center would be ~= (550, 446).
                check(f"toast bottom-right (x={x}, y={y})",
                      x > 800 and y > 500)
            except Exception as e:
                check(f"toast bottom-right ({e})", False)

            # Non-modal: no grab held by the toast.
            try:
                check("toast holds no grab (non-modal)",
                      root.grab_current() is None)
            except Exception as e:
                check(f"toast holds no grab ({e})", False)

            # The Game Day choice dialog CAN still grab input on top of
            # the toast -- this is the exact scenario from Muck's
            # screenshot that used to break.
            try:
                dlg = tk.Toplevel(root)
                dlg.grab_set()
                root.update_idletasks()
                check("choice dialog can grab while toast is up",
                      root.grab_current() == dlg)
                dlg.grab_release()
                dlg.destroy()
            except Exception as e:
                check(f"choice dialog can grab ({e})", False)

            # Auto mode hint grows the toast slightly.
            try:
                ov.set_auto_mode(True)
                root.update_idletasks()
                h2 = ov._window.winfo_height()
                check("auto hint shows", ov._hint_label is not None)
                ov.set_auto_mode(False)
            except Exception as e:
                check(f"auto mode ({e})", False)

            ov.destroy()
            check("destroy hides toast", not ov.is_showing)
            root.destroy()
        except Exception as e:
            check(f"widget tests ({e})", False)

    print("== never raises on garbage ==")
    try:
        from day_sim_loading import DaySimLoadingOverlay
        ov = DaySimLoadingOverlay(parent=None)  # no display: no-op
        ov.set_status(None)
        ov.set_status("")
        ov.set_auto_mode(True)
        ov.set_auto_mode(False)
        ov.destroy()
        ov.destroy()  # double destroy
        check("garbage input never raises", True)
    except Exception as e:
        check(f"garbage input never raises ({e})", False)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
