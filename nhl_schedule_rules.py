# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""NHL schedule rules: the fundamental enforcer for realistic scheduling.

This module is the single source of truth for what a realistic NHL
schedule looks like. It defines the league's real-life structural rules
as named constants, validates any generated schedule against them, and
repairs hard violations -- without ever breaking the game.

Design contract (read before touching):
- NEVER raises. Every public entry point catches its own errors and
  degrades to "report, don't block".
- NEVER deletes games. Repair moves games to new dates; it never drops
  them. An 82-game slate with a soft-rule miss beats a short slate.
- HARD rules (completeness, no 3-in-a-row, no doubleheaders, season
  window) get repair attempts. SOFT rules (back-to-back counts,
  home/away balance) are reported, never "fixed" -- chasing them with
  moves risks breaking hard rules.
- Completeness outranks everything: if a repair can't place a game
  without violating a hard rule, the game stays and the violation is
  logged CRITICAL. A playable schedule always comes out.
"""

from collections import defaultdict
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Real-life NHL structural rules.
# ---------------------------------------------------------------------------

GAMES_PER_TEAM = 82
LEAGUE_TEAMS = 32

# A team never plays 3 days in a row in the real NHL. This is the hardest
# immersion rule in the scheduler: a 3-in-3 on the calendar reads as broken.
MAX_CONSECUTIVE_GAME_DAYS = 2

# Real NHL back-to-back load per team per season. Target band is where the
# league actually lands; the report band is the wider "don't bother Chris"
# range. Below/above the report band gets flagged, never auto-fixed.
BACK_TO_BACK_TARGET = (11, 16)
BACK_TO_BACK_REPORT_BAND = (8, 20)

# No team plays twice on the same day. Ever.
MAX_GAMES_PER_TEAM_PER_DAY = 1

# Sanity: the league never schedules more than 16 games (32 teams) a day.
MAX_GAMES_PER_DAY = 16

# Regular season window (month, day). Games outside this are flagged.
SEASON_START = (10, 1)
SEASON_END = (4, 30)

# Home/away balance: 41/41 is perfect; this band is "fine, don't flag".
HOME_GAME_BAND = (39, 43)

HARD = "hard"
SOFT = "soft"


class Violation:
    """One rule breach. Never raised as an exception -- collected."""

    def __init__(self, rule, severity, team, detail):
        self.rule = rule
        self.severity = severity
        self.team = team
        self.detail = detail

    def __repr__(self):
        return (f"Violation({self.rule}, {self.severity}, "
                f"{self.team}, {self.detail})")


def _team_name(team):
    return team.team_name if hasattr(team, "team_name") else str(team)


def _team_dates(games):
    """Map team name -> sorted list of game dates (regular season only)."""
    team_dates = defaultdict(set)
    for g in games:
        if not isinstance(g, dict):
            continue
        if g.get("preseason"):
            continue
        d = g.get("date")
        if d is None:
            continue
        for side in ("home_team", "away_team"):
            t = g.get(side)
            if t is not None:
                team_dates[_team_name(t)].add(d)
    return {t: sorted(ds) for t, ds in team_dates.items()}


def _back_to_backs(dates):
    return sum(1 for i in range(1, len(dates))
               if (dates[i] - dates[i - 1]).days == 1)


def _max_streak(dates):
    run, best = 1, 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


# ---------------------------------------------------------------------------
# Validation (pure: no side effects, never raises).
# ---------------------------------------------------------------------------

def validate_schedule(games, season_year=None):
    """Check a schedule against every NHL structural rule.

    Returns a list of Violation. Empty list == clean.
    """
    violations = []
    try:
        return _validate_inner(games, season_year, violations)
    except Exception as exc:  # never break the game on a validator bug
        violations.append(Violation("validator_error", HARD, "-",
                                    f"validator crashed: {exc}"))
        return violations


def _validate_inner(games, season_year, violations):
    team_dates = _team_dates(games)

    # --- Hard: completeness ---
    for team, dates in sorted(team_dates.items()):
        if len(dates) != GAMES_PER_TEAM:
            violations.append(Violation(
                "game_count", HARD, team,
                f"{len(dates)} games, expected {GAMES_PER_TEAM}"))

    # --- Hard: no 3+ consecutive game days ---
    for team, dates in sorted(team_dates.items()):
        if _max_streak(dates) > MAX_CONSECUTIVE_GAME_DAYS:
            worst = _max_streak(dates)
            violations.append(Violation(
                "consecutive_days", HARD, team,
                f"{worst} straight game days (max {MAX_CONSECUTIVE_GAME_DAYS})"))

    # --- Hard: no doubleheaders ---
    per_day = defaultdict(set)
    for g in games:
        if not isinstance(g, dict) or g.get("preseason"):
            continue
        d = g.get("date")
        if d is None:
            continue  # dateless records can't double-book; skip, don't flag
        for side in ("home_team", "away_team"):
            t = g.get(side)
            if t is None:
                continue
            name = _team_name(t)
            if name in per_day[d]:
                violations.append(Violation(
                    "doubleheader", HARD, name, f"two games on {d}"))
            per_day[d].add(name)

    # --- Hard: season window ---
    if season_year is not None:
        start = date(season_year, *SEASON_START)
        end = date(season_year + 1, *SEASON_END)
        for team, dates in sorted(team_dates.items()):
            outside = [d for d in dates if d < start or d > end]
            if outside:
                violations.append(Violation(
                    "season_window", HARD, team,
                    f"{len(outside)} games outside {start}..{end}"))

    # --- Hard: daily league load ---
    day_counts = defaultdict(int)
    for g in games:
        if isinstance(g, dict) and not g.get("preseason"):
            day_counts[g.get("date")] += 1
    for d, n in sorted(day_counts.items()):
        if n > MAX_GAMES_PER_DAY:
            violations.append(Violation(
                "daily_load", HARD, "-",
                f"{n} games on {d} (max {MAX_GAMES_PER_DAY})"))

    # --- Soft: back-to-back band ---
    lo, hi = BACK_TO_BACK_REPORT_BAND
    for team, dates in sorted(team_dates.items()):
        n = _back_to_backs(dates)
        if n < lo or n > hi:
            violations.append(Violation(
                "back_to_backs", SOFT, team,
                f"{n} back-to-backs (report band {lo}-{hi}, "
                f"target {BACK_TO_BACK_TARGET[0]}-{BACK_TO_BACK_TARGET[1]})"))

    # --- Soft: home/away balance ---
    home_counts = defaultdict(int)
    for g in games:
        if not isinstance(g, dict) or g.get("preseason"):
            continue
        h = g.get("home_team")
        if h is not None:
            home_counts[_team_name(h)] += 1
    hlo, hhi = HOME_GAME_BAND
    for team, dates in sorted(team_dates.items()):
        h = home_counts.get(team, 0)
        if not (hlo <= h <= hhi):
            violations.append(Violation(
                "home_balance", SOFT, team,
                f"{h} home games (band {hlo}-{hhi})"))

    return violations


# ---------------------------------------------------------------------------
# Enforcement (repairs hard violations; never raises, never deletes games).
# ---------------------------------------------------------------------------

def enforce_schedule(games, season_year=None):
    """Validate and repair a schedule. Returns (games, unfixable).

    - Repairs hard violations by moving games (never deleting).
    - Soft violations are reported, never touched.
    - Never raises; worst case returns the schedule unchanged with the
      unfixable violations listed.
    """
    try:
        violations = validate_schedule(games, season_year)
    except Exception as exc:
        return games, [Violation("validator_error", HARD, "-",
                                 f"enforce aborted: {exc}")]

    hard = [v for v in violations if v.severity == HARD]
    soft = [v for v in violations if v.severity == SOFT]

    for v in soft:
        print(f"   📋 Schedule note ({v.rule}): {v.team} -- {v.detail}")

    if not hard:
        return games, []

    unfixable = []
    for v in hard:
        try:
            if v.rule == "consecutive_days":
                if not _repair_streak(games, v.team, season_year):
                    unfixable.append(v)
            elif v.rule == "doubleheader":
                if not _repair_doubleheader(games, v.team, v.detail,
                                            season_year):
                    unfixable.append(v)
            else:
                # game_count / season_window / daily_load have no safe
                # auto-repair: report loudly, keep the schedule playable.
                unfixable.append(v)
        except Exception as exc:
            unfixable.append(Violation(v.rule, HARD, v.team,
                                       f"{v.detail} (repair crashed: {exc})"))

    for v in unfixable:
        print(f"   🚨 Schedule HARD violation unfixable: {v.rule}: "
              f"{v.team} -- {v.detail}")

    return games, unfixable


def _playing_on(games, check_date):
    playing = set()
    for g in games:
        if isinstance(g, dict) and g.get("date") == check_date \
                and not g.get("preseason"):
            for side in ("home_team", "away_team"):
                t = g.get(side)
                if t is not None:
                    playing.add(_team_name(t))
    return playing


def _would_streak(games, team_name, new_date):
    """Would team_name have 3+ straight game days including new_date?"""
    dates = set()
    for g in games:
        if not isinstance(g, dict) or g.get("preseason"):
            continue
        for side in ("home_team", "away_team"):
            t = g.get(side)
            if t is not None and _team_name(t) == team_name:
                dates.add(g.get("date"))
    dates.add(new_date)
    ds = sorted(dates)
    for i in range(len(ds) - 2):
        if (ds[i + 1] - ds[i]).days == 1 \
                and (ds[i + 2] - ds[i + 1]).days == 1:
            return True
    return False


def _season_bounds(games, season_year):
    dates = [g["date"] for g in games
             if isinstance(g, dict) and g.get("date") is not None]
    if not dates:
        return None, None
    if season_year is not None:
        return date(season_year, *SEASON_START), \
            date(season_year + 1, *SEASON_END)
    return min(dates), max(dates)


# The real NHL goes dark over Christmas (Dec 24-26: no games). The
# generator respects the break; repairs must not undo it by moving a
# game onto those dates.
_NO_GAME_DATES = {(12, 24), (12, 25), (12, 26)}


def _is_dark_date(d):
    try:
        return (d.month, d.day) in _NO_GAME_DATES
    except Exception:
        return False


def _try_move_game(games, target, min_date, max_date):
    """Move target game to a nearby open date. True if moved."""
    home = _team_name(target["home_team"])
    away = _team_name(target["away_team"])
    others = [g for g in games if g is not target]

    for max_offset in (14, 30):
        for offset in range(1, max_offset + 1):
            for new_date in (target["date"] + timedelta(days=offset),
                             target["date"] - timedelta(days=offset)):
                if new_date < min_date or new_date > max_date:
                    continue
                if _is_dark_date(new_date):
                    continue
                playing = _playing_on(others, new_date)
                if home in playing or away in playing:
                    continue
                if _would_streak(others, home, new_date):
                    continue
                if _would_streak(others, away, new_date):
                    continue
                target["date"] = new_date
                return True
    return False


def _try_swap_game(games, target):
    """Swap target's date with another game. True if swapped.

    After the swap, target's teams (home/away) sit on other_date and the
    other game's teams (oh/oa) sit on d2. Each pair must be free of other
    commitments on its new date -- i.e. not appearing in any game on that
    date besides the one being swapped away.
    """
    home = _team_name(target["home_team"])
    away = _team_name(target["away_team"])
    d2 = target["date"]
    for other in games:
        if other is target or not isinstance(other, dict):
            continue
        other_date = other.get("date")
        if other_date is None:
            continue
        oh = _team_name(other["home_team"])
        oa = _team_name(other["away_team"])
        # home/away move onto other_date: clear except the departing pair
        playing_on_other = _playing_on(games, other_date) - {oh, oa}
        if home in playing_on_other or away in playing_on_other:
            continue
        # oh/oa move onto d2: clear except the departing pair
        playing_on_d2 = _playing_on(games, d2) - {home, away}
        if oh in playing_on_d2 or oa in playing_on_d2:
            continue
        temp = [g for g in games
                if g is not target and g is not other]
        if _would_streak(temp, home, other_date):
            continue
        if _would_streak(temp, away, other_date):
            continue
        if _would_streak(temp, oh, d2):
            continue
        if _would_streak(temp, oa, d2):
            continue
        target["date"], other["date"] = other_date, d2
        return True
    return False


def _repair_streak(games, team_name, season_year):
    """Move the middle game(s) of a 3+ streak. True if all fixed."""
    min_date, max_date = _season_bounds(games, season_year)
    if min_date is None:
        return False
    ok = True
    # Re-scan after each move; cap iterations so a pathological case
    # can't spin forever.
    for _ in range(10):
        team_dates = []
        for g in games:
            if not isinstance(g, dict) or g.get("preseason"):
                continue
            d = g.get("date")
            if d is None:
                continue
            names = {_team_name(g.get("home_team")),
                     _team_name(g.get("away_team"))}
            if team_name in names:
                team_dates.append(d)
        team_dates = sorted(set(team_dates))

        moved_this_pass = False
        for i in range(len(team_dates) - 2):
            d1, d2, d3 = team_dates[i], team_dates[i + 1], team_dates[i + 2]
            if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                target = next(
                    (g for g in games
                     if isinstance(g, dict) and g.get("date") == d2
                     and team_name in (_team_name(g.get("home_team")),
                                       _team_name(g.get("away_team")))),
                    None)
                if target is None:
                    ok = False
                    break
                if _try_move_game(games, target, min_date, max_date) \
                        or _try_swap_game(games, target):
                    moved_this_pass = True
                    break
                ok = False
                break
        if not moved_this_pass:
            break
    return ok


def _repair_doubleheader(games, team_name, detail, season_year):
    """Move one of the same-day games. True if fixed."""
    min_date, max_date = _season_bounds(games, season_year)
    if min_date is None:
        return False
    by_date = defaultdict(list)
    for g in games:
        if not isinstance(g, dict) or g.get("preseason"):
            continue
        d = g.get("date")
        names = {_team_name(g.get("home_team")),
                 _team_name(g.get("away_team"))}
        if team_name in names:
            by_date[d].append(g)
    for d, glist in by_date.items():
        if len(glist) > 1:
            target = glist[1]
            return _try_move_game(games, target, min_date, max_date) \
                or _try_swap_game(games, target)
    return True
