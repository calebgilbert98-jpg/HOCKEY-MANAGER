"""Development screen: active training programs + prospect watchlist.

Batch D (2026-10-05): ports the desktop Development Center's write
capabilities -- per-player "Assign Training Program", per-player drills
(Practice Center), "Coach Runs Practice", positional training, and
offseason (summer) programs. Reads come from /api/development; writes
enqueue commands for the Tk thread (bridge._execute_command) and poll
app._web_dev_result via /api/development/result.
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player, _player_ovr

bp = Blueprint("development", __name__)

# Development-Center vocabulary (desktop parity):
# enhanced_practice_system.FOCUS_TO_PRACTICE_TYPE / INTENSITY_LABEL_TO_ENUM
_DEV_FOCUSES = [
    "Skating & Speed", "Shooting Accuracy", "Passing & Vision",
    "Defensive Positioning", "Physical Conditioning", "Mental Toughness",
    "Position-Specific Skills", "Hockey IQ Development",
]
_DEV_INTENSITIES = ["Light", "Standard", "Intensive"]


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _as_dict(v):
    return v if isinstance(v, dict) else {}


def _date_str(d):
    try:
        return d.strftime("%b %d, %Y")
    except Exception:
        return str(d) if d is not None else ""


def _program_sources(live):
    """All known homes for training-program data, most specific first."""
    out = []
    out.append(_safe(lambda: live.training_programs))
    gm = _safe(lambda: live.game_manager)
    if gm is not None:
        out.append(_safe(lambda: gm.training_programs))
    try:
        from enhanced_practice_system import ACTIVE_TRAINING_PROGRAMS
        out.append(_safe(lambda: dict(ACTIVE_TRAINING_PROGRAMS)))
    except Exception:
        pass
    return out


def _player_index(players):
    """id -> player, keyed by both raw and stringified ids."""
    idx = {}
    for p in players or []:
        try:
            pid = getattr(p, "id", None)
        except Exception:
            continue
        for key in (pid, str(pid)):
            try:
                if key is not None and key not in idx:
                    idx[key] = p
            except Exception:
                continue
    return idx


def _squads(live):
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return [], []
    roster = _safe(lambda: list(team.roster or []), []) or []
    farm = _safe(lambda: list(getattr(team, "ahl_roster", None) or []), []) or []
    return roster, farm


def _resolve_player(pid, idx):
    for key in (pid, str(pid)):
        p = idx.get(key)
        if p is not None:
            return p
    try:
        return idx.get(int(pid))
    except Exception:
        return None


def _team_prospects(live):
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    return _safe(lambda: list(getattr(team, "prospects", None) or []), []) or []


@bp.route("/development")
def development_page():
    return render_template("development.html")


@bp.route("/api/development")
def api_development():
    live = _live()
    if live is None:
        return jsonify({"programs": [], "prospects": []})
    return jsonify(_safe(lambda: get_development(live),
                         {"programs": [], "prospects": []}))


# ------------------------------------------------------------------
# Batch D: assignment catalogs, per-player practice state, offseason
# gate, and the write endpoints (enqueue -> poll).
# ------------------------------------------------------------------

def _dev_engine():
    try:
        from web_ui.bridge import _batchd_engine
        return _batchd_engine()
    except Exception:
        return None


def _dev_practice_catalog():
    """Drills, intensities and fatigue costs (engine truth)."""
    try:
        from enhanced_practice_system import PracticeType, PracticeIntensity
    except Exception:
        return {"drills": [], "intensities": []}
    engine = _dev_engine()
    drills = []
    for pt in PracticeType:
        attrs = []
        if engine is not None:
            try:
                attrs = sorted(
                    (engine.practice_effectiveness.get(pt) or {}).keys())
            except Exception:
                attrs = []
        costs = {}
        if engine is not None:
            for pi in PracticeIntensity:
                try:
                    costs[pi.value] = engine._calculate_fatigue_cost(pi, 60)
                except Exception:
                    pass
        drills.append({
            "key": pt.value,
            "label": pt.value.replace("_", " ").title(),
            "trains": attrs[:6],
        })
    return {
        "drills": drills,
        "intensities": [pi.value for pi in PracticeIntensity],
        "fatigue_costs": costs,
    }


def _dev_offseason(live):
    """Desktop gating parity: assignable Jun-Aug (is_offseason)."""
    try:
        from datetime import date
        import offseason_programs as _osp
        game_date = _safe(lambda: getattr(live, "current_date", None)) \
            or date.today()
        return {
            "assignable": bool(_osp.is_offseason(game_date)),
            "month": int(getattr(game_date, "month", 0) or 0),
        }
    except Exception:
        return {"assignable": False, "month": 0}


def _dev_players(live, roster, farm, prospects):
    """Assignable player cards: fatigue, program, position training."""
    engine = _dev_engine()
    try:
        from enhanced_practice_system import ACTIVE_TRAINING_PROGRAMS
    except Exception:
        ACTIVE_TRAINING_PROGRAMS = {}
    try:
        import offseason_programs as _osp
    except Exception:
        _osp = None
    try:
        import position_training as _pt
    except Exception:
        _pt = None

    gm = _safe(lambda: live.game_manager)
    gm_programs = _safe(lambda: gm.training_programs, {}) or {}
    prog_ids = set()
    for src in (gm_programs, ACTIVE_TRAINING_PROGRAMS):
        try:
            for k in src.keys():
                prog_ids.add(str(k))
        except Exception:
            continue

    farm_ids = {_safe(lambda: id(p)) for p in farm}
    out = []
    seen = set()
    for p in list(roster or []) + list(farm or []) + list(prospects or []):
        try:
            if id(p) in seen:
                continue
            seen.add(id(p))
        except Exception:
            continue
        wp = to_web_player(p)
        pid = wp.get("id")
        try:
            history = engine.get_player_history(
                getattr(p, "id", pid)) if engine is not None else None
            fatigue = int(getattr(history, "current_fatigue", 0) or 0)
            schedule = getattr(history, "current_schedule", None)
        except Exception:
            fatigue, schedule = 0, None
        sched_txt = ""
        if schedule:
            try:
                sched_txt = (f"{schedule['type'].value.replace('_', ' ').title()} "
                             f"({schedule['intensity'].value}) - "
                             f"{schedule['sessions_remaining']} left")
            except Exception:
                sched_txt = "active"
        prog = _safe(
            lambda: (gm_programs.get(getattr(p, "id", pid))
                     or gm_programs.get(str(pid))
                     or ACTIVE_TRAINING_PROGRAMS.get(getattr(p, "id", pid))
                     or ACTIVE_TRAINING_PROGRAMS.get(str(pid))))
        osp = _safe(lambda: _osp.get_offseason_program(p)) if _osp else None
        pos_info = {"primary": "", "eligible": [], "familiarity": {},
                    "target": ""}
        if _pt is not None:
            try:
                primary = str(getattr(p, "primary_position", "") or "")
                try:
                    primary = (getattr(p, "primary_position", None).value
                               if hasattr(getattr(p, "primary_position", None),
                                          "value") else primary)
                except Exception:
                    pass
                pos_info["primary"] = primary
                elig = _pt.eligible_training_positions(p)
                pos_info["eligible"] = elig
                for pos in elig:
                    try:
                        pos_info["familiarity"][pos] = round(
                            float(_pt.get_familiarity(p, pos)), 1)
                    except Exception:
                        continue
                pos_info["target"] = str(
                    getattr(p, "position_training_target", "") or "")
            except Exception:
                pass
        out.append({
            "id": pid,
            "name": wp.get("name"),
            "position": wp.get("position"),
            "age": wp.get("age"),
            "overall": wp.get("overall"),
            "squad": "AHL" if _safe(lambda: id(p)) in farm_ids
                     else ("Prospect" if p in (prospects or []) else "NHL"),
            "injured": bool(wp.get("injured")),
            "fatigue": fatigue,
            "in_program": str(pid) in prog_ids,
            "program": ({"focus": str(prog.get("focus") or ""),
                         "intensity": str(prog.get("intensity") or "")}
                        if isinstance(prog, dict) else None),
            "schedule": sched_txt,
            "offseason": ({"focus": str(osp.get("focus") or ""),
                           "intensity": str(osp.get("intensity") or "")}
                          if isinstance(osp, dict) else None),
            "position_training": pos_info,
        })
    out.sort(key=lambda e: (e.get("name") or ""))
    return out


def get_development(live):
    """JSON-safe payload: active training programs + prospect watchlist."""
    roster, farm = _squads(live)
    idx = _player_index(roster + farm)

    # Merge program sources, de-duplicated by normalized player id.
    programs = {}
    for src in _program_sources(live):
        for pid, prog in _as_dict(src).items():
            if not isinstance(prog, dict):
                continue
            norm = str(pid)
            if norm in programs:
                continue
            programs[norm] = (pid, prog)

    prog_entries = []
    in_program = set()
    for norm, (pid, prog) in programs.items():
        player = _resolve_player(pid, idx)
        if player is not None:
            in_program.add(str(_safe(lambda: getattr(player, "id", "?"), "?")))
            web_player = to_web_player(player)
        else:
            web_player = {
                "id": norm,
                "name": _safe(lambda: str(prog.get("player_name") or "?"), "?"),
                "position": _safe(lambda: str(prog.get("position") or "?"), "?"),
                "age": _safe(lambda: int(prog.get("age") or 0), 0),
                "overall": _safe(lambda: int(prog.get("overall") or 0), 0),
                "salary": 0,
                "captaincy": "",
                "injured": False,
            }
        prog_entries.append({
            "player": web_player,
            "focus": _safe(lambda: str(prog.get("focus") or "—"), "—"),
            "intensity": _safe(lambda: str(prog.get("intensity") or "—"), "—"),
            "assigned": _date_str(_safe(lambda: prog.get("assigned"))),
        })
    prog_entries.sort(key=lambda e: e["player"].get("name", ""))

    # Prospect watchlist: age <= 23 across NHL + AHL, best overall first.
    prospects = []
    for p in roster + farm:
        age = _safe(lambda: int(getattr(p, "age", 0) or 0), 99)
        if age <= 23:
            prospects.append(p)
    prospects.sort(key=lambda p: _player_ovr(p),
                   reverse=True)
    farm_ids = {_safe(lambda: id(p)) for p in farm}
    web_prospects = []
    for p in prospects[:12]:
        wp = to_web_player(p)
        wp["squad"] = "AHL" if _safe(lambda: id(p)) in farm_ids else "NHL"
        wp["in_program"] = str(wp.get("id", "")) in in_program
        web_prospects.append(wp)

    team_prospects = _safe(lambda: _team_prospects(live), []) or []
    return {
        "programs": prog_entries,
        "prospects": web_prospects,
        "players": _safe(lambda: _dev_players(live, roster, farm, team_prospects), []),
        "catalog": {
            "focuses": _DEV_FOCUSES,
            "intensities": _DEV_INTENSITIES,
            "practice": _safe(lambda: _dev_practice_catalog(), {"drills": [], "intensities": []}),
        },
        "offseason": _safe(lambda: _dev_offseason(live), {"assignable": False, "month": 0}),
    }


def _enqueue(op, **kwargs):
    """Enqueue a dev command; returns (ok, nonce)."""
    import uuid as _uuid
    from web_ui.bridge import enqueue_command
    nonce = _uuid.uuid4().hex
    ok = enqueue_command(op, nonce=nonce, **kwargs)
    return ok, nonce


@bp.route("/api/development/result")
def api_development_result():
    live = _live()
    result = _safe(lambda: getattr(live, "_web_dev_result", None)) \
        if live else None
    return jsonify({"result": result})


@bp.route("/api/development/assign-program", methods=["POST"])
def api_assign_program():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("assign_training_program",
                         player_id=data.get("player_id"),
                         focus=data.get("focus"),
                         intensity=data.get("intensity"))
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/cancel-program", methods=["POST"])
def api_cancel_program():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("cancel_training_program",
                         player_id=data.get("player_id"))
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/practice/run", methods=["POST"])
def api_practice_run():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("run_practice_session",
                         player_id=data.get("player_id"),
                         drill=data.get("drill"),
                         intensity=data.get("intensity"))
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/practice/can", methods=["POST"])
def api_practice_can():
    """Side-effect-free availability preview (engine.can_practice)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    out = _safe(lambda: _practice_can(
        live, data.get("player_id"), data.get("drill"),
        data.get("intensity")),
        {"ok": False, "reason": "Unavailable."})
    return jsonify(out)


