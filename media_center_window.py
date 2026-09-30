# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# media_center_window.py
# Media Center UI for the optional Media & Press Conference System
# CustomTkinter rebuild: CTkToplevel chrome, styled dark treeviews for
# journalists/storylines, rounded event cards in a CTkScrollableFrame.

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup, confirm_card
from media_system import (MediaSystem, MediaEngagementLevel)

import customtkinter as ctk


class MediaCenterView(ctk.CTkFrame):
    """Media Center - Optional immersive media interactions"""

    _ENGAGEMENT_DESCRIPTIONS = {
        "Disabled": "No media interactions - pure hockey management",
        "Minimal": "Major events only (trades, big signings)",
        "Standard": "Pre/post-game + major events",
        "Full Immersion": "Complete storylines & all interactions",
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
        self._close_screen = None  # set by show_screen() or the MediaCenterWindow wrapper
        self.configure(fg_color=BG)

        # Initialize media system if not exists
        if not hasattr(self.app.game_manager, 'media_system'):
            self.app.game_manager.media_system = MediaSystem(self.app.game_manager)

        self.media_system = self.app.game_manager.media_system

        self._setup_tree_style()
        self._create_interface()
        self._update_display()

        # Add to tracked windows
        self.app.open_windows['media_center'] = self

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _on_closing(self):
        """Remove self from tracked windows on close."""
        try:
            if 'media_center' in self.app.open_windows:
                del self.app.open_windows['media_center']
        except Exception:
            pass
        self.close_view()

    # ------------------------------------------------------------------
    # Styling helpers
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """Dark, flat styling for the journalist/storyline lists (styled
        ttk.Treeview per the migration guide)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Media.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=26,
                        font=('Segoe UI', 10))
        style.configure('Media.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Media.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('Media.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('Media.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Media.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])

    def _card(self, parent, **kw):
        """Rounded content card (used selectively -- not on everything)."""
        ct = self._ct
        return ctk.CTkFrame(parent, fg_color=ct['CARD'], corner_radius=12, **kw)

    # ------------------------------------------------------------------
    # Interface construction
    # ------------------------------------------------------------------
    def _create_interface(self):
        ct = self._ct

        main_container = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main_container.pack(fill='both', expand=True, padx=15, pady=15)

        # Header card: title + live status
        self._create_header(main_container)

        # Two-column layout (replaces ttk.PanedWindow)
        columns = ctk.CTkFrame(main_container, fg_color="transparent")
        columns.pack(fill='both', expand=True, pady=(12, 0))
        columns.grid_columnconfigure(0, weight=1)
        columns.grid_columnconfigure(1, weight=2)
        columns.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(columns, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        right_panel = ctk.CTkFrame(columns, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky='nsew', padx=(6, 0))

        # Left: settings, status, journalists
        self._create_settings_panel(left_panel)
        self._create_status_panel(left_panel)
        self._create_journalist_panel(left_panel)

        # Right: events, storylines
        self._create_events_panel(right_panel)
        self._create_storylines_panel(right_panel)

    def _create_header(self, parent):
        """Header card with title and quick status."""
        header = self._card(parent)
        header.pack(fill='x', pady=(0, 0))
        self._heading(header, "Media Center", size=20).pack(
            side='left', padx=16, pady=12)
        self.status_label = self._body(header, "", size=12, dim=True)
        self.status_label.pack(side='right', padx=16, pady=12)

    def _create_settings_panel(self, parent):
        """Media engagement settings card."""
        ct = self._ct
        card = self._card(parent)
        card.pack(fill='x', pady=(0, 10))
        self._heading(card, "Media Settings", size=14).pack(
            anchor='w', padx=14, pady=(12, 6))

        # Engagement level dropdown (CTkComboBox per theme rules)
        self._body(card, "Choose your media engagement level:", size=11,
                   dim=True).pack(anchor='w', padx=14)
        values = [lvl.value for lvl in MediaEngagementLevel]
        self.engagement_var = tk.StringVar(
            value=self.media_system.engagement_level.value)
        self.engagement_combo = ctk.CTkComboBox(
            card, values=values, variable=self.engagement_var,
            command=self._on_engagement_change,
            width=260, fg_color=ct['PANEL'], border_color=ct['BORDER'])
        self.engagement_combo.pack(anchor='w', padx=14, pady=(6, 2))
        self.engagement_desc = self._body(
            card, self._ENGAGEMENT_DESCRIPTIONS.get(
                self.engagement_var.get(), ""), size=11, dim=True)
        self.engagement_desc.pack(anchor='w', padx=14, pady=(0, 8))

        # Auto-handle option
        self.auto_handle_var = tk.BooleanVar(
            value=self.media_system.auto_handle_minor_events)
        ctk.CTkCheckBox(
            card, text="Auto-handle routine interviews",
            variable=self.auto_handle_var,
            command=self._on_auto_handle_change,
            text_color=ct['TEXT'], font=('Segoe UI', 11)).pack(
                anchor='w', padx=14, pady=(0, 8))

        # Quick actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill='x', padx=14, pady=(0, 14))
        self._secondary_button(
            actions, "Skip All Pending",
            command=self._skip_all_events).pack(side='left', padx=(0, 8))
        self._secondary_button(
            actions, "Refresh",
            command=self._update_display).pack(side='left')

    def _create_status_panel(self, parent):
        """Media status overview card with read-only text."""
        ct = self._ct
        card = self._card(parent)
        card.pack(fill='x', pady=(0, 10))
        self._heading(card, "Media Status", size=14).pack(
            anchor='w', padx=14, pady=(12, 6))
        self.status_text = ctk.CTkTextbox(
            card, height=170, wrap='word', corner_radius=8,
            fg_color=ct['PANEL'], border_color=ct['BORDER'], border_width=1,
            text_color=ct['TEXT'], font=('Segoe UI', 10))
        self.status_text.pack(fill='x', padx=14, pady=(0, 14))
        self.status_text.configure(state='disabled')

    @staticmethod
    def _relationship_descriptor(rel):
        if rel >= 4:
            return "Warm"
        if rel >= 1:
            return "Cordial"
        if rel == 0:
            return "Neutral"
        if rel >= -3:
            return "Cool"
        return "Hostile"

    def _journalist_summary(self):
        """One-line climate summary from real journalist relationship data."""
        journalists = self.media_system.journalists
        if not journalists:
            return "No journalists covering the team yet."
        avg = sum(j.relationship for j in journalists) / len(journalists)
        friendly = max(journalists, key=lambda j: j.relationship)
        harsh = min(journalists, key=lambda j: j.relationship)
        climate = ("Warm coverage" if avg > 2 else
                   "Neutral coverage" if avg > -2 else "Hostile coverage")
        return (f"Coverage climate: {climate} (avg {avg:+.1f}). "
                f"Friendliest: {friendly.name} ({friendly.relationship:+d}). "
                f"Harshest: {harsh.name} ({harsh.relationship:+d}).")

    def _create_journalist_panel(self, parent):
        """Journalist relationship card with dark styled treeview."""
        card = self._card(parent)
        card.pack(fill='both', expand=True)
        self._heading(card, "Journalist Relations", size=14).pack(
            anchor='w', padx=14, pady=(12, 4))

        self._body(card, self._journalist_summary(), size=11, dim=True).pack(
            anchor='w', padx=14, pady=(0, 8))

        columns = {'name': ('Name', 130), 'outlet': ('Outlet', 80),
                   'type': ('Type', 90), 'relationship': ('Relations', 120)}
        self.journalist_tree = self._make_tree(card, columns, height_rows=5)

        for journalist in self.media_system.journalists:
            relationship_str = (f"{journalist.relationship:+d} "
                                f"({self._relationship_descriptor(journalist.relationship)})")
            self.journalist_tree.insert('', tk.END, values=[
                journalist.name, journalist.outlet, journalist.type.value,
                relationship_str
            ])

    def _make_tree(self, parent, columns, height_rows=6):
        """Build a styled dark ttk.Treeview with a matching scrollbar."""
        ct = self._ct
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill='both', expand=True, padx=14, pady=(0, 14))
        cols = list(columns.keys())
        tree = ttk.Treeview(frame, columns=cols, show='headings',
                            style='Media.Treeview',
                            height=height_rows)
        for key, (label, width) in columns.items():
            tree.heading(key, text=label, anchor='w')
            tree.column(key, width=width, anchor='w')
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                  command=tree.yview,
                                  style='Media.Vertical.TScrollbar')
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        return tree

    def _create_events_panel(self, parent):
        """Pending media events card with scrollable event cards."""
        card = self._card(parent)
        card.pack(fill='both', expand=True, pady=(0, 10))
        self._heading(card, "Pending Media Events", size=14).pack(
            anchor='w', padx=14, pady=(12, 6))
        self.events_frame = ctk.CTkScrollableFrame(
            card, fg_color="transparent", height=280, corner_radius=8)
        self.events_frame.pack(fill='both', expand=True, padx=14,
                               pady=(0, 14))

    def _create_storylines_panel(self, parent):
        """Active storylines card with dark styled treeview + empty state."""
        card = self._card(parent)
        card.pack(fill='x')
        self._heading(card, "Active Storylines", size=14).pack(
            anchor='w', padx=14, pady=(12, 4))

        columns = {'title': ('Storyline', 220), 'type': ('Type', 130),
                   'intensity': ('Heat', 70), 'days_left': ('Days Left', 80)}
        self.storylines_tree = self._make_tree(card, columns, height_rows=5)

        self.storylines_empty = self._body(card, "", size=11, dim=True)
        self.storylines_empty.pack(anchor='w', padx=14, pady=(0, 10))

    # ------------------------------------------------------------------
    # Backend event-shape adapter
    # ------------------------------------------------------------------
    def _event_view(self, event):
        """Return a uniform dict-like view of a pending media event.

        media_system.py is inconsistent internally: ``get_pending_media_events``
        yields ``MediaEvent`` dataclasses (attribute access), while
        ``handle_media_response`` treats events as dicts (item access), and
        ``_generate_post_game_media_event``-style events are plain dicts.
        Normalize here (media_system.py is intentionally not touched) so the
        UI never crashes on either shape.
        """
        if isinstance(event, dict):
            return dict(event)
        details = getattr(event, 'details', None) or {}
        questions = []
        if hasattr(self.media_system, 'get_interview_questions'):
            try:
                questions = self.media_system.get_interview_questions(event)
            except Exception:
                questions = []
        importance = getattr(event, 'importance', 5) or 5
        return {
            'type': getattr(event, 'type', 'media_event'),
            'journalist': details.get('journalist'),
            'questions': questions,
            'optional': bool(getattr(event, 'auto_handled', False)),
            'impact_level': ('low' if importance < 4 else
                             'medium' if importance < 7 else 'high'),
            'details': details,
        }

    def _resolve_event(self, event, response_choice):
        """Process a response via media_system, tolerating its dict/object
        inconsistency for ``MediaEvent`` dataclasses."""
        try:
            self.media_system.handle_media_response(event, response_choice)
        except (TypeError, KeyError, AttributeError):
            # The backend's dict-style access trips on MediaEvent objects
            # (produced by process_trade/process_signing); mark completed
            # directly instead of crashing.
            if hasattr(event, 'completed'):
                event.completed = True

    # ------------------------------------------------------------------
    # Population / display updates
    # ------------------------------------------------------------------
    def _populate_events(self):
        """Rebuild the event cards in the scroll area."""
        for widget in self.events_frame.winfo_children():
            widget.destroy()

        pending_events = self.media_system.get_pending_media_events()

        if not pending_events:
            empty = self._card(self.events_frame)
            empty.pack(fill='x', pady=6, padx=4)
            self._heading(empty, "No pending media events", size=14).pack(
                pady=(18, 4))
            self._body(empty,
                       "Events will appear here based on your engagement "
                       "level\nand recent team activities.",
                       size=11, dim=True).pack(pady=(0, 18))
            return

        for event in pending_events:
            self._create_event_card(self.events_frame, event)

    def _create_event_card(self, parent, event):
        """Create a rounded card for a single media event."""
        ct = self._ct
        view = self._event_view(event)
        card = self._card(parent)
        card.pack(fill='x', pady=6, padx=4)

        # Header row: event type + required/optional badge
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill='x', padx=14, pady=(12, 4))
        event_type = view['type'].replace('_', ' ').title()
        self._heading(header_row, event_type, size=13).pack(side='left')
        if view.get('optional', False):
            badge_text, badge_color = "OPTIONAL", ct['GREEN']
        else:
            badge_text, badge_color = "REQUIRED", "#FF5722"
        ctk.CTkLabel(header_row, text=badge_text, text_color=badge_color,
                     font=('Segoe UI', 10, 'bold')).pack(side='right')

        # Journalist info
        journalist = view.get('journalist')
        if journalist:
            jrow = ctk.CTkFrame(card, fg_color="transparent")
            jrow.pack(fill='x', padx=14, pady=2)
            ctk.CTkLabel(
                jrow,
                text=f"{journalist.name} ({journalist.outlet}) - "
                     f"{journalist.type.value}",
                text_color='#FFB300', font=('Segoe UI', 10, 'bold')).pack(
                    side='left')
            rel_color = (ct['GREEN'] if journalist.relationship > 0
                         else ct['RED'] if journalist.relationship < 0
                         else ct['GOLD'])
            ctk.CTkLabel(
                jrow, text=f"Relationship: {journalist.relationship:+d}",
                text_color=rel_color,
                font=('Segoe UI', 10)).pack(side='right')

        # Questions (first two)
        questions = view.get('questions', [])
        if questions:
            self._body(card, "Questions:", size=11, dim=True).pack(
                anchor='w', padx=14, pady=(6, 0))
            for i, question in enumerate(questions[:2], 1):
                self._body(card, f"{i}. {question}", size=11).pack(
                    anchor='w', padx=(24, 14), pady=1)
            if len(questions) > 2:
                self._body(card, f"+ {len(questions) - 2} more questions...",
                           size=10, dim=True).pack(
                    anchor='w', padx=(24, 14), pady=(2, 0))

        # Action buttons
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill='x', padx=14, pady=(10, 14))
        if view.get('optional', False):
            self._secondary_button(
                buttons, "Skip Interview",
                command=lambda e=event: self._skip_event(e)).pack(
                    side='left', padx=(0, 8))
        self._primary_button(
            buttons, "Handle Interview",
            command=lambda e=event, v=view: self._handle_event(e, v)).pack(
                side='left', padx=(0, 8))
        self._secondary_button(
            buttons, "Auto-Handle",
            command=lambda e=event: self._auto_handle_event(e)).pack(
                side='right')

    def _populate_storylines(self):
        """Populate the storylines tree."""
        for item in self.storylines_tree.get_children():
            self.storylines_tree.delete(item)

        current_date = self.app.game_manager.current_date
        active_storylines = [s for s in self.media_system.storylines
                             if s.is_active(current_date)]

        for storyline in active_storylines:
            days_left = storyline.duration_days - \
                (current_date - storyline.created_date).days
            intensity = storyline.intensity
            heat = "High" if intensity >= 7 else "Medium" if intensity >= 4 \
                else "Low"
            self.storylines_tree.insert('', tk.END, values=[
                storyline.title,
                storyline.type.value,
                heat,
                f"{days_left} days"
            ])

        if not active_storylines:
            self.storylines_empty.configure(
                text="No active storylines right now. Storylines are "
                     "generated from trades, streaks and signings when your "
                     "engagement level is above Minimal.")
        else:
            self.storylines_empty.configure(text="")

    def _update_status_text(self):
        """Update the status text display."""
        self.status_text.configure(state='normal')
        self.status_text.delete('1.0', tk.END)

        status = self.media_system.get_system_status()
        journalists = self.media_system.journalists

        rep = status['gm_reputation']
        rep_label = ("Excellent" if rep >= 80 else "Good" if rep >= 60 else
                     "Average" if rep >= 40 else "Poor" if rep >= 20 else
                     "Terrible")
        avg_rel = status['avg_journalist_relationship']
        rel_label = ("Warm coverage" if avg_rel > 2 else
                     "Neutral coverage" if avg_rel > -2 else "Hostile coverage")

        extra = ""
        if journalists:
            friendly = max(journalists, key=lambda j: j.relationship)
            harsh = min(journalists, key=lambda j: j.relationship)
            extra = (f"\nFriendliest voice: {friendly.name} ({friendly.outlet}, "
                     f"{friendly.relationship:+d})"
                     f"\nHarshest critic: {harsh.name} ({harsh.outlet}, "
                     f"{harsh.relationship:+d})")

        status_content = f"""MEDIA SYSTEM STATUS

Engagement Level: {status['engagement_level']}
Pending Events: {status['pending_events']}
Active Storylines: {status['active_storylines']}

GM REPUTATION: {rep}/100 ({rep_label})
AVG JOURNALIST RELATIONS: {avg_rel:.1f} ({rel_label}){extra}

TIP: {"Higher engagement = more storylines but more interactions" if status['engagement_level'] == 'Disabled' else
        "Skip interviews to save time, handle them for better control" if status['pending_events'] > 0 else
        "Media interactions affect team morale and reputation"}"""

        self.status_text.insert('1.0', status_content)
        self.status_text.configure(state='disabled')

    def _update_display(self):
        """Update all display elements."""
        # Update header status
        status = self.media_system.get_system_status()
        status_text = (f"Level: {status['engagement_level']} | Pending: "
                       f"{status['pending_events']} | Reputation: "
                       f"{status['gm_reputation']}/100")
        self.status_label.configure(text=status_text)

        # Keep engagement controls in sync with backend state
        self.engagement_var.set(self.media_system.engagement_level.value)
        self.engagement_desc.configure(
            text=self._ENGAGEMENT_DESCRIPTIONS.get(
                self.engagement_var.get(), ""))
        self.auto_handle_var.set(self.media_system.auto_handle_minor_events)

        # Update all panels
        self._populate_events()
        self._populate_storylines()
        self._update_status_text()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_engagement_change(self, new_value=None):
        """Handle engagement level change."""
        value = new_value if new_value is not None else self.engagement_var.get()
        new_level = MediaEngagementLevel(value)
        old_level = self.media_system.engagement_level

        self.engagement_desc.configure(
            text=self._ENGAGEMENT_DESCRIPTIONS.get(value, ""))

        if new_level != old_level:
            self.media_system.set_engagement_level(new_level)
            self._update_display()

            level_messages = {
                MediaEngagementLevel.DISABLED:
                    "Media system disabled. Focus on pure hockey management!",
                MediaEngagementLevel.MINIMAL:
                    "Minimal media coverage enabled. Major events only.",
                MediaEngagementLevel.STANDARD:
                    "Standard coverage enabled. Pre/post-game interviews included.",
                MediaEngagementLevel.FULL:
                    "Full immersion enabled. Complete storyline experience!"
            }

            messagebox.showinfo("Media Settings Updated",
                                level_messages[new_level])

    def _on_auto_handle_change(self):
        """Handle auto-handle setting change."""
        self.media_system.auto_handle_minor_events = self.auto_handle_var.get()

    def _skip_all_events(self):
        """Skip all pending events."""
        pending = len(self.media_system.get_pending_media_events())
        if pending > 0:
            # Gating T2-Phase 3: non-modal confirm; dismiss = keep events.
            confirm_card(self, "Skip All Events",
                         f"Skip all {pending} pending media events?\n\n"
                         "They will be auto-handled professionally.",
                         on_yes=self._skip_all_events_confirmed)

    def _skip_all_events_confirmed(self):
        """Skip all pending events after the user confirmed."""
        pending = len(self.media_system.get_pending_media_events())
        self.media_system.skip_all_pending_events()
        self._update_display()
        messagebox.showinfo("Events Skipped",
                            f"All {pending} events handled "
                            "professionally.")

    def _skip_event(self, event):
        """Skip a specific event."""
        self._resolve_event(event, 'skipped')
        self._update_display()

    def _auto_handle_event(self, event):
        """Auto-handle an event with professional response."""
        self._resolve_event(event, 'professional')
        self._update_display()
        messagebox.showinfo("Event Handled",
                            "Interview handled with professional responses.")

    def _handle_event(self, event, view=None):
        """Open the interactive interview as an embedded screen."""
        self.app.show_screen(
            'interview', 'Interview', InterviewView,
            view if view is not None else self._event_view(event),
            event, media_view=self)

class MediaCenterWindow(InGamePopup):
    """Popup wrapper around MediaCenterView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Media Center")
        self._view = MediaCenterView(self, app=parent, *args, **kwargs)
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
class InterviewView(ctk.CTkFrame):
    """Interactive interview for media events, as an embedded focus card."""

    def __init__(self, parent, event, raw_event=None, app=None,
                 media_view=None, on_done=None, _response_style=None):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GREEN, RED, GOLD,
        )
        self._ct = dict(TEAL=TEAL, BG=BG, PANEL=PANEL, CARD=CARD,
                        BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GREEN=GREEN, RED=RED, GOLD=GOLD)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()

        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the InterviewWindow wrapper
        self.event = event          # uniform dict-like view (display)
        self.raw_event = raw_event if raw_event is not None else event
        self.media_view = media_view  # MediaCenterView that owns event resolution
        self.on_done = on_done
        self._response_style = _response_style or "professional"

        self.configure(fg_color=BG)

        self._create_interview_interface()
        self._populate_questions()
        try:
            self.response_var.set(self._response_style)
        except Exception:
            pass

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _screen_mgr(self):
        """The app-level screen manager (owns show_screen)."""
        mv = self.media_view
        if mv is not None:
            mgr_app = getattr(mv, "app", None)
            if mgr_app is not None and hasattr(mgr_app, "show_screen"):
                return mgr_app
        if hasattr(self.app, "show_screen"):
            return self.app
        return None

    def _card(self, parent, **kw):
        # Sub-cards use PANEL so they stand out against the CARD focus card.
        ct = self._ct
        return ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12, **kw)

    def _create_interview_interface(self):
        """Create the interview interface inside a centered focus card."""
        ct = self._ct
        # Focus card: full-screen view, content in a centered card.
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(expand=True, fill="both")
        card_holder = ctk.CTkFrame(center, fg_color=ct['BG'], corner_radius=0)
        card_holder.pack(expand=True, padx=24, pady=24)
        main = ctk.CTkFrame(card_holder, fg_color=ct['CARD'],
                            corner_radius=12, width=700)
        main.pack(padx=2, pady=2)

        self._create_interview_header(main)
        self._create_questions_area(main)
        self._create_response_area(main)
        self._create_action_buttons(main)

    def _create_interview_header(self, parent):
        """Header card with journalist context."""
        ct = self._ct
        card = self._card(parent)
        card.pack(fill='x', pady=(0, 12))

        journalist = self.event.get('journalist')
        if journalist:
            self._body(
                card, f"{journalist.name} - {journalist.outlet}",
                size=13).pack(anchor='w', padx=14, pady=(12, 2))
            info_row = ctk.CTkFrame(card, fg_color="transparent")
            info_row.pack(fill='x', padx=14, pady=(0, 4))
            self._body(info_row,
                       f"Reporter Type: {journalist.type.value}",
                       size=11, dim=True).pack(side='left')
            rel_color = (ct['GREEN'] if journalist.relationship > 0
                         else ct['RED'] if journalist.relationship < 0
                         else ct['GOLD'])
            ctk.CTkLabel(
                info_row, text=f"Relationship: {journalist.relationship:+d}",
                text_color=rel_color,
                font=('Segoe UI', 11)).pack(side='right')

            context_text = self._get_event_context()
            if context_text:
                self._body(card, context_text, size=11, dim=True).pack(
                    anchor='w', padx=14, pady=(0, 12))

    def _create_questions_area(self, parent):
        """Scrollable questions card."""
        card = self._card(parent)
        card.pack(fill='both', expand=True, pady=(0, 12))
        self._heading(card, "Interview Questions", size=14).pack(
            anchor='w', padx=14, pady=(12, 6))
        self.questions_frame = ctk.CTkScrollableFrame(
            card, fg_color="transparent", height=200, corner_radius=8)
        self.questions_frame.pack(fill='both', expand=True, padx=14,
                                  pady=(0, 14))

    def _create_response_area(self, parent):
        """Response style selection card."""
        ct = self._ct
        card = self._card(parent)
        card.pack(fill='x', pady=(0, 12))
        self._heading(card, "Choose Your Response Style", size=14).pack(
            anchor='w', padx=14, pady=(12, 4))

        self.response_var = tk.StringVar(value="professional")

        responses = [
            ("professional", "Professional",
             "Balanced, diplomatic responses"),
            ("supportive", "Supportive",
             "Back your players and organization"),
            ("confident", "Confident",
             "Express strong confidence in team direction"),
            ("diplomatic", "Diplomatic",
             "Avoid controversy, redirect questions"),
            ("honest", "Brutally Honest",
             "Tell it like it is, consequences be damned"),
            ("dismissive", "Dismissive",
             "Short answers, show irritation")
        ]

        for i, (value, text, desc) in enumerate(responses):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill='x', padx=14, pady=1)
            ctk.CTkRadioButton(row, text=text, variable=self.response_var,
                              value=value, text_color=ct['TEXT'],
                              font=('Segoe UI', 11)).pack(side='left')
            self._body(row, f"- {desc}", size=10, dim=True).pack(
                side='left', padx=(10, 0))
        # Bottom padding
        ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

    def _create_action_buttons(self, parent):
        """Action buttons row."""
        buttons = ctk.CTkFrame(parent, fg_color="transparent")
        buttons.pack(fill='x', padx=15, pady=(0, 15))
        self._secondary_button(
            buttons, "Preview Answers",
            command=self._preview_responses).pack(side='left')
        self._secondary_button(
            buttons, "Cancel", command=self.close_view).pack(
                side='right', padx=(8, 0))
        self._primary_button(
            buttons, "Give Interview",
            command=self._submit_interview).pack(side='right')

    def _populate_questions(self):
        """Populate questions in the scroll area."""
        questions = self.event.get('questions', [])

        for i, question in enumerate(questions, 1):
            qcard = self._card(self.questions_frame)
            qcard.pack(fill='x', pady=5, padx=4)
            self._heading(qcard, f"Q{i}:", size=12).pack(
                anchor='w', padx=12, pady=(10, 2))
            self._body(qcard, question, size=11).pack(
                anchor='w', padx=22, pady=(0, 10))

    def _get_event_context(self):
        """Get contextual information for the interview."""
        event_type = self.event['type']

        if event_type == 'post_game_interview':
            game_result = self.event.get('game_result', {})
            if game_result.get('won', False):
                return "Post-game interview following your team's victory"
            else:
                return "Post-game interview following your team's loss"
        elif event_type == 'trade_announcement':
            return "Press conference to discuss recent trade"
        elif event_type == 'contract_signing':
            player = self.event.get('player')
            if player:
                return f"Media availability regarding {player.full_name}'s contract"

        return "Media availability"

    def _preview_responses(self):
        """Show preview of how answers would sound (as a screen)."""
        response_style = self.response_var.get()
        questions = self.event.get('questions', [])

        if not questions:
            messagebox.showinfo("No Questions", "No questions to preview.")
            return

        mgr = self._screen_mgr()
        if mgr is None:
            return
        mgr.show_screen('response_preview', 'Response Preview', PreviewView,
                        response_style, questions,
                        interview_event=self.event,
                        interview_raw_event=self.raw_event,
                        media_view=self.media_view,
                        on_done=self.on_done)

    def _generate_sample_responses(self, questions, style):
        """Generate sample responses in the chosen style."""
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

        sample_responses = response_templates.get(
            style, response_templates['professional'])

        preview = f"Response Style: {style.title()}\n{'=' * 40}\n\n"

        for i, question in enumerate(questions, 1):
            response = sample_responses[min(i-1, len(sample_responses)-1)]
            preview += f"Q{i}: {question}\n\n"
            preview += f"A{i}: {response}\n\n"
            preview += "-" * 40 + "\n\n"

        return preview

    def _submit_interview(self):
        """Submit the interview response."""
        response_style = self.response_var.get()

        # Handle the media response (tolerates dict/object backend mismatch)
        mv = self.media_view
        if mv is not None:
            try:
                mv._resolve_event(self.raw_event, response_style)
            except Exception:
                pass

        # Show result
        impact_messages = {
            'low': "Your response was noted by the media.",
            'medium': "Your response will be discussed in tomorrow's coverage.",
            'high': "Your response is making headlines across the hockey world."
        }

        impact_level = self.event.get('impact_level', 'low')
        messagebox.showinfo("Interview Complete",
                            "Interview completed successfully!\n\n"
                            f"{impact_messages[impact_level]}")

        # Update the media center view, then report completion and close
        if mv is not None:
            try:
                mv._update_display()
            except Exception:
                pass
        cb = getattr(self, "on_done", None)
        if callable(cb):
            try:
                cb(response_style)
            except Exception:
                pass
        self.close_view()


