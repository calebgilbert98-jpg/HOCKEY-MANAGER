# reputation_system.py
# Player & personnel reputation system for Puck Dynasty.
#
# Two independent axes, FM/EHM-style:
#
#   reputation (0-100)  -- career standing / legacy. A RATCHET: it only ever
#       goes up or stays flat. Veterans never lose it. High leadership feeds
#       it directly, so a near-retirement Joe Thornton-type carries a big
#       reputation as a veteran leader even when his on-ice value has faded.
#       Reputation is about *standing*, not trade value.
#
#   controversy (0-100) -- volatility / character risk. Explosive outbursts,
#       visibly not caring, locker-room behaviour, off-ice incidents. High
#       controversy discounts trade value, hurts locker-room chemistry and
#       draws media heat. Unlike reputation it CAN decay: a clean season
#       cools things down toward the player's personality baseline.
#
# The module is headless-safe (no tkinter) so the sim engine can call it.

import random
import re
from datetime import date
from typing import List, Dict, Optional, Any

# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

VETERAN_AGE = 32            # age at which leadership weighs heaviest
REPUTATION_MAX = 100
CONTROVERSY_MAX = 100

# How much each controversy event type moves the needle (x severity 1-10)
CONTROVERSY_WEIGHTS = {
    "outburst": 2.2,       # explosive outburst at coach / refs / media
    "effort": 1.8,         # visibly not caring, low compete level
    "locker_room": 2.5,    # locker-room behaviour incident
    "off_ice": 2.0,        # off-ice incident
    "holdout": 1.5,        # contract holdout / trade-demand drama
    "suspension": 1.2,      # league suspension (feeds from discipline)
}

# Clean-season cooldown: controversy drifts back toward baseline by this much
CONTROVERSY_DECAY_PER_CLEAN_SEASON = 4

# Reputation tier labels for UI
REPUTATION_TIERS = [
    (90, "Legend"),
    (75, "Star"),
    (60, "Established"),
    (40, "Regular"),
    (20, "Fringe"),
    (0, "Unknown"),
]

CONTROVERSY_TIERS = [
    (75, "Volatile"),
    (50, "Fiery"),
    (25, "Occasional edge"),
    (0, "Model citizen"),
]


# ---------------------------------------------------------------------------
# Field management (save compatibility)
# ---------------------------------------------------------------------------

def ensure_reputation_fields(entity: Any) -> None:
    """Backfill reputation fields on entities loaded from old saves.

    Old pickles predate these fields; without this, attribute access
    raises AttributeError and crashes the load. Safe to call on every load.
    """
    if not hasattr(entity, "reputation"):
        entity.reputation = 0
    if not hasattr(entity, "controversy"):
        entity.controversy = 0
    # Locked identity: dealt once, never re-dealt. No recursion --
    # _deal_base_controversy never calls ensure_reputation_fields.
    if getattr(entity, "base_controversy", None) is None:
        try:
            _deal_base_controversy(entity)
        except Exception:
            entity.base_controversy = 15
    if not hasattr(entity, "controversy_history"):
        entity.controversy_history = []
    if not hasattr(entity, "reputation_history"):
        entity.reputation_history = []
    # Staff-only: leadership (1-20 EHM scale) and team tenure feed the
    # room-status model. Seeded here for old saves; new Staff get real
    # dataclass defaults (see the game_classes patch).
    if hasattr(entity, "role") and not hasattr(entity, "primary_position"):
        if not hasattr(entity, "leadership"):
            entity.leadership = random.randint(8, 18)
        if not hasattr(entity, "years_with_team"):
            entity.years_with_team = random.randint(0, 4)
        if not hasattr(entity, "gm_trust"):
            entity.gm_trust = 70
        if not hasattr(entity, "ambition"):
            entity.ambition = "climb"
        if not hasattr(entity, "favorite_team"):
            entity.favorite_team = ""
        if not hasattr(entity, "control_need"):
            entity.control_need = 50
        if not hasattr(entity, "first_nhl_chair"):
            entity.first_nhl_chair = False
    # League-level bad blood (rivalries follow people across teams).
    if hasattr(entity, "teams") and hasattr(entity, "standings") and not hasattr(entity, "roster"):
        if not hasattr(entity, "rivalries") or entity.rivalries is None:
            entity.rivalries = []
    # Team-level dynamics state (survives saves once the dataclass lands).
    if hasattr(entity, "roster") and hasattr(entity, "staff"):
        if not hasattr(entity, "dynamics_log") or entity.dynamics_log is None:
            entity.dynamics_log = []
        if not hasattr(entity, "line_control") or entity.line_control is None:
            entity.line_control = "coach"


def seed_player_reputation(player: Any) -> int:
    """Initial reputation from draft pedigree. Called at generation time."""
    ensure_reputation_fields(player)
    base = 5
    try:
        # Early picks arrive with hype; parse "Round X, Pick Y"
        import re
        m = re.search(r"Round\s+(\d+)", getattr(player, "draft_position", "") or "")
        if m:
            rnd = int(m.group(1))
            base += max(0, 18 - rnd * 2)   # 1st round ~+16, 7th round ~+4
    except Exception:
        pass
    # High-leadership prospects already look like future captains
    try:
        base += int(getattr(player, "leadership", 50) / 25)  # +0..+4
    except Exception:
        pass
    player.reputation = max(0, min(REPUTATION_MAX, base))
    return player.reputation


def seed_staff_reputation(staff: Any) -> int:
    """Seed a 0-100 career reputation from the legacy 5-15 staff reputation."""
    ensure_reputation_fields(staff)
    legacy = getattr(staff, "reputation", 10)  # legacy 5-15 scale
    # Map 5-15 -> 20-70 so existing staff land mid-range, room to grow
    mapped = int(20 + (max(5, min(15, legacy)) - 5) * 5)
    staff.career_reputation = mapped
    return mapped


# ---------------------------------------------------------------------------
# Reputation updates (RATCHET: never decreases)
# ---------------------------------------------------------------------------

def update_player_reputation(
    player: Any,
    season_points: int = 0,
    games_played: int = 0,
    league_avg_ppg: float = 0.8,
    awards: Optional[List[str]] = None,
    playoff_rounds_won: int = 0,
) -> int:
    """Recompute reputation from this season's body of work.

    The result is ratcheted: ``player.reputation = max(old, new)``.
    Veterans never regress -- a 38-year-old Joe Thornton keeps every bit
    of standing he earned, even in a 20-point season.

    Leadership is a first-class input, weighted heavier for veterans:
    great leaders are remembered as leaders, independent of scoring.

    Captaincy bonus scales with leadership: a 'C' who can't lead the room
    doesn't bank the same standing as a true captain.
    """
    ensure_reputation_fields(player)
    awards = awards or []

    target = 0

    # -- Performance vs league -------------------------------------------
    if games_played > 0:
        ppg = season_points / games_played
        # 1.5x league average pace over a full season ~= star-level year
        perf = (ppg / max(0.01, league_avg_ppg)) * 45
        target += max(0, min(45, perf))

    # -- Awards ------------------------------------------------------------
    award_values = {
        "hart": 12, "norris": 10, "vezina": 10, "art_ross": 10,
        "selke": 6, "calder": 6, "conn_smythe": 12, "stanley_cup": 10,
    }
    for a in awards:
        target += award_values.get(str(a).lower(), 3)

    # -- Playoff success -----------------------------------------------------
    target += min(15, playoff_rounds_won * 4)

    # -- Leadership (the Thornton rule) --------------------------------------
    leadership = getattr(player, "leadership", 50) or 0
    age = getattr(player, "age", 25) or 25
    # Veterans: leadership is worth up to +25. Young players: up to +10.
    # Great leaders bank reputation that outlives their legs.
    if age >= VETERAN_AGE:
        target += (leadership / 100) * 25
    else:
        target += (leadership / 100) * 10

    # -- Captaincy (scaled by leadership) --------------------------------------
    # A figurehead captain banks less than a true leader of men.
    captaincy = getattr(player, "captaincy", None)
    if captaincy == "C":
        target += round(8 * (0.3 + 0.7 * leadership / 100))
    elif captaincy == "A":
        target += round(4 * (0.3 + 0.7 * leadership / 100))

    target = max(0, min(REPUTATION_MAX, int(target)))

    # RATCHET: reputation never goes down.
    if target > player.reputation:
        player.reputation = target
        player.reputation_history.append({
            "date": date.today().isoformat(),
            "reputation": player.reputation,
            "reason": "season_update",
        })
    return player.reputation


def update_staff_reputation(staff: Any, team_win_pct: float = 0.5,
                            championships: int = 0) -> int:
    """Move a staff member's 0-100 career_reputation for the season.

    A .500 season holds steady; winning builds slowly, losing erodes
    (coaches, unlike players, CAN lose standing -- that's the hot seat).
    Championships bank +12. Clamped to 0-100.
    """
    ensure_reputation_fields(staff)
    try:
        current = getattr(staff, "career_reputation", 0) or 0
        # Win% swing capped at +/-5 per season; Cups are the big movers.
        swing = max(-5, min(5, int((team_win_pct - 0.5) * 10)))
        target = max(0, min(100, current + swing + championships * 12))
        if target != current:
            staff.career_reputation = target
            staff.reputation_history.append({
                "date": date.today().isoformat(),
                "reputation": staff.career_reputation,
                "reason": "season_update",
            })
        return staff.career_reputation
    except Exception:
        return getattr(staff, "career_reputation", 0) or 0


# ---------------------------------------------------------------------------
# Controversy
# ---------------------------------------------------------------------------

def controversy_baseline(entity: Any) -> int:
    """Personality baseline controversy drifts back toward.

    The locked base_controversy IS the baseline. Only entities that were
    never dealt a personality fall back to the discipline/teamwork read.
    """
    try:
        locked = getattr(entity, "base_controversy", None)
        if isinstance(locked, int) and locked >= 0:
            return locked
        discipline = getattr(entity, "discipline", 60) or 60
        teamwork = getattr(entity, "teamwork", 60) or 60
        # discipline 1..100 -> baseline 30..0 ; bad teammates add a little
        base = int((100 - discipline) * 0.3 + (100 - teamwork) * 0.1)
        return max(0, min(40, base))
    except Exception:
        return 10


def record_controversy_event(
    entity: Any,
    event_type: str,
    severity: int = 5,
    description: str = "",
    game_date: Optional[str] = None,
) -> int:
    """Log a controversy incident and raise the entity's controversy score.

    event_type: one of "outburst" | "effort" | "locker_room" | "off_ice"
                | "holdout" | "suspension".
    severity: 1-10.

    This is the hook future systems (media, discipline, morale events)
    will call into -- e.g. a post-game outburst, a healthy scratch over
    effort, a leaked locker-room story.
    """
    ensure_reputation_fields(entity)
    weight = CONTROVERSY_WEIGHTS.get(event_type, 1.5)
    severity = max(1, min(10, severity))
    bump = int(round(weight * severity))

    entity.controversy = max(0, min(CONTROVERSY_MAX, entity.controversy + bump))
    entity.controversy_history.append({
        "date": game_date or date.today().isoformat(),
        "type": event_type,
        "severity": severity,
        "description": description,
        "controversy_after": entity.controversy,
    })
    # Cap history so long careers don't bloat saves
    if len(entity.controversy_history) > 50:
        entity.controversy_history = entity.controversy_history[-50:]
    return entity.controversy


def decay_controversy(entity: Any, incidents_this_season: int = 0,
                      team: Any = None, coach: Any = None,
                      win_pct: Optional[float] = None) -> int:
    """Seasonal volatility development.

    Controversy eases halfway toward its scenario target
    (locked base + scenario offset, clamped to +/-25 of base) -- no
    whiplash, identity preserved. Incidents spike it first; then the
    scenario pulls it back. Called from the end-of-season hook.
    """
    ensure_reputation_fields(entity)
    base = controversy_baseline(entity)
    if _is_staff_entity(entity):
        offset, _ = _coach_volatility_offset(entity, team, coach, win_pct)
    else:
        offset, _ = _player_volatility_offset(entity, team, coach, win_pct)
    target = max(0, min(100, base + offset))
    cur = getattr(entity, "controversy", base) or 0
    if incidents_this_season:
        cur = min(100, cur + incidents_this_season * 3)
    entity.controversy = int(round(max(0, min(100, cur + (target - cur) * 0.5))))
    return entity.controversy


# ---------------------------------------------------------------------------
# Derived values: what reputation & controversy DO
# ---------------------------------------------------------------------------

def locker_room_impact(player: Any, team_context: Optional[Dict[str, Any]] = None) -> float:
    """Net locker-room value of a player. Context decides what edge means.

    Without team_context, returns the base read: respected, high-leadership,
    low-drama players stabilize a room; volatile players drag it down.

    With team_context, BOTH things can be true at once for the same player:
    a hard-nosed, high-edge athlete is fuel on a winning team with a strong
    leadership group and poison on a losing, rudderless one.

    team_context keys:
        win_pct: float 0..1 -- the team's winning atmosphere.
        room_leadership: float 0..100 -- average leadership of the room's core.
            Complimentary structure channels edge; its absence lets edge rot.

    The interaction: volatility * presence * atmosphere. Leaders' edge reads
    as intensity (penalized less, redeemed more); low-leadership volatility
    reads as selfish chaos. Returns roughly -0.8 .. +0.9.
    Feed into team chemistry calculations.
    """
    ensure_reputation_fields(player)
    try:
        leadership = (getattr(player, "leadership", 50) or 50) / 100
        rep = (player.reputation or 0) / 100
        vol = (player.controversy or 0) / 100
        age = getattr(player, "age", 25) or 25
        veteran_bonus = 0.1 if age >= VETERAN_AGE else 0.0

        # Leaders' edge is intensity; everyone else's edge is just noise.
        effective_vol = vol * (1.0 - leadership * 0.4)

        if not team_context:
            return round(
                leadership * 0.45 + rep * 0.25 - effective_vol * 0.6 + veteran_bonus, 3
            )

        win_pct = max(0.0, min(1.0, team_context.get("win_pct", 0.5)))
        room_leadership = max(0.0, min(100.0, team_context.get("room_leadership", 50))) / 100
        atmosphere = (win_pct - 0.5) * 2.0          # -1 (losing) .. +1 (winning)
        structure = 0.5 + room_leadership * 0.5    # structured rooms channel edge
        presence = leadership * 0.7 + rep * 0.3    # how much weight the room gives them

        # Atmosphere also deepens/shallows the base volatility penalty:
        # losing rooms make edge rot faster, winning rooms tolerate it.
        penalty_mult = 1.0 - atmosphere * 0.4 * structure
        base = (leadership * 0.45 + rep * 0.25
                - effective_vol * 0.6 * penalty_mult + veteran_bonus)

        # The swing: same player, opposite signs in opposite rooms.
        # ASYMMETRIC: only a leader's edge becomes fuel in a good room
        # (gated on leadership); anyone's volatility rots a losing room.
        lead_gate = leadership if atmosphere > 0 else 1.0
        swing = vol * presence * atmosphere * 2.8 * structure * lead_gate
        return round(base + swing, 3)
    except Exception:
        return 0.0


def award_championship(entity: Any) -> int:
    """Flat reputation bonus for winning the Stanley Cup. Ratchet-safe by
    construction (pure addition, capped at 100). Call at the offseason
    rollover for every player/staff member on the champion team.
    """
    ensure_reputation_fields(entity)
    try:
        if hasattr(entity, "career_reputation"):
            entity.career_reputation = min(100, entity.career_reputation + 8)
            return entity.career_reputation
        entity.reputation = min(REPUTATION_MAX, (entity.reputation or 0) + 8)
        entity.reputation_history.append({
            "date": date.today().isoformat(),
            "reputation": entity.reputation,
            "reason": "stanley_cup",
        })
        return entity.reputation
    except Exception:
        return 0


