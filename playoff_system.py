"""
NHL Playoff System Implementation
Complete Stanley Cup playoff bracket generation and management
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from popup_system import messagebox, InGamePopup
from datetime import date, timedelta
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from game_classes import Team, PlayerPosition


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


@dataclass
class PlayoffSeries:
    """Represents a playoff series between two teams"""
    round_name: str  # "Wild Card", "Division Semifinals", etc.
    team1: Team
    team2: Team
    team1_wins: int = 0
    team2_wins: int = 0
    games_played: int = 0
    is_complete: bool = False
    winner: Optional[Team] = None
    series_format: int = 7  # Best of 7
    # Narrative ledger: per-game facts for series memory (beats are derived
    # from this, not from the win counters). Additive — nothing else reads it.
    game_results: List[Dict] = field(default_factory=list)
    
    def add_game_result(self, team1_won: bool, game_info: Optional[Dict] = None):
        """Add a game result to the series"""
        if team1_won:
            self.team1_wins += 1
        else:
            self.team2_wins += 1
        self.games_played += 1
        if game_info:
            try:
                self.game_results.append(dict(game_info))
            except Exception:
                pass
        
        # Check if series is complete
        wins_needed = (self.series_format // 2) + 1
        if self.team1_wins >= wins_needed:
            self.is_complete = True
            self.winner = self.team1
        elif self.team2_wins >= wins_needed:
            self.is_complete = True
            self.winner = self.team2


class PlayoffBracket:
    """Manages the entire NHL playoff bracket"""
    
    def __init__(self, league):
        self.league = league
        self.eastern_teams: List[Team] = []
        self.western_teams: List[Team] = []
        self.playoff_series: Dict[str, List[PlayoffSeries]] = {
            'wild_card': [],
            'division_semifinals': [],
            'division_finals': [],
            'conference_finals': [],
            'stanley_cup_final': []
        }
        self.current_round = 'wild_card'
        self.stanley_cup_champion: Optional[Team] = None
        
    def generate_playoff_bracket(self):
        """Generate the complete playoff bracket based on standings.

        Top 8 teams per conference by league standings (points, then wins,
        then goal differential), mirroring the NHL format.
        """
        eastern, western = self._get_playoff_qualified_teams()
        self.eastern_teams = eastern
        self.western_teams = western

        # Assign 1-8 seeds for display/sorting
        for i, team in enumerate(self.eastern_teams):
            team.standings_position = i + 1
        for i, team in enumerate(self.western_teams):
            team.standings_position = i + 1

        # Generate first round matchups
        self._create_wild_card_round()

    def _get_playoff_qualified_teams(self):
        """Get the top 8 teams per conference that qualify for playoffs.

        Returns (eastern_teams, western_teams), each sorted best-first.
        Reads the league standings dict (source of truth for the season).
        """
        standings = getattr(self.league, 'standings', {})

        def sort_key(team):
            st = standings.get(team.team_name, {})
            points = st.get('Points', 0)
            wins = st.get('W', st.get('Wins', 0))
            goal_diff = getattr(team, 'goals_for', 0) - getattr(team, 'goals_against', 0)
            return (-points, -wins, -goal_diff)

        eastern, western = [], []
        for team in self.league.teams:
            if getattr(team, 'league_name', '') != 'National Hockey League':
                continue
            if getattr(team, 'conference', '') == 'Eastern':
                eastern.append(team)
            else:
                western.append(team)

        eastern.sort(key=sort_key)
        western.sort(key=sort_key)
        return eastern[:8], western[:8]
    
    def _is_eastern_team(self, team: Team) -> bool:
        """Determine if team is in Eastern Conference"""
        eastern_divisions = ['Atlantic', 'Metropolitan']
        return hasattr(team, 'division') and team.division in eastern_divisions
    
    def _create_wild_card_round(self):
        """Create Wild Card round matchups"""
        # Eastern Conference Wild Card
        east_matchups = [
            (self.eastern_teams[0], self.eastern_teams[7]),  # 1 vs 8
            (self.eastern_teams[1], self.eastern_teams[6]),  # 2 vs 7
            (self.eastern_teams[2], self.eastern_teams[5]),  # 3 vs 6
            (self.eastern_teams[3], self.eastern_teams[4])   # 4 vs 5
        ]
        
        # Western Conference Wild Card
        west_matchups = [
            (self.western_teams[0], self.western_teams[7]),  # 1 vs 8
            (self.western_teams[1], self.western_teams[6]),  # 2 vs 7
            (self.western_teams[2], self.western_teams[5]),  # 3 vs 6
            (self.western_teams[3], self.western_teams[4])   # 4 vs 5
        ]
        
        # Create series
        for team1, team2 in east_matchups + west_matchups:
            series = PlayoffSeries("Wild Card Round", team1, team2)
            self.playoff_series['wild_card'].append(series)
    
    # Bracket flow: Round 1 -> Round 2 -> Conference Finals -> Stanley Cup Final.
    # ('division_finals' holds the two conference-final series; 'conference_finals'
    # is kept as a legacy key.)
    ROUND_ORDER = ['wild_card', 'division_semifinals', 'division_finals',
                   'stanley_cup_final']

    def advance_to_next_round(self, round_name: str):
        """Advance winners to the next playoff round"""
        current_series = self.playoff_series[round_name]
        # Narrative ledger: a completed series acquires a memory — its
        # defining beats, weighted by what actually happened. Recorded once
        # per series, here, before winners move on.
        try:
            from narrative_ledger import (active_ledger,
                                          record_playoff_series_memory)
            _led = active_ledger()
            if _led is not None:
                for _s in current_series:
                    if getattr(_s, "is_complete", False) and \
                            not getattr(_s, "_ledger_recorded", False):
                        record_playoff_series_memory(_led, _s)
                        _s._ledger_recorded = True
        except Exception:
            pass
        winners = [series.winner for series in current_series if series.is_complete and series.winner]

        if round_name == 'wild_card':
            self._create_division_semifinals(winners)
        elif round_name == 'division_semifinals':
            self._create_division_finals(winners)
        elif round_name == 'division_finals':
            # Conference champions advance to the Stanley Cup Final
            self._create_conference_finals(winners)
        elif round_name == 'stanley_cup_final':
            if winners:
                self.stanley_cup_champion = winners[0]

        # Move the current-round pointer forward
        try:
            next_idx = self.ROUND_ORDER.index(round_name) + 1
            self.current_round = (self.ROUND_ORDER[next_idx]
                                  if next_idx < len(self.ROUND_ORDER) else 'complete')
        except ValueError:
            pass
    
    def _create_division_semifinals(self, winners: List[Team]):
        """Create Division Semifinals matchups"""
        eastern_winners = [team for team in winners if self._is_eastern_team(team)]
        western_winners = [team for team in winners if not self._is_eastern_team(team)]
        
        # Sort by original seeding and create matchups
        eastern_winners.sort(key=lambda t: t.standings_position)
        western_winners.sort(key=lambda t: t.standings_position)
        
        # Eastern matchups (highest vs lowest remaining seeds)
        for i in range(0, len(eastern_winners), 2):
            if i + 1 < len(eastern_winners):
                series = PlayoffSeries("Division Semifinals", 
                                     eastern_winners[i], eastern_winners[i + 1])
                self.playoff_series['division_semifinals'].append(series)
        
        # Western matchups
        for i in range(0, len(western_winners), 2):
            if i + 1 < len(western_winners):
                series = PlayoffSeries("Division Semifinals", 
                                     western_winners[i], western_winners[i + 1])
                self.playoff_series['division_semifinals'].append(series)
    
    def _create_division_finals(self, winners: List[Team]):
        """Create Division Finals matchups"""
        eastern_winners = [team for team in winners if self._is_eastern_team(team)]
        western_winners = [team for team in winners if not self._is_eastern_team(team)]
        
        # Create conference championship series
        if len(eastern_winners) >= 2:
            series = PlayoffSeries("Division Finals", eastern_winners[0], eastern_winners[1])
            self.playoff_series['division_finals'].append(series)
        
        if len(western_winners) >= 2:
            series = PlayoffSeries("Division Finals", western_winners[0], western_winners[1])
            self.playoff_series['division_finals'].append(series)
    
    def _create_conference_finals(self, winners: List[Team]):
        """Create the Stanley Cup Final from the two conference champions."""
        eastern_winners = [t for t in winners if self._is_eastern_team(t)]
        western_winners = [t for t in winners if not self._is_eastern_team(t)]

        if eastern_winners and western_winners:
            self._create_stanley_cup_final([eastern_winners[0], western_winners[0]])
    
    def _create_stanley_cup_final(self, winners: List[Team]):
        """Create Stanley Cup Final"""
        if len(winners) >= 2:
            series = PlayoffSeries("Stanley Cup Final", winners[0], winners[1])
            self.playoff_series['stanley_cup_final'].append(series)
    
    def simulate_playoff_game(self, series: PlayoffSeries) -> Tuple[int, int]:
        """Simulate a single playoff game and return scores"""
        # Use the existing game simulation but with playoff modifiers
        from simulation import GameSim
        
        # Create game simulation with playoff intensity. Pass the upcoming series
        # game number so playoff officiating (whistle ramp, desperation bump,
        # tension stakes) and rivalries engage correctly.
        game_sim = GameSim(series.team1, series.team2, is_playoff=True,
                           series_game=series.games_played + 1,
                           rivalries=getattr(getattr(self, "league", None),
                                             "rivalries", None))
        result = game_sim.simulate_game()

        # Stash headline specs (brawls, ...) for the lore system; the playoff
        # window drains them via headlines.drain_bracket_headlines().
        try:
            pending = list(getattr(game_sim, "pending_headlines", None) or [])
            if pending:
                stash = getattr(self, "_pending_headlines", None)
                if not isinstance(stash, list):
                    stash = []
                    self._pending_headlines = stash
                stash.extend(pending)
        except Exception:
            pass

        home_score = result.get('home_score', 0)
        away_score = result.get('away_score', 0)

        # Determine winner and update series
        team1_won = home_score > away_score

        # Narrative ledger: per-game facts for series memory. Cheap reads
        # off the finished sim — no extra simulation work.
        game_info = {"game": series.games_played + 1,
                     "t1_score": home_score, "t2_score": away_score,
                     "team1_won": team1_won, "ot": False,
                     "goalie_steal": None}
        try:
            game_info["ot"] = bool(getattr(game_sim, "period", 1) > 3)
            _wteam = series.team1 if team1_won else series.team2
            _wg = game_sim._selected_goalie(_wteam)
            _gs = (getattr(game_sim, "game_stats", {}) or {}).get(
                getattr(_wg, "id", None), {}) or {}
            _saves = int(_gs.get("saves", 0) or 0)
            _svp = float(_gs.get("save_percentage", 0) or 0)
            if _saves >= 32 and _svp >= 0.935:
                _gname = (getattr(_wg, "full_name", None)
                          or getattr(_wg, "name", "the goalie"))
                game_info["goalie_steal"] = f"{_gname} ({_saves} saves)"
        except Exception:
            pass
        series.add_game_result(team1_won, game_info)

        return home_score, away_score
    
    def get_playoff_status(self) -> Dict:
        """Get current playoff status for display"""
        return {
            'current_round': self.current_round,
            'eastern_teams': len(self.eastern_teams),
            'western_teams': len(self.western_teams),
            'total_series': sum(len(series_list) for series_list in self.playoff_series.values()),
            'completed_series': sum(
                len([s for s in series_list if s.is_complete]) 
                for series_list in self.playoff_series.values()
            ),
            'stanley_cup_champion': self.stanley_cup_champion
        }


class PlayoffView(ctk.CTkFrame):
    """NHL Playoff bracket viewer and management window"""
    
    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the PlayoffWindow wrapper
        self.playoff_bracket = None
        
        self.configure(fg_color=self.app.BG_COLOR)
        
        # Create the playoff interface
        self._create_playoff_interface()
        
        # Initialize playoff bracket if season is complete
        self._check_playoff_eligibility()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()
    
    def _create_playoff_interface(self):
        """Create the main playoff interface"""
        # Main frame
        main_frame = ttk.Frame(self, style='Content.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="🏆 NHL Stanley Cup Playoffs", 
                               style='Title.TLabel', font=_sfont(self.app.FONT_FAMILY, 24, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Control buttons
        control_frame = ttk.Frame(main_frame, style='Content.TFrame')
        control_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Button(control_frame, text="Generate Playoff Bracket", 
                  command=self._generate_bracket, style='TButton').pack(side='left', padx=(0, 10))
        
        ttk.Button(control_frame, text="Simulate Round", 
                  command=self._simulate_current_round, style='TButton').pack(side='left', padx=(0, 10))
        
        ttk.Button(control_frame, text="Simulate All Playoffs", 
                  command=self._simulate_all_playoffs, style='TButton').pack(side='left', padx=(0, 10))
        
        # Status frame
        self.status_frame = ttk.LabelFrame(main_frame, text="Playoff Status", style='Card.TLabelframe')
        self.status_frame.pack(fill='x', pady=(0, 20))
        
        self.status_label = ttk.Label(self.status_frame, text="No playoffs generated yet", 
                                     style='Content.TLabel')
        self.status_label.pack(pady=10)
        
        # Bracket display frame
        bracket_container = ttk.Frame(main_frame, style='Content.TFrame')
        bracket_container.pack(fill='both', expand=True)
        
        # Create scrollable bracket view
        canvas = tk.Canvas(bracket_container, bg=self.app.CONTENT_BG)
        scrollbar = ttk.Scrollbar(bracket_container, orient="vertical", command=canvas.yview)
        self.bracket_frame = ttk.Frame(canvas, style='Content.TFrame')
        
        self.bracket_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.bracket_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.canvas = canvas
    
    def _check_playoff_eligibility(self):
        """Check if playoffs can be generated"""
        if hasattr(self.app, 'league') and self.app.league:
            # Check if regular season is complete
            current_date = getattr(self.app, 'current_date', None)
            if current_date:
                playoff_start = date(self.app.league.season_year + 1, 4, 16)
                if current_date >= playoff_start:
                    self.status_label.config(text="Regular season complete - Ready to generate playoffs!")
                else:
                    days_remaining = (playoff_start - current_date).days
                    self.status_label.config(text=f"Regular season in progress - {days_remaining} days until playoffs")
    
    def _generate_bracket(self):
        """Generate the playoff bracket"""
        try:
            if not hasattr(self.app, 'league') or not self.app.league:
                messagebox.showerror("Error", "No league data available")
                return
            
            self.playoff_bracket = PlayoffBracket(self.app.league)
            self.playoff_bracket.generate_playoff_bracket()
            
            self._update_status_display()
            self._display_bracket()
            
            messagebox.showinfo("Playoffs Generated", 
                              f"Playoff bracket created with {len(self.playoff_bracket.eastern_teams)} Eastern and "
                              f"{len(self.playoff_bracket.western_teams)} Western Conference teams!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate playoff bracket: {str(e)}")
    
    def _simulate_current_round(self):
        """Simulate all series in the current round"""
        if not self.playoff_bracket:
            messagebox.showwarning("Warning", "Please generate playoff bracket first")
            return
        
        current_series = self.playoff_bracket.playoff_series[self.playoff_bracket.current_round]
        incomplete_series = [s for s in current_series if not s.is_complete]
        
        if not incomplete_series:
            messagebox.showinfo("Round Complete", "Current round is already complete!")
            return
        
        # Heavy sim: warn, fallback-save, then show live progress.
        import sim_progress
        if not sim_progress.confirm_heavy_sim(
                self, "Simulate Round",
                f"This will simulate every remaining game of the "
                f"{self.playoff_bracket.current_round} round."):
            return
        sim_progress.create_fallback_save(self.app, "playoffs_round")
        dlg = sim_progress.SimProgressDialog(
            self, title="Simulating Playoff Round")
        try:
            games_done = 0
            est_total = max(1, len(incomplete_series) * 7)
            for si, series in enumerate(incomplete_series):
                while not series.is_complete:
                    home_score, away_score = self.playoff_bracket.simulate_playoff_game(series)
                    games_done += 1
                    dlg.update(games_done / est_total,
                               f"Series {si + 1}/{len(incomplete_series)} "
                               f"-- game {games_done} simulated")
        finally:
            dlg.close()

        # Lore: deliver any headlines stashed during the round (brawls, ...).
        try:
            import headlines
            headlines.drain_bracket_headlines(self.app, self.playoff_bracket)
        except Exception:
            pass

        # Advance to next round (bracket updates its own current_round)
        self.playoff_bracket.advance_to_next_round(self.playoff_bracket.current_round)

        self._update_status_display()
        self._display_bracket()
        
        # Check if playoffs are complete
        if self.playoff_bracket.stanley_cup_champion:
            messagebox.showinfo("Stanley Cup Champion!", 
                              f"🏆 {self.playoff_bracket.stanley_cup_champion.team_name} "
                              f"wins the Stanley Cup!")
    
    def _simulate_all_playoffs(self):
        """Simulate the entire playoff tournament"""
        if not self.playoff_bracket:
            messagebox.showwarning("Warning", "Please generate playoff bracket first")
            return
        
        # Heavy sim: warn, fallback-save, then show live progress.
        # (Also driven headless by season bulk-sim; the dialog degrades
        # gracefully if no display is available.)
        import sim_progress
        try:
            _headless = bool(getattr(self.app, '_bulk_simming', False))
        except Exception:
            _headless = False
        if not _headless and not sim_progress.confirm_heavy_sim(
                self, "Simulate All Playoffs",
                "This will simulate every remaining playoff game through "
                "the Stanley Cup Final."):
            return
        sim_progress.create_fallback_save(self.app, "playoffs_all")
        dlg = None
        if not _headless:
            try:
                dlg = sim_progress.SimProgressDialog(
                    self, title="Simulating Stanley Cup Playoffs")
            except Exception:
                dlg = None

        round_order = PlayoffBracket.ROUND_ORDER
        games_done = 0
        try:
            for round_name in round_order:
                self.playoff_bracket.current_round = round_name
                current_series = self.playoff_bracket.playoff_series[round_name]

                # Simulate all series in this round
                for si, series in enumerate(current_series):
                    while not series.is_complete:
                        self.playoff_bracket.simulate_playoff_game(series)
                        games_done += 1
                        if dlg is not None:
                            dlg.update(games_done / 105.0,
                                       f"{str(round_name).replace('_', ' ').title()}: "
                                       f"series {si + 1}/{len(current_series)} "
                                       f"-- game {games_done} simulated")

                # Advance winners to next round
                self.playoff_bracket.advance_to_next_round(round_name)
        finally:
            if dlg is not None:
                dlg.close()

        # Lore: deliver any headlines stashed during the tournament.
        try:
            import headlines
            headlines.drain_bracket_headlines(self.app, self.playoff_bracket)
        except Exception:
            pass

        self._update_status_display()
        self._display_bracket()
        
        if self.playoff_bracket.stanley_cup_champion:
            messagebox.showinfo("Playoffs Complete!", 
                              f"🏆 {self.playoff_bracket.stanley_cup_champion.team_name} "
                              f"are your Stanley Cup Champions!")
    
    def _update_status_display(self):
        """Update the status display"""
        if not self.playoff_bracket:
            return
        
        status = self.playoff_bracket.get_playoff_status()
        
        if status['stanley_cup_champion']:
            status_text = f"🏆 Stanley Cup Champions: {status['stanley_cup_champion'].team_name}"
        else:
            status_text = (f"Current Round: {status['current_round'].replace('_', ' ').title()}\n"
                          f"Series: {status['completed_series']}/{status['total_series']} completed")
        
        self.status_label.config(text=status_text)
    
    def _display_bracket(self):
        """Display the playoff bracket"""
        # Clear existing bracket display
        for widget in self.bracket_frame.winfo_children():
            widget.destroy()
        
        if not self.playoff_bracket:
            return
        
        row = 0
        
        # Display each round
        round_order = PlayoffBracket.ROUND_ORDER
        
        for round_name in round_order:
            series_list = self.playoff_bracket.playoff_series[round_name]
            if not series_list:
                continue
            
            # Round header
            round_title = round_name.replace('_', ' ').title()
            round_label = ttk.Label(self.bracket_frame, text=f"🏒 {round_title}", 
                                   style='Heading.TLabel', font=_sfont(self.app.FONT_FAMILY, 16, 'bold'))
            round_label.grid(row=row, column=0, columnspan=4, pady=(20, 10), sticky='w')
            row += 1
            
            # Display series
            for i, series in enumerate(series_list):
                self._display_series(series, row, i % 2)
                if i % 2 == 1:  # Two series per row
                    row += 1
            
            if len(series_list) % 2 == 1:  # Odd number of series
                row += 1
    
    def _display_series(self, series: PlayoffSeries, row: int, col: int):
        """Display a single playoff series"""
        # Series frame
        series_frame = ttk.LabelFrame(self.bracket_frame, text=f"{series.round_name}", 
                                     style='Card.TLabelframe')
        series_frame.grid(row=row, column=col*2, columnspan=2, padx=10, pady=5, sticky='ew')
        
        # Team 1
        team1_frame = ttk.Frame(series_frame, style='Content.TFrame')
        team1_frame.pack(fill='x', padx=5, pady=2)
        
        team1_name = f"{series.team1.team_name}"
        if series.winner == series.team1:
            team1_name += " 🏆"
        
        ttk.Label(team1_frame, text=team1_name, style='Content.TLabel').pack(side='left')
        ttk.Label(team1_frame, text=f"Wins: {series.team1_wins}", 
                 style='Content.TLabel').pack(side='right')
        
        # VS separator
        ttk.Label(series_frame, text="vs", style='Content.TLabel', 
                 font=_sfont(self.app.FONT_FAMILY, 10, 'italic')).pack()
        
        # Team 2
        team2_frame = ttk.Frame(series_frame, style='Content.TFrame')
        team2_frame.pack(fill='x', padx=5, pady=2)
        
        team2_name = f"{series.team2.team_name}"
        if series.winner == series.team2:
            team2_name += " 🏆"
        
        ttk.Label(team2_frame, text=team2_name, style='Content.TLabel').pack(side='left')
        ttk.Label(team2_frame, text=f"Wins: {series.team2_wins}", 
                 style='Content.TLabel').pack(side='right')
        
        # Series status
        if series.is_complete:
            status_text = f"Series Complete ({series.games_played} games)"
        else:
            wins_needed = (series.series_format // 2) + 1
            status_text = f"In Progress (First to {wins_needed})"
        
        ttk.Label(series_frame, text=status_text, style='Content.TLabel', 
                 font=_sfont(self.app.FONT_FAMILY, 8)).pack(pady=(5, 0))


def test_playoff_system():
    """Test the playoff system with sample data"""
    from game_classes import League, Team
    
    # Create test league with proper parameter order
    league = League(league_name="Test League", season_year=2024)
    
    # Clear default teams and add our test teams
    league.teams.clear()
    
    # Create test teams with standings
    teams_data = [
        ("Boston Bruins", "Atlantic", 60, 15, 7, 127),
        ("Toronto Maple Leafs", "Atlantic", 50, 25, 7, 107),
        ("Tampa Bay Lightning", "Atlantic", 48, 30, 4, 100),
        ("Florida Panthers", "Atlantic", 42, 32, 8, 92),
        ("New York Rangers", "Metropolitan", 55, 23, 4, 114),
        ("Carolina Hurricanes", "Metropolitan", 52, 24, 6, 110),
        ("New Jersey Devils", "Metropolitan", 47, 25, 10, 104),
        ("Washington Capitals", "Metropolitan", 35, 37, 10, 80),
        ("Colorado Avalanche", "Central", 58, 19, 5, 121),
        ("Dallas Stars", "Central", 47, 21, 14, 108),
        ("Minnesota Wild", "Central", 46, 25, 11, 103),
        ("Winnipeg Jets", "Central", 43, 32, 7, 93),
        ("Vegas Golden Knights", "Pacific", 51, 22, 9, 111),
        ("Edmonton Oilers", "Pacific", 50, 25, 7, 107),
        ("Los Angeles Kings", "Pacific", 44, 27, 11, 99),
        ("Seattle Kraken", "Pacific", 46, 28, 8, 100),
        ("Buffalo Sabres", "Atlantic", 39, 37, 6, 84),
        ("Detroit Red Wings", "Atlantic", 35, 37, 10, 80),
        ("Columbus Blue Jackets", "Metropolitan", 25, 48, 9, 59),
        ("Philadelphia Flyers", "Metropolitan", 31, 38, 13, 75),
    ]
    
    for name, division, wins, losses, otl, points in teams_data:
        team = Team(name, name, division, "Eastern" if division in ["Atlantic", "Metropolitan"] else "Western")
        team.wins = wins
        team.losses = losses
        team.ot_losses = otl
        team.standings_position = points  # Simple position based on points
        league.teams.append(team)
    
    # Test playoff bracket generation
    bracket = PlayoffBracket(league)
    bracket.generate_playoff_bracket()
    
    print("=== PLAYOFF BRACKET GENERATED ===")
    print(f"Eastern Conference Teams: {len(bracket.eastern_teams)}")
    for i, team in enumerate(bracket.eastern_teams, 1):
        print(f"  {i}. {team.team_name} ({team.points} pts)")
    
    print(f"\nWestern Conference Teams: {len(bracket.western_teams)}")
    for i, team in enumerate(bracket.western_teams, 1):
        print(f"  {i}. {team.team_name} ({team.points} pts)")
    
    print(f"\nWild Card Round Matchups: {len(bracket.playoff_series['wild_card'])}")
    for series in bracket.playoff_series['wild_card']:
        print(f"  {series.team1.team_name} vs {series.team2.team_name}")
    
    return bracket


if __name__ == "__main__":
    # Test the playoff system
    test_bracket = test_playoff_system()
    print("\nPlayoff system test completed successfully!")


class PlayoffWindow(InGamePopup):
    """Popup wrapper around PlayoffView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("NHL Playoffs - Stanley Cup Tournament")
        self._view = PlayoffView(self, app=parent, *args, **kwargs)
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
