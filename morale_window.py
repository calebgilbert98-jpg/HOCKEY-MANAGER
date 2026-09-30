# morale_window.py
# FM24-style Team Morale screen, tailored to Puck Dynasty's NHL systems:
# coaching style + player engagement fit, live player response to the coach,
# GM advisories, line control, team actions, and the dynamics feed.
# CustomTkinter: CTkToplevel chrome, dark ttk.Treeview, CTkScrollableFrame.

from popup_system import InGamePopup
from tkinter import ttk

import customtkinter as ctk

import reputation_system as rs
import dressing_room as dr_room


class MoraleView(ctk.CTkFrame):
    """Team Morale - dressing-room dynamics at a glance."""

    RESPONSE_TAGS = {
        "Bought in": "resp_good",
        "Neutral": "resp_neutral",
        "Tuning out": "resp_warn",
        "Quit on coach": "resp_bad",
    }

    def __init__(self, parent, app=None):
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

        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the MoraleWindow wrapper
        self.configure(fg_color=BG)

        self._setup_tree_style()
        self._create_interface()
        self.refresh()

        self.app.open_windows['morale'] = self

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _on_closing(self):
        try:
            if 'morale' in self.app.open_windows:
                del self.app.open_windows['morale']
        except Exception:
            pass
        self.close_view()

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
                                               command=self._open_line_control_popup)
        self.line_btn.pack(side='left', padx=6)
        # Team actions the GM can order
        self._secondary_button(coach_btns, text="Bag Skate",
                               command=self._do_bag_skate).pack(side='left', padx=6)
        self._secondary_button(coach_btns, text="Speech",
                               command=self._do_speech).pack(side='left', padx=6)
        self._secondary_button(coach_btns, text="Practice",
                               command=self._do_practice).pack(side='left', padx=6)
        self._secondary_button(coach_btns, text="Back Room",
                               command=self._do_back_room).pack(side='left', padx=6)

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
        sg_card.pack(fill='x', pady=(0, 10))
        self.sg_body = ctk.CTkLabel(sg_card, text="", justify='left',
                                    font=('Segoe UI', 10), wraplength=400)
        self.sg_body.pack(anchor='w', padx=12, pady=(0, 8))
        riv_card = self._make_card(right_col, "Rivalries & Bad Blood")
        riv_card.pack(fill='x')
        self.riv_body = ctk.CTkLabel(riv_card, text="", justify='left',
                                     font=('Segoe UI', 10), wraplength=380)
        self.riv_body.pack(anchor='w', padx=12, pady=(0, 6))
        self._secondary_button(riv_card, text="Declare Rival",
                               command=self._open_declare_rival_popup).pack(
                                   anchor='w', padx=12, pady=(0, 10))

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
            team = self.app.user_team
            st = self.app.league.standings.get(team.team_name, {})
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

    def _mp_send(self, action, params):
        """Route a GM action to the multiplayer host when this is a client.

        Returns True when routed (the caller must NOT mutate local state --
        the host applies it and the next STATE_SYNC refreshes this window).
        The host is always local (mp_client is None) and keeps working
        exactly as before.
        """
        try:
            client = getattr(self.app, "mp_client", None)
            if client is None:
                return False
            params = dict(params or {})
            team = getattr(self.app, "user_team", None)
            params.setdefault("team_id",
                              getattr(team, "team_name", "") if team else "")
            client.send_action(action, params)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _do_bag_skate(self):
        if self._mp_send("team_event", {"event": "bag_skate"}):
            return
        try:
            team = self.app.user_team
            coach = self._head_coach(team)
            if coach is None:
                return
            rs.apply_bag_skate(team, coach, list(team.roster))
            self.refresh()
        except Exception:
            pass

    def _do_speech(self):
        if self._mp_send("team_event", {"event": "inspiring_speech"}):
            return
        try:
            team = self.app.user_team
            coach = self._head_coach(team)
            if coach is None:
                return
            rs.apply_inspiring_speech(team, coach, list(team.roster))
            self.refresh()
        except Exception:
            pass

    def _do_practice(self):
        if self._mp_send("team_event", {"event": "great_practice"}):
            return
        try:
            team = self.app.user_team
            coach = self._head_coach(team)
            if coach is None:
                return
            rs.apply_great_practice(team, coach, list(team.roster))
            self.refresh()
        except Exception:
            pass

    def _do_back_room(self):
        """GM goes on the record for his people. Small, honest lift."""
        if self._mp_send("team_event", {"event": "gm_backing"}):
            return
        try:
            import media_engine
            team = self.app.user_team
            media_engine.gm_public_backing(
                getattr(self.app, 'league', None), team, "room",
                user_triggered=True)
            self.refresh()
        except Exception:
            pass

    def _open_line_control_popup(self):
        try:
            team = self.app.user_team
            current = getattr(team, 'line_control', 'coach') or 'coach'
            if current == 'gm':
                # Giving the pen back is always amicable.
                if self._mp_send("set_line_control", {"holder": "coach"}):
                    return
                rs.set_line_control(team, 'coach', self._team_context(),
                                    list(team.roster))
                self.refresh()
                return
            coach = self._head_coach(team)
            if coach is None:
                return
            LineControlPopup(self, coach, team, list(team.roster),
                             self._team_context(), on_done=self.refresh)
        except Exception:
            pass

    def _open_declare_rival_popup(self):
        try:
            team = self.app.user_team
            DeclareRivalPopup(self, team, self.app.league,
                              on_done=self.refresh)
        except Exception:
            pass

    def _open_advise_popup(self):
        try:
            team = self.app.user_team
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
            team = self.app.user_team
            roster = list(team.roster)
        except Exception:
            return
        ctx = self._team_context()
        coach = self._head_coach(team)
        chem = rs.team_chemistry(roster, ctx)
        hierarchy = rs.team_hierarchy(roster)
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
            amb = rs.COACH_AMBITIONS.get(getattr(coach, 'ambition', 'climb'),
                                             getattr(coach, 'ambition', ''))
            fav = getattr(coach, 'favorite_team', '') or ''
            preview = rs.preview_line_control_discussion(coach, ctx)
            self.coach_body.configure(
                text=f"{getattr(coach, 'full_name', 'Coach')}  •  {style['label']}  •  "
                     f"{rs.control_label(coach)}\n"
                     f"{style['description']}\n"
                     f"Motivating {getattr(coach, 'motivating', '?')}  •  "
                     f"Discipline {getattr(coach, 'discipline', '?')}  •  "
                     f"Leadership {getattr(coach, 'leadership', '?')}  •  "
                     f"Man-mgmt {getattr(coach, 'man_management', '?')}  •  "
                     f"Youth {getattr(coach, 'working_with_youngsters', '?')}\n"
                     f"Ambition: {amb}" + (f"  •  Boyhood team: {fav}" if fav else "") + "\n"
                     f"Room status: {st['level']} ({st['risk']:.0%} risk)  •  "
                     f"GM trust: {getattr(coach, 'gm_trust', 70)}/100  •  "
                     f"Influence: {getattr(coach, 'influence', 70)}/100\n"
                     f"If you discuss the lines: {preview['text']}")
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
        self.sg_body.configure(text=self._social_groups_text(team, roster))
        self._refresh_rivalries(team, coach, roster)

    def _social_groups_text(self, team, roster):
        """Social Groups card: room atmosphere, cohesion, and every
        affinity clique with its leader and bond. Falls back quietly
        if the clique engine can't read this roster."""
        try:
            cliques = dr_room.form_cliques(team)
        except Exception:
            cliques = []
        lines = []
        try:
            atm = dr_room.room_atmosphere(team)
            if isinstance(atm, dict):
                label = atm.get("label", "Steady")
            else:
                label = atm[0]
            coh = dr_room.cohesion(team)
            aicon = {"Electric": "\u26a1", "Tight-knit": "\U0001f91d",
                     "Steady": "\U0001f642", "Strained": "\U0001f61f",
                     "Fractured": "\U0001f494"}.get(label, "\u2022")
            lines.append(f"{aicon} Room: {label}  \u2022  "
                         f"cohesion {int(round(coh))}%")
        except Exception:
            pass
        for g in cliques:
            try:
                bond = float(g.get("bond", 0.5))
            except Exception:
                bond = 0.5
            bdesc = "tight" if bond >= 0.75 else "solid" if bond >= 0.55 \
                else "loose" if bond >= 0.4 else "fragile"
            try:
                infl = float(g.get("leader_influence", 0))
            except Exception:
                infl = 0
            led = f" \u2014 led by {g['leader']}" \
                if g.get("leader") and infl >= 70 else ""
            members = g.get("members", []) or []
            # form_cliques stores display-name strings
            names = ", ".join(str(m).split()[0] for m in members[:6])
            more = f" +{len(members) - 6}" if len(members) > 6 else ""
            lines.append(f"\u2022 {g.get('name', 'Group')} ({len(members)}): "
                         f"{names}{more}{led} [{bdesc}]")
        try:
            grouped = sum(len(g.get("members", []) or []) for g in cliques)
            floaters = len(roster) - grouped
            if floaters > 0:
                lines.append(f"  {floaters} floater"
                             f"{'s' if floaters != 1 else ''} outside the "
                             f"circles")
        except Exception:
            pass
        return "\n".join(lines) if lines else "No social circles formed yet."

    def _refresh_rivalries(self, team, coach, roster):
        try:
            league = getattr(self.app, 'league', None)
            rivalries = list(getattr(league, 'rivalries', []) or [])
        except Exception:
            rivalries = []
        lines = []
        if coach is not None and rivalries:
            for r in rs.get_rivalries_for(rivalries, coach)[:3]:
                other = r['b_name'] if r['a_name'] == getattr(coach, 'full_name', '') else r['a_name']
                lock = "\U0001f512 " if r.get('solidified') else ""
                lines.append(f"\U0001f525 {lock}{other} ({r['intensity']:.0f} -- {r['origin'].replace('_', ' ')})")
        if rivalries:
            team_rs = [r for r in rivalries
                       if r['kind'] == 'team_team'
                       and (r['a'][1] == team.team_name or r['b'][1] == team.team_name)]
            team_rs.sort(key=lambda r: -r['intensity'])
            for r in team_rs[:3]:
                other = r['b_name'] if r['a'][1] == team.team_name else r['a_name']
                lock = "\U0001f512 " if r.get('solidified') else ""
                lines.append(f"\U0001f3d2 {lock}{other}: {r['intensity']:.0f} ({r['origin'].replace('_', ' ')})")
            # loudest player beef on the roster
            beefs = []
            for p in roster:
                beefs += rs.get_rivalries_for(rivalries, p)
            beefs.sort(key=lambda r: -r['intensity'])
            for r in beefs[:2]:
                lines.append(f"\U0001f94a {r['a_name']} vs {r['b_name']}: {r['intensity']:.0f}")
            my_keys = {("team", team.team_name), ("gm", team.team_name)}
            for r in rs.declared_rivalries_for(rivalries, team):
                other = r['b_name'] if r['a'] in my_keys else r['a_name']
                lines.append(f"\U0001f4e2 Declared rival: {other} ({r['intensity']:.0f})")
        self.riv_body.configure(
            text="\n".join(lines) if lines else "No bad blood on record. Yet.")

    def _record(self):
        try:
            st = self.app.league.standings.get(self.app.user_team.team_name, {})
            return st.get('W', st.get('Wins', 0)), st.get('L', st.get('Losses', 0))
        except Exception:
            return 0, 0

