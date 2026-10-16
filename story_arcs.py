# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Multi-day story arcs (R10) -- Press Box storylines with real resolutions.

A Press Box story that implies a future opens an ARC in the narrative
ledger the moment the story fires:

    hot-seat story      -> fired / retained
    trade-rumor story   -> traded / stayed put
    milestone countdown -> milestone achieved
    injury report       -> returned to the lineup

A daily scan re-reads REAL engine state (the coach carousel, completed-
trade logs, career stats, injury flags) and, when the future arrives,
emits a follow-up story through the normal Press Box path.

Design rules (house style):
- Initiation is a pure function of the story firing. note_story_fired()
  never consults resolvability: ALL hot-seat stories open arcs, even ones
  that will obviously end "retained"; rumor arcs open even if no trade
  ever happens.
- Resolution is read off engine objects, never invented. Every detector
  fails closed: if the premise cannot be proved from engine state, the
  arc stays open (or expires silently) -- a follow-up is never emitted
  on a guess.
- Follow-ups are one-shot per arc (ledger status machine plus a 400-day
  one-shot mark in _daily_news_recent), surface within 14 game-days of
  the resolving event, and pass the same Unknown-entity post-render
  guard as every other Press Box story.
- One story per (game, player): re-firings of the initiating story while
  its arc is open do not open duplicate arcs.
- Nothing here ever raises.
"""

from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from narrative_ledger import (
    ARC_KIND_HOT_SEAT,
    ARC_KIND_INJURY,
    ARC_KIND_MILESTONE,
    ARC_KIND_TRADE_RUMOR,
    ARC_KINDS,
    get_ledger,
)

_log = logging.getLogger("story_arcs")

# -- tuning ---------------------------------------------------------------
# Days a hot-seat coach must survive before the arc resolves "retained".
HOT_SEAT_HEAT_WINDOW_DAYS = 21
# Follow-ups must surface within this many game-days of the resolving event.
ARC_FOLLOWUP_WINDOW_DAYS = 14
# Open/resolved arcs older than this (by opened date) are expired silently.
ARC_EXPIRE_DAYS = 400
# One-shot marks for delivered follow-ups (longer than any season).
ARC_FOLLOWUP_MARK_WINDOW = 400

_UNKNOWN_MARKERS = ("Unknown Player", "Unknown Team")


# ---------------------------------------------------------------------------
# Small safe helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _iso(v) -> str:
    try:
        if isinstance(v, datetime):
            return v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        if hasattr(v, "isoformat"):
            return v.isoformat()[:10]
    except Exception:
        pass
    return ""


def _parse_iso_date(v) -> Optional[date]:
    try:
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        s = str(v or "").strip()[:10]
        return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except Exception:
        return None


def _clean_name(v) -> str:
    """Display name, or '' when it is missing or a placeholder."""
    s = str(v or "").strip()
    if not s:
        return ""
    for m in _UNKNOWN_MARKERS:
        if m in s:
            return ""
    if s.lower() in ("unknown", "none"):
        return ""
    return s


def _iter_teams(app) -> List[Any]:
    try:
        gm = getattr(app, "game_manager", None)
        league = (getattr(gm, "league", None)
                  if gm is not None else None) or getattr(app, "league", None)
        return list(getattr(league, "teams", None) or []) or []
    except Exception:
        return []


def _team_name_of(t) -> str:
    return _clean_name(_safe(lambda: t.team_name, ""))


def _find_player(app, player_id) -> Tuple[Optional[Any], Optional[Any]]:
    """(player, team) for a stored player id across all league rosters."""
    if player_id is None:
        return None, None
    try:
        want = str(player_id)
        for t in _iter_teams(app):
            for p in getattr(t, "roster", None) or []:
                try:
                    pid = getattr(p, "id", None)
                    if pid is None or str(pid) != want:
                        continue
                    return p, t
                except Exception:
                    continue
    except Exception:
        pass
    return None, None


def _trade_history(app) -> List[Any]:
    try:
        gm = getattr(app, "game_manager", None)
        src = gm if gm is not None else app
        return list(getattr(src, "trade_history", None) or [])
    except Exception:
        return []


def _parse_trade_date(v) -> Optional[date]:
    try:
        from daily_news import _td_parse_trade_date
        return _td_parse_trade_date(v)
    except Exception:
        return None


def _trade_deadline(app) -> Optional[date]:
    try:
        from daily_news import _td_deadline
        return _td_deadline(app)
    except Exception:
        return None


def _current_coach_name(app, team_name: str) -> str:
    """Whoever holds the head-coach chair for team_name right now.

    Reads the same chair the hot-seat bucket reads (daily_news._head_coach
    over team.staff), with a fallback to the dressing-room layout
    (team.head_coach). '' when the chair is empty or the team is unknown.
    """
    if not team_name:
        return ""
    try:
        from daily_news import _head_coach, _coach_name
        for t in _iter_teams(app):
            try:
                if _team_name_of(t) != team_name:
                    continue
                name = _clean_name(_coach_name(_head_coach(t)))
                if name:
                    return name
                c = getattr(t, "head_coach", None)
                if c is not None:
                    n = (getattr(c, "name", None)
                         or getattr(c, "full_name", None))
                    if _clean_name(n):
                        return _clean_name(n)
                    full = (f"{getattr(c, 'first_name', '') or ''} "
                            f"{getattr(c, 'last_name', '') or ''}").strip()
                    if _clean_name(full):
                        return _clean_name(full)
                return ""
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _career_goals(p) -> Optional[int]:
    """Career goal total, mirroring _milestone_watch's read order."""
    try:
        career = getattr(p, "career_stats", None)
        v = getattr(career, "goals", None) if career is not None else None
        if v is None:
            v = getattr(p, "career_goals", None)
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _injury_resolved(p) -> bool:
    """True only when the engine's own healed state holds: not flagged
    injured, no games remaining, off IR/LTIR. Mirrors the fields
    _heal_injured_player clears."""
    try:
        if bool(getattr(p, "is_injured", False)):
            return False
        try:
            remaining = int(getattr(p, "games_remaining_injured", 0) or 0)
        except Exception:
            remaining = 0
        if remaining > 0:
            return False
        ir = str(getattr(p, "ir_status", "") or "").upper()
        if ir in ("IR", "LTIR"):
            return False
        return True
    except Exception:
        return False


