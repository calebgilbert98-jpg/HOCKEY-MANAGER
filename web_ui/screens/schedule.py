# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Schedule screen: full season schedule, daily results, and box scores.

Batch A (core loop gaps, 2026-10-06):

- GET /api/schedule_full -- every scheduled game (past + future) with
  month labels, scores when played, and box-score lookup keys. Powers the
  rebuilt schedule page (month filter, My Team / League tabs, sortable
  columns, Watch / Simulate / Box Score actions).
- GET /api/daily_results -- the simmed day's games, standings, and news.
  Web parity for main._post_advance_landing -> _show_daily_results_window
  (Games / Standings / News tabs). The hub shows this as a modal after
  each day advance when games were played.
- GET /api/boxscore?date=<iso>&home=<team> -- completed-game drill-down:
  header, scoring summary, player stats, team stats, 3 stars, lines grades.
  Web parity for GameBoxScoreView (game_box_score.py).
- GET /boxscore -- the box-score page.

The legacy /api/schedule (upcoming user-team games) in bridge.py is left
untouched; the hub still uses it.
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe

bp = Blueprint("schedule", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _league(live):
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: getattr(gm, "league", None)) or \
        _safe(lambda: getattr(live, "league", None))


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


def _team_abbr(name):
    try:
        from web_ui.bridge import TEAM_ABBR
        hit = TEAM_ABBR.get(name)
        if hit:
            return hit
    except Exception:
        pass
    try:
        return "".join(w[0] for w in str(name).split()[:2]).upper() or "?"
    except Exception:
        return "?"


def _iso(d):
    """date/datetime/ISO string -> 'YYYY-MM-DD' or None."""
    try:
        if isinstance(d, datetime):
            return d.date().isoformat()
        if isinstance(d, date):
            return d.isoformat()
        s = str(d or "")[:10]
        return date.fromisoformat(s).isoformat()
    except Exception:
        return None


def _date_key(value):
    """Normalize a mixed-format date to datetime.date (mirrors main.py)."""
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def _results_by_date(live):
    """{date: [game_result, ...]} via the app's O(1) index, rebuilt on fallback."""
    try:
        idx = getattr(live, "_results_by_date_index", None)
        if callable(idx):
            return idx() or {}
    except Exception:
        pass
    by_date = {}
    results = _safe(lambda: list(getattr(live, "game_results", None) or []), []) or []
    for r in results:
        try:
            k = _date_key(r.get("date"))
            if k is not None:
                by_date.setdefault(k, []).append(r)
        except Exception:
            continue
    return by_date


def _match_result(results, home_name, away_name):
    """Pick the result matching a (home, away) team-name pair."""
    for r in results or []:
        try:
            if _team_name(r.get("home_team")) == home_name and \
                    _team_name(r.get("away_team")) == away_name:
                return r
        except Exception:
            continue
    return None


def _find_game_result(live, date_iso, home_name, away_name=None):
    """Locate one completed game's result dict. Never raises."""
    try:
        key = _date_key(date_iso)
        if key is None or not home_name:
            return None
        results = _results_by_date(live).get(key, [])
        if away_name:
            hit = _match_result(results, home_name, away_name)
            if hit is not None:
                return hit
        for r in results:
            try:
                if _team_name(r.get("home_team")) == home_name:
                    return r
            except Exception:
                continue
    except Exception:
        pass
    return None


def _current_date(live):
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: getattr(gm, "current_date", None)) or \
        _safe(lambda: getattr(live, "current_date", None))


def _schedule_entries(live):
    """Yield normalized schedule entries from the league schedule.

    Handles tuple (date, home, away) and dict formats; skips NHL_EVENTs,
    non-NHL leagues, and playoff entries (same exclusions as the day sim).
    """
    league = _league(live)
    sched = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
    for item in sched:
        try:
            if isinstance(item, tuple) and len(item) >= 3:
                if len(item) >= 2 and item[1] == "NHL_EVENT":
                    continue
                yield {"date": item[0], "home_team": item[1],
                       "away_team": item[2], "event_type": "GAME",
                       "preseason": False}
            elif isinstance(item, dict):
                if item.get("event_type") == "NHL_EVENT":
                    continue
                if item.get("league", "NHL") != "NHL":
                    continue
                if item.get("playoff"):
                    continue
                yield item
        except Exception:
            continue