def _practice_can(live, pid, drill_key, intensity_key):
    from enhanced_practice_system import PracticeType, PracticeIntensity
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return {"ok": False, "reason": "No team."}
    player = None
    for lst in ("roster", "ahl_roster", "prospects"):
        for p in list(getattr(team, lst, None) or []):
            try:
                if str(getattr(p, "id", None)) == str(pid):
                    player = p
                    break
            except Exception:
                continue
        if player is not None:
            break
    if player is None:
        return {"ok": False, "reason": "Player not found."}
    try:
        drill = PracticeType(str(drill_key or "skating"))
        pint = PracticeIntensity(str(intensity_key or "moderate"))
    except ValueError:
        return {"ok": False, "reason": "Unknown drill/intensity."}
    engine = _dev_engine()
    if engine is None:
        return {"ok": False, "reason": "Practice engine unavailable."}
    can, why = engine.can_practice(player, drill, pint)
    fatigue_cost = engine._calculate_fatigue_cost(pint, 60)
    return {"ok": can, "reason": why if not can else "Ready to practice",
            "fatigue_cost": fatigue_cost}


@bp.route("/api/development/practice/schedule", methods=["POST"])
def api_practice_schedule():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("schedule_practice",
                         player_id=data.get("player_id"),
                         drill=data.get("drill"),
                         intensity=data.get("intensity"),
                         sessions=data.get("sessions"))
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/practice/stop", methods=["POST"])
def api_practice_stop():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("stop_practice_schedule",
                         player_id=data.get("player_id"))
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/practice/coach-runs", methods=["POST"])
def api_coach_runs_practice():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    ok, nonce = _enqueue("coach_runs_practice")
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/position/train", methods=["POST"])
def api_position_train():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("assign_position_training",
                         player_id=data.get("player_id"),
                         target=data.get("target"))
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/offseason/assign", methods=["POST"])
def api_offseason_assign():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("assign_offseason_program",
                         player_id=data.get("player_id"),
                         focus=data.get("focus"),
                         intensity=data.get("intensity"))
    return jsonify({"ok": ok, "nonce": nonce})


