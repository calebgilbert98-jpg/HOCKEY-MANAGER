"""Finances screen: salary cap, payroll, owner budget (read-only v1)."""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _web_app_ref, _safe, enqueue_command, _player_ovr

bp = Blueprint("finances", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _load_salary_cap_helpers():
    """Defensive import of salary_cap_system helpers (may fail in tests)."""
    try:
        import salary_cap_system as _scs
        return {
            "cap_breakdown": getattr(_scs, "cap_breakdown", None),
            "cap_space": getattr(_scs, "cap_space", None),
            "total_cap_charge": getattr(_scs, "total_cap_charge", None),
            "floor": getattr(_scs, "SALARY_CAP_FLOOR", 78_000_000),
            "default_cap": getattr(_scs, "DEFAULT_CAP", 104_000_000),
        }
    except Exception:
        return None


def _pos_str(p):
    """Clean position string: PlayerPosition enum -> 'RW', plain str passes through."""
    pos = _safe(lambda: getattr(p, "primary_position", "?"), "?")
    return str(getattr(pos, "value", pos))


def _player_cap_hit(p):
    """Best-effort per-player cap hit: contract AAV first, then .salary."""
    hit = _safe(lambda: int(getattr(getattr(p, "contract", None), "salary", 0) or 0)
                + int(getattr(getattr(p, "contract", None), "signing_bonus", 0) or 0)
                - int(getattr(p, "retained_amount", 0) or 0), None)
    if hit is not None and hit > 0:
        return max(0, hit)
    return _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)


@bp.route("/finances")
def finances_page():
    return render_template("finances.html")


@bp.route("/api/finances")
def api_finances():
    live = _live()
    if live is None:
        return jsonify({"error": "no live game bound", "cap": None})
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"error": "no user team"})

    scs = _load_salary_cap_helpers()
    default_cap = (scs or {}).get("default_cap", 104_000_000) if scs else 104_000_000
    floor = (scs or {}).get("floor", 78_000_000) if scs else 78_000_000

    cap = _safe(lambda: int(getattr(team, "salary_cap", default_cap) or default_cap),
                default_cap)

    # --- Cap breakdown: real module first, sum-of-salaries fallback -------
    breakdown = None
    if scs and scs.get("cap_breakdown"):
        breakdown = _safe(lambda: scs["cap_breakdown"](team))
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
    sum_hits = _safe(lambda: sum(_player_cap_hit(p) for p in roster), 0)
    if (not isinstance(breakdown, dict)
            or (_safe(lambda: int(breakdown.get("total", 0) or 0), 0) == 0
                and sum_hits > 0)):
        # No contract data (e.g. tests) or module unavailable: fall back to
        # summing player cap hits.
        roster_charge = sum_hits
        breakdown = {
            "cap": cap, "roster": roster_charge, "buried": 0,
            "waivers_shed": 0, "buyouts": 0, "seeded_buyout": 0,
            "seeded_retained": 0, "seeded_overage": 0, "retained": 0,
            "retention_slots": "0/3", "dead_cap": 0, "total": roster_charge,
            "space": cap - roster_charge, "over_cap": (cap - roster_charge) < 0,
            "floor": floor, "floor_space": roster_charge - floor,
            "under_floor": roster_charge < floor,
        }

    total = _safe(lambda: int(breakdown.get("total", 0) or 0), 0)
    space = _safe(lambda: int(breakdown.get("space", cap - total) or 0), 0)
    dead_cap = _safe(lambda: int(breakdown.get("dead_cap", 0) or 0), 0)
    roster_charge = _safe(lambda: int(breakdown.get("roster", 0) or 0), 0)
    over_cap = _safe(lambda: bool(breakdown.get("over_cap", space < 0)), space < 0)
    under_floor = _safe(lambda: bool(breakdown.get("under_floor", total < floor)),
                        total < floor)

    # status: green comfortable / yellow tight / red over-or-under-floor
    pct_free = (space / cap) if cap else 0
    if over_cap:
        status = "over"
    elif under_floor:
        status = "under_floor"
    elif pct_free < 0.03:
        status = "tight"
    else:
        status = "comfortable"

    # --- Payroll breakdown by player (top cap hits) -----------------------
    hits = []
    for p in roster:
        try:
            hits.append({
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "position": _pos_str(p),
                "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                "overall": _player_ovr(p),
                "salary": _player_cap_hit(p),
                "injured": _safe(lambda: bool(getattr(p, "is_injured", False)), False),
            })
        except Exception:
            continue
    hits.sort(key=lambda h: h["salary"], reverse=True)
    top_hits = hits[:15]

    # --- Owner budget ------------------------------------------------------
    budget = _safe(lambda: int(getattr(team, "player_budget", 0) or 0), 0)
    bonus_spent = _safe(lambda: int(getattr(team, "bonus_spent", 0) or 0), 0)
    budget_remaining = _safe(lambda: int(team.player_budget_remaining()),
                             budget - bonus_spent)

    return jsonify({
        "team": _safe(lambda: getattr(team, "team_name", ""), ""),
        "cap": cap,
        "floor": floor,
        "total": total,
        "space": space,
        "dead_cap": dead_cap,
        "roster_charge": roster_charge,
        "over_cap": over_cap,
        "under_floor": under_floor,
        "status": status,
        "pct_free": pct_free,
        "breakdown": breakdown,
        "top_hits": top_hits,
        "roster_count": len(hits),
        "owner_budget": {
            "budget": budget,
            "spent": bonus_spent,
            "remaining": budget_remaining,
        },
    })


