# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Goalie personality system for Puck Dynasty.

Design intent (per Muck, 2026-09-27): a Binnington responds to a game very
differently than a Brodeur. Goalie play is shaped by personality --
temperament, how they handle traffic and adversity, how they mesh with the
goalie coach and the room, and whether they elevate in April. This module
models all of it, and it is also the lever that rebalances league scoring
toward ~2.8 goals per game (from 2.25): exploitable weaknesses (screens on
low-composure goalies), puck-handling turnovers, tilt/blowup asymmetry, and
a youth tax on unready goalies add goals at the margins while elite
technicians still suppress them.

Both sim engines consume the SAME math here so they stay converged:
  - GameSim (simulation.py): applies save_prob_mult inside
    _calculate_save_probability and turnover rolls in the event loop.
  - AdvancedGameSim (main.py): applies goalie_mesh_factor / the inverse of
    save_prob_mult to shot_chance, in the same additive try/except style as
    the impact-tier and perfect-mesh hooks.

All tuning constants live at the top of this file. Nothing here imports
simulation/main -- pure functions only, so there are no import cycles.
"""

import random

# Kill switch for A/B balance testing: when True, every public function
# returns its neutral value (no personality effects). Used by the balance
# harness to measure the system's true contribution.
DISABLED = False

# ---------------------------------------------------------------------------
# Tuning constants -- the scoring-balance levers. Target: ~2.8 GPG league mean.
# ---------------------------------------------------------------------------

# Traffic / screen tax: goalies who don't track through chaos get beat more.
# This is the single biggest scoring lever -- traffic shots are ~25-30% of
# all shots, so a few points of save% here moves the league mean.
TRAFFIC_TAX_LOW_COMPOSURE = 0.900   # composure < 64: -10% on traffic shots
TRAFFIC_TAX_MID_COMPOSURE = 0.940   # composure 64-73: -6.0%
TRAFFIC_BONUS_HIGH_COMPOSURE = 1.000  # composure 74+: no bonus -- everyone gets screened

# Clean looks: temperament shapes EVERY shot, not just traffic. The
# Binnington/Brodeur axis -- fiery goalies over-challenge and get caught
# moving, unorthodox ones are spectacular or swimming, calm technicians are
# always square. Net-negative by design: more beatable than the old model's
# average, which is what moves the league mean.
CLEAN_FIERY = 0.985
CLEAN_UNORTHODOX = 0.980
CLEAN_CALM = 1.002
CLEAN_TECHNICIAN = 1.002

# Temperament x traffic interaction (Binnington vs Brodeur axis).
FIERY_TRAFFIC_BONUS = 1.03    # fiery goalies thrive in chaos
CALM_TRAFFIC_PENALTY = 0.97   # calm technicians want clean looks
UNORTHODOX_TRAFFIC_SWING = 0.05  # Hasek types: +/-5% per game, feast/famine

# Battler trait (Binnington/Hasek): bounce-back and tilt.
BATTLER_BOUNCE_BACK = 1.05       # +5% saves for 5 min after allowing a goal
BATTLER_TRAFFIC_BONUS = 1.04     # loves the blue-paint battle
BATTLER_TILT_GOALS_IN_PERIOD = 3  # shelled threshold that can trigger tilt
BATTLER_TILT_PENALTY = 0.93      # unravelled: -7% the rest of the game

# Technician trait (Price/Lundqvist): never beats himself.
TECHNICIAN_SOFT_GOAL_SUPPRESS = 1.06  # +6% on weak/low-danger shots

# Puck-handling turnovers: bad puck-handlers gift high-danger chances.
# Per-game expected extra HD chances against:
PH_TURNOVER_BASE = 1.2          # at puck_handling <= 58
PH_TURNOVER_SAFE = 0.05         # at puck_handling >= 74 (never quite zero)
PH_TURNOVER_MID_ATTR = 66       # linear interpolation between

# Youth tax: goalies who aren't ready get exposed (supports the
# goalies-develop-later story -- see player_development_system).
YOUTH_TAX_AGE = 23
YOUTH_TAX_GP = 30
YOUTH_TAX_MULT = 0.955           # -4.5% until they've played real games

# Playoff elevator: some goalies turn it on in April.
PLAYOFF_BIG_GAME_MULT = 1.045     # big_game_goalie trait (stacks w/ 1.05 base)
PLAYOFF_FIERY_VET_MULT = 1.02     # fiery + 100+ GP: feeds off the moment
PLAYOFF_CALM_VET_MULT = 1.02      # calm + composure 80+ + 100+ GP: ice water
PLAYOFF_ROOKIE_NERVES = 0.95      # age < 24 and < 50 GP: the moment is big

# Veteran calm (regular season + playoffs): old, composed goalies steady.
VETERAN_CALM_AGE = 32
VETERAN_CALM_MULT = 1.015

# Rebound temperament shift: athletic scramblers kick out more second
# chances; technicians swallow pucks. Per-save upgrade/downgrade probability
# applied to the rebound outcome ladder. Conservative: the average shift is
# ~+0.03, worth roughly +0.2 GPG league-wide.
REBOUND_SHIFT_FIERY = 0.18
REBOUND_SHIFT_UNORTHODOX = 0.27
REBOUND_SHIFT_CALM = -0.09
REBOUND_SHIFT_BATTLER = 0.09
REBOUND_SHIFT_TECHNICIAN = -0.15
REBOUND_SHIFT_POOR_RC = 0.18      # rebound_control < 58
REBOUND_SHIFT_WEAK_RC = 0.09      # rebound_control < 62
REBOUND_SHIFT_ELITE_RC = -0.09    # rebound_control >= 74


# ---------------------------------------------------------------------------
# Rebound temperament
# ---------------------------------------------------------------------------

def rebound_shift(goalie):
    """Net per-save rebound shift: positive = kicks out more second chances.

    Athletic scramblers (fiery/unorthodox) survive on reaction and kick pucks
    into play; technicians (calm, technician trait, elite rebound_control)
    swallow everything. Returns a probability delta applied to the rebound
    outcome ladder in the sim engine.
    """
    if DISABLED:
        return 0.0
    shift = 0.0
    temp = goalie_temperament(goalie)
    if temp == FIERY:
        shift += REBOUND_SHIFT_FIERY
    elif temp == UNORTHODOX:
        shift += REBOUND_SHIFT_UNORTHODOX
    elif temp == CALM:
        shift += REBOUND_SHIFT_CALM
    if _has_trait(goalie, "battler"):
        shift += REBOUND_SHIFT_BATTLER
    if _has_trait(goalie, "technician"):
        shift += REBOUND_SHIFT_TECHNICIAN
    rc = _attr(goalie, "rebound_control")
    if rc < 58:
        shift += REBOUND_SHIFT_POOR_RC
    elif rc < 62:
        shift += REBOUND_SHIFT_WEAK_RC
    elif rc >= 74:
        shift += REBOUND_SHIFT_ELITE_RC
    return max(-0.40, min(0.40, shift))


# ---------------------------------------------------------------------------
# Goalie-coach + goalie-room mesh
# ---------------------------------------------------------------------------

# Goalie-coach mesh: trust builds with tenure; style fit matters.
COACH_TRUST_MAX = 1.02            # fully trusted by his goalie coach
COACH_TRUST_MIN = 0.985           # new coach / stylistic clash
COACH_STYLE_CLASH_PENALTY = 0.99  # fiery goalie + disciplinarian, etc.

# Goalie-room mesh: the room lifts or drags its goalie.
ROOM_LIFT_MAX = 1.015
ROOM_DRAG_MIN = 0.99


# ---------------------------------------------------------------------------
# Temperament
# ---------------------------------------------------------------------------

FIERY = "fiery"          # Binnington / Roy / Hextall: feeds on chaos, can tilt
CALM = "calm"            # Brodeur / Price / Lundqvist: positional, unflappable
UNORTHODOX = "unorthodox"  # Hasek / Thomas: athletic chaos, feast or famine

TEMPERAMENTS = (FIERY, CALM, UNORTHODOX)


def _attr(player, name, default=50.0):
    try:
        return float(getattr(player, name, default) or default)
    except (TypeError, ValueError):
        return float(default)


def _has_trait(player, trait_id):
    try:
        return trait_id in (getattr(player, "traits", None) or [])
    except Exception:
        return False


def assign_goalie_temperament(goalie, rng=None):
    """Assign a temperament from attributes. Called at player generation."""
    rng = rng or random
    stored = getattr(goalie, "goalie_temperament", "") or ""
    if stored in TEMPERAMENTS:
        return stored
    aggr = _attr(goalie, "aggressiveness")
    comp = _attr(goalie, "composure")
    athl = (_attr(goalie, "reflexes") + _attr(goalie, "agility")) / 2.0
    pos = _attr(goalie, "positioning")
    if aggr >= 75 and comp <= 72:
        temp = FIERY  # the true maniacs
    elif athl >= 76 and pos <= 72:
        temp = UNORTHODOX  # athletic chaos, positionally raw
    elif comp >= 74:
        temp = CALM  # ice in the veins
    else:
        temp = rng.choices(TEMPERAMENTS, weights=[0.25, 0.50, 0.25])[0]
    try:
        goalie.goalie_temperament = temp
    except Exception:
        pass
    return temp


def goalie_temperament(goalie):
    t = getattr(goalie, "goalie_temperament", "") or ""
    if t in TEMPERAMENTS:
        return t
    return assign_goalie_temperament(goalie)


# Off-night / locked-in game variance. Rolled once per goalie per game.
NIGHT_OFF_CHANCE = 0.10    # fighting it: the puck looks fast tonight
NIGHT_OFF_MULT = 0.95      # -5% all game
NIGHT_LOCKED_CHANCE = 0.06  # locked in: seeing everything
NIGHT_LOCKED_MULT = 1.03   # +3% all game


def _roll_night(rng):
    r = rng.random()
    if r < NIGHT_OFF_CHANCE:
        return NIGHT_OFF_MULT
    if r < NIGHT_OFF_CHANCE + NIGHT_LOCKED_CHANCE:
        return NIGHT_LOCKED_MULT
    return 1.0


# ---------------------------------------------------------------------------
# Per-game personality state (mirrors the goaltender_fatigue dict pattern)
# ---------------------------------------------------------------------------

def new_game_state(rng=None):
    """Fresh per-goalie, per-game personality state for the sim engines."""
    rng = rng or random
    return {
        "goals_this_period": 0,
        "goals_total": 0,
        "seconds_since_goal": 9999.0,
        "tilted": False,
        # Unorthodox swing is rolled once per game: feast or famine.
        "unorthodox_swing": rng.uniform(-UNORTHODOX_TRAFFIC_SWING,
                                        UNORTHODOX_TRAFFIC_SWING),
        "night": _roll_night(rng),
        "story_flags": set(),
    }


def record_goal_allowed(state, period_just_ended=False):
    """Call when this goalie is beaten. Handles bounce-back + tilt checks."""
    state["goals_total"] = state.get("goals_total", 0) + 1
    state["goals_this_period"] = state.get("goals_this_period", 0) + 1
    state["seconds_since_goal"] = 0.0


def check_tilt(goalie, state, rng=None):
    """Battlers can unravel when shelled. Returns True if tilt just started."""
    if DISABLED:
        return False
    rng = rng or random
    if state.get("tilted"):
        return False
    if not _has_trait(goalie, "battler"):
        return False
    if state.get("goals_this_period", 0) < BATTLER_TILT_GOALS_IN_PERIOD:
        return False
    # Composure saves him; low composure unravels. Fiery is the risk/reward.
    comp = _attr(goalie, "composure")
    tilt_chance = max(0.05, min(0.60, (80.0 - comp) / 100.0 + 0.10))
    if rng.random() < tilt_chance:
        state["tilted"] = True
        state["story_flags"].add("tilt")
        return True
    return False


# ---------------------------------------------------------------------------
# Save probability modifier -- the core per-shot hook
# ---------------------------------------------------------------------------

def save_prob_mult(goalie, shot_ctx, state=None, is_playoff=False,
                   career_gp=0, rng=None):
    """Multiplier on save probability for one shot.

    shot_ctx: dict with:
      traffic (bool): screen / tip / rebound / net-front chaos
      soft (bool):    weak shot, bad angle -- the ones technicians never allow
    state: per-game dict from new_game_state() (may be None for stateless use)
    """
    if DISABLED:
        return 1.0
    rng = rng or random
    mult = 1.0
    comp = _attr(goalie, "composure")
    temp = goalie_temperament(goalie)
    traffic = bool(shot_ctx.get("traffic"))
    soft = bool(shot_ctx.get("soft"))

    # -- Exploitable weakness: tracking through traffic ---------------------
    if traffic:
        if comp < 64:
            mult *= TRAFFIC_TAX_LOW_COMPOSURE
        elif comp < 74:
            mult *= TRAFFIC_TAX_MID_COMPOSURE
        else:
            mult *= TRAFFIC_BONUS_HIGH_COMPOSURE
        # Temperament interaction
        if temp == FIERY:
            mult *= FIERY_TRAFFIC_BONUS
        elif temp == CALM:
            mult *= CALM_TRAFFIC_PENALTY
        elif temp == UNORTHODOX and state is not None:
            mult *= 1.0 + state.get("unorthodox_swing", 0.0)
        # Battler trait: lives for the blue-paint battle
        if _has_trait(goalie, "battler"):
            mult *= BATTLER_TRAFFIC_BONUS

    # -- Clean looks: temperament shapes every shot, not just traffic --------
    if not traffic:
        if temp == FIERY:
            mult *= CLEAN_FIERY
        elif temp == UNORTHODOX:
            mult *= CLEAN_UNORTHODOX
        elif temp == CALM:
            mult *= CLEAN_CALM
        if _has_trait(goalie, "technician"):
            mult *= CLEAN_TECHNICIAN

    # -- Technician: never beaten by the soft one ----------------------------
    if soft and _has_trait(goalie, "technician"):
        mult *= TECHNICIAN_SOFT_GOAL_SUPPRESS

    # -- Bounce-back: battlers respond right after getting scored on ---------
    if state is not None and _has_trait(goalie, "battler"):
        if state.get("seconds_since_goal", 9999.0) <= 300.0 \
                and state.get("goals_total", 0) > 0:
            mult *= BATTLER_BOUNCE_BACK

    # -- Tilt: unravelled battlers leak --------------------------------------
    if state is not None and state.get("tilted"):
        mult *= BATTLER_TILT_PENALTY

    # -- Off night / locked in: the game's form --------------------------------
    if state is not None:
        mult *= state.get("night", 1.0)

    # -- Youth tax ------------------------------------------------------------
    try:
        age = int(getattr(goalie, "age", 99) or 99)
    except (TypeError, ValueError):
        age = 99
    if age <= YOUTH_TAX_AGE and career_gp < YOUTH_TAX_GP:
        mult *= YOUTH_TAX_MULT

    # -- Playoff elevator ------------------------------------------------------
    if is_playoff:
        if _has_trait(goalie, "big_game_goalie"):
            mult *= PLAYOFF_BIG_GAME_MULT
        if career_gp >= 100:
            if temp == FIERY:
                mult *= PLAYOFF_FIERY_VET_MULT
            elif temp == CALM and comp >= 74:
                mult *= PLAYOFF_CALM_VET_MULT
        elif age < 24 and career_gp < 50:
            mult *= PLAYOFF_ROOKIE_NERVES

    # -- Veteran calm -----------------------------------------------------------
    if age >= VETERAN_CALM_AGE and comp >= 74:
        mult *= VETERAN_CALM_MULT

    return max(0.80, min(1.25, mult))


# ---------------------------------------------------------------------------
# Puck-handling turnovers -- the other scoring lever
# ---------------------------------------------------------------------------

def turnover_chance_per_game(goalie):
    """Expected extra high-danger chances gifted per game by bad puck-handling.

    The flip side of the puck_handler trait: goalies who can't play the puck
    turn it over behind the net. The sim engine rolls this once per game and
    injects that many bonus high-danger shots.
    """
    if DISABLED:
        return 0.0
    ph = _attr(goalie, "puck_handling")
    if ph >= 74:
        return PH_TURNOVER_SAFE
    if ph <= 58:
        return PH_TURNOVER_BASE
    frac = (75.0 - ph) / (75.0 - PH_TURNOVER_MID_ATTR)
    return PH_TURNOVER_SAFE + (PH_TURNOVER_BASE - PH_TURNOVER_SAFE) * min(1.0, max(0.0, frac))


def roll_turnovers(goalie, rng=None):
    """Roll actual turnover count for a game (Poisson around the expectation)."""
    rng = rng or random
    lam = turnover_chance_per_game(goalie)
    # Knuth's Poisson sampler -- lam is small (<1), this is cheap.
    L = 2.718281828459045 ** (-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


# ---------------------------------------------------------------------------
# Goalie-coach + goalie-room mesh
# ---------------------------------------------------------------------------

def goalie_coach_factor(goalie, coach):
    """0.985 - 1.02. Trust builds with tenure; style fit matters.

    coach: any object with style/personality attributes (all getattr-guarded).
    """
    if coach is None:
        return 1.0
    factor = 1.0
    # Tenure trust: a goalie who has worked with his coach for years plays free.
    try:
        tenure = int(getattr(coach, "tenure_years",
                             getattr(coach, "years_with_team", 0)) or 0)
    except (TypeError, ValueError):
        tenure = 0
    factor *= 1.0 + min(tenure, 5) * ((COACH_TRUST_MAX - 1.0) / 5.0)
    # Style fit: technicians love structure, fiery goalies chafe under
    # disciplinarians, unorthodox goalies need a coach who lets them be weird.
    temp = goalie_temperament(goalie)
    style = str(getattr(coach, "coaching_style",
                        getattr(coach, "style", "")) or "").lower()
    clash = False
    if temp == FIERY and any(w in style for w in ("disciplinarian", "defensive", "strict")):
        clash = True
    elif temp == CALM and any(w in style for w in ("chaotic", "run-and-gun", "offensive")):
        clash = True
    elif temp == UNORTHODOX and any(w in style for w in ("structured", "system", "rigid")):
        clash = True
    if clash:
        factor *= COACH_STYLE_CLASH_PENALTY
    # A real goalie-coach specialty is gold for development AND game trust.
    specialty = str(getattr(coach, "specialty", "") or "").lower()
    if "goalie" in specialty:
        factor *= 1.01
    return max(COACH_TRUST_MIN, min(1.03, factor))


def goalie_room_factor(goalie, team):
    """0.99 - 1.015. The room lifts its goalie or hangs him out.

    team: any object with leadership/morale-ish attributes (getattr-guarded).
    """
    if team is None:
        return 1.0
    factor = 1.0
    leadership = _attr(team, "leadership", _attr(team, "room_leadership", 60))
    morale = _attr(team, "morale", _attr(team, "team_morale", 60))
    temp = goalie_temperament(goalie)
    # A fiery goalie feeds a strong room and drags a fragile one.
    if temp == FIERY:
        if leadership >= 70:
            factor *= 1.0 + (ROOM_LIFT_MAX - 1.0) * min(1.0, (leadership - 70) / 20.0)
        elif leadership < 55:
            factor *= 1.0 - (1.0 - ROOM_DRAG_MIN) * min(1.0, (55 - leadership) / 20.0)
    # A calm veteran steadies a young group in front of him.
    elif temp == CALM:
        try:
            age = int(getattr(goalie, "age", 0) or 0)
        except (TypeError, ValueError):
            age = 0
        if age >= 30 and _attr(goalie, "composure") >= 78:
            factor *= 1.008
    # Good morale lifts every goalie a little.
    if morale >= 75:
        factor *= 1.005
    elif morale <= 40:
        factor *= 0.997
    return max(ROOM_DRAG_MIN, min(1.02, factor))


def goalie_mesh_factor(goalie, team=None, coach=None, is_playoff=False,
                       career_gp=0):
    """Combined goalie-side mesh multiplier for shot_chance (AdvancedGameSim).

    Returns a SAVE-side multiplier: divide shot_chance by it (same pattern as
    the impact-tier save_prob_mult hook). Encapsulates coach trust, room fit,
    and the playoff elevator so both engines share one number.
    """
    mult = 1.0
    mult *= goalie_coach_factor(goalie, coach)
    mult *= goalie_room_factor(goalie, team)
    if is_playoff:
        # Playoff elevator, stateless version (no per-game state here).
        temp = goalie_temperament(goalie)
        comp = _attr(goalie, "composure")
        try:
            age = int(getattr(goalie, "age", 99) or 99)
        except (TypeError, ValueError):
            age = 99
        if _has_trait(goalie, "big_game_goalie"):
            mult *= PLAYOFF_BIG_GAME_MULT
        if career_gp >= 100:
            if temp == FIERY or (temp == CALM and comp >= 74):
                mult *= 1.02
        elif age < 24 and career_gp < 50:
            mult *= PLAYOFF_ROOKIE_NERVES
    return max(0.90, min(1.10, mult))


# ---------------------------------------------------------------------------
# Scouting-facing summary (for the analytics hub / scout tips)
# ---------------------------------------------------------------------------

def personality_brief(goalie):
    """One-line scout brief on a goalie's personality. For UI/scouting."""
    temp = goalie_temperament(goalie)
    traits = [t for t in ("battler", "technician", "wall", "puck_handler",
                          "big_game_goalie") if _has_trait(goalie, t)]
    bits = {"fiery": "Fiery competitor -- thrives in chaos, can unravel when shelled.",
            "calm": "Calm technician -- positional, unflappable, wants clean looks.",
            "unorthodox": "Unorthodox athlete -- spectacular or shaky, rarely in between."}
    brief = bits.get(temp, "")
    if traits:
        brief += " Traits: " + ", ".join(traits) + "."
    ph = _attr(goalie, "puck_handling")
    if ph < 55:
        brief += " Shaky with the puck -- forecheck his breakouts."
    if getattr(goalie, "generational_goalie", False):
        brief += " GENERATIONAL prospect -- fast-tracked to the show."
    return brief
