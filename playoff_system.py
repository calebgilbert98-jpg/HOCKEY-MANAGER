# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from game_classes import Team


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
    # Dynamic scheduling: every series lives on the calendar. start_date is
    # set when the round is created; game_dates holds up to 7 potential
    # dates (2 days apart, NHL rhythm); end_date stamps the clincher.
    # series_id tags the league.schedule entries so unplayed games can be
    # pruned when a series ends early. bracket_side ('EA'..'WD') pins the
    # fixed-bracket slot for round-2 pairing.
    start_date: Optional[date] = None
    game_dates: List[date] = field(default_factory=list)
    end_date: Optional[date] = None
    series_id: str = ""
    bracket_side: str = ""
    # Hype: computed when the series is scheduled. rivalry_heat (0-100)
    # comes from the league rivalry store; hype_tags are short story
    # labels ("Bad blood", "Playoff rematch", "Upset watch"); marquee
    # flags the calendar entries fans circle. Additive.
    rivalry_heat: float = 0.0
    hype_tags: List[str] = field(default_factory=list)
    marquee: bool = False

    # 2-2-1-1-1: team1 (higher seed) hosts games 1, 2, 5, 7.
    HOME_GAMES = frozenset({1, 2, 5, 7})

    def home_team_for_game(self, game_number: int):
        """Venue for game N of the series (1-indexed)."""
        return self.team1 if game_number in self.HOME_GAMES else self.team2

    def away_team_for_game(self, game_number: int):
        return self.team2 if game_number in self.HOME_GAMES else self.team1

    def next_game_date(self):
        """Calendar date for the next unplayed game, if scheduled."""
        try:
            return self.game_dates[self.games_played]
        except (IndexError, TypeError):
            return None
    
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
        if self.is_complete and self.end_date is None:
            # Stamp the clincher's date from the scheduled game dates.
            try:
                self.end_date = self.game_dates[self.games_played - 1]
            except (IndexError, TypeError):
                self.end_date = None


def _game7_ot_hero(pgr: Dict, team1: Any, team2: Any
                  ) -> Optional[Tuple[Any, str, str]]:
    """Resolve a Game-7 OT winner to (player, name, team_name).

    Prefers the actual OT scorer (the period-4 goal in notable_events);
    falls back to the 1st star (the OT-winner bonus usually puts him
    there). Returns None when nobody resolves. Additive helper for the
    clutch story line in PlayoffBracket.simulate_playoff_game."""
    pid = None
    try:
        from stars import _ot_scorer_id as _otid
        pid = _otid(pgr or {})
    except Exception:
        pid = None
    if pid is None:
        try:
            _stars = (pgr or {}).get("three_stars") or []
            if _stars:
                pid = (_stars[0] or {}).get("player_id")
        except Exception:
            pid = None
    if pid is None:
        return None
    for t in (team1, team2):
        for p in getattr(t, "roster", None) or []:
            try:
                if getattr(p, "id", None) == pid:
                    nm = getattr(p, "full_name", None) or (
                        f"{getattr(p, 'first_name', '')} "
                        f"{getattr(p, 'last_name', '')}").strip()
                    return p, (nm or "A playoff hero"), str(
                        getattr(t, "team_name", "") or "")
            except Exception:
                continue
    return None


