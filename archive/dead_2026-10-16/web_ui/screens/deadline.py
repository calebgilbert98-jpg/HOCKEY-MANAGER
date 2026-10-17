# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Trade Deadline Center: countdown, stance, market, rumors.

Hub-style web port of trade_deadline_center.py (~2000 lines). Prioritizes
the four pillars: countdown to the deadline, buyer/seller stance picker,
trade market (buyers/sellers + impact players), and the rumor feed.

All derived from real league state; buyers/sellers come from actual
standings thirds (the manager's mock-random _identify_buyer_teams is NOT
used). Rumors come from the real media rumor engine (media_rumors.py).
"""
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, _resolve_gm

bp = Blueprint("deadline", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _gm(live):
    return _resolve_gm(live)


def _league(live):
    gm = _gm(live)
    return _safe(lambda: gm.league)


def _deadline_date(league):
    try:
        from trade_deadline_manager import trade_deadline_date
        return trade_deadline_date(league)
    except Exception:
        return None


def _today(gm):
    d = _safe(lambda: gm.current_date)
    try:
        return d.date() if isinstance(d, datetime) else d
    except Exception:
        return date.today()


def _team_points(t):
    try:
        return 2 * int(getattr(t, "wins", 0) or 0) + int(
            getattr(t, "ot_losses", 0) or getattr(t, "otl", 0) or 0)
    except Exception:
        return 0


def _compute_stance(live, league, gm):
    """Buyer/seller/tweener verdict + positional needs + cap space.
    Mirrors TradeDeadlineCenter._compute_stance (~215) on real data."""
    user = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if user is None or league is None:
        return None
    teams = [t for t in (_safe(lambda: list(league.teams), []) or [])
             if hasattr(t, "wins") and hasattr(t, "team_name")]
    ordered = sorted(teams, key=_team_points, reverse=True)
    uname = _safe(lambda: user.team_name, "")
    rank = None
    for i, t in enumerate(ordered):
        if t is user or getattr(t, "team_name", None) == uname:
            rank = i + 1
            break
    n = len(ordered)
    games = (int(getattr(user, "wins", 0) or 0)
             + int(getattr(user, "losses", 0) or 0)
             + int(getattr(user, "ot_losses", 0)
                   or getattr(user, "otl", 0) or 0))
    if rank is None or n < 2 or games == 0:
        verdict, reason = ("TBD",
                           "Season hasn't started \u2014 no standings data yet.")
    elif rank / n <= 1 / 3:
        verdict, reason = ("BUYER",
                           f"{rank} of {n} in the standings \u2014 a contender "
                           "should load up.")
    elif rank / n >= 2 / 3:
        verdict, reason = ("SELLER",
                           f"{rank} of {n} in the standings \u2014 sell "
                           "rentals, stockpile picks.")
    else:
        verdict, reason = ("TWEENER",
                           f"{rank} of {n} in the standings \u2014 one move "
                           "either way.")

    # Positional needs: weakest average OVR groups.
    needs = []
    try:
        groups = {"Forwards": ("C", "LW", "RW"),
                  "Defense": ("LD", "RD", "D"),
                  "Goalies": ("G",)}
        roster = list(getattr(user, "roster", []) or [])
        avgs = []
        for gname, codes in groups.items():
            ovrs = []
            for pl in roster:
                pp = getattr(pl, "primary_position", None)
                code = getattr(pp, "value", str(pp))
                if code in codes:
                    try:
                        ovrs.append(pl.overall_rating())
                    except Exception:
                        pass
            if ovrs:
                avgs.append((gname, sum(ovrs) / len(ovrs), len(ovrs)))
        avgs.sort(key=lambda x: x[1])
        needs = [{"group": g, "avg_ovr": round(a, 1), "count": c}
                 for g, a, c in avgs[:2]]
    except Exception:
        pass

    try:
        cap_space = int(getattr(user, "cap_space", 0) or 0)
    except Exception:
        cap_space = None
    record = ""
    try:
        w = int(getattr(user, "wins", 0) or 0)
        l = int(getattr(user, "losses", 0) or 0)
        otl = int(getattr(user, "ot_losses", 0)
                  or getattr(user, "otl", 0) or 0)
        record = f"{w}-{l}-{otl}"
    except Exception:
        pass
    return {
        "verdict": verdict, "reason": reason,
        "rank": rank, "of": n, "record": record,
        "needs": needs, "cap_space": cap_space,
    }


def _market(live, league, gm):
    """Buyers/sellers from real standings thirds + impact players from
    the real trade market (media_rumors.get_impact_players)."""
    teams = [t for t in (_safe(lambda: list(league.teams), []) or [])
             if hasattr(t, "wins") and hasattr(t, "team_name")]
    ordered = sorted(teams, key=_team_points, reverse=True)
    n = len(ordered)

    def _card(t):
        w = int(getattr(t, "wins", 0) or 0)
        l = int(getattr(t, "losses", 0) or 0)
        otl = int(getattr(t, "ot_losses", 0)
                  or getattr(t, "otl", 0) or 0)
        try:
            cap = int(getattr(t, "cap_space", 0) or 0)
        except Exception:
            cap = None
        return {
            "team": getattr(t, "team_name", "?"),
            "is_user": bool(getattr(t, "is_user_team", False)),
            "record": f"{w}-{l}-{otl}",
            "points": _team_points(t),
            "cap_space": cap,
        }

    buyers = [_card(t) for t in ordered[:max(1, n // 3)]] if n else []
    sellers = [_card(t) for t in ordered[-(max(1, n // 3)):]] \
        if n else []
    sellers.reverse()

    impact = []
    try:
        import media_rumors as mr
        for ip in mr.get_impact_players(game_manager=gm, league=league,
                                        count=8) or []:
            impact.append({
                "name": ip.get("name", "?"),
                "pos": ip.get("pos", ""),
                "team": ip.get("team", ""),
                "status": ip.get("status", ""),
                "value": ip.get("value", ""),
            })
    except Exception:
        pass

    # Recent deadline deals from trade history.
    recent_deals = []
    try:
        hist = _safe(lambda: list(getattr(gm, "trade_history", None)
                                   or []), []) or []
        for ct in reversed(hist[-8:]):
            s = _safe(lambda: str(getattr(ct, "summary", "") or ""), "")
            d = _safe(lambda: str(getattr(ct, "date", "") or ""), "")
            if s:
                recent_deals.append({"summary": s, "date": d})
    except Exception:
        pass
    return {"buyers": buyers, "sellers": sellers, "impact": impact,
            "recent_deals": recent_deals}


@bp.route("/deadline")
def deadline_page():
    return render_template("deadline.html")


@bp.route("/api/deadline")
def api_deadline():
    """Full deadline-center payload: countdown, stance, market, rumors."""
    live = _live()
    if live is None:
        return jsonify({"available": False})
    league = _league(live)
    gm = _gm(live)
    if league is None:
        return jsonify({"available": False})
    try:
        dd = _deadline_date(league)
        today = _today(gm)
        days_left = (dd - today).days if dd and today else None
        is_day = bool(dd and today and dd == today)
        passed = bool(days_left is not None and days_left < 0)

        rumors = []
        try:
            import media_rumors as mr
            from trade_deadline_manager import get_deadline_manager
            dm = get_deadline_manager(gm)
            rumors = mr.generate_rumors(deadline_manager=dm,
                                        game_manager=gm, league=league) or []
        except Exception:
            pass

        declared = _safe(lambda: getattr(league, "_web_deadline_stance",
                                        ""), "") or ""
        return jsonify({
            "available": True,
            "deadline_date": dd.isoformat() if dd else "",
            "deadline_label": dd.strftime("%B %d, %Y") if dd else "TBD",
            "today": today.isoformat() if today else "",
            "days_left": days_left,
            "is_deadline_day": is_day,
            "passed": passed,
            "deadline_hour_et": "3:00 PM ET",
            "stance": _compute_stance(live, league, gm),
            "declared_stance": declared,
            "market": _market(live, league, gm),
            "rumors": rumors,
        })
    except Exception:
        return jsonify({"available": False})


@bp.route("/api/deadline/stance", methods=["POST"])
def api_deadline_stance():
    """Declare your deadline stance (buyer/seller/stand pat).

    Stored on the league (web scratch); the suggested verdict stays
    visible for comparison. Mirrors the desktop stance picker.
    """
    data = request.get_json(force=True, silent=True) or {}
    stance = str(data.get("stance") or "").strip().lower()
    if stance not in ("buyer", "seller", "stand pat", "tweener"):
        return jsonify({"ok": False,
                        "error": "stance must be buyer/seller/stand pat/tweener"}), 400
    live = _live()
    league = _league(live) if live else None
    if league is None:
        return jsonify({"ok": False, "error": "no league"}), 503
    try:
        league._web_deadline_stance = stance
    except Exception:
        return jsonify({"ok": False, "error": "could not save"}), 500
    return jsonify({"ok": True, "stance": stance})
