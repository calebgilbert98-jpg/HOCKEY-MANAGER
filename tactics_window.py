# tactics_window.py
# FM24-style Team Tactics screen for Puck Dynasty's NHL systems layer:
# all seven zone modules with descriptions + expected tradeoffs,
# familiarity, roster/coach fit, club identity, saved preferred tactics,
# one-click identity presets, and the coach-control flow
# (suggest / enforce / take over the whiteboard).
# CustomTkinter: CTkToplevel chrome, CTkScrollableFrame, mirrors morale_window.

from tkinter import messagebox
from popup_system import InGamePopup

import customtkinter as ctk

import reputation_system as rs
import tactics as tx


class TacticsView(ctk.CTkFrame):
    """Team Tactics - the whiteboard: systems, fit, and who owns it."""

    CATS = [
        ("forecheck", "Forecheck", "FORECHECK_SYSTEMS"),
        ("neutral_zone", "Neutral Zone", "NEUTRAL_ZONE_SYSTEMS"),
        ("dzone", "Defensive Zone", "DZONE_SYSTEMS"),
        ("ozone", "Offensive Zone", "OZONE_SYSTEMS"),
        ("breakout", "Breakout", "BREAKOUT_SYSTEMS"),
        ("pp", "Power Play", "POWERPLAY_SYSTEMS"),
        ("pk", "Penalty Kill", "PENALTY_KILL_SYSTEMS"),
    ]

    def __init__(self, parent, app=None):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED,
                        BLUE=BLUE, ROW_HOVER=ROW_HOVER, ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()

        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the TacticsWindow wrapper
        self.configure(fg_color=BG)

        self._pending = {}          # category -> new system key
        self._key_of_name = {}      # per-category display name -> key
        self._response_text = ""
        self._mp_locked = getattr(self.app, "mp_client", None) is not None
        self._section = "whiteboard"  # or "intel"
        self._footer_hidden = False

        self._create_interface()
        self.refresh()

        _wins = getattr(self.app, "open_windows", None)
        if isinstance(_wins, dict):
            _wins['tactics'] = self

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _on_closing(self):
        try:
            if 'tactics' in self.app.open_windows:
                del self.app.open_windows['tactics']
        except Exception:
            pass
        self.close_view()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _team(self):
        return getattr(self.app, "user_team", None)

    def _head_coach(self, team):
        try:
            for s in getattr(team, 'staff', []) or []:
                if 'Head Coach' in str(getattr(getattr(s, 'role', None), 'value', '')):
                    return s
        except Exception:
            pass
        return None

    def _team_context(self):
        ctx = {"win_pct": 0.5, "losing_streak": 0}
        try:
            team = self._team()
            st = self.app.league.standings.get(team.team_name, {})
            w = st.get('W', st.get('Wins', 0))
            l = st.get('L', st.get('Losses', 0))
            otl = st.get('OTL', 0)
            ctx["win_pct"] = w / max(1, w + l + otl)
            ctx["losing_streak"] = int(st.get("losing_streak", st.get("streak", 0)) or 0)
        except Exception:
            pass
        return ctx

    def _catalog(self, attr):
        return getattr(tx, attr)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _create_interface(self):
        ct = self._ct
        self._header = ctk.CTkFrame(self, fg_color=ct['PANEL'], corner_radius=10)
        self._header.pack(fill='x', padx=14, pady=(14, 8))
        self._header_title = self._heading(self._header, text="Tactics", size=16)
        self._header_title.pack(anchor='w', padx=14, pady=(10, 0))
        self._header_sub = self._body(self._header, text="", size=11)
        self._header_sub.pack(anchor='w', padx=14)
        secrow = ctk.CTkFrame(self._header, fg_color="transparent")
        secrow.pack(fill='x', padx=14, pady=(4, 2))
        self._section_seg = ctk.CTkSegmentedButton(
            secrow, values=["Whiteboard", "League Intel"],
            command=self._on_section,
            selected_color=ct['TEAL'], selected_hover_color=ct['TEAL_HOVER'],
            unselected_color=ct['CARD'], unselected_hover_color=ct['ROW_HOVER'])
        self._section_seg.pack(side='left')
        self._section_seg.set("Whiteboard")
        famrow = ctk.CTkFrame(self._header, fg_color="transparent")
        famrow.pack(fill='x', padx=14, pady=(6, 4))
        self._body(famrow, text="System familiarity", size=11).pack(side='left')
        self._fam_bar = ctk.CTkProgressBar(famrow, width=220, height=10,
                                           progress_color=ct['TEAL'],
                                           bg_color=ct['PANEL'])
        self._fam_bar.pack(side='left', padx=10)
        self._fam_label = self._body(famrow, text="", size=11)
        self._fam_label.pack(side='left')
        self._control_label = self._body(self._header, text="", size=11)
        self._control_label.pack(anchor='w', padx=14, pady=(0, 10))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill='both', expand=True, padx=14, pady=4)
        self._cards = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._cards.pack(fill='both', expand=True)

        self._footer = ctk.CTkFrame(self, fg_color=ct['PANEL'], corner_radius=10)
        self._footer.pack(fill='x', padx=14, pady=(8, 14))
        self._pending_label = self._body(self._footer, text="", size=11)
        self._pending_label.pack(anchor='w', padx=14, pady=(8, 0))
        self._preview_label = self._body(self._footer, text="", size=11)
        self._preview_label.pack(anchor='w', padx=14)
        btnrow = ctk.CTkFrame(self._footer, fg_color="transparent")
        btnrow.pack(fill='x', padx=10, pady=(4, 6))
        self._btn_suggest = self._primary_button(btnrow, text="Suggest to Coach",
                                                 command=self._on_suggest)
        self._btn_enforce = self._secondary_button(btnrow, text="Enforce Tactics",
                                                   command=self._on_enforce)
        self._btn_takeover = self._secondary_button(btnrow, text="Take Over Whiteboard",
                                                    command=self._on_takeover)
        self._btn_handback = self._secondary_button(btnrow, text="Hand Back to Coach",
                                                     command=self._on_handback)
        self._btn_save_pref = self._secondary_button(btnrow, text="Save as Preferred",
                                                     command=self._on_save_pref)
        self._btn_load_pref = self._secondary_button(btnrow, text="Load Preferred",
                                                     command=self._on_load_pref)
        for b in (self._btn_suggest, self._btn_enforce, self._btn_takeover,
                  self._btn_handback, self._btn_save_pref, self._btn_load_pref):
            b.pack(side='left', padx=6)
        presetrow = ctk.CTkFrame(self._footer, fg_color="transparent")
        presetrow.pack(fill='x', padx=10, pady=(2, 2))
        self._body(presetrow, text="Identity:", size=11).pack(side='left', padx=(4, 2))
        for _pkey, _pmeta in tx.IDENTITY_PRESETS.items():
            _b = self._secondary_button(
                presetrow, text=_pmeta["name"],
                command=lambda k=_pkey: self._on_identity_preset(k))
            _b.pack(side='left', padx=4)
            _tip = _pmeta.get("blurb", "")
            if _tip:
                try:
                    _b.configure(text=f"{_pmeta['name']}")  # tooltip via title below
                except Exception:
                    pass
        self._response_label = self._body(self._footer, text="", size=11)
        self._response_label.pack(anchor='w', padx=14, pady=(0, 10))

    # ------------------------------------------------------------------
    # Sections: Whiteboard vs League Intel
    # ------------------------------------------------------------------
    def _on_section(self, value):
        self._section = "intel" if value == "League Intel" else "whiteboard"
        self.refresh()

    def _set_footer_visible(self, visible):
        if visible == (not self._footer_hidden):
            return
        if visible:
            self._footer.pack(fill='x', padx=14, pady=(8, 14))
            self._footer_hidden = False
        else:
            self._footer.pack_forget()
            self._footer_hidden = True

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self):
        ct = self._ct
        team = self._team()
        if team is None:
            return
        try:
            tx.ensure_team_tactics(team)
            tk_ = tx.team_tactics(team)
        except Exception:
            tk_ = {}
        coach = self._head_coach(team)
        cname = getattr(coach, "full_name", "No head coach") if coach else "No head coach"
        control = tx.get_tactics_control(team)

        identity = tx.describe_team_tactics(team)
        self._header_title.configure(
            text=f"{getattr(team, 'team_name', 'Tactics')} -- Tactics")
        self._header_sub.configure(text=" | ".join(identity))

        fam = float(getattr(team, "tactics_familiarity", 85) or 85)
        self._fam_bar.set(max(0.0, min(1.0, fam / 100.0)))
        self._fam_label.configure(text=f"{fam:.0f}%")

        if control == "coach":
            self._control_label.configure(
                text=f"Whiteboard: {cname} -- change a system below, then "
                     f"suggest it, enforce it, or take the whiteboard.",
                text_color=ct['TEXT_DIM'])
        else:
            self._control_label.configure(
                text="Whiteboard: YOU (GM) -- changes apply immediately. "
                     "The coach works with your systems.",
                text_color=ct['GOLD'])

        # League Intel is its own clean section: no whiteboard cards, no footer.
        if self._section == "intel":
            self._set_footer_visible(False)
            self._build_intel()
            return
        self._set_footer_visible(True)

        # Fit snapshot for the installed systems.
        try:
            rfit = tx.team_system_fit(team)
            cfit = tx.coach_tactics_fit(coach, team) if coach else 1.0
            fit_txt = f"Roster fit {rfit:.2f}  |  Coach fit {cfit:.2f}"
        except Exception:
            fit_txt = ""

        # Rebuild the seven module cards.
        for w in self._cards.winfo_children():
            w.destroy()
        coach_prefs = tx.ensure_coach_tactics(coach) if coach else {}
        for cat, label, attr in self.CATS:
            catalog = self._catalog(attr)
            self._build_card(cat, label, catalog, tk_.get(cat), coach,
                             coach_prefs.get(cat), fit_txt if cat == "ozone" else "")

        # Footer state.
        n = len(self._pending)
        if n:
            names = ", ".join(f"{c}" for c in self._pending)
            self._pending_label.configure(
                text=f"{n} change{'s' if n > 1 else ''} pending: {names}",
                text_color=ct['GOLD'])
            if control == "coach" and coach is not None:
                try:
                    prev = rs.preview_tactics_discussion(
                        coach, dict(self._pending), self._team_context())
                    self._preview_label.configure(
                        text=f"If you suggest it: {prev['text']}",
                        text_color=ct['TEXT_DIM'])
                except Exception:
                    self._preview_label.configure(text="")
            else:
                self._preview_label.configure(text="")
        else:
            self._pending_label.configure(text="No pending changes.",
                                           text_color=ct['TEXT_FAINT'])
            self._preview_label.configure(text="")

        is_coach = (control == "coach")
        show_action = is_coach and n and not self._mp_locked
        for b in (self._btn_suggest, self._btn_enforce, self._btn_takeover):
            if show_action:
                b.pack(side='left', padx=6)
            else:
                b.pack_forget()
        if (not is_coach) and not self._mp_locked:
            self._btn_handback.pack(side='left', padx=6)
        else:
            self._btn_handback.pack_forget()
        if self._mp_locked:
            self._pending_label.configure(
                text="Multiplayer client: tactics are set by the host.",
                text_color=ct['TEXT_DIM'])
        self._response_label.configure(text=self._response_text or "")

    # ------------------------------------------------------------------
    # League Intel view
    # ------------------------------------------------------------------
    def _intel_card(self, lines):
        """One clean intel card: bold title line + wrapped dim detail lines."""
        ct = self._ct
        card = ctk.CTkFrame(self._cards, fg_color=ct['CARD'], corner_radius=8)
        card.pack(fill='x', padx=6, pady=4)
        first = True
        for text, dim in lines:
            w = self._body(card, text=text, size=11 if dim else 12, dim=dim)
            w.configure(wraplength=640, justify='left')
            w.pack(anchor='w', padx=10, pady=(8, 0) if first else (0, 0))
            first = False
        card.winfo_children()[-1].pack_configure(pady=(0, 8))
        return card

    def _build_intel(self):
        """League Intel section: the book on your systems + the chessboard."""
        ct = self._ct
        for w in self._cards.winfo_children():
            w.destroy()
        team = self._team()
        if team is None:
            return
        try:
            tx.ensure_team_tactics(team)
            user_tk = tx.team_tactics(team)
        except Exception:
            user_tk = {}
        cat_labels = {c: l for c, l, _a in self.CATS}

        # -- Section 1: the book on you ---------------------------------
        self._heading(self._cards, text="THE BOOK ON YOU", size=14).pack(
            anchor='w', padx=6, pady=(6, 0))
        sub = self._body(
            self._cards,
            text="Teams whose scouts have a real read on your systems -- "
                 "and the answer they'd install against you tonight.",
            size=11, dim=True)
        sub.configure(wraplength=640, justify='left')
        sub.pack(anchor='w', padx=6, pady=(0, 2))

        found = False
        try:
            league_teams = getattr(getattr(self.app, "league", None), "teams", []) or []
            uname = getattr(team, "team_name", "")
            for opp in league_teams:
                if opp is team or getattr(opp, "team_name", None) == uname:
                    continue
                for cat, sys_key, heat in tx.damaging_user_systems(opp, team)[:2]:
                    counter = tx.TACTICAL_COUNTERS.get(sys_key)
                    if not counter:
                        continue
                    found = True
                    ccat, answer, why = counter
                    sys_label = (tx.CATALOGS.get(cat, {}).get(sys_key, {})
                                 .get("name", sys_key))
                    ans_label = (tx.CATALOGS.get(ccat, {}).get(answer, {})
                                 .get("name", answer))
                    self._intel_card([
                        (getattr(opp, "team_name", "?"), False),
                        (f"Your {sys_label} is running {heat:.1f}x the answer "
                         f"threshold vs them.", True),
                        (f"Expect: {ans_label} -- {why}.", True),
                    ])
        except Exception:
            pass
        if not found:
            sub2 = self._body(
                self._cards,
                text="No team has a real book on your systems yet. "
                     "Keep winning -- they will.",
                size=11, dim=True)
            sub2.configure(wraplength=640, justify='left')
            sub2.pack(anchor='w', padx=6, pady=4)

        # -- Section 2: the chessboard -----------------------------------
        self._heading(self._cards, text="THE CHESSBOARD", size=14).pack(
            anchor='w', padx=6, pady=(14, 0))
        sub3 = self._body(
            self._cards,
            text="Every system has a hockey answer. This is what the league "
                 "throws at yours.",
            size=11, dim=True)
        sub3.configure(wraplength=640, justify='left')
        sub3.pack(anchor='w', padx=6, pady=(0, 2))
        shown = 0
        for cat, label, _attr in self.CATS:
            sys_key = user_tk.get(cat)
            counter = tx.TACTICAL_COUNTERS.get(sys_key)
            if not counter:
                continue
            shown += 1
            ccat, answer, why = counter
            sys_label = (tx.CATALOGS.get(cat, {}).get(sys_key, {})
                         .get("name", sys_key))
            ans_label = (tx.CATALOGS.get(ccat, {}).get(answer, {})
                         .get("name", answer))
            ans_cat = cat_labels.get(ccat, ccat)
            self._intel_card([
                (f"YOUR {label.upper()}: {sys_label}", False),
                (f"THEIR ANSWER: {ans_label} ({ans_cat})", True),
                (f"{why}.", True),
            ])
        if not shown:
            sub4 = self._body(self._cards,
                              text="No counters mapped for your current systems.",
                              size=11, dim=True)
            sub4.configure(wraplength=640, justify='left')
            sub4.pack(anchor='w', padx=6, pady=4)

    def _build_card(self, cat, label, catalog, current_key, coach,
                    coach_pref_key, fit_txt):
        ct = self._ct
        card = ctk.CTkFrame(self._cards, fg_color=ct['CARD'], corner_radius=10)
        card.pack(fill='x', pady=6, padx=2)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill='x', padx=12, pady=(10, 2))
        self._heading(top, text=label, size=13).pack(side='left')

        names = [v.get("name", k) for k, v in catalog.items()]
        self._key_of_name[cat] = {v.get("name", k): k for k, v in catalog.items()}
        cur_name = catalog.get(current_key, {}).get("name", names[0]) \
            if current_key else names[0]
        # A pending change shows in the dropdown.
        pend_key = self._pending.get(cat)
        if pend_key and pend_key in catalog:
            cur_name = catalog[pend_key].get("name", cur_name)

        combo = ctk.CTkComboBox(top, values=names, state='readonly', width=300,
                                fg_color=ct['PANEL'], border_color=ct['BORDER'],
                                button_color=ct['BG'],
                                dropdown_fg_color=ct['PANEL'],
                                dropdown_text_color=ct['TEXT'],
                                text_color=ct['TEXT'])
        combo.set(cur_name)
        combo.pack(side='right')
        combo.configure(command=lambda _n, c=cat: self._on_pick(c, combo.get()))

        desc = ctk.CTkLabel(card, text="", font=(self._ff(), 11),
                            text_color=ct['TEXT_DIM'], wraplength=920,
                            justify="left", anchor="w")
        desc.pack(fill='x', padx=12, pady=(2, 0))
        trade = ctk.CTkLabel(card, text="", font=(self._ff(), 11, "bold"),
                             text_color=ct['TEXT'], anchor="w")
        trade.pack(fill='x', padx=12)
        fitline = ctk.CTkLabel(card, text="", font=(self._ff(), 10),
                               text_color=ct['TEXT_FAINT'], anchor="w")
        fitline.pack(fill='x', padx=12, pady=(0, 10))

        def _paint(name=cur_name):
            key = self._key_of_name[cat].get(name)
            sys = catalog.get(key, {})
            desc.configure(text=sys.get("blurb", ""))
            trade.configure(text="Expected: " + tx.system_tradeoffs(cat, key))
            bits = []
            if coach is not None and coach_pref_key:
                bits.append("Suits the coach's style"
                            if key == coach_pref_key else "Not his preferred system")
            if fit_txt and cat == "ozone":
                bits.append(fit_txt)
            fitline.configure(text="  |  ".join(bits))

        _paint()
        # Note: _on_pick calls refresh(), which rebuilds the cards with the
        # pending selection shown -- no extra repaint needed here.

    def _ff(self):
        return "Segoe UI"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_identity_preset(self, preset_key):
        """One-click identity install: stages all seven modules as pending
        changes so they flow through the normal suggest/enforce path."""
        team = self._team()
        if team is None:
            return
        meta = tx.IDENTITY_PRESETS.get(preset_key, {})
        modules = meta.get("modules", {})
        if not modules:
            return
        try:
            current = tx.team_tactics(team)
        except Exception:
            current = {}
        n = 0
        for cat, key in modules.items():
            try:
                catalog = tx.CATALOGS.get(cat, {})
            except Exception:
                catalog = {}
            if key in catalog and current.get(cat) != key:
                self._pending[cat] = key
                n += 1
        self._response_text = (f"{meta.get('name', preset_key)} staged "
                               f"({n} modules) -- suggest it to the coach or "
                               f"enforce it." if n else
                               f"{meta.get('name', preset_key)} already installed.")
        self.refresh()

    def _on_pick(self, cat, display_name):
        team = self._team()
        if team is None:
            return
        key = self._key_of_name.get(cat, {}).get(display_name)
        if not key:
            return
        try:
            current = tx.team_tactics(team).get(cat)
        except Exception:
            current = None
        if key == current:
            self._pending.pop(cat, None)
        elif tx.get_tactics_control(team) == "gm":
            # The GM owns the whiteboard: changes apply immediately.
            tx.set_team_system(team, cat, key)
            self._pending.pop(cat, None)
            self._response_text = ""
        else:
            # Coach owns it: stage the change until suggest/enforce/takeover.
            self._pending[cat] = key
        self.refresh()

    def _on_suggest(self):
        team = self._team()
        if team is None or not self._pending:
            return
        try:
            res = rs.suggest_tactics_to_coach(team, dict(self._pending),
                                             self._team_context())
        except Exception as e:
            res = {"applied": False, "text": f"Could not suggest: {e}"}
        if res.get("applied"):
            self._pending.clear()
        self._response_text = res.get("text", "")
        try:
            news = getattr(self.app, "add_news", None)
            if news and res.get("applied"):
                news(f"Tactics: {res['text']}")
        except Exception:
            pass
        self.refresh()

    def _on_enforce(self):
        team = self._team()
        if team is None or not self._pending:
            return
        if not messagebox.askyesno(
                "Enforce Tactics",
                "Overrule your head coach and enforce these systems?\n"
                "It works -- and he won't forget it."):
            return
        try:
            res = rs.enforce_tactics(team, dict(self._pending),
                                     self._team_context())
        except Exception as e:
            res = {"applied": False, "text": f"Could not enforce: {e}"}
        if res.get("applied"):
            self._pending.clear()
        self._response_text = res.get("text", "")
        try:
            news = getattr(self.app, "add_news", None)
            if news and res.get("applied"):
                news(f"Tactics: {res['text']}")
        except Exception:
            pass
        self.refresh()

    def _on_takeover(self):
        team = self._team()
        if team is None:
            return
        if not messagebox.askyesno(
                "Take Over Whiteboard",
                "Take permanent control of tactics from your head coach?\n"
                "His reaction will depend on his personality."):
            return
        try:
            res = rs.take_over_tactics(team, self._team_context())
        except Exception as e:
            res = {"changed": False, "text": f"Could not take over: {e}"}
        if res.get("changed"):
            # Pending changes are yours now -- apply them.
            try:
                for cat, key in list(self._pending.items()):
                    tx.set_team_system(team, cat, key)
                self._pending.clear()
            except Exception:
                pass
        self._response_text = res.get("text", "")
        try:
            news = getattr(self.app, "add_news", None)
            if news and res.get("changed"):
                news(f"Tactics: {res['text']}")
        except Exception:
            pass
        self.refresh()

    def _on_handback(self):
        team = self._team()
        if team is None:
            return
        try:
            res = rs.hand_back_tactics(team)
        except Exception as e:
            res = {"changed": False, "text": f"Could not hand back: {e}"}
        self._response_text = res.get("text", "")
        self.refresh()

    def _on_save_pref(self):
        team = self._team()
        if team is None:
            return
        try:
            tx.save_preferred_tactics(team)
            self._response_text = ("Preferred tactics saved -- one click gets "
                                   "you back to your hockey.")
        except Exception as e:
            self._response_text = f"Could not save: {e}"
        self.refresh()

    def _on_load_pref(self):
        team = self._team()
        if team is None:
            return
        try:
            pref = tx.get_preferred_tactics(team)
        except Exception:
            pref = None
        if not pref:
            self._response_text = "No preferred tactics saved yet."
            self.refresh()
            return
        try:
            current = tx.team_tactics(team)
        except Exception:
            current = {}
        self._pending = {c: k for c, k in pref.items()
                         if current.get(c) != k}
        if tx.get_tactics_control(team) == "gm":
            for cat, key in list(self._pending.items()):
                tx.set_team_system(team, cat, key)
            self._pending.clear()
            self._response_text = "Preferred tactics installed."
        else:
            self._response_text = ("Preferred tactics staged -- suggest them to "
                                   "your coach, enforce them, or take over.")
        self.refresh()


class TacticsWindow(InGamePopup):
    """Popup wrapper around TacticsView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Team Tactics")
        self._view = TacticsView(self, app=parent, *args, **kwargs)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)
    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)
