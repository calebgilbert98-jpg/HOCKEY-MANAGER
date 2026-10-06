"""Morale screen: full dressing-room management.

Migrated from Tkinter MoraleView (morale_window.py).
Coaching card, watch list, player response table, dynamics feed,
hierarchy, social groups, rivalries — plus GM actions (Bag Skate,
Speech, Practice, Back Room, Advise Coach, Line Control).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, enqueue_command

bp = Blueprint("morale", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


@bp.route("/morale")
def morale_page():
    return render_template("morale.html")


@bp.route("/api/morale")
def api_morale():
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"error": "no team"}), 503
    roster = _safe(lambda: list(team.roster), []) or []

    try:
        import reputation_system as rs
    except Exception:
        rs = None

    out = {}

    # --- Team chemistry header ---
    if rs is not None:
        try:
            ctx = {"team": team}
            chem = rs.team_chemistry(roster, ctx)
            out["chemistry"] = {
                "score": chem.get("score", 0),
                "label": chem.get("label", ""),
            }
        except Exception:
            out["chemistry"] = {"score": 0, "label": ""}
    else:
        vals = [_safe(lambda: int(getattr(p, "morale", 0) or 0) * 10, 0) for p in roster]
        avg = sum(vals) / len(vals) if vals else 0
        out["chemistry"] = {"score": round(avg), "label": ""}

    # --- Coaching card ---
    coach = None
    if rs is not None:
        try:
            # Find head coach from staff
            staff = _safe(lambda: list(getattr(team, "staff", [])), []) or []
            for s in staff:
                if "head coach" in str(_safe(lambda: getattr(s, "role", ""), "")).lower():
                    coach = s
                    break
        except Exception:
            pass
    if coach is not None and rs is not None:
        try:
            rs.ensure_reputation_fields(coach)
            style = rs.coach_style(coach)
            out["coach"] = {
                "id": _safe(lambda: str(getattr(coach, "id", "")), ""),
                "name": _safe(lambda: getattr(coach, "full_name", "Coach"), "Coach"),
                "style": style.get("label", ""),
                "description": style.get("description", ""),
                "line_control": _safe(lambda: getattr(team, "line_control", "coach"), "coach"),
                "gm_trust": _safe(lambda: int(getattr(coach, "gm_trust", 70)), 70),
            }
        except Exception:
            out["coach"] = None
    else:
        out["coach"] = None

    # --- Watch list (dynamics issues) ---
    if rs is not None and coach is not None:
        try:
            ctx = {"team": team}
            issues = rs.detect_dynamics_issues(team, ctx, roster, coach)
            out["watch_list"] = [
                {"severity": i.get("severity", "low"), "text": i.get("text", "")}
                for i in (issues or [])
            ]
        except Exception:
            out["watch_list"] = []
    else:
        out["watch_list"] = []

    # --- Player response table ---
    players = []
    if rs is not None:
        try:
            ctx = {"team": team}
            hierarchy = rs.team_hierarchy(roster)
            tier_of = {}
            for tier, ps in hierarchy.items():
                for p in ps:
                    tier_of[id(p)] = tier
            for p in sorted(roster, key=lambda x: rs.hierarchy_score(x), reverse=True):
                rs.ensure_reputation_fields(p)
                resp = rs.player_coach_response(p, coach, ctx) if coach else {"label": "Neutral"}
                try:
                    eng = rs.engagement_style(p).get("label", "")
                except Exception:
                    eng = ""
                players.append({
                    "id": _safe(lambda: str(getattr(p, "id", ""))),
                    "name": _safe(lambda: getattr(p, "full_name", "?")),
                    "engagement": eng,
                    "response": resp.get("label", "Neutral"),
                    "happiness": _safe(lambda: int(getattr(p, "happiness", 70) or 0), 70),
                    "morale": _safe(lambda: int(getattr(p, "morale", 0) or 0) * 10, 0),
                    "tier": tier_of.get(id(p), "-"),
                })
        except Exception:
            pass
    if not players:
        # Fallback: basic morale list
        for p in roster:
            players.append({
                "id": _safe(lambda: str(getattr(p, "id", ""))),
                "name": _safe(lambda: getattr(p, "full_name", "?")),
                "engagement": "",
                "response": "Neutral",
                "happiness": 70,
                "morale": _safe(lambda: int(getattr(p, "morale", 0) or 0) * 10, 0),
                "tier": "-",
            })
    out["players"] = players

    # --- Dynamics feed ---
    if rs is not None:
        try:
            feed = rs.get_dynamics_feed(team, limit=25)
            out["feed"] = [
                {"date": e.get("date", ""), "text": e.get("text", ""),
                 "tone": e.get("tone", "")}
                for e in (feed or [])
            ]
        except Exception:
            out["feed"] = []
    else:
        out["feed"] = []

    # --- Hierarchy ---
    if rs is not None:
        try:
            hierarchy = rs.team_hierarchy(roster)
            out["hierarchy"] = [
                {"tier": tier,
                 "names": [_safe(lambda: getattr(p, "full_name", "?")) for p in ps[:5]],
                 "count": len(ps)}
                for tier, ps in hierarchy.items()
            ]
        except Exception:
            out["hierarchy"] = []
    else:
        out["hierarchy"] = []

    return jsonify(out)


@bp.route("/api/morale/action", methods=["POST"])
def api_morale_action():
    """GM dressing-room actions: bag_skate, speech, practice, back_room."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action", "")
    if action not in ("bag_skate", "speech", "practice", "back_room",
                      "advise_coach", "line_control"):
        return jsonify({"ok": False, "error": "bad action"}), 400
    ok = enqueue_command("morale_action", action=action,
                         detail=data.get("detail", ""))
    return jsonify({"ok": ok})
