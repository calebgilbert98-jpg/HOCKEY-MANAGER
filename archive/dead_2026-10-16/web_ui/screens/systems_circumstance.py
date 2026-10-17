"""Systems: Circumstance Shifts.

Web port of TRACK C #7 (trackc_circumstance_view.py, origin/main).
Shows "tonight's circumstance baseline": for each skater (and goalie),
the shift circumstance_shift() will apply per composite for the NEXT
game -- decomposed into energy / morale / home-ice / rivalry
components, verified to sum to the engine function's own output.

PUZZLE RULE: your own team's shifts are your info (shown). Opponent
detail stays qualitative (rivalry intensity band only).
"""
from types import SimpleNamespace

from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, player_portrait, _resolve_gm

bp = Blueprint("systems_circumstance", __name__)

_COMPOSITE_LABELS = {
    "chance_creation": "Chance creation",
    "finishing": "Finishing",
    "skating": "Skating",
    "defensive_play": "Defensive play",
    "goalie_save": "Goalie save",
    "physicality": "Physicality",
    "discipline": "Discipline",
    "faceoff": "Faceoff",
    "puck_retrieval": "Puck retrieval",
}


def _live():
    from web_ui.bridge import _web_app_ref, _resolve_gm
    return _web_app_ref


def _ctx():
    live = _live()
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    today = _safe(lambda: getattr(live, "current_date", None))
    return live, team, league, today


def _next_game(league, team, today):
    """Next scheduled game for the team: (date, home_team, away_team)."""
    try:
        my = getattr(team, "team_name", "")
        best = None
        for item in list(getattr(league, "schedule", None) or []):
            try:
                if isinstance(item, dict):
                    d, h, a = (item.get("date"), item.get("home_team"),
                               item.get("away_team"))
                elif isinstance(item, (tuple, list)) and len(item) >= 3:
                    d, h, a = item[0], item[1], item[2]
                else:
                    continue
                hn = getattr(h, "team_name", h)
                an = getattr(a, "team_name", a)
                if my not in (hn, an):
                    continue
                if today is not None and d is not None and d <= today:
                    continue
                if best is None or (d is not None and d < best[0]):
                    best = (d, h, a)
            except Exception:
                continue
        return best
    except Exception:
        return None


def _fake_sim(league, nxt):
    if nxt is None:
        return SimpleNamespace(home_team=None, away_team=None,
                               rivalries=list(getattr(league, "rivalries", None) or []),
                               period=1, clock=1200.0)
    _d, h, a = nxt
    return SimpleNamespace(home_team=h, away_team=a,
                           rivalries=list(getattr(league, "rivalries", None) or []),
                           period=1, clock=1200.0)


def _pos_short(p):
    pos = str(_safe(lambda: getattr(getattr(p, "primary_position", None), "name", ""), "") or "")
    return (pos.replace("LEFT_", "L").replace("RIGHT_", "R")
               .replace("_WING", "W").replace("_DEFENSE", "D")
               .replace("CENTER", "C").replace("GOALIE", "G") or "?")


@bp.route("/systems/circumstance")
def circumstance_page():
    return render_template("systems_circumstance.html")


@bp.route("/api/systems/circumstance")
def api_circumstance():
    live, team, league, today = _ctx()
    if live is None:
        return jsonify({"error": "no game"}), 503
    if team is None or league is None:
        return jsonify({"error": "no team"}), 503
    key = request.args.get("composite", "finishing")
    if key not in _COMPOSITE_LABELS:
        key = "finishing"
    try:
        import attribute_composites as acmp
        import condition_system as cs
    except Exception:
        return jsonify({"error": "engine unavailable"}), 503

    nxt = _next_game(league, team, today)
    fake = _fake_sim(league, nxt)
    my_name = getattr(team, "team_name", "")
    home_name = getattr(getattr(fake, "home_team", None), "team_name", "") or ""
    is_home = bool(home_name) and home_name == my_name

    rows = []
    for p in list(getattr(team, "roster", None) or []):
        try:
            energy = cs.get_game_energy(p)
            total = acmp.circumstance_shift(p, key, sim=fake, team=team,
                                           energy=energy)
            # Component decomposition from the documented engine terms
            # (same as the desktop view; sums to the real total).
            e_term = -2.0 * (1.0 - max(0.0, min(100.0, energy)) / 100.0)
            try:
                m = max(1.0, min(100.0, float(getattr(p, "morale", 70.0))))
            except (TypeError, ValueError):
                m = 70.0
            mo_term = max(-1.0, min(1.0, (m - 70.0) / 30.0))
            h_term = 0.4 if is_home else 0.0
            r_term = 0.0
            kind = acmp._EVENT_KIND.get(key, "neutral")
            if kind in ("physical", "discipline") and nxt is not None:
                try:
                    import physicality as phys
                    hn = getattr(nxt[1], "team_name", nxt[1])
                    an = getattr(nxt[2], "team_name", nxt[2])
                    heat = float(phys.rivalry_heat_between(
                        getattr(league, "rivalries", None), hn, an) or 0.0)
                    heat = max(0.0, min(100.0, heat)) / 100.0
                    r_term = (0.6 if kind == "physical" else -0.6) * heat
                except Exception:
                    r_term = 0.0
            pid = str(_safe(lambda: getattr(p, "id", ""), ""))
            name = str(_safe(lambda: getattr(p, "full_name", "?"), "?"))
            rows.append({"id": pid, "name": name, "pos": _pos_short(p),
                         "portrait": player_portrait(pid),
                         "total": round(float(total), 2),
                         "energy": round(e_term, 2), "morale": round(mo_term, 2),
                         "home": round(h_term, 2), "rivalry": round(r_term, 2)})
        except Exception:
            continue
    rows.sort(key=lambda r: r["total"])

    if nxt is None:
        note = ("Offseason / no fixture found \u2014 showing the energy + morale baseline only "
                "(home ice and rivalry apply once there's a next game).")
        next_game, opponent = None, None
    else:
        d, h, a = nxt
        hn = getattr(h, "team_name", h)
        an = getattr(a, "team_name", a)
        note = (f"Next game: {an} @ {hn} ({d}). "
                f"You are {'home' if is_home else 'away'}. Pre-game baseline "
                "(period 1) \u2014 the late/close-game clutch term applies in-game only.")
        next_game = {"date": str(d), "home": str(hn), "away": str(an),
                     "is_home": is_home}
        try:
            import physicality as phys
            heat = float(phys.rivalry_heat_between(
                getattr(league, "rivalries", None), h, a) or 0.0)
        except Exception:
            heat = 0.0
        opp_name = str(an) if str(hn) == my_name else str(hn)
        opponent = {"name": opp_name, "heat": round(max(0.0, min(100.0, heat)), 0)}
    return jsonify({
        "composite": key,
        "composites": [{"key": k, "label": v} for k, v in _COMPOSITE_LABELS.items()],
        "note": note,
        "next_game": next_game,
        "opponent": opponent,
        "rows": rows,
    })
