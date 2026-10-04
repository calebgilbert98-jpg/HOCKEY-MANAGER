"""News screen: league-wide news wire (read-only v1)."""
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe

bp = Blueprint("news", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _news_payload(app):
    """app.news_log -> newest-first JSON-safe list. Never raises."""
    raw = _safe(lambda: list(getattr(app, "news_log", None) or []), []) or []
    items = []
    for entry in raw:
        try:
            if isinstance(entry, dict):
                d = entry.get("date")
                story = entry.get("story", "")
            else:
                # defensive: non-dict entries get a blank date, stringified story
                d, story = None, entry
            if story is None:
                story_text = ""
            else:
                story_text = _safe(lambda: str(story), "") or ""
            if isinstance(d, (date, datetime)):
                date_iso = d.isoformat()
                date_label = d.strftime("%b %d, %Y")
            else:
                date_iso = ""
                date_label = _safe(lambda: str(d), "") or ""
            items.append({
                "date": date_iso,          # sort key (may be "" when unknown)
                "date_label": date_label,  # display label
                "story": story_text,
            })
        except Exception:
            continue
    # newest first; entries without a parseable date sink to the bottom
    try:
        items.sort(key=lambda x: x["date"], reverse=True)
    except Exception:
        items.reverse()
    return {"items": items, "count": len(items)}


@bp.route("/news")
def news_page():
    return render_template("news.html")


@bp.route("/api/news")
def api_news():
    live = _live()
    if live is None:
        return jsonify({"items": [], "count": 0})
    return jsonify(_news_payload(live))
