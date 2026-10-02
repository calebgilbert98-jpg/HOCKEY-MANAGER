# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# gm_relationships_window.py
# GM Relationships dashboard — surfaces the GM reputation system (Wave B D48)
# in the UI. Stature, pairwise respect/heat, and trend arrows turn the hidden
# respect tax into a played system.
#
# Read-only dashboard. All data comes from reputation_system.py; nothing is
# reimplemented here. Never raises on missing data.

from tkinter import ttk

import customtkinter as ctk

from popup_system import InGamePopup

import reputation_system as rs


# Trend arrow glyphs
_TREND_ARROW = {
    "warming": "\u2191",   # ↑
    "cooling": "\u2193",   # ↓
    "steady": "\u2192",    # →
}

# Tier colors for the respect tier label
_TIER_COLORS = {
    "warm": "#4CAF50",      # green
    "cordial": "#8BC34A",   # light green
    "wary": "#FF9800",      # orange
    "cold": "#F44336",      # red
}


def _safe_int(fn, *args, default=0):
    """Call fn(*args), return int or default. Never raises."""
    try:
        return int(fn(*args))
    except Exception:
        return default


def _safe_str(fn, *args, default=""):
    """Call fn(*args), return str or default. Never raises."""
    try:
        v = fn(*args)
        return str(v) if v is not None else default
    except Exception:
        return default


def _gm_name(team):
    """Best-effort GM name for a team. Never raises."""
    try:
        gm = rs._team_gm_staff(team)
        if gm is not None:
            name = getattr(gm, "full_name", None) or getattr(gm, "name", None)
            if name:
                return str(name)
    except Exception:
        pass
    try:
        tname = getattr(team, "team_name", "") or ""
        return f"{tname} GM"
    except Exception:
        return "Unknown GM"


def _team_display_name(team):
    """Best-effort team display name. Never raises."""
    try:
        return str(getattr(team, "team_name", "Unknown") or "Unknown")
    except Exception:
        return "Unknown"


