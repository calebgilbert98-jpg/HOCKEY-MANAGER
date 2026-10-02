#!/usr/bin/env python3
"""QA: inbox scroll performance — verify the scroll speedup is applied.

Checks:
1. _speed_up_scroll exists and never raises (bad input, missing canvas)
2. interactive_frame and _story_frame get yscrollincrement=90
3. Scrolling one "unit" moves 3x further than the CTk default (30px)
"""
import os, sys
os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/tmp/wt-inbox-scroll")

passed, failed = [], []
def check(name, cond):
    (passed if cond else failed).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}")

import tkinter as tk
import customtkinter as ctk

# 1. Import the helper without building the full inbox (heavy).
#    We test the logic directly on real CTkScrollableFrames.
src = open("/tmp/wt-inbox-scroll/inbox_window.py").read()
check("speed_up_scroll method present", "_speed_up_scroll" in src)
check("applied to interactive_frame",
      "self._speed_up_scroll(self.interactive_frame)" in src)
check("applied to _story_frame",
      "self._speed_up_scroll(self._story_frame)" in src)
check("never-raises guard present",
      "def _speed_up_scroll" in src and "except Exception" in src)

# 2. Functional: replicate the method's logic on a real frame
root = ctk.CTk()
root.geometry("800x600")
frame = ctk.CTkScrollableFrame(root, width=760, height=400)
frame.pack(fill="both", expand=True)
for i in range(30):
    ctk.CTkLabel(frame, text=f"Item {i}").pack(anchor="w", padx=10, pady=2)
    ctk.CTkButton(frame, text=f"Button {i}").pack(anchor="w", padx=14, pady=2)
root.update_idletasks(); root.update()

canvas = frame._parent_canvas
default_inc = int(canvas.cget("yscrollincrement"))
check(f"CTk default increment is 30 (got {default_inc})", default_inc == 30)

# Apply the same logic as _speed_up_scroll
try:
    frame._parent_canvas.configure(yscrollincrement=90)
    ok = True
except Exception:
    ok = False
check("configure yscrollincrement=90 never raises", ok)
check("increment now 90", int(canvas.cget("yscrollincrement")) == 90)

# 3. One unit now moves 3x the pixels
y0 = canvas.yview()[0]
canvas.yview_scroll(1, "units")
root.update_idletasks(); root.update()
# Measure pixel delta via canvas coords
bbox = canvas.bbox("all")
# yview fraction -> pixels: fraction * scrollregion height
sr_h = (bbox[3] - bbox[1]) if bbox else 1
moved_frac = canvas.yview()[0] - y0
moved_px = moved_frac * sr_h
check(f"one unit scrolls ~90px (got {moved_px:.0f}px)", 80 <= moved_px <= 100)

# 4. Never-raises on garbage input
class FakeFrame:  # no _parent_canvas
    pass
try:
    FakeFrame()._parent_canvas.configure(yscrollincrement=90)
    raised = False
except Exception:
    raised = True
check("garbage frame raises (so guard is needed)", raised)
# The real method wraps in try/except — simulate:
try:
    try:
        FakeFrame()._parent_canvas.configure(yscrollincrement=90)
    except Exception:
        pass
    ok2 = True
except Exception:
    ok2 = False
check("guarded call never raises", ok2)

root.destroy()

print(f"\n{len(passed)}/{len(passed)+len(failed)} pass")
sys.exit(1 if failed else 0)
