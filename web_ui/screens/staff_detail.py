"""Staff detail screen: quick profile for a coach/staff member.

Header: name, role, department, rating. Facts: age, nationality,
experience, years with team, salary, morale. All defensive.
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import enqueue_command

bp = Blueprint("staff_detail", __name__)


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _find_staff(sid):
    live = _live()
    if live is None:
        return None
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    staff = _safe(lambda: list(getattr(team, "staff", []) or []), []) or []
    for s in staff:
        if str(_safe(lambda: getattr(s, "id", ""), "")) == str(sid):
            return s
    return None


@bp.route("/staff/<sid>")
def staff_detail_page(sid):
    return render_template("staff_detail.html", sid=sid)


@bp.route("/api/staff/<sid>")
def api_staff_detail(sid):
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    s = _find_staff(sid)
    if s is None:
        return jsonify({"error": "not found"}), 404
    from web_ui.screens.staff import to_web_staff
    d = to_web_staff(s)
    # Extra detail fields
    d["department"] = _safe(lambda: getattr(s, "department", ""), "") or ""
    d["contract_years"] = _safe(lambda: int(getattr(s, "contract_years", 0) or 0), 0)
    d["specialty"] = _safe(lambda: getattr(s, "specialty", ""), "") or ""
    d["reputation"] = _safe(lambda: getattr(s, "reputation", ""), "") or ""
    d["tactics"] = _safe(lambda: getattr(s, "tactics", ""), "") or ""
    d["tabs"] = _staff_tabs(s)
    return jsonify(d)


# ----------------------------------------------------------------------
# Batch B: detail tabs (staff_management_window parity)
# ----------------------------------------------------------------------

_STAFF_ATTR_GROUPS = [
    ("Coaching", ["coaching_forwards", "coaching_defensemen",
                  "coaching_goalies", "attacking_coaching",
                  "defensive_coaching", "technical_coaching",
                  "mental_coaching"]),
    ("Tactical", ["tactical_knowledge", "game_preparation",
                  "match_preparation"]),
    ("Development", ["working_with_youngsters", "player_development",
                     "judging_player_ability", "judging_player_potential"]),
    ("Management", ["man_management", "motivating", "discipline",
                    "level_of_discipline", "media_handling"]),
    ("Personality", ["leadership", "determination", "adaptability"]),
]


def _staff_tabs(s):
    """Attributes, Standing, Personality + role-conditional Record /
    Track Record / Analytics (desktop tab parity). All JSON-safe."""
    tabs = {}
    # -- Attributes --
    attr_groups = []
    for label, attrs in _STAFF_ATTR_GROUPS:
        items = []
        for a in attrs:
            v = _safe(lambda: getattr(s, a, None))
            if isinstance(v, (int, float)) and v > 0:
                items.append({"name": a.replace("_", " ").title(),
                              "value": int(v)})
        if items:
            attr_groups.append({"label": label, "items": items})
    tabs["attributes"] = attr_groups
    # -- Standing --
    standing = []
    try:
        import reputation_system as _rs
        st = _rs.room_status(s)
        if isinstance(st, dict):
            level = st.get("level", "Secure")
            risk = float(st.get("risk", 0.0) or 0.0)
            standing.append({"text": "Room standing: %s (%.0f%% "
                                     "losing-the-room risk)" % (level, risk * 100),
                             "kind": "warn" if risk >= 0.45 else "info"})
    except Exception:
        pass
    try:
        if str(getattr(getattr(s, "role", None), "name", "")) \
                == "HEAD_COACH":
            standing.append({
                "text": "GM trust: %d/100" % int(
                    getattr(s, "gm_trust", 70) or 70),
                "kind": "info"})
    except Exception:
        pass
    try:
        eff = getattr(s, "assistant_effect", None)
        if eff:
            standing.append({"text": "Assistant effectiveness: %.0f"
                                     % float(eff), "kind": "ok"})
    except Exception:
        pass
    try:
        cn = getattr(s, "control_need", None)
        if cn is not None:
            standing.append({"text": "Control need: %.0f/100" % float(cn),
                             "kind": "info"})
    except Exception:
        pass
    tabs["standing"] = standing or [{"text": "No standing data recorded.",
                                     "kind": "info"}]
    # -- Personality --
    personality = {"style": "", "style_description": "", "lines": []}
    try:
        import reputation_system as _rs
        style = _rs.coach_style(s)
        personality["style"] = _safe(lambda: style.get("label", ""), "")
        personality["style_description"] = _safe(
            lambda: style.get("description", ""), "")
    except Exception:
        pass
    ambition_text = {
        "stanley_cup": "Burning to win the Stanley Cup.",
        "climb": "Climbing -- wants a bigger chair.",
        "developer": "Lives to develop young players.",
        "hometown": "Dreams of coaching his hometown team.",
        "lifer": "A lifer -- happy wherever the game takes him.",
    }.get(str(getattr(s, "ambition", "") or ""), "")
    if ambition_text:
        personality["lines"].append("Ambition: " + ambition_text)
    fav = _safe(lambda: getattr(s, "favorite_team", None))
    if fav:
        personality["lines"].append("Boyhood team: " + str(fav))
    try:
        cn = float(getattr(s, "control_need", 50))
        personality["lines"].append(
            "Runs the room his way -- needs full control." if cn >= 75
            else "Comfortable sharing the room with his staff." if cn >= 45
            else "Collaborative -- delegates freely to assistants.")
    except Exception:
        pass
    try:
        mot = float(getattr(s, "motivating", 50))
        disc = float(getattr(s, "discipline", 50))
        if mot >= 75 and disc >= 75:
            personality["lines"].append(
                "Demanding and inspiring in equal measure.")
        elif mot >= 75 and disc < 60:
            personality["lines"].append("An arm-around-the-shoulder motivator.")
        elif disc >= 75 and mot < 60:
            personality["lines"].append("A demanding disciplinarian.")
        elif mot < 45 and disc < 45:
            personality["lines"].append(
                "Hands-off -- lets the leaders run the room.")
    except Exception:
        pass
    tabs["personality"] = personality
    # -- role-conditional tabs --
    try:
        from game_classes import StaffRole as _SR
        role = getattr(s, "role", None)
        scout_roles = {_SR.HEAD_SCOUT, _SR.PROFESSIONAL_SCOUT,
                       _SR.AMATEUR_SCOUT, _SR.EUROPEAN_SCOUT}
        is_scout = role in scout_roles
        is_director = role == _SR.ANALYTICS_DIRECTOR
        try:
            import coach_records as _crw
            is_coach = _crw.is_coaching_role(s)
        except Exception:
            is_coach = False
    except Exception:
        is_scout = is_director = is_coach = False
    if is_coach:
        tabs["record"] = _coaching_record_tab(s)
    if is_scout:
        tabs["track_record"] = _track_record_tab(s)
    if is_director:
        tabs["analytics"] = _analytics_tab(s)
    return tabs


def _coaching_record_tab(s):
    """Record page: year-by-year W-L-OTL, playoff results, honours."""
    out = {"totals": "", "honours": [], "seasons": []}
    try:
        import coach_records as _cr
        record = list(getattr(s, "career_record", None) or [])
        t = _cr.career_totals(record)
        out["totals"] = ("%d-%d-%d (%.3f) over %d seasons · %d Stanley Cups "
                         "· %d Jack Adams" % (
                             t["w"], t["l"], t["otl"], t["win_pct"],
                             t["seasons"], t["cups"], t["adams"]))
        for e in reversed(record):
            if not isinstance(e, dict):
                continue
            out["seasons"].append({
                "season": str(e.get("season", "?")),
                "team": str(e.get("team", "?"))[:26],
                "role": str(e.get("role", "?"))[:18],
                "wl": "%s-%s-%s" % (e.get("w", 0), e.get("l", 0),
                                    e.get("otl", 0)),
                "playoffs": str(e.get("playoff", "?"))[:28],
                "cup": e.get("playoff") == "Won Stanley Cup",
                "adams": bool(e.get("jack_adams")),
            })
    except Exception:
        pass
    try:
        import accolades as _acc
        for label, years in _acc.group_accolades(s) or []:
            out["honours"].append("%s Winner: %s" % (label, ", ".join(years)))
    except Exception:
        pass
    return out


def _track_record_tab(s):
    """Track Record page: graded calls, hit rate, recent reads."""
    out = {"record_line": "", "history": []}
    try:
        import analytics_scouting as _as
        _as.ensure_analytics_fields(s)
        out["record_line"] = str(_as.scout_record_line(s) or "")
        hist = list(reversed(list(getattr(s, "tip_history", []) or [])))[-8:]
        for h in hist:
            try:
                res = h.get("result", "?")
                out["history"].append({
                    "mark": ("hit" if res == "hit" else "miss"
                             if res == "miss" else "pending"),
                    "player": h.get("player_name", h.get("player", "?")),
                    "kind": h.get("kind", ""),
                    "date": h.get("date", ""),
                })
            except Exception:
                continue
    except Exception:
        pass
    return out


def _analytics_tab(s):
    """Analytics page: what the director's department does for the club."""
    out = {"quality": 0, "tier": "", "club_quality": None,
           "refresh_days": None, "note": ""}
    try:
        import analytics_scouting as _as
        import advanced_metrics as _am
        personal = _as.analytics_director_quality(s)
        tier = _as.department_tier_label(personal)
        out.update(quality=int(personal), tier=str(tier))
        out["refresh_days"] = int(_am.department_refresh_days(personal))
        sid = _safe(lambda: str(getattr(s, "id", "")), "")
        if sid and _find_staff(sid) is not None:
            live = _live()
            gm = _safe(lambda: live.game_manager) if live else None
            team = _safe(lambda: gm.user_team) if gm else None
            if team is not None:
                club_q = int(getattr(team, "analytics_quality", personal)
                             or personal)
                out["club_quality"] = club_q
                out["refresh_days"] = int(_am.department_refresh_days(club_q))
        out["note"] = ("A better department sharpens the picture, never the "
                       "players: tighter confidence intervals on modeled "
                       "metrics, fresher model snapshots, less visible "
                       "noise. Box-score facts stay exact at every tier.")
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------
# Batch B: extension negotiation, hire result, org chart, staff report.
# ----------------------------------------------------------------------

