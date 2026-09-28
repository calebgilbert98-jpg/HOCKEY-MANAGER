"""AHL (minors) stat ledger -- lightweight, deliberately not a league sim.

The AHL has no simulated games, standings, or schedules in Puck Dynasty --
by design (don't save as much league data for the minors). This module
gives the farm just enough stat reality for the AHL Stats screen to answer
"who's cooking": on each simmed NHL day, every player on an AHL roster may
log an AHL game, with a stat line generated from his attributes.

The ledger lives on ``player.ahl_stats`` (a PlayerStats, same shape as
``stats`` and ``playoff_stats``) and is NEVER mixed with NHL numbers:

  - NHL screens read ``player.stats`` / ``player.playoff_stats`` from
    ``team.roster`` only.
  - The AHL Stats screen reads ``player.ahl_stats`` from
    ``team.ahl_roster`` only.

A callup/senddown freezes the other ledger mid-season -- an AHL point can
never show up as an NHL point or vice versa. No bleeding, by construction.

Perf: ~800 AHL players x a few RNG calls per simmed day -- microseconds,
no per-frame cost. Skipped entirely outside the AHL regular-season window
(Oct 1 - Apr 20) and never during the NHL playoffs.
"""

import math
import random

# Chance an AHL player logs a game on a given simmed NHL day.
# 0.39 x ~184 days ~= 72 games, the real AHL schedule length.
GAME_PROBABILITY = 0.39
# Chance an AHL goalie is his club's starter on a game day (~2-3 goalies
# per farm roster, one net).
GOALIE_START_PROBABILITY = 0.45


def ensure_ahl_stats(player):
    """Backfill the AHL ledger on players from old saves. Idempotent."""
    ledger = getattr(player, "ahl_stats", None)
    if ledger is None:
        try:
            from game_classes import PlayerStats
            ledger = PlayerStats()
        except Exception:
            return None
        try:
            player.ahl_stats = ledger
        except Exception:
            pass
    return ledger


def reset_ahl_stats(player):
    """Zero the AHL ledger at season rollover (mirrors stats/playoff_stats)."""
    try:
        from game_classes import PlayerStats
        player.ahl_stats = PlayerStats()
    except Exception:
        pass


def _poisson(lam):
    """Small-lambda Poisson sample (Knuth). lam is always < 5 here."""
    if lam <= 0:
        return 0
    l = math.exp(-lam)
    k = 0
    p = 1.0
    while p > l:
        k += 1
        p *= random.random()
    return k - 1


def _overall(player):
    try:
        return int(player.overall_rating())
    except Exception:
        return 60


def _is_goalie(player):
    try:
        return player.primary_position.value == "G"
    except Exception:
        return str(getattr(player, "primary_position", "")).upper().endswith(
            "GOALIE")


def _skater_game(player, ledger):
    """One AHL game for a skater: points from overall, PIM from edge."""
    ovr = _overall(player)
    # Expected AHL points/game. 75 ovr (NHL-tweener) ~= 0.84; 65 ~= 0.44;
    # 60 ~= 0.24. AHL scoring leaders sit ~1.1-1.3 -- nobody here should
    # live there without NHL-caliber talent.
    ppg = max(0.05, (ovr - 54) * 0.04)
    ledger.games_played += 1
    ledger.goals += _poisson(ppg * 0.38)
    ledger.assists += _poisson(ppg * 0.62)
    ledger.shots += _poisson(2.2)
    if random.random() < 0.16:
        pim = 2 if random.random() < 0.85 else 5
        ledger.penalties_in_minutes += pim
        ledger.penalties += 1


