"""Offer Sheets screen: sign a rival club's unsigned RFA.

Web port of OfferSheetWindow (offer_sheet_ui.py, main.py:21033
open_offer_sheet_window). One rulebook: the same rfa_system engine the
desktop July pass uses (is_rfa, offer_sheet_compensation,
own_pick_available, player_decision.player_accepts_offer_sheet,
ai_match_decision, apply_offer_sheet_matched, execute_offer_sheet).
Reads are plain GETs; presenting a sheet enqueues the
"present_offer_sheet" command (bridge._execute_command runs the real
engine on the main thread).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player, enqueue_command, _player_ovr

bp = Blueprint("offer_sheets", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _gm(live):
    return _safe(lambda: live.game_manager)


def _user_team(live):
    return _safe(lambda: _gm(live).user_team) or _safe(lambda: live.user_team)


def _league(live):
    return _safe(lambda: _gm(live).league) or _safe(lambda: live.league)


def _rfa():
    try:
        import rfa_system as _rfa
        return _rfa
    except Exception:
        return None


def _tier_label(ovr):
    """Talent tier (never the numeric overall is the desktop rule for this
    screen; the web roster shows numbers, so expose both)."""
    try:
        from attribute_composites import talent_tier
        return talent_tier(int(ovr))
    except Exception:
        return "Decent"


def _targets(live):
    """Unsigned RFAs on rival NHL clubs (arbitration filers excluded --
    filing blocks offer sheets, same as the desktop and the July pass)."""
    rfa = _rfa()
    if rfa is None:
        return []
    league = _league(live)
    user = _user_team(live)
    user_names = {str(_safe(lambda: getattr(user, "team_name", "")) or "")}
    out = []
    teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []
    for team in teams:
        if team is user:
            continue
        if str(_safe(lambda: getattr(team, "team_name", "")) or "") in user_names:
            continue
        if str(_safe(lambda: getattr(team, "league_name", "")) or "") != "National Hockey League":
            continue
        for p in list(_safe(lambda: getattr(team, "roster", None) or [], []) or []):
            try:
                if not rfa.is_rfa(p):
                    continue
                if bool(getattr(p, "arbitration_filed", False)):
                    continue
                if bool(getattr(p, "offer_sheet_pending", False)):
                    continue
                market = int(rfa.market_value_estimate(p) or 0)
                out.append((p, team, market))
            except Exception:
                continue
    out.sort(key=lambda t: t[2], reverse=True)
    return out


def _target_row(p, team, market):
    d = to_web_player(p)
    d["position"] = _safe(
        lambda: getattr(getattr(p, "primary_position", None), "value",
                        str(getattr(p, "primary_position", "?"))), "?")
    d["team_name"] = _safe(lambda: getattr(team, "team_name", "?"), "?")
    d["market"] = market
    d["tier"] = _tier_label(_player_ovr(p))
    d["id"] = _safe(lambda: str(getattr(p, "id", id(p))))
    return d


def _compensation_pick_status(user_team, year, picks):
    """Port of compensation_pick_status (offer_sheet_ui.py): which required
    compensation picks the user can actually furnish (own picks, no
    double-count). Returns (lines, missing_rounds)."""
    rfa = _rfa()
    lines, missing, used = [], [], set()
    if rfa is None:
        return lines, picks
    for rnd in picks:
        pk, y = None, year
        for yy in range(year, year + 7):
            cand = _safe(lambda: rfa.own_pick_available(user_team, yy, rnd))
            if cand is not None and id(cand) not in used:
                pk, y = cand, yy
                break
        if pk is None:
            missing.append(rnd)
            lines.append({"ok": False,
                          "text": f"round {rnd}: not yours to trade ({year}-{year + 6})"})
        else:
            used.add(id(pk))
            lines.append({"ok": True,
                          "text": f"{y} round {rnd} (your own pick)"})
    return lines, missing


def _cap_space(live, team):
    try:
        from salary_cap_system import cap_breakdown
        return int(_safe(lambda: cap_breakdown(team).get("space", 0), 0) or 0)
    except Exception:
        return 0


def _window_check(live):
    try:
        import transaction_windows as _tw
        d = _safe(lambda: getattr(live, "current_date", None))
        ok, why = _tw.check_window("offer_sheet", d)
        return bool(ok), (why or "")
    except Exception:
        return True, ""


@bp.route("/offer_sheets")
def offer_sheets_page():
    return render_template("offer_sheets.html")


@bp.route("/api/offer_sheets/targets")
def api_offer_sheets_targets():
    live = _live()
    if live is None:
        return jsonify({"targets": [], "window": {"ok": False, "reason": "no live game"}})
    targets = [_target_row(p, t, m) for (p, t, m) in _targets(live)]
    user = _user_team(live)
    win_ok, win_msg = _window_check(live)
    return jsonify({
        "targets": targets,
        "count": len(targets),
        "window": {"ok": win_ok, "reason": win_msg},
        "cap_space": _cap_space(live, user),
        "roster_size": _safe(lambda: len(list(getattr(user, "roster", None) or [])), 0),
    })


@bp.route("/api/offer_sheets/preview")
def api_offer_sheets_preview():
    """Live preview for a target + terms: compensation, checks, interest
    read. Mirrors OfferSheetWindow._update_preview."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    pid = request.args.get("player_id")
    try:
        aav = int(float(request.args.get("aav") or 0))
        years = int(request.args.get("years") or 4)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "aav/years invalid"}), 400
    years = max(1, min(5, years))
    if aav <= 0:
        return jsonify({"ok": False, "error": "aav must be positive"}), 400

    hit = None
    for (p, team, market) in _targets(live):
        if str(_safe(lambda: getattr(p, "id", ""), "")) == str(pid):
            hit = (p, team, market)
            break
    if hit is None:
        return jsonify({"ok": False, "error": "target not available"}), 404
    p, original_team, market = hit
    user = _user_team(live)
    league = _league(live)

    rfa = _rfa()
    label, picks = _safe(lambda: rfa.offer_sheet_compensation(aav),
                         ("No compensation", [])) if rfa else ("?", [])
    year = int(_safe(lambda: getattr(league, "season_year", 2026), 2026) or 2026) + 1
    comp_lines, missing = _compensation_pick_status(user, year, picks)

    checks = []
    space = _cap_space(live, user)
    checks.append({"ok": space >= aav,
                   "text": f"Cap space ${_fmt(space)} vs ${_fmt(aav)}/yr"})
    n_roster = _safe(lambda: len(list(getattr(user, "roster", None) or [])), 0)
    checks.append({"ok": n_roster < 23, "text": f"Roster {n_roster}/23"})
    if missing:
        checks.append({"ok": False, "text": "Missing own picks — sheet can't be signed"})
    win_ok, win_msg = _window_check(live)
    checks.append({"ok": win_ok,
                   "text": "Offer-sheet window open" if win_ok
                   else f"Window closed — {win_msg}"})
    all_ok = all(c["ok"] for c in checks)

    # Qualitative interest read (no roll revealed) -- desktop rule.
    interest = ""
    try:
        import player_decision as _pd
        appeal, _reasons = _pd.contract_appeal(
            p, user, aav, years, current_team=original_team,
            league=league, app=live, is_offer_sheet=True)
        if appeal >= 0.7:
            interest = "His camp is listening closely."
        elif appeal >= 0.52:
            interest = "His camp is lukewarm — money talks."
        elif appeal >= 0.35:
            interest = "His camp sounds cool on the idea."
        else:
            interest = "His camp wants nothing to do with this."
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "compensation": {"label": label, "lines": comp_lines,
                         "missing_rounds": missing},
        "checks": checks,
        "valid": all_ok,
        "interest": interest,
        "market": market,
    })