class PlayoffBracket:
    """Manages the entire NHL playoff bracket"""

    # Dynamic playoff scheduling: games every other day (NHL rhythm),
    # and each round starts REST_DAYS after the LAST completed series of
    # the previous round — never on a fixed date, never before every
    # series is decided.
    PLAYOFF_GAME_SPACING = 2
    PLAYOFF_REST_DAYS = 2

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

    # ------------------------------------------------------------------
    # Dynamic playoff scheduling.
    #
    # Every series lives on the calendar: game dates are set when its
    # round is created, and the next round starts PLAYOFF_REST_DAYS after
    # the LAST completed series of the previous round. Playoff games are
    # published to league.schedule (tagged playoff=True) so team
    # schedules and the calendar show them; unplayed games are pruned
    # when a series ends early. The daily sim skips playoff entries —
    # they are simmed through the bracket, never twice.
    # ------------------------------------------------------------------

    def _next_series_id(self):
        n = getattr(self, '_series_seq', 0) + 1
        self._series_seq = n
        return f"PO-{getattr(getattr(self, 'league', None), 'season_year', '?')}-{n:02d}"

    def _schedule_series(self, series, start_date):
        """Assign calendar dates to a series (up to 7, every other day)."""
        try:
            series.series_id = series.series_id or self._next_series_id()
            series.start_date = start_date
            series.game_dates = [
                start_date + timedelta(days=i * self.PLAYOFF_GAME_SPACING)
                for i in range(int(getattr(series, 'series_format', 7) or 7))
            ]
        except Exception:
            pass

    def _publish_series_to_schedule(self, series):
        """Append a series' potential games to league.schedule."""
        try:
            sched = getattr(getattr(self, 'league', None), 'schedule', None)
            if sched is None or not getattr(series, 'game_dates', None):
                return
            # Drop any stale entries for this series first (idempotent).
            self._prune_series_schedule(series, prune_all=True)
            for i, d in enumerate(series.game_dates, start=1):
                sched.append({
                    'date': d,
                    'home_team': series.home_team_for_game(i),
                    'away_team': series.away_team_for_game(i),
                    'playoff': True,
                    'event_type': 'PLAYOFF',
                    'series_id': series.series_id,
                    'series_game': i,
                    'round_name': getattr(series, 'round_name', ''),
                    'round_key': getattr(series, '_round_key', ''),
                    # Hype: calendar views mark marquee games; the tags
                    # ("Bad blood", "Playoff rematch") are the story.
                    'marquee': bool(getattr(series, 'marquee', False)),
                    'hype_tags': list(getattr(series, 'hype_tags', None)
                                      or []),
                })
            # Keep date order: the daily sim early-breaks past today.
            try:
                sched.sort(key=lambda x: x['date']
                           if isinstance(x, dict) and 'date' in x else x[0])
            except Exception:
                pass
        except Exception:
            pass

    def _prune_series_schedule(self, series, prune_all=False):
        """Remove unplayed games of a series from league.schedule.

        Called when a series ends early (games beyond the clincher vanish)
        and before re-publishing (idempotency).
        """
        try:
            sched = getattr(getattr(self, 'league', None), 'schedule', None)
            if sched is None or not getattr(series, 'series_id', ''):
                return
            played = 0 if prune_all else int(
                getattr(series, 'games_played', 0) or 0)
            sched[:] = [e for e in sched
                        if not (isinstance(e, dict)
                                and e.get('series_id') == series.series_id
                                and e.get('series_game', 0) > played)]
        except Exception:
            pass

    def _stamp_played_game(self, series, home_score, away_score):
        """Record the score on the scheduled entry for a simmed game."""
        try:
            sched = getattr(getattr(self, 'league', None), 'schedule', None)
            if sched is None:
                return
            for e in sched:
                if (isinstance(e, dict)
                        and e.get('series_id') == getattr(
                            series, 'series_id', '')
                        and e.get('series_game') == int(
                            getattr(series, 'games_played', 0) or 0)):
                    e['home_score'] = home_score
                    e['away_score'] = away_score
                    e['played'] = True
                    break
        except Exception:
            pass

    def _last_regular_season_date(self):
        """Latest regular-season game date on the league schedule."""
        try:
            sched = getattr(getattr(self, 'league', None), 'schedule', None)
            dates = [e['date'] for e in sched or []
                     if isinstance(e, dict) and e.get('date') is not None
                     and not e.get('playoff') and not e.get('preseason')]
            return max(dates) if dates else None
        except Exception:
            return None

    def build_projection(self):
        """Build a projected Round 1 from the current standings.

        Used by the bracket tree before the playoffs kick off: shows the
        matchups as they would be if the season ended today. Later rounds
        are genuinely unknown, so only the wild-card round is projected.
        Projections never touch the calendar (schedule_games=False).
        """
        eastern, western = self._get_playoff_qualified_teams()
        self.eastern_teams = eastern
        self.western_teams = western
        self._assign_conference_seeds()
        for key in self.playoff_series:
            self.playoff_series[key] = []
        self._create_wild_card_round(schedule_games=False)
        self.is_projection = True
        self.current_round = 'wild_card'
        return self

    def _assign_conference_seeds(self):
        """standings_position = conference rank by points (display only)."""
        for conf_teams in (self.eastern_teams, self.western_teams):
            ranked = sorted(conf_teams, key=self._standings_sort_key)
            for i, team in enumerate(ranked):
                try:
                    team.standings_position = i + 1
                except Exception:
                    pass

    def generate_playoff_bracket(self):
        """Generate the complete playoff bracket based on standings.

        Format comes from the setup-time choice on the league:
        'divisional' (current NHL: top 3 per division + 2 wild cards,
        fixed bracket) or 'conference' (classic: top 8 per conference
        by points, 1v8/2v7/3v6/4v5, reseeded each round). Round 1 is
        scheduled onto the calendar starting shortly after the last
        regular-season game.
        """
        eastern, western = self._get_playoff_qualified_teams()
        self.eastern_teams = eastern
        self.western_teams = western
        self._assign_conference_seeds()

        # Round 1 starts after the regular season breathes: 2 days after
        # the last scheduled regular-season game (never a fixed date).
        start = self._last_regular_season_date()
        if start is not None:
            start = start + timedelta(days=self.PLAYOFF_REST_DAYS)
        else:
            try:
                start = date(getattr(self.league, 'season_year', 2026) + 1,
                             4, 16)
            except Exception:
                start = None

        # Generate first round matchups, on the calendar.
        self._create_wild_card_round(schedule_games=True,
                                     start_date=start)
        # Hype: one "circle the dates" story for the round's marquee
        # series (silent without an app, e.g. projections).
        try:
            self._announce_round_hype('wild_card')
        except Exception:
            pass

    def _standings_sort_key(self, team):
        """Points, then wins, then goal differential (best-first)."""
        standings = getattr(self.league, 'standings', None) or {}
        st = standings.get(getattr(team, 'team_name', ''), None) or {}
        points = st.get('Points', 0)
        wins = st.get('W', st.get('Wins', 0))
        try:
            goal_diff = (getattr(team, 'goals_for', 0) or 0) - \
                (getattr(team, 'goals_against', 0) or 0)
        except Exception:
            goal_diff = 0
        return (-points, -wins, -goal_diff)

    def _conference_of(self, team):
        """Conference for qualification; division-mapped fallback."""
        conf = getattr(team, 'conference', '') or ''
        if conf in ('Eastern', 'Western'):
            return conf
        div = getattr(team, 'division', '') or ''
        if div in ('Atlantic', 'Metropolitan'):
            return 'Eastern'
        if div in ('Central', 'Pacific'):
            return 'Western'
        return 'Eastern'

    def _playoff_format(self):
        """'divisional' (current NHL) or 'conference' (classic 1v8).

        Setup-only choice stored on the league; old saves default to
        divisional. One reader so every bracket path agrees.
        """
        try:
            pf = getattr(getattr(self, 'league', None), 'playoff_format',
                         'divisional')
            return pf if pf in ('divisional', 'conference') else 'divisional'
        except Exception:
            return 'divisional'

    def _conference_qualified_teams(self):
        """Classic format: top 8 per conference by points, best-first.

        No division auto-berths -- straight points ranking with no
        protected seeds for division winners.
        """
        standings = getattr(self.league, 'standings', None) or {}

        def sort_key(team):
            st = standings.get(getattr(team, 'team_name', ''), {}) or {}
            points = st.get('Points', 0)
            wins = st.get('W', st.get('Wins', 0))
            try:
                goal_diff = (getattr(team, 'goals_for', 0) or 0) - \
                    (getattr(team, 'goals_against', 0) or 0)
            except Exception:
                goal_diff = 0
            return (-points, -wins, -goal_diff)

        eastern, western = [], []
        for team in getattr(self.league, 'teams', None) or []:
            if getattr(team, 'league_name', '') != 'National Hockey League':
                continue
            if self._conference_of(team) == 'Eastern':
                eastern.append(team)
            else:
                western.append(team)
        return (sorted(eastern, key=sort_key)[:8],
                sorted(western, key=sort_key)[:8])

    def _get_playoff_qualified_teams(self):
        """Route qualification by the setup-time format choice.

        Divisional: NHL qualification, top 3 per division + 2 wild cards
        per conference (bracket order). Conference: classic top-8-by-points
        per conference (seed order).
        """
        if self._playoff_format() == 'conference':
            return self._conference_qualified_teams()
        """NHL qualification: top 3 per division + 2 wild cards per conference.

        Returns (eastern, western): 8 teams each in fixed-bracket order
        [DW1, DW2, D1#2, D1#3, D2#2, D2#3, WC1, WC2], where DW1 is the
        division winner with more points and D1 is DW1's division.
        Reads the league standings dict (source of truth for the season).
        """
        by_division = defaultdict(list)
        for team in getattr(self.league, 'teams', None) or []:
            if getattr(team, 'league_name', '') != 'National Hockey League':
                continue
            by_division[getattr(team, 'division', 'Unknown')
                        or 'Unknown'].append(team)

        conf_divs = {'Eastern': [], 'Western': []}
        conf_leftovers = {'Eastern': [], 'Western': []}
        for div_name in sorted(by_division.keys()):
            div_teams = sorted(by_division[div_name],
                               key=self._standings_sort_key)
            if not div_teams:
                continue
            conf = self._conference_of(div_teams[0])
            conf_divs[conf].append(div_teams[:3])
            conf_leftovers[conf].extend(div_teams[3:])

        eastern, western = [], []
        for conf, out in (('Eastern', eastern), ('Western', western)):
            divs = [d for d in conf_divs[conf][:2] if d]
            if len(divs) >= 2:
                # Division winners, best points first; D1 = DW1's division.
                w1, w2 = sorted(
                    [(d[0], d) for d in divs],
                    key=lambda wd: self._standings_sort_key(wd[0]))
                DW1, D1 = w1[0], w1[1]
                DW2, D2 = w2[0], w2[1]
                bracket = [DW1, DW2]
                bracket += [t for t in D1[1:3]]
                bracket += [t for t in D2[1:3]]
            elif len(divs) == 1:
                bracket = list(divs[0][:3])
            else:
                bracket = []
            wild = sorted(conf_leftovers[conf],
                          key=self._standings_sort_key)
            need = 8 - len(bracket)
            bracket += wild[:max(0, need)]
            # Defensive: never hand the bracket a short conference.
            if len(bracket) < 8:
                pool = sorted(
                    [t for t in
                     getattr(self.league, 'teams', None) or []
                     if getattr(t, 'league_name', '') ==
                     'National Hockey League'
                     and self._conference_of(t) == conf
                     and t not in bracket],
                    key=self._standings_sort_key)
                bracket += pool[:8 - len(bracket)]
            out.extend(bracket[:8])
        return eastern, western
    
    def _is_eastern_team(self, team: Team) -> bool:
        """Determine if team is in Eastern Conference"""
        eastern_divisions = ['Atlantic', 'Metropolitan']
        return hasattr(team, 'division') and team.division in eastern_divisions
    
    def _create_conference_first_round(self, schedule_games=True,
                                       start_date=None):
        """Classic round 1: 1v8, 2v7, 3v6, 4v5 per conference.

        In this format eastern_teams/western_teams are best-first seed
        order, so seeds are list positions. bracket_side pins the slot for
        the tree view; later rounds reseed, so sides are display-only here.
        """
        for conf_teams, conf_tag in ((self.eastern_teams, 'E'),
                                     (self.western_teams, 'W')):
            if len(conf_teams) < 8:
                continue
            pairs = [(conf_teams[0], conf_teams[7], 'A'),
                     (conf_teams[1], conf_teams[6], 'B'),
                     (conf_teams[2], conf_teams[5], 'C'),
                     (conf_teams[3], conf_teams[4], 'D')]
            for team1, team2, side in pairs:
                series = PlayoffSeries("Wild Card Round", team1, team2)
                series.bracket_side = conf_tag + side
                self.playoff_series['wild_card'].append(series)
                if schedule_games:
                    # Single choke point: dates, hype, calendar, in one.
                    self._schedule_new_series(series, 'wild_card',
                                              start_date)

    def _create_reseeded_round(self, winners, start_date, round_key,
                               round_name):
        """Classic format rounds 2-3: reseed by conference seed.

        Highest remaining seed hosts the lowest, second-highest hosts
        second-lowest (straight conference seeding). Seeds are the
        regular-season conference ranks, which never change once the
        bracket is set.
        """
        def _seed(t):
            try:
                return int(getattr(t, 'standings_position', 99) or 99)
            except Exception:
                return 99

        for conf_winners, conf_tag in (
                ([t for t in winners if self._is_eastern_team(t)], 'E'),
                ([t for t in winners if not self._is_eastern_team(t)],
                 'W')):
            ranked = sorted(conf_winners, key=_seed)
            n = len(ranked)
            for i in range(n // 2):
                hi, lo = ranked[i], ranked[n - 1 - i]
                series = PlayoffSeries(round_name, hi, lo)
                series.bracket_side = f"{conf_tag}R{i + 1}"
                self.playoff_series[round_key].append(series)
                self._schedule_new_series(series, round_key, start_date)

    def _create_wild_card_round(self, schedule_games=True, start_date=None):
        """Create Round 1 matchups in the NHL divisional format.

        Bracket order per conference is [DW1, DW2, D1#2, D1#3, D2#2,
        D2#3, WC1, WC2]; pairings: DW1 vs WC2, D1#2 vs D1#3, D2#2 vs
        D2#3, DW2 vs WC1. Fixed bracket — round 2 pairs winners (A,B)
        and (C,D), no reseeding.
        """
        if self._playoff_format() == 'conference':
            self._create_conference_first_round(schedule_games, start_date)
            return
        for conf_teams, conf_tag in ((self.eastern_teams, 'E'),
                                     (self.western_teams, 'W')):
            if len(conf_teams) < 8:
                continue
            DW1, DW2, D1_2, D1_3, D2_2, D2_3, WC1, WC2 = conf_teams[:8]
            matchups = [
                (DW1, WC2, 'A'),    # best division winner vs worst wild card
                (D1_2, D1_3, 'B'),  # intra-division 2 vs 3
                (D2_2, D2_3, 'C'),  # intra-division 2 vs 3
                (DW2, WC1, 'D'),    # other winner vs top wild card
            ]
            for team1, team2, side in matchups:
                series = PlayoffSeries("Wild Card Round", team1, team2)
                series.bracket_side = conf_tag + side
                self.playoff_series['wild_card'].append(series)
                if schedule_games:
                    # Single choke point: dates, hype, calendar, in one.
                    self._schedule_new_series(series, 'wild_card',
                                              start_date)
    
    # Bracket flow: Round 1 -> Round 2 -> Conference Finals -> Stanley Cup Final.
    # ('division_finals' holds the two conference-final series; 'conference_finals'
    # is kept as a legacy key.)
    ROUND_ORDER = ['wild_card', 'division_semifinals', 'division_finals',
                   'stanley_cup_final']

    def advance_to_next_round(self, round_name: str) -> bool:
        """Advance winners to the next playoff round.

        SOUNDNESS GATE: every series in the round must be complete. A
        partial advance would orphan teams and corrupt the bracket, so a
        short round refuses (returns False) instead of building half a
        round. The next round starts PLAYOFF_REST_DAYS after the LAST
        completed series — dynamic timing, never a fixed date.
        """
        # IDEMPOTENCY: the daily loop and the bracket window can both
        # trigger the advance for a finished round -- either path first
        # wins. If the current-round pointer already moved past
        # round_name, the next round was built; never rebuild it.
        # (Also covers callers that rewind current_round manually: if
        # the next round already holds series -- or the Cup already has
        # a champion -- the advance happened.)
        try:
            _order = self.ROUND_ORDER
            _cur = getattr(self, 'current_round', '')
            _next_key = {'wild_card': 'division_semifinals',
                         'division_semifinals': 'division_finals',
                         'division_finals': 'stanley_cup_final'}.get(
                             round_name)
            if _cur == 'complete':
                return True
            if _cur in _order and round_name in _order \
                    and _order.index(_cur) > _order.index(round_name):
                return True
            if _next_key and (self.playoff_series.get(_next_key) or []):
                return True
            if round_name == 'stanley_cup_final' and \
                    getattr(self, 'stanley_cup_champion', None) is not None:
                return True
        except Exception:
            pass
        current_series = self.playoff_series[round_name]
        incomplete = [s for s in current_series if not s.is_complete]
        if incomplete:
            print(f"⛔ Cannot advance from {round_name}: "
                  f"{len(incomplete)} of {len(current_series)} series "
                  f"still playing.")
            return False
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
        # Rivalry lifecycle: a completed playoff series leaves heat --
        # seven-game wars and upsets leave more. Recorded once per
        # series, here, before winners move on. Additive: rivalries only.
        try:
            from reputation_system import record_playoff_series as _rps
            _rivs = getattr(getattr(self, "league", None), "rivalries", None)
            if isinstance(_rivs, list):
                for _s in current_series:
                    if not getattr(_s, "is_complete", False) or \
                            getattr(_s, "_rivalry_recorded", False):
                        continue
                    _w = getattr(_s, "winner", None)
                    _t1, _t2 = getattr(_s, "team1", None), \
                        getattr(_s, "team2", None)
                    _l = _t2 if _w is _t1 else (_t1 if _w is _t2 else None)
                    if _w is not None and _l is not None:
                        _games = int(getattr(_s, "games_played", 7) or 7)
                        try:
                            _wp = int(getattr(_w, "standings_position", 99)
                                      or 99)
                            _lp = int(getattr(_l, "standings_position", 99)
                                      or 99)
                        except Exception:
                            _wp, _lp = 99, 99
                        _rps(_rivs, _w, _l, games=_games,
                             upset=bool(_wp > _lp))
                    _s._rivalry_recorded = True
        except Exception:
            pass
        winners = [series.winner for series in current_series if series.is_complete and series.winner]

        # Dynamic timing: the next round begins REST_DAYS after the LAST
        # series of this round ended — a sweep doesn't rush anyone, a
        # 7-game war doesn't hold the bracket hostage beyond the rest.
        next_start = None
        try:
            end_dates = [s.end_date for s in current_series
                         if getattr(s, 'end_date', None) is not None]
            if end_dates:
                next_start = (max(end_dates)
                              + timedelta(days=self.PLAYOFF_REST_DAYS))
        except Exception:
            next_start = None

        # Fixed-bracket order for round 2: map each winner back to the
        # bracket_side of the series they won (A,B,C,D per conference).
        side_of = {}
        for s in current_series:
            w = getattr(s, 'winner', None)
            if w is not None:
                side_of[id(w)] = getattr(s, 'bracket_side', '')

        if round_name == 'wild_card':
            self._create_division_semifinals(winners, next_start,
                                             prev_sides=side_of)
        elif round_name == 'division_semifinals':
            self._create_division_finals(winners, next_start)
        elif round_name == 'division_finals':
            # Conference champions advance to the Stanley Cup Final
            self._create_conference_finals(winners, next_start)
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

        # Hype: one "circle the dates" story for the new round's marquee
        # series. Not for the completed final (the Cup recap covers it).
        try:
            _next_key = {'wild_card': 'division_semifinals',
                         'division_semifinals': 'division_finals',
                         'division_finals': 'stanley_cup_final'}.get(
                             round_name)
            if _next_key:
                self._announce_round_hype(_next_key)
        except Exception:
            pass

        # Move the current-round pointer forward
        try:
            next_idx = self.ROUND_ORDER.index(round_name) + 1
            self.current_round = (self.ROUND_ORDER[next_idx]
                                  if next_idx < len(self.ROUND_ORDER) else 'complete')
        except ValueError:
            pass
        return True
    
    def _schedule_new_series(self, series, round_key, start_date):
        """Date, publish, and register one new series (single choke point)."""
        try:
            series._round_key = round_key
            self._schedule_series(series, start_date)
            self._compute_series_hype(series)
            self._publish_series_to_schedule(series)
        except Exception:
            pass

    def _compute_series_hype(self, series):
        """Stamp rivalry/intensity hype onto a series at schedule time.

        Reads the league rivalry store (bad blood from old playoff wars,
        declared hate, regional heat) and the narrative ledger, then tags
        the series: "Bad blood", "Heated rivalry", "Playoff rematch",
        "Seven-game war", "Upset watch". Marquee series are the ones fans
        circle on the calendar. Runs inside the single scheduling choke
        point so every round gets it; unscheduled projections skip it.

        Feedback loop: advance_to_next_round records heat from each
        completed series, so wars leave hype for future rounds/years.
        """
        t1, t2 = series.team1, series.team2
        n1 = getattr(t1, 'team_name', '') or ''
        n2 = getattr(t2, 'team_name', '') or ''
        heat = 0.0
        tags: List[str] = []
        rematch = False
        try:
            from reputation_system import get_rivalry_heat, rivalry_between
            rivalries = getattr(getattr(self, 'league', None),
                                'rivalries', None) or []
            try:
                heat = float(get_rivalry_heat(rivalries, t1, t2)
                             .get('heat', 0.0) or 0.0)
            except Exception:
                heat = 0.0
            try:
                rec = rivalry_between(rivalries, t1, t2, 'team_team')
                story = str((rec or {}).get('story', '') or '')
                if rec and (rec.get('origin') == 'playoff_series'
                            or 'Playoff series:' in story):
                    rematch = True
                    tags.append('Playoff rematch')
                    if 'Seven games' in story:
                        tags.append('Seven-game war')
            except Exception:
                pass
        except Exception:
            pass
        # Narrative memory can smolder where the rivalry store is quiet
        # (grudges decay slowly in the ledger).
        try:
            ledger = getattr(self, 'narrative_ledger', None)
            if ledger is not None and n1 and n2:
                mem = float(ledger.memory_weight(n1, n2) or 0.0)
                if mem >= 70.0:
                    heat = max(heat, 65.0)
        except Exception:
            pass
        if heat >= 65.0:
            tags.insert(0, 'Bad blood')
        elif heat >= 35.0:
            tags.append('Heated rivalry')
        # Upset watch: a bottom seed (7-8) drawing a top seed (1-2) in
        # round one. Works for both formats: divisional wild cards vs
        # division winners, or classic 1v8 / 2v7.
        try:
            s1 = int(getattr(t1, 'standings_position', 0) or 0)
            s2 = int(getattr(t2, 'standings_position', 0) or 0)
            if min(s1, s2) <= 2 and max(s1, s2) >= 7:
                tags.append('Upset watch')
        except Exception:
            pass
        try:
            series.rivalry_heat = max(0.0, min(100.0, heat))
            # Dedupe while keeping order (ledger + store can agree).
            seen = set()
            series.hype_tags = [t for t in tags
                                if not (t in seen or seen.add(t))]
            series.marquee = (heat >= 50.0) or rematch
        except Exception:
            pass

    def _announce_round_hype(self, round_key):
        """One inbox story per round for its marquee series.

        "Circle the dates": every flagged series gets its Game 1 date and
        story tags in a single roundup — one headline per round, inside
        the daily cap, instead of a per-series blast. Silent when there's
        no app (headless/bulk sims), when called off the main thread (the
        Sim-All worker must not touch UI), or when nothing is marquee.
        """
        try:
            import threading
            if threading.current_thread() is not threading.main_thread():
                return
            app = getattr(self, 'app', None)
            if app is None:
                return
            series_list = [s for s in (self.playoff_series.get(round_key)
                                       or [])
                           if getattr(s, 'marquee', False)]
            if not series_list:
                return
            import headlines
            items = []
            for s in series_list:
                dates = getattr(s, 'game_dates', None) or []
                d1 = dates[0] if len(dates) > 0 else None
                d2 = dates[1] if len(dates) > 1 else None
                items.append({
                    't1': getattr(s.team1, 'team_name', ''),
                    't2': getattr(s.team2, 'team_name', ''),
                    'tags': list(getattr(s, 'hype_tags', None) or []),
                    'heat': float(getattr(s, 'rivalry_heat', 0.0) or 0.0),
                    'game1_fmt': d1.strftime('%b %d') if d1 else '',
                    'game2_fmt': d2.strftime('%b %d') if d2 else '',
                })
            involved = []
            for it in items:
                involved.extend([it['t1'], it['t2']])
            headlines.deliver_spec(app, {
                'kind': 'playoff_series_preview',
                'round_name': (getattr(series_list[0], 'round_name', '')
                               or str(round_key)),
                'items': items,
                'involved': tuple(involved),
            })
        except Exception:
            pass

    def _create_division_semifinals(self, winners: List[Team],
                                    start_date=None, prev_sides=None):
        """Create Round 2: fixed bracket — winner(A) vs winner(B),
        winner(C) vs winner(D) per conference. No reseeding (NHL)."""
        if self._playoff_format() == 'conference':
            self._create_reseeded_round(winners, start_date,
                                        'division_semifinals',
                                        "Division Semifinals")
            return
        eastern_winners = [team for team in winners if self._is_eastern_team(team)]
        western_winners = [team for team in winners if not self._is_eastern_team(team)]

        # Bracket order, not seed order: A,B,C,D as the series were made.
        def _bracket_key(t):
            return (prev_sides or {}).get(id(t), '')
        eastern_winners.sort(key=_bracket_key)
        western_winners.sort(key=_bracket_key)

        for conf_winners in (eastern_winners, western_winners):
            for i in range(0, len(conf_winners), 2):
                if i + 1 < len(conf_winners):
                    series = PlayoffSeries("Division Semifinals",
                                           conf_winners[i],
                                           conf_winners[i + 1])
                    self.playoff_series['division_semifinals'].append(series)
                    self._schedule_new_series(series, 'division_semifinals',
                                              start_date)

    def _create_division_finals(self, winners: List[Team], start_date=None):
        """Create conference championship series.

        Divisional format: winner(AB) vs winner(CD) fixed bracket.
        Conference format: reseed — highest remaining seed hosts the
        lowest (with two teams left that's simply seed order).
        """
        if self._playoff_format() == 'conference':
            self._create_reseeded_round(winners, start_date,
                                        'division_finals',
                                        "Division Finals")
            return
        eastern_winners = [team for team in winners if self._is_eastern_team(team)]
        western_winners = [team for team in winners if not self._is_eastern_team(team)]

        # Create conference championship series
        if len(eastern_winners) >= 2:
            series = PlayoffSeries("Division Finals", eastern_winners[0], eastern_winners[1])
            self.playoff_series['division_finals'].append(series)
            self._schedule_new_series(series, 'division_finals', start_date)

        if len(western_winners) >= 2:
            series = PlayoffSeries("Division Finals", western_winners[0], western_winners[1])
            self.playoff_series['division_finals'].append(series)
            self._schedule_new_series(series, 'division_finals', start_date)

    def _create_conference_finals(self, winners: List[Team], start_date=None):
        """Create the Stanley Cup Final from the two conference champions."""
        eastern_winners = [t for t in winners if self._is_eastern_team(t)]
        western_winners = [t for t in winners if not self._is_eastern_team(t)]

        if eastern_winners and western_winners:
            self._create_stanley_cup_final([eastern_winners[0], western_winners[0]],
                                           start_date=start_date)

    def _create_stanley_cup_final(self, winners: List[Team], start_date=None):
        """Create Stanley Cup Final"""
        if len(winners) >= 2:
            series = PlayoffSeries("Stanley Cup Final", winners[0], winners[1])
            self.playoff_series['stanley_cup_final'].append(series)
            self._schedule_new_series(series, 'stanley_cup_final',
                                      start_date)

    def _find_series(self, series_id):
        """Return the PlayoffSeries with this id, or None."""
        if not series_id:
            return None
        try:
            for series_list in (self.playoff_series or {}).values():
                for s in series_list or []:
                    if getattr(s, 'series_id', None) == series_id:
                        return s
        except Exception:
            pass
        return None

    def try_play_scheduled_game(self, series_id, game_number) -> bool:
        """Play one calendar-scheduled playoff game, exactly once.

        The daily loop calls this for each playoff entry dated today;
        the bracket's own controls call simulate_playoff_game directly.
        Either path driving first wins -- this sims ONLY when the entry
        is the series' next unplayed game:

          - unknown series_id -> False (stale/pruned entry)
          - series already complete -> False
          - entry already played (games_played >= game_number) -> False
          - entry is not the next game
            (games_played + 1 != game_number) -> False
          - series not in the bracket's current round -> False

        Returns True when a game was simulated (and stamped onto its
        calendar entry by simulate_playoff_game).
        """
        try:
            game_number = int(game_number or 0)
        except (TypeError, ValueError):
            return False
        if game_number < 1:
            return False
        series = self._find_series(series_id)
        if series is None or bool(getattr(series, 'is_complete', False)):
            return False
        try:
            games_played = int(getattr(series, 'games_played', 0) or 0)
        except (TypeError, ValueError):
            return False
        if games_played + 1 != game_number:
            # Already simmed via the bracket (games_played >= game_number)
            # or a stale out-of-order entry -- never double-sim, never skip
            # ahead of the series' real next game.
            return False
        try:
            current = (self.playoff_series or {}).get(
                getattr(self, 'current_round', '')) or []
            if series not in current:
                return False
        except Exception:
            return False
        self.simulate_playoff_game(series)
        return True

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
        # 2-2-1-1-1 venues: the higher seed (team1) hosts games 1, 2, 5, 7.
        # The sim is venue-aware, and the scheduled calendar entries use
        # the same mapping, so the bracket and the schedule always agree.
        _home_team = series.home_team_for_game(_game_no)
        _away_team = series.away_team_for_game(_game_no)
        _team1_home = _home_team is series.team1
        # Clutch tracking (additive): a Game 7 is the 7th game of a
        # best-of-7 series. Computed BEFORE add_game_result bumps
        # games_played below.
        _is_game7 = (_game_no == 7
                     and int(getattr(series, "series_format", 7) or 7) == 7)
        try:
            from narrative_ledger import active_ledger as _al
            _led = _al()
        except Exception:
            _led = None
        _atm = pregame_crowd(_home_team, _away_team, ledger=_led,
                             is_playoff=True, series_game=_game_no,
                             elimination_game=_elim,
                             rivalry_heat=getattr(series, 'rivalry_heat',
                                                  0.0))
        game_sim = GameSim(_home_team, _away_team, is_playoff=True,
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

        # Determine winner and update series (scores are home/away now;
        # map back to the series-relative team1_won the bracket tracks).
        team1_won = (home_score > away_score) if _team1_home \
            else (away_score > home_score)

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

        # Calendar: stamp the score on this game's scheduled entry; if the
        # series just ended, prune the unplayed games from the schedule.
        try:
            self._stamp_played_game(series, home_score, away_score)
            if series.is_complete:
                self._prune_series_schedule(series)
        except Exception:
            pass

        # Playoff stat ledger: fold this game's per-player numbers into each
        # player's season playoff_stats (feeds the Conn Smythe race). Cheap:
        # one pass over the finished game's stat table, no extra simulation.
        try:
            self._fold_playoff_stats(game_sim, series.team1, series.team2,
                                     team1_won)
        except Exception:
            pass

        # Three stars of the game: Cup runs leave the same card trace as
        # the regular season -- stars on the result, season counts, and a
        # 1st-star Signature Games moment (marked playoff).
        try:
            from stars import record_game_stars as _rgs
            _pdate = getattr(getattr(self, "app", None),
                             "current_date", None)
            _pgr = {
                "game_stats": getattr(game_sim, "game_stats", None) or {},
                # The existing OT-winner +3 in select_three_stars reads
                # notable_events -- hand it over so playoff stars credit
                # the OT hero exactly like regular-season stars do.
                "notable_events": getattr(game_sim, "notable_events",
                                         None) or [],
                "home_score": home_score,
                "away_score": away_score,
                "winner": series.team1 if team1_won else series.team2,
            }
            _rgs(_pgr, _home_team, _away_team, preseason=False,
                 game_date=_pdate, playoff=True, game7=_is_game7)
            # Clutch lore (additive): announce newly-earned tags, and make
            # a Game-7 OT winner read like it. News-feed only, rare by
            # construction (tag grants happen once per tag per player;
            # Game-7 OT deciders are a few per postseason).
            try:
                from clutch import clutch_epithet as _cep7
                _app7 = getattr(self, "app", None)
                _news7 = (getattr(_app7, "add_news", None)
                          if _app7 is not None else None)
                if _news7 is not None:
                    for _g7 in (_pgr.get("clutch_tags_granted") or []):
                        _lbl7 = str(_g7.get("label", "") or "")
                        if _lbl7:
                            _news7(
                                f"\U0001f3f7\ufe0f Reputation earned: "
                                f"{_g7.get('name', 'A playoff hero')} is "
                                f"now known around the league as "
                                f"\"{_lbl7}\".")
                    if _is_game7 and game_info.get("ot"):
                        _hero7 = _game7_ot_hero(
                            _pgr, series.team1, series.team2)
                        if _hero7 is not None:
                            _hp, _hn, _ht = _hero7
                            _ep7 = _cep7(_hp)
                            _who7 = (f"{_ep7} {_hn}".strip()
                                     if _ep7 else _hn)
                            _news7(
                                f"\u2b50 GAME 7, OVERTIME: {_who7} "
                                f"({_ht}) buries the winner -- {_ht} "
                                f"take the series in the decider.")
            except Exception:
                pass
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
        # Seamless transition: at season's end the bracket builds itself
        # the moment this window opens -- no manual "Generate" click
        # between the regular season and Game 1.
        try:
            if self.playoff_bracket is None and self._regular_season_complete():
                self._generate_bracket(quiet=True)
        except Exception:
            pass
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
        self._btn_gen = control_frame.winfo_children()[-1]

        ttk.Button(control_frame, text="Simulate Round",
                  command=self._simulate_current_round, style='TButton').pack(side='left', padx=(0, 10))
        self._btn_round = control_frame.winfo_children()[-1]

        ttk.Button(control_frame, text="Simulate All Playoffs",
                  command=self._simulate_all_playoffs, style='TButton').pack(side='left', padx=(0, 10))
        self._btn_all = control_frame.winfo_children()[-1]

        ttk.Button(control_frame, text="Refresh Bracket",
                  command=self.refresh_bracket, style='TButton').pack(side='left', padx=(0, 10))

        # MP rule: a client never triggers bracket mutations -- the host
        # owns them. Buttons are disabled up front; the handlers re-check
        # (defense in depth) in case MP state changed after build.
        if self._is_mp_client():
            for _b in (self._btn_gen, self._btn_round, self._btn_all):
                try:
                    _b.state(["disabled"])
                except Exception:
                    pass

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

        # Zoom-to-fit: keep the whole tree on screen when the window
        # resizes (debounced; redraws only if the factor changed).
        self._bracket_refit_after = None
        self._bracket_last_scale = None
        try:
            canvas.bind("<Configure>", self._on_bracket_canvas_resize)
        except Exception:
            pass

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
    
    # ------------------------------------------------------------------
    # Multiplayer host-only gate
    # ------------------------------------------------------------------
    def _is_mp_client(self):
        """True when this machine is a client in someone else's MP session.

        Uses the app's own _mp_client_mode() when available; falls back to
        the raw mp_client/mp_host attrs for test doubles.
        """
        try:
            app = getattr(self, 'app', None)
            fn = getattr(app, '_mp_client_mode', None)
            if callable(fn):
                return bool(fn())
            return getattr(app, 'mp_client', None) is not None \
                and getattr(app, 'mp_host', None) is None
        except Exception:
            return False

    def _mp_guard(self, action):
        """Host-only gate for bracket mutations. Returns True to proceed.

        Clients get an in-game notice; the host (or single-player) passes
        straight through to the normal warning + fallback-save flow.
        """
        if self._is_mp_client():
            try:
                messagebox.showinfo(
                    "Host only",
                    f"Only the session host can {action}.\n\n"
                    "You're connected as a client -- ask the host to run it.",
                    parent=self)
            except Exception:
                pass
            return False
        return True

    def _generate_bracket(self, quiet=False):
        """Generate the playoff bracket.

        quiet=True skips the popup: used for the automatic bracket at
        season's end so the playoffs open seamlessly on the bracket.
        """
        if not self._mp_guard("generate the playoff bracket"):
            return
        try:
            if not hasattr(self.app, 'league') or not self.app.league:
                messagebox.showerror("Error", "No league data available")
                return

            self.playoff_bracket = PlayoffBracket(self.app.league)
            # The bracket needs the app for the current date in sim paths.
            try:
                self.playoff_bracket.app = self.app
            except Exception:
                pass
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

            if not quiet:
                messagebox.showinfo("Playoffs Generated",
                                  f"Playoff bracket created with {len(self.playoff_bracket.eastern_teams)} Eastern and "
                                  f"{len(self.playoff_bracket.western_teams)} Western Conference teams!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate playoff bracket: {str(e)}")

    def _regular_season_complete(self):
        """True when every NHL club has played its full regular-season slate."""
        try:
            fn = getattr(self.app, '_check_season_complete', None)
            if callable(fn):
                return bool(fn())
        except Exception:
            pass
        try:
            current_date = getattr(self.app, 'current_date', None)
            season_year = getattr(getattr(self.app, 'league', None),
                                  'season_year', None)
            if current_date is not None and season_year is not None:
                return current_date >= date(season_year + 1, 4, 16)
        except Exception:
            pass
        return False

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
        if not self._mp_guard("simulate a playoff round"):
            return
        if not self.playoff_bracket:
            messagebox.showwarning("Warning", "Please generate playoff bracket first")
            return
        
        current_series = self.playoff_bracket.playoff_series[self.playoff_bracket.current_round]
        incomplete_series = [s for s in current_series if not s.is_complete]
        
        if not incomplete_series:
            messagebox.showinfo("Round Complete", "Current round is already complete!")
            return
        
        # Heavy sim: warn, fallback-save, then show live progress.
        # Gating T2-Phase 3: non-modal confirm; dismiss = don't sim.
        import sim_progress
        sim_progress.ask_heavy_sim(
            self, "Simulate Round",
            f"This will simulate every remaining game of the "
            f"{self.playoff_bracket.current_round} round.",
            on_yes=self._simulate_round_confirmed)

    def _simulate_round_confirmed(self):
        """Heavy-sim continuation: fallback save, then the synchronous
        round sim behind a live progress dialog. Incomplete series are
        re-read at confirm time (live state, not click-time state)."""
        if not self.playoff_bracket:
            return
        current_series = self.playoff_bracket.playoff_series[self.playoff_bracket.current_round]
        incomplete_series = [s for s in current_series if not s.is_complete]
        if not incomplete_series:
            messagebox.showinfo("Round Complete", "Current round is already complete!")
            return
        import sim_progress
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
        if not self._mp_guard("simulate the playoffs"):
            return
        if not self.playoff_bracket:
            messagebox.showwarning("Warning", "Please generate playoff bracket first")
            return

        import sim_progress
        try:
            _headless = bool(getattr(self.app, '_bulk_simming', False))
        except Exception:
            _headless = False

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

        # Gating T2-Phase 3: non-modal confirm; dismiss = don't sim. The
        # worker body closes over the round plan built above.
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

        def _confirmed():
            sim_progress.create_fallback_save(self.app, "playoffs_all")
            sim_progress.run_threaded(
                self, "Simulating Stanley Cup Playoffs",
                _run_games, _on_done)

        sim_progress.ask_heavy_sim(
            self, "Simulate All Playoffs",
            "This will simulate every remaining playoff game through "
            "the Stanley Cup Final.",
            on_yes=_confirmed)
        return

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

    # Reference restyle (Muck's arena render): dark brushed-metal backdrop,
    # neon-glow connectors, glassy dark cards with team-color glow.
    BRACKET_BG_EDGE = "#04060B"    # backdrop vignette edge
    BRACKET_BG_GLOW = "#26314A"   # backdrop center glow
    BRACKET_CARD_BG = "#12161F"   # glassy card body
    BRACKET_ROW_TEXT = "#F2F5F9"  # near-white row text
    BRACKET_CONN_HALO = "#0E3A5C"  # connector glow: outer halo
    BRACKET_CONN_MID = "#2FB9E8"   # connector glow: neon cyan mid
    BRACKET_CONN_CORE = "#C9F1FF"  # connector glow: bright core

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

    # Zoom-to-fit bounds: the tree scales down so all 7 columns fit the
    # canvas width (no horizontal scroll, like the visualizer ice surface).
    # Below the floor the window is simply too small and scrolling returns.
    BRACKET_SCALE_MIN = 0.45

    def _bracket_scale(self):
        """Zoom factor so the full 7-column tree fits the canvas width.

        1.0 = natural size; <1 shrinks cards, gaps, and fonts
        proportionally. Clamped to [BRACKET_SCALE_MIN, 1.0].
        """
        avail = 0
        try:
            canvas = getattr(self, "canvas", None)
            if canvas is not None:
                try:
                    canvas.update_idletasks()
                except Exception:
                    pass
                avail = int(canvas.winfo_width() or 0)
        except Exception:
            avail = 0
        if avail < 200:
            try:
                avail = int(self.winfo_width() or 0)
            except Exception:
                avail = 0
        if avail < 200:
            avail = 1400  # pre-layout / headless fallback
        natural = (2 * self.BRACKET_PAD + 7 * self.BRACKET_CARD_W
                   + 6 * self.BRACKET_GAP_X)
        try:
            s = avail / float(natural)
        except Exception:
            s = 1.0
        return min(1.0, max(self.BRACKET_SCALE_MIN, s))

    def _on_bracket_canvas_resize(self, _event=None):
        """Debounced re-fit when the window is resized."""
        try:
            pending = getattr(self, "_bracket_refit_after", None)
            if pending:
                try:
                    self.after_cancel(pending)
                except Exception:
                    pass
            self._bracket_refit_after = self.after(250, self._refit_bracket)
        except Exception:
            pass

    def _refit_bracket(self):
        """Redraw only if the zoom factor materially changed."""
        self._bracket_refit_after = None
        try:
            new_s = self._bracket_scale()
            old_s = getattr(self, "_bracket_last_scale", None)
            if old_s is not None and abs(new_s - old_s) < 0.02:
                return
            self._display_bracket()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Reference restyle helpers (Muck's arena render)
    # ------------------------------------------------------------------
    @staticmethod
    def _shade_color(hex_color, factor):
        """Scale a #RRGGBB color toward black (factor < 1) or white
        (factor > 1). Used for card glows and halos."""
        try:
            hx = str(hex_color).lstrip("#")
            r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
            if factor <= 1.0:
                r, g, b = (int(c * factor) for c in (r, g, b))
            else:
                r, g, b = (int(c + (255 - c) * (factor - 1.0))
                           for c in (r, g, b))
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            return f"#{r:02X}{g:02X}{b:02X}"
        except Exception:
            return hex_color

    def _bracket_bg_photo(self, w, h):
        """Dark brushed-metal arena backdrop as a Tk photo image.

        Radial glow (BRACKET_BG_GLOW) falling off to BRACKET_BG_EDGE, with
        faint vertical brushed streaks. Rendered small and upscaled, cached
        per quantized size so resizes don't thrash. Returns None on any
        failure (callers fall back to the flat canvas bg).
        """
        try:
            w, h = max(160, int(w)), max(90, int(h))
        except Exception:
            return None
        qw, qh = max(120, w // 4), max(68, h // 4)
        key = (qw, qh)
        try:
            cached = getattr(self, "_bracket_bg_cache", None)
            if cached is not None and cached[0] == key:
                return cached[1]
        except Exception:
            pass
        try:
            from PIL import Image, ImageDraw, ImageTk
            import random

            def _rgb(hx):
                hx = str(hx).lstrip("#")
                return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))

            er, eg, eb = _rgb(self.BRACKET_BG_EDGE)
            gr, gg, gb = _rgb(self.BRACKET_BG_GLOW)
            img = Image.new("RGB", (qw, qh), (er, eg, eb))
            d = ImageDraw.Draw(img)
            cx, cy = qw / 2.0, qh * 0.42
            rx, ry = qw * 0.75, qh * 0.95
            steps = 40
            for i in range(steps, 0, -1):
                t = i / float(steps)
                k = (1.0 - t) ** 1.7
                col = (int(er + (gr - er) * k),
                       int(eg + (gg - eg) * k),
                       int(eb + (gb - eb) * k))
                d.ellipse([cx - rx * t, cy - ry * t,
                           cx + rx * t, cy + ry * t], fill=col)
            # Faint vertical brushed streaks on an overlay.
            rnd = random.Random(11)
            for _ in range(30):
                x = rnd.randint(0, qw - 1)
                shade = 6 if rnd.random() < 0.5 else -6
                d.line([x, 0, x, qh],
                       fill=(max(0, min(255, er + shade)),
                             max(0, min(255, eg + shade)),
                             max(0, min(255, eb + shade))))
            img = img.resize((w, h), Image.BILINEAR)
            photo = ImageTk.PhotoImage(img)
            try:
                self._bracket_bg_cache = (key, photo)
            except Exception:
                pass
            return photo
        except Exception:
            return None

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
            # Near-black vignette edge: any canvas area beyond the brushed
            # backdrop photo blends into the render instead of flat navy.
            canvas.configure(bg=self.BRACKET_BG_EDGE)
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

        # --- zoom-to-fit: the whole tree scales to the canvas width, so
        # --- all 7 columns stay on screen with no horizontal scrolling.
        bs = self._bracket_scale()
        self._bracket_last_scale = bs
        card_w = max(120, int(self.BRACKET_CARD_W * bs))
        gap_x = int(self.BRACKET_GAP_X * bs)
        pad = int(self.BRACKET_PAD * bs)
        gap_y = max(10, int(self.BRACKET_GAP_Y * bs))

        # --- create the series cards (provisional positions) ---
        cards = {}  # id(series) -> dict(wid, widget, x, y, series, round, ci, conf)
        for ci, ss in enumerate(col_series):
            rkey, conf = self.BRACKET_COLUMNS[ci]
            mirror = (conf == "Eastern")
            x = pad + ci * (card_w + gap_x)
            for s in ss:
                try:
                    card = self._series_card(s, projected=projected,
                                            mirror=mirror, width=card_w,
                                            scale=bs)
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
        min_h = max(48, int(80 * bs))
        for key, c in cards.items():
            try:
                heights[key] = max(min_h, int(c["widget"].winfo_reqheight()))
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
        y0 = pad + 10
        for ci in self.BRACKET_LAYOUT_ORDER:
            keys = [id(s) for s in col_series[ci] if id(s) in cards]
            if ci in (0, 6):
                y = y0
                for k in keys:
                    cards[k]["y"] = y
                    y += heights[k] + gap_y
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
                y = yy + heights[k] + gap_y

        # --- place cards ---
        for k, c in cards.items():
            try:
                canvas.coords(c["wid"], c["x"], c["y"])
            except Exception:
                pass

        # --- team-color glow halos behind each card ---
        try:
            for k, c in cards.items():
                accent = getattr(c["widget"], "_bracket_accent", None) \
                    or self.BRACKET_CONN_MID
                x, y = c["x"], c["y"]
                ch = heights[k]
                canvas.create_rectangle(
                    x - 8, y - 8, x + card_w + 8, y + ch + 8,
                    fill=self._shade_color(accent, 0.22), outline="",
                    tags=("halo",))
                canvas.create_rectangle(
                    x - 4, y - 4, x + card_w + 4, y + ch + 4,
                    fill=self._shade_color(accent, 0.40), outline="",
                    tags=("halo",))
            canvas.tag_lower("halo")
        except Exception:
            pass

        # --- neon-glow elbow connectors (West flows left->right, East
        # --- right->left): halo + mid + bright core over the same path.
        glow_w = max(0.6, bs)
        for k, tkey in targets.items():
            if tkey not in cards:
                continue
            c, t = cards[k], cards[tkey]
            try:
                if c["ci"] < t["ci"]:
                    x1 = c["x"] + card_w
                    x2 = t["x"]
                else:
                    x1 = c["x"]
                    x2 = t["x"] + card_w
                y1 = c["y"] + heights[k] / 2
                y2 = t["y"] + heights[tkey] / 2
                mx = (x1 + x2) / 2
                for lw, col in ((7 * glow_w, self.BRACKET_CONN_HALO),
                                (3.5 * glow_w, self.BRACKET_CONN_MID),
                                (1.5 * glow_w, self.BRACKET_CONN_CORE)):
                    canvas.create_line(x1, y1, mx, y1, mx, y2, x2, y2,
                                       fill=col, width=lw, smooth=False)
            except Exception:
                pass

        # --- Stanley Cup Final title above the Final card ---
        try:
            fam = self.app.FONT_FAMILY
            for k, c in cards.items():
                if c["round"] != "stanley_cup_final":
                    continue
                ex = c["x"] + card_w / 2
                ey = max(c["y"] - 8, 96)
                canvas.create_text(ex, ey - int(52 * bs), text="\U0001F3C6",
                                   font=_cfont(fam, max(12, int(20 * bs)), ""),
                                   anchor="s")
                canvas.create_text(ex, ey - int(48 * bs),
                                   text="STANLEY CUP FINAL",
                                   fill="#F2F5F9",
                                   font=_cfont(fam, max(10, int(15 * bs)),
                                              "bold"), anchor="n")
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
                            c["x"] + card_w / 2,
                            c["y"] + heights[k] + 16, anchor="n",
                            text=f"\U0001F3C6 {champ.team_name} — Stanley Cup Champions",
                            fill="#C9A227",
                            font=_cfont(self.app.FONT_FAMILY,
                                       max(9, int(12 * bs)), "bold"))
                        break
        except Exception:
            pass

        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

        # --- brushed-metal arena backdrop, drawn last and lowered to the
        # --- very bottom so cards, halos, and connectors sit on top of it.
        try:
            x1, y1, x2, y2 = canvas.bbox("all")
            photo = self._bracket_bg_photo(int(x2 - x1), int(y2 - y1))
            if photo is not None:
                self._bracket_bg_image = photo  # keep a live reference
                canvas.create_image(x1, y1, image=photo, anchor="nw",
                                    tags=("bracket_bg",))
                canvas.tag_lower("bracket_bg")
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

    @staticmethod
    def _winner_text_color(accent, on_accent, gold="#C9A227"):
        """Winner's name/wins render in gold -- unless the club's own
        accent is equally light (BOS/PIT gold, LA silver), in which case
        gold-on-gold is unreadable and we keep the accent's designed
        on-color instead."""
        def _lum(h):
            try:
                r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255.0
                           for i in (0, 2, 4))
                f = lambda c: c / 12.92 if c <= 0.03928 else \
                    ((c + 0.055) / 1.055) ** 2.4
                return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
            except Exception:
                return 0.0
        try:
            la, lg = _lum(accent), _lum(gold)
            ratio = (max(la, lg) + 0.05) / (min(la, lg) + 0.05)
        except Exception:
            ratio = 5.0
        return gold if ratio >= 2.0 else on_accent

    def _series_card(self, series, projected=False, mirror=False,
                     width=None, scale=1.0):
        """One arena-render series card: glassy dark body with a team-color
        glow border, dark rows with a team-color accent bar, near-white
        text, and the series-wins badge right-aligned on every card.
        Higher seed on top. Click opens the series detail.

        width/scale come from the zoom-to-fit layout so the whole tree
        stays on screen; fonts and row heights shrink proportionally.

        (mirror is kept for API compatibility; badges sit right on all
        cards per the reference.)
        """
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

        def _accent(tname):
            accent, _hover, on_accent = "#2E7FBF", "#14293F", "#F2F5F9"
            if _tid is not None:
                try:
                    accent, _hover, on_accent = _tid.accent_for_team(tname)
                except Exception:
                    pass
            return accent, on_accent

        top_accent, _ = _accent(getattr(order[0][0], 'team_name', ''))
        card_border = gold if decided else top_accent
        row_base = self._shade_color(self.BRACKET_CARD_BG, 1.18)
        muted = "#8A94A3"

        # Tight card: exactly two rows + padding, no dead space below.
        row_h = max(26, int(40 * scale))
        card_h = 2 * row_h + 18  # top pad 6 + mid pad 6 + bottom pad 6
        try:
            card = ctk.CTkFrame(self.canvas, width=width or self.BRACKET_CARD_W,
                                height=card_h,
                                corner_radius=8,
                                border_width=2,
                                border_color=card_border,
                                fg_color=self.BRACKET_CARD_BG)
        except Exception:
            card = ctk.CTkFrame(self.canvas, width=width or self.BRACKET_CARD_W,
                                height=card_h)
        try:
            card.pack_propagate(False)
        except Exception:
            pass
        # Stash the glow color for the canvas halo drawn behind the card.
        try:
            card._bracket_accent = top_accent
        except Exception:
            pass

        bar_w = max(3, int(5 * scale))
        for idx, (team, wins) in enumerate(order):
            tname = getattr(team, 'team_name', '')
            is_winner = decided and winner_name == tname
            is_loser = decided and not is_winner
            accent, on_accent = _accent(tname)
            try:
                row = ctk.CTkFrame(card, fg_color=row_base, corner_radius=6,
                                   height=row_h)
            except Exception:
                row = ctk.CTkFrame(card, height=row_h)
            pad_bottom = 6 if idx == len(order) - 1 else 0
            try:
                row.pack(fill="x", padx=6, pady=(6, pad_bottom))
            except Exception:
                row.pack(fill="x")
            try:
                row.pack_propagate(False)
            except Exception:
                pass
            # Team-color accent bar on the row's leading edge.
            try:
                bar = ctk.CTkFrame(row, fg_color=accent, width=bar_w,
                                   corner_radius=0)
                bar.pack(side="left", fill="y", padx=(0, 2))
                bar.pack_propagate(False)
            except Exception:
                pass
            seed = getattr(team, 'standings_position', '')
            seed_txt = f"({seed}) " if seed else ""
            abbr = team_abbr(tname)
            winner_fg = self._winner_text_color(accent, on_accent, gold)
            name_fg = winner_fg if is_winner else (
                muted if is_loser else self.BRACKET_ROW_TEXT)
            wins_fg = winner_fg if is_winner else self.BRACKET_ROW_TEXT
            try:
                name_lbl = ctk.CTkLabel(
                    row, text=f"{seed_txt}{abbr}", anchor="w",
                    font=_cfont(self.app.FONT_FAMILY, max(9, int(15 * scale)),
                               "bold"),
                    text_color=name_fg)
                wins_lbl = ctk.CTkLabel(
                    row, text=str(wins), anchor="e",
                    font=_cfont(self.app.FONT_FAMILY, max(11, int(22 * scale)),
                               "bold"),
                    text_color=wins_fg, width=max(20, int(34 * scale)))
            except Exception:
                continue
            try:
                # Badge right-aligned on every card, per the reference.
                wins_lbl.pack(side="right", padx=(2, 8))
                name_lbl.pack(side="left", padx=(6, 0))
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