def _game_played_state(entry, live, by_date):
    """(played, home_score, away_score, overtime, shootout) for a schedule entry."""
    try:
        hs = entry.get("home_score")
        aws = entry.get("away_score")
        if hs is not None and aws is not None:
            return True, int(hs), int(aws), False, False
    except Exception:
        pass
    # Fall back to the recorded results index (scores not stamped on the entry).
    try:
        key = _date_key(entry.get("date"))
        home = _team_name(entry.get("home_team"))
        away = _team_name(entry.get("away_team"))
        r = _match_result((by_date or {}).get(key, []), home, away)
        if r is not None:
            return (True, int(r.get("home_score", 0) or 0),
                    int(r.get("away_score", 0) or 0),
                    bool(r.get("overtime")), bool(r.get("shootout")))
    except Exception:
        pass
    return False, None, None, False, False


@bp.route("/api/schedule_full")
def api_schedule_full():
    """Full season schedule: past + future, with scores and lookup keys."""
    live = _live()
    if live is None:
        return jsonify({"user_team": None, "months": [], "games": []})
    gm = _safe(lambda: live.game_manager)
    user_team = _safe(lambda: getattr(gm, "user_team", None)) or \
        _safe(lambda: getattr(live, "user_team", None))
    my_name = _safe(lambda: getattr(user_team, "team_name", ""), "") or ""
    today = _current_date(live)
    today_key = _date_key(today)
    by_date = _results_by_date(live)

    games = []
    months = []
    seen_months = set()
    for entry in _schedule_entries(live):
        try:
            gd = entry.get("date")
            key = _date_key(gd)
            iso = _iso(gd)
            home = _team_name(entry.get("home_team"))
            away = _team_name(entry.get("away_team"))
            if not home or not away or home == "?" or away == "?":
                continue
            played, hs, aws, ot, so = _game_played_state(entry, live, by_date)
            if key is not None:
                month_label = key.strftime("%B %Y")
                if month_label not in seen_months:
                    seen_months.add(month_label)
                    months.append({"label": month_label,
                                   "key": key.strftime("%Y-%m")})
            else:
                month_label = ""
            is_today = key is not None and today_key is not None and key == today_key
            is_past = key is not None and today_key is not None and key < today_key
            games.append({
                "date_iso": iso,
                "date_label": key.strftime("%a %m/%d") if key else str(gd or ""),
                "month": key.strftime("%Y-%m") if key else "",
                "month_label": month_label,
                "home": home,
                "away": away,
                "home_abbr": _team_abbr(home),
                "away_abbr": _team_abbr(away),
                "played": played,
                "home_score": hs,
                "away_score": aws,
                "status": "Final" if played else ("Today" if is_today else "Scheduled"),
                "overtime": ot,
                "shootout": so,
                "preseason": bool(entry.get("preseason", False)),
                "is_user": my_name in (home, away),
                "is_today": is_today,
                "is_past": is_past,
            })
        except Exception:
            continue
    games.sort(key=lambda g: (g["date_iso"] is None, g["date_iso"] or ""))
    return jsonify({"user_team": my_name, "months": months, "games": games})


# ----------------------------------------------------------------------
# Daily results (post-advance landing)
# ----------------------------------------------------------------------

def _news_items(live, n=5):
    """Last n news stories, newest last (desktop shows them in log order)."""
    raw = _safe(lambda: list(getattr(live, "news_log", None) or []), []) or []
    out = []
    for item in raw[-n:]:
        try:
            if isinstance(item, dict):
                out.append({
                    "date": _iso(item.get("date")) or "",
                    "story": str(item.get("story", "")),
                })
            else:
                out.append({"date": "", "story": str(item)})
        except Exception:
            continue
    return out


