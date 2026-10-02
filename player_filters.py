"""Elite player filtering for scouting and roster screens (Eastside/FM-style).

:class:`PlayerFilter` is the data model -- text search plus any number of
attribute/composite threshold rows (AND semantics), evaluated through a
:class:`player_views.ViewContext` so scouting filters respect the fog of
war (thresholds match on the *perceived* midpoint of what your scouts
actually know).

:class:`FilterBar` is the reusable widget: a search entry, an "+ Add
filter" button opening a small non-modal picker (attribute + min/max),
active filters as removable chips, and a Clear button. Screens call
:meth:`FilterBar.get_filter` and run :meth:`PlayerFilter.matches`.
"""

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AttrThreshold:
    """One threshold row: key in {'ovr','age','attr:<a>','comp:<c>'},
    min/max inclusive, either may be None."""
    key: str
    label: str
    min: float = None
    max: float = None

    def describe(self):
        lo = f"{_num(self.min)}" if self.min is not None else ""
        hi = f"{_num(self.max)}" if self.max is not None else ""
        if self.min is not None and self.max is not None:
            return f"{self.label} {lo}\u2013{hi}"
        if self.min is not None:
            return f"{self.label} \u2265 {lo}"
        if self.max is not None:
            return f"{self.label} \u2264 {hi}"
        return self.label


def _num(v):
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(v)


class PlayerFilter:
    """Text + threshold rows. Empty filter matches everything."""

    def __init__(self):
        self.text = ""
        self.thresholds = []  # [AttrThreshold]

    def is_empty(self):
        return not self.text.strip() and not self.thresholds

    def _value_for(self, player, ctx, key):
        if key == "ovr":
            try:
                from player_views import column_sort
                return column_sort("ovr", player, ctx)
            except Exception:
                return None
        if key == "age":
            try:
                return float(player.age)
            except (TypeError, ValueError):
                return None
        if key.startswith("attr:"):
            from player_views import _mid
            return _mid(ctx.attr(player, key[5:]))
        if key.startswith("comp:"):
            from player_views import _mid
            return _mid(ctx.composite(player, key[5:]))
        return None

    def matches(self, player, ctx):
        t = (self.text or "").strip().lower()
        if t:
            name = getattr(player, "full_name", "") or ""
            if t not in name.lower():
                return False
        for th in self.thresholds:
            v = self._value_for(player, ctx, th.key)
            # Unknown value can't satisfy a threshold: exclude (strict,
            # predictable -- like Eastside).
            if v is None:
                return False
            if th.min is not None and v < th.min:
                return False
            if th.max is not None and v > th.max:
                return False
        return True


# ---------------------------------------------------------------------------
# Pickable filter targets: OVR, Age, every attribute, every composite
# ---------------------------------------------------------------------------

def filter_targets():
    """Ordered [(label, key)] for the add-filter picker."""
    try:
        from player_views import COLUMN_DEFS
    except Exception:
        return [("OVR", "ovr"), ("Age", "age")]
    targets = [("OVR", "ovr"), ("Age", "age")]
    attrs, comps = [], []
    for k, d in COLUMN_DEFS.items():
        if k.startswith("attr:"):
            attrs.append((d.header, k))
        elif k.startswith("comp:"):
            comps.append((d.header, k))
    # De-dup labels defensively (suffix the group on collision).
    seen = {"OVR", "Age"}
    def _uniq(label, group):
        base, i = label, 2
        while base in seen:
            base = f"{label} ({group})"
            i += 1
        seen.add(base)
        return base
    targets += [(_uniq(lbl, "attr"), k)
                for lbl, k in sorted(attrs, key=lambda x: x[0].lower())]
    targets += [(_uniq(lbl, "comp"), k)
                for lbl, k in sorted(comps, key=lambda x: x[0].lower())]
    return targets


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Widget styling: explicit dark styles so the bar matches the game's dark
# theme even when the host screen hasn't applied its ttk theme (and so it
# never inherits a light default).
# ---------------------------------------------------------------------------

