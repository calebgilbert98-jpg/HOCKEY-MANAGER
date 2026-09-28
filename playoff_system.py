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
from typing import List, Dict, Tuple, Optional, Any
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


def _cfont(family, size, weight=""):
    """CTk-compatible font (CTk widgets reject tkinter.font.Font).

    Plain tuples keep working everywhere; ui_scale live-resize does not
    apply here, which is fine for bracket chrome.
    """
    try:
        return ctk.CTkFont(family=family, size=size,
                           weight=weight if weight else "normal")
    except Exception:
        return (family, size, weight) if weight else (family, size)


TEAM_ABBREVIATIONS = {
    'Anaheim Ducks': 'ANA', 'Boston Bruins': 'BOS', 'Buffalo Sabres': 'BUF',
    'Carolina Hurricanes': 'CAR', 'Columbus Blue Jackets': 'CBJ',
    'Calgary Flames': 'CGY', 'Chicago Blackhawks': 'CHI', 'Colorado Avalanche': 'COL',
    'Dallas Stars': 'DAL', 'Detroit Red Wings': 'DET', 'Edmonton Oilers': 'EDM',
    'Florida Panthers': 'FLA', 'Los Angeles Kings': 'LAK', 'Minnesota Wild': 'MIN',
    'Montreal Canadiens': 'MTL', 'New Jersey Devils': 'NJD',
    'Nashville Predators': 'NSH', 'New York Islanders': 'NYI',
    'New York Rangers': 'NYR', 'Ottawa Senators': 'OTT',
    'Philadelphia Flyers': 'PHI', 'Pittsburgh Penguins': 'PIT',
    'Seattle Kraken': 'SEA', 'San Jose Sharks': 'SJS', 'St. Louis Blues': 'STL',
    'Tampa Bay Lightning': 'TBL', 'Toronto Maple Leafs': 'TOR',
    'Utah Mammoth': 'UTA', 'Utah Hockey Club': 'UTA', 'Arizona Coyotes': 'ARI',
    'Vancouver Canucks': 'VAN', 'Vegas Golden Knights': 'VGK',
    'Winnipeg Jets': 'WPG', 'Washington Capitals': 'WSH',
}


def team_abbr(team_name):
    """Three-letter abbreviation for a team name (fallback: first 3 letters)."""
    if not team_name:
        return "???"
    return TEAM_ABBREVIATIONS.get(team_name, team_name[:3].upper())


ROUND_DISPLAY_NAMES = {
    'wild_card': 'Round 1',
    'division_semifinals': 'Round 2',
    'division_finals': 'Conference Finals',
    'conference_finals': 'Conference Finals',
    'stanley_cup_final': 'Stanley Cup Final',
}


