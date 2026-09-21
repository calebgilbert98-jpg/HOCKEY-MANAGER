# position_specific_attributes.py
# This file contains the updated Player class with position-specific attributes

from dataclasses import dataclass, field
import random
from enum import Enum
from typing import Dict, List, Optional
import itertools

# Use the same enums and counters as the original game_classes.py
from game_classes import PlayerPosition, PlayerRole, GameBalance, player_id_counter
from game_classes import Contract, PlayerStats

@dataclass
class PlayerV2:
    """Represents a hockey player with position-specific attributes."""
    first_name: str
    last_name: str
    age: int
    primary_position: PlayerPosition
    
    id: int = field(default_factory=lambda: next(player_id_counter), init=False)
    jersey_number: int = field(default_factory=lambda: random.randint(1, 98))
    captaincy: str = None # 'C', 'A', or None
    
    # Common attributes for all players
    contract: Contract = field(default_factory=Contract)
    stats: PlayerStats = field(default_factory=PlayerStats)
    team_name: str = "Free Agent"
    x: int = 0  # X position on ice
    y: int = 0  # Y position on ice
    potential_grade: str = field(default_factory=lambda: random.choice(['A', 'B', 'C', 'D', 'F']))
    morale: int = 10  # Player morale on a scale of 1-20
    
    # Mental attributes for all players
    aggression: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    anticipation: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    bravery: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    composure: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    concentration: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    flair: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    influence: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    leadership: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    teamwork: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    # Physical attributes for all players
    acceleration: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    agility: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    balance: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    # Remove pace and offensive_read, add new attributes
    off_the_puck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    wristshot: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    slapshot: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    pokecheck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    bodycheck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    one_timer: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    backhand: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    faceoff_wins: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    screen_shots: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    loose_puck: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    creativity: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    pressure_player: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    speed: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    stamina: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    strength: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    # Technical attributes for skaters - initialized only for skaters in __post_init__
    checking: int = 1
    deflection: int = 1
    deking: int = 1
    faceoffs: int = 1
    hitting: int = 1
    off_the_puck: int = 1  # Movement without the puck
    wristshot: int = 1
    slapshot: int = 1
    passing: int = 1
    pokecheck: int = 1
    shooting: int = 1
    stickhandling: int = 1
    
    # Goalie attributes - initialized only for goalies in __post_init__
    reflexes: int = 1
    positioning: int = 1
    rebound_control: int = 1
    puck_handling: int = 1
    glove_hand: int = 1
    stick_side: int = 1
    breakaway_skill: int = 1
    aggressiveness_goalie: int = 1
    
    # Legacy attributes to maintain backward compatibility
    # These will be mapped to new attributes in __post_init__
    defensive_awareness: int = 1
    offensive_awareness: int = 1
    shot_blocking: int = 1
    
    # Tendencies
    shoot_pass_tendency: int = field(default_factory=lambda: random.randint(0, 100))
    hitting_tendency: int = field(default_factory=lambda: random.randint(0, 100))
    
    def __post_init__(self):
        """Initializes position-specific attributes after basic initialization."""
        # Initialize position-specific attributes
        if self.primary_position == PlayerPosition.GOALIE:
            # Set goalie attributes
            self.reflexes = random.randint(8, 18)
            self.positioning = random.randint(8, 18)
            self.rebound_control = random.randint(8, 18)
            self.puck_handling = random.randint(8, 18)
            self.glove_hand = random.randint(8, 18)
            self.stick_side = random.randint(8, 18)
            self.breakaway_skill = random.randint(8, 18)
            self.aggressiveness_goalie = random.randint(8, 18)
        else:
            # Set skater attributes
            self.checking = random.randint(8, 18)
            self.deflection = random.randint(8, 18)
            self.deking = random.randint(8, 18)
            self.hitting = random.randint(8, 18)
            # Enhanced position-specific attributes
            self.off_the_puck = random.randint(8, 18)
            self.wristshot = random.randint(10, 18)  # Forwards are better at wrist shots
            self.slapshot = random.randint(6, 14)
            self.one_timer = random.randint(8, 16)
            self.backhand = random.randint(6, 14)
            self.screen_shots = random.randint(8, 16)
            self.loose_puck = random.randint(8, 16)
            self.passing = random.randint(8, 18)
            self.pokecheck = random.randint(8, 18)
            self.shooting = random.randint(8, 18)
            self.slapshot = random.randint(8, 18)
            self.stickhandling = random.randint(8, 18)
            self.wristshot = random.randint(8, 18)
            
            # Position-specific adjustments
            if self.primary_position == PlayerPosition.CENTER:
                self.faceoffs = random.randint(10, 18)
            else:
                self.faceoffs = random.randint(5, 15)
                
            # Set legacy attributes to maintain compatibility
            # Map new attributes to existing ones for compatibility
            self.offensive_awareness = self.off_the_puck  # Use off_the_puck as offensive awareness
            self.defensive_awareness = self.checking  # Approximate mapping
            self.shot_blocking = self.deflection  # Approximate mapping

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
        
    def __hash__(self):
        """Make Player objects hashable based on their ID."""
        return hash(self.id)
        
    def __eq__(self, other):
        """Compare Player objects based on their ID."""
        if not isinstance(other, PlayerV2):
            return False
        return self.id == other.id

    def get_role(self) -> PlayerRole:
        """Dynamically determines the player's role based on their attributes."""
        if self.primary_position == PlayerPosition.GOALIE:
            return PlayerRole.GOALIE
        
        if self.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
            if self.off_the_puck > 15 and self.shooting > 13:
                return PlayerRole.OFFENSIVE_DEFENSEMAN
            if self.checking > 15 and self.pokecheck > 13:
                return PlayerRole.DEFENSIVE_DEFENSEMAN
            return PlayerRole.TWO_WAY_DEFENSEMAN
            
        # For forwards
        if self.shooting > 16 and self.wristshot > 15:
            return PlayerRole.SNIPER
        if self.passing > 16 and self.flair > 15:
            return PlayerRole.PLAYMAKER
        if self.strength > 15 and self.hitting > 14 and self.hitting_tendency > 60:
            return PlayerRole.POWER_FORWARD
        if self.strength > 16 and self.checking > 16 and self.aggression > 15:
            return PlayerRole.ENFORCER
        if self.teamwork > 14 and self.checking > 14 and self.defensive_awareness > 12:
            return PlayerRole.GRINDER
        return PlayerRole.TWO_WAY_FORWARD

    def overall_rating(self) -> int:
        """Calculates a weighted overall rating based on position."""
        if self.primary_position == PlayerPosition.GOALIE:
            rating = (
                self.reflexes * 0.15 +
                self.positioning * 0.15 +
                self.rebound_control * 0.15 +
                self.puck_handling * 0.10 +
                self.glove_hand * 0.15 +
                self.stick_side * 0.15 +
                self.breakaway_skill * 0.10 +
                self.composure * 0.05
            )
        elif self.primary_position == PlayerPosition.CENTER:
            rating = (
                self.passing * 0.12 +
                self.shooting * 0.10 +
                self.stickhandling * 0.10 +
                self.deking * 0.08 +
                self.wristshot * 0.08 +
                self.slapshot * 0.08 +
                self.faceoffs * 0.10 +
                self.off_the_puck * 0.10 +
                self.checking * 0.06 +
                self.speed * 0.08 +
                self.stamina * 0.05 +
                self.strength * 0.05
            )
        elif self.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
            rating = (
                self.shooting * 0.12 +
                self.wristshot * 0.10 +
                self.slapshot * 0.08 +
                self.passing * 0.10 +
                self.stickhandling * 0.10 +
                self.deking * 0.08 +
                self.off_the_puck * 0.10 +
                self.speed * 0.10 +
                self.strength * 0.08 +
                self.checking * 0.06 +
                self.hitting * 0.08
            )
        elif self.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
            rating = (
                self.checking * 0.15 +
                self.pokecheck * 0.12 +
                self.passing * 0.10 +
                self.stickhandling * 0.08 +
                self.shooting * 0.06 +
                self.slapshot * 0.08 +
                self.deflection * 0.10 +
                self.strength * 0.12 +
                self.stamina * 0.08 +
                self.balance * 0.06 +
                self.speed * 0.05
            )
        else:
            # Fallback for other positions
            rating = (
                self.shooting * 0.10 +
                self.passing * 0.10 +
                self.stickhandling * 0.10 +
                self.checking * 0.10 +
                self.speed * 0.10 +
                self.strength * 0.10 +
                self.stamina * 0.10 +
                self.composure * 0.10 +
                self.teamwork * 0.10 +
                self.anticipation * 0.10
            )
        
        return round(rating)

    def is_superstar(self) -> bool:
        """Determines if a player is considered a superstar."""
        return self.overall_rating() >= 88

