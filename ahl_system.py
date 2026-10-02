# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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


# ---------------------------------------------------------------------------
# New-CBA paper-transaction rule (2026)
#
# The old CBA let clubs "loan" a player to the AHL on paper and recall him
# the next day without him ever reporting -- a cap-space maneuver (the
# Marco Kasper shuttle). The new deal closes it: any player assigned to
# the AHL must play at least one game down there before he can be
# recalled to the NHL.
#
# The counter lives on player.ahl_games_since_assignment:
#   None -> grandfathered (old save, initial roster construction, or never
#           assigned under this rule) -> recall is legal.
#   0    -> freshly assigned, hasn't dressed yet -> recall is BLOCKED.
#   >= 1 -> has played at least one AHL game -> recall is legal.
#
# Every NHL->AHL assignment stamps the counter to 0; every dressed AHL
# appearance increments it. The counter survives trades (he still hasn't
# played), and a fresh assignment re-stamps it. Emergency recalls don't
# exist as a mechanic in Puck Dynasty, so there's no carve-out to write.
# ---------------------------------------------------------------------------

def stamp_ahl_assignment(player):
    """Mark an NHL->AHL assignment: the recall gate starts counting.

    Call at every demotion point (quiet demote, waiver clearing,
    roster-move screen). Idempotent and exception-safe.
    """
    try:
        player.ahl_games_since_assignment = 0
    except Exception:
        pass


def ahl_recall_block_reason(player):
    """None if recalling this player is legal, else a human-readable
    reason the recall is blocked. Old saves and never-assigned players
    (counter None) are grandfathered -- always legal."""
    try:
        n = getattr(player, "ahl_games_since_assignment", None)
    except Exception:
        return None
    if n is None:
        return None
    try:
        if int(n) >= 1:
            return None
    except Exception:
        return None
    name = str(getattr(player, "full_name", "He") or "He")
    return (
        f"{name} was just assigned to the AHL and hasn't played a game "
        f"down there yet. Under the new CBA a player must play at least "
        f"one AHL game before he can be recalled -- no more paper "
        f"transactions."
    )


def note_ahl_appearance(player):
    """Count one dressed AHL game toward the recall gate.

    Only call when the player actually dressed (a generated stat line).
    Grandfathered players (counter None) are left alone.
    """
    try:
        n = getattr(player, "ahl_games_since_assignment", None)
    except Exception:
        return
    if n is None:
        return
    try:
        player.ahl_games_since_assignment = int(n) + 1
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
                        # He dressed: counts toward the recall gate.
                        note_ahl_appearance(player)
                    # Non-starters don't dress: no GP, no line.
                else:
                    _skater_game(player, ledger)
                    # He dressed: counts toward the recall gate.
                    note_ahl_appearance(player)
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

# ---------------------------------------------------------------------------
# Weekly farm confidence: AHL production -> morale / attitude / call-up buzz
# ---------------------------------------------------------------------------
#
# Runs once a week from the career maintenance path
# (main._career_weekly_update, every Monday). Every farm player in the league
# is measured against the SAME expected-production curves that generate his
# AHL stat lines (_skater_game / _goalie_game above), so the read is
# self-consistent: a kid "cooking" is genuinely beating what his attributes
# project -- never a narrative slapped on top of noise.
#
# Situationally relevant only -- quiet weeks stay quiet:
#   - prospect (age <= 23) at >= 1.4x expected P/GP over 10+ GP: confidence
#     surges (morale +4), the live call-up buzz flag is set, and the user
#     gets ONE inbox note per prospect per season (user's farm only) -- the
#     kid is forcing the issue.
#   - the same kid, but he's already tasted the NHL this season
#     (NHL GP > 0): bigger surge (morale +6) -- "give me another shot".
#   - veteran (age >= 27) producing on the farm but never called up:
#     frustration (happiness -3, morale -2) -- he knows what this means.
#     No inbox noise; it surfaces through the normal squad-concerns UI.
#   - young player slumping at <= 0.5x expected over 15+ GP: confidence
#     dips (morale -4, happiness -2).
#   - goalies read on SV% vs their expected curve (>= .915 cooking,
#     <= .875 slump, min 5 GP) instead of P/GP.
#
# The morale moves feed everything downstream for free: the existing
# situational call-up readiness term ("Confidence right now" in
# prospect_development) reads morale, and the weekly happiness/morale chain
# in manager_career picks up the happiness moves. No engine logic touched.
#
# New player attributes (plain values, so save/load round-trips them via
# the generic __dict__ path; getattr defaults cover old saves):
#   - ahl_callup_buzz (bool): live flag, recomputed weekly -- True while
#     the player is cooking on the farm, cleared otherwise (and cleared
#     for anyone on an NHL roster).
#   - ahl_buzz_note_sent (bool): one inbox note per prospect per season;
#     reset in League.end_of_season next to the AHL ledger wipe.
#
# Perf: ~800 farm players x a handful of attribute reads, once a week.
# Microseconds; no per-frame or per-day cost.