def series_status_text(series):
    """One-line series status, e.g. 'BOS leads 3-2', 'Series tied 2-2'.

    Returns (text, decided_bool). Shared by the bracket tree and the
    series-detail popup so both always agree.
    """
    try:
        a = team_abbr(getattr(series.team1, 'team_name', ''))
        b = team_abbr(getattr(series.team2, 'team_name', ''))
        w1 = int(getattr(series, 'team1_wins', 0) or 0)
        w2 = int(getattr(series, 'team2_wins', 0) or 0)
        if int(getattr(series, 'games_played', 0) or 0) == 0:
            return "Series not started", False
        if getattr(series, 'is_complete', False):
            winner = getattr(series, 'winner', None)
            w = team_abbr(getattr(winner, 'team_name', '')) if winner is not None else (a if w1 > w2 else b)
            return f"{w} wins {max(w1, w2)}-{min(w1, w2)}", True
        if w1 == w2:
            return f"Series tied {w1}-{w2}", False
        leader = a if w1 > w2 else b
        return f"{leader} leads {max(w1, w2)}-{min(w1, w2)}", False
    except Exception:
        return "", False


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
        # Per-game observers (the PlayoffView registers one so the bracket
        # tree refreshes live as each game is simmed). Empty by default:
        # zero behavior change for bulk/headless sims.
        self._game_listeners: List[Any] = []
        # True when this object is a standings projection (pre-playoffs),
        # not the real tournament bracket.
        self.is_projection = False

    def add_game_listener(self, fn):
        """Register fn(series) to run after every simmed playoff game."""
        try:
            if callable(fn) and fn not in self._game_listeners:
                self._game_listeners.append(fn)
        except Exception:
            pass

    def discard_game_listener(self, fn):
        try:
            if fn in self._game_listeners:
                self._game_listeners.remove(fn)
        except Exception:
            pass

    def _notify_game_listeners(self, series):
        for fn in list(self._game_listeners):
            try:
                fn(series)
            except Exception:
                pass

    def build_projection(self):
        """Build a projected Round 1 from the current standings.

        Used by the bracket tree before the playoffs kick off: shows the
        matchups as they would be if the season ended today. Later rounds
        are genuinely unknown, so only the wild-card round is projected.
        """
        eastern, western = self._get_playoff_qualified_teams()
        self.eastern_teams = eastern
        self.western_teams = western
        for i, team in enumerate(eastern):
            team.standings_position = i + 1
        for i, team in enumerate(western):
            team.standings_position = i + 1
        for key in self.playoff_series:
            self.playoff_series[key] = []
        self._create_wild_card_round()
        self.is_projection = True
        self.current_round = 'wild_card'
        return self
        
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
                # The Cup is lifted: decide the playoff MVP now, while the
                # full playoff ledger is still in memory. Real-life criteria:
                # almost always the champion's best player -- the playoff
                # scoring leader, or a goalie on an all-time run.
                try:
                    self._decide_conn_smythe()
                except Exception:
                    pass

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
        # tension stakes) and rivalries engage correctly. The crowd knows the
        # stakes too: elimination games and Game 7s get a louder building.
        from arena_atmosphere import pregame_crowd, crowd_hype_for_tension
        _elim = (series.team1_wins == 3 or series.team2_wins == 3)
        _game_no = series.games_played + 1
        try:
            from narrative_ledger import active_ledger as _al
            _led = _al()
        except Exception:
            _led = None
        _atm = pregame_crowd(series.team1, series.team2, ledger=_led,
                             is_playoff=True, series_game=_game_no,
                             elimination_game=_elim)
        game_sim = GameSim(series.team1, series.team2, is_playoff=True,
                           series_game=_game_no,
                           rivalries=getattr(getattr(self, "league", None),
                                             "rivalries", None),
                           atmosphere=_atm,
                           crowd_hype=crowd_hype_for_tension(
                               _atm.get("energy", 50.0),
                               _atm.get("mood", 30.0)))
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

        # Playoff stat ledger: fold this game's per-player numbers into each
        # player's season playoff_stats (feeds the Conn Smythe race). Cheap:
        # one pass over the finished game's stat table, no extra simulation.
        try:
            self._fold_playoff_stats(game_sim, series.team1, series.team2,
                                     team1_won)
        except Exception:
            pass

        # Live bracket: tell observers (the tree view) a game just finished.
        self._notify_game_listeners(series)

        return home_score, away_score

    def _fold_playoff_stats(self, game_sim: Any, team1: Any, team2: Any,
                            team1_won: bool) -> None:
        """Accumulate GameSim.game_stats into Player.playoff_stats.

        Skaters: GP/g/a. Goalies: GP/saves/shots_against/goals_against/
        shutouts, plus a win/loss for the two starters (the winning team's
        selected goalie takes the win -- the real-life criterion the
        playoff MVP voters actually watch).
        """
        stats = getattr(game_sim, "game_stats", None) or {}
        wteam = team1 if team1_won else team2
        lteam = team2 if team1_won else team1
        wgoalie = lgoalie = None
        try:
            wgoalie = game_sim._selected_goalie(wteam)
            lgoalie = game_sim._selected_goalie(lteam)
        except Exception:
            pass
        wid = getattr(wgoalie, "id", None)
        lid = getattr(lgoalie, "id", None)
        for pid, gs in stats.items():
            if not isinstance(gs, dict):
                continue
            p = gs.get("player")
            if p is None:
                continue
            ps = getattr(p, "playoff_stats", None)
            if ps is None:
                continue
            try:
                ps.games_played = int(getattr(ps, "games_played", 0) or 0) + 1
                ps.goals = int(getattr(ps, "goals", 0) or 0) + int(
                    gs.get("g", 0) or 0)
                ps.assists = int(getattr(ps, "assists", 0) or 0) + int(
                    gs.get("a", 0) or 0)
                ps.saves = int(getattr(ps, "saves", 0) or 0) + int(
                    gs.get("saves", 0) or 0)
                ps.shots_against = int(
                    getattr(ps, "shots_against", 0) or 0) + int(
                    gs.get("shots_against", 0) or 0)
                ps.goals_against = int(
                    getattr(ps, "goals_against", 0) or 0) + int(
                    gs.get("goals_against", 0) or 0)
                ps.shutouts = int(getattr(ps, "shutouts", 0) or 0) + int(
                    gs.get("shutouts", 0) or 0)
                if pid == wid:
                    ps.wins = int(getattr(ps, "wins", 0) or 0) + 1
                elif pid == lid:
                    ps.losses = int(getattr(ps, "losses", 0) or 0) + 1
            except Exception:
                continue

    # Conn Smythe bar for goalies: an all-time run (Giguere .945 in '03,
    # Hextall '87, Vasilevskiy .937 in '21). Below it, the skaters decide.
    _SMYTHE_GOALIE_SV = 0.935
    _SMYTHE_GOALIE_WINS = 12

    @staticmethod
    def _smythe_is_goalie(p: Any) -> bool:
        try:
            pos = getattr(p, "primary_position", None)
            pv = str(getattr(pos, "value", pos) or "").upper()
            return pv in ("G", "GOALIE", "GOALTENDER") or bool(
                getattr(p, "is_goalie", False))
        except Exception:
            return False

    def _decide_conn_smythe(self) -> Optional[Any]:
        """Pick the playoff MVP by real-life criteria and bank it.

        The Conn Smythe goes to the most valuable player of the playoffs.
        In practice that means:
          1. The Stanley Cup champion's playoff scoring leader, UNLESS
          2. the champion's goalie authored an all-time run (SV% >= .935
             with 12+ wins -- Vasilevskiy '21, Quick '12, Giguere '03), OR
          3. a skater on the LOSING side authored a historic run:
             >= 35 playoff points AND >= 1.5x the champion's best skater
             total (McDavid '24: 42 pts vs the Panthers' best ~24;
             Leach '76: 24 pts, 19 goals).
        Narrative exceptions the numbers can't capture (Crosby '16,
        Hedman '20, Crozier '66, Hextall '87) are documented in
        docs/CONN_SMYTHE_COACHES_GUIDE.md as a known limitation.

        The winner is banked into his trophy case immediately and stashed
        on the bracket (``conn_smythe_winner`` / ``conn_smythe_name``)
        for the offseason rollover (season history + reputation).
        """
        champ = getattr(self, "stanley_cup_champion", None)
        if champ is None:
            return None
        roster = list(getattr(champ, "roster", None) or [])
        best_skater = None
        best_skater_key = None
        best_goalie = None
        best_goalie_key = None
        for p in roster:
            ps = getattr(p, "playoff_stats", None)
            if ps is None:
                continue
            gp = int(getattr(ps, "games_played", 0) or 0)
            if gp <= 0:
                continue
            g = int(getattr(ps, "goals", 0) or 0)
            a = int(getattr(ps, "assists", 0) or 0)
            if self._smythe_is_goalie(p):
                w = int(getattr(ps, "wins", 0) or 0)
                sa = int(getattr(ps, "shots_against", 0) or 0)
                sv = (int(getattr(ps, "saves", 0) or 0) / sa) if sa else 0.0
                key = (w, round(sv, 4))
                if best_goalie_key is None or key > best_goalie_key:
                    best_goalie, best_goalie_key = p, key
            else:
                key = (g + a, g)
                if best_skater_key is None or key > best_skater_key:
                    best_skater, best_skater_key = p, key
        winner = None
        if best_goalie is not None:
            gw, gsv = best_goalie_key
            if gw >= self._SMYTHE_GOALIE_WINS and gsv >= self._SMYTHE_GOALIE_SV:
                winner = best_goalie
        if winner is None:
            # McDavid/Leach historic-run exception: a skater on a losing
            # team wins only if his run was genuinely historic -- >= 35
            # playoff points AND >= 1.5x the champion's best skater total.
            loser = self._historic_loser_run(best_skater_key)
            if loser is not None:
                winner = loser
            else:
                winner = (best_skater if best_skater is not None
                          else best_goalie)
        if winner is None:
            return None
        self.conn_smythe_winner = winner
        try:
            self.conn_smythe_name = (
                getattr(winner, "full_name", None)
                or getattr(winner, "name", None) or "?")
        except Exception:
            self.conn_smythe_name = "?"
        # Bank the trophy immediately so the player's case shows it even if
        # the user quits before the offseason rollover.
        try:
            from accolades import bank_accolade
            from coach_records import season_label
            league = getattr(self, "league", None)
            year = int(getattr(league, "season_year", 2025) or 2025)
            bank_accolade(winner, "conn_smythe", season_label(year))
        except Exception:
            pass
        return winner

    def _historic_loser_run(self, champ_best_key):
        """McDavid '24 / Leach '76 exception.

        Scan every NON-champion playoff roster for a skater with >= 35
        playoff points and a total >= 1.5x the champion's best skater.
        Returns the player, or None.
        """
        try:
            if not champ_best_key:
                return None
            champ_pts = champ_best_key[0]
            league = getattr(self, "league", None)
            teams = list(getattr(league, "teams", None) or [])
            champ = getattr(self, "stanley_cup_champion", None)
            champ_name = getattr(champ, "team_name", None)
            best = None
            best_key = None
            for t in teams:
                if getattr(t, "team_name", None) == champ_name:
                    continue
                for p in list(getattr(t, "roster", None) or []):
                    if self._smythe_is_goalie(p):
                        continue
                    ps = getattr(p, "playoff_stats", None)
                    if ps is None:
                        continue
                    gp = int(getattr(ps, "games_played", 0) or 0)
                    if gp <= 0:
                        continue
                    pts = (int(getattr(ps, "goals", 0) or 0)
                           + int(getattr(ps, "assists", 0) or 0))
                    if pts < 35:
                        continue
                    if champ_pts and pts < 1.5 * champ_pts:
                        continue
                    key = (pts, int(getattr(ps, "goals", 0) or 0))
                    if best_key is None or key > best_key:
                        best, best_key = p, key
            return best
        except Exception:
            return None
    
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
        self._bracket_refresh_pending = False
        
        self.configure(fg_color=self.app.BG_COLOR)
        
        # Create the playoff interface
        self._create_playoff_interface()

        # Adopt a live bracket already running on the league (e.g. the
        # window was closed mid-playoffs and reopened). The tree then shows
        # the real tournament, never a stale projection.
        try:
            _lb = getattr(getattr(self.app, 'league', None), 'playoff_bracket', None)
            if _lb is not None and getattr(_lb, 'playoff_series', None):
                if any(_lb.playoff_series.get(r) for r in PlayoffBracket.ROUND_ORDER):
                    self.playoff_bracket = _lb
                    _lb.add_game_listener(self._on_bracket_game)
        except Exception:
            pass
        
        # Initialize playoff bracket if season is complete
        self._check_playoff_eligibility()
        self._update_status_display()
        self._display_bracket()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        try:
            if self.playoff_bracket is not None:
                self.playoff_bracket.discard_game_listener(self._on_bracket_game)
        except Exception:
            pass
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
        
        ttk.Button(control_frame, text="Refresh Bracket",
                  command=self.refresh_bracket, style='TButton').pack(side='left', padx=(0, 10))

        # Season-long LEAGUE TENSION gauge (the in-game INTENSITY meter's
        # big brother): the league sees at a glance whether tensions are
        # high across the season, and which incident is driving it.
        try:
            self._tension_frame = ttk.Frame(control_frame,
                                            style='Content.TFrame')
            self._tension_frame.pack(side='right', padx=(10, 0))
            self._tension_canvas = tk.Canvas(
                self._tension_frame, width=210, height=150,
                bg=self.app.CONTENT_BG, highlightthickness=0)
            self._tension_canvas.pack()
            self._tension_driver = ttk.Label(
                self._tension_frame, text="", style='Content.TLabel',
                font=_sfont(self.app.FONT_FAMILY, 9, 'italic'),
                wraplength=200, justify='center')
            self._tension_driver.pack(pady=(0, 2))
        except Exception:
            self._tension_canvas = None
            self._tension_driver = None
        
        # Status frame
        self.status_frame = ttk.LabelFrame(main_frame, text="Playoff Status", style='Card.TLabelframe')
        self.status_frame.pack(fill='x', pady=(0, 8))
        
        self.status_label = ttk.Label(self.status_frame, text="No playoffs generated yet", 
                                     style='Content.TLabel')
        self.status_label.pack(pady=6)

        # Projection banner (visible only while the tree shows projected
        # matchups instead of the real tournament).
        self.projection_label = ttk.Label(
            main_frame, text="", style='Content.TLabel',
            font=_sfont(self.app.FONT_FAMILY, 11, 'italic'))
        self.projection_label.pack(fill='x', pady=(0, 6))
        
        # Bracket display frame
        bracket_container = ttk.Frame(main_frame, style='Content.TFrame')
        bracket_container.pack(fill='both', expand=True)
        
        # Scrollable bracket tree (drawn directly on the canvas: series
        # cards are embedded windows, rounds linked by connector lines).
        canvas = tk.Canvas(bracket_container, bg=self.app.CONTENT_BG,
                           highlightthickness=0)
        vscroll = ttk.Scrollbar(bracket_container, orient="vertical",
                                command=canvas.yview)
        hscroll = ttk.Scrollbar(bracket_container, orient="horizontal",
                                command=canvas.xview)
        canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")
        bracket_container.grid_rowconfigure(0, weight=1)
        bracket_container.grid_columnconfigure(0, weight=1)

        # Bottom ticker: 2K-style selected-series readout bar.
        try:
            self.ticker_label = tk.Label(
                main_frame, text="", anchor="center", justify="center",
                bg=self.BRACKET_TICKER_BG, fg="#E8EDF2",
                font=_sfont(self.app.FONT_FAMILY, 12, "bold"))
            self.ticker_label.pack(fill="x", ipady=8, pady=(8, 0))
        except Exception:
            self.ticker_label = None

        self.canvas = canvas
        self._refresh_tension_gauge()
    
    def _check_playoff_eligibility(self):
        """Check if playoffs can be generated"""
        # A live bracket is already showing: its own status line owns this.
        if self.playoff_bracket is not None:
            return
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
            # The bracket lives on the league: reopening this window
            # mid-playoffs (or any other reader) finds the live tournament.
            try:
                self.app.league.playoff_bracket = self.playoff_bracket
            except Exception:
                pass
            self.playoff_bracket.add_game_listener(self._on_bracket_game)
            
            self._update_status_display()
            self._display_bracket()
            
            messagebox.showinfo("Playoffs Generated", 
                              f"Playoff bracket created with {len(self.playoff_bracket.eastern_teams)} Eastern and "
                              f"{len(self.playoff_bracket.western_teams)} Western Conference teams!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate playoff bracket: {str(e)}")

    # ------------------------------------------------------------------
    # Live bracket updates
    # ------------------------------------------------------------------
    def refresh_bracket(self):
        """Public: rebuild the tree from the current bracket state."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._update_status_display()
        self._display_bracket()
        self._refresh_tension_gauge()

    def _refresh_tension_gauge(self):
        """Redraw the season-long LEAGUE TENSION gauge. Never raises."""
        c = getattr(self, '_tension_canvas', None)
        if c is None:
            return
        try:
            c.delete("all")
        except Exception:
            return
        try:
            from narrative_ledger import active_ledger as _al
            from season_intensity import season_intensity, draw_gauge
            info = season_intensity(_al())
            draw_gauge(c, 105, 88, 52, info,
                       font_family=getattr(self.app, 'FONT_FAMILY', 'Arial'))
            drv = self._tension_driver
            if drv is not None:
                try:
                    drivers = info.get("drivers") or []
                    if drivers and float(info.get("value", 0) or 0) >= 25:
                        dtxt = str(drivers[0].get("label", "") or "")[:95]
                        drv.configure(text=f"Driven by: {dtxt}")
                    else:
                        drv.configure(text="A calm league \u2014 for now.")
                except Exception:
                    pass
        except Exception:
            pass

    def _on_bracket_game(self, series):
        """Listener: a playoff game just finished (possibly on a worker
        thread). Coalesce rapid game bursts into one tree refresh on the
        UI thread."""
        if self._bracket_refresh_pending:
            return
        self._bracket_refresh_pending = True
        try:
            self.after(250, self._coalesced_bracket_refresh)
        except Exception:
            self._bracket_refresh_pending = False

    def _coalesced_bracket_refresh(self):
        self._bracket_refresh_pending = False
        try:
            self.refresh_bracket()
        except Exception:
            pass
    
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
                    # The tree shows every game as it lands.
                    self._display_bracket()
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
        """Simulate the entire playoff tournament.

        Interactive path: the sim runs in a worker thread behind a
        cancelable progress dialog, so the UI stays responsive (the old
        ~69s main-thread freeze is gone). Cancel keeps every game already
        played. Headless/bulk path: synchronous, unchanged.
        """
        if not self.playoff_bracket:
            messagebox.showwarning("Warning", "Please generate playoff bracket first")
            return

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

        bracket = self.playoff_bracket
        round_order = PlayoffBracket.ROUND_ORDER

        def _run_games(cancel_event, progress):
            """Worker body: pure sim, no widgets. Runs off the UI thread."""
            games_done = 0
            for round_name in round_order:
                bracket.current_round = round_name
                current_series = bracket.playoff_series[round_name]

                # Simulate all series in this round
                for si, series in enumerate(current_series):
                    while not series.is_complete:
                        if cancel_event is not None and cancel_event.is_set():
                            return
                        bracket.simulate_playoff_game(series)
                        games_done += 1
                        if progress is not None:
                            progress(games_done / 105.0,
                                     f"{str(round_name).replace('_', ' ').title()}: "
                                     f"series {si + 1}/{len(current_series)} "
                                     f"-- game {games_done} simulated")

                # Advance winners to next round
                bracket.advance_to_next_round(round_name)
                if cancel_event is not None and cancel_event.is_set():
                    return

        if _headless:
            # Bulk sim: synchronous, no dialog (driven by main.py, which
            # checks _playoffs_complete() immediately after).
            _run_games(None, None)
            self._finish_all_playoffs(cancelled=False)
            return

        def _on_done(cancelled, error):
            if error is not None:
                try:
                    from popup_system import messagebox as _mb
                    _mb.showerror("Playoff sim failed",
                                  f"The playoff sim hit an error and stopped:\n{error}\n\n"
                                  "Your fallback save was created before the sim started.",
                                  parent=self)
                except Exception:
                    pass
            self._finish_all_playoffs(cancelled=cancelled or error is not None)

        sim_progress.run_threaded(
            self, "Simulating Stanley Cup Playoffs",
            _run_games, _on_done)

    def _finish_all_playoffs(self, cancelled=False):
        """UI-thread wrap-up after Sim All: lore drain, bracket refresh,
        champion (or partial-progress) notice."""
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
                              f"\U0001f3c6 {self.playoff_bracket.stanley_cup_champion.team_name} "
                              f"are your Stanley Cup Champions!")
        elif cancelled:
            messagebox.showinfo("Playoff sim cancelled",
                                "The sim was cancelled. The bracket keeps every "
                                "game already played -- Sim All again to continue.")
    
    def _update_status_display(self):
        """Update the status display"""
        if not self.playoff_bracket:
            # Projection mode (or nothing yet): say so instead of going stale.
            try:
                _proj = self._build_projection_bracket()
            except Exception:
                _proj = None
            if _proj is not None:
                self.status_label.config(
                    text="Pre-playoffs — projected Round 1 matchups below.")
            else:
                self.status_label.config(text="No playoffs generated yet")
            return
        
        status = self.playoff_bracket.get_playoff_status()
        
        if status['stanley_cup_champion']:
            status_text = f"🏆 Stanley Cup Champions: {status['stanley_cup_champion'].team_name}"
        else:
            status_text = (f"Current Round: {status['current_round'].replace('_', ' ').title()}\n"
                          f"Series: {status['completed_series']}/{status['total_series']} completed")
        
        self.status_label.config(text=status_text)
    
    # ------------------------------------------------------------------
    # Bracket tree (2K-style mirrored layout)
    # ------------------------------------------------------------------
    BRACKET_CARD_W = 264
    BRACKET_GAP_X = 96
    BRACKET_PAD = 24
    BRACKET_GAP_Y = 26
    BRACKET_NAVY = "#0A1428"
    BRACKET_TICKER_BG = "#0E1930"

    # Column definitions: (round_key, conference). West advances left->in,
    # East advances right->in, the Cup is decided in the middle -- the
    # mirrored conference bracket from the reference.
    BRACKET_COLUMNS = (
        ("wild_card", "Western"),
        ("division_semifinals", "Western"),
        ("division_finals", "Western"),
        ("stanley_cup_final", None),
        ("division_finals", "Eastern"),
        ("division_semifinals", "Eastern"),
        ("wild_card", "Eastern"),
    )
    # Column indices positioned after both Round 1 columns, so every
    # card's feeders are already placed when it is centered on them.
    BRACKET_LAYOUT_ORDER = (0, 6, 1, 5, 2, 4, 3)

    @staticmethod
    def _series_conference(series):
        """Conference of a series (both clubs share one until the Final)."""
        for t in (getattr(series, 'team1', None),
                  getattr(series, 'team2', None)):
            c = getattr(t, 'conference', '') or ''
            if c in ("Eastern", "Western"):
                return c
        return "Western"  # unknown -> left side, keeps the tree balanced

    @staticmethod
    def _r1_sort_key(s):
        """Round 1 top-to-bottom: 1v8, 4v5, 3v6, 2v7 by top seed."""
        def _seed(t):
            try:
                return int(getattr(t, 'standings_position', 99) or 99)
            except Exception:
                return 99
        t1, t2 = getattr(s, 'team1', None), getattr(s, 'team2', None)
        return min(_seed(t1), _seed(t2))

    def _tree_bracket(self):
        """Return (bracket, projected_bool) for the tree.

        The live tournament when one exists; otherwise a standings
        projection so the tree is never empty mid-season.
        """
        b = self.playoff_bracket
        try:
            if b is not None and getattr(b, 'playoff_series', None):
                if any(b.playoff_series.get(r) for r in PlayoffBracket.ROUND_ORDER):
                    return b, bool(getattr(b, 'is_projection', False))
        except Exception:
            pass
        proj = self._build_projection_bracket()
        return proj, proj is not None

    def _build_projection_bracket(self):
        """Projected Round 1 from the current standings (pre-playoffs)."""
        try:
            league = getattr(self.app, 'league', None)
            if league is None or not getattr(league, 'teams', None):
                return None
            b = PlayoffBracket(league)
            b.build_projection()
            return b if b.playoff_series.get('wild_card') else None
        except Exception:
            return None

    def _set_projection_banner(self, projected, bracket):
        lbl = getattr(self, 'projection_label', None)
        if lbl is None:
            return
        try:
            if projected:
                dt = getattr(self.app, 'current_date', None)
                when = f"as of {dt}" if dt else "based on current standings"
                lbl.configure(
                    text=f"🔮 PROJECTION {when} — matchups lock in when the playoffs begin.")
            else:
                lbl.configure(text="")
        except Exception:
            pass

    def _display_bracket(self):
        """Draw the playoff bracket as a 2K-style mirrored tree.

        West rounds run down the left edge inward, East rounds down the
        right edge inward, the Stanley Cup Final sits in the middle under
        a Cup emblem. Series cards wear team colors with the series-wins
        badge at the outer edge; white elbow connectors link rounds; the
        bottom ticker reads out the selected series. Before the playoffs
        kick off, Round 1 shows as a projection from the standings.
        """
        canvas = getattr(self, 'canvas', None)
        if canvas is None:
            return
        try:
            canvas.delete("all")
        except Exception:
            return
        try:
            canvas.configure(bg=self.BRACKET_NAVY)
        except Exception:
            pass

        bracket, projected = self._tree_bracket()
        self._tree_bracket_obj = bracket
        self._tree_projected = projected
        self._set_projection_banner(projected, bracket)
        if bracket is None:
            try:
                canvas.create_text(
                    self.BRACKET_PAD + 16, self.BRACKET_PAD + 16, anchor="nw",
                    text="No league data yet — start a season to see playoff projections.",
                    fill="#9E9E9C",
                    font=_cfont(self.app.FONT_FAMILY, 12, ""))
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass
            return

        # --- series per column ---
        col_series = []
        for rkey, conf in self.BRACKET_COLUMNS:
            ss = list((getattr(bracket, 'playoff_series', None) or {}).get(rkey) or [])
            if conf is not None:
                ss = [s for s in ss if self._series_conference(s) == conf]
            if rkey == "wild_card":
                try:
                    ss.sort(key=self._r1_sort_key)
                except Exception:
                    pass
            col_series.append(ss)
        if not any(col_series):
            return

        # --- create the series cards (provisional positions) ---
        cards = {}  # id(series) -> dict(wid, widget, x, y, series, round, ci, conf)
        for ci, ss in enumerate(col_series):
            rkey, conf = self.BRACKET_COLUMNS[ci]
            mirror = (conf == "Eastern")
            x = self.BRACKET_PAD + ci * (self.BRACKET_CARD_W + self.BRACKET_GAP_X)
            for s in ss:
                try:
                    card = self._series_card(s, projected=projected,
                                             mirror=mirror)
                except Exception:
                    continue
                try:
                    wid = canvas.create_window(x, 0, window=card, anchor="nw")
                except Exception:
                    continue
                cards[id(s)] = {"wid": wid, "widget": card, "x": x, "y": 0,
                                "series": s, "round": rkey, "ci": ci,
                                "conf": conf}
        if not cards:
            return
        try:
            canvas.update_idletasks()
        except Exception:
            pass
        heights = {}
        for key, c in cards.items():
            try:
                heights[key] = max(80, int(c["widget"].winfo_reqheight()))
            except Exception:
                heights[key] = 150

        # --- series linkage: which next-round series each series feeds ---
        targets = {}  # id(series) -> id(target series)
        for key, c in cards.items():
            _nxt, tgt = series_target(bracket, c["series"])
            if tgt is not None and id(tgt) in cards:
                targets[key] = id(tgt)
        feeders_of = {}
        for key, tkey in targets.items():
            feeders_of.setdefault(tkey, []).append(key)

        # --- vertical layout: both Round 1 columns stack; every other
        # --- column centers on its feeders (feeders always placed first
        # --- thanks to BRACKET_LAYOUT_ORDER) ---
        y0 = self.BRACKET_PAD + 10
        for ci in self.BRACKET_LAYOUT_ORDER:
            keys = [id(s) for s in col_series[ci] if id(s) in cards]
            if ci in (0, 6):
                y = y0
                for k in keys:
                    cards[k]["y"] = y
                    y += heights[k] + self.BRACKET_GAP_Y
                continue

            def _feed_y(k):
                fl = [f for f in feeders_of.get(k, []) if f in cards]
                if not fl:
                    return 1e9
                return (sum(cards[f]["y"] + heights[f] / 2 for f in fl)
                        / len(fl))
            try:
                keys.sort(key=_feed_y)
            except Exception:
                pass
            y = y0
            for k in keys:
                fl = [f for f in feeders_of.get(k, []) if f in cards]
                if fl:
                    cy = (sum(cards[f]["y"] + heights[f] / 2 for f in fl)
                          / len(fl))
                    yy = max(cy - heights[k] / 2, y)
                else:
                    yy = y
                cards[k]["y"] = yy
                y = yy + heights[k] + self.BRACKET_GAP_Y

        # --- place cards ---
        for k, c in cards.items():
            try:
                canvas.coords(c["wid"], c["x"], c["y"])
            except Exception:
                pass

        # --- white elbow connectors (West flows left->right, East right->left) ---
        for k, tkey in targets.items():
            if tkey not in cards:
                continue
            c, t = cards[k], cards[tkey]
            try:
                if c["ci"] < t["ci"]:
                    x1 = c["x"] + self.BRACKET_CARD_W
                    x2 = t["x"]
                else:
                    x1 = c["x"]
                    x2 = t["x"] + self.BRACKET_CARD_W
                y1 = c["y"] + heights[k] / 2
                y2 = t["y"] + heights[tkey] / 2
                mx = (x1 + x2) / 2
                canvas.create_line(x1, y1, mx, y1, mx, y2, x2, y2,
                                   fill="#DCE3EB", width=2, smooth=False)
            except Exception:
                pass

        # --- Stanley Cup emblem above the Final ---
        try:
            fam = self.app.FONT_FAMILY
            for k, c in cards.items():
                if c["round"] != "stanley_cup_final":
                    continue
                ex = c["x"] + self.BRACKET_CARD_W / 2
                ey = max(c["y"] - 8, 96)
                canvas.create_text(ex, ey - 44, text="\U0001F3C6",
                                   font=_cfont(fam, 30, ""), anchor="s")
                canvas.create_text(ex, ey - 40, text="STANLEY CUP",
                                   fill="#C9A227",
                                   font=_cfont(fam, 13, "bold"), anchor="n")
                canvas.create_text(ex, ey - 20, text="PLAYOFFS",
                                   fill="#F2F2F2",
                                   font=_cfont(fam, 11, ""), anchor="n")
                break
        except Exception:
            pass

        # --- champion marker under the Final card ---
        try:
            champ = getattr(bracket, 'stanley_cup_champion', None)
            if champ is not None and not projected:
                for k, c in cards.items():
                    if c["round"] == "stanley_cup_final":
                        canvas.create_text(
                            c["x"] + self.BRACKET_CARD_W / 2,
                            c["y"] + heights[k] + 16, anchor="n",
                            text=f"\U0001F3C6 {champ.team_name} — Stanley Cup Champions",
                            fill="#C9A227",
                            font=_cfont(self.app.FONT_FAMILY, 12, "bold"))
                        break
        except Exception:
            pass

        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

        # --- ticker defaults to the top West Round 1 series ---
        try:
            first = (col_series[0] or [None])[0]
            if first is None:
                for ss in col_series:
                    if ss:
                        first = ss[0]
                        break
            if first is not None:
                self._update_ticker(first, projected)
        except Exception:
            pass

    def _update_ticker(self, series, projected=False):
        """2K-style bottom ticker readout for the selected series."""
        lbl = getattr(self, 'ticker_label', None)
        if lbl is None or series is None:
            return
        try:
            bracket = getattr(self, '_tree_bracket_obj', None)
            rkey = None
            if bracket is not None:
                for r in PlayoffBracket.ROUND_ORDER:
                    try:
                        if any(s is series
                               for s in (bracket.playoff_series.get(r) or [])):
                            rkey = r
                            break
                    except Exception:
                        continue
            rname = ROUND_DISPLAY_NAMES.get(rkey, "Playoffs").upper()
            t1n = getattr(getattr(series, 'team1', None), 'team_name', '')
            t2n = getattr(getattr(series, 'team2', None), 'team_name', '')
            status, _dec = series_status_text(series)
            prefix = "\U0001F52E PROJECTION \u2014 " if projected else ""
            lbl.configure(
                text=f"{prefix}{rname}: {t1n} vs {t2n} \u2014 {status}")
        except Exception:
            pass

    def _series_card(self, series, projected=False, mirror=False):
        """One 2K-style series card: two team-colored rows, the series-wins
        badge at the outer edge (left for West, right for East). Higher
        seed on top. Click opens the series detail."""
        try:
            import team_identity_system as _tid
        except Exception:
            _tid = None
        t1, t2 = series.team1, series.team2
        w1 = int(getattr(series, 'team1_wins', 0) or 0)
        w2 = int(getattr(series, 'team2_wins', 0) or 0)
        decided = bool(getattr(series, 'is_complete', False))
        winner_name = getattr(getattr(series, 'winner', None), 'team_name', None)
        gold = "#C9A227"

        def _seed(t):
            try:
                return int(getattr(t, 'standings_position', 99) or 99)
            except Exception:
                return 99

        order = [(t1, w1), (t2, w2)]
        try:
            order.sort(key=lambda tw: _seed(tw[0]))
        except Exception:
            pass

        try:
            card = ctk.CTkFrame(self.canvas, width=self.BRACKET_CARD_W,
                                corner_radius=8,
                                border_width=2 if decided else 1,
                                border_color=gold if decided else "#2A3A52",
                                fg_color="#0E1930")
        except Exception:
            card = ctk.CTkFrame(self.canvas, width=self.BRACKET_CARD_W)
        try:
            card.pack_propagate(False)
        except Exception:
            pass

        for idx, (team, wins) in enumerate(order):
            tname = getattr(team, 'team_name', '')
            is_winner = decided and winner_name == tname
            is_loser = decided and not is_winner
            accent, hover, on_accent = "#1B3A5C", "#14293F", "#F2F2F2"
            if _tid is not None:
                try:
                    accent, hover, on_accent = _tid.accent_for_team(tname)
                except Exception:
                    pass
            row_bg = hover if is_loser else accent
            try:
                row = ctk.CTkFrame(card, fg_color=row_bg, corner_radius=6,
                                   height=40)
            except Exception:
                row = ctk.CTkFrame(card, height=40)
            pad_bottom = 6 if idx == len(order) - 1 else 0
            try:
                row.pack(fill="x", padx=6, pady=(6, pad_bottom))
            except Exception:
                row.pack(fill="x")
            try:
                row.pack_propagate(False)
            except Exception:
                pass
            seed = getattr(team, 'standings_position', '')
            seed_txt = f"({seed}) " if seed else ""
            abbr = team_abbr(tname)
            try:
                wins_lbl = ctk.CTkLabel(
                    row, text=str(wins), anchor="center",
                    font=_cfont(self.app.FONT_FAMILY, 22, "bold"),
                    text_color=gold if is_winner else on_accent)
                name_lbl = ctk.CTkLabel(
                    row, text=f"{seed_txt}{abbr}", anchor="w",
                    font=_cfont(self.app.FONT_FAMILY, 15, "bold"),
                    text_color=gold if is_winner else on_accent)
            except Exception:
                continue
            try:
                if not mirror:
                    # West: wins badge at the left (outer) edge.
                    wins_lbl.pack(side="left", padx=(8, 2))
                    name_lbl.pack(side="left", padx=(4, 0))
                else:
                    # East: wins badge at the right (outer) edge.
                    wins_lbl.pack(side="right", padx=(2, 8))
                    name_lbl.pack(side="left", padx=(10, 0))
            except Exception:
                pass

        try:
            card.configure(cursor="hand2")
        except Exception:
            pass
        self._bind_card_click(card, series, projected)
        return card

    def _bind_card_click(self, widget, series, projected):
        try:
            widget.bind("<Button-1>",
                        lambda e: self._open_series_detail(series, projected))
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._bind_card_click(child, series, projected)
        except Exception:
            pass

    def _open_series_detail(self, series, projected=False):
        """Click a bracket series -> its storylines panel."""
        self._update_ticker(series, projected)
        try:
            bracket = (self.playoff_bracket if not projected
                       else self._build_projection_bracket())
            SeriesDetailPopup(self, self.app, series, bracket=bracket,
                              projected=projected)
        except Exception:
            pass


def series_target(bracket, series):
    """Next-round series this series feeds into, by team identity.

    Returns (next_round_key, target_series_or_None). Winner-matched first
    (most accurate once decided), then either combatant for live series.
    """
    try:
        rounds = [r for r in PlayoffBracket.ROUND_ORDER
                  if bracket.playoff_series.get(r)]
        ri = next(i for i, r in enumerate(rounds)
                  if any(s is series for s in bracket.playoff_series[r]))
    except StopIteration:
        return None, None
    except Exception:
        return None, None
    if ri + 1 >= len(rounds):
        return None, None
    nxt = rounds[ri + 1]
    names = {getattr(series.team1, 'team_name', ''),
             getattr(series.team2, 'team_name', '')}
    winner_name = getattr(getattr(series, 'winner', None), 'team_name', None)
    cands = bracket.playoff_series[nxt]
    if winner_name:
        for cand in cands:
            if winner_name in (getattr(cand.team1, 'team_name', ''),
                               getattr(cand.team2, 'team_name', '')):
                return nxt, cand
    for cand in cands:
        if names & {getattr(cand.team1, 'team_name', ''),
                    getattr(cand.team2, 'team_name', '')}:
            return nxt, cand
    return nxt, None


def _sibling_series(bracket, series):
    """Another series in the same round feeding the same next-round slot."""
    try:
        _nxt, my_target = series_target(bracket, series)
        if my_target is None:
            return None
        rounds = [r for r in PlayoffBracket.ROUND_ORDER
                  if bracket.playoff_series.get(r)]
        for r in rounds:
            for cand in bracket.playoff_series[r]:
                if cand is series:
                    continue
                _n2, t = series_target(bracket, cand)
                if t is my_target:
                    return cand
    except Exception:
        pass
    return None


def _top_playoff_scorers(team, n=3):
    rows = []
    for p in getattr(team, 'roster', None) or []:
        d = getattr(p, 'playoff_stats', None) or {}
        try:
            pts = int(d.get('points', 0) or 0)
        except Exception:
            pts = 0
        if pts > 0:
            name = getattr(p, 'full_name', None) or getattr(p, 'name', 'Unknown')
            try:
                g = int(d.get('goals', 0) or 0)
                a = int(d.get('assists', 0) or 0)
            except Exception:
                g, a = 0, 0
            rows.append((pts, name, g, a))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return rows[:n]


def _series_storylines(series):
    """Narrative bullets for a series: streaks, elimination, comebacks."""
    lines = []
    try:
        a1 = team_abbr(getattr(series.team1, 'team_name', ''))
        a2 = team_abbr(getattr(series.team2, 'team_name', ''))
        w1 = int(getattr(series, 'team1_wins', 0) or 0)
        w2 = int(getattr(series, 'team2_wins', 0) or 0)
        games = list(getattr(series, 'game_results', None) or [])
        # -- Bad blood (additive): an injury-causing hit or controversial
        # incident between these clubs drives the series before a puck
        # drops, so it leads the storylines even for projected matchups.
        try:
            from narrative_ledger import active_ledger as _al
            _led = _al()
            if _led is not None:
                _n1 = getattr(series.team1, 'team_name', '')
                _n2 = getattr(series.team2, 'team_name', '')
                _seen = 0
                for _ev in _led.between(_n1, _n2, kinds=["incident"]):
                    _facts = _ev.get("facts") or {}
                    if _facts.get("incident_kind") not in (
                            "star_injured", "player_injured",
                            "controversial_hit"):
                        continue
                    _detail = (_ev.get("text") or _facts.get("detail")
                               or "").strip()
                    if _detail:
                        lines.append(f"\U0001FA78 Bad blood: {_detail} "
                                     f"\u2014 expect this series to have an edge.")
                    else:
                        lines.append("\U0001FA78 Bad blood between these clubs "
                                     "\u2014 expect this series to have an edge.")
                    _seen += 1
                    if _seen >= 2:
                        break
        except Exception:
            pass
        if not games:
            if lines:
                lines.append("First game of the series is still to come.")
                return lines
            return ["First game of the series is still to come."]
        last_t1 = bool(games[-1].get('team1_won'))
        streak = 0
        for g in reversed(games):
            if bool(g.get('team1_won')) == last_t1:
                streak += 1
            else:
                break
        who = a1 if last_t1 else a2
        if streak >= 2:
            lines.append(f"{who} has won {streak} straight in this series.")
        if not getattr(series, 'is_complete', False):
            ng = int(getattr(series, 'games_played', 0) or 0) + 1
            if w1 == 3 and w2 < 3:
                lines.append(f"{a2} faces elimination in Game {ng}.")
            if w2 == 3 and w1 < 3:
                lines.append(f"{a1} faces elimination in Game {ng}.")
            if w1 == 3 and w2 == 0:
                lines.append(f"{a1} is one win from the sweep.")
            if w2 == 3 and w1 == 0:
                lines.append(f"{a2} is one win from the sweep.")
            if int(getattr(series, 'games_played', 0) or 0) == 6:
                lines.append("Game 7 will decide it — winner takes all.")
        else:
            wname = team_abbr(
                getattr(getattr(series, 'winner', None), 'team_name', ''))
            if min(w1, w2) == 0 and wname:
                lines.append(f"{wname} completed the sweep.")
            elif streak >= 3 and wname:
                lines.append(f"{wname} closed it out with {streak} straight wins.")
        seq = [bool(g.get('team1_won')) for g in games]
        for t1flag, abbr_ in ((True, a1), (False, a2)):
            down0 = 0
            for won_t1 in seq:
                if won_t1 != t1flag:
                    down0 += 1
                else:
                    break
            if down0 >= 2 and not getattr(series, 'is_complete', False):
                cur_w = w1 if t1flag else w2
                cur_l = w2 if t1flag else w1
                if cur_w >= cur_l:
                    lines.append(
                        f"{abbr_} has clawed all the way back from {down0}-0 down.")
                else:
                    lines.append(f"{abbr_} is battling back from {down0}-0 down.")
        ot = sum(1 for g in games if g.get('ot'))
        if ot:
            lines.append(
                f"{ot} overtime game{'s' if ot > 1 else ''} so far — tight series.")
    except Exception:
        pass
    return lines


def build_series_detail_content(parent, app, series, bracket=None,
                                projected=False):
    """Fill `parent` with the clicked series' storylines panel."""
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg, dim = "#C9A227", "#DCE3EB", "#8A94A0"
    t1, t2 = series.team1, series.team2
    a1 = team_abbr(getattr(t1, 'team_name', ''))
    a2 = team_abbr(getattr(t2, 'team_name', ''))
    s1 = getattr(t1, 'standings_position', '')
    s2 = getattr(t2, 'standings_position', '')
    ctk.CTkLabel(parent, text=f"{a1} ({s1})  vs  {a2} ({s2})",
                 font=_cfont(fam, 18, "bold"),
                 text_color=fg).pack(pady=(4, 0))
    status, _dec = series_status_text(series)
    ctk.CTkLabel(parent, text=status if status else "Not started",
                 font=_cfont(fam, 13, "italic"),
                 text_color=gold).pack(pady=(0, 8))

    if projected:
        _detail_tale_of_tape(parent, app, series)
    else:
        _detail_games(parent, app, series)
        _detail_splits(parent, app, series)
        ctk.CTkLabel(parent, text="Storylines",
                     font=_cfont(fam, 13, "bold"),
                     text_color=gold).pack(anchor="w", pady=(8, 2))
        for ln in _series_storylines(series):
            ctk.CTkLabel(parent, text="•  " + ln, font=_cfont(fam, 12, ""),
                         text_color=fg, anchor="w", wraplength=480,
                         justify="left").pack(fill="x", padx=4, pady=1)
        ctk.CTkLabel(parent, text="Players to watch (playoff scoring to date)",
                     font=_cfont(fam, 13, "bold"),
                     text_color=gold).pack(anchor="w", pady=(8, 2))
        any_rows = False
        for team in (t1, t2):
            for pts, name, g, a_ in _top_playoff_scorers(team):
                any_rows = True
                ctk.CTkLabel(
                    parent,
                    text=f"{team_abbr(getattr(team, 'team_name', ''))}  {name} — "
                         f"{pts} pts ({g}G, {a_}A)",
                    font=_cfont(fam, 12, ""), text_color=fg,
                    anchor="w").pack(fill="x", padx=4)
        if not any_rows:
            ctk.CTkLabel(parent, text="No playoff scoring yet.",
                         font=_cfont(fam, 12, "italic"),
                         text_color=dim).pack(anchor="w", padx=4)
    _detail_road_ahead(parent, app, series, bracket, projected)