class GMRelationshipsView(ctk.CTkFrame):
    """GM Relationships dashboard — what every other GM thinks of you.

    Columns: Team | GM | Stature | Respect | Tier | Heat | Trend
    Click a column header to sort. Color-coded: green = high respect,
    red = high heat.
    """

    COLUMNS = ("team", "gm", "stature", "respect", "tier", "heat", "trend")
    HEADERS = {
        "team": "Team",
        "gm": "GM",
        "stature": "Stature",
        "respect": "Respect",
        "tier": "Tier",
        "heat": "Heat",
        "trend": "Trend",
    }

    def __init__(self, parent, league=None, user_team=None, app=None):
        from ctk_theme import (
            init_ctk_theme, heading, body,
            BG, PANEL, CARD, BORDER, TEXT, TEXT_DIM,
            GREEN, RED, GOLD,
        )
        self._ct = dict(BG=BG, PANEL=PANEL, CARD=CARD, BORDER=BORDER,
                        TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        GREEN=GREEN, RED=RED, GOLD=GOLD)
        self._heading = heading
        self._body = body
        init_ctk_theme()

        ctk.CTkFrame.__init__(self, parent)
        self.configure(fg_color=BG)
        self._league = league
        self._user_team = user_team
        self.app = app if app is not None else parent

        self._sort_col = "respect"
        self._sort_rev = True  # default: highest respect first
        self._rows = []  # list of dicts

        self._setup_tree_style()
        self._create_interface()
        self.refresh()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        ct = self._ct
        style = ttk.Style(self)
        style.configure(
            "GMRels.Treeview",
            background=ct["CARD"], fieldbackground=ct["CARD"],
            foreground=ct["TEXT"], rowheight=26,
            borderwidth=0, relief="flat",
        )
        style.configure(
            "GMRels.Treeview.Heading",
            background=ct["PANEL"], foreground=ct["TEXT"],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0, relief="flat",
        )
        style.map("GMRels.Treeview",
                  background=[("selected", ct["BORDER"])])
        # Row tags for color coding
        style.configure("GMRels.Treeview", foreground=ct["TEXT"])
        self._tree_tags = {
            "respect_high": {"foreground": "#4CAF50"},
            "respect_low": {"foreground": "#F44336"},
            "heat_high": {"foreground": "#F44336"},
            "heat_low": {"foreground": "#4CAF50"},
        }

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    def _create_interface(self):
        ct = self._ct

        # Header: title + own stature
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        self._heading(header, text="GM Relationships").pack(
            anchor="w", side="left")

        # Own stature badge
        own_stature = _safe_int(rs.gm_stature, self._user_team, default=50)
        stature_lbl = ctk.CTkLabel(
            header,
            text=f"Your stature: {own_stature}/100",
            font=("Segoe UI", 12, "bold"),
            text_color=ct["GOLD"],
        )
        stature_lbl.pack(anchor="e", side="right", padx=8)

        # Explainer
        explainer = (
            "Stature: your league-wide reputation (0-100).  "
            "Respect: how this GM views you (-100 to 100).  "
            "Heat: personal friction (0-100).  "
            "Trend: which way respect is moving (↑ warming, ↓ cooling, → steady).  "
            "Respect decays toward your stature baseline over time."
        )
        self._body(self, text=explainer, wraplength=900).pack(
            anchor="w", padx=16, pady=(0, 8))

        # Treeview
        tree_frame = ctk.CTkFrame(self, fg_color=ct["PANEL"], corner_radius=10)
        tree_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self._tree = ttk.Treeview(
            tree_frame, columns=self.COLUMNS, show="headings",
            style="GMRels.Treeview",
        )
        for col in self.COLUMNS:
            self._tree.heading(
                col, text=self.HEADERS[col],
                command=lambda c=col: self._on_sort(c),
            )
            # Column widths
            w = {"team": 180, "gm": 160, "stature": 70, "respect": 70,
                 "tier": 80, "heat": 60, "trend": 60}.get(col, 100)
            anchor = "center" if col not in ("team", "gm") else "w"
            self._tree.column(col, width=w, anchor=anchor, stretch=True)

        # Scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True,
                        padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Configure row tags
        for tag, kw in self._tree_tags.items():
            self._tree.tag_configure(tag, **kw)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _collect_rows(self):
        """Build the row list from reputation_system. Never raises."""
        rows = []
        try:
            teams = list(getattr(self._league, "teams", []) or [])
        except Exception:
            teams = []
        user_id = None
        try:
            user_id = getattr(self._user_team, "id", None)
        except Exception:
            pass

        for team in teams:
            try:
                # Skip the user's own team
                tid = getattr(team, "id", None)
                if tid is not None and tid == user_id:
                    continue
                # Also skip by identity in case ids are missing
                if team is self._user_team:
                    continue

                stature = _safe_int(rs.gm_stature, team, default=50)
                respect = _safe_int(rs.gm_gm_respect, self._league,
                                    self._user_team, team, default=0)
                heat = _safe_int(rs.gm_gm_heat, self._league,
                                 self._user_team, team, default=0)
                tier = _safe_str(rs.respect_tier_label, respect,
                                 default="wary")
                trend = _safe_str(rs.respect_trend, self._league,
                                  self._user_team, team, default="steady")
                arrow = _TREND_ARROW.get(trend, "\u2192")

                rows.append({
                    "team": _team_display_name(team),
                    "gm": _gm_name(team),
                    "stature": stature,
                    "respect": respect,
                    "tier": tier,
                    "heat": heat,
                    "trend": trend,
                    "arrow": arrow,
                })
            except Exception:
                continue
        return rows

    def _sort_key(self, row, col):
        if col in ("stature", "respect", "heat"):
            try:
                return float(row[col])
            except Exception:
                return 0.0
        return str(row.get(col, "")).lower()

    def _on_sort(self, col):
        """Column header click: sort by that column, toggle direction."""
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            # Numeric columns default descending, text ascending
            self._sort_rev = col in ("stature", "respect", "heat")
        self._populate()

    def _row_tags(self, row):
        """Color-coding tags for a row."""
        tags = []
        try:
            if row["respect"] >= 50:
                tags.append("respect_high")
            elif row["respect"] <= -25:
                tags.append("respect_low")
        except Exception:
            pass
        try:
            if row["heat"] >= 60:
                tags.append("heat_high")
            elif row["heat"] <= 20:
                tags.append("heat_low")
        except Exception:
            pass
        return tuple(tags)

    def _populate(self):
        """Fill the treeview from self._rows, sorted. Never raises."""
        try:
            self._tree.delete(*self._tree.get_children())
        except Exception:
            return
        try:
            col = self._sort_col
            rev = self._sort_rev
            ordered = sorted(self._rows,
                             key=lambda r: self._sort_key(r, col),
                             reverse=rev)
        except Exception:
            ordered = self._rows
        for row in ordered:
            try:
                values = (
                    row["team"],
                    row["gm"],
                    row["stature"],
                    f"{row['respect']:+d}",
                    row["tier"].capitalize(),
                    row["heat"],
                    row["arrow"],
                )
                self._tree.insert("", "end", values=values,
                                  tags=self._row_tags(row))
            except Exception:
                continue

    def refresh(self):
        """Re-collect and re-populate. Never raises."""
        try:
            self._rows = self._collect_rows()
            self._populate()
        except Exception:
            pass


class GMRelationshipsWindow(InGamePopup):
    """Popup wrapper around GMRelationshipsView (for non-screen use)."""

    def __init__(self, parent, league=None, user_team=None, *args, **kwargs):
        super().__init__(parent)
        self.title("GM Relationships")
        self.geometry("900x600")
        self.minsize(760, 480)
        self._view = GMRelationshipsView(
            self, league=league, user_team=user_team, app=parent,
            *args, **kwargs)
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return super().__getattr__(name)


def show_gm_relationships(parent, league, user_team):
    """Open the GM Relationships dashboard as a Toplevel.

    Read-only view of stature / respect / heat / trend for all 31 rival
    GMs. Never raises — returns the window or None.
    """
    try:
        win = GMRelationshipsWindow(parent, league=league,
                                    user_team=user_team)
        try:
            win.grab_set()
        except Exception:
            pass
        return win
    except Exception:
        return None
