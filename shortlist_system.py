"""
Shortlist System for Hockey Manager

A comprehensive player shortlist system for tracking:
- Trade targets
- Prospects to watch
- Free agent targets  
- Draft prospects
- Players of interest with custom categories and notes
"""

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json
import os

@dataclass
class ShortlistEntry:
    """Represents a player entry in the shortlist"""
    player_id: str
    player_name: str
    category: str
    notes: str = ""
    date_added: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1=High, 2=Medium, 3=Low
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'player_id': self.player_id,
            'player_name': self.player_name,
            'category': self.category,
            'notes': self.notes,
            'date_added': self.date_added.isoformat(),
            'priority': self.priority
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary"""
        entry = cls(
            player_id=data['player_id'],
            player_name=data['player_name'],
            category=data['category'],
            notes=data.get('notes', ''),
            priority=data.get('priority', 1)
        )
        entry.date_added = datetime.fromisoformat(data['date_added'])
        return entry

class ShortlistManager:
    """Manages the shortlist system"""
    
    CATEGORIES = [
        "Trade Targets",
        "Free Agent Targets", 
        "Draft Prospects",
        "Future Prospects",
        "Development Watch",
        "Injury Replacements",
        "Custom"
    ]
    
    PRIORITY_LEVELS = {
        1: "High Priority",
        2: "Medium Priority", 
        3: "Low Priority"
    }
    
    def __init__(self):
        self.entries: List[ShortlistEntry] = []
        self.save_file = "saves/shortlist.json"
        self.load_shortlist()
    
    def add_player(self, player_id: str, player_name: str, category: str, 
                   notes: str = "", priority: int = 2) -> bool:
        """Add a player to the shortlist"""
        # Check if player already exists in this category
        existing = self.get_entry(player_id, category)
        if existing:
            return False
            
        entry = ShortlistEntry(
            player_id=player_id,
            player_name=player_name,
            category=category,
            notes=notes,
            priority=priority
        )
        self.entries.append(entry)
        self.save_shortlist()
        return True
    
    def remove_player(self, player_id: str, category: str = None) -> bool:
        """Remove a player from shortlist (all entries or specific category)"""
        initial_count = len(self.entries)
        
        if category:
            self.entries = [e for e in self.entries 
                          if not (e.player_id == player_id and e.category == category)]
        else:
            self.entries = [e for e in self.entries if e.player_id != player_id]
            
        if len(self.entries) < initial_count:
            self.save_shortlist()
            return True
        return False
    
    def get_entry(self, player_id: str, category: str) -> Optional[ShortlistEntry]:
        """Get a specific entry"""
        for entry in self.entries:
            if entry.player_id == player_id and entry.category == category:
                return entry
        return None
    
    def get_entries_by_category(self, category: str) -> List[ShortlistEntry]:
        """Get all entries in a category"""
        return [e for e in self.entries if e.category == category]
    
    def get_entries_by_priority(self, priority: int) -> List[ShortlistEntry]:
        """Get all entries with specific priority"""
        return [e for e in self.entries if e.priority == priority]
    
    def update_notes(self, player_id: str, category: str, notes: str):
        """Update notes for an entry"""
        entry = self.get_entry(player_id, category)
        if entry:
            entry.notes = notes
            self.save_shortlist()
    
    def update_priority(self, player_id: str, category: str, priority: int):
        """Update priority for an entry"""
        entry = self.get_entry(player_id, category)
        if entry:
            entry.priority = priority
            self.save_shortlist()
    
    def get_all_entries(self) -> List[ShortlistEntry]:
        """Get all entries sorted by date added (newest first)"""
        return sorted(self.entries, key=lambda x: x.date_added, reverse=True)
    
    def save_shortlist(self):
        """Save shortlist to file"""
        try:
            os.makedirs(os.path.dirname(self.save_file), exist_ok=True)
            data = [entry.to_dict() for entry in self.entries]
            with open(self.save_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving shortlist: {e}")
    
    def load_shortlist(self):
        """Load shortlist from file"""
        try:
            if os.path.exists(self.save_file):
                with open(self.save_file, 'r') as f:
                    data = json.load(f)
                self.entries = [ShortlistEntry.from_dict(entry) for entry in data]
        except Exception as e:
            print(f"Error loading shortlist: {e}")
            self.entries = []

class ShortlistWindow(tk.Toplevel):
    """Main shortlist management window"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.shortlist_manager = parent.shortlist_manager
        
        self.title("Player Shortlist")
        self.geometry("900x700")
        self.configure(bg=parent.BG_COLOR)
        
        # Set up styling
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        
        self.create_interface()
        self.populate_shortlist()
        
        # Make window non-modal
        self.transient(parent)
        self.grab_set()
    
    def create_interface(self):
        """Create the shortlist interface"""
        
        # Title bar
        title_bar = ttk.Frame(self, padding=(20, 10))
        title_bar.pack(fill="x")
        ttk.Label(title_bar, text="Player Shortlist", 
                 font=(self.parent.FONT_FAMILY, 16, 'bold'),
                 background=self.parent.BG_COLOR, 
                 foreground=self.parent.HEADER_COLOR).pack()
        
        # Main content frame
        content_frame = ttk.Frame(self, padding=10)
        content_frame.pack(fill="both", expand=True)
        
        # Category filter frame
        filter_frame = ttk.LabelFrame(content_frame, text="Filter", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        # Category filter
        ttk.Label(filter_frame, text="Category:").pack(side="left")
        self.category_var = tk.StringVar(value="All Categories")
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var,
                                    values=["All Categories"] + ShortlistManager.CATEGORIES,
                                    state="readonly", width=20)
        category_combo.pack(side="left", padx=(5, 15))
        category_combo.bind('<<ComboboxSelected>>', self.filter_shortlist)
        
        # Priority filter
        ttk.Label(filter_frame, text="Priority:").pack(side="left")
        self.priority_var = tk.StringVar(value="All Priorities")
        priority_combo = ttk.Combobox(filter_frame, textvariable=self.priority_var,
                                    values=["All Priorities"] + list(ShortlistManager.PRIORITY_LEVELS.values()),
                                    state="readonly", width=15)
        priority_combo.pack(side="left", padx=5)
        priority_combo.bind('<<ComboboxSelected>>', self.filter_shortlist)
        
        # Search frame
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(side="right")
        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side="left", padx=5)
        search_entry.bind('<KeyRelease>', self.filter_shortlist)
        
        # Shortlist treeview
        tree_frame = ttk.Frame(content_frame)
        tree_frame.pack(fill="both", expand=True)
        
        # Create treeview with columns
        columns = {
            'player': ('Player', 200),
            'category': ('Category', 150),
            'priority': ('Priority', 100),
            'notes': ('Notes', 250),
            'date_added': ('Added', 100)
        }
        
        self.shortlist_tree = self.parent._create_treeview(tree_frame, columns, height=20)
        
        # Add context menu to treeview
        self.add_shortlist_context_menu()
        
        # Action buttons frame
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(button_frame, text="Add Player", 
                  command=self.show_add_player_dialog).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Remove Selected", 
                  command=self.remove_selected).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Edit Notes", 
                  command=self.edit_notes).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Change Priority", 
                  command=self.change_priority).pack(side="left", padx=(0, 10))
        
        # Close button on right
        ttk.Button(button_frame, text="Close", 
                  command=self.destroy).pack(side="right")
    
    def populate_shortlist(self):
        """Populate the shortlist treeview"""
        # Clear existing items
        for item in self.shortlist_tree.get_children():
            self.shortlist_tree.delete(item)
        
        # Get all entries
        entries = self.shortlist_manager.get_all_entries()
        
        # Initialize tree maps if not exists
        if not hasattr(self.parent, 'tree_maps'):
            self.parent.tree_maps = {}
        if self.shortlist_tree not in self.parent.tree_maps:
            self.parent.tree_maps[self.shortlist_tree] = {}
        
        # Populate tree
        for entry in entries:
            priority_text = ShortlistManager.PRIORITY_LEVELS[entry.priority]
            date_text = entry.date_added.strftime("%m/%d/%y")
            
            item = self.shortlist_tree.insert("", "end", values=(
                entry.player_name,
                entry.category,
                priority_text,
                entry.notes[:50] + ("..." if len(entry.notes) > 50 else ""),
                date_text
            ))
            
            # Store entry in tree maps
            self.parent.tree_maps[self.shortlist_tree][item] = entry
    
    def filter_shortlist(self, event=None):
        """Filter shortlist based on current filter settings"""
        # Clear existing items
        for item in self.shortlist_tree.get_children():
            self.shortlist_tree.delete(item)
        
        # Get filter values
        category_filter = self.category_var.get()
        priority_filter = self.priority_var.get()
        search_filter = self.search_var.get().lower()
        
        # Get all entries and apply filters
        entries = self.shortlist_manager.get_all_entries()
        
        filtered_entries = []
        for entry in entries:
            # Category filter
            if category_filter != "All Categories" and entry.category != category_filter:
                continue
            
            # Priority filter  
            if priority_filter != "All Priorities":
                if ShortlistManager.PRIORITY_LEVELS[entry.priority] != priority_filter:
                    continue
            
            # Search filter
            if search_filter:
                if (search_filter not in entry.player_name.lower() and 
                    search_filter not in entry.notes.lower()):
                    continue
            
            filtered_entries.append(entry)
        
        # Populate filtered results
        for entry in filtered_entries:
            priority_text = ShortlistManager.PRIORITY_LEVELS[entry.priority]
            date_text = entry.date_added.strftime("%m/%d/%y")
            
            item = self.shortlist_tree.insert("", "end", values=(
                entry.player_name,
                entry.category,
                priority_text,
                entry.notes[:50] + ("..." if len(entry.notes) > 50 else ""),
                date_text
            ))
            
            # Store entry in tree maps
            self.parent.tree_maps[self.shortlist_tree][item] = entry
    
    def add_shortlist_context_menu(self):
        """Add context menu to shortlist treeview"""
        def show_context_menu(event):
            item = self.shortlist_tree.identify_row(event.y)
            if item:
                self.shortlist_tree.selection_set(item)
                context_menu = tk.Menu(self, tearoff=0)
                
                context_menu.add_command(label="View Player Profile", 
                                       command=lambda: self.view_player_profile(item))
                context_menu.add_separator()
                context_menu.add_command(label="Edit Notes", 
                                       command=self.edit_notes)
                context_menu.add_command(label="Change Priority", 
                                       command=self.change_priority)
                context_menu.add_separator()
                context_menu.add_command(label="Remove from Shortlist", 
                                       command=self.remove_selected)
                
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()
        
        self.shortlist_tree.bind("<Button-3>", show_context_menu)
    
    def view_player_profile(self, item):
        """Open player profile for selected player"""
        if item in self.parent.tree_maps[self.shortlist_tree]:
            entry = self.parent.tree_maps[self.shortlist_tree][item]
            # Find the actual player object
            player = self.find_player_by_id(entry.player_id)
            if player:
                from ui_components import PlayerProfileWindow
                profile_window = PlayerProfileWindow(self.parent, player)
            else:
                messagebox.showwarning("Player Not Found", 
                                     f"Could not find player {entry.player_name} in current rosters.")
    
    def find_player_by_id(self, player_id):
        """Find player object by ID across all teams"""
        # Check user team
        for player in (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects):
            if player.id == player_id:
                return player
        
        # Check other teams
        for team in self.parent.teams.values():
            for player in (team.roster + team.ahl_roster + team.prospects):
                if player.id == player_id:
                    return player
        
        # Check free agents
        if hasattr(self.parent, 'free_agents'):
            for player in self.parent.free_agents:
                if player.id == player_id:
                    return player
        
        return None
    
    def show_add_player_dialog(self):
        """Show dialog to add a player to shortlist"""
        AddPlayerDialog(self, self.shortlist_manager)
    
    def remove_selected(self):
        """Remove selected entry from shortlist"""
        selected = self.shortlist_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an entry to remove.")
            return
        
        item = selected[0]
        if item in self.parent.tree_maps[self.shortlist_tree]:
            entry = self.parent.tree_maps[self.shortlist_tree][item]
            
            if messagebox.askyesno("Confirm Removal", 
                                 f"Remove {entry.player_name} from {entry.category}?"):
                self.shortlist_manager.remove_player(entry.player_id, entry.category)
                self.filter_shortlist()  # Refresh display
    
    def edit_notes(self):
        """Edit notes for selected entry"""
        selected = self.shortlist_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an entry to edit.")
            return
        
        item = selected[0]
        if item in self.parent.tree_maps[self.shortlist_tree]:
            entry = self.parent.tree_maps[self.shortlist_tree][item]
            EditNotesDialog(self, entry, self.shortlist_manager)
    
    def change_priority(self):
        """Change priority for selected entry"""
        selected = self.shortlist_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an entry to modify.")
            return
        
        item = selected[0]
        if item in self.parent.tree_maps[self.shortlist_tree]:
            entry = self.parent.tree_maps[self.shortlist_tree][item]
            ChangePriorityDialog(self, entry, self.shortlist_manager)

