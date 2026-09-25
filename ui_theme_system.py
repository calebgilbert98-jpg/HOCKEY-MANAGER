# ui_theme_system.py
# Professional UI Theme System inspired by Football Manager and OOTP

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
from team_identity_system import NHLTeamIdentity

@dataclass
class ColorScheme:
    """Professional color scheme for hockey management"""
    # Base colors
    primary_bg: str = '#0F1419'        # Deep navy base
    secondary_bg: str = '#1B2332'      # Lighter panel background
    tertiary_bg: str = '#242F42'       # Card/widget backgrounds
    
    # Text colors
    primary_text: str = '#FFFFFF'      # Headers and important text
    secondary_text: str = '#B8C5D6'    # Body text
    muted_text: str = '#7A8AA3'        # Less important text
    
    # Accent colors
    primary_accent: str = '#DC3545'    # Professional red (for buttons, highlights)
    secondary_accent: str = '#4A9EFF'  # Ice blue (for links, secondary actions)
    calendar_accent: str = '#2E7BD6'   # Blue specifically for calendar elements
    success: str = '#46C93A'           # Green for positive stats
    warning: str = '#FF9F43'           # Orange for warnings
    danger: str = '#E74C3C'            # Red for negative stats
    
    # Team-specific colors
    team_home: str = '#2E86AB'         # Home team blue
    team_away: str = '#A23B72'         # Away team burgundy
    
    # UI element colors
    border_light: str = '#3A4A63'      # Light borders
    border_dark: str = '#1A2332'       # Dark borders
    hover_bg: str = '#2A3441'          # Hover states
    selected_bg: str = '#335577'       # Selected items
    
    # Data visualization
    stat_excellent: str = '#46C93A'    # 90-100% ratings
    stat_good: str = '#6BCF7F'         # 80-89% ratings  
    stat_average: str = '#FFD93D'      # 70-79% ratings
    stat_poor: str = '#FF9F43'         # 60-69% ratings
    stat_terrible: str = '#E74C3C'     # Below 60% ratings

