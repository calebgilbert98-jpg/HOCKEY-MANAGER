# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: visualizer speed UI controls (Play/Pause, 1x/2x/4x, Auto, End).

Verifies the clickable aspects and wiring of the playback controls in
pbp_visual_sim.py:
  - exactly one _set_speed definition (the old duplicate silently overrode
    the auto_pace-aware version, so manual clicks were swallowed by Auto)
  - speed pills exist, are clickable, and drive self.speed
  - manual speed pick always beats Auto pacing
  - active speed pill is visibly dotted; Auto clears the dots
  - Play/Pause label tracks self.playing on both RoundedButton and tk.Button
  - switching speeds never corrupts playback state
  - every new path never raises on garbage input

Run: DISPLAY=:99 python3 qa_speed_controls.py   (Xvfb for widget tests)
"""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  FAIL") + f" {name}"
          + (f" -- {detail}" if detail and not cond else ""))


import pbp_visual_sim as pv
from pbp_visual_sim import PBPVisualSim

# --------------------------------------------------------------------------
# 1. Static: exactly one _set_speed definition
# --------------------------------------------------------------------------
src_all = inspect.getsource(pv)
check("single _set_speed def",
      src_all.count("def _set_speed") == 1,
      f"found {src_all.count('def _set_speed')}")
check("_set_speed disables auto_pace",
      "auto_pace" in inspect.getsource(PBPVisualSim._set_speed))
check("_set_speed refreshes pills",
      "_refresh_speed_btns" in inspect.getsource(PBPVisualSim._set_speed))
check("_refresh_speed_btns exists",
      hasattr(PBPVisualSim, "_refresh_speed_btns"))
check("init tail refreshes play + speed controls",
      "_refresh_play_btn()" in src_all and "_refresh_speed_btns()" in src_all)


# --------------------------------------------------------------------------
# 2. Logic harness (no display): unbound methods on a fake self
# --------------------------------------------------------------------------
class FakeBtn:
    """Mimics both RoundedButton (set_text) and tk.Button (config only)."""
    def __init__(self, text, use_set_text=False):
        self._text = text
        if use_set_text:
            # real tk.Button has NO set_text attr at all
            self.set_text = self._do_set_text

    def _do_set_text(self, t):
        self._text = t

    def cget(self, k):
        assert k == "text"
        return self._text

    def config(self, **kw):
        if "text" in kw:
            self._text = kw["text"]

    def invoke(self):
        self._cmd()

    def bind_cmd(self, cmd):
        self._cmd = cmd


def make_harness():
    h = types.SimpleNamespace()
    h.speed = 1
    h.auto_pace = False
    h.playing = False
    h.speed_btns = {1: FakeBtn("1x"), 2: FakeBtn("2x"), 4: FakeBtn("4x")}
    h.auto_btn = FakeBtn("Auto")
    h.play_btn = FakeBtn("Pause", use_set_text=True)
    h._feed = lambda msg, tag=None, ev=None: None
    # bind the real methods (staticmethod stays unbound)
    for m in ("_set_speed", "_refresh_speed_btns", "_toggle_play",
              "_refresh_play_btn", "_toggle_auto"):
        setattr(h, m, types.MethodType(getattr(PBPVisualSim, m), h))
    h._refresh_toggle_btn = PBPVisualSim._refresh_toggle_btn
    return h


h = make_harness()
h._set_speed(4)
check("set_speed(4) sets speed", h.speed == 4)
check("4x pill dotted", h.speed_btns[4].cget("text").endswith("●"))
check("1x/2x pills undotted",
      not h.speed_btns[1].cget("text").endswith("●")
      and not h.speed_btns[2].cget("text").endswith("●"))

h._set_speed(2)
check("set_speed(2) moves dot", h.speed_btns[2].cget("text").endswith("●")
      and not h.speed_btns[4].cget("text").endswith("●"))

# manual pick beats Auto
h.auto_pace = True
h.auto_btn = FakeBtn("Auto ●")
h._set_speed(2)
check("manual speed kills auto_pace", h.auto_pace is False)
check("auto pill undotted after manual pick",
      not h.auto_btn.cget("text").endswith("●"))
check("manual speed still applies", h.speed == 2)

# play/pause label on RoundedButton-style
h.playing = False
h._refresh_play_btn()
check("label 'Play' when paused", h.play_btn.cget("text") == "Play")
h._toggle_play()
check("toggle flips playing", h.playing is True)
check("label 'Pause' when playing", h.play_btn.cget("text") == "Pause")

# play/pause label on plain tk.Button-style (no set_text)
h2 = make_harness()
h2.play_btn = FakeBtn("Pause", use_set_text=False)
h2.playing = False
h2._refresh_play_btn()
check("tk.Button label 'Play' when paused",
      h2.play_btn.cget("text") == "Play")
h2._toggle_play()
check("tk.Button label 'Pause' when playing",
      h2.play_btn.cget("text") == "Pause")

# auto toggle clears / restores dots
h3 = make_harness()
h3._set_speed(4)
h3._toggle_auto()
check("auto on clears speed dots",
      not any(b.cget("text").endswith("●")
              for b in h3.speed_btns.values()))
check("auto pill dotted", h3.auto_btn.cget("text").endswith("●"))
h3._toggle_auto()
check("auto off re-dots current speed",
      h3.speed_btns[4].cget("text").endswith("●"))

# speed switches don't corrupt playback state
h4 = make_harness()
h4.playhead, h4.cursor, h4.events = 123.5, 42, ["a", "b"]
h4._set_speed(1); h4._set_speed(4); h4._set_speed(2)
check("state intact across speed switches",
      (h4.playhead, h4.cursor, h4.events) == (123.5, 42, ["a", "b"]))
check("final speed honored", h4.speed == 2)

# never raises on garbage
for fn, args in [
    (PBPVisualSim._set_speed, (types.SimpleNamespace(), 2)),
    (PBPVisualSim._refresh_speed_btns, (types.SimpleNamespace(),)),
    (PBPVisualSim._refresh_play_btn, (types.SimpleNamespace(),)),
    (PBPVisualSim._toggle_auto, (types.SimpleNamespace(),)),
]:
    try:
        fn(*args)
        ok = True
    except Exception:
        ok = False
    check(f"never raises: {fn.__name__} on empty self", ok)

# --------------------------------------------------------------------------
# 3. Widget tests under Xvfb: real pills, real clicks
# --------------------------------------------------------------------------
import tkinter as tk

root = tk.Tk()
root.withdraw()
frame = tk.Frame(root)
frame.pack()


class WidgetHarness:
    pass


wh = WidgetHarness()
wh.speed = 1
wh.auto_pace = False
wh._feed = lambda msg, tag=None, ev=None: None
wh._refresh_toggle_btn = PBPVisualSim._refresh_toggle_btn  # staticmethod
wh.speed_btns = {}
# build the pills exactly like _build_widgets does
for label, val in (("1x", 1), ("2x", 2), ("4x", 4)):
    b = PBPVisualSim._pill(wh, frame, label,
                           lambda v=val: PBPVisualSim._set_speed(wh, v), w=38)
    wh.speed_btns[val] = b
wh.auto_btn = FakeBtn("Auto")
wh._set_speed = types.MethodType(PBPVisualSim._set_speed, wh)
wh._refresh_speed_btns = types.MethodType(PBPVisualSim._refresh_speed_btns, wh)

root.update()
check("3 speed pills built", len(wh.speed_btns) == 3)

# click each pill for real -- guards the late-binding closure bug.
# RoundedButton is a Canvas (no invoke()); call its stored command,
# which is exactly what a real click dispatches.
def _click(btn):
    cmd = getattr(btn, "_command", None)
    if callable(cmd):
        cmd()
    else:
        btn.invoke()


for label, val in (("1x", 1), ("2x", 2), ("4x", 4)):
    _click(wh.speed_btns[val])
    root.update()
    check(f"click {label} -> speed {val}", wh.speed == val)

# dot appears on the real widget text
check("real 4x pill shows dot",
      wh.speed_btns[4].cget("text").replace(" ", "").endswith("●")
      or "●" in wh.speed_btns[4].cget("text"))

# manual click while auto on: auto dies, speed applies
wh.auto_pace = True
_click(wh.speed_btns[1])
root.update()
check("widget click kills auto_pace", wh.auto_pace is False)
check("widget click applies speed", wh.speed == 1)

root.destroy()

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
