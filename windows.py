# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# windows.py
# Contains the classes for all the major pop-up windows in the application.

import tkinter as tk
from tkinter import ttk
from popup_system import (messagebox, InGamePopup)
import customtkinter as ctk
from game_classes import (StaffRole, PlayerPosition, to_100_scale)
import random
import os
import re
from player_context_menu import PlayerContextMenu, add_player_context_menu
from ui_widgets import PillButton
from manager_career import morale_label


def _mp_is_client(app):
    """True when this app instance is an MP client (not host, not SP)."""
    try:
        return getattr(app, "mp_client", None) is not None
    except Exception:
        return False


def _mp_route(app, action, params, on_sent=None):
    """Route a management action to the host in MP client mode.

    Returns True when routed -- the caller must NOT mutate local state.
    The host validates, applies to the canonical state, and the next
    STATE_SYNC refreshes the UI (the action_ack/action_rejected toast
    confirms the outcome). Returns False on the host / in single-player,
    where the caller keeps its normal local behavior.

    If the send itself fails, the action is CONSUMED (True): the caller
    must not fall through to its local branch, which would mutate a
    snapshot the next sync wipes. The user gets an honest error instead,
    and on_sent is NOT called -- success UX must live in on_sent, never
    after this call, or a failed send would show a false confirmation.
    """
    try:
        client = getattr(app, "mp_client", None)
        if client is None:
            return False
        p = dict(params or {})
        team = getattr(app, "user_team", None)
        p.setdefault("team_id",
                     getattr(team, "team_name", "") if team else "")
        try:
            client.send_action(action, p)
        except Exception as e:
            try:
                messagebox.showerror(
                    "Not Sent",
                    f"Couldn't reach the host ({e}). Nothing changed -- "
                    f"try again.")
            except Exception:
                pass
            return True
        if on_sent is not None:
            try:
                on_sent()
            except Exception:
                pass
        return True
    except Exception:
        return False


def _sfont(family, size, weight=""):
    """Scale-aware font tuple replacement (honors Settings -> Font size).

    Returns a live tkinter Font registered with ui_scale; changing the
    tier resizes open-window text in place. Falls back to a plain tuple
    when ui_scale is unavailable (headless stubs).
    """
    try:
        from ui_scale import font as _mkfont
        return _mkfont(family, size, weight)
    except Exception:
        return (family, size, weight) if weight else (family, size)


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
    dlg = InGamePopup(parent)
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


class RosterView(ctk.CTkFrame):
    """Roster Management (CustomTkinter): dark cards, modern tab bar,
    pill filters, styled stat tables, depth-chart tiles, cap tab."""

    # Tab keys in display order
    _TAB_ORDER = ('nhl', 'ahl', 'prospects', 'depth', 'cap')

    def __init__(self, parent, app=None):
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
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the RosterWindow wrapper
        self.configure(fg_color=BG)

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
        self.context_menu_manager = PlayerContextMenu(self.app)

        # Create the interface
        self.create_enhanced_interface()
        self._setup_tree_style()
        self.update_views()

        # Track window
        self.app.open_windows['roster'] = self

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

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

        # Build tabs lazily: only the initially visible tab's widgets are
        # created up front; the rest build on first selection. CTk widget
        # construction dominates screen-open cost, so this cuts per-open
        # widget count by ~80%. Data population always goes through the
        # normal refresh path, so lazily built tabs are current on arrival.
        self._tab_builders = {
            'nhl': self.create_enhanced_nhl_tab,
            'ahl': self.create_enhanced_ahl_tab,
            'prospects': self.create_enhanced_prospects_tab,
            'depth': self.create_depth_chart_tab,
            'cap': self.create_salary_cap_tab,
        }
        self._tabs_built = set()
        self._build_roster_tab(self._TAB_ORDER[0])
        try:
            self.tabview.configure(command=self._on_roster_tab_selected)
        except Exception:
            pass

        # Action buttons footer
        self.create_action_footer(main_container)

    def _build_roster_tab(self, key):
        """Build one tab's widgets on first use, then populate it."""
        if key in getattr(self, '_tabs_built', set()):
            return
        builder = getattr(self, '_tab_builders', {}).get(key)
        if builder is None:
            return
        self._tabs_built.add(key)
        builder()
        try:
            if key in ('nhl', 'ahl', 'prospects'):
                self.update_roster_tab(key)
            elif key == 'depth':
                self.refresh_depth_chart()
            elif key == 'cap':
                self.refresh_salary_cap()
        except (AttributeError, tk.TclError):
            pass

    def _on_roster_tab_selected(self):
        """CTkTabview change callback: build the newly shown tab on demand."""
        try:
            current_name = self.tabview.get()
        except Exception:
            return
        for key, tab_name in self._tab_names.items():
            if tab_name == current_name:
                self._build_roster_tab(key)
                break

    def _cap_numbers(self):
        """Shared payroll figures for the header and the Salary Cap tab.

        Uses the central cap accounting (roster + in-game buyouts + seeded
        real-life dead cap) so the header, the Salary Cap tab, trade
        validation, and the Next Day blocker always agree. Display only --
        cap rules themselves live in the sim.
        Returns (salary_cap, current_payroll, cap_space, dead_cap).
        """
        try:
            from salary_cap_system import cap_breakdown
            bd = cap_breakdown(self.app.user_team)
            return bd["cap"], bd["total"], bd["space"], bd["dead_cap"]
        except Exception:
            salary_cap = getattr(self.app.user_team, 'salary_cap', 104000000)
            current_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000))
                                 for p in self.app.user_team.roster)
            return salary_cap, current_salary, salary_cap - current_salary, 0

    def create_header_section(self, parent):
        """Create header with team overview and quick stats."""
        ct = self._ct
        header = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12)
        header.pack(fill="x", pady=(0, 4))

        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 4))

        self._heading(top, text=f"{self.app.user_team.team_name.upper()} ROSTER",
                      size=18).pack(side="left")

        # Quick roster stats on the right
        nhl_count = len(self.app.user_team.roster)
        ahl_count = len(self.app.user_team.ahl_roster)
        prospects_count = len(self.app.user_team.prospects)
        _, _, cap_space, _ = self._cap_numbers()
        stats_text = (f"NHL: {nhl_count}/23 | AHL: {ahl_count}/20 | "
                      f"Prospects: {prospects_count} | Cap Space: ${cap_space:,}")
        self.stats_label = self._body(top, text=stats_text, size=11)
        self.stats_label.pack(side="right")

        # Subtitle with season info
        try:
            season_year = self.app.league.season_year
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
            'eta': ('ETA', 60),
            'rights': ('Rights', 90),
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
                self.app.open_player_profile(p)

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
            # EHM/FM24: right-click any player name for the player menu
            try:
                from player_context_menu import bind_player_context
                for w in (tile, name_lbl, sub_lbl):
                    bind_player_context(w, player, self)
            except Exception:
                pass
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
        forwards = [p for p in self.app.user_team.roster
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
        defensemen = [p for p in self.app.user_team.roster
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

        goalies = [p for p in self.app.user_team.roster
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
        cap_percentage = (current_salary / salary_cap) * 100 if salary_cap else 0

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
            cap_labels.append(("Total Dead Cap:", f"${dead_cap:,}"))
            try:
                from salary_cap_system import cap_breakdown as _cbd
                _bd = _cbd(self.app.user_team)
                if _bd["seeded_retained"]:
                    cap_labels.append(("Retained Salary (real):",
                                       f"${_bd['seeded_retained']:,}"))
                if _bd["seeded_overage"]:
                    cap_labels.append(("Bonus Overage (real):",
                                       f"${_bd['seeded_overage']:,}"))
                if _bd["seeded_buyout"]:
                    cap_labels.append(("Buyouts (real 2026-27):",
                                       f"${_bd['seeded_buyout']:,}"))
            except Exception:
                pass
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
        for player in sorted(self.app.user_team.roster, key=lambda p: p.overall_rating(), reverse=True):
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
                               command=self.app.open_trade_block_window).pack(side="left", padx=5)
        self._secondary_button(left, text="Contract Extensions",
                               command=self.app.open_contract_extensions_window).pack(side="left", padx=5)

        right = ctk.CTkFrame(footer, fg_color="transparent")
        right.pack(side="right")
        self._secondary_button(right, text="Export Roster",
                               command=self.export_roster).pack(side="left", padx=5)
        self._secondary_button(right, text="Refresh",
                               command=self.update_views).pack(side="left", padx=5)
        self._secondary_button(right, text="Close",
                               command=self.close_view).pack(side="left", padx=5)

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
                               font_family=self.app.FONT_FAMILY)

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
            self._secondary_button(actions, text="Return to Junior",
                                   command=lambda: self.bulk_move_players('ahl', 'prospects')).pack(side="left", padx=3)
        elif roster_type == 'prospects':
            self._primary_button(actions, text="Promote to AHL",
                                 command=lambda: self.bulk_move_players('prospects', 'ahl')).pack(side="left", padx=3)
            self._secondary_button(actions, text="Rights Watch",
                                   command=self.open_rights_watch).pack(side="left", padx=3)

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
        # TRACK C #3a: suspended rows keep the 'injured' red foreground via the
        # status rewrite; this background-only tag composes without a
        # foreground conflict (two foreground tags do not compose reliably).
        tree.tag_configure('suspended', background='#3a2320')
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

    def _rights_status(self, player):
        """Signed vs unsigned rights status for the prospects table.

        Shows only the user's own rights bookkeeping -- expiry year and
        warning state. No scouting truth leaks: nothing here reveals a
        prospect's hidden potential.
        """
        try:
            _c = getattr(player, 'contract', None)
            if (_c is not None and getattr(_c, 'salary', 0)
                    and getattr(_c, 'years_remaining', 0) > 0):
                return "Signed"
        except Exception:
            pass
        try:
            _rt = getattr(player, 'rights_team', '') or ''
            _exp = int(getattr(player, 'rights_expiry_year', 0) or 0)
        except Exception:
            _rt, _exp = '', 0
        try:
            _uname = getattr(getattr(self.app, 'user_team', None),
                             'team_name', '')
            _yr = int(getattr(getattr(self.app, 'league', None),
                              'season_year', 0) or 0)
        except Exception:
            _uname, _yr = '', 0
        if _rt and _exp and (_rt == _uname or not _uname):
            _warn = "⚠ " if _yr and _exp - _yr <= 1 else ""
            return f"{_warn}Rights '{str(_exp)[2:]}"
        return "—"

    def _unsigned_rights_prospects(self):
        """The user's unsigned rights-held prospects, soonest expiry
        first."""
        try:
            _team = self.app.user_team
            _uname = getattr(_team, 'team_name', '')
            _pool = list(getattr(_team, 'prospects', []) or [])
        except Exception:
            return []
        _out = []
        for _p in _pool:
            try:
                _c = getattr(_p, 'contract', None)
                if (_c is not None and getattr(_c, 'salary', 0)
                        and getattr(_c, 'years_remaining', 0) > 0):
                    continue  # signed
                if (getattr(_p, 'rights_team', '') or '') != _uname:
                    continue
                _exp = int(getattr(_p, 'rights_expiry_year', 0) or 0)
                if not _exp:
                    continue
                _out.append((_exp, _p))
            except Exception:
                continue
        _out.sort(key=lambda _t: (_t[0], getattr(_t[1], 'full_name', '')))
        return [p for _e, p in _out]

    def open_rights_watch(self):
        """Rights Watch: every unsigned rights-held prospect, soonest
        expiry first, with warning states and one-click ELC talks."""
        ct = self._ct
        dlg = InGamePopup(self)
        dlg.title("Rights Watch")
        dlg.geometry("620x520")
        dlg.configure(fg_color=ct['BG'])
        dlg.transient(self)
        self._heading(dlg, text="Rights Watch", size=16).pack(pady=(14, 2))
        self._body(
            dlg,
            text=("Your unsigned rights-held prospects. Sign them to an "
                  "entry-level deal before their rights expire, or they "
                  "re-enter the draft and you lose them for nothing."),
            size=10, dim=True, wraplength=560).pack(pady=(0, 8))
        try:
            _yr = int(getattr(getattr(self.app, 'league', None),
                              'season_year', 0) or 0)
        except Exception:
            _yr = 0
        _prospects = self._unsigned_rights_prospects()
        _list_frame = ctk.CTkFrame(dlg, fg_color=ct['CARD'], corner_radius=8)
        _list_frame.pack(fill='both', expand=True, padx=14, pady=6)
        lb = tk.Listbox(_list_frame, bg=ct['CARD'], fg=ct['TEXT'],
                        relief='flat', font=("Segoe UI", 11),
                        selectbackground=ct['ROW_SELECTED'],
                        highlightthickness=0, activestyle='none')
        lb.pack(fill='both', expand=True, padx=8, pady=8)
        if not _prospects:
            lb.insert(tk.END, "  No unsigned rights-held prospects. "
                              "Every drafted prospect is signed.")
        for _p in _prospects:
            _exp = int(getattr(_p, 'rights_expiry_year', 0) or 0)
            try:
                _pos = _p.primary_position.value
            except Exception:
                _pos = "?"
            _left = _exp - _yr if _yr else None
            if _left is not None and _left <= 0:
                _state, _color = "EXPIRES THIS YEAR", ct['RED']
            elif _left == 1:
                _state, _color = "1 year left", "#e8b93c"
            else:
                _state, _color = f"{_left} years left", ct['TEXT_DIM']
            lb.insert(tk.END,
                      f"  {getattr(_p, 'full_name', '?'):<24} {_pos:<3} "
                      f"age {getattr(_p, 'age', '?'):<3}  "
                      f"rights thru {_exp}  -- {_state}")
            lb.itemconfig(tk.END, foreground=_color)

        def _open_elc():
            _sel = lb.curselection()
            if not _sel or not _prospects:
                return
            _p = _prospects[_sel[0]]
            try:
                self.app.open_contract_negotiation_window(_p, is_elc=True)
            except Exception as e:
                # Honest failure: keep the dialog open so the user can
                # retry or pick someone else -- never destroy on failure.
                messagebox.showwarning(
                    "ELC Talks Unavailable",
                    f"Couldn't open ELC talks for "
                    f"{getattr(_p, 'full_name', 'that prospect')} ({e}). "
                    f"The dialog is still open -- try again.")
                return
            dlg.destroy()

        _btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        _btn_row.pack(pady=(0, 12))
        self._primary_button(_btn_row, text="Open ELC talks",
                             command=_open_elc).pack(side="left", padx=6)
        self._secondary_button(_btn_row, text="Close",
                               command=dlg.destroy).pack(side="left", padx=6)

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

            # Get player info (ratings on the native 1-100 scale, matching
            # the Min OVR filter pills)
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
            # TRACK C #3a: suspended players are silently unavailable in the
            # lineup builder -- surface the badge in the status column.
            try:
                _susp_n = int(getattr(player, 'suspension_games_remaining', 0) or 0)
            except (TypeError, ValueError):
                _susp_n = 0
            if _susp_n > 0:
                injury_status = f"SUSPENDED ({_susp_n})"

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
                # draft_round is stamped by the draft generator (prospect
                # development engine); 0/empty means undrafted / free agent.
                draft_round = getattr(player, 'draft_round', 0) or 'FA'
                # farm_league is where the engine actually simmed him last
                # season (prospect_development); fall back to legacy fields.
                league = (getattr(player, 'farm_league', '') or
                          getattr(player, 'current_league', '') or 'Amateur')
                development = self.calculate_development_trend(player)
                eta = self.calculate_eta(player)
                rights = self._rights_status(player)
                # Remove salary and contract columns for prospects, add prospect-specific data
                values = [checkbox, name, position, age, overall, potential,
                         draft_year, draft_round, league, development, eta,
                         rights]

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
            if _susp_n > 0:
                tags.append('suspended')
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
        """NHL readiness for AHL players: talent grade adjusted by the
        situation -- injury openings, coach fit, line fit, farm trend, and
        his live NHL audition. The arrows flag a number the moment is
        moving (▲ up / ▼ down)."""
        try:
            import prospect_development as _pd
            team = getattr(self.app, 'user_team', None)
            score, deltas = _pd.situational_readiness(player, team)
            net = sum(d for _, d in deltas)
            tag = " ▲" if net >= 8 else (" ▼" if net <= -8 else "")
            return f"{score:.0f}%{tag}"
        except Exception:
            pass
        try:
            import prospect_development as _pd
            return f"{_pd.callup_readiness(player):.0f}%"
        except Exception:
            pass
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
        if player.overall_rating() >= 70:
            return "Ready"
        elif player.overall_rating() >= 65:
            return "1-2 years"
        elif player.overall_rating() >= 34:
            return "2-3 years"
        else:
            return "3+ years"

    # ------------------------------------------------------------------
    # Table interaction
    # ------------------------------------------------------------------
    def _name_column_id(self, tree):
        """Return the treeview column id (e.g. '#3') of the 'name' column."""
        try:
            return f"#{list(tree['columns']).index('name') + 1}"
        except (ValueError, tk.TclError):
            return None

    def handle_tree_click(self, event, tree, roster_type):
        """Handle tree click events."""
        region = tree.identify_region(event.x, event.y)
        if region == 'cell':
            col = tree.identify_column(event.x)
            if col == '#1':  # Selection column
                item_id = tree.identify_row(event.y)
                if item_id:
                    self.toggle_player_selection(item_id, tree, roster_type)
                return
            # Single left-click on the player's name opens the profile card.
            if col == self._name_column_id(tree):
                item_id = tree.identify_row(event.y)
                if item_id and item_id in self.player_maps[roster_type]:
                    player = self.player_maps[roster_type][item_id]
                    self.app.open_player_profile(player)

    def handle_double_click(self, event, tree, roster_type):
        """Handle double-click to open player profile."""
        # The name column already opens the profile on single click, so a
        # double-click there must not open a second card.
        if tree.identify_region(event.x, event.y) == 'cell':
            if tree.identify_column(event.x) == self._name_column_id(tree):
                return
        item_id = tree.identify_row(event.y)
        if item_id and item_id in self.player_maps[roster_type]:
            player = self.player_maps[roster_type][item_id]
            self.app.open_player_profile(player)

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
                # Junior-aged signed CHL prospects can go straight back
                # to junior (new CBA: everyone else stays pro).
                try:
                    import game_classes as _gc2
                    _elig_nhl = (
                        getattr(player, "contract", None) is not None
                        and _gc2.junior_track_of(player) == "CHL"
                        and int(getattr(player, "age", 20) or 20) < 20)
                except Exception:
                    _elig_nhl = False
                if _elig_nhl:
                    roster_options.insert(
                        1, ("Return to Junior",
                            lambda: self.move_player(player, 'nhl', 'prospects')))
            elif roster_type == 'ahl':
                # Only junior-eligible signed prospects get a junior
                # option; everyone else stays in the pro system (a
                # signed veteran can no longer be stashed in the
                # prospects list to dodge the cap).
                try:
                    import game_classes as _gc3
                    _elig_ahl = (
                        getattr(player, "contract", None) is not None
                        and _gc3.junior_track_of(player) == "CHL"
                        and int(getattr(player, "age", 20) or 20) < 20)
                except Exception:
                    _elig_ahl = False
                roster_options = [
                    ("Call Up to NHL", lambda: self.move_player(player, 'ahl', 'nhl')),
                ]
                if _elig_ahl:
                    roster_options.append(
                        ("Return to Junior",
                         lambda: self.move_player(player, 'ahl', 'prospects')))
            elif roster_type == 'prospects':
                roster_options = [
                    ("Promote to AHL", lambda: self.move_player(player, 'prospects', 'ahl'))
                ]
                # Unsigned rights-held prospect: explicit ELC negotiation
                # instead of the silent auto-sign on promotion.
                try:
                    _elc_elig = (
                        getattr(player, "contract", None) is None
                        and (getattr(player, "rights_team", "") or "")
                        == getattr(getattr(self.app, "user_team", None),
                                    "team_name", ""))
                    # ELC eligibility: 25+ is outside the Entry Level
                    # System (CBA 9.1(b); new CBA, no European exception).
                    if _elc_elig:
                        try:
                            from draft_generator import age_on_sept15 as _s15m
                            import salary_cap_system as _scs_m
                            _sy_m = getattr(getattr(self.app, "league", None),
                                            "season_year", None)
                            _s15v = _s15m(getattr(player, "birth_date", ""),
                                          _sy_m)
                            _elc_age_m = (_s15v if _s15v is not None
                                          else getattr(player, "age", 20))
                            if _scs_m.elc_years_for_age(_elc_age_m) <= 0:
                                _elc_elig = False
                        except Exception:
                            pass
                except Exception:
                    _elc_elig = False
                if _elc_elig:
                    roster_options.insert(
                        0, ("Offer ELC…",
                            lambda: self.app.open_contract_negotiation_window(
                                player, is_elc=True)))

            # Add contract options
            roster_options.append(("Contract Extension",
                                 lambda: self.app.open_contract_negotiation_window(player, True)))

            # Use universal context menu
            if not hasattr(self, 'context_menu_manager'):
                self.context_menu_manager = PlayerContextMenu(self.app)

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
            self.populate_roster_tree(self.nhl_tree, self.app.user_team.roster, 'nhl')
        elif roster_type == 'ahl':
            self.populate_roster_tree(self.ahl_tree, self.app.user_team.ahl_roster, 'ahl')
        elif roster_type == 'prospects':
            self.populate_roster_tree(self.prospects_tree, self.app.user_team.prospects, 'prospects')

        self.update_roster_summary(roster_type)

    def update_roster_summary(self, roster_type):
        """Update roster summary information."""
        if roster_type == 'nhl':
            players = self.app.user_team.roster
            selected_count = len(self.selected_players['nhl'])
            total_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000)) for p in players)
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            avg_overall = sum(to_100_scale(p.overall_rating()) for p in players) / len(players) if players else 0

            summary = f"Players: {len(players)}/23 | Selected: {selected_count} | Total Salary: ${total_salary:,} | Avg Age: {avg_age:.1f} | Avg OVR: {avg_overall:.1f}"
            self.nhl_summary_label.configure(text=summary)

        elif roster_type == 'ahl':
            players = self.app.user_team.ahl_roster
            selected_count = len(self.selected_players['ahl'])
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            avg_overall = sum(to_100_scale(p.overall_rating()) for p in players) / len(players) if players else 0

            summary = f"Players: {len(players)}/20 | Selected: {selected_count} | Avg Age: {avg_age:.1f} | Avg OVR: {avg_overall:.1f}"
            self.ahl_summary_label.configure(text=summary)

        elif roster_type == 'prospects':
            players = self.app.user_team.prospects
            selected_count = len(self.selected_players['prospects'])
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            high_potential = len([p for p in players if getattr(p, 'potential_grade', 'C') in ['A+', 'A', 'A-']])

            summary = f"Prospects: {len(players)} | Selected: {selected_count} | High Potential: {high_potential} | Avg Age: {avg_age:.1f}"
            self.prospects_summary_label.configure(text=summary)

    def select_all_players(self, roster_type):
        """Select all players in the roster."""
        if roster_type == 'nhl':
            players = self.app.user_team.roster
        elif roster_type == 'ahl':
            players = self.app.user_team.ahl_roster
        else:
            players = self.app.user_team.prospects

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
            messagebox.showinfo("No Selection", "Please select players to move.")
            return

        # Get source and destination lists
        if from_roster == 'nhl':
            source_list = self.app.user_team.roster
        elif from_roster == 'ahl':
            source_list = self.app.user_team.ahl_roster
        else:
            source_list = self.app.user_team.prospects

        # Move players
        players_to_move = [p for p in source_list if p.id in selected_ids]

        # Junior return (AHL -> prospects) only applies to signed,
        # junior-aged CHL prospects. Pre-filter here so a bulk move
        # doesn't pop one blocking dialog per ineligible player --
        # move_player still enforces the rule per player.
        _junior_bulk = (from_roster in ('nhl', 'ahl')
                        and to_roster not in ('nhl', 'ahl'))
        _skipped = 0
        _unsigned_skipped = 0
        _is_promotion_bulk = (from_roster not in ('nhl', 'ahl')
                              and to_roster in ('nhl', 'ahl'))
        for player in players_to_move:
            if _junior_bulk:
                try:
                    import game_classes as _gcb
                    _ok = (getattr(player, "contract", None) is not None
                           and _gcb.junior_track_of(player) == "CHL"
                           and int(getattr(player, "age", 20) or 20) < 20)
                except Exception:
                    _ok = False
                if not _ok:
                    _skipped += 1
                    continue
            if _is_promotion_bulk and getattr(player, "contract", None) is None:
                # Unsigned prospects need an explicit ELC first -- one
                # summary instead of a dialog per kid.
                _unsigned_skipped += 1
                continue
            self.move_player(player, from_roster, to_roster)
        if _skipped:
            messagebox.showinfo(
                "Return to Junior",
                f"{_skipped} selected player(s) can't go back to junior -- "
                f"only signed under-20 CHL prospects are eligible.")
        if _unsigned_skipped:
            messagebox.showinfo(
                "Unsigned prospects",
                f"{_unsigned_skipped} selected prospect(s) need an "
                f"entry-level contract first -- right-click and choose "
                f"'Offer ELC' to negotiate, then promote.")

        # Clear selections and update views
        self.selected_players[from_roster].clear()
        self.update_views()

    def move_player(self, player, from_roster, to_roster):
        """Move a single player between rosters.

        Promotion (prospects -> NHL/AHL): an unsigned prospect can't
        skate for $0 -- promotion is blocked until he has an ELC, and
        the user is routed straight into contract talks ("Offer ELC").
        The CHL-NHL agreement gates AHL assignment for under-20 CHL
        prospects (new CBA: 19-year-old first-rounders excepted).

        Junior return (NHL/AHL -> prospects): a SIGNED junior-aged
        (under-20) CHL prospect goes back to his junior club. An
        ex-college player can never go back to college once he's signed
        an NHL deal -- minors or NHL only. This also closes the old
        loophole where a signed veteran could be stashed in the
        prospects list to dodge the cap.
        """
        try:
            import game_classes as _gc
        except Exception:
            _gc = None
        _is_promotion = (from_roster not in ('nhl', 'ahl')
                         and to_roster in ('nhl', 'ahl'))
        _is_junior_return = (from_roster in ('nhl', 'ahl')
                             and to_roster not in ('nhl', 'ahl'))

        if _is_promotion:
            # CHL-NHL agreement (new CBA 2026): an under-20 CHL prospect
            # is not AHL-eligible -- he goes back to junior -- EXCEPT a
            # 19-year-old drafted in the first round, who may be loaned
            # to the AHL. Applies signed or unsigned.
            if to_roster == 'ahl' and _gc is not None and \
                    not _gc.prospect_ahl_eligible(player):
                _age = int(getattr(player, "age", 20) or 20)
                messagebox.showwarning(
                    "CHL-NHL agreement",
                    f"{player.full_name} is {_age} and CHL-drafted -- "
                    f"he isn't eligible for the AHL roster. Under the "
                    f"new CBA only 19-year-old first-round picks may be "
                    f"loaned to the AHL. He'll keep developing in junior.")
                return
            # 23-man NHL roster limit.
            if to_roster == 'nhl' and \
                    len(self.app.user_team.roster) >= 23:
                messagebox.showerror(
                    "Roster Full",
                    "Your NHL roster is full (23). Move someone out "
                    "first.")
                return
            # Signing gate: an unsigned prospect (contract=None) can't
            # skate for $0. No silent auto-sign -- the user negotiates
            # the ELC explicitly ("Offer ELC" on the prospects menu).
            # Promotion just routes into contract talks.
            if getattr(player, "contract", None) is None:
                # ELC eligibility backstop: 25+ prospects sit outside the
                # Entry Level System (CBA 9.1(b); new CBA) -- the ELC
                # dialog can't serve them. (Nearly unreachable: rights
                # expire long before 25.)
                _elc_ok = True
                try:
                    from draft_generator import age_on_sept15 as _s15p
                    import salary_cap_system as _scs_p
                    _sy_p = getattr(getattr(self.app, "league", None),
                                    "season_year", None)
                    _s15v_p = _s15p(getattr(player, "birth_date", ""), _sy_p)
                    _elc_age_p = (_s15v_p if _s15v_p is not None
                                  else getattr(player, "age", 20))
                    if _scs_p.elc_years_for_age(_elc_age_p) <= 0:
                        _elc_ok = False
                except Exception:
                    pass
                if not _elc_ok:
                    messagebox.showwarning(
                        "Outside the Entry Level System",
                        f"{player.full_name} is past ELC age and can't "
                        f"sign an entry-level contract.")
                    return
                # Backstop: prospects who predate rights stamping
                # get stamped on the fly so the ELC gate has
                # something to consume.
                _league = getattr(self.app, 'league', None)
                try:
                    if _league is not None and not getattr(
                            player, "rights_team", ""):
                        from datetime import date as _date
                        _yr = getattr(_league, "current_year",
                                      _date.today().year)
                        try:
                            _league.stamp_draft_rights(
                                player,
                                self.app.user_team.team_name, int(_yr))
                        except Exception:
                            pass
                except Exception:
                    pass
                if messagebox.askyesno(
                        "Unsigned prospect",
                        f"{player.full_name} needs an entry-level contract "
                        f"before he can join the {to_roster.upper()} "
                        f"roster.\n\nOpen contract talks now?"):
                    try:
                        self.app.open_contract_negotiation_window(
                            player, is_elc=True)
                    except Exception:
                        pass
                return
            try:
                player.playing_where = "NHL" if to_roster == 'nhl' \
                    else "AHL"
            except Exception:
                pass

        elif _is_junior_return:
            # Only signed players get junior-assignment semantics;
            # unsigned ones just rejoin the unsigned pool.
            if getattr(player, "contract", None) is not None:
                _track = _gc.junior_track_of(player) if _gc else "EUROPE"
                _jage = int(getattr(player, "age", 20) or 20)
                if not (_track == "CHL" and _jage < 20):
                    if _track == "NCAA":
                        _why = (f"{player.full_name} signed an NHL "
                                f"contract -- that ended his NCAA "
                                f"eligibility. He can only play in the "
                                f"NHL or AHL now, never back in college.")
                    else:
                        _why = (f"Only junior-aged (under-20) CHL "
                                f"prospects can be returned to junior. "
                                f"{player.full_name} stays with the pro "
                                f"club.")
                    messagebox.showwarning("Can't return to junior", _why)
                    return
                try:
                    player.playing_where = _gc.junior_assignment_label(
                        player) if _gc else "Junior"
                except Exception:
                    pass
                try:
                    self.app.add_news(
                        f"{player.full_name} was returned to junior "
                        f"({player.playing_where}).")
                except Exception:
                    pass

        # New-CBA paper-transaction rule: a player assigned to the AHL must
        # play at least one game down there before he can be recalled.
        # Grandfathered players (old saves, never assigned) pass through.
        if from_roster == 'ahl' and to_roster == 'nhl':
            try:
                import ahl_system as _ahl_gate_w
                _block = _ahl_gate_w.ahl_recall_block_reason(player)
            except Exception:
                _block = None
            if _block:
                messagebox.showwarning("Recall blocked (new CBA)", _block)
                return

        # MP client: the gates above are local UX; the actual move is
        # host-applied. Route it instead of mutating the snapshot.
        if _mp_route(self.app,
                     "call_up" if to_roster == 'nhl'
                     else "send_to_minors" if to_roster == 'ahl'
                     else "return_to_junior",
                     {"player_id": str(getattr(player, "id", ""))}):
            return

        # Remove from source
        if from_roster == 'nhl':
            self.app.user_team.roster.remove(player)
        elif from_roster == 'ahl':
            self.app.user_team.ahl_roster.remove(player)
        else:
            self.app.user_team.prospects.remove(player)

        # Add to destination
        if to_roster == 'nhl':
            self.app.user_team.roster.append(player)
            # Dressing room: a promotion into the NHL room -- the room
            # reacts to WHO he is. First appearance per team only
            # (guarded inside); shuffling a regular up and down is quiet.
            try:
                import dressing_room as _dr_arr
                _dr_arr.cascade_on_arrival(
                    self.app.user_team, player, how="callup",
                    date_str=str(getattr(self.app, "current_date", "")))
            except Exception:
                pass
        elif to_roster == 'ahl':
            self.app.user_team.ahl_roster.append(player)
            # NHL->AHL is an assignment under the new CBA: stamp the
            # recall gate (a promotion from the prospect pool is not).
            if from_roster == 'nhl':
                try:
                    import ahl_system as _ahl_stamp_w
                    _ahl_stamp_w.stamp_ahl_assignment(player)
                except Exception:
                    pass
        else:
            self.app.user_team.prospects.append(player)

        # Update any open windows
        self.app.update_all_views()

    def add_to_trade_block(self, player):
        """Add player to trade block."""
        if not hasattr(self.app, 'trade_block'):
            self.app.trade_block = []

        if player not in self.app.trade_block:
            # MP client: the league-level block lives on the host (it's
            # what AI GMs read); the local list stays as the display.
            # It is only appended on a successful send -- a failed send
            # shows the error and leaves the display untouched.
            _tb_ids = ([str(getattr(p, "id", ""))
                        for p in self.app.trade_block]
                       + [str(getattr(player, "id", ""))])

            def _tb_done():
                self.app.trade_block.append(player)
                messagebox.showinfo(
                    "Trade Block",
                    f"{player.full_name} added to trade block.")

            if _mp_is_client(self.app):
                if _mp_route(self.app, "set_trade_block",
                             {"player_ids": _tb_ids}, on_sent=_tb_done):
                    return
            _tb_done()
        else:
            messagebox.showinfo("Trade Block", f"{player.full_name} is already on the trade block.")

    def open_lines_editor(self):
        """Open the live lines editor."""
        try:
            self.app.open_edit_lines_window()
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
            filename = f"roster_export_{self.app.user_team.team_name.replace(' ', '_')}_{timestamp}.csv"
            filepath = os.path.join(exports_dir, filename)

            # Collect all roster data
            roster_data = []

            # Add NHL roster
            for player in self.app.user_team.roster:
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
            for player in self.app.user_team.ahl_roster:
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
            for player in self.app.user_team.prospects:
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

            messagebox.showinfo("Export Successful",
                                 f"Roster exported successfully!\n\n"
                                 f"File: {filename}\n"
                                 f"Location: {exports_dir}\n"
                                 f"Players exported: {len(roster_data)}")

        except Exception as e:
            print(f"Error exporting roster: {e}")
            messagebox.showerror("Export Error", f"Failed to export roster:\n{str(e)}")

    def update_views(self):
        """Update all roster views.

        Only already-built tabs are refreshed; unbuilt tabs populate from
        current data when first selected (_build_roster_tab), so nothing
        can go stale.
        """
        built = getattr(self, '_tabs_built', {'nhl', 'ahl', 'prospects', 'depth', 'cap'})
        for rt in ('nhl', 'ahl', 'prospects'):
            if rt in built:
                self.update_roster_tab(rt)

        # Update header stats
        nhl_count = len(self.app.user_team.roster)
        ahl_count = len(self.app.user_team.ahl_roster)
        prospects_count = len(self.app.user_team.prospects)

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
        # they are not the currently visible tab (only if already built;
        # unbuilt tabs populate on first selection).
        try:
            if 'depth' in built:
                self.refresh_depth_chart()
            if 'cap' in built:
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



