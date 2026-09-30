# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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
from tkinter import ttk
from popup_system import messagebox, InGamePopup
from player_context_menu import PlayerContextMenu
import customtkinter as ctk
from ctk_theme import BG, CARD
from dataclasses import dataclass, field
from typing import (List, Optional)
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


def _focus_card(view, width=600):
    """Focus-card layout: full-screen view with content in a centered card.

    Used for the small shortlist dialogs so they read as screen jumps
    rather than floating popups.
    """
    outer = ctk.CTkFrame(view, fg_color=BG)
    outer.pack(fill="both", expand=True)
    card = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=12, width=width)
    card.pack(expand=True, padx=24, pady=24)
    return card


class ShortlistView(ctk.CTkFrame):
    """Main shortlist management view (full-screen)."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ShortlistWindow wrapper
        self.configure(fg_color=BG)
        self.shortlist_manager = self.app.shortlist_manager

        # Set up styling
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        self.create_interface()
        self.populate_shortlist()

        # Non-modal: the shortlist is a workbench, not a verdict -- the
        # user can keep it open (or click out of it) while exploring.


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass


    def _ask_confirm(self, text, on_yes, on_no=None):
        """Show an in-view Yes/No panel (replaces messagebox.askyesno)."""
        old = getattr(self, "_confirm_panel", None)
        if old is not None:
            try: old.destroy()
            except Exception: pass
        import customtkinter as ctk
        panel = ctk.CTkFrame(self, fg_color="#2a2a3a", corner_radius=8)
        panel.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(panel, text=text, wraplength=520).pack(padx=12, pady=(10, 6))
        btns = ctk.CTkFrame(panel, fg_color="transparent")
        btns.pack(pady=(0, 10))
        def _yes():
            try: panel.destroy()
            except Exception: pass
            self._confirm_panel = None
            on_yes()
        def _no():
            try: panel.destroy()
            except Exception: pass
            self._confirm_panel = None
            if on_no: on_no()
        ctk.CTkButton(btns, text="Yes", command=_yes, width=90).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="No", command=_no, width=90).pack(side="left", padx=6)
        self._confirm_panel = panel

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def create_interface(self):
        """Create the shortlist interface"""


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

        self.shortlist_tree = self.app._create_treeview(tree_frame, columns, height=20)

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
                  command=self.close_view).pack(side="right")

    def populate_shortlist(self):
        """Populate the shortlist treeview"""
        # Clear existing items
        for item in self.shortlist_tree.get_children():
            self.shortlist_tree.delete(item)

        # Get all entries
        entries = self.shortlist_manager.get_all_entries()

        # Initialize tree maps if not exists
        if not hasattr(self.app, 'tree_maps'):
            self.app.tree_maps = {}
        if self.shortlist_tree not in self.app.tree_maps:
            self.app.tree_maps[self.shortlist_tree] = {}

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
            self.app.tree_maps[self.shortlist_tree][item] = entry

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
            self.app.tree_maps[self.shortlist_tree][item] = entry

    def add_shortlist_context_menu(self):
        """Add context menu to shortlist treeview (universal player menu + shortlist actions)."""
        def show_context_menu(event):
            item = self.shortlist_tree.identify_row(event.y)
            if not item:
                return
            self.shortlist_tree.selection_set(item)
            entry = self.app.tree_maps.get(self.shortlist_tree, {}).get(item)
            player = self.find_player_by_id(entry.player_id) if entry else None
            if player:
                PlayerContextMenu(self.app).show_context_menu(
                    event, player,
                    additional_options=[
                        ("Edit Notes", self.edit_notes),
                        ("Change Priority", self.change_priority),
                        ("Remove from Shortlist", self.remove_selected),
                    ])
            else:
                # Entry's player not on any roster: shortlist-only actions.
                context_menu = tk.Menu(self, tearoff=0)
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
        if item in self.app.tree_maps[self.shortlist_tree]:
            entry = self.app.tree_maps[self.shortlist_tree][item]
            # Find the actual player object
            player = self.find_player_by_id(entry.player_id)
            if player:
                if hasattr(self.app, "open_player_profile"):
                    self.app.open_player_profile(player)
                else:
                    from ui_components import PlayerProfileWindow
                    profile_window = PlayerProfileWindow(self.app, player)
            else:
                messagebox.showwarning("Player Not Found",
                                     f"Could not find player {entry.player_name} in current rosters.")

    def find_player_by_id(self, player_id):
        """Find player object by ID across all teams"""
        # Check user team
        for player in (self.app.user_team.roster +
                      self.app.user_team.ahl_roster +
                      self.app.user_team.prospects):
            if player.id == player_id:
                return player

        # Check other teams
        for team in self.app.teams.values():
            for player in (team.roster + team.ahl_roster + team.prospects):
                if player.id == player_id:
                    return player

        # Check free agents
        if hasattr(self.app, 'free_agents'):
            for player in self.app.free_agents:
                if player.id == player_id:
                    return player

        return None

    def _back_to_shortlist(self):
        """Return to the shortlist screen (fresh) after a dialog completes."""
        self.app.show_screen('shortlist', 'Player Shortlist',
                             ShortlistView, fresh=True)

    def show_add_player_dialog(self):
        """Show dialog to add a player to shortlist"""
        self.app.show_screen('shortlist_add_player', 'Add Player to Shortlist',
                             AddPlayerView,
                             shortlist_manager=self.shortlist_manager,
                             on_done=self._back_to_shortlist)

    def remove_selected(self):
        """Remove selected entry from shortlist"""
        selected = self.shortlist_tree.selection()
        if not selected:
            self._show_banner("Please select an entry to remove.", "warn")
            return

        item = selected[0]
        if item in self.app.tree_maps[self.shortlist_tree]:
            entry = self.app.tree_maps[self.shortlist_tree][item]

            self._ask_confirm(f"Remove {entry.player_name} from {entry.category}?",
                              lambda: (self.shortlist_manager.remove_player(entry.player_id, entry.category),
                                       self.filter_shortlist()))

    def edit_notes(self):
        """Edit notes for selected entry"""
        selected = self.shortlist_tree.selection()
        if not selected:
            self._show_banner("Please select an entry to edit.", "warn")
            return

        item = selected[0]
        if item in self.app.tree_maps[self.shortlist_tree]:
            entry = self.app.tree_maps[self.shortlist_tree][item]
            self.app.show_screen('shortlist_edit_notes', 'Edit Notes',
                                 EditNotesView, entry=entry,
                                 shortlist_manager=self.shortlist_manager,
                                 on_done=self._back_to_shortlist)

    def change_priority(self):
        """Change priority for selected entry"""
        selected = self.shortlist_tree.selection()
        if not selected:
            self._show_banner("Please select an entry to modify.", "warn")
            return

        item = selected[0]
        if item in self.app.tree_maps[self.shortlist_tree]:
            entry = self.app.tree_maps[self.shortlist_tree][item]
            self.app.show_screen('shortlist_change_priority', 'Change Priority',
                                 ChangePriorityView, entry=entry,
                                 shortlist_manager=self.shortlist_manager,
                                 on_done=self._back_to_shortlist)


class ShortlistWindow(InGamePopup):
    """Popup wrapper around ShortlistView (backward compatibility)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Player Shortlist")
        app = (getattr(parent, 'app', None)
               or getattr(parent, 'parent', None) or parent)
        self._view = ShortlistView(self, app=app)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)


