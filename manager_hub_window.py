"""Manager Hub UI: Football Manager-style career screens for Puck Dynasty.

Tabs: Board, Squad, Training, Youth, Press, Profile.
Dialogs: TeamTalkDialog, PressConferenceDialog, OppositionReportDialog.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from typing import List, Optional

import manager_career as mc


class ManagerHubWindow(tk.Toplevel):
    """FM-style manager hub with tabbed career screens."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.career = parent.career
        self.title("Manager Hub")
        self.geometry("950x680")
        try:
            self.configure(background=parent.BG_COLOR)
        except Exception:
            pass

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.notebook = notebook

        self._build_board_tab(notebook)
        self._build_squad_tab(notebook)
        self._build_training_tab(notebook)
        self._build_youth_tab(notebook)
        self._build_press_tab(notebook)
        self._build_profile_tab(notebook)

    # ------------------------------------------------------------------
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
        for p in self.parent.user_team.roster:
            if p.id == pid:
                return p
        return None

    def _refresh_squad(self):
        for i in self.squad_tree.get_children():
            self.squad_tree.delete(i)
        for p in sorted(self.parent.user_team.roster,
                        key=lambda x: (x.last_name, x.first_name)):
            try:
                pos = p.primary_position.name if hasattr(p.primary_position, "name") else str(p.primary_position)
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
        text, _effects = mc.chat_with_player(p, action)
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
        team = self.parent.user_team
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
    def _build_youth_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Youth  ")
        ttk.Label(frame, text="Academy Intake",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, wraplength=600, justify="left",
                  text="Each July, your academy graduates a new class of prospects. "
                       "Top prospects can be signed straight to your roster.",
                  font=("Helvetica", 10)).pack(anchor="w", pady=5)
        self.youth_list = tk.Text(frame, height=18, width=80, wrap="word",
                                  font=("Helvetica", 10))
        self.youth_list.pack(fill="both", expand=True, pady=5)
        self._refresh_youth()

    def _refresh_youth(self):
        self.youth_list.delete("1.0", "end")
        history = self.career.youth_history
        if not history:
            self.youth_list.insert("end", "No intakes yet. The next academy class graduates in July.")
            return
        for intake in reversed(history):
            self.youth_list.insert("end",
                f"=== {intake.get('year')} intake ({len(intake.get('prospects', []))} prospects) ===\n")
            for pr in intake.get("prospects", []):
                self.youth_list.insert(
                    "end",
                    f"• {pr['first_name']} {pr['last_name']}, {pr['age']} — {pr['position']} "
                    f"(OVR {pr['overall']}, POT {pr['potential']}) — {pr['scout_note']}\n")
            self.youth_list.insert("end", "\n")

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
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Profile  ")
        prof = self.career.profile
        ttk.Label(frame, text="Manager Profile",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, font=("Helvetica", 12),
                  text=f"Reputation: {prof.reputation}/100 — {prof.level}").pack(anchor="w", pady=5)
        ttk.Label(frame, font=("Helvetica", 11), justify="left",
                  text=(f"Career record: {prof.career_wins}W - {prof.career_losses}L - {prof.career_otl}OTL\n"
                        f"Titles won: {prof.titles_won}\n"
                        f"Playoff appearances: {prof.playoff_appearances}\n"
                        f"Seasons managed: {prof.seasons_managed}")).pack(anchor="w", pady=5)
        ttk.Label(frame, text="Media prompts:",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.prompts_var = tk.BooleanVar(value=self.career.prompts_enabled)

        def _toggle():
            self.career.prompts_enabled = self.prompts_var.get()

        ttk.Checkbutton(frame, text="Show press conferences & team talks on matchdays",
                        variable=self.prompts_var,
                        command=_toggle).pack(anchor="w")


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class TeamTalkDialog(tk.Toplevel):
    """Modal team talk picker. Result: (option_dict_or_None, reaction_text, boost)."""

    def __init__(self, parent, team, when: str, context: dict):
        super().__init__(parent)
        self.parent_gui = parent
        self.team = team
        self.when = when
        self.context = context
        self.result = None
        self.title("Team Talk")
        self.geometry("560x420")
        self.transient(parent)
        self.grab_set()

        titles = {"prematch": "Pre-Match Team Talk",
                  "intermission": "Intermission Team Talk",
                  "postmatch": "Full-Time Team Talk"}
        ttk.Label(self, text=titles.get(when, "Team Talk"),
                  font=("Helvetica", 14, "bold")).pack(pady=10)
        ctx_desc = {
            "prematch": f"Next up: {context.get('opponent_name', 'the opposition')}.",
            "intermission": f"Score: {context.get('score_line', '')}.",
            "postmatch": f"Final: {context.get('score_line', '')}.",
        }
        ttk.Label(self, text=ctx_desc.get(when, ""),
                  font=("Helvetica", 11)).pack(pady=4)

        self.options = mc.get_team_talk_options(when, context)
        list_frame = ttk.Frame(self)
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

        ttk.Button(self, text="Say nothing",
                   command=self.destroy).pack(pady=10)
        self.wait_window(self)

    def _choose(self, option):
        reaction, boost = mc.apply_team_talk(self.team, option, self.context)
        messagebox.showinfo("Dressing Room", reaction, parent=self)
        self.result = (option, reaction, boost)
        self.destroy()


class PressConferenceDialog(tk.Toplevel):
    """Modal press conference. Result: list of chosen answer dicts."""

    def __init__(self, parent, questions: List[dict], title: str = "Press Conference"):
        super().__init__(parent)
        self.questions = questions
        self.chosen = []
        self.title(title)
        self.geometry("620x520")
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text=title,
                  font=("Helvetica", 14, "bold")).pack(pady=10)
        self.q_index = 0
        self.q_label = ttk.Label(self, text="", wraplength=560,
                                 font=("Helvetica", 11, "bold"))
        self.q_label.pack(pady=8)
        self.j_label = ttk.Label(self, text="", font=("Helvetica", 10, "italic"))
        self.j_label.pack()
        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(fill="both", expand=True, padx=20, pady=10)
        self._show_question()
        self.wait_window(self)

    def _show_question(self):
        for w in self.btn_frame.winfo_children():
            w.destroy()
        if self.q_index >= len(self.questions):
            self.destroy()
            return
        q = self.questions[self.q_index]
        self.j_label.config(text=f"— {q['journalist']}")
        self.q_label.config(text=f"Q{self.q_index + 1}: {q['question']}")
        for ans in q["answers"]:
            ttk.Button(self.btn_frame, text=ans["label"], wraplength=500,
                       command=lambda a=ans: self._answer(a)).pack(fill="x", pady=5)

    def _answer(self, ans):
        self.chosen.append(ans)
        messagebox.showinfo("Media Reaction", ans["reaction"], parent=self)
        self.q_index += 1
        self._show_question()


class OppositionReportDialog(tk.Toplevel):
    """Read-only pre-match scout report."""

    def __init__(self, parent, report: dict):
        super().__init__(parent)
        self.title(f"Scout Report: {report.get('team')}")
        self.geometry("600x520")
        text = tk.Text(self, wrap="word", font=("Helvetica", 10), padx=12, pady=12)
        text.pack(fill="both", expand=True)
        text.insert("end", f"SCOUT REPORT: {report.get('team')}\n", "h")
        text.insert("end", f"Record: {report.get('record')}   Danger level: {report.get('danger_level')}\n\n")
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
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=8)
