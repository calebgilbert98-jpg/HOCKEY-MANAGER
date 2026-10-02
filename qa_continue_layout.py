"""qa_continue_layout.py - Verify the big centered Advance ("Next Day") button
never overlaps, obscures, or pushes out any menu group in the reorganized
menu bar.

Builds the REAL _create_enhanced_menu_bar (extracted from main.py via ast,
bound to a fake manager) under Xvfb at several window widths and asserts:
  WIDE (>= content fits):
    1. No pixel overlap between the Advance button and any nav pill/dropdown.
    2. The Advance button is centered on the WINDOW (not on an oversized grid).
    3. Every nav pill / dropdown button is fully inside the window.
  NARROW (< content fits):
    4. The button drops below the pills row -- still no overlap.
    5. Every pill stays fully inside the window (nothing pushed off-screen).
"""
import ast
import datetime
import os
import sys
import types

WT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WT)

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from ctk_theme import init_ctk_theme, BORDER
from tooltip import create_tooltip
from event_day_hubs import is_draft_day, is_free_agency_day

METHODS = [
    "_create_enhanced_menu_bar",
    "_create_nav_pill",
    "_create_dropdown_menu",
    "refresh_next_day_button",
    "update_inbox_notification",
    "_get_inbox_button_text",
    "_nav_back",
    "_nav_forward",
    "get_continue_state",
    "is_trade_deadline_day",
    "_mp_host_mode",
    "_mp_client_mode",
]
MODULE_FUNCS = ["_qol_add_tooltip"]


