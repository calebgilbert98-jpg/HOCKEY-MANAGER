# modern_ui.py
# modern modern UI design system for Puck Dynasty.
# 
# Design principles borrowed from modern sports apps:
# - Deep dark backgrounds (not pure black, warm charcoal)
# - Rounded cards (14px radius) with subtle borders
# - Generous whitespace and breathing room
# - Clear visual hierarchy: big bold numbers, small muted labels
# - Avatar-centric design (circular)
# - Teal accent color (#00ceb8 - teal accent)
# - Minimalist, no clutter
# - Subtle status indicators (dots, pills)

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Dict, Any


class AppColors:
    """modern color palette."""
    
    # Backgrounds
    BG = "#0e0e11"              # Deep warm charcoal (main background)
    BG_ELEVATED = "#16161a"     # Slightly lighter (cards)
    BG_HOVER = "#1e1e24"        # Hover state
    BG_PRESSED = "#24242c"      # Pressed state
    
    # Borders (subtle, low opacity)
    BORDER = "#26262e"          # Card borders
    BORDER_LIGHT = "#2e2e38"    # Slightly more visible
    
    # Text
    TEXT_PRIMARY = "#ffffff"    # Main text
    TEXT_SECONDARY = "#a1a1aa"  # Muted text (zinc-400)
    TEXT_TERTIARY = "#71717a"   # Very muted (zinc-500)
    
    # Accent (teal)
    ACCENT = "#00ceb8"          # Primary accent
    ACCENT_DIM = "#00a894"      # Darker accent for hover
    ACCENT_BG = "#0d2b28"       # Accent background (subtle)
    
    # Semantic
    SUCCESS = "#3fb950"         # Green (wins, positive)
    WARNING = "#d29922"         # Amber (warnings)
    DANGER = "#f85149"          # Red (losses, negative)
    INFO = "#58a6ff"            # Blue (info)
    
    # Team color fallback
    TEAM_DEFAULT = "#00ceb8"


class _AppFontsMeta(type):
    """Metaclass: AppFonts.<NAME> returns a live ui_scale Font.

    Sizes match the original fixed tuples at the Default tier; every
    other tier (and auto-fit) rescales them in place. Attribute access
    is cached, so repeated ``font=AppFonts.SMALL`` evaluations share
    one Font object instead of minting new ones.
    """
    _SIZES = {
        # Headings
        "HERO":        (28, "bold"),    # Large hero numbers
        "H1":          (20, "bold"),    # Section titles
        "H2":          (16, "bold"),    # Card titles
        "H3":          (14, "bold"),    # Subsection
        # Body
        "BODY":        (12, "normal"),  # Regular text
        "BODY_BOLD":   (12, "bold"),    # Bold body
        "SMALL":       (11, "normal"),  # Small text
        "SMALL_BOLD":  (11, "bold"),
        # Labels (uppercase, muted)
        "LABEL":       (10, "bold"),    # Small caps labels
        "CAPTION":     (9, "normal"),   # Tiny captions
        # Numbers
        "STAT_LARGE":  (32, "bold"),    # Big stat numbers
        "STAT_MEDIUM": (24, "bold"),    # Medium stats
        "STAT_SMALL":  (18, "bold"),    # Small stats
    }

    def __getattr__(cls, name):
        spec = cls._SIZES.get(name)
        if spec is None:
            raise AttributeError("AppFonts has no attribute %r" % (name,))
        size, weight = spec
        try:
            from ui_scale import get as _getfont
            return _getfont("Segoe UI", size, weight)
        except Exception:
            return ("Segoe UI", size, weight)


class AppFonts(metaclass=_AppFontsMeta):
    """Typography scale (live fonts honoring Settings -> Font size)."""


class AppCard(tk.Frame):
    """modern rounded card with subtle border.
    
    A clean container with:
    - 14px rounded corners (via canvas background)
    - Subtle 1px border
    - Generous padding (16px)
    - Dark elevated background
    """
    
    def __init__(self, parent, padding=16, radius=14, bg=None, **kwargs):
        self.radius = radius
        self.padding = padding
        self.card_bg = bg or AppColors.BG_ELEVATED
        
        # Use a canvas for rounded background
        super().__init__(parent, bg=parent.cget("bg") if hasattr(parent, 'cget') else AppColors.BG, **kwargs)
        
        # Inner frame for content with padding
        self.content = tk.Frame(self, bg=self.card_bg)
        self.content.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Content wrapper with padding
        self.inner = tk.Frame(self.content, bg=self.card_bg)
        self.inner.pack(fill="both", expand=True, padx=padding, pady=padding)
    
    def get_content_frame(self):
        """Return the frame to add content to."""
        return self.inner


