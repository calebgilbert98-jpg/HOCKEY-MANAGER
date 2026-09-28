"""Undrafted European free agents ("the Panarin pipeline").

Real phenomenon: every summer a thin trickle of undrafted Europeans aged
22-28 (Panarin, Zuccarello, Bobrovsky, Dadonov types) cross the pond as
free agents from the SHL, KHL, Liiga, NL, DEL, and the Czech/Slovak
Extraligas. This module generates that trickle: a SMALL annual batch of
free agents with realistic attributes, so both the user and the AI can
sign them through the NORMAL contract/FA systems.

TUNING (per Chris, 2026-09-28 -- the pool must be THIN):
- Batch: 4-8 players per offseason, weighted small (expected ~5.0/year).
- ~75% are clear AHL/tweener organizational depth (overall 70-77):
  nobody worth an NHL contract; lotto tickets at best.
- ~23% are NHL gambles (overall 78-83): 0-1 per year is even worth an
  NHL-contract gamble ("might become a 13th forward").
- ~10% per offseason, ONE impact player (top-6 F / top-4 D / starting
  goalie, overall 84-89). Pure probability -- no schedule/counter --
  so it lands roughly once every 8-12 years. A rare treat, not a flood.
- 10-year expectation: ~50 players, ~39 depth, ~9 gambles, ~1 impact.
  Real NHL contributors from this pool over a decade: a handful.

The AI must treat these as gambles (report-only note in HOOK NOTES below):
free_agent_offer decisions carry the AI's normal estimated salary, so a
guard on is_euro_import is recommended in _evaluate_free_agency.

Design rules: new Players with fresh ids (never pulled from
league.draft_prospects), team_name="Free Agent" so both the database
manager path (get_free_agents filters team_name == "Free Agent") and the
league.free_agents fallback see them. They are new objects -- no
prospect duplication possible by construction.
"""

import random
from typing import Dict, List, Optional

from game_classes import Contract, Player, PlayerPosition

try:
    from draft_generator import get_random_birthplace, get_random_name
except ImportError:  # pragma: no cover - headless safety
    def get_random_name(country):  # type: ignore
        return "Anon", "Europen"
    def get_random_birthplace(country):  # type: ignore
        return "Unknown"

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

# Nationality -> the European pro league the player is crossing from.
# get_random_name() accepts whatever nationality string it is given (it
# falls back to the "Other" pool for nations another worker hasn't added
# yet), so this mapping must never KeyError.
LEAGUE_SOURCES = [
    "SHL", "KHL", "Liiga", "NL", "DEL",
    "Czech Extraliga", "Slovak Extraliga",
    "ICEHL", "Eliteserien", "AHL-equivalent",
]

NATIONALITY_SOURCE = {
    "Sweden": "SHL",
    "Finland": "Liiga",
    "Russia": "KHL",
    "Switzerland": "NL",
    "Germany": "DEL",
    "Czechia": "Czech Extraliga",
    "Slovakia": "Slovak Extraliga",
    "Austria": "ICEHL",
    "Slovenia": "ICEHL",
    "Latvia": "KHL",
    "Norway": "Eliteserien",
    "Denmark": "SHL",
    "France": "NL",
    "Kazakhstan": "KHL",
    "Belarus": "KHL",
    "Ukraine": "AHL-equivalent",
}

EURO_NATIONS = list(NATIONALITY_SOURCE.keys())

# ---------------------------------------------------------------------------
# Quality tiers (see module docstring for the 10-year expectation math)
# ---------------------------------------------------------------------------

# Per-player tier rolls. Impact stars are NOT rolled per player -- they are
# one 10%/offseason roll in generate_euro_free_agents (see below).
QUALITY_TIERS = {
    # Clear AHL/tweener material: organizational depth, not NHL options.
    "depth":  {"share": 0.79, "overall": (70, 77), "grades": ["C+", "C", "C-", "B-"]},
    # Worth an NHL-contract gamble: 13th-forward / 7th-D / backup lotto.
    # ~0.95 of these per year => a typical year has 0-1 such gambles.
    "gamble": {"share": 0.19, "overall": (78, 83), "grades": ["B-", "C+"]},
}

