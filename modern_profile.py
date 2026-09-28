# modern_profile.py
# modern player profile -- FM24-style.
# Clean, modern, no white text boxes.
#
# Layout (FM24-inspired):
# - Header: avatar, name, position/age/OVR pills, team + contract strip
# - Season Stats: key metrics in cards
# - Attributes: FM24-style Technical / Mental / Physical columns with bars
# - Personality & Dressing Room: attitude/morale pills, reputation,
#   fan standing, room tier, coach fit, relationships
# - NHL Readiness: talent grade + situational adjustments

import tkinter as tk
from popup_system import InGamePopup
from tkinter import ttk
from modern_ui import (
    AppColors, AppFonts, AppCard, PillBadge, AppButton
)

# FM24-style attribute groups: (display label, Player field name)
SKATER_TECHNICAL = [
    ("Shooting", "shooting"),
    ("Shot Accuracy", "shooting_accuracy"),
    ("Shot Power", "shooting_power"),
    ("Passing", "passing"),
    ("Pass Accuracy", "passing_accuracy"),
    ("Puck Handling", "puck_handling"),
    ("Faceoffs", "faceoffs"),
    ("Pokecheck", "pokecheck"),
]
SKATER_MENTAL = [
    ("Vision", "vision"),
    ("Creativity", "creativity"),
    ("Anticipation", "anticipation"),
    ("Decisions", "decision_making"),
    ("Off. Awareness", "off_the_puck"),
    ("Determination", "determination"),
    ("Teamwork", "teamwork"),
    ("Discipline", "discipline"),
    ("Flair", "flair"),
    ("Consistency", "consistency"),
    ("Big Games", "important_matches"),
    ("Work Ethic", "work_ethic"),
    ("Coachability", "coachability"),
    ("Adaptability", "adaptability"),
]
SKATER_PHYSICAL = [
    ("Skating", "skating"),
    ("Speed", "speed"),
    ("Acceleration", "acceleration"),
    ("Agility", "agility"),
    ("Balance", "balance"),
    ("Strength", "strength"),
    ("Stamina", "stamina"),
    ("Aggression", "aggressiveness"),
    ("Checking", "checking"),
    ("Bodycheck", "bodycheck"),
]
GOALIE_TECHNICAL = [
    ("Positioning", "positioning"),
    ("Reflexes", "reflexes"),
    ("Glove Hand", "glove_hand"),
    ("Rebound Ctrl", "rebound_control"),
    ("Puck Handling", "puck_handling"),
    ("Passing", "passing"),
]
GOALIE_MENTAL = [
    ("Anticipation", "anticipation"),
    ("Decisions", "decision_making"),
    ("Determination", "determination"),
    ("Teamwork", "teamwork"),
    ("Discipline", "discipline"),
    ("Consistency", "consistency"),
    ("Big Games", "important_matches"),
    ("Work Ethic", "work_ethic"),
    ("Adaptability", "adaptability"),
]
GOALIE_PHYSICAL = [
    ("Skating", "skating"),
    ("Speed", "speed"),
    ("Agility", "agility"),
    ("Balance", "balance"),
    ("Strength", "strength"),
    ("Stamina", "stamina"),
    ("Aggression", "aggressiveness"),
]


