"""
Roster import wizard for Puck Dynasty.

Lets the user start a career from pre-built Eastside Hockey Manager rosters
(such as xECK29x's Premier Pivot / ECK rosters) or from CSV roster files.

Two source paths:
  * EHM ``database.db`` — schema-tolerant auto-detection with a manual
    column-mapping fallback and a data preview before importing.
  * CSV files (teams.csv + players.csv) — see csv_roster_importer for the
    documented format; the wizard can generate blank templates.

On completion the wizard calls ``on_complete(league, user_team, gm_name)``
with a fully built Puck Dynasty ``League``.
"""

from __future__ import annotations

import os
import queue
import sqlite3
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from modern_ui import AppButton, AppCard, AppColors, AppFonts

STEP_TITLES = ["Source", "Detection", "Preview", "Options", "Import"]

HOW_TO_GET_ECK = (
    "Where to find an EHM database.db:\n"
    "1. In EHM on Steam, subscribe to xECK29x's Premier Pivot Database\n"
    "   (Steam Workshop) and let it download.\n"
    "2. Copy database.db out of the workshop folder, e.g.\n"
    "   .../steamapps/workshop/content/301120/1428241604/database.db\n"
    "   (the number is the workshop item id; copy the file somewhere safe).\n"
    "3. Back here, choose 'EHM database.db' and browse to your copy.\n\n"
    "No EHM install? Use the CSV path instead: download the templates,\n"
    "fill in teams.csv / players.csv, and import those."
)