# Chance of one genuine impact player (top-6 F / top-4 D / starting
# goalie, overall 84-89, grade A-/B+) appearing in a given offseason.
# 0.10/year => ~1 every 8-12 years. Pure probability, NOT a
# counter/schedule (Chris: a rare treat, never on rails).
IMPACT_PROBABILITY = 0.10
IMPACT_OVERALL = (84, 89)
IMPACT_GRADES = ["A-", "B+"]

# Batch size: small, weighted toward 4-5. Expected value ~5.0/year.
BATCH_SIZE_CHOICES = [4, 5, 6, 7, 8]
BATCH_SIZE_WEIGHTS = [30, 30, 20, 12, 8]

# Realistic positional mix with ~15% goalies.
POSITION_WEIGHTS = [
    (PlayerPosition.CENTER, 0.22),
    (PlayerPosition.LEFT_WING, 0.16),
    (PlayerPosition.RIGHT_WING, 0.16),
    (PlayerPosition.LEFT_DEFENSE, 0.13),
    (PlayerPosition.RIGHT_DEFENSE, 0.13),
    (PlayerPosition.DEFENSE, 0.05),
    (PlayerPosition.GOALIE, 0.15),
]

# Every attribute that feeds Player.overall_rating() for any position
# (skater formulas + goalie formula). Setting ALL of these to the tier
# target (+/- jitter) pins the computed overall to the tier band, since
# each formula is a weighted average of them.
RATING_ATTRS = [
    "skating", "shooting", "shooting_accuracy", "shooting_power",
    "passing", "passing_accuracy", "passing_creativity", "deking",
    "stickhandling", "vision", "hockey_iq", "offensive_awareness",
    "defensive_awareness", "faceoffs", "faceoff_wins", "composure",
    "endurance", "determination", "off_the_puck", "one_timer",
    "loose_puck", "wristshot", "slapshot", "backhand", "screen_shots",
    "strength", "checking", "balance", "bodycheck", "pokecheck",
    "shot_blocking", "aggressiveness", "anticipation", "pressure_player",
    # goalie formula
    "goaltending", "reflexes", "positioning", "rebound_control",
    "puck_handling", "glove_hand", "stick_side", "breakaway_skill",
    "confidence", "focus",
]

# Fringe/card attributes that don't move overall much: set near target
# so the player card reads plausibly.
FRINGE_ATTRS = [
    "flair", "teamwork", "leadership", "discipline", "consistency",
    "important_matches", "coachability", "work_ethic", "adaptability",
    "creativity", "decision_making", "acceleration", "agility",
    "speed", "stamina", "durability",
]


def _source_for(nationality: str) -> str:
    return NATIONALITY_SOURCE.get(nationality, "AHL-equivalent")


def _roll_position(rng: random.Random) -> PlayerPosition:
    positions, weights = zip(*POSITION_WEIGHTS)
    return rng.choices(positions, weights=weights, k=1)[0]


def _roll_tier(rng: random.Random) -> str:
    tiers, weights = zip(*[(t, c["share"]) for t, c in QUALITY_TIERS.items()])
    return rng.choices(tiers, weights=weights, k=1)[0]


# overall_rating() is NOT a plain average: each position formula's weights
# sum to more than 1 (measured from game_classes.py: CENTER 1.10,
# LW/RW 1.20, LD/RD/D 1.16, GOALIE 1.00). To land a target overall, the
# underlying attributes must be divided by the position's weight sum.
POSITION_WEIGHT_SUM = {
    PlayerPosition.CENTER: 1.10,
    PlayerPosition.LEFT_WING: 1.20,
    PlayerPosition.RIGHT_WING: 1.20,
    PlayerPosition.LEFT_DEFENSE: 1.16,
    PlayerPosition.RIGHT_DEFENSE: 1.16,
    PlayerPosition.DEFENSE: 1.16,
    PlayerPosition.GOALIE: 1.00,
}


