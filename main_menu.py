"""
Modern Main Menu for Hockey Manager
Professional main menu with New Game, Continue, Load Game, and Settings options
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
from datetime import datetime
from save_load_system import SaveLoadWindow, GameSaveManager

# Try to import PIL for image support
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class MainMenu(tk.Tk):
    """Modern main menu interface for Hockey Manager"""
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.title("🏒 Hockey Manager Pro")
        self.geometry("1200x800")
        self.configure(bg='#0a0a0a')
        self.resizable(True, True)
        
        # Game launch settings
        self.launch_mode = None  # 'new', 'continue', 'load'
        self.load_file_path = None
        self.new_game_settings = None
        
        # Style setup
        self._setup_styles()
        
        # Load background
        self.background_photo = None
        self.background_image = None
        self._load_background_image()
        
        # Create UI
        self._create_interface()
        
        # Center window
        self._center_window()
        
        # Check for existing saves
        self._check_continue_availability()
        
        # Setup proper cleanup
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_styles(self):
        """Setup modern dark theme styles"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Color scheme
        self.BG_COLOR = '#0a0a0a'
        self.PANEL_COLOR = '#1a1a1a'
        self.ACCENT_COLOR = '#d13438'
        self.ACCENT_HOVER = '#e54e52'
        self.TEXT_COLOR = '#ffffff'
        self.SUBTITLE_COLOR = '#b0b0b0'
        
        # Configure styles
        self.style.configure('Menu.TFrame', background=self.PANEL_COLOR)
        self.style.configure('MenuTitle.TLabel', 
                           background=self.PANEL_COLOR, 
                           foreground=self.TEXT_COLOR,
                           font=('Segoe UI', 32, 'bold'))
        self.style.configure('MenuSubtitle.TLabel',
                           background=self.PANEL_COLOR,
                           foreground=self.SUBTITLE_COLOR,
                           font=('Segoe UI', 14))
        self.style.configure('MenuButton.TButton',
                           font=('Segoe UI', 16, 'bold'),
                           foreground=self.TEXT_COLOR,
                           background=self.ACCENT_COLOR,
                           borderwidth=0,
                           focuscolor='none',
                           lightcolor=self.ACCENT_COLOR,
                           darkcolor=self.ACCENT_COLOR)
        self.style.map('MenuButton.TButton',
                     background=[('active', self.ACCENT_HOVER),
                               ('pressed', '#a1272a')])
        
        self.style.configure('MenuSecondary.TButton',
                           font=('Segoe UI', 14),
                           foreground=self.TEXT_COLOR,
                           background='#2a2a2a',
                           borderwidth=0,
                           focuscolor='none')
        self.style.map('MenuSecondary.TButton',
                     background=[('active', '#3a3a3a'),
                               ('pressed', '#1a1a1a')])
    
    def _load_background_image(self):
        """Load background image if available"""
        # Temporarily disable background images to prevent pyimage errors
        print("Main menu background images temporarily disabled to prevent pyimage errors")
        return
        
        if not PIL_AVAILABLE:
            return
        
        image_paths = [
            "hockey_bg.png", "hockey_bg.jpg", "background.png", "background.jpg",
            "assets/background.png", "images/hockey_bg.png"
        ]
        
        for path in image_paths:
            if os.path.exists(path):
                try:
                    image = Image.open(path)
                    # Resize to fit window
                    image = image.resize((1200, 800), Image.Resampling.LANCZOS)
                    # Apply dark overlay for better text readability
                    overlay = Image.new('RGBA', image.size, (10, 10, 10, 180))
                    image = Image.alpha_composite(image.convert('RGBA'), overlay)
                    
                    # Store the PIL image to prevent garbage collection
                    self.background_image = image
                    self.background_photo = ImageTk.PhotoImage(image)
                    print(f"Main menu loaded background image: {path}")
                    break
                except Exception as e:
                    print(f"Failed to load {path}: {e}")
                    # Clear any partial references
                    self.background_photo = None
                    self.background_image = None
    
    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _create_interface(self):
        """Create the main menu interface"""
        # Main container
        if self.background_photo:
            try:
                # Canvas with background image
                self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.BG_COLOR)
                self.canvas.pack(fill='both', expand=True)
                
                # Test if we can use the image
                test_label = tk.Label(self.canvas, image=self.background_photo)
                test_label.destroy()  # If this works, the image is valid
                
                self.canvas.create_image(600, 400, anchor='center', image=self.background_photo)
                parent = self.canvas
                print("Main menu background image applied successfully")
            except (tk.TclError, AttributeError) as e:
                print(f"Main menu background image error: {e}")
                # Fall back to simple frame
                if hasattr(self, 'canvas'):
                    self.canvas.destroy()
                self.background_photo = None
                main_frame = tk.Frame(self, bg=self.BG_COLOR)
                main_frame.pack(fill='both', expand=True)
                parent = main_frame
        else:
            # Simple frame without background
            main_frame = tk.Frame(self, bg=self.BG_COLOR)
            main_frame.pack(fill='both', expand=True)
            parent = main_frame
        
        # Central menu panel
        self.menu_panel = tk.Frame(parent, bg=self.PANEL_COLOR, 
                                  relief='solid', borderwidth=1)
        
        if self.background_photo:
            self.canvas.create_window(600, 400, anchor='center', window=self.menu_panel)
        else:
            self.menu_panel.place(relx=0.5, rely=0.5, anchor='center')
        
        self._create_menu_content()
    
    def _create_menu_content(self):
        """Create the menu panel content"""
        # Title section
        title_frame = tk.Frame(self.menu_panel, bg=self.PANEL_COLOR)
        title_frame.pack(pady=(40, 20))
        
        # Game title
        title_label = ttk.Label(title_frame, text="HOCKEY MANAGER", 
                               style='MenuTitle.TLabel')
        title_label.pack()
        
        # Version/subtitle
        subtitle_label = ttk.Label(title_frame, text="Professional Hockey Management Simulation", 
                                  style='MenuSubtitle.TLabel')
        subtitle_label.pack(pady=(5, 0))
        
        # Menu buttons section
        buttons_frame = tk.Frame(self.menu_panel, bg=self.PANEL_COLOR)
        buttons_frame.pack(pady=20, padx=60)
        
        # Main menu buttons
        self.new_game_btn = ttk.Button(buttons_frame, text="🏒 NEW GAME", 
                                      command=self._new_game,
                                      style='MenuButton.TButton')
        self.new_game_btn.pack(fill='x', pady=8, ipady=15)
        
        self.continue_btn = ttk.Button(buttons_frame, text="▶️ CONTINUE", 
                                      command=self._continue_game,
                                      style='MenuButton.TButton',
                                      state='disabled')
        self.continue_btn.pack(fill='x', pady=8, ipady=15)
        
        self.load_game_btn = ttk.Button(buttons_frame, text="📁 LOAD GAME", 
                                       command=self._load_game,
                                       style='MenuButton.TButton')
        self.load_game_btn.pack(fill='x', pady=8, ipady=15)
        
        # Secondary options
        secondary_frame = tk.Frame(self.menu_panel, bg=self.PANEL_COLOR)
        secondary_frame.pack(pady=(10, 0))
        
        settings_btn = ttk.Button(secondary_frame, text="⚙️ Settings", 
                                 command=self._open_settings,
                                 style='MenuSecondary.TButton')
        settings_btn.pack(side='left', padx=(0, 10), ipady=10)
        
        about_btn = ttk.Button(secondary_frame, text="ℹ️ About", 
                              command=self._show_about,
                              style='MenuSecondary.TButton')
        about_btn.pack(side='left', padx=10, ipady=10)
        
        exit_btn = ttk.Button(secondary_frame, text="❌ Exit", 
                             command=self._exit_game,
                             style='MenuSecondary.TButton')
        exit_btn.pack(side='left', padx=(10, 0), ipady=10)
        
        # Status bar
        status_frame = tk.Frame(self.menu_panel, bg=self.PANEL_COLOR)
        status_frame.pack(side='bottom', fill='x', pady=(20, 20))
        
        self.status_label = ttk.Label(status_frame, text="Ready to play", 
                                     style='MenuSubtitle.TLabel')
        self.status_label.pack()
    
    def _check_continue_availability(self):
        """Check if there's a recent save to continue from"""
        try:
            saves_dir = "saves"
            if not os.path.exists(saves_dir):
                return
            
            # Look for the most recent save file
            save_files = []
            for filename in os.listdir(saves_dir):
                if filename.endswith('.hm'):
                    filepath = os.path.join(saves_dir, filename)
                    if os.path.isfile(filepath):
                        mtime = os.path.getmtime(filepath)
                        save_files.append((filepath, mtime))
            
            if save_files:
                # Enable continue button
                self.continue_btn.configure(state='normal')
                # Store the most recent save file
                save_files.sort(key=lambda x: x[1], reverse=True)
                self.continue_save_path = save_files[0][0]
                
                # Update status
                filename = os.path.basename(self.continue_save_path)
                modified = datetime.fromtimestamp(save_files[0][1])
                self.status_label.configure(text=f"Recent save: {filename} ({modified.strftime('%m/%d %H:%M')})")
            
        except Exception as e:
            print(f"Error checking continue availability: {e}")
    
    def _new_game(self):
        """Start a new game"""
        self.status_label.configure(text="Setting up new game...")
        self.update()
        
        # Import and show startup window for team selection
        from startup_window import StartupWindow
        
        try:
            # Create startup window (handles singleton internally)
            startup = StartupWindow()
            
            # Hide main menu temporarily
            self.withdraw()
            
            # Center startup window
            startup.geometry("1000x700")
            startup.update_idletasks()
            x = (startup.winfo_screenwidth() // 2) - 500
            y = (startup.winfo_screenheight() // 2) - 350
            startup.geometry(f"1000x700+{x}+{y}")
            
            startup.mainloop()
            
            if startup.game_settings:
                self.launch_mode = 'new'
                self.new_game_settings = startup.game_settings
                self.destroy()  # Close main menu
            else:
                self.deiconify()  # Show main menu again
                self.status_label.configure(text="New game cancelled")
                
        except Exception as e:
            print(f"Error creating startup window: {e}")
            self.deiconify()  # Show main menu again
            self.status_label.configure(text=f"Error: {str(e)}")
    
    def _continue_game(self):
        """Continue from the most recent save"""
        if not hasattr(self, 'continue_save_path'):
            messagebox.showerror("Error", "No recent save file found")
            return
        
        self.status_label.configure(text="Loading recent save...")
        self.update()
        
        self.launch_mode = 'load'
        self.load_file_path = self.continue_save_path
        self.destroy()
    
    def _load_game(self):
        """Open load game dialog"""
        self.status_label.configure(text="Opening load game dialog...")
        self.update()
        
        # Create a temporary parent for the load dialog
        temp_parent = tk.Toplevel()
        temp_parent.withdraw()
        
        # Configure temp parent to match our styling
        temp_parent.configure(bg=self.BG_COLOR)
        temp_parent.title("Load Game")
        temp_parent.geometry("800x600")
        
        # Show temp parent
        temp_parent.deiconify()
        temp_parent.focus_set()
        
        # Create load window
        load_window = SaveLoadWindow(temp_parent, mode='load')
        
        # Wait for load window to close
        self.wait_window(load_window)
        
        # Check if a game was loaded
        if hasattr(load_window, 'loaded_file_path') and load_window.loaded_file_path:
            self.launch_mode = 'load'
            self.load_file_path = load_window.loaded_file_path
            temp_parent.destroy()
            self.destroy()
        else:
            temp_parent.destroy()
            self.status_label.configure(text="Load game cancelled")
    
    def _open_settings(self):
        """Open settings dialog"""
        self._show_settings_dialog()
    
    def _show_settings_dialog(self):
        """Show settings configuration dialog"""
        settings_window = tk.Toplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("600x400")
        settings_window.configure(bg=self.PANEL_COLOR)
        settings_window.resizable(False, False)
        
        # Center on parent
        settings_window.transient(self)
        settings_window.grab_set()
        
        # Settings content
        main_frame = tk.Frame(settings_window, bg=self.PANEL_COLOR)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Settings", 
                 font=('Segoe UI', 18, 'bold'),
                 foreground=self.TEXT_COLOR,
                 background=self.PANEL_COLOR).pack(pady=(0, 20))
        
        # Graphics settings
        graphics_frame = tk.LabelFrame(main_frame, text="Graphics", 
                                      bg=self.PANEL_COLOR, fg=self.TEXT_COLOR,
                                      font=('Segoe UI', 12, 'bold'))
        graphics_frame.pack(fill='x', pady=10)
        
        self.fullscreen_var = tk.BooleanVar()
        tk.Checkbutton(graphics_frame, text="Fullscreen mode", 
                      variable=self.fullscreen_var,
                      bg=self.PANEL_COLOR, fg=self.TEXT_COLOR,
                      selectcolor=self.PANEL_COLOR,
                      activebackground=self.PANEL_COLOR,
                      activeforeground=self.TEXT_COLOR).pack(anchor='w', padx=10, pady=5)
        
        # Game settings
        game_frame = tk.LabelFrame(main_frame, text="Game Settings", 
                                  bg=self.PANEL_COLOR, fg=self.TEXT_COLOR,
                                  font=('Segoe UI', 12, 'bold'))
        game_frame.pack(fill='x', pady=10)
        
        self.autosave_var = tk.BooleanVar(value=True)
        tk.Checkbutton(game_frame, text="Enable autosave", 
                      variable=self.autosave_var,
                      bg=self.PANEL_COLOR, fg=self.TEXT_COLOR,
                      selectcolor=self.PANEL_COLOR,
                      activebackground=self.PANEL_COLOR,
                      activeforeground=self.TEXT_COLOR).pack(anchor='w', padx=10, pady=5)
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg=self.PANEL_COLOR)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Apply", 
                  command=lambda: self._apply_settings(settings_window),
                  style='MenuSecondary.TButton').pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="Cancel", 
                  command=settings_window.destroy,
                  style='MenuSecondary.TButton').pack(side='left', padx=5)
    
    def _apply_settings(self, window):
        """Apply settings and close dialog"""
        # Here you would save settings to file or apply them
        messagebox.showinfo("Settings", "Settings applied successfully!")
        window.destroy()
    
    def _show_about(self):
        """Show about dialog"""
        about_text = """Hockey Manager Pro
        
A comprehensive hockey management simulation game.

Features:
• Complete team management
• Player development and trading
• Advanced game simulation
• Draft system
• Financial management
• Modern UI with dark theme

Version: 2024.1
Developed with Python and Tkinter"""
        
        messagebox.showinfo("About Hockey Manager Pro", about_text)
    
    def _exit_game(self):
        """Exit the application"""
        if messagebox.askyesno("Exit", "Are you sure you want to exit Hockey Manager?"):
            self.destroy()
    
    def _cleanup_resources(self):
        """Clean up image resources to prevent memory leaks"""
        try:
            if hasattr(self, 'background_photo') and self.background_photo:
                del self.background_photo
                self.background_photo = None
            if hasattr(self, 'background_image') and self.background_image:
                self.background_image.close()
                del self.background_image
                self.background_image = None
        except Exception as e:
            print(f"Error cleaning up main menu resources: {e}")
    
    def _on_closing(self):
        """Handle window closing properly"""
        self._cleanup_resources()
        self.destroy()
    
    def destroy(self):
        """Override destroy to ensure proper cleanup"""
        self._cleanup_resources()
        super().destroy()


