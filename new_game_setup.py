"""Puck Dynasty — new-game setup wizard.

Two modes:
  * Quick Start — sensible defaults preselected; pick a league + team (or
    Randomize), enter a GM name, hit Start.
  * Custom Setup — database size, league toggles, per-league sim detail,
    fog of war, GM name, and team selection.

Standalone entry point::

    from new_game_setup import open_setup_wizard
    open_setup_wizard(parent_tk, on_start)   # on_start(config_dict)

``on_start`` receives the config dict documented below, then the wizard
closes itself. Nothing is generated here — generation stays in
``database_generator``; use :func:`build_database_config` to turn the
wizard config into a ``DatabaseConfig``.

CONFIG SCHEMA (all keys always present)
--------------------------------------
{
    "mode":          "quick" | "custom",
    "database_size": "small" | "medium" | "large",     # default "medium"
    "leagues":       ["NHL", ...],                     # subset of
                                                      # ["NHL","AHL","ECHL","KHL"],
                                                      # default ["NHL","AHL"]
    "sim_detail":    {"NHL": "full", "AHL": "quick"},  # one entry per active
                                                      # league; values are
                                                      # "full" | "quick" | "scores"
    "fog_of_war":    True,                             # bool, default True
    "gm_name":       str,                              # default "General Manager"
    "user_league":   "NHL",                            # league key of managed team
    "user_team":     "Boston Bruins",                  # team name of managed team
}

DATABASE SIZES (verified by headless generation, NHL+AHL default set)
---------------------------------------------------------------------
  small  -> ~2,500 players   (fastest; low-spec machines)
  medium -> ~6,000 players   (recommended default)
  large  -> ~12,000 players  (slower generation + sim)

Totals scale with the league selection (fewer leagues => fewer players).

SIM DETAIL (per active league)
-----------------------------
  full   — every game simulated event-by-event with complete player stats
           (engine: simulation.GameSim.simulate_game — also powers the
           play-by-play viewer).
  quick  — fast result sim: scores and standings only, no per-player
           events/ratings (engine: GameManager._simulate_game_lightweight).
  scores — final scores with minimal detail. No lighter engine path exists
           yet, so this currently uses the Quick path; a dedicated lighter
           path is a documented follow-up.

FOG OF WAR
----------
  True  — unscouted players show fogged (noisy) ratings, as today.
  False — all ratings shown as true. Stored on the config; the follow-up is
          to have GameManager expose it (e.g. ``gm.fog_of_war``) and consult
          it in scouting display code (scouting_profiles.fogged_value,
          PlayerProfileWindow is_scouted).

WIRING (for whoever connects this to the game start flow — main.py untouched)
-----------------------------------------------------------------------------
  * New-game entry today: ``main.py`` ``__main__`` "direct" branch calls
    ``StartupWindow()`` then ``gm.apply_startup_settings(startup.game_settings)``
    and ``gm.set_user_team(startup.selected_team)``.
  * ``GameManager.apply_startup_settings`` (main.py) reads
    ``settings['database_size']`` -> ``DATABASE_CONFIGURATIONS``. To wire the
    wizard in, add a branch: if the settings dict carries a ``DatabaseConfig``
    (built via ``build_database_config``), use it directly instead of the
    preset lookup. Then::
        gm.startup_settings = config            # gm_name already consumed via
                                                # startup_settings['gm_name']
        gm.set_user_team(config["user_team"])
        gm.fog_of_war = config["fog_of_war"]    # follow-up: consult in UI
        gm.sim_detail = config["sim_detail"]    # follow-up: consult in the
                                                # calendar sim loop
"""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from modern_widgets import (
        RoundedButton, SegmentedControl, DarkEntry,
        style_combobox, apply_dark_form_theme,
    )
    _HAS_MODERN = True
except Exception:  # standalone safety
    _HAS_MODERN = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BG = "#0B0F16"
CONTENT_BG = "#111826"
PANEL_BG = "#141C2A"
TEXT = "#E8ECF1"
MUTED = "#8B94A5"
ACCENT = "#E63946"
FONT = "Segoe UI"

