# settings_window.py
# Settings & preferences — modern dark UI matching the rest of Puck Dynasty.

import tkinter as tk
from tkinter import ttk
import json
import os

from modern_ui import AppColors, AppFonts, AppCard, AppButton


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


class SettingsWindow(tk.Toplevel):
    """Settings & preferences window in the modern dark UI."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title("Settings - Hockey Manager")
        self.geometry("760x620")
        self.configure(background=AppColors.BG)

        # Settings data
        self.settings = self._load_settings()

        # Make window modal
        self.transient(parent)
        self.grab_set()

        self._create_interface()
        self._load_current_values()

        # Center the window
        self._center_window()

        # Track window
        if hasattr(parent, 'open_windows'):
            parent.open_windows['settings'] = self

    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

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
        for key in ("results", "interface", "simulation", "notifications"):
            holder, content = self._make_scrollable_tab(self._tab_content)
            self._tab_holders[key] = holder
            self._tab_frames[key] = content

        self._create_results_tab(self._tab_frames["results"])
        self._create_interface_tab(self._tab_frames["interface"])
        self._create_simulation_tab(self._tab_frames["simulation"])
        self._create_notifications_tab(self._tab_frames["notifications"])

        self._create_footer(main)
        self._select_tab("results")

    def _create_header(self, parent):
        header = tk.Frame(parent, bg=AppColors.BG)
        header.pack(fill="x", pady=(0, 12))
        tk.Label(header, text="Settings", bg=AppColors.BG,
                 fg=AppColors.TEXT_PRIMARY, font=AppFonts.H1).pack(anchor="w")
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
                ("notifications", "Notifications")]
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
        self.theme_var = tk.StringVar()
        self._row(theme, "Theme:", self.theme_var,
                  ['Dark (Current)', 'Light (Coming Soon)',
                   'High Contrast (Coming Soon)'], width=24)
        self.font_size_var = tk.StringVar()
        self._row(theme, "Font size:", self.font_size_var,
                  ['Small', 'Medium (Current)', 'Large'], width=18)

        window = self._section(content, "Window Behavior")
        self.auto_close_var = tk.BooleanVar()
        self._check(window, "Automatically close settings window after saving",
                    self.auto_close_var)
        self.remember_windows_var = tk.BooleanVar()
        self._check(window, "Remember window positions and sizes",
                    self.remember_windows_var)

    def _create_simulation_tab(self, content):
        """Game simulation preferences."""
        speed = self._section(content, "Simulation Speed")
        self.sim_speed_var = tk.StringVar()
        self._row(speed, "Game simulation speed:", self.sim_speed_var,
                  ['Very Fast', 'Fast (Current)', 'Normal', 'Detailed'],
                  width=16)

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
        """Load settings from file or create defaults"""
        settings_file = os.path.join(os.path.dirname(__file__),
                                     'settings.json')

        # Default settings
        defaults = {
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
                'font_size': 'Medium (Current)',
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
            }
        }

        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._merge_settings(defaults, loaded_settings)
                    return defaults
            else:
                return defaults
        except Exception as e:
            print(f"Error loading settings: {e}")
            return defaults

    def _merge_settings(self, defaults, loaded):
        """Recursively merge loaded settings into defaults"""
        for key, value in loaded.items():
            if key in defaults:
                if isinstance(value, dict) and isinstance(
                        defaults[key], dict):
                    self._merge_settings(defaults[key], value)
                else:
                    defaults[key] = value

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
                                            'Medium (Current)'))
        self.auto_close_var.set(ui_prefs.get('auto_close_settings', False))
        self.remember_windows_var.set(
            ui_prefs.get('remember_window_positions', True))

        # Simulation
        simulation = self.settings.get('simulation', {})

        self.sim_speed_var.set(
            simulation.get('simulation_speed', 'Fast (Current)'))
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
            'auto_close_settings': self.auto_close_var.get(),
            'remember_window_positions': self.remember_windows_var.get()
        })

        # Simulation
        self.settings.setdefault('simulation', {}).update({
            'simulation_speed': self.sim_speed_var.get(),
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

    def _notify_parent_of_changes(self):
        """Notify parent of setting changes"""
        if hasattr(self.parent, 'apply_settings'):
            self.parent.apply_settings(self.settings)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _mark_changed(self, event=None):
        """Mark that settings have been changed"""
        self.title("Settings - Hockey Manager *")

    def _reset_to_defaults(self):
        """Reset all settings to defaults"""
        result = tk.messagebox.askyesno(
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?\n\n"
            "This cannot be undone.",
            parent=self)
        if result:
            self.settings = self._load_settings()
            self._load_current_values()
            self._mark_changed()

    def _apply_settings(self):
        """Apply settings without saving to file"""
        self._collect_current_values()
        self._notify_parent_of_changes()
        tk.messagebox.showinfo(
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

            # Show success message
            tk.messagebox.showinfo(
                "Settings Saved",
                "Settings have been saved successfully.", parent=self)

            # Auto-close if enabled
            if self.auto_close_var.get():
                self.destroy()
            else:
                self.title("Settings - Hockey Manager")  # Remove * indicator

        except Exception as e:
            tk.messagebox.showerror(
                "Error", f"Failed to save settings:\n{e}", parent=self)

    def _cancel(self):
        """Cancel changes and close window"""
        if self.title().endswith('*'):  # Check if there are unsaved changes
            result = tk.messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before "
                "closing?",
                parent=self)
            if result is True:  # Save
                self._save_settings()
                return
            elif result is None:  # Cancel
                return

        self.destroy()

    def get_game_results_settings(self):
        """Get current game results settings for external use"""
        return self.settings.get('game_results', {})

    def destroy(self):
        """Clean up when window is destroyed"""
        if hasattr(self.parent, 'open_windows') and \
                'settings' in self.parent.open_windows:
            del self.parent.open_windows['settings']
        super().destroy()
