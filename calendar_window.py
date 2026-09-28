# calendar_window.py
# Season Calendar for Puck Dynasty.
# CustomTkinter rebuild: CTkToplevel with a month grid of colored day cells
# (game/event markers), a day-detail pane (results, team form, season
# series), month navigation, and trade-deadline quick actions.
# All date/event logic is unchanged from the ttk version; only the
# presentation layer was rebuilt.

import calendar
from datetime import date, timedelta

import tkinter as tk
from popup_system import InGamePopup

import customtkinter as ctk


class CalendarView(ctk.CTkFrame):
    """Season calendar: month grid + day detail pane."""

    # Day-cell styles keyed by event priority. Each entry carries the cell
    # background, text color, hover color, and the legend label.
    DAY_STYLES = {
        'today':      {'bg': '#00ceb8', 'fg': '#0e0e11', 'hover': '#00a896',
                       'label': 'Today'},
        'home':       {'bg': '#2f81f7', 'fg': '#ffffff', 'hover': '#1f6feb',
                       'label': 'Home Game'},
        'away':       {'bg': '#0ea5b7', 'fg': '#ffffff', 'hover': '#0c8a96',
                       'label': 'Away Game'},
        'league':     {'bg': '#546E7A', 'fg': '#ffffff', 'hover': '#455a64',
                       'label': 'League Games'},
        'allstar':    {'bg': '#e8b93c', 'fg': '#0e0e11', 'hover': '#c99a2e',
                       'label': 'All-Star Events'},
        'deadline':   {'bg': '#e74c3c', 'fg': '#ffffff', 'hover': '#c9402f',
                       'label': 'Trade Deadline'},
        'draft':      {'bg': '#9b4dca', 'fg': '#ffffff', 'hover': '#7b3aa3',
                       'label': 'Draft'},
        'freeagency': {'bg': '#3fb950', 'fg': '#0e0e11', 'hover': '#34a244',
                       'label': 'Free Agency'},
        'important':  {'bg': '#f2762e', 'fg': '#ffffff', 'hover': '#cf611f',
                       'label': 'Special Events'},
        'break':      {'bg': '#33333a', 'fg': '#a1a1aa', 'hover': '#26262c',
                       'label': 'Break Days'},
        'default':    {'bg': '#1e1e24', 'fg': '#f4f4f5', 'hover': '#2e2e38',
                       'label': 'Regular Day'},
    }

    LEGEND_ORDER = ['today', 'home', 'away', 'league', 'allstar', 'deadline',
                    'draft', 'freeagency', 'important', 'break']

    # Styles whose cells get bold text (mirrors the old ttk emphasis).
    _BOLD_STYLES = ('home', 'away', 'allstar', 'deadline', 'today')

    def __init__(self, parent, app=None):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the CalendarWindow wrapper
        self.configure(fg_color=BG)

        # Current date tracking
        self.current_view_date = self.app.current_date
        self.selected_date = None
        self._selected_btn = None

        # Event data
        self.events_by_date = {}
        self._load_season_events()

        # Create UI
        self._create_widgets()
        self._populate_calendar()

        # Add to parent's open windows
        self.app.open_windows['calendar'] = self

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _create_widgets(self):
        """Create the calendar interface."""
        ct = self._ct
        main = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main.pack(fill='both', expand=True, padx=14, pady=14)

        self._create_header(main)
        self._create_legend(main)

        # Content: calendar grid (left, stretches) + details pane (right)
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill='both', expand=True)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        content.grid_rowconfigure(0, weight=1)

        cal_card = ctk.CTkFrame(content, fg_color=ct['PANEL'], corner_radius=12)
        cal_card.grid(row=0, column=0, sticky='nsew', padx=(0, 7))

        detail_card = ctk.CTkFrame(content, fg_color=ct['PANEL'],
                                   corner_radius=12, width=360)
        detail_card.grid(row=0, column=1, sticky='nsew', padx=(7, 0))

        self._create_calendar_grid(cal_card)
        self._create_details_panel(detail_card)

    def _create_header(self, parent):
        """Create header with title, month/year display, and navigation."""
        ct = self._ct
        header = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12)
        header.pack(fill='x', pady=(0, 12))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side='left', padx=16, pady=12)
        self._heading(title_box, "Season Calendar", size=20).pack(anchor='w')
        self._body(title_box, self.app.user_team.team_name,
                   size=12, dim=True).pack(anchor='w')

        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.pack(side='right', padx=16, pady=12)
        self.month_year_label = self._heading(nav, "", size=16)
        self.month_year_label.pack(side='left', padx=(0, 16))
        self._secondary_button(nav, "Prev", command=self._prev_month,
                               width=84, height=34).pack(side='left', padx=3)
        self._primary_button(nav, "Today", command=self._go_to_today,
                             width=84, height=34).pack(side='left', padx=3)
        self._secondary_button(nav, "Next", command=self._next_month,
                               width=84, height=34).pack(side='left', padx=3)

    def _create_legend(self, parent):
        """Create the color key card for day-cell styles."""
        ct = self._ct
        legend = ctk.CTkFrame(parent, fg_color=ct['PANEL'], corner_radius=12)
        legend.pack(fill='x', pady=(0, 12))

        inner = ctk.CTkFrame(legend, fg_color="transparent")
        inner.pack(fill='x', padx=14, pady=10)
        for i, key in enumerate(self.LEGEND_ORDER):
            style = self.DAY_STYLES[key]
            row, col = divmod(i, 5)
            chip = ctk.CTkFrame(inner, fg_color="transparent")
            chip.grid(row=row, column=col, padx=10, pady=3, sticky='w')
            dot = ctk.CTkLabel(chip, text="\u25cf",
                               text_color=style['bg'],
                               font=("Segoe UI", 14, "bold"))
            dot.pack(side='left', padx=(0, 6))
            self._body(chip, style['label'], size=11, dim=True).pack(side='left')
        for c in range(5):
            inner.grid_columnconfigure(c, weight=1)

    def _create_calendar_grid(self, parent):
        """Create the calendar grid layout."""
        ct = self._ct
        self._body(parent, "Calendar", size=13, dim=True).pack(
            anchor='w', padx=16, pady=(14, 4))

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                'Friday', 'Saturday', 'Sunday']
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill='x', padx=14, pady=(0, 6))
        for i, day in enumerate(days):
            label = ctk.CTkLabel(header_frame, text=day[:3].upper(),
                                 font=("Segoe UI", 11, "bold"),
                                 text_color=ct['TEXT_DIM'])
            label.grid(row=0, column=i, padx=1, pady=1, sticky='ew')
            header_frame.grid_columnconfigure(i, weight=1)

        # Calendar grid
        self.calendar_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.calendar_frame.pack(fill='both', expand=True,
                                 padx=14, pady=(0, 14))

        for i in range(7):  # 7 columns (days of week)
            self.calendar_frame.grid_columnconfigure(i, weight=1)
        for i in range(6):  # 6 rows (max weeks in month)
            self.calendar_frame.grid_rowconfigure(i, weight=1)

        # Store day buttons for updates
        self.day_buttons = {}

    def _create_details_panel(self, parent):
        """Create the event details panel."""
        ct = self._ct
        self._body(parent, "Day Details", size=13, dim=True).pack(
            anchor='w', padx=16, pady=(14, 4))
        self.selected_date_label = self._heading(parent, "Select a date",
                                                 size=16)
        self.selected_date_label.pack(anchor='w', padx=16, pady=(0, 8))

        # Read-only event log with native scrollbars
        self.events_text = ctk.CTkTextbox(parent, wrap='word',
                                          fg_color=ct['CARD'],
                                          text_color=ct['TEXT'],
                                          font=("Segoe UI", 11),
                                          activate_scrollbars=True,
                                          corner_radius=8)
        self.events_text.pack(fill='both', expand=True, padx=16)
        # CTkTextbox forbids tag fonts (breaks widget scaling); use theme
        # colors for hierarchy instead.
        self.events_text.tag_config('title', foreground=ct['TEAL'])
        self.events_text.tag_config('section', foreground=ct['GOLD'])
        self.events_text.configure(state='disabled')

        # Quick actions (dynamic - rebuilt based on the selected date)
        self.actions_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.actions_frame.pack(fill='x', padx=16, pady=12)

        # Initialize with default actions
        self._create_default_actions()

    def _create_default_actions(self):
        """Create default action buttons."""
        for widget in self.actions_frame.winfo_children():
            widget.destroy()

        self._secondary_button(self.actions_frame, text="View Game Details",
                               command=self._view_game_details).pack(
                                   fill='x', pady=3)
        self._secondary_button(self.actions_frame, text="Team Stats",
                               command=self._view_team_stats).pack(
                                   fill='x', pady=3)
        self._secondary_button(self.actions_frame, text="News & Updates",
                               command=self._view_news).pack(fill='x', pady=3)

    def _create_trade_deadline_actions(self):
        """Create action buttons for trade deadline day."""
        for widget in self.actions_frame.winfo_children():
            widget.destroy()

        # Trade Deadline Center button (prominent)
        self._primary_button(self.actions_frame, text="TRADE DEADLINE CENTER",
                             command=self._launch_trade_deadline_center).pack(
                                 fill='x', pady=3)
        self._secondary_button(self.actions_frame, text="Trade Center",
                               command=self.app.open_trade_window).pack(
                                   fill='x', pady=3)
        self._secondary_button(self.actions_frame, text="Market Analysis",
                               command=self._view_market_analysis).pack(
                                   fill='x', pady=3)
        self._secondary_button(self.actions_frame, text="Deadline News",
                               command=self._view_news).pack(fill='x', pady=3)

    def _launch_trade_deadline_center(self):
        """Launch the Trade Deadline Center from calendar."""
        self.app.open_trade_deadline_center()

    def _view_market_analysis(self):
        """Placeholder for market analysis - could open trade statistics."""
        # For now, redirect to trade window
        self.app.open_trade_window()

    # ------------------------------------------------------------------
    # Event data (unchanged logic)
    # ------------------------------------------------------------------
    def _load_season_events(self):
        """Load all season events from the game data."""
        self.events_by_date.clear()

        # Load NHL calendar information from league
        self.nhl_calendar_info = self._get_nhl_calendar_info()

        # Load team games and NHL events
        for game_entry in self.app.league.schedule:
            # Handle different schedule formats
            if isinstance(game_entry, dict):
                # New format: dictionary with date, home_team, away_team, etc.
                game_date = game_entry['date']
                home_team = game_entry['home_team']
                away_team = game_entry['away_team']
            elif isinstance(game_entry, (tuple, list)) and len(game_entry) >= 3:
                # Handle NHL special events in tuple format: (date, 'NHL_EVENT', event_data)
                if game_entry[1] == 'NHL_EVENT':
                    game_date = game_entry[0]
                    event_data = game_entry[2]  # The event data dictionary
                    event = {
                        'type': event_data['type'],
                        'title': event_data['title'],
                        'description': event_data['description'],
                        'importance': 'critical'
                    }

                    if game_date not in self.events_by_date:
                        self.events_by_date[game_date] = []
                    self.events_by_date[game_date].append(event)
                    continue  # Skip to next entry

                # Regular game format: tuple/list with (date, home_team, away_team)
                game_date, home_team, away_team = game_entry[0], game_entry[1], game_entry[2]
            else:
                continue  # Skip malformed entries

            # Handle NHL special events (legacy format)
            if home_team == 'NHL_EVENT':
                event_data = away_team  # The event data dictionary
                event = {
                    'type': event_data['type'],
                    'title': event_data['title'],
                    'description': event_data['description'],
                    'importance': 'critical'
                }

                if game_date not in self.events_by_date:
                    self.events_by_date[game_date] = []
                self.events_by_date[game_date].append(event)

            # Handle regular team games - show ALL games (EHM/FM style)
            # User's games get high importance, others get normal
            else:
                is_user_game = self.app.user_team in (home_team, away_team)

                if is_user_game:
                    is_home = self.app.user_team == home_team
                    opponent = away_team if is_home else home_team

                    event = {
                        'type': 'game',
                        'title': f"{'vs' if is_home else '@'} {opponent.team_name}",
                        'description': f"{'Home' if is_home else 'Away'} game against {opponent.team_name}",
                        'is_home': is_home,
                        'opponent': opponent,
                        'home_team': home_team,
                        'away_team': away_team,
                        'is_user_game': True,
                        'importance': 'high'
                    }

                    # Check if this is a special game
                    if self._is_special_date(game_date):
                        event['importance'] = 'critical'
                else:
                    # Other teams' games - show compactly
                    home_name = home_team.team_name if hasattr(home_team, 'team_name') else str(home_team)
                    away_name = away_team.team_name if hasattr(away_team, 'team_name') else str(away_team)

                    event = {
                        'type': 'game',
                        'title': f"{away_name} @ {home_name}",
                        'description': f"NHL game: {away_name} at {home_name}",
                        'is_home': None,
                        'opponent': None,
                        'home_team': home_team,
                        'away_team': away_team,
                        'is_user_game': False,
                        'importance': 'normal'
                    }

                if game_date not in self.events_by_date:
                    self.events_by_date[game_date] = []
                self.events_by_date[game_date].append(event)

        # NHL events are now loaded from the main schedule above
        # Only add break days and other calendar events
        self._add_break_days_and_holidays()

        # Add other important dates
        self._add_important_dates()

    def _get_season_year(self):
        """Get the season year (year the season starts) from the league.

        Falls back to deriving from current_date if league not available.
        The season_year is the year the season starts (e.g., 2024 for 2024-25).
        """
        try:
            if hasattr(self.app, 'league') and hasattr(self.app.league, 'season_year'):
                return self.app.league.season_year
        except (AttributeError, TypeError):
            pass
        # Fallback: derive from current date
        # If we're in Jan-Sep, the season started last year
        current = self.app.current_date
        if current.month >= 10:
            return current.year
        else:
            return current.year - 1

    def _is_special_date(self, game_date):
        """Check if a date represents a special game (holidays, rivalries, etc.)."""
        # Check for holiday games
        if (game_date.month == 12 and game_date.day == 25) or \
           (game_date.month == 1 and game_date.day == 1) or \
           (game_date.month == 11 and 22 <= game_date.day <= 28):  # Thanksgiving week
            return True

        # Check for season opener/closer
        # Use season_year (year season starts) to avoid year-boundary bugs
        season_year = self._get_season_year()
        season_start = date(season_year, 10, 8)
        season_end = date(season_year + 1, 4, 25)

        if abs((game_date - season_start).days) <= 7 or \
           abs((season_end - game_date).days) <= 7:
            return True

        return False

    def _get_nhl_calendar_info(self):
        """Get NHL calendar information from the league.

        Uses league.season_year and matches the dates used by the actual
        schedule generator in game_classes.py (_create_authentic_nhl_calendar).
        """
        season_year = self._get_season_year()

        # Match the real generator dates exactly:
        # - Thanksgiving: Nov 24 (season_year)
        # - Christmas: Dec 24-25 (season_year)
        # - All-Star: Feb 5-11 (season_year + 1)
        # - Trade deadline: Mar 8 (season_year + 1)
        return {
            'all_star_break': (
                date(season_year + 1, 2, 5),
                date(season_year + 1, 2, 11)
            ),
            'trade_deadline': date(season_year + 1, 3, 8),
            'christmas_break': (
                date(season_year, 12, 24),
                date(season_year, 12, 25)
            ),
            'thanksgiving_break': (
                date(season_year, 11, 24),
                date(season_year, 11, 24)
            )
        }

    def _add_break_days_and_holidays(self):
        """Add break days and holiday periods (main events now come from schedule)."""
        if not self.nhl_calendar_info:
            return

        # All-Star break dates
        all_star_start, all_star_end = self.nhl_calendar_info['all_star_break']
        current_date = all_star_start

        # Add All-Star break days (main events now come from schedule)
        while current_date <= all_star_end:
            if current_date not in self.events_by_date:
                self.events_by_date[current_date] = []

            # Check if this date already has a main event from the schedule
            has_main_event = any(e['type'] in ['all_star_skills', 'all_star_game']
                               for e in self.events_by_date[current_date])

            # Only add break day if there's no main event
            if not has_main_event:
                event = {
                    'type': 'break_day',
                    'title': 'All-Star Break',
                    'description': 'No regular season games scheduled',
                    'importance': 'medium'
                }
                self.events_by_date[current_date].append(event)

            current_date += timedelta(days=1)

        # Trade deadline now comes from the main schedule

        # Christmas break dates
        christmas_start, christmas_end = self.nhl_calendar_info['christmas_break']
        current_date = christmas_start

        while current_date <= christmas_end:
            if current_date.day == 25:  # Christmas Day
                event = {
                    'type': 'christmas',
                    'title': 'Christmas Day',
                    'description': 'Special holiday games may be scheduled',
                    'importance': 'high'
                }
            else:
                event = {
                    'type': 'break_day',
                    'title': 'Christmas Break',
                    'description': 'Reduced game schedule for holidays',
                    'importance': 'medium'
                }

            if current_date not in self.events_by_date:
                self.events_by_date[current_date] = []
            self.events_by_date[current_date].append(event)
            current_date += timedelta(days=1)

    def _add_important_dates(self):
        """Add important league dates and events (non-NHL calendar events).

        Uses league.season_year and matches the actual schedule generator dates.
        """
        season_year = self._get_season_year()

        important_dates = [
            (date(season_year, 10, 8), "Season Opener", "NHL regular season begins"),
            (date(season_year + 1, 1, 1), "New Year's Day", "Winter Classic and New Year games"),
            (date(season_year + 1, 2, 14), "Valentine's Day", "Special promotional games"),
            (date(season_year + 1, 4, 25), "Regular Season End", "End of regular season"),
            (date(season_year + 1, 4, 26), "Playoffs Begin", "Stanley Cup Playoffs start"),
            (date(season_year + 1, 6, 27), "Draft Day", "NHL Entry Draft"),
            (date(season_year + 1, 7, 1), "Free Agency", "Free agency period begins")
        ]

        for event_date, title, description in important_dates:
            # Skip if we already have events for this date (avoid duplicates)
            if event_date in self.events_by_date:
                continue

            event = {
                'type': 'league_event',
                'title': title,
                'description': description,
                'importance': 'medium'
            }

            if event_date not in self.events_by_date:
                self.events_by_date[event_date] = []
            self.events_by_date[event_date].append(event)

    # ------------------------------------------------------------------
    # Month grid rendering
    # ------------------------------------------------------------------
    def _style_for_day(self, day):
        """Return (style_key, marker_text) for a calendar date.

        Priority: today > user game > league games > all-star >
        trade deadline > draft > free agency > christmas/special >
        break day > other important > default. Same priority order as the
        old ttk version. One fix: 'league_event' entries titled
        "Draft Day"/"Free Agency" (added by _add_important_dates) now map
        to the draft/free-agency styles, since no event ever carried the
        'entry_draft'/'free_agency' types the old check looked for.
        """
        events = self.events_by_date.get(day, [])
        is_today = (day == self.app.current_date)

        style_key, marker = 'default', ''
        if events:
            game_events = [e for e in events if e['type'] == 'game']
            all_star = [e for e in events
                        if e['type'] in ('all_star', 'all_star_skills',
                                         'all_star_game')]
            deadline = [e for e in events if e['type'] == 'trade_deadline']
            draft = [e for e in events
                     if e['type'] == 'entry_draft'
                     or (e['type'] == 'league_event'
                         and 'draft' in e['title'].lower())]
            free_agency = [e for e in events
                           if e['type'] == 'free_agency'
                           or (e['type'] == 'league_event'
                               and 'free agency' in e['title'].lower())]
            xmas = [e for e in events if e['type'] == 'christmas']
            breaks = [e for e in events if e['type'] == 'break_day']

            if game_events:
                user_games = [g for g in game_events if g.get('is_user_game')]
                if user_games:
                    game = user_games[0]
                    style_key = 'home' if game.get('is_home') else 'away'
                    marker = 'HOME' if game.get('is_home') else 'AWAY'
                else:
                    style_key = 'league'
                    marker = f"{len(game_events)} games"
            elif all_star:
                style_key, marker = 'allstar', 'ASG'
            elif deadline:
                style_key, marker = 'deadline', 'TDL'
            elif draft:
                style_key, marker = 'draft', 'DRAFT'
            elif free_agency:
                style_key, marker = 'freeagency', 'FA'
            elif xmas:
                style_key, marker = 'important', 'XMAS'
            elif breaks:
                style_key, marker = 'break', 'BREAK'
            elif any(e.get('importance') in ('high', 'critical')
                     for e in events):
                style_key, marker = 'important', '!'

        if is_today:
            # Today keeps the teal cell, but still shows its game marker.
            if style_key not in ('home', 'away'):
                marker = ''
            return 'today', marker
        return style_key, marker

    def _populate_calendar(self):
        """Populate the calendar with the current month."""
        ct = self._ct
        # Clear existing buttons
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()
        self.day_buttons.clear()
        self._selected_btn = None

        # Update month/year label
        month_name = calendar.month_name[self.current_view_date.month]
        self.month_year_label.configure(
            text=f"{month_name} {self.current_view_date.year}")

        # Get calendar data
        cal = calendar.monthcalendar(self.current_view_date.year,
                                     self.current_view_date.month)

        # Create day cells
        for week_num, week in enumerate(cal):
            for day_num, day in enumerate(week):
                if day == 0:  # Empty cell
                    continue

                button_date = date(self.current_view_date.year,
                                   self.current_view_date.month, day)
                style_key, marker = self._style_for_day(button_date)
                style = self.DAY_STYLES[style_key]
                text = str(day) if not marker else f"{day}\n{marker}"
                font = (("Segoe UI", 11, "bold") if style_key in self._BOLD_STYLES
                        else ("Segoe UI", 11))

                btn = ctk.CTkButton(
                    self.calendar_frame, text=text,
                    fg_color=style['bg'], hover_color=style['hover'],
                    text_color=style['fg'], font=font,
                    corner_radius=6, border_width=0,
                    command=lambda d=button_date: self._select_date(d))
                btn.grid(row=week_num, column=day_num,
                         padx=2, pady=2, sticky='nsew')

                self.day_buttons[button_date] = btn

        # Restore the selection ring if the selected date is visible
        if self.selected_date in self.day_buttons:
            self._selected_btn = self.day_buttons[self.selected_date]
            self._selected_btn.configure(border_width=2,
                                         border_color=ct['TEAL'])

    def _select_date(self, selected_date):
        """Handle date selection."""
        if self._selected_btn is not None:
            self._selected_btn.configure(border_width=0)
        self._selected_btn = self.day_buttons.get(selected_date)
        if self._selected_btn is not None:
            self._selected_btn.configure(border_width=2,
                                         border_color=self._ct['TEAL'])
        self.selected_date = selected_date
        self._update_details_panel()

    def _update_details_panel(self):
        """Update the details panel with selected date information."""
        if not self.selected_date:
            return

        # Update selected date label
        date_str = self.selected_date.strftime("%A, %B %d, %Y")
        self.selected_date_label.configure(text=date_str)

        # Clear and populate events
        self.events_text.configure(state='normal')
        self.events_text.delete("1.0", "end")

        events = self.events_by_date.get(self.selected_date, [])

        # Check if this date has trade deadline events
        has_trade_deadline = any(event.get('type') == 'trade_deadline'
                                 for event in events)

        if not events:
            self.events_text.insert("end", "No events scheduled for this date.")
        else:
            for i, event in enumerate(events):
                if i > 0:
                    self.events_text.insert("end", "\n" + "\u2500" * 40 + "\n\n")

                # Event title
                self.events_text.insert("end", f"{event['title']}\n",
                                        tags='title')

                # Event description
                self.events_text.insert("end", f"{event['description']}\n\n")

                # Additional details for games
                if event['type'] == 'game':
                    self._insert_game_details(event)

        self.events_text.configure(state='disabled')

        # Update action buttons based on the selected date
        if has_trade_deadline:
            self._create_trade_deadline_actions()
        else:
            self._create_default_actions()

    # ------------------------------------------------------------------
    # Day-detail enrichment (unchanged logic)
    # ------------------------------------------------------------------
    def _team_label(self, team):
        """Display name for a team object (or the raw value for strings)."""
        if team is None:
            return "TBD"
        return getattr(team, 'team_name', str(team))

    def _user_results(self):
        """Game results involving the user team, oldest first."""
        user = self.app.user_team
        results = []
        for result in getattr(self.app, 'game_results', None) or []:
            try:
                if user in (result['home_team'], result['away_team']):
                    results.append(result)
            except (KeyError, TypeError):
                continue
        results.sort(key=lambda r: r.get('date') or date.min)
        return results

    def _describe_user_result(self, result):
        """Return (outcome, summary line) for a result from the user's perspective.

        Outcome is 'W', 'L' or 'T'. Returns None when the result is malformed.
        """
        try:
            user = self.app.user_team
            home, away = result['home_team'], result['away_team']
            is_home = (user == home)
            opponent = away if is_home else home
            us = result['home_score'] if is_home else result['away_score']
            them = result['away_score'] if is_home else result['home_score']
            winner = result.get('winner')
            if winner is not None:
                outcome = 'W' if winner == user else 'L'
            else:
                outcome = 'W' if us > them else ('L' if us < them else 'T')
            venue = 'vs' if is_home else '@'
            when = result['date'].strftime('%b %d') if result.get('date') else ''
            return outcome, f"{when}: {outcome} {us}-{them} {venue} {self._team_label(opponent)}".strip()
        except (KeyError, TypeError, AttributeError):
            return None

    def _recent_form_lines(self):
        """Last-5 form lines plus record and streak, from real game results."""
        results = self._user_results()
        if not results:
            return ["No games played yet this season."]
        described = [d for d in (self._describe_user_result(r) for r in results[-5:]) if d]
        if not described:
            return ["No games played yet this season."]
        lines = [f"  {text}" for _outcome, text in described]
        w = sum(1 for o, _ in described if o == 'W')
        l = sum(1 for o, _ in described if o == 'L')
        lines.append(f"  Last 5: {w}-{l}")
        # Current streak (walk back from the most recent result)
        streak_outcome, streak_n = None, 0
        for r in reversed(results):
            d = self._describe_user_result(r)
            if not d or d[0] == 'T':
                break
            if streak_outcome is None:
                streak_outcome = d[0]
            if d[0] == streak_outcome:
                streak_n += 1
            else:
                break
        if streak_outcome:
            lines.append(f"  Streak: {streak_outcome}{streak_n}")
        return lines

    def _iter_schedule_games(self):
        """Yield (date, home_team, away_team) for real games in the schedule,
        skipping NHL special-event entries."""
        league = getattr(self.app, 'league', None)
        schedule = getattr(league, 'schedule', None) or []
        for entry in schedule:
            try:
                if isinstance(entry, dict):
                    game_date = entry.get('date')
                    home, away = entry.get('home_team'), entry.get('away_team')
                elif isinstance(entry, (tuple, list)) and len(entry) >= 3:
                    if entry[1] == 'NHL_EVENT':
                        continue
                    game_date, home, away = entry[0], entry[1], entry[2]
                else:
                    continue
                if home == 'NHL_EVENT':
                    continue
                yield game_date, home, away
            except (TypeError, IndexError):
                continue

    def _season_series_lines(self, opponent):
        """Season series vs an opponent: played results plus upcoming meetings."""
        lines = []
        meetings = [r for r in self._user_results()
                    if opponent in (r['home_team'], r['away_team'])]
        described = [d for d in (self._describe_user_result(r) for r in meetings) if d]
        if not described:
            lines.append("First meeting this season.")
        else:
            w = sum(1 for o, _ in described if o == 'W')
            l = sum(1 for o, _ in described if o == 'L')
            lines.append(f"Series record: {w}-{l}")
            for _outcome, text in described:
                lines.append(f"  {text}")
        # Upcoming meetings from the schedule
        upcoming = []
        for game_date, home, away in self._iter_schedule_games():
            if game_date is None or game_date <= self.selected_date:
                continue
            if opponent in (home, away) and self.app.user_team in (home, away):
                venue = 'vs' if self.app.user_team == home else '@'
                upcoming.append(f"{game_date.strftime('%b %d')}: {venue} {self._team_label(opponent)}")
        if upcoming:
            lines.append("Upcoming: " + "; ".join(upcoming[:4]))
        else:
            lines.append("No further meetings scheduled.")
        return lines

    def _insert_game_details(self, event):
        """Insert enriched details for a game event.

        User-team games get matchup info, the result when played, team form
        (last 5) and the season series vs the opponent - all from real game
        results and the schedule. League games get a matchup line instead of
        crashing on the missing opponent reference.
        """
        if event.get('is_user_game') and event.get('opponent') is not None:
            opponent = event['opponent']
            location = "Home Ice" if event['is_home'] else getattr(opponent, 'city', 'Away')
            self.events_text.insert("end", f"Location: {location}\n")
            self.events_text.insert("end", f"Opponent: {self._team_label(opponent)}\n")

            # Check if game has been played
            game_result = self._get_game_result(self.selected_date, opponent)
            if game_result:
                self.events_text.insert("end", f"Result: {game_result}\n")

            # Team form: last 5 results
            self.events_text.insert("end", "\nTeam Form (Last 5)\n", tags='section')
            for line in self._recent_form_lines():
                self.events_text.insert("end", line + "\n")

            # Season series vs this opponent
            self.events_text.insert("end",
                                    f"\nSeason Series vs {self._team_label(opponent)}\n",
                                    tags='section')
            for line in self._season_series_lines(opponent):
                self.events_text.insert("end", line + "\n")
        else:
            # League game not involving the user team
            home = self._team_label(event.get('home_team'))
            away = self._team_label(event.get('away_team'))
            self.events_text.insert("end", f"Matchup: {away} @ {home}\n")

    def _get_game_result(self, game_date, opponent):
        """Get the result of a game if it has been played."""
        for result in self.app.game_results:
            if (result['date'] == game_date and
                opponent in (result['home_team'], result['away_team'])):

                if self.app.user_team == result['home_team']:
                    user_score = result['home_score']
                    opp_score = result['away_score']
                else:
                    user_score = result['away_score']
                    opp_score = result['home_score']

                result_text = "Won" if result['winner'] == self.app.user_team else "Lost"
                return f"{result_text} {user_score}-{opp_score}"
        return None

    # ------------------------------------------------------------------
    # Navigation + actions (unchanged behavior)
    # ------------------------------------------------------------------
    def _prev_month(self):
        """Navigate to previous month."""
        if self.current_view_date.month == 1:
            self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year - 1, month=12)
        else:
            self.current_view_date = self.current_view_date.replace(month=self.current_view_date.month - 1)
        self._populate_calendar()

    def _next_month(self):
        """Navigate to next month."""
        if self.current_view_date.month == 12:
            self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year + 1, month=1)
        else:
            self.current_view_date = self.current_view_date.replace(month=self.current_view_date.month + 1)
        self._populate_calendar()

    def _go_to_today(self):
        """Navigate to current date."""
        self.current_view_date = self.app.current_date
        self._populate_calendar()
        self._select_date(self.app.current_date)

    def _view_game_details(self):
        """View detailed game information."""
        if not self.selected_date:
            return

        events = self.events_by_date.get(self.selected_date, [])
        game_events = [e for e in events if e['type'] == 'game']

        if game_events:
            # Open game details or schedule window
            self.app.open_schedule_window()

    def _view_team_stats(self):
        """View team statistics."""
        self.app.open_roster_window()

    def _view_news(self):
        """View news and updates."""
        self.app.open_news_window()

    def update_calendar(self):
        """Refresh the calendar with current data."""
        self._load_season_events()
        self._populate_calendar()
        if self.selected_date:
            self._update_details_panel()

    def update_views(self):
        """Refresh the calendar - called by main window when sim advances.

        This is the standard interface that main.py's _update_heavy_panels
        looks for on all open windows.
        """
        try:
            # Only refresh if window still exists
            if self.winfo_exists():
                self.update_calendar()
        except tk.TclError:
            # Window was destroyed, ignore
            pass

class CalendarWindow(InGamePopup):
    """Popup wrapper around CalendarView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        try:
            self.title(f"Season Calendar - {parent.user_team.team_name}")
        except Exception:
            self.title("Season Calendar")
        self._view = CalendarView(self, app=parent, *args, **kwargs)
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