_FB_BG = "#16161d"
_FB_CARD = "#232a3a"
_FB_TEXT = "#ffffff"
_FB_DIM = "#a1a1aa"
_FB_ACCENT = "#00ceb8"


def _ensure_filterbar_styles():
    if getattr(_ensure_filterbar_styles, "_done", False):
        return
    _ensure_filterbar_styles._done = True
    style = ttk.Style()
    style.configure("FilterBar.TFrame", background=_FB_BG)
    style.configure("FilterBar.TLabel", background=_FB_BG,
                    foreground=_FB_TEXT, font=("Segoe UI", 10))
    style.configure("FilterBar.Dim.TLabel", background=_FB_BG,
                    foreground=_FB_DIM, font=("Segoe UI", 10))
    style.configure("FilterBar.TButton", background=_FB_CARD,
                    foreground=_FB_TEXT, font=("Segoe UI", 10),
                    relief="flat", padding=(8, 4))
    style.map("FilterBar.TButton", background=[("active", "#2e2e38")])
    style.configure("FilterBar.TEntry", fieldbackground="#0e0e11",
                    foreground=_FB_TEXT, insertcolor=_FB_TEXT,
                    relief="flat", padding=4)
    style.configure("FilterBar.Chip.TFrame", background=_FB_CARD)
    style.configure("FilterBar.Chip.TLabel", background=_FB_CARD,
                    foreground=_FB_TEXT, font=("Segoe UI", 10))
    style.configure("FilterBar.Chip.TButton", background=_FB_CARD,
                    foreground=_FB_DIM, font=("Segoe UI", 10, "bold"),
                    relief="flat", padding=(2, 0))
    style.map("FilterBar.Chip.TButton", foreground=[("active", _FB_TEXT)])


