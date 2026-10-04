"""History screen: league champions + records (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe

bp = Blueprint("history", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _season_to_web(s):
    """One season record dict -> JSON-safe dict."""
    try:
        awards = _safe(lambda: dict(s.get("awards", None) or {}), {})
    except Exception:
        awards = {}
    return {
        "year": _safe(lambda: s.get("year"), ""),
        "champion": _safe(lambda: s.get("champion") or ""),
        "runner_up": _safe(lambda: s.get("runner_up") or ""),
        "series_score": _safe(lambda: s.get("series_score") or ""),
        "presidents_trophy": _safe(lambda: s.get("presidents_trophy") or ""),
        "conn_smythe": _safe(lambda: s.get("conn_smythe") or ""),
        "awards": {str(k): str(v) for k, v in awards.items()},
    }


def _record_store_summary(store):
    """Franchise record store -> {franchises: n, records: n}."""
    try:
        d = store or {}
        return {
            "franchises": len(d),
            "records": sum(len(v or {}) for v in d.values()),
        }
    except Exception:
        return {"franchises": 0, "records": 0}


def _history_payload(app):
    """LeagueHistory -> JSON-safe dict. Never raises."""
    hist = _safe(lambda: getattr(app.game_manager, "league_history", None))
    # defensive fallbacks: some builds keep history on the app or league
    if hist is None:
        hist = _safe(lambda: getattr(app, "league_history", None))
    if hist is None:
        gm_league = _safe(lambda: getattr(app.game_manager, "league", None))
        hist = _safe(lambda: getattr(gm_league, "history", None)) if gm_league else None

    if hist is None:
        return {"has_data": False, "seasons": [], "records": None,
                "hall_of_fame_count": 0}

    champions = _safe(lambda: hist.champions_list(), []) or []
    seasons = [_season_to_web(s) for s in champions]
    # champions_list is newest-first; keep that ordering for display
    fr = _safe(lambda: getattr(hist, "franchise_records", None))
    records = None
    if fr is not None:
        records = {
            "skater_career": _record_store_summary(_safe(lambda: fr.career_records)),
            "skater_season": _record_store_summary(_safe(lambda: fr.season_records)),
            "goalie_career": _record_store_summary(_safe(lambda: fr.goalie_career_records)),
            "goalie_season": _record_store_summary(_safe(lambda: fr.goalie_season_records)),
            "team_season": _record_store_summary(_safe(lambda: fr.team_season_records)),
            "streaks": _record_store_summary(_safe(lambda: fr.streaks)),
        }
    hof = _safe(lambda: list(getattr(hist, "hall_of_fame", None) or []), [])

    return {
        "has_data": bool(seasons) or bool(hof),
        "seasons": seasons,
        "records": records,
        "hall_of_fame_count": len(hof),
    }


@bp.route("/history")
def history_page():
    return render_template("history.html")


@bp.route("/api/history")
def api_history():
    live = _live()
    if live is None:
        return jsonify({"has_data": False, "seasons": [], "records": None,
                        "hall_of_fame_count": 0})
    return jsonify(_history_payload(live))
