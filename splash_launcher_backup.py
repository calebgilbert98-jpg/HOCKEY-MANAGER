"""
Puck Dynasty - Splash Screen Launcher
Beautiful full-screen background with simple continue button leading to main launcher
"""

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import sys

class SplashLauncher(tk.Tk):
    """Splash screen with full background image and continue button"""
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.title("Puck Dynasty")
        self.configure(bg='#000000')
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Set window size (reasonable size for splash)
        window_width = min(1200, int(screen_width * 0.8))
        window_height = min(800, int(screen_height * 0.8))
        x_pos = (screen_width - window_width) // 2
        y_pos = (screen_height - window_height) // 2
        
        self.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        
        # Set window icon if available
        try:
            if os.path.exists("puck_dynasty_icon.ico"):
                self.iconbitmap("puck_dynasty_icon.ico")
        except:
            pass
        
        # Make window topmost initially
        self.attributes('-topmost', True)
        
        # Store window dimensions for interface creation
        self.window_width = window_width
        self.window_height = window_height
        
        # Initialize variables
        self.background_image = None
        self.continue_clicked = False
        
        # Load and display background
        self._load_background()
        
        # Create interface immediately 
        self._create_interface()
        
        # Start simple animations after interface is ready
        self.animation_phase = 0
        self.animation_running = True
        self.after(1000, self._start_animations)
        
        # Bind escape key to close
        self.bind('<Escape>', self._on_escape)
        self.focus_set()
        
        # Force window to display
        self.update_idletasks()
        self.lift()
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))
        
    def _load_background(self):
        """Load the hockey background image"""
        try:
            # Try different possible background image names
            bg_files = [
                "hockey manager background.png",
                "hockey_bg.png", 
                "background.png",
                "PUCK DYNASTY LOGO.png"
            ]
            
            for bg_file in bg_files:
                if os.path.exists(bg_file):
                    print(f"🏒 Loading background: {bg_file}")
                    
                    # Load and resize image to fit screen
                    original = Image.open(bg_file).convert('RGBA')
                    
                    # Get screen size
                    screen_width = self.winfo_screenwidth()
                    screen_height = self.winfo_screenheight()
                    
                    # Resize maintaining aspect ratio, but fill screen
                    img_ratio = original.width / original.height
                    screen_ratio = screen_width / screen_height
                    
                    if img_ratio > screen_ratio:
                        # Image is wider - fit height
                        new_height = screen_height
                        new_width = int(new_height * img_ratio)
                    else:
                        # Image is taller - fit width  
                        new_width = screen_width
                        new_height = int(new_width / img_ratio)
                    
                    # Resize and crop to center
                    resized = original.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # If larger than screen, crop from center
                    if new_width > screen_width or new_height > screen_height:
                        left = (new_width - screen_width) // 2
                        top = (new_height - screen_height) // 2
                        right = left + screen_width
                        bottom = top + screen_height
                        resized = resized.crop((left, top, right, bottom))
                    
                    # Add subtle dark overlay for better text visibility
                    overlay = Image.new('RGBA', resized.size, (0, 0, 0, 80))
                    self.background_image = Image.alpha_composite(resized, overlay)
                    
                    print("✅ Background image loaded and optimized for fullscreen")
                    return
                    
            print("⚠️ No background image found - using solid background")
            
        except Exception as e:
            print(f"⚠️ Background loading failed: {e}")
            self.background_image = None
    
    def _create_interface(self):
        """Create the splash screen interface"""
        # Main canvas for background
        self.canvas = tk.Canvas(
            self, 
            width=self.window_width,
            height=self.window_height,
            highlightthickness=0, 
            bg='#000000'
        )
        self.canvas.pack(fill='both', expand=True)
        
        # Display background if loaded
        if self.background_image:
            try:
                self.bg_photo = ImageTk.PhotoImage(self.background_image)
                self.canvas.create_image(0, 0, anchor='nw', image=self.bg_photo)
            except Exception as e:
                print(f"Background display failed: {e}")
        
        # Use stored window dimensions
        canvas_width = self.window_width
        canvas_height = self.window_height
        
        # Create clean title area
        title_y = canvas_height * 0.25
        
        # Simple background panel for title
        panel_width = 700
        panel_height = 120
        panel_x = (canvas_width - panel_width) // 2
        panel_y = title_y - 60
        
        # Clean background rectangle
        self.canvas.create_rectangle(
            panel_x, panel_y, panel_x + panel_width, panel_y + panel_height,
            fill='#000000', stipple='gray25', outline='#D13438', width=3
        )
        
        # Title shadow
        self.canvas.create_text(
            canvas_width // 2 + 3, title_y + 3,
            text="🏒 PUCK DYNASTY",
            font=('Segoe UI', 42, 'bold'),
            fill='#000000',
            anchor='center'
        )
        
        # Main title text
        self.canvas.create_text(
            canvas_width // 2, title_y,
            text="🏒 PUCK DYNASTY",
            font=('Segoe UI', 42, 'bold'),
            fill='#FFFFFF',
            anchor='center'
        )
        
        # Subtitle
        subtitle_y = title_y + 45
        self.canvas.create_text(
            canvas_width // 2 + 2, subtitle_y + 2,
            text="Professional Hockey Management Experience",
            font=('Segoe UI', 16, 'italic'),
            fill='#000000',
            anchor='center'
        )
        
        self.canvas.create_text(
            canvas_width // 2, subtitle_y,
            text="Professional Hockey Management Experience",
            font=('Segoe UI', 16, 'italic'),
            fill='#C0C0C0',
            anchor='center'
        )
        
        # Clean continue button
        button_y = canvas_height * 0.6
        
        # Button dimensions
        button_width = 350
        button_height = 70
        button_x1 = (canvas_width - button_width) // 2
        button_y1 = button_y - (button_height // 2)
        button_x2 = button_x1 + button_width
        button_y2 = button_y1 + button_height
        
        # Button shadow
        self.canvas.create_rectangle(
            button_x1 + 4, button_y1 + 4,
            button_x2 + 4, button_y2 + 4,
            fill='#000000', outline='', width=0
        )
        
        # Main button background
        self.button_bg = self.canvas.create_rectangle(
            button_x1, button_y1, button_x2, button_y2,
            fill='#D13438', outline='#FFFFFF', width=3,
            tags='button'
        )
        
        # Button text shadow
        self.canvas.create_text(
            canvas_width // 2 + 2, button_y + 2,
            text="▶ ENTER THE RINK",
            font=('Segoe UI', 18, 'bold'),
            fill='#000000',
            anchor='center'
        )
        
        # Main button text
        self.button_text = self.canvas.create_text(
            canvas_width // 2, button_y,
            text="▶ ENTER THE RINK",
            font=('Segoe UI', 18, 'bold'),
            fill='#FFFFFF',
            anchor='center',
            tags='button'
        )
        
        # Bind button click
        self.canvas.tag_bind('button', '<Button-1>', self._continue_to_launcher)
        self.canvas.tag_bind('button', '<Enter>', self._on_button_hover)
        self.canvas.tag_bind('button', '<Leave>', self._on_button_leave)
        
        # Also bind canvas click for anywhere-to-continue
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        
        # Add decorative elements
        self._add_decorative_elements(canvas_width, canvas_height)
        
        # Simple instructions at bottom
        instructions_y = canvas_height * 0.8
        
        # Simple instruction text with shadow
        self.canvas.create_text(
            canvas_width // 2 + 1, instructions_y + 1,
            text="Press ESC to exit  •  Click anywhere to continue",
            font=('Segoe UI', 12),
            fill='#000000',
            anchor='center'
        )
        
        self.canvas.create_text(
            canvas_width // 2, instructions_y,
            text="Press ESC to exit  •  Click anywhere to continue",
            font=('Segoe UI', 12),
            fill='#AAAAAA',
            anchor='center'
        )
        
        # Version info (smaller and at very bottom)
        version_y = canvas_height * 0.92
        self.canvas.create_text(
            canvas_width // 2, version_y,
            text="Version 1.0 Beta  •  © 2025 Puck Dynasty",
            font=('Segoe UI', 9),
            fill='#666666',
            anchor='center'
        )
        
        print(f"✅ Enhanced interface created with dimensions: {canvas_width}x{canvas_height}")
    
    def _add_decorative_elements(self, canvas_width, canvas_height):
        """Add simple decorative hockey-themed elements"""
        # Simple corner decorations that won't overlap with main content
        
        # Hockey sticks in far corners (smaller and more subtle)
        stick_color = '#8B4513'
        
        # Top left (smaller)
        self.canvas.create_line(30, 30, 80, 50, fill=stick_color, width=4)
        self.canvas.create_oval(75, 45, 85, 55, fill=stick_color, outline='')
        
        # Top right (smaller)
        self.canvas.create_line(canvas_width-30, 30, canvas_width-80, 50, fill=stick_color, width=4)
        self.canvas.create_oval(canvas_width-85, 45, canvas_width-75, 55, fill=stick_color, outline='')
        
        # Simple pucks in safe corners (away from text)
        puck_positions = [
            (60, canvas_height - 80),  # Bottom left
            (canvas_width - 80, canvas_height - 80),  # Bottom right
        ]
        
        for x, y in puck_positions:
            # Puck shadow
            self.canvas.create_oval(x+2, y+2, x+18, y+18, fill='#000000', outline='')
            # Main puck
            self.canvas.create_oval(x, y, x+16, y+16, fill='#222222', outline='#FFFFFF', width=1)
    
    def _on_button_hover(self, event):
        """Enhanced button hover effect"""
        self.canvas.itemconfig(self.button_bg, fill='#E54E52', outline='#FFFF00', width=3)
        self.canvas.config(cursor='hand2')
        
        # Add glow effect
        self._add_button_glow(True)
    
    def _on_button_leave(self, event):
        """Enhanced button leave effect"""
        self.canvas.itemconfig(self.button_bg, fill='#D13438', outline='#FFFFFF', width=2)
        self.canvas.config(cursor='')
        
        # Remove glow effect
        self._add_button_glow(False)
    
    def _add_button_glow(self, show_glow):
        """Add or remove button glow effect"""
        # Remove existing glow
        self.canvas.delete('glow')
        
        if show_glow:
            # Find button coordinates
            button_coords = self.canvas.coords(self.button_bg)
            if len(button_coords) >= 4:
                x1, y1, x2, y2 = button_coords
                
                # Create glow rings
                glow_colors = ['#FFD700', '#FFA500', '#FF6B6B']
                for i, color in enumerate(glow_colors):
                    offset = (i + 1) * 3
                    self.canvas.create_rectangle(
                        x1 - offset, y1 - offset, x2 + offset, y2 + offset,
                        outline=color, width=2, fill='', tags='glow'
                    )
    
    def _start_animations(self):
        """Start subtle animations"""
        if self.animation_running:
            self._animate_button_pulse()
    
    def _animate_button_pulse(self):
        """Subtle button pulsing animation"""
        if not self.animation_running or self.continue_clicked:
            return
            
        try:
            if hasattr(self, 'button_text') and hasattr(self, 'canvas'):
                # Simple color pulse
                self.animation_phase += 0.1
                colors = ['#FFFFFF', '#F8F8F8', '#F0F0F0', '#F8F8F8']
                color_index = int(self.animation_phase) % len(colors)
                
                self.canvas.itemconfig(self.button_text, fill=colors[color_index])
                
                # Schedule next pulse
                self.after(300, self._animate_button_pulse)
        except Exception as e:
            # Stop animations if there's an error
            print(f"Animation error: {e}")
            self.animation_running = False
    
    def _continue_to_launcher(self, event=None):
        """Continue to main launcher"""
        if self.continue_clicked:
            return
        
        self.continue_clicked = True
        self.animation_running = False  # Stop animations
        print("🚀 Launching main application...")
        
        try:
            # Import and launch the enhanced launcher
            try:
                from enhanced_launcher import EnhancedPuckDynastyLauncher
                
                # Hide splash screen before launching
                self.withdraw()
                
                launcher = EnhancedPuckDynastyLauncher()
                
                # Close splash when main launcher closes
                def on_launcher_close():
                    try:
                        launcher.quit()
                    except:
                        pass
                    self.quit()
                
                launcher.protocol("WM_DELETE_WINDOW", on_launcher_close)
                
                # Center the launcher
                launcher.update_idletasks()
                x = (launcher.winfo_screenwidth() // 2) - (launcher.winfo_width() // 2)
                y = (launcher.winfo_screenheight() // 2) - (launcher.winfo_height() // 2)
                launcher.geometry(f"+{x}+{y}")
                
                launcher.mainloop()
                
            except ImportError as e:
                print(f"Enhanced launcher not available: {e}")
                from tkinter import messagebox
                messagebox.showerror("Error", f"Could not load enhanced launcher:\n{str(e)}")
                self.quit()
                
        except Exception as e:
            print(f"Launch error: {e}")
            from tkinter import messagebox
            messagebox.showerror("Launch Error", f"Failed to launch application:\n{str(e)}")
            # Show splash again on error
            self.deiconify()
            self.continue_clicked = False
            self.animation_running = True
            self.after(500, self._start_animations)
    
    def _on_canvas_click(self, event):
        """Handle clicks on canvas"""
        # Check if clicking on button area
        button_items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        button_clicked = any('button' in self.canvas.gettags(item) for item in button_items)
        
        # If not clicking on button, continue to launcher
        if not button_clicked:
            self._continue_to_launcher()
    
    def _on_escape(self, event):
        """Handle escape key"""
        result = messagebox.askyesno("Exit", "Exit Puck Dynasty?")
        if result:
            self.quit()


def main():
    """Main entry point"""
    try:
        splash = SplashLauncher()
        splash.mainloop()
    except Exception as e:
        print(f"Splash launcher error: {e}")
        messagebox.showerror("Error", f"Failed to start Puck Dynasty:\n{str(e)}")


if __name__ == "__main__":
    main()