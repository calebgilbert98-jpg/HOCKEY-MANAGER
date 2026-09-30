# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Captaincy forges leaders: leadership is built from tenure, results, impact.

Three mechanisms, all additive (the development engine is never touched):

1. TENURE REINFORCEMENT -- holding the C (or A) season after season forges
   leadership by itself, in any situation. Tracked as consecutive seasons
   wearing each letter (``captain_tenure_years`` / ``alternate_tenure_years``),
   stamped per-season so re-runs are idempotent. Losing the letter resets.

2. SITUATION-REFLECTIVE GROWTH -- the same tenure in a good situation forges
   much more than in a bad one. Team results (win pct, playoff rounds, Cup)
   and personal impact (scoring vs league, star selections, clutch tags) feed
   a growth component that tenure AMPLIFIES: a five-year captain who wins a
   Cup grows far more than a first-year captain with the same ring.

3. MENTORSHIP (the Yzerman effect) -- young letter-less players absorb
   leadership from an elite, winning room. The regime teaches only when its
   best letter-wearer is genuinely elite (85+ leadership) AND the team wins;
   high-character kids (determination + teamwork) absorb more. A young player
   who comes up under a legendary captain on a winning team is more likely
   to become a great dressing-room presence later.

Fractional growth is banked (``_leadership_carry``), not rounded away, so a
quiet +0.5 season still compounds. The Toews/Crosby arc: a young captain
(<= 24) gets a youth multiplier, so a 21-year-old C lifting the Cup rockets
toward elite leadership while a 32-year-old C in the same spot barely moves.
Diminishing returns near 100 keep "best leader in the league" rare. Growth
never goes negative here -- leadership earned is kept (matches the
reputation ratchet philosophy).

