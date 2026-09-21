# settings_window.py
# Comprehensive settings management for Hockey Manager

import tkinter as tk
from tkinter import ttk
import json
import os
from typing import Dict, Any

class SettingsWindow(tk.Toplevel):
    """Comprehensive settings window for managing game preferences"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        self.title("Settings - Hockey Manager")
        self.geometry("800x600")
        self.configure(background=parent.BG_COLOR)
        
        # Settings data
        self.settings = self._load_settings()
        
        # Track changes
        self.pending_changes = {}
        
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
        
    def _create_interface(self):
        """Create the main interface"""
        # Main container
        main_frame = ttk.Frame(self, style='Panel.TFrame', padding=15)
        main_frame.pack(fill='both', expand=True)
        
        # Header
        self._create_header(main_frame)
        
        # Settings content with tabs
        self._create_settings_content(main_frame)
        
        # Footer with action buttons
        self._create_footer(main_frame)
        
    def _create_header(self, parent):
        """Create the header section"""
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame')
        header_frame.pack(fill='x', pady=(0, 15))
        
        # Title
        title_label = tk.Label(header_frame, text="⚙️ Settings & Preferences", 
                              font=(self.parent.FONT_FAMILY, 16, 'bold'),
                              fg=self.parent.HEADER_COLOR, bg=self.parent.TITLE_BAR_COLOR)
        title_label.pack(side='left')
        
        # Subtitle
        subtitle_label = tk.Label(header_frame, text="Customize your Hockey Manager experience",
                                 font=(self.parent.FONT_FAMILY, 10),
                                 fg=self.parent.TEXT_COLOR, bg=self.parent.TITLE_BAR_COLOR)
        subtitle_label.pack(side='left', padx=(15, 0))
        
    def _create_settings_content(self, parent):
        """Create the main settings content with tabs"""
        # Create notebook for different setting categories
        self.notebook = ttk.Notebook(parent, style='TNotebook')
        self.notebook.pack(fill='both', expand=True, pady=(0, 15))
        
        # Tab 1: Game Results Display
        self._create_results_display_tab()
        
        # Tab 2: User Interface
        self._create_ui_preferences_tab()
        
        # Tab 3: Game Simulation
        self._create_simulation_preferences_tab()
        
        # Tab 4: Notifications
        self._create_notifications_tab()
        
    def _create_results_display_tab(self):
        """Create tab for game results display preferences"""
        tab_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(tab_frame, text="📊 Game Results")
        
        # Scrollable content
        canvas = tk.Canvas(tab_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.parent.CONTENT_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Content with padding
        content_frame = ttk.Frame(scrollable_frame, style='Panel.TFrame', padding=15)
        content_frame.pack(fill='both', expand=True)
        
        # Default View Settings
        view_frame = ttk.LabelFrame(content_frame, text="Default View Settings", 
                                   style='PlayerPanel.TLabelframe', padding=15)
        view_frame.pack(fill='x', pady=(0, 15))
        
        # Show user team only by default
        self.user_team_only_var = tk.BooleanVar()
        user_team_check = tk.Checkbutton(view_frame, text="Show only my team's games by default", 
                                       variable=self.user_team_only_var,
                                       font=(self.parent.FONT_FAMILY, 10),
                                       fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                       selectcolor=self.parent.CONTENT_BG,
                                       command=self._mark_changed)
        user_team_check.pack(anchor='w', pady=2)
        
        # Default leagues
        league_subframe = tk.Frame(view_frame, bg=self.parent.CONTENT_BG)
        league_subframe.pack(fill='x', pady=(10, 0))
        
        tk.Label(league_subframe, text="Default leagues to display:", 
                font=(self.parent.FONT_FAMILY, 10, 'bold'),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(anchor='w')
        
        # League checkboxes
        self.league_vars = {}
        leagues = ['National Hockey League', 'American Hockey League', 'ECHL', 'CHL', 'NCAA', 'International']
        
        for i, league in enumerate(leagues):
            if i % 2 == 0:  # Two columns
                row_frame = tk.Frame(league_subframe, bg=self.parent.CONTENT_BG)
                row_frame.pack(fill='x', pady=2)
                
            var = tk.BooleanVar()
            self.league_vars[league] = var
            
            check = tk.Checkbutton(row_frame, text=league,
                                 variable=var,
                                 font=(self.parent.FONT_FAMILY, 9),
                                 fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                 selectcolor=self.parent.CONTENT_BG,
                                 command=self._mark_changed)
            check.pack(side='left', anchor='w', padx=(20, 100))
        
        # Performance Settings
        performance_frame = ttk.LabelFrame(content_frame, text="Performance & Display Limits", 
                                         style='PlayerPanel.TLabelframe', padding=15)
        performance_frame.pack(fill='x', pady=(0, 15))
        
        # Max games to display
        games_limit_frame = tk.Frame(performance_frame, bg=self.parent.CONTENT_BG)
        games_limit_frame.pack(fill='x', pady=2)
        
        tk.Label(games_limit_frame, text="Maximum games to display:", 
                font=(self.parent.FONT_FAMILY, 10),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left')
        
        self.max_games_var = tk.StringVar()
        games_values = ['25', '50', '100', '200', 'All']
        games_dropdown = ttk.Combobox(games_limit_frame, textvariable=self.max_games_var,
                                    values=games_values, state='readonly', width=8)
        games_dropdown.pack(side='left', padx=(10, 0))
        games_dropdown.bind('<<ComboboxSelected>>', self._mark_changed)
        
        tk.Label(games_limit_frame, text="(Recommended: 50 for performance)", 
                font=(self.parent.FONT_FAMILY, 8, 'italic'),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left', padx=(10, 0))
        
        # Max news items to display
        news_limit_frame = tk.Frame(performance_frame, bg=self.parent.CONTENT_BG)
        news_limit_frame.pack(fill='x', pady=(10, 2))
        
        tk.Label(news_limit_frame, text="Maximum news items to display:", 
                font=(self.parent.FONT_FAMILY, 10),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left')
        
        self.max_news_var = tk.StringVar()
        news_values = ['5', '10', '20', '50', 'All']
        news_dropdown = ttk.Combobox(news_limit_frame, textvariable=self.max_news_var,
                                   values=news_values, state='readonly', width=8)
        news_dropdown.pack(side='left', padx=(10, 0))
        news_dropdown.bind('<<ComboboxSelected>>', self._mark_changed)
        
        # News Category Settings
        news_frame = ttk.LabelFrame(content_frame, text="News Categories", 
                                   style='PlayerPanel.TLabelframe', padding=15)
        news_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(news_frame, text="Default news categories to display:", 
                font=(self.parent.FONT_FAMILY, 10, 'bold'),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(anchor='w', pady=(0, 5))
        
        # News category checkboxes
        self.news_category_vars = {}
        categories = ['Team News', 'League News', 'Trades', 'Injuries', 'Signings', 'Draft', 'Other']
        
        for i, category in enumerate(categories):
            if i % 2 == 0:  # Two columns
                row_frame = tk.Frame(news_frame, bg=self.parent.CONTENT_BG)
                row_frame.pack(fill='x', pady=2)
                
            var = tk.BooleanVar()
            self.news_category_vars[category] = var
            
            check = tk.Checkbutton(row_frame, text=category,
                                 variable=var,
                                 font=(self.parent.FONT_FAMILY, 9),
                                 fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                 selectcolor=self.parent.CONTENT_BG,
                                 command=self._mark_changed)
            check.pack(side='left', anchor='w', padx=(20, 80))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def _create_ui_preferences_tab(self):
        """Create tab for user interface preferences"""
        tab_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(tab_frame, text="🎨 Interface")
        
        # Content with padding
        content_frame = ttk.Frame(tab_frame, style='Panel.TFrame', padding=15)
        content_frame.pack(fill='both', expand=True)
        
        # Theme Settings
        theme_frame = ttk.LabelFrame(content_frame, text="Visual Theme", 
                                    style='PlayerPanel.TLabelframe', padding=15)
        theme_frame.pack(fill='x', pady=(0, 15))
        
        # Theme selection
        theme_row = tk.Frame(theme_frame, bg=self.parent.CONTENT_BG)
        theme_row.pack(fill='x', pady=2)
        
        tk.Label(theme_row, text="Theme:", 
                font=(self.parent.FONT_FAMILY, 10),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left')
        
        self.theme_var = tk.StringVar()
        theme_values = ['Dark (Current)', 'Light (Coming Soon)', 'High Contrast (Coming Soon)']
        theme_dropdown = ttk.Combobox(theme_row, textvariable=self.theme_var,
                                    values=theme_values, state='readonly', width=20)
        theme_dropdown.pack(side='left', padx=(10, 0))
        theme_dropdown.bind('<<ComboboxSelected>>', self._mark_changed)
        
        # Font size
        font_row = tk.Frame(theme_frame, bg=self.parent.CONTENT_BG)
        font_row.pack(fill='x', pady=(10, 2))
        
        tk.Label(font_row, text="Font size:", 
                font=(self.parent.FONT_FAMILY, 10),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left')
        
        self.font_size_var = tk.StringVar()
        font_values = ['Small', 'Medium (Current)', 'Large']
        font_dropdown = ttk.Combobox(font_row, textvariable=self.font_size_var,
                                   values=font_values, state='readonly', width=15)
        font_dropdown.pack(side='left', padx=(10, 0))
        font_dropdown.bind('<<ComboboxSelected>>', self._mark_changed)
        
        # Window Settings
        window_frame = ttk.LabelFrame(content_frame, text="Window Behavior", 
                                     style='PlayerPanel.TLabelframe', padding=15)
        window_frame.pack(fill='x', pady=(0, 15))
        
        # Auto-close settings window after save
        self.auto_close_var = tk.BooleanVar()
        auto_close_check = tk.Checkbutton(window_frame, text="Automatically close settings window after saving", 
                                        variable=self.auto_close_var,
                                        font=(self.parent.FONT_FAMILY, 10),
                                        fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                        selectcolor=self.parent.CONTENT_BG,
                                        command=self._mark_changed)
        auto_close_check.pack(anchor='w', pady=2)
        
        # Remember window positions
        self.remember_windows_var = tk.BooleanVar()
        remember_check = tk.Checkbutton(window_frame, text="Remember window positions and sizes", 
                                      variable=self.remember_windows_var,
                                      font=(self.parent.FONT_FAMILY, 10),
                                      fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                      selectcolor=self.parent.CONTENT_BG,
                                      command=self._mark_changed)
        remember_check.pack(anchor='w', pady=2)
        
    def _create_simulation_preferences_tab(self):
        """Create tab for game simulation preferences"""
        tab_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(tab_frame, text="🏒 Simulation")
        
        # Content with padding
        content_frame = ttk.Frame(tab_frame, style='Panel.TFrame', padding=15)
        content_frame.pack(fill='both', expand=True)
        
        # Simulation Speed
        speed_frame = ttk.LabelFrame(content_frame, text="Simulation Speed", 
                                    style='PlayerPanel.TLabelframe', padding=15)
        speed_frame.pack(fill='x', pady=(0, 15))
        
        speed_row = tk.Frame(speed_frame, bg=self.parent.CONTENT_BG)
        speed_row.pack(fill='x', pady=2)
        
        tk.Label(speed_row, text="Game simulation speed:", 
                font=(self.parent.FONT_FAMILY, 10),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left')
        
        self.sim_speed_var = tk.StringVar()
        speed_values = ['Very Fast', 'Fast (Current)', 'Normal', 'Detailed']
        speed_dropdown = ttk.Combobox(speed_row, textvariable=self.sim_speed_var,
                                    values=speed_values, state='readonly', width=15)
        speed_dropdown.pack(side='left', padx=(10, 0))
        speed_dropdown.bind('<<ComboboxSelected>>', self._mark_changed)
        
        # Auto-continue options
        auto_frame = ttk.LabelFrame(content_frame, text="Auto-Continue Settings", 
                                   style='PlayerPanel.TLabelframe', padding=15)
        auto_frame.pack(fill='x', pady=(0, 15))
        
        # Auto-continue through days
        self.auto_continue_var = tk.BooleanVar()
        auto_continue_check = tk.Checkbutton(auto_frame, text="Auto-continue through non-game days", 
                                           variable=self.auto_continue_var,
                                           font=(self.parent.FONT_FAMILY, 10),
                                           fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                           selectcolor=self.parent.CONTENT_BG,
                                           command=self._mark_changed)
        auto_continue_check.pack(anchor='w', pady=2)
        
        # Show daily results
        self.show_daily_results_var = tk.BooleanVar()
        daily_results_check = tk.Checkbutton(auto_frame, text="Always show daily results window", 
                                            variable=self.show_daily_results_var,
                                            font=(self.parent.FONT_FAMILY, 10),
                                            fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                            selectcolor=self.parent.CONTENT_BG,
                                            command=self._mark_changed)
        daily_results_check.pack(anchor='w', pady=2)
        
        # Game Viewer Settings
        viewer_frame = ttk.LabelFrame(content_frame, text="Game Viewer", 
                                     style='PlayerPanel.TLabelframe', padding=15)
        viewer_frame.pack(fill='x', pady=(0, 15))
        
        # Use game viewer for user team games
        self.use_game_viewer_var = tk.BooleanVar()
        game_viewer_check = tk.Checkbutton(viewer_frame, text="Use visual game viewer for my team's games", 
                                          variable=self.use_game_viewer_var,
                                          font=(self.parent.FONT_FAMILY, 10),
                                          fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                          selectcolor=self.parent.CONTENT_BG,
                                          command=self._mark_changed)
        game_viewer_check.pack(anchor='w', pady=2)
        
        # Game viewer mode
        viewer_mode_row = tk.Frame(viewer_frame, bg=self.parent.CONTENT_BG)
        viewer_mode_row.pack(fill='x', pady=(10, 2))
        
        tk.Label(viewer_mode_row, text="Game viewer mode:", 
                font=(self.parent.FONT_FAMILY, 10),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left')
        
        self.game_viewer_mode_var = tk.StringVar()
        viewer_mode_values = ['Full Game', 'Highlights Only', 'Fast Forward']
        viewer_mode_dropdown = ttk.Combobox(viewer_mode_row, textvariable=self.game_viewer_mode_var,
                                          values=viewer_mode_values, state='readonly', width=15)
        viewer_mode_dropdown.pack(side='left', padx=(10, 0))
        viewer_mode_dropdown.bind('<<ComboboxSelected>>', self._mark_changed)
        
    def _create_notifications_tab(self):
        """Create tab for notification preferences"""
        tab_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(tab_frame, text="🔔 Notifications")
        
        # Content with padding
        content_frame = ttk.Frame(tab_frame, style='Panel.TFrame', padding=15)
        content_frame.pack(fill='both', expand=True)
        
        # Email notifications
        email_frame = ttk.LabelFrame(content_frame, text="Email Notifications", 
                                    style='PlayerPanel.TLabelframe', padding=15)
        email_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(email_frame, text="Receive email notifications for:", 
                font=(self.parent.FONT_FAMILY, 10, 'bold'),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(anchor='w', pady=(0, 5))
        
        # Notification type checkboxes
        self.email_notification_vars = {}
        email_types = ['Trade Offers', 'Contract Expiring Soon', 'Injury Reports', 
                      'Player Milestones', 'League News', 'Draft Updates']
        
        for email_type in email_types:
            var = tk.BooleanVar()
            self.email_notification_vars[email_type] = var
            
            check = tk.Checkbutton(email_frame, text=email_type,
                                 variable=var,
                                 font=(self.parent.FONT_FAMILY, 9),
                                 fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                 selectcolor=self.parent.CONTENT_BG,
                                 command=self._mark_changed)
            check.pack(anchor='w', pady=2, padx=(20, 0))
        
        # Sound notifications
        sound_frame = ttk.LabelFrame(content_frame, text="Sound Notifications", 
                                    style='PlayerPanel.TLabelframe', padding=15)
        sound_frame.pack(fill='x', pady=(0, 15))
        
        # Enable sounds
        self.enable_sounds_var = tk.BooleanVar()
        sounds_check = tk.Checkbutton(sound_frame, text="Enable sound effects", 
                                    variable=self.enable_sounds_var,
                                    font=(self.parent.FONT_FAMILY, 10),
                                    fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG,
                                    selectcolor=self.parent.CONTENT_BG,
                                    command=self._mark_changed)
        sounds_check.pack(anchor='w', pady=2)
        
        # Sound volume
        volume_row = tk.Frame(sound_frame, bg=self.parent.CONTENT_BG)
        volume_row.pack(fill='x', pady=(10, 2))
        
        tk.Label(volume_row, text="Sound volume:", 
                font=(self.parent.FONT_FAMILY, 10),
                fg=self.parent.TEXT_COLOR, bg=self.parent.CONTENT_BG).pack(side='left')
        
        self.sound_volume_var = tk.StringVar()
        volume_values = ['Off', 'Low', 'Medium', 'High']
        volume_dropdown = ttk.Combobox(volume_row, textvariable=self.sound_volume_var,
                                     values=volume_values, state='readonly', width=10)
        volume_dropdown.pack(side='left', padx=(10, 0))
        volume_dropdown.bind('<<ComboboxSelected>>', self._mark_changed)
        
    def _create_footer(self, parent):
        """Create the footer with action buttons"""
        footer_frame = ttk.Frame(parent, style='Panel.TFrame')
        footer_frame.pack(fill='x')
        
        # Left side - Reset to defaults
        reset_btn = tk.Button(footer_frame, text="Reset to Defaults", 
                            font=(self.parent.FONT_FAMILY, 10),
                            bg=self.parent.CONTENT_BG, 
                            fg=self.parent.TEXT_COLOR,
                            activebackground=self.parent.ACCENT_HOVER,
                            relief='flat', cursor='hand2',
                            command=self._reset_to_defaults)
        reset_btn.pack(side='left', pady=10)
        
        # Right side - action buttons
        button_frame = tk.Frame(footer_frame, bg=self.parent.BG_COLOR)
        button_frame.pack(side='right', pady=10)
        
        # Cancel button
        cancel_btn = tk.Button(button_frame, text="Cancel", 
                             font=(self.parent.FONT_FAMILY, 10),
                             bg=self.parent.CONTENT_BG, 
                             fg=self.parent.TEXT_COLOR,
                             activebackground=self.parent.ACCENT_HOVER,
                             relief='flat', cursor='hand2',
                             command=self._cancel)
        cancel_btn.pack(side='left', padx=(0, 10))
        
        # Apply button
        apply_btn = tk.Button(button_frame, text="Apply", 
                            font=(self.parent.FONT_FAMILY, 10),
                            bg=self.parent.CONTENT_BG, 
                            fg=self.parent.TEXT_COLOR,
                            activebackground=self.parent.ACCENT_HOVER,
                            relief='flat', cursor='hand2',
                            command=self._apply_settings)
        apply_btn.pack(side='left', padx=(0, 10))
        
        # Save button
        save_btn = tk.Button(button_frame, text="Save", 
                           font=(self.parent.FONT_FAMILY, 11, 'bold'),
                           bg=self.parent.ACCENT_COLOR, 
                           fg=self.parent.HEADER_COLOR,
                           activebackground=self.parent.ACCENT_HOVER,
                           relief='flat', cursor='hand2',
                           command=self._save_settings)
        save_btn.pack(side='left')
        
    def _load_settings(self):
        """Load settings from file or create defaults"""
        settings_file = os.path.join(os.path.dirname(__file__), 'settings.json')
        
        # Default settings
        defaults = {
            'game_results': {
                'show_user_team_only': True,
                'default_leagues': ['National Hockey League'],
                'max_games_display': '50',
                'max_news_display': '10',
                'default_news_categories': ['Team News', 'League News', 'Trades', 'Injuries']
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
                'game_viewer_mode': 'Full Game'
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
                if isinstance(value, dict) and isinstance(defaults[key], dict):
                    self._merge_settings(defaults[key], value)
                else:
                    defaults[key] = value
                    
    def _load_current_values(self):
        """Load current values into the UI"""
        # Game Results settings
        game_results = self.settings.get('game_results', {})
        
        self.user_team_only_var.set(game_results.get('show_user_team_only', True))
        
        default_leagues = game_results.get('default_leagues', ['National Hockey League'])
        for league, var in self.league_vars.items():
            var.set(league in default_leagues)
            
        self.max_games_var.set(game_results.get('max_games_display', '50'))
        self.max_news_var.set(game_results.get('max_news_display', '10'))
        
        default_news_cats = game_results.get('default_news_categories', ['Team News', 'League News', 'Trades', 'Injuries'])
        for category, var in self.news_category_vars.items():
            var.set(category in default_news_cats)
        
        # UI Preferences
        ui_prefs = self.settings.get('ui_preferences', {})
        
        self.theme_var.set(ui_prefs.get('theme', 'Dark (Current)'))
        self.font_size_var.set(ui_prefs.get('font_size', 'Medium (Current)'))
        self.auto_close_var.set(ui_prefs.get('auto_close_settings', False))
        self.remember_windows_var.set(ui_prefs.get('remember_window_positions', True))
        
        # Simulation
        simulation = self.settings.get('simulation', {})
        
        self.sim_speed_var.set(simulation.get('simulation_speed', 'Fast (Current)'))
        self.auto_continue_var.set(simulation.get('auto_continue_non_game_days', False))
        self.show_daily_results_var.set(simulation.get('always_show_daily_results', True))
        self.use_game_viewer_var.set(simulation.get('use_game_viewer', False))
        self.game_viewer_mode_var.set(simulation.get('game_viewer_mode', 'Full Game'))
        
        # Notifications
        notifications = self.settings.get('notifications', {})
        
        email_notifications = notifications.get('email_notifications', {})
        for email_type, var in self.email_notification_vars.items():
            var.set(email_notifications.get(email_type, False))
            
        self.enable_sounds_var.set(notifications.get('enable_sounds', True))
        self.sound_volume_var.set(notifications.get('sound_volume', 'Medium'))
        
    def _mark_changed(self, event=None):
        """Mark that settings have been changed"""
        # Visual indicator that changes are pending
        self.title("Settings - Hockey Manager *")
        
    def _reset_to_defaults(self):
        """Reset all settings to defaults"""
        result = tk.messagebox.askyesno("Reset Settings", 
                                       "Are you sure you want to reset all settings to defaults?\n\nThis cannot be undone.",
                                       parent=self)
        if result:
            # Load default settings and update UI
            self.settings = self._load_settings()  # This loads defaults when no file exists
            self._load_current_values()
            self._mark_changed()
            
    def _apply_settings(self):
        """Apply settings without saving to file"""
        self._collect_current_values()
        self._notify_parent_of_changes()
        tk.messagebox.showinfo("Settings Applied", "Settings have been applied for this session.", parent=self)
        
    def _save_settings(self):
        """Save settings to file and apply them"""
        self._collect_current_values()
        
        # Save to file
        settings_file = os.path.join(os.path.dirname(__file__), 'settings.json')
        try:
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
                
            self._notify_parent_of_changes()
            
            # Show success message
            tk.messagebox.showinfo("Settings Saved", "Settings have been saved successfully.", parent=self)
            
            # Auto-close if enabled
            if self.auto_close_var.get():
                self.destroy()
            else:
                self.title("Settings - Hockey Manager")  # Remove * indicator
                
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to save settings:\n{e}", parent=self)
            
    def _collect_current_values(self):
        """Collect current values from UI and update settings"""
        # Game Results
        self.settings['game_results'] = {
            'show_user_team_only': self.user_team_only_var.get(),
            'default_leagues': [league for league, var in self.league_vars.items() if var.get()],
            'max_games_display': self.max_games_var.get(),
            'max_news_display': self.max_news_var.get(),
            'default_news_categories': [cat for cat, var in self.news_category_vars.items() if var.get()]
        }
        
        # UI Preferences
        self.settings['ui_preferences'] = {
            'theme': self.theme_var.get(),
            'font_size': self.font_size_var.get(),
            'auto_close_settings': self.auto_close_var.get(),
            'remember_window_positions': self.remember_windows_var.get()
        }
        
        # Simulation
        self.settings['simulation'] = {
            'simulation_speed': self.sim_speed_var.get(),
            'auto_continue_non_game_days': self.auto_continue_var.get(),
            'always_show_daily_results': self.show_daily_results_var.get(),
            'use_game_viewer': self.use_game_viewer_var.get(),
            'game_viewer_mode': self.game_viewer_mode_var.get()
        }
        
        # Notifications
        self.settings['notifications'] = {
            'email_notifications': {email_type: var.get() for email_type, var in self.email_notification_vars.items()},
            'enable_sounds': self.enable_sounds_var.get(),
            'sound_volume': self.sound_volume_var.get()
        }
        
    def _notify_parent_of_changes(self):
        """Notify parent of setting changes"""
        if hasattr(self.parent, 'apply_settings'):
            self.parent.apply_settings(self.settings)
            
    def _cancel(self):
        """Cancel changes and close window"""
        if self.title().endswith('*'):  # Check if there are unsaved changes
            result = tk.messagebox.askyesnocancel("Unsaved Changes", 
                                                 "You have unsaved changes. Do you want to save before closing?",
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
        if hasattr(self.parent, 'open_windows') and 'settings' in self.parent.open_windows:
            del self.parent.open_windows['settings']
        super().destroy()