class AddPlayerView(ctk.CTkFrame):
    """Dialog for adding a player to shortlist (focus-card view)."""

    def __init__(self, parent, app=None, shortlist_manager=None, on_done=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the AddPlayerDialog wrapper
        self.configure(fg_color=BG)
        self.shortlist_manager = shortlist_manager
        self._on_done = on_done

        self.create_interface()
        self.populate_players()


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _finish(self):
        """Dialog complete: run the on_done callback, else close the view."""
        cb = self._on_done
        if callable(cb):
            try:
                cb()
            except Exception:
                pass
        else:
            self.close_view()

    def create_interface(self):
        """Create the add player interface"""
        card = _focus_card(self, width=560)

        body = ttk.Frame(card, padding=18)
        body.pack(fill="both", expand=True)

        # Player selection
        player_frame = ttk.LabelFrame(body, text="Select Player", padding=10)
        player_frame.pack(fill="x", pady=5)

        self.player_var = tk.StringVar()
        self.player_combo = ttk.Combobox(player_frame, textvariable=self.player_var,
                                        state="readonly", width=40)
        self.player_combo.pack(fill="x")

        # Category selection
        category_frame = ttk.LabelFrame(body, text="Category", padding=10)
        category_frame.pack(fill="x", pady=5)

        self.category_var = tk.StringVar(value="Trade Targets")
        category_combo = ttk.Combobox(category_frame, textvariable=self.category_var,
                                    values=ShortlistManager.CATEGORIES,
                                    state="readonly")
        category_combo.pack(fill="x")

        # Priority selection
        priority_frame = ttk.LabelFrame(body, text="Priority", padding=10)
        priority_frame.pack(fill="x", pady=5)

        self.priority_var = tk.StringVar(value="Medium Priority")
        priority_combo = ttk.Combobox(priority_frame, textvariable=self.priority_var,
                                    values=list(ShortlistManager.PRIORITY_LEVELS.values()),
                                    state="readonly")
        priority_combo.pack(fill="x")

        # Notes
        notes_frame = ttk.LabelFrame(body, text="Notes", padding=10)
        notes_frame.pack(fill="both", expand=True, pady=5)

        self.notes_text = tk.Text(notes_frame, height=4, wrap="word",
                                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR)
        self.notes_text.pack(fill="both", expand=True)

        # Buttons
        button_frame = ttk.Frame(body)
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(button_frame, text="Add to Shortlist",
                  command=self.add_player).pack(side="left")
        ttk.Button(button_frame, text="Cancel",
                  command=self._finish).pack(side="right")

    def populate_players(self):
        """Populate player dropdown with available players"""
        players = []

        # Add players from all teams (excluding user team for trade targets)
        for team_name, team in self.app.teams.items():
            if team_name != self.app.user_team.name:
                for player in team.roster + team.ahl_roster + team.prospects:
                    players.append(f"{player.full_name} ({team_name})")

        # Add free agents
        if hasattr(self.app, 'free_agents'):
            for player in self.app.free_agents:
                players.append(f"{player.full_name} (Free Agent)")

        # Add user team players for development tracking
        for player in (self.app.user_team.roster +
                      self.app.user_team.ahl_roster +
                      self.app.user_team.prospects):
            players.append(f"{player.full_name} ({self.app.user_team.name})")

        self.player_combo['values'] = sorted(players)

    def add_player(self):
        """Add selected player to shortlist"""
        player_selection = self.player_var.get()
        if not player_selection:
            self._show_banner("Please select a player.", "warn")
            return

        category = self.category_var.get()
        if not category:
            self._show_banner("Please select a category.", "warn")
            return

        priority_text = self.priority_var.get()
        priority = next((k for k, v in ShortlistManager.PRIORITY_LEVELS.items()
                        if v == priority_text), 2)

        notes = self.notes_text.get("1.0", "end-1c")

        # Extract player name and find player object
        player_name = player_selection.split(" (")[0]
        player = self.find_player_by_name(player_name)

        if not player:
            self._show_banner("Could not find selected player.", "error")
            return

        # Add to shortlist
        if self.shortlist_manager.add_player(player.id, player.full_name,
                                           category, notes, priority):
            self._show_banner(f"{player.full_name} added to {category}!", "ok")
            self._finish()
        else:
            messagebox.showwarning("Duplicate",
                                 f"{player.full_name} is already in {category}.")

    def find_player_by_name(self, player_name):
        """Find player object by name"""
        # Check all teams
        for team in self.app.teams.values():
            for player in team.roster + team.ahl_roster + team.prospects:
                if player.full_name == player_name:
                    return player

        # Check free agents
        if hasattr(self.app, 'free_agents'):
            for player in self.app.free_agents:
                if player.full_name == player_name:
                    return player

        return None


class AddPlayerDialog(InGamePopup):
    """Popup wrapper around AddPlayerView (backward compatibility)."""

    def __init__(self, parent_window, shortlist_manager):
        super().__init__(parent_window, modal=True)
        self.title("Add Player to Shortlist")
        app = (getattr(parent_window, 'app', None)
               or getattr(parent_window, 'parent', None) or parent_window)
        self._view = AddPlayerView(self, app=app,
                                  shortlist_manager=shortlist_manager)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)


