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

    # --- Social groups (dressing_room cliques) ---
    out["social"] = _social_payload(team, roster)

    # --- Arrival cascades (room log + recent arrivals) ---
    out["cascades"] = _cascades_payload(team, roster)

    # --- Team talk flow (tones, pending talks, speakers) ---
    out["talk"] = _talk_payload(team)

    return jsonify(out)


def _social_payload(team, roster):
    """FM24-style social groups: cliques, floaters, atmosphere."""
    try:
        import dressing_room as _dr
    except Exception:
        return {"cliques": [], "floaters": [], "atmosphere": None}
    try:
        by_id = {}
        for p in roster:
            try:
                by_id[_dr._pid(p)] = p
            except Exception:
                continue
        cliques = []
        for c in _dr.form_cliques(team):
            members = []
            for pid in c.get("member_ids", set()):
                p = by_id.get(pid)
                if p is None:
                    continue
                members.append({
                    "id": _safe(lambda: str(getattr(p, "id", ""))),
                    "name": _safe(lambda: getattr(p, "full_name", "?")),
                    "morale": _safe(lambda: int(getattr(p, "morale", 70) or 70), 70),
                })
            members.sort(key=lambda m: m["name"])
            cliques.append({
                "name": c.get("name", ""),
                "kind": c.get("kind", ""),
                "nationality": c.get("nationality", ""),
                "members": members,
                "bond": c.get("bond", 0),
                "mood": c.get("mood", 70),
                "leader": c.get("leader", "-"),
                "size": c.get("size", len(members)),
                "mean_age": c.get("mean_age"),
            })
        floaters = []
        for f in _dr.floaters(team):
            p = by_id.get(f.get("id"))
            floaters.append({
                "id": _safe(lambda: str(getattr(p, "id", ""))) if p is not None else "",
                "name": f.get("name", "?"),
            })
        try:
            atmo = _dr.room_atmosphere(team)
        except Exception:
            atmo = None
        return {"cliques": cliques, "floaters": floaters, "atmosphere": atmo}
    except Exception:
        return {"cliques": [], "floaters": [], "atmosphere": None}


def _cascades_payload(team, roster):
    """How morale events cascade through the room: the room log plus
    recent arrivals and how settled each one is."""
    try:
        import dressing_room as _dr
    except Exception:
        return {"log": [], "arrivals": []}
    try:
        dr = _dr.ensure_dressing_room_fields(team)
        log = list(dr.get("mood_log", []) or [])[-25:]
        by_id = {}
        for p in roster:
            try:
                by_id[_dr._pid(p)] = p
            except Exception:
                continue
        arrivals = []
        for pid, rec in (dr.get("arrivals", {}) or {}).items():
            p = by_id.get(pid)
            if p is None:
                continue
            arrivals.append({
                "id": _safe(lambda: str(getattr(p, "id", ""))),
                "name": _safe(lambda: getattr(p, "full_name", "?")),
                "integration": _dr.integration_of(team, p),
            })
        arrivals.sort(key=lambda a: a["integration"])
        return {"log": log, "arrivals": arrivals}
    except Exception:
        return {"log": [], "arrivals": []}


TALK_TONES = [
    ("calm", "Calm",
     "Steadies nerves. Best when tied or protecting a lead — and the "
     "tone losing streaks crave."),
    ("fired-up", "Fired Up",
     "Chases a deficit. Electric when trailing or in rivalry games; "
     "reads as panic when comfortably ahead."),
    ("cautious", "Cautious",
     "Protects a lead. Locks in structure — the intermission talk of a "
     "coach sitting on two goals."),
]


def _talk_fit(tone, score_state, situation, rival, streak):
    """Deterministic fit half of give_talk() — mirrored for the preview."""
    try:
        import dressing_room as _dr
        fit = _dr.TONE_FIT.get((tone, score_state), 55)
    except Exception:
        fit = 55
    if streak <= -2 and tone == "calm":
        fit = min(100, fit + 12)
    if rival and tone == "fired-up" and situation == "pregame":
        fit = min(100, fit + 12)
    if score_state == "leading" and tone == "fired-up":
        fit = max(5, fit - 10)
    return fit