# ------------------------------------------------------------------
# Buyout calculator (web port of BuyoutCalculatorView in windows.py).
# Uses the real buyout math (windows.buyout_schedule) and the real
# mutation (buyout_window.execute_buyout) via a bridge command.
# ------------------------------------------------------------------

def _buyout_schedule(p):
    """(total, annual, byears, rows) via the game's real NHL buyout math.
    Never raises."""
    try:
        from windows import buyout_schedule
        return buyout_schedule(p)
    except Exception:
        return 0, 0, 0, []


def _buyout_candidate_row(p):
    c = _safe(lambda: getattr(p, "contract", None))
    if c is None:
        return None
    salary = _safe(lambda: int(getattr(c, "salary", 0) or 0), 0)
    years = _safe(lambda: int(getattr(c, "years_remaining", 0) or 0), 0)
    if salary <= 0 or years <= 0:
        return None
    total, annual, byears, rows = _buyout_schedule(p)
    if not rows:
        return None
    return {
        "id": _safe(lambda: str(getattr(p, "id", id(p)))),
        "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
        "position": _pos_str(p),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
        "cap_hit": salary,
        "years_left": years,
        "buyout_cost": int(total),
        "annual_dead": int(annual),
        "dead_years": int(byears),
        "schedule": [
            {"year": int(i), "cap_hit": int(hit), "savings": int(savings)}
            for (i, hit, savings) in rows
        ],
        "nmc": _safe(lambda: bool(getattr(c, "no_movement_clause", False)), False),
        "ntc": _safe(lambda: bool(getattr(c, "no_trade_clause", False)), False),
    }


@bp.route("/api/finances/buyouts")
def api_finances_buyouts():
    """Buyout calculator payload: candidates (real buyout math) + active
    buyout cap hits + the window gate."""
    live = _live()
    if live is None:
        return jsonify({"candidates": [], "error": "no live game"}), 503
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"candidates": [], "error": "no user team"}), 503
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
    candidates = []
    for p in roster:
        try:
            row = _buyout_candidate_row(p)
            if row:
                candidates.append(row)
        except Exception:
            continue
    candidates.sort(key=lambda r: r["cap_hit"], reverse=True)
    try:
        import transaction_windows as _tw
        win_ok, win_msg = _tw.check_window(
            "buyout", _safe(lambda: getattr(live, "current_date", None)))
    except Exception:
        win_ok, win_msg = True, ""
    hits = _safe(lambda: dict(getattr(team, "buyout_cap_hits", None) or {}), {}) or {}
    return jsonify({
        "candidates": candidates,
        "active_buyouts": [{"year": int(y), "hit": int(v)}
                           for y, v in sorted(hits.items())],
        "window": {"ok": bool(win_ok), "reason": win_msg or ""},
    })