def _set_attributes(player: Player, target: int, rng: random.Random) -> None:
    """Pin rating attributes so overall_rating() lands at `target`.

    The rating formulas are weighted sums whose weights exceed 1, so the
    attributes are set to target / weight_sum (+/- small jitter)."""
    wsum = POSITION_WEIGHT_SUM.get(player.primary_position, 1.0)
    base = target / wsum
    for attr in RATING_ATTRS:
        setattr(player, attr,
                max(1, min(100, int(base + rng.randint(-2, 2)))))
    for attr in FRINGE_ATTRS:
        setattr(player, attr,
                max(1, min(100, int(base + rng.randint(-6, 4)))))
    # 100-scale injury proneness: lower is better, keep these players
    # durable-ish like any professional.
    player.injury_proneness = rng.randint(20, 55)
    player.hitting_tendency = rng.randint(20, 80)
    player.shoot_pass_tendency = rng.randint(20, 80)


def _make_player(nationality: str, position: PlayerPosition, age: int,
                 tier: str, year: int, rng: random.Random) -> Player:
    source = _source_for(nationality)
    first, last = get_random_name(nationality)
    try:
        birthplace = get_random_birthplace(nationality)
    except Exception:
        birthplace = "Unknown"

    player = Player(first_name=first, last_name=last, age=age,
                    primary_position=position)

    # Identity / origin
    player.nationality = nationality
    player.birthplace = birthplace
    player.birth_date = (f"{year - age}-{rng.randint(1, 12):02d}-"
                         f"{rng.randint(1, 28):02d}")
    player.draft_position = "Undrafted"  # never drafted -- that's the point
    player.draft_year = (year - age) + 18  # eligible year they were passed over

    # Physical frame by role
    if position == PlayerPosition.GOALIE:
        feet = rng.choices([5, 6], weights=[20, 80])[0]
        inches = rng.randint(8, 11) if feet == 5 else rng.randint(0, 5)
        player.weight = rng.randint(180, 225)
    elif position in (PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE,
                      PlayerPosition.RIGHT_DEFENSE):
        feet = rng.choices([5, 6], weights=[30, 70])[0]
        inches = rng.randint(10, 11) if feet == 5 else rng.randint(0, 4)
        player.weight = rng.randint(180, 235)
    else:
        feet = rng.choices([5, 6], weights=[40, 60])[0]
        inches = rng.randint(8, 11) if feet == 5 else rng.randint(0, 3)
        player.weight = rng.randint(165, 215)
    player.height = f"{feet}'{inches}\""
    player.handedness = rng.choices(["Left", "Right"], weights=[60, 40])[0]

    # Quality
    cfg = QUALITY_TIERS[tier]
    lo, hi = cfg["overall"]
    target = rng.randint(lo, hi)
    _set_attributes(player, target, rng)
    player.potential_grade = rng.choice(cfg["grades"])
    player.true_potential_grade = player.potential_grade
    player.potential = rng.randint(10, 16)
    player.peak_rating = rng.randint(10, 18)

    # Career baselines: years of European pro hockey, zero NHL games.
    # Keeps Calder eligibility real (NHL GP is what counts) and gives AI
    # evaluation something to chew on.
    pro_seasons = max(1, age - 18)
    if position == PlayerPosition.GOALIE:
        gp = pro_seasons * rng.randint(30, 45)
        player.career_games_goalie = gp
        player.career_games = gp
        player.career_wins = int(gp * rng.uniform(0.40, 0.55))
        player.career_losses = int(gp * rng.uniform(0.30, 0.45))
        player.career_shutouts = int(gp * rng.uniform(0.05, 0.12))
        player.goalie_temperament = rng.choice(["fiery", "calm", "unorthodox"])
    else:
        gp = pro_seasons * rng.randint(40, 52)
        player.career_games = gp
        rate = 0.25 + (target - 70) * 0.012  # better players score more
        pts = int(gp * rate)
        player.career_goals = int(pts * rng.uniform(0.35, 0.45))
        player.career_assists = pts - player.career_goals
        player.career_points = pts
    player.nhl_games_played = 0
    player.prior_nhl_gp = []
    player.is_rookie = True
    player.seasons_played = 0

    # Free-agent state: the NORMAL pool conventions. database_manager's
    # get_free_agents() filters team_name == "Free Agent"; the legacy
    # league.free_agents list is appended by run_euro_free_agency().
    player.team_name = "Free Agent"
    # Unsigned placeholder deal -- the signing path overwrites salary/years.
    player.contract = Contract(salary=800_000, years_remaining=0)
    player.squad_status = "Surplus"

    # Euro-import markers (plain attrs, not dataclass fields -- old-save safe).
    player.is_euro_import = True
    player.source_league = source
    player.euro_import_year = year

    return player


