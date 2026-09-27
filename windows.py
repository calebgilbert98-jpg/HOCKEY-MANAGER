# windows.py
# Contains the classes for all the major pop-up windows in the application.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import customtkinter as ctk
from game_classes import StaffRole, PlayerPosition, ScoutingReport, to_100_scale
from datetime import timedelta
import random
import os
import re
from player_context_menu import PlayerContextMenu, add_player_context_menu
from ui_widgets import PillButton
from modern_ui import AppColors, AppCard
from manager_career import morale_label


def make_pill_group(parent, options, on_select, font_family='Segoe UI'):
    """Row of PillButtons shared by all windows.

    options: list of (value, label). Returns dict value -> PillButton.
    Caller paints selection state via btn.set_selected(...).
    """
    try:
        canvas_bg = parent.cget('bg')
    except tk.TclError:
        # ttk containers have no -bg; fall back to the theme background
        try:
            canvas_bg = ttk.Style().lookup('Panel.TFrame', 'background') or '#0e0e11'
        except Exception:
            canvas_bg = '#0e0e11'
    btns = {}
    for value, label in options:
        b = PillButton(parent, text=label, bg=canvas_bg,
                       font=(font_family, 9, 'bold'),
                       padx=12, pady=4,
                       command=lambda v=value: on_select(v))
        b.pack(side=tk.LEFT, padx=2)
        btns[value] = b
    return btns


# ---------------------------------------------------------------------------
# Quality-of-life helpers: sortable treeviews, friendly empty states,
# and a consistent modern confirm dialog.
# ---------------------------------------------------------------------------

def _qol_sort_value(val):
    """Convert a treeview cell value to something sortable (numeric-aware)."""
    if isinstance(val, str):
        cleaned = (val.replace('$', '').replace(',', '').replace('#', '')
                      .replace('%', '').rstrip('yY').strip())
        try:
            return int(cleaned)
        except (ValueError, TypeError):
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return val.lower()
    return val


def make_tree_sortable(tree):
    """Enable click-column-header sorting on a ttk.Treeview.

    Numeric-aware (handles $1,000,000 / "5y" / percentages); toggles
    ascending/descending and shows an arrow on the sorted column.
    """
    state = {'column': None, 'reverse': False}

    def _sort(col):
        if state['column'] == col:
            state['reverse'] = not state['reverse']
        else:
            state['column'] = col
            state['reverse'] = False
        cols = list(tree['columns'])
        try:
            idx = cols.index(col)
        except ValueError:
            return
        rows = []
        for iid in tree.get_children(''):
            values = tree.item(iid, 'values')
            rows.append((values, iid))
        rows.sort(
            key=lambda r: _qol_sort_value(r[0][idx]) if idx < len(r[0]) else '',
            reverse=state['reverse'])
        for n, (_, iid) in enumerate(rows):
            tree.move(iid, '', n)
        arrow = ' \u2191' if not state['reverse'] else ' \u2193'
        for c in cols:
            base = tree.heading(c, 'text')
            for suffix in (' \u2191', ' \u2193'):
                if base.endswith(suffix):
                    base = base[:-len(suffix)]
            tree.heading(c, text=base + (arrow if c == col else ''))

    for col in tree['columns']:
        tree.heading(col, command=lambda c=col: _sort(c))
    # Keep a reference so the closures are not garbage collected.
    tree._qol_sort_fn = _sort


def set_tree_empty_state(tree, message=None):
    """Show a friendly overlay message when a treeview has no rows.

    Call after populating a table: with rows present any overlay is hidden;
    with zero rows the message is shown centered over the table instead of
    leaving a confusing blank grid.
    """
    label = getattr(tree, '_qol_empty_label', None)
    if tree.get_children():
        if label is not None:
            label.place_forget()
        return
    if not message:
        if label is not None:
            label.place_forget()
        return
    if label is None:
        label = tk.Label(tree, text=message, bg='#16161a', fg='#a1a1aa',
                         font=('Segoe UI', 11, 'italic'), padx=18, pady=12,
                         wraplength=380, justify='center')
        tree._qol_empty_label = label
    else:
        label.config(text=message)
    label.place(relx=0.5, rely=0.5, anchor='center')
    label.lift()


def qol_confirm(parent, title, message, confirm_text="Confirm", cancel_text="Cancel"):
    """Small modern confirm dialog in the charcoal/teal theme.

    Returns True when the user confirms, False otherwise.
    """
    result = {'ok': False}
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.resizable(False, False)
    dlg.configure(bg='#0e0e11')
    try:
        dlg.grab_set()
    except tk.TclError:
        pass

    def _close(ok):
        result['ok'] = ok
        try:
            dlg.grab_release()
        except tk.TclError:
            pass
        dlg.destroy()

    tk.Label(dlg, text=title, bg='#0e0e11', fg='#ffffff',
             font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=18, pady=(16, 6))
    tk.Label(dlg, text=message, bg='#0e0e11', fg='#a1a1aa',
             font=('Segoe UI', 10), wraplength=380, justify='left'
             ).pack(anchor='w', padx=18, pady=(0, 14))

    btn_frame = tk.Frame(dlg, bg='#0e0e11')
    btn_frame.pack(fill='x', padx=18, pady=(0, 16))
    tk.Button(btn_frame, text=cancel_text, command=lambda: _close(False),
              bg='#1e1e24', fg='#ffffff', activebackground='#2a2a32',
              activeforeground='#ffffff', relief='flat', padx=18, pady=8,
              font=('Segoe UI', 10)).pack(side='right')
    tk.Button(btn_frame, text=confirm_text, command=lambda: _close(True),
              bg='#00ceb8', fg='#0e0e11', activebackground='#00a894',
              activeforeground='#0e0e11', relief='flat', padx=18, pady=8,
              font=('Segoe UI', 10, 'bold')).pack(side='right', padx=(0, 10))

    dlg.bind('<Escape>', lambda e: _close(False))
    dlg.bind('<Return>', lambda e: _close(True))
    dlg._qol_escape_close = lambda: _close(False)

    # Center over the parent window.
    try:
        dlg.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        dw, dh = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        x = px + max(0, (pw - dw) // 2)
        y = py + max(0, (ph - dh) // 3)
        dlg.geometry(f"+{x}+{y}")
    except tk.TclError:
        pass
    dlg.wait_window()
    return result['ok']


class RosterWindow(ctk.CTkToplevel):
    """Roster Management (CustomTkinter): dark cards, modern tab bar,
    pill filters, styled stat tables, depth-chart tiles, cap tab."""

    # Tab keys in display order
    _TAB_ORDER = ('nhl', 'ahl', 'prospects', 'depth', 'cap')

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED,
                        BLUE=BLUE, ROW_HOVER=ROW_HOVER, ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()
        super().__init__(parent)
        self.parent = parent
        self.title(f"{parent.user_team.team_name} - Roster Management")
        self.configure(fg_color=BG)
        self.geometry("1600x1000")
        self.minsize(1400, 800)

        # State variables (unchanged from the ttk version)
        self.selected_players = {'nhl': set(), 'ahl': set(), 'prospects': set()}
        self.roster_filters = {
            'position': tk.StringVar(master=self, value="All"),
            'age_min': tk.StringVar(master=self, value=""),
            'age_max': tk.StringVar(master=self, value=""),
            'overall_min': tk.StringVar(master=self, value=""),
            'contract_status': tk.StringVar(master=self, value="All"),
            'injury_status': tk.StringVar(master=self, value="All")
        }
        self.sort_column = None
        self.sort_reverse = False

        # Player maps for treeviews
        self.player_maps = {'nhl': {}, 'ahl': {}, 'prospects': {}}

        # Current tab names (counts change -> tabview.rename)
        self._tab_names = {}

        # Initialize context menu manager
        self.context_menu_manager = PlayerContextMenu(self.parent)

        # Create the interface
        self.create_enhanced_interface()
        self._setup_tree_style()
        self.update_views()

        # Track window
        self.parent.open_windows['roster'] = self

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def create_enhanced_interface(self):
        """Create the comprehensive roster management interface."""
        ct = self._ct
        main_container = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Slim branded banner strip (decorative; never breaks the window)
        try:
            from branding import SlimBanner
            SlimBanner(main_container, 'roster_banner.png', height=84,
                       bg=ct['BG']).pack(fill='x', pady=(0, 10))
        except Exception:
            pass

        # Header section with team overview
        self.create_header_section(main_container)

        # Modern tab bar (CTkTabview instead of ttk.Notebook)
        self.tabview = ctk.CTkTabview(
            main_container,
            fg_color=ct['PANEL'],
            corner_radius=12,
            border_width=1,
            border_color=ct['BORDER'],
            segmented_button_fg_color=ct['PANEL'],
            segmented_button_selected_color=ct['TEAL'],
            segmented_button_selected_hover_color=ct['TEAL_HOVER'],
            segmented_button_unselected_color=ct['CARD'],
            segmented_button_unselected_hover_color=ct['BORDER'],
            text_color=ct['TEXT'],
        )
        self.tabview.pack(fill="both", expand=True, pady=(16, 0))

        self._tab_names = {
            'nhl': "NHL Roster (23)",
            'ahl': "AHL Roster (20)",
            'prospects': "Prospects",
            'depth': "Depth Chart",
            'cap': "Salary Cap",
        }
        for key in self._TAB_ORDER:
            self.tabview.add(self._tab_names[key])

        # Build each tab's content
        self.create_enhanced_nhl_tab()
        self.create_enhanced_ahl_tab()
        self.create_enhanced_prospects_tab()
        self.create_depth_chart_tab()
        self.create_salary_cap_tab()

        # Action buttons footer
        self.create_action_footer(main_container)

    def _cap_numbers(self):
        """Shared payroll figures for the header and the Salary Cap tab.

        Includes buyout dead cap so the header always agrees with the
        Salary Cap tab. Display only -- cap rules themselves live in the sim.
        Returns (salary_cap, current_payroll, cap_space, dead_cap).
        """
        salary_cap = 83500000
        current_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000))
                             for p in self.parent.user_team.roster)
        season = getattr(getattr(self.parent, 'league', None), 'season_year', 2026)
        dead_cap = (getattr(self.parent.user_team, 'buyout_cap_hits', {}) or {}).get(season, 0)
        current_salary += dead_cap
        return salary_cap, current_salary, salary_cap - current_salary, dead_cap

    def create_header_section(self, parent):
        """Create header with team overview and quick stats."""
        ct = self._ct
        header = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12)
        header.pack(fill="x", pady=(0, 4))

        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 4))

        self._heading(top, text=f"{self.parent.user_team.team_name.upper()} ROSTER",
                      size=18).pack(side="left")

        # Quick roster stats on the right
        nhl_count = len(self.parent.user_team.roster)
        ahl_count = len(self.parent.user_team.ahl_roster)
        prospects_count = len(self.parent.user_team.prospects)
        _, _, cap_space, _ = self._cap_numbers()
        stats_text = (f"NHL: {nhl_count}/23 | AHL: {ahl_count}/20 | "
                      f"Prospects: {prospects_count} | Cap Space: ${cap_space:,}")
        self.stats_label = self._body(top, text=stats_text, size=11)
        self.stats_label.pack(side="right")

        # Subtitle with season info
        try:
            season_year = self.parent.league.season_year
            season_str = f"{season_year}-{str(season_year + 1)[-2:]}"
        except Exception:
            season_str = "2026-27"
        total_players = nhl_count + ahl_count + prospects_count
        self._body(header,
                   text=f"Season: {season_str} | Total Players: {total_players}",
                   size=10, dim=True).pack(anchor="w", padx=20, pady=(0, 12))

    def _roster_tab_frame(self, key):
        """Return the CTkTabview content frame for a tab key."""
        return self.tabview.tab(self._tab_names[key])

    def create_enhanced_nhl_tab(self):
        """Create enhanced NHL roster tab with filtering and management tools."""
        nhl_frame = self._roster_tab_frame('nhl')

        # Toolbar for NHL roster
        self.create_roster_toolbar(nhl_frame, 'nhl')

        # NHL roster table with enhanced columns
        nhl_columns = {
            'select': ('☐', 30),
            'jersey': ('#', 40),
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 40),
            'ovr': ('OVR', 45),
            'pot': ('Pot', 45),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'morale': ('Morale', 115),
            'injury': ('Health', 80),
            'toi': ('TOI/GP', 60),
            'performance': ('Performance', 80)
        }

        self.nhl_tree = self.create_enhanced_treeview(nhl_frame, nhl_columns, 'nhl')

        # NHL roster summary
        self.create_roster_summary(nhl_frame, 'nhl')

    def create_enhanced_ahl_tab(self):
        """Create enhanced AHL roster tab."""
        ahl_frame = self._roster_tab_frame('ahl')

        # Toolbar for AHL roster
        self.create_roster_toolbar(ahl_frame, 'ahl')

        # AHL roster table
        ahl_columns = {
            'select': ('☐', 30),
            'jersey': ('#', 40),
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 40),
            'ovr': ('OVR', 45),
            'pot': ('Pot', 45),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'morale': ('Morale', 70),
            'readiness': ('NHL Ready', 80),
            'development': ('Development', 80)
        }

        self.ahl_tree = self.create_enhanced_treeview(ahl_frame, ahl_columns, 'ahl')

        # AHL roster summary
        self.create_roster_summary(ahl_frame, 'ahl')

    def create_enhanced_prospects_tab(self):
        """Create enhanced prospects tab."""
        prospects_frame = self._roster_tab_frame('prospects')

        # Toolbar for prospects
        self.create_roster_toolbar(prospects_frame, 'prospects')

        # Prospects table
        prospects_columns = {
            'select': ('☐', 30),
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 40),
            'ovr': ('OVR', 45),
            'pot': ('Pot', 45),
            'draft_year': ('Draft Year', 80),
            'draft_round': ('Round', 60),
            'league': ('League', 100),
            'development': ('Development', 80),
            'eta': ('ETA', 60)
        }

        self.prospects_tree = self.create_enhanced_treeview(prospects_frame, prospects_columns, 'prospects')

        # Prospects summary
        self.create_roster_summary(prospects_frame, 'prospects')
    def create_depth_chart_tab(self):
        """Create interactive depth chart tab."""
        ct = self._ct
        depth_frame = self._roster_tab_frame('depth')

        header = ctk.CTkFrame(depth_frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(12, 4))
        self._heading(header, text="TEAM DEPTH CHART", size=14).pack()
        self._body(header, text="Click a player tile to open their profile",
                   size=9, dim=True).pack(pady=(2, 0))

        # Scrollable chart area (plain tk canvas per the migration guide --
        # CTk has no canvas and the canvas blends fine inside CTk frames)
        scroll_wrap = ctk.CTkFrame(depth_frame, fg_color="transparent")
        scroll_wrap.pack(fill="both", expand=True, padx=6, pady=(4, 8))
        canvas = tk.Canvas(scroll_wrap, bg=ct['PANEL'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_wrap, orient="vertical",
                                  command=canvas.yview,
                                  style='Roster.Vertical.TScrollbar')
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        chart_frame = tk.Frame(canvas, bg=ct['PANEL'])
        canvas_window = canvas.create_window((0, 0), window=chart_frame,
                                             anchor="nw")
        chart_frame.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_window, width=e.width))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._depth_scroll = (_on_mousewheel, canvas)
        for seq, cmd in (("<MouseWheel>", _on_mousewheel),
                         ("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units")),
                         ("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))):
            canvas.bind(seq, cmd)
        self._depth_chart_frame = chart_frame
        self._depth_chart_bg = ct['PANEL']

        # Build the depth chart sections (rebuildable via _build_depth_chart_sections)
        self._build_depth_chart_sections()

    def _bind_depth_wheel(self, widget):
        """Route mousewheel events over depth-chart widgets to the canvas."""
        _on_mousewheel, _canvas = self._depth_scroll
        for seq, cmd in (("<MouseWheel>", _on_mousewheel),
                         ("<Button-4>", lambda _e: _canvas.yview_scroll(-1, "units")),
                         ("<Button-5>", lambda _e: _canvas.yview_scroll(1, "units"))):
            widget.bind(seq, cmd, add="+")
        for child in widget.winfo_children():
            self._bind_depth_wheel(child)

    def _build_depth_chart_sections(self):
        """(Re)build the depth chart cards from current roster data."""
        for child in self._depth_chart_frame.winfo_children():
            child.destroy()
        self.create_forwards_depth_chart(self._depth_chart_frame)
        self.create_defense_depth_chart(self._depth_chart_frame)
        self.create_goalies_depth_chart(self._depth_chart_frame)
        self._bind_depth_wheel(self._depth_chart_frame)

    def _depth_section_card(self, parent, title):
        """Rounded card container for one depth-chart section."""
        ct = self._ct
        card = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=12)
        card.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 12, "bold"),
                     text_color=ct['TEAL']).pack(anchor="w", padx=14, pady=(10, 6))
        return card

    def _depth_line_row(self, parent, label):
        """One labelled row (line/pair/role) inside a depth-chart card."""
        ct = self._ct
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(row, text=label, width=80, anchor="w",
                     font=("Segoe UI", 10, "bold"),
                     text_color=ct['TEXT_DIM']).pack(side="left")
        return row

    def _depth_player_tile(self, parent, player, slot_label):
        """One player slot: filled clickable tile, or a muted open slot."""
        ct = self._ct
        if player is not None:
            tile = ctk.CTkFrame(parent, fg_color=ct['BORDER'], corner_radius=8,
                                cursor="hand2")
            tile.pack(side="left", padx=4, fill="x", expand=True)
            name_lbl = ctk.CTkLabel(tile, text=player.full_name,
                                    font=("Segoe UI", 10, "bold"),
                                    text_color=ct['TEXT'])
            name_lbl.pack(pady=(6, 0))
            sub_lbl = ctk.CTkLabel(
                tile,
                text=f"{slot_label}  ·  {to_100_scale(player.overall_rating())} OVR",
                font=("Segoe UI", 9), text_color=ct['TEAL'])
            sub_lbl.pack(pady=(0, 6))

            def _open(_event, p=player):
                self.parent.open_player_profile(p)

            def _hover_on(_event, t=tile):
                t.configure(fg_color=ct['ROW_HOVER'])

            def _hover_off(_event, t=tile):
                t.configure(fg_color=ct['BORDER'])

            tile.bind('<Button-1>', _open)
            tile.bind('<Enter>', _hover_on)
            tile.bind('<Leave>', _hover_off)
            for child in (name_lbl, sub_lbl):
                child.bind('<Button-1>', _open)
                child.bind('<Enter>', _hover_on)
                child.bind('<Leave>', _hover_off)
        else:
            tile = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8,
                                border_width=1, border_color=ct['BORDER'])
            tile.pack(side="left", padx=4, fill="x", expand=True)
            ctk.CTkLabel(tile, text=f"Open {slot_label}",
                         font=("Segoe UI", 10),
                         text_color=ct['TEXT_FAINT']).pack(pady=10)

    def create_forwards_depth_chart(self, parent):
        """Create forwards depth chart visualization."""
        body = self._depth_section_card(parent, "FORWARDS")

        # Top 12 forwards by overall, dealt onto 4 lines of LW-C-RW
        forwards = [p for p in self.parent.user_team.roster
                    if p.primary_position.value in ('C', 'LW', 'RW')]
        forwards.sort(key=lambda p: p.overall_rating(), reverse=True)

        lines = ["1st Line", "2nd Line", "3rd Line", "4th Line"]
        positions = ["LW", "C", "RW"]
        for i, line in enumerate(lines):
            row = self._depth_line_row(body, line)
            for j, pos in enumerate(positions):
                idx = i * 3 + j
                player = forwards[idx] if idx < len(forwards) else None
                self._depth_player_tile(row, player, pos)

    def create_defense_depth_chart(self, parent):
        """Create defense depth chart visualization."""
        body = self._depth_section_card(parent, "DEFENSE")

        # Top 6 defensemen by overall, dealt onto 3 pairs of LD-RD
        defensemen = [p for p in self.parent.user_team.roster
                      if p.primary_position.value in ('LD', 'RD', 'D')]
        defensemen.sort(key=lambda p: p.overall_rating(), reverse=True)

        pairs = ["1st Pair", "2nd Pair", "3rd Pair"]
        for i, pair in enumerate(pairs):
            row = self._depth_line_row(body, pair)
            for j, pos in enumerate(["LD", "RD"]):
                idx = i * 2 + j
                player = defensemen[idx] if idx < len(defensemen) else None
                self._depth_player_tile(row, player, pos)

    def create_goalies_depth_chart(self, parent):
        """Create goalies depth chart visualization."""
        body = self._depth_section_card(parent, "GOALIES")

        goalies = [p for p in self.parent.user_team.roster
                   if p.primary_position.value == 'G']
        goalies.sort(key=lambda p: p.overall_rating(), reverse=True)

        for i, role in enumerate(["Starter", "Backup"]):
            row = self._depth_line_row(body, role)
            player = goalies[i] if i < len(goalies) else None
            self._depth_player_tile(row, player, "G")
    def create_salary_cap_tab(self):
        """Create salary cap management tab."""
        cap_frame = self._roster_tab_frame('cap')
        self._cap_tab = cap_frame
        self._build_salary_cap_content()

    def _build_salary_cap_content(self):
        """(Re)build the salary cap tab from current roster data."""
        ct = self._ct
        for child in self._cap_tab.winfo_children():
            child.destroy()

        header = ctk.CTkFrame(self._cap_tab, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(12, 4))
        self._heading(header, text="SALARY CAP MANAGEMENT", size=14).pack()

        # Cap overview
        self.create_cap_overview(self._cap_tab)

        # Contract details
        self.create_contract_breakdown(self._cap_tab)

    def create_cap_overview(self, parent):
        """Create salary cap overview section."""
        ct = self._ct
        card = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=12)
        card.pack(fill="x", padx=10, pady=8)

        # Calculate salary cap info (shared with the header via _cap_numbers)
        salary_cap, current_salary, cap_space, dead_cap = self._cap_numbers()
        cap_percentage = (current_salary / salary_cap) * 100

        # Cap usage bar (pill-shaped progress bar)
        bar_row = ctk.CTkFrame(card, fg_color="transparent")
        bar_row.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(bar_row, text="Cap usage", font=("Segoe UI", 10, "bold"),
                     text_color=ct['TEXT_DIM']).pack(side="left")
        ctk.CTkLabel(bar_row, text=f"{cap_percentage:.1f}%",
                     font=("Segoe UI", 10, "bold"),
                     text_color=ct['TEAL']).pack(side="right")
        bar = ctk.CTkProgressBar(card, height=12, corner_radius=6,
                                 fg_color=ct['BORDER'], progress_color=ct['TEAL'])
        bar.pack(fill="x", padx=18, pady=(0, 6))
        bar.set(min(1.0, current_salary / salary_cap))

        # Cap info grid
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=18, pady=(6, 14))
        cap_labels = [
            ("Salary Cap:", f"${salary_cap:,}"),
            ("Current Payroll:", f"${current_salary:,}"),
            ("Cap Space:", f"${cap_space:,}"),
            ("Cap Usage:", f"{cap_percentage:.1f}%"),
        ]
        if dead_cap:
            cap_labels.append(("Buyout Dead Cap:", f"${dead_cap:,}"))
        for i, (label, value) in enumerate(cap_labels):
            row, col = i // 2, (i % 2) * 2
            ctk.CTkLabel(info, text=label, font=("Segoe UI", 10),
                         text_color=ct['TEXT_DIM']).grid(row=row, column=col,
                                                         sticky='w', padx=5, pady=2)
            ctk.CTkLabel(info, text=value, font=("Segoe UI", 11, "bold"),
                         text_color=ct['TEXT']).grid(row=row, column=col + 1,
                                                    sticky='w', padx=5, pady=2)

    def create_contract_breakdown(self, parent):
        """Create detailed contract breakdown."""
        ct = self._ct
        card = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=12)
        card.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(card, text="Contracts", font=("Segoe UI", 12, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=18, pady=(12, 6))

        # Contract table (dark styled treeview -- see create_enhanced_treeview
        # for the design rationale)
        contract_columns = {
            'name': ('Player', 200),
            'pos': ('Pos', 50),
            'salary': ('Salary', 100),
            'years_left': ('Years Left', 80),
            'total_value': ('Total Value', 100),
            'cap_hit': ('Cap Hit', 100),
            'status': ('Status', 100)
        }

        table_frame = ctk.CTkFrame(card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.contract_tree = ttk.Treeview(table_frame, columns=list(contract_columns.keys()),
                                          show='headings', height=15,
                                          style='Roster.Treeview')
        for col, (text, width) in contract_columns.items():
            self.contract_tree.heading(col, text=text)
            self.contract_tree.column(col, width=width,
                                      anchor='center' if col != 'name' else 'w')
        make_tree_sortable(self.contract_tree)

        contract_scroll = ttk.Scrollbar(table_frame, orient="vertical",
                                        command=self.contract_tree.yview,
                                        style='Roster.Vertical.TScrollbar')
        self.contract_tree.configure(yscrollcommand=contract_scroll.set)

        self.contract_tree.pack(side="left", fill="both", expand=True)
        contract_scroll.pack(side="right", fill="y")

        # Populate contract data
        self.populate_contract_tree()

    def populate_contract_tree(self):
        """Populate the contract breakdown table."""
        # Clear existing items
        self.contract_tree.delete(*self.contract_tree.get_children())

        # Get all NHL roster players
        for player in sorted(self.parent.user_team.roster, key=lambda p: p.overall_rating(), reverse=True):
            # Get contract details
            salary = getattr(player, 'salary', getattr(player.contract, 'salary', 750000))
            years_left = getattr(player, 'contract_years', getattr(player.contract, 'years_remaining', 0))
            total_value = salary * years_left
            cap_hit = salary  # For simplicity, assuming cap hit equals salary

            # Determine status
            if years_left <= 1:
                status = "Expiring"
            elif years_left <= 2:
                status = "Short-term"
            else:
                status = "Long-term"

            # Insert into tree
            values = [
                player.full_name,
                player.primary_position.value,
                f"${salary:,}",
                str(years_left),
                f"${total_value:,}",
                f"${cap_hit:,}",
                status
            ]

            self.contract_tree.insert('', 'end', values=values)

    def create_action_footer(self, parent):
        """Create action buttons footer."""
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", pady=(12, 0))

        left = ctk.CTkFrame(footer, fg_color="transparent")
        left.pack(side="left")
        self._secondary_button(left, text="Trade Block",
                               command=self.parent.open_trade_block_window).pack(side="left", padx=5)
        self._secondary_button(left, text="Contract Extensions",
                               command=self.parent.open_contract_extensions_window).pack(side="left", padx=5)

        right = ctk.CTkFrame(footer, fg_color="transparent")
        right.pack(side="right")
        self._secondary_button(right, text="Export Roster",
                               command=self.export_roster).pack(side="left", padx=5)
        self._secondary_button(right, text="Refresh",
                               command=self.update_views).pack(side="left", padx=5)
        self._secondary_button(right, text="Close",
                               command=self.destroy).pack(side="left", padx=5)

    def _setup_tree_style(self):
        """Dark, flat styling for the roster tables.

        Design decision (see migration guide): the roster tables carry
        11-13 sortable columns plus checkbox multi-select and per-row
        status tags. Rebuilding that as CTk frames would be a maintenance
        burden with no readability gain, so the tables stay ttk.Treeview --
        but styled to not look like a 2000s grid: no borders, no gridlines,
        generous row height, dark headers, teal-tinted selection.
        """
        ct = self._ct
        style = ttk.Style(self)

        style.configure('Roster.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=30,
                        font=('Segoe UI', 10))
        style.configure('Roster.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Roster.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        # Remove the dotted focus border around the tree area
        style.layout('Roster.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])

        # Dark scrollbars to match
        style.configure('Roster.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.configure('Roster.Horizontal.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Roster.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])
        style.map('Roster.Horizontal.TScrollbar',
                  background=[('active', ct['BORDER'])])
    # ------------------------------------------------------------------
    # Toolbar / filters
    # ------------------------------------------------------------------
    def _make_pill_group(self, parent, options, current_value, on_select):
        """Row of PillButtons; returns dict value -> button. Caller keeps it
        in a group list so _paint_pill_groups can repaint all copies."""
        return make_pill_group(parent, options, on_select,
                               font_family=self.parent.FONT_FAMILY)

    def _paint_pill_groups(self):
        for groups_attr, current in (
                ('_pos_pill_groups', self.roster_filters['position'].get()),
                ('_age_pill_groups', self._age_filter_value()),
                ('_ovr_pill_groups', self.roster_filters['overall_min'].get() or "All")):
            for group in getattr(self, groups_attr, []):
                for value, btn in group.items():
                    btn.set_selected(value == current)

    def _age_filter_value(self):
        lo, hi = self.roster_filters['age_min'].get(), self.roster_filters['age_max'].get()
        if not lo and not hi:
            return "All"
        if not lo and hi == "22":
            return "U23"
        if lo == "23" and hi == "29":
            return "23-29"
        if lo == "30" and not hi:
            return "30+"
        return "All"

    def _set_age_filter(self, value):
        f = self.roster_filters
        presets = {"All": ("", ""), "U23": ("", "22"),
                   "23-29": ("23", "29"), "30+": ("30", "")}
        lo, hi = presets[value]
        f['age_min'].set(lo)
        f['age_max'].set(hi)
        self._paint_pill_groups()
        self._refresh_all_roster_tabs()

    def _set_ovr_filter(self, value):
        self.roster_filters['overall_min'].set("" if value == "All" else value)
        self._paint_pill_groups()
        self._refresh_all_roster_tabs()

    def _set_position_filter(self, value):
        """Set the position filter via pill and refresh all roster tabs."""
        self.roster_filters['position'].set(value)
        self._paint_pill_groups()
        self._refresh_all_roster_tabs()

    def _refresh_all_roster_tabs(self):
        for rt in ('nhl', 'ahl', 'prospects'):
            try:
                self.update_roster_tab(rt)
            except Exception:
                pass

    def create_roster_toolbar(self, parent, roster_type):
        """Create filtering and action toolbar for roster tabs."""
        ct = self._ct
        toolbar = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=10)
        toolbar.pack(fill="x", padx=10, pady=(10, 0))

        # Filter pills on the left. PillButton is canvas-drawn and needs a
        # plain tk parent for its bg lookup, so each group gets a tk.Frame
        # wrapper tinted to match the card.
        filters = ctk.CTkFrame(toolbar, fg_color="transparent")
        filters.pack(side="left", padx=12, pady=8)

        def _pill_row(label_text):
            row = ctk.CTkFrame(filters, fg_color="transparent")
            row.pack(side="left", padx=(0, 14))
            ctk.CTkLabel(row, text=label_text, font=("Segoe UI", 10, "bold"),
                         text_color=ct['TEXT_DIM']).pack(side="left", padx=(0, 6))
            wrap = tk.Frame(row, bg=ct['CARD'])
            wrap.pack(side="left")
            return wrap

        if not hasattr(self, '_pos_pill_groups'):
            self._pos_pill_groups = []
        self._pos_pill_groups.append(self._make_pill_group(
            _pill_row("Position"), [(o, o) for o in ("All", "F", "D", "G")],
            self.roster_filters['position'].get(), self._set_position_filter))

        if not hasattr(self, '_age_pill_groups'):
            self._age_pill_groups = []
        self._age_pill_groups.append(self._make_pill_group(
            _pill_row("Age"), [("All", "All"), ("U23", "U23"),
                               ("23-29", "23-29"), ("30+", "30+")],
            self._age_filter_value(), self._set_age_filter))

        if not hasattr(self, '_ovr_pill_groups'):
            self._ovr_pill_groups = []
        self._ovr_pill_groups.append(self._make_pill_group(
            _pill_row("Min OVR"), [("All", "All"), ("70", "70+"),
                                   ("80", "80+"), ("90", "90+")],
            self.roster_filters['overall_min'].get() or "All",
            self._set_ovr_filter))
        self._paint_pill_groups()

        # Action buttons on the right
        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.pack(side="right", padx=12, pady=8)

        if roster_type == 'nhl':
            self._secondary_button(actions, text="Send to AHL",
                                   command=lambda: self.bulk_move_players('nhl', 'ahl')).pack(side="left", padx=3)
            self._primary_button(actions, text="Edit Lines",
                                 command=self.open_lines_editor).pack(side="left", padx=3)
        elif roster_type == 'ahl':
            self._primary_button(actions, text="Call Up",
                                 command=lambda: self.bulk_move_players('ahl', 'nhl')).pack(side="left", padx=3)
            self._secondary_button(actions, text="Send to Prospects",
                                   command=lambda: self.bulk_move_players('ahl', 'prospects')).pack(side="left", padx=3)
        elif roster_type == 'prospects':
            self._primary_button(actions, text="Promote to AHL",
                                 command=lambda: self.bulk_move_players('prospects', 'ahl')).pack(side="left", padx=3)

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------
    def create_enhanced_treeview(self, parent, columns, roster_type):
        """Create a dark-styled multi-column table with sorting/selection.

        (See _setup_tree_style for why this stays a ttk.Treeview.)
        """
        ct = self._ct
        table_frame = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tree = ttk.Treeview(table_frame, columns=list(columns.keys()),
                            show='headings', style='Roster.Treeview', height=20)

        # Configure columns
        for col, (text, width) in columns.items():
            tree.heading(col, text=text,
                         command=lambda c=col: self.sort_treeview(tree, c, roster_type))
            tree.column(col, width=width, anchor='center' if col not in ['name'] else 'w')

        # Row status tags -- the old code assigned these tags but never
        # configured them, so they were invisible. Now they actually style.
        tree.tag_configure('selected', background=ct['ROW_SELECTED'])
        tree.tag_configure('injured', foreground=ct['RED'])
        tree.tag_configure('elite', foreground=ct['GOLD'])
        tree.tag_configure('star', foreground=ct['TEAL'])

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical",
                                    command=tree.yview,
                                    style='Roster.Vertical.TScrollbar')
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal",
                                    command=tree.xview,
                                    style='Roster.Horizontal.TScrollbar')
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack treeview and scrollbars
        tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        v_scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=10)
        h_scrollbar.pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        # Bind events
        tree.bind('<Button-1>', lambda e: self.handle_tree_click(e, tree, roster_type))
        tree.bind('<Double-1>', lambda e: self.handle_double_click(e, tree, roster_type))
        tree.bind('<Button-3>', lambda e: self.show_context_menu(e, tree, roster_type))

        return tree

    def create_roster_summary(self, parent, roster_type):
        """Create summary section for each roster tab."""
        ct = self._ct
        summary = ctk.CTkFrame(parent, fg_color="transparent")
        summary.pack(fill="x", padx=10, pady=(0, 10))

        summary_label = ctk.CTkLabel(summary, text="", font=("Segoe UI", 10),
                                    text_color=ct['TEXT_DIM'])
        summary_label.pack(side="left")
        setattr(self, f'{roster_type}_summary_label', summary_label)

        # Selection actions on the right
        selection = ctk.CTkFrame(summary, fg_color="transparent")
        selection.pack(side="right")
        self._secondary_button(selection, text="Select All",
                               command=lambda: self.select_all_players(roster_type)).pack(side="left", padx=3)
        self._secondary_button(selection, text="Clear Selection",
                               command=lambda: self.clear_selection(roster_type)).pack(side="left", padx=3)

    def _player_passes_filters(self, player):
        """True when the player matches the roster toolbar filters."""
        f = self.roster_filters
        pos_filter = f['position'].get()
        if pos_filter and pos_filter != "All":
            pos = player.primary_position.value
            groups = {'F': ('LW', 'C', 'RW'), 'D': ('LD', 'RD', 'D'), 'G': ('G',)}
            if pos_filter in groups:
                if pos not in groups[pos_filter]:
                    return False
            elif pos != pos_filter:
                return False
        try:
            if f['age_min'].get().strip() and player.age < int(f['age_min'].get()):
                return False
            if f['age_max'].get().strip() and player.age > int(f['age_max'].get()):
                return False
            # Overall filter is on the 1-100 display scale
            if f['overall_min'].get().strip():
                from game_classes import to_100_scale
                if to_100_scale(player.overall_rating()) < int(f['overall_min'].get()):
                    return False
        except (ValueError, TypeError):
            pass
        return True

    def _roster_filters_active(self):
        """True when any roster toolbar filter is narrowing the list."""
        f = getattr(self, 'roster_filters', {}) or {}
        try:
            pos = f.get('position')
            if pos is not None and pos.get() not in ('', 'All'):
                return True
            for key in ('age_min', 'age_max', 'overall_min'):
                entry = f.get(key)
                if entry is not None and str(entry.get()).strip():
                    return True
        except Exception:
            pass
        return False

    def populate_roster_tree(self, tree, players, roster_type):
        """Populate table with player data."""
        # Clear existing items
        tree.delete(*tree.get_children())
        self.player_maps[roster_type] = {}

        for player in sorted(players, key=lambda p: p.overall_rating(), reverse=True):
            if not self._player_passes_filters(player):
                continue
            # Selection checkbox
            is_selected = player.id in self.selected_players[roster_type]
            checkbox = "☑" if is_selected else "☐"

            # Get player info (ratings on the 1-100 display scale, matching
            # the Min OVR filter pills; the sim itself runs on ~50-scale)
            name = player.full_name
            position = player.primary_position.value
            age = player.age
            overall = to_100_scale(player.overall_rating())
            potential = getattr(player, 'potential_grade', 'C')

            # Contract info
            salary = getattr(player, 'salary', getattr(player.contract, 'salary', 750000))
            contract_years = getattr(player, 'contract_years', getattr(player.contract, 'years_remaining', 0))

            # Morale is stored 1-10: show on the 1-100 scale with its descriptor
            morale_raw = int(getattr(player, 'morale', 7) or 7)
            morale = f"{morale_raw * 10} {morale_label(morale_raw)}"
            injury_status = getattr(player, 'injury_status', 'Healthy')

            # Basic values for all roster types
            values = [checkbox, getattr(player, 'jersey_number', ''), name, position,
                     age, overall, potential, f"${salary:,}", f"{contract_years}y", morale]

            # Add roster-specific columns
            if roster_type == 'nhl':
                toi = getattr(player, 'average_toi', '0:00')
                performance = self.calculate_performance_rating(player)
                values.extend([injury_status, toi, performance])
            elif roster_type == 'ahl':
                readiness = self.calculate_nhl_readiness(player)
                development = self.calculate_development_trend(player)
                values.extend([readiness, development])
            elif roster_type == 'prospects':
                draft_year = getattr(player, 'draft_year', 'Undrafted')
                draft_round = getattr(player, 'draft_round', 'FA')
                league = getattr(player, 'current_league', 'Amateur')
                development = self.calculate_development_trend(player)
                eta = self.calculate_eta(player)
                # Remove salary and contract columns for prospects, add prospect-specific data
                values = [checkbox, name, position, age, overall, potential,
                         draft_year, draft_round, league, development, eta]

            # Insert item
            item_id = tree.insert('', 'end', values=values)
            self.player_maps[roster_type][item_id] = player

            # Apply tags for visual styling (thresholds on the 1-100 display
            # scale; identical to the old 47/44 internal-scale cutoffs)
            tags = []
            if is_selected:
                tags.append('selected')
            if injury_status != 'Healthy':
                tags.append('injured')
            if overall >= 94:
                tags.append('elite')
            elif overall >= 88:
                tags.append('star')

            if tags:
                tree.item(item_id, tags=tags)

        # Friendly empty state instead of a blank table.
        if self._roster_filters_active():
            set_tree_empty_state(tree, "No players match your filters")
        else:
            set_tree_empty_state(tree, "No players on this roster")

    def calculate_performance_rating(self, player):
        """Calculate performance rating for NHL players (1-100 display scale)."""
        # Based on season performance; morale (1-10) nudges the rating
        base_performance = to_100_scale(player.overall_rating())
        morale_raw = int(getattr(player, 'morale', 7) or 7)
        variation = (morale_raw - 10) * 2
        performance = max(1, min(100, base_performance + variation))
        return f"{performance}"

    def calculate_nhl_readiness(self, player):
        """Calculate NHL readiness percentage for AHL players."""
        readiness = min(100, max(0, (player.overall_rating() - 35) * 5))
        return f"{readiness:.0f}%"

    def calculate_development_trend(self, player):
        """Calculate development trend."""
        if player.age <= 20:
            return "Rapid ↗"
        elif player.age <= 23:
            return "Steady ↗"
        elif player.age <= 26:
            return "Slow ↗"
        else:
            return "Stable →"

    def calculate_eta(self, player):
        """Calculate estimated time of arrival for prospects."""
        if player.overall_rating() >= 40:
            return "Ready"
        elif player.overall_rating() >= 37:
            return "1-2 years"
        elif player.overall_rating() >= 34:
            return "2-3 years"
        else:
            return "3+ years"

    # ------------------------------------------------------------------
    # Table interaction
    # ------------------------------------------------------------------
    def handle_tree_click(self, event, tree, roster_type):
        """Handle tree click events."""
        region = tree.identify_region(event.x, event.y)
        if region == 'cell':
            col = tree.identify_column(event.x)
            if col == '#1':  # Selection column
                item_id = tree.identify_row(event.y)
                if item_id:
                    self.toggle_player_selection(item_id, tree, roster_type)

    def handle_double_click(self, event, tree, roster_type):
        """Handle double-click to open player profile."""
        item_id = tree.identify_row(event.y)
        if item_id and item_id in self.player_maps[roster_type]:
            player = self.player_maps[roster_type][item_id]
            self.parent.open_player_profile(player)

    def show_context_menu(self, event, tree, roster_type):
        """Show enhanced context menu for player actions using universal system."""
        item_id = tree.identify_row(event.y)
        if item_id and item_id in self.player_maps[roster_type]:
            player = self.player_maps[roster_type][item_id]

            # Create roster-specific additional options
            roster_options = []

            if roster_type == 'nhl':
                roster_options = [
                    ("Send to AHL", lambda: self.move_player(player, 'nhl', 'ahl')),
                    ("Add to Trade Block", lambda: self.add_to_trade_block(player))
                ]
            elif roster_type == 'ahl':
                roster_options = [
                    ("Call Up to NHL", lambda: self.move_player(player, 'ahl', 'nhl')),
                    ("Send to Prospects", lambda: self.move_player(player, 'ahl', 'prospects'))
                ]
            elif roster_type == 'prospects':
                roster_options = [
                    ("Promote to AHL", lambda: self.move_player(player, 'prospects', 'ahl'))
                ]

            # Add contract options
            roster_options.append(("Contract Extension",
                                 lambda: self.parent.open_contract_negotiation_window(player, True)))

            # Use universal context menu
            if not hasattr(self, 'context_menu_manager'):
                self.context_menu_manager = PlayerContextMenu(self.parent)

            self.context_menu_manager.show_context_menu(event, player, roster_options)

    def toggle_player_selection(self, item_id, tree, roster_type):
        """Toggle player selection state."""
        if item_id in self.player_maps[roster_type]:
            player = self.player_maps[roster_type][item_id]

            if player.id in self.selected_players[roster_type]:
                self.selected_players[roster_type].remove(player.id)
                checkbox = "☐"
                # Drop the selected tag, keep status tags
                tags = [t for t in tree.item(item_id, 'tags') if t != 'selected']
            else:
                self.selected_players[roster_type].add(player.id)
                checkbox = "☑"
                tags = list(tree.item(item_id, 'tags')) + ['selected']

            # Update checkbox display
            values = list(tree.item(item_id, 'values'))
            values[0] = checkbox
            tree.item(item_id, values=values, tags=tags)

            self.update_roster_summary(roster_type)

    def sort_treeview(self, tree, col, roster_type):
        """Sort table by column."""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        # Get all items
        items = list(tree.get_children())

        # Sort based on column
        def get_sort_key(item_id):
            values = tree.item(item_id, 'values')
            col_index = list(tree['columns']).index(col)
            value = values[col_index] if col_index < len(values) else ''

            # Potential grades are letters: map to a numeric order
            if col == 'pot':
                order = {'A+': 12, 'A': 11, 'A-': 10, 'B+': 9, 'B': 8,
                         'B-': 7, 'C+': 6, 'C': 5, 'C-': 4,
                         'D+': 3, 'D': 2, 'D-': 1, 'F': 0}
                return order.get(str(value).strip().upper(), -1)

            # Handle numeric columns
            if col in ['age', 'ovr']:
                try:
                    return int(value)
                except:
                    return 0
            elif col == 'salary':
                try:
                    return int(value.replace('$', '').replace(',', ''))
                except:
                    return 0
            return str(value).lower()

        items.sort(key=get_sort_key, reverse=self.sort_reverse)

        # Reorder items in tree
        for i, item_id in enumerate(items):
            tree.move(item_id, '', i)

    # ------------------------------------------------------------------
    # Roster management actions
    # ------------------------------------------------------------------
    def apply_filters(self, roster_type):
        """Apply filters to roster view."""
        self.update_roster_tab(roster_type)

    def update_roster_tab(self, roster_type):
        """Update specific roster tab."""
        if roster_type == 'nhl':
            self.populate_roster_tree(self.nhl_tree, self.parent.user_team.roster, 'nhl')
        elif roster_type == 'ahl':
            self.populate_roster_tree(self.ahl_tree, self.parent.user_team.ahl_roster, 'ahl')
        elif roster_type == 'prospects':
            self.populate_roster_tree(self.prospects_tree, self.parent.user_team.prospects, 'prospects')

        self.update_roster_summary(roster_type)

    def update_roster_summary(self, roster_type):
        """Update roster summary information."""
        if roster_type == 'nhl':
            players = self.parent.user_team.roster
            selected_count = len(self.selected_players['nhl'])
            total_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000)) for p in players)
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            avg_overall = sum(to_100_scale(p.overall_rating()) for p in players) / len(players) if players else 0

            summary = f"Players: {len(players)}/23 | Selected: {selected_count} | Total Salary: ${total_salary:,} | Avg Age: {avg_age:.1f} | Avg OVR: {avg_overall:.1f}"
            self.nhl_summary_label.configure(text=summary)

        elif roster_type == 'ahl':
            players = self.parent.user_team.ahl_roster
            selected_count = len(self.selected_players['ahl'])
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            avg_overall = sum(to_100_scale(p.overall_rating()) for p in players) / len(players) if players else 0

            summary = f"Players: {len(players)}/20 | Selected: {selected_count} | Avg Age: {avg_age:.1f} | Avg OVR: {avg_overall:.1f}"
            self.ahl_summary_label.configure(text=summary)

        elif roster_type == 'prospects':
            players = self.parent.user_team.prospects
            selected_count = len(self.selected_players['prospects'])
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            high_potential = len([p for p in players if getattr(p, 'potential_grade', 'C') in ['A+', 'A', 'A-']])

            summary = f"Prospects: {len(players)} | Selected: {selected_count} | High Potential: {high_potential} | Avg Age: {avg_age:.1f}"
            self.prospects_summary_label.configure(text=summary)

    def select_all_players(self, roster_type):
        """Select all players in the roster."""
        if roster_type == 'nhl':
            players = self.parent.user_team.roster
        elif roster_type == 'ahl':
            players = self.parent.user_team.ahl_roster
        else:
            players = self.parent.user_team.prospects

        self.selected_players[roster_type] = {p.id for p in players}
        self.update_roster_tab(roster_type)

    def clear_selection(self, roster_type):
        """Clear all player selections."""
        self.selected_players[roster_type].clear()
        self.update_roster_tab(roster_type)

    def bulk_move_players(self, from_roster, to_roster):
        """Move selected players between rosters."""
        selected_ids = self.selected_players[from_roster].copy()

        if not selected_ids:
            tk.messagebox.showinfo("No Selection", "Please select players to move.")
            return

        # Get source and destination lists
        if from_roster == 'nhl':
            source_list = self.parent.user_team.roster
        elif from_roster == 'ahl':
            source_list = self.parent.user_team.ahl_roster
        else:
            source_list = self.parent.user_team.prospects

        # Move players
        players_to_move = [p for p in source_list if p.id in selected_ids]

        for player in players_to_move:
            self.move_player(player, from_roster, to_roster)

        # Clear selections and update views
        self.selected_players[from_roster].clear()
        self.update_views()

    def move_player(self, player, from_roster, to_roster):
        """Move a single player between rosters."""
        # Remove from source
        if from_roster == 'nhl':
            self.parent.user_team.roster.remove(player)
        elif from_roster == 'ahl':
            self.parent.user_team.ahl_roster.remove(player)
        else:
            self.parent.user_team.prospects.remove(player)

        # Add to destination
        if to_roster == 'nhl':
            self.parent.user_team.roster.append(player)
        elif to_roster == 'ahl':
            self.parent.user_team.ahl_roster.append(player)
        else:
            self.parent.user_team.prospects.append(player)

        # Update any open windows
        self.parent.update_all_views()

    def add_to_trade_block(self, player):
        """Add player to trade block."""
        if not hasattr(self.parent, 'trade_block'):
            self.parent.trade_block = []

        if player not in self.parent.trade_block:
            self.parent.trade_block.append(player)
            tk.messagebox.showinfo("Trade Block", f"{player.full_name} added to trade block.")
        else:
            tk.messagebox.showinfo("Trade Block", f"{player.full_name} is already on the trade block.")

    def open_lines_editor(self):
        """Open the live lines editor."""
        try:
            self.parent.open_edit_lines_window()
        except Exception:
            pass

    def export_roster(self):
        """Export roster to CSV file."""
        try:
            from datetime import datetime
            import csv
            import os

            # Create exports directory if it doesn't exist
            exports_dir = "exports"
            if not os.path.exists(exports_dir):
                os.makedirs(exports_dir)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"roster_export_{self.parent.user_team.team_name.replace(' ', '_')}_{timestamp}.csv"
            filepath = os.path.join(exports_dir, filename)

            # Collect all roster data
            roster_data = []

            # Add NHL roster
            for player in self.parent.user_team.roster:
                contract = player.contract
                salary = getattr(contract, 'salary', 750000) if contract else 750000
                years_remaining = getattr(contract, 'years_remaining', 0) if contract else 0

                roster_data.append([
                    "NHL",
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    to_100_scale(player.overall_rating()),
                    f"${salary:,}",
                    years_remaining,
                    getattr(player, 'games_played', 0),
                    getattr(player, 'goals', 0),
                    getattr(player, 'assists', 0),
                    getattr(player, 'points', 0),
                    getattr(player, 'plus_minus', 0)
                ])

            # Add AHL roster
            for player in self.parent.user_team.ahl_roster:
                contract = player.contract
                salary = getattr(contract, 'salary', 750000) if contract else 750000
                years_remaining = getattr(contract, 'years_remaining', 0) if contract else 0

                roster_data.append([
                    "AHL",
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    to_100_scale(player.overall_rating()),
                    f"${salary:,}",
                    years_remaining,
                    getattr(player, 'games_played', 0),
                    getattr(player, 'goals', 0),
                    getattr(player, 'assists', 0),
                    getattr(player, 'points', 0),
                    getattr(player, 'plus_minus', 0)
                ])

            # Add Prospects
            for player in self.parent.user_team.prospects:
                contract = player.contract
                salary = getattr(contract, 'salary', 750000) if contract else 750000
                years_remaining = getattr(contract, 'years_remaining', 0) if contract else 0

                roster_data.append([
                    "Prospects",
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    to_100_scale(player.overall_rating()),
                    f"${salary:,}",
                    years_remaining,
                    getattr(player, 'games_played', 0),
                    getattr(player, 'goals', 0),
                    getattr(player, 'assists', 0),
                    getattr(player, 'points', 0),
                    getattr(player, 'plus_minus', 0)
                ])

            # Write to CSV
            headers = ["Level", "Name", "Position", "Age", "Overall", "Salary", "Years Left",
                      "GP", "G", "A", "PTS", "+/-"]

            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(roster_data)

            tk.messagebox.showinfo("Export Successful",
                                 f"Roster exported successfully!\n\n"
                                 f"File: {filename}\n"
                                 f"Location: {exports_dir}\n"
                                 f"Players exported: {len(roster_data)}")

        except Exception as e:
            print(f"Error exporting roster: {e}")
            tk.messagebox.showerror("Export Error", f"Failed to export roster:\n{str(e)}")

    def update_views(self):
        """Update all roster views."""
        self.update_roster_tab('nhl')
        self.update_roster_tab('ahl')
        self.update_roster_tab('prospects')

        # Update header stats
        nhl_count = len(self.parent.user_team.roster)
        ahl_count = len(self.parent.user_team.ahl_roster)
        prospects_count = len(self.parent.user_team.prospects)

        # Header cap figures (buyout dead cap included, matching the Salary Cap tab)
        _, _, cap_space, _ = self._cap_numbers()
        stats_text = f"NHL: {nhl_count}/23 | AHL: {ahl_count}/20 | Prospects: {prospects_count} | Cap Space: ${cap_space:,}"
        self.stats_label.configure(text=stats_text)

        # Update tab labels with counts (CTkTabview.rename keeps tab content)
        for key, new_name in (('nhl', f"NHL Roster ({nhl_count})"),
                              ('ahl', f"AHL Roster ({ahl_count})"),
                              ('prospects', f"Prospects ({prospects_count})")):
            old_name = self._tab_names[key]
            if old_name != new_name:
                try:
                    self.tabview.rename(old_name, new_name)
                except Exception:
                    pass
                self._tab_names[key] = new_name

        # Keep the Depth Chart and Salary Cap tabs in sync too, even when
        # they are not the currently visible tab
        try:
            self.refresh_depth_chart()
            self.refresh_salary_cap()
        except (tk.TclError, AttributeError):
            pass

    def refresh_depth_chart(self):
        """Refresh the depth chart with current roster data."""
        try:
            self._build_depth_chart_sections()
        except (AttributeError, tk.TclError):
            pass

    def refresh_salary_cap(self):
        """Refresh the salary cap information."""
        try:
            self._build_salary_cap_content()
        except (AttributeError, tk.TclError):
            pass

class FreeAgencyWindow(ctk.CTkToplevel):
    """Free Agency Market (CustomTkinter): dark cards, pill filters,
    styled stat tables, CTk dialogs for contracts/comparison/analysis."""

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()
        super().__init__(parent)
        self.parent = parent
        self.title("Free Agency Market")
        self.configure(fg_color=BG)
        self.geometry("1400x900")
        self.minsize(1200, 700)

        # State variables (unchanged from the ttk version)
        self.selected_players = []
        self.selected_staff = []
        self.player_filters = {}
        self.staff_filters = {}
        self._fa_pill_groups = []
        self._staff_pill_groups = []

        # Create the interface
        self.create_enhanced_interface()
        self._setup_tree_style()
        self.update_views()

        # Track window
        self.parent.open_windows['free_agency'] = self

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def create_enhanced_interface(self):
        """Create the modern free agency interface."""
        ct = self._ct
        main_container = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Header section with market overview
        self.create_header_section(main_container)

        # Modern tab bar (CTkTabview instead of ttk.Notebook)
        self.tabview = ctk.CTkTabview(
            main_container,
            fg_color=ct['PANEL'],
            corner_radius=12,
            border_width=1,
            border_color=ct['BORDER'],
            segmented_button_fg_color=ct['PANEL'],
            segmented_button_selected_color=ct['TEAL'],
            segmented_button_selected_hover_color=ct['TEAL_HOVER'],
            segmented_button_unselected_color=ct['CARD'],
            segmented_button_unselected_hover_color=ct['BORDER'],
            text_color=ct['TEXT'],
        )
        self.tabview.pack(fill="both", expand=True, pady=(16, 0))
        for name in ("Free Agent Players", "Free Agent Staff", "Market Overview"):
            self.tabview.add(name)

        self.create_enhanced_player_tab()
        self.create_enhanced_staff_tab()
        self.create_market_overview_tab()

        # Action buttons footer
        self.create_action_footer(main_container)

    def create_header_section(self, parent):
        """Create the header with market overview and quick stats."""
        ct = self._ct
        header = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12)
        header.pack(fill="x", pady=(0, 4))

        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 4))

        self._heading(top, text="FREE AGENCY MARKET", size=18).pack(side="left")

        # Quick stats on the right
        player_count = len(self.parent.game_manager.free_agents)
        staff_count = len(self.parent.league.free_agent_staff)
        self._body(top, text=f"Available: {player_count} Players \u2022 {staff_count} Staff",
                   dim=True, size=12).pack(side="right")

        # Subtitle row
        sub = ctk.CTkFrame(header, fg_color="transparent")
        sub.pack(fill="x", padx=20, pady=(4, 14))
        self._body(sub, text="Season 2024-25 \u2022 Free Agency Period",
                   dim=True, size=11).pack(side="left")

        # Team cap space on the right
        user_team = self.parent.game_manager.user_team
        current_salary = sum(getattr(p, "salary", getattr(p.contract, "salary", 750000)) for p in user_team.roster)
        cap_space = 83500000 - current_salary  # NHL salary cap
        if cap_space > 10000000:
            cap_color = ct['TEAL']
        elif cap_space > 0:
            cap_color = ct['GOLD']
        else:
            cap_color = ct['RED']
        ctk.CTkLabel(sub, text=f"Available Cap Space: ${cap_space:,}",
                     font=("Segoe UI", 11, "bold"),
                     text_color=cap_color).pack(side="right")

    # ------------------------------------------------------------------
    # Pill filter helpers
    # ------------------------------------------------------------------
    def _pill_row(self, parent, label, options, var, on_change, groups):
        """One labeled row of PillButtons. PillButton is canvas-drawn and
        needs a plain tk parent for its bg lookup, so the group gets a
        tk.Frame wrapper tinted to match the card."""
        ct = self._ct
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, font=("Segoe UI", 10, "bold"),
                     text_color=ct['TEXT_DIM'], width=80,
                     anchor="w").pack(side="left", padx=(0, 6))
        wrap = tk.Frame(row, bg=ct['CARD'])
        wrap.pack(side="left")
        btns = make_pill_group(wrap, options, lambda v: on_change(var, v))
        groups.append((var, btns))
        # Paint initial selection state
        current = var.get()
        for value, btn in btns.items():
            btn.set_selected(value == current)

    def _fa_set_filter(self, var, value):
        """Set a free-agency pill filter and refresh instantly."""
        var.set(value)
        self._fa_paint_pills()
        self.populate_filtered_players()

    def _fa_paint_pills(self):
        for var, btns in self._fa_pill_groups:
            current = var.get()
            for value, btn in btns.items():
                btn.set_selected(value == current)

    def _staff_set_filter(self, var, value):
        """Set a staff pill filter and refresh instantly."""
        var.set(value)
        self._staff_paint_pills()
        self.populate_filtered_staff()

    def _staff_paint_pills(self):
        for var, btns in self._staff_pill_groups:
            current = var.get()
            for value, btn in btns.items():
                btn.set_selected(value == current)

    def _setup_tree_style(self):
        """Dark, flat styling for the FA tables (styled ttk.Treeview, per
        the migration guide -- the tables carry 9-11 sortable columns)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('FA.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=30,
                        font=('Segoe UI', 10))
        style.configure('FA.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('FA.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('FA.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('FA.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.configure('FA.Horizontal.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('FA.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])
        style.map('FA.Horizontal.TScrollbar',
                  background=[('active', ct['BORDER'])])

    def _create_fa_treeview(self, parent, columns, height=20, sort_cmd=None):
        """Dark-styled multi-column table inside a rounded card."""
        ct = self._ct
        table_frame = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tree = ttk.Treeview(table_frame, columns=list(columns.keys()),
                            show='headings', style='FA.Treeview', height=height)
        for col, (text, width) in columns.items():
            if sort_cmd is not None:
                tree.heading(col, text=text,
                             command=lambda c=col: sort_cmd(tree, c))
            else:
                tree.heading(col, text=text)
            tree.column(col, width=width,
                        anchor='w' if col == 'name' else 'center')

        # OVR tier tags -- match the Trade Center / CTkPlayerList color scale
        tree.tag_configure('tier_elite', foreground=ct['GREEN'])  # 85+
        tree.tag_configure('tier_top', foreground=ct['TEAL'])     # 78-84
        tree.tag_configure('tier_mid', foreground=ct['GOLD'])     # 70-77

        v_scroll = ttk.Scrollbar(table_frame, orient="vertical",
                                 command=tree.yview,
                                 style='FA.Vertical.TScrollbar')
        h_scroll = ttk.Scrollbar(table_frame, orient="horizontal",
                                 command=tree.xview,
                                 style='FA.Horizontal.TScrollbar')
        tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        v_scroll.pack(side="right", fill="y", padx=(0, 6), pady=10)
        h_scroll.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        return tree

    @staticmethod
    def _ovr_tag(ovr):
        """Tier tag for OVR color-coding (matches CTkPlayerList scale)."""
        if ovr >= 85:
            return 'tier_elite'
        if ovr >= 78:
            return 'tier_top'
        if ovr >= 70:
            return 'tier_mid'
        return ''

    # ------------------------------------------------------------------
    # Player tab
    # ------------------------------------------------------------------
    def create_enhanced_player_tab(self):
        """Player free agency tab with filters, table, and actions."""
        ct = self._ct
        player_tab = self.tabview.tab("Free Agent Players")

        # Filter card
        filter_frame = ctk.CTkFrame(player_tab, fg_color=ct['CARD'], corner_radius=10)
        filter_frame.pack(fill="x", padx=10, pady=10)
        self._heading(filter_frame, text="Player Filters & Search", size=12).pack(
            anchor="w", padx=14, pady=(10, 6))

        # Name search (text search keeps a text box; everything else is pills)
        search_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        search_row.pack(fill="x", padx=14, pady=(0, 6))
        self._body(search_row, text="Name:", dim=True).pack(side="left", padx=(0, 8))
        self.player_name_search = ctk.CTkEntry(
            search_row, width=220, placeholder_text="Search by name...",
            fg_color=ct['BG'], border_color=ct['BORDER'])
        self.player_name_search.pack(side="left", padx=(0, 12))
        self.player_name_search.bind('<KeyRelease>', self.filter_players)
        self._secondary_button(search_row, text="Clear Filters",
                               command=self.clear_player_filters).pack(side="right")

        # Pill filter rows (instant-apply, no dropdowns)
        pills = ctk.CTkFrame(filter_frame, fg_color="transparent")
        pills.pack(fill="x", padx=14, pady=(0, 10))
        self.player_position_filter = tk.StringVar(master=self, value='All')
        self.player_age_filter = tk.StringVar(master=self, value='All')
        self.player_rating_filter = tk.StringVar(master=self, value='All')
        self.player_salary_filter = tk.StringVar(master=self, value='All')
        self.player_contract_filter = tk.StringVar(master=self, value='All')
        self.player_sort_filter = tk.StringVar(master=self, value='Overall')

        self._pill_row(pills, "Position:", [(v, v) for v in
                       ('All', 'C', 'LW', 'RW', 'LD', 'RD', 'G')],
                       self.player_position_filter, self._fa_set_filter,
                       self._fa_pill_groups)
        self._pill_row(pills, "Age:", [(v, v) for v in
                       ('All', '18-22', '23-26', '27-30', '31-35', '36+')],
                       self.player_age_filter, self._fa_set_filter,
                       self._fa_pill_groups)
        self._pill_row(pills, "Rating:", [('All', 'All'), ('90+', '90+'),
                       ('85-89', '85-89'), ('80-84', '80-84'), ('75-79', '75-79'),
                       ('70-74', '70-74'), ('<70', '<70')],
                       self.player_rating_filter, self._fa_set_filter,
                       self._fa_pill_groups)
        self._pill_row(pills, "Salary:", [(v, v) for v in
                       ('All', 'Under $1M', '$1M-$3M', '$3M-$5M', '$5M-$8M', 'Over $8M')],
                       self.player_salary_filter, self._fa_set_filter,
                       self._fa_pill_groups)
        self._pill_row(pills, "Contract:", [(v, v) for v in
                       ('All', '1 Year', '2 Years', '3-4 Years', '5+ Years')],
                       self.player_contract_filter, self._fa_set_filter,
                       self._fa_pill_groups)
        self._pill_row(pills, "Sort by:", [(v, v) for v in
                       ('Overall', 'Age', 'Name', 'Position', 'Salary', 'Potential')],
                       self.player_sort_filter, self._fa_set_filter,
                       self._fa_pill_groups)

        # Results and selection info
        info_frame = ctk.CTkFrame(player_tab, fg_color="transparent")
        info_frame.pack(fill="x", padx=14, pady=(0, 2))
        self.player_results_label = self._body(info_frame, text="Showing 0 players",
                                               dim=True, size=11)
        self.player_results_label.pack(side="left")
        self.player_selection_label = self._body(info_frame, text="",
                                                dim=True, size=11)
        self.player_selection_label.pack(side="right")

        # Player table
        player_columns = {
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'pot': ('Pot', 50),
            'salary': ('Salary', 100),
            'years': ('Years', 60),
            'nationality': ('Country', 80),
            'shoots': ('Shoots', 60),
            'height': ('Height', 60),
            'weight': ('Weight', 60)
        }
        self.fa_player_tree = self._create_fa_treeview(
            player_tab, player_columns, height=22,
            sort_cmd=self.parent._sort_treeview_generic)

        # Bind events
        add_player_context_menu(self.fa_player_tree, self)
        self.fa_player_tree.bind('<Double-1>', self.negotiate_with_player)
        self.fa_player_tree.bind('<<TreeviewSelect>>', self.on_player_selection_changed)

        # Action buttons
        actions = ctk.CTkFrame(player_tab, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=10)
        self._primary_button(actions, text="Sign Selected Player",
                             command=self.sign_selected_player).pack(
            side="left", padx=(0, 10))
        self._secondary_button(actions, text="View Player Profile",
                               command=self.view_selected_player_profile).pack(
            side="left", padx=(0, 10))
        self._secondary_button(actions, text="Compare Players",
                               command=self.compare_selected_players).pack(
            side="left", padx=(0, 10))
        self._secondary_button(actions, text="Market Analysis",
                               command=self.show_player_market_analysis).pack(
            side="left")

    # ------------------------------------------------------------------
    # Staff tab
    # ------------------------------------------------------------------
    def create_enhanced_staff_tab(self):
        """Staff free agency tab with filters, table, and actions."""
        ct = self._ct
        staff_tab = self.tabview.tab("Free Agent Staff")

        # Filter card
        filter_frame = ctk.CTkFrame(staff_tab, fg_color=ct['CARD'], corner_radius=10)
        filter_frame.pack(fill="x", padx=10, pady=10)
        self._heading(filter_frame, text="Staff Filters & Search", size=12).pack(
            anchor="w", padx=14, pady=(10, 6))

        # Name search + role dropdown (23 roles is too many for pills) + clear
        top_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(0, 6))
        self._body(top_row, text="Name:", dim=True).pack(side="left", padx=(0, 8))
        self.staff_name_search = ctk.CTkEntry(
            top_row, width=220, placeholder_text="Search by name...",
            fg_color=ct['BG'], border_color=ct['BORDER'])
        self.staff_name_search.pack(side="left", padx=(0, 16))
        self.staff_name_search.bind('<KeyRelease>', self.filter_staff)
        self._body(top_row, text="Role:", dim=True).pack(side="left", padx=(0, 8))
        from game_classes import StaffRole
        roles = ['All'] + [role.value for role in StaffRole]
        self.staff_role_combo = ctk.CTkComboBox(
            top_row, values=roles, width=220,
            command=lambda _v: self.filter_staff(),
            fg_color=ct['BG'], border_color=ct['BORDER'],
            button_color=ct['CARD'], button_hover_color=ct['BORDER'])
        self.staff_role_combo.set('All')
        self.staff_role_combo.pack(side="left", padx=(0, 16))
        self._secondary_button(top_row, text="Clear Filters",
                               command=self.clear_staff_filters).pack(side="right")

        # Pill filter rows (instant-apply)
        pills = ctk.CTkFrame(filter_frame, fg_color="transparent")
        pills.pack(fill="x", padx=14, pady=(0, 10))
        self.staff_department_filter = tk.StringVar(master=self, value='All')
        self.staff_experience_filter = tk.StringVar(master=self, value='All')
        self.staff_salary_filter = tk.StringVar(master=self, value='All')
        self.staff_sort_filter = tk.StringVar(master=self, value='Overall')

        self._pill_row(pills, "Department:", [(v, v) for v in
                       ('All', 'Management', 'Coaching', 'Development',
                        'Scouting', 'Medical', 'Analytics')],
                       self.staff_department_filter, self._staff_set_filter,
                       self._staff_pill_groups)
        self._pill_row(pills, "Experience:", [(v, v) for v in
                       ('All', '0-2 Years', '3-5 Years', '6-10 Years',
                        '11-15 Years', '16+ Years')],
                       self.staff_experience_filter, self._staff_set_filter,
                       self._staff_pill_groups)
        self._pill_row(pills, "Salary:", [(v, v) for v in
                       ('All', 'Under $100k', '$100k-$250k',
                        '$250k-$500k', '$500k-$1M', 'Over $1M')],
                       self.staff_salary_filter, self._staff_set_filter,
                       self._staff_pill_groups)
        self._pill_row(pills, "Sort by:", [(v, v) for v in
                       ('Overall', 'Name', 'Role', 'Experience', 'Salary', 'Age')],
                       self.staff_sort_filter, self._staff_set_filter,
                       self._staff_pill_groups)

        # Results and selection info
        info_frame = ctk.CTkFrame(staff_tab, fg_color="transparent")
        info_frame.pack(fill="x", padx=14, pady=(0, 2))
        self.staff_results_label = self._body(info_frame, text="Showing 0 staff",
                                              dim=True, size=11)
        self.staff_results_label.pack(side="left")
        self.staff_selection_label = self._body(info_frame, text="",
                                                dim=True, size=11)
        self.staff_selection_label.pack(side="right")

        # Staff table
        staff_columns = {
            'name': ('Name', 180),
            'role': ('Role', 200),
            'dept': ('Department', 120),
            'ovr': ('Rating', 60),
            'experience': ('Experience', 100),
            'salary': ('Salary', 100),
            'years': ('Contract', 80),
            'age': ('Age', 50),
            'nationality': ('Country', 80)
        }
        self.fa_staff_tree = self._create_fa_treeview(
            staff_tab, staff_columns, height=22,
            sort_cmd=self.parent._sort_treeview_generic)

        # Bind events
        self.fa_staff_tree.bind('<Button-3>', self.show_staff_context_menu)
        self.fa_staff_tree.bind('<Double-1>', self.negotiate_with_staff)
        self.fa_staff_tree.bind('<<TreeviewSelect>>', self.on_staff_selection_changed)

        # Action buttons
        actions = ctk.CTkFrame(staff_tab, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=10)
        self._primary_button(actions, text="Hire Selected Staff",
                             command=self.hire_selected_staff).pack(
            side="left", padx=(0, 10))
        self._secondary_button(actions, text="View Staff Profile",
                               command=self.view_selected_staff_profile).pack(
            side="left", padx=(0, 10))
        self._secondary_button(actions, text="Compare Staff",
                               command=self.compare_selected_staff).pack(side="left")

    # ------------------------------------------------------------------
    # Market overview tab
    # ------------------------------------------------------------------
    def create_market_overview_tab(self):
        """Market overview tab with analytics and trends."""
        self._build_market_overview(self.tabview.tab("Market Overview"))

    def _build_market_overview(self, overview_tab):
        """Build (or rebuild) the market overview content."""
        ct = self._ct
        # Market summary card
        summary = ctk.CTkFrame(overview_tab, fg_color=ct['CARD'], corner_radius=10)
        summary.pack(fill="x", padx=10, pady=10)
        self._heading(summary, text="Market Summary", size=12).pack(
            anchor="w", padx=14, pady=(10, 6))

        stats_grid = ctk.CTkFrame(summary, fg_color="transparent")
        stats_grid.pack(fill="x", padx=14, pady=(0, 10))
        stats_grid.grid_columnconfigure(0, weight=1)
        stats_grid.grid_columnconfigure(1, weight=1)

        player_stats = ctk.CTkFrame(stats_grid, fg_color=ct['PANEL'], corner_radius=8)
        player_stats.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._heading(player_stats, text="PLAYER MARKET", size=11).pack(
            anchor="w", padx=12, pady=(10, 4))
        self.populate_player_market_stats(player_stats)

        staff_stats = ctk.CTkFrame(stats_grid, fg_color=ct['PANEL'], corner_radius=8)
        staff_stats.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._heading(staff_stats, text="STAFF MARKET", size=11).pack(
            anchor="w", padx=12, pady=(10, 4))
        self.populate_staff_market_stats(staff_stats)

        # Top players card
        top_card = ctk.CTkFrame(overview_tab, fg_color=ct['CARD'], corner_radius=10)
        top_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._heading(top_card, text="Top Available Players", size=12).pack(
            anchor="w", padx=14, pady=(10, 6))

        positions_frame = ctk.CTkFrame(top_card, fg_color="transparent")
        positions_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        positions = [('Forwards', ['C', 'LW', 'RW']),
                     ('Defense', ['LD', 'RD', 'D']),
                     ('Goalies', ['G'])]
        for i, (pos_name, pos_types) in enumerate(positions):
            pos_frame = ctk.CTkFrame(positions_frame, fg_color=ct['PANEL'],
                                     corner_radius=8)
            pos_frame.grid(row=0, column=i, sticky="nsew", padx=5)
            positions_frame.columnconfigure(i, weight=1)
            self._heading(pos_frame, text=pos_name.upper(), size=11).pack(
                anchor="w", padx=10, pady=(8, 4))
            self.populate_top_players_by_position(pos_frame, pos_types)

    def populate_player_market_stats(self, parent_frame):
        """Populate player market statistics."""
        free_agents = self.parent.game_manager.free_agents
        if not free_agents:
            self._body(parent_frame, text="No free agents available",
                       dim=True).pack(anchor="w", padx=12, pady=5)
            return

        total_players = len(free_agents)
        avg_age = sum(p.age for p in free_agents) / total_players
        avg_rating = sum(p.overall_rating() for p in free_agents) / total_players

        pos_counts = {}
        for player in free_agents:
            pos = player.primary_position.value
            pos_counts[pos] = pos_counts.get(pos, 0) + 1

        avg_salary = sum(self.calculate_market_value(p) for p in free_agents) / total_players

        for stat in (f"Total Available: {total_players}",
                     f"Average Age: {avg_age:.1f}",
                     f"Average Rating: {to_100_scale(avg_rating):.1f}",
                     f"Avg. Market Value: ${avg_salary:,.0f}"):
            self._body(parent_frame, text=stat, dim=True, size=11).pack(
                anchor="w", padx=12, pady=1)

        self._body(parent_frame, text="By Position:", size=10).pack(
            anchor="w", padx=12, pady=(8, 2))
        for pos, count in sorted(pos_counts.items()):
            self._body(parent_frame, text=f"  {pos}: {count}",
                       dim=True, size=11).pack(anchor="w", padx=12)
        # bottom padding
        ctk.CTkFrame(parent_frame, fg_color="transparent", height=8).pack()

    def populate_staff_market_stats(self, parent_frame):
        """Populate staff market statistics."""
        available_staff = self.parent.game_manager.league.free_agent_staff
        if not available_staff:
            self._body(parent_frame, text="No staff available",
                       dim=True).pack(anchor="w", padx=12, pady=5)
            return

        total_staff = len(available_staff)
        avg_age = sum(s.age for s in available_staff) / total_staff

        staff_ratings = []
        for s in available_staff:
            try:
                if hasattr(s, 'overall_rating') and callable(getattr(s, 'overall_rating')):
                    staff_ratings.append(s.overall_rating())
                elif hasattr(s, 'overall_rating'):
                    staff_ratings.append(s.overall_rating)
                else:
                    attrs = ['tactical_knowledge', 'man_management', 'motivating']
                    available_attrs = [getattr(s, attr, 10) for attr in attrs if hasattr(s, attr)]
                    staff_ratings.append(sum(available_attrs) / len(available_attrs) if available_attrs else 10)
            except Exception:
                staff_ratings.append(10)
        avg_rating = sum(staff_ratings) / len(staff_ratings) if staff_ratings else 10

        role_counts = {}
        for staff in available_staff:
            role = staff.role.value
            role_counts[role] = role_counts.get(role, 0) + 1

        avg_salary = sum(getattr(s, 'salary', 100000) for s in available_staff) / total_staff

        for stat in (f"Total Available: {total_staff}",
                     f"Average Age: {avg_age:.1f}",
                     f"Average Rating: {avg_rating:.1f}",
                     f"Avg. Salary: ${avg_salary:,.0f}"):
            self._body(parent_frame, text=stat, dim=True, size=11).pack(
                anchor="w", padx=12, pady=1)

        self._body(parent_frame, text="By Role:", size=10).pack(
            anchor="w", padx=12, pady=(8, 2))
        for role, count in sorted(role_counts.items()):
            self._body(parent_frame,
                       text=f"  {role.replace('_', ' ').title()}: {count}",
                       dim=True, size=11).pack(anchor="w", padx=12)
        ctk.CTkFrame(parent_frame, fg_color="transparent", height=8).pack()

    def populate_top_players_by_position(self, parent_frame, positions):
        """Populate top players for specific positions."""
        ct = self._ct
        position_players = [p for p in self.parent.game_manager.free_agents
                            if p.primary_position.value in positions]
        if not position_players:
            self._body(parent_frame, text="No players available",
                       dim=True).pack(anchor="w", padx=10, pady=5)
            return

        top_players = sorted(position_players,
                             key=lambda p: p.overall_rating(), reverse=True)[:5]

        columns = {'name': ('Player', 130), 'ovr': ('OVR', 44), 'age': ('Age', 44)}
        top_tree = ttk.Treeview(parent_frame, columns=list(columns.keys()),
                                show='headings', height=6, style='FA.Treeview')
        for col, (text, width) in columns.items():
            top_tree.heading(col, text=text)
            top_tree.column(col, width=width,
                            anchor='w' if col == 'name' else 'center')
        make_tree_sortable(top_tree)

        for player in top_players:
            ovr = to_100_scale(player.overall_rating())
            tag = self._ovr_tag(ovr)
            top_tree.insert('', 'end',
                            values=[player.full_name, ovr, player.age],
                            tags=(tag,) if tag else ())

        top_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        top_tree.bind('<Double-1>',
                      lambda e: self.handle_market_overview_double_click(e, top_tree))

    def handle_market_overview_double_click(self, event, tree):
        """Handle double-click on market overview player."""
        item_id = tree.identify_row(event.y)
        if item_id:
            player_name = tree.item(item_id, 'values')[0]
            for player in self.parent.game_manager.free_agents:
                if player.full_name == player_name:
                    self.parent.open_contract_negotiation_window(player)
                    break

    # ------------------------------------------------------------------
    # Action footer
    # ------------------------------------------------------------------
    def create_action_footer(self, parent):
        """Create the action buttons footer."""
        ct = self._ct
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", pady=(12, 0))

        bulk = ctk.CTkFrame(footer, fg_color="transparent")
        bulk.pack(side="left")
        self._secondary_button(bulk, text="Refresh Market",
                               command=self.refresh_market).pack(
            side="left", padx=(0, 10))
        self._secondary_button(bulk, text="Export List",
                               command=self.export_free_agents).pack(side="left")

        controls = ctk.CTkFrame(footer, fg_color="transparent")
        controls.pack(side="right")
        self._secondary_button(controls, text="Close",
                               command=self.destroy).pack(side="right", padx=(10, 0))
        self._secondary_button(controls, text="Help",
                               command=self.show_help).pack(side="right")

    # ------------------------------------------------------------------
    # Filtering / population (logic unchanged from the ttk version)
    # ------------------------------------------------------------------
    def filter_players(self, event=None):
        """Filter the player list based on current filter settings."""
        self.populate_filtered_players()

    def filter_staff(self, event=None):
        """Filter the staff list based on current filter settings."""
        self.populate_filtered_staff()

    def populate_filtered_players(self):
        """Populate the player tree with filtered results."""
        for item in self.fa_player_tree.get_children():
            self.fa_player_tree.delete(item)

        name_filter = self.player_name_search.get().lower()
        position_filter = self.player_position_filter.get()
        age_filter = self.player_age_filter.get()
        rating_filter = self.player_rating_filter.get()
        salary_filter = self.player_salary_filter.get()
        contract_filter = self.player_contract_filter.get()
        sort_by = self.player_sort_filter.get()

        filtered_players = []
        for player in self.parent.game_manager.free_agents:
            if name_filter and name_filter not in player.full_name.lower():
                continue
            if position_filter != 'All' and player.primary_position.value != position_filter:
                continue

            if age_filter != 'All':
                age = player.age
                if age_filter == '18-22' and not (18 <= age <= 22):
                    continue
                elif age_filter == '23-26' and not (23 <= age <= 26):
                    continue
                elif age_filter == '27-30' and not (27 <= age <= 30):
                    continue
                elif age_filter == '31-35' and not (31 <= age <= 35):
                    continue
                elif age_filter == '36+' and age < 36:
                    continue

            # Rating filter (1-100 display scale, matching the OVR column)
            if rating_filter != 'All':
                rating = to_100_scale(player.overall_rating())
                if rating_filter == '90+' and rating < 90:
                    continue
                elif rating_filter == '85-89' and not (85 <= rating <= 89):
                    continue
                elif rating_filter == '80-84' and not (80 <= rating <= 84):
                    continue
                elif rating_filter == '75-79' and not (75 <= rating <= 79):
                    continue
                elif rating_filter == '70-74' and not (70 <= rating <= 74):
                    continue
                elif rating_filter == '<70' and rating >= 70:
                    continue

            if salary_filter != 'All':
                salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
                if salary_filter == 'Under $1M' and salary >= 1_000_000:
                    continue
                elif salary_filter == '$1M-$3M' and not (1_000_000 <= salary <= 3_000_000):
                    continue
                elif salary_filter == '$3M-$5M' and not (3_000_000 < salary <= 5_000_000):
                    continue
                elif salary_filter == '$5M-$8M' and not (5_000_000 < salary <= 8_000_000):
                    continue
                elif salary_filter == 'Over $8M' and salary <= 8_000_000:
                    continue

            if contract_filter != 'All':
                years = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 1))
                if contract_filter == '1 Year' and years != 1:
                    continue
                elif contract_filter == '2 Years' and years != 2:
                    continue
                elif contract_filter == '3-4 Years' and not (3 <= years <= 4):
                    continue
                elif contract_filter == '5+ Years' and years < 5:
                    continue

            filtered_players.append(player)

        if sort_by == 'Overall':
            filtered_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        elif sort_by == 'Age':
            filtered_players.sort(key=lambda p: p.age)
        elif sort_by == 'Name':
            filtered_players.sort(key=lambda p: p.full_name)
        elif sort_by == 'Position':
            filtered_players.sort(key=lambda p: p.primary_position.value)
        elif sort_by == 'Salary':
            filtered_players.sort(
                key=lambda p: getattr(p, "salary", getattr(p.contract, "salary", 750000)),
                reverse=True)
        elif sort_by == 'Potential':
            filtered_players.sort(key=lambda p: p.potential_grade or '')

        for player in filtered_players:
            salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
            contract_years = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 1))
            ovr = to_100_scale(player.overall_rating())

            values = [
                player.full_name,
                player.primary_position.value,
                player.age,
                ovr,
                player.potential_grade,
                f"${salary:,}",
                f"{contract_years}y",
                getattr(player, 'nationality', 'Unknown'),
                getattr(player, 'shoots', 'R'),
                f"{getattr(player, 'height_feet', 6)}'{getattr(player, 'height_inches', 0)}\"",
                f"{getattr(player, 'weight', 180)} lbs"
            ]

            tag = self._ovr_tag(ovr)
            item_id = self.fa_player_tree.insert('', 'end', values=values,
                                                 tags=(tag,) if tag else ())

            if 'fa_players' not in self.parent.tree_maps:
                self.parent.tree_maps['fa_players'] = {}
            self.parent.tree_maps['fa_players'][item_id] = player

        self.player_results_label.configure(text=f"Showing {len(filtered_players)} players")
        set_tree_empty_state(self.fa_player_tree, "No players match your filters")

    def populate_filtered_staff(self):
        """Populate the staff tree with filtered results."""
        for item in self.fa_staff_tree.get_children():
            self.fa_staff_tree.delete(item)

        name_filter = self.staff_name_search.get().lower()
        role_filter = self.staff_role_combo.get()
        department_filter = self.staff_department_filter.get()
        experience_filter = self.staff_experience_filter.get()
        salary_filter = self.staff_salary_filter.get()
        sort_by = self.staff_sort_filter.get()

        filtered_staff = []
        for staff in self.parent.league.free_agent_staff:
            if name_filter and name_filter not in staff.full_name.lower():
                continue
            if role_filter != 'All' and staff.role.value != role_filter:
                continue

            if department_filter != 'All':
                from game_classes import Staff as StaffClass
                staff_dept = StaffClass.get_role_department(staff.role)
                if staff_dept != department_filter:
                    continue

            if experience_filter != 'All':
                exp = max(0, staff.age - 25)
                if experience_filter == '0-2 Years' and not (0 <= exp <= 2):
                    continue
                elif experience_filter == '3-5 Years' and not (3 <= exp <= 5):
                    continue
                elif experience_filter == '6-10 Years' and not (6 <= exp <= 10):
                    continue
                elif experience_filter == '11-15 Years' and not (11 <= exp <= 15):
                    continue
                elif experience_filter == '16+ Years' and exp < 16:
                    continue

            if salary_filter != 'All':
                sal = staff.salary
                if salary_filter == 'Under $100k' and sal >= 100_000:
                    continue
                elif salary_filter == '$100k-$250k' and not (100_000 <= sal <= 250_000):
                    continue
                elif salary_filter == '$250k-$500k' and not (250_000 < sal <= 500_000):
                    continue
                elif salary_filter == '$500k-$1M' and not (500_000 < sal <= 1_000_000):
                    continue
                elif salary_filter == 'Over $1M' and sal <= 1_000_000:
                    continue

            filtered_staff.append(staff)

        if sort_by == 'Overall':
            filtered_staff.sort(key=lambda s: s.overall_rating, reverse=True)
        elif sort_by == 'Name':
            filtered_staff.sort(key=lambda s: s.full_name)
        elif sort_by == 'Role':
            filtered_staff.sort(key=lambda s: s.role.value)
        elif sort_by == 'Experience':
            filtered_staff.sort(key=lambda s: max(0, s.age - 25), reverse=True)
        elif sort_by == 'Salary':
            filtered_staff.sort(key=lambda s: s.salary, reverse=True)
        elif sort_by == 'Age':
            filtered_staff.sort(key=lambda s: s.age)

        for staff in filtered_staff:
            from game_classes import Staff as StaffClass
            department = StaffClass.get_role_department(staff.role)
            experience = max(0, staff.age - 25)
            rating = to_100_scale(staff.overall_rating)

            values = [
                staff.full_name,
                staff.role.value,
                department,
                rating,
                f"{experience}y",
                f"${staff.salary:,}",
                f"{staff.contract_years}y",
                staff.age,
                staff.nationality
            ]

            tag = self._ovr_tag(rating)
            item_id = self.fa_staff_tree.insert('', 'end', values=values,
                                                tags=(tag,) if tag else ())

            if 'fa_staff' not in self.parent.tree_maps:
                self.parent.tree_maps['fa_staff'] = {}
            self.parent.tree_maps['fa_staff'][item_id] = staff

        self.staff_results_label.configure(text=f"Showing {len(filtered_staff)} staff")
        set_tree_empty_state(self.fa_staff_tree, "No staff match your filters")

    def clear_player_filters(self):
        """Clear all player filters."""
        self.player_name_search.delete(0, tk.END)
        self.player_position_filter.set('All')
        self.player_age_filter.set('All')
        self.player_rating_filter.set('All')
        self.player_salary_filter.set('All')
        self.player_contract_filter.set('All')
        self.player_sort_filter.set('Overall')
        self._fa_paint_pills()
        self.populate_filtered_players()

    def clear_staff_filters(self):
        """Clear all staff filters."""
        self.staff_name_search.delete(0, tk.END)
        self.staff_role_combo.set('All')
        self.staff_department_filter.set('All')
        self.staff_experience_filter.set('All')
        self.staff_salary_filter.set('All')
        self.staff_sort_filter.set('Overall')
        self._staff_paint_pills()
        self.populate_filtered_staff()

    def on_player_selection_changed(self, event=None):
        """Handle player selection changes."""
        selection = self.fa_player_tree.selection()
        self.player_selection_label.configure(
            text=f"{len(selection)} player(s) selected" if selection else "")

    def on_staff_selection_changed(self, event=None):
        """Handle staff selection changes."""
        selection = self.fa_staff_tree.selection()
        self.staff_selection_label.configure(
            text=f"{len(selection)} staff selected" if selection else "")

    def sign_selected_player(self):
        """Sign the selected player."""
        selection = self.fa_player_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a player to sign.")
            return

        player = self.parent.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.parent.open_contract_negotiation_window(player)

    def hire_selected_staff(self):
        """Hire the selected staff member via a real contract offer."""
        selection = self.fa_staff_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a staff member to hire.")
            return

        staff = self.parent.tree_maps.get('fa_staff', {}).get(selection[0])
        if staff:
            self._open_staff_contract_dialog(staff)

    def negotiate_with_player(self, event=None):
        """Negotiate with a player (double-click handler)."""
        self.sign_selected_player()

    def negotiate_with_staff(self, event=None):
        """Negotiate with a staff member (double-click handler)."""
        self.hire_selected_staff()

    def show_staff_context_menu(self, event):
        """Show context menu for staff."""
        item_id = self.fa_staff_tree.identify_row(event.y)
        if not item_id:
            return

        self.fa_staff_tree.selection_set(item_id)
        staff = self.parent.tree_maps.get('fa_staff', {}).get(item_id)
        if not staff:
            return

        menu = tk.Menu(self, tearoff=0, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        menu.add_command(label=f"Hire {staff.full_name}", command=self.hire_selected_staff)
        menu.add_command(label="View Staff Profile", command=self.view_selected_staff_profile)

        menu.tk_popup(event.x_root, event.y_root)

    def view_selected_player_profile(self):
        """View the selected player's profile."""
        selection = self.fa_player_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a player to view.")
            return

        player = self.parent.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.parent.open_player_profile(player)

    def view_selected_staff_profile(self):
        """View the selected staff member's profile."""
        selection = self.fa_staff_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a staff member to view.")
            return

        staff = self.parent.tree_maps.get('fa_staff', {}).get(selection[0])
        if staff:
            self._open_staff_profile_dialog(staff)

    # ------------------------------------------------------------------
    # Staff contract dialog (CTk rebuild of the old ttk dialog)
    # ------------------------------------------------------------------
    def _open_staff_contract_dialog(self, staff):
        """Negotiate a real contract offer with a free-agent staff member."""
        ct = self._ct
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Contract Offer - {staff.full_name}")
        dlg.configure(fg_color=ct['BG'])
        dlg.geometry("480x420")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        card = ctk.CTkFrame(dlg, fg_color=ct['PANEL'], corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        self._heading(body, text=f"{staff.full_name}", size=15).pack(anchor="w")
        self._body(body, text=f"{staff.role.value} \u2022 {staff.nationality} \u2022 Age {staff.age}",
                   dim=True, size=11).pack(anchor="w", pady=(2, 10))

        # Asking terms banner
        asking = ctk.CTkFrame(body, fg_color=ct['CARD'], corner_radius=8)
        asking.pack(fill="x", pady=(0, 12))
        self._body(asking, text=f"Asking: ${staff.salary:,} / year  \u2022  {staff.contract_years} years",
                   size=12).pack(anchor="w", padx=12, pady=10)

        offer_info = {'years': 2, 'salary_mult': 1.0}

        self._body(body, text="Contract length:", dim=True, size=11).pack(anchor="w", pady=(0, 4))
        years_seg = ctk.CTkSegmentedButton(
            body, values=["1", "2", "3", "4", "5"],
            selected_color=ct['TEAL'], selected_hover_color=ct['TEAL_HOVER'],
            unselected_color=ct['CARD'], unselected_hover_color=ct['BORDER'],
            command=lambda _v: _paint())
        years_seg.set("2")
        years_seg.pack(anchor="w", pady=(0, 10))

        self._body(body, text="Salary offer:", dim=True, size=11).pack(anchor="w", pady=(0, 4))
        sal_seg = ctk.CTkSegmentedButton(
            body, values=["80%", "Asking", "120%"],
            selected_color=ct['TEAL'], selected_hover_color=ct['TEAL_HOVER'],
            unselected_color=ct['CARD'], unselected_hover_color=ct['BORDER'],
            command=lambda _v: _paint())
        sal_seg.set("Asking")
        sal_seg.pack(anchor="w", pady=(0, 12))

        offer_label = self._body(body, text="", size=12)
        offer_label.pack(anchor="w", pady=(0, 2))
        chance_label = self._body(body, text="", size=11)
        chance_label.pack(anchor="w", pady=(0, 12))

        mult_map = {"80%": 0.8, "Asking": 1.0, "120%": 1.2}

        def _paint():
            offer_info['years'] = int(years_seg.get())
            offer_info['salary_mult'] = mult_map[sal_seg.get()]
            salary = int(staff.salary * offer_info['salary_mult'])
            offer_label.configure(
                text=f"Your offer: ${salary:,} / year  x  {offer_info['years']} "
                     f"year{'s' if offer_info['years'] > 1 else ''}")
            chance = self._staff_offer_accept_chance(staff, offer_info['salary_mult'])
            if chance >= 0.75:
                color = ct['GREEN']
            elif chance >= 0.45:
                color = ct['GOLD']
            else:
                color = ct['RED']
            chance_label.configure(text=f"Estimated acceptance chance: {chance:.0%}",
                                   text_color=color)

        _paint()

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(4, 0))
        self._secondary_button(btns, text="Cancel",
                               command=dlg.destroy).pack(side="right", padx=(10, 0))
        self._primary_button(btns, text="Make Offer",
                             command=lambda: self._resolve_staff_offer(
                                 staff, offer_info['years'],
                                 int(staff.salary * offer_info['salary_mult']),
                                 dlg)).pack(side="right")

    def _staff_offer_accept_chance(self, staff, salary_mult):
        """Rough acceptance chance for a staff offer (display only)."""
        rating = to_100_scale(staff.overall_rating)
        prestige = getattr(self.parent.game_manager.user_team, 'prestige', 50)
        base = 0.45 + (salary_mult - 1.0) * 1.4 + (prestige - 50) / 400 - (rating - 60) / 600
        return max(0.05, min(0.98, base))

    def _resolve_staff_offer(self, staff, years, salary, dlg):
        """Resolve a staff contract offer (original acceptance logic)."""
        chance = self._staff_offer_accept_chance(staff, salary / max(1, staff.salary))

        if self.parent.game_manager.sign_free_agent_staff(staff, salary, years):
            import random
            if random.random() < chance:
                tk.messagebox.showinfo("Offer Accepted",
                                       f"{staff.full_name} has accepted your offer!")
                self.populate_filtered_staff()
                self.refresh_market_overview_data()
                dlg.destroy()
            else:
                tk.messagebox.showinfo("Offer Declined",
                                       f"{staff.full_name} has declined your offer. "
                                       f"Consider offering a better salary.")
        else:
            tk.messagebox.showerror("Error", "Failed to sign staff member. Check your budget.")

    def _open_staff_profile_dialog(self, staff):
        """View a free-agent staff member's profile (CTk)."""
        ct = self._ct
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Staff Profile - {staff.full_name}")
        dlg.configure(fg_color=ct['BG'])
        dlg.geometry("460x500")
        dlg.transient(self)

        card = ctk.CTkFrame(dlg, fg_color=ct['PANEL'], corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=14)

        rating = to_100_scale(staff.overall_rating)
        tier_color = (ct['GREEN'] if rating >= 85 else ct['TEAL'] if rating >= 78
                      else ct['GOLD'] if rating >= 70 else ct['TEXT_DIM'])

        self._heading(scroll, text=staff.full_name, size=16).pack(anchor="w")
        self._body(scroll, text=staff.role.value, dim=True, size=12).pack(anchor="w")
        ctk.CTkLabel(scroll, text=f"{rating:.0f}", font=("Segoe UI", 28, "bold"),
                     text_color=tier_color).pack(anchor="w", pady=(6, 2))

        attrs = staff.get_attributes_for_role() if hasattr(staff, 'get_attributes_for_role') else {}
        for attr_name, attr_value in attrs.items():
            self._fa_attr_row(scroll, attr_name, attr_value)

        ctk.CTkFrame(scroll, fg_color=ct['BORDER'], height=1).pack(fill="x", pady=10)

        exp = max(0, staff.age - 25)
        for text in (f"Age: {staff.age}",
                     f"Nationality: {staff.nationality}",
                     f"Experience: {exp} years",
                     f"Asking: ${staff.salary:,} / year",
                     f"Contract: {staff.contract_years} years"):
            self._body(scroll, text=text, dim=True, size=11).pack(anchor="w", pady=1)

        self._primary_button(scroll, text=f"Hire {staff.full_name}",
                             command=lambda: (dlg.destroy(),
                                              self._open_staff_contract_dialog(staff))
                             ).pack(anchor="w", pady=(14, 0))

    def _fa_attr_row(self, parent, name, value):
        """One attribute row with a meter (used by staff profiles)."""
        ct = self._ct
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=name.replace('_', ' ').title(),
                     font=("Segoe UI", 10), text_color=ct['TEXT_DIM'],
                     width=150, anchor="w").pack(side="left")
        meter = ctk.CTkProgressBar(row, width=140, height=8,
                                   progress_color=ct['TEAL'],
                                   fg_color=ct['BORDER'])
        meter.set(max(0.0, min(1.0, value / 100)))
        meter.pack(side="left", padx=8)
        ctk.CTkLabel(row, text=f"{value:.0f}", font=("Segoe UI", 10, "bold"),
                     text_color=ct['TEXT'], width=36).pack(side="left")

    # ------------------------------------------------------------------
    # Player comparison (CTk)
    # ------------------------------------------------------------------
    def compare_selected_players(self):
        """Compare multiple selected players."""
        selection = self.fa_player_tree.selection()
        if len(selection) < 2:
            tk.messagebox.showwarning("Selection Required",
                                       "Please select at least 2 players to compare.")
            return

        players = []
        for item_id in selection:
            player = self.parent.tree_maps.get('fa_players', {}).get(item_id)
            if player:
                players.append(player)

        if len(players) < 2:
            tk.messagebox.showwarning("Error", "Could not find selected players.")
            return

        self.create_player_comparison_window(players)

    def create_player_comparison_window(self, players):
        """Create a window comparing multiple players (CTk)."""
        ct = self._ct
        compare_window = ctk.CTkToplevel(self)
        compare_window.title(f"Player Comparison ({len(players)} players)")
        compare_window.configure(fg_color=ct['BG'])
        compare_window.geometry("900x700")
        compare_window.transient(self)

        card = ctk.CTkFrame(compare_window, fg_color=ct['PANEL'], corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        self._heading(card, text=f"Player Comparison ({len(players)} players)",
                      size=14).pack(anchor="w", padx=16, pady=(12, 4))

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Header row
        header = ctk.CTkFrame(scroll, fg_color=ct['CARD'], corner_radius=8)
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="Attribute", font=("Segoe UI", 10, "bold"),
                     text_color=ct['TEXT_DIM'], width=180, anchor="w").pack(
            side="left", padx=10, pady=8)
        for player in players:
            ctk.CTkLabel(header, text=player.full_name,
                         font=("Segoe UI", 10, "bold"), text_color=ct['TEXT'],
                         width=130).pack(side="left", padx=4, pady=8)

        # Comparison sections
        self.add_comparison_section(scroll, "Basic Info", players,
                                    [('Position', lambda p: p.primary_position.value),
                                     ('Age', lambda p: str(p.age)),
                                     ('Height', lambda p: f"{getattr(p, 'height_feet', 6)}'{getattr(p, 'height_inches', 0)}\""),
                                     ('Weight', lambda p: f"{getattr(p, 'weight', 180)} lbs"),
                                     ('Shoots', lambda p: getattr(p, 'shoots', 'R')),
                                     ('Nationality', lambda p: getattr(p, 'nationality', 'Unknown'))],
                                    compare_numeric=False)

        self.add_comparison_section(scroll, "Ratings", players,
                                    [('Overall', lambda p: to_100_scale(p.overall_rating())),
                                     ('Potential', lambda p: p.potential_grade)],
                                    compare_numeric=True)

        skill_attrs = self.get_skill_attributes()
        if skill_attrs:
            self.add_comparison_section(scroll, "Skills", players,
                                        [(name.replace('_', ' ').title(),
                                          lambda p, attr=name: to_100_scale(getattr(p, attr, 10)))
                                         for name in skill_attrs[:12]],
                                        compare_numeric=True)

        personality_attrs = self.get_personality_attributes()
        if personality_attrs:
            self.add_comparison_section(scroll, "Personality", players,
                                        [(name.replace('_', ' ').title(),
                                          lambda p, attr=name: to_100_scale(getattr(p, attr, 10)))
                                         for name in personality_attrs[:8]],
                                        compare_numeric=True)

        self.add_comparison_section(scroll, "Contract", players,
                                    [('Salary', lambda p: f"${getattr(p, 'salary', getattr(p.contract, 'salary', 750000)):,}"),
                                     ('Years', lambda p: f"{getattr(p, 'contract_years', getattr(p.contract, 'years_remaining', 1))}y")],
                                    compare_numeric=False)

    def get_skill_attributes(self):
        """Get list of skill attribute names."""
        return [
            'skating', 'shooting', 'passing', 'puck_handling', 'checking',
            'positioning', 'hitting', 'shot_blocking', 'faceoffs', 'stickhandling',
            'offensive_awareness', 'defensive_awareness', 'speed', 'strength',
            'endurance', 'durability'
        ]

    def get_personality_attributes(self):
        """Get list of personality attribute names."""
        return [
            'leadership', 'work_ethic', 'determination', 'team_player',
            'consistency', 'clutch', 'discipline', 'aggression'
        ]

    def add_comparison_section(self, parent, title, players, attributes, compare_numeric=True):
        """Add a comparison section to the comparison window."""
        ct = self._ct
        section = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=8)
        section.pack(fill="x", pady=(0, 8))

        self._heading(section, text=title, size=11).pack(anchor="w", padx=10, pady=(8, 2))

        for attr_name, attr_func in attributes:
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            ctk.CTkLabel(row, text=attr_name, font=("Segoe UI", 10),
                         text_color=ct['TEXT_DIM'], width=180,
                         anchor="w").pack(side="left", padx=10)

            values = []
            for player in players:
                try:
                    value = attr_func(player)
                    values.append(value)
                except Exception:
                    values.append("N/A")

            # Determine best/worst for numeric values
            best_idx = worst_idx = None
            if compare_numeric:
                numeric_values = []
                for i, v in enumerate(values):
                    try:
                        numeric_values.append((i, float(v)))
                    except (ValueError, TypeError):
                        pass
                if numeric_values:
                    best_idx = max(numeric_values, key=lambda x: x[1])[0]
                    worst_idx = min(numeric_values, key=lambda x: x[1])[0]

            for i, value in enumerate(values):
                color = ct['TEXT']
                if i == best_idx:
                    color = ct['GREEN']
                elif i == worst_idx:
                    color = ct['RED']
                ctk.CTkLabel(row, text=str(value), font=("Segoe UI", 10),
                             text_color=color, width=130).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # Staff comparison (CTk)
    # ------------------------------------------------------------------
    def compare_selected_staff(self):
        """Compare multiple selected staff members."""
        selection = self.fa_staff_tree.selection()
        if len(selection) < 2:
            tk.messagebox.showwarning("Selection Required",
                                       "Please select at least 2 staff members to compare.")
            return

        staff_list = []
        for item_id in selection:
            staff = self.parent.tree_maps.get('fa_staff', {}).get(item_id)
            if staff:
                staff_list.append(staff)

        if len(staff_list) < 2:
            tk.messagebox.showwarning("Error", "Could not find selected staff members.")
            return

        self.create_staff_comparison_window(staff_list)

    def create_staff_comparison_window(self, staff_list):
        """Create a window comparing multiple staff members (CTk)."""
        ct = self._ct
        compare_window = ctk.CTkToplevel(self)
        compare_window.title(f"Staff Comparison ({len(staff_list)} staff)")
        compare_window.configure(fg_color=ct['BG'])
        compare_window.geometry("800x600")
        compare_window.transient(self)

        card = ctk.CTkFrame(compare_window, fg_color=ct['PANEL'], corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        self._heading(card, text=f"Staff Comparison ({len(staff_list)} staff)",
                      size=14).pack(anchor="w", padx=16, pady=(12, 4))

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        header = ctk.CTkFrame(scroll, fg_color=ct['CARD'], corner_radius=8)
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="Attribute", font=("Segoe UI", 10, "bold"),
                     text_color=ct['TEXT_DIM'], width=180, anchor="w").pack(
            side="left", padx=10, pady=8)
        for staff in staff_list:
            ctk.CTkLabel(header, text=staff.full_name,
                         font=("Segoe UI", 10, "bold"), text_color=ct['TEXT'],
                         width=130).pack(side="left", padx=4, pady=8)

        self.add_comparison_section(scroll, "Basic Info", staff_list,
                                    [('Role', lambda s: s.role.value),
                                     ('Department', lambda s: self._staff_dept(s)),
                                     ('Age', lambda s: str(s.age)),
                                     ('Nationality', lambda s: s.nationality),
                                     ('Experience', lambda s: f"{max(0, s.age - 25)}y")],
                                    compare_numeric=False)

        self.add_comparison_section(scroll, "Ratings", staff_list,
                                    [('Overall', lambda s: to_100_scale(s.overall_rating))],
                                    compare_numeric=True)

        all_attrs = set()
        for staff in staff_list:
            if hasattr(staff, 'get_attributes_for_role'):
                attrs = staff.get_attributes_for_role()
                all_attrs.update(attrs.keys())

        if all_attrs:
            self.add_comparison_section(scroll, "Attributes", staff_list,
                                        [(name.replace('_', ' ').title(),
                                          lambda s, attr=name: to_100_scale(
                                              s.get_attributes_for_role().get(attr, 10)
                                              if hasattr(s, 'get_attributes_for_role') else 10))
                                         for name in sorted(all_attrs)[:12]],
                                        compare_numeric=True)

        self.add_comparison_section(scroll, "Contract", staff_list,
                                    [('Salary', lambda s: f"${s.salary:,}"),
                                     ('Years', lambda s: f"{s.contract_years}y")],
                                    compare_numeric=False)

    def _staff_dept(self, staff):
        from game_classes import Staff as StaffClass
        return StaffClass.get_role_department(staff.role)

    # ------------------------------------------------------------------
    # Market analysis (CTk)
    # ------------------------------------------------------------------
    def show_player_market_analysis(self):
        """Show market analysis for the selected player."""
        selection = self.fa_player_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection",
                                       "Please select a player for market analysis.")
            return

        player = self.parent.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.create_market_analysis_window(player)

    def create_market_analysis_window(self, player):
        """Create a market analysis window for a player (CTk)."""
        ct = self._ct
        analysis_window = ctk.CTkToplevel(self)
        analysis_window.title(f"Market Analysis - {player.full_name}")
        analysis_window.configure(fg_color=ct['BG'])
        analysis_window.geometry("700x600")
        analysis_window.transient(self)

        card = ctk.CTkFrame(analysis_window, fg_color=ct['PANEL'], corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        self._heading(card, text=f"Market Analysis - {player.full_name}",
                      size=14).pack(anchor="w", padx=16, pady=(12, 4))
        self._body(card, text=f"{player.primary_position.value} \u2022 Age {player.age} \u2022 "
                              f"OVR {to_100_scale(player.overall_rating())}",
                   dim=True, size=11).pack(anchor="w", padx=16, pady=(0, 8))

        tabview = ctk.CTkTabview(card, fg_color=ct['CARD'], corner_radius=10,
                                 border_width=0,
                                 segmented_button_fg_color=ct['CARD'],
                                 segmented_button_selected_color=ct['TEAL'],
                                 segmented_button_selected_hover_color=ct['TEAL_HOVER'],
                                 segmented_button_unselected_color=ct['PANEL'],
                                 segmented_button_unselected_hover_color=ct['BORDER'],
                                 text_color=ct['TEXT'])
        tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for name in ("Value Analysis", "Comparable Players", "Contract Projection"):
            tabview.add(name)

        self.create_value_analysis(tabview.tab("Value Analysis"), player)
        self.create_comparable_analysis(tabview.tab("Comparable Players"), player)
        self.create_contract_projection(tabview.tab("Contract Projection"), player)

    def create_value_analysis(self, parent, player):
        """Create the value analysis section."""
        ct = self._ct
        info = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=8)
        info.pack(fill="x", padx=10, pady=10)
        self._heading(info, text="Value Assessment", size=12).pack(
            anchor="w", padx=12, pady=(10, 4))

        market_value = self.calculate_market_value(player)
        current_salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))

        value_diff = market_value - current_salary
        if value_diff > 500000:
            value_text = f"UNDERVALUED by ${value_diff:,.0f}"
            value_color = ct['GREEN']
        elif value_diff < -500000:
            value_text = f"OVERVALUED by ${abs(value_diff):,.0f}"
            value_color = ct['RED']
        else:
            value_text = "FAIRLY VALUED"
            value_color = ct['TEAL']

        self._body(info, text=f"Market Value: ${market_value:,.0f}", size=11).pack(
            anchor="w", padx=12, pady=1)
        self._body(info, text=f"Current Salary: ${current_salary:,.0f}", size=11).pack(
            anchor="w", padx=12, pady=1)
        ctk.CTkLabel(info, text=f"Assessment: {value_text}",
                     font=("Segoe UI", 11, "bold"),
                     text_color=value_color).pack(anchor="w", padx=12, pady=(4, 10))

        factors = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=8)
        factors.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._heading(factors, text="Value Factors", size=12).pack(
            anchor="w", padx=12, pady=(10, 4))

        value_factors = self.get_value_factors(player)
        for factor, impact in value_factors:
            row = ctk.CTkFrame(factors, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=1)
            self._body(row, text=factor, size=11).pack(side="left")
            ctk.CTkLabel(row, text=impact, font=("Segoe UI", 11),
                         text_color=ct['GREEN'] if '+' in impact else ct['RED']
                         ).pack(side="right")

    def create_comparable_analysis(self, parent, player):
        """Create the comparable players analysis."""
        self._heading(parent, text="Comparable Players", size=12).pack(
            anchor="w", padx=14, pady=(10, 4))

        comparable = self.find_comparable_players(player)

        columns = {'name': ('Player', 150), 'age': ('Age', 50),
                   'ovr': ('OVR', 50), 'salary': ('Salary', 100),
                   'value': ('Value Score', 100)}
        comp_tree = ttk.Treeview(parent, columns=list(columns.keys()),
                                 show='headings', height=10, style='FA.Treeview')
        for col, (text, width) in columns.items():
            comp_tree.heading(col, text=text)
            comp_tree.column(col, width=width,
                             anchor='w' if col == 'name' else 'center')
        make_tree_sortable(comp_tree)

        for comp_player, score in comparable[:10]:
            salary = getattr(comp_player, "salary", getattr(comp_player.contract, "salary", 750000))
            ovr = to_100_scale(comp_player.overall_rating())
            tag = self._ovr_tag(ovr)
            comp_tree.insert('', 'end',
                             values=[comp_player.full_name, comp_player.age, ovr,
                                     f"${salary:,}", f"{score:.1f}"],
                             tags=(tag,) if tag else ())

        comp_tree.pack(fill="both", expand=True, padx=14, pady=(0, 10))

    def create_contract_projection(self, parent, player):
        """Create the contract projection section."""
        ct = self._ct
        info = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=8)
        info.pack(fill="x", padx=10, pady=10)
        self._heading(info, text="Contract Projection", size=12).pack(
            anchor="w", padx=12, pady=(10, 4))

        market_value = self.calculate_market_value(player)
        age = player.age
        suggested_length = self.suggest_contract_length(player)

        term_mult = 1.0
        if suggested_length >= 5:
            term_mult = 0.95  # Slight discount for long term
        elif suggested_length <= 2:
            term_mult = 1.05  # Premium for short term

        projected_salary = market_value * term_mult
        total_value = projected_salary * suggested_length

        for text in (f"Projected Annual Salary: ${projected_salary:,.0f}",
                     f"Suggested Length: {suggested_length} years",
                     f"Total Contract Value: ${total_value:,.0f}"):
            self._body(info, text=text, size=11).pack(anchor="w", padx=12, pady=1)

        self._body(info, text=f"Rationale: {'Prime years, lock in long term' if age < 28 else 'Veteran, shorter term preferred' if age < 32 else 'Aging player, minimal term'}",
                   dim=True, size=11).pack(anchor="w", padx=12, pady=(6, 10))

    # ------------------------------------------------------------------
    # Contract/value calculations (logic unchanged)
    # ------------------------------------------------------------------
    def calculate_market_value(self, player):
        """Calculate the market value of a player."""
        base_value = 750000  # Minimum NHL salary

        # Rating-based value (100-scale: 74 OVR starter -> (74/92)^2 ~= 0.65x)
        rating = player.overall_rating()
        rating_multiplier = (rating / 92) ** 2  # Exponential scaling

        # Age factor
        age = player.age
        if age < 25:
            age_factor = 1.2  # Young players get premium
        elif age < 30:
            age_factor = 1.0  # Prime years
        elif age < 35:
            age_factor = 0.8  # Declining
        else:
            age_factor = 0.6  # Veteran minimum

        # Position factor
        position = player.primary_position.value
        if position == 'G':
            position_factor = 1.1  # Goalies are valuable
        elif position in ['C']:
            position_factor = 1.15  # Centers are premium
        else:
            position_factor = 1.0

        market_value = base_value * rating_multiplier * age_factor * position_factor
        return max(market_value, base_value)

    def suggest_contract_length(self, player):
        """Suggest optimal contract length for a player."""
        age = player.age
        rating = player.overall_rating()

        if age < 25 and rating > 75:
            return 6  # Young star, long term
        elif age < 28:
            return 5  # Prime player
        elif age < 30:
            return 4  # Established
        elif age < 33:
            return 3  # Veteran
        elif age < 35:
            return 2  # Aging
        else:
            return 1  # Old veteran

    def get_value_factors(self, player):
        """Get factors affecting player value."""
        factors = []

        age = player.age
        if age < 25:
            factors.append(("Young age", "+15%"))
        elif age > 32:
            factors.append(("Advanced age", "-20%"))

        rating = player.overall_rating()
        if rating > 45:
            factors.append(("Elite rating", "+25%"))
        elif rating > 40:
            factors.append(("Above average rating", "+10%"))
        elif rating < 35:
            factors.append(("Below average rating", "-15%"))

        position = player.primary_position.value
        if position == 'C':
            factors.append(("Center premium", "+15%"))
        elif position == 'G':
            factors.append(("Goalie premium", "+10%"))

        potential = player.potential_grade
        if potential in ['A', 'A+']:
            factors.append(("High potential", "+20%"))
        elif potential in ['B', 'B+']:
            factors.append(("Good potential", "+10%"))

        return factors

    def find_comparable_players(self, target_player):
        """Find comparable players for market analysis."""
        comparable = []
        target_rating = target_player.overall_rating()
        target_age = target_player.age
        target_pos = target_player.primary_position.value

        for player in self.parent.game_manager.free_agents:
            if player == target_player:
                continue

            # Calculate similarity score
            rating_diff = abs(player.overall_rating() - target_rating)
            age_diff = abs(player.age - target_age)
            pos_match = 1 if player.primary_position.value == target_pos else 0

            # Similarity score (lower is more similar)
            similarity = rating_diff * 2 + age_diff * 0.5 - pos_match * 5
            score = max(0, 100 - similarity)

            if score > 60:  # Only include reasonably similar players
                comparable.append((player, score))

        return sorted(comparable, key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------
    # Refresh / export / help
    # ------------------------------------------------------------------
    def refresh_market(self):
        """Refresh the free agency market data."""
        self.update_views()
        # Rebuild the market overview tab content
        try:
            tab = self.tabview.tab("Market Overview")
            for child in tab.winfo_children():
                child.destroy()
            self._build_market_overview(tab)
        except Exception:
            pass
        tk.messagebox.showinfo("Market Refreshed",
                               "Free agency market data has been refreshed.")

    def update_views(self):
        """Update all views with current data."""
        current = self.tabview.get()
        self.populate_filtered_players()
        self.populate_filtered_staff()
        # Re-select the previously active tab (population doesn't change it,
        # but keep this deterministic for callers during __init__).
        self.tabview.set(current)

    def refresh_market_overview_data(self):
        """Refresh just the market overview numbers after a signing."""
        try:
            tab = self.tabview.tab("Market Overview")
            for child in tab.winfo_children():
                child.destroy()
            self._build_market_overview(tab)
        except Exception:
            pass

    def export_free_agents(self):
        """Export free agent lists to CSV."""
        import csv
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Free Agents"
        )

        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Type', 'Name', 'Position/Role', 'Age', 'Rating',
                                     'Salary', 'Contract Years', 'Nationality'])

                    for player in self.parent.game_manager.free_agents:
                        salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
                        years = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 1))
                        writer.writerow(['Player', player.full_name,
                                         player.primary_position.value, player.age,
                                         to_100_scale(player.overall_rating()),
                                         salary, years, getattr(player, 'nationality', 'Unknown')])

                    for staff in self.parent.league.free_agent_staff:
                        writer.writerow(['Staff', staff.full_name, staff.role.value,
                                         staff.age, to_100_scale(staff.overall_rating),
                                         staff.salary, staff.contract_years, staff.nationality])

                tk.messagebox.showinfo("Export Complete",
                                       f"Free agent data exported to {filename}")
            except Exception as e:
                tk.messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

    def show_help(self):
        """Show help information."""
        help_text = """Free Agency Market Help

PLAYER TAB:
- Use filters to narrow down available players
- Pill buttons apply instantly -- no dropdowns to manage
- Click column headers to sort
- Double-click a player to open contract negotiations
- Select multiple players and click "Compare Players" to compare them
- Use "Market Analysis" for detailed value assessment

STAFF TAB:
- Filter staff by role, department, experience, and salary
- Double-click a staff member to make a contract offer
- Compare staff members to find the best fit

MARKET OVERVIEW:
- View market statistics and trends
- See top available players by position
- Double-click players to open negotiations

FILTERS:
- Position: Filter by player position
- Age: Filter by age ranges
- Rating: Filter by overall rating ranges
- Salary: Filter by salary expectations
- Contract: Filter by desired contract length

Double-click any player or staff member to begin negotiations.
Right-click for additional options and analysis tools.

The Market Overview tab provides analytics and top available talent.
"""
        tk.messagebox.showinfo("Free Agency Help", help_text)

class TradeWindow(ctk.CTkToplevel):
    """Trade Center (CustomTkinter): live value meter, picks, AI counter-offers, history."""

    METER_W = 280
    METER_H = 22

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, CTkPlayerList, CTkOfferList,
            primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE)
        init_ctk_theme()
        super().__init__(parent)
        self.parent = parent
        self.title("Trade Center")
        self.geometry("1280x780")
        self.configure(fg_color=BG)
        self.trade_offers = {'user': [], 'partner': []}
        self._history_visible = False

        # Slim branded banner strip (decorative; never breaks the window)
        try:
            from branding import SlimBanner
            SlimBanner(self, 'trade_banner.png', height=84,
                       bg=BG).pack(fill='x', padx=10, pady=(10, 0))
        except Exception:
            pass

        import trade_engine as te
        self.te = te
        gm = getattr(parent, 'game_manager', None)
        if gm is not None and not hasattr(gm, 'trade_history'):
            gm.trade_history = []

        # ---- Header ----
        header = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        header.pack(fill='x', padx=10, pady=(10, 0))
        heading(header, "Trade Center").pack(side='left', padx=(14, 0), pady=10)
        body(header, "Build a deal both GMs can live with", dim=True).pack(
            side='left', padx=(12, 0))
        hist_btn = secondary_button(header, text="Trade History",
                                    command=self._toggle_history)
        hist_btn.pack(side='right', padx=14)

        # Partner selector row
        partner_row = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        partner_row.pack(fill='x', padx=10, pady=(8, 0))
        body(partner_row, "Trade partner:").pack(side='left', padx=(14, 0), pady=8)
        partner_teams = sorted(t.team_name for t in parent.league.teams
                               if t != parent.user_team)
        self.partner_combo = ctk.CTkComboBox(
            partner_row, values=partner_teams, width=260,
            command=lambda _v: self.update_trade_partner_roster())
        self.partner_combo.pack(side='left', padx=(8, 16), pady=8)
        if partner_teams:
            self.partner_combo.set(partner_teams[0])
        body(partner_row, "Their needs:", dim=True).pack(side='left')
        self.needs_label = body(partner_row, "", dim=False)
        self.needs_label.configure(font=("Segoe UI", 11, "bold"))
        self.needs_label.pack(side='left', padx=(6, 0))

        # ---- Main 3-column layout ----
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill='both', expand=True, padx=10, pady=8)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_columnconfigure(2, weight=3)
        main.grid_rowconfigure(0, weight=1)
        self.main_pane = main

        # Your roster
        user_frame = ctk.CTkFrame(main, fg_color=CARD, corner_radius=10)
        user_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        heading(user_frame, parent.user_team.team_name, size=13).pack(
            anchor='w', padx=12, pady=(10, 4))
        self.user_list = CTkPlayerList(user_frame)
        self.user_list.pack(fill='both', expand=True, padx=8, pady=4)
        btn_row = ctk.CTkFrame(user_frame, fg_color="transparent")
        btn_row.pack(fill='x', padx=8, pady=(4, 10))
        secondary_button(btn_row, text="Add Player  →",
                         command=lambda: self._add_to_trade('user')).pack(
                             side='left', padx=(0, 6))
        secondary_button(btn_row, text="Add Pick",
                         command=lambda: self._add_pick_dialog('user')).pack(side='left')

        # Center: deal panel (scrollable so Propose stays reachable at any height)
        center = ctk.CTkScrollableFrame(main, fg_color=PANEL, corner_radius=10)
        center.grid(row=0, column=1, sticky="nsew", padx=4)

        body(center, "YOUR OFFER", size=10, dim=True).pack(anchor='w', padx=12, pady=(10, 2))
        self.user_offer_list = CTkOfferList(center, height=120)
        self.user_offer_list.pack(fill='x', padx=8)
        secondary_button(center, text="Remove selected",
                         command=lambda: self._remove_from_trade('user')).pack(
                             anchor='e', padx=12, pady=(4, 8))

        # Live trade meter
        body(center, "TRADE METER", size=10, dim=True).pack(anchor='w', padx=12)
        self.meter_canvas = tk.Canvas(center, width=self.METER_W, height=self.METER_H,
                                      highlightthickness=0, bg=PANEL)
        self.meter_canvas.pack(fill='x', padx=12, pady=(2, 2))
        self.meter_label = body(center, "Add assets to evaluate")
        self.meter_label.configure(font=("Segoe UI", 11, "bold"))
        self.meter_label.pack(anchor='w', padx=12, pady=(0, 2))
        self.cap_label = body(center, "", dim=True)
        self.cap_label.pack(anchor='w', padx=12, pady=(0, 8))

        body(center, "THEIR OFFER", size=10, dim=True).pack(anchor='w', padx=12)
        self.partner_offer_list = CTkOfferList(center, height=120)
        self.partner_offer_list.pack(fill='x', padx=8)
        secondary_button(center, text="Remove selected",
                         command=lambda: self._remove_from_trade('partner')).pack(
                             anchor='e', padx=12, pady=(4, 8))

        primary_button(center, text="Propose Trade",
                       command=self.propose_trade).pack(fill='x', padx=12, pady=(6, 0))
        body(center, "The AI GM evaluates value, needs and cap space.\nLowball and expect a counter.",
             size=10, dim=True).pack(padx=12, pady=(8, 10))

        # Partner roster
        partner_frame = ctk.CTkFrame(main, fg_color=CARD, corner_radius=10)
        partner_frame.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        self.partner_title = heading(partner_frame, "Trade Partner", size=13)
        self.partner_title.pack(anchor='w', padx=12, pady=(10, 4))
        self.partner_list = CTkPlayerList(partner_frame)
        self.partner_list.pack(fill='both', expand=True, padx=8, pady=4)
        pbtn_row = ctk.CTkFrame(partner_frame, fg_color="transparent")
        pbtn_row.pack(fill='x', padx=8, pady=(4, 10))
        secondary_button(pbtn_row, text="←  Add Player",
                         command=lambda: self._add_to_trade('partner')).pack(
                             side='left', padx=(0, 6))
        secondary_button(pbtn_row, text="Add Pick",
                         command=lambda: self._add_pick_dialog('partner')).pack(side='left')

        # History panel (hidden by default)
        self.history_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)

        self.update_views()

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def update_views(self):
        roster = sorted(self.parent.user_team.roster,
                        key=lambda p: p.overall_rating(), reverse=True)
        self.user_list.set_players(roster)
        self.update_trade_partner_roster()
        self._refresh_offer_lists()
        self._update_meter()

    def update_trade_partner_roster(self, event=None):
        name = self.partner_combo.get()
        team = next((t for t in self.parent.league.teams
                     if t.team_name == name), None)
        if team:
            self.partner_title.configure(text=team.team_name)
            roster = sorted(team.roster, key=lambda p: p.overall_rating(), reverse=True)
            self.partner_list.set_players(roster)
            needs = self.te.team_needs(team)[:3]
            self.needs_label.configure(text="  ".join(needs) if needs else "—")
        # Partner changed -> clear their side of the deal
        self.trade_offers['partner'] = []
        self._refresh_offer_lists()
        self._update_meter()

    def _refresh_offer_lists(self):
        for side, lst in (('user', self.user_offer_list),
                          ('partner', self.partner_offer_list)):
            labels = [f"{self.te.asset_label(a)}  [{self.te.asset_value(a)}]"
                      for a in self.trade_offers[side]]
            lst.set_items(labels)

    # ------------------------------------------------------------------
    # Trade meter
    # ------------------------------------------------------------------
    def _eval(self):
        return self.te.evaluate_trade(self.trade_offers['user'],
                                      self.trade_offers['partner'])

    def _round_rect(self, c, x1, y1, x2, y2, r, **kw):
        c.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, **kw)
        c.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, **kw)
        c.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, **kw)
        c.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, **kw)
        c.create_rectangle(x1 + r, y1, x2 - r, y2, **kw)
        c.create_rectangle(x1, y1 + r, x2, y2 - r, **kw)

    def _update_meter(self):
        ct = self._ct
        c = self.meter_canvas
        c.delete('all')
        w = c.winfo_width() or self.METER_W
        h = self.METER_H
        pad = 2
        r = (h - 2 * pad) // 2
        ev = self._eval()
        total = ev.user_value + ev.partner_value
        # Track
        self._round_rect(c, pad, pad, w - pad, h - pad, r,
                         fill='#23232b', outline='')
        if total > 0:
            uw = pad + (w - 2 * pad) * ev.user_value / total
            # User share (teal) / partner share (gold), clipped to rounded track
            c.create_rectangle(pad + r, pad + 1, uw, h - pad - 1,
                               fill=ct['TEAL'], outline='')
            c.create_arc(pad, pad, pad + 2 * r, h - pad, start=90, extent=180,
                         fill=ct['TEAL'], outline='')
            c.create_rectangle(uw, pad + 1, w - pad - r, h - pad - 1,
                               fill=ct['GOLD'], outline='')
            c.create_arc(w - pad - 2 * r, pad, w - pad, h - pad,
                         start=270, extent=180, fill=ct['GOLD'], outline='')
            # Fairness marker at center
            c.create_line(w / 2, pad, w / 2, h - pad, fill=ct['BG'], width=2)
        # Label
        if not self.trade_offers['user'] or not self.trade_offers['partner']:
            self.meter_label.configure(text="Add assets on both sides to evaluate",
                                       text_color=ct['TEXT_FAINT'])
        else:
            color = {'Fair deal': ct['GREEN'], 'You overpay': ct['BLUE'],
                     'They overpay': ct['GOLD']}.get(ev.label, ct['TEXT'])
            self.meter_label.configure(
                text=f"{ev.label}  (you {ev.user_value} vs them {ev.partner_value})",
                text_color=color)
        # Cap impact for the user
        gm_team = self.parent.user_team
        in_sal = sum(getattr(p, 'salary', 0) or 0 for p in self.trade_offers['partner']
                     if not self.te._is_pick(p))
        out_sal = sum(getattr(p, 'salary', 0) or 0 for p in self.trade_offers['user']
                      if not self.te._is_pick(p))
        try:
            new_pay = gm_team.payroll - out_sal + in_sal
            room = gm_team.salary_cap - new_pay
            ok = room >= 0
            self.cap_label.configure(
                text=f"Cap room after: ${room / 1e6:.1f}M"
                     if ok else f"OVER CAP by ${-room / 1e6:.1f}M — shed salary!",
                text_color=ct['GREEN'] if ok else ct['RED'])
        except Exception:
            self.cap_label.configure(text="")

    # ------------------------------------------------------------------
    # Building the deal
    # ------------------------------------------------------------------
    def _add_to_trade(self, side):
        lst = self.user_list if side == 'user' else self.partner_list
        player = lst.get_selected()
        if player and player not in self.trade_offers[side]:
            self.trade_offers[side].append(player)
            self._refresh_offer_lists()
            self._update_meter()

    def _remove_from_trade(self, side):
        lst = self.user_offer_list if side == 'user' else self.partner_offer_list
        idx = lst.get_selected_index()
        if idx is None or idx >= len(self.trade_offers[side]):
            return
        del self.trade_offers[side][idx]
        self._refresh_offer_lists()
        self._update_meter()

    def _team_picks(self, team):
        picks = []
        for yr in sorted(getattr(team, 'draft_picks', {}).keys()):
            for pk in team.draft_picks[yr]:
                if getattr(pk, 'current_team', '') == team.team_name:
                    picks.append(pk)
        return picks

    def _add_pick_dialog(self, side):
        from ctk_theme import secondary_button, primary_button, heading, body, BG, PANEL, TEXT
        team = (self.parent.user_team if side == 'user' else
                next((t for t in self.parent.league.teams
                      if t.team_name == self.partner_combo.get()), None))
        if team is None:
            return
        picks = [p for p in self._team_picks(team)
                 if p not in self.trade_offers[side]]
        if not picks:
            messagebox.showinfo("No picks", f"{team.team_name} has no tradeable picks.")
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Add draft pick")
        dlg.geometry("420x360")
        dlg.configure(fg_color=BG)
        dlg.transient(self)
        heading(dlg, f"Select a {team.team_name} pick:", size=12).pack(pady=(14, 6))
        pick_list = CTkOfferList(dlg, height=200)
        pick_list.pack(fill='both', expand=True, padx=12)
        pick_list.set_items([f"{self.te.asset_label(pk)}  [{self.te.asset_value(pk)}]"
                             for pk in picks])

        def add():
            idx = pick_list.get_selected_index()
            if idx is not None:
                self.trade_offers[side].append(picks[idx])
                self._refresh_offer_lists()
                self._update_meter()
                dlg.destroy()

        primary_button(dlg, text="Add to Offer", command=add).pack(pady=12)

    # ------------------------------------------------------------------
    # Proposing + AI negotiation
    # ------------------------------------------------------------------
    def _partner_team(self):
        return next((t for t in self.parent.league.teams
                     if t.team_name == self.partner_combo.get()), None)

    def propose_trade(self):
        partner = self._partner_team()
        if partner is None:
            messagebox.showwarning("No partner", "Select a trade partner first.")
            return
        user_assets = list(self.trade_offers['user'])
        partner_assets = list(self.trade_offers['partner'])
        if not user_assets or not partner_assets:
            messagebox.showwarning("Incomplete", "Put assets on both sides first.")
            return
        # Cap check for the user before bothering the AI
        if not self.te._cap_ok_after(self.parent.user_team, user_assets, partner_assets):
            messagebox.showerror("Cap problem",
                                 "This trade puts YOU over the salary cap. Shed salary first.")
            return
        resp = self.te.ai_consider_trade(partner, user_assets, partner_assets,
                                         user_team=self.parent.user_team)
        if resp.decision == 'accept':
            self._complete_trade(partner, user_assets, partner_assets)
            messagebox.showinfo("Trade Accepted", resp.message +
                                "\n\n" + self._last_summary)
        elif resp.decision == 'reject':
            messagebox.showerror("Trade Rejected", resp.message)
        else:
            self._counter_dialog(partner, user_assets, partner_assets, resp)

    def _counter_dialog(self, partner, user_assets, partner_assets, resp):
        from ctk_theme import secondary_button, primary_button, heading, body, BG, PANEL
        dlg = ctk.CTkToplevel(self)
        dlg.title("Counter-offer")
        dlg.geometry("460x280")
        dlg.configure(fg_color=BG)
        dlg.transient(self)
        heading(dlg, f"{partner.team_name} counters", size=15).pack(pady=(16, 6))
        body(dlg, resp.message, size=11, dim=True).pack(pady=6, padx=24)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(pady=16)

        def accept_counter():
            ua = list(user_assets) + list(resp.want_added)
            pa = list(partner_assets) + list(resp.will_add)
            if not self.te._cap_ok_after(self.parent.user_team, ua, pa):
                messagebox.showerror("Cap problem",
                                     "The counter puts you over the cap.")
                return
            dlg.destroy()
            self._complete_trade(partner, ua, pa)
            messagebox.showinfo("Trade Accepted",
                                "Counter accepted!\n\n" + self._last_summary)

        primary_button(btns, text="Accept Counter",
                       command=accept_counter).pack(side='left', padx=8)
        secondary_button(btns, text="Walk Away",
                         command=dlg.destroy).pack(side='left', padx=8)

    def _complete_trade(self, partner, user_assets, partner_assets):
        gm = getattr(self.parent, 'game_manager', None)
        date_str = str(getattr(gm, 'current_date', '')) if gm else ''
        trade = self.te.execute_trade(self.parent.user_team, partner,
                                      user_assets, partner_assets, date_str)
        self._last_summary = trade.summary
        if gm is not None:
            gm.trade_history.append(trade)
            # Media + news
            try:
                traded = [a for a in user_assets if not self.te._is_pick(a)]
                received = [a for a in partner_assets if not self.te._is_pick(a)]
                if hasattr(gm, 'media_system') and gm.media_system:
                    gm.media_system.process_trade(
                        user_team=self.parent.user_team, other_team=partner,
                        traded_players=traded, received_players=received)
            except Exception:
                pass
            try:
                self.parent.add_news_story(f"TRADE: {trade.summary}")
            except Exception:
                pass
        self.trade_offers = {'user': [], 'partner': []}
        self.parent.update_all_views()
        self.update_views()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def _toggle_history(self):
        from ctk_theme import heading, body, TEXT_FAINT
        gm = getattr(self.parent, 'game_manager', None)
        history = list(getattr(gm, 'trade_history', [])) if gm else []
        if self._history_visible:
            self.history_frame.pack_forget()
            self._history_visible = False
            return
        for child in self.history_frame.winfo_children():
            child.destroy()
        heading(self.history_frame, f"Trade History ({len(history)})", size=13).pack(
            anchor='w', padx=14, pady=(10, 4))
        if not history:
            body(self.history_frame, "No trades yet this save.", dim=True).pack(
                anchor='w', padx=14, pady=(0, 10))
        else:
            hist_list = CTkOfferList(self.history_frame, height=120)
            hist_list.pack(fill='x', padx=10, pady=(0, 10))
            hist_list.set_items([f"{t.date} — {t.summary}"
                                 for t in reversed(history[-20:])])
        self.history_frame.pack(fill='x', padx=10, pady=(0, 8), before=self.main_pane)
        self._history_visible = True


class ScoutingWindow(tk.Toplevel):
    """Modern Scouting Department: fog-of-war prospects, regional scouts, draft board."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Scouting Department")
        self.geometry("1280x780")
        self.configure(background=parent.BG_COLOR)
        import scouting as scmod
        self.scmod = scmod
        self._gm = getattr(parent, 'game_manager', parent)
        self.selected_scout = None
        self.selected_prospect = None
        self.filter_var = tk.StringVar(master=self, value="All Prospects")
        self.search_var = tk.StringVar(master=self)
        self.region_var = tk.StringVar(master=self)

        # ---- Header ----
        header = ttk.Frame(self, style='Panel.TFrame', padding=(14, 10))
        header.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(header, text="Scouting Department",
                  font=(parent.FONT_FAMILY, 18, 'bold'),
                  style='Heading.TLabel').pack(side='left')
        n_prospects = len(getattr(parent.league, 'draft_prospects', []) or [])
        ttk.Label(header, text=f"{n_prospects} draft-eligible prospects on the radar",
                  style='Secondary.TLabel').pack(side='left', padx=(12, 0))

        main_pane = ttk.PanedWindow(self, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=10, pady=8)

        # ============ LEFT: scouts ============
        left = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(left, weight=1)

        ttk.Label(left, text="YOUR SCOUTS", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.scouts_tree = parent._create_treeview(
            left, {'name': ('Name', 120), 'jpa': ('JPA', 36),
                   'jpp': ('JPP', 36), 'region': ('Region', 90)}, height=6)
        self.scouts_tree.pack(fill='x', pady=(0, 4))
        self.scouts_tree.bind('<<TreeviewSelect>>', self._on_scout_selected)

        reg_frame = ttk.Frame(left, style='Panel.TFrame')
        reg_frame.pack(fill='x', pady=(0, 4))
        ttk.Label(reg_frame, text="Region:", style='Secondary.TLabel').pack(side='left')
        self.region_combo = ttk.Combobox(reg_frame, textvariable=self.region_var,
                                        values=self.scmod.SCOUT_REGIONS,
                                        state='readonly', width=16)
        self.region_combo.pack(side='left', padx=6)
        ttk.Button(reg_frame, text="Assign", command=self._assign_region,
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(reg_frame, text="Clear", command=self._clear_region,
                   style='Secondary.TButton').pack(side='left', padx=2)

        ttk.Button(left, text="Hire Scout", command=self._hire_scout,
                   style='Secondary.TButton').pack(anchor='w', pady=(0, 8))

        ttk.Label(left, text="ACTIVE ASSIGNMENTS", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.assign_tree = parent._create_treeview(
            left, {'player': ('Player', 110), 'view': ('Views', 44),
                   'acc': ('Acc', 36)}, height=8)
        self.assign_tree.pack(fill='both', expand=True)
        ttk.Button(left, text="Remove Assignment", command=self._remove_assignment,
                   style='Secondary.TButton').pack(anchor='w', pady=(6, 0))
        ttk.Label(left, text="Regional scouts file reports automatically every few days.",
                  style='Secondary.TLabel', wraplength=260,
                  font=(parent.FONT_FAMILY, 9)).pack(anchor='w', pady=(6, 0))

        # ============ CENTER: prospects + report ============
        center = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(center, weight=2)

        top_row = ttk.Frame(center, style='Panel.TFrame')
        top_row.pack(fill='x', pady=(0, 4))
        ttk.Label(top_row, text="PROSPECT POOL", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(side='left')
        filt_frame = ttk.Frame(top_row, style='Panel.TFrame')
        filt_frame.pack(side='left', padx=(10, 4))
        self._prospect_pills = make_pill_group(
            filt_frame,
            [(o, o) for o in ("All Prospects", "Forwards", "Defensemen",
                              "Goalies", "Top 50", "Not Scouted")],
            self._set_prospect_filter, parent.FONT_FAMILY)
        self._paint_prospect_pills()
        ttk.Entry(top_row, textvariable=self.search_var, width=14).pack(side='left', padx=4)
        ttk.Button(top_row, text="Search", command=self._refresh_prospects,
                   style='Secondary.TButton').pack(side='left')

        self.prospects_tree = parent._create_treeview(
            center, {'rank': ('#', 36), 'name': ('Name', 140), 'pos': ('Pos', 40),
                     'age': ('Age', 36), 'nat': ('Nat', 70), 'pot': ('Pot', 80),
                     'status': ('Status', 90)}, height=11)
        self.prospects_tree.pack(fill='both', expand=True, pady=(0, 6))
        self.prospects_tree.bind('<<TreeviewSelect>>', self._on_prospect_selected)
        for g in self.scmod.GRADE_ORDER:
            self.prospects_tree.tag_configure(f"pot_{g}",
                                              foreground=self.scmod.grade_color(g))

        # Report card
        self.report_frame = ttk.Frame(center, style='Card.TFrame', padding=10)
        self.report_frame.pack(fill='x')
        self._build_report_card()

        # ============ RIGHT: draft board ============
        right = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(right, weight=1)
        ttk.Label(right, text="MY DRAFT BOARD", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        ttk.Label(right, text="Your rankings drive auto-draft on draft night.",
                  style='Secondary.TLabel', wraplength=240,
                  font=(parent.FONT_FAMILY, 9)).pack(anchor='w', pady=(0, 4))
        self.board_list = tk.Listbox(right, height=24, activestyle='none',
                                     bg='#232a3a', fg='#ffffff',
                                     selectbackground='#0d2b28', relief='flat',
                                     highlightthickness=1,
                                     highlightbackground='#2e2e38')
        self.board_list.pack(fill='both', expand=True)
        brow = ttk.Frame(right, style='Panel.TFrame')
        brow.pack(fill='x', pady=(6, 0))
        ttk.Button(brow, text="▲", width=3, command=lambda: self._move_board(-1),
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(brow, text="▼", width=3, command=lambda: self._move_board(1),
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(brow, text="Remove", command=self._remove_board,
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(right, text="Reset to Consensus Top 50",
                   command=self._reset_board,
                   style='Secondary.TButton').pack(fill='x', pady=(6, 0))

        self._refresh_all()

    # ------------------------------------------------------------------
    def _build_report_card(self):
        f = self.report_frame
        self.rep_title = ttk.Label(f, text="Select a prospect",
                                  font=(self.parent.FONT_FAMILY, 13, 'bold'),
                                  style='Card.TLabel')
        self.rep_title.pack(anchor='w')
        self.rep_pot = ttk.Label(f, text="", font=(self.parent.FONT_FAMILY, 12, 'bold'),
                                style='Card.TLabel')
        self.rep_pot.pack(anchor='w', pady=(2, 0))
        self.rep_meta = ttk.Label(f, text="", style='Card.TLabel',
                                 font=(self.parent.FONT_FAMILY, 10))
        self.rep_meta.pack(anchor='w')
        cols = ttk.Frame(f, style='Card.TFrame')
        cols.pack(fill='x', pady=(6, 0))
        left_c = ttk.Frame(cols, style='Card.TFrame')
        left_c.pack(side='left', fill='x', expand=True)
        right_c = ttk.Frame(cols, style='Card.TFrame')
        right_c.pack(side='left', fill='x', expand=True)
        ttk.Label(left_c, text="Strengths", style='Card.TLabel',
                  font=(self.parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.rep_strengths = ttk.Label(left_c, text="—", style='Card.TLabel',
                                      wraplength=260, justify='left')
        self.rep_strengths.pack(anchor='w')
        ttk.Label(right_c, text="Weaknesses", style='Card.TLabel',
                  font=(self.parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.rep_weak = ttk.Label(right_c, text="—", style='Card.TLabel',
                                  wraplength=260, justify='left')
        self.rep_weak.pack(anchor='w')
        self.rep_notes = ttk.Label(f, text="", style='Card.TLabel',
                                  wraplength=560, justify='left',
                                  font=(self.parent.FONT_FAMILY, 10))
        self.rep_notes.pack(anchor='w', pady=(6, 0))
        brow = ttk.Frame(f, style='Card.TFrame')
        brow.pack(fill='x', pady=(8, 0))
        ttk.Button(brow, text="Assign Selected Scout",
                   command=self._assign_scout_to_prospect,
                   style='Secondary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(brow, text="Add to Draft Board",
                   command=self._add_prospect_to_board,
                   style='Secondary.TButton').pack(side='left')

    # ------------------------------------------------------------------
    def _refresh_all(self):
        self._refresh_scouts()
        self._refresh_assignments()
        self._refresh_prospects()
        self._refresh_board()

    def _refresh_scouts(self):
        from game_classes import StaffRole
        tree = self.scouts_tree
        tree.delete(*tree.get_children())
        scouts = [s for s in self.parent.user_team.staff
                  if self.scmod.is_scout(s)]
        tm = self.parent.tree_maps.setdefault(tree, {})
        for s in scouts:
            region = self.scmod.get_scout_region(self._gm, s) or "—"
            item = tree.insert('', 'end', values=(
                getattr(s, 'full_name', '?'),
                getattr(s, 'judging_player_ability', '?'),
                getattr(s, 'judging_player_potential', '?'),
                region))
            tm[item] = s

    def _on_scout_selected(self, event=None):
        sel = self.scouts_tree.selection()
        tm = self.parent.tree_maps.get(self.scouts_tree, {})
        self.selected_scout = tm.get(sel[0]) if sel else None
        if self.selected_scout:
            self.region_var.set(
                self.scmod.get_scout_region(self._gm, self.selected_scout) or "")

    def _assign_region(self):
        if not self.selected_scout:
            messagebox.showwarning("No Scout", "Select a scout first.")
            return
        region = self.region_var.get()
        if not region:
            return
        self.scmod.set_scout_region(self._gm, self.selected_scout, region)
        self._refresh_scouts()

    def _clear_region(self):
        if self.selected_scout:
            self.scmod.set_scout_region(self._gm, self.selected_scout, None)
            self.region_var.set("")
            self._refresh_scouts()

    def _hire_scout(self):
        from game_classes import Staff, StaffRole
        import random as _r
        names = [("Jim", "Gregory"), ("Marie", "Labelle"), ("Ken", "Holland"),
                 ("Sofia", "Lindqvist"), ("Petr", "Novak"), ("Dave", "Morrison")]
        fn, ln = _r.choice(names)
        scout = Staff(first_name=fn, last_name=ln, role=StaffRole.AMATEUR_SCOUT)
        self.parent.user_team.staff.append(scout)
        messagebox.showinfo("Scout Hired",
                            f"{scout.full_name} joined your scouting department.\n"
                            f"Assign them a region to start filing reports.")
        self._refresh_scouts()

    def _refresh_assignments(self):
        tree = self.assign_tree
        tree.delete(*tree.get_children())
        tm = self.parent.tree_maps.setdefault(tree, {})
        for player, scout in getattr(self.parent, 'scouting_assignments', {}).items():
            report = self.parent.user_team.scouting_reports.get(player.id)
            views = getattr(report, 'viewings', 0) if report else 0
            acc = getattr(report, 'accuracy', '—') if report else '—'
            item = tree.insert('', 'end', values=(
                player.full_name,
                views, acc))
            tm[item] = player

    def _remove_assignment(self):
        sel = self.assign_tree.selection()
        tm = self.parent.tree_maps.get(self.assign_tree, {})
        player = tm.get(sel[0]) if sel else None
        if player and player in getattr(self.parent, 'scouting_assignments', {}):
            del self.parent.scouting_assignments[player]
            self._refresh_assignments()
            self._refresh_prospects()

    # ------------------------------------------------------------------
    def _filtered_prospects(self):
        all_p = sorted(getattr(self.parent.league, 'draft_prospects', []) or [],
                       key=lambda p: getattr(p, 'draft_ranking', 0), reverse=True)
        ft = self.filter_var.get()
        from game_classes import PlayerPosition
        if ft == "Forwards":
            all_p = [p for p in all_p if p.primary_position in
                     (PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                      PlayerPosition.RIGHT_WING)]
        elif ft == "Defensemen":
            all_p = [p for p in all_p if p.primary_position in
                     (PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
                      PlayerPosition.DEFENSE)]
        elif ft == "Goalies":
            all_p = [p for p in all_p
                     if p.primary_position == PlayerPosition.GOALIE]
        elif ft == "Top 50":
            all_p = all_p[:50]
        elif ft == "Not Scouted":
            reports = self.parent.user_team.scouting_reports
            all_p = [p for p in all_p if p.id not in reports]
        q = self.search_var.get().lower().strip()
        if q:
            all_p = [p for p in all_p if q in p.full_name.lower()]
        return all_p

    def _set_prospect_filter(self, value):
        self.filter_var.set(value)
        self._paint_prospect_pills()
        self._refresh_prospects()

    def _paint_prospect_pills(self):
        current = self.filter_var.get()
        for value, btn in getattr(self, '_prospect_pills', {}).items():
            btn.set_selected(value == current)

    def _refresh_prospects(self):
        tree = self.prospects_tree
        tree.delete(*tree.get_children())
        tm = self.parent.tree_maps.setdefault(tree, {})
        reports = self.parent.user_team.scouting_reports
        assigns = getattr(self.parent, 'scouting_assignments', {})
        for i, p in enumerate(self._filtered_prospects()[:400]):
            report = reports.get(p.id)
            if report:
                pot = self.scmod.report_potential_display(report, p)
                status = f"Scouted ({getattr(report, 'accuracy', '?')})"
                top_grade = pot.split("–")[-1].strip()
            elif p in assigns:
                pot = self.scmod.consensus_range(p)
                status = "In progress"
                top_grade = pot.split("–")[-1].strip()
            else:
                pot = self.scmod.consensus_range(p)
                status = "—"
                top_grade = pot.split("–")[-1].strip()
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            tag = f"pot_{top_grade}" if top_grade in self.scmod.GRADE_ORDER else ""
            item = tree.insert('', 'end', values=(
                i + 1, p.full_name, pos, p.age,
                getattr(p, 'nationality', '?'), pot, status),
                tags=(tag,) if tag else ())
            tm[item] = p

    def _on_prospect_selected(self, event=None):
        sel = self.prospects_tree.selection()
        tm = self.parent.tree_maps.get(self.prospects_tree, {})
        self.selected_prospect = tm.get(sel[0]) if sel else None
        self._show_report()

    def _show_report(self):
        p = self.selected_prospect
        if p is None:
            return
        reports = self.parent.user_team.scouting_reports
        report = reports.get(p.id)
        try:
            pos = p.primary_position.value
        except Exception:
            pos = "?"
        self.rep_title.config(
            text=f"{p.full_name}  ·  {pos}  ·  {p.age}  ·  {getattr(p, 'nationality', '?')}")
        if report:
            pot = self.scmod.report_potential_display(report, p)
            top = pot.split("–")[-1].strip()
            self.rep_pot.config(text=f"Potential: {pot}",
                                foreground=self.scmod.grade_color(top))
            info = self.scmod.report_summary(report)
            self.rep_meta.config(
                text=f"Report accuracy {info['accuracy']}  ·  {info['viewings']} viewings  ·  "
                     f"Scout: {info['scout']}  ·  Region: {info['region']}")
            self.rep_strengths.config(
                text="\n".join(f"• {s}" for s in info['strengths']) or "—")
            self.rep_weak.config(
                text="\n".join(f"• {w}" for w in info['weaknesses']) or "—")
            notes = []
            if info['comparable'] != '—':
                notes.append(f"Comparable: {info['comparable']}")
            if info['projection'] != '—':
                notes.append(f"ETA: {info['projection']}")
            if info['notes']:
                notes.append(info['notes'][:220])
            self.rep_notes.config(text="   ".join(notes))
        else:
            pot = self.scmod.consensus_range(p)
            top = pot.split("–")[-1].strip()
            self.rep_pot.config(text=f"Potential: {pot}  (consensus — scout for certainty)",
                                foreground=self.scmod.grade_color(top))
            assigned = p in getattr(self.parent, 'scouting_assignments', {})
            self.rep_meta.config(
                text="No report yet — " +
                     ("a scout is watching." if assigned else "assign a scout or a region."))
            self.rep_strengths.config(text="—")
            self.rep_weak.config(text="—")
            self.rep_notes.config(text="")

    def _assign_scout_to_prospect(self):
        p = self.selected_prospect
        if p is None:
            messagebox.showwarning("No Prospect", "Select a prospect first.")
            return
        scout = self.selected_scout
        if scout is None:
            from game_classes import StaffRole
            scouts = [s for s in self.parent.user_team.staff
                      if self.scmod.is_scout(s)]
            if not scouts:
                messagebox.showwarning("No Scouts", "Hire a scout first.")
                return
            scout = scouts[0]
        assigns = self.parent.scouting_assignments
        if p in assigns:
            messagebox.showinfo("Already Assigned", "This prospect is already being scouted.")
            return
        if len(assigns) >= 30:
            messagebox.showwarning("Limit", "You have 30 active assignments already.")
            return
        assigns[p] = scout
        messagebox.showinfo("Assignment Started",
                            f"{scout.full_name} will scout {p.full_name}.")
        self._refresh_assignments()
        self._refresh_prospects()
        self._show_report()

    # ------------------------------------------------------------------
    def _refresh_board(self):
        lb = self.board_list
        lb.delete(0, tk.END)
        ids = self.scmod.get_draft_board(self.parent.user_team)
        by_id = {p.id: p for p in
                 getattr(self.parent.league, 'draft_prospects', []) or []}
        # prune missing
        ids = [i for i in ids if i in by_id]
        self.scmod.set_draft_board(self.parent.user_team, ids)
        for n, pid in enumerate(ids, 1):
            p = by_id[pid]
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            lb.insert(tk.END, f"{n}. {p.full_name} ({pos})")

    def _add_prospect_to_board(self):
        p = self.selected_prospect
        if p is None:
            return
        ids = self.scmod.get_draft_board(self.parent.user_team)
        if p.id not in ids:
            ids.append(p.id)
            self.scmod.set_draft_board(self.parent.user_team, ids)
            self._refresh_board()

    def _move_board(self, direction):
        lb = self.board_list
        sel = lb.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + direction
        ids = self.scmod.get_draft_board(self.parent.user_team)
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            self.scmod.set_draft_board(self.parent.user_team, ids)
            self._refresh_board()
            lb.select_set(j)

    def _remove_board(self):
        lb = self.board_list
        sel = lb.curselection()
        if not sel:
            return
        ids = self.scmod.get_draft_board(self.parent.user_team)
        del ids[sel[0]]
        self.scmod.set_draft_board(self.parent.user_team, ids)
        self._refresh_board()

    def _reset_board(self):
        prospects = sorted(getattr(self.parent.league, 'draft_prospects', []) or [],
                           key=lambda p: getattr(p, 'draft_ranking', 0),
                           reverse=True)[:50]
        self.scmod.set_draft_board(self.parent.user_team, [p.id for p in prospects])
        self._refresh_board()


class DraftWindow(ctk.CTkToplevel):
    """Draft night war room: live board, ticker, shortlist, draft-day trades, grades."""

    # Map any potential-grade variant onto a draft_night.grade_color key.
    _GRADE_BASE = {'A+': 'A+', 'A': 'A', 'A-': 'A', 'B+': 'B+', 'B': 'B',
                   'B-': 'B', 'C+': 'C', 'C': 'C', 'C-': 'C',
                   'D+': 'D', 'D': 'D', 'D-': 'D', 'F': 'F'}

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()
        super().__init__(parent)
        self.parent = parent
        self.title("NHL Entry Draft")
        self.geometry("1280x800")
        self.configure(fg_color=BG)

        # Slim branded banner strip (decorative; never breaks the window)
        try:
            from branding import SlimBanner
            SlimBanner(self, 'draft_banner.png', height=84,
                       bg=BG).pack(fill='x', padx=10, pady=(10, 0))
        except Exception:
            pass

        import draft_night as dn
        import scouting as scmod
        import trade_engine as te
        self.dn = dn
        self.scmod = scmod
        self.te = te

        self.current_round = 1
        self.total_rounds = 7
        self.current_pick = 0
        self.draft_order = []          # [round, team, draft_pick]
        self.picks_made = []           # (team_name, overall, player)
        self.selected_prospect = None
        self.strategy_var = tk.StringVar(master=self, value="BPA")
        self.pos_filter_var = tk.StringVar(master=self, value="All Positions")
        self._ai_after_id = None

        ct = self._ct

        # ---- Header ----
        header = ctk.CTkFrame(self, fg_color=ct['PANEL'], corner_radius=10)
        header.pack(fill='x', padx=10, pady=(10, 0))
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side='left', padx=14, pady=10)
        self._heading(title_box, text="NHL Entry Draft", size=18).pack(anchor='w')
        self.draft_status_label = self._body(title_box, text="Draft Night", dim=True)
        self.draft_status_label.pack(anchor='w')
        # On-the-clock spotlight
        self.clock_frame = ctk.CTkFrame(header, fg_color=ct['CARD'],
                                       corner_radius=10)
        self.clock_frame.pack(side='right', padx=14, pady=10)
        ctk.CTkLabel(self.clock_frame, text="ON THE CLOCK",
                     font=("Segoe UI", 9, 'bold'),
                     text_color=ct['TEXT_DIM']).pack(pady=(8, 0), padx=16)
        self.clock_label = ctk.CTkLabel(self.clock_frame, text="—",
                                       font=("Segoe UI", 15, 'bold'),
                                       text_color=ct['TEXT'])
        self.clock_label.pack(padx=16)
        self.pick_info_label = self._body(self.clock_frame, text="", dim=True)
        self.pick_info_label.pack(padx=16, pady=(0, 8))

        # ---- 3 columns (grid; CTk has no PanedWindow) ----
        main_pane = ctk.CTkFrame(self, fg_color="transparent")
        main_pane.pack(fill='both', expand=True, padx=10, pady=8)
        main_pane.grid_columnconfigure(0, weight=2)
        main_pane.grid_columnconfigure(1, weight=1)
        main_pane.grid_columnconfigure(2, weight=1)
        main_pane.grid_rowconfigure(0, weight=1)

        # LEFT: draft board
        left = ctk.CTkFrame(main_pane, fg_color=ct['PANEL'], corner_radius=10)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 4))
        ctk.CTkLabel(left, text="DRAFT BOARD",
                     font=("Segoe UI", 10, 'bold'),
                     text_color=ct['TEXT_DIM']).pack(anchor='w',
                                                     padx=12, pady=(10, 4))
        self._setup_tree_style()
        board_card = ctk.CTkFrame(left, fg_color=ct['CARD'], corner_radius=8)
        board_card.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.draft_results_tree = self._create_draft_board(board_card)

        # CENTER: war room
        center = ctk.CTkFrame(main_pane, fg_color=ct['PANEL'], corner_radius=10)
        center.grid(row=0, column=1, sticky='nsew', padx=4)
        ctk.CTkLabel(center, text="WAR ROOM",
                     font=("Segoe UI", 10, 'bold'),
                     text_color=ct['TEXT_DIM']).pack(anchor='w',
                                                     padx=12, pady=(10, 4))
        self.next_pick_label = ctk.CTkLabel(center, text="",
                                            font=("Segoe UI", 11, 'bold'),
                                            text_color=ct['TEXT'])
        self.next_pick_label.pack(anchor='w', padx=12, pady=(0, 4))

        # Strategy pills (PillButton is canvas-drawn: needs a plain tk parent
        # for its bg lookup, so each row gets a tk.Frame wrapper tinted to
        # match the panel)
        self._draft_pill_groups = []
        strat_row = ctk.CTkFrame(center, fg_color="transparent")
        strat_row.pack(fill='x', padx=12, pady=(0, 4))
        ctk.CTkLabel(strat_row, text="Strategy:",
                     font=("Segoe UI", 10, 'bold'),
                     text_color=ct['TEXT_DIM'], width=70,
                     anchor="w").pack(side='left', padx=(0, 6))
        strat_wrap = tk.Frame(strat_row, bg=ct['PANEL'])
        strat_wrap.pack(side='left')
        strat_btns = make_pill_group(
            strat_wrap,
            [("BPA", "Best Available"), ("Need", "Positional Need")],
            lambda v: self._draft_set_pill(self.strategy_var, v))
        self._draft_pill_groups.append((self.strategy_var, strat_btns))

        filt_row = ctk.CTkFrame(center, fg_color="transparent")
        filt_row.pack(fill='x', padx=12, pady=(0, 4))
        ctk.CTkLabel(filt_row, text="Show:",
                     font=("Segoe UI", 10, 'bold'),
                     text_color=ct['TEXT_DIM'], width=70,
                     anchor="w").pack(side='left', padx=(0, 6))
        filt_wrap = tk.Frame(filt_row, bg=ct['PANEL'])
        filt_wrap.pack(side='left')
        filt_btns = make_pill_group(
            filt_wrap,
            [("All Positions", "All"), ("Forwards", "Forwards"),
             ("Defensemen", "Defense"), ("Goalies", "Goalies")],
            lambda v: self._draft_set_pill(self.pos_filter_var, v))
        self._draft_pill_groups.append((self.pos_filter_var, filt_btns))
        self._draft_paint_pills()

        ctk.CTkLabel(center, text="SHORTLIST",
                     font=("Segoe UI", 10, 'bold'),
                     text_color=ct['TEXT_DIM']).pack(anchor='w',
                                                     padx=12, pady=(4, 2))
        self.shortlist = tk.Listbox(center, height=14, activestyle='none',
                                    bg=ct['CARD'], fg=ct['TEXT'],
                                    selectbackground=ct['ROW_SELECTED'],
                                    relief='flat',
                                    highlightthickness=1,
                                    highlightbackground=ct['BORDER'])
        self.shortlist.pack(fill='x', padx=12, pady=(0, 4))
        self.shortlist.bind('<<ListboxSelect>>', self._on_shortlist_select)

        self.selected_label = self._body(center, text="No prospect selected",
                                   dim=True)
        self.selected_label.configure(wraplength=300)
        self.selected_label.pack(anchor='w', padx=12, pady=(0, 6))

        btn_col = ctk.CTkFrame(center, fg_color="transparent")
        btn_col.pack(fill='x', padx=12, pady=(0, 10))
        self.draft_button = self._primary_button(btn_col, text="Draft Selected",
                                           command=self.make_user_pick)
        self.draft_button.pack(fill='x', pady=2)
        self.auto_button = self._secondary_button(btn_col,
                                            text="Auto Pick (My Board)",
                                            command=self.auto_pick)
        self.auto_button.pack(fill='x', pady=2)
        self.trade_pick_button = self._secondary_button(btn_col,
                                                  text="Trade This Pick",
                                                  command=self.trade_current_pick)
        self.trade_pick_button.pack(fill='x', pady=2)

        # RIGHT: ticker
        right = ctk.CTkFrame(main_pane, fg_color=ct['PANEL'], corner_radius=10)
        right.grid(row=0, column=2, sticky='nsew', padx=(4, 0))
        ctk.CTkLabel(right, text="DRAFT TICKER",
                     font=("Segoe UI", 10, 'bold'),
                     text_color=ct['TEXT_DIM']).pack(anchor='w',
                                                     padx=12, pady=(10, 4))
        ticker_card = ctk.CTkFrame(right, fg_color=ct['CARD'], corner_radius=8)
        ticker_card.pack(fill='both', expand=True, padx=10, pady=(0, 6))
        self.ticker = tk.Listbox(ticker_card, activestyle='none',
                                 bg=ct['CARD'], fg=ct['TEXT_DIM'],
                                 relief='flat', height=30,
                                 highlightthickness=0)
        self.ticker.pack(fill='both', expand=True, padx=8, pady=8)
        self.grades_button = self._secondary_button(right, text="Draft Grades",
                                              command=self.show_grades,
                                              state='disabled')
        self.grades_button.pack(fill='x', padx=10, pady=(0, 10))

        self.start_draft()

    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """Dark, flat styling for the draft board (styled ttk.Treeview, per
        the migration guide -- the board carries sortable columns)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Draft.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=28,
                        font=('Segoe UI', 10))
        style.configure('Draft.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Draft.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('Draft.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('Draft.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Draft.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])

    def _create_draft_board(self, parent):
        """Dark-styled draft board table inside a rounded card."""
        ct = self._ct
        columns = {'pick': ('#', 40), 'team': ('Team', 130),
                   'player': ('Player', 150), 'pos': ('Pos', 40),
                   'pot': ('Pot', 60)}
        tree = ttk.Treeview(parent, columns=list(columns.keys()),
                            show='headings', style='Draft.Treeview',
                            height=30)
        for col, (text, width) in columns.items():
            tree.heading(col, text=text,
                         command=lambda c=col, t=tree:
                         self.parent._sort_treeview_generic(t, c))
            tree.column(col, width=width, anchor='center')
        # Potential-grade row colors (same scale as the other CTk screens)
        for g in ('A+', 'A', 'B+', 'B', 'C', 'D', 'F'):
            tree.tag_configure(f"pot_{g}",
                               foreground=self.dn.grade_color(g))
        self.parent._bind_player_context_menu(tree, 'default', False)
        v_scroll = ttk.Scrollbar(parent, orient="vertical",
                                 command=tree.yview,
                                 style='Draft.Vertical.TScrollbar')
        tree.configure(yscrollcommand=v_scroll.set)
        tree.pack(side="left", fill="both", expand=True,
                  padx=(10, 0), pady=10)
        v_scroll.pack(side="right", fill="y", padx=(0, 6), pady=10)
        return tree

    def _pot_color(self, grade):
        """Foreground color for a potential grade (A+ green ... F red)."""
        g = (str(grade) if grade is not None else 'C').strip()
        return self.dn.grade_color(self._GRADE_BASE.get(g, 'C'))

    # ------------------------------------------------------------------
    def start_draft(self):
        # Make sure every team owns its picks (idempotent if already done)
        try:
            self.parent.league.initialize_all_draft_picks()
        except Exception:
            pass
        current_year = self.parent.league.season_year
        self.draft_order = []
        try:
            order = self.parent.league.get_draft_order(current_year)
        except Exception:
            order = []
        for overall_pick, team, draft_pick in order:
            try:
                draft_pick.overall_pick = overall_pick
            except Exception:
                pass
            self.draft_order.append([draft_pick.round, team, draft_pick])
        if not self.draft_order:
            standings = getattr(self.parent.league, 'standings', None) or {}
            sorted_teams = sorted(
                self.parent.league.teams,
                key=lambda t: standings.get(t.team_name, {}).get('Points', 0))
            for round_num in range(1, self.total_rounds + 1):
                for team in sorted_teams:
                    self.draft_order.append([round_num, team, None])
        self.current_pick = 0
        self.picks_made = []
        self.draft_results_tree.delete(*self.draft_results_tree.get_children())
        self.ticker.delete(0, tk.END)
        self._ticker("Welcome to draft night. The floor is buzzing.")
        self._refresh_shortlist()
        self.process_draft_pick()

    # ------------------------------------------------------------------
    def _ticker(self, line):
        self.ticker.insert(0, line)
        if self.ticker.size() > 120:
            self.ticker.delete(120, tk.END)

    def _available_prospects(self):
        return sorted(self.parent.league.draft_prospects,
                      key=lambda p: getattr(p, 'draft_ranking', 0), reverse=True)

    def _board_sorted_available(self):
        """Available prospects ordered by the user's draft board, then consensus."""
        avail = self._available_prospects()
        rank = self.scmod.board_rank_map(self.parent.user_team)
        if not rank:
            return avail
        return sorted(avail, key=lambda p: rank.get(p.id, 10_000 + getattr(p, 'draft_ranking', 0) * -1))

    def _draft_set_pill(self, var, value):
        var.set(value)
        self._draft_paint_pills()
        self._refresh_shortlist()

    def _draft_paint_pills(self):
        for var, btns in getattr(self, '_draft_pill_groups', []):
            current = var.get()
            for value, btn in btns.items():
                btn.set_selected(value == current)

    def _refresh_shortlist(self):
        self.shortlist.delete(0, tk.END)
        self._shortlist_players = []
        filt = self.pos_filter_var.get()
        from game_classes import PlayerPosition
        reports = self.parent.user_team.scouting_reports
        count = 0
        for p in self._board_sorted_available():
            if filt == "Forwards" and p.primary_position not in (
                    PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                    PlayerPosition.RIGHT_WING):
                continue
            if filt == "Defensemen" and p.primary_position not in (
                    PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
                    PlayerPosition.DEFENSE):
                continue
            if filt == "Goalies" and p.primary_position != PlayerPosition.GOALIE:
                continue
            report = reports.get(p.id)
            pot = (self.scmod.report_potential_display(report, p) if report
                   else self.scmod.consensus_range(p))
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            idx = self.shortlist.size()
            self.shortlist.insert(tk.END, f"{p.full_name}  ({pos})  {pot}")
            self.shortlist.itemconfig(
                idx, foreground=self._pot_color(
                    getattr(p, 'potential_grade', 'C')))
            self._shortlist_players.append(p)
            count += 1
            if count >= 30:
                break

    def _on_shortlist_select(self, event=None):
        sel = self.shortlist.curselection()
        if not sel:
            return
        p = self._shortlist_players[sel[0]]
        self.selected_prospect = p
        reports = self.parent.user_team.scouting_reports
        report = reports.get(p.id)
        pot = (self.scmod.report_potential_display(report, p) if report
               else self.scmod.consensus_range(p) + " (consensus)")
        try:
            pos = p.primary_position.value
        except Exception:
            pos = "?"
        self.selected_label.configure(
            text=f"Selected: {p.full_name} ({pos}, {p.age}) — Potential {pot}")

    # ------------------------------------------------------------------
    def process_draft_pick(self):
        if self.current_pick >= len(self.draft_order):
            self.end_draft()
            return
        round_num, team_on_clock, _dp = self.draft_order[self.current_pick]
        if round_num != self.current_round:
            self.current_round = round_num
        overall = self.current_pick + 1
        pick_in_round = (self.current_pick %
                         max(1, len(self.parent.league.teams))) + 1

        self.draft_status_label.configure(
            text=f"Round {round_num} of {self.total_rounds}")
        self.clock_label.configure(text=team_on_clock.team_name)
        self.pick_info_label.configure(
            text=f"Pick #{overall}  (Round {round_num}, #{pick_in_round} in round)")

        is_user = team_on_clock == self.parent.user_team
        state = 'normal' if is_user else 'disabled'
        self.draft_button.configure(state=state)
        self.auto_button.configure(state=state)
        self.trade_pick_button.configure(state=state)

        # Your next pick info
        nxt = next((i for i in range(self.current_pick, len(self.draft_order))
                    if self.draft_order[i][1] == self.parent.user_team), None)
        if nxt is not None:
            r = self.draft_order[nxt][0]
            self.next_pick_label.configure(
                text=f"Your next pick: #{nxt + 1} (Round {r})")
        else:
            self.next_pick_label.configure(text="No picks remaining")

        if not is_user:
            if self._ai_after_id:
                try:
                    self.after_cancel(self._ai_after_id)
                except Exception:
                    pass
            self._ai_after_id = self.after(650, self.ai_make_pick)

    def ai_make_pick(self):
        self._ai_after_id = None
        if self.current_pick >= len(self.draft_order):
            return
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        available = self._available_prospects()
        if not available:
            self.end_draft()
            return
        needs = self.te.team_needs(team_on_clock)
        # Consider top 12, weigh positional need + randomness
        candidates = available[:12]
        round_num = self.draft_order[self.current_pick][0]
        scored = []
        for p in candidates:
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            base = getattr(p, 'draft_ranking', 0)
            if pos in needs[:2]:
                base *= 1.08
            if pos == 'G' and round_num <= 1:
                base *= 0.80  # goalies rarely go top-10
            base *= random.uniform(0.94, 1.06)
            scored.append((base, p))
        scored.sort(key=lambda s: s[0], reverse=True)
        selected = scored[0][1]
        # Reach / steal detection for the ticker
        idx = available.index(selected)
        self.execute_pick(team_on_clock, selected,
                          reach=idx >= 8, steal=idx == 0 and self.current_pick >= 4)

    def make_user_pick(self):
        if not self.selected_prospect:
            messagebox.showwarning("No Prospect", "Select a prospect from the shortlist.")
            return
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        if team_on_clock != self.parent.user_team:
            return
        p = self.selected_prospect
        if p not in self.parent.league.draft_prospects:
            messagebox.showwarning("Unavailable", "That prospect was already drafted.")
            self._refresh_shortlist()
            return
        if not messagebox.askyesno("Confirm Pick",
                                   f"Draft {p.full_name}?\nThis cannot be undone."):
            return
        self.execute_pick(team_on_clock, p)

    def auto_pick(self):
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        if team_on_clock != self.parent.user_team:
            return
        available = self._board_sorted_available()
        if not available:
            return
        if self.strategy_var.get() == "Need":
            needs = self.te.team_needs(self.parent.user_team)
            pick = None
            for p in available[:8]:
                try:
                    pos = p.primary_position.value
                except Exception:
                    pos = "?"
                if pos in needs[:3]:
                    pick = p
                    break
            selected = pick or available[0]
        else:
            selected = available[0]
        self.execute_pick(team_on_clock, selected)

    def execute_pick(self, team, player, reach=False, steal=False):
        round_num, _t, _dp = self.draft_order[self.current_pick]
        overall = self.current_pick + 1
        team.add_player(player, "prospects")
        try:
            self.parent.league.draft_prospects.remove(player)
        except ValueError:
            pass
        try:
            pos = player.primary_position.value
        except Exception:
            pos = "?"
        pot_grade = self._GRADE_BASE.get(
            str(getattr(player, 'potential_grade', 'C')).strip(), 'C')
        self.draft_results_tree.insert('', 0, values=(
            overall, team.team_name, player.full_name, pos,
            getattr(player, 'potential_grade', '?')),
            tags=(f"pot_{pot_grade}",))
        self._ticker(self.dn.ticker_line(overall, team.team_name, player,
                                         round_num, reach=reach, steal=steal))
        self.picks_made.append((team.team_name, overall, player))
        try:
            self.parent.news_log.append({
                'date': self.parent.current_date, 'type': 'draft',
                'story': f"With pick #{overall}, the {team.team_name} select "
                         f"{player.full_name} ({pos})."})
        except Exception:
            pass
        self.current_pick += 1
        self.selected_prospect = None
        self.selected_label.configure(text="No prospect selected")
        self._refresh_shortlist()
        # Keep the board scrolled to the newest pick
        kids = self.draft_results_tree.get_children()
        if kids:
            self.draft_results_tree.see(kids[0])
        self.process_draft_pick()

    # ------------------------------------------------------------------
    def trade_current_pick(self):
        """Draft-day trade: swap your current pick with a partner's pick."""
        ct = self._ct
        if self.current_pick >= len(self.draft_order):
            return
        _r, team_on_clock, user_pick = self.draft_order[self.current_pick]
        if team_on_clock != self.parent.user_team:
            messagebox.showinfo("Not Your Pick", "You can only trade your own pick.")
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Trade this pick")
        dlg.geometry("480x460")
        dlg.configure(fg_color=ct['BG'])
        dlg.transient(self)
        overall = self.current_pick + 1
        self._heading(dlg, text=f"Your pick: #{overall} (Round {_r})",
                size=13).pack(pady=(14, 4))
        self._body(dlg, text="Select a partner and one of their upcoming picks:",
             dim=True).pack(pady=(0, 8))

        teams = sorted(t.team_name for t in self.parent.league.teams
                       if t != self.parent.user_team)

        def _partner_picks(name):
            team = next((t for t in self.parent.league.teams
                         if t.team_name == name), None)
            out = []
            for i in range(self.current_pick + 1, len(self.draft_order)):
                r, t, dp = self.draft_order[i]
                if t == team and dp is not None:
                    out.append((i, dp, r))
            return team, out

        def _store():
            dlg._picks = _partner_picks(combo.get())[1]

        def _refresh_lb(_value=None):
            lb.delete(0, tk.END)
            _t, picks = _partner_picks(combo.get())
            for i, dp, r in picks:
                val = self.te.pick_trade_value(dp)
                lb.insert(tk.END, f"#{i + 1} (Round {r}) — value {val}")
            _store()

        dlg._picks = []
        combo = ctk.CTkComboBox(dlg, values=teams, state='readonly',
                                width=280, command=_refresh_lb)
        combo.pack(pady=4)

        picks_card = ctk.CTkFrame(dlg, fg_color=ct['CARD'], corner_radius=8)
        picks_card.pack(fill='both', expand=True, padx=14, pady=6)
        lb = tk.Listbox(picks_card, height=10, bg=ct['CARD'], fg=ct['TEXT'],
                        selectbackground=ct['ROW_SELECTED'], relief='flat',
                        highlightthickness=0, activestyle='none')
        lb.pack(fill='both', expand=True, padx=8, pady=8)

        info = self._body(dlg, text="", dim=True)
        info.configure(wraplength=440, justify='center')
        info.pack(pady=4)

        def _update_info(event=None):
            sel = lb.curselection()
            if not sel or not dlg._picks:
                info.configure(text="")
                return
            i, dp, r = dlg._picks[sel[0]]
            uv = self.dn.pick_slot_value(overall)
            tv = self.dn.pick_slot_value(i + 1)
            if uv > tv:
                info.configure(text=f"You give #{overall} (slot value {uv}), "
                                     f"get #{i + 1} (slot value {tv}). They may want more.")
            elif tv > uv:
                info.configure(text=f"You give #{overall} (slot value {uv}), "
                                     f"get #{i + 1} (slot value {tv}). Good value for you.")
            else:
                info.configure(text="Even swap on paper.")

        lb.bind('<<ListboxSelect>>', _update_info)

        def _propose():
            sel = lb.curselection()
            if not sel or not dlg._picks:
                return
            j, partner_pick, _r2 = dlg._picks[sel[0]]
            partner = next(t for t in self.parent.league.teams
                           if t.team_name == combo.get())
            resp = self.te.ai_consider_trade(
                partner, [user_pick], [partner_pick],
                user_team=self.parent.user_team)
            if resp.decision == 'reject':
                messagebox.showerror("Rejected", resp.message)
                return
            if resp.decision == 'counter':
                extra = resp.want_added + resp.will_add
                detail = "; ".join(self.te.asset_label(a) for a in extra)
                if not messagebox.askyesno("Counter-offer",
                                           f"{resp.message}\n\nAccept?"):
                    return
                self._execute_pick_swap(j, user_pick, partner_pick,
                                        resp.want_added, resp.will_add)
            else:
                self._execute_pick_swap(j, user_pick, partner_pick, [], [])
            dlg.destroy()
            messagebox.showinfo("Trade Complete", "Pick swap completed.")
            self.process_draft_pick()

        self._primary_button(dlg, text="Propose Swap",
                       command=_propose).pack(pady=10)

    def _swap_pick_owner(self, draft_pick, new_team):
        """Point a draft pick (and its draft-order slot) at a new owner."""
        try:
            draft_pick.current_team = new_team.team_name
        except Exception:
            pass
        for entry in self.draft_order:
            if entry[2] is draft_pick:
                entry[1] = new_team

    def _execute_pick_swap(self, partner_idx, user_pick, partner_pick,
                           want_added, will_add):
        user_team = self.parent.user_team
        partner_team = self.draft_order[partner_idx][1]
        # Swap the picks
        self._swap_pick_owner(user_pick, partner_team)
        self._swap_pick_owner(partner_pick, user_team)
        # Move any extra assets
        for a in want_added:  # user gives more
            if self.te._is_pick(a):
                self._swap_pick_owner(a, partner_team)
            else:
                try:
                    user_team.remove_player(a)
                    partner_team.add_player(a)
                except Exception:
                    pass
        for a in will_add:  # partner sweetens
            if self.te._is_pick(a):
                self._swap_pick_owner(a, user_team)
            else:
                try:
                    partner_team.remove_player(a)
                    user_team.add_player(a)
                except Exception:
                    pass
        # History + news
        gm = getattr(self.parent, 'game_manager', None)
        summary = (f"{user_team.team_name} acquires pick "
                   f"#{partner_idx + 1} from {partner_team.team_name}.")
        if gm is not None:
            if not hasattr(gm, 'trade_history'):
                gm.trade_history = []
            gm.trade_history.append(self.te.CompletedTrade(
                str(getattr(gm, 'current_date', '')), user_team.team_name,
                partner_team.team_name,
                [self.te.asset_label(user_pick)],
                [self.te.asset_label(partner_pick)], summary))
        try:
            self.parent.add_news_story(f"DRAFT TRADE: {summary}")
        except Exception:
            pass
        self._ticker(f"TRADE: {summary}")

    # ------------------------------------------------------------------
    def show_grades(self):
        ct = self._ct
        grades = self.dn.draft_grades(self.picks_made)
        dlg = ctk.CTkToplevel(self)
        dlg.title("Draft Grades")
        dlg.geometry("420x540")
        dlg.configure(fg_color=ct['BG'])
        dlg.transient(self)
        self._heading(dlg, text="Draft Grades", size=16).pack(pady=14)
        grades_card = ctk.CTkFrame(dlg, fg_color=ct['CARD'], corner_radius=8)
        grades_card.pack(fill='both', expand=True, padx=14, pady=6)
        lb = tk.Listbox(grades_card, bg=ct['CARD'], fg=ct['TEXT'],
                        relief='flat', font=("Segoe UI", 11),
                        selectbackground=ct['ROW_SELECTED'],
                        highlightthickness=0, activestyle='none')
        lb.pack(fill='both', expand=True, padx=8, pady=8)
        user_grade = None
        for team, grade, ratio in grades:
            lb.insert(tk.END, f"  {grade}   {team}")
            lb.itemconfig(tk.END, foreground=self._pot_color(grade))
            if team == self.parent.user_team.team_name:
                user_grade = grade
        if user_grade:
            ug = ctk.CTkLabel(dlg, text=f"Your draft grade: {user_grade}",
                              font=("Segoe UI", 13, 'bold'),
                              text_color=self._pot_color(user_grade))
            ug.pack(pady=10)

    def end_draft(self):
        if self._ai_after_id:
            try:
                self.after_cancel(self._ai_after_id)
            except Exception:
                pass
        self._ai_after_id = None
        self.draft_status_label.configure(text="Draft Complete")
        self.clock_label.configure(text="—")
        self.pick_info_label.configure(text="All 7 rounds complete")
        self.draft_button.configure(state='disabled')
        self.auto_button.configure(state='disabled')
        self.trade_pick_button.configure(state='disabled')
        self.grades_button.configure(state='normal')
        self._ticker("That's a wrap on draft night.")
        self.show_grades()


class ScheduleWindow(ctk.CTkToplevel):
    """League Schedule (CustomTkinter): tabbed My Team / League tables,
    month-filter combo, color-coded game rows (win/loss/today), modern
    action buttons. All schedule logic preserved."""

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()
        super().__init__(parent)
        self.parent = parent
        self.title("League Schedule")
        self.configure(fg_color=BG)
        self.geometry("1000x750")
        self.minsize(900, 650)

        ct = self._ct
        main_container = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Header card: title + my-team record/legend
        header = ctk.CTkFrame(main_container, fg_color=ct['CARD'], corner_radius=12)
        header.pack(fill="x", pady=(0, 12))
        heading(header, "League Schedule", size=20).pack(side="left", padx=16, pady=12)
        self.my_sched_header = body(header, "", size=12, dim=True)
        self.my_sched_header.pack(side="left", padx=8, pady=12)

        # Month filter card
        filter_frame = ctk.CTkFrame(main_container, fg_color=ct['PANEL'],
                                    corner_radius=10)
        filter_frame.pack(fill="x", pady=(0, 12))
        body(filter_frame, "Month:", size=12, dim=True).pack(
            side="left", padx=(14, 6), pady=10)
        self.month_filter = tk.StringVar(master=self, value='All')
        self.month_combo = ctk.CTkComboBox(
            filter_frame,
            values=['All'],
            command=self._on_month_selected,
            width=160,
            fg_color=ct['CARD'],
            button_color=ct['CARD'],
            button_hover_color=ct['BORDER'],
            dropdown_fg_color=ct['CARD'],
            dropdown_hover_color=ct['BORDER'],
            dropdown_text_color=ct['TEXT'],
            text_color=ct['TEXT'],
            border_color=ct['BORDER'],
            border_width=1,
            corner_radius=8,
        )
        self.month_combo.pack(side="left", pady=10)
        self.month_combo.set('All')

        # Tabs: My Team Schedule / League Schedule
        self.tabview = ctk.CTkTabview(
            main_container,
            fg_color=ct['PANEL'],
            corner_radius=12,
            border_width=1,
            border_color=ct['BORDER'],
            segmented_button_fg_color=ct['PANEL'],
            segmented_button_selected_color=ct['TEAL'],
            segmented_button_selected_hover_color=ct['TEAL_HOVER'],
            segmented_button_unselected_color=ct['CARD'],
            segmented_button_unselected_hover_color=ct['BORDER'],
        )
        self.tabview.pack(fill="both", expand=True, pady=(0, 12))
        self.tabview.add("My Team Schedule")
        self.tabview.add("League Schedule")

        columns = {'date': ('Date', 120), 'away': ('Away Team', 220),
                   'score': ('Score', 90), 'home': ('Home Team', 220),
                   'status': ('Status', 110)}

        my_team_frame = self.tabview.tab("My Team Schedule")
        self.my_schedule_tree = self._create_schedule_treeview(my_team_frame, columns, 25)
        self.my_schedule_tree.bind('<Double-1>', self.on_game_double_click)
        self.my_schedule_tree.bind('<Button-3>', self.show_game_context_menu)

        league_frame = self.tabview.tab("League Schedule")
        self.league_schedule_tree = self._create_schedule_treeview(league_frame, columns, 25)
        self.league_schedule_tree.bind('<Double-1>', self.on_game_double_click)
        self.league_schedule_tree.bind('<Button-3>', self.show_game_context_menu)

        # Action buttons
        self.create_action_buttons(main_container)

        # Store schedule data for game launching
        self.schedule_data = {}

        self._setup_tree_style()
        self.update_views()

    # ------------------------------------------------------------------
    # CTk styling helpers
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """Dark, flat styling for the schedule tables (styled ttk.Treeview,
        per the migration guide -- the tables carry 5 sortable columns and
        per-game color tags)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Schedule.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=30,
                        font=('Segoe UI', 10))
        style.configure('Schedule.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Schedule.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('Schedule.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('Schedule.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.configure('Schedule.Horizontal.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Schedule.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])
        style.map('Schedule.Horizontal.TScrollbar',
                  background=[('active', ct['BORDER'])])

        # Game-row color tags (applied to both tables)
        for tree in (self.my_schedule_tree, self.league_schedule_tree):
            tree.tag_configure('today', background=ct['ROW_SELECTED'],
                               foreground=ct['TEXT'])
            tree.tag_configure('completed', foreground=ct['TEXT_DIM'])
            tree.tag_configure('win', foreground=ct['GREEN'])
            tree.tag_configure('loss', foreground=ct['RED'])
            tree.tag_configure('upcoming', foreground=ct['TEXT'])

    def _create_schedule_treeview(self, parent, columns, height=25):
        """Dark-styled game table inside a rounded card."""
        ct = self._ct
        table_frame = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tree = ttk.Treeview(table_frame, columns=list(columns.keys()),
                            show='headings', style='Schedule.Treeview',
                            height=height)
        for col, (text, width) in columns.items():
            tree.heading(col, text=text,
                         command=lambda c=col, t=tree: self.parent._sort_treeview_generic(t, c))
            tree.column(col, width=width, anchor='center')

        v_scroll = ttk.Scrollbar(table_frame, orient="vertical",
                                 command=tree.yview,
                                 style='Schedule.Vertical.TScrollbar')
        h_scroll = ttk.Scrollbar(table_frame, orient="horizontal",
                                 command=tree.xview,
                                 style='Schedule.Horizontal.TScrollbar')
        tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        v_scroll.pack(side="right", fill="y", padx=(0, 6), pady=10)
        h_scroll.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        return tree

    def _on_month_selected(self, value):
        """Month combo callback: sync the filter var and rebuild the tables."""
        self.month_filter.set(value)
        self.update_views()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def create_action_buttons(self, parent):
        """Create action buttons for schedule operations."""
        ct = self._ct
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill='x', pady=(4, 0))

        # Watch Game button
        self.watch_game_btn = self._primary_button(
            button_frame,
            text="Watch Game",
            command=self.watch_selected_game,
        )
        self.watch_game_btn.pack(side='left', padx=(0, 10))

        # Simulate Game button
        self.simulate_game_btn = self._secondary_button(
            button_frame,
            text="Simulate Game",
            command=self.simulate_selected_game,
        )
        self.simulate_game_btn.pack(side='left', padx=(0, 10))

        # Refresh button
        self._secondary_button(
            button_frame,
            text="Refresh",
            command=self.update_views,
        ).pack(side='right')

    def on_game_double_click(self, event):
        """Handle double-click on a game - launch game viewer."""
        self.watch_selected_game()

    def show_game_context_menu(self, event):
        """Show context menu for game operations."""
        ct = self._ct
        tree = event.widget
        item = tree.identify_row(event.y)
        if not item:
            return

        menu = tk.Menu(self, tearoff=0, bg=ct['CARD'], fg=ct['TEXT'],
                       activebackground=ct['TEAL'], activeforeground=ct['BG'])
        menu.add_command(label="Watch Game", command=self.watch_selected_game)
        menu.add_command(label="Simulate Game", command=self.simulate_selected_game)
        menu.add_separator()
        menu.add_command(label="Game Stats", command=self.view_game_stats)
        menu.add_command(label="Game Recap", command=self.view_game_recap)

        menu.tk_popup(event.x_root, event.y_root)

    def get_selected_game_data(self):
        """Get data for the currently selected game.

        Looks the game up in self.schedule_data (built by update_views) using
        the selected row's date/team names, so it works regardless of the
        underlying schedule entry format (dict, tuple, or special events).
        """
        # Pick the treeview from the currently visible tab
        try:
            if self.tabview.get() == "League Schedule":
                tree = self.league_schedule_tree
            else:
                tree = self.my_schedule_tree
        except Exception:
            # Fallback to my team schedule
            tree = self.my_schedule_tree

        selection = tree.selection()
        if not selection:
            return None

        item = selection[0]
        values = tree.item(item, 'values')
        if not values or len(values) < 4:
            return None

        # Parse the selected game data
        date_str, away_team_name, score, home_team_name = values[:4]

        game_key = f"{date_str}_{home_team_name}_{away_team_name}"
        entry = self.schedule_data.get(game_key)
        if not entry:
            return None

        return {
            'date': entry['date'],
            'home_team': entry['home'],
            'away_team': entry['away'],
            'score': entry['score'],
            'status': entry['status'],
            'has_been_played': entry['status'] == "Final",
        }

    def watch_selected_game(self):
        """Launch the game viewer for the selected game."""
        game_data = self.get_selected_game_data()
        if not game_data:
            tk.messagebox.showwarning("No Game Selected", "Please select a game to watch.")
            return

        if game_data['has_been_played']:
            # Already played - watch the recorded result
            self._launch_game_viewer(game_data, commit=False)
            return

        # Game hasn't been played yet. Only past games can be simulated into
        # the season record; future games would be re-simmed by the season
        # engine on day advance (double-counting stats), so they are only
        # offered as a non-committing preview.
        try:
            is_past_game = game_data['date'] < self.parent.current_date
        except TypeError:
            is_past_game = False

        if is_past_game:
            response = tk.messagebox.askyesno(
                "Game Not Played",
                "This game hasn't been played yet.\n\n"
                "Would you like to simulate and watch it?\n"
                "(The result will be recorded in your season.)")
            if not response:
                return
            self._launch_game_viewer(game_data, commit=True)
        else:
            response = tk.messagebox.askyesno(
                "Future Game",
                "This game is scheduled for today or the future.\n\n"
                "Watch a preview simulation? It will not affect your season.")
            if not response:
                return
            self._launch_game_viewer(game_data, commit=False)

    def simulate_selected_game(self):
        """Simulate the selected game without watching.

        Only past games with no recorded result can be simulated here.
        Today's and future games are handled by the season simulation when
        advancing days; simulating them here would double-count results.
        """
        game_data = self.get_selected_game_data()
        if not game_data:
            tk.messagebox.showwarning("No Game Selected", "Please select a game to simulate.")
            return

        if game_data['has_been_played']:
            tk.messagebox.showinfo("Game Already Played", "This game has already been played.")
            return

        try:
            is_past_game = game_data['date'] < self.parent.current_date
        except TypeError:
            is_past_game = False

        if not is_past_game:
            tk.messagebox.showinfo(
                "Future Game",
                "This game is scheduled for today or the future.\n"
                "It will be played automatically when you advance the season.\n\n"
                "Manual simulation is only available for past games that "
                "were never played.")
            return

        # Simulate the game
        self._simulate_game(game_data)
        self.update_views()

    def _launch_game_viewer(self, game_data, commit=True):
        """Launch the game viewer for a specific game.

        Args:
            game_data: dict from get_selected_game_data()
            commit: if True and the game hasn't been played, the simulated
                result is recorded in the season (game_results + team stats).
                If False, the sim is a throwaway preview and nothing is stored.
        """
        try:
            from GAME_VIEWER import launch_game_viewer
            from simulation import GameSim

            home_team = game_data['home_team']
            away_team = game_data['away_team']

            if commit and not game_data['has_been_played']:
                # Simulate the game for viewing and record the result
                sim = GameSim(home_team, away_team)
                sim.run()

                game_result = self._build_game_result(game_data, sim)

                # Add to game results if not already there
                if not self._find_game_result(game_data):
                    self.parent.game_results.append(game_result)
                    self._update_team_stats_from_game(game_result)
                    self.update_views()

                event_log = game_result['event_log']
            else:
                # Watch the recorded game (or a throwaway preview sim for an
                # unplayed game) - never re-sim a played game's score.
                result = self._find_game_result(game_data)
                event_log = (result.get('event_log') if result else None) or []
                if not event_log:
                    sim = GameSim(home_team, away_team)
                    sim.run()
                    event_log = sim.event_log

            # launch_game_viewer(event_log, duration, home_team, away_team, parent)
            launch_game_viewer(event_log, 3600,
                               home_team.team_name, away_team.team_name,
                               parent=self)

        except Exception as e:
            tk.messagebox.showerror("Game Viewer Error",
                                    f"Failed to launch game viewer:\n{str(e)}")
            print(f"Game viewer launch error: {e}")

    def _build_game_result(self, game_data, sim):
        """Build a game_results-compatible result dict from a GameSim run.

        Includes the keys the rest of the app expects ('winner',
        'event_log', 'overtime', 'shootout', ...).
        """
        home_team = game_data['home_team']
        away_team = game_data['away_team']
        home_score = sim.home_score
        away_score = sim.away_score

        winner = home_team if home_score > away_score else away_team
        notable_events = getattr(sim, 'notable_events', []) or []
        went_ot = any(e.get('period', 0) > 3 for e in notable_events
                      if isinstance(e, dict))
        went_so = any(e.get('period', 0) == 5 for e in notable_events
                      if isinstance(e, dict))

        return {
            'date': game_data['date'],
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'winner': winner,
            'events': getattr(sim, 'game_log', []) or [],
            'notable_events': notable_events,
            'player_ratings': {},
            'event_log': getattr(sim, 'event_log', []) or [],
            'overtime': went_ot,
            'shootout': went_so,
        }

    def _simulate_game(self, game_data):
        """Simulate a game and store the results."""
        try:
            from simulation import GameSim

            home_team = game_data['home_team']
            away_team = game_data['away_team']

            # Create and run simulation
            sim = GameSim(home_team, away_team)
            sim.run()

            # Don't store a duplicate if one was recorded meanwhile
            if self._find_game_result(game_data):
                tk.messagebox.showinfo("Already Recorded",
                                       "A result for this game is already recorded.")
                self.update_views()
                return

            game_result = self._build_game_result(game_data, sim)

            # Add to game results
            self.parent.game_results.append(game_result)

            # Update team stats
            self._update_team_stats_from_game(game_result)

            # Show result
            tk.messagebox.showinfo("Game Simulated",
                                   f"Game Result:\n\n"
                                   f"{away_team.team_name} {sim.away_score} - {sim.home_score} {home_team.team_name}")

        except Exception as e:
            tk.messagebox.showerror("Simulation Error",
                                    f"Failed to simulate game:\n{str(e)}")

    def _update_team_stats_from_game(self, game_result):
        """Update team statistics from game result.

        Uses the canonical Team.update_record() (points is a computed
        property on Team, so it must never be assigned directly).
        """
        home_team = game_result['home_team']
        away_team = game_result['away_team']
        home_score = game_result['home_score']
        away_score = game_result['away_score']

        # Update goals for/against (guarded: not all Team objects carry these)
        home_team.goals_for = getattr(home_team, 'goals_for', 0) + home_score
        home_team.goals_against = getattr(home_team, 'goals_against', 0) + away_score
        away_team.goals_for = getattr(away_team, 'goals_for', 0) + away_score
        away_team.goals_against = getattr(away_team, 'goals_against', 0) + home_score

        # Update wins/losses (OT losers still earn a point via ot_losses)
        went_ot = bool(game_result.get('overtime') or game_result.get('shootout'))
        if home_score > away_score:
            home_team.update_record("WIN")
            away_team.update_record("LOSS", overtime=went_ot)
        elif away_score > home_score:
            away_team.update_record("WIN")
            home_team.update_record("LOSS", overtime=went_ot)
        else:
            # Ties shouldn't happen (GameSim resolves OT/shootout), but stay safe
            home_team.update_record("TIE")
            away_team.update_record("TIE")

    def _find_game_result(self, game_data):
        """Find the stored result matching the selected game."""
        for gr in self.parent.game_results:
            gd, grdate = game_data['date'], gr.get('date')
            same_day = (gd == grdate or
                        (hasattr(gd, 'date') and hasattr(grdate, 'date') and
                         gd.date() == grdate.date()))
            if (same_day and
                    gr.get('home_team') is game_data['home_team'] and
                    gr.get('away_team') is game_data['away_team']):
                return gr
        return None

    def view_game_stats(self):
        """View detailed stats for the selected game."""
        game_data = self.get_selected_game_data()
        if not game_data:
            tk.messagebox.showwarning("No Game Selected",
                                      "Please select a game first.")
            return
        result = self._find_game_result(game_data)
        if not result:
            tk.messagebox.showinfo("No Data",
                                   "This game hasn't been played yet — no stats available.")
            return
        GameDetailWindow(self.parent, result, initial_tab="stats")

    def view_game_recap(self):
        """View game recap and highlights."""
        game_data = self.get_selected_game_data()
        if not game_data:
            tk.messagebox.showwarning("No Game Selected",
                                      "Please select a game first.")
            return
        result = self._find_game_result(game_data)
        if not result:
            tk.messagebox.showinfo("No Data",
                                   "This game hasn't been played yet — no recap available.")
            return
        GameDetailWindow(self.parent, result, initial_tab="recap")

    @staticmethod
    def _parse_schedule_entry(game_entry):
        """Normalize one league.schedule entry to (date, home_team, away_team).

        Returns None for malformed entries and non-game special events
        (e.g. All-Star / NHL_EVENT entries).
        """
        game_date = home = away = None
        if isinstance(game_entry, dict):
            # New format: dictionary with date, home_team, away_team, etc.
            game_date = game_entry.get('date')
            home = game_entry.get('home_team')
            away = game_entry.get('away_team')
        elif isinstance(game_entry, (tuple, list)) and len(game_entry) >= 3:
            # Old format: tuple/list with (date, home_team, away_team)
            game_date, home, away = game_entry[0], game_entry[1], game_entry[2]
        else:
            return None

        # Skip special events (All-Star, outdoor games, etc.) - not real games
        if (game_date is None or not hasattr(game_date, 'strftime')
                or not (hasattr(home, 'team_name') and hasattr(away, 'team_name'))):
            return None
        return game_date, home, away

    def _parsed_schedule(self):
        """Schedule entries normalized to (date, home, away), parsed once.

        The raw league.schedule mixes dict and tuple formats and is
        re-scanned by several views; parse it once per schedule object and
        reuse. Rebuilds automatically when the schedule list is replaced
        (new season / load game).
        """
        src = self.parent.league.schedule
        if getattr(self, '_parsed_schedule_src', None) is not src:
            parsed = []
            for game_entry in src:
                entry = self._parse_schedule_entry(game_entry)
                if entry:
                    parsed.append(entry)
            self._parsed_schedule_cache = parsed
            self._parsed_schedule_src = src
        return self._parsed_schedule_cache

    def _schedule_months(self):
        """Month labels present in the schedule, in chronological order."""
        months = []
        seen = set()
        for game_date, home, away in self._parsed_schedule():
            try:
                label = game_date.strftime("%b %Y")
            except (AttributeError, ValueError):
                continue
            if label not in seen:
                seen.add(label)
                months.append(label)
        return months

    def _game_row_tag(self, home, away, score, status):
        """Color tag for a game row involving the user's team.

        'win' (green) / 'loss' (red) for decided games, 'today' for today's
        game, 'completed' (dimmed) for other past games, 'upcoming' otherwise.
        Returns '' for games not involving the user's team.
        """
        if self.parent.user_team not in (home, away):
            return ''
        row_tag = 'completed'
        if status == "Final" and "-" in score:
            try:
                a_s, h_s = (int(x) for x in score.split("-"))
                mine = h_s if home == self.parent.user_team else a_s
                theirs = a_s if home == self.parent.user_team else h_s
                row_tag = 'win' if mine > theirs else 'loss'
            except (ValueError, IndexError):
                row_tag = 'completed'
        elif status == "Today":
            row_tag = 'today'
        return row_tag

    def update_views(self):
        self.my_schedule_tree.delete(*self.my_schedule_tree.get_children())
        self.league_schedule_tree.delete(*self.league_schedule_tree.get_children())

        self.schedule_data.clear()
        self._first_upcoming = None

        # Month filter options
        month_values = ['All'] + self._schedule_months()
        self.month_combo.configure(values=month_values)
        if self.month_filter.get() not in month_values:
            self.month_filter.set('All')
            self.month_combo.set('All')
        selected_month = self.month_filter.get()

        for game_date, home, away in self._parsed_schedule():
            # Month filter
            try:
                if selected_month != 'All' and game_date.strftime("%b %Y") != selected_month:
                    continue
            except (AttributeError, ValueError):
                pass

            # Determine game status and score
            status = "Scheduled"
            score = "- : -"

            if game_date < self.parent.current_date:
                # O(1) result lookup via the app's matchup index (was a full
                # scan of game_results per scheduled game: O(games x results))
                game_result = self.parent.find_game_result(game_date, home, away)
                if game_result is not None:
                    score = f"{game_result['away_score']}-{game_result['home_score']}"
                    status = "Final"
                else:
                    score = "0-0"  # Fallback if no result found
                    status = "Simulated"
            elif game_date == self.parent.current_date:
                status = "Today"

            values = (game_date.strftime("%b %d, %Y"), away.team_name, score, home.team_name, status)

            # Store game data for easy access (keyed the same way
            # get_selected_game_data() looks it up: display date string +
            # team names)
            game_key = f"{game_date.strftime('%b %d, %Y')}_{home.team_name}_{away.team_name}"
            self.schedule_data[game_key] = {
                'date': game_date,
                'home': home,
                'away': away,
                'score': score,
                'status': status
            }

            # Color tag for games involving the user's team (win/loss/today)
            row_tag = self._game_row_tag(home, away, score, status)
            league_tags = (row_tag,) if row_tag else ()
            item_id = self.league_schedule_tree.insert('', 'end', values=values,
                                                       tags=league_tags)
            if self.parent.user_team in (home, away):
                my_item_id = self.my_schedule_tree.insert('', 'end', values=values,
                                                           tags=(row_tag,))
                if self._first_upcoming is None and status in ("Today", "Scheduled"):
                    self._first_upcoming = my_item_id

        if self._first_upcoming:
            self.my_schedule_tree.see(self._first_upcoming)
            self.my_schedule_tree.selection_set(self._first_upcoming)
        try:
            team = self.parent.user_team
            rec = f"{getattr(team, 'wins', 0)}-{getattr(team, 'losses', 0)}-{getattr(team, 'otl', getattr(team, 'ot_losses', 0))}"
            self.my_sched_header.configure(
                text=f"{team.team_name}  \u2022  {rec}  \u2022  Green = win, red = loss")
        except Exception:
            pass

        set_tree_empty_state(self.my_schedule_tree, "No games scheduled for your team")
        set_tree_empty_state(self.league_schedule_tree, "No league games scheduled")

class FinancesWindow(ctk.CTkToplevel):
    """Comprehensive financial management window with detailed breakdown and projections.

    Rebuilt with CustomTkinter (Sept 2026): CTkToplevel shell, CTkTabview
    tabs, CTkFrame stat cards, dark styled Treeviews, CTkComboBox year
    selector, CTkSegmentedButton report picker, pill filter rows, and a
    CTkProgressBar cap-utilization meter. All calculation and reporting
    logic is unchanged from the ttk version.
    """

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()
        super().__init__(parent)
        self.parent = parent
        self.title(f"{parent.user_team.team_name} - Financial Management")
        self.configure(fg_color=BG)
        self.geometry("1400x900")
        self.minsize(1200, 700)

        # Initialize data structures
        self.current_season = 2024
        self.selected_projection_year = tk.StringVar(master=self, value=str(self.current_season))

        # Create the interface
        self.create_interface()
        self._setup_tree_style()
        self.update_views()

        # Track window
        self.parent.open_windows['finances'] = self

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def create_interface(self):
        """Create the comprehensive financial interface."""
        ct = self._ct
        # Main container
        main_container = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Header section
        self.create_header_section(main_container)

        # Main tabbed interface (CTkTabview instead of ttk.Notebook)
        self.tabview = ctk.CTkTabview(
            main_container,
            fg_color=ct['PANEL'],
            corner_radius=12,
            border_width=1,
            border_color=ct['BORDER'],
            segmented_button_fg_color=ct['PANEL'],
            segmented_button_selected_color=ct['TEAL'],
            segmented_button_selected_hover_color=ct['TEAL_HOVER'],
            segmented_button_unselected_color=ct['CARD'],
            segmented_button_unselected_hover_color=ct['BORDER'],
            text_color=ct['TEXT'],
        )
        self.tabview.pack(fill="both", expand=True, pady=(16, 0))
        for name in ("Salary Cap", "Contracts", "Projections", "Management", "Reports"):
            self.tabview.add(name)

        # Salary Cap Overview tab
        self.create_salary_cap_tab(self.tabview.tab("Salary Cap"))

        # Player Contracts tab
        self.create_contracts_tab(self.tabview.tab("Contracts"))

        # Future Projections tab
        self.create_projections_tab(self.tabview.tab("Projections"))

        # Contract Management tab
        self.create_management_tab(self.tabview.tab("Management"))

        # Financial Reports tab
        self.create_reports_tab(self.tabview.tab("Reports"))

    def create_header_section(self, parent):
        """Create header with financial overview."""
        ct = self._ct
        header_frame = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12)
        header_frame.pack(fill="x", pady=(0, 4))

        top = ctk.CTkFrame(header_frame, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 4))

        # Title
        self._heading(top, text=f"{self.parent.user_team.team_name.upper()} FINANCIAL MANAGEMENT",
                      size=18).pack(side="left")

        # Quick stats on the right
        stats_frame = ctk.CTkFrame(top, fg_color="transparent")
        stats_frame.pack(side="right")

        # Calculate current financials
        current_payroll = self.calculate_current_payroll()
        salary_cap = self._salary_cap()
        cap_space = salary_cap - current_payroll

        cap_color = ct['GREEN'] if cap_space >= 0 else ct['RED']
        self.header_stats_label = ctk.CTkLabel(
            stats_frame,
            text=f"Cap Space: ${cap_space:,}  |  Payroll: ${current_payroll:,}  |  Cap: ${salary_cap:,}",
            font=("Segoe UI", 12, "bold"),
            text_color=cap_color,
        )
        self.header_stats_label.pack()

    def create_salary_cap_tab(self, cap_frame):
        """Create salary cap overview tab."""
        ct = self._ct

        # Top section - Cap overview
        overview_frame = ctk.CTkFrame(cap_frame, fg_color=ct['CARD'], corner_radius=12)
        overview_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(overview_frame, text="Salary Cap Overview",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        # Create overview grid
        overview_grid = ctk.CTkFrame(overview_frame, fg_color="transparent")
        overview_grid.pack(fill="x", padx=12, pady=12)

        # Configure grid columns
        for i in range(4):
            overview_grid.columnconfigure(i, weight=1)

        # Current payroll breakdown
        current_payroll = self.calculate_current_payroll()
        ahl_payroll = self.calculate_ahl_payroll()
        buried_salary = self.calculate_buried_salary()
        salary_cap = self._salary_cap()
        cap_space = salary_cap - current_payroll

        self.create_stat_box(overview_grid, "Current Payroll", f"${current_payroll:,}", 0, 0)
        self.create_stat_box(overview_grid, "Salary Cap", f"${salary_cap:,}", 0, 1)
        self.create_stat_box(overview_grid, "Cap Space", f"${cap_space:,}", 0, 2,
                             color='green' if cap_space >= 0 else 'red')
        self.create_stat_box(overview_grid, "AHL Payroll", f"${ahl_payroll:,}", 0, 3)

        # Cap utilization bar
        self.create_cap_utilization_bar(overview_frame, current_payroll, salary_cap)

        # Middle section - Position breakdown
        position_frame = ctk.CTkFrame(cap_frame, fg_color=ct['CARD'], corner_radius=12)
        position_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(position_frame, text="Salary by Position",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        # Create position breakdown treeview
        pos_columns = {
            'position': ('Position', 100),
            'players': ('Players', 80),
            'total_salary': ('Total Salary', 120),
            'avg_salary': ('Avg Salary', 120),
            'percentage': ('% of Cap', 80)
        }

        self._position_table, self.position_tree = self._create_fin_treeview(position_frame, pos_columns, 8)
        self._position_table.pack(fill="both", expand=True, padx=10, pady=10)

    def create_contracts_tab(self, contracts_frame):
        """Create detailed player contracts tab."""
        ct = self._ct

        # Filter controls
        filter_frame = ctk.CTkFrame(contracts_frame, fg_color=ct['CARD'], corner_radius=12)
        filter_frame.pack(fill="x", padx=10, pady=10)

        filter_grid = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_grid.pack(fill="x", padx=12, pady=12)

        # Roster filter (pills)
        ctk.CTkLabel(filter_grid, text="Roster:", font=("Segoe UI", 11, "bold"),
                     text_color=ct['TEXT_DIM']).grid(row=0, column=0, padx=5, sticky='w')
        self.roster_filter = tk.StringVar(master=self, value='All')
        _roster_pill_frame = tk.Frame(filter_grid, bg=ct['CARD'])
        _roster_pill_frame.grid(row=0, column=1, padx=5, sticky='w')
        self._fin_roster_pills = make_pill_group(
            _roster_pill_frame, [(o, o) for o in ('All', 'NHL', 'AHL', 'Prospects')],
            self._set_finance_filter('roster_filter'))

        # Position filter (pills)
        ctk.CTkLabel(filter_grid, text="Position:", font=("Segoe UI", 11, "bold"),
                     text_color=ct['TEXT_DIM']).grid(row=0, column=2, padx=5, sticky='w')
        self.position_filter = tk.StringVar(master=self, value='All')
        _pos_pill_frame = tk.Frame(filter_grid, bg=ct['CARD'])
        _pos_pill_frame.grid(row=0, column=3, padx=5, sticky='w')
        self._fin_pos_pills = make_pill_group(
            _pos_pill_frame, [(o, o) for o in ('All', 'G', 'D', 'F')],
            self._set_finance_filter('position_filter'))

        # Contract status filter (pills)
        ctk.CTkLabel(filter_grid, text="Status:", font=("Segoe UI", 11, "bold"),
                     text_color=ct['TEXT_DIM']).grid(row=0, column=4, padx=5, sticky='w')
        self.status_filter = tk.StringVar(master=self, value='All')
        _status_pill_frame = tk.Frame(filter_grid, bg=ct['CARD'])
        _status_pill_frame.grid(row=0, column=5, padx=5, sticky='w')
        self._fin_status_pills = make_pill_group(
            _status_pill_frame,
            [(o, o) for o in ('All', 'Expiring', 'RFA', 'UFA', 'Long-term')],
            self._set_finance_filter('status_filter'))
        self._paint_finance_pills()

        # Contracts treeview
        contract_columns = {
            'name': ('Player', 180),
            'position': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'salary': ('Salary', 100),
            'years': ('Years', 60),
            'status': ('Status', 80),
            'trade_clause': ('NTC', 60),
            'cap_hit': ('Cap Hit', 100),
            'expiry': ('Expires', 70)
        }

        self._contracts_table, self.contracts_tree = self._create_fin_treeview(contracts_frame, contract_columns, 20)
        self._contracts_table.pack(fill="both", expand=True, padx=10, pady=10)

        # Right-click menu with finance actions (replaces the default binding
        # from _create_treeview so Negotiate Extension / Trade are one click away)
        self.contracts_tree.bind('<Button-3>', self._show_contracts_context_menu)

    def create_projections_tab(self, projections_frame):
        """Create future salary projections tab."""
        ct = self._ct

        # Controls
        controls_frame = ctk.CTkFrame(projections_frame, fg_color=ct['CARD'], corner_radius=12)
        controls_frame.pack(fill="x", padx=10, pady=10)

        controls_inner = ctk.CTkFrame(controls_frame, fg_color="transparent")
        controls_inner.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(controls_inner, text="View Year:", font=("Segoe UI", 11, "bold"),
                     text_color=ct['TEXT_DIM']).pack(side="left", padx=5)

        year_combo = ctk.CTkComboBox(
            controls_inner,
            variable=self.selected_projection_year,
            values=[str(y) for y in range(self.current_season, self.current_season + 6)],
            width=120,
            fg_color=ct['BG'],
            border_color=ct['BORDER'],
            button_color=ct['TEAL'],
            button_hover_color=ct['TEAL_HOVER'],
            dropdown_fg_color=ct['PANEL'],
            dropdown_text_color=ct['TEXT'],
            dropdown_hover_color=ct['ROW_HOVER'],
            text_color=ct['TEXT'],
            command=lambda v: self.update_projections_view(),
        )
        year_combo.pack(side="left", padx=5)

        # Refresh button
        self._secondary_button(controls_inner, text="Refresh",
                               command=self.update_projections_view).pack(side="left", padx=10)

        # Summary frame
        summary_frame = ctk.CTkFrame(projections_frame, fg_color=ct['CARD'], corner_radius=12)
        summary_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(summary_frame, text="Financial Projection Summary",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        self.projection_summary_label = ctk.CTkLabel(
            summary_frame, text="", font=('Consolas', 11),
            text_color=ct['TEXT'], justify="left", anchor="w")
        self.projection_summary_label.pack(fill="x", padx=16, pady=(6, 14))

        # Expiring contracts
        expiring_frame = ctk.CTkFrame(projections_frame, fg_color=ct['CARD'], corner_radius=12)
        expiring_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(expiring_frame, text="Expiring Contracts",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        expiring_columns = {
            'name': ('Player', 180),
            'position': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'salary': ('Current Salary', 120),
            'years_left': ('Years Left', 80),
            'status': ('Status', 100),
            'estimated_ask': ('Est. Ask', 120)
        }

        self._expiring_table, self.expiring_tree = self._create_fin_treeview(expiring_frame, expiring_columns, 15)
        self._expiring_table.pack(fill="both", expand=True, padx=10, pady=10)

    def create_management_tab(self, management_frame):
        """Create contract management tools tab."""
        ct = self._ct

        # Quick actions section
        actions_frame = ctk.CTkFrame(management_frame, fg_color=ct['CARD'], corner_radius=12)
        actions_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(actions_frame, text="Quick Actions",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        actions_grid = ctk.CTkFrame(actions_frame, fg_color="transparent")
        actions_grid.pack(fill="x", padx=12, pady=(6, 14))

        # Configure grid
        for i in range(3):
            actions_grid.columnconfigure(i, weight=1)

        # Action buttons
        self._secondary_button(actions_grid, text="Negotiate Extensions",
                               command=self.open_contract_extensions).grid(row=0, column=0, padx=5, pady=5, sticky='ew')

        self._secondary_button(actions_grid, text="Trade Evaluator",
                               command=self.open_trade_evaluator).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        self._secondary_button(actions_grid, text="Salary Analytics",
                               command=self.show_salary_analytics).grid(row=0, column=2, padx=5, pady=5, sticky='ew')

        self._secondary_button(actions_grid, text="Buyout Calculator",
                               command=self.open_buyout_calculator).grid(row=1, column=0, padx=5, pady=5, sticky='ew')

        self._secondary_button(actions_grid, text="Cap Compliance Check",
                               command=self.check_cap_compliance).grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        self._primary_button(actions_grid, text="Export Report",
                             command=self.export_financial_report).grid(row=1, column=2, padx=5, pady=5, sticky='ew')

        # Recommendations section
        recommendations_frame = ctk.CTkFrame(management_frame, fg_color=ct['CARD'], corner_radius=12)
        recommendations_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(recommendations_frame, text="Financial Recommendations",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        text_wrap = ctk.CTkFrame(recommendations_frame, fg_color="transparent")
        text_wrap.pack(fill="both", expand=True, padx=12, pady=(6, 14))

        self.recommendations_text = tk.Text(
            text_wrap, height=15, wrap=tk.WORD,
            bg=ct['CARD'], fg=ct['TEXT'],
            insertbackground=ct['TEXT'],
            selectbackground=ct['ROW_SELECTED'],
            font=('Segoe UI', 10), borderwidth=0,
            highlightthickness=0)
        self.recommendations_text.pack(side="left", fill="both", expand=True)

        recommendations_scroll = ctk.CTkScrollbar(
            text_wrap, orientation="vertical",
            command=self.recommendations_text.yview)
        recommendations_scroll.pack(side="right", fill="y")
        self.recommendations_text.configure(yscrollcommand=recommendations_scroll.set)

    def create_reports_tab(self, reports_frame):
        """Create financial reports tab."""
        ct = self._ct

        # Report selection
        selection_frame = ctk.CTkFrame(reports_frame, fg_color=ct['CARD'], corner_radius=12)
        selection_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(selection_frame, text="Select Report",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        report_grid = ctk.CTkFrame(selection_frame, fg_color="transparent")
        report_grid.pack(fill="x", padx=12, pady=(6, 14))

        self.report_type = tk.StringVar(master=self, value="salary_breakdown")

        self._report_labels = ["Salary Breakdown", "Contract Timeline",
                               "Position Analysis", "Age Demographics",
                               "Performance vs Salary"]
        self._report_values = ["salary_breakdown", "contract_timeline",
                               "position_analysis", "age_demographics",
                               "performance_salary"]

        report_seg = ctk.CTkSegmentedButton(
            report_grid,
            values=self._report_labels,
            fg_color=ct['BG'],
            selected_color=ct['TEAL'],
            selected_hover_color=ct['TEAL_HOVER'],
            unselected_color=ct['CARD'],
            unselected_hover_color=ct['BORDER'],
            text_color=ct['TEXT'],
            command=self._on_report_selected,
        )
        report_seg.pack(fill="x", padx=4)
        report_seg.set("Salary Breakdown")
        self._report_seg = report_seg

        # Report display
        display_frame = ctk.CTkFrame(reports_frame, fg_color=ct['CARD'], corner_radius=12)
        display_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(display_frame, text="Report Output",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=16, pady=(12, 0))

        report_wrap = ctk.CTkFrame(display_frame, fg_color="transparent")
        report_wrap.pack(fill="both", expand=True, padx=12, pady=(6, 14))

        self.report_text = tk.Text(report_wrap, wrap=tk.WORD,
                                   bg=ct['CARD'], fg=ct['TEXT'],
                                   insertbackground=ct['TEXT'],
                                   selectbackground=ct['ROW_SELECTED'],
                                   font=('Consolas', 10), borderwidth=0,
                                   highlightthickness=0)
        self.report_text.pack(side="left", fill="both", expand=True)

        report_scroll = ctk.CTkScrollbar(report_wrap, orientation="vertical",
                                         command=self.report_text.yview)
        report_scroll.pack(side="right", fill="y")
        self.report_text.configure(yscrollcommand=report_scroll.set)

    def _on_report_selected(self, label):
        """Sync the segmented-button choice to the report key, then refresh."""
        try:
            idx = self._report_labels.index(label)
        except ValueError:
            return
        self.report_type.set(self._report_values[idx])
        self.update_report_view()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """Dark, flat styling for the finances tables (styled ttk.Treeview,
        per the migration guide -- the tables carry 8-10 sortable columns)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('FIN.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=30,
                        font=('Segoe UI', 10))
        style.configure('FIN.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('FIN.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('FIN.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('FIN.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.configure('FIN.Horizontal.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('FIN.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])
        style.map('FIN.Horizontal.TScrollbar',
                  background=[('active', ct['BORDER'])])

    def _create_fin_treeview(self, parent, columns, height=15):
        """Dark-styled multi-column table inside a rounded card, with the
        app's generic heading-click sorting wired up."""
        ct = self._ct
        table_frame = ctk.CTkFrame(parent, fg_color=ct['BG'], corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tree = ttk.Treeview(table_frame, columns=list(columns.keys()),
                            show='headings', style='FIN.Treeview', height=height)
        for col, (text, width) in columns.items():
            tree.heading(col, text=text,
                         command=lambda c=col, t=tree: self.parent._sort_treeview_generic(t, c))
            tree.column(col, width=width, anchor='w' if col == 'name' else 'center')

        # Status tags -- color-code contract situations
        tree.tag_configure('status_rfa', foreground=ct['TEAL'])
        tree.tag_configure('status_ufa', foreground=ct['GOLD'])
        tree.tag_configure('status_expiring', foreground=ct['GOLD'])
        tree.tag_configure('status_longterm', foreground=ct['TEXT_DIM'])

        v_scroll = ttk.Scrollbar(table_frame, orient="vertical",
                                 style='FIN.Vertical.TScrollbar',
                                 command=tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient="horizontal",
                                 style='FIN.Horizontal.TScrollbar',
                                 command=tree.xview)
        tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        return table_frame, tree

    # Helper methods
    def create_stat_box(self, parent, title, value, row, col, color=None):
        """Create a statistical display card with color-coded value."""
        ct = self._ct
        box_frame = ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=10)
        box_frame.grid(row=row, column=col, padx=5, pady=5, sticky='ew')

        ctk.CTkLabel(box_frame, text=title,
                     font=("Segoe UI", 10),
                     text_color=ct['TEXT_DIM']).pack(pady=(12, 2))

        if color == 'green':
            value_color = ct['GREEN']
        elif color == 'red':
            value_color = ct['RED']
        else:
            value_color = ct['TEXT']

        ctk.CTkLabel(box_frame, text=value,
                     font=("Segoe UI", 16, "bold"),
                     text_color=value_color).pack(pady=(0, 12))

    def create_cap_utilization_bar(self, parent, current_payroll, salary_cap):
        """Create a modern pill-shaped salary cap utilization meter."""
        ct = self._ct
        bar_frame = ctk.CTkFrame(parent, fg_color="transparent")
        bar_frame.pack(fill="x", padx=16, pady=(4, 16))

        # Calculate percentage
        percentage = (current_payroll / salary_cap) * 100 if salary_cap else 0

        # Utilization color: healthy -> teal, tight -> gold, over -> red
        if percentage > 95:
            bar_color = ct['RED']
        elif percentage >= 80:
            bar_color = ct['GOLD']
        else:
            bar_color = ct['TEAL']

        self.cap_util_bar = ctk.CTkProgressBar(
            bar_frame,
            height=22,
            corner_radius=11,
            fg_color=ct['BORDER'],
            progress_color=bar_color,
        )
        self.cap_util_bar.pack(fill="x", side="left", expand=True)
        self.cap_util_bar.set(max(0.0, min(1.0, current_payroll / salary_cap if salary_cap else 0)))

        ctk.CTkLabel(bar_frame, text=f"{percentage:.1f}% utilized",
                     font=("Segoe UI", 11, "bold"),
                     text_color=ct['TEXT_DIM']).pack(side="left", padx=(12, 0))

    # Calculation methods
    def calculate_current_payroll(self):
        """Calculate the current NHL payroll."""
        total = 0
        for player in self.parent.user_team.roster:
            if hasattr(player, 'contract') and hasattr(player.contract, 'salary'):
                total += player.contract.salary
            elif hasattr(player, 'salary'):
                total += player.salary
        return total

    def calculate_ahl_payroll(self):
        """Calculate the AHL payroll."""
        total = 0
        for player in getattr(self.parent.user_team, 'ahl_roster', []):
            if hasattr(player, 'contract') and hasattr(player.contract, 'salary'):
                total += player.contract.salary
            elif hasattr(player, 'salary'):
                total += player.salary
        return total

    def calculate_buried_salary(self):
        """Calculate buried salary (players in AHL making over minimum)."""
        # For now, return 0 as this requires more complex contract tracking
        return 0

    def _salary_cap(self):
        """The team's salary cap (falls back to the default NHL cap)."""
        return getattr(self.parent.user_team, 'salary_cap', 83_500_000)

    # Update methods
    def update_views(self):
        """Update all views in the finances window."""
        self.update_salary_cap_view()
        self.update_contracts_view()
        self.update_projections_view()
        self.update_recommendations()
        self.update_report_view()

    def update_salary_cap_view(self):
        """Update the salary cap overview."""
        # Update header stats
        current_payroll = self.calculate_current_payroll()
        salary_cap = self._salary_cap()
        cap_space = salary_cap - current_payroll

        ct = self._ct
        cap_color = ct['GREEN'] if cap_space >= 0 else ct['RED']
        self.header_stats_label.configure(
            text=f"Cap Space: ${cap_space:,}  |  Payroll: ${current_payroll:,}  |  Cap: ${salary_cap:,}",
            text_color=cap_color,
        )

        # Update position breakdown
        self.position_tree.delete(*self.position_tree.get_children())

        position_data = self.calculate_position_breakdown()
        for pos, data in position_data.items():
            percentage = (data['total'] / salary_cap) * 100 if salary_cap > 0 else 0
            values = (
                pos,
                str(data['count']),
                f"${data['total']:,}",
                f"${data['avg']:,}",
                f"{percentage:.1f}%"
            )
            self.position_tree.insert('', 'end', values=values)

    def calculate_position_breakdown(self):
        """Calculate salary breakdown by position."""
        positions = {'Goalies': {'count': 0, 'total': 0},
                    'Defense': {'count': 0, 'total': 0},
                    'Forwards': {'count': 0, 'total': 0}}

        for player in self.parent.user_team.roster:
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)

            if hasattr(player, 'primary_position'):
                if player.primary_position == PlayerPosition.GOALIE:
                    positions['Goalies']['count'] += 1
                    positions['Goalies']['total'] += salary
                elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
                    positions['Defense']['count'] += 1
                    positions['Defense']['total'] += salary
                else:
                    positions['Forwards']['count'] += 1
                    positions['Forwards']['total'] += salary

        # Calculate averages
        for pos_data in positions.values():
            pos_data['avg'] = pos_data['total'] // pos_data['count'] if pos_data['count'] > 0 else 0

        return positions

    def _set_finance_filter(self, attr):
        """Returns an on_select callback for a finance pill group."""
        def _select(value):
            getattr(self, attr).set(value)
            self._paint_finance_pills()
            self.update_contracts_view()
        return _select

    def _paint_finance_pills(self):
        for pills_attr, var_attr in (('_fin_roster_pills', 'roster_filter'),
                                     ('_fin_pos_pills', 'position_filter'),
                                     ('_fin_status_pills', 'status_filter')):
            current = getattr(self, var_attr).get()
            for value, btn in getattr(self, pills_attr, {}).items():
                btn.set_selected(value == current)

    _STATUS_TAGS = {'RFA': 'status_rfa', 'UFA': 'status_ufa',
                    'Expiring': 'status_expiring', 'Long-term': 'status_longterm'}

    def update_contracts_view(self):
        """Update the contracts view with filtering."""
        self.contracts_tree.delete(*self.contracts_tree.get_children())
        # Keyed by the treeview widget, matching the app-wide tree_maps
        # convention (see main._create_treeview / _show_player_context_menu).
        self.parent.tree_maps[self.contracts_tree] = {}

        # Get all players based on roster filter
        roster_filter = self.roster_filter.get()
        players = []

        if roster_filter == 'All':
            players.extend(self.parent.user_team.roster)
            players.extend(getattr(self.parent.user_team, 'ahl_roster', []))
            players.extend(getattr(self.parent.user_team, 'prospects', []))
        elif roster_filter == 'NHL':
            players = self.parent.user_team.roster
        elif roster_filter == 'AHL':
            players = getattr(self.parent.user_team, 'ahl_roster', [])
        elif roster_filter == 'Prospects':
            players = getattr(self.parent.user_team, 'prospects', [])

        # Apply filters and populate tree
        for player in players:
            # Position filter
            pos_filter = self.position_filter.get()
            if pos_filter != 'All':
                if hasattr(player, 'primary_position'):
                    if pos_filter == 'G' and player.primary_position != PlayerPosition.GOALIE:
                        continue
                    elif pos_filter == 'D' and player.primary_position not in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
                        continue
                    elif pos_filter == 'F' and player.primary_position not in [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
                        continue

            # Get contract info
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
            years = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1

            # Determine status
            status = self.determine_contract_status(player, years)

            # Status filter
            status_filter = self.status_filter.get()
            if status_filter != 'All' and status != status_filter:
                continue

            # Format position
            position = getattr(player.primary_position, 'name', 'F') if hasattr(player, 'primary_position') else 'F'
            if position in ['LEFT_WING', 'RIGHT_WING', 'CENTER']:
                position = position[0] if position == 'CENTER' else position[:2]
            elif position in ['LEFT_DEFENSE', 'RIGHT_DEFENSE', 'DEFENSE']:
                position = 'D'
            elif position == 'GOALIE':
                position = 'G'

            values = (
                player.full_name,
                position,
                str(getattr(player, 'age', 22)),
                str(player.overall_rating()),
                f"${salary:,}",
                str(years),
                status,
                ("Yes" if getattr(player.contract, 'no_trade_clause', False) else "No") if hasattr(player, 'contract') else "No",
                f"${salary:,}",  # Cap hit (simplified)
                str(self.current_season + years)
            )

            item = self.contracts_tree.insert('', 'end', values=values,
                                              tags=(self._STATUS_TAGS.get(status, ''),))
            self.parent.tree_maps[self.contracts_tree][item] = player

    def determine_contract_status(self, player, years_remaining):
        """Determine the contract status of a player."""
        age = getattr(player, 'age', 22)

        if years_remaining <= 1:
            if age < 25:
                return "RFA"
            else:
                return "UFA"
        elif years_remaining <= 2:
            return "Expiring"
        else:
            return "Long-term"

    def update_projections_view(self):
        """Update the projections view."""
        try:
            selected_year = int(self.selected_projection_year.get())
        except (TypeError, ValueError):
            selected_year = self.current_season
            self.selected_projection_year.set(str(selected_year))
        years_ahead = selected_year - self.current_season

        # Calculate projected payroll
        projected_payroll = 0
        expiring_players = []

        for player in self.parent.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)

            if years_left > years_ahead:
                projected_payroll += salary
            else:
                expiring_players.append(player)

        # Update summary
        salary_cap = self._salary_cap()
        projected_space = salary_cap - projected_payroll

        summary_text = f"""
Projection for {selected_year} Season:
Committed Payroll:    ${projected_payroll:,}
Projected Cap:        ${salary_cap:,}
Available Space:      ${projected_space:,}
Expiring Contracts:   {len(expiring_players)} players
"""

        self.projection_summary_label.configure(text=summary_text)

        # Update expiring contracts tree
        self.expiring_tree.delete(*self.expiring_tree.get_children())

        for player in expiring_players:
            estimated_ask = self.estimate_contract_ask(player)
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            current_salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)

            status = self.determine_contract_status(player, years_left)
            position = getattr(player.primary_position, 'name', 'F') if hasattr(player, 'primary_position') else 'F'

            values = (
                player.full_name,
                position[:1] if position in ['CENTER', 'LEFT_WING', 'RIGHT_WING'] else position[:1],
                str(getattr(player, 'age', 22)),
                str(player.overall_rating()),
                f"${current_salary:,}",
                str(years_left),
                status,
                f"${estimated_ask:,}"
            )

            self.expiring_tree.insert('', 'end', values=values,
                                      tags=(self._STATUS_TAGS.get(status, ''),))

    def estimate_contract_ask(self, player):
        """Estimate what a player might ask for in their next contract."""
        ovr = player.overall_rating()
        age = getattr(player, 'age', 22)
        current_salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)

        # Base estimate on overall rating
        if ovr >= 85:
            base_ask = random.randint(8_000_000, 12_000_000)
        elif ovr >= 80:
            base_ask = random.randint(5_000_000, 8_000_000)
        elif ovr >= 75:
            base_ask = random.randint(3_000_000, 5_000_000)
        elif ovr >= 70:
            base_ask = random.randint(1_500_000, 3_000_000)
        else:
            base_ask = random.randint(750_000, 1_500_000)

        # Age adjustments
        if age < 25:
            base_ask *= 0.9  # Younger players more affordable
        elif age > 32:
            base_ask *= 0.8  # Older players less expensive

        # Don't go too far from current salary unless big performance change
        if current_salary > 0:
            max_increase = current_salary * 1.5
            min_decrease = current_salary * 0.7
            base_ask = max(min_decrease, min(max_increase, base_ask))

        return int(base_ask)

    def update_recommendations(self):
        """Update financial recommendations."""
        recommendations = self.generate_recommendations()

        self.recommendations_text.delete(1.0, tk.END)
        for rec in recommendations:
            self.recommendations_text.insert(tk.END, f"\u2022 {rec}\n\n")

    def generate_recommendations(self):
        """Generate financial recommendations based on current situation."""
        recommendations = []

        current_payroll = self.calculate_current_payroll()
        salary_cap = self._salary_cap()
        cap_space = salary_cap - current_payroll
        cap_percentage = (current_payroll / salary_cap) * 100

        # Cap space recommendations
        if cap_percentage > 95:
            recommendations.append("URGENT: You are very close to the salary cap. Consider trading high-salary players or demoting players to create space.")
        elif cap_percentage > 90:
            recommendations.append("WARNING: Limited cap space available. Be cautious with any new signings.")
        elif cap_percentage < 70:
            recommendations.append("You have significant cap space available. Consider upgrading your roster through free agency or trades.")

        # Contract expiry analysis
        expiring_next_year = []
        for player in self.parent.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            if years_left <= 1:
                expiring_next_year.append(player)

        if len(expiring_next_year) > 8:
            recommendations.append(f"You have {len(expiring_next_year)} players with expiring contracts. Start extension negotiations early to avoid losing key players.")

        # Age demographics
        old_expensive_players = []
        for player in self.parent.user_team.roster:
            age = getattr(player, 'age', 22)
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
            if age > 33 and salary > 4_000_000:
                old_expensive_players.append(player)

        if old_expensive_players:
            recommendations.append(f"Consider the future value of older, expensive players: {', '.join([p.full_name for p in old_expensive_players[:3]])}{'...' if len(old_expensive_players) > 3 else ''}")

        # Position balance
        position_data = self.calculate_position_breakdown()
        for pos, data in position_data.items():
            percentage = (data['total'] / current_payroll) * 100 if current_payroll > 0 else 0
            if pos == 'Goalies' and percentage > 15:
                recommendations.append("Your goalie spending is high relative to other positions. Consider if this allocation is optimal.")
            elif pos == 'Defense' and percentage > 35:
                recommendations.append("High spending on defense. Ensure this matches your team strategy.")
            elif pos == 'Forwards' and percentage < 50:
                recommendations.append("Consider if your forward spending is sufficient for offensive production.")

        if not recommendations:
            recommendations.append("Your financial situation looks stable. Continue monitoring contract expirations and cap space.")

        return recommendations

    def update_report_view(self):
        """Update the selected report view."""
        report_type = self.report_type.get()

        self.report_text.delete(1.0, tk.END)

        if report_type == "salary_breakdown":
            self.generate_salary_breakdown_report()
        elif report_type == "contract_timeline":
            self.generate_contract_timeline_report()
        elif report_type == "position_analysis":
            self.generate_position_analysis_report()
        elif report_type == "age_demographics":
            self.generate_age_demographics_report()
        elif report_type == "performance_salary":
            self.generate_performance_salary_report()

    def generate_salary_breakdown_report(self):
        """Generate detailed salary breakdown report."""
        current_payroll = self.calculate_current_payroll()
        salary_cap = self._salary_cap()
        cap_space = salary_cap - current_payroll
        cap_pct = (current_payroll / salary_cap) * 100 if salary_cap else 0

        report = f"""
SALARY BREAKDOWN REPORT
{self.parent.user_team.team_name} - {self.current_season} Season
{'='*60}

SUMMARY
-------
Total Payroll:    ${current_payroll:,}
Salary Cap:       ${salary_cap:,}
Cap Space:        ${cap_space:,}
Cap Utilization:  {cap_pct:.1f}%

TOP 10 SALARIES
---------------
"""

        # Sort players by salary
        sorted_players = sorted(self.parent.user_team.roster,
                              key=lambda p: getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0),
                              reverse=True)

        for i, player in enumerate(sorted_players[:10], 1):
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
            percentage = (salary / current_payroll) * 100 if current_payroll > 0 else 0
            report += f"{i:2}. {player.full_name:<20} ${salary:>10,} ({percentage:4.1f}%)\n"

        # Position breakdown
        position_data = self.calculate_position_breakdown()
        report += "\n\nPOSITION BREAKDOWN\n------------------\n"

        for pos, data in position_data.items():
            percentage = (data['total'] / current_payroll) * 100 if current_payroll > 0 else 0
            report += f"{pos:<10} {data['count']:2} players  ${data['total']:>10,} ({percentage:4.1f}%) avg: ${data['avg']:,}\n"

        self.report_text.insert(tk.END, report)

    def generate_contract_timeline_report(self):
        """Generate contract timeline report."""
        report = f"""
CONTRACT TIMELINE REPORT
{self.parent.user_team.team_name}
{'='*50}

CONTRACTS BY EXPIRY YEAR
------------------------
"""

        # Group by expiry year
        expiry_groups = {}
        for player in self.parent.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            expiry_year = self.current_season + years_left

            if expiry_year not in expiry_groups:
                expiry_groups[expiry_year] = []
            expiry_groups[expiry_year].append(player)

        for year in sorted(expiry_groups.keys()):
            players = expiry_groups[year]
            total_salary = sum(getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0) for p in players)

            report += f"\n{year}: {len(players)} players, ${total_salary:,}\n"
            report += "-" * 40 + "\n"

            for player in sorted(players, key=lambda p: getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0), reverse=True):
                salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
                age_at_expiry = getattr(player, 'age', 22) + (year - self.current_season)
                status = "RFA" if age_at_expiry < 25 else "UFA"
                report += f"  {player.full_name:<20} ${salary:>8,} (age {age_at_expiry}, {status})\n"

        self.report_text.insert(tk.END, report)

    def generate_position_analysis_report(self):
        """Generate position analysis report."""
        report = f"""
POSITION ANALYSIS REPORT
{self.parent.user_team.team_name}
{'='*50}

DETAILED POSITION BREAKDOWN
---------------------------
"""

        # Analyze by specific positions
        positions = {
            'Goalies': [],
            'Defense': [],
            'Centers': [],
            'Wingers': []
        }

        for player in self.parent.user_team.roster:
            if hasattr(player, 'primary_position'):
                if player.primary_position == PlayerPosition.GOALIE:
                    positions['Goalies'].append(player)
                elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
                    positions['Defense'].append(player)
                elif player.primary_position == PlayerPosition.CENTER:
                    positions['Centers'].append(player)
                else:
                    positions['Wingers'].append(player)

        for pos_name, players in positions.items():
            if not players:
                continue

            total_salary = sum(getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0) for p in players)
            avg_salary = total_salary / len(players) if players else 0
            avg_age = sum(getattr(p, 'age', 22) for p in players) / len(players) if players else 0
            avg_ovr = sum(p.overall_rating() for p in players) / len(players) if players else 0

            report += f"\n{pos_name.upper()}\n"
            report += f"Players: {len(players)}\n"
            report += f"Total Salary: ${total_salary:,}\n"
            report += f"Average Salary: ${avg_salary:,.0f}\n"
            report += f"Average Age: {avg_age:.1f}\n"
            report += f"Average OVR: {avg_ovr:.1f}\n"
            report += "-" * 30 + "\n"

            for player in sorted(players, key=lambda p: getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0), reverse=True):
                salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
                report += f"  {player.full_name:<20} {getattr(player, 'age', 22):2} yrs  OVR {player.overall_rating():2}  ${salary:>8,}\n"

        self.report_text.insert(tk.END, report)

    def generate_age_demographics_report(self):
        """Generate age demographics report."""
        report = f"""
AGE DEMOGRAPHICS REPORT
{self.parent.user_team.team_name}
{'='*50}

AGE GROUP BREAKDOWN
-------------------
"""

        age_groups = {
            '18-22': [], '23-26': [], '27-30': [], '31-34': [], '35+': []
        }

        for player in self.parent.user_team.roster:
            age = getattr(player, 'age', 22)
            if age <= 22:
                age_groups['18-22'].append(player)
            elif age <= 26:
                age_groups['23-26'].append(player)
            elif age <= 30:
                age_groups['27-30'].append(player)
            elif age <= 34:
                age_groups['31-34'].append(player)
            else:
                age_groups['35+'].append(player)

        for group_name, players in age_groups.items():
            if not players:
                continue

            total_salary = sum(getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0) for p in players)
            avg_ovr = sum(p.overall_rating() for p in players) / len(players) if players else 0

            report += f"\nAGE {group_name}\n"
            report += f"Players: {len(players)}\n"
            report += f"Total Salary: ${total_salary:,}\n"
            report += f"Average OVR: {avg_ovr:.1f}\n"
            report += "-" * 25 + "\n"

            for player in players:
                salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
                report += f"  {player.full_name:<20} {getattr(player, 'age', 22):2} yrs  ${salary:>8,}\n"

        self.report_text.insert(tk.END, report)

    def generate_performance_salary_report(self):
        """Generate performance vs salary analysis."""
        report = f"""
PERFORMANCE vs SALARY ANALYSIS
{self.parent.user_team.team_name}
{'='*50}

VALUE ANALYSIS
--------------
(Players ranked by value: OVR rating vs salary cost)
"""

        # Calculate value scores
        player_values = []
        for player in self.parent.user_team.roster:
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
            ovr = player.overall_rating()

            # Calculate value score (higher is better value)
            if salary > 0:
                value_score = (ovr ** 2) / (salary / 1_000_000)  # OVR squared divided by salary in millions
            else:
                value_score = ovr ** 2

            player_values.append((player, ovr, salary, value_score))

        # Sort by value score
        player_values.sort(key=lambda x: x[3], reverse=True)

        report += "\nBEST VALUE CONTRACTS\n" + "-" * 25 + "\n"
        for i, (player, ovr, salary, value) in enumerate(player_values[:10], 1):
            report += f"{i:2}. {player.full_name:<20} OVR {ovr:2} ${salary:>8,} (Value: {value:.1f})\n"

        report += "\nHIGHEST PAID PLAYERS\n" + "-" * 25 + "\n"
        highest_paid = sorted(player_values, key=lambda x: x[2], reverse=True)[:10]
        for i, (player, ovr, salary, value) in enumerate(highest_paid, 1):
            report += f"{i:2}. {player.full_name:<20} OVR {ovr:2} ${salary:>8,} (Value: {value:.1f})\n"

        report += "\nPOTENTIAL OVERPAYS\n" + "-" * 25 + "\n"
        potential_overpays = [pv for pv in player_values if pv[2] > 3_000_000 and pv[3] < 50][:5]
        for i, (player, ovr, salary, value) in enumerate(potential_overpays, 1):
            report += f"{i:2}. {player.full_name:<20} OVR {ovr:2} ${salary:>8,} (Value: {value:.1f})\n"

        self.report_text.insert(tk.END, report)

    # Event handlers
    def _show_contracts_context_menu(self, event):
        """Right-click menu for the contracts list, with finance actions."""
        item_id = self.contracts_tree.identify_row(event.y)
        if not item_id:
            return
        self.contracts_tree.selection_set(item_id)
        player = self.parent.tree_maps.get(self.contracts_tree, {}).get(item_id)
        if not player:
            return
        PlayerContextMenu(self).show_context_menu(
            event, player,
            additional_options=[
                ("Negotiate Extension", self.negotiate_extension),
                ("Trade Player", self.trade_player),
                ("Contract Details",
                 lambda p=player: self._view_contract_details(p)),
            ])

    def view_contract_player_profile(self):
        """View the selected player's profile."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.parent.tree_maps.get(self.contracts_tree, {}):
            player = self.parent.tree_maps.get(self.contracts_tree, {})[selection[0]]
            self.parent.open_player_profile(player)

    def negotiate_extension(self):
        """Open contract negotiation for selected player."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.parent.tree_maps.get(self.contracts_tree, {}):
            player = self.parent.tree_maps.get(self.contracts_tree, {})[selection[0]]
            # Open contract negotiation window
            if 'contract_negotiation' not in self.parent.open_windows or not self.parent.open_windows['contract_negotiation'].winfo_exists():
                self.parent.open_windows['contract_negotiation'] = ContractNegotiationWindow(self.parent, player, is_extension=True)
            self.parent.open_windows['contract_negotiation'].focus_set()

    def trade_player(self):
        """Open trade window for selected player."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.parent.tree_maps.get(self.contracts_tree, {}):
            player = self.parent.tree_maps.get(self.contracts_tree, {})[selection[0]]
            # Open trade window with this player pre-selected
            self.parent.open_trade_window()

    # Action methods
    def open_contract_extensions(self):
        """Open contract extensions window."""
        if 'contract_extensions' not in self.parent.open_windows or not self.parent.open_windows['contract_extensions'].winfo_exists():
            self.parent.open_windows['contract_extensions'] = ContractExtensionsWindow(self.parent)
        self.parent.open_windows['contract_extensions'].focus_set()

    def open_trade_evaluator(self):
        """Open trade evaluator tool (the Trade Center)."""
        self.parent.open_trade_window()

    def show_salary_analytics(self):
        """Show advanced salary analytics."""
        SalaryAnalyticsWindow(self.parent)

    def open_buyout_calculator(self):
        """Open buyout calculator."""
        BuyoutCalculatorWindow(self.parent)

    def check_cap_compliance(self):
        """Check salary cap compliance."""
        current_payroll = self.calculate_current_payroll()
        salary_cap = self._salary_cap()

        if current_payroll > salary_cap:
            over_amount = current_payroll - salary_cap
            messagebox.showerror("Cap Violation", f"Your team is ${over_amount:,} over the salary cap!\nYou must make moves to become compliant.")
        else:
            space = salary_cap - current_payroll
            messagebox.showinfo("Cap Compliant", f"Your team is cap compliant with ${space:,} in available space.")

    def export_financial_report(self):
        """Export detailed financial report to file."""
        try:
            from datetime import datetime
            import os

            # Create exports directory next to the app (not the process cwd)
            exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
            if not os.path.exists(exports_dir):
                os.makedirs(exports_dir)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"financial_report_{self.parent.user_team.team_name.replace(' ', '_')}_{timestamp}.txt"
            filepath = os.path.join(exports_dir, filename)

            # Calculate financial data
            current_payroll = sum(getattr(p.contract, 'salary', getattr(p, 'salary', 750000))
                                for p in self.parent.user_team.roster
                                if hasattr(p, 'contract') or hasattr(p, 'salary'))

            salary_cap = self._salary_cap()
            cap_space = salary_cap - current_payroll

            # Generate detailed report
            report_content = f"""
DETAILED FINANCIAL REPORT
{self.parent.user_team.team_name} - {datetime.now().strftime('%Y-%m-%d')}
{'='*70}

SALARY CAP SUMMARY
------------------
Total Payroll:      ${current_payroll:,}
Salary Cap:         ${salary_cap:,}
Available Space:    ${cap_space:,}
Cap Utilization:    {(current_payroll / salary_cap) * 100:.1f}%
Cap Status:         {'COMPLIANT' if current_payroll <= salary_cap else 'OVER CAP'}

ROSTER BREAKDOWN
----------------
"""

            # Sort players by salary for detailed breakdown
            sorted_players = sorted(self.parent.user_team.roster,
                                  key=lambda p: getattr(p.contract, 'salary', getattr(p, 'salary', 750000)),
                                  reverse=True)

            for i, player in enumerate(sorted_players, 1):
                salary = getattr(player.contract, 'salary', getattr(player, 'salary', 750000))
                years_left = getattr(player.contract, 'years_remaining', 0) if hasattr(player, 'contract') else 0

                report_content += f"{i:2d}. {player.full_name:<25} {str(player.primary_position):<8} ${salary:>10,} ({years_left} yrs)\n"

            # Contract expiry analysis
            report_content += f"\n\nCONTRACT EXPIRY ANALYSIS\n{'-'*25}\n"

            expiring_this_year = [p for p in self.parent.user_team.roster
                                if hasattr(p, 'contract') and getattr(p.contract, 'years_remaining', 0) <= 1]
            expiring_next_year = [p for p in self.parent.user_team.roster
                                if hasattr(p, 'contract') and getattr(p.contract, 'years_remaining', 0) == 2]

            report_content += f"Contracts expiring this season: {len(expiring_this_year)}\n"
            for player in expiring_this_year:
                salary = getattr(player.contract, 'salary', 750000)
                report_content += f"  \u2022 {player.full_name} - ${salary:,}\n"

            report_content += f"\nContracts expiring next season: {len(expiring_next_year)}\n"
            for player in expiring_next_year:
                salary = getattr(player.contract, 'salary', 750000)
                report_content += f"  \u2022 {player.full_name} - ${salary:,}\n"

            # Position breakdown
            report_content += f"\n\nSALARY BY POSITION\n{'-'*18}\n"

            position_totals = {}
            for player in self.parent.user_team.roster:
                pos = str(player.primary_position)
                salary = getattr(player.contract, 'salary', getattr(player, 'salary', 750000))

                if pos not in position_totals:
                    position_totals[pos] = {'total': 0, 'count': 0}
                position_totals[pos]['total'] += salary
                position_totals[pos]['count'] += 1

            for pos, data in sorted(position_totals.items()):
                avg_salary = data['total'] / data['count'] if data['count'] > 0 else 0
                report_content += f"{pos:<12} {data['count']:2d} players  ${data['total']:>10,}  (avg: ${avg_salary:,.0f})\n"

            # Future projections
            report_content += f"\n\nFUTURE CAP PROJECTIONS\n{'-'*22}\n"
            report_content += f"Next season cap space (estimated): ${cap_space:,}\n"
            report_content += f"Extension priorities: {len(expiring_this_year)} players need new contracts\n"
            report_content += f"Trade candidates: Players with high salaries and declining performance\n"

            # Write report to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)

            messagebox.showinfo("Export Successful",
                              f"Financial report exported successfully!\n\n"
                              f"File: {filename}\n"
                              f"Location: {exports_dir}")

        except Exception as e:
            print(f"Error exporting financial report: {e}")
            messagebox.showerror("Export Error", f"Failed to export financial report:\n{str(e)}")

    def _view_contract_details(self, player):
        """View detailed contract information"""
        contract = getattr(player, 'contract', None)
        if contract:
            salary = getattr(contract, 'salary', 750000)
            years = getattr(contract, 'years_remaining', 0)
            messagebox.showinfo("Contract Details",
                              f"Player: {player.full_name}\n"
                              f"Salary: ${salary:,}\n"
                              f"Years remaining: {years}\n"
                              f"Cap hit: ${salary:,}")
        else:
            messagebox.showinfo("Contract Details", f"No contract information available for {player.full_name}")



class NewsWindow(ctk.CTkToplevel):
    """League news feed — modern CTk rebuild.

    Two-pane layout: a scrollable feed of rounded article cards (headline,
    category chip, date, preview) on the left and a dark reading pane on the
    right. Category pill filters + text search narrow the feed.
    """

    # Emoji ranges stripped from story text before display (stories are
    # written by the sim in main.py and may contain emoji).
    _EMOJI_RE = re.compile(
        "["
        "\U0001F000-\U0001FAFF"  # emoticons, transport, supplemental symbols
        "\U00002600-\U000027BF"  # misc symbols & dingbats
        "\U00002B00-\U00002BFF"  # misc symbols and arrows
        "\u2190-\u21FF"          # arrows
        "\u2300-\u23FF"          # misc technical
        "\u2C60-\u2C7F"
        "\uFE0F\u200D"
        "]+"
    )

    # (category, keywords) — first match wins, order matters.
    _CATEGORY_KEYWORDS = (
        ("Injuries", ("injur", "hurt", "sidelined", "out for", "healthy scratch")),
        ("Trades", ("trade", "acquir", "trade block")),
        ("Signings", ("sign", "contract", "extension", "deal", "waiver", "claim")),
        ("Development", ("development", "improv", "scout")),
        ("Draft", ("draft", "lottery")),
        ("Scores", ("defeat", " shutout", "overtime", "shootout", " final", "beat ")),
        ("League", ("breaking", "suspend", "fine", "award", "trophy", "record",
                    "milestone", "streak", "hired", "hiring", "general manager")),
    )
    _CATEGORY_COLORS = {
        "All": "#00ceb8",
        "Injuries": "#e74c3c",
        "Trades": "#58a6ff",
        "Signings": "#3fb950",
        "Development": "#00ceb8",
        "Draft": "#e8b93c",
        "Scores": "#ff9e64",
        "League": "#b392f0",
        "Other": "#71717a",
    }

    def __init__(self, parent):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED,
                        BLUE=BLUE, ROW_HOVER=ROW_HOVER, ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()
        super().__init__(parent)
        self.parent = parent
        self.title("League News")
        self.configure(fg_color=BG)
        self.geometry("1200x750")
        self.minsize(1000, 600)

        ct = self._ct
        self._filter = "All"
        self._search = ""
        self._articles = []       # (clean_story, date_str, category)
        self._cards = []          # (frame, index)
        self._selected_idx = None
        self._selected_frame = None
        self._pill_buttons = {}

        # ---- Header card ----
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        header.pack(fill="x", padx=12, pady=(12, 0))
        heading(header, text="League News", size=20).pack(side="left", padx=16, pady=12)
        self._count_lbl = body(header, text="", dim=True)
        self._count_lbl.pack(side="left", padx=(4, 0), pady=12)
        self._refresh_btn = secondary_button(header, text="Refresh",
                                             command=self.populate_news, width=110)
        self._refresh_btn.pack(side="right", padx=16, pady=10)
        self._search_entry = ctk.CTkEntry(
            header, placeholder_text="Search stories...", width=220,
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            placeholder_text_color=TEXT_FAINT, corner_radius=8)
        self._search_entry.pack(side="right", padx=(0, 8), pady=10)
        self._search_entry.bind("<KeyRelease>", self._on_search)

        # ---- Category pill row ----
        pill_row = ctk.CTkFrame(self, fg_color="transparent")
        pill_row.pack(fill="x", padx=12, pady=(10, 0))
        categories = ["All"] + [c for c, _ in self._CATEGORY_KEYWORDS] + ["Other"]
        for cat in categories:
            btn = ctk.CTkButton(
                pill_row, text=cat, width=0, height=28, corner_radius=14,
                fg_color=CARD, hover_color=BORDER, text_color=TEXT_DIM,
                font=("Segoe UI", 11),
                command=lambda c=cat: self._set_filter(c))
            btn.pack(side="left", padx=(0, 8))
            self._pill_buttons[cat] = btn
        self._mark_pill_selected()

        # ---- Two-pane content ----
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=10)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        self._feed = ctk.CTkScrollableFrame(content, fg_color=PANEL,
                                            corner_radius=12)
        self._feed.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        reader = ctk.CTkFrame(content, fg_color=CARD, corner_radius=12)
        reader.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._reader_meta = body(reader, text="", size=11, dim=True)
        self._reader_meta.pack(anchor="w", padx=16, pady=(14, 4))
        self._reader_headline = heading(reader, text="", size=15)
        self._reader_headline.pack(anchor="w", padx=16, pady=(0, 8))
        self._reader_text = ctk.CTkTextbox(reader, wrap="word",
                                           fg_color=BG, text_color=TEXT,
                                           border_color=BORDER, border_width=1,
                                           corner_radius=8,
                                           font=("Segoe UI", 12))
        self._reader_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.populate_news()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    @classmethod
    def _clean_story(cls, story):
        """Strip emoji and tidy whitespace for display."""
        text = cls._EMOJI_RE.sub("", str(story or ""))
        return " ".join(text.split())

    @classmethod
    def _categorize(cls, story):
        lowered = story.lower()
        for cat, keywords in cls._CATEGORY_KEYWORDS:
            if any(k in lowered for k in keywords):
                return cat
        return "Other"

    @staticmethod
    def _headline(story, limit=110):
        """First sentence, truncated — used as the card headline."""
        first = story.split(". ")[0].strip()
        if len(first) > limit:
            first = first[:limit].rsplit(" ", 1)[0] + "..."
        return first

    # ------------------------------------------------------------------
    # Filtering / rendering
    # ------------------------------------------------------------------
    def _set_filter(self, category):
        self._filter = category
        self._mark_pill_selected()
        self._render_feed()

    def _mark_pill_selected(self):
        ct = self._ct
        for cat, btn in self._pill_buttons.items():
            if cat == self._filter:
                btn.configure(fg_color=ct["TEAL"], text_color=ct["BG"],
                              hover_color=ct["TEAL_HOVER"],
                              font=("Segoe UI", 11, "bold"))
            else:
                btn.configure(fg_color=ct["CARD"], text_color=ct["TEXT_DIM"],
                              hover_color=ct["BORDER"],
                              font=("Segoe UI", 11))

    def _on_search(self, _event=None):
        self._search = self._search_entry.get().strip().lower()
        self._render_feed()

    def _load_articles(self):
        """Read the parent's news log into (story, date_str, category) tuples."""
        news_log = getattr(self.parent, "news_log", None) or []
        articles = []
        for item in reversed(news_log):
            if isinstance(item, dict):
                date = item.get("date")
                story = self._clean_story(item.get("story"))
            else:
                date, story = None, self._clean_story(item)
            if not story:
                continue
            date_str = date.strftime("%b %d, %Y") if hasattr(date, "strftime") else ""
            articles.append((story, date_str, self._categorize(story)))
        return articles

    def populate_news(self):
        """Re-render the news feed from the current news_log.

        Also called by main.add_news() while the window is open — this name
        is the live-update entry point (refresh_news is kept as an alias).
        """
        self._articles = self._load_articles()
        self._render_feed()

    def refresh_news(self):
        """Backwards-compatible alias for populate_news."""
        self.populate_news()

    def _filtered(self):
        out = []
        for i, (story, date_str, cat) in enumerate(self._articles):
            if self._filter != "All" and cat != self._filter:
                continue
            if self._search and self._search not in story.lower():
                continue
            out.append((i, story, date_str, cat))
        return out

    def _render_feed(self):
        ct = self._ct
        for frame, _ in self._cards:
            frame.destroy()
        self._cards = []
        self._selected_idx = None
        self._selected_frame = None

        items = self._filtered()
        total = len(self._articles)
        shown = len(items)
        self._count_lbl.configure(
            text=f"{shown} of {total} stories" if total else "")

        if not items:
            msg = ("No news yet. Advance the season to generate league news."
                   if not self._articles
                   else "No stories match the current filter.")
            empty = self._body(self._feed, text=msg, dim=True, size=13)
            empty.pack(padx=20, pady=60)
            self._cards.append((empty, -1))
            self._show_article(None)
            return

        for idx, story, date_str, cat in items:
            card = ctk.CTkFrame(self._feed, fg_color=ct["CARD"],
                                corner_radius=10, border_width=1,
                                border_color=ct["BORDER"])
            card.pack(fill="x", padx=10, pady=6)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(10, 0))
            chip = ctk.CTkLabel(top, text=cat, font=("Segoe UI", 10, "bold"),
                                text_color=self._CATEGORY_COLORS.get(cat, ct["TEXT_FAINT"]),
                                fg_color=ct["BG"], corner_radius=10)
            chip.pack(side="left", padx=8, pady=2)
            if date_str:
                self._body(top, text=date_str, size=10, dim=True).pack(side="right")

            self._heading(card, text=self._headline(story), size=13,
                                wraplength=400, justify="left").pack(
                anchor="w", padx=14, pady=(6, 2))
            preview = story if len(story) <= 170 else story[:170].rsplit(" ", 1)[0] + "..."
            self._body(card, text=preview, size=11, dim=True, wraplength=400,
                 justify="left").pack(anchor="w", padx=14, pady=(0, 10))

            for w in (card, top, chip):
                w.bind("<Button-1>", lambda e, i=idx, f=card: self._select(i, f))
                w.bind("<Enter>", lambda e, f=card: self._hover(f, True))
                w.bind("<Leave>", lambda e, f=card: self._hover(f, False))
            self._cards.append((card, idx))

        # Auto-select the newest story.
        first_card, first_idx = self._cards[0]
        if first_idx >= 0:
            self._select(first_idx, first_card)

    # ------------------------------------------------------------------
    # Selection / reading pane
    # ------------------------------------------------------------------
    def _hover(self, frame, on):
        if frame is self._selected_frame:
            return
        frame.configure(border_color=self._ct["TEAL"] if on else self._ct["BORDER"])

    def _select(self, idx, frame):
        ct = self._ct
        if self._selected_frame is not None and self._selected_frame is not frame:
            self._selected_frame.configure(border_color=ct["BORDER"])
        self._selected_idx = idx
        self._selected_frame = frame
        frame.configure(border_color=ct["TEAL"])
        story, date_str, cat = self._articles[idx]
        self._show_article((story, date_str, cat))

    def _show_article(self, article):
        if article is None:
            self._reader_meta.configure(text="")
            self._reader_headline.configure(text="Select a story to read")
            self._reader_text.configure(state="normal")
            self._reader_text.delete("1.0", "end")
            self._reader_text.configure(state="disabled")
            return
        story, date_str, cat = article
        color = self._CATEGORY_COLORS.get(cat, self._ct["TEXT_FAINT"])
        self._reader_meta.configure(text=f"{cat}  •  {date_str}" if date_str else cat,
                                    text_color=color)
        reader_headline = self._headline(story, limit=160)
        self._reader_headline.configure(
            text="" if reader_headline == story else reader_headline)
        self._reader_text.configure(state="normal")
        self._reader_text.delete("1.0", "end")
        self._reader_text.insert("1.0", story)
        self._reader_text.configure(state="disabled")


class GMOptionsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("General Manager Options")
        self.geometry("600x450")
        self.configure(background=parent.BG_COLOR)

        header = ttk.Frame(self, style='Panel.TFrame', padding=(20, 14))
        header.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(header, text="GM OPTIONS",
                  font=(parent.FONT_FAMILY, 16, 'bold'),
                  style='Heading.TLabel').pack(side='left')

        # GM Management Options
        management_frame = ttk.LabelFrame(self, text="Team Management", padding=15)
        management_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(management_frame, text="Manage Trade Block", command=self.parent.open_trade_block_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Handle Waivers", command=self.parent.open_waivers_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Set Captains", command=self.parent.open_set_captains_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Negotiate Extensions", command=self.negotiate_extensions, style='Accent.TButton').pack(pady=5, fill='x')

        # Game Settings & Preferences
        settings_frame = ttk.LabelFrame(self, text="Game Settings & Preferences", padding=15)
        settings_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(settings_frame, text="Settings & Preferences", command=self.parent.open_settings_window).pack(pady=5, fill='x')

        # Close button
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=20)

    def negotiate_extensions(self):
        if 'contract_extensions' not in self.parent.open_windows or not self.parent.open_windows['contract_extensions'].winfo_exists():
            self.parent.open_windows['contract_extensions'] = ContractExtensionsWindow(self.parent)
        self.parent.open_windows['contract_extensions'].focus_set()

class ContractNegotiationWindow(tk.Toplevel):
    def __init__(self, parent, player, is_extension=False):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.is_extension = is_extension
        self.title(f"Negotiate with {player.full_name}")
        self.geometry("500x450")
        self.configure(background=parent.BG_COLOR)
        self.transient(parent)
        self.grab_set()

        # Create main container with padding
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Title section
        title_text = "Contract Extension" if is_extension else "Contract Offer"
        ttk.Label(main_frame, text=title_text, style='Title.TLabel').pack(pady=(0, 10))
        
        # Player info section
        player_frame = ttk.LabelFrame(main_frame, text="Player Information", style='Panel.TLabelframe')
        player_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(player_frame, text=f"Name: {player.full_name}", style='TLabel').pack(anchor='w', padx=10, pady=5)
        ttk.Label(player_frame, text=f"Position: {player.primary_position.value}", style='TLabel').pack(anchor='w', padx=10, pady=2)
        ttk.Label(player_frame, text=f"Age: {player.age}", style='TLabel').pack(anchor='w', padx=10, pady=2)
        ttk.Label(player_frame, text=f"Overall Rating: {to_100_scale(player.overall_rating())}", style='TLabel').pack(anchor='w', padx=10, pady=2)
        ttk.Label(player_frame, text=f"Potential: {player.potential_grade}", style='TLabel').pack(anchor='w', padx=10, pady=(2, 10))
        
        # Current contract info (if extension)
        if is_extension and hasattr(player, 'salary'):
            current_frame = ttk.LabelFrame(main_frame, text="Current Contract", style='Panel.TLabelframe')
            current_frame.pack(fill='x', pady=(0, 15))
            
            ttk.Label(current_frame, text=f"Current Salary: ${player.salary:,}", style='TLabel').pack(anchor='w', padx=10, pady=5)
            if hasattr(player, 'contract_years'):
                ttk.Label(current_frame, text=f"Years Remaining: {player.contract_years}", style='TLabel').pack(anchor='w', padx=10, pady=(2, 10))
        
        # Contract offer section
        offer_frame = ttk.LabelFrame(main_frame, text="Contract Offer", style='Panel.TLabelframe')
        offer_frame.pack(fill='x', pady=(0, 15))
        
        # Salary input
        salary_frame = ttk.Frame(offer_frame)
        salary_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(salary_frame, text="Annual Salary: $", style='TLabel').pack(side='left')
        self.salary_var = tk.StringVar(master=self, value="750000")
        salary_entry = ttk.Entry(salary_frame, textvariable=self.salary_var, width=15)
        salary_entry.pack(side='left', padx=(5, 0))
        
        # Years input
        years_frame = ttk.Frame(offer_frame)
        years_frame.pack(fill='x', padx=10, pady=(5, 10))
        ttk.Label(years_frame, text="Contract Length:", style='TLabel').pack(side='left')
        self.years_var = tk.StringVar(master=self, value="1")
        years_entry = ttk.Entry(years_frame, textvariable=self.years_var, width=5)
        years_entry.pack(side='left', padx=(5, 5))
        ttk.Label(years_frame, text="years", style='TLabel').pack(side='left')
        
        # Total value display
        self.total_label = ttk.Label(offer_frame, text="Total Contract Value: $0", style='Subtitle.TLabel')
        self.total_label.pack(anchor='w', padx=10, pady=(10, 15))
        
        # Update total when values change
        self.salary_var.trace('w', self.update_total)
        self.years_var.trace('w', self.update_total)
        self.update_total()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=20)
        
        ttk.Button(button_frame, text="Submit Offer", command=self.submit_offer, style='TButton').pack(side='right', padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.destroy, style='TButton').pack(side='right')

    def update_total(self, *args):
        """Update the total contract value display."""
        try:
            salary = int(self.salary_var.get().replace(',', ''))
            years = int(self.years_var.get())
            total = salary * years
            self.total_label.config(text=f"Total Contract Value: ${total:,}")
        except (ValueError, AttributeError):
            self.total_label.config(text="Total Contract Value: $0")

    def submit_offer(self):
        try:
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = int(self.years_var.get())
            
            # Validate inputs
            if salary <= 0:
                messagebox.showerror("Invalid Input", "Salary must be greater than $0.")
                return
            if years <= 0 or years > 8:
                messagebox.showerror("Invalid Input", "Contract length must be between 1 and 8 years.")
                return
            
            # Set the values on the player object first
            self.player.salary = salary
            self.player.contract_years = years
            
            # Then call handle_contract_offer with proper arguments
            accepted = self.parent.handle_contract_offer(self.player, extension=self.is_extension)
            if accepted:
                self.destroy()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for salary and years.")

class TradeBlockWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Trade Block")
        self.geometry("1200x800")
        self.configure(background=parent.BG_COLOR)
        
        # Initialize data
        self.trade_block_players = []
        self.interested_teams = {}
        
        self.create_widgets()
        self.load_trade_block()
    
    def create_widgets(self):
        """Create the trade block interface."""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Trade Block", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create notebook for different sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True)
        
        # Your Trade Block tab
        self.your_block_frame = ttk.Frame(notebook)
        notebook.add(self.your_block_frame, text="Your Trade Block")
        self.create_your_trade_block(self.your_block_frame)
        
        # Other Teams' Blocks tab
        self.other_blocks_frame = ttk.Frame(notebook)
        notebook.add(self.other_blocks_frame, text="Other Teams")
        self.create_other_trade_blocks(self.other_blocks_frame)
        
        # Trade Interest tab
        self.interest_frame = ttk.Frame(notebook)
        notebook.add(self.interest_frame, text="Trade Interest")
        self.create_trade_interest(self.interest_frame)
    
    def create_your_trade_block(self, parent):
        """Create your team's trade block management."""
        # Controls frame
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(controls_frame, text="Add Player to Block", 
                  command=self.add_to_trade_block).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Remove from Block", 
                  command=self.remove_from_trade_block).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Generate Interest", 
                  command=self.generate_trade_interest).pack(side='left', padx=5)
        
        # Trade block players list
        block_frame = ttk.LabelFrame(parent, text="Players on Trade Block")
        block_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create treeview for trade block players
        columns = ('Name', 'Position', 'Age', 'Overall', 'Salary', 'Years Left', 'Interest Level')
        self.block_tree = ttk.Treeview(block_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.block_tree.heading(col, text=col)
            if col == 'Name':
                self.block_tree.column(col, width=150)
            elif col in ['Position', 'Age', 'Overall']:
                self.block_tree.column(col, width=80)
            elif col == 'Salary':
                self.block_tree.column(col, width=120)
            else:
                self.block_tree.column(col, width=100)
        make_tree_sortable(self.block_tree)
        
        # Scrollbar for trade block
        block_scrollbar = ttk.Scrollbar(block_frame, orient='vertical', command=self.block_tree.yview)
        self.block_tree.configure(yscrollcommand=block_scrollbar.set)
        
        self.block_tree.pack(side='left', fill='both', expand=True)
        block_scrollbar.pack(side='right', fill='y')
        add_player_context_menu(self.block_tree, self)
    
    def create_other_trade_blocks(self, parent):
        """Create view of other teams' trade blocks."""
        # Team selection
        select_frame = ttk.Frame(parent)
        select_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(select_frame, text="Select Team:").pack(side='left', padx=5)
        self.team_var = tk.StringVar(master=self)
        self.team_combo = ttk.Combobox(select_frame, textvariable=self.team_var, 
                                      values=self.get_other_teams(), width=30)
        self.team_combo.pack(side='left', padx=5)
        self.team_combo.bind('<<ComboboxSelected>>', self.on_team_selected)
        
        ttk.Button(select_frame, text="Refresh", 
                  command=self.refresh_other_blocks).pack(side='left', padx=10)
        
        # Other teams' players
        other_frame = ttk.LabelFrame(parent, text="Available Players")
        other_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Team', 'Name', 'Position', 'Age', 'Overall', 'Salary', 'Interest')
        self.other_tree = ttk.Treeview(other_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.other_tree.heading(col, text=col)
            if col in ['Name', 'Team']:
                self.other_tree.column(col, width=120)
            elif col in ['Position', 'Age', 'Overall']:
                self.other_tree.column(col, width=80)
            else:
                self.other_tree.column(col, width=100)
        make_tree_sortable(self.other_tree)
        
        # Double-click to show interest
        self.other_tree.bind('<Double-1>', self.express_interest)
        
        other_scrollbar = ttk.Scrollbar(other_frame, orient='vertical', command=self.other_tree.yview)
        self.other_tree.configure(yscrollcommand=other_scrollbar.set)
        
        self.other_tree.pack(side='left', fill='both', expand=True)
        other_scrollbar.pack(side='right', fill='y')
    
    def create_trade_interest(self, parent):
        """Create trade interest management."""
        # Interest summary
        summary_frame = ttk.LabelFrame(parent, text="Trade Interest Summary")
        summary_frame.pack(fill='x', padx=10, pady=10)
        
        self.interest_summary = tk.Text(summary_frame, height=6, wrap='word', bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR, insertbackground=self.parent.TEXT_COLOR)
        self.interest_summary.pack(fill='x', padx=10, pady=10)
        
        # Detailed interest
        detail_frame = ttk.LabelFrame(parent, text="Detailed Interest")
        detail_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Your Player', 'Interested Team', 'Their Interest', 'Your Interest', 'Status')
        self.interest_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.interest_tree.heading(col, text=col)
            self.interest_tree.column(col, width=150)
        make_tree_sortable(self.interest_tree)
        
        # Buttons for interest management
        interest_buttons = ttk.Frame(detail_frame)
        interest_buttons.pack(fill='x', pady=5)
        
        ttk.Button(interest_buttons, text="Negotiate Trade", 
                  command=self.start_trade_negotiation).pack(side='left', padx=5)
        ttk.Button(interest_buttons, text="Decline Interest", 
                  command=self.decline_interest).pack(side='left', padx=5)
        
        interest_scrollbar = ttk.Scrollbar(detail_frame, orient='vertical', command=self.interest_tree.yview)
        self.interest_tree.configure(yscrollcommand=interest_scrollbar.set)
        
        self.interest_tree.pack(side='left', fill='both', expand=True)
        interest_scrollbar.pack(side='right', fill='y')
    
    def load_trade_block(self):
        """Load current trade block data."""
        # Initialize trade block if it doesn't exist
        if not hasattr(self.parent.user_team, 'trade_block'):
            self.parent.user_team.trade_block = []
        
        self.update_trade_block_display()
        self.update_interest_display()
    
    def add_to_trade_block(self):
        """Add a player to the trade block."""
        # Create player selection dialog
        self.create_player_selection_dialog()
    
    def create_player_selection_dialog(self):
        """Create dialog to select players for trade block."""
        dialog = tk.Toplevel(self)
        dialog.title("Add Player to Trade Block")
        dialog.geometry("600x400")
        dialog.configure(background=self.parent.BG_COLOR)
        
        # Available players
        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Select players to add to trade block:", 
                 style='Title.TLabel').pack(pady=10)
        
        # Player list
        columns = ('Name', 'Position', 'Age', 'Overall', 'Salary')
        player_tree = ttk.Treeview(frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            player_tree.heading(col, text=col)
            player_tree.column(col, width=120)
        make_tree_sortable(player_tree)
        
        # Populate with roster players not already on trade block
        current_block = getattr(self.parent.user_team, 'trade_block', [])
        for player in self.parent.user_team.roster:
            if player not in current_block:
                salary = getattr(player.contract, 'salary', 750000) if player.contract else 750000
                player_tree.insert('', 'end', values=(
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    player.overall_rating(),
                    f"${salary:,}"
                ))
        
        player_tree.pack(fill='both', expand=True)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=10)
        
        def add_selected():
            selection = player_tree.selection()
            if selection:
                for item in selection:
                    player_name = player_tree.item(item)['values'][0]
                    player = next((p for p in self.parent.user_team.roster if p.full_name == player_name), None)
                    if player:
                        if not hasattr(self.parent.user_team, 'trade_block'):
                            self.parent.user_team.trade_block = []
                        if player not in self.parent.user_team.trade_block:
                            self.parent.user_team.trade_block.append(player)
                
                self.update_trade_block_display()
                dialog.destroy()
        
        ttk.Button(btn_frame, text="Add Selected", command=add_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def remove_from_trade_block(self):
        """Remove selected player from trade block."""
        selection = self.block_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a player to remove.")
            return
        
        for item in selection:
            player_name = self.block_tree.item(item)['values'][0]
            player = next((p for p in getattr(self.parent.user_team, 'trade_block', []) 
                          if p.full_name == player_name), None)
            if player:
                self.parent.user_team.trade_block.remove(player)
        
        self.update_trade_block_display()
    
    def generate_trade_interest(self):
        """Generate interest from other teams."""
        if not hasattr(self.parent.user_team, 'trade_block') or not self.parent.user_team.trade_block:
            tk.messagebox.showinfo("No Players", "Add players to your trade block first.")
            return
        
        import random
        
        # Generate interest for each player on trade block
        for player in self.parent.user_team.trade_block:
            # Random teams might be interested
            interested_teams = random.sample(self.parent.league.teams, random.randint(1, 4))
            for team in interested_teams:
                if team != self.parent.user_team:
                    if player not in self.interested_teams:
                        self.interested_teams[player] = []
                    
                    interest_level = random.choice(['Low', 'Medium', 'High'])
                    self.interested_teams[player].append({
                        'team': team,
                        'interest_level': interest_level,
                        'status': 'Active'
                    })
        
        self.update_interest_display()
        tk.messagebox.showinfo("Interest Generated", "Trade interest has been generated for your players!")
    
    def update_trade_block_display(self):
        """Update the trade block display."""
        # Clear current items
        for item in self.block_tree.get_children():
            self.block_tree.delete(item)
        
        # Add trade block players
        trade_block = getattr(self.parent.user_team, 'trade_block', [])
        for player in trade_block:
            salary = getattr(player.contract, 'salary', 750000) if player.contract else 750000
            years_left = getattr(player.contract, 'years_remaining', 0) if player.contract else 0
            
            # Calculate interest level
            interest_count = len(self.interested_teams.get(player, []))
            if interest_count == 0:
                interest_level = "None"
            elif interest_count <= 2:
                interest_level = "Low"
            elif interest_count <= 4:
                interest_level = "Medium"
            else:
                interest_level = "High"
            
            self.block_tree.insert('', 'end', values=(
                player.full_name,
                str(player.primary_position),
                player.age,
                player.overall_rating(),
                f"${salary:,}",
                years_left,
                interest_level
            ))
        set_tree_empty_state(
            self.block_tree,
            "Your trade block is empty \u2014 add players to start fielding offers")
    
    def update_interest_display(self):
        """Update the interest display."""
        # Clear current items
        for item in self.interest_tree.get_children():
            self.interest_tree.delete(item)
        
        # Update summary
        total_players = len(getattr(self.parent.user_team, 'trade_block', []))
        total_interest = sum(len(interests) for interests in self.interested_teams.values())
        
        summary_text = f"Players on Trade Block: {total_players}\n"
        summary_text += f"Total Interest Expressions: {total_interest}\n"
        summary_text += f"Active Negotiations: 0\n"  # Would track actual negotiations
        
        self.interest_summary.delete(1.0, tk.END)
        self.interest_summary.insert(1.0, summary_text)
        
        # Add detailed interest
        for player, interests in self.interested_teams.items():
            for interest in interests:
                self.interest_tree.insert('', 'end', values=(
                    player.full_name,
                    interest['team'].team_name,
                    interest['interest_level'],
                    "Considering",  # Your interest level
                    interest['status']
                ))
        set_tree_empty_state(self.interest_tree, "No trade interest yet")
    
    def get_other_teams(self):
        """Get list of other teams."""
        return [team.team_name for team in self.parent.league.teams 
                if team != self.parent.user_team]
    
    def on_team_selected(self, event=None):
        """Handle team selection."""
        # Would populate with selected team's trade block
        # For now, show placeholder
        selected_team = self.team_var.get()
        if selected_team:
            # Clear and show message
            for item in self.other_tree.get_children():
                self.other_tree.delete(item)
            
            # Find team and show some players as "available"
            team = next((t for t in self.parent.league.teams if t.team_name == selected_team), None)
            if team:
                import random
                available_players = random.sample(team.roster, min(5, len(team.roster)))
                for player in available_players:
                    salary = getattr(player.contract, 'salary', 750000) if player.contract else 750000
                    self.other_tree.insert('', 'end', values=(
                        team.team_name,
                        player.full_name,
                        str(player.primary_position),
                        player.age,
                        player.overall_rating(),
                        f"${salary:,}",
                        random.choice(['Available', 'Limited Interest', 'High Price'])
                    ))
    
    def refresh_other_blocks(self):
        """Refresh other teams' trade blocks."""
        self.on_team_selected()
    
    def express_interest(self, event=None):
        """Express interest in a player."""
        selection = self.other_tree.selection()
        if selection:
            item = selection[0]
            values = self.other_tree.item(item)['values']
            team_name, player_name = values[0], values[1]
            
            tk.messagebox.showinfo("Interest Expressed", 
                                 f"You have expressed interest in {player_name} from {team_name}.\n\n"
                                 f"The team will consider your interest and may respond with trade proposals.")
    
    def start_trade_negotiation(self):
        """Start trade negotiation."""
        selection = self.interest_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select an interest to negotiate.")
            return
        
        values = self.interest_tree.item(selection[0])['values']
        player_name, team_name = values[0], values[1]
        
        tk.messagebox.showinfo("Trade Negotiation", 
                             f"Starting trade negotiation for {player_name} with {team_name}.\n\n"
                             f"This would open the trade negotiation interface.")
    
    def decline_interest(self):
        """Decline trade interest."""
        selection = self.interest_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select an interest to decline.")
            return
        
        # Remove from interest tracking
        self.interest_tree.delete(selection[0])
        tk.messagebox.showinfo("Interest Declined", "Trade interest has been declined.")

class WaiversWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Waivers")
        self.geometry("1000x700")
        self.configure(background=parent.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create top panel with instructions
        instruction_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        instruction_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(instruction_frame, text="Waiver Wire Management", font=(parent.FONT_FAMILY, 16, 'bold'), 
                 style='Heading.TLabel').pack(anchor='w', padx=10, pady=5)
        
        ttk.Label(instruction_frame, text="Players must clear waivers when being sent down to the AHL if they have played " 
                                         "more than 160 NHL games, or are older than 25 years. "
                                         "Players on waivers can be claimed by other teams (starting with the lowest ranked team).", 
                 wraplength=900, style='Muted.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Create notebook with tabs
        self.notebook = ttk.Notebook(main_frame, style='Modern.TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=5, pady=10)
        
        # Create tabs
        my_players_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        waiver_wire_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        
        self.notebook.add(my_players_frame, text="Waiver-Eligible Players")
        self.notebook.add(waiver_wire_frame, text="Waiver Wire")
        
        # My players tab
        columns = {'name': ('Player', 200), 'age': ('Age', 40), 'pos': ('Pos', 50), 
                  'ovr': ('OVR', 50), 'games': ('NHL Games', 80), 
                  'salary': ('Salary', 100), 'actions': ('Actions', 150)}
        
        self.eligible_tree = parent._create_treeview(my_players_frame, columns, 20)
        self.eligible_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create a button frame for my players
        my_buttons_frame = ttk.Frame(my_players_frame, style='Panel.TFrame')
        my_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(my_buttons_frame, text="Place Selected on Waivers", 
                  command=self.place_on_waivers).pack(side='left', padx=5)
        
        # Waiver wire tab
        wire_columns = {'name': ('Player', 200), 'age': ('Age', 40), 'pos': ('Pos', 50), 
                       'ovr': ('OVR', 50), 'games': ('NHL Games', 80), 
                       'salary': ('Salary', 100), 'team': ('Current Team', 150),
                       'actions': ('Actions', 150)}
        
        self.waiver_tree = parent._create_treeview(waiver_wire_frame, wire_columns, 20)
        self.waiver_tree.pack(fill='both', expand=True, padx=5, pady=5)
        add_player_context_menu(self.waiver_tree, self)
        
        # Create a button frame for waiver wire
        wire_buttons_frame = ttk.Frame(waiver_wire_frame, style='Panel.TFrame')
        wire_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(wire_buttons_frame, text="Claim Selected Player", 
                  command=self.claim_from_waivers).pack(side='left', padx=5)
                  
        self.populate_eligible_players()
        self.populate_waiver_wire()
        
    def is_waiver_eligible(self, player):
        """Determine if player is waiver-eligible based on age and NHL games played."""
        # Players over 25 or with more than 160 NHL games require waivers
        nhl_games = getattr(player, 'nhl_games_played', 0)
        return player.age >= 25 or nhl_games >= 160
        
    def populate_eligible_players(self):
        """Populate the tree with waiver-eligible players from user's team."""
        self.eligible_tree.delete(*self.eligible_tree.get_children())
        
        # Get all NHL roster players who would be eligible for waivers
        eligible_players = [p for p in self.parent.user_team.roster if self.is_waiver_eligible(p)]
        
        for player in eligible_players:
            player_values = (
                player.full_name,
                player.age,
                player.primary_position.name,
                player.overall_rating(),
                getattr(player, 'nhl_games_played', 0),
                f"${player.contract.salary:,}",
                "Place on Waivers"
            )
            item = self.eligible_tree.insert('', 'end', values=player_values)
            self.eligible_tree.item(item, tags=(str(player.id),))
            
        # Configure row click event
        self.eligible_tree.bind('<ButtonRelease-1>', self.on_eligible_click)

        set_tree_empty_state(self.eligible_tree, "No waiver-eligible players on your roster")
        
    def populate_waiver_wire(self):
        """Populate the tree with players currently on the waiver wire."""
        self.waiver_tree.delete(*self.waiver_tree.get_children())
        
        for player in self.parent.waiver_list:
            player_values = (
                player.full_name,
                player.age,
                player.primary_position.name,
                player.overall_rating(),
                getattr(player, 'nhl_games_played', 0),
                f"${player.contract.salary:,}",
                player.team_name,
                "Claim"
            )
            item = self.waiver_tree.insert('', 'end', values=player_values)
            self.waiver_tree.item(item, tags=(str(player.id),))
            
        # Configure row click event
        self.waiver_tree.bind('<ButtonRelease-1>', self.on_waiver_click)

        set_tree_empty_state(self.waiver_tree, "The waiver wire is empty")
        
    def on_eligible_click(self, event):
        """Handle click on eligible players tree."""
        region = self.eligible_tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.eligible_tree.identify_row(event.y)
            column = self.eligible_tree.identify_column(event.x)
            
            # If clicking on the Actions column (column #7)
            if column == '#7':
                self.place_on_waivers(item)
                
    def on_waiver_click(self, event):
        """Handle click on waiver wire tree."""
        region = self.waiver_tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.waiver_tree.identify_row(event.y)
            column = self.waiver_tree.identify_column(event.x)
            
            # If clicking on the Actions column (column #8)
            if column == '#8':
                self.claim_from_waivers(item)
    
    def place_on_waivers(self, item=None):
        """Place the selected player on waivers."""
        if not item:
            selected = self.eligible_tree.selection()
            if not selected:
                messagebox.showinfo("Selection Required", "Please select a player to place on waivers.")
                return
            item = selected[0]
            
        player_id = int(self.eligible_tree.item(item, "tags")[0])
        player = next((p for p in self.parent.user_team.roster if p.id == player_id), None)
        
        if player:
            confirm = qol_confirm(self, "Confirm Waiver",
                                  f"Place {player.full_name} on waivers? "
                                  "Other teams will have a chance to claim them.",
                                  confirm_text="Place on Waivers")
            if confirm:
                # Add to waiver list
                player.on_waivers = True
                player.waiver_days = 2  # Players stay on waivers for 2 days
                self.parent.waiver_list.append(player)
                
                # Add to news log
                self.parent.add_news(f"{player.full_name} placed on waivers by {self.parent.user_team.team_name}.")
                
                # Update the views
                self.populate_eligible_players()
                self.populate_waiver_wire()
                messagebox.showinfo("Player on Waivers", 
                                   f"{player.full_name} has been placed on waivers. "
                                   "They will remain on waivers for 2 days, during which time other teams may claim them.")
    
    def claim_from_waivers(self, item=None):
        """Claim a player from the waiver wire."""
        if not item:
            selected = self.waiver_tree.selection()
            if not selected:
                messagebox.showinfo("Selection Required", "Please select a player to claim from waivers.")
                return
            item = selected[0]
            
        player_id = int(self.waiver_tree.item(item, "tags")[0])
        player = next((p for p in self.parent.waiver_list if p.id == player_id), None)
        
        if player:
            # Check if user's team has roster space
            if len(self.parent.user_team.roster) >= 23:
                messagebox.showerror("Roster Full", 
                                    "Your NHL roster is full. Please release or reassign a player before claiming from waivers.")
                return
                
            # Check salary cap compliance
            if player.contract.salary > self.parent.user_team.cap_space:
                messagebox.showerror("Cap Space Issue", 
                                    f"You don't have enough cap space to add this player's ${player.contract.salary:,} salary.")
                return
                
            confirm = qol_confirm(self, "Confirm Claim",
                                  f"Claim {player.full_name} from waivers? "
                                  "They will be added to your NHL roster.",
                                  confirm_text="Claim Player")
            if confirm:
                # Remove from previous team
                old_team = next((t for t in self.parent.league.teams if t.team_name == player.team_name), None)
                if old_team:
                    old_team.remove_player(player)
                
                # Remove from waiver list
                self.parent.waiver_list.remove(player)
                player.on_waivers = False
                player.waiver_days = 0
                
                # Add to user team
                self.parent.user_team.add_player(player)
                
                # Add to news log
                self.parent.add_news(f"{player.full_name} claimed off waivers by {self.parent.user_team.team_name}.")
                
                # Update views
                self.populate_waiver_wire()
                messagebox.showinfo("Player Claimed", 
                                   f"{player.full_name} has been claimed from waivers and added to your NHL roster.")
                
                # Refresh the main roster view if it's open
                if 'roster' in self.parent.open_windows and self.parent.open_windows['roster'].winfo_exists():
                    self.parent.open_windows['roster'].populate_trees()

class ContractExtensionsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Contract Extensions")
        self.geometry("1000x700")
        self.configure(background=parent.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create top panel with instructions
        instruction_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        instruction_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(instruction_frame, text="Contract Extensions", font=(parent.FONT_FAMILY, 16, 'bold'), 
                 style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        ttk.Label(instruction_frame, text="Negotiate extensions with players entering the final year of their contract. "
                                         "Per NHL rules, you can extend contracts at any time in the final year.", 
                 wraplength=900, style='Info.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Create notebook with tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, padx=5, pady=10)
        
        # Create tabs
        expiring_frame = ttk.Frame(notebook, style='Tab.TFrame')
        all_contracts_frame = ttk.Frame(notebook, style='Tab.TFrame')
        
        notebook.add(expiring_frame, text="Expiring Contracts")
        notebook.add(all_contracts_frame, text="All Contracts")
        
        # Expiring contracts tab
        columns = {'name': ('Player', 200), 'age': ('Age', 40), 'pos': ('Pos', 50), 
                  'ovr': ('OVR', 50), 'pot': ('POT', 50), 'salary': ('Current Salary', 120), 
                  'market': ('Market Value', 120), 'actions': ('Actions', 150)}
        
        self.expiring_tree = parent._create_treeview(expiring_frame, columns, 20)
        self.expiring_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # All contracts tab
        self.all_contracts_tree = parent._create_treeview(all_contracts_frame, columns, 20)
        self.all_contracts_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Add footer with controls
        footer_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        footer_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(footer_frame, text="Negotiate Selected", command=self.negotiate_selected).pack(side='left', padx=5)
        ttk.Button(footer_frame, text="Auto-Negotiate All", command=self.auto_negotiate_all).pack(side='left', padx=5)
        ttk.Button(footer_frame, text="Close", command=self.destroy).pack(side='right', padx=5)
        
        self.populate_tables()
        
    def populate_tables(self):
        """Populate the contract tables with data."""
        self.expiring_tree.delete(*self.expiring_tree.get_children())
        self.all_contracts_tree.delete(*self.all_contracts_tree.get_children())
        
        team = self.parent.user_team
        
        # Tree data maps to retrieve player objects
        self.parent.tree_maps[self.expiring_tree] = {}
        self.parent.tree_maps[self.all_contracts_tree] = {}
        
        # Sort players by overall rating
        sorted_players = sorted(team.roster, key=lambda p: p.overall_rating(), reverse=True)
        
        for player in sorted_players:
            # Calculate market value based on player attributes and age
            market_value = self.calculate_market_value(player)
            
            values = (
                player.full_name,
                player.age,
                player.primary_position.value,
                player.overall_rating(),
                player.potential_grade,
                f"${player.contract.salary:,}",
                f"${market_value:,}",
                "Negotiate"
            )
            
            # Add to All Contracts tab
            item_id = self.all_contracts_tree.insert('', 'end', values=values)
            self.parent.tree_maps[self.all_contracts_tree][item_id] = player
            
            # Add to Expiring Contracts tab if contract expires this season
            if player.contract.years_remaining <= 1:
                item_id = self.expiring_tree.insert('', 'end', values=values, tags=('expiring',))
                self.parent.tree_maps[self.expiring_tree][item_id] = player
                
        # Add right-click context menu for trees
        self.expiring_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.expiring_tree))
        self.all_contracts_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.all_contracts_tree))
        
        # Add double-click binding for negotiation
        self.expiring_tree.bind("<Double-1>", lambda e: self.negotiate_from_event(e, self.expiring_tree))
        self.all_contracts_tree.bind("<Double-1>", lambda e: self.negotiate_from_event(e, self.all_contracts_tree))
        
    def calculate_market_value(self, player):
        """Calculate a player's market value based on attributes, age, position, etc."""
        # Base value determined by overall rating (100-scale: 74 OVR starter -> $3.5M)
        base_value = max(750000, (player.overall_rating() - 60) * 250000)
        
        # Age modifier - players in their prime (23-29) get premium
        age_modifier = 1.0
        if 23 <= player.age <= 29:
            age_modifier = 1.2
        elif player.age >= 30:
            # Declining value with age
            age_modifier = max(0.5, 1.0 - ((player.age - 30) * 0.05))
        
        # Position modifier - centers and first-line defensemen get premium
        position_modifier = 1.0
        if player.primary_position == PlayerPosition.CENTER:
            position_modifier = 1.15
        elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            position_modifier = 1.1
        elif player.primary_position == PlayerPosition.GOALIE:
            # Goalies have different value curve
            position_modifier = 1.0 if player.overall_rating() >= 80 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if player.age <= 25:
            potential_map = {'A': 1.5, 'B': 1.3, 'C': 1.1, 'D': 1.0, 'F': 0.9}
            potential_modifier = potential_map.get(player.potential_grade, 1.0)
        
        # Stats performance bonus (simplified for now)
        performance_bonus = player.stats.goals * 50000 + player.stats.assists * 30000
        
        # Calculate final market value
        market_value = (base_value * age_modifier * position_modifier * potential_modifier) + performance_bonus
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
    
    def _show_context_menu(self, event, tree):
        """Show right-click context menu for the tree."""
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
            
        tree.selection_set(item_id)
        player = self.parent.tree_maps.get(tree, {}).get(item_id)
        if not player:
            return
            
        menu = tk.Menu(self, tearoff=0, bg="#3C3C3C", fg="white")
        menu.add_command(label="Negotiate Extension", 
                        command=lambda: self.open_negotiation_window(player))
        menu.add_command(label="View Player Profile", 
                        command=lambda: self.parent.open_player_profile(player))
        menu.tk_popup(event.x_root, event.y_root)
    
    def negotiate_from_event(self, event, tree):
        """Handle double-click on tree item."""
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
            
        player = self.parent.tree_maps.get(tree, {}).get(item_id)
        if player:
            self.open_negotiation_window(player)
    
    def open_negotiation_window(self, player):
        """Open the negotiation window for a specific player."""
        if player.contract.years_remaining > 1:
            messagebox.showinfo("Not Eligible", 
                               f"{player.full_name} has {player.contract.years_remaining} years left on their contract. "
                               f"Per NHL rules, players can only negotiate extensions in the final year of their contract.")
            return
            
        # Calculate recommended contract offer
        market_value = self.calculate_market_value(player)
        max_years = 8  # NHL max extension is 8 years for own players
        
        # Open Advanced Contract Negotiation Window
        self.parent.open_windows['extension_negotiation'] = ExtensionNegotiationWindow(
            self.parent, player, market_value, max_years)
        self.parent.open_windows['extension_negotiation'].focus_set()
    
    def negotiate_selected(self):
        """Negotiate with the selected player."""
        selection = self.expiring_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a player to negotiate with.")
            return
            
        item_id = selection[0]
        player = self.parent.tree_maps.get(self.expiring_tree, {}).get(item_id)
        if player:
            self.open_negotiation_window(player)
    
    def auto_negotiate_all(self):
        """Auto-negotiate with all expiring contracts."""
        team = self.parent.user_team
        expiring_players = [p for p in team.roster if p.contract.years_remaining <= 1]
        
        if not expiring_players:
            messagebox.showinfo("No Expiring Contracts", "There are no players with expiring contracts.")
            return
            
        result_messages = []
        for player in expiring_players:
            market_value = self.calculate_market_value(player)
            
            # Determine years based on age and value
            if player.age <= 25:
                years = min(8, random.randint(4, 6))  # Young players get longer deals
            elif player.age <= 30:
                years = random.randint(3, 5)  # Prime-age players
            else:
                years = random.randint(1, 3)  # Older players get shorter deals
                
            # Adjust offer based on player value
            offer_percentage = random.uniform(0.9, 1.1)  # Offer between 90-110% of market value
            salary_offer = int(market_value * offer_percentage)
            
            # Simulate negotiation
            accepted = self.simulate_negotiation(player, salary_offer, years)
            
            if accepted:
                # Update player contract
                player.contract.salary = salary_offer
                player.contract.years_remaining = years
                result_messages.append(f"{player.full_name}: Accepted {years} years at ${salary_offer:,}")
            else:
                result_messages.append(f"{player.full_name}: Rejected {years} years at ${salary_offer:,}")
        
        # Show results
        result_window = tk.Toplevel(self)
        result_window.title("Auto-Negotiation Results")
        result_window.geometry("500x400")
        result_window.configure(background=self.parent.BG_COLOR)
        
        ttk.Label(result_window, text="Contract Extension Results", 
                font=(self.parent.FONT_FAMILY, 14, 'bold')).pack(pady=10)
        
        result_text = tk.Text(result_window, width=60, height=20, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        result_text.pack(pady=10, padx=10, fill='both', expand=True)
        
        for msg in result_messages:
            result_text.insert('end', msg + '\n')
        
        ttk.Button(result_window, text="Close", command=result_window.destroy).pack(pady=10)
        
        # Refresh data
        self.populate_tables()
    
    def simulate_negotiation(self, player, salary_offer, years):
        """Simulate contract negotiation based on player expectations."""
        # Calculate minimum acceptable salary based on overall rating and age
        # (100-scale: ~75% of the market-value base curve, NHL-minimum floor)
        min_salary = max(750000, (player.overall_rating() - 60) * 187500)
        
        # Adjust for age
        if player.age >= 30:
            min_salary *= max(0.5, 1.0 - ((player.age - 30) * 0.05))
        
        # Chance of accepting depends on how good the offer is
        acceptance_chance = 0.5  # Base chance
        
        # Adjust based on salary offered vs minimum expected
        if salary_offer >= min_salary * 1.2:
            acceptance_chance += 0.4  # Great offer
        elif salary_offer >= min_salary * 1.1:
            acceptance_chance += 0.25  # Good offer
        elif salary_offer >= min_salary:
            acceptance_chance += 0.1  # Fair offer
        else:
            acceptance_chance -= 0.3  # Poor offer
        
        # Adjust based on years
        ideal_years = 8 if player.age <= 25 else 5 if player.age <= 30 else 2
        years_diff = abs(years - ideal_years)
        
        if years_diff == 0:
            acceptance_chance += 0.2  # Perfect term
        elif years_diff <= 1:
            acceptance_chance += 0.1  # Close to ideal term
        elif years_diff >= 3:
            acceptance_chance -= 0.2  # Far from ideal term
        
        # Adjust for player loyalty
        if hasattr(player, 'teamwork') and player.teamwork > 15:
            acceptance_chance += 0.1  # Loyal player
        
        # Final result
        return random.random() < max(0.05, min(0.95, acceptance_chance))

class ExtensionNegotiationWindow(tk.Toplevel):
    def __init__(self, parent, player, market_value, max_years):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.market_value = market_value
        self.max_years = max_years
        
        self.title(f"Negotiate Extension with {player.full_name}")
        self.geometry("700x600")
        self.configure(background=parent.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Player info section
        info_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        info_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(info_frame, text=f"{player.full_name} - {player.primary_position.value}", 
                 font=(parent.FONT_FAMILY, 16, 'bold'), style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Create two columns for player info
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(fill='x', padx=10, pady=5)
        
        # Left column
        left_col = ttk.Frame(details_frame)
        left_col.pack(side='left', fill='x', expand=True)
        
        ttk.Label(left_col, text=f"Age: {player.age}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(left_col, text=f"Overall Rating: {to_100_scale(player.overall_rating())}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(left_col, text=f"Potential: {player.potential_grade}", style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Right column
        right_col = ttk.Frame(details_frame)
        right_col.pack(side='right', fill='x', expand=True)
        
        ttk.Label(right_col, text=f"Current Salary: ${player.contract.salary:,}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(right_col, text=f"Years Remaining: {player.contract.years_remaining}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(right_col, text=f"Estimated Market Value: ${market_value:,}", style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Stats summary
        stats_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        stats_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(stats_frame, text="Season Statistics", font=(parent.FONT_FAMILY, 12, 'bold'), 
                 style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        stats_text = f"Goals: {player.stats.goals}   Assists: {player.stats.assists}   Points: {player.stats.points}"
        ttk.Label(stats_frame, text=stats_text, style='Info.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Contract negotiation section
        contract_frame = ttk.LabelFrame(main_frame, text="Contract Offer", )
        contract_frame.pack(fill='x', padx=5, pady=10)
        
        # Salary slider and entry
        salary_frame = ttk.Frame(contract_frame)
        salary_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(salary_frame, text="Salary per year:", style='Info.TLabel').pack(side='left')
        
        self.salary_var = tk.StringVar(master=self, value=f"{market_value:,}")
        salary_entry = ttk.Entry(salary_frame, textvariable=self.salary_var, width=15)
        salary_entry.pack(side='left', padx=10)
        
        # Min/recommended/max salary buttons
        salary_presets = ttk.Frame(contract_frame)
        salary_presets.pack(fill='x', padx=10, pady=5)
        
        min_salary = max(750000, int(market_value * 0.8))
        recommended_salary = market_value
        max_salary = int(market_value * 1.2)
        
        ttk.Button(salary_presets, text=f"Min (${min_salary:,})", 
                  command=lambda: self.salary_var.set(f"{min_salary:,}")).pack(side='left', padx=5)
        ttk.Button(salary_presets, text=f"Recommended (${recommended_salary:,})", 
                  command=lambda: self.salary_var.set(f"{recommended_salary:,}")).pack(side='left', padx=5)
        ttk.Button(salary_presets, text=f"Max (${max_salary:,})", 
                  command=lambda: self.salary_var.set(f"{max_salary:,}")).pack(side='left', padx=5)
        
        # Contract length
        years_frame = ttk.Frame(contract_frame)
        years_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(years_frame, text="Contract Length (years):", style='Info.TLabel').pack(side='left')
        
        self.years_var = tk.IntVar(master=self, value=min(5, max_years))
        years_scale = ttk.Scale(years_frame, from_=1, to=max_years, variable=self.years_var, 
                               orient='horizontal', length=200)
        years_scale.pack(side='left', padx=10)
        
        years_label = ttk.Label(years_frame, textvariable=self.years_var, style='Info.TLabel')
        years_label.pack(side='left')
        
        # No-trade clause
        ntc_frame = ttk.Frame(contract_frame)
        ntc_frame.pack(fill='x', padx=10, pady=10)
        
        self.ntc_var = tk.BooleanVar(master=self, value=False)
        ttk.Checkbutton(ntc_frame, text="Include No-Trade Clause", variable=self.ntc_var,
                       style='TCheckbutton').pack(side='left')
        
        # Signing bonus
        bonus_frame = ttk.Frame(contract_frame)
        bonus_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(bonus_frame, text="Signing Bonus ($):", style='Info.TLabel').pack(side='left')
        
        self.bonus_var = tk.StringVar(master=self, value="0")
        bonus_entry = ttk.Entry(bonus_frame, textvariable=self.bonus_var, width=15)
        bonus_entry.pack(side='left', padx=10)
        
        # Total contract value display
        self.total_value_var = tk.StringVar(master=self)
        total_frame = ttk.Frame(contract_frame)
        total_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(total_frame, text="Total Contract Value:", style='Info.TLabel', font=(parent.FONT_FAMILY, 12, 'bold')).pack(side='left')
        ttk.Label(total_frame, textvariable=self.total_value_var, style='Info.TLabel', font=(parent.FONT_FAMILY, 12, 'bold')).pack(side='left', padx=10)
        
        # Update total when values change
        self.years_var.trace_add('write', self.update_total)
        self.salary_var.trace_add('write', self.update_total)
        self.bonus_var.trace_add('write', self.update_total)
        
        # Initial update
        self.update_total()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', padx=5, pady=10)
        
        ttk.Button(button_frame, text="Submit Offer", command=self.submit_offer).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side='right', padx=5)
    
    def update_total(self, *args):
        """Update the total contract value display."""
        try:
            # Parse salary with commas
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = self.years_var.get()
            
            # Parse bonus
            bonus_str = self.bonus_var.get().replace(',', '')
            bonus = int(bonus_str) if bonus_str else 0
            
            total = (salary * years) + bonus
            self.total_value_var.set(f"${total:,}")
        except ValueError:
            self.total_value_var.set("Invalid input")
    
    def submit_offer(self):
        """Submit contract offer to the player."""
        try:
            # Parse salary with commas
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = self.years_var.get()
            
            # Parse bonus
            bonus_str = self.bonus_var.get().replace(',', '')
            bonus = int(bonus_str) if bonus_str else 0
            
            # Validate inputs
            if salary < 750000:
                messagebox.showerror("Invalid Salary", "Salary must be at least $750,000 (NHL minimum).")
                return
                
            if years < 1 or years > self.max_years:
                messagebox.showerror("Invalid Contract Length", 
                                   f"Contract length must be between 1 and {self.max_years} years.")
                return
                
            if bonus < 0:
                messagebox.showerror("Invalid Bonus", "Signing bonus cannot be negative.")
                return
            
            # Calculate likelihood of acceptance
            acceptance_chance = self.calculate_acceptance_chance(salary, years, bonus)
            
            # Simulate player decision
            accepted = random.random() < acceptance_chance
            
            if accepted:
                # Update player contract
                self.player.contract.salary = salary
                self.player.contract.years_remaining = years
                self.player.contract.signing_bonus = bonus
                self.player.contract.no_trade_clause = self.ntc_var.get()
                
                messagebox.showinfo("Offer Accepted", 
                                  f"{self.player.full_name} has accepted your contract extension offer.\n\n"
                                  f"{years} years at ${salary:,}/year\n"
                                  f"{'With' if self.ntc_var.get() else 'Without'} No-Trade Clause\n"
                                  f"Signing Bonus: ${bonus:,}")
                self.destroy()
            else:
                counter_years = min(years + random.randint(-1, 1), self.max_years)
                counter_salary = int(salary * random.uniform(1.05, 1.2))
                
                response = messagebox.askyesno("Offer Rejected", 
                                             f"{self.player.full_name} has rejected your contract extension offer.\n\n"
                                             f"Counter offer: {counter_years} years at ${counter_salary:,}/year\n\n"
                                             f"Would you like to accept this counter offer?")
                
                if response:
                    # Update player contract with counter offer
                    self.player.contract.salary = counter_salary
                    self.player.contract.years_remaining = counter_years
                    self.player.contract.signing_bonus = bonus
                    self.player.contract.no_trade_clause = self.ntc_var.get()
                    
                    messagebox.showinfo("Counter Offer Accepted", 
                                      f"You have accepted {self.player.full_name}'s counter offer.\n\n"
                                      f"{counter_years} years at ${counter_salary:,}/year")
                    self.destroy()
        
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for salary, years, and bonus.")
    
    def calculate_acceptance_chance(self, salary, years, bonus):
        """Calculate the likelihood of the player accepting the contract offer."""
        # Base acceptance chance
        chance = 0.5
        
        # Adjust based on salary vs market value
        salary_ratio = salary / self.market_value
        
        if salary_ratio >= 1.1:
            chance += 0.3  # Great offer
        elif salary_ratio >= 1.0:
            chance += 0.15  # Good offer
        elif salary_ratio >= 0.9:
            chance += 0.05  # Fair offer
        else:
            chance -= 0.3  # Poor offer
        
        # Adjust based on player age and contract length
        ideal_years = 8 if self.player.age <= 25 else 5 if self.player.age <= 30 else 2
        years_diff = abs(years - ideal_years)
        
        if years_diff == 0:
            chance += 0.15  # Perfect term
        elif years_diff <= 1:
            chance += 0.05  # Close to ideal term
        elif years_diff >= 4:
            chance -= 0.15  # Far from ideal term
        
        # Bonus adds slight bonus to acceptance
        if bonus > 0:
            chance += min(0.1, bonus / (salary * years) * 0.5)
        
        # No-trade clause adds value for veterans
        if self.ntc_var.get() and self.player.age >= 28:
            chance += 0.1
        
        # Cap the chance between 5% and 95%
        return max(0.05, min(0.95, chance))

class SetCaptainsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Set Captains")
        self.geometry("400x300")
        self.configure(background=parent.BG_COLOR)

        self.captain_var = tk.StringVar(master=self)
        self.alternate1_var = tk.StringVar(master=self)
        self.alternate2_var = tk.StringVar(master=self)

        self._create_widgets()
        self.load_captains()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill='both', expand=True)

        players = [p.full_name for p in self.parent.user_team.roster]

        ttk.Label(main_frame, text="Captain (C):").pack(pady=(0, 5))
        captain_combo = ttk.Combobox(main_frame, textvariable=self.captain_var, values=players, state='readonly')
        captain_combo.pack(fill='x', pady=(0, 10))

        ttk.Label(main_frame, text="Alternate Captain (A):").pack(pady=(0, 5))
        alt1_combo = ttk.Combobox(main_frame, textvariable=self.alternate1_var, values=players, state='readonly')
        alt1_combo.pack(fill='x', pady=(0, 10))
        
        ttk.Label(main_frame, text="Alternate Captain (A):").pack(pady=(0, 5))
        alt2_combo = ttk.Combobox(main_frame, textvariable=self.alternate2_var, values=players, state='readonly')
        alt2_combo.pack(fill='x', pady=(0, 10))

        ttk.Button(main_frame, text="Save Captains", command=self.save_captains).pack(pady=20)

    def load_captains(self):
        for p in self.parent.user_team.roster:
            if p.captaincy == 'C':
                self.captain_var.set(p.full_name)
            elif p.captaincy == 'A':
                if not self.alternate1_var.get():
                    self.alternate1_var.set(p.full_name)
                else:
                    self.alternate2_var.set(p.full_name)

    def save_captains(self):
        for p in self.parent.user_team.roster:
            p.captaincy = None

        captain_name = self.captain_var.get()
        alt1_name = self.alternate1_var.get()
        alt2_name = self.alternate2_var.get()

        for p in self.parent.user_team.roster:
            if p.full_name == captain_name:
                p.captaincy = 'C'
            elif p.full_name == alt1_name or p.full_name == alt2_name:
                p.captaincy = 'A'
        
        messagebox.showinfo("Captains Updated", "Team captaincy has been updated.")
        self.parent.update_all_views()
        self.destroy()

# --- Drag-and-Drop Edit Lines Window ---
class GMDashboardWindow(tk.Toplevel):
    """GM Dashboard: record, cap, contracts, top performers, vitals, staff."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("GM Dashboard")
        self.configure(background=parent.BG_COLOR)
        self.geometry("860x720")
        self._build()

    # ---------- helpers ----------
    def _card(self, master, title, r, c):
        card = ttk.Frame(master, style='Card.TFrame', padding=12)
        card.grid(row=r, column=c, sticky='nsew', padx=6, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _big(self, card, text):
        ttk.Label(card, text=text, style='TLabel',
                  font=(self.parent.FONT_FAMILY, 18, 'bold')).pack(anchor='w', pady=(2, 4))

    # ---------- build ----------
    def _build(self):
        team = self.parent.user_team
        league = self.parent.league
        st = league.standings.get(team.team_name, {"W": 0, "L": 0, "OTL": 0, "Points": 0})
        w, l, otl, pts = st.get("W", 0), st.get("L", 0), st.get("OTL", 0), st.get("Points", 0)
        gp = w + l + otl

        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(header, text=f"{team.city} {team.team_name}",
                  font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  style='TLabel').pack(side=tk.LEFT)
        season = getattr(league, 'season_year', '')
        ttk.Label(header, text=f"  Season {season}" if season else "",
                  style='Secondary.TLabel').pack(side=tk.LEFT)
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=(self.parent.FONT_FAMILY, 9, 'bold'),
                   padx=12, pady=5, command=self._refresh).pack(side=tk.RIGHT)

        self.grid_host = ttk.Frame(self, style='Panel.TFrame')
        self.grid_host.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        for i in range(2):
            self.grid_host.columnconfigure(i, weight=1)
        # NOTE: rows intentionally have no weight so each row sizes to its
        # tallest card; equal row weights clipped card content (labels cut off)
        self._fill_cards(team, league, st, w, l, otl, pts, gp)

    def _fill_cards(self, team, league, st, w, l, otl, pts, gp):
        for child in self.grid_host.winfo_children():
            child.destroy()

        # --- Record ---
        card = self._card(self.grid_host, "Record", 0, 0)
        self._big(card, f"{w} - {l} - {otl}")
        self._line(card, f"{pts} points in {gp} games", secondary=True)
        ordered = sorted(league.standings.items(),
                         key=lambda kv: kv[1].get("Points", 0), reverse=True)
        rank = next((i + 1 for i, (name, _s) in enumerate(ordered)
                     if name == team.team_name), None)
        if rank:
            self._line(card, f"League rank: {rank} of {len(ordered)}")
        if gp > 0:
            pace = pts / gp * 82
            self._line(card, f"82-game pace: {pace:.1f} pts", secondary=True)

        # --- Salary cap ---
        card = self._card(self.grid_host, "Salary Cap", 0, 1)
        payroll = team.payroll
        cap = team.salary_cap
        space = team.cap_space
        self._big(card, f"${space / 1e6:.2f}M")
        self._line(card, "cap space available", secondary=True)
        self._line(card, f"Payroll: ${payroll / 1e6:.2f}M / ${cap / 1e6:.1f}M")
        bar = ttk.Frame(card, style='Panel.TFrame')
        bar.pack(fill=tk.X, pady=(6, 2))
        frac = min(1.0, payroll / cap) if cap else 0
        fill = tk.Canvas(bar, height=10, bg='#232a3a', highlightthickness=0)
        fill.pack(fill=tk.X)
        fill.update_idletasks()
        bw = max(1, fill.winfo_width())
        color = '#00ceb8' if frac >= 0.95 else ('#e0a030' if frac >= 0.85 else '#2a9d8f')
        fill.create_rectangle(0, 0, bw * frac, 10, fill=color, outline='')
        self._line(card, f"{frac * 100:.0f}% of cap used", secondary=True)

        # --- Contracts ---
        card = self._card(self.grid_host, "Contracts", 1, 0)
        expiring = [p for p in team.roster
                    if getattr(p.contract, 'years_remaining', 99) <= 1]
        expiring.sort(key=lambda p: p.contract.salary, reverse=True)
        self._big(card, f"{len(expiring)}")
        self._line(card, "contracts expiring this season", secondary=True)
        for p in expiring[:4]:
            self._line(card, f"{p.full_name} — ${p.contract.salary / 1e6:.2f}M")

        # --- Top performers ---
        card = self._card(self.grid_host, "Top Scorers", 1, 1)
        skaters = [p for p in team.roster
                   if p.primary_position.value != 'G']
        skaters.sort(key=lambda p: p.stats.points, reverse=True)
        if skaters:
            lead = skaters[0]
            self._big(card, f"{lead.full_name}")
            self._line(card, f"{lead.stats.goals}G - {lead.stats.assists}A - "
                             f"{lead.stats.points}P in {lead.stats.games_played} GP",
                       secondary=True)
            for p in skaters[1:4]:
                self._line(card, f"{p.full_name}: {p.stats.points} pts "
                                 f"({p.stats.goals}G, {p.stats.assists}A)")
        else:
            self._line(card, "No skaters on roster", secondary=True)

        # --- Team vitals ---
        card = self._card(self.grid_host, "Team Vitals", 2, 0)
        try:
            chem = team.team_chemistry
        except Exception:
            chem = None
        if chem is not None:
            self._line(card, f"Chemistry: {chem}/100")
        if team.roster:
            avg_morale = sum(p.morale for p in team.roster) / len(team.roster)
            avg_age = sum(p.age for p in team.roster) / len(team.roster)
            self._line(card, f"Avg morale: {avg_morale:.1f}/10")
            self._line(card, f"Avg age: {avg_age:.1f} years")
            self._line(card, f"Roster size: {len(team.roster)} players")

        # --- Staff ---
        card = self._card(self.grid_host, "Staff", 2, 1)
        from game_classes import StaffRole
        staff = getattr(team, 'staff', [])
        gm = next((s for s in staff if s.role == StaffRole.GENERAL_MANAGER), None)
        hc = next((s for s in staff if s.role == StaffRole.HEAD_COACH), None)
        self._big(card, f"{len(staff)}")
        self._line(card, "staff employed", secondary=True)
        if gm:
            self._line(card, f"GM: {gm.full_name}")
        if hc:
            self._line(card, f"Head Coach: {hc.full_name}")

    def _refresh(self):
        team = self.parent.user_team
        league = self.parent.league
        st = league.standings.get(team.team_name, {"W": 0, "L": 0, "OTL": 0, "Points": 0})
        w, l, otl, pts = st.get("W", 0), st.get("L", 0), st.get("OTL", 0), st.get("Points", 0)
        self._fill_cards(team, league, st, w, l, otl, pts, w + l + otl)


class SeasonGoalsWindow(tk.Toplevel):
    """Season Goals: board expectation, live progress, milestones, youth watch."""

    EXPECTATIONS = [
        ("cup", "Stanley Cup"),
        ("contender", "Conf. Final"),
        ("playoffs", "Playoffs"),
        ("competitive", "Winning Record"),
        ("rebuild", "Rebuild"),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Season Goals")
        self.configure(background=parent.BG_COLOR)
        self.geometry("640x600")
        self._exp_var = tk.StringVar(
            master=self,
            value=getattr(parent.user_team, 'board_expectation', 'playoffs'))
        self._build()

    def _card(self, title):
        card = ttk.Frame(self, style='Card.TFrame', padding=12)
        card.pack(fill=tk.X, padx=12, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _set_expectation(self, key):
        self._exp_var.set(key)
        self.parent.user_team.board_expectation = key
        self._paint_pills()
        self._refresh_progress()

    def _paint_pills(self):
        for key, btn in self._pill_btns:
            btn.set_selected(self._exp_var.get() == key)

    def _build(self):
        team = self.parent.user_team
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(header, text="Season Goals",
                  font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  style='TLabel').pack(side=tk.LEFT)
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=(self.parent.FONT_FAMILY, 9, 'bold'),
                   padx=12, pady=5, command=self._refresh_progress).pack(side=tk.RIGHT)

        # Board expectation pills
        card = self._card("Board Expectation")
        self._line(card, "Set what the board expects this season. Saved automatically.",
                   secondary=True)
        row = ttk.Frame(card, style='Card.TFrame')
        row.pack(fill=tk.X, pady=(6, 2))
        self._pill_btns = []
        for key, label in self.EXPECTATIONS:
            b = PillButton(row, text=label, bg='#1a2233',
                           font=(self.parent.FONT_FAMILY, 9, 'bold'),
                           padx=11, pady=5,
                           command=lambda k=key: self._set_expectation(k))
            b.pack(side=tk.LEFT, padx=3, pady=2)
            self._pill_btns.append((key, b))
        self._paint_pills()

        # Live progress
        self.progress_card = self._card("Progress")
        self.progress_lines = ttk.Frame(self.progress_card, style='Card.TFrame')
        self.progress_lines.pack(fill=tk.X)

        # Milestones
        self.mile_card = self._card("Milestones")
        self.mile_lines = ttk.Frame(self.mile_card, style='Card.TFrame')
        self.mile_lines.pack(fill=tk.X)

        # Youth watch
        youth_card = self._card("Development Watch (U23)")
        youth = [p for p in team.roster if p.age <= 23]
        youth.sort(key=lambda p: p.potential_grade or 'Z')
        if youth:
            for p in youth[:4]:
                self._line(youth_card,
                           f"{p.full_name} ({p.primary_position.value}, {p.age}) — "
                           f"potential {p.potential_grade}, {p.stats.games_played} GP")
        else:
            self._line(youth_card, "No players aged 23 or under on the roster.",
                       secondary=True)

        self._refresh_progress()

    def _refresh_progress(self):
        for child in self.progress_lines.winfo_children():
            child.destroy()
        for child in self.mile_lines.winfo_children():
            child.destroy()
        team = self.parent.user_team
        league = self.parent.league
        st = league.standings.get(team.team_name, {"W": 0, "L": 0, "OTL": 0, "Points": 0})
        w, l, otl, pts = st["W"], st["L"], st["OTL"], st["Points"]
        gp = w + l + otl

        # Conference rank and playoff cut
        conf = getattr(team, 'conference', None)
        conf_teams = [t for t in league.teams
                      if getattr(t, 'conference', None) == conf] if conf else list(league.teams)
        conf_order = sorted(conf_teams,
                            key=lambda t: league.standings.get(t.team_name, {}).get("Points", 0),
                            reverse=True)
        rank = next((i + 1 for i, t in enumerate(conf_order)
                     if t.team_name == team.team_name), None)
        pace = (pts / gp * 82) if gp else 0

        def _mkline(master, text, secondary=False):
            ttk.Label(master, text=text,
                      style='Secondary.TLabel' if secondary else 'TLabel',
                      font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

        exp = self._exp_var.get()
        exp_label = dict(self.EXPECTATIONS)[exp]
        _mkline(self.progress_lines, f"Board expects: {exp_label}")
        if rank:
            _mkline(self.progress_lines,
                    f"Conference rank: {rank} of {len(conf_order)} — "
                    f"{w}-{l}-{otl}, {pts} pts ({pace:.1f} pace)")
        in_playoffs = rank is not None and rank <= 8
        verdicts = {
            "cup": "Decided in the playoffs — keep the team healthy.",
            "contender": "Decided in the playoffs — aim for home ice.",
            "playoffs": ("On track — currently in a playoff spot."
                         if in_playoffs else
                         "Off track — outside the playoff cut. Points needed."),
            "competitive": ("On track — winning record."
                            if w > l else
                            "Off track — need more wins than losses."),
            "rebuild": None,
        }
        if exp == "rebuild":
            kids = [p for p in team.roster if p.age <= 23 and p.stats.games_played >= 10]
            _mkline(self.progress_lines,
                    f"{len(kids)} youngster(s) playing regular minutes "
                    f"(10+ GP): " + (", ".join(p.full_name for p in kids[:4])
                                     if kids else "none yet"))
        elif verdicts[exp]:
            _mkline(self.progress_lines, verdicts[exp],
                    secondary=True)

        # Milestones (auto-evaluated)
        miles = [
            ("Winning record", w > l and gp > 0),
            ("Playoff position", bool(in_playoffs)),
            ("100-point pace", pace >= 100 and gp > 0),
            ("Top scorer at 70+ pt pace",
             any((p.stats.points / max(1, p.stats.games_played) * 82) >= 70
                 for p in team.roster
                 if p.primary_position.value != 'G' and p.stats.games_played >= 10)),
        ]
        for label, done in miles:
            mark = "✓" if done else "○"
            _mkline(self.mile_lines, f"{mark}  {label}")


class TeamAnalyticsWindow(tk.Toplevel):
    """Team Analytics: offense, defense, goalies, scoring mix, discipline."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Team Analytics")
        self.configure(background=parent.BG_COLOR)
        self.geometry("880x640")
        self._build()

    def _card(self, title, r, c):
        card = ttk.Frame(self.grid_host, style='Card.TFrame', padding=12)
        card.grid(row=r, column=c, sticky='nsew', padx=6, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _big(self, card, text):
        ttk.Label(card, text=text, style='TLabel',
                  font=(self.parent.FONT_FAMILY, 18, 'bold')).pack(anchor='w', pady=(2, 4))

    def _build(self):
        team = self.parent.user_team
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(header, text="Team Analytics",
                  font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  style='TLabel').pack(side=tk.LEFT)
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=(self.parent.FONT_FAMILY, 9, 'bold'),
                   padx=12, pady=5, command=self._refresh).pack(side=tk.RIGHT)

        self.grid_host = ttk.Frame(self, style='Panel.TFrame')
        self.grid_host.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        for i in range(2):
            self.grid_host.columnconfigure(i, weight=1)
        for i in range(3):
            self.grid_host.rowconfigure(i, weight=1)
        self._fill(team)

    def _fill(self, team):
        for child in self.grid_host.winfo_children():
            child.destroy()
        skaters = [p for p in team.roster if p.primary_position.value != 'G']
        goalies = [p for p in team.roster if p.primary_position.value == 'G']
        tgp = max(1, max([p.stats.games_played for p in team.roster] or [0]))

        gf = sum(p.stats.goals for p in skaters)
        shots = sum(p.stats.shots for p in skaters)
        ga = sum((p.stats.shots_against - p.stats.saves) for p in goalies)
        sa = sum(p.stats.shots_against for p in goalies)
        sv = sum(p.stats.saves for p in goalies)
        pim = sum(p.stats.penalties_in_minutes for p in team.roster)

        # Offense
        card = self._card("Offense", 0, 0)
        self._big(card, f"{gf / tgp:.2f}")
        self._line(card, "goals per game", secondary=True)
        self._line(card, f"{gf} goals in {tgp} team games")
        if shots:
            self._line(card, f"{shots / tgp:.1f} shots/game — "
                             f"{gf / shots * 100:.1f}% shooting")

        # Defense
        card = self._card("Defense", 0, 1)
        self._big(card, f"{ga / tgp:.2f}")
        self._line(card, "goals against per game", secondary=True)
        self._line(card, f"{ga} allowed in {tgp} team games")
        if sa:
            self._line(card, f"{sa / tgp:.1f} shots against/game — "
                             f"{sv / sa * 100:.1f}% team save%")

        # Goalies
        card = self._card("Goaltenders", 1, 0)
        if goalies:
            goalies.sort(key=lambda p: p.stats.games_played, reverse=True)
            for g in goalies[:4]:
                gp = g.stats.games_played
                gsa, gsv = g.stats.shots_against, g.stats.saves
                gga = gsa - gsv
                svp = f"{gsv / gsa * 100:.1f}%" if gsa else "—"
                ga_g = f"{gga / gp:.2f}" if gp else "—"
                self._line(card, f"{g.full_name}: {gp} GP, {svp} SV%, {ga_g} GA/G")
        else:
            self._line(card, "No goaltenders on roster", secondary=True)

        # Scoring by position
        card = self._card("Scoring Mix", 1, 1)
        pos_goals = {}
        for p in skaters:
            pos_goals[p.primary_position.value] = \
                pos_goals.get(p.primary_position.value, 0) + p.stats.goals
        total = max(1, sum(pos_goals.values()))
        for pos in ("C", "LW", "RW", "LD", "RD"):
            gls = pos_goals.get(pos, 0)
            bar = "■" * max(1, int(gls / total * 20)) if gls else "—"
            self._line(card, f"{pos:3s} {gls:3d} goals  {bar}")

        # Discipline
        card = self._card("Discipline", 2, 0)
        self._big(card, f"{pim / tgp:.1f}")
        self._line(card, "PIM per game", secondary=True)
        offenders = sorted(team.roster,
                           key=lambda p: p.stats.penalties_in_minutes,
                           reverse=True)[:3]
        for p in offenders:
            if p.stats.penalties_in_minutes:
                self._line(card, f"{p.full_name}: {p.stats.penalties_in_minutes} PIM")

        # Top scorers
        card = self._card("Top Scorers", 2, 1)
        skaters.sort(key=lambda p: p.stats.points, reverse=True)
        for p in skaters[:5]:
            s = p.stats
            ppg = s.points / max(1, s.games_played)
            self._line(card, f"{p.full_name}: {s.goals}G {s.assists}A "
                             f"({ppg:.2f} P/GP)")

    def _refresh(self):
        self._fill(self.parent.user_team)


class SalaryAnalyticsWindow(tk.Toplevel):
    """Salary Analytics: payroll mix by position, top cap hits, expiring money."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Salary Analytics")
        self.configure(background=parent.BG_COLOR)
        self.geometry("720x600")
        self._build()

    def _card(self, title):
        card = ttk.Frame(self, style='Card.TFrame', padding=12)
        card.pack(fill=tk.X, padx=12, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _build(self):
        team = self.parent.user_team
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(header, text="Salary Analytics",
                  font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  style='TLabel').pack(side=tk.LEFT)
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=(self.parent.FONT_FAMILY, 9, 'bold'),
                   padx=12, pady=5, command=self._refresh).pack(side=tk.RIGHT)
        self.body = ttk.Frame(self, style='Panel.TFrame')
        self.body.pack(fill=tk.BOTH, expand=True)
        self._fill()

    def _fill(self):
        for child in self.body.winfo_children():
            child.destroy()
        team = self.parent.user_team
        payroll = team.payroll
        cap = team.salary_cap

        # Overview
        card = self._card("Overview")
        self._line(card, f"Payroll: ${payroll:,}  •  Cap: ${cap:,}  •  "
                         f"Space: ${team.cap_space:,}")
        self._line(card, f"{payroll / cap * 100:.1f}% of cap committed"
                   if cap else "No cap set", secondary=True)

        # By position
        card = self._card("Payroll by Position")
        groups = {"Forwards": ("C", "LW", "RW"),
                  "Defense": ("LD", "RD"),
                  "Goalies": ("G",)}
        for label, poses in groups.items():
            members = [p for p in team.roster if p.primary_position.value in poses]
            spent = sum(p.contract.salary for p in members)
            share = spent / payroll * 100 if payroll else 0
            bar = "■" * max(1, int(share / 5)) if spent else "—"
            self._line(card, f"{label:9s} ${spent / 1e6:5.2f}M ({share:4.1f}%)  "
                             f"{bar}  [{len(members)} players]")

        # Top cap hits
        card = self._card("Top Cap Hits")
        top = sorted(team.roster, key=lambda p: p.contract.salary, reverse=True)[:8]
        for i, p in enumerate(top, 1):
            self._line(card, f"{i}. {p.full_name} ({p.primary_position.value}) — "
                             f"${p.contract.salary:,} × {p.contract.years_remaining} yr")

        # Expiring money
        card = self._card("Expiring Contracts")
        expiring = [p for p in team.roster if p.contract.years_remaining <= 1]
        freed = sum(p.contract.salary for p in expiring)
        self._line(card, f"{len(expiring)} contracts expire — "
                         f"${freed:,} comes off the books")
        for p in sorted(expiring, key=lambda p: p.contract.salary, reverse=True)[:5]:
            self._line(card, f"{p.full_name}: ${p.contract.salary:,}", secondary=True)

        # Dead cap from buyouts
        hits = getattr(team, 'buyout_cap_hits', {}) or {}
        if hits:
            card = self._card("Buyout Dead Cap")
            for yr in sorted(hits):
                self._line(card, f"{yr}: ${hits[yr]:,} dead cap")

    def _refresh(self):
        self._fill()


def buyout_schedule(player):
    """NHL buyout math. Returns (total_cost, annual_hit, buyout_years, rows).

    rows: list of (season_offset, cap_hit, savings) for each buyout year.
    """
    salary = player.contract.salary
    years = player.contract.years_remaining
    if years <= 0 or salary <= 0:
        return 0, 0, 0, []
    fraction = 1 / 3 if player.age < 26 else 2 / 3
    total_cost = salary * years * fraction
    buyout_years = 2 * years
    annual = total_cost / buyout_years
    rows = []
    for i in range(1, buyout_years + 1):
        if i <= years:
            savings = salary - annual
        else:
            savings = -annual
        rows.append((i, annual, savings))
    return total_cost, annual, buyout_years, rows


class BuyoutCalculatorWindow(tk.Toplevel):
    """Buyout Calculator: real NHL buyout math with execute."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Buyout Calculator")
        self.configure(background=parent.BG_COLOR)
        self.geometry("680x620")
        self._selected = None
        self._build()

    def _build(self):
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(header, text="Buyout Calculator",
                  font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  style='TLabel').pack(side=tk.LEFT)
        ttk.Label(header, text="NHL rules: 2/3 of remaining salary (1/3 if under 26), "
                               "spread over 2× remaining term",
                  style='Secondary.TLabel', wraplength=340,
                  justify='right').pack(side=tk.RIGHT)

        cols = ttk.Frame(self, style='Panel.TFrame')
        cols.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        left = ttk.Frame(cols, style='Card.TFrame', padding=10)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        ttk.Label(left, text="Roster", style='TLabel',
                  font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        self.lb = tk.Listbox(left, height=22, activestyle='none',
                             bg='#232a3a', fg='#ffffff',
                             selectbackground='#0d2b28', relief='flat',
                             highlightthickness=1,
                             highlightbackground='#2e2e38',
                             font=(self.parent.FONT_FAMILY, 10))
        self.lb.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.lb.bind('<<ListboxSelect>>', self._on_select)
        self._players = sorted(self.parent.user_team.roster,
                               key=lambda p: p.contract.salary, reverse=True)
        for p in self._players:
            self.lb.insert(tk.END,
                           f"{p.full_name} ({p.primary_position.value}) — "
                           f"${p.contract.salary / 1e6:.2f}M × {p.contract.years_remaining}")

        right = ttk.Frame(cols, style='Card.TFrame', padding=10)
        right.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        self.detail = ttk.Frame(right, style='Card.TFrame')
        self.detail.pack(fill=tk.BOTH, expand=True)
        self._show_placeholder()
        self.active_box = ttk.Frame(right, style='Card.TFrame', padding=4)
        self.active_box.pack(fill=tk.X, pady=(8, 0))
        self._render_active_buyouts()

    def _line(self, master, text, secondary=False, bold=False):
        ttk.Label(master, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=(self.parent.FONT_FAMILY, 10,
                        'bold' if bold else 'normal')).pack(anchor='w', pady=1)

    def _show_placeholder(self):
        for child in self.detail.winfo_children():
            child.destroy()
        self._line(self.detail, "Select a player to see", secondary=True)
        self._line(self.detail, "their buyout breakdown.", secondary=True)

    def _on_select(self, event=None):
        sel = self.lb.curselection()
        if not sel:
            return
        self._selected = self._players[sel[0]]
        self._render_detail()

    def _render_detail(self):
        for child in self.detail.winfo_children():
            child.destroy()
        p = self._selected
        self._line(self.detail, p.full_name, bold=True)
        self._line(self.detail,
                   f"Age {p.age} • {p.primary_position.value} • "
                   f"${p.contract.salary:,}/yr × {p.contract.years_remaining} yr",
                   secondary=True)
        total, annual, byears, rows = buyout_schedule(p)
        if not rows:
            self._line(self.detail, "No remaining term — nothing to buy out.",
                       secondary=True)
            return
        self._line(self.detail, f"Buyout cost: ${total:,.0f}", bold=True)
        self._line(self.detail,
                   f"Cap hit: ${annual:,.0f}/yr for {byears} years",
                   secondary=True)
        ttk.Separator(self.detail, orient='horizontal').pack(fill='x', pady=6)
        for i, hit, savings in rows:
            yr_label = f"Year {i}"
            if savings >= 0:
                txt = f"{yr_label}: cap hit ${hit:,.0f} — saves ${savings:,.0f}"
            else:
                txt = f"{yr_label}: cap hit ${hit:,.0f} — dead money"
            self._line(self.detail, txt, secondary=True)
        ttk.Separator(self.detail, orient='horizontal').pack(fill='x', pady=6)
        PillButton(self.detail, text="Execute Buyout", bg='#0e0e11',
                   font=(self.parent.FONT_FAMILY, 10, 'bold'),
                   padx=16, pady=7,
                   command=self._execute_buyout).pack(anchor='w', pady=(4, 0))

    def _render_active_buyouts(self):
        for child in self.active_box.winfo_children():
            child.destroy()
        team = self.parent.user_team
        hits = getattr(team, 'buyout_cap_hits', {}) or {}
        if hits:
            self._line(self.active_box, "Active buyout cap hits:", bold=True)
            for yr in sorted(hits):
                self._line(self.active_box, f"{yr}: ${hits[yr]:,.0f}", secondary=True)
        else:
            self._line(self.active_box, "No active buyouts.", secondary=True)

    def _execute_buyout(self):
        from tkinter import messagebox
        p = self._selected
        if not p:
            return
        total, annual, byears, rows = buyout_schedule(p)
        if not rows:
            return
        if not qol_confirm(
                self,
                "Confirm Buyout",
                f"Buy out {p.full_name}?\n\n"
                f"Cost: ${total:,.0f} spread as ${annual:,.0f}/yr "
                f"over {byears} years.\n"
                f"{p.full_name} will become a free agent.",
                confirm_text="Buy Out"):
            return
        team = self.parent.user_team
        league = self.parent.league
        season = getattr(league, 'season_year', 2026)
        hits = getattr(team, 'buyout_cap_hits', None)
        if hits is None:
            hits = {}
            team.buyout_cap_hits = hits
        for i, hit, _s in rows:
            yr = season + i - 1
            hits[yr] = hits.get(yr, 0) + hit
        if p in team.roster:
            team.roster.remove(p)
        p.team_name = "Free Agent"
        messagebox.showinfo("Buyout Complete",
                            f"{p.full_name} has been bought out and is now "
                            f"a free agent.\nDead cap: ${annual:,.0f}/yr for "
                            f"{byears} years.")
        self._selected = None
        self._show_placeholder()
        # rebuild listbox + active buyouts
        self.lb.delete(0, tk.END)
        self._players = sorted(team.roster,
                               key=lambda pl: pl.contract.salary, reverse=True)
        for pl in self._players:
            self.lb.insert(tk.END,
                           f"{pl.full_name} ({pl.primary_position.value}) — "
                           f"${pl.contract.salary / 1e6:.2f}M × {pl.contract.years_remaining}")
        self._render_active_buyouts()


class GameDetailWindow(tk.Toplevel):
    """Game Recap / Game Stats: scoring summary, team stats, three stars."""

    def __init__(self, parent, game_result, initial_tab="recap"):
        super().__init__(parent)
        self.parent = parent
        self.result = game_result
        self.title("Game Details")
        self.configure(background=parent.BG_COLOR)
        self.geometry("640x560")
        self._build(initial_tab)

    def _line(self, master, text, secondary=False, bold=False, size=10):
        ttk.Label(master, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=(self.parent.FONT_FAMILY, size,
                        'bold' if bold else 'normal')).pack(anchor='w', pady=1)

    def _build(self, initial_tab):
        r = self.result
        home, away = r['home_team'], r['away_team']
        hs, aws = r['home_score'], r['away_score']
        date = r['date']
        date_str = date.strftime("%b %d, %Y") if hasattr(date, 'strftime') else str(date)

        header = ttk.Frame(self, style='Panel.TFrame', padding=14)
        header.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(header, text=f"{away.team_name}  {aws}  @  {hs}  {home.team_name}",
                  style='TLabel',
                  font=(self.parent.FONT_FAMILY, 15, 'bold')).pack(anchor='center')
        sub = date_str
        if r.get('shootout'):
            sub += "  •  Shootout"
        elif r.get('overtime'):
            sub += "  •  Overtime"
        ttk.Label(header, text=sub, style='Secondary.TLabel',
                  font=(self.parent.FONT_FAMILY, 10)).pack(anchor='center')

        tabs = ttk.Frame(self, style='Panel.TFrame')
        tabs.pack(fill=tk.X, padx=12, pady=(0, 6))
        self.body = ttk.Frame(self, style='Card.TFrame', padding=12)
        self.body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self._tab_var = tk.StringVar(value=initial_tab)
        for key, label in (("recap", "Game Recap"), ("stats", "Game Stats")):
            PillButton(tabs, text=label, bg='#0e0e11',
                       font=(self.parent.FONT_FAMILY, 9, 'bold'),
                       padx=14, pady=6,
                       command=lambda k=key: self._show_tab(k)).pack(side=tk.LEFT, padx=(0, 6))
        self._show_tab(initial_tab)

    def _show_tab(self, tab):
        for child in self.body.winfo_children():
            child.destroy()
        if tab == "recap":
            self._fill_recap()
        else:
            self._fill_stats()

    def _roster_lookup(self):
        r = self.result
        by_id = {}
        for team in (r['home_team'], r['away_team']):
            for p in team.roster:
                by_id[p.id] = (p, team)
        return by_id

    def _fill_recap(self):
        r = self.result
        self._line(self.body, "Scoring Summary", bold=True, size=12)
        events = r.get('event_log') or []
        by_id = self._roster_lookup()
        goals = [e for e in events if e.get('type') == 'GOAL_ADVANCED']
        if not goals:
            self._line(self.body,
                       "Detailed scoring data is unavailable for this game.",
                       secondary=True)
        home_running = away_running = 0
        for i, e in enumerate(goals, 1):
            d = e.get('details', {})
            info = by_id.get(d.get('scorer_id'))
            if info:
                p, team = info
                name = p.full_name
                abbr = team.team_name
            else:
                name, abbr = "Unknown", "?"
            if abbr == r['home_team'].team_name:
                home_running += 1
            elif abbr == r['away_team'].team_name:
                away_running += 1
            gtype = d.get('goal_type', '').replace('_', ' ').title()
            xg = d.get('expected_goal')
            extra = f"  •  {gtype}" if gtype else ""
            extra += f"  •  xG {xg}" if xg is not None else ""
            self._line(self.body,
                       f"{i}. {name} ({abbr}){extra}   [{away_running}-{home_running}]",
                       secondary=True)
        notable = [n for n in (r.get('notable_events') or [])
                   if n.get('event') not in ('overtime',)]
        if notable:
            ttk.Separator(self.body, orient='horizontal').pack(fill='x', pady=8)
            self._line(self.body, "Notable", bold=True, size=12)
            for n in notable:
                who = ""
                pl = n.get('player')
                if pl is not None:
                    who = getattr(pl, 'full_name', str(pl)) + " — "
                self._line(self.body, f"{who}{n.get('event', '')}",
                           secondary=True)

    def _fill_stats(self):
        r = self.result
        self._line(self.body, "Team Stats", bold=True, size=12)
        events = r.get('event_log') or []
        by_id = self._roster_lookup()
        goals_h = goals_a = saves_h = saves_a = 0
        for e in events:
            d = e.get('details', {})
            if e.get('type') == 'GOAL_ADVANCED':
                info = by_id.get(d.get('scorer_id'))
                if info and info[1].team_name == r['home_team'].team_name:
                    goals_h += 1
                else:
                    goals_a += 1
            elif e.get('type') == 'SAVE_ADVANCED':
                info = by_id.get(d.get('goaltender_id'))
                if info and info[1].team_name == r['home_team'].team_name:
                    saves_h += 1
                else:
                    saves_a += 1
        shots_h = goals_h + saves_a   # home shots = home goals + away goalie saves
        shots_a = goals_a + saves_h
        rows = [
            ("Goals", goals_a, goals_h),
            ("Shots on Goal", shots_a, shots_h),
            ("Saves", saves_a, saves_h),
        ]
        a_name, h_name = r['away_team'].team_name, r['home_team'].team_name
        self._line(self.body, f"{'':22s}{a_name[:18]:>18s}  {h_name[:18]:>18s}",
                   secondary=True, bold=True)
        for label, av, hv in rows:
            self._line(self.body, f"{label:22s}{av:>18d}  {hv:>18d}",
                       secondary=True)
        if not events:
            self._line(self.body, "Detailed stats unavailable for this game.",
                       secondary=True)

        ratings = r.get('player_ratings') or {}
        stars = []
        for team_name, pmap in ratings.items():
            for pid, rating in pmap.items():
                info = by_id.get(pid)
                name = info[0].full_name if info else "Unknown"
                stars.append((rating, name, team_name))
        stars.sort(reverse=True)
        if stars:
            ttk.Separator(self.body, orient='horizontal').pack(fill='x', pady=8)
            self._line(self.body, "Three Stars", bold=True, size=12)
            medals = ["★", "★★", "★★★"]
            for i, (rating, name, tname) in enumerate(stars[:3]):
                self._line(self.body,
                           f"{medals[i]}  {name} ({tname}) — {rating}/10",
                           secondary=True)
