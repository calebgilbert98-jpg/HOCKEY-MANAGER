# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Entry draft screen: draft board with pick order and results."""
from flask import Blueprint, jsonify, render_template, request
from web_ui.bridge import _safe, _player_ovr

bp = Blueprint("draft", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _prospect_index(league):
    """Every draftable prospect by id: live class + already-drafted ones on
    team lists (mirrors EntryDraftSession._prospect_index, read-only)."""
    idx = {}
    for p in _safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []:
        try:
            pid = getattr(p, "id", None)
            if pid is not None:
                idx.setdefault(pid, p)
        except Exception:
            continue
    for t in _safe(lambda: list(getattr(league, "teams", None) or []), []) or []:
        for attr in ("prospects", "roster", "ahl_roster"):
            for p in _safe(lambda: list(getattr(t, attr, None) or []), []) or []:
                try:
                    pid = getattr(p, "id", None)
                    if pid is not None:
                        idx.setdefault(pid, p)
                except Exception:
                    continue
    return idx


def get_draft_state(app):
    """Serialize the entry draft session for the board."""
    gm = _safe(lambda: app.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: app.league)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    if league is None:
        return {"active": False}

    session = _safe(lambda: getattr(league, "entry_draft_session", None))
    if session is None or _safe(lambda: bool(session.is_complete()), True):
        return {"active": False}

    year = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    slots = _safe(lambda: list(getattr(session, "slots", None) or []), []) or []
    picks = _safe(lambda: list(getattr(session, "picks", None) or []), []) or []
    cur_idx = _safe(lambda: int(getattr(session, "current_pick", 0) or 0), 0)
    user_name = _safe(lambda: getattr(team, "team_name", ""), "") or ""

    pick_by_overall = {}
    for p in picks:
        try:
            pick_by_overall[int(p.get("overall", -1))] = p
        except Exception:
            continue

    prospects = _prospect_index(league)

    def _to_web_prospect(p):
        return {
            "id": _safe(lambda: str(getattr(p, "id", id(p)))),
            "name": _safe(lambda: getattr(p, "full_name", "?")),
            "position": _safe(lambda: getattr(p, "primary_position", "?")),
            "age": _safe(lambda: int(getattr(p, "age", 0) or 0)),
            "overall": _player_ovr(p),
        }

    board = []
    rounds = set()
    for s in slots:
        try:
            overall = int(s.get("overall", 0) or 0)
            rnd = int(s.get("round", 0) or 0)
            rounds.add(rnd)
            owner = str(s.get("owner", "") or "")
            rec = pick_by_overall.get(overall)
            prospect = None
            if rec is not None:
                prospect = prospects.get(rec.get("player_id"))
            board.append({
                "overall": overall,
                "round": rnd,
                "owner": owner,
                "is_user_pick": bool(user_name and owner == user_name),
                "is_current": overall == cur_idx + 1,
                "made": rec is not None,
                "team": str(rec.get("team", "")) if rec is not None else None,
                "prospect": _to_web_prospect(prospect) if prospect is not None else None,
            })
        except Exception:
            continue

    made_count = len(pick_by_overall)
    user_picks = sorted(
        [b["overall"] for b in board if b["is_user_pick"] and not b["made"]])
    return {
        "active": True,
        "year": year,
        "current_overall": cur_idx + 1,
        "total_slots": len(board),
        "made_count": made_count,
        "rounds": sorted(rounds),
        "user_picks": user_picks,
        "board": board,
    }


@bp.route("/draft")
def draft_page():
    return render_template("draft.html")


@bp.route("/api/draft")
def api_draft():
    live = _live()
    if live is None:
        return jsonify({"active": False})
    return jsonify(get_draft_state(live))


# --- War room: available / my picks / scout report -----------------------


def _draft_session(live):
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    return _safe(lambda: getattr(league, "entry_draft_session", None))


def _prospect_pos(p):
    """Position string from primary_position enum or position attr."""
    try:
        pp = getattr(p, "primary_position", None)
        if pp is not None:
            v = getattr(pp, "value", None) or str(pp)
            # "PlayerPosition.RIGHT_DEFENSE" -> "RD"; value is already "RD"
            v = str(v).split(".")[-1].replace("RIGHT_", "R").replace("LEFT_", "L").replace("_DEFENSE", "D").replace("_WING", "W").replace("CENTER", "C").replace("GOALIE", "G")
            return v
    except Exception:
        pass
    return _safe(lambda: str(getattr(p, "primary_position", "?") or "?"), "?")


def _available_prospects(live):
    """Draftable prospects not yet picked."""
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    if league is None:
        return []
    session = _draft_session(live)
    picked_ids = set()
    if session is not None:
        for p in (_safe(lambda: list(getattr(session, "picks", None) or []), []) or []):
            try:
                picked_ids.add(str(p.get("player_id")))
            except Exception:
                pass
    prospects = _safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []
    out = []
    for p in prospects:
        try:
            pid = str(getattr(p, "id", ""))
            if pid in picked_ids:
                continue
            out.append({
                "id": pid,
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "position": _prospect_pos(p),
                "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                "overall": _player_ovr(p),
                "potential": _safe(lambda: str(getattr(p, "potential_grade", "?") or "?"), "?"),
            })
        except Exception:
            continue
    try:
        out.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return out


@bp.route("/api/draft/available")
def api_draft_available():
    live = _live()
    if live is None:
        return jsonify({"prospects": []})
    pos = (request.args.get("pos") or "All").strip()
    q = (request.args.get("q") or "").strip().lower()
    prospects = _available_prospects(live)
    if pos != "All":
        prospects = [p for p in prospects
                     if (p.get("position") or "").upper() == pos
                     or (pos == "D" and (p.get("position") or "").upper() in ("LD", "RD"))
                     or (pos == "W" and (p.get("position") or "").upper() in ("LW", "RW"))]
    if q:
        prospects = [p for p in prospects if q in (p.get("name") or "").lower()]
    return jsonify({"prospects": prospects})


@bp.route("/api/draft/scout_report")
def api_draft_scout_report():
    """Scout report for one prospect."""
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    pid = str(request.args.get("player_id") or "")
    target = None
    for p in _available_prospects(live):
        if p["id"] == pid:
            # Find the real object for attributes
            gm = _safe(lambda: live.game_manager)
            league = _safe(lambda: gm.league) or _safe(lambda: live.league)
            for q in (_safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []):
                if str(getattr(q, "id", "")) == pid:
                    target = q
                    break
            break
    if target is None:
        return jsonify({"error": "prospect not found"}), 404
    attrs = {}
    for a in ("shooting_accuracy", "shooting_power", "passing", "skating",
              "checking", "defensive_awareness", "offensive_awareness",
              "strength", "hockey_iq", "potential_grade"):
        try:
            v = getattr(target, a, None)
            if v is not None:
                attrs[a] = v if isinstance(v, str) else int(v)
        except Exception:
            pass
    report = _safe(lambda: getattr(target, "scout_report", "") or "", "")
    strengths = _safe(lambda: list(getattr(target, "strengths", None) or []), []) or []
    weaknesses = _safe(lambda: list(getattr(target, "weaknesses", None) or []), []) or []
    return jsonify({
        "id": pid,
        "name": _safe(lambda: getattr(target, "full_name", "?"), "?"),
        "position": _prospect_pos(target),
        "age": _safe(lambda: int(getattr(target, "age", 0) or 0), 0),
        "overall": _safe(lambda: int(getattr(target, "overall", 0) or 0), 0),
        "attributes": attrs,
        "report": report,
        "strengths": strengths,
        "weaknesses": weaknesses,
    })


@bp.route("/api/draft/pick", methods=["POST"])
def api_draft_pick():
    """Draft Selected: queue a user pick (2-step confirm on client)."""
    data = request.get_json(force=True, silent=True) or {}
    pid = str(data.get("player_id") or "")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    import web_ui.bridge as _b
    _b.enqueue_command({"op": "draft_pick", "player_id": pid})
    return jsonify({"ok": True})


@bp.route("/api/draft/sim_pick", methods=["POST"])
def api_draft_sim_pick():
    """Sim Pick: AI selects for the current slot."""
    import web_ui.bridge as _b
    _b.enqueue_command({"op": "draft_sim_pick"})
    return jsonify({"ok": True})


# --- Draft depth: buzz ticker / draft-day trade feed / draft grades ------


def _draft_league(live):
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: gm.league) or _safe(lambda: live.league)


