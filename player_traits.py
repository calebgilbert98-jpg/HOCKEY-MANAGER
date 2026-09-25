"""Player traits system for Puck Dynasty.

Traits represent exceptional abilities that make players perform better at
specific skills. A "Big Hitter" throws harder, more frequent checks. A
"Speedster" creates more breakaways. Traits are earned from attributes
(typically 36+ on the internal ~50 scale, i.e. ~85+ on the 1-100 display
scale) and provide concrete simulation bonuses.

Traits are stored as a list of trait IDs on player.traits.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Trait:
    """A single player trait definition."""
    id: str
    name: str
    description: str
    category: str  # 'offense', 'defense', 'physical', 'skating', 'mental', 'goalie'
    # Attribute requirements: [(attr_name, min_value), ...] — all must be met
    requirements: List[Tuple[str, int]]
    # Sim effects: {effect_key: bonus_value}. Documented per-effect in GameSim.
    sim_effects: Dict[str, float] = field(default_factory=dict)
    # Positions this trait applies to (None = all skaters)
    positions: List[str] = None


# ---------------------------------------------------------------------------
# Skater traits
# ---------------------------------------------------------------------------

SKATER_TRAITS = [
    Trait(
        id="big_hitter",
        name="Big Hitter",
        description="Devastating body checks that separate opponents from the puck.",
        category="physical",
        requirements=[("checking", 43), ("strength", 37), ("aggressiveness", 35)],
        sim_effects={
            "hit_frequency_mult": 1.10,   # throws ~10% more hits
            "hit_force_mult": 1.12,       # hits ~12% more effective
            "intimidation": 0.05,         # opponents slightly more likely to rush plays
            "big_hit_injury_bonus": 0.03, # +3% injury chance when landing a big hit
        },
    ),
    Trait(
        id="speedster",
        name="Speedster",
        description="Blazing speed that creates breakaways and beats defenders wide.",
        category="skating",
        requirements=[("speed", 43), ("acceleration", 37)],
        sim_effects={
            "breakaway_chance_mult": 1.12,
            "zone_entry_mult": 1.08,
            "backcheck_mult": 1.08,
        },
    ),
    Trait(
        id="sniper",
        name="Sniper",
        description="Elite release and accuracy; shoots more and scores more.",
        category="offense",
        requirements=[("shooting", 43), ("shooting_accuracy", 39)],
        sim_effects={
            "shot_quality_mult": 1.08,
            "shot_frequency_mult": 1.10,
            "one_timer_mult": 1.08,
        },
    ),
    Trait(
        id="playmaker",
        name="Playmaker",
        description="Sees plays before they develop; threads passes through traffic.",
        category="offense",
        requirements=[("passing", 43), ("passing_creativity", 37)],
        sim_effects={
            "pass_success_mult": 1.08,
            "assist_chance_mult": 1.10,
            "giveaway_reduction": 0.10,
        },
    ),
    Trait(
        id="dangler",
        name="Dangler",
        description="Sick hands — beats defenders one-on-one with dekes.",
        category="offense",
        requirements=[("deking", 43), ("agility", 37)],
        sim_effects={
            "deke_success_mult": 1.12,
            "controlled_entry_mult": 1.08,
        },
    ),
    Trait(
        id="grinder",
        name="Grinder",
        description="Relentless on the forecheck; wins puck battles along the boards.",
        category="physical",
        requirements=[("forechecking", 43), ("determination", 37), ("balance", 35)],
        sim_effects={
            "puck_battle_mult": 1.10,
            "forecheck_pressure_mult": 1.12,
            "turnover_forcing_mult": 1.08,
        },
    ),
    Trait(
        id="shot_blocker",
        name="Shot Blocker",
        description="Fearlessly gets in shooting lanes.",
        category="defense",
        requirements=[("shot_blocking", 43)],
        sim_effects={
            "block_chance_mult": 1.15,
        },
    ),
    Trait(
        id="shutdown",
        name="Shutdown Defender",
        description="Erases opponents defensively with positioning and stick work.",
        category="defense",
        requirements=[("defensive_awareness", 43), ("pokecheck", 37)],
        sim_effects={
            "defensive_stops_mult": 1.05,
            "takeaway_mult": 1.12,
        },
    ),
    Trait(
        id="two_way",
        name="Two-Way",
        description="Impacts the game at both ends of the ice.",
        category="defense",
        requirements=[("defensive_awareness", 43), ("offensive_awareness", 37)],
        sim_effects={
            "transition_mult": 1.06,
            "defensive_stops_mult": 1.05,
            "shot_quality_mult": 1.04,
        },
    ),
    Trait(
        id="enforcer",
        name="Enforcer",
        description="Polices the ice; teammates play bigger with him around.",
        category="physical",
        requirements=[("strength", 43), ("aggressiveness", 39)],
        sim_effects={
            "fight_win_mult": 1.15,
            "team_toughness_aura": 0.05,   # teammates get +5% hit effectiveness
            "intimidation": 0.08,
        },
    ),
    Trait(
        id="clutch",
        name="Clutch",
        description="Elevates when the game is on the line.",
        category="mental",
        requirements=[("pressure_player", 43), ("composure", 37)],
        sim_effects={
            "overtime_mult": 1.08,
            "shootout_mult": 1.10,
            "late_game_mult": 1.06,   # last 5 minutes, tied or down 1
        },
    ),
    Trait(
        id="iron_man",
        name="Iron Man",
        description="Rarely injured; recovers quickly when hurt.",
        category="physical",
        requirements=[("durability", 43)],
        sim_effects={
            "injury_chance_mult": 0.75,
            "injury_duration_mult": 0.85,
        },
    ),
    Trait(
        id="one_timer_specialist",
        name="One-Timer Specialist",
        description="Lethal on set-up one-timers, especially on the power play.",
        category="offense",
        requirements=[("one_timer", 43), ("shooting_power", 37)],
        sim_effects={
            "one_timer_mult": 1.12,
            "pp_shot_quality_mult": 1.08,
        },
    ),
]

# ---------------------------------------------------------------------------
# Goalie traits
# ---------------------------------------------------------------------------

GOALIE_TRAITS = [
    Trait(
        id="wall",
        name="Wall",
        description="Nearly impossible to beat cleanly; squares to every shot.",
        category="goalie",
        requirements=[("positioning", 43)],
        sim_effects={
            "save_chance_mult": 1.04,
        },
    ),
    Trait(
        id="puck_handler",
        name="Puck Handler",
        description="Acts as a third defenseman; starts breakouts with crisp passes.",
        category="goalie",
        requirements=[("puck_handling", 43)],
        sim_effects={
            "breakout_pass_mult": 1.12,
            "dump_in_negation": 0.10,
        },
    ),
    Trait(
        id="big_game_goalie",
        name="Big-Game Goalie",
        description="Stands tallest when the stakes are highest.",
        category="goalie",
        requirements=[("pressure_player", 43), ("composure", 37)],
        sim_effects={
            "overtime_mult": 1.06,
            "shootout_mult": 1.08,
            "playoff_mult": 1.05,
        },
    ),
]

ALL_TRAITS = {t.id: t for t in SKATER_TRAITS + GOALIE_TRAITS}


def infer_traits(player) -> List[str]:
    """Infer trait IDs from a player's attributes.

    Returns a list of trait IDs the player qualifies for. A player can have
    multiple traits, but we cap at 3 to keep them special.
    """
    from game_classes import PlayerPosition

    is_goalie = player.primary_position == PlayerPosition.GOALIE
    pool = GOALIE_TRAITS if is_goalie else SKATER_TRAITS

    qualified = []
    for trait in pool:
        meets_all = True
        for attr_name, min_val in trait.requirements:
            if getattr(player, attr_name, 0) < min_val:
                meets_all = False
                break
        if meets_all:
            qualified.append(trait.id)

    # Cap at 3 traits, preferring the ones with the highest attribute margins
    if len(qualified) > 3:
        def margin(tid):
            trait = ALL_TRAITS[tid]
            return sum(getattr(player, attr, 0) - min_v
                       for attr, min_v in trait.requirements)
        qualified.sort(key=margin, reverse=True)
        qualified = qualified[:3]

    return qualified


def get_trait(trait_id: str) -> Trait:
    """Get a trait definition by ID."""
    return ALL_TRAITS.get(trait_id)


def get_player_traits(player) -> List[Trait]:
    """Get full trait definitions for a player's trait IDs."""
    trait_ids = getattr(player, "traits", []) or []
    return [ALL_TRAITS[tid] for tid in trait_ids if tid in ALL_TRAITS]


def has_trait(player, trait_id: str) -> bool:
    """Check if a player has a specific trait."""
    return trait_id in (getattr(player, "traits", []) or [])


def get_sim_bonus(player, effect_key: str, default: float = 1.0) -> float:
    """Get the combined multiplier for a sim effect from all player traits.

    Multiplicative effects (ending in _mult) multiply together.
    Additive effects (like intimidation) sum together.
    """
    traits = get_player_traits(player)
    if not traits:
        return default

    if effect_key.endswith("_mult"):
        result = 1.0
        for trait in traits:
            if effect_key in trait.sim_effects:
                result *= trait.sim_effects[effect_key]
        return result
    else:
        # Additive
        result = 0.0
        for trait in traits:
            result += trait.sim_effects.get(effect_key, 0.0)
        return result if result != 0.0 else default
