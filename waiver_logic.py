# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""AI waiver management (BUG-019).

The waiver wire had a working claim pipeline but no supply: AI GMs never
placed anyone on waivers, so the wire only ever held the user's own
discards. This module is the AI GMs' logic, mirroring buyout_window.py:

    process_ai_waivers(league, app=None, rng=None, camp_cuts=False)

runs weekly (Monday, alongside claim processing) and waives players for
the three reasons real GMs use the wire:

  1. Cap compliance -- over the cap (or within $1M of it), waive the
     fringe veteran making too much. Burial (salary minus ~$1.925M
     exemption) is the savings; the cap engine already sheds the hit
     while the player sits on the wire and applies burial on clearance.
  2. AHL shuttle -- roster over 23: waive the bottom-of-roster
     waiver-eligible extras so they can be demoted.
  3. Camp cuts (camp_cuts=True, first week of October) -- trim to 23.
     Waiver-exempt kids are assigned straight to the AHL; eligible
     veterans go through the wire.

Placement mechanics are identical to the user's path (WaiversView):
on_waivers=True, waiver_days=2, appended to the wire. A no-movement
clause blocks placement, franchise pieces (86+) are never waived, and
the June dead month is respected via transaction_windows.

The user's club is never touched -- the user works the wire themselves.
"""

import random

WAIVER_DAYS = 2
ROSTER_LIMIT = 23
FRANCHISE_OVR = 86          # franchise pieces are never waived
CAP_CASUALTY_MIN_HIT = 2_000_000   # burying less than this saves ~nothing
CAP_CASUALTY_MAX_OVR = 79          # ...on a player this good or better
CAP_PRESSURE_BELOW = 1_000_000     # space below this = uncomfortable
MAX_WAIVERS_PER_CALL = 2


# ---------------------------------------------------------------------------
# Small helpers (mirroring buyout_window.py conventions)
# ---------------------------------------------------------------------------

def is_waiver_eligible(player):
    """Waiver eligibility. Parity rule with WaiversView.is_waiver_eligible:
    age 25+ or 160+ NHL games require waivers."""
    try:
        age = int(getattr(player, "age", 0) or 0)
    except Exception:
        age = 0
    try:
        games = int(getattr(player, "nhl_games_played", 0) or 0)
    except Exception:
        games = 0
    return age >= 25 or games >= 160


def _is_nhl_team(team):
    return str(getattr(team, "league_name", "") or "") == "National Hockey League"


def _is_user_team(league, team):
    try:
        if team is getattr(league, "user_team", None):
            return True
    except Exception:
        pass
    try:
        import game_classes as _gc
        return bool(_gc.is_human_managed(team))
    except Exception:
        return bool(getattr(team, "is_user_team", False))


def _team_space(team):
    try:
        from salary_cap_system import cap_breakdown
        return int(cap_breakdown(team).get("space", 0) or 0)
    except Exception:
        return 0


def _gm_trigger_prob(team):
    """Shrewder GMs work the wire more. Defensive: neutral 0.5."""
    try:
        prof = getattr(team, "gm_profile", None)
        abil = float(getattr(prof, "gm_ability01", 0.5) or 0.5)
    except Exception:
        abil = 0.5
    abil = max(0.0, min(1.0, abil))
    return 0.35 + 0.5 * abil


def _wire(league, app):
    """The canonical waiver wire. The app owns it in practice; the league
    carries a fallback so engine-only callers still place visibly."""
    if app is not None:
        wl = getattr(app, "waiver_list", None)
        if wl is not None:
            return wl
    wl = getattr(league, "waiver_list", None)
    if wl is None:
        try:
            league.waiver_list = []
        except Exception:
            return []
        wl = league.waiver_list
    return wl


def _nmc(p):
    c = getattr(p, "contract", None)
    return bool(getattr(c, "no_movement_clause", False))


def _cap_hit(p):
    c = getattr(p, "contract", None)
    try:
        return int(getattr(c, "salary", 0) or 0)
    except Exception:
        return 0


def _ovr(p):
    try:
        return int(p.overall_rating())
    except Exception:
        return 70


def _candidate_rows(team):
    """Waiver-eligible NHL roster players the AI may place, with guards."""
    out = []
    for p in list(getattr(team, "roster", []) or []):
        try:
            if getattr(p, "contract", None) is None:
                continue
            if not is_waiver_eligible(p):
                continue
            if bool(getattr(p, "on_waivers", False)):
                continue
            # Real NHL: an NMC blocks waiver placement (and the AHL
            # assignment that follows) without the player's consent.
            # The AI doesn't ask; it moves on.
            if _nmc(p):
                continue
            ovr = _ovr(p)
            if ovr >= FRANCHISE_OVR:
                continue  # franchise pieces don't hit the wire
            out.append((p, ovr, _cap_hit(p)))
        except Exception:
            continue
    return out


def _years_remaining(p):
    try:
        return int(getattr(getattr(p, "contract", None),
                           "years_remaining", 0) or 0)
    except Exception:
        return 0


def _is_cap_casualty(p, ovr, cap_hit):
    if cap_hit >= CAP_CASUALTY_MIN_HIT and ovr <= CAP_CASUALTY_MAX_OVR:
        return True
    try:
        age = int(getattr(p, "age", 30) or 30)
    except Exception:
        age = 30
    if (age >= 32 and cap_hit >= 4_000_000 and ovr < 82
            and _years_remaining(p) >= 2):
        return True
    return False


def _position_group(p):
    try:
        pos = getattr(p, "primary_position", None)
        name = getattr(pos, "name", str(pos))
    except Exception:
        name = ""
    return "G" if "GOALIE" in str(name) else ("D" if "DEFENSE" in str(name)
                                             else "F")


def _place_on_wire(league, app, wire, team, player, reason):
    player.on_waivers = True
    player.waiver_days = WAIVER_DAYS
    if player not in wire:
        wire.append(player)
    pn = getattr(player, "full_name", getattr(player, "name", "?"))
    tn = getattr(team, "team_name", "?")
    story = f"📋 {tn} place {pn} on waivers ({reason})."
    if app is not None:
        try:
            app.add_news(story)
        except Exception:
            pass
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app) if app is not None else None
        if led is not None:
            led.record(
                kind="waiver", teams=[tn], players=[pn], weight=25,
                season=int(getattr(league, "season_year", 2026) or 2026),
                text=f"{tn} place {pn} on waivers ({reason}).",
                facts={"player": pn, "team": tn, "reason": reason})
    except Exception:
        pass
    return {"team": tn, "player": pn, "reason": reason}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_ai_waivers(league, app=None, rng=None, camp_cuts=False):
    """Weekly AI waiver management. Returns a summary dict.

    AI clubs only; the user's club is never touched. camp_cuts=True trims
    every AI roster to 23 (early October): exempt kids go straight to the
    AHL, eligible veterans go through the wire.
    """
    r = rng or random.Random()
    summary = {"waived": [], "assigned": [], "camp_cuts": bool(camp_cuts)}

    # The wire is closed in the June dead month -- one rulebook.
    try:
        import transaction_windows as _tw
        _d = getattr(app, "current_date", None) if app is not None else None
        _ok, _ = _tw.check_window("waiver_place", _d)
        if not _ok:
            return summary
    except Exception:
        pass

    wire = _wire(league, app)
    try:
        from salary_cap_system import burial_exemption as _bex
        _bury = int(_bex(getattr(league, "season_year", None)))
    except Exception:
        _bury = 1_925_000

    for team in list(getattr(league, "teams", []) or []):
        try:
            if not _is_nhl_team(team):
                continue
            if _is_user_team(league, team):
                continue
            prob = _gm_trigger_prob(team)
            done = 0

            roster = list(getattr(team, "roster", []) or [])

            # --- 1. Cap compliance: waive the fringe making too much ------
            try:
                space = _team_space(team)
            except Exception:
                space = 0
            if space < CAP_PRESSURE_BELOW and done < MAX_WAIVERS_PER_CALL:
                cands = []
                for (p, ovr, hit) in _candidate_rows(team):
                    if not _is_cap_casualty(p, ovr, hit):
                        continue
                    # Savings if he clears and is buried.
                    cands.append((hit - _bury, p, ovr, hit))
                cands.sort(key=lambda c: c[0], reverse=True)
                for (_save, p, ovr, hit) in cands:
                    if done >= MAX_WAIVERS_PER_CALL:
                        break
                    if _save < 500_000:
                        continue
                    if r.random() > prob:
                        continue
                    summary["waived"].append(
                        _place_on_wire(league, app, wire, team, p,
                                       "cap compliance"))
                    done += 1
                    space += _save  # the wire shed; re-check pressure
                    if space >= CAP_PRESSURE_BELOW:
                        break

            # --- 2/3. Roster trim: AHL shuttle / camp cuts -----------------
            # Re-read the roster; step 1 may have placed players.
            roster = [pl for pl in list(getattr(team, "roster", []) or [])
                      if not bool(getattr(pl, "on_waivers", False))]
            over = len(roster) - ROSTER_LIMIT
            if over > 0 and done < MAX_WAIVERS_PER_CALL:
                reason = ("camp cut" if camp_cuts else "AHL assignment")
                # Bottom of the roster first; never strand the crease.
                # Camp cuts read the just-finished training camp: a bad
                # camp (low camp_avg) jumps the queue, a great camp saves
                # a bubble player -- EHM managers cut on camp form.
                def _cut_key(c):
                    p = c[0]
                    try:
                        camp = float(getattr(p, "camp_avg", 0.0) or 0.0)
                    except Exception:
                        camp = 0.0
                    if camp_cuts and camp > 0:
                        return (camp, c[1])
                    return (99.0, c[1])
                cands = sorted(_candidate_rows(team), key=_cut_key)
                goalies = [pl for pl in roster
                           if _position_group(pl) == "G"]
                for (p, ovr, hit) in cands:
                    if over <= 0 or done >= MAX_WAIVERS_PER_CALL:
                        break
                    if (_position_group(p) == "G" and len(goalies) <= 2
                            and p in goalies):
                        continue  # never waive into one goalie
                    if r.random() > prob:
                        continue
                    summary["waived"].append(
                        _place_on_wire(league, app, wire, team, p, reason))
                    done += 1
                    over -= 1
                    if p in goalies:
                        goalies.remove(p)

                # Camp cuts: waiver-exempt kids go straight down, worst
                # camp first.
                if camp_cuts:
                    ahl = getattr(team, "ahl_roster", None)
                    if ahl is not None:
                        def _kid_key(pl):
                            try:
                                return float(getattr(pl, "camp_avg", 0.0)
                                             or 0.0)
                            except Exception:
                                return 0.0
                        _kids = sorted(
                            list(getattr(team, "roster", []) or []),
                            key=_kid_key)
                        for p in _kids:
                            if len([pl for pl in
                                     list(getattr(team, "roster", []) or [])
                                     if not bool(getattr(
                                         pl, "on_waivers", False))]) \
                                    <= ROSTER_LIMIT:
                                break
                            try:
                                if getattr(p, "contract", None) is None:
                                    continue
                                if is_waiver_eligible(p):
                                    continue
                                if bool(getattr(p, "on_waivers", False)):
                                    continue
                                if _nmc(p):
                                    continue
                            except Exception:
                                continue
                            try:
                                team.roster.remove(p)
                                ahl.append(p)
                                try:
                                    import ahl_system as _ahl
                                    _ahl.stamp_ahl_assignment(p)
                                except Exception:
                                    pass
                                pn = getattr(p, "full_name",
                                             getattr(p, "name", "?"))
                                summary["assigned"].append(
                                    {"team": getattr(team, "team_name", "?"),
                                     "player": pn})
                            except Exception:
                                continue
        except Exception:
            continue

    return summary


# ---------------------------------------------------------------------------
# NHL waiver priority (claim order) -- CBA Article 13 style
# ---------------------------------------------------------------------------
# The real rule: when several clubs claim the same player, the club with
# the lowest points percentage gets him. From opening day through
# November 1 the order is set by the PREVIOUS season's final standings;
# from November 1 on it is set by CURRENT standings. A club that
# successfully claims a player drops to the bottom of the order (it has
# used its priority).
#
# process_waivers() in main.py consumes this; the WaiversView wire tab
# displays the order and the user's rank.

NOVEMBER_CUTOFF_MONTH = 11
NOVEMBER_CUTOFF_DAY = 1


def snapshot_final_standings(league):
    """Bank the season's final standings before they are reset.

    Call at the top of League.end_of_season() (game_classes.py), before
    initialize_standings() wipes the table. Old-save safe: plain attrs.
    """
    try:
        table = getattr(league, "standings", None) or {}
        snap = {}
        for name, row in table.items():
            try:
                pts = int((row or {}).get("Points", 0) or 0)
                gp = (int((row or {}).get("W", 0) or 0)
                      + int((row or {}).get("L", 0) or 0)
                      + int((row or {}).get("OTL", 0) or 0))
            except Exception:
                pts, gp = 0, 0
            snap[str(name)] = {"points": pts, "games": gp}
        league.previous_season_standings = snap
        league.previous_season_label = str(
            getattr(league, "season_year", "") or "")
    except Exception:
        pass


def _priority_basis(league, on_date):
    """('final'|'current', basis_key). Pre-Nov 1 -> previous final table."""
    try:
        y = int(getattr(on_date, "year", 0) or 0)
        m = int(getattr(on_date, "month", 0) or 0)
    except Exception:
        return "current", "current"
    season_start_year = y if m >= 7 else y - 1
    try:
        from datetime import date as _date
        cutoff = _date(season_start_year, NOVEMBER_CUTOFF_MONTH,
                       NOVEMBER_CUTOFF_DAY)
        if on_date < cutoff:
            label = str(getattr(league, "previous_season_label", "") or "")
            return "final", "final:%s" % (label or season_start_year - 1)
    except Exception:
        pass
    return "current", "current:%d" % season_start_year


def _team_points_pct(league, team, basis):
    name = str(getattr(team, "team_name", "") or "")
    row = None
    if basis == "final":
        snap = getattr(league, "previous_season_standings", None) or {}
        row = snap.get(name)
    if row is None:
        table = getattr(league, "standings", None) or {}
        d = table.get(name) or {}
        try:
            row = {"points": int(d.get("Points", 0) or 0),
                   "games": (int(d.get("W", 0) or 0)
                             + int(d.get("L", 0) or 0)
                             + int(d.get("OTL", 0) or 0))}
        except Exception:
            row = {"points": 0, "games": 0}
    pts = row.get("points", 0)
    gp = row.get("games", 0)
    pct = (pts / (2.0 * gp)) if gp else 0.0
    return pct, pts, name


def waiver_priority_order(league, on_date):
    """Teams in waiver-claim priority: lowest points percentage first.

    Successful claimants since the last basis change sit at the bottom
    (they have used their priority), in the order they claimed.
    """
    try:
        teams = [t for t in (getattr(league, "teams", None) or [])
                 if _is_nhl_team(t)]
    except Exception:
        return []
    basis, basis_key = _priority_basis(league, on_date)
    # Basis flip (season rollover / Nov 1) resets the used-priority list.
    try:
        if getattr(league, "_waiver_priority_basis_key", None) != basis_key:
            league._waiver_priority_basis_key = basis_key
            league._waiver_claim_demotion = []
    except Exception:
        pass
    ranked = sorted(teams,
                    key=lambda t: (_team_points_pct(league, t, basis)[0],
                                   _team_points_pct(league, t, basis)[1],
                                   str(getattr(t, "team_name", ""))))
    try:
        demoted = [n for n in
                   (getattr(league, "_waiver_claim_demotion", None) or [])
                   if isinstance(n, str)]
    except Exception:
        demoted = []
    if demoted:
        demote_set = set(demoted)
        head = [t for t in ranked
                if str(getattr(t, "team_name", "")) not in demote_set]
        # Claim order preserved at the tail.
        tail = []
        for n in demoted:
            hit = next((t for t in ranked
                        if str(getattr(t, "team_name", "")) == n), None)
            if hit is not None and hit not in tail:
                tail.append(hit)
        ranked = head + tail
    return ranked


def waiver_priority_rank(league, team, on_date):
    """1-based waiver priority rank of a team (None if not ranked)."""
    try:
        order = waiver_priority_order(league, on_date)
        name = str(getattr(team, "team_name", "") or "")
        for i, t in enumerate(order):
            if str(getattr(t, "team_name", "")) == name:
                return i + 1
    except Exception:
        pass
    return None


def waiver_priority_basis_label(league, on_date):
    """Human string for the wire screen, e.g. '2027-28 final standings'."""
    basis, _key = _priority_basis(league, on_date)
    if basis == "final":
        label = str(getattr(league, "previous_season_label", "") or "").strip()
        if label:
            return "%s final standings" % label
        return "last season's final standings"
    return "current standings"


def note_waiver_claim(league, team):
    """Record a successful claim: the club drops to the bottom of the order."""
    try:
        name = str(getattr(team, "team_name", "") or "")
        if not name:
            return
        cur = getattr(league, "_waiver_claim_demotion", None)
        if not isinstance(cur, list):
            cur = []
            league._waiver_claim_demotion = cur
        if name in cur:
            cur.remove(name)
        cur.append(name)
    except Exception:
        pass
