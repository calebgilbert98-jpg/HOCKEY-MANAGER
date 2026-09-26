# visual_identity_system.py
# Comprehensive visual identity and atmosphere system for Hockey Manager

import tkinter as tk
from tkinter import ttk
import random
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, date
import math

@dataclass
class TeamColorScheme:
    """Enhanced team color scheme with emotional context"""
    primary: str
    secondary: str
    accent: str
    background: str
    text_light: str
    text_dark: str
    success: str
    warning: str
    danger: str
    
    # Atmospheric colors
    ice_blue: str = "#E8F4F8"
    arena_shadow: str = "#1A1A1A"
    spotlight: str = "#FFFACD"
    crowd_energy: str = "#FF6B35"

@dataclass
class VisualTheme:
    """Complete visual theme with atmospheric elements"""
    colors: TeamColorScheme
    fonts: Dict[str, Tuple[str, int, str]]
    shadows: Dict[str, str]
    gradients: Dict[str, str]
    animations: Dict[str, Dict]

class HockeyAtmosphereSystem:
    """Creates atmospheric visual elements and team identity"""
    
    def __init__(self):
        self.team_identities = self._initialize_team_identities()
        self.current_theme = None
        self.animation_queue = []
        
    def _initialize_team_identities(self) -> Dict[str, TeamColorScheme]:
        """Initialize NHL team color schemes with atmospheric elements"""
        return {
            "Boston Bruins": TeamColorScheme(
                primary="#FFB81C", secondary="#000000", accent="#FFFFFF",
                background="#1A1A1A", text_light="#FFFFFF", text_dark="#000000",
                success="#3fb950", warning="#d29922", danger="#f85149",
                ice_blue="#E8F4F8", arena_shadow="#0D0D0D", spotlight="#FFFACD"
            ),
            "Montreal Canadiens": TeamColorScheme(
                primary="#AF1E2D", secondary="#192168", accent="#FFFFFF",
                background="#1A1A1A", text_light="#FFFFFF", text_dark="#AF1E2D",
                success="#3fb950", warning="#d29922", danger="#f85149",
                ice_blue="#E8F4F8", arena_shadow="#0D0D0D", spotlight="#FFFACD"
            ),
            "Toronto Maple Leafs": TeamColorScheme(
                primary="#003E7E", secondary="#FFFFFF", accent="#003E7E",
                background="#1A1A1A", text_light="#FFFFFF", text_dark="#003E7E",
                success="#3fb950", warning="#d29922", danger="#f85149",
                ice_blue="#E8F4F8", arena_shadow="#0D0D0D", spotlight="#FFFACD"
            ),
            "Tampa Bay Lightning": TeamColorScheme(
                primary="#002868", secondary="#FFFFFF", accent="#000000",
                background="#1A1A1A", text_light="#FFFFFF", text_dark="#002868",
                success="#3fb950", warning="#d29922", danger="#f85149",
                ice_blue="#E8F4F8", arena_shadow="#0D0D0D", spotlight="#FFFACD"
            ),
            "Pittsburgh Penguins": TeamColorScheme(
                primary="#000000", secondary="#FCB514", accent="#FFFFFF",
                background="#1A1A1A", text_light="#FFFFFF", text_dark="#000000",
                success="#3fb950", warning="#d29922", danger="#f85149",
                ice_blue="#E8F4F8", arena_shadow="#0D0D0D", spotlight="#FFFACD"
            ),
            "Chicago Blackhawks": TeamColorScheme(
                primary="#CF0A2C", secondary="#000000", accent="#FFFFFF",
                background="#1A1A1A", text_light="#FFFFFF", text_dark="#CF0A2C",
                success="#3fb950", warning="#d29922", danger="#f85149",
                ice_blue="#E8F4F8", arena_shadow="#0D0D0D", spotlight="#FFFACD"
            ),
            # Add more teams as needed
        }
    
    def get_team_colors(self, team_name: str) -> Optional[TeamColorScheme]:
        """Get team color scheme with fallback to default"""
        return self.team_identities.get(team_name, self._get_default_scheme())
    
    def _get_default_scheme(self) -> TeamColorScheme:
        """Default color scheme for unknown teams"""
        return TeamColorScheme(
            primary="#f85149", secondary="#1F1F1F", accent="#FFFFFF",
            background="#181818", text_light="#E0E0E0", text_dark="#f85149",
            success="#3fb950", warning="#d29922", danger="#f85149",
            ice_blue="#E8F4F8", arena_shadow="#0D0D0D", spotlight="#FFFACD"
        )
    
    def create_atmospheric_theme(self, team_name: str) -> VisualTheme:
        """Create complete atmospheric theme for a team"""
        colors = self.get_team_colors(team_name)
        
        fonts = {
            'title': ('Segoe UI', 24, 'bold'),
            'heading': ('Segoe UI', 16, 'bold'),
            'subheading': ('Segoe UI', 12, 'bold'),
            'body': ('Segoe UI', 10, 'normal'),
            'caption': ('Segoe UI', 9, 'normal'),
            'number': ('Consolas', 12, 'bold'),  # For stats
            'logo': ('Impact', 20, 'bold'),      # For team initials
        }
        
        shadows = {
            'card': '#2A2A2A',      # Dark gray for card shadows
            'button': '#333333',    # Lighter gray for button shadows
            'text': '#1A1A1A',     # Very dark gray for text shadows
            'deep': '#0F0F0F'      # Almost black for deep shadows
        }
        
        gradients = {
            'primary': f"linear-gradient(135deg, {colors.primary} 0%, {colors.secondary} 100%)",
            'background': f"linear-gradient(180deg, {colors.background} 0%, {colors.arena_shadow} 100%)",
            'card': f"linear-gradient(145deg, {colors.background} 0%, {colors.secondary} 100%)",
            'ice': f"linear-gradient(90deg, {colors.ice_blue} 0%, #FFFFFF 50%, {colors.ice_blue} 100%)"
        }
        
        animations = {
            'fade_in': {'duration': 300, 'easing': 'ease-in'},
            'slide_up': {'duration': 400, 'easing': 'ease-out'},
            'bounce': {'duration': 600, 'easing': 'ease-in-out'},
            'pulse': {'duration': 1000, 'easing': 'ease-in-out', 'repeat': True}
        }
        
        return VisualTheme(colors=colors, fonts=fonts, shadows=shadows, 
                          gradients=gradients, animations=animations)

