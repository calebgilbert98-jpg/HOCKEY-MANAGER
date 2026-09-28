"""Offer-sheet UI (BUG-020): the user-facing half of the offer-sheet system.

The engine was already complete -- AI offer sheets run in the July RFA
pass (process_rfa_offseason), the player decides via
player_decision.player_accepts_offer_sheet, the original club matches via
ai_match_decision, and execute_offer_sheet moves the player plus the real
compensation picks. The July pass even notes "the user signs offer sheets
via the UI, not here" -- but that UI was never built, so the user had no
way to initiate one.

OfferSheetWindow (InGamePopup, CTk): browse unsigned RFAs on rival NHL
clubs, set AAV + term, see live compensation (the real
offer_sheet_compensation bands) with own-pick availability, a cap check,
and a qualitative read of the player's interest -- then present the
sheet. The player may refuse (his camp's reasons are shown); otherwise
the original club matches or declines on the spot through the same
ai_match_decision the engine uses. One rulebook, both directions.
"""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from popup_system import InGamePopup, messagebox


def _money(n):
    try:
        return f"${int(n):,}"
    except Exception:
        return "$?"


def compensation_pick_status(user_team, year, picks):
    """Preview which compensation picks the user can actually furnish.

    Mirrors execute_offer_sheet's find logic (walk forward through the
    club's own upcoming picks, as far as picks exist) with transfer
    semantics simulated through a used-set, so the preview never
    promises the same pick twice. Returns (lines, missing_rounds);
    lines are (ok, text) tuples.
    """
    import rfa_system as _rfa
    lines, missing, used_ids = [], [], set()
    for rnd in picks:
        pk, y = None, year
        for _yy in range(year, year + 7):
            cand = _rfa.own_pick_available(user_team, _yy, rnd)
            if cand is not None and id(cand) not in used_ids:
                pk, y = cand, _yy
                break
        if pk is None:
            missing.append(rnd)
            lines.append((False,
                          f"round {rnd}: not yours to trade ({year}-{year + 6})"))
        else:
            used_ids.add(id(pk))
            lines.append((True, f"{y} round {rnd} (your own pick)"))
    return lines, missing


