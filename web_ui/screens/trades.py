"""Trades screen: trade center proposal builder (v1, read-only-friendly)."""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import (
    _safe,
    enqueue_command,
    to_web_player,
    to_web_team,
)

bp = Blueprint("trades", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


@bp.route("/trades")
def trades_page():
    return render_template("trades.html")


@bp.route("/api/trades/teams")
def api_trades_teams():
    """All 32 teams, flagging the user team and teams with players on the block."""
    live = _live()
    if live is None:
        return jsonify({"teams": [], "user_team": None, "trade_block_count": 0})
    gm = _safe(lambda: live.game_manager)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []
    my_name = _safe(lambda: gm.user_team.team_name) or _safe(lambda: live.user_team.team_name)

    # Which teams have players listed in app.trade_block?
    block = _safe(lambda: list(getattr(live, "trade_block", None) or []), []) or []
    block_teams = set()
    for p in block:
        try:
            owner = getattr(p, "team", None) or getattr(p, "team_name", None)
            block_teams.add(_team_name(owner))
        except Exception:
            continue

    out = []
    for t in teams:
        d = to_web_team(t)
        tn = _team_name(t)
        d["is_user"] = bool(my_name) and tn == my_name
        d["on_block"] = tn in block_teams
        out.append(d)
    return jsonify({
        "teams": out,
        "user_team": my_name,
        "trade_block_count": len(block),
    })


@bp.route("/api/trades/roster")
def api_trades_roster():
    """Roster for the named trade partner plus the user's own roster."""
    live = _live()
    if live is None:
        return jsonify({"team": None, "players": [], "my_roster": []})
    want = request.args.get("team", "")
    gm = _safe(lambda: live.game_manager)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []

    target = None
    for t in teams:
        if _team_name(t) == want:
            target = t
            break

    players = []
    if target is not None:
        players = [to_web_player(p)
                   for p in _safe(lambda: list(target.roster), []) or []]
    my = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    mine = [to_web_player(p)
            for p in _safe(lambda: list(my.roster), []) or []] if my else []
    return jsonify({"team": want, "players": players, "my_roster": mine})


@bp.route("/api/trades/propose", methods=["POST"])
def api_trades_propose():
    """Queue a trade proposal for the Tk main thread to evaluate/execute.

    v1 payload (team, give_ids, get_ids) -> queues "propose_trade"
    (the actual trade logic and AI evaluation live in Python; the parent
    wires "propose_trade" in _execute_command); this route only enqueues.

    v2 trade-builder payload (target_team_id, give_pids, give_picks,
    want_pids, want_picks) -> queues "execute_trade". The Tk-thread
    handler resolves the assets, validates retention/protection terms,
    and SENDS the offer through trade_negotiation.send_offer(): a
    pending negotiation with response_due = today + 1-3 days. The AI
    GM's answer (accept / counter / reject) arrives via the inbox on
    day advance -- instantly only on the deadline-day rush (desktop
    parity).

    Gap 2: optional "retention" ({pid: pct}) and "pick_protection"
    ({pick id: code}) terms, plus "retention_acquire" ({pid: pct} —
    salary we ask the PARTNER to keep on players we acquire).
    Hard server-side validation here (the UI also clamps — never trust
    it): pct must be 1-50, codes must be the engine's real set, and
    retention is dry-run through the engine's own _retention_check
    (slot limit, two-club/75-day rules) against the retaining club —
    ours for "retention", the partner for "retention_acquire".
    """
    data = request.get_json(force=True, silent=True) or {}

    # -- v2: trade-builder modal payload (players + picks, AI-gated) -----
    if "target_team_id" in data:
        team_id = data.get("target_team_id")
        give_pids = [str(x) for x in (data.get("give_pids") or [])]
        give_picks = [str(x) for x in (data.get("give_picks") or [])]
        want_pids = [str(x) for x in (data.get("want_pids") or [])]
        want_picks = [str(x) for x in (data.get("want_picks") or [])]
        if not team_id:
            return jsonify({"ok": False, "error": "missing target_team_id"}), 400
        if not give_pids and not give_picks and not want_pids and not want_picks:
            return jsonify({"ok": False, "error": "empty proposal"}), 400

        # -- Gap 2: retention + pick protection (server-side validation) --
        raw_retention = data.get("retention") or {}
        raw_protection = data.get("pick_protection") or {}
        if not isinstance(raw_retention, dict):
            raw_retention = {}
        if not isinstance(raw_protection, dict):
            raw_protection = {}
        for _k, _v in raw_retention.items():
            try:
                _pct = float(_v)
            except Exception:
                return jsonify({"ok": False,
                                "error": f"retention on {_k} is not a number"}), 400
            if not (0 < _pct <= 50):
                return jsonify({"ok": False,
                                "error": f"retention on {_k} must be 1-50% "
                                         f"(got {_pct:g}%)"}), 400
        for _k, _v in raw_protection.items():
            if str(_v) not in PROTECTION_CODES:
                return jsonify({"ok": False,
                                "error": f"unknown pick protection code: "
                                         f"{_v!r} (use one of "
                                         f"{', '.join(PROTECTION_CODES)})"}), 400
        retention_terms = parse_retention_terms(raw_retention, set(give_pids))
        protection_terms = parse_protection_terms(raw_protection, set(give_picks))
        # Opponent retention: salary we ask the PARTNER to keep on
        # players we acquire (0/25/50%). Same wire format as
        # "retention", validated against the partner club below.
        raw_ret_acq = data.get("retention_acquire") or {}
        if not isinstance(raw_ret_acq, dict):
            raw_ret_acq = {}
        for _k, _v in raw_ret_acq.items():
            try:
                _pct = float(_v)
            except Exception:
                return jsonify({"ok": False,
                                "error": f"retention_acquire on {_k} is "
                                         f"not a number"}), 400
            if not (0 < _pct <= 50):
                return jsonify({"ok": False,
                                "error": f"retention_acquire on {_k} must be "
                                         f"1-50% (got {_pct:g}%)"}), 400
        # Dry-run retention through the engine's real rules (slot limit,
        # two-club/75-day CBA rules). Ours dry-runs against OUR club;
        # theirs dry-runs against the PARTNER club. Engine re-checks at
        # execution too.
        live = _live()
        user_team = partner = None
        if live is not None:
            _gm2 = _safe(lambda: live.game_manager)
            user_team = _safe(lambda: _gm2.user_team) \
                or _safe(lambda: live.user_team)
            partner = _find_team(live, team_id)
        if user_team is not None and retention_terms:
            _gplayers, _ = _resolve_assets(user_team, give_pids, [])
            _ok, _errs = validate_retention_terms(
                user_team, _gplayers, retention_terms)
            if not _ok:
                return jsonify({"ok": False,
                                "error": "retention invalid: "
                                         + "; ".join(_errs)}), 400
        acquire_terms = parse_retention_terms(raw_ret_acq, set(want_pids))
        if acquire_terms:
            if partner is None:
                return jsonify({"ok": False,
                                "error": "unknown trade partner"}), 400
            _wplayers, _ = _resolve_assets(partner, want_pids, [])
            _ok, _errs = validate_retention_terms(
                partner, _wplayers, acquire_terms)
            if not _ok:
                return jsonify({"ok": False,
                                "error": "retention_acquire invalid: "
                                         + "; ".join(_errs)}), 400

        ok = enqueue_command(
            "execute_trade",
            target_team_id=str(team_id),
            give_pids=give_pids,
            give_picks=give_picks,
            want_pids=want_pids,
            want_picks=want_picks,
            retention=retention_terms,
            retention_acquire=acquire_terms,
            pick_protection=protection_terms,
        )
        return jsonify({"ok": ok, "queued": "execute_trade", "team": team_id})

    # -- v1: original payload -------------------------------------------------
    # The v1 desktop-window flow is retired (no OS popups): trades now go
    # through the in-page Trade Builder modal (v2 above) with live AI
    # evaluation. This branch returns an in-page error the v1 JS renders
    # in its note area.
    team = data.get("team")
    if team or data.get("give_ids") or data.get("get_ids"):
        return jsonify({
            "ok": False,
            "error": "Use the Trade Builder modal — it evaluates with "
                     "the live AI and executes accepted deals.",
        }), 400
    return jsonify({"ok": False, "error": "empty proposal"}), 400


# ======================================================================
# Trade builder v2 (2026-10-04): interactive in-page modal + real AI eval.
# Appended; the v1 routes above are untouched.
#
# New routes:
# - GET /api/trades/assets?team_id=X — players + draft picks for a team.
# - GET /api/trades/evaluate — read-only REAL AI verdict via
#   trade_engine.ai_consider_trade() (accept/reject/counter + reason + values).
# - POST /api/trades/propose — extended additively: the new-style payload
#   (target_team_id + give_pids/give_picks/want_pids/want_picks) enqueues
#   "execute_trade"; the v1 payload keeps its old "propose_trade" behavior.
# - GET /api/trades/result — poll the last queued execute_trade outcome
#   (the Tk-thread handler stashes it on app._web_trade_result).
#
# Writes ONLY go through enqueue_command(). The coordinator wires
# "execute_trade" in bridge._execute_command(): it re-validates AI acceptance
# and calls the real trade_engine.execute_trade() there.
# ======================================================================


def _round_suffix(r):
    try:
        r = int(r)
    except Exception:
        return ""
    if 11 <= (r % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(r % 10, "th")


def _to_web_pick(pk):
    """DraftPick -> JSON-safe dict."""
    year = _safe(lambda: int(getattr(pk, "year", 0) or 0), 0)
    rnd = _safe(lambda: int(getattr(pk, "round", 0) or 0), 0)
    orig = _safe(lambda: str(getattr(pk, "original_team", "") or ""), "")
    cur = _safe(lambda: str(getattr(pk, "current_team", "") or ""), "")
    if orig and cur and orig != cur:
        label = f"{year} {rnd}{_round_suffix(rnd)} (from {orig})"
    else:
        label = f"{year} {rnd}{_round_suffix(rnd)}"
    return {
        "kind": "pick",
        "id": _safe(lambda: str(getattr(pk, "id", "")), ""),
        "year": year,
        "round": rnd,
        "original_team": orig,
        "current_team": cur,
        "protection": _safe(lambda: str(getattr(pk, "protection", "") or ""), ""),
        "label": label,
    }


def _team_trade_lists(team):
    """(players, picks) the game lets a team trade: roster, ahl_roster,
    prospects, and draft_picks {year: [DraftPick]}."""
    players = []
    for attr, level in (("roster", "NHL"), ("ahl_roster", "AHL"),
                        ("prospects", "Prospects")):
        for p in _safe(lambda: list(getattr(team, attr, None) or []), []) or []:
            players.append((p, level))
    picks = []
    by_year = _safe(lambda: dict(getattr(team, "draft_picks", None) or {}), {}) or {}
    for year in sorted(by_year.keys()):
        for pk in _safe(lambda: list(by_year.get(year) or []), []) or []:
            picks.append(pk)
    return players, picks


def _find_team(live, team_id):
    """Match a team by abbreviation, name, team_name, or 'City Name'."""
    if not team_id:
        return None
    gm = _safe(lambda: live.game_manager)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []
    want = str(team_id).strip().lower()
    for t in teams:
        d = to_web_team(t)
        cands = {
            str(d.get("abbr") or "").lower(),
            str(d.get("name") or "").lower(),
            str(_team_name(t) or "").lower(),
            f"{d.get('city', '')} {d.get('name', '')}".strip().lower(),
        }
        if want in cands:
            return t
    return None


def _resolve_assets(team, pids, pick_ids):
    """Map id strings -> live game objects (players, picks)."""
    pid_set = {str(x) for x in (pids or [])}
    pick_set = {str(x) for x in (pick_ids or [])}
    players, picks = _team_trade_lists(team)
    out_players = [p for p, _lvl in players if str(getattr(p, "id", "")) in pid_set]
    out_picks = [pk for pk in picks if str(getattr(pk, "id", "")) in pick_set]
    return out_players, out_picks


def _trade_engine():
    """Lazy import of the game's trade engine (keeps Flask import light)."""
    try:
        import trade_engine
        return trade_engine
    except Exception:
        return None


@bp.route("/api/trades/assets")
def api_trades_assets():
    """Tradeable assets of one team: players (roster/AHL/prospects) + picks."""
    live = _live()
    if live is None:
        return jsonify({"team": None, "players": [], "picks": []})
    team = _find_team(live, request.args.get("team_id", ""))
    if team is None:
        return jsonify({"error": "unknown team"}), 404
    players, picks = _team_trade_lists(team)
    slots = retention_slots_summary(team)
    return jsonify({
        "team": _team_name(team),
        "players": [{**to_web_player(p), "level": lvl,
                     "cap_hit": _player_cap_hit(p)}
                    for p, lvl in players],
        "picks": [_to_web_pick(pk) for pk in picks],
        # Gap 2: retention slot meter + the engine's real protection codes.
        "retention_slots_used": slots["used"],
        "retention_slots_max": slots["max"],
        "protection_options": protection_options(),
    })


@bp.route("/api/trades/evaluate")
def api_trades_evaluate():
    """Read-only REAL AI verdict on a hypothetical deal.

    Query params: give_pids, give_picks, want_pids, want_picks (comma ids),
    target_team_id. Gap 2 additions: retention ("pid:pct,pid:pct"),
    retention_acquire ("pid:pct,pid:pct" — salary we ask the partner to
    keep on players we acquire) and protection ("pickid:code,pickid:code")
    — retention is passed to the real ai_consider_trade() (its cap check
    is retention-aware) and both term sets are echoed back for the UI.
    No state mutation: only calls trade_engine's read-only
    ai_consider_trade() + evaluate_trade(). Protection is never stamped
    on live picks here (that happens only at execution, in the bridge).
    """
    live = _live()

    def _csv(name):
        raw = request.args.get(name, "") or ""
        return [s.strip() for s in raw.split(",") if s.strip()]

    target_id = request.args.get("target_team_id", "")
    give_pids, give_picks = _csv("give_pids"), _csv("give_picks")
    want_pids, want_picks = _csv("want_pids"), _csv("want_picks")

    if live is None:
        # Mock/demo mode: no game loaded — clearly labeled.
        return jsonify({
            "verdict": "reject",
            "reason": "Demo mode — connect a live game for a real AI verdict.",
            "mock": True,
            "give_value": 0, "get_value": 0, "diff": 0, "ratio": 0.0,
            "label": "Demo",
        })

    _gm3 = _safe(lambda: live.game_manager)
    user_team = _safe(lambda: _gm3.user_team) or _safe(lambda: live.user_team)
    partner = _find_team(live, target_id)
    te = _trade_engine()
    if user_team is None or partner is None or te is None:
        return jsonify({"verdict": "reject",
                        "reason": "Could not resolve teams or trade engine.",
                        "give_value": 0, "get_value": 0, "diff": 0,
                        "ratio": 0.0, "label": "Incomplete"})

    give_players, give_pick_objs = _resolve_assets(user_team, give_pids, give_picks)
    want_players, want_pick_objs = _resolve_assets(partner, want_pids, want_picks)
    give_assets = give_players + give_pick_objs
    want_assets = want_players + want_pick_objs

    # Gap 2: parse + sanitize the deal terms (retention pct, protection
    # codes) and dry-run retention against the real engine rules. Picks
    # are NOT mutated here — protection stamps happen at execution only.
    retention_terms = parse_retention_terms(
        dict(_pair_csv(request.args.get("retention", ""))),
        {str(getattr(p, "id", "")) for p in give_players})
    protection_terms = parse_protection_terms(
        dict(_pair_csv(request.args.get("protection", ""))),
        {str(getattr(pk, "id", "")) for pk in give_pick_objs})
    ret_ok, ret_errors = validate_retention_terms(
        user_team, give_players, retention_terms)
    # Opponent retention: salary we ask the PARTNER to keep on players
    # we acquire. Validated against the partner club (their 3-slot
    # limit, two-club/75-day rules); merged into the retention map for
    # the AI verdict — the engine prices both sides generically.
    acquire_terms = parse_retention_terms(
        dict(_pair_csv(request.args.get("retention_acquire", ""))),
        {str(getattr(p, "id", "")) for p in want_players})
    acq_ok, acq_errors = validate_retention_terms(
        partner, want_players, acquire_terms)
    prot_adj = protection_value_adjustment(give_pick_objs, protection_terms, te)
    terms_note = deal_terms_note(give_players, give_pick_objs,
                                 retention_terms, protection_terms,
                                 want_players=want_players,
                                 acquire_terms=acquire_terms)

    if not give_assets and not want_assets:
        return jsonify({"verdict": "reject",
                        "reason": "There's nothing on the table yet.",
                        "give_value": 0, "get_value": 0, "diff": 0,
                        "ratio": 0.0, "label": "Incomplete"})

    # Value breakdown (pure math, no AI opinion).
    ev = _safe(lambda: te.evaluate_trade(
        give_assets, want_assets,
        user_team=user_team, partner_team=partner,
        perceiver_team=partner))
    give_value = _safe(lambda: ev.user_value, 0) or 0
    get_value = _safe(lambda: ev.partner_value, 0) or 0
    diff = _safe(lambda: ev.diff, give_value - get_value) or 0
    ratio = _safe(lambda: ev.ratio, 0.0) or 0.0
    label = _safe(lambda: ev.label, "Incomplete") or "Incomplete"

    # REAL AI verdict — read-only; ai_consider_trade never mutates.
    # Retention is passed through: the AI's cap check prices the reduced
    # incoming hit exactly like a real GM pricing retained money. Both
    # sides' terms ride in one map (the engine splits them per side).
    all_retention = {**retention_terms, **acquire_terms}

    def _verdict_call():
        try:
            return te.ai_consider_trade(
                partner, give_assets, want_assets, user_team=user_team,
                retention=all_retention)
        except TypeError:
            # Older ai_consider_trade without the retention kwarg.
            return te.ai_consider_trade(
                partner, give_assets, want_assets, user_team=user_team)
    resp = _safe(_verdict_call)
    verdict = _safe(lambda: resp.decision, "reject") or "reject"
    reason = _safe(lambda: resp.message, "") or ""

    return jsonify({
        "verdict": verdict,          # accept | reject | counter
        "reason": reason,
        "give_value": give_value,    # what we give up (trade points)
        "get_value": get_value,      # what we receive (trade points)
        "diff": diff,
        "ratio": ratio,
        "label": label,
        "give_count": len(give_assets),
        "get_count": len(want_assets),
        # Gap 2: deal terms reflected in the verdict.
        "retention_terms": retention_terms,    # {pid: pct} we retain
        "retention_acquire_terms": acquire_terms,  # {pid: pct} they retain
        "protection_terms": protection_terms,  # {pick id: code}
        "retention_valid": ret_ok,
        "retention_errors": ret_errors,
        "retention_acquire_valid": acq_ok,
        "retention_acquire_errors": acq_errors,
        "protection_adjustment": prot_adj,     # heuristic pts (display)
        "terms_note": terms_note,
    })


@bp.route("/api/trades/result")
def api_trades_result():
    """Last queued execute_trade outcome (stashed by the Tk-thread handler)."""
    live = _live()
    result = _safe(lambda: getattr(live, "_web_trade_result", None)) if live else None
    return jsonify({"result": result})


# ======================================================================
# Gap 2: salary retention + pick protection in the trade builder.
# (Appended 2026-10-04; v2 routes above untouched except additive edits.)
#
# Wire format (matches the desktop flow in trade_negotiation.py):
#   retention:      {player id (str): pct} — salary the user's club keeps
#                   on players it trades away. Engine: 1-50% per deal,
#                   max 3 active slots per club (trade_engine.MAX_*
#                   constants). Passed to ai_consider_trade() (its cap
#                   check is retention-aware) and execute_trade().
#   retention_acquire:
#                   {player id (str): pct} — salary the user asks the
#                   PARTNER club to keep on players the user acquires.
#                   Same engine limits, dry-run against the PARTNER
#                   (their slot count / aggregate / 75-day clock). The
#                   bridge merges both maps into one retention dict for
#                   send_offer/execute_trade (the engine splits per side:
#                   the retaining club is whichever side traded the
#                   player away).
#   pick_protection:{pick id (str): code} — the engine's REAL protection
#                   codes are "top-3" | "top-10" | "lottery" (see
#                   trade_engine.protection_label). Applied at execution
#                   by stamping pick.protection/is_conditional/condition,
#                   exactly like trade_negotiation._neg_terms(stamp=True).
# ======================================================================

# Engine's real protection codes — never invent others.
PROTECTION_CODES = ("top-3", "top-10", "lottery")

# Retention pct choices offered in the UI (engine max is 50).
RETENTION_OPTIONS = (0, 25, 50)

# Protection valuation haircut for the verdict display. The ENGINE does
# not price protection (pick_trade_value ignores it; the desktop flow
# doesn't adjust either), so this is a documented UI heuristic: a
# protected pick may roll to next year, making it worth less to the
# receiving GM. The AI's accept/reject decision itself is unchanged.
PROTECTION_HAIRCUT = {"top-3": 0.15, "top-10": 0.25, "lottery": 0.35}


def _player_cap_hit(p):
    """Engine-consistent cap hit: contract salary minus retained amount."""
    hit = _safe(lambda: int(getattr(getattr(p, "contract", None),
                                   "salary", 0) or 0), 0)
    if not hit:
        hit = _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)
    hit -= _safe(lambda: int(getattr(p, "retained_amount", 0) or 0), 0)
    return max(0, hit)


def _fmt_money(n):
    try:
        n = int(n)
    except Exception:
        return "$0"
    if n >= 1_000_000:
        return f"${n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"${round(n / 1_000)}K"
    return f"${n}"


def retention_slots_summary(team):
    """{used, max} retention slots for a club. _safe()-wrapped."""
    te = _trade_engine()
    used = _safe(lambda: int(te.retention_slots_used(team)), 0) if te else 0
    mx = _safe(lambda: int(te.MAX_RETENTION_SLOTS), 3) if te else 3
    return {"used": max(0, used), "max": max(1, mx)}


def protection_options():
    """[{code, label}] using the engine's real protection_label()."""
    te = _trade_engine()
    out = []
    for code in PROTECTION_CODES:
        label = _safe(lambda c=code: te.protection_label(c), "") if te else ""
        out.append({"code": code, "label": label or code})
    return out


def parse_retention_terms(raw, valid_pids=None):
    """Sanitize retention terms -> {str pid: float pct}.

    Keeps only terms for assets the user is actually trading away
    (valid_pids) with 0 < pct <= engine MAX_RETENTION_PCT. Anything
    else is dropped (the propose endpoint hard-rejects bad input
    before this is reached).
    """
    te = _trade_engine()
    cap = _safe(lambda: float(te.MAX_RETENTION_PCT), 50.0) if te else 50.0
    out = {}
    items = raw.items() if isinstance(raw, dict) else []
    for k, v in items:
        pid = str(k)
        if valid_pids is not None and pid not in {str(x) for x in valid_pids}:
            continue
        try:
            pct = float(v)
        except Exception:
            continue
        if 0 < pct <= cap:
            out[pid] = pct
    return out


def parse_protection_terms(raw, valid_pick_ids=None):
    """Sanitize pick protection -> {str pick id: code}.

    Keeps only the engine's real codes for picks the user is actually
    trading away.
    """
    out = {}
    items = raw.items() if isinstance(raw, dict) else []
    for k, v in items:
        kid = str(k)
        if valid_pick_ids is not None and \
                kid not in {str(x) for x in valid_pick_ids}:
            continue
        code = str(v or "").strip()
        if code in PROTECTION_CODES:
            out[kid] = code
    return out


def validate_retention_terms(user_team, give_players, retention_terms):
    """Dry-run every retention term against the real engine rules.

    Uses trade_engine.apply_retention_dry_run (the same _retention_check
    execute_trade preflights): 1-50%, 3-slot club limit (counting the
    other proposed terms in this deal via `extra`), 15% aggregate is
    checked at execution, two-club/75-day rules included.
    Returns (ok, [error strings]). _safe()-wrapped reads only.
    """
    te = _trade_engine()
    if not retention_terms:
        return True, []
    if te is None or user_team is None:
        return False, ["Trade engine unavailable for retention check."]
    by_id = {}
    for p in give_players or []:
        by_id[str(_safe(lambda: getattr(p, "id", ""), ""))] = p
    errors = []
    for pid, pct in retention_terms.items():
        player = by_id.get(str(pid))
        if player is None:
            errors.append(f"Retention target {pid} is not in the deal.")
            continue
        others = {k: v for k, v in retention_terms.items()
                  if str(k) != str(pid)}
        ok, msg = _safe(
            lambda: te.apply_retention_dry_run(user_team, player, pct,
                                               extra=others),
            (False, "retention check failed"))
        if not ok:
            name = _safe(lambda: getattr(player, "full_name", pid), pid)
            errors.append(f"{name}: {msg}")
    return (len(errors) == 0), errors


def protection_value_adjustment(give_pick_objs, protection_terms, te=None):
    """Heuristic point discount for protected outgoing picks (display).

    Documented estimate only — the engine's pick_trade_value does not
    price protection. Returned so the verdict panel can show the user
    what the protection likely costs their offer.
    """
    te = te or _trade_engine()
    if not protection_terms or te is None:
        return 0
    adj = 0
    for pk in give_pick_objs or []:
        code = (protection_terms or {}).get(
            str(_safe(lambda: getattr(pk, "id", ""), "")))
        haircut = PROTECTION_HAIRCUT.get(code)
        if not haircut:
            continue
        val = _safe(lambda: te.pick_trade_value(pk), 0) or 0
        adj += int(round(val * haircut))
    return adj


def deal_terms_note(give_players, give_pick_objs, retention_terms,
                    protection_terms, want_players=None,
                    acquire_terms=None):
    """Human-readable summary of the deal's retention/protection terms."""
    te = _trade_engine()
    bits = []
    for p in give_players or []:
        pct = (retention_terms or {}).get(
            str(_safe(lambda: getattr(p, "id", ""), "")))
        if pct:
            name = _safe(lambda: getattr(p, "full_name", "?"), "?")
            amt = int(round(_player_cap_hit(p)
                            * min(float(pct), 50.0) / 100.0))
            bits.append(f"you retain {float(pct):g}% "
                        f"({_fmt_money(amt)}) on {name}")
    for p in want_players or []:
        pct = (acquire_terms or {}).get(
            str(_safe(lambda: getattr(p, "id", ""), "")))
        if pct:
            name = _safe(lambda: getattr(p, "full_name", "?"), "?")
            amt = int(round(_player_cap_hit(p)
                            * min(float(pct), 50.0) / 100.0))
            bits.append(f"they retain {float(pct):g}% "
                        f"({_fmt_money(amt)}) on {name}")
    for pk in give_pick_objs or []:
        code = (protection_terms or {}).get(
            str(_safe(lambda: getattr(pk, "id", ""), "")))
        if code:
            label = _safe(lambda: te.protection_label(code), code) \
                if te else code
            desc = _safe(lambda: getattr(pk, "description",
                                         "pick"), "pick")
            bits.append(f"{desc} is {str(label).lower()}")
    if not bits:
        return ""
    return "Deal terms: " + "; ".join(bits) + "."


def _pair_csv(raw):
    """Parse 'a:1,b:2' query param -> [(a, 1), (b, 2)] (values stay str)."""
    out = []
    for chunk in str(raw or "").split(","):
        chunk = chunk.strip()
        if ":" not in chunk:
            continue
        k, v = chunk.split(":", 1)
        k, v = k.strip(), v.strip()
        if k:
            out.append((k, v))
    return out


# ======================================================================
# Async trade negotiations (desktop parity, trade_negotiation.py).
#
# Proposing a trade (bridge op "execute_trade") now SENDS an offer:
# a pending TradeNegotiation with response_due = today + 1-3 days.
# The AI GM's answer (accept / counter / reject) arrives via the
# inbox when process_due_negotiations runs on day advance
# (main.simulate_day) -- instantly only on the deadline-day rush.
# This endpoint exposes the open negotiation threads (history +
# current terms) for the Trade Center's "Open negotiations" panel;
# answering happens from the inbox (inbox_trade_accept/decline, wired
# in bridge.py) or via a counter from this screen
# ("trade_counter_negotiation" command).
# ======================================================================

@bp.route("/api/trades/negotiations")
def api_trades_negotiations():
    """Open trade negotiation threads for the user team."""
    live = _live()
    if live is None:
        return jsonify({"negotiations": []})
    gm = _safe(lambda: live.game_manager)
    store = _safe(lambda: list(getattr(gm, "trade_negotiations", None) or []),
                  []) or []
    try:
        import trade_negotiation as tn
    except Exception:
        tn = None
    out = []
    for n in store:
        try:
            if tn is not None and isinstance(n, tn.TradeNegotiation):
                is_open = n.is_open
            else:
                is_open = str(getattr(n, "status", "")) in (
                    "awaiting_ai", "awaiting_user")
            if not is_open:
                continue
            due = getattr(n, "response_due", None)
            created = getattr(n, "created", None)
            if tn is not None and isinstance(n, tn.TradeNegotiation):
                you_send = tn.asset_summary(
                    n.user_assets, n.retention, n.pick_protection)
                you_get = tn.asset_summary(n.partner_assets)
            else:
                you_send = ", ".join(
                    str(a.get("name", "?")) for a in
                    (getattr(n, "user_assets", None) or [])
                    if isinstance(a, dict)) or "?"
                you_get = ", ".join(
                    str(a.get("name", "?")) for a in
                    (getattr(n, "partner_assets", None) or [])
                    if isinstance(a, dict)) or "?"
            out.append({
                "id": str(getattr(n, "id", "")),
                "partner": str(getattr(n, "partner_team_name", "?")),
                "direction": str(getattr(n, "direction", "")),
                "status": str(getattr(n, "status", "")),
                "rounds": int(getattr(n, "rounds", 0) or 0),
                "patience": round(float(getattr(n, "patience", 1.0) or 1.0), 2),
                "response_due": (due.isoformat() if hasattr(due, "isoformat")
                                 else None),
                "created": (created.isoformat()
                            if hasattr(created, "isoformat") else None),
                "you_send": you_send,
                "you_get": you_get,
                "last_message": str(getattr(n, "last_message", "") or ""),
                "history": [
                    {"date": str(h.get("date", "")),
                     "by": str(h.get("by", "")),
                     "summary": str(h.get("summary", ""))}
                    for h in (getattr(n, "history", None) or [])
                    if isinstance(h, dict)
                ],
            })
        except Exception:
            continue
    # Most recent first.
    out.sort(key=lambda d: (d.get("created") or ""), reverse=True)
    return jsonify({"negotiations": out})
