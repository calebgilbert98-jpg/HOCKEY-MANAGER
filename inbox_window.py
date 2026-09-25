# inbox_window.py
# Email Inbox system for Hockey Manager, similar to EHM

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from game_classes import EmailMessage, EmailGenerator
from typing import List, Optional

class InboxWindow(tk.Toplevel):
    """EHM-style Email Inbox window with comprehensive email management."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Inbox")
        self.geometry("1000x700")
        self.configure(background=parent.BG_COLOR)
        
        # Initialize inbox reference
        self.inbox = parent.user_team.inbox
        self.selected_message = None
        
        self._setup_styles()
        self._create_interface()
        self._populate_inbox()
        
        # Update parent's inbox notification
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _setup_styles(self):
        """Setup custom styles for the inbox."""
        style = ttk.Style()
        
        # Email list styles
        style.configure('Unread.Treeview', foreground='#FFFFFF', background='#2A2A2A')
        style.configure('Read.Treeview', foreground='#AAAAAA', background='#1F1F1F')
        style.configure('Urgent.Treeview', foreground='#FF6B6B', background='#2A2A2A')
        
    def _create_interface(self):
        """Create the main inbox interface."""
        # Main container
        main_frame = ttk.Frame(self, style='Panel.TFrame', padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Header with inbox stats
        self._create_header(main_frame)
        
        # Main content area - split between email list and preview
        content_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        content_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        # Left side - Email list and filters
        left_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Right side - Email preview
        right_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        self._create_email_list(left_frame)
        self._create_email_preview(right_frame)
        
        # Bottom toolbar
        self._create_toolbar(main_frame)
        
    def _create_header(self, parent):
        """Create the header with inbox statistics."""
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))
        
        # Title and stats
        title_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        title_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(title_frame, text="Inbox", style='Header.TLabel', 
                 font=(self.parent.FONT_FAMILY, 16, 'bold')).pack(side='left')
        
        self.stats_label = ttk.Label(title_frame, text="", style='Header.TLabel', 
                                   font=(self.parent.FONT_FAMILY, 12))
        self.stats_label.pack(side='right')
        
        # Filter buttons
        filter_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        filter_frame.pack(fill='x', padx=10, pady=(0, 5))
        
        filters = [
            ("All", "all"),
            ("Unread", "unread"), 
            ("Urgent", "urgent"),
            ("Trade", "Trade"),
            ("Scouting", "Scouting"),
            ("Contracts", "Contracts"),
            ("Injuries", "Injuries"),
            ("Media", "Media"),
            ("League", "League")
        ]
        
        self._filter_buttons = {}
        for text, filter_type in filters:
            btn = ttk.Button(filter_frame, text=text, style='Secondary.TButton',
                           command=lambda f=filter_type: self._apply_filter(f))
            btn.pack(side='left', padx=2)
            self._filter_buttons[filter_type] = btn
        self._filter_buttons["all"].configure(style='TButton')
            
    def _create_email_list(self, parent):
        """Create the email list with filters."""
        list_frame = ttk.Frame(parent, style='Panel.TFrame', padding=5)
        list_frame.pack(fill='both', expand=True)
        
        ttk.Label(list_frame, text="Messages", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Create treeview for email list
        columns = {
            'priority': ('!', 30),
            'sender': ('From', 150), 
            'subject': ('Subject', 250),
            'category': ('Category', 80),
            'date': ('Date', 80),
            'status': ('Status', 60)
        }
        
        # Create treeview
        tree_frame = ttk.Frame(list_frame, style='Panel.TFrame')
        tree_frame.pack(fill='both', expand=True)
        
        self.email_tree = ttk.Treeview(tree_frame, columns=list(columns.keys()), 
                                     show='headings', height=20)
        
        # Configure columns
        for col, (text, width) in columns.items():
            self.email_tree.heading(col, text=text)
            self.email_tree.column(col, width=width, anchor='w' if col != 'priority' else 'center')
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.email_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.email_tree.xview)
        
        self.email_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
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
        preview_frame = ttk.Frame(parent, style='Panel.TFrame', padding=5)
        preview_frame.pack(fill='both', expand=True)
        
        ttk.Label(preview_frame, text="Message Preview", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Email header frame
        header_frame = ttk.Frame(preview_frame, style='PlayerPanel.TFrame', padding=8)
        header_frame.pack(fill='x', pady=(0, 5))
        
        self.preview_from_label = ttk.Label(header_frame, text="From: ", style='PlayerInfo.TLabel')
        self.preview_from_label.pack(anchor='w')
        
        self.preview_subject_label = ttk.Label(header_frame, text="Subject: ", style='PlayerInfo.TLabel')
        self.preview_subject_label.pack(anchor='w')
        
        self.preview_date_label = ttk.Label(header_frame, text="Date: ", style='PlayerInfo.TLabel')
        self.preview_date_label.pack(anchor='w')
        
        self.preview_category_label = ttk.Label(header_frame, text="Category: ", style='PlayerInfo.TLabel')
        self.preview_category_label.pack(anchor='w')
        
        # Email content
        content_frame = ttk.Frame(preview_frame, style='Panel.TFrame')
        content_frame.pack(fill='both', expand=True)
        
        self.content_text = tk.Text(content_frame, wrap='word', 
                                  bg=self.parent.CONTENT_BG, 
                                  fg=self.parent.TEXT_COLOR,
                                  font=(self.parent.FONT_FAMILY, 10),
                                  state='disabled',
                                  relief='flat',
                                  borderwidth=0)
        
        content_scrollbar = ttk.Scrollbar(content_frame, orient='vertical', command=self.content_text.yview)
        self.content_text.configure(yscrollcommand=content_scrollbar.set)
        
        self.content_text.pack(side='left', fill='both', expand=True)
        content_scrollbar.pack(side='right', fill='y')
        
        # Action buttons frame
        action_frame = ttk.Frame(preview_frame, style='Panel.TFrame')
        action_frame.pack(fill='x', pady=(5, 0))
        
        self.mark_read_btn = ttk.Button(action_frame, text="Mark as Read", 
                                      command=self._mark_current_read, style='TButton')
        self.mark_read_btn.pack(side='left', padx=(0, 5))
        
        self.reply_btn = ttk.Button(action_frame, text="Reply", 
                                  command=self._reply_to_current, style='TButton')
        self.reply_btn.pack(side='left', padx=5)
        
        self.delete_btn = ttk.Button(action_frame, text="Delete", 
                                   command=self._delete_current, style='TButton')
        self.delete_btn.pack(side='left', padx=5)
        
        # Special action button (initially hidden)
        self.special_action_btn = ttk.Button(action_frame, text="", 
                                           command=None, style='Accent.TButton')
        # Don't pack initially - will be shown/hidden as needed
        
    def _create_toolbar(self, parent):
        """Create the bottom toolbar."""
        toolbar_frame = ttk.Frame(parent, style='TitleBar.TFrame')
        toolbar_frame.pack(fill='x', pady=(10, 0))
        
        # Toolbar buttons
        ttk.Button(toolbar_frame, text="Compose", command=self._compose_email, 
                 style='TButton').pack(side='left', padx=5)
        
        ttk.Button(toolbar_frame, text="Mark All Read", command=self._mark_all_read, 
                 style='TButton').pack(side='left', padx=5)
        
        ttk.Button(toolbar_frame, text="Delete Read", command=self._delete_read_messages, 
                 style='TButton').pack(side='left', padx=5)
        
        ttk.Button(toolbar_frame, text="Refresh", command=self._refresh_inbox, 
                 style='TButton').pack(side='left', padx=5)
        
        # Close button
        ttk.Button(toolbar_frame, text="Close", command=self._on_closing, 
                 style='TButton').pack(side='right', padx=5)
        
    def _create_context_menu(self):
        """Create context menu for email list."""
        self.context_menu = tk.Menu(self, tearoff=0, 
                                  bg=self.parent.TITLE_BAR_COLOR, 
                                  fg=self.parent.TEXT_COLOR)
        
        self.context_menu.add_command(label="Mark as Read", command=self._mark_current_read)
        self.context_menu.add_command(label="Mark as Unread", command=self._mark_current_unread)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Reply", command=self._reply_to_current)
        self.context_menu.add_command(label="Forward", command=self._forward_current)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Mark as Important", command=self._mark_current_important)
        self.context_menu.add_command(label="Delete", command=self._delete_current)
        
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
        
        # Apply styling based on read status
        if not message.is_read:
            self.email_tree.item(item_id, tags='unread')
        elif message.is_urgent:
            self.email_tree.item(item_id, tags='urgent')
            
    def _apply_filter(self, filter_type: str):
        """Apply filter to email list."""
        for ftype, btn in getattr(self, '_filter_buttons', {}).items():
            btn.configure(style='TButton' if ftype == filter_type else 'Secondary.TButton')
        # Clear current view
        for item in self.email_tree.get_children():
            self.email_tree.delete(item)
            
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
        self.preview_from_label.config(text=f"From: {message.sender} ({message.sender_type})")
        self.preview_subject_label.config(text=f"Subject: {message.subject}")
        self.preview_date_label.config(text=f"Date: {message.date_sent.strftime('%B %d, %Y')}")
        self.preview_category_label.config(text=f"Category: {message.category}")
        
        # Update content
        self.content_text.config(state='normal')
        self.content_text.delete(1.0, tk.END)
        self.content_text.insert(1.0, message.content)
        
        # Add response info if needed
        if message.requires_response:
            self.content_text.insert(tk.END, f"\n\n--- RESPONSE REQUIRED ---")
            if message.response_deadline:
                self.content_text.insert(tk.END, f"\nDeadline: {message.response_deadline.strftime('%B %d, %Y')}")
            if message.is_overdue():
                self.content_text.insert(tk.END, f"\n⚠️  OVERDUE")
                
        self.content_text.config(state='disabled')
        
        # Update button states
        self.mark_read_btn.config(text="Mark as Unread" if message.is_read else "Mark as Read")
        self.reply_btn.config(state='normal' if message.requires_response else 'disabled')
        
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
            self.special_action_btn.config(
                text="🏒 START FANTASY DRAFT",
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
        """Refresh the inbox display."""
        self._populate_inbox()
        if hasattr(self.parent, 'update_inbox_notification'):
            self.parent.update_inbox_notification()
            
    def _clear_preview(self):
        """Clear the message preview pane."""
        self.preview_from_label.config(text="From: ")
        self.preview_subject_label.config(text="Subject: ")
        self.preview_date_label.config(text="Date: ")
        self.preview_category_label.config(text="Category: ")
        
        self.content_text.config(state='normal')
        self.content_text.delete(1.0, tk.END)
        self.content_text.config(state='disabled')
        
        self.mark_read_btn.config(text="Mark as Read", state='disabled')
        self.reply_btn.config(state='disabled')
        
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
            
        self.stats_label.config(text=stats_text)
        
    def _on_closing(self):
        """Handle window closing."""
        # Update parent inbox notification
        if hasattr(self.parent, 'update_inbox_notification'):
            self.parent.update_inbox_notification()
        self.destroy()


# Sample email generation removed - emails are now generated dynamically from actual game events