class VisualHierarchyManager:
    """Manages visual hierarchy and information architecture"""
    
    def __init__(self, theme: VisualTheme):
        self.theme = theme
        
    def create_card_with_hierarchy(self, parent, title: str, content_type: str = "default") -> tk.Frame:
        """Create a card with proper visual hierarchy"""
        card = tk.Frame(parent, bg=self.theme.colors.secondary, relief='flat', bd=0)
        
        # Add subtle shadow effect
        shadow_frame = tk.Frame(parent, bg=self.theme.shadows['card'], height=2)
        
        # Title bar with team color accent
        title_bar = tk.Frame(card, bg=self.theme.colors.primary, height=4)
        title_bar.pack(fill='x', pady=(0, 8))
        
        # Title label with proper typography
        title_label = tk.Label(card, text=title,
                              font=self.theme.fonts['heading'],
                              fg=self.theme.colors.text_light,
                              bg=self.theme.colors.secondary)
        title_label.pack(anchor='w', padx=16, pady=(8, 0))
        
        # Content area
        content_frame = tk.Frame(card, bg=self.theme.colors.secondary)
        content_frame.pack(fill='both', expand=True, padx=16, pady=16)
        
        return card, content_frame
    
    def create_stat_display(self, parent, stat_name: str, stat_value: str, 
                           context: str = "neutral") -> tk.Frame:
        """Create visually appealing stat display"""
        stat_frame = tk.Frame(parent, bg=self.theme.colors.background, 
                             relief='flat', bd=1, padx=12, pady=8)
        
        # Stat value (large, prominent)
        value_label = tk.Label(stat_frame, text=stat_value,
                              font=self.theme.fonts['number'],
                              fg=self._get_context_color(context),
                              bg=self.theme.colors.background)
        value_label.pack()
        
        # Stat name (smaller, muted)
        name_label = tk.Label(stat_frame, text=stat_name,
                             font=self.theme.fonts['caption'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.background)
        name_label.pack()
        
        return stat_frame
    
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

class AnimationManager:
    """Handles smooth transitions and micro-interactions"""
    
    def __init__(self, root):
        self.root = root
        self.active_animations = {}
        
    def fade_in(self, widget, duration: int = 300):
        """Fade in animation"""
        # Simulate fade by changing alpha (limited in tkinter)
        self._animate_property(widget, 'alpha', 0, 1, duration)
    
    def slide_up(self, widget, distance: int = 20, duration: int = 400):
        """Slide up animation"""
        original_y = widget.winfo_y()
        start_y = original_y + distance
        self._animate_movement(widget, start_y, original_y, duration, 'y')
    
    def pulse_effect(self, widget, scale_factor: float = 1.05, duration: int = 1000):
        """Pulsing effect for important elements"""
        self._animate_scale(widget, 1.0, scale_factor, duration, repeat=True)
    
    def _animate_property(self, widget, property_name: str, start_value: float, 
                         end_value: float, duration: int):
        """Animate a widget property over time"""
        steps = 20
        step_duration = duration // steps
        step_size = (end_value - start_value) / steps
        
        def animate_step(step: int):
            if step <= steps:
                current_value = start_value + (step_size * step)
                # Apply the property change (limited options in tkinter)
                if property_name == 'alpha':
                    # Simulate alpha by adjusting colors
                    pass
                self.root.after(step_duration, lambda: animate_step(step + 1))
        
        animate_step(0)
    
    def _animate_movement(self, widget, start_pos: int, end_pos: int, 
                         duration: int, axis: str):
        """Animate widget movement"""
        steps = 20
        step_duration = duration // steps
        step_size = (end_pos - start_pos) / steps
        
        def animate_step(step: int):
            if step <= steps:
                current_pos = start_pos + (step_size * step)
                if axis == 'y':
                    widget.place(y=int(current_pos))
                elif axis == 'x':
                    widget.place(x=int(current_pos))
                self.root.after(step_duration, lambda: animate_step(step + 1))
        
        animate_step(0)
    
    def _animate_scale(self, widget, start_scale: float, end_scale: float, 
                      duration: int, repeat: bool = False):
        """Animate widget scaling effect"""
        # Simplified scaling by adjusting font size for labels
        if isinstance(widget, tk.Label):
            current_font = widget.cget('font')
            if isinstance(current_font, str):
                return  # Can't modify string fonts easily
                
            steps = 10
            step_duration = duration // (steps * 2)  # Forward and backward
            
            def scale_step(step: int, direction: int):
                if step <= steps:
                    scale = start_scale + ((end_scale - start_scale) * step / steps * direction)
                    # Adjust font size to simulate scaling
                    try:
                        font_family, font_size, font_style = current_font
                        new_size = int(font_size * scale)
                        widget.config(font=(font_family, new_size, font_style))
                    except:
                        pass
                    
                    self.root.after(step_duration, lambda: scale_step(step + 1, direction))
                elif direction == 1:
                    # Start reverse animation
                    scale_step(0, -1)
                elif repeat:
                    # Restart animation
                    self.root.after(500, lambda: scale_step(0, 1))

class ContextualElementsManager:
    """Manages atmospheric and contextual UI elements"""
    
    def __init__(self, theme: VisualTheme):
        self.theme = theme
        
    def create_arena_atmosphere(self, parent) -> tk.Frame:
        """Create arena-like atmospheric elements"""
        atmosphere_frame = tk.Frame(parent, bg=self.theme.colors.arena_shadow)
        
        # Ice rink visual element
        ice_frame = tk.Frame(atmosphere_frame, bg=self.theme.colors.ice_blue, 
                            height=4, relief='flat')
        ice_frame.pack(fill='x', pady=(0, 1))
        
        # Spotlight effect (subtle gradient simulation)
        spotlight_frame = tk.Frame(atmosphere_frame, bg=self.theme.colors.spotlight, 
                                  height=1, relief='flat')
        spotlight_frame.pack(fill='x')
        
        return atmosphere_frame
    
    def create_team_logo_placeholder(self, parent, team_name: str, size: int = 48) -> tk.Frame:
        """Create team logo placeholder with team colors"""
        team_colors = HockeyAtmosphereSystem().get_team_colors(team_name)
        
        logo_frame = tk.Frame(parent, bg=team_colors.primary, 
                             width=size, height=size, relief='flat')
        logo_frame.pack_propagate(False)
        
        # Team initials
        initials = self._get_team_initials(team_name)
        logo_label = tk.Label(logo_frame, text=initials,
                             font=self.theme.fonts['logo'],
                             fg=team_colors.text_light,
                             bg=team_colors.primary)
        logo_label.place(relx=0.5, rely=0.5, anchor='center')
        
        return logo_frame
    
    def _get_team_initials(self, team_name: str) -> str:
        """Get team initials for logo placeholder"""
        words = team_name.split()
        if len(words) >= 2:
            return f"{words[-2][0]}{words[-1][0]}"  # Last two words (e.g., "TB" for Tampa Bay Lightning)
        return team_name[:2].upper()
    
    def create_mood_indicator(self, parent, mood: str) -> tk.Frame:
        """Create team mood/morale indicator"""
        mood_colors = {
            'excellent': self.theme.colors.success,
            'good': '#90EE90',
            'neutral': self.theme.colors.text_light,
            'poor': self.theme.colors.warning,
            'terrible': self.theme.colors.danger
        }
        
        mood_frame = tk.Frame(parent, bg=self.theme.colors.background)
        
        # Mood indicator dot
        mood_dot = tk.Frame(mood_frame, bg=mood_colors.get(mood, self.theme.colors.text_light),
                           width=12, height=12, relief='flat')
        mood_dot.pack(side='left', padx=(0, 8))
        
        # Mood text
        mood_label = tk.Label(mood_frame, text=f"Team Morale: {mood.title()}",
                             font=self.theme.fonts['caption'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.background)
        mood_label.pack(side='left')
        
        return mood_frame

class StorytellingDataPresentation:
    """Transforms data-heavy interfaces into storytelling experiences"""
    
    def __init__(self, theme: VisualTheme):
        self.theme = theme
        
    def create_narrative_summary(self, parent, data: Dict) -> tk.Frame:
        """Create narrative summary instead of raw data dump"""
        summary_frame = tk.Frame(parent, bg=self.theme.colors.secondary)
        
        # Story title
        story_title = tk.Label(summary_frame, text="Your Team's Story",
                              font=self.theme.fonts['heading'],
                              fg=self.theme.colors.primary,
                              bg=self.theme.colors.secondary)
        story_title.pack(anchor='w', pady=(0, 12))
        
        # Narrative elements
        narratives = self._generate_narratives(data)
        for narrative in narratives:
            self._create_narrative_element(summary_frame, narrative)
        
        return summary_frame
    
    def _generate_narratives(self, data: Dict) -> list:
        """Generate narrative elements from data"""
        narratives = []
        
        # Example narratives based on team performance
        if data.get('recent_performance', 'neutral') == 'good':
            narratives.append({
                'icon': '🔥',
                'title': 'On Fire!',
                'description': 'Your team is riding a hot streak with strong performances.',
                'context': 'positive'
            })
        
        if data.get('salary_cap_situation', 'neutral') == 'tight':
            narratives.append({
                'icon': '💰',
                'title': 'Cap Crunch',
                'description': 'Salary cap space is limited. Strategic moves needed.',
                'context': 'warning'
            })
        
        if data.get('injury_count', 0) > 3:
            narratives.append({
                'icon': '🏥',
                'title': 'Injury Bug',
                'description': 'Multiple players are dealing with injuries.',
                'context': 'negative'
            })
        
        return narratives
    
    def _create_narrative_element(self, parent, narrative: Dict):
        """Create individual narrative element"""
        element_frame = tk.Frame(parent, bg=self.theme.colors.background, 
                                relief='flat', bd=1)
        element_frame.pack(fill='x', pady=4, padx=8)
        
        # Icon and title row
        header_frame = tk.Frame(element_frame, bg=self.theme.colors.background)
        header_frame.pack(fill='x', padx=12, pady=(8, 4))
        
        # Icon
        icon_label = tk.Label(header_frame, text=narrative['icon'],
                             font=('Segoe UI', 16),
                             bg=self.theme.colors.background)
        icon_label.pack(side='left', padx=(0, 8))
        
        # Title
        title_label = tk.Label(header_frame, text=narrative['title'],
                              font=self.theme.fonts['subheading'],
                              fg=self._get_context_color(narrative['context']),
                              bg=self.theme.colors.background)
        title_label.pack(side='left')
        
        # Description
        desc_label = tk.Label(element_frame, text=narrative['description'],
                             font=self.theme.fonts['body'],
                             fg=self.theme.colors.text_light,
                             bg=self.theme.colors.background,
                             wraplength=400, justify='left')
        desc_label.pack(anchor='w', padx=12, pady=(0, 8))
    
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

# Global instance for easy access
hockey_atmosphere = HockeyAtmosphereSystem()
