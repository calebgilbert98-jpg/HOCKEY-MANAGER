"""Trade block screen: players available in trades.

v1: read-only card list of entries on the block (team / position /
overall). Entries may be Player objects or plain dicts -- both are
handled defensively.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, to_web_player

bp = Blueprint("trade_block", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


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


@bp.route("/trade_block")
def trade_block_page():
    return render_template("trade_block.html")


@bp.route("/api/trade_block")
def api_trade_block():
    live = _live()
    if live is None:
        return jsonify({"players": []})
    block = _safe(lambda: list(getattr(live, "trade_block", None) or []), []) or []
    entries = []
    for e in block:
        try:
            entries.append(_to_web_block_entry(e))
        except Exception:
            continue
    try:
        entries.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return jsonify({"players": entries})