def _ps_val(ps, *keys, default=0):
    """Read one stat from a per-player playoff ledger, any shape.

    Real games store player.playoff_stats as a PlayerStats dataclass
    (attribute access, games_played); fixtures sometimes use plain dicts
    (key access, 'GP'). Tries each key in order; never raises.
    """
    if ps is None:
        return default
    for key in keys:
        try:
            v = ps.get(key, None) if isinstance(ps, dict) else getattr(ps, key, None)
            if v is not None:
                return v
        except Exception:
            continue
    return default


def _top_playoff_scorers(team, n=3):
    rows = []
    for p in getattr(team, 'roster', None) or []:
        d = getattr(p, 'playoff_stats', None)
        try:
            pts = int(_ps_val(d, 'points') or 0)
        except Exception:
            pts = 0
        if pts > 0:
            name = getattr(p, 'full_name', None) or getattr(p, 'name', 'Unknown')
            try:
                g = int(_ps_val(d, 'goals') or 0)
                a = int(_ps_val(d, 'assists') or 0)
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
                # Clutch tags (additive): a tagged player skating in a
                # looming Game 7 gets a named beat -- the room knows his
                # reputation. No tagged players: no line (graceful).
                try:
                    from clutch import clutch_epithet as _cep_sl
                    _seen_ep = set()
                    for _tm in (getattr(series, 'team1', None),
                                getattr(series, 'team2', None)):
                        for _p in (getattr(_tm, 'roster', None) or []):
                            _ep = _cep_sl(_p)
                            if not _ep or _ep in _seen_ep:
                                continue
                            _seen_ep.add(_ep)
                            _nm = (getattr(_p, 'full_name', None) or
                                   (f"{getattr(_p, 'first_name', '')} "
                                    f"{getattr(_p, 'last_name', '')}")
                                   .strip()) or "A playoff hero"
                            lines.append(f"{_ep} {_nm} skates in Game 7 "
                                         f"-- this is his stage.")
                            if len(_seen_ep) >= 2:
                                break
                        if len(_seen_ep) >= 2:
                            break
                except Exception:
                    pass
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