@bp.route("/api/development/offseason/clear", methods=["POST"])
def api_offseason_clear():
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    ok, nonce = _enqueue("clear_offseason_program",
                         player_id=data.get("player_id"))
    return jsonify({"ok": ok, "nonce": nonce})


# ----------------------------------------------------------------------
# Batch B: development analytics + training recommendations
# (player_development_window_professional parity: team overview, position
# analysis, age analysis, per-player key attributes with grades, and the
# top-3 development focus recommendations).
# ----------------------------------------------------------------------

_DEV_KEY_ATTRS = {
    "C": ["skating", "passing", "faceoffs", "hockey_iq", "vision",
          "determination"],
    "LW": ["skating", "shooting", "passing", "checking", "determination",
           "conditioning"],
    "RW": ["skating", "shooting", "passing", "checking", "determination",
           "conditioning"],
    "D": ["skating", "defense", "passing", "checking", "positioning",
          "hockey_iq"],
    "G": ["goaltending", "reflexes", "positioning", "rebound_control",
          "mental_toughness", "consistency"],
}


def _dev_pos_group(p):
    """Primary position -> desktop key-attribute group."""
    try:
        pos = getattr(p, "primary_position", None)
        v = str(getattr(pos, "value", pos) or "").upper()
    except Exception:
        v = ""
    if v in ("C", "CENTER"):
        return "C"
    if v in ("LW", "LEFT_WING"):
        return "LW"
    if v in ("RW", "RIGHT_WING"):
        return "RW"
    if v in ("D", "LD", "RD", "DEFENSE", "DEFENCE", "DEFENSEMAN"):
        return "D"
    if v in ("G", "GOALIE", "GOALTENDER"):
        return "G"
    return "C"