def trade_value_modifier(player: Any, buyer_is_contender: bool = False) -> float:
    """Multiplier on a player's trade value from reputation dynamics.

    - Controversy discounts: up to -35% at max volatility. GMs pay less
      for a headache, however talented.
    - Veteran-leader premium: contenders pay +15% for a high-leadership,
      high-reputation veteran at the deadline -- the Thornton effect.
      This is NOT general trade value; it only applies to contenders
      shopping for glue guys.
    """
    ensure_reputation_fields(player)
    mod = 1.0
    try:
        mod -= (player.controversy / CONTROVERSY_MAX) * 0.35
        age = getattr(player, "age", 25) or 25
        leadership = getattr(player, "leadership", 50) or 50
        if (
            buyer_is_contender
            and age >= VETERAN_AGE
            and leadership >= 75
            and player.reputation >= 60
        ):
            mod += 0.15
    except Exception:
        pass
    return round(max(0.4, mod), 3)


def contract_ask_modifier(player: Any) -> float:
    """How reputation/controversy shift a player's salary expectations.

    Stars know their worth (+); volatile players with big reputations
    still get paid, but teams bake in risk (-).
    """
    ensure_reputation_fields(player)
    mod = 1.0
    try:
        mod += (player.reputation / REPUTATION_MAX) * 0.25
        mod -= (player.controversy / CONTROVERSY_MAX) * 0.10
    except Exception:
        pass
    return round(max(0.7, mod), 3)


def media_heat(player_or_staff: Any) -> int:
    """0-100 media attention score. High rep + high controversy = circus."""
    ensure_reputation_fields(player_or_staff)
    try:
        rep = player_or_staff.reputation or 0
        vol = player_or_staff.controversy or 0
        # Controversial stars dominate the cycle; quiet grinders don't
        return max(0, min(100, int(rep * 0.4 + vol * 0.8)))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def describe_reputation(entity: Any) -> str:
    ensure_reputation_fields(entity)
    score = getattr(entity, "reputation", 0) or 0
    for threshold, label in REPUTATION_TIERS:
        if score >= threshold:
            return label
    return "Unknown"


def describe_controversy(entity: Any) -> str:
    ensure_reputation_fields(entity)
    score = getattr(entity, "controversy", 0) or 0
    for threshold, label in CONTROVERSY_TIERS:
        if score >= threshold:
            return label
    return "Model citizen"


def reputation_summary(player: Any) -> Dict[str, Any]:
    """One dict for profile windows: reputation, controversy and derived bits."""
    ensure_reputation_fields(player)
    return {
        "reputation": player.reputation,
        "reputation_tier": describe_reputation(player),
        "controversy": player.controversy,
        "controversy_tier": describe_controversy(player),
        "attitude": describe_attitude(player),   # visible personality label
        "locker_room_impact": locker_room_impact(player),
        "media_heat": media_heat(player),
        "contract_loyalty": contract_loyalty(player),
        "social_group": player_social_group(player),
    }


# ---------------------------------------------------------------------------
# Visible attitude
# ---------------------------------------------------------------------------

# controversy is the VISIBLE attitude/volatility attribute (0-100), shown on
# player profiles like any other attribute. Every system that needs to know
# "what kind of character is this guy" reads it: trade requests, contract
# loyalty, relationships, chemistry. Future scenario hooks (outbursts,
# effort issues, leaks) all feed record_controversy_event().
ATTITUDE_LABELS = [
    (80, "Volatile"),
    (60, "Fiery"),
    (40, "Emotional"),
    (20, "Even-keeled"),
    (0, "Model professional"),
]


def describe_attitude(entity: Any) -> str:
    """Visible personality label for profiles and the Morale tab."""
    ensure_reputation_fields(entity)
    score = getattr(entity, "controversy", 0) or 0
    for threshold, label in ATTITUDE_LABELS:
        if score >= threshold:
            return label
    return "Model professional"


# ---------------------------------------------------------------------------
# Character-driven behaviours
# ---------------------------------------------------------------------------

def trade_request_risk(player: Any, team_context: Optional[Dict[str, Any]] = None) -> float:
    """0..1 likelihood this player agitates for a move.

    Volatile players in bad situations ask out; loyal leaders ride it out.
    Feeds the transfer-request logic: roll against this each month for
    unhappy players.
    """
    ensure_reputation_fields(player)
    try:
        vol = (player.controversy or 0) / 100
        leadership = (getattr(player, "leadership", 50) or 50) / 100
        happiness = getattr(player, "happiness", 70) or 70
        ice_concern = getattr(player, "playing_time_concern", 0) or 0

        risk = vol * 0.35
        risk += max(0.0, (70 - happiness) / 100) * 0.5
        risk += (ice_concern / 100) * 0.25
        if team_context:
            win_pct = max(0.0, min(1.0, team_context.get("win_pct", 0.5)))
            risk += max(0.0, (0.45 - win_pct)) * 0.9   # losing pours fuel
        # Loyal leaders don't quit on the room
        if player.controversy < 40:
            risk -= leadership * 0.15
        if getattr(player, "transfer_requested", False):
            risk = min(1.0, risk + 0.3)  # already agitating: likely to repeat
        return round(max(0.0, min(1.0, risk)), 3)
    except Exception:
        return 0.0


def contract_loyalty(player: Any) -> float:
    """0..1 contract loyalty. High loyalty = re-signs cheaper, doesn't hold out.

    Suggested use in contract talks: demand_mult = 1.05 - loyalty * 0.15.
    """
    ensure_reputation_fields(player)
    try:
        leadership = getattr(player, "leadership", 50) or 50
        happiness = getattr(player, "happiness", 70) or 70
        loyalty = (0.55 + leadership * 0.003 - (player.controversy or 0) * 0.005
                   + (happiness - 70) * 0.003)
        return round(max(0.05, min(0.98, loyalty)), 3)
    except Exception:
        return 0.5


def relationship_chemistry(a: Any, b: Any) -> float:
    """-1..1 how well two players get along. Drives social groups and
    line-combination side effects (future)."""
    for p in (a, b):
        ensure_reputation_fields(p)
    try:
        vol_a = (a.controversy or 0)
        vol_b = (b.controversy or 0)
        lead_a = getattr(a, "leadership", 50) or 50
        lead_b = getattr(b, "leadership", 50) or 50

        score = 0.15  # teammates default mildly positive
        if vol_a < 25 and vol_b < 25:
            score += 0.25                              # quiet pros bond
        if abs(vol_a - vol_b) < 15:
            score += 0.20                              # similar temperaments
        if (vol_a >= 60 and lead_b >= 75) or (vol_b >= 60 and lead_a >= 75):
            score -= 0.45                              # leader vs headcase
        # Veteran mentors the kid
        age_a = getattr(a, "age", 25) or 25
        age_b = getattr(b, "age", 25) or 25
        if lead_a >= 80 and age_b <= 24 and vol_b < 40:
            score += 0.20
        if lead_b >= 80 and age_a <= 24 and vol_a < 40:
            score += 0.20
        if getattr(a, "nationality", "") == getattr(b, "nationality", ""):
            score += 0.10
        return round(max(-1.0, min(1.0, score)), 3)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Team hierarchy & social groups (FM-style)
# ---------------------------------------------------------------------------

HIERARCHY_TIERS = ["Team Leaders", "Core Group", "Squad Players", "Fringe"]
HIERARCHY_WEIGHTS = {"Team Leaders": 3.0, "Core Group": 2.0,
                     "Squad Players": 1.0, "Fringe": 0.5}


def _tenure_years(player: Any) -> float:
    tenure = getattr(player, "team_tenure", "") or ""
    if "4+" in tenure:
        return 5.0
    if "3 year" in tenure:
        return 3.0
    if "2 year" in tenure:
        return 2.0
    return 0.5


def hierarchy_score(player: Any) -> float:
    """Influence score: leadership + reputation + tenure. Captains get a bump."""
    ensure_reputation_fields(player)
    try:
        leadership = getattr(player, "leadership", 50) or 50
        score = (leadership * 0.45 + (player.reputation or 0) * 0.35
                 + min(_tenure_years(player), 5) * 3.0)
        if getattr(player, "captaincy", None) == "C":
            score += 8
        elif getattr(player, "captaincy", None) == "A":
            score += 4
        return round(score, 1)
    except Exception:
        return 0.0


def team_hierarchy(roster: List[Any]) -> Dict[str, List[Any]]:
    """FM-style dressing-room hierarchy. Top ~4 by influence lead the room."""
    scored = sorted(((hierarchy_score(p), p) for p in roster),
                    key=lambda t: t[0], reverse=True)
    tiers: Dict[str, List[Any]] = {t: [] for t in HIERARCHY_TIERS}
    for i, (score, p) in enumerate(scored):
        if i < 4 and score >= 55:
            tiers["Team Leaders"].append(p)
        elif score >= 50:
            tiers["Core Group"].append(p)
        elif score >= 30:
            tiers["Squad Players"].append(p)
        else:
            tiers["Fringe"].append(p)
    return tiers


def player_social_group(player: Any) -> str:
    """Primary clique, FM social-groups style. One label per player for v1."""
    ensure_reputation_fields(player)
    try:
        vol = player.controversy or 0
        age = getattr(player, "age", 25) or 25
        if vol >= 55:
            return "Edge group"
        if age >= 32:
            return "Veterans"
        if age <= 23:
            return "Young guns"
        return "Core"
    except Exception:
        return "Core"


def social_groups(roster: List[Any]) -> Dict[str, List[Any]]:
    """Clique breakdown of the room."""
    groups: Dict[str, List[Any]] = {}
    for p in roster:
        groups.setdefault(player_social_group(p), []).append(p)
    return groups


# ---------------------------------------------------------------------------
# Team chemistry: one guy can't ruin a room
# ---------------------------------------------------------------------------

CHEMISTRY_LABELS = [
    (80, "Harmonious"),
    (65, "United"),
    (50, "Functional"),
    (35, "Fractured"),
    (0, "Toxic"),
]


