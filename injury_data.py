# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""injury_data.py -- grounded injury probability/severity tables + shared injury decisions.

W4 (icetime-ecosystem), 2026-09-29.

THE ONE DECISION: roll_general_injury() + apply_injury() are the single shared
implementation of "a non-hit in-game injury happens". AdvancedGameSim,
GameSim, and the batch lightweight sim all call it -- one decision, N
fidelities. Per-engine call sites pass only their calibrated base rate; the
victim selection, severity, body-part, and concussion logic below is shared.
The hit path (simulation._apply_hit_injury) routes its type/severity through
the same tables via hit_injury_spec().

REAL-DATA GROUNDING (numbers below cite these sources):
  [R1] Rotowire, "NHL's Most Injured Teams of 2024-25" (2024-25 season):
       32 teams, 819 injury events, 6,588 man-games lost.
       -> 25.6 injuries/team/season; ~206 MGL/team/season; 8.04 MGL/injury.
       -> 0.312 injuries per team-game over an 82-game season.
  [R2] Knapik et al., "Injuries in the NHL From 2012 to 2023", Am J Sports
       Med 2026 (AJSM Vol. 54, No. 5): body-region incidence and mean time
       loss. Incidence: Head 21.2%, Hand 12.9%, Hip/groin 9.6%, Knee 8.7%,
       Shoulder 8.0%, Foot 6.4%, Ankle 6.1%, Upper arm 5.3%, Thigh 4.4%,
       Neck 3.9% (remainder undisclosed/other). Mean MGL/injury excluding
       zero-MGL events: 9.3 overall; knee 12.6, shoulder 11.0, ankle 11.1
       (longest); concussion 7.7. Mechanism mix (Fig. 5): body checks are
       the largest single category but a minority overall -- non-check
       mechanisms (non-contact, incidental contact, puck, environment,
       fights) dominate in aggregate (~70%).
  [R3] Mixed-methods concussion study (2000-01..2022-23): 1,054 concussions
       over 23 seasons -> ~1.43/team/season ~= 5.6% of injury events;
       mean 13.77 games missed (range 1-82); incidence 0.54-1.18 per 1000
       athlete-exposures.
  [R4] Benson et al., NHL-NHLPA Concussion Program (CMAJ): recurrent
       concussion -> 2.25x time loss vs first concussion.
  [R5] 7-season prospective pro-hockey study (Springer): lower limb 40.4%,
       upper limb 25.5%, head/spine 25%, trunk 9% -- cross-checks [R2]'s mix.

DESIGN NOTES (judgment calls, NOT data -- marked as such):
  * Circumstance severity bumps (dirty hit / enforcer-vs-small-star mismatch
    / open-ice collision) are tuned for feel; the base rates they scale are
    data-grounded.
  * Medical-staff effects are design (no public dataset links staff quality
    to recovery days); kept modest: +/-20% recovery time, setback odds
    roughly halved/doubled at the extremes.
  * No LTIR / cap relief (out of scope per brief); no goalie-specific
    mechanism split beyond a lower victim weight (goalies ~4.6% of
    concussions in [R3] vs ~10% of dressed skaters -- they get hurt less).
