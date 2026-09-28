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
        """Create the profile UI."""
        # Scrollable main
        canvas = tk.Canvas(self, bg=AppColors.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        main = tk.Frame(canvas, bg=AppColors.BG)

        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Content
        content = tk.Frame(main, bg=AppColors.BG)
        content.pack(fill="both", expand=True, padx=24, pady=24)

        self._create_header(content)
        self._create_stats(content)
        self._create_attributes(content)
        self._create_personality(content)
        self._create_readiness(content)

    def _create_header(self, parent):
        """Player header: avatar, name, pills, team + contract strip."""
        header = tk.Frame(parent, bg=AppColors.BG)
        header.pack(fill="x", pady=(0, 24))

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

    def _create_personality(self, parent):
        """Personality & Dressing Room: FM24-style personality panel fed by
        the reputation/social systems -- pills, morale bars, relationships."""
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
        tk.Label(content, text="Personality & Dressing Room",
                 font=AppFonts.H2, fg=AppColors.TEXT_PRIMARY,
                 bg=card.card_bg).pack(anchor="w", pady=(0, 12))

        try:
            att = rs.describe_attitude(p)
            ff = rs.fan_favourite_score(p, team)
            tier = "-"
            if roster:
                tiers = rs.team_hierarchy(roster)
                for tname, ps in tiers.items():
                    if p in ps:
                        tier = tname
                        break

            # Pills row
            pills = tk.Frame(content, bg=card.card_bg)
            pills.pack(anchor="w", pady=(0, 10))
            att_colors = {
                "Volatile": AppColors.DANGER, "Fiery": AppColors.WARNING,
                "Emotional": AppColors.WARNING, "Even-keeled": AppColors.SUCCESS,
                "Model professional": AppColors.INFO,
            }
            PillBadge(pills, text=att,
                      bg=AppColors.BG_ELEVATED,
                      fg=att_colors.get(att, AppColors.TEXT_SECONDARY)
                      ).pack(side="left", padx=(0, 8))
            PillBadge(pills, text=f"Fans: {ff['tier']}",
                      bg=AppColors.BG_ELEVATED,
                      fg=AppColors.TEXT_SECONDARY).pack(side="left", padx=(0, 8))
            if tier != "-":
                PillBadge(pills, text=f"Room: {tier}",
                          bg=AppColors.BG_ELEVATED,
                          fg=AppColors.TEXT_SECONDARY).pack(side="left", padx=(0, 8))
            # Coach fit badge
            coach = self._head_coach_of(team) if team else None
            if coach is not None:
                try:
                    resp = rs.player_coach_response(p, coach)
                    label = resp.get("response", "Neutral") if isinstance(resp, dict) else str(resp)
                    PillBadge(pills, text=f"Coach: {label}",
                              bg=AppColors.BG_ELEVATED,
                              fg=AppColors.TEXT_SECONDARY).pack(side="left", padx=(0, 8))
                except Exception:
                    pass
            # Trade-request risk pill (only when notable)
            try:
                risk = rs.trade_request_risk(p)
                if risk >= 0.5:
                    PillBadge(pills, text="Trade risk: HIGH",
                              bg=AppColors.BG_ELEVATED,
                              fg=AppColors.DANGER).pack(side="left", padx=(0, 8))
                elif risk >= 0.3:
                    PillBadge(pills, text="Trade risk: elevated",
                              bg=AppColors.BG_ELEVATED,
                              fg=AppColors.WARNING).pack(side="left", padx=(0, 8))
            except Exception:
                pass

            # Morale / happiness bars + reputation line
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
                tk.Label(content, text="Why fans care: " + "; ".join(ff["reasons"][:2]),
                         font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                         bg=card.card_bg, wraplength=850,
                         justify="left").pack(anchor="w", pady=2)

            # Relationships
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
            for _cid, story in list(getattr(p, "coach_bonds", None) or {}.items())[:3]:
                tk.Label(content, text="Forged bond  " + story,
                         font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY,
                         bg=card.card_bg, wraplength=850,
                         justify="left").pack(anchor="w", pady=2)
        except Exception as e:
            tk.Label(content, text=f"Dynamics unavailable ({e})",
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
