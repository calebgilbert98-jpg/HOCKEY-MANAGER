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


def _resolve_salary_cap(app, gm, blocker, log):
    from salary_cap_system import cap_breakdown
    try:
        from salary_cap_system import _active_roster_hit as _hit
    except Exception:
        def _hit(p):
            c = getattr(p, "contract", None)
            return int(getattr(c, "salary", 0) or 0)

    from game_classes import PlayerPosition
    team = gm.user_team
    demoted = []
    for _ in range(30):  # safety bound
        bd = cap_breakdown(team)
        if not bd["over_cap"]:
            break
        roster = list(getattr(team, "roster", None) or [])
        skaters = [p for p in roster
                   if getattr(p, "primary_position", None)
                   != PlayerPosition.GOALIE]
        goalies = [p for p in roster
                   if getattr(p, "primary_position", None)
                   == PlayerPosition.GOALIE]
        if len(skaters) <= 18 or len(goalies) <= 2:
            raise DayLoopAbort(
                f"salary_cap: cannot shed salary without breaking roster "
                f"minimums ({len(skaters)} skaters, {len(goalies)} goalies)")
        victim = max(skaters, key=_hit)
        roster.remove(victim)
        team.roster = roster
        team.ahl_roster.append(victim)
        demoted.append((getattr(victim, "full_name", "?"), _hit(victim)))
    else:
        raise DayLoopAbort("salary_cap: still over cap after 30 demotions")
    bd = cap_breakdown(team)
    if bd["over_cap"]:
        raise DayLoopAbort(
            f"salary_cap: still over cap (${bd['total'] / 1e6:.2f}M vs "
            f"${bd['cap'] / 1e6:.2f}M) after demotions")
    return (f"demoted {len(demoted)} to AHL until compliant: "
            + ", ".join(f"{n} (${h / 1e6:.2f}M)" for n, h in demoted))


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
            # Season-end transition: end_of_season() opens the playoffs
            # bracket WITHOUT advancing the date; the next simulate_day
            # drives the bracket via _simulate_playoff_day. Not a stall --
            # tolerate a short run of these, then fail loud.
            #
            # Headless gap (B2): in bulk/headless mode the playoffs window
            # may not materialize, so league.playoff_bracket is never
            # created and _playoffs_in_progress() stays False -- every
            # subsequent day re-enters end_of_season and returns without
            # advancing. Workaround: if the season is complete but no live
            # bracket exists, generate one directly so the next day can
            # drive it.
            try:
                _season_complete = bool(app._check_season_complete())
            except Exception:
                _season_complete = False
            if not _season_complete:
                try:
                    from datetime import timedelta as _td
                    _sched_dates = [
                        e.get('date') for e in app.league.schedule
                        if isinstance(e, dict) and e.get('date')]
                    if _sched_dates:
                        _last = max(_sched_dates)
                        if app.current_date > _last + _td(days=7):
                            _season_complete = True
                except Exception:
                    pass
            try:
                _in_playoffs = bool(app._playoffs_in_progress())
            except Exception:
                _in_playoffs = False
            if _season_complete and not _in_playoffs:
                try:
                    from playoff_system import PlayoffBracket
                    _league = getattr(app, "league", None)
                    _bracket = getattr(_league, "playoff_bracket", None)
                    _has = _bracket is not None and any(
                        _bracket.playoff_series.get(r)
                        for r in PlayoffBracket.ROUND_ORDER)
                    if not _has and _league is not None:
                        _bracket = PlayoffBracket(_league)
                        _bracket.generate_playoff_bracket()
                        try:
                            _league.playoff_bracket = _bracket
                        except Exception:
                            pass
                        log(f"  [transition] generated missing playoff "
                            f"bracket headless (season-end stall workaround)")
                    _in_playoffs = bool(app._playoffs_in_progress())
                except Exception as e:
                    log(f"  [transition] bracket workaround failed: {e}")
            _stalls = stats.get("consecutive_stalls", 0) + 1
            stats["consecutive_stalls"] = _stalls
            # Tolerate up to 3 consecutive non-advancing days regardless of
            # playoff state: the season-end transition is the known case,
            # and a true hard stall will exceed 3 and raise below.
            if _stalls <= 3:
                log(f"  [transition] date held at {app.current_date} "
                    f"(stall {_stalls}/3 tolerated; in_playoffs={_in_playoffs})")
            else:
                raise DayLoopAbort(
                    f"{day_label}: STALL -- simulate_day returned without "
                    f"advancing the date or the deadline clock "
                    f"(label={label!r})")
        else:
            stats["consecutive_stalls"] = 0
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
