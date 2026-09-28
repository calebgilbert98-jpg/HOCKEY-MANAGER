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
                cands = sorted(_candidate_rows(team),
                               key=lambda c: c[1])
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

                # Camp cuts: waiver-exempt kids go straight down.
                if camp_cuts:
                    ahl = getattr(team, "ahl_roster", None)
                    if ahl is not None:
                        for p in list(getattr(team, "roster", []) or []):
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