class FilterBar(ttk.Frame):
    """Search entry + add-filter button + active-filter chips + clear."""

    def __init__(self, parent, on_change=None, **kw):
        _ensure_filterbar_styles()
        kw.setdefault("style", "FilterBar.TFrame")
        super().__init__(parent, **kw)
        self._on_change = on_change
        self._filter = PlayerFilter()
        self._targets = filter_targets()
        self._chip_frames = []  # [(AttrThreshold, widget)]

        # Search entry
        ttk.Label(self, text="Search:", style="FilterBar.TLabel").pack(
            side="left", padx=(0, 4))
        self._search_var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self._search_var, width=18,
                          style="FilterBar.TEntry")
        entry.pack(side="left", padx=(0, 8))
        entry.bind("<KeyRelease>", self._on_search)

        # Add-filter button
        ttk.Button(self, text="+ Add filter", style="FilterBar.TButton",
                   command=self._open_add_dialog).pack(side="left", padx=(0, 8))

        # Chips live here
        self._chips = ttk.Frame(self, style="FilterBar.TFrame")
        self._chips.pack(side="left", fill="x", expand=True)

        # Count + clear
        self._count_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._count_var,
                  style="FilterBar.Dim.TLabel").pack(side="left", padx=(8, 4))
        ttk.Button(self, text="Clear", style="FilterBar.TButton",
                   command=self.clear).pack(side="left")

    # -- public API ----------------------------------------------------------
    def get_filter(self):
        return self._filter

    def set_count(self, shown, total):
        if shown == total:
            self._count_var.set(f"{total} players")
        else:
            self._count_var.set(f"{shown} of {total} players")

    def clear(self):
        self._filter = PlayerFilter()
        self._search_var.set("")
        for _, w in self._chip_frames:
            w.destroy()
        self._chip_frames = []
        self._changed()

    # -- internals ------------------------------------------------------------
    def _changed(self):
        if callable(self._on_change):
            try:
                self._on_change()
            except Exception:
                pass

    def _on_search(self, _event=None):
        self._filter.text = self._search_var.get()
        self._changed()

    def _open_add_dialog(self):
        _ensure_filterbar_styles()
        dlg = tk.Toplevel(self)
        dlg.title("Add filter")
        try:
            dlg.configure(bg=_FB_BG)
            dlg.transient(self.winfo_toplevel())
        except Exception:
            pass
        # Non-modal: no grab_set -- the screen stays usable (Eastside-style).
        frm = ttk.Frame(dlg, padding=14, style="FilterBar.TFrame")
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Attribute:",
                  style="FilterBar.TLabel").grid(row=0, column=0, sticky="w",
                                                 pady=(0, 4))
        labels = [lbl for lbl, _ in self._targets]
        combo_var = tk.StringVar(value=labels[0] if labels else "")
        combo = ttk.Combobox(frm, textvariable=combo_var, values=labels,
                             state="readonly", width=28)
        combo.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(frm, text="Min:",
                  style="FilterBar.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(frm, text="Max:",
                  style="FilterBar.TLabel").grid(row=2, column=1, sticky="w")
        min_var, max_var = tk.StringVar(), tk.StringVar()
        ttk.Entry(frm, textvariable=min_var, width=10,
                  style="FilterBar.TEntry").grid(
            row=3, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(frm, textvariable=max_var, width=10,
                  style="FilterBar.TEntry").grid(
            row=3, column=1, sticky="w")

        err_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=err_var, foreground="#e5484d",
                  background=_FB_BG).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        btns = ttk.Frame(frm, style="FilterBar.TFrame")
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", style="FilterBar.TButton",
                   command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text="Add", style="FilterBar.TButton",
                   command=lambda: self._add_from_dialog(
            dlg, combo_var, min_var, max_var, err_var)).pack(
                side="right", padx=(0, 6))

        try:
            x = self.winfo_rootx() + 40
            y = self.winfo_rooty() + 40
            dlg.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _add_from_dialog(self, dlg, combo_var, min_var, max_var, err_var):
        label = combo_var.get()
        key = next((k for lbl, k in self._targets if lbl == label), None)
        if key is None:
            err_var.set("Pick an attribute.")
            return
        try:
            mn = float(min_var.get()) if min_var.get().strip() else None
            mx = float(max_var.get()) if max_var.get().strip() else None
        except ValueError:
            err_var.set("Min/Max must be numbers.")
            return
        if mn is None and mx is None:
            err_var.set("Set a min, a max, or both.")
            return
        if mn is not None and mx is not None and mn > mx:
            err_var.set("Min can't exceed max.")
            return
        # Replace an existing row on the same attribute (FM behavior).
        self._filter.thresholds = [t for t in self._filter.thresholds
                                   if t.key != key]
        for t, w in list(self._chip_frames):
            if t.key == key:
                w.destroy()
                self._chip_frames.remove((t, w))
        th = AttrThreshold(key=key, label=label, min=mn, max=mx)
        self._filter.thresholds.append(th)
        self._make_chip(th)
        dlg.destroy()
        self._changed()

    def _make_chip(self, th):
        chip = ttk.Frame(self._chips, style="FilterBar.Chip.TFrame",
                         relief="solid", borderwidth=1, padding=(6, 2))
        chip.pack(side="left", padx=3, pady=2)
        ttk.Label(chip, text=th.describe(),
                  style="FilterBar.Chip.TLabel").pack(side="left")
        ttk.Button(chip, text="\u00d7", width=2,
                   style="FilterBar.Chip.TButton",
                   command=lambda: self._remove_threshold(th, chip)).pack(
                       side="left", padx=(4, 0))
        self._chip_frames.append((th, chip))

    def _remove_threshold(self, th, chip):
        self._filter.thresholds = [t for t in self._filter.thresholds
                                   if t is not th]
        chip.destroy()
        self._chip_frames = [(t, w) for t, w in self._chip_frames if t is not th]
        self._changed()