def _series_big_moments(series):
    """Chronological highlight reel for a series.

    Derived from the real per-game facts: overtime winners, shutouts,
    statement wins (4+ goal margin), and goalie steals. Returns a list of
    (emoji, text) in game order. Empty when nothing notable happened yet.
    """
    moments = []
    try:
        games = list(getattr(series, 'game_results', None) or [])
        a1 = team_abbr(getattr(getattr(series, 'team1', None), 'team_name', ''))
        a2 = team_abbr(getattr(getattr(series, 'team2', None), 'team_name', ''))
        for g in games:
            try:
                s1, s2 = int(g.get('t1_score', 0)), int(g.get('t2_score', 0))
            except Exception:
                continue
            t1w = bool(g.get('team1_won'))
            w, l = (a1, a2) if t1w else (a2, a1)
            ws, ls = (s1, s2) if t1w else (s2, s1)
            gn = g.get('game', '?')
            core = f"Game {gn}: {w} {ws}\u2013{ls} {l}"
            if g.get('ot'):
                moments.append(("\u26A1", f"{core} \u2014 overtime winner"))
            if ls == 0 and ws > 0:
                moments.append(("\U0001F9F1", f"{core} \u2014 shutout"))
            elif ws - ls >= 4:
                moments.append(("\U0001F4A5", f"{core} \u2014 statement win"))
            gs = g.get('goalie_steal')
            if gs:
                moments.append(("\U0001F9F1",
                                f"Game {gn}: {gs} stood on his head ({core})"))
    except Exception:
        pass
    return moments