"""
import random

# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _ovr(entity, default=75.0):
    """Overall rating whether it's a method (Player.overall_rating) or a
    property/plain attribute (Staff.overall_rating, test fakes)."""
    try:
        v = getattr(entity, "overall_rating", default)
        if callable(v):
            v = v()
        return float(v or default)
    except Exception:
        return float(default)


# ---------------------------------------------------------------------------
# Grounded base rates
# ---------------------------------------------------------------------------

# [R1] 819 injuries / 32 teams / 82 games.
INJURIES_PER_TEAM_GAME = 0.31
# [R1] 6,588 MGL / 32 teams; 8.04 MGL per injury event.
MGL_PER_TEAM_SEASON = 206.0
MEAN_GAMES_PER_INJURY = 8.0

# Non-hit mechanisms are ~70% of events [R2, Fig. 5 mechanism mix]; the hit
# path covers body-check injuries, this roll covers everything else.
GENERAL_INJURY_BASE_RATE = 0.22
# Quick engines (AdvancedGameSim, batch lightweight sim) have NO hit-injury
# path, so the general roll carries the full grounded load there.
QUICK_ENGINE_GENERAL_RATE = 0.31
# Hit-path target: 0.31 * ~0.28 body-check share [R2] ~= 0.09/team-game.
HIT_PATH_TARGET_RATE = 0.09
# Measured 2026-09-29 (60-GameSim-game probe, pre-change): the unscaled hit
# path produced 0.567 injuries/team-game at mean 2.29 games -- ~6x its
# mechanism share. Scale the INJURY_CAUSED weight by 0.09/0.567 ~= 0.15.
# Hit frequency/physics stay W5's; only the injury conversion is the injury
# system's calibration.
HIT_INJURY_PROB_SCALE = 0.15

# Re-aggravation: a player inside his return window re-injures more easily
# (design; the physio report already warns "rushing him back risks
# re-injury" -- this wires the mechanic behind the warning).
REINJURY_WINDOW_GAMES = 10
REINJURY_MULT = 1.6
#: D24 (Wave A): playing hurt is allowed -- but it has risks. A tagged
#: skater's general-injury weight rises 1.5x on top of any re-injury
#: multiplier. The tag is per-game (cleared by resolve_game_lineup).
PLAYING_HURT_MULT = 1.5
# Goalie victim weight vs skaters (design, informed by [R3]: goalies are
# ~4.6% of concussions despite ~10% of dressed players).
GOALIE_VICTIM_WEIGHT = 0.35
# 10+ games (~3 weeks) flags the AI-replacement bookkeeping.
LONG_TERM_THRESHOLD = 10

# ---------------------------------------------------------------------------
# Body-region incidence [R2, Table 5] + type flavor per region
# ---------------------------------------------------------------------------
# (region_key, share of injuries). Shares sum to 0.765; the rest is the
# NHL's beloved "undisclosed" bucket, reported as upper/lower-body.
REGION_INCIDENCE = [
    ("HEAD", 0.212),
    ("HAND", 0.129),
    ("HIP_GROIN", 0.096),
    ("KNEE", 0.087),
    ("SHOULDER", 0.080),
    ("FOOT", 0.064),
    ("ANKLE", 0.061),
    ("UPPER_ARM", 0.053),
    ("THIGH", 0.044),
    ("NECK", 0.039),
    ("OTHER", 0.135),
]
# Regions with the longest mean time loss [R2]: knee 12.6, shoulder 11.0,
# ankle 11.1 MGL/injury -- these bump one severity tier 25% of the time.
HIGH_SEVERITY_REGIONS = {"KNEE", "SHOULDER", "ANKLE"}

REGION_TYPES = {
    "HEAD": ["Cut requiring stitches", "Broken nose", "Broken jaw",
             "Facial laceration"],
    "HAND": ["Broken hand", "Broken finger", "Sprained wrist", "Bruised hand"],
    "HIP_GROIN": ["Pulled groin", "Hip flexor strain", "Groin strain",
                  "Sports hernia"],
    "KNEE": ["Sprained MCL", "Torn meniscus", "Bruised knee", "Knee sprain"],
    "SHOULDER": ["Separated shoulder", "Dislocated shoulder", "Shoulder strain",
                 "AC joint sprain"],
    "FOOT": ["Broken foot", "Bruised foot", "Foot contusion"],
    "ANKLE": ["High ankle sprain", "Sprained ankle", "Ankle fracture"],
    "UPPER_ARM": ["Broken arm", "Bruised bicep", "Forearm contusion"],
    "THIGH": ["Charley horse", "Pulled quad", "Thigh bruise", "Hamstring strain"],
    "NECK": ["Strained neck", "Neck strain", "Whiplash"],
    # The NHL "undisclosed" bucket -- reported by body half, like the real IR.
    "OTHER": ["Upper-body injury", "Lower-body injury", "Back spasms",
              "Bruised ribs"],
}

# Concussion: ~5.6% of injury events [R3]. Head is 21.2% of injuries [R2],
# so 0.056/0.212 ~= 0.26 of head injuries are concussions.
CONCUSSION_SHARE_OF_HEAD = 0.26
# [R3] mean 13.77 games missed, range 1-82. Lognormal(mu=2.35, sigma=0.75):
# mean ~13.9, median ~10.5 -- long right tail like the real data.
_CONCUSSION_MU = 2.35
_CONCUSSION_SIGMA = 0.75
# [R4] recurrent concussion -> 2.25x time loss.
CONCUSSION_REPEAT_MULT = 2.25

# ---------------------------------------------------------------------------
# Severity tiers, calibrated so the general roll averages ~8.5 games [R1/R2]
# ---------------------------------------------------------------------------
# (cumulative_prob, lo_games, hi_games, label)
SEVERITY_TIERS = [
    (0.55, 1, 4, "day-to-day"),
    (0.85, 5, 12, "weeks"),
    (0.965, 13, 30, "month-plus"),
    (1.01, 31, 82, "season-threatening"),
]
MAX_GAMES_MISSED = 82

# Career-ending injury benchmark (Muck 2026-10-02):
# Real NHL 2016-2026: ~1 acute career-ending injury per decade league-wide
# (Cody McCormick, blood clots, 2016 — the clearest case). Chronic-degenerative
# endings (Hossa, Seabrook, Weber, Price) go through the 3-year LTIR decision,
# not this path. This is the catastrophic single-event tier.
# Rate: 0.001 of all injuries (1 in 1000) ~= 0.8 per decade league-wide.
CAREER_ENDING_RATE = 0.001


def _roll_region():
    r = random.random()
    cum = 0.0
    for region, share in REGION_INCIDENCE:
        cum += share
        if r < cum:
            return region
    return "OTHER"


def concussion_games(player=None):
    """Games missed for a concussion [R3]; repeat concussions cost 2.25x [R4]."""
    import math
    g = 1 + int(random.lognormvariate(_CONCUSSION_MU, _CONCUSSION_SIGMA))
    try:
        # Repeat = any prior concussion in the career ledger [R4]. (The
        # ledger is incremented in apply_injury AFTER the severity roll, so
        # the current concussion is never double-counted here.)
        if int(getattr(player, "career_concussions", 0) or 0) >= 1:
            g = int(round(g * CONCUSSION_REPEAT_MULT))
    except Exception:
        pass
    return max(1, min(MAX_GAMES_MISSED, g))


def roll_severity(player=None):
    """Roll (games, region, type_label, is_concussion) for a general injury.

    Mean ~8.5 games [R1: 8.04, R2: 9.3 excl. zero-MGL]. Never raises.
    """
    try:
        region = _roll_region()
        # Concussion check on head injuries [R3].
        if region == "HEAD" and random.random() < CONCUSSION_SHARE_OF_HEAD:
            return {
                "games": concussion_games(player),
                "region": "HEAD",
                "type": "Concussion",
                "concussion": True,
                "tier": "concussion",
            }
        r = random.random()
        tier_idx = 0
        for i, (cum, _lo, _hi, _label) in enumerate(SEVERITY_TIERS):
            if r < cum:
                tier_idx = i
                break
        # Long-layoff regions [R2] bump a tier 25% of the time.
        if region in HIGH_SEVERITY_REGIONS and random.random() < 0.25:
            tier_idx = min(tier_idx + 1, len(SEVERITY_TIERS) - 1)
        _cum, lo, hi, label = SEVERITY_TIERS[tier_idx]
        games = random.randint(lo, hi)
        type_label = random.choice(REGION_TYPES.get(region, REGION_TYPES["OTHER"]))
        return {"games": games, "region": region, "type": type_label,
                "concussion": False, "tier": label}
    except Exception:
        return {"games": 2, "region": "OTHER", "type": "Bruised ribs",
                "concussion": False, "tier": "day-to-day"}


# ---------------------------------------------------------------------------
# W3 integration (defensive): fatigue -> injury-risk multiplier
# ---------------------------------------------------------------------------

def fatigue_injury_risk_mult(player):
    """W3's canonical fatigue->injury-risk multiplier (condition_system).

    >= 1.0 whenever gassed or worn; exactly 1.0 for fresh players. Falls
    back to neutral 1.0 if condition_system is unavailable -- never raises.
    (W3 owns the formula; the injury system only consumes it.)
    """
    try:
        from condition_system import fatigue_injury_risk_mult as _w3
        return max(1.0, float(_w3(player)))
    except Exception:
        return 1.0


def _proneness_mult(player):
    """Victim weight from injury_proneness. Prefers W3's canonical mult."""
    try:
        from condition_system import injury_proneness_mult as _w3p
        return max(0.2, float(_w3p(player)))
    except Exception:
        pass
    try:
        p = float(getattr(player, "injury_proneness", 45) or 45)
    except Exception:
        p = 45.0
    return max(0.2, min(1.6, 0.5 + p / 90.0))


