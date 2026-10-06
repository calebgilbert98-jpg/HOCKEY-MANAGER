"""History screen: league champions + records (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, _resolve_gm

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


# ------------------------------------------------------------------
# Batch C (League): missing history tabs. Ported from main.py
# LeagueHistoryView (~30206-30653): Career Leaders, Hall of Fame,
# Advanced Stats (+ glossary), Season Reviews; the awards view shows
# the FULL award list (web previously truncated to 3).
# ------------------------------------------------------------------

_HISTORY_CATS = ["points", "goals", "assists", "wins", "shutouts",
                 "save_pct"]


def _hist(live):
    hist = _safe(lambda: getattr(live.game_manager, "league_history", None))
    if hist is None:
        hist = _safe(lambda: getattr(live, "league_history", None))
    if hist is None:
        gm_league = _safe(lambda: getattr(live.game_manager, "league", None))
        hist = _safe(lambda: getattr(gm_league, "history", None)) \
            if gm_league else None
    return hist


@bp.route("/api/history/career-leaders")
def api_history_career_leaders():
    """Career Leaders tab: LeagueHistory.career_leaders over all current
    players (desktop _build_leaders ~30599)."""
    from flask import request as _req
    live = _live()
    cat = (_req.args.get("category") or "points").strip()
    if cat not in _HISTORY_CATS:
        cat = "points"
    if live is None:
        return jsonify({"categories": _HISTORY_CATS, "category": cat,
                        "leaders": []})
    try:
        from league_history import LeagueHistory
        gm = _resolve_gm(live)
        league = _safe(lambda: gm.league)
        players = []
        for t in (_safe(lambda: list(league.teams), []) or []):
            players.extend(_safe(lambda: list(t.roster), []) or [])
        leaders = LeagueHistory.career_leaders(players, cat, limit=25) or []
        rows = []
        for i, ld in enumerate(leaders, 1):
            try:
                v = ld["value"]
                vstr = f"{v:.3f}" if cat == "save_pct" else str(int(v))
                rows.append({
                    "rank": i, "name": ld.get("name", "?"),
                    "team": ld.get("team") or "",
                    "games": int(ld.get("games", 0) or 0),
                    "value": vstr,
                })
            except Exception:
                continue
        return jsonify({"categories": _HISTORY_CATS, "category": cat,
                        "value_label": "SV%" if cat == "save_pct"
                        else cat.upper(),
                        "leaders": rows})
    except Exception:
        return jsonify({"categories": _HISTORY_CATS, "category": cat,
                        "leaders": []})


@bp.route("/api/history/hall-of-fame")
def api_history_hof():
    """Hall of Fame list tab (desktop _build_hof ~30653): inductees with
    career lines and Cup counts."""
    live = _live()
    hist = _hist(live) if live else None
    if hist is None:
        return jsonify({"inductees": [], "bar": ""})
    try:
        inds = sorted(_safe(lambda: list(getattr(hist, "hall_of_fame", None)
                                         or []), []) or [],
                      key=lambda x: x.get("year_inducted", 0), reverse=True)
        rows = []
        for ind in inds:
            try:
                pos = str(ind.get("position", "") or "")
                if "GOALIE" in pos.upper():
                    line = (f"{ind.get('games', 0)} GP, "
                            f"{ind.get('wins', 0)} W, "
                            f"{ind.get('shutouts', 0)} SO")
                else:
                    line = (f"{ind.get('games', 0)} GP, "
                            f"{ind.get('goals', 0)} G, "
                            f"{ind.get('assists', 0)} A, "
                            f"{ind.get('points', 0)} Pts")
                rows.append({
                    "name": ind.get("name", "?"),
                    "position": pos,
                    "year_inducted": ind.get("year_inducted", "?"),
                    "teams": ind.get("teams") or [],
                    "line": line,
                    "cups": int(ind.get("cups", 0) or 0),
                    "awards": ind.get("awards") or [],
                })
            except Exception:
                continue
        return jsonify({
            "inductees": rows,
            "bar": ("1000+ points / 500+ goals (skaters) \u2022 300+ wins "
                    "(goalies) \u2022 icon-level reputation"),
        })
    except Exception:
        return jsonify({"inductees": [], "bar": ""})


@bp.route("/api/history/advanced-stats")
def api_history_advanced():
    """Advanced Stats tab (desktop _build_advanced ~30357): team 5v5
    process table, league leaders per advanced category, and the full
    GLOSSARY."""
    live = _live()
    if live is None:
        return jsonify({"teams": [], "leaders": {}, "glossary": {},
                        "note": ""})
    try:
        from advanced_metrics import (team_advanced,
                                      league_leaders_advanced, GLOSSARY)
        gm = _resolve_gm(live)
        league = _safe(lambda: gm.league)
        teams = _safe(lambda: list(league.teams), []) or []
        trows = []
        for t in teams:
            try:
                m = team_advanced(t)
                trows.append({
                    "team": _safe(lambda: t.team_name, "?"),
                    "cf_pct": round(float(getattr(m, "cf_pct", 0) or 0), 1),
                    "ff_pct": round(float(getattr(m, "ff_pct", 0) or 0), 1),
                    "xgf_pct": round(float(getattr(m, "xgf_pct", 0) or 0), 1),
                    "gf_pct": round(float(getattr(m, "gf_pct", 0) or 0), 1),
                    "pdo": round(float(getattr(m, "pdo", 0) or 0), 3),
                    "pp_pct": round(float(getattr(m, "pp_pct", 0) or 0), 1),
                    "pk_pct": round(float(getattr(m, "pk_pct", 0) or 0), 1),
                    "srs": round(float(getattr(m, "srs", 0) or 0), 2),
                })
            except Exception:
                continue
        players = []
        for t in teams:
            players.extend(_safe(lambda: list(t.roster), []) or [])
        cats = [("ixG", "ixg"), ("xGF%", "xgf_pct"), ("Corsi%", "cf_pct"),
                ("PDO", "pdo"), ("P/60", "p_per60"),
                ("Game Score", "game_score"), ("GSAx", "gsax")]
        leaders = {}
        for label, cat in cats:
            try:
                rows = []
                for r in league_leaders_advanced(players, cat, limit=5) or []:
                    v = r["value"]
                    vs = (f"{v:.3f}" if cat == "pdo"
                          else f"{v:.1f}" if isinstance(v, float)
                          else str(v))
                    rows.append({"name": r.get("name", "?"), "value": vs})
                leaders[label] = {
                    "rows": rows,
                    "definition": GLOSSARY.get(label, ""),
                }
            except Exception:
                leaders[label] = {"rows": [], "definition": ""}
        return jsonify({
            "teams": trows,
            "leaders": leaders,
            "glossary": dict(GLOSSARY or {}),
            "note": ("Modeled estimates from attributes and production "
                     "\u2014 not tracking data."),
        })
    except Exception:
        return jsonify({"teams": [], "leaders": {}, "glossary": {},
                        "note": ""})


@bp.route("/api/history/season-reviews")
def api_history_season_reviews():
    """Season Reviews tab (desktop _build_season_reviews ~30287):
    per-club archived end-of-season review cards. Query: team, year."""
    from flask import request as _req
    live = _live()
    if live is None:
        return jsonify({"teams": [], "team": "", "years": [],
                        "year": "", "lines": []})
    try:
        gm = _resolve_gm(live)
        league = _safe(lambda: gm.league)
        clubs = [t for t in (_safe(lambda: list(league.teams), []) or [])
                 if getattr(t, "league_name", "") ==
                 "National Hockey League"]
        names = sorted({_safe(lambda: t.team_name, "?") for t in clubs})
        user_name = _safe(lambda: getattr(
            _safe(lambda: gm.user_team), "team_name", ""), "")
        team = (_req.args.get("team") or "").strip()
        if team not in names:
            team = user_name if user_name in names else \
                (names[0] if names else "")
        club = next((t for t in clubs
                     if _safe(lambda: t.team_name, "") == team), None)
        archive = dict(getattr(club, "season_reviews", None) or {}) \
            if club is not None else {}
        years = sorted(archive.keys(), reverse=True)
        labels = [f"{archive[y].get('label', y)} ({y})" for y in years]
        year = (_req.args.get("year") or "").strip()
        if year not in labels:
            year = labels[0] if labels else ""
        lines = []
        if year and years:
            try:
                y = years[labels.index(year)]
                lines = list(archive[y].get("lines", []) or [])
            except (ValueError, IndexError):
                pass
        return jsonify({
            "teams": names, "team": team,
            "years": labels, "year": year, "lines": lines,
            "empty": not lines,
        })
    except Exception:
        return jsonify({"teams": [], "team": "", "years": [],
                        "year": "", "lines": []})


@bp.route("/api/history/awards-full")
def api_history_awards_full():
    """Full awards lists per season (desktop _build_awards ~30554 shows
    every award; the web JS previously truncated to 3)."""
    live = _live()
    hist = _hist(live) if live else None
    if hist is None:
        return jsonify({"years": [], "year": "", "awards": {}})
    try:
        from flask import request as _req
        seasons = _safe(lambda: list(getattr(hist, "seasons", None) or []),
                        []) or []
        years = sorted({s.get("year") for s in seasons
                        if isinstance(s, dict) and s.get("year")},
                       reverse=True)
        try:
            year = int((_req.args.get("year") or "") or 0)
        except (TypeError, ValueError):
            year = 0
        if year not in years:
            year = years[0] if years else 0
        season = _safe(lambda: hist.get_season(year), {}) or {}
        awards = dict(season.get("awards", {}) or {})
        if season.get("conn_smythe"):
            awards = dict(awards)
            awards["Conn Smythe"] = season["conn_smythe"]
        if season.get("champion"):
            awards = dict(awards)
            awards.setdefault("Stanley Cup", season["champion"])
        return jsonify({
            "years": years, "year": year,
            "awards": {str(k): str(v) for k, v in awards.items()},
            "runner_up": season.get("runner_up", ""),
            "series_score": season.get("series_score", ""),
        })
    except Exception:
        return jsonify({"years": [], "year": "", "awards": {}})