DATABASE_SIZES = {
    "small": {
        "label": "Small",
        "tagline": "~2,500 players \u2022 fastest",
        "desc": "Quick careers and low-spec machines. NHL + AHL generate "
                "about 2,500 players.",
        "total_players": 2000,
        "prospects_per_draft": 60,
    },
    "medium": {
        "label": "Medium",
        "tagline": "~6,000 players \u2022 recommended",
        "desc": "Balanced depth for most players. NHL + AHL generate "
                "about 6,000 players.",
        "total_players": 6000,
        "prospects_per_draft": 200,
    },
    "large": {
        "label": "Large",
        "tagline": "~12,000 players \u2022 slowest",
        "desc": "Deep prospect pools and full farm systems. NHL + AHL "
                "generate about 12,000 players; generation and simming "
                "take noticeably longer.",
        "total_players": 15000,
        "prospects_per_draft": 400,
    },
}

WIZARD_LEAGUES = {
    "NHL":  {"db_name": "National Hockey League", "teams": 32, "country": "North America",
             "level": 1, "detail_default": "full",
             "blurb": "The show. 32 teams, 82-game schedule."},
    "AHL":  {"db_name": "American Hockey League", "teams": 30, "country": "North America",
             "level": 2, "detail_default": "quick",
             "blurb": "Top farm league. Affiliated with NHL clubs."},
    "ECHL": {"db_name": "ECHL", "teams": 26, "country": "North America",
             "level": 3, "detail_default": "scores",
             "blurb": "AA minor hockey. Development depth."},
    "KHL":  {"db_name": "KHL", "teams": 23, "country": "Russia",
             "level": 1, "detail_default": "quick",
             "blurb": "Russia's top league. Separate talent pool."},
}

SIM_DETAILS = {
    "full":   "Full \u2014 event-by-event, full player stats",
    "quick":  "Quick \u2014 scores + standings only",
    "scores": "Scores only \u2014 minimal detail",
}
SIM_DETAIL_KEYS = list(SIM_DETAILS.keys())

DEFAULT_CONFIG = {
    "mode": "quick",
    "database_size": "medium",
    "leagues": ["NHL", "AHL"],
    "sim_detail": {"NHL": "full", "AHL": "quick"},
    "fog_of_war": True,
    "gm_name": "General Manager",
    "user_league": "NHL",
    "user_team": "Boston Bruins",
}


# ---------------------------------------------------------------------------
# Helpers (logic, no GUI)
# ---------------------------------------------------------------------------

def build_database_config(cfg: dict):
    """Turn a wizard config dict into a database_generator.DatabaseConfig.

    Raises KeyError/ValueError on invalid input.
    """
    from database_generator import DatabaseConfig

    size_key = cfg.get("database_size", "medium")
    if size_key not in DATABASE_SIZES:
        raise ValueError(f"unknown database_size: {size_key!r}")
    leagues = cfg.get("leagues") or ["NHL"]
    for key in leagues:
        if key not in WIZARD_LEAGUES:
            raise ValueError(f"unknown league: {key!r}")

    size = DATABASE_SIZES[size_key]
    infos = [{
        "name": WIZARD_LEAGUES[k]["db_name"],
        "level": WIZARD_LEAGUES[k]["level"],
        "teams": WIZARD_LEAGUES[k]["teams"],
        "country": WIZARD_LEAGUES[k]["country"],
    } for k in leagues]

    return DatabaseConfig(
        name=f"{size['label']} Database",
        description=size["desc"],
        total_players=size["total_players"],
        prospects_per_draft=size["prospects_per_draft"],
        leagues_count=len(infos),
        teams_per_league=max(i["teams"] for i in infos),
        depth_factor=1.0,
        veteran_distribution=0.7,
        international_factor=1.0,
        minor_league_depth=2,
        staff_count=12,
        league_infos=infos,
    )


def preview_team_names(league_key: str):
    """Team names selectable before generation.

    NHL/AHL use the real name lists from database_generator. ECHL/KHL names
    are generated at setup time, so only a random pick is offered there.
    """
    from database_generator import NHL_TEAMS, AHL_TEAMS
    if league_key == "NHL":
        return list(NHL_TEAMS)
    if league_key == "AHL":
        return list(AHL_TEAMS)
    return []  # generated at setup; random only


