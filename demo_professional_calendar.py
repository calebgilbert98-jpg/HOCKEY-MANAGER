"""
Live Professional Calendar Demo
==============================

This demonstrates the professional calendar integrated with the main 
Hockey Manager application, replacing the old calendar system.
"""

import tkinter as tk
from datetime import date, timedelta
from professional_calendar_manager import create_calendar_window
from schedule_engine import ScheduleEngine, ScheduleConfiguration, ScheduleGenerationMode


def create_demo_schedule_engine():
    """Create a demo schedule engine with realistic data."""
    from collections import namedtuple
    Team = namedtuple('Team', ['team_name'])
    
    # Create NHL-style teams
    teams = [
        Team('Boston Bruins'),
        Team('New York Rangers'), 
        Team('Montreal Canadiens'),
        Team('Toronto Maple Leafs'),
        Team('Pittsburgh Penguins'),
        Team('Philadelphia Flyers'),
        Team('Washington Capitals'),
        Team('New York Islanders')
    ]
    
    config = ScheduleConfiguration(
        season_start_date=date(2024, 10, 1),
        season_end_date=date(2025, 4, 30),
        teams=teams,
        games_per_team=20,  # Reduced for demo
        generation_mode=ScheduleGenerationMode.PROFESSIONAL,
        allow_back_to_back=False,  # Professional constraints
        preferred_game_days=[1, 2, 4, 5, 6]  # Tue, Wed, Fri, Sat, Sun
    )
    
    return ScheduleEngine(config)


