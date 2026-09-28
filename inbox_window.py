# inbox_window.py
# Email Inbox system for Hockey Manager, similar to EHM
# CustomTkinter rebuild: CTkToplevel, dark pill filters, styled dark
# message list with unread/urgent/overdue row tags, dark preview pane.

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup
from datetime import date, timedelta
from game_classes import EmailMessage, EmailGenerator
from typing import List, Optional

import customtkinter as ctk


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
        """Dark, flat styling for the message list (styled ttk.Treeview per
        the migration guide -- the list carries 6 columns and per-message
        color tags)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Inbox.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=30,
                        font=('Segoe UI', 10))
        style.configure('Inbox.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Inbox.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('Inbox.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('Inbox.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.configure('Inbox.Horizontal.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Inbox.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])
        style.map('Inbox.Horizontal.TScrollbar',
                  background=[('active', ct['BORDER'])])

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

        self._create_email_list(list_frame)
        self._create_email_preview(preview_frame)

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
                font=('Segoe UI', 11),
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
        """Create the email list with filters."""
        ct = self._ct
        self._heading(parent, "Messages", size=14).pack(
            anchor='w', padx=14, pady=(12, 6))

        columns = {
            'priority': ('!', 30),
            'sender': ('From', 170),
            'subject': ('Subject', 460),
            'category': ('Category', 110),
            'date': ('Date', 100),
            'status': ('Status', 90)
        }

        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        self.email_tree = ttk.Treeview(table_frame, columns=list(columns.keys()),
                                       show='headings', height=8,
                                       style='Inbox.Treeview')

        for col, (text, width) in columns.items():
            self.email_tree.heading(col, text=text)
            self.email_tree.column(col, width=width,
                                   anchor='w' if col != 'priority' else 'center')

        # Message-row color tags: first tag in the tuple wins on conflicts
        self.email_tree.tag_configure(
            'overdue', foreground=ct['GOLD'], font=('Segoe UI', 10, 'bold'))
        self.email_tree.tag_configure(
            'urgent', foreground=ct['RED'], font=('Segoe UI', 10, 'bold'))
        self.email_tree.tag_configure(
            'unread', foreground=ct['TEXT'], font=('Segoe UI', 10, 'bold'))
        self.email_tree.tag_configure('read', foreground=ct['TEXT_DIM'])
        self.email_tree.tag_configure('new_status', foreground=ct['TEAL'])

        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical',
                                    style='Inbox.Vertical.TScrollbar',
                                    command=self.email_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal',
                                    style='Inbox.Horizontal.TScrollbar',
                                    command=self.email_tree.xview)

        self.email_tree.configure(yscrollcommand=v_scrollbar.set,
                                  xscrollcommand=h_scrollbar.set)

        self.email_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')

        # Bind events
        self.email_tree.bind('<<TreeviewSelect>>', self._on_email_select)
        self.email_tree.bind('<Double-Button-1>', self._on_email_double_click)

        # Context menu
        self._create_context_menu()

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
            corner_radius=10, font=('Segoe UI', 11))
        self.content_text.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        self.content_text.configure(state='disabled')

        # Interactive action frame (game-day bundle, press conferences).
        # Hidden unless the selected message carries an interactive action;
        # it shares the content_text slot.
        self.interactive_frame = ctk.CTkScrollableFrame(
            parent, fg_color=ct['PANEL'], border_width=1,
            border_color=ct['BORDER'], corner_radius=10)

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

        self.email_tree.bind('<Button-3>', self._show_context_menu)

    def _show_context_menu(self, event):
        """Show context menu."""
        item = self.email_tree.identify('item', event.x, event.y)
        if item:
            self.email_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _populate_inbox(self):
        """Populate the inbox with messages."""
        # Clear existing items
        for item in self.email_tree.get_children():
            self.email_tree.delete(item)

        # Clear tree maps
        if hasattr(self.app, 'tree_maps') and 'inbox_messages' in self.app.tree_maps:
            self.app.tree_maps['inbox_messages'].clear()

        # Add messages
        for message in self.inbox.messages:
            self._add_message_to_tree(message)

        # Update stats
        self._update_stats()
        self._select_first_message()

    def _select_first_message(self):
        """Select the first message so the preview is never empty."""
        children = self.email_tree.get_children()
        if children:
            self.email_tree.selection_set(children[0])
            self.email_tree.focus(children[0])

    def _row_tags(self, message: EmailMessage):
        """Return treeview tags for a message: first tag wins on conflicts."""
        if message.is_overdue():
            return ('overdue',)
        if message.is_urgent:
            return ('urgent',)
        if not message.is_read:
            return ('unread',)
        return ('read',)

    def _add_message_to_tree(self, message: EmailMessage):
        """Add a single message to the tree."""
        # Priority indicator
        priority_icon = ""
        if message.is_urgent or message.priority >= 4:
            priority_icon = "!!"
        elif message.is_important or message.priority >= 3:
            priority_icon = "!"
        elif message.requires_response:
            priority_icon = ">"

        # Status
        status = "New" if not message.is_read else "Read"
        if message.is_overdue():
            status = "Overdue"
        if getattr(message, "is_saved", False):
            status = f"📌 {status}"

        # Date formatting
        date_str = message.date_sent.strftime("%m/%d")
        if message.get_age_days() == 0:
            date_str = "Today"
        elif message.get_age_days() == 1:
            date_str = "Yesterday"

        # Insert item
        item_id = self.email_tree.insert('', 'end', values=(
            priority_icon,
            message.sender,
            message.subject[:50] + "..." if len(message.subject) > 50 else message.subject,
            message.category,
            date_str,
            status
        ))

        # Store message reference in tree_maps
        if not hasattr(self.app, 'tree_maps'):
            self.app.tree_maps = {}
        if 'inbox_messages' not in self.app.tree_maps:
            self.app.tree_maps['inbox_messages'] = {}
        self.app.tree_maps['inbox_messages'][item_id] = message

        # Apply styling based on read/urgent/overdue status
        self.email_tree.item(item_id, tags=self._row_tags(message))

    def _apply_filter(self, filter_type: str):
        """Apply filter to email list."""
        self._current_filter = filter_type
        self._paint_filter_pills()
        # Clear current view
        for item in self.email_tree.get_children():
            self.email_tree.delete(item)

        # Clear tree maps (messages are re-registered below)
        if hasattr(self.app, 'tree_maps') and 'inbox_messages' in self.app.tree_maps:
            self.app.tree_maps['inbox_messages'].clear()

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
            self._add_message_to_tree(message)
        self._select_first_message()
        self._update_stats()

    def _update_filter_badges(self):
        """Update per-filter unread count badges on the filter pills.

        Badges show the number of unread messages visible under each filter,
        e.g. "Trade (2)". Filters with no unread messages show the plain label.
        """
        buttons = getattr(self, '_filter_buttons', {})
        if not buttons:
            return

        unread = self.inbox.get_unread_messages()
        urgent_unread = [m for m in self.inbox.get_urgent_messages() if not m.is_read]

        counts = {
            'all': len(unread),
            'unread': len(unread),
            'urgent': len(urgent_unread),
        }
        for category in ('Trade', 'Scouting', 'Contracts', 'Injuries', 'Media', 'League'):
            counts[category] = sum(
                1 for m in self.inbox.get_messages_by_category(category) if not m.is_read)

        for label, filter_type in self._FILTERS:
            btn = buttons[filter_type]
            count = counts.get(filter_type, 0)
            btn.configure(text=f"{label} ({count})" if count > 0 else label)

    def _on_email_select(self, event):
        """Handle email selection."""
        selection = self.email_tree.selection()
        if selection:
            item = selection[0]
            # Get message object from tree_maps
            if (hasattr(self.app, 'tree_maps') and
                'inbox_messages' in self.app.tree_maps and
                item in self.app.tree_maps['inbox_messages']):
                message = self.app.tree_maps['inbox_messages'][item]
                self.selected_message = message
                self._display_message_preview(message)

    def _on_email_double_click(self, event):
        """Handle double-click on email."""
        if self.selected_message:
            # Mark as read and open full view
            if not self.selected_message.is_read:
                self.inbox.mark_message_read(self.selected_message.id)
                self._refresh_inbox()

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
                "trade_offer", "trade_counter"):
            self._show_interactive_action(message)
        else:
            self._hide_interactive_action()
            # Update content
            self.content_text.configure(state='normal')
            self.content_text.delete(1.0, tk.END)
            self.content_text.insert(1.0, message.content)

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
            mapping = {}
            if hasattr(self.app, 'tree_maps'):
                mapping = self.app.tree_maps.get('inbox_messages', {})
            for item_id, message in mapping.items():
                if getattr(message, 'id', None) == message_id:
                    self.email_tree.selection_set(item_id)
                    self.email_tree.see(item_id)
                    self.email_tree.focus(item_id)
                    self._on_email_select(None)
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
        self._heading(self.interactive_frame, title, size=13,
                      wraplength=300, justify='left', anchor='w').pack(
            anchor='w', padx=10, pady=(12, 4))
        sep = ctk.CTkFrame(self.interactive_frame, height=1,
                           fg_color=ct['BORDER'])
        sep.pack(fill='x', padx=10, pady=(0, 6))

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

        # ---- Watch / Quick ----
        self._action_section("HOW TO PLAY TONIGHT")
        btn_row = ctk.CTkFrame(self.interactive_frame, fg_color="transparent")
        btn_row.pack(fill='x', padx=10, pady=8)
        self._primary_button(btn_row, text="\u25B6 WATCH LIVE",
                             width=200, height=44,
                             command=lambda: app._resolve_game_day(True)
                             ).pack(side='left', padx=(0, 8))
        self._secondary_button(btn_row, text="\u26A1 QUICK SIM",
                               width=200, height=44,
                               command=lambda: app._resolve_game_day(False)
                               ).pack(side='left', padx=8)

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
            self._iwrap("\u2022 " + tn.asset_summary([ad]), size=11, padx=18)
        self._iwrap("YOU GET:", size=10, dim=True, padx=10, pady=(6, 0))
        for ad in neg.partner_assets or []:
            self._iwrap("\u2022 " + tn.asset_summary([ad]), size=11, padx=18)

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
        self._iwrap(f"{name} rejected your offer but will sign for "
                    f"${asking:,} per year over {years} year(s).",
                    size=11, padx=10, pady=(4, 2))
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


    def _on_bundle_presser_answer(self, message, qi, ai):
        try:
            self.app._answer_bundle_presser(message, qi, ai)
        except Exception:
            pass
        self._show_interactive_action(message)

    def _on_bundle_team_talk(self, message, oi):
        try:
            self.app._answer_bundle_team_talk(message, oi)
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
        if self.selected_message:
            if messagebox.askyesno("Delete Message", "Are you sure you want to delete this message?"):
                self.inbox.delete_message(self.selected_message.id)
                self.selected_message = None
                self._clear_preview()
                self._refresh_inbox()

    def _reply_to_current(self):
        """Reply to current message."""
        if self.selected_message and self.selected_message.requires_response:
            messagebox.showinfo("Reply", f"Reply functionality for {self.selected_message.category} messages coming soon!")

    def _forward_current(self):
        """Forward current message."""
        if self.selected_message:
            messagebox.showinfo("Forward", "Forward functionality coming soon!")

    def _compose_email(self):
        """Compose a new email."""
        messagebox.showinfo("Compose", "Compose functionality coming soon!")

    def _mark_all_read(self):
        """Mark all messages as read."""
        if messagebox.askyesno("Mark All Read", "Mark all messages as read?"):
            self.inbox.mark_all_read()
            self._refresh_inbox()

    def _delete_read_messages(self):
        """Delete all read messages."""
        read_messages = [msg for msg in self.inbox.messages if msg.is_read]
        if read_messages:
            if messagebox.askyesno("Delete Read", f"Delete {len(read_messages)} read messages?"):
                for message in read_messages:
                    self.inbox.delete_message(message.id)
                self._refresh_inbox()
        else:
            messagebox.showinfo("Delete Read", "No read messages to delete.")

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
