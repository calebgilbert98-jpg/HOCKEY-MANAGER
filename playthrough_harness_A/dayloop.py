# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Drive the real day-processing path headless.

advance_days(gm, n) calls HockeyManagerGUI.simulate_day once per day --
the same entry point the Continue button uses -- with a deterministic
blocker policy:

  fantasy_draft    -> complete via the all-AI FantasyDraftManager draft
  salary_cap       -> demote highest cap-hit skaters to the AHL until
                      compliant (keeps >=18 skaters, >=2 goalies on the
                      NHL roster)
  captaincy_choice -> seniority policy: most-tenured skater gets the C,
                      next two get the As (never a goalie; validated with
                      the real _validate_captaincy_pick)
  season_meeting   -> resolve with the AI-equivalent mandate (the same
                      mandate structure + downstream wiring as the user
                      path, via resolve_ai_season_meeting)
  <registry ids>   -> known BLOCKS_ADVANCE/PAUSES_DAY ids from the
                      pending-items registry: no generic policy exists;
                      fail closed with a clear abort marker.

Every blocker and its resolution is logged. Unknown blockers abort the
run explicitly -- days are never silently skipped. Trade-deadline clock
ticks, playoff days, season end and offseason rollover all happen inside
simulate_day; the loop just keeps pressing Continue.
"""
import time
import traceback
from collections import Counter


class DayLoopAbort(Exception):
    """Explicit abort: the run cannot continue deterministically."""


def _nhl_teams(league):
    return [t for t in getattr(league, "teams", [])
            if getattr(t, "league_name", "") == "National Hockey League"]


def _unsigned_players(team):
    """Roster players on expired deals (years_remaining == 0)."""
    out = []
    for p in (getattr(team, "roster", None) or []):
        try:
            c = getattr(p, "contract", None)
            if c is not None and int(getattr(c, "years_remaining", 1) or 0) == 0:
                out.append(p)
        except Exception:
            continue
    return out


def _resolve_unsigned_contracts(team, league, log):
    """Offseason unsigned-contract resolution (harness GM policy, 2026-10-01).

    Root cause of the S5 salary_cap dead-end: the harness never re-signed or
    released expiring user-team contracts. AI clubs get AI extension planning
    (ai_team_management.process_daily_decisions skips human-managed teams by
    design -- a human uses the Negotiate Extension UI). Twelve expired deals
    ($31.36M) piled up on Toronto's roster, still counting against the cap on
    2031-07-05, manufacturing a $0.17M "overage" out of thin air. The other 30
    clubs had 0-2 such players; the 2,855-player UFA pool shows the July-1
    transition ran league-wide.

    AI-equivalent policy per unsigned player:
      keep = rfa_system._is_core_keep  (ovr >= 82 or (age <= 24 and ovr >= 78),
             the game's canonical core-keep definition, used to reserve cap)
      keep -> extension at the AI's estimated salary
              (AITeamManager._estimate_player_salary, deterministic) with a
              deterministic term (midpoint of _determine_contract_length's
              bands: 7/3/5/2 -- the AI itself rolls inside those bands)
      walk -> released to the FA pool (team_name='Free Agent'), mirroring the
              July-1 UFA reality and what AI clubs' unwanted players get
    Returns (kept, walked): lists of (name, salary).
    """
    unsigned = _unsigned_players(team)
    if not unsigned:
        return [], []
    try:
        from rfa_system import _is_core_keep as _keep_rule
    except Exception:
        def _keep_rule(p):
            try:
                ovr = float(p.overall_rating())
            except Exception:
                ovr = 70.0
            return ovr >= 82 or (int(getattr(p, "age", 99) or 99) <= 24
                                 and ovr >= 78)
    try:
        from ai_team_management import AITeamManager
        _mgr = AITeamManager()
        _mgr._cap_system = None  # -> DEFAULT_CAP, deterministic estimate
    except Exception:
        _mgr = None

    def _term_for(p):
        try:
            age = int(getattr(p, "age", 30) or 30)
        except Exception:
            age = 30
        try:
            from game_classes import to_100_scale
            ovr100 = int(to_100_scale(p.overall_rating()))
        except Exception:
            ovr100 = 75
        if age <= 24 and ovr100 >= 90:
            return 7
        if age < 26:
            return 3
        if age < 30:
            return 5
        return 2

    fa_pool = None
    if league is not None:
        fa_pool = getattr(league, "free_agents", None)
    kept, walked = [], []
    for p in unsigned:
        name = getattr(p, "full_name", "?")
        try:
            keep = bool(_keep_rule(p))
        except Exception:
            keep = False
        if keep:
            try:
                salary = int(_mgr._estimate_player_salary(p)) if _mgr \
                    else int(getattr(p.contract, "salary", 0) or 0)
            except Exception:
                salary = int(getattr(getattr(p, "contract", None),
                                     "salary", 0) or 0)
            term = _term_for(p)
            try:
                p.contract.salary = salary
                p.contract.years_remaining = term
            except Exception:
                continue
            kept.append((name, salary))
            log(f"  [unsigned] re-signed {name}: "
                f"${salary / 1e6:.2f}M x {term}y (AI-equivalent extension)")
        else:
            try:
                team.roster.remove(p)
            except Exception:
                continue
            try:
                p.team_name = "Free Agent"
                p.former_team = getattr(team, "team_name", "")
            except Exception:
                pass
            if isinstance(fa_pool, list):
                fa_pool.append(p)
            walked.append((name, int(getattr(getattr(p, "contract", None),
                                            "salary", 0) or 0)))
            log(f"  [unsigned] {name} walks to UFA "
                f"(${(walked[-1][1]) / 1e6:.2f}M off the books)")
    return kept, walked


def _resolve_salary_cap(app, gm, blocker, log):
    from salary_cap_system import cap_breakdown, compliance_charge
    try:
        from salary_cap_system import (_active_roster_hit as _hit,
                                       minor_league_cap_charge as _min_hit)
    except Exception:
        def _hit(p):
            c = getattr(p, "contract", None)
            return int(getattr(c, "salary", 0) or 0)

        def _min_hit(p):
            return 0
    try:
        from salary_cap_system import _expected_wire_charge as _wire_hit
    except Exception:
        _wire_hit = _min_hit

    from game_classes import PlayerPosition
    team = gm.user_team
    notes = []

    # Step 1 (2026-10-01): resolve unsigned (expired-contract) players FIRST.
    # They are the usual root cause of a phantom overage -- S5's $0.17M
    # "overage" was $31.36M of unresolved expired deals. A real GM told
    # "you're over the cap" checks who is actually counting before shedding.
    kept, walked = _resolve_unsigned_contracts(
        team, getattr(gm, "league", None), log)
    if kept or walked:
        notes.append(f"resolved {len(kept)} re-signed / {len(walked)} walked "
                     f"unsigned contracts")

    # Step 2: demote by ACTUAL cap shed, under the game's real rulebook.
    # The old policy (highest-hit skater only, hard 18-skater floor) was
    # stricter than anything the game enforces -- there is no roster-minimum
    # day gate -- and blind to the real math: two-way deals demote to $0,
    # sub-exemption one-way deals demote to $0, goalies are demotable too,
    # and NMC players can never be demoted (the old policy's first victim
    # would have been $12.85M NMC Griffin Morin -- an illegal move).
    demoted = []
    wired = []
    floor_warned = False

    def _compliant():
        try:
            bd = cap_breakdown(team)
            if not bd["over_cap"]:
                return True
            # D45: an in-flight corrective waive counts at its expected
            # post-clearing charge -- the wire clock is doing its job.
            return int(compliance_charge(team)) <= int(bd["cap"])
        except Exception:
            return False

    def _counts():
        roster = list(getattr(team, "roster", None) or [])
        sk = [p for p in roster
              if getattr(p, "primary_position", None) != PlayerPosition.GOALIE]
        gl = [p for p in roster
              if getattr(p, "primary_position", None) == PlayerPosition.GOALIE]
        return roster, sk, gl

    for _ in range(30):  # safety bound
        if _compliant():
            break
        roster, skaters, goalies = _counts()
        cands = []
        for p in roster:
            try:
                c = getattr(p, "contract", None)
                if c is not None and bool(getattr(c, "no_movement_clause",
                                                 False)):
                    continue  # NMC: cannot be demoted without consent
                shed = int(_hit(p)) - int(_min_hit(p))
                if shed <= 0:
                    continue
            except Exception:
                continue
            is_g = getattr(p, "primary_position", None) == PlayerPosition.GOALIE
            cands.append((shed, is_g, p))
        if not cands:
            raise DayLoopAbort(
                "salary_cap: no demotable contract sheds cap "
                f"({len(skaters)} skaters, {len(goalies)} goalies; "
                "rest are NMC or shed nothing)")
        # Biggest real shed first; prefer waiver-exempt (quiet) and prefer
        # keeping >=18 skaters / >=2 goalies, but that floor is a preference,
        # not a hard abort -- the game enforces no roster-minimum day gate.
        # Hard floor: never strand the club with zero goalies.
        cands.sort(key=lambda t: t[0], reverse=True)

        def _waiver_free(p):
            # Same rule as main._player_needs_waivers (25+ or 160+ NHL games
            # must clear the wire); replicated here to avoid importing the
            # GUI module headless.
            try:
                return not (int(getattr(p, "age", 0) or 0) >= 25 or int(
                    getattr(p, "nhl_games_played", 0) or 0) >= 160)
            except Exception:
                return False

        pick = None
        for prefer_floor in (True, False):
            for shed, is_g, p in cands:
                if is_g and len(goalies) <= 1:
                    continue
                if prefer_floor:
                    if not is_g and len(skaters) <= 18:
                        continue
                    if is_g and len(goalies) <= 2:
                        continue
                pick = (shed, is_g, p)
                break
            if pick is not None:
                break
        if pick is None:
            raise DayLoopAbort(
                "salary_cap: cannot shed without stranding zero goalies")
        shed, is_g, victim = pick
        below_floor = (not is_g and len(skaters) <= 18) or (
            is_g and len(goalies) <= 2)
        if _waiver_free(victim):
            team.roster.remove(victim)
            team.ahl_roster.append(victim)
            demoted.append((getattr(victim, "full_name", "?"), shed))
        else:
            # Corrective waive, mirroring main.send_to_ahl: 2 days on the
            # wire, then clearance auto-assigns to the AHL (burial rule).
            # compliance_charge() stands the blocker down meanwhile (D45).
            try:
                victim.on_waivers = True
                victim.waiver_days = 2
                wl = getattr(app, "waiver_list", None)
                if isinstance(wl, list) and victim not in wl:
                    wl.append(victim)
                wired.append((getattr(victim, "full_name", "?"),
                              int(_hit(victim)) - int(_wire_hit(victim))))
            except Exception:
                team.roster.remove(victim)
                team.ahl_roster.append(victim)
                demoted.append((getattr(victim, "full_name", "?"), shed))
        if below_floor and not floor_warned:
            notes.append("below the 18-skater/2-goalie preference "
                         "(game permits it; no roster-minimum day gate)")
            floor_warned = True
        roster, skaters, goalies = _counts()
    else:
        raise DayLoopAbort("salary_cap: still over cap after 30 moves")
    if not _compliant():
        bd = cap_breakdown(team)
        raise DayLoopAbort(
            f"salary_cap: still over cap (${bd['total'] / 1e6:.2f}M vs "
            f"${bd['cap'] / 1e6:.2f}M) after moves")
    parts = []
    if notes:
        parts.append("; ".join(notes))
    if demoted:
        parts.append("demoted " + ", ".join(
            f"{n} (shed ${h / 1e6:.2f}M)" for n, h in demoted))
    if wired:
        parts.append("waived " + ", ".join(
            f"{n} (sheds ${h / 1e6:.2f}M on clearing)" for n, h in wired))
    return "; ".join(parts) if parts else "already compliant"


def _resolve_captaincy(app, gm, blocker, log):
    from .boot import _resolve_captaincy_by_seniority
    letters = _resolve_captaincy_by_seniority(gm, gm.user_team)
    return (f"seniority pick persisted: C={letters['C']}, "
            f"A={letters['A'][0]}, {letters['A'][1]}")


def _resolve_season_meeting(app, gm, blocker, log):
    from coach_season_meeting import (resolve_ai_season_meeting,
                                      is_meeting_pending)
    team = gm.user_team
    season_year = getattr(gm.league, "season_year", None)
    mandate = resolve_ai_season_meeting(team, gm.league, season_year)
    if is_meeting_pending(team):
        raise DayLoopAbort(
            "season_meeting: AI-equivalent resolution did not clear the "
            "pending flag")
    exp = (mandate or {}).get("expectation", "?")
    return f"resolved with AI-equivalent mandate (expectation={exp})"


def _resolve_fantasy_draft(app, gm, blocker, log):
    from .boot import _auto_fantasy_draft
    _auto_fantasy_draft(app, gm, log)
    return "completed via all-AI FantasyDraftManager draft"


def _resolve_salary_floor(app, gm, blocker, log):
    from ai_team_management import AITeamManager
    from salary_cap_system import total_cap_charge, SALARY_CAP_FLOOR
    league = gm.league
    team = gm.user_team
    mgr = AITeamManager()
    mgr._league_ref = league
    try:
        made = mgr._enforce_salary_floor(
            team, getattr(league, "free_agents", []), app.current_date)
    except Exception as e:
        raise DayLoopAbort(f"salary_floor: AI compliance error: {e!r}")
    after = total_cap_charge(team)
    if after < int(SALARY_CAP_FLOOR):
        raise DayLoopAbort(
            f"salary_floor: still ${after / 1e6:.2f}M vs "
            f"${int(SALARY_CAP_FLOOR) / 1e6:.2f}M floor after "
            f"{made} signing(s)")
    return (f"AI-equivalent floor compliance: {made} FA signing(s), "
            f"payroll ${after / 1e6:.2f}M")


def _resolve_dress_minimum(app, gm, blocker, log):
    """BUG-002: summon emergency fillers -- the blocker's own remedy.

    The roster-limits gate fires correctly; headless just had no policy to
    answer it. Mirrors what the UI's Summon button does.
    """
    from roster_limits import summon_emergency_fillers, lineup_shortfall
    team = gm.user_team
    sk_need, go_need = lineup_shortfall(team)
    summoned = summon_emergency_fillers(team)
    sk_left, go_left = lineup_shortfall(team)
    if sk_left > 0 or go_left > 0:
        raise DayLoopAbort(
            f"dress_minimum: summon covered {len(summoned)} but shortfall "
            f"remains ({sk_left} skaters, {go_left} goalies)")
    names = ", ".join(getattr(p, "full_name", "?") for p in summoned)
    return (f"summoned {len(summoned)} emergency filler(s) "
            f"(needed {sk_need} skaters, {go_need} goalies): {names}")


_RESOLVERS = {
    "fantasy_draft": _resolve_fantasy_draft,
    "salary_cap": _resolve_salary_cap,
    "salary_floor": _resolve_salary_floor,
    "captaincy_choice": _resolve_captaincy,
    "season_meeting": _resolve_season_meeting,
    "dress_minimum": _resolve_dress_minimum,
}


class BlockerPolicy:
    """Deterministic blocker resolution with full logging."""

    def __init__(self, log=print):
        self.log = log
        self.resolved = Counter()
        self._seen_resumable = set()

    def resolve(self, app, blocker):
        bid = blocker.get("id", "?")
        title = blocker.get("title", "")
        resolver = _RESOLVERS.get(bid)
        if resolver is None:
            raise DayLoopAbort(
                f"no policy for blocker id={bid!r} title={title!r} "
                f"detail={blocker.get('detail', '')!r} -- failing closed")
        how = resolver(app, app.game_manager, blocker, self.log)
        self.resolved[bid] += 1
        self.log(f"  [blocker] {bid}: {how}")
        return how

    def note_resumable(self, app):
        """Log RESUMABLE registry items (parked, never block the day)."""
        try:
            from popup_system import get_pending_items, RESUMABLE
            items = get_pending_items(app, kinds=(RESUMABLE,))
        except Exception:
            return
        for it in items or []:
            iid = it.get("id", "?")
            if iid not in self._seen_resumable:
                self._seen_resumable.add(iid)
                self.log(f"  [parked] resumable item: {iid} -- "
                         f"{it.get('title', '')}")


def _deadline_clock(gm):
    try:
        from trade_deadline_manager import get_deadline_manager
        store = get_deadline_manager(gm)._clock_store()
        return (store.get("minutes"), bool(store.get("expired")))
    except Exception:
        return None


def advance_days(gm, n, policy=None, tap=None, log=print,
                 max_blocker_rounds=10, daily_hook=None):
    """Advance n days through the real simulate_day path.

    Returns a stats dict: days_requested/advanced, deadline_ticks,
    blockers_resolved, per_day_seconds, games_simmed, stalled/aborted info.
    Raises DayLoopAbort on any day that cannot advance deterministically.

    daily_hook(gm, day_index): optional callable run once per simulated
        day after the tap drain (e.g. daily GM rituals like team talks).
        Exceptions are logged, never fatal.
    """
    app = gm.app
    if app is None:
        raise DayLoopAbort("gm.app is None -- boot via "
                           "playthrough_harness.boot.new_game")
    policy = policy or BlockerPolicy(log=log)
    stats = {
        "days_requested": n,
        "days_advanced": 0,
        "deadline_ticks": 0,
        "blockers_resolved": Counter(),
        "per_day_seconds": [],
        "games_simmed": 0,
        "start_date": str(app.current_date),
        "end_date": None,
    }
    games_before = len(getattr(app, "game_results", None) or [])

    for i in range(n):
        day_label = f"day {i + 1}/{n} ({app.current_date})"
        # --- blockers first: resolve until the day is free to advance ---
        label, blockers = app.get_continue_state()
        rounds = 0
        while blockers:
            rounds += 1
            if rounds > max_blocker_rounds:
                raise DayLoopAbort(
                    f"{day_label}: blockers did not clear after "
                    f"{max_blocker_rounds} resolution rounds: "
                    f"{[b.get('id') for b in blockers]}")
            log(f"{day_label}: {len(blockers)} blocker(s) "
                f"[{', '.join(b.get('id', '?') for b in blockers)}]")
            for b in blockers:
                policy.resolve(app, b)
            label, blockers = app.get_continue_state()
        policy.note_resumable(app)

        on_deadline_clock = label.startswith("+30m") or label == "Deadline Day"
        clock_before = _deadline_clock(gm) if on_deadline_clock else None
        date_before = app.current_date
        # Snapshot the season-end guard + playoff bracket so the stall
        # detector can recognise the legitimate season-end transition:
        # end_of_season() opens the playoff bracket without advancing the
        # date (by design -- the user sees the summary / bracket, then the
        # next Next Day runs _simulate_playoff_day). That single no-advance
        # day is progress, not a stall.
        _handled_before = getattr(app, "_season_end_handled_year", None)
        _bracket_before = getattr(getattr(app, "league", None),
                                  "playoff_bracket", None) is not None

        t0 = time.time()
        try:
            app.simulate_day()
        except Exception:
            log(f"ABORT {day_label}: simulate_day raised:\n"
                + traceback.format_exc())
            raise DayLoopAbort(
                f"{day_label}: simulate_day raised -- see log for traceback")
        dt = time.time() - t0
        stats["per_day_seconds"].append(dt)

        # --- stall detection: the day must move the date or the clock ---
        clock_after = _deadline_clock(gm) if on_deadline_clock else None
        date_moved = app.current_date != date_before
        clock_moved = (clock_before is not None and clock_after is not None
                       and clock_after != clock_before)
        if not date_moved and not clock_moved:
            _handled_after = getattr(app, "_season_end_handled_year", None)
            _bracket_after = getattr(getattr(app, "league", None),
                                     "playoff_bracket", None) is not None
            _season_transition = (_handled_after != _handled_before
                                  or (_bracket_after and not _bracket_before))
            if _season_transition:
                # Legitimate: end_of_season() just ran (season summary +
                # playoff bracket opened). The next day continues into the
                # playoffs. Not a stall.
                log(f"{day_label}: season-end transition (no date advance; "
                    f"end_of_season ran, bracket={_bracket_after}) -- "
                    f"continuing")
                stats.setdefault("season_transitions", 0)
                stats["season_transitions"] += 1
                # Headless gap (B2, ported from the Sim B harness): in
                # bulk/headless mode the playoff bracket may never
                # materialize -- end_of_season's open_playoffs_window path
                # needs a real GUI window, and the re-entry branch then
                # skips the playoffs entirely (season 2 ran with zero
                # playoff games: the date jumped straight to the
                # offseason). If the season is complete but no live
                # bracket exists anywhere the game reads it, generate one
                # directly so the following days drive the real
                # _simulate_playoff_day path instead of skipping the
                # tournament.
                if not _bracket_after:
                    try:
                        _complete = bool(app._check_season_complete())
                    except Exception:
                        _complete = False
                    if _complete:
                        try:
                            from playoff_system import PlayoffBracket
                            _has_real = False
                            for _o in (getattr(gm, "league", None),
                                       getattr(app, "league", None),
                                       app, gm):
                                try:
                                    _b = getattr(_o, "playoff_bracket", None)
                                    if _b is not None and any(
                                            _b.playoff_series.get(r)
                                            for r in
                                            PlayoffBracket.ROUND_ORDER):
                                        _has_real = True
                                        break
                                except Exception:
                                    pass
                            if not _has_real:
                                # BUG-REVIEW-002 safety net: the playoffs view
                                # may still hold LAST season's decided bracket
                                # (open_windows is never torn down headless).
                                # _playoffs_complete() trusts the view first,
                                # so a stale decided bracket would skip this
                                # season's tournament. A decided bracket on
                                # the view with no real bracket on the league
                                # is stale by construction (_generate_bracket
                                # always attaches to the league).
                                try:
                                    _w = (getattr(app, "open_windows", None)
                                          or {}).get("playoffs")
                                    _wb = (getattr(_w, "playoff_bracket", None)
                                           if _w is not None else None)
                                    if (_wb is not None and getattr(
                                            _wb, "stanley_cup_champion",
                                            None) is not None):
                                        _w.playoff_bracket = None
                                        log("  [transition] cleared stale "
                                            "decided playoff bracket from "
                                            "playoffs view (BUG-REVIEW-002)")
                                except Exception:
                                    pass
                                _league = (getattr(gm, "league", None)
                                           or getattr(app, "league", None))
                                _nb = PlayoffBracket(_league)
                                _nb.generate_playoff_bracket()
                                _seen_ids = set()
                                for _o in (getattr(gm, "league", None),
                                           getattr(app, "league", None),
                                           app, gm):
                                    if _o is None or id(_o) in _seen_ids:
                                        continue
                                    _seen_ids.add(id(_o))
                                    try:
                                        _o.playoff_bracket = _nb
                                    except Exception:
                                        pass
                                log("  [transition] generated missing "
                                    "playoff bracket headless "
                                    "(B2 workaround)")
                        except Exception as e:
                            log(f"  [transition] bracket generation "
                                f"failed: {e}")
            else:
                raise DayLoopAbort(
                    f"{day_label}: STALL -- simulate_day returned without "
                    f"advancing the date or the deadline clock "
                    f"(label={label!r})")
        if on_deadline_clock and clock_moved and not date_moved:
            stats["deadline_ticks"] += 1
        if date_moved:
            stats["days_advanced"] += 1

        if tap is not None:
            try:
                tap.drain(app)
            except Exception as e:
                log(f"{day_label}: narrative tap failed (non-fatal): {e}")

        if daily_hook is not None:
            try:
                daily_hook(gm, i)
            except Exception as e:
                log(f"{day_label}: daily_hook failed (non-fatal): {e}")

        if (i + 1) % 10 == 0 or i == n - 1:
            log(f"{day_label}: done in {dt:.2f}s "
                f"(date now {app.current_date})")

    stats["end_date"] = str(app.current_date)
    stats["games_simmed"] = (len(getattr(app, "game_results", None) or [])
                             - games_before)
    stats["blockers_resolved"] = dict(policy.resolved)
    return stats
