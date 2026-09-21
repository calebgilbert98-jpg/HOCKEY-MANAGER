"""
Test script for enhanced Trade Deadline Center with Phase 4 interactive tools
"""

import tkinter as tk
from trade_deadline_center import TradeDeadlineCenter
from trade_deadline_manager import get_deadline_manager

class TestApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Trade Deadline Center Test - Phase 4")
        self.root.geometry("300x200")
        self.root.configure(bg='#181818')
        
        # Mock game manager attributes
        self.game_manager = None
        
        self._create_test_ui()
        
    def _create_test_ui(self):
        """Create test interface"""
        tk.Label(self.root, text="Enhanced Trade Deadline Center",
                bg='#181818', fg='white',
                font=('Segoe UI', 14, 'bold')).pack(pady=20)
        
        tk.Label(self.root, text="Phase 4: Interactive Trade Tools",
                bg='#181818', fg='#F59E0B',
                font=('Segoe UI', 12)).pack(pady=10)
        
        # Test button
        test_btn = tk.Button(self.root, text="🚨 OPEN TRADE DEADLINE CENTER",
                            command=self._open_deadline_center,
                            bg='#DC2626', fg='white',
                            font=('Segoe UI', 12, 'bold'),
                            padx=20, pady=10)
        test_btn.pack(pady=20)
        
        # Features tested
        features_text = """Features Tested:
• Enhanced trade activity feed
• Breaking news system  
• Player movement tracker
• Quick trade interface
• Emergency trade mode
• Market browser"""
        
        tk.Label(self.root, text=features_text,
                bg='#181818', fg='#E0E0E0',
                font=('Segoe UI', 9), justify='left').pack(pady=10)
    
    def _open_deadline_center(self):
        """Open the Trade Deadline Center"""
        try:
            # Initialize deadline manager
            deadline_manager = get_deadline_manager(self.game_manager)
            
            # Create and show deadline center
            deadline_center = TradeDeadlineCenter(self.root)
            deadline_center.focus_set()
            
            print("✅ Trade Deadline Center opened successfully!")
            print("🎯 Test the following:")
            print("   • Breaking news notifications")
            print("   • Enhanced trade feed with impact ratings")
            print("   • Player movement tracker statistics")
            print("   • Quick Trade button → Opens streamlined trade interface")
            print("   • Emergency Trade button → Opens urgent deadline mode")
            print("   • Browse Market button → Opens market analysis")
            
        except Exception as e:
            print(f"❌ Error opening Trade Deadline Center: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """Run the test application"""
        print("🚀 Starting Enhanced Trade Deadline Center Test (Phase 4)")
        print("📅 This tests the interactive trade proposal tools")
        print("⚡ Features: Quick trades, emergency mode, market browser")
        print()
        self.root.mainloop()

if __name__ == "__main__":
    app = TestApp()
    app.run()