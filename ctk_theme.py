# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# ctk_theme.py
# CustomTkinter theme setup + shared widgets for Puck Dynasty.
# Call init_ctk_theme() once at startup before creating CTk windows.

import os
import sys

import customtkinter as ctk

# ---- Puck Dynasty palette (mirrors modern_ui.py) ----
TEAL = "#00ceb8"
TEAL_HOVER = "#00a896"
TEAL_DARK = "#008f80"
BG = "#0e0e11"          # window background
PANEL = "#16161a"       # frames / panels
CARD = "#1e1e24"        # cards, entry fields
BORDER = "#2e2e38"      # subtle borders
ROW_HOVER = "#26262e"
ROW_SELECTED = "#0d2b28"
TEXT = "#f4f4f5"
TEXT_DIM = "#a1a1aa"
TEXT_FAINT = "#71717a"
GOLD = "#e8b93c"
GREEN = "#3fb950"
RED = "#e74c3c"
BLUE = "#58a6ff"

# Readable text color for the current accent (dark on gold/teal, white on
# navy/red). set_team_accent() keeps it in sync with TEAL.
ACCENT_TEXT = BG

_THEME_APPLIED = False


def _darken_hex(hex_color, factor=0.85):
    """Scale a hex color toward black by factor (0..1). Never raises."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))
    except Exception:
        return hex_color


def set_team_accent(accent, hover=None, text=None):
    """Re-theme UI accents to a team's colors.

    Mutates TEAL/TEAL_HOVER/TEAL_DARK/ACCENT_TEXT. Widget helpers in this
    module read those globals at call time, so everything built after this
    call -- nav pills, primary buttons, selected states -- wears the team
    color. Safe to call repeatedly; pass no args to restore legacy teal.
    """
    global TEAL, TEAL_HOVER, TEAL_DARK, ACCENT_TEXT
    TEAL = accent or "#00ceb8"
    TEAL_HOVER = hover or _darken_hex(TEAL, 0.85)
    TEAL_DARK = _darken_hex(TEAL, 0.7)
    ACCENT_TEXT = text or BG




def _theme_path():
    """Resolve assets/puck_dynasty_theme.json in dev tree and PyInstaller bundle."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "assets", "puck_dynasty_theme.json"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "assets", "puck_dynasty_theme.json"))
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def init_ctk_theme():
    """Apply the Puck Dynasty CustomTkinter theme. Safe to call repeatedly."""
    global _THEME_APPLIED
    if _THEME_APPLIED:
        return
    ctk.set_appearance_mode("dark")
    path = _theme_path()
    if path:
        try:
            ctk.set_default_color_theme(path)
        except Exception:
            pass  # fall back to built-in dark-blue; widgets still get explicit colors
    _THEME_APPLIED = True


def primary_button(parent, text, command=None, **kw):
    """Teal primary CTkButton (follows the team accent once themed)."""
    kw.setdefault("fg_color", TEAL)
    kw.setdefault("hover_color", TEAL_HOVER)
    kw.setdefault("text_color", ACCENT_TEXT)
    kw.setdefault("corner_radius", 8)
    kw.setdefault("font", ("Segoe UI", 12, "bold"))
    return ctk.CTkButton(parent, text=text, command=command, **kw)


def secondary_button(parent, text, command=None, **kw):
    """Dark secondary CTkButton."""
    kw.setdefault("fg_color", CARD)
    kw.setdefault("hover_color", BORDER)
    kw.setdefault("text_color", TEXT)
    kw.setdefault("corner_radius", 8)
    kw.setdefault("font", ("Segoe UI", 12))
    return ctk.CTkButton(parent, text=text, command=command, **kw)


def heading(parent, text, size=18, **kw):
    # Route through ui_scale so Settings -> Font size actually works.
    if "font" not in kw:
        from ui_scale import scaled
        size = scaled(size)
    kw.setdefault("font", ("Segoe UI", size, "bold"))
    kw.setdefault("text_color", TEXT)
    return ctk.CTkLabel(parent, text=text, **kw)


