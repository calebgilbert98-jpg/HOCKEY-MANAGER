"""Systems: Clutch Factors.

Web port of TRACK C #5 (trackc_clutch_view.py, origin/main).
team_clutch moves close games; this page shows WHAT the inputs are.

PUZZLE RULE (same as desktop): qualitative indicators only -- which
factors are lifting or dragging the room, never exact weights or
magnitudes. Signs come from team_clutch.clutch_breakdown(); the numbers
never reach the screen.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, _resolve_gm

bp = Blueprint("systems_clutch", __name__)

#: What each clutch input IS (design text, verbatim from the desktop view).
_FACTOR_STORIES = {
    "talent": ("Marquee talent",
               "Your best players' big-game pedigree. Stars who have been there tilt close games."),
    "temperament": ("Big-game temperament",
                    "Composure under pressure from your key players \u2014 who wants the puck late."),
    "traits": ("Earned identity",
               "Clutch traits and playoff tags the room has earned over the years."),
    "morale": ("Room state",
               "Morale \u00d7 leadership. A tight room holds its nerve; a fractured one doesn't."),
    "situation": ("Situation",
                  "The room's hunger and circumstance \u2014 contract years, droughts, milestones."),
    "trend": ("Form",
              "How the last stretch went. Winning breeds calm; losing breeds gripping the stick."),
    "heat": ("Matchup heat",
             "Rivalry and occasion. Big-game rooms rise to it; fragile rooms shrink."),
}
_FACTOR_ORDER = ("talent", "temperament", "traits", "morale",
                 "situation", "trend", "heat")


def _live():
    from web_ui.bridge import _web_app_ref, _resolve_gm
    return _web_app_ref


def _team():
    live = _live()
    gm = _resolve_gm(live)
    return _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)


def _sign(term):
    try:
        t = float(term)
    except (TypeError, ValueError):
        return "neutral"
    if t > 0.0005:
        return "lifting"
    if t < -0.0005:
        return "dragging"
    return "neutral"


@bp.route("/systems/clutch")
def clutch_page():
    return render_template("systems_clutch.html")


@bp.route("/api/systems/clutch")
def api_clutch():
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    team = _team()
    if team is None:
        return jsonify({"error": "no team"}), 503
    try:
        import team_clutch as tcl
        breakdown = tcl.clutch_breakdown(team) or {}
    except Exception:
        breakdown = {}
    try:
        total = float(breakdown.get("total", 1.0))
    except (TypeError, ValueError):
        total = 1.0
    # Verdict bands mirror the desktop view; the raw total never leaves.
    if total >= 1.02:
        verdict = {"label": "Clutch edge", "tone": "green",
                   "blurb": "This room tilts tight games its way more often than not."}
    elif total <= 0.98:
        verdict = {"label": "Shaky late", "tone": "red",
                   "blurb": "Close games have been slipping \u2014 the room doesn't hold its nerve yet."}
    else:
        verdict = {"label": "Neutral", "tone": "blue",
                   "blurb": "No strong lean either way; close games are coin flips."}
    factors = []
    for key in _FACTOR_ORDER:
        label, story = _FACTOR_STORIES[key]
        factors.append({"key": key, "label": label, "story": story,
                        "sign": _sign(breakdown.get(key, 0.0))})
    return jsonify({"verdict": verdict, "factors": factors})
