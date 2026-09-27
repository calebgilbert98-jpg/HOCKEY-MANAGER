# morale_window.py
# FM24-style Team Morale screen, tailored to Puck Dynasty's NHL systems:
# coaching style + player engagement fit, live player response to the coach,
# GM advisories, line control, team actions, and the dynamics feed.
# CustomTkinter: CTkToplevel chrome, dark ttk.Treeview, CTkScrollableFrame.

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

import reputation_system as rs


class MoraleWindow(ctk.CTkToplevel):
    """Team Morale - dressing-room dynamics at a glance."""

    RESPONSE_TAGS = {
        "Bought in": "resp_good",
        "Neutral": "resp_neutral",
        "Tuning out": "resp_warn",
        "Quit on coach": "resp_bad",
    }

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()

        super().__init__(parent)
        self.parent = parent
        self.title("Team Morale")
        self.configure(fg_color=BG)
        self.geometry("1280x920")
        self.minsize(1060, 760)

        self._setup_tree_style()
        self._create_interface()
        self.refresh()

        parent.open_windows['morale'] = self
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        try:
            if 'morale' in self.parent.open_windows:
                del self.parent.open_windows['morale']
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Morale.Treeview',
                        background=ct['CARD'], fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'], rowheight=26,
                        font=('Segoe UI', 10))
        style.configure('Morale.Treeview.Heading',
                        background=ct['PANEL'], foreground=ct['TEXT_DIM'],
                        font=('Segoe UI', 10, 'bold'))
        style.map('Morale.Treeview', background=[('selected', ct['ROW_SELECTED'])])
        self.tree_tags = {
            'resp_good': {'foreground': ct['GREEN']},
            'resp_neutral': {'foreground': ct['TEXT_DIM']},
            'resp_warn': {'foreground': ct['GOLD']},
            'resp_bad': {'foreground': ct['RED']},
        }

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _create_interface(self):
        ct = self._ct
        main = ctk.CTkFrame(self, fg_color=ct['BG'])
        main.pack(fill='both', expand=True, padx=12, pady=12)

        # Header
        header = ctk.CTkFrame(main, fg_color=ct['PANEL'], corner_radius=10)
        header.pack(fill='x', pady=(0, 10))
        self._heading(header, text="Team Morale").pack(side='left', padx=16, pady=10)
        self.header_score = ctk.CTkLabel(header, text="", font=('Segoe UI', 15, 'bold'))
        self.header_score.pack(side='right', padx=16, pady=10)

        # Row 1: Coaching card + Watch list
        row1 = ctk.CTkFrame(main, fg_color=ct['BG'])
        row1.pack(fill='x', pady=(0, 10))

        coach_card = self._make_card(row1, "Coaching")
        coach_card.pack(side='left', fill='both', expand=True, padx=(0, 6))
        self.coach_body = ctk.CTkLabel(coach_card, text="", justify='left',
                                       font=('Segoe UI', 11))
        self.coach_body.pack(anchor='w', padx=12, pady=(0, 6))
        coach_btns = ctk.CTkFrame(coach_card, fg_color=ct['CARD'])
        coach_btns.pack(fill='x', padx=12, pady=(0, 10))
        self._secondary_button(coach_btns, text="Advise Coach",
                               command=self._open_advise_popup).pack(side='left', padx=(0, 6))
        self.line_btn = self._secondary_button(coach_btns, text="Lines: Coach",
                                               command=self._toggle_line_control)
        self.line_btn.pack(side='left', padx=6)
        # Team actions the GM can order
        self._secondary_button(coach_btns, text="Bag Skate",
                               command=self._do_bag_skate).pack(side='left', padx=6)
        self._secondary_button(coach_btns, text="Speech",
                               command=self._do_speech).pack(side='left', padx=6)
        self._secondary_button(coach_btns, text="Practice",
                               command=self._do_practice).pack(side='left', padx=6)

        watch_card = self._make_card(row1, "Watch List")
        watch_card.pack(side='left', fill='both', expand=True, padx=(6, 0))
        self.watch_body = ctk.CTkLabel(watch_card, text="", justify='left',
                                       font=('Segoe UI', 11), wraplength=420)
        self.watch_body.pack(anchor='w', padx=12, pady=(0, 10))

        # Row 2: Player response table
        resp_card = self._make_card(main, "Player Response to Coach")
        resp_card.pack(fill='both', expand=False, pady=(0, 10))
        cols = ('player', 'engagement', 'response', 'happiness', 'attitude', 'tier')
        self.tree = ttk.Treeview(resp_card, columns=cols, show='headings',
                                 style='Morale.Treeview', height=9)
        headers = {'player': 'Player', 'engagement': 'Engagement Style',
                   'response': 'Response', 'happiness': 'Happiness',
                   'attitude': 'Attitude', 'tier': 'Tier'}
        widths = {'player': 190, 'engagement': 190, 'response': 120,
                  'happiness': 90, 'attitude': 140, 'tier': 110}
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c],
                             anchor='w' if c in ('player', 'engagement') else 'center')
        for tag, kw in self.tree_tags.items():
            self.tree.tag_configure(tag, **kw)
        self.tree.pack(fill='x', padx=12, pady=(0, 6))

        # Row 3: Dynamics feed + Hierarchy/Social
        row3 = ctk.CTkFrame(main, fg_color=ct['BG'])
        row3.pack(fill='both', expand=True)

        feed_card = self._make_card(row3, "Dynamics Feed")
        feed_card.pack(side='left', fill='both', expand=True, padx=(0, 6))
        self.feed_frame = ctk.CTkScrollableFrame(feed_card, fg_color=ct['CARD'],
                                                 corner_radius=8, height=150)
        self.feed_frame.pack(fill='both', expand=True, padx=12, pady=(0, 10))

        right_col = ctk.CTkFrame(row3, fg_color=ct['BG'])
        right_col.pack(side='left', fill='both', expand=True, padx=(6, 0))
        hier_card = self._make_card(right_col, "Hierarchy")
        hier_card.pack(fill='x', pady=(0, 10))
        self.hier_body = ctk.CTkLabel(hier_card, text="", justify='left',
                                      font=('Segoe UI', 10))
        self.hier_body.pack(anchor='w', padx=12, pady=(0, 8))
        sg_card = self._make_card(right_col, "Social Groups")
        sg_card.pack(fill='x')
        self.sg_body = ctk.CTkLabel(sg_card, text="", justify='left',
                                    font=('Segoe UI', 10))
        self.sg_body.pack(anchor='w', padx=12, pady=(0, 8))

        # Footer
        footer = ctk.CTkFrame(main, fg_color=ct['BG'])
        footer.pack(fill='x', pady=(8, 0))
        self._secondary_button(footer, text="Refresh",
                               command=self.refresh).pack(side='right')

    def _make_card(self, parent, title):
        ct = self._ct
        card = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=10,
                            border_width=1, border_color=ct['BORDER'])
        self._heading(card, text=title, size=14).pack(anchor='w', padx=12, pady=(8, 4))
        return card

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _team_context(self):
        ctx = {"win_pct": 0.5, "room_leadership": 50, "losing_streak": 0}
        try:
            team = self.parent.user_team
            st = self.parent.league.standings.get(team.team_name, {})
            w = st.get('W', st.get('Wins', 0))
            l = st.get('L', st.get('Losses', 0))
            otl = st.get('OTL', 0)
            ctx["win_pct"] = w / max(1, w + l + otl)
            # losing streak from recent form if the league tracks it
            ctx["losing_streak"] = int(st.get("losing_streak", st.get("streak", 0)) or 0)
            leaders = rs.team_hierarchy(list(team.roster)).get("Team Leaders", [])
            if leaders:
                ctx["room_leadership"] = sum(
                    getattr(p, 'leadership', 50) or 50 for p in leaders) / len(leaders)
        except Exception:
            pass
        return ctx

    def _head_coach(self, team):
        try:
            for s in getattr(team, 'staff', []) or []:
                if 'Head Coach' in str(getattr(getattr(s, 'role', None), 'value', '')):
                    return s
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _do_bag_skate(self):
        try:
            team = self.parent.user_team
            coach = self._head_coach(team)
            if coach is None:
                return
            rs.apply_bag_skate(team, coach, list(team.roster))
            self.refresh()
        except Exception:
            pass

    def _do_speech(self):
        try:
            team = self.parent.user_team
            coach = self._head_coach(team)
            if coach is None:
                return
            rs.apply_inspiring_speech(team, coach, list(team.roster))
            self.refresh()
        except Exception:
            pass

    def _do_practice(self):
        try:
            team = self.parent.user_team
            coach = self._head_coach(team)
            if coach is None:
                return
            rs.apply_great_practice(team, coach, list(team.roster))
            self.refresh()
        except Exception:
            pass

    def _toggle_line_control(self):
        try:
            team = self.parent.user_team
            ctx = self._team_context()
            current = getattr(team, 'line_control', 'coach') or 'coach'
            target = 'gm' if current == 'coach' else 'coach'
            rs.set_line_control(team, target, ctx, list(team.roster))
            self.refresh()
        except Exception:
            pass

    def _open_advise_popup(self):
        try:
            team = self.parent.user_team
            coach = self._head_coach(team)
            if coach is None:
                return
            AdviseCoachPopup(self, coach, team, list(team.roster),
                            on_done=self.refresh)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self):
        ct = self._ct
        try:
            team = self.parent.user_team
            roster = list(team.roster)
        except Exception:
            return
        ctx = self._team_context()
        coach = self._head_coach(team)
        chem = rs.team_chemistry(roster, ctx)
        hierarchy = rs.team_hierarchy(roster)
        groups = rs.social_groups(roster)
        tier_of = {}
        for tier, ps in hierarchy.items():
            for p in ps:
                tier_of[id(p)] = tier

        # Header
        score, label = chem["score"], chem["label"]
        color = ct['GREEN'] if score >= 65 else ct['GOLD'] if score >= 50 else ct['RED']
        w, l = self._record()
        self.header_score.configure(
            text=f"{team.team_name} ({w}-{l})  •  {score}/100 {label}",
            text_color=color)

        # Coaching card
        if coach is not None:
            rs.ensure_reputation_fields(coach)
            style = rs.coach_style(coach)
            st = rs.room_status(coach, ctx, roster)
            lc = getattr(team, 'line_control', 'coach') or 'coach'
            self.coach_body.configure(
                text=f"{getattr(coach, 'full_name', 'Coach')}  •  {style['label']}\n"
                     f"{style['description']}\n"
                     f"Motivating {getattr(coach, 'motivating', '?')}  •  "
                     f"Discipline {getattr(coach, 'discipline', '?')}  •  "
                     f"Leadership {getattr(coach, 'leadership', '?')}  •  "
                     f"Man-mgmt {getattr(coach, 'man_management', '?')}\n"
                     f"Room status: {st['level']} ({st['risk']:.0%} risk)  •  "
                     f"GM trust: {getattr(coach, 'gm_trust', 70)}/100")
            self.line_btn.configure(text=f"Lines: {'YOU (GM)' if lc == 'gm' else 'Coach'}")
        else:
            self.coach_body.configure(text="No head coach on staff.")
            self.line_btn.configure(text="Lines: Coach")

        # Watch list
        if coach is not None:
            issues = rs.detect_dynamics_issues(team, ctx, roster, coach)
        else:
            issues = []
        if issues:
            sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            lines = [f"{sev_icon.get(i['severity'], '•')} {i['text']}" for i in issues]
            self.watch_body.configure(text="\n\n".join(lines))
        else:
            self.watch_body.configure(text="🟢 No structural issues detected. The room is stable.")

        # Player response table
        for row in self.tree.get_children():
            self.tree.delete(row)
        for p in sorted(roster, key=lambda x: rs.hierarchy_score(x), reverse=True):
            rs.ensure_reputation_fields(p)
            resp = rs.player_coach_response(p, coach, ctx) if coach else \
                {"label": "Neutral", "engagement": rs.engagement_style(p)["label"]}
            tag = self.RESPONSE_TAGS.get(resp["label"], "resp_neutral")
            self.tree.insert('', 'end', values=(
                getattr(p, 'full_name', 'Unknown'),
                resp["engagement"],
                resp["label"],
                f"{getattr(p, 'happiness', 70) or 0}/100",
                rs.describe_attitude(p),
                tier_of.get(id(p), '-'),
            ), tags=(tag,))

        # Dynamics feed
        for wdg in self.feed_frame.winfo_children():
            wdg.destroy()
        feed = rs.get_dynamics_feed(team, limit=25)
        if not feed:
            ctk.CTkLabel(self.feed_frame, text="No dynamics yet this season.",
                         font=('Segoe UI', 11),
                         text_color=ct['TEXT_FAINT']).pack(anchor='w', padx=8, pady=4)
        for ev in feed:
            icon = {"up": "▲", "down": "▼"}.get(ev.get("tone"), "•")
            tcolor = {"up": ct['GREEN'], "down": ct['RED']}.get(ev.get("tone"), ct['TEXT_DIM'])
            row = ctk.CTkFrame(self.feed_frame, fg_color='transparent')
            row.pack(fill='x', padx=4, pady=2)
            ctk.CTkLabel(row, text=icon, font=('Segoe UI', 11, 'bold'),
                         text_color=tcolor, width=20).pack(side='left')
            ctk.CTkLabel(row, text=f"{ev.get('date', '')}  {ev.get('text', '')}",
                         font=('Segoe UI', 10), text_color=ct['TEXT'],
                         wraplength=520, justify='left').pack(side='left', fill='x', expand=True)

        # Hierarchy + social groups (compact)
        hier_lines = []
        for tier in rs.HIERARCHY_TIERS:
            ps = hierarchy.get(tier, [])
            names = ", ".join(getattr(p, 'first_name', '?') for p in ps[:5])
            more = f" +{len(ps) - 5}" if len(ps) > 5 else ""
            hier_lines.append(f"{tier} ({len(ps)}): {names}{more}")
        self.hier_body.configure(text="\n".join(hier_lines))
        sg_lines = [f"{g} ({len(ps)})" for g, ps in groups.items()]
        self.sg_body.configure(text="   •   ".join(sg_lines))

    def _record(self):
        try:
            st = self.parent.league.standings.get(self.parent.user_team.team_name, {})
            return st.get('W', st.get('Wins', 0)), st.get('L', st.get('Losses', 0))
        except Exception:
            return 0, 0