def _staff_offer_chance(s, salary):
    """Desktop StaffContractView._staff_offer_accept_chance parity
    (display-side estimate of the negotiate_contract roll)."""
    try:
        from game_classes import staff_market_ask, to_100_scale
        import reputation_system as _rs
        live = _live()
        gm = _safe(lambda: live.game_manager) if live else None
        team = _safe(lambda: gm.user_team) if gm else None
        ask = staff_market_ask(s)
        salary_mult = salary / max(1, ask)
        try:
            rating = to_100_scale(getattr(s, "overall_rating", 60) or 60)
        except Exception:
            rating = 60
        prestige = _safe(lambda: getattr(team, "prestige", 50), 50)
        base = (0.45 + (salary_mult - 1.0) * 1.4
                + (prestige - 50) / 400 - (rating - 60) / 600)
        try:
            base += _rs.gm_staff_accept_delta(team) if team else 0
        except Exception:
            pass
        return max(0.05, min(0.98, base))
    except Exception:
        return 0.5


@bp.route("/api/staff/<sid>/negotiate-preview")
def api_staff_negotiate_preview(sid):
    """Extension demands: current terms, the staffer's ask window, the
    league staff budget, and the acceptance-chance estimate."""
    s = _find_staff(sid)
    if s is None:
        return jsonify({"error": "not found"}), 404
    live = _live()
    gm = _safe(lambda: live.game_manager) if live else None
    team = _safe(lambda: gm.user_team) if gm else None
    salary = _safe(lambda: int(getattr(s, "salary", 0) or 0), 0)
    rep = _safe(lambda: float(getattr(s, "reputation", 10) or 10), 10.0)
    ask_min = int(salary * (0.8 + rep / 10 * 0.1))
    ask_max = int(salary * (1.2 + rep / 10 * 0.2))
    try:
        from game_classes import staff_market_ask
        market_ask = int(staff_market_ask(s))
    except Exception:
        market_ask = ask_min
    budget = _safe(lambda: team.staff_budget_remaining(), None) \
        if team is not None else None
    try:
        offer = int(request.args.get("offer") or 0)
    except (TypeError, ValueError):
        offer = 0
    return jsonify({
        "name": _safe(lambda: getattr(s, "full_name", "?"), "?"),
        "current_salary": salary,
        "current_years": _safe(lambda: int(getattr(
            s, "contract_years", 0) or 0), 0),
        "ask_min": ask_min, "ask_max": ask_max, "market_ask": market_ask,
        "budget_remaining": budget,
        "chance": round(_staff_offer_chance(s, offer), 3) if offer else None,
    })


