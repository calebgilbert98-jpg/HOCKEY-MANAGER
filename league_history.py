"""
League History — the universe's memory (roadmap F2).

Records every completed season: champions, award winners, single-season
records, and career leaderboards. This is the data foundation; the season
flow calls record_season() when a season completes, and UI reads the
query methods. Nothing here depends on the season flow being real yet.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import json


@dataclass
class SeasonSummary:
    """One completed season."""
    season_id: str  # e.g. "2026-27"
    champion: str = ""
    runner_up: str = ""
    final_score: str = ""  # e.g. "4-2"
    # Award winners: award name -> player name
    awards: Dict[str, str] = field(default_factory=dict)
    # Single-season leaders: stat -> (player, value, team)
    scoring_leader: Optional[tuple] = None  # (name, points, team)
    goals_leader: Optional[tuple] = None
    assists_leader: Optional[tuple] = None
    goalie_wins_leader: Optional[tuple] = None
    goalie_sv_pct_leader: Optional[tuple] = None
    # Team records
    most_wins: Optional[tuple] = None  # (team, wins)
    most_points: Optional[tuple] = None  # (team, points)


@dataclass
class CareerTotals:
    """Accumulated career stats for one player."""
    player_id: str = ""
    name: str = ""
    games: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    pim: int = 0
    # Goalie
    wins: int = 0
    losses: int = 0
    shutouts: int = 0
    cups: int = 0  # championships won


class LeagueHistory:
    """The league's permanent memory."""

    def __init__(self):
        self.seasons: List[SeasonSummary] = []
        self.careers: Dict[str, CareerTotals] = {}  # player_id -> totals
        # All-time single-season records: stat -> (name, value, season, team)
        self.single_season_records: Dict[str, tuple] = {}
        # Franchise titles: team -> [season_ids]
        self.franchise_titles: Dict[str, List[str]] = {}

    def record_season(self, summary: SeasonSummary,
                      player_stats: Optional[List[Dict[str, Any]]] = None,
                      goalie_stats: Optional[List[Dict[str, Any]]] = None):
        """Record a completed season. player_stats: list of dicts with
        player_id, name, team, gp, g, a, pts, pim. goalie_stats: player_id,
        name, team, w, l, so.
        """
        self.seasons.append(summary)

        # Champion bookkeeping
        if summary.champion:
            self.franchise_titles.setdefault(summary.champion, []).append(
                summary.season_id)

        # Accumulate careers + check single-season records
        for ps in (player_stats or []):
            pid = ps.get('player_id', ps.get('name', ''))
            c = self.careers.setdefault(pid, CareerTotals(
                player_id=pid, name=ps.get('name', '')))
            c.games += ps.get('gp', 0)
            c.goals += ps.get('g', 0)
            c.assists += ps.get('a', 0)
            pts = ps.get('pts', ps.get('g', 0) + ps.get('a', 0))
            c.points += pts
            c.pim += ps.get('pim', 0)
            if summary.champion and ps.get('team') == summary.champion:
                c.cups += 1
            self._check_record('goals', ps.get('g', 0), ps, summary)
            self._check_record('assists', ps.get('a', 0), ps, summary)
            self._check_record('points', pts, ps, summary)

        for gs in (goalie_stats or []):
            pid = gs.get('player_id', gs.get('name', ''))
            c = self.careers.setdefault(pid, CareerTotals(
                player_id=pid, name=gs.get('name', '')))
            c.wins += gs.get('w', 0)
            c.losses += gs.get('l', 0)
            c.shutouts += gs.get('so', 0)
            if summary.champion and gs.get('team') == summary.champion:
                c.cups += 1
            self._check_record('goalie_wins', gs.get('w', 0), gs, summary)
            self._check_record('shutouts', gs.get('so', 0), gs, summary)

    def _check_record(self, stat: str, value: int, ps: Dict,
                      summary: SeasonSummary):
        current = self.single_season_records.get(stat)
        if value and (current is None or value > current[1]):
            self.single_season_records[stat] = (
                ps.get('name', ''), value, summary.season_id,
                ps.get('team', ''))

    # ---- Queries (UI reads these) ----

    def champions(self) -> List[tuple]:
        """[(season_id, champion, runner_up, final_score), ...] newest first."""
        return [(s.season_id, s.champion, s.runner_up, s.final_score)
                for s in reversed(self.seasons)]

    def career_leaders(self, stat: str, n: int = 10) -> List[tuple]:
        """Top-n career leaders: [(name, value, cups), ...]."""
        valid = {'goals', 'assists', 'points', 'games', 'pim',
                 'wins', 'shutouts'}
        if stat not in valid:
            raise ValueError(f"unknown career stat: {stat}")
        ranked = sorted(self.careers.values(),
                        key=lambda c: getattr(c, stat), reverse=True)
        return [(c.name, getattr(c, stat), c.cups) for c in ranked[:n]]

    def franchise_history(self, team: str) -> Dict[str, Any]:
        titles = self.franchise_titles.get(team, [])
        return {
            'team': team,
            'championships': len(titles),
            'title_seasons': titles,
            'seasons_recorded': len(self.seasons),
        }

    # ---- Persistence ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            'seasons': [asdict(s) for s in self.seasons],
            'careers': {k: asdict(v) for k, v in self.careers.items()},
            'single_season_records': {
                k: list(v) for k, v in self.single_season_records.items()},
            'franchise_titles': self.franchise_titles,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LeagueHistory':
        h = cls()
        h.seasons = [SeasonSummary(**s) for s in data.get('seasons', [])]
        h.careers = {k: CareerTotals(**v)
                     for k, v in data.get('careers', {}).items()}
        h.single_season_records = {
            k: tuple(v)
            for k, v in data.get('single_season_records', {}).items()}
        h.franchise_titles = data.get('franchise_titles', {})
        return h

    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str) -> 'LeagueHistory':
        with open(path) as f:
            return cls.from_dict(json.load(f))