def _standings_rows(live):
    """League table sorted by points (mirrors the daily-results window)."""
    league = _league(live)
    table = _safe(lambda: dict(getattr(league, "standings", None) or {}), {}) or {}
    teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []
    gm = _safe(lambda: live.game_manager)
    my_name = _safe(lambda: getattr(getattr(gm, "user_team", None),
                                    "team_name", ""), "") or ""
    rows = []
    for t in teams:
        try:
            name = _team_name(t)
            st = table.get(name) or {}
            w = int(st.get("W", 0) or 0)
            l = int(st.get("L", 0) or 0)
            otl = int(st.get("OTL", 0) or 0)
            pts = int(st.get("Points", 0) or 0)
            gf = int(_safe(lambda: getattr(t, "goals_for", 0), 0) or 0)
            ga = int(_safe(lambda: getattr(t, "goals_against", 0), 0) or 0)
            rows.append({"team": name, "abbr": _team_abbr(name),
                         "gp": w + l + otl, "w": w, "l": l, "otl": otl,
                         "pts": pts, "gf": gf, "ga": ga, "diff": gf - ga,
                         "is_user": name == my_name})
        except Exception:
            continue
    rows.sort(key=lambda r: (r["pts"], r["diff"], r["gf"]), reverse=True)
    return rows


def _game_summary(r):
    """Compact JSON for one game_result (games tab + user game)."""
    try:
        home = _team_name(r.get("home_team"))
        away = _team_name(r.get("away_team"))
        hs = int(r.get("home_score", 0) or 0)
        aws = int(r.get("away_score", 0) or 0)
        d = r.get("date")
        note = ""
        if r.get("shootout"):
            note = "SO"
        elif r.get("overtime"):
            note = "OT"
        return {
            "date_iso": _iso(d),
            "date_label": _date_key(d).strftime("%a %m/%d") if _date_key(d) else str(d or ""),
            "home": home, "away": away,
            "home_abbr": _team_abbr(home), "away_abbr": _team_abbr(away),
            "home_score": hs, "away_score": aws,
            "note": note,
            "winner": _team_name(r.get("winner")) if r.get("winner") is not None else "",
        }
    except Exception:
        return {}


def _game_highlights(r):
    """Notable Goal/Save/Hit/Fight events, desktop-style strings."""
    out = []
    for event in _safe(lambda: list(r.get("notable_events") or []), []) or []:
        try:
            if not isinstance(event, dict):
                continue
            if event.get("event") not in ("Goal", "Save", "Hit", "Fight"):
                continue
            p = event.get("player")
            if p is not None and hasattr(p, "full_name"):
                pname = p.full_name
            else:
                pname = str(p or "Unknown")
            period = event.get("period", 1)
            try:
                t = int(event.get("time", 0) or 0)
                tstr = f"{t // 60:02d}:{t % 60:02d}"
            except Exception:
                tstr = ""
            plabel = f"P{period}" if period <= 3 else ("OT" if period == 4 else "SO")
            out.append(f"{event.get('event')}: {pname} ({plabel} {tstr})".strip())
        except Exception:
            continue
    return out


@bp.route("/api/daily_results")
def api_daily_results():
    """Results for the day that was just simulated (current_date - 1).

    Web parity for HockeyManagerGUI._show_daily_results_window: the games
    played, the league table, and the latest news. The hub renders this as
    a modal after advance_day when games_played > 0.
    """
    live = _live()
    if live is None:
        return jsonify({"ok": False, "games_played": 0})
    today = _current_date(live)
    simmed = None
    try:
        if isinstance(today, datetime):
            simmed = (today - timedelta(days=1)).date()
        elif isinstance(today, date):
            simmed = today - timedelta(days=1)
    except Exception:
        pass
    results = []
    try:
        if simmed is not None:
            results = list(_results_by_date(live).get(simmed, []))
    except Exception:
        pass
    gm = _safe(lambda: live.game_manager)
    my_name = _safe(lambda: getattr(getattr(gm, "user_team", None),
                                    "team_name", ""), "") or ""
    games = [_game_summary(r) for r in results]
    games = [g for g in games if g]
    user_game = None
    highlights = []
    for r, g in zip(results, games):
        try:
            if my_name and my_name in (_team_name(r.get("home_team")),
                                      _team_name(r.get("away_team"))):
                user_game = g
                highlights = _game_highlights(r)
                break
        except Exception:
            continue
    return jsonify({
        "ok": True,
        "date_iso": simmed.isoformat() if simmed else "",
        "date_label": simmed.strftime("%A, %B %d, %Y") if simmed else "",
        "games_played": len(games),
        "games": games,
        "user_game": user_game,
        "highlights": highlights,
        "standings": _standings_rows(live),
        "news": _news_items(live, 5),
    })