class EditNotesView(ctk.CTkFrame):
    """Dialog for editing shortlist entry notes (focus-card view)."""

    def __init__(self, parent, app=None, entry=None,
                 shortlist_manager=None, on_done=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the EditNotesDialog wrapper
        self.configure(fg_color=BG)
        self.entry = entry
        self.shortlist_manager = shortlist_manager
        self._on_done = on_done

        self.create_interface()


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _finish(self):
        """Dialog complete: run the on_done callback, else close the view."""
        cb = self._on_done
        if callable(cb):
            try:
                cb()
            except Exception:
                pass
        else:
            self.close_view()

    def create_interface(self):
        """Create the notes editing interface"""
        card = _focus_card(self, width=560)

        body = ttk.Frame(card, padding=18)
        body.pack(fill="both", expand=True)

        # Title
        title_label = ttk.Label(body, text=self.entry.player_name,
                               font=(self.app.FONT_FAMILY, 14, 'bold'),
                               background=self.app.BG_COLOR,
                               foreground=self.app.HEADER_COLOR)
        title_label.pack(pady=10)

        # Notes text area
        notes_frame = ttk.LabelFrame(body, text="Notes", padding=10)
        notes_frame.pack(fill="both", expand=True, pady=10)

        self.notes_text = tk.Text(notes_frame, wrap="word", height=8,
                                 bg=self.app.CONTENT_BG,
                                 fg=self.app.TEXT_COLOR)
        self.notes_text.pack(fill="both", expand=True)

        # Load existing notes
        self.notes_text.insert("1.0", self.entry.notes)

        # Buttons
        button_frame = ttk.Frame(body)
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(button_frame, text="Save",
                  command=self.save_notes).pack(side="left")
        ttk.Button(button_frame, text="Cancel",
                  command=self._finish).pack(side="right")

    def save_notes(self):
        """Save the edited notes"""
        new_notes = self.notes_text.get("1.0", "end-1c")
        self.shortlist_manager.update_notes(self.entry.player_id,
                                          self.entry.category, new_notes)
        self._show_banner("Notes updated successfully!", "ok")
        self._finish()


class EditNotesDialog(InGamePopup):
    """Popup wrapper around EditNotesView (backward compatibility)."""

    def __init__(self, parent_window, entry, shortlist_manager):
        super().__init__(parent_window, modal=True)
        self.title("Edit Notes")
        app = (getattr(parent_window, 'app', None)
               or getattr(parent_window, 'parent', None) or parent_window)
        self._view = EditNotesView(self, app=app, entry=entry,
                                   shortlist_manager=shortlist_manager)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)