class AddPlayerDialog(tk.Toplevel):
    """Dialog for adding a player to shortlist"""
    
    def __init__(self, parent_window, shortlist_manager):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.parent = parent_window.parent
        self.shortlist_manager = shortlist_manager
        
        self.title("Add Player to Shortlist")
        self.geometry("400x350")
        self.configure(bg=self.parent.BG_COLOR)
        
        self.create_interface()
        self.populate_players()
        
        # Make modal
        self.transient(parent_window)
        self.grab_set()
        
    def create_interface(self):
        """Create the add player interface"""
        
        # Title
        title_label = ttk.Label(self, text="Add Player to Shortlist", 
                               font=(self.parent.FONT_FAMILY, 14, 'bold'),
                               background=self.parent.BG_COLOR,
                               foreground=self.parent.HEADER_COLOR)
        title_label.pack(pady=10)
        
        # Player selection
        player_frame = ttk.LabelFrame(self, text="Select Player", padding=10)
        player_frame.pack(fill="x", padx=20, pady=5)
        
        self.player_var = tk.StringVar()
        self.player_combo = ttk.Combobox(player_frame, textvariable=self.player_var,
                                        state="readonly", width=40)
        self.player_combo.pack(fill="x")
        
        # Category selection
        category_frame = ttk.LabelFrame(self, text="Category", padding=10)
        category_frame.pack(fill="x", padx=20, pady=5)
        
        self.category_var = tk.StringVar(value="Trade Targets")
        category_combo = ttk.Combobox(category_frame, textvariable=self.category_var,
                                    values=ShortlistManager.CATEGORIES,
                                    state="readonly")
        category_combo.pack(fill="x")
        
        # Priority selection
        priority_frame = ttk.LabelFrame(self, text="Priority", padding=10)
        priority_frame.pack(fill="x", padx=20, pady=5)
        
        self.priority_var = tk.StringVar(value="Medium Priority")
        priority_combo = ttk.Combobox(priority_frame, textvariable=self.priority_var,
                                    values=list(ShortlistManager.PRIORITY_LEVELS.values()),
                                    state="readonly")
        priority_combo.pack(fill="x")
        
        # Notes
        notes_frame = ttk.LabelFrame(self, text="Notes", padding=10)
        notes_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        self.notes_text = tk.Text(notes_frame, height=4, wrap="word",
                                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        self.notes_text.pack(fill="both", expand=True)
        
        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Button(button_frame, text="Add to Shortlist", 
                  command=self.add_player).pack(side="left")
        ttk.Button(button_frame, text="Cancel", 
                  command=self.destroy).pack(side="right")
    
    def populate_players(self):
        """Populate player dropdown with available players"""
        players = []
        
        # Add players from all teams (excluding user team for trade targets)
        for team_name, team in self.parent.teams.items():
            if team_name != self.parent.user_team.name:
                for player in team.roster + team.ahl_roster + team.prospects:
                    players.append(f"{player.full_name} ({team_name})")
        
        # Add free agents
        if hasattr(self.parent, 'free_agents'):
            for player in self.parent.free_agents:
                players.append(f"{player.full_name} (Free Agent)")
        
        # Add user team players for development tracking
        for player in (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects):
            players.append(f"{player.full_name} ({self.parent.user_team.name})")
        
        self.player_combo['values'] = sorted(players)
    
    def add_player(self):
        """Add selected player to shortlist"""
        player_selection = self.player_var.get()
        if not player_selection:
            messagebox.showwarning("No Selection", "Please select a player.")
            return
        
        category = self.category_var.get()
        if not category:
            messagebox.showwarning("No Category", "Please select a category.")
            return
        
        priority_text = self.priority_var.get()
        priority = next((k for k, v in ShortlistManager.PRIORITY_LEVELS.items() 
                        if v == priority_text), 2)
        
        notes = self.notes_text.get("1.0", "end-1c")
        
        # Extract player name and find player object
        player_name = player_selection.split(" (")[0]
        player = self.find_player_by_name(player_name)
        
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        
        # Add to shortlist
        if self.shortlist_manager.add_player(player.id, player.full_name, 
                                           category, notes, priority):
            messagebox.showinfo("Added", f"{player.full_name} added to {category}!")
            self.parent_window.filter_shortlist()  # Refresh parent window
            self.destroy()
        else:
            messagebox.showwarning("Duplicate", 
                                 f"{player.full_name} is already in {category}.")
    
    def find_player_by_name(self, player_name):
        """Find player object by name"""
        # Check all teams
        for team in self.parent.teams.values():
            for player in team.roster + team.ahl_roster + team.prospects:
                if player.full_name == player_name:
                    return player
        
        # Check free agents
        if hasattr(self.parent, 'free_agents'):
            for player in self.parent.free_agents:
                if player.full_name == player_name:
                    return player
        
        return None

class EditNotesDialog(tk.Toplevel):
    """Dialog for editing shortlist entry notes"""
    
    def __init__(self, parent_window, entry, shortlist_manager):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.entry = entry
        self.shortlist_manager = shortlist_manager
        
        self.title("Edit Notes")
        self.geometry("400x300")
        self.configure(bg=parent_window.parent.BG_COLOR)
        
        self.create_interface()
        
        # Make modal
        self.transient(parent_window)
        self.grab_set()
    
    def create_interface(self):
        """Create the notes editing interface"""
        
        # Title
        title_label = ttk.Label(self, text=f"Edit Notes - {self.entry.player_name}", 
                               font=(self.parent_window.parent.FONT_FAMILY, 14, 'bold'),
                               background=self.parent_window.parent.BG_COLOR,
                               foreground=self.parent_window.parent.HEADER_COLOR)
        title_label.pack(pady=10)
        
        # Notes text area
        notes_frame = ttk.LabelFrame(self, text="Notes", padding=10)
        notes_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.notes_text = tk.Text(notes_frame, wrap="word",
                                 bg=self.parent_window.parent.CONTENT_BG, 
                                 fg=self.parent_window.parent.TEXT_COLOR)
        self.notes_text.pack(fill="both", expand=True)
        
        # Load existing notes
        self.notes_text.insert("1.0", self.entry.notes)
        
        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Button(button_frame, text="Save", 
                  command=self.save_notes).pack(side="left")
        ttk.Button(button_frame, text="Cancel", 
                  command=self.destroy).pack(side="right")
    
    def save_notes(self):
        """Save the edited notes"""
        new_notes = self.notes_text.get("1.0", "end-1c")
        self.shortlist_manager.update_notes(self.entry.player_id, 
                                          self.entry.category, new_notes)
        self.parent_window.filter_shortlist()  # Refresh parent window
        messagebox.showinfo("Saved", "Notes updated successfully!")
        self.destroy()

class ChangePriorityDialog(tk.Toplevel):
    """Dialog for changing shortlist entry priority"""
    
    def __init__(self, parent_window, entry, shortlist_manager):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.entry = entry
        self.shortlist_manager = shortlist_manager
        
        self.title("Change Priority")
        self.geometry("300x200")
        self.configure(bg=parent_window.parent.BG_COLOR)
        
        self.create_interface()
        
        # Make modal
        self.transient(parent_window)
        self.grab_set()
    
    def create_interface(self):
        """Create the priority change interface"""
        
        # Title
        title_label = ttk.Label(self, text=f"Change Priority - {self.entry.player_name}", 
                               font=(self.parent_window.parent.FONT_FAMILY, 14, 'bold'),
                               background=self.parent_window.parent.BG_COLOR,
                               foreground=self.parent_window.parent.HEADER_COLOR)
        title_label.pack(pady=10)
        
        # Priority selection
        priority_frame = ttk.LabelFrame(self, text="New Priority", padding=10)
        priority_frame.pack(fill="x", padx=20, pady=10)
        
        current_priority = ShortlistManager.PRIORITY_LEVELS[self.entry.priority]
        self.priority_var = tk.StringVar(value=current_priority)
        priority_combo = ttk.Combobox(priority_frame, textvariable=self.priority_var,
                                    values=list(ShortlistManager.PRIORITY_LEVELS.values()),
                                    state="readonly")
        priority_combo.pack(fill="x")
        
        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Button(button_frame, text="Update", 
                  command=self.update_priority).pack(side="left")
        ttk.Button(button_frame, text="Cancel", 
                  command=self.destroy).pack(side="right")
    
    def update_priority(self):
        """Update the entry priority"""
        priority_text = self.priority_var.get()
        priority = next((k for k, v in ShortlistManager.PRIORITY_LEVELS.items() 
                        if v == priority_text), self.entry.priority)
        
        self.shortlist_manager.update_priority(self.entry.player_id, 
                                             self.entry.category, priority)
        self.parent_window.filter_shortlist()  # Refresh parent window
        messagebox.showinfo("Updated", "Priority updated successfully!")
        self.destroy()