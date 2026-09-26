# modern_theme_bridge.py
# Applies the modern Puck Dynasty dark theme to every legacy window.
#
# Legacy windows were built with a mix of ttk default styles and classic tk
# widgets. Calling apply_modern_theme(root) once at startup restyles all of
# them to the charcoal/teal palette (AppColors) without rewriting each file:
#   - ttk 'clam' theme with every standard style configured
#   - tk option database defaults for Listbox, Text, Entry, Menu, etc.
#
# Explicit per-widget colors set by a window still win over these defaults.

import tkinter as tk
from tkinter import ttk

from modern_ui import AppColors, AppFonts

_APPLIED = False


def apply_modern_theme(root):
    """Apply the modern dark theme globally. Safe to call multiple times."""
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    BG = AppColors.BG
    ELEV = AppColors.BG_ELEVATED
    HOVER = AppColors.BG_HOVER
    BORDER = AppColors.BORDER
    ACCENT = AppColors.ACCENT
    ACCENT_DIM = AppColors.ACCENT_DIM
    ACCENT_BG = AppColors.ACCENT_BG
    T1 = AppColors.TEXT_PRIMARY
    T2 = AppColors.TEXT_SECONDARY
    T3 = AppColors.TEXT_TERTIARY

    # ---- base ----
    style.configure(".", background=BG, foreground=T1,
                    fieldbackground=ELEV, troughcolor=BG,
                    bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, arrowcolor=T2,
                    font=AppFonts.SMALL)

    # ---- frames / labels ----
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=T1)
    style.configure("Muted.TLabel", background=BG, foreground=T2)
    style.configure("Heading.TLabel", background=BG, foreground=T1,
                    font=AppFonts.H2)
    style.configure("Title.TLabel", background=BG, foreground=T1,
                    font=AppFonts.H1)
    style.configure("Subheading.TLabel", background=BG, foreground=T1,
                    font=AppFonts.H3)

    # ---- buttons ----
    style.configure("TButton", background=ELEV, foreground=T1,
                    bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, padding=8, font=AppFonts.SMALL_BOLD)
    style.map("TButton",
              background=[("active", HOVER), ("pressed", AppColors.BG_PRESSED)],
              foreground=[("active", T1)],
              bordercolor=[("focus", ACCENT)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    bordercolor=ACCENT_DIM, lightcolor=ACCENT_DIM,
                    darkcolor=ACCENT_DIM, padding=8,
                    font=AppFonts.SMALL_BOLD)
    style.map("Accent.TButton",
              background=[("active", ACCENT_DIM)],
              foreground=[("active", "#ffffff")])

    # ---- notebook / tabs ----
    style.configure("TNotebook", background=BG, bordercolor=BG,
                    lightcolor=BG, darkcolor=BG, tabmargins=[0, 0, 0, 0])
    style.configure("TNotebook.Tab", background=BG, foreground=T2,
                    bordercolor=BG, lightcolor=BG, darkcolor=BG,
                    padding=[14, 8], font=AppFonts.SMALL_BOLD)
    style.map("TNotebook.Tab",
              background=[("selected", BG), ("active", HOVER)],
              foreground=[("selected", ACCENT), ("active", T1)])

    # ---- treeview (rosters, standings, stats grids) ----
    style.configure("Treeview", background=ELEV, foreground=T1,
                    fieldbackground=ELEV, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER,
                    rowheight=26, font=AppFonts.SMALL)
    style.configure("Treeview.Heading", background=BG, foreground=T2,
                    bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, font=AppFonts.LABEL)
    style.map("Treeview",
              background=[("selected", ACCENT_BG)],
              foreground=[("selected", T1)])
    style.map("Treeview.Heading",
              background=[("active", HOVER)],
              foreground=[("active", T1)])

    # ---- inputs ----
    style.configure("TEntry", fieldbackground=ELEV, foreground=T1,
                    bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, insertcolor=T1, padding=6)
    style.map("TEntry", bordercolor=[("focus", ACCENT)])
    style.configure("TCombobox", fieldbackground=ELEV, background=ELEV,
                    foreground=T1, arrowcolor=ACCENT,
                    bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, padding=6)
    style.map("TCombobox",
              fieldbackground=[("readonly", ELEV)],
              foreground=[("readonly", T1)],
              background=[("readonly", HOVER), ("active", HOVER)],
              arrowcolor=[("readonly", ACCENT)])
    style.configure("TSpinbox", fieldbackground=ELEV, foreground=T1,
                    background=ELEV, arrowcolor=ACCENT,
                    bordercolor=BORDER, insertcolor=T1, padding=6)

    # ---- check / radio ----
    style.configure("TCheckbutton", background=BG, foreground=T1,
                    indicatorcolor=ELEV, indicatorbackground=ELEV)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorcolor=[("selected", ACCENT)])
    style.configure("TRadiobutton", background=BG, foreground=T1,
                    indicatorcolor=ELEV)
    style.map("TRadiobutton",
              background=[("active", BG)],
              indicatorcolor=[("selected", ACCENT)])

    # ---- labelframe ----
    style.configure("TLabelframe", background=ELEV, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
    style.configure("TLabelframe.Label", background=ELEV, foreground=T1,
                    font=AppFonts.H3)

    # ---- scrollbar / progress / separator / scale ----
    style.configure("TScrollbar", background=ELEV, troughcolor=BG,
                    bordercolor=BG, arrowcolor=T3)
    style.map("TScrollbar", background=[("active", HOVER)])
    style.configure("Vertical.TScrollbar", background=ELEV, troughcolor=BG,
                    bordercolor=BG, arrowcolor=T3)
    style.map("Vertical.TScrollbar", background=[("active", HOVER)])
    style.configure("Horizontal.TScrollbar", background=ELEV, troughcolor=BG,
                    bordercolor=BG, arrowcolor=T3)
    style.map("Horizontal.TScrollbar", background=[("active", HOVER)])
    style.configure("TProgressbar", background=ACCENT, troughcolor=ELEV,
                    bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)
    style.configure("TSeparator", background=BORDER)
    style.configure("TScale", background=BG, troughcolor=ELEV,
                    bordercolor=BORDER)
    style.configure("TMenubutton", background=ELEV, foreground=T1,
                    arrowcolor=ACCENT, padding=6)
    style.configure("TPanedwindow", background=BG)

    # ---- classic tk widgets via option database ----
    opt = root.option_add
    opt("*Background", BG)
    opt("*Foreground", T1)
    opt("*selectBackground", ACCENT_BG)
    opt("*selectForeground", T1)
    opt("*Entry*Background", ELEV)
    opt("*Entry*Foreground", T1)
    opt("*Entry*insertBackground", T1)
    opt("*Text*Background", ELEV)
    opt("*Text*Foreground", T1)
    opt("*Text*insertBackground", T1)
    opt("*Listbox*Background", ELEV)
    opt("*Listbox*Foreground", T1)
    opt("*Listbox*selectBackground", ACCENT_BG)
    opt("*Listbox*selectForeground", T1)
    opt("*Menu*Background", ELEV)
    opt("*Menu*Foreground", T1)
    opt("*Menu*activeBackground", ACCENT_BG)
    opt("*Menu*activeForeground", T1)
    opt("*Checkbutton*Background", BG)
    opt("*Checkbutton*Foreground", T1)
    opt("*Checkbutton*selectColor", ACCENT)
    opt("*Checkbutton*activeBackground", BG)
    opt("*Radiobutton*Background", BG)
    opt("*Radiobutton*Foreground", T1)
    opt("*Radiobutton*selectColor", ACCENT)
    opt("*Scale*Background", BG)
    opt("*Scale*Foreground", T2)
    opt("*Scale*troughColor", ELEV)
    opt("*Spinbox*Background", ELEV)
    opt("*Spinbox*Foreground", T1)
    opt("*Message*Background", BG)
    opt("*Message*Foreground", T2)
    # Combobox popdown list
    root.tk.call("option", "add", "*TCombobox*Listbox.background", ELEV)
    root.tk.call("option", "add", "*TCombobox*Listbox.foreground", T1)
    root.tk.call("option", "add", "*TCombobox*Listbox.selectBackground",
                 ACCENT_BG)
    root.tk.call("option", "add", "*TCombobox*Listbox.selectForeground", T1)

    # Default font family for classic widgets
    try:
        root.tk.call("font", "configure", "TkDefaultFont",
                     "-family", "Segoe UI", "-size", 10)
        root.tk.call("font", "configure", "TkTextFont",
                     "-family", "Segoe UI", "-size", 10)
    except Exception:
        pass
