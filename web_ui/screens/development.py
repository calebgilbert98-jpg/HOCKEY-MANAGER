"""Development screen: active training programs + prospect watchlist."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, to_web_player, _player_ovr

bp = Blueprint("development", __name__)


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

    return {"programs": prog_entries, "prospects": web_prospects}


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
