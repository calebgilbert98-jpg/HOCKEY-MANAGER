"""
Puck Dynasty - Simple Splash Launcher
Reliable splash screen that shows background and launches enhanced launcher
"""

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
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
        
        # Load background and create interface
        self._load_background()
        self._create_interface()
        
        # Bind keys - any key continues except ESC
        self.bind('<Key>', self._on_any_key)
        self.bind('<Button-1>', lambda e: self._continue_to_launcher())  # Mouse click also continues
        self.bind('<Escape>', self._on_escape)
        
        # Focus window
        self.focus_set()
        
    def _load_background(self):
        """Load background image"""
        self.background_image = None
        
        bg_files = [
            "puckdynastybackground.png",
            "hockey manager background.png",
            "hockey_bg.png", 
            "PUCK DYNASTY LOGO.png"
        ]
        
        for bg_file in bg_files:
            if os.path.exists(bg_file):
                try:
                    print(f"🏒 Loading background: {bg_file}")
                    original = Image.open(bg_file).convert('RGBA')
                    
                    # Resize to fit window
                    resized = original.resize((900, 600), Image.Resampling.LANCZOS)
                    
                    # Add dark overlay
                    overlay = Image.new('RGBA', resized.size, (0, 0, 0, 100))
                    self.background_image = Image.alpha_composite(resized, overlay)
                    
                    print("✅ Background loaded successfully")
                    break
                except Exception as e:
                    print(f"Background load error: {e}")
    
    def _create_interface(self):
        """Create simple interface"""
        # Main frame
        main_frame = tk.Frame(self, bg='#000000')
        main_frame.pack(fill='both', expand=True)
        
        # Background label
        if self.background_image:
            try:
                self.bg_photo = ImageTk.PhotoImage(self.background_image)
                bg_label = tk.Label(main_frame, image=self.bg_photo, bg='#000000')
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception as e:
                print(f"Background display error: {e}")
        
        # Flashing text overlay - no buttons or frames
        self.flash_label = tk.Label(main_frame,
                                   text="Press Any Key to Continue",
                                   font=('Segoe UI', 16, 'bold'),
                                   bg=main_frame['bg'], fg='#FFFFFF')
        self.flash_label.place(relx=0.5, rely=0.85, anchor='center')
        
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
        if hasattr(self, 'flash_label') and self.flash_label.winfo_exists():
            # Toggle visibility
            if self.flash_visible:
                self.flash_label.configure(fg='#FFFFFF')
            else:
                self.flash_label.configure(fg='#888888')
            
            self.flash_visible = not self.flash_visible
            
            # Schedule next flash
            self.after(800, self._flash_text)  # Flash every 800ms
    
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