class RosterImportWizard(tk.Toplevel):
    """Step-by-step importer.  Calls on_complete(league, team, gm) at the end."""

    def __init__(self, parent,
                 on_complete: Callable[[Any, str, str], None]):
        super().__init__(parent)
        self.on_complete = on_complete
        self.title("Import Rosters - Puck Dynasty")
        self.geometry("860x680")
        self.configure(bg=AppColors.BG)
        self.resizable(True, True)
        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass

        # state
        self.source_kind = tk.StringVar(value="ehm")  # ehm | csv
        self.db_path = tk.StringVar(value="")
        self.teams_csv = tk.StringVar(value="")
        self.players_csv = tk.StringVar(value="")
        self.probe = None
        self.manual_overrides: Dict[str, str] = {}
        self.league = None
        self.import_stats: Dict[str, Any] = {}
        self.step = 0
        self._msgq: "queue.Queue" = queue.Queue()
        self._worker: Optional[threading.Thread] = None

        # options
        self.opt_season = tk.IntVar(value=2026)
        self.opt_scope = tk.StringVar(value="nhl_only")
        self.opt_salary_mult = tk.DoubleVar(value=1.0)
        self.opt_staff = tk.BooleanVar(value=True)
        self.opt_free_agents = tk.BooleanVar(value=True)
        self.opt_team = tk.StringVar(value="")
        self.opt_gm = tk.StringVar(value="")

        self._build_chrome()
        self._build_steps()
        self._show_step(0)
        self.after(120, self._pump_queue)

    # -- chrome ------------------------------------------------------
    def _build_chrome(self):
        header = tk.Frame(self, bg=AppColors.BG)
        header.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(header, text="Import Rosters",
                 font=AppFonts.H1, bg=AppColors.BG,
                 fg=AppColors.TEXT_PRIMARY).pack(side="left")
        tk.Label(header, text="Start a career with pre-built EHM rosters",
                 font=AppFonts.SMALL, bg=AppColors.BG,
                 fg=AppColors.TEXT_SECONDARY).pack(side="left", padx=(12, 0))

        self.step_bar = tk.Frame(self, bg=AppColors.BG)
        self.step_bar.pack(fill="x", padx=20, pady=(4, 8))
        self._step_labels: List[tk.Label] = []
        for i, title in enumerate(STEP_TITLES):
            lbl = tk.Label(self.step_bar, text=f"{i+1}. {title}",
                           font=AppFonts.SMALL_BOLD, bg=AppColors.BG,
                           fg=AppColors.TEXT_TERTIARY, padx=8)
            lbl.pack(side="left")
            self._step_labels.append(lbl)

        self.body = tk.Frame(self, bg=AppColors.BG)
        self.body.pack(fill="both", expand=True, padx=20, pady=4)

        nav = tk.Frame(self, bg=AppColors.BG)
        nav.pack(fill="x", padx=20, pady=(4, 16))
        self.back_btn = AppButton(nav, text="Back", style="secondary",
                                  command=self._on_back, width=110)
        self.back_btn.pack(side="left")
        self.next_btn = AppButton(nav, text="Next", style="primary",
                                  command=self._on_next, width=130)
        self.next_btn.pack(side="right")

    def _build_steps(self):
        self.step_frames: List[tk.Frame] = []
        builders = [self._build_step_source, self._build_step_detection,
                    self._build_step_preview, self._build_step_options,
                    self._build_step_import]
        for build in builders:
            f = tk.Frame(self.body, bg=AppColors.BG)
            build(f)
            self.step_frames.append(f)

    def _show_step(self, idx: int):
        self.step = idx
        for i, f in enumerate(self.step_frames):
            f.pack_forget()
        self.step_frames[idx].pack(fill="both", expand=True)
        for i, lbl in enumerate(self._step_labels):
            if i < idx:
                lbl.configure(fg=AppColors.ACCENT)
            elif i == idx:
                lbl.configure(fg=AppColors.TEXT_PRIMARY)
            else:
                lbl.configure(fg=AppColors.TEXT_TERTIARY)
        self.back_btn.configure(state="normal" if idx > 0 else "disabled")
        # redraw next button label
        self.next_btn.destroy()
        label = ("Start Import" if idx == 3 else
                 "Close" if idx == 4 and self.league else "Next")
        self.next_btn = AppButton(self.next_btn.master, text=label,
                                  style="primary", command=self._on_next,
                                  width=130)
        self.next_btn.pack(side="right")
        if idx == 1:
            self._run_detection()
        elif idx == 2:
            self._build_preview()

    # -- step 1: source ----------------------------------------------
    def _build_step_source(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=6)
        inner = card.get_content_frame()
        tk.Label(inner, text="EHM database.db  (recommended)",
                 font=AppFonts.H3, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY).pack(anchor="w")
        tk.Label(inner,
                 text="Point at the database.db from an ECK / Premier Pivot "
                      "roster pack.\nReal NHL players, attributes, clubs and "
                      "contracts are detected automatically.",
                 font=AppFonts.SMALL, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_SECONDARY, justify="left").pack(anchor="w",
                                                                  pady=(4, 8))
        row = tk.Frame(inner, bg=AppColors.BG_ELEVATED)
        row.pack(fill="x")
        AppButton(row, text="Browse...", style="secondary",
                  command=self._browse_db, width=110).pack(side="left")
        tk.Label(row, textvariable=self.db_path, font=AppFonts.CAPTION,
                 bg=AppColors.BG_ELEVATED, fg=AppColors.ACCENT,
                 wraplength=560, justify="left").pack(side="left", padx=10)
        tk.Radiobutton(inner, text="Use EHM database.db", variable=self.source_kind,
                       value="ehm", bg=AppColors.BG_ELEVATED,
                       fg=AppColors.TEXT_PRIMARY,
                       selectcolor=AppColors.BG_HOVER,
                       activebackground=AppColors.BG_ELEVATED).pack(anchor="w",
                                                                   pady=(8, 0))

        card2 = AppCard(parent)
        card2.pack(fill="x", pady=6)
        inner2 = card2.get_content_frame()
        tk.Label(inner2, text="CSV roster files", font=AppFonts.H3,
                 bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY).pack(anchor="w")
        tk.Label(inner2, text="Import hand-built rosters from teams.csv + "
                 "players.csv.",
                 font=AppFonts.SMALL, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_SECONDARY).pack(anchor="w", pady=(4, 8))
        for label, var, cmd in (("teams.csv", self.teams_csv,
                                 self._browse_teams_csv),
                                ("players.csv", self.players_csv,
                                 self._browse_players_csv)):
            r = tk.Frame(inner2, bg=AppColors.BG_ELEVATED)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=AppFonts.SMALL_BOLD,
                     bg=AppColors.BG_ELEVATED,
                     fg=AppColors.TEXT_SECONDARY, width=12).pack(side="left")
            AppButton(r, text="Browse...", style="secondary", command=cmd,
                      width=110).pack(side="left")
            tk.Label(r, textvariable=var, font=AppFonts.CAPTION,
                     bg=AppColors.BG_ELEVATED, fg=AppColors.ACCENT,
                     wraplength=480, justify="left").pack(side="left",
                                                          padx=10)
        r2 = tk.Frame(inner2, bg=AppColors.BG_ELEVATED)
        r2.pack(fill="x", pady=(8, 0))
        AppButton(r2, text="Download CSV templates", style="secondary",
                  command=self._download_templates, width=200).pack(side="left")
        tk.Radiobutton(inner2, text="Use CSV roster files",
                       variable=self.source_kind, value="csv",
                       bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY,
                       selectcolor=AppColors.BG_HOVER,
                       activebackground=AppColors.BG_ELEVATED).pack(anchor="w",
                                                                   pady=(8, 0))

        help_card = AppCard(parent)
        help_card.pack(fill="both", expand=True, pady=6)
        hinner = help_card.get_content_frame()
        tk.Label(hinner, text="How to get ECK roster data",
                 font=AppFonts.H3, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY).pack(anchor="w")
        txt = tk.Text(hinner, height=8, wrap="word", font=AppFonts.SMALL,
                      bg=AppColors.BG, fg=AppColors.TEXT_SECONDARY,
                      relief="flat", padx=8, pady=8)
        txt.insert("1.0", HOW_TO_GET_ECK)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, pady=(6, 0))

    def _browse_db(self):
        p = filedialog.askopenfilename(
            title="Select EHM database.db",
            filetypes=[("EHM database", "*.db"), ("All files", "*.*")])
        if p:
            self.db_path.set(p)
            self.source_kind.set("ehm")

    def _browse_teams_csv(self):
        p = filedialog.askopenfilename(
            title="Select teams.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if p:
            self.teams_csv.set(p)
            self.source_kind.set("csv")

    def _browse_players_csv(self):
        p = filedialog.askopenfilename(
            title="Select players.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if p:
            self.players_csv.set(p)
            self.source_kind.set("csv")

    def _download_templates(self):
        d = filedialog.askdirectory(title="Where to save CSV templates?")
        if not d:
            return
        try:
            from csv_roster_importer import write_templates
            t, pl = write_templates(d)
            messagebox.showinfo(
                "Templates saved",
                f"Templates written to:\n{t}\n{pl}\n\nFill them in, then "
                "come back and import.")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not write templates:\n{exc}")
    # -- step 2: detection -------------------------------------------
    def _build_step_detection(self, parent):
        self.det_status = tk.Label(parent, text="", font=AppFonts.BODY,
                                   bg=AppColors.BG, fg=AppColors.TEXT_SECONDARY,
                                   wraplength=780, justify="left")
        self.det_status.pack(anchor="w", pady=(4, 8))
        card = AppCard(parent)
        card.pack(fill="both", expand=True, pady=6)
        inner = card.get_content_frame()
        self.det_report = tk.Text(inner, wrap="word", font=("Consolas", 10),
                                  bg=AppColors.BG, fg=AppColors.TEXT_SECONDARY,
                                  relief="flat", padx=10, pady=10,
                                  state="disabled")
        self.det_report.pack(fill="both", expand=True)
        # manual mapping fallback (hidden unless needed)
        self.manual_frame = tk.Frame(parent, bg=AppColors.BG)

    def _set_report(self, text: str):
        self.det_report.configure(state="normal")
        self.det_report.delete("1.0", "end")
        self.det_report.insert("1.0", text)
        self.det_report.configure(state="disabled")

    def _run_detection(self):
        self.manual_frame.pack_forget()
        if self.source_kind.get() == "csv":
            self._detect_csv()
            return
        path = self.db_path.get().strip()
        if not path:
            self.det_status.configure(
                text="No database selected. Go back and browse to a "
                     "database.db file.")
            self._set_report("")
            return
        self.det_status.configure(text="Analyzing database.db ...")
        self._set_report("Reading schema, please wait.")
        from ehm_roster_importer import probe_database
        self._run_thread(lambda: ("probe", probe_database(path)))

    def _detect_csv(self):
        from csv_roster_importer import preview_csv
        t, pl = self.teams_csv.get().strip(), self.players_csv.get().strip()
        if not t or not pl:
            self.det_status.configure(
                text="Select both teams.csv and players.csv to continue.")
            self._set_report("")
            return
        import csv as _csv, os as _os
        try:
            with open(t, newline="", encoding="utf-8-sig") as fh:
                teams = list(_csv.DictReader(fh))
            with open(pl, newline="", encoding="utf-8-sig") as fh:
                players = list(_csv.DictReader(fh))
        except Exception as exc:
            self.det_status.configure(text=f"Could not read CSV files: {exc}")
            self._set_report("")
            return
        named = [r for r in players
                 if (r.get("first_name") or "").strip()
                 and (r.get("last_name") or "").strip()]
        self.det_status.configure(
            text=f"CSV check passed: {len(teams)} teams, {len(named)} players "
                 f"with names ({len(players) - len(named)} rows skipped).")
        lines = [f"Teams ({len(teams)}):"]
        lines += [f"  - {(r.get('team_name') or '?').strip()}"
                  for r in teams[:12]]
        if len(teams) > 12:
            lines.append(f"  ... and {len(teams) - 12} more")
        lines.append("")
        lines.append(f"Sample players:")
        for r in preview_csv(pl, 8):
            lines.append(f"  - {r['name']} ({r['pos']}, {r['age']}) - "
                         f"{r['team']}")
        self._set_report("\n".join(lines))
        self.probe = None

    def _on_probe_done(self, probe):
        self.probe = probe
        rep = probe.report()
        self._set_report(rep)
        if probe.is_sqlite and probe.confidence >= 0.5:
            self.det_status.configure(
                text=f"Database recognized (confidence "
                     f"{probe.confidence:.0%}). Continue to preview the data.")
        elif probe.is_sqlite:
            self.det_status.configure(
                text=f"Low detection confidence ({probe.confidence:.0%}). "
                     "You can map the columns manually below.")
            self._show_manual_mapping()
        else:
            self.det_status.configure(
                text="This file is not a readable SQLite EHM database. "
                     "Check the help on step 1, or use the CSV path instead.")
            self._set_report(rep)

    def _show_manual_mapping(self):
        for child in self.manual_frame.winfo_children():
            child.destroy()
        card = AppCard(self.manual_frame)
        card.pack(fill="x", pady=6)
        inner = card.get_content_frame()
        tk.Label(inner, text="Manual column mapping",
                 font=AppFonts.H3, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY).pack(anchor="w")
        tk.Label(inner, text="Auto-detection was unsure. Pick the right "
                 "table and columns:",
                 font=AppFonts.SMALL, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_SECONDARY).pack(anchor="w", pady=(2, 8))
        tables = sorted(self.probe.tables.keys())
        cols_for: Dict[str, List[str]] = {}
        path = self.db_path.get().strip()
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            for t in tables:
                try:
                    cols_for[t] = [r[1] for r in conn.execute(
                        f'PRAGMA table_info("{t}")')]
                except sqlite3.Error:
                    cols_for[t] = []
            conn.close()
        except sqlite3.Error:
            cols_for = {t: [] for t in tables}

        form = tk.Frame(inner, bg=AppColors.BG_ELEVATED)
        form.pack(fill="x")
        self._map_vars: Dict[str, tk.StringVar] = {}
        fields = [("staff_table", "Staff table", tables, True),
                  ("first_name", "First name column", [], False),
                  ("last_name", "Last name column", [], False),
                  ("club_contracted", "Club column", [], False),
                  ("dob", "Date of birth column", [], False)]

        def refill(*_a):
            t = self._map_vars["staff_table"].get()
            cols = [""] + cols_for.get(t, [])
            for key, _label, _opts, _is_t in fields[1:]:
                cb = self._map_cbs[key]
                cb["values"] = cols
                cur = self._map_vars[key].get()
                if cur not in cols:
                    self._map_vars[key].set("")

        self._map_cbs: Dict[str, ttk.Combobox] = {}
        for key, label, opts, _ in fields:
            r = tk.Frame(form, bg=AppColors.BG_ELEVATED)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=AppFonts.SMALL_BOLD,
                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                     width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value="")
            if key == "staff_table" and self.probe.detected.get("staff"):
                cur = self.probe.detected["staff"].physical
                if cur in opts:
                    var.set(cur)
            self._map_vars[key] = var
            cb = ttk.Combobox(r, textvariable=var, values=opts, width=40,
                              state="readonly")
            cb.pack(side="left")
            self._map_cbs[key] = cb
        self._map_vars["staff_table"].trace_add("write", refill)
        refill()
        AppButton(inner, text="Apply mapping", style="primary",
                  command=self._apply_manual_mapping,
                  width=160).pack(anchor="w", pady=(10, 0))
        self.manual_frame.pack(fill="x", pady=6)

    def _apply_manual_mapping(self):
        from ehm_roster_importer import retarget_staff_table
        table = self._map_vars["staff_table"].get()
        if not table:
            messagebox.showwarning("Mapping", "Choose a staff table first.")
            return
        path = self.db_path.get().strip()
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            retarget_staff_table(self.probe, conn, table)
            conn.close()
        except sqlite3.Error as exc:
            messagebox.showerror("Mapping", f"Could not re-read table:\n{exc}")
            return
        for logical in ("first_name", "last_name", "club_contracted", "dob"):
            val = self._map_vars[logical].get().strip()
            if val:
                self.probe.field_map[logical] = val
        self._set_report(self.probe.report())
        self.det_status.configure(
            text=f"Mapping applied (confidence "
                 f"{self.probe.confidence:.0%}). Continue to preview.")

    # -- step 3: preview ---------------------------------------------
    def _build_step_preview(self, parent):
        self.prev_summary = tk.Label(parent, text="", font=AppFonts.BODY,
                                     bg=AppColors.BG,
                                     fg=AppColors.TEXT_SECONDARY,
                                     wraplength=780, justify="left")
        self.prev_summary.pack(anchor="w", pady=(4, 8))
        card = AppCard(parent)
        card.pack(fill="both", expand=True, pady=6)
        inner = card.get_content_frame()
        cols = ("name", "club", "pos", "overall", "skating", "shooting",
                "passing")
        self.prev_tree = ttk.Treeview(inner, columns=cols, show="headings",
                                      height=14)
        widths = {"name": 200, "club": 200, "pos": 50, "overall": 70,
                  "skating": 70, "shooting": 70, "passing": 70}
        heads = {"name": "Player", "club": "Club", "pos": "Pos",
                 "overall": "Overall", "skating": "Skating",
                 "shooting": "Shooting", "passing": "Passing"}
        for c in cols:
            self.prev_tree.heading(c, text=heads[c])
            self.prev_tree.column(c, width=widths[c], anchor="center" if
                                 c != "name" and c != "club" else "w")
        vs = ttk.Scrollbar(inner, orient="vertical",
                           command=self.prev_tree.yview)
        self.prev_tree.configure(yscrollcommand=vs.set)
        self.prev_tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

    def _build_preview(self):
        for item in self.prev_tree.get_children():
            self.prev_tree.delete(item)
        if self.source_kind.get() == "csv":
            from csv_roster_importer import preview_csv
            rows = preview_csv(self.players_csv.get().strip(), 40)
            self.prev_summary.configure(
                text=f"{len(rows)} sample rows from players.csv "
                     "(overall shown after import).")
            for r in rows:
                self.prev_tree.insert("", "end",
                                      values=(r["name"], r["team"], r["pos"],
                                              "-", "-", "-", "-"))
            return
        if not self.probe or not self.probe.is_sqlite:
            self.prev_summary.configure(text="No database analyzed yet.")
            return
        from ehm_roster_importer import preview_players
        rows = preview_players(self.db_path.get().strip(), self.probe, 40)
        self.prev_summary.configure(
            text=f"Top {len(rows)} players by current ability "
                 "(overall on the 1-100 display scale).")
        for r in rows:
            self.prev_tree.insert("", "end",
                                  values=(r["name"], r["club"], r["pos"],
                                          r["overall"], r["skating"],
                                          r["shooting"], r["passing"]))

    # -- step 4: options ---------------------------------------------
    def _build_step_options(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=6)
        inner = card.get_content_frame()
        tk.Label(inner, text="Import options", font=AppFonts.H3,
                 bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY).pack(anchor="w", pady=(0, 8))

        def opt_row(label):
            r = tk.Frame(inner, bg=AppColors.BG_ELEVATED)
            r.pack(fill="x", pady=4)
            tk.Label(r, text=label, font=AppFonts.SMALL_BOLD,
                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                     width=22, anchor="w").pack(side="left")
            return r

        r = opt_row("Season starts")
        ttk.Spinbox(r, from_=2020, to=2040, textvariable=self.opt_season,
                    width=8).pack(side="left")

        r = opt_row("Teams to import")
        ttk.Combobox(r, textvariable=self.opt_scope, state="readonly",
                     width=28,
                     values=["nhl_only", "nhl_plus_affiliates"]).pack(
                         side="left")
        tk.Label(r, text="(nhl_only = NHL clubs; nhl_plus_affiliates also "
                 "fills AHL affiliates)",
                 font=AppFonts.CAPTION, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_TERTIARY).pack(side="left", padx=8)

        r = opt_row("Salary multiplier")
        ttk.Spinbox(r, from_=0.1, to=5.0, increment=0.1,
                    textvariable=self.opt_salary_mult,
                    width=8).pack(side="left")
        tk.Label(r, text="(scale EHM wages into Puck Dynasty cap dollars)",
                 font=AppFonts.CAPTION, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_TERTIARY).pack(side="left", padx=8)

        tk.Checkbutton(inner, text="Import non-player staff (coaches, scouts)",
                       variable=self.opt_staff, bg=AppColors.BG_ELEVATED,
                       fg=AppColors.TEXT_PRIMARY,
                       selectcolor=AppColors.BG_HOVER,
                       activebackground=AppColors.BG_ELEVATED,
                       font=AppFonts.SMALL).pack(anchor="w", pady=4)
        tk.Checkbutton(inner, text="Include free agents",
                       variable=self.opt_free_agents,
                       bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY,
                       selectcolor=AppColors.BG_HOVER,
                       activebackground=AppColors.BG_ELEVATED,
                       font=AppFonts.SMALL).pack(anchor="w", pady=4)

        r = opt_row("Your team")
        self.team_combo = ttk.Combobox(r, textvariable=self.opt_team,
                                      state="readonly", width=30)
        self.team_combo.pack(side="left")

        r = opt_row("GM name")
        tk.Entry(r, textvariable=self.opt_gm, width=30,
                 bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY,
                 insertbackground=AppColors.TEXT_PRIMARY,
                 relief="flat").pack(side="left", ipady=4)

        note = AppCard(parent)
        note.pack(fill="x", pady=6)
        ninner = note.get_content_frame()
        tk.Label(ninner, text="A note on compatibility",
                 font=AppFonts.H3, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY).pack(anchor="w")
        tk.Label(ninner,
                 text="Puck Dynasty reads the open EHM database format "
                      "directly from database.db. Rosters are matched to the "
                      "32 NHL clubs by name; unmatched clubs land in free "
                      "agency. Player attributes are converted from EHM's "
                      "1-20 scale to Puck Dynasty's display scale.",
                 font=AppFonts.SMALL, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_SECONDARY, wraplength=740,
                 justify="left").pack(anchor="w", pady=(4, 0))

    def _refresh_team_options(self):
        names: List[str] = []
        if self.source_kind.get() == "csv":
            import csv as _csv
            try:
                with open(self.teams_csv.get().strip(), newline="",
                          encoding="utf-8-sig") as fh:
                    for r in _csv.DictReader(fh):
                        n = (r.get("team_name") or "").strip()
                        if n:
                            names.append(n)
            except Exception:
                pass
        else:
            # best effort: the 32 NHL names (import matches clubs to these)
            try:
                from game_classes import League
                names = [t.team_name for t in League("x").teams]
            except Exception:
                names = []
        self.team_combo["values"] = names
        if names and self.opt_team.get() not in names:
            self.opt_team.set(names[0])

    # -- step 5: import ----------------------------------------------
    def _build_step_import(self, parent):
        self.imp_status = tk.Label(parent, text="", font=AppFonts.BODY,
                                   bg=AppColors.BG,
                                   fg=AppColors.TEXT_SECONDARY,
                                   wraplength=780, justify="left")
        self.imp_status.pack(anchor="w", pady=(4, 8))
        card = AppCard(parent)
        card.pack(fill="both", expand=True, pady=6)
        inner = card.get_content_frame()
        self.imp_log = tk.Text(inner, wrap="word", font=("Consolas", 10),
                               bg=AppColors.BG, fg=AppColors.TEXT_SECONDARY,
                               relief="flat", padx=10, pady=10,
                               state="disabled")
        self.imp_log.pack(fill="both", expand=True)
        self.imp_progress = ttk.Progressbar(parent, mode="indeterminate")
        self.imp_progress.pack(fill="x", pady=(6, 0))

    def _log(self, text: str):
        self.imp_log.configure(state="normal")
        self.imp_log.insert("end", text + "\n")
        self.imp_log.see("end")
        self.imp_log.configure(state="disabled")

    def _start_import(self):
        self._log("Starting import...")
        self.imp_progress.start(12)
        self.imp_status.configure(text="Importing rosters, please wait.")
        opts = dict(season_year=self.opt_season.get(),
                    team_scope=self.opt_scope.get(),
                    salary_multiplier=self.opt_salary_mult.get(),
                    import_staff=self.opt_staff.get(),
                    include_free_agents=self.opt_free_agents.get())
        kind = self.source_kind.get()
        if kind == "csv":
            t, pl = (self.teams_csv.get().strip(),
                     self.players_csv.get().strip())

            def job():
                from csv_roster_importer import import_league_from_csv
                return ("imported", import_league_from_csv(
                    t, pl, season_year=opts["season_year"]))
        else:
            path, probe = self.db_path.get().strip(), self.probe

            def job():
                from ehm_roster_importer import import_league_from_db
                return ("imported", import_league_from_db(
                    path, probe=probe, **opts))
        self._run_thread(job)

    def _on_import_done(self, result):
        self.imp_progress.stop()
        league, stats = result
        self.league = league
        self.import_stats = stats
        lines = [f"Imported {stats.get('players', 0)} players "
                 f"({stats.get('skaters', 0)} skaters, "
                 f"{stats.get('goalies', 0)} goalies).",
                 f"Matched {stats.get('matched_clubs', 0)} clubs, "
                 f"{stats.get('free_agents', 0)} free agents, "
                 f"{stats.get('staff', 0)} staff members."]
        if stats.get("errors"):
            lines.append(f"{len(stats['errors'])} warnings "
                         f"(see log).")
        for e in stats.get("errors", [])[:10]:
            self._log(f"warning: {e}")
        self.imp_status.configure(text="\n".join(lines))
        for line in lines:
            self._log(line)
        self._log("Done. Press 'Start Career' to begin.")
        # relabel the nav button to finish
        nav = self.next_btn.master
        self.next_btn.destroy()
        self.next_btn = AppButton(nav, text="Start Career",
                                  style="primary", command=self._on_next,
                                  width=140)
        self.next_btn.pack(side="right")

    # -- threading ---------------------------------------------------
    def _run_thread(self, job):
        if self._worker and self._worker.is_alive():
            return
        def runner():
            try:
                self._msgq.put(job())
            except Exception as exc:  # noqa: BLE001
                self._msgq.put(("error", repr(exc)))
        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def _pump_queue(self):
        try:
            while True:
                kind, payload = self._msgq.get_nowait()
                if kind == "probe":
                    self._on_probe_done(payload)
                elif kind == "imported":
                    self._on_import_done(payload)
                elif kind == "error":
                    self.det_status.configure(text=f"Error: {payload}")
                    self._set_report("")
                    self.imp_progress.stop()
                    self._log(f"Error: {payload}")
        except queue.Empty:
            pass
        self.after(120, self._pump_queue)

    # -- navigation --------------------------------------------------
    def _on_back(self):
        if self.step > 0:
            self._show_step(self.step - 1)

    def _on_next(self):
        if self.step == 0:
            if self.source_kind.get() == "ehm" and not self.db_path.get():
                messagebox.showwarning(
                    "No file selected",
                    "Browse to a database.db file first, or choose the CSV "
                    "path.")
                return
            if self.source_kind.get() == "csv" and not (
                    self.teams_csv.get() and self.players_csv.get()):
                messagebox.showwarning(
                    "No files selected",
                    "Select both teams.csv and players.csv (or download the "
                    "templates first).")
                return
            self._show_step(1)
        elif self.step == 1:
            if self.source_kind.get() == "ehm":
                if not self.probe or not self.probe.is_sqlite:
                    messagebox.showwarning(
                        "Not ready",
                        "The database could not be read. Pick a valid "
                        "database.db or use the CSV path.")
                    return
                if self.probe.confidence < 0.3 and not any(
                        self.probe.field_map.values()):
                    messagebox.showwarning(
                        "Not ready",
                        "Detection found no usable player data. Try the "
                        "manual column mapping above, or the CSV path.")
                    return
            self._show_step(2)
        elif self.step == 2:
            self._refresh_team_options()
            self._show_step(3)
        elif self.step == 3:
            if not self.opt_team.get():
                messagebox.showwarning("Pick your team",
                                       "Choose the team you want to manage.")
                return
            self._show_step(4)
            self._start_import()
        elif self.step == 4:
            if self.league is None:
                return  # import still running or failed
            team = self.opt_team.get()
            gm = self.opt_gm.get().strip() or "GM"
            self.grab_release()
            self.destroy()
            self.on_complete(self.league, team, gm)


def open_roster_import_wizard(parent,
                              on_complete: Callable[[Any, str, str], None]):
    """Open the import wizard as a modal dialog."""
    RosterImportWizard(parent, on_complete)
