"""Roster management screen: NHL / AHL / Prospects / Depth Chart / Salary Cap.

Migrated from Tkinter RosterView (windows.py:282, ~2300 lines).
Full 5-tab interface with sort/filter/search, bulk moves with CBA
validation, and player context actions.
"""
from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("roster", __name__)


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "?"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,}"


def _tier_label(ovr):
    """Tier label (not numeric) like the Tkinter view."""
    try:
        o = int(ovr or 0)
    except Exception:
        return "?"
    if o >= 90:
        return "Elite"
    if o >= 85:
        return "Top"
    if o >= 80:
        return "1st"
    if o >= 75:
        return "2nd"
    if o >= 70:
        return "3rd"
    if o >= 65:
        return "4th"
    if o >= 60:
        return "Depth"
    return "Minors"


def _health_badges(p):
    """IR/LTIR/SUSPENDED/EMERGENCY badges."""
    badges = []
    try:
        import ir_system as _irs
        st = _irs.ir_status_of(p)
        if st and st != "None":
            badges.append(st)
    except Exception:
        pass
    if _safe(lambda: bool(getattr(p, "injured", False)), False):
        if "IR" not in badges and "LTIR" not in badges:
            badges.append("INJ")
    try:
        import roster_limits as _rl
        if _rl.is_emergency_filler(p):
            badges.append("EMERGENCY")
    except Exception:
        pass
    return badges


def to_roster_player(p):
    """Rich player dict for roster tables (all Tkinter columns)."""
    c = _safe(lambda: getattr(p, "contract", None))
    return {
        "id": _safe(lambda: str(getattr(p, "id", id(p)))),
        "name": _safe(lambda: getattr(p, "full_name", "?")),
        "position": _safe(lambda: str(getattr(p, "primary_position", "") or "?")),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0)),
        "jersey": _safe(lambda: getattr(p, "jersey_number", ""), ""),
        "overall": _safe(lambda: int(getattr(p, "overall", 0) or 0)),
        "tier": _tier_label(_safe(lambda: getattr(p, "overall", 0))),
        "potential": _safe(lambda: getattr(p, "potential", 0), 0),
        "salary": _safe(lambda: int(getattr(p, "salary", 0) or 0)),
        "salary_fmt": _fmt_money(_safe(lambda: getattr(p, "salary", 0))),
        "contract_years": _safe(lambda: getattr(c, "years_remaining", 0), 0) if c else 0,
        "has_contract": c is not None,
        "ntc": _safe(lambda: bool(getattr(c, "no_trade_clause", False)), False) if c else False,
        "nmc": _safe(lambda: bool(getattr(c, "no_movement_clause", False)), False) if c else False,
        "morale": _safe(lambda: int(getattr(p, "morale", 0) or 0), 0),
        "morale_100": _safe(lambda: int(getattr(p, "morale", 0) or 0) * 10, 0),
        "captaincy": _safe(lambda: getattr(p, "captaincy", "") or ""),
        "health": _health_badges(p),
        "injured": _safe(lambda: bool(getattr(p, "injured", False)), False),
        "rights_team": _safe(lambda: getattr(p, "rights_team", "") or ""),
    }


def _get_team_lists(live):
    """Return (nhl, ahl, prospects) player lists."""
    team = _safe(lambda: live.user_team)
    if team is None:
        return [], [], []
    nhl = _safe(lambda: list(team.roster), []) or []
    ahl = _safe(lambda: list(getattr(team, "ahl_roster", [])), []) or []
    pros = _safe(lambda: list(getattr(team, "prospects", [])), []) or []
    return nhl, ahl, pros


@bp.route("/roster")
def roster_page():
    return render_template("roster.html")


@bp.route("/api/roster")
def api_roster():
    """?tab=nhl|ahl|prospects — full player lists with all columns."""
    live = _live()
    if live is None:
        return jsonify({"tab": "nhl", "players": [], "counts": {}})
    tab = request.args.get("tab", "nhl")
    nhl, ahl, pros = _get_team_lists(live)
    data = {
        "nhl": nhl,
        "ahl": ahl,
        "prospects": pros,
    }.get(tab, nhl)
    return jsonify({
        "tab": tab,
        "players": [to_roster_player(p) for p in data],
        "counts": {
            "nhl": len(nhl),
            "ahl": len(ahl),
            "prospects": len(pros),
        },
    })