# ----------------------------------------------------------------------
# Box score
# ----------------------------------------------------------------------

def _pos_short(player):
    pos = _safe(lambda: getattr(player, "primary_position", None))
    val = _safe(lambda: getattr(pos, "value", None)) or \
        _safe(lambda: getattr(pos, "name", ""), "") or ""
    return str(val)


def _is_goalie(player):
    name = str(_safe(lambda: getattr(getattr(player, "primary_position", None),
                                     "name", ""), "") or "").upper()
    return "GOALIE" in name


def _player_link(pid, name):
    return {"pid": str(pid or ""), "name": name or "Unknown"}


def _roster_lookup(r):
    by_id = {}
    for team in (r.get("home_team"), r.get("away_team")):
        for p in _safe(lambda: list(getattr(team, "roster", None) or []), []) or []:
            try:
                pid = getattr(p, "id", None)
                if pid is not None and pid not in by_id:
                    by_id[pid] = p
            except Exception:
                continue
    # Merge game_stats-embedded players (traded away since, etc.).
    for pid, gs in ((r.get("game_stats") or {}).items()):
        try:
            p = gs.get("player") if isinstance(gs, dict) else None
            if p is not None and pid not in by_id:
                by_id[pid] = p
        except Exception:
            continue
    return by_id


def _period_label(period):
    try:
        p = int(period)
    except (TypeError, ValueError):
        return "?"
    if p <= 3:
        return f"Period {p}"
    if p == 4:
        return "Overtime"
    return "Shootout"


def _scoring_summary(r, by_id, home_name, away_name):
    """Goals grouped by period with running score (GameBoxScoreView parity)."""
    events = _safe(lambda: list(r.get("event_log") or []), []) or []
    goals = [e for e in events
             if isinstance(e, dict) and e.get("type") == "GOAL_ADVANCED"]

    def _key(e):
        d = e.get("details", {}) if isinstance(e.get("details"), dict) else {}
        return (d.get("period", 99), e.get("timestamp", 0))

    goals.sort(key=_key)
    if not goals:
        # Fallback for quick-simmed games: notable Goal events.
        for ne in _safe(lambda: list(r.get("notable_events") or []), []) or []:
            try:
                if isinstance(ne, dict) and ne.get("event") == "Goal":
                    goals.append({"_ne": True, "details": {
                        "period": ne.get("period", 1),
                        "time_str": "",
                        "scorer_id": getattr(ne.get("player"), "id", None),
                        "assist_ids": [],
                        "strength": "EV",
                        "goal_type": "",
                    }, "timestamp": 0})
            except Exception:
                continue

    out = []
    home_running = away_running = 0
    for e in goals:
        try:
            d = e.get("details", {}) if isinstance(e.get("details"), dict) else {}
            period = d.get("period", 1)
            scorer_id = d.get("scorer_id")
            sp = by_id.get(scorer_id)
            scorer_team = _safe(lambda: getattr(sp, "team_name", ""), "") or ""
            if scorer_team == home_name:
                home_running += 1
            elif scorer_team == away_name:
                away_running += 1
            assists = []
            for aid in (d.get("assist_ids") or []):
                ap = by_id.get(aid)
                assists.append(_player_link(
                    aid, _safe(lambda: getattr(ap, "full_name", "Unknown"),
                               "Unknown")))
            out.append({
                "period": period,
                "period_label": _period_label(period),
                "time_str": str(d.get("time_str", "") or ""),
                "scorer": _player_link(
                    scorer_id,
                    _safe(lambda: getattr(sp, "full_name", "Unknown"),
                           "Unknown")),
                "assists": assists,
                "team": scorer_team,
                "team_abbr": _team_abbr(scorer_team),
                "strength": str(d.get("strength", "EV") or "EV"),
                "goal_type": str(d.get("goal_type", "") or "").replace("_", " ").title(),
                "away_running": away_running,
                "home_running": home_running,
            })
        except Exception:
            continue
    return out


