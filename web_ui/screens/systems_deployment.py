"""Systems: Ice-Time Deployment.

Web port of TRACK C #1 (trackc_deployment_view.py, origin/main).
Read-only over deployment_policy: the coach's deployment policy in
effect (style, concentration, soft-cap triggers), per-line deployment
shares for a neutral (0-0, 1st period) game state, honored GM advice,
and the cap exceptions. Numbers come straight from
deployment_policy.deployment_weights; nothing here simulates.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe

bp = Blueprint("systems_deployment", __name__)

#: Neutral game state: the coach's BASE policy, before score/clock tilt it.
_NEUTRAL_STATE = {
    "score_diff": 0, "period": 1, "clock": 1200.0,
    "is_playoff": False, "must_win": False, "bench_short": False,
    "ot_marathon": False, "is_home": True,
}

_GROUPS = [
    ("F", "Forwards", ["L1", "L2", "L3", "L4"]),
    ("D", "Defense", ["Pair 1", "Pair 2", "Pair 3"]),
    ("PP", "Power play", ["PP1", "PP2"]),
    ("PK", "Penalty kill", ["PK1", "PK2"]),
]

_CONC_LABELS = [
    (0.70, "Rides the top units (star-heavy)"),
    (0.55, "Leans on the top units"),
    (0.38, "Balanced deployment"),
    (0.00, "Rolls four lines / three pairs"),
]


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _team():
    live = _live()
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)


def _concentration_label(c):
    for cutoff, label in _CONC_LABELS:
        if c >= cutoff:
            return label
    return "Balanced deployment"


@bp.route("/systems/deployment")
def deployment_page():
    return render_template("systems_deployment.html")


@bp.route("/api/systems/deployment")
def api_deployment():
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    team = _team()
    if team is None:
        return jsonify({"error": "no team"}), 503
    out = {"coach_name": "?", "style_key": "balanced", "style_label": "Balanced",
           "family": "balanced", "groups": [], "concentration": None,
           "concentration_label": "", "overload": False,
           "cap_exceptions": [], "advice": []}
    try:
        import deployment_policy as dp
        coach = _safe(lambda: dp._head_coach_for(team))
        if coach is not None:
            out["coach_name"] = (
                f"{_safe(lambda: getattr(coach, 'first_name', ''), '')} "
                f"{_safe(lambda: getattr(coach, 'last_name', ''), '')}").strip() or "?"
            try:
                import reputation_system as rs
                cs = rs.coach_style(coach) if coach is not None else {}
                out["style_key"] = (cs or {}).get("key", "balanced")
                out["style_label"] = (cs or {}).get("label", "Balanced")
            except Exception:
                pass
        try:
            import tactics as tx
            out["family"] = tx.team_family(team) or "balanced"
        except Exception:
            pass
        family = out["family"] if out["family"] in (
            "pressure", "structure", "balanced") else "balanced"
        try:
            w = dp.deployment_weights(team, {"key": out["style_key"]},
                                      family, dict(_NEUTRAL_STATE)) or {}
            meta = w.get("meta", {}) or {}
            conc = meta.get("concentration")
            if conc is not None:
                out["concentration"] = round(float(conc), 3)
                out["concentration_label"] = _concentration_label(float(conc))
            out["overload"] = bool(meta.get("overload"))
            for key, title, labels in _GROUPS:
                shares = w.get(key) or []
                rows = []
                for label, share in zip(labels, shares):
                    try:
                        s = float(share)
                    except (TypeError, ValueError):
                        s = 0.0
                    rows.append({"label": label, "share": round(s, 3)})
                if rows:
                    out["groups"].append({"key": key, "title": title, "rows": rows})
        except Exception:
            pass
        try:
            exc = dp.soft_cap_exceptions(dict(_NEUTRAL_STATE)) or {}
            out["cap_exceptions"] = sorted(
                str(k) for k, v in exc.items() if v)
        except Exception:
            pass
        try:
            adv = dp._honored_advice(team) or {}
            keys = adv.get("keys", set()) if isinstance(adv, dict) else set()
            label_of = {v: k for k, v in
                        getattr(dp, "_ADVICE_LABELS", {}).items()}
            out["advice"] = sorted(
                str(label_of.get(k, k)).capitalize() for k in keys)
        except Exception:
            pass
    except Exception:
        pass
    return jsonify(out)