def _detail_intensity(parent, app, series):
    """Per-series intensity meter: what the in-game meter will show.

    Scoped to the two clubs' ledger heat (same incidents, bands, and colors
    as the in-game INTENSITY meter), framed as the hype forecast for an
    unstarted series and the live temperature for one underway.
    Grudge-week-style hype copy when it's hot.
    """
    import tkinter as tk
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg, dim = "#C9A227", "#DCE3EB", "#8A94A0"
    ctk.CTkLabel(parent, text="Series intensity",
                 font=_cfont(fam, 13, "bold"),
                 text_color=gold).pack(anchor="w", pady=(8, 2))
    t1n = getattr(getattr(series, 'team1', None), 'team_name', '')
    t2n = getattr(getattr(series, 'team2', None), 'team_name', '')
    try:
        from narrative_ledger import active_ledger as _al
        from season_intensity import series_intensity, hype_line, draw_gauge
        info = series_intensity(_al(), t1n, t2n)
        canvas = tk.Canvas(parent, width=200, height=132,
                           bg="#0A1428", highlightthickness=0)
        canvas.pack(pady=(2, 2))
        draw_gauge(canvas, 100, 82, 48, info, font_family=fam,
                   title="SERIES INTENSITY")
        hype = hype_line(info.get("label"),
                         team_abbr(t1n), team_abbr(t2n))
        ctk.CTkLabel(parent, text=hype, font=_cfont(fam, 12, "italic"),
                     text_color=info.get("color", fg),
                     anchor="w", wraplength=480,
                     justify="left").pack(fill="x", padx=4, pady=(2, 0))
        drivers = info.get("drivers") or []
        if drivers and float(info.get("value", 0) or 0) >= 25:
            dtxt = str(drivers[0].get("label", "") or "")[:110]
            ctk.CTkLabel(parent, text=f"Driving it: {dtxt}",
                         font=_cfont(fam, 11, "italic"), text_color=dim,
                         anchor="w", wraplength=480,
                         justify="left").pack(fill="x", padx=4)
    except Exception:
        pass


