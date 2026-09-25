# sleeper_nav.py
# Sleeper-inspired navigation bar.
# Clean, minimal, with clear active states.

import tkinter as tk
from sleeper_ui import SleeperColors, SleeperFonts


class SleeperNavBar(tk.Frame):
    """Modern navigation bar (Sleeper-style).
    
    Features:
    - Clean horizontal layout with generous spacing
    - Active item highlighted with accent underline
    - Muted inactive items
    - Dropdown support for grouped items
    - Dark background matching the app theme
    """
    
    def __init__(self, parent, items=None, on_select=None, **kwargs):
        """
        Args:
            parent: Parent widget
            items: List of (label, command) or (label, submenu_dict)
            on_select: Callback when item selected (index)
        """
        super().__init__(parent, bg=SleeperColors.BG, **kwargs)
        
        self.items = items or []
        self.on_select = on_select
        self.buttons = []
        self.active_index = -1
        
        # Bottom border
        self.border = tk.Frame(self, bg=SleeperColors.BORDER, height=1)
        self.border.pack(side="bottom", fill="x")
        
        # Container for buttons
        self.btn_container = tk.Frame(self, bg=SleeperColors.BG)
        self.btn_container.pack(fill="x", padx=16, pady=8)
        
        self._create_buttons()
    
    def _create_buttons(self):
        """Create navigation buttons."""
        for i, item in enumerate(self.items):
            if len(item) == 2:
                label, action = item
                if isinstance(action, dict):
                    # Dropdown
                    btn = self._create_dropdown(label, action, i)
                else:
                    # Simple button
                    btn = self._create_button(label, action, i)
            else:
                continue
            
            btn.pack(side="left", padx=4)
            self.buttons.append(btn)
    
    def _create_button(self, label, command, index):
        """Create a simple nav button."""
        # Container for button + indicator
        container = tk.Frame(self.btn_container, bg=SleeperColors.BG)
        
        # Button
        btn = tk.Label(
            container,
            text=label,
            font=SleeperFonts.BODY,
            fg=SleeperColors.TEXT_SECONDARY,
            bg=SleeperColors.BG,
            padx=16, pady=8,
            cursor="hand2"
        )
        btn.pack()
        
        # Active indicator (hidden by default)
        indicator = tk.Frame(container, bg=SleeperColors.BG, height=2)
        indicator.pack(fill="x", pady=(4, 0))
        
        # Bind
        for w in [container, btn]:
            w.bind("<Enter>", lambda e, b=btn: b.configure(fg=SleeperColors.TEXT_PRIMARY))
            w.bind("<Leave>", lambda e, b=btn, idx=index: self._on_leave(b, idx))
            w.bind("<Button-1>", lambda e, idx=index, cmd=command: self._on_click(idx, cmd))
        
        container.indicator = indicator
        container.label = btn
        container.index = index
        
        return container
    
    def _create_dropdown(self, label, menu_items, index):
        """Create a dropdown nav button."""
        container = tk.Frame(self.btn_container, bg=SleeperColors.BG)
        
        # Button with arrow
        btn = tk.Label(
            container,
            text=f"{label}  ▾",
            font=SleeperFonts.BODY,
            fg=SleeperColors.TEXT_SECONDARY,
            bg=SleeperColors.BG,
            padx=16, pady=8,
            cursor="hand2"
        )
        btn.pack()
        
        # Active indicator
        indicator = tk.Frame(container, bg=SleeperColors.BG, height=2)
        indicator.pack(fill="x", pady=(4, 0))
        
        # Create menu
        menu = tk.Menu(container, tearoff=0,
                      bg=SleeperColors.BG_ELEVATED,
                      fg=SleeperColors.TEXT_PRIMARY,
                      activebackground=SleeperColors.BG_HOVER,
                      activeforeground=SleeperColors.TEXT_PRIMARY,
                      relief="flat", bd=0)
        
        for item_label, item_cmd in menu_items.items():
            # Clean up emoji for cleaner look (optional)
            menu.add_command(label=item_label, command=item_cmd)
        
        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)
        
        for w in [container, btn]:
            w.bind("<Enter>", lambda e, b=btn: b.configure(fg=SleeperColors.TEXT_PRIMARY))
            w.bind("<Leave>", lambda e, b=btn, idx=index: self._on_leave(b, idx))
            w.bind("<Button-1>", show_menu)
        
        container.indicator = indicator
        container.label = btn
        container.index = index
        
        return container
    
    def _on_leave(self, btn, index):
        """Handle mouse leave."""
        if index != self.active_index:
            btn.configure(fg=SleeperColors.TEXT_SECONDARY)
    
    def _on_click(self, index, command):
        """Handle button click."""
        self.set_active(index)
        if command:
            command()
        if self.on_select:
            self.on_select(index)
    
    def set_active(self, index):
        """Set the active nav item."""
        self.active_index = index
        for i, btn in enumerate(self.buttons):
            is_active = (i == index)
            if is_active:
                btn.label.configure(fg=SleeperColors.TEXT_PRIMARY,
                                   font=SleeperFonts.BODY_BOLD)
                btn.indicator.configure(bg=SleeperColors.ACCENT)
            else:
                btn.label.configure(fg=SleeperColors.TEXT_SECONDARY,
                                   font=SleeperFonts.BODY)
                btn.indicator.configure(bg=SleeperColors.BG)


class SleeperTabBar(tk.Frame):
    """Tab bar for content sections (Sleeper-style).
    
    Cleaner than ttk.Notebook - uses pill-style tabs.
    """
    
    def __init__(self, parent, tabs=None, on_select=None, **kwargs):
        super().__init__(parent, bg=SleeperColors.BG, **kwargs)
        
        self.tabs = tabs or []
        self.on_select = on_select
        self.buttons = []
        self.active_index = 0
        
        for i, label in enumerate(self.tabs):
            btn = self._create_tab(label, i)
            btn.pack(side="left", padx=4)
            self.buttons.append(btn)
        
        self._update_ui()
    
    def _create_tab(self, label, index):
        """Create a tab button."""
        # Pill background
        pill = tk.Frame(self, bg=SleeperColors.BG_ELEVATED,
                       padx=16, pady=8, cursor="hand2")
        
        lbl = tk.Label(pill, text=label,
                      font=SleeperFonts.SMALL_BOLD,
                      fg=SleeperColors.TEXT_SECONDARY,
                      bg=SleeperColors.BG_ELEVATED)
        lbl.pack()
        
        for w in [pill, lbl]:
            w.bind("<Button-1>", lambda e, idx=index: self.select(idx))
        
        pill.label = lbl
        return pill
    
    def select(self, index):
        """Select a tab."""
        self.active_index = index
        self._update_ui()
        if self.on_select:
            self.on_select(index)
    
    def _update_ui(self):
        """Update tab appearance."""
        for i, btn in enumerate(self.buttons):
            is_active = (i == self.active_index)
            bg = SleeperColors.ACCENT if is_active else SleeperColors.BG_ELEVATED
            fg = "#ffffff" if is_active else SleeperColors.TEXT_SECONDARY
            
            btn.configure(bg=bg)
            btn.label.configure(bg=bg, fg=fg)
