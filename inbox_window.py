# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# inbox_window.py
# Email Inbox system for Hockey Manager, similar to EHM
# CustomTkinter rebuild: CTkToplevel, dark pill filters, styled dark
# message list with unread/urgent/overdue row tags, dark preview pane.

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup, confirm_card
from datetime import date
from game_classes import EmailMessage

import customtkinter as ctk
from player_context_menu import PlayerContextMenu

def _ifont(size, weight=""):
    """Scale-aware Segoe UI font (honors Settings -> Font size).

    For plain-tk widgets; CTk call sites use ui_scale.scaled() inline
    because CustomTkinter doesn't safely accept tkinter Font objects.
    """
    try:
        from ui_scale import font as _mkfont
        return _mkfont("Segoe UI", size, weight)
    except Exception:
        return ("Segoe UI", size, weight) if weight else ("Segoe UI", size)


def _scaled(px):
    try:
        from ui_scale import scaled as _s
        return _s(px)
    except Exception:
        return px


class InboxView(ctk.CTkFrame):
    """EHM-style Email Inbox view.

    A plain CTkFrame so it can be embedded anywhere: full-screen inside the
    main window (the default, via HockeyManagerGUI.open_inbox_window) or
    inside the legacy InboxWindow popup card.
    """

    _FILTERS = [
        ("All", "all"),
        ("Unread", "unread"),
        ("Urgent", "urgent"),
        ("Saved", "saved"),
        ("📖 Story", "story"),
        ("Trade", "Trade"),
        ("Scouting", "Scouting"),
        ("Contracts", "Contracts"),
        ("Injuries", "Injuries"),
        ("Media", "Media"),
        ("League", "League"),
    ]

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
        ctk.CTkFrame.__init__(self, parent, fg_color=BG)
        self.app = app if app is not None else parent
        # Set by show_screen() (dashboard) or the InboxWindow wrapper (card).
        self._close_screen = None

        # Initialize inbox reference
        self.inbox = self.app.user_team.inbox
        self.selected_message = None
        self._current_filter = "all"

        self._setup_tree_style()
        self._create_interface()
        self._populate_inbox()



    # ------------------------------------------------------------------
    # CTk styling helpers
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """No-op: the Gmail-style row list (2026-10-04) replaced the
        ttk.Treeview, so there is no tree style to configure."""

    def _create_interface(self):
        """Create the main inbox interface."""
        ct = self._ct

        main_container = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main_container.pack(fill='both', expand=True, padx=15, pady=15)

        # Header card: title + inbox stats
        header = ctk.CTkFrame(main_container, fg_color=ct['CARD'],
                              corner_radius=12)
        header.pack(fill='x', pady=(0, 12))
        self._heading(header, "Inbox", size=20).pack(
            side='left', padx=16, pady=12)
        self.stats_label = self._body(header, "", size=12, dim=True)
        self.stats_label.pack(side='right', padx=16, pady=12)

        # Filter pills
        self._create_filter_pills(main_container)

        # Bottom toolbar (docked to the bottom via side='bottom'; packed
        # before the content frame so it always keeps its space)
        self._create_toolbar(main_container)

        # Main content area - emails above, message content below. The
        # preview pane carries the email itself and gets the larger share
        # of the space; the list is just the index.
        content_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        content_frame.pack(fill='both', expand=True, pady=(12, 0))
        content_frame.grid_columnconfigure(0, weight=1)
        # uniform group: the cavity is split strictly 1:2 by weight -- the
        # open email is the biggest part of the window, EHM-style, while the
        # message list (with its tall treeview) scrolls in its strip.
        content_frame.grid_rowconfigure(0, weight=1, uniform="inbox_rows")
        content_frame.grid_rowconfigure(1, weight=2, uniform="inbox_rows")

        list_frame = ctk.CTkFrame(content_frame, fg_color=ct['CARD'],
                                  corner_radius=12)
        list_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 6))
        preview_frame = ctk.CTkFrame(content_frame, fg_color=ct['CARD'],
                                     corner_radius=12)
        preview_frame.grid(row=1, column=0, sticky='nsew', pady=(6, 0))

        self._content_frame = content_frame
        self._list_frame = list_frame
        self._preview_frame = preview_frame

        self._create_email_list(list_frame)
        self._create_email_preview(preview_frame)

        # Season Story view (Muck 2026-10-02): a unified chronological
        # narrative surface -- storylines, rivalries, milestones, digest --
        # in the inbox, EHM/FM-style. Hidden until the Story filter pill
        # is selected; spans both content rows when shown.
        self._story_frame = ctk.CTkScrollableFrame(
            content_frame, fg_color=ct['CARD'], corner_radius=12)
        self._story_frame.grid(row=0, column=0, rowspan=2, sticky='nsew')
        self._story_frame.grid_remove()
        # Same scroll-speedup as the interactive frame (story cards pile up).
        self._speed_up_scroll(self._story_frame)

    def _speed_up_scroll(self, scrollable_frame, increment=90):
        """Make wheel scrolling snappy on widget-heavy CTkScrollableFrames.

        CTkScrollableFrame redraws all child widgets on each scroll step;
        with 30+ widgets each 30px step costs 20-50ms (visibly choppy).
        Bumping yscrollincrement 3x means 3x fewer steps to cover the same
        distance. Applies to both the frame's own wheel handler and the
        global scroll_manager (both scroll in "units"). Never raises.
        """
        try:
            scrollable_frame._parent_canvas.configure(
                yscrollincrement=increment)
        except Exception:
            pass

    def _create_filter_pills(self, parent):
        """Two rows of rounded CTk filter pills (selected pill is teal).

        Row 1: status filters. Row 2: category filters. Two rows keep all
        nine pills visible at the default window width.
        """
        ct = self._ct
        pill_card = ctk.CTkFrame(parent, fg_color=ct['PANEL'],
                                 corner_radius=10)
        pill_card.pack(fill='x', pady=(0, 0))
        self._filter_buttons = {}
        status_row = ctk.CTkFrame(pill_card, fg_color="transparent")
        status_row.pack(fill='x', padx=8, pady=(8, 2))
        category_row = ctk.CTkFrame(pill_card, fg_color="transparent")
        category_row.pack(fill='x', padx=8, pady=(2, 8))
        for label, filter_type in self._FILTERS:
            row = (status_row if filter_type in ("all", "unread", "urgent",
                                                "saved")
                   else category_row)
            btn = ctk.CTkButton(
                row, text=label,
                fg_color=ct['CARD'], hover_color=ct['BORDER'],
                text_color=ct['TEXT'],
                border_width=1, border_color=ct['BORDER'],
                corner_radius=16, height=30, width=110,
                font=('Segoe UI', _scaled(11)),
                command=lambda f=filter_type: self._apply_filter(f))
            btn.pack(side='left', padx=4)
            self._filter_buttons[filter_type] = btn
        self._paint_filter_pills()

    def _paint_filter_pills(self):
        """Highlight the active filter pill in teal."""
        ct = self._ct
        for ftype, btn in self._filter_buttons.items():
            if ftype == self._current_filter:
                btn.configure(fg_color=ct['TEAL'], hover_color=ct['TEAL_HOVER'],
                              text_color=ct['BG'], border_color=ct['TEAL'])
            else:
                btn.configure(fg_color=ct['CARD'], hover_color=ct['BORDER'],
                              text_color=ct['TEXT'], border_color=ct['BORDER'])

    def _create_email_list(self, parent):
        """Gmail-style message list: friendly rows with color indicators.

        Replaces the old spreadsheet Treeview (2026-10-04). Each message is
        a row card: colored indicator bar on the left, sender + subject +
        snippet, date on the right. Mandatory messages (requires_response)
        get a red bar and an "Action needed" pill so they stand out.
        """
        ct = self._ct
        self._heading(parent, "Messages", size=14).pack(
            anchor='w', padx=14, pady=(12, 2))

        # Color legend: what each indicator means.
        legend = ctk.CTkFrame(parent, fg_color="transparent")
        legend.pack(fill='x', padx=14, pady=(0, 4))
        for color, text in [(ct['RED'], "Action needed"),
                            (ct['GOLD'], "Urgent"),
                            (ct['TEAL'], "Unread")]:
            ctk.CTkLabel(legend, text="\u25cf", text_color=color,
                         font=('Segoe UI', _scaled(10))).pack(
                             side='left', padx=(0, 2))
            ctk.CTkLabel(legend, text=text, text_color=ct['TEXT_DIM'],
                         font=('Segoe UI', _scaled(10))).pack(
                             side='left', padx=(0, 12))

        self._list_scroll = ctk.CTkScrollableFrame(parent,
                                                   fg_color="transparent")
        self._list_scroll.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self._speed_up_scroll(self._list_scroll)
        self._row_widgets = {}   # message.id -> row CTkFrame
        self._row_messages = {}  # message.id -> EmailMessage
        self._selected_message_id = None

        # Context menu (right-click on a row)
        self._create_context_menu()

    def _indicator_for(self, message):
        """Return (bar_color, needs_action) for a message row.

        Red    = mandatory: requires a response / is overdue (blocks Continue)
        Gold   = urgent or important
        Blue   = plain unread
        None   = read, nothing pending
        """
        ct = self._ct
        try:
            if message.is_overdue():
                return ct['RED'], True
        except Exception:
            pass
        if getattr(message, 'requires_response', False):
            return ct['RED'], True
        if getattr(message, 'is_urgent', False) or message.priority >= 4:
            return ct['GOLD'], False
        if getattr(message, 'is_important', False) or message.priority >= 3:
            return ct['GOLD'], False
        if not message.is_read:
            return ct['TEAL'], False
        return None, False

    def _bind_row_clicks(self, widget, message):
        """Bind click/double-click/right-click on a row and its children."""
        widget.bind('<Button-1>',
                    lambda e, m=message: self._select_message(m))
        widget.bind('<Double-Button-1>',
                    lambda e: self._on_row_double_click())
        widget.bind('<Button-3>',
                    lambda e, m=message: self._show_row_context_menu(e, m))
        for child in widget.winfo_children():
            self._bind_row_clicks(child, message)

    def _add_message_row(self, message):
        """Add one Gmail-style row card for a message."""
        ct = self._ct
        bar_color, needs_action = self._indicator_for(message)
        unread = not message.is_read
        mid = getattr(message, 'id', None) or str(id(message))

        row = ctk.CTkFrame(self._list_scroll, fg_color=ct['CARD'],
                           corner_radius=8)
        row.pack(fill='x', padx=4, pady=3)

        # Left color indicator bar
        bar = ctk.CTkFrame(row, fg_color=bar_color or ct['CARD'],
                           width=4, corner_radius=2)
        bar.pack(side='left', fill='y', padx=(8, 0), pady=8)

        # Text block: sender / subject + snippet
        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side='left', fill='both', expand=True,
                        padx=(10, 4), pady=7)
        sender_font = ('Segoe UI', _scaled(11), 'bold') if unread else \
            ('Segoe UI', _scaled(11))
        ctk.CTkLabel(text_frame, text=message.sender or "(no sender)",
                     font=sender_font, text_color=ct['TEXT'],
                     anchor='w').pack(fill='x')
        snippet = (getattr(message, 'content', '') or "").replace(
            "\n", " ").strip()
        if len(snippet) > 90:
            snippet = snippet[:90] + "\u2026"
        subj_line = message.subject or "(no subject)"
        if snippet:
            subj_line += f"  \u2014  {snippet}"
        subj_font = ('Segoe UI', _scaled(10), 'bold') if unread else \
            ('Segoe UI', _scaled(10))
        ctk.CTkLabel(text_frame, text=subj_line, font=subj_font,
                     text_color=ct['TEXT'] if unread else ct['TEXT_DIM'],
                     anchor='w').pack(fill='x')

        # Right block: date + action pill
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side='right', padx=(4, 10), pady=7)
        try:
            age = message.get_age_days()
        except Exception:
            age = 0
        if age <= 0:
            date_str = "Today"
        elif age == 1:
            date_str = "Yesterday"
        else:
            try:
                date_str = message.date_sent.strftime("%m/%d")
            except Exception:
                date_str = ""
        ctk.CTkLabel(right, text=date_str,
                     font=('Segoe UI', _scaled(10)),
                     text_color=ct['TEXT_DIM'], anchor='e').pack(anchor='e')
        if getattr(message, "is_saved", False):
            ctk.CTkLabel(right, text="\U0001f4cc",
                         font=('Segoe UI', _scaled(10)),
                         text_color=ct['TEXT_DIM'], anchor='e').pack(anchor='e')
        if needs_action:
            ctk.CTkLabel(right, text="Action needed",
                         font=('Segoe UI', _scaled(9), 'bold'),
                         text_color="#ffffff", fg_color=ct['RED'],
                         corner_radius=10, padx=8, pady=2,
                         anchor='e').pack(anchor='e', pady=(4, 0))

        self._bind_row_clicks(row, message)
        self._row_widgets[mid] = row
        self._row_messages[mid] = message
        # Keep the legacy tree_maps working for focus_message() callers.
        try:
            if not hasattr(self.app, 'tree_maps'):
                self.app.tree_maps = {}
            self.app.tree_maps.setdefault('inbox_messages', {})[mid] = message
        except Exception:
            pass
        self._paint_row_selection()

    def _paint_row_selection(self):
        """Highlight the selected row."""
        ct = self._ct
        for mid, row in self._row_widgets.items():
            try:
                row.configure(
                    fg_color=ct['ROW_SELECTED']
                    if mid == self._selected_message_id else ct['CARD'])
            except Exception:
                pass

    def _select_message(self, message):
        """Select a message row and show it in the preview pane."""
        mid = getattr(message, 'id', None) or str(id(message))
        self._selected_message_id = mid
        self.selected_message = message
        self._paint_row_selection()
        self._display_message_preview(message)

    def _clear_rows(self):
        """Remove all message rows."""
        for child in self._list_scroll.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._row_widgets = {}
        self._row_messages = {}
        self._selected_message_id = None
        self.selected_message = None
        try:
            if hasattr(self.app, 'tree_maps') and \
                    'inbox_messages' in self.app.tree_maps:
                self.app.tree_maps['inbox_messages'].clear()
        except Exception:
            pass
    def _create_email_preview(self, parent):
        """Create the email preview pane."""
        ct = self._ct
        self._heading(parent, "Message", size=14).pack(
            anchor='w', padx=14, pady=(12, 6))

        # Email header card (compact two-column grid -- the pane is now
        # full width, so From/Date and Subject/Category share rows and the
        # message body gets the vertical room).
        header_frame = ctk.CTkFrame(parent, fg_color=ct['PANEL'],
                                    corner_radius=10)
        header_frame.pack(fill='x', padx=12, pady=(0, 8))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=1)

        self.preview_from_label = self._body(header_frame, "From: ", size=11)
        self.preview_from_label.grid(row=0, column=0, sticky='w',
                                     padx=12, pady=(8, 2))
        self.preview_date_label = self._body(header_frame, "Date: ", size=11)
        self.preview_date_label.grid(row=0, column=1, sticky='w',
                                     padx=12, pady=(8, 2))
        self.preview_subject_label = self._body(header_frame, "Subject: ",
                                                size=11)
        self.preview_subject_label.grid(row=1, column=0, sticky='w',
                                        padx=12, pady=(2, 8))
        self.preview_category_label = self._body(header_frame, "Category: ",
                                                 size=11)
        self.preview_category_label.grid(row=1, column=1, sticky='w',
                                         padx=12, pady=(2, 8))

        # Email content (dark CTkTextbox with styled scrollbar)
        self.content_text = ctk.CTkTextbox(
            parent, wrap='word',
            fg_color=ct['PANEL'], text_color=ct['TEXT'],
            border_width=1, border_color=ct['BORDER'],
            corner_radius=10, font=('Segoe UI', _scaled(11)))
        self.content_text.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        self.content_text.configure(state='disabled')

        # Interactive action frame (game-day bundle, press conferences).
        # Hidden unless the selected message carries an interactive action;
        # it shares the content_text slot.
        self.interactive_frame = ctk.CTkScrollableFrame(
            parent, fg_color=ct['PANEL'], border_width=1,
            border_color=ct['BORDER'], corner_radius=10)
        # Muck 2026-10-02: snappier wheel scrolling. CTkScrollableFrame
        # redraws every child widget on each scroll step; the game-day
        # bundle / pressers pack 30-100+ widgets, so each 30px step takes
        # 20-50ms (choppy). A 3x increment means 3x fewer steps.
        self._speed_up_scroll(self.interactive_frame)

        # Action buttons row
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.pack(fill='x', padx=12, pady=(0, 12))

        self.mark_read_btn = self._secondary_button(
            action_frame, text="Mark as Read",
            command=self._mark_current_read, width=120)
        self.mark_read_btn.pack(side='left', padx=(0, 6))

        self.reply_btn = self._secondary_button(
            action_frame, text="Reply",
            command=self._reply_to_current, width=90)
        self.reply_btn.pack(side='left', padx=3)

        self.delete_btn = self._secondary_button(
            action_frame, text="Delete",
            command=self._delete_current, width=90)
        self.delete_btn.pack(side='left', padx=3)

        # Save for later: pinned messages never auto-expire (headline news
        # otherwise leaves the inbox after 7 game-days).
        self.save_btn = self._secondary_button(
            action_frame, text="📌 Save",
            command=self._toggle_save_current, width=90)
        self.save_btn.pack(side='left', padx=3)

        # Special action button (initially hidden)
        self.special_action_btn = self._primary_button(
            action_frame, text="", command=None, width=180)
        # Don't pack initially - will be shown/hidden as needed

    def _build_player_name_index(self):
        """Build full_name -> player map from user team + league (cached per message)."""
        index = {}
        def add_players(players):
            for p in players or []:
                name = getattr(p, 'full_name', None)
                if name and name not in index:
                    index[name] = p
        app = self.app
        # User team first (takes precedence on name collisions)
        ut = getattr(app, 'user_team', None)
        if ut is not None:
            add_players(getattr(ut, 'roster', []))
            add_players(getattr(ut, 'ahl_roster', []))
            add_players(getattr(ut, 'prospects', []))
        # League-wide
        league = getattr(app, 'league', None)
        for team in getattr(league, 'teams', []) or []:
            add_players(getattr(team, 'roster', []))
            add_players(getattr(team, 'ahl_roster', []))
            add_players(getattr(team, 'prospects', []))
        return index

    def _tag_player_names(self):
        """Tag player names in message text; right-click opens the player menu.

        Names render underlined so users know they are interactive.
        """
        txt = self.content_text
        # Clear old player tags
        for tag in txt.tag_names():
            if tag.startswith("player-"):
                txt.tag_delete(tag)
        index = self._build_player_name_index()
        if not index:
            return
        # Longest names first so "John Smith Jr" wins over "John Smith"
        for name in sorted(index, key=len, reverse=True):
            player = index[name]
            start = "1.0"
            while True:
                pos = txt.search(name, start, stopindex=tk.END, nocase=False)
                if not pos:
                    break
                end = f"{pos}+{len(name)}c"
                tag = f"player-{getattr(player, 'id', id(player))}"
                # Skip if already tagged (overlap from a longer name)
                if tag in txt.tag_names(pos):
                    start = end
                    continue
                txt.tag_add(tag, pos, end)
                txt.tag_config(tag, underline=True,
                               foreground=getattr(self.app, 'ACCENT_COLOR', '#4FC3F7'))
                # Bind right-click on this specific tagged range
                def _show(event, p=player):
                    try:
                        PlayerContextMenu(self.app).show_context_menu(event, p)
                    except Exception:
                        pass
                txt.tag_bind(tag, "<Button-3>", _show)
                # Also bind Shift+F10 for keyboard access
                txt.tag_bind(tag, "<Shift-F10>", _show)
                start = end
        # Ensure the textbox itself doesn't swallow right-clicks elsewhere
        try:
            txt.bind("<Button-3>", lambda e: None)
        except Exception:
            pass

    def _create_toolbar(self, parent):
        """Create the bottom toolbar."""
        ct = self._ct
        toolbar_frame = ctk.CTkFrame(parent, fg_color=ct['PANEL'],
                                     corner_radius=10)
        toolbar_frame.pack(side='bottom', fill='x', pady=(12, 0))

        self._secondary_button(toolbar_frame, text="Compose",
                               command=self._compose_email,
                               width=110).pack(side='left', padx=(10, 4), pady=10)
        self._secondary_button(toolbar_frame, text="Mark All Read",
                               command=self._mark_all_read,
                               width=120).pack(side='left', padx=4, pady=10)
        self._secondary_button(toolbar_frame, text="Delete Read",
                               command=self._delete_read_messages,
                               width=110).pack(side='left', padx=4, pady=10)
        self._secondary_button(toolbar_frame, text="Refresh",
                               command=self._refresh_inbox,
                               width=100).pack(side='left', padx=4, pady=10)
        self._secondary_button(toolbar_frame, text="Close",
                               command=self._on_closing,
                               width=90).pack(side='right', padx=10, pady=10)

    def _create_context_menu(self):
        """Create context menu for email list."""
        ct = self._ct
        self.context_menu = tk.Menu(self, tearoff=0,
                                    bg=ct['PANEL'], fg=ct['TEXT'],
                                    activebackground=ct['ROW_SELECTED'],
                                    activeforeground=ct['TEXT'])

        self.context_menu.add_command(label="Mark as Read",
                                      command=self._mark_current_read)
        self.context_menu.add_command(label="Mark as Unread",
                                      command=self._mark_current_unread)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Reply",
                                      command=self._reply_to_current)
        self.context_menu.add_command(label="Forward",
                                      command=self._forward_current)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Mark as Important",
                                      command=self._mark_current_important)
        self.context_menu.add_command(label="📌 Save / Unsave",
                                      command=self._toggle_save_current)
        self.context_menu.add_command(label="Delete",
                                      command=self._delete_current)
        # (Right-click is bound per row in _bind_row_clicks.)

    def _show_context_menu(self, event):
        """Legacy context-menu entry point (kept for external callers)."""
        if self.selected_message is not None:
            try:
                self.context_menu.post(event.x_root, event.y_root)
            except Exception:
                pass

    def _show_row_context_menu(self, event, message):
        """Right-click on a Gmail-style row: select it, then show the menu."""
        try:
            self._select_message(message)
            self.context_menu.post(event.x_root, event.y_root)
        except Exception:
            pass

    def _populate_inbox(self):
        """Populate the inbox with Gmail-style rows."""
        self._clear_rows()
        for message in self.inbox.messages:
            self._add_message_row(message)
        self._update_stats()
        self._select_first_message()

    def _select_first_message(self):
        """Select the first message so the preview is never empty."""
        try:
            children = self._list_scroll.winfo_children()
        except Exception:
            children = []
        if children and self._row_messages:
            first_id = next(iter(self._row_messages))
            self._select_message(self._row_messages[first_id])

    def _apply_filter(self, filter_type: str):
        """Apply filter to the Gmail-style message list."""
        self._current_filter = filter_type
        self._paint_filter_pills()
        # Season Story view replaces the email list entirely.
        if filter_type == "story":
            self._show_story_view()
            return
        self._show_email_view()
        self._clear_rows()

        # Filter messages
        filtered_messages = []
        if filter_type == "all":
            filtered_messages = self.inbox.messages
        elif filter_type == "unread":
            filtered_messages = self.inbox.get_unread_messages()
        elif filter_type == "urgent":
            filtered_messages = self.inbox.get_urgent_messages()
        elif filter_type == "saved":
            filtered_messages = [m for m in self.inbox.messages
                                 if getattr(m, "is_saved", False)]
        else:
            # Category filter
            filtered_messages = self.inbox.get_messages_by_category(filter_type)

        # Populate with filtered messages
        for message in filtered_messages:
            self._add_message_row(message)
        self._select_first_message()
        self._update_stats()

    def _on_email_select(self, event=None):
        """Legacy selection entry point (kept for external callers)."""
        if self.selected_message is not None:
            self._display_message_preview(self.selected_message)

    def _on_row_double_click(self):
        """Double-click a row: mark as read and refresh."""
        if self.selected_message:
            if not self.selected_message.is_read:
                self.inbox.mark_message_read(self.selected_message.id)
                self._refresh_inbox()

    def _on_email_double_click(self, event=None):
        """Handle double-click on email (legacy signature)."""
        self._on_row_double_click()
    def _display_message_preview(self, message: EmailMessage):
        """Display message in the preview pane."""
        # Update header labels
        self.preview_from_label.configure(
            text=f"From: {message.sender} ({message.sender_type})")
        self.preview_subject_label.configure(
            text=f"Subject: {message.subject}")
        self.preview_date_label.configure(
            text=f"Date: {message.date_sent.strftime('%B %d, %Y')}")
        self.preview_category_label.configure(
            text=f"Category: {message.category}")

        # Interactive inbox actions (game-day bundle, press conferences)
        # render rich widgets in place of the plain text content.
        if getattr(message, 'action_type', None) in (
                "game_day", "postmatch_presser",
                "trade_offer", "trade_counter", "contract_counter",
                "rfa_qualifying", "offer_sheet_match",
                "offer_sheet_trade_alt",
                "arbitration_walkaway", "buyout_window",
                "staff_renewal", "media_fine_response"):
            self._show_interactive_action(message)
        else:
            self._hide_interactive_action()
            # Update content
            self.content_text.configure(state='normal')
            self.content_text.delete(1.0, tk.END)
            self.content_text.insert(1.0, message.content)
            self._tag_player_names()

            # Add response info if needed
            if message.requires_response:
                self.content_text.insert(tk.END, "\n\n--- RESPONSE REQUIRED ---")
                if message.response_deadline:
                    self.content_text.insert(
                        tk.END,
                        f"\nDeadline: {message.response_deadline.strftime('%B %d, %Y')}")
                if message.is_overdue():
                    self.content_text.insert(tk.END, "\nOVERDUE")

            # Headline retention note (FM24/EHM-style transparency)
            ttl = getattr(message, "news_ttl_days", None)
            if ttl is not None:
                if getattr(message, "is_milestone", False):
                    self.content_text.insert(
                        tk.END, "\n\n⭐ MILESTONE for your club -- kept "
                               "permanently.")
                elif getattr(message, "is_saved", False):
                    self.content_text.insert(
                        tk.END, "\n\n📌 SAVED by you -- kept until you "
                               "unsave or delete it.")
                else:
                    self.content_text.insert(
                        tk.END, f"\n\n📰 League news -- leaves your inbox "
                               f"after {ttl} days unless you save it.")

            self.content_text.configure(state='disabled')

        # Update button states
        self.mark_read_btn.configure(
            text="Mark as Unread" if message.is_read else "Mark as Read")
        self.reply_btn.configure(
            state='normal' if message.requires_response else 'disabled')
        self.save_btn.configure(
            text="📌 Unsave" if getattr(message, "is_saved", False)
            else "📌 Save")

        # Handle fantasy draft special button
        self._handle_fantasy_draft_button(message)

        # Handle draft-lottery reveal special button
        self._handle_lottery_reveal_button(message)

    def _toggle_save_current(self):
        """Pin/unpin the selected message ("save for later").

        Saved messages are exempt from the 7-day headline expiry.
        """
        if self.selected_message:
            self.selected_message.is_saved = not getattr(
                self.selected_message, "is_saved", False)
            self.save_btn.configure(
                text="📌 Unsave" if self.selected_message.is_saved
                else "📌 Save")
            self._refresh_inbox()

    def _mark_current_read(self):
        """Mark current message as read."""
        if self.selected_message:
            if not self.selected_message.is_read:
                self.inbox.mark_message_read(self.selected_message.id)
            else:
                # Mark as unread
                self.selected_message.is_read = False
                self.selected_message.date_read = None
                self.inbox.unread_count += 1
            self._refresh_inbox()

    def _mark_current_unread(self):
        """Mark current message as unread."""
        if self.selected_message and self.selected_message.is_read:
            self.selected_message.is_read = False
            self.selected_message.date_read = None
            self.inbox.unread_count += 1
            self._refresh_inbox()

    def _handle_fantasy_draft_button(self, message):
        """Handle showing/hiding the fantasy draft button based on message content."""
        # Check if this is a fantasy draft message
        if ("FANTASY DRAFT" in message.subject.upper() and
            message.sender_type == "League" and
            hasattr(self.app.game_manager, 'pending_fantasy_draft') and
            self.app.game_manager.pending_fantasy_draft):

            # Show fantasy draft button
            self.special_action_btn.configure(
                text="START FANTASY DRAFT",
                command=self._start_fantasy_draft
            )
            self.special_action_btn.pack(side='right', padx=5)
        else:
            # Hide the special button if it's not needed
            self.special_action_btn.pack_forget()

    def _handle_lottery_reveal_button(self, message):
        """Show WATCH THE REVEAL for the draft-lottery results card.

        Only ever shows; never hides -- the fantasy-draft handler owns the
        hide path so the two don't fight over the shared button.
        """
        pending = getattr(self.app.game_manager, '_pending_lottery_reveal', None)
        if ("DRAFT LOTTERY" in (message.subject or "").upper() and
                message.sender_type == "Media" and pending):
            self.special_action_btn.configure(
                text="WATCH THE REVEAL",
                command=self._watch_lottery_reveal,
            )
            self.special_action_btn.pack(side='right', padx=5)

    def _watch_lottery_reveal(self):
        """Open the televised lottery countdown from the inbox.

        Gating Phase 2: the reveal is a Tier-1 screen now (was a popup).
        """
        pending = getattr(self.app.game_manager, '_pending_lottery_reveal', None)
        if not pending:
            return
        try:
            from draft_lottery import LotteryRevealView

            def _clear(_p=pending):
                try:
                    if getattr(self.app.game_manager,
                               '_pending_lottery_reveal', None) is _p:
                        delattr(self.app.game_manager, '_pending_lottery_reveal')
                except Exception:
                    pass

            self.app.show_screen(
                "draft_lottery", f"NHL Draft Lottery {pending['year']}",
                LotteryRevealView, pending["year"], pending["rows"],
                on_done=_clear)
        except Exception:
            pass

    def _start_fantasy_draft(self):
        """Launch the fantasy draft from the inbox."""
        try:
            # Mark the message as read
            if self.selected_message and not self.selected_message.is_read:
                self.inbox.mark_message_read(self.selected_message.id)
                self._refresh_inbox()

            # Close inbox and launch fantasy draft
            self._on_closing()

            # Launch the fantasy draft window
            self.app.open_fantasy_draft_window()

        except Exception as e:
            messagebox.showerror("Error", f"Could not start fantasy draft: {e}")

    # ------------------------------------------------------------------
    # Interactive inbox actions: game-day bundle + press conferences.
    # These replace the old modal popups (presser dialog, team-talk
    # dialog, game-mode dialog) with widgets inside the inbox.
    # ------------------------------------------------------------------

    def focus_message(self, message_id) -> bool:
        """Select and display the message with the given id."""
        try:
            for mid, message in self._row_messages.items():
                if getattr(message, 'id', None) == message_id:
                    self._select_message(message)
                    row = self._row_widgets.get(mid)
                    if row is not None:
                        try:
                            self._list_scroll._parent_canvas.see(row)
                        except Exception:
                            pass
                    return True
        except Exception:
            pass
        return False

    def _show_interactive_action(self, message):
        """Swap the text content for the interactive action widgets."""
        self.content_text.pack_forget()
        self.interactive_frame.pack(fill='both', expand=True,
                                    padx=12, pady=(0, 8))
        for w in self.interactive_frame.winfo_children():
            w.destroy()
        if message.action_type == "game_day":
            self._render_game_day_bundle(message)
        elif message.action_type == "postmatch_presser":
            self._render_postmatch_presser(message)
        elif message.action_type in ("trade_offer", "trade_counter"):
            self._render_trade_negotiation(message)
        elif message.action_type == "contract_counter":
            self._render_contract_counter(message)
        elif message.action_type == "rfa_qualifying":
            self._render_rfa_qualifying(message)
        elif message.action_type == "offer_sheet_match":
            self._render_offer_sheet_match(message)
        elif message.action_type == "offer_sheet_trade_alt":
            self._render_offer_sheet_trade_alt(message)
        elif message.action_type == "arbitration_walkaway":
            self._render_arbitration_walkaway(message)
        elif message.action_type == "buyout_window":
            self._render_buyout_window(message)
        elif message.action_type == "staff_renewal":
            self._render_staff_renewal(message)
        elif message.action_type == "media_fine_response":
            self._render_media_fine_response(message)

    def _hide_interactive_action(self):
        """Restore the plain text content view."""
        try:
            self.interactive_frame.pack_forget()
        except Exception:
            pass
        try:
            self.content_text.pack(fill='both', expand=True,
                                   padx=12, pady=(0, 8))
        except Exception:
            pass

    def _action_section(self, title):
        ct = self._ct
        lbl = self._heading(self.interactive_frame, title, size=13,
                            wraplength=300, justify='left', anchor='w')
        lbl.pack(anchor='w', padx=10, pady=(12, 4))
        sep = ctk.CTkFrame(self.interactive_frame, height=1,
                           fg_color=ct['BORDER'])
        sep.pack(fill='x', padx=10, pady=(0, 6))
        return lbl

    def _iwrap(self, text, size=11, dim=False, bold=False, padx=14, pady=2):
        """Wrapped label for the interactive pane (preview is narrow)."""
        if bold:
            lbl = self._heading(self.interactive_frame, text, size=size,
                                wraplength=270, justify='left', anchor='w')
        else:
            lbl = self._body(self.interactive_frame, text, size=size, dim=dim,
                             wraplength=270, justify='left', anchor='w')
        lbl.pack(anchor='w', padx=padx, pady=pady)
        return lbl

    def _bind_name_label_menu(self, lbl, name):
        """EHM/FM24: right-click a player-name label -> player menu."""
        try:
            from player_context_menu import bind_player_context
            p = self._build_player_name_index().get(name)
            if lbl is not None and p is not None:
                bind_player_context(lbl, p, self)
        except Exception:
            pass

    def _bind_staff_name_menu(self, lbl, name):
        """EHM/FM24: right-click a staff-name label -> staff menu."""
        try:
            from player_context_menu import bind_staff_context
            st = None
            try:
                for s in getattr(getattr(self.app, 'user_team', None),
                                 'staff', []) or []:
                    if getattr(s, 'full_name', None) == name:
                        st = s
                        break
            except Exception:
                pass
            if lbl is not None and st is not None:
                bind_staff_context(lbl, st, self)
        except Exception:
            pass

    def _bind_asset_row_menu(self, lbl, asset_dict):
        """EHM/FM24: right-click a trade-asset row label -> player menu."""
        try:
            import trade_negotiation as tn
            from player_context_menu import bind_player_context
            objs, _ = tn.resolve_assets(self.app, [asset_dict])
            if objs and hasattr(objs[0], 'full_name'):
                bind_player_context(lbl, objs[0], self)
        except Exception:
            pass

    def _render_game_day_bundle(self, message):
        """Pre-match presser + team talk + Watch/Quick, all in the inbox."""
        data = message.action_data or {}
        app = self.app
        try:
            today = app.current_date.isoformat()
        except Exception:
            today = ""
        stale = bool(data.get("game_date")) and data.get("game_date") != today

        self._iwrap(f"GAME DAY: {data.get('away', '')} @ {data.get('home', '')}",
                    size=15, bold=True, padx=10, pady=(10, 2))
        self._iwrap(message.content or "", size=11, dim=True, padx=10, pady=(0, 4))

        if stale:
            self._iwrap("This game has already been played -- these options "
                        "are no longer available.", size=11, dim=True, padx=10)
            return

        # ---- Pre-match presser ----
        self._action_section("PRE-MATCH PRESSER")
        questions = data.get("presser") or []
        answered = data.get("presser_answered") or []
        reactions = data.get("presser_reactions") or {}
        all_answered = answered and all(answered)
        # Muck 2026-10-02: presser was too long -- offer a one-tap skip.
        if not all_answered and questions:
            self._secondary_button(
                self.interactive_frame, text="\u23e9 Skip presser",
                command=lambda m=message:
                    self._on_bundle_presser_skip(m)
            ).pack(anchor='w', padx=14, pady=(0, 4))
        if data.get("presser_skipped"):
            self._iwrap("\u2713 Skipped -- no comment for the press today.",
                        size=10, dim=True, pady=(0, 4))
        elif questions:
            for qi, q in enumerate(questions):
                is_answered = qi < len(answered) and answered[qi]
                self._iwrap(f"Q{qi + 1}: {q.get('question', '')}", size=11,
                            pady=(8, 2))
                self._iwrap(f"\u2014 {q.get('journalist', '')}", size=10, dim=True)
                if is_answered:
                    self._iwrap("\u2713 Answered", size=10, dim=True)
                    if reactions.get(qi):
                        self._iwrap(f"\u201C{reactions.get(qi)}\u201D",
                                    size=10, dim=True, pady=(0, 4))
                else:
                    for ai, ans in enumerate(q.get("answers") or []):
                        self._secondary_button(
                            self.interactive_frame, text=ans.get("label", ""),
                            command=lambda qi=qi, ai=ai, m=message:
                                self._on_bundle_presser_answer(m, qi, ai)
                        ).pack(anchor='w', padx=14, pady=2)

        # ---- Team talk ----
        self._action_section("DRESSING ROOM: TEAM TALK")
        talk_options = data.get("talk_options") or []
        chosen = data.get("talk_chosen")
        if chosen is not None:
            opt = talk_options[chosen] if 0 <= chosen < len(talk_options) else {}
            self._iwrap(f"\u2713 \u201C{opt.get('label', '')}\u201D",
                        size=11, pady=(4, 2))
            if data.get("talk_reaction"):
                self._iwrap(f"\u201C{data.get('talk_reaction')}\u201D",
                            size=10, dim=True, pady=(0, 4))
        else:
            self._iwrap("Rally the room before puck drop:",
                        size=11, dim=True, pady=(4, 2))
            for oi, opt in enumerate(talk_options):
                fit_note = {"good": " \u2713 looks ideal",
                            "risky": " \u26A0 risky"}.get(opt.get("fit"), "")
                self._secondary_button(
                    self.interactive_frame,
                    text=str(opt.get("label", "")) + fit_note,
                    command=lambda oi=oi, m=message:
                        self._on_bundle_team_talk(m, oi)
                ).pack(anchor='w', padx=14, pady=2)
                self._iwrap(f"\u201C{opt.get('text', '')}\u201D",
                            size=10, dim=True, padx=20)

        # ---- Coach's instruction (D1) ----
        self._action_section("COACH'S INSTRUCTION")
        instr_options = data.get("instruction_options") or []
        instr_chosen = data.get("instruction_chosen")
        if instr_chosen is not None:
            chosen_opt = next(
                (o for o in instr_options if o.get("id") == instr_chosen),
                {})
            self._iwrap(f"\u2713 \u201C{chosen_opt.get('label', '')}\u201D",
                        size=11, pady=(4, 2))
        else:
            self._iwrap("The bench's marching orders for tonight:",
                        size=11, dim=True, pady=(4, 2))
            for opt in instr_options:
                oid = opt.get("id")
                self._secondary_button(
                    self.interactive_frame,
                    text=str(opt.get("label", "")),
                    command=lambda oid=oid, m=message:
                        self._on_bundle_instruction(m, oid)
                ).pack(anchor='w', padx=14, pady=2)
                self._iwrap(f"\u201C{opt.get('text', '')}\u201D",
                            size=10, dim=True, padx=20)

        # ---- Watch / Quick ----
        self._action_section("HOW TO PLAY TONIGHT")
        btn_row = ctk.CTkFrame(self.interactive_frame, fg_color="transparent")
        btn_row.pack(fill='x', padx=10, pady=8)
        # Preseason exhibitions are never appointment viewing: the engine
        # quick-sims them and records no stats (main._resolve_game_day).
        # The button stays visible but disabled so the UI is honest about
        # the choice being unavailable instead of silently discarding it.
        is_preseason = self._is_preseason_game_day(app)
        watch_btn = self._primary_button(btn_row, text="\u25B6 WATCH LIVE",
                             width=200, height=44,
                             command=lambda: app._resolve_game_day(True)
                             )
        watch_btn.pack(side='left', padx=(0, 8))
        self._secondary_button(btn_row, text="\u26A1 QUICK SIM",
                               width=200, height=44,
                               command=lambda: app._resolve_game_day(False)
                               ).pack(side='left', padx=8)
        if is_preseason:
            # Disabled AND visibly dimmed: a disabled button that looks
            # identical to an enabled one fails the accessibility pass.
            watch_btn.configure(state="disabled", fg_color="#3d434e",
                                hover_color="#3d434e", text_color="#9aa0ab")
            self._iwrap("Preseason exhibitions aren't watchable -- they're "
                        "quick-simmed and no stats are recorded.",
                        size=10, dim=True, padx=14, pady=(0, 6))

    def _is_preseason_game_day(self, app):
        """True when today's user-team game is a preseason exhibition."""
        try:
            team = getattr(app, 'user_team', None)
            today = getattr(app, 'current_date', None)
            if team is None or today is None:
                return False
            for item in (getattr(getattr(app, 'league', None),
                                'schedule', None) or []):
                try:
                    if isinstance(item, dict):
                        d, h, a = (item.get("date"), item.get("home_team"),
                                   item.get("away_team"))
                    elif isinstance(item, (tuple, list)) and len(item) >= 3:
                        d, h, a = item[0], item[1], item[2]
                    else:
                        continue
                    if d == today and (h == team or a == team):
                        return bool(item.get("preseason")) \
                            if isinstance(item, dict) else False
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _render_postmatch_presser(self, message):
        """Post-match presser Q&A inside the inbox (non-blocking)."""
        data = message.action_data or {}
        self._iwrap("POST-MATCH PRESSER", size=15, bold=True,
                    padx=10, pady=(10, 2))
        self._iwrap(message.content or "", size=11, dim=True,
                    padx=10, pady=(0, 4))
        questions = data.get("questions") or []
        answered = data.get("answered") or []
        reactions = data.get("reactions") or {}
        for qi, q in enumerate(questions):
            is_answered = qi < len(answered) and answered[qi]
            self._iwrap(f"Q{qi + 1}: {q.get('question', '')}", size=11,
                        pady=(8, 2))
            self._iwrap(f"\u2014 {q.get('journalist', '')}", size=10, dim=True)
            if is_answered:
                self._iwrap("\u2713 Answered", size=10, dim=True)
                if reactions.get(qi):
                    self._iwrap(f"\u201C{reactions.get(qi)}\u201D",
                                size=10, dim=True, pady=(0, 4))
            else:
                for ai, ans in enumerate(q.get("answers") or []):
                    self._secondary_button(
                        self.interactive_frame, text=ans.get("label", ""),
                        command=lambda qi=qi, ai=ai, m=message:
                            self._on_postmatch_answer(m, qi, ai)
                    ).pack(anchor='w', padx=14, pady=2)
        if answered and all(answered):
            self._iwrap("Presser complete -- the story is filed.",
                        size=11, dim=True, padx=10, pady=10)

    # ------------------------------------------------------------------
    # Trade negotiation (FM24/EHM-style): offers and counters live in the
    # inbox. Nothing here is a blocking decision -- the user can read it,
    # close the inbox, and come back days later.
    # ------------------------------------------------------------------

    def _render_trade_negotiation(self, message):
        import trade_negotiation as tn
        app = self.app
        neg_id = (message.action_data or {}).get("negotiation_id")
        neg = tn.get_negotiation(app, neg_id) if neg_id else None

        self._iwrap("TRADE TALKS", size=15, bold=True, padx=10, pady=(10, 2))
        if neg is None or not neg.is_open:
            self._iwrap("This negotiation is no longer on the table.",
                        size=11, dim=True, padx=10)
            return

        is_counter = message.action_type == "trade_counter"
        self._iwrap(f"{neg.partner_team_name}  "
                    f"\u00b7  Round {neg.rounds}", size=11, dim=True, padx=10)
        if neg.last_message and is_counter:
            self._iwrap(f"\u201C{neg.last_message}\u201D", size=11,
                        padx=10, pady=(4, 2))
        if neg.patience < 0.7 and neg.is_open:
            self._iwrap("They are losing patience -- the next offer "
                        "should be your best.", size=10, dim=True, padx=10)

        self._action_section("THE DEAL ON THE TABLE")
        self._iwrap("YOU SEND:", size=10, dim=True, padx=10, pady=(2, 0))
        for ad in neg.user_assets or []:
            _albl = self._iwrap("\u2022 " + tn.asset_summary([ad]),
                                size=11, padx=18)
            self._bind_asset_row_menu(_albl, ad)
        self._iwrap("YOU GET:", size=10, dim=True, padx=10, pady=(6, 0))
        for ad in neg.partner_assets or []:
            _albl = self._iwrap("\u2022 " + tn.asset_summary([ad]),
                                size=11, padx=18)
            self._bind_asset_row_menu(_albl, ad)

        self._action_section("YOUR MOVE")
        btn_row = ctk.CTkFrame(self.interactive_frame, fg_color="transparent")
        btn_row.pack(anchor='w', padx=10, pady=6)
        if is_counter:
            self._secondary_button(
                btn_row, text="Review & Adjust",
                command=lambda m=message: self._on_trade_negotiate(m)
            ).pack(side='left', padx=(0, 8))
            self._primary_button(
                btn_row, text="Accept Counter",
                command=lambda m=message: self._on_trade_accept(m)
            ).pack(side='left', padx=(0, 8))
        else:
            self._secondary_button(
                btn_row, text="Negotiate",
                command=lambda m=message: self._on_trade_negotiate(m)
            ).pack(side='left', padx=(0, 8))
            self._primary_button(
                btn_row, text="Accept",
                command=lambda m=message: self._on_trade_accept(m)
            ).pack(side='left', padx=(0, 8))
        self._secondary_button(
            btn_row, text="Walk Away",
            command=lambda m=message: self._on_trade_decline(m)
        ).pack(side='left')
        self._iwrap("Close this inbox any time -- the offer waits for you.",
                    size=10, dim=True, padx=10, pady=(8, 0))

    def _trade_neg_from_message(self, message):
        import trade_negotiation as tn
        neg_id = (message.action_data or {}).get("negotiation_id")
        return tn.get_negotiation(self.app, neg_id) if neg_id else None

    def _on_trade_negotiate(self, message):
        import trade_negotiation as tn
        neg = self._trade_neg_from_message(message)
        if neg is None or not neg.is_open:
            return
        app = self.app
        try:
            user_objs, _ = tn.resolve_assets(app, neg.user_assets)
            partner_objs, _ = tn.resolve_assets(app, neg.partner_assets)
            partner = tn.find_team(app, neg.partner_team_name)
            preset = {"partner": partner,
                      "user_assets": user_objs,
                      "partner_assets": partner_objs,
                      "negotiation_id": neg.id,
                      "mode": "counter"}
            self._on_closing()
            app.open_trade_window(preset=preset)
        except Exception as e:
            print(f"trade negotiate failed: {e}")

    def _on_trade_accept(self, message):
        import trade_negotiation as tn
        neg = self._trade_neg_from_message(message)
        if neg is None:
            return
        try:
            tn.accept_negotiation(self.app, neg.id)
        except Exception as e:
            print(f"trade accept failed: {e}")
        message.action_done = True
        self._refresh_inbox()
        self._display_message_preview(message)

    def _on_trade_decline(self, message):
        import trade_negotiation as tn
        neg = self._trade_neg_from_message(message)
        if neg is None:
            return
        try:
            tn.decline_negotiation(self.app, neg.id)
        except Exception as e:
            print(f"trade decline failed: {e}")
        message.action_done = True
        self._refresh_inbox()
        self._display_message_preview(message)

    # -- contract counter-offers (FM24/EHM style agent replies) -------------
    def _render_contract_counter(self, message):
        data = message.action_data or {}
        name = data.get("player_name", "The player")
        asking = data.get("asking_price", 0)
        years = data.get("years", 1)

        self._iwrap("CONTRACT COUNTER-OFFER", size=15, bold=True,
                    padx=10, pady=(10, 2))
        if message.action_done:
            self._iwrap("This negotiation is closed.", size=11, dim=True,
                        padx=10)
            return
        _nm_lbl = self._iwrap(f"{name} rejected your offer but will sign for "
                              f"${asking:,} per year over {years} year(s).",
                              size=11, padx=10, pady=(4, 2))
        self._bind_name_label_menu(_nm_lbl, name)
        # Market-demand context (qualitative): same signal the negotiation
        # context box shows, read from action_data so the inbox path matches
        # the legacy popup path (UI-BUG-01).
        try:
            _ssig = str(data.get("scarcity_signal", "balanced"))
            if _ssig and _ssig != "balanced":
                from salary_cap_system import scarcity_signal_text as _sst
                self._iwrap("Market: " + _sst(_ssig, data.get("scarcity_pos")),
                            size=10, dim=True, padx=10, pady=(0, 2))
        except Exception:
            pass
        self._action_section("YOUR MOVE")
        btn_row = ctk.CTkFrame(self.interactive_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=6)
        # Vertical full-width buttons: the preview pane is narrow (~330px) and
        # a single row clips the third action.
        self._primary_button(
            btn_row, text=f"Accept ${asking:,}/yr",
            command=lambda m=message: self._on_contract_counter_accept(m)
        ).pack(fill="x", pady=(0, 8))
        self._secondary_button(
            btn_row, text="New Offer",
            command=lambda m=message: self._on_contract_counter_new_offer(m)
        ).pack(fill="x", pady=(0, 8))
        self._secondary_button(
            btn_row, text="Walk Away",
            command=lambda m=message: self._on_contract_counter_walkaway(m)
        ).pack(fill="x")
        self._iwrap("Close this inbox any time -- the offer waits for you.",
                    size=10, dim=True, padx=10, pady=(6, 0))

    def _on_contract_counter_accept(self, message):
        try:
            self.app.accept_contract_counter(message)
        except Exception as e:
            print(f"contract counter accept failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    def _on_contract_counter_new_offer(self, message):
        try:
            self.app.reopen_contract_negotiation(message)
        except Exception as e:
            print(f"contract counter new offer failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    def _on_contract_counter_walkaway(self, message):
        message.action_done = True
        self._refresh_inbox()
        self._display_message_preview(message)

    # ---------- RFA: qualifying offers ----------
    def _render_rfa_qualifying(self, message):
        """Per-RFA Qualify / Don't qualify buttons (rfa_system)."""
        data = message.action_data or {}
        cards = data.get("cards", []) or []
        decided = data.get("decided", {}) or {}
        self._iwrap("QUALIFYING OFFERS", size=15, bold=True,
                    padx=10, pady=(10, 2))
        if message.action_done:
            self._iwrap("All qualifying decisions are in.", size=11, dim=True,
                        padx=10)
            return
        remaining = [c for c in cards if str(c.get("player_id")) not in decided]
        if not remaining:
            message.action_done = True
            self._iwrap("All qualifying decisions are in.", size=11, dim=True,
                        padx=10)
            return
        for c in remaining:
            pid = str(c.get("player_id"))
            name = c.get("name", "Unknown")
            qo = c.get("qo_amount", 0)
            prior = c.get("prior_salary", 0)
            _rfa_hdr = self._action_section(name.upper())
            self._bind_name_label_menu(_rfa_hdr, name)
            self._iwrap(f"Qualifying offer: ${qo:,}  (was ${prior:,})",
                        size=11, padx=10, pady=(2, 4))
            btn_row = ctk.CTkFrame(self.interactive_frame,
                                   fg_color="transparent")
            btn_row.pack(fill="x", padx=10, pady=(0, 4))
            self._primary_button(
                btn_row, text=f"Extend QO ${qo:,}",
                command=lambda m=message, p=pid:
                    self._on_rfa_qualify(m, p, True),
            ).pack(fill="x", pady=(0, 6))
            self._secondary_button(
                btn_row, text="Don't qualify (walks as UFA)",
                command=lambda m=message, p=pid:
                    self._on_rfa_qualify(m, p, False),
            ).pack(fill="x")
        self._iwrap("Qualifying keeps his rights; declining makes him a UFA.",
                    size=10, dim=True, padx=10, pady=(6, 0))

    def _on_rfa_qualify(self, message, player_id, qualify):
        try:
            self.app.apply_rfa_qualifying_decision(message, player_id, qualify)
        except Exception as e:
            print(f"rfa qualify failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    # ---------- Buyout window ----------
    def _render_buyout_window(self, message):
        """Per-candidate Buy out / Keep buttons (buyout_window)."""
        data = message.action_data or {}
        self._iwrap("BUYOUT WINDOW — JUNE 15-30", size=15, bold=True,
                    padx=10, pady=(10, 2))
        if message.action_done:
            self._iwrap("The window has closed.", size=11, dim=True, padx=10)
            return
        cards = data.get("cards", []) or []
        decided = data.get("decided", {}) or {}
        remaining = [c for c in cards
                     if str(c.get("player_id")) not in decided]
        if not remaining:
            message.action_done = True
            self._iwrap("All buyout decisions are in.", size=11, dim=True,
                        padx=10)
            return
        for c in remaining:
            pid = str(c.get("player_id"))
            name = c.get("name", "Unknown")
            flag = "  ⚠️ DEAD WEIGHT" if c.get("dead_weight") else ""
            _hdr = self._action_section(f"{name.upper()}{flag}")
            # EHM/FM24: right-click the candidate name -> player menu.
            self._bind_name_label_menu(_hdr, name)
            self._iwrap(
                f"Age {c.get('age')} • {c.get('overall')} ovr • "
                f"${c.get('cap_hit'):,}/yr × {c.get('years_left')} left",
                size=11, padx=10, pady=(2, 2))
            self._iwrap(
                f"Buyout: ${c.get('buyout_cost'):,} total → "
                f"${c.get('annual_dead'):,}/yr dead cap × "
                f"{c.get('dead_years')} yrs. "
                f"Saves ${c.get('savings_y1'):,} this season.",
                size=11, padx=10, pady=(0, 4))
            btn_row = ctk.CTkFrame(self.interactive_frame,
                                   fg_color="transparent")
            btn_row.pack(fill="x", padx=10, pady=(0, 4))
            self._primary_button(
                btn_row,
                text=f"Buy out ({name.split()[-1]})",
                command=lambda m=message, p=pid:
                    self._on_buyout_decide(m, p, True),
            ).pack(fill="x", pady=(0, 6))
            self._secondary_button(
                btn_row, text="Keep him",
                command=lambda m=message, p=pid:
                    self._on_buyout_decide(m, p, False),
            ).pack(fill="x")
        self._iwrap("Buyouts clear cap now but leave dead money for "
                    "years. Undecided players stay put.",
                    size=10, dim=True, padx=10, pady=(6, 0))

    def _on_buyout_decide(self, message, player_id, buyout):
        try:
            self.app.apply_buyout_decision(message, player_id, buyout)
        except Exception as e:
            print(f"buyout decide failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    # ---------- Staff renewals (D5 follow-up) ----------
    def _render_staff_renewal(self, message):
        """Per-staffer Re-sign (1/2/3 yr) / Let walk buttons
        (staff_renewal)."""
        data = message.action_data or {}
        self._iwrap("STAFF CONTRACT RENEWALS", size=15, bold=True,
                    padx=10, pady=(10, 2))
        if message.action_done:
            self._iwrap("All renewal decisions are in.", size=11, dim=True,
                        padx=10)
            return
        offers = data.get("offers", []) or []
        decided = data.get("decided", {}) or {}
        remaining = [o for o in offers
                     if str(o.get("staff_id")) not in decided]
        if not remaining:
            message.action_done = True
            self._iwrap("All renewal decisions are in.", size=11, dim=True,
                        padx=10)
            return
        for o in remaining:
            sid = str(o.get("staff_id"))
            name = o.get("name", "Unknown")
            role = o.get("role", "staffer")
            _st_hdr = self._action_section(f"{name.upper()} — {role.upper()}")
            self._bind_staff_name_menu(_st_hdr, name)
            self._iwrap(
                f"Age {o.get('age')} • career standing "
                f"{o.get('reputation')}/100 • "
                f"{o.get('years_with_team', 0)} yrs with the club • "
                f"${o.get('salary', 0):,}/yr",
                size=11, padx=10, pady=(2, 2))
            self._iwrap(
                "His deal expired. Re-sign him now on a fresh deal "
                "(same role, same salary) or let him walk to the "
                "free-agent pool.",
                size=11, padx=10, pady=(0, 4))
            btn_row = ctk.CTkFrame(self.interactive_frame,
                                   fg_color="transparent")
            btn_row.pack(fill="x", padx=10, pady=(0, 4))
            for yrs in (1, 3):
                self._secondary_button(
                    btn_row,
                    text=f"Re-sign × {yrs} yr",
                    command=lambda m=message, s=sid, y=yrs:
                        self._on_staff_renewal_decide(m, s, y),
                ).pack(fill="x", pady=(0, 6))
            self._primary_button(
                btn_row,
                text=f"Re-sign × 2 yrs (recommended)",
                command=lambda m=message, s=sid:
                    self._on_staff_renewal_decide(m, s, 2),
            ).pack(fill="x", pady=(0, 6))
            self._secondary_button(
                btn_row, text="Let him walk",
                command=lambda m=message, s=sid:
                    self._on_staff_renewal_decide(m, s, None),
            ).pack(fill="x")
        self._iwrap("Undecided staff walk to the pool when the new "
                    "season starts.",
                    size=10, dim=True, padx=10, pady=(6, 0))

    def _on_staff_renewal_decide(self, message, staff_id, years):
        try:
            self.app.apply_staff_renewal_decision(message, staff_id, years)
        except Exception as e:
            print(f"staff renewal decide failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    # ---------- League fine response (Wave C D36) ----------
    def _render_media_fine_response(self, message):
        """A league fine landed on a human-managed club: the GM answers
        for it -- Appeal (25% the league halves it) or Accept and move on.
        Performative only: no cap teeth, per Muck's call."""
        data = message.action_data or {}
        self._iwrap("LEAGUE FINE", size=15, bold=True,
                    padx=10, pady=(10, 2))
        try:
            my_team = getattr(getattr(self.app, "user_team", None),
                              "team_name", "")
        except Exception:
            my_team = ""
        name = data.get("fine_name", "")
        team = data.get("fine_team", "")
        amount = data.get("fine_amount", 0) or 0
        reason = data.get("fine_reason", "")
        self._iwrap(f"{name} ({team})", size=12, bold=True, padx=10)
        self._iwrap(f"${int(amount):,} -- {reason}", size=11, padx=10,
                    pady=(0, 4))
        if message.action_done or data.get("responded"):
            self._iwrap(data.get("outcome", "This fine has been answered."),
                        size=11, padx=10, pady=(4, 0))
            return
        if team != my_team:
            self._iwrap("Not your club's fine -- nothing for you to answer "
                        "for.", size=11, dim=True, padx=10)
            return
        self._action_section("YOUR RESPONSE")
        self._iwrap("The league office awaits your answer. An appeal works "
                    "about one time in four -- and the head office remembers "
                    "who complains.", size=10, dim=True, padx=10, pady=(0, 4))
        btn_row = ctk.CTkFrame(self.interactive_frame,
                               fg_color="transparent")
        btn_row.pack(anchor='w', padx=10, pady=6)
        self._secondary_button(
            btn_row, text="Appeal the fine",
            command=lambda m=message:
                self._on_fine_response(m, "appeal"),
        ).pack(side='left', padx=(0, 8))
        self._primary_button(
            btn_row, text="Accept and move on",
            command=lambda m=message:
                self._on_fine_response(m, "accept"),
        ).pack(side='left')

    def _on_fine_response(self, message, choice):
        import media_engine
        try:
            outcome = media_engine.resolve_fine_appeal(
                self.app, message.action_data or {}, choice)
            message.action_data["outcome"] = outcome
            message.action_done = True
        except Exception as e:
            print(f"fine response failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    # ---------- RFA: offer-sheet match ----------
    def _render_offer_sheet_match(self, message):
        data = message.action_data or {}
        self._iwrap("OFFER SHEET", size=15, bold=True, padx=10, pady=(10, 2))
        if message.action_done:
            self._iwrap("Decision made.", size=11, dim=True, padx=10)
            return
        aav = data.get("aav", 0)
        years = data.get("years", 1)
        comp = data.get("compensation", "")
        self._iwrap(f"${aav:,}/yr x {years}y.", size=12, bold=True,
                    padx=10, pady=(2, 2))
        self._iwrap(f"Decline and take: {comp}", size=11, padx=10, pady=(0, 2))
        self._iwrap("Matching keeps him at these terms -- he can't be "
                    "traded for a year without his consent.",
                    size=10, dim=True, padx=10, pady=(0, 4))
        btn_row = ctk.CTkFrame(self.interactive_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=6)
        self._primary_button(
            btn_row, text="Match the offer sheet",
            command=lambda m=message: self._on_offer_sheet_match(m, True),
        ).pack(fill="x", pady=(0, 8))
        self._secondary_button(
            btn_row, text="Decline, take the picks",
            command=lambda m=message: self._on_offer_sheet_match(m, False),
        ).pack(fill="x")

    def _on_offer_sheet_match(self, message, match):
        try:
            self.app.apply_offer_sheet_match_decision(message, match)
        except Exception as e:
            print(f"offer sheet match failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    def _render_offer_sheet_trade_alt(self, message):
        data = message.action_data or {}
        self._iwrap("TRADE ALTERNATIVE", size=15, bold=True, padx=10,
                    pady=(10, 2))
        if message.action_done:
            self._iwrap("Decision made.", size=11, dim=True, padx=10)
            return
        aav = data.get("aav", 0)
        years = data.get("years", 1)
        comp = data.get("compensation", "")
        pkg_ids = data.get("package_player_ids") or []
        pkg_val = data.get("package_value", 0)
        self._iwrap(f"${aav:,}/yr x {years}y.", size=12, bold=True,
                    padx=10, pady=(2, 2))
        self._iwrap(f"Trade offer: {len(pkg_ids)} player(s) "
                    f"(~${pkg_val:,} trade value) instead of: {comp}",
                    size=11, padx=10, pady=(0, 2))
        self._iwrap("Accepting trades his rights for the package -- the "
                    "picks stay with the offering club. Declining takes "
                    "the pick compensation, exactly as the original "
                    "decline.",
                    size=10, dim=True, padx=10, pady=(0, 4))
        btn_row = ctk.CTkFrame(self.interactive_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=6)
        self._primary_button(
            btn_row, text="Accept the trade",
            command=lambda m=message: self._on_offer_sheet_trade_alt(
                m, True),
        ).pack(fill="x", pady=(0, 8))
        self._secondary_button(
            btn_row, text="Decline, take the picks",
            command=lambda m=message: self._on_offer_sheet_trade_alt(
                m, False),
        ).pack(fill="x")

    def _on_offer_sheet_trade_alt(self, message, accept):
        try:
            self.app.apply_offer_sheet_trade_alt_decision(message, accept)
        except Exception as e:
            print(f"offer sheet trade alternative failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)

    # ---------- RFA: arbitration walk-away ----------
    def _render_arbitration_walkaway(self, message):
        data = message.action_data or {}
        self._iwrap("ARBITRATION WALK-AWAY WINDOW", size=15, bold=True,
                    padx=10, pady=(10, 2))
        if message.action_done:
            self._iwrap("Decision made.", size=11, dim=True, padx=10)
            return
        aav = data.get("award_aav", 0)
        term = data.get("term_years", 1)
        self._iwrap(f"Award: ${aav:,}/yr x {term}y.", size=12, bold=True,
                    padx=10, pady=(2, 2))
        self._iwrap("Walk away within 48 hours and he becomes a UFA. "
                    "Otherwise the award is binding.",
                    size=10, dim=True, padx=10, pady=(0, 4))
        btn_row = ctk.CTkFrame(self.interactive_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=6)
        self._primary_button(
            btn_row, text="Accept the award",
            command=lambda m=message: self._on_arbitration_walkaway(m, False),
        ).pack(fill="x", pady=(0, 8))
        self._secondary_button(
            btn_row, text="Walk away (becomes UFA)",
            command=lambda m=message: self._on_arbitration_walkaway(m, True),
        ).pack(fill="x")

    def _on_arbitration_walkaway(self, message, walk_away):
        try:
            self.app.apply_arbitration_walkaway_decision(message, walk_away)
        except Exception as e:
            print(f"arbitration walkaway failed: {e}")
        self._refresh_inbox()
        self._display_message_preview(message)


    def _on_bundle_presser_answer(self, message, qi, ai):
        try:
            self.app._answer_bundle_presser(message, qi, ai)
        except Exception:
            pass
        self._show_interactive_action(message)

    def _on_bundle_presser_skip(self, message):
        """Muck 2026-10-02: one-tap skip for a presser that's too long."""
        try:
            self.app._skip_bundle_presser(message)
        except Exception:
            pass
        self._show_interactive_action(message)

    def _on_bundle_team_talk(self, message, oi):
        try:
            self.app._answer_bundle_team_talk(message, oi)
        except Exception:
            pass
        self._show_interactive_action(message)

    def _on_bundle_instruction(self, message, opt_id):
        try:
            self.app._answer_bundle_instruction(message, opt_id)
        except Exception:
            pass
        self._show_interactive_action(message)

    def _on_postmatch_answer(self, message, qi, ai):
        try:
            self.app._answer_postmatch_presser(message, qi, ai)
        except Exception:
            pass
        self._show_interactive_action(message)

    def _mark_current_important(self):
        """Toggle important status of current message."""
        if self.selected_message:
            self.selected_message.is_important = not self.selected_message.is_important
            self._refresh_inbox()

    def _delete_current(self):
        """Delete current message."""
        if not self.selected_message:
            return

        def _do_delete():
            self.inbox.delete_message(self.selected_message.id)
            self.selected_message = None
            self._clear_preview()
            self._refresh_inbox()

        # Gating T2-Phase 3: non-modal confirm; dismiss = keep the message.
        confirm_card(self, "Delete Message",
                     "Are you sure you want to delete this message?",
                     on_yes=_do_delete)

    def _reply_to_current(self):
        """Reply to the current message via a real editor.

        Send appends the reply to the inbox message store; the original
        is marked read and its response requirement cleared.
        """
        message = self.selected_message
        if not message:
            return
        subject = message.subject or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        app = self.app

        def _on_sent(msg, _to):
            self.inbox.add_message(msg)
            try:
                message.requires_response = False
            except Exception:
                pass
            try:
                self.inbox.mark_message_read(message.id)
            except Exception:
                pass
            self._refresh_inbox()
            self.focus_message(msg.id)

        _MessageEditor(self, app, title="Reply",
                       to_value=message.sender or "", to_locked=True,
                       subject_value=subject,
                       category=message.category or "General",
                       on_sent=_on_sent)

    def _forward_current(self):
        """Forward the current message via a real editor (quoted body)."""
        message = self.selected_message
        if not message:
            return
        subject = message.subject or ""
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"
        quoted = (f"--- Forwarded message ---\n"
                  f"From: {message.sender or ''}\n"
                  f"Date: {message.date_sent}\n"
                  f"Subject: {message.subject or ''}\n\n"
                  f"{message.content or ''}")
        app = self.app

        def _on_sent(msg, _to):
            self.inbox.add_message(msg)
            self._refresh_inbox()
            self.focus_message(msg.id)

        _MessageEditor(self, app, title="Forward message",
                       subject_value=subject, body_value=quoted,
                       category=message.category or "General",
                       on_sent=_on_sent)

    def _compose_email(self):
        """Compose a new message via a real editor."""
        app = self.app

        def _on_sent(msg, _to):
            self.inbox.add_message(msg)
            self._refresh_inbox()
            self.focus_message(msg.id)

        _MessageEditor(self, app, title="Compose message",
                       category="General", on_sent=_on_sent)

    def _mark_all_read(self):
        """Mark all messages as read."""
        def _do_mark():
            self.inbox.mark_all_read()
            self._refresh_inbox()

        # Gating T2-Phase 3: non-modal confirm; dismiss = keep unread.
        confirm_card(self, "Mark All Read", "Mark all messages as read?",
                     on_yes=_do_mark)

    def _delete_read_messages(self):
        """Delete all read messages."""
        read_messages = [msg for msg in self.inbox.messages if msg.is_read]
        if not read_messages:
            messagebox.showinfo("Delete Read", "No read messages to delete.")
            return

        def _do_delete():
            for message in read_messages:
                self.inbox.delete_message(message.id)
            self._refresh_inbox()

        # Gating T2-Phase 3: non-modal confirm; dismiss = keep them.
        confirm_card(self, "Delete Read",
                     f"Delete {len(read_messages)} read messages?",
                     on_yes=_do_delete)

    def _refresh_inbox(self):
        """Refresh the inbox display, preserving the active filter."""
        self._apply_filter(getattr(self, '_current_filter', 'all'))
        if hasattr(self.app, 'update_inbox_notification'):
            self.app.update_inbox_notification()

    def _clear_preview(self):
        """Clear the message preview pane."""
        self.preview_from_label.configure(text="From: ")
        self.preview_subject_label.configure(text="Subject: ")
        self.preview_date_label.configure(text="Date: ")
        self.preview_category_label.configure(text="Category: ")

        self.content_text.configure(state='normal')
        self.content_text.delete(1.0, tk.END)
        self.content_text.configure(state='disabled')

        self.mark_read_btn.configure(text="Mark as Read", state='disabled')
        self.reply_btn.configure(state='disabled')

    def _update_stats(self):
        """Update inbox statistics."""
        total = len(self.inbox.messages)
        unread = self.inbox.unread_count
        urgent = len(self.inbox.get_urgent_messages())
        overdue = len(self.inbox.get_overdue_messages())

        stats_text = f"Total: {total} | Unread: {unread}"
        if urgent > 0:
            stats_text += f" | Urgent: {urgent}"
        if overdue > 0:
            stats_text += f" | Overdue: {overdue}"

        self.stats_label.configure(text=stats_text)

        # Refresh per-filter unread badges
        self._update_filter_badges()

    # ------------------------------------------------------------------
    # Season Story view (Muck 2026-10-02)
    #
    # A unified chronological narrative surface inside the inbox,
    # EHM/FM-style: the inbox is where the season story unfolds. Pulls
    # together active storylines, rivalry heat, milestones, the league
    # digest and past-season context into one readable narrative.
    # Every data access is guarded -- old/odd saves degrade to empty
    # sections, never crashes.
    # ------------------------------------------------------------------
    _STORY_KIND_ICONS = {
        'cup_window': '🏆', 'legacy_chase': '⏳', 'prospect_watch': '🌱',
        'trust_process': '🧱', 'hot_seat': '🪑', 'trade_rumor': '🔄',
        'goalie': '🥅', 'leadership': '🎖️', 'deadline_race': '🏁',
    }

    def _show_story_view(self):
        """Swap the email list/preview for the Season Story narrative."""
        for attr in ('_list_frame', '_preview_frame'):
            try:
                getattr(self, attr).grid_remove()
            except Exception:
                pass
        try:
            self._story_frame.grid()
        except Exception:
            pass
        self._populate_season_story()
        try:
            self._update_filter_badges()
        except Exception:
            pass

    def _show_email_view(self):
        """Restore the email list/preview (no-op when already shown)."""
        try:
            self._story_frame.grid_remove()
        except Exception:
            pass
        for attr in ('_list_frame', '_preview_frame'):
            try:
                getattr(self, attr).grid()
            except Exception:
                pass

    def _story_ctx(self):
        """Best-effort (game_manager, league, user_team, current_date)."""
        gm = league = team = now = None
        try:
            gm = getattr(self.app, 'game_manager', None)
        except Exception:
            gm = None
        try:
            league = getattr(gm, 'league', None) if gm is not None else None
        except Exception:
            league = None
        try:
            team = getattr(self.app, 'user_team', None)
        except Exception:
            team = None
        try:
            now = getattr(gm, 'current_date', None)
        except Exception:
            now = None
        return gm, league, team, now

    def _collect_developing(self):
        """Live narrative state: active storylines + hot rivalries."""
        items = []
        gm, league, team, now = self._story_ctx()
        # 1. media narratives (media_engine.Narrative)
        try:
            for n in (getattr(league, 'media_narratives', None) or []):
                try:
                    heat = float(getattr(n, 'heat', 0) or 0)
                    kind = str(getattr(n, 'kind', '') or '')
                    items.append({
                        'icon': self._STORY_KIND_ICONS.get(kind, '📰'),
                        'title': str(getattr(n, 'title', 'Developing storyline') or ''),
                        'desc': f"{getattr(n, 'team_name', '')} · heat {heat:.0f}/100",
                        'heat': heat,
                    })
                except Exception:
                    continue
        except Exception:
            pass
        # 2. media-system storylines (MediaStoryline, date-bound)
        try:
            ms = getattr(gm, 'media_system', None) if gm is not None else None
            for s in (getattr(ms, 'storylines', None) or []):
                try:
                    try:
                        active = s.is_active(now) if now is not None else True
                    except Exception:
                        active = True
                    if not active:
                        continue
                    inten = int(getattr(s, 'intensity', 5) or 5)
                    stype = getattr(getattr(s, 'type', None), 'value', '') or ''
                    desc = f"intensity {inten}/10" + (f" · {stype}" if stype else '')
                    items.append({
                        'icon': '📰',
                        'title': str(getattr(s, 'title', '') or 'Storyline'),
                        'desc': desc,
                        'heat': inten * 10.0,
                    })
                except Exception:
                    continue
        except Exception:
            pass
        # 3. hot rivalries (team_team, intensity >= 50)
        try:
            import reputation_system as _rs  # noqa: F401 (namespace pin)
            rivs = getattr(league, 'rivalries', None) or []
            seen = set()
            for r in rivs:
                try:
                    if not isinstance(r, dict):
                        continue
                    if r.get('kind') != 'team_team':
                        continue
                    heat = float(r.get('intensity', 0) or 0)
                    if heat < 50:
                        continue
                    key = (r.get('a'), r.get('b'))
                    if key in seen:
                        continue
                    seen.add(key)
                    an = r.get('a_name') or '?'
                    bn = r.get('b_name') or '?'
                    label = 'Bad blood' if heat >= 65 else 'Heated'
                    origin = r.get('origin') or ''
                    desc = f"{label} · {heat:.0f}/100" + (f" · {origin}" if origin else '')
                    items.append({'icon': '🔥', 'title': f"{an} vs {bn}",
                                  'desc': desc, 'heat': heat})
                except Exception:
                    continue
        except Exception:
            pass
        items.sort(key=lambda d: d.get('heat', 0), reverse=True)
        return items[:8]

    def _collect_story_feed(self, limit=80):
        """Chronological backbone: recent Media/League inbox messages."""
        out = []
        try:
            msgs = [m for m in (getattr(self.inbox, 'messages', None) or [])
                    if getattr(m, 'category', '') in ('Media', 'League')]
        except Exception:
            return out

        def _d(m):
            try:
                return (getattr(m, 'game_date_sent', None)
                        or getattr(m, 'date_sent', None))
            except Exception:
                return None

        try:
            msgs.sort(key=lambda m: (_d(m) is not None, _d(m)), reverse=True)
        except Exception:
            pass
        for m in msgs[:limit]:
            try:
                d = _d(m)
                subj = str(getattr(m, 'subject', '') or '')
                low = subj.lower()
                if (getattr(m, 'is_milestone', False) or 'milestone' in low
                        or 'record' in low):
                    icon = '⭐'
                elif 'around the league' in low:
                    icon = '🌐'
                elif 'bad blood' in low or 'rivalry' in low:
                    icon = '🔥'
                elif getattr(m, 'category', '') == 'League':
                    icon = '📢'
                else:
                    icon = '🎙️'
                snippet = str(getattr(m, 'content', '') or '').replace('\n', ' ').strip()
                if len(snippet) > 150:
                    snippet = snippet[:147] + '...'
                out.append({'date': d, 'icon': icon, 'subject': subj,
                            'snippet': snippet,
                            'sender': str(getattr(m, 'sender', '') or '')})
            except Exception:
                continue
        return out

    def _collect_history_lines(self, count=4):
        """Past-season context from LeagueHistory (newest first)."""
        lines = []
        try:
            gm, league, team, now = self._story_ctx()
            lh = getattr(gm, 'league_history', None)
            seasons = list(getattr(lh, 'seasons', None) or [])
            tname = getattr(team, 'team_name', '') or ''
            for s in reversed(seasons[-count:]):
                try:
                    if not isinstance(s, dict):
                        continue
                    yr = s.get('year', '?')
                    champ = s.get('champion') or '—'
                    runner = s.get('runner_up') or ''
                    text = f"{yr}: {champ} champions" + (f" over {runner}" if runner else '')
                    lines.append({'text': text, 'mine': champ == tname and bool(tname)})
                except Exception:
                    continue
        except Exception:
            pass
        return lines

    def _story_hook(self):
        """One-line narrative framing for the season header."""
        try:
            gm, league, team, now = self._story_ctx()
            tname = getattr(team, 'team_name', '') or 'your team'
            year = getattr(league, 'season_year', '') or ''
            title = f"📖 {tname} — {year} Season Story" if year else "📖 Season Story"
            lh = getattr(gm, 'league_history', None)
            seasons = list(getattr(lh, 'seasons', None) or [])
            last_cup = None
            for s in reversed(seasons):
                try:
                    if isinstance(s, dict) and s.get('champion') == tname:
                        last_cup = s.get('year')
                        break
                except Exception:
                    continue
            if seasons and isinstance(seasons[-1], dict) \
                    and seasons[-1].get('champion') == tname:
                hook = "Defending the crown. All 31 teams are coming for you."
            elif last_cup is not None:
                try:
                    n = int(str(year)[:4]) - int(last_cup)
                    if n > 0:
                        hook = (f"It's been {n} year{'s' if n != 1 else ''} since "
                                f"{tname} lifted the Cup. The clock is ticking.")
                    else:
                        hook = f"{tname} are champions. The encore starts now."
                except Exception:
                    hook = f"{tname} have tasted glory before. Time to chase it again."
            else:
                hook = (f"No banners yet in the {tname} rafters. "
                        "Every dynasty starts with a season like this one.")
            return title, hook
        except Exception:
            return "📖 Season Story", "Every season tells a story. This is yours."

    def _story_badge_count(self):
        try:
            return len(self._collect_developing())
        except Exception:
            return 0

    def _populate_season_story(self):
        """Build the Season Story view. Never raises."""
        ct = self._ct
        frame = self._story_frame
        try:
            for w in frame.winfo_children():
                w.destroy()
        except Exception:
            return
        try:
            # -- header ------------------------------------------------
            title, hook = self._story_hook()
            head = ctk.CTkFrame(frame, fg_color=ct['PANEL'], corner_radius=10)
            head.pack(fill='x', padx=10, pady=(10, 8))
            self._heading(head, title, size=17).pack(anchor='w', padx=14, pady=(10, 2))
            self._body(head, hook, size=12, dim=True).pack(anchor='w', padx=14, pady=(0, 10))

            # -- developing now ----------------------------------------
            developing = self._collect_developing()
            self._heading(frame, "🔥 Developing now", size=14).pack(
                anchor='w', padx=14, pady=(6, 4))
            if not developing:
                self._body(frame,
                           "Nothing simmering yet — the season is young. "
                           "Storylines ignite from games, trades and streaks.",
                           size=11, dim=True).pack(anchor='w', padx=18, pady=(0, 6))
            for it in developing:
                card = ctk.CTkFrame(frame, fg_color=ct['CARD'], corner_radius=8,
                                    border_width=1, border_color=ct['BORDER'])
                card.pack(fill='x', padx=12, pady=4)
                row = ctk.CTkFrame(card, fg_color='transparent')
                row.pack(fill='x', padx=10, pady=(8, 2))
                self._body(row, f"{it['icon']}  {it['title']}", size=12,
                           bold=True).pack(side='left')
                heat = it.get('heat')
                if heat:
                    bar = ctk.CTkProgressBar(row, width=110, height=8,
                                             progress_color=ct['GOLD'])
                    bar.pack(side='right', padx=(8, 0))
                    try:
                        bar.set(max(0.0, min(1.0, float(heat) / 100.0)))
                    except Exception:
                        pass
                self._body(card, it.get('desc', ''), size=11, dim=True).pack(
                    anchor='w', padx=14, pady=(0, 8))

            # -- the story so far --------------------------------------
            feed = self._collect_story_feed()
            self._heading(frame, "📅 The story so far", size=14).pack(
                anchor='w', padx=14, pady=(10, 4))
            if not feed:
                self._body(frame,
                           "No league stories in your inbox yet. "
                           "Headlines land here as the season unfolds.",
                           size=11, dim=True).pack(anchor='w', padx=18, pady=(0, 6))
            last_month = None
            for e in feed:
                d = e.get('date')
                try:
                    mkey = (d.year, d.month) if d is not None else None
                    mlabel = d.strftime('%B %Y') if d is not None else 'Earlier'
                except Exception:
                    mkey, mlabel = None, 'Earlier'
                if mkey != last_month:
                    last_month = mkey
                    self._body(frame, mlabel, size=11, bold=True).pack(
                        anchor='w', padx=16, pady=(8, 2))
                row = ctk.CTkFrame(frame, fg_color='transparent')
                row.pack(fill='x', padx=16, pady=2)
                try:
                    dstr = d.strftime('%m/%d') if d is not None else '—'
                except Exception:
                    dstr = '—'
                self._body(row, dstr, size=10, dim=True, width=44).pack(side='left')
                self._body(row, e['icon'], size=12, width=26).pack(side='left')
                txt = ctk.CTkFrame(row, fg_color='transparent')
                txt.pack(side='left', fill='x', expand=True)
                self._body(txt, e['subject'], size=11, bold=True).pack(anchor='w')
                if e.get('snippet'):
                    self._body(txt, e['snippet'], size=10, dim=True).pack(anchor='w')

            # -- where we've been --------------------------------------
            hist = self._collect_history_lines()
            if hist:
                self._heading(frame, "🏆 Where we've been", size=14).pack(
                    anchor='w', padx=14, pady=(10, 4))
                for h in hist:
                    lbl = self._body(frame,
                                     ("★ " if h['mine'] else "    ") + h['text'],
                                     size=11, dim=not h['mine'])
                    if h['mine']:
                        try:
                            lbl.configure(text_color=ct['GOLD'])
                        except Exception:
                            pass
                    lbl.pack(anchor='w', padx=18, pady=1)
                ctk.CTkFrame(frame, fg_color='transparent', height=10).pack()

            self.stats_label.configure(
                text=f"Season Story · {len(developing)} developing · "
                     f"{len(feed)} moments")
        except Exception:
            pass

    def request_close(self):
        """Close the view: refresh the nav badge, then hand off."""
        if hasattr(self.app, 'update_inbox_notification'):
            self.app.update_inbox_notification()
        self.close_view()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # Popup-mode alias kept for the InboxWindow wrapper.
    _on_closing = request_close


# Sample email generation removed - emails are now generated dynamically from actual game events


class _MessageEditor(InGamePopup):
    """Non-modal To/Subject/Body editor behind Reply, Forward, and Compose.

    Thin and honest: Send builds a real EmailMessage and appends it to the
    user's inbox store through the existing add_message() write path, so
    the sent copy is a real record in the same store as incoming mail.
    The sent copy is marked read -- it is our own outbound text, not new
    mail -- and never expires as headline news (no TTL). Closing the
    editor discards the draft (confirmed when the user typed something).
    Never modal: no grab_set, so it can't seize the game loop.
    """

    def __init__(self, parent, app, title, to_value="", to_locked=False,
                 subject_value="", body_value="", category="General",
                 sender_tag="You", on_sent=None):
        super().__init__(parent)
        self.app = app if app is not None else parent
        self.title(title)
        self.geometry("520x460")
        self._category = category or "General"
        self._sender_tag = sender_tag
        self._on_sent = on_sent
        self._sent = False

        self.to_var = tk.StringVar(value=to_value)
        self.subj_var = tk.StringVar(value=subject_value)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        def _row(label, var, locked=False):
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(r, text=label, width=70, anchor="w",
                         font=("Segoe UI", 11, "bold")).pack(side="left")
            e = ctk.CTkEntry(r, textvariable=var, width=380,
                             font=("Segoe UI", 11))
            if locked:
                e.configure(state="disabled")
            e.pack(side="left", fill="x", expand=True)
            return e

        _row("To:", self.to_var, locked=to_locked)
        _row("Subject:", self.subj_var)
        ctk.CTkLabel(body, text="Message:", anchor="w",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w",
                                                        pady=(4, 4))
        self.body_box = ctk.CTkTextbox(body, font=("Segoe UI", 11),
                                       wrap="word")
        self.body_box.pack(fill="both", expand=True)
        if body_value:
            self.body_box.insert("1.0", body_value)

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(12, 0))
        ctk.CTkButton(btns, text="Send", width=120,
                      command=self._send).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btns, text="Cancel", width=120, fg_color="transparent",
                      border_width=1, command=self._on_close).pack(side="right")

        try:
            self.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

    def _draft_text(self):
        try:
            return self.body_box.get("1.0", "end").strip()
        except Exception:
            return ""

    def _on_close(self):
        """Discard the draft; confirm first if anything was typed."""
        if self._draft_text():
            # Gating T2-Phase 3: non-modal confirm; dismiss/Escape keeps
            # editing (the safe default), Yes discards and closes.
            confirm_card(self, "Discard draft?",
                         "Close without sending? Your draft will be lost.",
                         on_yes=self.destroy)
            return
        self.destroy()

    def _send(self):
        to = self.to_var.get().strip()
        if not to:
            messagebox.showwarning("No recipient",
                                   "Enter a recipient before sending.",
                                   parent=self)
            return
        body = self._draft_text()
        if not body:
            messagebox.showwarning("Empty message",
                                   "Write something before sending.",
                                   parent=self)
            return
        subject = self.subj_var.get().strip() or "(no subject)"
        today = getattr(self.app, "current_date", None) or date.today()
        msg = EmailMessage(
            sender=self._sender_tag,
            sender_type="System",
            subject=subject,
            content=f"To: {to}\n\n{body}",
            date_sent=today,
            game_date_sent=today,
            category=self._category,
            is_read=True,  # our own sent copy, not new mail
        )
        self._sent = True
        try:
            self.destroy()
        except Exception:
            pass
        cb = self._on_sent
        if callable(cb):
            cb(msg, to)


class InboxWindow(InGamePopup):
    """Popup wrapper around InboxView (backward compatibility).

    New code should embed InboxView as a full-screen view via
    HockeyManagerGUI.open_inbox_window() instead of opening this card.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Inbox")
        # Closing the card must tear down the popup card (manager-owned),
        # not just the inner frame.
        self._view = InboxView(self, app=parent)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)
        try:
            self.protocol("WM_DELETE_WINDOW", self._view.request_close)
        except Exception:
            pass

    def focus_message(self, message_id):
        return self._view.focus_message(message_id)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)