@bp.route("/api/roster/depth")
def api_depth():
    """Depth chart: 4 lines + 3 pairs + goalies from team.lineup."""
    live = _live()
    if live is None:
        return jsonify({"units": []})
    from web_ui.screens.lines import get_lines
    d = get_lines(live)
    return jsonify({"units": d.get("units", [])})


@bp.route("/api/roster/cap")
def api_cap():
    """Salary cap breakdown (mirrors Tkinter _cap_numbers)."""
    live = _live()
    if live is None:
        return jsonify({})
    team = _safe(lambda: live.user_team)
    if team is None:
        return jsonify({})
    try:
        from salary_cap_system import cap_breakdown
        bd = cap_breakdown(team)
        cap = bd["cap"]
        total = bd["total"]
        space = bd["space"]
        dead = bd["dead_cap"]
        extra = {
            "retained": bd.get("seeded_retained", 0),
            "overage": bd.get("seeded_overage", 0),
            "buyouts": bd.get("seeded_buyout", 0),
        }
    except Exception:
        cap = _safe(lambda: getattr(team, "salary_cap", 104_000_000), 104_000_000)
        total = sum(_safe(lambda: int(getattr(p, "salary", 0) or 0), 0)
                    for p in _safe(lambda: list(team.roster), []) or [])
        space = cap - total
        dead = 0
        extra = {}
    # Contract table
    nhl, _, _ = _get_team_lists(live)
    contracts = []
    for p in nhl:
        rp = to_roster_player(p)
        contracts.append({
            "name": rp["name"],
            "position": rp["position"],
            "salary": rp["salary"],
            "salary_fmt": rp["salary_fmt"],
            "years": rp["contract_years"],
            "ntc": rp["ntc"],
            "nmc": rp["nmc"],
        })
    contracts.sort(key=lambda c: c["salary"], reverse=True)
    return jsonify({
        "cap": cap,
        "cap_fmt": _fmt_money(cap),
        "payroll": total,
        "payroll_fmt": _fmt_money(total),
        "space": space,
        "space_fmt": _fmt_money(space),
        "pct": round(total / cap * 100, 1) if cap else 0,
        "dead_cap": dead,
        "dead_fmt": _fmt_money(dead),
        **{k: _fmt_money(v) for k, v in extra.items() if v},
        "contracts": contracts,
    })


@bp.route("/api/roster/player/<pid>")
def api_player(pid):
    """Single player detail for profile modal."""
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    nhl, ahl, pros = _get_team_lists(live)
    player = None
    found_tab = None
    for tab, lst in (("nhl", nhl), ("ahl", ahl), ("prospects", pros)):
        for p in lst:
            if str(_safe(lambda: getattr(p, "id", ""), "")) == str(pid):
                player = p
                found_tab = tab
                break
        if player:
            break
    if player is None:
        return jsonify({"error": "not found"}), 404
    rp = to_roster_player(player)
    rp["tab"] = found_tab
    # Attribute bars (1-100 scale)
    try:
        from game_classes import to_100_scale
        attrs = {}
        for attr in ["skating", "shooting", "passing", "defense",
                     "physical", "hockey_iq", "stamina", "poise"]:
            v = _safe(lambda: getattr(player, attr, 0), 0)
            attrs[attr] = _safe(lambda: int(to_100_scale(v)), 0)
        rp["attributes"] = attrs
    except Exception:
        rp["attributes"] = {}
    return jsonify(rp)


