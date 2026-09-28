"""Persistent shot charts: capture, store, and query shot locations.

At game end, the visualizer exports {game_id, date, home, away, shots}.
Stored on the career (cap: last 50 games, ring buffer). Viewable from
results screen, team pages, and player profiles.

Design doc: docs/REPLAYABLE_EVIDENCE_DESIGN.md

Engine boundary: zero sim changes. Purely capture + presentation of data
the engine already emits.
"""

from collections import deque
from typing import Any, Dict, List, Optional


MAX_GAMES = 50


class ShotChartStore:
    """Ring buffer of per-game shot charts."""

    def __init__(self, max_games: int = MAX_GAMES):
        self.games: deque = deque(maxlen=max_games)
        self._by_id: Dict[str, Dict[str, Any]] = {}

    def add(self, game_dict: Dict[str, Any]):
        """Add a game shot chart. Evicts oldest if at capacity."""
        gid = game_dict.get("game_id")
        if gid and gid in self._by_id:
            # Replace existing (e.g., re-export)
            self.games = deque(
                [g for g in self.games if g.get("game_id") != gid],
                maxlen=self.games.maxlen)
        self.games.append(game_dict)
        if gid:
            # Rebuild index (deque doesn't support efficient removal)
            self._by_id = {g.get("game_id"): g for g in self.games if g.get("game_id")}

    def get(self, game_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(game_id)

    def for_team(self, team_name: str, last_n: int = 5) -> List[Dict[str, Any]]:
        """Shot charts for a team's last N games (as home or away)."""
        result = []
        for g in reversed(self.games):
            if g.get("home") == team_name or g.get("away") == team_name:
                result.append(g)
                if len(result) >= last_n:
                    break
        return result

    def for_player(self, player_id: Any) -> List[Dict[str, Any]]:
        """All shots by a player across stored games."""
        shots = []
        for g in self.games:
            for s in g.get("shots", []):
                if s.get("shooter_id") == player_id:
                    shots.append({
                        **s,
                        "game_id": g.get("game_id"),
                        "date": g.get("date"),
                        "home": g.get("home"),
                        "away": g.get("away"),
                    })
        return shots

    def aggregate_team_shots(self, team_name: str, last_n: int = 5) -> List[Dict[str, Any]]:
        """All shots by a team across their last N games (for team shot map)."""
        shots = []
        for g in self.for_team(team_name, last_n):
            is_home = g.get("home") == team_name
            side = "home" if is_home else "away"
            for s in g.get("shots", []):
                if s.get("side") == side:
                    shots.append(s)
        return shots

    def to_dict(self) -> Dict[str, Any]:
        return {"games": list(self.games)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShotChartStore":
        store = cls()
        for g in data.get("games", []):
            store.add(g)
        return store


def draw_shotmap(canvas, shots: List[Dict[str, Any]],
                 X, Y, home_primary: str = "#00ff9d",
                 away_primary: str = "#ff6b6b"):
    """Draw shots on a tkinter canvas. X/Y are coordinate transform functions.

    Shared helper: the visualizer and the chart viewer both use this.
    Shot dict: {x, y, side ('home'|'away'), result ('goal'|'save'|'block'|'miss')}.
    """
    canvas.delete("shotmap")
    for s in shots:
        x, y = s.get("x", 0), s.get("y", 0)
        side = s.get("side", "home")
        result = s.get("result", "miss")
        px, py = X(x), Y(y)
        col = home_primary if side == "home" else away_primary
        if result == "goal":
            # Green X (goal)
            r = 7
            canvas.create_line(px - r, py, px + r, py, fill="#00ff9d",
                               width=2, tags=("shotmap", "fx"))
            canvas.create_line(px, py - r, px, py + r, fill="#00ff9d",
                               width=2, tags=("shotmap", "fx"))
        elif result == "save":
            # Filled circle (saved)
            r = 5
            canvas.create_oval(px - r, py - r, px + r, py + r,
                               fill=col, outline="white", tags=("shotmap", "fx"))
        elif result == "block":
            # Triangle (blocked)
            r = 6
            canvas.create_polygon(px, py - r, px - r, py + r, px + r, py + r,
                                  fill=col, outline="white", tags=("shotmap", "fx"))
        else:  # miss
            # Small hollow circle (missed)
            r = 4
            canvas.create_oval(px - r, py - r, px + r, py + r,
                               outline=col, width=1, tags=("shotmap", "fx"))
