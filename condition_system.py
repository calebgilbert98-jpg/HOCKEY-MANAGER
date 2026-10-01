# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Condition / fatigue / wear-and-tear system -- W3 (fatigue worker).

The canonical per-player condition model for Puck Dynasty. Three fatigue
models used to not talk to each other (GameSim per-game energy was
attribute-blind, quick_sim wired stamina/endurance/durability, and the
lines-editor "condition" was a hardcoded 100%). This module is the one
decision both fidelities share:

* ``fatigue_resistance`` -- the stamina/endurance/durability blend. Mirrors
  quick_sim._calculate_fatigue_factor's resistance term; GameSim's
  _update_fatigue scales its accumulation/recovery off the same blend.
* ``get_condition`` -- persistent 0-100 season condition (wear-and-tear),
  stored on Player.condition (additive field; old saves use the
  getattr-default 100.0).
* ``apply_postgame_wear`` -- post-game wear accumulation + rest recovery.
  Heavy-minutes games (>~35 min for skaters) apply escalating wear: the
  59-minute-game consequences live here, not in deployment caps.
* ``fatigue_injury_risk_mult`` -- tired/worn players get hurt MORE
  (multiplier >= 1 when gassed or worn). Consumed by GameSim's injury
  decisions (hit-result injury weight, severity) and available to W4/W5's
  event code as the risk multiplier they apply.
* ``is_gassed`` / ``condition_tier`` / thresholds -- consumed by W2's
  deployment weights (defensive import on their side; no hard dependency).

Attribute-scale notes (do not "fix" without re-calibrating consumers):
* stamina / endurance / durability are native 50-90 (1-100 clamps).
  Defaults here are 70 (mid-native), NOT quick_sim's legacy getattr
  default of 10.
* injury_proneness is Player.injury_proneness: 1-100, HIGHER = more prone,
  gauss(45, 20). This is the opposite of player_development_system.py:61's
  separate 5-15 lower=more-prone field on a different class -- never conflate.
* work_rate scale drift (50-85 generated vs 5-20 in test helpers) is left
  alone; this module does not consume work_rate.

Condition bands align with W6's condition_ui.py:
    90-100 Fresh | 70-89 Good | 50-69 Worn | 0-49 Gassed
"""

# ---------------------------------------------------------------------------
# Thresholds / tuning constants (W2 consumes these; keep names stable)
# ---------------------------------------------------------------------------

#: In-game energy below this -> gassed (matches impact_system's <35 gassed
#: hitter tier).
GASSED_ENERGY = 35.0
#: Persistent condition below this -> gassed (matches W6's Gassed band).
GASSED_CONDITION = 50.0
#: Persistent condition below this -> worn (matches W6's Good floor).
WORN_CONDITION = 70.0

#: Skater TOI (minutes) beyond which wear escalates steeply.
HEAVY_TOI_SKATER_MIN = 35.0
#: Goalie TOI (minutes) beyond which wear escalates (regulation is 60).
HEAVY_TOI_GOALIE_MIN = 65.0

#: Condition points lost for a normal-workload game at intensity 1.0.
WEAR_PER_GAME = 2.0
RECOVERY_DAMPING = 0.138388  # softens back-to-back recovery swings
#: Condition points recovered per full rest day (scaled by stamina blend).
RECOVERY_PER_DAY = 2.5
#: In-game energy restored at each intermission (scaled by stamina blend).
INTERMISSION_RECOVERY = 12.0
#: In-game energy restored by a timeout (scaled by stamina blend).
TIMEOUT_RECOVERY = 8.0

#: Condition floor -- wear never drops a player below this in one season's
#: accumulation (bodies break, but nobody hits 0 from TOI alone).
CONDITION_FLOOR = 25.0


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clamp_attr(value, default=70.0):
    """Clamp a 1-100 native attribute; default = mid-native 70."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    if v != v:  # NaN
        return float(default)
    return max(1.0, min(100.0, v))


def _is_goalie(player):
    try:
        pos = getattr(player, "primary_position", None)
        return getattr(pos, "name", "") == "GOALIE"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Canonical per-player state
# ---------------------------------------------------------------------------