def execute_roster_move(app, cmd):
    """Execute roster moves on the Tk main thread with CBA validation.

    Mirrors RosterView.move_player / bulk_move_players (windows.py).
    Returns (moved, errors) for the result poll.
    """
    player_ids = [str(x) for x in cmd.get("player_ids", [])]
    frm = cmd.get("from_roster", "")
    to = cmd.get("to_roster", "")
    team = _safe(lambda: app.user_team)
    if team is None:
        return 0, ["no team"]
    src_map = {
        "nhl": _safe(lambda: list(team.roster), []) or [],
        "ahl": _safe(lambda: list(getattr(team, "ahl_roster", [])), []) or [],
        "prospects": _safe(lambda: list(getattr(team, "prospects", [])), []) or [],
    }
    src = src_map.get(frm, [])
    dst_attr = {"nhl": "roster", "ahl": "ahl_roster",
                "prospects": "prospects"}.get(to)
    if dst_attr is None:
        return 0, ["bad destination"]
    by_id = {str(_safe(lambda: getattr(p, "id", ""), "")): p for p in src}
    players = [by_id[pid] for pid in player_ids if pid in by_id]

    try:
        import game_classes as _gc
    except Exception:
        _gc = None

    moved, errors = 0, []
    is_promotion = frm not in ("nhl", "ahl") and to in ("nhl", "ahl")
    is_junior_return = frm in ("nhl", "ahl") and to not in ("nhl", "ahl")

    for player in players:
        name = _safe(lambda: getattr(player, "full_name", "?"), "?")
        # --- Promotion validations ---
        if is_promotion:
            # CHL-NHL agreement: under-20 CHL prospects not AHL-eligible
            # (except 19yo first-rounders).
            if to == "ahl" and _gc is not None:
                try:
                    if not _gc.prospect_ahl_eligible(player):
                        errors.append(
                            f"{name}: not AHL-eligible (CHL-NHL agreement)")
                        continue
                except Exception:
                    pass
            # 23-man NHL roster limit
            if to == "nhl" and len(_safe(lambda: list(team.roster), [])) >= 23:
                errors.append(f"{name}: NHL roster full (23)")
                continue
            # ELC gate: unsigned prospects need a contract first
            if getattr(player, "contract", None) is None:
                errors.append(f"{name}: needs an entry-level contract first")
                continue
            try:
                player.playing_where = "NHL" if to == "nhl" else "AHL"
            except Exception:
                pass
        # --- Junior return validations ---
        elif is_junior_return:
            if getattr(player, "contract", None) is not None and _gc is not None:
                try:
                    track = _gc.junior_track_of(player)
                    jage = int(getattr(player, "age", 20) or 20)
                    if not (track == "CHL" and jage < 20):
                        errors.append(
                            f"{name}: only junior-aged CHL prospects "
                            f"can return to junior")
                        continue
                except Exception:
                    pass
        # --- Execute the move ---
        try:
            src.remove(player)
            getattr(team, dst_attr).append(player)
            moved += 1
        except Exception as e:
            errors.append(f"{name}: move failed ({e})")
    # Store result for the poll endpoint
    try:
        app._web_roster_move_result = {"moved": moved, "errors": errors}
    except Exception:
        pass
    try:
        app.update_all_views()
    except Exception:
        pass
    return moved, errors


@bp.route("/api/roster/move", methods=["POST"])
def api_move():
    """Queue a roster move for the Tk main thread.

    Body: {player_ids: [...], from: 'nhl'|'ahl'|'prospects',
           to: 'nhl'|'ahl'|'prospects'}
    Returns immediately; the command queue executes with CBA validation.
    """
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no game"}), 503
    data = request.get_json(force=True, silent=True) or {}
    player_ids = data.get("player_ids", [])
    frm = data.get("from", "")
    to = data.get("to", "")
    if not player_ids or frm not in ("nhl", "ahl", "prospects") \
            or to not in ("nhl", "ahl", "prospects"):
        return jsonify({"ok": False, "error": "bad request"}), 400
    from web_ui.bridge import enqueue_command
    ok = enqueue_command("roster_move", player_ids=player_ids,
                         from_roster=frm, to_roster=to)
    return jsonify({"ok": ok, "queued": len(player_ids)})


@bp.route("/api/roster/move_result")
def api_move_result():
    """Poll the last roster_move outcome."""
    live = _live()
    if live is None:
        return jsonify({"moved": 0, "errors": []})
    return jsonify(getattr(live, "_web_roster_move_result",
                           {"moved": 0, "errors": []}))
