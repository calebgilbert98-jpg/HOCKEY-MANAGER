"""Trade block screen: full 3-tab management.

Tabs (matching Tkinter TradeBlockWindow):
1. Your Trade Block — players you've made available, with filters
   (position, min OVR, max age), bulk add/remove, Shop Player,
   Suggest Value, Simulate Offers, Generate Interest.
2. Trade Interest — AI teams interested in your block players,
   backed by the real league.trade_market store. Decline interest.
3. Other Teams — other clubs' block players; Express Interest,
   Negotiate (jump to Trade Center).

All writes go through the bridge command queue (main thread).
All reads via _safe(). No Tk from Flask.
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player

bp = Blueprint("trade_block", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _enqueue(op, **kw):
    import web_ui.bridge as _b
    cmd = {"op": op}
    cmd.update(kw)
    _b.enqueue_command(cmd)


def _to_web_block_entry(entry):
    """Trade-block entry (Player or dict) -> JSON-safe dict."""
    if isinstance(entry, dict):
        name = _safe(lambda: entry.get("name") or entry.get("full_name") or "?", "?")
        pos = _safe(lambda: entry.get("position") or entry.get("pos") or "?", "?")
        ovr = _safe(lambda: int(entry.get("overall") or entry.get("ovr") or 0), 0)
        sal = _safe(lambda: int(entry.get("salary") or 0), 0)
        age = _safe(lambda: int(entry.get("age") or 0), 0)
        team = _safe(lambda: entry.get("team") or entry.get("team_name") or "", "")
        pid = _safe(lambda: str(entry.get("id") or entry.get("player_id") or ""), "")
    else:
        base = to_web_player(entry)
        name, pos, ovr, sal, age = (base.get("name", "?"), base.get("position", "?"),
                                   base.get("overall", 0), base.get("salary", 0),
                                   base.get("age", 0))
        team = _safe(lambda: getattr(entry, "team_name", "") or "", "")
        pid = base.get("id", "")
    return {
        "id": pid, "name": name, "position": pos, "overall": ovr,
        "salary": sal, "age": age, "team": team,
    }


def _user_block(live):
    """User's trade block players (dedupe by id)."""
    block = _safe(lambda: list(getattr(live, "trade_block", None) or []), []) or []
    seen, out = set(), []
    for p in block:
        try:
            pid = str(getattr(p, "id", "") or "")
        except Exception:
            pid = ""
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        out.append(p)
    return out


def _league_of(live):
    gm = _safe(lambda: getattr(live, "game_manager", None))
    lg = _safe(lambda: getattr(gm, "league", None)) if gm else None
    if lg is None:
        lg = _safe(lambda: getattr(live, "league", None))
    return lg


@bp.route("/trade_block")
def trade_block_page():
    return render_template("trade_block.html")


@bp.route("/api/trade_block")
def api_trade_block():
    """Your block with optional filters: pos, min_ovr, max_age."""
    live = _live()
    if live is None:
        return jsonify({"players": []})
    pos = (request.args.get("pos") or "All").strip()
    try:
        min_ovr = int(request.args.get("min_ovr") or 0)
    except Exception:
        min_ovr = 0
    try:
        max_age = int(request.args.get("max_age") or 0)
    except Exception:
        max_age = 0
    entries = []
    for e in _user_block(live):
        try:
            d = _to_web_block_entry(e)
            if pos != "All":
                pp = (d["position"] or "").upper()
                hit = (pp == pos or
                       (pos == "W" and pp in ("LW", "RW")) or
                       (pos == "D" and pp in ("LD", "RD")))
                if not hit:
                    continue
            if min_ovr and d["overall"] < min_ovr:
                continue
            if max_age and d["age"] > max_age:
                continue
            entries.append(d)
        except Exception:
            continue
    try:
        entries.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return jsonify({"players": entries})


@bp.route("/api/trade_block/interest")
def api_trade_block_interest():
    """AI interest in your block players from the real trade_market store."""
    live = _live()
    if live is None:
        return jsonify({"interest": []})
    out = []
    try:
        import trade_market as tm
        league = _league_of(live)
        if league is None:
            return jsonify({"interest": []})
        market = tm.get_market(league)
        listings = _safe(lambda: list(market.get("listings", []) or []), []) or []
        my_name = _safe(lambda: getattr(getattr(live, "user_team", None),
                                        "team_name", ""), "")
        for li in listings:
            try:
                if not isinstance(li, dict):
                    continue
                if li.get("source") != "user_block":
                    continue
                seller = li.get("seller") or li.get("team") or ""
                if my_name and seller and seller != my_name:
                    continue
                pname = li.get("player_name") or ""
                for r in (li.get("ai_interest") or []):
                    if not isinstance(r, dict):
                        continue
                    if r.get("status") == "Declined":
                        continue
                    out.append({
                        "player": pname,
                        "player_id": str(li.get("player_id") or ""),
                        "team": r.get("team", ""),
                        "interest": r.get("interest") or r.get("level") or "",
                        "status": r.get("status") or "Open",
                    })
            except Exception:
                continue
    except Exception:
        pass
    return jsonify({"interest": out})


