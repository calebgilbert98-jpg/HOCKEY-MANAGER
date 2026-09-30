# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""trackc_common.py -- shared scaffolding for the TRACK C missing-UI surfaces.

Read-only helpers for the 8 new "Systems" screens. Nothing here mutates
engine state; every surface renders numbers that trace back to the engine
read it cites. Eastside grammar: content surfaces via show_screen, non-modal,
no grab_set anywhere.
"""

import tkinter as tk


def init_trackc_view(view, parent, app):
    """Standard CustomTkinter view bootstrap (mirrors RosterView's pattern)."""
    import customtkinter as ctk
    from ctk_theme import (
        init_ctk_theme, primary_button, secondary_button, heading, body,
        TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
        TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
        ROW_HOVER, ROW_SELECTED,
    )
    view._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                    CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                    TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED,
                    BLUE=BLUE, ROW_HOVER=ROW_HOVER, ROW_SELECTED=ROW_SELECTED)
    view._primary_button = primary_button
    view._secondary_button = secondary_button
    view._heading = heading
    view._body = body
    init_ctk_theme()
    ctk.CTkFrame.__init__(view, parent)
    view.app = app if app is not None else parent
    view._close_screen = None  # set by show_screen()
    view.configure(fg_color=BG)


def make_body(view):
    """Header + refresh button + scrollable body. Returns (body, status_var)."""
    import customtkinter as ctk
    ct = view._ct
    top = ctk.CTkFrame(view, fg_color=ct["PANEL"], corner_radius=0)
    top.pack(fill="x")
    view._heading(top, text=view.TITLE, size=18).pack(side="left", padx=16, pady=10)
    view._body(top, text=view.SUBTITLE, dim=True).pack(side="left", padx=4, pady=10)
    view._secondary_button(top, text="Refresh", width=90,
                           command=view.refresh).pack(side="right", padx=16, pady=8)
    status = tk.StringVar(master=view, value="")
    view._body(top, text="", textvariable=status, dim=True).pack(side="right", padx=4)
    view._status_var = status
    body = ctk.CTkScrollableFrame(view, fg_color=view._ct["BG"])
    body.pack(fill="both", expand=True, padx=12, pady=(8, 12))
    return body


def section(parent_view, body, title, note=None):
    """A labeled card section. Returns the inner frame to pack rows into."""
    import customtkinter as ctk
    ct = parent_view._ct
    card = ctk.CTkFrame(body, fg_color=ct["CARD"], corner_radius=8)
    card.pack(fill="x", padx=4, pady=6)
    parent_view._heading(card, text=title, size=14).pack(anchor="w", padx=14, pady=(10, 2))
    if note:
        parent_view._body(card, text=note, dim=True).pack(anchor="w", padx=14, pady=(0, 6))
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=(0, 10))
    return inner


def row(parent_view, parent, texts, widths=None, bold_first=False):
    """One table row: texts aligned in fixed-width columns (single-level scroll)."""
    import customtkinter as ctk
    ct = parent_view._ct
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill="x", pady=1)
    widths = widths or [None] * len(texts)
    for i, t in enumerate(texts):
        w = widths[i] if i < len(widths) else None
        lbl = ctk.CTkLabel(f, text=str(t), width=w or 0,
                           anchor="w", font=("Segoe UI", 12,
                                             "bold" if (bold_first and i == 0) else "normal"))
        lbl.pack(side="left", padx=(0, 10))
    return f


def chip(parent_view, parent, text, color_key):
    import customtkinter as ctk
    ct = parent_view._ct
    return ctk.CTkLabel(parent, text=text, fg_color=ct[color_key],
                        text_color="#101418", corner_radius=10,
                        font=("Segoe UI", 11, "bold"),
                        padx=8, pady=2)


def hbar(parent_view, parent, frac, width=160, color_key="TEAL"):
    """A small progress bar (frac 0..1)."""
    import customtkinter as ctk
    ct = parent_view._ct
    bar = ctk.CTkProgressBar(parent, width=width, height=10,
                             fg_color=ct["BORDER"], progress_color=ct[color_key])
    bar.set(max(0.0, min(1.0, frac)))
    return bar


def user_team(view):
    try:
        return view.app.user_team
    except Exception:
        return None


def league_of(view):
    try:
        return view.app.league
    except Exception:
        return None


def player_name(p):
    try:
        return p.full_name or getattr(p, "name", "?")
    except Exception:
        return "?"