def get_condition(player):
    """Persistent season condition 0-100. Additive field on Player; old
    saves without it read 100.0. Never raises."""
    try:
        v = float(getattr(player, "condition", 100.0))
    except (TypeError, ValueError):
        return 100.0
    if v != v:
        return 100.0
    return max(0.0, min(100.0, v))


def _set_condition(player, value):
    try:
        player.condition = max(CONDITION_FLOOR, min(100.0, float(value)))
    except Exception:
        pass
    return get_condition(player)


def get_game_energy(player):
    """Transient per-game energy pool 0-100 (what GameSim drains each tick).
    Additive attr ``game_energy``; defaults to 100. Never raises."""
    try:
        v = float(getattr(player, "game_energy", 100.0))
    except (TypeError, ValueError):
        return 100.0
    if v != v:
        return 100.0
    return max(0.0, min(100.0, v))


def sync_game_energy(player, energy):
    """Write the canonical per-game energy pool (called by the sims as they
    drain/recover energy). Never raises."""
    try:
        player.game_energy = max(0.0, min(100.0, float(energy)))
    except Exception:
        pass


def reset_game_fatigue(player):
    """Reset the per-game energy pool to 100 at puck drop. Called once per
    game per player (GameSim does this on its first tick; quick_sim at game
    start). Does NOT touch persistent condition or last-game TOI -- previous
    games' soreness carries into the new game by design."""
    sync_game_energy(player, 100.0)


# ---------------------------------------------------------------------------
# The shared attribute decision: stamina / endurance / durability blend
# ---------------------------------------------------------------------------

def fatigue_resistance(player):
    """The one fatigue decision both fidelities share.

    Mirrors quick_sim._calculate_fatigue_factor's resistance term:
    (endurance + stamina + durability) / 3 on the native 1-100 scale.
    Never raises.
    """
    e = _clamp_attr(getattr(player, "endurance", 70.0))
    s = _clamp_attr(getattr(player, "stamina", 70.0))
    d = _clamp_attr(getattr(player, "durability", 70.0))
    return (e + s + d) / 3.0


def fatigue_accumulation_mult(player):
    """Multiplier on fatigue accumulation: >1 for low-stamina players (tire
    faster), <1 for iron lungs. Neutral (1.0) at resistance 70, so league-
    average behavior is unchanged -- only differentiation is added.
    Range ~[0.78, 2.33] across plausible inputs. Never raises."""
    try:
        return 70.0 / max(30.0, fatigue_resistance(player))
    except Exception:
        return 1.0


def fatigue_recovery_mult(player):
    """Multiplier on fatigue recovery (timeouts, intermissions, rest days):
    high-stamina players bounce back faster. Neutral at 70, clamped
    [0.5, 1.6]. Never raises."""
    try:
        return max(0.5, min(1.6, fatigue_resistance(player) / 70.0))
    except Exception:
        return 1.0


def injury_proneness_mult(player):
    """Victim-side injury multiplier from Player.injury_proneness (1-100,
    HIGHER = more prone; native ~gauss(45, 20)). 45 -> 1.0, 90 -> 1.5,
    10 -> ~0.6, clamped [0.5, 1.6]. Never raises.

    WARNING: player_development_system.py:61 defines a SEPARATE
    injury_proneness (5-15, lower = more prone) on a different class.
    This function only reads Player.injury_proneness -- do not conflate.
    """
    try:
        p = _clamp_attr(getattr(player, "injury_proneness", 45.0), default=45.0)
    except Exception:
        p = 45.0
    return max(0.5, min(1.6, 0.5 + p / 90.0))


# ---------------------------------------------------------------------------
# Injury-risk multiplier (the sign fix)
# ---------------------------------------------------------------------------

