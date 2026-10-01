# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# settings_window.py
# Settings & preferences — modern dark UI matching the rest of Puck Dynasty.

import tkinter as tk
from popup_system import messagebox, InGamePopup, confirm_card, ask_card
from tkinter import ttk
import json
import os
import customtkinter as ctk

from modern_ui import AppColors, AppFonts, AppCard, AppButton


# Gating T2-Phase 3: the unsaved-changes card answers through this named
# resolver on post-load re-present. The view is kept module-side while
# the card is open (same pattern as staff_management_window._chain_app).
_SETTINGS_DIRTY_VIEW = None


def _set_settings_dirty_view(view):
    global _SETTINGS_DIRTY_VIEW
    _SETTINGS_DIRTY_VIEW = view


def _settings_dirty_answer(session_id, dialog_id, value, **kwargs):
    """DIALOG_RESOLVERS['settings_dirty_answer']: 'save' saves (and may
    auto-close), 'nosave' closes without saving, anything else stays.
    Never raises; a missing view is an honest no-op."""
    try:
        view = _SETTINGS_DIRTY_VIEW
        if view is None:
            return False
        if value == "save":
            try:
                view._save_settings()
            except Exception:
                pass
        elif value == "nosave":
            try:
                view.close_view()
            except Exception:
                pass
        return True
    except Exception:
        return False


try:
    from popup_system import register_dialog_resolver as _sreg
    _sreg("settings_dirty_answer", _settings_dirty_answer)
except Exception:
    pass


def default_settings():
    """Built-in settings defaults.

    Kept at module level so headless callers (e.g. main.get_settings)
    can read settings without constructing the SettingsWindow GUI.
    """
    return {
        'game_results': {
            'show_user_team_only': True,
            'default_leagues': ['National Hockey League'],
            'max_games_display': '50',
            'max_news_display': '10',
            'default_news_categories': ['Team News', 'League News',
                                        'Trades', 'Injuries']
        },
        'ui_preferences': {
            'theme': 'Dark (Current)',
            'font_size': 'Default',
            'auto_close_settings': False,
            'remember_window_positions': True
        },
        'simulation': {
            'simulation_speed': 'Fast (Current)',
            'auto_continue_non_game_days': False,
            'always_show_daily_results': True,
            'use_game_viewer': False,
            'game_viewer_mode': 'Full Game',
            'draft_class_quality': 'Normal',
            'scoring_level': 'Low (Current)'
        },
        'notifications': {
            'email_notifications': {
                'Trade Offers': True,
                'Contract Expiring Soon': True,
                'Injury Reports': True,
                'Player Milestones': False,
                'League News': False,
                'Draft Updates': True
            },
            'enable_sounds': True,
            'sound_volume': 'Medium'
        },
        'career': {
            # Muck's flag: user can choose whether the GM can be sacked.
            # True = board can sack you at 0 confidence (default, classic FM).
            # False = job is safe; confidence still affects budgets/morale.
            'gm_can_be_sacked': True,
        },
    }


def _merge_settings(defaults, loaded):
    """Recursively merge loaded settings into defaults (in place)."""
    for key, value in loaded.items():
        if key in defaults:
            if isinstance(value, dict) and isinstance(defaults[key], dict):
                _merge_settings(defaults[key], value)
            else:
                defaults[key] = value


def load_settings(path=None):
    """Load settings.json merged over defaults — no GUI involved.

    Used by main.get_settings() so reading settings never constructs
    (and flashes) a SettingsWindow.
    """
    settings_file = path or os.path.join(os.path.dirname(__file__),
                                         'settings.json')
    settings = default_settings()
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                _merge_settings(settings, json.load(f))
    except Exception as e:
        print(f"Error loading settings: {e}")
    return settings