@bp.route("/api/staff/<sid>/negotiate", methods=["POST"])
def api_staff_negotiate(sid):
    """Make an extension offer: demands + offer + negotiate_contract roll.
    Lands in the inbox on agreement."""
    s = _find_staff(sid)
    if s is None:
        return jsonify({"ok": False, "error": "not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    try:
        salary = int(data.get("salary") or 0)
    except (TypeError, ValueError):
        salary = 0
    try:
        years = int(data.get("years") or 0)
    except (TypeError, ValueError):
        years = 0
    if salary <= 0 or not (1 <= years <= 5):
        return jsonify({"ok": False,
                        "error": "offer needs a salary and 1-5 years"}), 400
    ok = enqueue_command("negotiate_staff_contract", staff_id=str(sid),
                         salary=salary, years=years)
    return jsonify({"ok": ok, "queued": "negotiate_staff_contract"})


@bp.route("/api/staff/hire-result")
def api_staff_hire_result():
    """Poll the outcome of the last staff write (hire / extension)."""
    live = _live()
    if live is None:
        return jsonify({"result": None})
    return jsonify({"result": _safe(lambda: getattr(
        live, "_web_staff_result", None))})


_STAFF_CATEGORIES = [
    ("Management", ["GENERAL_MANAGER", "ASSISTANT_GENERAL_MANAGER"]),
    ("Coaching", ["HEAD_COACH", "ASSISTANT_COACH", "ASSOCIATE_COACH",
                   "GOALIE_COACH", "POWER_PLAY_COACH", "PENALTY_KILL_COACH",
                   "SKATING_COACH", "SKILLS_COACH", "STRENGTH_COACH",
                   "CONDITIONING_COACH", "VIDEO_COACH"]),
    ("Scouting", ["HEAD_SCOUT", "PROFESSIONAL_SCOUT", "AMATEUR_SCOUT",
                  "EUROPEAN_SCOUT", "ADVANCE_SCOUT"]),
    ("Medical", ["TEAM_DOCTOR", "PHYSIOTHERAPIST"]),
    ("Analytics", ["ANALYTICS_DIRECTOR", "STATISTICIAN",
                   "MEDIA_RELATIONS"]),
]


def _staff_cat(s):
    try:
        name = str(getattr(getattr(s, "role", None), "name", "") or "")
    except Exception:
        name = ""
    for cat, roles in _STAFF_CATEGORIES:
        if name in roles:
            return cat
    return "Other"


def _web_staff_entry(s):
    from web_ui.screens.staff import to_web_staff
    d = to_web_staff(s)
    d["contract_years"] = _safe(
        lambda: int(getattr(s, "contract_years", 0) or 0), 0)
    return d


def _org_chart_payload(team):
    staff = _safe(lambda: list(getattr(team, "staff", []) or []), []) or []
    cats = {}
    for s in staff:
        cats.setdefault(_staff_cat(s), []).append(s)
    for members in cats.values():
        members.sort(key=lambda m: _safe(
            lambda: int(getattr(m, "overall_rating", 0) or 0), 0),
            reverse=True)

    def has_role(s, *names):
        return str(getattr(getattr(s, "role", None), "name", "")) in names

    tree = []
    mgmt = cats.get("Management", [])
    gm_s = next((s for s in mgmt if has_role(s, "GENERAL_MANAGER")), None)
    agms = [s for s in mgmt if s is not gm_s]
    tree.append({"level": "Management", "reports": [
        {"role": "General Manager",
         "person": _web_staff_entry(gm_s) if gm_s else None},
        {"role": "Assistant General Manager",
         "people": [_web_staff_entry(s) for s in agms]}]})
    coaches = cats.get("Coaching", [])
    hc = next((s for s in coaches if has_role(s, "HEAD_COACH")), None)
    assistants = [s for s in coaches
                  if has_role(s, "ASSISTANT_COACH", "ASSOCIATE_COACH")]
    specialists = [s for s in coaches
                   if s is not hc and s not in assistants]
    tree.append({"level": "Coaching Staff", "reports": [
        {"role": "Head Coach",
         "person": _web_staff_entry(hc) if hc else None},
        {"role": "Assistant Coaches",
         "people": [_web_staff_entry(s) for s in assistants]},
        {"role": "Specialized Coaches",
         "people": [_web_staff_entry(s) for s in specialists]}]})
    for dept in ("Scouting", "Medical", "Analytics"):
        tree.append({"level": dept, "reports": [
            {"role": dept,
             "people": [_web_staff_entry(s)
                        for s in cats.get(dept, [])]}]})
    other = cats.get("Other", [])
    if other:
        tree.append({"level": "Other", "reports": [
            {"role": "Other",
             "people": [_web_staff_entry(s) for s in other]}]})
    return {"tree": tree,
            "team": _safe(lambda: getattr(team, "team_name", ""), "")}


@bp.route("/api/staff/org-chart")
def api_staff_org_chart():
    """Organizational chart (desktop generate_organizational_chart parity)."""
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"error": "no team"}), 503
    return jsonify(_org_chart_payload(team))