All constants are conservative and additive. Leadership stays on the
native 1-100 scale, clamped.
"""

from typing import Any, Dict, List, Optional

# ----------------------------------------------------------------------
# Named constants (all additive; no engine weights touched).
# ----------------------------------------------------------------------
TENURE_C_PER_YEAR = 1.0      # flat leadership per season wearing the C
TENURE_A_PER_YEAR = 0.5      # flat leadership per season wearing the A
TENURE_MAX_AMPLIFY_YEARS = 5  # tenure amplifies situation growth up to here
TENURE_SITUATION_AMPLIFY = 0.12  # +12% situation growth per tenure year
SITUATION_ROUND_VALUE = 0.75  # leadership per playoff round won (C)
SITUATION_CUP_BONUS = 1.5   # extra for winning the Cup (C)
SITUATION_WIN_PCT_SCALE = 4.0  # (win_pct - .500) * scale; floored at 0
IMPACT_STAR_VALUE = 0.15    # leadership per weighted star selection
IMPACT_STAR_MAX = 1.5       # cap on the star component
IMPACT_PPG_MULT = 1.25      # ppg >= this x league avg earns the bonus
IMPACT_PPG_BONUS = 1.0
YOUTH_MAX_AGE = 24          # <= this age: the Toews/Crosby arc
YOUTH_MULT = 1.6
PRIME_MULT = 1.0            # 25-31
VETERAN_MIN_AGE = 32        # >= this age
VETERAN_MULT = 0.5
DIMINISHING_DIVISOR = 35.0  # growth *= (100 - leadership) / divisor
ALTERNATE_MULT = 0.5        # alternates get half of a captain's growth
SEASON_GROWTH_CAP = 4        # max leadership gained in one season
ELITE_THRESHOLD = 90        # crossing this as a young letter-wearer is news
ELITE_STORY_MAX_AGE = 25
CUP_CAPTAIN_REP_BONUS = 4   # extra reputation for the Cup-winning captain
# --- Legendary captain (the Toews/Crosby/Yzerman arc, completed) -----------
LEGENDARY_CAPTAIN_TENURE = 5       # seasons wearing the C
LEGENDARY_CAPTAIN_LEADERSHIP = 88  # genuinely elite leader
# --- Mentorship (the Yzerman effect) -------------------------------------
# A young player who spends his formative years in a room run by elite
# leaders -- and sees that regime WIN -- absorbs leadership by osmosis.
# The teachers are the letter group (usually the captain); the learners
# are young players without letters. "Right personalities" on both sides:
# the regime must be genuinely elite, and high-character kids
# (determination + teamwork) absorb more than low-character ones.
MENTOR_MAX_AGE = 24         # learners: formative years only
MENTOR_ELITE_LEADER = 85    # regime bar: best letter-wearer's leadership
MENTOR_WIN_PCT = 0.55       # regime must win, too (or reach the playoffs)
MENTOR_BASE = 1.0           # base annual absorption
MENTOR_CUP_MULT = 1.25      # lifting the Cup together teaches extra


def _weighted_stars(player: Any) -> float:
    try:
        from stars import weighted_star_count as _wsc
        return float(_wsc(player) or 0.0)
    except Exception:
        return 0.0


def _has_clutch_tag(player: Any) -> bool:
    try:
        tags = getattr(player, "clutch_tags", None) or []
        return bool(tags)
    except Exception:
        return False


def _age_mult(age: int) -> float:
    if age <= YOUTH_MAX_AGE:
        return YOUTH_MULT
    if age >= VETERAN_MIN_AGE:
        return VETERAN_MULT
    return PRIME_MULT


def _bank_leadership(player: Any, leadership: float, raw: float) -> int:
    """Add fractional growth to the carry bank; apply whole points.

    Small-but-real growth (a 29-year-old alternate's quiet +0.5) is banked,
    not rounded away -- tenure's promise compounds over seasons instead of
    vanishing to banker's rounding. Returns the applied whole-point delta.
    """
    try:
        carry = float(getattr(player, "_leadership_carry", 0.0) or 0.0)
    except Exception:
        carry = 0.0
    carry += max(0.0, raw)
    whole = int(carry)
    delta = 0
    if whole > 0:
        old_i = int(round(leadership))
        new_i = max(1, min(100, old_i + whole))
        try:
            player.leadership = new_i
        except Exception:
            new_i = old_i
        delta = new_i - old_i
        carry = max(0.0, carry - whole)
        if new_i >= 100:
            carry = 0.0  # at the cap: discard what can never apply
    try:
        player._leadership_carry = carry
    except Exception:
        pass
    return delta


def apply_mentorship_growth(
    player: Any,
    season_year: int,
    win_pct: float = 0.5,
    playoff_rounds_won: int = 0,
    is_champ: bool = False,
    best_letter_leadership: Optional[float] = None,
) -> Dict[str, Any]:
    """The Yzerman effect: young players absorb leadership from an elite,
    winning room.

    Learners are letter-less players aged <= MENTOR_MAX_AGE. The regime
    teaches only when its best letter-wearer is elite (>= 85 leadership)
    AND the team wins (win pct >= .550 or at least one playoff round).
    High-character kids (determination + teamwork) absorb more -- the
    right personalities learn faster. Banked fractionally like letter
    growth; re-runs in the same season no-op via the shared season stamp.
    """
    result: Dict[str, Any] = {"mentorship_delta": 0}
    try:
        if getattr(player, "captaincy", None) in ("C", "A"):
            return result  # letter-wearers have their own path
        try:
            age = int(getattr(player, "age", 99) or 99)
        except Exception:
            age = 99
        if age > MENTOR_MAX_AGE:
            return result
        try:
            best = float(best_letter_leadership or 0.0)
        except Exception:
            best = 0.0
        if best < MENTOR_ELITE_LEADER:
            return result  # no elite regime figure to learn from
        try:
            wp = float(win_pct or 0.5)
        except Exception:
            wp = 0.5
        if wp < MENTOR_WIN_PCT and int(playoff_rounds_won or 0) < 1:
            return result  # the regime has to win for the lesson to land
        if getattr(player, "_mentorship_season", None) == season_year:
            return result  # already absorbed this season's lesson
        # Regime strength: elite leader x winning clip (Cup lifts it more).
        regime = (best / 100.0) * (
            0.5 + 0.5 * min(1.0, max(0.0, wp - 0.5) * 4.0))
        if is_champ:
            regime *= MENTOR_CUP_MULT
        # Character: the right personalities absorb more.
        try:
            det = float(getattr(player, "determination", 50) or 50)
            tw = float(getattr(player, "teamwork", 50) or 50)
        except Exception:
            det, tw = 50.0, 50.0
        personality_mult = 0.5 + ((det + tw) / 2.0) / 100.0
        try:
            leadership = float(getattr(player, "leadership", 50) or 50)
        except Exception:
            leadership = 50.0
        raw = MENTOR_BASE * regime * personality_mult
        raw *= max(0.0, (100.0 - leadership) / DIMINISHING_DIVISOR)
        delta = _bank_leadership(player, leadership, raw)
        try:
            player._mentorship_season = season_year
        except Exception:
            pass
        result["mentorship_delta"] = delta
    except Exception:
        pass
    return result


def _update_tenure(player: Any, season_year: int) -> Dict[str, int]:
    """Advance consecutive-letter tenure. Idempotent per season via stamp.

    Returns {"captain": n, "alternate": n} after the update.
    """
    try:
        cap = int(getattr(player, "captain_tenure_years", 0) or 0)
    except Exception:
        cap = 0
    try:
        alt = int(getattr(player, "alternate_tenure_years", 0) or 0)
    except Exception:
        alt = 0
    try:
        if getattr(player, "_captaincy_growth_season", None) == season_year:
            return {"captain": cap, "alternate": alt}
        letter = getattr(player, "captaincy", None)
        if letter == "C":
            cap += 1
            alt = 0
        elif letter == "A":
            alt += 1
            cap = 0
        else:
            cap = 0
            alt = 0
        player.captain_tenure_years = cap
        player.alternate_tenure_years = alt
        player._captaincy_growth_season = season_year
    except Exception:
        pass
    return {"captain": cap, "alternate": alt}


def apply_captaincy_growth(
    player: Any,
    season_year: int,
    win_pct: float = 0.5,
    playoff_rounds_won: int = 0,
    is_champ: bool = False,
    league_avg_ppg: float = 0.8,
) -> Dict[str, Any]:
    """Grow a letter-wearer's leadership from tenure, results and impact.

    Runs once per player per offseason (season-stamped; re-runs no-op).
    Returns {"letter", "tenure", "leadership_delta", "milestone_story"}.
    """
    result: Dict[str, Any] = {
        "letter": getattr(player, "captaincy", None),
        "tenure": 0,
        "leadership_delta": 0,
        "milestone_story": None,
    }
    try:
        letter = getattr(player, "captaincy", None)
        # Season-stamp: a re-run in the same offseason must not double-apply
        # growth. Read the stamp BEFORE _update_tenure sets it below.
        already_applied = (getattr(player, "_captaincy_growth_season", None)
                           == season_year)
        tenure_map = _update_tenure(player, season_year)
        if letter not in ("C", "A"):
            return result
        is_captain = letter == "C"
        tenure = tenure_map["captain"] if is_captain else tenure_map["alternate"]
        result["tenure"] = tenure
        if already_applied:
            return result

        try:
            age = int(getattr(player, "age", 25) or 25)
        except Exception:
            age = 25
        try:
            leadership = float(getattr(player, "leadership", 50) or 50)
        except Exception:
            leadership = 50.0

        # -- Tenure reinforcement: holding the letter forges, in any
        # -- situation.
        reinforcement = TENURE_C_PER_YEAR if is_captain else TENURE_A_PER_YEAR

        # -- Situation-reflective growth: good situations forge more, and
        # -- tenure amplifies what the situation teaches.
        situation = max(0.0, (float(win_pct or 0.5) - 0.5)
                        * SITUATION_WIN_PCT_SCALE)
        situation += max(0, int(playoff_rounds_won or 0)) * SITUATION_ROUND_VALUE
        if is_champ:
            situation += SITUATION_CUP_BONUS
        amplify = 1.0 + min(tenure, TENURE_MAX_AMPLIFY_YEARS) \
            * TENURE_SITUATION_AMPLIFY

        # -- Personal impact: stars and elite scoring add their own weight.
        impact = min(IMPACT_STAR_MAX, _weighted_stars(player) * IMPACT_STAR_VALUE)
        try:
            stats = getattr(player, "stats", None)
            pts = int(getattr(stats, "points", 0) or 0)
            gp = int(getattr(stats, "games_played", 0) or 0)
            if gp > 0 and league_avg_ppg > 0 \
                    and (pts / gp) >= IMPACT_PPG_MULT * league_avg_ppg:
                impact += IMPACT_PPG_BONUS
        except Exception:
            pass
        if _has_clutch_tag(player):
            impact += IMPACT_PPG_BONUS * 0.5

        # Alternates get roughly half a captain's growth: their tenure
        # reinforcement is already halved (0.5 vs 1.0), and situation +
        # impact are halved on top -- but the flat reinforcement itself
        # is NOT halved twice.
        role_mult = 1.0 if is_captain else ALTERNATE_MULT
        raw = (reinforcement
               + (situation * amplify + impact) * role_mult) \
            * _age_mult(age)
        # Diminishing returns near the top: 90+ barely moves.
        raw *= max(0.0, (100.0 - leadership) / DIMINISHING_DIVISOR)
        raw = min(float(SEASON_GROWTH_CAP), raw)

        old_i = int(round(leadership))
        delta = _bank_leadership(player, leadership, raw)
        result["leadership_delta"] = delta
        if delta > 0:
            new_i = old_i + delta
            # Milestone: a young letter-wearer arrives as an elite leader.
            # Fires once (flagged), and the story names the tenure.
            if (age <= ELITE_STORY_MAX_AGE and old_i < ELITE_THRESHOLD
                    <= new_i
                    and not getattr(player, "_elite_leader_story_told",
                                    False)):
                try:
                    player._elite_leader_story_told = True
                except Exception:
                    pass
                name = getattr(player, "full_name", "The young captain")
                result["milestone_story"] = (
                    f"\u00a9 {name} has grown into one of the league's "
                    f"premier leaders in year {tenure} wearing the "
                    f"\"{letter}\".")
    except Exception:
        pass
    return result


def cup_captain_rep_bonus(player: Any, is_champ: bool = True,
                          season_year: Optional[int] = None) -> int:
    """Extra reputation for the captain who lifts the Cup.

    The whole roster banks award_championship (+8); the C banks a little
    more -- leading a champion is the signature leadership credential.
    Ratchet-safe (pure addition, capped). Only applies when the player's
    team actually won (is_champ). Season-idempotent: when season_year is
    given, re-running offseason processing for the same season never
    double-pays (credited seasons persist on the player, pickle-safe).
    """
    try:
        if not is_champ or getattr(player, "captaincy", None) != "C":
            return int(getattr(player, "reputation", 0) or 0)
        if season_year is not None:
            try:
                credited = getattr(player, "_cup_captain_rep_seasons", None)
                credited = set(credited) if credited else set()
            except Exception:
                credited = set()
            if season_year in credited:
                return int(getattr(player, "reputation", 0) or 0)
            credited.add(season_year)
            try:
                player._cup_captain_rep_seasons = credited
            except Exception:
                pass
        from datetime import date
        import reputation_system as _rs
        _rs.ensure_reputation_fields(player)
        player.reputation = min(
            _rs.REPUTATION_MAX,
            int(player.reputation or 0) + CUP_CAPTAIN_REP_BONUS)
        try:
            player.reputation_history.append({
                "date": date.today().isoformat(),
                "reputation": player.reputation,
                "reason": "stanley_cup_as_captain",
            })
        except Exception:
            pass
        return int(player.reputation)
    except Exception:
        return 0


# ----------------------------------------------------------------------
# Legendary captain: the Toews/Crosby/Yzerman arc, completed.
#
# A legendary captain is not just a long-tenured C or a Cup winner --
# it is the full arc: years wearing the C, genuinely elite leadership,
# AND a Cup lifted as captain. All three are required. A beloved
# long-timer who never won, or a passenger who wore the C on a stacked
# team, does not qualify. Once earned, the status is permanent -- it
# feeds fan opinion (the face of the franchise), team icon status
# (icon_team), and legacy (immortality's career score).
# ----------------------------------------------------------------------
def is_legendary_captain(player: Any) -> bool:
    """True when the captaincy arc is complete."""
    try:
        if int(getattr(player, "captain_tenure_years", 0) or 0) \
                < LEGENDARY_CAPTAIN_TENURE:
            return False
        if int(getattr(player, "leadership", 0) or 0) \
                < LEGENDARY_CAPTAIN_LEADERSHIP:
            return False
        cups_as_captain = getattr(player, "_cup_captain_rep_seasons", None)
        if not cups_as_captain:
            return False
        return True
    except Exception:
        return False


def stamp_legendary_captain(player: Any, team_name: str,
                           season_year: Optional[int] = None) -> bool:
    """Stamp legendary status once. Returns True when newly stamped.

    Stamping sets the permanent status flags AND the player's team icon
    status (``icon_team``): a legendary captain IS the franchise's icon,
    while he is still wearing the sweater -- not only at retirement.
    The icon team is the franchise he captained to glory, so a later
    trade cannot reassign it (the Coffey rule: status is team-specific).
    Re-runs no-op via the flag; the caller raises the news story.
    """
    try:
        if getattr(player, "_legendary_captain", False):
            return False
        if not is_legendary_captain(player):
            return False
        player._legendary_captain = True
        try:
            player._legendary_captain_team = team_name or ""
        except Exception:
            pass
        if season_year is not None:
            try:
                player._legendary_captain_season = int(season_year)
            except Exception:
                pass
        # Team icon status: the face of THIS franchise.
        try:
            if team_name:
                player.icon_team = team_name
        except Exception:
            pass
        return True
    except Exception:
        return False
