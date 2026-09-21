# enhanced_visual_components.py
# Advanced visual components for immersive hockey management experience

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Tuple
import random
from datetime import date, datetime
from visual_identity_system import HockeyAtmosphereSystem, VisualTheme
from game_classes import PlayerPosition

class ImmersivePlayerCard:
    """Player card with team colors, personality, and storytelling"""
    
    def __init__(self, parent, player, team_theme: VisualTheme):
        self.parent = parent
        self.player = player
        self.theme = team_theme
        
    def create_card(self) -> tk.Frame:
        """Create immersive player card with visual hierarchy"""
        card_frame = tk.Frame(self.parent, bg=self.theme.colors.secondary,
                             relief='flat', bd=1, padx=0, pady=0)
        
        # Player header with team colors
        header_frame = tk.Frame(card_frame, bg=self.theme.colors.primary, height=6)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Main content area
        content_frame = tk.Frame(card_frame, bg=self.theme.colors.secondary, padx=16, pady=12)
        content_frame.pack(fill='both', expand=True)
        
        # Player info row
        info_row = tk.Frame(content_frame, bg=self.theme.colors.secondary)
        info_row.pack(fill='x', pady=(0, 8))
        
        # Player number (if available)
        if hasattr(self.player, 'jersey_number'):
            number_label = tk.Label(info_row, text=f"#{self.player.jersey_number}",
                                   font=self.theme.fonts['number'],
                                   fg=self.theme.colors.primary,
                                   bg=self.theme.colors.secondary)
            number_label.pack(side='left', padx=(0, 8))
        
        # Player name and position
        name_pos_frame = tk.Frame(info_row, bg=self.theme.colors.secondary)
        name_pos_frame.pack(side='left', fill='x', expand=True)
        
        name_label = tk.Label(name_pos_frame, text=self.player.full_name,
                             font=self.theme.fonts['subheading'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.secondary)
        name_label.pack(anchor='w')
        
        position_label = tk.Label(name_pos_frame, text=self.player.primary_position.value,
                                 font=self.theme.fonts['caption'],
                                 fg=self.theme.colors.primary,
                                 bg=self.theme.colors.secondary)
        position_label.pack(anchor='w')
        
        # Age and handedness
        details_label = tk.Label(info_row, text=f"Age {self.player.age} • {getattr(self.player, 'handedness', 'R')}",
                                font=self.theme.fonts['caption'],
                                fg=self.theme.colors.text_light,
                                bg=self.theme.colors.secondary)
        details_label.pack(side='right')
        
        # Key stats row
        stats_frame = tk.Frame(content_frame, bg=self.theme.colors.background,
                              relief='flat', bd=1, padx=8, pady=6)
        stats_frame.pack(fill='x', pady=(4, 0))
        
        # Show position-specific key stats
        key_stats = self._get_key_stats()
        for i, (stat_name, stat_value, context) in enumerate(key_stats):
            stat_container = tk.Frame(stats_frame, bg=self.theme.colors.background)
            stat_container.pack(side='left', padx=(0, 16) if i < len(key_stats)-1 else (0, 0))
            
            value_label = tk.Label(stat_container, text=str(stat_value),
                                  font=self.theme.fonts['number'],
                                  fg=self._get_stat_color(context),
                                  bg=self.theme.colors.background)
            value_label.pack()
            
            name_label = tk.Label(stat_container, text=stat_name,
                                 font=self.theme.fonts['caption'],
                                 fg=self.theme.colors.text_light,
                                 bg=self.theme.colors.background)
            name_label.pack()
        
        return card_frame
    
    def _get_key_stats(self) -> List[Tuple[str, int, str]]:
        """Get key stats based on position"""
        if self.player.primary_position == PlayerPosition.GOALIE:
            return [
                ("Overall", self.player.overall_rating(), "primary"),
                ("Goaltending", getattr(self.player, 'goaltending', 0), "positive"),
                ("Reflexes", getattr(self.player, 'reflexes', 0), "positive")
            ]
        else:
            return [
                ("Overall", self.player.overall_rating(), "primary"),
                ("Skating", getattr(self.player, 'skating', 0), "neutral"),
                ("Shooting", getattr(self.player, 'shooting', 0), "positive")
            ]
    
    def _get_stat_color(self, context: str) -> str:
        """Get color for stat based on context"""
        colors = {
            'primary': self.theme.colors.primary,
            'positive': self.theme.colors.success,
            'neutral': self.theme.colors.text_light,
            'negative': self.theme.colors.danger
        }
        return colors.get(context, self.theme.colors.text_light)

class AtmosphericTeamStandings:
    """Team standings with visual storytelling and context"""
    
    def __init__(self, parent, league, user_team, theme: VisualTheme):
        self.parent = parent
        self.league = league
        self.user_team = user_team
        self.theme = theme
        
    def create_standings_widget(self) -> tk.Frame:
        """Create immersive standings widget"""
        standings_frame = tk.Frame(self.parent, bg=self.theme.colors.background)
        
        # Header with atmosphere
        header_frame = tk.Frame(standings_frame, bg=self.theme.colors.primary, height=32)
        header_frame.pack(fill='x', pady=(0, 8))
        header_frame.pack_propagate(False)
        
        header_label = tk.Label(header_frame, text="🏆 League Standings",
                               font=self.theme.fonts['heading'],
                               fg=self.theme.colors.text_light,
                               bg=self.theme.colors.primary)
        header_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Standings list with visual hierarchy
        standings_list = tk.Frame(standings_frame, bg=self.theme.colors.background)
        standings_list.pack(fill='both', expand=True, padx=8)
        
        # Get sorted standings
        sorted_teams = self._get_sorted_standings()
        
        for i, (team_name, record) in enumerate(sorted_teams[:8]):  # Top 8
            team_frame = self._create_team_standing_row(standings_list, i+1, team_name, record)
            team_frame.pack(fill='x', pady=2)
        
        return standings_frame
    
    def _create_team_standing_row(self, parent, position: int, team_name: str, record: Dict) -> tk.Frame:
        """Create individual team standing row"""
        # Highlight user team
        is_user_team = team_name == self.user_team.team_name
        bg_color = self.theme.colors.primary if is_user_team else self.theme.colors.secondary
        text_color = self.theme.colors.text_light
        
        row_frame = tk.Frame(parent, bg=bg_color, relief='flat', bd=1, padx=12, pady=6)
        
        # Position
        pos_label = tk.Label(row_frame, text=str(position),
                            font=self.theme.fonts['number'],
                            fg=self._get_position_color(position),
                            bg=bg_color, width=3)
        pos_label.pack(side='left', padx=(0, 12))
        
        # Team name
        team_label = tk.Label(row_frame, text=team_name,
                             font=self.theme.fonts['body'],
                             fg=text_color, bg=bg_color)
        team_label.pack(side='left', fill='x', expand=True, anchor='w')
        
        # Record
        wins = record.get('W', 0)
        losses = record.get('L', 0)
        otl = record.get('OTL', 0)
        points = record.get('Points', 0)
        
        record_text = f"{wins}-{losses}-{otl}"
        record_label = tk.Label(row_frame, text=record_text,
                               font=self.theme.fonts['body'],
                               fg=text_color, bg=bg_color)
        record_label.pack(side='right', padx=(8, 0))
        
        # Points
        points_label = tk.Label(row_frame, text=f"{points} pts",
                               font=self.theme.fonts['number'],
                               fg=self.theme.colors.success if is_user_team else text_color,
                               bg=bg_color)
        points_label.pack(side='right', padx=(8, 0))
        
        return row_frame
    
    def _get_sorted_standings(self) -> List[Tuple[str, Dict]]:
        """Get sorted team standings"""
        standings_list = []
        for team_name, record in self.league.standings.items():
            standings_list.append((team_name, record))
        
        # Sort by points, then by wins
        standings_list.sort(key=lambda x: (x[1].get('Points', 0), x[1].get('W', 0)), reverse=True)
        return standings_list
    
    def _get_position_color(self, position: int) -> str:
        """Get color based on playoff position"""
        if position <= 8:  # Playoff spots
            return self.theme.colors.success
        elif position <= 16:  # Bubble teams
            return self.theme.colors.warning
        else:  # Lottery teams
            return self.theme.colors.danger

class GameHighlightWidget:
    """Widget for displaying game highlights with atmosphere"""
    
    def __init__(self, parent, game_data: Dict, theme: VisualTheme):
        self.parent = parent
        self.game_data = game_data
        self.theme = theme
        
    def create_highlight_widget(self) -> tk.Frame:
        """Create game highlight widget"""
        highlight_frame = tk.Frame(self.parent, bg=self.theme.colors.secondary,
                                  relief='flat', bd=1)
        
        # Game header
        header_frame = tk.Frame(highlight_frame, bg=self.theme.colors.primary, height=24)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Game info
        home_team = self.game_data.get('home_team', 'Home')
        away_team = self.game_data.get('away_team', 'Away')
        home_score = self.game_data.get('home_score', 0)
        away_score = self.game_data.get('away_score', 0)
        
        game_info = f"{away_team} @ {home_team}"
        game_label = tk.Label(header_frame, text=game_info,
                             font=self.theme.fonts['caption'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.primary)
        game_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Content area
        content_frame = tk.Frame(highlight_frame, bg=self.theme.colors.secondary, padx=12, pady=8)
        content_frame.pack(fill='both', expand=True)
        
        # Score display
        score_frame = tk.Frame(content_frame, bg=self.theme.colors.secondary)
        score_frame.pack(fill='x', pady=(0, 8))
        
        score_text = f"{away_team} {away_score} - {home_score} {home_team}"
        score_label = tk.Label(score_frame, text=score_text,
                              font=self.theme.fonts['subheading'],
                              fg=self.theme.colors.text_light,
                              bg=self.theme.colors.secondary)
        score_label.pack()
        
        # Game highlights
        highlights = self.game_data.get('highlights', [])
        if highlights:
            for highlight in highlights[:3]:  # Show top 3
                highlight_label = tk.Label(content_frame, text=f"⭐ {highlight}",
                                          font=self.theme.fonts['caption'],
                                          fg=self.theme.colors.text_light,
                                          bg=self.theme.colors.secondary,
                                          wraplength=200, justify='left')
                highlight_label.pack(anchor='w', pady=1)
        
        return highlight_frame

class ImmersiveNewsPanel:
    """News panel with storytelling and visual impact"""
    
    def __init__(self, parent, news_items: List[str], theme: VisualTheme):
        self.parent = parent
        self.news_items = news_items
        self.theme = theme
        
    def create_news_panel(self) -> tk.Frame:
        """Create immersive news panel"""
        news_frame = tk.Frame(self.parent, bg=self.theme.colors.background)
        
        # News header
        header_frame = tk.Frame(news_frame, bg=self.theme.colors.arena_shadow, height=32)
        header_frame.pack(fill='x', pady=(0, 8))
        header_frame.pack_propagate(False)
        
        header_label = tk.Label(header_frame, text="📰 Breaking News",
                               font=self.theme.fonts['heading'],
                               fg=self.theme.colors.spotlight,
                               bg=self.theme.colors.arena_shadow)
        header_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # News ticker effect
        ticker_frame = tk.Frame(news_frame, bg=self.theme.colors.primary, height=4)
        ticker_frame.pack(fill='x', pady=(0, 8))
        
        # News items
        news_content = tk.Frame(news_frame, bg=self.theme.colors.background)
        news_content.pack(fill='both', expand=True, padx=8)
        
        for i, news_item in enumerate(self.news_items[:5]):  # Show latest 5
            news_row = self._create_news_item(news_content, news_item, i)
            news_row.pack(fill='x', pady=2)
        
        return news_frame
    
    def _create_news_item(self, parent, news_text: str, index: int) -> tk.Frame:
        """Create individual news item"""
        item_frame = tk.Frame(parent, bg=self.theme.colors.secondary,
                             relief='flat', bd=1, padx=8, pady=6)
        
        # News icon based on content
        icon = self._get_news_icon(news_text)
        icon_label = tk.Label(item_frame, text=icon,
                             font=('Segoe UI', 12),
                             bg=self.theme.colors.secondary)
        icon_label.pack(side='left', padx=(0, 8))
        
        # News text
        news_label = tk.Label(item_frame, text=news_text,
                             font=self.theme.fonts['body'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.secondary,
                             wraplength=300, justify='left')
        news_label.pack(side='left', fill='x', expand=True, anchor='w')
        
        # Timestamp
        time_label = tk.Label(item_frame, text=f"{index+1}h ago",
                             font=self.theme.fonts['caption'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.secondary)
        time_label.pack(side='right')
        
        return item_frame
    
    def _get_news_icon(self, news_text: str) -> str:
        """Get appropriate icon for news item"""
        news_lower = news_text.lower()
        if 'trade' in news_lower:
            return '🔄'
        elif 'goal' in news_lower or 'score' in news_lower:
            return '🥅'
        elif 'win' in news_lower or 'won' in news_lower:
            return '🏆'
        elif 'injury' in news_lower:
            return '🏥'
        elif 'sign' in news_lower or 'contract' in news_lower:
            return '📝'
        else:
            return '📰'

class AtmosphericScheduleWidget:
    """Schedule widget with atmosphere and team context"""
    
    def __init__(self, parent, schedule_data: List[Dict], user_team, theme: VisualTheme):
        self.parent = parent
        self.schedule_data = schedule_data
        self.user_team = user_team
        self.theme = theme
        
    def create_schedule_widget(self) -> tk.Frame:
        """Create atmospheric schedule widget"""
        schedule_frame = tk.Frame(self.parent, bg=self.theme.colors.background)
        
        # Header with ice effect
        header_frame = tk.Frame(schedule_frame, bg=self.theme.colors.ice_blue, height=28)
        header_frame.pack(fill='x', pady=(0, 8))
        header_frame.pack_propagate(False)
        
        header_label = tk.Label(header_frame, text="🏒 Upcoming Games",
                               font=self.theme.fonts['heading'],
                               fg=self.theme.colors.text_dark,
                               bg=self.theme.colors.ice_blue)
        header_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Games list
        games_content = tk.Frame(schedule_frame, bg=self.theme.colors.background)
        games_content.pack(fill='both', expand=True, padx=8)
        
        # Show next 3 games
        upcoming_games = self._get_upcoming_games()
        for i, game in enumerate(upcoming_games[:3]):
            game_row = self._create_game_row(games_content, game, i)
            game_row.pack(fill='x', pady=3)
        
        return schedule_frame
    
    def _create_game_row(self, parent, game: Dict, index: int) -> tk.Frame:
        """Create individual game row"""
        is_home = game.get('home_team') == self.user_team.team_name
        opponent = game.get('away_team') if is_home else game.get('home_team')
        
        game_frame = tk.Frame(parent, bg=self.theme.colors.secondary,
                             relief='flat', bd=1, padx=12, pady=8)
        
        # Date
        game_date = game.get('date', 'TBD')
        date_label = tk.Label(game_frame, text=str(game_date),
                             font=self.theme.fonts['caption'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.secondary)
        date_label.pack(side='left', padx=(0, 12))
        
        # Opponent and venue
        venue_text = "vs." if is_home else "@"
        game_text = f"{venue_text} {opponent}"
        game_label = tk.Label(game_frame, text=game_text,
                             font=self.theme.fonts['body'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.secondary)
        game_label.pack(side='left', fill='x', expand=True, anchor='w')
        
        # Home indicator
        if is_home:
            home_indicator = tk.Label(game_frame, text="🏠",
                                     font=('Segoe UI', 12),
                                     bg=self.theme.colors.secondary)
            home_indicator.pack(side='right')
        
        return game_frame
    
    def _get_upcoming_games(self) -> List[Dict]:
        """Get upcoming games for the user team"""
        try:
            # Try to get actual upcoming games from schedule
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'league'):
                user_team_name = self.user_team.team_name
                today = getattr(self.parent.game_manager, 'current_date', None)
                upcoming_games = []
                
                # Look for next 3-5 scheduled games
                for team in self.parent.game_manager.league.teams:
                    if hasattr(team, 'schedule'):
                        for game in team.schedule:
                            if (hasattr(game, 'home_team') and hasattr(game, 'away_team') and 
                                hasattr(game, 'date') and (game.home_team == user_team_name or game.away_team == user_team_name)):
                                if today is None or game.date >= today:
                                    upcoming_games.append({
                                        'date': str(game.date),
                                        'home_team': game.home_team,
                                        'away_team': game.away_team
                                    })
                
                # Sort by date and return first few games
                upcoming_games.sort(key=lambda x: x['date'])
                return upcoming_games[:3]  # Return next 3 games
                
        except Exception as e:
            pass
        
        # Fallback if no schedule data available
        return [
            {'date': 'Schedule TBD', 'home_team': self.user_team.team_name, 'away_team': 'TBD'},
            {'date': 'Season Setup', 'home_team': 'TBD', 'away_team': self.user_team.team_name},
            {'date': 'Games Pending', 'home_team': self.user_team.team_name, 'away_team': 'TBD'}
        ]
