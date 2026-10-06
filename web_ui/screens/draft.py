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
