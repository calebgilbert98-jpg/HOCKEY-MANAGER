"""Player profile hub (CustomTkinter, charcoal/teal).

A full assessment hub for a player — far beyond attributes:
overview & status, season + career numbers, grouped attributes,
contract & development future, health, and scouting context,
with quick actions (Scout, Physio, Trade For).

Opened via app.open_player_profile(player).
"""

import tkinter as tk

import customtkinter as ctk

from ctk_theme import (
    init_ctk_theme, primary_button, heading, body,
    TEAL, BG, PANEL, CARD, BORDER,
    TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
)


def _ovr100(player):
    try:
        from game_classes import to_100_scale
        return int(to_100_scale(player.overall_rating()))
    except Exception:
        return 0


def _is_goalie(player):
    try:
        return "GOALIE" in str(player.primary_position).upper()
    except Exception:
        return False


def _pos_short(player):
    try:
        return str(player.primary_position).split(".")[-1].replace("_", " ").title()
    except Exception:
        return "?"


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "—"
    if v <= 0:
        return "—"
    return f"${v / 1e6:.2f}M"


class PlayerProfileHub(ctk.CTkToplevel):
    """Tabbed player assessment hub."""

    W, H = 1060, 780

    def __init__(self, parent, player):
        init_ctk_theme()
        super().__init__(parent)
        self.player = player
        self.app = parent
        # Unwrap to the app object if parent is a window
        for _ in range(4):
            if hasattr(self.app, "open_player_profile") or hasattr(self.app, "user_team"):
                break
            nxt = getattr(self.app, "parent", None)
            if nxt is None:
                break
            self.app = nxt

        p = player
        try:
            name = p.full_name
        except Exception:
            name = "Player Profile"
        self.title(f"{name} — Profile")
        self.geometry(f"{self.W}x{self.H}")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        try:
            self.transient(parent)
        except Exception:
            pass

        self._build_header()
        self._build_tabs()
        self._build_actions()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self):
        p = self.player
        hdr = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        hdr.pack(fill="x")

        # Face
        face_box = ctk.CTkFrame(hdr, fg_color="transparent", width=112, height=112)
        face_box.pack(side="left", padx=(18, 6), pady=14)
        face_box.pack_propagate(False)
        photo = None
        try:
            from player_faces import get_face_photo
            photo = get_face_photo(p, size=112)
        except Exception:
            photo = None
        if photo is not None:
            self._face_photo = photo  # keep reference
            lbl = ctk.CTkLabel(face_box, text="", image=photo)
            lbl.pack(expand=True)
        else:
            initials = "?"
            try:
                initials = f"{p.first_name[0]}{p.last_name[0]}".upper()
            except Exception:
                pass
            ctk.CTkLabel(face_box, text=initials,
                         font=("Segoe UI", 34, "bold"),
                         text_color=TEXT).pack(expand=True)

        info = ctk.CTkFrame(hdr, fg_color="transparent")
        info.pack(side="left", fill="y", padx=6, pady=10)

        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(anchor="w")
        try:
            cap = getattr(p, "captaincy", None)
            title_txt = p.full_name + (f"  ({cap})" if cap else "")
        except Exception:
            title_txt = "Unknown Player"
        heading(name_row, title_txt, size=22).pack(side="left")
        try:
            jn = getattr(p, "jersey_number", None)
            if jn:
                body(name_row, f"  #{jn}", dim=True, size=14).pack(side="left")
        except Exception:
            pass

        team_txt = str(getattr(p, "team_name", "") or "")
        if team_txt and team_txt != "Free Agent":
            body(info, team_txt, dim=True, size=12).pack(anchor="w", pady=(2, 6))
        else:
            body(info, "Free Agent", dim=True, size=12).pack(anchor="w", pady=(2, 6))

        # Pills: position / age / OVR / potential
        pills = ctk.CTkFrame(info, fg_color="transparent")
        pills.pack(anchor="w", pady=(0, 6))
        self._pill(pills, _pos_short(p), TEAL).pack(side="left", padx=(0, 6))
        try:
            self._pill(pills, f"Age {p.age}", TEXT_DIM).pack(side="left", padx=(0, 6))
        except Exception:
            pass
        ovr = _ovr100(p)
        self._pill(pills, f"{ovr} OVR", self._ovr_color(ovr)).pack(side="left", padx=(0, 6))
        try:
            pg = str(getattr(p, "potential_grade", "") or "").strip().upper()
            if pg:
                self._pill(pills, f"POT {pg}", GOLD).pack(side="left", padx=(0, 6))
        except Exception:
            pass

        # Status badges
        badges = self._status_badges()
        if badges:
            brow = ctk.CTkFrame(info, fg_color="transparent")
            brow.pack(anchor="w")
            for txt, color in badges:
                self._pill(brow, txt, color).pack(side="left", padx=(0, 6))

    def _pill(self, parent, text, color):
        f = ctk.CTkFrame(parent, fg_color="#23262c", corner_radius=12,
                         border_width=1, border_color=BORDER)
        ctk.CTkLabel(f, text=text, font=("Segoe UI", 11, "bold"),
                     text_color=color).pack(padx=10, pady=3)
        return f

    @staticmethod
    def _ovr_color(ovr):
        if ovr >= 85:
            return GOLD
        if ovr >= 75:
            return GREEN
        if ovr >= 65:
            return TEAL
        return TEXT_DIM

    def _status_badges(self):
        p = self.player
        out = []
        if bool(getattr(p, "is_injured", False)):
            out.append(("INJURED", RED))
        try:
            if int(getattr(p, "current_point_streak", 0) or 0) >= 3:
                out.append((f"Hot — {p.current_point_streak}-game point streak", GREEN))
        except Exception:
            pass
        try:
            if int(getattr(p, "morale", 10) or 10) <= 4:
                out.append(("Low morale", GOLD))
        except Exception:
            pass
        if bool(getattr(p, "transfer_requested", False)):
            out.append(("Transfer requested", RED))
        try:
            if bool(getattr(p, "on_waivers", False)):
                out.append(("On waivers", BLUE))
        except Exception:
            pass
        return out

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def _build_tabs(self):
        tabs = ctk.CTkTabview(self, fg_color="transparent",
                              segmented_button_fg_color=PANEL,
                              segmented_button_selected_color=TEAL,
                              segmented_button_selected_hover_color=TEAL,
                              text_color=TEXT)
        tabs.pack(fill="both", expand=True, padx=14, pady=(10, 4))
        for name in ("Overview", "Season & Career", "Attributes",
                     "Contract & Future", "Health", "Scouting"):
            tabs.add(name)
        self._tab_overview(tabs.tab("Overview"))
        self._tab_season_career(tabs.tab("Season & Career"))
        self._tab_attributes(tabs.tab("Attributes"))
        self._tab_contract_future(tabs.tab("Contract & Future"))
        self._tab_health(tabs.tab("Health"))
        self._tab_scouting(tabs.tab("Scouting"))

    def _scroll(self, tab):
        sf = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        sf.pack(fill="both", expand=True)
        return sf

    def _section(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 10))
        heading(card, title, size=14).pack(anchor="w", padx=16, pady=(12, 8))
        return card

    def _kv(self, parent, label, value, value_color=None):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=2)
        body(r, label, dim=True, size=12).pack(side="left")
        ctk.CTkLabel(r, text=str(value), font=("Segoe UI", 12, "bold"),
                     text_color=value_color or TEXT).pack(side="right")
        return r

    def _stat_tiles(self, parent, items):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 10))
        for label, value in items:
            tile = ctk.CTkFrame(row, fg_color=PANEL, corner_radius=10)
            tile.pack(side="left", fill="both", expand=True, padx=4)
            ctk.CTkLabel(tile, text=str(value), font=("Segoe UI", 18, "bold"),
                         text_color=TEXT).pack(pady=(10, 0))
            body(tile, label, dim=True, size=10).pack(pady=(0, 10))

    # ------------------------------------------------------------------
    # Overview tab
    # ------------------------------------------------------------------
    def _tab_overview(self, tab):
        p = self.player
        sf = self._scroll(tab)

        # Bio
        bio = self._section(sf, "Bio")
        brow = ctk.CTkFrame(bio, fg_color="transparent")
        brow.pack(fill="x", padx=16, pady=(0, 12))
        left = ctk.CTkFrame(brow, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)
        right = ctk.CTkFrame(brow, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        for label, attr in (("Nationality", "nationality"),
                            ("Born", "birthplace"),
                            ("Birth date", "birth_date"),
                            ("Height", "height"),
                            ("Weight", "weight"),
                            ("Shoots", "handedness")):
            self._kv(left, label, getattr(p, attr, "—") or "—")
        for label, attr in (("Draft", "draft_position"),
                            ("Draft year", "draft_year"),
                            ("Pro debut", "pro_debut"),
                            ("Seasons played", "seasons_played"),
                            ("Rookie", "Yes" if getattr(p, "is_rookie", False) else "No"),
                            ("Teams (career)", "teams_count")):
            self._kv(right, label, getattr(p, attr, "—") or "—")

        # Season at a glance
        glance = self._section(sf, "Season at a Glance")
        s = getattr(p, "stats", None)
        if _is_goalie(p):
            gp = getattr(s, "games_played", 0) if s else 0
            svp = getattr(s, "save_percentage", 0) if s else 0
            items = [
                ("GP", gp),
                ("W", getattr(s, "wins", 0) if s else 0),
                ("SV%", f"{svp:.3f}" if gp else ".000"),
                ("GAA", f"{getattr(s, 'goals_against_avg', 0):.2f}" if s else "0.00"),
                ("SO", getattr(s, "shutouts", 0) if s else 0),
            ]
        else:
            gp = getattr(s, "games_played", 0) if s else 0
            g = getattr(s, "goals", 0) if s else 0
            a = getattr(s, "assists", 0) if s else 0
            items = [
                ("GP", gp),
                ("G", g),
                ("A", a),
                ("PTS", g + a),
                ("+/-", getattr(p, "plus_minus", 0)),
                ("PIM", getattr(s, "penalties_in_minutes", 0) if s else 0),
            ]
        self._stat_tiles(glance, items)

        # Form & role
        form = self._section(sf, "Form, Role & Standing")
        try:
            role = p.get_role()
            role_txt = str(role).split(".")[-1].replace("_", " ").title()
        except Exception:
            role_txt = "—"
        self._kv(form, "Role", role_txt, TEAL)
        self._kv(form, "Squad status", getattr(p, "squad_status", "—") or "—")
        self._kv(form, "Happiness", f"{getattr(p, 'happiness', 70)}/100")
        self._kv(form, "Morale", self._morale_word())
        if not _is_goalie(p):
            self._kv(form, "Point streak", f"{getattr(p, 'current_point_streak', 0)} games")
            self._kv(form, "Goal streak", f"{getattr(p, 'current_goal_streak', 0)} games")
            self._kv(form, "Hat tricks (season)", getattr(p, "hat_tricks_season", 0))
        traits = getattr(p, "traits", []) or []
        if traits:
            trow = ctk.CTkFrame(form, fg_color="transparent")
            trow.pack(fill="x", padx=16, pady=(6, 12))
            body(trow, "Traits", dim=True, size=12).pack(side="left", padx=(0, 8))
            for t in traits[:6]:
                self._pill(trow, str(t).replace("_", " ").title(), BLUE).pack(
                    side="left", padx=(0, 6))
        else:
            ctk.CTkFrame(form, fg_color="transparent", height=12).pack()

    def _morale_word(self):
        try:
            m = int(getattr(self.player, "morale", 10) or 10)
        except Exception:
            return "—"
        if m >= 8:
            return f"{m}/10 — Excellent"
        if m >= 6:
            return f"{m}/10 — Good"
        if m >= 4:
            return f"{m}/10 — Okay"
        return f"{m}/10 — Poor"

    # ------------------------------------------------------------------
    # Season & Career tab
    # ------------------------------------------------------------------
    def _tab_season_career(self, tab):
        p = self.player
        sf = self._scroll(tab)
        s = getattr(p, "stats", None)

        season = self._section(sf, "This Season — Detail")
        if _is_goalie(p):
            rows = [
                ("Games played", getattr(s, "games_played", 0) if s else 0),
                ("Wins / Losses", f"{getattr(s, 'wins', 0)}/{getattr(s, 'losses', 0)}" if s else "0/0"),
                ("Shots against", getattr(s, "shots_against", 0) if s else 0),
                ("Saves", getattr(s, "saves", 0) if s else 0),
                ("Save %", f"{(getattr(s, 'save_percentage', 0) or 0):.3f}"),
                ("Goals against avg", f"{(getattr(s, 'goals_against_avg', 0) or 0):.2f}"),
                ("Shutouts", getattr(s, "shutouts", 0) if s else 0),
            ]
        else:
            gp = getattr(s, "games_played", 0) if s else 0
            g = getattr(s, "goals", 0) if s else 0
            a = getattr(s, "assists", 0) if s else 0
            rows = [
                ("Games played", gp),
                ("Goals", g),
                ("Assists", a),
                ("Points", g + a),
                ("Points per game", f"{(g + a) / gp:.2f}" if gp else "0.00"),
                ("Plus/minus", getattr(p, "plus_minus", 0)),
                ("Penalty minutes", getattr(s, "penalties_in_minutes", 0) if s else 0),
                ("Shots", getattr(s, "shots", 0) if s else 0),
                ("Shooting %", f"{100 * g / max(getattr(s, 'shots', 0) or 1, 1):.1f}%" if s else "—"),
                ("Avg. time on ice", getattr(p, "avg_toi", "—") or "—"),
            ]
        for label, value in rows:
            self._kv(season, label, value)
        ctk.CTkFrame(season, fg_color="transparent", height=10).pack()

        career = self._section(sf, "Career Totals")
        if _is_goalie(p):
            crows = [
                ("Games", getattr(p, "career_games_goalie", 0)),
                ("Wins / Losses", f"{getattr(p, 'career_wins', 0)}/{getattr(p, 'career_losses', 0)}"),
                ("Shutouts", getattr(p, "career_shutouts", 0)),
                ("Saves", getattr(p, "career_saves", 0)),
            ]
        else:
            crows = [
                ("Games", getattr(p, "career_games", 0)),
                ("Goals", getattr(p, "career_goals", 0)),
                ("Assists", getattr(p, "career_assists", 0)),
                ("Points", getattr(p, "career_points", 0)),
                ("Penalty minutes", getattr(p, "career_penalty_minutes", 0)),
                ("Hat tricks", getattr(p, "hat_tricks_career", 0)),
                ("Longest point streak", f"{getattr(p, 'longest_point_streak', 0)} games"),
                ("Longest goal streak", f"{getattr(p, 'longest_goal_streak', 0)} games"),
            ]
        for label, value in crows:
            self._kv(career, label, value)
        ctk.CTkFrame(career, fg_color="transparent", height=10).pack()

    # ------------------------------------------------------------------
    # Attributes tab
    # ------------------------------------------------------------------
    def _tab_attributes(self, tab):
        p = self.player
        sf = self._scroll(tab)
        if _is_goalie(p):
            groups = [
                ("Goaltending", [
                    ("Goaltending", "goaltending"),
                    ("Reflexes", "reflexes"),
                    ("Positioning", "positioning"),
                    ("Rebound Control", "rebound_control"),
                    ("Glove Hand", "glove_hand"),
                    ("Stick Side", "stick_side"),
                    ("Puck Handling", "puck_handling"),
                    ("Breakaways", "breakaway_skill"),
                ]),
                ("Mental", [
                    ("Composure", "composure"),
                    ("Focus", "focus"),
                    ("Confidence", "confidence"),
                    ("Anticipation", "anticipation"),
                    ("Decision Making", "decision_making"),
                ]),
                ("Physical", [
                    ("Durability", "durability"),
                    ("Stamina", "stamina"),
                    ("Agility", "agility"),
                ]),
            ]
        else:
            groups = [
                ("Skating", [
                    ("Speed", "speed"),
                    ("Acceleration", "acceleration"),
                    ("Agility", "agility"),
                    ("Balance", "balance"),
                    ("Endurance", "endurance"),
                    ("Stamina", "stamina"),
                ]),
                ("Offense", [
                    ("Shooting", "shooting"),
                    ("Shot Accuracy", "shooting_accuracy"),
                    ("Shot Power", "shooting_power"),
                    ("Wristshot", "wristshot"),
                    ("Slapshot", "slapshot"),
                    ("One-Timer", "one_timer"),
                    ("Passing", "passing"),
                    ("Pass Accuracy", "passing_accuracy"),
                    ("Pass Creativity", "passing_creativity"),
                    ("Off. Awareness", "offensive_awareness"),
                    ("Deking", "deking"),
                    ("Stickhandling", "stickhandling"),
                    ("Creativity", "creativity"),
                    ("Vision", "vision"),
                ]),
                ("Defense", [
                    ("Def. Awareness", "defensive_awareness"),
                    ("Pokecheck", "pokecheck"),
                    ("Bodycheck", "bodycheck"),
                    ("Shot Blocking", "shot_blocking"),
                    ("Forechecking", "forechecking"),
                    ("First Pass", "first_pass"),
                ]),
                ("Physical", [
                    ("Strength", "strength"),
                    ("Checking", "checking"),
                    ("Aggressiveness", "aggressiveness"),
                    ("Hitting Tendency", "hitting_tendency"),
                    ("Puck Protection", "puck_protection"),
                    ("Durability", "durability"),
                ]),
                ("Mental", [
                    ("Hockey IQ", "hockey_iq"),
                    ("Anticipation", "anticipation"),
                    ("Decision Making", "decision_making"),
                    ("Composure", "composure"),
                    ("Determination", "determination"),
                    ("Work Ethic", "work_ethic"),
                    ("Teamwork", "teamwork"),
                    ("Leadership", "leadership"),
                    ("Consistency", "consistency"),
                    ("Discipline", "discipline"),
                ]),
            ]
            if "CENTER" in str(getattr(p, "primary_position", "")).upper():
                groups.insert(3, ("Faceoffs", [
                    ("Faceoffs", "faceoffs"),
                    ("Faceoff Wins", "faceoff_wins"),
                ]))
        for gname, attrs in groups:
            card = self._section(sf, gname)
            for label, attr in attrs:
                self._attr_bar(card, label, getattr(p, attr, 0))
            ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def _attr_bar(self, parent, name, value):
        from game_classes import to_100_scale
        try:
            disp = int(to_100_scale(value))
        except Exception:
            disp = 50
        disp = max(1, min(100, disp))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=3)
        ctk.CTkLabel(row, text=name, font=("Segoe UI", 11),
                     text_color=TEXT_DIM, width=120, anchor="w").pack(side="left")
        track = ctk.CTkFrame(row, fg_color=PANEL, corner_radius=4, height=10)
        track.pack(side="left", fill="x", expand=True, padx=(8, 8))
        track.pack_propagate(False)
        fill = ctk.CTkFrame(track, fg_color=self._bar_color(disp), corner_radius=4)
        fill.place(relx=0, rely=0, relwidth=disp / 100, relheight=1)
        ctk.CTkLabel(row, text=str(disp), font=("Segoe UI", 11, "bold"),
                     text_color=TEXT, width=34, anchor="e").pack(side="right")

    @staticmethod
    def _bar_color(v):
        if v >= 85:
            return GOLD
        if v >= 72:
            return GREEN
        if v >= 58:
            return TEAL
        return "#5a626e"

    # ------------------------------------------------------------------
    # Contract & Future tab
    # ------------------------------------------------------------------
    def _tab_contract_future(self, tab):
        p = self.player
        sf = self._scroll(tab)
        c = getattr(p, "contract", None)

        con = self._section(sf, "Contract")
        if c is not None:
            self._kv(con, "Salary", _fmt_money(getattr(c, "salary", 0)))
            self._kv(con, "Years remaining", getattr(c, "years_remaining", 0))
            self._kv(con, "Signing bonus", _fmt_money(getattr(c, "signing_bonus", 0)))
            self._kv(con, "Performance bonus", _fmt_money(getattr(c, "performance_bonus", 0)))
            self._kv(con, "No-trade clause", "Yes" if getattr(c, "no_trade_clause", False) else "No")
        else:
            body(con, "No contract on file.", dim=True).pack(padx=16, pady=(0, 12))
        ctk.CTkFrame(con, fg_color="transparent", height=10).pack()

        fut = self._section(sf, "Development Outlook")
        try:
            pg = str(getattr(p, "potential_grade", "") or "").strip().upper() or "—"
        except Exception:
            pg = "—"
        self._kv(fut, "Potential grade", pg, GOLD)
        try:
            from game_classes import to_100_scale
            ceil = int(to_100_scale(p._potential_cap()))
            self._kv(fut, "Potential ceiling", f"{ceil} OVR")
        except Exception:
            pass
        self._kv(fut, "Age", getattr(p, "age", "—"))
        self._kv(fut, "Peak rating (internal)", getattr(p, "peak_rating", "—"))
        self._kv(fut, "Coachability", self._word(getattr(p, "coachability", 30)))
        self._kv(fut, "Work ethic", self._word(getattr(p, "work_ethic", 30)))
        self._kv(fut, "Adaptability", self._word(getattr(p, "adaptability", 30)))
        note = self._dev_note()
        if note:
            body(fut, note, dim=True, size=12).pack(anchor="w", padx=16, pady=(8, 12))
        else:
            ctk.CTkFrame(fut, fg_color="transparent", height=10).pack()

    def _word(self, v):
        try:
            v = float(v)
        except Exception:
            return "—"
        if v >= 40:
            return "Excellent"
        if v >= 34:
            return "Good"
        if v >= 27:
            return "Average"
        return "Below average"

    def _dev_note(self):
        p = self.player
        try:
            age = int(getattr(p, "age", 27))
            pg = str(getattr(p, "potential_grade", "") or "").strip().upper()
        except Exception:
            return ""
        if age <= 23 and pg in ("A", "B"):
            return "Young with top-end potential — development minutes now will pay off for years."
        if age <= 23:
            return "Still developing — regular ice time is the priority."
        if age >= 33:
            return "Veteran — expect gradual decline; value is in leadership and reliability."
        if age >= 29:
            return "In his prime years — this is the window to contend with him."
        return "Established — what you see is close to what you get."

    # ------------------------------------------------------------------
    # Health tab
    # ------------------------------------------------------------------
    def _tab_health(self, tab):
        p = self.player
        sf = self._scroll(tab)
        h = self._section(sf, "Medical")
        injured = bool(getattr(p, "is_injured", False))
        self._kv(h, "Status", "INJURED" if injured else "Fit to play",
                 RED if injured else GREEN)
        self._kv(h, "Injury", str(getattr(p, "injury_type", "None") or "None"))
        self._kv(h, "Est. games out",
                 str(getattr(p, "games_remaining_injured", 0) or 0) if injured else "—")
        self._kv(h, "Last injury", str(getattr(p, "last_injury", "None") or "None"))
        self._kv(h, "Career games missed", getattr(p, "career_games_missed", 0))
        self._kv(h, "Days missed (season)", getattr(p, "days_missed", 0))
        self._kv(h, "Durability", self._word(getattr(p, "durability", 30)))
        self._kv(h, "Injury proneness",
                 self._word(100 - (getattr(p, "injury_proneness", 50) or 0)))
        self._kv(h, "Stamina", self._word(getattr(p, "stamina", 30)))
        ctk.CTkFrame(h, fg_color="transparent", height=10).pack()

    # ------------------------------------------------------------------
    # Scouting tab
    # ------------------------------------------------------------------
    def _tab_scouting(self, tab):
        p = self.player
        sf = self._scroll(tab)
        report = None
        try:
            app = self.app
            team = getattr(app, "user_team", None)
            reports = getattr(team, "scouting_reports", {}) if team else {}
            report = reports.get(getattr(p, "id", None))
        except Exception:
            report = None

        card = self._section(sf, "Scouting Report")
        if report is None:
            body(card, "No scouting report on file for this player.",
                 dim=True, size=12).pack(anchor="w", padx=16, pady=(0, 8))
            body(card, "Assign a scout to build a report over the coming days — "
                       "accuracy improves with each viewing.",
                 dim=True, size=12).pack(anchor="w", padx=16, pady=(0, 12))
            primary_button(card, text="Assign Scout",
                           command=self._action_scout).pack(anchor="w", padx=16, pady=(0, 14))
        else:
            try:
                scout = getattr(report, "scout", None)
                sname = (getattr(scout, "full_name", None)
                         or getattr(scout, "name", None) or "Staff")
            except Exception:
                sname = "Staff"
            self._kv(card, "Scout", sname)
            self._kv(card, "Accuracy", getattr(report, "accuracy", "?"))
            try:
                rel = float(getattr(report, "reliability", 0) or 0)
                self._kv(card, "Reliability", f"{int(rel * 100)}%")
            except Exception:
                pass
            self._kv(card, "Viewings", getattr(report, "viewings", 0))
            self._kv(card, "Region", getattr(report, "region_coverage", "Unknown") or "Unknown")
            self._kv(card, "Competition", getattr(report, "competition_level", "Unknown") or "Unknown")
            strengths = getattr(report, "strengths", []) or []
            weaknesses = getattr(report, "weaknesses", []) or []
            if strengths:
                body(card, "Strengths", dim=True, size=11).pack(anchor="w", padx=16, pady=(8, 2))
                for s in strengths[:6]:
                    body(card, f"•  {s}", size=12).pack(anchor="w", padx=24, pady=1)
            if weaknesses:
                body(card, "Weaknesses", dim=True, size=11).pack(anchor="w", padx=16, pady=(8, 2))
                for w in weaknesses[:6]:
                    body(card, f"•  {w}", size=12).pack(anchor="w", padx=24, pady=1)
            notes = getattr(report, "notes", "") or ""
            if notes:
                body(card, "Notes", dim=True, size=11).pack(anchor="w", padx=16, pady=(8, 2))
                body(card, notes, size=12).pack(anchor="w", padx=24, pady=(0, 4))
            pa = getattr(report, "personality_assessment", "") or ""
            if pa:
                self._kv(card, "Personality", pa)
            proj = getattr(report, "projected_nhl_arrival", "") or ""
            if proj:
                self._kv(card, "Projected arrival", proj)
            ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

    # ------------------------------------------------------------------
    # Action bar
    # ------------------------------------------------------------------
    def _build_actions(self):
        bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(padx=14, pady=10)
        primary_button(inner, text="Scout Player",
                       command=self._action_scout).pack(side="left", padx=(0, 8))
        ctk.CTkButton(inner, text="Physio Report", width=130,
                      fg_color="#23262c", hover_color="#2c313a",
                      text_color=TEXT,
                      command=self._action_physio).pack(side="left", padx=(0, 8))
        ctk.CTkButton(inner, text="Trade For...", width=130,
                      fg_color="#23262c", hover_color="#2c313a",
                      text_color=TEXT,
                      command=self._action_trade).pack(side="left", padx=(0, 8))
        ctk.CTkButton(inner, text="Close", width=100,
                      fg_color="transparent", hover_color="#2c313a",
                      text_color=TEXT_DIM,
                      command=self.destroy).pack(side="right")

    def _menu(self):
        from player_context_menu import PlayerContextMenu
        return PlayerContextMenu(self.app)

    def _action_scout(self):
        try:
            self._menu()._scout_player(self.player)
        except Exception as e:
            print(f"Scout action failed: {e}")

    def _action_physio(self):
        try:
            self._menu()._physio_report(self.player)
        except Exception as e:
            print(f"Physio action failed: {e}")

    def _action_trade(self):
        try:
            from windows import TradeWindow
            team_name = getattr(self.player, "team_name", "") or ""
            app = self.app
            user_team = getattr(app, "user_team", None)
            if user_team is not None and team_name == getattr(user_team, "team_name", ""):
                return
            win = TradeWindow(app)
            try:
                if team_name and hasattr(win, "partner_combo"):
                    win.partner_combo.set(team_name)
                    win.update_trade_partner_roster()
            except Exception as e:
                print(f"Trade partner preset failed: {e}")
        except Exception as e:
            print(f"Trade action failed: {e}")


# Backwards-compatible alias: main.py imports PlayerProfile from here.
PlayerProfile = PlayerProfileHub
