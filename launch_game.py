"""
Launch script for Puck Dynasty with proper splash and enhanced launcher
"""

def launch_with_splash():
    """Launch game with splash screen and enhanced launcher"""
    try:
        print("Starting Puck Dynasty...")
        
        from splash_launcher import SplashLauncher
        print("Launching splash screen...")
        splash = SplashLauncher()
        splash.mainloop()
        print("Application completed")
        
    except ImportError as e:
        print(f"Splash launcher not available: {e}")
        print("Falling back to direct launch...")
        launch_direct()
        
    except Exception as e:
        print(f"Splash launcher error: {e}")
        import traceback
        traceback.print_exc()
        print("Falling back to direct launch...")
        launch_direct()

def launch_direct():
    """Direct launch without splash/launcher"""
    try:
        print("Starting Hockey Manager directly...")
        
        from main import GameManager, HockeyManagerGUI
        
        gm = GameManager()
        print("Game manager created")
        
        default_settings = {
            'database_size': 'Medium',
            'fantasy_draft': False,
            'user_team': 'Carolina Hurricanes'
        }
        gm.apply_startup_settings(default_settings)
        print("Startup settings applied")
        
        app = HockeyManagerGUI(gm)
        app.lift()
        app.focus_force()
        app.attributes('-topmost', True)
        app.after(100, lambda: app.attributes('-topmost', False))
        
        print("Starting main loop...")
        app.mainloop()
        print("Application closed")
        
    except Exception as e:
        print(f"Direct launch error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    launch_with_splash()