# Helper functions to convert between Player and PlayerV2
def convert_to_v2(player):
    """Convert a legacy Player to PlayerV2."""
    v2_player = PlayerV2(
        first_name=player.first_name,
        last_name=player.last_name,
        age=player.age,
        primary_position=player.primary_position
    )
    
    # Copy over all common properties
    v2_player.id = player.id
    v2_player.jersey_number = player.jersey_number
    v2_player.captaincy = player.captaincy
    v2_player.contract = player.contract
    v2_player.stats = player.stats
    v2_player.team_name = player.team_name
    v2_player.x = player.x
    v2_player.y = player.y
    v2_player.potential_grade = player.potential_grade
    v2_player.morale = getattr(player, 'morale', 10)  # Copy morale or default to 10
    
    # Copy legacy mental attributes to new ones where possible
    v2_player.composure = getattr(player, 'composure', random.randint(8, 18))
    v2_player.anticipation = getattr(player, 'anticipation', random.randint(8, 18))
    v2_player.teamwork = player.teamwork
    v2_player.flair = player.flair
    v2_player.leadership = player.leadership
    v2_player.aggression = getattr(player, 'aggressiveness', random.randint(8, 18))
    v2_player.concentration = getattr(player, 'focus', random.randint(8, 18))
    
    # Copy legacy physical attributes
    v2_player.acceleration = getattr(player, 'acceleration', random.randint(8, 18))
    v2_player.agility = getattr(player, 'agility', random.randint(8, 18))
    v2_player.balance = getattr(player, 'balance', random.randint(8, 18))
    v2_player.off_the_puck = getattr(player, 'off_the_puck', random.randint(8, 18))
    v2_player.wristshot = getattr(player, 'wristshot', random.randint(8, 18))
    v2_player.slapshot = getattr(player, 'slapshot', random.randint(8, 18))
    v2_player.speed = getattr(player, 'speed', random.randint(8, 18))
    v2_player.stamina = getattr(player, 'stamina', random.randint(8, 18))
    v2_player.strength = player.strength
    
    # Handle position-specific attributes
    if player.primary_position == PlayerPosition.GOALIE:
        v2_player.reflexes = getattr(player, 'reflexes', random.randint(8, 18))
        v2_player.positioning = getattr(player, 'positioning', random.randint(8, 18))
        v2_player.rebound_control = getattr(player, 'rebound_control', random.randint(8, 18))
        v2_player.puck_handling = getattr(player, 'puck_handling', random.randint(8, 18))
        v2_player.glove_hand = getattr(player, 'glove_hand', random.randint(8, 18))
        v2_player.stick_side = getattr(player, 'stick_side', random.randint(8, 18))
        v2_player.breakaway_skill = getattr(player, 'breakaway_skill', random.randint(8, 18))
        v2_player.aggressiveness_goalie = getattr(player, 'aggressiveness', random.randint(8, 18))
    else:
        # Skater attributes
        v2_player.checking = player.checking
        v2_player.deflection = getattr(player, 'deflections', random.randint(8, 18))
        v2_player.deking = player.deking
        v2_player.faceoffs = player.faceoffs
        v2_player.hitting = getattr(player, 'strength', random.randint(8, 18))  # Approximate
        v2_player.off_the_puck = player.offensive_awareness
        v2_player.passing = player.passing
        v2_player.pokecheck = getattr(player, 'defensive_awareness', random.randint(8, 18))  # Approximate
        v2_player.shooting = player.shooting
        v2_player.slapshot = getattr(player, 'shooting_power', random.randint(8, 18))  # Approximate
        v2_player.stickhandling = getattr(player, 'stickhandling', random.randint(8, 18))
        v2_player.wristshot = getattr(player, 'shooting_accuracy', random.randint(8, 18))  # Approximate
    
    # Copy tendencies
    v2_player.shoot_pass_tendency = player.shoot_pass_tendency
    v2_player.hitting_tendency = player.hitting_tendency
    
    return v2_player