def make_config(mode="quick", database_size="medium", leagues=None,
                sim_detail=None, fog_of_war=True, gm_name="",
                user_league="NHL", user_team=""):
    """Build a validated config dict (schema documented at top of file)."""
    leagues = list(leagues) if leagues else list(DEFAULT_CONFIG["leagues"])
    leagues = [k for k in leagues if k in WIZARD_LEAGUES] or ["NHL"]

    detail = {}
    for k in leagues:
        want = (sim_detail or {}).get(k)
        detail[k] = want if want in SIM_DETAILS else WIZARD_LEAGUES[k]["detail_default"]

    if user_league not in leagues:
        user_league = leagues[0]
    names = preview_team_names(user_league)
    if user_team not in names:
        user_team = names[0] if names else "Random"

    return {
        "mode": mode if mode in ("quick", "custom") else "quick",
        "database_size": database_size if database_size in DATABASE_SIZES else "medium",
        "leagues": leagues,
        "sim_detail": detail,
        "fog_of_war": bool(fog_of_war),
        "gm_name": (gm_name or "").strip() or "General Manager",
        "user_league": user_league,
        "user_team": user_team,
    }

# ---------------------------------------------------------------------------
# Wizard UI
# ---------------------------------------------------------------------------

class NewGameSetupWizard(tk.Toplevel):
    """New-career setup wizard. Calls on_start(config) then closes."""

    def __init__(self, parent, on_start_callback):
        super().__init__(parent)
        self.on_start_callback = on_start_callback
        self.title("Puck Dynasty \u2014 New Career Setup")
        self.geometry("920x790")
        self.configure(bg=BG)
        self.resizable(False, False)
        try:
            self.transient(parent)
        except Exception:
            pass

        # State
        self.mode_var = tk.StringVar(value="quick")
        self.size_var = tk.StringVar(value="medium")
        self.league_vars = {k: tk.BooleanVar(value=(k in ("NHL", "AHL")))
                            for k in WIZARD_LEAGUES}
        self.detail_vars = {k: tk.StringVar(value=WIZARD_LEAGUES[k]["detail_default"])
                            for k in WIZARD_LEAGUES}
        self.fog_var = tk.BooleanVar(value=True)
        self.gm_var = tk.StringVar(value="")
        self.q_league_var = tk.StringVar(value="NHL")
        self.q_team_var = tk.StringVar(value="")
        self.c_league_var = tk.StringVar(value="NHL")
        self.c_team_var = tk.StringVar(value="")
        self._detail_combos = {}
        self._team_combos = {}

        try:
            if _HAS_MODERN:
                apply_dark_form_theme(self)
        except Exception:
            pass

        self._build()
        self._show_mode("quick")
        self._center()

    # -- layout ---------------------------------------------------------
    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(header, text="New Career", font=(FONT, 22, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(header, text="Set up your hockey universe",
                 font=(FONT, 11), bg=BG, fg=MUTED).pack(side="left", padx=(12, 0), pady=(8, 0))

        if _HAS_MODERN:
            seg = SegmentedControl(header, ["Quick Start", "Custom Setup"],
                                   initial=0, accent=ACCENT, bg=BG,
                                   command=self._on_mode_seg)
            seg.pack(side="right")
            self._mode_seg = seg
        else:
            frm = tk.Frame(header, bg=BG)
            frm.pack(side="right")
            tk.Radiobutton(frm, text="Quick Start", variable=self.mode_var,
                           value="quick", command=lambda: self._show_mode("quick"),
                           bg=BG, fg=TEXT, selectcolor=PANEL_BG,
                           activebackground=BG, activeforeground=TEXT).pack(side="left")
            tk.Radiobutton(frm, text="Custom Setup", variable=self.mode_var,
                           value="custom", command=lambda: self._show_mode("custom"),
                           bg=BG, fg=TEXT, selectcolor=PANEL_BG,
                           activebackground=BG, activeforeground=TEXT).pack(side="left")

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=24, pady=6)

        self.quick_frame = tk.Frame(self.body, bg=BG)
        self.custom_frame = tk.Frame(self.body, bg=BG)
        self._build_quick(self.quick_frame)
        self._build_custom(self.custom_frame)

        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=24, pady=(6, 18))
        if _HAS_MODERN:
            RoundedButton(footer, text="Cancel", bg="#2A3346", fg=TEXT,
                          command=self.destroy, padx=18, pady=8).pack(side="right", padx=(8, 0))
            self._start_btn = RoundedButton(footer, text="Start Career \u2192", bg=ACCENT,
                                            fg="white", font=(FONT, 12, "bold"),
                                            command=self._on_start, padx=26, pady=10)
            self._start_btn.pack(side="right")
        else:
            tk.Button(footer, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
            tk.Button(footer, text="Start Career \u2192", bg=ACCENT, fg="white",
                      activebackground=ACCENT, command=self._on_start).pack(side="right")

    def _center(self):
        self.update_idletasks()
        try:
            px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
            pw, ph = self.master.winfo_width(), self.master.winfo_height()
            x, y = px + (pw - 920) // 2, py + (ph - 790) // 2
        except Exception:
            x = y = 60
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _on_mode_seg(self, value):
        self._show_mode("quick" if value == "Quick Start" else "custom")

    def _show_mode(self, mode):
        # SegmentedControl fires its command during construction, before the
        # page frames exist — guard for that.
        self.mode_var.set(mode)
        if not hasattr(self, "quick_frame"):
            return
        self.quick_frame.pack_forget()
        self.custom_frame.pack_forget()
        (self.quick_frame if mode == "quick" else self.custom_frame).pack(fill="both", expand=True)
        # Size the window to the content: quick mode is compact, custom needs
        # the full height for all sections.
        try:
            self.geometry("920x560" if mode == "quick" else "920x790")
            self._center()
        except Exception:
            pass

    # -- shared section widgets ------------------------------------------
    def _section(self, parent, title, subtitle=""):
        """Square panel section (no rounded outer corners)."""
        outer = tk.Frame(parent, bg=PANEL_BG, highlightthickness=1,
                         highlightbackground="#232D42")
        outer.pack(fill="x", pady=8)
        tk.Label(outer, text=title, font=(FONT, 13, "bold"),
                 bg=PANEL_BG, fg=TEXT).pack(anchor="w", padx=16, pady=(12, 0))
        if subtitle:
            tk.Label(outer, text=subtitle, font=(FONT, 10),
                     bg=PANEL_BG, fg=MUTED, wraplength=820,
                     justify="left").pack(anchor="w", padx=16, pady=(2, 4))
        body = tk.Frame(outer, bg=PANEL_BG)
        body.pack(fill="x", padx=16, pady=(4, 14))
        return body

    def _dark_check(self, parent, text, variable, command=None):
        return tk.Checkbutton(parent, text=text, variable=variable,
                              bg=PANEL_BG, fg=TEXT, selectcolor=ACCENT,
                              activebackground=PANEL_BG, activeforeground=TEXT,
                              highlightthickness=0,
                              font=(FONT, 11), anchor="w", command=command)

    def _combo(self, parent, textvariable, values, width=34, command=None):
        cb = ttk.Combobox(parent, textvariable=textvariable, values=values,
                          width=width, state="readonly")
        if _HAS_MODERN:
            try:
                style_combobox(ttk.Style())
                cb.configure(style="Dark.TCombobox")
            except Exception:
                pass
        if command:
            cb.bind("<<ComboboxSelected>>", lambda e: command())
        return cb

    def _gm_name_row(self, parent):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="GM name:", font=(FONT, 11, "bold"),
                 bg=PANEL_BG, fg=TEXT).pack(side="left")
        if _HAS_MODERN:
            entry = DarkEntry(row, textvariable=self.gm_var, width=300)
            entry.pack(side="left", padx=(10, 0))
        else:
            entry = tk.Entry(row, textvariable=self.gm_var, width=32,
                             bg="#0E1420", fg=TEXT, insertbackground=TEXT,
                             relief="solid", bd=1, highlightthickness=0,
                             font=(FONT, 11))
            entry.pack(side="left", padx=(10, 0))
        entry.bind("<FocusIn>", lambda e: self._ph_focus(entry, True))
        entry.bind("<FocusOut>", lambda e: self._ph_focus(entry, False))
        self._ph_focus(entry, False)
        return row

    def _ph_focus(self, entry, focused):
        try:
            entry.configure(fg=TEXT if (focused or self.gm_var.get()) else MUTED)
        except Exception:
            pass

    def _team_picker_rows(self, parent, league_var, team_var, league_choices=None):
        """League + team dropdowns. league_choices limits the league list."""
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="League:", font=(FONT, 11, "bold"),
                 bg=PANEL_BG, fg=TEXT).pack(side="left")
        league_cb = self._combo(row, league_var, league_choices or list(WIZARD_LEAGUES.keys()),
                                width=8,
                                command=lambda: self._refresh_teams(league_var, team_var))
        league_cb.pack(side="left", padx=(10, 18))
        tk.Label(row, text="Team:", font=(FONT, 11, "bold"),
                 bg=PANEL_BG, fg=TEXT).pack(side="left")
        team_cb = self._combo(row, team_var, [], width=30)
        team_cb.pack(side="left", padx=(10, 12))
        self._team_combos[id(team_var)] = team_cb
        if _HAS_MODERN:
            RoundedButton(row, text="Randomize", bg="#2A3346", fg=TEXT,
                          command=lambda: self._randomize(league_var, team_var, league_choices),
                          padx=14, pady=6).pack(side="left")
        else:
            tk.Button(row, text="Randomize",
                      command=lambda: self._randomize(league_var, team_var, league_choices)).pack(side="left")
        self._refresh_teams(league_var, team_var)
        return team_cb

    def _refresh_teams(self, league_var, team_var):
        names = preview_team_names(league_var.get())
        cb = self._team_combos.get(id(team_var))
        if cb is None:
            return
        if names:
            cb.configure(values=names)
            if team_var.get() not in names:
                team_var.set(names[0])
        else:
            cb.configure(values=["Random team (generated at setup)"])
            team_var.set("Random team (generated at setup)")

    def _randomize(self, league_var, team_var, league_choices=None):
        choices = league_choices or list(WIZARD_LEAGUES.keys())
        league = random.choice(choices)
        league_var.set(league)
        self._refresh_teams(league_var, team_var)
        names = preview_team_names(league)
        if names:
            team_var.set(random.choice(names))

    # -- quick start page -------------------------------------------------
    def _build_quick(self, parent):
        sec = self._section(parent, "Quick Start",
                            "Sensible defaults, zero fuss. Pick a team (or randomize), "
                            "name your GM, and go.")
        defaults = tk.Label(sec, font=(FONT, 10), bg=PANEL_BG, fg=MUTED,
                            justify="left", wraplength=720,
                            text="Defaults: Medium database (~6,000 players) \u2022 "
                                 "NHL + AHL \u2022 NHL full sim, AHL quick sim \u2022 "
                                 "fog of war on. Change anything in Custom Setup.")
        defaults.pack(anchor="w", pady=(0, 8))

        self._team_picker_rows(sec, self.q_league_var, self.q_team_var)
        self._gm_name_row(sec)

    # -- custom setup page --------------------------------------------------
    def _build_custom(self, parent):
        # Database size (compact: segmented pills + one-line description)
        sec = self._section(parent, "Database Size",
                            "How many players to generate. Smaller is faster on "
                            "low-spec machines.")
        row = tk.Frame(sec, bg=PANEL_BG)
        row.pack(fill="x")
        if _HAS_MODERN:
            seg = SegmentedControl(row, ["Small", "Medium", "Large"], initial=1,
                                   accent=ACCENT, bg=PANEL_BG, command=self._on_size)
            seg.pack(side="left")
        else:
            for key in ("small", "medium", "large"):
                tk.Radiobutton(row, text=DATABASE_SIZES[key]["label"],
                               variable=self.size_var, value=key,
                               command=lambda k=key: self._on_size(k),
                               bg=PANEL_BG, fg=TEXT, selectcolor=ACCENT,
                               activebackground=PANEL_BG,
                               activeforeground=TEXT).pack(side="left", padx=(0, 12))
        self._size_desc = tk.Label(row, text="", font=(FONT, 10), bg=PANEL_BG,
                                   fg=MUTED, justify="left")
        self._size_desc.pack(side="left", padx=(14, 0))
        self._on_size("medium")

        # Leagues + per-league sim detail + fog of war (2-column grid)
        sec = self._section(parent, "Leagues & Sim Detail",
                            "Which leagues exist in your universe, and how deeply "
                            "each one is simulated. Fog of war hides true ratings "
                            "of unscouted players until your scouts see them.")
        grid = tk.Frame(sec, bg=PANEL_BG)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        for i, (key, info) in enumerate(WIZARD_LEAGUES.items()):
            cell = tk.Frame(grid, bg=PANEL_BG)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", pady=3,
                      padx=(0, 12) if i % 2 == 0 else (12, 0))
            chk = self._dark_check(cell, f"{key} \u2014 {info['blurb']}",
                                   self.league_vars[key],
                                   command=self._on_league_toggle)
            chk.pack(anchor="w")
            drow = tk.Frame(cell, bg=PANEL_BG)
            drow.pack(anchor="w", pady=(2, 0))
            tk.Label(drow, text="Sim:", font=(FONT, 10),
                     bg=PANEL_BG, fg=MUTED).pack(side="left", padx=(22, 6))
            detail_cb = self._combo(drow, self.detail_vars[key],
                                    [SIM_DETAILS[k] for k in SIM_DETAIL_KEYS],
                                    width=30)
            detail_cb.bind("<<ComboboxSelected>>",
                           lambda e, k=key, cb=detail_cb: self.detail_vars[k].set(
                               SIM_DETAIL_KEYS[[SIM_DETAILS[x] for x in SIM_DETAIL_KEYS].index(cb.get())]))
            detail_cb.set(SIM_DETAILS[self.detail_vars[key].get()])
            detail_cb.pack(side="left")
            self._detail_combos[key] = detail_cb
        sep = tk.Frame(sec, bg="#232D42", height=1)
        sep.pack(fill="x", pady=(8, 6))
        self._dark_check(sec, "Enable fog of war (recommended)",
                         self.fog_var).pack(anchor="w")
        self._on_league_toggle()

        # Your team
        sec = self._section(parent, "Your Team",
                            "The club you'll manage. Leagues list updates with "
                            "your selection above.")
        self._team_picker_rows(sec, self.c_league_var, self.c_team_var,
                               league_choices=["NHL", "AHL"])
        self._gm_name_row(sec)

    def _on_size(self, label):
        key = {"Small": "small", "Medium": "medium", "Large": "large"}.get(label, label)
        self.size_var.set(key)
        # SegmentedControl fires its command during construction, before
        # _size_desc exists — guard for that.
        if not hasattr(self, "_size_desc"):
            return
        info = DATABASE_SIZES[key]
        self._size_desc.configure(text=f"{info['tagline']}")

    def _on_league_toggle(self):
        active = [k for k, v in self.league_vars.items() if v.get()]
        for k, cb in self._detail_combos.items():
            try:
                cb.configure(state="readonly" if k in active else "disabled")
            except Exception:
                pass
        # keep custom team picker to active leagues
        cur = self.c_league_var.get()
        if cur not in active and active:
            self.c_league_var.set(active[0])
        self._refresh_teams(self.c_league_var, self.c_team_var)

    # -- start -------------------------------------------------------------
    def _active_leagues(self):
        return [k for k, v in self.league_vars.items() if v.get()] or ["NHL"]

    def _on_start(self):
        mode = self.mode_var.get()
        if mode == "quick":
            cfg = make_config(
                mode="quick",
                database_size="medium",
                leagues=["NHL", "AHL"],
                sim_detail={"NHL": "full", "AHL": "quick"},
                fog_of_war=True,
                gm_name=self.gm_var.get(),
                user_league=self.q_league_var.get(),
                user_team=self.q_team_var.get(),
            )
        else:
            leagues = self._active_leagues()
            # detail_vars hold sim-detail keys ("full"/"quick"/"scores");
            # the combos only display the friendly labels.
            detail = {k: self.detail_vars[k].get() for k in leagues}
            cfg = make_config(
                mode="custom",
                database_size=self.size_var.get(),
                leagues=leagues,
                sim_detail=detail,
                fog_of_war=self.fog_var.get(),
                gm_name=self.gm_var.get(),
                user_league=self.c_league_var.get(),
                user_team=self.c_team_var.get(),
            )
        try:
            self.on_start_callback(cfg)
        finally:
            self.destroy()


def open_setup_wizard(parent, on_start_callback):
    """Open the new-game setup wizard.

    :param parent: Tk parent window.
    :param on_start_callback: called with the config dict when the user
        clicks Start Career; the wizard closes itself afterwards.
    :returns: the NewGameSetupWizard instance.
    """
    wiz = NewGameSetupWizard(parent, on_start_callback)
    try:
        wiz.grab_set()
    except Exception:
        pass
    # transient() of a withdrawn/hidden parent can leave the window withdrawn
    # on WM-less displays; make visibility explicit.
    try:
        wiz.deiconify()
        wiz.lift()
    except Exception:
        pass
    return wiz
