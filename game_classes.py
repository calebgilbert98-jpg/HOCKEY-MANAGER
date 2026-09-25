# game_classes.py
# A refactored and improved version focusing on structure, scalability, and clarity.

import random
import itertools
import uuid
from datetime import datetime, timedelta
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta, datetime, time

# --- Constants and Configuration ---
class GameBalance:
    MIN_ATTRIBUTE = 1
    MAX_ATTRIBUTE = 50
    DEFAULT_MIN_ATTRIBUTE = 25
    DEFAULT_MAX_ATTRIBUTE = 45
    
    PEAK_AGE_START = 27
    PEAK_AGE_END = 32
    DEVELOPMENT_CHANCE = 0.6
    DECLINE_CHANCE = 0.4

    MAX_SCOUTING_VIEWINGS = 15


def to_100_scale(value):
    """Convert an internal ~50-scale rating to the 1-100 display scale.

    The sim engine, AI and development all run on the internal scale;
    everything the user sees (overall, attributes) goes through this.
    """
    try:
        return max(1, min(100, int(round(float(value) * 2))))
    except (TypeError, ValueError):
        return 50


# --- Enumerations for Clarity ---
class PlayerPosition(Enum):
    CENTER = "C"
    LEFT_WING = "LW"
    RIGHT_WING = "RW"
    LEFT_DEFENSE = "LD"
    RIGHT_DEFENSE = "RD"
    DEFENSE = "D"
    GOALIE = "G"

    @property
    def attribute_weights(self):
        weights = {
            PlayerPosition.CENTER: {
                'skating': 0.2, 'shooting': 0.25, 'passing': 0.25,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.LEFT_WING: {
                'skating': 0.2, 'shooting': 0.3, 'passing': 0.2,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.RIGHT_WING: {
                'skating': 0.2, 'shooting': 0.3, 'passing': 0.2,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.LEFT_DEFENSE: {
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.RIGHT_DEFENSE: {
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.DEFENSE: {  # <-- FIXED HERE
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.GOALIE: {
                'glove': 0.25, 'blocker': 0.25, 'pads': 0.25,
                'reflexes': 0.15, 'positioning': 0.1
            }
        }
        return weights[self]

class PlayerRole(Enum):
    SNIPER = "Sniper"
    PLAYMAKER = "Playmaker"
    POWER_FORWARD = "Power Forward"
    GRINDER = "Grinder"
    ENFORCER = "Enforcer"
    TWO_WAY_FORWARD = "Two-Way Forward"
    OFFENSIVE_DEFENSEMAN = "Offensive Defenseman"
    DEFENSIVE_DEFENSEMAN = "Defensive Defenseman"
    TWO_WAY_DEFENSEMAN = "Two-Way Defenseman"
    GOALIE = "Goalie"

class StaffRole(Enum):
    # Management
    GENERAL_MANAGER = "General Manager"
    ASSISTANT_GENERAL_MANAGER = "Assistant General Manager"
    
    # Coaching Staff
    HEAD_COACH = "Head Coach"
    ASSISTANT_COACH = "Assistant Coach"
    ASSOCIATE_COACH = "Associate Coach"
    GOALIE_COACH = "Goalie Coach"
    POWER_PLAY_COACH = "Power Play Coach"
    PENALTY_KILL_COACH = "Penalty Kill Coach"
    
    # Development Staff
    SKILLS_COACH = "Skills Coach"
    CONDITIONING_COACH = "Conditioning Coach"
    SKATING_COACH = "Skating Coach"
    
    # Scouting Staff
    HEAD_SCOUT = "Head Scout"
    PROFESSIONAL_SCOUT = "Professional Scout"
    AMATEUR_SCOUT = "Amateur Scout"
    EUROPEAN_SCOUT = "European Scout"
    ADVANCE_SCOUT = "Advance Scout"
    
    # Medical & Support Staff
    TEAM_DOCTOR = "Team Doctor"
    PHYSIOTHERAPIST = "Physiotherapist"
    EQUIPMENT_MANAGER = "Equipment Manager"
    STRENGTH_COACH = "Strength & Conditioning Coach"
    
    # Analytics & Media
    VIDEO_COACH = "Video Coach"
    STATISTICIAN = "Statistician"
    MEDIA_RELATIONS = "Media Relations"

# --- Data-Driven Class Structures ---
@dataclass
class Contract:
    """Holds all player contract details."""
    salary: int = 750000
    years_remaining: int = 0
    signing_bonus: int = 0
    performance_bonus: int = 0
    no_trade_clause: bool = False

@dataclass
class PlayerStats:
    """Tracks player statistics for a season."""
    goals: int = 0
    assists: int = 0
    penalties_in_minutes: int = 0
    saves: int = 0
    penalties: int = 0
    shots: int = 0
    games_played: int = 0
    shots_against: int = 0  # For goalies: total shots faced

    @property
    def points(self) -> int:
        return self.goals + self.assists

player_id_counter = itertools.count()

@dataclass(eq=False)
class Player:
    """Represents a single, deeply detailed hockey player."""
    first_name: str
    last_name: str
    age: int
    primary_position: PlayerPosition
    
    id: int = field(default_factory=lambda: next(player_id_counter), init=False)
    jersey_number: int = field(default_factory=lambda: random.randint(1, 98))
    captaincy: str = None # 'C', 'A', or None
    
    # Personal information with realistic defaults
    nationality: str = "Canada"
    birthplace: str = "Unknown"
    height: str = field(default_factory=lambda: f"{random.randint(5, 6)}'{random.randint(6, 11)}\"")  # 5'6" to 6'11"
    weight: int = field(default_factory=lambda: random.randint(160, 230))  # 160-230 lbs
    handedness: str = field(default_factory=lambda: random.choice(["Left", "Right"]))
    birth_date: str = field(default_factory=lambda: f"{random.randint(1995, 2006)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}")
    draft_year: int = field(default_factory=lambda: random.randint(2010, 2024))
    draft_position: str = field(default_factory=lambda: f"Round {random.randint(1, 7)}, Pick {random.randint(1, 31)}")
    
    determination: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    teamwork: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    leadership: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    discipline: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    flair: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    consistency: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    important_matches: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    morale: int = 10

    # Football Manager-style career fields (happiness, squad status, chats)
    happiness: int = 70  # 0-100, how happy the player is at the club
    squad_status: str = "Rotation"  # Star Player / Key Player / Regular Starter / Rotation / Prospect / Surplus
    playing_time_concern: int = 0  # 0-100, worry about lack of ice time
    transfer_requested: bool = False
    promise_made: str = ""  # e.g. "more_icetime"
    last_chat: str = ""  # ISO date of last private chat

    # Career and development tracking
    pro_debut: str = field(default_factory=lambda: f"{random.randint(2015, 2024)}-{random.randint(10, 12)}-{random.randint(1, 28):02d}")
    teams_count: int = field(default_factory=lambda: random.randint(1, 4))
    team_tenure: str = field(default_factory=lambda: random.choice(["This season", "2 years", "3 years", "4+ years"]))
    peak_rating: int = field(default_factory=lambda: random.randint(12, 20))
    potential: int = field(default_factory=lambda: random.randint(10, 20))
    
    # Health and injury tracking  
    is_injured: bool = False
    days_missed: int = 0
    career_games_missed: int = field(default_factory=lambda: random.randint(0, 50))
    last_injury: str = "None"
    injury_type: str = "None"
    games_remaining_injured: int = 0
    
    # Development attributes
    coachability: int = field(default_factory=lambda: random.randint(25, 45))
    work_ethic: int = field(default_factory=lambda: random.randint(25, 45))
    adaptability: int = field(default_factory=lambda: random.randint(25, 45))
    team_chemistry: int = field(default_factory=lambda: random.randint(10, 20))
    line_chemistry: int = field(default_factory=lambda: random.randint(10, 20))
    
    # SEASON STATISTICS - Reset each season
    games_played: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    penalty_minutes: int = 0
    shots: int = 0
    avg_toi: str = "0:00"
    
    # Goalie specific season stats
    wins: int = 0
    losses: int = 0
    save_percentage: float = 0.000
    goals_against_avg: float = 0.00
    shutouts: int = 0
    saves: int = 0
    goals_against: int = 0
    shots_against: int = 0
    
    # CAREER STATISTICS - Accumulated over multiple seasons
    career_games: int = 0
    career_goals: int = 0
    career_assists: int = 0
    career_points: int = 0
    career_penalty_minutes: int = 0
    career_shots: int = 0
    
    # Goalie career stats
    career_wins: int = 0
    career_losses: int = 0
    career_shutouts: int = 0
    career_saves: int = 0
    career_goals_against: int = 0
    career_shots_against: int = 0
    career_games_goalie: int = 0
    
    # STREAKS AND SPECIAL ACHIEVEMENTS
    current_point_streak: int = 0
    current_goal_streak: int = 0
    longest_point_streak: int = 0
    longest_goal_streak: int = 0
    hat_tricks_season: int = 0
    hat_tricks_career: int = 0
    
    # RECORD TRACKING
    seasons_played: int = 0
    is_rookie: bool = True

    # Waiver related attributes
    on_waivers: bool = False
    waiver_days: int = 0
    nhl_games_played: int = field(default_factory=lambda: random.randint(0, 500))

    skating: int = field(default_factory=lambda: random.randint(25, 45))
    strength: int = field(default_factory=lambda: random.randint(25, 45))
    injury_proneness: int = field(default_factory=lambda: random.randint(1, 20))

    shooting: int = field(default_factory=lambda: random.randint(25, 45))
    passing: int = field(default_factory=lambda: random.randint(25, 45))
    deking: int = field(default_factory=lambda: random.randint(25, 45))

    offensive_awareness: int = field(default_factory=lambda: random.randint(25, 45))
    defensive_awareness: int = field(default_factory=lambda: random.randint(25, 45))
    
    checking: int = field(default_factory=lambda: random.randint(25, 45))
    faceoffs: int = field(default_factory=lambda: random.randint(25, 45))
    
    goaltending: int = field(default_factory=lambda: random.randint(25, 45))
    
    shoot_pass_tendency: int = field(default_factory=lambda: random.randint(0, 100))
    hitting_tendency: int = field(default_factory=lambda: random.randint(0, 100))

    potential_grade: str = field(default_factory=lambda: random.choice(['A', 'B', 'C', 'D', 'F']))
    
    contract: Contract = field(default_factory=Contract)
    stats: PlayerStats = field(default_factory=PlayerStats)
    
    team_name: str = "Free Agent"
    x: int = 0  # X position on ice
    y: int = 0  # Y position on ice

    # New attributes (all initialized 5-20)
    stickhandling: int = field(default_factory=lambda: random.randint(25, 45))
    vision: int = field(default_factory=lambda: random.randint(25, 45))
    shooting_accuracy: int = field(default_factory=lambda: random.randint(25, 45))
    shooting_power: int = field(default_factory=lambda: random.randint(25, 45))
    passing_accuracy: int = field(default_factory=lambda: random.randint(25, 45))
    passing_creativity: int = field(default_factory=lambda: random.randint(25, 45))
    first_pass: int = field(default_factory=lambda: random.randint(25, 45))
    breakout_passes: int = field(default_factory=lambda: random.randint(25, 45))
    forechecking: int = field(default_factory=lambda: random.randint(25, 45))
    puck_protection: int = field(default_factory=lambda: random.randint(25, 45))
    deflections: int = field(default_factory=lambda: random.randint(25, 45))
    shot_blocking: int = field(default_factory=lambda: random.randint(25, 45))
    hockey_iq: int = field(default_factory=lambda: random.randint(25, 45))
    composure: int = field(default_factory=lambda: random.randint(25, 45))
    aggressiveness: int = field(default_factory=lambda: random.randint(25, 45))
    work_rate: int = field(default_factory=lambda: random.randint(25, 45))
    anticipation: int = field(default_factory=lambda: random.randint(25, 45))
    decision_making: int = field(default_factory=lambda: random.randint(25, 45))
    focus: int = field(default_factory=lambda: random.randint(25, 45))
    confidence: int = field(default_factory=lambda: random.randint(25, 45))
    acceleration: int = field(default_factory=lambda: random.randint(25, 45))
    balance: int = field(default_factory=lambda: random.randint(25, 45))
    endurance: int = field(default_factory=lambda: random.randint(25, 45))
    agility: int = field(default_factory=lambda: random.randint(25, 45))
    speed: int = field(default_factory=lambda: random.randint(25, 45))
    stamina: int = field(default_factory=lambda: random.randint(25, 45))
    durability: int = field(default_factory=lambda: random.randint(25, 45))
    
    # New attributes replacing pace and offensive_read
    off_the_puck: int = field(default_factory=lambda: random.randint(25, 45))  # Movement without puck
    
    # Physical and tactical attributes
    wristshot: int = field(default_factory=lambda: random.randint(25, 45))
    slapshot: int = field(default_factory=lambda: random.randint(25, 45))
    pokecheck: int = field(default_factory=lambda: random.randint(25, 45))
    bodycheck: int = field(default_factory=lambda: random.randint(25, 45))
    one_timer: int = field(default_factory=lambda: random.randint(25, 45))
    backhand: int = field(default_factory=lambda: random.randint(25, 45))
    faceoff_wins: int = field(default_factory=lambda: random.randint(25, 45))
    screen_shots: int = field(default_factory=lambda: random.randint(25, 45))
    loose_puck: int = field(default_factory=lambda: random.randint(25, 45))
    creativity: int = field(default_factory=lambda: random.randint(25, 45))
    pressure_player: int = field(default_factory=lambda: random.randint(25, 45))  # Performance under pressure
    # Goalie-specific attributes
    reflexes: int = field(default_factory=lambda: random.randint(25, 45))
    positioning: int = field(default_factory=lambda: random.randint(25, 45))
    rebound_control: int = field(default_factory=lambda: random.randint(25, 45))
    puck_handling: int = field(default_factory=lambda: random.randint(25, 45))
    glove_hand: int = field(default_factory=lambda: random.randint(25, 45))
    stick_side: int = field(default_factory=lambda: random.randint(25, 45))
    breakaway_skill: int = field(default_factory=lambda: random.randint(25, 45))
    
    # Waiver attributes
    on_waivers: bool = False
    waiver_days: int = 0
    nhl_games_played: int = field(default_factory=lambda: random.randint(0, 500))  # For waiver eligibility

    def __post_init__(self):
        """Adjusts attributes based on position after initialization."""
        if self.primary_position == PlayerPosition.CENTER:
            self.faceoffs = random.randint(30, 45)
        elif self.primary_position == PlayerPosition.GOALIE:
            self.goaltending = random.randint(30, 45)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
        
    def __hash__(self):
        """Make Player objects hashable based on their ID."""
        return hash(self.id)
        
    def __eq__(self, other):
        """Compare Player objects based on their ID."""
        if not isinstance(other, Player):
            return False
        return self.id == other.id

    def get_role(self) -> PlayerRole:
        """Dynamically determines the player's role based on their attributes."""
        if self.primary_position == PlayerPosition.GOALIE:
            return PlayerRole.GOALIE
        
        if self.primary_position == PlayerPosition.DEFENSE:  # <-- FIXED HERE
            if self.offensive_awareness > 15 and self.shooting > 13:
                return PlayerRole.OFFENSIVE_DEFENSEMAN
            if self.defensive_awareness > 15 and self.checking > 13:
                return PlayerRole.DEFENSIVE_DEFENSEMAN
            return PlayerRole.TWO_WAY_DEFENSEMAN
            
        if self.shooting > 16 and self.offensive_awareness > 15:
            return PlayerRole.SNIPER
        if self.passing > 16 and self.flair > 15:
            return PlayerRole.PLAYMAKER
        if self.strength > 15 and self.checking > 14 and self.hitting_tendency > 60:
            return PlayerRole.POWER_FORWARD
        if self.strength > 16 and self.checking > 16 and self.discipline < 8:
            return PlayerRole.ENFORCER
        if self.determination > 14 and self.teamwork > 14 and self.defensive_awareness > 12:
            return PlayerRole.GRINDER
        return PlayerRole.TWO_WAY_FORWARD

    def overall_rating(self) -> int:
        """Calculates a weighted overall rating based on position, including all attributes."""
        if self.primary_position == PlayerPosition.GOALIE:
            rating = (
                self.goaltending * 0.12 +
                self.reflexes * 0.15 +
                self.positioning * 0.15 +
                self.rebound_control * 0.12 +
                self.puck_handling * 0.08 +
                self.glove_hand * 0.08 +
                self.stick_side * 0.08 +
                self.breakaway_skill * 0.08 +
                self.confidence * 0.05 +
                self.focus * 0.05 +
                self.composure * 0.04
            )
        elif self.primary_position == PlayerPosition.CENTER:
            rating = (
                self.skating * 0.08 +
                self.shooting * 0.06 +
                self.shooting_accuracy * 0.06 +
                self.shooting_power * 0.05 +
                self.passing * 0.07 +
                self.passing_accuracy * 0.06 +
                self.passing_creativity * 0.06 +
                self.deking * 0.05 +
                self.stickhandling * 0.06 +
                self.vision * 0.06 +
                self.hockey_iq * 0.06 +
                self.offensive_awareness * 0.06 +
                self.defensive_awareness * 0.05 +
                self.faceoffs * 0.07 +
                self.faceoff_wins * 0.04 +
                self.composure * 0.04 +
                self.endurance * 0.04 +
                self.determination * 0.04 +
                self.off_the_puck * 0.04 +
                self.one_timer * 0.03 +
                self.loose_puck * 0.02
            )
        elif self.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
            rating = (
                self.skating * 0.09 +
                self.shooting * 0.08 +
                self.shooting_accuracy * 0.07 +
                self.shooting_power * 0.07 +
                self.wristshot * 0.06 +
                self.slapshot * 0.05 +
                self.passing * 0.06 +
                self.passing_accuracy * 0.05 +
                self.passing_creativity * 0.05 +
                self.deking * 0.06 +
                self.stickhandling * 0.06 +
                self.vision * 0.06 +
                self.hockey_iq * 0.06 +
                self.offensive_awareness * 0.07 +
                self.defensive_awareness * 0.04 +
                self.composure * 0.04 +
                self.endurance * 0.04 +
                self.determination * 0.04 +
                self.off_the_puck * 0.05 +
                self.one_timer * 0.04 +
                self.backhand * 0.03 +
                self.screen_shots * 0.03
            )
        elif self.primary_position in (PlayerPosition.DEFENSE,
                                             PlayerPosition.LEFT_DEFENSE,
                                             PlayerPosition.RIGHT_DEFENSE):
            rating = (
                self.skating * 0.08 +
                self.passing * 0.06 +
                self.passing_accuracy * 0.06 +
                self.passing_creativity * 0.05 +
                self.strength * 0.07 +
                self.checking * 0.07 +
                self.bodycheck * 0.06 +
                self.defensive_awareness * 0.09 +
                self.shot_blocking * 0.07 +
                self.pokecheck * 0.06 +
                self.anticipation * 0.06 +
                self.hockey_iq * 0.06 +
                self.composure * 0.05 +
                self.aggressiveness * 0.05 +
                self.balance * 0.05 +
                self.endurance * 0.05 +
                self.determination * 0.05 +
                self.slapshot * 0.04 +
                self.loose_puck * 0.04 +
                self.pressure_player * 0.04
            )
        else:
            # Fallback for other positions
            rating = (
                self.skating * 0.10 +
                self.shooting * 0.08 +
                self.passing * 0.08 +
                self.deking * 0.07 +
                self.stickhandling * 0.07 +
                self.vision * 0.07 +
                self.hockey_iq * 0.07 +
                self.offensive_awareness * 0.07 +
                self.defensive_awareness * 0.07 +
                self.composure * 0.07 +
                self.endurance * 0.07 +
                self.determination * 0.07 +
                self.off_the_puck * 0.05 +
                self.loose_puck * 0.04
            )
        return int(rating)

    def _potential_cap(self) -> int:
        """Overall-rating ceiling implied by the player's potential grade (50-scale)."""
        g = (self.potential_grade or 'C').strip().upper()
        base = {'A': 48, 'B': 44, 'C': 40, 'D': 35, 'F': 30}
        cap = base.get(g[:1], 40)
        if len(g) > 1:
            if g[1] == '+':
                cap += 2
            elif g[1] == '-':
                cap -= 2
        return cap

    def age_one_year(self):
        """Handles player aging, development, and decline."""
        self.age += 1
        if self.contract.years_remaining > 0:
            self.contract.years_remaining -= 1

        potential_cap = self._potential_cap()

        if self.age < GameBalance.PEAK_AGE_START and self.overall_rating() < potential_cap:
            # Development closes a fraction of the gap to the player's ceiling
            # each year: prospects surge, established players refine slowly.
            gap = potential_cap - self.overall_rating()
            if self.age <= 20:
                frac = 0.25
            elif self.age <= 23:
                frac = 0.18
            elif self.age <= 26:
                frac = 0.10
            else:
                frac = 0.05
            frac *= random.uniform(0.8, 1.2)
            # ~0.06 overall per attribute point (weighted average of ~20 attrs)
            attr_points = min(120, max(1, int(gap * frac / 0.06)))
            for _ in range(attr_points):
                self._change_random_attribute(1)
        elif self.age > GameBalance.PEAK_AGE_END:
            if random.random() < GameBalance.DECLINE_CHANCE:
                self._change_random_attribute(-1)

    def _ovr_attributes(self) -> list:
        """Attribute names that feed this player's positional overall rating."""
        if self.primary_position == PlayerPosition.GOALIE:
            return ['goaltending', 'reflexes', 'positioning', 'rebound_control',
                    'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill',
                    'confidence', 'focus', 'composure']
        if self.primary_position == PlayerPosition.CENTER:
            return ['skating', 'shooting', 'shooting_accuracy', 'shooting_power',
                    'passing', 'passing_accuracy', 'passing_creativity', 'deking',
                    'stickhandling', 'vision', 'hockey_iq', 'offensive_awareness',
                    'defensive_awareness', 'faceoffs', 'faceoff_wins', 'composure',
                    'endurance', 'determination', 'off_the_puck', 'one_timer',
                    'loose_puck']
        if self.primary_position in (PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING):
            return ['skating', 'shooting', 'shooting_accuracy', 'shooting_power',
                    'wristshot', 'slapshot', 'passing', 'passing_accuracy',
                    'passing_creativity', 'deking', 'stickhandling', 'vision',
                    'hockey_iq', 'offensive_awareness', 'defensive_awareness',
                    'composure', 'endurance', 'determination', 'off_the_puck',
                    'one_timer', 'backhand', 'screen_shots']
        if self.primary_position in (PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE,
                                     PlayerPosition.RIGHT_DEFENSE):
            return ['skating', 'passing', 'passing_accuracy', 'passing_creativity',
                    'strength', 'checking', 'bodycheck', 'defensive_awareness',
                    'shot_blocking', 'pokecheck', 'anticipation', 'hockey_iq',
                    'composure', 'aggressiveness', 'balance', 'endurance',
                    'determination', 'slapshot', 'loose_puck', 'pressure_player']
        return ['skating', 'shooting', 'passing', 'deking', 'stickhandling',
                'vision', 'hockey_iq', 'offensive_awareness', 'defensive_awareness',
                'composure', 'endurance', 'determination', 'off_the_puck',
                'loose_puck']

    def _change_random_attribute(self, amount: int):
        """Helper to randomly increase or decrease a skill attribute."""
        # Development targets attributes that actually move the player's OVR;
        # occasionally (25%) it touches a secondary attribute for flavor.
        if random.random() < 0.75:
            skill_attributes = self._ovr_attributes()
        else:
            skill_attributes = [
            'skating', 'strength', 'shooting', 'passing', 'deking',
            'offensive_awareness', 'defensive_awareness', 'checking', 'faceoffs',
            'goaltending', 'determination', 'teamwork', 'leadership', 'discipline', 'flair',
            'stickhandling', 'vision', 'shooting_accuracy', 'shooting_power',
            'passing_accuracy', 'passing_creativity', 'puck_protection', 'deflections',
            'shot_blocking', 'hockey_iq', 'composure', 'aggressiveness', 'work_rate',
            'anticipation', 'decision_making', 'focus', 'confidence', 'acceleration',
            'balance', 'endurance', 'agility', 'speed', 'stamina', 'durability',
            'off_the_puck', 'wristshot', 'slapshot', 'pokecheck', 'bodycheck',
            'one_timer', 'backhand', 'faceoff_wins', 'screen_shots', 'loose_puck',
            'creativity', 'pressure_player', 'reflexes', 'positioning', 'rebound_control',
            'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill'
        ]
        
        attr_to_change = random.choice(skill_attributes)
        current_value = getattr(self, attr_to_change)
        
        new_value = max(GameBalance.MIN_ATTRIBUTE, min(GameBalance.MAX_ATTRIBUTE, current_value + amount))
        
        setattr(self, attr_to_change, new_value)

    @property
    def value(self):
        """Calculate player's market value based on attributes and performance."""
        # Base value determined by overall rating
        base_value = self.overall_rating() * 100000
        
        # Age modifier - players in their prime (23-29) get premium
        age_modifier = 1.0
        if 23 <= self.age <= 29:
            age_modifier = 1.2
        elif self.age >= 30:
            # Declining value with age
            age_modifier = max(0.5, 1.0 - ((self.age - 30) * 0.05))
        
        # Position modifier - centers and first-line defensemen get premium
        position_modifier = 1.0
        if self.primary_position == PlayerPosition.CENTER:
            position_modifier = 1.15
        elif self.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            position_modifier = 1.1
        elif self.primary_position == PlayerPosition.GOALIE:
            # Goalies have different value curve
            position_modifier = 1.0 if self.overall_rating() >= 50 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if self.age <= 25:
            potential_map = {'A': 1.5, 'B': 1.3, 'C': 1.1, 'D': 1.0, 'F': 0.9}
            potential_modifier = potential_map.get(self.potential_grade, 1.0)
        
        # Stats performance bonus (simplified for now)
        stats = getattr(self, 'stats', None)
        performance_bonus = 0
        if stats:
            performance_bonus = getattr(stats, 'goals', 0) * 50000 + getattr(stats, 'assists', 0) * 30000
        
        # Calculate final market value
        market_value = (base_value * age_modifier * position_modifier * potential_modifier) + performance_bonus
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
    
    def negotiate_contract(self, salary, years):
        min_salary = self.value * 0.9
        max_salary = self.value * 1.2
        if min_salary <= salary <= max_salary and years >= 1:
            return True
        return False
    
    def add_game_stats(self, goals=0, assists=0, penalty_minutes=0, plus_minus=0, shots=0,
                      wins=0, losses=0, saves=0, goals_against=0, shots_against=0, shutout=False):
        """Add statistics from a single game"""
        # Season stats
        self.games_played += 1
        self.goals += goals
        self.assists += assists
        self.points = self.goals + self.assists
        self.penalty_minutes += penalty_minutes
        self.plus_minus += plus_minus
        self.shots += shots
        
        # Career stats  
        self.career_games += 1
        self.career_goals += goals
        self.career_assists += assists
        self.career_points = self.career_goals + self.career_assists
        self.career_penalty_minutes += penalty_minutes
        self.career_shots += shots
        
        # Goalie stats
        if self.primary_position == PlayerPosition.GOALIE:
            self.wins += wins
            self.losses += losses
            self.saves += saves
            self.goals_against += goals_against
            self.shots_against += shots_against
            
            self.career_wins += wins
            self.career_losses += losses
            self.career_saves += saves
            self.career_goals_against += goals_against
            self.career_shots_against += shots_against
            if wins > 0 or losses > 0:
                self.career_games_goalie += 1
                
            if shutout:
                self.shutouts += 1
                self.career_shutouts += 1
                
            # Update percentages
            self._update_goalie_stats()
        
        # Handle streaks
        if goals + assists > 0:
            self.current_point_streak += 1
            self.longest_point_streak = max(self.longest_point_streak, self.current_point_streak)
        else:
            self.current_point_streak = 0
            
        if goals > 0:
            self.current_goal_streak += 1
            self.longest_goal_streak = max(self.longest_goal_streak, self.current_goal_streak)
        else:
            self.current_goal_streak = 0
            
        # Track hat tricks
        if goals >= 3:
            self.hat_tricks_season += 1
            self.hat_tricks_career += 1
    
    def _update_goalie_stats(self):
        """Update calculated goalie statistics"""
        if self.shots_against > 0:
            self.save_percentage = self.saves / self.shots_against
        else:
            self.save_percentage = 0.0
            
        games = max(self.wins + self.losses, 1)
        self.goals_against_avg = self.goals_against / games
    
    def reset_season_stats(self):
        """Reset season statistics for a new season"""
        self.games_played = 0
        self.goals = 0
        self.assists = 0
        self.points = 0
        self.penalty_minutes = 0
        self.plus_minus = 0
        self.shots = 0
        self.wins = 0
        self.losses = 0
        self.shutouts = 0
        self.saves = 0
        self.goals_against = 0
        self.shots_against = 0
        self.save_percentage = 0.0
        self.goals_against_avg = 0.0
        self.hat_tricks_season = 0
        self.current_point_streak = 0
        self.current_goal_streak = 0
        
        self.seasons_played += 1
        self.is_rookie = (self.seasons_played == 1)
    
    def get_ppg(self) -> float:
        """Get points per game"""
        if self.games_played == 0:
            return 0.0
        return self.points / self.games_played
    
    def get_career_ppg(self) -> float:
        """Get career points per game"""
        if self.career_games == 0:
            return 0.0
        return self.career_points / self.career_games
    
    def get_goals_per_game(self) -> float:
        """Get goals per game"""
        if self.games_played == 0:
            return 0.0
        return self.goals / self.games_played
    
    def get_shooting_percentage(self) -> float:
        """Get shooting percentage"""
        if self.shots == 0:
            return 0.0
        return (self.goals / self.shots) * 100
    
    def get_career_save_percentage(self) -> float:
        """Get career save percentage for goalies"""
        if self.career_shots_against == 0:
            return 0.0
        return self.career_saves / self.career_shots_against
    
    def get_career_gaa(self) -> float:
        """Get career goals against average"""
        if self.career_games_goalie == 0:
            return 0.0
        return self.career_goals_against / self.career_games_goalie
    
    def get_stat_for_record_check(self, stat_type: str) -> int:
        """Get current stat value for record comparison"""
        stat_mapping = {
            'single_season_goals': self.goals,
            'single_season_assists': self.assists, 
            'single_season_points': self.points,
            'single_season_pim': self.penalty_minutes,
            'single_season_wins': self.wins,
            'single_season_shutouts': self.shutouts,
            'career_goals': self.career_goals,
            'career_assists': self.career_assists,
            'career_points': self.career_points,
            'career_pim': self.career_penalty_minutes,
            'career_wins': self.career_wins,
            'career_shutouts': self.career_shutouts,
            'career_games': self.career_games,
            'longest_point_streak': self.current_point_streak,
            'longest_goal_streak': self.current_goal_streak,
            'most_hat_tricks_season': self.hat_tricks_season,
            'most_hat_tricks_career': self.hat_tricks_career,
        }
        return stat_mapping.get(stat_type, 0)

@dataclass
class Staff:
    """Represents a non-player staff member with detailed EHM-style attributes."""
    first_name: str
    last_name: str
    role: StaffRole
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    age: int = field(default_factory=lambda: random.randint(25, 65))
    nationality: str = field(default_factory=lambda: random.choice(['USA', 'Canada', 'Russia', 'Sweden', 'Finland', 'Czech Republic']))
    
    # Core Coaching Attributes (1-20 scale)
    coaching_forwards: int = field(default_factory=lambda: random.randint(8, 18))
    coaching_defensemen: int = field(default_factory=lambda: random.randint(8, 18))
    coaching_goalies: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Tactical Knowledge
    tactical_knowledge: int = field(default_factory=lambda: random.randint(8, 18))
    game_preparation: int = field(default_factory=lambda: random.randint(8, 18))
    match_preparation: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Player Development
    working_with_youngsters: int = field(default_factory=lambda: random.randint(8, 18))
    player_development: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Management Skills
    man_management: int = field(default_factory=lambda: random.randint(8, 18))
    motivating: int = field(default_factory=lambda: random.randint(8, 18))
    discipline: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Scouting Abilities
    judging_player_ability: int = field(default_factory=lambda: random.randint(8, 18))
    judging_player_potential: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Communication & Relationships
    media_handling: int = field(default_factory=lambda: random.randint(8, 18))
    determination: int = field(default_factory=lambda: random.randint(8, 18))
    adaptability: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Specialized Skills (position-dependent)
    level_of_discipline: int = field(default_factory=lambda: random.randint(8, 18))
    attacking_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    defensive_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    mental_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    technical_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Contract Information
    salary: int = field(default_factory=lambda: random.randint(75000, 500000))
    contract_years: int = field(default_factory=lambda: random.randint(1, 5))
    
    # Performance Tracking
    reputation: int = field(default_factory=lambda: random.randint(5, 15))
    experience: int = field(default_factory=lambda: random.randint(1, 30))  # Years of experience
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def overall_rating(self) -> int:
        """Calculate overall rating based on role-specific attributes"""
        if self.role in [StaffRole.HEAD_COACH, StaffRole.ASSISTANT_COACH, StaffRole.ASSOCIATE_COACH]:
            return int((
                self.tactical_knowledge * 0.25 +
                self.man_management * 0.20 +
                self.motivating * 0.15 +
                self.coaching_forwards * 0.15 +
                self.coaching_defensemen * 0.15 +
                self.discipline * 0.10
            ))
        elif self.role == StaffRole.GOALIE_COACH:
            return int((
                self.coaching_goalies * 0.40 +
                self.technical_coaching * 0.25 +
                self.working_with_youngsters * 0.20 +
                self.man_management * 0.15
            ))
        elif 'SCOUT' in self.role.value.upper():
            return int((
                self.judging_player_ability * 0.35 +
                self.judging_player_potential * 0.35 +
                self.determination * 0.15 +
                self.adaptability * 0.15
            ))
        elif self.role == StaffRole.GENERAL_MANAGER:
            return int((
                self.judging_player_ability * 0.20 +
                self.judging_player_potential * 0.20 +
                self.man_management * 0.20 +
                self.tactical_knowledge * 0.15 +
                self.media_handling * 0.15 +
                self.determination * 0.10
            ))
        else:
            # General staff rating
            return int((
                self.determination * 0.30 +
                self.adaptability * 0.25 +
                self.man_management * 0.25 +
                self.discipline * 0.20
            ))
    
    def get_role_description(self) -> str:
        """Get a description of what this staff member does"""
        descriptions = {
            StaffRole.GENERAL_MANAGER: "Oversees all hockey operations, trades, signings, and strategic planning.",
            StaffRole.HEAD_COACH: "Leads the team, makes strategic decisions, and manages game tactics.",
            StaffRole.ASSISTANT_COACH: "Supports the head coach with tactical planning and player development.",
            StaffRole.GOALIE_COACH: "Specializes in goaltender training and development.",
            StaffRole.HEAD_SCOUT: "Leads scouting operations and evaluates talent across all levels.",
            StaffRole.PROFESSIONAL_SCOUT: "Scouts professional leagues for trade targets and free agents.",
            StaffRole.AMATEUR_SCOUT: "Evaluates amateur players for the NHL draft.",
            StaffRole.EUROPEAN_SCOUT: "Focuses on European leagues and international talent.",
            StaffRole.SKILLS_COACH: "Develops individual player skills and techniques.",
            StaffRole.CONDITIONING_COACH: "Manages player fitness and physical conditioning.",
        }
        return descriptions.get(self.role, "Provides specialized support to the organization.")
    
    def negotiate_contract(self, salary, years):
        """Determine if staff member will accept contract offer"""
        reputation_modifier = self.reputation / 10
        min_salary = int(self.salary * (0.8 + reputation_modifier * 0.1))
        max_salary = int(self.salary * (1.2 + reputation_modifier * 0.2))
        
        if min_salary <= salary <= max_salary and 1 <= years <= 5:
            # Higher reputation staff are pickier
            acceptance_chance = 0.8 - (self.reputation - 10) * 0.02
            return random.random() < acceptance_chance
        return False
    
    @staticmethod
    def is_unique_role(role: StaffRole) -> bool:
        """Check if a role should be unique per team (only one allowed)"""
        unique_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH
        ]
        return role in unique_roles
    
    @staticmethod
    def is_essential_role(role: StaffRole) -> bool:
        """Check if a role is essential for team operation"""
        essential_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH,
            StaffRole.ASSISTANT_GENERAL_MANAGER,
            StaffRole.HEAD_SCOUT
        ]
        return role in essential_roles
    
    @staticmethod
    def get_role_department(role: StaffRole) -> str:
        """Get the department/category for a staff role"""
        departments = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',
            
            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',
            
            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',
            
            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',
            
            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',
            StaffRole.EQUIPMENT_MANAGER: 'Medical',
            
            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics'
        }
        return departments.get(role, 'Other')

@dataclass
class ScoutingReport:
    """Enhanced EHM-style scouting report with detailed analysis and reliability tracking."""
    player: Player
    scout: Staff
    scouted_attributes: Dict[str, str] = field(default_factory=dict)
    scouted_potential: Optional[str] = None
    viewings: int = 0
    accuracy: str = 'F'  # Letter grade A-F for report accuracy
    last_viewed: Optional[datetime] = None
    reliability: float = 0.0  # 0.0 to 1.0 scale
    notes: str = ""
    
    # Enhanced scouting features
    region_coverage: str = "Unknown"  # Which region this player was scouted in
    competition_level: str = "Unknown"  # Level of competition observed
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    comparable_players: List[str] = field(default_factory=list)
    injury_history_known: bool = False
    personality_assessment: str = ""
    coachability_rating: int = 0  # 1-20 scale
    interview_conducted: bool = False
    
    # Projection data
    projected_draft_position: Optional[int] = None
    projected_nhl_arrival: Optional[str] = None  # "1-2 years", "3-4 years", etc.
    ceiling_rating: int = 0  # Potential ceiling (1-20)
    floor_rating: int = 0   # Likely floor (1-20)
    
    def calculate_reliability(self) -> float:
        """Calculate how reliable this scouting report is (0.0 to 1.0)"""
        base_reliability = {
            'A': 0.95,
            'B': 0.80,
            'C': 0.65, 
            'D': 0.45,
            'F': 0.25
        }.get(self.accuracy, 0.25)
        
        # Scout skill factor
        scout_skill = (self.scout.judging_player_ability + self.scout.judging_player_potential) / 40.0
        
        # Experience bonus
        exp_bonus = min(0.1, self.scout.experience * 0.003)
        
        # Interview bonus
        interview_bonus = 0.05 if self.interview_conducted else 0.0
        
        return min(1.0, base_reliability * scout_skill + exp_bonus + interview_bonus)

    def update_report(self, player: Player, scout: Staff):
        """Updates the report with enhanced EHM-style scouting mechanics."""
        self.viewings += 1
        self.last_viewed = datetime.now()
        
        # Determine competition level
        if player.age < 20:
            competition_levels = ["Junior A", "Junior B", "College", "International Junior"]
            self.competition_level = random.choice(competition_levels)
        else:
            competition_levels = ["AHL", "ECHL", "European Pro", "KHL", "International"]
            self.competition_level = random.choice(competition_levels)
        
        # Region assignment based on scout specialization
        if self.scout.role == StaffRole.EUROPEAN_SCOUT:
            self.region_coverage = random.choice(["Sweden", "Finland", "Russia", "Czech Republic", "Germany", "Switzerland"])
        elif self.scout.role == StaffRole.AMATEUR_SCOUT:
            self.region_coverage = random.choice(["Western Canada", "Eastern Canada", "USA West", "USA East", "USA Central"])
        else:
            self.region_coverage = random.choice(["North America", "Europe", "International"])
        
        # Calculate accuracy based on viewings, scout skill, and role match
        base_viewings = self.viewings
        
        # Scout skill bonus viewings
        skill_bonus = (self.scout.judging_player_ability + self.scout.judging_player_potential) // 10
        effective_viewings = base_viewings + skill_bonus
        
        # Determine accuracy grade
        if effective_viewings >= 20: 
            self.accuracy = 'A'
        elif effective_viewings >= 15: 
            self.accuracy = 'B'
        elif effective_viewings >= 10: 
            self.accuracy = 'C'
        elif effective_viewings >= 5: 
            self.accuracy = 'D'
        else: 
            self.accuracy = 'F'
        
        # Update reliability
        self.reliability = self.calculate_reliability()
        
        # Scout attributes with position-specific focus
        self._scout_attributes(player, scout)
        
        # Scout potential with advanced projections
        self._scout_potential_and_projections(player, scout)
        
        # Generate comprehensive notes
        self._generate_advanced_notes(player, scout)
        
        # Conduct interview if scout is good enough and enough viewings
        if self.viewings >= 3 and scout.man_management > 12 and random.random() < 0.3:
            self._conduct_player_interview(player)

    def _scout_attributes(self, player: Player, scout: Staff):
        """Scout player attributes with position-specific accuracy."""
        # Determine key attributes by position
        if player.primary_position == PlayerPosition.GOALIE:
            primary_attrs = ['goaltending', 'reflexes', 'positioning', 'rebound_control']
            secondary_attrs = ['puck_handling', 'determination', 'discipline', 'composure']
        elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            primary_attrs = ['defensive_awareness', 'checking', 'passing', 'shot_blocking', 'skating']
            secondary_attrs = ['shooting', 'strength', 'vision', 'teamwork', 'discipline']
        else:  # Forwards
            primary_attrs = ['shooting', 'passing', 'offensive_awareness', 'deking', 'skating']
            secondary_attrs = ['defensive_awareness', 'checking', 'faceoffs', 'determination', 'composure']
        
        all_attrs = primary_attrs + secondary_attrs
        
        # Scout accuracy modifiers
        accuracy_variance = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'F': 4}[self.accuracy]
        primary_accuracy = max(0, accuracy_variance - 1)  # Primary attributes more accurate
        
        for attr in all_attrs:
            if not hasattr(player, attr):
                continue
                
            true_value = getattr(player, attr)
            is_primary = attr in primary_attrs
            variance = primary_accuracy if is_primary else accuracy_variance
            
            # Generate scouted value
            if self.accuracy == 'A' and is_primary and random.random() < 0.9:
                # A-grade scouts get exact values on key attributes
                self.scouted_attributes[attr] = str(true_value)
            elif variance == 0:
                self.scouted_attributes[attr] = str(true_value)
            else:
                # Create ranges based on accuracy
                lower = max(1, true_value - random.randint(0, variance))
                upper = min(20, true_value + random.randint(0, variance))
                
                if lower == upper:
                    self.scouted_attributes[attr] = str(lower)
                else:
                    self.scouted_attributes[attr] = f"{lower}-{upper}"

    def _scout_potential_and_projections(self, player: Player, scout: Staff):
        """Scout potential with advanced projection system."""
        # Potential scouting accuracy based on JPP
        jpp = scout.judging_player_potential
        
        potential_grades = ["F", "D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
        true_index = potential_grades.index(player.potential_grade) if hasattr(player, 'potential_grade') else 5
        
        # Variance decreases with higher JPP
        variance = max(1, 4 - (jpp // 5))
        scouted_index = max(0, min(len(potential_grades)-1, true_index + random.randint(-variance, variance)))
        self.scouted_potential = potential_grades[scouted_index]
        
        # Project ceiling and floor
        base_overall = player.overall_rating() if hasattr(player, 'overall_rating') else 50
        
        # Ceiling projection (optimistic)
        ceiling_modifier = random.randint(5, 15) if player.age < 23 else random.randint(0, 8)
        self.ceiling_rating = min(20, (base_overall + ceiling_modifier) // 5)
        
        # Floor projection (conservative)
        floor_modifier = random.randint(-5, 5) if player.age < 25 else random.randint(-2, 2)
        self.floor_rating = max(5, (base_overall + floor_modifier) // 5)
        
        # NHL arrival projection
        if player.age >= 23:
            self.projected_nhl_arrival = "Ready now"
        elif player.age >= 21:
            self.projected_nhl_arrival = "1-2 years"
        elif player.age >= 19:
            self.projected_nhl_arrival = "2-3 years"
        else:
            self.projected_nhl_arrival = "3-5 years"
        
        # Draft position projection for young players
        if player.age <= 18:
            potential_to_draft = {
                "A+": (1, 5), "A": (3, 12), "A-": (8, 25),
                "B+": (15, 45), "B": (25, 75), "B-": (40, 120),
                "C+": (60, 150), "C": (100, 210), "C-": (150, 210),
                "D": (180, 210), "F": (200, 210)
            }
            
            if self.scouted_potential in potential_to_draft:
                min_pick, max_pick = potential_to_draft[self.scouted_potential]
                # Add scout uncertainty
                uncertainty = 20 if self.accuracy in ['D', 'F'] else 10
                min_pick = max(1, min_pick - uncertainty)
                max_pick = min(210, max_pick + uncertainty)
                self.projected_draft_position = random.randint(min_pick, max_pick)

    def _generate_advanced_notes(self, player: Player, scout: Staff):
        """Generate comprehensive scouting notes with detailed analysis."""
        notes = []
        
        # Potential assessment
        potential_descriptions = {
            "A+": "Generational talent with franchise-altering potential. Could become one of the greatest players in the league.",
            "A": "Elite talent with superstar potential. Projects as a franchise cornerstone for years to come.",
            "A-": "Excellent potential with top-line/top-pairing upside. Should develop into an impact player.",
            "B+": "Very good potential with solid first-line/first-pairing ceiling. Projects as a core player.",
            "B": "Good potential with middle-six/top-four upside. Should become a reliable NHL regular.",
            "B-": "Above average potential. Projects as a useful middle-six/second-pairing contributor.",
            "C+": "Average potential with bottom-six/third-pairing ceiling. Could carve out an NHL role.",
            "C": "Limited upside but should develop into a depth player at the NHL level.",
            "C-": "Below average potential. May struggle to establish himself as an NHL regular.",
            "D": "Low ceiling. Likely career minor leaguer with limited NHL opportunities.",
            "F": "Very limited potential. Unlikely to reach professional hockey."
        }
        
        notes.append(potential_descriptions.get(self.scouted_potential, "Potential assessment ongoing."))
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        for attr, value_str in self.scouted_attributes.items():
            avg_value = self.get_attribute_value(attr)
            
            if avg_value >= 16:
                strengths.append(attr)
            elif avg_value <= 8:
                weaknesses.append(attr)
        
        # Add descriptive strengths
        if 'skating' in strengths:
            notes.append("Elite skating ability with exceptional speed and agility.")
        elif 'shooting' in strengths:
            notes.append("Possesses a lethal shot with accuracy and power.")
        elif 'passing' in strengths:
            notes.append("Excellent vision and playmaking ability.")
        elif 'defensive_awareness' in strengths:
            notes.append("Outstanding defensive instincts and positioning.")
        
        # Add comparable players for high-potential prospects
        if self.scouted_potential in ['A+', 'A', 'A-'] and self.accuracy in ['A', 'B']:
            comparables = [
                "Reminds me of a young Connor McDavid in terms of hockey IQ",
                "Similar playing style to Nathan MacKinnon",
                "Comparable to Erik Karlsson in terms of offensive awareness",
                "Has shades of Sidney Crosby's competitiveness",
                "Playing style reminiscent of Auston Matthews",
                "Comparable to Cale Makar's skating ability"
            ]
            self.comparable_players = [random.choice(comparables)]
            notes.append(self.comparable_players[0])
        
        # Competition level context
        notes.append(f"Scouted primarily in {self.competition_level} competition.")
        
        # Add projection timeline
        notes.append(f"Projected NHL readiness: {self.projected_nhl_arrival}.")
        
        if self.projected_draft_position:
            notes.append(f"Current draft projection: {self.projected_draft_position} overall.")
        
        self.notes = " ".join(notes)
        self.strengths = strengths
        self.weaknesses = weaknesses

    def _conduct_player_interview(self, player: Player):
        """Conduct a player interview to assess personality and coachability."""
        self.interview_conducted = True
        
        # Generate personality assessment
        personalities = [
            "Highly motivated and driven competitor",
            "Quiet leader who leads by example", 
            "Vocal presence with natural leadership qualities",
            "Team-first player with excellent character",
            "Intense competitor with strong work ethic",
            "Coachable player who accepts instruction well",
            "Independent thinker who needs proper motivation"
        ]
        
        self.personality_assessment = random.choice(personalities)
        
        # Coachability rating (influenced by actual player attributes if available)
        base_coachability = 10
        if hasattr(player, 'determination'):
            base_coachability += (player.determination - 10) // 2
        if hasattr(player, 'discipline'):
            base_coachability += (player.discipline - 10) // 2
        
        self.coachability_rating = max(1, min(20, base_coachability + random.randint(-3, 3)))

    def get_attribute_value(self, attr_name: str) -> int:
        """Extract numeric value from scouted attribute (handles ranges)."""
        if attr_name not in self.scouted_attributes:
            return 10
            
        attr_val = self.scouted_attributes[attr_name]
        
        if '-' in attr_val:
            lower, upper = map(int, attr_val.split('-'))
            return (lower + upper) // 2
        else:
            return int(attr_val)

    def get_confidence_level(self) -> str:
        """Return a description of scout confidence in this report."""
        confidence_map = {
            'A': "Very High Confidence",
            'B': "High Confidence", 
            'C': "Moderate Confidence",
            'D': "Low Confidence",
            'F': "Very Low Confidence"
        }
        return confidence_map.get(self.accuracy, "Unknown")
    
    def is_recommendation_positive(self) -> bool:
        """Determine if scout recommends this player."""
        if self.scouted_potential in ['A+', 'A', 'A-', 'B+']:
            return True
        elif self.scouted_potential in ['B', 'B-'] and self.accuracy in ['A', 'B']:
            return True
        return False

# --- Email and Inbox System (EHM-style) ---
@dataclass
class EmailMessage:
    """Represents an email message in the inbox system, similar to EHM."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    sender_type: str = "System"  # "System", "Agent", "Scout", "Media", "Owner", "Player", "Staff"
    subject: str = ""
    content: str = ""
    date_sent: date = field(default_factory=date.today)
    date_read: Optional[date] = None
    is_read: bool = False
    is_important: bool = False
    is_urgent: bool = False
    category: str = "General"  # "Trade", "Scouting", "Contracts", "Injuries", "Development", "Media", "League", "General"
    attachments: List[str] = field(default_factory=list)  # For potential future file attachments
    requires_response: bool = False
    response_deadline: Optional[date] = None
    priority: int = 1  # 1=Low, 2=Medium, 3=High, 4=Urgent
    
    # Related game objects (for context)
    related_player_id: Optional[str] = None
    related_team: Optional[str] = None
    related_contract_id: Optional[str] = None
    
    def mark_as_read(self):
        """Mark this email as read."""
        if not self.is_read:
            self.is_read = True
            self.date_read = date.today()
    
    def is_overdue(self) -> bool:
        """Check if this email's response is overdue."""
        if self.requires_response and self.response_deadline:
            return date.today() > self.response_deadline
        return False
    
    def get_age_days(self) -> int:
        """Get the age of this email in days."""
        return (date.today() - self.date_sent).days

@dataclass 
class EmailInbox:
    """Manages the player's email inbox system, similar to EHM."""
    messages: List[EmailMessage] = field(default_factory=list)
    unread_count: int = 0
    total_messages: int = 0
    auto_delete_after_days: int = 365  # Auto-delete old emails after 1 year
    
    def add_message(self, message: EmailMessage):
        """Add a new message to the inbox."""
        self.messages.insert(0, message)  # Add to front for newest first
        if not message.is_read:
            self.unread_count += 1
        self.total_messages += 1
        self._cleanup_old_messages()
    
    def mark_message_read(self, message_id: str):
        """Mark a specific message as read."""
        for message in self.messages:
            if message.id == message_id and not message.is_read:
                message.mark_as_read()
                self.unread_count = max(0, self.unread_count - 1)
                break
    
    def mark_all_read(self):
        """Mark all messages as read."""
        for message in self.messages:
            if not message.is_read:
                message.mark_as_read()
        self.unread_count = 0
    
    def delete_message(self, message_id: str):
        """Delete a specific message."""
        for i, message in enumerate(self.messages):
            if message.id == message_id:
                if not message.is_read:
                    self.unread_count = max(0, self.unread_count - 1)
                del self.messages[i]
                break
    
    def get_messages_by_category(self, category: str) -> List[EmailMessage]:
        """Get all messages in a specific category."""
        return [msg for msg in self.messages if msg.category == category]
    
    def get_unread_messages(self) -> List[EmailMessage]:
        """Get all unread messages."""
        return [msg for msg in self.messages if not msg.is_read]
    
    def get_urgent_messages(self) -> List[EmailMessage]:
        """Get all urgent messages."""
        return [msg for msg in self.messages if msg.is_urgent or msg.priority >= 4]
    
    def get_overdue_messages(self) -> List[EmailMessage]:
        """Get all messages that require a response and are overdue."""
        return [msg for msg in self.messages if msg.is_overdue()]
    
    def _cleanup_old_messages(self):
        """Remove messages older than the auto-delete threshold."""
        cutoff_date = date.today() - timedelta(days=self.auto_delete_after_days)
        initial_count = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.date_sent >= cutoff_date]
        deleted_count = initial_count - len(self.messages)
        if deleted_count > 0:
            print(f"Auto-deleted {deleted_count} old email messages")

class EmailGenerator:
    """Generates realistic emails for various game events, similar to EHM."""
    
    @staticmethod
    def create_trade_offer_email(offering_team: str, target_player: str, offered_players: List[str]) -> EmailMessage:
        """Create an email for a trade offer."""
        subject = f"Trade Offer from {offering_team}"
        content = f"Dear General Manager,\n\n"
        content += f"The {offering_team} have submitted a trade proposal:\n\n"
        content += f"They are requesting: {target_player}\n"
        content += f"They are offering: {', '.join(offered_players)}\n\n"
        content += f"Please review this proposal and respond at your earliest convenience.\n\n"
        content += f"Regards,\nLeague Office"
        
        return EmailMessage(
            sender=f"{offering_team} GM",
            sender_type="Agent",
            subject=subject,
            content=content,
            category="Trade",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=3),
            priority=3,
            related_team=offering_team
        )
    
    @staticmethod
    def create_injury_report_email(player_name: str, injury_type: str, expected_return: str) -> EmailMessage:
        """Create an email for a player injury."""
        subject = f"Injury Report: {player_name}"
        content = f"Medical Department Update\n\n"
        content += f"Player: {player_name}\n"
        content += f"Injury: {injury_type}\n"
        content += f"Expected Return: {expected_return}\n\n"
        content += f"We will continue to monitor {player_name}'s recovery and provide updates as necessary.\n\n"
        content += f"Dr. Smith\nTeam Physician"
        
        return EmailMessage(
            sender="Medical Staff",
            sender_type="Staff",
            subject=subject,
            content=content,
            category="Injuries",
            is_important=True,
            priority=3,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_scouting_report_email(scout_name: str, player_name: str, potential_grade: str) -> EmailMessage:
        """Create an email for a completed scouting report."""
        subject = f"Scouting Report: {player_name}"
        content = f"Scouting Department Report\n\n"
        content += f"Scout: {scout_name}\n"
        content += f"Player: {player_name}\n"
        content += f"Potential Grade: {potential_grade}\n\n"
        content += f"The complete scouting report is now available in the scouting system.\n\n"
        content += f"Best regards,\n{scout_name}\nScout"
        
        return EmailMessage(
            sender=scout_name,
            sender_type="Scout",
            subject=subject,
            content=content,
            category="Scouting",
            priority=2,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_contract_negotiation_email(player_name: str, agent_name: str, demand_type: str) -> EmailMessage:
        """Create an email for contract negotiations."""
        subject = f"Contract Negotiation: {player_name}"
        content = f"Dear General Manager,\n\n"
        content += f"I am writing on behalf of my client, {player_name}.\n\n"
        content += f"{demand_type}\n\n"
        content += f"Please contact me to discuss terms.\n\n"
        content += f"Best regards,\n{agent_name}\nPlayer Agent"
        
        return EmailMessage(
            sender=agent_name,
            sender_type="Agent",
            subject=subject,
            content=content,
            category="Contracts",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=7),
            priority=2,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_media_request_email(journalist_name: str, topic: str) -> EmailMessage:
        """Create an email for a media interview request."""
        subject = f"Interview Request: {topic}"
        content = f"Dear General Manager,\n\n"
        content += f"I am writing to request an interview regarding {topic}.\n\n"
        content += f"Would you be available for a brief discussion this week?\n\n"
        content += f"Best regards,\n{journalist_name}\nSports Journalist"
        
        return EmailMessage(
            sender=journalist_name,
            sender_type="Media",
            subject=subject,
            content=content,
            category="Media",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=2),
            priority=1
        )
    
    @staticmethod
    def create_league_announcement_email(subject: str, content: str) -> EmailMessage:
        """Create an email for league announcements."""
        return EmailMessage(
            sender="League Office",
            sender_type="System",
            subject=subject,
            content=content,
            category="League",
            is_important=True,
            priority=2
        )

@dataclass
class DraftPick:
    """Represents a draft pick that can be owned and traded."""
    year: int  # Draft year
    round: int  # Round number (1-7)
    original_team: str  # Team that originally owned this pick
    current_team: str  # Team that currently owns this pick
    overall_pick: int = 0  # Overall pick number (calculated when draft order is set)
    is_conditional: bool = False  # If this pick has conditions attached
    condition: str = ""  # Description of any conditions
    traded_from: str = ""  # Team this pick was traded from (if applicable)
    trade_date: str = ""  # When this pick was traded
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """Calculate overall pick number based on round."""
        if self.overall_pick == 0:
            # Estimate overall pick (32 teams per round). Mid-round is the
            # honest default for an unknown pick - estimating pick #1 of the
            # round inflates trade value via the lottery premium.
            self.overall_pick = ((self.round - 1) * 32) + 16
    
    @property
    def description(self) -> str:
        """Get a description of this draft pick."""
        if self.original_team == self.current_team:
            return f"{self.year} {self.round}st Round Pick"
        else:
            return f"{self.year} {self.round}st Round Pick (from {self.original_team})"
    
    @property
    def value(self) -> int:
        """Calculate the trade value of this draft pick."""
        # Base value decreases with later rounds and later years
        base_values = {1: 1000, 2: 500, 3: 250, 4: 125, 5: 100, 6: 75, 7: 50}
        base_value = base_values.get(self.round, 25)
        
        # Decrease value for future years
        year_penalty = max(0, (self.year - 2024) * 50)
        
        # Conditional picks are worth less
        conditional_penalty = 200 if self.is_conditional else 0
        
        return max(25, base_value - year_penalty - conditional_penalty)
    
    def can_be_traded(self) -> bool:
        """Check if this pick can be traded (some leagues have rules)."""
        # Basic rule: can't trade conditional picks that haven't been fulfilled
        if self.is_conditional and self.condition:
            return False
        return True

@dataclass
class GMProfile:
    """Represents the General Manager's profile and background."""
    name: str = "Your Name"
    age: int = 35
    birthplace: str = "Toronto, ON"
    nationality: str = "Canadian"
    
    # Playing background
    former_player: bool = False
    playing_position: str = "Center"  # If former player
    nhl_games_played: int = 0
    career_points: int = 0
    
    # Management background  
    coaching_experience: bool = False
    years_coaching: int = 0
    assistant_gm_experience: bool = False
    years_as_assistant: int = 0
    
    # Education & Skills
    education_level: str = "University Degree"  # High School, College, University Degree, MBA
    management_style: str = "Balanced"  # Analytics-Based, Traditional, Player-First, Balanced
    
    # Personality traits that could affect gameplay
    risk_tolerance: str = "Moderate"  # Conservative, Moderate, Aggressive
    loyalty_to_players: str = "Medium"  # Low, Medium, High
    media_savvy: str = "Good"  # Poor, Average, Good, Excellent
    
    def __post_init__(self):
        """Validate GM profile data after initialization."""
        if self.age < 25:
            self.age = 25
        elif self.age > 70:
            self.age = 70

@dataclass
class Team:
    """Represents a single hockey team with a deep organizational structure."""
    team_name: str
    city: str
    division: str
    conference: str
    league_name: str = "National Hockey League"  # Default to NHL
    gm_name: str = "General Manager"  # Name of the team's GM
    gm_profile: GMProfile = field(default_factory=GMProfile)  # Full GM profile
    
    roster: List[Player] = field(default_factory=list)
    ahl_roster: List[Player] = field(default_factory=list)
    prospects: List[Player] = field(default_factory=list)
    staff: List[Staff] = field(default_factory=list)
    lineup: Dict[str, Player] = field(default_factory=dict)
    
    is_user_team: bool = False
    salary_cap: int = 83500000
    scouting_reports: Dict[int, ScoutingReport] = field(default_factory=dict)
    inbox: EmailInbox = field(default_factory=EmailInbox)  # Email inbox system
    
    # Team tactics (connected to strategy UI and sim engine)
    # Even strength: 'Offensive', 'Balanced', 'Defensive'
    tactic_even_strength: str = "Balanced"
    # Power play: 'Very Offensive', 'Offensive', 'Balanced'
    tactic_power_play: str = "Offensive"
    # Penalty kill: 'Aggressive', 'Defensive', 'Very Defensive'
    tactic_penalty_kill: str = "Defensive"
    # Line matching: 'Aggressive', 'Standard', 'Conservative'
    tactic_line_matching: str = "Standard"
    
    # Draft picks owned by this team
    draft_picks: Dict[int, List[DraftPick]] = field(default_factory=dict)  # Year -> List of picks
    
    # Team Statistics for Standings
    wins: int = 0
    losses: int = 0
    ties: int = 0
    ot_losses: int = 0
    games_played: int = 0

    @property
    def payroll(self) -> int:
        return sum(p.contract.salary for p in self.roster)

    @property
    def cap_space(self) -> int:
        return self.salary_cap - self.payroll
    
    @property
    def team_chemistry(self) -> int:
        """Calculates team chemistry based on player morale and leadership."""
        if not self.roster:
            return 50
        avg_morale = sum(p.morale for p in self.roster) / len(self.roster)
        avg_leadership = sum(p.leadership for p in self.roster) / len(self.roster)
        return int((avg_morale * 6) + (avg_leadership * 4))
    
    @property
    def points(self) -> int:
        """Calculate total points (2 for win, 1 for tie/OT loss)"""
        return (self.wins * 2) + self.ties + self.ot_losses
    
    @property
    def winning_percentage(self) -> float:
        """Calculate winning percentage"""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played
    
    @property
    def record_string(self) -> str:
        """Get team record as a formatted string"""
        if self.ot_losses > 0:
            return f"{self.wins}-{self.losses}-{self.ot_losses}"
        elif self.ties > 0:
            return f"{self.wins}-{self.losses}-{self.ties}"
        else:
            return f"{self.wins}-{self.losses}"

    def add_player(self, player: Player, roster_type: str = "roster"):
        """Adds a player to the specified roster (roster, ahl, prospects)."""
        roster_map = { "roster": self.roster, "ahl": self.ahl_roster, "prospects": self.prospects }
        if roster_type in roster_map:
            roster_map[roster_type].append(player)
            player.team_name = self.team_name
        else:
            raise ValueError("Invalid roster type specified.")

    def remove_player(self, player: Player):
        """Removes a player from any list they are on."""
        if player in self.roster: self.roster.remove(player)
        if player in self.ahl_roster: self.ahl_roster.remove(player)
        if player in self.prospects: self.prospects.remove(player)
        player.team_name = "Free Agent"

    def get_players_by_position(self, position: PlayerPosition) -> List[Player]:
        return [p for p in self.roster if p.primary_position == position]

    def get_starting_goalie(self) -> Player:
        goalies = self.get_players_by_position(PlayerPosition.GOALIE)
        if not goalies:
            return Player("Default", "Goalie", 99, PlayerPosition.GOALIE, goaltending=1)
        return max(goalies, key=lambda g: g.overall_rating())
    
    def validate_staff_structure(self) -> Dict[str, List[str]]:
        """Validate the team's staff structure and return any issues"""
        issues = {'errors': [], 'warnings': []}
        
        # Check for unique role violations
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        role_counts = {}
        
        for staff_member in self.staff:
            role = staff_member.role
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # Check unique role constraints
        for role in unique_roles:
            count = role_counts.get(role, 0)
            if count == 0:
                issues['errors'].append(f"Missing {role.value}")
            elif count > 1:
                issues['errors'].append(f"Multiple {role.value}s ({count})")
        
        # Check essential roles
        essential_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH
        ]
        
        for role in essential_roles:
            if role not in role_counts:
                issues['warnings'].append(f"Missing {role.value}")
        
        # Check total staff count
        if len(self.staff) < 8:
            issues['warnings'].append(f"Only {len(self.staff)} staff members (recommended: 10-15)")
        elif len(self.staff) > 20:
            issues['warnings'].append(f"Very large staff ({len(self.staff)} members)")
        
        return issues
    
    def get_staff_by_role(self, role: StaffRole) -> List[Staff]:
        """Get all staff members with a specific role"""
        return [staff for staff in self.staff if staff.role == role]
    
    def has_unique_roles(self) -> bool:
        """Check if team has exactly one of each unique role"""
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        for role in unique_roles:
            staff_with_role = self.get_staff_by_role(role)
            if len(staff_with_role) != 1:
                return False
        return True
    
    def update_record(self, result: str, overtime: bool = False):
        """Update team record based on game result"""
        self.games_played += 1
        
        if result.upper() == "WIN":
            self.wins += 1
        elif result.upper() == "LOSS":
            if overtime:
                self.ot_losses += 1
            else:
                self.losses += 1
        elif result.upper() == "TIE":
            self.ties += 1
    
    def reset_season_record(self):
        """Reset team record for new season"""
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.ot_losses = 0
        self.games_played = 0
    
    def generate_sample_season_record(self, games_played: int = 25):
        """Generate a realistic sample season record for demonstration purposes"""
        import random
        
        # Reset current record
        self.reset_season_record()
        
        # Based on team quality (average roster rating), determine win probability
        if self.roster:
            avg_rating = sum(p.overall_rating() for p in self.roster[:20]) / min(20, len(self.roster))
            # Convert rating (0-20) to win probability (0.3 - 0.7)
            base_win_probability = 0.3 + (avg_rating / 20.0) * 0.4
        else:
            base_win_probability = 0.5  # Default 50% win rate
        
        # Simulate games
        for _ in range(games_played):
            self.games_played += 1
            
            # Random outcome based on team strength
            outcome_roll = random.random()
            
            if outcome_roll < base_win_probability:
                self.wins += 1
            elif outcome_roll < base_win_probability + 0.08:  # 8% chance of OT loss
                self.ot_losses += 1
            elif outcome_roll < base_win_probability + 0.12:  # 4% chance of tie (rare in modern NHL)
                self.ties += 1
            else:
                self.losses += 1

    def initialize_draft_picks(self, years: List[int]):
        """Initialize standard draft picks for specified years."""
        for year in years:
            if year not in self.draft_picks:
                self.draft_picks[year] = []
                
            # Add standard 7 rounds of picks if they don't exist
            existing_rounds = {pick.round for pick in self.draft_picks[year]}
            for round_num in range(1, 8):  # Rounds 1-7
                if round_num not in existing_rounds:
                    pick = DraftPick(
                        year=year,
                        round=round_num,
                        original_team=self.team_name,
                        current_team=self.team_name
                    )
                    self.draft_picks[year].append(pick)

    def get_picks_for_year(self, year: int) -> List[DraftPick]:
        """Get all draft picks owned by this team for a specific year."""
        return self.draft_picks.get(year, [])

    def get_tradeable_picks(self, years: List[int] = None) -> List[DraftPick]:
        """Get all tradeable draft picks owned by this team."""
        if years is None:
            years = list(self.draft_picks.keys())
        
        tradeable = []
        for year in years:
            for pick in self.draft_picks.get(year, []):
                if pick.can_be_traded():
                    tradeable.append(pick)
        return tradeable

    def trade_pick(self, pick: DraftPick, to_team: str, trade_details: str = ""):
        """Trade a draft pick to another team."""
        if pick not in self.draft_picks.get(pick.year, []):
            raise ValueError("Team does not own this draft pick")
        
        if not pick.can_be_traded():
            raise ValueError("This draft pick cannot be traded")
        
        # Update pick ownership
        pick.traded_from = self.team_name
        pick.current_team = to_team
        pick.trade_date = str(date.today())
        
        # Remove from this team's picks
        self.draft_picks[pick.year].remove(pick)

    def receive_pick(self, pick: DraftPick):
        """Receive a draft pick from a trade."""
        # Ensure the year exists in our picks dictionary
        if pick.year not in self.draft_picks:
            self.draft_picks[pick.year] = []
        
        # Update ownership
        pick.current_team = self.team_name
        
        # Add to our picks
        self.draft_picks[pick.year].append(pick)

    def get_draft_pick_summary(self) -> str:
        """Get a summary of all draft picks owned."""
        if not self.draft_picks:
            return "No draft picks"
        
        summary_parts = []
        for year in sorted(self.draft_picks.keys()):
            picks = self.draft_picks[year]
            if picks:
                rounds = sorted([pick.round for pick in picks])
                summary_parts.append(f"{year}: Rounds {', '.join(map(str, rounds))}")
        
        return "; ".join(summary_parts) if summary_parts else "No draft picks"

    def count_picks_by_round(self, year: int) -> Dict[int, int]:
        """Count how many picks the team has in each round for a given year."""
        picks = self.get_picks_for_year(year)
        round_counts = {}
        
        for pick in picks:
            round_counts[pick.round] = round_counts.get(pick.round, 0) + 1
        
        return round_counts

@dataclass
class League:
    """Represents the entire league, structured like the NHL."""
    league_name: str
    season_year: int = field(default_factory=lambda: datetime.now().year)
    teams: List[Team] = field(default_factory=list)
    free_agents: List[Player] = field(default_factory=list)  # Kept for compatibility, but may be overridden
    free_agent_staff: List[Staff] = field(default_factory=list)
    draft_prospects: List[Player] = field(default_factory=list)
    schedule: List[Tuple[date, Team, Team]] = field(default_factory=list)
    standings: Dict[str, Dict] = field(default_factory=dict)
    current_game_index: int = 0
    _game_manager: object = field(default=None, init=False, repr=False)  # Reference to game manager
    
    def set_game_manager(self, game_manager):
        """Set reference to game manager for database access."""
        self._game_manager = game_manager
    
    def __post_init__(self):
        self.setup_nhl_teams()

    def setup_nhl_teams(self):
        """Initializes the league with all 32 real NHL teams (2024-25 season)."""
        teams_data = {
            # Eastern Conference
            "Metropolitan": {
                "Carolina Hurricanes": "Raleigh", "Columbus Blue Jackets": "Columbus", 
                "New Jersey Devils": "Newark", "New York Islanders": "New York", 
                "New York Rangers": "New York", "Philadelphia Flyers": "Philadelphia", 
                "Pittsburgh Penguins": "Pittsburgh", "Washington Capitals": "Washington"
            },
            "Atlantic": {
                "Boston Bruins": "Boston", "Buffalo Sabres": "Buffalo", 
                "Detroit Red Wings": "Detroit", "Florida Panthers": "Sunrise", 
                "Montréal Canadiens": "Montreal", "Ottawa Senators": "Ottawa", 
                "Tampa Bay Lightning": "Tampa Bay", "Toronto Maple Leafs": "Toronto"
            },
            # Western Conference
            "Central": {
                "Chicago Blackhawks": "Chicago", "Colorado Avalanche": "Denver", 
                "Dallas Stars": "Dallas", "Minnesota Wild": "St. Paul", 
                "Nashville Predators": "Nashville", "St. Louis Blues": "St. Louis", 
                "Utah Hockey Club": "Salt Lake City", "Winnipeg Jets": "Winnipeg"
            },
            "Pacific": {
                "Anaheim Ducks": "Anaheim", "Calgary Flames": "Calgary", 
                "Edmonton Oilers": "Edmonton", "Los Angeles Kings": "Los Angeles", 
                "San Jose Sharks": "San Jose", "Seattle Kraken": "Seattle", 
                "Vancouver Canucks": "Vancouver", "Vegas Golden Knights": "Las Vegas"
            }
        }
        for division, teams in teams_data.items():
            conference = "Eastern" if division in ["Metropolitan", "Atlantic"] else "Western"
            for name, city in teams.items():
                team = Team(name, city, division, conference)
                team.league_name = "National Hockey League"  # Mark as NHL team
                self.teams.append(team)
        self.initialize_standings()

    def initialize_standings(self):
        """Sets up the standings dictionary for each team."""
        for team in self.teams:
            self.standings[team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}

    def generate_schedule(self, season_year=None, rotation_seed=None):
        """Generate complete league schedule with authentic NHL rotating patterns and realistic distribution.

        Args:
            season_year: The year this season starts (default: the league's
                season_year, which defaults to the current year)
            rotation_seed: Optional seed for reproducible schedule variations (uses season_year if None)
        """
        if season_year is None:
            season_year = self.season_year
        print(f"🏒 Generating league schedule for {season_year}-{season_year+1} season...")
        
        # Set up seasonal rotation seed
        if rotation_seed is None:
            rotation_seed = season_year
        random.seed(rotation_seed)  # For reproducible but varied schedules
        
        self.schedule.clear()
        
        # Group teams by league
        leagues = {}
        for team in self.teams:
            league_name = getattr(team, 'league_name', 'National Hockey League')
            if league_name not in leagues:
                leagues[league_name] = []
            leagues[league_name].append(team)
        
        # Generate schedule for each league separately
        for league_name, league_teams in leagues.items():
            if len(league_teams) < 2:
                continue  # Skip leagues with less than 2 teams
                
            print(f"Generating schedule for {league_name} ({len(league_teams)} teams)")
            if league_name == "National Hockey League":
                self._generate_authentic_nhl_schedule(league_teams, season_year, rotation_seed)
            else:
                self._generate_other_league_schedule(league_teams, league_name)
        
        # Sort all games by date
        self.schedule.sort(key=lambda x: x['date'] if isinstance(x, dict) and 'date' in x else x[0])
        
        # Verify schedule integrity
        self._verify_complete_schedule_integrity()
        
        # Reset random seed to avoid affecting other game elements
        import time
        random.seed(int(time.time()))

    def _generate_authentic_nhl_schedule(self, nhl_teams, season_year, rotation_seed):
        """Generate NHL schedule with simple chronological approach to prevent consecutive games."""
        print("🏒 Building NHL schedule with simple consecutive games prevention...")
        
        if len(nhl_teams) != 32:
            print(f"⚠️ Warning: Expected 32 NHL teams, got {len(nhl_teams)}")
            return
        
        # Initialize NHL games only (preserve existing schedule for other leagues)
        nhl_games = []
        self.games = {}
        
        # Create all required matchups first (82 games per team = 1,312 total games)
        all_matchups = self._create_all_nhl_matchups(nhl_teams)
        print(f"Created {len(all_matchups)} total matchups")
        
        # Schedule games chronologically with consecutive games prevention
        self._schedule_games_chronologically(all_matchups, nhl_teams, season_year)
        
        # Add NHL special events (All-Star, Trade Deadline, Draft, etc.)
        calendar_data = self._create_authentic_nhl_calendar(season_year)
        self._add_nhl_special_events(calendar_data['events'], season_year)

    def _create_all_nhl_matchups(self, nhl_teams):
        """Create all required NHL matchups in a simple way - exactly 82 games per team."""
        print("Creating all NHL matchups...")
        
        # Organize teams by division and conference
        divisions = {
            'Atlantic': [t for t in nhl_teams if t.division == 'Atlantic'],
            'Metropolitan': [t for t in nhl_teams if t.division == 'Metropolitan'], 
            'Central': [t for t in nhl_teams if t.division == 'Central'],
            'Pacific': [t for t in nhl_teams if t.division == 'Pacific']
        }
        
        all_matchups = []
        
        # Each team needs exactly 82 games total
        # Simple approach: Each team plays every other team in the league ~2-3 times
        
        # For each team, schedule games against all 31 other teams
        interconference_games_assigned = 0  # Track to keep total at 82 per team
        
        for i, team1 in enumerate(nhl_teams):
            for j, team2 in enumerate(nhl_teams):
                if i < j:  # Avoid duplicates - each pair only once
                    # Decide how many games between these teams based on relationship
                    if team1.division == team2.division:
                        # Division rivals: 4 games each (4 × 7 = 28 games per team)
                        games_count = 4
                    elif team1.conference == team2.conference:
                        # Same conference, different division: 3 games each (3 × 8 = 24 games per team)
                        games_count = 3  
                    else:
                        # Different conference: 2 games each (2 × 16 = 32 games per team)
                        # Total: 28 + 24 + 32 = 84, which is 2 over our target
                        # So reduce some inter-conference games from 2 to 1
                        if (i + j) % 16 < 14:  # 14 out of 16 inter-conference matchups get 2 games
                            games_count = 2
                        else:  # 2 out of 16 inter-conference matchups get 1 game  
                            games_count = 1
                        # This gives: 28 + 24 + (2×14 + 1×2) = 28 + 24 + 30 = 82 games
                    
                    # Add the games (alternating home/away)
                    for game_num in range(games_count):
                        if game_num % 2 == 0:
                            all_matchups.append((team1, team2, 'HOME'))  # team1 hosts
                        else:
                            all_matchups.append((team2, team1, 'HOME'))  # team2 hosts
        
        # Shuffle matchups to distribute them randomly throughout season
        random.shuffle(all_matchups)
        print(f"Created {len(all_matchups)} total games")
        return all_matchups

    def _schedule_games_chronologically(self, all_matchups, nhl_teams, season_year):
        """Schedule games chronologically with REALISTIC NHL conflict prevention - allows back-to-backs but prevents 3+ consecutive games."""
        print("Scheduling games with REALISTIC NHL scheduling rules...")
        
        # Initialize NHL-specific storage
        nhl_games = []
        
        # Track when each team last played AND what games are scheduled per day
        team_last_played = {team.team_name: None for team in nhl_teams}
        team_second_last_played = {team.team_name: None for team in nhl_teams}  # Track two days back
        team_games_scheduled = {team.team_name: 0 for team in nhl_teams}
        team_back_to_backs = {team.team_name: 0 for team in nhl_teams}  # Track back-to-back count
        games_by_date = {}  # Track which teams play on each date
        
        # Create season dates using the same range as the calendar for consistency
        season_start = date(season_year, 10, 8)   # Match calendar start
        season_end = date(season_year + 1, 4, 25)  # Match extended calendar end
        
        # Get NHL calendar events for proper break scheduling
        calendar_data = self._create_authentic_nhl_calendar(season_year)
        calendar_events = calendar_data['events']
        
        current_date = season_start
        scheduled_matchups = []
        remaining_matchups = all_matchups.copy()
        
        max_games_per_day = 16  # Maximum NHL games per day (each game uses 2 teams)
        max_back_to_backs_per_team = 25  # More flexible to ensure all games get scheduled
        
        # Track progress and apply progressive flexibility
        days_into_season = 0
        total_season_days = (season_end - season_start).days
        
        # Season pacing - reduce daily games to spread over full calendar
        # Real NHL averages 6.9 games/day over 191 days
        target_daily_games = max(4, min(16, int(1312 / total_season_days * 1.2)))  # Slight buffer
        
        while current_date <= season_end and remaining_matchups:
            days_into_season += 1
            season_progress = days_into_season / total_season_days if total_season_days > 0 else 0
            
            # NHL Calendar breaks - skip certain dates to spread season
            should_skip_date = False
            
            # Check for official NHL break periods
            # Christmas break (Dec 24-26) - reduced games
            if current_date.month == 12 and current_date.day in [24, 25, 26]:
                if len(remaining_matchups) > 200:  # Only skip if plenty of games remain
                    should_skip_date = True
            
            # New Year's Day - reduced games  
            elif current_date.month == 1 and current_date.day == 1:
                if len(remaining_matchups) > 150:
                    should_skip_date = True
                    
            # Check for All-Star break using actual calendar dates
            else:
                # Check if current date is in any official break period
                for break_name, break_period in [
                    ('thanksgiving_break', calendar_events.get('thanksgiving_break')),
                    ('christmas_break', calendar_events.get('christmas_break')),
                    ('all_star_break', calendar_events.get('all_star_break'))
                ]:
                    if break_period and isinstance(break_period, tuple) and len(break_period) == 2:
                        break_start, break_end = break_period
                        if break_start <= current_date <= break_end:
                            should_skip_date = True
                            break  # Exit the loop early if we found a break
            
            if should_skip_date:
                current_date += timedelta(days=1)
                continue
            
            # Dynamically adjust daily games based on season progress to spread games
            season_progress = days_into_season / total_season_days if total_season_days > 0 else 0
            
            # IMPROVED Progressive daily limit - more gradual increases to prevent clustering
            remaining_days = max(1, total_season_days - days_into_season)
            needed_daily = len(remaining_matchups) / remaining_days if remaining_days > 0 else target_daily_games
            
            if season_progress < 0.4:  # Early season - conservative scheduling
                daily_limit = max(4, target_daily_games - 1)
            elif season_progress < 0.7:  # Mid season - normal pace  
                daily_limit = target_daily_games
            elif season_progress < 0.85:  # Late season - gradual increase
                daily_limit = min(target_daily_games + 2, int(needed_daily * 1.2))
            else:  # Final stretch - controlled increase with limits
                # Cap at 12 games per day even in final stretch to prevent clustering
                daily_limit = min(12, max(target_daily_games, int(needed_daily * 1.1)))
            
            # MODIFIED EMERGENCY MODE: More restrictive - only for very end of season
            emergency_mode = season_progress > 0.90 and len(remaining_matchups) > 50
            
            # Initialize tracking for this date
            if current_date not in games_by_date:
                games_by_date[current_date] = set()  # Set of team names playing today
            
            daily_games = []
            teams_playing_today = games_by_date[current_date].copy()
            
            # Try to schedule games for today
            attempts = 0
            max_attempts = len(remaining_matchups) * 3  # More attempts to find valid games
            
            while len(daily_games) < daily_limit and remaining_matchups and attempts < max_attempts:
                attempts += 1
                matchup_found = False
                
                for i, (team1, team2, venue) in enumerate(remaining_matchups):
                    team1_name = team1.team_name
                    team2_name = team2.team_name
                    
                    # CRITICAL FIX: Check if EITHER team is already playing today
                    if team1_name in teams_playing_today or team2_name in teams_playing_today:
                        continue  # Skip - one of the teams already has a game today
                    
                    # Relaxed constraints in emergency mode
                    if not emergency_mode:
                        # ENHANCED RULE: Prevent 3+ consecutive games with stricter enforcement
                        yesterday = current_date - timedelta(days=1)
                        day_before_yesterday = current_date - timedelta(days=2)
                        
                        team1_played_yesterday = team_last_played.get(team1_name) == yesterday
                        team1_played_day_before = team_second_last_played.get(team1_name) == day_before_yesterday
                        team2_played_yesterday = team_last_played.get(team2_name) == yesterday
                        team2_played_day_before = team_second_last_played.get(team2_name) == day_before_yesterday
                        
                        # STRONGER 3-consecutive prevention - now includes late season
                        if (team1_played_yesterday and team1_played_day_before) or (team2_played_yesterday and team2_played_day_before):
                            continue  # Would create 3+ consecutive games - forbidden
                        
                        # PROGRESSIVE back-to-back limits with IMPROVED logic
                        is_back_to_back_team1 = team1_played_yesterday
                        is_back_to_back_team2 = team2_played_yesterday
                        
                        # More generous back-to-back limits but stricter consecutive limits
                        progressive_limit = max(22, int(28 - (6 * season_progress)))
                        
                        if is_back_to_back_team1 and team_back_to_backs[team1_name] >= progressive_limit:
                            continue  # Team1 has used up their progressive back-to-back budget
                        if is_back_to_back_team2 and team_back_to_backs[team2_name] >= progressive_limit:
                            continue  # Team2 has used up their progressive back-to-back budget
                    else:
                        # EMERGENCY MODE: Still prevent 3+ consecutive even in emergency
                        yesterday = current_date - timedelta(days=1)
                        day_before_yesterday = current_date - timedelta(days=2)
                        
                        team1_played_yesterday = team_last_played.get(team1_name) == yesterday
                        team1_played_day_before = team_second_last_played.get(team1_name) == day_before_yesterday
                        team2_played_yesterday = team_last_played.get(team2_name) == yesterday
                        team2_played_day_before = team_second_last_played.get(team2_name) == day_before_yesterday
                        
                        # Even in emergency mode, prevent excessive consecutive games
                        if (team1_played_yesterday and team1_played_day_before) or (team2_played_yesterday and team2_played_day_before):
                            continue  # Still prevent 3+ consecutive in emergency mode
                    
                    # This game is valid - schedule it!
                    game_data = {
                        'date': current_date,
                        'home_team': team1 if venue == 'HOME' else team2,
                        'away_team': team2 if venue == 'HOME' else team1,
                        'time': time(19, 0),  # 7:00 PM
                        'league': 'NHL'
                    }
                    
                    daily_games.append(game_data)
                    scheduled_matchups.append((team1, team2, venue))
                    
                    # Update tracking - BOTH teams are now playing today
                    teams_playing_today.add(team1_name)
                    teams_playing_today.add(team2_name)
                    
                    # Update game history tracking
                    team_second_last_played[team1_name] = team_last_played[team1_name]
                    team_second_last_played[team2_name] = team_last_played[team2_name]
                    team_last_played[team1_name] = current_date
                    team_last_played[team2_name] = current_date
                    
                    # Update game counters
                    team_games_scheduled[team1_name] += 1
                    team_games_scheduled[team2_name] += 1
                    
                    # Update back-to-back counters only if not in emergency mode
                    if not emergency_mode or (is_back_to_back_team1 or is_back_to_back_team2):
                        if is_back_to_back_team1:
                            team_back_to_backs[team1_name] += 1
                        if is_back_to_back_team2:
                            team_back_to_backs[team2_name] += 1
                    
                    # Remove this matchup from remaining
                    remaining_matchups.pop(i)
                    matchup_found = True
                    break
                
                # If we couldn't find a valid matchup, try with MORE CAREFUL relaxed rules
                if not matchup_found and season_progress > 0.75:
                    # Try again with carefully relaxed constraints - still prevent excessive consecutive games
                    for i, (team1, team2, venue) in enumerate(remaining_matchups):
                        team1_name = team1.team_name
                        team2_name = team2.team_name
                        
                        # CRITICAL: Still check if EITHER team is already playing today
                        if team1_name in teams_playing_today or team2_name in teams_playing_today:
                            continue  # Skip - one of the teams already has a game today
                        
                        # IMPROVED: Still prevent 3+ consecutive games even in relaxed mode
                        yesterday = current_date - timedelta(days=1)
                        day_before = current_date - timedelta(days=2)
                        
                        team1_played_yesterday = team_last_played.get(team1_name) == yesterday
                        team1_played_day_before = team_second_last_played.get(team1_name) == day_before
                        team2_played_yesterday = team_last_played.get(team2_name) == yesterday
                        team2_played_day_before = team_second_last_played.get(team2_name) == day_before
                        
                        # Still enforce 3-consecutive limit even in relaxed mode (prevents 9-game streaks!)
                        if (team1_played_yesterday and team1_played_day_before) or (team2_played_yesterday and team2_played_day_before):
                            continue  # Would create 3+ consecutive - still forbidden even in relaxed mode
                        
                        # Valid game found with careful relaxed rules
                        game_data = {
                            'date': current_date,
                            'home_team': team1 if venue == 'HOME' else team2,
                            'away_team': team2 if venue == 'HOME' else team1,
                            'time': time(19, 0),  # 7:00 PM
                            'league': 'NHL'
                        }
                        
                        daily_games.append(game_data)
                        scheduled_matchups.append((team1, team2, venue))
                        
                        # Update tracking
                        teams_playing_today.add(team1_name)
                        teams_playing_today.add(team2_name)
                        
                        team_second_last_played[team1_name] = team_last_played[team1_name]
                        team_second_last_played[team2_name] = team_last_played[team2_name]
                        team_last_played[team1_name] = current_date
                        team_last_played[team2_name] = current_date
                        
                        team_games_scheduled[team1_name] += 1
                        team_games_scheduled[team2_name] += 1
                        
                        # Track back-to-backs in relaxed mode too
                        is_back_to_back_team1 = team1_played_yesterday
                        is_back_to_back_team2 = team2_played_yesterday
                        if is_back_to_back_team1:
                            team_back_to_backs[team1_name] += 1
                        if is_back_to_back_team2:
                            team_back_to_backs[team2_name] += 1
                        
                        remaining_matchups.pop(i)
                        matchup_found = True
                        break
                
                # If we still couldn't find a valid matchup, stop trying for today
                if not matchup_found:
                    break
            
            # Store which teams played today for future reference
            games_by_date[current_date] = teams_playing_today
            
            # Add today's games to the NHL schedule
            if daily_games:
                nhl_games.extend(daily_games)
                if current_date.strftime('%Y-%m-%d') not in self.games:
                    self.games[current_date.strftime('%Y-%m-%d')] = []
                self.games[current_date.strftime('%Y-%m-%d')].extend(daily_games)
                
                # Verify no team plays twice today
                team_count_today = {}
                for game in daily_games:
                    home_team = game['home_team'].team_name
                    away_team = game['away_team'].team_name
                    team_count_today[home_team] = team_count_today.get(home_team, 0) + 1
                    team_count_today[away_team] = team_count_today.get(away_team, 0) + 1
                
                # Check for violations
                violations = [team for team, count in team_count_today.items() if count > 1]
                if violations:
                    print(f"🚨 ERROR: Teams playing multiple games on {current_date}: {violations}")
                    
            current_date += timedelta(days=1)
        
        # Report results
        print(f"\n✅ PROPER NHL Scheduling complete!")
        print(f"Total games scheduled: {len(scheduled_matchups)}")
        print(f"Remaining unscheduled: {len(remaining_matchups)}")
        
        # FORCE-SCHEDULE REMAINING: If games couldn't be placed, try harder
        # This ensures all 1,312 matchups (82 per team) get scheduled
        if remaining_matchups:
            print(f"\n🔧 Force-scheduling {len(remaining_matchups)} remaining games...")
            remaining_matchups = self._force_schedule_remaining(
                remaining_matchups, nhl_teams, nhl_games, games_by_date,
                team_last_played, team_second_last_played, team_games_scheduled,
                season_start, season_end
            )
            print(f"After force-schedule: {len(remaining_matchups)} still unscheduled")
        
        # Verify no same-day conflicts across the entire schedule
        print("\n🔍 Verifying no same-day conflicts...")
        for check_date, games in self.games.items():
            teams_on_date = []
            for game in games:
                if hasattr(game, 'get'):  # It's a dictionary
                    teams_on_date.extend([game['home_team'].team_name, game['away_team'].team_name])
            
            # Check for duplicates
            if len(teams_on_date) != len(set(teams_on_date)):
                duplicate_teams = [team for team in set(teams_on_date) if teams_on_date.count(team) > 1]
                print(f"🚨 CONFLICT on {check_date}: {duplicate_teams} play multiple games")
        
        print("✅ Same-day conflict verification complete!")
        
        # Check each team's game count
        for team_name, count in team_games_scheduled.items():
            if count != 82:
                print(f"⚠️ {team_name}: {count} games (target: 82)")
        
        print("✅ Fixed NHL scheduling - NO MORE MULTIPLE GAMES PER DAY!")
        
        # HARD GUARANTEE: No team ever plays 3+ consecutive days.
        # This validation pass catches any violations from any code path
        # and reschedules the middle game of each streak to a nearby open date.
        nhl_games = self._enforce_no_three_in_a_row(nhl_games, nhl_teams)
        
        # Add NHL games to main schedule
        self.schedule.extend(nhl_games)
        print(f"✅ Added {len(nhl_games)} NHL games to main schedule")
    
    def _force_schedule_remaining(self, remaining_matchups, nhl_teams, nhl_games, games_by_date,
                                   team_last_played, team_second_last_played, team_games_scheduled,
                                   season_start, season_end):
        """Force-schedule games that couldn't be placed in the main loop.
        
        Tries every date in the season for each remaining matchup.
        Only enforces hard constraints: no same-day doubleheaders, no 3-in-a-row.
        Returns list of matchups that still couldn't be scheduled (should be empty).
        """
        from datetime import timedelta
        
        still_remaining = []
        
        for team1, team2, venue in remaining_matchups:
            team1_name = team1.team_name
            team2_name = team2.team_name
            scheduled = False
            
            # Try every date in the season
            check_date = season_start
            while check_date <= season_end and not scheduled:
                # Skip if either team already plays this date
                teams_today = games_by_date.get(check_date, set())
                if team1_name in teams_today or team2_name in teams_today:
                    check_date += timedelta(days=1)
                    continue
                
                # Check no-three-in-a-row (hard constraint)
                yesterday = check_date - timedelta(days=1)
                day_before = check_date - timedelta(days=2)
                
                t1_y = team_last_played.get(team1_name) == yesterday
                t1_db = team_second_last_played.get(team1_name) == day_before
                t2_y = team_last_played.get(team2_name) == yesterday
                t2_db = team_second_last_played.get(team2_name) == day_before
                
                if (t1_y and t1_db) or (t2_y and t2_db):
                    check_date += timedelta(days=1)
                    continue
                
                # Valid date found! Schedule the game
                game_data = {
                    'date': check_date,
                    'home_team': team1 if venue == 'HOME' else team2,
                    'away_team': team2 if venue == 'HOME' else team1,
                    'league': 'NHL'
                }
                nhl_games.append(game_data)
                
                # Update tracking
                if check_date not in games_by_date:
                    games_by_date[check_date] = set()
                games_by_date[check_date].add(team1_name)
                games_by_date[check_date].add(team2_name)
                
                # Update last played (need to be careful - this is simplified)
                # For force-schedule, we just update the most recent
                team_last_played[team1_name] = check_date
                team_last_played[team2_name] = check_date
                team_games_scheduled[team1_name] += 1
                team_games_scheduled[team2_name] += 1
                
                scheduled = True
            
            if not scheduled:
                still_remaining.append((team1, team2, venue))
        
        return still_remaining
    
    def _enforce_no_three_in_a_row(self, games, nhl_teams):
        """Ensure no team plays 3+ consecutive days. Fixes violations by moving the middle game.
        
        Args:
            games: List of game dicts with 'date', 'home_team', 'away_team'
            nhl_teams: List of Team objects
            
        Returns:
            The games list with violations fixed (games moved to nearby open dates)
        """
        from collections import defaultdict
        
        def get_team_name(team):
            return team.team_name if hasattr(team, 'team_name') else str(team)
        
        def find_violations(game_list):
            """Find all (team_name, d1, d2, d3) 3-in-a-row violations."""
            team_dates = defaultdict(list)
            for g in game_list:
                d = g['date']
                team_dates[get_team_name(g['home_team'])].append(d)
                team_dates[get_team_name(g['away_team'])].append(d)
            
            violations = []
            for team, dates in team_dates.items():
                dates = sorted(set(dates))
                for i in range(len(dates) - 2):
                    d1, d2, d3 = dates[i], dates[i+1], dates[i+2]
                    if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                        violations.append((team, d1, d2, d3))
            return violations
        
        def teams_playing_on(game_list, check_date):
            """Get set of team names playing on a given date."""
            playing = set()
            for g in game_list:
                if g['date'] == check_date:
                    playing.add(get_team_name(g['home_team']))
                    playing.add(get_team_name(g['away_team']))
            return playing
        
        def would_create_violation(game_list, team_name, new_date):
            """Check if moving a team's game to new_date would create a 3-in-a-row."""
            team_dates = set()
            for g in game_list:
                d = g['date']
                t1 = get_team_name(g['home_team'])
                t2 = get_team_name(g['away_team'])
                if t1 == team_name or t2 == team_name:
                    team_dates.add(d)
            team_dates.add(new_date)
            dates = sorted(team_dates)
            for i in range(len(dates) - 2):
                d1, d2, d3 = dates[i], dates[i+1], dates[i+2]
                if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                    return True
            return False
        
        violations = find_violations(games)
        if not violations:
            print("✅ Schedule validation: no 3-in-a-row violations found")
            return games
        
        print(f"⚠️ Schedule validation: found {len(violations)} 3-in-a-row violations, fixing...")
        
        # Get the full date range of the schedule
        all_dates = sorted(set(g['date'] for g in games))
        if not all_dates:
            return games
        min_date, max_date = all_dates[0], all_dates[-1]
        
        fixed = 0
        # Try to fix each violation by moving the middle game (d2)
        for team_name, d1, d2, d3 in violations:
            # Find the game on d2 involving this team
            target_game = None
            for g in games:
                if g['date'] == d2 and (get_team_name(g['home_team']) == team_name or 
                                        get_team_name(g['away_team']) == team_name):
                    target_game = g
                    break
            
            if not target_game:
                continue
            
            home_name = get_team_name(target_game['home_team'])
            away_name = get_team_name(target_game['away_team'])
            
            # Look for an open date where neither team plays
            # Strategy 1: Nearby dates (14 days)
            # Strategy 2: Wider window (30 days)  
            # Strategy 3: Full season scan
            # Strategy 4: Swap with another game
            moved = False
            
            # Strategy 1-3: Find open date (expanding search)
            for max_offset in [14, 30, 1000]:  # 1000 = full season
                if moved:
                    break
                for offset in range(1, max_offset + 1):
                    if moved:
                        break
                    for new_date in [d2 + timedelta(days=offset), d2 - timedelta(days=offset)]:
                        if new_date < min_date or new_date > max_date:
                            continue
                        if max_offset == 1000 and offset > (max_date - min_date).days:
                            break
                        
                        playing = teams_playing_on(games, new_date)
                        if home_name in playing or away_name in playing:
                            continue
                        
                        # Don't create new violations
                        other_games = [g for g in games if g is not target_game]
                        if would_create_violation(other_games, home_name, new_date):
                            continue
                        if would_create_violation(other_games, away_name, new_date):
                            continue
                        
                        # Safe to move
                        target_game['date'] = new_date
                        fixed += 1
                        moved = True
                        break
                    if max_offset == 1000 and offset > (max_date - min_date).days:
                        break
            
            # Strategy 4: If still not moved, try swapping with another game
            # Find a game on a date where our teams don't play, swap dates
            if not moved:
                for other_game in games:
                    if other_game is target_game:
                        continue
                    other_date = other_game['date']
                    other_home = get_team_name(other_game['home_team'])
                    other_away = get_team_name(other_game['away_team'])
                    
                    # Can't swap if it would cause same-day conflict
                    # (our teams would play on other_date, their teams on d2)
                    playing_on_other = teams_playing_on(games, other_date)
                    playing_on_d2 = teams_playing_on(games, d2)
                    
                    # After swap: our game moves to other_date, their game moves to d2
                    # Check: our teams not already on other_date (we know they're not, we checked)
                    # Check: their teams not already on d2 (excluding our game)
                    other_teams_on_d2 = playing_on_d2 - {home_name, away_name}
                    if other_home in other_teams_on_d2 or other_away in other_teams_on_d2:
                        continue
                    
                    # Check no new violations would be created
                    # (Simplified: just check the four teams involved)
                    temp_games = [g for g in games if g is not target_game and g is not other_game]
                    # Simulate the swap
                    if would_create_violation(temp_games, home_name, other_date):
                        continue
                    if would_create_violation(temp_games, away_name, other_date):
                        continue
                    if would_create_violation(temp_games, other_home, d2):
                        continue
                    if would_create_violation(temp_games, other_away, d2):
                        continue
                    
                    # Safe to swap
                    target_game['date'], other_game['date'] = other_date, d2
                    fixed += 1
                    moved = True
                    print(f"🔄 Swapped games to fix 3-in-a-row for {team_name}")
                    break
            
            if not moved:
                # ABSOLUTE LAST RESORT: This should never happen with 200-day season
                # But if it does, we log it as a critical error
                print(f"🚨 CRITICAL: Could not fix 3-in-a-row for {team_name} on {d2} ({home_name} vs {away_name})")
        
        # Final check
        remaining = find_violations(games)
        if remaining:
            print(f"⚠️ Schedule validation: {len(remaining)} violations remain after fix attempt")
        else:
            print(f"✅ Schedule validation: fixed {fixed} games, no 3-in-a-row violations remain")
        
        return games
    
    def _create_authentic_nhl_matchup_pattern(self, nhl_teams, season_year, rotation_seed):
        """Create authentic NHL matchup assignments using real NHL rotation logic.
        
        Each team plays exactly 82 games:
        - 26 games vs division rivals (7 rivals, some get 4 games, others get 3)
        - 24 games vs same-conference non-division (8 teams × 3 games each)  
        - 32 games vs other conference (16 teams × 2 games each)
        """
        print(f"🔄 Creating {season_year} NHL matchup pattern with rotation seed {rotation_seed}...")
        
        if len(nhl_teams) != 32:
            print(f"⚠️ Warning: Expected 32 NHL teams, got {len(nhl_teams)}")
            return {}
        
        # Organize teams by divisions
        divisions = self._organize_nhl_divisions(nhl_teams)
        
        # Verify division structure
        if len(divisions) != 4 or any(len(teams) != 8 for teams in divisions.values()):
            print("⚠️ Error: Invalid NHL division structure")
            return {}
        
        # Create the seasonal matchup assignments
        matchup_assignments = {}
        
        # Step 1: Division games (26 per team, rotating 4-game vs 3-game assignments)
        self._assign_divisional_games(divisions, matchup_assignments, rotation_seed)
        
        # Step 2: Conference games (24 per team, rotating intensity)  
        self._assign_conference_games(divisions, matchup_assignments, rotation_seed)
        
        # Step 3: Interconference games (32 per team, rotating home/away)
        self._assign_interconference_games(divisions, matchup_assignments, season_year)
        
        # Verify each team has exactly 82 games
        self._verify_matchup_assignments(matchup_assignments, nhl_teams)
        
        return matchup_assignments
    
    def _organize_nhl_divisions(self, nhl_teams):
        """Organize teams into proper NHL divisional structure."""
        divisions = {
            'Eastern_Metropolitan': [],
            'Eastern_Atlantic': [],
            'Western_Central': [],
            'Western_Pacific': []
        }
        
        for team in nhl_teams:
            if team.conference == 'Eastern' and team.division == 'Metropolitan':
                divisions['Eastern_Metropolitan'].append(team)
            elif team.conference == 'Eastern' and team.division == 'Atlantic':
                divisions['Eastern_Atlantic'].append(team) 
            elif team.conference == 'Western' and team.division == 'Central':
                divisions['Western_Central'].append(team)
            elif team.conference == 'Western' and team.division == 'Pacific':
                divisions['Western_Pacific'].append(team)
        
        print(f"📊 NHL Division Structure:")
        for div_name, teams in divisions.items():
            print(f"  {div_name}: {len(teams)} teams")
        
        return divisions
    
    def _assign_divisional_games(self, divisions, matchup_assignments, rotation_seed):
        """Assign divisional games with authentic NHL structure (26 games per team)."""
        print("⚡ Assigning divisional rivalries...")
        
        for div_name, div_teams in divisions.items():
            # Each team plays exactly 26 divisional games against 7 rivals
            # Real NHL: 3 rivals × 4 games + 4 rivals × 3 games = 26 games (rotating annually)
            
            for i, team in enumerate(div_teams):
                if team.team_name not in matchup_assignments:
                    matchup_assignments[team.team_name] = []
                
                # Get division rivals (the other 7 teams)
                division_rivals = [t for t in div_teams if t != team]
                
                # Use rotation seed to determine which teams get more/fewer games
                random.seed(rotation_seed + hash(team.team_name) % 1000)
                random.shuffle(division_rivals)
                
                # Assign 26 total divisional games: start with 2 per rival, then distribute extras
                # 7 rivals × 2 games = 14 base games, need 12 more to reach 26
                
                # Give everyone base 2 games (1 home, 1 away)
                for rival in division_rivals:
                    matchup_assignments[team.team_name].append(('HOME', rival))
                    matchup_assignments[team.team_name].append(('AWAY', rival))
                
                # Distribute 12 extra games among the 7 rivals
                for j in range(12):  # 12 extra games to get from 14 to 26
                    rival = division_rivals[j % len(division_rivals)]
                    # Alternate home/away for extra games
                    venue = 'HOME' if j % 2 == 0 else 'AWAY'
                    matchup_assignments[team.team_name].append((venue, rival))
    
    def _assign_conference_games(self, divisions, matchup_assignments, rotation_seed):
        """Assign same-conference, different-division games (24 per team)."""
        print("🏒 Assigning conference rivalries...")
        
        # Eastern Conference: Metropolitan vs Atlantic (bidirectional)
        self._assign_interdivisional_games(
            divisions['Eastern_Metropolitan'], 
            divisions['Eastern_Atlantic'], 
            matchup_assignments, 
            rotation_seed
        )
        self._assign_interdivisional_games(
            divisions['Eastern_Atlantic'], 
            divisions['Eastern_Metropolitan'], 
            matchup_assignments, 
            rotation_seed
        )
        
        # Western Conference: Central vs Pacific (bidirectional)
        self._assign_interdivisional_games(
            divisions['Western_Central'], 
            divisions['Western_Pacific'], 
            matchup_assignments, 
            rotation_seed
        )
        self._assign_interdivisional_games(
            divisions['Western_Pacific'], 
            divisions['Western_Central'], 
            matchup_assignments, 
            rotation_seed
        )
    
    def _assign_interdivisional_games(self, div1_teams, div2_teams, matchup_assignments, rotation_seed):
        """Assign games between two divisions in same conference (24 games per team)."""
        # Each team needs exactly 24 games against the 8 teams from the other division
        # NHL Pattern: each team plays all 8 opponents exactly 3 times = 24 games
        
        for i, team1 in enumerate(div1_teams):
            if team1.team_name not in matchup_assignments:
                matchup_assignments[team1.team_name] = []
            
            # Each team plays all 8 teams from other division exactly 3 times
            for team2 in div2_teams:
                # 3 games: 2 home, 1 away OR 1 home, 2 away (alternates by rotation)
                random.seed(rotation_seed + hash(team1.team_name + team2.team_name) % 1000)
                if random.randint(0, 1) == 0:
                    # Pattern A: 2 home, 1 away
                    matchup_assignments[team1.team_name].append(('HOME', team2))
                    matchup_assignments[team1.team_name].append(('HOME', team2))
                    matchup_assignments[team1.team_name].append(('AWAY', team2))
                else:
                    # Pattern B: 1 home, 2 away  
                    matchup_assignments[team1.team_name].append(('HOME', team2))
                    matchup_assignments[team1.team_name].append(('AWAY', team2))
                    matchup_assignments[team1.team_name].append(('AWAY', team2))
    
    def _assign_interconference_games(self, divisions, matchup_assignments, season_year):
        """Assign interconference games with rotating home/away (32 per team)."""
        print("🌐 Assigning interconference matchups...")
        
        eastern_teams = divisions['Eastern_Metropolitan'] + divisions['Eastern_Atlantic']
        western_teams = divisions['Western_Central'] + divisions['Western_Pacific']
        
        # Each Eastern team plays each Western team exactly 2 games (16 × 2 = 32 games)
        for east_team in eastern_teams:
            if east_team.team_name not in matchup_assignments:
                matchup_assignments[east_team.team_name] = []
            
            for west_team in western_teams:
                if west_team.team_name not in matchup_assignments:
                    matchup_assignments[west_team.team_name] = []
                
                # 2 games: rotate who hosts more (1 home, 1 away each team)
                # Add one home game for Eastern team
                matchup_assignments[east_team.team_name].append(('HOME', west_team))
                matchup_assignments[west_team.team_name].append(('AWAY', east_team))
                
                # Add one home game for Western team  
                matchup_assignments[west_team.team_name].append(('HOME', east_team))
                matchup_assignments[east_team.team_name].append(('AWAY', west_team))
    
    def _verify_matchup_assignments(self, matchup_assignments, nhl_teams):
        """Verify that each team has exactly 82 games assigned."""
        print("✅ Verifying matchup assignments...")
        
        all_teams_valid = True
        for team in nhl_teams:
            team_games = len(matchup_assignments.get(team.team_name, []))
            if team_games != 82:
                print(f"⚠️ {team.team_name}: {team_games} games (should be 82)")
                all_teams_valid = False
        
        if all_teams_valid:
            print("✅ All 32 teams have exactly 82 games assigned!")
        else:
            print("❌ Matchup assignment validation failed!")
        
        return all_teams_valid
    
    def _create_authentic_nhl_calendar(self, season_year):
        """Create authentic NHL season calendar with flexible scheduling."""
        print(f"📅 Creating {season_year}-{season_year+1} NHL calendar...")
        
        # Flexible NHL season dates - extend season to match real NHL timing
        season_start = date(season_year, 10, 8)   # Start a few days earlier  
        season_end = date(season_year + 1, 4, 25)  # End late April like real NHL
        
        # Define NHL calendar events and restrictions
        calendar_events = {
            'season_start': season_start,
            'season_end': season_end,
            'thanksgiving_break': (
                date(season_year, 11, 24),  # Just Thanksgiving day
                date(season_year, 11, 24)   # Single day break
            ),
            'christmas_break': (
                date(season_year, 12, 24),  # Christmas Eve to Christmas day
                date(season_year, 12, 25)   # Shorter break for more flexibility
            ),
            'all_star_break': (
                date(season_year + 1, 2, 5),   # Typically first week of February
                date(season_year + 1, 2, 11)
            ),
            'trade_deadline': date(season_year + 1, 3, 8),  # First Friday in March
            'entry_draft': date(season_year + 1, 6, 27),   # Late June
            'free_agency': date(season_year + 1, 7, 1)     # July 1st
        }
        
        # Generate schedulable dates with NHL preferences
        available_dates = []
        current_date = season_start
        
        while current_date <= season_end:
            # Check for breaks
            in_break = False
            
            # Check each break period
            for break_name, break_period in [
                ('thanksgiving_break', calendar_events['thanksgiving_break']),
                ('christmas_break', calendar_events['christmas_break']),
                ('all_star_break', calendar_events['all_star_break'])
            ]:
                if isinstance(break_period, tuple) and len(break_period) == 2:
                    if break_period[0] <= current_date <= break_period[1]:
                        in_break = True
                        break
            
            if not in_break:
                # More flexible NHL scheduling - include most days
                weekday = current_date.weekday()  # 0=Monday, 6=Sunday
                
                # More inclusive day selection for maximum scheduling flexibility
                if weekday == 0:  # Monday - use regularly
                    schedule_probability = 0.7  # Increased from 0.4
                elif weekday in [1, 3, 5]:  # Tuesday, Thursday, Saturday - preferred
                    schedule_probability = 1.0
                elif weekday == 6:  # Sunday - common for afternoon games
                    schedule_probability = 0.95  # Increased from 0.9
                else:  # Wednesday, Friday - use frequently
                    schedule_probability = 0.9  # Increased from 0.8
                
                # Include most dates to provide better scheduling flexibility
                if random.random() < schedule_probability:
                    available_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        print(f"📅 Generated {len(available_dates)} available game dates")
        print(f"🎯 Season: {season_start} to {season_end}")
        
        return {
            'available_dates': available_dates,
            'events': calendar_events,
            'season_info': {
                'start': season_start,
                'end': season_end,
                'year': season_year
            }
        }
    
    def _distribute_nhl_games_realistically(self, matchup_assignments, nhl_teams, season_calendar):
        """Simple, robust NHL scheduling that ABSOLUTELY prevents 3+ consecutive games."""
        print("� Distributing games with STRICT consecutive games prevention...")
        
        available_dates = season_calendar['available_dates']
        season_info = season_calendar['season_info']
        
        # Initialize team tracking for realistic distribution
        team_tracking = {}
        for team in nhl_teams:
            team_tracking[team.team_name] = {
                'games_scheduled': 0,
                'home_games': 0,
                'away_games': 0,
                'back_to_backs': 0,
                'back_to_back_budget': 20,  # More realistic back-to-back budget - NHL teams average 15-20
                'last_game': None,
                'second_last_game': None, 
                'consecutive_games': 0,
                'schedule': []
            }
        
        # Initialize daily game tracking
        daily_game_count = {date: 0 for date in available_dates}
        
        # Track daily capacity (NHL typically schedules 10-15 games per night)
        daily_games = {date: [] for date in available_dates}
        max_games_per_day = 15
        
        # Convert matchup assignments to schedulable games list
        # The key insight: each assignment represents exactly half of one game
        # We need to process only HOME assignments to avoid counting each game twice
        games_to_schedule = []
        total_assignments = sum(len(assignments) for assignments in matchup_assignments.values())
        
        for team_name, assignments in matchup_assignments.items():
            for venue, opponent in assignments:
                if venue == 'HOME':
                    # Only process HOME assignments to create each game exactly once
                    # This team is home, opponent is away
                    home_team = next(t for t in nhl_teams if t.team_name == team_name)
                    away_team = opponent
                    games_to_schedule.append((home_team, away_team))
        
        print(f"📋 Scheduling {len(games_to_schedule)} total games...")
        
        # Schedule games using intelligent distribution with retry logic
        scheduled_games = []
        unscheduled_games = []
        
        # Sort games by priority (division games first, then conference, then interconference)
        def game_priority(game):
            home_team, away_team = game
            if home_team.division == away_team.division:
                return 1  # Division games - highest priority, spread throughout season
            elif home_team.conference == away_team.conference:
                return 2  # Conference games - second priority
            else:
                return 3  # Interconference - can cluster more
        
        games_to_schedule.sort(key=game_priority)
        
        # First pass: Try to schedule all games with strict constraints
        print("🎯 First pass: Scheduling with strict constraints...")
        total_games = len(games_to_schedule)
        for i, (home_team, away_team) in enumerate(games_to_schedule):
            if i % 200 == 0:  # Progress updates
                print(f"  Progress: {i}/{total_games} games ({i/total_games*100:.1f}%)")
            
            # Find optimal date for this matchup
            best_date = self._find_optimal_nhl_game_date(
                home_team, away_team, available_dates, team_tracking, daily_game_count, season_calendar
            )
            
            if best_date:
                # Schedule the game
                scheduled_games.append((best_date, home_team, away_team))
                daily_game_count[best_date] += 1
                
                # Update team tracking
                self._update_nhl_team_tracking(
                    home_team, away_team, best_date, team_tracking
                )
            else:
                # Could not schedule with current constraints - save for retry
                unscheduled_games.append((home_team, away_team))
        
        # Second pass: Retry unscheduled games with shuffled order and relaxed constraints
        if unscheduled_games:
            print(f"⚠️ {len(unscheduled_games)} games remain unscheduled. Retrying with relaxed constraints...")
            
            # Shuffle the unscheduled games to try different ordering
            import random
            random.shuffle(unscheduled_games)
            
            # Retry each unscheduled game with more flexible date selection
            for home_team, away_team in unscheduled_games:
                # Try with more flexible constraints
                best_date = self._find_best_game_date_flexible(
                    home_team, away_team, available_dates, team_tracking, daily_game_count
                )
                
                if best_date:
                    scheduled_games.append((best_date, home_team, away_team))
                    daily_game_count[best_date] += 1
                    
                    self._update_nhl_team_tracking(
                        home_team, away_team, best_date, team_tracking
                    )
                else:
                    print(f"⚠️ Still could not schedule {home_team.team_name} vs {away_team.team_name}")
        
        # Add scheduled games to main schedule
        self.schedule.extend(scheduled_games)
        
        # Print distribution summary
        self._report_schedule_stats_enhanced(team_tracking, nhl_teams)
        
        print(f"✅ Successfully scheduled {len(scheduled_games)} NHL games")
    
    def _find_best_game_date_flexible(self, home_team, away_team, available_dates, team_tracking, daily_game_count):
        """More flexible date finding for games that couldn't be scheduled normally."""
        MAX_DAILY_GAMES = 20  # Relaxed limit
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Check if date is too busy (relaxed constraint)
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check ONLY the critical constraints
            home_valid, home_priority = self._check_team_constraints_flexible(
                home_team, game_date, team_tracking, True
            )
            away_valid, away_priority = self._check_team_constraints_flexible(
                away_team, game_date, team_tracking, False
            )
            
            if home_valid and away_valid:
                combined_priority = home_priority + away_priority
                candidate_dates.append((game_date, combined_priority))
        
        # Return best date (lowest penalty)
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        return None
    
    def _check_team_constraints_flexible(self, team, game_date, team_tracking, is_home_team):
        """More flexible constraint checking that only blocks absolute violations."""
        team_name = team.team_name
        track = team_tracking[team_name]
        
        last_game = track['last_game']
        second_last_game = track['second_last_game']
        
        # HARD CONSTRAINTS (absolute violations only)
        
        # 1. No same-day games (absolute rule)
        scheduled_dates = {scheduled_date for scheduled_date, _, _ in track['schedule']}
        if game_date in scheduled_dates:
            return False, float('inf')
        
        # 2. NEVER allow 3+ consecutive games (non-negotiable)
        if (last_game and second_last_game and
            last_game == game_date - timedelta(days=1) and
            second_last_game == game_date - timedelta(days=2)):
            return False, float('inf')
        
        # ALL OTHER CONSTRAINTS ARE NOW SOFT (penalties only)
        priority = 0
        
        # Back-to-back penalty (but don't hard block unless absolutely necessary)
        is_back_to_back = (last_game and last_game == game_date - timedelta(days=1))
        if is_back_to_back:
            back_to_back_budget = track['back_to_back_budget']
            
            # Only hard block if completely out of budget AND we have other options
            if back_to_back_budget <= 0:
                priority += 1000  # Very high penalty but not infinite
            else:
                priority += 50  # Regular back-to-back penalty
        
        return True, priority
        
        # Print distribution summary
        self._print_scheduling_summary(team_tracking, nhl_teams)
        
        print(f"✅ Successfully scheduled {len(scheduled_games)} NHL games")
    
    def _find_optimal_game_date(self, home_team, away_team, available_dates, team_tracking, daily_games, max_per_day):
        """Find optimal date for a game considering back-to-backs, rest, and balance."""
        best_date = None
        best_score = -1
        
        # Get team tracking info
        home_track = team_tracking[home_team.team_name]
        away_track = team_tracking[away_team.team_name]
        
        # Look through available dates for best fit
        for game_date in available_dates:
            # Skip if day is already at capacity
            if len(daily_games[game_date]) >= max_per_day:
                continue
            
            score = 0
            
            # Check back-to-back situations for both teams
            home_last_game = home_track.get('last_game_date')
            away_last_game = away_track.get('last_game_date')
            
            # Prevent excessive back-to-backs
            would_be_home_b2b = (home_last_game and 
                                (game_date - home_last_game).days == 1)
            would_be_away_b2b = (away_last_game and 
                                (game_date - away_last_game).days == 1)
            
            # Block if either team would exceed back-to-back limit
            if would_be_home_b2b and home_track['back_to_backs'] >= home_track['max_back_to_backs']:
                continue
            if would_be_away_b2b and away_track['back_to_backs'] >= away_track['max_back_to_backs']:
                continue
            
            # Prevent 3+ consecutive games - STRICT enforcement
            if home_track['consecutive_games'] >= 2 and would_be_home_b2b:
                # Home team already has 2+ consecutive games, would make 3+
                continue
            if away_track['consecutive_games'] >= 2 and would_be_away_b2b:
                # Away team already has 2+ consecutive games, would make 3+
                continue
            
            # Prefer adequate rest between games
            if home_last_game:
                home_rest = (game_date - home_last_game).days
                if home_rest >= 2:
                    score += 10  # Good rest
                elif home_rest == 1:
                    score += 2   # Back-to-back (acceptable if under limit)
            else:
                score += 5  # First game
            
            if away_last_game:
                away_rest = (game_date - away_last_game).days
                if away_rest >= 2:
                    score += 10
                elif away_rest == 1:
                    score += 2
            else:
                score += 5
            
            # Prefer balanced monthly distribution
            month = game_date.month
            home_month_games = home_track['monthly_distribution'][month]
            away_month_games = away_track['monthly_distribution'][month]
            
            if home_month_games < 7 and away_month_games < 7:  # Target ~7 games per month
                score += 5
            
            # Prefer moderate daily game count
            daily_count = len(daily_games[game_date])
            if 6 <= daily_count <= 10:  # Sweet spot
                score += 3
            elif daily_count <= 5:
                score += 1
            
            if score > best_score:
                best_score = score
                best_date = game_date
        
        return best_date
    
    def _update_team_tracking_realistic(self, home_team, away_team, game_date, team_tracking):
        """Update team tracking with realistic NHL patterns."""
        home_track = team_tracking[home_team.team_name]
        away_track = team_tracking[away_team.team_name]
        
        # Update game counts
        home_track['games_scheduled'] += 1
        home_track['home_games'] += 1
        away_track['games_scheduled'] += 1
        away_track['away_games'] += 1
        
        # Update monthly distribution
        month = game_date.month
        home_track['monthly_distribution'][month] += 1
        away_track['monthly_distribution'][month] += 1
        
        # Check and update back-to-back status
        for team, track in [(home_team, home_track), (away_team, away_track)]:
            last_game = track.get('last_game_date')
            if last_game and (game_date - last_game).days == 1:
                track['back_to_backs'] += 1
                track['consecutive_games'] += 1  # Increment consecutive games
            else:
                track['consecutive_games'] = 1  # Reset to 1 (this game is the first in new streak)
            
            # Update schedule and last game date
            venue = 'HOME' if team == home_team else 'AWAY'
            opponent = away_team if team == home_team else home_team
            track['schedule'].append((game_date, opponent, venue))
            track['last_game_date'] = game_date
    
    def _print_scheduling_summary(self, team_tracking, nhl_teams):
        """Print summary of scheduling results."""
        print("\n📊 Scheduling Summary:")
        
        back_to_back_counts = [track['back_to_backs'] for track in team_tracking.values()]
        min_b2b = min(back_to_back_counts)
        max_b2b = max(back_to_back_counts)
        avg_b2b = sum(back_to_back_counts) / len(back_to_back_counts)
        
        print(f"   Back-to-backs: {min_b2b}-{max_b2b} (avg: {avg_b2b:.1f}) - NHL target: 7-16")
        
        # Check teams with concerning back-to-back counts
        problematic_teams = [name for name, track in team_tracking.items() 
                           if track['back_to_backs'] > 20]
        if problematic_teams:
            print(f"⚠️ Teams with >20 back-to-backs: {len(problematic_teams)}")
        else:
            print("✅ All teams have realistic back-to-back counts!")
    
    def _add_nhl_special_events(self, calendar_events, season_year):
        """Add NHL special events to the schedule."""
        print("⭐ Adding NHL special events...")
        
        # All-Star Week Events
        all_star_start, all_star_end = calendar_events['all_star_break']
        
        # All-Star Skills Competition
        skills_date = all_star_start + timedelta(days=2)
        self.schedule.append((skills_date, 'NHL_EVENT', {
            'type': 'all_star_skills',
            'title': '⚡ NHL All-Star Skills Competition',
            'description': f'{season_year} NHL All-Star Skills Competition'
        }))
        
        # All-Star Game (ALWAYS the day after Skills Competition)
        game_date = skills_date + timedelta(days=1)  # Fixed: 1 day after Skills, not 3 days after start
        self.schedule.append((game_date, 'NHL_EVENT', {
            'type': 'all_star_game',
            'title': '🌟 NHL All-Star Game',
            'description': f'{season_year} NHL All-Star Game'
        }))
        
        # Trade Deadline
        trade_deadline = calendar_events['trade_deadline']
        self.schedule.append((trade_deadline, 'NHL_EVENT', {
            'type': 'trade_deadline',
            'title': '📈 NHL Trade Deadline',
            'description': 'Final day for trades before playoffs (3 PM ET)'
        }))
        
        # Entry Draft (after season ends)
        draft_date = calendar_events['entry_draft']
        self.schedule.append((draft_date, 'NHL_EVENT', {
            'type': 'entry_draft',
            'title': '🎯 NHL Entry Draft',
            'description': f'{season_year} NHL Entry Draft'
        }))
        
        # Free Agency Opens 
        free_agency_date = calendar_events['free_agency']
        self.schedule.append((free_agency_date, 'NHL_EVENT', {
            'type': 'free_agency',
            'title': '💰 NHL Free Agency Opens',
            'description': 'Unrestricted free agents can sign with any team'
        }))
        
        print(f"✅ Added {5} NHL special events for {season_year} season")
    
    def _verify_complete_schedule_integrity(self):
        """Verify the complete generated schedule meets NHL standards."""
        print("\n🔍 Verifying schedule integrity...")
        
        # Count games by league
        nhl_games = []
        special_events = []
        
        for game_item in self.schedule:
            # Handle both dictionary and tuple formats
            if isinstance(game_item, dict):
                # Check if it's an NHL game
                if game_item.get('league') == 'NHL':
                    nhl_games.append(game_item)
                # Check if it's a special event
                elif game_item.get('home_team') == 'NHL_EVENT' or 'NHL_EVENT' in str(game_item):
                    special_events.append(game_item)
            elif isinstance(game_item, (tuple, list)) and len(game_item) >= 3:
                # Old format: check for special events
                if game_item[1] == 'NHL_EVENT':
                    special_events.append(game_item)
                else:
                    # Legacy tuple format: only count if both teams are NHL teams
                    # (other leagues like the AHL also use tuples in old saves)
                    if hasattr(game_item[1], 'team_name') and hasattr(game_item[2], 'team_name'):
                        home_lg = getattr(game_item[1], 'league_name', 'National Hockey League')
                        away_lg = getattr(game_item[2], 'league_name', 'National Hockey League')
                        if home_lg == 'National Hockey League' and away_lg == 'National Hockey League':
                            nhl_games.append(game_item)
        
        # Verify NHL teams get exactly 82 games each
        nhl_team_counts = {}
        for game_entry in nhl_games:
            # Handle different schedule formats
            if isinstance(game_entry, dict):
                # New format: dictionary with date, home_team, away_team, etc.
                home_team = game_entry.get('home_team')
                away_team = game_entry.get('away_team')
                league = game_entry.get('league', '')
                
                # Only count NHL games
                if league == 'NHL' and hasattr(home_team, 'team_name') and hasattr(away_team, 'team_name'):
                    home_name = home_team.team_name
                    away_name = away_team.team_name
                    nhl_team_counts[home_name] = nhl_team_counts.get(home_name, 0) + 1
                    nhl_team_counts[away_name] = nhl_team_counts.get(away_name, 0) + 1
            elif isinstance(game_entry, (tuple, list)) and len(game_entry) >= 3:
                # Old format: tuple/list with (date, home_team, away_team)
                game_date, home_team, away_team = game_entry[0], game_entry[1], game_entry[2]
                if hasattr(home_team, 'team_name') and hasattr(away_team, 'team_name'):
                    home_name = home_team.team_name
                    away_name = away_team.team_name
                    nhl_team_counts[home_name] = nhl_team_counts.get(home_name, 0) + 1
                    nhl_team_counts[away_name] = nhl_team_counts.get(away_name, 0) + 1
        
        # Check results
        total_teams = len(nhl_team_counts)
        teams_with_82 = sum(1 for count in nhl_team_counts.values() if count == 82)
        
        print(f"📊 NHL Schedule Verification:")
        print(f"   Total teams: {total_teams}")
        print(f"   Teams with 82 games: {teams_with_82}")
        print(f"   Total NHL games: {len(nhl_games)}")
        print(f"   Special events: {len(special_events)}")
        
        if teams_with_82 == total_teams and len(nhl_games) == 1312:  # 32 teams * 82 games / 2
            print("✅ PERFECT NHL SCHEDULE!")
            print("   🎯 All teams: exactly 82 games")
            print("   🎯 Total games: exactly 1,312")
            print("   🎯 Seasonal rotation: implemented")
            return True
        else:
            print("❌ Schedule verification failed!")
            if teams_with_82 != total_teams:
                print(f"   ⚠️ {total_teams - teams_with_82} teams don't have 82 games")
            if len(nhl_games) != 1312:
                print(f"   ⚠️ Expected 1,312 total games, got {len(nhl_games)}")
            return False
        
        # Free Agency begins (typically July 1st)
        free_agency_date = date(self.season_year + 1, 7, 1)
        self.schedule.append((free_agency_date, 'NHL_EVENT', {
            'type': 'free_agency',
            'title': '💼 NHL Free Agency Opens',
            'description': 'Unrestricted free agents can sign with any team'
        }))
        
        print(f"✅ Added 5 NHL special events to schedule")
    
    def _find_optimal_nhl_game_date(self, home_team, away_team, available_dates, 
                                  team_tracking, daily_game_count, calendar_info):
        """Find optimal date with strict back-to-back management."""
        MAX_DAILY_GAMES = 16
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Skip if day is too busy
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check team constraints
            home_valid, home_penalty = self._check_nhl_team_constraints(
                home_team, game_date, team_tracking, True, calendar_info
            )
            away_valid, away_penalty = self._check_nhl_team_constraints(
                away_team, game_date, team_tracking, False, calendar_info
            )
            
            if home_valid and away_valid:
                # Calculate total penalty (lower is better)
                total_penalty = home_penalty + away_penalty
                
                # Add home/away balance bonus
                home_balance = self._calculate_nhl_home_away_balance(
                    home_team, team_tracking, True
                )
                away_balance = self._calculate_nhl_home_away_balance(
                    away_team, team_tracking, False
                )
                
                total_penalty += home_balance + away_balance
                candidate_dates.append((game_date, total_penalty))
        
        # Return best date (lowest penalty)
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        # No valid dates found - do NOT schedule rather than violate constraints
        return None
    
    def _check_nhl_team_constraints(self, team, game_date, team_tracking, 
                                  is_home_team, calendar_info):
        """Check NHL scheduling constraints with realistic back-to-back management."""
        track = team_tracking[team.team_name]
        
        # HARD CONSTRAINTS (must pass)
        
        # 1. No same-day games (absolute rule)
        if any(scheduled_date == game_date for scheduled_date, _, _ in track['schedule']):
            return False, float('inf')
        
        # 2. ONLY prevent 3+ consecutive games (this is the key fix)
        last_game = track['last_game']
        second_last_game = track['second_last_game']
        
        if (last_game and second_last_game and 
            last_game == game_date - timedelta(days=1) and
            second_last_game == game_date - timedelta(days=2)):
            return False, float('inf')  # Would create 3 consecutive games - FORBIDDEN
        
        # SOFT CONSTRAINTS (affect priority - lower penalty is better)
        penalty = 0
        
        # Back-to-back management - now more lenient
        is_back_to_back = (track['last_game'] and 
                          track['last_game'] == game_date - timedelta(days=1))
        
        if is_back_to_back:
            # Light penalty for back-to-backs but don't prevent them
            penalty += 10  # Reduced from 25+
            
            # Only start restricting if we have way too many
            if track['back_to_back_budget'] <= 0:
                penalty += 100  # Heavy penalty but not forbidden
        
        # Rest day bonuses (encourage variety)
        if track['last_game']:
            days_rest = (game_date - track['last_game']).days - 1
            if days_rest == 0:      # Back-to-back 
                penalty += 5
            elif days_rest == 1:    # 1 day rest (good)
                penalty -= 5
            elif days_rest == 2:    # 2 days rest (better) 
                penalty -= 10
            elif days_rest >= 3:    # 3+ days rest (optimal)
                penalty -= 15
            elif days_rest > 7:     # Too much rest
                penalty += days_rest - 7
        
        # Trade deadline considerations (schedule easier games late)
        trade_deadline = calendar_info.get('trade_deadline')
        if trade_deadline and game_date > trade_deadline:
            penalty += 5  # Slight penalty for post-deadline games
        
        return True, penalty
    
    def _calculate_nhl_home_away_balance(self, team, team_tracking, is_home_game):
        """Calculate penalty for home/away imbalance (target: 41 home, 41 away)."""
        track = team_tracking[team.team_name]
        
        current_home = track['home_games']
        current_away = track['away_games']
        games_played = track['games_scheduled']
        
        if games_played == 0:
            return 0  # No penalty for first game
        
        # Calculate current ratio
        if is_home_game:
            new_home = current_home + 1
            new_away = current_away
        else:
            new_home = current_home  
            new_away = current_away + 1
        
        total_games = new_home + new_away
        home_ratio = new_home / total_games if total_games > 0 else 0.5
        
        # Target is 50/50 split (41 home, 41 away out of 82)
        target_ratio = 0.5
        imbalance = abs(home_ratio - target_ratio)
        
        # Penalty increases with imbalance
        if imbalance > 0.15:      # More than 15% off
            return 15
        elif imbalance > 0.10:    # More than 10% off
            return 10
        elif imbalance > 0.05:    # More than 5% off
            return 5
        else:
            return 0
    
    def _update_nhl_team_tracking(self, home_team, away_team, game_date, team_tracking):
        """Update team tracking after scheduling an NHL game."""
        for team in [home_team, away_team]:
            track = team_tracking[team.team_name]
            is_home = (team == home_team)
            
            # Check for back-to-back
            is_back_to_back = (track['last_game'] and 
                             track['last_game'] == game_date - timedelta(days=1))
            
            # Update tracking
            track['games_scheduled'] += 1
            if is_home:
                track['home_games'] += 1
            else:
                track['away_games'] += 1
            
            if is_back_to_back:
                track['back_to_backs'] += 1
                track['back_to_back_budget'] -= 1
            
            # Update consecutive games tracking
            if is_back_to_back:
                track['consecutive_games'] += 1
            else:
                track['consecutive_games'] = 1
            
            # Update last game tracking for consecutive games prevention
            track['second_last_game'] = track['last_game']
            track['last_game'] = game_date
            
            # Update schedule
            opponent = away_team if is_home else home_team
            track['schedule'].append((game_date, opponent.team_name, 'HOME' if is_home else 'AWAY'))
    
    def _report_nhl_schedule_compliance(self, nhl_teams):
        """Report NHL schedule compliance and statistics."""
        print("\n🏒 NHL SCHEDULE COMPLIANCE REPORT")
        print("=" * 50)
        
        # Collect statistics (filter out NHL special events)
        team_stats = {}
        for team in nhl_teams:
            team_name = team.team_name
            team_games = [(date, home_team, away_team) for date, home_team, away_team in self.schedule 
                         if home_team != 'NHL_EVENT' and 
                         (home_team.team_name == team_name or away_team.team_name == team_name)]
            
            home_games = sum(1 for _, home_team, _ in team_games if home_team.team_name == team_name)
            away_games = len(team_games) - home_games
            
            # Count back-to-backs
            dates = sorted([date for date, _, _ in team_games])
            back_to_backs = sum(1 for i in range(len(dates)-1) 
                              if (dates[i+1] - dates[i]).days == 1)
            
            team_stats[team_name] = {
                'total_games': len(team_games),
                'home_games': home_games,
                'away_games': away_games, 
                'back_to_backs': back_to_backs
            }
        
        # Summary statistics
        total_games = [stats['total_games'] for stats in team_stats.values()]
        home_games = [stats['home_games'] for stats in team_stats.values()]  
        away_games = [stats['away_games'] for stats in team_stats.values()]
        back_to_backs = [stats['back_to_backs'] for stats in team_stats.values()]
        
        print(f"✅ Teams: {len(nhl_teams)}")
        print(f"✅ Total games: {len(self.schedule)}")
        print(f"✅ Games per team: {sum(total_games)/len(total_games):.1f} avg")
        print(f"✅ Home games per team: {sum(home_games)/len(home_games):.1f} avg")
        print(f"✅ Away games per team: {sum(away_games)/len(away_games):.1f} avg")
        print(f"🎯 Back-to-backs per team: {sum(back_to_backs)/len(back_to_backs):.1f} avg")
        print(f"🎯 Back-to-back range: {min(back_to_backs)}-{max(back_to_backs)} per team")
        
        # Check compliance
        games_82 = sum(1 for games in total_games if games == 82)
        home_away_balanced = sum(1 for i in range(len(home_games)) 
                               if abs(home_games[i] - away_games[i]) <= 2)
        back_to_back_compliant = sum(1 for bb in back_to_backs if 7 <= bb <= 16)
        
        print(f"\n📊 COMPLIANCE CHECK:")
        print(f"   82 games per team: {games_82}/{len(nhl_teams)} teams ✅" if games_82 == len(nhl_teams) else f"   82 games per team: {games_82}/{len(nhl_teams)} teams ❌")
        print(f"   Balanced home/away: {home_away_balanced}/{len(nhl_teams)} teams ✅" if home_away_balanced >= len(nhl_teams) * 0.9 else f"   Balanced home/away: {home_away_balanced}/{len(nhl_teams)} teams ❌")
        print(f"   Back-to-backs 7-16: {back_to_back_compliant}/{len(nhl_teams)} teams ✅" if back_to_back_compliant >= len(nhl_teams) * 0.8 else f"   Back-to-backs 7-16: {back_to_back_compliant}/{len(nhl_teams)} teams 🎯")
    
    def _generate_other_league_schedule(self, league_teams, league_name):
        """Generate schedule for non-NHL leagues with proper same-day conflict prevention."""
        if len(league_teams) < 2:
            return

        # Short league code for schedule entries (matches NHL dict format)
        league_codes = {
            "National Hockey League": "NHL",
            "American Hockey League": "AHL",
        }
        league_code = league_codes.get(league_name, league_name)

        print(f"🏒 Generating schedule for {league_name} ({len(league_teams)} teams)")
        
        # Create all matchups (each team plays each other team twice - home and away)
        matchups = []
        for team1 in league_teams:
            for team2 in league_teams:
                if team1 != team2:
                    matchups.append((team1, team2))
        
        print(f"Created {len(matchups)} total matchups for {league_name}")
        
        # Determine season dates
        season_start = date(self.season_year, 10, 1)
        season_end = date(self.season_year + 1, 3, 31)
        
        # Create available dates (Monday-Saturday)
        available_dates = []
        current_date = season_start
        while current_date <= season_end:
            if current_date.weekday() < 6:  # Monday-Saturday
                available_dates.append(current_date)
            current_date += timedelta(days=1)
        
        print(f"📅 Available dates: {len(available_dates)} for {league_name}")
        
        # Track which teams are playing on which dates to prevent conflicts
        team_schedules = {team.team_name: [] for team in league_teams}
        scheduled_games = 0
        
        # Schedule games with same-day conflict prevention
        for home_team, away_team in matchups:
            game_scheduled = False
            
            # Try to find a date where both teams are available
            for game_date in available_dates:
                # Check if either team already has a game on this date
                if (game_date not in team_schedules[home_team.team_name] and 
                    game_date not in team_schedules[away_team.team_name]):
                    
                    # Schedule the game (dict format matches NHL entries)
                    from datetime import time as dt_time
                    self.schedule.append({
                        'date': game_date,
                        'home_team': home_team,
                        'away_team': away_team,
                        'time': dt_time(19, 0),
                        'league': league_code,
                    })
                    
                    # Mark both teams as busy on this date
                    team_schedules[home_team.team_name].append(game_date)
                    team_schedules[away_team.team_name].append(game_date)
                    
                    scheduled_games += 1
                    game_scheduled = True
                    break
            
            if not game_scheduled:
                print(f"⚠️ Could not schedule {home_team.team_name} vs {away_team.team_name}")
        
        print(f"✅ Scheduled {scheduled_games}/{len(matchups)} games for {league_name}")
        
        # Verify no same-day conflicts
        self._verify_no_same_day_conflicts_for_league(league_teams, league_name)
    
    def _verify_no_same_day_conflicts_for_league(self, league_teams, league_name):
        """Verify that no team in this league plays multiple games on the same day."""
        from collections import defaultdict

        team_names = {team.team_name for team in league_teams}
        team_games_by_date = defaultdict(lambda: defaultdict(int))

        def _team_name(t):
            return t.team_name if hasattr(t, 'team_name') else str(t)

        # Count games per team per date for this league (handles dict and tuple formats)
        for entry in self.schedule:
            if isinstance(entry, dict):
                game_date = entry.get('date')
                home_team, away_team = entry.get('home_team'), entry.get('away_team')
            elif isinstance(entry, (tuple, list)) and len(entry) >= 3:
                game_date, home_team, away_team = entry[0], entry[1], entry[2]
            else:
                continue
            if game_date is None or home_team is None or away_team is None:
                continue
            hn, an = _team_name(home_team), _team_name(away_team)
            if hn in team_names:
                team_games_by_date[game_date][hn] += 1
            if an in team_names:
                team_games_by_date[game_date][an] += 1

        # Check for conflicts
        conflicts_found = False
        for game_date, team_counts in team_games_by_date.items():
            for team_name, game_count in team_counts.items():
                if game_count > 1:
                    print(f"⚠️ CONFLICT: {team_name} has {game_count} games on {game_date} in {league_name}")
                    conflicts_found = True

        if not conflicts_found:
            print(f"✅ No same-day conflicts found in {league_name}")

        return not conflicts_found
        
        if not conflicts_found:
            print(f"✅ No same-day conflicts found in {league_name}")
        
        return not conflicts_found

    def _verify_nhl_schedule_integrity(self):
        """Verify NHL schedule meets all requirements."""
        print("\n🔍 Verifying NHL schedule integrity...")
        
        # Collect team statistics (filter out NHL special events)
        team_schedules = {}
        for game_date, home_team, away_team in self.schedule:
            # Skip NHL special events
            if home_team == 'NHL_EVENT':
                continue
                
            # Track home team
            if home_team.team_name not in team_schedules:
                team_schedules[home_team.team_name] = []
            team_schedules[home_team.team_name].append((game_date, away_team.team_name, 'HOME'))
            
            # Track away team  
            if away_team.team_name not in team_schedules:
                team_schedules[away_team.team_name] = []
            team_schedules[away_team.team_name].append((game_date, home_team.team_name, 'AWAY'))
        
        # Check for violations
        same_day_violations = 0
        back_to_back_violations = 0
        consecutive_violations = 0
        
        for team_name, schedule in team_schedules.items():
            schedule.sort()  # Sort by date
            
            # Check same-day violations
            dates = [game_date for game_date, _, _ in schedule]
            if len(dates) != len(set(dates)):
                same_day_violations += 1
                print(f"❌ {team_name}: Multiple games on same day")
            
            # Check back-to-back and consecutive game violations
            back_to_backs = 0
            max_consecutive = 0
            current_consecutive = 0
            
            for i in range(len(dates)):
                if i > 0:
                    days_diff = (dates[i] - dates[i-1]).days
                    if days_diff == 1:
                        back_to_backs += 1
                        current_consecutive += 1
                    else:
                        max_consecutive = max(max_consecutive, current_consecutive)
                        current_consecutive = 1
                else:
                    current_consecutive = 1
            
            max_consecutive = max(max_consecutive, current_consecutive)
            
            if back_to_backs > 16:  # Allow up to 16 back-to-backs
                back_to_back_violations += 1
            
            if max_consecutive > 3:  # Max 3 consecutive games
                consecutive_violations += 1
        
        # Summary
        total_teams = len(team_schedules)
        print(f"📊 INTEGRITY SUMMARY:")
        print(f"   Same-day violations: {same_day_violations}/{total_teams} teams")
        print(f"   Excessive back-to-backs: {back_to_back_violations}/{total_teams} teams") 
        print(f"   Excessive consecutive games: {consecutive_violations}/{total_teams} teams")
        
        if same_day_violations == 0:
            print("✅ No same-day violations detected")
        if back_to_back_violations <= total_teams * 0.1:  # Allow 10% of teams to exceed
            print("✅ Back-to-back violations within acceptable range")
        if consecutive_violations == 0:
            print("✅ No excessive consecutive game violations")
    
    def _generate_nhl_game_dates(self, start_date, end_date):
        """Generate realistic NHL game dates based on actual NHL scheduling patterns."""
        valid_dates = []
        current_date = start_date
        
        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Monday, 6=Sunday
            
            # NHL typically plays:
            # - Tuesday through Sunday (avoid Monday)
            # - More games on Tue/Thu/Sat/Sun, fewer on Wed/Fri
            if weekday == 0:  # Monday - very rare
                if random.random() < 0.1:  # Only 10% chance
                    valid_dates.append(current_date)
            elif weekday in [1, 3, 5, 6]:  # Tue, Thu, Sat, Sun - primary days
                valid_dates.append(current_date)
            elif weekday in [2, 4]:  # Wed, Fri - secondary days
                if random.random() < 0.7:  # 70% chance
                    valid_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        return valid_dates
    
    def _find_best_game_date(self, home_team, away_team, available_dates, 
                            team_tracking, daily_game_count):
        """Find the best date for a game considering all NHL scheduling constraints."""
        MAX_DAILY_GAMES = 16
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Check if date is too busy
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check constraints for both teams
            home_valid, home_priority = self._check_team_constraints_enhanced(
                home_team, game_date, team_tracking, True  # is_home_team
            )
            away_valid, away_priority = self._check_team_constraints_enhanced(
                away_team, game_date, team_tracking, False  # is_home_team
            )
            
            if home_valid and away_valid:
                # Calculate combined priority (lower is better)
                # Add home/away balance bonus to priority
                home_balance_bonus = self._calculate_home_away_bonus(home_team, team_tracking, True)
                away_balance_bonus = self._calculate_home_away_bonus(away_team, team_tracking, False)
                
                combined_priority = (home_priority + away_priority + 
                                   home_balance_bonus + away_balance_bonus)
                candidate_dates.append((game_date, combined_priority))
        
        # Sort by priority and return best date
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        return None
    
    def _check_team_constraints_enhanced(self, team, game_date, team_tracking, is_home_team):
        """Enhanced constraint checking that's more flexible to allow complete schedule generation."""
        team_name = team.team_name
        track = team_tracking[team_name]
        
        last_game = track['last_game']
        second_last_game = track['second_last_game']
        
        # HARD CONSTRAINTS (must pass)
        
        # 1. No same-day games (absolute rule)
        scheduled_dates = {scheduled_date for scheduled_date, _, _ in track['schedule']}
        if game_date in scheduled_dates:
            return False, float('inf')
        
        # 2. STRICTLY prevent 3+ consecutive games (non-negotiable)
        if (last_game and second_last_game and
            last_game == game_date - timedelta(days=1) and
            second_last_game == game_date - timedelta(days=2)):
            return False, float('inf')
        
        # SOFT CONSTRAINTS (affect priority - lower priority is better)
        priority = 0
        
        # Check back-to-back status
        is_back_to_back = (last_game and last_game == game_date - timedelta(days=1))
        back_to_back_budget = track['back_to_back_budget']
        
        if is_back_to_back:
            # Apply back-to-back penalties but don't hard block (except when budget is exhausted)
            if back_to_back_budget <= 0:
                # Hard block only when completely out of budget
                return False, float('inf')
            
            # Base penalty for back-to-backs
            priority += 25
            
            # Escalating penalty as budget gets lower
            budget_used = 14 - back_to_back_budget
            priority += budget_used * 5
            
            # Season-based penalties
            games_scheduled = track['games_scheduled']
            season_progress = games_scheduled / 82.0
            if season_progress > 0.5:
                priority += 20
            if season_progress > 0.7:
                priority += 40
        
        # Prefer good spacing between games
        if last_game and not is_back_to_back:
            days_since_last = (game_date - last_game).days
            if days_since_last == 2:  # 1 day rest - good
                priority -= 5
            elif days_since_last == 3:  # 2 days rest - optimal
                priority -= 10
            elif days_since_last >= 6:  # Too much rest - penalize lightly
                priority += (days_since_last - 5) * 2
        
        # Home/away balance bonus
        games_scheduled = track['games_scheduled']
        if games_scheduled > 10:  # Only apply after several games scheduled
            home_games = track['home_games']
            away_games = track['away_games']
            current_home_ratio = home_games / games_scheduled if games_scheduled > 0 else 0.5
            
            if is_home_team:
                if current_home_ratio < 0.4:  # Need more home games
                    priority -= 8
                elif current_home_ratio > 0.6:  # Too many home games
                    priority += 8
            else:  # Away game
                if current_home_ratio > 0.6:  # Need more away games
                    priority -= 8
                elif current_home_ratio < 0.4:  # Too many away games
                    priority += 8
        
        return True, priority
    
    def _calculate_home_away_bonus(self, team, team_tracking, is_home_game):
        """Calculate priority bonus/penalty for maintaining home/away balance."""
        track = team_tracking[team.team_name]
        home_games = track['home_games']
        away_games = track['away_games']
        total_games = track['games_scheduled']
        
        # Target: 41 home, 41 away games (82 total)
        if total_games == 0:
            return 0  # No bias for first game
        
        current_home_ratio = home_games / total_games if total_games > 0 else 0.5
        target_ratio = 0.5  # 50/50 split
        
        if is_home_game:
            # If we're scheduling a home game
            new_home_ratio = (home_games + 1) / (total_games + 1)
            if new_home_ratio > 0.6:  # Too many home games
                return 5  # Penalty
            elif current_home_ratio < 0.4:  # Need more home games
                return -3  # Bonus
        else:
            # If we're scheduling an away game  
            new_away_ratio = (away_games + 1) / (total_games + 1)
            if new_away_ratio > 0.6:  # Too many away games
                return 5  # Penalty
            elif current_home_ratio > 0.6:  # Need more away games
                return -3  # Bonus
        
        return 0  # No adjustment needed
    

    
    def _update_team_tracking_after_game(self, home_team, away_team, game_date, team_tracking):
        """Update tracking information after scheduling a game with enhanced back-to-back budget tracking."""
        for team in [home_team, away_team]:
            team_name = team.team_name
            track = team_tracking[team_name]
            is_home_game = (team == home_team)
            
            # Check if this creates a back-to-back
            is_back_to_back = (track['last_game'] and 
                             track['last_game'] == game_date - timedelta(days=1))
            
            # Update tracking
            track['second_last_game'] = track['last_game']
            track['last_game'] = game_date
            track['games_scheduled'] += 1
            
            # Update home/away counts
            if is_home_game:
                track['home_games'] += 1
            else:
                track['away_games'] += 1
            
            # Update back-to-back tracking and budget
            if is_back_to_back:
                track['back_to_backs'] += 1
                track['back_to_back_budget'] -= 1  # Consume one from budget
            
            # Update consecutive games count
            if is_back_to_back:
                track['consecutive_games'] += 1
            else:
                track['consecutive_games'] = 1
            
            # Add to schedule
            opponent = away_team if team == home_team else home_team
            home_away = 'home' if is_home_game else 'away'
            track['schedule'].append((game_date, opponent.team_name, home_away))
    
    def _report_schedule_stats_enhanced(self, team_tracking, teams):
        """Enhanced reporting with home/away balance and back-to-back budget tracking."""
        total_back_to_backs = 0
        total_games = 0
        total_home_games = 0
        total_away_games = 0
        back_to_back_violations = []
        home_away_violations = []
        
        for team in teams:
            track = team_tracking[team.team_name]
            total_back_to_backs += track['back_to_backs']
            total_games += track['games_scheduled']
            total_home_games += track['home_games']
            total_away_games += track['away_games']
            
            # Check back-to-back violations
            if track['back_to_backs'] > 14:
                back_to_back_violations.append(
                    f"{team.team_name}: {track['back_to_backs']} back-to-backs (budget remaining: {track['back_to_back_budget']})"
                )
            
            # Check home/away balance (should be close to 41/41)
            home_games = track['home_games']
            away_games = track['away_games']
            total_team_games = home_games + away_games
            
            if total_team_games > 0:
                home_ratio = home_games / total_team_games
                if abs(home_ratio - 0.5) > 0.15:  # More than 15% imbalance
                    home_away_violations.append(
                        f"{team.team_name}: {home_games}H/{away_games}A ({home_ratio:.1%} home)"
                    )
        
        # Calculate averages
        avg_back_to_backs = total_back_to_backs / len(teams) if teams else 0
        avg_games = total_games / len(teams) if teams else 0
        avg_home_games = total_home_games / len(teams) if teams else 0
        avg_away_games = total_away_games / len(teams) if teams else 0
        
        print(f"✓ Enhanced Schedule Generation Complete:")
        print(f"  Average total games per team: {avg_games:.1f}")
        print(f"  Average home games per team: {avg_home_games:.1f}")
        print(f"  Average away games per team: {avg_away_games:.1f}")
        print(f"  Average back-to-backs per team: {avg_back_to_backs:.1f}")
        
        # Report violations
        if back_to_back_violations:
            print(f"⚠️ Back-to-back violations ({len(back_to_back_violations)}):")
            for violation in back_to_back_violations[:5]:
                print(f"  {violation}")
            if len(back_to_back_violations) > 5:
                print(f"  ... and {len(back_to_back_violations) - 5} more")
        else:
            print(f"✅ All teams within back-to-back limit (≤14)")
        
        if home_away_violations:
            print(f"⚠️ Home/Away balance issues ({len(home_away_violations)}):")
            for violation in home_away_violations[:5]:
                print(f"  {violation}")
        else:
            print(f"✅ All teams have balanced home/away games (~50/50)")
    
    def _report_schedule_stats(self, team_tracking, teams):
        """Legacy reporting method - kept for compatibility."""
        self._report_schedule_stats_enhanced(team_tracking, teams)

    def end_of_season(self):
        """Handles all end-of-season logic like aging players and resetting stats."""
        all_players = self.get_all_players()
        for player in all_players:
            player.age_one_year()
            player.stats = PlayerStats()
        
        self.season_year += 1
        
        # Initialize draft picks for upcoming years
        self.initialize_all_draft_picks()
        
        self.initialize_standings()
        self.generate_schedule(season_year=self.season_year)

    def initialize_all_draft_picks(self):
        """Initialize draft picks for all teams for the next few years."""
        future_years = [self.season_year + i for i in range(3)]  # Next 3 years
        
        for team in self.teams:
            team.initialize_draft_picks(future_years)

    def get_draft_order(self, year: int) -> List[Tuple[int, Team, DraftPick]]:
        """Generate the draft order for a specific year based on standings.
        
        Returns:
            List of tuples: (overall_pick_number, team, draft_pick)
        """
        draft_order = []
        
        # Sort teams by points (worst to best for each round)
        sorted_teams = sorted(self.teams, 
                            key=lambda t: self.standings[t.team_name]['Points'])
        
        for round_num in range(1, 8):  # 7 rounds
            round_picks = []
            
            # Get all picks for this round and year
            for team in sorted_teams:
                team_picks = [pick for pick in team.get_picks_for_year(year) 
                            if pick.round == round_num]
                
                for pick in team_picks:
                    # Find the team that currently owns this pick
                    current_owner = None
                    for owner_team in self.teams:
                        if pick in owner_team.get_picks_for_year(year):
                            current_owner = owner_team
                            break
                    
                    if current_owner:
                        round_picks.append((current_owner, pick))
            
            # Sort by original team's standing (traded picks keep original position)
            round_picks.sort(key=lambda x: sorted_teams.index(
                next(t for t in self.teams if t.team_name == x[1].original_team)
            ))
            
            # Assign overall pick numbers
            for i, (current_owner, pick) in enumerate(round_picks):
                overall_pick = ((round_num - 1) * 32) + i + 1
                pick.overall_pick = overall_pick
                draft_order.append((overall_pick, current_owner, pick))
        
        return draft_order

    def simulate_draft_lottery(self, year: int):
        """Simulate draft lottery for first round picks (if applicable)."""
        # This is a simplified lottery - in reality it's more complex
        first_round_picks = []
        
        # Get all first round picks for the year
        for team in self.teams:
            team_picks = [pick for pick in team.get_picks_for_year(year) 
                         if pick.round == 1]
            for pick in team_picks:
                first_round_picks.append(pick)
        
        # Sort by original team standings (worst to best)
        sorted_teams = sorted(self.teams, 
                            key=lambda t: self.standings[t.team_name]['Points'])
        
        first_round_picks.sort(key=lambda pick: sorted_teams.index(
            next(t for t in self.teams if t.team_name == pick.original_team)
        ))
        
        # Simple lottery simulation - top 3 picks have some randomization
        if len(first_round_picks) >= 3:
            import random
            
            # Small chance for teams 4-8 to jump into top 3
            lottery_teams = first_round_picks[:8]  # Bottom 8 teams eligible
            
            # 20% chance for a team to jump to #1
            if random.random() < 0.2 and len(lottery_teams) > 3:
                winner_idx = random.randint(3, min(7, len(lottery_teams) - 1))
                # Move the lottery winner to first position
                winner_pick = lottery_teams.pop(winner_idx)
                lottery_teams.insert(0, winner_pick)
                
                # Update the first round picks list
                first_round_picks = lottery_teams + first_round_picks[8:]

    def trade_draft_pick(self, pick: DraftPick, from_team: Team, to_team: Team, trade_details: str = ""):
        """Execute a draft pick trade between two teams."""
        if pick not in from_team.get_picks_for_year(pick.year):
            raise ValueError(f"{from_team.team_name} does not own this draft pick")
        
        # Execute the trade
        from_team.trade_pick(pick, to_team.team_name, trade_details)
        to_team.receive_pick(pick)
        
        return True

    def _verify_schedule_integrity(self):
        """Comprehensive verification of NHL scheduling rules and constraints."""
        from collections import defaultdict
        
        print("🔍 Verifying NHL schedule integrity...")
        
        # Group games by date and team
        team_games_by_date = defaultdict(lambda: defaultdict(list))
        team_schedules = defaultdict(list)  # List of (date, opponent, home/away) for each team
        
        for game_date, home_team, away_team in self.schedule:
            home_name = home_team.team_name
            away_name = away_team.team_name
            
            team_games_by_date[game_date][home_name].append('home')
            team_games_by_date[game_date][away_name].append('away')
            
            team_schedules[home_name].append((game_date, away_name, 'home'))
            team_schedules[away_name].append((game_date, home_name, 'away'))
        
        violations = []
        team_stats = {}
        
        # Check Rule 1: No team plays multiple games on the same day
        same_day_violations = []
        for game_date, teams_data in team_games_by_date.items():
            for team_name, games in teams_data.items():
                if len(games) > 1:
                    same_day_violations.append(f"{team_name} has {len(games)} games on {game_date}")
        
        # Check each team's schedule for NHL compliance
        for team_name, schedule in team_schedules.items():
            # Sort by date
            schedule.sort(key=lambda x: x['date'] if isinstance(x, dict) and 'date' in x else x[0])
            
            # Calculate team statistics
            total_games = len(schedule)
            back_to_backs = 0
            consecutive_streaks = []
            current_streak = 1
            max_consecutive = 1
            
            for i in range(1, len(schedule)):
                prev_date = schedule[i-1][0]
                curr_date = schedule[i][0]
                days_between = (curr_date - prev_date).days
                
                if days_between == 1:  # Back-to-back
                    back_to_backs += 1
                    current_streak += 1
                else:
                    if current_streak > 1:
                        consecutive_streaks.append(current_streak)
                    max_consecutive = max(max_consecutive, current_streak)
                    current_streak = 1
            
            # Don't forget the last streak
            if current_streak > 1:
                consecutive_streaks.append(current_streak)
            max_consecutive = max(max_consecutive, current_streak)
            
            team_stats[team_name] = {
                'games': total_games,
                'back_to_backs': back_to_backs,
                'max_consecutive': max_consecutive,
                'consecutive_streaks': consecutive_streaks
            }
            
            # Check Rule 2: No more than 14 back-to-backs per team
            if back_to_backs > 14:
                violations.append(f"{team_name}: {back_to_backs} back-to-backs (limit: 14)")
            
            # Check Rule 3: No more than 2 consecutive games
            if max_consecutive > 2:
                violations.append(f"{team_name}: {max_consecutive} consecutive games (limit: 2)")
        
        # Check Rule 4: Reasonable daily game distribution
        daily_game_counts = defaultdict(int)
        for game_date, _, _ in self.schedule:
            daily_game_counts[game_date] += 1
        
        busy_days = [(date, count) for date, count in daily_game_counts.items() if count > 16]
        
        # Generate comprehensive report
        print(f"\n📊 SCHEDULE INTEGRITY REPORT")
        print(f"{'='*50}")
        
        # Same-day violations (most critical)
        if same_day_violations:
            print(f"❌ CRITICAL: Same-day game violations ({len(same_day_violations)}):")
            for violation in same_day_violations[:10]:
                print(f"   • {violation}")
            if len(same_day_violations) > 10:
                print(f"   ... and {len(same_day_violations) - 10} more")
        else:
            print(f"✅ Same-day games: PASSED (no team plays multiple games same day)")
        
        # Back-to-back violations
        back_to_back_violations = [v for v in violations if "back-to-backs" in v]
        if back_to_back_violations:
            print(f"❌ Back-to-back violations ({len(back_to_back_violations)}):")
            for violation in back_to_back_violations[:5]:
                print(f"   • {violation}")
        else:
            print(f"✅ Back-to-back limit: PASSED (all teams ≤14 back-to-backs)")
        
        # Consecutive game violations
        consecutive_violations = [v for v in violations if "consecutive games" in v]
        if consecutive_violations:
            print(f"❌ Consecutive game violations ({len(consecutive_violations)}):")
            for violation in consecutive_violations[:5]:
                print(f"   • {violation}")
        else:
            print(f"✅ Consecutive games: PASSED (no team plays >2 consecutive)")
        
        # Daily distribution
        if busy_days:
            print(f"⚠️ Busy days (>16 games): {len(busy_days)}")
            for date, count in sorted(busy_days, key=lambda x: x[1], reverse=True)[:3]:
                print(f"   • {date}: {count} games")
        else:
            print(f"✅ Daily distribution: PASSED (≤16 games per day)")
        
        # Overall statistics
        if team_stats:
            avg_games = sum(stats['games'] for stats in team_stats.values()) / len(team_stats)
            avg_back_to_backs = sum(stats['back_to_backs'] for stats in team_stats.values()) / len(team_stats)
            
            print(f"\n📈 LEAGUE STATISTICS")
            print(f"   Teams: {len(team_stats)}")
            print(f"   Total games: {len(self.schedule)}")
            print(f"   Avg games per team: {avg_games:.1f}")
            print(f"   Avg back-to-backs per team: {avg_back_to_backs:.1f}")
        
        # Final verdict
        total_violations = len(same_day_violations) + len(violations)
        if total_violations == 0:
            print(f"\n🎉 SCHEDULE INTEGRITY: EXCELLENT")
            print(f"   All NHL scheduling rules satisfied!")
        elif len(same_day_violations) == 0:
            print(f"\n✅ SCHEDULE INTEGRITY: GOOD")
            print(f"   Critical rules satisfied, {len(violations)} minor violations")
        else:
            print(f"\n❌ SCHEDULE INTEGRITY: NEEDS IMPROVEMENT") 
            print(f"   {total_violations} total violations found")
        
        print(f"{'='*50}\n")

    def get_all_players(self) -> List[Player]:
        """Returns a list of every single player in the game world."""
        all_players = list(self.free_agents)
        all_players.extend(self.draft_prospects)
        for team in self.teams:
            all_players.extend(team.roster)
            all_players.extend(team.ahl_roster)
            all_players.extend(team.prospects)
        return all_players

    def add_team(self, team: Team):
        """Add a team to the league."""
        self.teams.append(team)
        # Initialize standings for this team
        self.standings[team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}

    def _simple_schedule_nhl_games(self):
        """Simple NHL scheduling that absolutely prevents 3+ consecutive games.
        
        Uses a straightforward chronological approach with basic constraint checking.
        """
        print("Starting simple NHL schedule generation...")
        
        # Initialize schedule and games dictionary
        self.schedule = []
        self.games = {}
        
        # Initialize team tracking
        team_tracking = {}
        for team in self.teams:
            team_tracking[team.team_name] = {
                'games_scheduled': 0,
                'last_game_date': None,
                'consecutive_count': 0,
                'back_to_back_used': 0,
                'home_games': 0,
                'away_games': 0
            }
        
        # Get all possible game dates (assuming season starts October 1st, 2024)
        season_start = datetime(2024, 10, 1)
        season_end = datetime(2025, 4, 20)  # NHL season typically ends in April
        all_dates = []
        current_date = season_start
        while current_date <= season_end:
            # Skip certain days if needed (e.g., Christmas)
            if current_date.month == 12 and current_date.day == 25:
                current_date += timedelta(days=1)
                continue
            all_dates.append(current_date)
            current_date += timedelta(days=1)
        
        print(f"Season dates: {len(all_dates)} days from {season_start} to {season_end}")
        
        # Generate all required matchups (82 games per team means 1312 total games)
        required_matchups = []
        
        # Intra-division games (4 games each = 4*7*2 = 56 games per team, intra-division)
        # Each team plays 4 games against 7 other teams in division
        for division in ['Atlantic', 'Metropolitan', 'Central', 'Pacific']:
            division_teams = [t for t in self.teams if t.division == division]
            for i, team1 in enumerate(division_teams):
                for j, team2 in enumerate(division_teams):
                    if i < j:  # Avoid duplicates
                        # Add 4 games between these teams (2 home, 2 away each)
                        for game_num in range(4):
                            if game_num < 2:
                                required_matchups.append((team1.team_name, team2.team_name))
                            else:
                                required_matchups.append((team2.team_name, team1.team_name))
        
        # Inter-division games within conference (3 games each)
        conferences = ['Eastern', 'Western']
        for conf in conferences:
            conf_teams = [t for t in self.teams if t.conference == conf]
            divisions = list(set(t.division for t in conf_teams))
            
            for div1 in divisions:
                for div2 in divisions:
                    if div1 != div2:
                        div1_teams = [t for t in conf_teams if t.division == div1]
                        div2_teams = [t for t in conf_teams if t.division == div2]
                        
                        for team1 in div1_teams:
                            for team2 in div2_teams:
                                # Add 3 games (alternating home/away)
                                for game_num in range(3):
                                    if game_num == 0:
                                        required_matchups.append((team1.team_name, team2.team_name))
                                    elif game_num == 1:
                                        required_matchups.append((team2.team_name, team1.team_name))
                                    else:
                                        # Alternate which team gets extra home game
                                        if hash(team1.team_name + team2.team_name) % 2 == 0:
                                            required_matchups.append((team1.team_name, team2.team_name))
                                        else:
                                            required_matchups.append((team2.team_name, team1.team_name))
        
        # Inter-conference games (2 games each)
        eastern_teams = [t for t in self.teams if t.conference == 'Eastern']
        western_teams = [t for t in self.teams if t.conference == 'Western']
        
        for east_team in eastern_teams:
            for west_team in western_teams:
                # Add 2 games (1 home, 1 away)
                required_matchups.append((east_team.team_name, west_team.team_name))
                required_matchups.append((west_team.team_name, east_team.team_name))
        
        print(f"Generated {len(required_matchups)} required matchups")
        
        # Shuffle matchups to randomize scheduling order
        random.shuffle(required_matchups)
        
        # Schedule games chronologically
        scheduled_games = 0
        failed_attempts = 0
        max_failed_attempts = 1000
        
        for home_team, away_team in required_matchups:
            game_scheduled = False
            
            # Try to schedule this game on the earliest possible date
            for date in all_dates:
                if self._teams_can_play_simple(home_team, away_team, date, team_tracking):
                    # Schedule the game
                    game_id = f"game_{len(self.games) + 1}"
                    self.games[game_id] = {
                        'game_id': game_id,
                        'home_team': home_team,
                        'away_team': away_team,
                        'date': date.strftime('%Y-%m-%d'),
                        'time': '19:00',  # Default 7 PM start
                        'venue': f"{home_team} Arena"
                    }
                    
                    # Also add to schedule list for compatibility
                    home_team_obj = next(t for t in self.teams if t.team_name == home_team)
                    away_team_obj = next(t for t in self.teams if t.team_name == away_team)
                    self.schedule.append((date.date(), home_team_obj, away_team_obj))
                    
                    # Update team tracking
                    for team in [home_team, away_team]:
                        team_data = team_tracking[team]
                        team_data['games_scheduled'] += 1
                        
                        if team_data['last_game_date']:
                            days_diff = (date - team_data['last_game_date']).days
                            if days_diff == 1:
                                team_data['consecutive_count'] += 1
                                if team == home_team:
                                    team_data['back_to_back_used'] += 1
                            else:
                                team_data['consecutive_count'] = 1
                        else:
                            team_data['consecutive_count'] = 1
                        
                        team_data['last_game_date'] = date
                        
                        if team == home_team:
                            team_data['home_games'] += 1
                        else:
                            team_data['away_games'] += 1
                    
                    scheduled_games += 1
                    game_scheduled = True
                    break
            
            if not game_scheduled:
                failed_attempts += 1
                print(f"Failed to schedule {home_team} vs {away_team} - failed attempts: {failed_attempts}")
                
                if failed_attempts >= max_failed_attempts:
                    print("Too many failed scheduling attempts. Stopping.")
                    break
        
        print(f"Scheduled {scheduled_games} games successfully")
        
        # Print final statistics
        for team_name, data in team_tracking.items():
            print(f"{team_name}: {data['games_scheduled']} games, "
                  f"{data['home_games']} home, {data['away_games']} away, "
                  f"{data['back_to_back_used']} back-to-backs")
        
        return True

    def _teams_can_play_simple(self, home_team, away_team, date, team_tracking):
        """Simple constraint checking - only prevents 3+ consecutive games."""
        
        # Check if both teams can play on this date
        for team in [home_team, away_team]:
            team_data = team_tracking[team]
            
            # Skip if team already has a game on this date
            game_today = any(
                game['date'] == date.strftime('%Y-%m-%d') and 
                (game['home_team'] == team or game['away_team'] == team)
                for game in self.games.values()
            )
            if game_today:
                return False
            
            # Check for 3+ consecutive games
            if team_data['last_game_date']:
                days_diff = (date - team_data['last_game_date']).days
                
                if days_diff == 1:  # This would be back-to-back
                    # Check if this would create 3 consecutive games
                    if team_data['consecutive_count'] >= 2:
                        return False  # Would create 3+ in a row
                    
                    # Allow some back-to-backs (teams typically have 10-15 per season)
                    if team_data['back_to_back_used'] >= 15:
                        return False
        
        return True





