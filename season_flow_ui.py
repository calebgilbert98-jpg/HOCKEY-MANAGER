# season_flow_ui.py
# UI Components for Automated Season Flow
# Provides user interface for controlling season automation

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
from automated_season_flow import AutomatedSeasonFlow, AutoAdvanceMode, SeasonPhase, get_season_phase_color, format_days_until_milestone

class SeasonFlowControlPanel(ttk.Frame):
    """Control panel for automated season progression"""
    
    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self.parent = parent
        self.game_manager = game_manager
        
        # Initialize automation system
        self.automation = AutomatedSeasonFlow(game_manager)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the control panel UI"""
        # Main container with title
        title_frame = ttk.Frame(self)
        title_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(title_frame, text="⚡ AUTOMATED SEASON FLOW", 
                 style='Title.TLabel', font=('Segoe UI', 12, 'bold')).pack(side='left')
        
        # Current status display
        status_frame = ttk.LabelFrame(self, text="Season Status", padding=10)
        status_frame.pack(fill='x', padx=5, pady=5)
        
        # Phase indicator
        self.phase_frame = ttk.Frame(status_frame)
        self.phase_frame.pack(fill='x', pady=2)
        
        ttk.Label(self.phase_frame, text="Current Phase:", style='PlayerInfo.TLabel').pack(side='left')
        self.phase_label = ttk.Label(self.phase_frame, text="Regular Season", style='Header.TLabel')
        self.phase_label.pack(side='left', padx=(10, 0))
        
        # Next milestone
        self.milestone_frame = ttk.Frame(status_frame)
        self.milestone_frame.pack(fill='x', pady=2)
        
        ttk.Label(self.milestone_frame, text="Next Milestone:", style='PlayerInfo.TLabel').pack(side='left')
        self.milestone_label = ttk.Label(self.milestone_frame, text="Loading...", style='PlayerInfo.TLabel')
        self.milestone_label.pack(side='left', padx=(10, 0))
        
        # Automation controls
        control_frame = ttk.LabelFrame(self, text="Automation Controls", padding=10)
        control_frame.pack(fill='x', padx=5, pady=5)
        
        # Mode selection
        mode_frame = ttk.Frame(control_frame)
        mode_frame.pack(fill='x', pady=2)
        
        ttk.Label(mode_frame, text="Mode:", style='PlayerInfo.TLabel').pack(side='left')
        
        self.mode_var = tk.StringVar(value=AutoAdvanceMode.MANUAL.value)
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.mode_var, 
                                 values=[mode.value for mode in AutoAdvanceMode],
                                 state='readonly', width=20)
        mode_combo.pack(side='left', padx=(10, 0))
        mode_combo.bind('<<ComboboxSelected>>', self._on_mode_change)
        
        # Speed control
        speed_frame = ttk.Frame(control_frame)
        speed_frame.pack(fill='x', pady=2)
        
        ttk.Label(speed_frame, text="Speed:", style='PlayerInfo.TLabel').pack(side='left')
        
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = ttk.Scale(speed_frame, from_=0.1, to=10.0, 
                               variable=self.speed_var, orient='horizontal', length=150)
        speed_scale.pack(side='left', padx=(10, 0))
        
        self.speed_label = ttk.Label(speed_frame, text="1.0x", style='PlayerInfo.TLabel')
        self.speed_label.pack(side='left', padx=(5, 0))
        
        speed_scale.bind('<Motion>', self._update_speed_label)
        speed_scale.bind('<ButtonRelease-1>', self._on_speed_change)
        
        # Action buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        self.start_btn = ttk.Button(button_frame, text="🚀 Start Automation", 
                                   command=self._start_automation, style='TButton')
        self.start_btn.pack(side='left', padx=(0, 5))
        
        self.stop_btn = ttk.Button(button_frame, text="⏹️ Stop Automation", 
                                  command=self._stop_automation, style='TButton')
        self.stop_btn.pack(side='left', padx=5)
        self.stop_btn.config(state='disabled')
        
        self.settings_btn = ttk.Button(button_frame, text="⚙️ Settings", 
                                      command=self._open_settings, style='TButton')
        self.settings_btn.pack(side='right')
        
        # Quick advance buttons
        quick_frame = ttk.LabelFrame(self, text="Quick Actions", padding=10)
        quick_frame.pack(fill='x', padx=5, pady=5)
        
        quick_button_frame = ttk.Frame(quick_frame)
        quick_button_frame.pack(fill='x')
        
        ttk.Button(quick_button_frame, text="📅 Next Game", 
                  command=self._advance_to_next_game, style='Menu.TButton').pack(side='left', padx=(0, 5))
        ttk.Button(quick_button_frame, text="🎯 Next Milestone", 
                  command=self._advance_to_milestone, style='Menu.TButton').pack(side='left', padx=5)
        ttk.Button(quick_button_frame, text="📅 Skip Week", 
                  command=self._skip_week, style='Menu.TButton').pack(side='left', padx=5)
        ttk.Button(quick_button_frame, text="📅 Skip Month", 
                  command=self._skip_month, style='Menu.TButton').pack(side='right')
        
        # Update display
        self.update_display()
        
    def update_display(self):
        """Update the display with current information"""
        try:
            # Update phase
            current_phase = self.automation.update_season_phase()
            self.phase_label.config(text=current_phase.value)
            
            # Update next milestone
            next_milestone = self.automation.get_next_milestone()
            if next_milestone:
                days_until = format_days_until_milestone(next_milestone, self.game_manager.current_date)
                milestone_text = f"{next_milestone.name} in {days_until}"
                self.milestone_label.config(text=milestone_text)
            else:
                self.milestone_label.config(text="No upcoming milestones")
                
            # Update automation status
            if self.automation.automation_active:
                self.start_btn.config(state='disabled')
                self.stop_btn.config(state='normal')
            else:
                self.start_btn.config(state='normal')
                self.stop_btn.config(state='disabled')
                
        except Exception as e:
            print(f"Error updating season flow display: {e}")
            
    def _on_mode_change(self, event=None):
        """Handle automation mode change"""
        mode_value = self.mode_var.get()
        for mode in AutoAdvanceMode:
            if mode.value == mode_value:
                self.automation.settings.mode = mode
                break
                
    def _update_speed_label(self, event=None):
        """Update speed display label"""
        speed = self.speed_var.get()
        self.speed_label.config(text=f"{speed:.1f}x")
        
    def _on_speed_change(self, event=None):
        """Handle speed change"""
        speed = self.speed_var.get()
        self.automation.settings.days_per_second = speed
        
    def _start_automation(self):
        """Start automated season progression"""
        self.automation.start_automation()
        self.update_display()
        
    def _stop_automation(self):
        """Stop automated season progression"""
        self.automation.stop_automation()
        self.update_display()
        
    def _open_settings(self):
        """Open automation settings window"""
        SettingsWindow(self, self.automation)
        
    def _advance_to_next_game(self):
        """Advance to the next user team game"""
        try:
            current_date = self.game_manager.current_date
            
            # Find next user team game
            upcoming_games = self.automation._get_upcoming_user_games(30)  # Look 30 days ahead
            if not upcoming_games:
                tk.messagebox.showinfo("No Games", "No upcoming user team games found in the next 30 days.")
                return
                
            next_game = upcoming_games[0]
            target_date = next_game[0]
            
            # Advance days until we reach the game date
            days_to_advance = (target_date - current_date).days
            if days_to_advance > 0:
                self._advance_days(days_to_advance)
                
        except Exception as e:
            print(f"Error advancing to next game: {e}")
            tk.messagebox.showerror("Error", f"Failed to advance to next game: {e}")
            
    def _advance_to_milestone(self):
        """Advance to the next milestone"""
        try:
            next_milestone = self.automation.get_next_milestone()
            if not next_milestone:
                tk.messagebox.showinfo("No Milestones", "No upcoming milestones found.")
                return
                
            current_date = self.game_manager.current_date
            target_date = next_milestone.date
            
            days_to_advance = (target_date - current_date).days
            if days_to_advance > 0:
                self._advance_days(days_to_advance)
                
        except Exception as e:
            print(f"Error advancing to milestone: {e}")
            tk.messagebox.showerror("Error", f"Failed to advance to milestone: {e}")
            
    def _skip_week(self):
        """Skip ahead one week"""
        self._advance_days(7)
        
    def _skip_month(self):
        """Skip ahead one month"""
        self._advance_days(30)
        
    def _advance_days(self, days):
        """Advance the specified number of days"""
        try:
            for _ in range(days):
                self.game_manager.simulate_day()
                
            # Update displays
            self.update_display()
            if hasattr(self.game_manager, 'update_all_views'):
                self.game_manager.update_all_views()
                
            tk.messagebox.showinfo("Advanced", f"Advanced {days} day{'s' if days != 1 else ''}.")
            
        except Exception as e:
            print(f"Error advancing days: {e}")
            tk.messagebox.showerror("Error", f"Failed to advance days: {e}")

class SettingsWindow(tk.Toplevel):
    """Settings window for automation configuration"""
    
    def __init__(self, parent, automation):
        super().__init__(parent)
        self.parent = parent
        self.automation = automation
        
        self.title("Automation Settings")
        self.geometry("500x600")
        self.configure(background=parent.master.BG_COLOR)
        self.resizable(False, False)
        
        # Make it modal
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the settings UI"""
        main_frame = ttk.Frame(self, style='Panel.TFrame', padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(main_frame, text="⚙️ Automation Settings", 
                 style='Title.TLabel', font=('Segoe UI', 14, 'bold')).pack(pady=(0, 20))
        
        # Game simulation settings
        game_frame = ttk.LabelFrame(main_frame, text="Game Simulation", padding=10)
        game_frame.pack(fill='x', pady=(0, 10))
        
        self.sim_away_var = tk.BooleanVar(value=self.automation.settings.simulate_away_games)
        ttk.Checkbutton(game_frame, text="Simulate away games automatically", 
                       variable=self.sim_away_var).pack(anchor='w', pady=2)
        
        self.viewer_home_var = tk.BooleanVar(value=self.automation.settings.show_game_viewer_for_home)
        ttk.Checkbutton(game_frame, text="Show game viewer for home games", 
                       variable=self.viewer_home_var).pack(anchor='w', pady=2)
        
        self.viewer_away_var = tk.BooleanVar(value=self.automation.settings.show_game_viewer_for_away)
        ttk.Checkbutton(game_frame, text="Show game viewer for away games", 
                       variable=self.viewer_away_var).pack(anchor='w', pady=2)
        
        # Automation behavior
        behavior_frame = ttk.LabelFrame(main_frame, text="Automation Behavior", padding=10)
        behavior_frame.pack(fill='x', pady=(0, 10))
        
        self.pause_milestones_var = tk.BooleanVar(value=self.automation.settings.pause_at_milestones)
        ttk.Checkbutton(behavior_frame, text="Pause at important milestones", 
                       variable=self.pause_milestones_var).pack(anchor='w', pady=2)
        
        self.pause_games_var = tk.BooleanVar(value=self.automation.settings.pause_at_user_games)
        ttk.Checkbutton(behavior_frame, text="Pause at user team games", 
                       variable=self.pause_games_var).pack(anchor='w', pady=2)
        
        self.skip_offseason_var = tk.BooleanVar(value=self.automation.settings.auto_skip_offseason)
        ttk.Checkbutton(behavior_frame, text="Automatically skip off-season", 
                       variable=self.skip_offseason_var).pack(anchor='w', pady=2)
        
        # Milestone preview
        milestone_frame = ttk.LabelFrame(main_frame, text="Upcoming Milestones", padding=10)
        milestone_frame.pack(fill='both', expand=True, pady=(0, 20))
        
        # Create milestone list
        columns = ('Date', 'Milestone', 'Days Until')
        self.milestone_tree = ttk.Treeview(milestone_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.milestone_tree.heading(col, text=col)
            if col == 'Date':
                self.milestone_tree.column(col, width=100)
            elif col == 'Days Until':
                self.milestone_tree.column(col, width=80)
            else:
                self.milestone_tree.column(col, width=200)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(milestone_frame, orient='vertical', command=self.milestone_tree.yview)
        self.milestone_tree.configure(yscrollcommand=scrollbar.set)
        
        self.milestone_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Populate milestones
        self._populate_milestones()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')
        
        ttk.Button(button_frame, text="Save Settings", 
                  command=self._save_settings, style='TButton').pack(side='right', padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", 
                  command=self.destroy, style='TButton').pack(side='right')
        
    def _populate_milestones(self):
        """Populate the milestone tree"""
        try:
            current_date = self.automation.game_manager.current_date
            
            # Clear existing items
            for item in self.milestone_tree.get_children():
                self.milestone_tree.delete(item)
                
            # Add upcoming milestones (next 10)
            upcoming = [m for m in self.automation.milestones if m.date > current_date][:10]
            
            for milestone in upcoming:
                days_until = (milestone.date - current_date).days
                days_text = f"{days_until} day{'s' if days_until != 1 else ''}"
                
                self.milestone_tree.insert('', 'end', values=(
                    milestone.date.strftime('%b %d'),
                    milestone.name,
                    days_text
                ))
                
        except Exception as e:
            print(f"Error populating milestones: {e}")
            
    def _save_settings(self):
        """Save the automation settings"""
        try:
            settings = self.automation.settings
            settings.simulate_away_games = self.sim_away_var.get()
            settings.show_game_viewer_for_home = self.viewer_home_var.get()
            settings.show_game_viewer_for_away = self.viewer_away_var.get()
            settings.pause_at_milestones = self.pause_milestones_var.get()
            settings.pause_at_user_games = self.pause_games_var.get()
            settings.auto_skip_offseason = self.skip_offseason_var.get()
            
            tk.messagebox.showinfo("Settings Saved", "Automation settings have been updated.")
            self.destroy()
            
        except Exception as e:
            print(f"Error saving settings: {e}")
            tk.messagebox.showerror("Error", f"Failed to save settings: {e}")

class MilestoneNotificationWindow(tk.Toplevel):
    """Window for displaying milestone notifications"""
    
    def __init__(self, parent, milestone):
        super().__init__(parent)
        self.parent = parent
        self.milestone = milestone
        
        self.title(f"Milestone: {milestone.name}")
        self.geometry("400x300")
        self.configure(background=parent.BG_COLOR)
        self.resizable(False, False)
        
        # Center window
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the notification UI"""
        main_frame = ttk.Frame(self, style='Panel.TFrame', padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Icon and title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill='x', pady=(0, 20))
        
        # Use phase-appropriate emoji
        phase_icons = {
            SeasonPhase.TRADE_DEADLINE: "⏰",
            SeasonPhase.PLAYOFFS: "🏒", 
            SeasonPhase.ENTRY_DRAFT: "📋",
            SeasonPhase.FREE_AGENCY: "💰",
        }
        
        icon = phase_icons.get(self.milestone.phase, "🎯")
        ttk.Label(title_frame, text=icon, font=('Segoe UI', 32)).pack()
        ttk.Label(title_frame, text=self.milestone.name, 
                 style='Title.TLabel', font=('Segoe UI', 16, 'bold')).pack(pady=(10, 0))
        
        # Date
        ttk.Label(main_frame, text=self.milestone.date.strftime('%B %d, %Y'), 
                 style='Header.TLabel', font=('Segoe UI', 12)).pack(pady=(0, 10))
        
        # Description
        ttk.Label(main_frame, text=self.milestone.description, 
                 style='PlayerInfo.TLabel', wraplength=300, justify='center').pack(pady=(0, 20))
        
        # Phase indicator
        phase_frame = ttk.Frame(main_frame)
        phase_frame.pack(pady=(0, 20))
        
        ttk.Label(phase_frame, text="Season Phase:", style='PlayerInfo.TLabel').pack(side='left')
        phase_label = ttk.Label(phase_frame, text=self.milestone.phase.value, style='Header.TLabel')
        phase_label.pack(side='left', padx=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')
        
        ttk.Button(button_frame, text="Continue", 
                  command=self.destroy, style='TButton').pack(side='right')
        
        if self.milestone.is_critical:
            ttk.Button(button_frame, text="Open Relevant Window", 
                      command=self._open_relevant_window, style='TButton').pack(side='right', padx=(0, 10))
            
    def _open_relevant_window(self):
        """Open the relevant window for this milestone"""
        # This would open trade window for trade deadline, draft window for draft, etc.
        pass