def _fmt(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return "?"


@bp.route("/api/offer_sheets/present", methods=["POST"])
def api_offer_sheets_present():
    """Queue presenting an offer sheet. Revalidates everything the desktop
    validates; the main-thread op runs the player/AI decisions + the real
    engine mutation."""
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    try:
        aav = int(data.get("aav"))
        years = int(data.get("years", 4))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "aav and years must be integers"}), 400
    years = max(1, min(5, years))
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    hit = None
    for (p, team, market) in _targets(live):
        if str(_safe(lambda: getattr(p, "id", ""), "")) == str(pid):
            hit = (p, team, market)
            break
    if hit is None:
        return jsonify({"ok": False, "error": "target not available"}), 404
    p, original_team, _market = hit
    user = _user_team(live)
    league = _league(live)

    rfa = _rfa()
    label, picks = _safe(lambda: rfa.offer_sheet_compensation(aav),
                         ("No compensation", [])) if rfa else ("?", [])
    year = int(_safe(lambda: getattr(league, "season_year", 2026), 2026) or 2026) + 1
    _lines, missing = _compensation_pick_status(user, year, picks)
    if missing:
        return jsonify({"ok": False,
                        "error": f"You don't hold your own picks for the required "
                                 f"compensation ({label})."}), 422
    space = _cap_space(live, user)
    if space < aav:
        return jsonify({"ok": False,
                        "error": f"Not enough cap space: {_fmt(space)} available vs "
                                 f"{_fmt(aav)}/yr."}), 422
    n_roster = _safe(lambda: len(list(getattr(user, "roster", None) or [])), 0)
    if n_roster >= 23:
        return jsonify({"ok": False,
                        "error": "Your NHL roster is full (23/23)."}), 422
    win_ok, win_msg = _window_check(live)
    if not win_ok:
        return jsonify({"ok": False, "error": win_msg}), 422

    queued = enqueue_command("present_offer_sheet", player_id=str(pid),
                             aav=aav, years=years)
    return jsonify({"ok": bool(queued), "queued": "present_offer_sheet"})


