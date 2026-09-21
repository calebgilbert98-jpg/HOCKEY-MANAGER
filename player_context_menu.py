"""
Universal Player Context Menu System
Provides consistent right-click player interactions across all windows
"""

import tkinter as tk
from tkinter import messagebox

class PlayerContextMenu:
    """Universal player context menu for consistent player interactions across all windows"""
    
    def __init__(self, parent_window):
        self.parent = parent_window
        
    def show_context_menu(self, event, player, additional_options=None):
        """
        Show context menu for a player
        
        Args:
            event: The right-click event
            player: The Player object
            additional_options: List of tuples (label, command) for window-specific options
        """
        context_menu = tk.Menu(self.parent, tearoff=0)
        
        # Configure menu styling to match parent window
        if hasattr(self.parent, 'CONTENT_BG'):
            context_menu.configure(
                bg=self.parent.CONTENT_BG,
                fg=self.parent.TEXT_COLOR,
                activebackground=self.parent.ACCENT_COLOR,
                activeforeground='white',
                font=('Segoe UI', 9)
            )
        
        # Standard player options
        context_menu.add_command(
            label=f"👤 View {player.full_name}'s Profile",
            command=lambda: self._view_player_profile(player)
        )
        
        context_menu.add_separator()
        
        context_menu.add_command(
            label="🔍 Scout Player",
            command=lambda: self._scout_player(player)
        )
        
        context_menu.add_command(
            label="⭐ Add to Shortlist",
            command=lambda: self._add_to_shortlist(player)
        )
        
        context_menu.add_command(
            label="📊 Compare with Another Player",
            command=lambda: self._compare_players(player)
        )
        
        context_menu.add_separator()
        
        # Development and training options
        context_menu.add_command(
            label="🎯 Assign Training Focus",
            command=lambda: self._assign_training_focus(player)
        )
        
        context_menu.add_command(
            label="📈 View Development History",
            command=lambda: self._view_development_history(player)
        )
        
        # Contract and management options
        context_menu.add_separator()
        
        context_menu.add_command(
            label="💼 Contract Details",
            command=lambda: self._view_contract_details(player)
        )
        
        context_menu.add_command(
            label="🔄 Propose Trade",
            command=lambda: self._propose_trade(player)
        )
        
        # Check if player is on user's team for team-specific options
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            if (player in self.parent.user_team.roster or 
                player in self.parent.user_team.ahl_roster or 
                player in self.parent.user_team.prospects):
                
                context_menu.add_command(
                    label="🔄 Move Between Rosters",
                    command=lambda: self._move_between_rosters(player)
                )
        
        # Add window-specific options if provided
        if additional_options:
            context_menu.add_separator()
            for label, command in additional_options:
                context_menu.add_command(label=label, command=command)
        
        # Show menu
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def _view_player_profile(self, player):
        """Open player profile window"""
        try:
            from ui_components import PlayerProfileWindow
            PlayerProfileWindow(self.parent, player)
        except ImportError:
            # Fallback if PlayerProfileWindow doesn't exist
            messagebox.showinfo(
                "Player Profile", 
                f"Player: {player.full_name}\\n"
                f"Position: {player.primary_position.value}\\n"
                f"Age: {player.age}\\n"
                f"Overall Rating: {player.overall_rating()}\\n"
                f"Potential: {getattr(player, 'potential', 'Unknown')}\\n\\n"
                f"Team: {getattr(player, 'team_name', 'Free Agent')}"
            )
    
    def _scout_player(self, player):
        """Open scouting assignment dialog or show existing report"""
        # Check if player is already being scouted
        if (hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'user_team') and
            hasattr(self.parent.parent.user_team, 'scouting_reports')):
            
            report = self.parent.parent.user_team.scouting_reports.get(player.id)
            if report:
                # Show existing scouting report
                accuracy = getattr(report.scout, 'jpa', 75) if hasattr(report, 'scout') else 75
                potential = getattr(report, 'scouted_potential', 'Unknown')
                viewings = getattr(report, 'viewings', 1)
                
                messagebox.showinfo(
                    "Existing Scouting Report",
                    f"Scout Report: {player.full_name}\\n\\n"
                    f"Scout: {report.scout.full_name if hasattr(report, 'scout') else 'Unknown'}\\n"
                    f"Accuracy: {accuracy}%\\n"
                    f"Viewings: {viewings}\\n"
                    f"Potential: {potential}\\n\\n"
                    f"Status: {'Complete' if viewings >= 3 else 'In Progress'}"
                )
                return
        
        # Try to open scouting window or create assignment
        try:
            # Try to open or focus existing scouting window
            if hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'open_scouting_window'):
                self.parent.parent.open_scouting_window()
                messagebox.showinfo("Scout Assignment", f"Scouting window opened. Assign a scout to {player.full_name} from the prospects list.")
            elif hasattr(self.parent, 'open_scouting_window'):
                self.parent.open_scouting_window()
                messagebox.showinfo("Scout Assignment", f"Scouting window opened. Assign a scout to {player.full_name} from the prospects list.")
            else:
                # Create quick scout assignment dialog
                self._create_scout_assignment_dialog(player)
        except Exception as e:
            # Fallback to assignment dialog
            self._create_scout_assignment_dialog(player)
    
    def _create_scout_assignment_dialog(self, player):
        """Create a dialog for scout assignment"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Scout Assignment - {player.full_name}")
        dialog.geometry("400x300")
        dialog.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        
        # Header
        header = tk.Label(dialog, text=f"Assign Scout to {player.full_name}", 
                         font=('Segoe UI', 12, 'bold'))
        header.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                        bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header.pack(pady=20)
        
        # Get available scouts
        available_scouts = []
        try:
            if (hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'user_team') and
                hasattr(self.parent.parent.user_team, 'staff')):
                from game_classes import StaffRole
                available_scouts = [s for s in self.parent.parent.user_team.staff 
                                  if hasattr(s, 'role') and str(s.role) == 'StaffRole.SCOUT']
        except Exception:
            available_scouts = []
        
        if available_scouts:
            # Scout selection
            select_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
            select_frame.pack(fill='x', padx=20, pady=10)
            
            tk.Label(select_frame, text="Select Scout:", 
                    fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                    bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
            
            from tkinter import ttk
            scout_var = tk.StringVar()
            scout_combo = ttk.Combobox(select_frame, textvariable=scout_var,
                                     values=[f"{s.full_name} (JPA: {getattr(s, 'jpa', 75)})" for s in available_scouts],
                                     state='readonly')
            scout_combo.pack(fill='x', pady=5)
            
            def assign_scout():
                if scout_var.get():
                    selected_scout = available_scouts[scout_combo.current()]
                    messagebox.showinfo("Scout Assigned", 
                                      f"{selected_scout.full_name} assigned to scout {player.full_name}!")
                    dialog.destroy()
            
            assign_btn = ttk.Button(select_frame, text="Assign Scout", command=assign_scout)
            assign_btn.pack(pady=10)
        else:
            # No scouts available
            no_scouts = tk.Label(dialog, text="No scouts available\\nHire scouts in the Staff Management section",
                               fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                               bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
            no_scouts.pack(pady=20)
        
        # Close button
        from tkinter import ttk
        close_btn = ttk.Button(dialog, text="Close", command=dialog.destroy)
        close_btn.pack(pady=10)
    
    def _add_to_shortlist(self, player):
        """Add player to shortlist with category selection"""
        # Create shortlist dialog
        shortlist_dialog = tk.Toplevel(self.parent)
        shortlist_dialog.title("Add to Shortlist")
        shortlist_dialog.geometry("400x300")
        shortlist_dialog.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        shortlist_dialog.resizable(False, False)
        
        # Make modal
        shortlist_dialog.transient(self.parent)
        shortlist_dialog.grab_set()
        
        # Title
        title_label = tk.Label(shortlist_dialog, 
                              text=f"Add {player.full_name} to Shortlist",
                              font=(getattr(self.parent, 'FONT_FAMILY', 'Segoe UI'), 14, 'bold'),
                              fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                              bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        title_label.pack(pady=10)
        
        # Category selection
        category_frame = tk.LabelFrame(shortlist_dialog, text="Category", 
                                      fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                      bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        category_frame.pack(fill='x', padx=20, pady=10)
        
        from shortlist_system import ShortlistManager
        category_var = tk.StringVar(value="Trade Targets")
        
        from tkinter import ttk
        category_combo = ttk.Combobox(category_frame, textvariable=category_var,
                                     values=ShortlistManager.CATEGORIES,
                                     state="readonly")
        category_combo.pack(fill='x', padx=10, pady=5)
        
        # Priority selection
        priority_frame = tk.LabelFrame(shortlist_dialog, text="Priority",
                                      fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                      bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        priority_frame.pack(fill='x', padx=20, pady=5)
        
        priority_var = tk.StringVar(value="Medium Priority")
        priority_combo = ttk.Combobox(priority_frame, textvariable=priority_var,
                                     values=list(ShortlistManager.PRIORITY_LEVELS.values()),
                                     state="readonly")
        priority_combo.pack(fill='x', padx=10, pady=5)
        
        # Notes
        notes_frame = tk.LabelFrame(shortlist_dialog, text="Notes",
                                   fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                   bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        notes_frame.pack(fill='both', expand=True, padx=20, pady=5)
        
        notes_text = tk.Text(notes_frame, height=4, wrap="word",
                            bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'),
                            fg=getattr(self.parent, 'TEXT_COLOR', 'white'))
        notes_text.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Buttons
        button_frame = tk.Frame(shortlist_dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        button_frame.pack(fill='x', padx=20, pady=10)
        
        def add_player():
            category = category_var.get()
            priority_text = priority_var.get()
            priority = next((k for k, v in ShortlistManager.PRIORITY_LEVELS.items() 
                           if v == priority_text), 2)
            notes = notes_text.get("1.0", "end-1c")
            
            # Get shortlist manager
            if hasattr(self.parent, 'shortlist_manager'):
                shortlist_manager = self.parent.shortlist_manager
            elif hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'shortlist_manager'):
                shortlist_manager = self.parent.parent.shortlist_manager
            else:
                messagebox.showerror("Error", "Shortlist manager not available.")
                shortlist_dialog.destroy()
                return
            
            # Add to shortlist
            if shortlist_manager.add_player(player.id, player.full_name, category, notes, priority):
                messagebox.showinfo("Added to Shortlist", 
                                   f"{player.full_name} added to {category}!")
                shortlist_dialog.destroy()
            else:
                messagebox.showwarning("Already on Shortlist", 
                                      f"{player.full_name} is already in {category}.")
        
        ttk.Button(button_frame, text="Add to Shortlist", command=add_player).pack(side="left")
        ttk.Button(button_frame, text="Cancel", command=shortlist_dialog.destroy).pack(side="right")
    
    def _compare_players(self, player):
        """Open enhanced player comparison tool"""
        self._create_enhanced_comparison_window(player)
    
    def _create_comparison_window(self, player):
        """Create comparison window"""
        compare_window = tk.Toplevel(self.parent)
        compare_window.title(f"Compare Players - {player.full_name}")
        compare_window.geometry("600x500")
        
        # Configure window colors if parent has them
        if hasattr(self.parent, 'BG_COLOR'):
            compare_window.configure(bg=self.parent.BG_COLOR)
        
        # Header
        header_label = tk.Label(compare_window, 
                               text=f"Player Comparison - {player.full_name}",
                               font=('Segoe UI', 16, 'bold'))
        if hasattr(self.parent, 'HEADER_COLOR'):
            header_label.configure(fg=self.parent.HEADER_COLOR, bg=self.parent.BG_COLOR)
        header_label.pack(pady=20)
        
        # Instructions
        instructions = tk.Label(compare_window,
                               text="Select another player to compare attributes and potential",
                               font=('Segoe UI', 10))
        if hasattr(self.parent, 'TEXT_COLOR'):
            instructions.configure(fg=self.parent.TEXT_COLOR, bg=self.parent.BG_COLOR)
        instructions.pack(pady=10)
        
        # Player selection frame
        selection_frame = tk.Frame(compare_window)
        if hasattr(self.parent, 'BG_COLOR'):
            selection_frame.configure(bg=self.parent.BG_COLOR)
        selection_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Get all players for comparison
        all_players = []
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            all_players = (self.parent.user_team.roster + 
                          self.parent.user_team.ahl_roster + 
                          self.parent.user_team.prospects)
        
        # Player selection
        select_label = tk.Label(selection_frame, text="Compare with:", font=('Segoe UI', 11, 'bold'))
        if hasattr(self.parent, 'TEXT_COLOR'):
            select_label.configure(fg=self.parent.TEXT_COLOR, bg=self.parent.BG_COLOR)
        select_label.pack(anchor='w')
        
        from tkinter import ttk
        compare_var = tk.StringVar()
        compare_combo = ttk.Combobox(selection_frame, textvariable=compare_var,
                                   values=[p.full_name for p in all_players if p != player],
                                   state='readonly', width=40)
        compare_combo.pack(anchor='w', pady=10, fill='x')
        
        def do_comparison():
            selected_name = compare_var.get()
            if selected_name:
                compare_player = next((p for p in all_players if p.full_name == selected_name), None)
                if compare_player:
                    self._show_comparison_results(player, compare_player, compare_window)
        
        compare_btn = ttk.Button(selection_frame, text="Compare Players", command=do_comparison)
        compare_btn.pack(pady=10)
    
    def _show_enhanced_comparison_results(self, player1, player2, results_frame):
        """Show enhanced comparison results in the provided frame"""
        # Clear existing results
        for widget in results_frame.winfo_children():
            widget.destroy()
        
        # Header
        header = tk.Label(results_frame, 
                         text=f"{player1.full_name} vs {player2.full_name}",
                         font=('Segoe UI', 14, 'bold'))
        header.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                        bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        header.pack(pady=10)
        
        # Create scrollable comparison
        from tkinter import ttk
        
        # Treeview for comparison
        columns = ('Attribute', player1.full_name, player2.full_name, 'Advantage')
        tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Attribute':
                tree.column(col, width=120)
            elif col == 'Advantage':
                tree.column(col, width=80)
            else:
                tree.column(col, width=100)
        
        # Comparison data
        comparison_data = [
            ("Overall Rating", player1.overall_rating(), player2.overall_rating()),
            ("Age", player1.age, player2.age),
            ("Potential", getattr(player1, 'potential', 10), getattr(player2, 'potential', 10)),
            ("Skating", getattr(player1, 'skating', 10), getattr(player2, 'skating', 10)),
            ("Shooting", getattr(player1, 'shooting', 10), getattr(player2, 'shooting', 10)),
            ("Passing", getattr(player1, 'passing', 10), getattr(player2, 'passing', 10)),
            ("Defense", getattr(player1, 'defense', 10), getattr(player2, 'defense', 10)),
            ("Hockey IQ", getattr(player1, 'hockey_iq', 10), getattr(player2, 'hockey_iq', 10)),
            ("Physical", getattr(player1, 'physical', 10), getattr(player2, 'physical', 10)),
        ]
        
        for stat, val1, val2 in comparison_data:
            # Determine advantage
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if val1 > val2:
                    advantage = player1.full_name[:10] + "..."
                elif val2 > val1:
                    advantage = player2.full_name[:10] + "..."
                else:
                    advantage = "Tied"
            else:
                advantage = "N/A"
            
            tree.insert('', 'end', values=(stat, str(val1), str(val2), advantage))
        
        tree.pack(fill='both', expand=True, pady=10)
        
        # Summary
        summary_frame = tk.Frame(results_frame, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        summary_frame.pack(fill='x', pady=10)
        
        # Calculate overall advantage
        p1_advantages = sum(1 for _, v1, v2 in comparison_data 
                           if isinstance(v1, (int, float)) and isinstance(v2, (int, float)) and v1 > v2)
        p2_advantages = sum(1 for _, v1, v2 in comparison_data 
                           if isinstance(v1, (int, float)) and isinstance(v2, (int, float)) and v2 > v1)
        
        if p1_advantages > p2_advantages:
            winner = player1.full_name
            margin = "significant" if p1_advantages - p2_advantages > 3 else "slight"
        elif p2_advantages > p1_advantages:
            winner = player2.full_name
            margin = "significant" if p2_advantages - p1_advantages > 3 else "slight"
        else:
            winner = "Neither player"
            margin = "very close"
        
        summary_text = f"Summary: {winner} has a {margin} advantage overall."
        
        summary_label = tk.Label(summary_frame, text=summary_text, font=('Segoe UI', 11, 'bold'),
                               fg=getattr(self.parent, 'ACCENT_COLOR', '#D13438'),
                               bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        summary_label.pack()
    
    def _assign_training_focus(self, player):
        """Open training focus assignment"""
        try:
            # Try to open development window with player pre-selected
            if hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'open_development_window'):
                self.parent.parent.open_development_window()
                messagebox.showinfo("Development Window", f"Development window opened. Select {player.full_name} for training assignment.")
            elif hasattr(self.parent, 'open_development_window'):
                self.parent.open_development_window()
                messagebox.showinfo("Development Window", f"Development window opened. Select {player.full_name} for training assignment.")
            else:
                # Create training assignment dialog
                self._create_training_assignment_dialog(player)
        except Exception:
            self._create_training_assignment_dialog(player)
    
    def _create_training_assignment_dialog(self, player):
        """Create training assignment dialog"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Training Assignment - {player.full_name}")
        dialog.geometry("400x350")
        dialog.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        
        # Header
        header = tk.Label(dialog, text=f"Assign Training for {player.full_name}", 
                         font=('Segoe UI', 12, 'bold'))
        header.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                        bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header.pack(pady=15)
        
        # Current attributes display
        current_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        current_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(current_frame, text="Current Attributes:", font=('Segoe UI', 10, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        attributes = [
            ('Skating', getattr(player, 'skating', 10)),
            ('Shooting', getattr(player, 'shooting', 10)),
            ('Passing', getattr(player, 'passing', 10)),
            ('Defense', getattr(player, 'defense', 10)),
        ]
        
        for attr_name, value in attributes:
            attr_text = f"{attr_name}: {value}"
            tk.Label(current_frame, text=attr_text, font=('Segoe UI', 9),
                    fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                    bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        # Training focus selection
        focus_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        focus_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(focus_frame, text="Select Training Focus:", font=('Segoe UI', 10, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        from tkinter import ttk
        focus_var = tk.StringVar()
        focus_options = ["Skating", "Shooting", "Passing", "Defense", "Physical Conditioning", "Hockey IQ"]
        focus_combo = ttk.Combobox(focus_frame, textvariable=focus_var,
                                 values=focus_options, state='readonly')
        focus_combo.pack(fill='x', pady=5)
        
        # Training intensity
        intensity_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        intensity_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(intensity_frame, text="Training Intensity:", font=('Segoe UI', 10, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        intensity_var = tk.StringVar(value="Medium")
        intensities = ["Light", "Medium", "Heavy"]
        for intensity in intensities:
            tk.Radiobutton(intensity_frame, text=intensity, variable=intensity_var, value=intensity,
                         fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                         bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'),
                         selectcolor=getattr(self.parent, 'ACCENT_COLOR', '#D13438')).pack(anchor='w')
        
        def assign_training():
            if focus_var.get():
                messagebox.showinfo("Training Assigned", 
                                  f"{player.full_name} assigned to {intensity_var.get().lower()} {focus_var.get().lower()} training!\\n\\n"
                                  f"Training will continue for 2 weeks.")
                dialog.destroy()
        
        # Buttons
        button_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        button_frame.pack(fill='x', padx=20, pady=15)
        
        ttk.Button(button_frame, text="Assign Training", command=assign_training).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def _view_development_history(self, player):
        """Show player development history"""
        messagebox.showinfo(
            "Development History",
            f"Development History - {player.full_name}\\n\\n"
            f"Current Stage: Developing\\n"
            f"Recent Activities:\\n"
            f"• Completed skating training program\\n"
            f"• Overall rating progress tracked\\n"
            f"• Regular practice participation\\n\\n"
            f"Next Steps: Continue current development path"
        )
    
    def _view_contract_details(self, player):
        """Open player profile with contract tab selected"""
        try:
            from ui_components import PlayerProfileWindow
            # Create the profile window
            profile_window = PlayerProfileWindow(self.parent, player)
            # Focus on the contract tab (tab index 3 based on order: Overview, Attributes, Stats, Contract, Development)
            profile_window.notebook.select(3)
        except (ImportError, Exception) as e:
            # Fallback to message box if profile window unavailable
            if hasattr(player, 'contract') and player.contract:
                salary = f"${getattr(player.contract, 'salary', 750000):,}"
                years = getattr(player.contract, 'years_remaining', 1)
                contract_type = getattr(player.contract, 'contract_type', 'Standard')
            else:
                salary = "$750,000"
                years = 1
                contract_type = "Entry Level"
                
            messagebox.showinfo(
                "Contract Details",
                f"Contract Information - {player.full_name}\\n\\n"
                f"Salary: {salary}\\n"
                f"Contract Length: {years} year(s) remaining\\n"
                f"Contract Type: {contract_type}\\n"
                f"Status: Active"
            )
    
    def _move_between_rosters(self, player):
        """Move player between different rosters"""
        current_roster = "Unknown"
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            if player in self.parent.user_team.roster:
                current_roster = "NHL Roster"
            elif player in self.parent.user_team.ahl_roster:
                current_roster = "AHL Roster"
            elif player in self.parent.user_team.prospects:
                current_roster = "Prospects"
        
        messagebox.showinfo(
            "Roster Management",
            f"Roster Management - {player.full_name}\\n\\n"
            f"Current Roster: {current_roster}\\n\\n"
            f"Available Actions:\\n"
            f"• Move to NHL Roster\\n"
            f"• Move to AHL Roster\\n"
            f"• Move to Prospects\\n\\n"
            f"This functionality will be implemented in roster management."
        )
    
    def _propose_trade(self, player):
        """Open trade proposal window with player pre-selected"""
        try:
            # Try to open existing trade window
            if hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'open_trade_window'):
                self.parent.parent.open_trade_window()
                messagebox.showinfo("Trade Window", f"Trade window opened. Add {player.full_name} to your trade proposal.")
            elif hasattr(self.parent, 'open_trade_window'):
                self.parent.open_trade_window()
                messagebox.showinfo("Trade Window", f"Trade window opened. Add {player.full_name} to your trade proposal.")
            else:
                # Create quick trade proposal dialog
                self._create_trade_proposal_dialog(player)
        except Exception:
            # Fallback to trade proposal dialog
            self._create_trade_proposal_dialog(player)
    
    def _create_trade_proposal_dialog(self, player):
        """Create a trade proposal dialog"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Trade Proposal - {player.full_name}")
        dialog.geometry("500x400")
        dialog.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        
        # Header
        header = tk.Label(dialog, text=f"Propose Trade for {player.full_name}", 
                         font=('Segoe UI', 14, 'bold'))
        header.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                        bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header.pack(pady=20)
        
        # Player info
        info_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        info_frame.pack(fill='x', padx=20, pady=10)
        
        info_text = f"Position: {player.primary_position.value}\\n"
        info_text += f"Overall: {player.overall_rating()}\\n"
        info_text += f"Age: {player.age}\\n"
        
        if hasattr(player, 'contract') and player.contract:
            salary = getattr(player.contract, 'salary', 750000)
            info_text += f"Salary: ${salary:,}"
        
        info_label = tk.Label(info_frame, text=info_text, justify='left',
                             fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                             bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        info_label.pack(anchor='w')
        
        # Team selection
        team_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        team_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(team_frame, text="Select Team to Trade With:", 
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        # Get available teams
        available_teams = []
        if (hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'league') and
            hasattr(self.parent.parent.league, 'teams')):
            user_team = getattr(self.parent.parent, 'user_team', None)
            available_teams = [team for team in self.parent.parent.league.teams 
                             if team != user_team][:10]  # Limit to first 10 for demo
        
        if not available_teams:
            # Create some example teams
            available_teams = ["Montreal Canadiens", "Toronto Maple Leafs", "Boston Bruins",
                             "New York Rangers", "Chicago Blackhawks"]
        
        from tkinter import ttk
        team_var = tk.StringVar()
        team_combo = ttk.Combobox(team_frame, textvariable=team_var,
                                values=[team.team_name if hasattr(team, 'team_name') else str(team) 
                                       for team in available_teams],
                                state='readonly')
        team_combo.pack(fill='x', pady=5)
        
        # Trade message
        message_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        message_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        tk.Label(message_frame, text="Trade Proposal Message:", 
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E')).pack(anchor='w')
        
        message_text = tk.Text(message_frame, height=4, width=50)
        message_text.insert('1.0', f"We are interested in acquiring {player.full_name}. What would you want in return?")
        message_text.pack(fill='both', expand=True, pady=5)
        
        # Buttons
        button_frame = tk.Frame(dialog, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        button_frame.pack(fill='x', padx=20, pady=10)
        
        def send_proposal():
            if team_var.get():
                messagebox.showinfo("Trade Proposal Sent", 
                                  f"Trade proposal for {player.full_name} sent to {team_var.get()}!\\n\\n"
                                  f"You will receive a response within 24-48 hours.")
                dialog.destroy()
        
        ttk.Button(button_frame, text="Send Proposal", command=send_proposal).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def _create_enhanced_comparison_window(self, player):
        """Create enhanced comparison window with better styling and functionality"""
        compare_window = tk.Toplevel(self.parent)
        compare_window.title(f"Player Comparison - {player.full_name}")
        compare_window.geometry("900x700")
        compare_window.configure(bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        
        # Header frame
        header_frame = tk.Frame(compare_window, bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header_frame.pack(fill='x', pady=10)
        
        header_label = tk.Label(header_frame, 
                               text=f"Player Comparison Tool",
                               font=('Segoe UI', 18, 'bold'))
        header_label.configure(fg=getattr(self.parent, 'HEADER_COLOR', 'white'), 
                              bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'))
        header_label.pack()
        
        # Main content frame with notebook
        from tkinter import ttk
        notebook = ttk.Notebook(compare_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Quick Compare tab
        quick_tab = ttk.Frame(notebook)
        notebook.add(quick_tab, text="Quick Compare")
        self._create_quick_compare_tab(quick_tab, player)
        
        # Detailed Analysis tab
        detailed_tab = ttk.Frame(notebook)
        notebook.add(detailed_tab, text="Detailed Analysis")
        self._create_detailed_analysis_tab(detailed_tab, player)
        
        # Position Comparison tab
        position_tab = ttk.Frame(notebook)
        notebook.add(position_tab, text="Position Peers")
        self._create_position_comparison_tab(position_tab, player)
    
    def _create_quick_compare_tab(self, parent, player1):
        """Create quick comparison tab"""
        # Player selection frame
        selection_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        selection_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(selection_frame, text="Compare with:", 
                font=('Segoe UI', 12, 'bold'),
                fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A')).pack(anchor='w', pady=5)
        
        # Get all available players
        all_players = self._get_all_players()
        
        from tkinter import ttk
        compare_var = tk.StringVar()
        compare_combo = ttk.Combobox(selection_frame, textvariable=compare_var,
                                   values=[p.full_name for p in all_players if p != player1],
                                   state='readonly', width=40, font=('Segoe UI', 10))
        compare_combo.pack(anchor='w', pady=5, fill='x')
        
        # Results frame
        results_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        def do_quick_comparison():
            selected_name = compare_var.get()
            if selected_name:
                compare_player = next((p for p in all_players if p.full_name == selected_name), None)
                if compare_player:
                    self._show_enhanced_comparison_results(player1, compare_player, results_frame)
        
        compare_btn = ttk.Button(selection_frame, text="Compare Players", command=do_quick_comparison)
        compare_btn.pack(pady=10)
    
    def _create_detailed_analysis_tab(self, parent, player):
        """Create detailed analysis tab"""
        content_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Player analysis
        analysis_text = self._generate_detailed_analysis(player)
        
        from tkinter import scrolledtext
        analysis_display = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, width=80, height=25,
                                                   font=('Consolas', 10),
                                                   bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'),
                                                   fg=getattr(self.parent, 'TEXT_COLOR', 'white'),
                                                   insertbackground=getattr(self.parent, 'TEXT_COLOR', 'white'))
        analysis_display.pack(fill='both', expand=True)
        analysis_display.insert('1.0', analysis_text)
        analysis_display.config(state='disabled')
    
    def _create_position_comparison_tab(self, parent, player):
        """Create position peers comparison tab"""
        content_frame = tk.Frame(parent, bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A'))
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(content_frame, text=f"Position Peers - {player.primary_position.value}",
                font=('Segoe UI', 14, 'bold'),
                fg=getattr(self.parent, 'HEADER_COLOR', 'white'),
                bg=getattr(self.parent, 'CONTENT_BG', '#2A2A2A')).pack(pady=10)
        
        # Get players of same position
        same_position_players = [p for p in self._get_all_players() 
                               if p.primary_position == player.primary_position and p != player]
        
        # Sort by overall rating
        same_position_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Display top 10 peers
        peers_text = f"Top {min(10, len(same_position_players))} {player.primary_position.value} players:\\n\\n"
        
        for i, peer in enumerate(same_position_players[:10], 1):
            peers_text += f"{i:2}. {peer.full_name:<25} OVR: {peer.overall_rating():2} Age: {peer.age:2}\\n"
        
        peers_text += f"\\n{player.full_name} ranks approximately #{same_position_players.index(player) + 1 if player in same_position_players else 'Unknown'} among {player.primary_position.value} players."
        
        from tkinter import scrolledtext
        peers_display = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, width=80, height=20,
                                                font=('Consolas', 10),
                                                bg=getattr(self.parent, 'BG_COLOR', '#1E1E1E'),
                                                fg=getattr(self.parent, 'TEXT_COLOR', 'white'))
        peers_display.pack(fill='both', expand=True, pady=10)
        peers_display.insert('1.0', peers_text)
        peers_display.config(state='disabled')
    
    def _get_all_players(self):
        """Get all available players from various sources"""
        all_players = []
        
        # Try to get players from parent's user team
        if hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'user_team'):
            team = self.parent.parent.user_team
            all_players.extend(getattr(team, 'roster', []))
            all_players.extend(getattr(team, 'ahl_roster', []))
            all_players.extend(getattr(team, 'prospects', []))
        elif hasattr(self.parent, 'user_team'):
            team = self.parent.user_team
            all_players.extend(getattr(team, 'roster', []))
            all_players.extend(getattr(team, 'ahl_roster', []))
            all_players.extend(getattr(team, 'prospects', []))
        
        # If still no players, create some sample data
        if not all_players:
            # This is a fallback - in real implementation, you'd access the league's player pool
            pass
            
        return all_players[:100]  # Limit to first 100 players for performance
    
    def _generate_detailed_analysis(self, player):
        """Generate detailed player analysis text"""
        analysis = f"DETAILED PLAYER ANALYSIS\\n"
        analysis += f"{'='*50}\\n\\n"
        
        analysis += f"Player: {player.full_name}\\n"
        analysis += f"Position: {player.primary_position.value}\\n"
        analysis += f"Age: {player.age}\\n"
        analysis += f"Overall Rating: {player.overall_rating()}\\n\\n"
        
        # Attributes analysis
        analysis += f"ATTRIBUTES BREAKDOWN\\n"
        analysis += f"{'-'*25}\\n"
        
        attributes = [
            ('Skating', getattr(player, 'skating', 'N/A')),
            ('Shooting', getattr(player, 'shooting', 'N/A')),
            ('Passing', getattr(player, 'passing', 'N/A')),
            ('Defense', getattr(player, 'defense', 'N/A')),
            ('Hockey IQ', getattr(player, 'hockey_iq', 'N/A')),
            ('Physical', getattr(player, 'physical', 'N/A')),
        ]
        
        for attr_name, value in attributes:
            if value != 'N/A':
                rating = "Elite" if value >= 18 else "Excellent" if value >= 16 else "Good" if value >= 14 else "Average" if value >= 12 else "Below Average"
                analysis += f"{attr_name:<15}: {value:2} ({rating})\\n"
        
        analysis += f"\\nSTRENGTHS & WEAKNESSES\\n"
        analysis += f"{'-'*25}\\n"
        
        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []
        
        for attr_name, value in attributes:
            if value != 'N/A':
                if value >= 16:
                    strengths.append(attr_name)
                elif value <= 10:
                    weaknesses.append(attr_name)
        
        if strengths:
            analysis += f"Strengths: {', '.join(strengths)}\\n"
        if weaknesses:
            analysis += f"Weaknesses: {', '.join(weaknesses)}\\n"
        
        analysis += f"\\nDEVELOPMENT RECOMMENDATION\\n"
        analysis += f"{'-'*25}\\n"
        
        if player.age <= 20:
            analysis += "High development potential due to young age.\\n"
        elif player.age <= 25:
            analysis += "Good development potential in prime years.\\n"
        else:
            analysis += "Limited development potential due to age.\\n"
        
        if weaknesses:
            analysis += f"Focus training on: {', '.join(weaknesses[:2])}\\n"
        
        return analysis

def add_player_context_menu(treeview, parent_window):
    """
    Helper function to add player context menu to any treeview widget
    
    Args:
        treeview: The treeview widget containing players
        parent_window: The parent window instance
    """
    context_menu_manager = PlayerContextMenu(parent_window)
    
    def on_right_click(event):
        # Identify which item was right-clicked
        item_id = treeview.identify_row(event.y)
        if not item_id:
            return
            
        # Select the item
        treeview.selection_set(item_id)
        
        # Get the player object from tree_maps
        player = None
        if hasattr(parent_window, 'parent') and hasattr(parent_window.parent, 'tree_maps'):
            player = parent_window.parent.tree_maps.get(treeview, {}).get(item_id)
        elif hasattr(parent_window, 'tree_maps'):
            player = parent_window.tree_maps.get(treeview, {}).get(item_id)
        
        if player:
            context_menu_manager.show_context_menu(event, player)
    
    treeview.bind('<Button-3>', on_right_click)
    return context_menu_manager