PROSPECT_MAX_AGE = 23
VETERAN_MIN_AGE = 27
COOKING_MULT = 1.4      # farm P/GP vs overall-expected P/GP
COOKING_MIN_GP = 10
SLUMP_MULT = 0.5
SLUMP_MIN_GP = 15
GOALIE_COOKING_SV = 0.915
GOALIE_SLUMP_SV = 0.875
GOALIE_MIN_GP = 5


def _expected_ahl_ppg(player):
    """Expected AHL points/game -- the same curve _skater_game deals from."""
    return max(0.05, (_overall(player) - 54) * 0.04)


def _expected_ahl_sv(player):
    """Expected AHL SV% -- the same curve _goalie_game deals from."""
    return 0.880 + (_overall(player) - 55) * 0.0012


def _bump_morale(player, delta):
    m = getattr(player, "morale", 70) or 70
    player.morale = max(1, min(100, m + delta))


# T1 refinement (2026-09-30): adaptability in the farm-confidence pass.
# Demotion frustration (cook_vet) and slump dips (slump/g_slump) are morale
# SHOCKS -- negative deltas dampened via adaptability_shock_mult (rails
# [0.75, 1.0]). Cooking surges (cook/g_cook) are slump RECOVERY -- positive
# deltas scaled by adaptability_recovery_mult (rails [1.0, 1.25]), so high
# adaptability refills morale faster: the hole is shallower AND refills
# quicker, which is what "shortens slumps" means in morale terms. Form and
# production curves are untouched (morale and form stay separate).
def _adapt_shock_mult(player):
    try:
        import reputation_system as _rs
        return _rs.adaptability_shock_mult(player)
    except Exception:
        return 1.0


def _adapt_recovery_mult(player):
    try:
        import reputation_system as _rs
        return _rs.adaptability_recovery_mult(player)
    except Exception:
        return 1.0


def _bump_happiness(player, delta):
    h = getattr(player, "happiness", 70) or 70
    player.happiness = max(0, min(100, h + delta))


def _full_name(player):
    try:
        return f"{player.first_name} {player.last_name}"
    except Exception:
        return "Unknown player"


