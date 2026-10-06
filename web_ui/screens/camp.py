"""Camp screen: training camp report card (storylines timeline)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe

bp = Blueprint("camp", __name__)

# Training camp window (training_camp.py CAMP_START=(9,12), runs Sep 12-30).
CAMP_LABEL = "Sep 12 – 30"


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _date_str(d):
    try:
        return d.strftime("%b %d")
    except Exception:
        return str(d) if d is not None else ""


def _story_entries(stories):
    out = []
    for s in stories or []:
        try:
            if isinstance(s, dict):
                d, story = s.get("date"), s.get("story")
            elif isinstance(s, (list, tuple)) and len(s) >= 2:
                d, story = s[0], s[1]
            else:
                continue
            text = str(story or "").strip()
            if not text:
                continue
            out.append({"date": _date_str(d), "story": text})
        except Exception:
            continue
    return out


def get_camp(live):
    """JSON-safe payload: camp storyline timeline + roster note."""
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) if gm is not None else None
    stories = _safe(lambda: league.preseason_stories, []) if league else []
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    roster_size = _safe(lambda: len(team.roster or []), 0) if team else 0
    return {
        "camp_window": CAMP_LABEL,
        "stories": _story_entries(stories),
        "roster_size": roster_size,
    }


@bp.route("/camp")
def camp_page():
    return render_template("camp.html")


@bp.route("/api/camp")
def api_camp():
    live = _live()
    if live is None:
        return jsonify({"camp_window": CAMP_LABEL, "stories": [],
                        "roster_size": 0})
    return jsonify(_safe(lambda: get_camp(live),
                         {"camp_window": CAMP_LABEL, "stories": [],
                          "roster_size": 0}))