def _carousel_fired_date(coach_name: str,
                         opened: Optional[date]) -> Optional[date]:
    """The engine's own firing record for this coach on/after the arc's
    opened date, or None.

    Source: dressing_room.COACH_CAROUSEL, written by fire_coach() with
    reason="fired" and an ISO date. An undated or pre-arc entry is NOT a
    usable record -- fail closed (the detector treats it as unprovable).
    dressing_room is imported lazily: it needs a UI toolkit at module
    import, so a hard import would break headless use.
    """
    if not coach_name:
        return None
    try:
        import dressing_room as _dr
        carousel = getattr(_dr, "COACH_CAROUSEL", None) or []
    except Exception:
        return None
    try:
        for e in carousel:
            try:
                if not isinstance(e, dict):
                    continue
                if str(e.get("name") or "") != coach_name:
                    continue
                if str(e.get("reason") or "") != "fired":
                    continue
                d = _parse_iso_date(e.get("date"))
                if d is None:
                    continue
                if opened is not None and d < opened:
                    continue  # a firing from before this arc's story
                return d
            except Exception:
                continue
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Initiation -- a pure function of the story firing
# ---------------------------------------------------------------------------

def _initiation_facts_ok(arc_kind: str, facts: Dict[str, Any]) -> bool:
    """Minimum viable identity for an arc. This is about the STORY's own
    data being usable (real names, real ids) -- never about whether a
    resolution looks likely."""
    try:
        if arc_kind == ARC_KIND_HOT_SEAT:
            return bool(_clean_name(facts.get("coach_name"))
                        and _clean_name(facts.get("team_name")))
        if arc_kind == ARC_KIND_TRADE_RUMOR:
            return (bool(_clean_name(facts.get("player_name")))
                    and bool(_clean_name(facts.get("team_name")))
                    and facts.get("player_id") is not None)
        if arc_kind == ARC_KIND_MILESTONE:
            try:
                mark = int(facts.get("mark"))
            except Exception:
                return False
            return (bool(_clean_name(facts.get("player_name")))
                    and bool(_clean_name(facts.get("team_name")))
                    and facts.get("player_id") is not None
                    and mark > 0)
        if arc_kind == ARC_KIND_INJURY:
            try:
                out = int(facts.get("games_out"))
            except Exception:
                return False
            return (bool(_clean_name(facts.get("player_name")))
                    and bool(_clean_name(facts.get("team_name")))
                    and facts.get("player_id") is not None
                    and out >= 1)
    except Exception:
        return False
    return False