def create_demo_parent():
    """Create a demo parent that mimics HockeyManagerGUI."""
    
    class DemoHockeyManager(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("🏒 Hockey Manager - Professional Calendar Demo")
            self.geometry("800x600")
            
            # Set up styling (matching main app)
            self._setup_styles()
            
            # Mock user team
            from collections import namedtuple
            Team = namedtuple('Team', ['team_name', 'city'])
            self.user_team = Team('Boston Bruins', 'Boston')
            
            # Open windows tracking
            self.open_windows = {}
            
            # Create UI
            self._create_demo_ui()
        
        def _setup_styles(self):
            """Set up visual styles matching the main app."""
            self.BG_COLOR = '#181818'
            self.CONTENT_BG = '#1F1F1F'
            self.TITLE_BAR_COLOR = '#2A2A2A'
            self.TEXT_COLOR = '#E0E0E0'
            self.HEADER_COLOR = '#FFFFFF'
            self.ACCENT_COLOR = '#D13438'
            self.ACCENT_ACTIVE = '#A1272A'
            self.ACCENT_HOVER = '#E54E52'
            self.FONT_FAMILY = 'Segoe UI'
            
            self.configure(bg=self.BG_COLOR)
        
        def _create_demo_ui(self):
            """Create demo UI with calendar launch button."""
            # Title
            title_frame = tk.Frame(self, bg=self.TITLE_BAR_COLOR, height=60)
            title_frame.pack(fill='x')
            title_frame.pack_propagate(False)
            
            title_label = tk.Label(title_frame,
                                  text="🏒 Hockey Manager - Professional Calendar Demo",
                                  bg=self.TITLE_BAR_COLOR,
                                  fg=self.HEADER_COLOR,
                                  font=(self.FONT_FAMILY, 16, 'bold'))
            title_label.pack(expand=True)
            
            # Main content
            content_frame = tk.Frame(self, bg=self.BG_COLOR)
            content_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Demo info
            info_text = """🎯 Professional Calendar System Demo

This demonstrates the new professional calendar system that replaces 
the old calendar_window.py with advanced features:

✅ Schedule Engine Integration (Phase 3)
✅ Professional Color Coding
✅ Advanced Event Management
✅ Performance Optimizations
✅ Modern UI Design

Click the button below to launch the professional calendar!"""
            
            info_label = tk.Label(content_frame,
                                 text=info_text,
                                 bg=self.BG_COLOR,
                                 fg=self.TEXT_COLOR,
                                 font=(self.FONT_FAMILY, 11),
                                 justify='left',
                                 wraplength=500)
            info_label.pack(pady=20)
            
            # Calendar launch button
            self.calendar_button = tk.Button(content_frame,
                                           text="🗓️ Open Professional Calendar",
                                           bg=self.ACCENT_COLOR,
                                           fg='white',
                                           font=(self.FONT_FAMILY, 14, 'bold'),
                                           padx=30, pady=15,
                                           command=self.open_professional_calendar,
                                           relief='flat')
            self.calendar_button.pack(pady=20)
            
            # Status label
            self.status_label = tk.Label(content_frame,
                                       text="Ready to launch professional calendar...",
                                       bg=self.BG_COLOR,
                                       fg=self.TEXT_COLOR,
                                       font=(self.FONT_FAMILY, 10))
            self.status_label.pack(pady=10)
            
            # Schedule engine status
            self.schedule_status = tk.Label(content_frame,
                                          text="Creating schedule engine...",
                                          bg=self.BG_COLOR,
                                          fg='#4CAF50',
                                          font=(self.FONT_FAMILY, 9))
            self.schedule_status.pack()
            
            # Create schedule engine
            self.after(100, self._initialize_schedule_engine)
        
        def _initialize_schedule_engine(self):
            """Initialize the schedule engine in the background."""
            try:
                self.schedule_engine = create_demo_schedule_engine()
                self.schedule_status.config(text="✅ Schedule engine ready - Professional mode enabled")
                self.status_label.config(text="🚀 Ready! Click button to launch professional calendar.")
                self.calendar_button.config(state='normal')
                
                # Generate initial schedule
                events = self.schedule_engine.generate_schedule()
                validation = self.schedule_engine.validate_current_schedule()
                
                stats_text = f"📊 Schedule: {len(events)} events, Validation: {'✅ Pass' if validation.is_valid else '⚠️ Issues'}"
                
                stats_label = tk.Label(self.calendar_button.master,
                                     text=stats_text,
                                     bg=self.BG_COLOR,
                                     fg='#4CAF50',
                                     font=(self.FONT_FAMILY, 9))
                stats_label.pack(pady=5)
                
            except Exception as e:
                self.schedule_status.config(text=f"❌ Error: {e}", fg='#F44336')
                self.calendar_button.config(state='disabled')
        
        def open_professional_calendar(self):
            """Open the professional calendar window."""
            try:
                self.status_label.config(text="🗓️ Opening professional calendar...")
                self.update()
                
                # Create the professional calendar window
                calendar_window = create_calendar_window(self, self.schedule_engine)
                
                self.status_label.config(text="✅ Professional calendar opened successfully!")
                
                # Focus the calendar window
                calendar_window.lift()
                calendar_window.focus_force()
                
            except Exception as e:
                self.status_label.config(text=f"❌ Error opening calendar: {e}", fg='#F44336')
                print(f"Calendar error: {e}")
                import traceback
                traceback.print_exc()
    
    return DemoHockeyManager()


def run_live_calendar_demo():
    """Run the live professional calendar demo."""
    print("🚀 LAUNCHING LIVE PROFESSIONAL CALENDAR DEMO")
    print("=" * 50)
    
    try:
        # Create demo application
        print("Creating demo application...")
        app = create_demo_parent()
        
        print("✅ Demo application created")
        print("✅ Professional calendar system ready")
        print("✅ Schedule engine integration active")
        
        print("\n🎯 DEMO FEATURES:")
        print("   • Professional color-coded events")
        print("   • Schedule engine integration") 
        print("   • Modern calendar UI")
        print("   • Event interaction system")
        print("   • Performance optimizations")
        
        print(f"\n🏒 User Team: {app.user_team.team_name}")
        print("🗓️ Click the button in the demo window to open the calendar!")
        
        # Run the demo
        app.mainloop()
        
        print("\n🎉 Demo completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_live_calendar_demo()
    if success:
        print("\n✅ PROFESSIONAL CALENDAR DEMO COMPLETED!")
    else:
        print("\n❌ DEMO FAILED!")
    
    input("\nPress Enter to exit...")
    exit(0 if success else 1)