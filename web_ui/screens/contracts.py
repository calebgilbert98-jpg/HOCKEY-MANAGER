"""Contracts screen: roster contracts sorted by cap hit, with extensions.

v1: table of user-team roster contracts showing player, position, cap
hit, term remaining and an expiring flag. "Extend" enqueues the
"extend_contract" command (the parent must wire that op into
bridge._execute_command / the game's extension path).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("contracts", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _web_position(p):
    """Best-effort position label. Never raises."""
    try:
        from game_classes import position_label
        label = _safe(lambda: position_label(p))
        if label and label != "?":
            return label
    except Exception:
        pass
    return _safe(lambda: str(getattr(p, "primary_position", "?") or "?"), "?")


def _to_web_contract(p):
    d = to_web_player(p)
    d["position"] = _web_position(p)
    contract = _safe(lambda: getattr(p, "contract", None))
    salary = _safe(lambda: int(getattr(contract, "salary", 0) or 0), 0)
    years = _safe(lambda: getattr(contract, "years_remaining", None))
    if years is None:
        years = _safe(lambda: getattr(contract, "term", None))
    years = _safe(lambda: int(years), 0)
    d["salary"] = salary
    d["cap_hit"] = salary
    d["years_remaining"] = years
    d["expiring"] = bool(years <= 1)
    # clause flags for the tooltip line
    d["no_trade"] = _safe(lambda: bool(getattr(contract, "no_trade_clause", False)), False)
    d["no_movement"] = _safe(lambda: bool(getattr(contract, "no_movement_clause", False)), False)
    d["two_way"] = _safe(lambda: bool(getattr(contract, "two_way", False)), False)
    return d


@bp.route("/contracts")
def contracts_page():
    return render_template("contracts.html")


@bp.route("/api/contracts")
def api_contracts():
    live = _live()
    if live is None:
        return jsonify({"contracts": [], "summary": {}})
    gm = _safe(lambda: live.game_manager)
    from flask import request as _rq
    only_expiring = (_rq.args.get("tab") or "all") == "expiring"
    team = _safe(lambda: getattr(gm, "user_team", None)) or \
           _safe(lambda: getattr(live, "user_team", None))
    roster = []
    for lst in ("roster", "ahl_roster"):
        roster.extend(_safe(lambda: list(getattr(team, lst, None) or []), []) or [])
    rows = []
    for p in roster:
        try:
            d = _to_web_contract(p)
            if only_expiring and not d.get("expiring"):
                continue
            rows.append(d)
        except Exception:
            continue
    try:
        rows.sort(key=lambda d: d.get("cap_hit", 0), reverse=True)
    except Exception:
        pass
    total = _safe(lambda: sum(r.get("cap_hit", 0) for r in rows), 0)
    cap = _safe(lambda: int(getattr(live.game_manager.league, "salary_cap", 0) or 0), 0)
    return jsonify({
        "contracts": rows,
        "summary": {
            "total_cap_hit": total,
            "cap_ceiling": cap,
            "player_count": len(rows),
        },
    })


# ------------------------------------------------------------------
# v2 contract flow: extension terms, cap preview, validated re-signs
# ------------------------------------------------------------------

@bp.route("/api/contracts/result")
def api_contracts_result():
    """Last queued sign/extend outcome (stashed by the Tk-thread handler)."""
    live = _live()
    result = _safe(lambda: getattr(live, "_web_contract_result", None)) \
        if live else None
    return jsonify({"result": result})

def _find_roster_player(live, pid):
    """Roster player by id. Never raises."""
    try:
        gm = _safe(lambda: live.game_manager)
        _ut = _safe(lambda: getattr(gm, "user_team", None)) or \
              _safe(lambda: getattr(live, "user_team", None))
        roster = _safe(lambda: list(getattr(_ut, "roster", None)
                                    or []), []) or []
        for p in roster:
            if str(_safe(lambda: getattr(p, "id", id(p)), "")) == str(pid):
                return p
    except Exception:
        pass
    return None


def _live_cap(live):
    try:
        c = int(live.get_live_cap())
        if c > 0:
            return c
    except Exception:
        pass
    return 104_000_000


def _term_bounds(live, extension):
    """(min_years, max_years): new CBA = 7 to re-sign, 6 external."""
    try:
        from salary_cap_system import max_contract_term
        return 1, int(max_contract_term(bool(extension)))
    except Exception:
        return 1, 7 if extension else 6


def _salary_bounds(live):
    """(min_salary, max_salary) for a new deal: season-aware league
    minimum, 20%-of-live-cap maximum."""
    cap = _live_cap(live)
    try:
        from salary_cap_system import league_minimum_salary
        sy = _safe(lambda: getattr(getattr(live, "game_manager", None),
                                  "league", None).season_year)
        min_sal = int(league_minimum_salary(sy))
    except Exception:
        min_sal = 775_000
    return min_sal, int(0.20 * cap)


def _cap_state(live, offer_salary=0, extension=False, current_hit=0):
    """Current + projected cap via salary_cap_system.total_cap_charge.
    Extensions replace the player's existing hit instead of stacking.
    Never raises."""
    out = {"live_cap": 0, "current_charge": 0, "current_space": 0,
           "projected_charge": 0, "space_after": 0, "fits": False}
    try:
        from salary_cap_system import total_cap_charge
        cap = _live_cap(live)
        gm = _safe(lambda: live.game_manager)
        team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
        charge = int(_safe(lambda: total_cap_charge(team), 0))
        proj = charge + int(offer_salary or 0)
        if extension:
            proj -= int(current_hit or 0)
        out.update(live_cap=cap, current_charge=charge,
                   current_space=cap - charge, projected_charge=proj,
                   space_after=cap - proj, fits=(cap - proj) >= 0)
    except Exception:
        pass
    return out


def _validate_extension(live, p, salary, years):
    """Server-side validation through the game's shared gate
    (HockeyManagerGUI._validate_contract_terms with extension=True).
    Returns (ok, message)."""
    try:
        ok, msg = live._validate_contract_terms(p, int(salary), int(years),
                                                extension=True)
        return bool(ok), (msg or "")
    except Exception:
        return False, "Could not validate contract terms."


def _extension_window(live, p):
    """Extensions only in the final year of a deal
    (transaction_windows.check_window). Returns (ok, reason)."""
    try:
        import transaction_windows as _tw
        d = _safe(lambda: getattr(live, "current_date", None))
        ok, why = _tw.check_window("extension", d, ctx={"player": p})
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _extension_estimate(p, live_cap):
    """AAV the player would likely accept, replicating the game's own
    market-value curve (ContractExtensionsView.calculate_market_value,
    main.py): cap-relative base (ovr x $100k), age / position /
    potential modifiers, performance bonus. The desktop flow accepts
    90-120% of the player's value (person.negotiate_contract); return
    the band too."""
    try:
        from salary_cap_system import DEFAULT_CAP
    except Exception:
        DEFAULT_CAP = 104_000_000
    ovr = _safe(lambda: float(p.overall_rating()), 75.0) or 75.0
    age = _safe(lambda: int(getattr(p, "age", 27) or 27), 27)
    base = ovr * 100_000 * (live_cap / DEFAULT_CAP)
    age_mod = 1.2 if 23 <= age <= 29 else (
        max(0.5, 1.0 - ((age - 30) * 0.05)) if age >= 30 else 1.0)
    pos = getattr(p, "primary_position", "")
    pos_name = getattr(pos, "value", str(pos))
    pos_mod = 1.15 if pos_name == "C" else (
        1.1 if pos_name in ("LD", "RD") else 1.0)
    pot_mod = 1.0
    if age <= 25:
        pot_mod = {"A": 1.5, "B": 1.3, "C": 1.1, "D": 1.0, "F": 0.9}.get(
            _safe(lambda: getattr(p, "potential_grade", "C"), "C"), 1.0)
    perf = 0
    try:
        perf = int(p.stats.goals) * 50_000 + int(p.stats.assists) * 30_000
    except Exception:
        pass
    estimate = max(750_000, int(base * age_mod * pos_mod * pot_mod) + perf)
    # Desktop acceptance band: 90-120% of value (negotiate_contract).
    try:
        value = getattr(p, "value",
                        p.overall_rating() * 100_000)
        value = float(value or 0) or float(ovr * 100_000)
    except Exception:
        value = float(ovr * 100_000)
    return {
        "aav_estimate": estimate,
        "accept_low": int(value * 0.9),
        "accept_high": int(value * 1.2),
    }


@bp.route("/api/contracts/extension_terms")
def api_contracts_extension_terms():
    """Current contract + reasonable extension ranges (years, AAV) +
    cap preview. Optional query params years / aav preview exact terms."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    pid = request.args.get("player_id")
    p = _find_roster_player(live, pid)
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    years_min, years_max = _term_bounds(live, extension=True)
    min_sal, max_sal = _salary_bounds(live)
    cur = _to_web_contract(p)
    est = _extension_estimate(p, _live_cap(live))
    try:
        years = int(request.args.get("years") or 0)
    except (TypeError, ValueError):
        years = 0
    try:
        aav = int(float(request.args.get("aav") or 0))
    except (TypeError, ValueError):
        aav = 0
    if not years:
        years = min(years_max, 5 if _safe(lambda: int(getattr(p, "age", 27) or 27), 27) < 33 else 3)
    if not aav:
        aav = est["aav_estimate"]
    win_ok, win_msg = _extension_window(live, p)
    valid, valid_msg = _validate_extension(live, p, aav, years)
    return jsonify({
        "ok": True,
        "player": cur,
        "years_min": years_min,
        "years_max": years_max,
        "min_salary": min_sal,
        "max_salary": max_sal,
        "aav_estimate": est["aav_estimate"],
        "accept_band": {"low": est["accept_low"], "high": est["accept_high"]},
        "preview": {
            "years": years, "aav": aav,
            **_cap_state(live, offer_salary=aav, extension=True,
                         current_hit=cur.get("salary", 0)),
        },
        "window": {"ok": win_ok, "reason": win_msg},
        "valid": valid and win_ok,
        "valid_reason": valid_msg or win_msg,
        "note": ("Extensions apply instantly (no UFA consideration "
                 "period) when the player accepts."),
    })