@bp.route("/api/finances/buyouts/execute", methods=["POST"])
def api_finances_buyouts_execute():
    """Queue a buyout of a roster player. Server validates the buyout
    window; the main-thread op revalidates and runs the real engine."""
    from flask import request
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    try:
        import transaction_windows as _tw
        ok, why = _tw.check_window(
            "buyout", _safe(lambda: getattr(live, "current_date", None)))
        if not ok:
            return jsonify({"ok": False, "error": why}), 422
    except Exception:
        pass
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or [] \
        if team else []
    player = next((p for p in roster
                   if str(_safe(lambda: getattr(p, "id", ""), "")) == str(pid)),
                  None)
    if player is None:
        return jsonify({"ok": False, "error": "player not on roster"}), 404
    if _buyout_candidate_row(player) is None:
        return jsonify({"ok": False, "error": "nothing to buy out (no remaining term)"}), 422
    queued = enqueue_command("execute_buyout", player_id=str(pid))
    return jsonify({"ok": bool(queued), "queued": "execute_buyout"})


# ======================================================================
# Batch D: Finances depth.
# Desktop parity (FinancesWindow, windows.py):
#   - Projections tab (create_projections_tab / update_projections_view):
#     year picker, committed payroll for a future season, expiring
#     contracts with estimated asks + status labels.
#   - Reports tab: 5 reports (salary_breakdown, contract_timeline,
#     position_analysis, age_demographics, performance_salary).
#   - Management tab: recommendations + quick actions
#     (generate_recommendations).
#   - Contracts view: filters + status labels
#     (determine_contract_status: RFA / UFA / Expiring / Long-term).
#   - Cap position breakdown + AHL payroll
#     (calculate_position_breakdown / calculate_ahl_payroll).
# ======================================================================

def _fin_team(live):
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)


def _fin_season(live):
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: int(getattr(getattr(gm, "league", None),
                                    "season_year", 0) or 0), 0)


def _contract_salary(p):
    c = _safe(lambda: getattr(p, "contract", None))
    s = _safe(lambda: int(getattr(c, "salary", 0) or 0), 0)
    if s <= 0:
        s = _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)
    return max(0, s)


def _contract_years_left(p):
    c = _safe(lambda: getattr(p, "contract", None))
    y = _safe(lambda: getattr(c, "years_remaining", None))
    if y is None:
        y = _safe(lambda: getattr(p, "contract_years", 1), 1)
    return max(0, _safe(lambda: int(y or 0), 0))


def _contract_status(p, years_left):
    """Desktop determine_contract_status: RFA / UFA / Expiring / Long-term."""
    age = _safe(lambda: int(getattr(p, "age", 22) or 22), 22)
    if years_left <= 1:
        return "RFA" if age < 25 else "UFA"
    if years_left <= 2:
        return "Expiring"
    return "Long-term"


def _estimate_ask(p):
    """Deterministic port of estimate_contract_ask (desktop uses random;
    the web uses the band midpoint so the number is stable and honest)."""
    try:
        ovr = float(p.overall_rating())
    except Exception:
        ovr = 75.0
    age = _safe(lambda: int(getattr(p, "age", 22) or 22), 22)
    cur = _contract_salary(p)
    if ovr >= 85:
        lo, hi = 8_000_000, 12_000_000
    elif ovr >= 80:
        lo, hi = 5_000_000, 8_000_000
    elif ovr >= 75:
        lo, hi = 3_000_000, 5_000_000
    elif ovr >= 70:
        lo, hi = 1_500_000, 3_000_000
    else:
        lo, hi = 750_000, 1_500_000
    base = (lo + hi) / 2
    if age < 25:
        base *= 0.9
    elif age > 32:
        base *= 0.8
    if cur > 0:
        base = max(cur * 0.7, min(cur * 1.5, base))
    return int(base)


