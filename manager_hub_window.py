# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Manager Hub UI: Football Manager-style career screens for Puck Dynasty.

Tabs: Board, Squad, Training, Prospects, Press, Profile.
Dialogs: TeamTalkDialog, PressConferenceDialog, OppositionReportDialog.
"""

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup
from datetime import date
from typing import List

import customtkinter as ctk

import manager_career as mc
from player_context_menu import PlayerContextMenu


class ManagerHubView(ctk.CTkFrame):
    """FM-style manager hub with tabbed career screens."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ManagerHubWindow wrapper
        self.career = self.app.career
        try:
            self.configure(fg_color=self.app.BG_COLOR)
        except Exception:
            pass

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.notebook = notebook

        self._build_board_tab(notebook)
        self._build_squad_tab(notebook)
        self._build_training_tab(notebook)
        self._build_prospects_tab(notebook)
        self._build_press_tab(notebook)
        self._build_profile_tab(notebook)

    # ------------------------------------------------------------------

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()
    def _build_board_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Board  ")
        board = self.career.board

        ttk.Label(frame, text="Board Confidence",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")
        self.conf_bar = ttk.Progressbar(frame, length=400, maximum=100,
                                        value=board.confidence)
        self.conf_bar.pack(anchor="w", pady=5)
        self.conf_label = ttk.Label(
            frame, text=f"{board.confidence}/100 — {board.job_status}",
            font=("Helvetica", 11))
        self.conf_label.pack(anchor="w")

        ttk.Label(frame, text="Season expectation:",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(15, 2))
        exp_var = tk.StringVar(value=board.expectation or "playoffs")
        exp_combo = ttk.Combobox(frame, textvariable=exp_var,
                                 values=list(mc.EXPECTATIONS.keys()),
                                 state="readonly", width=25)
        exp_combo.pack(anchor="w")

        def _save_exp():
            board.set_expectation(exp_var.get())
            messagebox.showinfo("Board",
                                f"Expectation set: {mc.EXPECTATIONS[board.expectation]['label']}")
            self._refresh_board()

        ttk.Button(frame, text="Set Expectation",
                   command=_save_exp).pack(anchor="w", pady=5)

        self.exp_desc = ttk.Label(frame, text="", wraplength=600,
                                  font=("Helvetica", 10, "italic"))
        self.exp_desc.pack(anchor="w", pady=5)

        ttk.Label(frame, text="Season record:",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.record_label = ttk.Label(frame, text="", font=("Helvetica", 11))
        self.record_label.pack(anchor="w")

        ttk.Label(frame, text="Latest board review:",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.review_label = ttk.Label(frame, text="", wraplength=600,
                                      font=("Helvetica", 10))
        self.review_label.pack(anchor="w")

        self.patience_label = ttk.Label(frame, text="", wraplength=600,
                                        font=("Helvetica", 10, "italic"))
        self.patience_label.pack(anchor="w", pady=(5, 2))

        def _request_patience():
            board = self.career.board
            today = ""
            try:
                today = self.app.current_date.isoformat()
            except Exception:
                pass
            granted, headline, body = board.request_patience(today)
            # Granted: the room settles knowing the manager is safe.
            if granted:
                try:
                    team = self.app.user_team
                    for p in (getattr(team, "roster", []) or []):
                        m = getattr(p, "morale", 70) or 70
                        p.morale = min(100, m + 2)
                except Exception:
                    pass
            messagebox.showinfo(headline, body)
            self._refresh_board()

        ttk.Button(frame, text="Request a meeting with the owner",
                   command=_request_patience).pack(anchor="w", pady=5)

        ttk.Label(frame, text="Expectation progress:",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.progress_label = ttk.Label(frame, text="", wraplength=620,
                                        font=("Helvetica", 10), justify="left")
        self.progress_label.pack(anchor="w")

        def _on_exp_change(_e=None):
            key = exp_var.get()
            self.exp_desc.config(
                text=f"{mc.EXPECTATIONS[key]['label']}: {mc.EXPECTATIONS[key]['description']}")
        exp_combo.bind("<<ComboboxSelected>>", _on_exp_change)
        _on_exp_change()
        self._refresh_board()

    def _refresh_board(self):
        board = self.career.board
        self.conf_bar.config(value=board.confidence)
        self.conf_label.config(
            text=f"{board.confidence}/100 — {board.job_status}")
        self.record_label.config(
            text=f"{board.season_wins}W - {board.season_losses}L - {board.season_otl}OTL")
        self.review_label.config(
            text=board.last_review or "No reviews yet this season.")
        try:
            today = self.app.current_date.isoformat()
        except Exception:
            today = ""
        self.patience_label.config(text=board.patience_status(today))
        self.progress_label.config(text=self._expectation_progress_text())

    # Rough full-season point targets per expectation. These are estimates
    # (the usual NHL ranges), clearly labeled as such — not game data.
    _EXPECTATION_TARGETS = {
        "win_cup": (108, "roughly 108+ points — a top seed and a full Cup run"),
        "contend": (100, "roughly 100+ points — a top-four seed for a deep run"),
        "playoffs": (94, "roughly 94+ points — the usual playoff cutoff range"),
        "rebuild": (None, "no points target — player development is the goal"),
    }

    def _expectation_progress_text(self):
        board = self.career.board
        exp = board.expectation or "playoffs"
        gp = board.season_wins + board.season_losses + board.season_otl
        pts = board.season_wins * 2 + board.season_otl
        # Slate length for pace math: 84 from the 2026-27 CBA; old saves
        # (82-game schedules) carry no attribute and keep 82.
        _gm = getattr(self.app, "game_manager", None)
        _slate = getattr(getattr(_gm, "league", None),
                         "season_games_count", 82) or 82
        target, note = self._EXPECTATION_TARGETS.get(exp, (94, ""))
        lines = []

        if gp == 0:
            lines.append("The season has not started, so there is no points "
                         "pace to measure yet.")
        else:
            pace = pts / gp * _slate
            lines.append(f"Current pace: {pts} points in {gp} games "
                         f"({pace:.1f} points per {_slate} games).")
            if target is None:
                lines.append(f"Expectation ({mc.EXPECTATIONS[exp]['label']}): "
                             f"{note}.")
            else:
                gap = pace - target
                verdict = ("on track" if gap >= -2
                           else "within reach" if gap >= -8
                           else "off the pace")
                lines.append(
                    f"Expectation ({mc.EXPECTATIONS[exp]['label']}): {note}. "
                    f"You are {verdict} ({gap:+.1f} vs target pace).")

        cutoff = self._playoff_cutoff_pace()
        if cutoff is None:
            lines.append("Playoff picture: league standings are not "
                         "available yet.")
        else:
            lines.append(f"Playoff picture: the current league-wide cutoff "
                         f"pace is about {cutoff:.0f} points — you sit "
                         f"{pts - cutoff:+.0f} vs that mark.")
        return "\n".join(lines)

    def _playoff_cutoff_pace(self):
        """Approximate full-slate pace of the 16th-place team, or None."""
        try:
            gm = getattr(self.app, "game_manager", None)
            if gm is None:
                return None
            league = getattr(gm, "league", None)
            _slate = getattr(league, "season_games_count", 82) or 82
            standings = (getattr(league, "standings", None)
                         or getattr(gm, "standings", None))
            if not standings or len(standings) < 16:
                return None
            paces = []
            for s in standings.values():
                g = s.get("W", 0) + s.get("L", 0) + s.get("OTL", 0)
                if g > 0:
                    paces.append(s.get("Points", 0) / g * _slate)
            if len(paces) < 16:
                return None
            return sorted(paces, reverse=True)[15]
        except Exception:
            return None

    # ------------------------------------------------------------------
    def _build_squad_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="  Squad  ")

        cols = ("name", "pos", "age", "morale", "happiness", "status", "concern")
        self.squad_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                       height=16)
        headers = {"name": "Player", "pos": "Pos", "age": "Age",
                   "morale": "Morale", "happiness": "Mood",
                   "status": "Squad Status", "concern": "Concern"}
        widths = {"name": 170, "pos": 45, "age": 40, "morale": 80,
                  "happiness": 90, "status": 120, "concern": 70}
        for c in cols:
            self.squad_tree.heading(c, text=headers[c])
            self.squad_tree.column(c, width=widths[c])
        self.squad_tree.pack(fill="both", expand=True)
        self.squad_tree.bind("<Button-3>", self._show_squad_context_menu)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=8)
        for key, info in mc.CHAT_ACTIONS.items():
            ttk.Button(btn_frame, text=info["label"],
                       command=lambda k=key: self._do_chat(k)).pack(side="left", padx=2)

        btn_frame2 = ttk.Frame(frame)
        btn_frame2.pack(fill="x")
        ttk.Label(btn_frame2, text="Squad status:").pack(side="left")
        self.status_var = tk.StringVar(value="Rotation")
        ttk.Combobox(btn_frame2, textvariable=self.status_var,
                     values=mc.SQUAD_STATUSES, state="readonly",
                     width=16).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text="Set Status",
                   command=self._set_squad_status).pack(side="left", padx=2)
        ttk.Button(btn_frame2, text="Name Captain (C)",
                   command=lambda: self._set_captaincy("C")).pack(side="left", padx=2)
        ttk.Button(btn_frame2, text="Name Alternate (A)",
                   command=lambda: self._set_captaincy("A")).pack(side="left", padx=2)
        ttk.Button(btn_frame2, text="Remove Letter",
                   command=lambda: self._set_captaincy(None)).pack(side="left", padx=2)

        self._refresh_squad()

    def _selected_player(self):
        sel = self.squad_tree.selection()
        if not sel:
            messagebox.showinfo("Squad", "Select a player first.")
            return None
        pid = int(self.squad_tree.item(sel[0], "values")[0].split("|")[0])
        for p in self.app.user_team.roster:
            if p.id == pid:
                return p
        return None

    def _player_by_id(self, pid):
        for p in self.app.user_team.roster:
            if p.id == pid:
                return p
        return None

    def _show_squad_context_menu(self, event):
        """Right-click on a squad row -> full player context menu."""
        item = self.squad_tree.identify_row(event.y)
        if not item:
            return
        self.squad_tree.selection_set(item)
        try:
            pid = int(self.squad_tree.item(item, "values")[0].split("|")[0])
        except Exception:
            return
        player = self._player_by_id(pid)
        if not player:
            return
        PlayerContextMenu(self.app).show_context_menu(event, player)

    def _refresh_squad(self):
        for i in self.squad_tree.get_children():
            self.squad_tree.delete(i)
        for p in sorted(self.app.user_team.roster,
                        key=lambda x: (x.last_name, x.first_name)):
            try:
                from game_classes import position_label as _pl
                pos = _pl(p)
            except Exception:
                pos = "?"
            letter = f" ({p.captaincy})" if getattr(p, "captaincy", None) else ""
            self.squad_tree.insert("", "end", values=(
                f"{p.id}|{p.first_name} {p.last_name}{letter}",
                pos, p.age,
                mc.morale_label(getattr(p, "morale", 7) or 7),
                mc.happiness_label(getattr(p, "happiness", 70) or 70),
                getattr(p, "squad_status", "Rotation") or "Rotation",
                f"{getattr(p, 'playing_time_concern', 0) or 0}%",
            ))

    def _do_chat(self, action):
        p = self._selected_player()
        if not p:
            return
        _today = getattr(self.app, "current_date", None)
        text, _effects = mc.chat_with_player(p, action, today=_today)
        messagebox.showinfo("Private Chat", text)
        self._refresh_squad()

    def _set_squad_status(self):
        p = self._selected_player()
        if not p:
            return
        p.squad_status = self.status_var.get()
        self._refresh_squad()

    def _set_captaincy(self, letter):
        p = self._selected_player()
        if not p:
            return
        team = self.app.user_team
        if letter == "C":
            for mate in team.roster:
                if getattr(mate, "captaincy", None) == "C":
                    mate.captaincy = None
        p.captaincy = letter
        what = "captain" if letter == "C" else ("alternate captain" if letter == "A" else "letter removed")
        messagebox.showinfo("Leadership",
                            f"{p.first_name} {p.last_name} — {what}.")
        self._refresh_squad()

    # ------------------------------------------------------------------
    def _build_training_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Training  ")
        training = self.career.training

        ttk.Label(frame, text="Weekly Training Schedule",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")

        ttk.Label(frame, text="Preset:").pack(anchor="w", pady=(10, 2))
        self.preset_var = tk.StringVar(value=training.preset_name)
        preset_combo = ttk.Combobox(frame, textvariable=self.preset_var,
                                    values=list(mc.TRAINING_PRESETS.keys()),
                                    state="readonly", width=25)
        preset_combo.pack(anchor="w")

        def _apply_preset(_e=None):
            training.set_preset(self.preset_var.get())
            self._refresh_training()

        preset_combo.bind("<<ComboboxSelected>>", _apply_preset)

        self.unit_vars = {}
        grid = ttk.Frame(frame)
        grid.pack(anchor="w", pady=10)
        ttk.Label(grid, text="Unit", font=("Helvetica", 10, "bold")).grid(row=0, column=0, padx=5)
        ttk.Label(grid, text="Intensity", font=("Helvetica", 10, "bold")).grid(row=0, column=1, padx=5)
        ttk.Label(grid, text="Focus", font=("Helvetica", 10, "bold")).grid(row=0, column=2, padx=5)
        for i, unit in enumerate(mc.TRAINING_UNITS, start=1):
            ttk.Label(grid, text=unit).grid(row=i, column=0, padx=5, pady=3, sticky="w")
            ivar = tk.StringVar(value=training.schedule[unit][0])
            fvar = tk.StringVar(value=training.schedule[unit][1])
            ttk.Combobox(grid, textvariable=ivar, values=mc.TRAINING_INTENSITIES,
                         state="readonly", width=12).grid(row=i, column=1, padx=5)
            ttk.Combobox(grid, textvariable=fvar, values=mc.TRAINING_FOCI,
                         state="readonly", width=12).grid(row=i, column=2, padx=5)
            self.unit_vars[unit] = (ivar, fvar)

        def _save_custom():
            for unit, (ivar, fvar) in self.unit_vars.items():
                training.set_unit(unit, ivar.get(), fvar.get())
            self.preset_var.set("Custom")
            self._refresh_training()

        ttk.Button(frame, text="Apply Custom Schedule",
                   command=_save_custom).pack(anchor="w", pady=5)

        ttk.Label(frame, text="Expected effects this week:",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.training_effects = ttk.Label(frame, text="", wraplength=600,
                                          font=("Helvetica", 10),
                                          justify="left")
        self.training_effects.pack(anchor="w")
        self._refresh_training()

    def _refresh_training(self):
        training = self.career.training
        for unit, (ivar, fvar) in self.unit_vars.items():
            ivar.set(training.schedule[unit][0])
            fvar.set(training.schedule[unit][1])
        self.preset_var.set(training.preset_name)
        fx = training.weekly_effects()
        lines = [
            f"Development rate: x{fx['development_mult']}",
            f"Injury risk: x{fx['injury_risk_mult']}",
            f"Squad morale: {'+' if fx['morale_delta'] >= 0 else ''}{fx['morale_delta']}",
        ] + fx["notes"]
        self.training_effects.config(text="\n".join("• " + l for l in lines))

    # ------------------------------------------------------------------
    def _build_prospects_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Prospects  ")
        ttk.Label(frame, text="Prospect Pool",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, wraplength=600, justify="left",
                  text="Unsigned players your club has drafted and holds the rights to. "
                       "They develop in juniors, college, or the minors — sign the best "
                       "ones to your roster when they're ready.",
                  font=("Helvetica", 10)).pack(anchor="w", pady=5)
        self.prospect_list = tk.Text(frame, height=18, width=80, wrap="word",
                                     font=("Helvetica", 10))
        self.prospect_list.pack(fill="both", expand=True, pady=5)
        self._refresh_prospects()

    def refresh(self):
        """Re-entrant refresh for screen-cache hits (gating Phase 1).

        Clear-then-fill per tab. The Profile tab is static manager identity
        and is intentionally not refreshed.
        """
        for _fn in (self._refresh_board, self._refresh_squad,
                    self._refresh_training, self._refresh_prospects,
                    self._refresh_press):
            try:
                _fn()
            except Exception:
                pass

    def _refresh_press(self):
        """Clear-then-fill rebuild of the press-conference history text."""
        box = self.press_list
        try:
            box.config(state="normal")
        except Exception:
            pass
        try:
            box.delete("1.0", "end")
        except Exception:
            return
        hist = self.career.press_history
        if not hist:
            box.insert("end", "No press conferences held yet.")
        for entry in reversed(hist[-20:]):
            box.insert(
                "end",
                f"[{entry.get('date')}] {entry.get('type')}: "
                f"{entry.get('summary')}\n\n")

    def _refresh_prospects(self):
        """List the user club's drafted (unsigned) prospects, best first."""
        box = self.prospect_list
        box.config(state="normal")
        box.delete("1.0", "end")
        prospects = list(getattr(self.app.user_team, "prospects", []) or [])
        if not prospects:
            box.insert("end", "No unsigned prospects yet. Build your pipeline "
                              "at the NHL Entry Draft each June.")
        else:
            def _ovr(p):
                try:
                    return int(p.overall_rating())
                except Exception:
                    return 0
            try:
                from player_context_menu import PlayerContextMenu
                _pros_mgr = PlayerContextMenu(self)
            except Exception:
                _pros_mgr = None
            for p in sorted(prospects, key=_ovr, reverse=True):
                try:
                    pos = p.primary_position.value
                except Exception:
                    pos = getattr(p, "position", "?")
                grade = getattr(p, "potential_grade", "?") or "?"
                age = getattr(p, "age", "?")
                try:
                    name = p.full_name
                except Exception:
                    name = "Unknown"
                try:
                    from attribute_composites import talent_tier as _tt
                    _ptier = _tt(_ovr(p))
                except Exception:
                    _ptier = "Decent"
                # EHM/FM24: right-click a name -> player menu. Tag the
                # name span (line starts with "• ").
                try:
                    _lstart = box.index("end-1c")
                except Exception:
                    _lstart = None
                box.insert("end",
                           f"• {name}, {age} — {pos} "
                           f"({_ptier}, POT {grade})\n")
                try:
                    if (_lstart is not None and _pros_mgr is not None
                            and hasattr(p, 'full_name')):
                        _m = _pros_mgr
                        _pp = p

                        def _show(_e, _p=_pp, _mm=_m):
                            try:
                                _mm.show_context_menu(_e, _p)
                            except Exception:
                                pass

                        _tag = f"mh-pros-{getattr(p, 'id', id(p))}"
                        _ns = f"{_lstart}+2c"
                        _ne = f"{_lstart}+{2 + len(str(name))}c"
                        box.tag_add(_tag, _ns, _ne)
                        box.tag_config(_tag, underline=True)
                        box.tag_bind(_tag, "<Button-3>", _show)
                        box.tag_bind(_tag, "<Shift-F10>", _show)
                except Exception:
                    pass
        box.config(state="disabled")

    # ------------------------------------------------------------------
    def _build_press_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Press  ")
        ttk.Label(frame, text="Press Conference History",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")
        self.press_list = tk.Text(frame, height=22, width=80, wrap="word",
                                  font=("Helvetica", 10))
        self.press_list.pack(fill="both", expand=True, pady=5)
        hist = self.career.press_history
        if not hist:
            self.press_list.insert("end", "No press conferences held yet.")
        for entry in reversed(hist[-20:]):
            self.press_list.insert(
                "end", f"[{entry.get('date')}] {entry.get('type')}: {entry.get('summary')}\n\n")

    # ------------------------------------------------------------------
    def _build_profile_tab(self, notebook):
        # R8 (UI repairs): busy cursor while the Profile tab builds.
        try:
            from ctk_theme import busy_cursor
            _cm = busy_cursor(self)
            _cm.__enter__()
        except Exception:
            _cm = None
        try:
            self._build_profile_tab_inner(notebook)
        finally:
            try:
                if _cm is not None:
                    _cm.__exit__(None, None, None)
            except Exception:
                pass

    def _build_profile_tab_inner(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Profile  ")
        prof = self.career.profile
        gmp = getattr(getattr(self.app, "user_team", None), "gm_profile", None)

        name = getattr(gmp, "name", None) or "Manager"
        ttk.Label(frame, text=f"Manager Profile \u2014 {name}",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")

        cols = ttk.Frame(frame)
        cols.pack(fill="x", pady=(6, 0))
        left = ttk.Frame(cols)
        left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        right = ttk.Frame(cols)
        right.pack(side="left", fill="both", expand=True)

        # ---- left: personal details, style, background ----
        ttk.Label(left, text="Personal",
                  font=("Helvetica", 11, "bold")).pack(anchor="w")
        if gmp is not None:
            for line in (
                f"Age: {getattr(gmp, 'age', '?')}",
                f"Birthplace: {getattr(gmp, 'birthplace', '?')}",
                f"Nationality: {getattr(gmp, 'nationality', '?')}",
                f"Education: {getattr(gmp, 'education_level', '?')}",
            ):
                ttk.Label(left, font=("Helvetica", 10), text=line).pack(anchor="w")
            ttk.Label(left, text="Management style:",
                      font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(8, 0))
            for line in (
                f"Style: {getattr(gmp, 'management_style', '?')}",
                f"Risk tolerance: {getattr(gmp, 'risk_tolerance', '?')}",
                f"Loyalty to players: {getattr(gmp, 'loyalty_to_players', '?')}",
                f"Media savvy: {getattr(gmp, 'media_savvy', '?')}",
            ):
                ttk.Label(left, font=("Helvetica", 10), text=line).pack(anchor="w")
            bits = []
            if getattr(gmp, "former_player", False):
                bits.append(
                    f"Former {getattr(gmp, 'playing_position', 'player')}: "
                    f"{getattr(gmp, 'nhl_games_played', 0)} NHL games, "
                    f"{getattr(gmp, 'career_points', 0)} career points.")
            if getattr(gmp, "coaching_experience", False):
                bits.append(
                    f"{getattr(gmp, 'years_coaching', 0)} years coaching experience.")
            if getattr(gmp, "assistant_gm_experience", False):
                bits.append(
                    f"{getattr(gmp, 'years_as_assistant', 0)} years as an assistant GM.")
            if bits:
                ttk.Label(left, text="Background:",
                          font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(8, 0))
                for b in bits:
                    ttk.Label(left, font=("Helvetica", 10), text=f"\u2022 {b}",
                              wraplength=340, justify="left").pack(anchor="w")
        else:
            ttk.Label(left, font=("Helvetica", 10),
                      text="No manager biography on file.").pack(anchor="w")
        club = getattr(getattr(self.app, "user_team", None), "team_name", None)
        start = getattr(self.career, "career_start_date", "") or ""
        if club or start:
            ttk.Label(left, text="Appointment:",
                      font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(8, 0))
            if club:
                ttk.Label(left, font=("Helvetica", 10),
                          text=f"Club: {club}").pack(anchor="w")
            if start:
                ttk.Label(left, font=("Helvetica", 10),
                          text=f"In charge since: {start}").pack(anchor="w")

        # ---- right: reputation + career record ----
        ttk.Label(right, text="Reputation",
                  font=("Helvetica", 11, "bold")).pack(anchor="w")
        ttk.Label(right, font=("Helvetica", 12),
                  text=f"{prof.reputation}/100 \u2014 {prof.level}").pack(anchor="w", pady=5)
        ttk.Label(right, text="Career record",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(8, 0))
        board = getattr(self.career, "board", None)
        season_line = ""
        if board is not None:
            season_line = (f"\nCurrent season: {board.season_wins}W - "
                           f"{board.season_losses}L - {board.season_otl}OTL")
        ttk.Label(right, font=("Helvetica", 11), justify="left",
                  text=(f"Career: {prof.career_wins}W - {prof.career_losses}L - "
                        f"{prof.career_otl}OTL{season_line}\n"
                        f"Titles won: {prof.titles_won}\n"
                        f"Playoff appearances: {prof.playoff_appearances}\n"
                        f"Seasons managed: {prof.seasons_managed}")).pack(anchor="w", pady=5)

        # ---- preferences (full width) ----
        ttk.Label(frame, text="Preferences:",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.prompts_var = tk.BooleanVar(value=self.career.prompts_enabled)

        def _toggle():
            self.career.prompts_enabled = self.prompts_var.get()

        ttk.Checkbutton(frame, text="Show press conferences & team talks on matchdays",
                        variable=self.prompts_var,
                        command=_toggle).pack(anchor="w")


# ---------------------------------------------------------------------------

# Dialogs (embedded focus-card screens + thin popup wrappers)
# ---------------------------------------------------------------------------
class TeamTalkView(ctk.CTkFrame):
    """Team talk picker as an embedded full-screen focus card.

    Result (option_dict_or_None, reaction_text, boost) is delivered via the
    on_done callback; the view then closes itself. Replaces the blocking
    wait_window() flow of the old TeamTalkDialog.
    """

    def __init__(self, parent, team, when: str, context: dict,
                 app=None, on_done=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the TeamTalkDialog wrapper
        self.team = team
        self.when = when
        self.context = context
        self.result = None
        self.on_done = on_done
        try:
            self.configure(fg_color=self.app.BG_COLOR)
        except Exception:
            pass

        # Focus card: full-screen view, content in a centered card.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(self, fg_color="#1c1c21", corner_radius=12,
                            width=560)
        card.grid(row=0, column=0, padx=24, pady=24)

        titles = {"prematch": "Pre-Match Team Talk",
                  "intermission": "Intermission Team Talk",
                  "postmatch": "Full-Time Team Talk"}
        ttk.Label(card, text=titles.get(when, "Team Talk"),
                  font=("Helvetica", 14, "bold")).pack(pady=(16, 6))
        ctx_desc = {
            "prematch": f"Next up: {context.get('opponent_name', 'the opposition')}.",
            "intermission": f"Score: {context.get('score_line', '')}.",
            "postmatch": f"Final: {context.get('score_line', '')}.",
        }
        ttk.Label(card, text=ctx_desc.get(when, ""),
                  font=("Helvetica", 11)).pack(pady=4)

        self.options = mc.get_team_talk_options(when, context)
        list_frame = ttk.Frame(card)
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)
        for opt in self.options:
            fit_note = {"good": " ✓ looks ideal", "risky": " ⚠ risky"}.get(opt["fit"], "")
            btn = ttk.Button(list_frame,
                             text=opt["label"] + fit_note,
                             command=lambda o=opt: self._choose(o))
            btn.pack(fill="x", pady=4)
            ttk.Label(list_frame, text=f'"{opt["text"]}"',
                      font=("Helvetica", 9, "italic"),
                      wraplength=480).pack(anchor="w", padx=10)

        ttk.Button(card, text="Say nothing",
                   command=self._say_nothing).pack(pady=(6, 16))

    def _choose(self, option):
        _ctx = dict(self.context or {})
        if "today" not in _ctx:
            _ctx["today"] = getattr(self.app, "current_date", None)
        reaction, boost = mc.apply_team_talk(self.team, option, _ctx)
        messagebox.showinfo("Dressing Room", reaction, parent=self)
        self.result = (option, reaction, boost)
        self._finish()

    def _say_nothing(self):
        self.result = None
        self._finish()

    def _finish(self):
        cb = getattr(self, "on_done", None)
        if callable(cb):
            try:
                cb(self.result)
            except Exception:
                pass
        self.close_view()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()


class PressConferenceView(ctk.CTkFrame):
    """Press conference as an embedded full-screen focus card.

    Result (list of chosen answer dicts) is delivered via the on_done
    callback; the view then closes itself. Replaces the blocking
    wait_window() flow of the old PressConferenceDialog.
    """

    def __init__(self, parent, questions: List[dict],
                 title: str = "Press Conference", app=None, on_done=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the PressConferenceDialog wrapper
        self.questions = questions
        self.chosen = []
        self.on_done = on_done
        try:
            self.configure(fg_color=self.app.BG_COLOR)
        except Exception:
            pass

        # Focus card: full-screen view, content in a centered card.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(self, fg_color="#1c1c21", corner_radius=12,
                            width=600)
        card.grid(row=0, column=0, padx=24, pady=24)

        ttk.Label(card, text=title,
                  font=("Helvetica", 14, "bold")).pack(pady=(16, 6))
        self.q_index = 0
        self.q_label = ttk.Label(card, text="", wraplength=540,
                                 font=("Helvetica", 11, "bold"))
        self.q_label.pack(pady=8)
        self.j_label = ttk.Label(card, text="", font=("Helvetica", 10, "italic"))
        self.j_label.pack()
        self.btn_frame = ttk.Frame(card)
        self.btn_frame.pack(fill="both", expand=True, padx=20, pady=(10, 16))
        self._show_question()

    def _show_question(self):
        for w in self.btn_frame.winfo_children():
            w.destroy()
        if self.q_index >= len(self.questions):
            self._finish()
            return
        q = self.questions[self.q_index]
        self.j_label.config(text=f"— {q['journalist']}")
        self.q_label.config(text=f"Q{self.q_index + 1}: {q['question']}")
        for ans in q["answers"]:
            ttk.Button(self.btn_frame, text=ans["label"],
                       command=lambda a=ans: self._answer(a)).pack(fill="x", pady=5)

    def _answer(self, ans):
        self.chosen.append(ans)
        messagebox.showinfo("Media Reaction", ans["reaction"], parent=self)
        self.q_index += 1
        self._show_question()

    def _finish(self):
        cb = getattr(self, "on_done", None)
        if callable(cb):
            try:
                cb(self.chosen)
            except Exception:
                pass
        self.close_view()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()


class OppositionReportView(ctk.CTkFrame):
    """Read-only pre-match scout report as an embedded focus card."""

    def __init__(self, parent, report: dict, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the OppositionReportDialog wrapper
        try:
            self.configure(fg_color=self.app.BG_COLOR)
        except Exception:
            pass

        # Focus card: full-screen view, content in a centered card.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(self, fg_color="#1c1c21", corner_radius=12,
                            width=580)
        card.grid(row=0, column=0, padx=24, pady=24)

        ttk.Label(card, text=f"SCOUT REPORT: {report.get('team')}",
                  font=("Helvetica", 14, "bold")).pack(pady=(16, 4))
        ttk.Label(card,
                  text=f"Record: {report.get('record')}   "
                       f"Danger level: {report.get('danger_level')}",
                  font=("Helvetica", 11)).pack(pady=(0, 8))

        text = tk.Text(card, wrap="word", font=("Helvetica", 10),
                       padx=12, pady=12, height=18, width=64)
        text.pack(fill="both", expand=True, padx=16)
        text.insert("end", "STRENGTHS\n", "h")
        for s in report.get("strengths", []):
            text.insert("end", f"• {s}\n")
        text.insert("end", "\nWEAKNESSES\n", "h")
        for w in report.get("weaknesses", []):
            text.insert("end", f"• {w}\n")
        text.insert("end", "\nKEY PLAYERS\n", "h")
        for k in report.get("key_players", []):
            text.insert("end", f"• {k}\n")
        text.insert("end", "\nTACTICAL ADVICE\n", "h")
        for a in report.get("tactical_advice", []):
            text.insert("end", f"• {a}\n")
        text.tag_configure("h", font=("Helvetica", 11, "bold"))
        text.config(state="disabled")
        ttk.Button(card, text="Close",
                   command=self.close_view).pack(pady=14)

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()