def body(parent, text, size=12, dim=False, **kw):
    if "font" not in kw:
        from ui_scale import scaled
        size = scaled(size)
    kw.setdefault("font", ("Segoe UI", size))
    kw.setdefault("text_color", TEXT_DIM if dim else TEXT)
    return ctk.CTkLabel(parent, text=text, **kw)


class busy_cursor:
    """Show a wait cursor while a heavy UI build runs, then restore it.

    Additive R8 helper: wrap list/window construction that can take a
    beat (staff trees, comparison window, hub tabs) so the user sees the
    app is working. Forces a paint on entry so the cursor change is
    visible before the heavy work starts. Never raises. Usable as
    ``with busy_cursor(widget):`` or via manual __enter__/__exit__.
    """

    def __init__(self, widget):
        self._widget = widget

    def __enter__(self):
        try:
            self._widget.config(cursor="watch")
        except Exception:
            pass
        try:
            self._widget.update_idletasks()
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._widget.config(cursor="")
        except Exception:
            pass
        return False


class CTkPlayerList(ctk.CTkScrollableFrame):
    """Modern selectable player list — a CTk-native replacement for the
    two-column (name / OVR) ttk.Treeview used in trade-style windows.

    Usage:
        lst = CTkPlayerList(parent)
        lst.set_players(players)          # list of player objects
        player = lst.get_selected()       # currently selected player or None
        lst.set_players(...)              # re-populate (clears selection)
    """

    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", CARD)
        kw.setdefault("corner_radius", 10)
        super().__init__(parent, **kw)
        self._players = []
        self._rows = []          # (frame, player)
        self._selected = None
        self._selected_frame = None
        self._badge_fn = None    # optional: badge_fn(player) -> (text, color)
        # Optional: on_right_click(event, player) -- EHM/FM24 player menu.
        self.on_right_click = None

    def set_players(self, players, badge_fn=None):
        for frame, _ in self._rows:
            frame.destroy()
        self._rows = []
        self._players = list(players)
        self._selected = None
        self._selected_frame = None
        self._badge_fn = badge_fn
        for p in self._players:
            self._add_row(p)

    def _add_row(self, player):
        row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)

        name = getattr(player, "full_name", str(player))
        try:
            ovr = int(player.overall_rating())
        except Exception:
            ovr = 0
        pos = ""
        try:
            pos = player.primary_position.name.replace("_", " ").title()
        except Exception:
            pass
        try:
            _age = getattr(player, "age", None)
            _age_txt = f" \u00b7 {int(_age)}" \
                if _age is not None else ""
        except Exception:
            _age_txt = ""

        name_lbl = ctk.CTkLabel(row, text=name, font=("Segoe UI", 12),
                                text_color=TEXT, anchor="w")
        name_lbl.pack(side="left", padx=(8, 4), pady=6)
        if pos or _age_txt:
            pos_lbl = ctk.CTkLabel(row, text=f"{pos}{_age_txt}",
                                   font=("Segoe UI", 10),
                                   text_color=TEXT_FAINT, anchor="w", width=118)
            pos_lbl.pack(side="left", padx=4)

        ovr_color = self._ovr_color(ovr)
        ovr_lbl = ctk.CTkLabel(row, text=str(ovr), font=("Segoe UI", 12, "bold"),
                               text_color=ovr_color, width=36, anchor="e")
        ovr_lbl.pack(side="right", padx=8)

        # Optional value badge (trade screen: the other GM's valuation).
        badge_lbl = None
        if self._badge_fn is not None:
            try:
                _badge = self._badge_fn(player)
            except Exception:
                _badge = None
            if _badge:
                try:
                    _btext, _bcolor = _badge[0], _badge[1]
                except Exception:
                    _btext, _bcolor = None, None
                if _btext:
                    badge_lbl = ctk.CTkLabel(
                        row, text=str(_btext), font=("Segoe UI", 9, "bold"),
                        text_color=_bcolor or TEXT_DIM, anchor="e", width=170)
                    badge_lbl.pack(side="right", padx=(4, 2))

        _bind = [w for w in (row, name_lbl, ovr_lbl, badge_lbl) if w is not None]
        for w in _bind:
            w.bind("<Button-1>", lambda e, f=row, pl=player: self._select(f, pl))
            w.bind("<Enter>", lambda e, f=row: self._hover(f, True))
            w.bind("<Leave>", lambda e, f=row: self._hover(f, False))
            w.bind("<Button-3>", lambda e, pl=player: self._fire_right_click(e, pl))
            w.bind("<Shift-F10>", lambda e, pl=player: self._fire_right_click(e, pl))
        self._rows.append((row, player))

    def _fire_right_click(self, event, player):
        cb = getattr(self, "on_right_click", None)
        if callable(cb):
            try:
                cb(event, player)
            except Exception:
                pass

    @staticmethod
    def _ovr_color(ovr):
        if ovr >= 85:
            return GREEN
        if ovr >= 78:
            return TEAL
        if ovr >= 70:
            return GOLD
        return TEXT_DIM

    def _hover(self, frame, on):
        if frame is self._selected_frame:
            return
        frame.configure(fg_color=ROW_HOVER if on else "transparent")

    def _select(self, frame, player):
        if self._selected_frame is not None:
            self._selected_frame.configure(fg_color="transparent")
        self._selected = player
        self._selected_frame = frame
        frame.configure(fg_color=ROW_SELECTED)

    def get_selected(self):
        return self._selected

    def clear_selection(self):
        if self._selected_frame is not None:
            self._selected_frame.configure(fg_color="transparent")
        self._selected = None
        self._selected_frame = None


