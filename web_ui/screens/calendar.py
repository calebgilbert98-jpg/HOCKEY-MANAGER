"""Calendar screen: month calendar view of the season schedule (read-only v1)."""
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, _team_name

bp = Blueprint("calendar", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _iso(d):
    """datetime/date -> 'YYYY-MM-DD' string; anything else -> str fallback."""
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if d is None:
        return ""
    return _safe(lambda: str(d), "") or ""


def _calendar_payload(app):
    """Full schedule -> JSON-safe payload. Never raises."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    my_name = _safe(lambda: team.team_name, "") if team else ""

    today = _safe(lambda: gm.current_date) if gm else None
    today_iso = _iso(today)

    sched = []
    if gm is not None:
        league = _safe(lambda: gm.league)
        raw = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
        for g in raw:
            try:
                if not isinstance(g, dict):
                    continue
                home = _team_name(g.get("home_team"))
                away = _team_name(g.get("away_team"))
                gd = g.get("date")
                mine = bool(my_name) and my_name in (home, away)
                sched.append({
                    "date": _iso(gd),
                    "home": home,
                    "away": away,
                    "is_home": bool(mine) and home == my_name,
                    "opponent": away if home == my_name else (home if mine else ""),
                    "mine": mine,
                    "preseason": bool(g.get("preseason", False)),
                })
            except Exception:
                continue

    # chronological where possible (fall back to original order on weird data)
    try:
        sched.sort(key=lambda x: x["date"])
    except Exception:
        pass

    return {
        "today": today_iso,
        "team": my_name or "",
        "games": sched,
    }


@bp.route("/calendar")
def calendar_page():
    return render_template("calendar.html")


@bp.route("/api/calendar")
def api_calendar():
    live = _live()
    if live is None:
        return jsonify({"today": "", "team": "", "games": []})
    return jsonify(_calendar_payload(live))


# ------------------------------------------------------------------
# Batch C (League) minor: event markers + deadline-day actions
# (~200 lines desktop: trade deadline, draft day, season start/end,
# plus a deadline-day action hook into the Deadline Center).
# ------------------------------------------------------------------

def _calendar_events(live):
    """League event markers: trade deadline, entry draft, season bounds.

    Never raises; dates are ISO strings.
    """
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league)
    events = []
    if league is None:
        return events

    # Trade deadline (derived from the schedule, same as the center).
    try:
        from trade_deadline_manager import trade_deadline_date
        dd = trade_deadline_date(league)
        if dd:
            events.append({
                "date": dd.isoformat(),
                "kind": "deadline",
                "label": "Trade Deadline (3 PM ET)",
                "action": "/deadline",
                "action_label": "Open Deadline Center",
            })
    except Exception:
        pass

    # Entry draft day.
    try:
        session = _safe(lambda: getattr(league, "entry_draft_session", None))
        dyear = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
        if not dyear:
            dyear = _safe(lambda: int(getattr(league, "season_year", 0) or 0),
                          0) + 1
        if dyear:
            # Draft is late June; the desktop war room keys off the
            # session year.
            events.append({
                "date": f"{dyear}-06-28",
                "kind": "draft",
                "label": f"{dyear} Entry Draft",
                "action": "/draft",
                "action_label": "Open Draft Day Central",
            })
    except Exception:
        pass

    # Season bounds from the schedule.
    try:
        sched = _safe(lambda: list(getattr(league, "schedule", None)
                                   or []), []) or []
        dates = []
        for g in sched:
            try:
                if not isinstance(g, dict) or g.get("preseason"):
                    continue
                d = g.get("date")
                iso = _iso(d)
                if iso:
                    dates.append(iso)
            except Exception:
                continue
        dates.sort()
        if dates:
            events.append({"date": dates[0], "kind": "season",
                           "label": "Opening Night"})
            if dates[-1] != dates[0]:
                events.append({"date": dates[-1], "kind": "season",
                               "label": "Regular Season Ends"})
    except Exception:
        pass
    return events


@bp.route("/api/calendar/events")
def api_calendar_events():
    """Event markers + deadline-day state for the calendar page."""
    live = _live()
    if live is None:
        return jsonify({"events": [], "deadline": None})
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) if gm else None
    deadline = None
    if league is not None:
        try:
            from trade_deadline_manager import trade_deadline_date
            dd = trade_deadline_date(league)
            today = _safe(lambda: gm.current_date)
            try:
                today = today.date() if isinstance(today, datetime) \
                    else today
            except Exception:
                today = None
            if dd:
                days_left = (dd - today).days if today else None
                deadline = {
                    "date": dd.isoformat(),
                    "label": dd.strftime("%B %d, %Y"),
                    "days_left": days_left,
                    "is_today": bool(today and dd == today),
                    "passed": bool(days_left is not None and days_left < 0),
                }
        except Exception:
            pass
    return jsonify({"events": _calendar_events(live), "deadline": deadline})