class InterviewWindow(InGamePopup):
    """Popup wrapper around InterviewView (backward compatibility)."""
    def __init__(self, parent, event, raw_event=None, on_done=None):
        super().__init__(parent)
        media_view = parent if hasattr(parent, "_resolve_event") else None
        app = parent if media_view is None else None
        self._view = InterviewView(self, event, raw_event, app=app,
                                   media_view=media_view, on_done=on_done)
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


class PreviewView(ctk.CTkFrame):
    """Read-only preview of sample answers, as an embedded focus card.

    Closing returns to the interview screen (rebuilt with the same event
    and response style), mirroring the old modal-over-interview flow.
    """

    def __init__(self, parent, response_style, questions, app=None,
                 interview_event=None, interview_raw_event=None,
                 media_view=None, on_done=None):
        from ctk_theme import (
            init_ctk_theme, secondary_button, heading, body,
            BG, CARD, PANEL, BORDER, TEXT,
        )
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        self._ct = dict(BG=BG, CARD=CARD, PANEL=PANEL, BORDER=BORDER,
                        TEXT=TEXT)
        init_ctk_theme()

        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the PreviewWindow wrapper
        self.response_style = response_style
        self.questions = questions
        self.interview_event = interview_event
        self.interview_raw_event = interview_raw_event
        self.media_view = media_view
        self.on_done = on_done
        self.configure(fg_color=BG)

        # Focus card: full-screen view, content in a centered card.
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(expand=True, fill="both")
        card_holder = ctk.CTkFrame(center, fg_color=BG, corner_radius=0)
        card_holder.pack(expand=True, padx=24, pady=24)
        main = ctk.CTkFrame(card_holder, fg_color=CARD, corner_radius=12,
                            width=620)
        main.pack(padx=2, pady=2)

        card = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12)
        card.pack(fill='both', expand=True, padx=15, pady=(15, 12))
        self._heading(card, f"Preview: {response_style.title()} Style",
                      size=16).pack(anchor='w', padx=14, pady=(12, 8))

        text_widget = ctk.CTkTextbox(
            card, wrap='word', corner_radius=8,
            fg_color=BG, border_color=BORDER, border_width=1,
            text_color=TEXT, font=('Segoe UI', 10))
        text_widget.pack(fill='both', expand=True, padx=14, pady=(0, 14))

        preview_content = self._sample_responses()
        text_widget.insert('1.0', preview_content)
        text_widget.configure(state='disabled')

        self._secondary_button(main, "Close Preview",
                               command=self._close).pack(pady=(0, 15))

    def _sample_responses(self):
        """Generate sample responses via the interview's template engine."""
        try:
            # _generate_sample_responses is pure (uses only its arguments).
            return InterviewView._generate_sample_responses(
                None, self.questions[:2], self.response_style)
        except Exception:
            return ""

    def _close(self):
        """Return to the interview screen (or dashboard if unavailable)."""
        mgr = self._screen_mgr()
        if (mgr is not None and self.interview_event is not None):
            mgr.show_screen('interview', 'Interview', InterviewView,
                            self.interview_event, self.interview_raw_event,
                            media_view=self.media_view, on_done=self.on_done,
                            _response_style=self.response_style)
        else:
            self.close_view()

    def _screen_mgr(self):
        mv = self.media_view
        if mv is not None:
            mgr_app = getattr(mv, "app", None)
            if mgr_app is not None and hasattr(mgr_app, "show_screen"):
                return mgr_app
        if hasattr(self.app, "show_screen"):
            return self.app
        return None

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()


class PreviewWindow(InGamePopup):
    """Popup wrapper around PreviewView (backward compatibility)."""
    def __init__(self, parent, response_style, questions):
        super().__init__(parent)
        interview_view = parent if hasattr(parent, "_generate_sample_responses") else None
        app = parent if interview_view is None else None
        self._view = PreviewView(
            self, response_style, questions, app=app,
            interview_event=getattr(interview_view, "event", None),
            interview_raw_event=getattr(interview_view, "raw_event", None),
            media_view=getattr(interview_view, "media_view", None),
            on_done=getattr(interview_view, "on_done", None))
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
