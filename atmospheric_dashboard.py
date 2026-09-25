# atmospheric_dashboard.py
# Immersive, story-driven dashboard with visual hierarchy and team personality

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta, datetime
from typing import Dict, List, Optional
import random
from visual_identity_system import (
    HockeyAtmosphereSystem, VisualHierarchyManager, 
    AnimationManager, ContextualElementsManager, 
    StorytellingDataPresentation
)
from modern_widgets import RoundedButton

class AtmosphericDashboard:
    """Immersive dashboard that makes you feel like a real GM"""
    
    def __init__(self, parent, game_manager, user_team):
        self.parent = parent
        self.game_manager = game_manager
        self.user_team = user_team
        
        # Initialize visual systems
        self.atmosphere_system = HockeyAtmosphereSystem()
        self.theme = self.atmosphere_system.create_atmospheric_theme(user_team.team_name)
        
        # QUICK FIX: Override theme colors with dark theme to fix white UI issue
        # Store original colors for reference
        self.original_colors = self.theme.colors
        
        # Override with dark colors similar to main UI theme
        self.theme.colors.background = '#0F1419'        # Dark navy
        self.theme.colors.arena_shadow = '#0F1419'      # Same as background
        self.theme.colors.secondary = '#1B2332'         # Lighter panel background
        self.theme.colors.ice_blue = '#2E7BD6'          # Blue accent
        self.theme.colors.text_light = '#B8C5D6'        # Light text color
        
        # Keep team-specific primary color but ensure it's not white
        if hasattr(self.theme.colors, 'primary') and self.theme.colors.primary in ['#FFFFFF', '#ffffff', 'white']:
            self.theme.colors.primary = '#DC3545'  # Default red if primary is white
        
        self.hierarchy_manager = VisualHierarchyManager(self.theme)
        self.animation_manager = AnimationManager(parent)
        self.contextual_manager = ContextualElementsManager(self.theme)
        self.storytelling_manager = StorytellingDataPresentation(self.theme)
        
        # Dashboard state
        self.widgets = {}
        self.animated_elements = []
        
        # Widget references for refreshing
        self.widget_refs = {}
        
    def create_immersive_dashboard(self, container):
        """Create the main immersive dashboard experience"""
        # Store container reference for refresh functionality
        self.container = container
        
        # Clear any existing content
        for widget in container.winfo_children():
            widget.destroy()
        
        # Main container with atmospheric background
        main_frame = tk.Frame(container, bg=self.theme.colors.arena_shadow)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Configure grid for responsive layout
        main_frame.grid_rowconfigure(0, weight=0)  # Arena atmosphere bar
        main_frame.grid_rowconfigure(1, weight=0)  # Hero section
        main_frame.grid_rowconfigure(2, weight=1)  # Main content
        main_frame.grid_rowconfigure(3, weight=0)  # Action bar
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Create atmospheric sections
        self._create_arena_atmosphere_bar(main_frame)
        self._create_hero_command_center(main_frame)
        self._create_storytelling_content_grid(main_frame)
        self._create_gm_action_center(main_frame)
        
        # Start atmospheric animations
        self._start_ambient_animations()
        
        return main_frame
    
    def _create_arena_atmosphere_bar(self, parent):
        """Create atmospheric arena elements at the top"""
        atmosphere_frame = tk.Frame(parent, bg=self.theme.colors.ice_blue, height=6)
        atmosphere_frame.grid(row=0, column=0, sticky='ew', padx=0, pady=0)
        atmosphere_frame.grid_propagate(False)
        
        # Ice effect with team color accent
        team_accent = tk.Frame(atmosphere_frame, bg=self.theme.colors.primary, height=2)
        team_accent.pack(fill='x', side='bottom')
        
        # Store for animations
        self.widgets['atmosphere_bar'] = atmosphere_frame
        
    def _create_hero_command_center(self, parent):
        """Create GM command center with team identity and key controls"""
        hero_frame = tk.Frame(parent, bg=self.theme.colors.background, 
                             relief='flat', bd=0, padx=20, pady=16)
        hero_frame.grid(row=1, column=0, sticky='ew', padx=12, pady=8)
        
        # Configure hero grid
        hero_frame.grid_columnconfigure(0, weight=0)  # Team identity
        hero_frame.grid_columnconfigure(1, weight=1)  # Command center
        hero_frame.grid_columnconfigure(2, weight=0)  # Action panel
        
        # Team identity section (left)
        self._create_team_identity_section(hero_frame)
        
        # GM command center (middle)
        self._create_command_center_section(hero_frame)
        
        # Action panel (right)
        self._create_action_panel_section(hero_frame)
        
        self.widgets['hero_frame'] = hero_frame
        
    def _create_team_identity_section(self, parent):
        """Create team identity with logo, colors, and personality"""
        identity_frame = tk.Frame(parent, bg=self.theme.colors.background)
        identity_frame.grid(row=0, column=0, sticky='nw', padx=(0, 24))
        
        # Team logo with atmosphere
        logo_container = tk.Frame(identity_frame, bg=self.theme.colors.primary,
                                 width=72, height=72, relief='flat', bd=2)
        logo_container.pack(pady=(0, 12))
        logo_container.pack_propagate(False)
        
        # Team initials in logo
        initials = self._get_team_initials()
        logo_label = tk.Label(logo_container, text=initials,
                             font=self.theme.fonts['logo'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.primary)
        logo_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Team name with personality
        team_name_label = tk.Label(identity_frame, text=self.user_team.team_name,
                                  font=self.theme.fonts['title'],
                                  fg=self.theme.colors.primary,
                                  bg=self.theme.colors.background)
        team_name_label.pack(anchor='w')
        
        # Team motto/personality
        motto = self._get_team_motto()
        motto_label = tk.Label(identity_frame, text=motto,
                              font=('Segoe UI', 9, 'italic'),
                              fg=self.theme.colors.text_light,
                              bg=self.theme.colors.background)
        motto_label.pack(anchor='w', pady=(2, 0))
        
        # Team mood indicator
        mood_frame = self.contextual_manager.create_mood_indicator(
            identity_frame, self._get_team_mood()
        )
        mood_frame.pack(anchor='w', pady=(8, 0))
        
        self.widgets['team_identity'] = identity_frame
        self.animated_elements.append(logo_label)  # For pulse effect
        
    def _create_command_center_section(self, parent):
        """Create GM command center with key metrics and storytelling"""
        command_frame = tk.Frame(parent, bg=self.theme.colors.background)
        command_frame.grid(row=0, column=1, sticky='ew', padx=20)
        
        # Command center title
        title_label = tk.Label(command_frame, text="General Manager Command Center",
                              font=self.theme.fonts['heading'],
                              fg=self.theme.colors.text_light,
                              bg=self.theme.colors.background)
        title_label.pack(anchor='w', pady=(0, 16))
        
        # Key metrics grid with visual hierarchy
        metrics_container = tk.Frame(command_frame, bg=self.theme.colors.background)
        metrics_container.pack(fill='x', pady=(0, 16))
        
        # Configure metrics grid
        for i in range(4):
            metrics_container.grid_columnconfigure(i, weight=1)
        
        # Create metric cards with storytelling
        metrics = self._get_storytelling_metrics()
        for i, metric in enumerate(metrics):
            metric_card = self._create_metric_card(metrics_container, metric, i)
            metric_card.grid(row=0, column=i, sticky='ew', padx=6)
        
        # Current situation narrative
        situation_frame = tk.Frame(command_frame, bg=self.theme.colors.secondary,
                                  relief='flat', bd=1)
        situation_frame.pack(fill='x', pady=(8, 0))
        
        situation_title = tk.Label(situation_frame, text="🎯 Current Situation",
                                  font=self.theme.fonts['subheading'],
                                  fg=self.theme.colors.primary,
                                  bg=self.theme.colors.secondary)
        situation_title.pack(anchor='w', padx=16, pady=(12, 4))
        
        situation_text = self._generate_situation_narrative()
        situation_label = tk.Label(situation_frame, text=situation_text,
                                  font=self.theme.fonts['body'],
                                  fg=self.theme.colors.text_light,
                                  bg=self.theme.colors.secondary,
                                  wraplength=500, justify='left')
        situation_label.pack(anchor='w', padx=16, pady=(0, 12))
        
        self.widgets['command_center'] = command_frame
        
    def _create_action_panel_section(self, parent):
        """Create action panel with continue button and quick actions"""
        action_frame = tk.Frame(parent, bg=self.theme.colors.background)
        action_frame.grid(row=0, column=2, sticky='ne', padx=(24, 0))
        
        # Current date with atmosphere
        date_container = tk.Frame(action_frame, bg=self.theme.colors.secondary,
                                 relief='flat', bd=1, padx=16, pady=12)
        date_container.pack(pady=(0, 16))
        
        current_date = getattr(self.game_manager, 'current_date', date.today())
        date_str = current_date.strftime("%B %d, %Y")
        day_str = current_date.strftime("%A")
        
        self.date_label = tk.Label(date_container, text=date_str,
                             font=self.theme.fonts['subheading'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.secondary)
        self.date_label.pack()
        
        self.day_label = tk.Label(date_container, text=day_str,
                            font=self.theme.fonts['caption'],
                            fg=self.theme.colors.primary,
                            bg=self.theme.colors.secondary)
        self.day_label.pack()
        
        # Primary action button (Continue Day) with atmosphere
        continue_btn = tk.Button(action_frame, text="Continue Day",
                               font=self.theme.fonts['subheading'],
                               bg=self.theme.colors.primary,
                               fg=self.theme.colors.text_light,
                               activebackground=self.theme.colors.success,
                               activeforeground=self.theme.colors.text_light,
                               relief='flat', bd=0, highlightthickness=0,
                               padx=24, pady=12,
                               cursor='hand2',
                               command=self._continue_day_action)
        continue_btn.pack(pady=(0, 12))

        # Add hover effects
        self._add_button_hover_effects(continue_btn)
        # Gentle "alive" pulse on the primary action
        self._pulse_continue_button(continue_btn)
        
        # Quick actions menu
        quick_actions_label = tk.Label(action_frame, text="Quick Actions",
                                      font=self.theme.fonts['caption'],
                                      fg=self.theme.colors.text_light,
                                      bg=self.theme.colors.background)
        quick_actions_label.pack(anchor='w', pady=(8, 4))
        
        quick_actions = [
            ("Team Stats", self._quick_stats_action),
            ("Roster", self._quick_roster_action),
            ("Standings", self._quick_standings_action),
        ]

        for action_text, action_command in quick_actions:
            action_btn = RoundedButton(action_frame, text=action_text,
                                       command=action_command,
                                       font=self.theme.fonts['body'],
                                       bg=self.theme.colors.secondary,
                                       fg=self.theme.colors.text_light,
                                       radius=9, padx=16, pady=8,
                                       width=170)
            action_btn.pack(pady=3)
        
        self.widgets['action_panel'] = action_frame
        self.widgets['continue_btn'] = continue_btn
        
    def _create_storytelling_content_grid(self, parent):
        """Create main content grid with storytelling approach"""
        content_frame = tk.Frame(parent, bg=self.theme.colors.background)
        content_frame.grid(row=2, column=0, sticky='nsew', padx=12, pady=8)
        
        # Configure responsive grid
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=2)  # Main story area
        content_frame.grid_columnconfigure(1, weight=1)  # Sidebar
        
        # Main story area
        story_area = self._create_main_story_area(content_frame)
        story_area.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        
        # Information sidebar
        sidebar = self._create_information_sidebar(content_frame)
        sidebar.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        
        self.widgets['content_frame'] = content_frame
        
    def _create_main_story_area(self, parent):
        """Create main story area with narrative focus"""
        story_frame = tk.Frame(parent, bg=self.theme.colors.background)
        
        # Story navigation
        nav_frame = tk.Frame(story_frame, bg=self.theme.colors.secondary, height=48)
        nav_frame.pack(fill='x', pady=(0, 12))
        nav_frame.pack_propagate(False)
        
        story_tabs = ["Team Performance", "Recent Events", "Priorities", "League Pulse", "Standings", "Stat Leaders"]
        self.active_tab = 0  # Track active tab
        self.tab_buttons = []  # Store tab buttons for styling updates
        self.tab_indicators = []

        for i, tab_text in enumerate(story_tabs):
            tab_wrap = tk.Frame(nav_frame, bg=self.theme.colors.secondary)
            tab_wrap.pack(side='left', padx=6)
            tab_btn = tk.Button(tab_wrap, text=tab_text,
                               font=self.theme.fonts['body'],
                               bg=self.theme.colors.secondary,
                               fg='#ffffff' if i == 0 else '#8b98ac',
                               relief='flat', bd=0, highlightthickness=0,
                               padx=10, pady=10,
                               cursor='hand2',
                               command=lambda idx=i: self._switch_tab(idx))
            tab_btn.pack()
            indicator = tk.Frame(tab_wrap, height=2,
                                 bg=self.theme.colors.primary if i == 0 else self.theme.colors.secondary)
            indicator.pack(fill='x')
            self._add_button_hover_effects(tab_btn, subtle=True)
            self.tab_buttons.append(tab_btn)
            self.tab_indicators.append(indicator)
        
        # Story content area
        self.story_content = tk.Frame(story_frame, bg=self.theme.colors.background)
        self.story_content.pack(fill='both', expand=True)
        
        # Create initial narrative content
        self._create_performance_narrative(self.story_content)
        
        return story_frame
        
    def _switch_tab(self, tab_index):
        """Switch between different tabs in the story section"""
        # Update active tab
        self.active_tab = tab_index
        
        # Update button styles: active tab gets white text + red underline
        for i, btn in enumerate(self.tab_buttons):
            active = (i == tab_index)
            btn.configure(fg='#ffffff' if active else '#8b98ac')
            if i < len(self.tab_indicators):
                self.tab_indicators[i].configure(
                    bg=self.theme.colors.primary if active else self.theme.colors.secondary)
        
        # Clear current content
        for widget in self.story_content.winfo_children():
            widget.destroy()
        
        # Load appropriate content based on tab
        if tab_index == 0:  # Team Performance
            self._create_performance_narrative(self.story_content)
        elif tab_index == 1:  # Recent Events
            self._create_recent_events_tab(self.story_content)
        elif tab_index == 2:  # Priorities
            self._create_priorities_tab(self.story_content)
        elif tab_index == 3:  # League Pulse
            self._create_league_pulse_tab(self.story_content)
        elif tab_index == 4:  # Standings
            self._create_standings_tab(self.story_content)
        elif tab_index == 5:  # Stat Leaders
            self._create_stat_leaders_tab(self.story_content)
        
    def _create_information_sidebar(self, parent):
        """Create information sidebar with enhanced inbox and quick info"""
        sidebar_frame = tk.Frame(parent, bg=self.theme.colors.background)
        
        # Enhanced inbox section
        inbox_card, inbox_content = self.hierarchy_manager.create_card_with_hierarchy(
            sidebar_frame, "📬 GM Inbox", "inbox"
        )
        inbox_card.pack(fill='x', pady=(0, 12))
        
        # Inbox content with visual hierarchy
        self._create_enhanced_inbox_content(inbox_content)
        
        # Enhanced Next Game card with interactivity
        next_game_card, next_game_content = self.hierarchy_manager.create_card_with_hierarchy(
            sidebar_frame, "🏒 Next Game", "info"
        )
        next_game_card.pack(fill='x', pady=(0, 8))
        self._create_enhanced_next_game_widget(next_game_content)
        
        # Other Quick information cards
        info_cards = [
            ("🏆 Standings", self._get_quick_standings_info()),
            ("💰 Cap Space", self._get_cap_space_info()),
            ("🏥 Injuries", self._get_injury_info()),
            ("📈 Trending", self._get_trending_info())
        ]
        
        for card_title, card_info in info_cards:
            info_card, info_content = self.hierarchy_manager.create_card_with_hierarchy(
                sidebar_frame, card_title, "info"
            )
            info_card.pack(fill='x', pady=(0, 8))
            
            info_label = tk.Label(info_content, text=card_info,
                                 font=self.theme.fonts['body'],
                                 fg=self.theme.colors.text_light,
                                 bg=self.theme.colors.secondary,
                                 wraplength=200, justify='left')
            info_label.pack(anchor='w')
        
        return sidebar_frame
        
    def _create_gm_action_center(self, parent):
        """Create bottom action center with atmospheric elements"""
        action_center = tk.Frame(parent, bg=self.theme.colors.arena_shadow, height=60)
        action_center.grid(row=3, column=0, sticky='ew', padx=0, pady=0)
        action_center.grid_propagate(False)
        
        # Ice effect
        ice_line = tk.Frame(action_center, bg=self.theme.colors.ice_blue, height=2)
        ice_line.pack(fill='x', side='top')
        
        # Action content
        content_frame = tk.Frame(action_center, bg=self.theme.colors.arena_shadow)
        content_frame.pack(fill='both', expand=True, padx=20, pady=8)
        
        # Status indicators
        status_text = self._get_gm_status_text()
        status_label = tk.Label(content_frame, text=status_text,
                               font=self.theme.fonts['caption'],
                               fg=self.theme.colors.text_light,
                               bg=self.theme.colors.arena_shadow)
        status_label.pack(side='left')
        
        # Right side indicators
        indicators_frame = tk.Frame(content_frame, bg=self.theme.colors.arena_shadow)
        indicators_frame.pack(side='right')
        
        # Team record
        record = self._get_team_record()
        record_label = tk.Label(indicators_frame, text=f"Record: {record}",
                               font=self.theme.fonts['body'],
                               fg=self.theme.colors.primary,
                               bg=self.theme.colors.arena_shadow)
        record_label.pack(side='right', padx=(0, 20))
        
        self.widgets['action_center'] = action_center
    
    # Helper methods for content generation
    def _get_team_initials(self) -> str:
        """Get team initials for logo"""
        words = self.user_team.team_name.split()
        if len(words) >= 2:
            return f"{words[-2][0]}{words[-1][0]}"
        return self.user_team.team_name[:2].upper()
    
    def _get_team_motto(self) -> str:
        """Get team motto based on team name"""
        mottos = {
            "Boston Bruins": "Strength through tradition",
            "Montreal Canadiens": "Excellence and honor",
            "Toronto Maple Leafs": "Blue and white pride",
            "Tampa Bay Lightning": "Strike fast, strike hard",
            "Pittsburgh Penguins": "Championship mentality",
            "Chicago Blackhawks": "Legacy of champions"
        }
        return mottos.get(self.user_team.team_name, "Pursuit of excellence")
    
    def _get_team_mood(self) -> str:
        """Determine team mood based on recent performance"""
        # This would normally be calculated from actual game data
        moods = ["excellent", "good", "neutral", "poor"]
        return random.choice(moods)
    
    def _get_storytelling_metrics(self) -> List[Dict]:
        """Get metrics with storytelling context"""
        try:
            # Get team record
            user_team = getattr(self.parent, 'user_team', None)
            wins = getattr(user_team, 'wins', 0)
            losses = getattr(user_team, 'losses', 0)
            ot_losses = getattr(user_team, 'ot_losses', 0)
            total_games = wins + losses + ot_losses
            
            # Calculate win percentage for context
            if total_games > 0:
                win_pct = wins / total_games
                if win_pct >= 0.6:
                    wins_context = "positive"
                    wins_subtitle = "Strong performance"
                    wins_trend = "↗"
                elif win_pct >= 0.4:
                    wins_context = "neutral"
                    wins_subtitle = "Building momentum"
                    wins_trend = "→"
                else:
                    wins_context = "negative"
                    wins_subtitle = "Room to improve"
                    wins_trend = "↘"
            else:
                wins_context = "neutral"
                wins_subtitle = "Season starting"
                wins_trend = "→"
            
            # Calculate salary cap space
            total_cap = 88000000  # NHL salary cap
            used_cap = 0
            roster_spots_used = 0
            max_roster = 23
            
            if user_team and hasattr(user_team, 'roster'):
                for player in user_team.roster:
                    if hasattr(player, 'contract') and player.contract:
                        used_cap += getattr(player.contract, 'salary', 750000)
                    else:
                        used_cap += 750000  # League minimum
                    roster_spots_used += 1
            
            cap_space = total_cap - used_cap
            roster_spots_open = max_roster - roster_spots_used
            
            if cap_space > 10000000:
                cap_context = "positive"
                cap_subtitle = "Plenty of room"
                cap_trend = "↗"
            elif cap_space > 3000000:
                cap_context = "neutral"
                cap_subtitle = "Manageable space"
                cap_trend = "→"
            else:
                cap_context = "negative"
                cap_subtitle = "Tight budget"
                cap_trend = "↘"
            
            # Get top scorer
            top_scorer_name = "Unknown"
            top_scorer_points = 0
            if user_team and hasattr(user_team, 'roster'):
                for player in user_team.roster:
                    player_points = getattr(player, 'goals', 0) + getattr(player, 'assists', 0)
                    if player_points > top_scorer_points:
                        top_scorer_points = player_points
                        top_scorer_name = getattr(player, 'full_name', 'Unknown')
            
            # Get team goals per game
            goals_for = getattr(user_team, 'goals_for', 0) if user_team else 0
            if total_games > 0:
                goals_per_game = goals_for / total_games
                goals_value = f"{goals_per_game:.1f}/game"
                if goals_per_game >= 3.5:
                    goals_context = "positive"
                    goals_subtitle = "High-powered offense"
                    goals_trend = "↗"
                elif goals_per_game >= 2.5:
                    goals_context = "neutral"
                    goals_subtitle = "Solid production"
                    goals_trend = "→"
                else:
                    goals_context = "negative"
                    goals_subtitle = "Need more scoring"
                    goals_trend = "↘"
            else:
                goals_value = "0.0/game"
                goals_context = "neutral"
                goals_subtitle = "Season starting"
                goals_trend = "→"
            
            return [
                {
                    "icon": "🏆",
                    "title": "Wins",
                    "value": str(wins),
                    "subtitle": wins_subtitle,
                    "context": wins_context,
                    "trend": wins_trend
                },
                {
                    "icon": "💰",
                    "title": "Cap Space",
                    "value": f"${cap_space/1000000:.1f}M",
                    "subtitle": cap_subtitle,
                    "context": cap_context,
                    "trend": cap_trend
                },
                {
                    "icon": "⭐",
                    "title": "Top Scorer",
                    "value": f"{top_scorer_points} pts",
                    "subtitle": top_scorer_name.split()[-1] if top_scorer_name != "Unknown" else "No stats yet",
                    "context": "positive" if top_scorer_points > 0 else "neutral",
                    "trend": "↗" if top_scorer_points > 0 else "→"
                },
                {
                    "icon": "🥅",
                    "title": "Goals For",
                    "value": goals_value,
                    "subtitle": goals_subtitle,
                    "context": goals_context,
                    "trend": goals_trend
                }
            ]
        except Exception as e:
            # Fallback to basic metrics if something goes wrong
            return [
                {"icon": "🏆", "title": "Wins", "value": "0", "subtitle": "Season starting", "context": "neutral", "trend": "→"},
                {"icon": "💰", "title": "Cap Space", "value": "Loading...", "subtitle": "Calculating", "context": "neutral", "trend": "→"},
                {"icon": "⭐", "title": "Top Scorer", "value": "0 pts", "subtitle": "No stats yet", "context": "neutral", "trend": "→"},
                {"icon": "🥅", "title": "Goals For", "value": "0.0/game", "subtitle": "Season starting", "context": "neutral", "trend": "→"}
            ]
    
    def _create_metric_card(self, parent, metric: Dict, index: int) -> tk.Frame:
        """Create individual metric card with storytelling"""
        accent = self._get_context_color(metric.get("context", "neutral"))
        card = tk.Frame(parent, bg=self.theme.colors.secondary,
                       relief='flat', bd=0, padx=16, pady=12)
        # Slim accent line on top instead of a chunky border
        tk.Frame(card, bg=accent, height=2).pack(fill='x', pady=(0, 8))
        
        # Icon and trend
        header_frame = tk.Frame(card, bg=self.theme.colors.secondary)
        header_frame.pack(fill='x')
        
        icon_label = tk.Label(header_frame, text=metric["icon"],
                             font=('Segoe UI', 16),
                             bg=self.theme.colors.secondary)
        icon_label.pack(side='left')
        
        trend_label = tk.Label(header_frame, text=metric.get("trend", ""),
                              font=self.theme.fonts['caption'],
                              fg=self._get_trend_color(metric.get("trend", "")),
                              bg=self.theme.colors.secondary)
        trend_label.pack(side='right')
        
        # Value
        value_label = tk.Label(card, text=metric["value"],
                              font=self.theme.fonts['heading'],
                              fg=self._get_context_color(metric.get("context", "neutral")),
                              bg=self.theme.colors.secondary)
        value_label.pack()
        
        # Store reference for specific metrics we want to update
        metric_title = metric.get("title", "")
        if "Record" in metric_title or "Wins" in metric_title:
            self.widget_refs['record_label'] = value_label
        elif "Cap Space" in metric_title:
            self.widget_refs['cap_label'] = value_label
        elif "Top Scorer" in metric_title or "Scorer" in metric_title:
            self.widget_refs['scorer_label'] = value_label
        
        # Title and subtitle
        title_label = tk.Label(card, text=metric["title"],
                              font=self.theme.fonts['body'],
                              fg=self.theme.colors.text_light,
                              bg=self.theme.colors.secondary)
        title_label.pack()
        
        subtitle_label = tk.Label(card, text=metric["subtitle"],
                                 font=self.theme.fonts['caption'],
                                 fg=self.theme.colors.text_light,
                                 bg=self.theme.colors.secondary)
        subtitle_label.pack()
        
        return card
    
    def _generate_situation_narrative(self) -> str:
        """Generate current situation narrative"""
        narratives = [
            "Your team is building momentum with solid performances. The locker room chemistry is strong.",
            "Recent acquisitions are starting to gel with the core group. Expectations are rising.",
            "The power play has been clicking lately, creating scoring opportunities consistently.",
            "Defensive improvements have given the team more confidence in close games."
        ]
        return random.choice(narratives)
    
    def _create_performance_narrative(self, parent):
        """Create performance narrative section"""
        # Performance story with visual elements
        perf_frame = tk.Frame(parent, bg=self.theme.colors.background)
        perf_frame.pack(fill='both', expand=True, padx=16, pady=16)
        
        # Story headline
        headline = tk.Label(perf_frame, text="📈 Your Team's Journey This Season",
                           font=self.theme.fonts['heading'],
                           fg=self.theme.colors.primary,
                           bg=self.theme.colors.background)
        headline.pack(anchor='w', pady=(0, 16))
        
        # Performance highlights - generate dynamically from team data
        highlights = self._generate_performance_highlights()
        
        for highlight in highlights:
            highlight_frame = tk.Frame(perf_frame, bg=self.theme.colors.secondary,
                                     relief='flat', bd=1)
            highlight_frame.pack(fill='x', pady=4)
            
            highlight_label = tk.Label(highlight_frame, text=highlight,
                                      font=self.theme.fonts['body'],
                                      fg=self.theme.colors.text_light,
                                      bg=self.theme.colors.secondary)
            highlight_label.pack(anchor='w', padx=16, pady=8)
    
    def _generate_performance_highlights(self):
        """Generate dynamic performance highlights based on actual team data"""
        try:
            highlights = []
            user_team = getattr(self.parent, 'user_team', None)
            
            if not user_team:
                return ["� Team data loading...", "⏳ Performance analysis pending..."]
            
            # Check team record for streaks
            wins = getattr(user_team, 'wins', 0)
            losses = getattr(user_team, 'losses', 0)
            total_games = wins + losses
            
            if total_games > 0:
                win_pct = wins / total_games
                if win_pct >= 0.7:
                    highlights.append("🔥 Dominant season performance - elite tier team")
                elif win_pct >= 0.6:
                    highlights.append("⭐ Strong season with excellent chemistry")
                elif win_pct >= 0.5:
                    highlights.append("📈 Competitive season, building momentum")
                elif win_pct >= 0.4:
                    highlights.append("🛠️ Developing team showing improvement")
                else:
                    highlights.append("🔧 Rebuilding phase - focusing on development")
            else:
                highlights.append("🏒 Season beginning - ready for action")
            
            # Analyze roster for highlights
            if hasattr(user_team, 'roster') and user_team.roster:
                top_players = sorted(user_team.roster, 
                                   key=lambda p: getattr(p, 'goals', 0) + getattr(p, 'assists', 0), 
                                   reverse=True)[:3]
                
                if top_players and (getattr(top_players[0], 'goals', 0) + getattr(top_players[0], 'assists', 0)) > 0:
                    top_scorer = top_players[0]
                    points = getattr(top_scorer, 'goals', 0) + getattr(top_scorer, 'assists', 0)
                    highlights.append(f"⭐ {getattr(top_scorer, 'full_name', 'Top player')} leading with {points} points")
                else:
                    highlights.append("🎯 Balanced scoring across all lines")
                
                # Check for young talent
                young_players = [p for p in user_team.roster if getattr(p, 'age', 25) < 23]
                if young_players:
                    highlights.append(f"🌟 {len(young_players)} promising prospects developing in system")
                
                # Goalie performance
                goalies = [p for p in user_team.roster if getattr(p, 'primary_position', None) == 'G']
                if goalies:
                    highlights.append("🥅 Goaltending providing solid foundation")
            
            # Cap situation
            try:
                total_cap = 88000000
                used_cap = sum(getattr(getattr(p, 'contract', None), 'salary', 750000) 
                             for p in getattr(user_team, 'roster', []))
                cap_space = total_cap - used_cap
                
                if cap_space > 15000000:
                    highlights.append("💰 Excellent cap flexibility for strategic moves")
                elif cap_space > 5000000:
                    highlights.append("💼 Solid cap management with room to maneuver")
                else:
                    highlights.append("⚖️ Tight cap situation requiring strategic planning")
            except:
                highlights.append("📊 Financial analysis in progress")
            
            # Ensure we have at least some highlights
            if len(highlights) < 3:
                highlights.extend([
                    "🏆 Building championship culture",
                    "📈 Continuous improvement focus",
                    "🎯 Strategic development approach"
                ])
            
            return highlights[:4]  # Return max 4 highlights
            
        except Exception as e:
            return [
                "📊 Performance analysis loading...",
                "⏳ Team data synchronizing...",
                "🔄 Statistics updating...",
                "📈 Preparing detailed insights..."
            ]
    
    def _create_enhanced_inbox_content(self, parent):
        """Create enhanced inbox with visual hierarchy"""
        # Unread count
        unread_count = self._get_unread_count()
        if unread_count > 0:
            unread_frame = tk.Frame(parent, bg=self.theme.colors.danger,
                                   relief='flat', bd=0)
            unread_frame.pack(fill='x', pady=(0, 8))
            
            unread_label = tk.Label(unread_frame, text=f"📧 {unread_count} unread messages",
                                   font=self.theme.fonts['body'],
                                   fg=self.theme.colors.text_light,
                                   bg=self.theme.colors.danger)
            unread_label.pack(padx=8, pady=6)
        
        # Recent messages with icons
        messages = self._get_recent_messages()
        for message in messages[:3]:  # Show top 3
            msg_frame = tk.Frame(parent, bg=self.theme.colors.background,
                               relief='flat', bd=1, cursor='hand2')
            msg_frame.pack(fill='x', pady=2)
            
            # Message icon and preview
            icon = self._get_message_icon(message.get('type', 'general'))
            msg_text = f"{icon} {message.get('subject', 'No subject')}"
            
            msg_label = tk.Label(msg_frame, text=msg_text,
                                font=self.theme.fonts['caption'],
                                fg=self.theme.colors.text_light,
                                bg=self.theme.colors.background,
                                wraplength=180, justify='left')
            msg_label.pack(anchor='w', padx=8, pady=4)
        
        # View all button
        view_all_btn = RoundedButton(parent, text="📨 View All Messages",
                                     font=self.theme.fonts['caption'],
                                     bg=self.theme.colors.primary,
                                     fg=self.theme.colors.text_light,
                                     radius=9, padx=12, pady=7,
                                     command=self._view_all_inbox_action)
        view_all_btn.pack(pady=(8, 0))
    
    # Action methods
    def _continue_day_action(self):
        """Handle continue day action"""
        if hasattr(self.parent, 'simulate_day'):
            self.parent.simulate_day()
    
    def _quick_stats_action(self):
        """Quick stats action - Open Stats & Standings window"""
        if hasattr(self.parent, 'open_stats_standings_window'):
            self.parent.open_stats_standings_window()
        else:
            # Fallback to simple stats popup if stats window doesn't exist
            self._show_team_stats_popup()
    
    def _quick_roster_action(self):
        """Quick roster action - Open roster management"""
        if hasattr(self.parent, 'open_roster_window'):
            self.parent.open_roster_window()
        else:
            print("Roster window not available")
    
    def _quick_standings_action(self):
        """Quick standings action - Open Stats & Standings window with focus on standings"""
        if hasattr(self.parent, 'open_stats_standings_window'):
            self.parent.open_stats_standings_window(focus_tab='standings')
        else:
            print("Stats & Standings window not available")
    
    def _view_all_inbox_action(self):
        """View all inbox action - Open inbox window"""
        if hasattr(self.parent, 'open_inbox_window'):
            self.parent.open_inbox_window()
        else:
            print("Inbox window not available")
            
    def _show_team_stats_popup(self):
        """Show a simple team stats popup window"""
        import tkinter as tk
        from tkinter import ttk
        
        popup = tk.Toplevel(self)
        popup.title("Team Statistics")
        popup.configure(background=self.parent.BG_COLOR)
        popup.geometry("400x300")
        
        # Center the popup
        popup.transient(self)
        popup.grab_set()
        
        # Create content
        title_label = ttk.Label(popup, text="Team Statistics", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Team record
        user_team = self.parent.user_team
        record_text = f"Record: {user_team.wins}-{user_team.losses}-{user_team.ties}"
        record_label = ttk.Label(popup, text=record_text, style='Heading.TLabel')
        record_label.pack(pady=5)
        
        # Points
        points = user_team.wins * 2 + user_team.ties
        points_text = f"Points: {points}"
        points_label = ttk.Label(popup, text=points_text, style='TLabel')
        points_label.pack(pady=5)
        
        # Close button
        close_btn = ttk.Button(popup, text="Close", command=popup.destroy)
        close_btn.pack(pady=20)
    
    # Animation and effects
    def _pulse_continue_button(self, button):
        """Subtle breathing glow on the primary action so the screen feels alive."""
        base = self.theme.colors.primary
        glow = '#e5484d'
        shades = self._shade_range(base, glow, 24)
        state = {'t': 0.0, 'hover': False}

        def on_enter(_e):
            state['hover'] = True
        def on_leave(_e):
            state['hover'] = False
        button.bind('<Enter>', on_enter, add='+')
        button.bind('<Leave>', on_leave, add='+')

        def tick():
            try:
                if not button.winfo_exists():
                    return
                import math
                state['t'] += 0.07
                if not state['hover']:
                    idx = int((math.sin(state['t']) * 0.5 + 0.5) * (len(shades) - 1))
                    button.configure(bg=shades[idx])
                else:
                    button.configure(bg=glow)
            except Exception:
                pass
            finally:
                try:
                    button.after(90, tick)
                except Exception:
                    pass
        tick()

    @staticmethod
    def _shade_range(c1, c2, n):
        def hx(h):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        a, b = hx(c1), hx(c2)
        return ['#%02x%02x%02x' % tuple(int(a[j] + (b[j]-a[j]) * i/(n-1)) for j in range(3))
                for i in range(n)]

    def _start_ambient_animations(self):
        """Start subtle ambient animations"""
        # Pulse team logo every 3 seconds
        if self.animated_elements:
            self.animation_manager.pulse_effect(self.animated_elements[0], 1.02, 3000)
    
    def _add_button_hover_effects(self, button, subtle=False):
        """Add hover effects to buttons"""
        original_bg = button.cget('bg')
        hover_bg = self.theme.colors.success if not subtle else self.theme.colors.primary
        
        def on_enter(event):
            button.configure(bg=hover_bg)
        
        def on_leave(event):
            button.configure(bg=original_bg)
        
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
    
    # Utility methods
    def _get_trend_color(self, trend: str) -> str:
        """Get color for trend indicators"""
        if trend == "↗":
            return self.theme.colors.success
        elif trend == "↘":
            return self.theme.colors.danger
        return self.theme.colors.text_light
    
    def _get_context_color(self, context: str) -> str:
        """Get color based on context"""
        context_colors = {
            'positive': self.theme.colors.success,
            'negative': self.theme.colors.danger,
            'warning': self.theme.colors.warning,
            'neutral': self.theme.colors.text_light,
            'primary': self.theme.colors.primary
        }
        return context_colors.get(context, self.theme.colors.text_light)
    
    def _create_enhanced_next_game_widget(self, parent):
        """Create enhanced next game widget with interactivity"""
        # Get next game data
        next_game_data = self._get_detailed_next_game_info()
        
        if next_game_data:
            # Opponent info section
            opponent_frame = tk.Frame(parent, bg=self.theme.colors.secondary)
            opponent_frame.pack(fill='x', pady=(0, 8))
            
            # Matchup header
            matchup_label = tk.Label(opponent_frame, 
                                   text=f"vs. {next_game_data['opponent']}",
                                   font=self.theme.fonts['subheading'],
                                   fg=self.theme.colors.primary,
                                   bg=self.theme.colors.secondary)
            matchup_label.pack(anchor='w', padx=8, pady=(8, 4))
            
            # Game details
            details_text = f"{next_game_data['date_formatted']} • {next_game_data['home_away']}"
            details_label = tk.Label(opponent_frame, text=details_text,
                                   font=self.theme.fonts['body'],
                                   fg=self.theme.colors.text_light,
                                   bg=self.theme.colors.secondary)
            details_label.pack(anchor='w', padx=8, pady=(0, 4))
            
            # Team comparison section
            comparison_frame = tk.Frame(opponent_frame, bg=self.theme.colors.secondary)
            comparison_frame.pack(fill='x', padx=8, pady=(0, 8))
            
            # Your team column
            your_team_frame = tk.Frame(comparison_frame, bg=self.theme.colors.secondary)
            your_team_frame.pack(side='left', fill='x', expand=True)
            
            your_label = tk.Label(your_team_frame, text="Your Team",
                                font=self.theme.fonts['caption'],
                                fg=self.theme.colors.primary,
                                bg=self.theme.colors.secondary)
            your_label.pack(anchor='w')
            
            your_record = tk.Label(your_team_frame, text=next_game_data['your_record'],
                                 font=self.theme.fonts['caption'],
                                 fg=self.theme.colors.text_light,
                                 bg=self.theme.colors.secondary)
            your_record.pack(anchor='w')
            
            # VS separator
            vs_label = tk.Label(comparison_frame, text="VS",
                              font=self.theme.fonts['caption'],
                              fg=self.theme.colors.text_light,
                              bg=self.theme.colors.secondary)
            vs_label.pack(side='left', padx=8)
            
            # Opponent column
            opp_team_frame = tk.Frame(comparison_frame, bg=self.theme.colors.secondary)
            opp_team_frame.pack(side='right', fill='x', expand=True)
            
            opp_label = tk.Label(opp_team_frame, text="Opponent",
                               font=self.theme.fonts['caption'],
                               fg=self.theme.colors.primary,
                               bg=self.theme.colors.secondary)
            opp_label.pack(anchor='e')
            
            opp_record = tk.Label(opp_team_frame, text=next_game_data['opponent_record'],
                                font=self.theme.fonts['caption'],
                                fg=self.theme.colors.text_light,
                                bg=self.theme.colors.secondary)
            opp_record.pack(anchor='e')
            
            # Game preview button
            if next_game_data['days_until'] <= 1:  # Show preview for games today or tomorrow
                preview_btn = tk.Button(parent, text="📊 Game Preview",
                                      font=self.theme.fonts['caption'],
                                      bg=self.theme.colors.primary,
                                      fg=self.theme.colors.text_light,
                                      relief='flat', bd=0,
                                      padx=8, pady=4,
                                      cursor='hand2',
                                      command=lambda: self._show_game_preview(next_game_data))
                preview_btn.pack(pady=(4, 0))
                self._add_button_hover_effects(preview_btn, subtle=True)
        else:
            # No game scheduled fallback
            no_game_label = tk.Label(parent, text="No upcoming games\nSchedule TBD",
                                   font=self.theme.fonts['body'],
                                   fg=self.theme.colors.text_light,
                                   bg=self.theme.colors.secondary,
                                   justify='center')
            no_game_label.pack(pady=8)

    def _get_detailed_next_game_info(self):
        """Get detailed next game information for enhanced widget"""
        try:
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'league'):
                user_team_name = self.parent.user_team.team_name
                today = getattr(self.parent.game_manager, 'current_date', None)
                
                # Look for next scheduled game
                for team in self.parent.game_manager.league.teams:
                    if hasattr(team, 'schedule'):
                        for game in team.schedule:
                            if (hasattr(game, 'home_team') and hasattr(game, 'away_team') and 
                                hasattr(game, 'date') and 
                                (game.home_team == user_team_name or game.away_team == user_team_name)):
                                if today is None or game.date > today:
                                    # Found next game
                                    opponent_name = game.away_team if game.home_team == user_team_name else game.home_team
                                    is_home = game.home_team == user_team_name
                                    
                                    # Get opponent team object for stats
                                    opponent_team = None
                                    for t in self.parent.game_manager.league.teams:
                                        if t.team_name == opponent_name:
                                            opponent_team = t
                                            break
                                    
                                    # Calculate days until game
                                    days_until = (game.date - today).days if today else 0
                                    
                                    # Format date
                                    date_formatted = game.date.strftime("%m/%d")
                                    if days_until == 0:
                                        date_formatted += " (Today)"
                                    elif days_until == 1:
                                        date_formatted += " (Tomorrow)"
                                    
                                    # Get records
                                    your_record = f"{self.parent.user_team.wins}-{self.parent.user_team.losses}-{getattr(self.parent.user_team, 'ties', 0)}"
                                    opponent_record = "0-0-0"
                                    if opponent_team:
                                        opponent_record = f"{opponent_team.wins}-{opponent_team.losses}-{getattr(opponent_team, 'ties', 0)}"
                                    
                                    return {
                                        'opponent': opponent_name,
                                        'date': game.date,
                                        'date_formatted': date_formatted,
                                        'home_away': "Home" if is_home else "Away",
                                        'days_until': days_until,
                                        'your_record': your_record,
                                        'opponent_record': opponent_record,
                                        'opponent_team': opponent_team,
                                        'is_home': is_home
                                    }
            return None
        except Exception as e:
            print(f"Error getting detailed next game info: {e}")
            return None

    def _show_game_preview(self, game_data):
        """Show detailed game preview window"""
        preview_window = tk.Toplevel(self.parent)
        preview_window.title(f"Game Preview: vs. {game_data['opponent']}")
        preview_window.configure(bg=self.theme.colors.background)
        preview_window.geometry("500x600")
        preview_window.transient(self.parent)
        preview_window.grab_set()
        
        # Center the window
        preview_window.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 50,
            self.parent.winfo_rooty() + 50
        ))
        
        # Header
        header_frame = tk.Frame(preview_window, bg=self.theme.colors.primary, height=60)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, 
                             text=f"🏒 {self.parent.user_team.team_name} vs. {game_data['opponent']}",
                             font=self.theme.fonts['heading'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.primary)
        title_label.pack(expand=True)
        
        # Main content
        content_frame = tk.Frame(preview_window, bg=self.theme.colors.background)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Game details
        details_frame = tk.Frame(content_frame, bg=self.theme.colors.secondary, relief='flat', bd=1)
        details_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(details_frame, text="📅 Game Details",
                font=self.theme.fonts['subheading'],
                fg=self.theme.colors.primary,
                bg=self.theme.colors.secondary).pack(anchor='w', padx=12, pady=(12, 8))
        
        details_text = f"Date: {game_data['date_formatted']}\nVenue: {'Home' if game_data['is_home'] else 'Away'} Game\nType: Regular Season"
        tk.Label(details_frame, text=details_text,
                font=self.theme.fonts['body'],
                fg=self.theme.colors.text_light,
                bg=self.theme.colors.secondary,
                justify='left').pack(anchor='w', padx=12, pady=(0, 12))
        
        # Team comparison
        comparison_frame = tk.Frame(content_frame, bg=self.theme.colors.secondary, relief='flat', bd=1)
        comparison_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(comparison_frame, text="⚔️ Team Comparison",
                font=self.theme.fonts['subheading'],
                fg=self.theme.colors.primary,
                bg=self.theme.colors.secondary).pack(anchor='w', padx=12, pady=(12, 8))
        
        # Stats comparison grid
        stats_grid = tk.Frame(comparison_frame, bg=self.theme.colors.secondary)
        stats_grid.pack(fill='x', padx=12, pady=(0, 12))
        
        # Headers
        tk.Label(stats_grid, text="", width=15, font=self.theme.fonts['caption'],
                bg=self.theme.colors.secondary).grid(row=0, column=0)
        tk.Label(stats_grid, text="Your Team", width=12, font=self.theme.fonts['caption'],
                fg=self.theme.colors.primary, bg=self.theme.colors.secondary).grid(row=0, column=1)
        tk.Label(stats_grid, text="Opponent", width=12, font=self.theme.fonts['caption'],
                fg=self.theme.colors.primary, bg=self.theme.colors.secondary).grid(row=0, column=2)
        
        # Stats rows
        stats_data = [
            ("Record", game_data['your_record'], game_data['opponent_record']),
            ("Goals For", str(getattr(self.parent.user_team, 'goals_for', 0)), 
             str(getattr(game_data.get('opponent_team'), 'goals_for', 0)) if game_data.get('opponent_team') else "0"),
            ("Goals Against", str(getattr(self.parent.user_team, 'goals_against', 0)),
             str(getattr(game_data.get('opponent_team'), 'goals_against', 0)) if game_data.get('opponent_team') else "0")
        ]
        
        for i, (stat_name, your_stat, opp_stat) in enumerate(stats_data, 1):
            tk.Label(stats_grid, text=stat_name, font=self.theme.fonts['body'],
                    fg=self.theme.colors.text_light, bg=self.theme.colors.secondary).grid(row=i, column=0, sticky='w')
            tk.Label(stats_grid, text=your_stat, font=self.theme.fonts['body'],
                    fg=self.theme.colors.text_light, bg=self.theme.colors.secondary).grid(row=i, column=1)
            tk.Label(stats_grid, text=opp_stat, font=self.theme.fonts['body'],
                    fg=self.theme.colors.text_light, bg=self.theme.colors.secondary).grid(row=i, column=2)
        
        # Key players section
        players_frame = tk.Frame(content_frame, bg=self.theme.colors.secondary, relief='flat', bd=1)
        players_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(players_frame, text="⭐ Key Players to Watch",
                font=self.theme.fonts['subheading'],
                fg=self.theme.colors.primary,
                bg=self.theme.colors.secondary).pack(anchor='w', padx=12, pady=(12, 8))
        
        # Get top 3 players from user team
        if hasattr(self.parent.user_team, 'roster') and self.parent.user_team.roster:
            top_players = sorted(self.parent.user_team.roster, 
                               key=lambda p: getattr(p, 'goals', 0) + getattr(p, 'assists', 0), 
                               reverse=True)[:3]
            
            for player in top_players:
                points = getattr(player, 'goals', 0) + getattr(player, 'assists', 0)
                player_text = f"• {getattr(player, 'full_name', 'Unknown')} - {points} points"
                tk.Label(players_frame, text=player_text,
                        font=self.theme.fonts['body'],
                        fg=self.theme.colors.text_light,
                        bg=self.theme.colors.secondary).pack(anchor='w', padx=24, pady=1)
        
        # Close button
        close_btn = tk.Button(content_frame, text="Close Preview",
                            font=self.theme.fonts['body'],
                            bg=self.theme.colors.primary,
                            fg=self.theme.colors.text_light,
                            relief='flat', bd=0,
                            padx=20, pady=8,
                            cursor='hand2',
                            command=preview_window.destroy)
        close_btn.pack(pady=(10, 0))
        self._add_button_hover_effects(close_btn)

    def _get_next_game_info(self) -> str:
        """Get next game information"""
        # Try to get actual next game from schedule
        if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'league'):
            # Find next game for user team
            user_team_name = self.parent.user_team.team_name
            today = getattr(self.parent.game_manager, 'current_date', None)
            
            # Look for next scheduled game
            for team in self.parent.game_manager.league.teams:
                if hasattr(team, 'schedule'):
                    for game in team.schedule:
                        if (hasattr(game, 'home_team') and hasattr(game, 'away_team') and 
                            hasattr(game, 'date') and (game.home_team == user_team_name or game.away_team == user_team_name)):
                            if today is None or game.date > today:
                                opponent = game.away_team if game.home_team == user_team_name else game.home_team
                                home_away = "Home" if game.home_team == user_team_name else "Away"
                                return f"Next vs. {opponent}\n{game.date} • {home_away}\nRegular Season"
        
        # Fallback if no schedule data available
        return "Schedule TBD\nNext game pending\nSeason planning"
    
    def _get_cap_space_info(self) -> str:
        """Get salary cap space info"""
        try:
            # Calculate actual salary cap information
            salary_cap = 83500000  # NHL salary cap
            current_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000)) 
                               for p in self.parent.user_team.roster)
            cap_space = salary_cap - current_salary
            roster_spots = 23 - len(self.parent.user_team.roster)
            
            # Format cap space in millions
            cap_space_millions = cap_space / 1000000
            
            return (f"${cap_space_millions:.1f}M available\n"
                   f"{roster_spots} roster spots open\n"
                   f"Cap usage: {(current_salary/salary_cap)*100:.1f}%")
        except:
            return "Cap data loading...\nPlease wait...\nCalculating..."
    
    def _get_injury_info(self) -> str:
        """Get injury report"""
        try:
            # Count injured players from roster
            injured_players = []
            day_to_day_players = []
            
            for player in self.parent.user_team.roster:
                if hasattr(player, 'is_injured') and player.is_injured:
                    injured_players.append(player)
                elif hasattr(player, 'injury_status') and player.injury_status == 'day-to-day':
                    day_to_day_players.append(player)
            
            injured_count = len(injured_players)
            day_to_day_count = len(day_to_day_players)
            
            if injured_count == 0 and day_to_day_count == 0:
                return "No injuries\nFull health\nOverall: Excellent"
            else:
                status = "Healthy" if injured_count <= 1 else "Concerning" if injured_count <= 3 else "Critical"
                return f"{injured_count} players out\n{day_to_day_count} day-to-day\nOverall: {status}"
                
        except:
            return "Injury data loading\nHealth check pending\nOverall: Unknown"
    
    def _get_trending_info(self) -> str:
        """Get trending information"""
        try:
            trends = []
            
            # Analyze team stats for trends
            roster = self.parent.user_team.roster
            
            # Check team chemistry
            if hasattr(self.parent.user_team, 'team_chemistry'):
                chemistry = self.parent.user_team.team_chemistry
                if chemistry > 75:
                    trends.append("Team chemistry strong")
                elif chemistry < 50:
                    trends.append("Chemistry needs work")
            
            # Check for young talent
            young_players = [p for p in roster if p.age <= 22 and p.overall_rating() >= 42]
            if len(young_players) >= 3:
                trends.append("Young core developing")
            
            # Check average morale
            avg_morale = sum(getattr(p, 'morale', 50) for p in roster) / len(roster) if roster else 50
            if avg_morale > 75:
                trends.append("Team morale high")
            elif avg_morale < 40:
                trends.append("Morale concerns")
            
            # Default trends if none found
            if not trends:
                trends = ["Season developing", "Roster evaluation", "Planning ahead"]
            
            return "\n".join(trends[:3])  # Show max 3 trends
            
        except:
            return "Performance tracking\nTrend analysis\nData processing"
    
    def _get_quick_standings_info(self) -> str:
        """Get quick standings information"""
        try:
            # Get user team's current position
            user_team = self.parent.user_team
            user_record = f"{user_team.wins}-{user_team.losses}-{user_team.ties}"
            user_points = user_team.wins * 2 + user_team.ties
            
            # Calculate position among all teams
            if hasattr(self.parent, 'league') and self.parent.league:
                all_teams = []
                for team in self.parent.league.teams:
                    points = team.wins * 2 + team.ties
                    all_teams.append((team.team_name, points))
                
                # Sort by points
                all_teams.sort(key=lambda x: x[1], reverse=True)
                
                # Find user team position
                user_position = None
                for i, (team_name, points) in enumerate(all_teams):
                    if team_name == user_team.team_name:
                        user_position = i + 1
                        break
                
                if user_position:
                    return f"Position: {user_position} of {len(all_teams)}\nRecord: {user_record}\nPoints: {user_points}"
            
            # Fallback
            return f"Record: {user_record}\nPoints: {user_points}\nStandings updating..."
            
        except:
            return "Standings loading\nPosition tracking\nLeague analysis"
    
    def _get_gm_status_text(self) -> str:
        """Get GM status text"""
        try:
            # Create dynamic status based on team situation
            wins = getattr(self.parent.user_team, 'wins', 0)
            losses = getattr(self.parent.user_team, 'losses', 0)
            total_games = wins + losses + getattr(self.parent.user_team, 'ot_losses', 0)
            
            # Calculate team performance indicators
            roster_size = len(self.parent.user_team.roster)
            avg_age = sum(p.age for p in self.parent.user_team.roster) / roster_size if roster_size > 0 else 25
            avg_rating = sum(p.overall_rating() for p in self.parent.user_team.roster) / roster_size if roster_size > 0 else 75
            
            # Build status based on various factors
            status_parts = []
            
            # Performance status
            if total_games > 0:
                win_pct = wins / total_games
                if win_pct > 0.6:
                    status_parts.append("🎯 Strong performance")
                elif win_pct > 0.4:
                    status_parts.append("⚖️ Competitive balance")
                else:
                    status_parts.append("📊 Building phase")
            else:
                status_parts.append("🎯 Season ready")
            
            # Team composition status
            if avg_rating > 80:
                status_parts.append("💪 Elite roster")
            elif avg_rating > 75:
                status_parts.append("📈 Strong lineup")
            else:
                status_parts.append("🔧 Development focus")
            
            # Readiness status
            if roster_size >= 20:
                status_parts.append("💼 Full operations")
            else:
                status_parts.append("🏗️ Roster building")
            
            return " • ".join(status_parts)
            
        except:
            return "🎯 Systems operational • � Ready for action • 💼 Management active"
    
    def _get_team_record(self) -> str:
        """Get team record"""
        try:
            # Get actual team record
            wins = getattr(self.parent.user_team, 'wins', 0)
            losses = getattr(self.parent.user_team, 'losses', 0)
            ot_losses = getattr(self.parent.user_team, 'ot_losses', 0)
            
            return f"{wins}-{losses}-{ot_losses}"
        except:
            return "0-0-0"
    
    def _get_unread_count(self) -> int:
        """Get unread message count"""
        if hasattr(self.parent, 'user_team') and hasattr(self.parent.user_team, 'inbox'):
            return len([msg for msg in self.parent.user_team.inbox.messages if not msg.is_read])
        return 0  # No inbox available
    
    def _get_recent_messages(self) -> List[Dict]:
        """Get recent messages"""
        if hasattr(self.parent, 'user_team') and hasattr(self.parent.user_team, 'inbox'):
            # Get real messages from inbox
            messages = []
            for msg in self.parent.user_team.inbox.messages[-5:]:  # Last 5 messages
                # Determine message type based on subject/sender
                msg_type = 'general'
                subject = getattr(msg, 'subject', 'Unknown')
                subject_lower = subject.lower()
                
                if 'trade' in subject_lower or 'offer' in subject_lower:
                    msg_type = 'trade'
                elif 'injury' in subject_lower or 'medical' in subject_lower:
                    msg_type = 'medical'
                elif 'contract' in subject_lower or 'negotiation' in subject_lower:
                    msg_type = 'contract'
                elif 'scout' in subject_lower or 'report' in subject_lower:
                    msg_type = 'scout'
                elif 'achievement' in subject_lower or 'milestone' in subject_lower:
                    msg_type = 'achievement'
                
                messages.append({
                    'subject': subject,
                    'type': msg_type
                })
            
            return messages if messages else self._get_fallback_messages()
        else:
            return self._get_fallback_messages()
    
    def _get_fallback_messages(self) -> List[Dict]:
        """Get fallback messages when no inbox data available"""
        return [
            {'subject': 'Welcome to the season!', 'type': 'general'},
            {'subject': 'Roster evaluation complete', 'type': 'scout'},
            {'subject': 'Season schedule released', 'type': 'general'}
        ]
    
    def _get_message_icon(self, msg_type: str) -> str:
        """Get icon for message type"""
        icons = {
            'trade': '🔄',
            'achievement': '🏆',
            'medical': '🏥',
            'contract': '📝',
            'scout': '🔍',
            'general': '📧'
        }
        return icons.get(msg_type, '📧')

    def update_data(self, current_date=None, team_record=None, next_game=None, 
                   roster_highlights=None, recent_news=None):
        """Update dashboard data - method for compatibility with main application"""
        # Store updated data for use in refresh methods
        if current_date:
            self.current_date = current_date
        if team_record:
            self.team_record = team_record
        if next_game:
            self.next_game = next_game
        if roster_highlights:
            self.roster_highlights = roster_highlights
        if recent_news:
            self.recent_news = recent_news
        
        # Refresh visual elements if they exist
        # This method serves as a compatibility layer with the main application
    
    def refresh_dashboard(self):
        """Refresh all dashboard data and UI elements"""
        try:
            # First, always refresh the date display
            self._refresh_date_display()
            
            # Get fresh data
            metrics_list = self._get_storytelling_metrics()
            highlights = self._generate_performance_highlights()
            
            # Convert metrics list to dictionary format for easier access
            metrics_dict = self._extract_metrics_data(metrics_list)
            
            # Update existing widgets instead of recreating
            self._update_existing_widgets(metrics_dict, highlights)
            
        except Exception as e:
            print(f"Error refreshing dashboard: {e}")
            # Fallback: just update what we can
            self._refresh_date_display()
    
    def _extract_metrics_data(self, metrics_list):
        """Extract individual metric values from the metrics list"""
        metrics_dict = {}
        
        try:
            # Extract data from the metrics list
            for metric in metrics_list:
                title = metric.get('title', '')
                if 'Record' in title or 'Wins' in title:
                    # Extract wins, losses from value like "12-5-2"
                    value = metric.get('value', '0-0-0')
                    parts = value.split('-')
                    metrics_dict['wins'] = int(parts[0]) if len(parts) > 0 else 0
                    metrics_dict['losses'] = int(parts[1]) if len(parts) > 1 else 0 
                    metrics_dict['ot_losses'] = int(parts[2]) if len(parts) > 2 else 0
                elif 'Cap Space' in title:
                    # Extract cap space from value like "$15.2M"
                    value = metric.get('value', '$0.0M')
                    metrics_dict['cap_space_millions'] = float(value.replace('$', '').replace('M', ''))
                elif 'Top Scorer' in title or 'Scorer' in title:
                    # Extract goals from subtitle or value
                    subtitle = metric.get('subtitle', '')
                    value = metric.get('value', '0 pts')
                    metrics_dict['top_scorer'] = subtitle if subtitle != 'No stats yet' else 'N/A'
                    # Extract goals from value like "25 pts"
                    goals = value.replace(' pts', '').replace(' goals', '').replace('G', '')
                    try:
                        metrics_dict['top_scorer_goals'] = int(goals) if goals.isdigit() else 0
                    except:
                        metrics_dict['top_scorer_goals'] = 0
                        
        except Exception as e:
            print(f"Error extracting metrics data: {e}")
            # Fallback values
            metrics_dict = {
                'wins': 0, 'losses': 0, 'ot_losses': 0,
                'cap_space_millions': 0.0,
                'top_scorer': 'N/A', 'top_scorer_goals': 0
            }
        
        return metrics_dict
    
    def _update_existing_widgets(self, metrics, highlights):
        """Update existing dashboard widgets with new data"""
        try:
            # Update widgets if they exist and are accessible
            if hasattr(self, 'widget_refs'):
                # Update record display
                if 'record_label' in self.widget_refs:
                    try:
                        if self.widget_refs['record_label'].winfo_exists():
                            wins = metrics.get('wins', 0) 
                            losses = metrics.get('losses', 0)
                            ot_losses = metrics.get('ot_losses', 0)
                            self.widget_refs['record_label'].config(text=f"{wins}-{losses}-{ot_losses}")
                    except tk.TclError:
                        # Widget no longer exists
                        del self.widget_refs['record_label']
                
                # Update cap space display
                if 'cap_label' in self.widget_refs:
                    try:
                        if self.widget_refs['cap_label'].winfo_exists():
                            cap_space = metrics.get('cap_space_millions', 0.0)
                            self.widget_refs['cap_label'].config(text=f"${cap_space:.1f}M")
                    except tk.TclError:
                        # Widget no longer exists
                        del self.widget_refs['cap_label']
                
                # Update top scorer display
                if 'scorer_label' in self.widget_refs:
                    try:
                        if self.widget_refs['scorer_label'].winfo_exists():
                            top_scorer = metrics.get('top_scorer', 'N/A')
                            goals = metrics.get('top_scorer_goals', 0)
                            self.widget_refs['scorer_label'].config(text=f"{top_scorer} ({goals}G)")
                    except tk.TclError:
                        # Widget no longer exists
                        del self.widget_refs['scorer_label']
                    
            print("Dashboard widgets updated with fresh data")
            
        except Exception as e:
            print(f"Error updating dashboard widgets: {e}")
    
    def _refresh_date_display(self):
        """Refresh just the date display if full refresh fails"""
        try:
            # Update the date labels if they exist
            if hasattr(self, 'date_label') and hasattr(self, 'day_label'):
                current_date = getattr(self.game_manager, 'current_date', date.today())
                date_str = current_date.strftime("%B %d, %Y")
                day_str = current_date.strftime("%A")
                
                self.date_label.config(text=date_str)
                self.day_label.config(text=day_str)
        except Exception as e:
            print(f"Error refreshing date display: {e}")
    
    def _create_recent_events_tab(self, parent):
        """Create the Recent Events tab content"""
        events_frame = tk.Frame(parent, bg=self.theme.colors.background)
        events_frame.pack(fill='both', expand=True, padx=16, pady=16)
        
        # Header
        headline = tk.Label(events_frame, text="📝 Recent Team Events",
                           font=self.theme.fonts['heading'],
                           fg=self.theme.colors.primary,
                           bg=self.theme.colors.background)
        headline.pack(anchor='w', pady=(0, 16))
        
        # Get recent events
        recent_events = self._get_recent_events()
        
        # Events list
        events_container = tk.Frame(events_frame, bg=self.theme.colors.background)
        events_container.pack(fill='both', expand=True)
        
        for i, event in enumerate(recent_events):
            event_frame = tk.Frame(events_container, bg=self.theme.colors.secondary,
                                 relief='flat', bd=1)
            event_frame.pack(fill='x', pady=4)
            
            # Event header with timestamp
            header_frame = tk.Frame(event_frame, bg=self.theme.colors.secondary)
            header_frame.pack(fill='x', padx=12, pady=(8, 4))
            
            time_label = tk.Label(header_frame, text=event.get('timestamp', 'Recent'),
                                font=self.theme.fonts['caption'],
                                fg=self.theme.colors.text_light,
                                bg=self.theme.colors.secondary)
            time_label.pack(side='left')
            
            priority_color = self.theme.colors.primary if event.get('priority') == 'high' else self.theme.colors.text_light
            priority_label = tk.Label(header_frame, text=event.get('category', 'General'),
                                    font=self.theme.fonts['caption'],
                                    fg=priority_color,
                                    bg=self.theme.colors.secondary)
            priority_label.pack(side='right')
            
            # Event description
            desc_label = tk.Label(event_frame, text=event['description'],
                                font=self.theme.fonts['body'],
                                fg=self.theme.colors.text_light,
                                bg=self.theme.colors.secondary,
                                wraplength=600, justify='left')
            desc_label.pack(anchor='w', padx=12, pady=(0, 8))
    
    def _create_priorities_tab(self, parent):
        """Create the Priorities tab content"""
        priorities_frame = tk.Frame(parent, bg=self.theme.colors.background)
        priorities_frame.pack(fill='both', expand=True, padx=16, pady=16)
        
        # Header
        headline = tk.Label(priorities_frame, text="🎯 Current Team Priorities",
                           font=self.theme.fonts['heading'],
                           fg=self.theme.colors.primary,
                           bg=self.theme.colors.background)
        headline.pack(anchor='w', pady=(0, 16))
        
        # Get current priorities
        priorities = self._get_team_priorities()
        
        # Priorities grid
        for i, priority in enumerate(priorities):
            priority_frame = tk.Frame(priorities_frame, bg=self.theme.colors.secondary,
                                    relief='flat', bd=2)
            priority_frame.pack(fill='x', pady=6)
            
            # Priority header
            header_frame = tk.Frame(priority_frame, bg=self.theme.colors.primary)
            header_frame.pack(fill='x')
            
            title_label = tk.Label(header_frame, text=f"{priority['icon']} {priority['title']}",
                                 font=self.theme.fonts['subheading'],
                                 fg=self.theme.colors.text_light,
                                 bg=self.theme.colors.primary)
            title_label.pack(side='left', padx=12, pady=8)
            
            urgency_label = tk.Label(header_frame, text=priority['urgency'],
                                   font=self.theme.fonts['caption'],
                                   fg=self.theme.colors.text_light,
                                   bg=self.theme.colors.primary)
            urgency_label.pack(side='right', padx=12, pady=8)
            
            # Priority description and actions
            content_frame = tk.Frame(priority_frame, bg=self.theme.colors.secondary)
            content_frame.pack(fill='x', padx=12, pady=8)
            
            desc_label = tk.Label(content_frame, text=priority['description'],
                                font=self.theme.fonts['body'],
                                fg=self.theme.colors.text_light,
                                bg=self.theme.colors.secondary,
                                wraplength=600, justify='left')
            desc_label.pack(anchor='w', pady=(0, 4))
            
            if priority.get('actions'):
                actions_label = tk.Label(content_frame, text=f"→ {priority['actions']}",
                                       font=self.theme.fonts['caption'],
                                       fg=self.theme.colors.primary,
                                       bg=self.theme.colors.secondary,
                                       wraplength=600, justify='left')
                actions_label.pack(anchor='w')
    
    def _create_league_pulse_tab(self, parent):
        """Create the League Pulse tab content"""
        pulse_frame = tk.Frame(parent, bg=self.theme.colors.background)
        pulse_frame.pack(fill='both', expand=True, padx=16, pady=16)
        
        # Header
        headline = tk.Label(pulse_frame, text="📊 League Pulse",
                           font=self.theme.fonts['heading'],
                           fg=self.theme.colors.primary,
                           bg=self.theme.colors.background)
        headline.pack(anchor='w', pady=(0, 16))
        
        # Get league data
        league_data = self._get_league_pulse_data()
        
        # Create sections
        sections = [
            ("🏆 Standings Summary", league_data['standings']),
            ("📈 League Trends", league_data['trends']),
            ("🔥 Hot Topics", league_data['hot_topics']),
            ("📊 Statistical Leaders", league_data['stats'])
        ]
        
        for section_title, section_data in sections:
            section_frame = tk.Frame(pulse_frame, bg=self.theme.colors.secondary,
                                   relief='flat', bd=1)
            section_frame.pack(fill='x', pady=8)
            
            # Section header
            header_label = tk.Label(section_frame, text=section_title,
                                  font=self.theme.fonts['subheading'],
                                  fg=self.theme.colors.primary,
                                  bg=self.theme.colors.secondary)
            header_label.pack(anchor='w', padx=12, pady=(8, 4))
            
            # Section content
            for item in section_data:
                item_label = tk.Label(section_frame, text=f"• {item}",
                                    font=self.theme.fonts['body'],
                                    fg=self.theme.colors.text_light,
                                    bg=self.theme.colors.secondary,
                                    wraplength=600, justify='left')
                item_label.pack(anchor='w', padx=24, pady=2)
            
            # Add spacing
            tk.Frame(section_frame, bg=self.theme.colors.secondary, height=8).pack()
    
    def _get_recent_events(self):
        """Get recent team events"""
        try:
            # Try to get actual events from game manager
            events = []
            
            # Check for recent games
            user_team = getattr(self.parent, 'user_team', None)
            game_manager = getattr(self.parent, 'game_manager', None)
            
            if user_team and game_manager:
                # Recent game results
                recent_games = getattr(game_manager, 'recent_games', [])
                for game in recent_games[-3:]:  # Last 3 games
                    if hasattr(game, 'home_team') and hasattr(game, 'away_team'):
                        home_name = getattr(game.home_team, 'team_name', str(game.home_team))
                        away_name = getattr(game.away_team, 'team_name', str(game.away_team))
                        user_team_name = getattr(user_team, 'team_name', '')
                        
                        if user_team_name in [home_name, away_name]:
                            result = "Won" if getattr(game, 'user_won', False) else "Lost"
                            opponent = away_name if user_team_name == home_name else home_name
                            events.append({
                                'timestamp': 'Recent Game',
                                'category': 'Game Result',
                                'description': f"{result} against {opponent}",
                                'priority': 'high' if result == "Won" else 'normal'
                            })
                
                # Add roster events
                events.extend([
                    {
                        'timestamp': 'Today',
                        'category': 'Roster',
                        'description': 'Team chemistry building through practice sessions',
                        'priority': 'normal'
                    },
                    {
                        'timestamp': 'Yesterday', 
                        'category': 'Development',
                        'description': 'Young prospects showing improvement in training',
                        'priority': 'normal'
                    }
                ])
            
            # Fallback events if no real data
            if not events:
                events = [
                    {
                        'timestamp': 'Today',
                        'category': 'Team News',
                        'description': 'Team preparing for upcoming challenges',
                        'priority': 'normal'
                    },
                    {
                        'timestamp': 'Recent',
                        'category': 'Development',
                        'description': 'Coaching staff analyzing team performance',
                        'priority': 'normal'
                    },
                    {
                        'timestamp': 'This Week',
                        'category': 'Strategy',
                        'description': 'Tactical adjustments being implemented',
                        'priority': 'normal'
                    }
                ]
            
            return events[:6]  # Return max 6 events
            
        except Exception as e:
            return [
                {
                    'timestamp': 'Recent',
                    'category': 'System',
                    'description': 'Event tracking system initializing...',
                    'priority': 'normal'
                }
            ]
    
    def _get_team_priorities(self):
        """Get current team management priorities"""
        try:
            priorities = []
            user_team = getattr(self.parent, 'user_team', None)
            
            if user_team:
                # Analyze roster for priorities
                roster = getattr(user_team, 'roster', [])
                
                # Check contract situations
                expiring_contracts = 0
                for player in roster:
                    contract = getattr(player, 'contract', None)
                    if contract and getattr(contract, 'years_remaining', 2) <= 1:
                        expiring_contracts += 1
                
                if expiring_contracts > 0:
                    priorities.append({
                        'icon': '📝',
                        'title': 'Contract Extensions',
                        'urgency': 'High Priority',
                        'description': f'{expiring_contracts} players have contracts expiring soon',
                        'actions': 'Review extension candidates and initiate negotiations'
                    })
                
                # Cap space management
                try:
                    total_cap = 88000000
                    used_cap = sum(getattr(getattr(p, 'contract', None), 'salary', 750000) 
                                 for p in roster)
                    cap_space = total_cap - used_cap
                    
                    if cap_space < 5000000:
                        priorities.append({
                            'icon': '💰',
                            'title': 'Salary Cap Management',
                            'urgency': 'Medium Priority',
                            'description': f'Limited cap space remaining (${cap_space/1000000:.1f}M)',
                            'actions': 'Consider roster moves or contract restructuring'
                        })
                except:
                    pass
                
                # Team development
                young_players = [p for p in roster if getattr(p, 'age', 25) < 23]
                if young_players:
                    priorities.append({
                        'icon': '🌟',
                        'title': 'Prospect Development',
                        'urgency': 'Ongoing',
                        'description': f'{len(young_players)} young players need development focus',
                        'actions': 'Assign mentors and create development plans'
                    })
            
            # Default priorities if no real data
            if not priorities:
                priorities = [
                    {
                        'icon': '🎯',
                        'title': 'Team Chemistry',
                        'urgency': 'High Priority',
                        'description': 'Building cohesion and communication between line combinations',
                        'actions': 'Focus on line chemistry in practice sessions'
                    },
                    {
                        'icon': '📈',
                        'title': 'Performance Analysis',
                        'urgency': 'Medium Priority', 
                        'description': 'Analyzing recent game footage to identify improvement areas',
                        'actions': 'Review game tape with coaching staff'
                    },
                    {
                        'icon': '🏥',
                        'title': 'Player Health',
                        'urgency': 'Ongoing',
                        'description': 'Monitoring player fitness and injury prevention protocols',
                        'actions': 'Maintain conditioning programs and rest schedules'
                    }
                ]
            
            return priorities[:5]  # Return max 5 priorities
            
        except Exception as e:
            return [
                {
                    'icon': '⚙️',
                    'title': 'System Initialization',
                    'urgency': 'In Progress',
                    'description': 'Priority tracking system loading...',
                    'actions': 'Please wait for system initialization'
                }
            ]
    
    def _get_league_pulse_data(self):
        """Get league-wide statistics and trends"""
        try:
            game_manager = getattr(self.parent, 'game_manager', None)
            user_team = getattr(self.parent, 'user_team', None)
            
            data = {
                'standings': [],
                'trends': [],
                'hot_topics': [],
                'stats': []
            }
            
            if game_manager and user_team:
                # Try to get real league data
                leagues = getattr(game_manager, 'leagues', {})
                nhl = leagues.get('National Hockey League')
                
                if nhl:
                    teams = getattr(nhl, 'teams', [])
                    user_team_name = getattr(user_team, 'team_name', '')
                    
                    # Standings summary
                    user_wins = getattr(user_team, 'wins', 0)
                    user_losses = getattr(user_team, 'losses', 0)
                    total_games = user_wins + user_losses
                    
                    if total_games > 0:
                        win_pct = user_wins / total_games
                        if win_pct >= 0.6:
                            position = "top third"
                        elif win_pct >= 0.4:
                            position = "middle of the pack"
                        else:
                            position = "rebuilding phase"
                        
                        data['standings'].append(f"Your team currently {position} in league standings")
                    
                    data['standings'].extend([
                        f"League features {len(teams)} competitive teams",
                        "Standings remain tight with multiple playoff contenders",
                        "Every game crucial for playoff positioning"
                    ])
                    
                    # League trends
                    data['trends'].extend([
                        "Emphasis on speed and skill development across league",
                        "Power play efficiency becoming key differentiator",
                        "Goaltending depth crucial for playoff success",
                        "Young talent making immediate impact league-wide"
                    ])
                    
                    # Hot topics
                    data['hot_topics'].extend([
                        "Trade deadline activity expected to be significant",
                        "Salary cap management challenging for several teams",
                        "Rookie class showing exceptional promise",
                        "Coaching strategies evolving with rule changes"
                    ])
            
            # Fallback data
            if not data['standings']:
                data = {
                    'standings': [
                        "League standings tracking in progress",
                        "32 teams competing for playoff positioning",
                        "Competitive balance across all divisions",
                        "Multiple teams within striking distance"
                    ],
                    'trends': [
                        "Speed and skill emphasis continuing league-wide",
                        "Power play strategies becoming more sophisticated",
                        "Defensive systems adapting to offensive innovations",
                        "Young players making immediate impact"
                    ],
                    'hot_topics': [
                        "Trade deadline speculation heating up",
                        "Salary cap challenges affecting team decisions",
                        "International player development programs expanding",
                        "Analytics driving strategic decisions"
                    ],
                    'stats': [
                        "League scoring up 3% compared to last season",
                        "Power play conversion rate averaging 21.5%",
                        "Goaltender save percentages remain high at .912",
                        "Average game time 2:28 with faster pace of play"
                    ]
                }
            
            return data
            
        except Exception as e:
            return {
                'standings': ["League data loading..."],
                'trends': ["Statistical analysis in progress..."],
                'hot_topics': ["News aggregation updating..."],
                'stats': ["Performance metrics compiling..."]
            }

    def _create_standings_tab(self, parent):
        """Create the Standings tab content"""
        standings_frame = tk.Frame(parent, bg=self.theme.colors.background)
        standings_frame.pack(fill='both', expand=True, padx=16, pady=16)
        
        # Header
        headline = tk.Label(standings_frame, text="🏆 League Standings",
                           font=self.theme.fonts['heading'],
                           fg=self.theme.colors.primary,
                           bg=self.theme.colors.background)
        headline.pack(anchor='w', pady=(0, 16))
        
        # Create standings container
        standings_container = tk.Frame(standings_frame, bg=self.theme.colors.background)
        standings_container.pack(fill='both', expand=True)
        
        # Get league standings data
        standings_data = self._get_standings_data()
        
        # Create standings sections
        for division_name, teams in standings_data.items():
            # Division header
            div_frame = tk.Frame(standings_container, bg=self.theme.colors.secondary,
                               relief='flat', bd=1)
            div_frame.pack(fill='x', pady=4)
            
            div_header = tk.Label(div_frame, text=f"🏒 {division_name}",
                                font=self.theme.fonts['subheading'],
                                fg=self.theme.colors.primary,
                                bg=self.theme.colors.secondary)
            div_header.pack(anchor='w', padx=12, pady=8)
            
            # Teams in division
            for i, team_data in enumerate(teams):
                team_frame = tk.Frame(div_frame, bg=self.theme.colors.secondary)
                team_frame.pack(fill='x', padx=12, pady=2)
                
                # Team position and name
                pos_label = tk.Label(team_frame, text=f"{i+1}.",
                                   font=self.theme.fonts['body'],
                                   fg=self.theme.colors.text_light,
                                   bg=self.theme.colors.secondary,
                                   width=3)
                pos_label.pack(side='left', anchor='w')
                
                team_label = tk.Label(team_frame, text=team_data['name'],
                                    font=self.theme.fonts['body'],
                                    fg=self.theme.colors.text_light if team_data['name'] != self.parent.user_team.team_name else self.theme.colors.primary,
                                    bg=self.theme.colors.secondary)
                team_label.pack(side='left', anchor='w', padx=(5, 0))
                
                # Record
                record_label = tk.Label(team_frame, text=team_data['record'],
                                      font=self.theme.fonts['caption'],
                                      fg=self.theme.colors.text_light,
                                      bg=self.theme.colors.secondary)
                record_label.pack(side='right', anchor='e')

    def _create_stat_leaders_tab(self, parent):
        """Create the Stat Leaders tab content"""
        leaders_frame = tk.Frame(parent, bg=self.theme.colors.background)
        leaders_frame.pack(fill='both', expand=True, padx=16, pady=16)
        
        # Header
        headline = tk.Label(leaders_frame, text="👑 Statistical Leaders",
                           font=self.theme.fonts['heading'],
                           fg=self.theme.colors.primary,
                           bg=self.theme.colors.background)
        headline.pack(anchor='w', pady=(0, 16))
        
        # Create two columns for team and league leaders
        columns_frame = tk.Frame(leaders_frame, bg=self.theme.colors.background)
        columns_frame.pack(fill='both', expand=True)
        
        # Team leaders column
        team_column = tk.Frame(columns_frame, bg=self.theme.colors.background)
        team_column.pack(side='left', fill='both', expand=True, padx=(0, 8))
        
        team_header = tk.Label(team_column, text="🏒 Team Leaders",
                             font=self.theme.fonts['subheading'],
                             fg=self.theme.colors.primary,
                             bg=self.theme.colors.background)
        team_header.pack(anchor='w', pady=(0, 12))
        
        # Get team leaders data
        team_leaders = self._get_team_leaders_data()
        
        for category, leader_data in team_leaders.items():
            leader_frame = tk.Frame(team_column, bg=self.theme.colors.secondary,
                                  relief='flat', bd=1)
            leader_frame.pack(fill='x', pady=4)
            
            # Category header
            cat_label = tk.Label(leader_frame, text=category,
                               font=self.theme.fonts['body'],
                               fg=self.theme.colors.primary,
                               bg=self.theme.colors.secondary)
            cat_label.pack(anchor='w', padx=12, pady=(8, 4))
            
            # Leader info
            leader_label = tk.Label(leader_frame, text=f"{leader_data['player']} - {leader_data['value']}",
                                  font=self.theme.fonts['caption'],
                                  fg=self.theme.colors.text_light,
                                  bg=self.theme.colors.secondary)
            leader_label.pack(anchor='w', padx=12, pady=(0, 8))
        
        # League leaders column
        league_column = tk.Frame(columns_frame, bg=self.theme.colors.background)
        league_column.pack(side='right', fill='both', expand=True, padx=(8, 0))
        
        league_header = tk.Label(league_column, text="🌟 League Leaders",
                               font=self.theme.fonts['subheading'],
                               fg=self.theme.colors.primary,
                               bg=self.theme.colors.background)
        league_header.pack(anchor='w', pady=(0, 12))
        
        # Get league leaders data
        league_leaders = self._get_league_leaders_data()
        
        for category, leader_data in league_leaders.items():
            leader_frame = tk.Frame(league_column, bg=self.theme.colors.secondary,
                                  relief='flat', bd=1)
            leader_frame.pack(fill='x', pady=4)
            
            # Category header
            cat_label = tk.Label(leader_frame, text=category,
                               font=self.theme.fonts['body'],
                               fg=self.theme.colors.primary,
                               bg=self.theme.colors.secondary)
            cat_label.pack(anchor='w', padx=12, pady=(8, 4))
            
            # Leader info
            leader_label = tk.Label(leader_frame, text=f"{leader_data['player']} ({leader_data['team']}) - {leader_data['value']}",
                                  font=self.theme.fonts['caption'],
                                  fg=self.theme.colors.text_light,
                                  bg=self.theme.colors.secondary)
            leader_label.pack(anchor='w', padx=12, pady=(0, 8))

    def _get_standings_data(self):
        """Get current league standings data"""
        try:
            # Get teams from the league
            if hasattr(self.parent, 'league') and self.parent.league:
                # Get all NHL teams (league_name = "National Hockey League")
                nhl_teams = [team for team in self.parent.league.teams 
                           if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
                
                # If no league_name attribute, use all teams from the main league
                if not nhl_teams:
                    nhl_teams = self.parent.league.teams[:32]  # Assume first 32 are NHL teams
                
                # Group teams by division
                divisions = {}
                for team in nhl_teams:
                    # Use division if available, otherwise create logical groupings
                    if hasattr(team, 'division') and team.division:
                        division_name = f"{team.conference} - {team.division}" if hasattr(team, 'conference') else team.division
                    elif hasattr(team, 'conference') and team.conference:
                        division_name = f"{team.conference} Conference"
                    else:
                        # Fallback grouping for teams without proper division/conference data
                        division_name = "Eastern Conference" if hash(team.team_name) % 2 == 0 else "Western Conference"
                    
                    if division_name not in divisions:
                        divisions[division_name] = []
                    
                    # Calculate points (2 for win, 1 for tie/OT loss)
                    points = team.wins * 2 + getattr(team, 'ties', 0) + getattr(team, 'ot_losses', 0)
                    
                    divisions[division_name].append({
                        'name': team.team_name,
                        'record': f"{team.wins}-{team.losses}-{getattr(team, 'ties', 0)}",
                        'points': points,
                        'wins': team.wins,
                        'losses': team.losses,
                        'ties': getattr(team, 'ties', 0),
                        'games_played': team.wins + team.losses + getattr(team, 'ties', 0)
                    })
                
                # Sort teams within each division by points (then by wins as tiebreaker)
                for division in divisions:
                    divisions[division].sort(key=lambda x: (x['points'], x['wins']), reverse=True)
                
                return divisions
                
        except Exception as e:
            print(f"Error getting standings data: {e}")
            
        # Minimal fallback - should rarely be used
        return {
            "League Standings": [
                {'name': 'No data available', 'record': '0-0-0', 'points': 0}
            ]
        }

    def _get_team_leaders_data(self):
        """Get team statistical leaders"""
        try:
            if hasattr(self.parent, 'user_team') and self.parent.user_team:
                roster = self.parent.user_team.roster
                if roster:
                    # Calculate actual leaders from roster
                    goals_leader = max(roster, key=lambda p: getattr(p, 'goals', 0))
                    assists_leader = max(roster, key=lambda p: getattr(p, 'assists', 0))
                    points_leader = max(roster, key=lambda p: getattr(p, 'goals', 0) + getattr(p, 'assists', 0))
                    
                    return {
                        "Goals": {
                            'player': goals_leader.full_name,
                            'value': getattr(goals_leader, 'goals', 0)
                        },
                        "Assists": {
                            'player': assists_leader.full_name,
                            'value': getattr(assists_leader, 'assists', 0)
                        },
                        "Points": {
                            'player': points_leader.full_name,
                            'value': getattr(points_leader, 'goals', 0) + getattr(points_leader, 'assists', 0)
                        }
                    }
        except:
            pass
            
        # Fallback data
        return {
            "Goals": {'player': 'David Pastrnak', 'value': 18},
            "Assists": {'player': 'Brad Marchand', 'value': 24},
            "Points": {'player': 'David Pastrnak', 'value': 35},
            "Plus/Minus": {'player': 'Charlie McAvoy', 'value': '+12'},
            "PIM": {'player': 'Trent Frederic', 'value': 45}
        }

    def _get_league_leaders_data(self):
        """Get league statistical leaders"""
        try:
            if hasattr(self.parent, 'league') and self.parent.league:
                all_players = []
                for team in self.parent.league.teams:
                    all_players.extend(team.roster)
                
                if all_players:
                    goals_leader = max(all_players, key=lambda p: getattr(p, 'goals', 0))
                    assists_leader = max(all_players, key=lambda p: getattr(p, 'assists', 0))
                    points_leader = max(all_players, key=lambda p: getattr(p, 'goals', 0) + getattr(p, 'assists', 0))
                    
                    return {
                        "Goals": {
                            'player': goals_leader.full_name,
                            'team': goals_leader.team_name,
                            'value': getattr(goals_leader, 'goals', 0)
                        },
                        "Assists": {
                            'player': assists_leader.full_name,
                            'team': assists_leader.team_name,
                            'value': getattr(assists_leader, 'assists', 0)
                        },
                        "Points": {
                            'player': points_leader.full_name,
                            'team': points_leader.team_name,
                            'value': getattr(points_leader, 'goals', 0) + getattr(points_leader, 'assists', 0)
                        }
                    }
        except:
            pass
            
        # Fallback data
        return {
            "Goals": {'player': 'Connor McDavid', 'team': 'Edmonton Oilers', 'value': 25},
            "Assists": {'player': 'Erik Karlsson', 'team': 'San Jose Sharks', 'value': 32},
            "Points": {'player': 'Connor McDavid', 'team': 'Edmonton Oilers', 'value': 47},
            "Wins": {'player': 'Frederik Andersen', 'team': 'Carolina Hurricanes', 'value': 16},
            "Save %": {'player': 'Linus Ullmark', 'team': 'Boston Bruins', 'value': '.938'}
        }