def _buzz_note(player, team_name, ledger, ppg=None, sv=None):
    """The one-per-season 'he's forcing the issue' inbox note."""
    from game_classes import EmailMessage
    name = _full_name(player)
    age = getattr(player, "age", "?")
    gp = getattr(ledger, "games_played", 0) or 0
    if sv is not None:
        line = (f"{name} ({age}) is standing on his head for {team_name}: "
                f"{sv:.3f} SV% across {gp} AHL starts -- well above what his "
                f"game projects.")
    else:
        pts = (getattr(ledger, "goals", 0) or 0) + (getattr(ledger, "assists", 0) or 0)
        line = (f"{name} ({age}) has {pts} points in {gp} AHL games "
                f"({(ppg or 0):.2f} P/GP) for {team_name} -- well above what "
                f"his game projects.")
    nhl_gp = getattr(getattr(player, "stats", None), "games_played", 0) or 0
    if nhl_gp > 0:
        tail = (f"He's already had a taste of the NHL this season and is "
                f"playing like he wants another shot. His confidence is "
                f"through the roof -- and his call-up case keeps getting "
                f"louder.")
    else:
        tail = (f"The room's buzzing and he's playing like he wants your "
                f"phone to ring. His confidence is soaring -- and his "
                f"call-up case is getting louder by the week.")
    return EmailMessage(
        sender="Farm Report", sender_type="Scout",
        subject=f"🔥 {name} is forcing the issue in the AHL",
        content=f"{line}\n\n{tail}",
        category="Development", priority=2)


def _evaluate_farm_player(player):
    """Classify one farm player's week. Returns a tag string.

    Tags: 'cook' (prospect cooking), 'cook_vet' (veteran producing but
    stuck), 'slump' (young player slumping), 'g_cook' / 'g_slump' (goalie
    equivalents), or '' (quiet week -- leave him alone).
    """
    try:
        age = int(getattr(player, "age", 99) or 99)
    except (TypeError, ValueError):
        age = 99
    ledger = getattr(player, "ahl_stats", None)
    if ledger is None:
        return ""
    try:
        gp = int(getattr(ledger, "games_played", 0) or 0)
    except (TypeError, ValueError):
        return ""
    if _is_goalie(player):
        if gp < GOALIE_MIN_GP:
            return ""
        try:
            sv = float(getattr(ledger, "save_percentage", 0) or 0)
        except (TypeError, ValueError):
            return ""
        if sv >= GOALIE_COOKING_SV:
            return "g_cook"
        if sv <= GOALIE_SLUMP_SV:
            return "g_slump"
        return ""
    # Skaters: production vs the same curve that generated the line.
    if gp < COOKING_MIN_GP and gp < SLUMP_MIN_GP:
        return ""
    pts = (getattr(ledger, "goals", 0) or 0) + (getattr(ledger, "assists", 0) or 0)
    ppg = pts / max(1, gp)
    expected = _expected_ahl_ppg(player)
    ratio = ppg / expected if expected > 0 else 0
    if gp >= COOKING_MIN_GP and ratio >= COOKING_MULT:
        if age >= VETERAN_MIN_AGE:
            return "cook_vet"
        if age <= PROSPECT_MAX_AGE:
            return "cook"
        return ""  # mid-career tweener cooking: not a story either way
    if gp >= SLUMP_MIN_GP and ratio <= SLUMP_MULT and age <= PROSPECT_MAX_AGE:
        return "slump"
    return ""