def _is_goalie(player):
    try:
        pos = getattr(player, "primary_position", None)
        if pos is None:
            return False
        return getattr(pos, "name", "") == "GOALIE" or getattr(pos, "value", "") == "G"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# THE ONE DECISION: general (non-hit) in-game injury
# ---------------------------------------------------------------------------

def roll_general_injury(team, base_prob=GENERAL_INJURY_BASE_RATE):
    """Shared general-injury decision for all engines.

    Returns (victim, spec) or (None, None). Does NOT mutate -- call
    apply_injury() to sideline the victim. Victim weighting:
    injury_proneness x age curve x W3 fatigue multiplier x re-aggravation;
    goalies included at GOALIE_VICTIM_WEIGHT (previously impossible).
    Never raises.
    """
    try:
        if random.random() >= base_prob:
            return None, None
        candidates, weights = [], []
        for p in getattr(team, "roster", []) or []:
            try:
                if getattr(p, "is_injured", False):
                    continue
                age = float(getattr(p, "age", 25) or 25)
                age_factor = max(0.5, min(2.0, (age - 20.0) / 10.0))
                w = (_proneness_mult(p) * age_factor
                     * fatigue_injury_risk_mult(p))
                try:
                    gsr = getattr(p, "games_since_return", 999)
                    if gsr is not None and gsr < REINJURY_WINDOW_GAMES:
                        w *= REINJURY_MULT
                except Exception:
                    pass
                try:
                    # D24 (Wave A): playing hurt carries re-injury risk.
                    if getattr(p, "playing_hurt", False):
                        w *= PLAYING_HURT_MULT
                except Exception:
                    pass
                if _is_goalie(p):
                    w *= GOALIE_VICTIM_WEIGHT
                if w > 0:
                    candidates.append(p)
                    weights.append(w)
            except Exception:
                continue
        if not candidates:
            return None, None
        victim = random.choices(candidates, weights=weights, k=1)[0]
        return victim, roll_severity(victim)
    except Exception:
        return None, None