class StatCard(AppCard):
    """Stat card with big number and label (modern).
    
    Example:
        ┌─────────────┐
        │  0          │  <- Big number (32pt bold)
        │  WINS       │  <- Small uppercase label
        │  Season     │  <- Muted caption
        └─────────────┘
    """
    
    def __init__(self, parent, value="0", label="", caption="", 
                 value_color=None, accent_top=False, **kwargs):
        super().__init__(parent, **kwargs)
        frame = self.get_content_frame()
        
        # Optional accent bar at top
        if accent_top:
            accent = tk.Frame(frame, bg=AppColors.ACCENT, height=3)
            accent.pack(fill="x", pady=(0, 12))
        
        # Big number
        value_label = tk.Label(
            frame,
            text=value,
            font=AppFonts.STAT_MEDIUM,
            fg=value_color or AppColors.TEXT_PRIMARY,
            bg=self.card_bg
        )
        value_label.pack(anchor="w")
        
        # Label (uppercase, muted)
        if label:
            label_widget = tk.Label(
                frame,
                text=label.upper(),
                font=AppFonts.LABEL,
                fg=AppColors.TEXT_SECONDARY,
                bg=self.card_bg
            )
            label_widget.pack(anchor="w", pady=(4, 0))
        
        # Caption (very muted)
        if caption:
            caption_widget = tk.Label(
                frame,
                text=caption,
                font=AppFonts.CAPTION,
                fg=AppColors.TEXT_TERTIARY,
                bg=self.card_bg
            )
            caption_widget.pack(anchor="w", pady=(2, 0))
        
        self.value_label = value_label


class PlayerRow(tk.Frame):
    """Player list row (modern).
    
    ┌─────────────────────────────────────┐
    │ (O)  Connor McDavid        12 PTS   │
    │       C • EDM               +5      │
    └─────────────────────────────────────┘
    """
    
    def __init__(self, parent, name="", position="", team="", 
                 stat_value="", stat_label="", avatar_color=None,
                 on_click=None, **kwargs):
        bg = kwargs.pop('bg', AppColors.BG_ELEVATED)
        super().__init__(parent, bg=bg, **kwargs)
        
        self.on_click = on_click
        if on_click:
            self.bind("<Button-1>", lambda e: on_click())
            self.configure(cursor="hand2")
        
        # Avatar (circular, using canvas)
        avatar_size = 40
        avatar_canvas = tk.Canvas(
            self, width=avatar_size, height=avatar_size,
            bg=bg, highlightthickness=0
        )
        avatar_canvas.pack(side="left", padx=(12, 12), pady=10)
        
        # Draw circle
        color = avatar_color or AppColors.ACCENT
        avatar_canvas.create_oval(
            2, 2, avatar_size-2, avatar_size-2,
            fill=color, outline=""
        )
        # Initials
        initials = "".join([n[0] for n in name.split()[:2]]).upper() if name else "?"
        avatar_canvas.create_text(
            avatar_size//2, avatar_size//2,
            text=initials, font=("Segoe UI", 12, "bold"),
            fill="white"
        )
        
        # Info (name + details)
        info_frame = tk.Frame(self, bg=bg)
        info_frame.pack(side="left", fill="y", expand=True)
        
        name_label = tk.Label(
            info_frame, text=name,
            font=AppFonts.BODY_BOLD,
            fg=AppColors.TEXT_PRIMARY, bg=bg,
            anchor="w"
        )
        name_label.pack(anchor="w", pady=(10, 0))
        
        detail_text = f"{position}"
        if team:
            detail_text += f" • {team}"
        detail_label = tk.Label(
            info_frame, text=detail_text,
            font=AppFonts.SMALL,
            fg=AppColors.TEXT_SECONDARY, bg=bg,
            anchor="w"
        )
        detail_label.pack(anchor="w")
        
        # Stats (right side)
        if stat_value:
            stat_frame = tk.Frame(self, bg=bg)
            stat_frame.pack(side="right", padx=12)
            
            stat_val = tk.Label(
                stat_frame, text=stat_value,
                font=AppFonts.BODY_BOLD,
                fg=AppColors.TEXT_PRIMARY, bg=bg,
                anchor="e"
            )
            stat_val.pack(anchor="e", pady=(10, 0))
            
            if stat_label:
                stat_lbl = tk.Label(
                    stat_frame, text=stat_label,
                    font=AppFonts.CAPTION,
                    fg=AppColors.TEXT_TERTIARY, bg=bg,
                    anchor="e"
                )
                stat_lbl.pack(anchor="e")
        
        # Bind click to children
        if on_click:
            for child in [avatar_canvas, info_frame, name_label, detail_label]:
                try:
                    child.bind("<Button-1>", lambda e: on_click())
                    child.configure(cursor="hand2")
                except:
                    pass