def _upgrade_to_impact(player: Player, rng: random.Random) -> Player:
    """Turn a batch member into the rare impact player."""
    lo, hi = IMPACT_OVERALL
    target = rng.randint(lo, hi)
    _set_attributes(player, target, rng)
    player.potential_grade = rng.choice(IMPACT_GRADES)
    player.true_potential_grade = player.potential_grade
    player.potential = rng.randint(15, 19)
    player.peak_rating = rng.randint(16, 20)
    player.squad_status = "Key Player"
    return player


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_euro_free_agents(league, year: int,
                             rng_seed: Optional[int] = None) -> List[Player]:
    """Create one offseason's batch of undrafted European free agents.

    Returns new Player objects (fresh ids -- never pulled from
    league.draft_prospects). Deterministic when rng_seed is pinned.
    """
    rng = random.Random(rng_seed)
    if rng_seed is not None:
        random.seed(rng_seed)  # draft_generator names + Player factories

    batch_size = rng.choices(BATCH_SIZE_CHOICES,
                             weights=BATCH_SIZE_WEIGHTS, k=1)[0]
    existing_ids = {getattr(p, "id", None)
                    for p in getattr(league, "draft_prospects", []) or []}

    players: List[Player] = []
    for _ in range(batch_size):
        nation = rng.choice(EURO_NATIONS)
        position = _roll_position(rng)
        age = rng.randint(22, 28)
        tier = _roll_tier(rng)
        player = _make_player(nation, position, age, tier, year, rng)
        if player.id in existing_ids:  # never collide with a prospect
            continue
        existing_ids.add(player.id)
        players.append(player)

    # The rare impact player: one ~10%/year roll, upgrading a random
    # batch member. Pure probability -- no counter/schedule.
    impact = rng.random() < IMPACT_PROBABILITY and players
    if impact:
        _upgrade_to_impact(rng.choice(players), rng)

    return players


def euro_fa_news_items(players: List[Player]) -> List[str]:
    """Short news strings for the notable ones only (gambles + impact)."""
    items = []
    for p in players:
        lo, hi = IMPACT_OVERALL
        ovr = p.overall_rating()
        name = p.full_name
        src = getattr(p, "source_league", "Europe")
        if lo <= ovr <= hi:
            items.append(
                f"{src} star {name} ({p.age}) is signing in North America "
                f"as a free agent -- a potential impact addition.")
        elif ovr >= 78:
            items.append(
                f"{name}, a {p.age}-year-old {p.primary_position.value} "
                f"standout in the {src}, is coming over to North America "
                f"as a free agent.")
    return items