@bp.route("/api/contracts/extend_real", methods=["POST"])
def api_contracts_extend_real():
    """Queue a real contract extension (years + AAV). Optional
    "clause" (none|nmc|ntc|mntc), "clause_list_size" and
    "signing_bonus" ride the payload: staged like the desktop
    submit_offer (offered_clause_kind / offered_clause_list_size) so
    the clause is priced by trade_engine and lands on the deal via
    apply_clause_to_contract. Validated twice: here through the game's
    _validate_contract_terms + the extension window, and again on the
    main thread before HockeyManagerGUI.handle_contract_offer
    (extension=True) runs."""
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    extras, err = _offer_extras(data)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    try:
        years = int(data.get("years"))
        aav = int(data.get("aav"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "years and aav must be integers"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    p = _find_roster_player(live, pid)
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    ok, msg = _validate_extension(live, p, aav, years)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    ok, msg = _extension_window(live, p)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    if extras["clause"] != "none":
        try:
            import trade_engine as _te
            if not _te.clause_eligible(p):
                return jsonify({"ok": False, "error":
                    "Trade protection isn't available for this player "
                    "(27+ or 7 pro seasons required)."}), 422
        except Exception:
            pass
    queued = enqueue_command("extend_contract_real",
                             player_id=str(pid), years=years, aav=aav,
                             clause=extras["clause"],
                             clause_list_size=extras["clause_list_size"],
                             signing_bonus=extras["signing_bonus"])
    return jsonify({"ok": bool(queued), "queued": "extend_contract_real",
                    "clause": extras["clause"],
                    "signing_bonus": extras["signing_bonus"]})


# ------------------------------------------------------------------
# v3 multi-day negotiation: the agent's counter arrives as an inbox
# message (action_type="contract_counter", main.py:22421). The web
# mirrors it into app._web_negotiations so an in-page modal can show
# the offer thread and let the user Accept / Counter / Walk away
# without touching the desktop inbox window. All state mutations run
# on the main thread via bridge command ops; every call is
# _safe-wrapped and uses real game methods only.
# ------------------------------------------------------------------

_NEG_STATUSES = ("awaiting_agent", "countered", "accepted", "refused",
                 "walked")


def _negotiations(app):
    """Server-side negotiation map on the app (mock-safe). Never raises."""
    try:
        negs = getattr(app, "_web_negotiations", None)
        if not isinstance(negs, dict):
            negs = {}
            app._web_negotiations = negs
        return negs
    except Exception:
        return {}


def _pending_counter_message(app, pid):
    """Latest unanswered contract_counter inbox message for a player
    (messages append chronologically, so last match wins). Never raises."""
    try:
        inbox = getattr(getattr(app, "user_team", None), "inbox", None)
        msgs = list(getattr(inbox, "messages", None) or [])
        pid_s = str(pid)
        best = None
        for m in msgs:
            try:
                if getattr(m, "action_type", "") != "contract_counter":
                    continue
                if getattr(m, "action_done", False):
                    continue
                data = getattr(m, "action_data", None) or {}
                if str(data.get("player_id", "")) != pid_s:
                    continue
                best = m
            except Exception:
                continue
        return best
    except Exception:
        return None


def _find_neg_person(app, pid, kind):
    """Player by id: roster for extensions, free-agent pool for signings.
    Never raises."""
    try:
        if kind == "extend":
            pool = list(getattr(getattr(app, "user_team", None),
                                "roster", None) or [])
        else:
            league = getattr(getattr(app, "game_manager", None),
                             "league", None)
            pool = list(getattr(league, "free_agents", None) or [])
        for p in pool:
            if str(_safe(lambda: getattr(p, "id", id(p)), "")) == str(pid):
                return p
    except Exception:
        pass
    return None


def _neg_kind_for(app, pid):
    """sign vs extend for a player: existing negotiation state wins,
    else derive from where the player lives. Never raises."""
    try:
        st = _negotiations(app).get(str(pid))
        if st and st.get("kind") in ("sign", "extend"):
            return st["kind"]
    except Exception:
        pass
    try:
        roster = list(getattr(getattr(app, "user_team", None),
                              "roster", None) or [])
        for p in roster:
            if str(_safe(lambda: getattr(p, "id", id(p)), "")) == str(pid):
                return "extend"
    except Exception:
        pass
    return "sign"


def _apply_offer_verdict(app, st, result):
    """Map handle_contract_offer's return onto the negotiation state:
    True -> accepted; "consideration" -> awaiting_agent (the UFA bid
    period); False -> countered when a fresh contract_counter inbox
    message exists, refused otherwise."""
    if result is True:
        st["status"] = "accepted"
        return
    if result == "consideration":
        st["status"] = "awaiting_agent"
        st["note"] = ("Qualifying offer: the player fields bids from every "
                      "club for 3-7 days before deciding.")
        return
    counter = _pending_counter_message(app, st.get("player_id"))
    if counter is not None:
        data = getattr(counter, "action_data", None) or {}
        st["agent_ask"] = _safe(lambda: int(data.get("asking_price", 0)
                                            or 0), 0)
        st["counter_terms"] = {
            "years": _safe(lambda: int(data.get("years", 1) or 1), 1),
            "aav": _safe(lambda: int(data.get("asking_price", 0) or 0), 0),
        }
        st["status"] = "countered"
    else:
        st["status"] = "refused"


def handle_offer_command(app, pid, player, kind, years, aav):
    """Bridge hook for sign/extend ops. Stages the offer (already done by
    the caller), runs the real HockeyManagerGUI.handle_contract_offer
    (main.py:21978, notify="inbox"), and mirrors the verdict into
    app._web_negotiations. Never raises."""
    try:
        pid_s = str(pid)
        negs = _negotiations(app)
        st = negs.get(pid_s) or {}
        name = _safe(lambda: getattr(player, "full_name", "?"), "?")
        st.update(
            player_id=pid_s,
            player_name=st.get("player_name") or name,
            kind=kind,
            your_offers=list(st.get("your_offers") or []) + [
                {"years": int(years), "aav": int(aav)}],
            agent_ask=st.get("agent_ask"),
            counter_terms=st.get("counter_terms"),
            status="awaiting_agent",
            note="",
        )
        negs[pid_s] = st
    except Exception:
        return
    try:
        result = app.handle_contract_offer(
            player, extension=(kind == "extend"), notify="inbox")
    except Exception:
        return
    _safe(lambda: _apply_offer_verdict(app, st, result))


def handle_negotiation_command(app, cmd):
    """Dispatch the three v3 negotiation ops (called from thin bridge.py
    elif lines). All _safe-wrapped, real game methods only. Returns True
    when the op was handled."""
    op = cmd.get("op")
    try:
        if op == "negotiate_counter":
            return _negotiate_counter(app, cmd)
        if op == "negotiate_accept":
            return _negotiate_accept(app, cmd)
        if op == "negotiate_walk":
            return _negotiate_walk(app, cmd)
    except Exception:
        pass
    return False


def _negotiate_counter(app, cmd):
    """New offer into an open negotiation: desktop 'New Offer' semantics
    (inbox_window._on_contract_counter_new_offer): the pending counter is
    answered by the fresh offer, which runs the same real offer path and
    re-stashes the new verdict."""
    pid = cmd.get("player_id")
    if not pid:
        return True
    pid_s = str(pid)
    try:
        years = int(cmd.get("years", 0))
    except (TypeError, ValueError):
        years = 0
    try:
        aav = int(cmd.get("aav", 0))
    except (TypeError, ValueError):
        aav = 0
    try:
        kind = _neg_kind_for(app, pid_s)
        extension = (kind == "extend")
        player = _find_neg_person(app, pid_s, kind)
        if player is None or years < 1 or aav <= 0:
            return True
        # Re-validate through the game's own gate (the desktop counter
        # path gates accept too: main.py:22456).
        ok, reason = _safe(
            lambda: app._validate_contract_terms(player, aav, years,
                                                 extension=extension),
            (False, "Could not validate contract terms."))
        st = _negotiations(app).get(pid_s)
        if not ok:
            if st is not None:
                st["note"] = str(reason or "")
                st["status"] = "countered"  # talks stay open
            return True
        old = _pending_counter_message(app, pid_s)
        if old is not None:
            _safe(lambda: setattr(old, "action_done", True))
        player.salary = aav
        player.contract_years = years
        # Batch D: clause + signing bonus ride counters too.
        extras, _err = _offer_extras(cmd)
        if extras:
            try:
                player.offered_clause_kind = extras["clause"]
                player.offered_clause_list_size = extras["clause_list_size"]
                player.offered_signing_bonus = extras["signing_bonus"]
            except Exception:
                pass
        handle_offer_command(app, pid_s, player, kind, years, aav)
        return True
    except Exception:
        return True


def _negotiate_accept(app, cmd):
    """Accept the agent's counter as-is: the real
    HockeyManagerGUI.accept_contract_counter (main.py:22456). Extensions
    sign instantly; UFA counters open a consideration bid window."""
    pid = cmd.get("player_id")
    if not pid:
        return True
    pid_s = str(pid)
    try:
        st = _negotiations(app).get(pid_s)
        if st is None:
            return True
        counter = _pending_counter_message(app, pid_s)
        if counter is None:
            return True
        try:
            ok = app.accept_contract_counter(counter)
        except Exception:
            return True
        kind = st.get("kind") or _neg_kind_for(app, pid_s)
        if ok:
            if kind == "extend":
                st["status"] = "accepted"
                st["note"] = ""
            else:
                st["status"] = "awaiting_agent"
                st["note"] = ("Counter accepted — your bid is in; the agent "
                              "decides after the consideration period.")
        else:
            # League-office veto path (desktop _inbox_contract_result
            # "rejected" with reject_note).
            st["status"] = "refused"
            st["note"] = ("The league office rejected the counter terms — "
                          "his camp must come back with a compliant number.")
        return True
    except Exception:
        return True


def _negotiate_walk(app, cmd):
    """Walk away: the desktop equivalent
    (inbox_window._on_contract_counter_walkaway) only marks the message
    done -- nothing happens to the game. We do the same and close the
    web state."""
    pid = cmd.get("player_id")
    if not pid:
        return True
    pid_s = str(pid)
    try:
        counter = _pending_counter_message(app, pid_s)
        if counter is not None:
            _safe(lambda: setattr(counter, "action_done", True))
        st = _negotiations(app).get(pid_s)
        if st is not None:
            st["status"] = "walked"
        return True
    except Exception:
        return True


@bp.route("/api/contracts/negotiation")
def api_contracts_negotiation():
    """Poll endpoint for the in-page negotiation modal (used by both the
    contracts and free-agents pages). 200 with the server-side
    negotiation state, or {"status": "none"} when there is none."""
    live = _live()
    if live is None:
        return jsonify({"status": "none", "error": "no live game"}), 503
    pid = request.args.get("player_id")
    if not pid:
        return jsonify({"status": "none",
                        "error": "player_id required"}), 400
    st = _safe(lambda: _negotiations(live).get(str(pid)))
    if not st:
        return jsonify({"status": "none"})
    return jsonify({
        "player_id": st.get("player_id"),
        "player_name": st.get("player_name"),
        "kind": st.get("kind"),
        "your_offers": st.get("your_offers") or [],
        "agent_ask": st.get("agent_ask"),
        "counter_terms": st.get("counter_terms"),
        "status": st.get("status", "awaiting_agent"),
        "note": st.get("note", ""),
    })


@bp.route("/api/contracts/negotiate", methods=["POST"])
def api_contracts_negotiate():
    """Enqueue a negotiation action on an open counter talk:
    {"player_id", "action": "counter"|"accept"|"walk", years?, aav?}.
    Counter terms are re-validated here (game's own gates + the signing
    window); the main-thread op validates once more before running."""
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    action = data.get("action")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    st = _safe(lambda: _negotiations(live).get(str(pid)))
    if not st or st.get("status") != "countered":
        return jsonify({"ok": False,
                        "error": "No open negotiation for this player."}), 409
    if action == "accept":
        queued = enqueue_command("negotiate_accept", player_id=str(pid))
    elif action == "walk":
        queued = enqueue_command("negotiate_walk", player_id=str(pid))
    elif action == "counter":
        try:
            years = int(data.get("years"))
            aav = int(data.get("aav"))
        except (TypeError, ValueError):
            return jsonify({"ok": False,
                            "error": "years and aav must be integers"}), 400
        extras, err = _offer_extras(data)
        if err:
            return jsonify({"ok": False, "error": err}), 400
        kind = st.get("kind") or _neg_kind_for(live, pid)
        player = _find_neg_person(live, pid, kind)
        if player is None:
            return jsonify({"ok": False, "error": "player not found"}), 404
        ok, msg = _validate_neg_offer(live, player, aav, years, kind)
        if not ok:
            return jsonify({"ok": False, "error": msg}), 422
        queued = enqueue_command("negotiate_counter", player_id=str(pid),
                                 years=years, aav=aav,
                                 clause=extras["clause"],
                                 clause_list_size=extras["clause_list_size"],
                                 signing_bonus=extras["signing_bonus"])
    else:
        return jsonify({"ok": False, "error": "unknown action"}), 400
    return jsonify({"ok": bool(queued), "action": action})


def _validate_neg_offer(live, player, aav, years, kind):
    """Full gate set for a web counter-offer, mirroring the initial
    offer endpoints: the game's _validate_contract_terms plus the
    signing/extension window and (UFA sign) roster eligibility."""
    extension = (kind == "extend")
    try:
        if extension:
            ok, msg = _validate_extension(live, player, aav, years)
            if not ok:
                return False, msg
            return _extension_window(live, player)
        # sign path: same three gates as api_free_agents_offer
        from web_ui.screens import free_agents as _fa
        ok, msg = _fa._validate_offer(live, player, aav, years,
                                      extension=False)
        if not ok:
            return False, msg
        ok, msg = _fa._window_check(live, player, extension=False)
        if not ok:
            return False, msg
        return _fa._sign_eligibility(live, player)
    except Exception:
        return False, "Could not validate counter-offer terms."

@bp.route("/api/contracts/auto_negotiate", methods=["POST"])
def api_contracts_auto_negotiate():
    """Auto-Negotiate All: queue extension talks for every expiring deal."""
    import web_ui.bridge as _b
    _b.enqueue_command("auto_negotiate_extensions")
    return jsonify({"ok": True})


# ======================================================================
# Batch D: contract clauses + signing-bonus sweetener + comparables,
# and the ELC (entry-level contract) flow.
#
# Desktop parity (ContractNegotiationView, windows.py):
#   - clause picker: the four engine clause kinds via
#     trade_engine.clause_annual_value (the salary-reduction lever --
#     an offered clause raises the *effective* offer in
#     handle_contract_offer, and lands on the deal via
#     apply_clause_to_contract). Staged on the player as
#     offered_clause_kind / offered_clause_list_size, exactly like the
#     desktop submit_offer.
#   - signing-bonus sweetener: a field on the offer (staged as
#     offered_signing_bonus); on ELC offers it is real money inside
#     the CBA 10%-of-base band. On standard offers the desktop stages
#     only the clause (the bonus rides the MP payload), so the web
#     shows it in the effective-offer preview for parity.
#   - comparables: same-position, +-4 OVR contracts league-wide
#     (windows.py _comparables).
#   - ELC mode (main.py:23809 handle_elc_offer): unsigned rights-held
#     prospects get a band-validated offer (floor/ceil, 10% signing
#     bonus, $1M/yr perf bonus cap, term locked by signing age) via
#     salary_cap_system.elc_band -- no `?elc=1` dead ends.
# ======================================================================

def _find_any_player(live, pid):
    """Roster + free-agent pool + unsigned prospects by id. Never raises."""
    pid_s = str(pid)
    pools = []
    try:
        gm = _safe(lambda: live.game_manager)
        team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
        league = _safe(lambda: gm.league) or _safe(lambda: live.league)
        pools.append(list(getattr(team, "roster", None) or []))
        pools.append(list(getattr(league, "free_agents", None) or []))
        pools.append(list(getattr(team, "prospects", None) or []))
    except Exception:
        pass
    for pool in pools:
        for p in pool:
            try:
                if str(_safe(lambda: getattr(p, "id", id(p)), "")) == pid_s:
                    return p
            except Exception:
                continue
    return None


def _clause_info(live, p):
    """Clause picker data for one player. Desktop parity
    (windows.py:_refresh_clause_hint, trade_engine). Never raises."""
    out = {"eligible": False, "eligibility_note": "", "demand": 0.0,
           "options": []}
    try:
        import trade_engine as te
    except Exception:
        out["eligibility_note"] = "Trade engine unavailable."
        return out
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    eligible = bool(_safe(lambda: te.clause_eligible(p), False))
    out["eligible"] = eligible
    if not eligible:
        out["eligibility_note"] = ("Trade protection isn't available here "
                                   "-- the NHL only allows it for players "
                                   "27+ or with 7 pro seasons.")
    demand = float(_safe(lambda: te.clause_demand_score(p, team, league),
                         0.0) or 0.0)
    out["demand"] = round(demand, 2)
    for kind in ("none", "nmc", "ntc", "mntc"):
        label = _safe(lambda k=kind: te.clause_offer_label(k, 10), kind)
        val = int(_safe(lambda k=kind: te.clause_annual_value(p, k), 0) or 0)
        out["options"].append({
            "kind": kind, "label": str(label or kind),
            "annual_value": val,      # salary-reduction lever ($/yr)
            "default_list_size": 10,  # M-NTC team-list size
        })
    if demand >= 0.65:
        out["hint"] = ("His camp is pushing hard for trade protection -- "
                       "expect to pay more without it.")
    elif demand >= 0.35:
        out["hint"] = "Trade protection would sweeten your offer."
    else:
        out["hint"] = ""
    return out


@bp.route("/api/contracts/clause_options")
def api_contracts_clause_options():
    """NTC/NMC clause picker data: eligibility, demand, per-kind annual
    value (the salary-reduction lever via trade_engine.clause_annual_value)
    and labels."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    p = _find_any_player(live, request.args.get("player_id"))
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    info = _clause_info(live, p)
    info["ok"] = True
    info["player"] = _safe(lambda: getattr(p, "full_name", "?"), "?")
    return jsonify(info)


@bp.route("/api/contracts/comparables")
def api_contracts_comparables():
    """Comparable contracts: same position, +-4 OVR, league-wide rosters
    (windows.py _comparables). Talent tier shown, never raw numbers the
    desktop hides."""
    live = _live()
    if live is None:
        return jsonify({"comparables": []})
    p = _find_any_player(live, request.args.get("player_id"))
    if p is None:
        return jsonify({"comparables": []})
    try:
        my_ovr = float(p.overall_rating())
    except Exception:
        my_ovr = 75.0
    my_pos = _safe(lambda: getattr(getattr(p, "primary_position", ""),
                                   "value", ""), "")
    try:
        from attribute_composites import talent_tier as _tt
    except Exception:
        _tt = None
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []
    comps = []
    for t in teams:
        for q in _safe(lambda: list(getattr(t, "roster", None) or []),
                       []) or []:
            try:
                if q is p:
                    continue
                ovr = float(q.overall_rating())
                if abs(ovr - my_ovr) > 4:
                    continue
                qpos = _safe(lambda: getattr(
                    getattr(q, "primary_position", ""), "value", ""), "")
                if qpos != my_pos:
                    continue
                qc = _safe(lambda: getattr(q, "contract", None))
                sal = int(_safe(lambda: getattr(qc, "salary", 0)
                                or getattr(q, "salary", 0) or 0, 0) or 0)
                yrs = int(_safe(lambda: getattr(qc, "years_remaining", 0)
                                or getattr(q, "contract_years", 0) or 0,
                                0) or 0)
                comps.append({
                    "name": _safe(lambda: getattr(q, "full_name", "?"), "?"),
                    "team": _safe(lambda: getattr(t, "team_name", ""), ""),
                    "position": qpos,
                    "overall": round(ovr, 1),
                    "tier": _safe(lambda: _tt(ovr), "") if _tt else "",
                    "salary": sal,
                    "years_remaining": yrs,
                    "ovr_gap": round(abs(ovr - my_ovr), 1),
                })
            except Exception:
                continue
    comps.sort(key=lambda c: (c["ovr_gap"], -c["salary"]))
    return jsonify({"comparables": comps[:5]})


def _offer_extras(data):
    """Parse optional clause + signing-bonus fields from an offer
    payload. Returns (extras dict, error). Never raises."""
    extras = {}
    clause = str(data.get("clause") or "none").strip().lower()
    if clause not in ("none", "nmc", "ntc", "mntc"):
        return None, f"unknown clause kind: {clause!r}"
    try:
        list_size = int(data.get("clause_list_size") or 10)
    except (TypeError, ValueError):
        list_size = 10
    list_size = max(1, min(31, list_size))
    try:
        sb = int(data.get("signing_bonus") or 0)
    except (TypeError, ValueError):
        return None, "signing_bonus must be a number"
    if sb < 0:
        return None, "signing_bonus cannot be negative"
    extras["clause"] = clause
    extras["clause_list_size"] = list_size
    extras["signing_bonus"] = sb
    return extras, ""


# ------------------------------------------------------------------
# ELC flow: entry-level contract with an unsigned rights-held prospect.
# Band validation + bonus fields, desktop parity (main.py:23809
# handle_elc_offer, salary_cap_system.elc_band).
# ------------------------------------------------------------------

def _elc_eligible_prospect(live, pid):
    """Unsigned rights-held prospect of the user's team (the exact guard
    handle_elc_offer enforces). Never raises."""
    pid_s = str(pid)
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    tname = _safe(lambda: getattr(team, "team_name", ""), "")
    pool = _safe(lambda: list(getattr(team, "prospects", None) or []),
                 []) or []
    for p in pool:
        try:
            if str(_safe(lambda: getattr(p, "id", id(p)), "")) != pid_s:
                continue
            if getattr(p, "contract", None) is not None:
                return None
            if (getattr(p, "rights_team", "") or "") != tname:
                return None
            return p
        except Exception:
            continue
    return None


def _elc_band_info(live, p):
    """ELC band via salary_cap_system.elc_band (signing-age on Sept 15).
    Returns dict with floor/ceiling/years/bonus caps, or error. Never
    raises."""
    try:
        import salary_cap_system as _scs
        league = _safe(lambda: getattr(getattr(live, "game_manager", None),
                                      "league", None))
        season = _safe(lambda: getattr(league, "season_year", None))
        age = int(_safe(lambda: getattr(p, "age", 20), 20) or 20)
        floor, ceil, years = _scs.elc_band(age, season)
        max_sb_pct = float(_safe(lambda: _scs.ELC_SIGNING_BONUS_PCT, 0.10)
                           or 0.10)
        max_pb = int(_safe(lambda: _scs.ELC_PERF_BONUS_MAX, 1_000_000)
                     or 1_000_000)
        max_comp = int(_safe(
            lambda: _scs.elc_max_annual_comp(season), ceil) or ceil)
        ask = _safe(lambda: _scs.elc_prospect_ask(p, season), {}) or {}
        return {
            "ok": years > 0,
            "floor": int(floor), "ceiling": int(ceil), "years": int(years),
            "signing_bonus_max_pct": max_sb_pct,
            "perf_bonus_max": max_pb,
            "max_annual_comp": max_comp,
            "agent_ask": {
                "salary": int(ask.get("salary", 0) or 0),
                "years": int(ask.get("years", years) or years),
                "signing_bonus": int(ask.get("signing_bonus", 0) or 0),
                "performance_bonus": int(ask.get("performance_bonus", 0)
                                         or 0),
                "flavor": str(ask.get("flavor", "") or ""),
            } if isinstance(ask, dict) else {},
            "error": "" if years > 0 else
                ("Not ELC-eligible at 25+: sign him to a standard contract "
                 "instead."),
        }
    except Exception as e:
        return {"ok": False, "error": f"ELC band unavailable: {e}"}


@bp.route("/api/contracts/elc_terms")
def api_contracts_elc_terms():
    """ELC terms for an unsigned prospect: band (floor/ceiling/years),
    bonus caps, and the agent's ask -- desktop parity with
    _refresh_elc_context (windows.py)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    p = _elc_eligible_prospect(live, request.args.get("player_id"))
    if p is None:
        return jsonify({"ok": False, "error":
            "Not your unsigned rights-held prospect."}), 404
    band = _elc_band_info(live, p)
    band["ok"] = bool(band.get("ok"))
    band["player"] = {
        "id": str(_safe(lambda: getattr(p, "id", ""), "")),
        "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
        "position": _web_position(p),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
        "overall": _safe(lambda: float(p.overall_rating()), 0.0),
        "potential": str(_safe(lambda: getattr(p, "potential_grade",
                                              "?"), "?")),
    }
    return jsonify(band)


@bp.route("/api/contracts/elc_offer", methods=["POST"])
def api_contracts_elc_offer():
    """Queue an ELC offer (salary + signing_bonus + performance_bonus).
    Server-side band validation mirrors handle_elc_offer; the
    main-thread op runs the real handshake."""
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    try:
        salary = int(data.get("salary"))
        sb = int(data.get("signing_bonus") or 0)
        pb = int(data.get("performance_bonus") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False,
                        "error": "salary/signing_bonus/performance_bonus "
                                 "must be integers"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    p = _elc_eligible_prospect(live, pid)
    if p is None:
        return jsonify({"ok": False,
                        "error": "Not your unsigned rights-held prospect."}), 404
    band = _elc_band_info(live, p)
    if not band.get("ok"):
        return jsonify({"ok": False,
                        "error": band.get("error") or "ELC ineligible"}), 422
    floor, ceil = band["floor"], band["ceiling"]
    if not (floor <= salary <= ceil):
        return jsonify({"ok": False, "error":
            f"ELC base must sit inside ${floor:,} - ${ceil:,}/yr."}), 422
    max_sb = int(round(salary * band["signing_bonus_max_pct"]))
    if not (0 <= sb <= max_sb):
        return jsonify({"ok": False, "error":
            f"Signing bonus capped at 10% of base (${max_sb:,}/yr)."}), 422
    if not (0 <= pb <= band["perf_bonus_max"]):
        return jsonify({"ok": False, "error":
            f"Performance bonus capped at ${band['perf_bonus_max']:,}/yr."}), 422
    if salary + sb > band["max_annual_comp"]:
        return jsonify({"ok": False, "error":
            "Base + signing bonus exceeds the ELC max annual compensation."}), 422
    queued = enqueue_command("elc_offer", player_id=str(pid),
                             salary=salary, signing_bonus=sb,
                             performance_bonus=pb,
                             years=band["years"])
    return jsonify({"ok": bool(queued), "queued": "elc_offer",
                    "years": band["years"]})