class OfferSheetWindow(InGamePopup):
    """Sign a rival club's unsigned RFA to an offer sheet."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.league = getattr(parent, "league", None)
        self.user_team = getattr(self.league, "user_team", None)
        if self.user_team is None:
            self.user_team = getattr(parent, "user_team", None)

        self.title("Offer Sheets — Poach a Rival RFA")
        try:
            self.geometry("1180x760")
        except Exception:
            pass

        self._targets = []        # (player, original_team, market)
        self._selected = None     # (player, original_team, market)
        self._comp_year = None

        self._build()
        self._refresh_targets()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        try:
            from ctk_theme import (
                init_ctk_theme, primary_button, secondary_button,
                heading, body, TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
                TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED,
            )
            init_ctk_theme()
        except Exception:
            TEAL = "#2dd4bf"; BG = "#0f172a"; PANEL = "#1e293b"
            CARD = "#1e293b"; BORDER = "#334155"; TEXT = "#f1f5f9"
            TEXT_DIM = "#94a3b8"; TEXT_FAINT = "#64748b"
            GOLD = "#fbbf24"; GREEN = "#4ade80"; RED = "#f87171"
            TEAL_HOVER = "#14b8a6"
            def primary_button(p, **kw):
                return ctk.CTkButton(p, **kw)
            def secondary_button(p, **kw):
                return ctk.CTkButton(p, fg_color="transparent",
                                     border_width=1, **kw)
            def heading(p, **kw):
                return ctk.CTkLabel(p, **kw)
            def body(p, **kw):
                return ctk.CTkLabel(p, **kw)
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button

        ct = self._ct
        root = ctk.CTkFrame(self, fg_color=ct["BG"])
        root.pack(fill="both", expand=True)

        header = ctk.CTkFrame(root, fg_color=ct["PANEL"], corner_radius=12)
        header.pack(fill="x", padx=14, pady=(14, 10))
        heading(header, text="📝 Offer Sheets",
                font=("Segoe UI", 20, "bold"),
                text_color=ct["TEXT"]).pack(side="left", padx=16, pady=12)
        self._status_var = tk.StringVar(value="")
        body(header, text="", textvariable=self._status_var,
             font=("Segoe UI", 11), text_color=ct["TEXT_DIM"]).pack(
            side="left", padx=8, pady=12)
        secondary_button(header, text="Close",
                         command=self.destroy).pack(side="right", padx=16)

        main = ctk.CTkFrame(root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # --- left: RFA list -------------------------------------------
        left = ctk.CTkFrame(main, fg_color=ct["PANEL"], corner_radius=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        body(left, text="Unsigned RFAs on rival clubs",
             font=("Segoe UI", 13, "bold"),
             text_color=ct["TEXT"]).pack(anchor="w", padx=12, pady=(10, 4))

        cols = ("player", "age", "pos", "ovr", "team", "value")
        self._tree = ttk.Treeview(left, columns=cols, show="headings",
                                  height=22)
        for c, w, label in (("player", 170, "Player"), ("age", 45, "Age"),
                            ("pos", 55, "Pos"), ("ovr", 50, "OVR"),
                            ("team", 150, "Club"),
                            ("value", 100, "Est. value")):
            self._tree.heading(c, text=label)
            self._tree.column(c, width=w, anchor="w" if c in
                              ("player", "team") else "center")
        self._tree.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        body(left, text="Compensation picks must be your own — check the "
             "preview before presenting.",
             font=("Segoe UI", 10), text_color=ct["TEXT_FAINT"]).pack(
            anchor="w", padx=12, pady=(0, 10))

        # --- right: offer builder --------------------------------------
        right = ctk.CTkFrame(main, fg_color=ct["PANEL"], corner_radius=12,
                             width=380)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        body(right, text="Build the offer",
             font=("Segoe UI", 13, "bold"),
             text_color=ct["TEXT"]).pack(anchor="w", padx=12, pady=(10, 2))
        self._detail_var = tk.StringVar(value="Select a player on the left.")
        body(right, text="", textvariable=self._detail_var,
             font=("Segoe UI", 11), text_color=ct["TEXT_DIM"],
             wraplength=340, justify="left").pack(
            anchor="w", padx=12, pady=(0, 8))

        # AAV slider
        body(right, text="Average annual value",
             font=("Segoe UI", 11, "bold"),
             text_color=ct["TEXT"]).pack(anchor="w", padx=12)
        aav_row = ctk.CTkFrame(right, fg_color="transparent")
        aav_row.pack(fill="x", padx=12, pady=(2, 6))
        self._aav_var = tk.DoubleVar(value=4.0)
        self._aav_slider = ctk.CTkSlider(
            aav_row, from_=1.0, to=12.0, number_of_steps=110,
            variable=self._aav_var, command=lambda _v: self._update_preview())
        self._aav_slider.pack(side="left", fill="x", expand=True)
        self._aav_label_var = tk.StringVar(value="$4.0M")
        body(aav_row, text="", textvariable=self._aav_label_var,
             font=("Segoe UI", 11, "bold"), text_color=ct["GOLD"],
             width=70).pack(side="right", padx=(8, 0))

        # Term
        body(right, text="Term",
             font=("Segoe UI", 11, "bold"),
             text_color=ct["TEXT"]).pack(anchor="w", padx=12)
        self._years_var = tk.StringVar(value="4")
        ctk.CTkOptionMenu(right, variable=self._years_var,
                          values=["1", "2", "3", "4", "5"],
                          command=lambda _v: self._update_preview(),
                          width=120).pack(anchor="w", padx=12, pady=(2, 8))

        # Compensation preview
        body(right, text="Compensation if unmatched",
             font=("Segoe UI", 11, "bold"),
             text_color=ct["TEXT"]).pack(anchor="w", padx=12)
        self._comp_var = tk.StringVar(value="—")
        body(right, text="", textvariable=self._comp_var,
             font=("Segoe UI", 11), text_color=ct["TEXT_DIM"],
             wraplength=340, justify="left").pack(
            anchor="w", padx=12, pady=(0, 4))
        self._checks_var = tk.StringVar(value="")
        body(right, text="", textvariable=self._checks_var,
             font=("Segoe UI", 11), text_color=ct["TEXT_DIM"],
             wraplength=340, justify="left").pack(
            anchor="w", padx=12, pady=(0, 4))
        self._interest_var = tk.StringVar(value="")
        body(right, text="", textvariable=self._interest_var,
             font=("Segoe UI", 11, "italic"), text_color=ct["GOLD"],
             wraplength=340, justify="left").pack(
            anchor="w", padx=12, pady=(0, 8))

        self._submit_btn = primary_button(
            right, text="Present Offer Sheet",
            command=self._present_offer_sheet)
        self._submit_btn.pack(fill="x", padx=12, pady=(4, 6))
        self._result_var = tk.StringVar(value="")
        body(right, text="", textvariable=self._result_var,
             font=("Segoe UI", 11, "bold"), text_color=ct["TEXT"],
             wraplength=340, justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _nhl_teams(self):
        return [t for t in (getattr(self.league, "teams", []) or [])
                if str(getattr(t, "league_name", "") or "")
                == "National Hockey League"]

    def _refresh_targets(self):
        """Unsigned RFAs on rival NHL clubs (arbitration filers excluded --
        filing blocks offer sheets, same as the July pass)."""
        self._targets = []
        try:
            import rfa_system as _rfa
        except Exception:
            return
        user_names = {str(getattr(self.user_team, "team_name", "") or "")}
        for team in self._nhl_teams():
            if team is self.user_team:
                continue
            if str(getattr(team, "team_name", "") or "") in user_names:
                continue
            for p in list(getattr(team, "roster", []) or []):
                try:
                    if not _rfa.is_rfa(p):
                        continue
                    if bool(getattr(p, "arbitration_filed", False)):
                        continue
                    if bool(getattr(p, "offer_sheet_pending", False)):
                        continue
                    market = _rfa.market_value_estimate(p)
                    self._targets.append((p, team, market))
                except Exception:
                    continue
        self._targets.sort(key=lambda t: t[2], reverse=True)
        for item in self._tree.get_children():
            self._tree.delete(item)
        for (p, team, market) in self._targets:
            try:
                pos = getattr(getattr(p, "primary_position", None),
                              "name", "?")
                self._tree.insert("", "end", values=(
                    getattr(p, "full_name", getattr(p, "name", "?")),
                    getattr(p, "age", "?"), str(pos),
                    p.overall_rating(),
                    getattr(team, "team_name", "?"),
                    _money(market)), tags=(str(id(p)),))
            except Exception:
                continue
        self._update_status_line()

    def _update_status_line(self):
        try:
            import transaction_windows as _tw
            ok, why = _tw.check_window(
                "offer_sheet", getattr(self.app, "current_date", None))
        except Exception:
            ok, why = True, ""
        try:
            from salary_cap_system import cap_breakdown
            space = int(cap_breakdown(self.user_team).get("space", 0) or 0)
        except Exception:
            space = 0
        n = len(self._targets)
        state = ("window OPEN (Jul 1 – Dec 1)" if ok
                 else f"window CLOSED — {why}")
        self._status_var.set(
            f"{state}   •   {n} unsigned RFA"
            f"{'' if n == 1 else 's'} on the market   •   "
            f"Your cap space: {_money(space)}")

    def _on_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        tag = self._tree.item(sel[0], "tags")[0]
        for (p, team, market) in self._targets:
            if str(id(p)) == str(tag):
                self._selected = (p, team, market)
                break
        else:
            return
        p, team, market = self._selected
        try:
            pos = getattr(getattr(p, "primary_position", None), "name", "?")
            ovr = p.overall_rating()
        except Exception:
            pos, ovr = "?", "?"
        self._detail_var.set(
            f"{getattr(p, 'full_name', '?')} — {pos}, age "
            f"{getattr(p, 'age', '?')}, {ovr} OVR\n"
            f"Rights held by: {getattr(team, 'team_name', '?')}\n"
            f"Engine's market read: {_money(market)}/yr")
        # Start the AAV at his market read.
        try:
            self._aav_var.set(max(1.0, min(12.0, market / 1_000_000)))
        except Exception:
            pass
        self._result_var.set("")
        self._update_preview()

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _current_terms(self):
        aav = int(round(float(self._aav_var.get()) * 1_000_000))
        try:
            years = int(self._years_var.get())
        except Exception:
            years = 4
        years = max(1, min(5, years))
        return aav, years

    def _update_preview(self):
        ct = self._ct
        if self._selected is None:
            return
        p, original_team, market = self._selected
        aav, years = self._current_terms()
        self._aav_label_var.set(f"${aav / 1_000_000:.1f}M")
        try:
            import rfa_system as _rfa
            label, picks = _rfa.offer_sheet_compensation(aav)
            year = int(getattr(self.league, "season_year", 2026) or 2026) + 1
            self._comp_year = year
            if not picks:
                self._comp_var.set(f"{label} — no picks change hands.")
                missing = []
            else:
                lines, missing = compensation_pick_status(
                    self.user_team, year, picks)
                self._comp_var.set(
                    f"{label}:\n" + "\n".join(
                        f"{'✅' if ok else '❌'} {t}" for ok, t in lines))
        except Exception:
            label, picks, missing = "?", [], []
            self._comp_var.set("Compensation unavailable.")
        # Checks: cap + picks + window.
        checks = []
        try:
            from salary_cap_system import cap_breakdown
            space = int(cap_breakdown(self.user_team).get("space", 0) or 0)
        except Exception:
            space = 0
        checks.append(("✅" if space >= aav else "❌",
                       f"Cap space {_money(space)} vs {_money(aav)}/yr"))
        try:
            n_roster = len(getattr(self.user_team, "roster", []) or [])
        except Exception:
            n_roster = 23
        checks.append(("✅" if n_roster < 23 else "❌",
                       f"Roster {n_roster}/23"))
        if missing:
            checks.append(("❌", "Missing own picks — sheet can't be "
                                "signed"))
        try:
            import transaction_windows as _tw
            ok, _ = _tw.check_window(
                "offer_sheet", getattr(self.app, "current_date", None))
            checks.append(("✅" if ok else "❌",
                           "Offer-sheet window open" if ok
                           else "Window closed"))
        except Exception:
            pass
        self._checks_var.set("\n".join(f"{m} {t}" for m, t in checks))
        # Qualitative read of his interest (no roll revealed).
        try:
            import player_decision as _pd
            appeal, _reasons = _pd.contract_appeal(
                p, self.user_team, aav, years, current_team=original_team,
                league=self.league, app=self.app, is_offer_sheet=True)
            if appeal >= 0.7:
                read = "His camp is listening closely."
            elif appeal >= 0.52:
                read = "His camp is lukewarm — money talks."
            elif appeal >= 0.35:
                read = "His camp sounds cool on the idea."
            else:
                read = "His camp wants nothing to do with this."
            self._interest_var.set(f"📣 {read}")
        except Exception:
            self._interest_var.set("")

    # ------------------------------------------------------------------
    # Present the sheet
    # ------------------------------------------------------------------

    def _present_offer_sheet(self):
        if self._selected is None:
            messagebox.showinfo("Offer Sheets", "Select a player first.")
            return
        p, original_team, market = self._selected
        aav, years = self._current_terms()
        pname = getattr(p, "full_name", getattr(p, "name", "Unknown"))
        tname = getattr(original_team, "team_name", "?")

        import rfa_system as _rfa
        # 1. Window.
        try:
            import transaction_windows as _tw
            ok, why = _tw.check_window(
                "offer_sheet", getattr(self.app, "current_date", None))
            if not ok:
                messagebox.showinfo("Offer Sheets", why)
                return
        except Exception:
            pass
        # 2. Compensation + own picks (same fallback the engine uses).
        label, picks = _rfa.offer_sheet_compensation(aav)
        year = int(getattr(self.league, "season_year", 2026) or 2026) + 1
        _lines, missing = compensation_pick_status(
            self.user_team, year, picks)
        if missing:
            messagebox.showinfo(
                "Offer Sheets",
                f"You don't hold your own picks for the required "
                f"compensation ({label}). Without them the sheet can't "
                f"be signed.")
            return
        # 3. Cap + roster room.
        try:
            from salary_cap_system import cap_breakdown
            space = int(cap_breakdown(self.user_team).get("space", 0) or 0)
        except Exception:
            space = 0
        if space < aav:
            messagebox.showinfo(
                "Offer Sheets",
                f"Not enough cap space: {_money(space)} available vs "
                f"{_money(aav)}/yr. Clear room first.")
            return
        try:
            n_roster = len(getattr(self.user_team, "roster", []) or [])
        except Exception:
            n_roster = 0
        if n_roster >= 23:
            messagebox.showinfo(
                "Offer Sheets",
                "Your NHL roster is full (23/23). Move someone out before "
                "signing him.")
            return
        # 4. The player must agree to sign.
        try:
            import player_decision as _pd
            willing, _appeal, reasons = _pd.player_accepts_offer_sheet(
                p, self.user_team, aav, years, original_team,
                league=self.league, app=self.app,
                rng=getattr(self.app, "_rng", None))
        except Exception:
            willing, reasons = True, []
        if not willing:
            why_txt = f" {reasons[0]}" if reasons else ""
            self._result_var.set(f"❌ {pname} won't sign.{why_txt}")
            try:
                self.app.add_news(
                    f"{pname} rejects your offer sheet "
                    f"({_money(aav)}/yr × {years}y).{why_txt}")
            except Exception:
                pass
            return
        # 5. The original club matches or declines -- the same
        # ai_match_decision the July pass uses. One rulebook.
        if _rfa.ai_match_decision(original_team, p, aav, label):
            story = (f"✍️ OFFER SHEET: you sign {pname} "
                     f"({_money(aav)}/yr × {years}y) — {tname} match and "
                     f"keep him.")
            self._result_var.set(f"😤 {tname} matched. He stays.")
        else:
            res = _rfa.execute_offer_sheet(
                self.league, self.user_team, original_team, p, aav, years,
                app=self.app, rng=getattr(self.app, "_rng", None))
            if not res.get("ok"):
                messagebox.showinfo(
                    "Offer Sheets",
                    f"The sheet failed: {res.get('reason', 'unknown')}.")
                return
            story = res.get("story", "")
            self._result_var.set(f"🎉 He's yours! {label} goes to {tname}.")
        try:
            self.app.add_news(story)
        except Exception:
            pass
        self._selected = None
        self._refresh_targets()