def note_story_fired(app: Any, arc_kind: str, entity_key: str,
                     facts: Optional[Dict[str, Any]],
                     game_date: Any) -> Optional[Dict[str, Any]]:
    """Open an arc for a fired Press Box story.

    Called by the story buckets at the moment they fire. The decision is a
    pure function of the firing: resolvability is never consulted, so ALL
    hot-seat stories open arcs (even ones that will end "retained") and
    rumor arcs open even when no trade ever happens. Never raises.
    """
    try:
        if arc_kind not in ARC_KINDS:
            return None
        facts = dict(facts or {})
        if not _initiation_facts_ok(arc_kind, facts):
            return None
        facts.setdefault("opened_date", _iso(game_date))
        ledger = get_ledger(app)
        return ledger.open_arc(str(arc_kind), str(entity_key or ""),
                               facts=facts)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Resolution detection -- read off real engine state, fail closed
# ---------------------------------------------------------------------------

def _arc_opened_date(arc: Dict[str, Any]) -> Optional[date]:
    return _parse_iso_date((arc.get("facts") or {}).get("opened_date"))


def _arc_age_days(arc: Dict[str, Any], game_date: date) -> int:
    opened = _arc_opened_date(arc)
    if opened is None:
        return 0
    try:
        return (game_date - opened).days
    except Exception:
        return 0


def _detect_hot_seat(app, arc, game_date):
    """hot-seat -> fired / retained (past the heat window).

    Fired is proved by the engine's own firing record (COACH_CAROUSEL,
    dated on/after the arc opened) while the chair no longer holds him.
    Retained is proved by the same coach still holding the chair past the
    heat window. A turned-over chair with no provable firing expires the
    arc silently -- asserting either outcome would be a guess.
    Returns ("resolve", resolution, facts) | ("expire",) | None.
    """
    f = arc.get("facts") or {}
    coach = _clean_name(f.get("coach_name"))
    team = _clean_name(f.get("team_name"))
    if not coach or not team:
        return ("expire",)
    opened = _arc_opened_date(arc)
    fired_on = _carousel_fired_date(coach, opened)
    chair = _current_coach_name(app, team)
    if fired_on is not None and chair != coach:
        return ("resolve", "fired", {
            "coach_name": coach, "team_name": team,
            "fired_date": fired_on.isoformat(),
            "wins": f.get("wins"), "losses": f.get("losses"),
            "otl": f.get("otl")})
    if chair == coach:
        age = _arc_age_days(arc, game_date)
        if age >= HOT_SEAT_HEAT_WINDOW_DAYS:
            return ("resolve", "retained", {
                "coach_name": coach, "team_name": team, "days": age,
                "wins": f.get("wins"), "losses": f.get("losses"),
                "otl": f.get("otl")})
        return None
    return ("expire",)


def _detect_trade_rumor(app, arc, game_date):
    """rumor -> traded (real completed-trade log) / stayed (deadline passed
    with the player still on the club).

    A trade counts only when the completed-trade record is dated on/after
    the arc opened, names the player in the assets moved, and involves his
    club at rumor time. "Stayed" requires the deadline to have passed AND
    the player to still be on the same club -- a player who left by other
    means expires silently rather than earning a false "stayed".
    """
    f = arc.get("facts") or {}
    player = _clean_name(f.get("player_name"))
    team = _clean_name(f.get("team_name"))
    if not player or not team:
        return ("expire",)
    opened = _arc_opened_date(arc)
    for tr in _trade_history(app):
        try:
            a = str(getattr(tr, "team_a", "") or "").strip()
            b = str(getattr(tr, "team_b", "") or "").strip()
            if not a or not b:
                continue
            gave = [str(x or "")
                    for x in (getattr(tr, "a_gave", None) or [])]
            gave += [str(x or "")
                     for x in (getattr(tr, "b_gave", None) or [])]
            if player not in gave:
                continue
            if team not in (a, b):
                continue  # not his club's deal (duplicate-name guard)
            d = _parse_trade_date(getattr(tr, "date", None))
            if d is None:
                continue
            if opened is not None and d < opened:
                continue
            try:
                if d > game_date:
                    continue
            except Exception:
                continue
            new_team = b if a == team else a
            if not _clean_name(new_team):
                continue
            return ("resolve", "traded", {
                "player_name": player, "old_team": team,
                "new_team": new_team, "trade_date": d.isoformat()})
        except Exception:
            continue
    deadline = _trade_deadline(app)
    if deadline is not None:
        try:
            past = game_date > deadline
        except Exception:
            past = False
        if past:
            p, pt = _find_player(app, f.get("player_id"))
            if p is not None and pt is not None \
                    and _team_name_of(pt) == team:
                return ("resolve", "stayed", {
                    "player_name": player, "team_name": team,
                    "deadline": deadline.isoformat()})
            return ("expire",)
    return None


