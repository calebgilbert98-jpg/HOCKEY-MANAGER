# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Training Camp screen (EHM-style camp ratings + scrimmages).

TrainingCampWindow(InGamePopup): the user's club camp report --
per-scrimmage 1-10 player ratings, camp averages, standout flags, and
the Red vs White scrimmage log with 3 stars. Data comes from
training_camp.py (player.camp_ratings / team.camp_scrimmages), which
runs every September 12-30 in the daily advance.

Opened via app.open_training_camp_window() (Team menu).
"""

from tkinter import ttk

import customtkinter as ctk
from popup_system import InGamePopup

try:
    import training_camp as _tc
except Exception:
    _tc = None


class TrainingCampWindow(InGamePopup):
    """Popup wrapper: the user's training camp report."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Training Camp")
        self.app = parent
        try:
            self.geometry("1050x640")
        except Exception:
            pass

        team = getattr(parent, "user_team", None)
        tname = getattr(team, "team_name", "Your Club") if team else "Your Club"
        try:
            year = getattr(getattr(parent, "current_date", None), "year", "")
        except Exception:
            year = ""

        header = ctk.CTkLabel(
            self, text=f"Training Camp -- {tname} ({year})",
            font=(getattr(parent, "FONT_FAMILY", "Arial"), 16, "bold"))
        header.pack(anchor="w", padx=14, pady=(10, 2))

        self._status = ctk.CTkLabel(
            self, text="", font=(getattr(parent, "FONT_FAMILY", "Arial"), 11),
            text_color="gray70")
        self._status.pack(anchor="w", padx=14, pady=(0, 6))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=6)

        ratings_frame = ttk.Frame(notebook)
        scrims_frame = ttk.Frame(notebook)
        notebook.add(ratings_frame, text="Camp Ratings")
        notebook.add(scrims_frame, text="Scrimmages")

        self._ratings_tree = ttk.Treeview(ratings_frame, show="headings")
        self._ratings_tree.pack(fill="both", expand=True, padx=6, pady=6)

        self._scrims_tree = ttk.Treeview(
            scrims_frame, columns=("date", "score", "stars"), show="headings")
        for cid, label, w in (("date", "Date", 110), ("score", "Red - White", 120),
                              ("stars", "3 Stars", 600)):
            self._scrims_tree.heading(cid, text=label)
            self._scrims_tree.column(cid, width=w, anchor="w")
        self._scrims_tree.pack(fill="both", expand=True, padx=6, pady=6)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btns, text="Refresh", width=120,
                      command=self.refresh).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Close", width=120,
                      command=self.destroy).pack(side="right", padx=4)

        self.refresh()

    # -- data -------------------------------------------------------------
    def refresh(self):
        team = getattr(self.app, "user_team", None)
        if team is None or _tc is None:
            self._status.configure(text="No camp data available.")
            return
        try:
            rows = _tc.get_camp_table(team)
        except Exception:
            rows = []
        scrims = list(getattr(team, "camp_scrimmages", None) or [])

        n_games = max((len(r) for _, r, _, _ in rows), default=0)
        try:
            cur = getattr(self.app, "current_date", None)
            if _tc.is_camp_day(cur):
                status = (f"Camp in session -- {len(scrims)} scrimmage(s) played. "
                          f"Camp closes September 30; cuts follow in early October.")
            elif rows:
                status = (f"Final camp report -- {len(rows)} players attended, "
                          f"{len(scrims)} scrimmages. Ratings below.")
            else:
                status = "Camp opens September 12."
        except Exception:
            status = ""
        self._status.configure(text=status)

        # Ratings table: Player | Age | Pos | OVR | S1..Sn | Avg | Cond | Note
        cols = ["name", "age", "pos", "ovr"] + \
            [f"S{i+1}" for i in range(n_games)] + ["avg", "cond", "note"]
        self._ratings_tree["columns"] = cols
        headers = {"name": ("Player", 190), "age": ("Age", 45),
                   "pos": ("Pos", 60), "ovr": ("OVR", 50),
                   "avg": ("Avg", 55), "cond": ("Cond", 70),
                   "note": ("Note", 130)}
        for c in cols:
            if c in headers:
                label, w = headers[c]
            else:
                label, w = c, 52
            self._ratings_tree.heading(c, text=label)
            self._ratings_tree.column(c, width=w,
                                      anchor="w" if c in ("name", "note")
                                      else "center")
        self._ratings_tree.delete(*self._ratings_tree.get_children())
        for p, ratings, avg, standout in rows:
            try:
                vals = [getattr(p, "full_name", "?"),
                        getattr(p, "age", "?"),
                        getattr(getattr(p, "primary_position", None),
                                "name", ""),
                        p.overall_rating()]
                for i in range(n_games):
                    vals.append(f"{ratings[i]:.1f}" if i < len(ratings)
                                else "--")
                vals.append(f"{avg:.1f}")
                # W6: canonical condition indicator (defensive -- never crashes)
                try:
                    import condition_ui as _cu
                    _c = _cu.get_condition(p)
                    vals.append(f"{_c} ({_cu.condition_label(_c)})")
                except Exception:
                    vals.append("--")
                note = ""
                if standout:
                    note = "Standout"
                elif avg and avg <= 4.5 and len(ratings) >= 2:
                    note = "Poor camp"
                elif (int(getattr(p, "age", 99) or 99) <= 21 and avg >= 7.0
                        and len(ratings) >= 2):
                    note = "Pushing for a spot"
                vals.append(note)
                self._ratings_tree.insert("", "end", values=vals)
            except Exception:
                continue
        if not rows:
            self._ratings_tree.insert("", "end", values=(
                "No camp data yet -- camp opens September 12.", "", "", "",
                *[""] * (n_games + 3)))

        # Scrimmage log
        self._scrims_tree.delete(*self._scrims_tree.get_children())
        for s in scrims:
            try:
                self._scrims_tree.insert("", "end", values=(
                    s.get("date", ""),
                    f"{s.get('red', 0)} - {s.get('white', 0)}",
                    ", ".join(s.get("stars", []) or [])))
            except Exception:
                continue
        if not scrims:
            self._scrims_tree.insert("", "end", values=(
                "No scrimmages played yet.", "", ""))
