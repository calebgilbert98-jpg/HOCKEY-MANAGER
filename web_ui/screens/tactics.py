"""Team tactics screen: 6 tactic groups + practice planner.

Migrated from Tkinter TacticsView (main.py:25228).
Tactics write straight to the team object and feed the sim engine.
"""
from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("tactics", __name__)

TACTIC_GROUPS = [
    ("Even Strength", "tactic_even_strength", "Balanced",
     ["Very Defensive", "Defensive", "Balanced", "Offensive", "Very Offensive"],
     "5v5 play style"),
    ("Power Play", "tactic_power_play", "Offensive",
     ["Conservative", "Balanced", "Offensive", "Very Offensive"],
     "Man-advantage approach"),
    ("Penalty Kill", "tactic_penalty_kill", "Defensive",
     ["Very Defensive", "Defensive", "Balanced", "Aggressive"],
     "Short-handed defense"),
    ("Line Matching", "tactic_line_matching", "Standard",
     ["Conservative", "Standard", "Aggressive"],
     "Home-ice line deployment vs score state"),
    ("Forecheck", "tactic_forecheck", "2-1-2",
     ["2-1-2", "1-2-2", "1-4"],
     "Pressure scheme when the other team has the puck"),
    ("Offensive Zone", "tactic_offense", "Spread",
     ["Overload", "Umbrella", "Spread", "Crash the Net"],
     "5v5 attacking shape — where your shots come from"),
]

_ES_ATTACK = {'Very Defensive': 0.94, 'Defensive': 0.97, 'Balanced': 1.0,
              'Offensive': 1.04, 'Very Offensive': 1.08}
_ES_DEFENSE = {'Very Defensive': 0.92, 'Defensive': 0.96, 'Balanced': 1.0,
               'Offensive': 1.03, 'Very Offensive': 1.06}
_PP_MULT = {'Conservative': 0.96, 'Balanced': 1.0, 'Offensive': 1.05,
            'Very Offensive': 1.10}
_PK_DIV = {'Very Defensive': 1.10, 'Defensive': 1.05, 'Balanced': 1.0,
           'Aggressive': 0.96}


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _impact_lines(team):
    es = _safe(lambda: getattr(team, 'tactic_even_strength', 'Balanced'), 'Balanced')
    pp = _safe(lambda: getattr(team, 'tactic_power_play', 'Offensive'), 'Offensive')
    pk = _safe(lambda: getattr(team, 'tactic_penalty_kill', 'Defensive'), 'Defensive')
    lm = _safe(lambda: getattr(team, 'tactic_line_matching', 'Standard'), 'Standard')
    fc = _safe(lambda: getattr(team, 'tactic_forecheck', '2-1-2'), '2-1-2')
    off = _safe(lambda: getattr(team, 'tactic_offense', 'Spread'), 'Spread')
    atk = (_ES_ATTACK.get(es, 1.0) - 1.0) * 100
    allowed = (_ES_DEFENSE.get(es, 1.0) - 1.0) * 100
    pp_mult = _PP_MULT.get(pp, 1.05)
    pk_effect = (1.0 / _PK_DIV.get(pk, 1.05) - 1.0) * 100
    return [
        f"Even strength: your chance quality {atk:+.0f}%, chances you allow {allowed:+.0f}%",
        f"Power play ({pp}): chance quality {(pp_mult - 1.0) * 100:+.0f}% (before opponent's PK)",
        f"Penalty kill ({pk}): opponent chances {pk_effect:+.0f}% when shorthanded",
        f"Line matching ({lm}): " + (
            "top lines sheltered when leading, leaned on when trailing" if lm == "Aggressive"
            else "standard rotation" if lm == "Standard"
            else "even ice time regardless of score"),
        f"Forecheck ({fc}): " + (
            "heavy pressure on breakouts, more risk" if fc == "2-1-2"
            else "balanced pressure through the neutral zone" if fc == "1-2-2"
            else "concede the zone, protect the middle"),
        f"Offensive zone ({off}): " + (
            "numbers to the strong side, slot chances" if off == "Overload"
            else "point shots through traffic" if off == "Umbrella"
            else "balanced looks from everywhere" if off == "Spread"
            else "net-front chaos, tips and rebounds"),
    ]


@bp.route("/tactics")
def tactics_page():
    return render_template("tactics.html")


@bp.route("/api/tactics")
def api_tactics():
    live = _live()
    if live is None:
        return jsonify({"groups": [], "impact": []})
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"groups": [], "impact": []})
    groups = []
    for title, attr, default, values, hint in TACTIC_GROUPS:
        current = _safe(lambda: getattr(team, attr, default), default)
        # Ensure the attribute exists on the team
        try:
            if not hasattr(team, attr):
                setattr(team, attr, current)
        except Exception:
            pass
        groups.append({
            "title": title, "attr": attr, "hint": hint,
            "values": values, "current": current,
        })
    return jsonify({"groups": groups, "impact": _impact_lines(team)})


@bp.route("/api/tactics/set", methods=["POST"])
def api_tactics_set():
    """Set a tactic (queues for Tk thread to avoid threading issues)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    attr = data.get("attr", "")
    value = data.get("value", "")
    valid = {a for _, a, _, _, _ in TACTIC_GROUPS}
    if attr not in valid:
        return jsonify({"ok": False, "error": "bad attr"}), 400
    from web_ui.bridge import enqueue_command
    ok = enqueue_command("set_tactic", attr=attr, value=value)
    return jsonify({"ok": ok})


@bp.route("/api/tactics/practice")
def api_practice():
    """Current practice plan."""
    live = _live()
    if live is None:
        return jsonify({})
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    try:
        import dressing_room as _dr
        plan = _dr.ensure_dressing_room_fields(team).get("practice_plan") or {}
        foci = {k: v.get("label", k) for k, v in _dr.PRACTICE_FOCI.items()}
        intensities = {k: v.get("label", k) for k, v in _dr.PRACTICE_INTENSITIES.items()}
        return jsonify({
            "focus": plan.get("focus", "systems"),
            "intensity": plan.get("intensity", "moderate"),
            "bag_skate": bool(plan.get("bag_skate", False)),
            "foci": foci,
            "intensities": intensities,
        })
    except Exception:
        return jsonify({})


@bp.route("/api/tactics/practice", methods=["POST"])
def api_practice_set():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    from web_ui.bridge import enqueue_command
    ok = enqueue_command("set_practice",
                         focus=data.get("focus"),
                         intensity=data.get("intensity"),
                         bag_skate=bool(data.get("bag_skate")))
    return jsonify({"ok": ok})