def _draft_year_for(league, session):
    y = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    if y:
        return y
    y = _safe(lambda: int(getattr(league, "season_year", 0) or 0), 0)
    return y + 1 if y else 0


def _game_month(live):
    """Month of the in-game date; defaults to draft month (June)."""
    gm = _safe(lambda: live.game_manager)
    d = _safe(lambda: gm.current_date)
    try:
        m = int(d.month)
        if 1 <= m <= 12:
            return m
    except Exception:
        pass
    try:
        s = str(d or "")
        m = int(s.split("-")[1])
        if 1 <= m <= 12:
            return m
    except Exception:
        pass
    return 6


@bp.route("/api/draft/buzz")
def api_draft_buzz():
    """Draft buzz ticker: pick drama from real made picks, engine-generated
    draft chatter from real prospects in league.draft_prospects, plus a
    read-only steal-watch from real rostered players. Deterministic: the
    engine's narrative RNG is pinned per draft year and the global RNG
    state is restored, so reading buzz never perturbs the sim."""
    live = _live()
    if live is None:
        return jsonify({"items": []})
    league = _draft_league(live)
    if league is None:
        return jsonify({"items": []})
    import random as _random
    import draft_night as _dn
    import draft_stories as _ds

    prospects = _safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []
    session = _draft_session(live)
    year = _draft_year_for(league, session)
    items = []

    # Rank board positions for reach/steal detection (real draft_ranking).
    def _rank_score(p):
        try:
            return float(getattr(p, "draft_ranking", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    board_pos = {}
    for i, p in enumerate(sorted(prospects, key=_rank_score, reverse=True), 1):
        try:
            pid = getattr(p, "id", None)
            if pid is not None:
                board_pos.setdefault(str(pid), i)
        except Exception:
            continue

    # 1. Live pick drama from picks actually made (engine ticker language).
    slot_round = {}
    for s in (_safe(lambda: list(getattr(session, "slots", None) or []), []) or []):
        try:
            slot_round[int(s.get("overall", 0) or 0)] = int(s.get("round", 0) or 0)
        except Exception:
            continue
    pidx = _prospect_index(league)
    made = []
    for p in (_safe(lambda: list(getattr(session, "picks", None) or []), []) or []):
        try:
            overall = int(p.get("overall", 0) or 0)
            made.append((overall, p))
        except Exception:
            continue
    made.sort()
    trng = _random.Random(_dn.stable_draft_seed(year, "ticker"))
    for overall, p in made[-12:]:  # most recent first, capped
        try:
            player = pidx.get(p.get("player_id"))
            if player is None:
                continue
            team = str(p.get("team", "") or "")
            proj = board_pos.get(str(getattr(player, "id", "")))
            diff = (proj - overall) if proj else 0
            reach, steal = diff >= 10, diff <= -10
            kind = "reach" if reach else ("steal" if steal else
                                         ("milestone" if overall <= 3 and abs(diff) <= 2 else "pick"))
            rnd = slot_round.get(overall) or ((overall - 1) // 32 + 1)
            items.append({
                "kind": kind,
                "title": "Reach Alert" if reach else ("Steal Watch" if steal else "Pick #%d" % overall),
                "text": _dn.ticker_line(overall, team, player, rnd,
                                        reach=reach, steal=steal, rng=trng),
                "prospect_id": str(getattr(player, "id", "")),
                "team": team,
                "overall": overall,
            })
        except Exception:
            continue
    items.reverse()

    # 2 + 3. Engine chatter over real prospects (headline storylines first,
    # then the current month's build-up beat). RNG pinned + restored.
    state = _random.getstate()
    try:
        _random.seed(_dn.stable_draft_seed(year, "buzz"))
        try:
            for s in (_ds.assign_headline_storylines(prospects, year) or []):
                items.append({
                    "kind": "headline",
                    "title": str(s.get("title", "")),
                    "text": str(s.get("text", "")),
                    "prospect_id": (str(s.get("prospect_id"))
                                    if s.get("prospect_id") is not None else None),
                    "tags": list(s.get("tags", []) or []),
                })
        except Exception:
            pass
        try:
            month = _game_month(live)
            beats_month = month if 1 <= month <= 6 else 6
            for s in (_ds.season_beats(prospects, year, beats_month) or []):
                items.append({
                    "kind": "beat",
                    "title": str(s.get("title", "")),
                    "text": str(s.get("text", "")),
                    "prospect_id": (str(s.get("prospect_id"))
                                    if s.get("prospect_id") is not None else None),
                    "tags": list(s.get("tags", []) or []),
                })
        except Exception:
            pass
    finally:
        _random.setstate(state)

    # 4. Steal watch (read-only reimplementation of steal_retrospective's
    # filter: late-round picks with exploded potential). Never mutates
    # league state, so the real pipeline is untouched.
    try:
        _steal_grades = {"B+", "A-", "A", "A+"}
        found = []
        teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []
        for t in teams:
            pool = []
            for attr in ("roster", "prospects"):
                pool += _safe(lambda: list(getattr(t, attr, None) or []), []) or []
            for p in pool:
                try:
                    dround = int(getattr(p, "draft_round", 0) or 0)
                    if dround < 4:
                        continue
                    if int(getattr(p, "age", 99) or 99) > 26:
                        continue
                    grade = (getattr(p, "potential_grade", "") or "").strip()
                    if grade not in _steal_grades:
                        continue
                    if float(getattr(p, "draft_hype", 100) or 100) > 45:
                        continue
                    dyear = _safe(lambda: int(getattr(p, "drafted_year", 0) or 0), 0)
                    found.append((dround, p, dyear, grade))
                except Exception:
                    continue
        _grade_order = {"B+": 0, "A-": 1, "A": 2, "A+": 3}
        found.sort(key=lambda x: (-x[0], _grade_order.get(x[3], 0)), reverse=False)
        for dround, p, dyear, grade in found[:3]:
            name = _safe(lambda: getattr(p, "full_name", "?"), "?")
            when = "round %d of the %s draft" % (dround, dyear) if dyear else "round %d" % dround
            items.append({
                "kind": "steal",
                "title": "Steal Watch: %s" % name,
                "text": ("%s, taken in %s, has developed into a %s-potential "
                         "player — the Datsyuk story nobody saw coming."
                         % (name, when, grade)),
                "prospect_id": str(getattr(p, "id", "")),
                "tags": ["draft", "steal"],
            })
    except Exception:
        pass

    return jsonify({"items": items})


@bp.route("/api/draft/trade_feed")
def api_draft_trade_feed():
    """Draft-day trade feed: real deals from league.draft_day_deals
    (persisted through save/load), newest first."""
    import re
    live = _live()
    if live is None:
        return jsonify({"deals": []})
    gm = _safe(lambda: live.game_manager)
    league = _draft_league(live)
    if league is None:
        return jsonify({"deals": []})
    deals = _safe(lambda: list(getattr(league, "draft_day_deals", None) or []), []) or []

    # Match summaries to trade_history entries for the year badge.
    date_by_summary = {}
    try:
        for ct in (_safe(lambda: list(getattr(gm, "trade_history", None) or []), []) or []):
            s = _safe(lambda: str(getattr(ct, "summary", "") or ""), "")
            d = _safe(lambda: str(getattr(ct, "date", "") or ""), "")
            if s:
                date_by_summary.setdefault(s, d)
    except Exception:
        pass

    team_names = []
    for t in (_safe(lambda: list(getattr(league, "teams", None) or []), []) or []):
        n = _safe(lambda: str(getattr(t, "team_name", "") or ""), "")
        if n:
            team_names.append(n)

    out = []
    for raw in reversed(deals[-50:]):
        try:
            text = str(raw or "").strip()
            if not text:
                continue
            kind = "rumor" if text.upper().startswith("RUMOR") else "deal"
            text = re.sub(r"^(DRAFT TRADE|RUMOR)\s*:\s*", "", text, flags=re.I)
            year = None
            dd = date_by_summary.get("DRAFT TRADE: " + text) or date_by_summary.get(text)
            if dd:
                m = re.search(r"(\d{4})", dd)
                if m:
                    year = int(m.group(1))
            involved = sorted([n for n in team_names if n in text],
                              key=len, reverse=True)
            out.append({"text": text, "year": year, "teams": involved,
                        "kind": kind})
        except Exception:
            continue
    return jsonify({"deals": out})


@bp.route("/api/draft/grades")
def api_draft_grades():
    """Draft grades: persisted final grades from league.draft_grades_history
    (newest completed draft), or a live projected grade computed with the
    engine's own draft_grades() from picks made so far."""
    live = _live()
    if live is None:
        return jsonify({"source": "none", "year": None, "grades": []})
    league = _draft_league(live)
    if league is None:
        return jsonify({"source": "none", "year": None, "grades": []})
    import draft_night as _dn

    session = _draft_session(live)
    complete = _safe(lambda: bool(session.is_complete()), True) if session else True
    picks = _safe(lambda: list(getattr(session, "picks", None) or []), []) or []
    year = _draft_year_for(league, session)

    def _grade_entry(team, grade, ratio, detail):
        return {
            "name": team,
            "grade": grade,
            "color": _dn.grade_color(grade),
            "score": round(float(ratio), 3),
            "picks": detail or [],
        }

    # Live projection: draft is underway and picks have been made.
    if session is not None and not complete and picks:
        pidx = _prospect_index(league)
        slot_round = {}
        for s in (_safe(lambda: list(getattr(session, "slots", None) or []), []) or []):
            try:
                slot_round[int(s.get("overall", 0) or 0)] = int(s.get("round", 0) or 0)
            except Exception:
                continue
        picks_made = []
        detail = {}
        for p in picks:
            try:
                overall = int(p.get("overall", 0) or 0)
                team = str(p.get("team", "") or "")
                player = pidx.get(p.get("player_id"))
                if player is None or not team:
                    continue
                picks_made.append((team, overall, player))
                exp = _dn.pick_slot_value(overall)
                act = _dn.drafted_player_value(player)
                detail.setdefault(team, []).append({
                    "overall": overall,
                    "round": slot_round.get(overall) or ((overall - 1) // 32 + 1),
                    "player": _safe(lambda: getattr(player, "full_name", "?"), "?"),
                    "player_id": str(getattr(player, "id", "")),
                    "expected": exp,
                    "value": act,
                    "delta": act - exp,
                })
            except Exception:
                continue
        grades = _dn.draft_grades(picks_made)
        rows = [_grade_entry(t, g, r,
                            sorted(detail.get(t, []), key=lambda d: d["overall"]))
                for t, g, r in grades]
        return jsonify({
            "source": "live",
            "year": year or None,
            "note": "Projected — draft in progress. Grades update with every pick.",
            "grades": rows,
        })

    # Final: newest completed draft from the persisted history.
    hist = _safe(lambda: dict(getattr(league, "draft_grades_history", None) or {}), {}) or {}
    years = []
    for k in hist.keys():
        try:
            years.append(int(k))
        except (TypeError, ValueError):
            continue
    if years:
        y = max(years)
        rows = []
        for entry in (hist.get(str(y)) or []):
            try:
                t, g, r = entry[0], entry[1], float(entry[2])
                rows.append(_grade_entry(str(t), str(g), r, []))
            except Exception:
                continue
        return jsonify({"source": "final", "year": y, "grades": rows})
    return jsonify({"source": "none", "year": None, "grades": []})


# ======================================================================
# Batch D: draft-day incoming calls.
# Desktop parity (draft_day_trades.incoming_offer_for_user): when the
# user's club is on the clock in round 1, the most motivated AI club
# may call with a trade-up offer. Accept / Decline / Counter.
# The call is built with the desktop's own helpers (_round1_order,
# _draft_board, _trade_up_target, _build_trade_up_offer, ai_consider_trade)
# -- this module only adapts them to the web session's slot model.
# At most one call per pick; declining never re-rings for that slot.
# ======================================================================

def _ddt_session(live):
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    return _safe(lambda: getattr(league, "entry_draft_session", None))


def _ddt_pending(live):
    try:
        p = getattr(live, "_web_ddt_call", None)
        return p if isinstance(p, dict) else None
    except Exception:
        return None


def _ddt_store(live, call):
    try:
        live._web_ddt_call = call
    except Exception:
        pass


def _ddt_offered(live):
    return _safe(lambda: getattr(live, "_web_ddt_offered_pick", None))


def _ddt_mark_offered(live, overall):
    try:
        live._web_ddt_offered_pick = int(overall)
    except Exception:
        pass


def _ddt_declined(live):
    try:
        d = getattr(live, "_web_ddt_declined", None)
        if not isinstance(d, set):
            d = set()
            live._web_ddt_declined = d
        return d
    except Exception:
        return set()


def _ddt_serialize_asset(a):
    """Draft pick -> JSON. (Draft-day calls only ever move picks.)"""
    try:
        from game_classes import DraftPick
        is_pick = isinstance(a, DraftPick)
    except Exception:
        is_pick = False
    if not is_pick:
        return None
    try:
        import trade_engine as te
        label = te.asset_label(a)
    except Exception:
        label = (f"{getattr(a, 'year', '?')} "
                 f"round {getattr(a, 'round', '?')} pick")
    return {
        "id": str(_safe(lambda: getattr(a, "id", ""), "")),
        "kind": "pick",
        "label": str(label),
        "year": _safe(lambda: int(getattr(a, "year", 0) or 0), 0),
        "round": _safe(lambda: int(getattr(a, "round", 0) or 0), 0),
        "overall_pick": _safe(lambda: getattr(a, "overall_pick", None)),
    }


def _ddt_build_call(live):
    """Build the incoming call for the current pick, or None.

    Reuses draft_day_trades' offer-building + AI-verdict helpers with
    an adapter over the web session. Never raises."""
    try:
        import draft_day_trades as ddt
        import trade_engine as te
    except Exception:
        return None
    try:
        import random as _rng
    except Exception:
        return None
    session = _ddt_session(live)
    if session is None:
        return None
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    user_team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    year = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    cur_idx = _safe(lambda: int(getattr(session, "current_pick", 0) or 0), 0)
    overall = cur_idx + 1
    # Already rang / already declined for this slot.
    if _ddt_offered(live) == overall or overall in _ddt_declined(live):
        return None
    # Current slot must be round 1 and owned by the user.
    slots = _safe(lambda: list(getattr(session, "slots", None) or []),
                  []) or []
    cur_slot = next((s for s in slots
                     if int(s.get("overall", 0) or 0) == overall), None)
    if cur_slot is None or int(cur_slot.get("round", 0) or 0) != 1:
        return None
    uname = _safe(lambda: getattr(user_team, "team_name", ""), "")
    if str(cur_slot.get("owner", "") or "") != uname:
        return None
    _ddt_mark_offered(live, overall)
    if _rng.random() > 0.35:
        return None
    order = ddt._round1_order(league, year)
    board = ddt._draft_board(league)
    if not order or not board:
        return None
    try:
        ai_manager = _safe(lambda: getattr(live, "ai_manager", None))
    except Exception:
        ai_manager = None
    best = None
    for o2, t2, pk2 in order:
        try:
            if o2 <= overall or ddt._is_human(t2):
                continue
            pname = ddt._priority_name(ddt._priority_of(t2, ai_manager))
            tgt = ddt._trade_up_target(t2, o2, board, pname)
            if tgt is None:
                continue
            t_overall, prosp = tgt
            if t_overall != overall:
                continue
            mine = ddt._owned_picks(t2, year, 1)
            if not mine:
                continue
            offer = ddt._build_trade_up_offer(te, t2, mine[0], user_team,
                                              year)
            if offer is None:
                continue
            gives, gets = offer
            try:
                resp = te.ai_consider_trade(
                    user_team, list(gives), list(gets), user_team=t2)
            except Exception:
                continue
            if getattr(resp, "decision", "reject") == "reject":
                continue
            score = _rng.uniform(0, 1)
            if best is None or score > best[0]:
                best = (score, t2, gives, gets, prosp, resp)
        except Exception:
            continue
    if best is None:
        return None
    _s, caller, gives, gets, prosp, resp = best
    # Fold any AI counter into the terms before the user sees them
    # (desktop parity: the dialog shows exactly what accepting executes).
    if getattr(resp, "decision", "") == "counter":
        gives = list(gives) + list(getattr(resp, "want_added", None) or [])
        gets = list(gets) + list(getattr(resp, "will_add", None) or [])
    ser_gives = [a for a in (_ddt_serialize_asset(a) for a in gives) if a]
    ser_gets = [a for a in (_ddt_serialize_asset(a) for a in gets) if a]
    if not ser_gives or not ser_gets:
        return None
    try:
        why = ddt._call_why_lines(
            te, caller, prosp, board,
            ddt._priority_name(ddt._priority_of(caller, ai_manager)))
    except Exception:
        why = {}
    try:
        import scouting as _scmod
        tpot = _scmod.consensus_range(prosp)
    except Exception:
        tpot = "?"
    try:
        v_in = sum(te.asset_value(a) for a in gives)
        v_out = sum(te.asset_value(a) for a in gets)
        share = v_in / (v_in + v_out) if (v_in + v_out) > 0 else 0.5
    except Exception:
        share = 0.5
    vlabel = ("Value favors you" if share >= 0.55
              else "Value favors them" if share <= 0.45
              else "Roughly fair value")
    call = {
        "caller": _safe(lambda: getattr(caller, "team_name", "?"), "?"),
        "caller_id": str(_safe(lambda: getattr(caller, "id", ""), "")),
        "overall": overall,
        "year": year,
        "why_title": str(why.get("direction_short", "") or ""),
        "why_bullets": [str(b) for b in (why.get("bullets", None) or [])],
        "target": {
            "name": _safe(lambda: getattr(prosp, "full_name", "?"), "?"),
            "position": ddt._pos_of(prosp),
            "age": _safe(lambda: int(getattr(prosp, "age", 0) or 0), 0),
            "potential": str(tpot),
            "potential_grade": str(
                _safe(lambda: getattr(prosp, "potential_grade", "?"), "?")),
        },
        "you_send": ser_gets,     # gets: the user's pick going out
        "you_receive": ser_gives,  # gives: the caller's assets coming in
        "value_label": vlabel,
        "give_ids": [a["id"] for a in ser_gives if a.get("id")],
        "get_ids": [a["id"] for a in ser_gets if a.get("id")],
    }
    _ddt_store(live, call)
    return call


@bp.route("/api/draft/incoming_call")
def api_draft_incoming_call():
    """Poll for an incoming AI trade call while on the clock (round 1).
    Returns {"call": ...} or {"call": null}. At most one per pick."""
    live = _live()
    if live is None:
        return jsonify({"call": None})
    call = _ddt_pending(live)
    if call is None:
        call = _ddt_build_call(live)
    return jsonify({"call": call})


@bp.route("/api/draft/incoming_call/answer", methods=["POST"])
def api_draft_incoming_call_answer():
    """Answer the parked call: {"action": "accept"|"decline"|"counter"}.

    accept -> enqueue "draft_day_trade_accept" (main thread executes the
    real engine trade + pick-list sync + session order update).
    decline -> never re-rings for this slot (desktop parity).
    counter -> deeplink payload for the trade builder, call stays parked.
    """
    from flask import request as _rq
    data = _rq.get_json(force=True, silent=True) or {}
    action = str(data.get("action") or "").lower()
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    call = _ddt_pending(live)
    if call is None:
        return jsonify({"ok": False, "error": "no incoming call"}), 409
    if action == "decline":
        _ddt_declined(live).add(int(call.get("overall", 0) or 0))
        _ddt_store(live, None)
        return jsonify({"ok": True, "action": "decline"})
    if action == "counter":
        # Deeplink into the trade center: their offer as the starting
        # point, caller as partner.
        return jsonify({
            "ok": True, "action": "counter",
            "deeplink": {
                "page": "/trades",
                "target_team_id": call.get("caller"),
                "want_pids": [], "want_picks": call.get("give_ids") or [],
                "give_pids": [], "give_picks": call.get("get_ids") or [],
                "note": (f"Counter {call.get('caller')}: adjust their "
                         f"trade-up offer for #{call.get('overall')}."),
            },
        })
    if action == "accept":
        from web_ui.bridge import enqueue_command
        ok = enqueue_command("draft_day_trade_accept",
                             caller=str(call.get("caller") or ""),
                             overall=int(call.get("overall", 0) or 0))
        return jsonify({"ok": bool(ok), "action": "accept",
                        "queued": "draft_day_trade_accept"})
    return jsonify({"ok": False, "error": "unknown action"}), 400


@bp.route("/api/draft/incoming_call/result")
def api_draft_incoming_call_result():
    """Poll the outcome of an accepted call (stashed by the main-thread
    op)."""
    live = _live()
    r = _safe(lambda: getattr(live, "_web_draft_call_result", None)) \
        if live is not None else None
    if not r:
        return jsonify({"pending": True})
    return jsonify({"pending": False, "result": {
        "ok": bool(r.get("ok")),
        "summary": str(r.get("summary") or ""),
    }})
