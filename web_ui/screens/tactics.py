"""Team tactics screen: 7-module systems model + identity presets + analyst intel.

Deepened from the legacy 6-slider port of Tkinter TacticsView. The real
E1 tactics engine lives in tactics.py: seven whiteboard modules
(forecheck / neutral_zone / dzone / ozone / breakout / pp / pk), each with
a catalog of named systems, plus identity presets, roster/coach fit math,
familiarity, whiteboard control, and opponent tactical intel. This screen
exposes all of it; writes go through the command queue to the Tk thread.
"""
from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("tactics", __name__)

# Legacy aggression sliders (Tkinter TacticsView parity). These still feed
# the sim: tactic_even_strength/power_play/penalty_kill fold into
# resolve_team_tactics(), tactic_line_matching drives home-ice deployment,
# tactic_forecheck/tactic_offense are read by the shot engine. Kept as a
# "Game Management" section under the Systems tab.
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

CATEGORY_LABELS = {
    "forecheck": "Forecheck",
    "neutral_zone": "Neutral Zone",
    "dzone": "D-Zone Coverage",
    "ozone": "O-Zone Attack",
    "breakout": "Breakout",
    "pp": "Power Play",
    "pk": "Penalty Kill",
}

CATEGORY_HINTS = {
    "forecheck": "Pressure scheme in the offensive zone — how you hunt the puck",
    "neutral_zone": "The 80-foot battleground — how you defend and exit the middle",
    "dzone": "Protecting the house — coverage shape in your own end",
    "ozone": "How you generate chances at 5v5",
    "breakout": "How you exit your own zone with the puck",
    "pp": "Man-advantage formation — where PP shots come from",
    "pk": "Short-handed shape — how you take away time and space",
}


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _tx():
    import tactics as _t
    return _t


def _team(live):
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)


def _coach(team):
    from web_ui.bridge import _staff_role_str
    for s in _safe(lambda: list(getattr(team, "staff", [])), []) or []:
        if "head coach" in _staff_role_str(s).lower():
            return s
    return None


def _skaters(team):
    roster = _safe(lambda: list(team.roster), []) or []
    return [p for p in roster
            if not str(_safe(lambda: getattr(p, "primary_position", ""), "")
                       ).upper().startswith("G")]


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


def _modules_payload(tx, team):
    """The seven whiteboard modules with catalogs, fit, and tradeoffs."""
    tk = tx.ensure_team_tactics(team)
    skaters = _skaters(team)
    out = []
    for cat, _label, _attr in tx.ALL_CATEGORIES:
        catalog = tx.CATALOGS.get(cat, {})
        current = tk.get(cat)
        # Roster fit per system: mean player_system_fit over skaters.
        fits = {}
        for skey in catalog:
            try:
                if skaters:
                    fits[skey] = sum(tx.player_system_fit(p, skey, cat)
                                     for p in skaters) / len(skaters)
                else:
                    fits[skey] = 1.0
            except Exception:
                fits[skey] = 1.0
        cur_fit = fits.get(current, 1.0)
        systems = []
        for skey, s in catalog.items():
            systems.append({
                "key": skey,
                "name": s.get("name", skey),
                "blurb": s.get("blurb", ""),
                "tradeoffs": tx.system_tradeoffs(cat, skey),
                "exemplars": s.get("exemplars", []),
                "fit": round(fits.get(skey, 1.0), 3),
                "fit_delta": round(fits.get(skey, 1.0) - cur_fit, 3),
            })
        cur = catalog.get(current, {})
        out.append({
            "key": cat,
            "label": CATEGORY_LABELS.get(cat, cat),
            "hint": CATEGORY_HINTS.get(cat, ""),
            "current": current,
            "current_name": cur.get("name", current),
            "blurb": cur.get("blurb", ""),
            "tradeoffs": tx.system_tradeoffs(cat, current),
            "exemplars": cur.get("exemplars", []),
            "systems": systems,
        })
    return out


def _identity_payload(tx, team):
    active = tx.matching_identity(team)
    presets = []
    for key, p in tx.IDENTITY_PRESETS.items():
        modules = p.get("modules", {})
        presets.append({
            "key": key,
            "name": p.get("name", key),
            "tagline": p.get("tagline", ""),
            "blurb": p.get("blurb", ""),
            "exemplars": p.get("exemplars", []),
            "modules": [
                {"category": CATEGORY_LABELS.get(c, c),
                 "system": tx.CATALOGS.get(c, {}).get(s, {}).get("name", s)}
                for c, s in modules.items()
            ],
        })
    return {"active": active, "presets": presets}


