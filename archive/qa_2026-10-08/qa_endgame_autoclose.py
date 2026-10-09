#!/usr/bin/env python3
"""QA for End Game auto-close button (Muck 2026-10-02).

Verifies:
1. _on_end_game method exists and never raises (even with no game state)
2. _end_game_btn attribute is initialized
3. _complete_done flag is initialized
4. game_end event code path shows the button (source check)
5. on_complete fires synchronously if user clicks before the 500ms deferred call
6. _on_end_game calls _on_close (window actually closes)
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "pbp_visual_sim.py")
src = open(SRC).read()

passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")


print("== source checks ==")
check("_on_end_game method defined", "def _on_end_game(self)" in src)
check("_end_game_btn initialized in __init__",
      "self._end_game_btn = None" in src)
check("_complete_done initialized in __init__",
      "self._complete_done = False" in src)
check("button created with _pill", '"End Game"' in src)
check("button hidden until game_end", "pack_forget()" in src)
check("button shown on game_end",
      re.search(r'elif et == "game_end".*?_end_game_btn.*?\.pack\(side="left"',
                src, re.DOTALL) is not None)
check("_complete_done set when callback runs",
      "_complete_done = True" in src)
check("_on_end_game guarantees on_complete before close",
      re.search(r"def _on_end_game.*?_complete_done.*?_on_close",
                src, re.DOTALL) is not None)
check("never-raises guard on _on_end_game",
      re.search(r"def _on_end_game.*?except Exception",
                src, re.DOTALL) is not None)

print("== behavioral checks (no tkinter needed) ==")


class FakeBtn:
    def __init__(self):
        self.packed = False
        self.forgotten = False

    def pack(self, **kw):
        self.packed = True

    def pack_forget(self):
        self.forgotten = True


class FakeWin:
    """Minimal stand-in exercising _on_end_game logic without tkinter."""
    def __init__(self):
        self._complete_done = False
        self._closed = False
        self.cb_calls = []
        self.on_complete = lambda sim: self.cb_calls.append(sim)
        self.sim = object()
        self._end_game_btn = FakeBtn()

    def _on_close(self):
        self._closed = True


# Bind the real method source onto the fake (logic-only test)
import types
ns = {}
# Extract _on_end_game source and exec it in isolation
m = re.search(r"(    def _on_end_game\(self\):.*?)(?=\n    def _on_close)",
              src, re.DOTALL)
assert m, "could not extract _on_end_game"
exec("class _T:\n" + m.group(1), ns)
_on_end_game = ns["_T"]._on_end_game

# Case 1: on_complete not yet run -> fires synchronously, then closes
w = FakeWin()
_on_end_game(w)
check("fires on_complete synchronously when not done", len(w.cb_calls) == 1)
check("marks _complete_done", w._complete_done is True)
check("closes the window", w._closed is True)

# Case 2: on_complete already ran -> does NOT fire again, still closes
w2 = FakeWin()
w2._complete_done = True
_on_end_game(w2)
check("does not double-fire on_complete", len(w2.cb_calls) == 0)
check("still closes when already done", w2._closed is True)

# Case 3: no on_complete callback at all -> never raises, still closes
w3 = FakeWin()
w3.on_complete = None
_on_end_game(w3)
check("never raises with on_complete=None", w3._closed is True)

# Case 4: callback itself raises -> swallowed, still closes
w4 = FakeWin()


def _boom(sim):
    raise RuntimeError("boom")


w4.on_complete = _boom
_on_end_game(w4)
check("never raises when callback raises", w4._closed is True)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