class PlayerProfile(InGamePopup):
    """Modern player profile (FM24-style)."""

    def __init__(self, parent, player, **kwargs):
        super().__init__(parent, **kwargs)
        self.player = player
        self.parent_app = parent

        # Window setup
        try:
            name = f"{player.first_name} {player.last_name}"
        except:
            name = "Player Profile"

        self.title(f"{name} - Profile")
        self.geometry("980x760")
        self.configure(bg=AppColors.BG)

        self._create_ui()

    # -- helpers ---------------------------------------------------------
    def _find_team(self):
        """Return the Team object carrying this player, or None."""
        p = self.player
        league = getattr(getattr(self, "parent_app", None), "league", None)
        try:
            for t in (getattr(league, "teams", []) or []):
                if p in (getattr(t, "roster", []) or []):
                    return t
        except Exception:
            pass
        return None

    def _head_coach_of(self, team):
        try:
            for s in (getattr(team, "staff", []) or []):
                if str(getattr(getattr(s, "role", None), "name", "")) == "HEAD_COACH":
                    return s
        except Exception:
            pass
        return None

    # -- layout ----------------------------------------------------------
    def _create_ui(self):
        """Create the profile UI: fixed header, FM24-style tab strip, and
        one scrollable host whose pages swap under the tabs."""
        outer = tk.Frame(self, bg=AppColors.BG)
        outer.pack(fill="both", expand=True)

        self._create_header(outer)

        # FM24-style tab strip
        tab_defs = [
            ("Overview", self._page_overview),
            ("Analytics", self._page_analytics),
            ("Personality", self._page_personality),
            ("Scout Report", self._page_scout),
            ("Dynamics", self._page_dynamics),
        ]
        self._tab_buttons = {}
        self._tab_pages = {}
        tabbar = tk.Frame(outer, bg=AppColors.BG)
        tabbar.pack(fill="x", padx=24)
        for name, _builder in tab_defs:
            holder = tk.Frame(tabbar, bg=AppColors.BG, cursor="hand2")
            holder.pack(side="left", padx=(0, 4))
            lbl = tk.Label(holder, text=name, font=AppFonts.SMALL_BOLD,
                           fg=AppColors.TEXT_SECONDARY, bg=AppColors.BG,
                           padx=12, pady=6)
            lbl.pack()
            underline = tk.Frame(holder, bg=AppColors.BG, height=2)
            underline.pack(fill="x")
            for w in (holder, lbl):
                w.bind("<Button-1>", lambda e, n=name: self._switch_tab(n))
            self._tab_buttons[name] = (lbl, underline)

        # Scrollable page host (a single scroll region; pages swap inside)
        canvas = tk.Canvas(outer, bg=AppColors.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical",
                                  command=canvas.yview)
        main = tk.Frame(canvas, bg=AppColors.BG)

        main.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=main, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content = tk.Frame(main, bg=AppColors.BG)
        content.pack(fill="both", expand=True, padx=24, pady=16)

        for name, builder in tab_defs:
            page = tk.Frame(content, bg=AppColors.BG)
            builder(page)
            self._tab_pages[name] = page

        self._switch_tab("Overview")

    def _switch_tab(self, name):
        """Show one tab page and restyle the strip."""
        for tname, page in self._tab_pages.items():
            if tname == name:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        for tname, (lbl, underline) in self._tab_buttons.items():
            active = tname == name
            lbl.configure(fg=AppColors.TEXT_PRIMARY if active
                          else AppColors.TEXT_SECONDARY)
            underline.configure(bg=AppColors.ACCENT if active
                                else AppColors.BG)

    # -- tab pages -------------------------------------------------------
    def _page_overview(self, parent):
        self._create_stats(parent)
        self._create_attributes(parent)

    def _page_personality(self, parent):
        self._create_personality_traits(parent)

    def _page_scout(self, parent):
        self._create_readiness(parent)
        self._create_scout_notes(parent)

    def _page_analytics(self, parent):
        self._create_deep_dive(parent)
        self._page_scout_insights(parent)

    def _page_dynamics(self, parent):
        self._create_dynamics(parent)

    def _create_header(self, parent):
        """Player header: avatar, name, pills, team + contract strip."""
        header = tk.Frame(parent, bg=AppColors.BG)
        header.pack(fill="x", pady=(0, 8))

        # Large avatar
        size = 96
        avatar = tk.Canvas(header, width=size, height=size,
                          bg=AppColors.BG, highlightthickness=0)
        avatar.pack(side="left")

        # Position color
        try:
            pos = str(self.player.primary_position).upper()
            if 'GOALIE' in pos:
                color = AppColors.INFO
            elif 'DEFENSE' in pos:
                color = AppColors.WARNING
            else:
                color = AppColors.ACCENT
        except:
            color = AppColors.ACCENT

        avatar.create_oval(2, 2, size-2, size-2, fill=color, outline="")

        try:
            initials = f"{self.player.first_name[0]}{self.player.last_name[0]}".upper()
        except:
            initials = "?"
        avatar.create_text(size//2, size//2, text=initials,
                          font=("Segoe UI", 28, "bold"), fill="white")

        # Info
        info = tk.Frame(header, bg=AppColors.BG)
        info.pack(side="left", padx=20, fill="y")

        try:
            name = f"{self.player.first_name} {self.player.last_name}"
        except:
            name = "Unknown Player"

        name_label = tk.Label(info, text=name,
                             font=("Segoe UI", 24, "bold"),
                             fg=AppColors.TEXT_PRIMARY,
                             bg=AppColors.BG)
        name_label.pack(anchor="w")

        # Pills row
        pills = tk.Frame(info, bg=AppColors.BG)
        pills.pack(anchor="w", pady=(12, 0))

        try:
            pos_str = str(self.player.primary_position).split('.')[-1]
            pos_pill = PillBadge(pills, text=pos_str,
                                 bg=AppColors.ACCENT_BG,
                                 fg=AppColors.ACCENT)
            pos_pill.pack(side="left", padx=(0, 8))

            age = getattr(self.player, 'age', '?')
            age_pill = PillBadge(pills, text=f"Age {age}",
                                 bg=AppColors.BG_ELEVATED,
                                 fg=AppColors.TEXT_SECONDARY)
            age_pill.pack(side="left", padx=(0, 8))

            # Overall (1-100 display scale)
            try:
                from game_classes import to_100_scale
                overall = to_100_scale(self.player.overall_rating())
            except Exception:
                overall = '?'
            ovr_pill = PillBadge(pills, text=f"{overall} OVR",
                                 bg=AppColors.BG_ELEVATED,
                                 fg=AppColors.TEXT_PRIMARY)
            ovr_pill.pack(side="left")
        except:
            pass

        # Team + contract strip (FM24 header info)
        try:
            team = self._find_team()
            team_name = getattr(team, "team_name", None) or "Free Agent"
            contract = getattr(self.player, 'contract', None)
            salary = getattr(self.player, 'salary', getattr(contract, 'salary', None))
            years = getattr(self.player, 'contract_years',
                            getattr(contract, 'years_remaining', None))
            bits = [team_name]
            if salary:
                bits.append(f"${salary:,} / yr")
            if years is not None:
                bits.append(f"{years} yr{'s' if years != 1 else ''} left")
            strip = tk.Label(info, text="   •   ".join(bits),
                             font=AppFonts.SMALL,
                             fg=AppColors.TEXT_SECONDARY,
                             bg=AppColors.BG)
            strip.pack(anchor="w", pady=(8, 0))
        except Exception:
            pass

    def _create_stats(self, parent):
        """Season stats in cards."""
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()

        title = tk.Label(content, text="Season Stats",
                        font=AppFonts.H2,
                        fg=AppColors.TEXT_PRIMARY,
                        bg=card.card_bg)
        title.pack(anchor="w", pady=(0, 16))

        # Stats grid
        stats_frame = tk.Frame(content, bg=card.card_bg)
        stats_frame.pack(fill="x")

        try:
            is_goalie = 'GOALIE' in str(self.player.primary_position).upper()
            stats = self.player.stats

            if is_goalie:
                items = [
                    ("GP", getattr(stats, 'games_played', 0)),
                    ("W", getattr(stats, 'wins', 0)),
                    ("SV%", f"{getattr(stats, 'save_percentage', 0):.3f}"),
                    ("GAA", f"{getattr(stats, 'goals_against_average', 0):.2f}"),
                ]
            else:
                items = [
                    ("GP", getattr(stats, 'games_played', 0)),
                    ("G", getattr(stats, 'goals', 0)),
                    ("A", getattr(stats, 'assists', 0)),
                    ("PTS", getattr(stats, 'points', 0)),
                ]
        except:
            items = [("GP", 0), ("G", 0), ("A", 0), ("PTS", 0)]

        for label, value in items:
            col = tk.Frame(stats_frame, bg=card.card_bg)
            col.pack(side="left", fill="both", expand=True)

            val_label = tk.Label(col, text=str(value),
                                font=AppFonts.STAT_SMALL,
                                fg=AppColors.TEXT_PRIMARY,
                                bg=card.card_bg)
            val_label.pack()

            lbl = tk.Label(col, text=label,
                          font=AppFonts.CAPTION,
                          fg=AppColors.TEXT_SECONDARY,
                          bg=card.card_bg)
            lbl.pack()

    def _create_attributes(self, parent):
        """FM24-style grouped attributes: Technical / Mental / Physical."""
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()

        title = tk.Label(content, text="Attributes",
                        font=AppFonts.H2,
                        fg=AppColors.TEXT_PRIMARY,
                        bg=card.card_bg)
        title.pack(anchor="w", pady=(0, 16))

        try:
            is_goalie = 'GOALIE' in str(self.player.primary_position).upper()
        except:
            is_goalie = False
        groups = (
            [("Technical", GOALIE_TECHNICAL if is_goalie else SKATER_TECHNICAL),
             ("Mental", GOALIE_MENTAL if is_goalie else SKATER_MENTAL),
             ("Physical", GOALIE_PHYSICAL if is_goalie else SKATER_PHYSICAL)]
        )

        cols = tk.Frame(content, bg=card.card_bg)
        cols.pack(fill="x")
        for gi, (gname, attrs) in enumerate(groups):
            col = tk.Frame(cols, bg=card.card_bg)
            col.pack(side="left", fill="both", expand=True,
                     padx=(0 if gi == 0 else 18, 0))
            gh = tk.Label(col, text=gname, font=AppFonts.SMALL_BOLD,
                          fg=AppColors.ACCENT, bg=card.card_bg)
            gh.pack(anchor="w", pady=(0, 6))
            for label, field in attrs:
                val = getattr(self.player, field, None)
                if val is None:
                    continue
                self._create_attribute_bar(col, label, val, card.card_bg,
                                           compact=True)

    def _create_personality_traits(self, parent):
        """Personality: character, morale, reputation -- who he is."""
        import reputation_system as rs
        p = self.player
        try:
            rs.ensure_reputation_fields(p)
        except Exception:
            pass
        team = self._find_team()

        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        tk.Label(content, text="Personality",
                 font=AppFonts.H2, fg=AppColors.TEXT_PRIMARY,
                 bg=card.card_bg).pack(anchor="w", pady=(0, 12))
        try:
            att = rs.describe_attitude(p)
            ff = rs.fan_favourite_score(p, team)

            pills = tk.Frame(content, bg=card.card_bg)
            pills.pack(anchor="w", pady=(0, 10))
            att_colors = {
                "Volatile": AppColors.DANGER, "Fiery": AppColors.WARNING,
                "Emotional": AppColors.WARNING,
                "Even-keeled": AppColors.SUCCESS,
                "Model professional": AppColors.INFO,
            }
            PillBadge(pills, text=att,
                      bg=AppColors.BG_ELEVATED,
                      fg=att_colors.get(att, AppColors.TEXT_SECONDARY)
                      ).pack(side="left", padx=(0, 8))
            PillBadge(pills, text=f"Fans: {ff['tier']}",
                      bg=AppColors.BG_ELEVATED,
                      fg=AppColors.TEXT_SECONDARY).pack(side="left", padx=(0, 8))

            bars = tk.Frame(content, bg=card.card_bg)
            bars.pack(fill="x", pady=(0, 6))
            self._create_attribute_bar(bars, "Morale",
                                       getattr(p, "morale", 50), card.card_bg,
                                       compact=True)
            self._create_attribute_bar(bars, "Happiness",
                                       getattr(p, "happiness", 50), card.card_bg,
                                       compact=True)
            rep_line = (f"Reputation  {getattr(p, 'reputation', 0)}/100"
                        f"   •   Leadership  {getattr(p, 'leadership', 0)}/100")
            tk.Label(content, text=rep_line, font=AppFonts.SMALL,
                     fg=AppColors.TEXT_SECONDARY, bg=card.card_bg,
                     justify="left").pack(anchor="w", pady=(4, 2))
            if ff["reasons"]:
                tk.Label(content,
                         text="Why fans care: " + "; ".join(ff["reasons"][:2]),
                         font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                         bg=card.card_bg, wraplength=850,
                         justify="left").pack(anchor="w", pady=2)
        except Exception as e:
            tk.Label(content, text=f"Personality unavailable ({e})",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                     bg=card.card_bg).pack(anchor="w")

    def _create_dynamics(self, parent):
        """Team Dynamics: his place in the room -- hierarchy, coach fit,
        relationships."""
        import reputation_system as rs
        p = self.player
        try:
            rs.ensure_reputation_fields(p)
        except Exception:
            pass
        league = getattr(getattr(self, "parent_app", None), "league", None)
        team = self._find_team()
        roster = list(getattr(team, "roster", []) or []) if team else []

        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        tk.Label(content, text="Team Dynamics",
                 font=AppFonts.H2, fg=AppColors.TEXT_PRIMARY,
                 bg=card.card_bg).pack(anchor="w", pady=(0, 12))
        try:
            tier = "-"
            if roster:
                tiers = rs.team_hierarchy(roster)
                for tname, ps in tiers.items():
                    if p in ps:
                        tier = tname
                        break

            pills = tk.Frame(content, bg=card.card_bg)
            pills.pack(anchor="w", pady=(0, 10))
            if tier != "-":
                PillBadge(pills, text=f"Room: {tier}",
                          bg=AppColors.BG_ELEVATED,
                          fg=AppColors.TEXT_SECONDARY).pack(side="left",
                                                           padx=(0, 8))
            coach = self._head_coach_of(team) if team else None
            if coach is not None:
                try:
                    resp = rs.player_coach_response(p, coach)
                    label = (resp.get("response", "Neutral")
                             if isinstance(resp, dict) else str(resp))
                    PillBadge(pills, text=f"Coach: {label}",
                              bg=AppColors.BG_ELEVATED,
                              fg=AppColors.TEXT_SECONDARY).pack(side="left",
                                                               padx=(0, 8))
                except Exception:
                    pass
            try:
                risk = rs.trade_request_risk(p)
                if risk >= 0.5:
                    PillBadge(pills, text="Trade risk: HIGH",
                              bg=AppColors.BG_ELEVATED,
                              fg=AppColors.DANGER).pack(side="left",
                                                       padx=(0, 8))
                elif risk >= 0.3:
                    PillBadge(pills, text="Trade risk: elevated",
                              bg=AppColors.BG_ELEVATED,
                              fg=AppColors.WARNING).pack(side="left",
                                                        padx=(0, 8))
            except Exception:
                pass

            friends = rs.get_friends(p, roster) if roster else []
            if friends:
                tk.Label(content,
                         text="Close with  " + ", ".join(
                             f"{f['player'].first_name} {f['player'].last_name}"
                             for f in friends),
                         font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                         bg=card.card_bg, wraplength=850,
                         justify="left").pack(anchor="w", pady=2)
            rivals = rs.get_rivals(p, roster, league) if roster else []
            if rivals:
                tk.Label(content,
                         text="Bad blood  " + ", ".join(
                             f"{d['name']} ({d['origin']})" for d in rivals),
                         font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                         bg=card.card_bg, wraplength=850,
                         justify="left").pack(anchor="w", pady=2)
            for _cid, story in list(
                    getattr(p, "coach_bonds", None) or {}.items())[:3]:
                tk.Label(content, text="Forged bond  " + story,
                         font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                         bg=card.card_bg, wraplength=850,
                         justify="left").pack(anchor="w", pady=2)
            if not friends and not rivals:
                tk.Label(content,
                         text="No notable relationships on this roster yet.",
                         font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                         bg=card.card_bg).pack(anchor="w", pady=2)
        except Exception as e:
            tk.Label(content, text=f"Dynamics unavailable ({e})",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                     bg=card.card_bg).pack(anchor="w")


    def _create_deep_dive(self, parent):
        """Analytics: deep-dive advanced metrics -- offense, possession,
        defense, and goaltending -- in the style of NHL analytics sites.

        Shown through the club's analytics department lens: modeled
        metrics carry the department's noise and confidence intervals,
        and the snapshot shows its as-of date (data lag). Observed
        box-score facts are exact. Better departments, sharper picture
        -- never sharper players.
        """
        import advanced_metrics as am
        p = self.player
        try:
            is_goalie = 'GOALIE' in str(p.primary_position).upper()
        except Exception:
            is_goalie = False

        # Department lens: the numbers YOUR club sees. Every viewed
        # player -- own roster or opponent -- is rendered through the
        # user club's analytics department, so hiring a better
        # department is the only way to sharpen this picture.
        lens = None
        try:
            parent_app = getattr(self, "parent_app", None)
            team = getattr(parent_app, "user_team", None) or self._find_team()
            date_str = str(getattr(parent_app, "current_date", ""))
            if team is not None:
                if is_goalie:
                    lens = am.display_goalie_metrics(p, team, date_str)
                else:
                    lens = am.display_skater_metrics(p, team, date_str)
        except Exception:
            lens = None

        def _val(field, fallback):
            if lens is not None and field in lens.values:
                return lens.values[field]
            return fallback

        def _with_ci(field, text, pct100=False):
            # Honest uncertainty: modeled metrics show the department's
            # 90% confidence interval. Observed facts stay exact.
            # pct100: metric is stored 0-100 (CI already in points);
            # otherwise a fraction metric shown as % (CI x100).
            if lens is not None and field in lens.ci:
                ci = lens.ci[field]
                if text.rstrip().endswith("%"):
                    if pct100:
                        return f"{text} ±{ci:.1f} pts"
                    return f"{text} ±{ci * 100:.1f} pts"
                return f"{text} ±{ci:.1f}"
            return text

        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        tk.Label(content, text="Deep Dive — Advanced Analytics",
                 font=AppFonts.H2, fg=AppColors.TEXT_PRIMARY,
                 bg=card.card_bg).pack(anchor="w", pady=(0, 4))
        if lens is not None:
            tk.Label(content,
                     text=f"{lens.tier}  •  models as of {lens.as_of} "
                          f"(rebuilt every {lens.lag_days} day"
                          f"{'s' if lens.lag_days != 1 else ''})",
                     font=AppFonts.SMALL, fg=AppColors.ACCENT,
                     bg=card.card_bg).pack(anchor="w", pady=(0, 4))
        tk.Label(content,
                 text="Estimates, not tracking data: modeled metrics are shown "
                      "with your department's confidence interval (±); observed "
                      "box-score facts are exact. No shot locations are tracked. "
                      "Useful for comparing players and spotting trends -- not measured truth. "
                      "Hover ⓘ on any metric for what it is (and isn't).",
                 font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                 bg=card.card_bg, wraplength=640, justify="left").pack(anchor="w", pady=(0, 12))

        def _section(title, rows):
            tk.Label(content, text=title, font=AppFonts.H3,
                     fg=AppColors.TEXT_PRIMARY, bg=card.card_bg).pack(anchor="w", pady=(10, 4))
            for label, value, tip in rows:
                row = tk.Frame(content, bg=card.card_bg)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=label, font=AppFonts.BODY,
                         fg=AppColors.TEXT_SECONDARY, bg=card.card_bg,
                         width=28, anchor="w").pack(side="left")
                tk.Label(row, text=value, font=AppFonts.BODY_BOLD,
                         fg=AppColors.TEXT_PRIMARY, bg=card.card_bg).pack(side="left")
                if tip:
                    dot = tk.Label(row, text="ⓘ", font=AppFonts.SMALL,
                                   fg=AppColors.ACCENT, bg=card.card_bg, cursor="hand2")
                    dot.pack(side="left", padx=6)
                    dot.bind("<Enter>", lambda e, t=tip: self._show_glossary_tip(e, t))

        try:
            if is_goalie:
                m = am.goalie_advanced(p)
                _section("Goaltending — Above Expected", [
                    ("GSAx", _with_ci("gsax", f"{_val('gsax', m.gsax):+.1f}"), am.GLOSSARY["GSAx"]),
                    ("GSAA", f"{_val('gsaa', m.gsaa):+.1f}", am.GLOSSARY["GSAA"]),
                    ("High-danger SV%", _with_ci("hdsv_pct", f"{_val('hdsv_pct', m.hdsv_pct):.3f}"), am.GLOSSARY["HDSV%"]),
                    ("Quality-start %", _with_ci("qs_pct", f"{_val('qs_pct', m.qs_pct):.1%}"), am.GLOSSARY["QS%"]),
                ])
                _section("Workload", [
                    ("Save %", f"{_val('sv_pct', m.sv_pct):.3f}", None),
                    ("GAA", f"{_val('gaa', m.gaa):.2f}", None),
                    ("Shots against / 60", f"{_val('sa_per60', m.sa_per60):.1f}", None),
                ])
            else:
                m = am.skater_advanced(p)
                _section("Offense — Finishing & Creation", [
                    ("Shooting %", f"{_val('sh_pct', m.sh_pct):.1f}%", am.GLOSSARY["SH%"]),
                    ("Individual xG", _with_ci("ixg", f"{_val('ixg', m.ixg):.1f}"), am.GLOSSARY["ixG"]),
                    ("Goals / 60", f"{_val('g_per60', m.g_per60):.2f}", None),
                    ("Points / 60", f"{_val('p_per60', m.p_per60):.2f}", am.GLOSSARY["P/60"]),
                    ("Game Score", f"{_val('game_score', m.game_score):.1f}", am.GLOSSARY["Game Score"]),
                ])
                _section("Possession — Driving Play", [
                    ("Corsi %", _with_ci("cf_pct", f"{_val('cf_pct', m.cf_pct):.1f}%", True), am.GLOSSARY["CF%"]),
                    ("Fenwick %", _with_ci("ff_pct", f"{_val('ff_pct', m.ff_pct):.1f}%", True), am.GLOSSARY["FF%"]),
                    ("Expected-goal share", _with_ci("xgf_pct", f"{_val('xgf_pct', m.xgf_pct):.1f}%", True), am.GLOSSARY["xGF%"]),
                    ("Offensive-zone starts", _with_ci("oz_pct", f"{_val('oz_pct', m.oz_pct):.1f}%", True), am.GLOSSARY["OZ%"]),
                ])
                _section("Defense & Luck", [
                    ("PDO", _with_ci("pdo", f"{_val('pdo', m.pdo):.3f}"), am.GLOSSARY["PDO"]),
                    ("Hits", str(int(_val("hits", m.hits))), None),
                    ("Blocked shots", str(int(_val("blocks", m.blocks))), None),
                ])
        except Exception as e:
            tk.Label(content, text=f"Analytics unavailable ({e})",
                     font=AppFonts.BODY, fg=AppColors.TEXT_SECONDARY,
                     bg=card.card_bg).pack(anchor="w")


    def _page_scout_insights(self, parent):
        """Active scout insights on this player: open reads, track records,
        and any performance review the player is under.

        Reads show evidence, uncertainty, provenance and the scout
        responsible -- the analyst's puzzle, not an answer key.
        """
        p = self.player
        pid = getattr(p, "id", id(p))
        league = getattr(getattr(self, "parent_app", None), "league", None)
        teams = list(getattr(league, "teams", []) or []) if league else []

        reads = []   # (team_name, scout_name, record, kind, reason, date)
        watches = []  # human-readable review lines
        for t in teams:
            try:
                import analytics_scouting as _as
            except ImportError:
                break
            tname = getattr(t, "team_name", "")
            for entry in (getattr(t, "tip_ledger", None) or {}).values():
                try:
                    if entry.get("player_id") != pid:
                        continue
                    scout = self._find_staff_by_id(t, entry.get("scout_id"))
                    record = _as.scout_record_line(scout) if scout else "no record"
                    reads.append((tname, entry.get("scout_name", "?"), record,
                                  entry.get("kind", ""), entry.get("reason", ""),
                                  entry.get("date", "")))
                except Exception:
                    pass
            for w in (getattr(t, "sell_watch", None) or {}).values():
                try:
                    if w.get("player_id") == pid:
                        watches.append(
                            f"{tname} are reviewing this player after moving him "
                            f"({w.get('gp_since', 0)} GP since the deal). If his "
                            f"production collapses, their scout called the peak.")
                except Exception:
                    pass
            for w in (getattr(t, "steal_watch", None) or {}).values():
                try:
                    if w.get("player_id") == pid:
                        watches.append(
                            f"{tname} are watching this acquisition "
                            f"({w.get('gp_since', 0)} GP since the deal). If he "
                            f"breaks out, their scout called the steal.")
                except Exception:
                    pass

        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        tk.Label(content, text="Scout Insights",
                 font=AppFonts.H2, fg=AppColors.TEXT_PRIMARY,
                 bg=card.card_bg).pack(anchor="w", pady=(0, 4))
        if not reads and not watches:
            tk.Label(content,
                     text="No scout has filed a read on this player yet. "
                          "Pro scouts file reads on the 1st of each month -- "
                          "their track records are graded against what happens next.",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                     bg=card.card_bg, wraplength=640,
                     justify="left").pack(anchor="w")
            return
        for tname, sname, record, kind, reason, date in reads[:6]:
            kind_txt = "buy read" if kind == "buy" else "sell read" if kind == "sell" else "read"
            tk.Label(content,
                     text=f"{sname} ({tname}) — {record}",
                     font=AppFonts.BODY_BOLD, fg=AppColors.TEXT_PRIMARY,
                     bg=card.card_bg, wraplength=640,
                     justify="left").pack(anchor="w", pady=(6, 0))
            detail = f"Filed a {kind_txt} on {date}."
            if reason:
                detail += f" Evidence: {reason}"
            tk.Label(content, text=detail,
                     font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                     bg=card.card_bg, wraplength=640,
                     justify="left").pack(anchor="w")
        for line in watches[:4]:
            tk.Label(content, text="◈ " + line,
                     font=AppFonts.SMALL, fg=AppColors.ACCENT,
                     bg=card.card_bg, wraplength=640,
                     justify="left").pack(anchor="w", pady=(4, 0))

    def _find_staff_by_id(self, team, staff_id):
        """Locate a staffer on a team by id (for track-record display)."""
        if not staff_id:
            return None
        try:
            for s in (getattr(team, "staff", []) or []):
                if getattr(s, "id", None) == staff_id:
                    return s
        except Exception:
            pass
        return None



    def _show_glossary_tip(self, event, text):
        try:
            tip = tk.Toplevel()
            tip.wm_overrideredirect(True)
            tip.geometry(f"+{event.x_root+10}+{event.y_root+10}")
            tk.Label(tip, text=text, wraplength=280, justify="left",
                     background="#ffffe0", relief="solid", borderwidth=1,
                     font=AppFonts.SMALL).pack()
            event.widget.bind("<Leave>", lambda _e: tip.destroy(), add="+")
            tip.after(4000, tip.destroy)
        except Exception:
            pass

    def _create_scout_notes(self, parent):
        """Scout Report: strengths/weaknesses read off the attribute groups,
        plus the potential grade -- the written report behind the bars."""
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        tk.Label(content, text="Scout Report",
                 font=AppFonts.H2, fg=AppColors.TEXT_PRIMARY,
                 bg=card.card_bg).pack(anchor="w", pady=(0, 12))
        try:
            from game_classes import to_100_scale
        except Exception:
            def to_100_scale(v):
                return v
        try:
            is_goalie = 'GOALIE' in str(self.player.primary_position).upper()
        except Exception:
            is_goalie = False
        flat = (GOALIE_TECHNICAL + GOALIE_MENTAL + GOALIE_PHYSICAL
                if is_goalie else
                SKATER_TECHNICAL + SKATER_MENTAL + SKATER_PHYSICAL)
        scored = []
        for label, field in flat:
            val = getattr(self.player, field, None)
            if val is None:
                continue
            try:
                scored.append((label, int(to_100_scale(val))))
            except Exception:
                pass
        try:
            scored.sort(key=lambda t: t[1], reverse=True)
            strengths = [f"{n} ({v})" for n, v in scored[:3]]
            weak = sorted([t for t in scored if t[1] < 60],
                          key=lambda t: t[1])
            weaknesses = [f"{n} ({v})" for n, v in weak[:2]]
            grade = (getattr(self.player, "potential_grade", None)
                     or getattr(self.player, "potential", "?"))
            lines = [f"Potential grade:  {grade}"]
            if strengths:
                lines.append("Best assets:  " + ", ".join(strengths))
            if weaknesses:
                lines.append("Needs work:  " + ", ".join(weaknesses))
            else:
                lines.append("No glaring holes in his game.")
            for ln in lines:
                tk.Label(content, text=ln, font=AppFonts.SMALL,
                         fg=AppColors.TEXT_SECONDARY, bg=card.card_bg,
                         wraplength=850, justify="left"
                         ).pack(anchor="w", pady=2)
        except Exception as e:
            tk.Label(content, text=f"Scout report unavailable ({e})",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                     bg=card.card_bg).pack(anchor="w")

    def _create_readiness(self, parent):
        """NHL readiness: talent grade plus what the moment is doing to it.

        The number on the AHL tab is situational -- this card shows why:
        the base talent read, then every live adjustment (injury opening,
        coach fit, line fit, farm trend, his NHL audition).
        """
        import prospect_development as pd
        p = self.player
        team = getattr(getattr(self, "parent_app", None), "user_team", None)

        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        tk.Label(content, text="NHL Readiness",
                 font=AppFonts.H2, fg=AppColors.TEXT_PRIMARY,
                 bg=card.card_bg).pack(anchor="w", pady=(0, 8))
        try:
            base = pd.callup_readiness(p)
            score, deltas = pd.situational_readiness(p, team)
            lines = [f"Right now  {score:.0f}%   (talent grade {base:.0f}%)"]
            for label, d in deltas:
                sign = "+" if d > 0 else ""
                lines.append(f"  {sign}{d:.0f}   {label}")
            if not deltas:
                lines.append("  No situational adjustments -- straight talent read.")
            for ln in lines:
                tk.Label(content, text=ln, font=AppFonts.SMALL,
                         fg=AppColors.TEXT_SECONDARY, bg=card.card_bg,
                         wraplength=850, justify="left").pack(anchor="w", pady=2)
        except Exception as e:
            tk.Label(content, text=f"Readiness unavailable ({e})",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                     bg=card.card_bg).pack(anchor="w")

    def _create_attribute_bar(self, parent, name, value, bg, compact=False):
        """Create a visual attribute bar."""
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=3 if compact else 6)

        # Name
        name_label = tk.Label(row, text=name,
                             font=AppFonts.SMALL,
                             fg=AppColors.TEXT_SECONDARY,
                             bg=bg, width=14, anchor="w")
        name_label.pack(side="left")

        # Bar background
        bar_bg = tk.Frame(row, bg=AppColors.BG, height=8 if compact else 8)
        bar_bg.pack(side="left", fill="x", expand=True, padx=8 if compact else 12)

        # Convert internal scale to 1-100 display scale.
        # to_100_scale already handles both scales (doubles <55, passes through the rest).
        try:
            from game_classes import to_100_scale
            display_val = int(to_100_scale(value))
        except Exception:
            display_val = 50
        pct = max(0.0, min(1.0, display_val / 100))

        # Bar fill
        bar_fill = tk.Frame(bar_bg, bg=AppColors.ACCENT, height=8)
        bar_fill.place(relx=0, rely=0, relwidth=pct, relheight=1)

        # Value
        val_label = tk.Label(row, text=str(display_val),
                            font=AppFonts.SMALL_BOLD,
                            fg=AppColors.TEXT_PRIMARY,
                            bg=bg, width=4, anchor="e")
        val_label.pack(side="right")