def _goalie_game(player, ledger):
    """One AHL start: ~.900 goaltending around a league-average 2.80 GAA."""
    ovr = _overall(player)
    shots_against = 24 + int(random.random() * 10)
    # .880 at 55 ovr -> .904 at 75 ovr, plus game-to-game noise.
    svp = 0.880 + (ovr - 55) * 0.0012 + random.gauss(0, 0.012)
    svp = max(0.800, min(0.970, svp))
    saves = min(shots_against, int(round(shots_against * svp)))
    goals_against = shots_against - saves
    ledger.games_played += 1
    ledger.shots_against += shots_against
    ledger.saves += saves
    ledger.goals_against += goals_against
    if goals_against == 0:
        ledger.shutouts += 1
    # Win likelihood falls as the goals go in (AHL teams score ~3.0/gm).
    win_p = max(0.10, min(0.90, 0.50 + (2.8 - goals_against) * 0.12))
    if random.random() < win_p:
        ledger.wins += 1
    else:
        ledger.losses += 1
    try:
        ledger._update_goalie_stats()
    except Exception:
        pass


def simulate_ahl_day(league):
    """Roll one day of AHL stat lines for every farm roster in the league.

    Called from the daily maintenance path in main.py. Cheap by design:
    a probability roll per player, and only players who "played" get a
    generated line. No standings, no schedules, nothing persisted beyond
    the per-player ledger.
    """
    try:
        teams = getattr(league, "teams", None) or []
    except Exception:
        return
    for team in teams:
        try:
            farm = getattr(team, "ahl_roster", None) or []
        except Exception:
            continue
        for player in farm:
            try:
                if random.random() >= GAME_PROBABILITY:
                    continue
                ledger = ensure_ahl_stats(player)
                if ledger is None:
                    continue
                if _is_goalie(player):
                    if random.random() < GOALIE_START_PROBABILITY:
                        _goalie_game(player, ledger)
                    # Non-starters don't dress: no GP, no line.
                else:
                    _skater_game(player, ledger)
            except Exception:
                continue


def top_skaters(league, limit=25):
    """League-wide AHL scoring leaders: (player, team_name, ledger)."""
    rows = []
    for team in getattr(league, "teams", None) or []:
        tname = getattr(team, "team_name", "?")
        for p in getattr(team, "ahl_roster", None) or []:
            ledger = getattr(p, "ahl_stats", None)
            if ledger is None or getattr(ledger, "games_played", 0) == 0:
                continue
            try:
                if _is_goalie(p):
                    continue
            except Exception:
                pass
            rows.append((p, tname, ledger))
    rows.sort(key=lambda r: (r[2].goals + r[2].assists,
                             r[2].goals), reverse=True)
    return rows[:limit]


def top_goalies(league, limit=15, min_gp=5):
    """League-wide AHL goalie leaders by SV% (min GP): (player, team, ledger)."""
    rows = []
    for team in getattr(league, "teams", None) or []:
        tname = getattr(team, "team_name", "?")
        for p in getattr(team, "ahl_roster", None) or []:
            ledger = getattr(p, "ahl_stats", None)
            if ledger is None or getattr(ledger, "games_played", 0) < min_gp:
                continue
            try:
                if not _is_goalie(p):
                    continue
            except Exception:
                continue
            rows.append((p, tname, ledger))
    rows.sort(key=lambda r: (getattr(r[2], "save_percentage", 0),
                             r[2].wins), reverse=True)
    return rows[:limit]


def cooking(league, limit=15, min_gp=10):
    """'Who's cooking': best points-per-game among farm skaters (min GP).

    P/GP over raw points so a mid-season callup doesn't bury a hot start,
    and a grinder with 40 GP doesn't outrank a prospect scoring nightly.
    """
    rows = []
    for team in getattr(league, "teams", None) or []:
        tname = getattr(team, "team_name", "?")
        for p in getattr(team, "ahl_roster", None) or []:
            ledger = getattr(p, "ahl_stats", None)
            if ledger is None or getattr(ledger, "games_played", 0) < min_gp:
                continue
            try:
                if _is_goalie(p):
                    continue
            except Exception:
                pass
            gp = max(1, ledger.games_played)
            ppg = (ledger.goals + ledger.assists) / gp
            rows.append((ppg, p, tname, ledger))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [(p, tname, ledger, ppg) for ppg, p, tname, ledger in rows[:limit]]