def _detail_tale_of_tape(parent, app, series):
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg, dim = "#C9A227", "#DCE3EB", "#8A94A0"
    ctk.CTkLabel(parent, text="Tale of the tape (regular season)",
                 font=_cfont(fam, 13, "bold"),
                 text_color=gold).pack(anchor="w", pady=(6, 2))
    standings = getattr(getattr(app, 'league', None), 'standings', {}) or {}
    for team in (series.team1, series.team2):
        st = standings.get(getattr(team, 'team_name', ''), {}) or {}
        pts = st.get('Points', st.get('PTS', '?'))
        w = st.get('W', st.get('Wins', '?'))
        l = st.get('L', st.get('Losses', '?'))
        otl = st.get('OTL', st.get('OT', '?'))
        gf = getattr(team, 'goals_for', '?')
        ga = getattr(team, 'goals_against', '?')
        ctk.CTkLabel(
            parent,
            text=f"{team_abbr(getattr(team, 'team_name', ''))} "
                 f"({getattr(team, 'standings_position', '')}): "
                 f"{w}-{l}-{otl}, {pts} pts   •   {gf} GF / {ga} GA",
            font=_cfont(fam, 12, ""), text_color=fg,
            anchor="w").pack(fill="x", padx=4)
    ctk.CTkLabel(parent,
                 text="Projection only — the real series starts at 0-0.",
                 font=_cfont(fam, 11, "italic"),
                 text_color=dim).pack(anchor="w", pady=(6, 0))