def fatigue_injury_risk_mult(player):
    """Multiplier on injury probability for this player RIGHT NOW.

    Tired/worn players get hurt MORE (>= 1.0 whenever gassed or worn):
      * drained in-game energy -> up to 2.0x at 0 energy
      * worn persistent condition (<80) -> up to ~1.8x at the floor
      * acute soreness from a heavy-minutes last game -> up to 2.0x

    Fresh players return exactly 1.0 (no behavior change when nobody is
    tired). This is the multiplier W4/W5's event code consumes; GameSim's
    hit-result injury weight and severity already apply it. Never raises.
    """
    try:
        energy = get_game_energy(player)
        cond = get_condition(player)
        mult = 1.0 + (100.0 - energy) / 100.0
        mult *= 1.0 + max(0.0, 80.0 - cond) / 100.0 * 1.5
        # Acute: heavy-minutes last game leaves soreness into the next one.
        last_toi = float(getattr(player, "_w3_last_toi_min", 0.0) or 0.0)
        heavy = HEAVY_TOI_GOALIE_MIN if _is_goalie(player) else HEAVY_TOI_SKATER_MIN
        if last_toi > heavy:
            mult *= 1.0 + min(1.0, (last_toi - heavy) / 20.0)
        return round(mult, 3)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Post-game wear-and-tear
# ---------------------------------------------------------------------------

def apply_postgame_wear(player, toi_seconds, game_intensity=1.0, days_rest=2):
    """Season wear-and-tear: one game's TOI costs condition; rest days heal.

    * Wear accrues with TOI relative to a normal workload (20 min skaters,
      60 min goalies) at ``game_intensity``. Durability absorbs wear.
    * Beyond ~35 min (skaters) / ~65 min (goalies) the curve steepens
      ((over/10)^1.5): a 59-minute night costs ~25+ condition -- bodies break.
    * Recovery: ``days_rest`` x RECOVERY_PER_DAY, scaled by the
      stamina/endurance/durability blend (iron lungs bounce back faster).
    * Records ``_w3_last_toi_min`` so fatigue_injury_risk_mult can price
      acute soreness from the last game.

    Skaters who barely played (<=30s, healthy scratches) take no wear but
    still bank rest recovery. Returns the new condition. Never raises.
    """
    try:
        toi_min = max(0.0, float(toi_seconds or 0.0)) / 60.0
    except (TypeError, ValueError):
        toi_min = 0.0
    try:
        intensity = max(0.5, min(1.5, float(game_intensity)))
    except (TypeError, ValueError):
        intensity = 1.0
    try:
        rest = max(0, int(days_rest))
    except (TypeError, ValueError):
        rest = 2

    goalie = _is_goalie(player)
    normal_min = 60.0 if goalie else 20.0
    heavy_min = HEAVY_TOI_GOALIE_MIN if goalie else HEAVY_TOI_SKATER_MIN

    if toi_min > 0.5:
        wear = WEAR_PER_GAME * (toi_min / normal_min) * intensity
        if toi_min > heavy_min:
            over = toi_min - heavy_min
            wear *= 1.0 + (over / 10.0) ** 1.5
        # Durability absorbs wear (high durability -> less damage taken).
        try:
            dur = _clamp_attr(getattr(player, "durability", 70.0))
            wear *= max(0.7, min(1.3, 70.0 / max(30.0, dur)))
        except Exception:
            pass
        cond = get_condition(player) - wear
    else:
        cond = get_condition(player)

    # Rest-day recovery, faster for high-stamina players.
    cond += rest * RECOVERY_PER_DAY * fatigue_recovery_mult(player)

    try:
        player._w3_last_toi_min = toi_min
    except Exception:
        pass
    return _set_condition(player, cond)


def rest_days_after(schedule, team, game_date):
    """Days of rest between ``game_date`` and the team's NEXT scheduled game.

    Reads the ACTUAL schedule date gaps (caleb's EHM-style schedule
    guarantees back-to-backs; do not derive density here). Back-to-back ->
    0. Handles dict entries {'date', 'home_team', 'away_team'} and legacy
    (date, home, away) tuples; teams matched by team_name. Returns 3 when no
    future game is found (end of season), 2 when the schedule is unreadable.
    Never raises.
    """
    def _as_date(d):
        # datetime -> date; date passes through; anything else -> None.
        try:
            if d is None or isinstance(d, str):
                return None
            if callable(getattr(d, "date", None)):
                d = d.date()
            return d if hasattr(d, "year") else None
        except Exception:
            return None

    try:
        gdate = _as_date(game_date)
        team_name = getattr(team, "team_name", team)
        best = None
        for item in schedule or []:
            try:
                if isinstance(item, dict):
                    d, h, a = item.get("date"), item.get("home_team"), item.get("away_team")
                elif isinstance(item, (tuple, list)) and len(item) >= 3:
                    d, h, a = item[0], item[1], item[2]
                else:
                    continue
                d = _as_date(d)
                if d is None or gdate is None or d <= gdate:
                    continue
                hn = getattr(h, "team_name", h)
                an = getattr(a, "team_name", a)
                if team_name != hn and team_name != an:
                    continue
                if best is None or d < best:
                    best = d
            except Exception:
                continue
        if best is None:
            return 3
        return max(0, (best - gdate).days - 1)
    except Exception:
        return 2


