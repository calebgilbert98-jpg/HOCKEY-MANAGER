#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: scroll wheel always routes to the visible scrollable widget.

Verifies the scroll_manager fix for Muck's bug:
"your windows scroll wheel doesnt scroll the screen in front of you,
 it should always sync to the user facing screen"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = []
failed = []


def check(name, cond):
    (passed if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}: {name}")


print("== scroll_manager module ==")
try:
    import scroll_manager as sm
    check("module imports", True)
    check("register_scrollable exists", hasattr(sm, "register_scrollable"))
    check("install_global_handler exists", hasattr(sm, "install_global_handler"))
    check("unregister_scrollable exists", hasattr(sm, "unregister_scrollable"))
except Exception as e:
    check(f"module imports ({e})", False)
    sm = None

print("== no bind_all MouseWheel left in converted files ==")
for fname, allowed in [
    ("ui_components.py", 0),
    ("dashboard_home.py", 0),
    ("settings_window.py", 0),
    ("main.py", 0),  # install_global_handler uses bind_all internally, not a raw string here
]:
    try:
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)).read()
        # Count raw bind_all("<MouseWheel>" NOT inside scroll_manager.py
        import re
        hits = re.findall(r'bind_all\(\s*["\']<MouseWheel>["\']', src)
        # main.py: install_global_handler(self) call is fine; raw bind_all should be gone
        check(f"{fname}: no raw bind_all MouseWheel ({len(hits)} found)", len(hits) == allowed)
    except Exception as e:
        check(f"{fname} readable ({e})", False)

print("== scroll_manager referenced in converted files ==")
for fname in ["ui_components.py", "dashboard_home.py", "settings_window.py", "main.py"]:
    try:
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)).read()
        check(f"{fname}: uses scroll_manager", "scroll_manager" in src)
    except Exception as e:
        check(f"{fname} readable ({e})", False)

print("== registry behavior (no display) ==")
if sm is not None:
    class FakeCanvas:
        pass
    c1, c2 = FakeCanvas(), FakeCanvas()
    try:
        sm.register_scrollable(c1)
        sm.register_scrollable(c2)
        check("register two canvases", c1 in sm._registry and c2 in sm._registry)
        sm.register_scrollable(c1)  # idempotent
        check("re-register idempotent", c1 in sm._registry)
        sm.unregister_scrollable(c1)
        check("unregister works", c1 not in sm._registry and c2 in sm._registry)
    except Exception as e:
        check(f"registry ops ({e})", False)

    # never-raises on garbage
    for bad in [None, 0, "x", object()]:
        try:
            sm.register_scrollable(bad)
            sm.unregister_scrollable(bad)
            ok = True
        except Exception:
            ok = False
        check(f"register/unregister garbage {type(bad).__name__} never raises", ok)

print("== live tkinter routing (Xvfb) ==")
try:
    import tkinter as tk
    root = tk.Tk()
    # NOTE: do NOT withdraw -- winfo_containing needs a mapped window.
    # Xvfb provides the display.
    sm.install_global_handler(root)
    sm.install_global_handler(root)  # idempotent

    # Two scrollable canvases, like two screens.
    frames = []
    canvases = []
    for i in range(2):
        f = tk.Frame(root)
        f.pack()
        c = tk.Canvas(f, width=200, height=200)
        sb = tk.Scrollbar(f, orient="vertical", command=c.yview)
        inner = tk.Frame(c)
        c.create_window((0, 0), window=inner, anchor="nw")
        for j in range(50):
            tk.Label(inner, text=f"row {j}").pack()
        c.pack(side="left")
        sb.pack(side="right", fill="y")
        c.configure(yscrollcommand=sb.set)
        sm.register_scrollable(c)
        frames.append(f)
        canvases.append(c)
    root.update_idletasks()
    root.update()
    # Set scrollregion AFTER layout so there is actually something to scroll.
    for c in canvases:
        c.configure(scrollregion=c.bbox("all"))
    root.update_idletasks()

    # Simulate wheel over canvas 2 (the "screen in front of you").
    c2 = canvases[1]
    c2.update_idletasks()
    x = c2.winfo_rootx() + 50
    y = c2.winfo_rooty() + 50

    y0_c1 = canvases[0].yview()[0]
    y0_c2 = c2.yview()[0]

    # Build a synthetic wheel event routed through the global handler.
    ev = tk.Event()
    ev.widget = c2
    ev.delta = -120  # scroll down
    ev.x_root = x
    ev.y_root = y
    ev.state = 0
    ev.num = 0
    # fake .type as string-like; our handler is defensive
    try:
        ev.type = "38"  # not Button-4/5
    except Exception:
        pass
    sm._on_wheel(ev)
    root.update_idletasks()

    y1_c1 = canvases[0].yview()[0]
    y1_c2 = c2.yview()[0]
    check("wheel over canvas2 scrolls canvas2", y1_c2 > y0_c2)
    check("wheel over canvas2 does NOT scroll canvas1", abs(y1_c1 - y0_c1) < 1e-9)

    # Dedup: canvas with its own widget-level binding should not double-scroll.
    c3f = tk.Frame(root)
    c3f.pack()
    c3 = tk.Canvas(c3f, width=200, height=200)
    inner3 = tk.Frame(c3)
    c3.create_window((0, 0), window=inner3, anchor="nw")
    for j in range(50):
        tk.Label(inner3, text=f"r{j}").pack()
    c3.pack()
    root.update_idletasks()
    root.update()
    c3.configure(scrollregion=c3.bbox("all"))
    sm.register_scrollable(c3)
    scroll_count = [0]
    orig_yview_scroll = c3.yview_scroll

    def counting_scroll(*a, **k):
        scroll_count[0] += 1
        return orig_yview_scroll(*a, **k)
    c3.yview_scroll = counting_scroll
    # widget-level binding (like windows.py / fantasy_draft.py pattern)
    c3.bind("<MouseWheel>", lambda e: counting_scroll(int(-1 * (e.delta / 120)), "units"))
    root.update_idletasks()
    root.update()
    # Simulate: widget-level binding fires first (tkinter order), then global handler.
    ev3 = tk.Event()
    ev3.widget = c3
    ev3.delta = -120
    ev3.x_root = c3.winfo_rootx() + 50
    ev3.y_root = c3.winfo_rooty() + 50
    ev3.state = 0
    ev3.num = 0
    try:
        ev3.type = "38"
    except Exception:
        pass
    # widget-level fires:
    c3.event_generate("<MouseWheel>", delta=-120, x=50, y=50)
    root.update_idletasks()
    n_after_widget = scroll_count[0]
    # global handler should detect the own-binding and skip:
    sm._on_wheel(ev3)
    root.update_idletasks()
    check("widget-level binding scrolled once", n_after_widget >= 1)
    check("global handler dedups (no double scroll)", scroll_count[0] == n_after_widget)

    # Linux Button-4/5 path never raises
    for num in (4, 5):
        evb = tk.Event()
        evb.widget = c2
        evb.num = num
        evb.delta = 0
        evb.x_root = x
        evb.y_root = y
        evb.state = 0
        try:
            evb.type = str(num)
        except Exception:
            pass
        try:
            sm._on_wheel(evb)
            ok = True
        except Exception:
            ok = False
        check(f"Button-{num} never raises", ok)

    # garbage event never raises
    try:
        sm._on_wheel(object())
        ok = True
    except Exception:
        ok = False
    check("garbage event never raises", ok)

    root.destroy()
except Exception as e:
    import traceback
    traceback.print_exc()
    check(f"live tkinter test ({e})", False)

print()
print(f"{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
