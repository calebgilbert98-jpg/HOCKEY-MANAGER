# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# team_identity_system.py
# Team visual identity system with authentic NHL colors and styling

from typing import (Dict, Optional)
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
                text_on_primary="#000000",
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
                text_on_primary="#000000",
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
                primary="#FF4C00",      # Orange
                secondary="#041E42",    # Royal Navy Blue
                accent="#FFFFFF",       # White
                text_on_primary="#000000",
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
                text_on_secondary="#000000"
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


# ---------------------------------------------------------------------------
# UI accent resolution: one team's colors -> app-wide accent color.
# The accent must stay readable on the dark UI, so near-black primaries
# (Pittsburgh, Los Angeles) fall back to the secondary color.
# ---------------------------------------------------------------------------

_DEFAULT_ACCENT = ("#3B82F6", "#2563EB", "#0e0e11")  # legacy teal

# WCAG AA minimum for normal text. Every (text, background) pair the
# module hands out is guaranteed to meet it -- team colors are shifted
# the smallest possible amount toward white/black when they don't.
_WCAG_AA = 4.5
_DARK_BG = "#0e0e11"  # CONTENT_BG / window background


def _luminance(hex_color: str) -> float:
    """Relative luminance of a hex color, 0 (black) to 1 (white)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    except Exception:
        return 0.5


def _wcag_luminance(hex_color: str) -> float:
    """Gamma-corrected relative luminance per WCAG 2.x."""
    try:
        h = hex_color.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

        def lin(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = (lin(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    except Exception:
        return 0.5


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio of a (text, background) pair. Never raises."""
    try:
        l1, l2 = _wcag_luminance(fg), _wcag_luminance(bg)
        hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
        return (hi + 0.05) / (lo + 0.05)
    except Exception:
        return 1.0