def _detail_games(parent, app, series):
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg, dim = "#C9A227", "#DCE3EB", "#8A94A0"
    ctk.CTkLabel(parent, text="Game by game",
                 font=_cfont(fam, 13, "bold"),
                 text_color=gold).pack(anchor="w", pady=(6, 2))
    games = list(getattr(series, 'game_results', None) or [])
    if not games:
        ctk.CTkLabel(parent, text="No games played yet.",
                     font=_cfont(fam, 12, "italic"),
                     text_color=dim).pack(anchor="w", padx=4)
        return
    a1 = team_abbr(getattr(series.team1, 'team_name', ''))
    a2 = team_abbr(getattr(series.team2, 'team_name', ''))
    for g in games:
        try:
            s1, s2 = g.get('t1_score', 0), g.get('t2_score', 0)
            if g.get('team1_won'):
                core = f"{a1} {s1} – {s2} {a2}"
            else:
                core = f"{a2} {s2} – {s1} {a1}"
            extra = "  •  OT" if g.get('ot') else ""
            ctk.CTkLabel(parent,
                         text=f"Game {g.get('game', '?')}:  {core}{extra}",
                         font=_cfont(fam, 12, ""), text_color=fg,
                         anchor="w").pack(fill="x", padx=4)
            gs = g.get('goalie_steal')
            if gs:
                ctk.CTkLabel(parent, text=f"      🧱 {gs} stood on his head",
                             font=_cfont(fam, 11, "italic"),
                             text_color=dim, anchor="w").pack(fill="x", padx=4)
        except Exception:
            continue


