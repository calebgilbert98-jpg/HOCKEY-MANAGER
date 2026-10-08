"""Draft recaps for Puck Dynasty.

Two recaps, built into the game:

1. Fantasy draft recap -- one-time, at game start if a fantasy draft was
   conducted. Keyed ``'fantasy'`` in ``league.draft_recap_history``.
2. Annual entry draft recap -- every year the entry draft is conducted.
   Keyed ``str(year)`` in ``league.draft_recap_history``.

Each recap is plain data (dicts of str/int/float/None/lists) so it survives
save/load exactly like ``league.draft_grades_history`` does:

{
    'draft_type': 'fantasy' | 'entry',
    'year': <int>,
    'num_picks': <int>,
    'num_teams': <int>,
    'num_rounds': <int>,
    'picks': [
        {'overall_pick': int, 'round': int, 'team_name': str,
         'player_name': str, 'overall_rating': int | None,
         'age': int | None, 'potential': int | None,
         'position': str,            # 'C' | 'W' | 'D' | 'G'
         'value_ratio': float | None # drafted value vs slot expectation
        }, ...
    ],
    'grades': [[team_name, grade, ratio], ...],   # best-first
    'positional_breakdown': {'C': n, 'W': n, 'D': n, 'G': n},
}

Grading and value analysis reuse draft_night.draft_grades,
pick_slot_value and drafted_player_value -- no reinvented grading.
value_ratio = drafted_player_value(player) / pick_slot_value(overall):
  > 1.0 means the pick returned more value than its slot expects
  (steals / best values); < 1.0 means it returned less (reaches).

The native UI screen (native_ui/screens/draft_recap.py) renders the
round-by-round full board, the top-10 quick glance, user picks with
grades, best values, reaches and the positional breakdown.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Dict, List, Optional, Tuple

RECAP_FANTASY_KEY = "fantasy"


# ---------------------------------------------------------------------------
# small safe-access helpers (recap building must never break a draft)
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _recap_history(league) -> Dict:
    """Return league.draft_recap_history, creating it if missing."""
    try:
        hist = getattr(league, "draft_recap_history", None)
        if not isinstance(hist, dict):
            hist = {}
            league.draft_recap_history = hist
        return hist
    except Exception:
        return {}


def _league_year(league) -> int:
    return int(_safe(lambda: getattr(league, "season_year", None),
                     _date.today().year) or _date.today().year)


def _nhl_team_count(league) -> int:
    try:
        teams = getattr(league, "teams", None) or []
        n = sum(1 for t in teams
                if getattr(t, "league_name", "") == "National Hockey League")
        if n:
            return n
        return len(teams) or 32
    except Exception:
        return 32


def _pos_value(player) -> str:
    pp = _safe(lambda: getattr(player, "primary_position", None))
    v = _safe(lambda: pp.value, None)
    if v:
        return str(v)
    return "?"


def _pos_group(pos_value: str) -> str:
    """Normalize a position value to the recap groups C / W / D / G."""
    v = (pos_value or "").upper()
    if v == "C":
        return "C"
    if v in ("LW", "RW"):
        return "W"
    if v in ("LD", "RD", "D"):
        return "D"
    if v == "G":
        return "G"
    return "?"


def _overall_rating(player) -> Optional[int]:
    r = _safe(lambda: player.overall_rating())
    try:
        return int(r) if r is not None else None
    except (TypeError, ValueError):
        return None


def _age_on_draft(player, year: int) -> Optional[int]:
    try:
        from draft_generator import age_on_sept15
        return age_on_sept15(getattr(player, "birth_date", None), year)
    except Exception:
        return None


def _potential(player) -> Optional[int]:
    p = _safe(lambda: getattr(player, "potential", None))
    try:
        return int(p) if p is not None else None
    except (TypeError, ValueError):
        return None


def _value_ratio(player, overall_pick: int) -> Optional[float]:
    """Value returned vs value expected at the slot. >1 = steal, <1 = reach."""
    try:
        from draft_night import pick_slot_value, drafted_player_value
        expected = pick_slot_value(int(overall_pick or 0))
        actual = drafted_player_value(player)
        if not expected:
            return None
        return round(float(actual) / float(expected), 3)
    except Exception:
        return None


def _pick_dict(overall_pick: int, round_num: int, team_name: str,
               player, year: int) -> Dict:
    return {
        "overall_pick": int(overall_pick or 0),
        "round": int(round_num or 0),
        "team_name": str(team_name or "?"),
        "player_name": str(_safe(lambda: getattr(player, "full_name", "?"),
                                 "?") or "?"),
        "overall_rating": _overall_rating(player),
        "age": _age_on_draft(player, year),
        "potential": _potential(player),
        "position": _pos_group(_pos_value(player)),
        "value_ratio": _value_ratio(player, overall_pick),
    }


def _user_team_name(league) -> str:
    try:
        for t in (getattr(league, "teams", None) or []):
            if bool(getattr(t, "is_user_team", False)):
                return str(getattr(t, "team_name", "") or "")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# public accessors (used by the native UI screen)
# ---------------------------------------------------------------------------

def get_draft_recap(league, key) -> Optional[Dict]:
    """Return the recap dict for 'fantasy' or str(year), or None."""
    try:
        hist = _recap_history(league)
        rec = hist.get(str(key))
        return rec if isinstance(rec, dict) and rec else None
    except Exception:
        return None


def list_draft_recaps(league) -> List[str]:
    """Recap keys in selector order: fantasy first, then years ascending."""
    try:
        hist = _recap_history(league)
        years = sorted(k for k in hist.keys()
                       if k != RECAP_FANTASY_KEY and hist.get(k))
        keys = ([RECAP_FANTASY_KEY] if hist.get(RECAP_FANTASY_KEY) else [])
        return keys + years
    except Exception:
        return []


# ---------------------------------------------------------------------------
# inbox
# ---------------------------------------------------------------------------

def _post_inbox(league, subject: str, body: str) -> None:
    """Post a recap message to the user's inbox. Never raises; no-ops when
    there is no user team (headless / bulk-sim)."""
    try:
        user_team = None
        for t in (getattr(league, "teams", None) or []):
            if bool(getattr(t, "is_user_team", False)):
                user_team = t
                break
        if user_team is None:
            return
        from game_classes import EmailMessage
        msg = EmailMessage(
            sender="NHL Commissioner",
            sender_type="League",
            subject=subject,
            content=body,
            date_sent=_date.today(),
            is_important=True,
            category="League",
            priority=3,
        )
        inbox = getattr(user_team, "inbox", None)
        add = getattr(inbox, "add_message", None)
        if callable(add):
            add(msg)
        else:
            # Fallback for inbox-like containers without add_message.
            try:
                inbox.append(msg)  # type: ignore[union-attr]
            except Exception:
                pass
    except Exception:
        pass


def _inbox_body_fantasy(recap: Dict, user_team: str) -> str:
    picks = recap.get("picks") or []
    grades = {t: (g, r) for t, g, r in (recap.get("grades") or [])}
    lines = ["The fantasy draft is complete -- every NHL player has been "
             "redistributed. Open the full draft recap for the round-by-round "
             "board, best values and biggest reaches."]
    if picks:
        p1 = picks[0]
        lines.append(f"\n#1 overall: {p1['player_name']} "
                     f"({p1['overall_rating']} OVR) -> {p1['team_name']}.")
    if user_team and user_team in grades:
        g, r = grades[user_team]
        mine = [p for p in picks if p["team_name"] == user_team]
        lines.append(f"\nYour draft grade: {g} ({len(mine)} picks).")
        valued = [p for p in mine if p.get("value_ratio")]
        if valued:
            best = max(valued, key=lambda p: p["value_ratio"])
            lines.append(f"Best value: {best['player_name']} "
                         f"(#{best['overall_pick']}, {best['overall_rating']} "
                         f"OVR, {best['position']}).")
    lines.append("\nTap VIEW DRAFT RECAP above to browse every round.")
    return "\n".join(lines)


def _inbox_body_entry(recap: Dict, user_team: str) -> str:
    year = recap.get("year")
    picks = recap.get("picks") or []
    grades = {t: (g, r) for t, g, r in (recap.get("grades") or [])}
    lines = [f"The {year} NHL Entry Draft is complete."]
    if picks:
        p1 = picks[0]
        lines.append(f"\n#1 overall: {p1['player_name']} "
                     f"({p1['overall_rating']} OVR, {p1['position']}, "
                     f"age {p1['age']}) -> {p1['team_name']}.")
    if user_team and user_team in grades:
        g, r = grades[user_team]
        mine = [p for p in picks if p["team_name"] == user_team]
        lines.append(f"\nYour draft grade: {g} ({len(mine)} picks).")
        valued = [p for p in mine if p.get("value_ratio")]
        if valued:
            best = max(valued, key=lambda p: p["value_ratio"])
            lines.append(f"Best value: {best['player_name']} "
                         f"(#{best['overall_pick']}, R{best['round']}, "
                         f"{best['overall_rating']} OVR).")
    lines.append("\nTap VIEW DRAFT RECAP above to browse every round.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def _assemble(league, draft_type: str, year: int,
              pick_tuples: List[Tuple[str, int, int, object]]) -> Dict:
    """Shared assembler. pick_tuples = [(team_name, overall, round, player)]."""
    from draft_night import draft_grades

    picks = [_pick_dict(overall, rnd, tname, player, year)
             for tname, overall, rnd, player in pick_tuples
             if player is not None]
    picks.sort(key=lambda p: p["overall_pick"])

    grade_tuples = [(tname, overall, player)
                    for tname, overall, _rnd, player in pick_tuples
                    if player is not None]
    grades = _safe(lambda: draft_grades(grade_tuples), []) or []
    grades = [[str(t), str(g), round(float(r), 4)] for t, g, r in grades]

    breakdown = {"C": 0, "W": 0, "D": 0, "G": 0}
    for p in picks:
        breakdown[p["position"]] = breakdown.get(p["position"], 0) + 1

    recap = {
        "draft_type": draft_type,
        "year": int(year),
        "num_picks": len(picks),
        "num_teams": _nhl_team_count(league),
        "num_rounds": max([p["round"] for p in picks] or [0]),
        "picks": picks,
        "grades": grades,
        "positional_breakdown": breakdown,
    }
    return recap


def build_fantasy_draft_recap(league, mgr) -> Dict:
    """Build and persist the fantasy draft recap.

    Idempotent: returns the existing recap if one was already built.
    Posts an inbox message to the user's team on first build.
    """
    hist = _recap_history(league)
    existing = hist.get(RECAP_FANTASY_KEY)
    if isinstance(existing, dict) and existing:
        return existing

    year = _league_year(league)
    raw_picks = _safe(lambda: list(getattr(mgr, "draft_picks", None) or []), [])
    tuples = []
    for pk in raw_picks or []:
        try:
            team = getattr(pk, "team", None)
            tuples.append((
                str(getattr(team, "team_name", "?") or "?"),
                int(getattr(pk, "overall_pick", 0) or 0),
                int(getattr(pk, "round_num", 0) or 0),
                getattr(pk, "player", None),
            ))
        except Exception:
            continue

    recap = _assemble(league, "fantasy", year, tuples)
    try:
        hist[RECAP_FANTASY_KEY] = recap
        league.draft_recap_latest = RECAP_FANTASY_KEY
    except Exception:
        pass
    user_team = _user_team_name(league)
    _post_inbox(league, "📋 FANTASY DRAFT RECAP",
                _inbox_body_fantasy(recap, user_team))
    return recap


def build_entry_draft_recap(league, draft_year, picks_made) -> Dict:
    """Build and persist the entry draft recap for draft_year.

    picks_made: [(team_name, overall, player)] -- the exact shape
    conduct_entry_draft produces (and draft_grades consumes).
    Idempotent per year; posts an inbox message on first build.
    """
    try:
        year = int(draft_year)
    except (TypeError, ValueError):
        return {}
    key = str(year)
    hist = _recap_history(league)
    existing = hist.get(key)
    if isinstance(existing, dict) and existing:
        return existing

    n_teams = _nhl_team_count(league)
    tuples = []
    for entry in (picks_made or []):
        try:
            tname, overall, player = entry
            overall_i = int(overall or 0)
            rnd = (overall_i - 1) // n_teams + 1 if overall_i > 0 else 0
            tuples.append((str(tname or "?"), overall_i, rnd, player))
        except Exception:
            continue

    recap = _assemble(league, "entry", year, tuples)
    try:
        hist[key] = recap
        league.draft_recap_latest = key
    except Exception:
        pass
    user_team = _user_team_name(league)
    _post_inbox(league, f"📋 {year} ENTRY DRAFT RECAP",
                _inbox_body_entry(recap, user_team))
    return recap