class ModernUITheme:
    """Modern UI theme with professional sports management styling"""
    
    def __init__(self):
        self.colors = ColorScheme()
        self.fonts = self._setup_fonts()
        self.team_identity = NHLTeamIdentity()
        
    def _setup_fonts(self):
        """Setup font hierarchy for professional look"""
        return {
            'title': ('Segoe UI', 24, 'bold'),      # Page titles - increased from 18 to 24
            'heading': ('Segoe UI', 20, 'bold'),    # Section headers - increased from 14 to 20
            'subheading': ('Segoe UI', 16, 'bold'), # Subsection headers - increased from 12 to 16
            'body': ('Segoe UI', 14, 'normal'),     # Body text - increased from 10 to 14
            'small': ('Segoe UI', 12, 'normal'),    # Small text - increased from 9 to 12
            'mono': ('Consolas', 14, 'normal'),     # Numbers/stats - increased from 10 to 14
            'button': ('Segoe UI', 14, 'bold'),     # Button text - increased from 10 to 14
        }
    
    def apply_to_style(self, style: ttk.Style):
        """Apply modern theme to ttk.Style object"""
        
        # Configure base style
        style.theme_use('clam')
        
        # Base widget styling
        style.configure('.',
            background=self.colors.primary_bg,
            foreground=self.colors.primary_text,
            borderwidth=0,
            font=self.fonts['body']
        )
        
        # Frame styles
        style.configure('TFrame', background=self.colors.primary_bg)
        style.configure('Panel.TFrame', background=self.colors.secondary_bg, relief='flat', borderwidth=1)
        style.configure('Card.TFrame', background=self.colors.tertiary_bg, relief='flat', borderwidth=1)
        style.configure('Card.TLabel',
            background=self.colors.tertiary_bg,
            foreground=self.colors.primary_text,
            font=self.fonts['body']
        )
        style.configure('TitleBar.TFrame', background=self.colors.border_dark)
        
        # Label styles
        style.configure('TLabel', 
            background=self.colors.primary_bg, 
            foreground=self.colors.secondary_text,
            font=self.fonts['body']
        )
        style.configure('Title.TLabel',
            background=self.colors.primary_bg,
            foreground=self.colors.primary_text,
            font=self.fonts['title']
        )
        style.configure('Heading.TLabel',
            background=self.colors.secondary_bg,
            foreground=self.colors.primary_text,
            font=self.fonts['heading']
        )
        style.configure('Subheading.TLabel',
            background=self.colors.secondary_bg,
            foreground=self.colors.secondary_text,
            font=self.fonts['subheading']
        )
        style.configure('Muted.TLabel',
            background=self.colors.secondary_bg,
            foreground=self.colors.muted_text,
            font=self.fonts['small']
        )
        
        # Button styles
        style.configure('TButton',
            font=self.fonts['button'],
            foreground='white',
            background=self.colors.primary_accent,
            padding=(12, 8),
            borderwidth=0,
            relief='flat'
        )
        style.map('TButton',
            background=[
                ('active', self.colors.danger),
                ('pressed', '#C44569')
            ]
        )
        
        # Secondary button style
        style.configure('Secondary.TButton',
            font=self.fonts['button'],
            foreground=self.colors.secondary_text,
            background=self.colors.tertiary_bg,
            padding=(12, 8),
            borderwidth=1,
            relief='flat'
        )
        style.map('Secondary.TButton',
            background=[
                ('active', self.colors.hover_bg),
                ('pressed', self.colors.selected_bg)
            ],
            bordercolor=[
                ('focus', self.colors.secondary_accent),
                ('active', self.colors.secondary_accent)
            ]
        )
        
        # Calendar/Menu button style (uses blue for calendar elements)
        style.configure('Menu.TButton',
            font=self.fonts['button'],
            foreground='white',
            background=self.colors.calendar_accent,
            padding=(8, 6),
            borderwidth=0,
            relief='flat'
        )
        style.map('Menu.TButton',
            background=[
                ('active', '#2563EB'),  # Darker blue on hover
                ('pressed', '#1D4ED8')  # Even darker blue when pressed
            ]
        )
        
        # Modern dark nav pills (neutral chrome; team color reserved for accents)
        style.configure('TeamMenu.TButton',
            font=self.fonts['button'],
            foreground='#c3cddd',
            background='#141b2a',
            padding=(10, 8),
            borderwidth=0,
            relief='flat'
        )
        style.map('TeamMenu.TButton',
            foreground=[('active', '#ffffff')],
            background=[
                ('active', '#1e2942'),
                ('pressed', '#d13438')
            ]
        )
        
        # Treeview styling
        style.configure('Treeview',
            background=self.colors.tertiary_bg,
            foreground=self.colors.secondary_text,
            fieldbackground=self.colors.tertiary_bg,
            borderwidth=0,
            font=self.fonts['body'],
            rowheight=36  # Increased from 28 to 36 to accommodate larger font
        )
        style.configure('Treeview.Heading',
            background=self.colors.border_dark,
            foreground=self.colors.primary_text,
            font=self.fonts['subheading'],
            borderwidth=0,
            relief='flat'
        )
        style.map('Treeview.Heading',
            background=[('active', self.colors.hover_bg)]
        )
        style.map('Treeview',
            background=[('selected', self.colors.selected_bg)],
            foreground=[('selected', self.colors.primary_text)]
        )
        
        # Notebook/Tab styling
        style.configure('TNotebook',
            background=self.colors.primary_bg,
            borderwidth=0
        )
        style.configure('TNotebook.Tab',
            background=self.colors.tertiary_bg,
            foreground=self.colors.secondary_text,
            font=self.fonts['body'],
            padding=[20, 10],
            borderwidth=0
        )
        style.map('TNotebook.Tab',
            background=[
                ('selected', self.colors.primary_accent),
                ('active', self.colors.hover_bg)
            ],
            foreground=[
                ('selected', 'white'),
                ('active', self.colors.primary_text)
            ]
        )

        # LabelFrame styling (dark cards with subtle borders)
        style.configure('TLabelframe',
            background=self.colors.secondary_bg,
            foreground=self.colors.primary_text,
            bordercolor=self.colors.border_light,
            borderwidth=1,
            relief='flat',
            font=self.fonts['subheading']
        )
        style.configure('TLabelframe.Label',
            background=self.colors.secondary_bg,
            foreground=self.colors.primary_text,
            font=self.fonts['subheading']
        )
        style.configure('Panel.TLabelframe',
            background=self.colors.secondary_bg,
            foreground=self.colors.primary_text,
            bordercolor=self.colors.border_light,
            borderwidth=1,
            relief='flat',
            font=self.fonts['subheading']
        )
        style.configure('Panel.TLabelframe.Label',
            background=self.colors.secondary_bg,
            foreground=self.colors.secondary_text,
            font=self.fonts['body']
        )
        style.configure('Card.TLabelframe',
            background=self.colors.tertiary_bg,
            foreground=self.colors.primary_text,
            bordercolor=self.colors.border_light,
            borderwidth=1,
            relief='flat',
            font=self.fonts['subheading']
        )
        style.configure('Card.TLabelframe.Label',
            background=self.colors.tertiary_bg,
            foreground=self.colors.secondary_text,
            font=self.fonts['body']
        )
        
        # Entry/Input styling
        style.configure('TEntry',
            background=self.colors.tertiary_bg,
            foreground=self.colors.primary_text,
            borderwidth=1,
            relief='flat',
            insertcolor=self.colors.primary_text
        )
        style.map('TEntry',
            bordercolor=[
                ('focus', self.colors.secondary_accent),
                ('active', self.colors.secondary_accent)
            ]
        )
        
        # Combobox styling
        style.configure('TCombobox',
            background=self.colors.tertiary_bg,
            fieldbackground=self.colors.tertiary_bg,
            foreground=self.colors.primary_text,
            borderwidth=1,
            relief='flat',
            arrowcolor=self.colors.secondary_text
        )
        style.map('TCombobox',
            fieldbackground=[
                ('readonly', self.colors.tertiary_bg),
                ('focus', self.colors.tertiary_bg)
            ],
            foreground=[
                ('readonly', self.colors.primary_text)
            ]
        )
        
    def get_stat_color(self, value: float, max_value: float = 20.0) -> str:
        """Get color for stat value based on percentage"""
        percentage = (value / max_value) * 100
        
        if percentage >= 90:
            return self.colors.stat_excellent
        elif percentage >= 80:
            return self.colors.stat_good
        elif percentage >= 70:
            return self.colors.stat_average
        elif percentage >= 60:
            return self.colors.stat_poor
        else:
            return self.colors.stat_terrible
    
    def create_gradient_frame(self, parent, start_color: str, end_color: str, height: int = 4):
        """Create a gradient separator frame"""
        # For now, create a simple colored frame - gradient would need Canvas
        frame = tk.Frame(parent, bg=start_color, height=height)
        frame.pack(fill='x', pady=2)
        return frame
    
    def update_team_colors(self, style: ttk.Style, team_name: str):
        """Keep nav chrome neutral-dark; team color lives in accents only."""
        style.configure('TeamMenu.TButton',
            font=self.fonts['button'],
            foreground='#c3cddd',
            background='#141b2a',
            padding=(10, 8),
            borderwidth=0,
            relief='flat'
        )
        style.map('TeamMenu.TButton',
            foreground=[('active', '#ffffff')],
            background=[
                ('active', '#1e2942'),
                ('pressed', '#d13438')
            ]
        )
    
    def _darken_color(self, hex_color: str, factor: float) -> str:
        """Darken a hex color by the given factor (0.0 to 1.0)"""
        # Remove the '#' if present
        hex_color = hex_color.lstrip('#')
        
        # Convert to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Darken each component
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"