def apply_injury(player, spec, team=None):
    """Sideline the victim: flags, staff-scaled absence, bookkeeping.

    Medical staff quality scales the diagnosed absence (recovery_time_mult);
    10+ game injuries flag the AI-replacement bookkeeping. Returns the final
    games_remaining_injured. Never raises.

    Career-ending check (Muck 2026-10-02): ~0.1% of injuries are catastrophic
    and end the career immediately (real NHL benchmark: ~1 per decade).
    """
    try:
        games = max(1, int(spec.get("games", 1)))
    except Exception:
        games = 1
    if team is not None:
        try:
            games = max(1, int(round(games * recovery_time_mult(team))))
        except Exception:
            pass
    type_label = spec.get("type", "Undisclosed injury")
    # Career-ending roll: only on serious injuries (13+ games), very rare
    _career_ending = False
    try:
        if games >= 13 and random.random() < CAREER_ENDING_RATE:
            _career_ending = True
    except Exception:
        pass
    try:
        player.is_injured = True
        player.injury_type = type_label
        player.games_remaining_injured = games
        player.last_injury = type_label
        player.injured_today = True  # countdown starts with the NEXT game
        # Concussion protocol flag (additive; old-save safe via getattr).
        player.in_concussion_protocol = bool(spec.get("concussion", False))
        # Career-ending flag
        if _career_ending:
            player.career_ending_injury = True
    except Exception:
        pass
    # Career ledgers: these were seeded at generation and never updated.
    # days_missed (season) ticks in main._process_injury_recovery; the
    # career count is seeded here at diagnosis.
    try:
        player.career_games_missed = (
            int(getattr(player, "career_games_missed", 0) or 0) + games)
    except Exception:
        pass
    if spec.get("concussion", False):
        try:
            player.career_concussions = (
                int(getattr(player, "career_concussions", 0) or 0) + 1)
        except Exception:
            pass
    # Repeat-injury ledger (additive, capped): same-region aggravations and
    # concussion history now exist as data instead of a dead last_injury str.
    try:
        hist = getattr(player, "injury_history", None)
        if not isinstance(hist, list):
            hist = []
        hist.append({"type": type_label, "region": spec.get("region", "?"),
                     "games": games,
                     "concussion": bool(spec.get("concussion", False))})
        player.injury_history = hist[-8:]
    except Exception:
        pass
    if team is not None and games >= LONG_TERM_THRESHOLD:
        flag_long_term_injury(team, player, games)
    return games