class PillBadge(tk.Frame):
    """Small pill badge (modern).
    
    Used for status indicators, positions, etc.
    """
    
    def __init__(self, parent, text="", bg=None, fg=None, 
                 font=None, padx=12, pady=4, **kwargs):
        bg = bg or AppColors.ACCENT_BG
        fg = fg or AppColors.ACCENT
        
        super().__init__(parent, bg=bg, **kwargs)
        
        label = tk.Label(
            self, text=text,
            font=font or AppFonts.SMALL_BOLD,
            fg=fg, bg=bg,
            padx=padx, pady=pady
        )
        label.pack()


class AppButton(tk.Canvas):
    """modern button (rounded, modern).
    
    Primary: Teal background, white text
    Secondary: Dark background, subtle border
    """
    
    def __init__(self, parent, text="", command=None, 
                 style="primary", width=120, height=40,
                 font=None, **kwargs):
        super().__init__(
            parent, width=width, height=height,
            highlightthickness=0, bd=0,
            bg=parent.cget("bg") if hasattr(parent, 'cget') else AppColors.BG,
            **kwargs
        )
        
        self.command = command
        self.style = style
        self.width = width
        self.height = height
        
        # Colors
        if style == "primary":
            self.bg_color = AppColors.ACCENT
            self.hover_color = AppColors.ACCENT_DIM
            self.text_color = "#ffffff"
        else:  # secondary
            self.bg_color = AppColors.BG_ELEVATED
            self.hover_color = AppColors.BG_HOVER
            self.text_color = AppColors.TEXT_PRIMARY
        
        self.font = font or AppFonts.BODY_BOLD
        self.text = text
        self._enabled = True

        self._draw(self.bg_color)

        self.bind("<Enter>", lambda e: self._draw(self.hover_color))
        self.bind("<Leave>", lambda e: self._draw(self.bg_color))
        self.bind("<Button-1>", lambda e: self.command() if (self.command and self._enabled) else None)
        self.configure(cursor="hand2" if command else "")

    def set_text(self, text):
        """Change the button label (canvas-based button: redraws)."""
        self.text = text
        self._draw(self.bg_color)

    def set_enabled(self, enabled):
        """Enable/disable click handling with a visual cursor cue."""
        self._enabled = bool(enabled)
        try:
            self.configure(cursor="hand2" if self._enabled and self.command else ("watch" if not self._enabled else ""))
        except Exception:
            pass
    
    def _draw(self, bg_color):
        self.delete("all")
        r = 10  # corner radius
        w, h = self.width, self.height
        
        # Rounded rectangle
        self.create_rounded_rect(1, 1, w-1, h-1, r, fill=bg_color, outline="")
        
        # Text
        self.create_text(
            w//2, h//2, text=self.text,
            font=self.font, fill=self.text_color
        )
    
    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        """Draw a rounded rectangle."""
        points = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)




def apply_app_theme(root):
    """Apply modern theme to a Tkinter root window."""
    root.configure(bg=AppColors.BG)
    
    # Configure ttk styles
    style = ttk.Style(root)
    
    # Use clam theme as base (most customizable)
    try:
        style.theme_use('clam')
    except:
        pass
    
    # Frame styles
    style.configure('App.TFrame', background=AppColors.BG)
    style.configure('AppCard.TFrame', background=AppColors.BG_ELEVATED)
    
    # Label styles
    style.configure('App.TLabel',
                   background=AppColors.BG,
                   foreground=AppColors.TEXT_PRIMARY,
                   font=AppFonts.BODY)
    
    style.configure('AppMuted.TLabel',
                   background=AppColors.BG,
                   foreground=AppColors.TEXT_SECONDARY,
                   font=AppFonts.SMALL)
    
    style.configure('AppCard.TLabel',
                   background=AppColors.BG_ELEVATED,
                   foreground=AppColors.TEXT_PRIMARY,
                   font=AppFonts.BODY)
    
    return style