class ModernCheck(tk.Frame):
    """Dark checkbox row: custom-drawn box + label, bound to a BooleanVar."""

    def __init__(self, parent, text, variable, command=None, font=None):
        super().__init__(parent, bg=AppColors.BG_ELEVATED)
        self.variable = variable
        self._command = command
        self.box = tk.Canvas(self, width=18, height=18,
                             bg=AppColors.BG_ELEVATED,
                             highlightthickness=0, cursor="hand2")
        self.box.pack(side="left")
        self.label = tk.Label(self, text=text, bg=AppColors.BG_ELEVATED,
                              fg=AppColors.TEXT_PRIMARY,
                              font=font or AppFonts.SMALL, cursor="hand2")
        self.label.pack(side="left", padx=(8, 0))
        self._draw()
        for w in (self, self.box, self.label):
            w.bind("<Button-1>", self._toggle)
        try:
            self.variable.trace_add("write", lambda *a: self._draw())
        except Exception:
            pass

    def _draw(self):
        self.box.delete("all")
        on = bool(self.variable.get())
        fill = AppColors.ACCENT if on else AppColors.BG
        outline = AppColors.ACCENT if on else AppColors.BORDER_LIGHT
        self.box.create_rectangle(2, 2, 16, 16, fill=fill,
                                  outline=outline, width=1)
        if on:
            self.box.create_line(5, 9, 8, 12, fill="#ffffff", width=2)
            self.box.create_line(8, 12, 13, 5, fill="#ffffff", width=2)

    def _toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        self._draw()
        if self._command:
            self._command()


class SettingsDropdown(ttk.Combobox):
    """Dark dropdown matching the app's modern UI."""

    def __init__(self, parent, textvariable, values, width=16,
                 on_select=None):
        super().__init__(parent, textvariable=textvariable,
                         values=list(values), state="readonly", width=width,
                         font=AppFonts.SMALL)
        self._on_select = on_select
        self.bind("<<ComboboxSelected>>", self._handle_select)
        self._style()

    def _handle_select(self, event=None):
        if self._on_select:
            self._on_select(event)

    def _style(self):
        style = ttk.Style()
        name = f"SettingsDropdown_{id(self)}.TCombobox"
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(name,
                        fieldbackground=AppColors.BG_ELEVATED,
                        background=AppColors.BG_ELEVATED,
                        foreground=AppColors.TEXT_PRIMARY,
                        arrowcolor=AppColors.ACCENT,
                        bordercolor=AppColors.BORDER,
                        lightcolor=AppColors.BORDER,
                        darkcolor=AppColors.BORDER,
                        padding=6)
        style.map(name,
                  fieldbackground=[("readonly", AppColors.BG_ELEVATED)],
                  foreground=[("readonly", AppColors.TEXT_PRIMARY)],
                  background=[("readonly", AppColors.BG_HOVER)],
                  arrowcolor=[("readonly", AppColors.ACCENT)])
        self.configure(style=name)
        try:
            self.tk.call("ttk::combobox::PopdownWindow", self)
        except Exception:
            pass
        option = f"{self}._popdown.f.l"
        try:
            self.tk.call(option, "configure",
                         "-background", AppColors.BG_ELEVATED,
                         "-foreground", AppColors.TEXT_PRIMARY,
                         "-selectbackground", AppColors.ACCENT_BG,
                         "-selectforeground", AppColors.TEXT_PRIMARY)
        except Exception:
            pass