def weekly_farm_confidence(league, user_team=None):
    """Weekly morale/confidence/attitude pass over every farm roster.

    Returns a list of EmailMessage notes for the user's inbox (at most one
    per prospect per season). Safe to call with fakes; never raises.
    """
    notes = []
    try:
        teams = list(getattr(league, "teams", None) or [])
    except Exception:
        return notes
    for team in teams:
        try:
            is_user = user_team is not None and team is user_team
            tname = getattr(team, "team_name", "?")
        except Exception:
            continue
        # Anyone on an NHL roster isn't cooking on the farm: clear the
        # live buzz flag so it can't go stale after a call-up.
        try:
            for p in getattr(team, "roster", None) or []:
                try:
                    if getattr(p, "ahl_callup_buzz", False):
                        p.ahl_callup_buzz = False
                except Exception:
                    continue
        except Exception:
            pass
        try:
            farm = list(getattr(team, "ahl_roster", None) or [])
        except Exception:
            continue
        for p in farm:
            try:
                tag = _evaluate_farm_player(p)
            except Exception:
                continue
            try:
                if tag == "cook":
                    nhl_gp = getattr(getattr(p, "stats", None),
                                     "games_played", 0) or 0
                    _bump_morale(p, (6 if nhl_gp > 0 else 4)
                                 * _adapt_recovery_mult(p))
                    p.ahl_callup_buzz = True
                    if is_user and not getattr(p, "ahl_buzz_note_sent", False):
                        ledger = getattr(p, "ahl_stats", None)
                        gp = max(1, int(getattr(ledger, "games_played", 0) or 1))
                        pts = (getattr(ledger, "goals", 0) or 0) + \
                            (getattr(ledger, "assists", 0) or 0)
                        notes.append(_buzz_note(p, tname, ledger,
                                                ppg=pts / gp))
                        p.ahl_buzz_note_sent = True
                elif tag == "g_cook":
                    _bump_morale(p, 3 * _adapt_recovery_mult(p))
                    p.ahl_callup_buzz = True
                    if is_user and not getattr(p, "ahl_buzz_note_sent", False):
                        notes.append(_buzz_note(
                            p, tname, getattr(p, "ahl_stats", None),
                            sv=float(getattr(getattr(p, "ahl_stats", None),
                                             "save_percentage", 0) or 0)))
                        p.ahl_buzz_note_sent = True
                elif tag == "g_slump":
                    _bump_morale(p, -3 * _adapt_shock_mult(p))
                    _bump_happiness(p, -1)
                    p.ahl_callup_buzz = False
                elif tag == "cook_vet":
                    # Producing, but the phone never rings: frustration.
                    _bump_happiness(p, -3)
                    _bump_morale(p, -2 * _adapt_shock_mult(p))
                    p.ahl_callup_buzz = False
                elif tag == "slump":
                    _bump_morale(p, -4 * _adapt_shock_mult(p))
                    _bump_happiness(p, -2)
                    p.ahl_callup_buzz = False
                else:
                    # Quiet week: not cooking, not slumping -- flag off,
                    # no note, no morale touch.
                    if getattr(p, "ahl_callup_buzz", False):
                        p.ahl_callup_buzz = False
            except Exception:
                continue
    return notes


# ---------------------------------------------------------------------------
# Lightweight AHL standings (D41 Phase 1)
#
# The AHL still has no real game sim -- but each farm roster now carries a
# lightweight W/L/OTL record derived from abstract daily matchups weighted
# by roster strength. This is 80% of the feel (a standings table with
# movement) for 20% of the risk (no schedule gen, no game sim, no roster
# migration). Cheap: one abstract "game" per team per simmed day.
# ---------------------------------------------------------------------------

def ensure_ahl_record(team):
    """Backfill a lightweight standings record on a team. Idempotent."""
    try:
        rec = getattr(team, "ahl_record", None)
        if not isinstance(rec, dict):
            rec = {"w": 0, "l": 0, "otl": 0, "pts": 0,
                   "gf": 0, "ga": 0, "gp": 0}
            team.ahl_record = rec
        else:
            for k in ("w", "l", "otl", "pts", "gf", "ga", "gp"):
                rec.setdefault(k, 0)
        return rec
    except Exception:
        return {"w": 0, "l": 0, "otl": 0, "pts": 0, "gf": 0, "ga": 0, "gp": 0}


def reset_ahl_record(team):
    """Zero the standings record at season rollover."""
    try:
        team.ahl_record = {"w": 0, "l": 0, "otl": 0, "pts": 0,
                           "gf": 0, "ga": 0, "gp": 0}
    except Exception:
        pass


def _farm_strength(team) -> float:
    """Abstract team strength from ahl_roster quality. Never raises."""
    try:
        farm = getattr(team, "ahl_roster", None) or []
        if not farm:
            return 65.0
        total, n = 0.0, 0
        for p in farm:
            try:
                total += float(p.overall_rating())
                n += 1
            except Exception:
                continue
        return (total / n) if n else 65.0
    except Exception:
        return 65.0


