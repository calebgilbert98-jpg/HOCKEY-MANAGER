# tooltip.py
# Professional tooltip system for Hockey Manager

import tkinter as tk
from tkinter import ttk

class ToolTip:
    """
    Professional tooltip widget that appears on hover
    """
    def __init__(self, widget, text='Widget info', delay=500, wraplength=300):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<Motion>", self.on_motion)
        self.after_id = None
        
    def on_enter(self, event=None):
        self.schedule_tooltip()
        
    def on_leave(self, event=None):
        self.cancel_tooltip()
        self.hide_tooltip()
        
    def on_motion(self, event=None):
        self.cancel_tooltip()
        self.schedule_tooltip()
        
    def schedule_tooltip(self):
        self.cancel_tooltip()
        self.after_id = self.widget.after(self.delay, self.show_tooltip)
        
    def cancel_tooltip(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
            
    def show_tooltip(self):
        if self.tooltip_window is not None:
            return
            
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        # Professional styling
        frame = tk.Frame(tw, background='#2a2a2a', relief='solid', borderwidth=1)
        frame.pack()
        
        label = tk.Label(frame, text=self.text, justify='left',
                        background='#2a2a2a', foreground='#ffffff',
                        relief='flat', borderwidth=0,
                        font=("Arial", 9), wraplength=self.wraplength,
                        padx=12, pady=8)
        label.pack()
        
        # Add subtle shadow effect
        tw.attributes('-topmost', True)
        
    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

def create_tooltip(widget, text, delay=500):
    """Convenience function to create a tooltip"""
    return ToolTip(widget, text, delay)

# Database configuration tooltips
DATABASE_TOOLTIPS = {
    "Small": """Small Database (8,000 players)
    
Performance: Excellent
Memory Usage: Low
Loading Time: < 5 seconds

Leagues Included:
• National Hockey League (30 teams)
• American Hockey League (30 teams)

Perfect for:
• First-time players
• Quick games
• Learning the interface
• Older computers

Limitations:
• Limited prospect depth
• Fewer free agents
• Basic international representation""",

    "Medium": """Medium Database (25,000 players)
    
Performance: Good
Memory Usage: Moderate  
Loading Time: 10-15 seconds

Leagues Included:
• NHL & AHL (North America)
• ECHL (East Coast Hockey League)
• SHL (Swedish Hockey League)
• Liiga (Finnish Elite League)

Perfect for:
• Most players (recommended)
• Balanced gameplay
• Good depth without overwhelming
• Modern computers

Features:
• Rich prospect pools
• International diversity
• Multiple minor league levels""",

    "Large": """Large Database (50,000 players)
    
Performance: Fair
Memory Usage: High
Loading Time: 20-30 seconds

Leagues Included:
• Complete North American system
• Major European leagues
• Comprehensive minor leagues
• International tournaments

Perfect for:
• Experienced managers
• Deep simulation enthusiasts
• Long-term saves
• Powerful computers

Features:
• Extensive scouting opportunities
• Deep prospect development
• Realistic international representation
• Complex trade markets""",

    "Massive": """Massive Database (100,000+ players)
    
Performance: Requires patience
Memory Usage: Very High
Loading Time: 45-90 seconds

Leagues Included:
• Global hockey representation
• All major and minor leagues
• Junior systems worldwide
• University/college leagues

Perfect for:
• Hardcore simulation fans
• Ultimate realism seekers
• Patient players
• High-end computers

Features:
• Unparalleled depth
• Every possible prospect
• Global scouting networks
• Maximum authenticity

Warning: Requires significant system resources"""
}

if __name__ == "__main__":
    # Test the tooltip system
    root = tk.Tk()
    root.geometry("300x200")
    root.title("Tooltip Test")
    
    test_button = tk.Button(root, text="Hover for tooltip")
    test_button.pack(pady=50)
    
    tooltip = create_tooltip(test_button, "This is a test tooltip\nWith multiple lines\nAnd formatting!")
    
    root.mainloop()