# ------------------------------------------------------------------
# Main-thread command handler (bridge delegates here)
# ------------------------------------------------------------------

def _store_result(app, ok, summary, **kw):
    try:
        app._web_offer_sheet_result = {
            "marker": "present_offer_sheet",
            "ok": bool(ok),
            "summary": str(summary or ""),
            **kw,
        }
    except Exception:
        pass


def _find_rfa_target(app, pid):
    """Find (player, original_team) among rival NHL rosters. Never raises."""
    rfa = _rfa()
    if rfa is None:
        return None, None
    try:
        league = _league(app)
        user = _user_team(app)
        teams = list(getattr(league, "teams", None) or [])
        for team in teams:
            if team is user:
                continue
            if str(getattr(team, "league_name", "") or "") != "National Hockey League":
                continue
            for p in list(getattr(team, "roster", None) or []):
                if str(getattr(p, "id", "")) != str(pid):
                    continue
                try:
                    if not rfa.is_rfa(p):
                        return None, None
                    if bool(getattr(p, "arbitration_filed", False)):
                        return None, None
                    if bool(getattr(p, "offer_sheet_pending", False)):
                        return None, None
                except Exception:
                    return None, None
                return p, team
    except Exception:
        pass
    return None, None


def handle_present_offer_sheet_command(app, cmd):
    """Run the desktop OfferSheetWindow._present_offer_sheet flow on the
    main thread: revalidate window/picks/cap/roster, then the real engine
    (player_accepts_offer_sheet -> ai_match_decision ->
    apply_offer_sheet_matched / execute_offer_sheet). Stashes the outcome
    on app._web_offer_sheet_result for the poll endpoint. Never raises."""
    try:
        pid = str(cmd.get("player_id", ""))
        aav = int(cmd.get("aav", 0))
        years = int(cmd.get("years", 4))
    except (TypeError, ValueError):
        _store_result(app, False, "Invalid terms.")
        return
    years = max(1, min(5, years))
    try:
        rfa = _rfa()
        if rfa is None:
            _store_result(app, False, "Offer-sheet engine unavailable.")
            return
        league = _league(app)
        user = _user_team(app)
        player, original_team = _find_rfa_target(app, pid)
        pname = _safe(lambda: getattr(player, "full_name", "Unknown"), "Unknown") \
            if player is not None else "Unknown"
        if player is None or original_team is None or user is None:
            _store_result(app, False,
                          f"{pname} is no longer an available offer-sheet target.")
            return
        tname = _safe(lambda: getattr(original_team, "team_name", "?"), "?")
        # 1. Window gate (same rulebook as the desktop + engine).
        try:
            import transaction_windows as _tw
            ok, why = _tw.check_window("offer_sheet",
                                       _safe(lambda: getattr(app, "current_date", None)))
            if not ok:
                _store_result(app, False, str(why or "Offer-sheet window closed."))
                return
        except Exception:
            pass
        # 2. Compensation + own picks.
        label, picks = rfa.offer_sheet_compensation(aav)
        year = int(_safe(lambda: getattr(league, "season_year", 2026), 2026) or 2026) + 1
        _lines, missing = _compensation_pick_status(user, year, picks)
        if missing:
            _store_result(app, False,
                          f"You don't hold your own picks for the required "
                          f"compensation ({label}). Without them the sheet can't "
                          f"be signed.")
            return
        # 3. Cap + roster room.
        space = _cap_space(app, user)
        if space < aav:
            _store_result(app, False,
                          f"Not enough cap space: {_fmt(space)} available vs "
                          f"{_fmt(aav)}/yr.")
            return
        n_roster = _safe(lambda: len(list(getattr(user, "roster", None) or [])), 0)
        if n_roster >= 23:
            _store_result(app, False, "Your NHL roster is full (23/23).")
            return
        # 4. The player must agree to sign (real engine).
        try:
            import player_decision as _pd
            willing, _appeal, reasons = _pd.player_accepts_offer_sheet(
                player, user, aav, years, original_team,
                league=league, app=app,
                rng=_safe(lambda: getattr(app, "_rng", None)))
        except Exception:
            willing, reasons = True, []
        if not willing:
            why_txt = f" {reasons[0]}" if reasons else ""
            try:
                _news = getattr(app, "add_news", None)
                if callable(_news):
                    _news(f"{pname} rejects your offer sheet "
                          f"({_fmt(aav)}/yr x {years}y).{why_txt}")
            except Exception:
                pass
            _store_result(app, False, f"{pname} won't sign.{why_txt}")
            return
        # 5. The original club matches or declines -- the same
        # ai_match_decision the July pass uses. One rulebook.
        if rfa.ai_match_decision(original_team, player, aav, label):
            mres = rfa.apply_offer_sheet_matched(
                league, user, original_team, player, aav, years, app=app)
            story = mres.get("story", "")
            _store_result(app, True, f"{tname} matched. He stays.",
                          matched=True, story=story)
        else:
            res = rfa.execute_offer_sheet(
                league, user, original_team, player, aav, years,
                app=app, rng=_safe(lambda: getattr(app, "_rng", None)))
            if not res.get("ok"):
                _store_result(app, False,
                              f"The sheet failed: {res.get('reason', 'unknown')}.")
                return
            _store_result(app, True,
                          f"He's yours! {label} goes to {tname}.",
                          matched=False, story=res.get("story", ""))
    except Exception as e:
        _store_result(app, False, f"Offer sheet failed: {e}")


@bp.route("/api/offer_sheets/result")
def api_offer_sheets_result():
    """Poll the last present-offer-sheet outcome (stashed by the
    main-thread handler)."""
    live = _live()
    result = _safe(lambda: getattr(live, "_web_offer_sheet_result", None)) \
        if live else None
    return jsonify({"result": result})
