# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Narrative ledger — one normalized event record for rivalries + history.

Wave 3 design ("a rivalry should be a memory, not a multiplier"):
Puck Dynasty already stores origins, heat, incidents and grudges in several
places (reputation_system rivalries, controversy incidents, headlines, league
history). The ledger does NOT replace those stores. It is the single
normalized record each audience (rivalry, media, fans, reputation, history,
inbox) can query: facts are stored once, and every audience interprets them
through `interpret()`.

Performance contract (Muck's constraint: no load-time / responsiveness cost):
- All writes are O(1) amortized; every read is an index lookup plus a scan of
  that pair's own short event list. Nothing here ever scans the full ledger.
- Hooks fire only at natural points (incident logged, series completed,
  pre-game check = one dict lookup per game). No per-tick work.
- The store is capped (MAX_EVENTS); old low-weight events roll up into a
  compact per-pair archive instead of growing the save file forever.
- Save/load is a flat list of small dicts; old saves load with an empty
  ledger (backfill without inventing, per the history integrity rules).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

MAX_EVENTS = 4000          # hard cap on full-detail events in memory/save
DETAIL_SEASONS = 3         # full detail kept for the last N seasons
ARCHIVE_MIN_WEIGHT = 40    # older events below this roll into the archive
CALLBACK_COOLDOWN_DAYS = 21  # an incident is referenced at most this often
MEMORY_WINDOW_DAYS = 150     # incidents older than this stop triggering callbacks
CALLBACK_MIN_WEIGHT = 25     # trivia never earns a "remember when"

KIND_INCIDENT = "incident"
KIND_PLAYOFF_SERIES = "playoff_series"
KIND_MILESTONE_WATCH = "milestone_watch"
KIND_MILESTONE = "milestone"
KIND_CEREMONY = "ceremony"

AUDIENCES = ("room", "fans", "media", "league")


# ---------------------------------------------------------------------------
# Module-level active ledger (bridge for code that can't reach the app)
# ---------------------------------------------------------------------------

_ACTIVE_LEDGER: Optional["NarrativeLedger"] = None


def set_active_ledger(ledger: Optional["NarrativeLedger"]) -> None:
    global _ACTIVE_LEDGER
    _ACTIVE_LEDGER = ledger


def active_ledger() -> Optional["NarrativeLedger"]:
    return _ACTIVE_LEDGER


def get_ledger(app: Any) -> "NarrativeLedger":
    """Lazily attach a ledger to the app (mirrors league_history)."""
    led = getattr(app, "narrative_ledger", None)
    if not isinstance(led, NarrativeLedger):
        led = NarrativeLedger()
        try:
            app.narrative_ledger = led
        except Exception:
            pass
    set_active_ledger(led)
    return led


# ---------------------------------------------------------------------------
# Interpretation: one event, four viewpoints
# ---------------------------------------------------------------------------

def incident_short(facts: Dict[str, Any]) -> str:
    kind = facts.get("incident_kind", "incident")
    perp = facts.get("perpetrator", "")
    victim = facts.get("victim", "")
    labels = {
        "controversial_hit": "the hit",
        "bad_call": "the disallowed goal",
        "brawl": "the brawl",
        "line_brawl": "the line brawl",
        "cheap_shot": "the cheap shot",
        "injury_hit": "the hit that injured",
    }
    base = labels.get(kind, "the incident")
    if perp and victim:
        return f"{base} ({perp} on {victim})"
    return base


def interpret(event: Dict[str, Any], audience: str,
              perspective_team: Optional[str] = None) -> Optional[str]:
    """Render one audience's read of a stored event. Facts in, story out.

    perspective_team: the team whose eyes we see through (usually the user's).
    Returns None when this audience has nothing to say (e.g. the league only
    speaks when the event is large enough).
    """
    if audience not in AUDIENCES:
        return None
    kind = event.get("kind")
    facts = event.get("facts") or {}
    weight = event.get("weight", 0)
    teams = event.get("teams") or []
    season = event.get("season")

    if kind == KIND_INCIDENT:
        short = incident_short(facts)
        mine_involved = perspective_team in teams if perspective_team else False
        perp_team = facts.get("perpetrator_team", "")
        if audience == "room":
            if not mine_involved:
                return None
            if perp_team and perp_team == perspective_team:
                return (f"The room loved it — {facts.get('perpetrator', 'our guy')} "
                        f"standing up for the crest. That's remembered in here.")
            return (f"The room hasn't forgotten {short}. "
                    f"Protection, not recklessness — that's the message.")
        if audience == "fans":
            if not mine_involved:
                return None
            if perp_team and perp_team == perspective_team:
                return (f"The fans still cheer {short} — hero stuff in this "
                        f"building.")
            return (f"The fans still boo {short} — villain stuff in this "
                    f"building.")
        if audience == "media":
            if weight >= 60:
                return (f"Rivalry fuel: {short} between "
                        f"{' and '.join(teams)} is the storyline tonight.")
            return (f"A footnote for the broadcast: {short} adds a little "
                    f"edge to {' vs '.join(teams)}.")
        if audience == "league":
            if weight >= 70:
                return ("The league office has this feud flagged — "
                        "reputation is on the line tonight.")
            return None

    elif kind == KIND_PLAYOFF_SERIES:
        winner = facts.get("winner", "")
        loser = facts.get("loser", "")
        games = facts.get("games", 0)
        rd = facts.get("round", "playoffs")
        bits = []
        if facts.get("sweep"):
            bits.append("a sweep")
        if facts.get("comeback"):
            bits.append(facts["comeback"])
        if facts.get("seven_games"):
            bits.append("a seven-game classic")
        if facts.get("upset"):
            bits.append("the upset")
        detail = ", ".join(bits) if bits else f"{games} games"
        yr = f" ({season})" if season else ""
        if audience == "media":
            return (f"Remember{yr}: {winner} took {loser} in {detail} — "
                    f"that's the history tonight.")
        if audience == "fans":
            if perspective_team == winner:
                return (f"The fans remember{yr} — {winner} ended {loser}'s "
                        f"season in {detail}. They want it again.")
            if perspective_team == loser:
                return (f"The fans remember{yr} — {loser} fell to {winner} in "
                        f"{detail}. They haven't forgiven it.")
            return None
        if audience == "room":
            if perspective_team in (winner, loser):
                return (f"The room knows the history: {winner} over {loser}, "
                        f"{detail}{yr}. Weight it by what actually happened.")
            return None
        if audience == "league":
            if weight >= 70:
                return (f"A series the league markets: {winner} vs {loser}, "
                        f"{detail}{yr}.")
            return None

    elif kind in (KIND_MILESTONE_WATCH, KIND_MILESTONE):
        player = facts.get("player", "")
        milestone = facts.get("milestone", "")
        if audience == "media":
            venue = facts.get("venue_note", "")
            return (f"Milestone watch: {player} closing in on {milestone}"
                    f"{' — ' + venue if venue else ''}.")
        if audience == "fans":
            return f"The building knows: {player} is closing in on {milestone}."
        return None

    elif kind == KIND_CEREMONY:
        desc = facts.get("description", "a ceremony")
        if audience in ("fans", "media"):
            return f"Tonight's ceremony: {desc}."
        return None

    return None


# ---------------------------------------------------------------------------
# Matchup narrative — one call for the schedule/calendar presentation layer
# ---------------------------------------------------------------------------

def matchup_narrative(home: Any, away: Any, league: Any = None,
                      ledger: Any = None) -> Dict[str, Any]:
    """Presentation metadata for a matchup from the four narrative systems.

    Reads (never writes): the rivalry store (league.rivalries heat), the
    narrative ledger (grudge memory + playoff-series history), and each
    club's iconic-games list (legacy rematches).

    Returns {"rivalry_heat", "mem_weight", "hype_tags", "marquee",
    "grudge", "iconic_headline"}. Thresholds mirror pregame_crowd and the
    playoff _compute_series_hype so the building, the bracket and the
    calendar tell one story. Never raises; missing inputs -> quiet neutral.
    """
    out: Dict[str, Any] = {
        "rivalry_heat": 0.0, "mem_weight": 0.0, "hype_tags": [],
        "marquee": False, "grudge": False, "iconic_headline": None,
    }
    try:
        n1 = getattr(home, "team_name", None) or str(home or "")
        n2 = getattr(away, "team_name", None) or str(away or "")
        if not n1 or not n2 or n1 == n2:
            return out
        heat = 0.0
        tags: List[str] = []
        # -- rivalry store -------------------------------------------------
        try:
            from reputation_system import get_rivalry_heat, rivalry_between
            rivalries = getattr(league, "rivalries", None) or []
            try:
                heat = float(get_rivalry_heat(rivalries, home, away)
                             .get("heat", 0.0) or 0.0)
            except Exception:
                heat = 0.0
            try:
                rec = rivalry_between(rivalries, home, away, "team_team")
                story = str((rec or {}).get("story", "") or "")
                if rec and (rec.get("origin") == "playoff_series"
                            or "Playoff series:" in story):
                    tags.append("Playoff rematch")
                    if "Seven games" in story:
                        tags.append("Seven-game war")
            except Exception:
                pass
        except Exception:
            pass
        # -- ledger: grudge memory smolders where the store is quiet ------
        mem = 0.0
        try:
            if ledger is not None:
                mem = float(ledger.memory_weight(n1, n2) or 0.0)
                if mem >= 70.0:
                    heat = max(heat, 65.0)
                try:
                    if ledger.series_history(n1, n2) \
                            and "Playoff rematch" not in tags:
                        tags.append("Playoff rematch")
                except Exception:
                    pass
        except Exception:
            pass
        if heat >= 65.0:
            tags.insert(0, "Bad blood")
        elif heat >= 35.0:
            tags.append("Heated rivalry")
        elif mem >= 40.0 and "Heated rivalry" not in tags:
            tags.append("History between these two")
        # -- iconic legacy: a past classic between these clubs ------------
        iconic_headline = None
        try:
            seen_pair = {n1, n2}
            for club in (home, away):
                for e in getattr(club, "iconic_games", None) or []:
                    try:
                        if not isinstance(e, dict):
                            continue
                        if {str(e.get("home", "")),
                                str(e.get("away", ""))} == seen_pair:
                            iconic_headline = str(
                                e.get("headline", "") or "") or None
                            break
                    except Exception:
                        continue
                if iconic_headline:
                    break
            if iconic_headline and "Iconic rematch" not in tags:
                tags.append("Iconic rematch")
        except Exception:
            pass
        # Dedupe while keeping order.
        seen = set()
        tags = [t for t in tags if not (t in seen or seen.add(t))]
        out.update(
            rivalry_heat=max(0.0, min(100.0, heat)),
            mem_weight=max(0.0, mem),
            hype_tags=tags,
            marquee=(heat >= 50.0) or ("Playoff rematch" in tags)
            or (iconic_headline is not None),
            grudge=(heat >= 35.0) or (mem >= 40.0),
            iconic_headline=iconic_headline)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Playoff-series memory
# ---------------------------------------------------------------------------

def record_playoff_series_memory(ledger: "NarrativeLedger",
                                 series: Any) -> Optional[Dict[str, Any]]:
    """Derive the defining beats of a completed series from its game log.

    Weight later tension by what actually happened, not "playoffs +20":
    sweeps, comebacks, seven-gamers, OT winners, goalie steals, upsets and
    blown leads are all read off the real per-game facts.
    """
    try:
        winner = getattr(series, "winner", None)
        if winner is None:
            return None
        t1 = getattr(series, "team1", None)
        t2 = getattr(series, "team2", None)
        wname = getattr(winner, "team_name", "")
        lteam = t2 if winner is t1 else t1
        lname = getattr(lteam, "team_name", "") if lteam is not None else ""
        if not wname or not lname:
            return None
        games = list(getattr(series, "game_results", None) or [])
        w_wins = int(getattr(series, "team1_wins", 0)
                     if winner is t1 else getattr(series, "team2_wins", 0))
        l_wins = int(getattr(series, "team2_wins", 0)
                     if winner is t1 else getattr(series, "team1_wins", 0))
        n_games = int(getattr(series, "games_played", 0)) or len(games)

        # Comeback: winner trailed 0-2 or 1-3 at any point (from game order).
        comeback = None
        w_seq, l_seq = 0, 0
        for g in games:
            if bool(g.get("team1_won")) == (winner is t1):
                w_seq += 1
            else:
                l_seq += 1
            if l_seq == 2 and w_seq == 0:
                comeback = "came back from 0-2 down"
            elif l_seq == 3 and w_seq == 1:
                comeback = "came back from 1-3 down"
        # Blown lead: loser led 2-0 or 3-1 and lost.
        blown = None
        w_seq, l_seq = 0, 0
        for g in games:
            if bool(g.get("team1_won")) == (winner is t1):
                w_seq += 1
            else:
                l_seq += 1
            if w_seq == 0 and l_seq == 2:
                blown = f"{lname} blew a 2-0 series lead"
            elif w_seq == 1 and l_seq == 3:
                blown = f"{lname} blew a 3-1 series lead"

        sweep = l_wins == 0 and n_games > 0
        seven = n_games >= 7
        ot_games = [g for g in games if g.get("ot")]
        steals = [g for g in games if g.get("goalie_steal")]

        # Upset: worse seed (higher standings_position) wins.
        upset = False
        try:
            wp = getattr(winner, "standings_position", 99) or 99
            lp = getattr(lteam, "standings_position", 99) or 99
            upset = int(wp) > int(lp)
        except Exception:
            pass

        beats: List[str] = []
        for g in games:
            gn = g.get("game", "?")
            gw = wname if (bool(g.get("team1_won")) == (winner is t1)) else lname
            score = f"{g.get('t1_score', '?')}-{g.get('t2_score', '?')}"
            if g.get("ot"):
                beats.append(f"Game {gn} went to OT — {gw} took it {score}")
            if g.get("goalie_steal"):
                beats.append(f"Game {gn}: goalie steal — {g['goalie_steal']}")
        if games:
            last = games[-1]
            beats.append(f"{wname} closed it out in Game {last.get('game', n_games)}")
        if blown:
            beats.append(blown)

        weight = 40
        if seven:
            weight += 12
        if comeback:
            weight += 12
        if upset:
            weight += 10
        if sweep:
            weight += 4
        weight += min(10, 4 * len(ot_games))
        if "Final" in str(getattr(series, "round_name", "")):
            weight += 10
        weight = max(0, min(95, weight))

        facts = {
            "round": str(getattr(series, "round_name", "playoffs")),
            "winner": wname, "loser": lname,
            "games": n_games, "score": f"{w_wins}-{l_wins}",
            "sweep": sweep, "seven_games": seven,
            "comeback": comeback, "blown_lead": blown,
            "upset": upset, "ot_games": len(ot_games),
            "beats": beats,
        }
        text = (f"{wname} beat {lname} {w_wins}-{l_wins} "
                f"({facts['round']})")
        return ledger.record(KIND_PLAYOFF_SERIES, teams=[wname, lname],
                             facts=facts, weight=weight, text=text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

class NarrativeLedger:
    """Append-only, indexed, capped store of normalized narrative events."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []
        self._by_id: Dict[int, Dict[str, Any]] = {}
        self._by_pair: Dict[Tuple[str, str], List[int]] = {}
        self._by_player: Dict[str, List[int]] = {}
        self._by_kind: Dict[str, List[int]] = {}
        # (pair_key, kind) -> {count, first_season, last_season, max_weight, note}
        self.archive: Dict[str, Dict[str, Any]] = {}
        self._seq = 0
        self.season: Optional[int] = None
        self.day: int = 0  # days since season start; drives cooldowns

    # -- clock ------------------------------------------------------------
    def set_clock(self, season: Optional[int], day: int) -> None:
        self.season = season
        self.day = day

    # -- keys -------------------------------------------------------------
    @staticmethod
    def _pair_key(a: str, b: str) -> Tuple[str, str]:
        a, b = (a or ""), (b or "")
        return (a, b) if a <= b else (b, a)

    # -- writes -----------------------------------------------------------
    def record(self, kind: str, teams: Optional[List[str]] = None,
               players: Optional[List[str]] = None,
               facts: Optional[Dict[str, Any]] = None,
               weight: int = 30, text: str = "",
               season: Optional[int] = None,
               day: Optional[int] = None) -> Dict[str, Any]:
        """Append one normalized event. O(1) amortized."""
        self._seq += 1
        eid = self._seq
        teams = [t for t in (teams or []) if t]
        players = [p for p in (players or []) if p]
        ev = {
            "id": eid,
            "kind": kind,
            "season": season if season is not None else self.season,
            "day": day if day is not None else self.day,
            "teams": teams,
            "players": players,
            "facts": dict(facts or {}),
            "weight": max(0, min(100, int(weight))),
            "text": text,
            "last_callback_day": None,
            "ref_count": 0,
        }
        self.events.append(ev)
        self._by_id[eid] = ev
        if len(teams) >= 2:
            key = self._pair_key(teams[0], teams[1])
            self._by_pair.setdefault(key, []).append(eid)
        elif len(teams) == 1:
            self._by_pair.setdefault((teams[0], ""), []).append(eid)
        for p in players:
            self._by_player.setdefault(p, []).append(eid)
        self._by_kind.setdefault(kind, []).append(eid)
        if len(self.events) > MAX_EVENTS:
            self._prune_overflow()
        return ev

    def mark_referenced(self, event_id: int) -> None:
        ev = self._by_id.get(event_id)
        if ev is not None:
            ev["last_callback_day"] = self.day
            ev["ref_count"] = ev.get("ref_count", 0) + 1

    # -- reads (all index-backed) ------------------------------------------
    def _pair_events(self, a: str, b: str) -> List[Dict[str, Any]]:
        ids = self._by_pair.get(self._pair_key(a, b), [])
        return [self._by_id[i] for i in ids if i in self._by_id]

    def between(self, team_a: str, team_b: str,
                kinds: Optional[List[str]] = None,
                min_weight: int = 0) -> List[Dict[str, Any]]:
        """Newest-first events between two teams. Index lookup + short scan."""
        evs = self._pair_events(team_a, team_b)
        if kinds:
            kset = set(kinds)
            evs = [e for e in evs if e.get("kind") in kset]
        if min_weight:
            evs = [e for e in evs if e.get("weight", 0) >= min_weight]
        evs.sort(key=lambda e: (e.get("season") or 0, e.get("day") or 0,
                                e.get("id") or 0), reverse=True)
        return evs

    def memory_weight(self, team_a: str, team_b: str) -> float:
        """Total ledger weight between two teams, 0-100.

        Used by arena_atmosphere (bad-blood buildings) and outdoor-game
        host selection. Saturates: one big incident lands ~35-55, a real
        feud with several entries pins toward 100.
        """
        try:
            total = sum(float(e.get("weight", 0) or 0)
                        for e in self._pair_events(team_a, team_b))
        except Exception:
            return 0.0
        if total <= 0:
            return 0.0
        return min(100.0, total / (1.0 + total / 120.0))

    def latest_incident(self, team_a: str, team_b: str) -> Optional[Dict[str, Any]]:
        evs = self.between(team_a, team_b, kinds=[KIND_INCIDENT])
        return evs[0] if evs else None

    def series_history(self, team_a: str, team_b: str) -> List[Dict[str, Any]]:
        """The playoff memory between two teams, newest first."""
        return self.between(team_a, team_b, kinds=[KIND_PLAYOFF_SERIES])

    def for_player(self, name: str,
                   kinds: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        ids = self._by_player.get(name or "", [])
        evs = [self._by_id[i] for i in ids if i in self._by_id]
        if kinds:
            kset = set(kinds)
            evs = [e for e in evs if e.get("kind") in kset]
        evs.sort(key=lambda e: (e.get("season") or 0, e.get("day") or 0,
                                e.get("id") or 0), reverse=True)
        return evs

    def callback_candidate(self, team_a: str, team_b: str) -> Optional[Dict[str, Any]]:
        """Newest incident worth a 'remember when' — honoring cooldowns.

        Returns None when there is nothing fresh, nothing weighty, or the
        last reference is still inside the cooldown window (history should
        feel remembered, not repeated).
        """
        ev = self.latest_incident(team_a, team_b)
        if ev is None or ev.get("weight", 0) < CALLBACK_MIN_WEIGHT:
            return None
        ev_day = ev.get("day")
        if ev_day is not None and (self.day - ev_day) > MEMORY_WINDOW_DAYS:
            return None
        last = ev.get("last_callback_day")
        if last is not None and (self.day - last) < CALLBACK_COOLDOWN_DAYS:
            return None
        return ev

    def rivalry_summary(self, team_a: str, team_b: str) -> Dict[str, Any]:
        """Compact memory card: what these two teams actually did to each other."""
        evs = self.between(team_a, team_b)
        series = [e for e in evs if e.get("kind") == KIND_PLAYOFF_SERIES]
        incidents = [e for e in evs if e.get("kind") == KIND_INCIDENT]
        pair_key = "|".join(self._pair_key(team_a, team_b))
        archived = sum(1 for k in self.archive
                       if k.startswith(pair_key + "|"))
        return {
            "events": len(evs),
            "playoff_series": len(series),
            "incidents": len(incidents),
            "archived_older": archived,
            "latest": evs[0] if evs else None,
        }

    # -- pruning ------------------------------------------------------------
    def _archive_event(self, ev: Dict[str, Any]) -> None:
        teams = ev.get("teams") or []
        pair = "|".join(self._pair_key(teams[0] if len(teams) > 0 else "",
                                      teams[1] if len(teams) > 1 else ""))
        key = f"{pair}|{ev.get('kind')}"
        slot = self.archive.get(key)
        season = ev.get("season")
        if slot is None:
            self.archive[key] = slot = {
                "count": 0, "first_season": season, "last_season": season,
                "max_weight": 0, "note": ev.get("text", "")[:120],
            }
        slot["count"] += 1
        if season is not None:
            if slot["first_season"] is None or season < slot["first_season"]:
                slot["first_season"] = season
            if slot["last_season"] is None or season > slot["last_season"]:
                slot["last_season"] = season
        slot["max_weight"] = max(slot["max_weight"], ev.get("weight", 0))

    def _drop_event(self, ev: Dict[str, Any]) -> None:
        eid = ev.get("id")
        self._by_id.pop(eid, None)
        teams = ev.get("teams") or []
        if len(teams) >= 2:
            key = self._pair_key(teams[0], teams[1])
        elif teams:
            key = (teams[0], "")
        else:
            key = None
        if key is not None:
            lst = self._by_pair.get(key)
            if lst:
                try:
                    lst.remove(eid)
                except ValueError:
                    pass
        for p in ev.get("players") or []:
            lst = self._by_player.get(p)
            if lst:
                try:
                    lst.remove(eid)
                except ValueError:
                    pass
        lst = self._by_kind.get(ev.get("kind"))
        if lst:
            try:
                lst.remove(eid)
            except ValueError:
                pass

    def _prune_overflow(self) -> None:
        """Cap enforcement: roll the oldest low-weight events into the archive."""
        over = len(self.events) - MAX_EVENTS
        if over <= 0:
            return
        # Oldest first, lowest weight first — the memorable survives.
        cands = sorted(self.events, key=lambda e: (e.get("weight", 0),
                                                   e.get("id", 0)))
        for ev in cands[:over]:
            self._archive_event(ev)
            self._drop_event(ev)
            try:
                self.events.remove(ev)
            except ValueError:
                pass

    def advance_season(self, new_season: int) -> None:
        """Season rollover: keep full detail for recent/high-weight events."""
        cutoff = new_season - DETAIL_SEASONS
        for ev in list(self.events):
            season = ev.get("season")
            if season is not None and season < cutoff \
                    and ev.get("weight", 0) < ARCHIVE_MIN_WEIGHT:
                self._archive_event(ev)
                self._drop_event(ev)
                try:
                    self.events.remove(ev)
                except ValueError:
                    pass
        self.season = new_season
        self.day = 0

    # -- persistence ----------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self._seq,
            "season": self.season,
            "day": self.day,
            "events": self.events,
            "archive": self.archive,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "NarrativeLedger":
        led = cls()
        if not isinstance(data, dict):
            return led
        try:
            led._seq = int(data.get("seq", 0) or 0)
            led.season = data.get("season")
            led.day = int(data.get("day", 0) or 0)
            led.archive = dict(data.get("archive") or {})
            for ev in data.get("events") or []:
                if not isinstance(ev, dict):
                    continue
                eid = ev.get("id")
                if eid is None:
                    continue
                led.events.append(ev)
                led._by_id[eid] = ev
                teams = ev.get("teams") or []
                if len(teams) >= 2:
                    key = cls._pair_key(teams[0], teams[1])
                elif teams:
                    key = (teams[0], "")
                else:
                    key = None
                if key is not None:
                    led._by_pair.setdefault(key, []).append(eid)
                for p in ev.get("players") or []:
                    led._by_player.setdefault(p, []).append(eid)
                led._by_kind.setdefault(ev.get("kind"), []).append(eid)
        except Exception:
            return cls()
        return led

    def __len__(self) -> int:
        return len(self.events)