def apply_postgame_wear_for_game(home_team, away_team, game_date, schedule,
                                 toi_by_id=None, intensity=1.0):
    """Batch helper: apply post-game wear to both clubs' skaters/goalies.

    ``toi_by_id`` maps player.id -> TOI seconds (GameSim records
    player_toi_seconds per game). Players missing from the map are treated
    as scratches (no wear, rest recovery only). Rest days come from the real
    schedule via rest_days_after. Returns {player_id: new_condition}.
    Never raises.
    """
    out = {}
    try:
        for team in (home_team, away_team):
            try:
                rest = rest_days_after(schedule, team, game_date)
            except Exception:
                rest = 2
            for p in getattr(team, "roster", []) or []:
                try:
                    pid = getattr(p, "id", None)
                    toi = (toi_by_id or {}).get(pid, 0.0) if pid is not None else 0.0
                    out[pid] = apply_postgame_wear(p, toi, intensity, rest)
                except Exception:
                    continue
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Deployment API for W2 (defensive import on their side; no hard dependency)
# ---------------------------------------------------------------------------

def is_gassed(player):
    """True when the player should be pulled / sheltered: in-game energy
    below GASSED_ENERGY (35) or persistent condition below GASSED_CONDITION
    (50, W6's Gassed band). Never raises."""
    try:
        return get_game_energy(player) < GASSED_ENERGY or \
            get_condition(player) < GASSED_CONDITION
    except Exception:
        return False


def is_worn(player):
    """True when the player is carrying wear but not gassed: condition below
    WORN_CONDITION (70, W6's Good floor) while not gassed. Never raises."""
    try:
        c = get_condition(player)
        return c < WORN_CONDITION and c >= GASSED_CONDITION
    except Exception:
        return False


def condition_tier(player):
    """'FRESH' / 'GOOD' / 'WORN' / 'GASSED' -- band labels aligned with W6's
    condition_ui.py floors (90 / 70 / 50). Never raises."""
    try:
        c = get_condition(player)
    except Exception:
        return "GOOD"
    if c >= 90:
        return "FRESH"
    if c >= 70:
        return "GOOD"
    if c >= 50:
        return "WORN"
    return "GASSED"


# ---------------------------------------------------------------------------
# Wave A (2026-10-01, Muck D17/D18/D23/D24): deployment-facing condition reads
# ---------------------------------------------------------------------------

#: D23 -- per-tick bench recovery: energy points restored per second of game
#: time for benched skaters, scaled by fatigue_recovery_mult. A hard ES
#: shift costs ~25 energy (0.55/s x ~45s); a normal 2-3 minute bench sit
#: (~150s) at 0.22/s restores ~33 -- rotation players stay sustainable
#: across three periods, double-shifters and heavy-PK men still gas.
#: The old _update_fatigue docstring promised bench recovery; only
#: intermissions delivered. Never raises.
BENCH_RECOVERY_PER_S = 0.22


def condition_deployment_mult(player):
    """D17 -- persistent-condition factor on deployment quantity.

    A physical fact, not a vibe: applied OUTSIDE the vibe clamp in
    _player_deployment_score. Gassed (<50): 0.85; worn (<70): 0.94;
    fresh (>=90): 1.03; good: 1.00. Playing hurt (D24 tag) costs another
    x0.90 -- the wear shows in his minutes, exactly as Muck ordered.
    Never raises.
    """
    try:
        c = get_condition(player)
        if c < GASSED_CONDITION:
            m = 0.85
        elif c < WORN_CONDITION:
            m = 0.94
        elif c >= 90.0:
            m = 1.03
        else:
            m = 1.00
        if getattr(player, "playing_hurt", False):
            m *= 0.90
        return m
    except Exception:
        return 1.0