def _detect_milestone(app, arc, game_date):
    """milestone countdown -> achieved (career total reaches the mark)."""
    f = arc.get("facts") or {}
    player = _clean_name(f.get("player_name"))
    try:
        mark = int(f.get("mark"))
    except Exception:
        return ("expire",)
    if not player or mark <= 0:
        return ("expire",)
    p, t = _find_player(app, f.get("player_id"))
    if p is None:
        return None  # off-roster for now; wait rather than mis-expire
    total = _career_goals(p)
    if total is None:
        return None
    if total >= mark:
        team = _team_name_of(t) or _clean_name(f.get("team_name"))
        return ("resolve", "achieved", {
            "player_name": player, "team_name": team,
            "mark": mark, "total": total})
    return None


def _detect_injury(app, arc, game_date):
    """injury -> returned (the engine's own healed state)."""
    f = arc.get("facts") or {}
    if not _clean_name(f.get("player_name")):
        return ("expire",)
    p, t = _find_player(app, f.get("player_id"))
    if p is None:
        return None
    if _injury_resolved(p):
        team = _team_name_of(t) or _clean_name(f.get("team_name"))
        return ("resolve", "returned", {
            "player_name": _clean_name(f.get("player_name")),
            "team_name": team,
            "injury_type": _clean_name(f.get("injury_type")) or "injury"})
    return None


_DETECTORS = {
    ARC_KIND_HOT_SEAT: _detect_hot_seat,
    ARC_KIND_TRADE_RUMOR: _detect_trade_rumor,
    ARC_KIND_MILESTONE: _detect_milestone,
    ARC_KIND_INJURY: _detect_injury,
}


def _detect_resolution(app, arc, game_date):
    try:
        kind = (arc.get("facts") or {}).get("arc_kind")
        det = _DETECTORS.get(kind)
        if det is None:
            return ("expire",)
        return det(app, arc, game_date)
    except Exception:
        return None


def process_day(app: Any, game_date: date) -> int:
    """Daily arc scan: detect resolutions from real engine state, expire
    stale arcs. Returns the number of arcs resolved. Never raises."""
    n = 0
    try:
        ledger = get_ledger(app)
        for arc in ledger.open_arcs():
            try:
                outcome = _detect_resolution(app, arc, game_date)
            except Exception:
                outcome = None
            try:
                arc_id = arc.get("id")
                if outcome is None:
                    if _arc_age_days(arc, game_date) > ARC_EXPIRE_DAYS:
                        ledger.expire_arc(arc_id)
                elif outcome[0] == "resolve":
                    _, resolution, res_facts = outcome
                    ledger.resolve_arc(arc_id, resolution,
                                       _iso(game_date), res_facts or {})
                    n += 1
                elif outcome[0] == "expire":
                    ledger.expire_arc(arc_id)
            except Exception:
                continue
    except Exception:
        pass
    return n


# ---------------------------------------------------------------------------
# Follow-up stories -- through the normal Press Box path
# ---------------------------------------------------------------------------

_FOLLOWUP_MARK_TYPE = {
    ARC_KIND_HOT_SEAT: "arc_hot_seat",
    ARC_KIND_TRADE_RUMOR: "arc_trade_rumor",
    ARC_KIND_MILESTONE: "arc_milestone",
    ARC_KIND_INJURY: "arc_injury",
}