@bp.route("/api/finances/projections")
def api_finances_projections():
    """Future-season salary projection: ?year=. Committed payroll =
    players whose term outlives the target year; everyone else is
    expiring with an estimated ask + status label."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    team = _fin_team(live)
    if team is None:
        return jsonify({"ok": False, "error": "no user team"}), 503
    season = _fin_season(live)
    try:
        year = int(request.args.get("year") or season)
    except (TypeError, ValueError):
        year = season
    years_ahead = max(0, year - season)
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    committed, expiring = 0, []
    for p in roster:
        try:
            years_left = _contract_years_left(p)
            salary = _contract_salary(p)
            if years_left > years_ahead:
                committed += salary
            else:
                expiring.append({
                    "id": str(_safe(lambda: getattr(p, "id", ""), "")),
                    "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                    "position": _pos_str(p),
                    "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                    "salary": salary,
                    "years_left": years_left,
                    "status": _contract_status(p, years_left),
                    "estimated_ask": _estimate_ask(p),
                })
        except Exception:
            continue
    expiring.sort(key=lambda e: -e["salary"])
    cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                            or 104_000_000), 104_000_000)
    return jsonify({
        "ok": True,
        "season": season,
        "year": year,
        "years_ahead": years_ahead,
        "committed_payroll": committed,
        "projected_cap": cap,
        "projected_space": cap - committed,
        "expiring_count": len(expiring),
        "expiring": expiring,
    })


def _report_salary_breakdown(team, season, cap):
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    payroll = sum(_contract_salary(p) for p in roster)
    rows = []
    for p in sorted(roster, key=_contract_salary, reverse=True)[:10]:
        s = _contract_salary(p)
        rows.append({
            "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
            "position": _pos_str(p),
            "salary": s,
            "pct": round(100 * s / payroll, 1) if payroll else 0,
        })
    return {
        "title": "Salary Breakdown",
        "summary": {"payroll": payroll, "cap": cap, "space": cap - payroll,
                    "utilization_pct": round(100 * payroll / cap, 1)
                    if cap else 0},
        "top_salaries": rows,
        "position_breakdown": _position_breakdown(team),
    }


def _report_contract_timeline(team, season):
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    groups = {}
    for p in roster:
        try:
            yl = _contract_years_left(p)
            yr = season + yl
            groups.setdefault(yr, []).append({
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "salary": _contract_salary(p),
                "age_at_expiry": _safe(
                    lambda: int(getattr(p, "age", 22) or 22), 22) + yl,
                "status": ("RFA" if _safe(
                    lambda: int(getattr(p, "age", 22) or 22), 22) + yl < 25
                    else "UFA"),
            })
        except Exception:
            continue
    years = []
    for yr in sorted(groups):
        ps = sorted(groups[yr], key=lambda r: -r["salary"])
        years.append({
            "year": yr,
            "count": len(ps),
            "total_salary": sum(r["salary"] for r in ps),
            "players": ps,
        })
    return {"title": "Contract Timeline", "years": years}


def _position_breakdown(team):
    """Desktop calculate_position_breakdown: Goalies/Defense/Forwards."""
    pos = {"Goalies": {"count": 0, "total": 0},
           "Defense": {"count": 0, "total": 0},
           "Forwards": {"count": 0, "total": 0}}
    try:
        from game_classes import PlayerPosition as _PP
    except Exception:
        _PP = None
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    for p in roster:
        try:
            s = _contract_salary(p)
            pp = getattr(p, "primary_position", None)
            if _PP is not None and pp == _PP.GOALIE:
                pos["Goalies"]["count"] += 1
                pos["Goalies"]["total"] += s
            elif _PP is not None and pp in (
                    _PP.LEFT_DEFENSE, _PP.RIGHT_DEFENSE, _PP.DEFENSE):
                pos["Defense"]["count"] += 1
                pos["Defense"]["total"] += s
            else:
                pos["Forwards"]["count"] += 1
                pos["Forwards"]["total"] += s
        except Exception:
            continue
    for d in pos.values():
        d["avg"] = d["total"] // d["count"] if d["count"] else 0
    return pos


def _report_position_analysis(team):
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    try:
        from game_classes import PlayerPosition as _PP
    except Exception:
        _PP = None
    groups = {"Goalies": [], "Defense": [], "Centers": [], "Wingers": []}
    for p in roster:
        try:
            pp = getattr(p, "primary_position", None)
            if _PP is not None and pp == _PP.GOALIE:
                groups["Goalies"].append(p)
            elif _PP is not None and pp in (
                    _PP.LEFT_DEFENSE, _PP.RIGHT_DEFENSE, _PP.DEFENSE):
                groups["Defense"].append(p)
            elif _PP is not None and pp == _PP.CENTER:
                groups["Centers"].append(p)
            else:
                groups["Wingers"].append(p)
        except Exception:
            continue
    out = []
    for name, ps in groups.items():
        if not ps:
            continue
        total = sum(_contract_salary(p) for p in ps)
        try:
            avg_ovr = sum(float(p.overall_rating()) for p in ps) / len(ps)
        except Exception:
            avg_ovr = 0
        out.append({
            "position": name, "count": len(ps), "total_salary": total,
            "avg_salary": int(total / len(ps)) if ps else 0,
            "avg_age": round(sum(_safe(
                lambda q=p: int(getattr(q, "age", 22) or 22), 22)
                for p in ps) / len(ps), 1) if ps else 0,
            "avg_overall": round(avg_ovr, 1),
            "players": sorted(
                [{"name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                  "salary": _contract_salary(p),
                  "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0)}
                 for p in ps], key=lambda r: -r["salary"]),
        })
    return {"title": "Position Analysis", "groups": out}


def _report_age_demographics(team):
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    bands = {"Under 25": (0, 24), "25-29": (25, 29), "30-34": (30, 34),
             "35+": (35, 99)}
    out = []
    for name, (lo, hi) in bands.items():
        ps = [p for p in roster
              if lo <= _safe(lambda: int(getattr(p, "age", 27) or 27), 27)
              <= hi]
        total = sum(_contract_salary(p) for p in ps)
        out.append({
            "band": name, "count": len(ps), "total_salary": total,
            "avg_salary": int(total / len(ps)) if ps else 0,
            "players": sorted(
                [{"name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                  "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                  "salary": _contract_salary(p)} for p in ps],
                key=lambda r: -r["salary"]),
        })
    return {"title": "Age Demographics", "bands": out}


def _report_performance_salary(team):
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    rows = []
    for p in roster:
        try:
            pos = _pos_str(p)
            s = _contract_salary(p)
            if pos.upper() in ("G", "GOALIE"):
                gp = _safe(lambda: int(getattr(p, "games_played", 0) or 0), 0)
                sv = _safe(lambda: float(getattr(p, "save_percentage", 0)
                                        or 0), 0.0)
                metric, metric_label = sv, "SV%"
            else:
                pts = _safe(lambda: int(getattr(p, "points", 0) or 0), 0)
                metric, metric_label = pts, "PTS"
            per = (s / metric) if metric else None
            rows.append({
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "position": pos, "salary": s,
                "metric": metric, "metric_label": metric_label,
                "dollar_per": int(per) if per else None,
            })
        except Exception:
            continue
    rows.sort(key=lambda r: (r["dollar_per"] is None,
                             r["dollar_per"] or 0))
    return {"title": "Performance vs Salary", "rows": rows}


_REPORTS = {
    "salary_breakdown": _report_salary_breakdown,
    "contract_timeline": _report_contract_timeline,
    "position_analysis": _report_position_analysis,
    "age_demographics": _report_age_demographics,
    "performance_salary": _report_performance_salary,
}

REPORT_LIST = [
    ("salary_breakdown", "Salary Breakdown"),
    ("contract_timeline", "Contract Timeline"),
    ("position_analysis", "Position Analysis"),
    ("age_demographics", "Age Demographics"),
    ("performance_salary", "Performance vs Salary"),
]


@bp.route("/api/finances/reports")
def api_finances_reports():
    """The 5 desktop financial reports (?report=key)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    team = _fin_team(live)
    if team is None:
        return jsonify({"ok": False, "error": "no user team"}), 503
    key = (request.args.get("report") or "salary_breakdown").strip()
    fn = _REPORTS.get(key)
    if fn is None:
        return jsonify({"ok": False, "error": f"unknown report {key!r}",
                        "reports": [k for k, _ in REPORT_LIST]}), 404
    season = _fin_season(live)
    cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                            or 104_000_000), 104_000_000)
    if key in ("salary_breakdown", "contract_timeline"):
        data = fn(team, season, cap) if key == "salary_breakdown" \
            else fn(team, season)
    else:
        data = fn(team)
    return jsonify({"ok": True, "report": key,
                    "reports": [{"key": k, "label": lbl}
                                for k, lbl in REPORT_LIST],
                    "data": data})


