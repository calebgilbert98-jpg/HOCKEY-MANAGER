"""
Standalone Player Browser for Fantasy Draft
Simple, reliable player display system that guarantees player visibility
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
from game_classes import Player, PlayerPosition, to_100_scale
from game_classes import debug_print
from scouting_profiles import displayed_overall

class PlayerBrowserWindow(tk.Toplevel):
    """Standalone player browser with guaranteed player display"""
    
    def __init__(self, parent, players: List[Player], title="Available Players"):
        super().__init__(parent)
        self.parent = parent
        self.players = players
        self.selected_player = None

        # Paging: a Treeview with ~12k rows costs one Tcl round-trip per
        # insert, so we render one page at a time (filters still scan all).
        self.page = 0
        self.page_size = 250
        self._filter_after_id = None

        # Precompute display rows ONCE: (player, values, rating). Filtering
        # and sorting then reuse these instead of recomputing overall_rating
        # (and the fog-of-war noise) on every keystroke.
        user_team = self._user_team()
        self._all_rows = []
        for p in players:
            try:
                rating = p.overall_rating()
                self._all_rows.append((p, (
                    p.full_name,
                    p.primary_position.value,
                    f"{displayed_overall(p, user_team):.0f}",
                    p.age,
                    getattr(p, 'former_team', 'Unknown'),
                ), rating))
            except Exception:
                continue
        self._rows = []              # filtered + sorted (player, values, rating)
        self.filtered_players = []   # players only, same order as _rows
        
        # Window setup
        self.title(title)
        self.geometry("1200x800")
        self.configure(background='#181818')
        
        # Initialize filter variables
        self.search_var = tk.StringVar()
        self.position_var = tk.StringVar(value="All")
        self.min_rating_var = tk.StringVar(value="0")
        
        # Setup UI
        self.setup_ui()
        
        # Initial filter + population (replaces direct populate_players)
        self._do_filter()
        
    def setup_ui(self):
        """Setup the simple player browser UI"""
        # Main frame
        main_frame = tk.Frame(self, bg='#181818')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = tk.Frame(main_frame, bg='#1F1F1F')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = tk.Label(header_frame, text="🏒 Available Players Browser", 
                              font=('Segoe UI', 16, 'bold'), 
                              fg='#FFFFFF', bg='#1F1F1F')
        title_label.pack(pady=10)
        
        self.count_label = tk.Label(header_frame, text="", 
                                   font=('Segoe UI', 10), 
                                   fg='#E0E0E0', bg='#1F1F1F')
        self.count_label.pack()
        
        # Filter frame
        filter_frame = tk.Frame(main_frame, bg='#1F1F1F')
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Search
        tk.Label(filter_frame, text="Search:", fg='#E0E0E0', bg='#1F1F1F').grid(row=0, column=0, padx=5, pady=5, sticky='w')
        search_entry = tk.Entry(filter_frame, textvariable=self.search_var, width=20, bg='#2A2A2A', fg='#FFFFFF')
        search_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.search_var.trace('w', self.on_filter_change)
        
        # Position filter
        tk.Label(filter_frame, text="Position:", fg='#E0E0E0', bg='#1F1F1F').grid(row=0, column=2, padx=5, pady=5, sticky='w')
        position_combo = ttk.Combobox(filter_frame, textvariable=self.position_var,
                                     values=["All", "C", "LW", "RW", "LD", "RD", "G"], 
                                     width=8, state="readonly")
        position_combo.grid(row=0, column=3, padx=5, pady=5, sticky='w')
        position_combo.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        # Rating filter
        tk.Label(filter_frame, text="Min Rating:", fg='#E0E0E0', bg='#1F1F1F').grid(row=0, column=4, padx=5, pady=5, sticky='w')
        rating_spinbox = tk.Spinbox(filter_frame, from_=0, to=99, textvariable=self.min_rating_var, 
                                   width=5, bg='#2A2A2A', fg='#FFFFFF')
        rating_spinbox.grid(row=0, column=5, padx=5, pady=5, sticky='w')
        self.min_rating_var.trace('w', self.on_filter_change)
        
        # Clear button
        clear_btn = tk.Button(filter_frame, text="Clear Filters", command=self.clear_filters,
                             bg='#D13438', fg='#FFFFFF', activebackground='#A1272A')
        clear_btn.grid(row=0, column=6, padx=10, pady=5)
        
        # Players frame with scrollbars
        players_frame = tk.Frame(main_frame, bg='#181818')
        players_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview with scrollbars
        tree_frame = tk.Frame(players_frame, bg='#181818')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview
        columns = ('Name', 'Position', 'Overall', 'Age', 'Former Team')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=25)
        
        # Configure columns
        self.tree.heading('Name', text='Player Name')
        self.tree.heading('Position', text='Pos')
        self.tree.heading('Overall', text='OVR')
        self.tree.heading('Age', text='Age')
        self.tree.heading('Former Team', text='Former Team')
        
        self.tree.column('Name', width=200)
        self.tree.column('Position', width=60)
        self.tree.column('Overall', width=60)
        self.tree.column('Age', width=50)
        self.tree.column('Former Team', width=150)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.tree.bind('<Button-1>', self.on_player_select)
        self.tree.bind('<Double-1>', self.on_player_draft)
        
        # Button frame
        button_frame = tk.Frame(main_frame, bg='#181818')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.draft_btn = tk.Button(button_frame, text="🎯 DRAFT SELECTED PLAYER", 
                                  command=self.draft_player, state='disabled',
                                  bg='#D13438', fg='#FFFFFF', activebackground='#A1272A',
                                  font=('Segoe UI', 12, 'bold'))
        self.draft_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.info_label = tk.Label(button_frame, text="Select a player to draft", 
                                  fg='#E0E0E0', bg='#181818')
        self.info_label.pack(side=tk.LEFT)

        # Paging controls (Treeview renders one page; filters scan all rows)
        page_frame = tk.Frame(button_frame, bg='#181818')
        page_frame.pack(side=tk.LEFT, padx=20)
        self.prev_btn = tk.Button(page_frame, text="◀ Prev", command=self._prev_page,
                                  bg='#2A2A2A', fg='#FFFFFF',
                                  activebackground='#3A3A3A')
        self.prev_btn.pack(side=tk.LEFT, padx=2)
        self.page_label = tk.Label(page_frame, text="Page 1 / 1",
                                   fg='#E0E0E0', bg='#181818')
        self.page_label.pack(side=tk.LEFT, padx=6)
        self.next_btn = tk.Button(page_frame, text="Next ▶", command=self._next_page,
                                  bg='#2A2A2A', fg='#FFFFFF',
                                  activebackground='#3A3A3A')
        self.next_btn.pack(side=tk.LEFT, padx=2)
        
        # Close button
        close_btn = tk.Button(button_frame, text="Close", command=self.destroy,
                             bg='#2A2A2A', fg='#FFFFFF', activebackground='#3A3A3A')
        close_btn.pack(side=tk.RIGHT)
        
    def populate_players(self):
        """Render the current page of the filtered/sorted rows.

        Only ~250 Treeview inserts per refresh instead of one per player
        (~12k Tcl round-trips before this change).
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        total = len(self._rows)
        pages = max(1, -(-total // self.page_size))
        self.page = min(max(0, self.page), pages - 1)
        start = self.page * self.page_size
        page_rows = self._rows[start:start + self.page_size]

        for j, (player, values, _rating) in enumerate(page_rows):
            try:
                item_id = self.tree.insert('', 'end', values=values)
                # Index into filtered_players (global, not page-local)
                self.tree.set(item_id, '#0', str(start + j))
            except Exception as e:
                debug_print(f"DEBUG: Error adding player {start + j}: {e}")
                continue

        # Paging UI
        shown = f"{start + 1}-{start + len(page_rows)}" if total else "0"
        self.count_label.configure(
            text=f"Showing {shown} of {total} players "
                 f"(page {self.page + 1}/{pages})")
        self.page_label.configure(text=f"Page {self.page + 1} / {pages}")
        self.prev_btn.configure(state='normal' if self.page > 0 else 'disabled')
        self.next_btn.configure(
            state='normal' if self.page < pages - 1 else 'disabled')

        debug_print(f"DEBUG: Rendered page {self.page + 1}/{pages} "
                    f"({len(page_rows)} rows of {total})")

    def _prev_page(self):
        if self.page > 0:
            self.page -= 1
            self.populate_players()

    def _next_page(self):
        if (self.page + 1) * self.page_size < len(self._rows):
            self.page += 1
            self.populate_players()

    def on_filter_change(self, *args):
        """Debounced: typing in search no longer re-renders per keystroke."""
        if self._filter_after_id is not None:
            self.after_cancel(self._filter_after_id)
        self._filter_after_id = self.after(200, self._do_filter)

    def _do_filter(self):
        """Apply filters over the precomputed rows, sort once, page 1."""
        self._filter_after_id = None
        try:
            search_text = self.search_var.get().lower()
            position_filter = self.position_var.get()
            try:
                min_rating = int(self.min_rating_var.get() or 0)
            except (ValueError, TypeError):
                min_rating = 0

            rows = []
            for player, values, rating in self._all_rows:
                if search_text and search_text not in values[0].lower():
                    continue
                if position_filter != "All" and values[1] != position_filter:
                    continue
                if to_100_scale(rating) < min_rating:
                    continue
                rows.append((player, values, rating))

            # Sort by rating (highest first) -- rating computed once above
            rows.sort(key=lambda r: r[2], reverse=True)
            self._rows = rows
            self.filtered_players = [p for p, _v, _r in rows]
            self.page = 0
            self.populate_players()
        except Exception as e:
            debug_print(f"DEBUG: Error in filter: {e}")
            
    def clear_filters(self):
        """Clear all filters"""
        self.search_var.set("")
        self.position_var.set("All")
        self.min_rating_var.set("0")
        
    def on_player_select(self, event):
        """Handle player selection"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            try:
                # Get player index from the tree item
                player_index = int(self.tree.set(item, '#0'))
                if 0 <= player_index < len(self.filtered_players):
                    self.selected_player = self.filtered_players[player_index]
                    self.draft_btn.configure(state='normal')
                    self.info_label.configure(text=f"Selected: {self.selected_player.full_name} "
                                            f"({self.selected_player.primary_position.value}, "
                                            f"OVR {self.selected_player.overall_rating()})")
                else:
                    self.selected_player = None
                    self.draft_btn.configure(state='disabled')
                    self.info_label.configure(text="Invalid selection")
            except (ValueError, IndexError) as e:
                debug_print(f"DEBUG: Error selecting player: {e}")
                self.selected_player = None
                self.draft_btn.configure(state='disabled')
                self.info_label.configure(text="Error selecting player")
        
    def _user_team(self):
        """User's team for fog-of-war display (via parent GUI)."""
        try:
            gm = getattr(self.parent, 'game_manager', None)
            if gm is None:
                gm = getattr(self.parent, 'parent', None)
                gm = getattr(gm, 'game_manager', None) if gm else None
            return getattr(gm, 'user_team', None) if gm else None
        except Exception:
            return None

    def on_player_draft(self, event):
        """Handle double-click to draft"""
        self.draft_player()
        
    def draft_player(self):
        """Draft the selected player"""
        if not self.selected_player:
            messagebox.showwarning("No Selection", "Please select a player to draft.")
            return
            
        # Return the selected player to parent
        result = messagebox.askyesno("Draft Player", 
                                   f"Draft {self.selected_player.full_name}?\n\n"
                                   f"Position: {self.selected_player.primary_position.value}\n"
                                   f"Overall: {self.selected_player.overall_rating()}\n"
                                   f"Age: {self.selected_player.age}")
        
        if result:
            # Set result and close
            self.result = self.selected_player
            self.destroy()
        
    def get_selected_player(self):
        """Get the selected player (for external use)"""
        return getattr(self, 'result', None)

class SimpleDraftOrderWindow(tk.Toplevel):
    """Simple draft order display window"""
    
    def __init__(self, parent, draft_manager):
        super().__init__(parent)
        self.parent = parent
        self.draft_manager = draft_manager
        
        # Window setup
        self.title("🎯 Draft Order")
        self.geometry("800x600")
        self.configure(background='#181818')
        
        self.setup_ui()
        self.populate_draft_order()
        
    def setup_ui(self):
        """Setup the draft order UI"""
        # Main frame
        main_frame = tk.Frame(self, bg='#181818')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = tk.Frame(main_frame, bg='#1F1F1F')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = tk.Label(header_frame, text="🎯 Fantasy Draft Order", 
                              font=('Segoe UI', 16, 'bold'), 
                              fg='#FFFFFF', bg='#1F1F1F')
        title_label.pack(pady=10)
        
        # Current pick info
        current_pick = self.draft_manager.get_current_pick()
        if current_pick:
            current_text = f"Current Pick: #{current_pick.overall_pick} - {current_pick.team.team_name}"
        else:
            current_text = "Draft Complete"
            
        current_label = tk.Label(header_frame, text=current_text, 
                               font=('Segoe UI', 12), 
                               fg='#D13438', bg='#1F1F1F')
        current_label.pack()
        
        # Draft order frame
        order_frame = tk.Frame(main_frame, bg='#181818')
        order_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        columns = ('Pick', 'Round', 'Team', 'Status', 'Player')
        self.tree = ttk.Treeview(order_frame, columns=columns, show='headings', height=20)
        
        # Configure columns
        self.tree.heading('Pick', text='Pick #')
        self.tree.heading('Round', text='Round')
        self.tree.heading('Team', text='Team')
        self.tree.heading('Status', text='Status')
        self.tree.heading('Player', text='Selected Player')
        
        self.tree.column('Pick', width=60)
        self.tree.column('Round', width=60)
        self.tree.column('Team', width=200)
        self.tree.column('Status', width=120)
        self.tree.column('Player', width=200)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(order_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack tree and scrollbar
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        close_btn = tk.Button(main_frame, text="Close", command=self.destroy,
                             bg='#2A2A2A', fg='#FFFFFF', activebackground='#3A3A3A')
        close_btn.pack(pady=(10, 0))
        
    def populate_draft_order(self):
        """Populate the draft order"""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        debug_print(f"DEBUG: Populating draft order with {len(self.draft_manager.draft_picks)} picks")
        
        current_pick_num = self.draft_manager.current_pick
        
        # Show first 200 picks (10+ rounds)
        for i, pick in enumerate(self.draft_manager.draft_picks[:200]):
            # Determine status
            if pick.player:
                status = "COMPLETED"
                player_name = pick.player.full_name
            elif i == current_pick_num:
                status = "⏰ ON THE CLOCK"
                player_name = ""
            else:
                status = "UPCOMING"
                player_name = ""
                
            # Insert item
            item = self.tree.insert('', 'end', values=(
                pick.overall_pick,
                pick.round_num,
                pick.team.team_name,
                status,
                player_name
            ))
            
            # Highlight current pick
            if i == current_pick_num:
                self.tree.selection_set(item)
                self.tree.see(item)
                
        debug_print(f"DEBUG: Added {len(self.tree.get_children())} picks to draft order")
