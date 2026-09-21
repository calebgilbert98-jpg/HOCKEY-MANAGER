# media_center_window.py
# Media Center UI for the optional Media & Press Conference System

import tkinter as tk
from tkinter import ttk, messagebox
from media_system import MediaSystem, MediaEngagementLevel, JournalistType
import random

class MediaCenterWindow(tk.Toplevel):
    """Media Center - Optional immersive media interactions"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("🎬 Media Center")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1200x800")
        
        # Initialize media system if not exists
        if not hasattr(parent.game_manager, 'media_system'):
            parent.game_manager.media_system = MediaSystem(parent.game_manager)
        
        self.media_system = parent.game_manager.media_system
        
        self._setup_styles()
        self._create_interface()
        self._update_display()
        
        # Add to tracked windows
        parent.open_windows['media_center'] = self
    
    def _setup_styles(self):
        """Setup custom styles for media center"""
        style = ttk.Style()
        
        # Media-specific styles
        style.configure('Media.TFrame', background=self.parent.CONTENT_BG, relief='raised', borderwidth=1)
        style.configure('MediaTitle.TLabel', background=self.parent.CONTENT_BG, foreground=self.parent.HEADER_COLOR, 
                       font=(self.parent.FONT_FAMILY, 14, 'bold'))
        style.configure('MediaContent.TLabel', background=self.parent.CONTENT_BG, foreground=self.parent.TEXT_COLOR,
                       font=(self.parent.FONT_FAMILY, 10), wraplength=400)
        style.configure('Journalist.TLabel', background=self.parent.CONTENT_BG, foreground='#FFB300',
                       font=(self.parent.FONT_FAMILY, 10, 'bold'))
        style.configure('Question.TLabel', background=self.parent.CONTENT_BG, foreground=self.parent.TEXT_COLOR,
                       font=(self.parent.FONT_FAMILY, 10), wraplength=500)
        
        # Engagement level styles
        style.configure('Disabled.TRadiobutton', background=self.parent.CONTENT_BG, foreground='#808080')
        style.configure('Minimal.TRadiobutton', background=self.parent.CONTENT_BG, foreground='#4CAF50')
        style.configure('Standard.TRadiobutton', background=self.parent.CONTENT_BG, foreground='#2196F3')
        style.configure('Full.TRadiobutton', background=self.parent.CONTENT_BG, foreground='#FF5722')
    
    def _create_interface(self):
        """Create the complete media center interface"""
        # Main container
        main_container = ttk.Frame(self, style='Panel.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title and status
        self._create_header(main_container)
        
        # Create paned window for layout
        paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Left panel - Settings and status
        left_panel = ttk.Frame(paned, style='Panel.TFrame')
        paned.add(left_panel, weight=1)
        
        # Right panel - Active events and interviews
        right_panel = ttk.Frame(paned, style='Panel.TFrame')
        paned.add(right_panel, weight=2)
        
        # Create left panel content
        self._create_settings_panel(left_panel)
        self._create_status_panel(left_panel)
        self._create_journalist_panel(left_panel)
        
        # Create right panel content  
        self._create_events_panel(right_panel)
        self._create_storylines_panel(right_panel)
    
    def _create_header(self, parent):
        """Create header with title and quick status"""
        header_frame = ttk.Frame(parent, style='Title.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        title_label = ttk.Label(header_frame, text="🎬 Media Center", style='Title.TLabel')
        title_label.pack(side=tk.LEFT)
        
        # Quick status
        status = self.media_system.get_system_status()
        status_text = f"Level: {status['engagement_level']} | Pending: {status['pending_events']} | Reputation: {status['gm_reputation']}/100"
        self.status_label = ttk.Label(header_frame, text=status_text, style='Content.TLabel')
        self.status_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Separator
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
    
    def _create_settings_panel(self, parent):
        """Create media engagement settings"""
        settings_frame = self.parent._create_packed_panel(parent, "🔧 Media Settings")
        
        # Engagement level selection
        ttk.Label(settings_frame, text="Choose your media engagement level:", style='Content.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        self.engagement_var = tk.StringVar(value=self.media_system.engagement_level.value)
        
        # Radio buttons for engagement levels
        levels = [
            (MediaEngagementLevel.DISABLED, "🚫 Disabled", "No media interactions - pure hockey management"),
            (MediaEngagementLevel.MINIMAL, "📰 Minimal", "Major events only (trades, big signings)"),
            (MediaEngagementLevel.STANDARD, "🎙️ Standard", "Pre/post-game + major events"),
            (MediaEngagementLevel.FULL, "📺 Full Immersion", "Complete storylines & all interactions")
        ]
        
        for level, display_text, description in levels:
            frame = ttk.Frame(settings_frame, style='Panel.TFrame')
            frame.pack(fill=tk.X, pady=2)
            
            rb = ttk.Radiobutton(frame, text=display_text, variable=self.engagement_var, 
                               value=level.value, command=self._on_engagement_change)
            rb.pack(side=tk.LEFT)
            
            desc_label = ttk.Label(frame, text=f"- {description}", style='Small.TLabel')
            desc_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Additional options
        options_frame = ttk.Frame(settings_frame, style='Panel.TFrame')
        options_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.auto_handle_var = tk.BooleanVar(value=self.media_system.auto_handle_minor_events)
        ttk.Checkbutton(options_frame, text="Auto-handle routine interviews", 
                       variable=self.auto_handle_var, command=self._on_auto_handle_change).pack(anchor=tk.W)
        
        # Quick actions
        actions_frame = ttk.Frame(settings_frame, style='Panel.TFrame')
        actions_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(actions_frame, text="Skip All Pending", style='TButton',
                  command=self._skip_all_events).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(actions_frame, text="Refresh", style='TButton',
                  command=self._update_display).pack(side=tk.LEFT)
    
    def _create_status_panel(self, parent):
        """Create status overview panel"""
        status_frame = self.parent._create_packed_panel(parent, "📊 Media Status")
        
        # Status display area
        self.status_text = tk.Text(status_frame, height=8, width=40, wrap=tk.WORD,
                                  background=self.parent.CONTENT_BG, foreground=self.parent.TEXT_COLOR,
                                  font=(self.parent.FONT_FAMILY, 9), state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True)
    
    def _create_journalist_panel(self, parent):
        """Create journalist relationship panel"""
        journalist_frame = self.parent._create_packed_panel(parent, "👥 Journalist Relations")
        
        # Journalist list
        columns = {'name': ('Name', 120), 'outlet': ('Outlet', 80), 'type': ('Type', 80), 'relationship': ('Relations', 60)}
        self.journalist_tree = self.parent._create_treeview(journalist_frame, columns, height=6)
        
        # Populate journalists
        for journalist in self.media_system.journalists:
            relationship_str = f"{journalist.relationship:+d}"
            if journalist.relationship > 3:
                relationship_str += " 🟢"
            elif journalist.relationship < -3:
                relationship_str += " 🔴"
            else:
                relationship_str += " 🟡"
            
            self.journalist_tree.insert('', tk.END, values=[
                journalist.name, journalist.outlet, journalist.type.value, relationship_str
            ])
    
    def _create_events_panel(self, parent):
        """Create pending media events panel"""
        events_frame = self.parent._create_packed_panel(parent, "📺 Pending Media Events")
        
        # Events container with scrollbar
        events_container = ttk.Frame(events_frame, style='Panel.TFrame')
        events_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollable frame for events
        canvas = tk.Canvas(events_container, background=self.parent.CONTENT_BG)
        scrollbar = ttk.Scrollbar(events_container, orient=tk.VERTICAL, command=canvas.yview)
        self.events_scroll_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        self.events_scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.events_scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.events_canvas = canvas
    
    def _create_storylines_panel(self, parent):
        """Create active storylines panel"""
        storylines_frame = self.parent._create_packed_panel(parent, "📖 Active Storylines")
        
        # Storylines list
        columns = {'title': ('Storyline', 200), 'type': ('Type', 100), 'intensity': ('Heat', 60), 'days_left': ('Days Left', 80)}
        self.storylines_tree = self.parent._create_treeview(storylines_frame, columns, height=6)
    
    def _populate_events(self):
        """Populate the events scroll area"""
        # Clear existing event widgets
        for widget in self.events_scroll_frame.winfo_children():
            widget.destroy()
        
        pending_events = self.media_system.get_pending_media_events()
        
        if not pending_events:
            # No events message
            no_events_frame = ttk.Frame(self.events_scroll_frame, style='Media.TFrame')
            no_events_frame.pack(fill=tk.X, pady=5, padx=5)
            
            ttk.Label(no_events_frame, text="📰 No pending media events", 
                     style='MediaTitle.TLabel').pack(pady=20)
            ttk.Label(no_events_frame, text="Events will appear here based on your engagement level\nand recent team activities.", 
                     style='MediaContent.TLabel').pack()
            return
        
        # Create event cards
        for i, event in enumerate(pending_events):
            self._create_event_card(self.events_scroll_frame, event, i)
        
        # Update canvas scroll region
        self.events_scroll_frame.update_idletasks()
        self.events_canvas.configure(scrollregion=self.events_canvas.bbox("all"))
    
    def _create_event_card(self, parent, event, index):
        """Create a card for a media event"""
        # Event card frame
        card_frame = ttk.Frame(parent, style='Media.TFrame')
        card_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Event header
        header_frame = ttk.Frame(card_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        # Event type and status
        event_type = event['type'].replace('_', ' ').title()
        type_color = {'post_game_interview': '🎙️', 'trade_announcement': '🔄', 'contract_signing': '📝'}.get(event['type'], '📰')
        
        ttk.Label(header_frame, text=f"{type_color} {event_type}", style='MediaTitle.TLabel').pack(side=tk.LEFT)
        
        optional_text = "OPTIONAL" if event.get('optional', False) else "REQUIRED"
        optional_color = 'green' if event.get('optional', False) else '#FF5722'
        ttk.Label(header_frame, text=optional_text, foreground=optional_color, 
                 style='Content.TLabel').pack(side=tk.RIGHT)
        
        # Journalist info
        journalist = event.get('journalist')
        if journalist:
            journalist_frame = ttk.Frame(card_frame, style='Panel.TFrame')
            journalist_frame.pack(fill=tk.X, padx=10, pady=2)
            
            journalist_text = f"📰 {journalist.name} ({journalist.outlet}) - {journalist.type.value}"
            ttk.Label(journalist_frame, text=journalist_text, style='Journalist.TLabel').pack(side=tk.LEFT)
            
            # Relationship indicator
            rel_text = f"Relationship: {journalist.relationship:+d}"
            rel_color = '#4CAF50' if journalist.relationship > 0 else '#F44336' if journalist.relationship < 0 else '#FFC107'
            ttk.Label(journalist_frame, text=rel_text, foreground=rel_color,
                     style='Content.TLabel').pack(side=tk.RIGHT)
        
        # Questions
        questions = event.get('questions', [])
        if questions:
            questions_frame = ttk.Frame(card_frame, style='Panel.TFrame')
            questions_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(questions_frame, text="Questions:", style='Content.TLabel').pack(anchor=tk.W)
            
            for i, question in enumerate(questions[:2], 1):  # Show first 2 questions
                question_frame = ttk.Frame(questions_frame, style='Panel.TFrame')
                question_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(question_frame, text=f"{i}. {question}", 
                         style='Question.TLabel').pack(anchor=tk.W, padx=(10, 0))
            
            if len(questions) > 2:
                ttk.Label(questions_frame, text=f"+ {len(questions) - 2} more questions...", 
                         style='Small.TLabel').pack(anchor=tk.W, padx=(10, 0))
        
        # Action buttons
        buttons_frame = ttk.Frame(card_frame, style='Panel.TFrame')
        buttons_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        if event.get('optional', False):
            ttk.Button(buttons_frame, text="Skip Interview", style='TButton',
                      command=lambda e=event: self._skip_event(e)).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(buttons_frame, text="Handle Interview", style='TButton',
                  command=lambda e=event: self._handle_event(e)).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(buttons_frame, text="Auto-Handle", style='TButton',
                  command=lambda e=event: self._auto_handle_event(e)).pack(side=tk.RIGHT)
    
    def _populate_storylines(self):
        """Populate the storylines tree"""
        for item in self.storylines_tree.get_children():
            self.storylines_tree.delete(item)
        
        current_date = self.parent.game_manager.current_date
        active_storylines = [s for s in self.media_system.storylines if s.is_active(current_date)]
        
        for storyline in active_storylines:
            days_left = storyline.duration_days - (current_date - storyline.created_date).days
            intensity_display = "🔥" * min(3, storyline.intensity // 3)
            
            self.storylines_tree.insert('', tk.END, values=[
                storyline.title,
                storyline.type.value,
                intensity_display,
                f"{days_left} days"
            ])
    
    def _update_status_text(self):
        """Update the status text display"""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        
        status = self.media_system.get_system_status()
        
        status_content = f"""📊 MEDIA SYSTEM STATUS