def simulate_ahl_standings_day(league):
    """Roll one abstract AHL 'game day' for standings.

    Each farm team plays one abstract game vs a random opponent, weighted
    by roster strength. Scores are plausible AHL-style (2-5 goals). The
    per-player stat ledger (simulate_ahl_day) is untouched -- this only
    moves the W/L needle.

    Skipped outside the AHL season window (Oct 1 - Apr 20), mirroring
    the stat ledger's gating. Never raises.
    """
    try:
        teams = [t for t in (getattr(league, "teams", None) or [])
                 if getattr(t, "ahl_roster", None)]
        if len(teams) < 2:
            return
        # Season window gate (best-effort; sim even if date unknown)
        try:
            from datetime import date as _date
            today = getattr(league, "current_date", None)
            if today is not None:
                if hasattr(today, "month"):
                    m, d = today.month, today.day
                    in_window = (m == 10) or (m in (11, 12, 1, 2, 3)) or (m == 4 and d <= 20)
                    if not in_window:
                        return
        except Exception:
            pass

        strengths = {id(t): _farm_strength(t) for t in teams}
        order = list(teams)
        random.shuffle(order)
        # Pair up; odd team out sits (bye).
        for i in range(0, len(order) - 1, 2):
            a, b = order[i], order[i + 1]
            try:
                sa, sb = strengths[id(a)], strengths[id(b)]
                # Win probability from strength gap (Elo-lite).
                diff = sa - sb
                p_a = 1.0 / (1.0 + 10 ** (-diff / 8.0))
                r = random.random()
                # Plausible AHL scores.
                gf_a = max(1, min(7, int(random.gauss(3.1 + diff * 0.08, 1.4))))
                gf_b = max(1, min(7, int(random.gauss(3.1 - diff * 0.08, 1.4))))
                if gf_a == gf_b:
                    # Tie broken in "OT": winner gets 2 pts, loser 1.
                    if r < p_a:
                        gf_a += 1
                        _apply_ahl_result(a, b, gf_a, gf_b, ot=True)
                    else:
                        gf_b += 1
                        _apply_ahl_result(b, a, gf_b, gf_a, ot=True)
                elif (gf_a > gf_b and r < p_a) or (gf_b > gf_a and r >= p_a):
                    # Favorite won in regulation.
                    winner, loser = (a, b) if gf_a > gf_b else (b, a)
                    _apply_ahl_result(winner, loser,
                                      max(gf_a, gf_b), min(gf_a, gf_b), ot=False)
                else:
                    # Upset: underdog won in regulation (keep the rolled score).
                    winner, loser = (a, b) if gf_a > gf_b else (b, a)
                    _apply_ahl_result(winner, loser,
                                      max(gf_a, gf_b), min(gf_a, gf_b), ot=False)
            except Exception:
                continue
    except Exception:
        pass


def _apply_ahl_result(winner, loser, gf_w, gf_l, ot=False):
    """Apply an abstract result to both teams' records. Never raises."""
    try:
        wr = ensure_ahl_record(winner)
        lr = ensure_ahl_record(loser)
        wr["gp"] += 1
        lr["gp"] += 1
        wr["w"] += 1
        wr["pts"] += 2
        wr["gf"] += gf_w
        wr["ga"] += gf_l
        lr["gf"] += gf_l
        lr["ga"] += gf_w
        if ot:
            lr["otl"] += 1
            lr["pts"] += 1
        else:
            lr["l"] += 1
    except Exception:
        pass


def ahl_standings(league):
    """Sorted AHL standings: list of (team, record) by pts, then wins, then GD.

    Never raises.
    """
    try:
        rows = []
        for t in (getattr(league, "teams", None) or []):
            try:
                if not getattr(t, "ahl_roster", None):
                    continue
                rec = ensure_ahl_record(t)
                rows.append((t, rec))
            except Exception:
                continue
        rows.sort(key=lambda r: (r[1].get("pts", 0),
                                 r[1].get("w", 0),
                                 r[1].get("gf", 0) - r[1].get("ga", 0)),
                  reverse=True)
        return rows
    except Exception:
        return []