def load_real_methods():
    with open(os.path.join(WT, "main.py"), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    ns = {
        "tk": tk, "ttk": __import__("tkinter.ttk", fromlist=["x"]),
        "ctk": ctk, "messagebox": messagebox,
        "init_ctk_theme": init_ctk_theme, "BORDER": BORDER,
        "create_tooltip": create_tooltip,
        "is_draft_day": is_draft_day,
        "is_free_agency_day": is_free_agency_day,
    }
    cls_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "HockeyManagerGUI":
            cls_node = node
            break
    if cls_node is None:
        raise RuntimeError("HockeyManagerGUI class not found in main.py")
    found = {}
    for node in cls_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in METHODS:
            found[node.name] = node
    missing = [m for m in METHODS if m not in found]
    if missing:
        raise RuntimeError(f"methods not found: {missing}")
    mod = ast.Module(body=[], type_ignores=[])
    for name in METHODS:
        mod.body.append(found[name])
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in MODULE_FUNCS:
            mod.body.append(node)
    ast.fix_missing_locations(mod)
    code = compile(mod, "main_methods.py", "exec")
    exec(code, ns)
    return ns


class FakeManager:
    """Minimal stand-in with the attributes the menu-bar builder needs."""

    def __init__(self, root):
        self.master = root
        self.ACCENT_COLOR = "#ff6b1a"
        self.FONT_FAMILY = "Helvetica"
        self.current_date = datetime.date(2026, 9, 27)
        self._screen_history = []
        self._history_index = -1

    def __getattr__(self, name):
        if name.startswith("open_") or name in (
            "_on_continue_pressed", "toggle_season_flow_panel",
        ):
            return lambda *a, **k: None
        raise AttributeError(name)


def rect_of(w):
    return (
        w.winfo_rootx(), w.winfo_rooty(),
        w.winfo_rootx() + w.winfo_width(),
        w.winfo_rooty() + w.winfo_height(),
    )


def overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def inside_window(r, win_w, win_h):
    return r[0] >= 0 and r[1] >= 0 and r[2] <= win_w and r[3] <= win_h


def label_of(w):
    try:
        return w.cget("text")
    except Exception:
        return "?"


def check_width(ns, root, width):
    errors = []
    host = tk.Frame(root, bg="#0e0e11")
    host.pack(fill="both", expand=True)
    # Mirror the real app: the nav container stretches to the full width
    # (main_container column 0 has weight=1 there).
    host.grid_columnconfigure(0, weight=1)
    mgr = FakeManager(root)
    for name in METHODS + MODULE_FUNCS:
        setattr(mgr, name, types.MethodType(ns[name], mgr) if name in METHODS else ns[name])
    root.geometry(f"{width}x300+0+0")
    root.update_idletasks()
    root.update()
    mgr._create_enhanced_menu_bar(host)
    root.update_idletasks()
    root.update()
    # Let the after_idle layout pass run.
    root.update_idletasks()
    root.update()

    btn = getattr(mgr, "_next_day_btn", None)
    if btn is None or not btn.winfo_exists():
        host.destroy()
        return [f"{width}px: Advance button missing"], None
    btn_rect = rect_of(btn)
    win_w, win_h = root.winfo_width(), root.winfo_height()
    mode = getattr(mgr, "_menu_layout_mode", None)

    # Pills: CTkButton instances anywhere under host except the advance btn.
    pills = []
    def walk(w):
        for child in w.winfo_children():
            if isinstance(child, ctk.CTkButton) and child is not btn:
                pills.append(child)
            walk(child)
    walk(host)
    if not pills:
        errors.append(f"{width}px: no nav pills found (test harness broken)")

    if mode == "wide":
        # 1. No overlap.
        for p in pills:
            if overlaps(btn_rect, rect_of(p)):
                errors.append(
                    f"{width}px: OVERLAP: Advance {btn_rect} vs '{label_of(p)}' {rect_of(p)}")
        # 2. Button centered on the window (clamped up to 40px to clear
        # the wider left side -- imperceptible, never overlapping).
        btn_cx = (btn_rect[0] + btn_rect[2]) / 2
        if abs(btn_cx - win_w / 2) > 40:
            errors.append(
                f"{width}px: button not window-centered: cx={btn_cx:.0f} win_cx={win_w/2:.0f}")
        # 3. Button + pills fully inside the window.
        if not inside_window(btn_rect, win_w, win_h):
            errors.append(f"{width}px: Advance button clipped: {btn_rect} win=({win_w},{win_h})")
        for p in pills:
            pr = rect_of(p)
            if not inside_window(pr, win_w, win_h):
                errors.append(f"{width}px: CLIPPED pill '{label_of(p)}' {pr} win=({win_w},{win_h})")
    elif mode == "narrow":
        # 4. Button below the pills row, no overlap.
        pills_bottom = max((rect_of(p)[3] for p in pills), default=0)
        if btn_rect[1] < pills_bottom - 2:
            errors.append(
                f"{width}px: narrow mode but button not below pills: btn_top={btn_rect[1]} pills_bottom={pills_bottom}")
        for p in pills:
            if overlaps(btn_rect, rect_of(p)):
                errors.append(
                    f"{width}px: OVERLAP (narrow): Advance {btn_rect} vs '{label_of(p)}' {rect_of(p)}")
        # 5. Pills visible.
        for p in pills:
            pr = rect_of(p)
            if not inside_window(pr, win_w, win_h):
                errors.append(f"{width}px: CLIPPED pill '{label_of(p)}' {pr} win=({win_w},{win_h})")
        # Button horizontally centered in narrow mode too.
        btn_cx = (btn_rect[0] + btn_rect[2]) / 2
        if abs(btn_cx - win_w / 2) > 8:
            errors.append(
                f"{width}px: narrow button not centered: cx={btn_cx:.0f} win_cx={win_w/2:.0f}")
    else:
        errors.append(f"{width}px: layout mode never set (harness broken)")

    host.destroy()
    root.update_idletasks()
    return errors, mode


def main():
    ns = load_real_methods()
    root = tk.Tk()
    root.withdraw()
    root.deiconify()
    results = []
    all_errors = []
    for width in (1920, 1600, 1366, 1280, 1100, 1024):
        errs, mode = check_width(ns, root, width)
        results.append((width, mode, errs))
        all_errors.extend(errs)
    root.destroy()

    print("=== Continue/Advance button vs menu groups ===")
    for width, mode, errs in results:
        status = "OK" if not errs else f"{len(errs)} PROBLEM(S)"
        print(f"  {width}px [{mode}]: {status}")
        for e in errs:
            print(f"    - {e}")
    print(f"\n{len(all_errors)} total problem(s)")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
