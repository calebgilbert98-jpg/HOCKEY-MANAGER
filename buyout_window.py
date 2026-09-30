# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""The June 15-30 buyout window (real NHL timing).

Called once per offseason from HockeyManagerGUI._start_offseason, BEFORE
the July-1 jump and BEFORE league.end_of_season(). The stamped game date
is moved into the window (June 15) so the date gate in
transaction_windows.check_window("buyout", ...) sees a real window --
previously the July-1 jump skipped June 15-30 entirely, which meant the
gate made buyouts IMPOSSIBLE for everyone, and no AI GM ever bought a
player out.

AI clubs are processed end-to-end (same buyout math as the user). The
user's candidates arrive as an interactive inbox message
(action_type "buyout_window"), mirroring the RFA qualifying pattern:
the message itself is the window authorization, so resolving it after
July 1 does not re-hit the calendar gate.

One rulebook: execute_buyout() is the single data mutation. The
BuyoutCalculatorView._confirm_buyout user path calls it too.
"""

import random

# Tuning knobs -----------------------------------------------------------
# Minimum year-1 cap savings for a buyout to be worth the future dead cap.
MIN_Y1_SAVINGS = 500_000
# Cap-space threshold: only teams tighter than this consider buyouts.
NEED_SPACE_BELOW = 8_000_000
# Dead-weight tests (cap hit vs overall). Franchise pieces (>= 86) are
# never candidates. Calibrated so fair-value middle-six deals don't trip
# it: a 79-overall at $5M is roughly fair money, not a buyout.
DEAD_WEIGHT_RULES = (
    (6_000_000, 82),
    (4_500_000, 78),
    (3_000_000, 75),
)
# Old + expensive + term left: the classic buyout profile.
OLD_EXPENSIVE_AGE = 34
OLD_EXPENSIVE_HIT = 4_000_000
OLD_EXPENSIVE_OVR = 80
# At most this many buyouts per team per summer (real NHL: a handful
# league-wide).
MAX_BUYOUTS_PER_TEAM = 2


def _money(n):
    try:
        return f"${int(n):,}"
    except Exception:
        return "$0"


def execute_buyout(league, team, player, season_year=None):
    """Buy out a player's contract. The single data mutation for ALL
    buyout paths (AI window, user calculator, interactive inbox, MP).

    Writes team.buyout_cap_hits keyed by season-start calendar year,
    removes the player from the roster, and makes him a free agent
    (discoverable via team_name == "Free Agent", like every other path).
    Returns the (total_cost, annual_hit, buyout_years, rows) schedule.
    """
    from windows import buyout_schedule
    from trade_engine import clear_retention_state as _clr_ret

    total, annual, byears, rows = buyout_schedule(player)
    if not rows:
        return total, annual, byears, rows
    if season_year is None:
        season_year = int(getattr(league, "season_year", 2026) or 2026)
    hits = getattr(team, "buyout_cap_hits", None)
    if hits is None:
        hits = {}
        team.buyout_cap_hits = hits
    for i, hit, _s in rows:
        yr = int(season_year) + i - 1
        hits[yr] = hits.get(yr, 0) + hit
    if player in getattr(team, "roster", []) or []:
        team.roster.remove(player)
    player.team_name = "Free Agent"
    # His SPC is dead: the player-side retention fields clear (no more
    # discount for anyone). The retaining club's ledger entry stays live
    # -- that dead cap survives the buyout, per CBA.
    try:
        _clr_ret(player)
    except Exception:
        pass
    return total, annual, byears, rows


def _candidate_rows(team):
    """(player, contract, overall, cap_hit) for plausible buyout targets."""
    out = []
    for p in list(getattr(team, "roster", None) or []):
        try:
            c = getattr(p, "contract", None)
            if c is None:
                continue
            if bool(getattr(c, "entry_level", False)):
                continue  # buying out an ELC is never sensible
            if int(getattr(c, "years_remaining", 0) or 0) < 1:
                continue
            # Real NHL: a player with an NMC/NTC can't be bought out
            # without consent. The AI doesn't ask; it moves on.
            if bool(getattr(c, "no_movement_clause", False)):
                continue
            if bool(getattr(c, "no_trade_clause", False)):
                continue
            try:
                ovr = int(p.overall_rating())
            except Exception:
                continue
            if ovr >= 86:
                continue  # franchise pieces don't get bought out
            cap_hit = int(getattr(c, "salary", 0) or 0)
            if cap_hit < 2_000_000:
                continue
            out.append((p, c, ovr, cap_hit))
        except Exception:
            continue
    return out


def _is_dead_weight(p, c, ovr, cap_hit):
    age = getattr(p, "age", 30) or 30
    try:
        age = int(age)
    except Exception:
        age = 30
    for min_hit, max_ovr in DEAD_WEIGHT_RULES:
        if cap_hit >= min_hit and ovr < max_ovr:
            return True
    yrs = int(getattr(c, "years_remaining", 0) or 0)
    if (age >= OLD_EXPENSIVE_AGE and cap_hit >= OLD_EXPENSIVE_HIT
            and ovr < OLD_EXPENSIVE_OVR and yrs >= 2):
        return True
    return False


def _team_space(team):
    try:
        from salary_cap_system import cap_breakdown
        return int(cap_breakdown(team).get("space", 0) or 0)
    except Exception:
        return 0


def _gm_trigger_prob(team):
    """Shrewder GMs use the tool more. Defensive: neutral 0.5."""
    try:
        prof = getattr(team, "gm_profile", None)
        abil = float(getattr(prof, "gm_ability01", 0.5) or 0.5)
    except Exception:
        abil = 0.5
    abil = max(0.0, min(1.0, abil))
    return 0.35 + 0.5 * abil


def _is_nhl_team(team):
    return str(getattr(team, "league_name", "") or "") == "National Hockey League"


def _is_user_team(league, team):
    try:
        return team is getattr(league, "user_team", None)
    except Exception:
        return False


def _record_ledger(league, team, player, total, annual, byears, app=None):
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app) if app is not None else None
        if led is None:
            return
        tn = getattr(team, "team_name", "")
        pn = getattr(player, "full_name", getattr(player, "name", "A player"))
        led.record(
            kind="buyout", teams=[tn], players=[pn], weight=45,
            season=int(getattr(league, "season_year", 2026) or 2026) + 1,
            text=f"{tn} buy out {pn} "
                 f"(${int(total):,} over {byears} years).",
            facts={"player": pn, "team": tn, "total_cost": int(total),
                   "annual_hit": int(annual), "years": int(byears)})
    except Exception:
        pass


def process_buyout_window(league, app=None, rng=None):
    """Run the June 15-30 buyout window. Returns a summary dict.

    AI clubs: evaluated and executed end-to-end. User club: candidates
    are queued as an interactive inbox message; nothing is executed
    without the user's decision.
    """
    r = rng or random.Random()
    from windows import buyout_schedule

    summary = {"ai_buyouts": [], "user_candidates": 0, "window_year": None}
    try:
        summary["window_year"] = int(getattr(league, "season_year", 2026) or 2026) + 1
    except Exception:
        pass
    # Dead-cap hits key to the season the window opens (e.g. a June 2027
    # buyout hits 2027-28 onward).
    season_year = summary["window_year"]

    user_team = None
    ai_teams = []
    for team in list(getattr(league, "teams", []) or []):
        try:
            if not _is_nhl_team(team):
                continue
            if _is_user_team(league, team) or bool(getattr(team, "is_user_team", False)):
                user_team = team
            else:
                ai_teams.append(team)
        except Exception:
            continue

    # --- AI clubs -------------------------------------------------------
    for team in ai_teams:
        try:
            space = _team_space(team)
            if space > NEED_SPACE_BELOW:
                continue  # comfortable teams don't eat dead cap
            prob = _gm_trigger_prob(team)
            done = 0
            cands = _candidate_rows(team)
            # Biggest savings first (the most tempting lever).
            scored = []
            for (p, c, ovr, cap_hit) in cands:
                try:
                    _t, _a, _y, rows = buyout_schedule(p)
                    y1 = rows[0][2] if rows else 0
                except Exception:
                    y1 = 0
                scored.append((y1, p, c, ovr, cap_hit))
            scored.sort(key=lambda s: s[0], reverse=True)
            for (y1, p, c, ovr, cap_hit) in scored:
                if done >= MAX_BUYOUTS_PER_TEAM:
                    break
                if y1 < MIN_Y1_SAVINGS:
                    continue
                if not _is_dead_weight(p, c, ovr, cap_hit):
                    continue
                if r.random() > prob:
                    continue
                try:
                    total, annual, byears, _rows = execute_buyout(
                        league, team, p, season_year=season_year)
                except Exception:
                    continue
                done += 1
                pn = getattr(p, "full_name", getattr(p, "name", "?"))
                tn = getattr(team, "team_name", "?")
                summary["ai_buyouts"].append(
                    {"team": tn, "player": pn, "cap_hit": cap_hit,
                     "savings_y1": int(y1), "annual_dead": int(annual),
                     "years": int(byears)})
                _record_ledger(league, team, p, total, annual, byears, app=app)
                if app is not None:
                    try:
                        app.add_news(
                            f"✂️ {tn} buy out {pn} "
                            f"({_money(cap_hit)} cap hit). "
                            f"Dead cap: {_money(annual)}/yr × {byears}.")
                    except Exception:
                        pass
        except Exception:
            continue

    # --- User club: interactive inbox -----------------------------------
    if user_team is not None and app is not None:
        try:
            _queue_user_buyout_message(league, user_team, app, season_year)
            summary["user_candidates"] = len(
                _candidate_rows(user_team))
        except Exception:
            pass

    return summary


def _candidate_card(p, c, ovr, cap_hit):
    from windows import buyout_schedule
    try:
        total, annual, byears, rows = buyout_schedule(p)
    except Exception:
        return None
    if not rows:
        return None
    y1 = rows[0][2]
    return {
        "player_id": str(getattr(p, "id", "")),
        "name": getattr(p, "full_name", getattr(p, "name", "Unknown")),
        "age": int(getattr(p, "age", 0) or 0),
        "overall": int(ovr),
        "cap_hit": int(cap_hit),
        "years_left": int(getattr(c, "years_remaining", 0) or 0),
        "buyout_cost": int(total),
        "annual_dead": int(annual),
        "dead_years": int(byears),
        "savings_y1": int(y1),
        "dead_weight": bool(_is_dead_weight(p, c, ovr, cap_hit)),
    }


def _queue_user_buyout_message(league, team, app, season_year):
    """Interactive inbox: the user's buyout candidates for the window."""
    from game_classes import EmailMessage

    cards = []
    for (p, c, ovr, cap_hit) in _candidate_rows(team):
        try:
            card = _candidate_card(p, c, ovr, cap_hit)
        except Exception:
            card = None
        if card:
            cards.append(card)
    # Most tempting first: flagged dead weight, then biggest savings.
    cards.sort(key=lambda k: (not k["dead_weight"], -k["savings_y1"]))
    cards = cards[:8]

    lines = [
        "The buyout window is open (June 15-30).",
        "",
    ]
    if not cards:
        lines.append("No strong buyout candidates on your roster — "
                     "nobody's cap hit is dead enough weight to justify "
                     "the dead cap.")
    else:
        lines.append("Your finance team flagged these contracts:")
        for cd in cards:
            flag = " ⚠️ DEAD WEIGHT" if cd["dead_weight"] else ""
            lines.append(
                f"• {cd['name']} (age {cd['age']}, {cd['overall']} ovr): "
                f"{_money(cd['cap_hit'])}/yr × {cd['years_left']} left — "
                f"buyout costs {_money(cd['buyout_cost'])}, dead cap "
                f"{_money(cd['annual_dead'])}/yr × {cd['dead_years']}, "
                f"saves {_money(cd['savings_y1'])} this season.{flag}")
        lines.append("")
        lines.append("Decide on each below. Undecided players stay put — "
                     "the window closes June 30.")
    msg = EmailMessage(
        sender="Assistant GM",
        sender_type="Staff",
        subject=f"Buyout window open — {len(cards)} candidate"
                f"{'s' if len(cards) != 1 else ''} flagged",
        content="\n".join(lines),
        category="Contracts",
        is_important=True,
        requires_response=bool(cards),
        action_type="buyout_window",
        action_data={"cards": cards,
                     "team_id": getattr(team, "id", None),
                     "season_year": season_year,
                     "decided": {}},
    )
    try:
        app.send_email_to_user(msg)
    except Exception:
        pass
