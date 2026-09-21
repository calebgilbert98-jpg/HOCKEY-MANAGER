#!/usr/bin/env python3
"""
Quick integration test for the professional calendar system.
Tests the calendar opening with the main application.
"""

import tkinter as tk
from main import GameManager, HockeyManagerGUI


def test_main_calendar_integration():
    """Test opening the professional calendar from main application."""
    print("🧪 INTEGRATION TEST: Professional Calendar with Main App")
    print("=" * 60)
    
    try:
        # Create game manager first
        print("✅ Creating Game Manager...")
        game_manager = GameManager()
        
        # Create GUI with game manager
        print("✅ Creating Hockey Manager GUI...")
        app = HockeyManagerGUI(game_manager)
        
        # Test calendar opening
        print("✅ Attempting to open professional calendar...")
        app.open_calendar_window()
        
        print("✅ Professional calendar opened successfully!")
        print("📅 Calendar integration test PASSED")
        
        # Close after brief display
        app.after(3000, app.quit)  # Close after 3 seconds
        app.mainloop()
        
    except Exception as e:
        print(f"❌ Integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    return True


if __name__ == "__main__":
    print("🏒 Hockey Manager Professional Calendar Integration Test")
    print("Testing Phase 4 integration with main application...")
    print()
    
    success = test_main_calendar_integration()
    
    if success:
        print("\n🎉 INTEGRATION TEST COMPLETED SUCCESSFULLY!")
        print("✅ Professional Calendar is ready for Phase 5")
    else:
        print("\n❌ Integration test failed - needs debugging")