def _box_player_stats(r, by_id, home_name, away_name):
    """Per-team skater + goalie tables from game_stats."""
    game_stats = r.get("game_stats") or {}
    # GA per goalie from the goal events (engines that don't track
    # per-goalie GA still record the beaten goalie).
    ga_by_goalie = {}
    try:
        events = _safe(lambda: list(r.get("event_log") or []), []) or []
        for e in events:
            if isinstance(e, dict) and e.get("type") == "GOAL_ADVANCED":
                gid = (e.get("details", {}) or {}).get("goaltender_id")
                if gid:
                    ga_by_goalie[gid] = ga_by_goalie.get(gid, 0) + 1
    except Exception:
        pass

    teams = {}
    for team_name in (away_name, home_name):
        skaters, goalies = [], []
        for pid, gs in (game_stats or {}).items():
            try:
                if not isinstance(gs, dict):
                    continue
                p = gs.get("player") or by_id.get(pid)
                if p is None:
                    continue
                if _safe(lambda: getattr(p, "team_name", ""), "") != team_name:
                    continue
                if _is_goalie(p):
                    sa = int(gs.get("shots_against", 0) or 0)
                    sv = int(gs.get("saves", 0) or 0)
                    ga = int(gs.get("goals_against", 0) or 0) or \
                        ga_by_goalie.get(getattr(p, "id", None), 0)
                    if sa <= sv:  # engine didn't track shots against
                        sa = sv + ga
                    svp = round(sv / sa * 100, 1) if sa else None
                    goalies.append({
                        "player": _player_link(getattr(p, "id", None),
                                               _safe(lambda: getattr(
                                                   p, "full_name", "?"), "?")),
                        "sa": sa, "saves": sv, "svp": svp, "ga": ga,
                    })
                else:
                    g = int(gs.get("g", 0) or 0)
                    a = int(gs.get("a", 0) or 0)
                    skaters.append({
                        "player": _player_link(getattr(p, "id", None),
                                               _safe(lambda: getattr(
                                                   p, "full_name", "?"), "?")),
                        "pos": _pos_short(p),
                        "g": g, "a": a, "p": g + a,
                        "sog": int(gs.get("shots_on_goal", 0) or 0),
                        "hits": int(gs.get("hits", 0) or 0),
                        "blk": int(gs.get("blocked_shots",
                                          gs.get("blocked_shots_by", 0)) or 0),
                        "fo": f"{int(gs.get('faceoffs_won', 0) or 0)}-"
                              f"{int(gs.get('faceoffs_lost', 0) or 0)}",
                    })
            except Exception:
                continue
        skaters.sort(key=lambda s: (s["p"], s["g"]), reverse=True)
        teams[team_name] = {"skaters": skaters, "goalies": goalies,
                            "has_stats": bool(skaters or goalies)}
    return teams