🎯 Engagement Level: {status['engagement_level']}
📺 Pending Events: {status['pending_events']}
📖 Active Storylines: {status['active_storylines']}

👤 GM REPUTATION: {status['gm_reputation']}/100
{"🌟 Excellent" if status['gm_reputation'] >= 80 else 
 "😊 Good" if status['gm_reputation'] >= 60 else
 "😐 Average" if status['gm_reputation'] >= 40 else
 "😕 Poor" if status['gm_reputation'] >= 20 else "💀 Terrible"}

👥 AVG JOURNALIST RELATIONS: {status['avg_journalist_relationship']:.1f}
{"🤝 Great relationships" if status['avg_journalist_relationship'] > 2 else
 "📰 Neutral coverage" if status['avg_journalist_relationship'] > -2 else
 "⚡ Hostile media"}

💡 TIP: {"Higher engagement = more storylines but more interactions" if status['engagement_level'] == 'Disabled' else
        "Skip interviews to save time, handle them for better control" if status['pending_events'] > 0 else
        "Media interactions affect team morale and reputation"}"""
        
        self.status_text.insert(1.0, status_content)
        self.status_text.config(state=tk.DISABLED)
    
    def _update_display(self):
        """Update all display elements"""
        # Update header status
        status = self.media_system.get_system_status()
        status_text = f"Level: {status['engagement_level']} | Pending: {status['pending_events']} | Reputation: {status['gm_reputation']}/100"
        self.status_label.config(text=status_text)
        
        # Update all panels
        self._populate_events()
        self._populate_storylines()
        self._update_status_text()
    
    def _on_engagement_change(self):
        """Handle engagement level change"""
        new_level = MediaEngagementLevel(self.engagement_var.get())
        old_level = self.media_system.engagement_level
        
        if new_level != old_level:
            self.media_system.set_engagement_level(new_level)
            self._update_display()
            
            # Show confirmation message
            level_messages = {
                MediaEngagementLevel.DISABLED: "Media system disabled. Focus on pure hockey management!",
                MediaEngagementLevel.MINIMAL: "Minimal media coverage enabled. Major events only.",
                MediaEngagementLevel.STANDARD: "Standard coverage enabled. Pre/post-game interviews included.",
                MediaEngagementLevel.FULL: "Full immersion enabled. Complete storyline experience!"
            }
            
            messagebox.showinfo("Media Settings Updated", level_messages[new_level])
    
    def _on_auto_handle_change(self):
        """Handle auto-handle setting change"""
        self.media_system.auto_handle_minor_events = self.auto_handle_var.get()
    
    def _skip_all_events(self):
        """Skip all pending events"""
        pending = len(self.media_system.get_pending_media_events())
        if pending > 0:
            result = messagebox.askyesno("Skip All Events", 
                                       f"Skip all {pending} pending media events?\n\nThey will be auto-handled professionally.")
            if result:
                self.media_system.skip_all_pending_events()
                self._update_display()
                messagebox.showinfo("Events Skipped", f"All {pending} events handled professionally.")
    
    def _skip_event(self, event):
        """Skip a specific event"""
        self.media_system.handle_media_response(event, 'skipped')
        self._update_display()
    
    def _auto_handle_event(self, event):
        """Auto-handle an event with professional response"""
        self.media_system.handle_media_response(event, 'professional')
        self._update_display()
        messagebox.showinfo("Event Handled", "Interview handled with professional responses.")
    
    def _handle_event(self, event):
        """Open interactive interview window"""
        InterviewWindow(self, event)

class InterviewWindow(tk.Toplevel):
    """Interactive interview window for media events"""
    
    def __init__(self, parent, event):
        super().__init__(parent)
        self.parent = parent
        self.event = event
        
        self.title(f"🎙️ {event['type'].replace('_', ' ').title()}")
        self.configure(background=parent.parent.BG_COLOR)
        self.geometry("800x600")
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_interview_interface()
        self._populate_questions()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def _create_interview_interface(self):
        """Create the interview interface"""
        # Main container
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header with journalist info
        self._create_interview_header(main_frame)
        
        # Questions area
        self._create_questions_area(main_frame)
        
        # Response options
        self._create_response_area(main_frame)
        
        # Action buttons
        self._create_action_buttons(main_frame)
    
    def _create_interview_header(self, parent):
        """Create interview header with context"""
        header_frame = ttk.Frame(parent, style='Media.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        journalist = self.event.get('journalist')
        if journalist:
            # Journalist info
            journalist_text = f"📰 {journalist.name} - {journalist.outlet}"
            ttk.Label(header_frame, text=journalist_text, style='MediaTitle.TLabel').pack(pady=5)
            
            # Journalist type and relationship
            info_frame = ttk.Frame(header_frame, style='Panel.TFrame')
            info_frame.pack(fill=tk.X)
            
            type_text = f"Reporter Type: {journalist.type.value}"
            ttk.Label(info_frame, text=type_text, style='Content.TLabel').pack(side=tk.LEFT)
            
            rel_text = f"Relationship: {journalist.relationship:+d}"
            rel_color = '#4CAF50' if journalist.relationship > 0 else '#F44336' if journalist.relationship < 0 else '#FFC107'
            rel_label = ttk.Label(info_frame, text=rel_text, style='Content.TLabel')
            rel_label.pack(side=tk.RIGHT)
            
            # Context
            context_text = self._get_event_context()
            if context_text:
                ttk.Label(header_frame, text=context_text, style='MediaContent.TLabel').pack(pady=(10, 0))
        
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
    
    def _create_questions_area(self, parent):
        """Create scrollable questions area"""
        questions_label = ttk.Label(parent, text="Interview Questions:", style='MediaTitle.TLabel')
        questions_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Scrollable questions frame
        questions_frame = ttk.Frame(parent, style='Panel.TFrame')
        questions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        canvas = tk.Canvas(questions_frame, background=self.parent.parent.CONTENT_BG, height=250)
        scrollbar = ttk.Scrollbar(questions_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.questions_scroll_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        self.questions_scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.questions_scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.questions_canvas = canvas
    
    def _create_response_area(self, parent):
        """Create response style selection"""
        response_label = ttk.Label(parent, text="Choose Your Response Style:", style='MediaTitle.TLabel')
        response_label.pack(anchor=tk.W, pady=(0, 10))
        
        self.response_var = tk.StringVar(value="professional")
        
        responses = [
            ("professional", "🤝 Professional", "Balanced, diplomatic responses"),
            ("supportive", "💪 Supportive", "Back your players and organization"),
            ("confident", "⭐ Confident", "Express strong confidence in team direction"),
            ("diplomatic", "🧠 Diplomatic", "Avoid controversy, redirect questions"),
            ("honest", "💯 Brutally Honest", "Tell it like it is, consequences be damned"),
            ("dismissive", "🙄 Dismissive", "Short answers, show irritation")
        ]
        
        response_frame = ttk.Frame(parent, style='Panel.TFrame')
        response_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Create response grid
        for i, (value, text, desc) in enumerate(responses):
            row_frame = ttk.Frame(response_frame, style='Panel.TFrame')
            row_frame.pack(fill=tk.X, pady=2)
            
            rb = ttk.Radiobutton(row_frame, text=text, variable=self.response_var, value=value)
            rb.pack(side=tk.LEFT)
            
            desc_label = ttk.Label(row_frame, text=f"- {desc}", style='Small.TLabel')
            desc_label.pack(side=tk.LEFT, padx=(10, 0))
    
    def _create_action_buttons(self, parent):
        """Create action buttons"""
        buttons_frame = ttk.Frame(parent, style='Panel.TFrame')
        buttons_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Preview responses
        ttk.Button(buttons_frame, text="Preview Answers", style='TButton',
                  command=self._preview_responses).pack(side=tk.LEFT, padx=(0, 10))
        
        # Cancel
        ttk.Button(buttons_frame, text="Cancel", style='TButton',
                  command=self.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Submit
        ttk.Button(buttons_frame, text="Give Interview", style='TButton',
                  command=self._submit_interview).pack(side=tk.RIGHT)
    
    def _populate_questions(self):
        """Populate questions in the scroll area"""
        questions = self.event.get('questions', [])
        
        for i, question in enumerate(questions, 1):
            question_frame = ttk.Frame(self.questions_scroll_frame, style='Media.TFrame')
            question_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Question number and text
            num_label = ttk.Label(question_frame, text=f"Q{i}:", style='MediaTitle.TLabel')
            num_label.pack(anchor=tk.NW, padx=(10, 0), pady=(10, 5))
            
            question_label = ttk.Label(question_frame, text=question, style='Question.TLabel')
            question_label.pack(anchor=tk.W, padx=(25, 10), pady=(0, 10))
        
        # Update canvas
        self.questions_scroll_frame.update_idletasks()
        self.questions_canvas.configure(scrollregion=self.questions_canvas.bbox("all"))
    
    def _get_event_context(self):
        """Get contextual information for the interview"""
        event_type = self.event['type']
        
        if event_type == 'post_game_interview':
            game_result = self.event.get('game_result', {})
            if game_result.get('won', False):
                return f"🎉 Post-game interview following your team's victory"
            else:
                return f"😔 Post-game interview following your team's loss"
        elif event_type == 'trade_announcement':
            return f"🔄 Press conference to discuss recent trade"
        elif event_type == 'contract_signing':
            player = self.event.get('player')
            if player:
                return f"📝 Media availability regarding {player.full_name}'s contract"
        
        return "📰 Media availability"
    
    def _preview_responses(self):
        """Show preview of how answers would sound"""
        response_style = self.response_var.get()
        questions = self.event.get('questions', [])
        
        if not questions:
            messagebox.showinfo("No Questions", "No questions to preview.")
            return
        
        preview_window = tk.Toplevel(self)
        preview_window.title("Response Preview")
        preview_window.configure(background=self.parent.parent.BG_COLOR)
        preview_window.geometry("600x400")
        preview_window.transient(self)
        
        # Preview content
        preview_frame = ttk.Frame(preview_window, style='Panel.TFrame')
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        ttk.Label(preview_frame, text=f"Preview: {response_style.title()} Style", 
                 style='MediaTitle.TLabel').pack(pady=(0, 10))
        
        # Scrollable preview
        text_widget = tk.Text(preview_frame, wrap=tk.WORD, height=20, width=70,
                             background=self.parent.parent.CONTENT_BG, 
                             foreground=self.parent.parent.TEXT_COLOR,
                             font=(self.parent.parent.FONT_FAMILY, 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Generate sample responses
        preview_content = self._generate_sample_responses(questions[:2], response_style)
        text_widget.insert(1.0, preview_content)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(preview_frame, text="Close Preview", 
                  command=preview_window.destroy).pack(pady=(10, 0))
    
    def _generate_sample_responses(self, questions, style):
        """Generate sample responses in the chosen style"""
        responses = []
        
        response_templates = {
            'professional': [
                "We're focused on continuing to improve as a team.",
                "I have confidence in our players and our system.",
                "We'll evaluate our options and make the best decisions for the organization."
            ],
            'supportive': [
                "I couldn't be prouder of how our guys competed tonight.",
                "This group has tremendous character and we believe in them.",
                "Our players give everything they have every single night."
            ],
            'confident': [
                "We know exactly where we're headed and we're excited about it.",
                "This team has what it takes to compete at the highest level.",
                "We're building something special here."
            ],
            'diplomatic': [
                "That's something we'll discuss internally.",
                "Our focus remains on the next game and getting better each day.",
                "We prefer to keep those conversations private."
            ],
            'honest': [
                "Look, we didn't execute tonight and that's on everyone.",
                "Some tough decisions need to be made if we want to win.",
                "The results speak for themselves - we need to be better."
            ],
            'dismissive': [
                "Next question.",
                "We've addressed this already.",
                "I'm not getting into that."
            ]
        }
        
        sample_responses = response_templates.get(style, response_templates['professional'])
        
        preview = f"Response Style: {style.title()}\n{'=' * 40}\n\n"
        
        for i, question in enumerate(questions, 1):
            response = sample_responses[min(i-1, len(sample_responses)-1)]
            preview += f"Q{i}: {question}\n\n"
            preview += f"A{i}: {response}\n\n"
            preview += "-" * 40 + "\n\n"
        
        return preview
    
    def _submit_interview(self):
        """Submit the interview response"""
        response_style = self.response_var.get()
        
        # Handle the media response
        self.parent.media_system.handle_media_response(self.event, response_style)
        
        # Show result
        impact_messages = {
            'low': "Your response was noted by the media.",
            'medium': "Your response will be discussed in tomorrow's coverage.",
            'high': "Your response is making headlines across the hockey world."
        }
        
        impact_level = self.event.get('impact_level', 'low')
        messagebox.showinfo("Interview Complete", 
                          f"Interview completed successfully!\n\n{impact_messages[impact_level]}")
        
        # Update parent and close
        self.parent._update_display()
        self.destroy()