def team_chemistry(roster: List[Any],
                   team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Overall room health, 0-100.

    Impacts are hierarchy-weighted (leaders count 3x, fringe 0.5x), and a
    strong leadership core DAMPENS individual volatility -- one diva cannot
    single-handedly tank a room with a real core. Returns a dict built for
    the Morale tab: score, label, tier breakdown, biggest influences.
    """
    if not roster:
        return {"score": 50, "label": "Functional", "tiers": {}, "influences": []}
    try:
        hierarchy = team_hierarchy(roster)
        leaders = hierarchy["Team Leaders"]
        core_strength = 0.0
        if leaders:
            core_strength = max(0.0, sum(
                locker_room_impact(p, team_context) for p in leaders) / len(leaders))

        weighted_sum = 0.0
        weight_total = 0.0
        influences = []
        for tier, players in hierarchy.items():
            w = HIERARCHY_WEIGHTS[tier]
            for p in players:
                impact = locker_room_impact(p, team_context)
                # Dampening: a strong core absorbs one player's negativity.
                if impact < 0 and tier != "Team Leaders" and core_strength > 0.2:
                    impact = impact / (1.0 + core_strength * 2.5)
                weighted_sum += impact * w
                weight_total += w
                influences.append({
                    "name": getattr(p, "full_name", "Unknown"),
                    "tier": tier,
                    "impact": round(impact, 3),
                    "attitude": describe_attitude(p),
                    "happiness": getattr(p, "happiness", 70),
                })
        overall = weighted_sum / max(0.001, weight_total)
        score = max(0, min(100, int(50 + overall * 55)))
        label = next(lbl for thr, lbl in CHEMISTRY_LABELS if score >= thr)
        influences.sort(key=lambda d: d["impact"])
        return {
            "score": score,
            "label": label,
            "tiers": {t: len(ps) for t, ps in hierarchy.items()},
            "core_strength": round(core_strength, 3),
            "influences": influences,   # sorted worst -> best
        }
    except Exception:
        return {"score": 50, "label": "Functional", "tiers": {}, "influences": []}


# ---------------------------------------------------------------------------
# League perception vs team perception
# ---------------------------------------------------------------------------
# Two different audiences judge every person in hockey:
#   league_perception -- what the other 31 teams, the media and the fans think.
#                      Drives trade interest, hiring appeal, "hot seat" talk.
#   team_perception   -- what his OWN room thinks of him.
#                      Drives chemistry, buy-in, whether he's lost the room.
# They diverge all the time: the box-office diva the league loves but his
# teammates can't stand, or the beloved 4th-liner nobody outside the room
# has heard of. Both are pure functions of stored state (no new fields).

def _staff_100(entity: Any, attr: str, default: int = 10) -> float:
    """Staff 1-20 attribute -> 0-100 scale."""
    try:
        v = getattr(entity, attr, default)
        v = default if v is None else v
        return max(1, min(20, int(v))) * 5
    except Exception:
        return default * 5


def _is_staff(entity: Any) -> bool:
    return hasattr(entity, "role") and not hasattr(entity, "primary_position")


def _role_name(entity: Any) -> str:
    role = getattr(entity, "role", None)
    return str(getattr(role, "value", role) or "")


def _is_head_coach(entity: Any) -> bool:
    return _is_staff(entity) and "Head Coach" in _role_name(entity)


def _is_gm(entity: Any) -> bool:
    return _is_staff(entity) and "General Manager" in _role_name(entity) \
        and "Assistant" not in _role_name(entity)


def league_perception(entity: Any, season_ppg: float = 0.0,
                      league_avg_ppg: float = 0.8,
                      team_context: Optional[Dict[str, Any]] = None) -> float:
    """0-100: how the league (media, fans, other teams) sees this person."""
    ensure_reputation_fields(entity)
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    try:
        if _is_staff(entity):
            score = (entity.career_reputation or 0) * 0.50
            score += (win_pct - 0.5) * 100 * 0.30          # recent results talk
            score += _staff_100(entity, "media_handling") * 0.10
            score += min(100, (getattr(entity, "experience", 5) or 5) * 4) * 0.10
            ywt = getattr(entity, "years_with_team",
                          ctx.get("coach_tenure_years", 1)) or 0
            if win_pct < 0.45 and ywt >= 2:
                score -= 12                                # hot-seat talk
            if (entity.controversy or 0) >= 60:             # polarizing figure
                score += 5 if win_pct >= 0.5 else -8
            return round(max(0, min(100, score)), 1)
        # -- player --
        form = min(100, (season_ppg / max(0.01, league_avg_ppg)) * 50)
        score = (entity.reputation or 0) * 0.55 + form * 0.20
        score += (win_pct - 0.5) * 30                       # contender halo
        vol = entity.controversy or 0
        if vol >= 50:
            # Box office only sells while he's producing; a cold diva is
            # just a headache and the league prices him like one.
            form_factor = min(1.0, season_ppg / max(0.01, league_avg_ppg))
            if (entity.reputation or 0) >= 60:
                score += vol * 0.08 * (0.3 + 0.7 * form_factor)
            elif (entity.reputation or 0) < 40:
                score -= vol * 0.15                         # headcase discount
        return round(max(0, min(100, score)), 1)
    except Exception:
        return 50.0


def team_perception(entity: Any, team_context: Optional[Dict[str, Any]] = None,
                    roster: Optional[List[Any]] = None) -> float:
    """0-100: how his OWN room sees him. The 'lost the room' input."""
    ensure_reputation_fields(entity)
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    try:
        if _is_staff(entity):
            score = (_staff_100(entity, "man_management") * 0.30
                     + _staff_100(entity, "motivating") * 0.25
                     + _staff_100(entity, "leadership") * 0.25
                     + (100 - (entity.controversy or 0)) * 0.20)
            score += (win_pct - 0.5) * 40    # winning covers, losing exposes
            return round(max(0, min(100, score)), 1)
        # -- player --
        leadership = getattr(entity, "leadership", 50) or 50
        effort100 = (locker_room_impact(entity, ctx) + 1) * 50
        tenure_score = min(100, 40 + _tenure_years(entity) * 12)
        score = (leadership * 0.30 + (100 - (entity.controversy or 0)) * 0.25
                 + effort100 * 0.20 + tenure_score * 0.15 + win_pct * 100 * 0.10)
        captaincy = getattr(entity, "captaincy", None)
        if captaincy == "C":
            score += 8 * (0.3 + 0.7 * leadership / 100)   # the letter carries weight
        elif captaincy == "A":
            score += 4 * (0.3 + 0.7 * leadership / 100)
        return round(max(0, min(100, score)), 1)
    except Exception:
        return 50.0


# ---------------------------------------------------------------------------
# Losing the room
# ---------------------------------------------------------------------------
# Real-NHL model. Risk factors combine with noisy-OR (the probabilistically
# honest way: each factor is an independent chance to break the room), then
# mitigations (banked goodwill, beloved-vet shield) multiply the remainder
# down. Returns the probability plus every factor's contribution so the UI
# (and the debugger) can show the receipt.

ROOM_LEVELS = [
    (0.75, "Lost"),
    (0.55, "Fracturing"),
    (0.35, "Strain"),
    (0.0, "Secure"),
]


def _noisy_or(factors: List[float], mitigations: List[float]) -> float:
    risk = 1.0
    for f in factors:
        risk *= 1.0 - max(0.0, min(1.0, f))
    risk = 1.0 - risk
    for m in mitigations:
        risk *= 1.0 - max(0.0, min(1.0, m))
    return max(0.0, min(1.0, risk))


def room_status(entity: Any, team_context: Optional[Dict[str, Any]] = None,
                roster: Optional[List[Any]] = None,
                season_ppg: float = 0.0,
                league_avg_ppg: float = 0.8) -> Dict[str, Any]:
    """Probability this person has lost / is losing the room, with the full
    factor breakdown. Works for head coaches, GMs and players."""
    ensure_reputation_fields(entity)
    ctx = team_context or {}
    roster = roster or []
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    factors: List[tuple] = []
    mitigations: List[tuple] = []
    brash = (entity.controversy or 0) >= 60

    try:
        if _is_staff(entity) and not _is_gm(entity):
            kind = "coach"
            # 1. Losing -- the #1 killer of coaches in real life --------------
            f = min(0.50, max(0.0, 0.55 - win_pct) * 1.5)
            factors.append(("Losing record", round(f, 3)))
            # 2. Shelf life -- the message goes stale (NHL avg ~3 yrs) ---------
            ywt = getattr(entity, "years_with_team",
                          ctx.get("coach_tenure_years", 2)) or 0
            f = min(0.24, max(0.0, ywt - 3) * 0.06)
            factors.append(("Message gone stale", round(f, 3)))
            # 3-5. Can't communicate / motivate / lead -------------------------
            for attr, label, w in (("man_management", "Poor communicator", 0.45),
                                   ("motivating", "Can't motivate", 0.35),
                                   ("leadership", "Not a leader", 0.30)):
                v = getattr(entity, attr, 12) or 12
                f = max(0.0, (12 - v)) / 20 * w
                factors.append((label, round(f, 3)))
            # 6. Discipline mismatch (two-sided, very NHL) ---------------------
            disc = getattr(entity, "discipline", 10) or 10
            if roster:
                avg_age = sum(getattr(p, "age", 27) or 27 for p in roster) / len(roster)
                avg_lead = sum(getattr(p, "leadership", 50) or 50 for p in roster) / len(roster)
                avg_vol = sum((getattr(p, "controversy", 0) or 0) for p in roster) / len(roster)
                if disc >= 15 and avg_age >= 28.5 and avg_lead >= 60:
                    factors.append(("Drill sergeant vs veteran room", 0.14))
                if disc <= 8 and (avg_vol >= 38 or avg_age <= 25):
                    factors.append(("Lost control (soft coach, wild room)", 0.18))
            # 7. The leaders have quit on him ---------------------------------
            if roster:
                leaders = team_hierarchy(roster).get("Team Leaders", [])
                if leaders:
                    lh = sum(getattr(p, "happiness", 70) or 70 for p in leaders) / len(leaders)
                    if lh < 55:
                        factors.append(("Team leaders tuned out", 0.20))
                    elif lh < 65:
                        factors.append(("Team leaders wavering", 0.10))
            # 8. Brash accelerant -- public fights burn faster ----------------
            if brash:
                factors.append(("Brash personality accelerant", 0.10))
            # Mitigation: banked goodwill -------------------------------------
            if (entity.career_reputation or 0) >= 75:
                mitigations.append(("Championship goodwill", 0.25))
            if not _is_head_coach(entity):
                # Assistants don't get fired for the room; cap their risk.
                cap = 0.60
            else:
                cap = 1.0
        elif _is_gm(entity):
            kind = "gm"
            f = min(0.40, max(0.0, 0.55 - win_pct) * 1.2)
            factors.append(("Losing record", round(f, 3)))
            lp = league_perception(entity, team_context=ctx)
            if lp < 45:
                factors.append(("Fan/media pressure", 0.15))
            ywt = getattr(entity, "years_with_team",
                          ctx.get("coach_tenure_years", 2)) or 0
            if ywt >= 4 and (entity.career_reputation or 0) < 55:
                factors.append(("Tenure without results", 0.18))
            if brash:
                factors.append(("Brash GM accelerant", 0.10))
            cap = 1.0
        else:
            kind = "player"
            rep = entity.reputation or 0
            leadership = getattr(entity, "leadership", 50) or 50
            # 1. Production collapse vs expectation ----------------------------
            if rep >= 50 and league_avg_ppg > 0:
                exp_ppg = league_avg_ppg * (0.4 + rep / 60)
                under = max(0.0, 1 - season_ppg / max(0.01, exp_ppg))
                factors.append(("Production collapse", round(under * 0.30, 3)))
            # 2. Controversy ---------------------------------------------------
            factors.append(("Controversy", round((entity.controversy or 0) / 100 * 0.30, 3)))
            # 3. Effort questioned ----------------------------------------------
            if locker_room_impact(entity, ctx) < -0.05:
                factors.append(("Effort questioned", 0.18))
            # 4. Losing ----------------------------------------------------------
            factors.append(("Losing", round(max(0.0, 0.5 - win_pct) * 0.7, 3)))
            # 5. Captain scrutiny -- the C means you own it ----------------------
            scrutiny = 1.0
            if getattr(entity, "captaincy", None) == "C":
                scrutiny = 1.25
            elif getattr(entity, "captaincy", None) == "A":
                scrutiny = 1.10
            if brash and (entity.controversy or 0) >= 65:
                factors.append(("Brash star finger-pointing", 0.08))
            # Mitigation: beloved vet shield ------------------------------------
            if _tenure_years(entity) >= 4 and leadership >= 70:
                mitigations.append(("Beloved veteran shield", 0.35))
            risk = _noisy_or([f for _, f in factors], [m for _, m in mitigations])
            risk = min(1.0, risk * scrutiny)
            if rep < 45 and getattr(entity, "captaincy", None) is None:
                risk = min(risk, 0.30)   # role players don't lose rooms; they get waived
            cap = 1.0
            factors = [(l, v) for l, v in factors]  # keep order

        if kind != "player":
            risk = _noisy_or([f for _, f in factors], [m for _, m in mitigations])
            risk = min(risk, cap)

        level = next(lbl for thr, lbl in ROOM_LEVELS if risk >= thr)
        return {
            "kind": kind,
            "risk": round(risk, 3),
            "level": level,
            "brash": brash,
            "factors": sorted(factors, key=lambda t: t[1], reverse=True),
            "mitigations": [l for l, _ in mitigations],
            "league_perception": league_perception(entity, season_ppg, league_avg_ppg, ctx),
            "team_perception": team_perception(entity, ctx, roster),
        }
    except Exception:
        return {"kind": "unknown", "risk": 0.0, "level": "Secure", "brash": False,
                "factors": [], "mitigations": [],
                "league_perception": 50.0, "team_perception": 50.0}


# ---------------------------------------------------------------------------
# Implications: what "losing the room" DOES
# ---------------------------------------------------------------------------

def room_implications(status: Dict[str, Any], entity: Any,
                      team_context: Optional[Dict[str, Any]] = None,
                      roster: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """Concrete fallout for a room_status result. Areas: media, chemistry,
    trade, personnel, performance. Brash personalities escalate PUBLICLY
    (leaks, circus); quiet ones silently quit (effort drop, no circus)."""
    ensure_reputation_fields(entity)
    level = status.get("level", "Secure")
    kind = status.get("kind", "player")
    brash = status.get("brash", False)
    quiet = (entity.controversy or 0) < 30
    name = getattr(entity, "full_name", "Unknown")
    out: List[Dict[str, Any]] = []
    if level == "Secure":
        return out

    def add(area, text, magnitude):
        out.append({"area": area, "text": text, "magnitude": magnitude})

    # -- shared escalation ladder -------------------------------------------
    if level == "Strain":
        add("media", f"Media starts asking questions about {name}", 5)
        add("chemistry", "Room tension: chemistry drift", -3)
    elif level == "Fracturing":
        add("media", f"'Has {name} lost the room?' becomes the story", 12)
        add("chemistry", "Fracturing room: chemistry hit", -8)
        if kind == "player":
            add("trade", "Unhappy teammates' trade-request risk x1.5", 1.5)
            if getattr(entity, "captaincy", None) == "C":
                add("personnel", "Captaincy under review: strip the C?", 1)
        else:
            add("personnel", "Ownership pressure: win or else", 1)
    else:  # Lost
        add("chemistry", "Lost room: chemistry collapse", -15)
        if kind == "coach":
            add("personnel", f"Recommend termination: {name} should be fired", 1)
            add("media", "Firing watch: every loss is the lead story", 20)
        elif kind == "gm":
            add("personnel", f"Ownership review: {name}'s job in danger", 1)
        else:
            add("trade", f"{name} likely to demand a trade", 1)
            if getattr(entity, "captaincy", None) == "C":
                add("personnel", "Captaincy under review: strip the C?", 1)

    # -- personality split: brash goes public, quiet silently quits ----------
    if level in ("Fracturing", "Lost"):
        if brash:
            add("media", "Brash fallout: leaks to press, media circus", 15)
            add("chemistry", "Distraction penalty: circus drains the room", -5)
        elif quiet:
            add("performance", "Silent quit: effort drops without a sound", -8)

    # -- winning still papers over cracks at the margins ----------------------
    # (risk already prices winning heavily; this only softens Strain noise)
    return out


# ---------------------------------------------------------------------------
# Coaching styles & player engagement styles
# ---------------------------------------------------------------------------
# Every coach has a style derived from his attributes; every player has an
# engagement style derived from his personality. Style x engagement = fit,
# and fit is what the Morale screen shows as "how players respond to coach".

COACHING_STYLES = {
    "drill_sergeant": {
        "label": "Drill Sergeant",
        "description": "Bag skates, accountability, no excuses. Veterans tune it out; kids need it.",
        "restrictiveness": 0.9,
    },
    "players_coach": {
        "label": "Player's Coach",
        "description": "Arm around the shoulder. The room runs itself -- until it doesn't.",
        "restrictiveness": 0.3,
    },
    "tactician": {
        "label": "Tactician",
        "description": "Systems-first, video, structure. Skill gets a leash, not freedom.",
        "restrictiveness": 0.8,
    },
    "motivator": {
        "label": "Motivator",
        "description": "Speeches, emotion, us-against-the-world. Runs hot, burns out.",
        "restrictiveness": 0.4,
    },
    "developer": {
        "label": "Developer",
        "description": "Teacher first. Patience, reps, and a long view -- kids blossom.",
        "restrictiveness": 0.4,
    },
    "balanced": {
        "label": "Balanced",
        "description": "No single gear. Adjusts to the room he has.",
        "restrictiveness": 0.55,
    },
}


def coach_style(coach: Any) -> Dict[str, Any]:
    """Derive the coach's style from his attributes. Returns the style dict
    plus the winning key."""
    ensure_reputation_fields(coach)
    try:
        # Deviation from the NHL-average 10: only DISTINCTIVE traits define
        # a style. An all-average coach is balanced, not a weak motivator.
        d = lambda a: (getattr(coach, a, 10) or 10) - 10  # 1-20 scale
        scores = {
            "drill_sergeant": d("discipline") * 2 + d("motivating") * 0.5 - d("man_management") * 0.5,
            "players_coach": d("man_management") * 2 + d("motivating") * 0.5 - d("discipline") * 0.5,
            "tactician": d("tactical_knowledge") * 2 + d("game_preparation") * 0.5,
            "motivator": d("motivating") * 2 + d("leadership") * 1.5,
            "developer": d("working_with_youngsters") * 2 + d("player_development"),
        }
        best = max(scores, key=scores.get)
        # Nothing distinctive -> balanced.
        if scores[best] < 6:
            best = "balanced"
        style = dict(COACHING_STYLES[best])
        style["key"] = best
        return style
    except Exception:
        style = dict(COACHING_STYLES["balanced"])
        style["key"] = "balanced"
        return style


ENGAGEMENT_STYLES = {
    "needs_guidance": "Young and wild: needs a firm hand and clear structure.",
    "needs_freedom": "Creative skill: thrives with freedom, withers in a trap.",
    "thrives_on_structure": "Detail-driven: loves systems and accountability.",
    "veteran_autonomy": "Been there: wants trust, not micromanagement.",
    "fragile_confidence": "Confidence shot: needs an arm around him.",
    "steady_professional": "Pro's pro: brings it regardless of who's behind the bench.",
}


def engagement_style(player: Any) -> Dict[str, Any]:
    """Derive how this player engages with coaching from his personality."""
    ensure_reputation_fields(player)
    try:
        age = getattr(player, "age", 26) or 26
        vol = player.controversy or 0
        flair = getattr(player, "flair", 50) or 50
        disc = getattr(player, "discipline", 50) or 50
        lead = getattr(player, "leadership", 50) or 50
        happy = getattr(player, "happiness", 70) or 70
        conf = getattr(player, "morale", 10) or 10  # form/confidence, ~1-20
        if age <= 23 and vol >= 45:
            key = "needs_guidance"
        elif flair >= 68 and disc < 50:
            key = "needs_freedom"
        elif disc >= 62 and vol < 35:
            key = "thrives_on_structure"
        elif age >= 32 and lead >= 68:
            key = "veteran_autonomy"
        elif happy < 50 or conf <= 6:
            # Happiness is about the room; morale is about his own game.
            # A happy-but-cold player still needs an arm around him.
            key = "fragile_confidence"
        else:
            key = "steady_professional"
        return {"key": key, "label": key.replace("_", " ").title(),
                "description": ENGAGEMENT_STYLES[key]}
    except Exception:
        return {"key": "steady_professional", "label": "Steady Professional",
                "description": ENGAGEMENT_STYLES["steady_professional"]}


# Style x engagement fit matrix. Positive = buys in, negative = friction.
_COACH_FIT = {
    "drill_sergeant": {"needs_guidance": 0.4, "needs_freedom": -0.5,
                       "thrives_on_structure": 0.4, "veteran_autonomy": -0.2,
                       "fragile_confidence": -0.3, "steady_professional": 0.1},
    "players_coach": {"needs_guidance": -0.2, "needs_freedom": 0.3,
                      "thrives_on_structure": 0.1, "veteran_autonomy": 0.3,
                      "fragile_confidence": 0.4, "steady_professional": 0.1},
    "tactician": {"needs_guidance": 0.2, "needs_freedom": -0.4,
                  "thrives_on_structure": 0.4, "veteran_autonomy": 0.0,
                  "fragile_confidence": 0.0, "steady_professional": 0.2},
    "motivator": {"needs_guidance": 0.1, "needs_freedom": 0.2,
                  "thrives_on_structure": 0.0, "veteran_autonomy": 0.1,
                  "fragile_confidence": 0.3, "steady_professional": 0.1},
    "developer": {"needs_guidance": 0.5, "needs_freedom": 0.1,
                  "thrives_on_structure": 0.1, "veteran_autonomy": -0.1,
                  "fragile_confidence": 0.3, "steady_professional": 0.1},
    "balanced": {"needs_guidance": 0.1, "needs_freedom": 0.1,
                 "thrives_on_structure": 0.1, "veteran_autonomy": 0.1,
                 "fragile_confidence": 0.1, "steady_professional": 0.1},
}


def coach_player_fit(coach: Any, player: Any) -> float:
    """-1..1: how well this player's engagement style fits the coach."""
    try:
        style = coach_style(coach)["key"]
        eng = engagement_style(player)["key"]
        fit = _COACH_FIT.get(style, {}).get(eng, 0.0)
        # Good communicators smooth every edge; bad ones sharpen them.
        mm = getattr(coach, "man_management", 10) or 10
        fit += (mm - 10) / 10 * 0.25
        # Brash player + weak communicator = oil and water.
        if (player.controversy or 0) >= 60 and mm < 10:
            fit -= 0.2
        return round(max(-1.0, min(1.0, fit)), 3)
    except Exception:
        return 0.0


def player_coach_response(player: Any, coach: Any,
                          team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """How THIS player is responding to the coach: bought in -> quit."""
    try:
        # A bond forged in fire (Torts/Werenski arc) outlasts any fit model.
        bonds = getattr(player, "coach_bonds", None) or {}
        if getattr(coach, "id", None) in bonds:
            return {"score": 0.85, "label": "Bought in",
                    "fit": coach_player_fit(coach, player),
                    "engagement": engagement_style(player)["label"],
                    "bond": bonds[getattr(coach, "id")]}
        fit = coach_player_fit(coach, player)
        happy = getattr(player, "happiness", 70) or 70
        score = fit * 0.6 + (happy - 65) / 100 * 0.4
        if score >= 0.30:
            label = "Bought in"
        elif score >= -0.05:
            label = "Neutral"
        elif score >= -0.35:
            label = "Tuning out"
        else:
            label = "Quit on coach"
        return {"score": round(score, 3), "label": label,
                "fit": fit, "engagement": engagement_style(player)["label"]}
    except Exception:
        return {"score": 0.0, "label": "Neutral", "fit": 0.0,
                "engagement": "Steady Professional"}


# ---------------------------------------------------------------------------
# Team dynamics feed
# ---------------------------------------------------------------------------
# The living story of the room: every event that pushes morale up or down,
# stored on the team so it survives saves. The Morale screen renders it
# newest-first with up/down indicators.

def _team_log(team: Any) -> list:
    if not hasattr(team, "dynamics_log") or team.dynamics_log is None:
        team.dynamics_log = []
    return team.dynamics_log


def record_team_event(team: Any, event_type: str, text: str,
                      morale_delta: int = 0, tone: str = "neutral") -> Dict[str, Any]:
    """Append a dynamics event. tone: 'up' | 'down' | 'neutral'."""
    log = _team_log(team)
    event = {"date": date.today().isoformat(), "type": event_type,
             "text": text, "morale_delta": morale_delta, "tone": tone}
    log.append(event)
    del log[:-100]  # keep the story readable
    return event


def get_dynamics_feed(team: Any, limit: int = 30) -> List[Dict[str, Any]]:
    """Newest-first dynamics events."""
    return list(reversed(_team_log(team)[-limit:]))


def _shift_happiness(roster: List[Any], delta: int,
                     predicate=None) -> int:
    """Shift happiness for matching players. Returns count affected."""
    n = 0
    for p in roster:
        try:
            if predicate is None or predicate(p):
                p.happiness = max(0, min(100, (getattr(p, "happiness", 70) or 70) + delta))
                n += 1
        except Exception:
            pass
    return n


def apply_bag_skate(team: Any, coach: Any, roster: List[Any]) -> Dict[str, Any]:
    """Bag skate after a loss. Discipline message; the room hates it.
    Drill sergeants get a pass -- their rooms expect it."""
    style = coach_style(coach)["key"]
    if style == "drill_sergeant":
        n = _shift_happiness(roster, -1)
        text = (f"{getattr(coach, 'full_name', 'Coach')} bag-skated the team after the loss. "
                f"Business as usual under a drill sergeant ({n} affected).")
        delta = -1
    else:
        n = _shift_happiness(roster, -3)
        # Young wild players take it hardest.
        _shift_happiness(roster, -2, lambda p: (getattr(p, "age", 26) or 26) <= 23)
        text = (f"{getattr(coach, 'full_name', 'Coach')} bag-skated the team after the loss. "
                f"The room is fuming ({n} affected).")
        delta = -3
    return record_team_event(team, "bag_skate", text, morale_delta=delta, tone="down")


def apply_inspiring_speech(team: Any, coach: Any, roster: List[Any]) -> Dict[str, Any]:
    """Locker-room speech. Lands only if the coach can actually move a room."""
    mot = getattr(coach, "motivating", 10) or 10
    lead = getattr(coach, "leadership", 10) or 10
    if mot >= 14 or lead >= 14:
        _shift_happiness(roster, 5)
        text = (f"{getattr(coach, 'full_name', 'Coach')} gave an inspiring locker-room speech. "
                f"The room is buzzing.")
        return record_team_event(team, "speech", text, morale_delta=5, tone="up")
    _shift_happiness(roster, 1)
    text = (f"{getattr(coach, 'full_name', 'Coach')} tried a speech. It fell flat.")
    return record_team_event(team, "speech", text, morale_delta=1, tone="neutral")


def apply_great_practice(team: Any, coach: Any, roster: List[Any]) -> Dict[str, Any]:
    """Sharp practice after a loss. Small, honest bounce."""
    _shift_happiness(roster, 2)
    text = (f"Great practice after the loss -- {getattr(coach, 'full_name', 'Coach')} "
            f"had them sharp and focused.")
    return record_team_event(team, "practice", text, morale_delta=2, tone="up")


def apply_mistreat_player(team: Any, coach: Any, player: Any,
                          roster: List[Any],
                          rivalries: Optional[list] = None) -> Dict[str, Any]:
    """Coach mistreats (benches/buries) a player. The target seethes; if he's
    popular, the room notices."""
    ensure_reputation_fields(player)
    name = getattr(player, "full_name", "Unknown")
    player.happiness = max(0, (getattr(player, "happiness", 70) or 70) - 15)
    player.controversy = min(100, (player.controversy or 0) + 5)
    pop = team_perception(player, roster=roster)
    ff = fan_favourite_score(player, team)
    fav = ff["score"] >= 70
    friends = [p for p in roster
               if p is not player and _ensure_relationships(p).get(player.id, 0) >= 50]
    if pop >= 65:
        _shift_happiness(roster, -3, lambda p: p is not player)
        text = (f"{getattr(coach, 'full_name', 'Coach')} buried {name}. "
                f"The room thinks it's unfair -- popular players have long memories.")
        delta = -4
        if rivalries is not None:
            record_coach_player_beef(rivalries, coach, player,
                                     f"buried him unfairly; the room noticed")
    else:
        text = f"{getattr(coach, 'full_name', 'Coach')} buried {name}. Few complaints."
        delta = -1
    if fav:
        _shift_happiness(roster, -2)
        for p in friends:
            p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
        text += (f" {name} is a {ff['tier'].lower()} -- the fans are letting the "
                 f"organization hear it, and his friends in the room aren't happy.")
        delta -= 2
        leaders_backing = any(
            p in team_hierarchy(roster).get("Team Leaders", []) for p in friends)
        if leaders_backing:
            text += " The leadership group is not happy."
            delta -= 1
    return record_team_event(team, "mistreatment", text, morale_delta=delta, tone="down")


def detect_dynamics_issues(team: Any, team_context: Optional[Dict[str, Any]],
                           roster: List[Any], coach: Any) -> List[Dict[str, Any]]:
    """Watch-list: structural problems the numbers can see right now."""
    issues: List[Dict[str, Any]] = []
    try:
        ctx = team_context or {}
        win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
        disc = getattr(coach, "discipline", 10) or 10
        style = coach_style(coach)
        n = max(1, len(roster))
        avg_age = sum(getattr(p, "age", 27) or 27 for p in roster) / n
        avg_vol = sum((getattr(p, "controversy", 0) or 0) for p in roster) / n
        avg_flair = sum(getattr(p, "flair", 50) or 50 for p in roster) / n
        tactic = getattr(team, "tactic_even_strength", "Balanced")

        streak = ctx.get("losing_streak", 0)
        if streak >= 3 and disc >= 13:
            issues.append({"key": "too_tense", "severity": "high",
                           "text": f"Players look tense -- {streak}-game skid under a demanding coach. The room is gripping the sticks."})
        if avg_age <= 25.5 and disc <= 8:
            issues.append({"key": "not_hard_enough", "severity": "high",
                           "text": "Young group, soft practices: the coach isn't demanding enough and it shows."})
        if avg_vol >= 40 and disc <= 9:
            issues.append({"key": "lack_discipline", "severity": "medium",
                           "text": "The room lacks discipline -- too many passengers, not enough accountability."})
        if avg_flair >= 62 and tactic == "Defensive" and style["restrictiveness"] >= 0.7:
            if win_pct >= 0.58:
                issues.append({"key": "no_freedom", "severity": "low",
                               "text": "Skilled group playing a suffocating trap with no freedom... and it's working. Nobody's complaining yet."})
            elif win_pct < 0.45:
                issues.append({"key": "no_freedom", "severity": "high",
                               "text": "Skilled group forced into trap hockey with zero freedom -- and it's NOT working. The skill guys are dying on the vine."})
            else:
                issues.append({"key": "no_freedom", "severity": "medium",
                               "text": "Skilled group in a defensive system: the freedom question is simmering."})
        rs_coach = room_status(coach, ctx, roster)
        if rs_coach["level"] in ("Fracturing", "Lost"):
            issues.append({"key": "coach_tuned_out", "severity": "high",
                           "text": f"Coach is {rs_coach['level'].lower()} the room ({rs_coach['risk']:.0%} risk)."})
        if getattr(team, "line_control", "coach") == "gm" and win_pct >= 0.58:
            issues.append({"key": "gm_overstep", "severity": "medium",
                           "text": "GM is picking the lines on a winning team -- strong personalities are bristling."})
        return issues
    except Exception:
        return issues


# ---------------------------------------------------------------------------
# GM advises coach
# ---------------------------------------------------------------------------

ADVICE_TYPES = {
    "ease_up": "Ease off the players",
    "crack_down": "Demand more in practice",
    "free_the_skill": "Give the skilled players more freedom",
    "more_structure": "Install more structure",
    "play_the_kids": "Play the young players more",
    "shorten_bench": "Lean on the veterans",
}

_ADVICE_FALLOUT = {
    "ease_up": ("Coach eased off at the GM's suggestion -- the room exhales.", 4, None),
    "crack_down": ("Coach cracked down at the GM's suggestion -- practices got sharp, moods didn't.", -2, None),
    "free_the_skill": ("Coach freed up the skill players at the GM's suggestion.", 6, lambda p: (getattr(p, "flair", 50) or 50) >= 68),
    "more_structure": ("Coach installed more structure at the GM's suggestion.", 4, lambda p: engagement_style(p)["key"] == "thrives_on_structure"),
    "play_the_kids": ("Coach is playing the kids at the GM's suggestion.", 5, lambda p: (getattr(p, "age", 26) or 26) <= 23),
    "shorten_bench": ("Coach is leaning on the veterans at the GM's suggestion.", 4, lambda p: (getattr(p, "age", 26) or 26) >= 30),
}


def advise_coach(coach: Any, advice_key: str, team: Any = None,
                 roster: Optional[List[Any]] = None) -> Dict[str, Any]:
    """The GM advises the coach. Whether he listens depends on personality:
    adaptable communicators listen; brash, stubborn coaches take it as an
    insult. Trust (gm_trust) evolves with every exchange."""
    ensure_reputation_fields(coach)
    if not hasattr(coach, "gm_trust") or coach.gm_trust is None:
        coach.gm_trust = 70
    label = ADVICE_TYPES.get(advice_key, advice_key)
    brash = (coach.controversy or 0) >= 60
    try:
        adapt = getattr(coach, "adaptability", 10) or 10
        mm = getattr(coach, "man_management", 10) or 10
        p = (0.35 + (adapt * 5) / 100 * 0.30
             + (100 - (coach.controversy or 0)) / 100 * 0.20
             + (mm * 5) / 100 * 0.15
             + (coach.gm_trust - 70) / 100 * 0.50)
        if brash:
            p *= 0.6  # takes advice as an insult
        p = max(0.05, min(0.95, p))
        listened = random.random() < p
        cname = getattr(coach, "full_name", "Coach")
        if listened:
            coach.gm_trust = min(100, coach.gm_trust + 5)
            text, delta, pred = _ADVICE_FALLOUT.get(advice_key, (f"Coach took the advice: {label}.", 2, None))
            n = _shift_happiness(roster or [], delta, pred)
            if team is not None:
                record_team_event(team, "gm_advice", f"GM advised: {label}. {text} ({n} players lifted).",
                                  morale_delta=delta, tone="up" if delta > 0 else "neutral")
            return {"listened": True, "probability": round(p, 3),
                    "text": f"{cname} listened. {text}", "gm_trust": coach.gm_trust}
        coach.gm_trust = max(0, coach.gm_trust - 8)
        if brash:
            text = f"{cname} bristled at the interference: 'I know my room.' Trust erodes."
        else:
            text = f"{cname} nodded politely... and changed nothing. Trust erodes."
        if team is not None:
            record_team_event(team, "gm_advice", f"GM advised: {label}. {text}",
                              morale_delta=-2, tone="down")
        return {"listened": False, "probability": round(p, 3),
                "text": text, "gm_trust": coach.gm_trust}
    except Exception:
        return {"listened": False, "probability": 0.0, "text": "Advice lost in the noise.",
                "gm_trust": getattr(coach, "gm_trust", 70)}


# ---------------------------------------------------------------------------
# Line control: coach decides, or the GM takes the pen
# ---------------------------------------------------------------------------

def set_line_control(team: Any, who: str,
                     team_context: Optional[Dict[str, Any]] = None,
                     roster: Optional[List[Any]] = None) -> Dict[str, Any]:
    """who: 'coach' | 'gm'. Taking the lines on a WINNING team for no reason
    enrages strong personalities. Doing it on a loser is understood."""
    if not hasattr(team, "line_control") or team.line_control is None:
        team.line_control = "coach"
    who = "gm" if who == "gm" else "coach"
    if team.line_control == who:
        return {"changed": False, "text": f"Line control already with {who}."}
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    roster = roster or []
    team.line_control = who
    if who == "gm":
        if win_pct >= 0.58:
            # Great record, no reason: strong personalities take it personally.
            def strong(p):
                return (p.controversy or 0) >= 55 and (p.reputation or 0) >= 55
            n_strong = 0
            for p in roster:
                ensure_reputation_fields(p)
                try:
                    if strong(p):
                        p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 12)
                        p.controversy = min(100, (p.controversy or 0) + 5)
                        n_strong += 1
                    else:
                        p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
                except Exception:
                    pass
            text = (f"GM seized the lineup pen on a WINNING team ({win_pct:.0%}). "
                    f"{n_strong} strong personalities are furious -- why fix what isn't broken?")
            record_team_event(team, "line_control", text, morale_delta=-6, tone="down")
            return {"changed": True, "text": text, "strong_affected": n_strong}
        _shift_happiness(roster, 3, lambda p: (getattr(p, "happiness", 70) or 70) < 55)
        _shift_happiness(roster, -2, lambda p: (getattr(p, "age", 27) or 27) >= 32)
        text = (f"GM took over the lines ({win_pct:.0%} record). Struggling players welcome the shake-up; "
                f"veterans are wary.")
        record_team_event(team, "line_control", text, morale_delta=1, tone="neutral")
        return {"changed": True, "text": text, "strong_affected": 0}
    _shift_happiness(roster, 2)
    text = "Coach has the lineup pen back. Clarity restored."
    record_team_event(team, "line_control", text, morale_delta=2, tone="up")
    return {"changed": True, "text": text, "strong_affected": 0}


# ---------------------------------------------------------------------------
# Coach ambitions, control need, and amicable line control
# ---------------------------------------------------------------------------
# Not every coach hears "I'm taking the lines" the same way. Babcock hears a
# threat; Cooper hears a conversation; a rookie promoted from the AHL hears
# the GM who believed in him. control_need (0-100) is the axis.

COACH_AMBITIONS = {
    "stanley_cup": "Win a Cup -- everything else is noise.",
    "climb": "Climb the ladder -- AHL success, then an NHL chair.",
    "developer": "Build the next generation.",
    "hometown": "Coach his boyhood team before he's done.",
    "lifer": "Content where he is; loves the day-to-day.",
}


def control_label(coach: Any) -> str:
    cn = getattr(coach, "control_need", 50) or 50
    if cn >= 70:
        return "Authoritarian"
    if cn >= 45:
        return "Demanding"
    if cn >= 25:
        return "Collaborative"
    return "Player-led"


def _dry_spell(ctx: Dict[str, Any]) -> bool:
    return ctx.get("losing_streak", 0) >= 3 or ctx.get("win_pct", 0.5) < 0.45


def preview_line_control_discussion(coach: Any,
                                    team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The GM sits the coach down: 'we're in a dry spell, let me try something
    with the lines.' Returns the coach's likely response BEFORE it happens,
    so the Morale screen can show it FM-style."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    cn = getattr(coach, "control_need", 50) or 50
    trust = getattr(coach, "gm_trust", 70) or 70
    adapt = getattr(coach, "adaptability", 10) or 10
    dry = _dry_spell(ctx)
    rookie = bool(getattr(coach, "first_nhl_chair", False)) and \
        (getattr(coach, "years_with_team", 0) or 0) <= 2
    cname = getattr(coach, "full_name", "Coach").split()[0]

    if rookie:
        return {"tone": "welcomes", "penalty": 0, "trust_delta": 3,
                "text": f"{cname} welcomes it -- you believed in him when nobody else did. "
                        f"He'll try anything within reason for the team (and his career)."}
    if cn <= 35:
        if dry:
            return {"tone": "accepts", "penalty": 0, "trust_delta": 2,
                    "text": f"{cname} gets it -- dry spell, willing to try anything. No hard feelings."}
        return {"tone": "accepts", "penalty": -2, "trust_delta": 0,
                "text": f"{cname} is a little surprised (things are fine), but he trusts you."}
    if cn < 70:
        if dry:
            return {"tone": "wary", "penalty": -2, "trust_delta": -2,
                    "text": f"{cname} is wary -- it's his room -- but the results force his hand."}
        return {"tone": "wary", "penalty": -5, "trust_delta": -4,
                "text": f"{cname} doesn't love being second-guessed while things are working."}
    # Authoritarian: Babcock hears a threat no matter how nicely it's phrased.
    if dry:
        return {"tone": "bristles", "penalty": -4, "trust_delta": -6,
                "text": f"{cname} bristles. Even asked nicely, he hears: you don't trust him."}
    return {"tone": "furious", "penalty": -8, "trust_delta": -10,
            "text": f"{cname} is furious. Taking his lines is taking his authority -- he'll remember this."}


def set_line_control(team: Any, who: str,
                     team_context: Optional[Dict[str, Any]] = None,
                     roster: Optional[List[Any]] = None,
                     coach: Any = None,
                     approach: str = "seize") -> Dict[str, Any]:
    """who: 'coach' | 'gm'. approach: 'seize' (nuclear) | 'discuss' (amicable:
    'we're in a dry spell, let me try something'). Discuss avoids major
    penalties when the coach's personality allows it."""
    if not hasattr(team, "line_control") or team.line_control is None:
        team.line_control = "coach"
    who = "gm" if who == "gm" else "coach"
    if team.line_control == who:
        return {"changed": False, "text": f"Line control already with {who}."}
    ctx = team_context or {}
    win_pct = max(0.0, min(1.0, ctx.get("win_pct", 0.5)))
    roster = roster or []
    team.line_control = who

    if who == "coach":
        _shift_happiness(roster, 2)
        text = "Coach has the lineup pen back. Clarity restored."
        record_team_event(team, "line_control", text, morale_delta=2, tone="up")
        return {"changed": True, "text": text, "approach": approach}

    # ---- GM takes the pen ----
    if approach == "discuss" and coach is not None:
        prev = preview_line_control_discussion(coach, ctx)
        coach.gm_trust = max(0, min(100, (getattr(coach, "gm_trust", 70) or 70) + prev["trust_delta"]))
        pen = prev["penalty"]
        if pen:
            _shift_happiness(roster, pen)
        tone = "up" if prev["tone"] in ("welcomes", "accepts") else "down"
        text = f"GM discussed the lines with {getattr(coach, 'full_name', 'Coach')}. {prev['text']}"
        record_team_event(team, "line_control", text,
                          morale_delta=pen, tone=tone)
        return {"changed": True, "text": text, "approach": "discuss",
                "tone": prev["tone"], "strong_affected": 0}

    # ---- seize (nuclear option, unchanged) ----
    if win_pct >= 0.58:
        def strong(p):
            return (p.controversy or 0) >= 55 and (p.reputation or 0) >= 55
        n_strong = 0
        for p in roster:
            ensure_reputation_fields(p)
            try:
                if strong(p):
                    p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 12)
                    p.controversy = min(100, (p.controversy or 0) + 5)
                    n_strong += 1
                else:
                    p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
            except Exception:
                pass
        text = (f"GM seized the lineup pen on a WINNING team ({win_pct:.0%}). "
                f"{n_strong} strong personalities are furious -- why fix what isn't broken?")
        record_team_event(team, "line_control", text, morale_delta=-6, tone="down")
        return {"changed": True, "text": text, "approach": "seize",
                "strong_affected": n_strong}
    _shift_happiness(roster, 3, lambda p: (getattr(p, "happiness", 70) or 70) < 55)
    _shift_happiness(roster, -2, lambda p: (getattr(p, "age", 27) or 27) >= 32)
    text = (f"GM took over the lines ({win_pct:.0%} record). Struggling players welcome the shake-up; "
            f"veterans are wary.")
    record_team_event(team, "line_control", text, morale_delta=1, tone="neutral")
    return {"changed": True, "text": text, "approach": "seize", "strong_affected": 0}


def coach_job_appeal(coach: Any, team: Any,
                     team_context: Optional[Dict[str, Any]] = None,
                     is_promotion: bool = False) -> Dict[str, Any]:
    """0-100: how badly does this coach want THIS job? Drives hiring logic."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    score = 50
    reasons: List[str] = []
    tname = getattr(team, "team_name", "")
    ambition = getattr(coach, "ambition", "climb") or "climb"

    if (getattr(coach, "favorite_team", "") or "") == tname:
        score += 30
        reasons.append("Boyhood team -- he'd run through a wall for this crest.")
        if ambition == "hometown":
            score += 10
            reasons.append("It's his stated life's ambition.")
    if ambition == "stanley_cup":
        if ctx.get("win_pct", 0.5) >= 0.58:
            score += 15
            reasons.append("Contender -- a Cup is within reach.")
        else:
            score -= 10
            reasons.append("Rebuild -- wastes his window.")
    elif ambition == "climb" and is_promotion:
        score += 12
        reasons.append("A step up the ladder.")
    elif ambition == "developer":
        score += 8
        reasons.append("Likes building -- roster age fits." if ctx.get("avg_age", 27) <= 26
                       else "Wants young players to mold.")
    elif ambition == "lifer":
        score -= 8
        reasons.append("Content where he is.")
    score = max(0, min(100, score))
    return {"score": score, "reasons": reasons, "ambition": ambition,
            "ambition_label": COACH_AMBITIONS.get(ambition, ambition)}


def staffer_from_retired_player(player: Any, teams: List[Any]) -> Dict[str, Any]:
    """A player hangs them up and wants to coach. Carry what matters: his
    leadership, his boyhood team, and the logic that a Suzuki wants the Habs."""
    ensure_reputation_fields(player)
    attrs: Dict[str, Any] = {}
    attrs["leadership"] = max(8, min(18, int((getattr(player, "leadership", 50) or 50) / 100 * 18)))
    # Favorite team: 40% the sweater he retires in, else a random boyhood team.
    import random as _r
    tnames = [getattr(t, "team_name", "") for t in (teams or []) if getattr(t, "team_name", "")]
    fav = ""
    if tnames:
        last_team = getattr(player, "last_team_name", "") or ""
        if last_team in tnames and _r.random() < 0.40:
            fav = last_team
        else:
            fav = _r.choice(tnames)
    attrs["favorite_team"] = fav
    attrs["ambition"] = "hometown" if fav and _r.random() < 0.5 else "climb"
    attrs["control_need"] = max(10, min(90, int((getattr(player, "controversy", 30) or 30) * 0.8 + 20)))
    attrs["controversy"] = getattr(player, "controversy", 0) or 0
    # The man's nature follows him behind the bench: a hothead player
    # becomes a stubborn coach. And he keeps his pipeline -- the last
    # sweater he wore is where his guys are.
    generate_personality(player)
    attrs["base_controversy"] = getattr(player, "base_controversy", 20)
    last = getattr(player, "last_team_name", "") or getattr(player, "team_name", "")
    attrs["connections"] = [last] if last else []
    return attrs


# ---------------------------------------------------------------------------
# Rivalries & bad blood
# ---------------------------------------------------------------------------
# FM24-style favourite/rival staff logic, extended: coach-coach, coach-player,
# GM-coach, GM-agent, player-player, and team-team (regional, playoff, brawl).
# Stored on the league (league.rivalries) so bad blood follows people when
# they change teams. Decay is personality-dependent: grudge-holders never
# really let go; career-cost (a lost Cup, a firing) keeps it hot.

RIVALRY_KINDS = ("coach_coach", "coach_player", "gm_coach", "gm_agent",
                 "player_player", "team_team")

RIVALRY_ORIGINS = ("brawl_game", "playoff_series", "major_injury", "firing",
                   "heavy_hits", "award_race", "regional", "mistreatment",
                   "gm_power_struggle", "contract_dispute")

# The classics. Regional hate never fully dies.
REGIONAL_RIVALRIES = frozenset([
    ("Calgary Flames", "Edmonton Oilers"),
    ("Toronto Maple Leafs", "Ottawa Senators"),
    ("Toronto Maple Leafs", "Montreal Canadiens"),
    ("Boston Bruins", "Montreal Canadiens"),
    ("New York Rangers", "New York Islanders"),
    ("New York Rangers", "New Jersey Devils"),
    ("Philadelphia Flyers", "Pittsburgh Penguins"),
    ("Pittsburgh Penguins", "Washington Capitals"),
    ("Chicago Blackhawks", "St. Louis Blues"),
    ("Los Angeles Kings", "Anaheim Ducks"),
    ("Florida Panthers", "Tampa Bay Lightning"),
    ("Vancouver Canucks", "Edmonton Oilers"),
    ("Colorado Avalanche", "Vegas Golden Knights"),
    ("Dallas Stars", "St. Louis Blues"),
])


def _ekey(entity: Any) -> tuple:
    """Stable identity key: ('player', id) | ('staff', id) | ('team', name) | ('gm', team) | ('agent', name)."""
    try:
        if isinstance(entity, str):
            return ("agent", entity)
        if hasattr(entity, "primary_position"):
            return ("player", getattr(entity, "id", getattr(entity, "full_name", "?")))
        if hasattr(entity, "role"):
            return ("staff", getattr(entity, "id", getattr(entity, "full_name", "?")))
        if hasattr(entity, "roster") and hasattr(entity, "team_name"):
            return ("team", getattr(entity, "team_name", "?"))
        if hasattr(entity, "gm_name"):
            return ("gm", getattr(entity, "team_name", "?"))
    except Exception:
        pass
    return ("unknown", str(entity))


def _ename(entity: Any) -> str:
    try:
        if isinstance(entity, str):
            return entity
        if hasattr(entity, "full_name"):
            return getattr(entity, "full_name", "?")
        if hasattr(entity, "team_name"):
            return getattr(entity, "team_name", "?")
    except Exception:
        pass
    return "?"


def _rivalry_store(league: Any) -> list:
    if not hasattr(league, "rivalries") or league.rivalries is None:
        league.rivalries = []
    return league.rivalries


def add_rivalry(rivalries: list, a: Any, b: Any, kind: str, intensity: int,
                origin: str, story: str, grudge: int = 50,
                career_cost: int = 0) -> Dict[str, Any]:
    """Add (or heat up) a rivalry. Merges with an existing one between the
    same pair: intensity takes the max, stories accumulate."""
    ka, kb = _ekey(a), _ekey(b)
    if ka == kb:
        return {}
    # Canonical ordering so (a,b) == (b,a).
    if ka > kb:
        ka, kb, a, b = kb, ka, b, a
    for r in rivalries:
        if r["a"] == ka and r["b"] == kb and r["kind"] == kind:
            r["intensity"] = max(r["intensity"], max(0, min(100, intensity)))
            r["grudge"] = max(r["grudge"], grudge)
            r["career_cost"] = max(r["career_cost"], career_cost)
            if story and story not in r["story"]:
                r["story"] = r["story"] + " " + story
            return r
    rec = {"a": ka, "b": kb, "a_name": _ename(a), "b_name": _ename(b),
           "kind": kind, "intensity": max(0, min(100, intensity)),
           "origin": origin, "story": story, "date": date.today().isoformat(),
           "grudge": max(0, min(100, grudge)),
           "career_cost": max(0, min(100, career_cost))}
    rivalries.append(rec)
    return rec


def get_rivalries_for(rivalries: list, entity: Any,
                      min_intensity: int = 1) -> List[Dict[str, Any]]:
    k = _ekey(entity)
    return sorted(
        [r for r in rivalries
         if (r["a"] == k or r["b"] == k) and r["intensity"] >= min_intensity],
        key=lambda r: -r["intensity"])


def rivalry_between(rivalries: list, a: Any, b: Any,
                    kind: Optional[str] = None) -> Optional[Dict[str, Any]]:
    ka, kb = _ekey(a), _ekey(b)
    if ka > kb:
        ka, kb = kb, ka
    for r in rivalries:
        if r["a"] == ka and r["b"] == kb and (kind is None or r["kind"] == kind):
            return r
    return None


def decay_rivalries(rivalries: list, years: int = 1) -> int:
    """Offseason decay. Grudge-holders (high controversy/grudge) and people it
    cost something real (career_cost) barely cool off. Returns count removed."""
    removed = 0
    for r in list(rivalries):
        try:
            # Regional hate has a floor: it never fully dies.
            floor = 30 if r["origin"] == "regional" else 0
            base = 8 * years
            slow = (1 - r["grudge"] / 150.0) * (1 - r["career_cost"] / 200.0)
            r["intensity"] = max(floor, r["intensity"] - base * max(0.15, slow))
            if r["intensity"] <= 5 and floor == 0:
                rivalries.remove(r)
                removed += 1
        except Exception:
            pass
    return removed


def bury_hatchet(rivalries: list, a: Any, b: Any, reason: str = "") -> bool:
    """Explicitly end it (won together, shook hands, time healed)."""
    r = rivalry_between(rivalries, a, b)
    if r:
        rivalries.remove(r)
        return True
    return False


def seed_regional_rivalries(rivalries: list, teams: List[Any]) -> int:
    """Battle of Alberta etc. Intensity 55, high grudge: regional hate endures."""
    names = {getattr(t, "team_name", ""): t for t in (teams or [])}
    n = 0
    for n1, n2 in REGIONAL_RIVALRIES:
        if n1 in names and n2 in names:
            add_rivalry(rivalries, names[n1], names[n2], "team_team", 55,
                        "regional",
                        f"{n1} vs {n2}: regional hate. The building shakes for these games.",
                        grudge=75)
            n += 1
    return n


def record_brawl_game(rivalries: list, team_a: Any, team_b: Any,
                      coach_a: Any, coach_b: Any,
                      aggressor: str = "a", fights: int = 3) -> List[Dict[str, Any]]:
    """A coach sends his team out to punish the other: heavy hits, fights.
    The coaches carry it with them even if they change teams."""
    out = []
    agg_coach = coach_a if aggressor == "a" else coach_b
    vic_coach = coach_b if aggressor == "a" else coach_a
    out.append(add_rivalry(
        rivalries, agg_coach, vic_coach, "coach_coach", 45, "brawl_game",
        f"{_ename(agg_coach)} sent his team to punish {_ename(vic_coach)}'s: "
        f"{fights} fights, bad blood everywhere.",
        grudge=65))
    out.append(add_rivalry(
        rivalries, team_a, team_b, "team_team",
        30, "brawl_game",
        f"Brawl game: {fights} fights. These teams don't like each other.",
        grudge=55))
    return out


def record_playoff_series(rivalries: list, winner: Any, loser: Any,
                          games: int = 7, upset: bool = False) -> List[Dict[str, Any]]:
    out = []
    heat = 20 + (10 if games >= 7 else 0) + (10 if upset else 0)
    story = (f"Playoff series: {_ename(winner)} over {_ename(loser)} in {games}."
             + (" Seven games. Nobody forgot." if games >= 7 else "")
             + (" The upset stung." if upset else ""))
    out.append(add_rivalry(rivalries, winner, loser, "team_team", heat,
                           "playoff_series", story, grudge=60,
                           career_cost=40 if games >= 7 else 20))
    return out


def record_major_injury(rivalries: list, injured: Any, hitter: Any,
                        season_ending: bool = False) -> Dict[str, Any]:
    return add_rivalry(
        rivalries, injured, hitter, "player_player", 50, "major_injury",
        f"{_ename(hitter)} ended {_ename(injured)}'s "
        f"{'season' if season_ending else 'night'}. The room wants payback.",
        grudge=70, career_cost=60 if season_ending else 25)


def record_firing(rivalries: list, coach: Any, team: Any) -> Dict[str, Any]:
    """The firing: coach blames the GM. Follows the coach to his next job."""
    gm_name = f"{getattr(team, 'gm_name', 'GM')} ({getattr(team, 'team_name', '')})"
    grudge = min(90, 40 + (getattr(coach, "controversy", 0) or 0) // 2)
    return add_rivalry(
        rivalries, coach, gm_name, "gm_coach", 55, "firing",
        f"{_ename(coach)} was fired by {gm_name}. He blames the front office, not the room.",
        grudge=grudge, career_cost=50)


def record_award_race(rivalries: list, pa: Any, pb: Any, award: str) -> Dict[str, Any]:
    return add_rivalry(
        rivalries, pa, pb, "player_player", 25, "award_race",
        f"{_ename(pa)} vs {_ename(pb)}: {award} race got personal.",
        grudge=35)


def record_coach_player_beef(rivalries: list, coach: Any, player: Any,
                             reason: str) -> Dict[str, Any]:
    return add_rivalry(
        rivalries, coach, player, "coach_player", 40, "mistreatment",
        f"{_ename(coach)} vs {_ename(player)}: {reason}",
        grudge=55)


def record_agent_dispute(rivalries: list, agent_name: str, team: Any,
                         player: Any, issue: str) -> Dict[str, Any]:
    """GM-agent-player triangle: holdouts, lowball offers, tampering whispers."""
    gm_name = f"{getattr(team, 'gm_name', 'GM')} ({getattr(team, 'team_name', '')})"
    return add_rivalry(
        rivalries, agent_name,
        f"{gm_name} // {_ename(player)}", "gm_agent", 35, "contract_dispute",
        f"{agent_name} vs {gm_name} over {_ename(player)}: {issue}",
        grudge=45)


def get_rivalry_heat(rivalries: list, team_a: Any, team_b: Any,
                     coach_a: Any = None, coach_b: Any = None) -> Dict[str, Any]:
    """0-100 bad blood between two teams right now. Engine hook: high heat
    means more hits, more fights, tighter games."""
    heat = 0
    parts = []
    r = rivalry_between(rivalries, team_a, team_b, "team_team")
    if r:
        heat = max(heat, r["intensity"])
        parts.append(f"{r['a_name']} vs {r['b_name']}: {r['intensity']}")
    if coach_a is not None and coach_b is not None:
        rc = rivalry_between(rivalries, coach_a, coach_b, "coach_coach")
        if rc:
            heat = max(heat, rc["intensity"])
            parts.append(f"coaches: {rc['intensity']} ({rc['origin']})")
    heat = max(0, min(100, heat))
    return {"heat": heat,
            "label": "Simmering" if heat < 35 else "Heated" if heat < 65 else "Bad blood",
            "details": parts}


# ---------------------------------------------------------------------------
# Fan favourites
# ---------------------------------------------------------------------------
# Realistic parameters, in rough order of importance:
#   1. What they do on the ice (production) -- matters most.
#   2. Tenure -- the longer the sweater, the deeper the love.
#   3. Reputation + leadership -- stars and warriors.
#   4. Captaincy -- the C carries weight with fans.
#   5. Character -- box-office divas sell tickets while producing; fans turn
#      on expensive headaches fast.
#   6. Youth hype -- the 20-year-old phenom gets a bonus.

FAN_TIERS = [
    (85, "Beloved icon"),
    (70, "Fan favourite"),
    (55, "Popular"),
    (40, "Known quantity"),
    (0, "Anonymous"),
]


def _tenure_years(player: Any) -> int:
    t = str(getattr(player, "team_tenure", "") or "")
    try:
        if "This season" in t:
            return 0
        if "4+" in t:
            return 5
        import re as _re
        m = _re.search(r"(\d+)", t)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def fan_tier_label(score: float) -> str:
    for cutoff, label in FAN_TIERS:
        if score >= cutoff:
            return label
    return "Anonymous"


def fan_favourite_score(player: Any, team: Any = None) -> Dict[str, Any]:
    """0-100 how much the fans adore this player, and why."""
    ensure_reputation_fields(player)
    score = 15.0
    reasons: List[str] = []
    try:
        gp = max(1, getattr(player, "games_played", 1) or 1)
        pts = getattr(player, "points", 0) or 0
        ppg = pts / gp
        prod = min(30.0, ppg * 25)
        score += prod
        if ppg >= 1.0:
            reasons.append(f"Point-per-game star ({ppg:.2f} PPG)")
        elif ppg >= 0.6:
            reasons.append(f"Steady producer ({ppg:.2f} PPG)")

        yrs = _tenure_years(player)
        ten = min(15.0, yrs * 3)
        score += ten
        if yrs >= 4:
            reasons.append(f"{yrs}+ years in the sweater")

        rep = getattr(player, "reputation", 0) or 0
        score += rep * 0.15
        lead = getattr(player, "leadership", 50) or 50
        score += lead * 0.10
        if lead >= 80:
            reasons.append("Warrior -- leaves it all out there")

        role = str(getattr(player, "captaincy", "") or "").upper()
        if role == "C":
            score += 8
            reasons.append("Wears the C")
        elif role == "A":
            score += 4

        vol = getattr(player, "controversy", 0) or 0
        if vol >= 70:
            if ppg >= 0.8:
                score += 8
                reasons.append("Box-office -- fans love the theatre")
            else:
                score -= 12
                reasons.append("Expensive headache -- fans have turned")
        elif vol <= 20 and lead >= 60:
            score += 4
            reasons.append("Model pro")

        age = getattr(player, "age", 27) or 27
        if age <= 22 and ppg >= 0.7:
            score += 5
            reasons.append("Phenom hype")
    except Exception:
        pass
    score = max(0, min(100, round(score)))
    return {"score": score, "tier": fan_tier_label(score), "reasons": reasons}


def is_fan_favourite(player: Any, team: Any = None) -> bool:
    try:
        return fan_favourite_score(player, team)["score"] >= 70
    except Exception:
        return False


def coach_fan_appeal(coach: Any,
                     team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """0-100: how much the fans like the coach. Winning cures everything;
    player's coaches are loved, drill sergeants are respected (not loved)."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    score = 40.0
    reasons: List[str] = []
    try:
        wp = ctx.get("win_pct", 0.5)
        score += max(0.0, min(1.0, wp)) * 35
        if wp >= 0.6:
            reasons.append("Winning -- fans love a winner")
        yrs = getattr(coach, "years_with_team", 0) or 0
        score += min(10.0, yrs * 2)
        style = coach_style(coach)["label"]
        if style == "Player's Coach":
            score += 10
            reasons.append("Player's coach -- easy to love")
        elif style == "Drill Sergeant":
            score -= 5
            reasons.append("Demanding -- respected more than loved")
        vol = getattr(coach, "controversy", 0) or 0
        score -= vol * 0.1
        if (getattr(coach, "favorite_team", "") or "") == ctx.get("team_name", ""):
            score += 8
            reasons.append("One of our own")
    except Exception:
        pass
    score = max(0, min(100, round(score)))
    return {"score": score, "tier": fan_tier_label(score), "reasons": reasons}


# ---------------------------------------------------------------------------
# Friend / rival formation
# ---------------------------------------------------------------------------
# Whether two players become friends or rivals depends on character
# (controversy/leadership similarity), attributes (age, position group,
# nationality), and where each sits in the room hierarchy (same tier bonds;
# distant tiers grate). Stored on player.relationships: {other_id: -100..100}.

def _pos_group(p: Any) -> str:
    try:
        pos = str(getattr(p, "primary_position", "") or "").upper()
        if "GOAL" in pos or pos == "G":
            return "G"
        if "DEFEN" in pos or pos in ("LD", "RD", "D"):
            return "D"
        return "F"
    except Exception:
        return "F"


def bond_likelihood(a: Any, b: Any,
                    tier_of: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """0-100 friendship likelihood and 0-100 rivalry likelihood for a pair."""
    ensure_reputation_fields(a)
    ensure_reputation_fields(b)
    friendship = 30.0
    rivalry = 8.0
    reasons: List[str] = []
    try:
        if tier_of:
            ta, tb = tier_of.get(id(a)), tier_of.get(id(b))
            if ta and tb:
                if ta == tb:
                    friendship += 20
                    reasons.append(f"Same standing ({ta})")
                else:
                    order = ["Team Leaders", "Core Group", "Squad Players", "Fringe"]
                    gap = abs(order.index(ta) - order.index(tb))
                    if gap >= 2:
                        rivalry += 12
                        reasons.append("Different worlds in the room")
        ca, cb = (a.controversy or 0), (b.controversy or 0)
        if abs(ca - cb) <= 15:
            friendship += 12
            reasons.append("Similar temperaments")
        elif max(ca, cb) >= 65 and abs(ca - cb) >= 40:
            rivalry += 25
            reasons.append("Oil and water")
        la, lb = (getattr(a, "leadership", 50) or 50), (getattr(b, "leadership", 50) or 50)
        if la >= 70 and lb >= 70:
            friendship += 10
            reasons.append("Mutual respect of leaders")
        age_gap = abs((getattr(a, "age", 27) or 27) - (getattr(b, "age", 27) or 27))
        if age_gap <= 3:
            friendship += 8
        elif age_gap >= 9:
            rivalry += 6
            reasons.append("Generation gap")
        if _pos_group(a) == _pos_group(b):
            friendship += 6
        na, nb = str(getattr(a, "nationality", "") or ""), str(getattr(b, "nationality", "") or "")
        if na and na == nb:
            friendship += 4
    except Exception:
        pass
    return {"friendship": max(0, min(100, round(friendship))),
            "rivalry": max(0, min(100, round(rivalry))),
            "reasons": reasons}


def _ensure_relationships(p: Any) -> dict:
    ensure_reputation_fields(p)
    if not hasattr(p, "relationships") or not isinstance(getattr(p, "relationships", None), dict):
        p.relationships = {}
    if not hasattr(p, "coach_bonds") or not isinstance(getattr(p, "coach_bonds", None), dict):
        p.coach_bonds = {}
    return p.relationships


def nudge_relationship(a: Any, b: Any, delta: int,
                       reason: str = "") -> None:
    """Directly move one pair (events: brawl together, betrayal, ...)."""
    try:
        ra, rb = _ensure_relationships(a), _ensure_relationships(b)
        v = max(-100, min(100, ra.get(b.id, 0) + delta))
        ra[b.id] = v
        rb[a.id] = v
    except Exception:
        pass


def evolve_relationships(roster: List[Any], league: Any = None,
                         months: int = 1, seed: Optional[int] = None) -> List[Dict[str, Any]]:
    """Monthly roll: friendships and rivalries form and deepen on their own.
    Returns notable new developments for the dynamics feed."""
    import random as _r
    rng = _r.Random(seed)
    for p in roster:
        _ensure_relationships(p)
    tiers = team_hierarchy(roster)
    tier_of = {id(p): t for t, ps in tiers.items() for p in ps}
    league_rivs = list(getattr(league, "rivalries", []) or []) if league else []
    notable: List[Dict[str, Any]] = []
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            try:
                bl = bond_likelihood(a, b, tier_of)
                cur = a.relationships.get(b.id, 0)
                target = bl["friendship"] - bl["rivalry"]
                lr = rivalry_between(league_rivs, a, b) if league_rivs else None
                if lr:
                    target = min(target, -lr["intensity"])
                rate = 0.12 * months * (1.6 if lr else 1.0)  # bad blood festers fast
                step = (target - cur) * rate + rng.uniform(-3, 3)
                new = max(-100, min(100, round(cur + step)))
                a.relationships[b.id] = new
                b.relationships[a.id] = new
                if cur < 40 <= new:
                    notable.append({"kind": "friendship", "a": a, "b": b, "value": new})
                elif cur > -40 >= new:
                    notable.append({"kind": "rift", "a": a, "b": b, "value": new})
            except Exception:
                pass
    return notable


def get_friends(player: Any, roster: List[Any], n: int = 3) -> List[Dict[str, Any]]:
    rels = _ensure_relationships(player)
    scored = [(rels.get(p.id, 0), p) for p in roster if p is not player]
    scored.sort(key=lambda t: -t[0])
    return [{"player": p, "score": s} for s, p in scored[:n] if s >= 30]


def get_rivals(player: Any, roster: List[Any], league: Any = None,
               n: int = 3) -> List[Dict[str, Any]]:
    by_name: Dict[str, Dict[str, Any]] = {}
    rels = _ensure_relationships(player)
    scored = [(rels.get(p.id, 0), p) for p in roster if p is not player]
    scored.sort(key=lambda t: t[0])
    for s, p in scored:
        if s <= -30:
            by_name[getattr(p, "full_name", "?")] = {
                "name": getattr(p, "full_name", "?"), "score": s,
                "origin": "locker room"}
    if league is not None:
        for r in get_rivalries_for(getattr(league, "rivalries", []) or [], player):
            other = r["b_name"] if r["a"] == _ekey(player) else r["a_name"]
            origin = r["origin"].replace("_", " ") + (" (entrenched)" if r.get("solidified") else "")
            entry = {"name": other, "score": -r["intensity"], "origin": origin}
            if other in by_name:
                by_name[other]["score"] = min(by_name[other]["score"], entry["score"])
                by_name[other]["origin"] = entry["origin"]
            else:
                by_name[other] = entry
    out = sorted(by_name.values(), key=lambda d: d["score"])
    return out[:n]


# ---------------------------------------------------------------------------
# Reactions to developments: fan favourites change how news lands
# ---------------------------------------------------------------------------
# The room and the fanbase react to what happens to a player or coach.
# Fan favourites amplify everything: burying one is a scandal, extending one
# is a parade.

def _apply_room_shift(roster: List[Any], delta: int,
                      only: Optional[Any] = None) -> None:
    for p in roster:
        try:
            if only is None or only(p):
                p.happiness = max(0, min(100, (getattr(p, "happiness", 70) or 70) + delta))
        except Exception:
            pass


def player_news_reaction(team: Any, player: Any, kind: str,
                         roster: List[Any],
                         league: Any = None) -> Dict[str, Any]:
    """kind: trade_rumor | benched | injured | milestone | award |
    retirement | extension_signed. Returns what happened."""
    ensure_reputation_fields(player)
    ff = fan_favourite_score(player, team)
    fav = ff["score"] >= 70
    name = getattr(player, "full_name", "Player").split()
    name = name[0] if name else "Player"
    friends = [p for p in roster
               if p is not player and _ensure_relationships(p).get(player.id, 0) >= 50]
    room = 0
    fan = 0
    texts: List[str] = []
    if kind == "trade_rumor":
        room -= 2
        fan -= 15 if fav else 4
        texts.append(f"Trade winds around {name} are a distraction.")
        if fav:
            texts.append(f"The fans are furious -- {name} is a {ff['tier'].lower()}.")
        _apply_room_shift(friends, -2)
    elif kind == "benched":
        room -= 3 if fav else 1
        fan -= 12 if fav else 3
        texts.append(f"{name} benched." + (" The building boos." if fav else ""))
        _apply_room_shift(friends, -3)
    elif kind == "injured":
        tiers = team_hierarchy(roster)
        leader = player in tiers.get("Team Leaders", [])
        room -= 3 if leader else 1
        fan -= 8 if fav else 2
        texts.append(f"{name} hurt." + (" The room feels it." if leader else ""))
        _apply_room_shift(friends, -2)
    elif kind in ("milestone", "award"):
        room += 2
        fan += 10 if fav else 4
        texts.append(f"{name} honoured -- the room loves it."
                     + (" The city is buzzing." if fav else ""))
        _apply_room_shift(friends, 2)
        _apply_room_shift(roster, 1)
    elif kind == "retirement":
        room -= 2 if fav else 1
        fan -= 10 if fav else 3
        texts.append(f"{name} hangs them up."
                     + (" End of an era." if fav else ""))
    elif kind == "extension_signed":
        room += 2 if fav else 1
        fan += 12 if fav else 3
        texts.append(f"{name} extended."
                     + (" The fans are delighted." if fav else ""))
    else:
        texts.append(f"{name}: {kind}.")
    if room:
        _apply_room_shift(roster, room)
    tone = "up" if room > 0 else "down" if room < 0 else "neutral"
    record_team_event(team, "player_news",
                      " ".join(texts) + (f" (Fan impact: {fan:+d}.)" if fan else ""),
                      morale_delta=room, tone=tone)
    return {"room_delta": room, "fan_delta": fan, "fan_favourite": fav,
            "fan_score": ff["score"], "friends_affected": len(friends),
            "text": " ".join(texts)}


def coach_news_reaction(team: Any, coach: Any, kind: str,
                        roster: List[Any],
                        team_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """kind: fired | hired | line_seize | extension | milestone_win."""
    ensure_reputation_fields(coach)
    ctx = team_context or {}
    appeal = coach_fan_appeal(coach, ctx)
    loved = appeal["score"] >= 70
    cname = getattr(coach, "full_name", "Coach").split()[0]
    room = 0
    fan = 0
    texts: List[str] = []
    if kind == "fired":
        wp = ctx.get("win_pct", 0.5)
        if wp < 0.45 and (getattr(coach, "controversy", 0) or 0) >= 60:
            fan += 5
            texts.append(f"{cname} fired. Sections of the fanbase say good riddance.")
        else:
            room -= 4
            fan -= 20 if loved else 8
            texts.append(f"{cname} fired."
                         + (" The fans are livid -- he was beloved." if loved else ""))
        try:
            for p in roster:
                if player_coach_response(p, coach, ctx)["label"] == "Bought in":
                    p.happiness = max(0, (getattr(p, "happiness", 70) or 70) - 3)
        except Exception:
            pass
    elif kind == "hired":
        fav_team = (getattr(coach, "favorite_team", "") or "") == getattr(team, "team_name", "")
        room += 2
        fan += 10 if fav_team else 4
        texts.append(f"{cname} hired as head coach."
                     + (" A hometown hero -- the city is thrilled." if fav_team else ""))
    elif kind == "line_seize":
        room -= 2
        fan -= 6 if loved else 2
        texts.append(f"GM took {cname}'s lines."
                     + (" Talk radio is ablaze." if loved else ""))
    elif kind == "extension":
        room += 2
        fan += 8 if loved else 3
        texts.append(f"{cname} extended." + (" The fans approve." if loved else ""))
    elif kind == "milestone_win":
        room += 2
        fan += 8 if loved else 4
        texts.append(f"Milestone win for {cname}.")
    if room:
        _apply_room_shift(roster, room)
    tone = "up" if room > 0 else "down" if room < 0 else "neutral"
    record_team_event(team, "coach_news", " ".join(texts),
                      morale_delta=room, tone=tone)
    return {"room_delta": room, "fan_delta": fan, "fan_appeal": appeal["score"],
            "text": " ".join(texts)}


# Fan favourites take discounts to stay: loyalty nudge inside contract_loyalty.
_orig_contract_loyalty = contract_loyalty


def contract_loyalty(player: Any) -> float:  # noqa: F811
    base = _orig_contract_loyalty(player)
    try:
        if is_fan_favourite(player):
            base = min(0.98, base + 0.08)
    except Exception:
        pass
    return base


# ---------------------------------------------------------------------------
# Rivalry reviews: solidification every few years
# ---------------------------------------------------------------------------
# Every few years each rivalry gets a verdict: does it fade, simmer on, or
# SOLIDIFY into permanent bad blood? Stronger implications dominate the
# verdict -- a season-ending injury calcifies; just chirping along with a
# regional rivalry fades when the context changes.

RIVALRY_ORIGIN_WEIGHT = {
    "major_injury": 90,      # personal, career-affecting -- never really dies
    "brawl_game": 75,        # personal escalation
    "mistreatment": 70,
    "firing": 70,
    "playoff_series": 60,    # 7-game wars can calcify
    "heavy_hits": 55,
    "gm_power_struggle": 50,
    "contract_dispute": 45,
    "award_race": 35,
    "regional": 25,          # just encouraged the rivalry -- ambient
}

# Origins personal enough that the bad blood belongs to the MAN, not the sweater.
PERSONAL_ORIGINS = {"major_injury", "brawl_game", "mistreatment", "heavy_hits"}


def review_rivalries(rivalries: list, years: int = 3) -> List[Dict[str, Any]]:
    """Every few years: solidify, simmer, fade, or bury each rivalry.
    Returns the verdicts (useful for an offseason news feed)."""
    verdicts: List[Dict[str, Any]] = []
    for r in list(rivalries):
        try:
            # Old wounds eventually stop mattering for the nightly tension.
            if isinstance(r.get("incidents"), list):
                r["incidents"] = [i for i in r["incidents"]
                                  if _incident_games_ago(i) <= 164]
            if r.get("solidified"):
                # Entrenched: barely cools, never dies on its own.
                r["intensity"] = max(60, r["intensity"] - 1 * years)
                verdicts.append({"rivalry": r, "outcome": "entrenched",
                                 "text": f"{r['a_name']} vs {r['b_name']}: entrenched. "
                                         f"This one isn't going away."})
                continue
            strength = RIVALRY_ORIGIN_WEIGHT.get(r["origin"], 40)
            # Stronger implications play the biggest factor.
            score = (strength * 0.45 + r["grudge"] * 0.25
                     + r["career_cost"] * 0.15 + r["intensity"] * 0.15)
            if score >= 68:
                r["solidified"] = True
                r["intensity"] = max(r["intensity"], 65)
                verdicts.append({"rivalry": r, "outcome": "solidified",
                                 "text": f"{r['a_name']} vs {r['b_name']}: SOLIDIFIED. "
                                         f"{r['story'][:80]}"})
            elif score >= 42:
                r["intensity"] = max(20, r["intensity"] - 4 * years)
                verdicts.append({"rivalry": r, "outcome": "simmering",
                                 "text": f"{r['a_name']} vs {r['b_name']}: still simmering "
                                         f"({r['intensity']:.0f})."})
            else:
                # Regional hate has a floor: it never fully dies.
                floor = 30 if r["origin"] == "regional" else 0
                r["intensity"] = max(floor, r["intensity"] - 10 * years)
                if r["intensity"] <= 5 and floor == 0:
                    rivalries.remove(r)
                    verdicts.append({"rivalry": r, "outcome": "buried",
                                     "text": f"{r['a_name']} vs {r['b_name']}: buried. "
                                             f"Time healed it."})
                elif floor and r["intensity"] <= floor:
                    verdicts.append({"rivalry": r, "outcome": "enduring",
                                     "text": f"{r['a_name']} vs {r['b_name']}: enduring "
                                             f"({r['intensity']:.0f}) -- some hate never dies."})
                else:
                    verdicts.append({"rivalry": r, "outcome": "fading",
                                     "text": f"{r['a_name']} vs {r['b_name']}: fading "
                                             f"({r['intensity']:.0f})."})
        except Exception:
            pass
    return verdicts


def on_player_transfer(rivalries: list, player: Any,
                       from_team: Any = None,
                       to_team: Any = None) -> Dict[str, Any]:
    """A player changes sweaters. Personal bad blood (injuries, personal
    escalation) follows the MAN -- it's his, not the team's. Ambient stuff he
    merely 'encouraged' (regional chirping, mild award races) is left behind
    or cools to almost nothing."""
    carried: List[Dict[str, Any]] = []
    left: List[Dict[str, Any]] = []
    try:
        for r in list(get_rivalries_for(rivalries, player)):
            if r["kind"] not in ("player_player", "coach_player", "gm_coach"):
                continue
            if r["origin"] in PERSONAL_ORIGINS or r.get("solidified") or r["intensity"] >= 50:
                carried.append(r)
            elif r["intensity"] < 35:
                rivalries.remove(r)
                left.append(r)
            else:
                r["intensity"] = max(10, r["intensity"] - 25)
                left.append(r)
    except Exception:
        pass
    return {"carried": carried, "left_behind": left,
            "text": (f"{_ename(player)} moved. "
                     f"{len(carried)} personal beef(s) follow him; "
                     f"{len(left)} ambient one(s) left behind.")}


# ---------------------------------------------------------------------------
# National teammates
# ---------------------------------------------------------------------------
# International tournaments cut across NHL bad blood. Winning together --
# especially for leaders -- forges bonds; even real NHL enemies can bury it
# after a gold-medal run. A disaster can scar instead.

def apply_international_tournament(rivalries: list, players: List[Any],
                                   nation: str, result: str) -> Dict[str, Any]:
    """result: gold | silver | bronze | early_exit. players: same-nation
    participants. Returns what changed."""
    result = (result or "").lower()
    bond = {"gold": 12, "silver": 8, "bronze": 6}.get(result, 4)
    soften = {"gold": 25, "silver": 15, "bronze": 8}.get(result, 0)
    buried: List[Dict[str, Any]] = []
    bonded = 0
    try:
        for i, a in enumerate(players):
            ensure_reputation_fields(a)
            for b in players[i + 1:]:
                ensure_reputation_fields(b)
                # Shared triumph bonds; leaders bond hardest.
                la = getattr(a, "leadership", 50) or 50
                lb = getattr(b, "leadership", 50) or 50
                extra = 6 if (la >= 70 and lb >= 70) else 0
                nudge_relationship(a, b, bond + extra,
                                   f"{nation} {result} together")
                bonded += 1
                # NHL bad blood can be overcome by winning together.
                r = rivalry_between(rivalries, a, b)
                if r and soften:
                    r["intensity"] -= soften
                    if r["intensity"] <= 10 and not r.get("solidified"):
                        rivalries.remove(r)
                        buried.append(r)
                    elif r.get("solidified") and r["intensity"] < 60:
                        # Even entrenched hate thaws a little.
                        r["intensity"] = 60
        if result == "gold":
            for p in players:
                try:
                    p.reputation = min(100, (getattr(p, "reputation", 0) or 0) + 2)
                except Exception:
                    pass
    except Exception:
        pass
    medal = {"gold": "GOLD", "silver": "silver", "bronze": "bronze"}.get(result, "early exit")
    return {"bonded_pairs": bonded, "buried": buried,
            "text": (f"{nation} {medal}: {bonded} pair(s) bonded. "
                     + (f"{len(buried)} NHL beef(s) buried." if buried else ""))}


# ---------------------------------------------------------------------------
# In-game punishment: coaches sending guys out, and who answers
# ---------------------------------------------------------------------------
# The Maurice scenario: getting blown out in a Cup Final game, he sends his
# guys to wear the other team down for tomorrow. The Knoblauch archetype
# would never -- character forbids it. Tortorella would be livid and answer
# in kind. Personality first, situation second.

def game_tension(home_team: Any, away_team: Any, rivalries: list,
                 is_playoff: bool = False, series_game: int = 0) -> float:
    """0-100: how much bad blood is in the building tonight."""
    try:
        t = 0.0
        for r in rivalries:
            if r["kind"] == "team_team":
                names = {r["a_name"], r["b_name"]}
                hn = getattr(home_team, "team_name", "")
                an = getattr(away_team, "team_name", "")
                if hn in names and an in names:
                    t += r["intensity"] * 0.6
        if is_playoff:
            t += 15 + max(0, series_game) * 2
        return round(min(100.0, t), 1)
    except Exception:
        return 0.0


def coach_reprisal_tendency(coach: Any) -> float:
    """0 = would never send guys out (Knoblauch). 1 = always will (Tortorella)."""
    try:
        style = coach_style(coach)["label"]
        t = 0.30
        if style == "Drill Sergeant":
            t += 0.35
        elif style == "Motivator":
            t += 0.15
        elif style == "Player's Coach":
            t -= 0.25
        t += (getattr(coach, "controversy", 20) or 20) / 100 * 0.30
        t += (getattr(coach, "discipline", 10) or 10) / 20 * 0.10
        return round(max(0.0, min(1.0, t)), 3)
    except Exception:
        return 0.3


def order_punishment(coach: Any, team: Any, game_state: Dict[str, Any],
                     rivalries: Optional[list] = None) -> Dict[str, Any]:
    """Does the coach send his guys out to punish the other team?
    game_state: score_diff (team's perspective), period, is_playoff,
    opponent, tension.
    The ORDERED team gets the bigger modifier -- the order carries weight
    the mere retaliation doesn't."""
    try:
        tendency = coach_reprisal_tendency(coach)
        sd = game_state.get("score_diff", 0)
        period = game_state.get("period", 1)
        is_playoff = game_state.get("is_playoff", False)
        tension = game_state.get("tension", 0)
        score = tendency
        reasons: List[str] = []
        if sd <= -3 and is_playoff:
            score += 0.35
            reasons.append("blown out in a playoff game -- wear them down for tomorrow")
        elif sd <= -3:
            score += 0.15
            reasons.append("getting run out of the building")
        elif sd <= -2 and period >= 3:
            score += 0.10
            reasons.append("game slipping away late")
        if tension >= 60:
            score += 0.15
            reasons.append("bad blood already boiling over")
        if game_state.get("running_it_up"):
            score += 0.10
            reasons.append("they're running it up")
        ordered = score >= 0.75
        cname = getattr(coach, "full_name", "Coach")
        if not ordered:
            story = f"{cname} keeps it clean. No order sent."
            if tension >= 60:
                story += " The room remembers, but this isn't who they are."
            return {"ordered": False, "tendency": tendency, "score": round(score, 3),
                    "reasons": reasons, "tension": tension, "story": story}
        # It happened: the building knows, and so does the league.
        if rivalries is not None:
            try:
                opp = game_state.get("opponent")
                if opp is not None:
                    opp_coach = getattr(opp, "head_coach", None)
                    if opp_coach is None:
                        opp_coach = opp_head_coach_of(rivalries, opp)
                    record_brawl_game(rivalries, team, opp, coach, opp_coach,
                                      aggressor="a", fights=4)
            except Exception:
                pass
        return {"ordered": True, "tendency": tendency, "score": round(score, 3),
                "reasons": reasons,
                "instigator_mod": 1.25,    # the ordered team: +25% physical impact
                "retaliation_mod": 1.10,   # the answer: smaller, reactive
                "story": f"{cname} sent them out: {'; '.join(reasons)}."}
    except Exception:
        return {"ordered": False, "tendency": 0.3, "score": 0.0,
                "reasons": [], "story": "No order."}


def opp_head_coach_of(rivalries: list, team: Any) -> Any:
    """Best-effort lookup of a team's head coach for rivalry records."""
    try:
        hc = getattr(team, "head_coach", None)
        if hc is not None:
            return hc
    except Exception:
        pass
    # Fallback: a lightweight stand-in keyed by team so the record still lands.
    class _StandIn:
        pass
    s = _StandIn()
    s.id = f"hc_{getattr(team, 'team_name', 'unknown')}"
    s.full_name = f"{getattr(team, 'team_name', 'Opponent')} head coach"
    return s


def respond_to_punishment(coach: Any, game_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """They're running your guys. Do you answer?
    Tortorella: livid, retaliates, tension +20. Knoblauch: composed, never."""
    try:
        tendency = coach_reprisal_tendency(coach)
        cname = getattr(coach, "full_name", "Coach")
        if tendency >= 0.65:
            return {"responds": True, "tone": "livid",
                    "retaliation_mod": 1.15, "tension_delta": 20,
                    "story": f"{cname} is LIVID on the bench -- the response is coming, "
                             f"and it's coming hard."}
        if tendency >= 0.35:
            return {"responds": True, "tone": "measured",
                    "retaliation_mod": 1.05, "tension_delta": 10,
                    "story": f"{cname} answers it -- measured, but they won't be pushed around."}
        tension = (game_state or {}).get("tension", 0)
        story = f"{cname} keeps the bench calm. 'We play hockey. We don't do that.'"
        simmer = False
        if tension >= 60:
            # We won't forget -- but this group isn't the type to answer.
            simmer = True
            story += (" The room is seething, though. They won't forget this one.")
        return {"responds": False, "tone": "composed",
                "retaliation_mod": 1.0, "tension_delta": 0,
                "simmer": simmer, "carried_tension": tension if simmer else 0,
                "story": story}
    except Exception:
        return {"responds": False, "tone": "composed", "retaliation_mod": 1.0,
                "tension_delta": 0, "story": "No response."}


# ---------------------------------------------------------------------------
# Performance as a beef rectifier: the Torts/Werenski arc
# ---------------------------------------------------------------------------
# A hard coach who drags a career year out of a player forges a bond out of
# the beef. The friction becomes the foundation -- "he made me the player
# I am." Once forged, the player is bought in for good.

def rectify_coach_player_beef(rivalries: list, player: Any, coach: Any,
                              career_best: bool = False,
                              form: float = 50.0) -> Dict[str, Any]:
    """Performance heals coach-player bad blood. A career year under a hard
    coach turns the beef into a bond."""
    try:
        r = rivalry_between(rivalries, player, coach)
        if not r or r["kind"] != "coach_player":
            return {"rectified": False, "reason": "no coach-player beef to rectify"}
        style = coach_style(coach)["label"]
        hard = style == "Drill Sergeant" or (getattr(coach, "discipline", 10) or 10) >= 14
        score = 0.0
        if career_best:
            score += 60
        score += max(0.0, form - 60) * 1.0
        if hard:
            score += 15  # the hard-driving coach gets credit for the career year
        score -= r["grudge"] * 0.3  # deep grudges are harder to melt
        cname = getattr(coach, "full_name", "Coach")
        pname = getattr(player, "full_name", "Player")
        if score >= 55:
            bury_hatchet(rivalries, player, coach)
            ensure_reputation_fields(player)
            bonds = getattr(player, "coach_bonds", None)
            if bonds is None:
                player.coach_bonds = {}
                bonds = player.coach_bonds
            bonds[getattr(coach, "id", id(coach))] = (
                f"Career year under {cname} -- the beef became a bond")
            try:
                player.happiness = min(100, (getattr(player, "happiness", 70) or 70) + 8)
                player.morale = min(100, (getattr(player, "morale", 70) or 70) + 8)
            except Exception:
                pass
            return {"rectified": True, "score": round(score, 1),
                    "story": f"{cname} was hard on {pname} -- and dragged a career year "
                             f"out of him. The beef is gone; what's left is a bond. "
                             f"'He made me the player I am.'"}
        return {"rectified": False, "score": round(score, 1),
                "reason": "not enough on-ice proof yet -- the beef survives"}
    except Exception:
        return {"rectified": False, "reason": "error"}


# ---------------------------------------------------------------------------
# Game tension drivers: fights, penalties, history, and recent wounds
# ---------------------------------------------------------------------------
# Tension is the room's MEMORY -- it can be sky-high even when the coach
# would never order retaliation. You hurt our star last game? We won't
# forget. But whether we ANSWER is a separate, personality-gated question.

INCIDENT_WEIGHTS = {
    "star_injured": 25,      # you hurt our best player -- we remember
    "player_injured": 12,
    "controversial_hit": 10,
    "coach_comments": 8,     # he ran his mouth in the media
    "brawl": 15,
}


def record_game_incident(rivalries: list, team_a: Any, team_b: Any,
                         kind: str, detail: str = "") -> Dict[str, Any]:
    """Log something these two teams won't forget. Stored on the team_team
    rivalry record so it survives saves and follows the feud."""
    try:
        if kind not in INCIDENT_WEIGHTS:
            return {"recorded": False, "reason": f"unknown kind {kind}"}
        # Find or create the team_team record.
        r = None
        for cand in rivalries:
            if cand["kind"] == "team_team":
                names = {cand["a_name"], cand["b_name"]}
                if ({getattr(team_a, "team_name", ""), getattr(team_b, "team_name", "")} <= names
                        and len(names) == 2):
                    r = cand
                    break
        if not r:
            if _ekey(team_a) == _ekey(team_b):
                return {"recorded": False, "reason": "a team cannot feud with itself"}
            r = add_rivalry(rivalries, team_a, team_b, "team_team", 15,
                            "regional",
                            f"{_ename(team_a)} vs {_ename(team_b)}: bad blood started here.")
        log = r.get("incidents")
        if not isinstance(log, list):
            r["incidents"] = log = []
        log.append({"kind": kind, "detail": detail,
                    "date": date.today().isoformat()})
        return {"recorded": True, "kind": kind, "detail": detail}
    except Exception:
        return {"recorded": False, "reason": "error"}


def _incident_games_ago(inc: Dict[str, Any]) -> float:
    try:
        d = date.fromisoformat(inc.get("date", date.today().isoformat()))
        days = (date.today() - d).days
        return max(0.0, days / 3.0)  # roughly a game every 3 days
    except Exception:
        return 0.0


def _rivalry_age_years(r: Dict[str, Any]) -> float:
    try:
        d = date.fromisoformat(r.get("date", date.today().isoformat()))
        return max(0.0, (date.today() - d).days / 365.0)
    except Exception:
        return 0.0


def game_tension(home_team: Any, away_team: Any, rivalries: list,
                 is_playoff: bool = False, series_game: int = 0,
                 recent_fights: int = 0, recent_pim: int = 0,
                 extra_incidents: Optional[List[Dict[str, Any]]] = None) -> float:
    """0-100: how much bad blood is in the building tonight.
    Drivers: historic rivalry heat, recent fights, recent penalty minutes,
    logged incidents (a star hurt last game spikes it), playoff stakes."""
    try:
        t = 0.0
        hn = getattr(home_team, "team_name", "")
        an = getattr(away_team, "team_name", "")
        incidents: List[Dict[str, Any]] = list(extra_incidents or [])
        for r in rivalries:
            if r["kind"] != "team_team":
                continue
            names = {r["a_name"], r["b_name"]}
            if not ({hn, an} <= names and len(names) == 2):
                continue
            contrib = r["intensity"] * 0.6
            # Historic feuds weigh more than fresh ones at the same heat.
            if r.get("solidified") or _rivalry_age_years(r) >= 5:
                contrib = r["intensity"] * 0.75 + 5
            t += contrib
            for inc in (r.get("incidents") or []):
                incidents.append(inc)
        # Fights and penalty minutes: chippiness is measurable.
        t += min(24.0, recent_fights * 6.0)
        t += min(15.0, recent_pim * 0.3)
        # Recent wounds decay -- last game matters, two months ago barely does.
        for inc in incidents:
            w = INCIDENT_WEIGHTS.get(inc.get("kind"), 0)
            if not w:
                continue
            ago = inc.get("games_ago", _incident_games_ago(inc))
            t += w * (0.75 ** max(0.0, ago))
        if is_playoff:
            t += 15 + max(0, series_game) * 2
        return round(min(100.0, t), 1)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Personality: locked identity, living volatility
# ---------------------------------------------------------------------------
# base_controversy is dealt ONCE at generation and never changes -- it's who
# the man IS. controversy is how much he's ACTING OUT right now, and it
# drifts with scenario: mentors, coaching fit, adversity, happiness, money.
# A base-80 hothead can learn to live at 55. He will never be a 10.
# Identity is preserved; behavior is earned.

def _deal_base_controversy(entity: Any, hothead_chance: float = 0.08) -> int:
    """The actual deal. Never calls ensure_reputation_fields (no recursion)."""
    roll = random.random()
    if roll < 0.05:
        base = random.randint(0, 8)     # saint
    elif roll < 0.05 + hothead_chance:
        base = random.randint(55, 85)   # hothead
    else:
        base = random.randint(8, 35)    # everyone else
    entity.base_controversy = base
    entity.controversy = base
    return base


def generate_personality(entity: Any, hothead_chance: float = 0.08) -> int:
    """Deal a locked personality. Idempotent -- never re-deals a locked one."""
    try:
        ensure_reputation_fields(entity)
        if isinstance(getattr(entity, "base_controversy", None), int):
            return entity.base_controversy
        return _deal_base_controversy(entity, hothead_chance)
    except Exception:
        return 20


def _is_staff_entity(entity: Any) -> bool:
    return not hasattr(entity, "primary_position")


def _draft_overall(p: Any) -> Optional[int]:
    try:
        s = getattr(p, "draft_position", "") or ""
        if "Round 1" in s:
            m = re.search(r"Pick (\d+)", s)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


def _golden_prospect(p: Any) -> bool:
    """Won everything before the NHL: top-10 pick, or 'A' potential as a teen."""
    ov = _draft_overall(p)
    if ov is not None:
        return ov <= 10
    try:
        return ((getattr(p, "potential_grade", "") or "").upper() == "A"
                and (getattr(p, "age", 99) or 99) <= 21)
    except Exception:
        return False


def _player_tier(p: Any, team: Any) -> str:
    try:
        if team is None:
            return ""
        tiers = team_hierarchy(getattr(team, "roster", []) or [])
        pid = getattr(p, "id", None)
        for name, members in tiers.items():
            if any(getattr(m, "id", None) == pid for m in members):
                return name
    except Exception:
        pass
    return ""


def _player_volatility_offset(p: Any, team: Any = None, coach: Any = None,
                              win_pct: Optional[float] = None) -> tuple:
    """Scenario offset for a player: negative calms, positive escalates."""
    off = 0
    reasons: List[str] = []
    base = controversy_baseline(p)
    age = getattr(p, "age", 27) or 27
    happy = getattr(p, "happiness", 65) or 65

    # Veteran mentorship: the room raises him right -- or nobody checks him.
    mentors = 0
    if team is not None:
        for mate in getattr(team, "roster", []) or []:
            if mate is p:
                continue
            if (getattr(mate, "leadership", 0) or 0) >= 75 \
                    and (getattr(mate, "age", 0) or 0) >= 30:
                mentors += 1
    if mentors:
        d = -min(8, 3 * mentors)
        off += d
        reasons.append(f"{mentors} veteran mentor(s) steadying him ({d})")
    elif base >= 50:
        off += 2
        reasons.append("no veteran presence to check him (+2)")

    # The right coaching -- or the wrong one.
    if coach is not None:
        try:
            label = player_coach_response(p, coach).get("label", "")
            if label == "Bought in":
                off -= 4
                reasons.append("right coach for him (-4)")
            elif label == "Tuning out":
                off += 3
                reasons.append("tuning the coach out (+3)")
            elif label == "Quit on coach":
                off += 6
                reasons.append("quit on the coach (+6)")
        except Exception:
            pass

    # Golden-prospect adversity shock: won everything, never faced it until now.
    # McDavid prevails. Not every prospect is built like that.
    if _golden_prospect(p) and (getattr(p, "nhl_games_played", 999) or 999) < 100:
        adversity = (win_pct is not None and win_pct < 0.45) or happy < 45 \
            or _player_tier(p, team) in ("Fringe", "Squad Players")
        if adversity:
            character = (getattr(p, "leadership", 50) or 50) + (100 - base)
            if character >= 140:
                off -= 4
                reasons.append("golden prospect met real adversity and prevailed (-4)")
            else:
                off += 7
                reasons.append("entitlement meets reality: first real adversity (+7)")

    # Tough early years humble a young hothead who wasn't handed everything.
    if age <= 23 and base >= 50 and not _golden_prospect(p):
        if (win_pct is not None and win_pct < 0.50) or happy < 55:
            off -= 4
            reasons.append("tough rookie years humbled him (-4)")

    # Knows his place: happy and winning vs miserable on a loser.
    if happy >= 65 and win_pct is not None and win_pct >= 0.55:
        off -= 3
        reasons.append("happy and winning (-3)")
    if happy < 45 and win_pct is not None and win_pct < 0.45:
        off += 6
        reasons.append("miserable on a loser (+6)")

    # Just got paid -- security calms. Underpaid and knows it -- doesn't.
    try:
        ovr = p.overall_rating() if hasattr(p, "overall_rating") else 40
        salary = getattr(p, "salary", 0) or 0
        expected = max(750_000, (ovr - 38) * 750_000)
        if salary >= expected * 1.2:
            off -= 2
            reasons.append("paid and secure (-2)")
        elif salary < expected * 0.7 and ovr >= 42:
            off += 3
            reasons.append("underpaid and knows it (+3)")
    except Exception:
        pass

    # Age mellows everyone, even hotheads.
    if age >= 30:
        off -= 3
        reasons.append("veteran perspective (-3)")
    elif age >= 24:
        off -= 2
        reasons.append("maturing (-2)")

    return max(-25, min(25, off)), reasons


def _coach_volatility_offset(c: Any, team: Any = None, coach: Any = None,
                             win_pct: Optional[float] = None) -> tuple:
    """Scenario offset for a coach."""
    off = 0
    reasons: List[str] = []
    base = controversy_baseline(c)
    ywt = getattr(c, "years_with_team", 0) or 0
    if win_pct is not None and win_pct < 0.450:
        off -= 5
        reasons.append("losing humbled him (-5)")
    if ywt <= 1 and base >= 50:
        off -= 6
        reasons.append("new organization, changing his ways (-6)")
    if win_pct is not None and win_pct >= 0.600 \
            and (getattr(c, "controversy", 0) or 0) >= 50:
        off += 4
        reasons.append("winning lets him get away with it (+4)")
    return max(-25, min(25, off)), reasons


def volatility_drivers(entity: Any, team: Any = None, coach: Any = None,
                       win_pct: Optional[float] = None) -> List[str]:
    """Human-readable reasons behind this year's volatility drift."""
    try:
        ensure_reputation_fields(entity)
        if _is_staff_entity(entity):
            return _coach_volatility_offset(entity, team, coach, win_pct)[1]
        return _player_volatility_offset(entity, team, coach, win_pct)[1]
    except Exception:
        return []


def coach_market_appeal(coach: Any, hiring_org: tuple = ()) -> Dict[str, Any]:
    """How badly does the league want this coach? Record talks, controversy
    costs -- unless someone in the hiring org vouches for him. A stubborn,
    controversial coach who isn't winning needs friends to pipeline him."""
    try:
        ensure_reputation_fields(coach)
        rep = getattr(coach, "reputation", 50) or 50
        cont = getattr(coach, "controversy", 20) or 20
        tax = cont * 0.4
        vouched = any(v in (getattr(coach, "connections", None) or [])
                      for v in (hiring_org or ()))
        if vouched:
            tax *= 0.5
        score = max(0, min(100, rep * 0.7 - tax + 15))
        return {"appeal": round(score, 1), "reputation": rep,
                "controversy_tax": round(tax, 1), "vouched": vouched,
                "story": (f"{_ename(coach)}: appeal {score:.0f} "
                          f"(rep {rep}, controversy tax {tax:.0f}"
                          f"{', vouched by a friend in the org' if vouched else ''}).")}
    except Exception:
        return {"appeal": 50.0, "reputation": 50, "controversy_tax": 0,
                "vouched": False, "story": "Appeal unavailable."}


def volatility_trade_discount(player: Any) -> float:
    """Talent-personality-volatility balance for trade value: hotheads cost
    less, but a superstar is worth the headache."""
    try:
        c = getattr(player, "controversy", 0) or 0
        ovr = player.overall_rating() if hasattr(player, "overall_rating") else 40
        star = max(0.0, min(1.0, (ovr - 40) / 24.0))
        discount = (c / 100.0) * 0.25 * (1.15 - star)
        return round(max(0.70, 1 - discount), 3)
    except Exception:
        return 1.0