def _detail_splits(parent, app, series):
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg = "#C9A227", "#DCE3EB"
    ctk.CTkLabel(parent, text="Series splits",
                 font=_cfont(fam, 13, "bold"),
                 text_color=gold).pack(anchor="w", pady=(8, 2))
    games = list(getattr(series, 'game_results', None) or [])
    hdr = f"{'Team':<5}{'W':>3}{'L':>3}{'GF':>4}{'GA':>4}{'GF/G':>6}{'BigW':>5}{'OT':>6}"
    ctk.CTkLabel(parent, text=hdr, font=("Courier", 11, "bold"),
                 text_color=gold, anchor="w").pack(fill="x", padx=4)
    for idx, team in ((0, series.team1), (1, series.team2)):
        w = int(getattr(series, 'team1_wins', 0) or 0) if idx == 0 else int(
            getattr(series, 'team2_wins', 0) or 0)
        l = int(getattr(series, 'team2_wins', 0) or 0) if idx == 0 else int(
            getattr(series, 'team1_wins', 0) or 0)
        gf, ga, otw, otl, big = 0, 0, 0, 0, 0
        for g in games:
            try:
                s1, s2 = int(g.get('t1_score', 0)), int(g.get('t2_score', 0))
            except Exception:
                s1, s2 = 0, 0
            mine, theirs = (s1, s2) if idx == 0 else (s2, s1)
            gf += mine
            ga += theirs
            big = max(big, mine - theirs)
            if g.get('ot'):
                if mine > theirs:
                    otw += 1
                else:
                    otl += 1
        gp = len(games)
        gpg = gf / gp if gp else 0.0
        txt = (f"{team_abbr(getattr(team, 'team_name', '')):<5}{w:>3}{l:>3}"
               f"{gf:>4}{ga:>4}{gpg:>6.2f}{('+' + str(big)):>5}"
               f"{f'{otw}-{otl}':>6}")
        ctk.CTkLabel(parent, text=txt, font=("Courier", 11, "normal"),
                     text_color=fg, anchor="w").pack(fill="x", padx=4)


