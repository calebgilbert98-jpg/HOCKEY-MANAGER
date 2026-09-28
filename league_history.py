"""League Memory: persistent archive of seasons, awards, leaders, Hall of Fame.

Records every season's champion, award winners, and standings; tracks career
leaderboards; inducts Hall of Famers at retirement. Read-only with respect to
gameplay — it records outcomes, never changes them.

Design doc: docs/LEAGUE_MEMORY_DESIGN.md
"""

from typing import Any, Dict, List, Optional


# Hall of Fame thresholds
HOF_POINTS = 1000
HOF_GOALS = 500
HOF_GOALIE_WINS = 300
HOF_GAMES_SKATER = 1200
HOF_GAMES_GOALIE = 600


class LeagueHistory:
    """Persistent league archive. Stored on the career, saved via save_load_system."""

    def __init__(self):
        self.seasons: List[Dict[str, Any]] = []  # one per completed season
        self.hall_of_fame: List[Dict[str, Any]] = []  # inducted players
        self.first_season_year: Optional[int] = None

    # -- Season archive --

    def record_season(self, year: int, champion: Optional[str],
                      runner_up: Optional[str], series_score: Optional[str],
                      presidents_trophy: Optional[str],
                      conn_smythe: Optional[str],
                      awards: Dict[str, str],
                      standings_snapshot: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Record a completed season. Returns the season record."""
        if self.first_season_year is None:
            self.first_season_year = year
        # Avoid double-recording (season-end flow can re-enter)
        if any(s.get("year") == year for s in self.seasons):
            return next(s for s in self.seasons if s.get("year") == year)
        record = {
            "year": year,
            "champion": champion,
            "runner_up": runner_up,
            "series_score": series_score,
            "presidents_trophy": presidents_trophy,
            "conn_smythe": conn_smythe,
            "awards": dict(awards),
            "standings": standings_snapshot,
        }
        self.seasons.append(record)
        return record

    def get_season(self, year: int) -> Optional[Dict[str, Any]]:
        for s in self.seasons:
            if s.get("year") == year:
                return s
        return None

    def champions_list(self) -> List[Dict[str, Any]]:
        """All champions, newest first."""
        return sorted(
            [s for s in self.seasons if s.get("champion")],
            key=lambda s: s["year"], reverse=True)

    # -- Career leaderboards --

    @staticmethod
    def career_leaders(players: List[Any], category: str,
                       limit: int = 25) -> List[Dict[str, Any]]:
        """All-time leaders from active players' career_* totals plus HOFers.

        category: 'points' | 'goals' | 'assists' | 'wins' | 'shutouts' | 'save_pct'
        """
        skaters = ["points", "goals", "assists"]
        goalies = ["wins", "shutouts", "save_pct"]
        results = []
        for p in players:
            try:
                pos = getattr(p, "primary_position", None)
                pos_name = getattr(pos, "name", str(pos))
                is_goalie = "GOALIE" in pos_name.upper()
                if category in skaters and is_goalie:
                    continue
                if category in goalies and not is_goalie:
                    continue
                career = getattr(p, "career_stats", {}) or {}
                val = 0
                if category == "points":
                    val = career.get("points", 0)
                elif category == "goals":
                    val = career.get("goals", 0)
                elif category == "assists":
                    val = career.get("assists", 0)
                elif category == "wins":
                    val = career.get("wins", 0)
                elif category == "shutouts":
                    val = career.get("shutouts", 0)
                elif category == "save_pct":
                    # Need min games; compute from shots/saves if available
                    gp = career.get("games_played", 0)
                    if gp < 200:
                        continue
                    saves = career.get("saves", 0)
                    shots = career.get("shots_against", 0)
                    val = (saves / shots) if shots > 0 else 0
                # Min games filter for counting stats
                if category in ("points", "goals", "assists"):
                    if career.get("games_played", 0) < 100 and val < 50:
                        continue
                if category in ("wins", "shutouts"):
                    if career.get("games_played", 0) < 100 and val == 0:
                        continue
                results.append({
                    "name": getattr(p, "full_name", getattr(p, "name", "?")),
                    "team": getattr(p, "team_name", ""),
                    "value": val,
                    "games": career.get("games_played", 0),
                })
            except Exception:
                continue
        # Sort descending (higher is better for all categories)
        results.sort(key=lambda r: r["value"], reverse=True)
        return results[:limit]

    # -- Hall of Fame --

    @staticmethod
    def qualifies_for_hof(player: Any) -> bool:
        """Does this retiring player clear the Hall of Fame bar?"""
        try:
            career = getattr(player, "career_stats", {}) or {}
            pos = getattr(player, "primary_position", None)
            pos_name = getattr(pos, "name", str(pos))
            is_goalie = "GOALIE" in pos_name.upper()
            icon_level = getattr(player, "icon_level", "")
            if icon_level == "icon":
                return True
            if is_goalie:
                return (career.get("wins", 0) >= HOF_GOALIE_WINS or
                        career.get("games_played", 0) >= HOF_GAMES_GOALIE)
            return (career.get("points", 0) >= HOF_POINTS or
                    career.get("goals", 0) >= HOF_GOALS or
                    career.get("games_played", 0) >= HOF_GAMES_SKATER)
        except Exception:
            return False

    def induct(self, player: Any, year: int) -> Optional[Dict[str, Any]]:
        """Induct a player into the Hall of Fame. Returns the induction record."""
        name = getattr(player, "full_name", getattr(player, "name", "?"))
        # Avoid double-induction
        if any(h.get("name") == name for h in self.hall_of_fame):
            return None
        career = getattr(player, "career_stats", {}) or {}
        pos = getattr(player, "primary_position", None)
        record = {
            "name": name,
            "position": getattr(pos, "name", str(pos)),
            "year_inducted": year,
            "teams": getattr(player, "teams_played_for", [getattr(player, "team_name", "")]),
            "games": career.get("games_played", 0),
            "goals": career.get("goals", 0),
            "assists": career.get("assists", 0),
            "points": career.get("points", 0),
            "wins": career.get("wins", 0),
            "shutouts": career.get("shutouts", 0),
            "cups": getattr(player, "stanley_cups", 0),
            "awards": getattr(player, "awards_won", []),
        }
        self.hall_of_fame.append(record)
        return record

    # -- Persistence --

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seasons": self.seasons,
            "hall_of_fame": self.hall_of_fame,
            "first_season_year": self.first_season_year,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeagueHistory":
        h = cls()
        h.seasons = data.get("seasons", [])
        h.hall_of_fame = data.get("hall_of_fame", [])
        h.first_season_year = data.get("first_season_year")
        return h