def launch_hockey_manager():
    """Launch Hockey Manager through the main menu"""
    # Show main menu
    menu = MainMenu()
    menu.mainloop()
    
    # Check what the user wants to do
    if not hasattr(menu, 'launch_mode') or menu.launch_mode is None:
        return  # User closed menu without selecting anything
    
    # Import main game components
    from main import GameManager, HockeyManagerGUI
    from save_load_system import GameSaveManager
    
    try:
        if menu.launch_mode == 'new':
            # Start new game with settings from startup window
            print("Starting new game...")
            gm = GameManager()
            gm.apply_startup_settings(menu.new_game_settings)
            
            # Extract team selection from settings
            if 'selected_team' in menu.new_game_settings:
                gm.set_user_team(menu.new_game_settings['selected_team'])
            
            # Launch main game
            app = HockeyManagerGUI(gm)
            app.startup_settings = menu.new_game_settings
            app._update_game_viewer_button_state()
            app.mainloop()
            
        elif menu.launch_mode == 'load':
            # Load existing save
            print(f"Loading game from: {menu.load_file_path}")
            gm = GameManager()
            save_manager = GameSaveManager(gm)
            
            if save_manager.load_game(menu.load_file_path):
                print("Game loaded successfully")
                app = HockeyManagerGUI(gm)
                app.on_game_loaded()  # Mark as loaded game for autosave
                app._update_game_viewer_button_state()
                app.mainloop()
            else:
                messagebox.showerror("Load Error", "Failed to load the selected save file")
                
    except Exception as e:
        import traceback
        print(f"Error launching game: {e}")
        traceback.print_exc()
        messagebox.showerror("Launch Error", f"Failed to start Hockey Manager:\n{str(e)}")

    def _cleanup_resources(self):
        """Clean up image resources to prevent memory leaks"""
        try:
            if hasattr(self, 'background_photo') and self.background_photo:
                del self.background_photo
                self.background_photo = None
            if hasattr(self, 'background_image') and self.background_image:
                self.background_image.close()
                del self.background_image
                self.background_image = None
        except Exception as e:
            print(f"Error cleaning up main menu resources: {e}")
    
    def _on_closing(self):
        """Handle window closing properly"""
        self._cleanup_resources()
        self.destroy()
    
    def destroy(self):
        """Override destroy to ensure proper cleanup"""
        self._cleanup_resources()
        super().destroy()


if __name__ == "__main__":
    launch_hockey_manager()