def _detail_big_moments(parent, app, series):
    """Big-moment log: the series' defining on-ice moments, in order."""
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg, dim = "#C9A227", "#DCE3EB", "#8A94A0"
    ctk.CTkLabel(parent, text="Big moments",
                 font=_cfont(fam, 13, "bold"),
                 text_color=gold).pack(anchor="w", pady=(8, 2))
    moments = _series_big_moments(series)
    if not moments:
        ctk.CTkLabel(parent, text="No games yet \u2014 the moments will write "
                                  "themselves.",
                     font=_cfont(fam, 12, "italic"),
                     text_color=dim).pack(anchor="w", padx=4)
        return
    for emoji, txt in moments:
        ctk.CTkLabel(parent, text=f"{emoji}  {txt}",
                     font=_cfont(fam, 12, ""), text_color=fg,
                     anchor="w", wraplength=480,
                     justify="left").pack(fill="x", padx=4, pady=1)


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

    # Per-series intensity: the hype forecast (or live temperature) for
    # this matchup -- what the in-game meter will show when they meet.
    _detail_intensity(parent, app, series)

    if projected:
        _detail_tale_of_tape(parent, app, series)
    else:
        _detail_playoff_tape(parent, app, series, bracket)
        _detail_games(parent, app, series)
        _detail_splits(parent, app, series)
        ctk.CTkLabel(parent, text="Storylines",
                     font=_cfont(fam, 13, "bold"),
                     text_color=gold).pack(anchor="w", pady=(8, 2))
        for ln in _series_storylines(series):
            ctk.CTkLabel(parent, text="•  " + ln, font=_cfont(fam, 12, ""),
                         text_color=fg, anchor="w", wraplength=480,
                         justify="left").pack(fill="x", padx=4, pady=1)
        _detail_big_moments(parent, app, series)
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