_FOLLOWUP_TEMPLATES = {
    ("hot_seat", "fired"): [
        "COACHING CHANGE: {coach} is out in {team} -- the hot-seat chatter proved prophetic.",
        "{team} has fired {coach}. This space had him on the hot seat at {w}-{l}-{otl} -- the board finally acted.",
        "The axe falls in {team}: {coach} is out after weeks of speculation about his job.",
        "COACHING CHANGE: {coach}'s time in {team} is over -- the {w}-{l}-{otl} slide cost him his job.",
        "It was only a matter of time: {team} fires {coach}, who had been coaching for his job for weeks.",
        "{coach} is done in {team}. The hot-seat talk is over -- so is his tenure.",
        "COACHING CHANGE: {team} pulls the plug on the {coach} era at {w}-{l}-{otl}.",
        "The {team} board ran out of patience: {coach} fired after the {w}-{l}-{otl} start.",
        "COACHING CHANGE: {coach} never survived the speculation in {team} -- he's out.",
        "{w}-{l}-{otl} was enough for the {team} board -- {coach} has been let go.",
    ],
    ("hot_seat", "retained"): [
        "VOTE OF CONFIDENCE: {team} is sticking with {coach} -- {weeks} after the hot-seat talk, he's still behind the bench.",
        "{coach} survives in {team}: the board is standing by its coach despite the {w}-{l}-{otl} noise.",
        "The hot seat cools in {team} -- {coach} is still the coach {weeks} after the speculation peaked.",
        "VOTE OF CONFIDENCE: {team} brass back {coach} to turn the {w}-{l}-{otl} start around.",
        "{coach} lives to coach another day in {team} -- no change behind the bench.",
        "Despite weeks of hot-seat chatter, {team} keeps {coach}. The message: fix it with this group.",
        "VOTE OF CONFIDENCE: {coach} gets more runway in {team} -- the board isn't blinking.",
        "The {team} room still answers to {coach} -- {weeks} of speculation, no firing.",
    ],
    ("trade_rumor", "traded"): [
        "DONE DEAL: {player} is on the move -- {old_team} dealt him to {new_team}. The rumor mill called this one.",
        "{player} has a new home: {new_team} acquires him from {old_team}. Remember the speculation? Called it.",
        "DONE DEAL: The {player} rumors are over -- he's a {new_team} player now, via {old_team}.",
        "{old_team} pulls the trigger: {player} is headed to {new_team}.",
        "DONE DEAL: {player} to {new_team} -- the weeks of {old_team} speculation end with a trade.",
        "It's official: {player} goes from {old_team} to {new_team}.",
        "DONE DEAL: {new_team} lands {player} from {old_team} -- the rumor mill's biggest fish is caught.",
        "{player}'s {old_team} tenure is over -- he's been dealt to {new_team}.",
    ],
    ("trade_rumor", "stayed"): [
        "STAYING PUT: {player} is still a {team} player -- the deadline passed without a deal despite the speculation.",
        "No deal for {player}: the {team} star survives the deadline amid weeks of rumors.",
        "STAYING PUT: {team} keeps {player}. The rumor mill goes hungry this time.",
        "{player} stays in {team} -- all that speculation, no trade.",
        "STAYING PUT: The deadline came and went, and {player} is still wearing {team} colors.",
        "{team} holds onto {player} past the deadline -- the rumors never materialized.",
    ],
    ("milestone_countdown", "achieved"): [
        "MILESTONE: {player} has done it -- {mark} career goals. The countdown is over in {team}.",
        "{player} reaches {mark} career goals for {team} -- now sitting at {total}. History made.",
        "MILESTONE: The {team} faithful get their moment -- {player}'s {mark}th career goal is in the books.",
        "It's done: {player} ({team}) joins the {mark}-goal club with career goal number {total}.",
        "MILESTONE: {player} etches his name in -- {mark} career goals, sealed in {team} colors.",
        "The wait is over in {team}: {player} scores career goal {mark} (now at {total}).",
    ],
    ("injury", "returned"): [
        "BACK IN THE LINEUP: {player} is back for {team} after missing time with {injury_type}.",
        "{player} returns for {team} -- the {injury_type} is behind him.",
        "BACK IN THE LINEUP: {team} gets {player} back from the {injury_type}.",
        "{team}'s lineup is whole again: {player} is back after the {injury_type}.",
        "BACK IN THE LINEUP: {player} is good to go for {team} -- {injury_type} fully healed.",
        "The {injury_type} didn't keep him down long: {player} is back in the {team} lineup.",
    ],
}