def _box_team_stats(r, by_id, home_name, away_name):
    """Side-by-side team comparison rows (GameBoxScoreView parity)."""
    team_stats = r.get("team_stats") or {}
    a_ts = team_stats.get(away_name, {}) if isinstance(team_stats, dict) else {}
    h_ts = team_stats.get(home_name, {}) if isinstance(team_stats, dict) else {}
    if not isinstance(a_ts, dict):
        a_ts = {}
    if not isinstance(h_ts, dict):
        h_ts = {}

    def _val(ts, key, default=0):
        v = ts.get(key, default)
        return v if isinstance(v, (int, float)) else default

    # Fallbacks from the event log when team_stats are missing.
    shots_a = shots_h = saves_a = saves_h = 0
    if not a_ts and not h_ts:
        for e in _safe(lambda: list(r.get("event_log") or []), []) or []:
            try:
                if not isinstance(e, dict):
                    continue
                d = e.get("details", {}) or {}
                if e.get("type") == "GOAL_ADVANCED":
                    p = by_id.get(d.get("scorer_id"))
                    if p is not None and _safe(lambda: getattr(
                            p, "team_name", ""), "") == home_name:
                        shots_h += 1
                    else:
                        shots_a += 1
                elif e.get("type") == "SAVE_ADVANCED":
                    p = by_id.get(d.get("goaltender_id"))
                    if p is not None and _safe(lambda: getattr(
                            p, "team_name", ""), "") == home_name:
                        saves_h += 1
                        shots_a += 1
                    else:
                        saves_a += 1
                        shots_h += 1
            except Exception:
                continue

    def _blk(ts):
        return _val(ts, "blocked_shots_by_team", _val(ts, "blocked_shots"))

    return [
        {"label": "Goals", "away": r.get("away_score", 0),
         "home": r.get("home_score", 0)},
        {"label": "Shots on Goal",
         "away": _val(a_ts, "shots_on_goal", shots_a),
         "home": _val(h_ts, "shots_on_goal", shots_h)},
        {"label": "Saves",
         "away": _val(a_ts, "saves", saves_a),
         "home": _val(h_ts, "saves", saves_h)},
        {"label": "Hits",
         "away": _val(a_ts, "hits"), "home": _val(h_ts, "hits")},
        {"label": "Blocked Shots",
         "away": _blk(a_ts), "home": _blk(h_ts)},
        {"label": "Faceoffs Won",
         "away": _val(a_ts, "faceoffs_won"),
         "home": _val(h_ts, "faceoffs_won")},
        {"label": "Takeaways",
         "away": _val(a_ts, "takeaways"), "home": _val(h_ts, "takeaways")},
        {"label": "Giveaways",
         "away": _val(a_ts, "giveaways"), "home": _val(h_ts, "giveaways")},
        {"label": "Power Play",
         "away": f"{_val(a_ts, 'power_play_goals')}/"
                 f"{_val(a_ts, 'power_play_opportunities')}",
         "home": f"{_val(h_ts, 'power_play_goals')}/"
                 f"{_val(h_ts, 'power_play_opportunities')}"},
        {"label": "Short-handed Goals",
         "away": _val(a_ts, "short_handed_goals"),
         "home": _val(h_ts, "short_handed_goals")},
    ]


def _box_three_stars(r, by_id):
    """Three stars: recorded at game time when available, else ratings sort."""
    saved = r.get("three_stars")
    stars = []
    if saved:
        for s in (saved or [])[:3]:
            try:
                if not isinstance(s, dict):
                    continue
                name = s.get("name", "?")
                pid = None
                for _pid, p in by_id.items():
                    try:
                        if _safe(lambda: getattr(p, "full_name", ""), "") == name:
                            pid = _pid
                            break
                    except Exception:
                        continue
                stars.append({"name": name, "pid": str(pid or ""),
                              "team": s.get("team_name", ""),
                              "detail": str(s.get("line", "") or "")})
            except Exception:
                continue
        if stars:
            return stars
    ratings = r.get("player_ratings") or {}
    scored = []
    for team_name, pmap in ratings.items():
        if not isinstance(pmap, dict):
            continue
        for pid, rating in pmap.items():
            try:
                p = by_id.get(pid)
                scored.append((float(rating or 0),
                               _safe(lambda: getattr(p, "full_name", "Unknown"),
                                      "Unknown"),
                               pid, team_name))
            except Exception:
                continue
    scored.sort(key=lambda s: s[0], reverse=True)
    return [{"name": n, "pid": str(pid or ""), "team": t,
             "detail": f"{rtg:.1f}"} for rtg, n, pid, t in scored[:3]]