def _dev_grade(value):
    """100-scale letter grade (desktop's 20-scale grades x5)."""
    if value >= 90:
        return "A+"
    if value >= 80:
        return "A"
    if value >= 70:
        return "B+"
    if value >= 60:
        return "B"
    if value >= 50:
        return "C+"
    if value >= 40:
        return "C"
    return "D"


def _dev_recommendations(p, key_attrs):
    """Desktop _generate_recommendations parity: weakness-first, age and
    position aware, top 3 with HIGH/MED/LOW priority."""
    recs = []
    vals = []
    for attr in key_attrs:
        try:
            v = int(getattr(p, attr, 50) or 50)
        except Exception:
            v = 50
        vals.append((attr, v))
    vals.sort(key=lambda x: x[1])
    if vals:
        lowest_attr, lowest_val = vals[0]
        if lowest_val < 70:
            recs.append({
                "area": lowest_attr.replace("_", " ").title(),
                "reason": f"Currently {lowest_val}/100 -- below team standard",
            })
    try:
        age = int(getattr(p, "age", 26) or 26)
    except Exception:
        age = 26
    if age <= 20:
        recs.append({"area": "Intensive Training",
                     "reason": "Young age allows for rapid development"})
    elif age >= 30:
        recs.append({"area": "Maintenance Focus",
                     "reason": "Prevent attribute decline due to age"})
    if _dev_pos_group(p) == "G":
        try:
            mt = int(getattr(p, "mental_toughness", 50) or 50)
        except Exception:
            mt = 50
        if mt < 75:
            recs.append({"area": "Mental Training",
                         "reason": "Critical for goalie consistency"})
    prios = ["HIGH", "MED", "LOW"]
    out = []
    for i, r in enumerate(recs[:3]):
        r = dict(r)
        r["priority"] = prios[i] if i < len(prios) else "LOW"
        out.append(r)
    return out


