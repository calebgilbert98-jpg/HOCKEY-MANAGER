# inbox_window.py
# Email Inbox system for Hockey Manager, similar to EHM
# CustomTkinter rebuild: CTkToplevel, dark pill filters, styled dark
# message list with unread/urgent/overdue row tags, dark preview pane.

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from game_classes import EmailMessage, EmailGenerator
from typing import List, Optional

import customtkinter as ctk


class InboxWindow(ctk.CTkToplevel):
    """EHM-style Email Inbox window with comprehensive email management."""

    _FILTERS = [
        ("All", "all"),
        ("Unread", "unread"),
        ("Urgent", "urgent"),
        ("Trade", "Trade"),
        ("Scouting", "Scouting"),
        ("Contracts", "Contracts"),
        ("Injuries", "Injuries"),
        ("Media", "Media"),
        ("League", "League"),
    ]

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
        self.title("Inbox")
        self.configure(fg_color=BG)
        self.geometry("1050x720")
        self.minsize(900, 600)

        # Initialize inbox reference
        self.inbox = parent.user_team.inbox
        self.selected_message = None
        self._current_filter = "all"

        self._setup_tree_style()
        self._create_interface()
        self._populate_inbox()

        # Update parent's inbox notification
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

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

        # Main content area - split between email list and preview
        content_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        content_frame.pack(fill='both', expand=True, pady=(12, 0))
        content_frame.grid_columnconfigure(0, weight=3)
        content_frame.grid_columnconfigure(1, weight=2)
        content_frame.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(content_frame, fg_color=ct['CARD'],
                                  corner_radius=12)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        right_frame = ctk.CTkFrame(content_frame, fg_color=ct['CARD'],
                                   corner_radius=12)
        right_frame.grid(row=0, column=1, sticky='nsew', padx=(6, 0))

        self._create_email_list(left_frame)
        self._create_email_preview(right_frame)

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
            row = (status_row if filter_type in ("all", "unread", "urgent")
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
            'sender': ('From', 150),
            'subject': ('Subject', 260),
            'category': ('Category', 90),
            'date': ('Date', 90),
            'status': ('Status', 80)
        }

        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        self.email_tree = ttk.Treeview(table_frame, columns=list(columns.keys()),
                                       show='headings', height=20,
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
        self._heading(parent, "Message Preview", size=14).pack(
            anchor='w', padx=14, pady=(12, 6))

        # Email header card
        header_frame = ctk.CTkFrame(parent, fg_color=ct['PANEL'],
                                    corner_radius=10)
        header_frame.pack(fill='x', padx=12, pady=(0, 8))

        self.preview_from_label = self._body(header_frame, "From: ", size=11)
        self.preview_from_label.pack(anchor='w', padx=12, pady=(8, 2))
        self.preview_subject_label = self._body(header_frame, "Subject: ",
                                                size=11)
        self.preview_subject_label.pack(anchor='w', padx=12, pady=2)
        self.preview_date_label = self._body(header_frame, "Date: ", size=11)
        self.preview_date_label.pack(anchor='w', padx=12, pady=2)
        self.preview_category_label = self._body(header_frame, "Category: ",
                                                 size=11)
        self.preview_category_label.pack(anchor='w', padx=12, pady=(2, 8))

        # Email content (dark CTkTextbox with styled scrollbar)
        self.content_text = ctk.CTkTextbox(
            parent, wrap='word',
            fg_color=ct['PANEL'], text_color=ct['TEXT'],
            border_width=1, border_color=ct['BORDER'],
            corner_radius=10, font=('Segoe UI', 11))
        self.content_text.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        self.content_text.configure(state='disabled')

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
        if hasattr(self.parent, 'tree_maps') and 'inbox_messages' in self.parent.tree_maps:
            self.parent.tree_maps['inbox_messages'].clear()

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
        if not hasattr(self.parent, 'tree_maps'):
            self.parent.tree_maps = {}
        if 'inbox_messages' not in self.parent.tree_maps:
            self.parent.tree_maps['inbox_messages'] = {}
        self.parent.tree_maps['inbox_messages'][item_id] = message

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
        if hasattr(self.parent, 'tree_maps') and 'inbox_messages' in self.parent.tree_maps:
            self.parent.tree_maps['inbox_messages'].clear()

        # Filter messages
        filtered_messages = []

        if filter_type == "all":
            filtered_messages = self.inbox.messages
        elif filter_type == "unread":
            filtered_messages = self.inbox.get_unread_messages()
        elif filter_type == "urgent":
            filtered_messages = self.inbox.get_urgent_messages()
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
            if (hasattr(self.parent, 'tree_maps') and
                'inbox_messages' in self.parent.tree_maps and
                item in self.parent.tree_maps['inbox_messages']):
                message = self.parent.tree_maps['inbox_messages'][item]
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

        self.content_text.configure(state='disabled')

        # Update button states
        self.mark_read_btn.configure(
            text="Mark as Unread" if message.is_read else "Mark as Read")
        self.reply_btn.configure(
            state='normal' if message.requires_response else 'disabled')

        # Handle fantasy draft special button
        self._handle_fantasy_draft_button(message)

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
            hasattr(self.parent.game_manager, 'pending_fantasy_draft') and
            self.parent.game_manager.pending_fantasy_draft):

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
            self.parent.open_fantasy_draft_window()

        except Exception as e:
            messagebox.showerror("Error", f"Could not start fantasy draft: {e}")

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
        if hasattr(self.parent, 'update_inbox_notification'):
            self.parent.update_inbox_notification()

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

    def _on_closing(self):
        """Handle window closing."""
        # Update parent inbox notification
        if hasattr(self.parent, 'update_inbox_notification'):
            self.parent.update_inbox_notification()
        self.destroy()


# Sample email generation removed - emails are now generated dynamically from actual game events