@bp.route("/api/staff/report")
def api_staff_report():
    """Comprehensive staff report (desktop generate_staff_report parity):
    executive summary, department breakdown, contract expirations."""
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"error": "no team"}), 503
    staff = _safe(lambda: list(getattr(team, "staff", []) or []), []) or []
    cats = {}
    for s in staff:
        cats.setdefault(_staff_cat(s), []).append(s)
    departments = []
    for cat in [c for c, _ in _STAFF_CATEGORIES] + ["Other"]:
        members = cats.get(cat, [])
        if not members:
            continue
        web_members = []
        for s in sorted(members, key=lambda m: _safe(
                lambda: int(getattr(m, "overall_rating", 0) or 0), 0),
                reverse=True):
            d = _web_staff_entry(s)
            d["status"] = _staff_status(s)
            web_members.append(d)
        salaries = [m["salary"] for m in web_members]
        ratings = [m["rating"] for m in web_members]
        departments.append({
            "name": cat, "members": web_members,
            "count": len(web_members),
            "avg_rating": round(sum(ratings) / len(ratings), 1)
            if ratings else 0,
            "total_salary": sum(salaries),
        })
    total = len(staff)
    exp = [s for s in staff
           if _safe(lambda: int(getattr(s, "contract_years", 99) or 99),
                    99) <= 1]
    return jsonify({
        "team": _safe(lambda: getattr(team, "team_name", ""), ""),
        "summary": {
            "total_staff": total,
            "total_salary": sum(_safe(
                lambda: int(getattr(s, "salary", 0) or 0), 0)
                for s in staff),
            "avg_experience": round(sum(_safe(
                lambda: int(getattr(s, "experience", 0) or 0), 0)
                for s in staff) / total, 1) if total else 0,
            "avg_rating": round(sum(_safe(
                lambda: int(getattr(s, "overall_rating", 0) or 0), 0)
                for s in staff) / total, 1) if total else 0,
        },
        "departments": departments,
        "expiring": [{
            "id": _safe(lambda: str(getattr(s, "id", "")), ""),
            "name": _safe(lambda: getattr(s, "full_name", "?"), "?"),
            "role": _safe(lambda: str(getattr(getattr(s, "role", None),
                                             "value", "")), ""),
            "contract_years": _safe(
                lambda: int(getattr(s, "contract_years", 0) or 0), 0),
        } for s in exp],
    })


def _staff_status(s):
    """One-line staff status (desktop get_staff_status approximation)."""
    try:
        morale = int(getattr(s, "morale", 70) or 70)
    except Exception:
        morale = 70
    try:
        years = int(getattr(s, "contract_years", 2) or 2)
    except Exception:
        years = 2
    if years <= 1:
        return "Expiring contract"
    if morale >= 80:
        return "Content"
    if morale >= 60:
        return "Steady"
    if morale >= 40:
        return "Restless"
    return "Unhappy"
