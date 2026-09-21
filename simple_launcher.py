"""
Puck Dynasty - Professional Game Launcher
Entry point that loads the splash launcher with full background experience
"""

# Import the splash launcher first for best visual experience
try:
    from splash_launcher import SplashLauncher, main as splash_main
    print("✅ Splash launcher loaded successfully")
    
    # Use splash launcher as primary
    PuckDynastyLauncher = SplashLauncher
    main = splash_main
    
except ImportError as e:
    print(f"⚠️ Splash launcher not available ({e}), trying enhanced launcher...")
    
    # Fallback to enhanced launcher
    try:
        from enhanced_launcher import EnhancedPuckDynastyLauncher, main as enhanced_main
        print("✅ Enhanced launcher loaded as fallback")
        
        PuckDynastyLauncher = EnhancedPuckDynastyLauncher
        main = enhanced_main
        
    except ImportError as e2:
        print(f"⚠️ Enhanced launcher not available ({e2}), using basic fallback...")
        
        # Simple fallback launcher
        import tkinter as tk
        from tkinter import messagebox
        
        class PuckDynastyLauncher(tk.Tk):
            """Basic fallback launcher"""
            
            def __init__(self):
                super().__init__()
                self.title("Puck Dynasty - Basic Launcher")
                self.geometry("400x200")
                self.configure(bg='#181818')
                
                tk.Label(self, text="🏒 Puck Dynasty", 
                        font=('Segoe UI', 24, 'bold'),
                        bg='#181818', fg='#FFFFFF').pack(pady=30)
                
                tk.Button(self, text="Launch Game",
                         font=('Segoe UI', 14),
                         bg='#D13438', fg='white',
                         command=self._launch_game).pack(pady=10)
                
                tk.Button(self, text="Exit",
                         font=('Segoe UI', 12),
                         bg='#666666', fg='white',
                         command=self.quit).pack(pady=5)
            
            def _launch_game(self):
                """Launch the main game"""
                try:
                    self.withdraw()
                    from main import GameManager, HockeyManagerGUI
                    gm = GameManager()
                    app = HockeyManagerGUI(gm)
                    app.mainloop()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to launch game:\n{str(e)}")
                    self.deiconify()
        
        def main():
            """Main entry point for fallback"""
            launcher = PuckDynastyLauncher()
            launcher.mainloop()


# Entry point
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import tkinter.messagebox as messagebox
        messagebox.showerror("Launcher Error", f"Failed to start launcher:\n{str(e)}")