def _playoff_team_line(bracket, team):
    """Aggregate a team's playoff numbers by walking the whole bracket.

    Returns GP/W/L/GF/GA/OTL summed over every series the team has played.
    Never raises; unknown teams come back all zeros.
    """
    name = getattr(team, 'team_name', '')
    gp = w = l = gf = ga = otl = 0
    try:
        rounds = getattr(bracket, 'playoff_series', {}) or {}
        for _rnd, series_list in rounds.items():
            for s in series_list or []:
                t1n = getattr(getattr(s, 'team1', None), 'team_name', '')
                t2n = getattr(getattr(s, 'team2', None), 'team_name', '')
                if name not in (t1n, t2n):
                    continue
                mine = 0 if name == t1n else 1
                for gm in list(getattr(s, 'game_results', None) or []):
                    try:
                        s1 = int(gm.get('t1_score', 0))
                        s2 = int(gm.get('t2_score', 0))
                    except Exception:
                        continue
                    ms, ts = (s1, s2) if mine == 0 else (s2, s1)
                    gp += 1
                    gf += ms
                    ga += ts
                    if ms > ts:
                        w += 1
                    else:
                        l += 1
                        if gm.get('ot'):
                            otl += 1
    except Exception:
        pass
    return {'gp': gp, 'w': w, 'l': l, 'gf': gf, 'ga': ga, 'otl': otl}


