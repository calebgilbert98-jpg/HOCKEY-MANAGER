"""Small UI pieces for the player-view system: selector + custom-view editor.

Kept separate from player_views.py so the data module stays UI-free and
importable from headless QA.
"""

import tkinter as tk
from tkinter import ttk


def _ensure_view_styles():
    """Dark styles for the selector, matching the filter bar."""
    if getattr(_ensure_view_styles, "_done", False):
        return
    _ensure_view_styles._done = True
    try:
        from player_filters import _ensure_filterbar_styles
        _ensure_filterbar_styles()
    except Exception:
        pass
    # Active view button: accent-tinted so the current view is obvious.
    try:
        from tkinter import ttk as _ttk
        _style = _ttk.Style()
        _style.configure("FilterBar.Active.TButton",
                         background="#0e4f4a", foreground="#ffffff",
                         font=("Segoe UI", 10, "bold"),
                         relief="flat", padding=(8, 4))
        _style.map("FilterBar.Active.TButton",
                   background=[("active", "#137a70")])
    except Exception:
        pass


class ViewButtonRow(ttk.Frame):
    """Row of toggle buttons for view selection (Eastside-style).

    One click switches the view -- no dropdown, no selection event to
    misfire, no popup. The active view is accent-highlighted. Custom
    views appear as extra buttons; refresh() rebuilds the row.
    """

    def __init__(self, parent, default_label="Club View", initial=None,
                 on_change=None, **kw):
        _ensure_view_styles()
        kw.setdefault("style", "FilterBar.TFrame")
        super().__init__(parent, **kw)
        self._default_label = default_label
        self._on_change = on_change
        self._current = initial or default_label
        self._buttons = {}  # name -> ttk.Button
        ttk.Label(self, text="View:", style="FilterBar.TLabel").pack(
            side="left", padx=(0, 6))
        self._btn_frame = ttk.Frame(self, style="FilterBar.TFrame")
        self._btn_frame.pack(side="left", fill="x", expand=True)
        self.refresh()

    def refresh(self):
        """Rebuild the button row (picks up new/deleted custom views)."""
        from player_views import list_view_names
        names = [self._default_label] + list_view_names()
        for w in self._btn_frame.winfo_children():
            w.destroy()
        self._buttons = {}
        for name in names:
            # Shorten long labels for button fit; full name in tooltip-ish.
            short = name.replace(" View", "").replace(" + ", "+")
            btn = ttk.Button(self._btn_frame, text=short,
                             style="FilterBar.TButton",
                             command=lambda n=name: self._picked(n))
            btn.pack(side="left", padx=2, pady=2)
            self._buttons[name] = btn
        if self._current not in names:
            self._current = self._default_label
        self._set_active(self._current)

    def _set_active(self, name):
        self._current = name
        for n, btn in self._buttons.items():
            try:
                btn.configure(style="FilterBar.Active.TButton"
                            if n == name else "FilterBar.TButton")
            except Exception:
                pass

    @property
    def current(self):
        return self._current

    def set_view(self, name):
        """Programmatic selection (e.g. restoring a saved view)."""
        if name in self._buttons:
            self._picked(name)

    def _picked(self, name):
        self._set_active(name)
        if callable(self._on_change):
            try:
                self._on_change(name)
            except Exception:
                pass


class ViewsFiltersPanel(ttk.Frame):
    """Solidified Eastside-style panel: view buttons + filter bar in one.

    A single titled section holding the :class:`ViewButtonRow` (top) and
    the elite :class:`FilterBar` (bottom). No popups, no dialogs --
    everything the user needs to slice the player list lives here.
    Delegates the filter API (get_filter/set_count/clear) to the bar.
    """

    def __init__(self, parent, default_label="Club View", initial_view=None,
                 on_view_change=None, on_filter_change=None, **kw):
        _ensure_view_styles()
        kw.setdefault("style", "FilterBar.TFrame")
        super().__init__(parent, **kw)
        self._on_view_change = on_view_change

        # Title
        ttk.Label(self, text="Views & Filters",
                  style="FilterBar.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                      padx=8, pady=(6, 2))
        # View buttons
        self.view_row = ViewButtonRow(
            self, default_label=default_label, initial=initial_view,
            on_change=self._view_picked)
        self.view_row.pack(fill="x", padx=8, pady=(0, 4))

        # Filter bar (search + inline add + chips + count)
        from player_filters import FilterBar
        self.filter_bar = FilterBar(self, on_change=on_filter_change)
        self.filter_bar.pack(fill="x", padx=8, pady=(0, 6))

    def _view_picked(self, name):
        if callable(self._on_view_change):
            try:
                self._on_view_change(name)
            except Exception:
                pass

    # -- filter API (delegated) -------------------------------------------
    def get_filter(self):
        return self.filter_bar.get_filter()

    def set_count(self, shown, total):
        self.filter_bar.set_count(shown, total)

    def clear(self):
        self.filter_bar.clear()

    @property
    def current_view(self):
        return self.view_row.current

    def refresh_views(self):
        self.view_row.refresh()
