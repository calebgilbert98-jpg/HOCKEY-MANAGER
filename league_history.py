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
        self.franchise_records = FranchiseRecords()
        self._seed_historical_records()

    def _seed_historical_records(self):
        """Backfill real NHL franchise history into an empty record book."""
        fr = self.franchise_records
        # Skip if any records already exist (simulated or previously seeded)
        stores = (fr.career_records, fr.season_records,
                  fr.goalie_career_records, fr.goalie_season_records,
                  fr.team_season_records)
        if any(s for s in stores):
            return
        try:
            from franchise_records_seed import FRANCHISE_RECORDS_SEED
        except ImportError:
            return
        fr.seed_historical_records(FRANCHISE_RECORDS_SEED)

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
            "franchise_records": self.franchise_records.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeagueHistory":
        h = cls()
        h.seasons = data.get("seasons", [])
        h.hall_of_fame = data.get("hall_of_fame", [])
        h.first_season_year = data.get("first_season_year")
        h.franchise_records = FranchiseRecords.from_dict(
            data.get("franchise_records", {}))
        # Old saves predate the record book: backfill real NHL history
        h._seed_historical_records()
        return h


# ---------------------------------------------------------------------------
# Franchise Records
# ---------------------------------------------------------------------------

# Record categories, mirroring how NHL clubs publish record books.
SKATER_CAREER_RECORDS = ["games", "goals", "assists", "points", "pim", "shots"]
SKATER_SEASON_RECORDS = ["goals", "assists", "points", "shots", "pim"]
GOALIE_CAREER_RECORDS = ["games", "wins", "shutouts", "saves"]
GOALIE_SEASON_RECORDS = ["wins", "shutouts", "save_pct"]
TEAM_SEASON_RECORDS = ["points", "wins", "goals_for", "goals_against",
                       "goal_differential"]