class CTkOfferList(ctk.CTkScrollableFrame):
    """Selectable asset list for trade offer building (replaces tk.Listbox)."""

    def __init__(self, parent, height=140, **kw):
        kw.setdefault("fg_color", BG)
        kw.setdefault("corner_radius", 8)
        super().__init__(parent, height=height, **kw)
        self._items = []        # (frame, label_text, payload_index)
        self._selected_idx = None
        self._selected_frame = None
        self._empty_label = None

    def set_items(self, labels):
        """labels: list of display strings. Selection index maps 1:1."""
        for frame, _, _ in self._items:
            frame.destroy()
        self._items = []
        self._selected_idx = None
        self._selected_frame = None
        if self._empty_label is not None:
            self._empty_label.destroy()
            self._empty_label = None
        if not labels:
            self._empty_label = ctk.CTkLabel(
                self, text="No assets added yet",
                font=("Segoe UI", 11, "italic"), text_color=TEXT_FAINT)
            self._empty_label.pack(padx=8, pady=8)
            return
        for i, text in enumerate(labels):
            row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=6)
            row.pack(fill="x", padx=4, pady=1)
            lbl = ctk.CTkLabel(row, text=text, font=("Segoe UI", 11),
                               text_color=TEXT, anchor="w")
            lbl.pack(side="left", padx=8, pady=4, fill="x", expand=True)
            for w in (row, lbl):
                w.bind("<Button-1>", lambda e, f=row, idx=i: self._select(f, idx))
                w.bind("<Enter>", lambda e, f=row: self._hover(f, True))
                w.bind("<Leave>", lambda e, f=row: self._hover(f, False))
            self._items.append((row, text, i))

    def _hover(self, frame, on):
        if frame is self._selected_frame:
            return
        frame.configure(fg_color=ROW_HOVER if on else "transparent")

    def _select(self, frame, idx):
        if self._selected_frame is not None:
            self._selected_frame.configure(fg_color="transparent")
        self._selected_idx = idx
        self._selected_frame = frame
        frame.configure(fg_color=ROW_SELECTED)

    def get_selected_index(self):
        return self._selected_idx