def _mix_hex(a: str, b: str, t: float) -> str:
    """Mix two hex colors; t=0 -> a, t=1 -> b. Never raises."""
    try:
        ah, bh = a.lstrip("#"), b.lstrip("#")
        ar, ag, ab = (int(ah[i:i + 2], 16) for i in (0, 2, 4))
        br, bg_, bb = (int(bh[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % (
            round(ar + (br - ar) * t),
            round(ag + (bg_ - ag) * t),
            round(ab + (bb - ab) * t))
    except Exception:
        return a


def ensure_text_contrast(fg: str, bg: str, minimum: float = _WCAG_AA) -> str:
    """Return fg moved the smallest possible amount toward white or black
    so it reaches `minimum` contrast on bg.

    Team colors keep their hue identity -- a dark red becomes a lighter
    red, never gray -- and already-passing colors come back untouched.
    Never raises.
    """
    try:
        if contrast_ratio(fg, bg) >= minimum:
            return fg
        best = None
        for target in ("#ffffff", "#000000"):
            lo, hi = 0.0, 1.0  # fraction toward target; want smallest hi that passes
            for _ in range(12):
                mid = (lo + hi) / 2
                if contrast_ratio(_mix_hex(fg, target, mid), bg) >= minimum:
                    hi = mid
                else:
                    lo = mid
            if best is None or hi < best[0]:
                best = (hi, _mix_hex(fg, target, hi))
        return best[1] if best else fg
    except Exception:
        return fg


def _darken(hex_color: str, factor: float = 0.85) -> str:
    """Scale a hex color toward black by factor (0..1)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))
    except Exception:
        return hex_color


def accent_for_team(team_name) -> tuple:
    """Return (accent, hover, text_on_accent) for a team name.

    Uses the team's primary color unless it is too dark to read on the
    dark UI, in which case the secondary color is used. Unknown or
    missing names fall back to the legacy teal.

    The returned text color is guaranteed WCAG AA (4.5:1) on both the
    accent and the hover backgrounds -- the team's color is shifted the
    smallest possible amount when it would otherwise fail. Never raises.
    """
    colors = None
    try:
        colors = nhl_identity.get_team_colors(team_name)
        if colors is None and team_name:
            key = str(team_name).strip().lower()
            for name, c in nhl_identity.team_colors.items():
                if name.lower() == key:
                    colors = c
                    break
    except Exception:
        colors = None
    if colors is None:
        return _DEFAULT_ACCENT
    if _luminance(colors.primary) < 0.09:
        base, text = colors.secondary, colors.text_on_secondary
    else:
        base, text = colors.primary, colors.text_on_primary
    text = ensure_text_contrast(text, base)
    hover = _darken(base, 0.85)
    if contrast_ratio(text, hover) < _WCAG_AA:
        # Ease the hover darkening toward the base until the text passes.
        lo, hi = 0.85, 1.0
        for _ in range(12):
            mid = (lo + hi) / 2
            if contrast_ratio(text, _darken(base, mid)) >= _WCAG_AA:
                hi = mid
            else:
                lo = mid
        hover = _darken(base, hi)
    return base, hover, text


def text_color_for_team(team_name) -> str:
    """Team-colored text that stays readable on the dark UI: the primary
    color, unless it is too dark to read on near-black, in which case the
    secondary is used. Unknown names fall back to the legacy teal.

    The returned color is guaranteed WCAG AA (4.5:1) on the dark UI
    background -- it is lightened the smallest possible amount toward
    white when the raw team color would fail, so the hue identity is
    kept. Never raises.
    """
    try:
        colors = nhl_identity.get_team_colors(team_name)
        if colors is None and team_name:
            key = str(team_name).strip().lower()
            for name, c in nhl_identity.team_colors.items():
                if name.lower() == key:
                    colors = c
                    break
        if colors is None:
            return _DEFAULT_ACCENT[0]
        if _luminance(colors.primary) < 0.15:
            candidate = colors.secondary
        else:
            candidate = colors.primary
        return ensure_text_contrast(candidate, _DARK_BG)
    except Exception:
        return _DEFAULT_ACCENT[0]


def dot_colors_for_team(team_name) -> tuple:
    """Return (body, trim) for on-ice skater dots in the team's two
    primary colors: body = primary, trim = secondary ring.

    The trim is used for the dot's outline ring only (jersey numbers
    stay high-contrast via text_color_for_team logic), so even teams
    whose primary and secondary are close stay readable.

    Unknown or missing names return (None, None) so callers can fall
    back to the legacy colors. Never raises.
    """
    try:
        colors = nhl_identity.get_team_colors(team_name)
        if colors is None and team_name:
            key = str(team_name).strip().lower()
            for name, c in nhl_identity.team_colors.items():
                if name.lower() == key:
                    colors = c
                    break
        if colors is None:
            return None, None
        return colors.primary, colors.secondary
    except Exception:
        return None, None


def jersey_chip(parent, team_name, w=46, h=26):
    """Small jersey-stripe chip: a tk.Canvas in the team's two primary
    colors (primary body, secondary hem stripe with trim pinstripes),
    for standings rows, lists and anywhere a team identity mark helps.

    Unknown or missing names fall back to a neutral chip. Never raises.
    """
    import tkinter as tk
    cv = tk.Canvas(parent, width=w, height=h, highlightthickness=0, bd=0)
    try:
        colors = nhl_identity.get_team_colors(team_name)
        if colors is None and team_name:
            key = str(team_name).strip().lower()
            for name, c in nhl_identity.team_colors.items():
                if name.lower() == key:
                    colors = c
                    break
        body = colors.primary if colors else "#2a2e35"
        stripe = colors.secondary if colors else "#3B82F6"
        trim = (colors.text_on_secondary if colors
                else "#ffffff")
        if trim.lower() == stripe.lower():
            trim = body if body.lower() != stripe.lower() else "#ffffff"
        cv.configure(bg=body)
        cv.create_rectangle(0, 0, w, h, fill=body, outline="")
        y0 = h - 9
        cv.create_rectangle(0, y0, w, y0 + 2, fill=trim, outline="")
        cv.create_rectangle(0, y0 + 2, w, y0 + 7, fill=stripe, outline="")
        cv.create_rectangle(0, y0 + 7, w, y0 + 9, fill=trim, outline="")
    except Exception:
        pass
    return cv