def _intel_payload(tx, team, live, coach):
    """Analyst cards: roster fit, coach fit, opponent intel, familiarity."""
    cards = []
    skaters = _skaters(team)

    # 1. Roster-fit suggestions: which systems suit the personnel better?
    try:
        tk = tx.team_tactics(team)
        for cat, _label, _attr in tx.ALL_CATEGORIES:
            catalog = tx.CATALOGS.get(cat, {})
            if not catalog or not skaters:
                continue
            cur = tk.get(cat)
            fits = {}
            for skey in catalog:
                try:
                    fits[skey] = sum(tx.player_system_fit(p, skey, cat)
                                     for p in skaters) / len(skaters)
                except Exception:
                    fits[skey] = 1.0
            best = max(fits, key=lambda k: fits[k])
            if best != cur and fits[best] - fits.get(cur, 1.0) >= 0.04:
                sys = catalog[best]
                cards.append({
                    "kind": "roster",
                    "title": f"Personnel fit: {sys.get('name', best)}",
                    "text": (f"Your skaters grade {fits[best]:.0%} in "
                             f"{sys.get('name', best)} vs {fits.get(cur, 1.0):.0%} "
                             f"in the current {CATEGORY_LABELS.get(cat, cat)} system. "
                             f"{sys.get('blurb', '')[:180]}"),
                    "action": {"label": "Install it",
                               "endpoint": "/api/tactics/system",
                               "payload": {"category": cat, "system": best}},
                })
            if len([c for c in cards if c["kind"] == "roster"]) >= 3:
                break
    except Exception:
        pass

    # 2. Coach fit: where the whiteboard disagrees with the man behind it.
    try:
        if coach is not None:
            prefs = tx.ensure_coach_tactics(coach)
            mine = tx.team_tactics(team)
            style = "Balanced"
            try:
                import reputation_system as _rs
                style = _rs.coach_style(coach).get("label", "Balanced")
            except Exception:
                pass
            mism = []
            for cat, _label, _attr in tx.ALL_CATEGORIES:
                want = prefs.get(cat)
                if want and want != mine.get(cat):
                    cat_dict = tx.CATALOGS.get(cat, {})
                    mism.append(
                        f"{CATEGORY_LABELS.get(cat, cat)}: he wants "
                        f"{cat_dict.get(want, {}).get('name', want)}")
            fit = tx.coach_tactics_fit(coach, team)
            cname = str(_safe(lambda: getattr(coach, "full_name", "Coach"), "Coach"))
            if mism:
                cards.append({
                    "kind": "coach",
                    "title": f"{cname} ({style}) disagrees with the whiteboard",
                    "text": (f"Coach-system fit is {fit:.0%}. "
                             f"{len(mism)} of 7 modules differ from what he'd run: "
                             + "; ".join(mism[:4])
                             + (f" (+{len(mism) - 4} more)" if len(mism) > 4 else "")
                             + ". A coach running someone else's systems coaches worse."),
                    "action": {"label": "Let him install his systems",
                               "endpoint": "/api/tactics/coach",
                               "payload": {"mode": "takeover"}},
                })
    except Exception:
        pass

    # 3. Opponent intel: which of your systems are actually hurting teams?
    try:
        gm = _safe(lambda: live.game_manager)
        league = _safe(lambda: gm.league) or _safe(lambda: live.league)
        teams = _safe(lambda: list(league.teams), []) or []
        hits = []
        for ai in teams:
            if ai is team:
                continue
            if not getattr(ai, "tactical_intel", None):
                continue
            for cat, sys_key, heat in tx.damaging_user_systems(ai, team):
                aname = _safe(lambda: getattr(ai, "team_name", "?"), "?")
                sname = tx.CATALOGS.get(cat, {}).get(sys_key, {}).get("name", sys_key)
                hits.append((heat, aname, CATEGORY_LABELS.get(cat, cat), sname))
        hits.sort(reverse=True)
        for heat, aname, clabel, sname in hits[:2]:
            cards.append({
                "kind": "opponent",
                "title": f"Intel: your {clabel.lower()} is torching {aname}",
                "text": (f"Across recent meetings your {sname} is producing "
                         f"{heat:.1f}x the damage threshold against them. "
                         f"They've seen it on film — expect an answer soon."),
                "action": None,
            })
        if not hits and teams:
            cards.append({
                "kind": "opponent",
                "title": "No damaging trends on film yet",
                "text": ("Rival coaches need at least two meetings against a "
                         "system before it shows up here. Nothing you're "
                         "running is consistently hurting anyone yet."),
                "action": None,
            })
    except Exception:
        pass

    # 4. Familiarity: the room is still learning.
    try:
        fam = float(_safe(lambda: getattr(team, "tactics_familiarity", 85), 85))
        if fam < 70:
            cards.append({
                "kind": "familiarity",
                "title": f"Room still learning ({fam:.0f}/100)",
                "text": ("New systems play muted until the reads are "
                         "automatic — every edge is dampened toward average "
                         "while familiarity rebuilds. It ticks up every game. "
                         "Avoid more changes until it settles."),
                "action": None,
            })
    except Exception:
        pass

    return cards