@bp.route("/api/trade_block/others")
def api_trade_block_others():
    """Other teams' trade-block players (from trade_market listings)."""
    live = _live()
    if live is None:
        return jsonify({"players": []})
    out = []
    try:
        import trade_market as tm
        league = _league_of(live)
        my_name = _safe(lambda: getattr(getattr(live, "user_team", None),
                                        "team_name", ""), "")
        if league is not None:
            market = tm.get_market(league)
            listings = _safe(lambda: list(market.get("listings", []) or []),
                             []) or []
            for li in listings:
                try:
                    if not isinstance(li, dict):
                        continue
                    seller = li.get("seller") or li.get("team") or ""
                    if not seller or (my_name and seller == my_name):
                        continue
                    if (li.get("source") or "") not in ("ai_block",
                                                        "team_block",
                                                        "block"):
                        continue
                    out.append({
                        "player": li.get("player_name") or "?",
                        "player_id": str(li.get("player_id") or ""),
                        "team": seller,
                        "position": li.get("position") or "?",
                        "overall": int(li.get("overall") or 0),
                    })
                except Exception:
                    continue
    except Exception:
        pass
    if not out:
        try:
            league = _league_of(live)
            my_name = _safe(lambda: getattr(getattr(live, "user_team", None),
                                            "team_name", ""), "")
            for t in (_safe(lambda: list(getattr(league, "teams", None) or []),
                            []) or []):
                try:
                    tn = _safe(lambda: getattr(t, "team_name", ""), "")
                    if not tn or tn == my_name:
                        continue
                    for p in (_safe(lambda: list(getattr(t, "trade_block", None)
                                                 or []), []) or []):
                        d = _to_web_block_entry(p)
                        out.append({"player": d["name"], "player_id": d["id"],
                                    "team": tn, "position": d["position"],
                                    "overall": d["overall"]})
                except Exception:
                    continue
        except Exception:
            pass
    try:
        out.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return jsonify({"players": out})


@bp.route("/api/trade_block/shop")
def api_trade_block_shop():
    """Shop Player: value + interested teams for one block player."""
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    pid = str(request.args.get("player_id") or "")
    target = None
    for p in _user_block(live):
        try:
            if str(getattr(p, "id", "")) == pid:
                target = p
                break
        except Exception:
            continue
    if target is None:
        return jsonify({"error": "player not on block"}), 404
    try:
        base_value = int(_safe(lambda: live.calculate_player_value(target), 0)
                         or 0)
    except Exception:
        base_value = 0
    discounted = int(base_value * 0.85)
    name = _safe(lambda: getattr(target, "full_name", "?"), "?")
    interested = []
    try:
        import trade_market as tm
        league = _league_of(live)
        if league is not None:
            market = tm.get_market(league)
            for li in (_safe(lambda: list(market.get("listings", []) or []),
                             []) or []):
                try:
                    if not isinstance(li, dict):
                        continue
                    if str(li.get("player_id") or "") != pid:
                        continue
                    for r in (li.get("ai_interest") or []):
                        if isinstance(r, dict) and r.get("status") != "Declined":
                            interested.append({
                                "team": r.get("team", ""),
                                "interest": r.get("interest") or r.get("level") or "",
                            })
                except Exception:
                    continue
    except Exception:
        pass
    return jsonify({
        "player": name, "player_id": pid,
        "market_value": base_value, "block_value": discounted,
        "interested": interested,
    })


@bp.route("/api/trade_block/suggest")
def api_trade_block_suggest():
    """Suggest Trade Value: valuation for block players."""
    live = _live()
    if live is None:
        return jsonify({"players": []})
    pids = [p for p in (request.args.get("player_ids") or "").split(",") if p]
    out = []
    for p in _user_block(live):
        try:
            pid = str(getattr(p, "id", ""))
            if pids and pid not in pids:
                continue
            base = int(_safe(lambda: live.calculate_player_value(p), 0) or 0)
            out.append({
                "player_id": pid,
                "player": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "market_value": base,
                "block_value": int(base * 0.85),
            })
        except Exception:
            continue
    return jsonify({"players": out})


# --- Write ops: all queue to the Tk main thread ---------------------------


@bp.route("/api/trade_block/add", methods=["POST"])
def api_trade_block_add():
    data = request.get_json(force=True, silent=True) or {}
    pids = data.get("player_ids") or []
    if isinstance(pids, str):
        pids = [pids]
    for pid in pids:
        _enqueue("trade_block_add", player_id=str(pid))
    return jsonify({"ok": True, "queued": len(pids)})


@bp.route("/api/trade_block/remove", methods=["POST"])
def api_trade_block_remove():
    data = request.get_json(force=True, silent=True) or {}
    pids = data.get("player_ids") or []
    if isinstance(pids, str):
        pids = [pids]
    for pid in pids:
        _enqueue("trade_block_remove", player_id=str(pid))
    return jsonify({"ok": True, "queued": len(pids)})


@bp.route("/api/trade_block/simulate_offers", methods=["POST"])
def api_trade_block_simulate_offers():
    _enqueue("trade_block_simulate_offers")
    return jsonify({"ok": True})


@bp.route("/api/trade_block/generate_interest", methods=["POST"])
def api_trade_block_generate_interest():
    _enqueue("trade_block_generate_interest")
    return jsonify({"ok": True})


@bp.route("/api/trade_block/decline_interest", methods=["POST"])
def api_trade_block_decline_interest():
    data = request.get_json(force=True, silent=True) or {}
    _enqueue("trade_block_decline_interest",
             player=data.get("player") or "",
             team=data.get("team") or "")
    return jsonify({"ok": True})


@bp.route("/api/trade_block/express_interest", methods=["POST"])
def api_trade_block_express_interest():
    data = request.get_json(force=True, silent=True) or {}
    _enqueue("trade_block_express_interest",
             player=data.get("player") or "",
             team=data.get("team") or "",
             player_id=str(data.get("player_id") or ""))
    return jsonify({"ok": True})
