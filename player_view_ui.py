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


class ViewSelector(ttk.Frame):
    """'View:' label + preset combobox + Manage button.

    The first entry is always ``default_label`` (the screen's native column
    set); the rest come from player_views.list_view_names().
    """

    def __init__(self, parent, default_label="Club View", initial=None,
                 on_change=None, **kw):
        _ensure_view_styles()
        kw.setdefault("style", "FilterBar.TFrame")
        super().__init__(parent, **kw)
        self._default_label = default_label
        self._on_change = on_change
        ttk.Label(self, text="View:",
                  style="FilterBar.TLabel").pack(side="left", padx=(0, 4))
        self._var = tk.StringVar(value=initial or default_label)
        self._combo = ttk.Combobox(self, textvariable=self._var,
                                   state="readonly", width=16)
        self._combo.pack(side="left")
        self._combo.bind("<<ComboboxSelected>>", self._picked)
        ttk.Button(self, text="Manage\u2026", style="FilterBar.TButton",
                   command=self._open_editor).pack(side="left", padx=(6, 0))
        self.refresh()

    def refresh(self):
        from player_views import list_view_names
        names = [self._default_label] + list_view_names()
        self._combo.configure(values=names)
        if self._var.get() not in names:
            self._var.set(self._default_label)

    @property
    def current(self):
        return self._var.get()

    def _picked(self, _event=None):
        if callable(self._on_change):
            try:
                self._on_change(self._var.get())
            except Exception:
                pass

    def _open_editor(self):
        open_view_editor(self, on_saved=self._editor_saved)

    def _editor_saved(self, name):
        self.refresh()
        self._var.set(name)
        self._picked()


def open_view_editor(parent, on_saved=None):
    """Non-modal custom-view editor: name + grouped column checklist."""
    from player_views import (COLUMN_DEFS, VIEWS, get_view_columns,
                              save_custom_view, delete_custom_view,
                              load_custom_views)

    dlg = tk.Toplevel(parent)
    dlg.title("Manage views")
    try:
        dlg.transient(parent.winfo_toplevel())
    except Exception:
        pass
    # Non-modal: the screen stays usable underneath.
    dlg.geometry("560x520")

    top = ttk.Frame(dlg, padding=12)
    top.pack(fill="x")
    ttk.Label(top, text="View name:").pack(side="left")
    name_var = tk.StringVar()
    ttk.Entry(top, textvariable=name_var, width=28).pack(side="left", padx=6)

    # Existing custom views (delete)
    mid = ttk.Frame(dlg, padding=(12, 0))
    mid.pack(fill="x")
    ttk.Label(mid, text="Saved views:").pack(side="left")
    custom_names = [n for n in load_custom_views() if n not in VIEWS]
    saved_var = tk.StringVar()
    saved_combo = ttk.Combobox(mid, textvariable=saved_var,
                               values=custom_names, state="readonly",
                               width=24)
    saved_combo.pack(side="left", padx=6)

    def _delete_saved():
        n = saved_var.get()
        if n:
            delete_custom_view(n)
            dlg.destroy()
            open_view_editor(parent, on_saved=on_saved)

    ttk.Button(mid, text="Delete", command=_delete_saved).pack(side="left")

    # Scrollable grouped checklist
    body = ttk.Frame(dlg, padding=(12, 6))
    body.pack(fill="both", expand=True)
    canvas = tk.Canvas(body, highlightthickness=0)
    vsb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>",
               lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    groups = {}
    for k, d in COLUMN_DEFS.items():
        groups.setdefault(d.group, []).append((k, d.header))
    check_vars = {}
    for gname in sorted(groups):
        ttk.Label(inner, text=gname,
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 2))
        grid = ttk.Frame(inner)
        grid.pack(anchor="w", fill="x")
        for i, (k, header) in enumerate(sorted(groups[gname],
                                               key=lambda x: x[1].lower())):
            var = tk.BooleanVar(value=False)
            check_vars[k] = var
            ttk.Checkbutton(grid, text=header, variable=var).grid(
                row=i // 3, column=i % 3, sticky="w", padx=(0, 12))

    err_var = tk.StringVar(value="")
    ttk.Label(dlg, textvariable=err_var, foreground="#e5484d").pack()

    def _load_into_editor(_event=None):
        n = saved_var.get()
        cols = get_view_columns(n) or []
        for k, var in check_vars.items():
            var.set(k in cols)
        name_var.set(n)

    saved_combo.bind("<<ComboboxSelected>>", _load_into_editor)

    def _save():
        cols = [k for k, var in check_vars.items() if var.get()]
        try:
            save_custom_view(name_var.get(), cols)
        except ValueError as e:
            err_var.set(str(e))
            return
        dlg.destroy()
        if callable(on_saved):
            try:
                on_saved(name_var.get().strip())
            except Exception:
                pass

    btns = ttk.Frame(dlg, padding=12)
    btns.pack(fill="x")
    ttk.Button(btns, text="Close", command=dlg.destroy).pack(side="right")
    ttk.Button(btns, text="Save view", command=_save).pack(side="right",
                                                            padx=(0, 8))