class RosterWindow(InGamePopup):
    """Popup wrapper around RosterView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title(f"{parent.user_team.team_name} - Roster Management")
        self._view = RosterView(self, app=parent, *args, **kwargs)
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
class FreeAgencyView(ctk.CTkFrame):
    """Free Agency Market (CustomTkinter): dark cards, pill filters,
    styled stat tables, CTk dialogs for contracts/comparison/analysis."""

    def __init__(self, parent, app=None):
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
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the FreeAgencyWindow wrapper
        self.configure(fg_color=BG)

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
        self.app.open_windows['free_agency'] = self

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

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

        # Build tabs lazily: only the visible tab's widgets are created up
        # front; the rest build on first selection (same rationale as
        # RosterView -- CTk widget construction dominates screen-open cost).
        self._fa_tab_builders = {
            'players': self.create_enhanced_player_tab,
            'staff': self.create_enhanced_staff_tab,
            'market': self.create_market_overview_tab,
        }
        self._fa_tab_keys = {"Free Agent Players": 'players',
                             "Free Agent Staff": 'staff',
                             "Market Overview": 'market'}
        self._fa_tabs_built = set()
        self._build_fa_tab('players')
        try:
            self.tabview.configure(command=self._on_fa_tab_selected)
        except Exception:
            pass

        # Action buttons footer
        self.create_action_footer(main_container)

    def _build_fa_tab(self, key):
        """Build one FA tab's widgets on first use, then populate it."""
        if key in getattr(self, '_fa_tabs_built', set()):
            return
        builder = getattr(self, '_fa_tab_builders', {}).get(key)
        if builder is None:
            return
        self._fa_tabs_built.add(key)
        builder()
        try:
            if key == 'players':
                self.populate_filtered_players()
            elif key == 'staff':
                self.populate_filtered_staff()
            # 'market' renders current data as part of its build.
        except (AttributeError, tk.TclError):
            pass

    def _on_fa_tab_selected(self):
        """CTkTabview change callback: build the newly shown tab on demand."""
        try:
            key = self._fa_tab_keys.get(self.tabview.get())
        except Exception:
            key = None
        if key:
            self._build_fa_tab(key)

    def create_header_section(self, parent):
        """Create the header with market overview and quick stats."""
        ct = self._ct
        header = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12)
        header.pack(fill="x", pady=(0, 4))

        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 4))

        self._heading(top, text="FREE AGENCY MARKET", size=18).pack(side="left")

        # Quick stats on the right
        player_count = len(self.app.game_manager.free_agents)
        staff_count = len(self.app.league.free_agent_staff)
        self._body(top, text=f"Available: {player_count} Players \u2022 {staff_count} Staff",
                   dim=True, size=12).pack(side="right")

        # Subtitle row
        sub = ctk.CTkFrame(header, fg_color="transparent")
        sub.pack(fill="x", padx=20, pady=(4, 14))
        self._body(sub, text="Season 2024-25 \u2022 Free Agency Period",
                   dim=True, size=11).pack(side="left")

        # Team cap space on the right
        user_team = self.app.game_manager.user_team
        current_salary = sum(getattr(p, "salary", getattr(p.contract, "salary", 750000)) for p in user_team.roster)
        cap_space = getattr(user_team, 'salary_cap', 104000000) - current_salary  # NHL salary cap
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
            sort_cmd=self.app._sort_treeview_generic)

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
        self.staff_source_filter = tk.StringVar(master=self, value='All')

        self._pill_row(pills, "Source:", [(v, v) for v in
                       ('All', 'Free Agents', 'Overseas', 'Rival AHL')],
                       self.staff_source_filter, self._staff_set_filter,
                       self._staff_pill_groups)

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

        # Club staff-budget line (league-wide rule, market-tiered).
        self.staff_budget_label = self._body(staff_tab, text="",
                                             dim=True, size=11)
        self.staff_budget_label.pack(anchor="w", padx=14, pady=(0, 2))

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
            'salary': ('Ask', 100),
            'years': ('Contract', 80),
            'age': ('Age', 50),
            'nationality': ('Country', 80),
            'club': ('Club', 170),
        }
        self.fa_staff_tree = self._create_fa_treeview(
            staff_tab, staff_columns, height=22,
            sort_cmd=self.app._sort_treeview_generic)

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
        free_agents = self.app.game_manager.free_agents
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
        from game_classes import staff_market_ask
        league = self.app.game_manager.league
        available_staff = list(getattr(league, 'free_agent_staff', None) or [])
        overseas = list(getattr(league, 'overseas_staff', None) or [])
        if not available_staff and not overseas:
            self._body(parent_frame, text="No staff available",
                       dim=True).pack(anchor="w", padx=12, pady=5)
            return

        total_staff = len(available_staff) + len(overseas)
        pool = available_staff + overseas
        avg_age = sum(s.age for s in pool) / total_staff

        staff_ratings = []
        for s in pool:
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
        for staff in pool:
            role = staff.role.value
            role_counts[role] = role_counts.get(role, 0) + 1

        avg_ask = sum(staff_market_ask(s) for s in pool) / total_staff

        for stat in (f"Total Available: {total_staff}",
                     f"Average Age: {avg_age:.1f}",
                     f"Average Rating: {avg_rating:.1f}",
                     f"Avg. Ask: ${avg_ask:,.0f}"):
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
        position_players = [p for p in self.app.game_manager.free_agents
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
            for player in self.app.game_manager.free_agents:
                if player.full_name == player_name:
                    self.app.open_contract_negotiation_window(player)
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
                               command=self.export_free_agents).pack(
            side="left", padx=(0, 10))
        self._secondary_button(bulk, text="📝 Offer Sheets",
                               command=self.app.open_offer_sheet_window).pack(
            side="left")

        controls = ctk.CTkFrame(footer, fg_color="transparent")
        controls.pack(side="right")
        self._secondary_button(controls, text="Close",
                               command=self.close_view).pack(side="right", padx=(10, 0))
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
        # Drop stale item->player mappings (item ids are recycled by Tk).
        self.parent.tree_maps.get('fa_players', {}).clear()
        self.parent.tree_maps.get(self.fa_player_tree, {}).clear()

        name_filter = self.player_name_search.get().lower()
        position_filter = self.player_position_filter.get()
        age_filter = self.player_age_filter.get()
        rating_filter = self.player_rating_filter.get()
        salary_filter = self.player_salary_filter.get()
        contract_filter = self.player_contract_filter.get()
        sort_by = self.player_sort_filter.get()

        filtered_players = []
        for player in self.app.game_manager.free_agents:
            # Draft lock: draft-eligible players never appear as signable
            # free agents (they can only change clubs via the draft).
            try:
                from draft_generator import player_locked_by_draft as _locked
                if _locked(player):
                    continue
            except Exception:
                pass
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

            if 'fa_players' not in self.app.tree_maps:
                self.app.tree_maps['fa_players'] = {}
            self.app.tree_maps['fa_players'][item_id] = player

        self.player_results_label.configure(text=f"Showing {len(filtered_players)} players")
        set_tree_empty_state(self.fa_player_tree, "No players match your filters")

    def populate_filtered_staff(self):
        """Populate the staff tree with filtered results.

        Three sources: unemployed free agents, overseas coaches, and rival
        clubs' AHL staff (approachable only in the offseason -- real rule).
        The Salary filter/sort and the Ask column use the market ask, not
        the staffer's old salary.
        """
        from game_classes import (Staff as StaffClass, staff_market_ask,
                                  can_approach_staff)
        for item in self.fa_staff_tree.get_children():
            self.fa_staff_tree.delete(item)

        name_filter = self.staff_name_search.get().lower()
        role_filter = self.staff_role_combo.get()
        department_filter = self.staff_department_filter.get()
        experience_filter = self.staff_experience_filter.get()
        salary_filter = self.staff_salary_filter.get()
        sort_by = self.staff_sort_filter.get()
        source_filter = (self.staff_source_filter.get()
                         if hasattr(self, 'staff_source_filter') else 'All')

        league = getattr(self.app, 'league', None)
        try:
            user_team = self.app.game_manager.user_team
        except Exception:
            user_team = None
        try:
            current_date = self.app.game_manager.current_date
        except Exception:
            current_date = None

        # ---- Build the combined market ----
        entries = []  # (staff, source, employer_team)
        if league is not None:
            for s in (getattr(league, 'free_agent_staff', None) or []):
                entries.append((s, 'free_agent', None))
            for s in (getattr(league, 'overseas_staff', None) or []):
                entries.append((s, 'overseas', None))
            for t in (getattr(league, 'teams', None) or []):
                if t is user_team:
                    continue
                for s in (getattr(t, 'staff', None) or []):
                    if (getattr(s, 'assignment', 'nhl') or 'nhl') == 'ahl':
                        entries.append((s, 'ahl_poach', t))

        _source_labels = {'free_agent': 'Free Agents', 'overseas': 'Overseas',
                          'ahl_poach': 'Rival AHL'}

        filtered = []
        for staff, source, employer in entries:
            if (source_filter != 'All'
                    and _source_labels.get(source) != source_filter):
                continue
            try:
                if name_filter and name_filter not in staff.full_name.lower():
                    continue
            except Exception:
                continue
            if role_filter != 'All' and staff.role.value != role_filter:
                continue

            if department_filter != 'All':
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

            ask = staff_market_ask(staff)
            if salary_filter != 'All':
                if salary_filter == 'Under $100k' and ask >= 100_000:
                    continue
                elif salary_filter == '$100k-$250k' and not (100_000 <= ask <= 250_000):
                    continue
                elif salary_filter == '$250k-$500k' and not (250_000 < ask <= 500_000):
                    continue
                elif salary_filter == '$500k-$1M' and not (500_000 < ask <= 1_000_000):
                    continue
                elif salary_filter == 'Over $1M' and ask <= 1_000_000:
                    continue

            filtered.append((staff, source, employer, ask))

        if sort_by == 'Overall':
            filtered.sort(key=lambda e: e[0].overall_rating, reverse=True)
        elif sort_by == 'Name':
            filtered.sort(key=lambda e: e[0].full_name)
        elif sort_by == 'Role':
            filtered.sort(key=lambda e: e[0].role.value)
        elif sort_by == 'Experience':
            filtered.sort(key=lambda e: max(0, e[0].age - 25), reverse=True)
        elif sort_by == 'Salary':
            filtered.sort(key=lambda e: e[3], reverse=True)
        elif sort_by == 'Age':
            filtered.sort(key=lambda e: e[0].age)

        for staff, source, employer, ask in filtered:
            department = StaffClass.get_role_department(staff.role)
            experience = max(0, staff.age - 25)
            rating = to_100_scale(staff.overall_rating)

            allowed, reason = can_approach_staff(
                staff, employer, user_team, current_date)
            if source == 'free_agent':
                club = "Free agent"
            elif source == 'overseas':
                club = getattr(staff, 'current_club', '') or "Overseas"
            else:
                club = (f"{getattr(employer, 'team_name', '')} (AHL)"
                        + ("" if allowed else " \u2014 offseason only"))

            values = [
                staff.full_name,
                staff.role.value,
                department,
                rating,
                f"{experience}y",
                f"${ask:,}",
                f"{staff.contract_years}y",
                staff.age,
                staff.nationality,
                club,
            ]

            tag = self._ovr_tag(rating)
            item_id = self.fa_staff_tree.insert('', 'end', values=values,
                                                tags=(tag,) if tag else ())

            if 'fa_staff' not in self.app.tree_maps:
                self.app.tree_maps['fa_staff'] = {}
            self.app.tree_maps['fa_staff'][item_id] = (staff, source, employer)

        # Club staff-budget line.
        try:
            _t = user_team
            _b = int(getattr(_t, 'staff_budget', 0) or 0)
            _c = _t.staff_payroll() if hasattr(_t, 'staff_payroll') else 0
            self.staff_budget_label.configure(
                text=f"Club staff budget: ${_b:,}   \u2022   "
                     f"Committed: ${_c:,}   \u2022   "
                     f"Available: ${_b - _c:,}")
        except Exception:
            pass

        self.staff_results_label.configure(text=f"Showing {len(filtered)} staff")
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
        if hasattr(self, 'staff_source_filter'):
            self.staff_source_filter.set('All')
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
            messagebox.showwarning("No Selection", "Please select a player to sign.")
            return

        # UFA window (real NHL: the market opens July 1 -- no free-agent
        # signings in June). One rulebook in transaction_windows.py.
        try:
            import transaction_windows as _tw
            _ok, _why = _tw.check_window(
                "sign_ufa", getattr(self.app, "current_date", None))
            if not _ok:
                messagebox.showinfo("Free Agency", _why)
                return
        except Exception:
            pass

        player = self.app.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.app.open_contract_negotiation_window(player)
        else:
            # Honest map-miss: the selection couldn't be resolved to a
            # player -- say so instead of silently doing nothing.
            messagebox.showwarning(
                "Couldn't Resolve Selection",
                "That row couldn't be matched to a free agent. "
                "Re-select the player and try again.")

    def _fa_staff_entry(self, item_id):
        """Unwrap a staff tree-map entry -> (staff, source, employer).

        Backward-compatible with bare-Staff entries (treated as free agents).
        """
        entry = self.app.tree_maps.get('fa_staff', {}).get(item_id)
        if isinstance(entry, tuple):
            staff = entry[0] if len(entry) > 0 else None
            source = entry[1] if len(entry) > 1 else 'free_agent'
            employer = entry[2] if len(entry) > 2 else None
            return staff, source, employer
        return entry, 'free_agent', None

    def hire_selected_staff(self):
        """Hire the selected staff member via a real contract offer."""
        selection = self.fa_staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member to hire.")
            return

        staff, source, employer = self._fa_staff_entry(selection[0])
        if staff:
            self._open_staff_contract_dialog(staff, hire_source=source,
                                             from_team=employer)

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
        staff, _src, _emp = self._fa_staff_entry(item_id)
        if not staff:
            return

        menu = tk.Menu(self, tearoff=0, bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR)
        menu.add_command(label=f"Hire {staff.full_name}", command=self.hire_selected_staff)
        menu.add_command(label="View Staff Profile", command=self.view_selected_staff_profile)

        menu.tk_popup(event.x_root, event.y_root)

    def view_selected_player_profile(self):
        """View the selected player's profile."""
        selection = self.fa_player_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to view.")
            return

        player = self.app.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.app.open_player_profile(player)

    def view_selected_staff_profile(self):
        """View the selected staff member's profile."""
        selection = self.fa_staff_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member to view.")
            return

        staff, source, employer = self._fa_staff_entry(selection[0])
        if staff:
            self._open_staff_profile_dialog(staff, hire_source=source,
                                            from_team=employer)

    # ------------------------------------------------------------------
    # Staff contract negotiation (full-screen jump)
    # ------------------------------------------------------------------
    def _open_staff_contract_dialog(self, staff, hire_source="free_agent",
                                      from_team=None):
        """Negotiate a real contract offer with a staff member.

        Full-screen jump via show_screen(). fresh=True: each negotiation
        builds for its own staffer. Approach rules are enforced BEFORE the
        jump: rival AHL staff can only be approached in the offseason, and
        other clubs' NHL staff are not approachable at all.
        """
        from game_classes import can_approach_staff
        try:
            user_team = self.app.game_manager.user_team
            current_date = self.app.game_manager.current_date
        except Exception:
            user_team = None
            current_date = None
        allowed, reason = can_approach_staff(staff, from_team, user_team,
                                             current_date)
        if not allowed:
            messagebox.showwarning("Cannot Approach", reason)
            return
        # Overseas coaches can be approached any time, but the approach
        # itself is the negotiation -- jump straight in.
        self.app.show_screen("staff_contract",
                             f"Contract Offer - {staff.full_name}",
                             StaffContractView, staff, fresh=True,
                             hire_source=hire_source, from_team=from_team)


    def _open_staff_profile_dialog(self, staff, hire_source="free_agent",
                                     from_team=None):
        """View a free-agent staff member's profile (CTk)."""
        ct = self._ct
        dlg = InGamePopup(self)
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

        self._staff_track_record_section(scroll, staff)

        ctk.CTkFrame(scroll, fg_color=ct['BORDER'], height=1).pack(fill="x", pady=10)

        exp = max(0, staff.age - 25)
        from game_classes import staff_market_ask as _sma
        for text in (f"Age: {staff.age}",
                     f"Nationality: {staff.nationality}",
                     f"Experience: {exp} years",
                     f"Asking: ${_sma(staff):,} / year",
                     f"Contract: {staff.contract_years} years"):
            self._body(scroll, text=text, dim=True, size=11).pack(anchor="w", pady=1)

        self._primary_button(scroll, text=f"Hire {staff.full_name}",
                             command=lambda: (dlg.destroy(),
                                              self._open_staff_contract_dialog(
                                                  staff, hire_source=hire_source,
                                                  from_team=from_team))
                             ).pack(anchor="w", pady=(14, 0))

    def _staff_track_record_section(self, scroll, staff):
        """Track-record card for scouts: graded calls, hit rate, and how
        their finds ripple through the club's reputation.

        The record -- not hidden ability -- is what a GM should judge a
        scout by. Every filed read is graded against what happened next:
        validated breakouts bank GM respect, player confidence and fan
        buzz; misses plant doubt and can cost the scout his job.
        """
        try:
            from game_classes import StaffRole
            scout_roles = {StaffRole.HEAD_SCOUT,
                           StaffRole.PROFESSIONAL_SCOUT,
                           StaffRole.AMATEUR_SCOUT}
            is_scout = getattr(staff, "role", None) in scout_roles
        except Exception:
            is_scout = False
        if not is_scout:
            return
        ct = self._ct
        try:
            import analytics_scouting as _as
            record_line = _as.scout_record_line(staff)
            history = list(getattr(staff, "tip_history", []) or [])
        except Exception:
            record_line = "no graded calls yet"
            history = []
        box = ctk.CTkFrame(scroll, fg_color=ct['CARD'], corner_radius=8)
        box.pack(fill="x", pady=(10, 4))
        self._heading(box, text="Scout Track Record", size=12).pack(
            anchor="w", padx=12, pady=(10, 2))
        self._body(box, text=f"Graded calls: {record_line}", size=11).pack(
            anchor="w", padx=12, pady=(0, 2))
        self._body(box,
                   text=("Every read this scout files is graded against what "
                         "happens next. A validated breakout banks the club: "
                         "+GM respect, player confidence, fan buzz. A miss "
                         "plants doubt -- and clubs fire scouts under 40%."),
                   dim=True, size=10).pack(anchor="w", padx=12, pady=(0, 6))
        if history:
            for h in list(reversed(history[-8:])):
                try:
                    kind = h.get("kind", "")
                    res = h.get("result", "?")
                    pname = h.get("player_name", h.get("player", "?"))
                    date = h.get("date", "")
                    mark = "✓" if res == "hit" else "✗" if res == "miss" else "·"
                    color = (ct['GREEN'] if res == "hit"
                             else ct['RED'] if res == "miss" else ct['TEXT_DIM'])
                    row = ctk.CTkFrame(box, fg_color="transparent")
                    row.pack(fill="x", padx=12, pady=1)
                    ctk.CTkLabel(row, text=mark,
                                 font=("Segoe UI", 10, "bold"),
                                 text_color=color, width=18).pack(side="left")
                    self._body(row,
                               text=f"{pname} — {kind} read, {date}",
                               size=10).pack(side="left")
                except Exception:
                    pass
            ctk.CTkFrame(box, fg_color="transparent", height=6).pack()
        self._staff_open_reads_section(scroll, staff)

    def _staff_open_reads_section(self, scroll, staff):
        """This scout's current open reads -- private to your club.

        Scout tips are never broadcast in the news feed; they are your
        staff's private reports to you. Buy reads (targets) and sell
        reads (your own players showing regression signs) filed this
        month live here, with the evidence, the uncertainty, and the
        risks exactly as the scout wrote them. Accuracy is the scout's
        own: a better eye writes better reads.
        """
        ct = self._ct
        try:
            sid = getattr(staff, "id", None)
            user_team = getattr(getattr(self, "app", None), "user_team",
                                None)
            if sid is None or user_team is None:
                return
            buys = [(pid, t) for pid, t in
                    (getattr(user_team, "scout_buy_tips", None) or {}).items()
                    if isinstance(t, dict) and t.get("scout_id") == sid]
            sells = [(pid, t) for pid, t in
                     (getattr(user_team, "scout_sell_tips", None) or {}).items()
                     if isinstance(t, dict) and t.get("scout_id") == sid]
        except Exception:
            return
        if not buys and not sells:
            return
        box = ctk.CTkFrame(scroll, fg_color=ct['CARD'], corner_radius=8)
        box.pack(fill="x", pady=(10, 4))
        self._heading(box, text="Open Reads", size=12).pack(
            anchor="w", padx=12, pady=(10, 2))
        self._body(box, text=("Private to your club -- never broadcast. "
                              "Act on them, or wait for the ledger to grade "
                              "them."),
                   dim=True, size=10).pack(anchor="w", padx=12, pady=(0, 6))

        def _read_row(tip, direction):
            try:
                kind = tip.get("kind", "") or ""
                tag = f" [{kind}]" if kind in ("AHL", "PROSPECT") else ""
                name = tip.get("name", "?")
                pteam = tip.get("pteam", "")
                head = (f"{name}{tag} ({pteam})" if pteam
                        else f"{name}{tag}")
                if direction == "sell":
                    head += " -- regression signs"
                row = ctk.CTkFrame(box, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=2)
                dot = ctk.CTkLabel(row,
                                   text="▲" if direction == "buy" else "▼",
                                   font=("Segoe UI", 10, "bold"),
                                   text_color=(ct['GREEN'] if direction == "buy"
                                               else ct['GOLD']),
                                   width=18)
                dot.pack(side="left")
                col = ctk.CTkFrame(row, fg_color="transparent")
                col.pack(side="left", fill="x", expand=True)
                self._body(col, text=head, size=11).pack(anchor="w")
                reason = tip.get("reason", "")
                conf = tip.get("confidence", "")
                if reason or conf:
                    sub = reason
                    if conf:
                        sub += f" ({conf} confidence)" if sub else \
                            f"{conf} confidence"
                    self._body(col, text=sub, dim=True,
                               size=10).pack(anchor="w")
                for r in (tip.get("risks", "") or [])[:2]:
                    self._body(col, text=f"Risk: {r}", dim=True,
                               size=10).pack(anchor="w")
            except Exception:
                pass

        if buys:
            self._body(box, text="Buy reads", size=11).pack(
                anchor="w", padx=12, pady=(4, 0))
            for _, tip in buys:
                _read_row(tip, "buy")
        if sells:
            self._body(box, text="Sell reads", size=11).pack(
                anchor="w", padx=12, pady=(4, 0))
            for _, tip in sells:
                _read_row(tip, "sell")
        ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

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
            messagebox.showwarning("Selection Required",
                                       "Please select at least 2 players to compare.")
            return

        players = []
        for item_id in selection:
            player = self.app.tree_maps.get('fa_players', {}).get(item_id)
            if player:
                players.append(player)

        if len(players) < 2:
            messagebox.showwarning("Error", "Could not find selected players.")
            return

        self.create_player_comparison_window(players)

    def create_player_comparison_window(self, players):
        """Create a window comparing multiple players (CTk)."""
        ct = self._ct
        compare_window = InGamePopup(self)
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
            messagebox.showwarning("Selection Required",
                                       "Please select at least 2 staff members to compare.")
            return

        staff_list = []
        for item_id in selection:
            staff, _src, _emp = self._fa_staff_entry(item_id)
            if staff:
                staff_list.append(staff)

        if len(staff_list) < 2:
            messagebox.showwarning("Error", "Could not find selected staff members.")
            return

        self.create_staff_comparison_window(staff_list)

    def create_staff_comparison_window(self, staff_list):
        """Create a window comparing multiple staff members (CTk)."""
        ct = self._ct
        compare_window = InGamePopup(self)
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
            messagebox.showwarning("No Selection",
                                       "Please select a player for market analysis.")
            return

        player = self.app.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.create_market_analysis_window(player)

    def create_market_analysis_window(self, player):
        """Create a market analysis window for a player (CTk)."""
        ct = self._ct
        analysis_window = InGamePopup(self)
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

        for player in self.app.game_manager.free_agents:
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
        messagebox.showinfo("Market Refreshed",
                               "Free agency market data has been refreshed.")

    def update_views(self):
        """Update all views with current data.

        Only already-built tabs are refreshed; unbuilt tabs populate from
        current data when first selected (_build_fa_tab).
        """
        built = getattr(self, '_fa_tabs_built',
                        {'players', 'staff', 'market'})
        current = self.tabview.get()
        if 'players' in built:
            self.populate_filtered_players()
        if 'staff' in built:
            self.populate_filtered_staff()
        # Re-select the previously active tab (population doesn't change it,
        # but keep this deterministic for callers during __init__).
        self.tabview.set(current)

    def refresh_market_overview_data(self):
        """Refresh just the market overview numbers after a signing.

        Skipped when the tab was never built -- it renders current data on
        first selection anyway.
        """
        if 'market' not in getattr(self, '_fa_tabs_built',
                                   {'players', 'staff', 'market'}):
            return
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

                    for player in self.app.game_manager.free_agents:
                        salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
                        years = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 1))
                        writer.writerow(['Player', player.full_name,
                                         player.primary_position.value, player.age,
                                         to_100_scale(player.overall_rating()),
                                         salary, years, getattr(player, 'nationality', 'Unknown')])

                    for staff in self.app.league.free_agent_staff:
                        writer.writerow(['Staff', staff.full_name, staff.role.value,
                                         staff.age, to_100_scale(staff.overall_rating),
                                         staff.salary, staff.contract_years, staff.nationality])

                messagebox.showinfo("Export Complete",
                                       f"Free agent data exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

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
        messagebox.showinfo("Free Agency Help", help_text)



class FreeAgencyWindow(InGamePopup):
    """Popup wrapper around FreeAgencyView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Free Agency Market")
        self._view = FreeAgencyView(self, app=parent, *args, **kwargs)
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
def _perceiver_ctx(app, ai_manager, holder_team):
    """What the USER (perceiver) brings to the read: my scouts' eyes, my
    history with his GM, his poker face, and the standings situation.
    Every lookup is defensive -- a missing piece just yields a neutral ctx.
    """
    ctx = {}
    try:
        user_team = app.user_team
        league = app.league
    except Exception:
        return ctx
    try:  # my scouts: good staff read him cleanly, bad staff file noise
        from team_draft_boards import scouting_quality as _sq
        ctx["scout_quality01"] = _sq(user_team) / 100.0
    except Exception:
        pass
    try:  # my relationship with his GM: rivalry vs good relations
        import reputation_system as _rs
        ctx["respect01"] = _rs.gm_gm_respect(
            league, user_team, holder_team) / 100.0
        ctx["heat01"] = _rs.gm_gm_heat(league, user_team, holder_team) / 100.0
    except Exception:
        pass
    try:  # franchise rivalry: bad blood between the TEAMS, not just the GMs
        import reputation_system as _rs
        _rivs = getattr(league, "rivalries", None) or []
        _rh = _rs.get_rivalry_heat(_rivs, user_team, holder_team)
        ctx["team_heat01"] = float(_rh.get("heat", 0)) / 100.0
    except Exception:
        pass
    try:  # his poker face: a skilled veteran leaks less than a rookie
        import ai_extension_planning as _aep
        ident = (ai_manager.gm_identities.get(holder_team.team_name)
                 if ai_manager is not None else None)
        ctx["holder_skill01"] = _aep.gm_ability01(ident)
    except Exception:
        pass
    try:  # the situation: same division + the standings race
        _ud = getattr(user_team, "division", "") or ""
        _hd = getattr(holder_team, "division", "") or ""
        ctx["same_division"] = bool(_ud and _ud == _hd)
    except Exception:
        pass
    try:
        import trade_storylines as _ts
        ctx["holder_stance"] = _ts.stance(app, holder_team.team_name)
    except Exception:
        pass
    try:
        ctx["perceiver_key"] = getattr(user_team, "team_name", "user")
    except Exception:
        pass
    return ctx


def gm_trade_value_badges(ai_manager, team, app=None, level="NHL"):
    """badge_fn for CTkPlayerList: the USER's read of how THIS team's GM
    values each player.

    EHM-style trade screen: at a glance you see who the other GM considers
    UNTOUCHABLE / CORE / VALUED / GETTABLE. Built on the same
    franchise_score the extension forward book uses, so the tag and the
    money the GM reserves always agree -- but filtered through YOUR
    scouts, YOUR relationship with his GM, his poker face, and the
    standings situation (see perceived_trade_value). Prospects get a
    PROSPECT prefix so the level is unmistakable. Falls back to a neutral
    read when the AI manager or the GM identity isn't available.
    """
    try:
        identity = ai_manager.gm_identities.get(team.team_name)
    except Exception:
        identity = None
    try:
        strategy = ai_manager.team_strategies.get(team.team_name)
    except Exception:
        strategy = None
    try:
        import ai_extension_planning as _aep
    except Exception:
        return None
    ctx = _perceiver_ctx(app, ai_manager, team) if app is not None else {}
    _prospect = (level or "NHL") == "Prospects"

    def _badge(player):
        try:
            label, color, _p, _t = _aep.perceived_trade_value(
                player, identity, strategy, ctx)
            if _prospect:
                label = f"PROSPECT \u00b7 {label}"
            return (label, color)
        except Exception:
            return None
    return _badge


class TradeWindow(InGamePopup):
    """Trade Center (CustomTkinter): live value meter, picks, AI counter-offers, history."""

    METER_W = 280
    METER_H = 22

    def __init__(self, parent, preset=None):
        from ctk_theme import (
            init_ctk_theme, CTkOfferList, CTkPlayerList,
            primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE)
        init_ctk_theme()
        # A workbench, not a verdict: non-modal with click-out so the
        # user can dismiss it freely and keep exploring. Sending an
        # offer never resolves instantly -- the AI GM answers in a few
        # days via the inbox.
        super().__init__(parent, modal=False, dismiss_on_backdrop=True)
        self.parent = parent
        self.title("Trade Center")
        self.geometry("1280x780")
        self.configure(fg_color=BG)
        self.trade_offers = {'user': [], 'partner': []}
        self._asset_levels = {'user': {}, 'partner': {}}  # id(player) -> NHL/AHL/Prospects
        # Deal sweeteners (user's outgoing assets only):
        #   _retention: player id -> pct of cap hit retained (0/25/50)
        #   _pick_protection: pick id -> "top-3" | "top-10" | "lottery"
        self._retention = {}
        self._pick_protection = {}
        self._history_visible = False
        self._preset = preset or {}
        self._negotiation_id = self._preset.get("negotiation_id")

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
        # R8(ii): busy/loading indicator for heavy ops (roster rebuilds,
        # partner switches). Mirrors the dashboard's set_continue_busy
        # pattern: visible status + wait cursor, painted BEFORE the work.
        self._busy_label = body(header, "", dim=True)
        self._busy_label.configure(font=("Segoe UI", 10, "italic"))
        self._busy_label.pack(side='right', padx=(0, 6))

        # Partner selector row
        partner_row = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        partner_row.pack(fill='x', padx=10, pady=(8, 0))
        body(partner_row, "Trade partner:").pack(side='left', padx=(14, 0), pady=8)
        # Realistic: trade partners are NHL franchises only --
        # never standalone AHL clubs.
        def _is_nhl(t):
            ln = str(getattr(t, 'league_name', '') or '')
            return (t != parent.user_team and
                    ('National Hockey League' in ln or 'NHL' in ln or not ln))
        partner_teams = sorted(t.team_name for t in parent.league.teams
                               if _is_nhl(t))
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
        # Realistic logic: trade assets by level (NHL/AHL/Prospects).
        # Trades are between NHL franchises; AHL/prospects are org assets.
        self._user_level = ctk.StringVar(value="NHL")
        _ulvl = ctk.CTkSegmentedButton(user_frame, values=["NHL", "AHL", "Prospects"],
                                       variable=self._user_level,
                                       command=lambda _v: self._refresh_user_list())
        _ulvl.pack(fill='x', padx=8, pady=(0, 4))
        self.user_list = CTkPlayerList(user_frame)
        self.user_list.pack(fill='both', expand=True, padx=8, pady=4)
        btn_row = ctk.CTkFrame(user_frame, fg_color="transparent")
        btn_row.pack(fill='x', padx=8, pady=(4, 2))
        secondary_button(btn_row, text="Add Player  →",
                         command=lambda: self._add_to_trade('user')).pack(
                             side='left', padx=(0, 6))
        secondary_button(btn_row, text="Add Pick",
                         command=lambda: self._add_pick_dialog('user')).pack(side='left')
        body(user_frame, "Double-click adds · Right-click removes",
             size=10, dim=True).pack(anchor='w', padx=12, pady=(0, 8))

        # Center: deal panel (scrollable so Propose stays reachable at any height)
        center = ctk.CTkScrollableFrame(main, fg_color=PANEL, corner_radius=10)
        center.grid(row=0, column=1, sticky="nsew", padx=4)

        body(center, "YOUR OFFER", size=10, dim=True).pack(anchor='w', padx=12, pady=(10, 2))
        self.user_offer_list = CTkOfferList(center, height=120)
        self.user_offer_list.pack(fill='x', padx=8)
        secondary_button(center, text="Remove selected",
                         command=lambda: self._remove_from_trade('user')).pack(
                             anchor='e', padx=12, pady=(4, 8))

        # Salary retention (real NHL retained-salary transactions): keep up
        # to 50% of an outgoing player's cap hit to sweeten the deal. The
        # retained slice becomes your dead cap for the rest of his contract.
        body(center, "SALARY RETENTION", size=10, dim=True).pack(anchor='w', padx=12)
        self._retention_slots_label = body(center, "", size=10, dim=True)
        self._retention_slots_label.pack(anchor='w', padx=12)
        self.retention_frame = ctk.CTkFrame(center, fg_color="transparent")
        self.retention_frame.pack(fill='x', padx=8, pady=(2, 4))

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

        self.propose_btn = primary_button(center, text="Send Offer",
                                          command=self.propose_trade)
        self.propose_btn.pack(fill='x', padx=12, pady=(6, 0))
        body(center, "The other GM takes a few days to answer.\nYou can close this and keep working -- the reply lands in your inbox.",
             size=10, dim=True).pack(padx=12, pady=(8, 10))

        # Partner roster
        partner_frame = ctk.CTkFrame(main, fg_color=CARD, corner_radius=10)
        partner_frame.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        self.partner_title = heading(partner_frame, "Trade Partner", size=13)
        self.partner_title.pack(anchor='w', padx=12, pady=(10, 4))
        self._partner_level = ctk.StringVar(value="NHL")
        _plvl = ctk.CTkSegmentedButton(partner_frame, values=["NHL", "AHL", "Prospects"],
                                       variable=self._partner_level,
                                       command=lambda _v: self.update_trade_partner_roster())
        _plvl.pack(fill='x', padx=8, pady=(0, 4))
        # EHM-style: whose value is whose -- their GM's read on each player.
        body(partner_frame, "Their GM values each player:  "
             "UNTOUCHABLE (not moving)  ·  CORE  ·  VALUED  ·  GETTABLE",
             size=10, dim=True).pack(anchor='w', padx=12, pady=(0, 2))
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
        self._apply_preset()
        self._wire_player_menus()

    # ------------------------------------------------------------------
    # Preset (opened from an inbox negotiation or a player menu)
    # ------------------------------------------------------------------
    def _apply_preset(self):
        pr = self._preset
        if not pr:
            return
        partner = pr.get("partner")
        if partner is not None:
            try:
                self.partner_combo.set(partner.team_name)
            except Exception:
                pass
            self.update_trade_partner_roster()
        for side in ("user", "partner"):
            assets = pr.get("user_assets" if side == "user" else "partner_assets")
            if assets:
                self.trade_offers[side] = [a for a in assets
                                           if a not in self.trade_offers[side]]
        self._refresh_offer_lists()
        self._update_meter()
        if pr.get("mode") == "counter":
            # Restore the deal's retention/protection terms so the user
            # counters from the same terms, not from scratch.
            try:
                import trade_negotiation as _tn
                _neg = _tn.get_negotiation(self.parent, self._negotiation_id)
                if _neg is not None:
                    self._retention = {
                        getattr(a, 'id', None): float(v)
                        for a in self.trade_offers['user']
                        for k, v in (_neg.retention or {}).items()
                        if str(k) == str(getattr(a, 'id', '')) and float(v or 0) > 0}
                    self._pick_protection = {
                        getattr(a, 'id', ''): v
                        for a in self.trade_offers['user']
                        for k, v in (_neg.pick_protection or {}).items()
                        if str(k) == str(getattr(a, 'id', '')) and v}
            except Exception:
                pass
            self._refresh_offer_lists()
            try:
                self.propose_btn.configure(text="Send Counter-Offer")
                self.title(f"Trade Center -- countering {partner.team_name}"
                           if partner is not None else "Trade Center")
            except Exception:
                pass

    def _wire_player_menus(self):
        """EHM/FM24: right-click any player row for the player menu."""
        try:
            from player_context_menu import PlayerContextMenu
            mgr = PlayerContextMenu(self)
            self.user_list.on_right_click = (
                lambda e, p: mgr.show_context_menu(e, p))
            self.partner_list.on_right_click = (
                lambda e, p: mgr.show_context_menu(e, p))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def _level_roster(self, team, level):
        """Get a team's roster at the given level (NHL/AHL/Prospects)."""
        if level == "AHL":
            players = getattr(team, 'ahl_roster', [])
        elif level == "Prospects":
            players = getattr(team, 'prospects', [])
        else:
            players = getattr(team, 'roster', [])
        return sorted(players, key=lambda p: p.overall_rating(), reverse=True)

    def _set_busy(self, busy, msg="Loading..."):
        """R8(ii): busy/loading feedback for heavy trade-center ops.

        Mirrors dashboard_home.set_continue_busy: visible status text plus
        a wait cursor, with a forced paint BEFORE the heavy work starts so
        the user sees it. The window stays non-modal (click-out dismiss
        still works) -- this is feedback, not a lock. Never raises.
        """
        try:
            if busy:
                self._busy_label.configure(text=msg)
                self.configure(cursor="watch")
            else:
                self._busy_label.configure(text="")
                self.configure(cursor="")
            # Force a real paint before the heavy list rebuilds start.
            self.update_idletasks()
            self.update()
        except Exception:
            pass

    def _refresh_user_list(self):
        self._set_busy(True, "Loading roster...")
        try:
            _lvl = self._user_level.get()
            _badge = (lambda _p: ("PROSPECT", "#a1a1aa")) \
                if _lvl == "Prospects" else None
            self.user_list.set_players(
                self._level_roster(self.parent.user_team, _lvl),
                badge_fn=_badge)
        finally:
            self._set_busy(False)

    def update_views(self):
        self._set_busy(True, "Loading rosters...")
        try:
            self._refresh_user_list()
            self.update_trade_partner_roster()
            self._refresh_offer_lists()
            self._update_meter()
        finally:
            self._set_busy(False)

    def update_trade_partner_roster(self, event=None):
        self._set_busy(True, "Loading trade partner...")
        try:
            name = self.partner_combo.get()
            team = next((t for t in self.parent.league.teams
                         if t.team_name == name), None)
            if team:
                lvl = self._partner_level.get() if hasattr(self, '_partner_level') else "NHL"
                self.partner_title.configure(text=f"{team.team_name} ({lvl})")
                try:
                    _badge_fn = gm_trade_value_badges(
                        self.parent.ai_manager, team,
                        app=self.parent, level=lvl)
                except Exception:
                    _badge_fn = None
                self.partner_list.set_players(self._level_roster(team, lvl),
                                              badge_fn=_badge_fn)
                needs = self.te.team_needs(team)[:3]
                self.needs_label.configure(text="  ".join(needs) if needs else "—")
            # Partner changed -> clear their side of the deal
            self.trade_offers['partner'] = []
            self._asset_levels['partner'] = {}
            self._refresh_offer_lists()
            self._update_meter()
        finally:
            self._set_busy(False)

    def _refresh_offer_lists(self):
        for side, lst in (('user', self.user_offer_list),
                          ('partner', self.partner_offer_list)):
            labels = []
            for a in self.trade_offers[side]:
                lvl = self._asset_levels[side].get(id(a), "NHL")
                tag = "" if lvl == "NHL" else f" ({lvl})"
                label = f"{self.te.asset_label(a)}{tag}  [{self.te.asset_value(a)}]"
                if not self.te._is_pick(a):
                    # Trade protection badge -- real clauses, real consequences.
                    ctag = self.te.clause_tag(a)
                    if ctag:
                        label += f"  [{ctag}]"
                if side == 'user':
                    if not self.te._is_pick(a):
                        pct = self._retention.get(getattr(a, 'id', None), 0)
                        if pct:
                            label += f"  ⟡ retains {pct:g}%"
                    else:
                        prot = self.te.protection_label(
                            self._pick_protection.get(getattr(a, 'id', ''), ''))
                        if prot:
                            label += f"  ⟡ {prot}"
                labels.append(label)
            lst.set_items(labels)
        self._refresh_retention_section()

    # ------------------------------------------------------------------
    # Salary retention
    # ------------------------------------------------------------------
    def _refresh_retention_section(self):
        """Rebuild the per-player retention rows for the user's offer."""
        for child in self.retention_frame.winfo_children():
            child.destroy()
        try:
            from ctk_theme import body as _body
            used = self.te.retention_slots_used(self.parent.user_team)
            self._retention_slots_label.configure(
                text=f"Retention slots used: {used}/{self.te.MAX_RETENTION_SLOTS}")
        except Exception:
            pass
        players = [a for a in self.trade_offers['user']
                   if not self.te._is_pick(a)]
        if not players:
            return
        import customtkinter as ctk
        from ctk_theme import body as _body
        for p in players:
            row = ctk.CTkFrame(self.retention_frame, fg_color="transparent")
            row.pack(fill='x', pady=1)
            try:
                hit = self.te._player_cap_hit(p)
                name = f"{p.full_name} (${hit / 1e6:.2f}M)"
            except Exception:
                name = str(p)
            _body(row, name, size=11).pack(side='left', padx=(4, 8))
            var = ctk.StringVar(
                value=f"{self._retention.get(getattr(p, 'id', None), 0):g}%")
            seg = ctk.CTkSegmentedButton(
                row, values=["0%", "25%", "50%"], variable=var, width=150,
                command=lambda v, _p=p: self._set_retention(_p, v))
            seg.pack(side='right', padx=4)

    def _set_retention(self, player, value):
        """User picked a retention pct for one outgoing player."""
        try:
            pct = float(str(value).replace("%", "") or 0)
        except Exception:
            pct = 0
        pid = getattr(player, 'id', None)
        if pct > 0:
            # Validate now so the meter never shows an illegal promise.
            # The game date drives the new-CBA 75-day double-retention
            # clock, same as execution.
            _gdate = getattr(self.parent, "current_date", None)
            _gleague = getattr(self.parent, "league", None)
            ok, note = self.te.apply_retention_dry_run(
                self.parent.user_team, player, pct,
                extra={k: v for k, v in self._retention.items() if k != pid},
                trade_date=_gdate,
                season_windows=self.te.regular_season_windows(_gleague))
            if not ok:
                # Non-modal FYI (gating T2-Phase 0): no OS-modal dialog.
                from popup_system import notify_card
                notify_card(self, "Can't retain", note, kind="warning")
                self._refresh_retention_section()
                return
            self._retention[pid] = pct
        else:
            self._retention.pop(pid, None)
        self._refresh_offer_lists()
        self._update_meter()

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
        # Cap impact for the user (central cap accounting: roster + dead cap,
        # so this label always agrees with the actual trade validation).
        # Retention-aware: money you retain on outgoing players stays home
        # as your dead cap instead of leaving with them.
        gm_team = self.parent.user_team
        user_players = [p for p in self.trade_offers['user']
                        if not self.te._is_pick(p)]
        partner_players = [p for p in self.trade_offers['partner']
                           if not self.te._is_pick(p)]
        in_sal = sum(self.te._player_cap_hit(p) for p in partner_players)
        out_sal = sum(self.te._player_cap_hit(p) for p in user_players)
        try:
            from salary_cap_system import total_cap_charge
            kept_home = self.te._retention_adjustment(user_players, self._retention)
            new_pay = total_cap_charge(gm_team) - out_sal + kept_home + in_sal
            room = gm_team.salary_cap - new_pay
            ok = room >= 0
            ret_note = (f" (incl. ${kept_home / 1e6:.2f}M retained)"
                        if kept_home else "")
            self.cap_label.configure(
                text=f"Cap room after: ${room / 1e6:.1f}M{ret_note}"
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
        if player:
            self._add_player_to_trade(side, player)

    def _add_player_to_trade(self, side, player):
        """Double-click on a roster row: add that player to the deal."""
        if player and player not in self.trade_offers[side]:
            self.trade_offers[side].append(player)
            lvl = (self._user_level.get() if side == 'user'
                   else self._partner_level.get())
            self._asset_levels[side][id(player)] = lvl
            self._refresh_offer_lists()
            self._update_meter()

    def _remove_player_from_trade(self, side, player):
        """Right-click on a roster row: pull that player out of the deal."""
        if player in self.trade_offers[side]:
            self.trade_offers[side].remove(player)
            self._refresh_offer_lists()
            self._update_meter()

    def _player_menu(self, side, player, event=None):
        """Right-click on a roster row: full player menu, incl. remove-from-trade."""
        from player_context_menu import PlayerContextMenu
        mgr = PlayerContextMenu(self.parent)
        extra = []
        if player in self.trade_offers[side]:
            extra.append(("Remove from trade",
                          lambda: self._remove_player_from_trade(side, player)))
        if event is not None:
            mgr.show_context_menu(event, player, additional_options=extra)
        elif extra:
            # Fallback: plain removal when no click position is available.
            self._remove_player_from_trade(side, player)

    def _remove_from_trade(self, side):
        lst = self.user_offer_list if side == 'user' else self.partner_offer_list
        idx = lst.get_selected_index()
        if idx is None or idx >= len(self.trade_offers[side]):
            return
        gone = self.trade_offers[side][idx]
        del self.trade_offers[side][idx]
        if side == 'user':
            # Deal terms die with the asset.
            self._retention.pop(getattr(gone, 'id', None), None)
            self._pick_protection.pop(getattr(gone, 'id', ''), None)
            self._pick_protection.pop(str(getattr(gone, 'id', '')), None)
        self._refresh_offer_lists()
        self._update_meter()

    def _team_picks(self, team):
        picks = []
        for yr in sorted(getattr(team, 'draft_picks', {}).keys()):
            for pk in team.draft_picks[yr]:
                if getattr(pk, 'current_team', '') == team.team_name:
                    # BUG-016: expired picks are dead paper, not assets.
                    try:
                        if not pk.can_be_traded():
                            continue
                    except Exception:
                        pass
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
        dlg = InGamePopup(self)
        dlg.title("Add draft pick")
        dlg.geometry("420x420")
        dlg.configure(fg_color=BG)
        dlg.transient(self)
        heading(dlg, f"Select a {team.team_name} pick:", size=12).pack(pady=(14, 6))
        pick_list = CTkOfferList(dlg, height=170)
        pick_list.pack(fill='both', expand=True, padx=12)
        pick_list.set_items([f"{self.te.asset_label(pk)}  [{self.te.asset_value(pk)}]"
                             for pk in picks])

        # Pick protection (real NHL lottery protection, 1st-rounders only):
        # if the pick lands in the protected zone, the original club keeps
        # it and the holder gets their next-year 1st instead. Requires the
        # club to still hold its next-year 1st-rounder.
        prot_var = ctk.StringVar(value="None")
        prot_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        prot_frame.pack(fill='x', padx=12, pady=(6, 0))
        body(prot_frame, "Protection:", size=11, dim=True).pack(side='left')
        prot_seg = ctk.CTkSegmentedButton(
            prot_frame, values=["None", "Top-3", "Top-10", "Lottery"],
            variable=prot_var, width=240)
        prot_seg.pack(side='right')
        prot_note = body(dlg, "", size=10, dim=True)
        prot_note.pack(padx=12, pady=(2, 0))

        def _refresh_prot_state(*_a):
            idx = pick_list.get_selected_index()
            ok, why = True, ""
            if idx is not None and 0 <= idx < len(picks):
                pk = picks[idx]
                if pk.round != 1:
                    ok, why = False, "Only 1st-round picks can be protected."
                else:
                    nxt = pk.year + 1
                    own_next = any(
                        q.round == 1 and q.current_team == team.team_name
                        for q in (getattr(team, 'draft_picks', {}) or {}).get(nxt, []))
                    if not own_next:
                        ok, why = False, (
                            f"{team.team_name} doesn't hold its {nxt} 1st-rounder "
                            f"-- nothing to defer to.")
            try:
                prot_seg.configure(state="normal" if ok else "disabled")
            except Exception:
                pass
            prot_note.configure(text=why if not ok else
                                "If the pick lands in the protected zone, it defers "
                                "to next year's 1st.")
            if not ok:
                prot_var.set("None")

        try:
            _last_prot_idx = {"i": None}

            def _poll_prot():
                try:
                    if not dlg.winfo_exists():
                        return
                    cur = pick_list.get_selected_index()
                    if cur != _last_prot_idx["i"]:
                        _last_prot_idx["i"] = cur
                        _refresh_prot_state()
                    dlg.after(200, _poll_prot)
                except Exception:
                    pass

            _poll_prot()
        except Exception:
            pass
        _refresh_prot_state()

        def add():
            idx = pick_list.get_selected_index()
            if idx is not None:
                pk = picks[idx]
                self.trade_offers[side].append(pk)
                prot = {"Top-3": "top-3", "Top-10": "top-10",
                        "Lottery": "lottery"}.get(prot_var.get(), "")
                if prot and side == 'user' and pk.round == 1:
                    self._pick_protection[pk.id] = prot
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
        """Send the offer. The AI GM answers in a few days via the inbox --
        this window can be closed freely in the meantime."""
        import trade_negotiation as tn
        partner = self._partner_team()
        if partner is None:
            messagebox.showwarning("No partner", "Select a trade partner first.")
            return
        user_assets = list(self.trade_offers['user'])
        partner_assets = list(self.trade_offers['partner'])
        if not user_assets or not partner_assets:
            messagebox.showwarning("Incomplete", "Put assets on both sides first.")
            return
        _league = (getattr(getattr(self.parent, 'game_manager', None),
                           'league', None)
                   or getattr(self.parent, 'league', None))
        # Two-way preflight: the partner's clause players get the same
        # destination-aware check the AI applies on its side -- up front,
        # not 1-3 days later when the answer comes back. Non-blocking: the
        # user can still send, but not blind.
        _their_vetoes = self.te.trade_vetoes(
            partner, self.parent.user_team,
            [p for p in partner_assets if not self.te._is_pick(p)], _league)
        if _their_vetoes:
            _bits = []
            for _tv in _their_vetoes:
                _vp = _tv["player"]
                _vn = getattr(_vp, "full_name", str(_vp))
                try:
                    _wok, _wwhy = self.te.will_waive_ntc(
                        _vp, partner, self.parent.user_team, _league)
                except Exception:
                    _wok = False
                _bits.append(f"\u2022 {_vn} ({_tv['detail']}) -- "
                             f"{'likely to waive' if _wok else 'may refuse'}")
            if not messagebox.askyesno(
                    "Trade protection",
                    "Heads-up -- the other side has clause players:\n\n"
                    + "\n".join(_bits)
                    + "\n\nThey'll be asked to waive for a move to the "
                    f"{self.parent.user_team.team_name}, and a refusal kills "
                    "the deal. Send the offer anyway?"):
                return
        # No-trade / no-movement clauses: the user's own clause players must
        # waive for this specific destination before the offer goes out.
        # Yes = ask him, No = pull him from the offer, Cancel = stop.
        # Cap check FIRST: no point asking a player to waive his clause for
        # a deal that can't clear the cap -- and stamping the waiver before
        # this check used to leak a live single-use waiver on cap failure.
        _pre_retention = {k: v for k, v in self._retention.items() if v}
        if not self.te._cap_ok_after(self.parent.user_team, user_assets,
                                     partner_assets,
                                     retention=_pre_retention):
            messagebox.showerror("Cap problem",
                                 "This trade puts YOU over the salary cap. "
                                 "Shed salary first.")
            return
        # MP client: route the raw offer to the host BEFORE the local
        # waiver dialogs -- the host runs the same askyesnocancel waiver
        # flow over the wire (NTC_WAIVER_REQUEST prompts) against canonical
        # state, so local stamping would just be snapshot noise.
        def _offer_sent():
            messagebox.showinfo(
                "Offer sent",
                f"Your offer is with {partner.team_name}'s front office.\n"
                "If any of your players must waive a clause, you'll be "
                "asked -- then expect an answer within a few days in your "
                "inbox.")
            self.destroy()
        if _mp_route(self.parent, "propose_trade", {
                "partner_team_id": partner.team_name,
                "offer": {
                    "players_out": [str(getattr(a, "id", ""))
                                    for a in user_assets
                                    if not self.te._is_pick(a)],
                    "picks_out": [str(getattr(a, "id", ""))
                                  for a in user_assets
                                  if self.te._is_pick(a)],
                    "players_in": [str(getattr(a, "id", ""))
                                   for a in partner_assets
                                   if not self.te._is_pick(a)],
                    "picks_in": [str(getattr(a, "id", ""))
                                 for a in partner_assets
                                 if self.te._is_pick(a)],
                    "retention": {str(k): v for k, v in
                                  _pre_retention.items()},
                    "pick_protection": {str(k): v for k, v in
                                        self._pick_protection.items()},
                }}, on_sent=_offer_sent):
            return
        # Waivers stamped in this pass belong to the proposal being built:
        # if the user cancels, they are cleared -- a dead proposal spends
        # nothing (the same rule the MP host applies to dead deals).
        _stamped = []
        for _v in self.te.trade_vetoes(
                self.parent.user_team, partner,
                [p for p in user_assets if not self.te._is_pick(p)], _league):
            _p, _pname = _v["player"], getattr(
                _v["player"], "full_name", str(_v["player"]))
            _ans = messagebox.askyesnocancel(
                "No-trade clause",
                f"{_pname} has a {_v['detail']}.\n\nAsk him to waive it for "
                f"a move to the {partner.team_name}?\n\n"
                f"Yes = ask him  |  No = remove him from the offer  |  "
                f"Cancel = stop")
            if _ans is None:
                for _sp in _stamped:
                    try:
                        _sp.contract.ntc_waiver_for = ""
                    except Exception:
                        pass
                return
            if _ans is False:
                self.trade_offers['user'] = [
                    a for a in self.trade_offers['user'] if a is not _p]
                self._retention.pop(getattr(_p, 'id', None), None)
                user_assets = list(self.trade_offers['user'])
                self._refresh_offer_lists()
                self._update_meter()
                continue
            _ok, _why = self.te.will_waive_ntc(
                _p, self.parent.user_team, partner, _league)
            if _ok:
                try:
                    _p.contract.ntc_waiver_for = partner.team_name
                    _stamped.append(_p)
                except Exception:
                    pass
                messagebox.showinfo("Waiver granted", _why)
            else:
                messagebox.showwarning(
                    "Waiver refused",
                    f"{_why}\n\nHe's staying put -- remove him from the "
                    f"offer or cancel.")
                return
        # Deal terms the user set on this screen (retention %, pick protection).
        # Rebuilt here because the waiver loop above may have pulled a player
        # (and his retention row) out of the offer on a refused waiver.
        retention = {k: v for k, v in self._retention.items() if v}
        pick_protection = dict(self._pick_protection)
        if self._negotiation_id and self._preset.get("mode") == "counter":
            neg = tn.get_negotiation(self.parent, self._negotiation_id)
            if neg is not None and neg.is_open:
                tn.send_counter(self.parent, neg, user_assets, partner_assets,
                                retention=retention,
                                pick_protection=pick_protection)
                messagebox.showinfo(
                    "Counter-offer sent",
                    f"Your revised proposal is with {partner.team_name}.\n"
                    "They will answer in a few days -- the reply lands in "
                    "your inbox. You can close this window.")
                self.destroy()
                return
        tn.send_offer(self.parent, partner, user_assets, partner_assets,
                      retention=retention, pick_protection=pick_protection)
        messagebox.showinfo(
            "Offer sent",
            f"Your offer is with {partner.team_name}'s front office.\n"
            "Expect an answer within a few days -- it will arrive in your "
            "inbox, so feel free to close this and keep working.")
        self.destroy()

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


class ScoutingView(ctk.CTkFrame):
    """Modern Scouting Department: fog-of-war prospects, regional scouts, draft board."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ScoutingWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(bg_color=self.app.BG_COLOR)
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
        n_prospects = len(getattr(self.app.league, 'draft_prospects', []) or [])
        ttk.Label(header, text=f"{n_prospects} draft-eligible prospects on the radar",
                  style='Secondary.TLabel').pack(side='left', padx=(12, 0))

        main_pane = ttk.PanedWindow(self, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=10, pady=8)

        # ============ LEFT: scouts ============
        left = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(left, weight=1)

        ttk.Label(left, text="YOUR SCOUTS", style='Secondary.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.scouts_tree = self.app._create_treeview(
            left, {'name': ('Name', 120), 'jpa': ('JPA', 36),
                   'jpp': ('JPP', 36), 'region': ('Region', 90)}, height=6)
        self.scouts_tree.pack(fill='x', pady=(0, 4))
        self.scouts_tree.bind('<<TreeviewSelect>>', self._on_scout_selected)

        reg_frame = ttk.Frame(left, style='Panel.TFrame')
        reg_frame.pack(fill='x', pady=(0, 4))
        ttk.Label(reg_frame, text="Region:", style='Secondary.TLabel').pack(side='left')
        self.region_combo = ttk.Combobox(reg_frame, textvariable=self.region_var,
                                        values=self.scmod.ALL_SCOUT_REGIONS,
                                        state='readonly', width=16)
        self.region_combo.pack(side='left', padx=6)
        ttk.Button(reg_frame, text="Assign", command=self._assign_region,
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(reg_frame, text="Clear", command=self._clear_region,
                   style='Secondary.TButton').pack(side='left', padx=2)

        ttk.Button(left, text="Hire Scout", command=self._hire_scout,
                   style='Secondary.TButton').pack(anchor='w', pady=(0, 8))

        ttk.Label(left, text="ACTIVE ASSIGNMENTS", style='Secondary.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.assign_tree = self.app._create_treeview(
            left, {'player': ('Player', 110), 'view': ('Views', 44),
                   'acc': ('Acc', 36)}, height=8)
        self.assign_tree.pack(fill='both', expand=True)
        ttk.Button(left, text="Remove Assignment", command=self._remove_assignment,
                   style='Secondary.TButton').pack(anchor='w', pady=(6, 0))
        ttk.Label(left, text="Regional scouts file reports automatically every few days.\n"
                           "Pro scouts cover their beat (AHL, SHL, Liiga, KHL, NL) the same way.",
                  style='Secondary.TLabel', wraplength=260,
                  font=_sfont(self.app.FONT_FAMILY, 9)).pack(anchor='w', pady=(6, 0))

        # ============ CENTER: prospects + report ============
        center = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(center, weight=2)

        top_row = ttk.Frame(center, style='Panel.TFrame')
        top_row.pack(fill='x', pady=(0, 4))
        ttk.Label(top_row, text="PROSPECT POOL", style='Secondary.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(side='left')
        filt_frame = ttk.Frame(top_row, style='Panel.TFrame')
        filt_frame.pack(side='left', padx=(10, 4))
        self._prospect_pills = make_pill_group(
            filt_frame,
            [(o, o) for o in ("All Prospects", "Forwards", "Defensemen",
                              "Goalies", "Top 50", "Not Scouted")],
            self._set_prospect_filter, self.app.FONT_FAMILY)
        self._paint_prospect_pills()
        ttk.Entry(top_row, textvariable=self.search_var, width=14).pack(side='left', padx=4)
        ttk.Button(top_row, text="Search", command=self._refresh_prospects,
                   style='Secondary.TButton').pack(side='left')

        self.prospects_tree = self.app._create_treeview(
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
                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        ttk.Label(right, text="Your rankings drive auto-draft on draft night.",
                  style='Secondary.TLabel', wraplength=240,
                  font=_sfont(self.app.FONT_FAMILY, 9)).pack(anchor='w', pady=(0, 4))
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

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _build_report_card(self):
        f = self.report_frame
        self.rep_title = ttk.Label(f, text="Select a prospect",
                                  font=_sfont(self.app.FONT_FAMILY, 13, 'bold'),
                                  style='Card.TLabel')
        self.rep_title.pack(anchor='w')
        self.rep_pot = ttk.Label(f, text="", font=_sfont(self.app.FONT_FAMILY, 12, 'bold'),
                                style='Card.TLabel')
        self.rep_pot.pack(anchor='w', pady=(2, 0))
        self.rep_meta = ttk.Label(f, text="", style='Card.TLabel',
                                 font=_sfont(self.app.FONT_FAMILY, 10))
        self.rep_meta.pack(anchor='w')
        cols = ttk.Frame(f, style='Card.TFrame')
        cols.pack(fill='x', pady=(6, 0))
        left_c = ttk.Frame(cols, style='Card.TFrame')
        left_c.pack(side='left', fill='x', expand=True)
        right_c = ttk.Frame(cols, style='Card.TFrame')
        right_c.pack(side='left', fill='x', expand=True)
        ttk.Label(left_c, text="Strengths", style='Card.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.rep_strengths = ttk.Label(left_c, text="—", style='Card.TLabel',
                                      wraplength=260, justify='left')
        self.rep_strengths.pack(anchor='w')
        ttk.Label(right_c, text="Weaknesses", style='Card.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.rep_weak = ttk.Label(right_c, text="—", style='Card.TLabel',
                                  wraplength=260, justify='left')
        self.rep_weak.pack(anchor='w')
        self.rep_notes = ttk.Label(f, text="", style='Card.TLabel',
                                  wraplength=560, justify='left',
                                  font=_sfont(self.app.FONT_FAMILY, 10))
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
        scouts = [s for s in self.app.user_team.staff
                  if self.scmod.is_scout(s)]
        tm = self.app.tree_maps.setdefault(tree, {})
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
        tm = self.app.tree_maps.get(self.scouts_tree, {})
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
        if _mp_route(self.app, "assign_scout",
                     {"scout_id": str(getattr(self.selected_scout, "id", "")),
                      "region": region}):
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
        self.app.user_team.staff.append(scout)
        messagebox.showinfo("Scout Hired",
                            f"{scout.full_name} joined your scouting department.\n"
                            f"Assign them a region to start filing reports.")
        self._refresh_scouts()

    def _refresh_assignments(self):
        tree = self.assign_tree
        tree.delete(*tree.get_children())
        tm = self.app.tree_maps.setdefault(tree, {})
        for player, scout in getattr(self.app, 'scouting_assignments', {}).items():
            report = self.app.user_team.scouting_reports.get(player.id)
            views = getattr(report, 'viewings', 0) if report else 0
            acc = getattr(report, 'accuracy', '—') if report else '—'
            item = tree.insert('', 'end', values=(
                player.full_name,
                views, acc))
            tm[item] = player

    def _remove_assignment(self):
        sel = self.assign_tree.selection()
        tm = self.app.tree_maps.get(self.assign_tree, {})
        player = tm.get(sel[0]) if sel else None
        if player and player in getattr(self.app, 'scouting_assignments', {}):
            del self.app.scouting_assignments[player]
            self._refresh_assignments()
            self._refresh_prospects()

    # ------------------------------------------------------------------
    def _filtered_prospects(self):
        all_p = sorted(getattr(self.app.league, 'draft_prospects', []) or [],
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
            reports = self.app.user_team.scouting_reports
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
        tm = self.app.tree_maps.setdefault(tree, {})
        reports = self.app.user_team.scouting_reports
        assigns = getattr(self.app, 'scouting_assignments', {})
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
        tm = self.app.tree_maps.get(self.prospects_tree, {})
        self.selected_prospect = tm.get(sel[0]) if sel else None
        self._show_report()

    def _show_report(self):
        p = self.selected_prospect
        if p is None:
            return
        reports = self.app.user_team.scouting_reports
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
            assigned = p in getattr(self.app, 'scouting_assignments', {})
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
            scouts = [s for s in self.app.user_team.staff
                      if self.scmod.is_scout(s)]
            if not scouts:
                messagebox.showwarning("No Scouts", "Hire a scout first.")
                return
            scout = scouts[0]
        assigns = self.app.scouting_assignments
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
        ids = self.scmod.get_draft_board(self.app.user_team)
        by_id = {p.id: p for p in
                 getattr(self.app.league, 'draft_prospects', []) or []}
        # prune missing
        ids = [i for i in ids if i in by_id]
        self.scmod.set_draft_board(self.app.user_team, ids)
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
            messagebox.showwarning("No Prospect", "Select a prospect first.")
            return
        ids = self.scmod.get_draft_board(self.app.user_team)
        if p.id not in ids:
            ids.append(p.id)
            self.scmod.set_draft_board(self.app.user_team, ids)
            self._refresh_board()

    def _move_board(self, direction):
        lb = self.board_list
        sel = lb.curselection()
        if not sel:
            messagebox.showwarning("No Prospect", "Select a prospect first.")
            return
        i = sel[0]
        j = i + direction
        ids = self.scmod.get_draft_board(self.app.user_team)
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            self.scmod.set_draft_board(self.app.user_team, ids)
            self._refresh_board()
            lb.select_set(j)

    def _remove_board(self):
        lb = self.board_list
        sel = lb.curselection()
        if not sel:
            messagebox.showwarning("No Prospect", "Select a prospect first.")
            return
        ids = self.scmod.get_draft_board(self.app.user_team)
        del ids[sel[0]]
        self.scmod.set_draft_board(self.app.user_team, ids)
        self._refresh_board()

    def _reset_board(self):
        prospects = sorted(getattr(self.app.league, 'draft_prospects', []) or [],
                           key=lambda p: getattr(p, 'draft_ranking', 0),
                           reverse=True)[:50]
        self.scmod.set_draft_board(self.app.user_team, [p.id for p in prospects])
        self._refresh_board()




class ScoutingWindow(InGamePopup):
    """Popup wrapper around ScoutingView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Scouting Department")
        self._view = ScoutingView(self, app=parent, *args, **kwargs)
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
class DraftView(ctk.CTkFrame):
    """Draft night war room: live board, ticker, shortlist, draft-day trades, grades."""

    # Map any potential-grade variant onto a draft_night.grade_color key.
    _GRADE_BASE = {'A+': 'A+', 'A': 'A', 'A-': 'A', 'B+': 'B+', 'B': 'B',
                   'B-': 'B', 'C+': 'C', 'C': 'C', 'C-': 'C',
                   'D+': 'D', 'D': 'D', 'D-': 'D', 'F': 'F'}

    def __init__(self, parent, app=None):
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
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the DraftWindow wrapper
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
        self._draft_started = False    # re-entry guard for start_draft()
        # BUG-2 fix: the session is league-owned (league.entry_draft_session,
        # draft_night.EntryDraftSession). The view attributes above are
        # working copies materialized from it; the session is the durable
        # journal. Destroying this view detaches without touching it.
        self._session = None
        self._reentry_issues = []
        # Per-team draft boards (team_draft_boards.build_team_boards):
        # {team_name: [prospects in that team's order]}. None until
        # start_draft() builds them; AI falls back to consensus when
        # they are unavailable.
        self.team_boards = None
        # Pre-draft joint scouting reports
        # (team_draft_boards.build_draft_reports): {team_name:
        # {"team_name", "board", "projected_picks"}}. Built once per
        # draft in start_draft; also stashed on the league.
        self.team_reports = None
        self.selected_prospect = None
        self._armed_prospect = None  # M4: two-step inline pick confirmation
        self.strategy_var = tk.StringVar(master=self, value="BPA")
        self.pos_filter_var = tk.StringVar(master=self, value="All Positions")
        self._ai_after_id = None
        # Single-player draft clock (item 1): per-draft RNG for ticker +
        # AI selection (item 3: deterministic replays).
        self._draft_rng = random.Random()
        self._sp_clock_id = None
        self._sp_clock_left = 0

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
        # Draft pace control (M5): 1x / 4x / sim-to-my-pick.
        pace_row = ctk.CTkFrame(self.clock_frame, fg_color="transparent")
        pace_row.pack(pady=(0, 8))
        ctk.CTkLabel(pace_row, text="PACE",
                     font=("Segoe UI", 9, 'bold'),
                     text_color=ct['TEXT_DIM']).pack(side='left', padx=(0, 6))
        self._pace_btns = {}
        for _mode, _lbl in (("1x", "1×"), ("4x", "4×"),
                            ("sim", "▶▶ My pick")):
            _pb = ctk.CTkButton(pace_row, text=_lbl, width=70, height=24,
                               font=("Segoe UI", 10, 'bold'),
                               command=lambda m=_mode: self._set_pace(m))
            _pb.pack(side='left', padx=2)
            self._pace_btns[_mode] = _pb
        self._pace_mode = '1x'
        self._sim_active = False
        self._paint_pace_btns()

        # ---- 3 columns (grid; CTk has no PanedWindow) ----
        main_pane = ctk.CTkFrame(self, fg_color="transparent")
        main_pane.pack(fill='both', expand=True, padx=10, pady=8)
        main_pane.grid_columnconfigure(0, weight=2)
        main_pane.grid_columnconfigure(1, weight=1)
        main_pane.grid_columnconfigure(2, weight=1)
        main_pane.grid_rowconfigure(0, weight=1)

        # LEFT: draft board -- tabbed: the available-prospect board is the
        # primary surface (war-room convention); results and the user's own
        # picks live one tap away.
        left = ctk.CTkFrame(main_pane, fg_color=ct['PANEL'], corner_radius=10)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 4))
        ctk.CTkLabel(left, text="DRAFT BOARD",
                     font=("Segoe UI", 10, 'bold'),
                     text_color=ct['TEXT_DIM']).pack(anchor='w',
                                                     padx=12, pady=(10, 4))
        tab_row = ctk.CTkFrame(left, fg_color="transparent")
        tab_row.pack(fill='x', padx=12, pady=(0, 4))
        self._board_tab_var = tk.StringVar(master=self, value="Available")
        self._board_tab_btns = {}
        # The "Scout Report" tab is the user's pre-draft joint scouting
        # report: the department's private board (top 40) + projected picks
        # mapped onto owned slots. It lives here, above the fold, instead of
        # in the war-room column where it fell below 900px.
        _tab_widths = {"Available": 150, "Results": 80, "My Picks": 80,
                       "Scout Report": 100}
        for _tab in ("Available", "Results", "My Picks", "Scout Report"):
            # The available board shows the PUBLIC consensus ranking,
            # not any club's private list -- label it so.
            _label = (("Available — Consensus" if _tab == "Available"
                       else _tab))
            _b = ctk.CTkButton(tab_row, text=_label,
                               width=_tab_widths[_tab],
                               height=26,
                               font=("Segoe UI", 10, 'bold'),
                               command=lambda t=_tab: self._draft_board_tab(t))
            _b.pack(side='left', padx=(0, 6))
            self._board_tab_btns[_tab] = _b
        self._setup_tree_style()
        board_card = ctk.CTkFrame(left, fg_color=ct['CARD'], corner_radius=8)
        board_card.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self._board_tab_frames = {}
        for _tab in ("Available", "Results", "My Picks", "Scout Report"):
            _f = tk.Frame(board_card, bg=ct['CARD'])
            self._board_tab_frames[_tab] = _f
        self.available_tree = self._create_available_board(
            self._board_tab_frames["Available"])
        self.draft_results_tree = self._create_draft_board(
            self._board_tab_frames["Results"])
        self.mypicks_tree = self._create_mypicks_board(
            self._board_tab_frames["My Picks"])
        # The joint scouting report lives in its own tab (read-only,
        # scrollable): the user's private board + projected picks.
        self.scouting_report_box = ctk.CTkTextbox(
            self._board_tab_frames["Scout Report"],
            fg_color=ct['CARD'], text_color=ct['TEXT'],
            font=("Segoe UI", 10), state='disabled', wrap='word')
        self.scouting_report_box.pack(fill='both', expand=True,
                                      padx=8, pady=8)
        # Live research strip: the next owned pick plus the department's
        # takes on the top available prospects, with one-click quick
        # scouting. Refreshed by _render_scouting_report.
        _rs = tk.Frame(self._board_tab_frames["Scout Report"],
                       bg=ct['CARD'])
        _rs.pack(fill='x', padx=8, pady=(8, 0),
                 before=self.scouting_report_box)
        self._research_title = ctk.CTkLabel(
            _rs, text="RESEARCH — NEXT PICK",
            font=("Segoe UI", 10, 'bold'), text_color=ct['TEXT_DIM'])
        self._research_title.pack(anchor='w', pady=(0, 2))
        _rs_row = tk.Frame(_rs, bg=ct['CARD'])
        _rs_row.pack(fill='x')
        self._research_list = tk.Listbox(
            _rs_row, height=6, activestyle='none', bg=ct['BG'],
            fg=ct['TEXT'], selectbackground=ct['ROW_SELECTED'],
            relief='flat', highlightthickness=1,
            highlightbackground=ct['BORDER'])
        self._research_list.pack(side='left', fill='x', expand=True)
        self._research_list.bind(
            '<Double-1>', lambda _e: self._research_quick_scout())
        _rs_btns = tk.Frame(_rs_row, bg=ct['CARD'])
        _rs_btns.pack(side='left', padx=(6, 0))
        self._research_scout_btn = self._secondary_button(
            _rs_btns, text="Quick scout",
            command=self._research_quick_scout)
        self._research_scout_btn.pack(pady=2)
        self._research_open_btn = self._secondary_button(
            _rs_btns, text="Scouting",
            command=lambda: self.app.open_scouting_window())
        self._research_open_btn.pack(pady=2)
        self._research_players = []
        self._draft_board_tab("Available")

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
        # Shortlist capped at 8 rows: the war room must fit in 900px
        # height with the prospect card + action buttons visible (no
        # clipping; single-level scrolling rule).
        self.shortlist = tk.Listbox(center, height=8, activestyle='none',
                                    bg=ct['CARD'], fg=ct['TEXT'],
                                    selectbackground=ct['ROW_SELECTED'],
                                    relief='flat',
                                    highlightthickness=1,
                                    highlightbackground=ct['BORDER'])
        self.shortlist.pack(fill='x', padx=12, pady=(0, 4))
        self.shortlist.bind('<<ListboxSelect>>', self._on_shortlist_select)
        self.shortlist.bind('<Double-1>', self._on_shortlist_double)

        self.selected_label = self._body(center, text="No prospect selected",
                                   dim=True)
        self.selected_label.configure(wraplength=300)
        self.selected_label.pack(anchor='w', padx=12, pady=(0, 6))

        # M2: inline prospect card -- evaluation at the moment of decision.
        self.prospect_card = ctk.CTkFrame(center, fg_color=ct['CARD'],
                                          corner_radius=8)
        self.prospect_card.pack(fill='x', padx=12, pady=(0, 6))

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
        self.research_button = self._secondary_button(btn_col,
                                               text="Research This Pick",
                                               command=self._open_draft_research)
        self.research_button.pack(fill='x', pady=2)
        # Esc disarms a two-step pick confirmation.
        self.bind('<Escape>', lambda _e: self._disarm_draft_button())

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

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        # MULTIPLAYER: stop a pending draft-clock wait and release the clock.
        try:
            if getattr(self, '_mp_wait_id', None):
                self.after_cancel(self._mp_wait_id)
        except Exception:
            pass
        self._mp_wait_id = None
        try:
            self.app._mp_clear_draft_clock()
        except Exception:
            pass
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

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
                         self.app._sort_treeview_generic(t, c))
            tree.column(col, width=width, anchor='center')
        # Potential-grade row colors (same scale as the other CTk screens)
        for g in ('A+', 'A', 'B+', 'B', 'C', 'D', 'F'):
            tree.tag_configure(f"pot_{g}",
                               foreground=self.dn.grade_color(g))
        self.app._bind_player_context_menu(tree, 'draft', False)
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

    # -- M1: tabbed draft board -------------------------------------------
    def _draft_board_tab(self, name):
        """Switch the left column between Available / Results / My Picks /
        Scout Report."""
        self._board_tab_var.set(name)
        ct = self._ct
        for tab, btn in self._board_tab_btns.items():
            active = tab == name
            btn.configure(fg_color=ct['TEAL'] if active else ct['CARD'],
                          text_color=ct['BG'] if active else ct['TEXT_DIM'])
        for tab, frame in self._board_tab_frames.items():
            if tab == name:
                frame.pack(fill='both', expand=True)
            else:
                frame.pack_forget()
        if name == "Scout Report":
            # Never arrive at a stale research list mid-draft.
            try:
                self._refresh_draft_research()
            except Exception:
                pass

    def _create_available_board(self, parent):
        """Ranked available-prospect board (the war room's primary surface)."""
        ct = self._ct
        columns = {'rank': ('#', 36), 'player': ('Player', 150),
                   'pos': ('Pos', 42), 'pot': ('Pot', 64), 'age': ('Age', 36)}
        tree = ttk.Treeview(parent, columns=list(columns.keys()),
                            show='headings', style='Draft.Treeview',
                            height=30)
        for col, (text, width) in columns.items():
            tree.heading(col, text=text,
                         command=lambda c=col, t=tree:
                         self.app._sort_treeview_generic(t, c))
            tree.column(col, width=width, anchor='center')
        for g in ('A+', 'A', 'B+', 'B', 'C', 'D', 'F'):
            tree.tag_configure(f"pot_{g}",
                               foreground=self.dn.grade_color(g))
        try:
            self.app._bind_player_context_menu(tree, 'draft', False)
        except Exception:
            pass
        v_scroll = ttk.Scrollbar(parent, orient="vertical",
                                 command=tree.yview,
                                 style='Draft.Vertical.TScrollbar')
        tree.configure(yscrollcommand=v_scroll.set)
        tree.pack(side="left", fill="both", expand=True,
                  padx=(10, 0), pady=10)
        v_scroll.pack(side="right", fill="y", padx=(0, 6), pady=10)
        tree.bind('<<TreeviewSelect>>', self._on_available_select)
        tree.bind('<Double-1>', self._on_available_double)
        return tree

    def _create_mypicks_board(self, parent):
        """The user's own selections, one tab away."""
        ct = self._ct
        columns = {'pick': ('#', 40), 'player': ('Player', 160),
                   'pos': ('Pos', 42), 'pot': ('Pot', 60)}
        tree = ttk.Treeview(parent, columns=list(columns.keys()),
                            show='headings', style='Draft.Treeview',
                            height=30)
        for col, (text, width) in columns.items():
            tree.heading(col, text=text,
                         command=lambda c=col, t=tree:
                         self.app._sort_treeview_generic(t, c))
            tree.column(col, width=width, anchor='center')
        for g in ('A+', 'A', 'B+', 'B', 'C', 'D', 'F'):
            tree.tag_configure(f"pot_{g}",
                               foreground=self.dn.grade_color(g))
        try:
            self.app._bind_player_context_menu(tree, 'draft', False)
        except Exception:
            pass
        v_scroll = ttk.Scrollbar(parent, orient="vertical",
                                 command=tree.yview,
                                 style='Draft.Vertical.TScrollbar')
        tree.configure(yscrollcommand=v_scroll.set)
        tree.pack(side="left", fill="both", expand=True,
                  padx=(10, 0), pady=10)
        v_scroll.pack(side="right", fill="y", padx=(0, 6), pady=10)
        return tree

    def _prospect_by_id(self, pid):
        for p in getattr(self.app.league, 'draft_prospects', None) or []:
            if str(getattr(p, 'id', '')) == str(pid):
                return p
        return None

    def _refresh_available_board(self):
        tree = getattr(self, 'available_tree', None)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        # Canonical item_id -> prospect map: the universal right-click
        # menu (main._show_player_context_menu) resolves rows through it.
        try:
            _tmap = self.app.tree_maps.setdefault(tree, {})
            _tmap.clear()
        except Exception:
            _tmap = None
        reports = getattr(self.app.user_team, 'scouting_reports', {}) or {}
        for i, p in enumerate(self._board_sorted_available(), 1):
            report = reports.get(getattr(p, 'id', None))
            pot = (self.scmod.report_potential_display(report, p) if report
                   else self.scmod.consensus_range(p))
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            grade = self._GRADE_BASE.get(
                str(getattr(p, 'potential_grade', 'C')).strip(), 'C')
            _iid = tree.insert('', 'end',
                                 iid=str(getattr(p, 'id', '')),
                                 values=(i, getattr(p, 'full_name', '?'),
                                         pos, pot, getattr(p, 'age', '?')),
                                 tags=(f"pot_{grade}",))
            if _tmap is not None:
                _tmap[_iid] = p

    def _refresh_mypicks_board(self):
        tree = getattr(self, 'mypicks_tree', None)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        try:
            _tmap = self.app.tree_maps.setdefault(tree, {})
            _tmap.clear()
        except Exception:
            _tmap = None
        try:
            uname = self.app.user_team.team_name
        except Exception:
            return
        for team_name, overall, player in self.picks_made:
            if team_name != uname:
                continue
            try:
                pos = player.primary_position.value
            except Exception:
                pos = "?"
            grade = self._GRADE_BASE.get(
                str(getattr(player, 'potential_grade', 'C')).strip(), 'C')
            _iid = tree.insert('', 'end', values=(
                overall, getattr(player, 'full_name', '?'), pos,
                getattr(player, 'potential_grade', '?')),
                tags=(f"pot_{grade}",))
            if _tmap is not None:
                _tmap[_iid] = player

    def _render_scouting_report(self):
        """Fill the Scout Report tab from the user's pre-draft joint report:
        the department's private ranking (top 40) plus projected picks mapped
        onto our owned slots. User's team only -- other clubs' reports are
        never rendered."""
        box = getattr(self, 'scouting_report_box', None)
        if box is None:
            return
        lines = []
        try:
            uname = self.app.user_team.team_name
            rep = (getattr(self, 'team_reports', None) or {}).get(uname)
        except Exception:
            rep = None
        if not rep:
            lines = ["Scouting report unavailable."]
        else:
            try:
                consensus = sorted(
                    self.app.league.draft_prospects,
                    key=lambda p: getattr(p, 'draft_ranking', 0),
                    reverse=True)
                crank = {id(p): i + 1 for i, p in enumerate(consensus)}
            except Exception:
                crank = {}
            board = rep.get('board') or []

            def _pos(p):
                try:
                    return p.primary_position.value
                except Exception:
                    return "?"

            lines.append("JOINT BOARD — our department's ranking "
                         f"(top 40 of {len(board)})")
            for i, p in enumerate(board[:40], 1):
                lines.append(
                    f"{i:>2}. {getattr(p, 'full_name', '?')} "
                    f"({_pos(p)}) · consensus #{crank.get(id(p), '?')}")
            lines.append("")
            lines.append("PROJECTED PICKS — if the draft falls per "
                         "our board")
            owned = rep.get('projected_picks') or []
            if not owned:
                lines.append("(no picks owned)")
            for pr in owned:
                pl = pr.get('prospect')
                if pl is None:
                    lines.append(f"Rd {pr.get('round')} · "
                                 f"#{pr.get('overall')} → "
                                 "(board exhausted)")
                else:
                    lines.append(f"Rd {pr.get('round')} · "
                                 f"#{pr.get('overall')} → "
                                 f"{getattr(pl, 'full_name', '?')} "
                                 f"({_pos(pl)})")
        try:
            box.configure(state='normal')
            box.delete('1.0', 'end')
            box.insert('1.0', "\n".join(lines))
            box.configure(state='disabled')
        except Exception:
            pass
        self._refresh_draft_research()

    # -- Mid-draft research: takes for the next owned pick ---------------
    def _next_owned_pick(self):
        """(overall, round) of the user's next not-yet-made pick, or None."""
        try:
            uteam = self.app.user_team
            for i in range(self.current_pick + 1, len(self.draft_order)):
                _round, team, dp = self.draft_order[i]
                if team is uteam or team == uteam:
                    return (int(getattr(dp, 'overall_pick', 0) or 0),
                            int(_round or 0))
        except Exception:
            pass
        return None

    def _open_draft_research(self):
        """Jump to the Scout Report tab with fresh research."""
        try:
            self._refresh_draft_research()
            self._draft_board_tab("Scout Report")
        except Exception:
            pass

    def _refresh_draft_research(self):
        """Fill the research strip: next owned pick + top available
        prospects with the department's report status. Never raises."""
        try:
            lst = getattr(self, '_research_list', None)
            if lst is None or not lst.winfo_exists():
                return
            title = getattr(self, '_research_title', None)
            nxt = self._next_owned_pick()
            if title is not None and title.winfo_exists():
                title.configure(
                    text=("RESEARCH — YOUR NEXT PICK "
                          f"(Rd {nxt[1]}, #{nxt[0]})" if nxt
                          else "RESEARCH — NO PICKS LEFT"))
            lst.delete(0, tk.END)
            self._research_players = []
            if not nxt:
                lst.insert(tk.END, "(no picks remaining)")
                return
            reports = (getattr(self.app.user_team, 'scouting_reports', {})
                       or {})
            for p in self._available_prospects()[:8]:
                try:
                    pos = p.primary_position.value
                except Exception:
                    pos = "?"
                rep = reports.get(getattr(p, 'id', None))
                if rep is not None:
                    acc = getattr(rep, 'accuracy', '?') or '?'
                    pot = getattr(rep, 'scouted_potential', '') or ''
                    take = f"your take: {pot} ({acc})".strip()
                else:
                    take = "unscouted"
                lst.insert(tk.END,
                           f"{getattr(p, 'full_name', '?')} ({pos}) · {take}")
                self._research_players.append(p)
        except Exception:
            pass

    def _research_quick_scout(self):
        """Quick-scout the research list's selected prospect."""
        try:
            sel = self._research_list.curselection()
            if not sel:
                return
            p = self._research_players[sel[0]]
            from player_context_menu import PlayerContextMenu
            PlayerContextMenu(self)._quick_scout_player(p)
            self._refresh_draft_research()
            _sel = getattr(self, 'selected_prospect', None)
            if _sel is not None:
                self._render_prospect_card(_sel)
        except Exception:
            pass

    def _on_available_select(self, event=None):
        sel = self.available_tree.selection()
        if not sel:
            return
        p = self._prospect_by_id(sel[0])
        if p is None:
            return
        self.selected_prospect = p
        if self._armed_prospect is not None and self._armed_prospect is not p:
            self._disarm_draft_button()
        self._render_prospect_card(p)

    def _on_available_double(self, event=None):
        self._on_available_select()
        if self.selected_prospect is not None:
            self._arm_draft_button(self.selected_prospect)

    # -- M2: inline prospect card ------------------------------------------
    def _render_prospect_card(self, p):
        """Evaluation at the moment of decision: identity, scout view,
        storyline, and team-need fit -- without leaving the war room."""
        ct = self._ct
        card = self.prospect_card
        for w in card.winfo_children():
            w.destroy()
        try:
            pos = p.primary_position.value
        except Exception:
            pos = "?"
        name = getattr(p, 'full_name', '?')
        age = getattr(p, 'age', '?')
        ht = getattr(p, 'height', '') or ''
        wt = getattr(p, 'weight', '') or ''
        nat = (getattr(p, 'nationality', None)
               or getattr(p, 'nation', '') or '')
        # Consensus rank among the available pool
        try:
            avail = self._available_prospects()
            crank = avail.index(p) + 1 if p in avail else None
        except Exception:
            crank = None
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill='x', padx=10, pady=(8, 0))
        ctk.CTkLabel(head, text=name,
                     font=("Segoe UI", 13, 'bold'),
                     text_color=ct['TEXT']).pack(side='left')
        if crank:
            ctk.CTkLabel(head, text=f"Consensus #{crank}",
                         font=("Segoe UI", 10, 'bold'),
                         text_color=ct['GOLD']).pack(side='right')
        meta_bits = [b for b in
                     (pos, f"Age {age}",
                      f"{ht}" if ht else "", f"{wt}" if wt else "",
                      str(nat) if nat else "") if b]
        self._body(head, text="  ·  ".join(meta_bits),
                   dim=True).pack(anchor='w', padx=10)
        # Scout view (fog-of-war) + storyline + need fit
        reports = getattr(self.app.user_team, 'scouting_reports', {}) or {}
        report = reports.get(getattr(p, 'id', None))
        if report is not None:
            try:
                viewings = int(getattr(report, 'viewings', 0) or 0)
            except Exception:
                viewings = 0
            acc = getattr(report, 'accuracy', '') or ''
            scout_line = (f"Your scout: {self.scmod.report_potential_display(report, p)}"
                          f"  ·  {viewings} viewing{'s' if viewings != 1 else ''}"
                          + (f"  ·  {acc} accuracy" if acc else ""))
        else:
            scout_line = (f"Unscouted — consensus "
                          f"{self.scmod.consensus_range(p)}")
        self._body(card, text=scout_line, dim=False).pack(
            anchor='w', padx=10, pady=(2, 0))
        # Team-board rank: where the USER's own scouts slot him (fog-of-war
        # safe -- it's their scouts' opinion, never true potential). Other
        # teams' boards are never shown.
        try:
            from team_draft_boards import team_rank_of
            _ut = getattr(self.app.user_team, 'team_name', None)
            _trank = team_rank_of(getattr(self, 'team_boards', None),
                                  _ut, p)
            if _trank:
                self._body(card, text=f"Our scouts rank him #{_trank}",
                           dim=True).pack(anchor='w', padx=10)
        except Exception:
            pass
        details = []
        if report is not None:
            strengths = list(getattr(report, 'strengths', None) or [])[:2]
            weaknesses = list(getattr(report, 'weaknesses', None) or [])[:2]
            if strengths:
                details.append("Strengths: " + ", ".join(str(s) for s in strengths))
            if weaknesses:
                details.append("Weaknesses: " + ", ".join(str(s) for s in weaknesses))
        try:
            storylines = getattr(self.app.league, 'prospect_storylines', {}) or {}
            story = storylines.get(p)
            if story:
                details.append(f"📖 {story.get('title', story.get('type', ''))}")
        except Exception:
            pass
        for line in details:
            lbl = self._body(card, text=line, dim=True)
            lbl.configure(wraplength=320)
            lbl.pack(anchor='w', padx=10)
        # Team-need fit chip
        try:
            needs = self.te.team_needs(self.app.user_team) or []
            if pos in needs[:2]:
                chip = ctk.CTkLabel(card, text="✓ FITS TEAM NEED",
                                    font=("Segoe UI", 9, 'bold'),
                                    text_color=ct['GREEN'])
                chip.pack(anchor='w', padx=10, pady=(2, 8))
            else:
                ctk.CTkLabel(card, text="", font=("Segoe UI", 2)).pack(pady=(0, 8))
        except Exception:
            pass
        # Right-click opens the full player menu (profile, quick scout...).
        try:
            from player_context_menu import PlayerContextMenu
            card.bind('<Button-3>',
                      lambda _e, _p=p: PlayerContextMenu(
                          self).show_context_menu(
                              _e, _p, quick_scout=True))
            for w in card.winfo_children():
                w.bind('<Button-3>',
                       lambda _e, _p=p: PlayerContextMenu(
                           self).show_context_menu(
                               _e, _p, quick_scout=True))
        except Exception:
            pass

    # ------------------------------------------------------------------
    def start_draft(self):
        # Re-entry guard: __init__ starts the draft, so an explicit second
        # call (as the runtime QA once did) must not rebuild the order,
        # re-roll the 32 team boards, or re-drive the market -- a rebuild
        # after draft-day trades would show 225 rows for 224 slots and
        # replace the boards mid-draft. Fresh views start unflagged.
        if getattr(self, '_draft_started', False):
            return
        # BUG-2 fix: the draft session is league-owned
        # (league.entry_draft_session, draft_night.EntryDraftSession). A
        # rebuilt view re-attaches to the live session and resumes exactly
        # where the draft left off -- it never starts a fresh draft over
        # committed picks. A year already conducted shows its completed
        # state, never a new draft.
        league = self.app.league
        current_year = league.season_year
        # BUG-2 fix: a saved journal the load couldn't honor degrades to an
        # honest unavailable state -- never a fresh draft over committed
        # picks.
        try:
            _why = getattr(league, 'entry_draft_unavailable_reason', None)
        except Exception:
            _why = None
        if _why:
            self._show_unavailable_state(str(_why))
            return
        try:
            _sess = getattr(league, 'entry_draft_session', None)
        except Exception:
            _sess = None
        try:
            _sess_year = int(getattr(_sess, 'year', 0) or 0)
        except Exception:
            _sess_year = 0
        # BUG-2 fix: a parked in-progress session owns the war room --
        # whatever the calendar says. The session is the authoritative
        # draft; re-entry resumes it exactly where it left off, never a
        # fresh build over committed picks.
        if _sess is not None and not _sess.is_complete():
            self._attach_session(_sess)
            return
        try:
            _conducted = self.dn._conducted_years(league)
        except Exception:
            _conducted = set()
        try:
            _cond_years = {int(y) for y in _conducted}
        except Exception:
            _cond_years = set()
        if int(current_year) in _cond_years:
            self._show_conducted_state(current_year)
            return
        # BUG-2 fix: a session whose slots are all picked but never
        # finalized (save/load edge) is finalized idempotently for the
        # SESSION's year -- never re-drafted. resume_entry_draft_session
        # replays nothing (every overall is already journaled) and runs
        # the standard finalize: conducted stamp, grades, session release.
        if _sess is not None and _sess_year and _sess.is_complete():
            try:
                self.dn.resume_entry_draft_session(
                    league, _sess, app=self.app)
            except Exception:
                pass
            self._show_conducted_state(_sess_year)
            return
        # Make sure every team owns its picks (idempotent if already done)
        try:
            self.app.league.initialize_all_draft_picks()
        except Exception:
            pass
        self.draft_order = []
        try:
            order = self.app.league.get_draft_order(current_year)
        except Exception:
            order = []
        # Deterministic per-draft RNG: replays with the same seed pick
        # identically; every slot draws from it (item 3).
        try:
            self._draft_rng = random.Random(
                self.dn.stable_draft_seed(current_year))
        except Exception:
            self._draft_rng = random.Random()
        # get_draft_order returns (overall_pick, team, draft_pick); the ROUND
        # lives on draft_pick.round (1-7). The overall pick number is the
        # authoritative first element -- never the enumeration index.
        for overall, team, draft_pick in (order or []):
            try:
                round_num = int(getattr(draft_pick, 'round', 0) or 0)
            except Exception:
                round_num = 0
            try:
                draft_pick.overall_pick = overall
            except Exception:
                pass
            self.draft_order.append([round_num, team, draft_pick])
        if not self.draft_order:
            standings = getattr(self.app.league, 'standings', None) or {}
            _nhl = [t for t in self.app.league.teams
                    if getattr(t, 'league_name', '') == 'National Hockey League']
            sorted_teams = sorted(
                _nhl or list(self.app.league.teams),
                key=lambda t: standings.get(t.team_name, {}).get('Points', 0))
            for round_num in range(1, self.total_rounds + 1):
                for team in sorted_teams:
                    self.draft_order.append([round_num, team, None])
        self.current_pick = 0
        self.picks_made = []
        # Pre-draft joint scouting reports: every team's scouting +
        # analytics department ranks the class once (their private board)
        # and maps it onto the picks they own. Generated ONCE per draft
        # here -- never per pick. AI teams draft from their report's
        # board; the user's report is viewable in the war room.
        # Imported here to avoid a module cycle.
        try:
            from team_draft_boards import build_draft_reports
            self.team_reports = build_draft_reports(
                self.app.league, self.draft_order)
            self.team_boards = {
                _n: _r["board"] for _n, _r in self.team_reports.items()}
        except Exception:
            self.team_reports = None
            self.team_boards = None
        try:
            self.app.league.team_draft_reports = self.team_reports
        except Exception:
            pass
        self._render_scouting_report()
        self.draft_results_tree.delete(*self.draft_results_tree.get_children())
        self.ticker.delete(0, tk.END)
        self._ticker("Welcome to draft night. The floor is buzzing.")
        self._refresh_shortlist()
        # BUG-2 fix: league-own the session. The view may be destroyed at
        # any time; the draft lives on in league.entry_draft_session and a
        # rebuilt view resumes from it. If the session can't be created,
        # the draft must NOT proceed sessionless (picks would commit with
        # no journal, and a later re-entry would start fresh over them):
        # honest unavailable instead.
        try:
            self._session = self.dn.EntryDraftSession.begin(
                self.app.league, current_year, self.draft_order,
                self.team_reports, self._draft_rng)
            self.app.league.entry_draft_session = self._session
        except Exception as _e:
            self._session = None
            try:
                self.app.league.entry_draft_unavailable_reason = (
                    "The draft session couldn't be created "
                    f"({_e}). No draft was started.")
            except Exception:
                pass
            self._show_unavailable_state(
                "The draft session couldn't be created "
                f"({_e}). No draft was started.")
            return
        self.process_draft_pick()
        self._draft_started = True

    # ------------------------------------------------------------------
    # BUG-2 fix: league-owned draft session. These methods re-attach a
    # rebuilt view to the live session (resume), or present an honest
    # terminal state (conducted / unavailable). They never start a fresh
    # draft over committed picks.
    # ------------------------------------------------------------------
    def _attach_session(self, session):
        """Re-entry: materialize view state from the league-owned session
        and resume the draft exactly where it left off."""
        league = self.app.league
        self._session = session
        # The session's draft class must still be the live one. If the
        # calendar advanced a full year past a parked draft, the class
        # was regenerated and the remaining slots can't be filled
        # faithfully -- honest unavailable, never a silent wrong-year
        # draft. (Unverifiable when the class isn't year-stamped: allow.)
        try:
            _class_year = int(getattr(league, 'draft_prospects_year', 0)
                              or 0)
            _syear = int(getattr(session, 'year', 0) or 0)
        except Exception:
            _class_year, _syear = 0, 0
        if _class_year and _syear and _class_year != _syear:
            self._show_unavailable_state(
                f"This {_syear} draft was parked past its draft class "
                f"(the {_class_year} class is now live). Its "
                f"{len(getattr(session, 'picks', None) or [])} completed "
                "picks stand, but the remaining slots can't be filled "
                "faithfully -- no new draft was started.")
            return
        # Revalidate owners against the live pick objects: a pick traded
        # mid-draft while the war room was closed repoints here. Committed
        # picks keep their selecting team in the journal.
        try:
            session.sync_owners_from_league(league)
        except Exception:
            pass
        try:
            self._reentry_issues = session.audit(league)
        except Exception:
            self._reentry_issues = []
        order = session.materialize_order(league)
        # Defensive: every slot needs a live team. If one no longer
        # resolves (post-load corruption), degrade honestly rather than
        # crash or silently restart.
        _missing = [str(s.get('overall', '?')) for s, e in
                    zip(session.slots, order)
                    if e[1] is None]
        if _missing:
            self._show_unavailable_state(
                "Draft session can't be resumed: "
                f"{len(_missing)} pick slot(s) no longer resolve to a "
                f"team ({', '.join(_missing[:6])}"
                f"{'…' if len(_missing) > 6 else ''}). No new draft was "
                "started.")
            return
        self.draft_order = order
        self.team_boards = session.materialize_boards(league)
        # Rebuild the minimal team_reports the scouting tab needs for the
        # user's club: the persisted board plus projected picks for the
        # REMAINING slots the user still owns.
        try:
            uname = getattr(getattr(self.app, 'user_team', None),
                            'team_name', '')
            uboard = (self.team_boards or {}).get(uname) or []
            _proj = []
            for _i in range(int(session.current_pick or 0), len(order)):
                try:
                    _r, _t, _dp = order[_i]
                    if _t is None or getattr(_t, 'team_name', '') != uname:
                        continue
                    _ov = _i + 1
                    _pl = uboard[_ov - 1] if _ov - 1 < len(uboard) else None
                    _proj.append({'round': int(_r or 0), 'overall': _ov,
                                  'prospect': _pl})
                except Exception:
                    continue
            self.team_reports = {uname: {'board': list(uboard),
                                         'projected_picks': _proj}}
        except Exception:
            self.team_reports = None
        self.picks_made = session.materialize_picks(league)
        try:
            self.current_pick = int(session.current_pick or 0)
        except Exception:
            self.current_pick = 0
        # Restore the RNG stream exactly where it was (getstate/setstate),
        # so the resumed draft is the SAME draft, not a lookalike.
        try:
            self._draft_rng = random.Random()
            self._draft_rng.setstate(session.rng_state)
        except Exception:
            self._draft_rng = random.Random(
                self.dn.stable_draft_seed(session.year))
        # current_round follows the cursor (1-based, clamp to last round).
        try:
            if 0 <= self.current_pick < len(self.draft_order):
                self.current_round = int(
                    self.draft_order[self.current_pick][0] or 1)
            else:
                self.current_round = 7
        except Exception:
            self.current_round = 7
        self._rebuild_results_from_session()
        try:
            self._render_scouting_report()
        except Exception:
            pass
        self._ticker("Welcome back. The draft resumes where it left off -- "
                     f"pick #{self.current_pick + 1} "
                     f"({len(self.picks_made)} of {len(self.draft_order)} "
                     "made).")
        for _issue in (self._reentry_issues or [])[:5]:
            self._ticker("Re-entry check: " + str(_issue))
        try:
            self._refresh_shortlist()
        except Exception:
            pass
        self._draft_started = True
        self.process_draft_pick()

    def _rebuild_results_from_session(self):
        """Rebuild the results tree from the session's pick journal."""
        try:
            self.draft_results_tree.delete(
                *self.draft_results_tree.get_children())
        except Exception:
            return
        try:
            _maps = self.app.tree_maps.setdefault(
                self.draft_results_tree, {})
        except Exception:
            _maps = {}
        for team_name, overall, player in sorted(
                self.picks_made, key=lambda t: t[1]):
            # Mirror execute_pick's insert exactly (5 columns, pot tag).
            try:
                pos = player.primary_position.value
            except Exception:
                pos = "?"
            try:
                pot_grade = self._GRADE_BASE.get(
                    str(getattr(player, 'potential_grade', 'C')).strip(),
                    'C')
            except Exception:
                pot_grade = 'C'
            try:
                _iid = self.draft_results_tree.insert(
                    '', 0,
                    values=(overall, team_name,
                            getattr(player, 'full_name', '?'), pos,
                            getattr(player, 'potential_grade', '?')),
                    tags=(f"pot_{pot_grade}",))
                try:
                    _maps[_iid] = player
                except Exception:
                    pass
            except Exception:
                continue

    def _sync_session_owners(self):
        """Mirror mid-draft pick trades into the session journal so a
        re-entry sees the same owners this view does."""
        try:
            sess = self._session
            if sess is None:
                return
            for i, entry in enumerate(self.draft_order or []):
                try:
                    _r, _t, _dp = entry
                    name = str(getattr(_t, 'team_name', '') or '')
                except Exception:
                    continue
                try:
                    if name and i < len(sess.slots):
                        sess.slots[i]['owner'] = name
                except Exception:
                    continue
        except Exception:
            pass

    def _show_conducted_state(self, year):
        """Honest terminal state for a year already conducted (war room or
        headless): never start a fresh draft over it."""
        self._draft_started = True
        try:
            self.draft_status_label.configure(
                text=f"{year} Draft Complete")
        except Exception:
            pass
        try:
            self.clock_label.configure(text="--")
            self.pick_info_label.configure(
                text="This draft was already conducted.")
        except Exception:
            pass
        for _b in ('draft_button', 'auto_button', 'trade_pick_button',
                    'sim_pick_button'):
            try:
                getattr(self, _b).configure(state='disabled')
            except Exception:
                pass
        try:
            self.grades_button.configure(state='normal')
        except Exception:
            pass
        self._ticker(f"The {year} NHL Entry Draft was already conducted. "
                     "Use Draft Grades to review it -- no new draft was "
                     "started.")
        # Grades come from history, never recomputed: recomputing from the
        # empty pick log of a re-attached view would overwrite the
        # persisted grades with nothing.
        try:
            _hist = getattr(self.app.league, 'draft_grades_history',
                            None) or {}
            _grades = [tuple(g) for g in (_hist.get(str(int(year))) or [])]
        except Exception:
            _grades = []
        if _grades:
            self._show_grades_popup(_grades)

    def _show_unavailable_state(self, reason):
        """Honest degraded state: the draft can't run, so say so and stop.
        Never silently restart."""
        self._draft_started = True
        try:
            self.draft_status_label.configure(text="Draft Unavailable")
        except Exception:
            pass
        try:
            self.clock_label.configure(text="--")
            self.pick_info_label.configure(text=str(reason))
        except Exception:
            pass
        for _b in ('draft_button', 'auto_button', 'trade_pick_button',
                    'sim_pick_button'):
            try:
                getattr(self, _b).configure(state='disabled')
            except Exception:
                pass
        self._ticker(str(reason))

    # ------------------------------------------------------------------
    def _ticker(self, line):
        # The ticker is a non-wrapping Listbox: fold long lines (e.g. the
        # draft-unavailable reason) into multiple rows so nothing is cut
        # off mid-sentence.
        for _ln in self._wrap_ticker_line(str(line)):
            self.ticker.insert(0, _ln)
        if self.ticker.size() > 120:
            self.ticker.delete(120, tk.END)

    def _wrap_ticker_line(self, line):
        """Split a ticker line into rows that fit the listbox width."""
        try:
            import textwrap
            from tkinter import font as _tkfont
            _w = self.ticker.winfo_width()
            if _w > 1:
                _f = _tkfont.Font(font=self.ticker.cget("font"))
                _avg = _f.measure("0123456789abcdefghijklmnopqrstuvwxyz") / 36
                _chars = max(20, int(_w / _avg) - 2) if _avg > 0 else 42
            else:
                _chars = 42
            _parts = textwrap.wrap(line, width=_chars,
                                   break_long_words=False,
                                   break_on_hyphens=False) or [line]
        except Exception:
            _parts = [line]
        # insert(0, ...) puts each new row on top, so feed the parts in
        # reverse to keep reading order.
        return list(reversed(_parts))

    def _available_prospects(self):
        return sorted(self.app.league.draft_prospects,
                      key=lambda p: getattr(p, 'draft_ranking', 0), reverse=True)

    def _board_sorted_available(self):
        """Available prospects ordered by the user's draft board, then consensus."""
        avail = self._available_prospects()
        rank = self.scmod.board_rank_map(self.app.user_team)
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

    def _show_shortlist_menu(self, event):
        """Right-click on a draft shortlist prospect -> full player menu."""
        try:
            idx = self.shortlist.nearest(event.y)
        except Exception:
            return
        if idx < 0 or idx >= len(getattr(self, '_shortlist_players', [])):
            return
        self.shortlist.selection_clear(0, tk.END)
        self.shortlist.selection_set(idx)
        player = self._shortlist_players[idx]
        PlayerContextMenu(self).show_context_menu(
            event, player, quick_scout=True)

    def _refresh_shortlist(self):
        self.shortlist.delete(0, tk.END)
        self._shortlist_players = []
        filt = self.pos_filter_var.get()
        from game_classes import PlayerPosition
        reports = self.app.user_team.scouting_reports
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
            _ban = "  [INELIGIBLE — rights held/lost]" if \
                self._redraft_banned(self.app.user_team, p) else ""
            self.shortlist.insert(tk.END, f"{p.full_name}  ({pos})  {pot}{_ban}")
            self.shortlist.itemconfig(
                idx, foreground=self._pot_color(
                    getattr(p, 'potential_grade', 'C')))
            self._shortlist_players.append(p)
            count += 1
            if count >= 30:
                break
        # Keep the tabbed board in step with the shortlist.
        try:
            self._refresh_available_board()
        except Exception:
            pass
        try:
            self._refresh_mypicks_board()
        except Exception:
            pass

    def _on_shortlist_double(self, event=None):
        self._on_shortlist_select()
        if self.selected_prospect is not None:
            self._arm_draft_button(self.selected_prospect)

    def _on_shortlist_select(self, event=None):
        sel = self.shortlist.curselection()
        if not sel:
            return
        p = self._shortlist_players[sel[0]]
        self.selected_prospect = p
        if self._armed_prospect is not None and self._armed_prospect is not p:
            self._disarm_draft_button()
        reports = self.app.user_team.scouting_reports
        report = reports.get(p.id)
        pot = (self.scmod.report_potential_display(report, p) if report
               else self.scmod.consensus_range(p) + " (consensus)")
        try:
            pos = p.primary_position.value
        except Exception:
            pos = "?"
        self.selected_label.configure(
            text=f"Selected: {p.full_name} ({pos}, {p.age}) — Potential {pot}")
        self._render_prospect_card(p)

    # -- M5: draft pace ----------------------------------------------------
    def _set_pace(self, mode):
        """1x / 4x / sim-to-my-pick. Sim takes effect immediately."""
        self._pace_mode = mode
        self._paint_pace_btns()
        if mode == 'sim' and not self._sim_active:
            try:
                if self._ai_after_id:
                    self.after_cancel(self._ai_after_id)
            except Exception:
                pass
            self._ai_after_id = None
            if self.current_pick < len(self.draft_order):
                self.process_draft_pick()

    def _paint_pace_btns(self):
        ct = self._ct
        for mode, btn in getattr(self, '_pace_btns', {}).items():
            active = mode == getattr(self, '_pace_mode', '1x')
            try:
                btn.configure(fg_color=ct['TEAL'] if active else ct['CARD'],
                              text_color=ct['BG'] if active else ct['TEXT_DIM'])
            except Exception:
                pass

    def _mp_clock_for(self, team):
        """True when a remote human owns this pick (MP draft-clock wait)."""
        try:
            return bool(
                getattr(self.app, 'mp_host', None) is not None
                and not bool(getattr(team, 'is_user_team', False))
                and __import__('game_classes').is_human_managed(team))
        except Exception:
            return False

    def _refresh_clock_ui(self, round_num, team_on_clock, overall):
        """Header/clock/next-pick labels + button states. No scheduling and
        no market hooks -- safe to call from the sim loop."""
        if round_num != self.current_round:
            self.current_round = round_num
        try:
            _nhl_count = sum(1 for _t in self.app.league.teams
                             if getattr(_t, 'league_name', '') ==
                             'National Hockey League') or 32
        except Exception:
            _nhl_count = 32
        pick_in_round = (self.current_pick % max(1, _nhl_count)) + 1
        self.draft_status_label.configure(
            text=f"Round {round_num} of {self.total_rounds}")
        self.clock_label.configure(text=team_on_clock.team_name)
        self.pick_info_label.configure(
            text=f"Pick #{overall}  (Round {round_num}, #{pick_in_round} in round)")
        is_user = team_on_clock == self.app.user_team
        state = 'normal' if is_user else 'disabled'
        self.draft_button.configure(state=state)
        self.auto_button.configure(state=state)
        self.trade_pick_button.configure(state=state)
        nxt = next((i for i in range(self.current_pick, len(self.draft_order))
                    if self.draft_order[i][1] == self.app.user_team), None)
        if nxt is not None:
            r = self.draft_order[nxt][0]
            self.next_pick_label.configure(
                text=f"Your next pick: #{nxt + 1} (Round {r})")
        else:
            self.next_pick_label.configure(text="No picks remaining")

    def _start_sp_draft_clock(self):
        """Single-player draft countdown for the local human's pick.

        Expiry auto-picks via the user's own strategy (BPA/Need) so the
        draft can never stall. The tick defers while a modal draft dialog
        (trade offer/counter) holds the grab -- the clock never fires
        under a dialog.
        """
        self._cancel_sp_draft_clock()
        try:
            _secs = int((self.app.get_settings().get('draft', {}) or {}
                         ).get('clock_seconds', 60))
        except Exception:
            _secs = 60
        if _secs <= 0:
            return
        self._sp_clock_left = _secs
        self._sp_clock_tick()

    def _cancel_sp_draft_clock(self):
        _id = getattr(self, '_sp_clock_id', None)
        if _id:
            try:
                self.after_cancel(_id)
            except Exception:
                pass
        self._sp_clock_id = None

    def _sp_clock_tick(self):
        self._sp_clock_id = None
        if self.current_pick >= len(self.draft_order):
            return
        _r, _team, _dp = self.draft_order[self.current_pick]
        if _team != self.app.user_team:
            return
        try:
            if self.grab_current() is not None:
                # Modal open (trade offer/counter): defer, don't fire.
                self._sp_clock_id = self.after(1000, self._sp_clock_tick)
                return
        except Exception:
            pass
        if self._sp_clock_left <= 0:
            try:
                self._ticker(f"{_team.team_name} ran out the clock -- "
                             f"auto-pick.")
            except Exception:
                pass
            self.auto_pick()
            return
        try:
            self.clock_label.configure(
                text=f"{_team.team_name} ({self._sp_clock_left}s)")
        except Exception:
            pass
        self._sp_clock_left -= 1
        self._sp_clock_id = self.after(1000, self._sp_clock_tick)

    def _ai_step(self):
        """One synchronous AI step for sim mode. Returns True to continue."""
        if self.current_pick >= len(self.draft_order):
            return False
        round_num, team_on_clock, _dp = self.draft_order[self.current_pick]
        if team_on_clock == self.app.user_team:
            return False
        if self._mp_clock_for(team_on_clock):
            return False
        if round_num == 1:
            try:
                from draft_day_trades import on_clock_check
                if on_clock_check(self):
                    # The call may have moved the pick; mirror the new
                    # owners into the session journal.
                    self._sync_session_owners()
                    return True  # order changed; step again
            except Exception:
                pass
            _r2, team_on_clock, _dp = self.draft_order[self.current_pick]
            if (team_on_clock == self.app.user_team
                    or self._mp_clock_for(team_on_clock)):
                return False
            round_num = _r2
        overall = self.current_pick + 1
        self._refresh_clock_ui(round_num, team_on_clock, overall)
        reach, steal = self._do_ai_pick()
        if overall <= 3 or reach or steal:
            # Pause on round-1 drama: drop to 1x so the user actually sees it.
            self._set_pace('1x')
            return False
        return True

    def _run_sim(self):
        """Sim-to-my-pick: run AI picks synchronously until the user's
        clock, an MP clock, draft end, or round-1 drama."""
        if self._sim_active:
            return
        self._sim_active = True
        try:
            guard = 0
            while guard < 500 and self._ai_step():
                guard += 1
        finally:
            self._sim_active = False
        self._refresh_shortlist()
        self.process_draft_pick()

    # ------------------------------------------------------------------
    def process_draft_pick(self):
        if self.current_pick >= len(self.draft_order):
            self.end_draft()
            return
        round_num, team_on_clock, _dp = self.draft_order[self.current_pick]
        # DRAFT-DAY MARKET: round 1 runs like the trade deadline. Before the
        # clock starts, the phones ring -- an AI club below may trade up for
        # the slot (AI on the clock), or an AI club may call the user with an
        # offer (user on the clock). Human-managed clubs are never moved
        # without consent; multiplayer draft-clock waits are untouched.
        if round_num == 1:
            try:
                from draft_day_trades import on_clock_check
                if on_clock_check(self):
                    round_num, team_on_clock, _dp = \
                        self.draft_order[self.current_pick]
                    # The call may have moved the pick; mirror the new
                    # owners into the session journal.
                    self._sync_session_owners()
            except Exception:
                pass
        if round_num != self.current_round:
            self.current_round = round_num
        overall = self.current_pick + 1
        self._refresh_clock_ui(round_num, team_on_clock, overall)

        is_user = team_on_clock == self.app.user_team

        # The phone rings for the user too: an AI club that loves someone
        # near the top of the board may call about your round-1 pick.
        if is_user and round_num == 1:
            try:
                from draft_day_trades import incoming_offer_for_user
                incoming_offer_for_user(self)
                # The call may have moved the pick; re-read the clock and
                # mirror the new owners into the session journal.
                self._sync_session_owners()
                if self.current_pick < len(self.draft_order):
                    _r2, team_on_clock, _dp = \
                        self.draft_order[self.current_pick]
                    is_user = team_on_clock == self.app.user_team
                    if not is_user:
                        state = 'disabled'
                        self.draft_button.configure(state=state)
                        self.auto_button.configure(state=state)
                        self.trade_pick_button.configure(state=state)
            except Exception:
                pass

        # Your next pick info is handled inside _refresh_clock_ui.

        # SINGLE-PLAYER draft clock (item 1): the local human's pick runs
        # a countdown; expiry auto-picks via their own strategy. Purely
        # single-player (mp_host is None) -- multiplayer keeps its own
        # 60s host clock untouched.
        if is_user and getattr(self.app, 'mp_host', None) is None:
            self._start_sp_draft_clock()
        else:
            self._cancel_sp_draft_clock()

        # MULTIPLAYER: a team claimed by a remote human doesn't get an AI
        # auto-pick -- its manager picks live on the draft clock (60s,
        # then the AI makes the pick for them).
        if not is_user:
            if self._mp_clock_for(team_on_clock):
                self.draft_button.configure(state='disabled')
                self.auto_button.configure(state='disabled')
                self.trade_pick_button.configure(state='disabled')
                self.clock_label.configure(
                    text=f"{team_on_clock.team_name} (GM deciding...)")
                try:
                    self.app._mp_open_draft_clock(
                        team_on_clock, round_num, overall)
                except Exception as e:
                    print(f"draft clock failed (non-fatal): {e}")
                try:
                    if getattr(self, '_mp_wait_id', None):
                        self.after_cancel(self._mp_wait_id)
                except Exception:
                    pass
                self._mp_wait_id = self.after(
                    1000, self._mp_check_client_pick)
                return

        if not is_user:
            if self._ai_after_id:
                try:
                    self.after_cancel(self._ai_after_id)
                except Exception:
                    pass
            if self._pace_mode == 'sim' and not self._sim_active:
                self._run_sim()
                return
            delay = 150 if self._pace_mode == '4x' else 650
            self._ai_after_id = self.after(delay, self.ai_make_pick)

    def _mp_check_client_pick(self):
        """Draft-clock wait loop: execute the client's pick, auto-pick on
        timeout, or keep waiting."""
        self._mp_wait_id = None
        try:
            st = getattr(self.app, '_mp_draft_clock', None)
        except Exception:
            st = None
        if not st or st.get("done"):
            return
        if self.current_pick >= len(self.draft_order):
            return
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        if st.get("team_id") != team_on_clock.team_name or \
                st.get("overall") != self.current_pick + 1:
            return  # stale clock (draft moved on without us)
        pid = st.get("pick_id")
        if pid:
            prospect = None
            try:
                for p in getattr(self.app.league,
                                 "draft_prospects", None) or []:
                    if str(getattr(p, "id", "")) == str(pid):
                        prospect = p
                        break
            except Exception:
                pass
            if prospect is not None:
                if self._redraft_banned(team_on_clock, prospect):
                    # Real NHL rule: ignore the illegal selection; clear it
                    # so the client can submit a legal pick before the clock.
                    try:
                        st["pick_id"] = None
                        self.app.mp_host.broadcast_chat(
                            f"{team_on_clock.team_name} tried to re-draft a "
                            f"prospect whose rights they lost -- not allowed "
                            f"under NHL rules.")
                    except Exception:
                        pass
                    self._mp_wait_id = self.after(
                        1000, self._mp_check_client_pick)
                    return
                st["done"] = True
                try:
                    self.app._mp_clear_draft_clock()
                except Exception:
                    pass
                self.execute_pick(team_on_clock, prospect)
                return
            # Unknown id (race): keep waiting for a valid one.
        import time as _time
        if _time.time() > float(st.get("deadline", 0)):
            st["done"] = True
            try:
                self.app._mp_clear_draft_clock()
            except Exception:
                pass
            try:
                self.app.mp_host.broadcast_chat(
                    f"{team_on_clock.team_name} ran out the draft clock -- "
                    f"auto-pick.")
            except Exception:
                pass
            self.ai_make_pick()
            return
        self._mp_wait_id = self.after(1000, self._mp_check_client_pick)

    def _do_ai_pick(self):
        """Execute one AI pick synchronously. Returns (reach, steal).

        Selection itself lives in draft_night.ai_select_prospect -- the
        same implementation the headless conductor uses, so the war room
        and the sim can't diverge.
        """
        if self.current_pick >= len(self.draft_order):
            return (False, False)
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        available = self._available_prospects()
        if not available:
            self.end_draft()
            return (False, False)
        # Real NHL rule: the club that lost a re-entry's rights can't
        # re-select him in this draft -- filter him from this team's pool.
        available = [p for p in available
                     if not self._redraft_banned(team_on_clock, p)]
        if not available:
            self.end_draft()
            return (False, False)
        try:
            needs = self.te.team_needs(team_on_clock)
        except Exception:
            needs = []
        try:
            board = (getattr(self, 'team_boards', None) or {}).get(
                getattr(team_on_clock, 'team_name', None))
        except Exception:
            board = None
        try:
            _strat = self.app.ai_manager.get_team_strategy(
                getattr(team_on_clock, 'team_name', ''))
            priority = getattr(_strat, 'priority', None)
        except Exception:
            priority = None
        round_num = self.draft_order[self.current_pick][0]
        overall = self.current_pick + 1
        # Dynamic need pivot: (position, round) this club already drafted
        # tonight, mirroring the headless conductor.
        _tname = getattr(team_on_clock, 'team_name', None)
        _drafted = []
        try:
            for _ptn, _po, _pp in (getattr(self, 'picks_made', None) or []):
                if _ptn != _tname:
                    continue
                try:
                    _ppos = _pp.primary_position.value
                except Exception:
                    _ppos = "?"
                try:
                    _prnd = self.draft_order[_po - 1][0]
                except Exception:
                    _prnd = 7
                _drafted.append((_ppos, _prnd))
        except Exception:
            _drafted = []
        selected, reach, steal = self.dn.ai_select_prospect(
            team_on_clock, available, board, needs, round_num, priority,
            self._draft_rng, overall=overall, drafted=_drafted)
        if selected is None:
            self.end_draft()
            return (False, False)
        self.execute_pick(team_on_clock, selected,
                          reach=reach, steal=steal)
        return (reach, steal)

    def ai_make_pick(self):
        """Scheduled (1x/4x) AI pick: one synchronous pick, then the draft
        flow continues via execute_pick -> process_draft_pick."""
        self._ai_after_id = None
        if self.current_pick >= len(self.draft_order):
            return
        self._do_ai_pick()

    def make_user_pick(self):
        if not self.selected_prospect:
            messagebox.showwarning("No Prospect", "Select a prospect from the shortlist.")
            return
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        if team_on_clock != self.app.user_team:
            return
        p = self.selected_prospect
        if p not in self.app.league.draft_prospects:
            messagebox.showwarning("Unavailable", "That prospect was already drafted.")
            self._refresh_shortlist()
            return
        if self._redraft_banned(team_on_clock, p):
            messagebox.showwarning(
                "Not Eligible",
                "NHL rules: you held this prospect's draft rights and lost "
                "them unsigned -- your club can't re-select him in this draft.")
            return
        # M4: two-step inline confirm -- first click arms, second commits.
        # No per-pick modal; mis-clicks die on the armed button instead.
        if self._armed_prospect is not p:
            self._arm_draft_button(p)
            return
        self._disarm_draft_button()
        self.execute_pick(team_on_clock, p)

    def _arm_draft_button(self, p):
        """Arm the draft button for one prospect; a second click commits."""
        self._armed_prospect = p
        name = getattr(p, 'full_name', '?')
        if len(name) > 20:
            name = name[:19] + "…"
        try:
            self.draft_button.configure(text=f"CONFIRM — DRAFT {name}")
        except Exception:
            pass

    def _disarm_draft_button(self):
        self._armed_prospect = None
        try:
            self.draft_button.configure(text="Draft Selected")
        except Exception:
            pass

    def auto_pick(self):
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        if team_on_clock != self.app.user_team:
            return
        available = self._board_sorted_available()
        if not available:
            # Prospect pool exhausted: terminate the draft so no pick
            # driver can spin on an un-advanced current_pick.
            self.end_draft()
            return
        # Real NHL rule: skip prospects this club can't re-select.
        available = [p for p in available
                     if not self._redraft_banned(team_on_clock, p)]
        if not available:
            self.end_draft()
            return
        if self.strategy_var.get() == "Need":
            needs = self.te.team_needs(self.app.user_team)
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

    def _redraft_banned(self, team, player) -> bool:
        """Real NHL rule: a club that held a prospect's draft rights and lost
        them unsigned may not re-select him in the immediate re-entry draft."""
        try:
            banned_from = str(getattr(player, 'draft_reentry_from', '') or '')
            return bool(banned_from) and \
                banned_from == getattr(team, 'team_name', None)
        except Exception:
            return False

    def execute_pick(self, team, player, reach=False, steal=False):
        # BUG-2 fix: transactional commit -- the overall pick number is the
        # idempotency key. A repeat call for an already-committed overall
        # (stale re-entry, double event) is rejected, never double-applied.
        try:
            _ov = int(self.current_pick) + 1
        except Exception:
            return False
        try:
            _sess = self._session
            if _sess is not None and _sess.has_pick(_ov):
                return False
        except Exception:
            pass
        round_num, _t, _dp = self.draft_order[self.current_pick]
        overall = self.current_pick + 1
        if self._redraft_banned(team, player):
            # Defensive: pick paths filter this upstream; never advance.
            return False
        team.add_player(player, "prospects")
        # Draft rights: stamp immediately at pick time (CHL 4yr/3yr /
        # NCAA 4yr / Europe 4yr from the player's junior league, new
        # CBA). The season rollover has a backstop for any prospect
        # that slips through, but the pick path is the canonical
        # stamper.
        try:
            _dy = getattr(self.app.league, "draft_prospects_year", None) \
                or getattr(getattr(self.app, "current_date", None), "year", 2027)
            self.app.league.stamp_draft_rights(player, team.team_name, _dy)
        except Exception:
            pass
        # The immediate re-draft ban is spent once he's selected.
        try:
            player.draft_reentry_from = ""
        except Exception:
            pass
        try:
            self.app.league.draft_prospects.remove(player)
        except ValueError:
            pass
        try:
            pos = player.primary_position.value
        except Exception:
            pos = "?"
        pot_grade = self._GRADE_BASE.get(
            str(getattr(player, 'potential_grade', 'C')).strip(), 'C')
        _drid = self.draft_results_tree.insert('', 0, values=(
            overall, team.team_name, player.full_name, pos,
            getattr(player, 'potential_grade', '?')),
            tags=(f"pot_{pot_grade}",))
        self.app.tree_maps.setdefault(self.draft_results_tree, {})[_drid] = player
        self._ticker(self.dn.ticker_line(overall, team.team_name, player,
                                         round_num, reach=reach, steal=steal,
                                         rng=self._draft_rng))
        self.picks_made.append((team.team_name, overall, player))
        # Draft Story Engine: fire pick drama (reach/steal/surprise)
        try:
            from draft_stories import draft_pick_drama
            # Get projected rank from league
            proj_rank = None
            try:
                proj_map = getattr(self.app.league, 'prospect_projected_rank', {})
                proj_rank = proj_map.get(id(player))
            except Exception:
                pass
            if proj_rank is None:
                # Fallback: use reach/steal flags to estimate
                proj_rank = overall  # no drama if unknown
            # Only fire for notable picks (top 3, or reach/steal)
            if overall <= 3 or reach or steal:
                # Get app reference
                app = self.app
                draft_pick_drama(app, overall, player, team, proj_rank)
        except Exception:
            pass
        try:
            self.app.news_log.append({
                'date': self.app.current_date, 'type': 'draft',
                'story': f"With pick #{overall}, the {team.team_name} select "
                         f"{player.full_name} ({pos})."})
        except Exception:
            pass
        self.current_pick += 1
        # BUG-2 fix: journal the commit on the league-owned session (the
        # durable record across view destruction). record_pick is
        # idempotent per overall; the cursor and RNG stream persist too.
        try:
            if self._session is not None:
                self._session.record_pick(
                    overall, team.team_name, getattr(player, 'id', None))
                self._session.current_pick = self.current_pick
                try:
                    self._session.rng_state = self._draft_rng.getstate()
                except Exception:
                    pass
        except Exception:
            pass
        self.selected_prospect = None
        self._disarm_draft_button()
        self.selected_label.configure(text="No prospect selected")
        self._refresh_shortlist()
        # The research strip names available prospects: keep it in step
        # with the pool after every pick.
        try:
            self._refresh_draft_research()
        except Exception:
            pass
        # Keep the board scrolled to the newest pick (skip during sim --
        # the sim loop drives the draft and scroll churn is pure noise).
        if not self._sim_active:
            kids = self.draft_results_tree.get_children()
            if kids:
                self.draft_results_tree.see(kids[0])
        # In sim mode the driver loop advances the draft; otherwise the
        # next pick is scheduled/driven from here.
        if not self._sim_active:
            self.process_draft_pick()
        return True

    # ------------------------------------------------------------------
    def trade_current_pick(self):
        """Draft-day trade: swap your current pick with a partner's pick."""
        ct = self._ct
        if self.current_pick >= len(self.draft_order):
            return
        _r, team_on_clock, user_pick = self.draft_order[self.current_pick]
        if team_on_clock != self.app.user_team:
            messagebox.showinfo("Not Your Pick", "You can only trade your own pick.")
            return
        if user_pick is None:
            # Fallback draft order (no pick objects): nothing to trade.
            messagebox.showinfo(
                "No Pick Data",
                "Pick ownership data isn't available for this draft, "
                "so the pick can't be traded.")
            return
        dlg = InGamePopup(self)
        dlg.title("Trade this pick")
        dlg.geometry("480x460")
        dlg.configure(fg_color=ct['BG'])
        dlg.transient(self)
        overall = self.current_pick + 1
        self._heading(dlg, text=f"Your pick: #{overall} (Round {_r})",
                size=13).pack(pady=(14, 4))
        self._body(dlg, text="Select a partner and one of their upcoming picks:",
             dim=True).pack(pady=(0, 8))

        teams = sorted(t.team_name for t in self.app.league.teams
                       if t != self.app.user_team
                       and getattr(t, 'league_name', '') ==
                       'National Hockey League')

        def _partner_picks(name):
            team = next((t for t in self.app.league.teams
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
            partner = next(t for t in self.app.league.teams
                           if t.team_name == combo.get())
            resp = self.te.ai_consider_trade(
                partner, [user_pick], [partner_pick],
                user_team=self.app.user_team)
            if resp.decision == 'reject':
                messagebox.showerror("Rejected", resp.message)
                return
            if resp.decision == 'counter':
                extra = resp.want_added + resp.will_add
                detail = "; ".join(self.te.asset_label(a) for a in extra)
                if not messagebox.askyesno("Counter-offer",
                                           f"{resp.message}\n\nAccept?"):
                    return
                _done = self._execute_pick_swap(
                    j, user_pick, partner_pick,
                    resp.want_added, resp.will_add)
            else:
                _done = self._execute_pick_swap(
                    j, user_pick, partner_pick, [], [])
            if not _done:
                return  # legality preflight blocked it; dialog stays open
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

    def _validate_pick_swap(self, partner_team, user_pick, partner_pick,
                              want_added, will_add):
        """Centralized legality preflight for a draft pick swap: the two
        base picks PLUS any counter-added assets. Mirrors the gates
        trade_engine enforces for full trades -- freeze/deadline,
        ownership, cap in both directions, NTC/NMC consent.

        The counter path used to skip all of this: an AI counter could
        add a player who'd since moved, blow either cap, or carry an
        un-waived clause straight into the swap. Returns (ok, message).
        """
        te = self.te
        league = self.app.league
        user_team = self.app.user_team
        user_gives = [user_pick] + list(want_added or [])
        partner_gives = [partner_pick] + list(will_add or [])
        # 1. Freeze / deadline gate
        try:
            _dstr = str(getattr(self.app, 'current_date', ''))
            if not te.trades_allowed(_dstr, league):
                return (False, "Trading is frozen right now "
                               "(trade freeze / deadline).")
        except Exception:
            pass
        # 2. Ownership -- counter-added assets may have moved since the
        # counter was built.
        for a in user_gives:
            if te._is_pick(a):
                if str(getattr(a, 'current_team', '')) != \
                        user_team.team_name:
                    return (False, f"You no longer own "
                                   f"{te.asset_label(a)}.")
            elif a not in (getattr(user_team, 'roster', []) or []):
                return (False, f"{getattr(a, 'full_name', 'A player')} is "
                                "no longer on your roster.")
        for a in partner_gives:
            if te._is_pick(a):
                if str(getattr(a, 'current_team', '')) != \
                        partner_team.team_name:
                    return (False, f"{partner_team.team_name} no longer "
                                   f"owns {te.asset_label(a)}.")
            elif a not in (getattr(partner_team, 'roster', []) or []):
                return (False, f"{getattr(a, 'full_name', 'A player')} is "
                                "no longer on their roster.")
        # 3. Cap, both directions
        try:
            if not te._cap_ok_after(user_team, user_gives, partner_gives):
                return (False, "This trade puts YOU over the salary cap.")
        except Exception:
            pass
        try:
            if not te._cap_ok_after(partner_team, partner_gives, user_gives):
                return (False, f"This trade puts {partner_team.team_name} "
                                "over the salary cap.")
        except Exception:
            pass
        # 4. NTC/NMC consent on every moving player
        try:
            for _from, _to, _assets in (
                    (user_team, partner_team, user_gives),
                    (partner_team, user_team, partner_gives)):
                _skaters = [a for a in _assets if not te._is_pick(a)]
                for _v in te.trade_vetoes(_from, _to, _skaters, league):
                    _ok, _why = te.will_waive_ntc(
                        _v["player"], _from, _to, league)
                    if not _ok:
                        return (False, _why or "A no-trade clause blocks "
                                             "this deal.")
        except Exception:
            pass
        return (True, "")

    def _execute_pick_swap(self, partner_idx, user_pick, partner_pick,
                           want_added, will_add):
        user_team = self.app.user_team
        partner_team = self.draft_order[partner_idx][1]
        # Legality preflight: the counter path used to skip every gate.
        _ok, _why = self._validate_pick_swap(
            partner_team, user_pick, partner_pick, want_added, will_add)
        if not _ok:
            messagebox.showerror("Trade blocked", _why)
            return False
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
        # History + news. CompletedTrade records the FULL deal -- the two
        # base picks plus every counter-added asset (the old record
        # silently dropped the extras).
        gm = getattr(self.app, 'game_manager', None)
        summary = (f"{user_team.team_name} acquires pick "
                   f"#{partner_idx + 1} from {partner_team.team_name}.")
        _user_gives = [user_pick] + list(want_added or [])
        _partner_gives = [partner_pick] + list(will_add or [])
        if gm is not None:
            if not hasattr(gm, 'trade_history'):
                gm.trade_history = []
            gm.trade_history.append(self.te.CompletedTrade(
                str(getattr(gm, 'current_date', '')), user_team.team_name,
                partner_team.team_name,
                [self.te.asset_label(a) for a in _user_gives],
                [self.te.asset_label(a) for a in _partner_gives], summary))
        try:
            self.app.add_news_story(f"DRAFT TRADE: {summary}")
        except Exception:
            pass
        self._ticker(f"TRADE: {summary}")
        return True

    # ------------------------------------------------------------------
    def show_grades(self):
        """Draft review: grade + value-vs-slot for every team, the best
        value pick of the draft, and the user's own picks -- persisted to
        league.draft_grades_history so past drafts can be revisited.

        Grades measure the draft, not hidden truth: they compare each
        club's haul against slot value (the public draft board), never
        against a prospect's true ceiling.
        """
        ct = self._ct
        try:
            _lg = self.app.league
            _dy = int(getattr(_lg, 'draft_prospects_year', None)
                      or getattr(_lg, 'season_year', 0) or 0)
            grades = self.dn.persist_draft_grades(
                _lg, _dy, self.picks_made)
        except Exception:
            grades = self.dn.draft_grades(self.picks_made)
        self._show_grades_popup(grades)

    def _show_grades_popup(self, grades):
        """Render the Draft Grades dialog from precomputed `grades`.

        Split out of show_grades so a completed draft's persisted grades
        can be shown without recomputing (recomputing from an empty pick
        log would overwrite the history with nothing).
        """
        ct = self._ct
        dlg = InGamePopup(self)
        dlg.title("Draft Grades")
        dlg.geometry("560x680")
        dlg.configure(fg_color=ct['BG'])
        dlg.transient(self)
        self._heading(dlg, text="Draft Grades", size=16).pack(pady=(14, 2))
        self._body(
            dlg,
            text=("How each club's haul stacks up against slot value, "
                  "curved across all 32 teams. A+ is a franchise-altering "
                  "night; F means the board said the picks were reaches."),
            size=10, dim=True, wraplength=500).pack(pady=(0, 8))

        # Best value pick of the draft (value / slot value).
        _best_line = ""
        try:
            _best = max(
                self.picks_made,
                key=lambda _t: (self.dn.drafted_player_value(_t[2])
                                / max(1.0, self.dn.pick_slot_value(_t[1]))))
            _btn, _bov, _bp = _best
            _br = (self.dn.drafted_player_value(_bp)
                   / max(1.0, self.dn.pick_slot_value(_bov)))
            _best_line = (f"Best value: #{_bov} "
                          f"{getattr(_bp, 'full_name', '?')} ({_btn}) -- "
                          f"{_br:.2f}x slot value")
        except Exception:
            pass
        if _best_line:
            self._body(dlg, text=_best_line, size=11).pack(pady=(0, 6))

        grades_card = ctk.CTkFrame(dlg, fg_color=ct['CARD'], corner_radius=8)
        grades_card.pack(fill='both', expand=True, padx=14, pady=6)
        lb = tk.Listbox(grades_card, bg=ct['CARD'], fg=ct['TEXT'],
                        relief='flat', font=("Segoe UI", 11),
                        selectbackground=ct['ROW_SELECTED'],
                        highlightthickness=0, activestyle='none')
        lb.pack(fill='both', expand=True, padx=8, pady=8)
        user_grade = None
        _uname = getattr(getattr(self.app, 'user_team', None),
                         'team_name', '')
        for team, grade, ratio in grades:
            lb.insert(tk.END, f"  {grade:>2}   {team:<28}  {ratio:.2f}x")
            lb.itemconfig(tk.END, foreground=self.dn.grade_color(grade))
            if team == _uname:
                user_grade = grade
        # The user's own picks, so the review answers "how did I do".
        _mine = [(ov, p) for tn, ov, p in self.picks_made if tn == _uname]
        if _mine:
            self._body(dlg, text="Your picks:", size=11).pack(
                pady=(6, 0))
            _lines = []
            for _ov, _p in _mine[:9]:
                try:
                    _pos = _p.primary_position.value
                except Exception:
                    _pos = "?"
                _lines.append(f"#{_ov} {getattr(_p, 'full_name', '?')} "
                              f"({_pos})")
            self._body(dlg, text="   ".join(_lines), size=10, dim=True,
                       wraplength=520).pack(pady=(0, 4))
        if user_grade:
            ug = ctk.CTkLabel(dlg, text=f"Your draft grade: {user_grade}",
                              font=("Segoe UI", 13, 'bold'),
                              text_color=self.dn.grade_color(user_grade))
            ug.pack(pady=10)
        self._primary_button(dlg, text="Close",
                             command=dlg.destroy).pack(pady=(0, 12))

    def end_draft(self):
        # Terminate the pick order: a draft that ends early (e.g. the
        # prospect pool runs out) must not leave current_pick mid-order,
        # or any direct pick driver spins forever re-calling pick methods.
        try:
            self.current_pick = len(self.draft_order)
        except Exception:
            pass
        if self._ai_after_id:
            try:
                self.after_cancel(self._ai_after_id)
            except Exception:
                pass
        self._ai_after_id = None
        try:
            if getattr(self, '_mp_wait_id', None):
                self.after_cancel(self._mp_wait_id)
        except Exception:
            pass
        self._mp_wait_id = None
        try:
            self.app._mp_clear_draft_clock()
        except Exception:
            pass
        self.draft_status_label.configure(text="Draft Complete")
        self.clock_label.configure(text="—")
        self.pick_info_label.configure(text="All 7 rounds complete")
        self.draft_button.configure(state='disabled')
        self.auto_button.configure(state='disabled')
        self.trade_pick_button.configure(state='disabled')
        self.grades_button.configure(state='normal')
        self._ticker("That's a wrap on draft night.")
        # Real NHL re-entry: undrafted prospects are automatically eligible
        # again next year while age-eligible -- stash them for the next draft
        # class (processed in _hold_entry_draft). The immediate re-draft ban
        # (draft_reentry_from) only lasts one draft, so clear it now.
        try:
            _lg = self.app.league
            _left = list(getattr(_lg, "draft_prospects", None) or [])
            for _p in _left:
                try:
                    _p.draft_reentry_from = ""
                except Exception:
                    pass
            _lg.undrafted_pool = _left
        except Exception:
            pass
        # Stamp this draft year as conducted (idempotency guard): the
        # headless conductor and the offseason guarantee both respect it,
        # so a war-room draft can never be re-conducted by the sim.
        try:
            _lg = self.app.league
            _dy = int(getattr(_lg, 'draft_prospects_year', None)
                      or getattr(_lg, 'season_year', 0) or 0)
            self.dn.mark_draft_conducted(_lg, _dy)
            # BUG-2 fix: the draft is done -- close the league-owned
            # session so any re-entry shows the conducted state, never a
            # fresh draft.
            try:
                if self._session is not None:
                    self._session.completed = True
            except Exception:
                pass
            try:
                _lg.entry_draft_session = None
            except Exception:
                pass
        except Exception:
            pass
        # Stop the single-player draft clock (item 1).
        try:
            self._cancel_sp_draft_clock()
        except Exception:
            pass
        self.show_grades()




class DraftWindow(InGamePopup):
    """Popup wrapper around DraftView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("NHL Entry Draft")
        self._view = DraftView(self, app=parent, *args, **kwargs)
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
class ScheduleView(ctk.CTkFrame):
    """League Schedule (CustomTkinter): tabbed My Team / League tables,
    month-filter combo, color-coded game rows (win/loss/today), modern
    action buttons. All schedule logic preserved."""

    def __init__(self, parent, app=None):
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
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ScheduleWindow wrapper
        self.configure(fg_color=BG)

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

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

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
            # Marquee playoff series: the dates fans circle. Gold beats
            # win/loss green/red -- it is the rarer, deliberate signal.
            tree.tag_configure('marquee', foreground=ct['GOLD'])
            # Background-only companion to 'today': lets a marquee game
            # played today keep its highlight without a second tag
            # fighting 'marquee' over the foreground.
            tree.tag_configure('today_bg', background=ct['ROW_SELECTED'])

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
                         command=lambda c=col, t=tree: self.app._sort_treeview_generic(t, c))
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
            'has_been_played': str(entry['status']).startswith("Final"),
        }

    def watch_selected_game(self):
        """Launch the game viewer for the selected game."""
        game_data = self.get_selected_game_data()
        if not game_data:
            messagebox.showwarning("No Game Selected", "Please select a game to watch.")
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
            is_past_game = game_data['date'] < self.app.current_date
        except TypeError:
            is_past_game = False

        if is_past_game:
            response = messagebox.askyesno(
                "Game Not Played",
                "This game hasn't been played yet.\n\n"
                "Would you like to simulate and watch it?\n"
                "(The result will be recorded in your season.)")
            if not response:
                return
            self._launch_game_viewer(game_data, commit=True)
        else:
            response = messagebox.askyesno(
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
            messagebox.showwarning("No Game Selected", "Please select a game to simulate.")
            return

        if game_data['has_been_played']:
            messagebox.showinfo("Game Already Played", "This game has already been played.")
            return

        try:
            is_past_game = game_data['date'] < self.app.current_date
        except TypeError:
            is_past_game = False

        if not is_past_game:
            messagebox.showinfo(
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
                    self.app.game_results.append(game_result)
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
            messagebox.showerror("Game Viewer Error",
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
            'game_stats': getattr(sim, 'game_stats', {}) or {},
            'team_stats': getattr(sim, 'team_stats', {}) or {},
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
                messagebox.showinfo("Already Recorded",
                                       "A result for this game is already recorded.")
                self.update_views()
                return

            game_result = self._build_game_result(game_data, sim)

            # Add to game results
            self.app.game_results.append(game_result)

            # Update team stats
            self._update_team_stats_from_game(game_result)

            # Show result
            messagebox.showinfo("Game Simulated",
                                   f"Game Result:\n\n"
                                   f"{away_team.team_name} {sim.away_score} - {sim.home_score} {home_team.team_name}")

        except Exception as e:
            messagebox.showerror("Simulation Error",
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
        for gr in self.app.game_results:
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
            messagebox.showwarning("No Game Selected",
                                      "Please select a game first.")
            return
        result = self._find_game_result(game_data)
        if not result:
            messagebox.showinfo("No Data",
                                   "This game hasn't been played yet — no stats available.")
            return
        GameDetailWindow(self.app, result, initial_tab="stats")

    def view_game_recap(self):
        """View game recap and highlights."""
        game_data = self.get_selected_game_data()
        if not game_data:
            messagebox.showwarning("No Game Selected",
                                      "Please select a game first.")
            return
        result = self._find_game_result(game_data)
        if not result:
            messagebox.showinfo("No Data",
                                   "This game hasn't been played yet — no recap available.")
            return
        GameDetailWindow(self.app, result, initial_tab="recap")

    def _matchup_narrative(self, home, away):
        """Live narrative metadata for a regular-season matchup.

        Reads the rivalry store, ledger grudge memory and iconic history
        (narrative_ledger.matchup_narrative); cached per matchup for the
        render pass so the 82-game list stays cheap. Playoff rows never
        reach here -- the bracket's stamp wins.
        """
        try:
            hn = getattr(home, "team_name", "") or ""
            an = getattr(away, "team_name", "") or ""
            key = (hn, an)
            cache = self.__dict__.setdefault("_narrative_cache", {})
            if key not in cache:
                from narrative_ledger import get_ledger, matchup_narrative
                try:
                    _led = get_ledger(self.app)
                except Exception:
                    _led = None
                cache[key] = matchup_narrative(
                    home, away, league=getattr(self.app, "league", None),
                    ledger=_led)
            return cache[key]
        except Exception:
            return None

    @staticmethod
    def _playoff_entry_result(raw):
        """(score, status) for a bracket-stamped playoff entry, else None.

        The bracket sims playoff games itself, so they never land in
        game_results -- but _stamp_played_game records the score on the
        schedule entry. The calendar prefers the stamp.
        """
        raw = raw or {}
        if raw.get("playoff") and raw.get("played"):
            return (f"{raw.get('away_score', 0)}-{raw.get('home_score', 0)}",
                    "Final")
        return None

    @staticmethod
    def _parse_schedule_entry(game_entry):
        """Normalize one league.schedule entry.

        Returns (date, home_team, away_team, raw) where raw is the
        original dict entry (carries playoff/marquee/hype fields) or
        None for tuple-format entries. None for malformed entries and
        non-game special events (e.g. All-Star / NHL_EVENT entries).
        """
        game_date = home = away = None
        raw = game_entry if isinstance(game_entry, dict) else None
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
        return game_date, home, away, raw

    def _parsed_schedule(self):
        """Schedule entries normalized to (date, home, away, raw), parsed once.

        The raw league.schedule mixes dict and tuple formats and is
        re-scanned by several views; parse it once per schedule object and
        reuse. Rebuilds automatically when the schedule list is replaced
        (new season / load game). The 4th element is the original dict
        entry (or None) so playoff/marquee/hype fields survive to the
        renderer.
        """
        src = self.app.league.schedule
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
        for game_date, home, away, _raw in self._parsed_schedule():
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
        if self.app.user_team not in (home, away):
            return ''
        row_tag = 'completed'
        if status == "Final" and "-" in score:
            try:
                a_s, h_s = (int(x) for x in score.split("-"))
                mine = h_s if home == self.app.user_team else a_s
                theirs = a_s if home == self.app.user_team else h_s
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
        # Fresh narrative read each render: grudges form mid-season, and
        # the matchup cache must not outlive the data it was built from.
        self.__dict__.pop("_narrative_cache", None)

        # Month filter options
        month_values = ['All'] + self._schedule_months()
        self.month_combo.configure(values=month_values)
        if self.month_filter.get() not in month_values:
            self.month_filter.set('All')
            self.month_combo.set('All')
        selected_month = self.month_filter.get()

        for game_date, home, away, raw in self._parsed_schedule():
            # Month filter
            try:
                if selected_month != 'All' and game_date.strftime("%b %Y") != selected_month:
                    continue
            except (AttributeError, ValueError):
                pass

            # Determine game status and score
            status = "Scheduled"
            score = "- : -"

            if game_date < self.app.current_date:
                # Playoff entries carry their own stamp
                # (played/home_score/away_score): the bracket sims them,
                # not the daily game loop, so they never land in
                # game_results. Prefer the stamp; fall back to the index.
                _stamped = self._playoff_entry_result(raw)
                if _stamped is not None:
                    score, status = _stamped
                    game_result = None
                else:
                    # O(1) result lookup via the app's matchup index (was a full
                    # scan of game_results per scheduled game: O(games x results))
                    game_result = self.app.find_game_result(game_date, home, away)
                if game_result is not None:
                    score = f"{game_result['away_score']}-{game_result['home_score']}"
                    status = "Final"
                elif status != "Final":
                    score = "0-0"  # Fallback if no result found
                    status = "Simulated"
            elif game_date == self.app.current_date:
                status = "Today"

            # Playoff/marquee presentation: the bracket publishes round_key,
            # series_id, marquee and hype_tags on each calendar entry.
            # Marquee series are the ones fans circle -- gold row + a star
            # and the top hype tag in the status column.
            raw = raw or {}
            is_playoff = bool(raw.get("round_key") or raw.get("series_id"))
            marquee = bool(raw.get("marquee"))
            hype_tags = list(raw.get("hype_tags") or [])
            if not is_playoff:
                # Regular-season grudge games: the schedule generator
                # doesn't stamp narrative metadata (and the template cache
                # would strip it), so enrich live from the four narrative
                # systems -- rivalry store, ledger grudge memory, iconic
                # history. Cached per matchup for the render pass.
                try:
                    _narr = self._matchup_narrative(home, away)
                except Exception:
                    _narr = None
                if _narr:
                    marquee = marquee or bool(_narr.get("marquee"))
                    if not hype_tags:
                        hype_tags = list(_narr.get("hype_tags") or [])

            # Color tag for games involving the user's team (win/loss/today)
            row_tag = self._game_row_tag(home, away, score, status)
            # NOTE: ttk Treeview tags with *conflicting* options (two tags
            # both setting foreground) do not compose under a custom
            # style -- resolve to a single foreground tag in Python.
            # Tags with distinct options (marquee fg + today_bg bg) do
            # combine, in any order.
            if marquee:
                # Marquee gold is the rarer, deliberate signal: it beats
                # win/loss/dimmed. Keep the "today" background highlight
                # via a background-only tag.
                tags = ["marquee"]
                if row_tag == "today":
                    tags.append("today_bg")
            elif row_tag:
                tags = [row_tag]
            else:
                tags = []
            display_status = status
            if is_playoff and display_status == "Scheduled":
                display_status = "Playoffs"
            if marquee:
                star = "\u2605" + (f" {hype_tags[0]}" if hype_tags else "")
                display_status = f"{display_status} {star}".strip()
            league_tags = tuple(tags)

            values = (game_date.strftime("%b %d, %Y"), away.team_name,
                      score, home.team_name, display_status)

            # Store game data for easy access (keyed the same way
            # get_selected_game_data() looks it up: display date string +
            # team names)
            game_key = f"{game_date.strftime('%b %d, %Y')}_{home.team_name}_{away.team_name}"
            self.schedule_data[game_key] = {
                'date': game_date,
                'home': home,
                'away': away,
                'score': score,
                'status': display_status,
                'marquee': marquee,
                'hype_tags': hype_tags,
                'round_key': raw.get("round_key"),
            }

            item_id = self.league_schedule_tree.insert('', 'end', values=values,
                                                       tags=league_tags)
            if self.app.user_team in (home, away):
                my_item_id = self.my_schedule_tree.insert('', 'end', values=values,
                                                           tags=tuple(tags))
                if self._first_upcoming is None and status in ("Today", "Scheduled"):
                    self._first_upcoming = my_item_id

        if self._first_upcoming:
            self.my_schedule_tree.see(self._first_upcoming)
            self.my_schedule_tree.selection_set(self._first_upcoming)
        try:
            team = self.app.user_team
            rec = f"{getattr(team, 'wins', 0)}-{getattr(team, 'losses', 0)}-{getattr(team, 'otl', getattr(team, 'ot_losses', 0))}"
            self.my_sched_header.configure(
                text=f"{team.team_name}  \u2022  {rec}  \u2022  Green = win, red = loss")
        except Exception:
            pass

        set_tree_empty_state(self.my_schedule_tree, "No games scheduled for your team")
        set_tree_empty_state(self.league_schedule_tree, "No league games scheduled")



class ScheduleWindow(InGamePopup):
    """Popup wrapper around ScheduleView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("League Schedule")
        self._view = ScheduleView(self, app=parent, *args, **kwargs)
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
class FinancesView(ctk.CTkFrame):
    """Comprehensive financial management window with detailed breakdown and projections.

    Rebuilt with CustomTkinter (Sept 2026): CTkToplevel shell, CTkTabview
    tabs, CTkFrame stat cards, dark styled Treeviews, CTkComboBox year
    selector, CTkSegmentedButton report picker, pill filter rows, and a
    CTkProgressBar cap-utilization meter. All calculation and reporting
    logic is unchanged from the ttk version.
    """

    def __init__(self, parent, app=None):
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
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the FinancesWindow wrapper
        self.configure(fg_color=BG)

        # Initialize data structures
        self.current_season = 2024
        self.selected_projection_year = tk.StringVar(master=self, value=str(self.current_season))

        # Create the interface
        self.create_interface()
        self._setup_tree_style()
        self.update_views()

        # Track window
        self.app.open_windows['finances'] = self

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

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
        self._heading(top, text=f"{self.app.user_team.team_name.upper()} FINANCIAL MANAGEMENT",
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
                         command=lambda c=col, t=tree: self.app._sort_treeview_generic(t, c))
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
        """Calculate the current cap charge (the number that matters).

        Uses the canonical cap_breakdown(): active-roster hits + buried
        one-way money in the minors + all dead cap (buyouts, seeded
        penalties, retained), minus any cap dollars temporarily shed by
        players sitting on the waiver wire. This is the same charge the
        Next Day compliance check and trade validation enforce, so the
        finance screens can never disagree with them.
        """
        try:
            from salary_cap_system import cap_breakdown
            return max(0, int(cap_breakdown(self.app.user_team)["total"]))
        except Exception:
            pass
        total = 0
        for player in self.app.user_team.roster:
            if hasattr(player, 'contract') and hasattr(player.contract, 'salary'):
                total += player.contract.salary
            elif hasattr(player, 'salary'):
                total += player.salary
        # Waiver shed: players on the wire temporarily don't count, so an
        # over-cap club sees its real cap space here (matches the Next Day
        # compliance check and trade validation).
        try:
            from salary_cap_system import waiver_shed_charge
            total -= waiver_shed_charge(self.app.user_team)
        except Exception:
            pass
        return max(0, total)

    def calculate_ahl_payroll(self):
        """Calculate the AHL payroll."""
        total = 0
        for player in getattr(self.app.user_team, 'ahl_roster', []):
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
        return getattr(self.app.user_team, 'salary_cap', 104_000_000)

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

        for player in self.app.user_team.roster:
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
        self.app.tree_maps[self.contracts_tree] = {}

        # Get all players based on roster filter
        roster_filter = self.roster_filter.get()
        players = []

        if roster_filter == 'All':
            players.extend(self.app.user_team.roster)
            players.extend(getattr(self.app.user_team, 'ahl_roster', []))
            players.extend(getattr(self.app.user_team, 'prospects', []))
        elif roster_filter == 'NHL':
            players = self.app.user_team.roster
        elif roster_filter == 'AHL':
            players = getattr(self.app.user_team, 'ahl_roster', [])
        elif roster_filter == 'Prospects':
            players = getattr(self.app.user_team, 'prospects', [])

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
            self.app.tree_maps[self.contracts_tree][item] = player

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

        for player in self.app.user_team.roster:
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
        for player in self.app.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            if years_left <= 1:
                expiring_next_year.append(player)

        if len(expiring_next_year) > 8:
            recommendations.append(f"You have {len(expiring_next_year)} players with expiring contracts. Start extension negotiations early to avoid losing key players.")

        # Age demographics
        old_expensive_players = []
        for player in self.app.user_team.roster:
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
{self.app.user_team.team_name} - {self.current_season} Season
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
        sorted_players = sorted(self.app.user_team.roster,
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
{self.app.user_team.team_name}
{'='*50}

CONTRACTS BY EXPIRY YEAR
------------------------
"""

        # Group by expiry year
        expiry_groups = {}
        for player in self.app.user_team.roster:
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
{self.app.user_team.team_name}
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

        for player in self.app.user_team.roster:
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
{self.app.user_team.team_name}
{'='*50}

AGE GROUP BREAKDOWN
-------------------
"""

        age_groups = {
            '18-22': [], '23-26': [], '27-30': [], '31-34': [], '35+': []
        }

        for player in self.app.user_team.roster:
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
{self.app.user_team.team_name}
{'='*50}

VALUE ANALYSIS
--------------
(Players ranked by value: OVR rating vs salary cost)
"""

        # Calculate value scores
        player_values = []
        for player in self.app.user_team.roster:
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
        player = self.app.tree_maps.get(self.contracts_tree, {}).get(item_id)
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
        if selection and selection[0] in self.app.tree_maps.get(self.contracts_tree, {}):
            player = self.app.tree_maps.get(self.contracts_tree, {})[selection[0]]
            self.app.open_player_profile(player)

    def negotiate_extension(self):
        """Open contract negotiation for selected player."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.app.tree_maps.get(self.contracts_tree, {}):
            player = self.app.tree_maps.get(self.contracts_tree, {})[selection[0]]
            # Contract talks are a full-screen jump now (session resumes).
            self.app.open_contract_negotiation_window(player, is_extension=True)

    def trade_player(self):
        """Open trade window for selected player."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.app.tree_maps.get(self.contracts_tree, {}):
            player = self.app.tree_maps.get(self.contracts_tree, {})[selection[0]]
            # Open trade window with this player pre-selected
            self.app.open_trade_window()

    # Action methods
    def open_contract_extensions(self):
        """Open contract extensions (full-screen jump)."""
        self.app.open_contract_extensions_window()

    def open_trade_evaluator(self):
        """Open trade evaluator tool (the Trade Center)."""
        self.app.open_trade_window()

    def show_salary_analytics(self):
        """Show advanced salary analytics."""
        self.app.show_screen('salary_analytics', 'Salary Analytics',
                             SalaryAnalyticsView)

    def open_buyout_calculator(self):
        """Open buyout calculator (full-screen jump)."""
        self.app.show_screen('buyout_calculator', 'Buyout Calculator',
                             BuyoutCalculatorView)

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
            filename = f"financial_report_{self.app.user_team.team_name.replace(' ', '_')}_{timestamp}.txt"
            filepath = os.path.join(exports_dir, filename)

            # Calculate financial data
            current_payroll = sum(getattr(p.contract, 'salary', getattr(p, 'salary', 750000))
                                for p in self.app.user_team.roster
                                if hasattr(p, 'contract') or hasattr(p, 'salary'))

            salary_cap = self._salary_cap()
            cap_space = salary_cap - current_payroll

            # Generate detailed report
            report_content = f"""
DETAILED FINANCIAL REPORT
{self.app.user_team.team_name} - {datetime.now().strftime('%Y-%m-%d')}
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
            sorted_players = sorted(self.app.user_team.roster,
                                  key=lambda p: getattr(p.contract, 'salary', getattr(p, 'salary', 750000)),
                                  reverse=True)

            for i, player in enumerate(sorted_players, 1):
                salary = getattr(player.contract, 'salary', getattr(player, 'salary', 750000))
                years_left = getattr(player.contract, 'years_remaining', 0) if hasattr(player, 'contract') else 0

                report_content += f"{i:2d}. {player.full_name:<25} {str(player.primary_position):<8} ${salary:>10,} ({years_left} yrs)\n"

            # Contract expiry analysis
            report_content += f"\n\nCONTRACT EXPIRY ANALYSIS\n{'-'*25}\n"

            expiring_this_year = [p for p in self.app.user_team.roster
                                if hasattr(p, 'contract') and getattr(p.contract, 'years_remaining', 0) <= 1]
            expiring_next_year = [p for p in self.app.user_team.roster
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
            for player in self.app.user_team.roster:
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





class FinancesWindow(InGamePopup):
    """Popup wrapper around FinancesView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title(f"{parent.user_team.team_name} - Financial Management")
        self._view = FinancesView(self, app=parent, *args, **kwargs)
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
class NewsView(ctk.CTkFrame):
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

    def __init__(self, parent, app=None):
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
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the NewsWindow wrapper
        self.configure(fg_color=BG)

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

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

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
        news_log = getattr(self.app, "news_log", None) or []
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




class NewsWindow(InGamePopup):
    """Popup wrapper around NewsView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("League News")
        self._view = NewsView(self, app=parent, *args, **kwargs)
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
class GMOptionsView(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the GMOptionsWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(bg_color=self.app.BG_COLOR)

        header = ttk.Frame(self, style='Panel.TFrame', padding=(20, 14))
        header.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(header, text="GM OPTIONS",
                  font=_sfont(self.app.FONT_FAMILY, 16, 'bold'),
                  style='Heading.TLabel').pack(side='left')

        # GM Management Options
        management_frame = ttk.LabelFrame(self, text="Team Management", padding=15)
        management_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(management_frame, text="Manage Trade Block", command=self.app.open_trade_block_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Handle Waivers", command=self.app.open_waivers_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Set Captains", command=self.app.open_set_captains_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Negotiate Extensions", command=self.negotiate_extensions, style='Accent.TButton').pack(pady=5, fill='x')

        # Game Settings & Preferences
        settings_frame = ttk.LabelFrame(self, text="Game Settings & Preferences", padding=15)
        settings_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(settings_frame, text="Settings & Preferences", command=self.app.open_settings_window).pack(pady=5, fill='x')

        # Close button
        ttk.Button(self, text="Close", command=self.close_view).pack(pady=20)

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def negotiate_extensions(self):
        self.app.open_contract_extensions_window()



class GMOptionsWindow(InGamePopup):
    """Popup wrapper around GMOptionsView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("General Manager Options")
        self._view = GMOptionsView(self, app=parent, *args, **kwargs)
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
class ContractNegotiationView(ctk.CTkFrame):
    """Contract talks as a full-screen view (FM/EHM style).

    Offer builder on the left, team/player context on the right: cap space,
    the agent's ask, comparable contracts, and this negotiation's offer
    history. Negotiation state lives in ``app.negotiation_sessions`` so the
    user can jump to another screen mid-talks and resume from the navbar.
    """

    def __init__(self, parent, player=None, is_extension=False, app=None,
                 is_elc=False):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the wrapper
        self.player = player
        self.is_extension = is_extension
        # ELC mode: negotiating a first contract with an unsigned
        # rights-held prospect. Term is locked to the signing-age table,
        # salary lives inside the ELC band, and signing/performance
        # bonuses are on the table instead of trade protection.
        self.is_elc = bool(is_elc)
        self._elc_counter = None  # agent's counter terms, when offered
        self.configure(fg_color=self.app.BG_COLOR)
        self._session = self._get_session()
        self._build()
        self._refresh_history()
        self._refresh_context()

    # ---------- session ----------

    def _get_session(self):
        sessions = getattr(self.app, "negotiation_sessions", None)
        if sessions is None:
            sessions = {}
            self.app.negotiation_sessions = sessions
        player = self.player
        key = getattr(player, "id", None) or id(player)
        sess = sessions.get(key)
        if sess is None or sess.get("player") is not player:
            sess = {
                "player": player,
                "is_extension": self.is_extension,
                "is_elc": self.is_elc,
                "offers": [],          # (salary, years, result)
                "asking_price": None,  # last known agent ask
                "draft_salary": "",
                "draft_years": 1,
                "draft_clause": "none",
                "draft_clause_size": 10,
                "draft_signing_bonus": "",
                "draft_perf_bonus": "",
            }
            sessions[key] = sess
        self._sess_key = key
        return sess

    def _close_session(self):
        sessions = getattr(self.app, "negotiation_sessions", None)
        if sessions is not None:
            sessions.pop(self._sess_key, None)
        try:
            self.app.refresh_screen_navbar()
        except Exception:
            pass

    # ---------- market data ----------

    @staticmethod
    def _estimate_market_value(player):
        """Standard market-value curve (matches ContractExtensionsView)."""
        try:
            ovr = player.overall_rating()
        except Exception:
            ovr = 75
        base_value = max(750000, (ovr - 60) * 250000)
        age_modifier = 1.0
        age = getattr(player, "age", 27)
        if 23 <= age <= 29:
            age_modifier = 1.2
        elif age >= 30:
            age_modifier = max(0.5, 1.0 - ((age - 30) * 0.05))
        pos = getattr(player, "primary_position", None)
        pos_name = getattr(pos, "value", str(pos))
        position_modifier = 1.0
        if pos_name == "C":
            position_modifier = 1.15
        elif pos_name in ("LD", "RD"):
            position_modifier = 1.1
        potential_modifier = 1.0
        if age <= 25:
            potential_modifier = {"A": 1.5, "B": 1.3, "C": 1.1,
                                  "D": 1.0, "F": 0.9}.get(
                                      getattr(player, "potential_grade", "C"), 1.0)
        try:
            performance_bonus = (player.stats.goals * 50000
                                 + player.stats.assists * 30000)
        except Exception:
            performance_bonus = 0
        return max(750000, int(base_value * age_modifier
                               * position_modifier * potential_modifier)
                   + performance_bonus)

    def _comparables(self, limit=5):
        player = self.player
        try:
            my_ovr = player.overall_rating()
        except Exception:
            my_ovr = 75
        my_pos = getattr(getattr(player, "primary_position", ""), "value", "")
        comps = []
        league = getattr(self.app, "league", None)
        for team in getattr(league, "teams", []) or []:
            for p in getattr(team, "roster", []) or []:
                if p is player:
                    continue
                try:
                    ovr = p.overall_rating()
                except Exception:
                    continue
                if abs(ovr - my_ovr) > 4:
                    continue
                ppos = getattr(getattr(p, "primary_position", ""), "value", "")
                if ppos != my_pos:
                    continue
                sal = getattr(getattr(p, "contract", None), "salary",
                              getattr(p, "salary", 0)) or 0
                yrs = getattr(getattr(p, "contract", None), "years_remaining",
                              getattr(p, "contract_years", 0)) or 0
                comps.append((abs(ovr - my_ovr), p.full_name, sal, yrs, ovr))
        comps.sort(key=lambda c: (c[0], -c[2]))
        return comps[:limit]

    # ---------- layout ----------

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _build(self):
        p = self.player
        app = self.app
        if self.is_elc:
            title_text = "Entry-Level Contract"
        else:
            title_text = "Contract Extension" if self.is_extension else "Contract Offer"
        # ELC band for the hint line (term locked to the signing-age table).
        self._elc_floor, self._elc_ceil, self._elc_years = None, None, None
        if self.is_elc:
            try:
                import salary_cap_system as _scs_b
                try:
                    from draft_generator import age_on_sept15 as _s15_b
                except Exception:
                    _s15_b = None
                _sy = getattr(getattr(app, "league", None), "season_year", None)
                _elc_age_b = getattr(p, "age", 20)
                if _s15_b is not None:
                    try:
                        _s15v = _s15_b(getattr(p, "birth_date", ""), _sy)
                        if _s15v is not None:
                            _elc_age_b = _s15v
                    except Exception:
                        pass
                self._elc_floor, self._elc_ceil, self._elc_years = \
                    _scs_b.elc_band(_elc_age_b, _sy)
            except Exception:
                pass

        # Header
        header = ttk.Frame(self, style="Panel.TFrame", padding=14)
        header.pack(fill=tk.X, padx=12, pady=(12, 6))
        try:
            pos = p.primary_position.value
        except Exception:
            pos = ""
        try:
            ovr = p.overall_rating()
        except Exception:
            ovr = "?"
        ttk.Label(header, text=f"{title_text}: {p.full_name}",
                  style="TLabel",
                  font=(app.FONT_FAMILY, 16, "bold")).pack(anchor="w")
        ttk.Label(header,
                  text=f"{pos}  •  Age {getattr(p, 'age', '?')}  •  "
                       f"OVR {ovr}  •  POT {getattr(p, 'potential_grade', '?')}",
                  style="Secondary.TLabel",
                  font=(app.FONT_FAMILY, 11)).pack(anchor="w", pady=(2, 0))
        if self.is_extension:
            try:
                cur_sal = p.contract.salary
                cur_yrs = p.contract.years_remaining
                ttk.Label(header,
                          text=f"Current deal: ${cur_sal:,} × {cur_yrs} yr(s) remaining",
                          style="Secondary.TLabel",
                          font=(app.FONT_FAMILY, 11)).pack(anchor="w")
            except Exception:
                pass
        if self.is_elc and int(getattr(self, "_elc_years", 0) or 0) <= 0:
            # 25+ prospects sit outside the Entry Level System -- the
            # dialog can't produce a legal offer (handle_elc_offer will
            # refuse on submit; the menu gates normally prevent this).
            ttk.Label(header,
                      text="Not ELC-eligible: 25+ is outside the Entry "
                           "Level System (CBA 9.1(b)).",
                      style="Secondary.TLabel",
                      font=(app.FONT_FAMILY, 11)).pack(anchor="w", pady=(2, 0))

        # Two columns in a scrollable area (fits full-screen and popup wrapper)
        scroll = ctk.CTkScrollableFrame(self, fg_color=self.app.BG_COLOR)
        scroll.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        cols = ttk.Frame(scroll, style="Panel.TFrame")
        cols.pack(fill=tk.BOTH, expand=True)
        cols.columnconfigure(0, weight=3)
        cols.columnconfigure(1, weight=2)

        left = ttk.Frame(cols, style="Card.TFrame", padding=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right = ttk.Frame(cols, style="Card.TFrame", padding=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ---- Left: offer builder ----
        ttk.Label(left, text="Your Offer", style="TLabel",
                  font=(app.FONT_FAMILY, 13, "bold")).pack(anchor="w", pady=(0, 8))

        salary_row = ttk.Frame(left, style="Card.TFrame")
        salary_row.pack(fill=tk.X, pady=4)
        ttk.Label(salary_row, text="Annual salary: $",
                  style="TLabel").pack(side=tk.LEFT)
        init_sal = self._session.get("draft_salary") or "750000"
        if self.is_elc and self._elc_floor is not None:
            # Never prefill below the displayed ELC floor -- the offer
            # would be dead on arrival.
            try:
                init_sal = str(max(
                    int(str(init_sal).replace(",", "").strip() or 0),
                    int(self._elc_floor)))
            except Exception:
                init_sal = str(self._elc_floor)
        self.salary_var = tk.StringVar(master=self, value=str(init_sal))
        ttk.Entry(salary_row, textvariable=self.salary_var,
                  width=16).pack(side=tk.LEFT, padx=(6, 0))
        if self.is_elc and self._elc_floor is not None:
            ttk.Label(salary_row,
                      text=f"  (ELC band ${self._elc_floor:,}-"
                           f"${self._elc_ceil:,}/yr)",
                      style="Secondary.TLabel").pack(side=tk.LEFT)

        years_row = ttk.Frame(left, style="Card.TFrame")
        years_row.pack(fill=tk.X, pady=4)
        if self.is_elc:
            # Term isn't negotiable on an ELC: the signing-age table sets
            # it (3/2/1). years_var is still kept for the shared paths.
            self.years_var = tk.IntVar(master=self,
                                       value=int(self._elc_years or 3))
            ttk.Label(years_row, text="Term:", style="TLabel").pack(side=tk.LEFT)
            ttk.Label(years_row,
                      text=f"{int(self._elc_years or 3)} year(s)  "
                           f"(ELC term set by signing age — not negotiable)",
                      style="TLabel").pack(side=tk.LEFT, padx=(8, 0))
        else:
            ttk.Label(years_row, text="Term:", style="TLabel").pack(side=tk.LEFT)
            max_years = 7 if self.is_extension else 6  # new CBA: 7 to re-sign, 6 external
            self.years_var = tk.IntVar(master=self,
                                       value=int(self._session.get("draft_years") or 1))
            ttk.Scale(years_row, from_=1, to=max_years, variable=self.years_var,
                      orient="horizontal", length=220).pack(side=tk.LEFT, padx=8)
            ttk.Label(years_row, textvariable=self.years_var,
                      style="TLabel", width=3).pack(side=tk.LEFT)
            ttk.Label(years_row, text=f"year(s)  (max {max_years})",
                      style="Secondary.TLabel").pack(side=tk.LEFT)

        # ---- ELC bonuses (instead of trade protection) ----
        if self.is_elc:
            try:
                import salary_cap_system as _scs_c
                _sb_cap_txt = "10% of base"
                _pb_cap = _scs_c.ELC_PERF_BONUS_MAX
            except Exception:
                _pb_cap = 1000000
            sb_row = ttk.Frame(left, style="Card.TFrame")
            sb_row.pack(fill=tk.X, pady=4)
            ttk.Label(sb_row, text="Signing bonus: $",
                      style="TLabel").pack(side=tk.LEFT)
            self.signing_var = tk.StringVar(
                master=self,
                value=str(self._session.get("draft_signing_bonus") or "0"))
            ttk.Entry(sb_row, textvariable=self.signing_var,
                      width=16).pack(side=tk.LEFT, padx=(6, 0))
            ttk.Label(sb_row, text=f"/yr  (max {_sb_cap_txt})",
                      style="Secondary.TLabel").pack(side=tk.LEFT)
            pb_row = ttk.Frame(left, style="Card.TFrame")
            pb_row.pack(fill=tk.X, pady=4)
            ttk.Label(pb_row, text="Performance bonus: $",
                      style="TLabel").pack(side=tk.LEFT)
            self.perf_var = tk.StringVar(
                master=self,
                value=str(self._session.get("draft_perf_bonus") or "0"))
            ttk.Entry(pb_row, textvariable=self.perf_var,
                      width=16).pack(side=tk.LEFT, padx=(6, 0))
            ttk.Label(pb_row, text=f"/yr  (max ${_pb_cap:,})",
                      style="Secondary.TLabel").pack(side=tk.LEFT)
            self.signing_var.trace_add("write", self._update_total)
            self.perf_var.trace_add("write", self._update_total)

        # ---- Trade protection (real clauses, real leverage) ----
        if not self.is_elc:
            import trade_engine as _te
            clause_row = ttk.Frame(left, style="Card.TFrame")
            clause_row.pack(fill=tk.X, pady=4)
            ttk.Label(clause_row, text="Trade protection:",
                      style="TLabel").pack(side=tk.LEFT)
            self._clause_names = {"none": "None",
                                  "nmc": "No-movement clause",
                                  "ntc": "Full no-trade",
                                  "mntc": "Modified no-trade"}
            self._clause_keys = {v: k for k, v in self._clause_names.items()}
            _cur = str(self._session.get("draft_clause") or "none")
            if _cur not in self._clause_names:
                _cur = "none"
            self.clause_var = tk.StringVar(master=self,
                                           value=self._clause_names[_cur])
            self.clause_menu = ttk.OptionMenu(
                clause_row, self.clause_var, self._clause_names[_cur],
                *self._clause_names.values(), command=self._on_clause_change)
            self.clause_menu.pack(side=tk.LEFT, padx=8)
            # Real NHL: trade protection requires UFA eligibility (27+ / 7 pro
            # seasons) -- kids can't be offered what the CBA won't allow.
            try:
                if not _te.clause_eligible(getattr(self, "player", None)):
                    self.clause_menu.configure(state="disabled")
                    self.clause_var.set(self._clause_names["none"])
                    self._session["draft_clause"] = "none"
            except Exception:
                pass
            self.clause_size_frame = ttk.Frame(clause_row, style="Card.TFrame")
            ttk.Label(self.clause_size_frame, text="blocked teams:",
                      style="Secondary.TLabel").pack(side=tk.LEFT)
            self.clause_size_var = tk.IntVar(
                master=self, value=int(self._session.get("draft_clause_size")
                                       or 10))
            ttk.Scale(self.clause_size_frame, from_=3, to=20,
                      variable=self.clause_size_var,
                      orient="horizontal", length=110).pack(side=tk.LEFT, padx=6)
            ttk.Label(self.clause_size_frame, textvariable=self.clause_size_var,
                      style="TLabel", width=3).pack(side=tk.LEFT)
            self.clause_size_var.trace_add("write", self._on_clause_size_change)
            self.clause_hint_var = tk.StringVar(master=self, value="")
            ttk.Label(left, textvariable=self.clause_hint_var,
                      style="Secondary.TLabel", wraplength=520).pack(anchor="w",
                                                                     pady=(0, 4))
            self._on_clause_change(self.clause_var.get())
            self._refresh_clause_hint()
        else:
            # ELC mode: no trade protection on an entry-level deal. Stubs
            # keep the shared paths (history, walk-away) from touching
            # missing attributes.
            self._clause_names = {"none": "None"}
            self._clause_keys = {"None": "none"}
            self.clause_var = tk.StringVar(master=self, value="None")
            self.clause_size_var = tk.IntVar(master=self, value=10)
            self.clause_hint_var = tk.StringVar(master=self, value="")

        self.total_label = ttk.Label(left, text="Total: $0", style="TLabel",
                                     font=(app.FONT_FAMILY, 12, "bold"))
        self.total_label.pack(anchor="w", pady=(8, 4))
        self.salary_var.trace_add("write", self._update_total)
        self.years_var.trace_add("write", self._update_total)
        self._update_total()

        # Result banner
        self.banner_var = tk.StringVar(master=self, value="")
        self.banner = ttk.Label(left, textvariable=self.banner_var,
                                style="Secondary.TLabel", wraplength=520)
        self.banner.pack(anchor="w", pady=(4, 8))
        if self.is_elc and self._elc_floor is not None:
            # The banner doubles as the ELC rule card: band, locked term,
            # and why there's no clause picker.
            self.banner_var.set(
                f"Entry-Level Contract: base must sit inside the band "
                f"(${self._elc_floor:,}-${self._elc_ceil:,}/yr); term is "
                f"fixed at {int(self._elc_years or 3)} year(s). No trade "
                f"protection on an ELC — signing and performance bonuses "
                f"are the sweetener.")

        btn_row = ttk.Frame(left, style="Card.TFrame")
        btn_row.pack(fill=tk.X, pady=(4, 2))
        ttk.Button(btn_row, text="Submit Offer",
                   command=self.submit_offer).pack(side=tk.LEFT, padx=(0, 8))
        # ELC mode: appears when the agent counters -- one click accepts
        # his number.
        self.counter_btn = ttk.Button(btn_row, text="",
                                      command=self._accept_elc_counter)
        if self.is_elc:
            self.counter_btn.pack(side=tk.LEFT, padx=(0, 8))
            self.counter_btn.pack_forget()
        ttk.Button(btn_row, text="Walk Away",
                   command=self.walk_away).pack(side=tk.LEFT)

        # Jump links
        jump_row = ttk.Frame(left, style="Card.TFrame")
        jump_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(jump_row, text="Jump to:", style="Secondary.TLabel").pack(
            side=tk.LEFT, padx=(0, 8))
        ttk.Button(jump_row, text="Roster",
                   command=lambda: self._jump("roster")).pack(side=tk.LEFT,
                                                              padx=4)
        ttk.Button(jump_row, text="Extensions",
                   command=lambda: self._jump("extensions")).pack(side=tk.LEFT,
                                                                   padx=4)
        ttk.Button(jump_row, text="Cap Analytics",
                   command=lambda: self._jump("cap")).pack(side=tk.LEFT, padx=4)
        ttk.Button(jump_row, text="Inbox",
                   command=lambda: self._jump("inbox")).pack(side=tk.LEFT,
                                                             padx=4)

        # ---- Right: context ----
        ttk.Label(right, text="Negotiation Context", style="TLabel",
                  font=(app.FONT_FAMILY, 13, "bold")).pack(anchor="w",
                                                           pady=(0, 8))
        self.context_box = tk.Text(right, height=14, wrap="word",
                                   bg=app.CONTENT_BG, fg=app.TEXT_COLOR,
                                   relief="flat", padx=8, pady=8,
                                   font=(app.FONT_FAMILY, 10))
        self.context_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.context_box.configure(state="disabled")

        ttk.Label(right, text="Offer History", style="TLabel",
                  font=(app.FONT_FAMILY, 12, "bold")).pack(anchor="w",
                                                           pady=(4, 4))
        self.history_box = tk.Text(right, height=8, wrap="word",
                                   bg=app.CONTENT_BG, fg=app.TEXT_COLOR,
                                   relief="flat", padx=8, pady=8,
                                   font=(app.FONT_FAMILY, 10))
        self.history_box.pack(fill=tk.BOTH, expand=True)
        self.history_box.configure(state="disabled")

    def _jump(self, where):
        try:
            if where == "roster":
                self.app.open_roster_window()
            elif where == "extensions":
                self.app.open_contract_extensions_window()
            elif where == "cap":
                # No open_salary_analytics_window exists anywhere; the
                # Finances screen (cap-utilization meter, payroll breakdown,
                # projections) is the honest existing cap surface. No new
                # cap logic -- salary-cap stays in its owner's lane.
                self.app.open_finances_window()
            elif where == "inbox":
                self.app.open_inbox_window()
        except Exception:
            pass

    # ---------- live updates ----------

    def _on_clause_change(self, _display=None):
        key = self._clause_keys.get(self.clause_var.get(), "none")
        self._session["draft_clause"] = key
        if key == "mntc":
            self.clause_size_frame.pack(side=tk.LEFT, padx=(4, 0))
        else:
            self.clause_size_frame.pack_forget()
        self._refresh_clause_hint()

    def _on_clause_size_change(self, *args):
        try:
            self._session["draft_clause_size"] = int(
                self.clause_size_var.get())
        except Exception:
            pass
        self._refresh_clause_hint()

    def _clause_key(self):
        return self._clause_keys.get(self.clause_var.get(), "none")

    def _refresh_clause_hint(self):
        import trade_engine as _te
        try:
            # Real NHL: no trade protection without UFA eligibility.
            if not _te.clause_eligible(self.player):
                self.clause_hint_var.set(
                    "Trade protection isn't available here -- the NHL only "
                    "allows it for players 27+ or with 7 pro seasons.")
                return
            key = self._clause_key()
            demand = _te.clause_demand_score(
                self.player, getattr(self.app, "user_team", None),
                getattr(self.app, "league", None))
            if key == "none":
                if demand >= 0.65:
                    self.clause_hint_var.set(
                        "His camp is pushing hard for trade protection -- "
                        "expect to pay more without it.")
                elif demand >= 0.35:
                    self.clause_hint_var.set(
                        "Trade protection would sweeten your offer.")
                else:
                    self.clause_hint_var.set("")
            else:
                val = _te.clause_annual_value(self.player, key)
                self.clause_hint_var.set(
                    f"Offering {_te.clause_offer_label(key, self.clause_size_var.get())} "
                    f"— worth about ${val:,}/yr to him.")
        except Exception:
            self.clause_hint_var.set("")

    def _update_total(self, *args):
        try:
            salary = int(str(self.salary_var.get()).replace(",", ""))
            years = int(self.years_var.get())
            if self.is_elc:
                # ELC total: base + signing bonus + performance bonus, per
                # year, times the locked term.
                def _n(v):
                    try:
                        return int(str(v.get()).replace(",", "") or 0)
                    except (ValueError, AttributeError):
                        return 0
                sb = _n(self.signing_var)
                pb = _n(self.perf_var)
                self.total_label.config(
                    text=f"Total: ${(salary + sb + pb) * years:,}  "
                         f"(${salary:,}/yr + ${sb:,} SB + ${pb:,} perf "
                         f"× {years} yr)")
                self._session["draft_salary"] = str(salary)
                self._session["draft_years"] = years
                self._session["draft_signing_bonus"] = str(sb)
                self._session["draft_perf_bonus"] = str(pb)
                return
            self.total_label.config(
                text=f"Total: ${salary * years:,}  "
                     f"(${salary:,}/yr × {years} yr)")
            self._session["draft_salary"] = str(salary)
            self._session["draft_years"] = years
        except (ValueError, AttributeError):
            self.total_label.config(text="Total: $0")

    def _refresh_context(self):
        app = self.app
        p = self.player
        if self.is_elc:
            self._refresh_elc_context()
            return
        lines = []
        # Cap
        try:
            live_cap = app.get_live_cap() if hasattr(app, "get_live_cap") else None
            payroll = getattr(app.user_team, "payroll", None)
            if live_cap and payroll is not None:
                lines.append(f"Salary cap: ${live_cap:,}")
                lines.append(f"Team payroll: ${payroll:,}")
                lines.append(f"Cap space: ${live_cap - payroll:,}")
                lines.append("")
        except Exception:
            pass
        # Agent's ask
        ask = self._session.get("asking_price")
        if ask:
            lines.append(f"Agent's ask: ${ask:,}/yr")
        else:
            mv = self._estimate_market_value(p)
            lines.append(f"Estimated market value: ${mv:,}/yr")
        lines.append("")
        # Comparables
        lines.append("Comparable contracts:")
        comps = self._comparables()
        if not comps:
            lines.append("  (no close comparables found)")
        for _, name, sal, yrs, ovr in comps:
            lines.append(f"  {name} ({ovr} OVR): ${sal:,}/yr × {yrs}")
        self.context_box.configure(state="normal")
        self.context_box.delete("1.0", "end")
        self.context_box.insert("end", "\n".join(lines))
        self.context_box.configure(state="disabled")

    def _refresh_elc_context(self):
        """Right-column context in ELC mode: the camp's ask, not comparables.

        An unsigned prospect has no NHL comparables worth showing -- what
        matters is pedigree (what his draft slot usually gets) and what
        his camp is asking for.
        """
        lines = []
        try:
            import salary_cap_system as _scs_e
            _sy = getattr(getattr(self.app, "league", None),
                          "season_year", None)
            ask = _scs_e.elc_prospect_ask(self.player, _sy)
            lines.append(
                f"Agent's ask: ${ask['salary']:,}/yr × {ask['years']} yr(s)")
            if ask["signing_bonus"]:
                lines.append(
                    f"  + ${ask['signing_bonus']:,}/yr signing bonus")
            if ask["performance_bonus"]:
                lines.append(
                    f"  + ${ask['performance_bonus']:,}/yr performance bonus")
            lines.append("")
            lines.append(ask["flavor"])
            lines.append("")
            lines.append(
                f"ELC band: ${ask['floor']:,}-${ask['ceiling']:,}/yr base. "
                f"Term is fixed at {ask['years']} year(s) by signing age — "
                f"the one thing you can't negotiate.")
        except Exception as e:
            lines.append(f"(ask unavailable: {e})")
        self.context_box.configure(state="normal")
        self.context_box.delete("1.0", "end")
        self.context_box.insert("end", "\n".join(lines))
        self.context_box.configure(state="disabled")

    def _refresh_history(self):
        offers = self._session.get("offers", [])
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        if not offers:
            self.history_box.insert("end", "No offers yet this session.")
        else:
            for i, (sal, yrs, result) in enumerate(offers, 1):
                self.history_box.insert(
                    "end", f"Round {i}: ${sal:,}/yr × {yrs} — {result}\n")
        self.history_box.configure(state="disabled")

    # ---------- actions ----------

    def _record_offer(self, salary, years, result):
        self._session["offers"].append((salary, years, result))
        self._refresh_history()

    def submit_offer(self):
        if self.app._mp_client_block("free-agent signings"):
            return
        if self.is_elc:
            self._submit_elc_offer()
            return
        p = self.player
        try:
            salary = int(str(self.salary_var.get()).replace(",", ""))
            years = int(self.years_var.get())
        except ValueError:
            self.banner_var.set("Please enter valid numbers for salary and years.")
            return
        if salary <= 0:
            self.banner_var.set("Salary must be greater than $0.")
            return
        max_years = 7 if self.is_extension else 6  # new CBA: 7 to re-sign, 6 external
        if years < 1 or years > max_years:
            self.banner_var.set(
                f"Contract length must be between 1 and {max_years} years.")
            return
        # Same signing path as the original popup: stage the offer on the
        # player object, then run the central handler (inbox routing).
        # Clause terms ride along as staged single-use attributes.
        p.salary = salary
        p.contract_years = years
        p.offered_clause_kind = self._clause_key()
        p.offered_clause_list_size = int(self.clause_size_var.get() or 10)
        import trade_engine as _te
        _clause_txt = _te.clause_offer_label(
            p.offered_clause_kind, p.offered_clause_list_size)
        accepted = self.app.handle_contract_offer(
            p, extension=self.is_extension, notify="inbox")
        if accepted:
            self._record_offer(salary, years, f"accepted ✓ ({_clause_txt})")
            self._close_session()
            self.close_view()
        else:
            self._record_offer(salary, years,
                               f"rejected — agent responded via inbox "
                               f"({_clause_txt})")
            self.banner_var.set(
                "Offer rejected. The agent's response is in your inbox — "
                "adjust the offer or jump back here from the navbar chip.")
            try:
                self.app.refresh_screen_navbar()
            except Exception:
                pass

    def _submit_elc_offer(self):
        """One ELC offer round: validate the band, run the prospect
        handshake, and either sign him, show the agent's counter, or
        report the rejection. The view stays open until it's signed or
        the user walks away."""
        p = self.player

        def _num(var):
            try:
                return int(str(var.get()).replace(",", "") or 0)
            except (ValueError, AttributeError):
                return None

        salary, sb, pb = (_num(self.salary_var), _num(self.signing_var),
                          _num(self.perf_var))
        if salary is None or sb is None or pb is None or salary <= 0:
            self.banner_var.set("Enter valid numbers for salary and bonuses.")
            return
        years = int(self.years_var.get() or 0)
        res = self.app.handle_elc_offer(p, salary, sb, pb)
        verdict = res.get("verdict")
        if verdict == "accepted":
            self._record_offer(salary, years,
                               f"accepted ✓ (${sb:,} SB, ${pb:,}/yr perf)")
            self._close_session()
            self.close_view()
        elif verdict == "counter":
            c = res.get("counter") or {}
            self._elc_counter = c
            self._record_offer(salary, years, "countered by agent")
            self.banner_var.set(
                f"Agent counters: ${c.get('salary', 0):,}/yr "
                f"× {c.get('years', years)} + ${c.get('signing_bonus', 0):,} "
                f"signing bonus + ${c.get('performance_bonus', 0):,}/yr "
                f"performance bonus. Accept below or adjust your offer.")
            try:
                self.counter_btn.config(
                    text=f"Accept ${c.get('salary', 0):,}/yr counter")
                self.counter_btn.pack(side=tk.LEFT, padx=(0, 8))
            except Exception:
                pass
        else:
            self._record_offer(
                salary, years, f"{verdict} -- {res.get('note', '')}")
            self.banner_var.set(res.get("note") or "Offer rejected.")
            self._elc_counter = None
            try:
                self.counter_btn.pack_forget()
            except Exception:
                pass

    def _accept_elc_counter(self):
        """One-click acceptance: fill the agent's number and submit."""
        c = self._elc_counter or {}
        if not c:
            return
        try:
            self.salary_var.set(str(c.get("salary", 0)))
            self.signing_var.set(str(c.get("signing_bonus", 0)))
            self.perf_var.set(str(c.get("performance_bonus", 0)))
        except Exception:
            pass
        self._submit_elc_offer()

    def walk_away(self):
        # Validate before recording: a non-numeric salary gets an honest
        # inline error, never a crash.
        try:
            salary = int(str(self.salary_var.get()).replace(",", "") or 0)
        except (ValueError, TypeError):
            self.banner_var.set(
                "Couldn't record the walk-away: the salary field isn't a "
                "number. Fix it or clear it first.")
            return
        try:
            years = int(self.years_var.get() or 0)
        except (ValueError, TypeError):
            self.banner_var.set(
                "Couldn't record the walk-away: the years field isn't a "
                "number. Fix it or clear it first.")
            return
        self._record_offer(salary, years, "walked away")
        self._close_session()
        self.close_view()


class ContractNegotiationWindow(InGamePopup):
    """Popup wrapper around ContractNegotiationView (backward compatibility).

    New code should embed ContractNegotiationView as a full-screen view via
    HockeyManagerGUI.show_screen() instead of opening this card.
    """

    def __init__(self, parent, player=None, is_extension=False):
        super().__init__(parent)
        self._view = ContractNegotiationView(self, app=parent, player=player,
                                             is_extension=is_extension)
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

class WaiversView(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the WaiversWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(bg_color=self.app.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create top panel with instructions
        instruction_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        instruction_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(instruction_frame, text="Waiver Wire Management", font=_sfont(self.app.FONT_FAMILY, 16, 'bold'), 
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
        
        self.eligible_tree = self.app._create_treeview(my_players_frame, columns, 20)
        self.eligible_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create a button frame for my players
        my_buttons_frame = ttk.Frame(my_players_frame, style='Panel.TFrame')
        my_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(my_buttons_frame, text="Place Selected on Waivers", 
                  command=self.place_on_waivers).pack(side='left', padx=5)
        
        # Waiver wire tab
        # NHL claim-priority strip: the order claims resolve in, lowest
        # points percentage first (last season's final table until Nov 1,
        # current standings after). A club that claims drops to the bottom.
        self._priority_frame = ttk.Frame(waiver_wire_frame, style='Panel.TFrame')
        self._priority_frame.pack(fill='x', padx=5, pady=(5, 0))
        self._priority_label = ttk.Label(
            self._priority_frame, text="", style='Muted.TLabel', wraplength=1000,
            font=_sfont(self.app.FONT_FAMILY, 9))
        self._priority_label.pack(anchor='w', padx=5, pady=4)
        wire_columns = {'name': ('Player', 200), 'age': ('Age', 40), 'pos': ('Pos', 50),
                       'ovr': ('OVR', 50), 'games': ('NHL Games', 80),
                       'salary': ('Salary', 100), 'team': ('Current Team', 150),
                       'days': ('Days Left', 70),
                       'actions': ('Actions', 150)}

        self.waiver_tree = self.app._create_treeview(waiver_wire_frame, wire_columns, 20)
        self.waiver_tree.pack(fill='both', expand=True, padx=5, pady=5)
        add_player_context_menu(self.waiver_tree, self)
        
        # Create a button frame for waiver wire
        wire_buttons_frame = ttk.Frame(waiver_wire_frame, style='Panel.TFrame')
        wire_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(wire_buttons_frame, text="Claim Selected Player", 
                  command=self.claim_from_waivers).pack(side='left', padx=5)
                  
        self.populate_eligible_players()
        self.populate_waiver_wire()
        
    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def is_waiver_eligible(self, player):
        """Determine if player is waiver-eligible based on age and NHL games played."""
        # Players over 25 or with more than 160 NHL games require waivers
        nhl_games = getattr(player, 'nhl_games_played', 0)
        return player.age >= 25 or nhl_games >= 160
        
    def populate_eligible_players(self):
        """Populate the tree with waiver-eligible players from user's team."""
        self.eligible_tree.delete(*self.eligible_tree.get_children())
        self.parent.tree_maps.setdefault(self.eligible_tree, {}).clear()

        # Get all NHL roster players who would be eligible for waivers
        eligible_players = [p for p in self.app.user_team.roster if self.is_waiver_eligible(p)]
        
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
            self.parent.tree_maps[self.eligible_tree][item] = player
            
        # Configure row click event
        self.eligible_tree.bind('<ButtonRelease-1>', self.on_eligible_click)

        set_tree_empty_state(self.eligible_tree, "No waiver-eligible players on your roster")
        
    def populate_waiver_wire(self):
        """Populate the tree with players currently on the waiver wire."""
        self.waiver_tree.delete(*self.waiver_tree.get_children())

        for player in self.app.waiver_list:
            _pending = bool(getattr(player, "user_claim_pending", False))
            player_values = (
                player.full_name,
                player.age,
                player.primary_position.name,
                player.overall_rating(),
                getattr(player, 'nhl_games_played', 0),
                f"${player.contract.salary:,}",
                player.team_name,
                max(0, int(getattr(player, 'waiver_days', 0) or 0)),
                "Claim Submitted" if _pending else "Claim"
            )
            item = self.waiver_tree.insert('', 'end', values=player_values)
            self.waiver_tree.item(item, tags=(str(player.id),))

        # Configure row click event
        self.waiver_tree.bind('<ButtonRelease-1>', self.on_waiver_click)

        set_tree_empty_state(self.waiver_tree, "The waiver wire is empty")
        self._refresh_priority_strip()

    def _refresh_priority_strip(self):
        """Show the NHL claim order and where the user's club sits in it."""
        try:
            import waiver_logic as _wl
            _lg = getattr(getattr(self.app, 'game_manager', None),
                          'league', None) or getattr(self.app, 'league', None)
            _order = _wl.waiver_priority_order(
                _lg, getattr(self.app, "current_date", None))
            _basis = _wl.waiver_priority_basis_label(
                _lg, getattr(self.app, "current_date", None))
            _mine = str(getattr(getattr(self.app, 'user_team', None),
                                'team_name', '') or '')
            _names = [str(getattr(t, 'team_name', '')) for t in _order]
            try:
                _my_rank = _names.index(_mine) + 1
            except ValueError:
                _my_rank = None
            _top = ", ".join(f"{i+1}. {n}" for i, n in enumerate(_names[:8]))
            if len(_names) > 8:
                _top += f", ... ({len(_names)} clubs)"
            _txt = (f"Claim priority ({_basis}): {_top}"
                    + (f" -- your club is #{_my_rank}." if _my_rank
                       else "."))
            self._priority_label.configure(text=_txt)
        except Exception:
            pass

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
            
            # If clicking on the Actions column (column #9)
            if column == '#9':
                self.claim_from_waivers(item)
    
    def place_on_waivers(self, item=None):
        """Place the selected player on waivers."""
        # Waiver window (the wire doesn't run in the June dead month).
        # One rulebook in transaction_windows.py.
        try:
            import transaction_windows as _tw
            _ok, _why = _tw.check_window(
                "waiver_place", getattr(self.app, "current_date", None))
            if not _ok:
                messagebox.showinfo("Waivers", _why)
                return
        except Exception:
            pass
        if not item:
            selected = self.eligible_tree.selection()
            if not selected:
                messagebox.showinfo("Selection Required", "Please select a player to place on waivers.")
                return
            item = selected[0]
            
        player_id = int(self.eligible_tree.item(item, "tags")[0])
        player = next((p for p in self.app.user_team.roster if p.id == player_id), None)
        
        if player:
            # Real NHL: a no-movement clause blocks waiver placement (and
            # the AHL assignment that follows) without the player's
            # consent. A no-trade clause alone does NOT block waivers.
            import trade_engine as _te
            _kind, _detail = _te.clause_of(player)
            if _kind == "NMC":
                _ask = messagebox.askyesno(
                    "No-movement clause",
                    f"{player.full_name} has a {_detail}.\n\n"
                    "He must approve being exposed on waivers. Ask him?")
                if not _ask:
                    return
                _lg = getattr(getattr(self.app, 'game_manager', None),
                              'league', None) or getattr(self.app, 'league', None)
                _ok, _why = _te.will_waive_ntc(
                    player, self.app.user_team, None, _lg, context="waivers")
                if not _ok:
                    messagebox.showwarning(
                        "Waiver refused",
                        f"{_why}\n\nHe's staying on the roster.")
                    return
                messagebox.showinfo("Waiver approved", _why)
            confirm = qol_confirm(self, "Confirm Waiver",
                                  f"Place {player.full_name} on waivers? "
                                  "Other teams will have a chance to claim them.",
                                  confirm_text="Place on Waivers")
            if confirm:
                # Add to waiver list
                player.on_waivers = True
                player.waiver_days = 2  # Players stay on waivers for 2 days
                self.app.waiver_list.append(player)
                
                # Add to news log
                self.app.add_news(f"{player.full_name} placed on waivers by {self.app.user_team.team_name}.")
                
                # Update the views
                self.populate_eligible_players()
                self.populate_waiver_wire()
                messagebox.showinfo("Player on Waivers",
                                   f"{player.full_name} has been placed on waivers. "
                                   "They will remain on waivers for 2 days, during which time other teams may claim them. "
                                   f"Their cap hit is temporarily shed until waivers clear -- "
                                   f"this can bring an over-cap roster back into compliance.")
    
    def claim_from_waivers(self, item=None):
        """Claim a player from the waiver wire."""
        # Waiver window (the wire doesn't run in the June dead month).
        # One rulebook in transaction_windows.py.
        try:
            import transaction_windows as _tw
            _ok, _why = _tw.check_window(
                "waiver_claim", getattr(self.app, "current_date", None))
            if not _ok:
                messagebox.showinfo("Waivers", _why)
                return
        except Exception:
            pass
        if not item:
            selected = self.waiver_tree.selection()
            if not selected:
                messagebox.showinfo("Selection Required", "Please select a player to claim from waivers.")
                return
            item = selected[0]
            
        player_id = int(self.waiver_tree.item(item, "tags")[0])
        player = next((p for p in self.app.waiver_list if p.id == player_id), None)
        
        if player:
            # Check if user's team has roster space
            if len(self.app.user_team.roster) >= 23:
                messagebox.showerror("Roster Full", 
                                    "Your NHL roster is full. Please release or reassign a player before claiming from waivers.")
                return
                
            # Check salary cap compliance
            if player.contract.salary > self.app.user_team.cap_space:
                messagebox.showerror("Cap Space Issue", 
                                    f"You don't have enough cap space to add this player's ${player.contract.salary:,} salary.")
                return
                
            if getattr(player, "user_claim_pending", False):
                messagebox.showinfo("Claim Pending",
                                    f"You already have a pending claim on {player.full_name}. "
                                    "It will be processed at noon in waiver priority order.")
                return
            # Your waiver priority right now (the wire tab shows the full order).
            _rank = None
            try:
                import waiver_logic as _wl
                _lg = getattr(getattr(self.app, 'game_manager', None),
                              'league', None) or getattr(self.app, 'league', None)
                _rank = _wl.waiver_priority_rank(
                    _lg, self.app.user_team,
                    getattr(self.app, "current_date", None))
            except Exception:
                pass
            _rank_txt = f" (your waiver priority: #{_rank})" if _rank else ""
            confirm = qol_confirm(self, "Submit Claim",
                                  f"Submit a waiver claim for {player.full_name}? "
                                  f"Claims are processed at noon in waiver priority order{_rank_txt} -- "
                                  "a higher-priority club that also claims him gets him first.",
                                  confirm_text="Submit Claim")
            if confirm:
                # MP client: the claim queues on the host and is processed
                # at noon in priority order -- never set the local flag,
                # which the next STATE_SYNC would wipe.
                def _claim_sent():
                    messagebox.showinfo(
                        "Claim Submitted",
                        f"Waiver claim submitted for {player.full_name}. "
                        f"It will be processed at the next waiver run in "
                        f"priority order{_rank_txt}.")
                if _mp_route(self.app, "claim_waivers",
                             {"player_id": str(getattr(player, "id", ""))},
                             on_sent=_claim_sent):
                    return
                # Real NHL: the claim is queued and processed at noon in
                # priority order (main.process_waivers), not granted
                # instantly. The flag is spent when the claim resolves.
                player.user_claim_pending = True

                # Add to news log
                self.app.add_news(f"{self.app.user_team.team_name} submitted a waiver claim for {player.full_name}.")

                # Update views
                self.populate_waiver_wire()
                messagebox.showinfo("Claim Submitted",
                                   f"Waiver claim submitted for {player.full_name}. "
                                   f"It will be processed at the next waiver run in priority order{_rank_txt}.")



class WaiversWindow(InGamePopup):
    """Popup wrapper around WaiversView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Waivers")
        self._view = WaiversView(self, app=parent, *args, **kwargs)
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
class ContractExtensionsView(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ContractExtensionsWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(fg_color=parent.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create top panel with instructions
        instruction_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        instruction_frame.pack(fill='x', padx=5, pady=5)
        
        
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
        ttk.Button(footer_frame, text="Close", command=self.close_view).pack(side='right', padx=5)
        
        self.populate_tables()
        
    def populate_tables(self):
        """Populate the contract tables with data."""
        self.expiring_tree.delete(*self.expiring_tree.get_children())
        self.all_contracts_tree.delete(*self.all_contracts_tree.get_children())
        
        team = self.app.user_team
        
        # Tree data maps to retrieve player objects
        self.app.tree_maps[self.expiring_tree] = {}
        self.app.tree_maps[self.all_contracts_tree] = {}
        
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
            self.app.tree_maps[self.all_contracts_tree][item_id] = player
            
            # Add to Expiring Contracts tab if contract expires this season
            if player.contract.years_remaining <= 1:
                item_id = self.expiring_tree.insert('', 'end', values=values, tags=('expiring',))
                self.app.tree_maps[self.expiring_tree][item_id] = player
                
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
        player = self.app.tree_maps.get(tree, {}).get(item_id)
        if not player:
            return
            
        menu = tk.Menu(self, tearoff=0, bg="#3C3C3C", fg="white")
        menu.add_command(label="Negotiate Extension", 
                        command=lambda: self.open_negotiation_window(player))
        menu.add_command(label="View Player Profile", 
                        command=lambda: self.app.open_player_profile(player))
        menu.tk_popup(event.x_root, event.y_root)
    
    def negotiate_from_event(self, event, tree):
        """Handle double-click on tree item."""
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
            
        player = self.app.tree_maps.get(tree, {}).get(item_id)
        if player:
            self.open_negotiation_window(player)
    
    def open_negotiation_window(self, player):
        """Jump to the extension-negotiation screen for a specific player."""
        if player.contract.years_remaining > 1:
            self._say(f"{player.full_name} has {player.contract.years_remaining} years "
                      f"left on their contract. Per NHL rules, extensions can only be "
                      f"negotiated in the final year.")
            return

        # Calculate recommended contract offer
        market_value = self.calculate_market_value(player)
        max_years = 7  # new CBA max extension is 7 years for own players

        # Full-screen jump; the extensions list is resumable from the navbar.
        self.app.show_screen("extension_negotiation",
                             f"Extension: {player.full_name}",
                             ExtensionNegotiationView, player, market_value,
                             max_years)

    def _say(self, text):
        if not hasattr(self, "_status_var"):
            self._status_var = tk.StringVar(master=self, value="")
            ttk.Label(self, textvariable=self._status_var,
                      style="Secondary.TLabel",
                      wraplength=720).pack(anchor="w", padx=10, pady=(0, 6))
        self._status_var.set(text)

    def negotiate_selected(self):
        """Negotiate with the selected player."""
        selection = self.expiring_tree.selection()
        if not selection:
            self._say("Please select a player to negotiate with.")
            return

        item_id = selection[0]
        player = self.app.tree_maps.get(self.expiring_tree, {}).get(item_id)
        if player:
            self.open_negotiation_window(player)
        else:
            # Honest map-miss: the selection couldn't be resolved.
            self._say("Couldn't match that row to a player. "
                      "Re-select and try again.")
    
    def auto_negotiate_all(self):
        """Auto-negotiate with all expiring contracts."""
        team = self.app.user_team
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
                # New SPC: the old deal's retention state dies with it (the
                # retaining club's ledger entry survives independently).
                try:
                    from trade_engine import clear_retention_state as _clr1
                    _clr1(player)
                except Exception:
                    pass
                result_messages.append(f"{player.full_name}: Accepted {years} years at ${salary_offer:,}")
            else:
                result_messages.append(f"{player.full_name}: Rejected {years} years at ${salary_offer:,}")
        
        # Show results
        result_window = InGamePopup(self)
        result_window.title("Auto-Negotiation Results")
        result_window.geometry("500x400")
        result_window.configure(background=self.app.BG_COLOR)
        
        ttk.Label(result_window, text="Contract Extension Results", 
                font=(self.app.FONT_FAMILY, 14, 'bold')).pack(pady=10)
        
        result_text = tk.Text(result_window, width=60, height=20, bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR)
        result_text.pack(pady=10, padx=10, fill='both', expand=True)
        
        for msg in result_messages:
            result_text.insert('end', msg + '\n')
        
        ttk.Button(result_window, text="Close", command=result_window.destroy).pack(pady=10)
        
        # Refresh data
        self.populate_tables()
    
    def simulate_negotiation(self, player, salary_offer, years):
        """Simulate contract negotiation: the PLAYER weighs the offer.

        The player-decision model (player_decision.py) replaces the old
        money-only math: ambition (cup/money/ice/stability/home), loyalty,
        role, hometown, people in the room, and bad blood all move the
        needle. The GM-stature hooks below are unchanged.
        """
        _uteam = (getattr(getattr(self, 'app', None), 'game_manager', None)
                  is not None and
                  getattr(self.app.game_manager, 'user_team', None)) or \
            getattr(getattr(self, 'app', None), 'user_team', None)
        try:
            import player_decision as _pd
            import reputation_system as _rs
            _premium = _rs.gm_ask_premium(_uteam) if _uteam is not None else 1.0
            _appeal, _reasons = _pd.contract_appeal(
                player, _uteam, salary_offer, years,
                current_team=_uteam,  # re-signing: he is staying home
                league=getattr(getattr(self, 'app', None), 'league', None),
                app=getattr(self, 'app', None),
                market_mult=_premium)
            acceptance_chance = 0.05 + 0.90 * _appeal
        except Exception:
            # Legacy money/term fallback if the model is unavailable.
            min_salary = max(750000, (player.overall_rating() - 60) * 187500)
            try:
                if _uteam is not None:
                    import reputation_system as _rs
                    min_salary *= _rs.gm_ask_premium(_uteam)
            except Exception:
                pass
            if player.age >= 30:
                min_salary *= max(0.5, 1.0 - ((player.age - 30) * 0.05))
            acceptance_chance = 0.5
            if salary_offer >= min_salary * 1.2:
                acceptance_chance += 0.4
            elif salary_offer >= min_salary * 1.1:
                acceptance_chance += 0.25
            elif salary_offer >= min_salary:
                acceptance_chance += 0.1
            else:
                acceptance_chance -= 0.3
            ideal_years = 8 if player.age <= 25 else 5 if player.age <= 30 else 2
            years_diff = abs(years - ideal_years)
            if years_diff == 0:
                acceptance_chance += 0.2
            elif years_diff <= 1:
                acceptance_chance += 0.1
            elif years_diff >= 3:
                acceptance_chance -= 0.2
            if hasattr(player, 'teamwork') and player.teamwork > 15:
                acceptance_chance += 0.1

        # GM stature: stars can afford to be picky about who they play
        # for -- a respected GM gets a small bump, a clown GM gets the
        # cold shoulder. Depth players just want a contract. Additive.
        try:
            if _uteam is not None:
                import reputation_system as _rs
                acceptance_chance += _rs.gm_fa_accept_delta(_uteam, player)
        except Exception:
            pass

        # Final result
        return random.random() < max(0.05, min(0.95, acceptance_chance))

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

class ContractExtensionsWindow(InGamePopup):
    """Popup wrapper around ContractExtensionsView (backward compatibility).

    New code should embed ContractExtensionsView as a full-screen view via
    HockeyManagerGUI.show_screen() instead of opening this card.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._view = ContractExtensionsView(self, app=parent)
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

class ExtensionNegotiationView(ctk.CTkFrame):
    def __init__(self, parent, player, market_value, max_years, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ExtensionNegotiationWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.player = player
        self.market_value = market_value
        self.max_years = max_years
        # Gating Phase 1: negotiation state lives in app.negotiation_sessions
        # (same pattern as ContractNegotiationView) so the user can jump to
        # another screen mid-talks and resume from the navbar.
        self._session = self._get_session()

        self.configure(fg_color=parent.BG_COLOR)
        
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
        self.ntc_var.trace_add('write', self.update_total)

        # Restore any in-progress offer parked in the session, then update.
        self._restore_draft()
        self.update_total()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', padx=5, pady=10)
        
        ttk.Button(button_frame, text="Submit Offer", command=self.submit_offer).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.close_view).pack(side='right', padx=5)

        # In-view message banner + counter-offer host (no popups)
        self._banner_frame = ttk.Frame(main_frame)
        self._banner_frame.pack(fill='x', padx=5, pady=(0, 4))
        self._counter_host = ttk.Frame(main_frame)
        self._counter_host.pack(fill='x', padx=5, pady=4)
    
    # ---------- session ----------

    def _get_session(self):
        sessions = getattr(self.app, "negotiation_sessions", None)
        if sessions is None:
            sessions = {}
            self.app.negotiation_sessions = sessions
        player = self.player
        key = getattr(player, "id", None) or id(player)
        sess = sessions.get(key)
        if sess is None or sess.get("player") is not player:
            sess = {
                "player": player,
                "is_extension": True,
                "draft_salary": "",
                "draft_years": 0,
                "draft_ntc": False,
                "draft_signing_bonus": "",
            }
            sessions[key] = sess
        self._sess_key = key
        try:
            self.app.refresh_screen_navbar()
        except Exception:
            pass
        return sess

    def _close_session(self):
        sessions = getattr(self.app, "negotiation_sessions", None)
        if sessions is not None:
            sessions.pop(getattr(self, "_sess_key", None), None)
        try:
            self.app.refresh_screen_navbar()
        except Exception:
            pass

    def _restore_draft(self):
        """Seed the offer widgets from the session's in-progress draft.

        The widget traces fire update_total (which writes through to the
        session), so the draft is snapshotted first and the write-through
        is suspended during the restore -- otherwise restoring salary
        first would clobber the parked years/ntc/bonus with the widgets'
        still-initial values.
        """
        sess = dict(self._session or {})
        self._restoring = True
        try:
            try:
                sal = sess.get("draft_salary") or f"{self.market_value:,}"
                self.salary_var.set(str(sal))
            except Exception:
                pass
            try:
                yrs = int(sess.get("draft_years") or min(5, self.max_years))
                self.years_var.set(max(1, min(yrs, self.max_years)))
            except Exception:
                pass
            try:
                ntc = sess.get("draft_ntc", None)
                if ntc is None:
                    # Cross-view compat: ContractNegotiationView stores clauses
                    # as draft_clause ("none"/"full"/...).
                    ntc = str(sess.get("draft_clause") or "none") != "none"
                self.ntc_var.set(bool(ntc))
            except Exception:
                pass
            try:
                self.bonus_var.set(str(sess.get("draft_signing_bonus") or "0"))
            except Exception:
                pass
        finally:
            self._restoring = False

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
            # Write-through: the in-progress offer survives navigation.
            # Suspended while _restore_draft seeds the widgets (the traces
            # fire on each .set(), and must not clobber the parked draft).
            if getattr(self, "_restoring", False):
                return
            try:
                sess = self._session
                sess["draft_salary"] = str(salary)
                sess["draft_years"] = years
                sess["draft_signing_bonus"] = str(bonus)
                ntc = bool(self.ntc_var.get())
                sess["draft_ntc"] = ntc
                # Cross-view compat with ContractNegotiationView.
                sess["draft_clause"] = "full" if ntc else "none"
            except Exception:
                pass
        except ValueError:
            self.total_value_var.set("Invalid input")
    
    def submit_offer(self):
        """Submit contract offer to the player."""
        if self.app._mp_client_block("contract extensions"):
            return
        try:
            # Parse salary with commas
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = self.years_var.get()

            # Parse bonus
            bonus_str = self.bonus_var.get().replace(',', '')
            bonus = int(bonus_str) if bonus_str else 0

            # Validate inputs (in-view banner, not a popup)
            if salary < 750000:
                self._say("Salary must be at least $750,000 (NHL minimum).")
                return

            if years < 1 or years > self.max_years:
                self._say(f"Contract length must be between 1 and {self.max_years} years.")
                return

            if bonus < 0:
                self._say("Signing bonus cannot be negative.")
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
                # New SPC: the old deal's retention state dies with it (the
                # retaining club's ledger entry survives independently).
                try:
                    from trade_engine import clear_retention_state as _clr2
                    _clr2(self.player)
                except Exception:
                    pass
                self.player.contract.no_trade_clause = self.ntc_var.get()

                _why = ""
                try:
                    _rs0 = getattr(self, "_last_appeal_reasons", []) or []
                    if _rs0:
                        _why = f" ({_rs0[0][0].upper()}{_rs0[0][1:]}.)"
                except Exception:
                    pass
                self._say(f"{self.player.full_name} has accepted: {years} years "
                          f"at ${salary:,}/year "
                          f"({'with' if self.ntc_var.get() else 'without'} NTC, "
                          f"bonus ${bonus:,}).{_why}")
                self._hide_counter()
                self._close_session()
                self.after(1200, self.close_view)
            else:
                counter_years = min(years + random.randint(-1, 1), self.max_years)
                counter_salary = int(salary * random.uniform(1.05, 1.2))
                self._show_counter(counter_years, counter_salary, bonus)

        except ValueError:
            self._say("Please enter valid numbers for salary, years, and bonus.")

    def _say(self, text):
        """Show a status message in the view's banner (no popup)."""
        if not hasattr(self, "_banner_var"):
            self._banner_var = tk.StringVar(master=self, value="")
            banner = ttk.Label(self._banner_frame, textvariable=self._banner_var,
                               style="Secondary.TLabel", wraplength=640)
            banner.pack(anchor="w", padx=10, pady=(0, 6))
        self._banner_var.set(text)

    def _show_counter(self, counter_years, counter_salary, bonus):
        """In-view counter-offer panel (replaces the askyesno popup)."""
        self._hide_counter()
        panel = ttk.LabelFrame(self._counter_host, text="Agent's Counter-Offer",
                               padding=10)
        panel.pack(fill=tk.X, padx=5, pady=8)
        ttk.Label(panel,
                  text=f"{self.player.full_name}'s camp rejected your offer.\n"
                       f"Counter: {counter_years} years at ${counter_salary:,}/year",
                  style="TLabel", wraplength=600).pack(anchor="w", pady=(0, 8))
        btns = ttk.Frame(panel)
        btns.pack(anchor="w")
        ttk.Button(btns, text="Accept Counter",
                   command=lambda: self._accept_counter(counter_years,
                                                        counter_salary,
                                                        bonus)).pack(side=tk.LEFT,
                                                                     padx=(0, 8))
        ttk.Button(btns, text="Adjust My Offer",
                   command=self._hide_counter).pack(side=tk.LEFT)
        self._counter_panel = panel
        self._say("Offer rejected — the agent countered. Accept it or adjust your offer above.")

    def _hide_counter(self):
        panel = getattr(self, "_counter_panel", None)
        if panel is not None:
            try:
                panel.destroy()
            except Exception:
                pass
        self._counter_panel = None

    def _accept_counter(self, counter_years, counter_salary, bonus):
        if self.app._mp_client_block("contract extensions"):
            return
        self.player.contract.salary = counter_salary
        self.player.contract.years_remaining = counter_years
        self.player.contract.signing_bonus = bonus
        self.player.contract.no_trade_clause = self.ntc_var.get()
        self._say(f"Counter accepted: {self.player.full_name}, "
                  f"{counter_years} years at ${counter_salary:,}/year.")
        self._hide_counter()
        self.after(1200, self.close_view)
    
    def calculate_acceptance_chance(self, salary, years, bonus):
        """Likelihood the player accepts: the player-decision model
        (ambition, loyalty, role, hometown, people, bad blood) sets the
        base chance; bonus money and trade protection add on top, as before.
        """
        _app = getattr(self, 'app', None)
        _uteam = (getattr(getattr(_app, 'game_manager', None), 'user_team', None)
                  or getattr(_app, 'user_team', None))
        _league = getattr(_app, 'league', None)
        try:
            import player_decision as _pd
            import reputation_system as _rs
            _premium = _rs.gm_ask_premium(_uteam) if _uteam is not None else 1.0
            # extension (he is ours) vs open-market signing (he is leaving
            # his last club): the stay-vs-go math differs completely.
            _pteam = getattr(self.player, 'team_name', '') or ''
            _uname = getattr(_uteam, 'team_name', '') or ''
            if _uteam is not None and _pteam == _uname:
                _current = _uteam
            else:
                _current = _pd.previous_team(self.player, _league)
            _appeal, _reasons = _pd.contract_appeal(
                self.player, _uteam, salary, years,
                current_team=_current, league=_league, app=_app,
                market_mult=_premium)
            try:
                self._last_appeal_reasons = list(_reasons or [])
            except Exception:
                pass
            chance = 0.05 + 0.90 * _appeal
        except Exception:
            # Legacy money/term fallback.
            chance = 0.5
            salary_ratio = salary / max(1, getattr(self, 'market_value', salary) or 1)
            if salary_ratio >= 1.1:
                chance += 0.3
            elif salary_ratio >= 1.0:
                chance += 0.15
            elif salary_ratio >= 0.9:
                chance += 0.05
            else:
                chance -= 0.3
            ideal_years = 8 if self.player.age <= 25 else 5 if self.player.age <= 30 else 2
            years_diff = abs(years - ideal_years)
            if years_diff == 0:
                chance += 0.15
            elif years_diff <= 1:
                chance += 0.05
            elif years_diff >= 4:
                chance -= 0.15

        # Bonus adds slight bonus to acceptance
        if bonus > 0:
            chance += min(0.1, bonus / max(1, salary * years) * 0.5)

        # Trade protection: one shared valuation (trade_engine), scaled by
        # how hard this player actually pushes for a clause -- not a flat
        # veteran bonus.
        if self.ntc_var.get():
            import trade_engine as _te
            chance += _te.clause_acceptance_bonus(self.player, "ntc")

        # Cap the chance between 5% and 95%
        return max(0.05, min(0.95, chance))

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

class ExtensionNegotiationWindow(InGamePopup):
    """Popup wrapper around ExtensionNegotiationView (backward compatibility).

    New code should embed ExtensionNegotiationView as a full-screen view via
    HockeyManagerGUI.show_screen() instead of opening this card.
    """

    def __init__(self, parent, player, market_value, max_years):
        super().__init__(parent)
        self._view = ExtensionNegotiationView(self, app=parent, player=player,
                                              market_value=market_value,
                                              max_years=max_years)
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

class StaffContractView(ctk.CTkFrame):
    """Full-screen staff contract negotiation.

    Jumped to via HockeyManagerGUI.show_screen() (was: a 480x420
    InGamePopup from FreeAgencyView._open_staff_contract_dialog). The
    negotiation is roll-first through game_manager.sign_free_agent_staff().

    Sept 2026: the salary offer is a free dollar entry (tailored offers,
    not 80/100/120% steps). The club's league-wide staff budget is shown
    and enforced -- offers cannot exceed the remaining budget. hire_source
    tracks where the staffer came from ("free_agent" | "overseas" |
    "ahl_poach") so a successful hire leaves the right pool/club.
    """

    def __init__(self, parent, staff=None, app=None, hire_source="free_agent",
                 from_team=None):
        super().__init__(parent, fg_color="transparent")
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        init_ctk_theme()
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN, RED=RED,
                        BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        self.app = app
        self.staff = staff
        self.hire_source = hire_source or "free_agent"
        self.from_team = from_team
        self._close_screen = None  # set by show_screen()
        self._build()

    def close_view(self):
        """Close this screen (dashboard in screen mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _parse_offer(self):
        """Parse the dollar entry into an int, or None when invalid."""
        try:
            raw = self._salary_entry.get().strip()
            raw = raw.replace("$", "").replace(",", "").replace(" ", "")
            value = int(float(raw))
            return value if value > 0 else None
        except Exception:
            return None

    def _build(self):
        from game_classes import staff_market_ask
        ct = self._ct
        staff = self.staff
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        card = ctk.CTkFrame(scroll, fg_color=ct['PANEL'], corner_radius=12,
                            width=560)
        card.pack(pady=18)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        if staff is None:
            self._body(body, text="No staff member selected.",
                       dim=True).pack(anchor="w", pady=12)
            self._secondary_button(body, text="Back",
                                   command=self.close_view).pack(anchor="w",
                                                                pady=(8, 0))
            return

        self._heading(body, text=f"{staff.full_name}",
                      size=16).pack(anchor="w")
        try:
            _role = staff.role.value
        except Exception:
            _role = getattr(staff, "role", "")
        self._body(body,
                   text=f"{_role} \u2022 {getattr(staff, 'nationality', '')} "
                        f"\u2022 Age {getattr(staff, 'age', '?')}",
                   dim=True, size=11).pack(anchor="w", pady=(2, 6))

        # Where he comes from (poach context).
        _src_line = ""
        if self.hire_source == "overseas":
            _src_line = (f"Currently coaching: "
                         f"{getattr(staff, 'current_club', '') or 'overseas'}")
        elif self.hire_source == "ahl_poach" and self.from_team is not None:
            _src_line = (f"Under contract: "
                         f"{getattr(self.from_team, 'team_name', '')} (AHL)")
        if _src_line:
            self._body(body, text=_src_line, dim=True,
                       size=11).pack(anchor="w", pady=(0, 4))

        ask = staff_market_ask(staff)

        # Asking terms banner
        asking = ctk.CTkFrame(body, fg_color=ct['CARD'], corner_radius=8)
        asking.pack(fill="x", pady=(0, 12))
        self._body(asking,
                   text=f"Asking: ${ask:,} / year",
                   size=12).pack(anchor="w", padx=12, pady=10)

        # Club staff budget banner (league-wide rule, market-tiered).
        try:
            _team = self.app.game_manager.user_team
            _budget = int(getattr(_team, 'staff_budget', 0) or 0)
            _committed = _team.staff_payroll() if hasattr(_team, 'staff_payroll') else 0
            _remaining = _budget - _committed
        except Exception:
            _budget = _committed = _remaining = 0
        budget_card = ctk.CTkFrame(body, fg_color=ct['CARD'], corner_radius=8)
        budget_card.pack(fill="x", pady=(0, 12))
        self._body(budget_card,
                   text=f"Club staff budget: ${_budget:,}  \u2022  "
                        f"Committed: ${_committed:,}  \u2022  "
                        f"Available: ${_remaining:,}",
                   size=11, dim=True).pack(anchor="w", padx=12, pady=10)
        self._budget_remaining = _remaining

        offer_info = {'years': 2}

        self._body(body, text="Contract length:", dim=True,
                   size=11).pack(anchor="w", pady=(0, 4))
        years_seg = ctk.CTkSegmentedButton(
            body, values=["1", "2", "3", "4", "5"],
            selected_color=ct['TEAL'], selected_hover_color=ct['TEAL_HOVER'],
            unselected_color=ct['CARD'], unselected_hover_color=ct['BORDER'],
            command=lambda _v: _paint())
        years_seg.set("2")
        years_seg.pack(anchor="w", pady=(0, 10))

        # Free dollar entry -- tailored offers, not fixed steps.
        self._body(body, text="Salary offer ($ / year):", dim=True,
                   size=11).pack(anchor="w", pady=(0, 4))
        self._salary_entry = ctk.CTkEntry(
            body, width=220, fg_color=ct['BG'], border_color=ct['BORDER'])
        self._salary_entry.insert(0, f"{ask:,}")
        self._salary_entry.pack(anchor="w", pady=(0, 12))
        self._salary_entry.bind('<KeyRelease>', lambda _e: _paint())

        # Which club the hire joins -- NHL roster or AHL affiliate. Poached
        # AHL staffers default to the farm (lateral move); everyone else
        # defaults to the NHL club.
        self._body(body, text="Assign to:", dim=True,
                   size=11).pack(anchor="w", pady=(0, 4))
        _default_asg = "AHL" if (self.hire_source == "ahl_poach") else "NHL"
        asg_seg = ctk.CTkSegmentedButton(
            body, values=["NHL", "AHL"],
            selected_color=ct['TEAL'], selected_hover_color=ct['TEAL_HOVER'],
            unselected_color=ct['CARD'], unselected_hover_color=ct['BORDER'],
            command=lambda _v: _paint())
        asg_seg.set(_default_asg)
        asg_seg.pack(anchor="w", pady=(0, 12))
        self._asg_seg = asg_seg

        offer_label = self._body(body, text="", size=12)
        offer_label.pack(anchor="w", pady=(0, 2))
        chance_label = self._body(body, text="", size=11)
        chance_label.pack(anchor="w", pady=(0, 12))

        def _paint():
            offer_info['years'] = int(years_seg.get())
            salary = self._parse_offer()
            if salary is None:
                offer_label.configure(text="Enter an offer amount.")
                chance_label.configure(text="")
                return
            offer_label.configure(
                text=f"Your offer: ${salary:,} / year  x  {offer_info['years']} "
                     f"year{'s' if offer_info['years'] > 1 else ''}")
            chance = self._staff_offer_accept_chance(staff, salary)
            if chance >= 0.75:
                color = ct['GREEN']
            elif chance >= 0.45:
                color = ct['GOLD']
            else:
                color = ct['RED']
            chance_label.configure(text=f"Estimated acceptance chance: {chance:.0%}",
                                   text_color=color)
            # Over-budget flag, live.
            if salary > (self._budget_remaining or 0):
                chance_label.configure(
                    text=f"Estimated acceptance chance: {chance:.0%}  \u2014  "
                         f"exceeds your available staff budget "
                         f"(${self._budget_remaining:,})",
                    text_color=ct['RED'])

        _paint()

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(4, 0))
        self._secondary_button(btns, text="Back",
                               command=self.close_view).pack(side="right",
                                                            padx=(10, 0))
        self._primary_button(btns, text="Make Offer",
                             command=lambda: self._resolve_staff_offer(
                                 staff, offer_info['years'],
                                 self._asg_seg.get().lower())).pack(side="right")

    def _staff_offer_accept_chance(self, staff, offer_salary):
        """Rough acceptance chance for a staff offer (display only)."""
        from game_classes import staff_market_ask
        ask = staff_market_ask(staff)
        salary_mult = offer_salary / max(1, ask)
        rating = to_100_scale(staff.overall_rating)
        try:
            prestige = getattr(self.app.game_manager.user_team, 'prestige', 50)
        except Exception:
            prestige = 50
        base = 0.45 + (salary_mult - 1.0) * 1.4 + (prestige - 50) / 400 - (rating - 60) / 600
        # GM stature: top coaches want to work for a GM the league
        # respects. Additive, bounded +/-0.08.
        try:
            import reputation_system as _rs
            base += _rs.gm_staff_accept_delta(
                self.app.game_manager.user_team)
        except Exception:
            pass
        return max(0.05, min(0.98, base))

    def _resolve_staff_offer(self, staff, years, assignment="nhl"):
        """Resolve a staff contract offer (original acceptance logic).

        The acceptance roll happens FIRST; the roster is only mutated
        on acceptance. (Signing before the roll hired staffers who had
        just declined the offer.)

        assignment picks which club the hire joins: "nhl" or "ahl".
        """
        import random
        salary = self._parse_offer()
        if salary is None:
            messagebox.showerror("Invalid Offer",
                                 "Enter a valid salary amount in dollars.")
            return
        # League-wide staff budget: hard block.
        try:
            team = self.app.game_manager.user_team
            remaining = (team.staff_budget_remaining()
                         if hasattr(team, 'staff_budget_remaining') else 0)
        except Exception:
            remaining = 0
        if salary > remaining:
            messagebox.showerror(
                "Over Budget",
                f"That offer (${salary:,}/yr) exceeds your available staff "
                f"budget (${remaining:,}). Every club in the league works "
                f"under a staff payroll budget -- trim the offer or move "
                f"money by letting staff go.")
            return
        # MP client: the host runs the acceptance roll against canonical
        # state -- a local roll would be snapshot noise.
        if _mp_route(self.app, "hire_staff",
                     {"staff_id": str(getattr(staff, "id", "")),
                      "salary": salary, "years": years,
                      "assignment": assignment},
                     on_sent=self.close_view):
            return
        chance = self._staff_offer_accept_chance(staff, salary)
        if random.random() < chance:
            # Only leave the source pool/club AFTER a successful signing --
            # if sign_free_agent_staff fails (e.g. a budget race), the
            # staffer must not be lost from their old club/pool.
            if self.app.game_manager.sign_free_agent_staff(
                    staff, salary, years, assignment):
                league = getattr(self.app, 'league', None)
                if self.hire_source == "overseas" and league is not None:
                    pool = getattr(league, "overseas_staff", None)
                    if pool is not None and staff in pool:
                        pool.remove(staff)
                elif (self.hire_source == "ahl_poach"
                      and self.from_team is not None
                      and staff in self.from_team.staff):
                    self.from_team.staff.remove(staff)
                messagebox.showinfo("Offer Accepted",
                                    f"{staff.full_name} has accepted your offer!")
                try:
                    self.app.update_all_views()
                except Exception:
                    pass
                self.close_view()
            else:
                messagebox.showerror("Error", "Failed to sign staff member. Check your budget.")
        else:
            messagebox.showinfo("Offer Declined",
                                f"{staff.full_name} has declined your offer. "
                                f"Consider offering a better salary.")

class CaptainChangeDialog(InGamePopup):
    """Pre-change judgment call: stripping the C has consequences.

    Buttons: speak with him first / announce it cold / cancel.
    Result in self.result: "speak" | "cold" | "cancel".
    """

    def __init__(self, app, old_name, new_name, reasons, **kwargs):
        kwargs.pop("parent", None)
        super().__init__(app, modal=True, **kwargs)
        self.title("Changing the Captaincy")
        self.result = "cancel"
        body = ttk.Frame(self, style='Card.TFrame', padding=20)
        body.pack(fill='both', expand=True)
        ttk.Label(
            body,
            text=(f"Stripping the C from {old_name} will have consequences.\n"
                  f"{new_name} takes over -- unless {old_name} is spoken "
                  "to first and respects the call."),
            style='TLabel', wraplength=480, justify='left').pack(
                anchor='w', pady=(0, 10))
        if reasons:
            ttk.Label(body, text="What you know:",
                      style='TLabel').pack(anchor='w')
            for r in reasons[:5]:
                ttk.Label(body, text=f"\u2022 {r}", style='Secondary.TLabel',
                          wraplength=480, justify='left').pack(
                              anchor='w', padx=8, pady=1)
        btns = ttk.Frame(body, style='Card.TFrame')
        btns.pack(fill='x', pady=(16, 0))
        ttk.Button(btns, text="Speak with him first",
                   command=lambda: self._choose("speak")).pack(
                       side='left', padx=(0, 8))
        ttk.Button(btns, text="Announce it cold",
                   command=lambda: self._choose("cold")).pack(
                       side='left', padx=(0, 8))
        ttk.Button(btns, text="Cancel",
                   command=lambda: self._choose("cancel")).pack(side='left')
        try:
            self.geometry("560x460")
        except Exception:
            pass

    def _choose(self, value):
        self.result = value
        try:
            self.destroy()
        except Exception:
            pass


class CaptainPushbackDialog(InGamePopup):
    """He pushed back: stand firm, compromise (keep an A), or back down.

    Result in self.result: "firm" | "alternate" | "backdown".
    """

    _QUOTES = {
        "pushback": "\u201cAfter everything I've given this team? You're "
                    "making a mistake.\u201d",
        "extreme": "\u201cWe're done here.\u201d He walks out.",
    }

    def __init__(self, app, old_name, new_name, tier, **kwargs):
        kwargs.pop("parent", None)
        super().__init__(app, modal=True, **kwargs)
        self.title("He Pushed Back")
        self.result = "backdown"
        body = ttk.Frame(self, style='Card.TFrame', padding=20)
        body.pack(fill='both', expand=True)
        ttk.Label(
            body,
            text=(f"{old_name} is not accepting the change to {new_name}:\n\n"
                  f"{self._QUOTES.get(tier, '')}\n\n"
                  "You have to make the call."),
            style='TLabel', wraplength=480, justify='left').pack(
                anchor='w', pady=(0, 16))
        btns = ttk.Frame(body, style='Card.TFrame')
        btns.pack(fill='x')
        ttk.Button(btns, text="Stand firm",
                   command=lambda: self._choose("firm")).pack(
                       side='left', padx=(0, 8))
        ttk.Button(btns, text="Name him alternate (A)",
                   command=lambda: self._choose("alternate")).pack(
                       side='left', padx=(0, 8))
        ttk.Button(btns, text="Back down",
                   command=lambda: self._choose("backdown")).pack(side='left')
        try:
            self.geometry("560x400")
        except Exception:
            pass

    def _choose(self, value):
        self.result = value
        try:
            self.destroy()
        except Exception:
            pass


class SetCaptainsView(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the SetCaptainsWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(fg_color=parent.BG_COLOR)

        self.captain_var = tk.StringVar(master=self)
        self.alternate1_var = tk.StringVar(master=self)
        self.alternate2_var = tk.StringVar(master=self)

        self._create_widgets()
        self.load_captains()

    def _create_widgets(self):
        # Focus card: this was a small dialog; on the full-screen view its
        # content lives in a centered card instead of stretching edge to edge.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = ttk.Frame(self, style='Card.TFrame', padding=24, width=560)
        card.grid(row=0, column=0, pady=24)
        main_frame = ttk.Frame(card, style='Card.TFrame')
        main_frame.pack(fill='both', expand=True)

        players = [p.full_name for p in self.app.user_team.roster]

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
        for p in self.app.user_team.roster:
            if p.captaincy == 'C':
                self.captain_var.set(p.full_name)
            elif p.captaincy == 'A':
                if not self.alternate1_var.get():
                    self.alternate1_var.set(p.full_name)
                else:
                    self.alternate2_var.set(p.full_name)

    def save_captains(self):
        team = self.app.user_team
        try:
            import captaincy_change as _cc
        except Exception:
            _cc = None

        def _by_name(nm):
            if not nm:
                return None
            for p in (getattr(team, "roster", None) or []):
                try:
                    if p.full_name == nm:
                        return p
                except Exception:
                    pass
            return None

        old_c = next((p for p in (getattr(team, "roster", None) or [])
                      if getattr(p, "captaincy", "") == "C"), None)
        new_c = _by_name(self.captain_var.get())
        alt1 = _by_name(self.alternate1_var.get())
        alt2 = _by_name(self.alternate2_var.get())

        # A deposition: an established captain is losing the C to someone
        # else (or to a vacancy). That has consequences -- route through
        # the judgment-call flow instead of the silent wipe.
        deposition = (
            _cc is not None and old_c is not None
            and _cc.is_established_captain(old_c)
            and (new_c is None or new_c is not old_c))
        dep_ctx = None
        if deposition:
            _proceed, dep_ctx = self._run_deposition_flow(
                team, old_c, new_c, _cc)
            if not _proceed:
                return  # backed down or cancelled: leave everything as is
        # MP client: letters land on the host's canonical roster. The
        # deposition conversation happened here; its fallout applies on
        # the host via the deposition context.
        _cap_params = {
            "captain_id": (str(getattr(new_c, "id", ""))
                           if new_c is not None else ""),
            "alt_ids": [str(getattr(a, "id", ""))
                        for a in (alt1, alt2) if a is not None]}
        if dep_ctx:
            _cap_params["deposition"] = dep_ctx

        def _caps_sent():
            messagebox.showinfo(
                "Captains Sent",
                "Your captaincy picks were sent to the host and apply "
                "on the next sync.")
            self.close_view()
        if _mp_route(self.app, "set_captaincy", _cap_params,
                     on_sent=_caps_sent):
            return
        if deposition:
            self._apply_letters(team, new_c, alt1, alt2,
                               skip_captain=True)
        else:
            self._apply_letters(team, new_c, alt1, alt2,
                               skip_captain=False)
        # A human just chose: never mistake these letters for auto-repair.
        try:
            self.app.user_team._captaincy_auto_assigned = False
        except Exception:
            pass
        messagebox.showinfo("Captains Updated", "Team captaincy has been updated.")
        self.app.update_all_views()
        self.close_view()

    @staticmethod
    def _apply_letters(team, new_c, alt1, alt2, skip_captain=False):
        """Write the chosen letters. skip_captain: the C was already dealt
        by the deposition flow -- only the alternates are (re)written."""
        for p in (getattr(team, "roster", None) or []):
            try:
                if skip_captain and getattr(p, "captaincy", "") == "C":
                    continue
                p.captaincy = None
            except Exception:
                pass
        targets = []
        if new_c is not None and not skip_captain:
            targets.append((new_c, "C"))
        if alt1 is not None:
            targets.append((alt1, "A"))
        if alt2 is not None:
            targets.append((alt2, "A"))
        for p, letter in targets:
            try:
                if getattr(p, "captaincy", "") == "C" and letter != "C":
                    continue  # never clobber the dealt C
                p.captaincy = letter
            except Exception:
                pass

    def _run_deposition_flow(self, team, old_c, new_c, _cc):
        """The judgment call. Returns (proceed, dep_ctx).

        The conversation (dialogs, pushback, the call) always happens
        here -- it's the GM's experience. dep_ctx describes the outcome
        for the host when the letters must land on canonical state (MP
        client); None when the consequences were applied locally (SP),
        which is also the case the host never sees.
        Headless fallback: talk first, stand firm -- same as the AI."""
        try:
            league = getattr(self.app, "league", None)
            info = _cc.assess_deposition(old_c, new_c, team, league)
            old_name = getattr(old_c, "full_name", "the captain")
            new_name = (getattr(new_c, "full_name", "no one")
                        if new_c is not None else "no one")
            dlg = CaptainChangeDialog(self.app, old_name, new_name,
                                      info.get("reasons", []))
            dlg.wait_window()
            pre = dlg.result
        except Exception:
            pre, info = "speak", {"acceptance": 0.5}
            old_name = getattr(old_c, "full_name", "the captain")
            new_name = (getattr(new_c, "full_name", "no one")
                        if new_c is not None else "no one")
        if pre == "cancel":
            return False, None
        talked = (pre == "speak")
        acceptance = float(info.get("acceptance", 0.5))
        acceptance += 0.18 if talked else -0.10
        acceptance = max(0.02, min(0.98, acceptance))
        tier = _cc.roll_tier(acceptance)
        if tier in ("pushback", "extreme"):
            try:
                pdlg = CaptainPushbackDialog(self.app, old_name, new_name,
                                             tier)
                pdlg.wait_window()
                call = pdlg.result
            except Exception:
                call = "firm"
            if call == "backdown":
                return False, None
            compromise = (call == "alternate")
        else:
            compromise = False
        try:
            date_str = self.app.current_date.isoformat()
        except Exception:
            date_str = ""
        # MP client: the fallout (morale, news, the letters) lands on the
        # host's canonical state -- applying it to this snapshot would be
        # wiped by the next sync.
        if _mp_is_client(self.app):
            return True, {"old_captain_id": str(getattr(old_c, "id", "")),
                          "tier": tier, "talked": talked,
                          "compromise": compromise, "date_str": date_str}
        report = _cc.apply_deposition(team, old_c, new_c, tier,
                                      talked=talked, date_str=date_str,
                                      compromise_alternate=compromise)
        for line in (report.get("news") or []):
            try:
                self.app.add_news(line)
            except Exception:
                pass
        detail = "\n".join(report.get("lines", []))
        if detail:
            try:
                messagebox.showinfo("Captaincy Change", detail)
            except Exception:
                pass
        # Extreme fallout leaves a repair path in the Dressing Room
        # ("Clear the air" row) -- nothing more to do here.
        return True, None

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

class SetCaptainsWindow(InGamePopup):
    """Popup wrapper around SetCaptainsView (backward compatibility).

    New code should embed SetCaptainsView as a full-screen view via
    HockeyManagerGUI.show_screen() instead of opening this card.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(args[0] if args else kwargs.get("parent"))
        parent = args[0] if args else kwargs.get("parent")
        kwargs.pop("parent", None)
        self._view = SetCaptainsView(self, app=parent, *args[1:], **kwargs)
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


class MandatoryCaptainsView(SetCaptainsView):
    """Item 7: mandatory, non-dismissible captain picker.

    Built on the SetCaptainsView combobox flow. Confirm validates
    (exactly 1 C + 2 As, no goalie letters, no double letters) and shows
    a clear inline error instead of silently fixing; persistence goes
    through GameManager._persist_captaincy_pick, the manual tool's
    by-name flow. There is no cancel path -- the hosting window refuses
    to close until a legal pick is confirmed.

    R1: candidates are sorted by leadership (best first) and each name
    carries its current letter ("Name (C)" / "Name (A)") so nobody is
    demoted by accident. The Confirm button is live-gated -- it enables
    only when the current pick validates -- and the same validation
    path backs the click, so the gate and the verdict can never
    disagree. Dropdown -> player mapping is by label->player dict, never
    by parsing the display string.
    """

    # -- R1(b)(c): candidates ------------------------------------------------
    @staticmethod
    def _leadership_of(p) -> int:
        try:
            return int(getattr(p, "leadership", 50) or 50)
        except Exception:
            return 50

    @staticmethod
    def _label_for(p) -> str:
        """Display label for a candidate: name plus its current letter,
        e.g. "Tyler St-Pierre (C)", so the user sees who holds what."""
        name = getattr(p, "full_name", "") or ""
        letter = getattr(p, "captaincy", "") or ""
        if letter == "C":
            return f"{name} (C)"
        if letter == "A":
            return f"{name} (A)"
        return name

    def _build_candidates(self):
        """Roster sorted by leadership (best first), with letter-marked
        labels. Returns (labels, label->player). Duplicate full names
        keep the same first-wins rule as the by-name validators."""
        roster = list(
            getattr(getattr(self.app, "user_team", None), "roster", None)
            or [])
        ordered = sorted(
            roster,
            key=lambda p: (-self._leadership_of(p),
                           getattr(p, "full_name", "") or ""))
        labels, mapping = [], {}
        for p in ordered:
            lab = self._label_for(p)
            labels.append(lab)
            mapping.setdefault(lab, p)
        return labels, mapping

    # -- R1(d): confirm gate -------------------------------------------------
    def _resolve_pick(self):
        """Map the three dropdown labels back to plain full names for the
        by-name GameManager validators. Unknown labels (unreachable with
        readonly combos, but cheap to guard) fall back to a robust
        trailing-marker strip, else "" so validation reports them."""
        names = []
        for var in (self.captain_var, self.alternate1_var,
                    self.alternate2_var):
            try:
                lab = (var.get() or "").strip()
            except Exception:
                lab = ""
            p = self._label_to_player.get(lab)
            if p is not None:
                names.append(getattr(p, "full_name", "") or "")
                continue
            base = lab
            if base.endswith(" (C)") or base.endswith(" (A)"):
                base = base[:-4].rstrip()
            names.append(base)
        return names[0], names[1], names[2]

    def _current_pick_error(self):
        """The live confirm gate: None when the current pick is legal,
        else the specific reason it is not. Fail-open (None) on
        unexpected errors -- the click-time check is the backstop."""
        try:
            gm = getattr(self.app, "game_manager", None) or self.app
            c, a1, a2 = self._resolve_pick()
            return gm._validate_captaincy_pick(
                self.app.user_team, c, a1, a2)
        except Exception:
            return None

    def _refresh_gate(self):
        """Enable Confirm only for a legal pick; narrate the specific
        problem otherwise. Stays quiet until the user starts picking so
        a fresh dialog doesn't open with a red error already showing."""
        err = self._current_pick_error()
        try:
            picked_any = any(
                (v.get() or "").strip() for v in
                (self.captain_var, self.alternate1_var, self.alternate2_var))
        except Exception:
            picked_any = True
        try:
            self.error_var.set(err if (err and picked_any) else "")
        except Exception:
            pass
        try:
            btn = getattr(self, "_confirm_btn", None)
            if btn is not None:
                btn.state(["!disabled"] if err is None else ["disabled"])
        except Exception:
            pass

    def _confirm_current_pick(self) -> bool:
        """Validate and persist the current dropdown picks. True when a
        legal pick was confirmed (dialog closed); False when rejected
        with the specific reason shown inline."""
        gm = getattr(self.app, 'game_manager', None) or self.app
        c, a1, a2 = self._resolve_pick()
        err = gm._validate_captaincy_pick(self.app.user_team, c, a1, a2)
        if err:
            self.error_var.set(err)
            try:
                self.error_label.update_idletasks()
            except Exception:
                pass
            self._refresh_gate()
            return False
        # MP client: letters land on the host's canonical roster.
        _by_id = {}
        for _p in (getattr(self.app.user_team, "roster", None) or []):
            try:
                _by_id[getattr(_p, "full_name", "")] = str(
                    getattr(_p, "id", ""))
            except Exception:
                pass
        if _mp_route(self.app, "set_captaincy",
                     {"captain_id": _by_id.get(c, ""),
                      "alt_ids": [_by_id.get(a1, ""), _by_id.get(a2, "")]},
                     on_sent=self.close_view):
            return True
        gm._persist_captaincy_pick(self.app.user_team, c, a1, a2)
        try:
            self.app.update_all_views()
        except Exception:
            pass
        self.close_view()
        return True

    def load_captains(self):
        """Preset the dropdowns to the club's current letters, using the
        letter-marked labels so the selection mapping stays exact."""
        labels = getattr(self, "_label_to_player", None) or {}
        roster = list(
            getattr(getattr(self.app, "user_team", None), "roster", None)
            or [])
        for p in roster:
            try:
                lab = self._label_for(p)
                if lab not in labels:
                    continue
                if getattr(p, "captaincy", "") == "C":
                    self.captain_var.set(lab)
                elif getattr(p, "captaincy", "") == "A":
                    if not self.alternate1_var.get():
                        self.alternate1_var.set(lab)
                    else:
                        self.alternate2_var.set(lab)
            except Exception:
                pass

    def _create_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = ttk.Frame(self, style='Card.TFrame', padding=24, width=600)
        card.grid(row=0, column=0, pady=24, sticky='n')
        main_frame = ttk.Frame(card, style='Card.TFrame')
        main_frame.pack(fill='both', expand=True)

        team_name = getattr(getattr(self.app, 'user_team', None),
                            'team_name', 'your team')
        ttk.Label(
            main_frame, text="Name your captains",
            style='Card.TLabel',
            font=_sfont(self.app.FONT_FAMILY, 14, 'bold')
        ).pack(anchor='w', pady=(0, 4))
        ttk.Label(
            main_frame,
            text=("NHL Rule 6.1 requires every club to dress exactly one "
                  f"captain (C) and two alternates (A). Pick {team_name}'s "
                  "letters to continue \u2014 a goaltender cannot wear a "
                  "letter, and one player cannot hold two letters."),
            style='Card.TLabel',
            font=_sfont(self.app.FONT_FAMILY, 10),
            wraplength=540, justify='left'
        ).pack(anchor='w', pady=(0, 14))

        # R1(b)(c): leadership-sorted candidates, each showing its
        # current letter so nobody is demoted by accident.
        self._cand_labels, self._label_to_player = self._build_candidates()
        players = self._cand_labels

        ttk.Label(main_frame, text="Captain (C):", style='Card.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 11, 'bold')
                  ).pack(anchor='w', pady=(0, 5))
        ttk.Combobox(main_frame, textvariable=self.captain_var,
                     values=players, state='readonly',
                     font=_sfont(self.app.FONT_FAMILY, 11)
                     ).pack(fill='x', pady=(0, 10))

        ttk.Label(main_frame, text="Alternate Captain (A):", style='Card.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 11, 'bold')
                  ).pack(anchor='w', pady=(0, 5))
        ttk.Combobox(main_frame, textvariable=self.alternate1_var,
                     values=players, state='readonly',
                     font=_sfont(self.app.FONT_FAMILY, 11)
                     ).pack(fill='x', pady=(0, 10))

        ttk.Label(main_frame, text="Alternate Captain (A):", style='Card.TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 11, 'bold')
                  ).pack(anchor='w', pady=(0, 5))
        ttk.Combobox(main_frame, textvariable=self.alternate2_var,
                     values=players, state='readonly',
                     font=_sfont(self.app.FONT_FAMILY, 11)
                     ).pack(fill='x', pady=(0, 10))

        self.error_var = tk.StringVar(master=self)
        self.error_label = ttk.Label(
            main_frame, textvariable=self.error_var, style='Card.TLabel',
            font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
            foreground='#e5484d', wraplength=540, justify='left')
        self.error_label.pack(anchor='w', pady=(2, 8))

        self._confirm_btn = ttk.Button(main_frame, text="Confirm Captains",
                                      command=self.save_captains)
        self._confirm_btn.pack(pady=(6, 4))
        # R1(d): live confirm gate -- the button enables only when the
        # current pick validates; the error line narrates why not.
        for _var in (self.captain_var, self.alternate1_var,
                     self.alternate2_var):
            try:
                _var.trace_add("write",
                               lambda *_a: self._refresh_gate())
            except Exception:
                pass
        self._refresh_gate()

    def save_captains(self):
        """Validate, then persist exactly like the manual tool. Invalid
        picks are rejected with an inline message -- never silently
        fixed, and the blocker stays open."""
        self._confirm_current_pick()


class MandatoryCaptainsWindow(InGamePopup):
    """Item 7: modal, non-dismissible host for MandatoryCaptainsView.

    The card cannot be closed -- not by its X button, not by Escape --
    until a legal 1C+2A pick is confirmed. Callers block on wait_window().
    """

    def __init__(self, app, team=None, **kwargs):
        kwargs.pop("parent", None)
        super().__init__(app, modal=True, **kwargs)
        self.title("Name Your Captains")
        # Non-dismissible: the popup manager ignores Escape / click-out
        # for non-dismissible cards, and the title-bar X is refused below.
        try:
            self._dismissible = False
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._refuse_close)
        self._view = MandatoryCaptainsView(self, app=app)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)
        try:
            self.geometry("640x640")
            self.fit_to_content(min_w=620, min_h=560)
        except Exception:
            pass

    def _refuse_close(self):
        """The blocker has no cancel path -- but R1(d): when the picks
        already sitting in the dropdowns are legal, honor the close as
        a confirm instead of flashing a misleading "pick your captains"
        error at a user who already did. Anything else nudges back to
        the form with the SPECIFIC reason the pick is illegal."""
        try:
            if self._view._confirm_current_pick():
                return
        except Exception:
            pass
        try:
            err = self._view._current_pick_error()
            self._view.error_var.set(
                err or "Pick exactly one captain (C) and two alternates (A) "
                       "to continue.")
        except Exception:
            pass


# --- Drag-and-Drop Edit Lines Window ---
class GMDashboardView(ctk.CTkFrame):
    """GM Dashboard: record, cap, contracts, top performers, vitals, staff."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the GMDashboardWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(bg_color=self.app.BG_COLOR)
        self._build()

    # ---------- helpers ----------

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _card(self, master, title, r, c):
        card = ttk.Frame(master, style='Card.TFrame', padding=12)
        card.grid(row=r, column=c, sticky='nsew', padx=6, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _big(self, card, text):
        ttk.Label(card, text=text, style='TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 18, 'bold')).pack(anchor='w', pady=(2, 4))

    # ---------- build ----------
    def _build(self):
        team = self.app.user_team
        league = self.app.league
        st = league.standings.get(team.team_name, {"W": 0, "L": 0, "OTL": 0, "Points": 0})
        w, l, otl, pts = st.get("W", 0), st.get("L", 0), st.get("OTL", 0), st.get("Points", 0)
        gp = w + l + otl

        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(header, text=f"{team.city} {team.team_name}",
                  font=_sfont(self.app.FONT_FAMILY, 16, 'bold'),
                  style='TLabel').pack(side=tk.LEFT)
        season = getattr(league, 'season_year', '')
        ttk.Label(header, text=f"  Season {season}" if season else "",
                  style='Secondary.TLabel').pack(side=tk.LEFT)
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=_sfont(self.app.FONT_FAMILY, 9, 'bold'),
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
            self._line(card, f"Avg morale: {avg_morale:.1f}/100")
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
        team = self.app.user_team
        league = self.app.league
        st = league.standings.get(team.team_name, {"W": 0, "L": 0, "OTL": 0, "Points": 0})
        w, l, otl, pts = st.get("W", 0), st.get("L", 0), st.get("OTL", 0), st.get("Points", 0)
        self._fill_cards(team, league, st, w, l, otl, pts, w + l + otl)




class GMDashboardWindow(InGamePopup):
    """Popup wrapper around GMDashboardView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("GM Dashboard")
        self._view = GMDashboardView(self, app=parent, *args, **kwargs)
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
class SeasonGoalsView(ctk.CTkFrame):
    """Season Goals: board expectation, live progress, milestones, youth watch."""

    EXPECTATIONS = [
        ("cup", "Stanley Cup"),
        ("contender", "Conf. Final"),
        ("playoffs", "Playoffs"),
        ("competitive", "Winning Record"),
        ("rebuild", "Rebuild"),
    ]

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the SeasonGoalsWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(fg_color=parent.BG_COLOR)
        self._exp_var = tk.StringVar(
            master=self,
            value=getattr(parent.user_team, 'board_expectation', 'playoffs'))
        self._build()

    def _card(self, title):
        card = ttk.Frame(self, style='Card.TFrame', padding=12)
        card.pack(fill=tk.X, padx=12, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=(self.app.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=(self.app.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _set_expectation(self, key):
        self._exp_var.set(key)
        self.app.user_team.board_expectation = key
        self._paint_pills()
        self._refresh_progress()

    def _paint_pills(self):
        for key, btn in self._pill_btns:
            btn.set_selected(self._exp_var.get() == key)

    def _build(self):
        team = self.app.user_team
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=(self.app.FONT_FAMILY, 9, 'bold'),
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
                           font=(self.app.FONT_FAMILY, 9, 'bold'),
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
        team = self.app.user_team
        league = self.app.league
        st = league.standings.get(team.team_name, {"W": 0, "L": 0, "OTL": 0, "Points": 0})
        w, l, otl = st["W"], st["L"], st["OTL"]
        pts = st.get("Points", 2 * w + otl)
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
                      font=(self.app.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

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

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

class SeasonGoalsWindow(InGamePopup):
    """Popup wrapper around SeasonGoalsView (backward compatibility).

    New code should embed SeasonGoalsView as a full-screen view via
    HockeyManagerGUI.show_screen() instead of opening this card.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(args[0] if args else kwargs.get("parent"))
        parent = args[0] if args else kwargs.get("parent")
        kwargs.pop("parent", None)
        self._view = SeasonGoalsView(self, app=parent, *args[1:], **kwargs)
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

class TeamAnalyticsView(ctk.CTkFrame):
    """Team Analytics: offense, defense, goalies, scoring mix, discipline."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the TeamAnalyticsWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(bg_color=self.app.BG_COLOR)
        self._build()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _card(self, title, r, c):
        card = ttk.Frame(self.grid_host, style='Card.TFrame', padding=12)
        card.grid(row=r, column=c, sticky='nsew', padx=6, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _big(self, card, text):
        ttk.Label(card, text=text, style='TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 18, 'bold')).pack(anchor='w', pady=(2, 4))

    def _build(self):
        team = self.app.user_team
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=_sfont(self.app.FONT_FAMILY, 9, 'bold'),
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
        self._fill(self.app.user_team)




class TeamAnalyticsWindow(InGamePopup):
    """Popup wrapper around TeamAnalyticsView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Team Analytics")
        self._view = TeamAnalyticsView(self, app=parent, *args, **kwargs)
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
class SalaryAnalyticsView(ctk.CTkFrame):
    """Salary Analytics: payroll mix by position, top cap hits, expiring money."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the SalaryAnalyticsWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(bg_color=self.app.BG_COLOR)
        self._build()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _card(self, title):
        card = ttk.Frame(self, style='Card.TFrame', padding=12)
        card.pack(fill=tk.X, padx=12, pady=6)
        ttk.Label(card, text=title, style='TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=(4, 8))
        return card

    def _line(self, card, text, secondary=False):
        ttk.Label(card, text=text,
                  style='Secondary.TLabel' if secondary else 'TLabel',
                  font=_sfont(self.app.FONT_FAMILY, 10)).pack(anchor='w', pady=1)

    def _build(self):
        team = self.app.user_team
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
        PillButton(header, text="Refresh", bg='#0e0e11',
                   font=_sfont(self.app.FONT_FAMILY, 9, 'bold'),
                   padx=12, pady=5, command=self._refresh).pack(side=tk.RIGHT)
        self.body = ttk.Frame(self, style='Panel.TFrame')
        self.body.pack(fill=tk.BOTH, expand=True)
        self._fill()

    def _fill(self):
        for child in self.body.winfo_children():
            child.destroy()
        team = self.app.user_team
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




class SalaryAnalyticsWindow(InGamePopup):
    """Popup wrapper around SalaryAnalyticsView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Salary Analytics")
        self._view = SalaryAnalyticsView(self, app=parent, *args, **kwargs)
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
class BuyoutCalculatorView(ctk.CTkFrame):
    """Buyout Calculator: real NHL buyout math with execute."""

    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the BuyoutCalculatorWindow wrapper
        parent = self.app  # this __init__ addressed the app as `parent`; keep that
        self.configure(fg_color=parent.BG_COLOR)
        self._selected = None
        self._build()

    def _build(self):
        header = ttk.Frame(self, style='Panel.TFrame', padding=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 4))
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
                  font=(self.app.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        self.lb = tk.Listbox(left, height=22, activestyle='none',
                             bg='#232a3a', fg='#ffffff',
                             selectbackground='#0d2b28', relief='flat',
                             highlightthickness=1,
                             highlightbackground='#2e2e38',
                             font=(self.app.FONT_FAMILY, 10))
        self.lb.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.lb.bind('<<ListboxSelect>>', self._on_select)
        self._players = sorted(self.app.user_team.roster,
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
                  font=(self.app.FONT_FAMILY, 10,
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


    def _show_roster_menu(self, event):
        """Right-click on a roster row -> full player context menu."""
        try:
            idx = self.lb.nearest(event.y)
        except Exception:
            return
        if idx < 0 or idx >= len(getattr(self, '_players', [])):
            return
        self.lb.selection_clear(0, tk.END)
        self.lb.selection_set(idx)
        player = self._players[idx]
        PlayerContextMenu(self.parent).show_context_menu(event, player)

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
                   font=(self.app.FONT_FAMILY, 10, 'bold'),
                   padx=16, pady=7,
                   command=self._execute_buyout).pack(anchor='w', pady=(4, 0))

    def _render_active_buyouts(self):
        for child in self.active_box.winfo_children():
            child.destroy()
        team = self.app.user_team
        hits = getattr(team, 'buyout_cap_hits', {}) or {}
        if hits:
            self._line(self.active_box, "Active buyout cap hits:", bold=True)
            for yr in sorted(hits):
                self._line(self.active_box, f"{yr}: ${hits[yr]:,.0f}", secondary=True)
        else:
            self._line(self.active_box, "No active buyouts.", secondary=True)

    def _execute_buyout(self):
        """Show an in-view confirmation panel for the buyout (no popup)."""
        p = self._selected
        if not p:
            return
        total, annual, byears, rows = buyout_schedule(p)
        if not rows:
            return
        for child in self.detail.winfo_children():
            child.destroy()
        self._line(self.detail, "Confirm Buyout", bold=True)
        self._line(self.detail,
                   f"Buy out {p.full_name}? {p.full_name} will become "
                   f"a free agent.", secondary=True)
        self._line(self.detail,
                   f"Cost: ${total:,.0f} spread as ${annual:,.0f}/yr "
                   f"over {byears} years.", secondary=True)
        btns = ttk.Frame(self.detail, style='Card.TFrame')
        btns.pack(anchor='w', pady=(10, 0))
        PillButton(btns, text="Confirm Buy Out", bg='#5c1a1a',
                   font=(self.app.FONT_FAMILY, 10, 'bold'),
                   padx=16, pady=7,
                   command=lambda: self._confirm_buyout(
                       p, total, annual, byears, rows)).pack(side=tk.LEFT,
                                                             padx=(0, 8))
        PillButton(btns, text="Cancel", bg='#0e0e11',
                   font=(self.app.FONT_FAMILY, 10),
                   padx=16, pady=7,
                   command=self._render_detail).pack(side=tk.LEFT)

    def _confirm_buyout(self, p, total, annual, byears, rows):
        # Buyout window (real NHL: June 15-30). One rulebook in
        # transaction_windows.py.
        try:
            import transaction_windows as _tw
            _ok, _why = _tw.check_window(
                "buyout", getattr(self.app, "current_date", None))
            if not _ok:
                messagebox.showinfo("Buyout Window", _why)
                return
        except Exception:
            pass
        # MP client: the host applies the buyout to canonical state.
        if _mp_route(self.app, "buyout_player",
                     {"player_id": str(getattr(p, "id", ""))}):
            self._selected = None
            for child in self.detail.winfo_children():
                child.destroy()
            self._line(self.detail, "Buyout sent", bold=True)
            self._line(self.detail,
                       f"{p.full_name}'s buyout was sent to the host and "
                       f"applies on the next sync.", secondary=True)
            return
        team = self.app.user_team
        league = self.app.league
        # One rulebook: the shared buyout mutation (buyout_window.py).
        # Same math + same season-year keying as before this refactor.
        try:
            import buyout_window as _bw
            total, annual, byears, rows = _bw.execute_buyout(
                league, team, p,
                season_year=getattr(league, 'season_year', 2026))
        except Exception:
            return
        self._selected = None
        for child in self.detail.winfo_children():
            child.destroy()
        self._line(self.detail, "Buyout complete", bold=True)
        self._line(self.detail,
                   f"{p.full_name} has been bought out and is now a free "
                   f"agent. Dead cap: ${annual:,.0f}/yr for "
                   f"{byears} years.", secondary=True)
        # rebuild listbox + active buyouts
        self.lb.delete(0, tk.END)
        self._players = sorted(team.roster,
                               key=lambda pl: pl.contract.salary, reverse=True)
        for pl in self._players:
            self.lb.insert(tk.END,
                           f"{pl.full_name} ({pl.primary_position.value}) -- "
                           f"${pl.contract.salary / 1e6:.2f}M x "
                           f"{pl.contract.years_remaining}")
        self._render_active_buyouts()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

class BuyoutCalculatorWindow(InGamePopup):
    """Popup wrapper around BuyoutCalculatorView (backward compatibility).

    New code should embed BuyoutCalculatorView as a full-screen view via
    HockeyManagerGUI.show_screen() instead of opening this card.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._view = BuyoutCalculatorView(self, app=parent)
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

class GameDetailWindow(InGamePopup):
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