class MoraleWindow(InGamePopup):
    """Popup wrapper around MoraleView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Team Morale")
        self._view = MoraleView(self, app=parent, *args, **kwargs)
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
class AdviseCoachPopup(InGamePopup):
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
        # parent_win is the Morale view; its app is the host (or MP client).
        self._app = getattr(parent_win, 'app', None) or getattr(parent_win, 'parent', None)

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
            if key == "feature_player":
                continue  # handled below with a player picker
            secondary_button(btn_frame, text=label,
                             command=lambda k=key: self._give_advice(k)).pack(
                                 fill='x', padx=10, pady=5)

        # Per-player ask: give one guy more ice time and a bigger role.
        feat_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        feat_frame.pack(fill='x', padx=16, pady=(0, 10))
        ctk.CTkLabel(feat_frame, text="Feature a player -- more ice time, bigger role:",
                     font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 2))
        names = [getattr(p, 'full_name', '?') for p in (roster or [])]
        self._feat_pick = ctk.CTkOptionMenu(feat_frame,
                                            values=names or ["(no players)"])
        self._feat_pick.pack(fill='x', padx=10, pady=4)
        row = ctk.CTkFrame(feat_frame, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=(0, 8))
        secondary_button(row, text="Request",
                         command=self._request_feature).pack(side='left', padx=(0, 6))
        secondary_button(row, text="Rescind",
                         command=self._rescind_feature).pack(side='left')

        self.result = ctk.CTkLabel(self, text="", font=('Segoe UI', 11),
                                   wraplength=480, justify='left')
        self.result.pack(padx=16, pady=(0, 12))

    def _picked_player(self):
        name = self._feat_pick.get()
        for p in (self._roster or []):
            if getattr(p, 'full_name', None) == name:
                return p
        return None

    def _mp_send(self, action, params, note="Sent to the host -- the room will react after the next sync."):
        """Route to the MP host when this machine is a client; True = routed."""
        try:
            client = getattr(self._app, "mp_client", None)
            if client is None:
                return False
            params = dict(params or {})
            params.setdefault("team_id", getattr(self._team, "team_name", ""))
            client.send_action(action, params)
            try:
                from ctk_theme import TEXT_DIM
                self.result.configure(text=note, text_color=TEXT_DIM)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _request_feature(self):
        from ctk_theme import GREEN, RED
        p = self._picked_player()
        if p is None:
            return
        if self._mp_send("advise_coach", {"advice_type": "feature_player",
                                          "target_player_id": str(getattr(p, "id", ""))}):
            return
        try:
            out = rs.advise_coach(self._coach, "feature_player", self._team,
                                  self._roster, target_player=p)
            heard = "LISTENED" if out["listened"] else "IGNORED"
            self.result.configure(
                text=f"{heard} (p={out['probability']:.0%}): {out['text']}",
                text_color=GREEN if out["listened"] else RED)
            if self._on_done:
                self._on_done()
        except Exception:
            pass

    def _rescind_feature(self):
        from ctk_theme import GREEN
        p = self._picked_player()
        if p is None:
            return
        if self._mp_send("unfeature_player", {"player_id": str(getattr(p, "id", ""))}):
            return
        try:
            out = rs.unfeature_player(self._coach, p, self._team)
            self.result.configure(text=out["text"], text_color=GREEN)
            if self._on_done:
                self._on_done()
        except Exception:
            pass

    def _give_advice(self, key):
        from ctk_theme import GREEN, RED
        if self._mp_send("advise_coach", {"advice_type": key}):
            return
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


class LineControlPopup(InGamePopup):
    """Discuss (amicable) vs seize (nuclear) the lineup pen."""

    def __init__(self, parent_win, coach, team, roster, ctx, on_done=None):
        from ctk_theme import init_ctk_theme, secondary_button, heading, BG, TEXT_DIM, GREEN, RED
        init_ctk_theme()
        super().__init__(parent_win)
        self.title("Line Control")
        self.configure(fg_color=BG)
        self.geometry("540x420")
        self.minsize(480, 380)
        self._coach = coach
        self._team = team
        self._roster = roster
        self._ctx = ctx
        self._on_done = on_done
        self._GREEN = GREEN
        self._RED = RED
        self._app = getattr(parent_win, 'app', None) or getattr(parent_win, 'parent', None)

        cname = getattr(coach, 'full_name', 'Coach')
        preview = rs.preview_line_control_discussion(coach, ctx)
        heading(self, text=f"The lineup pen: {cname}").pack(anchor='w', padx=16, pady=(12, 2))
        ctk.CTkLabel(self, text=f"{rs.control_label(coach)}  •  GM trust {getattr(coach, 'gm_trust', 70)}/100",
                     font=('Segoe UI', 11), text_color=TEXT_DIM).pack(anchor='w', padx=16)
        ctk.CTkLabel(self, text=f"Discuss: \"{preview['text']}\"",
                     font=('Segoe UI', 11), wraplength=500, justify='left').pack(
                         anchor='w', padx=16, pady=(10, 4))
        tone_color = GREEN if preview['tone'] in ('welcomes', 'accepts') else RED
        ctk.CTkLabel(self, text=f"Likely response: {preview['tone'].upper()}",
                     font=('Segoe UI', 11, 'bold'), text_color=tone_color).pack(
                         anchor='w', padx=16, pady=(0, 12))

        secondary_button(self, text="Discuss: \"let me try something\"",
                         command=self._discuss).pack(fill='x', padx=16, pady=6)
        secondary_button(self, text="Seize control (nuclear option)",
                         command=self._seize).pack(fill='x', padx=16, pady=6)
        self.result = ctk.CTkLabel(self, text="", font=('Segoe UI', 11),
                                   wraplength=500, justify='left')
        self.result.pack(padx=16, pady=12)

    def _mp_send(self, action, params):
        """Route to the MP host when this machine is a client; True = routed."""
        try:
            client = getattr(self._app, "mp_client", None)
            if client is None:
                return False
            params = dict(params or {})
            params.setdefault("team_id", getattr(self._team, "team_name", ""))
            client.send_action(action, params)
            try:
                from ctk_theme import TEXT_DIM
                self.result.configure(
                    text="Sent to the host -- the room will react after the next sync.",
                    text_color=TEXT_DIM)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _discuss(self):
        if self._mp_send("set_line_control", {"holder": "gm", "approach": "discuss"}):
            return
        try:
            out = rs.set_line_control(self._team, 'gm', self._ctx, self._roster,
                                      coach=self._coach, approach='discuss')
            self.result.configure(text=out['text'], text_color=self._GREEN)
            if self._on_done:
                self._on_done()
        except Exception:
            pass

    def _seize(self):
        if self._mp_send("set_line_control", {"holder": "gm", "approach": "seize"}):
            return
        try:
            out = rs.set_line_control(self._team, 'gm', self._ctx, self._roster,
                                      coach=self._coach, approach='seize')
            self.result.configure(text=out['text'], text_color=self._RED)
            if self._on_done:
                self._on_done()
        except Exception:
            pass


class DeclareRivalPopup(InGamePopup):
    """Name your enemy: declare a team rival or a personal beef with an
    opposing head coach. Declarations never fade until renounced."""

    def __init__(self, parent_win, team, league, on_done=None):
        from ctk_theme import (init_ctk_theme, secondary_button, heading,
                               BG, PANEL, TEXT_DIM, GREEN, RED)
        init_ctk_theme()
        super().__init__(parent_win)
        self.title("Declare Rival")
        self.configure(fg_color=BG)
        self.geometry("540x470")
        self.minsize(480, 440)
        self._team = team
        self._league = league
        self._on_done = on_done
        self._GREEN = GREEN
        self._RED = RED
        # parent_win is the Morale view; its app is the host (or MP client).
        self._app = getattr(parent_win, 'app', None) or getattr(parent_win, 'parent', None)

        heading(self, text="Declare a rival").pack(anchor='w', padx=16, pady=(12, 2))
        ctk.CTkLabel(self,
                     text=("Name your enemy. A declaration sets the heat to 70, "
                           "makes those games genuinely hostile, and never fades "
                           "until you renounce it. The league will hear about it."),
                     font=('Segoe UI', 11), text_color=TEXT_DIM,
                     justify='left', wraplength=500).pack(anchor='w', padx=16, pady=(0, 10))

        self._team_names = sorted(
            getattr(t, 'team_name', '') for t in (getattr(league, 'teams', []) or [])
            if getattr(t, 'team_name', '') and getattr(t, 'team_name', '') != getattr(team, 'team_name', ''))
        # coach display -> team name
        self._coach_map = {}
        for t in (getattr(league, 'teams', []) or []):
            tn = getattr(t, 'team_name', '')
            if not tn or tn == getattr(team, 'team_name', ''):
                continue
            for stf in getattr(t, 'staff', []) or []:
                if 'Head Coach' in str(getattr(getattr(stf, 'role', None), 'value', '')):
                    disp = f"{getattr(stf, 'full_name', 'Coach')} ({tn})"
                    self._coach_map[disp] = tn
                    break

        # -- team rival --
        tframe = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        tframe.pack(fill='x', padx=16, pady=(0, 10))
        ctk.CTkLabel(tframe, text="Team rival -- circle those dates:",
                     font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 2))
        self._team_pick = ctk.CTkOptionMenu(tframe,
                                            values=self._team_names or ["(no other teams)"])
        self._team_pick.pack(fill='x', padx=10, pady=4)
        secondary_button(tframe, text="Declare team rival",
                         command=lambda: self._declare("team")).pack(
                             anchor='w', padx=10, pady=(0, 8))

        # -- personal rival --
        pframe = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        pframe.pack(fill='x', padx=16, pady=(0, 10))
        ctk.CTkLabel(pframe, text="Personal rival -- an opposing head coach:",
                     font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 2))
        self._coach_pick = ctk.CTkOptionMenu(pframe,
                                             values=sorted(self._coach_map) or ["(no coaches)"])
        self._coach_pick.pack(fill='x', padx=10, pady=4)
        secondary_button(pframe, text="Declare personal rival",
                         command=lambda: self._declare("coach")).pack(
                             anchor='w', padx=10, pady=(0, 8))

        # -- renounce --
        rframe = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        rframe.pack(fill='x', padx=16, pady=(0, 10))
        ctk.CTkLabel(rframe, text="Live declarations -- take one back:",
                     font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 2))
        self._renounce_frame = rframe
        self._rebuild_renounce_list()

        self.result = ctk.CTkLabel(self, text="", font=('Segoe UI', 11),
                                   wraplength=500, justify='left')
        self.result.pack(padx=16, pady=(0, 12))

    # ------------------------------------------------------------------
    def _mp_send(self, action, params):
        """Route to the MP host when this machine is a client; True = routed."""
        try:
            client = getattr(self._app, "mp_client", None)
            if client is None:
                return False
            params = dict(params or {})
            params.setdefault("team_id", getattr(self._team, "team_name", ""))
            client.send_action(action, params)
            try:
                from ctk_theme import TEXT_DIM
                self.result.configure(
                    text="Sent to the host -- the league will hear about it after the next sync.",
                    text_color=TEXT_DIM)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _find_team(self, name):
        for t in (getattr(self._league, 'teams', []) or []):
            if getattr(t, 'team_name', '') == name:
                return t
        return None

    def _declare(self, kind):
        if kind == "team":
            target_team_name = self._team_pick.get()
        else:
            target_team_name = self._coach_map.get(self._coach_pick.get(), "")
        if not target_team_name:
            return
        if self._mp_send("declare_rivalry",
                         {"target_team": target_team_name, "target_kind": kind}):
            return
        try:
            target_team = self._find_team(target_team_name)
            rec, label = rs.declare_rivalry_for_gm(self._league, self._team,
                                                   target_team, kind)
            import headlines as hl
            hl.announce_rivalry_declaration(
                self._app, getattr(self._team, 'team_name', '?'),
                target_team_name, label, kind)
            self.result.configure(
                text=f"Declared: {label} (heat {rec['intensity']:.0f}). "
                     f"Those games just got personal.",
                text_color=self._GREEN)
            self._rebuild_renounce_list()
            if self._on_done:
                self._on_done()
        except ValueError as e:
            self.result.configure(text=str(e), text_color=self._RED)
        except Exception:
            pass

    def _rebuild_renounce_list(self):
        from ctk_theme import secondary_button
        for w in list(self._renounce_frame.winfo_children())[1:]:
            try:
                w.destroy()
            except Exception:
                pass
        try:
            rivalries = getattr(self._league, 'rivalries', []) or []
            declared = rs.declared_rivalries_for(rivalries, self._team)
        except Exception:
            declared = []
        if not declared:
            ctk.CTkLabel(self._renounce_frame, text="None. Pick a fight above.",
                         font=('Segoe UI', 11)).pack(anchor='w', padx=10, pady=(0, 8))
            return
        my_keys = {("team", getattr(self._team, 'team_name', '')),
                   ("gm", getattr(self._team, 'team_name', ''))}
        for r in declared:
            other = r['b_name'] if r['a'] in my_keys else r['a_name']
            kind = "team" if r['kind'] == "team_team" else "coach"
            # Resolve the target team for renounce.
            target_team_name = None
            if kind == "team":
                target_team_name = r['b_name'] if r['a'] in my_keys else r['a_name']
            else:
                for disp, tn in self._coach_map.items():
                    if disp.rsplit(" (", 1)[0] == other:
                        target_team_name = tn
                        break
            btn = secondary_button(
                self._renounce_frame, text=f"Renounce vs {other}",
                command=lambda k=kind, tn=target_team_name:
                    self._renounce(k, tn))
            btn.pack(anchor='w', padx=10, pady=2)

    def _renounce(self, kind, target_team_name):
        if not target_team_name:
            return
        if self._mp_send("renounce_rivalry",
                         {"target_team": target_team_name, "target_kind": kind}):
            return
        try:
            target_team = self._find_team(target_team_name)
            ok = rs.renounce_rivalry_for_gm(self._league, self._team,
                                            target_team, kind)
            self.result.configure(
                text=("Renounced. The hate cools from here."
                      if ok else "Nothing to renounce."),
                text_color=self._GREEN if ok else self._RED)
            self._rebuild_renounce_list()
            if self._on_done:
                self._on_done()
        except Exception:
            pass