def _grade_fn():
    try:
        from mesh_system import compute_skater_game_grade_v2
        return compute_skater_game_grade_v2
    except Exception:
        return None


def _box_lines(r, by_id, team_name):
    """Per-line player grades + combined line ratings (Lines tab parity)."""
    snap = ((r.get("lines") or {}).get(team_name)) if isinstance(
        r.get("lines"), dict) else None
    if not isinstance(snap, dict):
        return []
    game_stats = r.get("game_stats") or {}
    grade = _grade_fn()
    out = []
    units = []
    for i, line in enumerate((snap.get("Forwards") or [])[:4]):
        units.append((f"Line {i + 1}", line or []))
    for i, pair in enumerate((snap.get("Defense") or [])[:3]):
        units.append((f"Pair {i + 1}", pair or []))
    for label, pids in units:
        players = []
        grades = []
        for pid in pids or []:
            try:
                p = by_id.get(pid)
                if p is None:
                    continue
                gs = (game_stats or {}).get(pid) or {}
                g = int(gs.get("g", 0) or 0)
                a = int(gs.get("a", 0) or 0)
                gv, why = None, ""
                if grade is not None and pid in (game_stats or {}) and \
                        isinstance(gs, dict):
                    try:
                        gv, why = grade(p, gs)
                        if gv is not None:
                            grades.append(float(gv))
                    except Exception:
                        gv, why = None, ""
                players.append({
                    "player": _player_link(
                        pid, _safe(lambda: getattr(p, "full_name", "?"), "?")),
                    "pos": _pos_short(p),
                    "g": g, "a": a, "p": g + a,
                    "grade": round(float(gv), 1) if gv is not None else None,
                    "why": str(why or ""),
                })
            except Exception:
                continue
        rating = round(sum(grades) / len(grades), 1) if grades else None
        out.append({"label": label, "rating": rating, "players": players})
    return out


@bp.route("/api/boxscore")
def api_boxscore():
    """Completed-game box score. Params: date=<YYYY-MM-DD>, home=<team name>,
    away=<team name, optional>."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no game attached"}), 503
    date_iso = request.args.get("date", "")
    home = request.args.get("home", "")
    away = request.args.get("away", "")
    r = _find_game_result(live, date_iso, home, away or None)
    if r is None:
        return jsonify({"ok": False,
                        "error": "no recorded result for that game"}), 404
    try:
        home_name = _team_name(r.get("home_team"))
        away_name = _team_name(r.get("away_team"))
        by_id = _roster_lookup(r)
        d = r.get("date")
        date_label = _date_key(d).strftime("%a %b %d, %Y") if _date_key(d) \
            else str(d or "")
        note = ""
        if r.get("shootout"):
            note = "Shootout"
        elif r.get("overtime"):
            note = "Overtime"
        payload = {
            "ok": True,
            "date_iso": _iso(d),
            "date_label": date_label,
            "note": note,
            "home": {"name": home_name,
                     "abbr": _team_abbr(home_name),
                     "score": int(r.get("home_score", 0) or 0)},
            "away": {"name": away_name,
                     "abbr": _team_abbr(away_name),
                     "score": int(r.get("away_score", 0) or 0)},
            "scoring": _scoring_summary(r, by_id, home_name, away_name),
            "players": _box_player_stats(r, by_id, home_name, away_name),
            "team_stats": _box_team_stats(r, by_id, home_name, away_name),
            "three_stars": _box_three_stars(r, by_id),
            "lines": {home_name: _box_lines(r, by_id, home_name),
                      away_name: _box_lines(r, by_id, away_name)},
        }
        return jsonify(payload)
    except Exception as e:
        return jsonify({"ok": False, "error": f"box score failed: {e}"}), 500


@bp.route("/boxscore")
def boxscore_page():
    return render_template("boxscore.html")
