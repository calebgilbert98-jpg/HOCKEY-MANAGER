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
    
    # ------------------------------------------------------------------
    # Modern animated game menu
    # ------------------------------------------------------------------
    def _menu_font(self, size, weight='normal'):
        return ('Segoe UI', size, weight)

    def _spaced(self, text):
        return ' '.join(list(text))

    def _create_interface(self):
        """Create the modern animated main menu stage."""
        self.geometry("1280x800")
        self.minsize(1024, 640)
        self.configure(bg='#05070c')

        self.canvas = tk.Canvas(self, highlightthickness=0, bg='#05070c')
        self.canvas.pack(fill='both', expand=True)

        self._mx = 96
        self._pulse = 0.0
        self._items = []
        self._sel = 0
        self._particles = []
        self._glow_shades = self._make_shades('#3d0f14', '#d13438', 28)
        self._ticker_msg = ("   2025-26 SEASON   \u2022   32 TEAMS   \u2022   1,312 GAMES   "
                            "\u2022   BUILD YOUR DYNASTY   \u2022   OWN THE ICE   \u2022")
        self._ticker_x = 0
        self._menu_alive = True
        self._paint_w = 0

        self._define_menu_items()
        self._repaint()

        self.canvas.bind('<Configure>', lambda e: self._on_menu_resize(e))
        self.bind('<Up>', lambda e: self._menu_move(-1))
        self.bind('<Down>', lambda e: self._menu_move(1))
        self.bind('<Return>', lambda e: self._menu_activate())
        self.bind('<Escape>', lambda e: self._exit_game())

        # Compatibility shims for existing logic
        self.continue_btn = _MenuItemShim(self, 'continue')
        self.after(60, self._menu_tick)

    def _define_menu_items(self):
        self._menu_defs = [
            {'id': 'new',      'label': 'NEW GAME',  'cmd': self._new_game,      'enabled': True},
            {'id': 'continue', 'label': 'CONTINUE',  'cmd': self._continue_game, 'enabled': False},
            {'id': 'load',     'label': 'LOAD GAME', 'cmd': self._load_game,     'enabled': True},
            {'id': 'settings', 'label': 'SETTINGS',  'cmd': self._open_settings, 'enabled': True},
            {'id': 'about',    'label': 'ABOUT',     'cmd': self._show_about,    'enabled': True},
            {'id': 'exit',     'label': 'EXIT',      'cmd': self._exit_game,     'enabled': True},
        ]

    def _on_menu_resize(self, event):
        if abs(event.width - self._paint_w) > 40:
            self._repaint()

    def _repaint(self):
        c = self.canvas
        W, H = c.winfo_width(), c.winfo_height()
        if W < 50 or H < 50:
            self.after(120, self._repaint)
            return
        self._paint_w = W
        c.delete('bg', 'chrome', 'menu', 'glow')
        self._paint_backdrop(W, H)
        self._paint_rink(W, H)
        self._paint_title_block(W, H)
        self._paint_menu_items(W, H)
        self._paint_chrome(W, H)
        self._sel = 0
        self._refresh_item_targets()

    # -- backdrop ----------------------------------------------------
    def _make_shades(self, c1, c2, n):
        def hx(h):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        a, b = hx(c1), hx(c2)
        out = []
        for i in range(n):
            t = i / max(n - 1, 1)
            out.append('#%02x%02x%02x' % tuple(int(a[j] + (b[j] - a[j]) * t) for j in range(3)))
        return out

    def _paint_backdrop(self, W, H):
        c = self.canvas
        top = (13, 22, 38)
        bottom = (4, 6, 11)
        steps = 64
        for i in range(steps):
            t = i / (steps - 1)
            col = '#%02x%02x%02x' % tuple(int(top[j] + (bottom[j] - top[j]) * t) for j in range(3))
            y0 = int(H * i / steps)
            y1 = int(H * (i + 1) / steps) + 1
            c.create_rectangle(0, y0, W, y1, fill=col, outline='', tags='bg')
        # soft red ambience, left side
        for i, (rx, alpha) in enumerate([(0.55, 1), (0.42, 1), (0.30, 1)]):
            shade = self._make_shades('#05070c', '#20090d', 3)[i % 3]
            c.create_oval(-W*0.25, H*0.05, W*rx, H*0.95, fill=shade, outline='', tags='bg')

    def _paint_rink(self, W, H):
        c = self.canvas
        line, faint = '#122033', '#0e1826'
        # blue lines
        for fy in (0.30, 0.70):
            y = H * fy
            c.create_line(W*0.30, y, W, y, fill=line, width=4, tags='bg')
        # center red line (dim)
        c.create_line(W*0.65, H*0.30, W*0.65, H*0.70, fill='#231016', width=4, tags='bg')
        # faceoff circles, right side
        for fy in (0.30, 0.70):
            cx, cy = W*0.82, H*fy
            r = H*0.075
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=faint, width=3, tags='bg')
            c.create_oval(cx-3, cy-3, cx+3, cy+3, fill=faint, outline='', tags='bg')
        # goal crease hint
        c.create_arc(W*0.97, H*0.44, W*1.06, H*0.56, start=90, extent=180,
                     outline=faint, width=3, style='arc', tags='bg')

    # -- title --------------------------------------------------------
    def _paint_title_block(self, W, H):
        c = self.canvas
        mx = self._mx
        c.create_text(mx, 108, text=self._spaced('A MODERN HOCKEY MANAGEMENT SIM'),
                      font=self._menu_font(12), fill='#d13438', anchor='w', tags='chrome')
        # glow copies (animated color)
        self._glow1 = c.create_text(mx, 196, text='PUCK', font=self._menu_font(78, 'bold'),
                                    fill=self._glow_shades[0], anchor='w', tags=('chrome', 'glow'))
        self._glow2 = c.create_text(mx, 282, text='DYNASTY', font=self._menu_font(78, 'bold'),
                                    fill=self._glow_shades[0], anchor='w', tags=('chrome', 'glow'))
        c.create_text(mx, 192, text='PUCK', font=self._menu_font(78, 'bold'),
                      fill='#f2f4f8', anchor='w', tags='chrome')
        c.create_text(mx, 278, text='DYNASTY', font=self._menu_font(78, 'bold'),
                      fill='#d13438', anchor='w', tags='chrome')
        c.create_text(mx, 336, text='Build your dynasty. Own the ice.',
                      font=self._menu_font(15, 'italic'), fill='#8b98ac', anchor='w', tags='chrome')
        c.create_line(mx, 366, mx+300, 366, fill='#d13438', width=2, tags='chrome')
        c.create_line(mx, 367, mx+300, 367, fill='#5a1418', width=1, tags='chrome')

    # -- menu items ----------------------------------------------------
    def _paint_menu_items(self, W, H):
        c = self.canvas
        self._items = []
        y0, gap = 406, 56
        for i, d in enumerate(self._menu_defs):
            y = y0 + i * gap
            bar = c.create_rectangle(self._mx-30, y-18, self._mx-30, y+18,
                                     fill='#d13438', outline='', tags='menu')
            txt = c.create_text(self._mx, y, text=d['label'],
                                font=self._menu_font(21, 'bold'),
                                fill='#e8ecf2' if d['enabled'] else '#4c5563',
                                anchor='w', tags='menu')
            tag = f"menuitem{i}"
            c.itemconfig(bar, tags=('menu', tag))
            c.itemconfig(txt, tags=('menu', tag))
            c.tag_bind(tag, '<Enter>', lambda e, i=i: self._menu_hover(i))
            c.tag_bind(tag, '<Leave>', lambda e: self._menu_hover(self._sel))
            c.tag_bind(tag, '<Button-1>', lambda e, i=i: self._menu_click(i))
            self._items.append({'def': d, 'y': y, 'text': txt, 'bar': bar,
                                'x': float(self._mx), 'tx': float(self._mx),
                                'bw': 0.0, 'tbw': 0.0})

    def _paint_chrome(self, W, H):
        c = self.canvas
        mx = self._mx
        self._status_id = c.create_text(mx, H-64, text='Ready to play',
                                        font=self._menu_font(12), fill='#6b7688',
                                        anchor='w', tags='chrome')
        self.status_label = _TextShim(c, self._status_id)
        self._ticker_id = c.create_text(W, H-20, text=self._ticker_msg,
                                        font=self._menu_font(11), fill='#2c3648',
                                        anchor='w', tags='chrome')
        c.create_text(W-28, H-64, text='\u2191 \u2193 NAVIGATE  \u00b7  ENTER SELECT',
                      font=self._menu_font(11), fill='#4c5563', anchor='e', tags='chrome')
        c.create_text(W-28, H-40, text='PUCK DYNASTY v2.0',
                      font=self._menu_font(11), fill='#4c5563', anchor='e', tags='chrome')

    # -- interaction ---------------------------------------------------
    def _menu_hover(self, i):
        if self._items[i]['def']['enabled']:
            self._sel = i
            self._refresh_item_targets()

    def _menu_click(self, i):
        d = self._items[i]['def']
        if d['enabled']:
            self._sel = i
            self._refresh_item_targets()
            d['cmd']()

    def _menu_move(self, direction):
        n = len(self._items)
        i = self._sel
        for _ in range(n):
            i = (i + direction) % n
            if self._items[i]['def']['enabled']:
                self._sel = i
                break
        self._refresh_item_targets()

    def _menu_activate(self):
        d = self._items[self._sel]['def']
        if d['enabled']:
            d['cmd']()

    def _refresh_item_targets(self):
        for i, it in enumerate(self._items):
            en = it['def']['enabled']
            if i == self._sel and en:
                it['tx'], it['tbw'] = self._mx + 16, 6.0
            else:
                it['tx'], it['tbw'] = float(self._mx), 0.0
            c = self.canvas
            try:
                c.itemconfig(it['text'],
                             fill='#ffffff' if (i == self._sel and en)
                             else ('#e8ecf2' if en else '#4c5563'))
            except tk.TclError:
                pass

    def _set_item_enabled(self, item_id, enabled):
        for it in self._items:
            if it['def']['id'] == item_id:
                it['def']['enabled'] = enabled
                break
        self._refresh_item_targets()

    # -- animation ------------------------------------------------------
    def _spawn_particles(self):
        import random
        W = max(self.canvas.winfo_width(), 1100)
        H = max(self.canvas.winfo_height(), 700)
        for _ in range(34):
            x = random.uniform(0, W)
            y = random.uniform(0, H)
            r = random.uniform(1.0, 2.6)
            sp = random.uniform(0.25, 0.9)
            shade = random.choice(['#1b2940', '#24344f', '#2e425f'])
            pid = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=shade,
                                          outline='', tags='fx')
            self._particles.append({'id': pid, 'sp': sp,
                                    'wob': random.uniform(0, 6.28),
                                    'x0': x})

    def _menu_tick(self):
        if not self._menu_alive:
            return
        try:
            if not self.winfo_exists():
                return
            c = self.canvas
            self._pulse += 0.055
            import math
            # title glow pulse
            gi = int((math.sin(self._pulse) * 0.5 + 0.5) * (len(self._glow_shades) - 1))
            col = self._glow_shades[gi]
            for gid in ('_glow1', '_glow2'):
                g = getattr(self, gid, None)
                if g:
                    try:
                        c.itemconfig(g, fill=col)
                    except tk.TclError:
                        pass
            # particles drift upward
            W = c.winfo_width() or 1100
            H = c.winfo_height() or 700
            for p in self._particles:
                try:
                    x0, y0, x1, y1 = c.coords(p['id'])
                except (tk.TclError, ValueError):
                    continue
                ny0, ny1 = y0 - p['sp'], y1 - p['sp']
                p['wob'] += 0.02
                nx = p['x0'] + math.sin(p['wob']) * 14
                dx = nx - (x0 + x1) / 2
                if ny1 < -6:
                    ny0, ny1 = H + 2, H + 6
                    p['x0'] = (p['x0'] + 370) % max(W, 1)
                    nx = p['x0']
                    dx = 0
                    c.coords(p['id'], nx-2, ny0, nx+2, ny1)
                else:
                    c.move(p['id'], dx, -p['sp'])
            # ticker scroll
            try:
                self._ticker_x -= 1.1
                tw = c.bbox(self._ticker_id)
                if tw and self._ticker_x < - (tw[2] - tw[0]):
                    self._ticker_x = W
                c.coords(self._ticker_id, self._ticker_x, H - 20)
            except tk.TclError:
                pass
            # menu item easing
            for it in self._items:
                it['x'] += (it['tx'] - it['x']) * 0.28
                it['bw'] += (it['tbw'] - it['bw']) * 0.30
                try:
                    c.coords(it['text'], it['x'], it['y'])
                    c.coords(it['bar'], self._mx - 30, it['y'] - 18,
                             self._mx - 30 + it['bw'], it['y'] + 18)
                except tk.TclError:
                    pass
        finally:
            if self._menu_alive:
                self.after(40, self._menu_tick)

    def _create_menu_content(self):
        """Legacy entry point kept for compatibility (menu is canvas-built)."""
        pass

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
        self._menu_alive = False
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


class _MenuItemShim:
    """Lets existing code enable/disable canvas menu rows like a button."""
    def __init__(self, menu, item_id):
        self._menu = menu
        self._item_id = item_id

    def configure(self, **kw):
        if 'state' in kw:
            self._menu._set_item_enabled(self._item_id, kw['state'] == 'normal')

    config = configure


class _TextShim:
    """Lets existing code set text on a canvas text item like a label."""
    def __init__(self, canvas, text_id):
        self._canvas = canvas
        self._text_id = text_id

    def configure(self, **kw):
        if 'text' in kw:
            try:
                self._canvas.itemconfig(self._text_id, text=kw['text'])
            except Exception:
                pass

    config = configure