# ---------------------------------------------------------------------------
# Hit-path circumstance severity (additive reads of W5's hit context)
# ---------------------------------------------------------------------------
# W5 owns hit generation. The injury system only READS the hit context
# (hit_type / impact tier / hitter & victim attributes / zone) to scale
# severity -- never writes back into hit resolution. Coordinate: if W5
# changes the hit pipeline's context shape, only _hit_context() below needs
# updating.

def hit_circumstance(hitter, victim, hit_type, impact, sim=None):
    """Describe the dangerous circumstances of an injury-causing hit.

    Returns dict(dirty, big, mismatch, open_ice). All reads defensive.
    """
    ctx = {"dirty": False, "big": False, "mismatch": False, "open_ice": False}
    try:
        ht_name = getattr(hit_type, "name", "") or str(hit_type)
        ctx["dirty"] = ht_name in ("CHARGING", "BOARDING")
        ctx["big"] = (impact == 2)
        # Enforcer-vs-small-star mismatch: a heavyweight enforcer running a
        # star 20+ lbs lighter. (Star threshold 85 matches the feud logic.)
        try:
            from player_archetypes import get_archetype as _arch
            hitter_arch = _arch(hitter)
        except Exception:
            hitter_arch = ""
        try:
            victim_star = _ovr(victim) >= 85
        except Exception:
            victim_star = False
        try:
            hw = float(getattr(hitter, "weight", 200) or 200)
            vw = float(getattr(victim, "weight", 200) or 200)
        except Exception:
            hw, vw = 200.0, 200.0
        ctx["mismatch"] = (str(hitter_arch).upper() == "ENFORCER" and victim_star
                           and (hw - vw) >= 20)
        # Center-ice collision at speed ~= neutral-zone, big-impact hit.
        try:
            zone = getattr(sim, "current_zone", None) if sim is not None else None
            zval = getattr(zone, "value", "") or ""
            ctx["open_ice"] = (zval == "neutral_zone") and ctx["big"]
        except Exception:
            pass
    except Exception:
        pass
    return ctx


def hit_injury_spec(base_games, ctx, victim=None):
    """Severity/type for a hit-caused injury given its circumstance.

    base_games: the hit band roll (dirty 4-10 / big 2-6 / routine 1-4, after
    W3's proneness scaling in _apply_hit_injury). Circumstance bumps are
    DESIGN (feel-tuned); concussion odds rise with danger -- today concussion
    is flavor text only, here it becomes a real protocol injury.
    Returns (games, type_label, is_concussion). Never raises.
    """
    try:
        games = max(1, int(base_games))
        # Circumstance bumps (design): each dangerous element adds games.
        # Dirty hits are the most penalized because the league treats them
        # that way too (DoPS scale) -- and the audit brief calls for dirty
        # hits to hurt more.
        if ctx.get("dirty"):
            games += 2
        if ctx.get("mismatch"):
            games += 2
        if ctx.get("open_ice"):
            games += 2
        # Concussion probability scales with danger (design; grounded anchor:
        # ~5.6% of all injuries are concussions [R3], dirty hits on stars
        # should run far hotter than the average rub-out).
        p = 0.03
        if ctx.get("dirty"):
            p += 0.08
        if ctx.get("mismatch"):
            p += 0.06
        if ctx.get("open_ice"):
            p += 0.05
        if ctx.get("big"):
            p += 0.03
        p = min(0.30, p)
        if random.random() < p:
            cg = concussion_games(victim)
            # A concussion overrides a trivial base band -- brain injuries
            # are never "day-to-day" the way a charley horse is.
            return max(games, cg), "Concussion", True
        # Otherwise: body region + type from the shared grounded tables.
        # Dirty hits bias toward the head (head-hunting is why they're dirty).
        region = _roll_region()
        if ctx.get("dirty") and random.random() < 0.20:
            region = "HEAD"
        type_label = random.choice(REGION_TYPES.get(region, REGION_TYPES["OTHER"]))
        return games, type_label, False
    except Exception:
        return max(1, int(base_games or 1)), "Bruised ribs", False