class FranchiseRecords:
    """All-time records per franchise, in the style of NHL team record books.

    Tracks, for each franchise (keyed by team name):
    - Skater career records: most games/goals/assists/points/PIM/shots
    - Skater single-season records: most goals/assists/points/shots/PIM
    - Goalie career records: most games/wins/shutouts/saves
    - Goalie single-season records: most wins/shutouts, best SV%
    - Team season records: most points/wins, most/fewest goals for/against,
      best differential
    - Streaks: longest win streak, longest unbeaten streak

    Career accumulations are per-franchise: a player's stats count toward a
    franchise only for seasons played with that club. update_from_season()
    should be called at each season end.
    """

    def __init__(self):
        # {team_name: {player_id: {stat: total}}}
        self.franchise_career: Dict[str, Dict[str, Dict[str, float]]] = {}
        # {team_name: {category: {value, player, season}}}
        self.career_records: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.season_records: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.goalie_career_records: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.goalie_season_records: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.team_season_records: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.streaks: Dict[str, Dict[str, Any]] = {}
        # {player_id: name} for display
        self._names: Dict[str, str] = {}

    # -- internal helpers --

    @staticmethod
    def _pid(player: Any) -> str:
        return str(getattr(player, "id", getattr(player, "full_name", "?")))

    @staticmethod
    def _is_goalie(player: Any) -> bool:
        pos = getattr(player, "primary_position", None)
        return "GOALIE" in getattr(pos, "name", str(pos)).upper()

    def _accum(self, team_name: str, player: Any) -> Dict[str, float]:
        tc = self.franchise_career.setdefault(team_name, {})
        pid = self._pid(player)
        acc = tc.setdefault(pid, {c: 0 for c in
                                  SKATER_CAREER_RECORDS + GOALIE_CAREER_RECORDS})
        self._names[pid] = getattr(player, "full_name",
                                    getattr(player, "name", "?"))
        return acc

    def _maybe_record(self, store: Dict[str, Dict[str, Dict[str, Any]]],
                      team_name: str, category: str, value: float,
                      player: Any, season: str,
                      higher_is_better: bool = True,
                      label: Optional[str] = None) -> bool:
        """Set a record if value beats the stored one. Returns True if new record."""
        recs = store.setdefault(team_name, {})
        cur = recs.get(category)
        beats = (cur is None or
                 (higher_is_better and value > cur["value"]) or
                 (not higher_is_better and value < cur["value"]))
        if beats and value > 0:
            recs[category] = {
                "value": value,
                "player": label or getattr(player, "full_name",
                                           getattr(player, "name", "?")),
                "player_id": self._pid(player),
                "season": season,
            }
            return True
        return False

    # -- season-end update --

    def update_from_season(self, team: Any, season_label: str) -> List[Dict[str, Any]]:
        """Fold a completed season into franchise records.

        Returns a list of newly-set records (for news/inbox).
        """
        new_records = []
        team_name = getattr(team, "team_name", "?")
        rosters = (list(getattr(team, "roster", []) or []) +
                   list(getattr(team, "ahl_roster", []) or []))

        for p in rosters:
            # Authoritative season totals live directly on the Player
            # (add_game_stats); fall back to the .stats sub-object.
            gp_direct = getattr(p, "games_played", 0) or 0
            st = p if gp_direct else (
                getattr(p, "stats", None) or getattr(p, "season_stats", None))
            if st is None:
                continue
            acc = self._accum(team_name, p)
            gp = getattr(st, "games_played", 0) or 0
            if gp == 0:
                continue
            if self._is_goalie(p):
                for cat, attr in (("games", "games_played"), ("wins", "wins"),
                                  ("shutouts", "shutouts"), ("saves", "saves")):
                    v = getattr(st, attr, 0) or 0
                    acc[cat] += v
                    if self._maybe_record(self.goalie_career_records, team_name,
                                          cat, acc[cat], p, season_label):
                        new_records.append({"team": team_name, "type": "goalie_career",
                                            "category": cat, "player": self._names[self._pid(p)],
                                            "value": acc[cat]})
                # Single-season goalie records
                w = getattr(st, "wins", 0) or 0
                so = getattr(st, "shutouts", 0) or 0
                sa = getattr(st, "shots_against", 0) or 0
                sv = getattr(st, "saves", 0) or 0
                sv_pct = (sv / sa) if sa >= 500 else 0  # min. workload
                for cat, v in (("wins", w), ("shutouts", so), ("save_pct", sv_pct)):
                    if self._maybe_record(self.goalie_season_records, team_name,
                                          cat, v, p, season_label):
                        new_records.append({"team": team_name, "type": "goalie_season",
                                            "category": cat, "player": self._names[self._pid(p)],
                                            "value": v, "season": season_label})
            else:
                for cat, attr in (("games", "games_played"), ("goals", "goals"),
                                  ("assists", "assists"),
                                  ("shots", "shots")):
                    v = getattr(st, attr, 0) or 0
                    acc[cat] += v
                acc["pim"] += (getattr(st, "penalty_minutes", 0) or 0
                               or getattr(st, "penalties_in_minutes", 0) or 0)
                acc["points"] += (getattr(st, "goals", 0) or 0) + (getattr(st, "assists", 0) or 0)
                for cat in SKATER_CAREER_RECORDS:
                    if self._maybe_record(self.career_records, team_name,
                                          cat, acc[cat], p, season_label):
                        new_records.append({"team": team_name, "type": "career",
                                            "category": cat, "player": self._names[self._pid(p)],
                                            "value": acc[cat]})
                # Single-season skater records
                season_vals = {
                    "goals": getattr(st, "goals", 0) or 0,
                    "assists": getattr(st, "assists", 0) or 0,
                    "points": (getattr(st, "goals", 0) or 0) + (getattr(st, "assists", 0) or 0),
                    "shots": getattr(st, "shots", 0) or 0,
                    "pim": (getattr(st, "penalty_minutes", 0) or 0
                            or getattr(st, "penalties_in_minutes", 0) or 0),
                }
                for cat, v in season_vals.items():
                    if self._maybe_record(self.season_records, team_name,
                                          cat, v, p, season_label):
                        new_records.append({"team": team_name, "type": "season",
                                            "category": cat, "player": self._names[self._pid(p)],
                                            "value": v, "season": season_label})

        # Team season records
        pts = getattr(team, "points", 0) or 0
        wins = getattr(team, "wins", 0) or 0
        gf = getattr(team, "goals_for", 0) or 0
        ga = getattr(team, "goals_against", 0) or 0
        team_vals = {"points": pts, "wins": wins, "goals_for": gf,
                     "goal_differential": gf - ga}
        for cat, v in team_vals.items():
            if self._maybe_record(self.team_season_records, team_name,
                                  cat, v, team, season_label, label=team_name):
                new_records.append({"team": team_name, "type": "team_season",
                                    "category": cat, "value": v, "season": season_label})
        # Fewest goals against (lower is better)
        if self._maybe_record(self.team_season_records, team_name,
                              "goals_against", ga, team, season_label,
                              higher_is_better=False, label=team_name):
            new_records.append({"team": team_name, "type": "team_season",
                                "category": "goals_against", "value": ga,
                                "season": season_label})
        return new_records

    def record_streak(self, team_name: str, streak_type: str, length: int,
                      season_label: str) -> bool:
        """Record a win/unbeaten streak if it's a franchise best."""
        st = self.streaks.setdefault(team_name, {})
        cur = st.get(streak_type, {}).get("length", 0)
        if length > cur:
            st[streak_type] = {"length": length, "season": season_label}
            return True
        return False

    # -- queries for UI --

    def get_career_records(self, team_name: str) -> Dict[str, Dict[str, Any]]:
        return self.career_records.get(team_name, {})

    def get_season_records(self, team_name: str) -> Dict[str, Dict[str, Any]]:
        return self.season_records.get(team_name, {})

    def get_goalie_records(self, team_name: str) -> Dict[str, Dict[str, Any]]:
        return {"career": self.goalie_career_records.get(team_name, {}),
                "season": self.goalie_season_records.get(team_name, {})}

    def get_team_records(self, team_name: str) -> Dict[str, Dict[str, Any]]:
        recs = dict(self.team_season_records.get(team_name, {}))
        recs.update({f"streak_{k}": v for k, v in
                     self.streaks.get(team_name, {}).items()})
        return recs

    def all_teams(self) -> List[str]:
        teams = (set(self.career_records) | set(self.season_records) |
                 set(self.goalie_career_records) | set(self.team_season_records) |
                 set(self.franchise_career))
        return sorted(teams)

    # -- persistence --

    def to_dict(self) -> Dict[str, Any]:
        return {
            "franchise_career": self.franchise_career,
            "career_records": self.career_records,
            "season_records": self.season_records,
            "goalie_career_records": self.goalie_career_records,
            "goalie_season_records": self.goalie_season_records,
            "team_season_records": self.team_season_records,
            "streaks": self.streaks,
            "names": self._names,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FranchiseRecords":
        fr = cls()
        fr.franchise_career = data.get("franchise_career", {})
        fr.career_records = data.get("career_records", {})
        fr.season_records = data.get("season_records", {})
        fr.goalie_career_records = data.get("goalie_career_records", {})
        fr.goalie_season_records = data.get("goalie_season_records", {})
        fr.team_season_records = data.get("team_season_records", {})
        fr.streaks = data.get("streaks", {})
        fr._names = data.get("names", {})
        return fr

    # -- historical seeding (real NHL franchise records) --

    @staticmethod
    def _normalize_team_name(name: str) -> str:
        n = (name or "").strip().lower()
        n = n.replace("\u00e9", "e").replace("\u00e8", "e")
        return " ".join(n.split())

    def seed_historical_records(self, seed: dict) -> int:
        """Seed the record book with real NHL franchise history.

        `seed` maps team name -> {"season": {cat: (holder, value[, season])},
        "career": {...}, "goalie_season": {...}, "goalie_career": {...},
        "team_season": {cat: (value[, season])}}.

        Existing records are only overwritten when the seed value is
        strictly better, so simulated marks are never clobbered by weaker
        historical ones. Returns the number of teams seeded.
        """
        norm_seed = {self._normalize_team_name(k): v
                     for k, v in (seed or {}).items()}
        # Canonical team names already present (from simulated seasons)
        canon = {self._normalize_team_name(t): t
                 for t in list(self.career_records.keys())
                 + list(self.season_records.keys())}
        seeded = 0

        def _set(store, team, cat, value, holder, season,
                 higher_is_better=True):
            recs = store.setdefault(team, {})
            cur = recs.get(cat)
            beats = (cur is None or
                     (higher_is_better and value > cur["value"]) or
                     (not higher_is_better and value < cur["value"]))
            if beats:
                recs[cat] = {"value": value, "player": holder,
                             "season": season}
                return True
            return False

        for norm_name, data in norm_seed.items():
            team = canon.get(norm_name)
            if team is None:
                # No simulated history yet; use the seed's own team key
                # (find original key with this normalized form)
                orig = next((k for k in (seed or {})
                             if self._normalize_team_name(k) == norm_name),
                            norm_name)
                team = orig
            did_any = False
            for cat, tup in (data.get("season") or {}).items():
                holder, value = tup[0], tup[1]
                season = tup[2] if len(tup) > 2 else ""
                did_any |= _set(self.season_records, team, cat,
                                value, holder, season)
            for cat, tup in (data.get("career") or {}).items():
                holder, value = tup[0], tup[1]
                did_any |= _set(self.career_records, team, cat,
                                value, holder, "")
            for cat, tup in (data.get("goalie_season") or {}).items():
                holder, value = tup[0], tup[1]
                season = tup[2] if len(tup) > 2 else ""
                did_any |= _set(self.goalie_season_records, team, cat,
                                value, holder, season)
            for cat, tup in (data.get("goalie_career") or {}).items():
                holder, value = tup[0], tup[1]
                did_any |= _set(self.goalie_career_records, team, cat,
                                value, holder, "")
            for cat, tup in (data.get("team_season") or {}).items():
                value = tup[0] if isinstance(tup, (list, tuple)) else tup
                season = (tup[1] if isinstance(tup, (list, tuple))
                          and len(tup) > 1 else "")
                hib = cat not in ("fewest_ga",)
                did_any |= _set(self.team_season_records, team, cat,
                                value, "", season,
                                higher_is_better=hib)
            if did_any:
                seeded += 1
        return seeded