def _followup_context(arc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Format values for the follow-up template, or None when any named
    fact is unusable. Never asserts what the engine can't prove: every
    value comes from the arc record (the initiating story's own facts)
    or the detected resolution's facts."""
    try:
        f = arc.get("facts") or {}
        kind = f.get("arc_kind")
        res = f.get("resolution")
        coach = _clean_name(f.get("coach_name"))
        player = _clean_name(f.get("player_name"))
        team = _clean_name(f.get("team_name"))
        if kind == ARC_KIND_HOT_SEAT and res == "fired":
            if not (coach and team):
                return None
            try:
                w, l, otl = int(f.get("wins", 0)), int(f.get("losses", 0)), \
                    int(f.get("otl", 0))
            except Exception:
                return None
            return {"coach": coach, "team": team, "w": w, "l": l,
                    "otl": otl}
        if kind == ARC_KIND_HOT_SEAT and res == "retained":
            if not (coach and team):
                return None
            try:
                w, l, otl = int(f.get("wins", 0)), int(f.get("losses", 0)), \
                    int(f.get("otl", 0))
                days = int(f.get("days", HOT_SEAT_HEAT_WINDOW_DAYS))
            except Exception:
                return None
            weeks = max(1, days // 7)
            return {"coach": coach, "team": team, "w": w, "l": l,
                    "otl": otl, "weeks": weeks,
                    "weeks_word": "week" if weeks == 1 else "weeks"}
        if kind == ARC_KIND_TRADE_RUMOR and res == "traded":
            old = _clean_name(f.get("old_team"))
            new = _clean_name(f.get("new_team"))
            if not (player and old and new):
                return None
            return {"player": player, "old_team": old, "new_team": new}
        if kind == ARC_KIND_TRADE_RUMOR and res == "stayed":
            if not (player and team):
                return None
            return {"player": player, "team": team}
        if kind == ARC_KIND_MILESTONE and res == "achieved":
            try:
                mark, total = int(f.get("mark")), int(f.get("total"))
            except Exception:
                return None
            if not (player and team) or mark <= 0 or total < mark:
                return None
            return {"player": player, "team": team, "mark": mark,
                    "total": total}
        if kind == ARC_KIND_INJURY and res == "returned":
            if not (player and team):
                return None
            return {"player": player, "team": team,
                    "injury_type": _clean_name(f.get("injury_type"))
                    or "injury"}
    except Exception:
        return None
    return None


def _render_followup(arc: Dict[str, Any], rng) -> Optional[str]:
    try:
        f = arc.get("facts") or {}
        key = (f.get("arc_kind"), f.get("resolution"))
        tpls = _FOLLOWUP_TEMPLATES.get(key) or []
        if not tpls:
            return None
        ctx = _followup_context(arc)
        if ctx is None:
            return None
        return rng.choice(tpls).format(**ctx)
    except Exception:
        return None


def deliver_followups(app: Any, game_date: date) -> int:
    """Emit follow-ups for resolved arcs through the Press Box path.

    Each follow-up passes the Unknown-entity post-render guard, goes out
    via app.add_news, burns a one-shot mark, and closes its arc -- in that
    order, so a story is never marked delivered without being delivered.
    Only arcs resolved within ARC_FOLLOWUP_WINDOW_DAYS are eligible.
    Returns the number delivered. Never raises.
    """
    delivered = 0
    try:
        from daily_news import (_mark_recent, _recent_ok,
                                _story_has_unknown_entity)
    except Exception:
        return 0
    try:
        add = getattr(app, "add_news", None)
        if add is None:
            return 0
        ledger = get_ledger(app)
        rng = random.Random()
        try:
            rng.seed(hash((str(game_date), "story_arcs")))
        except Exception:
            pass
        for arc in ledger.resolved_arcs():
            try:
                f = arc.get("facts") or {}
                kind = f.get("arc_kind") or ""
                mtype = _FOLLOWUP_MARK_TYPE.get(kind)
                key = f.get("entity_key") or ""
                if not mtype or not key:
                    continue
                resolved = _parse_iso_date(f.get("resolved_date"))
                if resolved is None:
                    continue
                try:
                    age = (game_date - resolved).days
                except Exception:
                    continue
                if age < 0 or age > ARC_FOLLOWUP_WINDOW_DAYS:
                    continue
                if not _recent_ok(app, key, mtype, game_date,
                                   window=ARC_FOLLOWUP_MARK_WINDOW):
                    continue
                story = _render_followup(arc, rng)
                if not story:
                    continue
                if _story_has_unknown_entity(story):
                    _log.warning("story_arcs: suppressed follow-up failing "
                                 "post-render guard: %r", story[:160])
                    continue
                add(story)
                delivered += 1
                _mark_recent(app, key, mtype, game_date,
                             window=ARC_FOLLOWUP_MARK_WINDOW)
                ledger.close_arc(arc.get("id"))
            except Exception:
                continue
    except Exception:
        pass
    return delivered
