# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Puck Dynasty - Simple Splash Launcher
Reliable splash screen that shows background and launches enhanced launcher
"""

import tkinter as tk
from popup_system import messagebox
import os
import sys

class SplashLauncher(tk.Tk):
    """Simple, reliable splash screen"""
    
    def __init__(self):
        super().__init__()
        
        # Basic window setup
        self.title("Puck Dynasty")
        self.configure(bg='#000000')
        
        # Window size and position
        self.geometry("900x600")
        self.resizable(False, False)
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (450)
        y = (self.winfo_screenheight() // 2) - (300)
        self.geometry(f"900x600+{x}+{y}")
        
        # Set icon
        try:
            if os.path.exists("puck_dynasty_icon.ico"):
                self.iconbitmap("puck_dynasty_icon.ico")
        except:
            pass
        
        # Variables
        self.continue_clicked = False
        
        # Build the branded splash interface
        self._create_interface()
        
        # Bind keys - any key continues except ESC
        self.bind('<Key>', self._on_any_key)
        self.bind('<Button-1>', lambda e: self._continue_to_launcher())  # Mouse click also continues
        self.bind('<Escape>', self._on_escape)
        
        # Focus window
        self.focus_set()
        
    def _create_interface(self):
        """Create the branded splash screen.

        Full-window loading_bg.png, centered logo, PUCK DYNASTY title,
        and the flashing press-any-key prompt -- all drawn on one canvas
        so the text sits directly on the artwork.
        """
        self.configure(bg="#0e0e11")
        self._canvas = tk.Canvas(self, width=900, height=600,
                                 highlightthickness=0, bg="#0e0e11")
        self._canvas.pack(fill="both", expand=True)

        self._bg_photo = None
        self._logo_photo = None
        try:
            from branding import cover_photo, load_logo
            self._bg_photo = cover_photo("loading_bg.png", 900, 600)
            if self._bg_photo is not None:
                self._canvas.create_image(450, 300, image=self._bg_photo)
            self._logo_photo = load_logo(self, size=190)
            if self._logo_photo is not None:
                self._canvas.create_image(450, 205, image=self._logo_photo)
        except Exception:
            pass  # Artwork is decorative; the splash must always work

        # Title with a subtle drop shadow for legibility
        self._canvas.create_text(452, 402, text="PUCK DYNASTY",
                                 font=("Segoe UI", 38, "bold"), fill="#000000")
        self._canvas.create_text(450, 400, text="PUCK DYNASTY",
                                 font=("Segoe UI", 38, "bold"), fill="#ffffff")
        self._canvas.create_text(450, 448,
                                 text="Professional Hockey Management Simulator",
                                 font=("Segoe UI", 12), fill="#3B82F6")

        # Flashing continue prompt
        self._flash_id = self._canvas.create_text(
            450, 545, text="Press Any Key to Continue",
            font=("Segoe UI", 14, "bold"), fill="#ffffff")
        self._flash_shadow = self._canvas.create_text(
            451, 546, text="Press Any Key to Continue",
            font=("Segoe UI", 14, "bold"), fill="#000000")
        # Keep the shadow behind the text
        self._canvas.tag_lower(self._flash_shadow, self._flash_id)

        # Start flashing animation
        self.flash_visible = True
        self._flash_text()

    def _continue_to_launcher(self):
        """Continue to enhanced launcher"""
        if self.continue_clicked:
            return
            
        self.continue_clicked = True
        print("🚀 Launching enhanced launcher...")
        
        # Store self for use after mainloop exits
        self._launch_enhanced = True
        
        # Quit the splash mainloop - launcher will be created after
        self.quit()
    
    def _run_enhanced_launcher(self):
        """Actually create and run the enhanced launcher after splash is done"""
        try:
            # Import enhanced launcher
            print("📦 Importing enhanced launcher...")
            from enhanced_launcher import EnhancedPuckDynastyLauncher
            print("✅ Enhanced launcher imported successfully")
            
            # Destroy splash completely now
            print("🗑️ Destroying splash screen...")
            try:
                self.destroy()
            except Exception:
                pass
            
            # Create and show enhanced launcher (this creates a new Tk root)
            print("🎮 Creating enhanced launcher...")
            launcher = EnhancedPuckDynastyLauncher()
            print("✅ Enhanced launcher created successfully")
            
            # Ensure proper focus and window state
            launcher.lift()  # Bring to front
            launcher.focus_force()  # Force focus
            launcher.attributes('-topmost', True)  # Temporarily stay on top
            launcher.after(100, lambda: launcher.attributes('-topmost', False))  # Remove topmost after brief moment
            
            # Close handler
            def on_close():
                print("🔴 Enhanced launcher closing without starting game...")
                try:
                    launcher.quit()
                    launcher.destroy()
                except Exception as cleanup_error:
                    print(f"⚠️ Cleanup error: {cleanup_error}")
                print("🚪 Exiting application...")
                sys.exit()
            
            launcher.protocol("WM_DELETE_WINDOW", on_close)
            
            # Start launcher mainloop
            print("▶️ Starting enhanced launcher mainloop...")
            launcher.mainloop()
            print("✅ Enhanced launcher/game completed - exiting")
            
        except ImportError as e:
            print(f"❌ Enhanced launcher import error: {e}")
            print("🔄 Falling back to direct game launch...")
            self._direct_game_launch_standalone()
        except Exception as e:
            print(f"❌ Launch error: {e}")
            import traceback
            traceback.print_exc()
            print("🔄 Falling back to direct game launch...")
            self._direct_game_launch_standalone()
    
    def _direct_game_launch_standalone(self):
        """Direct launch of main game as standalone fallback"""
        try:
            print("🚀 Standalone direct game launch...")
            
            # Destroy splash if still exists
            try:
                self.destroy()
            except Exception:
                pass
            
            # Import main game components
            from main import GameManager, HockeyManagerGUI
            print("✅ Main game modules imported")
            
            # Create game manager
            gm = GameManager()
            print("✅ Game manager created")
            
            # Create and start GUI
            app = HockeyManagerGUI(gm)
            app.lift()
            app.focus_force()
            app.attributes('-topmost', True)
            app.after(100, lambda: app.attributes('-topmost', False))
            print("✅ Starting main game...")
            
            app.mainloop()
            print("✅ Game completed")
            
        except Exception as e:
            print(f"❌ Direct launch error: {e}")
            import traceback
            traceback.print_exc()
            # Can't show messagebox - no Tk root exists
            print(f"FATAL: Failed to launch game directly: {str(e)}")
    
    def _flash_text(self):
        """Flash the continue text"""
        try:
            if self.flash_visible:
                self._canvas.itemconfig(self._flash_id, fill="#ffffff")
            else:
                self._canvas.itemconfig(self._flash_id, fill="#5a5a64")
        except Exception:
            return
        self.flash_visible = not self.flash_visible
        # Schedule next flash
        try:
            self.after(800, self._flash_text)  # Flash every 800ms
        except Exception:
            pass

    def _on_any_key(self, event):
        """Handle any key press (except ESC)"""
        if event.keysym != 'Escape':
            self._continue_to_launcher()
    
    def _on_escape(self, event):
        """Handle escape key"""
        self._launch_enhanced = False
        self.quit()


def main():
    """Main entry point"""
    try:
        splash = SplashLauncher()
        splash._launch_enhanced = False  # Initialize flag
        splash.mainloop()
        
        # After mainloop exits, check if we should launch enhanced
        if getattr(splash, '_launch_enhanced', False):
            splash._run_enhanced_launcher()
        
    except Exception as e:
        print(f"Splash launcher error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()