class AdviseCoachPopup(ctk.CTkToplevel):
    """GM advisory popup: pick guidance, see whether the coach listens."""

    def __init__(self, parent_win, coach, team, roster, on_done=None):
        from ctk_theme import (
            init_ctk_theme, secondary_button, heading,
            BG, PANEL, TEXT_DIM,
        )
        init_ctk_theme()
        super().__init__(parent_win)
        self.title("Advise Coach")
        self.configure(fg_color=BG)
        self.geometry("520x560")
        self.minsize(460, 480)
        self._coach = coach
        self._team = team
        self._roster = roster
        self._on_done = on_done

        cname = getattr(coach, 'full_name', 'Coach')
        style = rs.coach_style(coach)
        heading(self, text=f"Advise {cname}").pack(anchor='w', padx=16, pady=(12, 2))
        ctk.CTkLabel(self,
                     text=f"{style['label']}  •  GM trust {getattr(coach, 'gm_trust', 70)}/100\n"
                          f"Whether he listens depends on personality -- brash coaches take advice as an insult.",
                     font=('Segoe UI', 11), text_color=TEXT_DIM,
                     justify='left', wraplength=480).pack(anchor='w', padx=16, pady=(0, 10))

        btn_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        btn_frame.pack(fill='both', expand=True, padx=16, pady=(0, 10))
        for key, label in rs.ADVICE_TYPES.items():
            secondary_button(btn_frame, text=label,
                             command=lambda k=key: self._give_advice(k)).pack(
                                 fill='x', padx=10, pady=5)

        self.result = ctk.CTkLabel(self, text="", font=('Segoe UI', 11),
                                   wraplength=480, justify='left')
        self.result.pack(padx=16, pady=(0, 12))

    def _give_advice(self, key):
        from ctk_theme import GREEN, RED
        try:
            out = rs.advise_coach(self._coach, key, self._team, self._roster)
            color = GREEN if out["listened"] else RED
            heard = "LISTENED" if out["listened"] else "IGNORED"
            self.result.configure(
                text=f"{heard} (p={out['probability']:.0%}): {out['text']}",
                text_color=color)
            if self._on_done:
                self._on_done()
        except Exception:
            pass
