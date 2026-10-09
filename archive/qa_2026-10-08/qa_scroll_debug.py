#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: scroll wheel auto-detection for unregistered canvases.

Verifies Muck's bug: "scroll wheel did not fix" on start screen and player card.
The player card canvas was never registered with scroll_manager.

Tests:
1. Auto-detection: unregistered Canvas with yscrollcommand is found
2. Player card canvas structure (mocked) scrolls via _on_wheel
3. Non-scrollable canvases (no yscrollcommand) are NOT auto-detected
4. Explicit registration still works (backward compat)
5. _track_enter tracks unregistered scrollable canvases
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = []
failed = []

def check(name, cond):
    (passed if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}: {name}")

print("== scroll_manager auto-detection ==")
import scroll_manager as sm
check("module imports", True)
check("_is_scrollable_canvas exists", hasattr(sm, "_is_scrollable_canvas"))

print("== live tkinter auto-detection (Xvfb) ==")
try:
    import tkinter as tk
    root = tk.Tk()
    sm.install_global_handler(root)

    # UNREGISTERED scrollable canvas (like player card before fix)
    f1 = tk.Frame(root)
    f1.pack()
    c1 = tk.Canvas(f1, width=200, height=200)
    sb1 = tk.Scrollbar(f1, orient="vertical", command=c1.yview)
    inner1 = tk.Frame(c1)
    c1.create_window((0, 0), window=inner1, anchor="nw")
    for j in range(50):
        tk.Label(inner1, text=f"row {j}").pack()
    c1.pack(side="left")
    sb1.pack(side="right", fill="y")
    c1.configure(yscrollcommand=sb1.set)
    # NOTE: NOT calling sm.register_scrollable(c1) -- testing auto-detection
    root.update_idletasks()
    root.update()
    c1.configure(scrollregion=c1.bbox("all"))
    root.update_idletasks()

    # Auto-detection should find it
    check("auto-detects unregistered scrollable canvas", sm._is_scrollable_canvas(c1))

    # _find_scrollable should find it via walk-up from inner label
    inner_label = inner1.winfo_children()[0]
    found = sm._find_scrollable(inner_label, root)
    check("_find_scrollable finds unregistered canvas via walk-up", found is c1)

    # Wheel event should scroll it
    y0 = c1.yview()[0]
    ev = tk.Event()
    ev.widget = inner_label
    ev.delta = -120
    ev.x_root = c1.winfo_rootx() + 50
    ev.y_root = c1.winfo_rooty() + 50
    ev.state = 0
    ev.num = 0
    try:
        ev.type = "38"
    except Exception:
        pass
    sm._on_wheel(ev)
    root.update_idletasks()
    y1 = c1.yview()[0]
    check("wheel scrolls UNREGISTERED canvas (auto-detect)", y1 > y0)

    # Non-scrollable canvas (no yscrollcommand) should NOT be detected
    c2 = tk.Canvas(root, width=100, height=100)
    c2.pack()
    root.update_idletasks()
    check("ignores canvas without scrollbar", not sm._is_scrollable_canvas(c2))

    # Explicit registration still works
    sm.register_scrollable(c2)
    check("explicit registration still works", c2 in sm._registry)

    # _track_enter tracks unregistered scrollable canvas
    sm._last_active = None
    ev_enter = tk.Event()
    ev_enter.widget = c1
    sm._track_enter(ev_enter)
    check("_track_enter tracks unregistered canvas", sm._last_active is c1)

    # Player card structure: canvas with embedded frame (like modern_profile.py)
    f3 = tk.Frame(root)
    f3.pack()
    outer = tk.Frame(f3)
    outer.pack()
    canvas3 = tk.Canvas(outer, highlightthickness=0)
    scrollbar3 = tk.Scrollbar(outer, orient="vertical", command=canvas3.yview)
    main3 = tk.Frame(canvas3)
    main3.bind("<Configure>", lambda e: canvas3.configure(scrollregion=canvas3.bbox("all")))
    canvas3.create_window((0, 0), window=main3, anchor="nw")
    canvas3.configure(yscrollcommand=scrollbar3.set)
    canvas3.pack(side="left", fill="both", expand=True)
    scrollbar3.pack(side="right", fill="y")
    content3 = tk.Frame(main3)
    content3.pack(fill="both", expand=True)
    for j in range(30):
        tk.Label(content3, text=f"player stat {j}").pack()
    root.update_idletasks()
    root.update()
    canvas3.configure(scrollregion=canvas3.bbox("all"))
    root.update_idletasks()

    # Should auto-detect without registration
    check("player-card-style canvas auto-detected", sm._is_scrollable_canvas(canvas3))
    deep_label = content3.winfo_children()[5]
    found3 = sm._find_scrollable(deep_label, root)
    check("finds player-card canvas from deep nested widget", found3 is canvas3)

    y0_3 = canvas3.yview()[0]
    ev3 = tk.Event()
    ev3.widget = deep_label
    ev3.delta = -120
    ev3.x_root = canvas3.winfo_rootx() + 50
    ev3.y_root = canvas3.winfo_rooty() + 50
    ev3.state = 0
    ev3.num = 0
    try:
        ev3.type = "38"
    except Exception:
        pass
    sm._on_wheel(ev3)
    root.update_idletasks()
    y1_3 = canvas3.yview()[0]
    check("wheel scrolls player-card-style canvas", y1_3 > y0_3)

    root.destroy()
except Exception as e:
    import traceback
    traceback.print_exc()
    check(f"live tkinter test ({e})", False)

print("== modern_profile.py registration ==")
try:
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modern_profile.py")).read()
    check("modern_profile imports scroll_manager", "scroll_manager" in src)
    check("modern_profile calls register_scrollable", "register_scrollable(canvas)" in src)
except Exception as e:
    check(f"modern_profile readable ({e})", False)

print()
print(f"{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
