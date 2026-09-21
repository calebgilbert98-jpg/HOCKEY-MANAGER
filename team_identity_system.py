# team_identity_system.py
# Team visual identity system with authentic NHL colors and styling

from typing import Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class TeamColors:
    """Team color scheme including primary, secondary, and accent colors"""
    primary: str        # Main team color
    secondary: str      # Secondary color  
    accent: str         # Accent/tertiary color
    text_on_primary: str    # Text color for primary background
    text_on_secondary: str  # Text color for secondary background

class NHLTeamIdentity:
    """NHL team visual identity system with authentic colors"""
    
    def __init__(self):
        self.team_colors = self._create_team_color_system()
        
    def _create_team_color_system(self) -> Dict[str, TeamColors]:
        """Create authentic NHL team color schemes"""
        return {
            # Atlantic Division
            "Boston Bruins": TeamColors(
                primary="#FFB81C",      # Gold
                secondary="#000000",    # Black  
                accent="#FFFFFF",       # White
                text_on_primary="#000000",
                text_on_secondary="#FFFFFF"
            ),
            "Buffalo Sabres": TeamColors(
                primary="#002654",      # Navy Blue
                secondary="#FCB514",    # Gold
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Detroit Red Wings": TeamColors(
                primary="#CE1126",      # Red
                secondary="#FFFFFF",    # White
                accent="#000000",       # Black
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Florida Panthers": TeamColors(
                primary="#041E42",      # Navy Blue
                secondary="#C8102E",    # Red
                accent="#B9975B",       # Gold
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Montreal Canadiens": TeamColors(
                primary="#AF1E2D",      # Red
                secondary="#192168",    # Blue
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Ottawa Senators": TeamColors(
                primary="#C52032",      # Red
                secondary="#000000",    # Black
                accent="#CBA044",       # Gold
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Tampa Bay Lightning": TeamColors(
                primary="#002868",      # Blue
                secondary="#FFFFFF",    # White
                accent="#000000",       # Black
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Toronto Maple Leafs": TeamColors(
                primary="#003E7E",      # Blue
                secondary="#FFFFFF",    # White
                accent="#000000",       # Black
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            
            # Metropolitan Division
            "Carolina Hurricanes": TeamColors(
                primary="#CC0000",      # Red
                secondary="#000000",    # Black
                accent="#A4A9AD",       # Silver
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Columbus Blue Jackets": TeamColors(
                primary="#002654",      # Navy Blue
                secondary="#CE1126",    # Red
                accent="#A4A9AD",       # Silver
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "New Jersey Devils": TeamColors(
                primary="#CE1126",      # Red
                secondary="#000000",    # Black
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "NY Islanders": TeamColors(
                primary="#00539B",      # Blue
                secondary="#F47D30",    # Orange
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "NY Rangers": TeamColors(
                primary="#0038A8",      # Blue
                secondary="#CE1126",    # Red
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Philadelphia Flyers": TeamColors(
                primary="#F74902",      # Orange
                secondary="#000000",    # Black
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Pittsburgh Penguins": TeamColors(
                primary="#000000",      # Black
                secondary="#FCB514",    # Gold
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Washington Capitals": TeamColors(
                primary="#041E42",      # Navy Blue
                secondary="#C8102E",    # Red
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            
            # Central Division
            "Chicago Blackhawks": TeamColors(
                primary="#CF0A2C",      # Red
                secondary="#000000",    # Black
                accent="#D4AF37",       # Gold
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Colorado Avalanche": TeamColors(
                primary="#6F263D",      # Burgundy
                secondary="#236192",    # Blue
                accent="#A2AAAD",       # Silver
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Dallas Stars": TeamColors(
                primary="#006847",      # Victory Green
                secondary="#8F8F8C",    # Silver
                accent="#000000",       # Black
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Minnesota Wild": TeamColors(
                primary="#A6192E",      # Iron Range Red
                secondary="#154734",    # Forest Green
                accent="#EAAA00",       # Harvest Gold
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Nashville Predators": TeamColors(
                primary="#FFB81C",      # Gold
                secondary="#041E42",    # Navy Blue
                accent="#FFFFFF",       # White
                text_on_primary="#000000",
                text_on_secondary="#FFFFFF"
            ),
            "St. Louis Blues": TeamColors(
                primary="#002F87",      # Blue
                secondary="#FCB514",    # Gold
                accent="#041E42",       # Navy Blue
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Utah Hockey Club": TeamColors(
                primary="#69BE28",      # Rock Black
                secondary="#154734",    # Salt Lake Blue
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Winnipeg Jets": TeamColors(
                primary="#041E42",      # Navy Blue
                secondary="#004C97",    # Aviator Blue
                accent="#AC162C",       # Red
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            
            # Pacific Division
            "Anaheim Ducks": TeamColors(
                primary="#F47A38",      # Orange
                secondary="#B9975B",    # Gold
                accent="#C1C6C8",       # Silver
                text_on_primary="#000000",
                text_on_secondary="#000000"
            ),
            "Calgary Flames": TeamColors(
                primary="#C8102E",      # Red
                secondary="#F1BE48",    # Gold
                accent="#000000",       # Black
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Edmonton Oilers": TeamColors(
                primary="#041E42",      # Navy Blue
                secondary="#FF4C00",    # Orange
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Los Angeles Kings": TeamColors(
                primary="#111111",      # Black
                secondary="#A2AAAD",    # Silver
                accent="#FFFFFF",       # White
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "San Jose Sharks": TeamColors(
                primary="#006D75",      # Teal
                secondary="#EA7200",    # Orange
                accent="#000000",       # Black
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Seattle Kraken": TeamColors(
                primary="#001628",      # Deep Sea Blue
                secondary="#96D8D8",    # Ice Blue
                accent="#C8102E",       # Red
                text_on_primary="#FFFFFF",
                text_on_secondary="#000000"
            ),
            "Vancouver Canucks": TeamColors(
                primary="#00205B",      # Blue
                secondary="#00843D",    # Green
                accent="#041C2C",       # Navy
                text_on_primary="#FFFFFF",
                text_on_secondary="#FFFFFF"
            ),
            "Vegas Golden Knights": TeamColors(
                primary="#B4975A",      # Gold
                secondary="#333F42",    # Steel Gray
                accent="#C8102E",       # Red
                text_on_primary="#000000",
                text_on_secondary="#FFFFFF"
            ),
        }
    
    def get_team_colors(self, team_name: str) -> Optional[TeamColors]:
        """Get color scheme for specified team"""
        return self.team_colors.get(team_name)
    
    def get_team_primary_color(self, team_name: str) -> str:
        """Get primary color for team"""
        colors = self.get_team_colors(team_name)
        return colors.primary if colors else "#002654"  # Default navy blue
    
    def get_team_secondary_color(self, team_name: str) -> str:
        """Get secondary color for team"""
        colors = self.get_team_colors(team_name)
        return colors.secondary if colors else "#FFFFFF"  # Default white
    
    def create_team_themed_style(self, style, team_name: str):
        """Apply team colors to ttk style elements"""
        colors = self.get_team_colors(team_name)
        if not colors:
            return
        
        # Team-themed button
        style.configure(f'{team_name}.TButton',
            background=colors.primary,
            foreground=colors.text_on_primary,
            font=('Segoe UI', 11, 'bold'),
            padding=(12, 8),
            borderwidth=0
        )
        style.map(f'{team_name}.TButton',
            background=[('active', colors.secondary)],
            foreground=[('active', colors.text_on_secondary)]
        )
        
        # Team-themed frame
        style.configure(f'{team_name}.TFrame',
            background=colors.primary
        )
        
        # Team-themed label
        style.configure(f'{team_name}.TLabel',
            background=colors.primary,
            foreground=colors.text_on_primary,
            font=('Segoe UI', 12, 'bold')
        )

# Global team identity instance
nhl_identity = NHLTeamIdentity()