class SettingsView(ctk.CTkFrame):
    """Settings & preferences view in the modern dark UI (full-screen)."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the SettingsWindow wrapper
        self.configure(fg_color=AppColors.BG)

        # Settings data
        self.settings = self._load_settings()
        # Unsaved-changes tracking (replaces the old "*"-in-title marker)
        self._dirty = False

        self._create_interface()
        self._load_current_values()


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass


    def _ask_confirm(self, text, on_yes, on_no=None):
        """Show an in-view Yes/No panel (replaces messagebox.askyesno)."""
        old = getattr(self, "_confirm_panel", None)
        if old is not None:
            try: old.destroy()
            except Exception: pass
        import customtkinter as ctk
        panel = ctk.CTkFrame(self, fg_color="#2a2a3a", corner_radius=8)
        panel.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(panel, text=text, wraplength=520).pack(padx=12, pady=(10, 6))
        btns = ctk.CTkFrame(panel, fg_color="transparent")
        btns.pack(pady=(0, 10))
        def _yes():
            try: panel.destroy()
            except Exception: pass
            self._confirm_panel = None
            on_yes()
        def _no():
            try: panel.destroy()
            except Exception: pass
            self._confirm_panel = None
            if on_no: on_no()
        ctk.CTkButton(btns, text="Yes", command=_yes, width=90).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="No", command=_no, width=90).pack(side="left", padx=6)
        self._confirm_panel = panel

    def close_view(self):
        """Close this screen, cleaning up the open-windows registry."""
        try:
            ow = getattr(self.app, 'open_windows', None)
            if ow is not None and 'settings' in ow:
                del ow['settings']
        except Exception:
            pass
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _create_interface(self):
        main = tk.Frame(self, bg=AppColors.BG)
        main.pack(fill="both", expand=True, padx=20, pady=16)

        self._create_header(main)
        self._create_tab_bar(main)

        # Content area holding one scrollable frame per tab
        self._tab_content = tk.Frame(main, bg=AppColors.BG)
        self._tab_content.pack(fill="both", expand=True, pady=(12, 12))

        self._tab_frames = {}
        self._tab_holders = {}
        for key in ("results", "interface", "simulation", "notifications", "career"):
            holder, content = self._make_scrollable_tab(self._tab_content)
            self._tab_holders[key] = holder
            self._tab_frames[key] = content

        self._create_results_tab(self._tab_frames["results"])
        self._create_interface_tab(self._tab_frames["interface"])
        self._create_simulation_tab(self._tab_frames["simulation"])
        self._create_notifications_tab(self._tab_frames["notifications"])
        self._create_career_tab(self._tab_frames["career"])

        self._create_footer(main)
        self._select_tab("results")

    def _create_header(self, parent):
        header = tk.Frame(parent, bg=AppColors.BG)
        header.pack(fill="x", pady=(0, 12))
        tk.Label(header, text="Customize your Puck Dynasty experience",
                 bg=AppColors.BG, fg=AppColors.TEXT_SECONDARY,
                 font=AppFonts.SMALL).pack(anchor="w", pady=(2, 0))

    def _create_tab_bar(self, parent):
        bar = tk.Frame(parent, bg=AppColors.BG)
        bar.pack(fill="x")
        self._tab_buttons = {}
        tabs = [("results", "Game Results"),
                ("interface", "Interface"),
                ("simulation", "Simulation"),
                ("notifications", "Notifications"),
                ("career", "Career")]
        for key, label in tabs:
            holder = tk.Frame(bar, bg=AppColors.BG)
            holder.pack(side="left", padx=(0, 6))
            btn = tk.Button(holder, text=label, relief="flat", bd=0,
                            highlightthickness=0, cursor="hand2",
                            font=AppFonts.SMALL_BOLD,
                            bg=AppColors.BG, activebackground=AppColors.BG,
                            command=lambda k=key: self._select_tab(k))
            btn.pack(padx=10, pady=(6, 2))
            underline = tk.Frame(holder, bg=AppColors.BG, height=2)
            underline.pack(fill="x")
            self._tab_buttons[key] = (btn, underline)
        # Divider under the tab bar
        tk.Frame(parent, bg=AppColors.BORDER, height=1).pack(fill="x")

    def _select_tab(self, key):
        for k, holder in self._tab_holders.items():
            if k == key:
                holder.pack(fill="both", expand=True)
            else:
                holder.pack_forget()
        for k, (btn, underline) in self._tab_buttons.items():
            active = (k == key)
            btn.configure(fg=AppColors.ACCENT if active
                          else AppColors.TEXT_SECONDARY,
                          activeforeground=AppColors.ACCENT
                          if active else AppColors.TEXT_PRIMARY)
            underline.configure(bg=AppColors.ACCENT if active
                                else AppColors.BG)

    def _make_scrollable_tab(self, parent):
        """A tab page with a scrollable content frame.
        Returns (holder, content frame)."""
        holder = tk.Frame(parent, bg=AppColors.BG)
        canvas = tk.Canvas(holder, bg=AppColors.BG, highlightthickness=0)
        # Dark scrollbar matching the UI
        sb_style = ttk.Style()
        try:
            sb_style.theme_use("clam")
        except Exception:
            pass
        sb_style_name = f"Dark.Vertical.TScrollbar"
        sb_style.configure(sb_style_name,
                           background=AppColors.BG_ELEVATED,
                           troughcolor=AppColors.BG,
                           bordercolor=AppColors.BG,
                           arrowcolor=AppColors.TEXT_TERTIARY)
        sb_style.map(sb_style_name,
                     background=[("active", AppColors.BG_HOVER),
                                 ("pressed", AppColors.BORDER_LIGHT)])
        scrollbar = ttk.Scrollbar(holder, orient="vertical",
                                  command=canvas.yview,
                                  style=sb_style_name)
        content = tk.Frame(canvas, bg=AppColors.BG)
        content.bind("<Configure>",
                     lambda e, c=canvas: c.configure(
                         scrollregion=c.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw",
                               tags="content")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>",
                    lambda e, c=canvas: c.itemconfigure(
                        "content", width=e.width))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        # Mousewheel scrolling
        canvas.bind("<Enter>", lambda e, c=canvas: c.bind_all(
            "<MouseWheel>", lambda ev: c.yview_scroll(
                -1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e, c=canvas: c.unbind_all(
            "<MouseWheel>"))
        return holder, content

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------

    def _section(self, parent, title):
        """A titled card section. Returns the inner frame to add rows to."""
        card = AppCard(parent, padding=14)
        card.pack(fill="x", pady=(0, 12))
        inner = card.get_content_frame()
        tk.Label(inner, text=title, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY,
                 font=AppFonts.H3).pack(anchor="w", pady=(0, 10))
        return inner

    def _row(self, parent, label, var, values, width=18, hint=None):
        """A labeled dropdown row."""
        row = tk.Frame(parent, bg=AppColors.BG_ELEVATED)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_PRIMARY, font=AppFonts.SMALL).pack(
                     side="left")
        SettingsDropdown(row, textvariable=var, values=values, width=width,
                         on_select=self._mark_changed).pack(
                             side="left", padx=(10, 0))
        if hint:
            tk.Label(row, text=hint, bg=AppColors.BG_ELEVATED,
                     fg=AppColors.TEXT_TERTIARY,
                     font=AppFonts.CAPTION).pack(side="left", padx=(10, 0))

    def _check(self, parent, text, var, pady=3):
        ModernCheck(parent, text=text, variable=var,
                    command=self._mark_changed,
                    font=AppFonts.SMALL).pack(anchor="w", pady=pady)

    def _caption(self, parent, text):
        tk.Label(parent, text=text, bg=AppColors.BG_ELEVATED,
                 fg=AppColors.TEXT_TERTIARY, font=AppFonts.CAPTION,
                 wraplength=620, justify="left").pack(anchor="w", pady=(2, 0))

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _create_results_tab(self, content):
        """Game results display preferences."""
        # Default view
        view = self._section(content, "Default View")
        self.user_team_only_var = tk.BooleanVar()
        self._check(view, "Show only my team's games by default",
                    self.user_team_only_var)

        leagues = ['National Hockey League', 'American Hockey League',
                   'ECHL', 'CHL', 'NCAA', 'International']
        tk.Label(view, text="Default leagues to display:",
                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                 font=AppFonts.SMALL_BOLD).pack(anchor="w", pady=(10, 4))
        self.league_vars = {}
        for i, league in enumerate(leagues):
            if i % 2 == 0:
                row = tk.Frame(view, bg=AppColors.BG_ELEVATED)
                row.pack(fill="x")
            var = tk.BooleanVar()
            self.league_vars[league] = var
            ModernCheck(row, text=league, variable=var,
                        command=self._mark_changed,
                        font=AppFonts.SMALL).pack(side="left",
                                                 padx=(0, 24), pady=2)

        # Performance
        perf = self._section(content, "Performance & Display Limits")
        self.max_games_var = tk.StringVar()
        self._row(perf, "Maximum games to display:", self.max_games_var,
                  ['25', '50', '100', '200', 'All'], width=8,
                  hint="Recommended: 50 for performance")
        self.max_news_var = tk.StringVar()
        self._row(perf, "Maximum news items to display:", self.max_news_var,
                  ['5', '10', '20', '50', 'All'], width=8)

        # News categories
        news = self._section(content, "News Categories")
        tk.Label(news, text="Default news categories to display:",
                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                 font=AppFonts.SMALL_BOLD).pack(anchor="w", pady=(0, 4))
        self.news_category_vars = {}
        categories = ['Team News', 'League News', 'Trades', 'Injuries',
                      'Signings', 'Draft', 'Other']
        for i, category in enumerate(categories):
            if i % 2 == 0:
                row = tk.Frame(news, bg=AppColors.BG_ELEVATED)
                row.pack(fill="x")
            var = tk.BooleanVar()
            self.news_category_vars[category] = var
            ModernCheck(row, text=category, variable=var,
                        command=self._mark_changed,
                        font=AppFonts.SMALL).pack(side="left",
                                                 padx=(0, 24), pady=2)

    def _create_interface_tab(self, content):
        """User interface preferences."""
        theme = self._section(content, "Visual Theme")
        # Only dark is actually implemented (ctk_theme forces dark mode;
        # nothing reads the stored 'theme' value). The dropdown offered
        # Light / High Contrast "(Coming Soon)" options that did nothing,
        # so it is replaced with an honest static label.
        self.theme_var = tk.StringVar(value='Dark (Current)')
        tk.Label(theme, text="Dark \u2014 the only available theme",
                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                 font=AppFonts.SMALL).pack(anchor="w", pady=4)
        self.font_size_var = tk.StringVar()
        self._row(theme, "Font size:", self.font_size_var,
                  ['Compact', 'Small', 'Default', 'Large', 'Extra Large'],
                  width=18)
        self._caption(theme, "Applies instantly to most windows.")

        window = self._section(content, "Window Behavior")
        self.auto_close_var = tk.BooleanVar()
        self._check(window, "Automatically close settings window after saving",
                    self.auto_close_var)
        self.remember_windows_var = tk.BooleanVar()
        self._check(window, "Remember window positions and sizes",
                    self.remember_windows_var)
        self.auto_fit_var = tk.BooleanVar()
        self._check(window, "Auto-fit text size to window size",
                    self.auto_fit_var)
        self._caption(window,
                      "Shrinks text instead of clipping it when the window "
                      "is small; grows it on large monitors.")

    def _create_simulation_tab(self, content):
        """Game simulation preferences."""
        # NOTE: the old "Game simulation speed" dropdown was removed --
        # the value was saved but never read anywhere, so the control was
        # a dead end. The stored value is preserved untouched in case a
        # future consumer needs it.
        auto = self._section(content, "Auto-Continue")
        self.auto_continue_var = tk.BooleanVar()
        self._check(auto, "Auto-continue through non-game days",
                    self.auto_continue_var)
        self.show_daily_results_var = tk.BooleanVar()
        self._check(auto, "Always show daily results window",
                    self.show_daily_results_var)

        viewer = self._section(content, "Game Viewer")
        self.use_game_viewer_var = tk.BooleanVar()
        self._check(viewer, "Use visual game viewer for my team's games",
                    self.use_game_viewer_var)
        self.game_viewer_mode_var = tk.StringVar()
        self._row(viewer, "Game viewer mode:", self.game_viewer_mode_var,
                  ['Full Game', 'Highlights Only', 'Fast Forward'], width=16)

        league = self._section(content, "League & Scoring")
        self.draft_quality_var = tk.StringVar()
        self._row(league, "Draft class quality:", self.draft_quality_var,
                  ['Weak', 'Normal', 'Strong', 'Generational'], width=14,
                  hint="applies to future draft classes")
        self.scoring_level_var = tk.StringVar()
        self._row(league, "Scoring level:", self.scoring_level_var,
                  ['Low (Current)', 'Medium (NHL Baseline)',
                   'High (Arcade)'], width=22,
                  hint="goals per game: ~5.5 / ~6.0 / 7+")

    def _create_notifications_tab(self, content):
        """Notification preferences."""
        email = self._section(content, "Email Notifications")
        tk.Label(email, text="Receive email notifications for:",
                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                 font=AppFonts.SMALL_BOLD).pack(anchor="w", pady=(0, 6))
        self.email_notification_vars = {}
        for email_type in ['Trade Offers', 'Contract Expiring Soon',
                           'Injury Reports', 'Player Milestones',
                           'League News', 'Draft Updates']:
            var = tk.BooleanVar()
            self.email_notification_vars[email_type] = var
            self._check(email, email_type, var)

        sound = self._section(content, "Sound Notifications")
        self.enable_sounds_var = tk.BooleanVar()
        self._check(sound, "Enable sound effects", self.enable_sounds_var)
        self.sound_volume_var = tk.StringVar()
        self._row(sound, "Sound volume:", self.sound_volume_var,
                  ['Off', 'Low', 'Medium', 'High'], width=10)

    def _create_career_tab(self, content):
        """Career / job security preferences."""
        job = self._section(content, "Job Security")
        self.gm_can_be_sacked_var = tk.BooleanVar()
        self._check(job, "Board can sack the GM (job is on the line)",
                    self.gm_can_be_sacked_var)
        tk.Label(job,
                 text=("If off, your job is safe no matter what — board confidence "
                       "still affects budgets and morale."),
                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                 font=AppFonts.SMALL, wraplength=400,
                 justify="left").pack(anchor="w", pady=(4, 0))

    def _create_footer(self, parent):
        footer = tk.Frame(parent, bg=AppColors.BG)
        footer.pack(fill="x", pady=(4, 0))

        AppButton(footer, text="Reset to Defaults", style="secondary",
                  width=150, height=38,
                  command=self._reset_to_defaults).pack(side="left")

        right = tk.Frame(footer, bg=AppColors.BG)
        right.pack(side="right")
        AppButton(right, text="Cancel", style="secondary",
                  width=100, height=38,
                  command=self._cancel).pack(side="left", padx=(0, 10))
        AppButton(right, text="Apply", style="secondary",
                  width=100, height=38,
                  command=self._apply_settings).pack(side="left",
                                                     padx=(0, 10))
        AppButton(right, text="Save", style="primary",
                  width=110, height=38,
                  command=self._save_settings).pack(side="left")

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _load_settings(self):
        """Load settings from file or create defaults (GUI-free helper)."""
        return load_settings()

    def refresh(self):
        """Re-entrant refresh for screen-cache hits (gating Phase 1).

        Preserves in-progress edits: when the user has unsaved (dirty)
        changes the widgets are left alone -- parking the view must never
        wipe half-made changes. Otherwise values re-sync from the dict.
        """
        if getattr(self, "_dirty", False):
            return
        self._load_current_values()

    def _load_current_values(self):
        """Load current values into the UI"""
        # Game Results settings
        game_results = self.settings.get('game_results', {})

        self.user_team_only_var.set(
            game_results.get('show_user_team_only', True))

        default_leagues = game_results.get(
            'default_leagues', ['National Hockey League'])
        for league, var in self.league_vars.items():
            var.set(league in default_leagues)

        self.max_games_var.set(game_results.get('max_games_display', '50'))
        self.max_news_var.set(game_results.get('max_news_display', '10'))

        default_news_cats = game_results.get(
            'default_news_categories',
            ['Team News', 'League News', 'Trades', 'Injuries'])
        for category, var in self.news_category_vars.items():
            var.set(category in default_news_cats)

        # UI Preferences
        ui_prefs = self.settings.get('ui_preferences', {})

        self.theme_var.set(ui_prefs.get('theme', 'Dark (Current)'))
        self.font_size_var.set(ui_prefs.get('font_size',
                                            'Default'))
        # Migrate legacy tier names (Small / Medium (Current) / Large).
        try:
            import ui_scale
            self.font_size_var.set(
                ui_scale.normalize_tier_name(self.font_size_var.get()))
        except Exception:
            pass
        self.auto_fit_var.set(ui_prefs.get('auto_fit_ui', False))
        self.auto_close_var.set(ui_prefs.get('auto_close_settings', False))
        self.remember_windows_var.set(
            ui_prefs.get('remember_window_positions', True))

        # Simulation
        simulation = self.settings.get('simulation', {})

        self.auto_continue_var.set(
            simulation.get('auto_continue_non_game_days', False))
        self.show_daily_results_var.set(
            simulation.get('always_show_daily_results', True))
        self.use_game_viewer_var.set(
            simulation.get('use_game_viewer', False))
        self.game_viewer_mode_var.set(
            simulation.get('game_viewer_mode', 'Full Game'))
        self.draft_quality_var.set(
            simulation.get('draft_class_quality', 'Normal'))
        self.scoring_level_var.set(
            simulation.get('scoring_level', 'Low (Current)'))

        # Notifications
        notifications = self.settings.get('notifications', {})

        email_notifications = notifications.get('email_notifications', {})
        for email_type, var in self.email_notification_vars.items():
            var.set(email_notifications.get(email_type, False))

        self.enable_sounds_var.set(notifications.get('enable_sounds', True))
        self.sound_volume_var.set(
            notifications.get('sound_volume', 'Medium'))

        # Career
        career = self.settings.get('career', {})
        self.gm_can_be_sacked_var.set(
            career.get('gm_can_be_sacked', True))

    def _collect_current_values(self):
        """Collect current values from UI into settings, preserving any
        keys this window doesn't manage (e.g. user_game_mode)."""
        # Game Results
        self.settings.setdefault('game_results', {}).update({
            'show_user_team_only': self.user_team_only_var.get(),
            'default_leagues': [league for league, var
                                in self.league_vars.items() if var.get()],
            'max_games_display': self.max_games_var.get(),
            'max_news_display': self.max_news_var.get(),
            'default_news_categories': [cat for cat, var
                                        in self.news_category_vars.items()
                                        if var.get()]
        })

        # UI Preferences
        self.settings.setdefault('ui_preferences', {}).update({
            'theme': self.theme_var.get(),
            'font_size': self.font_size_var.get(),
            'auto_fit_ui': self.auto_fit_var.get(),
            'auto_close_settings': self.auto_close_var.get(),
            'remember_window_positions': self.remember_windows_var.get()
        })

        # Simulation
        self.settings.setdefault('simulation', {}).update({
            # Preserved as stored: no UI control edits it anymore (it was
            # a dead control -- saved but never read). Keeping the value
            # harmless rather than deleting it.
            'simulation_speed': self.settings.get('simulation', {}).get(
                'simulation_speed', 'Fast (Current)'),
            'auto_continue_non_game_days': self.auto_continue_var.get(),
            'always_show_daily_results':
                self.show_daily_results_var.get(),
            'use_game_viewer': self.use_game_viewer_var.get(),
            'game_viewer_mode': self.game_viewer_mode_var.get(),
            'draft_class_quality': self.draft_quality_var.get(),
            'scoring_level': self.scoring_level_var.get()
        })

        # Notifications
        notif = self.settings.setdefault('notifications', {})
        notif.update({
            'email_notifications': {email_type: var.get()
                                    for email_type, var
                                    in self.email_notification_vars.items()},
            'enable_sounds': self.enable_sounds_var.get(),
            'sound_volume': self.sound_volume_var.get()
        })

        # Career
        self.settings.setdefault('career', {}).update({
            'gm_can_be_sacked': self.gm_can_be_sacked_var.get(),
        })

    def _notify_parent_of_changes(self):
        """Notify parent of setting changes"""
        if hasattr(self.app, 'apply_settings'):
            self.app.apply_settings(self.settings)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _mark_changed(self, event=None):
        """Mark that settings have been changed"""
        self._dirty = True

    def _reset_to_defaults(self):
        """Reset all settings to factory defaults"""
        def _do_reset():
            # Factory defaults, not last-saved: this is what "Reset to
            # Defaults" promises. default_settings() is the single
            # source of truth used by get_settings() for fresh installs.
            self.settings = default_settings()
            self._load_current_values()
            self._mark_changed()

        # Gating T2-Phase 3: non-modal confirm; dismiss = keep settings.
        confirm_card(self, "Reset Settings",
                     "Are you sure you want to reset all settings to defaults?\n\n"
                     "This cannot be undone.",
                     on_yes=_do_reset)

    def _apply_settings(self):
        """Apply settings without saving to file"""
        self._collect_current_values()
        self._notify_parent_of_changes()
        messagebox.showinfo(
            "Settings Applied",
            "Settings have been applied for this session.", parent=self)

    def _save_settings(self):
        """Save settings to file and apply them"""
        self._collect_current_values()

        # Save to file
        settings_file = os.path.join(os.path.dirname(__file__),
                                     'settings.json')
        try:
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)

            self._notify_parent_of_changes()

            # Apply the font-size + auto-fit choices immediately: the
            # live font registry resizes open windows in place.
            try:
                import ui_scale
                ui_scale.apply_from_prefs()
            except Exception:
                pass

            # Show success message
            messagebox.showinfo(
                "Settings Saved",
                "Settings have been saved successfully.", parent=self)

            # Auto-close if enabled
            if self.auto_close_var.get():
                self.close_view()
            else:
                self._dirty = False  # Clear the unsaved-changes indicator

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to save settings:\n{e}", parent=self)

    def _cancel(self):
        """Cancel changes and close window"""
        if not self._dirty:  # No unsaved changes: just close.
            self.close_view()
            return

        def _on_answer(value):
            if value == "save":
                self._save_settings()
            elif value == "nosave":
                self.close_view()
            # "cancel" or dismiss: stay, keep editing.

        # Gating T2-Phase 3: non-modal 3-way card; dismiss = stay.
        _set_settings_dirty_view(self)
        ask_card(self, "Unsaved Changes",
                 "You have unsaved changes. Do you want to save before "
                 "closing?",
                 [("Save", "save", "primary"),
                  ("Don't Save", "nosave", "secondary"),
                  ("Cancel", "cancel", "secondary")],
                 on_answer=_on_answer,
                 default_on_dismiss="defer",
                 session_id="settings_dirty", dialog_id="dirty_card",
                 resolver="settings_dirty_answer")

    def get_game_results_settings(self):
        """Get current game results settings for external use"""
        return self.settings.get('game_results', {})