@bp.route("/api/development/analytics")
def api_development_analytics():
    live = _live()
    if live is None:
        return jsonify({"overview": {}, "positions": [], "age_bands": [],
                        "players": []})
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"overview": {}, "positions": [], "age_bands": [],
                        "players": []})
    roster = _safe(lambda: list(team.roster or []), []) or []
    farm = _safe(lambda: list(getattr(team, "ahl_roster", None) or []), []) \
        or []
    prospects = _safe(lambda: list(getattr(team, "prospects", None) or []),
                      []) or []
    all_players = roster + farm + prospects

    total = len(all_players)
    overview = {
        "total_players": total,
        "avg_age": round(sum(_safe(lambda: int(getattr(p, "age", 0) or 0),
                                          0) for p in all_players) / total, 1)
        if total else 0,
        "avg_potential": round(sum(_safe(
            lambda: int(getattr(p, "potential", 50) or 50), 50)
            for p in all_players) / total, 1) if total else 0,
    }
    # Position analysis
    pos_groups = {}
    for p in all_players:
        g = _dev_pos_group(p)
        pos_groups.setdefault(g, []).append(p)
    positions = []
    for g in ("C", "LW", "RW", "D", "G"):
        ps = pos_groups.get(g, [])
        if not ps:
            continue
        positions.append({
            "position": g, "count": len(ps),
            "avg_potential": round(sum(_safe(
                lambda: int(getattr(p, "potential", 50) or 50), 50)
                for p in ps) / len(ps), 1),
        })
    # Age analysis
    bands = [("18-22", 18, 22), ("23-25", 23, 25), ("26-29", 26, 29),
             ("30+", 30, 99)]
    age_bands = []
    for label, lo, hi in bands:
        n = sum(1 for p in all_players
                if lo <= _safe(lambda: int(getattr(p, "age", 0) or 0), 0)
                <= hi)
        age_bands.append({"band": label, "count": n})
    # Per-player key attributes + recommendations
    farm_ids = {_safe(lambda: id(p)) for p in farm}
    prospect_ids = {_safe(lambda: id(p)) for p in prospects}
    players = []
    for p in all_players:
        try:
            g = _dev_pos_group(p)
            key_attrs = _DEV_KEY_ATTRS[g]
            attrs = []
            for attr in key_attrs:
                try:
                    from game_classes import to_100_scale
                    v = to_100_scale(getattr(p, attr, 50))
                except Exception:
                    v = 50
                attrs.append({"name": attr.replace("_", " ").title(),
                              "value": int(v), "grade": _dev_grade(v)})
            wp = to_web_player(p)
            pid = id(p)
            players.append({
                "id": wp.get("id"),
                "name": wp.get("name"),
                "position": wp.get("position"),
                "age": wp.get("age"),
                "overall": wp.get("overall"),
                "squad": ("AHL" if pid in farm_ids
                          else "Prospect" if pid in prospect_ids else "NHL"),
                "key_attributes": attrs,
                "recommendations": _dev_recommendations(p, key_attrs),
            })
        except Exception:
            continue
    players.sort(key=lambda e: (e.get("age") or 99,
                                -(e.get("overall") or 0)))
    return jsonify({"overview": overview, "positions": positions,
                    "age_bands": age_bands, "players": players})
