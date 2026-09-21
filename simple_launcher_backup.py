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
        
        # Fallback to basic launcher if enhanced version fails
        # Fallback to basic launcher if enhanced version fails
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog
        import os
        import sys
        from pathlib import Path
        from datetime import datetime
        import json
        import random
        from PIL import Image, ImageTk

        class PuckDynastyLauncher(tk.Tk):
            """Simplified professional game launcher (fallback version)"""
        
            def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Puck Dynasty - Hockey Management Simulator")
        self.geometry("900x600")
        self.minsize(800, 500)
        self.configure(bg='#0D1117')
        
        # State variables
        self.selected_save = None
        self.save_games = []
        
        # Initialize
        self._setup_window()
        self._create_interface()
        self._load_save_games()
        
        # Center window
        self._center_window()
        
        # Set up window close protocol
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _setup_window(self):
        """Configure window properties"""
        try:
            if os.path.exists("puck_dynasty_icon.ico"):
                self.iconbitmap("puck_dynasty_icon.ico")
        except:
            pass
        
        self.resizable(True, True)
        
    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def _create_interface(self):
        """Create the launcher interface"""
        # Header
        self._create_header()
        
        # Main content area
        self._create_main_content()
        
        # Footer
        self._create_footer()
        
    def _create_header(self):
        """Create header with branding"""
        header_frame = tk.Frame(self, bg='#161B22', height=100)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Title
        title_label = tk.Label(header_frame,
                              text="🏒 PUCK DYNASTY",
                              font=('Segoe UI', 28, 'bold'),
                              bg='#161B22', fg='#F0F6FC')
        title_label.pack(expand=True)
        
        subtitle_label = tk.Label(header_frame,
                                 text="Professional Hockey Management Simulator",
                                 font=('Segoe UI', 11),
                                 bg='#161B22', fg='#8B949E')
        subtitle_label.pack()
        
    def _create_main_content(self):
        """Create main content area"""
        content_frame = tk.Frame(self, bg='#0D1117')
        content_frame.pack(fill='both', expand=True, padx=40, pady=30)
        
        # Split into two columns
        left_frame = tk.Frame(content_frame, bg='#0D1117')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 20))
        
        right_frame = tk.Frame(content_frame, bg='#0D1117')
        right_frame.pack(side='right', fill='both', expand=True, padx=(20, 0))
        
        # Left: Quick actions
        self._create_quick_actions(left_frame)
        
        # Right: Save games
        self._create_save_games(right_frame)
        
    def _create_quick_actions(self, parent):
        """Create quick action buttons"""
        # Quick start section
        quick_frame = tk.LabelFrame(parent, text="  🚀 Quick Start  ",
                                   font=('Segoe UI', 14, 'bold'),
                                   bg='#0D1117', fg='#F0F6FC')
        quick_frame.pack(fill='x', pady=(0, 30))
        
        quick_container = tk.Frame(quick_frame, bg='#161B22', relief='solid', bd=1)
        quick_container.pack(fill='x', padx=15, pady=15)
        
        # New Career button
        new_btn = tk.Button(quick_container,
                           text="🏒 NEW CAREER",
                           font=('Segoe UI', 16, 'bold'),
                           bg='#238636', fg='white',
                           relief='flat', bd=0, pady=20,
                           cursor='hand2',
                           command=self._show_new_game_setup)
        new_btn.pack(fill='x', padx=20, pady=20)
        
        # Continue button (if saves exist)
        if self.save_games:
            continue_btn = tk.Button(quick_container,
                                   text="⚡ CONTINUE LAST GAME",
                                   font=('Segoe UI', 14, 'bold'),
                                   bg='#1F6FEB', fg='white',
                                   relief='flat', bd=0, pady=15,
                                   cursor='hand2',
                                   command=self._continue_last_game)
            continue_btn.pack(fill='x', padx=20, pady=(0, 20))
        
        # Tools section
        tools_frame = tk.LabelFrame(parent, text="  🔧 Tools  ",
                                   font=('Segoe UI', 14, 'bold'),
                                   bg='#0D1117', fg='#F0F6FC')
        tools_frame.pack(fill='x')
        
        tools_container = tk.Frame(tools_frame, bg='#161B22', relief='solid', bd=1)
        tools_container.pack(fill='x', padx=15, pady=15)
        
        # Tool buttons
        btn_style = {
            'font': ('Segoe UI', 11),
            'relief': 'flat',
            'bd': 0,
            'pady': 8,
            'cursor': 'hand2'
        }
        
        settings_btn = tk.Button(tools_container, text="⚙️ Settings",
                               bg='#6F42C1', fg='white', **btn_style,
                               command=self._open_settings)
        settings_btn.pack(fill='x', padx=20, pady=(20, 5))
        
        help_btn = tk.Button(tools_container, text="❓ Help & Guide",
                           bg='#6F42C1', fg='white', **btn_style,
                           command=self._open_help)
        help_btn.pack(fill='x', padx=20, pady=(5, 20))
        
    def _create_save_games(self, parent):
        """Create save games section"""
        saves_frame = tk.LabelFrame(parent, text="  📁 Save Games  ",
                                   font=('Segoe UI', 14, 'bold'),
                                   bg='#0D1117', fg='#F0F6FC')
        saves_frame.pack(fill='both', expand=True)
        
        saves_container = tk.Frame(saves_frame, bg='#161B22', relief='solid', bd=1)
        saves_container.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Save games list
        self.saves_tree = ttk.Treeview(saves_container,
                                      columns=('date', 'team'),
                                      show='headings',
                                      height=10)
        
        self.saves_tree.heading('#1', text='Save Name')
        self.saves_tree.heading('date', text='Date')
        self.saves_tree.heading('team', text='Team')
        
        self.saves_tree.column('#1', width=200)
        self.saves_tree.column('date', width=100)
        self.saves_tree.column('team', width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(saves_container, orient='vertical',
                                 command=self.saves_tree.yview)
        self.saves_tree.configure(yscrollcommand=scrollbar.set)
        
        self.saves_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Bind events
        self.saves_tree.bind('<<TreeviewSelect>>', self._on_save_select)
        self.saves_tree.bind('<Double-1>', self._load_selected_save)
        
        # Save management buttons
        btn_frame = tk.Frame(saves_container, bg='#161B22')
        btn_frame.pack(fill='x', pady=(10, 0))
        
        load_btn = tk.Button(btn_frame, text="📂 Load",
                           bg='#238636', fg='white',
                           font=('Segoe UI', 10), relief='flat', bd=0,
                           pady=8, padx=15, cursor='hand2',
                           command=self._load_selected_save)
        load_btn.pack(side='left', padx=(0, 10))
        
        delete_btn = tk.Button(btn_frame, text="🗑️ Delete",
                             bg='#DA3633', fg='white',
                             font=('Segoe UI', 10), relief='flat', bd=0,
                             pady=8, padx=15, cursor='hand2',
                             command=self._delete_selected_save)
        delete_btn.pack(side='left')
        
    def _create_footer(self):
        """Create footer"""
        footer_frame = tk.Frame(self, bg='#161B22', height=40)
        footer_frame.pack(fill='x', side='bottom')
        footer_frame.pack_propagate(False)
        
        # Status
        self.status_label = tk.Label(footer_frame, text="Ready to play",
                                   font=('Segoe UI', 10),
                                   bg='#161B22', fg='#8B949E')
        self.status_label.pack(side='left', padx=20, expand=True)
        
        # Exit button
        exit_btn = tk.Button(footer_frame, text="❌ Exit",
                           font=('Segoe UI', 10),
                           bg='#21262D', fg='#F0F6FC',
                           relief='flat', bd=0, pady=5, padx=15,
                           cursor='hand2',
                           command=self._on_closing)
        exit_btn.pack(side='right', padx=20)
        
    def _load_save_games(self):
        """Load available save games"""
        self.save_games = []
        
        try:
            for file in os.listdir('.'):
                if file.endswith(('.pdsave', '.save', '.sav')):
                    try:
                        stat = os.stat(file)
                        modified = datetime.fromtimestamp(stat.st_mtime)
                        
                        save_info = {
                            'filename': file,
                            'display_name': file.replace('.pdsave', '').replace('.save', '').replace('.sav', ''),
                            'date': modified.strftime('%Y-%m-%d'),
                            'team': 'Unknown'
                        }
                        
                        self.save_games.append(save_info)
                    except:
                        pass
        except:
            pass
            
        self._populate_saves_list()
        
    def _populate_saves_list(self):
        """Populate saves list"""
        # Clear existing
        for item in self.saves_tree.get_children():
            self.saves_tree.delete(item)
            
        # Add saves
        sorted_saves = sorted(self.save_games, key=lambda x: x['date'], reverse=True)
        
        for save in sorted_saves:
            self.saves_tree.insert('', 'end',
                                 text=save['display_name'],
                                 values=(save['date'], save['team']))
        
        # Select first save if available
        if sorted_saves:
            children = self.saves_tree.get_children()
            if children:
                self.saves_tree.selection_set(children[0])
                self.selected_save = sorted_saves[0]
                
    def _on_save_select(self, event):
        """Handle save selection"""
        selection = self.saves_tree.selection()
        if selection:
            item = selection[0]
            save_name = self.saves_tree.item(item, 'text')
            
            for save in self.save_games:
                if save['display_name'] == save_name:
                    self.selected_save = save
                    break
                    
    def _show_new_game_setup(self):
        """Show new game setup window"""
        setup_window = tk.Toplevel(self)
        setup_window.title("New Game Setup")
        setup_window.geometry("600x500")
        setup_window.configure(bg='#0D1117')
        setup_window.transient(self)
        setup_window.grab_set()
        
        # Center window
        setup_window.update_idletasks()
        x = (setup_window.winfo_screenwidth() // 2) - (300)
        y = (setup_window.winfo_screenheight() // 2) - (250)
        setup_window.geometry(f'600x500+{x}+{y}')
        
        # Header
        tk.Label(setup_window, text="🏒 New Game Setup",
                font=('Segoe UI', 20, 'bold'),
                bg='#0D1117', fg='#F0F6FC').pack(pady=30)
        
        # Main setup frame
        main_frame = tk.Frame(setup_window, bg='#161B22', relief='solid', bd=1)
        main_frame.pack(fill='both', expand=True, padx=40, pady=(0, 30))
        
        # Team selection
        tk.Label(main_frame, text="Your Team:",
                font=('Segoe UI', 14, 'bold'),
                bg='#161B22', fg='#F0F6FC').pack(pady=(30, 10))
        
        teams = ["Boston Bruins", "Montreal Canadiens", "Toronto Maple Leafs", 
                "New York Rangers", "Pittsburgh Penguins", "Colorado Avalanche",
                "Edmonton Oilers", "Vegas Golden Knights"]
        
        self.team_var = tk.StringVar(value="Boston Bruins")
        team_combo = ttk.Combobox(main_frame, textvariable=self.team_var,
                                 values=teams, state='readonly',
                                 font=('Segoe UI', 12))
        team_combo.pack(pady=(0, 10))
        
        # Random team button
        tk.Button(main_frame, text="🎲 Random Team",
                 font=('Segoe UI', 10),
                 bg='#1F6FEB', fg='white',
                 relief='flat', bd=0, pady=5, padx=15,
                 cursor='hand2',
                 command=lambda: self.team_var.set(random.choice(teams))).pack(pady=(0, 20))
        
        # Game options
        tk.Label(main_frame, text="Game Options:",
                font=('Segoe UI', 14, 'bold'),
                bg='#161B22', fg='#F0F6FC').pack(pady=(20, 15))
        
        # Options
        self.fantasy_var = tk.BooleanVar()
        fantasy_check = tk.Checkbutton(main_frame,
                                      text="🎲 Fantasy Draft (redistribute all players)",
                                      variable=self.fantasy_var,
                                      font=('Segoe UI', 11),
                                      bg='#161B22', fg='#F0F6FC',
                                      selectcolor='#21262D')
        fantasy_check.pack(pady=5)
        
        self.historical_var = tk.BooleanVar()
        historical_check = tk.Checkbutton(main_frame,
                                         text="📜 Use historical rosters (past seasons)",
                                         variable=self.historical_var,
                                         font=('Segoe UI', 11),
                                         bg='#161B22', fg='#F0F6FC',
                                         selectcolor='#21262D')
        historical_check.pack(pady=5)
        
        self.salary_cap_var = tk.BooleanVar(value=True)
        salary_check = tk.Checkbutton(main_frame,
                                     text="💰 Salary cap enabled ($83.5M)",
                                     variable=self.salary_cap_var,
                                     font=('Segoe UI', 11),
                                     bg='#161B22', fg='#F0F6FC',
                                     selectcolor='#21262D')
        salary_check.pack(pady=5)
        
        # Buttons
        btn_frame = tk.Frame(setup_window, bg='#0D1117')
        btn_frame.pack(fill='x', padx=40, pady=(0, 30))
        
        tk.Button(btn_frame, text="❌ Cancel",
                 font=('Segoe UI', 11),
                 bg='#6E7681', fg='white',
                 relief='flat', bd=0, pady=10, padx=20,
                 cursor='hand2',
                 command=setup_window.destroy).pack(side='left')
        
        tk.Button(btn_frame, text="🚀 Start Game",
                 font=('Segoe UI', 14, 'bold'),
                 bg='#238636', fg='white',
                 relief='flat', bd=0, pady=12, padx=30,
                 cursor='hand2',
                 command=lambda: self._start_game_from_setup(setup_window)).pack(side='right')
        
    def _start_game_from_setup(self, setup_window):
        """Start game with setup options"""
        try:
            setup_window.destroy()
            
            # Get options
            team = self.team_var.get()
            fantasy = self.fantasy_var.get()
            historical = self.historical_var.get()
            salary_cap = self.salary_cap_var.get()
            
            # Show starting message
            options = []
            if fantasy:
                options.append("Fantasy Draft")
            if historical:
                options.append("Historical")
            if not salary_cap:
                options.append("No Salary Cap")
                
            options_text = " • ".join(options) if options else "Standard"
            
            self.status_label.config(text=f"Starting: {team} ({options_text})")
            self.update()
            
            # Start the game
            self._start_main_game()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start game:\n{str(e)}")
            
    def _start_main_game(self):
        """Start the main game"""
        try:
            self.withdraw()
            
            from main import GameManager, HockeyManagerGUI
            
            # Create game manager with default settings
            gm = GameManager()
            
            # Create and start the main game application directly
            app = HockeyManagerGUI(gm)
            app.mainloop()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start game:\n{str(e)}")
            self.deiconify()
        finally:
            self.quit()
            
    def _load_selected_save(self, event=None):
        """Load selected save"""
        if not self.selected_save:
            messagebox.showwarning("No Selection", "Please select a save game.")
            return
            
        try:
            self.status_label.config(text=f"Loading {self.selected_save['display_name']}...")
            self.update()
            
            self._start_main_game()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load save:\n{str(e)}")
            
    def _continue_last_game(self):
        """Continue most recent save"""
        if self.save_games:
            recent = sorted(self.save_games, key=lambda x: x['date'], reverse=True)[0]
            self.selected_save = recent
            self._load_selected_save()
        else:
            messagebox.showinfo("No Saves", "No save games found.")
            
    def _delete_selected_save(self):
        """Delete selected save"""
        if not self.selected_save:
            messagebox.showwarning("No Selection", "Please select a save game.")
            return
            
        result = messagebox.askyesno("Confirm Delete",
                                   f"Delete '{self.selected_save['display_name']}'?\n\n"
                                   "This cannot be undone.")
        if result:
            try:
                os.remove(self.selected_save['filename'])
                self._load_save_games()
                self.status_label.config(text="Save deleted")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete save:\n{str(e)}")
                
    def _open_settings(self):
        """Open settings window"""
        messagebox.showinfo("Settings", "Settings window would open here.")
        
    def _open_help(self):
        """Open help window"""
        messagebox.showinfo("Help", "Game manual and help would open here.")
        
    def _on_closing(self):
        """Handle window closing"""
        self.quit()
        self.destroy()


def main():
    """Main entry point"""
    try:
        launcher = PuckDynastyLauncher()
        launcher.mainloop()
    except Exception as e:
        messagebox.showerror("Launcher Error", f"Failed to start launcher:\n{str(e)}")


# Entry point
def main():
    """Main entry point - use enhanced launcher if available, fallback otherwise"""
    try:
        if 'enhanced_main' in globals():
            enhanced_main()
        else:
            launcher = PuckDynastyLauncher()
            launcher.mainloop()
    except Exception as e:
        import tkinter.messagebox as messagebox
        messagebox.showerror("Launcher Error", f"Failed to start launcher:\n{str(e)}")


if __name__ == "__main__":
    main()