def _coach_payload(tx, team, coach):
    if coach is None:
        return None
    try:
        import reputation_system as _rs
        style = _rs.coach_style(coach).get("label", "Balanced")
    except Exception:
        style = "Balanced"
    prefs = tx.ensure_coach_tactics(coach)
    mine = tx.team_tactics(team)
    rows = []
    for cat, _label, _attr in tx.ALL_CATEGORIES:
        want = prefs.get(cat)
        cur = mine.get(cat)
        cat_dict = tx.CATALOGS.get(cat, {})
        rows.append({
            "category": CATEGORY_LABELS.get(cat, cat),
            "coach_wants": cat_dict.get(want, {}).get("name", want) if want else "—",
            "coach_wants_key": want,
            "current": cat_dict.get(cur, {}).get("name", cur) if cur else "—",
            "match": bool(want and want == cur),
        })
    return {
        "name": _safe(lambda: getattr(coach, "full_name", "Coach"), "Coach"),
        "style": style,
        "fit": round(tx.coach_tactics_fit(coach, team), 3),
        "control": tx.get_tactics_control(team),
        "rows": rows,
    }


@bp.route("/tactics")
def tactics_page():
    return render_template("tactics.html")


@bp.route("/api/tactics")
def api_tactics():
    live = _live()
    if live is None:
        return jsonify({"modules": [], "groups": [], "impact": []})
    team = _team(live)
    if team is None:
        return jsonify({"modules": [], "groups": [], "impact": []})
    tx = _tx()
    coach = _coach(team)
    try:
        engine = tx.resolve_team_tactics(team)
    except Exception:
        engine = {}
    groups = []
    for title, attr, default, values, hint in TACTIC_GROUPS:
        current = _safe(lambda: getattr(team, attr, default), default)
        try:
            if not hasattr(team, attr):
                setattr(team, attr, current)
        except Exception:
            pass
        groups.append({
            "title": title, "attr": attr, "hint": hint,
            "values": values, "current": current,
        })
    fam = _safe(lambda: float(getattr(team, "tactics_familiarity", 85)), 85)
    return jsonify({
        "modules": _modules_payload(tx, team),
        "identity": _identity_payload(tx, team),
        "familiarity": round(fam, 1),
        "control": tx.get_tactics_control(team),
        "coach": _coach_payload(tx, team, coach),
        "roster_fit": round(tx.team_system_fit(team), 3),
        "engine": {k: round(v, 3) for k, v in engine.items()
                   if isinstance(v, (int, float))},
        "intel": _intel_payload(tx, team, live, coach),
        "identity_lines": tx.describe_team_tactics(team),
        "groups": groups,
        "impact": _impact_lines(team),
    })


@bp.route("/api/tactics/system", methods=["POST"])
def api_tactics_system():
    """Install one whiteboard module (queues for Tk thread)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    category = data.get("category", "")
    system = data.get("system", "")
    try:
        tx = _tx()
        if category not in tx.CATALOGS or system not in tx.CATALOGS[category]:
            return jsonify({"ok": False, "error": "unknown system"}), 400
    except Exception:
        return jsonify({"ok": False, "error": "tactics unavailable"}), 503
    from web_ui.bridge import enqueue_command
    ok = enqueue_command("set_tactic_system", category=category,
                         system_key=system)
    return jsonify({"ok": ok})


@bp.route("/api/tactics/preset", methods=["POST"])
def api_tactics_preset():
    """Apply an identity preset (queues for Tk thread)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    preset = data.get("preset", "")
    try:
        tx = _tx()
        if preset not in tx.IDENTITY_PRESETS:
            return jsonify({"ok": False, "error": "unknown preset"}), 400
    except Exception:
        return jsonify({"ok": False, "error": "tactics unavailable"}), 503
    from web_ui.bridge import enqueue_command
    ok = enqueue_command("apply_identity_preset", preset=preset)
    return jsonify({"ok": ok})


@bp.route("/api/tactics/control", methods=["POST"])
def api_tactics_control():
    """Set whiteboard ownership: coach or gm (queues for Tk thread)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    who = data.get("who", "")
    if who not in ("coach", "gm"):
        return jsonify({"ok": False, "error": "bad owner"}), 400
    from web_ui.bridge import enqueue_command
    ok = enqueue_command("set_tactics_control", who=who)
    return jsonify({"ok": ok})


@bp.route("/api/tactics/coach", methods=["POST"])
def api_tactics_coach():
    """Coach actions: enforce (GM takes the whiteboard) or takeover
    (coach installs his own systems). Suggest is read-only and served
    by the coach payload / analyst tab."""
    live = _live()
    if live is None:
        return jsonify({"ok": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "")
    if mode not in ("enforce", "takeover"):
        return jsonify({"ok": False, "error": "bad mode"}), 400
    from web_ui.bridge import enqueue_command
    ok = enqueue_command("coach_tactics", mode=mode)
    return jsonify({"ok": ok})


@bp.route("/api/tactics/set", methods=["POST"])
def api_tactics_set():
    """Set a legacy tactic slider (queues for Tk thread)."""
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
    team = _team(live)
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