@bp.route("/api/finances/management")
def api_finances_management():
    """Management recommendations + quick actions (desktop
    generate_recommendations). Quick actions enqueue real ops."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    team = _fin_team(live)
    if team is None:
        return jsonify({"ok": False, "error": "no user team"}), 503
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    payroll = sum(_contract_salary(p) for p in roster)
    cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                            or 104_000_000), 104_000_000)
    space = cap - payroll
    pct = (payroll / cap * 100) if cap else 0
    recs = []
    if pct > 95:
        recs.append(("urgent",
            "You are very close to the salary cap. Consider trading "
            "high-salary players or demoting players to create space."))
    elif pct > 90:
        recs.append(("warning",
            "Limited cap space available. Be cautious with any new "
            "signings."))
    elif pct < 70:
        recs.append(("info",
            "You have significant cap space available. Consider upgrading "
            "your roster through free agency or trades."))
    expiring = [p for p in roster if _contract_years_left(p) <= 1]
    if len(expiring) > 8:
        recs.append(("warning",
            f"You have {len(expiring)} players with expiring contracts. "
            "Start extension negotiations early to avoid losing key "
            "players."))
    old_exp = [p for p in roster
               if _safe(lambda: int(getattr(p, "age", 22) or 22), 22) > 33
               and _contract_salary(p) > 4_000_000]
    if old_exp:
        names = ", ".join(_safe(lambda: getattr(p, "full_name", "?"), "?")
                          for p in old_exp[:3])
        recs.append(("info",
            f"Consider the future value of older, expensive players: "
            f"{names}{'...' if len(old_exp) > 3 else ''}"))
    posd = _position_breakdown(team)
    if payroll:
        g_pct = 100 * posd["Goalies"]["total"] / payroll
        d_pct = 100 * posd["Defense"]["total"] / payroll
        f_pct = 100 * posd["Forwards"]["total"] / payroll
        if g_pct > 15:
            recs.append(("info",
                "Your goalie spending is high relative to other positions. "
                "Consider if this allocation is optimal."))
        if d_pct > 35:
            recs.append(("info",
                "High spending on defense. Ensure this matches your team "
                "strategy."))
        if f_pct < 50:
            recs.append(("info",
                "Consider if your forward spending is sufficient for "
                "offensive production."))
    if not recs:
        recs.append(("ok",
            "Your financial situation looks stable. Continue monitoring "
            "contract expirations and cap space."))
    return jsonify({
        "ok": True,
        "payroll": payroll, "cap": cap, "space": space,
        "utilization_pct": round(pct, 1),
        "recommendations": [{"level": lvl, "text": txt}
                            for lvl, txt in recs],
        # Quick actions: real ops the bridge executes (see finances.py
        # bridge handler section).
        "quick_actions": [
            {"id": "auto_negotiate_extensions",
             "label": "Auto-negotiate all expiring extensions",
             "op": "auto_negotiate_extensions",
             "enabled": bool(expiring)},
            {"id": "open_contracts",
             "label": "Review contracts",
             "route": "/contracts", "enabled": True},
            {"id": "open_free_agents",
             "label": "Browse free agents",
             "route": "/free_agents", "enabled": space > 1_000_000},
        ],
    })


@bp.route("/api/finances/contracts")
def api_finances_contracts():
    """Full contracts view with filters + status labels (desktop
    update_contracts_view / determine_contract_status). ?filter=
    all|expiring|ufa|rfa|longterm&pos=&q=&sort=."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    team = _fin_team(live)
    if team is None:
        return jsonify({"ok": False, "error": "no user team"}), 503
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    filt = (request.args.get("filter") or "all").strip().lower()
    posf = (request.args.get("pos") or "all").strip().upper()
    q = (request.args.get("q") or "").strip().lower()
    sort = (request.args.get("sort") or "salary").strip().lower()
    rows = []
    for p in roster:
        try:
            yl = _contract_years_left(p)
            status = _contract_status(p, yl)
            pos = _pos_str(p)
            name = _safe(lambda: getattr(p, "full_name", "?"), "?")
            if filt == "expiring" and yl > 1:
                continue
            if filt == "ufa" and status != "UFA":
                continue
            if filt == "rfa" and status != "RFA":
                continue
            if filt == "longterm" and status != "Long-term":
                continue
            if posf != "ALL" and pos.upper() != posf:
                continue
            if q and q not in name.lower():
                continue
            c = _safe(lambda: getattr(p, "contract", None))
            rows.append({
                "id": str(_safe(lambda: getattr(p, "id", ""), "")),
                "name": name,
                "position": pos,
                "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                "salary": _contract_salary(p),
                "years_left": yl,
                "status": status,
                "no_trade": _safe(lambda: bool(
                    getattr(c, "no_trade_clause", False)), False),
                "no_movement": _safe(lambda: bool(
                    getattr(c, "no_movement_clause", False)), False),
                "two_way": _safe(lambda: bool(
                    getattr(c, "two_way", False)), False),
                "estimated_ask": _estimate_ask(p),
            })
        except Exception:
            continue
    if sort == "name":
        rows.sort(key=lambda r: r["name"])
    elif sort == "years":
        rows.sort(key=lambda r: r["years_left"])
    elif sort == "age":
        rows.sort(key=lambda r: -r["age"])
    else:
        rows.sort(key=lambda r: -r["salary"])
    return jsonify({
        "ok": True,
        "filters": ["all", "expiring", "ufa", "rfa", "longterm"],
        "contracts": rows,
        "count": len(rows),
    })