def _detail_road_ahead(parent, app, series, bracket, projected):
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg = "#C9A227", "#DCE3EB"
    ctk.CTkLabel(parent, text="Road ahead",
                 font=_cfont(fam, 13, "bold"),
                 text_color=gold).pack(anchor="w", pady=(8, 2))
    lines = []
    if projected or bracket is None:
        lines.append("Win this round and the bracket opens up — "
                     "later matchups depend on who survives.")
    else:
        try:
            nxt, target = series_target(bracket, series)
            me_done = bool(getattr(series, 'is_complete', False))
            if me_done:
                adv = team_abbr(
                    getattr(getattr(series, 'winner', None), 'team_name', ''))
            else:
                adv = "The winner"
            if nxt and target is not None:
                rn = ROUND_DISPLAY_NAMES.get(nxt, nxt)
                ta = team_abbr(getattr(target.team1, 'team_name', ''))
                tb = team_abbr(getattr(target.team2, 'team_name', ''))
                st, _d = series_status_text(target)
                lines.append(f"{adv} advances to the {rn}: {ta} vs {tb} "
                             f"({st if st else 'not started'}).")
            elif nxt:
                rn = ROUND_DISPLAY_NAMES.get(nxt, nxt)
                lines.append(f"{adv} advances to the {rn} — "
                             f"opponent still to be decided.")
            sib = _sibling_series(bracket, series)
            if sib is not None:
                sa = team_abbr(getattr(sib.team1, 'team_name', ''))
                sb = team_abbr(getattr(sib.team2, 'team_name', ''))
                sst, _d = series_status_text(sib)
                lines.append(f"Other half of the bracket: {sa} vs {sb} "
                             f"({sst if sst else 'not started'}).")
        except Exception:
            pass
    if not lines:
        lines.append("Nothing scheduled beyond this series.")
    for ln in lines:
        ctk.CTkLabel(parent, text="•  " + ln, font=_cfont(fam, 12, ""),
                     text_color=fg, anchor="w", wraplength=480,
                     justify="left").pack(fill="x", padx=4, pady=1)

class SeriesDetailPopup(InGamePopup):
    """Clickable-bracket series detail: games, splits, storylines, road ahead."""

    def __init__(self, master, app, series, bracket=None, projected=False):
        try:
            super().__init__(master)
        except Exception:
            return
        try:
            self.title("Series Details")
        except Exception:
            pass
        try:
            body = ctk.CTkScrollableFrame(self, fg_color="transparent")
            body.pack(fill="both", expand=True, padx=12, pady=12)
            build_series_detail_content(body, app, series, bracket=bracket,
                                        projected=projected)
        except Exception:
            pass
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