class ChangePriorityView(ctk.CTkFrame):
    """Dialog for changing shortlist entry priority (focus-card view)."""

    def __init__(self, parent, app=None, entry=None,
                 shortlist_manager=None, on_done=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ChangePriorityDialog wrapper
        self.configure(fg_color=BG)
        self.entry = entry
        self.shortlist_manager = shortlist_manager
        self._on_done = on_done

        self.create_interface()


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _finish(self):
        """Dialog complete: run the on_done callback, else close the view."""
        cb = self._on_done
        if callable(cb):
            try:
                cb()
            except Exception:
                pass
        else:
            self.close_view()

    def create_interface(self):
        """Create the priority change interface"""
        card = _focus_card(self, width=480)

        body = ttk.Frame(card, padding=18)
        body.pack(fill="both", expand=True)

        # Title
        title_label = ttk.Label(body, text=self.entry.player_name,
                               font=(self.app.FONT_FAMILY, 14, 'bold'),
                               background=self.app.BG_COLOR,
                               foreground=self.app.HEADER_COLOR)
        title_label.pack(pady=10)

        # Priority selection
        priority_frame = ttk.LabelFrame(body, text="New Priority", padding=10)
        priority_frame.pack(fill="x", pady=10)

        current_priority = ShortlistManager.PRIORITY_LEVELS[self.entry.priority]
        self.priority_var = tk.StringVar(value=current_priority)
        priority_combo = ttk.Combobox(priority_frame, textvariable=self.priority_var,
                                    values=list(ShortlistManager.PRIORITY_LEVELS.values()),
                                    state="readonly")
        priority_combo.pack(fill="x")

        # Buttons
        button_frame = ttk.Frame(body)
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(button_frame, text="Update",
                  command=self.update_priority).pack(side="left")
        ttk.Button(button_frame, text="Cancel",
                  command=self._finish).pack(side="right")

    def update_priority(self):
        """Update the entry priority"""
        priority_text = self.priority_var.get()
        priority = next((k for k, v in ShortlistManager.PRIORITY_LEVELS.items()
                        if v == priority_text), self.entry.priority)

        self.shortlist_manager.update_priority(self.entry.player_id,
                                             self.entry.category, priority)
        self._show_banner("Priority updated successfully!", "ok")
        self._finish()


class ChangePriorityDialog(InGamePopup):
    """Popup wrapper around ChangePriorityView (backward compatibility)."""

    def __init__(self, parent_window, entry, shortlist_manager):
        super().__init__(parent_window, modal=True)
        self.title("Change Priority")
        app = (getattr(parent_window, 'app', None)
               or getattr(parent_window, 'parent', None) or parent_window)
        self._view = ChangePriorityView(self, app=app, entry=entry,
                                        shortlist_manager=shortlist_manager)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)