@bp.route("/api/finances/cap_position")
def api_finances_cap_position():
    """Cap position breakdown + AHL payroll (desktop
    calculate_position_breakdown / calculate_ahl_payroll /
    calculate_buried_salary)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    team = _fin_team(live)
    if team is None:
        return jsonify({"ok": False, "error": "no user team"}), 503
    posd = _position_breakdown(team)
    ahl = _safe(lambda: list(getattr(team, "ahl_roster", None) or []),
                []) or []
    ahl_payroll = sum(_contract_salary(p) for p in ahl)
    # Buried salary: AHL salary above the bury threshold counts against
    # the cap (desktop calculate_buried_salary).
    try:
        from salary_cap_system import BURY_THRESHOLD as _bt
        bury_cap = int(_bt)
    except Exception:
        bury_cap = 1_150_000
    buried = 0
    for p in ahl:
        s = _contract_salary(p)
        if s > bury_cap:
            buried += s - bury_cap
    cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                            or 104_000_000), 104_000_000)
    floor = _safe(lambda: int(getattr(team, "salary_floor", 78_000_000)
                              or 78_000_000), 78_000_000)
    payroll = sum(_contract_salary(p) for p in
                  (_safe(lambda: list(getattr(team, "roster", None) or []),
                         []) or []))
    return jsonify({
        "ok": True,
        "cap": cap, "floor": floor,
        "payroll": payroll, "space": cap - payroll,
        "position_breakdown": posd,
        "ahl": {
            "count": len(ahl),
            "payroll": ahl_payroll,
            "bury_threshold": bury_cap,
            "buried_salary": buried,
        },
    })