# Professional widget templates
class ProfessionalWidgets:
    """Pre-built professional widget templates"""
    
    def __init__(self, theme: ModernUITheme):
        self.theme = theme
    
    def create_stat_card(self, parent, title: str, value: str, subtitle: str = "", 
                        icon: str = "", color_scheme: str = "default"):
        """Create a professional stat card widget"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        
        # Header with icon and title
        header = ttk.Frame(card, style='Card.TFrame')
        header.pack(fill='x', pady=(0, 8))
        
        if icon:
            icon_label = ttk.Label(header, text=icon, font=('Segoe UI', 16), style='Heading.TLabel')
            icon_label.pack(side='left', padx=(0, 8))
        
        title_label = ttk.Label(header, text=title, style='Subheading.TLabel')
        title_label.pack(side='left')
        
        # Value
        value_label = ttk.Label(card, text=value, style='Title.TLabel')
        value_label.pack(anchor='w')
        
        # Subtitle
        if subtitle:
            subtitle_label = ttk.Label(card, text=subtitle, style='Muted.TLabel')
            subtitle_label.pack(anchor='w', pady=(4, 0))
        
        return card
    
    def create_player_card(self, parent, player, show_stats: bool = True):
        """Create a professional player card"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        
        # Player header
        header = ttk.Frame(card, style='Card.TFrame')
        header.pack(fill='x', pady=(0, 8))
        
        # Jersey number
        jersey_frame = tk.Frame(header, bg=self.theme.colors.primary_accent, width=32, height=32)
        jersey_frame.pack(side='left', padx=(0, 12))
        jersey_frame.pack_propagate(False)
        
        jersey_label = tk.Label(
            jersey_frame, 
            text=str(getattr(player, 'jersey_number', '?')),
            bg=self.theme.colors.primary_accent,
            fg='white',
            font=self.theme.fonts['subheading']
        )
        jersey_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Player info
        info_frame = ttk.Frame(header, style='Card.TFrame')
        info_frame.pack(side='left', fill='both', expand=True)
        
        name_label = ttk.Label(info_frame, text=player.full_name, style='Heading.TLabel')
        name_label.pack(anchor='w')
        
        position_age = f"{player.primary_position.value} • Age {player.age}"
        details_label = ttk.Label(info_frame, text=position_age, style='Muted.TLabel')
        details_label.pack(anchor='w')
        
        if show_stats:
            # Stats section
            stats_frame = ttk.Frame(card, style='Card.TFrame')
            stats_frame.pack(fill='x', pady=(8, 0))
            
            # Overall rating with color coding
            ovr = player.overall_rating()
            ovr_color = self.theme.get_stat_color(ovr)
            
            ovr_label = tk.Label(
                stats_frame,
                text=f"OVR: {ovr}",
                bg=self.theme.colors.tertiary_bg,
                fg=ovr_color,
                font=self.theme.fonts['subheading']
            )
            ovr_label.pack(side='left')
        
        return card
    
    def create_action_toolbar(self, parent, actions: list):
        """Create a professional action toolbar"""
        toolbar = ttk.Frame(parent, style='Panel.TFrame', padding=8)
        
        for i, (text, command) in enumerate(actions):
            if i > 0:
                # Add separator
                sep = ttk.Separator(toolbar, orient='vertical')
                sep.pack(side='left', fill='y', padx=4)
            
            btn = ttk.Button(toolbar, text=text, command=command)
            btn.pack(side='left', padx=2)
        
        return toolbar

# Factory function
def create_modern_theme() -> ModernUITheme:
    """Create and return a modern UI theme instance"""
    return ModernUITheme()
