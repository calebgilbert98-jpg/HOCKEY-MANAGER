"""Morale screen: full dressing-room management.

Migrated from Tkinter MoraleView (morale_window.py).
Coaching card, watch list, player response table, dynamics feed,
hierarchy, social groups, rivalries — plus GM actions (Bag Skate,
Speech, Practice, Back Room, Advise Coach, Line Control).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, _staff_role_str, enqueue_command, _resolve_gm

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
    gm = _resolve_gm(live)
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
                if "head coach" in _staff_role_str(s).lower():
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
    gm = _resolve_gm(live)
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


# ----------------------------------------------------------------------
# Batch B: captaincy crisis, advise-coach, rivalries, coach carousel.
# ----------------------------------------------------------------------

def _dr_module():
    try:
        import dressing_room as _dr
        return _dr
    except Exception:
        return None


def _rs_module():
    try:
        import reputation_system as _rs
        return _rs
    except Exception:
        return None


def _team_league():
    live = _live()
    if live is None:
        return None, None, None
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    return live, team, league


@bp.route("/api/morale/crisis")
def api_crisis():
    """Captaincy-crisis banner state: the persisted crisis flag (set by the
    weekly dressing-room tick) else a live detection. Plus named successor
    candidates for the reassign path and recent authority receipts."""
    live, team, league = _team_league()
    if team is None:
        return jsonify({"crisis": None})
    _dr = _dr_module()
    detail = {}
    try:
        dr = _dr.ensure_dressing_room_fields(team) if _dr else {}
        if dr.get("captaincy_crisis"):
            detail = dict(dr.get("captaincy_crisis_detail") or {})
    except Exception:
        detail = {}
    if not detail and _dr is not None:
        try:
            crisis = _dr.detect_captaincy_crisis(team, league)
            if crisis is not None:
                detail = {
                    "captain_name": crisis.get("captain_name", ""),
                    "challenger_names": crisis.get("challenger_names") or [],
                    "severity": crisis.get("severity", 1),
                }
        except Exception:
            pass
    crisis = None
    if detail:
        # Named successors: challengers first, else highest-influence.
        succ = []
        try:
            roster = list(getattr(team, "roster", None) or [])
            names = [n for n in (detail.get("challenger_names") or []) if n]
            by_name = {}
            for p in roster:
                try:
                    by_name[_dr._name(p)] = p
                except Exception:
                    continue
            matched = [by_name[n] for n in names if n in by_name]
            if not matched:
                cap = _dr.captain_of(team)
                ranked = sorted(
                    (p for p in roster if p is not cap),
                    key=lambda p: _dr.influence_of(p), reverse=True)
                matched = ranked[:3]
            for p in matched[:4]:
                succ.append({
                    "id": _safe(lambda: str(getattr(p, "id", "")), ""),
                    "name": _safe(lambda: _dr._name(p), "?"),
                })
        except Exception:
            succ = []
        crisis = {
            "captain_name": detail.get("captain_name", ""),
            "challenger_names": detail.get("challenger_names") or [],
            "severity": detail.get("severity", 1),
            "successors": succ,
        }
    # Authority receipts (crisis resolutions, firings, hires).
    receipts = []
    try:
        dr = _dr.ensure_dressing_room_fields(team) if _dr else {}
        for rec in reversed(list(dr.get("practice_receipts") or [])):
            if not isinstance(rec, dict) or rec.get("kind") != "authority":
                continue
            receipts.append({
                "date": rec.get("date", ""),
                "title": rec.get("title", ""),
                "choice": rec.get("choice", ""),
                "gained": rec.get("gained") or [],
                "paid": rec.get("paid") or [],
                "relationships": rec.get("relationships") or [],
                "goal_met": rec.get("goal_met"),
            })
            if len(receipts) >= 5:
                break
    except Exception:
        receipts = []
    return jsonify({"crisis": crisis, "receipts": receipts})


@bp.route("/api/morale/crisis/resolve", methods=["POST"])
def api_crisis_resolve():
    """Resolve a captaincy crisis: keep | challenge | strip | reassign."""
    live, team, league = _team_league()
    if team is None:
        return jsonify({"ok": False, "error": "no team"}), 503
    data = request.get_json(force=True, silent=True) or {}
    choice = str(data.get("choice", "") or "")
    if choice not in ("keep", "challenge", "strip", "reassign"):
        return jsonify({"ok": False, "error": "bad choice"}), 400
    if choice == "reassign" and not data.get("new_captain_id"):
        # Never silently auto-strip the C (desktop rule).
        return jsonify({"ok": False,
                        "error": "reassign needs a named successor"}), 400
    ok = enqueue_command("resolve_captaincy_crisis", choice=choice,
                         new_captain_id=str(data.get("new_captain_id") or ""))
    return jsonify({"ok": ok})


@bp.route("/api/morale/advice-result")
def api_advice_result():
    """Poll the outcome of the last morale write (advice / rivalry /
    crisis / coach-carousel): the confirmation the desktop shows in its
    result label."""
    live = _live()
    if live is None:
        return jsonify({"result": None})
    return jsonify({"result": _safe(lambda: getattr(
        live, "_web_morale_result", None))})


@bp.route("/api/morale/advice-types")
def api_advice_types():
    """The 7 GM advice types, coach trust, currently-featured player."""
    live, team, league = _team_league()
    if team is None:
        return jsonify({"types": [], "coach": None})
    _rs = _rs_module()
    types = []
    if _rs is not None:
        try:
            types = [{"key": k, "label": v}
                     for k, v in _rs.ADVICE_TYPES.items()]
        except Exception:
            pass
    coach = None
    for s in list(getattr(team, "staff", None) or []):
        try:
            if "head coach" in _staff_role_str(s).lower():
                coach = s
                break
        except Exception:
            continue
    featured = None
    if coach is not None and _rs is not None:
        try:
            _rs.ensure_reputation_fields(coach)
        except Exception:
            pass
    for p in list(getattr(team, "roster", None) or []):
        try:
            if getattr(p, "usage_featured", False):
                featured = {
                    "id": _safe(lambda: str(getattr(p, "id", "")), ""),
                    "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                }
                break
        except Exception:
            continue
    line_control = _safe(lambda: getattr(team, "line_control", "coach"),
                         "coach")
    return jsonify({
        "types": types,
        "coach": ({"name": _safe(lambda: getattr(coach, "full_name", "Coach"),
                                "Coach"),
                   "gm_trust": _safe(lambda: int(getattr(
                       coach, "gm_trust", 70) or 70), 70)}
                  if coach is not None else None),
        "featured": featured,
        "line_control": line_control,
    })


@bp.route("/api/morale/rivalries")
def api_rivalries():
    """Rivalry panel (desktop MoraleView._refresh_rivalries parity): coach
    beefs, team rivalries, loudest player beefs, declared rivals -- plus
    the team picker for new declarations."""
    live, team, league = _team_league()
    if team is None or league is None:
        return jsonify({"entries": [], "teams": [], "declared": []})
    _rs = _rs_module()
    entries, declared = [], []
    if _rs is not None:
        try:
            rivalries = list(getattr(league, "rivalries", []) or [])
            tname = getattr(team, "team_name", "")
            # Coach beefs
            coach = None
            for s in list(getattr(team, "staff", None) or []):
                try:
                    if "head coach" in _staff_role_str(s).lower():
                        coach = s
                        break
                except Exception:
                    continue
            cname = getattr(coach, "full_name", "") if coach else ""
            for r in _rs.get_rivalries_for(rivalries, coach)[:3] \
                    if coach is not None else []:
                other = (r["b_name"] if r["a_name"] == cname
                         else r["a_name"])
                entries.append({
                    "category": "coach", "label": other,
                    "intensity": round(r.get("intensity", 0)),
                    "origin": str(r.get("origin", "")).replace("_", " "),
                    "solidified": bool(r.get("solidified")),
                })
            # Team rivalries
            team_rs = [r for r in rivalries
                       if r.get("kind") == "team_team"
                       and (r.get("a", (None, ""))[1] == tname
                            or r.get("b", (None, ""))[1] == tname)]
            team_rs.sort(key=lambda r: -r.get("intensity", 0))
            for r in team_rs[:3]:
                other = (r["b_name"] if r.get("a", (None, ""))[1] == tname
                         else r["a_name"])
                entries.append({
                    "category": "team", "label": other,
                    "intensity": round(r.get("intensity", 0)),
                    "origin": str(r.get("origin", "")).replace("_", " "),
                    "solidified": bool(r.get("solidified")),
                })
            # Loudest player beefs on the roster
            beefs = []
            for p in list(getattr(team, "roster", None) or []):
                beefs += _rs.get_rivalries_for(rivalries, p)
            beefs.sort(key=lambda r: -r.get("intensity", 0))
            for r in beefs[:2]:
                entries.append({
                    "category": "player",
                    "label": f"{r['a_name']} vs {r['b_name']}",
                    "intensity": round(r.get("intensity", 0)),
                    "origin": str(r.get("origin", "")).replace("_", " "),
                    "solidified": bool(r.get("solidified")),
                })
            # GM-declared (renounceable)
            my_keys = {("team", tname), ("gm", tname)}
            for r in _rs.declared_rivalries_for(rivalries, team):
                other = (r["b_name"] if r.get("a") in my_keys
                         else r["a_name"])
                kind = ("team" if r.get("kind") == "team_team"
                        else "coach")
                declared.append({
                    "label": other, "kind": kind,
                    "intensity": round(r.get("intensity", 0)),
                })
        except Exception:
            pass
    teams = []
    try:
        tname = getattr(team, "team_name", "")
        teams = sorted(
            str(getattr(t, "team_name", ""))
            for t in (getattr(league, "teams", []) or [])
            if getattr(t, "team_name", "") and getattr(t, "team_name", "")
            != tname)
    except Exception:
        pass
    return jsonify({"entries": entries, "teams": teams,
                    "declared": declared})


@bp.route("/api/morale/rivalries/declare", methods=["POST"])
def api_rivalry_declare():
    """Declare a team rival or a personal beef with an opposing head coach."""
    live, team, league = _team_league()
    if team is None or league is None:
        return jsonify({"ok": False, "error": "no game"}), 503
    data = request.get_json(force=True, silent=True) or {}
    kind = str(data.get("kind", "team") or "team")
    target = str(data.get("target", "") or "")
    if kind not in ("team", "coach") or not target:
        return jsonify({"ok": False, "error": "kind and target required"}), 400
    ok = enqueue_command("declare_rivalry", kind=kind, target=target)
    return jsonify({"ok": ok})


@bp.route("/api/morale/rivalries/renounce", methods=["POST"])
def api_rivalry_renounce():
    """Renounce a live GM-declared rivalry."""
    live, team, league = _team_league()
    if team is None or league is None:
        return jsonify({"ok": False, "error": "no game"}), 503
    data = request.get_json(force=True, silent=True) or {}
    kind = str(data.get("kind", "team") or "team")
    target = str(data.get("target", "") or "")
    if kind not in ("team", "coach") or not target:
        return jsonify({"ok": False, "error": "kind and target required"}), 400
    ok = enqueue_command("renounce_rivalry", kind=kind, target=target)
    return jsonify({"ok": ok})


@bp.route("/api/morale/coach/candidates")
def api_coach_candidates():
    """Coach carousel: current chair (style, trust, hot seat) + candidates
    (retreads, specialists, fresh-blood coordinators)."""
    live, team, league = _team_league()
    if team is None:
        return jsonify({"current": None, "candidates": [], "hot_seat": None})
    _dr = _dr_module()
    _rs = _rs_module()
    current, candidates, hot = None, [], None
    try:
        coach = _dr._room_head_coach(team) if _dr else None
        if coach is not None:
            style = _rs.coach_style(coach) if _rs else {}
            try:
                axis = _dr.coach_demanding_axis(coach)
                ax = ("Demanding" if axis >= 0.7 else "Players' coach"
                      if axis <= 0.3 else "Balanced")
            except Exception:
                ax = ""
            current = {
                "id": _safe(lambda: str(getattr(coach, "id", "")), ""),
                "name": _safe(lambda: getattr(
                    coach, "name", getattr(coach, "full_name", "Coach")),
                    "Coach"),
                "style": _safe(lambda: style.get("label", ""), ""),
                "style_key": _safe(lambda: style.get("key", ""), ""),
                "axis": ax,
                "gm_trust": _safe(lambda: int(getattr(
                    coach, "gm_trust", 70) or 70), 70),
                "shelf_weeks": _safe(lambda: int(getattr(
                    coach, "shelf_weeks", 0) or 0), 0),
            }
    except Exception:
        current = None
    try:
        if _dr is not None:
            for i, c in enumerate(_dr.coaching_candidates(team)):
                candidates.append({
                    "idx": i,
                    "name": c.get("name", "?"),
                    "source": c.get("source", ""),
                    "archetype": c.get("archetype", ""),
                    "style": c.get("style", ""),
                    "hot_seat": c.get("hot_seat", 0),
                    "note": c.get("note", ""),
                })
    except Exception:
        candidates = []
    try:
        # Read-only: surface the hot-seat state the weekly tick already
        # computed. Never run coach_hot_seat_check() from a GET -- it can
        # apply trust drift (a write).
        if _dr is not None:
            dr = _dr.ensure_dressing_room_fields(team)
            hot = dr.get("coach_hot_seat")
    except Exception:
        hot = None
    return jsonify({"current": current, "candidates": candidates,
                    "hot_seat": hot})


@bp.route("/api/morale/coach/fire", methods=["POST"])
def api_coach_fire():
    """Fire the head coach: carousel memory, room reaction, receipt."""
    live, team, league = _team_league()
    if team is None:
        return jsonify({"ok": False, "error": "no team"}), 503
    data = request.get_json(force=True, silent=True) or {}
    reason = str(data.get("reason", "fired") or "fired")
    if reason not in ("fired", "resigned", "mutual"):
        reason = "fired"
    ok = enqueue_command("fire_coach", reason=reason)
    return jsonify({"ok": ok})


@bp.route("/api/morale/coach/hire", methods=["POST"])
def api_coach_hire():
    """Hire a carousel candidate (idx from /api/morale/coach/candidates)."""
    live, team, league = _team_league()
    if team is None:
        return jsonify({"ok": False, "error": "no team"}), 503
    data = request.get_json(force=True, silent=True) or {}
    try:
        idx = int(data.get("candidate_idx", -1))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "bad candidate"}), 400
    ok = enqueue_command("hire_coach", candidate_idx=idx)
    return jsonify({"ok": ok})