def run_euro_free_agency(league, year: int, app=None) -> Dict:
    """THE hook: call once per offseason. Generates the batch, drops it
    into the FA pool the same way existing code does, posts news, and
    returns a summary dict.

    All guarded in try/except -- generation must never break the offseason.
    """
    summary = {"added": 0, "star": False, "news": [], "impact": None}
    try:
        seed = rng_seed_default(league, year)
        players = generate_euro_free_agents(league, year, rng_seed=seed)

        # Canonical FA pool: append to league.free_agents (the list the AI
        # FA path at main.py:5771 actually reads), AND register with the
        # database manager's all_players so database_manager.get_free_agents()
        # (team_name == "Free Agent") sees them too.
        pool = getattr(league, "free_agents", None)
        if pool is None:
            pool = []
            league.free_agents = pool
        db_all = None
        try:
            gm = getattr(league, "_game_manager", None)
            dbm = getattr(gm, "database_manager", None)
            db_all = getattr(dbm, "all_players", None)
        except Exception:
            db_all = None

        for p in players:
            try:
                if p not in pool:
                    pool.append(p)
                if isinstance(db_all, dict):
                    db_all[p.id] = p
            except Exception:
                continue

        news = euro_fa_news_items(players)
        impact_players = [p for p in players
                          if IMPACT_OVERALL[0] <= p.overall_rating()
                          <= IMPACT_OVERALL[1]]
        summary = {
            "added": len(players),
            "star": bool(impact_players),
            "news": news,
            "impact": (impact_players[0].full_name
                       if impact_players else None),
        }

        # Post news through the app if it offers a news API; otherwise the
        # coordinator can surface summary["news"].
        posted = False
        if app is not None:
            for story in news:
                try:
                    if hasattr(app, "add_news_story"):
                        app.add_news_story(story)
                    elif hasattr(app, "add_news"):
                        app.add_news(story)
                    else:
                        break
                    posted = True
                except Exception:
                    continue
        if not posted:
            summary["news"] = news
    except Exception as e:
        print(f"Euro FA generation skipped ({e})")
    return summary


def rng_seed_default(league, year: int) -> Optional[int]:
    """Deterministic per-(league, year) seed so the batch is stable if the
    hook is ever evaluated twice for the same offseason."""
    try:
        name = getattr(league, "league_name", "") or ""
        return (abs(hash((name, year))) % (2 ** 31)) or 1
    except Exception:
        return None


# ---------------------------------------------------------------------------
# HOOK NOTES (for the coordinator wiring this in)
# ---------------------------------------------------------------------------
#
# RECOMMENDED INSERTION POINT -- main.py, method _start_offseason
# (line 11402; the offseason welcome runs ~11451-11472). The draft class is
# generated there (line ~11452: self.league.draft_prospects =
# generate_draft_class(...)), then current_date jumps to July 1. Insert
# right after the draft-class line, before the date jump:
#
#     # Undrafted European free agents cross the pond (additive).
#     try:
#         from euro_free_agents import run_euro_free_agency
#         run_euro_free_agency(self.league, self.league.season_year, app=self)
#     except Exception as _e:
#         print(f"Euro FA import skipped: {_e}")
#
# This is the real game's once-per-offseason path (end_of_season ->
# _start_offseason). database_manager.simulate_offseason_movement() is
# dead code (never called) and automated_season_flow._free_agency_opens
# (automated_season_flow.py:454) is a print-only milestone not used by
# the real game loop -- don't hook there.
#
# AI-FA VISIBILITY VERDICT:
# - VISIBLE. _evaluate_free_agency (ai_team_management.py:282) iterates
#   the exact list we append to (main.py:5771 passes self.league.free_agents
#   into process_daily_decisions). No nationality/origin/source_league
#   filter exists anywhere in the FA path -- Euro FAs are evaluated
#   identically to existing free agents.
# - Age filters: prefer_youth teams skip age>30 (no effect -- we're 22-28);
#   prefer_experience teams skip age<23 (only age-22 Euro FAs skipped by
#   those teams; existing behavior, no change needed).
# - CONTRACT-LEVEL CAVEAT (report only, no edit made): AI signing decisions
#   are currently DECISION-ONLY -- I found no executor that consumes
#   free_agent_offer AIDecisions (main.py:5779 only logs them), so AI
#   teams sign nobody today and Euro FAs get zero AI offers for free.
#   IF a consumer is ever wired, _estimate_player_salary
#   (ai_team_management.py:438) would offer these players $1.2M-$6.5M
#   (and ~$5-6.5M to an 84-89 impact player) -- too big for gambles.
#   Minimal guard when that happens: in _evaluate_free_agency, after the
#   age checks, add:
#       if getattr(fa, "is_euro_import", False):
#           estimated_salary = min(estimated_salary, 1_000_000)
#   i.e. AI treats every Euro import as a league-min/ELC gamble.