def _talk_payload(team):
    try:
        import dressing_room as _dr
    except Exception:
        return {"tones": [], "pending": {}, "speakers": []}
    try:
        dr = _dr.ensure_dressing_room_fields(team)
        pending = {}
        for key in ("pregame", "intermission"):
            rec = dr.get(key)
            pending[key] = {
                "tone": rec.get("tone", ""),
                "speaker": rec.get("speaker", ""),
                "outcome": rec.get("outcome", ""),
                "note": rec.get("note", ""),
            } if isinstance(rec, dict) else None
        cap = _dr.captain_of(team)
        return {
            "tones": [{"key": k, "label": lab, "blurb": blurb}
                      for k, lab, blurb in TALK_TONES],
            "pending": pending,
            "speakers": [
                {"key": "coach", "label": "Head Coach"},
                {"key": "captain",
                 "label": f"Captain ({_dr._name(cap)})" if cap is not None else "Captain"},
            ],
        }
    except Exception:
        return {"tones": [], "pending": {}, "speakers": []}


def _talk_preview_calc(team, tone, situation, score_state, speaker, rival, streak):
    """Mirror give_talk()'s effectiveness math to preview outcome tiers."""
    try:
        import dressing_room as _dr
    except Exception:
        return None
    if tone not in ("calm", "fired-up", "cautious"):
        return None
    if situation not in ("pregame", "intermission"):
        situation = "pregame"
    if score_state not in ("leading", "trailing", "tied"):
        score_state = "tied"
    if speaker == "captain":
        cap = _dr.captain_of(team)
        speaker_inf = _dr.influence_of(cap) if cap is not None else 50
        speaker_name = _dr._name(cap) if cap is not None else "the captain"
    else:
        speaker = "coach"
        speaker_inf = _dr._coach_influence(team)
        speaker_name = "the coach"
    fit = _talk_fit(tone, score_state, situation, rival, streak)
    base = 0.55 * speaker_inf + 0.45 * fit
    lo, hi = base - 10, base + 10

    def tier(e):
        if e >= 78:
            return "landed"
        if e >= 55:
            return "steady"
        if e >= 35:
            return "flat"
        return "backfired"

    tiers = []
    for t in ("landed", "steady", "flat", "backfired"):
        tiers.append(t)
    likely = sorted({tier(lo), tier(hi), tier(base)},
                    key=tiers.index)
    dr = _dr.ensure_dressing_room_fields(team)
    pending = dr.get("intermission") if situation == "intermission" \
        else dr.get("pregame")
    repeat = isinstance(pending, dict)
    return {
        "tone": tone, "situation": situation, "score_state": score_state,
        "speaker": speaker, "speaker_name": speaker_name,
        "speaker_influence": int(speaker_inf),
        "fit": int(fit),
        "effectiveness_range": [round(lo, 1), round(hi, 1)],
        "likely": likely,
        "repeat": repeat,
        "repeat_note": ("The room has already heard today's words for this "
                        "situation — delivering again replaces the pending "
                        "talk but grants no further lift.") if repeat else "",
    }


@bp.route("/api/morale/talk/preview", methods=["POST"])
def api_talk_preview():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    try:
        streak = int(data.get("streak", 0) or 0)
    except (TypeError, ValueError):
        streak = 0
    prev = _talk_preview_calc(
        team,
        str(data.get("tone", "calm") or "calm"),
        str(data.get("situation", "pregame") or "pregame"),
        str(data.get("score_state", "tied") or "tied"),
        str(data.get("speaker", "coach") or "coach"),
        bool(data.get("rival", False)),
        streak,
    )
    if prev is None:
        return jsonify({"ok": False, "error": "bad tone"}), 400
    prev["ok"] = True
    return jsonify(prev)


@bp.route("/api/morale/talk", methods=["POST"])
def api_talk_deliver():
    """Deliver a team talk via the real give_talk() (queued for Tk thread)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    tone = str(data.get("tone", "calm") or "calm")
    if tone not in ("calm", "fired-up", "cautious"):
        return jsonify({"ok": False, "error": "bad tone"}), 400
    situation = str(data.get("situation", "pregame") or "pregame")
    if situation not in ("pregame", "intermission"):
        situation = "pregame"
    score_state = str(data.get("score_state", "tied") or "tied")
    if score_state not in ("leading", "trailing", "tied"):
        score_state = "tied"
    speaker = str(data.get("speaker", "coach") or "coach")
    if speaker not in ("coach", "captain"):
        speaker = "coach"
    try:
        streak = int(data.get("streak", 0) or 0)
    except (TypeError, ValueError):
        streak = 0
    ok = enqueue_command("team_talk", tone=tone, situation=situation,
                         score_state=score_state, speaker=speaker,
                         rival=bool(data.get("rival", False)), streak=streak)
    return jsonify({"ok": ok})


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