def _playoff_goalie_line(team):
    """(last_name, sv%, shutouts) for the team's most-used playoff goalie.

    Reads the same per-player playoff_stats the Conn Smythe race uses.
    Returns None when nobody has tended net yet.
    """
    best, best_gp = None, -1
    for p in getattr(team, 'roster', None) or []:
        ps = getattr(p, 'playoff_stats', None)
        try:
            saves = int(_ps_val(ps, 'saves') or 0)
        except Exception:
            saves = 0
        if saves <= 0:
            continue
        try:
            gp = int(_ps_val(ps, 'GP', 'gp', 'games_played') or 0)
        except Exception:
            gp = 0
        if gp > best_gp:
            best, best_gp = p, gp
    if best is None:
        return None
    ps = getattr(best, 'playoff_stats', None)
    try:
        sv = float(_ps_val(ps, 'saves') or 0) / float(_ps_val(ps, 'shots_against') or 1)
    except Exception:
        sv = 0.0
    try:
        so = int(_ps_val(ps, 'shutouts') or 0)
    except Exception:
        so = 0
    name = getattr(best, 'full_name', None) or getattr(best, 'name', 'Unknown')
    return str(name).split()[-1], sv, so


def _detail_playoff_tape(parent, app, series, bracket):
    """Tale of the tape for a live series: both clubs' playoff runs so far,
    side by side. Regular season built the seeding; this is the form that
    actually matters now."""
    fam = getattr(app, 'FONT_FAMILY', 'Arial')
    gold, fg, dim = "#C9A227", "#DCE3EB", "#8A94A0"
    ctk.CTkLabel(parent, text="Tale of the tape (playoffs to date)",
                 font=_cfont(fam, 13, "bold"),
                 text_color=gold).pack(anchor="w", pady=(8, 2))
    t1, t2 = series.team1, series.team2
    a1 = team_abbr(getattr(t1, 'team_name', ''))
    a2 = team_abbr(getattr(t2, 'team_name', ''))
    L = [_playoff_team_line(bracket, t1), _playoff_team_line(bracket, t2)]
    G = [_playoff_goalie_line(t1), _playoff_goalie_line(t2)]
    S = [_top_playoff_scorers(t, n=1) for t in (t1, t2)]

    def _per(line, key):
        gp = line['gp']
        return f"{line[key] / gp:.2f}" if gp else "--"

    def _fmt_goalie(gl):
        if gl is None:
            return "--"
        last, sv, so = gl
        return f"{last} {sv:.3f}".replace("0.", ".") + f"  ({so} SO)"

    def _fmt_scorer(sc):
        if not sc:
            return "--"
        pts, name, gg, aa = sc[0]
        return f"{str(name).split()[-1]} {pts} pts ({gg}G)"

    rows = [
        ("Record", f"{L[0]['w']}-{L[0]['l']}", f"{L[1]['w']}-{L[1]['l']}"),
        ("Goals / game", _per(L[0], 'gf'), _per(L[1], 'gf')),
        ("Allowed / game", _per(L[0], 'ga'), _per(L[1], 'ga')),
        ("OT losses", str(L[0]['otl']), str(L[1]['otl'])),
        ("Goalie (SV%)", _fmt_goalie(G[0]), _fmt_goalie(G[1])),
        ("Top scorer", _fmt_scorer(S[0]), _fmt_scorer(S[1])),
    ]
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=4)
    ctk.CTkLabel(frame, text=a1, font=_cfont(fam, 12, "bold"),
                 text_color=gold).grid(row=0, column=1, padx=10, sticky="e")
    ctk.CTkLabel(frame, text=a2, font=_cfont(fam, 12, "bold"),
                 text_color=gold).grid(row=0, column=2, padx=10, sticky="e")
    for r, (label, v1, v2) in enumerate(rows, start=1):
        ctk.CTkLabel(frame, text=label, font=_cfont(fam, 12, ""),
                     text_color=dim).grid(row=r, column=0, sticky="w",
                                          padx=(0, 8), pady=1)
        ctk.CTkLabel(frame, text=v1, font=("Courier", 12, "bold"),
                     text_color=fg).grid(row=r, column=1, sticky="e",
                                         padx=10, pady=1)
        ctk.CTkLabel(frame, text=v2, font=("Courier", 12, "bold"),
                     text_color=fg).grid(row=r, column=2, sticky="e",
                                         padx=10, pady=1)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(parent,
                 text="Playoff numbers only — the regular season built the "
                      "seeding, not the story.",
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