# ---------------------------------------------------------------------------
# Medical staff: quality -> recovery time + setback odds
# ---------------------------------------------------------------------------

def medical_staff_quality(team):
    """0-100 medical department quality for a team.

    Reads TEAM_DOCTOR + PHYSIOTHERAPIST via team.get_staff_by_role
    (additive read; never writes). Falls back to 50 (league-average) when
    the club employs no medical staff. Doctor and physio count equally.
    Never raises.
    """
    try:
        from game_classes import StaffRole
        docs = team.get_staff_by_role(StaffRole.TEAM_DOCTOR) or []
        phys = team.get_staff_by_role(StaffRole.PHYSIOTHERAPIST) or []
    except Exception:
        return 50.0
    ratings = []
    for s in list(docs)[:1] + list(phys)[:1]:
        try:
            ratings.append(float(s.overall_rating))
        except Exception:
            continue
    if not ratings:
        return 50.0
    return max(1.0, min(100.0, sum(ratings) / len(ratings)))


def recovery_time_mult(team):
    """Multiply a diagnosed absence by this (staff-modified recovery).

    Design: elite staff (90) -> 0.80x, average (50) -> 1.0x, poor (10) ->
    1.20x. Applied at diagnosis in apply_injury(); the staff UI reports it.
    """
    q = medical_staff_quality(team)
    return max(0.80, min(1.20, 1.0 + (50.0 - q) * 0.005))


def roll_setback(player, team):
    """Games ADDED by a rehab setback on this recovery tick (0 = none).

    Base 5%/tick for injuries with 5+ games left; medical quality roughly
    halves it at elite staff, +50% at poor staff (design). The pure
    countdown is gone: recovery now has variance. Never raises.
    """
    try:
        remaining = int(getattr(player, "games_remaining_injured", 0) or 0)
    except Exception:
        return 0
    if remaining < 5:
        return 0
    try:
        q = medical_staff_quality(team)
        mult = (100.0 - q + 25.0) / 75.0  # q=50 -> 1.0; 90 -> 0.47; 10 -> 1.53
    except Exception:
        mult = 1.0
    try:
        if random.random() < 0.05 * mult:
            return random.randint(1, 3)
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Long-term injury bookkeeping -> AI replacement (flagged follow-up)
# ---------------------------------------------------------------------------
# The injury side is fully built here (queue + flag on the team object).
# The AI CONSUMER is a flagged follow-up, not half-built:
#   ai_team_management._evaluate_roster_moves should read
#   team.injury_callup_queue (list of {player_id, position, games_out, name})
#   when team.needs_injury_replacement is set, and create AIDecision
#   injury_callup entries promoting a healthy AHL skater at the same
#   position -- with cap/roster-legality checks and a send-down when the
#   injured player returns. That is feature-sized; see W4 report.

def flag_long_term_injury(team, player, games):
    """Record a 10+ game injury for AI replacement consideration."""
    if games < LONG_TERM_THRESHOLD:
        return
    try:
        q = getattr(team, "injury_callup_queue", None)
        if not isinstance(q, list):
            q = []
            team.injury_callup_queue = q
        pid = getattr(player, "id", "")
        if all(e.get("player_id") != pid for e in q):
            try:
                pos = getattr(getattr(player, "primary_position", None),
                              "name", "")
            except Exception:
                pos = ""
            q.append({"player_id": pid, "position": pos, "games_out": games,
                      "name": getattr(player, "full_name", "a player")})
        team.needs_injury_replacement = True
    except Exception:
        pass


def clear_injury_flag(team, player):
    """Drop a recovered player from the replacement queue."""
    try:
        pid = getattr(player, "id", None)
        q = getattr(team, "injury_callup_queue", None)
        if isinstance(q, list):
            q[:] = [e for e in q if e.get("player_id") != pid]
            if not q:
                team.needs_injury_replacement = False
    except Exception:
        pass
