# typography_system.py
# Professional Typography System for Hockey Manager

import tkinter as tk
from tkinter import font
from typing import Dict, Tuple

class TypographySystem:
    """Professional typography system for consistent text hierarchy"""
    
    def __init__(self):
        self.font_family = 'Segoe UI'
        self.fonts = self._create_font_hierarchy()
        
    def _create_font_hierarchy(self) -> Dict[str, Tuple[str, int, str]]:
        """Create hierarchical font system"""
        return {
            # Display fonts for major headlines
            'display_large': (self.font_family, 28, 'bold'),
            'display_medium': (self.font_family, 24, 'bold'),
            'display_small': (self.font_family, 20, 'bold'),
            
            # Headlines for section headers
            'headline_large': (self.font_family, 18, 'bold'),
            'headline_medium': (self.font_family, 16, 'bold'),
            'headline_small': (self.font_family, 14, 'bold'),
            
            # Titles for subsections
            'title_large': (self.font_family, 13, 'bold'),
            'title_medium': (self.font_family, 12, 'bold'),
            'title_small': (self.font_family, 11, 'bold'),
            
            # Body text
            'body_large': (self.font_family, 11, 'normal'),
            'body_medium': (self.font_family, 10, 'normal'),
            'body_small': (self.font_family, 9, 'normal'),
            
            # Labels and metadata
            'label_large': (self.font_family, 10, 'bold'),
            'label_medium': (self.font_family, 9, 'bold'),
            'label_small': (self.font_family, 8, 'bold'),
            
            # Specialized fonts
            'monospace_large': ('Consolas', 11, 'normal'),  # For stats/numbers
            'monospace_medium': ('Consolas', 10, 'normal'),
            'monospace_small': ('Consolas', 9, 'normal'),
            
            # Button fonts
            'button_large': (self.font_family, 11, 'bold'),
            'button_medium': (self.font_family, 10, 'bold'),
            'button_small': (self.font_family, 9, 'bold'),
        }
    
    def get_font(self, font_type: str) -> Tuple[str, int, str]:
        """Get font configuration for specified type"""
        return self.fonts.get(font_type, self.fonts['body_medium'])
    
    def create_tk_font(self, font_type: str) -> font.Font:
        """Create a tkinter Font object for specified type"""
        family, size, weight = self.get_font(font_type)
        return font.Font(family=family, size=size, weight=weight)

class TextStyles:
    """Text styling utilities for consistent appearance"""
    
    def __init__(self, typography: TypographySystem, color_scheme):
        self.typography = typography
        self.colors = color_scheme
        
    def apply_text_style(self, widget, style_type: str, text_color: str = None):
        """Apply typography and color styling to a widget"""
        font_config = self.typography.get_font(style_type)
        widget.configure(font=font_config)
        
        if text_color:
            widget.configure(foreground=text_color)
    
    def create_styled_label(self, parent, text: str, style_type: str, 
                          text_color: str = None, bg_color: str = None, **kwargs):
        """Create a label with consistent styling"""
        font_config = self.typography.get_font(style_type)
        
        label = tk.Label(
            parent,
            text=text,
            font=font_config,
            foreground=text_color or self.colors.secondary_text,
            background=bg_color or self.colors.primary_bg,
            **kwargs
        )
        
        return label

# Create global typography instance
typography = TypographySystem()
